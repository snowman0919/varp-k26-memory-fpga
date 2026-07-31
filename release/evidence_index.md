# VARP K26 evidence index

This index separates direct, simulated, analytical, hybrid, and blocked claims. Hashes bind every entry to the release snapshot.

| ID | Evidence type | Artifact | Supported | Forbidden |
|---|---|---|---|---|
| E01 | graph-derived + analytical | `experiments/gemma3_1b/trace_manifest.json` | Hashed ONNX graph/token ledger and replay provenance | End-to-end model execution or hardware latency |
| E02 | graph-derived | `experiments/gemma3_1b/projection_trace.csv` | 183 dense projection nodes and source tensor geometry | Measured execution time |
| E03 | RTL-simulated bounded extract | `evidence/model/gemma3_1b_rtl_tile_parity.csv` | Three actual-weight 16x4 INT8 tiles match software references | Full-model RTL inference or global quantization accuracy |
| E04 | RTL-simulated | `evidence/waveforms/work_stealing_events.csv` | Scheduler-to-real-MatVec event timeline for the bounded case | System throughput or board timing |
| E05 | analytical model | `results/experiments/scheduler_controlled.csv` | Controlled six-policy comparisons across five seeds and three runs | RTL cycle performance or physical speedup |
| E06 | hybrid modeled | `results/model_level/gemma3_1b_hybrid.csv` | Projection-model plus disclosed host fallback arithmetic | Measured end-to-end accelerator latency |
| E07 | estimated energy | `results/power_cost/energy_category_model.csv` | Compute/link/DRAM energy sensitivity ranges | Vivado or board power |
| E08 | current price snapshot + arithmetic | `cost/cost_sensitivity.csv` | Memory-package/die cost sensitivity only | Full FPGA/board/system price |
| E09 | native KiCad | `hardware/kicad/k26_reports/k26_scope_manifest.json` | Internal proposal-coupon ERC/DRC/parity status | Fabrication readiness, SI/PI, or compliance |
| E10 | controlled review | `hardware/kicad/controlled_review.md` | Native and analyzer findings with explicit overrides | Production pinout, thermal closure, or EMC pass |
| E11 | toolchain contract | `docs/toolchain/COMPATIBILITY_MATRIX.md` | Required tools and explicit missing-tool consequences | Host-specific tool availability or successful design execution |
| E12 | asset QA | `build/publication_assets/validation_report.json` | Figure/flow/presentation asset validation | Scientific validation of the underlying models |

## Claim-to-evidence crosswalk

| Claim | Figure | Table / result | Generator / verifier | Primary source |
|---|---|---|---|---|
| C01: Architecture planes and open payload boundary | `paper/final/figures/paper_f01_evidence_path.svg` | `paper/final/submission_manuscript.md#iv-k26memory-fpga-시스템` | `hw/src/main/scala/varp/k26/K26WorkStealingTop.scala` | `docs/architecture.md` |
| C02: 7,837 graph nodes and 183 projections/token | `paper/final/figures/paper_f02_onnx_runtime_graph.svg` | `experiments/gemma3_1b/projection_trace.csv` | `experiments/gemma3_1b/generate_trace.py` | `experiments/gemma3_1b/trace_manifest.json` |
| C03: S0/S1/S2/S3 policy and evidence boundary | `paper/final/figures/paper_f03_policy_boundary.svg` | `results/experiments/scheduler_controlled.csv` | `scripts/run_k26_experiments.py` | `src/varp/k26_scheduler_model.py` |
| C04: Three bounded steals preserve MatVec identity | `paper/final/figures/paper_f04_waveform_identity.svg` | `evidence/waveforms/work_stealing_events.csv` | `scripts/build_rtl_evidence.py` | `hw/src/test/scala/varp/WorkStealingEvidenceSpec.scala` |
| C05: S3 lowers skew/mixed p95 versus S1 | `paper/final/figures/paper_f05_tail_latency.svg` | `build/publication_assets/tables/scheduler_core_metrics.csv` | `publication_tools/generate_publication_and_presentation.py` | `results/experiments/scheduler_controlled.csv` |
| C06: S3 p95/completion/remote-byte trade-off versus S2 | `paper/final/figures/paper_f06_tradeoff.svg` | `build/publication_assets/tables/scheduler_core_metrics.csv` | `publication_tools/generate_publication_and_presentation.py` | `results/experiments/scheduler_controlled.csv` |
| C07: Energy and cost are sensitivity estimates | `build/publication_assets/figures/F06/figure.svg` | `results/power_cost/energy_category_model.csv` | `scripts/build_power_cost_evidence.py` | `cost/memory_die_price_snapshot.csv` |
| C08: Native KiCad coupon is not fabrication-ready | `paper/final/figures/paper_f07_kicad_coupon_render.png` | `hardware/kicad/k26_reports/k26_scope_manifest.json` | `scripts/verify_k26_kicad.py` | `hardware/kicad/controlled_review.md` |
| C09: Blocked physical performance and power claims | `build/publication_assets/figures/F03/figure.svg` | `build/publication_assets/tables/blocked_evidence.csv` | `scripts/audit_phase_a_toolchain.py` | `docs/evidence.md` |

## Global blockers

- No Vivado implementation, place-and-route, timing, or report_power.
- No production MIG pin placement or SI/PI closure.
- No board power, throughput, thermal, or EMC compliance measurement.
- No model weights are redistributed.
- No HWP is emitted without an actual HWP tool and template.
