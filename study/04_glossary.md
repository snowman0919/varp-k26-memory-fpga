# 용어집

| 용어 | 뜻 |
|---|---|
| Prefill | 입력 문맥 전체를 병렬적으로 처리해 KV cache를 만드는 단계 |
| Decode | 이전 KV를 재사용하며 다음 토큰을 한 개씩 생성하는 단계 |
| Projection | attention/MLP의 선형변환; decode에서 가중치 재읽기 비중이 큼 |
| MatVec | 행렬과 벡터의 곱; 이 artifact는 signed INT8 16×4 primitive를 사용 |
| TileJob | 일부 K/N 범위와 주소·소유권·친화도를 가진 작업 단위 |
| FCFS | 도착 순서 우선 처리 |
| Work Stealing | 빈 worker가 다른 queue의 eligible job을 가져오는 정책 |
| Locality cost | 원격 weight/activation/reduction/bundle mismatch의 모델 비용 |
| p95/p99 | 지연 표본의 95/99 백분위; tail을 나타냄 |
| Compute duty | 실제 compute cycle 비율 |
| Reservation occupancy | dispatch 후 대기까지 포함한 cluster 예약 비율 |
| Backpressure | downstream이 받을 수 없어 upstream 전송을 늦추는 흐름 제어 |
| CDC | 서로 다른 clock domain 사이의 안전한 신호 전달 |
| DDR channel/bank/row | 독립 채널, 내부 병렬 bank, bank 안의 row 주소 계층 |
| DRAMsim3 | DRAM timing simulator; 본 repo의 snapshot은 replay와 결합되지 않음 |
| SpinalHDL | Scala 기반 하드웨어 기술 언어 |
| Verilator | HDL을 C++ 모델로 변환해 시뮬레이션하는 도구 |
| ERC/DRC | 전기 규칙/배선 규칙 검사; 제작 가능성 전체를 보장하지 않음 |
