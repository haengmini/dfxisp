# DFXISP Docs Index

이 폴더는 현재 메인라인 문서와 과거 참조 문서를 분리해서 읽기 위한 진입점입니다.

## 먼저 읽을 문서

| 순서 | 문서 | 목적 |
|---:|---|---|
| 1 | [`../README.md`](../README.md) | 프로젝트 전체 개요 |
| 2 | [`C_SIM_QUICKSTART.md`](C_SIM_QUICKSTART.md) | 새 컴퓨터에서 clone 후 C-Sim 실행 |
| 3 | [`SCENARIO.md`](SCENARIO.md) | 현재 조도 변화 시나리오와 golden-vector 의미 |
| 4 | [`Architecture.md`](Architecture.md) | SW/HW 전체 구조 |
| 5 | [`HW_SW_Interface.md`](HW_SW_Interface.md) | RGB32, pseudo-RAW, 보드 인터페이스 |
| 6 | [`PONYTAIL_REVIEW.md`](PONYTAIL_REVIEW.md) | 현재 구현의 Ponytail 관점 검수 |
| 7 | [`Research_Roadmap.md`](Research_Roadmap.md) | 연구 로드맵 |
| 8 | [`Analysis_Report.md`](Analysis_Report.md) | 실험/분석 요약 |

## 현재 메인라인 기준

현재 검증 가능한 메인라인은 `isppipeline/hls/`입니다.

```text
isppipeline/hls/
  include/dfxisp_accel.hpp
  src/dfxisp_accel.cpp
  tests/test_dfxisp_csim.cpp
  tools/gen_golden_vectors.py
  tests/golden_vectors.csv
  reports/latest.md
```

현재 C-Sim 시나리오는 다음 순서입니다.

```text
NORMAL → NORMAL → NORMAL → LOW_LIGHT → LOW_LIGHT → LOW_LIGHT → NORMAL
```

## historical/reference 문서

`docs/reference/`는 과거 demo, phase, waveform, tutorial 기록 보관 위치입니다. 현재 메인라인 정본이 아니라 다음 용도로만 봅니다.

- 과거 RTLsim/DFX FSM 로그 확인
- 과거 C-Sim/골든 벡터 기록 확인
- 보고서/논문 배경 자료 확인

새 구현/검증 기준은 `docs/README.md`, `docs/C_SIM_QUICKSTART.md`, `docs/SCENARIO.md`, `isppipeline/hls/README.md`를 우선합니다.

## 정리 원칙

- 삭제/대량 이동 없이 index로 역할을 분리한다.
- 현재 실행 가능한 명령은 `C_SIM_QUICKSTART.md`에 둔다.
- 과거 로그는 `reference/`에 보존하되, 현재 PASS로 오해하지 않는다.
- Vivado/Vitis HLS가 없는 환경에서 csynth/cosim/DFX 수치를 만들지 않는다.
