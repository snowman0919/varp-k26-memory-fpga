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
| 연구 중심 | K26 연산부와 확장형 Memory FPGA 공급부의 공동설계 | **PASS** | 논문·발표 모두 구조의 필요성, 동작, 효과 조건과 채택 조건을 중심으로 재구성 |
| 닫힌 데이터 경로 | 작업→DMA→메모리 응답→링크→연산 입력 FIFO→MatVec | **PASS(논리 경로)** | 실제 Gemma 대표 타일 3개의 ID·byte·cycle·결과 일치 RTL trace 보존; 물리 GTH/MIG/CDC는 미완료로 명시 |
| 실험 인과 | 원격 이동 비용이 링크 서비스 시간에 반영 | **PASS** | 기본/추가 전송 byte와 cycle을 분리하고 통제 실험 전부 재실행 |
| Gemma 의존성 | layer와 autoregressive token 장벽 | **PASS** | qkv→o→gate/up→down→다음 layer와 lm_head→다음 token 장벽 적용 |
| 작업 단위 | 투영 하나가 아닌 출력 타일 | **PASS** | 실제 K/N 형상에서 full-K, N≤1024 분석 타일 생성; 802 TileJobs/token |
| 배치 민감도 | 초기 배치 효과와 작업 훔치기 효과 분리 | **PASS** | source rule·round robin·size aware·channel affinity 비교 |
| K26-local 기준선 | 외부 메모리 채택 임계값 | **PASS** | 동일 조건 용량·대역폭 민감도에서 K26-local을 우선 기준선으로 판정 |
| KiCad | 정확한 범위의 인터페이스 참조 설계 | **PASS(제한 쿠폰)** | K26–Memory FPGA 경계, GTH/refclk, 대표 DDR3L 라우팅 쿠폰과 ERC/DRC 범위를 명시; 제작 가능 보드 주장은 금지 |
| 비용·에너지 | DRAM 부품 비용과 모델 추정만 사용 | **PASS(모델 범위)** | DRAM die 비용·분석 에너지 민감도만 제시하고 FPGA 가격·전체 BOM·실측 전력은 제외 |
| 논문 | 독립 국문 v11 최종본, 약 10쪽 | **PASS** | 제출본 8쪽·기술보고서 10쪽, v11-r1~r5와 v11-final 및 검토·변경 기록 보존 |
| 논문 언어 | 자연스러운 한국어, 내부 감사 문체 제거 | **PASS** | 최종 언어 검토와 PDF 텍스트 감사를 통과 |
| 발표 | 12~14장, 9:20~9:50, 목차와 진행 표시 | **PASS** | 14장, 목표 580초·낭독 추정 574.3초, PPTX/PDF/notes/source index/PNG/contact sheet |
| Manim | 설명 기능이 있는 영상 3개 이상 | **PASS** | 데이터 흐름·작업 재분배·타임라인·꼬리 지연·병목 이동 영상과 정지 fallback 생성 |
| 발표 편집성 | 텍스트·도형·그래프 편집 가능 | **PASS** | 14장 검증, 4개 내장 영상, 텍스트·도형 중심 구성; 전체 슬라이드 이미지화 없음 |
| Q&A | 80개 이상, v11 연구 중심 | **PASS** | 연구 중심 89문항과 31쪽 학습 자료 PDF 완성 |
| 공개 인덱스 | 논문·슬라이드·표·그림·영상·Q&A 한곳 연결 | **PASS** | `conference_package/INDEX.md`와 슬라이드별 출처·해석 경계 연결 |
| README | 한국어 최소 공개 진입점 | **PASS** | 구조·핵심 결과·Quick start·재현 명령·산출물 경로를 간결하게 제공 |
| 저장소 정리 | Release ZIP과 대형 미디어를 main에서 제거 | **PASS** | ZIP·대형 MP4/GIF 추적 제거 및 `.gitignore`; 로컬 Release 자산은 유지 |
| GitHub | `conference-final`, 최종 commit/tag/release | **진행 중** | 로컬 커밋 완료; 브랜치·PR 푸시 후 공개 tag/release는 보안 경보 해소 뒤 게시 |
| Actions | 오류 없는 공개 자동화 | **PASS** | 실패하던 공개 workflow를 삭제했고 현재 `.github/workflows` 추적 파일 0개 |
| 보안 | 비밀정보·내부 토큰 0건 | **BLOCKED(과거 이력)** | 현재 산출물·기존 Release 자산은 0건이나 과거 PDF 커밋의 Vault 토큰 경보 #1이 열려 있음; 폐기·교체 후 `revoked` 해소 필요 |
| 독립 검토 | 최소 5회 | **PASS** | 가속기 기여·인과·한국어 가독성·하드웨어 시각·발표/Q&A·최종 언어의 6회 검토와 대응 기록 보존 |
| 최종 검증 | make 계약·fresh archive·시각 QA | **진행 중** | unit/RTL/paper/presentation Gate 통과; source archive와 release checksum 최종 검증 예정 |

## 현재 금지 주장

- 실제 보드에서 측정한 성능 또는 전력
- 완성된 생산용 DDR/GTH/MIG 구현
- 전체 가속기 가격 또는 저비용 달성
- 3B 모델 실행 완료
- 제작 가능한 PCB
- 요청 단위 꼬리 지연 개선
- 모든 조건에서 우월한 작업 훔치기
- 의존성을 무시한 기존 32-token pooled 결과를 실제 decode-32로 해석

## P0 처리 결과

1. 닫힌 논리 RTL 경로와 실제 타일 trace: 완료.
2. 원격 전송 비용·의존성·token 장벽 반영 실험: 완료.
3. K26-local 및 초기 배치 기준선: 완료.
4. 연구 동결 문서와 Figure source 교체: 완료.
5. 연구 동결 이후 v11 논문·14장 발표 생성: 완료.
6. 남은 P0: 과거 Vault 토큰 폐기·교체 및 GitHub secret-scanning 경보 #1 해소.
