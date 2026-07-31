from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PowerCostEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            ["python3", "scripts/audit_phase_a_toolchain.py"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["python3", "scripts/build_power_cost_evidence.py"],
            cwd=ROOT,
            check=True,
        )

    def read_csv(self, relative: str) -> list[dict[str, str]]:
        with (ROOT / relative).open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_two_current_distributor_snapshots_and_no_fpga_price(self) -> None:
        rows = self.read_csv("cost/memory_die_price_snapshot.csv")
        included = [row for row in rows if row["included_in_cost_model"] == "true"]
        self.assertGreaterEqual(len({row["distributor"] for row in included}), 2)
        self.assertTrue(all(float(row["unit_package_price_usd"]) > 0 for row in included))
        self.assertTrue(all(row["physical_dies_per_package"] == "2" for row in included))
        all_text = (ROOT / "cost/cost_model.md").read_text().lower()
        self.assertNotIn("fpga_price", all_text)
        self.assertIn("fpga pricing is absent", all_text)

    def test_cost_model_is_dram_die_only_and_monotonic(self) -> None:
        rows = self.read_csv("cost/cost_sensitivity.csv")
        self.assertEqual(len(rows), 18)
        for capacity in ("8", "16"):
            subset = [row for row in rows if row["capacity_gib_binary"] == capacity]
            costs = sorted(float(row["total_dram_package_cost_usd"]) for row in subset)
            self.assertEqual(costs, sorted(costs))
            self.assertTrue(all(row["evidence_type"] == "analytical-cost-sensitivity" for row in subset))
            self.assertEqual(len({row["price_case"] for row in subset}), 3)
            self.assertEqual(len({row["delivery_case"] for row in subset}), 3)
        eight_mid = next(
            row for row in rows
            if row["capacity_gib_binary"] == "8"
            and row["price_case"] == "midpoint_sensitivity"
            and row["delivery_case"] == "central_delivery"
        )
        sixteen_mid = next(
            row for row in rows
            if row["capacity_gib_binary"] == "16"
            and row["price_case"] == "midpoint_sensitivity"
            and row["delivery_case"] == "central_delivery"
        )
        self.assertAlmostEqual(
            float(sixteen_mid["total_dram_package_cost_usd"]),
            2 * float(eight_mid["total_dram_package_cost_usd"]),
            places=2,
        )

    def test_energy_categories_and_evidence_boundary(self) -> None:
        rows = self.read_csv("results/power_cost/energy_category_model.csv")
        categories = {(row["domain"], row["category"]) for row in rows}
        for category in ("ACT", "PRE", "READ", "WRITE", "REFRESH", "idle_precharged", "idle_active"):
            self.assertIn(("DRAM", category), categories)
        self.assertIn(("compute", "INT8_MAC"), categories)
        self.assertIn(("link", "serialized_payload"), categories)
        self.assertTrue(all(float(row["energy_j"]) >= 0 for row in rows))
        metadata = json.loads(
            (ROOT / "results/power_cost/energy_model_metadata.json").read_text()
        )
        self.assertEqual(
            metadata["vivado_status"],
            "blocked_missing_executable_device_files_and_license",
        )
        self.assertIn("never measured", metadata["classification"])

    def test_gemma_energy_and_cost_join_remains_bounded(self) -> None:
        energy = self.read_csv(
            "results/power_cost/gemma3_1b_energy_join.csv"
        )
        self.assertEqual(
            {row["energy_case"] for row in energy},
            {"low", "central", "high"},
        )
        self.assertEqual(
            {row["scheduler"] for row in energy},
            {"S0", "S0-physical", "S1", "S2", "S3", "Oracle"},
        )
        for row in energy:
            self.assertAlmostEqual(
                float(row["link_bytes_per_token"]),
                float(row["base_link_bytes_per_token"])
                + float(row["steal_overhead_bytes_per_token"]),
                places=3,
            )
            components = sum(
                float(row[key])
                for key in (
                    "estimated_compute_j_per_token",
                    "estimated_link_j_per_token",
                    "estimated_memory_dynamic_j_per_token",
                )
            )
            self.assertAlmostEqual(
                components,
                float(row["estimated_total_dynamic_j_per_token"]),
                places=8,
            )
            self.assertIn("refresh, idle", row["memory_boundary"])
            self.assertNotIn("measured", row["evidence_type"])
        s0 = next(
            row for row in energy
            if row["scenario"] == "batch1_decode32"
            and row["scheduler"] == "S0"
            and row["energy_case"] == "central"
        )
        s3 = next(
            row for row in energy
            if row["scenario"] == "batch1_decode32"
            and row["scheduler"] == "S3"
            and row["energy_case"] == "central"
        )
        self.assertEqual(float(s0["steal_overhead_bytes_per_token"]), 0.0)
        self.assertGreater(float(s3["steal_overhead_bytes_per_token"]), 0.0)
        self.assertGreater(
            float(s3["estimated_link_j_per_token"]),
            float(s0["estimated_link_j_per_token"]),
        )
        normalized = self.read_csv(
            "cost/gemma3_1b_cost_normalized.csv"
        )
        self.assertEqual(len(normalized), 36)
        self.assertNotIn("delivery_case", normalized[0])
        self.assertEqual(
            len(
                {
                    (
                        row["scenario"],
                        row["scheduler"],
                        row["price_case"],
                    )
                    for row in normalized
                }
            ),
            len(normalized),
        )
        self.assertTrue(
            all(
                "DRAM-die denominator only" in row["claim_boundary"]
                for row in normalized
            )
        )

    def test_capacity_invariants_and_no_execution_claim(self) -> None:
        rows = self.read_csv("results/capacity/model_capacity_budget.csv")
        self.assertEqual({row["quantization"] for row in rows}, {"INT8", "INT4"})
        self.assertEqual(
            {row["model_case"] for row in rows},
            {"Gemma_3_1B", "generic_2B_capacity_case", "generic_3B_capacity_case"},
        )
        for row in rows:
            self.assertGreater(float(row["total_budget_gib"]), 0)
            if row["model_case"] != "Gemma_3_1B":
                self.assertEqual(row["scope"], "capacity_sensitivity_only")
                self.assertIn("no selected", row["source_or_assumption"])
        options = self.read_csv("results/capacity/memory_scaling_options.csv")
        self.assertEqual([row["total_8gbit_x8_packages"] for row in options], ["8", "16"])
        self.assertEqual([row["physical_4gbit_die_count"] for row in options], ["16", "32"])
        self.assertTrue(
            all("one_x8_rank" in row["package_internal_organization"] for row in options)
        )
        self.assertTrue(
            all(row["aggregate_pin_rate_ceiling_gbs"] == "6.400" for row in options)
        )

    def test_doctor_has_every_requested_tool_and_evidence_type(self) -> None:
        doctor = json.loads((ROOT / "build/doctor/DOCTOR.json").read_text())
        requested = {
            "Java", "Scala", "sbt", "SpinalHDL", "Verilator", "DRAMsim3",
            "Python", "ONNX", "ONNX Runtime", "Vivado", "Vivado device files",
            "Vivado license", "KiCad", "kicad-cli", "GTKWave", "Graphviz",
            "ffmpeg", "ImageMagick", "Pandoc", "LibreOffice", "python-pptx",
            "PptxGenJS", "gh CLI", "Git LFS",
        }
        self.assertEqual(set(doctor["tools"]), requested)
        self.assertTrue(
            all(item["evidence_type"] for item in doctor["tools"].values())
        )
        self.assertEqual(doctor["tools"]["Vivado"]["status"], "missing")
        self.assertEqual(doctor["tools"]["Vivado license"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
