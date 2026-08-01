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
        "모든 애니메이션은 Manim으로 생성했으며 수치 장면은 저장된 CSV를 직접 읽는다. 보드 실측 타이밍을 표현하지 않는다.",
        "",
        "| 순서 | Asset | 역할 | 근거 |",
        "|---:|---|---|---|",
        "| 1 | `tile_dataflow.mp4/.gif` | 실제 타일의 폐루프 논리 경로 | `gemma3_1b_closed_loop_trace.csv`와 RTL 구조 |",
        "| 2 | `work_stealing_sequence.mp4/.gif` | 대기 이득−이동 비용 선택 과정 | `k26_scheduler_model.py` |",
        "| 3 | `scheduler_timeline.mp4/.gif` | 동일 작업·시드의 S1/S3 사건 비교 | `s1_s3_timeline_events.csv` |",
        "| 4 | `tail_latency_results.mp4/.gif` | 합성 부하와 Gemma 배치 민감도 | `paired_policy_effects.csv`; `gemma3_1b_policy_effects.csv` |",
        "| 5 | `bottleneck_migration.mp4/.gif` | p95·비지역 가중치·완료시간 절충 | `paired_policy_effects.csv` |",
        "",
        "`presentation.mp4`와 `presentation.gif`는 위 장면을 연결한 무음 시각 요약이다. 9분 50초 구두 설명은 `speaker_notes.md`를 따른다.",
    ]
    (FINAL / "animation_manifest.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"visual_summary={mp4.relative_to(ROOT)} gif={gif.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
