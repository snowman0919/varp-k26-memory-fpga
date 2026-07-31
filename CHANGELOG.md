# Changelog

## v10-submission-ready — 2026-08-01

### Release closure

- Corrected public metadata and added a reviewer-oriented landing page.
- Added GitHub auto-ZIP fallback testing alongside checksum-bound Source ZIP
  reproduction.
- Added a 10-minute presentation, Manim animations, Korean study pack, and
  claim-to-evidence release index.
- Kept analytical, hybrid, estimated, RTL, and KiCad-native evidence labels
  explicit throughout all public materials.

## 2.0.0 — public-repository cleanup

- Preserved the complete v10 evidence snapshot on `v10-final` and
  `archive/v10-full-evidence`.
- Removed revision history, rendered publication variants, raw VCD, fabrication
  exports, GUI/plugin code, and G00–G10 legacy paths from the main line.
- Restored canonical publication CSV inputs and moved all rendered output to
  ignored `build/` directories.
- Added a real `make reproduce`, deterministic release target, CI, and public
  repository contract tests.
- Documented the three independent RTL planes, absent end-to-end DDR/link data
  loop, Python/RTL scheduling mismatch, 65-cycle MatVec calibration, and
  non-runnable DRAMsim3 boundary.

## v10-final — 2026-07-31

- Added graph-derived Gemma 3 1B projection and deterministic token traces.
- Added S0-physical and offline Oracle analytical comparisons.
- Added bounded actual-weight RTL parity for three representative projections.
- Added scheduler-to-real-MatVec temporal waveform evidence.
- Added bounded power, DRAM energy, capacity, and memory-die cost models.
- Added a controlled KiCad/native/EMC/thermal evidence review.
- Added publication figures, editable flows, animation, paper, report, and
  presentation packages.
- Added evidence manifests, deterministic release archives, and clean-clone
  reproduction gates.
