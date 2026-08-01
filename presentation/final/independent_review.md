# Independent Presentation Review

검토 대상은 최신 `presentation.pptx`, `presentation.pdf`, 16개 1920×1080 PNG,
contact sheet, speaker notes, full script, slide source index와 해당 CSV·RTL 원본이다.

| 독립 역할 | 최종 판정 | 확인 범위 |
|---|---|---|
| 한국어 기술 발표·가독성 검토자 | PASS | 3초 이해, 자연스러운 발화, 9:21 낭독 추정, 겹침·잘림, `고정 배정`·`작업 재배분` 용어 통일 |
| 하드웨어 연구자 | PASS | 2.4301 GiB 출처, 4C·4ch 구조 분석과 1C·1ch 정적 MatVec 시험 구분, 보수적 단계 의존 규칙, 분석 결과 한정 표현 |
| 최종 언어·시각 검토자 | PASS | 16장 흐름, 한 장 한 메시지, S1 최소 노출, Slides 8·10·12 포스터 프레임, Q&A 화면 단순성 |

자동 Gate는 다음을 확인한다.

- 16 slides, 16:9, 발표 목표 570초, 낭독 추정 561초
- 16개의 speaker-note 기억 문장·그림 순서·예상 질문·20초 답변·해석 경계
- 16-page PDF와 16개의 1920×1080 PNG
- 캔버스 밖 객체·텍스트 overflow·지원하지 않는 글리프 0건, 발표 본문 18pt 이상
- 내장 H.264 무음 영상 5개, Slides 8·10·12 포함, 내부 관계·포스터 프레임·외부 링크 없음
- KiCad·PCB·참조 쿠폰의 화면·speaker notes·slide source index 노출 0건

실행 명령:

```bash
python presentation/tools/validate_editable_deck.py
```
