# DRAMsim3 status

This public repository does not include a runnable DRAMsim3 adapter or a
cycle-coupled scheduler/DRAMsim3 flow. It preserves:

- four DDR3L configuration snapshots under `configs/dram/`;
- the imported four-channel statistics snapshot at
  `results/runs/dramsim3-snapshot/dramsim_stats_ch4.json`;
- a derived, explicitly bounded energy breakdown under `results/power_cost/`.

`make reproduce` does not claim to regenerate the imported DRAMsim3 snapshot.
The old experimental adapter is available only in the preserved
`archive/v10-full-evidence` history. `DRAMSIM3_ROOT` is probed for disclosure by
`make doctor`, but no sibling checkout is assumed and no DRAMsim3 performance
claim is promoted from mere tool availability.
