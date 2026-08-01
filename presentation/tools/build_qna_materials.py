#!/usr/bin/env python3
"""Build presenter-only Q&A material for the 17-slide final-round deck."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "study/10_qna_bank.md"
FINAL = ROOT / "presentation/final"


ATTACKS = [
    ("용량·채택", "1B가 4GB에 들어가는데 왜 외부 8GB인가?", "외부 8GB를 1B의 필수 용량으로 제안한 것이 아닙니다. 공급 분리와 더 큰 모델·긴 문맥의 채택 조건을 평가했습니다.", "현재 1B 용량 산술은 2.43 GiB이고 시험한 민감도에서는 K26 로컬이 더 유리했습니다. 따라서 1B에서는 외부 메모리를 채택하지 않는다는 판단도 연구 결과입니다. 더 큰 모델, 긴 문맥, 로컬 메모리 경합이 생길 때 같은 기준으로 재평가합니다.", 3, "results/model_level/k26_local_external_sensitivity.csv; paper/final/submission_manuscript.md"),
    ("RTL·측정", "실제 FPGA 성능을 측정했는가?", "아닙니다. 실제 Gemma 가중치 세 타일의 MatVec RTL 산술 일치만 직접 검증했고 성능 수치는 분석 모델입니다.", "직접 확인한 범위는 16×4 INT8 MatVec의 INT32 기준값 일치 3/3입니다. 실제 DDR, GTH 링크, 전체 Gemma 추론, 보드 지연과 전력은 측정하지 않았습니다. 다음 단계는 같은 작업으로 K26 로컬 기준선을 보드에서 측정하는 것입니다.", 6, "evidence/model/gemma3_1b_rtl_tile_parity.csv; docs/architecture.md"),
    ("독창성", "Work Stealing은 기존 기술인데 무엇이 새로운가?", "알고리즘 자체의 신규성을 주장하지 않습니다. 실제 Gemma 작업·초기 데이터 배치·이동 비용·RTL·PCB를 하나의 채택 분석으로 연결한 점이 기여입니다.", "기존 Work Stealing은 작업 균형 기법입니다. 이 연구에서는 K26 계산 위치와 외부 메모리의 데이터 위치를 함께 추적하고, 이동 이득과 링크·메모리 비용을 동일 흐름에서 비교했습니다. 그래서 결과는 ‘항상 훔친다’가 아니라 ‘어떤 조건에서만 재분배와 외부 메모리가 유효한가’입니다.", 5, "paper/final/submission_manuscript.md; docs/architecture.md"),
    ("스케줄링", "왜 중앙 큐가 아닌가?", "로컬 큐는 데이터 지역성과 분산 제어를 보존하면서 정적 배치의 불균형을 관찰할 수 있는 기준선이기 때문입니다.", "중앙 큐는 균형을 단순화하지만 모든 작업의 중재와 데이터 위치 결정을 한곳에 모읍니다. 이상적 전역 FIFO 비교는 분석 모델에 있지만, 물리 중재·팬아웃 비용을 포함한 현실적 중앙 큐 비교는 후속 과제입니다.", 7, "src/varp/k26_scheduler_model.py; paper/final/submission_manuscript.md"),
    ("스케줄링", "왜 지역성 인식 재분배가 어떤 조건에서는 더 느린가?", "초기 배치가 이미 균형이거나 이동 비용이 대기 감소보다 크면 재분배 비용만 추가되기 때문입니다.", "Gemma 기존 초기 배치에서는 p95가 0.28% 늘었지만 메모리 채널을 고려한 초기 배치에서는 19.79% 줄었습니다. 동일한 정책도 데이터가 처음 어디에 놓였는지와 원격 서비스 비용에 따라 결과가 바뀝니다.", 11, "results/model_level/gemma3_1b_policy_effects.csv"),
    ("모델·측정", "Slide 13의 GB/s와 cycle은 실측인가?", "아닙니다. 모두 유효 공급 대역폭과 완료 사이클을 바꾼 분석 민감도입니다.", "CSV의 GB/s는 모델 입력이고 cycle은 그 가정에서 계산한 완료 시점입니다. 시험 범위에서 외부 곡선이 로컬 곡선과 교차하지 않았다는 해석만 허용됩니다. 실제 보드 대역폭과 지연은 다음 실험에서 측정해야 합니다.", 13, "results/model_level/k26_local_external_sensitivity.csv"),
    ("PCB", "PCB는 제작 가능한가?", "아닙니다. 실제 KiCad 객체와 일부 배선을 갖춘 참조 라우팅 쿠폰입니다.", "풋프린트 29개와 고속·클록 배선 20개, 선언한 제한 범위 ERC/DRC 0을 확인했습니다. 그러나 전체 116개 중 55개가 미배선이고 실제 K26 핀, FPGA BGA ball, 네 MIG 채널, 전원 트리, SI/PI가 남아 제작용이 아닙니다.", 14, "hardware/kicad/k26_reports/k26_scope_manifest.json; hardware/kicad/controlled_review.md"),
    ("RTL·범위", "실제 Gemma가 전체 FPGA 경로를 통과했는가?", "아닙니다. 실제 가중치 세 타일이 제한된 MatVec RTL 시험 경로를 통과했습니다.", "작업 식별과 MatVec 산술은 확인했지만 응답 데이터는 시험 경계에서 주입했습니다. 실제 DDR 읽기, GTH 직렬 링크, 클록 도메인 교차, 전체 모델 추론은 포함하지 않았습니다. 따라서 전체 FPGA 경로 검증이라고 표현하지 않습니다.", 6, "evidence/model/gemma3_1b_rtl_tile_parity.csv; docs/architecture.md"),
    ("연구 판단", "외부 Memory FPGA 결과가 나쁜데 연구가 실패한 것 아닌가?", "아닙니다. 현재 1B 조건에서는 채택하지 말아야 한다는 설계 판단을 얻은 것이 결과입니다.", "구조 연구의 목적은 제안을 무조건 정당화하는 것이 아니라 채택 조건을 찾는 것입니다. 현재 모델에서는 링크 비용이 공급 분리 이득보다 컸습니다. 그래서 더 큰 모델·긴 문맥·실제 로컬 경합이라는 재평가 조건과 측정 순서를 함께 제시합니다.", 16, "results/model_level/k26_local_external_sensitivity.csv; paper/final/submission_manuscript.md"),
]


def parse_source() -> list[dict[str, str]]:
    text = SOURCE.read_text(encoding="utf-8")
    blocks = re.split(r"(?=^## Q\d+\.)", text, flags=re.MULTILINE)
    parsed: list[dict[str, str]] = []
    for block in blocks:
        head = re.search(r"^## Q(\d+)\. (.+)$", block, flags=re.MULTILINE)
        if not head:
            continue
        fields = {}
        for key, value in re.findall(r"^- \*\*(짧은 답|상세 답|근거|주의할 해석):\*\* (.+)$", block, flags=re.MULTILINE):
            fields[key] = value.strip()
        if {"짧은 답", "상세 답", "근거"}.issubset(fields):
            parsed.append({"id": head.group(1), "question": head.group(2).strip(), **fields})
    return parsed


def category(qid: int) -> str:
    if qid <= 8:
        return "연구 질문·독창성"
    if qid <= 21:
        return "Gemma 모델·작업 변환"
    if qid <= 30:
        return "RTL·링크·제어"
    if qid <= 58:
        return "스케줄링·분석 결과"
    if qid <= 66:
        return "전력·비용"
    if qid <= 70:
        return "메모리·채택 판단"
    if qid <= 81:
        return "PCB·물리 설계"
    return "재현성·한계"


def slide_for(qid: int) -> str:
    if qid <= 8:
        return f"Slide {16 if qid in {3, 6} else 15 if qid in {4, 8} else 5}"
    if qid <= 21:
        return f"Slide {9 if qid not in {13, 16} else 6}"
    if qid <= 30:
        return f"Slide {6 if qid in {22, 23, 24} else 4}"
    if qid <= 58:
        return f"Slide {12 if qid >= 51 else 11 if qid >= 38 else 8}"
    if qid <= 66:
        return "발표 화면 미제시 보조 분석"
    if qid <= 70:
        return "Slide 13"
    if qid <= 81:
        return "Slide 14"
    return "발표 화면 미제시 재현성 자료"


def clean_source(value: str) -> str:
    return value.replace("`", "")


def build_qna() -> None:
    parsed = parse_source()
    if len(parsed) < 40:
        raise RuntimeError(f"expected at least 40 source questions, got {len(parsed)}")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in parsed:
        grouped[category(int(item["id"]))].append(item)
    lines = [
        "# 본선 발표자용 Q&A 은행",
        "",
        "이 문서는 발표자 참고 자료이며 PPT 화면에는 넣지 않는다. 답변 순서는 결론 → 근거 유형·수치 → 해석 경계 → 다음 검증이다.",
        "",
        "## 최우선 공격 질문 9개",
        "",
    ]
    number = 1
    for cat, question, short, long, slide, source in ATTACKS:
        lines += [
            f"### Q{number:02d}. [{cat}] {question}", "",
            f"- **20초 핵심 답변:** {short}",
            f"- **60초 확장 답변:** {long}",
            f"- **근거 슬라이드:** Slide {slide}",
            f"- **근거 파일:** {source}", "",
        ]
        number += 1
    for cat in ("연구 질문·독창성", "Gemma 모델·작업 변환", "RTL·링크·제어", "스케줄링·분석 결과", "전력·비용", "메모리·채택 판단", "PCB·물리 설계", "재현성·한계"):
        lines += [f"## {cat}", ""]
        for item in grouped[cat]:
            qid = int(item["id"])
            caution = item.get("주의할 해석", "근거가 지지하는 범위만 답한다.")
            slide_ref = slide_for(qid)
            source_ref = clean_source(item["근거"])
            if qid == 6:
                source_ref = "paper/final/submission_manuscript.md — VIII. 결과와 시스템 설계 결정; X. 논의와 한계; XI. 결론"
            if qid == 89:
                slide_ref = "Slide 16"
                source_ref = "presentation/final/outline.md; presentation/final/speaker_notes.md — Slide 16"
            lines += [
                f"### Q{number:02d}. {item['question']}", "",
                f"- **20초 핵심 답변:** {item['짧은 답']}",
                f"- **60초 확장 답변:** {item['상세 답']} 해석 경계는 다음과 같다: {caution}",
                f"- **근거 슬라이드:** {slide_ref}",
                f"- **근거 파일:** {source_ref}", "",
            ]
            number += 1
    lines.insert(3, f"원본 89문항과 공격 질문 9개를 합쳐 총 {number - 1}문항으로 구성했다.")
    (FINAL / "qna_bank.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_peer_questions() -> None:
    questions = [
        ("AI 모델", "모델 정확도와 하드웨어 비용을 함께 비교할 때 어떤 기준으로 양자화 수준을 선택했나요?", "정확도·메모리·연산의 균형을 묻는다.", "정확도 저하가 급격해지는 비트폭이나 계층이 있었나요?"),
        ("AI 모델", "평균 성능이 아니라 최악 또는 p95 조건에서 모델의 행동이 달라지는 지점이 있었나요?", "본 발표의 꼬리 지연 관점과 연결된다.", "그 지점을 재현한 입력 사례를 하나 설명해 주실 수 있나요?"),
        ("하드웨어", "시뮬레이션 가정 중 실제 보드에서 결과를 가장 크게 바꿀 가능성이 있는 항목은 무엇인가요?", "분석과 실측의 경계를 확인한다.", "첫 보드 시험에서 그 가정을 어떤 지표로 판정하나요?"),
        ("하드웨어", "전력·열·신호 무결성 가운데 가장 먼저 닫아야 할 검증 관문은 무엇인가요?", "구현 우선순위를 묻는다.", "그 관문이 실패하면 설계를 어디까지 되돌려야 하나요?"),
        ("데이터 분석", "결과가 특정 시드나 초기 배치에 민감하지 않다는 것을 어떻게 확인했나요?", "재현성과 조건부 결론을 확인한다.", "가장 불리한 시드의 결과도 같은 방향이었나요?"),
        ("데이터 분석", "비교군 사이에 한 가지 변수만 달라졌다는 것을 어떤 자료로 증명했나요?", "인과 해석의 타당성을 묻는다.", "제거하지 못한 교란 변수가 있다면 무엇인가요?"),
        ("웹·서비스", "사용자 요청이 몰리는 순간의 꼬리 지연을 줄이기 위해 어떤 부하 분산 정책을 사용했나요?", "시스템 부하와 tail latency를 연결한다.", "재시도나 캐시 미스가 동시에 발생하면 정책이 어떻게 달라지나요?"),
        ("보안", "외부 장치나 네트워크 경계를 추가했을 때 새로 생기는 신뢰 경계와 공격면은 무엇인가요?", "구조 변화의 보안 비용을 묻는다.", "그 경계에서 무결성과 재전송을 어떻게 검증하나요?"),
        ("로보틱스", "실시간 제어 주기 안에서 평균보다 최악 지연을 더 중요하게 본 이유는 무엇인가요?", "마감시간과 꼬리 지연의 의미를 묻는다.", "마감시간을 넘었을 때 안전 상태로 전환하는 기준은 무엇인가요?"),
        ("로보틱스", "센서·연산·통신 중 병목이 이동할 때 시스템이 안전하게 성능을 낮추는 전략이 있나요?", "병목 이동과 안전한 열화를 연결한다.", "어떤 기능부터 줄여도 안전 요구를 유지할 수 있나요?"),
    ]
    lines = ["# 다른 발표자를 위한 질문 은행", "", "참여도 평가를 위해 분야별로 근거 있는 질문 10개를 준비한다.", ""]
    for index, (field, question, why, followup) in enumerate(questions, 1):
        lines += [f"## {index}. [{field}] {question}", "", f"- 질문 의도: {why}", f"- 후속 질문: {followup}", ""]
    (FINAL / "peer_question_bank.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    FINAL.mkdir(parents=True, exist_ok=True)
    build_qna()
    build_peer_questions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
