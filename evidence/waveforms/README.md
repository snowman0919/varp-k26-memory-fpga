# Work-stealing waveform evidence

This bundle is produced by the real SpinalHDL `TileScheduler`, `ComputeClusterArray`, `LegacyMatVecAdapter`, and `DecodeMatVecInt8`. Three jobs are intentionally held in queue 1; cluster 0 becomes available and steals jobs 1, 5, and 9. The test checks all four INT32 outputs against a software reference and closes accepted=dispatched=completed=3.

The harness proves scheduler-to-MatVec temporal behavior only. It does not prove GT/DDR PHY timing, physical bandwidth, synthesis timing, or Gemma model-level performance.

Generation:

```bash
sbt -batch "testOnly varp.WorkStealingEvidenceSpec"
python3 scripts/build_rtl_evidence.py
```

- Captured cycles: 224
- Steal cycles: 16, 17, 18
- VCD SHA-256: `e897a8119d4a603b41d743066c37a118e0cdd77cb61aa554f2835947e51e6829`
- Event CSV SHA-256: `9ce1ec5dd0c485029f495151df034d908da1a85fff82d6af47f6507a26b6fe8f`
