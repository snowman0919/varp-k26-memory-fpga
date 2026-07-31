#!/usr/bin/env python3
"""Build bounded analytical energy, DRAM-die cost, and capacity evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRICE_CSV = ROOT / "cost" / "memory_die_price_snapshot.csv"
POWER_DIR = ROOT / "results" / "power_cost"
CAPACITY_DIR = ROOT / "results" / "capacity"
ACCESS_DATE = "2026-07-31"
GIB = 1024**3


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_prices() -> list[float]:
    with PRICE_CSV.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    prices = [
        float(row["unit_package_price_usd"])
        for row in rows
        if row["included_in_cost_model"].lower() == "true"
    ]
    if len(prices) < 2 or any(price <= 0 for price in prices):
        raise ValueError("at least two positive included distributor snapshots required")
    return sorted(prices)


def build_cost() -> None:
    prices = load_prices()
    price_cases = {
        "low_snapshot": prices[0],
        "midpoint_sensitivity": sum(prices) / len(prices),
        "high_snapshot": prices[-1],
    }
    efficiency_cases = {
        "low_delivery": 0.50,
        "central_delivery": 0.70,
        "high_delivery": 0.85,
    }
    rows: list[dict] = []
    for capacity_gb, packages, ranks in [(8, 8, 1), (16, 16, 2)]:
        theoretical_gbs = 6.4  # 4 channels * x16 * 800 MT/s / 8
        for price_case, price in price_cases.items():
            for delivery_case, efficiency in efficiency_cases.items():
                physical_dies = packages * 2
                dram_cost = packages * price
                modeled_effective = theoretical_gbs * efficiency
                rows.append(
                    {
                        "architecture": f"{capacity_gb}GB_4ch_x16_{ranks}rank",
                        "capacity_gib_binary": capacity_gb,
                        "capacity_gb_decimal": f"{capacity_gb * GIB / 1e9:.3f}",
                        "channels": 4,
                        "ranks_per_channel": ranks,
                        "8gbit_x8_package_count": packages,
                        "4gbit_physical_die_count": physical_dies,
                        "price_case": price_case,
                        "delivery_case": delivery_case,
                        "unit_package_price_usd": f"{price:.2f}",
                        "imputed_physical_die_price_usd": f"{price / 2:.2f}",
                        "total_dram_package_cost_usd": f"{dram_cost:.2f}",
                        "total_imputed_physical_die_cost_usd": f"{dram_cost:.2f}",
                        "capacity_gib_per_dram_die_dollar": f"{capacity_gb / dram_cost:.6f}",
                        "capacity_gb_decimal_per_dram_die_dollar": f"{capacity_gb * GIB / 1e9 / dram_cost:.6f}",
                        "pin_rate_ceiling_gbs": f"{theoretical_gbs:.3f}",
                        "assumed_delivery_efficiency": f"{efficiency:.2f}",
                        "modeled_effective_gbs": f"{modeled_effective:.3f}",
                        "effective_gbs_per_dram_die_dollar": f"{modeled_effective / dram_cost:.6f}",
                        "evidence_type": "analytical-cost-sensitivity",
                    }
                )
    write_csv(
        ROOT / "cost" / "cost_sensitivity.csv",
        rows,
        list(rows[0]),
    )


def build_energy() -> None:
    # Scenario values are deliberately broad analytical inputs. The link central
    # case is anchored by AMD WP389's 80 mW / 3.125 Gb/s example (25.6 pJ/bit)
    # for one 7-series transceiver PMA; it is not a K26 endpoint-pair measurement.
    scenarios = [
        ("low", 1.0, 24.0, 0.80),
        ("central", 5.0, 51.2, 1.00),
        ("high", 15.0, 120.0, 1.20),
    ]
    rows: list[dict] = []
    for scenario, compute_pj_mac, link_pj_bit, dram_scale in scenarios:
        rows.extend(
            [
                {
                    "scenario": scenario,
                    "domain": "compute",
                    "category": "INT8_MAC",
                    "unit": "per_1e9_MAC",
                    "input_value": f"{compute_pj_mac:.3f}",
                    "input_unit": "pJ/MAC",
                    "energy_j": f"{compute_pj_mac * 1e-3:.9f}",
                    "evidence_type": "analytical-range",
                    "source_or_formula": "1e9 MAC * scenario pJ/MAC; no Vivado power result",
                },
                {
                    "scenario": scenario,
                    "domain": "link",
                    "category": "serialized_payload",
                    "unit": "per_GiB_transport",
                    "input_value": f"{link_pj_bit:.3f}",
                    "input_unit": "pJ/bit",
                    "energy_j": f"{link_pj_bit * 8 * GIB / 1e12:.9f}",
                    "evidence_type": "analytical-range",
                    "source_or_formula": "GiB*8*pJ/bit; coding/idle/retry must be added by trace",
                },
            ]
        )

        # Locked 4Gb x8 DDR3L-1600 DRAMsim3/Micron-derived electrical inputs.
        vdd = 1.35
        tck_ns = 1.25
        currents_ma = {
            "IDD0": 55.0,
            "IDD2N": 32.0,
            "IDD3N": 38.0,
            "IDD4W": 125.0,
            "IDD4R": 157.0,
            "IDD5AB": 235.0,
        }
        timing = {"tRAS": 28, "tRP": 11, "tRFC": 208, "burst_cycles": 4}
        dram_nominal = {
            "ACT": max(currents_ma["IDD0"] - currents_ma["IDD3N"], 0)
            * vdd
            * timing["tRAS"]
            * tck_ns,
            "PRE": max(currents_ma["IDD0"] - currents_ma["IDD2N"], 0)
            * vdd
            * timing["tRP"]
            * tck_ns,
            "READ": max(currents_ma["IDD4R"] - currents_ma["IDD3N"], 0)
            * vdd
            * timing["burst_cycles"]
            * tck_ns,
            "WRITE": max(currents_ma["IDD4W"] - currents_ma["IDD3N"], 0)
            * vdd
            * timing["burst_cycles"]
            * tck_ns,
            "REFRESH": max(currents_ma["IDD5AB"] - currents_ma["IDD2N"], 0)
            * vdd
            * timing["tRFC"]
            * tck_ns,
            "idle_precharged": currents_ma["IDD2N"] * vdd * tck_ns,
            "idle_active": currents_ma["IDD3N"] * vdd * tck_ns,
        }
        for category, energy_pj in dram_nominal.items():
            rows.append(
                {
                    "scenario": scenario,
                    "domain": "DRAM",
                    "category": category,
                    "unit": "per_command_per_x8_die"
                    if not category.startswith("idle")
                    else "per_cycle_per_x8_die",
                    "input_value": f"{dram_scale:.3f}",
                    "input_unit": "corner_multiplier",
                    "energy_j": f"{energy_pj * dram_scale / 1e12:.12f}",
                    "evidence_type": "analytical-command-model",
                    "source_or_formula": (
                        "VDD*incremental_IDD*command_cycles*tCK; "
                        "configs/dram/ddr3l_4gb_x8_1600.ini"
                    ),
                }
            )
    write_csv(
        POWER_DIR / "energy_category_model.csv",
        rows,
        list(rows[0]),
    )

    stats_path = ROOT / "results" / "runs" / "dramsim3-snapshot" / "dramsim_stats_ch4.json"
    stats = json.loads(stats_path.read_text())
    categories = {
        "ACT": "act_energy",
        "READ": "read_energy",
        "WRITE": "write_energy",
        "REFRESH": "ref_energy",
        "idle_precharged": "pre_stb_energy",
        "idle_active": "act_stb_energy",
    }
    observed: list[dict] = []
    for channel, values in sorted(stats.items(), key=lambda item: int(item[0])):
        for category, key in categories.items():
            value = values[key]
            energy_pj = sum(value.values()) if isinstance(value, dict) else value
            observed.append(
                {
                    "channel": channel,
                    "category": category,
                    "energy_pj": f"{energy_pj:.3f}",
                    "evidence_type": "DRAMsim3-simulated",
                    "source": str(stats_path.relative_to(ROOT)),
                }
            )
        observed.append(
            {
                "channel": channel,
                "category": "PRE",
                "energy_pj": "",
                "evidence_type": "not-separately-reported",
                "source": "PRE contribution is embedded in background-state accounting",
            }
        )
    write_csv(
        POWER_DIR / "dramsim3_energy_breakdown.csv",
        observed,
        list(observed[0]),
    )
    metadata = {
        "schema_version": "varp.power-cost.energy.v1",
        "generated_on": ACCESS_DATE,
        "classification": "estimated/modelled; never measured",
        "vivado_status": "blocked_missing_executable_device_files_and_license",
        "compute_model": {
            "range_pj_per_int8_mac": [1.0, 5.0, 15.0],
            "status": "sensitivity input; not an FPGA characterization",
        },
        "link_model": {
            "range_pj_per_transport_bit": [24.0, 51.2, 120.0],
            "status": "sensitivity input; not a K26-to-Kintex link measurement",
            "gemma_join_accounting": (
                "base modeled link bytes plus scheduler-specific remote-weight, "
                "activation-retransmission, and partial-sum steal overhead"
            ),
            "endpoint_multiplier": 2.0,
            "central_anchor": (
                "AMD WP389 example: 80 mW PMA at 3.125 Gb/s = 25.6 pJ/bit "
                "for one 7-series transceiver PMA; central transport scenario "
                "uses a conservative two-endpoint multiplier"
            ),
            "official_power_method": (
                "AMD UG440 XPE transceiver sheet predesign estimate; "
                "AMD UG1090 PDM early estimate and Vivado Power Report after implementation"
            ),
        },
        "dram_model": {
            "electrical_input": "configs/dram/ddr3l_4gb_x8_1600.ini",
            "range_multiplier": [0.8, 1.0, 1.2],
            "status": (
                "command-category analytical model for the locked 4Gb x8 profile; "
                "not a qualified 8Gb target-die power model"
            ),
        },
        "sources": [
            {
                "url": "https://docs.amd.com/r/en-US/ug1090-k26-thermal-design/Power-Estimation",
                "access_date": ACCESS_DATE,
                "evidence_type": "manufacturer_method",
            },
            {
                "url": "https://docs.amd.com/r/en-US/ug440-xilinx-power-estimator",
                "access_date": ACCESS_DATE,
                "evidence_type": "manufacturer_method",
            },
            {
                "url": "https://docs.amd.com/api/khub/documents/DuQSn1wHkzfV~xx8Hxb7pA/content",
                "access_date": ACCESS_DATE,
                "evidence_type": "manufacturer_example",
            },
            {
                "document": "Micron 4Gb x8 DDR3L datasheet, revision R 09/18",
                "sha256": "aa71e4a25901da402147abc017818e5d52fa214c88d73f6090c229edd558be7b",
                "evidence_type": "hashed manufacturer datasheet; bytes not redistributed",
            },
        ],
        "blocked_metrics": [
            "post-route FPGA power",
            "SAIF-calibrated compute energy",
            "implemented endpoint-pair link energy",
            "measured board energy",
            "refresh/idle-inclusive Gemma memory J/token without a command trace",
        ],
    }
    (POWER_DIR / "energy_model_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )


def build_gemma_energy_join() -> None:
    """Join the graph-derived projection ledger to bounded energy ranges.

    Memory energy is dynamic-transfer-only: an x8 BL8 READ transfers eight
    bytes per die, and one ACT/PRE pair is conservatively assigned per 1 KiB
    x8-die row. Refresh and idle/background energy remain unquantified because
    the Gemma replay has no DRAM command/timing trace.
    """

    with (ROOT / "experiments/gemma3_1b/projection_trace.csv").open(
        newline=""
    ) as handle:
        projections = list(csv.DictReader(handle))
    macs_per_token = sum(int(row["K"]) * int(row["N"]) for row in projections)
    projections_per_token = len(projections)
    with (ROOT / "results/model_level/gemma3_1b_hybrid.csv").open(
        newline=""
    ) as handle:
        hybrid = list(csv.DictReader(handle))
    with (POWER_DIR / "energy_category_model.csv").open(newline="") as handle:
        units = list(csv.DictReader(handle))

    by_scenario: dict[str, dict[tuple[str, str], float]] = {}
    for row in units:
        by_scenario.setdefault(row["scenario"], {})[
            (row["domain"], row["category"])
        ] = float(row["energy_j"])

    rows: list[dict] = []
    for hybrid_row in hybrid:
        tokens = int(hybrid_row["decode_tokens"])
        base_link_bytes_per_token = (
            int(hybrid_row["link_traffic_bytes"]) / tokens
        )
        steal_overhead_bytes_per_token = (
            int(hybrid_row["steal_overhead_traffic_bytes"]) / tokens
        )
        link_bytes_per_token = (
            base_link_bytes_per_token + steal_overhead_bytes_per_token
        )
        weight_bytes_per_token = (
            int(hybrid_row["modeled_total_int8_weight_bytes"]) / tokens
        )
        latency_s_per_token = (
            float(hybrid_row["hybrid_total_ms"]) / 1000 / tokens
        )
        for scenario in ("low", "central", "high"):
            category = by_scenario[scenario]
            compute_j = (
                macs_per_token
                / 1e9
                * category[("compute", "INT8_MAC")]
            )
            link_j = (
                link_bytes_per_token
                / GIB
                * category[("link", "serialized_payload")]
            )
            read_j = (
                weight_bytes_per_token
                / 8
                * category[("DRAM", "READ")]
            )
            rows_per_die = weight_bytes_per_token / 1024
            activate_precharge_j = rows_per_die * (
                category[("DRAM", "ACT")] + category[("DRAM", "PRE")]
            )
            memory_dynamic_j = read_j + activate_precharge_j
            total_j = compute_j + link_j + memory_dynamic_j
            rows.append(
                {
                    "scenario": hybrid_row["scenario"],
                    "scheduler": hybrid_row["scheduler"],
                    "energy_case": scenario,
                    "projection_nodes_per_token": projections_per_token,
                    "macs_per_token": macs_per_token,
                    "weight_bytes_per_token": f"{weight_bytes_per_token:.3f}",
                    "base_link_bytes_per_token": (
                        f"{base_link_bytes_per_token:.3f}"
                    ),
                    "steal_overhead_bytes_per_token": (
                        f"{steal_overhead_bytes_per_token:.3f}"
                    ),
                    "link_bytes_per_token": f"{link_bytes_per_token:.3f}",
                    "estimated_compute_j_per_token": f"{compute_j:.9f}",
                    "estimated_link_j_per_token": f"{link_j:.9f}",
                    "estimated_memory_dynamic_j_per_token": (
                        f"{memory_dynamic_j:.9f}"
                    ),
                    "estimated_total_dynamic_j_per_token": f"{total_j:.9f}",
                    "estimated_j_per_projection": (
                        f"{total_j / projections_per_token:.12f}"
                    ),
                    "hybrid_latency_s_per_token": f"{latency_s_per_token:.9f}",
                    "estimated_energy_delay_j_s": (
                        f"{total_j * latency_s_per_token:.12f}"
                    ),
                    "estimated_tokens_per_s": (
                        f"{1 / latency_s_per_token:.9f}"
                    ),
                    "evidence_type": (
                        "graph-derived-counts+hybrid-latency+analytical-energy"
                    ),
                    "memory_boundary": (
                        "dynamic READ+ACT+PRE estimate only; refresh, idle, "
                        "controller, PHY, and board power excluded; link term "
                        "includes base stream plus scheduler steal overhead"
                    ),
                }
            )
    energy_path = POWER_DIR / "gemma3_1b_energy_join.csv"
    write_csv(energy_path, rows, list(rows[0]))

    with (ROOT / "cost/cost_sensitivity.csv").open(newline="") as handle:
        costs = [
            row
            for row in csv.DictReader(handle)
            if row["capacity_gib_binary"] == "8"
            and row["delivery_case"] == "central_delivery"
        ]
    normalized: list[dict] = []
    for energy in rows:
        if energy["energy_case"] != "central":
            continue
        for cost in costs:
            dram_cost = float(cost["total_imputed_physical_die_cost_usd"])
            tokens_s = float(energy["estimated_tokens_per_s"])
            normalized.append(
                {
                    "scenario": energy["scenario"],
                    "scheduler": energy["scheduler"],
                    "price_case": cost["price_case"],
                    "dram_die_cost_usd": f"{dram_cost:.2f}",
                    "estimated_tokens_per_s": f"{tokens_s:.9f}",
                    "estimated_tokens_per_s_per_dram_die_dollar": (
                        f"{tokens_s / dram_cost:.12f}"
                    ),
                    "evidence_type": "hybrid-modeled+dram-die-cost-sensitivity",
                    "claim_boundary": (
                        "DRAM-die denominator only; excludes FPGA, PCB, "
                        "power delivery, cooling, assembly, and software cost"
                    ),
                }
            )
    write_csv(
        ROOT / "cost/gemma3_1b_cost_normalized.csv",
        normalized,
        list(normalized[0]),
    )


def build_capacity() -> None:
    model_specs = [
        {
            "model": "Gemma_3_1B",
            "params": 1_000_000_000,
            "kv_bytes_per_token": 26 * 2 * 1 * 256 * 2,
            "contexts": [4096, 32768],
            "scope": "actual_target_nominal_parameter_class",
            "source": "Google Gemma 3 model card; 32K context; config-derived KV upper bound",
        },
        {
            "model": "generic_2B_capacity_case",
            "params": 2_000_000_000,
            "kv_bytes_per_token": 32 * 1024,
            "contexts": [4096, 32768, 131072],
            "scope": "capacity_sensitivity_only",
            "source": "engineering assumption; no selected 2B model or execution",
        },
        {
            "model": "generic_3B_capacity_case",
            "params": 3_000_000_000,
            "kv_bytes_per_token": 48 * 1024,
            "contexts": [4096, 32768, 131072],
            "scope": "capacity_sensitivity_only",
            "source": "engineering assumption; no selected 3B model or execution",
        },
    ]
    rows: list[dict] = []
    for spec in model_specs:
        for quant, bits in [("INT8", 8), ("INT4", 4)]:
            weight = spec["params"] * bits / 8
            runtime_headroom = weight * 0.20 + 512 * 1024**2
            for context in spec["contexts"]:
                kv = spec["kv_bytes_per_token"] * context
                total = weight + runtime_headroom + kv
                rows.append(
                    {
                        "model_case": spec["model"],
                        "scope": spec["scope"],
                        "nominal_parameters": spec["params"],
                        "quantization": quant,
                        "context_tokens": context,
                        "weight_gib": f"{weight / GIB:.4f}",
                        "kv_bytes_per_token": spec["kv_bytes_per_token"],
                        "kv_cache_gib": f"{kv / GIB:.4f}",
                        "runtime_headroom_gib": f"{runtime_headroom / GIB:.4f}",
                        "total_budget_gib": f"{total / GIB:.4f}",
                        "fits_8gib_physical_capacity": str(total <= 8 * GIB).lower(),
                        "fits_16gib_physical_capacity": str(total <= 16 * GIB).lower(),
                        "evidence_type": "capacity-model",
                        "source_or_assumption": spec["source"],
                    }
                )
    write_csv(
        CAPACITY_DIR / "model_capacity_budget.csv",
        rows,
        list(rows[0]),
    )

    options = []
    for capacity, packages, ranks in [(8, 8, 1), (16, 16, 2)]:
        options.append(
            {
                "option": f"{capacity}GB_4ch_x16",
                "capacity_gib_binary": capacity,
                "capacity_gb_decimal": f"{capacity * GIB / 1e9:.3f}",
                "channels": 4,
                "data_width_per_channel_bits": 16,
                "ranks_per_channel": ranks,
                "8gbit_x8_dies_per_channel": 2 * ranks,
                "total_8gbit_x8_packages": packages,
                "physical_4gbit_die_count": packages * 2,
                "component_reference": "AS4C1G8D3LA-10BCN",
                "component_lifecycle": "current manufacturer catalog; distributor Active at DigiKey",
                "component_status": "cost-model candidate; MIG qualification unresolved",
                "package_internal_organization": "two_4gbit_x4_dies_stacked_as_one_x8_rank",
                "pin_rate_ceiling_mts": 800,
                "aggregate_pin_rate_ceiling_gbs": "6.400",
                "bandwidth_effect_of_second_rank": "capacity_only; no added channel bandwidth",
                "implementation_status": "blocked_missing_Vivado_MIG_placement_timing",
                "evidence_type": "datasheet-plus-capacity-arithmetic",
            }
        )
    write_csv(
        CAPACITY_DIR / "memory_scaling_options.csv",
        options,
        list(options[0]),
    )


def main() -> int:
    build_cost()
    build_energy()
    build_gemma_energy_join()
    build_capacity()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
