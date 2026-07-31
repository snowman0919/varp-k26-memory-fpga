#!/usr/bin/env python3
"""Build the VARP K26 evidence index and deterministic release archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterable
import zipfile

from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


rl_config.invariant = 1

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "build" / "evidence"
RELEASE = ROOT / "build" / "release"

RECORDS = (
    (
        "E01",
        "experiments/gemma3_1b/trace_manifest.json",
        "graph-derived + analytical",
        "Hashed ONNX graph/token ledger and replay provenance",
        "End-to-end model execution or hardware latency",
    ),
    (
        "E02",
        "experiments/gemma3_1b/projection_trace.csv",
        "graph-derived",
        "183 dense projection nodes and source tensor geometry",
        "Measured execution time",
    ),
    (
        "E03",
        "evidence/model/gemma3_1b_rtl_tile_parity.csv",
        "RTL-simulated bounded extract",
        "Three actual-weight 16x4 INT8 tiles match software references",
        "Full-model RTL inference or global quantization accuracy",
    ),
    (
        "E04",
        "evidence/waveforms/work_stealing_events.csv",
        "RTL-simulated",
        "Scheduler-to-real-MatVec event timeline for the bounded case",
        "System throughput or board timing",
    ),
    (
        "E05",
        "results/experiments/scheduler_controlled.csv",
        "analytical model",
        "Controlled six-policy comparisons across five seeds and three runs",
        "RTL cycle performance or physical speedup",
    ),
    (
        "E06",
        "results/model_level/gemma3_1b_hybrid.csv",
        "hybrid modeled",
        "Projection-model plus disclosed host fallback arithmetic",
        "Measured end-to-end accelerator latency",
    ),
    (
        "E07",
        "results/power_cost/energy_category_model.csv",
        "estimated energy",
        "Compute/link/DRAM energy sensitivity ranges",
        "Vivado or board power",
    ),
    (
        "E08",
        "cost/cost_sensitivity.csv",
        "current price snapshot + arithmetic",
        "Memory-package/die cost sensitivity only",
        "Full FPGA/board/system price",
    ),
    (
        "E09",
        "hardware/kicad/k26_reports/k26_scope_manifest.json",
        "native KiCad",
        "Internal proposal-coupon ERC/DRC/parity status",
        "Fabrication readiness, SI/PI, or compliance",
    ),
    (
        "E10",
        "hardware/kicad/controlled_review.md",
        "controlled review",
        "Native and analyzer findings with explicit overrides",
        "Production pinout, thermal closure, or EMC pass",
    ),
    (
        "E11",
        "docs/toolchain/COMPATIBILITY_MATRIX.md",
        "toolchain contract",
        "Required tools and explicit missing-tool consequences",
        "Host-specific tool availability or successful design execution",
    ),
    (
        "E12",
        "build/publication_assets/validation_report.json",
        "asset QA",
        "Figure/flow/presentation asset validation",
        "Scientific validation of the underlying models",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_records() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for identifier, relative, evidence_type, allowed, forbidden in RECORDS:
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        rows.append(
            {
                "id": identifier,
                "path": relative,
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
                "evidence_type": evidence_type,
                "allowed_interpretation": allowed,
                "forbidden_interpretation": forbidden,
            }
        )
    if missing:
        raise RuntimeError("missing required evidence: " + ", ".join(missing))
    return rows


def write_index(rows: list[dict[str, object]]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lines = [
        "# VARP K26 evidence index",
        "",
        "This index separates direct, simulated, analytical, hybrid, and blocked "
        "claims. Hashes bind every entry to the release snapshot.",
        "",
        "| ID | Evidence type | Artifact | Supported | Forbidden |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['evidence_type']} | `{row['path']}` | "
            f"{row['allowed_interpretation']} | {row['forbidden_interpretation']} |"
        )
    lines.extend(
        [
            "",
            "## Global blockers",
            "",
            "- No Vivado implementation, place-and-route, timing, or report_power.",
            "- No production MIG pin placement or SI/PI closure.",
            "- No board power, throughput, thermal, or EMC compliance measurement.",
            "- No model weights are redistributed.",
            "- No HWP is emitted without an actual HWP tool and template.",
            "",
        ]
    )
    (EVIDENCE / "evidence_index.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font_name = "Helvetica"
    if font_path.is_file():
        pdfmetrics.registerFont(TTFont("VarpK26Sans", str(font_path)))
        font_name = "VarpK26Sans"
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font_name
    document = SimpleDocTemplate(
        str(EVIDENCE / "evidence_index.pdf"),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="VARP K26 evidence index",
        author="CHOI YUNHYUK",
    )
    story = [
        Paragraph("VARP K26 evidence index", styles["Title"]),
        Paragraph(
            "Claim-separated manifest. Hashes bind entries to the release snapshot.",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
    ]
    for index, row in enumerate(rows):
        story.extend(
            [
                Paragraph(
                    f"{row['id']} — {row['evidence_type']}", styles["Heading2"]
                ),
                Paragraph(str(row["path"]), styles["Code"]),
                Paragraph(
                    "<b>Supports:</b> " + str(row["allowed_interpretation"]),
                    styles["BodyText"],
                ),
                Paragraph(
                    "<b>Does not support:</b> "
                    + str(row["forbidden_interpretation"]),
                    styles["BodyText"],
                ),
                Paragraph(
                    f"SHA-256: {row['sha256']} · {row['size_bytes']} bytes",
                    styles["BodyText"],
                ),
                Spacer(1, 3 * mm),
            ]
        )
        if index == 5:
            story.append(PageBreak())
    document.build(story)


def write_manifest(rows: list[dict[str, object]]) -> None:
    manifest = {
        "schema_version": "varp.k26.evidence-manifest.v1",
        "release": "main-v2",
        "model_weights_included": False,
        "records": rows,
        "global_claim_boundary": (
            "Direct graph/RTL/KiCad evidence is separated from analytical, "
            "hybrid, energy-estimate, and blocked physical claims."
        ),
    }
    (EVIDENCE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths = sorted(
        path
        for path in EVIDENCE.rglob("*")
        if path.is_file()
        and path.name != "checksums.sha256"
        and "__pycache__" not in path.parts
    )
    (EVIDENCE / "checksums.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(EVIDENCE).as_posix()}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / value.decode("utf-8")
        for value in result.stdout.split(b"\0")
        if value
    ]


def safe_for_release(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    lowered = relative.as_posix().lower()
    forbidden_names = {
        "model.onnx",
        "model.onnx_data",
        "pytorch_model.bin",
        "model.safetensors",
    }
    if path.name.lower() in forbidden_names:
        return False
    if any(part in {".git", "target", ".venv"} for part in relative.parts):
        return False
    if path.is_file() and path.stat().st_size > 100 * 1024 * 1024:
        return False
    return "secret" not in lowered


def deterministic_zip(
    output: Path,
    files: Iterable[Path],
    arcname_overrides: dict[Path, str] | None = None,
) -> None:
    arcname_overrides = arcname_overrides or {}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(set(files), key=lambda item: item.as_posix()):
            if not path.is_file() or not safe_for_release(path):
                continue
            relative = arcname_overrides.get(
                path, path.relative_to(ROOT).as_posix()
            )
            info = zipfile.ZipInfo(relative, date_time=(2026, 7, 31, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.stat().st_mode & 0o111 else 0o644) << 16
            archive.writestr(info, path.read_bytes())


def under(*roots: str) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        path = ROOT / root
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
    return files


def tracked_under(*roots: str) -> list[Path]:
    """Return only version-controlled files below the requested roots."""
    prefixes = tuple((ROOT / root).resolve() for root in roots)
    return [
        path
        for path in tracked_files()
        if any(path.resolve().is_relative_to(prefix) for prefix in prefixes)
    ]


def build_archives() -> None:
    RELEASE.mkdir(parents=True, exist_ok=True)
    for stale_archive in RELEASE.glob("VARP_K26_*.zip"):
        stale_archive.unlink()
    source_files = tracked_files()
    source_manifest = RELEASE / "source_manifest.txt"
    source_manifest.write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n"
            for path in sorted(source_files, key=lambda item: item.as_posix())
            if path.is_file() and safe_for_release(path)
        ),
        encoding="utf-8",
    )
    deterministic_zip(
        RELEASE / "VARP_K26_Source.zip",
        source_files + [source_manifest],
        {source_manifest: "source_manifest.txt"},
    )
    deterministic_zip(
        RELEASE / "VARP_K26_Compact_Evidence.zip",
        under(
            "evidence",
            "build/evidence",
            "results/experiments",
            "results/model_level",
            "results/power_cost",
            "results/capacity",
            "cost",
            "models",
            "docs/toolchain",
            "docs/rtl",
            "hardware/kicad/controlled_review.md",
            "hardware/kicad/k26_reports",
        ),
    )
    deterministic_zip(
        RELEASE / "VARP_K26_Publication_Assets.zip",
        under("build/publication_assets"),
    )
    deterministic_zip(
        RELEASE / "VARP_K26_Paper_and_Presentation.zip",
        tracked_under("paper/final", "paper/technical_report")
        + under("build/presentation"),
    )
    archives = sorted(RELEASE.glob("VARP_K26_*.zip"))
    (RELEASE / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in archives),
        encoding="utf-8",
    )
    (RELEASE / "release_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "varp.k26.release-manifest.v1",
                "tag": "main-v2",
                "model_weights_included": False,
                "archives": [
                    {
                        "name": path.name,
                        "sha256": sha256(path),
                        "size_bytes": path.stat().st_size,
                    }
                    for path in archives
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="build evidence index/manifest but not release archives",
    )
    arguments = parser.parse_args()
    rows = resolve_records()
    write_index(rows)
    write_manifest(rows)
    if not arguments.index_only:
        build_archives()
    print(
        f"VARP K26 evidence records={len(rows)} "
        f"archives={0 if arguments.index_only else 4}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
