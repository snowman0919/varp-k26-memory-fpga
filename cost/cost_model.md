# DRAM-die-only cost model

Snapshot date: 2026-07-31

## Scope

The price boundary contains only DDR3L memory components. It excludes the K26
SOM, Memory FPGA, PCB, connectors, regulators, assembly, freight, tax, engineering
labor, and every other system cost. Therefore none of the tables can be called an
accelerator price, product BOM, or system price.

The purchasable comparison part is Alliance Memory
`AS4C1G8D3LA-10BCN`: 8 Gb, 1G×8, 1.35 V DDR3L in a 78-ball dual-die package.
The [manufacturer product page](https://www.alliancememory.com/as4c1g8d3la/)
still lists the commercial, industrial, and automotive variants. The
[manufacturer datasheet](https://www.alliancememory.com/wp-content/uploads/pdf/ddr3/AllianceMemory_DDR3L_8G_AS4C1G8D3LA-10BCN-BIN-BAN_Feb2019_v1.0.pdf)
defines organization and electrical behavior. Listing is evidence of current
catalog presence, not a longevity guarantee.

Two authorized-distributor quantity-1 observations are retained:

- [DigiKey](https://www.digikey.com/en/products/detail/alliance-memory-inc/AS4C1G8D3LA-10BCN/10222124):
  USD 97.10, 667 units shown, Active, manufacturer lead time 40 weeks.
- [Mouser](https://www.mouser.com/ProductDetail/Alliance-Memory/AS4C1G8D3LA-10BCN?qs=unwgFEO1A6tj9PoTtfUwww%3D%3D):
  USD 39.32, 425 units shown, estimated factory lead time 8 weeks. The page did
  not expose a distinct lifecycle field.

Price and stock are volatile snapshots. Recheck immediately before procurement.
`MT41K1G8TRF-125:E` remains an explicitly obsolete Micron topology reference and
is excluded from every cost result.

The distributor price is for one packaged component, not for a bare silicon die.
The Alliance 8 Gb package contains two physical 4 Gb dies. Accordingly, the CSV
retains both package price and an imputed physical-die price (package price ÷ 2).
The latter is normalization arithmetic, not a separately purchasable die quote.
The manufacturer datasheet identifies the two stacked dies as x4 devices that
jointly expose one x8 interface and one package-level chip-select; the package is
therefore modeled as one rank, not two independently selectable ranks.

## Topologies

The 8 GiB baseline (8.590 decimal GB) uses four x16 channels. Each channel has
two 8 Gb ×8 devices
forming one x16 rank: eight packages and sixteen physical dies total. The
16 GiB (17.180 decimal GB) capacity option adds a second such rank to each
channel: sixteen packages and
thirty-two physical dies total. The second rank adds
capacity, not channels or pin bandwidth. Both topologies remain conditional
until four MIG instances, rank control, pin placement, and timing close in
Vivado.

The 6.4 GB/s number is an arithmetic pin-rate ceiling:

`4 channels × 16 bits × 800 MT/s ÷ 8 = 6.4 GB/s`.

It is neither measured nor an effective payload bandwidth. The sensitivity file
applies 0.50/0.70/0.85 delivery factors only to expose the denominator's effect;
these are analytical assumptions, not measured efficiencies.

## Price sensitivity

`cost_sensitivity.csv` independently crosses:

- low/midpoint/high package prices (two observations plus their midpoint); and
- 0.50/0.70/0.85 assumed payload-delivery efficiencies.

The reported metrics include both binary GiB and decimal GB per DRAM-die dollar,
plus modeled effective GB/s per DRAM-die dollar.
`gemma3_1b_cost_normalized.csv` additionally divides the hybrid-modeled Gemma
token rate by the low/midpoint/high 8 GiB DRAM-package cost. The delivery-factor
dimension is intentionally omitted from that table because the current hybrid
latency does not depend on the assumed effective-bandwidth sensitivity; keeping
it would duplicate each token-rate row three times. This is a
hybrid-modeled-token/s per DRAM-package-dollar denominator, not measured
throughput, energy efficiency, accelerator price, or total cost/benefit.

## Claim boundary

The topology tables are `analytical-cost-sensitivity`; the Gemma-normalized table
is `hybrid-modeled+dram-die-cost-sensitivity`. They are not quotes, purchase
orders, total BOMs, or measured cost/benefit. FPGA pricing is absent by design.
