# 학술대회 공개 패키지

이 인덱스는 논문, 발표, 실험 근거, 물리 참조 설계와 발표 준비 자료를 한곳에서
연결한다. 수치는 별도 표기가 없으면 분석 모델 결과이며 보드 실측값이 아니다.

## 최종 논문

- 원고: [`paper/final/submission_manuscript.md`](../paper/final/submission_manuscript.md)
- 제출 PDF: [`paper/final/submission_manuscript.pdf`](../paper/final/submission_manuscript.pdf)
- 그림·배치 목록: [`paper/final/figure_manifest.csv`](../paper/final/figure_manifest.csv)
- 코드·데이터 공개 범위: [`paper/final/code_and_data_availability.md`](../paper/final/code_and_data_availability.md)
- 개정 이력: [`paper/revisions/`](../paper/revisions/)

## 9분 40초 발표

- 편집 가능한 PPTX: [`presentation/final/presentation.pptx`](../presentation/final/presentation.pptx)
- PDF: [`presentation/final/presentation.pdf`](../presentation/final/presentation.pdf)
- 발표자 노트: [`presentation/final/speaker_notes.md`](../presentation/final/speaker_notes.md)
- 슬라이드별 출처·허용/금지 해석: [`presentation/final/slide_source_index.md`](../presentation/final/slide_source_index.md)
- 슬라이드 PNG와 전체 미리보기: [`presentation/final/slides/`](../presentation/final/slides/),
  [`presentation/final/slide_contact_sheet.png`](../presentation/final/slide_contact_sheet.png)
- Manim 생성 코드: [`presentation/tools/manim_scenes.py`](../presentation/tools/manim_scenes.py)

MP4/GIF는 저장소 용량을 줄이기 위해 GitHub Release 자산으로 제공한다. PPTX에는
데이터 흐름, 작업 훔치기, 실행 타임라인, 병목 이동 영상 네 개가 직접 포함되어 있다.

## 연구 데이터와 재현

- 연구 동결 요약: [`research/v11_research_freeze.md`](../research/v11_research_freeze.md)
- 정책 짝비교: [`results/experiments/paired_policy_effects.csv`](../results/experiments/paired_policy_effects.csv)
- Gemma 의존성·배치 민감도: [`results/model_level/gemma3_1b_placement_sensitivity.csv`](../results/model_level/gemma3_1b_placement_sensitivity.csv)
- K26 로컬/외부 후보 민감도: [`results/model_level/k26_local_external_sensitivity.csv`](../results/model_level/k26_local_external_sensitivity.csv)
- 닫힌 논리 RTL 추적: [`evidence/model/gemma3_1b_closed_loop_trace.csv`](../evidence/model/gemma3_1b_closed_loop_trace.csv)
- 전체 재현: 저장소 루트에서 `make setup && make reproduce`

## RTL과 KiCad 범위

- 논리 폐루프 RTL: [`hw/src/main/scala/varp/k26/ClosedLoopVirtualPrototypeTop.scala`](../hw/src/main/scala/varp/k26/ClosedLoopVirtualPrototypeTop.scala)
- 모델–RTL 계약: [`docs/model_rtl_contract.md`](../docs/model_rtl_contract.md)
- 시스템 구조와 미구현 물리 경로: [`docs/architecture.md`](../docs/architecture.md)
- Native KiCad 원본: [`hardware/kicad/`](../hardware/kicad/)

KiCad 자료는 인터페이스 라우팅 참조 쿠폰이며 **NOT FOR FABRICATION**이다. GTH
직렬화, CDC/크레딧, MIG/DDR 물리 타이밍, SI/PI와 보드 실측은 후속 검증 범위다.

## 발표 준비

- 89개 예상 질문과 답변: [`study/10_qna_bank.md`](../study/10_qna_bank.md)
- 통합 학습자료 PDF: [`study/study_pack.pdf`](../study/study_pack.pdf)
- 화이트보드 설명: [`study/11_whiteboard_explanations.md`](../study/11_whiteboard_explanations.md)
- 주장 경계: [`study/09_claim_boundary.md`](../study/09_claim_boundary.md)
