# 개념 지도

```text
Gemma ONNX hash
  └─ graph inventory (7,837 nodes)
      └─ projection ledger (183/token)
          ├─ representative INT8 tile → RTL MatVec parity
          └─ analytical TileJob stream → S0/S1/S2/S3 비교
                                      ├─ p95/p99
                                      ├─ completion time
                                      └─ remote bytes

K26 compute plane ── runnable RTL
Memory command plane ── independent command output
Link routing plane ── independent bundle output
DDR response/DMA/receive/CDC ── BLOCKED integration gate

KiCad native source → bounded ERC/DRC → NOT FOR FABRICATION
```

핵심은 화살표 하나가 곧 증거 결합을 뜻하지 않는다는 점이다. 각 연결은 실제 코드·테스트·로그가 있을 때만 닫힌 것으로 취급한다.
