# VARP K26–Memory FPGA — 10분 발표 Speaker Notes

총 목표 시간: 10:00

## Slide 1: Work Stealing으로 줄이는 Tail Latency (0:35)

기억할 문장: 지역성을 지키는 정적 큐도 작업이 치우치면 Tail latency를 키울 수 있습니다.

오늘 말씀드릴 질문은 단순히 메모리 대역폭이 중요한가가 아닙니다. 실제 Gemma 3 1B 작업을 여러 연산 클러스터에 나눌 때, 정적 소유권 때문에 일부 큐가 길어지고 다른 클러스터가 쉬는 상황을 어떻게 줄일 것인가입니다.

제안 구조는 K26 연산 SoC와 외부 Memory FPGA를 결합하고, Multi-Queue FCFS 위에 지역성 비용을 고려한 Work Stealing을 적용합니다. 핵심은 무조건 작업을 옮기는 것이 아니라, Tail을 줄이는 이득이 링크·메모리 이동 비용보다 큰 조건을 찾는 것입니다.

먼저 정적 큐에서 왜 Tail이 생기는지 보겠습니다.

## Slide 2: 왜 정적 큐가 Tail을 만드는가 (0:55)

기억할 문장: 정적 로컬 큐는 지역성을 지키지만 부하 균형을 보장하지 않습니다.

S1 정적 로컬 큐에서는 각 TileJob이 home cluster의 FCFS 큐에 들어갑니다. 이 방식은 원격 가중치 이동을 만들지 않는 장점이 있지만, skew가 생기면 Cluster 0의 큐만 길어지고 나머지 클러스터는 할 일이 없어집니다.

평균 지연만 보면 이 현상이 약하게 보일 수 있습니다. 하지만 사용자 체감과 시스템의 느린 요청을 결정하는 p95와 p99에서는 긴 queue wait가 그대로 드러납니다. 따라서 이 연구의 목표는 평균 처리량보다 Tail을 줄이면서 이동 비용을 통제하는 것입니다.

이 문제를 풀기 위해 계산 소유권과 메모리 친화도를 분리한 구조를 설계했습니다.

## Slide 3: K26 Compute × Memory FPGA (1:10)

기억할 문장: 이 구조는 계산할 위치와 데이터를 가져올 위치를 TileJob에서 분리합니다.

왼쪽 K26에는 TileScheduler, payload store, 네 개의 compute cluster와 signed INT8 16×4 MatVec가 있습니다. TileJob은 작업 identity, K/N 범위, weight·activation 주소, preferred channel과 link bundle을 보존합니다.

오른쪽 Memory FPGA 후보는 네 DDR3L 채널과 네 link bundle을 통해 weight service를 분리하는 구조입니다. 스케줄러는 어느 cluster가 계산할지 정하고, channel affinity는 데이터 이동 비용을 계산하는 기준이 됩니다.

현재 runnable RTL은 scheduler에서 payload store와 MatVec 결과까지입니다. DDR response와 link receive의 완전한 폐루프는 다음 검증 단계이며, 오늘의 중심은 이 구조 위에서 scheduling 조건을 분석한 결과입니다.

이제 유휴 클러스터가 어떤 규칙으로 작업을 가져오는지 보겠습니다.

## Slide 4: 유휴 클러스터가 일을 훔치는 5단계 (1:15)

기억할 문장: S3 지역성 인식 Work Stealing은 가장 오래된 작업이 아니라 이득이 남는 작업을 훔칩니다.

첫째, local queue가 비면 cluster가 유휴 상태임을 확인합니다. 둘째, 다른 victim queue에서 실행 가능한 작업을 탐색합니다. 셋째, job age에서 원격 weight, activation, reduction owner와 bundle mismatch 비용을 뺀 locality score를 계산합니다.

넷째, score가 양수인 eligible TileJob을 선택해 유휴 cluster로 옮깁니다. 마지막으로 job identity를 유지해 정확히 한 번만 completion이 발생하는지 검사합니다.

비교 기준인 S2는 가장 오래된 eligible job을 바로 가져옵니다. S3는 이동량을 줄이기 위해 지역성 비용을 함께 보므로 Tail과 remote traffic 사이의 절충이 생깁니다.

이 다섯 단계는 정책 개념을 설명합니다. 분석 모델은 victim queue의 모든 eligible job을 탐색하지만 현재 RTL은 victim head만 검사하며 ownership과 score 정의도 다릅니다. 따라서 model과 RTL이 알고리즘적으로 동일하다고 해석하면 안 됩니다.

정책을 비교하려면 실제 모델 작업을 동일한 TileJob ledger로 만들어야 합니다.

## Slide 5: 실제 Gemma 작업을 TileJob으로 바꾼다 (1:00)

기억할 문장: Gemma replay와 조건 분석용 치우침 스트레스는 서로 다른 작업 집합입니다.

해시로 고정한 Gemma 3 1B ONNX graph에는 7,837개 node가 있습니다. 여기서 attention의 q·k·v·o, MLP의 gate·up·down, lm_head를 필터링하면 token당 183개 projection이 됩니다.

Decode-32 조건에서는 183 곱하기 32, 즉 5,856개의 coarse TileJob ledger를 만듭니다. 이 Gemma replay에서 S3의 p95와 p99는 S1보다 각각 15.07%, 14.61% 낮았습니다.

다음 세 슬라이드는 이 한 개 replay를 반복하지 않습니다. 정책이 유효한 조건을 보기 위해 별도로 생성한 1,000-job 치우침 스트레스와 5개 seed를 사용합니다. 모든 비교에서 input, dispatch, completion ID가 같고 중복과 누락이 0인지 확인했습니다.

다음 슬라이드는 전체 2,000개 event를 축소한 그림이 아니라, 실제 차이가 시작되는 동일 시간 구간을 확대합니다.

## Slide 6: 놀고 있던 연산 클러스터가 Tail을 줄인다 (1:05)

기억할 문장: 제어된 치우침 스트레스에서 S3는 S1의 유휴 클러스터를 실제 steal 작업으로 채웁니다.

여기부터는 Gemma replay와 별개의 synthetic scheduler 실험입니다. 각 workload는 1,000 job이고 seed 19, 23, 29, 31, 43을 사용합니다. full-overlap analytical model이며 물리 cycle이 아닙니다. 타임라인은 seed 23의 S1과 S3, 총 2,000개 event 중 동일한 41k에서 43k 구간을 확대했습니다.

S1에서는 Cluster 0만 파란 로컬 작업을 처리하고 Cluster 1부터 3은 유휴입니다. S3에서는 J172, J162, J143이 각각 C0에서 C1, C2, C3으로 이동합니다. 회색선은 큐 대기, 어두운 색 구간은 링크·메모리 준비, 밝은 끝 구간은 compute입니다.

전체 5개 seed 중앙값에서 skew p95는 S1 대비 18.12% 줄었습니다. 그 대가로 S3에는 약 1.45 MiB의 원격 가중치 이동이 생깁니다. 즉 유휴를 줄인 효과와 이동 비용을 함께 봐야 합니다.

이제 p95뿐 아니라 p99도 같은 방향인지 확인하겠습니다.

## Slide 7: Tail은 얼마나 줄었나 (1:20)

기억할 문장: S3의 효과는 p95 한 점이 아니라 p99까지 같은 방향으로 나타납니다.

Gemma replay와 별개의 1,000-job synthetic skew workload에서 5개 seed 중앙값을 보겠습니다. full-overlap analytical model이며 물리 timing이 아닙니다. p95는 S1의 285.3k cycle에서 S3의 233.6k cycle로 18.12% 감소했습니다. p99는 302.2k에서 247.3k cycle로 18.16% 감소했습니다.

Mixed workload에서도 p95는 17.59% 줄고 p99도 감소합니다. 반면 balanced와 channel-hotspot에서는 stealing할 불균형이 없거나 memory channel 자체가 병목이어서 S3의 이득이 나타나지 않습니다.

따라서 결론은 S3가 항상 빠르다는 것이 아닙니다. 정적 ownership 때문에 queue skew가 Tail을 지배하는 조건에서 효과가 있다는 것입니다.

그렇다면 줄어든 queue wait의 비용이 어디로 이동하는지 보겠습니다.

## Slide 8: Work Stealing은 병목을 없애지 않고 이동시킨다 (0:55)

기억할 문장: Tail 감소는 공짜가 아니라 원격 이동과 resource pressure로 지불합니다.

이 수치도 Gemma replay가 아니라 같은 synthetic skew, 5-seed 중앙값, full-overlap analytical model에서 나옵니다. 왼쪽은 S3와 S1의 비교로 p95가 18.12% 감소합니다. 실제 평균 queue wait 감소율은 17.86%이므로 p95와 같은 지표로 해석하면 안 됩니다. 가운데는 S3와 S2의 비교로 remote weight가 37.84% 줄어듭니다.

오른쪽도 S3와 S2의 비교입니다. 더 보수적인 선택 때문에 마지막 completion은 0.98% 길어집니다. 즉 세 수치는 비교 기준이 서로 다릅니다. S1은 정적 baseline이고, S2는 locality를 고려하지 않는 stealing baseline입니다.

이 결과는 queue wait가 줄어든 대신 link와 memory service가 더 중요해졌음을 보여줍니다. 다음 단계는 이 비용을 실제 보드 인터페이스에서 계측하는 것입니다.

## Slide 9: 알고리즘을 실제 보드 인터페이스로 내렸다 (0:55)

기억할 문장: 물리 reference는 실제 KiCad 객체지만 아직 제작 가능한 보드는 아닙니다.

가운데 큰 이미지는 native KiCad source에서 렌더한 validation coupon입니다. 오른쪽 확대는 K26–Memory FPGA 연결 경계, 기준 클록 차동 경로, 대표 routed coupon 영역을 실제 render에서 잘라 보여줍니다.

현재 coupon에는 29 footprints, 20개의 routed GTH/refclock nets가 있고 선언한 제한 범위에서 ERC와 routed-subset DRC가 0입니다. 그러나 전체 보드에는 55 unrouted nets가 남아 있고, MIG pin placement, SI/PI, PDN, thermal과 timing closure는 수행하지 않았습니다.

따라서 이 이미지는 알고리즘을 어떤 인터페이스로 내려갈지 구체화한 reference coupon입니다. 제작 가능성을 주장하지 않고, 다음 검증의 대상과 범위를 명확히 한 것입니다.

## Slide 10: 조건을 찾았고, 다음은 폐루프 검증이다 (0:50)

기억할 문장: 이 연구의 기여는 Work Stealing의 승리가 아니라 유효 조건과 비용을 함께 밝힌 것입니다.

실제 Gemma graph에서 TileJob 변환을 정의했고, 별도의 제어된 스트레스에서 Tail과 이동 비용 조건을 분석했으며, 그 구조를 K26–Memory FPGA RTL과 KiCad 참조 설계까지 연결했습니다.

다음 단계는 DDR 응답부터 MatVec까지 폐루프를 완성하고 실제 대역폭·Tail·보드 전력을 측정하는 것입니다.

정적 큐의 유휴를 줄이면 Tail은 짧아지지만 링크·메모리 비용이 생깁니다. 이 연구는 그 재배치가 유효한 조건을 함께 제시합니다. 질문 받겠습니다.
