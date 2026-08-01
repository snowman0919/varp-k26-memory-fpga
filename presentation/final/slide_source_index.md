# Slide Source Index

모든 경로는 저장소 root 기준이다. 화면에서 생략한 시드·분석 모델 조건은 speaker notes와 연구 CSV에 남긴다.

| Slide | 원본 CSV | 사용 Figure / 자료 | 생성·검증 스크립트 | 허용 해석 | 금지 해석 |
|---:|---|---|---|---|---|
| 1 | 없음 | cover_background.png | image_gen; build_v11_deck.py | 연구 주제의 개념 이미지 | 실제 회로나 구현 보드 |
| 2 | 없음 | 편집 가능한 목차 | build_v11_deck.py | 발표 질문과 진행 순서 | 연구 결과 |
| 3 | model_capacity_budget.csv | 편집 가능한 의사결정식 | estimate_model_capacity.py; build_v11_deck.py | 2.4301 GiB 용량 모델과 연구 질문 전환 | K26 보드 측정 |
| 4 | 없음 | 편집 가능한 K26↔Memory FPGA 구조 | build_v11_deck.py; ClosedLoopVirtualPrototypeTop.scala | 4클러스터·4채널 구조 분석과 1클러스터·1채널 정적 MatVec 시험의 구분 | GTH·CDC·MIG 물리 완료 또는 4클러스터·4채널 전체 RTL 검증 |
| 5 | 없음 | 편집 가능한 관련 연구 비교 | build_v11_deck.py; submission_manuscript.md | 문헌에 적힌 비교 가능한 연구 공백 | Work Stealing 알고리즘 신규성 |
| 6 | gemma3_1b_rtl_tile_parity.csv | tile_dataflow.mp4/frame; 편집 가능한 검증 흐름 | manim_scenes.py; GemmaWeightTileRtlParitySpec.scala | 실제 가중치 3개 타일의 MatVec RTL 산술 일치 | 전체 Gemma·DDR·링크·성능 |
| 7 | 없음 | 편집 가능한 고정 큐 개념 | build_v11_deck.py | 고정 소유권의 지역성과 불균형 | 수치 성능 |
| 8 | 없음 | work_stealing_sequence.mp4/frame | manim_scenes.py; k26_scheduler_model.py | 이득과 이동 비용을 비교하는 정책 | 최적성·보드 타이밍 |
| 9 | projection_trace.csv; gemma3_1b_dependency_manifest.json | 편집 가능한 7,837→183→802 흐름 | gemma_dependency_model.py; build_v11_deck.py | ONNX 형상과 모델링한 보수적 단계 의존·타일 분할 | 전체 ONNX 의존성 재현·실제 FPGA 실행 횟수 |
| 10 | s1_s3_timeline_events.csv | scheduler_timeline.mp4/frame | generate_conference_figures.py; manim_scenes.py | 동일 합성 작업·초기값에서 정책만 바꾼 대표 사건 | Gemma 사건·물리 cycle |
| 11 | paired_policy_effects.csv; gemma3_1b_policy_effects.csv | tail_latency_results.mp4/frame; 편집 가능한 결과 | build_v11_research_summary.py; manim_scenes.py | 합성 짝비교와 Gemma 배치 민감도 | 사용자 요청 latency·보편적 우월성 |
| 12 | paired_policy_effects.csv | bottleneck_migration.mp4/frame | manim_scenes.py | 정적·무제약 기준을 분리한 비용 비교 | 세 수치가 같은 비교라는 해석 |
| 13 | k26_local_external_sensitivity.csv | 편집 가능한 조건 변화 곡선 | run_k26_local_baseline.py; build_v11_deck.py | 시험 범위에서 곡선이 만나지 않았다는 분석 결과 | 보드 실측·미래 모든 조건의 우월성 |
| 14 | 없음 | 편집 가능한 물리 검증 순서 | build_v11_deck.py; architecture.md | 현재 한계와 후속 실측 순서 | 실측 완료 |
| 15 | 없음 | 편집 가능한 3문장 결론·QR | build_v11_deck.py | 구조·조건·현재 채택 판단 | 외부 메모리의 보편적 실패·실측 완료 |
| 16 | 없음 | 편집 가능한 질문과 토론 화면·QR | build_v11_deck.py; qna_bank.md | 구두 질의응답 시작 | 추가 기술 결과 |
