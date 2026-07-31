#!/usr/bin/env python3
"""Validate the final editable conference deck and its companion artifacts."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import zipfile

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "presentation" / "final"
PPTX = FINAL / "presentation.pptx"
PDF = FINAL / "presentation.pdf"
EXPECTED_TITLES = [
    "Work Stealing으로 줄이는 Tail Latency",
    "왜 정적 큐가 Tail을 만드는가",
    "K26 Compute × Memory FPGA",
    "유휴 클러스터가 일을 훔치는 5단계",
    "실제 Gemma 작업을 TileJob으로 바꾼다",
    "놀고 있던 연산 클러스터가 Tail을 줄인다",
    "Tail은 얼마나 줄었나",
    "Work Stealing은 병목을 없애지 않고 이동시킨다",
    "알고리즘을 실제 보드 인터페이스로 내렸다",
    "조건을 찾았고, 다음은 폐루프 검증이다",
]


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
        FINAL / "assets" / "tile_dataflow.mp4",
        FINAL / "assets" / "tile_dataflow.gif",
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
        if index not in (1, 9) and pictures:
            fail(f"slide {index}: unexpected raster picture")
        if index == 9 and pictures != 4:
            fail(f"slide 9: expected main KiCad render plus three crops, got {pictures}")

        screen_text = " ".join(normalized)
        required_screen_text = {
            5: ("Gemma replay", "합성 스트레스", "별도 작업 집합"),
            6: ("제어된 치우침 스트레스", "큐 대기", "데이터 준비", "밝은 끝 연산"),
            7: ("제어된 치우침 스트레스", "5개 seed 중앙값", "분석 모델"),
            8: ("Tail 감소", "p95 · S3 vs S1", "완료시간 · S3 vs S2"),
            9: ("기준 클록 차동쌍", "쿠폰 ERC 0", "부분 DRC 0", "NOT FOR FABRICATION"),
        }
        for phrase in required_screen_text.get(index, ()):
            if phrase not in screen_text:
                fail(f"slide {index}: required screen qualifier missing: {phrase}")

    if total_pictures != 5:
        fail(f"expected five raster pictures in whole deck, got {total_pictures}")

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

    print(
        "validated: 10 slides, 16:9, 10 notes, 10:00 timing, "
        "10 PDF pages, 10 PNGs, editable visuals with five scoped raster images"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
