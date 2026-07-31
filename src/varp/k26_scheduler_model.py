"""Deterministic analytical reference model for K26 scheduler experiments.

This module is intentionally not RTL.  It models queueing, work stealing,
coarse memory/link service, and completion ordering so scheduler hypotheses can
be tested before the corresponding SpinalHDL is implemented.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import heapq
import math
import random
from statistics import mean
from typing import Any, Iterable


SCHEDULERS = ("S0", "S0-physical", "S1", "S2", "S3", "Oracle")
WORKLOADS = ("balanced", "skew", "hotspot", "bursty", "mixed")
CLUSTER_COUNTS = (1, 2, 4)
CHANNEL_COUNTS = (1, 2, 4)
BUNDLE_COUNTS = (1, 2, 4)
LINK_WIDTHS = (32, 64, 128, 256)
SERVICE_OVERLAP_MODES = ("full", "sequential")


@dataclass(frozen=True)
class TileJob:
    job_id: int
    arrival_timestamp: int
    layer_id: int
    operation_type: str
    activation_id: int
    weight_base: int
    output_base: int
    k_start: int
    k_length: int
    n_start: int
    n_length: int
    preferred_channel: int
    preferred_link_bundle: int
    reduction_owner: int
    priority: int
    stealable: bool
    home_cluster: int

    def identity(self) -> str:
        payload = "|".join(str(value) for value in asdict(self).values())
        return hashlib.sha256(payload.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class ModelConfig:
    scheduler: str = "S3"
    clusters: int = 4
    channels: int = 4
    bundles: int = 4
    link_width_bits: int = 128
    queue_capacity: int = 2048
    channel_bytes_per_cycle: int = 16
    compute_mac_per_cycle: int = 64
    bundle_clock_ratio: int = 1
    locality_age_weight: float = 1.0
    remote_weight_penalty: float = 10.0
    activation_penalty: float = 4.0
    reduction_penalty: float = 6.0
    link_contention_penalty: float = 2.0
    slow_channel: int | None = None
    slow_channel_factor: int = 1
    stalled_bundle: int | None = None
    delayed_cluster: int | None = None
    delayed_cluster_cycles: int = 0
    deadlock_no_progress_cycles: int = 100_000
    central_arbitration_cycles: int = 2
    central_fanout_cycles: int = 2
    central_crossbar_cycles: int = 3
    service_overlap_mode: str = "full"

    def __post_init__(self) -> None:
        if self.scheduler not in SCHEDULERS:
            raise ValueError("unknown scheduler")
        if self.clusters not in CLUSTER_COUNTS:
            raise ValueError("clusters must be 1, 2, or 4")
        if self.channels not in CHANNEL_COUNTS:
            raise ValueError("channels must be 1, 2, or 4")
        if self.bundles not in BUNDLE_COUNTS:
            raise ValueError("bundles must be 1, 2, or 4")
        if self.link_width_bits not in LINK_WIDTHS:
            raise ValueError("link width must be 32, 64, 128, or 256")
        if self.service_overlap_mode not in SERVICE_OVERLAP_MODES:
            raise ValueError("service overlap mode must be full or sequential")
        if self.queue_capacity < 1:
            raise ValueError("queue capacity must be positive")
        if min(
            self.central_arbitration_cycles,
            self.central_fanout_cycles,
            self.central_crossbar_cycles,
        ) < 0:
            raise ValueError("central queue physical costs must be non-negative")
        if self.slow_channel is not None and not (
            0 <= self.slow_channel < self.channels
        ):
            raise ValueError("slow channel outside configured channels")
        if self.stalled_bundle is not None and not (
            0 <= self.stalled_bundle < self.bundles
        ):
            raise ValueError("stalled bundle outside configured bundles")
        if self.delayed_cluster is not None and not (
            0 <= self.delayed_cluster < self.clusters
        ):
            raise ValueError("delayed cluster outside configured clusters")


def generate_jobs(
    workload: str,
    count: int,
    seed: int,
    *,
    clusters: int = 4,
    channels: int = 4,
    bundles: int = 4,
    all_stealable: bool = True,
) -> list[TileJob]:
    """Generate a fixed-seed TileJob ledger without mutating global RNG."""

    if workload not in WORKLOADS:
        raise ValueError("unknown workload")
    if count < 1:
        raise ValueError("job count must be positive")
    rng = random.Random(seed)
    jobs: list[TileJob] = []
    for job_id in range(count):
        if workload == "balanced":
            arrival = job_id * 2
            home = job_id % clusters
            k_length, n_length = 64, 16
            channel = job_id % channels
        elif workload == "skew":
            arrival = job_id
            home = 0 if rng.random() < 0.72 else rng.randrange(clusters)
            k_length = rng.choice((64, 128, 256, 512))
            n_length = rng.choice((8, 16, 32))
            channel = job_id % channels
        elif workload == "hotspot":
            arrival = job_id
            home = job_id % clusters
            k_length, n_length = rng.choice((128, 256)), 16
            channel = 0 if rng.random() < 0.85 else rng.randrange(channels)
        elif workload == "bursty":
            arrival = (job_id // 50) * 120 + rng.randrange(4)
            home = rng.randrange(clusters)
            k_length, n_length = rng.choice((64, 128, 256)), 16
            channel = rng.randrange(channels)
        else:
            arrival = job_id + (job_id // 80) * 20
            home = 0 if rng.random() < 0.55 else rng.randrange(clusters)
            operation = rng.choice(("attention", "lm_head", "mlp"))
            if operation == "attention":
                k_length, n_length = 128, 16
            elif operation == "lm_head":
                k_length, n_length = 256, 32
            else:
                k_length, n_length = 512, 32
            channel = rng.randrange(channels)

        operation = (
            rng.choice(("attention", "lm_head", "mlp"))
            if workload == "mixed"
            else ("mlp" if workload != "balanced" else "attention")
        )
        bundle = home % bundles
        jobs.append(
            TileJob(
                job_id=job_id,
                arrival_timestamp=arrival,
                layer_id=job_id % 26,
                operation_type=operation,
                activation_id=job_id // 8,
                weight_base=job_id * 4096,
                output_base=job_id * 1024,
                k_start=0,
                k_length=k_length,
                n_start=(job_id % 64) * n_length,
                n_length=n_length,
                preferred_channel=channel,
                preferred_link_bundle=bundle,
                reduction_owner=home,
                # Priority is currently metadata rather than a scheduling key.
                # Randomizing it keeps every fixed-seed ledger distinct without
                # perturbing the balanced workload's resource distribution.
                priority=rng.randrange(4),
                stealable=all_stealable,
                home_cluster=home,
            )
        )
    return jobs


def ledger_sha256(jobs: Iterable[TileJob]) -> str:
    digest = hashlib.sha256()
    for job in jobs:
        digest.update(job.identity().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _percentile(values: list[int], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _static_target(job: TileJob, clusters: int) -> int:
    return job.home_cluster % clusters


def run_model(
    jobs: Iterable[TileJob],
    config: ModelConfig,
    *,
    seed: int,
    workload: str,
    process_repetition: int = 0,
) -> dict[str, Any]:
    """Run the event-driven scheduler and return manuscript-facing metrics."""

    source_jobs = list(jobs)
    input_ledger_hash = ledger_sha256(source_jobs)
    job_list = sorted(
        source_jobs,
        key=lambda job: (job.arrival_timestamp, job.job_id),
    )
    if not job_list:
        raise ValueError("at least one job is required")
    if len({job.job_id for job in job_list}) != len(job_list):
        raise ValueError("duplicate input job_id")

    global_queue = config.scheduler in ("S0", "S0-physical", "Oracle")
    queues: list[list[TileJob]] = [
        [] for _ in range(1 if global_queue else config.clusters)
    ]
    # Oracle is an offline analysis schedule: the full ledger is visible, but
    # service still cannot begin before each job's recorded arrival.
    ingress: list[TileJob] = list(job_list) if config.scheduler == "Oracle" else []
    next_arrival = len(job_list) if config.scheduler == "Oracle" else 0
    cluster_available = [0] * config.clusters
    if config.delayed_cluster is not None:
        cluster_available[config.delayed_cluster] = config.delayed_cluster_cycles
    channel_available = [0] * config.channels
    bundle_available = [0] * config.bundles
    completions: list[tuple[int, int, int, TileJob, dict[str, int]]] = []
    completed: dict[int, dict[str, Any]] = {}
    dispatched: set[int] = set()
    completion_order: list[int] = []
    # Reservation occupancy includes resource wait, link/memory service, and
    # compute. Compute busy counts only modeled MAC service. Keeping both
    # prevents reservation occupancy from being misreported as MAC utilization.
    cluster_reserved = [0] * config.clusters
    cluster_compute_busy = [0] * config.clusters
    channel_busy = [0] * config.channels
    bundle_busy = [0] * config.bundles
    max_depth = [0] * len(queues)
    queue_waits: list[int] = []
    steal_attempts = 0
    successful_steals = 0
    remote_weight_bytes = 0
    activation_retransmission_bytes = 0
    partial_sum_traffic_bytes = 0
    request_serializer_wait = 0
    request_credit_wait = 0
    request_cdc_wait = 0
    outstanding_table_full_wait = 0
    response_serializer_wait = 0
    response_cdc_wait = 0
    consumer_fifo_full_wait = 0
    bundle_contention_wait = 0
    memory_command_wait = 0
    central_queue_control_cycles = 0
    now = min(job.arrival_timestamp for job in job_list)
    last_progress = now
    timed_out = False

    def queue_index(job: TileJob) -> int:
        if global_queue:
            return 0
        return _static_target(job, config.clusters)

    def admit() -> bool:
        changed = False
        remaining: list[TileJob] = []
        for job in ingress:
            index = queue_index(job)
            if len(queues[index]) < config.queue_capacity:
                queues[index].append(job)
                max_depth[index] = max(max_depth[index], len(queues[index]))
                changed = True
            else:
                remaining.append(job)
        ingress[:] = remaining
        return changed

    def steal_score(job: TileJob, thief: int) -> float:
        age = max(0, now - job.arrival_timestamp)
        local_bundle = thief % config.bundles
        return (
            config.locality_age_weight * age
            - config.remote_weight_penalty
            * (job.k_length * job.n_length / 1024)
            * (job.home_cluster != thief)
            - config.activation_penalty * (job.home_cluster != thief)
            - config.reduction_penalty * (job.reduction_owner != thief)
            - config.link_contention_penalty
            * (job.preferred_link_bundle != local_bundle)
        )

    def choose(cluster: int) -> tuple[TileJob, bool] | None:
        nonlocal steal_attempts, successful_steals
        if config.scheduler in ("S0", "S0-physical"):
            if queues[0]:
                return queues[0].pop(0), False
            return None
        if config.scheduler == "Oracle":
            if not queues[0]:
                return None

            def optimistic_finish(job: TileJob) -> tuple[int, int, int]:
                bundle = job.preferred_link_bundle % config.bundles
                channel = job.preferred_channel % config.channels
                weight_bytes = job.k_length * job.n_length
                wire_bytes = weight_bytes + job.k_length + job.n_length * 4 + 32
                link_cycles = max(
                    1,
                    math.ceil(
                        wire_bytes
                        / (config.link_width_bits // 8)
                        * config.bundle_clock_ratio
                    ),
                )
                memory_cycles = max(
                    1,
                    math.ceil(weight_bytes / config.channel_bytes_per_cycle),
                )
                compute_cycles = max(
                    1,
                    math.ceil(weight_bytes / config.compute_mac_per_cycle),
                )
                start = max(
                    now,
                    job.arrival_timestamp,
                    bundle_available[bundle],
                    channel_available[channel],
                )
                return (
                    start + max(link_cycles, memory_cycles) + compute_cycles,
                    job.arrival_timestamp,
                    job.job_id,
                )

            chosen = min(queues[0], key=optimistic_finish)
            queues[0].remove(chosen)
            return chosen, False
        if queues[cluster]:
            return queues[cluster].pop(0), False
        if config.scheduler == "S1":
            return None
        steal_attempts += 1
        candidates: list[tuple[float, int, int, TileJob]] = []
        for victim, queue in enumerate(queues):
            if victim == cluster:
                continue
            for position, job in enumerate(queue):
                if not job.stealable:
                    continue
                if config.scheduler == "S2":
                    score = float(now - job.arrival_timestamp)
                else:
                    score = steal_score(job, cluster)
                    if score <= 0:
                        continue
                candidates.append(
                    (-score, job.arrival_timestamp, job.job_id, job)
                )
        if not candidates:
            return None
        candidates.sort()
        chosen = candidates[0][3]
        queues[queue_index(chosen)].remove(chosen)
        successful_steals += 1
        return chosen, True

    while len(completed) < len(job_list):
        progressed = False
        while (
            next_arrival < len(job_list)
            and job_list[next_arrival].arrival_timestamp <= now
        ):
            ingress.append(job_list[next_arrival])
            next_arrival += 1
            progressed = True
        progressed = admit() or progressed

        while completions and completions[0][0] <= now:
            finish, _sequence, cluster, job, details = heapq.heappop(completions)
            if job.job_id in completed:
                raise AssertionError("job completed more than once")
            completed[job.job_id] = {
                "finish": finish,
                "latency": finish - job.arrival_timestamp,
                "cluster": cluster,
                **details,
            }
            completion_order.append(job.job_id)
            progressed = True

        for cluster in range(config.clusters):
            if cluster_available[cluster] > now:
                continue
            selected = choose(cluster)
            if selected is None:
                continue
            job, stolen = selected
            if job.job_id in dispatched:
                raise AssertionError("job dispatched more than once")
            bundle = job.preferred_link_bundle % config.bundles
            channel = job.preferred_channel % config.channels
            if config.stalled_bundle == bundle:
                queues[queue_index(job)].insert(0, job)
                continue
            dispatched.add(job.job_id)
            weight_bytes = job.k_length * job.n_length
            activation_bytes = job.k_length
            output_bytes = job.n_length * 4
            wire_bytes = weight_bytes + activation_bytes + output_bytes + 32
            link_cycles = max(
                1,
                math.ceil(
                    wire_bytes
                    / (config.link_width_bits // 8)
                    * config.bundle_clock_ratio
                ),
            )
            memory_factor = (
                config.slow_channel_factor
                if config.slow_channel == channel
                else 1
            )
            memory_cycles = max(
                1,
                math.ceil(weight_bytes / config.channel_bytes_per_cycle)
                * memory_factor,
            )
            compute_cycles = max(
                1,
                math.ceil(
                    job.k_length * job.n_length
                    / config.compute_mac_per_cycle
                ),
            )
            physical_dispatch_cycles = (
                config.central_arbitration_cycles
                + config.central_fanout_cycles
                + config.central_crossbar_cycles
                if config.scheduler == "S0-physical"
                else 0
            )
            central_queue_control_cycles += physical_dispatch_cycles
            dispatch_ready = max(now, job.arrival_timestamp) + physical_dispatch_cycles
            link_start = max(dispatch_ready, bundle_available[bundle])
            link_end = link_start + link_cycles
            if config.service_overlap_mode == "full":
                memory_start = max(dispatch_ready, channel_available[channel])
            else:
                # Conservative analytical sensitivity only: serialize the two
                # coarse service resources. This is not a physical protocol
                # model and intentionally bounds the default full-overlap case.
                memory_start = max(link_end, channel_available[channel])
            link_wait = link_start - now
            memory_wait = memory_start - now
            data_ready = max(link_end, memory_start + memory_cycles)
            finish = data_ready + compute_cycles
            bundle_available[bundle] = link_end
            channel_available[channel] = memory_start + memory_cycles
            cluster_available[cluster] = finish
            cluster_reserved[cluster] += finish - now
            cluster_compute_busy[cluster] += compute_cycles
            bundle_busy[bundle] += link_cycles
            channel_busy[channel] += memory_cycles
            bundle_contention_wait += link_wait
            memory_command_wait += memory_wait
            request_serializer_wait += max(0, link_cycles - 1)
            request_credit_wait += link_wait
            request_cdc_wait += 1
            response_serializer_wait += max(0, math.ceil(output_bytes / 16) - 1)
            response_cdc_wait += 1
            queue_waits.append(now - job.arrival_timestamp)
            if stolen and job.home_cluster != cluster:
                remote_weight_bytes += weight_bytes
                activation_retransmission_bytes += activation_bytes
                if job.reduction_owner != cluster:
                    partial_sum_traffic_bytes += output_bytes
            details = {
                "queue_wait": now - job.arrival_timestamp,
                "link_wait": link_wait,
                "memory_wait": memory_wait,
                "compute_cycles": compute_cycles,
                "stolen": int(stolen),
            }
            heapq.heappush(
                completions,
                (finish, job.job_id, cluster, job, details),
            )
            progressed = True
        progressed = admit() or progressed

        if progressed:
            last_progress = now
        future = [value for value in cluster_available if value > now]
        if completions:
            future.append(completions[0][0])
        if next_arrival < len(job_list):
            future.append(job_list[next_arrival].arrival_timestamp)
        if not future:
            if len(completed) != len(job_list):
                timed_out = True
            break
        next_time = min(future)
        if next_time <= now:
            next_time = now + 1
        if next_time - last_progress > config.deadlock_no_progress_cycles:
            timed_out = True
            break
        now = next_time

    completed_ids = set(completed)
    input_ids = {job.job_id for job in job_list}
    correctness = (
        not timed_out
        and completed_ids == input_ids
        and dispatched == input_ids
        and len(completion_order) == len(set(completion_order))
    )
    end_cycle = max(
        (row["finish"] for row in completed.values()),
        default=now,
    )
    start_cycle = min(job.arrival_timestamp for job in job_list)
    total_cycles = max(1, end_cycle - start_cycle)
    latencies = [row["latency"] for row in completed.values()]
    total_queue_depth = sum(len(queue) for queue in queues) + len(ingress)
    compute_utilization = [
        min(1.0, busy / total_cycles) for busy in cluster_compute_busy
    ]
    reservation_occupancy = [
        min(1.0, busy / total_cycles) for busy in cluster_reserved
    ]
    channel_utilization = [
        min(1.0, busy / total_cycles) for busy in channel_busy
    ]
    bundle_utilization = [
        min(1.0, busy / total_cycles) for busy in bundle_busy
    ]
    queue_imbalance = (
        max(max_depth) - min(max_depth) if len(max_depth) > 1 else 0
    )
    total_compute_work = sum(
        math.ceil(job.k_length * job.n_length / config.compute_mac_per_cycle)
        for job in job_list
    )
    total_memory_work = sum(
        math.ceil(job.k_length * job.n_length / config.channel_bytes_per_cycle)
        for job in job_list
    )
    total_link_work = sum(
        math.ceil(
            (
                job.k_length * job.n_length
                + job.k_length
                + job.n_length * 4
                + 32
            )
            / (config.link_width_bits // 8)
            * config.bundle_clock_ratio
        )
        for job in job_list
    )
    longest_single_job = max(
        max(
            math.ceil(job.k_length * job.n_length / config.channel_bytes_per_cycle),
            math.ceil(
                (
                    job.k_length * job.n_length
                    + job.k_length
                    + job.n_length * 4
                    + 32
                )
                / (config.link_width_bits // 8)
                * config.bundle_clock_ratio
            ),
        )
        + math.ceil(job.k_length * job.n_length / config.compute_mac_per_cycle)
        for job in job_list
    )
    oracle_resource_lower_bound_cycles = max(
        math.ceil(total_compute_work / config.clusters),
        math.ceil(total_memory_work / config.channels),
        math.ceil(total_link_work / config.bundles),
        longest_single_job,
    )
    result = {
        "schema_version": "varp.k26.scheduler-model.v1",
        "evidence_type": "analytical-model",
        "scheduler": config.scheduler,
        "workload": workload,
        "seed": seed,
        "process_repetition": process_repetition,
        "clusters": config.clusters,
        "channels": config.channels,
        "bundles": config.bundles,
        "link_width_bits": config.link_width_bits,
        "service_overlap_mode": config.service_overlap_mode,
        "jobs": len(job_list),
        "ledger_sha256": input_ledger_hash,
        "completed_jobs": len(completed),
        "total_completion_cycles": total_cycles,
        "throughput_jobs_per_kcycle": len(completed) * 1000 / total_cycles,
        "mean_tile_latency_cycles": mean(latencies) if latencies else 0.0,
        "p50_tile_latency_cycles": _percentile(latencies, 0.50),
        "p95_tile_latency_cycles": _percentile(latencies, 0.95),
        "p99_tile_latency_cycles": _percentile(latencies, 0.99),
        # Backward-compatible name now has the literal compute-busy meaning.
        "cluster_utilization_mean": mean(compute_utilization),
        "cluster_compute_utilization_mean": mean(compute_utilization),
        "cluster_reservation_occupancy_mean": mean(reservation_occupancy),
        "cluster_idle_cycles": sum(
            max(0, total_cycles - busy) for busy in cluster_reserved
        ),
        "cluster_compute_idle_cycles": sum(
            max(0, total_cycles - busy) for busy in cluster_compute_busy
        ),
        "queue_wait_mean_cycles": mean(queue_waits) if queue_waits else 0.0,
        "max_queue_depth": max(max_depth, default=0),
        "queue_imbalance": queue_imbalance,
        "ingress_backlog_final": total_queue_depth,
        "steal_attempts": steal_attempts,
        "successful_steals": successful_steals,
        "steal_success_rate": (
            successful_steals / steal_attempts if steal_attempts else 0.0
        ),
        "remote_weight_bytes": remote_weight_bytes,
        "activation_retransmission_bytes": activation_retransmission_bytes,
        "partial_sum_traffic_bytes": partial_sum_traffic_bytes,
        "link_bundle_utilization_mean": mean(bundle_utilization),
        "ddr_channel_utilization_mean": mean(channel_utilization),
        "request_serializer_wait": request_serializer_wait,
        "request_credit_wait": request_credit_wait,
        "request_cdc_wait": request_cdc_wait,
        "outstanding_table_full_wait": outstanding_table_full_wait,
        "response_serializer_wait": response_serializer_wait,
        "response_cdc_wait": response_cdc_wait,
        "consumer_fifo_full_wait": consumer_fifo_full_wait,
        "bundle_contention_wait": bundle_contention_wait,
        "memory_command_wait": memory_command_wait,
        "central_queue_control_cycles": central_queue_control_cycles,
        "oracle_resource_lower_bound_cycles": oracle_resource_lower_bound_cycles,
        "oracle_schedule_kind": (
            "offline-clairvoyant-list-schedule"
            if config.scheduler == "Oracle"
            else "not-applicable"
        ),
        "starvation_ratio": (
            sum(
                1
                for value in cluster_reserved
                if value == 0
            )
            / config.clusters
        ),
        "completion_reordered": completion_order
        != sorted(completion_order),
        "timed_out": timed_out,
        "correctness": correctness,
        "input_job_id_count": len(input_ids),
        "completed_job_id_count": len(completed_ids),
        "duplicate_completion_count": (
            len(completion_order) - len(set(completion_order))
        ),
    }
    if not timed_out and not correctness:
        raise AssertionError("exact-once/no-loss invariant failed")
    return result
