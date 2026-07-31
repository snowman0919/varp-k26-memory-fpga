# Bounded power and energy evidence

This directory contains energy **models**, not power measurements.

- `energy_category_model.csv` separates compute, serialized-link, and DDR3L
  command/background categories across low, central, and high scenarios.
- `dramsim3_energy_breakdown.csv` preserves the existing four-channel DRAMsim3
  run's simulated breakdown. DRAMsim3 does not report PRE as an independent
  energy bucket, so PRE is blank rather than fabricated.
- `gemma3_1b_energy_join.csv` joins graph-derived projection/MAC/byte counts
  and hybrid latency to low/central/high energy inputs. Its memory column is
  dynamic READ+ACT+PRE only; refresh, idle, controller, PHY, and board power
  remain excluded. Its link column includes the base modeled transport plus
  scheduler-specific remote-weight, activation-retransmission, and partial-sum
  steal overhead.
- `energy_model_metadata.json` records formula inputs, sources, evidence types,
  and blocked metrics.

Compute is normalized per billion INT8 MACs and link energy per GiB transported.
DRAM categories are normalized per command per x8 die or per idle clock. The
Gemma join supplies MAC, transported-byte, weight-byte, and hybrid elapsed-time
counts. It therefore reports an explicitly estimated dynamic J/token,
J/projection, and energy-delay range. A refresh/idle-inclusive memory or board
J/token remains blocked because the scheduler replay is not a DRAM command
trace.

Vivado, device files, and licensing are absent. There is no synthesis,
place-and-route, SAIF/VCD-based Vivado power analysis, or `report_power`.
Every modeled number must retain the `estimated`, `modeled`, or
`analytical-range` label.
