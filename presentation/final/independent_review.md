# Independent Presentation Review

검토 대상은 최신 `presentation.pptx`, `presentation.pdf`, 16개 원본 크기 PNG,
contact sheet, speaker notes, slide source index와 해당 CSV/RTL/KiCad 원본이다.

| 독립 역할 | 최종 판정 | 확인 범위 |
|---|---|---|
| 기술 컨퍼런스 발표자 | PASS | 14번 한계→향후 탐구, 15번 3줄 결론, 16번 Q&A의 25초·25초·15초 종결 흐름과 노트 전용 Q&A 참고자료 |
| 한국어 가독성 검토자 | PASS | 14~16번의 3초 이해, 글자 겹침·잘림·오버플로우 0건, 화면상 상세 Q&A 미노출 |
| 하드웨어 연구자 | PASS | K26 기준선→물리 폐루프→SI/PI·전력·동일 Gemma 재평가 관문, 분석 모델·민감도 qualifier, 제작·실측 과장 방지 |

하드웨어 검토에서 발견한 두 위험은 최종본에 반영했다. Slide 14는 `SI/PI·전력
검증 + 동일 Gemma 재평가`를 독립 관문으로 표시하고, Slide 15는 `분석 모델에서`와
`이번 민감도에서`를 화면에 직접 넣어 보드 실측·보편 결론으로 읽히지 않게 했다.

자동 Gate는 다음을 확인한다.

- 16 slides, 16:9, 목표 590초, 낭독 추정 578.0초
- 16개의 speaker-note 기억 문장·그림 순서·예상 질문·답변 핵심·해석 경계
- 16-page PDF와 16개의 1920×1080 PNG
- 캔버스 밖 객체·텍스트 overflow·지원하지 않는 글리프 0건, 최소 12 pt
- 내장 Manim 영상 4개, 편집 가능한 텍스트·도형 중심 구성
- Slide 16의 화면 텍스트를 `Q&A`, `질문 받겠습니다`, `감사합니다`로 제한

실행 명령:

```bash
python presentation/tools/validate_editable_deck.py
```
