# VARP K26–Memory FPGA — 10분 발표 아웃라인

상태: 아웃라인·스타일·백엔드 승인, 대표 슬라이드 샘플 승인 대기
형식: 16:9, 12장, 한국어 중심, minimal / clean / technical
대상: 연구 심사자와 기술 질의응답 청중

## Slide 1 — 왜 외부 Memory FPGA인가?

- 질문: 온디바이스 LLM의 tail latency를 locality-aware scheduling으로 줄일 수 있는가?
- K26 compute + external memory FPGA 연구 artifact
- 결과는 명시하지 않은 한 analytical/model/hybrid
- 역할: 표지 / 연구 질문

## Slide 2 — “메모리가 병목”이라는 말만으로는 부족하다

- 병목 진술에서 실행 가능한 queue·locality 정책으로 이동
- 평균이 아니라 p95/p99 tail을 대상으로 함
- 구현·모델·미검증 경계를 처음부터 분리
- 역할: 문제 정의

## Slide 3 — 최종 시스템 구조

- K26 compute plane, memory FPGA command plane, link routing plane
- 4-channel DDR3L capacity 후보와 4-lane link 후보
- 세 plane은 각각 검증됐지만 end-to-end payload loop는 닫히지 않음
- 역할: architecture
- Required images:
  - 실제 RTL/분석 경계 구조도; strict input asset; 라벨·화살표·증거 경계를 보존

    ![Architecture boundary](../../paper/final/figures/paper_f01_evidence_path.svg)

## Slide 4 — TileJob 데이터 경로와 증거 경계

- ONNX graph 7,837 nodes → token당 183 projections
- TileJob identity, queue, payload, MatVec 결과의 검증 범위
- ORT 기능 참조와 RTL/DRAMsim3/보드 timing을 결합하지 않음
- 역할: dataflow / evidence boundary
- Required images:
  - ONNX graph-to-scheduler 경계도; strict input asset; 숫자와 범례를 보존

    ![ONNX evidence flow](../../paper/final/figures/paper_f02_onnx_runtime_graph.svg)

## Slide 5 — 왜 Single FIFO가 충분하지 않은가?

- 전역 FIFO는 비교 기준이지만 physical arbitration 비용이 존재
- static local FCFS는 locality를 지키지만 skew에서 idle cluster 발생
- 성능·locality·구현비용의 trade-off
- 역할: comparison
- Required images:
  - 정책·증거 경계 그림; strict input asset

    ![Policy boundary](../../paper/final/figures/paper_f03_policy_boundary.svg)

## Slide 6 — Multi-Queue FCFS와 Work Stealing

- queue imbalance → idle cluster → victim scan
- oldest eligible + locality score → steal
- identity-preserving completion과 exact-once
- 역할: sequence / storyboard
- Required images:
  - Manim `work_stealing_sequence` 승인 프레임; strict input asset; 샘플 승인 후 생성

## Slide 7 — Gemma 3 1B 평가 방법

- 실제 graph inventory와 representative INT8 tile parity
- decode-32 projection ledger + analytical scheduler sweep
- hybrid estimate와 host functional reference는 별도 증거
- 역할: method / trace

## Slide 8 — 핵심 결과: tail latency와 remote traffic

- S3 vs S1 p95: skew −18.12%, mixed −17.59%
- p99·utilization·remote bytes를 함께 읽어야 함
- 결과는 analytical scheduler model, 보드 측정 아님
- 역할: data evidence
- Required images:
  - p95/p99 결과 패널; strict input asset; 수치·축·범례 변경 금지

    ![Tail latency](../../paper/final/figures/paper_f05_tail_latency.svg)

## Slide 9 — 에너지와 비용은 “추정치”다

- estimated dynamic energy/token, refresh·idle·PHY·board power 제외
- memory-die-cost normalized metric, 전체 시스템 가격 아님
- capacity sensitivity와 speed claim을 분리
- 역할: analytical estimate
- Required images:
  - trade-off 그림; strict input asset; qualifier와 수치 보존

    ![Energy cost tradeoff](../../paper/final/figures/paper_f06_tradeoff.svg)

## Slide 10 — KiCad 참조 설계와 validation coupon

- 실제 native KiCad source render와 bounded ERC/DRC
- 55 unrouted nets 등 fabrication blocker
- NOT FOR FABRICATION
- 역할: physical evidence
- Required images:
  - 실제 KiCad 3D render; strict input asset; 보드 형상·실크·텍스트 보존

    ![KiCad coupon](../../paper/final/figures/paper_f07_kicad_coupon_render.png)

## Slide 11 — 무엇을 증명했고, 무엇을 주장하지 않는가

- proven: bounded RTL, graph inventory, tile parity, native proposal checks
- modeled: scheduler, hybrid latency, energy/cost/capacity sensitivity
- not claimed: board measurement, payload bandwidth, full 3B execution, fabrication readiness
- 역할: evidence boundary / not claimed

## Slide 12 — 기여와 다음 검증 단계

- 기여: evidence-bounded locality-aware scheduling artifact
- 다음 단계: DDR/link response → weight FIFO → MatVec loop closure
- scheduler semantics 통일과 physical calibration
- Q&A 진입 질문: “어느 경계부터 실제 하드웨어인가?”
- 역할: summary / Q&A

## Source-asset mapping summary

| Slide | Strict input asset |
|---:|---|
| 3 | `paper_f01_evidence_path.svg` |
| 4 | `paper_f02_onnx_runtime_graph.svg` |
| 5 | `paper_f03_policy_boundary.svg` |
| 6 | Manim work-stealing approved frame |
| 8 | `paper_f05_tail_latency.svg` |
| 9 | `paper_f06_tradeoff.svg` |
| 10 | `paper_f07_kicad_coupon_render.png` |
