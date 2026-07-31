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


config.background_color = "#111827"
FONT = "Noto Sans CJK KR"
INK = "#E8EDF5"
MUTED = "#9BA8BA"
BLUE = "#4D8FD6"
TEAL = "#38A89D"
AMBER = "#E5A33D"
RED = "#D96C6C"


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
        title = label("Multi-Queue FCFS + Work Stealing", 38, INK, "BOLD").to_edge(UP, buff=0.28)
        qualifier = label("개념 시퀀스 · 보드 실측 타이밍 아님", 20, MUTED).next_to(title, DOWN, buff=0.10)
        left = panel("Cluster 0 · BUSY", BLUE, title_size=24).shift(LEFT * 3.45 + DOWN * 0.20)
        right = panel("Cluster 1 · IDLE", TEAL, title_size=24).shift(RIGHT * 3.45 + DOWN * 0.20)
        left_q = VGroup(job("J0"), job("J1"), job("J2"), job("J3")).arrange(RIGHT, buff=0.12).move_to(left[0]).shift(DOWN * 0.12)
        empty = label("empty", 24, MUTED).move_to(right[0]).shift(DOWN * 0.12)
        status = label("1  Queue imbalance", 30, AMBER, "BOLD").to_edge(DOWN, buff=0.38)
        self.play(FadeIn(title, qualifier, left, right, left_q, empty), FadeIn(status))
        self.wait(0.7)

        status2 = label("2  Idle cluster → victim search", 30, AMBER, "BOLD").move_to(status)
        probe = Circle(radius=0.24, color=TEAL).move_to(right[0]).shift(UP * 0.34)
        search = Arrow(right[0].get_left() + LEFT * 0.15, left[0].get_right() + RIGHT * 0.15, color=TEAL, buff=0.05)
        self.play(Transform(status, status2), FadeIn(probe), GrowArrow(search), FadeOut(empty))
        self.wait(0.7)

        score = VGroup(
            label("locality score", 22, MUTED),
            label("J2 = 0.91", 28, YELLOW_C, "BOLD"),
        ).arrange(DOWN, buff=0.08).next_to(search, UP, buff=0.12)
        status3 = label("3  Oldest eligible + locality score", 30, AMBER, "BOLD").move_to(status)
        self.play(Transform(status, status3), FadeIn(score))
        self.wait(0.7)

        stolen = left_q[2].copy()
        status4 = label("4  Steal J2 · identity 보존", 30, AMBER, "BOLD").move_to(status)
        self.play(Transform(status, status4), stolen.animate.move_to(right[0]).shift(DOWN * 0.12), FadeOut(search, probe, score))
        self.wait(0.8)

        complete = label("✓ exact-once completion", 21, GREEN_C, "BOLD").move_to(right[0]).shift(UP * 0.25)
        status5 = label("5  Completion · duplicate 0 · drop 0", 30, GREEN_C, "BOLD").move_to(status)
        self.play(Transform(status, status5), FadeIn(complete))
        self.wait(1.0)


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
            "1  memory request",
            "2  weight tile read",
            "3  link transfer",
            "4  INT8 MatVec execution",
            "5  identity-matched completion",
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
        note = label("closed end-to-end payload loop: 미검증", 22, RED, "BOLD").to_edge(DOWN, buff=0.92)
        self.play(FadeIn(boundary, note))
        self.wait(1.0)
