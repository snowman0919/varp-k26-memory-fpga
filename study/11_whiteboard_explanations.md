# 화이트보드 설명

## 전체 가속기 — 90초

왼쪽에 K26의 네 compute cluster, 오른쪽에 4-channel Memory FPGA를 그린다. TileJob에는 계산 범위와 home/locality 정보가 있다. 현재 compute RTL은 scheduler에서 payload store와 MatVec까지 닫혀 있지만 DDR response와 link receive는 닫히지 않았다. 따라서 결과는 정책 분석과 제한된 RTL 증거이며 보드 가속 성능이 아니다.

## Work Stealing — 60초

두 local queue를 그린다. 한쪽이 비고 다른 쪽이 길면 idle cluster가 victim을 찾는다. S2는 가장 오래된 eligible job, S3는 age에서 locality penalty를 뺀 score가 좋은 job을 고른다. tail은 줄 수 있지만 remote bytes와 마지막 completion이 나빠질 수 있다.

## 메모리 계층 — 60초

모델 weight, activation, KV cache를 분리한다. Channel은 독립 대역폭, bank는 내부 병렬성, row hit는 activation 비용 감소와 관계가 있다. Capacity fit과 bandwidth adequacy는 다른 질문이다.

## p95가 중요한 이유 — 45초

평균이 같아도 일부 요청이 매우 느리면 대화형 체감이 나쁘다. p95는 100개 중 느린 5개가 시작되는 경계다. 단 p95만 최적화하면 completion이나 traffic이 악화될 수 있어 함께 본다.

## 왜 완성 가속기가 아닌가 — 45초

compute, command, routing plane은 있지만 실제 weight가 DDR에서 응답되어 link를 건너 MatVec payload store에 들어오는 폐루프가 없다. 이 경계를 공개하는 것이 연구 신뢰성의 일부다.

## 다음 하드웨어 검증 — 60초

DMA request와 DDR response를 연결하고 credit/CDC가 있는 link receive를 만든다. returned weight를 FIFO/payload store에 넣어 exact-once MatVec completion을 확인한다. 그 뒤 local DDR4 baseline과 동일 workload로 bandwidth, p95, board power를 계측한다.
