#!/usr/bin/env python3
"""Validate the maintained Korean study sources and render one PDF.

The Markdown files in ``study/`` are authoritative.  This builder deliberately
does not embed a second copy of their text, which previously allowed the study
pack to overwrite corrected research claims with an obsolete snapshot.
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab import rl_config
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "study"
PDF = OUT / "study_pack.pdf"
rl_config.invariant = 1

REQUIRED = ["README.md"] + [f"{index:02d}_{name}.md" for index, name in enumerate((
    "one_page_summary",
    "concept_map",
    "paper_walkthrough",
    "slide_walkthrough",
    "glossary",
    "structures_and_dataflow",
    "experiment_and_metrics",
    "power_cost_and_energy",
    "kicad_and_physical_scope",
    "claim_boundary",
    "qna_bank",
    "whiteboard_explanations",
    "interview_script",
    "self_quiz",
    "misconceptions",
))]

FORBIDDEN = (
    "18.12%",
    "37.84%",
    "22.16%",
    "183×32=5,856",
    "DDR response→link receive→payload store→MatVec의 닫힌 end-to-end 경로는 아직 없다",
)

REQUIRED_FACTS = (
    "19.13%",
    "35.49%",
    "802",
    "25,664",
    "K26 로컬",
    "논리",
    "GTH",
    "MIG",
)


def validate() -> list[Path]:
    paths = [OUT / name for name in REQUIRED]
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.exists()]
    if missing:
        raise SystemExit(f"missing study sources: {missing}")

    corpus = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    stale = [token for token in FORBIDDEN if token in corpus]
    if stale:
        raise SystemExit(f"obsolete study claims remain: {stale}")
    absent = [token for token in REQUIRED_FACTS if token not in corpus]
    if absent:
        raise SystemExit(f"required v11 facts missing: {absent}")

    qna = (OUT / "10_qna_bank.md").read_text(encoding="utf-8")
    count = len(re.findall(r"^## Q\d+\.", qna, flags=re.MULTILINE))
    if count < 80:
        raise SystemExit(f"Q&A count {count} < 80")
    if "논리 RTL 데이터 흐름은 닫혔지만" not in qna:
        raise SystemExit("Q&A must distinguish the closed logical loop from the open physical path")
    return paths


def register_font() -> str:
    candidates = (
        Path("/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            try:
                pdfmetrics.registerFont(TTFont("StudyKorean", str(candidate)))
                pdfmetrics.registerFontFamily(
                    "StudyKorean",
                    normal="StudyKorean",
                    bold="StudyKorean",
                    italic="StudyKorean",
                    boldItalic="StudyKorean",
                )
                return "StudyKorean"
            except Exception:
                continue
    raise SystemExit("Korean PDF font not found")


def clean_inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r"<font name='StudyKorean'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


def render(paths: list[Path]) -> None:
    font = register_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle("BodyKO", parent=styles["BodyText"], fontName=font, fontSize=9.2, leading=14, spaceAfter=4)
    h1 = ParagraphStyle("H1KO", parent=body, fontSize=18, leading=23, spaceAfter=10, alignment=TA_CENTER)
    h2 = ParagraphStyle("H2KO", parent=body, fontSize=13, leading=17, spaceBefore=8, spaceAfter=5)
    h3 = ParagraphStyle("H3KO", parent=body, fontSize=11, leading=15, spaceBefore=5, spaceAfter=3)
    code = ParagraphStyle("CodeKO", parent=body, fontName=font, fontSize=7.3, leading=10, leftIndent=8 * mm)
    story = []
    for file_index, path in enumerate(paths):
        if file_index:
            story.append(PageBreak())
        in_code = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            if line.startswith("```"):
                in_code = not in_code
                continue
            if not line:
                story.append(Spacer(1, 2.5 * mm))
                continue
            if in_code:
                story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), code))
            elif line.startswith("### "):
                story.append(Paragraph(clean_inline(line[4:]), h3))
            elif line.startswith("## "):
                story.append(Paragraph(clean_inline(line[3:]), h2))
            elif line.startswith("# "):
                story.append(Paragraph(clean_inline(line[2:]), h1))
            elif line.startswith("- "):
                story.append(Paragraph("• " + clean_inline(line[2:]), body))
            elif re.match(r"^\d+\. ", line):
                story.append(Paragraph(clean_inline(line), body))
            elif line.startswith("|"):
                story.append(Paragraph(clean_inline(line.strip("| ").replace("|", " · ")), body))
            else:
                story.append(Paragraph(clean_inline(line), body))

    document = SimpleDocTemplate(
        str(PDF), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="VARP v11 연구 발표 스터디팩", author="VARP",
    )
    document.build(story)


def main() -> None:
    paths = validate()
    render(paths)
    print(f"validated {len(paths)} study sources; rendered {PDF.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
