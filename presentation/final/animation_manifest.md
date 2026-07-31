# 발표 시각자료 Manifest

모든 animation은 Manim으로 생성했으며 수치 장면은 committed CSV를 직접 읽는다. 보드 실측 timing을 표현하지 않는다.

| 순서 | Asset | 역할 | 근거 |
|---:|---|---|---|
| 1 | `tile_dataflow.mp4/.gif` | 구조·미통합 폐루프 | RTL module/dataflow boundary |
| 2 | `work_stealing_sequence.mp4/.gif` | S3 victim search·score·steal | scheduler policy |
| 3 | `scheduler_timeline.mp4/.gif` | S1/S3 동일 구간 비교 | `s1_s3_timeline_events.csv` |
| 4 | `tail_latency_results.mp4/.gif` | Gemma replay와 synthetic 조건 분리 | scheduler CSV 2종 |
| 5 | `bottleneck_migration.mp4/.gif` | p95·remote byte·completion 절충 | `scheduler_controlled.csv` |

`presentation.mp4`와 `presentation.gif`는 위 장면을 연결한 무음 visual abstract다. 10분 구두 설명은 `speaker_notes.md`를 따른다.
