# HWP 이관 가이드

실제 HWP 편집 도구와 학회 템플릿이 작업 환경에 없어 HWP 파일을 생성하지 않았다. 확장자를 바꾼 가짜 HWP도 만들지 않았다.

## 권장 이관 순서

1. 제출처의 공식 HWP 템플릿을 한컴오피스에서 연다.
2. 국문 제목, 영문 제목, 저자, 국문 초록, 영문 초록과 핵심어를 먼저 옮긴다.
3. 본문은 submission_manuscript.md의 I–X 절 순서를 유지해 붙여 넣는다.
4. 표 1–4는 HWP 표로 다시 생성하고 숫자 정렬을 오른쪽으로 맞춘다.
5. 그림은 build/publication_assets와 evidence의 PNG 또는 PDF를 사용한다. 본문용 PNG는 300 dpi 이상을 유지한다.
6. 그림 1–6의 caption과 evidence boundary 문장을 삭제하지 않는다.
7. 수식 4×16×800/8 = 6.4 GB/s는 HWP 수식 편집기로 다시 입력한다.
8. 참고문헌 [1]–[14]의 본문 인용 순서와 번호를 확인한다.

## 편집 시 유지할 claim boundary

- Graph node, initializer offset와 세 weight tile parity는 직접 또는 RTL-simulated evidence다.
- Scheduler, Gemma full replay와 hybrid total은 analytical 또는 hybrid modeled evidence다.
- Power와 energy는 modeled range이며 실제 보드 전력이 아니다.
- 가격은 DRAM package와 imputed physical-die normalization만 포함한다.
- KiCad coupon은 NOT FOR FABRICATION이며 full routing, pin, MIG, SI/PI 또는 제작 가능성을 보장하지 않는다.
- 3B 결과는 capacity sensitivity일 뿐 실제 3B 실행이 아니다.

## 최종 HWP 점검

- 약 10쪽, 2단, 학회 지정 글꼴과 여백
- 국·영문 초록이 첫 페이지에서 잘리지 않음
- 그림의 최소 글자가 인쇄 크기에서 8 pt 이상
- 표가 column 경계를 넘지 않음
- 영문 단어가 임의로 분리되지 않음
- local filesystem path, Markdown 문법, backtick이 남지 않음
- PDF로 다시 출력한 뒤 pdfinfo, pdftotext와 페이지별 육안 검토 수행
