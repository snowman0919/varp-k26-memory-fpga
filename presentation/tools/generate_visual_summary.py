#!/usr/bin/env python3
"""Concatenate the evidence animations into a portable presentation preview."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "presentation/final/assets"
FINAL = ROOT / "presentation/final"
STEMS = (
    "tile_dataflow",
    "work_stealing_sequence",
    "scheduler_timeline",
    "tail_latency_results",
    "bottleneck_migration",
)


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required")
    videos = [ASSETS / f"{stem}.mp4" for stem in STEMS]
    for video in videos:
        if not video.is_file() or video.stat().st_size == 0:
            raise SystemExit(f"missing animation: {video}")
    inputs: list[str] = []
    for video in videos:
        inputs.extend(("-i", str(video)))
    filter_graph = "".join(
        f"[{index}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:#07111F,fps=30,format=yuv420p[v{index}];"
        for index in range(len(videos))
    ) + "".join(f"[v{index}]" for index in range(len(videos))) + f"concat=n={len(videos)}:v=1:a=0[outv]"
    mp4 = FINAL / "presentation.mp4"
    gif = FINAL / "presentation.gif"
    run(
        ffmpeg,
        "-y",
        *inputs,
        "-filter_complex",
        filter_graph,
        "-map",
        "[outv]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-movflags",
        "+faststart",
        str(mp4),
    )
    run(ffmpeg, "-y", "-i", str(mp4), "-vf", "fps=8,scale=960:-2:flags=lanczos", "-loop", "0", str(gif))
    manifest = [
        "# 발표 시각자료 Manifest",
        "",
        "모든 animation은 Manim으로 생성했으며 수치 장면은 committed CSV를 직접 읽는다. 보드 실측 timing을 표현하지 않는다.",
        "",
        "| 순서 | Asset | 역할 | 근거 |",
        "|---:|---|---|---|",
        "| 1 | `tile_dataflow.mp4/.gif` | 구조·미통합 폐루프 | RTL module/dataflow boundary |",
        "| 2 | `work_stealing_sequence.mp4/.gif` | S3 victim search·score·steal | scheduler policy |",
        "| 3 | `scheduler_timeline.mp4/.gif` | S1/S3 동일 구간 비교 | `s1_s3_timeline_events.csv` |",
        "| 4 | `tail_latency_results.mp4/.gif` | Gemma replay와 synthetic 조건 분리 | scheduler CSV 2종 |",
        "| 5 | `bottleneck_migration.mp4/.gif` | p95·remote byte·completion 절충 | `scheduler_controlled.csv` |",
        "",
        "`presentation.mp4`와 `presentation.gif`는 위 장면을 연결한 무음 visual abstract다. 10분 구두 설명은 `speaker_notes.md`를 따른다.",
    ]
    (FINAL / "animation_manifest.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"visual_summary={mp4.relative_to(ROOT)} gif={gif.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
