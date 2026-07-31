# Independent Presentation Review

검토 대상은 `presentation.pptx`, `presentation.pdf`, 10개 원본 크기 PNG, contact sheet, speaker notes, slide source index와 해당 CSV/RTL/KiCad 원본이다.

| 독립 역할 | 최종 판정 | 확인 범위 |
|---|---|---|
| 기술 컨퍼런스 발표자 | PASS | 10분 흐름, 3초 메시지, 한국어 표현, 핵심 수치 밀도, speaker-note 전달성 |
| 시각 디자인 검토자 | PASS | 1920×1080 가독성, 위계·여백·색상, 겹침·잘림·누락 글리프, Slide 6/8/9 구성 |
| 하드웨어 연구자 | PASS | Gemma replay와 synthetic stress 분리, CSV 수치·baseline, timeline event 구간, model–RTL 비동등성, KiCad 검증 범위와 refclk P/N 좌표 |

최종 하드웨어 확인에서 `GTH_REFCLK0_N`은 PCB y=26.0의 상단 cyan 선, `GTH_REFCLK0_P`는 y=26.8의 하단 amber 선으로 native orthographic KiCad render와 일치한다.

자동 Gate는 다음을 확인한다.

- 10 slides, 16:9, 10:00 timing
- 10개의 speaker-note 기억 문장
- 10-page PDF와 10개의 1920×1080 PNG
- 표지 1개와 KiCad 4개를 제외한 발표 Figure의 native editable objects 구성
- Gemma replay/synthetic stress 화면 경계, Slide 6 구간 범례, Slide 8 baseline, Slide 9 제작 금지·검증 범위 qualifier

실행 명령:

```bash
python presentation/tools/validate_editable_deck.py
```
