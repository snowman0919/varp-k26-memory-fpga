# VARP K26 memory-FPGA research artifact

VARP is an evidence-bounded study of locality-aware work stealing for an
on-device Gemma 3 1B accelerator candidate built around Kria K26 compute and a
multi-channel memory FPGA.

![Implemented compute path, analytical service boundary, and blocked physical integration](paper/final/figures/paper_f01_evidence_path.svg)

## Scope and result

The repository connects a hashed ONNX graph inventory to a projection-job
ledger, an analytical scheduler model, bounded SpinalHDL/Verilator evidence,
and native KiCad proposal sources. Under the disclosed full-overlap analytical
model, locality-aware S3 lowers p95 versus static S1 by 18.12% for skew and
17.59% for mixed workloads. These are modeled scheduler results—not measured
accelerator speedups.

| Plane | Implemented boundary | Evidence |
|---|---|---|
| Compute | `TileJob + payload → scheduler → payload store → 16×4 INT8 MatVec → result` | RTL simulated, bounded exact-once tests |
| Memory | external request → channel ingress → bank-aware queue → command | RTL command plane; no PHY or response path |
| Link | external input → bundle router → output bundle | RTL routing plane; no GT wrapper or returned payload |
| Physical | KiCad hierarchy and validation coupon | native proposal checks; **NOT FOR FABRICATION** |

There is no implemented `scheduler → DMA → DDR/link response → weight FIFO →
MatVec` loop. The analytical default of 64 MAC/cycle is also not the issue rate
of the shipped primitive, which completes 64 MACs in 65 request-to-done cycles.

## Quick start

Prerequisites: Python 3.11+, Java 21, sbt, Verilator, KiCad 9 CLI, Pandoc,
Chromium/Chrome, Poppler, ffmpeg, and Noto CJK fonts.

```bash
make setup
make reproduce
```

Focused commands:

```bash
make test                 # Python and repository contracts
make rtl-test             # eight bounded RTL suites
make publication-index    # figures, flows, slides, and visual QA
make paper                # submission and extended report
make release              # deterministic source/evidence/paper archives
make clean-rtl            # target/ and simWorkspace/
make distclean            # all ignored build and RTL output
```

`make model-trace` is the only target that needs an authorized local Gemma 3
1B ONNX artifact via `GEMMA3_1B_ONNX_DIR`. It reads the artifact in place and
does not redistribute model weights.

## Paper and evidence

- [Submission manuscript](paper/final/submission_manuscript.pdf)
- [Extended technical report](paper/technical_report/technical_report.pdf)
- [Architecture and missing loop](docs/architecture.md)
- [Python/RTL semantic contract](docs/model_rtl_contract.md)
- [Analytical-to-RTL calibration](docs/calibration.md)
- [Claim and evidence boundaries](docs/evidence.md)
- [DRAMsim3 snapshot boundary](docs/dramsim3.md)

Canonical data live in `data/publication/`; generated visual and release files
go only below `build/`. Source archives include `source_manifest.txt`, so their
contracts remain testable without `.git` metadata.

## Rights and history

This is deliberately source-available research evidence, not an OSI-approved
open-source release. See [LICENSE](LICENSE), [AUTHORS.md](AUTHORS.md), and
[CITATION.cff](CITATION.cff). The complete historical evidence snapshot remains
at tag `v10-final` and branch `archive/v10-full-evidence` in the archival
repository.
