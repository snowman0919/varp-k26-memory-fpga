#!/usr/bin/env python3
"""Validate the final editable conference deck and its companion artifacts."""

from __future__ import annotations

from pathlib import Path
import json
import re
import sys
import zipfile

from PIL import Image
from PIL import ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "presentation" / "final"
PPTX = FINAL / "presentation.pptx"
PDF = FINAL / "presentation.pdf"
EXPECTED_TITLES = [
    "정적 큐의 Tail을 줄이는 Work Stealing",
    "연구 질문: 지역성과 부하 균형을 함께 얻을 수 있는가",
    "연구 대상 구조와 구현 경계",
    "지역성 비용을 반영한 Work Stealing",
    "실제 Gemma graph에서 평가 작업을 만든다",
    "동일 조건에서 S1과 S3의 실행을 비교한다",
    "실제 Gemma replay에서도 Tail이 감소했다",
    "Tail 감소의 비용은 원격 이동이다",
    "물리 참조 설계로 다음 검증 범위를 고정했다",
    "기여와 한계: 조건부 효과를 규명했다",
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
        FINAL / "slide_source_index.md",
        FINAL / "slide_contact_sheet.png",
        FINAL / "assets" / "work_stealing_sequence.mp4",
        FINAL / "assets" / "work_stealing_sequence.gif",
        FINAL / "assets" / "work_stealing_storyboard.png",
        FINAL / "assets" / "tile_dataflow.mp4",
        FINAL / "assets" / "tile_dataflow.gif",
        FINAL / "assets" / "scheduler_timeline.mp4",
        FINAL / "assets" / "scheduler_timeline.gif",
        FINAL / "assets" / "tail_latency_results.mp4",
        FINAL / "assets" / "tail_latency_results.gif",
        FINAL / "assets" / "bottleneck_migration.mp4",
        FINAL / "assets" / "bottleneck_migration.gif",
        FINAL / "presentation.mp4",
        FINAL / "presentation.gif",
        FINAL / "animation_manifest.md",
        ROOT / "research" / "final_research_freeze.json",
    ]
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    with zipfile.ZipFile(PPTX) as package:
        bad = package.testzip()
        if bad:
            fail(f"corrupt pptx entry: {bad}")

    prs = Presentation(PPTX)
    if len(prs.slides) != 10:
        fail(f"expected 10 slides, got {len(prs.slides)}")
    if abs(prs.slide_width / prs.slide_height - 16 / 9) > 0.002:
        fail("deck is not 16:9")

    notes_markers = 0
    total_pictures = 0
    checked_text_shapes = 0
    checked_text_runs = 0
    minimum_font_pt = 999.0
    slide_w, slide_h = prs.slide_width, prs.slide_height
    for index, (slide, expected_title) in enumerate(zip(prs.slides, EXPECTED_TITLES), 1):
        texts = [shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        normalized = [text.replace("\n", " ") for text in texts]
        if not any(expected_title in text for text in normalized):
            fail(f"slide {index}: title missing")
        notes = slide.notes_slide.notes_text_frame.text.strip()
        if not notes.startswith("기억할 문장:"):
            fail(f"slide {index}: speaker note does not start with memory sentence")
        notes_markers += 1
        pictures = sum(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes)
        total_pictures += pictures
        if index not in (1, 4, 9) and pictures:
            fail(f"slide {index}: unexpected raster picture")
        if index == 4 and pictures != 1:
            fail(f"slide 4: expected one Manim still, got {pictures}")
        if index == 9 and pictures != 4:
            fail(f"slide 9: expected main KiCad render plus three crops, got {pictures}")

        tolerance = 2 * 914400 / 144
        for shape in slide.shapes:
            if shape.left < -tolerance or shape.top < -tolerance or shape.left + shape.width > slide_w + tolerance or shape.top + shape.height > slide_h + tolerance:
                fail(f"slide {index}: shape outside canvas: {shape.name}")
            if not getattr(shape, "has_text_frame", False) or not shape.text.strip():
                continue
            checked_text_shapes += 1
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if not run.text.strip() or run.font.size is None:
                        continue
                    size_pt = run.font.size.pt
                    checked_text_runs += 1
                    minimum_font_pt = min(minimum_font_pt, size_pt)
                    if size_pt < 11.5:
                        fail(f"slide {index}: text below 12 pt: {run.text!r} {size_pt:.1f}")
                    face = ImageFont.truetype(FONT_BOLD if run.font.bold else FONT_REGULAR, max(10, round(size_pt * 2)))
                    width_px = shape.width / 914400 * 144
                    for line in run.text.splitlines() or [run.text]:
                        measured = face.getlength(line)
                        if measured > width_px * 0.96:
                            fail(f"slide {index}: horizontal text overflow risk in {shape.name}: {line!r}")
            line_count = max(1, shape.text.count("\n") + 1)
            sizes = [run.font.size.pt for p in shape.text_frame.paragraphs for run in p.runs if run.font.size]
            if sizes:
                needed_px = line_count * max(sizes) * 2 * 1.08
                height_px = shape.height / 914400 * 144
                if needed_px > height_px * 1.05:
                    fail(f"slide {index}: vertical text overflow risk in {shape.name}")

        text_shapes = [shape for shape in slide.shapes if getattr(shape, "has_text_frame", False) and shape.text.strip()]
        for left_index, left in enumerate(text_shapes):
            for right in text_shapes[left_index + 1 :]:
                overlap_left = max(left.left, right.left)
                overlap_top = max(left.top, right.top)
                overlap_right = min(left.left + left.width, right.left + right.width)
                overlap_bottom = min(left.top + left.height, right.top + right.height)
                if overlap_right <= overlap_left or overlap_bottom <= overlap_top:
                    continue
                overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
                smaller_area = min(left.width * left.height, right.width * right.height)
                if overlap_area / smaller_area > 0.05:
                    fail(f"slide {index}: overlapping text boxes: {left.name} / {right.name}")

        screen_text = " ".join(normalized)
        required_screen_text = {
            5: ("Gemma replay", "합성 스트레스", "별도 작업 집합"),
            6: ("동일 1,000-job stream", "큐 대기", "데이터 준비", "밝은 연산"),
            7: ("실제 Gemma projection ledger", "별도 skew stress", "-15.07%", "-14.61%", "-18.12%"),
            8: ("Tail 감소", "p95 · S3 vs S1", "완료시간 · S3 vs S2", "S2/S3 p95 순위 역전"),
            9: ("기준 클록 차동쌍", "ERC 0", "부분 DRC 0", "NOT FOR FABRICATION"),
        }
        for phrase in required_screen_text.get(index, ()):
            if phrase not in screen_text:
                fail(f"slide {index}: required screen qualifier missing: {phrase}")

    if total_pictures != 6:
        fail(f"expected six scoped raster pictures in whole deck, got {total_pictures}")

    reader = PdfReader(str(PDF))
    if len(reader.pages) != 10:
        fail(f"expected 10 PDF pages, got {len(reader.pages)}")

    slide_pngs = sorted((FINAL / "slides").glob("slide_*.png"))
    if len(slide_pngs) != 10:
        fail(f"expected 10 slide PNGs, got {len(slide_pngs)}")
    for path in slide_pngs:
        with Image.open(path) as image:
            if image.size != (1920, 1080):
                fail(f"unexpected PNG size: {path.name} {image.size}")
    with Image.open(FINAL / "slide_contact_sheet.png") as sheet:
        if sheet.width < 1000 or sheet.height < 1500:
            fail("contact sheet is unexpectedly small")

    notes_md = (FINAL / "speaker_notes.md").read_text(encoding="utf-8")
    if notes_md.count("기억할 문장:") != 10:
        fail("speaker_notes.md must contain 10 memory sentences")
    durations = re.findall(r"\((\d+):(\d{2})\)", notes_md)
    seconds = sum(int(minutes) * 60 + int(secs) for minutes, secs in durations)
    if seconds != 600:
        fail(f"speaker notes timing is {seconds}s, expected 600s")

    source_index = (FINAL / "slide_source_index.md").read_text(encoding="utf-8")
    for index in range(1, 11):
        if f"| {index} |" not in source_index:
            fail(f"source index missing slide {index}")
    required_headers = ("원본 CSV", "생성·검증 스크립트", "허용 해석", "금지 해석")
    for header in required_headers:
        if header not in source_index:
            fail(f"source index missing column: {header}")

    audit = {
        "status": "PASS",
        "slides": len(prs.slides),
        "aspect_ratio": "16:9",
        "rendered_png_size": [1920, 1080],
        "checked_text_shapes": checked_text_shapes,
        "checked_text_runs": checked_text_runs,
        "minimum_font_pt": minimum_font_pt,
        "out_of_bounds_shapes": 0,
        "horizontal_text_overflow_risks": 0,
        "vertical_text_overflow_risks": 0,
        "overlapping_text_box_pairs": 0,
        "scoped_raster_pictures": total_pictures,
        "speaker_note_memory_sentences": notes_markers,
        "duration_seconds": seconds,
    }
    (FINAL / "layout_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "validated: 10 slides, 16:9, 10 notes, 10:00 timing, "
        "10 PDF pages, 10 PNGs, bounded text geometry, editable visuals with six scoped raster images"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
