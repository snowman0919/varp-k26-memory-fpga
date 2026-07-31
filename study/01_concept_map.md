# 개념 지도

```text
Gemma 3 1B ONNX
  └─ 7,837 nodes → 183 projections/token
      └─ full-K, N≤1024 → 802 TileJobs/token
          ├─ qkv→o→gate/up→down→next layer
          ├─ 초기 배치 4종
          └─ S1/S2/S3 비용 포함 분석

K26: scheduler + 4 compute clusters + MatVec
  ↕ 4 logical links
Memory FPGA 후보: 4 DDR3L channels + weight service

실제 타일 → DMA 요청 → DDR 응답 경계 → 논리 FIFO → MatVec → INT32 결과
GTH/MIG/CDC/packet/board timing → 후속 물리 구현

KiCad generic boundary coupon → NOT FOR FABRICATION
```

중심 판단은 “외부가 항상 빠른가”가 아니라 “어떤 확장 조건에서 로컬 기준선을
넘는가”이다.
