from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from varp.k26_scheduler_model import (
    BUNDLE_COUNTS,
    CHANNEL_COUNTS,
    CLUSTER_COUNTS,
    LINK_WIDTHS,
    ModelConfig,
    SCHEDULERS,
    TileJob,
    WORKLOADS,
    generate_jobs,
    ledger_sha256,
    run_model,
)


ROOT = Path(__file__).resolve().parents[1]


class K26SchedulerModelTests(unittest.TestCase):
    def jobs(
        self,
        workload: str = "skew",
        count: int = 1000,
        seed: int = 19,
        *,
        stealable: bool = True,
    ):
        return generate_jobs(
            workload,
            count,
            seed,
            clusters=4,
            channels=4,
            bundles=4,
            all_stealable=stealable,
        )

    def simulate(self, jobs=None, **kwargs):
        workload = kwargs.pop("workload", "skew")
        return run_model(
            jobs or self.jobs(workload),
            ModelConfig(**kwargs),
            seed=19,
            workload=workload,
        )

    def test_supports_required_factor_domains(self) -> None:
        self.assertEqual(CLUSTER_COUNTS, (1, 2, 4))
        self.assertEqual(CHANNEL_COUNTS, (1, 2, 4))
        self.assertEqual(BUNDLE_COUNTS, (1, 2, 4))
        self.assertEqual(LINK_WIDTHS, (32, 64, 128, 256))
        self.assertEqual(
            SCHEDULERS,
            ("S0", "S0-physical", "S1", "S2", "S3", "Oracle"),
        )

    def test_fixed_seed_randomized_ledgers_are_deterministic(self) -> None:
        seed_plan = json.loads(
            (
                ROOT / "configs/experiments/k26_seed_ledger.json"
            ).read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(seed_plan["seeds"]), 5)
        identities = set()
        for workload in WORKLOADS:
            for seed in seed_plan["seeds"]:
                first = self.jobs(workload, 1000, seed)
                second = self.jobs(workload, 1000, seed)
                self.assertEqual(ledger_sha256(first), ledger_sha256(second))
                self.assertEqual(len(first), 1000)
                self.assertEqual(len({job.job_id for job in first}), 1000)
                identities.add(ledger_sha256(first))
        self.assertEqual(
            len(identities), len(WORKLOADS) * len(seed_plan["seeds"])
        )

    def test_all_schedulers_preserve_exact_once_no_loss(self) -> None:
        jobs = self.jobs()
        for scheduler in SCHEDULERS:
            with self.subTest(scheduler=scheduler):
                result = self.simulate(jobs, scheduler=scheduler)
                self.assertTrue(result["correctness"])
                self.assertEqual(result["completed_jobs"], 1000)
                self.assertEqual(result["duplicate_completion_count"], 0)
                self.assertEqual(
                    result["input_job_id_count"],
                    result["completed_job_id_count"],
                )
                self.assertEqual(result["evidence_type"], "analytical-model")

    def test_process_repetition_does_not_change_model_result(self) -> None:
        jobs = self.jobs("mixed")
        first = run_model(
            jobs,
            ModelConfig(),
            seed=19,
            workload="mixed",
            process_repetition=0,
        )
        second = run_model(
            jobs,
            ModelConfig(),
            seed=19,
            workload="mixed",
            process_repetition=2,
        )
        excluded = {"process_repetition"}
        self.assertEqual(
            {k: v for k, v in first.items() if k not in excluded},
            {k: v for k, v in second.items() if k not in excluded},
        )

    def test_optional_event_sink_records_source_trace_without_changing_metrics(self) -> None:
        jobs = self.jobs("skew", count=40, seed=23)
        events = []
        traced = run_model(
            jobs,
            ModelConfig(scheduler="S3"),
            seed=23,
            workload="skew",
            event_sink=events,
        )
        untraced = run_model(
            jobs,
            ModelConfig(scheduler="S3"),
            seed=23,
            workload="skew",
        )
        self.assertEqual(traced, untraced)
        self.assertEqual(len(events), 40)
        self.assertEqual({event["job_id"] for event in events}, set(range(40)))
        self.assertTrue(
            all(
                event["arrival_cycle"] <= event["dispatch_cycle"]
                <= event["compute_start_cycle"]
                < event["compute_end_cycle"]
                for event in events
            )
        )

    def test_oldest_eligible_stealing_and_locality_scoring(self) -> None:
        jobs = self.jobs("skew")
        s1 = self.simulate(jobs, scheduler="S1")
        s2 = self.simulate(jobs, scheduler="S2")
        s3 = self.simulate(jobs, scheduler="S3")
        self.assertEqual(s1["successful_steals"], 0)
        self.assertGreater(s2["successful_steals"], 0)
        self.assertGreater(s3["successful_steals"], 0)
        self.assertLess(s2["cluster_idle_cycles"], s1["cluster_idle_cycles"])
        self.assertLessEqual(
            s3["remote_weight_bytes"], s2["remote_weight_bytes"]
        )

    def test_compute_utilization_is_separate_from_reservation_occupancy(self) -> None:
        result = self.simulate(self.jobs("mixed"), scheduler="S3", workload="mixed")
        self.assertEqual(
            result["cluster_utilization_mean"],
            result["cluster_compute_utilization_mean"],
        )
        self.assertLess(
            result["cluster_compute_utilization_mean"],
            result["cluster_reservation_occupancy_mean"],
        )
        self.assertGreater(
            result["cluster_compute_idle_cycles"],
            result["cluster_idle_cycles"],
        )

    def test_sequential_service_is_an_explicit_conservative_sensitivity(self) -> None:
        jobs = self.jobs("mixed")
        full = self.simulate(
            jobs,
            scheduler="S3",
            workload="mixed",
            service_overlap_mode="full",
        )
        sequential = self.simulate(
            jobs,
            scheduler="S3",
            workload="mixed",
            service_overlap_mode="sequential",
        )
        self.assertEqual(full["service_overlap_mode"], "full")
        self.assertEqual(sequential["service_overlap_mode"], "sequential")
        self.assertGreaterEqual(
            sequential["total_completion_cycles"],
            full["total_completion_cycles"],
        )
        self.assertTrue(sequential["correctness"])

    def test_physical_central_queue_cost_and_oracle_bound_are_explicit(self) -> None:
        jobs = self.jobs("mixed", count=200)
        ideal = self.simulate(jobs, scheduler="S0", workload="mixed")
        physical = self.simulate(
            jobs,
            scheduler="S0-physical",
            workload="mixed",
        )
        oracle = self.simulate(jobs, scheduler="Oracle", workload="mixed")
        self.assertEqual(ideal["central_queue_control_cycles"], 0)
        self.assertEqual(
            physical["central_queue_control_cycles"],
            len(jobs) * 7,
        )
        self.assertGreaterEqual(
            physical["total_completion_cycles"],
            ideal["total_completion_cycles"],
        )
        self.assertEqual(
            oracle["oracle_schedule_kind"],
            "offline-clairvoyant-list-schedule",
        )
        self.assertLessEqual(
            oracle["oracle_resource_lower_bound_cycles"],
            oracle["total_completion_cycles"],
        )
        self.assertTrue(oracle["correctness"])

    def test_full_queues_apply_backpressure_without_loss(self) -> None:
        jobs = self.jobs("bursty", 1000)
        result = self.simulate(jobs, scheduler="S1", queue_capacity=4)
        self.assertTrue(result["correctness"])
        self.assertLessEqual(result["max_queue_depth"], 4)
        self.assertEqual(result["ingress_backlog_final"], 0)

    def test_slow_channel_increases_completion_time(self) -> None:
        jobs = self.jobs("hotspot")
        baseline = self.simulate(jobs)
        slow = self.simulate(
            jobs,
            slow_channel=0,
            slow_channel_factor=8,
        )
        self.assertTrue(slow["correctness"])
        self.assertGreater(
            slow["total_completion_cycles"],
            baseline["total_completion_cycles"],
        )

    def test_stalled_bundle_and_deadlock_timeout_are_explicit(self) -> None:
        result = self.simulate(
            self.jobs("balanced", 100),
            stalled_bundle=0,
            deadlock_no_progress_cycles=50,
        )
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["correctness"])
        self.assertLess(result["completed_jobs"], 100)

    def test_delayed_cluster_does_not_lose_jobs(self) -> None:
        result = self.simulate(
            self.jobs("mixed"),
            delayed_cluster=2,
            delayed_cluster_cycles=10_000,
        )
        self.assertTrue(result["correctness"])
        self.assertEqual(result["completed_jobs"], 1000)

    def test_repeated_steal_stress(self) -> None:
        result = self.simulate(self.jobs("skew"), scheduler="S2")
        self.assertTrue(result["correctness"])
        self.assertGreater(result["successful_steals"], 100)

    def test_no_eligible_job_is_never_stolen(self) -> None:
        result = self.simulate(
            self.jobs("skew", stealable=False),
            scheduler="S3",
        )
        self.assertTrue(result["correctness"])
        self.assertEqual(result["successful_steals"], 0)

    def test_response_reordering_preserves_exact_once(self) -> None:
        result = self.simulate(self.jobs("mixed"), scheduler="S3")
        self.assertTrue(result["completion_reordered"])
        self.assertTrue(result["correctness"])
        self.assertEqual(result["duplicate_completion_count"], 0)

    def test_duplicate_input_job_identity_is_rejected(self) -> None:
        job = self.jobs(count=1)[0]
        with self.assertRaisesRegex(ValueError, "duplicate input"):
            self.simulate([job, job])

    def test_invalid_stress_resource_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "stalled bundle"):
            ModelConfig(bundles=1, stalled_bundle=1)


class K26ExperimentRunnerTests(unittest.TestCase):
    def test_quick_runner_writes_bounded_manifest(self) -> None:
        import importlib.util

        path = ROOT / "scripts/run_k26_experiments.py"
        spec = importlib.util.spec_from_file_location("k26_runner", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            manifest = module.run(Path(directory), quick=True)
            self.assertEqual(manifest["evidence_type"], "analytical-model")
            self.assertTrue(manifest["all_correct"])
            self.assertFalse(manifest["any_timeout"])
            self.assertEqual(manifest["paper_first_factor_cases"], 52)
            self.assertEqual(manifest["process_rows"], 52)
            self.assertEqual(
                manifest["service_overlap_sensitivity"]["rows"],
                12,
            )
            self.assertGreater(
                manifest["full_cartesian_rows_not_run"],
                manifest["process_rows"],
            )


if __name__ == "__main__":
    unittest.main()
