# VARP K26 memory coupon — controlled-evidence review

> **NOT FOR FABRICATION — `proposal_only`**

**Review date:** 2026-07-31

**Native tool:** KiCad CLI 9.0.9

**Automated analyzers:** KiCad skill schema 1.4.0 plus EMC analyzer
**Reviewed source:** `k26_memory_coupon.kicad_sch`, `k26_memory_coupon.kicad_pcb`,
the hierarchical `k26_memory_reference` schematic, and the checked-in Gerber
set.

## Verdict

**PASS for an internally consistent, electrically connected research coupon
and paper illustration; FAIL for fabrication readiness, pin-level
implementation, signal/power integrity, thermal, or compliance claims.**

KiCad's native gates pass: coupon ERC 0/0, hierarchical reference ERC 0/0,
coupon DRC 0 violations, schematic parity 0 issues, and native unconnected-pad
count 0. Those results apply only to the deliberately reduced connector/bank
boundary model and its relaxed proposal rules. The independent analyzers find
55 unrouted logical nets, nine return-path crossings, no ground stitching,
insufficient test access, manufacturing-rule risks, and incomplete component
provenance. These findings are fabrication blockers, not paper blockers.

## Scope and evidence classes

| Class | What is supported |
|---|---|
| Raw-file checked | 29 schematic components, 116 named schematic nets, 29 PCB footprints, 65 track segments, 50 vias, one zone, 140 × 110 mm outline, four copper layers declared |
| Native-tool checked | ERC, DRC, schematic/PCB parity, exports, and the routed-subset connectivity under the checked-in proposal rules |
| Analyzer-derived | routing completeness, geometry/DFM heuristics, cross-domain return-path findings, Gerber completeness, EMC risk heuristics |
| Source-supported feasibility | K26 connector lane availability, XC7K160T package/bank capacity, and the conditional multi-controller architecture cited in `k26_native_validation.md` |
| Inference only | actual BGA/MIG placement, production stackup, impedance, insertion loss, skew, jitter, eye margin, PDN, junction temperature, and EMC pass/fail |
| Datasheet/extraction verified | none in this analyzer run; local datasheet extraction coverage is 0% |

No analyzer score is promoted to a hardware-performance or regulatory result.

## Native gates

| Gate | Result | Artifact |
|---|---:|---|
| Coupon ERC | 0 errors, 0 warnings | `k26_reports/coupon_erc.json` |
| Hierarchical reference ERC | 0 errors, 0 warnings | `k26_reports/reference_erc.json` |
| Coupon PCB DRC | 0 violations | `k26_reports/coupon_drc.json` |
| Schematic parity | 0 issues | `k26_reports/coupon_drc.json` |
| Native unconnected pads | 0 | `k26_reports/coupon_drc.rpt` |

`scripts/verify_k26_kicad.py` reran all of these gates and returned:
`KiCad native gate: PASS (coupon ERC=0, reference ERC=0,
coupon DRC/parity=0)`.

The native DRC result does not contradict the analyzer's 55 unrouted nets:
the proposal coupon intentionally ignores incomplete ratsnest connectivity
outside the routed subset, and `via_dangling` is disabled for its unfilled
internal ground-zone intent. Clearance, shorts, width, drill, outline, and
parity rules remain active.

## Schematic and component review

The coupon contains two IC/boundary devices, four connectors, one oscillator,
18 capacitors, and four resistors. It represents one DDR3L x16 slice, four
full-duplex K26 PL-GTH lanes, two GTH reference-clock pairs, reset/config/JTAG,
and a decoupling subset.

The schematic analyzer reports 16 findings: one error, one warning, and 14
informational items. The error is a sourcing-readiness gate: only 1 of 10
unique parts has an MPN. The warning is the absence of a datasheet extraction
directory. Consequently:

- no final DDR3L density/rank/organization is asserted;
- no connector or XC7K160T ball mapping is asserted;
- no oscillator, passive tolerance, voltage rating, or package claim is
  asserted;
- symbol pin names and net labels are treated as model consistency only.

## PCB, routing, and return paths

The PCB analyzer found 29 footprints, 116 nets, 65 track segments, 50 vias,
one zone, and 1,991.51 mm of track. It reports `routing_complete=false` and 55
unrouted nets. The explicitly routed evidence is the 20 GTH/refclock
single-ended nets. DDR, rail, reset, and JTAG completeness is not established.

Fabrication blockers reported by geometry analysis:

- 0.10 mm annular rings are below the analyzer's 0.125 mm standard-process
  threshold;
- ten untented via-in-pad cases require an explicit fabrication process;
- 27 SMD parts have no front-side fiducials;
- test-point coverage is 0/116 nets;
- 55 nets are unrouted.

Cross-analysis reports nine high-speed nets crossing a modeled GND-plane gap:
DDR CK P/N, DQ0, LDQS P/N, and both GTH reference-clock P/N pairs. It also
reports no ground stitching vias. These must be fixed or disproved with a
filled-zone, stackup-aware return-path review before fabrication.

## Gerber and manufacturing review

The Gerber analyzer found all expected copper, mask, paste, silkscreen, edge,
and drill outputs: 26 Gerber files, one mixed drill file, 63 holes, 1,139
flashes, and 5,533 draws. The job file gives a 140.1 × 110.1 mm board extent.

Two alignment warnings arise because the analyzer compares the extents of
sparse copper/mask artwork with the full Edge.Cuts rectangle. Empty paste or
silkscreen on some layers naturally has a smaller extent, so this is not by
itself evidence of a shifted plot. It remains a pre-fab checkpoint: inspect
the Gerbers in an independent CAM viewer and confirm origin, outline, drill,
mask, and every copper layer.

## EMC and thermal review

The CISPR 32 Class B-oriented risk analyzer produced 26 findings and a
heuristic score of 67/100. This is **not** a compliance prediction. The main
actionable findings are:

- ten decoupling capacitors are far from their nearest modeled via;
- J5 lacks modeled EMC filtering;
- four GTH reference-clock nets are on an outer layer and near J2;
- the return-path dataset was not recognized by the EMC consumer even though
  the separate cross-analyzer found nine explicit plane-gap crossings.

The thermal analyzer ran but assessed zero components. It skipped scoring
because there are no complete MPNs, extracted thermal parameters, or
quantifiable dissipation values. No temperature or cooling claim is supported.

## Power, interfaces, and testability

The source names +1V35, +3V3, and GND rails and includes a decoupling subset,
but it does not close the full K26/XC7K160T/DDR power tree, sequencing, current,
VTT/VREF tolerance, or PDN impedance. Four GTH lanes and two reference-clock
pairs are geometrically represented only. Production work requires exact
connector/package pins, Vivado MIG placement, GTX quad/refclock assignment,
fabricator stackup, field-solved impedance, loss/jitter budgeting, and SI/PI
simulation.

JTAG and reset boundaries are present, but 0% test-point coverage means the
coupon is not a manufacturing-test design. Add rail, reset, clock, link, and
DDR observation points plus a bring-up and boundary-scan plan.

## False positives and reviewer overrides

| Analyzer output | Disposition |
|---|---|
| Native DRC says zero unconnected pads | Valid only under proposal rules; overridden for completeness by the analyzer's 55-net routing inventory |
| Gerber width/height alignment warnings | Likely sparse-layer extent behavior; retain mandatory CAM overlay check |
| EMC says return-path data unavailable | Tool-consumer limitation; separate cross-analysis provides nine deterministic RP-002 findings |
| Numerical EMC score | Checklist prioritization only; never a pass/fail or lab substitute |
| Thermal score skipped | Correct result, not a clean thermal bill of health |
| One part with MPN | Insufficient to support any board-wide part, pin, lifecycle, or sourcing claim |

## Analyses performed and skipped

Performed:

- raw source and checked-in native-report inspection;
- KiCad 9.0.9 coupon and hierarchical ERC;
- KiCad 9.0.9 coupon PCB DRC and schematic parity;
- schematic analysis;
- full PCB and proximity analysis;
- schematic/PCB cross-analysis;
- Gerber/drill analysis;
- CISPR 32 Class B-oriented EMC risk analysis;
- thermal analyzer invocation;
- deterministic project verification script.

Skipped or non-applicable:

- datasheet deep review and pin-level extraction — no datasheet cache and
  incomplete MPN coverage;
- lifecycle/distributor audit — part identity coverage is insufficient and
  no unfounded sourcing lookup was substituted;
- SPICE/PDN simulation — `ngspice` is unavailable and no closed production
  circuit model exists;
- full-wave SI/EMI and lab compliance — no production stackup, enclosure,
  cable model, or calibrated hardware;
- Vivado MIG placement/timing — exact DDR organization and BGA placement are
  unresolved;
- fabrication release — explicitly prohibited by scope.

## Delta from the prior native review

The earlier `k26_native_validation.md` established the conditional native
gate and source counts. This review adds a fresh independent analyzer run,
full/proximity PCB inspection, Gerber analysis, cross-domain return-path
checks, EMC risk analysis, thermal invocation, explicit false-positive
disposition, and a performed/skipped ledger. No source schematic or PCB edit
was made, so the native outcome is unchanged. The additional analysis makes
the incompleteness concrete: 55 unrouted nets, nine return-path crossings,
no stitching, 0% test access, incomplete MPN/datasheet coverage, and no
thermal basis.

## Required next hardware phase

1. Select production DDR3L, oscillator, connectors, passives, regulators, and
   protection parts; archive manufacturer documents and exact MPNs.
2. Generate the four-controller topology in Vivado MIG for
   `XC7K160T-2FFG676I`; assign legal BGA, byte-group, bank, GTX, and refclock
   pins.
3. Close the fabricator stackup and impedance rules, fill reference planes,
   reroute all nets, add stitching, fiducials, test points, and explicit
   via-in-pad/tenting fabrication notes.
4. Complete PDN, SI, thermal, EMC, DFM, and manufacturing-test analyses.
5. Repeat native ERC/DRC/parity, analyzer suite, independent CAM review, and
   physical bring-up before any feasibility or performance statement.
