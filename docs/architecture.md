# K26–Memory FPGA 가상 시제품 구조와 구현 범위

## 닫힌 논리 데이터 경로

`ClosedLoopVirtualPrototypeTop`은 다음 경로를 하나의 backpressure-aware RTL
흐름으로 연결한다.

```text
MatVecFetchCommand
  → DMA 요청 FIFO
  → 4채널 메모리 명령 스케줄러
  → DDR 응답 경계(MemoryWeightResponse)
  → 작업 지역성에 따른 4개 논리 링크 FIFO
  → 작업 ID 기반 activation/weight 결합
  → 다중 큐 스케줄러
  → ComputeClusterArray
  → signed-INT8 MatVec 결과
```

입력 명령에는 작업 정보와 activation만 들어 있다. 가중치는 DDR 응답 경계에서
별도로 들어와 논리 링크 FIFO를 통과해야만 MatVec 명령으로 조립된다. 따라서
가중치 응답 없이 연산이 시작되지 않는다. pending table은 job ID를 기준으로
응답을 정확히 한 번만 수락하며, FIFO와 연산부의 역압을 상위 단계로 전달한다.

`ClosedLoopVirtualPrototypeTopSpec`은 실제 Gemma 3 1B 파일에서 제한적으로 추출한
세 개의 16×4 INT8 가중치 타일을 이 경로로 보낸다. DMA 명령, DDR 응답, MatVec
결과 cycle을 기록하고 software INT32 기준값과 일치하는지 검사한다.

## 물리 구현과 구분해야 하는 경계

현재 링크 FIFO는 넓은 논리 응답을 전달한다. 다음 항목은 아직 구현하지 않았다.

- GT serializer/deserializer와 lane bonding
- K26–Memory FPGA 사이의 실제 GTH wrapper
- 양쪽 clock domain crossing과 reset synchronization
- packet fragmentation, CRC 재전송, credit 반환
- MIG가 생성한 DDR3L PHY와 calibration
- Vivado 배치배선, timing closure, 실효 대역폭과 보드 전력 측정

따라서 현재 결과는 닫힌 **논리 RTL 가상 시제품**의 정확성과 역압을 검증한다.
물리 GTH/DDR 성능이나 실제 보드 대역폭을 검증하지 않는다.

## 기존 통합 셸

`K26WorkStealingTop`은 scheduler→연산 입력 저장소→MatVec 구간과 독립적인
메모리 명령·링크 라우팅 경로를 제공한다. 이전 논문은 이 셸의 세 경로를 하나의
전체 데이터 경로처럼 보이게 설명했다. 최종 논문에서는 직접 연결된
`ClosedLoopVirtualPrototypeTop`을 논리 구조 증거로 사용하고, 기존 셸은 모듈별
단위 시험과 설계 공간 실험용으로만 남긴다.

## KiCad 자료의 정확한 위치

현재 KiCad의 `k26_memory_coupon`은 전체 Memory FPGA 보드가 아니다. 범용 Samtec
커넥터 두 개가 K26 GTH 경계와 FPGA bank 경계를 대신하고, DDR3L x16 한 슬라이스와
대표 차동 링크 배선만 포함한다. 실제 K26 SOM 커넥터 핀, XC7K160T BGA pinout,
4채널 MIG, 전원 트리와 제작 검증은 포함하지 않는다. 따라서 이 자료는
**인터페이스 라우팅 검증 쿠폰**이며 `NOT FOR FABRICATION`이다.
