from __future__ import annotations

import re
import hashlib
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source_inventory() -> list[str]:
    """Read source paths in Git, release-archive, or GitHub auto-ZIP mode."""
    git_dir = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if git_dir.returncode == 0 and git_dir.stdout.strip() == "true":
        return subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    manifest = ROOT / "source_manifest.txt"
    if manifest.is_file():
        return [
            line.split("  ", 1)[1]
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # GitHub's automatic Download ZIP has neither .git nor the official
    # release-only source_manifest.txt. Its payload is the repository tree, so
    # enumerate that tree while excluding generated/cache roots.
    ignored_roots = {
        ".git", ".venv", "build", "target", "simWorkspace",
        "__pycache__", ".pytest_cache", ".mypy_cache",
    }
    return sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in ignored_roots for part in path.parts)
    )


class PublicRepositoryContractTest(unittest.TestCase):
    def test_public_targets_exist(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        for target in ("setup", "test", "rtl-test", "publication-index",
                       "paper", "reproduce", "reproduce-paper", "release",
                       "source-archive-test", "github-archive-test",
                       "clean-rtl", "distclean"):
            self.assertRegex(makefile, rf"(?m)^{re.escape(target)}:")

    def test_publication_sources_are_complete(self) -> None:
        required = {
            "k26_bottleneck_counters.csv",
            "k26_channel_link_matrix.csv",
            "k26_design_decisions.csv",
            "k26_kicad_status.csv",
            "k26_one_factor_summary.csv",
            "k26_research_flow.csv",
            "k26_scheduler_policies.csv",
            "k26_scheduler_summary.csv",
            "k26_steal_tradeoff.csv",
            "k26_system_architecture.csv",
        }
        present = {path.name for path in (ROOT / "data/publication").glob("*.csv")}
        self.assertEqual(present, required)

    def test_generated_and_legacy_trees_are_not_tracked(self) -> None:
        tracked = source_inventory()
        forbidden = (
            "publication_assets/", "paper/revisions/",
            "paper/reviews/", "hardware/kicad/k26_exports/",
            "hw/src/main/scala/varp/cosim/", "src/varp/g10",
        )
        self.assertFalse([path for path in tracked if path.startswith(forbidden)])

    def test_source_archive_manifest_integrity(self) -> None:
        manifest = ROOT / "source_manifest.txt"
        if not manifest.is_file():
            self.skipTest("Git worktree mode; release manifest is archive-only")
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_model_rtl_mismatch_and_cycle_calibration_are_disclosed(self) -> None:
        contract = (ROOT / "docs/model_rtl_contract.md").read_text(encoding="utf-8")
        calibration = (ROOT / "docs/calibration.md").read_text(encoding="utf-8")
        for token in ("home_cluster", "jobId % clusterCount", "queue heads only",
                      "at most one job per clock edge"):
            self.assertIn(token, contract)
        for token in ("64 MAC/cycle", "65 request-to-done cycles", "65×"):
            self.assertIn(token, calibration)

    def test_architecture_separates_closed_logical_and_open_physical_paths(self) -> None:
        architecture = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
        self.assertIn("ClosedLoopVirtualPrototypeTop", architecture)
        self.assertIn("닫힌 논리 데이터 경로", architecture)
        self.assertIn("GT serializer", architecture)
        self.assertIn("MIG", architecture)
        self.assertIn("NOT FOR FABRICATION", architecture)

    def test_release_and_paper_portability_guards(self) -> None:
        release = (ROOT / "scripts/build_release.py").read_text(encoding="utf-8")
        paper = (ROOT / "paper/final/build_paper.py").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("source_manifest.txt", release)
        self.assertIn("VARP_K26_Source.zip", release)
        self.assertIn("BROWSER_TIMEOUT_SECONDS = 180", paper)
        self.assertIn('re.sub(rb"node\\d{8}"', paper)
        self.assertIn("preserving their fixed width", paper)
        self.assertIn("scripts/verify_clean_source.py", makefile)

    def test_durable_public_paths_replace_stage_names(self) -> None:
        tracked = source_inventory()
        stale_prefixes = (
            "paper" + "10_tools/",
            "configs/dram/" + "g10_",
            "results/runs/" + "g06-",
            "scripts/build_" + "paper10_",
        )
        self.assertFalse(
            [path for path in tracked if path.startswith(stale_prefixes)]
        )
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for stale in ("inputs/" + "g10", "paper/submission/reviews", "inputs/legacy_paper"):
            self.assertNotIn(stale, attributes)

    def test_public_metadata_and_auto_zip_contract(self) -> None:
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("https://github.com/snowman0919/varp-k26-memory-fpga", citation)
        self.assertNotIn("varp-k26-memory-fpga-" + "paper10", citation)
        self.assertIn("자동 **Download ZIP**", readme)
        self.assertIn("`VARP_K26_Source.zip`", readme)

    def test_paper_contains_onnx_flow_and_native_kicad_render(self) -> None:
        manuscript = (ROOT / "paper/final/submission_manuscript.md").read_text(
            encoding="utf-8"
        )
        generator = (
            ROOT / "publication_tools/generate_publication_and_presentation.py"
        ).read_text(encoding="utf-8")
        for token in (
            "7,837개 노드",
            "paper_f02_onnx_runtime_graph.svg",
            "paper_f07_kicad_coupon_render.png",
            "hardware/kicad",
        ):
            self.assertIn(token, manuscript)
        render = ROOT / "paper/final/figures/paper_f07_kicad_coupon_render.png"
        self.assertGreater(render.stat().st_size, 500_000)
        self.assertIn("Reuse the reviewed native render", generator)
        self.assertNotIn('"kicad-cli", "pcb", "render"', generator)


if __name__ == "__main__":
    unittest.main()
