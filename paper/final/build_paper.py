#!/usr/bin/env python3
"""Build and audit the VARP K26 submission and extended technical report."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "paper" / "final"
REPORT = ROOT / "paper" / "technical_report"
BROWSER_TIMEOUT_SECONDS = 180


def run(
    *args: str, timeout: int = BROWSER_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        command = " ".join(Path(arg).name if index == 0 else arg
                           for index, arg in enumerate(args))
        raise SystemExit(
            f"paper command timed out after {timeout}s: {command}\n"
            f"stdout:\n{error.stdout or ''}\nstderr:\n{error.stderr or ''}"
        ) from error


def require_tools() -> dict[str, str]:
    names = ["pandoc", "pdfinfo", "pdftotext", "pdftohtml"]
    found = {name: shutil.which(name) or "" for name in names}
    found["browser"] = (
        shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or ""
    )
    missing = [name for name, path in found.items() if not path]
    if missing:
        raise SystemExit("missing required paper tools: " + ", ".join(missing))
    return found


def write_renderer_manifest(tools: dict[str, str]) -> None:
    output = ROOT / "build" / "paper" / "renderer_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    versions: dict[str, str] = {}
    for name, executable in tools.items():
        arguments = (
            ("-v",)
            if name in {"pdfinfo", "pdftotext", "pdftohtml"}
            else ("--version",)
        )
        result = run(executable, *arguments, timeout=30)
        text = (result.stdout or result.stderr).strip().splitlines()
        versions[name] = text[0] if text else "unknown"
    output.write_text(
        json.dumps(
            {
                "schema_version": "varp.k26.paper-renderer.v1",
                "browser_timeout_seconds": BROWSER_TIMEOUT_SECONDS,
                "executables": {
                    name: Path(path).name for name, path in tools.items()
                },
                "versions": versions,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def assemble_report() -> None:
    submission = (FINAL / "submission_manuscript.md").read_text(encoding="utf-8")
    submission = re.sub(
        r'^title: ".*?"$',
        'title: "K26–Memory FPGA 다채널 메모리·Work Stealing 구조: 확장 기술보고서"',
        submission,
        count=1,
        flags=re.MULTILINE,
    )
    submission = re.sub(
        r'^subtitle: ".*?"$',
        'subtitle: "Extended Technical Report on Gemma 3 1B Trace, RTL, Scheduler, Cost, and Physical Evidence"',
        submission,
        count=1,
        flags=re.MULTILINE,
    )
    appendices = (REPORT / "technical_appendices.md").read_text(encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "technical_report.md").write_text(
        submission.rstrip() + "\n\n\\newpage\n\n" + appendices.rstrip() + "\n",
        encoding="utf-8",
    )


def normalize_pdf_metadata(pdf: Path) -> None:
    """Make Chromium's otherwise time-varying PDF bytes deterministic."""
    payload = pdf.read_bytes()
    timestamp = re.compile(rb"D:\d{14}\+00'00'")
    normalized, count = timestamp.subn(b"D:20260731000000+00'00'", payload)
    if count != 2:
        raise SystemExit(
            f"{pdf.name}: expected CreationDate and ModDate, found {count}"
        )

    # Chromium assigns process-local accessibility IDs in tagged PDFs.  Their
    # starting value can change even when every rendered page is identical.
    # Canonicalize IDs in first-seen order while preserving their fixed width
    # and all reference relationships, so the cross-reference table offsets
    # remain valid.
    node_ids: dict[bytes, bytes] = {}

    def canonical_node_id(match: re.Match[bytes]) -> bytes:
        original = match.group(0)
        if original not in node_ids:
            node_ids[original] = f"node{len(node_ids) + 1:08d}".encode("ascii")
        return node_ids[original]

    normalized = re.sub(rb"node\d{8}", canonical_node_id, normalized)
    pdf.write_bytes(normalized)


def build_document(source: Path, css: Path, stem: Path, browser: str) -> int:
    html = stem.with_suffix(".html")
    pdf = stem.with_suffix(".pdf")
    plaintext = stem.with_name(stem.name + "_plaintext.txt")
    run(
        "pandoc",
        str(source),
        "--standalone",
        "--embed-resources",
        "--mathml",
        "--css",
        str(css),
        "--resource-path",
        f"{source.parent}:{ROOT}",
        "-o",
        str(html),
    )
    run("pandoc", str(source), "-t", "plain", "-o", str(plaintext))
    cleaned = "\n".join(
        line.rstrip() for line in plaintext.read_text(encoding="utf-8").splitlines()
    )
    plaintext.write_text(cleaned.rstrip() + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="varp-chromium-profile-") as profile:
        run(
            browser,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-background-networking",
            "--run-all-compositor-stages-before-draw",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf}",
            html.as_uri(),
        )
    normalize_pdf_metadata(pdf)
    info = run("pdfinfo", str(pdf)).stdout
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not match:
        raise SystemExit(f"could not read page count: {pdf}")
    return int(match.group(1))


def extract_and_audit(pdf: Path, text_out: Path) -> None:
    run("pdftotext", str(pdf), str(text_out))
    text = text_out.read_text(encoding="utf-8", errors="replace")
    forbidden = {
        "local filesystem path": r"/home/|file://",
        "Markdown backtick": r"`",
        "independence violation": r"9차 수정본|이전 논문|후속 논문|앞선 버전",
    }
    errors = [label for label, pattern in forbidden.items() if re.search(pattern, text)]
    if errors:
        raise SystemExit(f"{pdf.name}: " + ", ".join(errors))
    required = {
        "Gemma 3 1B": r"Gemma\s+3\s+1B",
        "ONNX Runtime boundary": r"ONNX\s+Runtime\s+Android\s+CPU",
        "graph inventory": r"7,837",
        "KiCad native source render": r"KiCad\s+native\s+PCB\s+source",
        "S0-physical": r"S0-physical",
        "analytical": r"analytical",
        "NOT FOR FABRICATION": r"NOT\s+FOR\s+FABRICATION",
        "18.12%": r"18\.12%",
        "17.59%": r"17\.59%",
        "skew p99": r"302,186\.41/249,379\.73/247,296\.42",
        "mixed p99": r"506,354\.73/426,120\.83/422,255\.59",
        "cost-normalized midpoint": r"0\.004551194106",
        "procurement refresh": r"조달\s+전에\s+갱신",
    }
    absent = [label for label, pattern in required.items() if not re.search(pattern, text)]
    if absent:
        raise SystemExit(f"{pdf.name}: missing required text: {absent}")


PAPER_SVG_FIGURES = (
    {
        "figure": "1",
        "asset_id": "F01",
        "source": "paper/final/figures/paper_f01_evidence_path.svg",
        "upstream": "build/publication_assets/figures/F01;data/publication/k26_system_architecture.csv",
        "evidence": "RTL-simulated + modeled + blocked",
        "scope": "core paper simplified SVG; detailed F01 is supplemental",
        "anchor": ("Implemented RTL planes", "missing end-to-end loop"),
    },
    {
        "figure": "2",
        "asset_id": "F06",
        "source": "paper/final/figures/paper_f02_onnx_runtime_graph.svg",
        "upstream": "experiments/gemma3_1b/trace_manifest.json;experiments/gemma3_1b/projection_trace.csv",
        "evidence": "graph-derived + separate ONNX Runtime host reference",
        "scope": "core paper ONNX graph/runtime boundary; detailed F06 is supplemental",
        "anchor": ("ONNX graph", "Runtime evidence boundary"),
    },
    {
        "figure": "3",
        "asset_id": "F02",
        "source": "paper/final/figures/paper_f03_policy_boundary.svg",
        "upstream": "build/publication_assets/figures/F02;data/publication/k26_scheduler_policies.csv",
        "evidence": "RTL decision/dispatch + analytical migration + blocked DMA/link/DDR",
        "scope": "core paper simplified SVG; detailed F02 is supplemental",
        "anchor": ("policy ladder and evidence boundary",),
    },
    {
        "figure": "4",
        "asset_id": "waveform",
        "source": "paper/final/figures/paper_f04_waveform_identity.svg",
        "upstream": "evidence/waveforms/work_stealing_events.csv",
        "evidence": "RTL-simulated bounded timeline",
        "scope": "core paper identity/count summary; compact event CSV is supplemental",
        "anchor": ("RTL-simulated job identity", "exact-once timeline"),
    },
    {
        "figure": "5",
        "asset_id": "F04-subset",
        "source": "paper/final/figures/paper_f05_tail_latency.svg",
        "upstream": "data/publication/k26_scheduler_summary.csv",
        "evidence": "analytical model",
        "scope": "core paper skew/mixed p95 subset; detailed F04 is supplemental",
        "anchor": ("Full-overlap", "locality-aware"),
    },
    {
        "figure": "6",
        "asset_id": "F04-subset",
        "source": "paper/final/figures/paper_f06_tradeoff.svg",
        "upstream": "data/publication/k26_scheduler_summary.csv",
        "evidence": "analytical model",
        "scope": "core paper S2/S3 trade-off subset; detailed F04 is supplemental",
        "anchor": ("against oldest-steal",),
    },
)

PAPER_RASTER_FIGURES = (
    {
        "figure": "7",
        "asset_id": "F05",
        "source": "paper/final/figures/paper_f07_kicad_coupon_render.png",
        "upstream": "hardware/kicad/k26_memory_coupon/k26_memory_coupon.kicad_pcb;hardware/kicad/controlled_review.md",
        "evidence": "KiCad-native source render + bounded checks",
        "scope": "core paper native PCB render; NOT FOR FABRICATION",
    },
)

PAPER_FIGURES = PAPER_SVG_FIGURES + PAPER_RASTER_FIGURES

SUPPLEMENTAL_ASSETS = (
    ("F03", "build/publication_assets/figures/F03", "graph-derived + analytical + host-measured", "presentation/supplement only"),
    ("T01", "build/publication_assets/figures/T01", "analytical model", "presentation/supplement only"),
    ("T02", "build/publication_assets/figures/T02", "analytical model + not-run", "presentation/supplement only"),
    ("T03", "build/publication_assets/figures/T03", "mixed evidence", "presentation/supplement only"),
    ("T04", "build/publication_assets/figures/T04", "analytical model", "presentation/supplement only"),
)


def svg_font_sizes(svg_path: Path) -> tuple[float, float]:
    root = ET.parse(svg_path).getroot()
    style = "\n".join(
        node.text or "" for node in root.iter() if node.tag.endswith("style")
    )
    class_sizes = {
        name: float(size)
        for name, size in re.findall(
            r"\.([A-Za-z0-9_-]+)\s*\{[^}]*font-size\s*:\s*([0-9.]+)px",
            style,
        )
    }
    sizes: list[float] = []
    title_size: float | None = None
    for node in root.iter():
        if not node.tag.endswith("text"):
            continue
        raw = node.attrib.get("font-size", "")
        size: float | None = None
        if raw:
            match = re.fullmatch(r"([0-9.]+)px", raw)
            if not match:
                raise SystemExit(f"{svg_path}: unsupported font-size {raw!r}")
            size = float(match.group(1))
        else:
            for class_name in node.attrib.get("class", "").split():
                if class_name in class_sizes:
                    size = class_sizes[class_name]
                    break
        if size is None:
            raise SystemExit(f"{svg_path}: text without explicit font size")
        sizes.append(size)
        if "h" in node.attrib.get("class", "").split() and title_size is None:
            title_size = size
    if not sizes or title_size is None:
        raise SystemExit(f"{svg_path}: missing text or title font")
    return min(sizes), title_size


def validate_final_figure_fonts(pdf: Path, pdftohtml: str) -> None:
    manuscript = (FINAL / "submission_manuscript.md").read_text(encoding="utf-8")
    placed = re.findall(r"!\[그림\s+([0-9]+)\.[^\]]*\]\(([^)]+)\)", manuscript)
    expected = [(item["figure"], Path(item["source"]).name) for item in PAPER_FIGURES]
    actual = [(number, Path(path).name) for number, path in placed]
    if actual != expected:
        raise SystemExit(
            "figure placement set/order differs from fail-closed manifest: "
            f"expected={expected}, actual={actual}"
        )

    xml_path = FINAL / "submission_manuscript_font_gate.xml"
    run(
        pdftohtml,
        "-xml",
        "-hidden",
        "-nodrm",
        "-zoom",
        "1",
        str(pdf),
        str(xml_path),
    )
    root = ET.parse(xml_path).getroot()
    xml_path.unlink()
    for sidecar in FINAL.glob(f"{xml_path.stem}-*.png"):
        sidecar.unlink()
    font_sizes = {
        spec.attrib["id"]: float(spec.attrib["size"])
        for spec in root.iter("fontspec")
    }
    gate_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []
    for item in PAPER_SVG_FIGURES:
        source = ROOT / item["source"]
        source_min, source_title = svg_font_sizes(source)
        matches: list[tuple[int, float, str]] = []
        for page in root.findall("page"):
            for text_node in page.findall("text"):
                text = "".join(text_node.itertext())
                normalized = " ".join(text.split())
                if all(token.lower() in normalized.lower() for token in item["anchor"]):
                    font_id = text_node.attrib.get("font")
                    if font_id not in font_sizes:
                        raise SystemExit(
                            f"Figure {item['figure']}: anchor has no final PDF font"
                        )
                    matches.append(
                        (int(page.attrib["number"]), font_sizes[font_id], normalized)
                    )
        if len(matches) != 1:
            raise SystemExit(
                f"Figure {item['figure']}: expected one PDF anchor, found {len(matches)}"
            )
        page_number, reported_title_pt, anchor_text = matches[0]
        # pdftohtml reports integer point sizes. Subtract 0.5 pt so the gate
        # uses a conservative lower bound rather than rounded display output.
        title_lower_pt = reported_title_pt - 0.5
        if title_lower_pt <= 0:
            raise SystemExit(f"Figure {item['figure']}: invalid final title size")
        scale_pt_per_source_px = title_lower_pt / source_title
        min_final_pt = source_min * scale_pt_per_source_px
        svg_root = ET.parse(source).getroot()
        view_box = [float(value) for value in svg_root.attrib["viewBox"].split()]
        placed_width_pt = view_box[2] * scale_pt_per_source_px
        status = "PASS" if min_final_pt >= 8.0 else "FAIL"
        gate_rows.append(
            {
                "paper_figure": item["figure"],
                "source_svg": item["source"],
                "final_page": str(page_number),
                "pdf_anchor": anchor_text,
                "source_min_font_px": f"{source_min:.3f}",
                "source_title_font_px": f"{source_title:.3f}",
                "reported_title_font_pt": f"{reported_title_pt:.3f}",
                "title_ratio_inferred_width_pt_not_pdf_bbox": f"{placed_width_pt:.3f}",
                "conservative_min_final_font_pt": f"{min_final_pt:.3f}",
                "required_min_pt": "8.000",
                "status": status,
            }
        )
        manifest_rows.append(
            {
                "paper_figure": item["figure"],
                "publication_asset_id": item["asset_id"],
                "paper_source": item["source"],
                "upstream_source": item["upstream"],
                "evidence_type": item["evidence"],
                "final_page": str(page_number),
                "scope": item["scope"],
                "min_final_font_pt": f"{min_final_pt:.3f}",
                "placement_gate": status,
            }
        )
        if status != "PASS":
            raise SystemExit(
                f"Figure {item['figure']}: final minimum {min_final_pt:.3f} pt < 8 pt"
            )

    for item in PAPER_RASTER_FIGURES:
        source = ROOT / item["source"]
        with Image.open(source) as raster:
            width, height = raster.size
        if width < 2000 or height < 1200:
            raise SystemExit(
                f"Figure {item['figure']}: raster too small: {width}x{height}"
            )
        pages = []
        for page in root.findall("page"):
            page_text = " ".join(
                " ".join("".join(node.itertext()).split())
                for node in page.findall("text")
            )
            if all(
                token in page_text
                for token in ("KiCad", "native", "PCB", "source", "validation", "coupon")
            ):
                pages.append(int(page.attrib["number"]))
        if len(pages) != 1:
            raise SystemExit(
                f"Figure {item['figure']}: expected one raster caption page, found {pages}"
            )
        status = f"PASS_RASTER_{width}x{height}"
        gate_rows.append(
            {
                "paper_figure": item["figure"],
                "source_svg": item["source"],
                "final_page": str(pages[0]),
                "pdf_anchor": "KiCad native PCB source / validation coupon",
                "source_min_font_px": "N/A",
                "source_title_font_px": "N/A",
                "reported_title_font_pt": "N/A",
                "title_ratio_inferred_width_pt_not_pdf_bbox": "N/A",
                "conservative_min_final_font_pt": "N/A",
                "required_min_pt": "N/A",
                "status": status,
            }
        )
        manifest_rows.append(
            {
                "paper_figure": item["figure"],
                "publication_asset_id": item["asset_id"],
                "paper_source": item["source"],
                "upstream_source": item["upstream"],
                "evidence_type": item["evidence"],
                "final_page": str(pages[0]),
                "scope": item["scope"],
                "min_final_font_pt": "N/A (native raster)",
                "placement_gate": status,
            }
        )

    for asset_id, source, evidence, scope in SUPPLEMENTAL_ASSETS:
        manifest_rows.append(
            {
                "paper_figure": "",
                "publication_asset_id": asset_id,
                "paper_source": "",
                "upstream_source": source,
                "evidence_type": evidence,
                "final_page": "",
                "scope": scope,
                "min_final_font_pt": "",
                "placement_gate": "NOT_PLACED",
            }
        )

    gate_path = FINAL / "final_placement_manifest.csv"
    with gate_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=gate_rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(gate_rows)
    manifest_path = FINAL / "figure_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=manifest_rows[0].keys(), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(
        "final_figure_font_gate=PASS "
        f"svg_figures={len(PAPER_SVG_FIGURES)} raster_figures={len(PAPER_RASTER_FIGURES)} "
        f"min_pt={min(float(row['conservative_min_final_font_pt']) for row in gate_rows if row['conservative_min_final_font_pt'] != 'N/A'):.3f}"
    )


def write_checksums(paths: list[Path]) -> None:
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT)}")
    (FINAL / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    tools = require_tools()
    write_renderer_manifest(tools)
    assemble_report()
    submission_pages = build_document(
        FINAL / "submission_manuscript.md",
        FINAL / "submission.css",
        FINAL / "submission_manuscript",
        tools["browser"],
    )
    report_pages = build_document(
        REPORT / "technical_report.md",
        REPORT / "report.css",
        REPORT / "technical_report",
        tools["browser"],
    )
    if not 8 <= submission_pages <= 12:
        raise SystemExit(f"submission pages {submission_pages}; expected 8–12")
    if report_pages <= submission_pages:
        raise SystemExit(
            f"technical report must be longer than submission: {report_pages} <= {submission_pages}"
        )
    extract_and_audit(
        FINAL / "submission_manuscript.pdf",
        FINAL / "submission_manuscript_pdf_text.txt",
    )
    extract_and_audit(
        REPORT / "technical_report.pdf",
        REPORT / "technical_report_pdf_text.txt",
    )
    validate_final_figure_fonts(
        FINAL / "submission_manuscript.pdf", tools["pdftohtml"]
    )
    sources = [
        FINAL / "submission_manuscript.md",
        FINAL / "submission_manuscript.pdf",
        FINAL / "abstract_ko.md",
        FINAL / "abstract_en.md",
        FINAL / "hwp_transfer_guide.md",
        FINAL / "final_placement_manifest.csv",
        FINAL / "figure_manifest.csv",
        REPORT / "technical_report.md",
        REPORT / "technical_report.pdf",
    ]
    write_checksums(sources)
    print(f"submission_pages={submission_pages}")
    print(f"technical_report_pages={report_pages}")
    print("pdf_text_audit=PASS")
    print("hwp_status=BLOCKED_NO_TOOL_OR_TEMPLATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
