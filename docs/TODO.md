# 프로젝트 TODO 및 진행 현황

이 문서는 현재 저장소 기준으로 남아 있는 작업과 이미 정리된 상태를 간단히 추적하기 위한 문서입니다.

---

## 1. 현재 연구 목표

목표는 다음과 같습니다.

1. pseudo-RAW 기반 ISP 평가 환경을 안정화한다.
2. adaptive ISP가 실제 객체검출 성능을 개선하는지 검증한다.
3. RGB32 기준 HLS/RTL/DFX 구현을 보드까지 연결한다.

---

## 2. 현재 완료된 핵심 항목

| 항목 | 상태 | 메모 |
|------|------|------|
| pseudo-RAW 데이터셋 구축 | 완료 | `Dataset/COCO_5000_raw/`, `Dataset/ExDark_5000_raw/` |
| Python ISP 골든모델 정리 | 완료 | `isppipeline/unprocess/isp_pipeline.py` |
| baseline ISP HLS 정리 | 완료 | `isppipeline/baseline/` |
| proposal ISP HLS 정리 | 완료 | `isppipeline/proposal/` |
| 정적/동적 평가 스크립트 정리 | 완료 | `isppipeline/eval/` |
| README 및 핵심 docs 구조 정리 | 완료 | `README.md`, `docs/` |

---

## 3. 단기 우선 작업

### 3.1 문서/구조 정합

- `docs/`와 실제 코드 경로가 계속 일치하도록 유지
- 레거시 `docs/reference/`와 현재 메인라인 문서의 역할 구분 유지
- RGB32 메인라인과 과거 grayscale/YUYV 기록이 섞이지 않도록 주석 정리

### 3.2 Python / 평가 경로

- `isp_pipeline.py` 기준으로 평가 파이프라인 단일화 유지
- `run_experiment.py`, `run_dynamic.py` 결과 재현 절차 문서화
- 현재 best 학습 레시피와 평가 조합을 명시적으로 정리

### 3.3 HLS / HW 경로

- RGB32 기준 wrapper 및 인터페이스 점검
- baseline / proposal HLS 합성 결과 재확인
- checker / binning / gamma 경로가 Python 골든과 동일한지 유지 점검

---

## 4. 중기 작업

### 4.1 CNN 실험

- ISP-in-the-loop + discriminative LR 조합 재검증
- COCO / ExDark / DynamicSwitch 조건별 최신 mAP 표 재작성
- best 모델 체크포인트와 실험 설정을 문서로 고정

### 4.2 보드 통합

- RGB32 기준 DMA 폭 / 스트림 경로 재정합
- PR bitstream 적재 경로 재정리
- DPU 직결 경로 실제 동작 검증

### 4.3 보고서 정리

- `Research_Roadmap.md`의 진행 현황 수치 최신화
- `Analysis_Report.md`의 historical 내용과 current 내용 구분 유지
- 최종 보고용 요약 문서 작성

---

## 5. 현재 확인된 주의사항

1. `docs/reference/`에는 과거 `isppipeline/demo` 기준 문서가 남아 있다.
2. `isppipeline/_ref/`는 현재 메인라인이 아니라 참조 보관 코드다.
3. 보드 인터페이스 문서 일부는 과거 grayscale / YUYV 기준을 포함한다.
4. 따라서 새 작업은 항상 `README.md`, `docs/Architecture.md`, `docs/Research_Roadmap.md`, `docs/HW_SW_Interface.md`를 우선 기준으로 삼아야 한다.

---

## 6. 다음 작업 제안

가장 우선순위가 높은 다음 단계는 아래 셋입니다.

1. RGB32 기준 보드 통합 경로를 문서와 코드에서 같은 용어로 통일
2. 최신 CNN best setting을 `Research_Roadmap.md`와 `Analysis_Report.md`에 동일하게 반영
3. `docs/reference/` 안의 역사 문서들에 "historical" 성격을 명시
