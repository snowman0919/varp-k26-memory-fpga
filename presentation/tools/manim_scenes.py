"""Source-backed Manim scenes for the v11 conference presentation.

The scenes explain state changes. Numerical values come from committed CSVs;
none of the animations represent measured board timing or power.
"""

from __future__ import annotations

import csv
from pathlib import Path

from manim import (
    Arrow,
    Circle,
    DOWN,
    FadeIn,
    FadeOut,
    GrowArrow,
    LEFT,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Scene,
    Text,
    Transform,
    UP,
    VGroup,
    config,
)


ROOT = Path(__file__).resolve().parents[2]
FONT = "Noto Sans CJK KR"
BG = "#07111F"
PANEL = "#102238"
INK = "#F4F7FB"
MUTED = "#91A5BA"
BLUE = "#4C8DFF"
CYAN = "#36D7E7"
TEAL = "#28B6A6"
AMBER = "#F1B44C"
RED = "#FF6B6B"
config.background_color = BG


def txt(value: str, size: int = 28, color: str = INK, bold: bool = False) -> Text:
    return Text(value, font=FONT, font_size=size, color=color, weight="BOLD" if bold else "NORMAL")


def box(label: str, color: str, width: float = 2.35, height: float = 1.25) -> VGroup:
    body = RoundedRectangle(width=width, height=height, corner_radius=0.14, color=color, fill_color=PANEL, fill_opacity=1)
    title = txt(label, 22, color, True).move_to(body)
    return VGroup(body, title)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def paired_effect(workload: str, comparison: str, metric: str) -> float:
    rows = read_csv(ROOT / "results/experiments/paired_policy_effects.csv")
    row = next(row for row in rows if row["workload"] == workload and row["comparison"] == comparison and row["metric"] == metric)
    return float(row["median_effect_pct"])


def placement_effect(placement: str, metric: str) -> float:
    rows = read_csv(ROOT / "results/model_level/gemma3_1b_policy_effects.csv")
    row = next(row for row in rows if row["decode_tokens"] == "1" and row["placement"] == placement)
    return float(row[metric])


class TileDataflow(Scene):
    """Gemma TileJob through the newly closed logical RTL path."""

    def construct(self):
        title = txt("Gemma TileJob의 폐루프 논리 경로", 40, INK, True).to_edge(UP, buff=0.28)
        subtitle = txt("실제 가중치 타일 3개 · DMA 응답 뒤에만 MatVec 실행", 21, MUTED).next_to(title, DOWN, buff=0.08)
        names = ["작업 수락", "DMA 요청", "DDR 응답 경계", "논리 링크 FIFO", "16×4 MatVec", "결과 확인"]
        colors = [BLUE, BLUE, TEAL, CYAN, BLUE, TEAL]
        stages = VGroup(*[box(name, color, 2.05, 1.15) for name, color in zip(names, colors)]).arrange(RIGHT, buff=0.20).scale(0.78).shift(DOWN * 0.15)
        arrows = VGroup(*[Arrow(stages[i][0].get_right(), stages[i + 1][0].get_left(), color=MUTED, buff=0.05, stroke_width=4) for i in range(5)])
        token = Circle(radius=0.14, color=AMBER, fill_color=AMBER, fill_opacity=1).move_to(stages[0])
        status = txt("gate_proj · 수락 5", 28, AMBER, True).to_edge(DOWN, buff=0.42)
        self.play(FadeIn(title, subtitle, stages, arrows, token, status))
        labels = ["gate_proj · 수락 5", "DMA 11", "응답 13", "job ID 결합", "MatVec 실행", "결과 88 · INT32 일치"]
        for index in range(1, 6):
            new_status = txt(labels[index], 28, TEAL if index == 5 else AMBER, True).move_to(status)
            self.play(token.animate.move_to(stages[index]), Transform(status, new_status), run_time=0.62)
            self.wait(0.18)
        boundary = txt("GTH·MIG 물리 경로는 후속 구현", 23, RED, True).to_edge(DOWN, buff=0.95)
        self.play(FadeIn(boundary))
        self.wait(1.0)


class WorkStealingSequence(Scene):
    """Static queue imbalance, locality cost, and exact-once transfer."""

    def construct(self):
        title = txt("빈 작업대가 일을 가져오되 운반 비용을 계산한다", 38, INK, True).to_edge(UP, buff=0.27)
        left = box("C0 · 긴 대기열", BLUE, 4.1, 2.1).shift(LEFT * 3.5 + DOWN * 0.15)
        right = box("C3 · 유휴", TEAL, 4.1, 2.1).shift(RIGHT * 3.5 + DOWN * 0.15)
        jobs = VGroup(*[RoundedRectangle(width=0.58, height=0.40, corner_radius=0.06, color=BLUE, fill_color=BLUE, fill_opacity=0.65) for _ in range(6)]).arrange(RIGHT, buff=0.12).move_to(left).shift(DOWN * 0.25)
        status = txt("1  정적 큐: 지역성은 유지하지만 C3는 쉰다", 27, AMBER, True).to_edge(DOWN, buff=0.38)
        self.play(FadeIn(title, left, right, jobs, status))
        probe = Arrow(right[0].get_left(), left[0].get_right(), color=CYAN, buff=0.12, stroke_width=7)
        status2 = txt("2  유휴 클러스터가 실행 가능한 작업을 탐색", 27, AMBER, True).move_to(status)
        self.play(Transform(status, status2), GrowArrow(probe))
        score = VGroup(txt("대기 감소 이득", 24, CYAN, True), txt("가중치·활성값·부분합 이동 비용을 차감", 23, RED, True), txt("남은 값이 양수일 때만 이동", 27, TEAL, True)).arrange(DOWN, buff=0.12).move_to([0, 1.1, 0])
        status3 = txt("3  지역성 비용을 링크 서비스 시간에 직접 부과", 27, AMBER, True).move_to(status)
        self.play(Transform(status, status3), FadeIn(score))
        stolen = jobs[-1].copy()
        status4 = txt("4  작업 소유권을 옮기고 정확히 한 번 완료", 27, TEAL, True).move_to(status)
        self.play(stolen.animate.move_to(right).shift(DOWN * 0.25), Transform(status, status4), FadeOut(probe, score), run_time=1.0)
        done = txt("중복 0 · 누락 0", 25, TEAL, True).move_to(right).shift(UP * 0.32)
        self.play(FadeIn(done))
        self.wait(1.1)


class SchedulerTimeline(Scene):
    """Highlight representative stolen jobs from the regenerated event CSV."""

    def construct(self):
        rows = read_csv(ROOT / "presentation/final/assets/s1_s3_timeline_events.csv")
        stolen = [row for row in rows if row["scheduler"] == "S3" and row["stolen"] == "1" and int(row["dispatch_cycle"]) > 30_000]
        selected: list[dict[str, str]] = []
        used_clusters: set[str] = set()
        for row in stolen:
            if row["dispatch_cluster"] not in used_clusters:
                selected.append(row)
                used_clusters.add(row["dispatch_cluster"])
            if len(selected) == 3:
                break
        s1_by_job = {row["job_id"]: row for row in rows if row["scheduler"] == "S1"}
        title = txt("같은 TileJob 세 건의 실제 사건 구간", 38, INK, True).to_edge(UP, buff=0.24)
        heads = VGroup(txt("S1 정적 로컬 큐", 26, BLUE, True), txt("S3 지역성 인식 작업 훔치기", 26, TEAL, True)).arrange(RIGHT, buff=4.4).shift(UP * 2.15)
        self.play(FadeIn(title, heads))

        def duration(row, start, end):
            return max(0, int(row[end]) - int(row[start]))

        groups = VGroup()
        for index, s3 in enumerate(selected):
            s1 = s1_by_job[s3["job_id"]]
            y = 1.25 - index * 1.25
            for side_x, row, scheduler in ((-3.75, s1, "S1"), (3.35, s3, "S3")):
                lane = RoundedRectangle(width=5.7, height=0.72, corner_radius=0.08, color="#294057", fill_color=PANEL, fill_opacity=1).move_to([side_x, y, 0])
                label = txt(f"J{row['job_id']} · C{row['dispatch_cluster']}", 17, INK, True).move_to([side_x - 2.05, y + 0.47, 0])
                queue = duration(row, "arrival_cycle", "dispatch_cycle")
                prep = duration(row, "dispatch_cycle", "compute_start_cycle")
                remote = duration(row, "remote_copy_start_cycle", "link_end_cycle") if int(row["remote_copy_bytes"]) else 0
                compute = duration(row, "compute_start_cycle", "compute_end_cycle")
                pieces = [("큐 대기", queue, MUTED, 2.3), ("데이터 준비", max(0, prep - remote), "#2B667B", 0.9)]
                if remote:
                    pieces.append(("원격 복사", remote, TEAL, 1.25))
                pieces.append(("연산", compute, BLUE, 0.75))
                cursor = side_x - 2.75
                row_shapes = VGroup(lane, label)
                for name, cycles, color, width in pieces:
                    block = Rectangle(width=width, height=0.44, color=color, fill_color=color, fill_opacity=0.78).move_to([cursor + width / 2, y, 0])
                    block_label = txt(f"{name}\n{cycles:,}", 12, INK, True).move_to(block)
                    row_shapes.add(block, block_label)
                    cursor += width + 0.04
                if scheduler == "S3":
                    idle = txt("훔치기 전 목적 C 유휴", 13, AMBER, True).next_to(lane, DOWN, buff=0.07)
                    row_shapes.add(idle)
                groups.add(row_shapes)
        self.play(FadeIn(groups), run_time=1.2)
        legend = VGroup(
            txt("구간 폭은 가독성용", 18, MUTED, True),
            txt("숫자는 CSV cycle", 18, CYAN, True),
            txt("청록 = 원격 복사", 18, TEAL, True),
            txt("파랑 = 연산", 18, BLUE, True),
        ).arrange(RIGHT, buff=0.5).to_edge(DOWN, buff=0.20)
        self.play(FadeIn(legend))
        self.wait(1.3)


class TailLatencyResults(Scene):
    """Show the key conditional result across synthetic and Gemma-shaped jobs."""

    def construct(self):
        title = txt("효과는 작업 형상과 초기 배치에 따라 달라진다", 39, INK, True).to_edge(UP, buff=0.27)
        skew_p95 = paired_effect("skew", "S3_vs_S1", "p95_tile_latency_cycles")
        skew_p99 = paired_effect("skew", "S3_vs_S1", "p99_tile_latency_cycles")
        source_p95 = placement_effect("source_rule", "tilejob_p95_effect_s3_vs_s1_pct")
        affinity_p95 = placement_effect("channel_affinity", "tilejob_p95_effect_s3_vs_s1_pct")
        panels = VGroup(box("합성 편향 부하", CYAN, 3.4, 2.4), box("Gemma · 기존 산술", AMBER, 3.4, 2.4), box("Gemma · 채널 친화", TEAL, 3.4, 2.4)).arrange(RIGHT, buff=0.55).shift(DOWN * 0.25)
        self.play(FadeIn(title, panels))
        numbers = VGroup(
            txt(f"p95 {skew_p95:.2f}%\np99 {skew_p99:.2f}%", 30, CYAN, True).move_to(panels[0]).shift(DOWN * 0.28),
            txt(f"p95 +{source_p95:.2f}%", 32, AMBER, True).move_to(panels[1]).shift(DOWN * 0.28),
            txt(f"p95 {affinity_p95:.2f}%", 32, TEAL, True).move_to(panels[2]).shift(DOWN * 0.28),
        )
        for number in numbers:
            self.play(FadeIn(number), run_time=0.55)
        rule = txt("Work Stealing은 초기 배치 뒤 남은 불균형이 이동 비용보다 클 때만 유효", 25, AMBER, True).to_edge(DOWN, buff=0.36)
        self.play(FadeIn(rule))
        self.wait(1.2)


class BottleneckMigration(Scene):
    """Animate queue relief, remote traffic, and the system-level decision."""

    def construct(self):
        title = txt("병목은 사라지지 않고 큐에서 데이터 이동으로 옮겨간다", 37, INK, True).to_edge(UP, buff=0.27)
        p95 = paired_effect("skew", "S3_vs_S1", "p95_tile_latency_cycles")
        remote = paired_effect("skew", "S3_vs_S2", "remote_weight_bytes")
        completion = paired_effect("skew", "S3_vs_S2", "total_completion_cycles")
        static_panel = RoundedRectangle(width=5.2, height=3.0, corner_radius=0.14, color=BLUE, fill_color=PANEL, fill_opacity=1).shift(LEFT * 3.3 + DOWN * 0.10)
        locality_panel = RoundedRectangle(width=5.2, height=3.0, corner_radius=0.14, color=TEAL, fill_color=PANEL, fill_opacity=1).shift(RIGHT * 3.3 + DOWN * 0.10)
        headings = VGroup(
            txt("정적 큐 효과 · S3 대 S1", 22, BLUE, True).move_to(static_panel).shift(UP * 1.05),
            txt("지역성 점수 효과 · S3 대 S2", 22, TEAL, True).move_to(locality_panel).shift(UP * 1.05),
        )
        self.play(FadeIn(title, static_panel, locality_panel, headings))
        left = VGroup(
            txt(f"큐 tail p95 {p95:.2f}%", 27, CYAN, True),
            txt("원격 링크 서비스: 0에서 발생", 20, AMBER, True),
            txt("병목: 큐에서 데이터 이동으로", 20, INK, True),
        ).arrange(DOWN, buff=0.34).move_to(static_panel).shift(DOWN * 0.25)
        right = VGroup(
            txt(f"원격 가중치 {remote:.2f}%", 27, TEAL, True),
            txt(f"완료시간 {completion:+.2f}%", 27, AMBER, True),
            txt("이동량 감소와 완료시간 이득은 다름", 19, INK, True),
        ).arrange(DOWN, buff=0.34).move_to(locality_panel).shift(DOWN * 0.25)
        self.play(FadeIn(left), run_time=0.7)
        self.play(FadeIn(right), run_time=0.7)
        decision = txt("서로 다른 기준 비교 · 단일 인과식으로 연결하지 않음", 24, AMBER, True).to_edge(DOWN, buff=0.30)
        self.play(FadeIn(decision))
        self.wait(1.2)
