#!/usr/bin/env python3
"""Generate CSV-backed dark conference figures for slides 6 and 8."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics
import sys

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from varp.k26_scheduler_model import ModelConfig, generate_jobs, ledger_sha256, run_model  # noqa: E402


SOURCE = ROOT / "results" / "experiments" / "scheduler_controlled.csv"
ASSETS = ROOT / "presentation" / "final" / "assets"
BG = "#07111F"
PANEL = "#0B1627"
WHITE = "#F4F7FB"
MUTED = "#8EA2B8"
CYAN = "#36D7E7"
TEAL = "#28B6A6"
BLUE = "#4C8DFF"
AMBER = "#F1B44C"
GRAY = "#5E7188"


def read_rows() -> list[dict[str, str]]:
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def canonical_row(rows: list[dict[str, str]], scheduler: str) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row["subset"] == "scheduler"
        and row["workload"] == "skew"
        and row["scheduler"] == scheduler
        and row["seed"] == "23"
        and row["process_repetition"] == "0"
        and row["clusters"] == "4"
        and row["channels"] == "4"
        and row["bundles"] == "4"
        and row["link_width_bits"] == "128"
        and row["service_overlap_mode"] == "full"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one canonical {scheduler} row, found {len(matches)}")
    return matches[0]


def build_event_csv(rows: list[dict[str, str]]) -> Path:
    jobs = generate_jobs("skew", 1000, 23, clusters=4, channels=4, bundles=4)
    events: list[dict[str, object]] = []
    for scheduler in ("S1", "S3"):
        sink: list[dict[str, object]] = []
        result = run_model(
            jobs,
            ModelConfig(scheduler=scheduler, clusters=4, channels=4, bundles=4, link_width_bits=128),
            seed=23,
            workload="skew",
            process_repetition=0,
            event_sink=sink,
        )
        source_row = canonical_row(rows, scheduler)
        checks = (
            ("ledger_sha256", result["ledger_sha256"], source_row["ledger_sha256"]),
            ("total_completion_cycles", result["total_completion_cycles"], int(source_row["total_completion_cycles"])),
            ("successful_steals", result["successful_steals"], int(source_row["successful_steals"])),
            ("remote_weight_bytes", result["remote_weight_bytes"], int(source_row["remote_weight_bytes"])),
        )
        for name, actual, expected in checks:
            if actual != expected:
                raise RuntimeError(f"{scheduler} {name}: regenerated={actual!r} source={expected!r}")
        events.extend(sink)
    if ledger_sha256(jobs) != canonical_row(rows, "S1")["ledger_sha256"]:
        raise RuntimeError("canonical job ledger hash mismatch")
    output = ASSETS / "s1_s3_timeline_events.csv"
    fields = list(events[0].keys())
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(events)
    return output


def idle_segments(events: list[dict[str, str]], start: int, end: int) -> list[tuple[int, int]]:
    intervals = sorted(
        (max(start, int(row["dispatch_cycle"])), min(end, int(row["compute_end_cycle"])))
        for row in events
        if int(row["compute_end_cycle"]) > start and int(row["dispatch_cycle"]) < end
    )
    merged: list[list[int]] = []
    for left, right in intervals:
        if not merged or left > merged[-1][1]:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    gaps: list[tuple[int, int]] = []
    cursor = start
    for left, right in merged:
        if left > cursor:
            gaps.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append((cursor, end))
    return gaps


def plot_timeline(event_csv: Path) -> Path:
    with event_csv.open(encoding="utf-8", newline="") as stream:
        events = list(csv.DictReader(stream))
    # The initial backlog keeps all clusters reserved in both policies.  This
    # source-derived window is the first stable interval where S1 has exhausted
    # three local queues while S3 continues to dispatch stolen jobs.
    window_start, window_end = 40_000, 55_000
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True, facecolor=BG)
    for ax, scheduler in zip(axes, ("S1 · Static local", "S3 · Locality-aware stealing")):
        policy = scheduler.split(" · ")[0]
        ax.set_facecolor(PANEL)
        ax.set_ylim(-0.7, 3.7)
        ax.set_yticks(range(4), [f"Cluster {i}" for i in range(4)])
        ax.tick_params(colors=MUTED, labelsize=12)
        ax.grid(axis="x", color="#21354B", alpha=0.55, linewidth=0.8)
        ax.set_title(scheduler, loc="left", color=WHITE, fontsize=19, weight="bold", pad=10)
        for cluster in range(4):
            lane = [row for row in events if row["scheduler"] == policy and int(row["dispatch_cluster"]) == cluster]
            for left, right in idle_segments(lane, window_start, window_end):
                if right - left >= 35:
                    ax.broken_barh([(left, right - left)], (cluster - 0.30, 0.60), facecolors=AMBER, alpha=0.17)
            for row in lane:
                arrival = int(row["arrival_cycle"])
                dispatch = int(row["dispatch_cycle"])
                compute_start = int(row["compute_start_cycle"])
                finish = int(row["compute_end_cycle"])
                if finish <= window_start or arrival >= window_end:
                    continue
                q0, q1 = max(window_start, arrival), min(window_end, dispatch)
                if q1 > q0:
                    ax.broken_barh([(q0, q1 - q0)], (cluster - 0.22, 0.10), facecolors=GRAY, alpha=0.72)
                t0, t1 = max(window_start, dispatch), min(window_end, compute_start)
                if t1 > t0:
                    ax.broken_barh([(t0, t1 - t0)], (cluster - 0.18, 0.36), facecolors=TEAL, alpha=0.80)
                c0, c1 = max(window_start, compute_start), min(window_end, finish)
                if c1 > c0:
                    edge = CYAN if row["stolen"] == "1" else BLUE
                    ax.broken_barh([(c0, c1 - c0)], (cluster - 0.25, 0.50), facecolors=BLUE, edgecolors=edge, linewidth=2 if row["stolen"] == "1" else 0.4)
                    if row["stolen"] == "1" and c1 - c0 > 45:
                        ax.plot(c0, cluster, marker=">", color=CYAN, markersize=5, zorder=5)
        for spine in ax.spines.values():
            spine.set_color("#20344A")
    axes[-1].set_xlim(window_start, window_end)
    axes[-1].set_xlabel("Analytical cycle · skew · seed 23 · source row hash verified", color=MUTED, fontsize=11)
    legend = [
        Patch(facecolor=AMBER, alpha=0.25, label="Idle interval"),
        Patch(facecolor=GRAY, label="Queue wait"),
        Patch(facecolor=TEAL, label="Link / memory service"),
        Patch(facecolor=BLUE, label="Compute"),
        Line2D([0], [0], marker=">", color="none", markerfacecolor=CYAN, markeredgecolor=CYAN, label="Stolen job", markersize=8),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=5, frameon=False, labelcolor=WHITE, fontsize=12, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("S1 waits. S3 redistributes work.", color=WHITE, fontsize=28, weight="bold", x=0.07, ha="left", y=0.985)
    fig.subplots_adjust(left=0.11, right=0.98, top=0.90, bottom=0.11, hspace=0.34)
    output = ASSETS / "s1_s3_execution_timeline.png"
    fig.savefig(output, dpi=150, facecolor=BG)
    plt.close(fig)
    return output


def median_policy_rows(rows: list[dict[str, str]], workload: str, scheduler: str) -> dict[str, float]:
    selected = [
        row
        for row in rows
        if row["subset"] == "scheduler"
        and row["workload"] == workload
        and row["scheduler"] == scheduler
        and row["process_repetition"] == "0"
        and row["clusters"] == "4"
        and row["channels"] == "4"
        and row["bundles"] == "4"
        and row["link_width_bits"] == "128"
        and row["service_overlap_mode"] == "full"
    ]
    if len(selected) != 5:
        raise RuntimeError(f"expected five {workload}/{scheduler} source rows, found {len(selected)}")
    fields = (
        "queue_wait_mean_cycles",
        "remote_weight_bytes",
        "link_bundle_utilization_mean",
        "ddr_channel_utilization_mean",
        "total_completion_cycles",
    )
    return {field: statistics.median(float(row[field]) for row in selected) for field in fields}


def build_bottleneck_csv(rows: list[dict[str, str]]) -> Path:
    output = ASSETS / "bottleneck_shift_source.csv"
    records = []
    for workload in ("skew", "mixed"):
        for scheduler in ("S1", "S2", "S3"):
            records.append({"schema_version": "varp.k26.presentation-metric.v1", "source": SOURCE.relative_to(ROOT).as_posix(), "aggregation": "median of five seeds; process_repetition=0", "workload": workload, "scheduler": scheduler, **median_policy_rows(rows, workload, scheduler)})
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    return output


def plot_bottleneck(source_csv: Path) -> Path:
    with source_csv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    metrics = (
        ("queue_wait_mean_cycles", "Queue wait", 1 / 1000, "kcy", "lower is better"),
        ("remote_weight_bytes", "Remote weight", 1 / (1024 * 1024), "MiB", "movement cost"),
        ("link_bundle_utilization_mean", "Link pressure", 100, "%", "resource pressure"),
        ("ddr_channel_utilization_mean", "Memory pressure", 100, "%", "resource pressure"),
        ("total_completion_cycles", "Completion", 1 / 1000, "kcy", "lower is better"),
    )
    colors = {"S1": GRAY, "S2": BLUE, "S3": CYAN}
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), facecolor=BG)
    for ax, workload in zip(axes, ("skew", "mixed")):
        ax.set_facecolor(PANEL)
        ax.set_xlim(-0.4, len(metrics) - 0.6)
        ax.set_ylim(-0.08, 1.08)
        ax.axis("off")
        subset = [row for row in rows if row["workload"] == workload]
        normalized: dict[str, list[float]] = {policy: [] for policy in colors}
        labels: dict[tuple[str, int], str] = {}
        for index, (field, title, scale, unit, hint) in enumerate(metrics):
            values = {row["scheduler"]: float(row[field]) * scale for row in subset}
            lo, hi = min(values.values()), max(values.values())
            span = hi - lo
            for policy, value in values.items():
                normalized[policy].append(0.5 if math.isclose(span, 0.0) else (value - lo) / span)
                labels[(policy, index)] = f"{value:.2f}{unit}" if unit != "%" else f"{value:.1f}%"
            ax.plot([index, index], [0, 1], color="#294057", linewidth=1.2)
            ax.text(index, 1.05, title, color=WHITE, fontsize=13, weight="bold", ha="center")
            ax.text(index, -0.07, hint, color=MUTED, fontsize=8.5, ha="center")
        for policy, values in normalized.items():
            ax.plot(range(len(metrics)), values, color=colors[policy], linewidth=2.7, alpha=0.92, marker="o", markersize=7, label=policy)
            for index, value in enumerate(values):
                offset = {"S1": -0.055, "S2": 0.035, "S3": 0.095}[policy]
                ax.text(index, min(1.02, max(0.0, value + offset)), labels[(policy, index)], color=colors[policy], fontsize=8.5, ha="center", weight="bold")
        ax.text(-0.37, 0.95, workload.upper(), color=AMBER, fontsize=14, weight="bold", va="top")
        tradeoff = (
            "S3 vs S2 · remote −37.84% · completion +0.98%"
            if workload == "skew"
            else "S3 vs S2 · remote −22.16% · completion +0.41%"
        )
        ax.text(-0.37, 0.78, tradeoff, color=CYAN, fontsize=10, weight="bold", va="top")
    handles = [Line2D([0], [0], color=colors[p], marker="o", linewidth=3, label=p) for p in ("S1", "S2", "S3")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, labelcolor=WHITE, fontsize=12, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("Stealing shifts the bottleneck—not just the latency.", color=WHITE, fontsize=27, weight="bold", x=0.06, ha="left", y=0.98)
    fig.text(0.98, 0.02, "Source: scheduler_controlled.csv · median of 5 seeds · analytical", color=MUTED, fontsize=9, ha="right")
    fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.10, hspace=0.35)
    output = ASSETS / "bottleneck_shift.png"
    fig.savefig(output, dpi=150, facecolor=BG)
    plt.close(fig)
    return output


def plot_kicad_scope() -> Path:
    manifest_path = ROOT / "hardware" / "kicad" / "k26_reports" / "k26_scope_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    native = manifest["native_results"]
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=BG)
    ax.set_facecolor(PANEL)
    ax.axis("off")
    ax.text(0.06, 0.86, "REFERENCE COUPON", color=CYAN, fontsize=19, weight="bold", transform=ax.transAxes)
    ax.text(0.06, 0.68, f"{native['coupon_footprints']} footprints", color=WHITE, fontsize=16, weight="bold", transform=ax.transAxes)
    ax.text(0.50, 0.68, f"{native['track_segments']} tracks", color=WHITE, fontsize=16, weight="bold", transform=ax.transAxes)
    ax.text(0.06, 0.53, f"{native['vias']} vias", color=WHITE, fontsize=16, weight="bold", transform=ax.transAxes)
    ax.text(0.50, 0.53, f"{native['routed_gth_and_refclock_nets']} routed GTH/refclk nets", color=WHITE, fontsize=13, weight="bold", transform=ax.transAxes)
    ax.plot([0.06, 0.94], [0.39, 0.39], color="#264258", linewidth=1.4, transform=ax.transAxes)
    ax.text(0.06, 0.25, "ERC 0 · bounded routed-subset DRC 0", color=TEAL, fontsize=13, weight="bold", transform=ax.transAxes)
    ax.text(0.06, 0.09, manifest["status"], color="#FF6B6B", fontsize=15, weight="bold", transform=ax.transAxes)
    ax.text(0.94, 0.09, "scope: proposal + routed coupon", color=MUTED, fontsize=9, ha="right", transform=ax.transAxes)
    output = ASSETS / "kicad_validation_scope_inset.png"
    fig.savefig(output, dpi=150, facecolor=BG, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return output


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    event_csv = build_event_csv(rows)
    timeline = plot_timeline(event_csv)
    bottleneck_csv = build_bottleneck_csv(rows)
    bottleneck = plot_bottleneck(bottleneck_csv)
    kicad_inset = plot_kicad_scope()
    for path in (event_csv, timeline, bottleneck_csv, bottleneck, kicad_inset):
        print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
