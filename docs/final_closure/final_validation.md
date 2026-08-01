# v11 최종 검증 기록

검증일: 2026-08-01  
브랜치: `conference-final`  
검증 기준 코드·데이터 커밋: `000f0c4`

## 판정

연구 모델, 논리 RTL 경로, KiCad 제한 쿠폰, 논문, 발표, 학습자료와 공식 소스
아카이브의 로컬 품질 Gate는 **PASS**다. 공개 GitHub Release만 과거 커밋에 남은
Vault token 경보 #1의 폐기·교체 확인 전까지 보류한다.

## 실행한 Gate

| 명령·검사 | 결과 |
|---|---|
| `make test` | PASS — Python 38개, archive 전용 1개 skip |
| `make rtl-test` 경로 | PASS — Scala/RTL 19개 |
| `make publication-index` | PASS — Figure 10개, flow 5개, 최소 환산 11.04 pt |
| `make paper` | PASS — 제출본 8쪽, 기술보고서 10쪽, 최소 Figure 글자 8.102 pt, PDF 텍스트 감사 |
| `make presentation` | PASS — 14장, 내장 영상 4개, notes 14개, 목표 580초·낭독 추정 574.3초, 최소 12 pt |
| 본선 심사 기준 Gate | PASS — 주제 이해도·전달성·질의응답·참여도 매핑, 슬라이드별 그림 순서·예상 질문·답변·주의 표현 14개 |
| `make reproduce` | PASS — 연구 동결·KiCad·논문 포함, `source_clean_gate=PASS` |
| `make release` | PASS — 공식 패키지 5종 생성 |
| `sha256sum -c release/checksums.sha256` | PASS — 5종 모두 일치 |
| `make source-archive-test` | PASS — 실제 `release/VARP_K26_Source.zip` 내부 38개 테스트·Figure 재생성·manifest 무결성 |
| `make github-archive-test` | PASS — GitHub 자동 소스 ZIP 등가 경로 |
| 독립 검토 | PASS — 가속기 기여, 인과, 한국어 가독성, 하드웨어 시각, 발표/Q&A, 최종 언어 6회 |

## 핵심 산출물

- 논문: `paper/final/submission_manuscript.pdf`
- 발표: `presentation/final/presentation.pptx`, `presentation/final/presentation.pdf`
- 발표자 노트·출처: `presentation/final/speaker_notes.md`,
  `presentation/final/slide_source_index.md`
- 연구 동결: `research/v11_research_freeze.md`
- 논리 RTL 추적: `evidence/model/gemma3_1b_closed_loop_trace.csv`
- KiCad 범위: `hardware/kicad/k26_reports/k26_scope_manifest.json`
- 학습자료: `study/study_pack.pdf`, `study/10_qna_bank.md`,
  `study/15_final_round_scoring_strategy.md`
- Release checksum: `release/checksums.sha256`

## 보안 보류 조건

현재 작업 트리·현재 논문/PPTX/PDF·기존 Release 자산의 고신뢰 자격증명 패턴은
검출 0건이다. 그러나 GitHub secret scanning에는 과거 커밋
`730a05b`의 `presentation/final/presentation.pdf`를 가리키는
HashiCorp Vault service token 경보 #1이 열려 있다. 토큰 값을 문서에 기록하지
않는다.

공개 `v11-conference-final` tag/Release 게시 조건은 다음 두 가지다.

1. Vault에서 해당 token을 폐기 또는 교체한다.
2. GitHub 경보 #1을 `revoked`로 해소한 뒤 상태를 재조회한다.

이 조건이 충족되기 전에는 clean branch와 PR은 게시할 수 있지만 새 공개 Release
자산은 게시하지 않는다. Git 이력 force-push는 사용하지 않는다.
