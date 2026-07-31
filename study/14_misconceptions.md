# 흔한 오해

| 오해 | 바로잡기 |
|---|---|
| 메모리가 병목이므로 외부 FPGA가 반드시 필요하다 | 로컬 DDR4 baseline이 없어 채택은 보류 상태다 |
| S3는 항상 가장 빠르다 | balanced/hotspot 이득이 없고 sequential skew에서 순위가 바뀐다 |
| occupancy 99%는 MAC 활용률 99%다 | 대기 포함 예약률이며 compute duty와 다르다 |
| S0 remote bytes 0은 측정 결과다 | 중앙 공유 storage를 가정한 모델 정의다 |
| 3/3 tile parity는 full model 정확성이다 | 세 representative 16×4 tile의 제한 증거다 |
| ORT 408.445 ms는 accelerator 결과다 | Y700 Android CPU EP 기능 참조다 |
| DRAMsim3 snapshot이 Gemma replay에 결합됐다 | 공개 snapshot은 보존 자료이며 재생성·결합되지 않았다 |
| ERC/DRC pass면 제작 가능하다 | unrouted/SI/PI/PDN/thermal 등 관문이 남는다 |
| 8 GB는 3B 실행을 증명한다 | generic capacity arithmetic일 뿐 실행 증거가 아니다 |
