#!/usr/bin/env python3
"""Build the 14-slide v11 Korean conference deck.

The presentation keeps text, diagrams, bars, arrows, and annotations editable.
Raster media is limited to a decorative cover, Manim fallback frames, the
native KiCad render/crops, and the repository QR code.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches
from reportlab import rl_config
from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.pdfgen import canvas as pdf_canvas

from build_editable_deck import (
    AMBER,
    BG,
    BG2,
    BG3,
    BLUE,
    CYAN,
    GRID,
    H,
    MUTED,
    RED,
    SLIDES,
    TEAL,
    W,
    WHITE,
    SlideCanvas,
    font,
    inch,
    normalize_pptx,
    ppt_rgb,
    rgb,
)


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "presentation/final"
ASSETS = FINAL / "assets"
PPTX = FINAL / "presentation.pptx"
PDF = FINAL / "presentation.pdf"
REPO_URL = "https://github.com/snowman0919/varp-k26-memory-fpga"
SECTIONS = ("문제", "구조", "평가", "결론")


@dataclass(frozen=True)
class SlideMeta:
    title: str
    section: int
    conclusion: str
    duration: int
    memory: str
    speech: str
    transition: str
    supplement: str


META = (
    SlideMeta("온디바이스 sLLM을 위한 K26–Memory FPGA 후보 구조 평가", 0, "Gemma 3 1B 작업 부하에서 구조·배치·이동 비용의 채택 조건을 분석한다.", 25, "이 발표는 완성 제품이 아니라 K26–Memory FPGA 후보 구조의 설계 공간 평가입니다.", "온디바이스 sLLM에서 가중치를 어디에 두고 어떻게 공급할지를 연구했습니다. K26이 연산과 제어를 맡고 외부 Memory FPGA가 다채널 가중치 공급을 맡는 후보 구조를 만들고, 작업 훔치기(Work Stealing)가 유휴 연산을 줄이는 조건과 그때 생기는 데이터 이동 비용을 함께 분석했습니다.", "먼저 오늘 답할 질문을 보겠습니다.", "후보 구조·분석 결과이며 제작 완료 가속기를 뜻하지 않습니다."),
    SlideMeta("오늘 답할 네 가지 질문", 0, "필요성→구조→검증→채택 조건의 순서로 연구 질문에 답한다.", 25, "발표는 왜 검토했는지, 무엇을 설계했는지, 무엇을 확인했는지, 언제 채택할지의 순서입니다.", "첫째 외부 메모리 구조를 왜 검토했는가, 둘째 계산부와 가중치 공급부를 어떻게 나눴는가, 셋째 실제 Gemma 작업에서 무엇을 검증했는가, 마지막으로 어떤 조건에서 구조와 작업 훔치기가 유효한가를 답하겠습니다.", "출발점은 예상과 달랐던 용량 계산입니다.", "세부 조건은 발표자 노트와 출처 인덱스에 있습니다."),
    SlideMeta("1B는 4GB에 들어갔다—연구 질문을 바꿨다", 0, "외부 8GB의 가치는 용량보다 가중치 공급 분리와 유휴 연산 감소에서 검증해야 한다.", 45, "Gemma 1B의 2.43 GiB가 K26 4GB 안에 들어가므로 외부 메모리는 기본 요구가 아니라 조건부 후보입니다.", "INT8 가중치와 문맥 32K, 실행 여유를 합치면 약 2.43 GiB였습니다. 그래서 외부 8GB가 필요하다는 최초 가설을 버리고, 가중치 공급을 분리해 네 클러스터의 유휴를 줄이는 이득이 데이터 이동 비용보다 큰가로 질문을 바꿨습니다.", "이 질문을 두 FPGA의 역할 분리로 구체화했습니다.", "2.43 GiB는 용량 모델이며 보드 실측이 아닙니다."),
    SlideMeta("계산은 K26, 공급은 Memory FPGA 후보", 1, "TileJob이 네 연산 클러스터와 네 DDR3L 채널·논리 링크의 위치를 함께 추적한다.", 50, "K26은 연산·제어를, Memory FPGA 후보는 네 채널의 가중치 공급을 맡습니다.", "K26의 네 연산 클러스터와 로컬 큐가 TileJob을 실행합니다. 외부 후보는 네 DDR3L 채널과 네 논리 링크로 가중치를 공급합니다. TileJob의 선호 채널과 링크가 계산 위치와 데이터 위치를 연결합니다. 실선은 이번에 닫은 논리 경로, 점선 GTH·CDC·MIG는 후속 물리 경로입니다.", "실제 타일이 닫힌 논리 경로를 통과하는지 확인했습니다.", "4채널과 4링크는 후보 구조이며 물리 GTH/MIG는 미구현입니다."),
    SlideMeta("실제 가중치 타일이 논리 폐루프 RTL을 통과했다", 1, "DMA 응답 뒤에 MatVec이 실행되고 세 결과가 INT32 기준과 일치했다.", 45, "대표 Gemma 타일 세 개가 작업 수락부터 결과까지 닫힌 논리 경로를 통과했습니다.", "작업 수락, DMA 요청, 응답 경계, 논리 링크 FIFO, 작업 ID 결합, MatVec 결과를 하나의 상위 모듈로 연결했습니다. gate_proj, lm_head, o_proj 세 타일이 모두 INT32 기준과 일치했습니다. 이 실제 타일 시험은 1클러스터·1채널·S0이며, S3 작업 소유권 시험은 별도의 합성 스케줄러 시험 입력입니다. 응답은 MIG가 아니라 시험벤치 경계에서 주입했습니다.", "이제 동적 재분배가 필요한 정적 큐 문제를 보겠습니다.", "GTH·CDC·MIG 물리 타이밍과 작업 훔치기 결합 실험은 포함하지 않습니다."),
    SlideMeta("정적 로컬 큐는 지역성을 지키지만 작업대를 놀린다", 1, "한 큐가 길어지면 다른 클러스터가 비어 있어도 꼬리 작업은 기다린다.", 40, "정적 큐의 문제는 전체 자원 부족보다 작업 쏠림입니다.", "각 클러스터가 자기 큐만 처리하면 가중치 지역성은 좋습니다. 하지만 C0에 작업이 몰리면 C1부터 C3이 비어 있어도 도와주지 못하고, 뒤쪽 TileJob의 p95와 p99가 길어집니다.", "빈 작업대가 일을 가져오는 조건을 추가했습니다.", "이 화면은 개념이며 수치는 뒤의 동일 시드 실험에서 제시합니다."),
    SlideMeta("이득이 이동 비용보다 클 때만 훔친다", 1, "대기 감소가 가중치·활성값·부분합 이동 비용보다 큰 작업만 옮긴다.", 40, "S3 지역성 인식 작업 훔치기(Work Stealing)는 이동 비용을 서비스 시간에 직접 반영합니다.", "유휴 클러스터가 실행 가능한 작업을 찾고, 기다림 감소에서 데이터 이동 비용을 뺀 값이 양수일 때만 작업 소유권을 옮깁니다. S2는 가장 오래된 작업을 가져오지만 S3는 지역성 비용을 포함해 원격 이동량을 줄입니다.", "정책을 실제 Gemma 형상의 작업으로 바꾸겠습니다.", "영상은 정책 상태 전이이며 최적성이나 보드 타이밍을 뜻하지 않습니다."),
    SlideMeta("Gemma 그래프를 의존성 있는 802개 TileJob으로 변환", 2, "초기 배치와 나중 재분배의 효과를 분리한다.", 45, "그래프 형상과 단계·토큰 의존성, 네 초기 배치를 명시적으로 모델링했습니다.", "7,837개 그래프 노드에서 토큰당 183개 밀집 투영을 찾고 N≤1024 기준으로 802 TileJob을 만들었습니다. q/k/v 다음 o, MLP, 다음 계층, lm_head 뒤 다음 토큰 순서를 지켰습니다. 32토큰은 25,664 TileJob입니다. 네 초기 배치를 비교해 처음부터 잘 나눈 효과와 나중에 훔친 효과를 구분했습니다.", "같은 작업과 시드에서 정책만 바꾼 실행을 보겠습니다.", "802와 25,664는 그래프 형상과 명시한 타일 분할 규칙의 결과입니다."),
    SlideMeta("동일 작업·동일 시드에서 S1과 S3만 바꿨다", 2, "S1의 유휴·대기 구간이 S3에서는 원격 준비와 연산 구간으로 바뀐다.", 50, "실행 사건 CSV의 같은 작업을 대기·원격 준비·연산 구간으로 비교합니다.", "합성 편향 부하의 같은 1,000개 작업과 같은 시드에서 정책만 바꿨습니다. 대표 작업 훔치기 세 건을 확대해 도착부터 배치까지의 대기, 원격 복사, 연산, 완료를 색으로 구분했습니다. 모든 정책은 완료 ID와 작업 해시가 같고 중복과 누락이 없습니다.", "다섯 시드를 짝지은 꼬리 지연 결과를 보겠습니다.", "분석 사건이며 GTH·DDR 물리 사이클이 아닙니다."),
    SlideMeta("효과는 부하 불균형과 초기 배치에 조건부", 2, "편향 부하에서는 줄지만 Gemma의 기존 산술 배치에서는 오히려 늘 수 있다.", 50, "작업 훔치기는 남은 불균형이 큰 조건에서만 효과가 있습니다.", "합성 편향 부하에서 S3는 S1보다 TileJob p95를 19.13%, p99를 18.71% 줄였습니다. Gemma 형상에서는 기존 산술 배치가 p95를 0.28% 늘렸고 채널 친화 배치에서는 19.79% 줄였습니다. 보편적 우월성이 아니라 효과 조건을 분리한 결과입니다.", "이득과 함께 새로 생긴 비용을 보겠습니다.", "p95와 p99는 의존성 해제 뒤 TileJob 완료 분포이며 사용자 응답 지연이 아닙니다."),
    SlideMeta("작업 훔치기는 병목을 없애지 않고 이동시킨다", 2, "큐 대기는 줄지만 원격 복사와 링크·메모리 서비스가 새 비용이 된다.", 45, "비교 기준을 분리하면 꼬리 지연 감소와 이동량 감소가 완료시간 개선을 보장하지 않음을 볼 수 있습니다.", "S3 대 S1에서 p95는 19.13% 줄었습니다. S3 대 S2에서 원격 가중치는 35.49% 줄었지만 완료시간은 0.01% 늘어 사실상 같았습니다. 첫 비교는 정적 큐 효과, 두 번째는 지역성 점수 효과입니다.", "이제 전체 구조가 K26 로컬 기준선을 이기는지 보겠습니다.", "서로 다른 기준의 수치를 하나의 인과식으로 해석하지 않습니다."),
    SlideMeta("이번 민감도에서는 K26 로컬이 우선이다", 3, "시험한 대역폭 범위에서 외부 4채널 후보는 K26 로컬 완료시간을 이기지 못했다.", 45, "Gemma 1B의 기본 선택은 이번 분석 민감도에서 K26 로컬입니다.", "대표 중앙 조건에서 K26 로컬 9.6 GB/s는 약 24.6M사이클, 외부 4채널 6.4 GB/s는 약 120.6M사이클이었습니다. 모든 시험 범위에서 외부 후보가 로컬을 이기지 못했습니다. 외부 구조는 더 큰 모델, 더 긴 문맥, 실제 로컬 경합이 계측될 때 재평가해야 합니다.", "물리 후보를 어디까지 구체화했는지 보겠습니다.", "분석 모델의 민감도이며 보드 측정이나 주파수 환산값이 아닙니다."),
    SlideMeta("KiCad 결과는 참조 라우팅 쿠폰이다", 3, "실제 KiCad 객체와 일부 배선은 만들었지만 전체 제품 보드나 제작 자료는 아니다.", 45, "쿠폰은 경계 링크·기준 클록·DDR3L 한 슬라이스의 물리 질문을 구체화합니다.", "범용 경계 커넥터, DDR3L x16 한 슬라이스, GTH/기준 클록 일부 배선을 실제 KiCad 객체로 만들었습니다. 풋프린트 29개와 배선 20개, 선언된 쿠폰 범위의 ERC/DRC 0을 확인했지만 전체 116개 신호망 중 55개가 미배선이고 SI/PI/PDN도 남았습니다.", "기여와 다음 검증을 정리하겠습니다.", "REFERENCE COUPON이며 NOT FOR FABRICATION입니다."),
    SlideMeta("기여는 구조·비용 모델·재현 가능한 설계 흐름", 3, "현재 결과는 제한 RTL과 분석 모델이며 GitHub에서 전 과정을 재현할 수 있다.", 30, "핵심 기여는 역할 분리 구조, 이동 비용을 포함한 동적 배치, 모델→RTL→KiCad 재현 흐름입니다.", "계산과 가중치 공급의 역할을 분리했고, 이동 비용을 실제 서비스 시간에 넣어 동적 작업 배치를 평가했으며, 모델 형상에서 논리 RTL과 KiCad 쿠폰까지 이어지는 흐름을 공개했습니다. 다음 단계는 K26 로컬 보드 실측, GTH와 MIG 물리 폐루프, 전체 보드 전력과 비용입니다.", "이상으로 발표를 마치겠습니다. 질문 받겠습니다.", "재현 시작 명령은 `make setup && make reproduce`입니다."),
)

NOTE_EXTENSIONS = (
    "중심 질문은 어떤 배치와 부하에서 공급 분리의 이득이 이동 비용을 넘어서는가입니다.",
    "",
    "2.43 GiB에는 INT8 가중치, 문맥 32K의 KV, 실행 여유가 포함됩니다. 명목 용량에 들어간다는 사실만으로 실제 대역폭과 지연이 충분하다고 결론 내리지는 않습니다.",
    "실선은 RTL에서 작업 ID와 데이터가 이어지는 논리 경로이고, 빨간 물리 경로는 아직 구현하지 않은 GTH 직렬화, 클록 도메인 교차, 패킷, MIG를 뜻합니다.",
    "세 타일의 수락 사이클은 5, 89, 173이고 결과 사이클은 88, 172, 256입니다. 이 기능 시험은 1클러스터 S0이므로 작업 훔치기 성능 증거와 분리합니다.",
    "",
    "S3 지역성 인식 작업 훔치기는 가중치뿐 아니라 활성값, 부분합, 링크 묶음 불일치 비용도 포함합니다. 추가 전송량은 사후 통계가 아니라 서비스 시간에 직접 부과됩니다.",
    "",
    "J79, J90, J100의 숫자는 원본 사건 CSV에서 가져왔습니다. 구간 폭은 가독성을 위해 압축했지만 상자 안 사이클, 클러스터, 작업 ID는 원본과 같습니다.",
    "",
    "왼쪽은 정적 S1과 S3를 비교하고 오른쪽은 가장 오래된 작업 우선 S2와 S3를 비교합니다. 기준이 다르므로 세 수치를 하나의 연속 인과식으로 읽으면 안 됩니다.",
    "4.8, 9.6, 14.4 GB/s의 로컬과 3.2, 6.4, 12.8 GB/s의 외부 민감도를 비교했습니다. 전 범위에서 외부 후보가 로컬 완료시간을 이기지 못했습니다.",
    "화면의 J1·J2는 특정 K26나 Memory FPGA BGA 핀 배치가 아니라 범용 경계입니다. 미배선 55개와 SI·PI·PDN 관문 때문에 제작 대상으로 사용할 수 없습니다.",
    "현재 결론은 Gemma 1B는 K26 로컬 우선입니다. 외부 후보는 더 큰 모델, 긴 문맥, 실제 로컬 경합이 계측된 뒤 같은 실행 추적과 정확성 조건에서 다시 판단합니다.",
)


def add_progress(c: SlideCanvas, section: int) -> None:
    x0, y, width, gap = 1160, 42, 140, 14
    for index, label in enumerate(SECTIONS):
        color = CYAN if index == section else "#294057"
        c.rect(x0 + index * (width + gap), y, width, 7, color)
        c.text(label, x0 + index * (width + gap), 8, width, 28, size=12, color=color if index == section else MUTED, bold=index == section, align="center")


def header(c: SlideCanvas, meta: SlideMeta) -> None:
    c.rect(82, 56, 58, 7, CYAN)
    c.text(meta.title, 82, 82, 1680, 70, size=31, bold=True)
    c.text(meta.conclusion, 84, 156, 1690, 52, size=20, color=MUTED)
    add_progress(c, meta.section)


def arrow_between(c: SlideCanvas, x: int, y: int, w: int = 90, color: str = CYAN) -> None:
    c.chevron(x, y, w, 50, color)


def embedded_movie(c: SlideCanvas, stem: str, x: int, y: int, w: int, h: int) -> None:
    frame = ASSETS / f"{stem}_frame.png"
    movie = ASSETS / f"{stem}.mp4"
    c.image_file(frame, x, y, w, h, mode="contain")
    c.slide.shapes.add_movie(str(movie), inch(x), inch(y), inch(w), inch(h), poster_frame_image=str(frame), mime_type="video/mp4")
    c.rect(x, y, w, h, BG, stroke=CYAN, stroke_width=2, radius=10, alpha=0)
    c.circle(x + w - 90, y + h - 90, 58, CYAN)
    c.text("▶", x + w - 78, y + h - 83, 34, 34, size=20, color=BG, bold=True, align="center", valign="middle")


def metric(c: SlideCanvas, x: int, y: int, value: str, label: str, color: str, width: int = 430) -> None:
    c.text(value, x, y, width, 76, size=37, color=color, bold=True, align="center")
    c.text(label, x, y + 78, width, 44, size=17, color=MUTED, align="center")


def slide_1(c: SlideCanvas) -> None:
    c.image_file(ASSETS / "cover_background.png", 0, 0, W, H, mode="cover")
    c.rect(0, 0, 1250, H, BG, alpha=66)
    c.rect(92, 220, 78, 8, CYAN)
    c.text("온디바이스 sLLM을 위한\nK26–Memory FPGA 후보 구조 평가", 92, 262, 1280, 220, size=39, bold=True)
    c.text("Gemma 3 1B 작업 부하의 구조·배치·이동 비용 분석", 96, 530, 1240, 60, size=22, color=CYAN, bold=True)
    c.text("최윤혁 · 한국디지털미디어고등학교", 96, 935, 760, 38, size=17, color=MUTED)


def slide_2(c: SlideCanvas) -> None:
    header(c, META[1])
    labels = [("1", "왜 검토했나", "용량 가설→질문 전환"), ("2", "무엇을 설계했나", "K26/Memory FPGA 역할"), ("3", "무엇을 확인했나", "Gemma→RTL→평가"), ("4", "언제 채택하나", "기준선·물리 범위")]
    xs = [150, 580, 1010, 1440]
    for index, (number, title, sub) in enumerate(labels):
        c.circle(xs[index], 350, 104, CYAN if index == 0 else BG3, stroke=CYAN, stroke_width=3)
        c.text(number, xs[index], 370, 104, 62, size=32, color=BG if index == 0 else CYAN, bold=True, align="center", valign="middle")
        c.text(title, xs[index] - 115, 510, 340, 48, size=21, bold=True, align="center")
        c.text(sub, xs[index] - 115, 585, 340, 52, size=18, color=MUTED, align="center", valign="middle")
        if index < 3:
            arrow_between(c, xs[index] + 155, 380, 120, "#294057")
    c.text("필요성  →  구조  →  검증  →  채택 조건", 430, 835, 1060, 64, size=27, color=CYAN, bold=True, align="center")


def slide_3(c: SlideCanvas) -> None:
    header(c, META[2])
    c.text("처음 가설", 165, 270, 460, 46, size=21, color=MUTED, bold=True, align="center")
    c.text("“1B도 외부 8GB가 필요하다”", 125, 350, 540, 72, size=27, color=WHITE, bold=True, align="center")
    arrow_between(c, 745, 370, 155, AMBER)
    c.text("용량 모델", 1030, 270, 460, 46, size=21, color=MUTED, bold=True, align="center")
    metric(c, 1045, 350, "2.43 GiB", "INT8 + 문맥 32K + 실행 여유", CYAN, 430)
    c.line(150, 535, 1770, 535, GRID, width=2)
    c.text("새 연구 질문", 120, 610, 330, 46, size=22, color=AMBER, bold=True)
    c.text("가중치 공급 분리 + 유휴 연산 감소", 430, 595, 660, 62, size=24, color=CYAN, bold=True, align="center")
    c.text(">", 1120, 602, 100, 60, size=34, color=AMBER, bold=True, align="center")
    c.text("원격 데이터 이동 비용", 1240, 595, 500, 62, size=24, color=WHITE, bold=True, align="center")
    c.rect(430, 750, 1120, 150, BG2, stroke=CYAN, stroke_width=2, radius=18)
    c.text("이 부등식이 성립하는\n구조·배치·부하 조건은 무엇인가?", 470, 772, 1040, 105, size=25, color=CYAN, bold=True, align="center", valign="middle")


def slide_4(c: SlideCanvas) -> None:
    header(c, META[3])
    c.rect(80, 270, 570, 610, BG2, stroke=BLUE, stroke_width=3, radius=22)
    c.text("Kria K26", 120, 300, 490, 52, size=28, color=BLUE, bold=True, align="center")
    for i in range(4):
        y = 400 + i * 90
        c.rect(125, y, 210, 58, BG3, stroke=BLUE, stroke_width=2, radius=10)
        c.text(f"연산 C{i}", 135, y + 11, 190, 36, size=19, bold=True, align="center")
        c.rect(375, y, 190, 58, BG3, stroke=CYAN, stroke_width=2, radius=10)
        c.text("로컬 큐", 385, y + 11, 170, 36, size=18, color=CYAN, bold=True, align="center")
    c.text("제어 · DMA · MatVec", 150, 790, 430, 42, size=20, color=MUTED, align="center")
    c.rect(1270, 270, 570, 610, BG2, stroke=TEAL, stroke_width=3, radius=22)
    c.text("Memory FPGA 후보", 1290, 300, 530, 52, size=26, color=TEAL, bold=True, align="center")
    for i in range(4):
        y = 400 + i * 90
        c.rect(1320, y, 205, 58, BG3, stroke=TEAL, stroke_width=2, radius=10)
        c.text(f"DDR Ch{i}", 1330, y + 11, 185, 36, size=19, bold=True, align="center")
        c.rect(1560, y, 190, 58, BG3, stroke=CYAN, stroke_width=2, radius=10)
        c.text(f"링크 L{i}", 1570, y + 11, 170, 36, size=19, color=CYAN, bold=True, align="center")
    c.text("4채널 가중치 공급", 1340, 790, 430, 42, size=20, color=MUTED, align="center")
    c.line(675, 470, 1240, 470, CYAN, width=7)
    c.text("TileJob·DMA·데이터", 740, 410, 440, 42, size=20, color=CYAN, bold=True, align="center")
    c.line(1240, 650, 675, 650, CYAN, width=7)
    c.text("작업 ID 결합 · 결과", 820, 670, 300, 42, size=20, color=TEAL, bold=True, align="center")
    c.text("GTH · CDC · MIG 물리 경로: 후속 구현", 700, 835, 540, 44, size=20, color=RED, bold=True, align="center")


def slide_5(c: SlideCanvas) -> None:
    header(c, META[4])
    embedded_movie(c, "tile_dataflow", 80, 270, 780, 610)
    rows = read_csv(ROOT / "evidence/model/gemma3_1b_closed_loop_trace.csv")
    start_x, end_x, max_cycle = 1040, 1720, 260
    for tick in (0, 100, 200):
        x = start_x + (end_x - start_x) * tick / max_cycle
        c.line(x, 350, x, 780, GRID, width=1)
        c.text(str(tick), x - 40, 790, 80, 34, size=18, color=MUTED, align="center")
    colors = [BLUE, TEAL, CYAN]
    for index, row in enumerate(rows):
        y = 420 + index * 135
        fetch, dma, response, result = (int(row[key]) for key in ("fetch_accept_cycle", "dma_command_cycle", "ddr_response_cycle", "matvec_result_cycle"))
        xs = [start_x + (end_x - start_x) * cycle / max_cycle for cycle in (fetch, dma, response, result)]
        c.text(row["projection_class"], 865, y - 18, 170, 44, size=18, color=colors[index], bold=True, align="right")
        c.line(xs[0], y, xs[3], y, colors[index], width=7)
        for x in xs:
            c.circle(x - 8, y - 8, 16, colors[index], stroke=WHITE, stroke_width=1)
        c.text(f"{fetch}→{response}→{result}", xs[0], y - 55, 300, 36, size=18, color=MUTED, bold=True)
    c.rect(1030, 870, 330, 58, BG2, stroke=TEAL, stroke_width=2, radius=18)
    c.text("3/3 INT32 일치", 1050, 880, 290, 36, size=19, color=TEAL, bold=True, align="center")
    c.text("실제 타일 시험: 1C · S0", 1370, 875, 430, 40, size=17, color=AMBER, bold=True, align="center")
    c.text("응답은 시험벤치 주입 · GTH/MIG 제외", 1030, 945, 760, 38, size=18, color=RED, bold=True, align="center")


def slide_6(c: SlideCanvas) -> None:
    header(c, META[5])
    c.text("S1 정적 로컬 큐", 150, 260, 620, 48, size=24, color=BLUE, bold=True, align="center")
    lanes_y = [390, 510, 630, 750]
    counts = [8, 1, 0, 0]
    for cluster, (y, count) in enumerate(zip(lanes_y, counts)):
        c.text(f"C{cluster}", 125, y + 6, 80, 36, size=20, bold=True, align="center")
        c.rect(230, y, 600, 56, BG2, stroke=GRID, stroke_width=2, radius=9)
        for j in range(count):
            c.rect(245 + j * 66, y + 10, 50, 36, BLUE if cluster == 0 else "#2B667B", radius=6)
        if count == 0:
            c.text("유휴", 460, y + 8, 140, 34, size=20, color=AMBER, bold=True, align="center")
    arrow_between(c, 900, 530, 130, AMBER)
    c.text("긴 꼬리", 895, 600, 140, 38, size=20, color=AMBER, bold=True, align="center")
    c.line(1130, 360, 1130, 820, GRID, width=2)
    c.text("지역성 유지", 1250, 410, 420, 48, size=26, color=TEAL, bold=True, align="center")
    c.text("가중치를 가까이 둔다", 1250, 485, 420, 44, size=22, color=WHITE, align="center")
    c.text("하지만", 1390, 595, 140, 42, size=20, color=MUTED, bold=True, align="center")
    c.text("부하 균형은 보장하지 않는다", 1190, 690, 540, 52, size=26, color=AMBER, bold=True, align="center")


def slide_7(c: SlideCanvas) -> None:
    header(c, META[6])
    embedded_movie(c, "work_stealing_sequence", 160, 260, 1600, 610)
    c.rect(470, 890, 980, 60, BG2, stroke=CYAN, stroke_width=2, radius=20)
    c.text("대기 감소 이득 > 데이터 이동 비용", 510, 902, 900, 40, size=23, color=CYAN, bold=True, align="center")


def slide_8(c: SlideCanvas) -> None:
    header(c, META[7])
    stages = [("ONNX 그래프", "7,837", BLUE), ("밀집 투영/토큰", "183", CYAN), ("TileJob/토큰", "802", TEAL)]
    xs = [140, 770, 1400]
    for index, (label, value, color) in enumerate(stages):
        c.circle(xs[index], 330, 240, BG2, stroke=color, stroke_width=3)
        c.text(value, xs[index] + 10, 385, 220, 70, size=38, color=color, bold=True, align="center")
        c.text(label, xs[index] - 30, 600, 300, 44, size=22, color=WHITE, bold=True, align="center")
        if index < 2:
            arrow_between(c, xs[index] + 315, 425, 130, color)
    c.line(160, 730, 1760, 730, GRID, width=2)
    c.text("q/k/v  →  o  →  gate/up  →  down  →  다음 계층", 260, 780, 1400, 54, size=25, color=CYAN, bold=True, align="center")
    c.text("32토큰 = 25,664 TileJob · 다음 토큰은 lm_head 완료 뒤 시작", 300, 875, 1320, 46, size=22, color=MUTED, align="center")


def slide_9(c: SlideCanvas) -> None:
    header(c, META[8])
    c.text("합성 편향 부하 1,000개 · 동일 시드 · 원본 사건 CSV", 400, 225, 1120, 38, size=19, color=AMBER, bold=True, align="center")
    embedded_movie(c, "scheduler_timeline", 140, 280, 1640, 650)
    c.text("어두운 유휴 · 회색 큐 대기 · 청록 원격 준비 · 파랑 연산", 410, 945, 1100, 40, size=19, color=MUTED, align="center")


def slide_10(c: SlideCanvas) -> None:
    header(c, META[9])
    c.text("합성 편향 부하 · S3 대 S1", 170, 270, 620, 44, size=23, color=CYAN, bold=True, align="center")
    metric(c, 180, 380, "-19.13%", "TileJob p95 · 동일 시드 5개 중앙값", CYAN, 600)
    metric(c, 180, 590, "-18.71%", "TileJob p99 · 동일 시드 5개 중앙값", TEAL, 600)
    c.line(910, 280, 910, 880, GRID, width=2)
    c.text("Gemma 형상 · 초기 배치에 따른 p95", 1010, 270, 720, 44, size=23, color=AMBER, bold=True, align="center")
    c.line(1090, 540, 1660, 540, MUTED, width=4)
    c.circle(1090, 520, 40, AMBER)
    c.circle(1620, 500, 80, TEAL)
    c.text("+0.28%", 1010, 610, 230, 54, size=29, color=AMBER, bold=True, align="center")
    c.text("기존 산술", 1010, 675, 230, 38, size=20, color=MUTED, align="center")
    c.text("-19.79%", 1510, 610, 270, 54, size=29, color=TEAL, bold=True, align="center")
    c.text("채널 친화", 1510, 675, 270, 38, size=20, color=MUTED, align="center")
    c.text("초기 배치가 이미 균형이면 이득 없음", 1050, 810, 660, 46, size=22, color=WHITE, bold=True, align="center")


def slide_11(c: SlideCanvas) -> None:
    header(c, META[10])
    embedded_movie(c, "bottleneck_migration", 170, 260, 1580, 650)
    c.text("p95는 S1 비교 · 원격 가중치와 완료시간은 S2 비교", 410, 930, 1100, 46, size=20, color=AMBER, bold=True, align="center")


def slide_12(c: SlideCanvas) -> None:
    header(c, META[11])
    c.text("K26 로컬 DDR4", 150, 285, 650, 52, size=27, color=BLUE, bold=True, align="center")
    c.text("Memory FPGA · 4채널 DDR3L", 1080, 285, 730, 52, size=25, color=TEAL, bold=True, align="center")
    c.rect(160, 400, 640, 300, BG2, stroke=BLUE, stroke_width=3, radius=20)
    c.rect(1120, 400, 640, 300, BG2, stroke=TEAL, stroke_width=3, radius=20)
    c.text("9.6 GB/s", 270, 455, 420, 70, size=38, color=BLUE, bold=True, align="center")
    c.text("24.6M사이클", 220, 565, 520, 70, size=31, color=WHITE, bold=True, align="center")
    c.text("6.4 GB/s", 1230, 455, 420, 70, size=38, color=TEAL, bold=True, align="center")
    c.text("120.6M사이클", 1180, 565, 520, 70, size=31, color=WHITE, bold=True, align="center")
    c.text("<", 880, 495, 160, 90, size=52, color=CYAN, bold=True, align="center")
    c.text("시험 범위 4.8–14.4 GB/s", 230, 725, 500, 46, size=21, color=MUTED, align="center")
    c.text("시험 범위 3.2–12.8 GB/s", 1190, 725, 500, 46, size=21, color=MUTED, align="center")
    c.rect(460, 835, 1000, 90, BG3, stroke=AMBER, stroke_width=2, radius=18)
    c.text("더 큰 모델·긴 문맥·실측 경합 시 재평가", 500, 855, 920, 50, size=23, color=AMBER, bold=True, align="center")


def prepare_kicad() -> tuple[Path, Path, Path]:
    source_path = ROOT / "paper/final/figures/paper_f07_kicad_coupon_render.png"
    source = Image.open(source_path).convert("RGB")
    crops = (
        (ASSETS / "kicad_link_crop.png", (420, 100, 1380, 610)),
        (ASSETS / "kicad_refclk_crop.png", (570, 210, 1180, 620)),
        (ASSETS / "kicad_routed_crop.png", (260, 360, 1050, 850)),
    )
    for path, bounds in crops:
        source.crop(bounds).save(path)
    return tuple(path for path, _ in crops)


def slide_13(c: SlideCanvas) -> None:
    header(c, META[12])
    render = ROOT / "paper/final/figures/paper_f07_kicad_coupon_render.png"
    crops = prepare_kicad()
    c.image_file(render, 70, 250, 1210, 650, mode="cover")
    c.rect(70, 250, 1210, 650, BG, stroke=TEAL, stroke_width=2, radius=12, alpha=0)
    c.rect(370, 505, 610, 78, BG, stroke=RED, stroke_width=2, radius=14, alpha=30)
    c.text("REFERENCE COUPON", 390, 520, 570, 48, size=29, color=RED, bold=True, align="center")
    labels = ("범용 경계 링크", "기준 클록 차동쌍", "DDR3L x16 한 슬라이스")
    for index, (crop, label) in enumerate(zip(crops, labels)):
        y = 255 + index * 205
        c.image_file(crop, 1360, y, 450, 145, mode="cover")
        c.rect(1360, y, 450, 145, BG, stroke=CYAN if index == 0 else TEAL, stroke_width=2, radius=8, alpha=0)
        c.text(label, 1340, y + 150, 490, 38, size=19, color=WHITE, bold=True, align="center")
        c.line(1285, y + 72, 1345, y + 72, CYAN, width=2)
    badges = (("풋프린트 29개", BLUE, 300), ("고속/클록 배선 20개", TEAL, 390), ("쿠폰 ERC/DRC 0", CYAN, 360))
    x = 110
    for label, color, width in badges:
        c.rect(x, 930, width, 54, BG2, stroke=color, stroke_width=2, radius=18)
        c.text(label, x + 10, 938, width - 20, 36, size=18, color=color, bold=True, align="center")
        x += width + 24
    c.text("전체 116개 중 55개 미배선", 1330, 900, 500, 34, size=17, color=AMBER, bold=True, align="center")
    c.text("NOT FOR FABRICATION", 1330, 960, 500, 34, size=16, color=RED, bold=True, align="center")


def make_qr() -> Path:
    import cairosvg

    output = ASSETS / "repository_qr.png"
    widget = QrCodeWidget(REPO_URL)
    x1, y1, x2, y2 = widget.getBounds()
    size = 360
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    svg_path = ASSETS / "repository_qr.svg"
    renderSVG.drawToFile(drawing, str(svg_path))
    cairosvg.svg2png(url=str(svg_path), write_to=str(output), output_width=720, output_height=720, background_color="white")
    return output


def slide_14(c: SlideCanvas) -> None:
    header(c, META[13])
    items = [("1", "계산·메모리\n역할 분리", BLUE), ("2", "이동 비용 포함\n동적 작업 배치", CYAN), ("3", "모델→RTL→KiCad\n재현 흐름", TEAL)]
    xs = [100, 480, 860]
    for number, label, color in items:
        x = xs[int(number) - 1]
        c.circle(x + 90, 330, 110, BG3, stroke=color, stroke_width=3)
        c.text(number, x + 90, 352, 110, 58, size=29, color=color, bold=True, align="center", valign="middle")
        c.text(label, x - 20, 500, 330, 110, size=20, color=WHITE, bold=True, align="center", valign="middle")
    c.line(90, 700, 1240, 700, GRID, width=2)
    c.text("한계", 110, 760, 120, 40, size=19, color=RED, bold=True)
    c.text("현재 성능·전력은 제한 RTL과 분석 모델 기반", 250, 748, 900, 58, size=22, color=WHITE, bold=True)
    qr = make_qr()
    c.rect(1370, 270, 400, 400, WHITE, radius=8)
    c.image_file(qr, 1390, 290, 360, 360, mode="contain")
    c.text("코드·데이터·논문", 1350, 690, 440, 42, size=20, color=CYAN, bold=True, align="center")
    c.text("github.com/snowman0919/\nvarp-k26-memory-fpga", 1300, 760, 540, 78, size=17, color=WHITE, align="center")
    c.text("Q&A", 1420, 900, 300, 60, size=34, color=CYAN, bold=True, align="center")


BUILDERS = (slide_1, slide_2, slide_3, slide_4, slide_5, slide_6, slide_7, slide_8, slide_9, slide_10, slide_11, slide_12, slide_13, slide_14)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_notes() -> None:
    lines = ["# VARP v11 — 9분 40초 발표자 노트", "", "총 목표 시간: 9:40", ""]
    for index, meta in enumerate(META, 1):
        minutes, seconds = divmod(meta.duration, 60)
        speech = " ".join(part for part in (meta.speech, NOTE_EXTENSIONS[index - 1]) if part)
        lines += [
            f"## Slide {index}: {meta.title} ({minutes}:{seconds:02d})",
            "",
            f"기억할 문장: {meta.memory}",
            "",
            f"발화문: {speech}",
            "",
            f"전환: {meta.transition or '이상으로 발표를 마치겠습니다. 질문 받겠습니다.'}",
            "",
            f"질문 시 보충: {meta.supplement}",
            "",
        ]
    (FINAL / "speaker_notes.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_outline() -> None:
    lines = ["# 온디바이스 sLLM을 위한 K26–Memory FPGA 후보 구조 평가", "", "형식: 16:9 · 14장 · 목표 9:40 · 한국어 기술 컨퍼런스 발표", "", "중심 문장: K26 계산부와 Memory FPGA 가중치 공급부의 후보 구조를 평가하고, 작업 훔치기(Work Stealing)는 남은 부하 불균형의 이득이 이동 비용보다 클 때만 사용하는 수단으로 둔다.", "", "## 구성", ""]
    for index, meta in enumerate(META, 1):
        minutes, seconds = divmod(meta.duration, 60)
        lines.append(f"{index}. {meta.title} — {minutes}:{seconds:02d} · {meta.conclusion}")
    (FINAL / "outline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_source_index() -> None:
    rows = [
        (1, "없음", "cover_background.png", "image_gen; build_v11_deck.py", "후보 구조의 장식적 배경", "실제 회로나 구현 완료 상태"),
        (2, "없음", "편집 가능한 목차", "build_v11_deck.py", "발표 질문과 진행 순서", "연구 결과"),
        (3, "k26_local_external_sensitivity.csv", "편집 가능한 질문 전환", "run_k26_local_baseline.py", "2.43 GiB 용량 모델과 K26 로컬 우선 판단", "K26 기능 실행·보드 측정"),
        (4, "없음", "편집 가능한 K26↔Memory FPGA 구조", "build_v11_deck.py; ClosedLoopVirtualPrototypeTop.scala", "4클러스터·4채널 후보와 논리/물리 경계", "GTH·MIG 물리 완료"),
        (5, "gemma3_1b_closed_loop_trace.csv", "tile_dataflow.mp4/frame; 세 타일 타임라인", "manim_scenes.py; ClosedLoopVirtualPrototypeTopSpec.scala", "1클러스터·S0 대표 타일 3개 논리 폐루프", "S3 결합 실행·전체 Gemma·보드 타이밍"),
        (6, "없음", "편집 가능한 정적 큐 개념", "build_v11_deck.py", "정적 소유권의 지역성과 불균형", "수치 성능"),
        (7, "없음", "work_stealing_sequence.mp4/frame", "manim_scenes.py; k26_scheduler_model.py", "대기 감소 이득과 이동 비용을 비교하는 정책", "최적성·보드 타이밍"),
        (8, "projection_trace.csv; gemma3_1b_dependency_manifest.json", "편집 가능한 7,837→183→802 흐름", "gemma_dependency_model.py", "ONNX 형상·모델 의존성·초기 배치", "기능적 텍스트 생성·실제 컴파일러 배치"),
        (9, "s1_s3_timeline_events.csv", "scheduler_timeline.mp4/frame", "generate_conference_figures.py; manim_scenes.py", "동일 합성 작업·시드의 대기·원격 준비·연산 구간", "Gemma 사건·물리 사이클"),
        (10, "paired_policy_effects.csv; gemma3_1b_policy_effects.csv", "편집 가능한 결과 비교", "build_v11_research_summary.py; build_v11_deck.py", "합성 paired median과 Gemma 배치 민감도", "사용자 요청 latency·보편적 우월성"),
        (11, "paired_policy_effects.csv", "bottleneck_migration.mp4/frame", "manim_scenes.py", "S1/S2 비교 기준을 분리한 병목 이동", "세 수치가 같은 비교라는 해석"),
        (12, "k26_local_external_sensitivity.csv", "편집 가능한 로컬/외부 비교", "run_k26_local_baseline.py; build_v11_deck.py", "시험한 대역폭 민감도에서 K26 로컬 우선", "보드 실측·모든 미래 조건의 우월성"),
        (13, "없음", "실제 KiCad 렌더와 확대 이미지", "verify_k26_kicad.py; kicad-cli; build_v11_deck.py", "참조 쿠폰의 객체·부분 배선·제한 검사 범위", "제작 가능 보드·전체 DRC 0"),
        (14, "없음", "편집 가능한 기여·QR", "build_v11_deck.py", "기여·한계·공개 저장소", "실측 전력·완성 제품"),
    ]
    lines = ["# Slide Source Index", "", "모든 경로는 저장소 root 기준이다. 화면에서 생략한 시드·분석 모델 조건은 speaker notes와 연구 CSV에 남긴다.", "", "| Slide | 원본 CSV | 사용 Figure / 자료 | 생성·검증 스크립트 | 허용 해석 | 금지 해석 |", "|---:|---|---|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    (FINAL / "slide_source_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_pdf(paths: list[Path]) -> None:
    rl_config.invariant = 1
    page_size = (960, 540)
    pdf = pdf_canvas.Canvas(str(PDF), pagesize=page_size, pageCompression=1)
    pdf.setTitle("온디바이스 sLLM을 위한 K26–Memory FPGA 후보 구조 평가")
    pdf.setAuthor("CHOI YUNHYUK")
    for path in paths:
        pdf.drawImage(str(path), 0, 0, width=960, height=540)
        pdf.showPage()
    pdf.save()


def contact_sheet(paths: list[Path]) -> Path:
    tw, th = 480, 270
    sheet = Image.new("RGB", (tw * 2 + 84, th * 7 + 135), rgb("#030812"))
    draw = ImageDraw.Draw(sheet)
    draw.text((42, 26), "VARP v11 · 14-slide contact sheet", font=font(18, True), fill=rgb(WHITE))
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        col, row = index % 2, index // 2
        x, y = 42 + col * tw, 90 + row * th
        sheet.paste(image, (x, y))
        draw.text((x + tw - 30, y + 24), f"{index + 1:02d}", font=font(9, True), fill=rgb(CYAN), anchor="mm")
    output = FINAL / "slide_contact_sheet.png"
    sheet.save(output)
    return output


def main() -> int:
    SLIDES.mkdir(parents=True, exist_ok=True)
    for stale in SLIDES.glob("slide_*.png"):
        stale.unlink()
    prs = Presentation()
    prs.slide_width = Inches(13.333333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = META[0].title
    prs.core_properties.author = "CHOI YUNHYUK"
    prs.core_properties.created = datetime(2026, 8, 1, 0, 0, 0)
    prs.core_properties.modified = datetime(2026, 8, 1, 0, 0, 0)
    paths: list[Path] = []
    for index, (meta, builder) in enumerate(zip(META, BUILDERS), 1):
        speech = f"{meta.speech} {NOTE_EXTENSIONS[index - 1]}"
        canvas = SlideCanvas(prs, meta.title, f"기억할 문장: {meta.memory}\n\n발화문: {speech}\n\n전환: {meta.transition}\n\n질문 시 보충: {meta.supplement}")
        builder(canvas)
        paths.append(canvas.save(index))
    prs.save(PPTX)
    normalize_pptx(PPTX)
    write_notes()
    write_outline()
    write_source_index()
    build_pdf(paths)
    sheet = contact_sheet(paths)
    print(f"pptx={PPTX} slides={len(prs.slides)}")
    print(f"pdf={PDF}")
    print(f"contact_sheet={sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
