# 온디바이스 sLLM을 위한 K26–Memory FPGA 후보 구조

Kria K26이 연산·제어를 맡고 외부 Memory FPGA가 다채널로 가중치를 공급하는
확장형 가속기 구조를 설계하고, 데이터 이동 비용을 포함한 작업 재분배가 언제
유효한지 평가한 연구 저장소다.

![K26 연산부와 Memory FPGA 가중치 공급부](paper/final/figures/paper_f01_evidence_path.svg)

## 핵심 결론

- Gemma 3 1B INT8와 문맥 길이 32K의 용량 모델은 2.43 GiB다. 따라서 기본 선택은
  K26 로컬이며 외부 8GB는 더 큰 모델·긴 문맥·로컬 경합을 위한 확장 후보다.
- 실제 그래프의 토큰당 183개 투영을 의존성 있는 802개 TileJob으로 변환했다.
- 합성 편향 부하의 동일 시드 다섯 개 중앙값에서 S3는 S1보다 TileJob p95를
  19.13%, p99를 18.71% 줄였다. 반면 Gemma 기존 산술 배치에서는 p95가 0.28%
  늘어 정책 효과가 초기 배치와 이동 비용에 조건부임을 확인했다.
- 대표 실제 가중치 타일 세 개가 작업 수락→DMA 요청→DDR 응답 경계→논리 링크
  FIFO→MatVec 결과의 폐루프 논리 RTL을 통과했고 INT32 기준과 일치했다.

이 수치는 보드 실측이 아니다. GTH·MIG 물리 타이밍, 전체 보드 전력·가격,
제작 가능한 PCB는 아직 검증하지 않았다.

## 연구 기여

1. K26의 연산·제어와 Memory FPGA의 가중치 공급 역할을 분리한 확장 후보 구조
2. 원격 가중치·활성값·부분합 비용을 서비스 시간에 부과한 동적 작업 배치 평가
3. 실제 모델 형상→분석 모델→폐루프 논리 RTL→KiCad 라우팅 쿠폰의 재현 흐름

## 빠른 시작

필수 도구는 Python 3.11+, Java 21, sbt, Verilator, KiCad CLI, Pandoc,
Chromium, Poppler, ffmpeg, Manim과 한글 글꼴이다.

```bash
make setup
make test
make rtl-test
make paper-experiments
make research-freeze
make paper
make presentation
make reproduce
```

허가된 원본 Gemma 3 1B ONNX가 있을 때만 다음 명령으로 trace를 재생성한다.
모델 가중치는 저장소와 release에 포함하지 않는다.

```bash
GEMMA3_1B_ONNX_DIR=/authorized/path make model-trace
```

## 주요 산출물

- [제출 논문](paper/final/submission_manuscript.pdf)
- [기술보고서](paper/technical_report/technical_report.pdf)
- [16장 발표자료](presentation/final/presentation.pptx)
- [발표 PDF](presentation/final/presentation.pdf)
- [발표자 노트](presentation/final/speaker_notes.md)
- [슬라이드별 출처 인덱스](presentation/final/slide_source_index.md)
- [발표 contact sheet](presentation/final/slide_contact_sheet.png)
- [연구 동결 기록](research/v11_research_freeze.md)
- [스터디팩과 Q&A](study/README.md)
- [코드·자료 공개 안내](paper/final/code_and_data_availability.md)
- [학술대회 패키지 통합 인덱스](conference_package/INDEX.md)

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `src/`, `tests/` | 의존성 인식 분석 모델과 검증 |
| `hw/` | SpinalHDL/Verilator RTL과 폐루프 논리 가상 시제품 |
| `experiments/`, `results/`, `evidence/` | Gemma trace, 합성 실험, 결과 CSV |
| `hardware/kicad/` | 일반 경계 라우팅 쿠폰, **NOT FOR FABRICATION** |
| `paper/`, `presentation/`, `study/` | 논문·발표·방어 자료 |

## 재현과 주장 범위

`make research-freeze`는 동일 시드 비교, 원격 복사 비용 부과, Gemma 단계·토큰
의존성, 실제 타일 RTL trace, K26 로컬 기준선과 KiCad 범위를 검사한다. 자세한
논리/물리 경계는 [architecture.md](docs/architecture.md)를 따른다.

## 소스 아카이브

GitHub의 자동 **Download ZIP**은 저장소 tree를 그대로 받는 편의 경로다. 재현
기준은 `v11-conference-final` release에 첨부하는 공식
`VARP_K26_Source.zip`이며, 이 파일은 `source_manifest`와 checksum을 함께
포함한다. 두 경로 모두 모델 가중치는 포함하지 않는다.

## 인용과 라이선스

[CITATION.cff](CITATION.cff)의 최윤혁(한국디지털미디어고등학교,
[ORCID 0009-0006-3537-0249](https://orcid.org/0009-0006-3537-0249)) 정보를 사용한다.
소스 사용 조건은 [LICENSE](LICENSE)를 따른다.
