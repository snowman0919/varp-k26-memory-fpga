# RTL module map

This inventory is generated from the named Scala sources. Width and queue descriptions are structural RTL facts; DDR PHY, GT PHY, synthesis, and board timing remain external physical gates.

| Module | Source | Role | Queue depth | Evidence boundary | Figure |
|---|---|---|---|---|---|
| `TileScheduler` | `hw/src/main/scala/varp/scheduler/TileScheduler.scala` | S0–S3 job ownership, FCFS and steal selection | 8 | implemented RTL | F01/F02 |
| `K26WorkStealingTop` | `hw/src/main/scala/varp/k26/K26WorkStealingTop.scala` | paper integration shell and payload identity store | scheduler 8; store 32 | implemented RTL | F01 |
| `ComputeClusterArray` | `hw/src/main/scala/varp/compute/ComputeCluster.scala` | one/two/four concrete compute clusters | cluster 4 | implemented RTL | F01 |
| `ComputeCluster` | `hw/src/main/scala/varp/compute/ComputeCluster.scala` | FCFS command buffering and exact job counters | 4 input; 2 output | implemented RTL | F01/F03 |
| `MatVecTileConsumer` | `hw/src/main/scala/varp/compute/ComputeCluster.scala` | buffered adapter around the imported MatVec | 4 input; 2 output | implemented RTL | F01/F03 |
| `LegacyMatVecAdapter` | `hw/src/main/scala/varp/compute/LegacyMatVecAdapter.scala` | job-preserving adapter for DecodeMatVecInt8 | single active command | implemented RTL | F01 |
| `DecodeMatVecInt8` | `hw/src/main/scala/qk/DecodeMatVecInt8.scala` | actual 16×4 signed INT8 MatVec primitive | internal pipeline | implemented RTL | F01/F03 |
| `BundleRouter` | `hw/src/main/scala/varp/link/BundleRouter.scala` | preferred-bundle assignment and bounded reroute | transport FIFO | implemented RTL; separate plane | F01 |
| `MultiChannelMemoryIngress` | `hw/src/main/scala/varp/memory/MultiChannelMemoryScheduler.scala` | output-tile channel affinity | 8/channel | implemented RTL; separate plane | F01 |
| `BankAwareChannelScheduler` | `hw/src/main/scala/varp/memory/MultiChannelMemoryScheduler.scala` | row-hit-first selection with age cap | 4 | implemented RTL; PHY external | F01 |
| `WorkStealingEvidenceTop` | `hw/src/main/scala/varp/evidence/WorkStealingEvidenceTop.scala` | instrumented scheduler-to-real-MatVec evidence harness | scheduler 8; cluster 4 | evidence-only RTL harness | F02/F03 |

Generation command: `python3 scripts/build_rtl_evidence.py`.
