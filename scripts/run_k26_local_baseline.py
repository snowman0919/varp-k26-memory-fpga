#!/usr/bin/env python3
"""Compare K26-local and external-memory analytical service sensitivities."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from varp.gemma_dependency_model import make_dependency_aware_tile_jobs  # noqa: E402
from varp.k26_scheduler_model import ModelConfig, run_model  # noqa: E402


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run() -> dict[str, Any]:
    projections = read_rows(
        ROOT / "experiments/gemma3_1b/projection_trace.csv"
    )
    rows: list[dict[str, Any]] = []
    model_clock_hz = 200_000_000

    for placement in ("source_rule", "size_aware"):
        jobs, summary = make_dependency_aware_tile_jobs(
            projections,
            decode_tokens=1,
            placement=placement,
            n_tile=1024,
        )
        cases: list[dict[str, Any]] = []
        local_points = (
            (24, 48, 72) if placement == "size_aware" else (48,)
        )
        for local_bytes in local_points:
            for scheduler in ("S1",):
                cases.append(
                    {
                        "architecture": "k26_local_shared_ddr4",
                        "scheduler": scheduler,
                        "channels": 1,
                        "bundles": 1,
                        "channel_bytes_per_cycle": local_bytes,
                        "link_width_bits": 128,
                        "external_link_enabled": False,
                    }
                )
        external_memory_points = (
            (4, 8, 16) if placement == "size_aware" else (8,)
        )
        for external_channel_bytes in external_memory_points:
            link_points = (
                (64, 128, 256)
                if placement == "size_aware" and external_channel_bytes == 8
                else (128,)
            )
            for link_width in link_points:
                for scheduler in ("S1", "S3"):
                    cases.append(
                        {
                            "architecture": "external_4ch_ddr3l_candidate",
                            "scheduler": scheduler,
                            "channels": 4,
                            "bundles": 4,
                            "channel_bytes_per_cycle": external_channel_bytes,
                            "link_width_bits": link_width,
                            "external_link_enabled": True,
                        }
                    )

        for case in cases:
            result = run_model(
                jobs,
                ModelConfig(
                    scheduler=case["scheduler"],
                    clusters=4,
                    channels=case["channels"],
                    bundles=case["bundles"],
                    channel_bytes_per_cycle=case[
                        "channel_bytes_per_cycle"
                    ],
                    link_width_bits=case["link_width_bits"],
                    external_link_enabled=case["external_link_enabled"],
                    queue_capacity=4096,
                    deadlock_no_progress_cycles=100_000_000_000,
                ),
                seed=0,
                workload="gemma3_1b_k26_local_external_sensitivity",
            )
            rows.append(
                {
                    "architecture": case["architecture"],
                    "placement": placement,
                    "scheduler": case["scheduler"],
                    "tile_jobs": len(jobs),
                    "cluster_tile_counts": "|".join(
                        str(value) for value in summary.cluster_tile_counts
                    ),
                    "channels": case["channels"],
                    "channel_bytes_per_cycle_each": case[
                        "channel_bytes_per_cycle"
                    ],
                    "modeled_aggregate_memory_gbps": (
                        case["channels"]
                        * case["channel_bytes_per_cycle"]
                        * model_clock_hz
                        / 1e9
                    ),
                    "external_link_enabled": case["external_link_enabled"],
                    "link_width_bits_per_bundle": case["link_width_bits"],
                    "total_completion_cycles": result[
                        "total_completion_cycles"
                    ],
                    "tilejob_p95_cycles": result[
                        "p95_tile_latency_cycles"
                    ],
                    "tilejob_p99_cycles": result[
                        "p99_tile_latency_cycles"
                    ],
                    "queue_wait_mean_cycles": result[
                        "queue_wait_mean_cycles"
                    ],
                    "base_link_service_cycles": result[
                        "base_link_service_cycles"
                    ],
                    "incremental_remote_link_service_cycles": result[
                        "incremental_remote_link_service_cycles"
                    ],
                    "remote_weight_bytes": result["remote_weight_bytes"],
                    "evidence_type": "analytical-sensitivity",
                    "claim_boundary": (
                        "K26 local bandwidth points are effective-bandwidth "
                        "sensitivities, not measurements. External points use "
                        "logical channel/link service and do not include MIG/GTH "
                        "timing, board power, or price."
                    ),
                }
            )

    output = ROOT / "results/model_level/k26_local_external_sensitivity.csv"
    write_csv(output, rows)
    manifest = {
        "schema_version": "varp.k26.local-external-sensitivity.v1",
        "rows": len(rows),
        "placements": ["source_rule", "size_aware"],
        "local_effective_memory_gbps": [4.8, 9.6, 14.4],
        "external_aggregate_memory_gbps": [3.2, 6.4, 12.8],
        "external_link_width_bits_per_bundle": [64, 128, 256],
        "capacity_fact": (
            "Gemma 3 1B modeled INT8 context-32K budget fits nominal K26 4GB; "
            "external 8GB is an expansion/isolation candidate, not a capacity "
            "requirement for this workload."
        ),
        "output": output.relative_to(ROOT).as_posix(),
    }
    manifest_path = ROOT / "results/model_level/k26_local_external_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
