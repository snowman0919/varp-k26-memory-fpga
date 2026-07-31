# VARP K26–Memory FPGA — 10분 논문 발표 아웃라인

형식: 16:9 · 10장 · 한국어 · 10:00
발표 성격: 제품 설명회가 아닌 연구 논문의 기술 컨퍼런스 발표
연구 동결 선행조건: `research/final_research_freeze.json` = PASS

## 중심 연구 문장

정적 로컬 큐는 데이터 지역성을 유지하지만 작업이 치우치면 일부 연산 클러스터가 유휴 상태에 빠진다. 지역성 인식 Work Stealing은 이동 비용보다 이득이 큰 작업을 재배치해 Tail latency를 줄일 수 있으며, 본 연구는 그 효과가 발생하는 조건과 link/memory 비용을 실제 Gemma 3 1B 작업·분석 모델·제한 RTL·KiCad 근거로 추적한다.

## 논문 발표 서사

`연구 질문 → 시스템 모델 → workload·방법 → 공정한 비교 → 결과 → 비용·민감도 → 제한 구현 근거 → 기여·한계`

### Slide 1 — 정적 큐의 Tail을 줄이는 Work Stealing (0:35)

- 역할: 논문 제목과 연구 질문.
- 기억할 점: “언제 Tail 감소가 원격 이동 비용보다 큰가?”
- Visual: 장식적 K26–Memory FPGA 배경. 실제 회로·수치는 생성 이미지에 맡기지 않는다.

### Slide 2 — 연구 질문: 지역성과 부하 균형을 함께 얻을 수 있는가 (0:55)

- 역할: 문제와 연구 공백.
- 기억할 점: static ownership은 locality를 보존하지만 queue skew의 p95/p99를 보장하지 않는다.
- Visual: 과부하 queue·유휴 cluster·긴 tail을 하나의 시선 흐름으로 연결.
- 연구 공백: 실제 LLM graph, Tail percentile, remote byte를 같은 조건에서 감사.

### Slide 3 — 연구 대상 구조와 구현 경계 (1:10)

- 역할: 논문이 평가하는 시스템 모델.
- 기억할 점: 계산 소유권과 데이터 친화도를 TileJob에서 분리.
- Visual: 실제 RTL module map에 맞춘 K26 compute plane과 외부 Memory FPGA plane.
- 경계: scheduler→payload store→MatVec는 제한 구현, DDR response→link receive→weight FIFO 폐루프는 미통합.

### Slide 4 — 지역성 비용을 반영한 Work Stealing (1:15)

- 역할: 제안 방법.
- 기억할 점: `score = age − 이동 비용`, 양수인 eligible job만 이동.
- Visual: Manim `work_stealing_sequence.mp4/.gif`의 최종 프레임.
- 주의: 분석 모델은 all-eligible search, RTL은 victim-head 검사로 의미가 동일하지 않다.

### Slide 5 — 실제 Gemma graph에서 평가 작업을 만든다 (1:00)

- 역할: workload 구성과 외적 타당성.
- 기억할 점: 7,837 graph nodes → token당 183 projections → decode-32 5,856 TileJobs.
- Visual: graph inventory에서 deterministic ledger로 가는 한 방향 pipeline.
- 구분: 실제 Gemma replay와 synthetic stress는 별도 data layer.

### Slide 6 — 동일 조건에서 S1과 S3의 실행을 비교한다 (1:05)

- 역할: 공정한 평가 설계와 대표 실행 사건.
- 기억할 점: job stream·resource·seed를 고정하고 scheduler만 변경.
- Visual: 원본 CSV 기반 41k–43k 확대 timeline. queue wait, data preparation, compute, idle, stolen job을 구분.
- Motion: `scheduler_timeline.mp4/.gif`.

### Slide 7 — 실제 Gemma replay에서도 Tail이 감소했다 (1:20)

- 역할: 논문의 핵심 결과.
- 기억할 점: 실제 Gemma decode-32 p95 −15.07%, p99 −14.61%; 별도 skew p95 −18.12%.
- Visual: p95/p99 paired bars와 `tail_latency_results.mp4/.gif`.
- 금지: 실제 replay와 synthetic stress를 동일 실험으로 합치거나 보드 측정으로 표현.

### Slide 8 — Tail 감소의 비용은 원격 이동이다 (0:55)

- 역할: trade-off와 조건 민감도.
- 기억할 점: synthetic skew에서 S3 vs S2 remote weight −37.84%, completion +0.98%.
- Visual: queue Tail → remote movement → completion의 3단계와 `bottleneck_migration.mp4/.gif`.
- 주의: p95는 S3 vs S1, remote/completion은 S3 vs S2로 기준이 다르다.

### Slide 9 — 물리 참조 설계로 다음 검증 범위를 고정했다 (0:55)

- 역할: 제한된 물리 근거.
- 기억할 점: 알고리즘의 완성을 주장하는 제품 보드가 아니라 interface validation coupon.
- Visual: native KiCad render 60–70%와 링크·refclk·routed coupon 확대.
- Badge: 29 footprints, 20 routed GTH/refclk nets, 제한 범위 ERC/DRC 0/0.
- Qualifier: `NOT FOR FABRICATION`.

### Slide 10 — 기여와 한계: 조건부 효과를 규명했다 (0:50)

- 역할: 논문 기여·한계·다음 실험.
- 기여: graph-derived workload, Tail/traffic 공동 감사, 제한 RTL·물리 근거 연결.
- 한계: analytical timing, 모델/RTL scheduler semantics 불일치, 미통합 DDR→link→MatVec 폐루프.
- 다음 검증: 실제 K26 local-memory baseline과 닫힌 payload path에서 latency·traffic·power 측정.

## 시각자료 목록

- Manim: `tile_dataflow`, `work_stealing_sequence`, `scheduler_timeline`, `tail_latency_results`, `bottleneck_migration` 각 MP4/GIF/정지 프레임.
- CSV 기반 editable visuals: S1/S3 timeline, Gemma p95/p99 bars, bottleneck trade-off.
- Native physical evidence: KiCad 3D render와 실제 routed/refclk crop.
- 전체 motion preview: `presentation.mp4`, `presentation.gif`.
