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
    title = txt(label, 28, color, True).move_to(body)
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
    """Explain the verified MatVec arithmetic path without implying board timing."""

    def construct(self):
        title = txt("실제 가중치로 MatVec 산술을 확인했다", 40, INK, True).to_edge(UP, buff=0.28)
        subtitle = txt("대표 가중치 타일 3개 · 소프트웨어 INT32 기준값과 비교", 28, MUTED).next_to(title, DOWN, buff=0.08)
        names = ["실제 가중치\n추출", "시험 입력\n생성", "16×4 INT8\nMatVec RTL", "기준값\n비교"]
        colors = [BLUE, CYAN, BLUE, TEAL]
        stages = VGroup(*[box(name, color, 2.65, 1.45) for name, color in zip(names, colors)]).arrange(RIGHT, buff=0.45).shift(DOWN * 0.10)
        arrows = VGroup(*[Arrow(stages[i][0].get_right(), stages[i + 1][0].get_left(), color=MUTED, buff=0.08, stroke_width=5) for i in range(3)])
        token = Circle(radius=0.14, color=AMBER, fill_color=AMBER, fill_opacity=1).move_to(stages[0])
        status = txt("대표 타일 1 · 게이트 투영", 28, AMBER, True).to_edge(DOWN, buff=0.42)
        self.play(FadeIn(title, subtitle, stages, arrows, token, status))
        labels = ["대표 타일 1 · 게이트 투영", "고정된 시험 벡터", "INT8 곱셈 · INT32 누산", "3/3 정확히 일치"]
        for index in range(1, 4):
            new_status = txt(labels[index], 30, TEAL if index == 3 else AMBER, True).move_to(status)
            self.play(token.animate.move_to(stages[index]), Transform(status, new_status), run_time=0.62)
            self.wait(0.18)
        boundary = txt("검증 범위 · MatVec 산술", 28, MUTED, True).to_edge(DOWN, buff=0.95)
        self.play(FadeIn(boundary))
        self.wait(1.0)


class WorkStealingSequence(Scene):
    """Show the three decisions in locality-aware work redistribution."""

    def construct(self):
        title = txt("빈 연산기는 이득이 있을 때만 작업을 가져온다", 38, INK, True).to_edge(UP, buff=0.27)
        left = box("C0 · 긴 대기열", BLUE, 4.1, 2.1).shift(LEFT * 3.5 + DOWN * 0.15)
        right = box("C2 · 유휴", TEAL, 4.1, 2.1).shift(RIGHT * 3.5 + DOWN * 0.15)
        left[1].shift(UP * 0.58)
        right[1].shift(UP * 0.58)
        jobs = VGroup(*[RoundedRectangle(width=0.58, height=0.40, corner_radius=0.06, color=BLUE, fill_color=BLUE, fill_opacity=0.65) for _ in range(6)]).arrange(RIGHT, buff=0.12).move_to(left).shift(DOWN * 0.25)
        status = txt("1  유휴 연산기 발견", 29, AMBER, True).to_edge(DOWN, buff=1.12)
        self.play(FadeIn(title, left, right, jobs, status))
        probe = Arrow(right[0].get_left(), left[0].get_right(), color=CYAN, buff=0.12, stroke_width=7)
        status2 = txt("2  기다림 감소와 데이터 이동 비용 비교", 29, AMBER, True).move_to(status)
        self.play(Transform(status, status2), GrowArrow(probe))
        score = VGroup(txt("기다림 감소", 30, CYAN, True), txt("-  가중치·활성값 이동", 29, RED, True), txt(">  0", 32, TEAL, True)).arrange(DOWN, buff=0.14).move_to([0, 1.0, 0])
        self.play(FadeIn(score))
        stolen = jobs[-1].copy()
        status3 = txt("3  이득이 클 때만 작업 이전", 29, TEAL, True).move_to(status)
        self.play(stolen.animate.move_to(right).shift(DOWN * 0.25), Transform(status, status3), FadeOut(probe, score), run_time=1.0)
        self.wait(1.1)


class SchedulerTimeline(Scene):
    """Compare one representative job from the committed event CSV."""

    def construct(self):
        rows = read_csv(ROOT / "presentation/final/assets/s1_s3_timeline_events.csv")
        s1 = next(row for row in rows if row["scheduler"] == "S1" and row["job_id"] == "996")
        s3 = next(row for row in rows if row["scheduler"] == "S3" and row["job_id"] == "996")
        q1, q3 = int(s1["queue_wait_cycles"]), int(s3["queue_wait_cycles"])
        saved = q1 - q3
        remote = int(s3["link_end_cycle"]) - int(s3["remote_copy_start_cycle"])
        compute = int(s3["compute_end_cycle"]) - int(s3["compute_start_cycle"])
        title = txt("같은 작업에서 배정 정책만 바꿨다", 40, INK, True).to_edge(UP, buff=0.24)
        static_head = txt("고정 배정 · C0", 29, BLUE, True).move_to([-4.2, 2.0, 0])
        move_head = txt("지역성 인식 재배분 · C2", 29, TEAL, True).move_to([3.8, 2.0, 0])
        self.play(FadeIn(title, static_head, move_head))

        def lane(x: float, queue_text: str, remote_text: str | None) -> VGroup:
            base = RoundedRectangle(width=6.0, height=1.1, corner_radius=0.10, color="#294057", fill_color=PANEL, fill_opacity=1).move_to([x, 0.35, 0])
            queue = Rectangle(width=2.7, height=0.68, color=MUTED, fill_color=MUTED, fill_opacity=0.55).move_to([x - 1.45, 0.35, 0])
            queue_label = txt(queue_text, 26, INK, True).move_to(queue)
            data = Rectangle(width=1.35, height=0.68, color="#2B667B", fill_color="#2B667B", fill_opacity=0.9).move_to([x + 0.62, 0.35, 0])
            data_label = txt("데이터\n준비", 24, INK, True).move_to(data)
            compute_box = Rectangle(width=0.95, height=0.68, color=BLUE, fill_color=BLUE, fill_opacity=0.86).move_to([x + 2.05, 0.35, 0])
            compute_label = txt(f"연산\n{compute}", 22, INK, True).move_to(compute_box)
            group = VGroup(base, queue, queue_label, data, data_label, compute_box, compute_label)
            if remote_text:
                remote_box = Rectangle(width=1.25, height=0.68, color=TEAL, fill_color=TEAL, fill_opacity=0.86).move_to([x + 0.61, -0.70, 0])
                remote_label = txt(remote_text, 22, INK, True).move_to(remote_box)
                connector = Arrow(data.get_bottom(), remote_box.get_top(), color=TEAL, buff=0.05, stroke_width=4)
                group.add(remote_box, remote_label, connector)
            return group

        static_lane = lane(-3.65, f"큐 대기\n{q1:,}", None)
        moved_lane = lane(3.65, f"큐 대기\n{q3:,}", f"원격 이동\n{remote}")
        self.play(FadeIn(static_lane), run_time=0.7)
        arrow = Arrow([-0.35, -1.65, 0], [0.35, -1.65, 0], color=CYAN, stroke_width=7)
        saved_text = txt(f"큐 대기 {saved:,} 사이클 감소", 29, CYAN, True).move_to([0, -2.25, 0])
        self.play(GrowArrow(arrow), FadeIn(moved_lane, saved_text), run_time=1.0)
        note = txt("폭은 설명용 · 숫자는 원본 사건 자료", 25, MUTED, True).to_edge(DOWN, buff=0.20)
        self.play(FadeIn(note))
        self.wait(1.3)


class TailLatencyResults(Scene):
    """Show the key conditional result across synthetic and Gemma-shaped jobs."""

    def construct(self):
        title = txt("효과는 작업 형상과 초기 배치에 따라 달라진다", 39, INK, True).to_edge(UP, buff=0.27)
        skew_p95 = paired_effect("skew", "S3_vs_S1", "p95_tile_latency_cycles")
        skew_p99 = paired_effect("skew", "S3_vs_S1", "p99_tile_latency_cycles")
        source_p95 = placement_effect("source_rule", "tilejob_p95_effect_s3_vs_s1_pct")
        affinity_p95 = placement_effect("channel_affinity", "tilejob_p95_effect_s3_vs_s1_pct")
        panels = VGroup(box("작업 치우침 실험", CYAN, 3.4, 2.4), box("Gemma · 기존 배치", AMBER, 3.4, 2.4), box("Gemma · 채널 고려", TEAL, 3.4, 2.4)).arrange(RIGHT, buff=0.55).shift(DOWN * 0.25)
        for panel in panels:
            panel[1].shift(UP * 0.72)
        self.play(FadeIn(title, panels))
        numbers = VGroup(
            txt(f"p95 {skew_p95:.2f}%\np99 {skew_p99:.2f}%", 30, CYAN, True).move_to(panels[0]).shift(DOWN * 0.34),
            txt(f"p95 +{source_p95:.2f}%", 32, AMBER, True).move_to(panels[1]).shift(DOWN * 0.34),
            txt(f"p95 {affinity_p95:.2f}%", 32, TEAL, True).move_to(panels[2]).shift(DOWN * 0.34),
        )
        for number in numbers:
            self.play(FadeIn(number), run_time=0.55)
        rule = txt("재배분은 초기 배치 뒤 남은 불균형이 이동 비용보다 클 때만 유효", 28, AMBER, True).to_edge(DOWN, buff=0.36)
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
            txt("고정 배정 대비", 28, BLUE, True).move_to(static_panel).shift(UP * 1.05),
            txt("무제약 재배분 대비", 28, TEAL, True).move_to(locality_panel).shift(UP * 1.05),
        )
        self.play(FadeIn(title, static_panel, locality_panel, headings))
        left = VGroup(
            txt(f"꼬리 지연 p95 {p95:.2f}%", 27, CYAN, True),
            txt("원격 링크 서비스: 0에서 발생", 24, AMBER, True),
            txt("병목: 큐에서 데이터 이동으로", 24, INK, True),
        ).arrange(DOWN, buff=0.34).move_to(static_panel).shift(DOWN * 0.25)
        right = VGroup(
            txt(f"원격 가중치 {remote:.2f}%", 27, TEAL, True),
            txt(f"완료시간 {completion:+.2f}%", 27, AMBER, True),
            txt("이동량 감소와 완료시간 이득은 다름", 24, INK, True),
        ).arrange(DOWN, buff=0.34).move_to(locality_panel).shift(DOWN * 0.25)
        self.play(FadeIn(left), run_time=0.7)
        self.play(FadeIn(right), run_time=0.7)
        decision = txt("서로 다른 기준 비교 · 단일 인과식으로 연결하지 않음", 24, AMBER, True).to_edge(DOWN, buff=0.30)
        self.play(FadeIn(decision))
        self.wait(1.2)
