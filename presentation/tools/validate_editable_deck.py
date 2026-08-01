#!/usr/bin/env python3
"""Fail-closed validation for the 16-slide v11 conference deck."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import zipfile

from PIL import Image, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pypdf import PdfReader
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "presentation/final"
PPTX = FINAL / "presentation.pptx"
PDF = FINAL / "presentation.pdf"
TITLES = [
    "온디바이스 sLLM을 위한 K26–Memory FPGA 후보 구조 평가",
    "오늘 답할 네 가지 질문",
    "1B는 4GB에 들어갔다—연구 질문을 바꿨다",
    "계산은 K26, 공급은 Memory FPGA 후보",
    "실제 가중치 타일이 논리 폐루프 RTL을 통과했다",
    "정적 로컬 큐는 지역성을 지키지만 작업대를 놀린다",
    "이득이 이동 비용보다 클 때만 훔친다",
    "Gemma 그래프를 의존성 있는 802개 TileJob으로 변환",
    "동일 작업·동일 시드에서 S1과 S3만 바꿨다",
    "효과는 부하 불균형과 초기 배치에 조건부",
    "작업 훔치기는 병목을 없애지 않고 이동시킨다",
    "이번 민감도에서는 K26 로컬이 우선이다",
    "KiCad 결과는 참조 라우팅 쿠폰이다",
    "한계와 향후 탐구 방향",
    "결론 및 기여",
    "Q&A",
]
FONT_REGULAR = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    required = [
        PPTX,
        PDF,
        FINAL / "speaker_notes.md",
        FINAL / "outline.md",
        FINAL / "slide_source_index.md",
        FINAL / "slide_contact_sheet.png",
        FINAL / "presentation.mp4",
        FINAL / "presentation.gif",
        FINAL / "animation_manifest.md",
        ROOT / "research/v11_research_freeze.json",
    ]
    for stem in ("tile_dataflow", "work_stealing_sequence", "scheduler_timeline", "bottleneck_migration"):
        required.extend((FINAL / "assets" / f"{stem}.mp4", FINAL / "assets" / f"{stem}.gif", FINAL / "assets" / f"{stem}_frame.png"))
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    with zipfile.ZipFile(PPTX) as package:
        if package.testzip():
            fail("PPTX ZIP contains a corrupt entry")
        movies = [name for name in package.namelist() if name.startswith("ppt/media/") and name.endswith(".mp4")]
        if len(movies) != 4:
            fail(f"expected four embedded Manim movies, got {len(movies)}")

    prs = Presentation(PPTX)
    if len(prs.slides) != 16:
        fail(f"expected 16 slides, got {len(prs.slides)}")
    if abs(prs.slide_width / prs.slide_height - 16 / 9) > 0.002:
        fail("deck is not 16:9")

    min_font = 999.0
    checked_runs = 0
    pictures = 0
    media = 0
    slide_w, slide_h = prs.slide_width, prs.slide_height
    tolerance = 2 * 914400 / 144
    cmaps = {
        False: TTFont(FONT_REGULAR).getBestCmap(),
        True: TTFont(FONT_BOLD).getBestCmap(),
    }
    for index, (slide, title) in enumerate(zip(prs.slides, TITLES), 1):
        texts = [shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        screen = " ".join(value.replace("\n", " ") for value in texts)
        if title not in screen:
            fail(f"slide {index}: title missing")
        if index == 16:
            allowed = {"Q&A", "질문 받겠습니다", "감사합니다"}
            visible = {value.strip() for value in texts if value.strip()}
            if not visible.issubset(allowed):
                fail(f"slide 16: detailed Q&A content must stay in speaker notes: {sorted(visible - allowed)!r}")
        notes = slide.notes_slide.notes_text_frame.text.strip()
        if not notes.startswith("기억할 문장:"):
            fail(f"slide {index}: notes do not start with memory sentence")
        if any(token in screen for token in ("-15.07%", "-14.61%", "-18.12%", "-37.84%", "+0.98%", "5,856")):
            fail(f"slide {index}: obsolete v10 result is visible")
        if "□" in screen or "−" in screen:
            fail(f"slide {index}: unsupported/rejected glyph is visible")
        pictures += sum(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes)
        media += sum(shape.shape_type == MSO_SHAPE_TYPE.MEDIA for shape in slide.shapes)
        for shape in slide.shapes:
            if shape.left < -tolerance or shape.top < -tolerance or shape.left + shape.width > slide_w + tolerance or shape.top + shape.height > slide_h + tolerance:
                fail(f"slide {index}: shape outside canvas: {shape.name}")
            if not getattr(shape, "has_text_frame", False) or not shape.text.strip():
                continue
            explicit_lines = max(1, shape.text.count("\n") + 1)
            run_sizes = [run.font.size.pt for paragraph in shape.text_frame.paragraphs for run in paragraph.runs if run.text.strip() and run.font.size]
            if run_sizes:
                estimated_height_px = explicit_lines * max(run_sizes) * 2 * 1.08
                shape_height_px = shape.height / 914400 * 144
                if estimated_height_px > shape_height_px * 1.04:
                    fail(f"slide {index}: vertical text overflow risk: {shape.text!r}")
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if not run.text.strip() or run.font.size is None:
                        continue
                    size = run.font.size.pt
                    min_font = min(min_font, size)
                    checked_runs += 1
                    if size < 11.5:
                        fail(f"slide {index}: text below 12pt: {run.text!r}")
                    face = ImageFont.truetype(FONT_BOLD if run.font.bold else FONT_REGULAR, max(10, round(size * 2)))
                    missing = sorted({char for char in run.text if not char.isspace() and ord(char) not in cmaps[bool(run.font.bold)]})
                    if missing:
                        fail(f"slide {index}: font lacks glyphs {missing!r} in {run.text!r}")
                    width_px = shape.width / 914400 * 144
                    for line in run.text.splitlines() or [run.text]:
                        if line == "▶":
                            continue
                        if face.getlength(line) > width_px * 1.02:
                            fail(f"slide {index}: horizontal text overflow risk: {line!r}")

    if media != 4:
        fail(f"expected four movie shapes, got {media}")
    if pictures != 10:
        fail(f"expected ten scoped raster pictures, got {pictures}")
    if len(PdfReader(str(PDF)).pages) != 16:
        fail("PDF does not have 16 pages")
    pngs = sorted((FINAL / "slides").glob("slide_*.png"))
    if len(pngs) != 16:
        fail(f"expected 16 slide PNGs, got {len(pngs)}")
    for path in pngs:
        with Image.open(path) as image:
            if image.size != (1920, 1080):
                fail(f"wrong slide PNG size: {path.name} {image.size}")

    notes_md = (FINAL / "speaker_notes.md").read_text(encoding="utf-8")
    if notes_md.count("기억할 문장:") != 16:
        fail("speaker notes must contain 16 memory sentences")
    for field in ("그림 설명 순서:", "예상 질문:", "답변 핵심:", "해석 경계:", "주의할 표현:"):
        if notes_md.count(field) != 16:
            fail(f"speaker notes must contain 16 {field} entries")
    for rubric in ("주제 이해도 30점", "전달성 10점", "질의응답 20점", "참여도 5점"):
        if rubric not in notes_md:
            fail(f"speaker notes missing final-round rubric: {rubric}")
    durations = re.findall(r"\((\d+):(\d{2})\)", notes_md)
    total_seconds = sum(int(minutes) * 60 + int(seconds) for minutes, seconds in durations)
    if total_seconds != 590:
        fail(f"speaker-note target is {total_seconds}s, expected 590s")
    spoken = "".join(re.findall(r"(?:발화문|전환): (.*)", notes_md)).replace(" ", "")
    estimated_seconds = len(spoken) / 275 * 60
    if not 560 <= estimated_seconds <= 590:
        fail(f"script reading estimate {estimated_seconds:.1f}s outside 9:20–9:50")

    source_index = (FINAL / "slide_source_index.md").read_text(encoding="utf-8")
    for index in range(1, 17):
        if f"| {index} |" not in source_index:
            fail(f"source index missing slide {index}")
    for header in ("원본 CSV", "생성·검증 스크립트", "허용 해석", "금지 해석"):
        if header not in source_index:
            fail(f"source index missing {header}")

    audit = {
        "status": "PASS",
        "slides": 16,
        "aspect_ratio": "16:9",
        "embedded_manim_movies": media,
        "scoped_raster_pictures": pictures,
        "checked_text_runs": checked_runs,
        "minimum_font_pt": min_font,
        "out_of_bounds_shapes": 0,
        "obsolete_v10_screen_values": 0,
        "speaker_note_memory_sentences": 16,
        "speaker_note_visual_orders": 16,
        "speaker_note_expected_questions": 16,
        "final_round_rubric_mapped": True,
        "target_duration_seconds": total_seconds,
        "script_estimate_seconds_at_275_chars_per_minute": round(estimated_seconds, 1),
        "rendered_png_size": [1920, 1080],
    }
    (FINAL / "layout_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"validated: 16 slides, 4 embedded movies, 16 notes, {total_seconds}s target, {estimated_seconds:.1f}s reading estimate, minimum {min_font:.1f}pt")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
