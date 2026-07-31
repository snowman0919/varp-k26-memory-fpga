#!/usr/bin/env python3
"""Validate the corrected v11 research freeze before paper/deck generation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/v11_research_freeze.md"
SUMMARY = ROOT / "research/v11_research_freeze.json"


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(actual: float, expected: float, tolerance: float = 0.02) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"expected {expected}, got {actual}")


def main() -> int:
    trace_manifest = json.loads(
        (ROOT / "experiments/gemma3_1b/trace_manifest.json").read_text()
    )
    graph = read_csv("experiments/gemma3_1b/graph_inventory.csv")
    projections = read_csv("experiments/gemma3_1b/projection_trace.csv")
    controlled = read_csv("results/experiments/scheduler_controlled.csv")
    paired = read_csv("results/experiments/paired_policy_effects.csv")
    dependency = read_csv("results/model_level/gemma3_1b_dependency_aware.csv")
    gemma_effects = read_csv("results/model_level/gemma3_1b_policy_effects.csv")
    local_external = read_csv(
        "results/model_level/k26_local_external_sensitivity.csv"
    )
    closed_loop = read_csv("evidence/model/gemma3_1b_closed_loop_trace.csv")
    events = read_csv("evidence/waveforms/work_stealing_events.csv")
    experiment_manifest = json.loads(
        (ROOT / "results/experiments/experiment_manifest.json").read_text()
    )
    dependency_manifest = json.loads(
        (ROOT / "results/model_level/gemma3_1b_dependency_manifest.json").read_text()
    )
    kicad = json.loads(
        (ROOT / "hardware/kicad/k26_reports/k26_scope_manifest.json").read_text()
    )

    assert REPORT.is_file()
    assert len(graph) == trace_manifest["graph_nodes"] == 7837
    assert len(projections) == trace_manifest["projection_nodes_per_token"] == 183
    assert trace_manifest["token_records"] == 32
    assert 183 * 32 == 5856

    assert len(controlled) == experiment_manifest["process_rows"] == 780
    assert all(
        row["correctness"] == "True" and row["timed_out"] == "False"
        for row in controlled
    )
    assert all(
        row["input_job_id_count"] == row["completed_job_id_count"]
        for row in controlled
    )
    assert all(row["duplicate_completion_count"] == "0" for row in controlled)
    result_path = ROOT / experiment_manifest["results"]["path"]
    assert sha256(result_path) == experiment_manifest["results"]["sha256"]

    # Paired fairness: every scheduler sees the same ledger for a workload/seed.
    ledger_groups: dict[tuple[str, str], set[str]] = {}
    for row in controlled:
        if row["subset"] != "scheduler":
            continue
        ledger_groups.setdefault((row["workload"], row["seed"]), set()).add(
            row["ledger_sha256"]
        )
    assert len(ledger_groups) == 25
    assert all(len(values) == 1 for values in ledger_groups.values())

    # Remote copies must be charged, not post-hoc counters.
    for row in controlled:
        charged = int(row["charged_link_bytes"])
        base = int(row["base_link_bytes"])
        extra = int(row["incremental_remote_link_bytes"])
        assert charged == base + extra
        if int(row["successful_steals"]) > 0 and int(row["remote_weight_bytes"]) > 0:
            assert extra > 0
            assert int(row["incremental_remote_link_service_cycles"]) > 0

    assert dependency_manifest["result_rows"] == len(dependency) == 16
    assert dependency_manifest["remote_transfer_semantics"] == (
        "prefetch-home-then-copy-to-thief"
    )
    assert {row["placement"] for row in dependency} == {
        "source_rule",
        "round_robin",
        "size_aware",
        "channel_affinity",
    }
    assert all(row["dependency_edge_count"] != "0" for row in dependency)
    assert all(row["correctness"] == "True" for row in dependency)
    assert all(row["serialized_token_model"] == "True" for row in dependency)

    def paired_effect(workload: str, comparison: str, metric: str) -> float:
        row = next(
            item
            for item in paired
            if item["workload"] == workload
            and item["comparison"] == comparison
            and item["metric"] == metric
        )
        assert row["paired_seed_count"] == "5"
        return float(row["median_effect_pct"])

    synthetic_p95 = paired_effect(
        "skew", "S3_vs_S1", "p95_tile_latency_cycles"
    )
    synthetic_p99 = paired_effect(
        "skew", "S3_vs_S1", "p99_tile_latency_cycles"
    )
    synthetic_remote = paired_effect(
        "skew", "S3_vs_S2", "remote_weight_bytes"
    )
    close(synthetic_p95, -19.13)
    close(synthetic_p99, -18.71)
    close(synthetic_remote, -35.49)

    def gemma_effect(placement: str, metric: str) -> float:
        row = next(
            item
            for item in gemma_effects
            if item["decode_tokens"] == "1" and item["placement"] == placement
        )
        return float(row[metric])

    source_completion = gemma_effect(
        "source_rule", "completion_effect_s3_vs_s1_pct"
    )
    source_p95 = gemma_effect(
        "source_rule", "tilejob_p95_effect_s3_vs_s1_pct"
    )
    affinity_p95 = gemma_effect(
        "channel_affinity", "tilejob_p95_effect_s3_vs_s1_pct"
    )
    close(source_completion, 4.80)
    close(source_p95, 0.28)
    close(affinity_p95, -19.79)

    assert len(closed_loop) == 3
    assert {row["projection_class"] for row in closed_loop} == {
        "gate_proj",
        "lm_head",
        "o_proj",
    }
    assert all(
        row["parity"] == "true"
        and row["expected_int32"] == row["observed_int32"]
        and int(row["fetch_accept_cycle"]) < int(row["dma_command_cycle"])
        < int(row["ddr_response_cycle"]) < int(row["matvec_result_cycle"])
        for row in closed_loop
    )
    last_event = events[-1]
    assert last_event["accepted"] == last_event["dispatched"] == "3"
    assert last_event["successful_steals"] == "3"

    local_mid = next(
        row
        for row in local_external
        if row["architecture"] == "k26_local_shared_ddr4"
        and row["placement"] == "size_aware"
        and row["modeled_aggregate_memory_gbps"] == "9.6"
    )
    external_mid = next(
        row
        for row in local_external
        if row["architecture"] == "external_4ch_ddr3l_candidate"
        and row["placement"] == "size_aware"
        and row["scheduler"] == "S1"
        and row["modeled_aggregate_memory_gbps"] == "6.4"
        and row["link_width_bits_per_bundle"] == "128"
    )
    assert int(local_mid["total_completion_cycles"]) < int(
        external_mid["total_completion_cycles"]
    )

    native = kicad["native_results"]
    assert kicad["status"] == "NOT FOR FABRICATION"
    assert native["coupon_footprints"] == 29
    assert native["routed_gth_and_refclock_nets"] == 20

    summary = {
        "schema_version": "varp.research-freeze.v11",
        "status": "PASS",
        "direct_rtl": {
            "closed_logical_path_tiles": len(closed_loop),
            "all_parity": True,
            "physical_gth_mig_closed": False,
        },
        "synthetic_paired_seed_median_pct": {
            "s3_vs_s1_tilejob_p95": round(synthetic_p95, 2),
            "s3_vs_s1_tilejob_p99": round(synthetic_p99, 2),
            "s3_vs_s2_remote_weight": round(synthetic_remote, 2),
        },
        "gemma_dependency_aware_pct": {
            "source_rule_s3_vs_s1_completion": round(source_completion, 2),
            "source_rule_s3_vs_s1_tilejob_p95": round(source_p95, 2),
            "channel_affinity_s3_vs_s1_tilejob_p95": round(affinity_p95, 2),
        },
        "design_decision": (
            "Gemma 1B keeps K26-local as the first baseline; external 8GB and "
            "work stealing remain conditional expansion mechanisms."
        ),
        "not_claimed": [
            "request-level tail latency",
            "functional full-model FPGA inference",
            "measured board performance or power",
            "closed physical GTH/MIG timing",
            "fabrication-ready PCB",
        ],
        "report": REPORT.relative_to(ROOT).as_posix(),
    }
    SUMMARY.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
