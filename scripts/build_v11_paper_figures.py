#!/usr/bin/env python3
"""Generate Korean, source-backed v11 paper SVG figures."""

from __future__ import annotations

import csv
from html import escape
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper/final/figures"
W, H = 1600, 900


def svg_start() -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">',
        '<rect width="1600" height="900" fill="#f7fbff"/>',
        '<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 Z" fill="#1878a8"/></marker></defs>',
    ]


def text(x: float, y: float, value: str, size: int = 28, color: str = "#102a43", weight: int = 500, anchor: str = "start") -> str:
    # The 1600 px canvas is reduced to a journal-column width in the final PDF.
    # Keep every embedded label at or above 31 px so the conservative placement
    # gate remains above 8 pt after that reduction.
    size = max(size, 31)
    return (
        f'<text x="{x}" y="{y}" font-size="{size}px" '
        f'font-family="Noto Sans CJK KR, Noto Sans KR, sans-serif" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">'
        f'{escape(value)}</text>'
    )


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "#8db4c8", radius: int = 18, sw: int = 3, dash: str = "") -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash_attr}/>'


def line(x1: float, y1: float, x2: float, y2: float, color: str = "#1878a8", sw: int = 5, arrow: bool = True, dash: str = "") -> str:
    marker = ' marker-end="url(#arrow)"' if arrow else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{marker}{dash_attr}/>'


def title(parts: list[str], heading: str, conclusion: str) -> None:
    parts += [
        text(70, 78, heading, 44, "#102a43", 800),
        text(70, 124, conclusion, 25, "#486581", 500),
    ]


def save(name: str, parts: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts.append("</svg>")
    (OUT / name).write_text("\n".join(parts) + "\n", encoding="utf-8")


def figure1() -> None:
    p = svg_start()
    title(p, "연산과 가중치 공급을 분리한 후보 구조", "논리 RTL 경로는 닫았지만 GTH·MIG 물리 경로는 후속 구현 범위다")
    p += [rect(60, 180, 570, 560, "#e8f4fb", "#287da8", 24, 4), text(95, 230, "Kria K26 · 연산/제어", 34, "#12557a", 800)]
    for index in range(4):
        y = 285 + index * 88
        p += [rect(105, y, 210, 60, "#ffffff", "#4d9ec2", 12, 2), text(210, y + 39, f"연산 클러스터 {index}", 23, "#173f5f", 650, "middle"), rect(350, y, 215, 60, "#d8eef7", "#4d9ec2", 12, 2), text(458, y + 39, "로컬 대기열", 23, "#173f5f", 650, "middle")]
    p += [rect(105, 655, 460, 55, "#dff3ed", "#2b9b86", 12, 2), text(335, 691, "로컬 4GB: 실행·활성값·KV cache", 23, "#16685a", 650, "middle")]
    p += [rect(970, 180, 570, 560, "#eaf7f4", "#258f7e", 24, 4), text(1005, 230, "Memory FPGA · 가중치 공급", 34, "#176d60", 800)]
    for index in range(4):
        y = 285 + index * 88
        p += [rect(1015, y, 205, 60, "#ffffff", "#49a995", 12, 2), text(1117, y + 39, f"DDR3L 채널 {index}", 23, "#155e55", 650, "middle"), rect(1260, y, 215, 60, "#dff3ed", "#49a995", 12, 2), text(1367, y + 39, "가중치 대기열", 23, "#155e55", 650, "middle")]
    p += [text(800, 248, "4개 논리 링크", 28, "#126e92", 800, "middle")]
    for index in range(4):
        y = 310 + index * 88
        p += [line(635, y, 960, y, "#1687b3", 7, True)]
    p += [rect(680, 670, 240, 52, "#ffffff", "#1687b3", 12, 2), text(800, 704, "DMA·응답·FIFO", 22, "#126e92", 700, "middle"), line(690, 780, 840, 780, "#1878a8", 6, False), text(860, 788, "연결된 논리 RTL", 22, "#35556b", 600), line(690, 830, 840, 830, "#8799a5", 5, False, "12 10"), text(860, 838, "GTH·MIG·보드: 미검증", 22, "#6b7780", 600)]
    save("paper_f01_evidence_path.svg", p)


def figure2() -> None:
    p = svg_start()
    title(p, "실제 그래프 형상을 의존성 있는 출력 타일로 변환", "32개 토큰은 겹치지 않으며, 초기 배치는 별도 설계 변수로 비교한다")
    stages = [(60, "ONNX 그래프", "노드 7,837"), (360, "투영 연산", "183개/토큰"), (660, "출력 타일", "802개/토큰"), (970, "단계 의존성", "qkv→o→MLP"), (1290, "직렬 토큰", "총 25,664개")]
    for x, h, s in stages:
        p += [rect(x, 205, 245, 150, "#ffffff", "#4d9ec2", 18, 3), text(x + 122, 260, h, 28, "#173f5f", 750, "middle"), text(x + 122, 315, s, 23, "#486581", 600, "middle")]
    for x in (305, 605, 915, 1235):
        p += [line(x, 280, x + 45, 280, "#1878a8", 5, True)]
    p += [text(70, 440, "보수적 단계 장벽", 30, "#102a43", 750), rect(70, 470, 1450, 120, "#edf6fb", "#76abc4", 18, 2)]
    labels = [(145, "q / k / v"), (430, "o"), (680, "gate / up"), (990, "down"), (1260, "다음 계층")]
    for x, label in labels:
        p += [rect(x, 505, 175, 54, "#ffffff", "#4d9ec2", 10, 2), text(x + 87, 541, label, 22, "#173f5f", 700, "middle")]
    for x in (320, 605, 855, 1165):
        p += [line(x, 532, x + 95, 532, "#1878a8", 4, True)]
    p += [text(70, 670, "비교한 초기 배치", 30, "#102a43", 750)]
    placements = [(70, "기존 산술", "464 / 208 / 78 / 52"), (440, "라운드로빈", "201 / 201 / 200 / 200"), (810, "크기 균형", "198 / 202 / 200 / 202"), (1180, "채널 친화", "394 / 136 / 136 / 136")]
    for x, h, s in placements:
        p += [rect(x, 705, 320, 105, "#eaf7f4", "#3f9f8c", 16, 2), text(x + 160, 746, h, 25, "#176d60", 750, "middle"), text(x + 160, 787, s, 21, "#486581", 600, "middle")]
    save("paper_f02_onnx_runtime_graph.svg", p)


def figure3() -> None:
    p = svg_start()
    title(p, "빈 클러스터가 작업을 가져오되 이동 비용을 먼저 계산", "정적 대기 감소가 가중치·활성값·부분합 복사 시간보다 클 때만 실행한다")
    p += [rect(60, 180, 600, 600, "#edf6fb", "#4d9ec2", 20, 3), text(95, 230, "S1 · 정적 다중 대기열", 32, "#173f5f", 800)]
    queue_counts = [7, 2, 1, 0]
    for c, count in enumerate(queue_counts):
        y = 300 + c * 105
        p += [text(110, y + 35, f"C{c}", 25, "#173f5f", 750), rect(170, y, 390, 55, "#ffffff", "#76abc4", 10, 2)]
        for j in range(count):
            p += [rect(185 + j * 50, y + 9, 38, 37, "#2f80b7" if c == 0 else "#73b7d2", "#ffffff", 5, 1)]
        if count == 0:
            p += [text(365, y + 36, "유휴", 23, "#9b4d45", 750, "middle")]
    p += [line(660, 480, 835, 480, "#188e80", 8, True), text(750, 445, "후보 검색", 24, "#176d60", 750, "middle")]
    p += [rect(850, 180, 690, 600, "#eaf7f4", "#3f9f8c", 20, 3), text(890, 230, "S3 · 지역성 인식 재분배", 32, "#176d60", 800)]
    checks = [(900, 300, "1  기다린 시간"), (900, 390, "2  가중치 크기"), (900, 480, "3  활성값·부분합"), (900, 570, "4  링크 불일치")]
    for x, y, label in checks:
        p += [rect(x, y, 300, 62, "#ffffff", "#59aa98", 12, 2), text(x + 25, y + 41, label, 23, "#155e55", 650)]
    p += [text(1240, 330, "대기 이득", 25, "#126e92", 750), text(1240, 382, "− 이동 비용", 25, "#9b4d45", 750), line(1235, 408, 1485, 408, "#708d9b", 3, False), text(1360, 458, "점수 > 0", 30, "#176d60", 800, "middle"), rect(1230, 505, 250, 112, "#d7f1ea", "#258f7e", 16, 3), text(1355, 548, "기본 위치 적재", 22, "#155e55", 650, "middle"), text(1355, 590, "→ 유휴 쪽 복사", 22, "#155e55", 750, "middle"), text(1195, 700, "추가 바이트·사이클을 링크에 부과", 24, "#486581", 650, "middle")]
    save("paper_f03_policy_boundary.svg", p)


def figure4() -> None:
    p = svg_start()
    title(p, "실제 가중치 타일 3개가 폐쇄형 논리 경로를 통과", "DMA 명령과 DDR 응답 뒤에만 MatVec이 실행되며 세 결과가 소프트웨어 기준과 일치한다")
    x0, x1 = 260, 1480
    max_cycle = 260
    for tick_value in (0, 50, 100, 150, 200, 250):
        x = x0 + (x1 - x0) * tick_value / max_cycle
        p += [line(x, 190, x, 760, "#d8e5ec", 2, False), text(x, 800, str(tick_value), 20, "#627d98", 500, "middle")]
    p += [text(1450, 845, "사이클", 22, "#486581", 600)]
    rows = [("gate_proj", 5, 11, 13, 88), ("lm_head", 89, 95, 97, 172), ("o_proj", 173, 179, 181, 256)]
    colors = ["#2f80b7", "#2aa58e", "#5576c5"]
    for idx, (name, fetch_c, dma_c, response_c, result_c) in enumerate(rows):
        y = 275 + idx * 180
        p += [text(65, y + 12, name, 27, "#173f5f", 750)]
        points = [(fetch_c, "수락"), (dma_c, "DMA"), (response_c, "응답"), (result_c, "결과")]
        p += [line(x0 + (x1 - x0) * fetch_c / max_cycle, y, x0 + (x1 - x0) * result_c / max_cycle, y, colors[idx], 10, False)]
        for cycle, _label in points:
            x = x0 + (x1 - x0) * cycle / max_cycle
            p += [f'<circle cx="{x}" cy="{y}" r="11" fill="{colors[idx]}" stroke="#ffffff" stroke-width="3"/>']
        mid_x = x0 + (x1 - x0) * ((fetch_c + result_c) / 2) / max_cycle
        result_x = x0 + (x1 - x0) * result_c / max_cycle
        p += [text(mid_x, y - 35, f"수락 {fetch_c} · DMA {dma_c} · 응답 {response_c}", 24, "#35556b", 650, "middle"), text(result_x, y + 48, f"결과 {result_c}", 24, "#35556b", 750, "middle")]
    p += [rect(1160, 710, 300, 58, "#e2f4ee", "#2aa58e", 10, 2), text(1310, 749, "3/3 INT32 일치", 20, "#176d60", 750, "middle"), rect(70, 720, 430, 64, "#fff3e9", "#c97938", 12, 2), text(285, 762, "GTH·MIG 타이밍은 포함하지 않음", 22, "#8a4a19", 700, "middle")]
    save("paper_f04_waveform_identity.svg", p)


def bar(parts: list[str], x: float, y0: float, width: float, value: float, scale: float, color: str, label: str) -> None:
    h = abs(value) * scale
    if value <= 0:
        parts.append(rect(x, y0, width, h, color, color, 3, 0))
        parts.append(text(x + width / 2, y0 + h + 30, f"{value:.2f}%", 21, "#35556b", 750, "middle"))
    else:
        parts.append(rect(x, y0 - h, width, h, color, color, 3, 0))
        parts.append(text(x + width / 2, y0 - h - 14, f"+{value:.2f}%", 21, "#9b4d45", 750, "middle"))
    parts.append(text(x + width / 2, 790, label, 22, "#35556b", 650, "middle"))


def figure5() -> None:
    p = svg_start()
    title(p, "작업 불균형이 큰 유효구간에서 꼬리 지연이 감소", "S3 대 S1 · 5개 시드의 TileJob p95 변화율 중앙값")
    y0 = 300
    p += [line(110, y0, 1500, y0, "#8da7b5", 3, False), text(90, y0 + 8, "0%", 20, "#627d98", 500, "end")]
    values = [("균형", 0.0), ("채널 집중", 0.0), ("순간 집중", -0.08), ("혼합", -17.70), ("편향", -19.13)]
    for idx, (label, value) in enumerate(values):
        color = "#2aa58e" if value < -5 else "#91b8c8"
        bar(p, 190 + idx * 260, y0, 125, value, 21, color, label)
    p += [rect(900, 665, 560, 90, "#eaf7f4", "#3f9f8c", 14, 2), text(1180, 705, "편향: p95 −19.13% · p99 −18.71%", 25, "#176d60", 800, "middle"), text(1180, 746, "S2 대비 비지역 가중치 −35.49%", 21, "#486581", 650, "middle")]
    save("paper_f05_tail_latency.svg", p)


def figure6() -> None:
    p = svg_start()
    title(p, "같은 Gemma 형상도 초기 배치 민감도가 결과를 가른다", "S3 대 S1 · TileJob p95와 전체 완료시간 변화율")
    y0 = 360
    p += [line(100, y0, 1500, y0, "#8da7b5", 3, False), text(85, y0 + 8, "0%", 20, "#627d98", 500, "end")]
    placements = [("기존 산술", 0.28, 4.80, "395 MB"), ("라운드로빈", 0.0, -0.59, "43 MB"), ("크기 균형", 0.0, -0.76, "111 MB"), ("채널 친화", -19.79, -7.56, "416 MB")]
    for idx, (label, p95, completion, remote) in enumerate(placements):
        x = 170 + idx * 345
        bar(p, x, y0, 90, p95, 15, "#2aa58e", label)
        bar(p, x + 105, y0, 90, completion, 15, "#2f80b7", "")
        p += [text(x + 97, 830, f"추가 {remote}", 19, "#627d98", 600, "middle")]
    p += [rect(1050, 165, 180, 54, "#e2f4ee", "#2aa58e", 10, 2), text(1140, 200, "TileJob p95", 20, "#176d60", 700, "middle"), rect(1250, 165, 180, 54, "#e7effb", "#2f80b7", 10, 2), text(1340, 200, "완료시간", 20, "#245a8a", 700, "middle")]
    save("paper_f06_tradeoff.svg", p)


def main() -> None:
    figure1()
    figure2()
    figure3()
    figure4()
    figure5()
    figure6()
    print(f"generated 6 SVG figures in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
