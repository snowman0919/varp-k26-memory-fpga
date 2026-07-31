# Slide Source Index

모든 경로는 저장소 root 기준이다. 화면에서 생략한 시드·분석 모델 조건은 speaker notes와 연구 CSV에 남긴다.

| Slide | 원본 CSV | 사용 Figure / 자료 | 생성·검증 스크립트 | 허용 해석 | 금지 해석 |
|---:|---|---|---|---|---|
| 1 | 없음 | cover_background.png | image_gen; build_v11_deck.py | 후보 구조의 장식적 배경 | 실제 회로나 구현 완료 상태 |
| 2 | 없음 | 편집 가능한 목차 | build_v11_deck.py | 발표 질문과 진행 순서 | 연구 결과 |
| 3 | k26_local_external_sensitivity.csv | 편집 가능한 질문 전환 | run_k26_local_baseline.py | 2.43 GiB 용량 모델과 K26 로컬 우선 판단 | K26 기능 실행·보드 측정 |
| 4 | 없음 | 편집 가능한 K26↔Memory FPGA 구조 | build_v11_deck.py; ClosedLoopVirtualPrototypeTop.scala | 4클러스터·4채널 후보와 논리/물리 경계 | GTH·MIG 물리 완료 |
| 5 | gemma3_1b_closed_loop_trace.csv | tile_dataflow.mp4/frame; 세 타일 타임라인 | manim_scenes.py; ClosedLoopVirtualPrototypeTopSpec.scala | 1클러스터·S0 대표 타일 3개 논리 폐루프 | S3 결합 실행·전체 Gemma·보드 타이밍 |
| 6 | 없음 | 편집 가능한 정적 큐 개념 | build_v11_deck.py | 정적 소유권의 지역성과 불균형 | 수치 성능 |
| 7 | 없음 | work_stealing_sequence.mp4/frame | manim_scenes.py; k26_scheduler_model.py | 대기 감소 이득과 이동 비용을 비교하는 정책 | 최적성·보드 타이밍 |
| 8 | projection_trace.csv; gemma3_1b_dependency_manifest.json | 편집 가능한 7,837→183→802 흐름 | gemma_dependency_model.py | ONNX 형상·모델 의존성·초기 배치 | 기능적 텍스트 생성·실제 컴파일러 배치 |
| 9 | s1_s3_timeline_events.csv | scheduler_timeline.mp4/frame | generate_conference_figures.py; manim_scenes.py | 동일 합성 작업·시드의 대기·원격 준비·연산 구간 | Gemma 사건·물리 사이클 |
| 10 | paired_policy_effects.csv; gemma3_1b_policy_effects.csv | 편집 가능한 결과 비교 | build_v11_research_summary.py; build_v11_deck.py | 합성 paired median과 Gemma 배치 민감도 | 사용자 요청 latency·보편적 우월성 |
| 11 | paired_policy_effects.csv | bottleneck_migration.mp4/frame | manim_scenes.py | S1/S2 비교 기준을 분리한 병목 이동 | 세 수치가 같은 비교라는 해석 |
| 12 | k26_local_external_sensitivity.csv | 편집 가능한 로컬/외부 비교 | run_k26_local_baseline.py; build_v11_deck.py | 시험한 대역폭 민감도에서 K26 로컬 우선 | 보드 실측·모든 미래 조건의 우월성 |
| 13 | 없음 | 실제 KiCad 렌더와 확대 이미지 | verify_k26_kicad.py; kicad-cli; build_v11_deck.py | 참조 쿠폰의 객체·부분 배선·제한 검사 범위 | 제작 가능 보드·전체 DRC 0 |
| 14 | 없음 | 편집 가능한 기여·QR | build_v11_deck.py | 기여·한계·공개 저장소 | 실측 전력·완성 제품 |
