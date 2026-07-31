# K26 / XC7K160T KiCad conditional-reference validation

> **NOT FOR FABRICATION — proposal_only**

**Date:** 2026-07-31  
**Tool:** KiCad CLI 9.0.9  
**Decision:** `XC7K160T-2FFG676I — conditionally_feasible`

## Outcome

The native KiCad sources are internally consistent within their declared
coupon scope:

| Native check | Result |
|---|---:|
| Coupon ERC | 0 errors, 0 warnings |
| Hierarchical reference ERC | 0 errors, 0 warnings |
| Coupon PCB DRC | 0 violations |
| Schematic/PCB parity | 0 issues |
| Unconnected pads reported by native DRC | 0 |

This is not a ready-to-fabricate result. The coupon intentionally replaces the
K26 SOM and XC7K160T BGA with connector/bank boundaries and ignores incomplete
ratsnest connectivity outside the explicitly routed subset. `via_dangling` is
also disabled because the source contains an unfilled internal GND-zone intent;
short, clearance, track-width, drill, outline, and parity rules remain active.

## Native source counts

| Item | Count |
|---|---:|
| Hierarchical modern schematic files | 8 |
| Coupon schematic components | 29 |
| Coupon schematic nets | 116 |
| Coupon PCB footprints | 29 |
| Coupon PCB nets including net 0 | 117 |
| Routed track segments | 65 |
| Vias | 50 |
| Zones | 1 |
| Routed GTH/refclock nets | 20 |
| Generated Gerber files | 26 |
| Drill files | 1 |
| Total exported files | 36 |

The 20 routed GTH-family nets comprise four full-duplex lanes (16
single-ended P/N nets) plus two reference-clock differential pairs (4 nets).
They are geometric connectivity routes only; no impedance, insertion loss,
skew, jitter, or eye-opening claim is made.

## Implemented hierarchy

1. K26 SOM240_2 / PL GTH bank 224 connector boundary.
2. XC7K160T-2FFG676I SelectIO/GTX bank boundary.
3. Four independent DDR3L x16 channel topology, 2GB/channel proposal.
4. Four-lane full-duplex K26-to-XC7K160T link and two refclock pairs.
5. Clock, reset, and configuration boundary.
6. Power and decoupling boundary.
7. JTAG/debug boundary.

The coupon instantiates one KiCad-library Micron 96-ball DDR3L x16 component
as a representative electrical/routing slice, DDR VREF/ZQ support, +1.35V and
+3.3V decoupling subsets, link/refclock routes, and reset/JTAG boundaries.
That representative device is not asserted to be the final 2GB-channel BOM.

## Feasibility and evidence boundary

- AMD DS987 identifies the K26 device as `XCK26-SFVC784-2LV-C/I` and exposes
  four PL-GTH TX/RX lanes plus two refclock inputs through SOM240_2:
  <https://docs.amd.com/r/en-US/ds987-k26-som/SOM240_2-Connector-Pinout>.
- AMD UG475/package files show XC7K160T FFG676 has eight 50-pin SelectIO banks
  and eight GTX lanes. The official package archive is
  <https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/k7packages/k7all.zip>.
- AMD UG586 permits multiple independent memory controllers but forbids bank
  sharing between controllers:
  <https://docs.amd.com/r/en-US/ug586_7Series_MIS/Bank-Sharing-Among-Controllers>.
- A four-controller placement is not proven until the exact memory
  organization is generated and placed by Vivado MIG for
  `XC7K160T-2FFG676I`.

No BGA ball, DQS byte group, VREF pin, address/control pin, GTX quad pin, or
MIG-generated constraint was invented in these files.

## Analyzer results and triage

The following analyzers were run: `analyze_schematic.py`,
`analyze_pcb.py --full`, `analyze_gerbers.py`, `cross_analysis.py`,
`analyze_emc.py`, and `analyze_thermal.py`.

- Schematic analyzer: 29 components, 116 nets. Its sourcing blocker and
  missing-datasheet warning are accepted blockers for a fabrication release;
  most entries are intentionally generic boundaries or proposal passives.
- PCB analyzer: reports 55 unrouted/error-class findings because the source
  contains a complete logical pin accounting while the PCB is deliberately a
  routed subset. These do not contradict native DRC because
  `unconnected_items` is explicitly outside coupon scope.
- Cross analysis: reports DDR/refclock return-path gaps and absent stitching.
  These remain genuine production-layout blockers. The internal plane is only
  a zone intent and no stackup-aware return-path design was performed.
- EMC analysis: score 67/100, with outer-layer refclock, connector filtering,
  stitching, and decoupling-via warnings. These are expected for the coupon
  but must not be waived on a carrier-board release.
- Gerber analyzer: two extent/alignment warnings result from exporting all
  auxiliary/user layers with different drawn extents. Native Edge.Cuts is a
  closed 140mm × 110mm outline and native DRC reports no geometry violation.
- Thermal analysis: skipped automatically because there is no complete
  production MPN/power dataset.

## Unresolved release gates

1. Generate four exact DDR3L x16 MIG instances and obtain a legal placed XDC.
2. Freeze a production-available DDR3L organization and MPN. Micron 8Gb x8
   `MT41K1G8` examples are obsolete; the clean 2×x8 single-rank topology is
   therefore not a frozen BOM.
3. Freeze GTX lane/quad/refclock assignments and verify K26 connector pins
   against the released DS987 revision.
4. Define data rate, encoding, AC coupling, refclock jitter, reset/training,
   link budget, stackup, 100-ohm routing, loss, skew, and eye-mask targets.
5. Complete every XC7K160T core/aux/I/O/GT rail, K26 carrier rail, sequencing,
   regulator, decoupling, thermal, and PDN requirement.
6. Complete configuration flash, JTAG chain, voltage domains, pull resistors,
   test points, protection, ESD, and manufacturing test strategy.
7. Replace every boundary placeholder with datasheet-checked symbols,
   footprints, manufacturer part numbers, and generated pin constraints.
8. Route the full board, refill planes, add stitching, rerun ERC/DRC/parity,
   SI/PI, timing closure, thermal, lifecycle, DFM, and physical validation.

## Not performed / review limits

- Vivado/MIG generation and placement: Vivado is unavailable on this host.
- SPICE: no `ngspice`, `xyce`, or `ltspice` executable is installed.
- Datasheet extraction: no project datasheet cache; pin-level correctness is
  not claimed beyond the cited AMD connector/package resource boundaries.
- Lifecycle audit: final MPNs do not exist, so a lifecycle result would be
  misleading.
- Prior-review delta: this is the first run of this new isolated reference.
- Field solver, SI/PI simulation, timing closure, fabrication review,
  assembly review, and laboratory measurement were not performed.

## Final verdict

The hierarchy and coupon are suitable as a reproducible **architectural
reference and routing experiment**. They are not a schematic release, PCB
release, or evidence that four MIG controllers place successfully.

**Fabrication readiness: blocked.  
Architecture status: conditionally feasible.**
