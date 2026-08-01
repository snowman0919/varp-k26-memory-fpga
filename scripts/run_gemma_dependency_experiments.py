#!/usr/bin/env python3
"""Run dependency-, placement-, and remote-cost-aware Gemma experiments."""

from __future__ import annotations

import csv
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from varp.gemma_dependency_model import (  # noqa: E402
    PLACEMENTS,
    make_dependency_aware_tile_jobs,
)
from varp.k26_scheduler_model import ModelConfig, run_model  # noqa: E402


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run() -> dict[str, Any]:
    source = ROOT / "experiments/gemma3_1b/projection_trace.csv"
    projections = read_rows(source)
    rows: list[dict[str, Any]] = []
    placement_rows: list[dict[str, Any]] = []

    # Decode-1 spans every placement/policy and isolates the initial mapping.
    # Decode-32 then checks the two most informative placement extremes while
    # enforcing an autoregressive token barrier.
    matrix = [
        (1, placement, scheduler)
        for placement in PLACEMENTS
        for scheduler in ("S1", "S2", "S3")
    ] + [
        (32, placement, scheduler)
        for placement in ("source_rule", "size_aware")
        for scheduler in ("S1", "S3")
    ]

    cache: dict[str, tuple[Any, Any]] = {}
    additive_fields = {
        "jobs",
        "completed_jobs",
        "total_completion_cycles",
        "cluster_idle_cycles",
        "cluster_compute_idle_cycles",
        "steal_attempts",
        "successful_steals",
        "remote_weight_bytes",
        "activation_retransmission_bytes",
        "partial_sum_traffic_bytes",
        "charged_link_bytes",
        "base_link_bytes",
        "incremental_remote_link_bytes",
        "base_link_service_cycles",
        "incremental_remote_link_service_cycles",
        "base_memory_service_cycles",
        "incremental_remote_memory_service_cycles",
        "remote_copy_cycles",
        "request_serializer_wait",
        "request_credit_wait",
        "request_cdc_wait",
        "outstanding_table_full_wait",
        "response_serializer_wait",
        "response_cdc_wait",
        "consumer_fifo_full_wait",
        "bundle_contention_wait",
        "memory_command_wait",
        "central_queue_control_cycles",
        "dependency_edge_count",
        "input_job_id_count",
        "completed_job_id_count",
        "duplicate_completion_count",
    }
    model_result_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for decode_tokens, placement, scheduler in matrix:
        if placement not in cache:
            # One dependency-aware token is the atomic model run. Decode-32 is
            # a strict serialized repetition of this run, which prevents the
            # impossible cross-token overlap in the legacy experiment.
            cache[placement] = make_dependency_aware_tile_jobs(
                projections,
                decode_tokens=1,
                placement=placement,
                n_tile=1024,
            )
        jobs, summary = cache[placement]
        events: list[dict[str, Any]] | None = (
            []
            if decode_tokens == 1
            and placement == "source_rule"
            and scheduler in {"S1", "S3"}
            else None
        )
        result_key = (placement, scheduler)
        if result_key not in model_result_cache:
            model_result_cache[result_key] = run_model(
                jobs,
                ModelConfig(
                    scheduler=scheduler,
                    clusters=4,
                    channels=4,
                    bundles=4,
                    link_width_bits=128,
                    queue_capacity=max(4096, len(jobs)),
                    deadlock_no_progress_cycles=100_000_000_000,
                ),
                seed=0,
                workload="gemma3_1b_dependency_aware_tiles",
                event_sink=events,
            )
        result = copy.deepcopy(model_result_cache[result_key])
        if decode_tokens > 1:
            for field in additive_fields:
                result[field] *= decode_tokens
            result["ledger_sha256"] = hashlib.sha256(
                (
                    (result["ledger_sha256"] + "\n") * decode_tokens
                ).encode("ascii")
            ).hexdigest()
            result["throughput_jobs_per_kcycle"] = (
                result["jobs"] * 1000 / result["total_completion_cycles"]
            )
        result.update(
            {
                "decode_tokens": decode_tokens,
                "placement": placement,
                "n_tile": 1024,
                "projection_instances": len(projections) * decode_tokens,
                "tile_jobs_per_token": summary.tile_count_per_token,
                "cluster_tile_counts_per_token": "|".join(
                    str(value) for value in summary.cluster_tile_counts
                ),
                "cluster_mac_counts_per_token": "|".join(
                    str(value) for value in summary.cluster_mac_counts
                ),
                "dependency_semantics": (
                    "qkv->o->gate/up->down->next-layer; "
                    "strict serialized token repetition"
                ),
                "serialized_token_model": True,
                "placement_evidence_type": "deterministic-modeled-policy",
                "timing_evidence_type": "analytical-model-v2",
                "claim_boundary": (
                    "ONNX-derived projection shapes are split into modeled "
                    "full-K/N<=1024 tiles. Transformer-stage and token barriers "
                    "are conservative; this is not functional Gemma inference, "
                    "MIG/GTH timing, or request-level latency."
                ),
            }
        )
        rows.append(result)

        if events is not None:
            event_path = ROOT / (
                "results/model_level/events_"
                f"dependency_decode1_source_rule_{scheduler}.csv"
            )
            write_csv(event_path, events)

    for placement in PLACEMENTS:
        subset = [
            row
            for row in rows
            if row["decode_tokens"] == 1 and row["placement"] == placement
        ]
        s1 = next(row for row in subset if row["scheduler"] == "S1")
        for row in subset:
            placement_rows.append(
                {
                    "placement": placement,
                    "scheduler": row["scheduler"],
                    "tile_jobs": row["jobs"],
                    "cluster_tile_counts_per_token": row[
                        "cluster_tile_counts_per_token"
                    ],
                    "total_completion_cycles": row["total_completion_cycles"],
                    "tilejob_p95_cycles": row["p95_tile_latency_cycles"],
                    "tilejob_p99_cycles": row["p99_tile_latency_cycles"],
                    "remote_weight_bytes": row["remote_weight_bytes"],
                    "incremental_remote_link_bytes": row[
                        "incremental_remote_link_bytes"
                    ],
                    "completion_vs_same_placement_s1_pct": (
                        (row["total_completion_cycles"]
                         / s1["total_completion_cycles"] - 1)
                        * 100
                    ),
                    "claim_boundary": (
                        "Decode-1 analytical tile schedule; not request tail or "
                        "functional inference."
                    ),
                }
            )

    result_path = ROOT / "results/model_level/gemma3_1b_dependency_aware.csv"
    placement_path = ROOT / "results/model_level/gemma3_1b_placement_sensitivity.csv"
    write_csv(result_path, rows)
    write_csv(placement_path, placement_rows)
    manifest = {
        "schema_version": "varp.gemma3.dependency-experiment.v1",
        "projection_source": source.relative_to(ROOT).as_posix(),
        "projection_rows": len(projections),
        "result_rows": len(rows),
        "placements": list(PLACEMENTS),
        "schedulers": ["S1", "S2", "S3"],
        "decode_tokens": [1, 32],
        "remote_transfer_semantics": "prefetch-home-then-copy-to-thief",
        "outputs": [
            result_path.relative_to(ROOT).as_posix(),
            placement_path.relative_to(ROOT).as_posix(),
        ],
    }
    manifest_path = ROOT / "results/model_level/gemma3_1b_dependency_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
