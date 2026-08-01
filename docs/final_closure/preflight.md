# 최종 마감 사전점검

점검일: 2026-08-01
저장소: `https://github.com/snowman0919/varp-k26-memory-fpga`
작업 브랜치: `conference-final`

## 1. 저장소 상태

- 작업 경로: `/home/monad/develop/workbench/varp-k26-memory-fpga`
- 공개 범위: GitHub public repository
- 기본 브랜치: `main`
- 점검 시작 브랜치: `repo-presentation-finalization`
- 현재 작업 브랜치: `conference-final` (`origin/main`에서 분기)
- 점검 시작 시 미커밋 변경: 없음
- 최근 기준 커밋:
  - `be02e39` Remove failing public artifact workflow
  - `d053c4f` remove failing public artifact workflow
  - `f1bab6c` Merge pull request #1 from snowman0919/repo-presentation-finalization
  - `8eaefa1` refresh submission release archives
  - `4dafc83` finalize research-first conference presentation

## 2. 민감정보 점검

### GitHub

- 2026-08-01 재조회에서 열린 secret-scanning 경고 1건을 확인했다.
- 유형은 HashiCorp Vault service token이며, 위치는 과거 커밋
  `730a05b`의 `presentation/final/presentation.pdf`다.
- GitHub는 이 경고를 `publicly_leaked=true`, `validity=unknown`으로 표시한다.
- 현재 작업 트리, 현재 PDF/PPTX, 기존 두 GitHub Release의 중첩 문서를 다시
  검사했으며 같은 고신뢰 패턴은 검출되지 않았다.
- 개인키 헤더 `BEGIN ... PRIVATE KEY`: 현재 파일에서 0건.

### 로컬 산출물

다음을 재귀적으로 검사했다.

- `paper/final/submission_manuscript.pdf`
- `presentation/final/presentation.pptx`
- `presentation/final/presentation.pdf`
- `release/*.zip` 및 ZIP 내부의 중첩 PPTX·문서

고신뢰 자격증명 패턴 검출 결과: 0건.

일반 키워드 `token`, `secret`, `api_key`, `password`, `vault`는 연구 문서와 코드의 토큰 용어 또는 보안 설명 때문에 별도로 분류했다. 실제 자격증명 할당으로 확인된 항목은 없다.

### 도구 가용성

- `gitleaks`: 설치되지 않음.
- `trufflehog`: 설치되지 않음.
- 대체 검사: GitHub secret-scanning API, 전체 Git 이력 패턴 검사, 현재 파일 검사, PDF/PPTX/release ZIP 재귀 검사.

후속 판정: 2026-08-01 09:32 KST에 저장소 소유자 `snowman0919`가 경보 #1을
`false_positive`로 해소했다. 해결 코멘트는 없고 GitHub validity는 `unknown`이지만,
소유자가 실제 비밀이 아니라는 분류를 명시했고 현재 작업 트리·PDF/PPTX·중첩
Release 자산 949개에서도 같은 고신뢰 패턴이 0건이었다. 따라서 force push 없이
보안 Gate를 해제하고 새 공개 Release를 진행한다. 경보에 표시됐던 문자열 자체는
문서나 로그에 기록하지 않는다.

## 3. 핵심 산출물 현황

| 산출물 | 현재 상태 |
|---|---|
| 논문 Markdown/PDF | 존재, PDF 12쪽 |
| 발표 PPTX/PDF | 존재, 16:9 10장 |
| 발표자 노트 | 존재 |
| 학습자료 PDF | 존재, 29쪽 |
| README/CITATION/Makefile | 존재 |
| KiCad | 완성 보드가 아닌 제한된 라우팅 검증 coupon |

## 4. 즉시 확인된 마감 결손

1. 발표자료가 목표 권장 13–16장이 아니라 10장이고 목차가 없다.
2. 현재 KiCad PCB는 K26와 XC7K160T를 실제 부품이 아닌 Samtec 경계 커넥터로 대체했다.
3. 대표 DDR3L x16 한 개만 배치되어 있으며 4채널·8개 package 물리 구현이 아니다.
4. `release/*.zip` 다섯 개가 `main`에 추적돼 있어 목표의 release/main 분리 조건과 충돌한다.
5. 대형 MP4/GIF가 `main`에 다수 추적돼 있다.
6. 논문은 영어 혼용과 방어적 증거 설명이 많아 독립적인 하드웨어 설계 논문으로 재편집해야 한다.
7. 최소 5회 독립 비평과 `paper/revisions/v10.1`–`v10-final` 보존이 아직 증명되지 않는다.
8. 최종 목표가 요구하는 `v10-conference-final` tag/release가 없다.

이 문서는 사전점검 기록이며, 위 결손이 해결되기 전에는 conference-ready 완료로 판정하지 않는다.
