# 부록 A. Evidence taxonomy와 재현 단위

이 기술보고서는 수치마다 생성 경로를 네 층으로 나눈다. Direct evidence는 ONNX graph parser가 읽은 node, initializer와 external-data byte, KiCad source의 component·net·track 수처럼 artifact에서 다시 셀 수 있는 값이다. RTL-simulated evidence는 Verilator에서 handshake와 sequential logic을 진행한 값이다. Analytical evidence는 명시한 event와 cost 식이 만든 값이다. Hybrid evidence는 서로 다른 두 evidence layer를 합친 값이다.

Gemma trace의 재현 단위는 model file 자체가 아니라 model manifest와 trace manifest다. Model weight는 repository에 복사하지 않는다. Manifest가 ONNX와 external-data SHA-256, file size, opset, input/output, layer·hidden·intermediate·vocabulary 정보를 기록한다. 생성기는 authorized read-only model directory를 입력받아 graph_inventory, projection_trace, token_trace와 representative weight tile을 다시 만든다. Output hash가 trace manifest와 다르면 paper 숫자를 재사용하지 않는다.

Scheduler의 재현 단위는 ledger SHA-256이다. 같은 seed와 workload로 생성한 job sequence가 정책마다 달라지면 공정한 비교가 아니다. 각 결과 row는 scheduler뿐 아니라 cluster, channel, bundle, width, completed ID count, duplicate count와 timeout을 함께 저장한다. Process repetition은 같은 ledger와 모델이 byte-identical 결과를 내는지 검사한다.

RTL temporal evidence의 공개 재현 단위는 current RTL test와 compact event CSV다. CSV는 224 cycle을 보존하고 cycle 16, 17, 18의 steal, 이후 MatVec start/result와 마지막 counter를 기계적으로 검사한다. Annotated SVG는 설명용 파생물이며 raw VCD는 저장소 크기를 줄이기 위해 `v10-final` archive에만 보존한다.

# 부록 B. RTL module map과 interface

TileScheduler는 S0–S3 ownership, FCFS queue와 victim selection을 구현한다. Scheduler depth는 local queue당 8이다. 표 3의 증거 경계에 따라 actual Gemma external-data tile→DecodeMatVecInt8와 synthetic TileScheduler→payload store→MatVec는 서로 다른 RTL-simulated 경로다. Scheduler dispatch→DMA/link/DDR request·response→MatVec release는 blocked 상태다.

ComputeClusterArray는 1, 2, 4개의 concrete cluster를 생성한다. 각 ComputeCluster의 input FIFO depth는 4, output FIFO depth는 2다. MatVecTileConsumer는 LegacyMatVecAdapter를 거쳐 16×4 signed INT8 DecodeMatVecInt8 primitive를 실행한다. Result는 INT32이며 job ID와 함께 반환된다. Accepted, dispatched, completed counter와 output ID가 exact-once invariant의 기준이다.

BundleRouter는 preferred bundle과 bounded reroute를 수행한다. MultiChannelMemoryIngress는 output tile에 channel affinity를 부여한다. BankAwareChannelScheduler는 row hit를 우선하지만 age cap으로 starvation을 제한한다. 이 memory/link plane은 생성 가능한 RTL이지만 WorkStealingEvidenceTop의 three-job waveform에 물리 DDR/GTH로 결합되지 않는다.

Clock boundary는 논리적으로 compute, link와 memory plane으로 나뉜다. 현 증거는 기능 simulation clock을 사용한다. K26 PL clock, GTH reference clock, Memory FPGA fabric/MIG clock과 CDC constraint를 production XDC에서 닫지 않았다. 따라서 module map의 bus width와 queue depth는 structural fact이지만 Fmax와 throughput은 blocked다.

# 부록 C. Gemma graph와 tile 추출 상세

Graph inventory는 node index, name, operator category, K, N, dtype, initializer name, byte offset, byte length, activation/output byte와 candidate cluster/channel/bundle을 기록한다. Attention projection 104개는 26 layer의 q, k, v, o로 구성된다. MLP 78개는 26 layer의 gate, up, down이다. 마지막 lm_head가 한 개 추가되어 토큰당 183개가 된다.

Token trace는 tokenizer가 만든 32개 deterministic input ID와 projection-order hash를 연결한다. 생성 text나 ORT timing trace가 아니다. Scheduler replay는 각 token의 projection order를 반복하고 각 projection을 한 개 coarse INT8 job으로 취급한다. 실제 accelerator는 projection을 많은 16×4 tile로 나누어야 하므로 coarse job의 wait distribution을 physical tile latency로 읽을 수 없다.

Representative tile은 initializer external-data offset에서 float32 64개를 읽는다. Quantizer는 tile별 maximum absolute value를 구하고 scale을 max_abs/127로 둔다. 각 값은 scale로 나눈 뒤 nearest integer로 반올림하고 -127에서 127로 clamp한다. Zero point는 0이다. 이 방식은 정확성 fixture를 고정하기 위한 것이며 production per-channel quantization policy가 아니다.

RTL parity는 attention output, MLP gate와 lm_head 세 tile에 대해 software의 signed INT8 dot product와 hardware INT32 result를 비교한다. Input vector와 quantized weight가 모두 fixture에 저장되어 model file 없이도 bounded RTL test를 다시 실행할 수 있다. 반대로 full graph trace를 재생성하려면 license가 허용된 원본 model이 필요하다.

# 부록 D. Scheduler algorithm과 invariants

S1은 arrival 시 home cluster queue에 job을 넣고 FIFO head만 실행한다. S2는 idle cluster가 victim queue의 eligible job 중 가장 오래된 것을 선택한다. S3의 ordering key는 age benefit과 locality penalty를 결합한다. Penalty는 remote weight byte, activation 비상주, reduction owner mismatch와 preferred bundle mismatch를 나타낸다. Score가 threshold를 넘지 않으면 local owner가 기다린다.

Stealing은 queue element 복제가 아니라 ownership transfer다. Scheduler는 victim queue에서 job을 제거한 뒤 target cluster에 한 번만 dispatch한다. Payload identity store는 job ID에 대응하는 weight/input fixture를 내보낸다. Completion scoreboard는 이미 끝난 ID를 다시 수락하지 않는다.

정상 종료 invariant는 input ID set과 completed ID set의 동일성, duplicate completion 0, ingress backlog 0과 timeout false다. Starvation ratio, completion reordered와 steal success rate는 진단 지표이며 correctness를 대신하지 않는다. Stalled bundle stress는 큰 completion 값으로 정상 통계에 섞지 않고 명시적 timeout/correctness false로 끝나야 한다.

Offline Oracle은 각 job과 resource availability를 미리 아는 list scheduler다. Oracle row의 resource lower bound는 compute, channel과 link load의 최대값이다. List schedule completion을 수학적 optimum으로 부르지 않는다. S0도 실제 central queue의 arbitration과 wiring을 완전히 나타내지 않으므로 lower-reference로만 사용한다. 특히 S0 remote weight 0은 관측이 아니라 global shared storage를 암묵적으로 둔 정의다. S0-physical은 arbitration 2, fanout 2, crossbar 3의 임의 +7 cycle/job 한 점만 추가한다. 대칭 traffic account와 0/수십/수백 cycle sensitivity가 없어 central/distributed physical 순위를 정할 수 없다.

# 부록 E. Synthetic 결과의 workload별 해석

Balanced는 네 home cluster와 channel에 job을 균등하게 배치한다. S0, S1, S2, S3는 같은 p95 19,524 cycle과 completion 22,506 cycle을 기록했다. S0-physical은 central control 때문에 completion 24,256 cycle로 길다. 이 case에서 stealing은 한 번도 발생하지 않는다.

Bursty는 arrival group 때문에 global FIFO도 burst wait를 받는다. S1 p95 중앙값은 61,001 cycle이고 S3는 60,891 cycle로 거의 같다. Completion은 S1 67,976, S2 66,934, S3 66,958 cycle이다. S3 remote weight 44,032 B는 S2 58,368 B보다 낮다. 그러나 차이가 작으므로 정책 우열을 강하게 말할 수 없다.

Hotspot은 preferred channel 0을 집중시킨다. S1과 S3 p95는 모두 159,940 cycle이고 completion도 170,908과 170,816 cycle로 유사하다. Compute work를 다른 cluster로 옮겨도 shared channel service가 제한되기 때문이다. 이 결과는 channel bottleneck을 queue policy 하나로 해결할 수 없음을 보여준다.

Skew는 home cluster 0에 job을 집중시킨다. Full-overlap mode에서 S1/S2/S3의 compute duty는 0.057097/0.069318/0.068999이고 reservation occupancy는 0.336200/0.998086/0.994864다. S1/S2/S3 unreserved idle은 811,713/1,914/5,137 cycle이다. Mixed의 compute duty는 0.068345/0.081225/0.080889, reservation occupancy는 0.413076/0.998245/0.996291, unreserved idle은 1,210,683/3,034/6,432 cycle이다. 정의는 본문 VI-B와 같으며 0.995/0.996은 reservation occupancy일 뿐이다.

Mixed는 attention, MLP와 lm_head shape를 섞어 job size 분산이 크다. S1 p95 478,553 cycle, S3 394,375 cycle로 tail이 줄지만 Oracle p95 341,161 cycle와 차이가 남는다. 큰 job의 locality penalty와 queue ordering을 더 정교하게 조정할 여지가 있다.

Seed 5개는 workload generator의 제한된 sensitivity다. Process repetition 3개는 같은 seed를 복제하므로 15개 독립 sample이 아니다. Confidence interval이나 통계적 유의성을 제시하지 않고 중앙값과 방향만 해석한다.

기본 latency 식은 같은 dispatch-ready 시점에서 link와 memory를 동시에 시작하고 `data_ready=max(link_end,memory_end)`로 두는 full-overlap abstraction이다. 이때 skew S1/S2/S3 p95는 285,333.05/236,527.85/233,625.15 cycle이고 mixed는 478,553.05/403,766.25/394,375.45 cycle이다. 별도 sequential-service sensitivity에서 p95는 skew 499,243.85/260,052.10/264,294.60, mixed 825,278.25/471,918.25/463,867.20 cycle이다. 따라서 skew에서는 S3가 S2보다 1.23% 낮던 full-overlap 순위가 sequential mode에서 S2가 약 1.63% 낮은 것으로 뒤집히고, mixed에서는 S3가 각각 2.33%와 1.71% 낮아 방향이 유지된다. 두 경계 모두 실제 DMA/link/DDR protocol timing 측정이 아니다.

# 부록 F. Gemma hybrid 조립식

Projection cycle은 200 MHz analytical model clock으로 millisecond로 변환한다. Decode-1은 생성 토큰 1개의 183 job, decode-32는 생성 토큰 32개의 5,856 job이다. 이 조건은 KV context-32K와 별개다. Link traffic은 modeled weight, activation retransmission, partial sum과 overhead를 포함한다. S0와 S1의 remote weight가 0이어도 total link byte는 model data path에 의해 약 1.003 GB/token이다. Decode-32의 S3 6.3346 s는 S0 6.3676 s보다 0.518% 짧지만 단일 coarse ledger와 비대칭 locality 회계 안의 작은 차이다.

Host fallback은 Y700 CPU EP profile에서 projection operator group을 제외한 평균 204.701 ms/token이다. Decode 32는 이 값을 32배한 6.550 s를 사용한다. Hybrid total은 scheduler projection time과 이 fallback의 합이다. Model이 autoregressive context 증가, cache effect, thermal throttling과 runtime scheduling을 포함하지 않으므로 선형 외삽은 architecture bookkeeping에만 쓴다.

Decode 32에서 S3는 S1보다 projection 1.006 s, hybrid total도 1.006 s 짧다. Host fallback이 정책과 무관하게 고정되어 있기 때문이다. 따라서 hybrid total 차이는 새로운 host measurement를 추가하지 않으며 projection model 차이를 그대로 반영한다.

Oracle projection은 5.269 s이지만 list schedule 자체가 physical implementation은 아니다. S3와 Oracle의 1.066 s 차이는 locality, queue와 resource availability의 modeling gap을 포함한다. 이를 hardware optimization ceiling으로 단정하지 않는다.

# 부록 G. Power와 energy formula

Compute unit energy는 10억 INT8 MAC에 pJ/MAC를 곱한다. Low, central, high는 각각 0.001, 0.005, 0.015 J per 10억 MAC이다. 이 범위는 architecture sensitivity이며 K26 또는 XC7K160T power report가 아니다.

Link unit energy는 1 GiB×8 bit/byte×pJ/bit로 계산한다. 24, 51.2, 120 pJ/bit에서 1 GiB transport는 0.206, 0.440, 1.031 J다. Coding overhead, serializer clock, idle, retry와 board loss가 빠져 있으므로 serialized payload unit일 뿐 transceiver total energy가 아니다.

DDR3L command model은 VDD, incremental current, command cycle과 tCK를 사용한다. Central scenario의 per-x8-die unit은 ACT 0.803 nJ, PRE 0.427 nJ, READ 0.803 nJ, WRITE 0.587 nJ, REFRESH 71.253 nJ다. Idle precharged/active는 cycle당 0.054/0.064 nJ다. Low/high corner는 central의 0.8/1.2배다.

보존된 `results/runs/dramsim3-snapshot/dramsim_stats_ch4.json` snapshot은 four-channel command와 background category를 제공하지만 PRE를 별도 bucket으로 보고하지 않는다. 공개 저장소에는 runnable adapter가 없으며 PRE energy를 0으로 채우지 않고 blank로 둔다.

별도 Gemma energy join은 graph-derived MAC, DRAM weight byte와 modeled link byte를 unit energy에 결합한다. S3 decode-32의 link account는 base 1,003,000,416 B/token과 steal overhead 88,806,088 B/token을 합친 1,091,806,504 B/token이다. 이에 따른 low/central/high dynamic estimate는 0.291943317/0.553753651/1.185041645 J/token이다. Central case의 hybrid latency는 약 0.403 s/token, energy-delay product는 약 0.222973478 J·s, throughput은 2.483495600 token/s다. 이 값은 dynamic READ+ACT+PRE, compute와 serialized payload만 포함한다. Refresh, idle, controller, PHY, clock와 board power가 빠져 있어 board-calibrated total energy가 아니다.

# 부록 H. DRAM capacity와 cost sensitivity

8 GiB baseline은 channel당 두 개 x8 package가 한 x16 rank를 이루고 이를 네 channel 반복한다. AS4C1G8D3LA-10BCN package 한 개는 8 Gb이며 내부에 두 physical 4 Gb x4 die가 있다. 전체는 package 8개, physical die 16개다. 16 GiB option은 channel당 두 번째 rank를 추가해 package 16개, physical die 32개가 된다. Gemma 1B INT8 context-32K capacity budget 2.4301 GiB는 명목 K26 local 4 GB에도 들어간다. 따라서 8 GiB의 근거는 Gemma 1B capacity necessity가 아니라 검증 대기 중인 independent-bandwidth/service-isolation design point다.

Quantity-1 price snapshot은 procurement quote가 아니며 시점에 따라 바뀐다. Low 39.32 USD/package와 high 97.10 USD/package를 그대로 보여주고 midpoint 68.21 USD를 sensitivity에 사용한다. Physical-die dollar는 package price/2로 환산한다. Package, rank와 bare die를 혼동하지 않는다.

Pin-rate 상한 6.4 GB/s에 delivery factor 0.50, 0.70, 0.85를 곱해 3.2, 4.48, 5.44 GB/s를 만든다. 이 factor는 측정 효율이 아니다. 16 GiB second rank는 capacity를 두 배로 하지만 channel width와 data rate를 바꾸지 않아 bandwidth 상한은 같다. 그 결과 effective GB/s per die-dollar는 8 GiB option의 절반이 된다.

Cost table은 memory component boundary만 다룬다. K26 SOM, FPGA, PCB, power, connector, heatsink, assembly, NRE, freight와 tax를 합하지 않는다. Total accelerator price, total BOM과 product value를 이 결과로 표현할 수 없다.

Hybrid throughput을 같은 DRAM-only denominator로 나눈 sensitivity도 별도 저장한다. S3 decode 32의 central hybrid throughput 2.4835 token/s를 midpoint DRAM-die cost 545.68 USD로 나누면 0.004551 token/s per DRAM-die dollar다. Low/high price snapshot에서는 denominator만 바뀐다. Cost-normalized CSV는 이 계산과 무관한 `delivery_case` 축을 제거해 price case 세 행만 둔다. 이 값은 total-system price-performance가 아니며 현재 hybrid throughput model의 DRAM-die 가격 정규화다.

# 부록 I. KiCad audit 상세

Native gate는 coupon ERC 0 error/0 warning, hierarchy ERC 0/0, coupon PCB DRC 0 violation, schematic parity 0 issue와 native unconnected pad 0을 기록했다. 이 값은 deliberately reduced connector/bank boundary와 proposal rule에만 적용된다.

Raw source inventory는 schematic component 29개, named net 116개, PCB footprint 29개, track segment 65개, via 50개, zone 1개와 four copper layer declaration이다. Analyzer의 routing_complete는 false이며 unrouted net은 55개다. Explicit routed subset은 GTH/reference-clock 20개 single-ended net이다.

Return-path cross analysis는 DDR CK P/N, DQ0, LDQS P/N과 두 GTH reference-clock pair에서 9개 plane-gap crossing을 찾았다. Ground stitching via도 없다. EMC risk analyzer의 67/100은 checklist priority일 뿐 compliance score가 아니다. Ten decoupling capacitor distance, J5 filtering 부재와 outer-layer reference clock이 주요 finding이다.

Manufacturing risk에는 0.10 mm annular ring, untented via-in-pad 10개, front fiducial 부재 27개와 test-point coverage 0/116이 포함된다. Gerber set은 26 file, mixed drill 1개, hole 63개, flash 1,139개, draw 5,533개를 가진다. Sparse layer와 full Edge.Cuts extent 비교에서 alignment warning이 있으므로 독립 CAM overlay가 필요하다.

Production 단계는 exact MPN/datasheet archive, four-controller Vivado MIG bank placement, GTX quad/refclock assignment, fabricator stackup, impedance/loss/jitter budget, plane fill와 stitching, PDN/SI/thermal/EMC, full routing과 manufacturing test를 요구한다. 그전에는 proposal-only 및 NOT FOR FABRICATION label을 유지한다.

# 부록 J. Reproduction과 claim audit

논문 build는 Markdown을 standalone HTML로 변환하고 figure를 embedded resource로 포함한 뒤 headless Chrome으로 PDF를 출력한다. Submission PDF는 A4 two-column CSS를 사용하고 기술보고서는 A4 single-column CSS를 사용한다. Build 이후 pdfinfo로 page 수를 읽고 pdftotext로 text extraction을 확인한다.

Quality gate는 PDF text에 local filesystem path와 backtick이 없는지 검사한다. Overclaim search는 보편적 최적, 제작 가능, 실제 보드 전력, full 3B execution과 total accelerator price에 해당하는 표현을 찾는다. 해당 단어가 limitation이나 금지 문맥에 나타날 수 있으므로 최종 판정은 문맥 감사다.

논문 수치는 graph manifest, scheduler CSV, RTL event CSV, cost sensitivity와 KiCad review에서 교차 확인한다. Figure는 설명 자산이고 source CSV가 숫자 권위다. Publication asset metadata의 blocked interpretation이 본문 claim보다 우선한다.

일반 재현은 `make setup && make reproduce` 하나로 실행한다. 필요한 외부 요소는 Java/Scala/sbt, Verilator, Python, KiCad CLI, Pandoc, Chrome과 PDF utilities다. Authorized Gemma model path는 선택적인 `make model-trace`에만 필요하다. Model weight는 repository와 release archive에 포함하지 않는다.
