# 최종 연구 동결 기록

상태: **PASS**
목적: 발표자료 생성 전에 논문·연구 데이터·RTL·구조 설계의 근거를 고정한다. 이 게이트는 새 실험을 추가하지 않는다.

## 연구 질문과 결론

정적 로컬 큐는 데이터 지역성을 유지하지만 작업이 치우치면 일부 연산 클러스터가 유휴 상태에 빠진다. 지역성 인식 Work Stealing은 이동 비용보다 이득이 큰 작업을 재배치해 Tail latency를 줄일 수 있으며, 그 효과는 큐 치우침과 link/memory service 가정에 조건부다.

## 동결된 핵심 근거

- 실제 Gemma 3 1B graph: **7,837 nodes**, token당 **183 projections**, decode-32 **5,856 TileJobs**.
- 실제 weight 기반 제한 RTL parity: **3/3 일치**.
- 계측 RTL: **3 accepted = 3 dispatched = 3 completed**, steal 3회가 실제 MatVec 결과까지 identity를 보존.
- 제어 실험: **780 rows**, 5 seeds, 모든 row exact-once·timeout 없음.
- 실제 Gemma decode-32 analytical replay: S3 vs S1 p95 **-15.07%**, p99 **-14.61%**.
- 별도 synthetic skew: S3 vs S1 p95 **-18.12%**, p99 **-18.16%**.
- 같은 synthetic skew에서 S3 vs S2: remote weight **-37.84%**, completion **+0.98%**.
- Native KiCad reference coupon: **29 footprints**, **20 routed GTH/refclk nets**, 제한 범위 ERC/DRC **0/0**.

## 발표에서 구분할 세 층

1. **직접·제한 구현 근거:** graph inventory, actual-weight tile parity, steal→MatVec identity, native KiCad 검사.
2. **분석 모델 결과:** p95/p99, completion, remote traffic, overlap sensitivity.
3. **미검증:** 실제 보드 성능·전력, DDR response→link receive→weight FIFO→MatVec 폐루프, 제작 준비 상태.

## 발표 생성 허용 조건

PPT는 이 문서와 `research/final_research_freeze.json`가 PASS일 때만 생성한다. 실제 Gemma replay와 synthetic stress를 같은 실험처럼 합치지 않으며, 분석 cycle을 RTL 또는 보드 cycle로 표현하지 않는다.
