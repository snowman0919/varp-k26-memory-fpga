#!/usr/bin/env python3
"""Build paired v11 research summaries from corrected analytical results."""

from __future__ import annotations

import csv
from pathlib import Path
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def pct(value: float, baseline: float) -> float:
    return (value / baseline - 1.0) * 100.0


def synthetic_paired_rows() -> list[dict[str, Any]]:
    source = read_csv(ROOT / "results/experiments/scheduler_controlled.csv")
    rows = [
        row
        for row in source
        if row["subset"] == "scheduler" and row["process_repetition"] == "0"
    ]
    output: list[dict[str, Any]] = []
    metrics = (
        "total_completion_cycles",
        "p95_tile_latency_cycles",
        "p99_tile_latency_cycles",
        "remote_weight_bytes",
        "incremental_remote_link_bytes",
    )
    for workload in sorted({row["workload"] for row in rows}):
        group = [row for row in rows if row["workload"] == workload]
        seeds = sorted({row["seed"] for row in group}, key=int)
        by_key = {(row["scheduler"], row["seed"]): row for row in group}
        for baseline in ("S1", "S2"):
            for metric in metrics:
                effects = []
                for seed in seeds:
                    base = float(by_key[(baseline, seed)][metric])
                    if base == 0:
                        continue
                    effects.append(
                        pct(float(by_key[("S3", seed)][metric]), base)
                    )
                if effects:
                    output.append(
                        {
                            "workload": workload,
                            "comparison": f"S3_vs_{baseline}",
                            "metric": metric,
                            "paired_seed_count": len(effects),
                            "median_effect_pct": f"{statistics.median(effects):.6f}",
                            "min_effect_pct": f"{min(effects):.6f}",
                            "max_effect_pct": f"{max(effects):.6f}",
                            "evidence_type": "paired-seed-analytical-model-v2",
                            "claim_boundary": (
                                "Synthetic workload; incremental stolen payload is "
                                "charged to logical link service. Not hardware timing."
                            ),
                        }
                    )
    return output


def gemma_policy_rows() -> list[dict[str, Any]]:
    source = read_csv(ROOT / "results/model_level/gemma3_1b_dependency_aware.csv")
    output: list[dict[str, Any]] = []
    for decode_tokens in (1, 32):
        placements = sorted(
            {
                row["placement"]
                for row in source
                if int(row["decode_tokens"]) == decode_tokens
            }
        )
        for placement in placements:
            group = [
                row
                for row in source
                if int(row["decode_tokens"]) == decode_tokens
                and row["placement"] == placement
            ]
            s1 = next(row for row in group if row["scheduler"] == "S1")
            s3 = next(row for row in group if row["scheduler"] == "S3")
            output.append(
                {
                    "decode_tokens": decode_tokens,
                    "placement": placement,
                    "tile_jobs": s3["jobs"],
                    "completion_effect_s3_vs_s1_pct": f"{pct(float(s3['total_completion_cycles']), float(s1['total_completion_cycles'])):.6f}",
                    "tilejob_p95_effect_s3_vs_s1_pct": f"{pct(float(s3['p95_tile_latency_cycles']), float(s1['p95_tile_latency_cycles'])):.6f}",
                    "tilejob_p99_effect_s3_vs_s1_pct": f"{pct(float(s3['p99_tile_latency_cycles']), float(s1['p99_tile_latency_cycles'])):.6f}",
                    "incremental_remote_link_bytes": s3[
                        "incremental_remote_link_bytes"
                    ],
                    "successful_steals": s3["successful_steals"],
                    "evidence_type": "dependency-aware-analytical-model-v2",
                    "claim_boundary": (
                        "ONNX-derived shapes, modeled placement, conservative stage "
                        "barriers, and serialized token repetition. TileJob percentiles "
                        "are not request-level tail latency."
                    ),
                }
            )
    return output


def find_effect(
    rows: list[dict[str, Any]],
    workload: str,
    comparison: str,
    metric: str,
) -> float:
    row = next(
        item
        for item in rows
        if item["workload"] == workload
        and item["comparison"] == comparison
        and item["metric"] == metric
    )
    return float(row["median_effect_pct"])


def main() -> None:
    synthetic = synthetic_paired_rows()
    gemma = gemma_policy_rows()
    write_csv(ROOT / "results/experiments/paired_policy_effects.csv", synthetic)
    write_csv(ROOT / "results/model_level/gemma3_1b_policy_effects.csv", gemma)

    skew_p95 = find_effect(
        synthetic, "skew", "S3_vs_S1", "p95_tile_latency_cycles"
    )
    skew_p99 = find_effect(
        synthetic, "skew", "S3_vs_S1", "p99_tile_latency_cycles"
    )
    skew_remote = find_effect(
        synthetic, "skew", "S3_vs_S2", "remote_weight_bytes"
    )
    source = next(
        row
        for row in gemma
        if row["decode_tokens"] == 1 and row["placement"] == "source_rule"
    )
    affinity = next(
        row
        for row in gemma
        if row["decode_tokens"] == 1
        and row["placement"] == "channel_affinity"
    )
    size_aware = next(
        row
        for row in gemma
        if row["decode_tokens"] == 1 and row["placement"] == "size_aware"
    )

    freeze = f"""# v11 연구 결과 동결

## 연구 질문

K26 연산부와 외부 Memory FPGA의 가중치 공급부를 분리하는 후보 구조에서,
초기 작업 배치의 불균형이 데이터 이동 비용보다 클 때만 지역성 인식 작업
재분배가 이득을 주는가를 평가한다.

## 직접 RTL 증거

- 실제 Gemma 3 1B에서 제한적으로 추출한 `gate_proj`, `lm_head`, `o_proj`
  16×4 INT8 타일 세 개가 작업 수락→DMA 명령→DDR 응답 경계→논리 링크 FIFO
  →MatVec 결과 경로를 통과했다.
- 세 결과는 software INT32 기준과 일치했고 job ID가 보존됐다.
- 이 경로는 논리 RTL 가상 시제품이다. GTH serializer, CDC, MIG, 실제 DDR
  timing과 보드 계측은 포함하지 않는다.

## 수정된 분석 모델

- 훔친 작업은 home prefetch 뒤 thief로 복사되는 weight·activation·부분합 byte와
  cycle을 링크 서비스에 추가한다.
- 실제 모델 형상은 projection 하나가 아니라 full-K, N≤1024 출력 타일로 나눈다.
- `q/k/v→o→gate/up→down→다음 layer` 장벽을 적용한다.
- 32-token 조건은 token 간 중첩 없이 동일한 dependency-aware token을 직렬 반복한다.
- 초기 배치는 원래 산술 규칙, round-robin, size-aware, channel-affinity를 비교한다.

## 핵심 결과

### 합성 불균형 부하, 5개 paired seed 중앙값

- S3 vs S1 TileJob p95: **{skew_p95:.2f}%**
- S3 vs S1 TileJob p99: **{skew_p99:.2f}%**
- S3 vs S2 비지역 가중치 이동량: **{skew_remote:.2f}%**

이 결과는 불균형이 명시적으로 주어진 합성 부하의 조건 분석이다.

### Gemma 형상 + 의존성 + 모델 배치

- 기존 source-rule 배치: S3 vs S1 완료시간
  **{float(source['completion_effect_s3_vs_s1_pct']):+.2f}%**,
  TileJob p95 **{float(source['tilejob_p95_effect_s3_vs_s1_pct']):+.2f}%**.
- size-aware 배치: 완료시간
  **{float(size_aware['completion_effect_s3_vs_s1_pct']):+.2f}%**,
  TileJob p95 **{float(size_aware['tilejob_p95_effect_s3_vs_s1_pct']):+.2f}%**.
- channel-affinity 배치: 완료시간
  **{float(affinity['completion_effect_s3_vs_s1_pct']):+.2f}%**,
  TileJob p95 **{float(affinity['tilejob_p95_effect_s3_vs_s1_pct']):+.2f}%**.

따라서 실제 모델 형상만으로 작업 재분배의 이득을 일반화할 수 없다. 초기 배치가
이미 균형이면 꼬리 지연 이득이 없고, 원격 복사 비용 때문에 완료시간이 악화될 수
있다. 채널 친화 배치처럼 남은 불균형이 큰 경우에만 유의미한 개선이 나타났다.

## K26-local 대 외부 메모리 후보

- Gemma 3 1B의 모델링된 INT8, context-32K 용량은 nominal K26 4GB 안에 들어간다.
- 분석 민감도에서 K26-local 유효 9.6 GB/s 기준선은 외부 4채널 DDR3L
  6.4 GB/s 후보보다 짧았다.
- 외부 8GB는 Gemma 1B의 필수 용량이나 성능 우위가 아니라, 3B·긴 문맥·가중치
  공급 격리를 위한 확장 후보로만 남는다.

## 최종 설계 결정

1. Work Stealing을 상시 정책으로 채택하지 않는다.
2. 초기 배치의 queue skew와 예상 원격 복사 비용을 비교해 선택적으로 켠다.
3. Gemma 1B에는 K26-local 기준선이 우선이며, 외부 Memory FPGA 채택은 더 큰
   모델 또는 실제 local contention 측정 뒤에 결정한다.
4. KiCad 쿠폰은 전체 보드가 아니라 링크·대표 DDR 배선의 공간 검토 자료다.

## 금지 해석

- request-level tail latency를 측정했다.
- 실제 Gemma 전체 추론을 FPGA에서 실행했다.
- 외부 메모리가 Gemma 1B에서 더 빠르거나 반드시 필요하다.
- 저비용·저전력을 실물로 달성했다.
- GTH/MIG timing이 닫혔거나 PCB가 제작 가능하다.
"""
    path = ROOT / "research/v11_research_freeze.md"
    path.write_text(freeze, encoding="utf-8")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
