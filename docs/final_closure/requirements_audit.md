# 통합 목표 요구사항 감사표

기준 문서:

1. `goal-objective.md` — VARP K26–Memory FPGA 최종 학술대회 산출물 목표
2. `VARP_IT_ACADEMIC_CONTEST_FINAL_REVISION_PROMPT.md` — IT 학술대회 v11 최종 개정 요구
3. `final1.md` — 저장소·PPT·study·release 품질과 재현성 Gate

두 문서가 충돌하면 더 최근의 v11 명칭과 12~14장 발표 구성을 적용한다. 사실성,
공개성, 재현성, 보안 요구는 두 문서의 더 엄격한 조건을 적용한다.

`final1.md`의 “구현과 실험을 확장하지 않는다”는 초기 release-only 범위는 이후
사용자가 “논문·연구 데이터·구조 설계를 먼저 끝내라”고 직접 변경했고, v11 목표도
연구 인과 보강을 요구하므로 superseded로 기록한다. 대신 `final1.md`의 Makefile,
archive, PDF timeout, README, study, release, secret scan Gate는 그대로 유지한다.

| 구분 | 최종 요구 | 현재 상태 | 완료 조건 |
|---|---|---|---|
| 연구 중심 | K26 연산부와 확장형 Memory FPGA 공급부의 공동설계 | FAIL | Work Stealing을 수단으로 내리고 구조·채택 조건을 본문 중심에 배치 |
| 닫힌 데이터 경로 | 작업→DMA→메모리 응답→링크→연산 입력 FIFO→MatVec | 진행 중 | 실제 Gemma 대표 타일 3개의 ID·byte·cycle·결과 일치 RTL trace |
| 실험 인과 | 원격 이동 비용이 링크 서비스 시간에 반영 | 진행 중 | 기본/추가 전송 byte와 cycle을 분리하고 전 실험 재실행 |
| Gemma 의존성 | layer와 autoregressive token 장벽 | 진행 중 | qkv→o→gate/up→down→다음 layer, lm_head→다음 token 적용 |
| 작업 단위 | 투영 하나가 아닌 출력 타일 | 진행 중 | 실제 K/N 형상에서 full-K, N≤1024 분석 타일 생성 |
| 배치 민감도 | 초기 배치 효과와 작업 훔치기 효과 분리 | 진행 중 | 원래 규칙·라운드로빈·크기 균형·채널 친화 비교 |
| K26-local 기준선 | 외부 메모리 채택 임계값 | 미착수 | 용량·대역폭·경합·에너지의 동일 조건 모델 기준선 |
| KiCad | 정확한 범위의 인터페이스 참조 설계 | FAIL | 현재 쿠폰을 대표 라우팅 실험으로 재분류하고 경계 신호 계약 보강 |
| 비용·에너지 | DRAM 부품 비용과 모델 추정만 사용 | 부분 충족 | 전체 가격·실측 전력 표현 금지, 민감도와 제외 항목 명시 |
| 논문 | 독립 국문 v11 최종본, 약 10쪽 | FAIL | v11-r1~r5와 v11-final, 5회 검토·변경 기록·PDF |
| 논문 언어 | 자연스러운 한국어, 내부 감사 문체 제거 | FAIL | 금지 영어 표현 감사와 용어 통일표 통과 |
| 발표 | 12~14장, 9:20~9:50, 목차와 진행 표시 | FAIL | PPTX/PDF/notes/source index/PNG/contact sheet |
| Manim | 설명 기능이 있는 영상 3개 이상 | 부분 충족 | 데이터 흐름·작업 재분배·타임라인·병목 비용 영상과 fallback frame |
| 발표 편집성 | 텍스트·도형·그래프 편집 가능 | 부분 충족 | 수치 Figure를 SVG/PPT 도형으로 유지하고 전체 이미지화 금지 |
| Q&A | 80개 이상, v11 연구 중심 | 부분 충족 | 필수 질문 포함, 정확한 파일명과 whiteboard 문서 |
| 공개 인덱스 | 논문·슬라이드·표·그림·영상·Q&A 한곳 연결 | FAIL | `conference_package/INDEX.md`와 슬라이드/논문 출처 인덱스 |
| README | 한국어 최소 공개 진입점 | FAIL | 한 문장·구조 그림·기여·Quick start·Paper·Presentation·Study |
| 저장소 정리 | Release ZIP과 대형 미디어를 main에서 제거 | FAIL | 추적 파일 제거, Release asset 업로드, main에는 소스·소형 still 유지 |
| GitHub | `conference-final`, 최종 commit/tag/release | 진행 중 | 원격 브랜치·tag·release URL과 checksum 검증 |
| Actions | 오류 없는 공개 자동화 | 부분 충족 | 실패 workflow 삭제 유지 또는 지원 도구만 쓰는 최소 CI 통과 |
| 보안 | 비밀정보·내부 토큰 0건 | PASS | 최종 archive 재검사에서도 0건 |
| 독립 검토 | 최소 5회 | 진행 중 | 각 review와 대응 change log를 v11 revision에 보존 |
| 최종 검증 | make 계약·fresh archive·시각 QA | 미착수 | 모든 명령 성공, PDF/PPT overflow·겹침 0건 |

## 현재 금지 주장

- 실제 보드에서 측정한 성능 또는 전력
- 완성된 생산용 DDR/GTH/MIG 구현
- 전체 가속기 가격 또는 저비용 달성
- 3B 모델 실행 완료
- 제작 가능한 PCB
- 요청 단위 꼬리 지연 개선
- 모든 조건에서 우월한 작업 훔치기
- 의존성을 무시한 기존 32-token pooled 결과를 실제 decode-32로 해석

## P0 수정 순서

1. 닫힌 논리 RTL 경로와 실제 타일 trace를 통과시킨다.
2. 원격 전송 비용과 의존성·token 장벽을 반영해 실험을 재산출한다.
3. K26-local 및 초기 배치 기준선을 추가한다.
4. 연구 동결 문서와 Figure source를 새 결과로 바꾼다.
5. 그 뒤에만 v11 논문과 12~14장 발표를 만든다.
