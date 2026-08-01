#!/usr/bin/env python3
"""Fail-closed validation for the 17-slide final-round conference deck."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import zipfile

from PIL import Image, ImageFont
from fontTools.ttLib import TTFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "presentation/final"
PPTX = FINAL / "presentation.pptx"
PDF = FINAL / "presentation.pdf"
TITLES = [
    "온디바이스 sLLM용 K26–Memory FPGA 가속기 설계",
    "오늘 답할 네 가지 질문",
    "1B 모델은 4GB에 들어갔다—그래서 질문을 바꿨다",
    "계산과 가중치 공급을 두 장치로 분리했다",
    "메모리 용량만 늘리지 않고 작업 배치와 데이터 위치를 함께 설계했다",
    "실제 Gemma 가중치를 MatVec RTL에서 검증했다",
    "정적 배정은 데이터를 가까이 두지만 작업을 고르게 나누지 못한다",
    "빈 연산기가 이득이 있는 작업만 가져온다",
    "Gemma 그래프를 802개 연산 타일로 나누고 단계 의존 규칙을 부여했다",
    "같은 작업에서 정적 배정과 작업 재분배만 비교했다",
    "작업이 치우친 경우에만 재분배가 효과적이었다",
    "유휴 연산은 줄었지만 데이터 이동이 새로운 비용이 됐다",
    "현재 모델 가정에서는 K26 로컬 경로가 유리했다",
    "핵심 인터페이스를 실제 PCB 객체로 구체화했다",
    "다음 단계는 분석 모델을 실제 하드웨어 경로로 닫는 것이다",
    "결론과 기여",
    "질문과 토론",
]
MOVIES = ("tile_dataflow", "work_stealing_sequence", "scheduler_timeline", "tail_latency_results", "bottleneck_migration")
FONT_REGULAR = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    required = [
        PPTX, PDF, FINAL / "speaker_notes.md", FINAL / "outline.md",
        FINAL / "slide_source_index.md", FINAL / "qna_bank.md",
        FINAL / "peer_question_bank.md", FINAL / "review_report.md",
        FINAL / "slide_contact_sheet.png", FINAL / "presentation.mp4",
        FINAL / "presentation.gif", FINAL / "animation_manifest.md",
        ROOT / "research/v11_research_freeze.json",
    ]
    for stem in MOVIES:
        required += [FINAL / "assets" / f"{stem}.mp4", FINAL / "assets" / f"{stem}.gif", FINAL / "assets" / f"{stem}_frame.png"]
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    with zipfile.ZipFile(PPTX) as package:
        if package.testzip():
            fail("PPTX ZIP contains a corrupt entry")
        movies = [name for name in package.namelist() if name.startswith("ppt/media/") and name.endswith(".mp4")]
        if len(movies) != len(MOVIES):
            fail(f"expected {len(MOVIES)} embedded Manim movies, got {len(movies)}")

    prs = Presentation(PPTX)
    if len(prs.slides) != 17:
        fail(f"expected 17 slides, got {len(prs.slides)}")
    if abs(prs.slide_width / prs.slide_height - 16 / 9) > 0.002:
        fail("deck is not 16:9")

    min_font = 999.0
    checked_runs = pictures = media = 0
    slide_w, slide_h = prs.slide_width, prs.slide_height
    tolerance = 2 * 914400 / 144
    cmaps = {False: TTFont(FONT_REGULAR).getBestCmap(), True: TTFont(FONT_BOLD).getBestCmap()}
    forbidden = re.compile(r"\b(candidate|bounded|replay|payload|contract|actual|full-overlap)\b", re.IGNORECASE)
    for index, (slide, title) in enumerate(zip(prs.slides, TITLES), 1):
        texts = [shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        screen = " ".join(value.replace("\n", " ") for value in texts)
        if title not in screen:
            fail(f"slide {index}: title missing")
        if index == 17:
            allowed = {"질문과 토론", "감사합니다"}
            visible = {value.strip() for value in texts if value.strip()}
            if not visible.issubset(allowed):
                fail(f"slide 17: Q&A detail must be presenter-only: {sorted(visible - allowed)!r}")
        notes = slide.notes_slide.notes_text_frame.text.strip()
        if not notes.startswith("기억할 문장:"):
            fail(f"slide {index}: notes do not start with memory sentence")
        if forbidden.search(screen):
            fail(f"slide {index}: internal/developer term is visible: {forbidden.search(screen).group(0)!r}")
        if any(token in screen for token in ("-15.07%", "-14.61%", "-18.12%", "-37.84%", "+0.98%", "5,856")):
            fail(f"slide {index}: obsolete result is visible")
        if "□" in screen or "−" in screen:
            fail(f"slide {index}: unsupported glyph is visible")
        if "TileJob" in screen and index != 4:
            fail(f"slide {index}: TileJob may appear only at the first-definition slide")
        if re.search(r"\bS1\b", screen) and index != 7:
            fail(f"slide {index}: S1 may appear only at its first-definition slide")
        if re.search(r"\bS3\b", screen) and index != 8:
            fail(f"slide {index}: S3 may appear only at its first-definition slide")
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
                estimated_height_px = explicit_lines * max(run_sizes) * 2 * 1.05
                shape_height_px = shape.height / 914400 * 144
                if estimated_height_px > shape_height_px * 1.06:
                    fail(f"slide {index}: vertical text overflow risk: {shape.text!r}")
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if not run.text.strip() or run.font.size is None:
                        continue
                    size = run.font.size.pt
                    min_font = min(min_font, size)
                    checked_runs += 1
                    floor = 9.5 if shape.top / 914400 * 144 >= 995 else 11.5
                    if size < floor:
                        fail(f"slide {index}: text below {floor:.0f}pt: {run.text!r}")
                    bold = bool(run.font.bold)
                    face = ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, max(10, round(size * 2)))
                    missing = sorted({char for char in run.text if not char.isspace() and ord(char) not in cmaps[bold]})
                    if missing:
                        fail(f"slide {index}: font lacks glyphs {missing!r} in {run.text!r}")
                    width_px = shape.width / 914400 * 144
                    for line in run.text.splitlines() or [run.text]:
                        if line != "▶" and face.getlength(line) > width_px * 1.03:
                            fail(f"slide {index}: horizontal text overflow risk: {line!r}")

    if media != 5:
        fail(f"expected five movie shapes, got {media}")
    if pictures != 11:
        fail(f"expected eleven scoped raster pictures, got {pictures}")
    if len(PdfReader(str(PDF)).pages) != 17:
        fail("PDF does not have 17 pages")
    pngs = sorted((FINAL / "slides").glob("slide_*.png"))
    if len(pngs) != 17:
        fail(f"expected 17 slide PNGs, got {len(pngs)}")
    for path in pngs:
        with Image.open(path) as image:
            if image.size != (1920, 1080):
                fail(f"wrong slide PNG size: {path.name} {image.size}")

    notes_md = (FINAL / "speaker_notes.md").read_text(encoding="utf-8")
    if notes_md.count("기억할 문장:") != 17:
        fail("speaker notes must contain 17 memory sentences")
    for field in ("목표 시간:", "그림 설명 순서:", "예상 질문:", "20초 답변:", "근거 파일:", "해석 경계:", "주의할 표현:"):
        if notes_md.count(field) != 17:
            fail(f"speaker notes must contain 17 {field} entries")
    for rubric in ("주제 이해도 30점", "전달성 10점", "질의응답 20점", "참여도 5점"):
        if rubric not in notes_md:
            fail(f"speaker notes missing final-round rubric: {rubric}")
    durations = re.findall(r"^## Slide \d+:.+\((\d+):(\d{2})\)$", notes_md, flags=re.MULTILINE)
    total_seconds = sum(int(minutes) * 60 + int(seconds) for minutes, seconds in durations)
    if total_seconds != 575:
        fail(f"speaker-note target is {total_seconds}s, expected 575s")
    spoken_sections = re.findall(r"^발화문: (.+)$|^전환: (.+)$", notes_md, flags=re.MULTILINE)
    spoken = "".join((a or b) for a, b in spoken_sections[:-2]).replace(" ", "")
    estimated_seconds = len(spoken) / 275 * 60
    if not 540 <= estimated_seconds <= 610:
        fail(f"script reading estimate {estimated_seconds:.1f}s is implausible for 9:35")

    source_index = (FINAL / "slide_source_index.md").read_text(encoding="utf-8")
    for index in range(1, 18):
        if f"| {index} |" not in source_index:
            fail(f"source index missing slide {index}")
    for header in ("원본 CSV", "생성·검증 스크립트", "허용 해석", "금지 해석"):
        if header not in source_index:
            fail(f"source index missing {header}")

    qna = (FINAL / "qna_bank.md").read_text(encoding="utf-8")
    if qna.count("**20초 핵심 답변:**") < 40 or qna.count("**60초 확장 답변:**") < 40:
        fail("presenter Q&A bank must contain at least 40 complete questions")
    for attack in ("1B가 4GB에 들어가는데", "실제 FPGA 성능", "Work Stealing은 기존 기술", "왜 중앙 큐", "더 느린가", "GB/s와 cycle은 실측", "PCB는 제작", "전체 FPGA 경로", "연구가 실패"):
        if attack not in qna:
            fail(f"Q&A bank missing attack question: {attack}")
    peer = (FINAL / "peer_question_bank.md").read_text(encoding="utf-8")
    if len(re.findall(r"^## \d+\.", peer, flags=re.MULTILINE)) < 10:
        fail("peer question bank must contain at least ten questions")
    for field in ("AI 모델", "하드웨어", "데이터 분석", "웹·서비스", "보안", "로보틱스"):
        if field not in peer:
            fail(f"peer question bank missing field: {field}")

    audit = {
        "status": "PASS", "slides": 17, "aspect_ratio": "16:9",
        "embedded_manim_movies": media, "scoped_raster_pictures": pictures,
        "checked_text_runs": checked_runs, "minimum_font_pt": min_font,
        "out_of_bounds_shapes": 0, "obsolete_screen_values": 0,
        "speaker_note_memory_sentences": 17, "target_duration_seconds": total_seconds,
        "script_estimate_seconds_at_275_chars_per_minute": round(estimated_seconds, 1),
        "qna_questions": qna.count("**20초 핵심 답변:**"),
        "peer_questions": len(re.findall(r"^## \d+\.", peer, flags=re.MULTILINE)),
        "rendered_png_size": [1920, 1080],
    }
    (FINAL / "layout_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"validated: 17 slides, 5 movies, 17 notes, {total_seconds}s target, {estimated_seconds:.1f}s reading estimate, minimum {min_font:.1f}pt")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
