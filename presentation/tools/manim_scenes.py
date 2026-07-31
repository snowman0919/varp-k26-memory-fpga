"""Manim scenes used by the final VARP presentation.

The animations illustrate protocol flow only. They do not represent measured
board timing or bandwidth.
"""

from manim import (
    BLUE_C,
    DOWN,
    FadeIn,
    FadeOut,
    GREEN_C,
    GrowArrow,
    LEFT,
    ORANGE,
    RED_C,
    RIGHT,
    Scene,
    Text,
    Transform,
    UP,
    VGroup,
    WHITE,
    YELLOW_C,
    Arrow,
    Circle,
    Dot,
    Line,
    Rectangle,
    RoundedRectangle,
    config,
)

import csv
from pathlib import Path
from statistics import median


config.background_color = "#111827"
FONT = "Noto Sans CJK KR"
INK = "#E8EDF5"
MUTED = "#9BA8BA"
BLUE = "#4D8FD6"
TEAL = "#38A89D"
CYAN = "#36D7E7"
AMBER = "#E5A33D"
RED = "#D96C6C"
ROOT = Path(__file__).resolve().parents[2]


def label(text: str, size: int = 28, color: str = INK, weight: str = "NORMAL") -> Text:
    return Text(text, font=FONT, font_size=size, color=color, weight=weight)


def panel(title: str, color: str, width: float = 3.2, height: float = 2.0, title_size: int = 28) -> VGroup:
    box = RoundedRectangle(width=width, height=height, corner_radius=0.16, color=color)
    title_obj = label(title, title_size, color, "BOLD").next_to(box.get_top(), DOWN, buff=0.18)
    return VGroup(box, title_obj)


def job(tag: str, color: str = BLUE) -> VGroup:
    box = RoundedRectangle(width=0.72, height=0.42, corner_radius=0.08, color=color, fill_color=color, fill_opacity=0.18)
    txt = label(tag, 18, INK, "BOLD").move_to(box)
    return VGroup(box, txt)


class WorkStealingSequence(Scene):
    """Queue imbalance through locality-aware stealing and exact-once completion."""

    def construct(self):
        title = label("Multi-Queue FCFS와 Work Stealing", 38, INK, "BOLD").to_edge(UP, buff=0.28)
        qualifier = label("개념 시퀀스 · 보드 실측 타이밍 아님", 20, MUTED).next_to(title, DOWN, buff=0.10)
        left = panel("Cluster 0 · 실행", BLUE, title_size=24).shift(LEFT * 3.45 + DOWN * 0.20)
        right = panel("Cluster 1 · 유휴", TEAL, title_size=24).shift(RIGHT * 3.45 + DOWN * 0.20)
        left_q = VGroup(job("J0"), job("J1"), job("J2"), job("J3")).arrange(RIGHT, buff=0.12).move_to(left[0]).shift(DOWN * 0.12)
        empty = label("빈 큐", 24, MUTED).move_to(right[0]).shift(DOWN * 0.12)
        status = label("1  큐 불균형", 30, AMBER, "BOLD").to_edge(DOWN, buff=0.38)
        self.play(FadeIn(title, qualifier, left, right, left_q, empty), FadeIn(status))
        self.wait(0.7)

        status2 = label("2  유휴 클러스터 → 피해 큐 탐색", 30, AMBER, "BOLD").move_to(status)
        probe = Circle(radius=0.24, color=TEAL).move_to(right[0]).shift(UP * 0.34)
        search = Arrow(right[0].get_left() + LEFT * 0.15, left[0].get_right() + RIGHT * 0.15, color=TEAL, buff=0.05)
        self.play(Transform(status, status2), FadeIn(probe), GrowArrow(search), FadeOut(empty))
        self.wait(0.7)

        score = VGroup(
            label("지역성 점수", 22, MUTED),
            label("J2 = 0.91", 28, YELLOW_C, "BOLD"),
        ).arrange(DOWN, buff=0.08).next_to(search, UP, buff=0.12)
        status3 = label("3  가장 오래된 실행 가능 작업 + 지역성 점수", 28, AMBER, "BOLD").move_to(status)
        self.play(Transform(status, status3), FadeIn(score))
        self.wait(0.7)

        stolen = left_q[2].copy()
        status4 = label("4  Steal J2 · identity 보존", 30, AMBER, "BOLD").move_to(status)
        self.play(Transform(status, status4), stolen.animate.move_to(right[0]).shift(DOWN * 0.12), FadeOut(search, probe, score))
        self.wait(0.8)

        complete = label("✓ 정확히 한 번 완료", 21, GREEN_C, "BOLD").move_to(right[0]).shift(UP * 0.25)
        status5 = label("5  완료 · 중복 0 · 누락 0", 30, GREEN_C, "BOLD").move_to(status)
        self.play(Transform(status, status5), FadeIn(complete))
        self.wait(1.0)

        self.play(FadeOut(left, right, left_q, stolen, status, complete, qualifier), run_time=0.55)
        stages = [
            ("1", "피해 큐 탐색", BLUE),
            ("2", "이득 계산", CYAN),
            ("3", "TileJob 이동", TEAL),
            ("4", "완료 확인", GREEN_C),
        ]
        summary = VGroup()
        for index, (number, text_value, color) in enumerate(stages):
            x = -4.8 + index * 3.2
            circle = Circle(radius=0.52, color=color, fill_color="#102238", fill_opacity=1).move_to([x, 0.35, 0])
            number_obj = label(number, 28, color, "BOLD").move_to(circle)
            name_obj = label(text_value, 22, INK, "BOLD").next_to(circle, DOWN, buff=0.22)
            summary.add(VGroup(circle, number_obj, name_obj))
            if index < 3:
                summary.add(Arrow([x + 0.75, 0.35, 0], [x + 2.45, 0.35, 0], color=MUTED, stroke_width=5))
        rule = label("대기 이득 - 이동 비용 > 0 인 작업만 훔친다", 29, CYAN, "BOLD").to_edge(DOWN, buff=0.45)
        self.play(FadeIn(summary), FadeIn(rule), run_time=0.8)
        self.wait(1.5)


class TileDataflow(Scene):
    """TileJob request, link transfer, MatVec execution, and completion."""

    def construct(self):
        title = label("TileJob 데이터 경로", 40, INK, "BOLD").to_edge(UP, buff=0.30)
        qualifier = label("구현·모델 경계를 분리한 프로토콜 흐름", 21, MUTED).next_to(title, DOWN, buff=0.10)
        names = ["Scheduler", "Memory FPGA", "FPGA Link", "16×4 MatVec", "Completion"]
        colors = [BLUE, TEAL, AMBER, BLUE, TEAL]
        boxes = VGroup(*[panel(n, c, width=2.25, height=1.45, title_size=21) for n, c in zip(names, colors)]).arrange(RIGHT, buff=0.25)
        boxes.scale(0.86).shift(DOWN * 0.08)
        arrows = VGroup(*[
            Arrow(boxes[i][0].get_right(), boxes[i + 1][0].get_left(), color=MUTED, buff=0.08, stroke_width=3)
            for i in range(len(boxes) - 1)
        ])
        stages = [
            "1  메모리 요청",
            "2  가중치 타일 읽기",
            "3  링크 전송",
            "4  INT8 MatVec 실행",
            "5  identity 일치 완료",
        ]
        status = label(stages[0], 29, AMBER, "BOLD").to_edge(DOWN, buff=0.38)
        token = Dot(radius=0.14, color=YELLOW_C).move_to(boxes[0][0])
        self.play(FadeIn(title, qualifier, boxes, arrows, token, status))
        self.wait(0.5)
        for idx in range(1, len(boxes)):
            new_status = label(stages[idx], 29, GREEN_C if idx == 4 else AMBER, "BOLD").move_to(status)
            self.play(token.animate.move_to(boxes[idx][0]), Transform(status, new_status), run_time=0.75)
            self.wait(0.35)
        boundary = Line(boxes[1].get_bottom() + DOWN * 0.2, boxes[1].get_top() + UP * 0.2, color=RED, stroke_width=3)
        boundary.shift(RIGHT * 1.2)
        note = label("닫힌 end-to-end payload loop: 미검증", 22, RED, "BOLD").to_edge(DOWN, buff=0.92)
        self.play(FadeIn(boundary, note))
        self.wait(1.0)


def controlled_value(workload: str, policy: str, field: str) -> float:
    with (ROOT / "results/experiments/scheduler_controlled.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    values = [
        float(row[field])
        for row in rows
        if row["subset"] == "scheduler"
        and row["workload"] == workload
        and row["scheduler"] == policy
        and row["process_repetition"] == "0"
        and row["service_overlap_mode"] == "full"
    ]
    if len(values) != 5:
        raise RuntimeError(f"expected five controlled rows for {workload}/{policy}")
    return median(values)


def gemma_value(policy: str, field: str) -> float:
    with (ROOT / "experiments/gemma3_1b/scheduler_replay.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = next(row for row in rows if row["scheduler"] == policy and row["decode_tokens"] == "32")
    return float(row[field])


class SchedulerTimeline(Scene):
    """Animate the CSV-backed S1/S3 representative skew interval."""

    def construct(self):
        source = ROOT / "presentation/final/assets/s1_s3_timeline_events.csv"
        with source.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows = [row for row in rows if 41_000 <= int(row["dispatch_cycle"]) < 43_000]
        title = label("동일한 작업, 다른 실행 경로", 39, INK, "BOLD").to_edge(UP, buff=0.26)
        subtitle = label("제어된 치우침 · seed 23 · 분석 사건", 20, MUTED).next_to(title, DOWN, buff=0.08)
        self.play(FadeIn(title, subtitle))

        def make_lanes(policy: str, x: float) -> VGroup:
            group = VGroup()
            heading = label("S1 정적 로컬 큐" if policy == "S1" else "S3 지역성 인식 Work Stealing", 24, BLUE if policy == "S1" else TEAL, "BOLD")
            heading.move_to([x, 2.15, 0])
            group.add(heading)
            for cluster in range(4):
                lane = RoundedRectangle(width=5.45, height=0.55, corner_radius=0.08, color="#20364D", fill_color="#102238", fill_opacity=1)
                lane.move_to([x + 0.25, 1.35 - cluster * 0.82, 0])
                lane_label = label(f"C{cluster}", 18, INK, "BOLD").next_to(lane, LEFT, buff=0.12)
                group.add(lane, lane_label)
            return group

        left = make_lanes("S1", -3.3)
        right = make_lanes("S3", 3.3)
        self.play(FadeIn(left, right))

        s1_jobs = [row for row in rows if row["scheduler"] == "S1"][:5]
        s3_jobs = []
        for cluster in range(4):
            candidates = [row for row in rows if row["scheduler"] == "S3" and int(row["dispatch_cluster"]) == cluster]
            if candidates:
                s3_jobs.append(next((row for row in candidates if row["stolen"] == "1"), candidates[0]))

        def draw_jobs(selected: list[dict[str, str]], x: float, policy: str) -> VGroup:
            group = VGroup()
            for index, row in enumerate(selected):
                cluster = int(row["dispatch_cluster"])
                stolen = row["stolen"] == "1"
                width = 0.92 if stolen else 0.76
                block = RoundedRectangle(width=width, height=0.38, corner_radius=0.06, color=TEAL if stolen else BLUE, fill_color=TEAL if stolen else BLUE, fill_opacity=0.58)
                block.move_to([x - 1.85 + index * 0.74, 1.35 - cluster * 0.82, 0])
                tag = label(f"J{row['job_id']}", 14, INK, "BOLD").move_to(block)
                group.add(block, tag)
            return group

        left_jobs = draw_jobs(s1_jobs, -3.3, "S1")
        self.play(FadeIn(left_jobs), run_time=1.0)
        idle = VGroup(*[label("유휴", 17, AMBER, "BOLD").move_to([-1.85, 1.35 - c * 0.82, 0]) for c in (1, 2, 3)])
        self.play(FadeIn(idle))
        arrow = Arrow([-0.2, 0.0, 0], [0.2, 0.0, 0], color=TEAL, stroke_width=8)
        self.play(GrowArrow(arrow))
        right_jobs = draw_jobs(s3_jobs, 3.3, "S3")
        self.play(FadeIn(right_jobs), FadeOut(idle), run_time=1.2)
        result = label("유휴 3개 → 훔친 작업 3개", 29, TEAL, "BOLD").to_edge(DOWN, buff=0.28)
        self.play(FadeIn(result))
        self.wait(1.2)


class TailLatencyResults(Scene):
    """Build the paper-result bars from the committed Gemma and stress CSVs."""

    def construct(self):
        title = label("Tail 감소는 두 데이터 층에서 확인된다", 38, INK, "BOLD").to_edge(UP, buff=0.26)
        subtitle = label("실제 Gemma replay와 조건 탐색용 synthetic stress를 분리", 20, MUTED).next_to(title, DOWN, buff=0.08)
        self.play(FadeIn(title, subtitle))

        panels = [(-3.4, "실제 Gemma decode-32", "p95_tile_latency_cycles", gemma_value), (3.4, "Synthetic skew · 5 seeds", "p95_tile_latency_cycles", None)]
        for x, heading, field, getter in panels:
            self.play(FadeIn(label(heading, 24, CYAN if x < 0 else TEAL, "BOLD").move_to([x, 1.85, 0])))
            if getter:
                s1, s3 = getter("S1", field), getter("S3", field)
            else:
                s1, s3 = controlled_value("skew", "S1", field), controlled_value("skew", "S3", field)
            max_value = max(s1, s3)
            bars = VGroup()
            for idx, (policy, value, color) in enumerate((("S1", s1, "#5E7188"), ("S3", s3, TEAL))):
                height = 2.7 * value / max_value
                bar = Rectangle(width=1.15, height=height, color=color, fill_color=color, fill_opacity=0.9)
                bar.move_to([x - 0.75 + idx * 1.5, -0.25 + height / 2, 0])
                policy_label = label(policy, 20, color, "BOLD").next_to(bar, DOWN, buff=0.12)
                bars.add(bar, policy_label)
            change = (s3 / s1 - 1) * 100
            number = label(f"{change:.2f}%", 36, TEAL, "BOLD").move_to([x, -2.15, 0])
            self.play(FadeIn(bars), FadeIn(number), run_time=1.0)
        note = label("효과는 balanced/hotspot이 아니라 queue skew 조건에서 발생", 25, AMBER, "BOLD").to_edge(DOWN, buff=0.20)
        self.play(FadeIn(note))
        self.wait(1.2)


class BottleneckMigration(Scene):
    """Animate the queue-to-remote-service trade-off from controlled CSVs."""

    def construct(self):
        title = label("Work Stealing은 병목을 이동시킨다", 40, INK, "BOLD").to_edge(UP, buff=0.28)
        subtitle = label("synthetic skew · full-overlap 분석 모델", 20, MUTED).next_to(title, DOWN, buff=0.08)
        self.play(FadeIn(title, subtitle))
        p95 = (controlled_value("skew", "S3", "p95_tile_latency_cycles") / controlled_value("skew", "S1", "p95_tile_latency_cycles") - 1) * 100
        remote = (controlled_value("skew", "S3", "remote_weight_bytes") / controlled_value("skew", "S2", "remote_weight_bytes") - 1) * 100
        completion = (controlled_value("skew", "S3", "total_completion_cycles") / controlled_value("skew", "S2", "total_completion_cycles") - 1) * 100
        stages = [
            ("큐 Tail", f"{p95:.2f}%", BLUE, "S3 vs S1"),
            ("원격 가중치", f"{remote:.2f}%", CYAN, "S3 vs S2"),
            ("완료시간", f"+{completion:.2f}%", TEAL, "S3 vs S2"),
        ]
        groups = VGroup()
        for idx, (name, value, color, base) in enumerate(stages):
            x = -4.6 + idx * 4.6
            circle = Circle(radius=0.63, color=color, fill_color="#102238", fill_opacity=1).move_to([x, 0.5, 0])
            name_obj = label(name, 22, INK, "BOLD").next_to(circle, UP, buff=0.25)
            value_obj = label(value, 34, color, "BOLD").move_to(circle)
            base_obj = label(base, 17, MUTED).next_to(circle, DOWN, buff=0.23)
            groups.add(VGroup(circle, name_obj, value_obj, base_obj))
            if idx < 2:
                groups.add(Arrow([x + 0.9, 0.5, 0], [x + 3.7, 0.5, 0], color=MUTED, stroke_width=6))
        for item in groups:
            self.play(FadeIn(item) if not isinstance(item, Arrow) else GrowArrow(item), run_time=0.55)
        caveat = label("비교 기준이 다르다 · 서비스 중첩 가정에 민감", 24, AMBER, "BOLD").to_edge(DOWN, buff=0.38)
        self.play(FadeIn(caveat))
        self.wait(1.2)
