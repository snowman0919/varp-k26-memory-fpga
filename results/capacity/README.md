# 8 GB / 16 GB capacity analysis

`model_capacity_budget.csv` is a capacity model. It is not execution evidence.

The Gemma 3 1B row uses the nominal 1B parameter class and the official 32K
context limit. The KV upper bound uses the inspected text configuration
(26 layers, one KV head, 256 head dimension, BF16 K and V):

`26 × 1 × 256 × 2 bytes × 2(K,V) = 26 KiB/token`.

The generic 2B and 3B rows are deliberately named capacity cases. Their 32 and
48 KiB/token values are engineering sensitivities, not attributes of a selected
or executed model. INT8 and INT4 weight bytes are nominal parameter-count
arithmetic. Runtime headroom is 20% of weight storage plus 512 MiB.

`memory_scaling_options.csv` compares four-channel x16 topologies. The 8 GiB
(8.590 decimal GB) option uses eight 8Gb x8 dual-die packages; the 16 GiB
(17.180 decimal GB) option uses sixteen.
Their physical 4Gb die counts are therefore 16 and 32. A second rank doubles
capacity but does not increase the four-channel 6.4 GB/s arithmetic pin-rate
ceiling. Four-MIG and two-rank placement/timing remain blocked without Vivado.
The manufacturer's dual-die package uses two stacked x4 dies to expose one x8
package interface with one chip-select, so each package is one rank for this
capacity arithmetic.

Gemma 3 1B is the only actual target. No row claims a 2B or 3B run.
