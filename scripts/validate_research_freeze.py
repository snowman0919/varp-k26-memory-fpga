#!/usr/bin/env python3
"""Cross-check the frozen research evidence before presentation generation.

This gate deliberately does not create new experiments.  It verifies that the
paper-facing claims can be reconstructed from the committed graph inventory,
analytical scheduler rows, bounded RTL evidence, and native KiCad manifest.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research" / "final_research_freeze.md"
SUMMARY = ROOT / "research" / "final_research_freeze.json"


def read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pct_change(new: float, old: float) -> float:
    return (new / old - 1.0) * 100.0


def close(actual: float, expected: float, tolerance: float = 0.01) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"expected {expected}, got {actual}")


def main() -> int:
    trace_manifest = json.loads((ROOT / "experiments/gemma3_1b/trace_manifest.json").read_text())
    graph = read_csv("experiments/gemma3_1b/graph_inventory.csv")
    projections = read_csv("experiments/gemma3_1b/projection_trace.csv")
    gemma = read_csv("experiments/gemma3_1b/scheduler_replay.csv")
    controlled = read_csv("results/experiments/scheduler_controlled.csv")
    parity = read_csv("evidence/model/gemma3_1b_rtl_tile_parity.csv")
    events = read_csv("evidence/waveforms/work_stealing_events.csv")
    experiment_manifest = json.loads((ROOT / "results/experiments/experiment_manifest.json").read_text())
    kicad = json.loads((ROOT / "hardware/kicad/k26_reports/k26_scope_manifest.json").read_text())

    assert len(graph) == trace_manifest["graph_nodes"] == 7837
    assert len(projections) == trace_manifest["projection_nodes_per_token"] == 183
    assert trace_manifest["token_records"] == 32
    assert 183 * 32 == 5856
    assert len(gemma) == trace_manifest["scheduler_replays"] == 12
    assert all(row["correctness"] == "True" and row["timed_out"] == "False" for row in gemma)

    assert len(controlled) == experiment_manifest["process_rows"] == 780
    assert all(row["correctness"] == "True" and row["timed_out"] == "False" for row in controlled)
    assert all(row["input_job_id_count"] == row["completed_job_id_count"] for row in controlled)
    assert all(row["duplicate_completion_count"] == "0" for row in controlled)
    result_path = ROOT / experiment_manifest["results"]["path"]
    assert sha256(result_path) == experiment_manifest["results"]["sha256"]

    assert len(parity) == 3
    assert all(row["parity"] == "true" and row["expected_int32"] == row["observed_int32"] for row in parity)
    last_event = events[-1]
    assert last_event["accepted"] == last_event["dispatched"] == "3"
    assert last_event["successful_steals"] == "3"
    assert sum(row["steal_event"] == "true" for row in events) == 3

    native = kicad["native_results"]
    assert kicad["status"] == "NOT FOR FABRICATION"
    assert native["coupon_erc_errors"] == native["reference_erc_errors"] == 0
    assert native["coupon_drc_violations"] == native["schematic_parity_issues"] == 0
    assert native["coupon_footprints"] == 29
    assert native["routed_gth_and_refclock_nets"] == 20

    def controlled_value(workload: str, policy: str, field: str) -> float:
        rows = [
            row for row in controlled
            if row["subset"] == "scheduler"
            and row["workload"] == workload
            and row["scheduler"] == policy
            and row["process_repetition"] == "0"
            and row["service_overlap_mode"] == "full"
        ]
        assert len(rows) == 5
        return median(float(row[field]) for row in rows)

    skew_s1_p95 = controlled_value("skew", "S1", "p95_tile_latency_cycles")
    skew_s3_p95 = controlled_value("skew", "S3", "p95_tile_latency_cycles")
    skew_s1_p99 = controlled_value("skew", "S1", "p99_tile_latency_cycles")
    skew_s3_p99 = controlled_value("skew", "S3", "p99_tile_latency_cycles")
    skew_s2_remote = controlled_value("skew", "S2", "remote_weight_bytes")
    skew_s3_remote = controlled_value("skew", "S3", "remote_weight_bytes")
    skew_s2_completion = controlled_value("skew", "S2", "total_completion_cycles")
    skew_s3_completion = controlled_value("skew", "S3", "total_completion_cycles")

    synthetic_p95 = pct_change(skew_s3_p95, skew_s1_p95)
    synthetic_p99 = pct_change(skew_s3_p99, skew_s1_p99)
    remote_change = pct_change(skew_s3_remote, skew_s2_remote)
    completion_change = pct_change(skew_s3_completion, skew_s2_completion)
    close(synthetic_p95, -18.12, 0.01)
    close(synthetic_p99, -18.16, 0.01)
    close(remote_change, -37.84, 0.01)
    close(completion_change, 0.98, 0.01)

    def gemma_value(tokens: int, policy: str, field: str) -> float:
        row = next(row for row in gemma if int(row["decode_tokens"]) == tokens and row["scheduler"] == policy)
        return float(row[field])

    gemma_p95 = pct_change(
        gemma_value(32, "S3", "p95_tile_latency_cycles"),
        gemma_value(32, "S1", "p95_tile_latency_cycles"),
    )
    gemma_p99 = pct_change(
        gemma_value(32, "S3", "p99_tile_latency_cycles"),
        gemma_value(32, "S1", "p99_tile_latency_cycles"),
    )
    close(gemma_p95, -15.07, 0.01)
    close(gemma_p99, -14.61, 0.01)

    summary = {
        "status": "PASS",
        "purpose": "presentation prerequisite; no new experiment added",
        "graph_nodes": len(graph),
        "projections_per_token": len(projections),
        "decode_32_tile_jobs": len(projections) * 32,
        "controlled_rows": len(controlled),
        "controlled_seeds": [19, 23, 29, 31, 43],
        "bounded_rtl_parity": "3/3",
        "bounded_steal_to_matvec": "3 accepted = 3 dispatched = 3 completed",
        "gemma_decode_32": {"s3_vs_s1_p95_pct": round(gemma_p95, 2), "s3_vs_s1_p99_pct": round(gemma_p99, 2)},
        "synthetic_skew": {
            "s3_vs_s1_p95_pct": round(synthetic_p95, 2),
            "s3_vs_s1_p99_pct": round(synthetic_p99, 2),
            "s3_vs_s2_remote_weight_pct": round(remote_change, 2),
            "s3_vs_s2_completion_pct": round(completion_change, 2),
        },
        "kicad": {
            "status": kicad["status"],
            "footprints": native["coupon_footprints"],
            "routed_gth_refclk_nets": native["routed_gth_and_refclock_nets"],
            "bounded_erc_drc": "0/0",
        },
        "presentation_claim_boundary": {
            "direct_or_bounded": ["actual graph inventory", "three actual-weight RTL parity tiles", "three steal-to-MatVec events", "native KiCad coupon checks"],
            "modeled": ["S0-S3 latency", "remote traffic", "completion and energy/cost sensitivity"],
            "not_claimed": ["measured board performance", "closed DDR-link-MatVec payload loop", "fabrication readiness", "full-model RTL inference"],
        },
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        f"""# 최종 연구 동결 기록

상태: **PASS**
목적: 발표자료 생성 전에 논문·연구 데이터·RTL·구조 설계의 근거를 고정한다. 이 게이트는 새 실험을 추가하지 않는다.

## 연구 질문과 결론

정적 로컬 큐는 데이터 지역성을 유지하지만 작업이 치우치면 일부 연산 클러스터가 유휴 상태에 빠진다. 지역성 인식 Work Stealing은 이동 비용보다 이득이 큰 작업을 재배치해 Tail latency를 줄일 수 있으며, 그 효과는 큐 치우침과 link/memory service 가정에 조건부다.

## 동결된 핵심 근거

- 실제 Gemma 3 1B graph: **7,837 nodes**, token당 **183 projections**, decode-32 **5,856 TileJobs**.
- 실제 weight 기반 제한 RTL parity: **3/3 일치**.
- 계측 RTL: **3 accepted = 3 dispatched = 3 completed**, steal 3회가 실제 MatVec 결과까지 identity를 보존.
- 제어 실험: **780 rows**, 5 seeds, 모든 row exact-once·timeout 없음.
- 실제 Gemma decode-32 analytical replay: S3 vs S1 p95 **{gemma_p95:.2f}%**, p99 **{gemma_p99:.2f}%**.
- 별도 synthetic skew: S3 vs S1 p95 **{synthetic_p95:.2f}%**, p99 **{synthetic_p99:.2f}%**.
- 같은 synthetic skew에서 S3 vs S2: remote weight **{remote_change:.2f}%**, completion **+{completion_change:.2f}%**.
- Native KiCad reference coupon: **29 footprints**, **20 routed GTH/refclk nets**, 제한 범위 ERC/DRC **0/0**.

## 발표에서 구분할 세 층

1. **직접·제한 구현 근거:** graph inventory, actual-weight tile parity, steal→MatVec identity, native KiCad 검사.
2. **분석 모델 결과:** p95/p99, completion, remote traffic, overlap sensitivity.
3. **미검증:** 실제 보드 성능·전력, DDR response→link receive→weight FIFO→MatVec 폐루프, 제작 준비 상태.

## 발표 생성 허용 조건

PPT는 이 문서와 `{SUMMARY.relative_to(ROOT)}`가 PASS일 때만 생성한다. 실제 Gemma replay와 synthetic stress를 같은 실험처럼 합치지 않으며, 분석 cycle을 RTL 또는 보드 cycle로 표현하지 않는다.
""",
        encoding="utf-8",
    )
    print(f"research_freeze=PASS report={REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
