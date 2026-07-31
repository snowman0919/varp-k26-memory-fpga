#!/usr/bin/env python3
"""Build source-bound RTL maps and the annotated stealing waveform evidence."""

from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

import cairosvg


ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "evidence/waveforms/work_stealing_events.csv"
SIM_VCD = (
    ROOT
    / "build/work-stealing-evidence/WorkStealingEvidenceTop/test/"
    "work_stealing_case_wave.vcd"
)
EVIDENCE = ROOT / "evidence/waveforms"
RTL_DOCS = ROOT / "docs/rtl"


MODULES = [
    ("TileScheduler", "hw/src/main/scala/varp/scheduler/TileScheduler.scala", "S0–S3 job ownership, FCFS and steal selection", "system", "TileJob", "ScheduledTile", "8", "implemented RTL", "F01/F02"),
    ("K26WorkStealingTop", "hw/src/main/scala/varp/k26/K26WorkStealingTop.scala", "paper integration shell and payload identity store", "system", "MatVecTileCommand", "MatVecTileResult", "scheduler 8; store 32", "implemented RTL", "F01"),
    ("ComputeClusterArray", "hw/src/main/scala/varp/compute/ComputeCluster.scala", "one/two/four concrete compute clusters", "system", "per-cluster command", "per-cluster result", "cluster 4", "implemented RTL", "F01"),
    ("ComputeCluster", "hw/src/main/scala/varp/compute/ComputeCluster.scala", "FCFS command buffering and exact job counters", "system", "MatVecTileCommand", "MatVecTileResult", "4 input; 2 output", "implemented RTL", "F01/F03"),
    ("MatVecTileConsumer", "hw/src/main/scala/varp/compute/ComputeCluster.scala", "buffered adapter around the imported MatVec", "system", "16 INT8 activations + 4×16 INT8 weights", "4×INT32", "4 input; 2 output", "implemented RTL", "F01/F03"),
    ("LegacyMatVecAdapter", "hw/src/main/scala/varp/compute/LegacyMatVecAdapter.scala", "job-preserving adapter for DecodeMatVecInt8", "system", "tile command", "tile result", "single active command", "implemented RTL", "F01"),
    ("DecodeMatVecInt8", "hw/src/main/scala/qk/DecodeMatVecInt8.scala", "actual 16×4 signed INT8 MatVec primitive", "system", "16×INT8 + 4×16×INT8", "4×INT32", "internal pipeline", "implemented RTL", "F01/F03"),
    ("BundleRouter", "hw/src/main/scala/varp/link/BundleRouter.scala", "preferred-bundle assignment and bounded reroute", "system", "routed packet", "1/2/4 bundle streams", "transport FIFO", "implemented RTL; separate plane", "F01"),
    ("MultiChannelMemoryIngress", "hw/src/main/scala/varp/memory/MultiChannelMemoryScheduler.scala", "output-tile channel affinity", "system", "memory tile request", "1/2/4 channel streams", "8/channel", "implemented RTL; separate plane", "F01"),
    ("BankAwareChannelScheduler", "hw/src/main/scala/varp/memory/MultiChannelMemoryScheduler.scala", "row-hit-first selection with age cap", "system", "channel request", "memory command", "4", "implemented RTL; PHY external", "F01"),
    ("WorkStealingEvidenceTop", "hw/src/main/scala/varp/evidence/WorkStealingEvidenceTop.scala", "instrumented scheduler-to-real-MatVec evidence harness", "system", "MatVecTileCommand", "MatVecTileResult + debug", "scheduler 8; cluster 4", "evidence-only RTL harness", "F02/F03"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_module_map() -> None:
    RTL_DOCS.mkdir(parents=True, exist_ok=True)
    for module, source, *_ in MODULES:
        text = (ROOT / source).read_text(encoding="utf-8")
        if f"class {module}" not in text and f"object {module}" not in text:
            raise ValueError(f"{module} is not present in {source}")
    header = [
        "module",
        "source_path",
        "role",
        "clock_domain",
        "input_width",
        "output_width",
        "queue_depth",
        "implemented_or_modeled",
        "paper_figure",
    ]
    csv_path = RTL_DOCS / "RTL_MODULE_MAP.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(MODULES)

    rows = "\n".join(
        f"| `{m}` | `{s}` | {role} | {depth} | {status} | {fig} |"
        for m, s, role, _, _, _, depth, status, fig in MODULES
    )
    (RTL_DOCS / "RTL_MODULE_MAP.md").write_text(
        "# RTL module map\n\n"
        "This inventory is generated from the named Scala sources. Width and "
        "queue descriptions are structural RTL facts; DDR PHY, GT PHY, "
        "synthesis, and board timing remain external physical gates.\n\n"
        "| Module | Source | Role | Queue depth | Evidence boundary | Figure |\n"
        "|---|---|---|---|---|---|\n"
        f"{rows}\n\n"
        "Generation command: `python3 scripts/build_rtl_evidence.py`.\n",
        encoding="utf-8",
    )


def load_events() -> list[dict[str, str]]:
    if not EVENTS.is_file():
        raise FileNotFoundError(
            "run `sbt -batch \"testOnly varp.WorkStealingEvidenceSpec\"` first"
        )
    with EVENTS.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or sum(row["steal_event"] == "true" for row in rows) != 3:
        raise ValueError("expected exactly three bounded stealing events")
    if max(int(row["successful_steals"]) for row in rows) != 3:
        raise ValueError("successful-steal ledger does not close")
    return rows


def build_svg(rows: list[dict[str, str]]) -> Path:
    width, height = 1600, 900
    left, right = 230, 1540
    max_cycle = max(int(row["cycle"]) for row in rows)
    scale = (right - left) / max_cycle
    lanes = [
        ("input valid/ready", "input_valid", 160, "#3568a8"),
        ("victim queue occupancy", "q1", 275, "#c28b2c"),
        ("eligible", "eligible", 390, "#738b42"),
        ("steal event", "steal_event", 505, "#d46a3a"),
        ("MatVec active C0", "matvec_active_0", 620, "#3568a8"),
        ("MatVec start/result", "matvec_start_0", 735, "#ad5f78"),
    ]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Actual RTL work-stealing event and MatVec execution timeline</title>",
        "<desc>Three jobs accumulate in local queue one, are stolen by cluster zero, and complete through the real DecodeMatVecInt8 datapath.</desc>",
        '<rect width="1600" height="900" fill="#fbfcfe"/>',
        '<text x="70" y="65" font-family="sans-serif" font-size="30" '
        'font-weight="700" fill="#18212f">Actual RTL temporal evidence · S3 to real MatVec</text>',
        '<text x="70" y="100" font-family="sans-serif" font-size="18" '
        'fill="#667085">Verilator VCD · 3 exact stolen jobs · evidence harness only</text>',
    ]
    for tick in range(0, max_cycle + 1, 20):
        x = left + tick * scale
        svg += [
            f'<line x1="{x:.1f}" y1="125" x2="{x:.1f}" y2="800" '
            'stroke="#d9dee8" stroke-width="1"/>',
            f'<text x="{x:.1f}" y="830" text-anchor="middle" '
            'font-family="sans-serif" font-size="14" fill="#667085">'
            f"{tick}</text>",
        ]
    svg.append(
        '<text x="885" y="865" text-anchor="middle" font-family="sans-serif" '
        'font-size="16" fill="#667085">cycle</text>'
    )
    for label, field, y, color in lanes:
        svg += [
            f'<text x="205" y="{y + 7}" text-anchor="end" '
            'font-family="sans-serif" font-size="17" fill="#18212f">'
            f"{escape(label)}</text>",
            f'<line x1="{left}" y1="{y + 25}" x2="{right}" y2="{y + 25}" '
            'stroke="#d9dee8" stroke-width="1"/>',
        ]
        if field == "q1":
            points = []
            for row in rows:
                x = left + int(row["cycle"]) * scale
                q = int(row[field])
                points.append(f"{x:.1f},{y + 35 - q * 9:.1f}")
            svg.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{color}" stroke-width="4"/>'
            )
            continue
        for row in rows:
            active = row[field] == "true"
            if field == "input_valid":
                active = (
                    row["input_valid"] == "true"
                    and row["input_ready"] == "true"
                )
            if not active:
                continue
            cycle = int(row["cycle"])
            x = left + cycle * scale
            if field in {"steal_event", "matvec_start_0"}:
                svg.append(
                    f'<line x1="{x:.1f}" y1="{y - 25}" x2="{x:.1f}" '
                    f'y2="{y + 30}" stroke="{color}" stroke-width="5"/>'
                )
            else:
                svg.append(
                    f'<rect x="{x:.1f}" y="{y - 18}" '
                    f'width="{max(scale, 2):.1f}" height="36" '
                    f'fill="{color}" opacity="0.86"/>'
                )
        if field == "matvec_start_0":
            for row in rows:
                if row["matvec_result_0"] == "true":
                    x = left + int(row["cycle"]) * scale
                    svg.append(
                        f'<circle cx="{x:.1f}" cy="{y}" r="8" '
                        'fill="#18212f"/>'
                    )
    steals = [row for row in rows if row["steal_event"] == "true"]
    first_x = left + int(steals[0]["cycle"]) * scale
    last_x = left + int(steals[-1]["cycle"]) * scale
    center_x = (first_x + last_x) / 2
    jobs = ", ".join(row["dispatch_job_id"] for row in steals)
    svg += [
        f'<path d="M{center_x:.1f},470 L{center_x:.1f},430" '
        'stroke="#d46a3a" stroke-width="2" marker-end="url(#arrow)"/>',
        f'<text x="{last_x + 18:.1f}" y="420" font-family="sans-serif" '
        'font-size="14" fill="#18212f">'
        f"cycles 16–18 · jobs {escape(jobs)} · Q1 to C0</text>",
    ]
    svg.insert(
        4,
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" '
        'refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" '
        'fill="#d46a3a"/></marker></defs>',
    )
    svg += [
        '<rect x="70" y="842" width="16" height="16" fill="#ad5f78"/>',
        '<text x="94" y="856" font-family="sans-serif" font-size="14" '
        'fill="#18212f">vertical tick: MatVec start</text>',
        '<circle cx="310" cy="850" r="7" fill="#18212f"/>',
        '<text x="323" y="856" font-family="sans-serif" font-size="14" '
        'fill="#18212f">dot: MatVec result</text>',
        "</svg>",
    ]
    svg_path = EVIDENCE / "work_stealing_annotated.svg"
    svg_bytes = ("\n".join(svg) + "\n").encode("utf-8")
    pdf_path = EVIDENCE / "work_stealing_annotated.pdf"
    svg_changed = not svg_path.is_file() or svg_path.read_bytes() != svg_bytes
    svg_path.write_bytes(svg_bytes)
    # Cairo embeds the wall-clock creation time in PDF output. Preserve the
    # checked-in PDF when its source SVG is byte-identical so a reproduction
    # run does not create a false binary diff.
    if svg_changed or not pdf_path.is_file():
        cairosvg.svg2pdf(
            bytestring=svg_bytes,
            write_to=str(pdf_path),
        )
    return svg_path


def write_wave_bundle(rows: list[dict[str, str]]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not SIM_VCD.is_file():
        raise FileNotFoundError(SIM_VCD)
    vcd = EVIDENCE / "work_stealing_case.vcd"
    shutil.copyfile(SIM_VCD, vcd)
    signals = [
        "TOP.io_now",
        "TOP.io_command_valid",
        "TOP.io_command_ready",
        "TOP.io_command_payload_job_jobId",
        "TOP.io_queueOccupancy_0",
        "TOP.io_queueOccupancy_1",
        "TOP.io_victimQueue",
        "TOP.io_dispatchTarget",
        "TOP.io_eligible",
        "TOP.io_age",
        "TOP.io_localityScore",
        "TOP.io_stealEvent",
        "TOP.io_dispatchJobId",
        "TOP.io_matVecStart_0",
        "TOP.io_matVecActive_0",
        "TOP.io_matVecResult_0",
        "TOP.io_results_0_valid",
        "TOP.io_results_0_payload_job_jobId",
        "TOP.io_successfulSteals",
    ]
    gtkw = [
        "[*] GTKWave Analyzer save file",
        f"[dumpfile] {vcd.as_posix()}",
        "[timestart] 0",
        "[size] 1600 900",
        "@28",
        *signals,
    ]
    (EVIDENCE / "work_stealing_case.gtkw").write_text(
        "\n".join(gtkw) + "\n", encoding="utf-8"
    )
    steals = [row for row in rows if row["steal_event"] == "true"]
    (EVIDENCE / "README.md").write_text(
        "# Work-stealing waveform evidence\n\n"
        "This bundle is produced by the real SpinalHDL `TileScheduler`, "
        "`ComputeClusterArray`, `LegacyMatVecAdapter`, and "
        "`DecodeMatVecInt8`. Three jobs are intentionally held in queue 1; "
        "cluster 0 becomes available and steals jobs 1, 5, and 9. The test "
        "checks all four INT32 outputs against a software reference and closes "
        "accepted=dispatched=completed=3.\n\n"
        "The harness proves scheduler-to-MatVec temporal behavior only. It does "
        "not prove GT/DDR PHY timing, physical bandwidth, synthesis timing, or "
        "Gemma model-level performance.\n\n"
        "Generation:\n\n"
        "```bash\n"
        'sbt -batch "testOnly varp.WorkStealingEvidenceSpec"\n'
        "python3 scripts/build_rtl_evidence.py\n"
        "```\n\n"
        f"- Captured cycles: {len(rows)}\n"
        f"- Steal cycles: {', '.join(row['cycle'] for row in steals)}\n"
        f"- VCD SHA-256: `{sha256(vcd)}`\n"
        f"- Event CSV SHA-256: `{sha256(EVENTS)}`\n",
        encoding="utf-8",
    )


def main() -> int:
    write_module_map()
    rows = load_events()
    write_wave_bundle(rows)
    build_svg(rows)
    print(
        f"RTL evidence: modules={len(MODULES)} cycles={len(rows)} "
        "steals=3 exact_results=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
