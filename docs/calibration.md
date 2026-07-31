# Compute-cycle calibration

The controlled analytical runs use `compute_mac_per_cycle = 64`, i.e. an
abstract 64 MAC/cycle issue rate. The current
`DecodeMatVecInt8` demo has `inputDim=16`, `outputDim=4`, and `tileDim=1`.
`LegacyMatVecSpec` directly checks its 65 request-to-done cycles boundary.

| Quantity | Analytical default | RTL demo | Ratio |
|---|---:|---:|---:|
| MACs per job | 64 | 64 | 1× |
| Accounted cycles per job | 1 | 65 | 65× |
| Effective MAC/cycle | 64.000 | 0.985 | 65× issue-rate gap |

This is a disclosure/calibration point, not a post-hoc rescaling of the
published scheduler tables. Existing reported analytical cycles retain their
original abstract issue-rate semantics. A physically meaningful latency claim
requires rerunning the model with a calibrated compute service and integrating
the currently absent memory/link response path.
