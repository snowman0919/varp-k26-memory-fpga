# 논문 순회

## I–II. 문제와 차별점

‘메모리가 병목’이라는 일반론을 TileJob 소유권, queue skew, locality cost, remote-byte 회계로 구체화한다. 알고리즘 신규성이나 최고 성능을 주장하지 않고 evidence chain을 기여로 둔다.

## III. 실제 workload

해시로 묶인 Gemma 3 1B ONNX에서 7,837-node inventory와 token당 183 projection을 얻는다. 실제 weight 16×4 tile 세 개만 RTL MatVec parity를 확인했으므로 model-wide accuracy로 확대하면 안 된다.

## IV–V. 구조와 정책

S0는 이상적 중앙 FIFO, S1은 static local, S2는 oldest eligible stealing, S3는 age에서 locality penalty를 뺀 score를 사용한다. compute/memory/link plane의 독립성을 명시한다.

## VI–VII. 방법과 결과

동일한 1,000-job synthetic streams와 seed 5개를 비교한다. full-overlap과 sequential은 물리 timing이 아니라 service boundary다. S3는 skew/mixed tail과 remote bytes에 이득이 있지만 balanced/hotspot에는 이득이 없고 completion time은 소폭 악화될 수 있다.

## VIII. 물리 범위와 결론

KiCad coupon은 native source와 제한된 검사 증거다. 55 unrouted nets, SI/PI/PDN/thermal 미검증 때문에 제작 준비 상태가 아니다. 다음 단계는 response가 있는 DMA/link/DDR loop와 보드 계측이다.
