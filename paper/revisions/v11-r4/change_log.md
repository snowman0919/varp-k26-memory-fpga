# v11-r4 변경 기록

- Q05의 증거 구분을 최신 원고 IV절 표 2에 연결했다.
- Q13의 MatVec 근거를 실제 `ComputeCluster.scala`와 `DecodeMatVecInt8.scala`로 고쳤다.
- Q29의 6.4 GB/s 산술값과 12.8 GB/s 민감도 지점을 서로 다른 가정으로 명시했다.
- Q70의 네 채널×2 GiB 구성을 미결정 분석 후보로 한정했다.
- 논리 Stream/FIFO 역압과 미구현 물리 크레딧·클록 도메인 교차를 분리했다.
- Slide 9의 사건 ID와 실행 구간이 원본 CSV에 맞고 잘림이 없음을 확인했다.
