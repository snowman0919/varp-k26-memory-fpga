# Evidence classes

| Class | Examples | Supports | Does not support |
|---|---|---|---|
| Direct source | model hashes, native KiCad files, controlled ledgers | provenance and declared structure | execution performance |
| RTL simulated | scheduler/MatVec tests, event CSV, tile parity | bounded functional behavior | board timing or throughput |
| Analytical/hybrid | scheduler tables, capacity, energy/cost arithmetic | comparisons under stated assumptions | measured acceleration or power |
| Imported snapshot | DRAMsim3 statistics | preserved prior run only | public end-to-end regeneration |
| Blocked | Vivado, MIG, SI/PI, thermal, EMC | future acceptance gates | any positive physical claim |

Every public claim must keep its qualifier. A KiCad ERC/limited-DRC pass is not
fabrication readiness. An available executable is not evidence that the design
ran through it. Model weights are never part of Git or release archives.
