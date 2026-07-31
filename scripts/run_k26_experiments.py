#!/usr/bin/env python3
"""Run the bounded paper-first K26 scheduler analytical model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from varp.k26_scheduler_model import (  # noqa: E402
    ModelConfig,
    generate_jobs,
    ledger_sha256,
    run_model,
)


PLAN_PATH = ROOT / "configs/experiments/k26_scheduler_paper.json"
SEED_PATH = ROOT / "configs/experiments/k26_seed_ledger.json"
OUTPUT_ROOT = ROOT / "results/experiments"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def path_for_manifest(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_cases(plan: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for subset in plan["paper_first_subsets"]:
        for workload in subset["workloads"]:
            for value in subset["values"]:
                case = {
                    "subset": subset["name"],
                    "workload": workload,
                    **subset["fixed"],
                    subset["vary"]: value,
                }
                cases.append(case)
    return cases


def run(output_root: Path, *, quick: bool = False) -> dict[str, Any]:
    plan = read_json(PLAN_PATH)
    seed_plan = read_json(SEED_PATH)
    seeds = seed_plan["seeds"][:1] if quick else seed_plan["seeds"]
    repetitions = (
        seed_plan["process_repetitions"][:1]
        if quick
        else seed_plan["process_repetitions"]
    )
    cases = build_cases(plan)
    output_root.mkdir(parents=True, exist_ok=True)

    # Canonical four-way logical affinity keeps every workload/seed ledger
    # identical while cluster/channel/bundle counts are varied by the model.
    ledgers: dict[tuple[str, int], list] = {}
    ledger_rows: list[dict[str, Any]] = []
    for workload in plan["workloads"]:
        for seed in seeds:
            jobs = generate_jobs(
                workload,
                plan["job_count"],
                seed,
                clusters=4,
                channels=4,
                bundles=4,
            )
            ledgers[(workload, seed)] = jobs
            ledger_rows.append(
                {
                    "workload": workload,
                    "seed": seed,
                    "jobs": len(jobs),
                    "ledger_sha256": ledger_sha256(jobs),
                }
            )

    results: list[dict[str, Any]] = []
    for case in cases:
        for seed in seeds:
            jobs = ledgers[(case["workload"], seed)]
            for repetition in repetitions:
                config = ModelConfig(
                    scheduler=case["scheduler"],
                    clusters=case["clusters"],
                    channels=case["channels"],
                    bundles=case["bundles"],
                    link_width_bits=case["link_width_bits"],
                )
                row = run_model(
                    jobs,
                    config,
                    seed=seed,
                    workload=case["workload"],
                    process_repetition=repetition,
                )
                row["subset"] = case["subset"]
                results.append(row)

    results_path = output_root / "scheduler_controlled.csv"
    fields = list(results[0].keys())
    with results_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)

    # Bound the unverified service-order assumption without expanding the main
    # factor matrix. The default model permits link and memory service to
    # overlap; this compact sensitivity serializes them as a conservative
    # analytical comparison on the two headline workloads.
    overlap_rows: list[dict[str, Any]] = []
    for workload in ("skew", "mixed"):
        for scheduler in ("S1", "S2", "S3"):
            for service_overlap_mode in ("full", "sequential"):
                for seed in seeds:
                    jobs = ledgers[(workload, seed)]
                    for repetition in repetitions:
                        row = run_model(
                            jobs,
                            ModelConfig(
                                scheduler=scheduler,
                                clusters=4,
                                channels=4,
                                bundles=4,
                                link_width_bits=128,
                                service_overlap_mode=service_overlap_mode,
                            ),
                            seed=seed,
                            workload=workload,
                            process_repetition=repetition,
                        )
                        row["subset"] = "service_overlap_sensitivity"
                        overlap_rows.append(row)
    overlap_path = output_root / "service_overlap_sensitivity.csv"
    with overlap_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(overlap_rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(overlap_rows)

    ledger_path = output_root / "seed_ledger.csv"
    with ledger_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("workload", "seed", "jobs", "ledger_sha256"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(ledger_rows)

    full_cartesian = (
        len(plan["workloads"])
        * len(plan["schedulers"])
        * len(plan["supported_factors"]["clusters"])
        * len(plan["supported_factors"]["channels"])
        * len(plan["supported_factors"]["bundles"])
        * len(plan["supported_factors"]["link_width_bits"])
        * len(seed_plan["seeds"])
        * len(seed_plan["process_repetitions"])
    )
    manifest = {
        "schema_version": "varp.k26.experiment-manifest.v1",
        "evidence_type": "analytical-model",
        "claim_boundary": plan["claim_boundary"],
        "plan_path": PLAN_PATH.relative_to(ROOT).as_posix(),
        "plan_sha256": sha256(PLAN_PATH),
        "seed_plan_path": SEED_PATH.relative_to(ROOT).as_posix(),
        "seed_plan_sha256": sha256(SEED_PATH),
        "quick": quick,
        "paper_first_factor_cases": len(cases),
        "process_rows": len(results),
        "full_cartesian_rows_not_run": full_cartesian,
        "all_correct": all(row["correctness"] for row in results),
        "any_timeout": any(row["timed_out"] for row in results),
        "results": {
            "path": path_for_manifest(results_path),
            "sha256": sha256(results_path),
        },
        "service_overlap_sensitivity": {
            "path": path_for_manifest(overlap_path),
            "sha256": sha256(overlap_path),
            "rows": len(overlap_rows),
            "modes": ["full", "sequential"],
            "claim_boundary": (
                "analytical bounding comparison; neither mode is a validated "
                "DMA/link/DDR protocol timing model"
            ),
        },
        "seed_ledger": {
            "path": path_for_manifest(ledger_path),
            "sha256": sha256(ledger_path),
            "rows": len(ledger_rows),
        },
    }
    manifest_path = output_root / "experiment_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_ROOT,
        help="output directory (default: results/experiments)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="one seed and one repetition for development only",
    )
    args = parser.parse_args()
    manifest = run(args.output, quick=args.quick)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
