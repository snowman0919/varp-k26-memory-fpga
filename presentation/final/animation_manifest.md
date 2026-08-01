# 발표 시각자료 Manifest

모든 애니메이션은 Manim으로 생성했으며 수치 장면은 저장된 CSV를 직접 읽는다. 보드 실측 타이밍을 표현하지 않는다.

| 순서 | Asset | 역할 | 근거 |
|---:|---|---|---|
| 1 | `tile_dataflow.mp4/.gif` | 실제 타일의 폐루프 논리 경로 | `gemma3_1b_closed_loop_trace.csv`와 RTL 구조 |
| 2 | `work_stealing_sequence.mp4/.gif` | 대기 이득−이동 비용 선택 과정 | `k26_scheduler_model.py` |
| 3 | `scheduler_timeline.mp4/.gif` | 동일 작업·시드의 S1/S3 사건 비교 | `s1_s3_timeline_events.csv` |
| 4 | `tail_latency_results.mp4/.gif` | 합성 부하와 Gemma 배치 민감도 | `paired_policy_effects.csv`; `gemma3_1b_policy_effects.csv` |
| 5 | `bottleneck_migration.mp4/.gif` | p95·비지역 가중치·완료시간 절충 | `paired_policy_effects.csv` |

`presentation.mp4`와 `presentation.gif`는 위 장면을 연결한 무음 시각 요약이다. 9분 50초 구두 설명은 `speaker_notes.md`를 따른다.
