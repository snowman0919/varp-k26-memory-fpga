# Slide Source Index

모든 경로는 repository root 기준이다. 화면에서 생략한 seed·모델·범위 조건은 이 인덱스와 speaker notes에서 유지한다.

| Slide | 원본 CSV | 사용 Figure / 자료 | 생성·검증 스크립트 | 허용 해석 | 금지 해석 |
|---:|---|---|---|---|---|
| 1 | 없음 | assets/cover_background.png | image_gen + build_editable_deck.py | 두 연산 모듈 사이의 추상적 데이터 이동을 장식적으로 표현 | 실제 칩·회로·구현 완료 상태 |
| 2 | results/experiments/scheduler_controlled.csv | 편집 가능한 queue/tail 도형 | build_editable_deck.py | 정적 ownership에서 skew와 idle이 생길 수 있음 | 실제 보드 p95 또는 물리 queue timing |
| 3 | 없음 | paper_f01_evidence_path.svg; RTL sources | build_editable_deck.py | TileScheduler/payload store/compute cluster와 독립 memory/link plane 구조 | 닫힌 DDR→link→MatVec payload loop |
| 4 | 없음 | work_stealing_sequence.mp4/.gif; work_stealing_storyboard.png; scheduler source | manim_scenes.py; generate_animations.py; build_editable_deck.py | S3의 victim search·locality score·exact-once 정책 개념 | 분석 모델의 all-eligible search와 RTL victim-head 검사, ownership, scoring을 알고리즘적으로 동일시하거나 새 알고리즘 최적성·보드 성능으로 해석 |
| 5 | experiments/gemma3_1b/projection_trace.csv; experiments/gemma3_1b/scheduler_replay.csv | 편집 가능한 7,837→183→5,856 pipeline | generate_trace.py; build_editable_deck.py | 실제 graph inventory와 graph-derived decode-32 replay; S1 대비 S3 p95 -15.07%, p99 -14.61% | 전체 모델 RTL 실행, ORT timing, 또는 다음 synthetic stress와 동일한 ledger |
| 6 | results/experiments/scheduler_controlled.csv; assets/s1_s3_timeline_events.csv | 편집 가능한 41k–43k 확대 타임라인; scheduler_timeline.mp4/.gif | generate_conference_figures.py; manim_scenes.py; build_editable_deck.py | Gemma replay와 별개의 synthetic skew 1,000-job seed 23 full-overlap analytical event에서 S1 idle, S3 J172/J162/J143 이동, queue/data/compute 구간 | Gemma replay event, RTL cycle, 물리 link/DDR timing, 또는 compute가 dispatch 직후 시작했다는 해석 |
| 7 | experiments/gemma3_1b/scheduler_replay.csv; results/experiments/scheduler_controlled.csv | 편집 가능한 Gemma p95/p99 막대; tail_latency_results.mp4/.gif | manim_scenes.py; build_editable_deck.py | 실제 graph-derived decode-32 replay의 S1 대비 S3 p95 -15.07%, p99 -14.61%; 별도 synthetic skew p95 -18.12%는 조건 일치 보조값 | 두 data layer를 동일 실험으로 합치거나 측정 K26 latency·보편적 우월성으로 해석 |
| 8 | results/experiments/scheduler_controlled.csv; assets/bottleneck_shift_source.csv | 편집 가능한 3단계 trade-off; bottleneck_migration.mp4/.gif | generate_conference_figures.py; manim_scenes.py; build_editable_deck.py | 같은 synthetic skew 5-seed full-overlap 중앙값에서 S1 대비 p95, S2 대비 remote/completion 절충 | p95 -18.12%를 queue-wait -17.86%와 동일시하거나 서로 다른 baseline 수치를 하나의 동일 비교로 해석 |
| 9 | 없음 | paper_f07_kicad_coupon_render.png; assets/kicad_top_render.png; k26_scope_manifest.json; 실제 render crops | kicad-cli pcb render; verify_k26_kicad.py; build_editable_deck.py | Native KiCad reference coupon, board 좌표 기반 GTH_REFCLK0 P/N 두 segment 강조, coupon ERC 0과 routed-subset DRC 0 범위 | 제작 가능 보드, 전체-board DRC 0, SI/PI/PDN/thermal closure |
| 10 | 없음 | docs/architecture.md; docs/evidence.md | build_editable_deck.py | 기여·현재 한계·다음 integration gate 요약 | 완성 accelerator, 보드 성능·전력, full 3B 실행 |
