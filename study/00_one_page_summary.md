# 한 장 요약

## 연구 질문

정적 큐 소유권으로 생기는 불균형에서, locality-aware Work Stealing이 원격 이동 비용을 통제하면서 p95/p99 tail latency를 줄일 수 있는가?

## 구조

K26 측에는 4개 compute cluster와 signed-INT8 16×4 MatVec 경로가 있다. 외부 Memory FPGA 후보에는 4-channel DDR3L command plane과 4-bundle link routing plane이 있다. 하지만 DDR response→link receive→payload store→MatVec의 닫힌 end-to-end 경로는 아직 없다.

## 핵심 결과

- graph-derived: Gemma 3 1B ONNX 7,837 nodes, token당 183 projections.
- RTL-simulated: 실제 weight tile 3/3 INT32 parity, synthetic steal→MatVec 3 accepted=3 completed.
- analytical: full-overlap에서 S3는 S1보다 skew p95 18.12%, mixed p95 17.59% 감소.
- analytical: S3는 S2보다 remote weight bytes를 skew 37.84%, mixed 22.16% 감소.
- capacity model: INT8 context-32K 2.4301 GiB는 명목 4 GB에도 들어간다.

## 결론

S3는 불균형 조건의 후보 정책이다. 외부 8 GiB의 채택 이유는 용량이 아니라 향후 측정할 로컬 대역폭·경합·전력에 달려 있다. 보드 성능·전력, 완전한 3B 실행, 제작 준비 상태는 주장하지 않는다.
