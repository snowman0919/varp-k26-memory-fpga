# VARP K26–Memory FPGA Accelerator

VARP studies locality-aware work stealing for an on-device Gemma 3 1B
accelerator candidate built around Kria K26 compute and a multi-channel memory
FPGA. **This is a research artifact. Results are analytical/model/hybrid unless
explicitly marked otherwise.**

![Implemented compute path, analytical service boundary, and blocked physical integration](paper/final/figures/paper_f01_evidence_path.svg)

## What is implemented

The repository connects a hash-bound ONNX graph inventory to a projection-job
ledger, an analytical scheduler model, bounded SpinalHDL/Verilator RTL evidence,
and native KiCad proposal sources.

| Plane | Implemented boundary | Evidence |
|---|---|---|
| Compute | `TileJob + payload → scheduler → payload store → 16×4 INT8 MatVec → result` | RTL simulated, bounded exact-once tests |
| Memory | external request → channel ingress → bank-aware queue → command | RTL command plane; no PHY or response path |
| Link | external input → bundle router → output bundle | RTL routing plane; no GT wrapper or returned payload |
| Physical | KiCad hierarchy and validation coupon | native proposal checks; **NOT FOR FABRICATION** |

## Key results

Under the disclosed full-overlap analytical model, locality-aware S3 lowers p95
versus static S1 by **18.12% for skew** and **17.59% for mixed** workloads. These
are modeled scheduler results—not measured accelerator speedups. Three actual
Gemma weight tiles match the bounded INT32 RTL references; native KiCad checks
pass only within the declared proposal/coupon scope.

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

`make model-trace` is the only target that needs an authorized local Gemma 3 1B
ONNX artifact via `GEMMA3_1B_ONNX_DIR`; model weights are never redistributed.

GitHub's automatic **Download ZIP** supports `make test` and
`make publication-index`. For checksum-bound full reproduction, use the
official Release `VARP_K26_Source.zip`, which contains `source_manifest.txt`.

## Documents

- [Submission manuscript](paper/final/submission_manuscript.pdf)
- [Extended technical report](paper/technical_report/technical_report.pdf)
- [10-minute presentation](presentation/final/presentation.pptx)
- [Presentation PDF](presentation/final/presentation.pdf)
- [Speaker notes](presentation/final/speaker_notes.md)
- [Slide source index](presentation/final/slide_source_index.md)
- [Slide contact sheet](presentation/final/slide_contact_sheet.png)
- [Independent presentation review](presentation/final/independent_review.md)
- [Work Stealing MP4](presentation/final/assets/work_stealing_sequence.mp4) / [GIF](presentation/final/assets/work_stealing_sequence.gif)
- [Study pack](study/study_pack.pdf)
- [Evidence index](release/evidence_index.md)
- [Architecture and missing loop](docs/architecture.md)
- [Python/RTL semantic contract](docs/model_rtl_contract.md)
- [Analytical-to-RTL calibration](docs/calibration.md)

## Repository layout

| Path | Purpose |
|---|---|
| `hw/`, `src/`, `tests/` | bounded RTL, analytical model, and contracts |
| `experiments/`, `results/`, `evidence/` | graph-derived, modeled, and RTL evidence |
| `hardware/kicad/` | reference hierarchy and validation coupon |
| `paper/`, `presentation/final/`, `study/` | submission and defense materials |
| `release/` | deterministic public release set and checksums |

## Scope and limitations

There is no implemented `scheduler → DMA → DDR/link response → weight FIFO →
MatVec` loop. The analytical 64 MAC/cycle default is not the shipped primitive's
issue rate: that primitive completes 64 MACs in 65 request-to-done cycles. This
repository does not claim board-measured performance, DDR/link payload
bandwidth, complete 3B execution, SI/PI closure, or fabrication readiness.

## Citation

Use [CITATION.cff](CITATION.cff): CHOI YUNHYUK, Korea Digital Media High
School, ORCID [0009-0006-3537-0249](https://orcid.org/0009-0006-3537-0249).

## License

This is deliberately source-available research evidence, not an OSI-approved
open-source release. See [LICENSE](LICENSE) and [AUTHORS.md](AUTHORS.md).
