# Independent Presentation Review

검토 대상은 `presentation.pptx`, `presentation.pdf`, 10개 원본 크기 PNG, contact sheet, speaker notes, slide source index와 해당 CSV/RTL/KiCad 원본이다.

| 독립 역할 | 최종 판정 | 확인 범위 |
|---|---|---|
| 기술 컨퍼런스 발표자 | PASS | 연구 질문→방법→실험→결과→조건 민감도→제한 구현의 10분 논문 발표 흐름, speaker-note 전달성 |
| 시각 디자인 검토자 | PASS | 1920×1080 가독성, 위계·여백·색상, 겹침·잘림·예상치 못한 줄바꿈, Slide 2/4/7/8 수정본 |
| 하드웨어 연구자 | PASS | Gemma replay와 synthetic stress 분리, 원고·CSV 수치와 방향, model–RTL 비동등성, KiCad 검증 범위, `NOT FOR FABRICATION` |

초기 검토에서 발견된 원고의 workload 혼합, Slide 4의 축소 4-panel, Slide 7 badge 잘림, Slide 2/8 줄바꿈, sequential service 경계 누락을 모두 수정한 뒤 세 역할이 최신 산출물을 다시 판정했다.

자동 Gate는 다음을 확인한다.

- 10 slides, 16:9, 10:00 timing
- 10개의 speaker-note 기억 문장
- 10-page PDF와 10개의 1920×1080 PNG
- 캔버스 밖 객체·텍스트 overflow·텍스트 박스 충돌 0건
- 표지 1개, Manim 정지 프레임 1개, KiCad 4개로 raster 사용 범위를 제한하고 나머지 Figure는 편집 가능한 객체로 구성
- Gemma replay/synthetic stress 화면 경계, Slide 6 구간 범례, Slide 8 baseline·sequential 순위 역전, Slide 9 제작 금지·검증 범위 qualifier

실행 명령:

```bash
python presentation/tools/validate_editable_deck.py
```
