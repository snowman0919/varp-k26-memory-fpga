# v11 연구 결과 동결

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

- S3 vs S1 TileJob p95: **-19.13%**
- S3 vs S1 TileJob p99: **-18.71%**
- S3 vs S2 비지역 가중치 이동량: **-35.49%**

이 결과는 불균형이 명시적으로 주어진 합성 부하의 조건 분석이다.

### Gemma 형상 + 의존성 + 모델 배치

- 기존 source-rule 배치: S3 vs S1 완료시간
  **+4.80%**,
  TileJob p95 **+0.28%**.
- size-aware 배치: 완료시간
  **-0.76%**,
  TileJob p95 **+0.00%**.
- channel-affinity 배치: 완료시간
  **-7.56%**,
  TileJob p95 **-19.79%**.

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
