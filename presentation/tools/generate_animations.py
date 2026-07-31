#!/usr/bin/env python3
"""Render and package the Manim evidence narratives used by the final deck."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCENES = Path(__file__).with_name("manim_scenes.py")
ASSETS = ROOT / "presentation" / "final" / "assets"
MEDIA = ROOT / "presentation" / "final" / ".work" / "manim"

JOBS = (
    ("WorkStealingSequence", "work_stealing_sequence", 4.8),
    ("TileDataflow", "tile_dataflow", 4.0),
    ("SchedulerTimeline", "scheduler_timeline", 3.8),
    ("TailLatencyResults", "tail_latency_results", 2.8),
    ("BottleneckMigration", "bottleneck_migration", 4.2),
)


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def locate(scene: str) -> Path:
    matches = sorted(MEDIA.rglob(f"{scene}.mp4"))
    if not matches:
        raise RuntimeError(f"render not found for {scene}")
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", choices=("l", "m", "h"), default="h")
    args = parser.parse_args()
    manim = shutil.which("manim")
    ffmpeg = shutil.which("ffmpeg")
    if not manim or not ffmpeg:
        raise SystemExit("manim and ffmpeg must be available on PATH")
    ASSETS.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    for scene, stem, frame_time in JOBS:
        run(manim, f"-q{args.quality}", "--format=mp4", "--media_dir", str(MEDIA), str(SCENES), scene)
        source = locate(scene)
        mp4 = ASSETS / f"{stem}.mp4"
        gif = ASSETS / f"{stem}.gif"
        still = ASSETS / f"{stem}_frame.png"
        shutil.copy2(source, mp4)
        run(ffmpeg, "-y", "-i", str(mp4), "-vf", "fps=12,scale=960:-2:flags=lanczos", "-loop", "0", str(gif))
        run(ffmpeg, "-y", "-ss", str(frame_time), "-i", str(mp4), "-frames:v", "1", "-update", "1", str(still))
    run(
        ffmpeg,
        "-y",
        "-i",
        str(ASSETS / "work_stealing_sequence.mp4"),
        "-vf",
        "fps=0.4,scale=760:-2:flags=lanczos,tile=2x2:nb_frames=4:padding=12:margin=12:color=#07111F",
        "-frames:v",
        "1",
        str(ASSETS / "work_stealing_storyboard.png"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
