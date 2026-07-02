<!--
=============================================================================
File   : isppipeline/hls/results/improvement-strategy-2026-07-03.md
Date   : 2026-07-03
Time   : 00:40 KST
Function: design-limitations-2026-07-03.md·dfx-vivado-considerations-2026-07-03.md
          에서 발견한 항목들을 실행 가능한 단계별 개선 전략으로 재구성.
Goal   : "개선 전략 수립" 요청에 대한 응답 — 무엇을 왜 먼저 할지, 각 항목의
          구체적 기술 접근·성공 기준·의존관계·보드 필요 여부를 명시.
=============================================================================
-->
# DFXISP 개선 전략 (2026-07-03)

> `design-limitations-2026-07-03.md`(무엇이 문제인가)와
> `dfx-vivado-considerations-2026-07-03.md`(DFX 구현에서 무엇을 겪었나)를 바탕으로
> "다음에 무엇을, 왜 그 순서로 할지"를 정리한다. 원칙: **보드 없이 끝낼 수 있는
> 것부터 끝낸다** — 보드는 유일하게 병렬화 안 되는 자원이므로, 보드에 올리기 전에
> SW/시뮬레이션으로 밝힐 수 있는 건 다 밝혀두는 쪽이 전체 일정을 줄인다.
>
> **갱신(같은 날 후속 실행):** Phase 0~2의 6개 항목("의존성 없음, 병렬 가능")을
> 모두 실행했다 — 결과: `results/phase0-2-execution-2026-07-03.md`. 각 항목의
> 상태는 아래 해당 절 제목에 표시.

---

## 전략 원칙

1. **mAP를 다시 쫓지 않는다.** guardrail은 "방향 A"(자원/전력 근거)로 이미
   답을 냈다 — low-light RM을 mAP로 정당화하려는 시도(ver2-A/B 같은 재시도)는
   전략에서 제외한다. 단, §1.2에서 밝힌 원인(BLC/WB)을 고치는 것은 **mAP가 아니라
   "설계가 의도대로 동작하는가"** 문제라 별개로 다룬다.
2. **PR 컨트롤러가 없으면 Stage 6는 시작조차 못 한다.** 이게 이번 전략에서
   유일한 진짜 blocking item이다 — 다른 항목은 병렬로 진행 가능하지만 이것만은
   순서상 먼저다.
3. **모든 항목에 "성공 기준"을 명시한다.** "개선했다"를 주장하려면 무엇을 재는지
   미리 정해둔다(이번 세션에서 "미비한 수치도 기록"한 습관을 그대로 유지).

---

## Phase 0 — 즉시 (보드 불필요, 하루 이내, 의존성 없음)

### 0.1 golden model 교차검증 CI 게이트 — ✅ 실행 완료(2026-07-03)
**문제:** `gen_golden_vectors.py`가 `dfxisp_accel.cpp`와 같은 버그를 미러링해도
`make verify`가 못 잡았다(§5.3 검증 방법론 맹점).
**전략:** golden CSV 생성과 **독립적인** 제3의 참조를 추가한다 — 예를 들어
`isp_pipeline_ver1.py`(SW eval이 쓰는, 이미 색상보존이 검증된 구현)의
`_bin_demosaic_rggb16`을 골든 벡터 생성 스크립트가 아니라 **테스트 스크립트에서
직접 import**해 C-sim 출력과 대조하는 별도 assert를 추가. 세 독립 구현(C++, golden
CSV 생성기, SW eval)이 모두 일치해야 통과.
**성공 기준:** 이 게이트가 있었다면 이번 세션 초반의 색상손실 버그를 `make verify`
단계에서 잡았어야 한다 — 회귀 테스트로 그 시나리오를 재현해 확인.
**리스크:** 낮음. **의존성:** 없음.

### 0.2 pblock 재검토(측정만, 재구현은 Phase 2) — ✅ 실행 완료(2026-07-03)
**문제:** 2개 클럭 리전 중 1개가 0.06%만 기여(§1.2/§4.2).
**전략:** 지금 당장 재floorplan하지 말고, 우선 `report_utilization -pblocks`로
**왜** 이런 배분이 나왔는지 원인만 규명(RP 셀들의 실제 배치 좌표를 `report_cell_lo
cation` 등으로 조회해 어느 클럭 리전에 몰려 있는지 확인). 재설계는 Phase 2에서
더 큰 RM 후보가 필요해질 때 묶어서 처리.
**성공 기준:** "왜 X1Y0에 99.94%가 몰렸는지"에 대한 구체적 설명(예: RM 셀의
초기 배치 시드가 특정 코너에 편향) 확보.
**리스크:** 낮음(조사만). **의존성:** 없음.

---

## Phase 1 — 알고리즘 개선 (보드 불필요, SW proxy로 검증)

### 1.1 저조도 baseline core WB 완화 — ✅ 실행 완료(2026-07-03, 승자: BLC 완화)
**문제:** ExDark에서 손실의 70%가 정적 WB 게인(R×1.117/B×1.199, 조도 무관 고정값)
에서 발생(§1.2).
**전략(구체적 실험 설계, 3개 변형을 ablation과 같은 방식으로 비교):**
  - **변형 A(WB 게인 완화):** `dark_ratio`가 높을수록 AWB 게인을 1.0(무보정)에
    선형 보간. 예: `gain_eff = lerp(1.0, gain_nominal, 1 - dark_ratio)`.
  - **변형 B(BLC 완화):** 저조도에서 BLC offset을 낮춰(예: 16→8) 어두운 신호
    클리핑을 줄임 — `ll_bin_radiometric` ablation에서 손상이 BLC/WB 어느 쪽
    비중이 더 큰지 아직 분리 안 됐으므로, 이 실험이 그 분리도 겸한다.
  - **변형 C(WB 완전 생략, baseline core 재정의):** low-light 경로에서만
    `apply_blc_wb12`를 건너뛰고 tone(gain+gamma)만 적용 — `ll_fullres_tone`
    ablation의 반대 극단(WB 없이 gain/gamma만)을 테스트.
**도구:** `tools/isp_pipeline_ablation.py`에 세 변형을 arm으로 추가 →
`tools/eval_map_ablation.py`로 ExDark n=71/COCO n=80(기존 Stage 3와 동일 표본
크기로 확대, 비교 가능하도록) mAP 재측정.
**성공 기준:** 변형 중 하나라도 ExDark lowlight mAP가 현재(0.062, ablation n=31
기준)에서 **normal(0.105) 이상**으로 회복하면 1차 성공 — `none`(0.220) 역전은
guardrail상 기대하지 않는다(원칙 1).
**리스크:** 중간(SW proxy 결과가 real-RAW로 이어진다는 보장 없음, §2.1 한계 상속).
**의존성:** 없음. **예상 소요:** 반나절(ablation 인프라 재사용).

### 1.2 checker 임계값 일반화 재검증 — ✅ 안전성 교차검증 완료(2026-07-03, COCO에서 무해 확인)
**문제:** `DARK_RATIO=0.80`이 두 데이터셋 스윕으로만 얻어짐(§1.3).
**전략:** 이번 실험(1.1)에서 만든 WB-완화 변형에 맞춰 checker 임계값도 함께
재스윕할지 결정 — WB를 완화하면 저조도 판정 자체의 최적 임계도 바뀔 수 있음.
**성공 기준:** 1.1의 승자 변형이 정해진 뒤 판단(선행 조건 있음).
**리스크:** 낮음. **의존성:** 1.1 완료 후.

---

## Phase 2 — DFX 인프라 완성 (보드 불필요, 순수 HDL/Vivado)

### 2.1 PR 컨트롤러 설계·합성 — 최우선 blocking item — ✅ 1차 설계+시뮬레이션 완료(2026-07-03)
**문제:** 설계에 `ICAPE3`/`STARTUPE3`가 0개(§4). 이게 없으면 Stage 6에서 "무엇이
재구성을 트리거하는가"가 정의되지 않는다.
**전략:**
  1. 최소 기능 FSM 설계: `IDLE → DRAIN_WAIT(ap_idle 폴링) → ICAP_ARM → ICAP_STREAM
     → ICAP_DESYNC → RM_WARMUP → IDLE`.
  2. `ICAPE3` 인스턴스화 + 32-bit write 시퀀스(어제 시뮬레이션에서 이미 실제
     partial bitstream의 word 구조·DESYNC 위치를 파일 레벨로 검증해뒀으므로
     그대로 재사용 가능 — `results/pr-latency-vivado-sim-2026-07-02.md`).
  3. `STARTUPE3`는 **일단 인스턴스화하지 않는 방향으로 검토**(부분 재구성은
     전체 재시작이 필요 없으므로) — 대신 완료 판정은 ICAPE3의 `PRDONE`이 아니라
     **자체 word-count 카운터**(스트리밍한 word 수 == 171,633이면 완료)로
     대체하는 실용적 설계. 이러면 어제 시뮬레이션에서 막혔던 문제(§2.2)를
     설계 단계에서 우회할 수 있다.
  4. bitstream 저장처는 아직 PS/DDR이 없으므로, 우선 **BRAM에 partial
     bitstream을 미리 로드**해두는 fabric-only 버전으로 시작(PS/DDR 통합은
     Phase 3).
**성공 기준:** 이 FSM을 XSIM으로 시뮬레이션했을 때 **word-count 기반 완료
신호가 실제로 assert**되는지 확인 — 이게 통과하면 어제 실패했던 "trigger→완료"
측정을 재시도해 이번엔 진짜 숫자를 얻는다.
**리스크:** 중간(신규 RTL 설계, 검증 필요). **의존성:** 없음(§2.2 pblock과 병행
가능). **예상 소요:** 2~3일(FSM 설계+합성+시뮬레이션 재시도).

### 2.2 pblock 재floorplan (0.2의 원인 규명 후) — ✅ 실행 완료(2026-07-03, 용량 2배)
**전략:** 0.2에서 밝힌 원인에 따라 (a) 단일 클럭 리전으로 명시적으로 축소하고
용량 내에서 RM을 설계하거나, (b) RM 셀 배치를 강제 분산시켜 2개 리전을 실제로
고르게 쓰도록 pblock 정의를 조정. LUT/BRAM/DSP 4종 모두 재검증(§1.3).
**성공 기준:** `report_utilization -pblocks`의 Clock Region Statistics에서 두
리전이 모두 유의미한 비율(예: 각 30% 이상)로 기여.
**리스크:** 낮음(플로어플랜 조정만). **의존성:** 0.2.

---

## Phase 3 — 보드 통합 준비 (여기부터 보드 필요성이 생김)

### 3.1 PS/DDR 통합
**전략:** Vivado Block Design으로 Zynq UltraScale+ PS + AXI interconnect +
static 영역(현재 `dfx_static_top`)을 연결. 2.1의 PR 컨트롤러가 SD카드/DDR에서
partial bitstream을 읽어오는 실제 경로로 전환(현재 BRAM 미리로드 버전에서 승격).
**성공 기준:** Block Design synthesis+implementation 성공, PS에서 AXI로 RM
레지스터 접근 가능 확인(fabric-only 시뮬레이션으로 우선 확인 후 보드).
**의존성:** 2.1 완료.

### 3.2 실제 클럭/리셋 핀 배정 + 타이밍 제약
**전략:** ZCU104 XDC로 실제 `ap_clk`/`ap_rst_n` 핀 배정. §6(Phase-무관, 이미
2026-07-03에 200MHz 제약 자체는 검증됨)에 실제 핀 위치만 추가하면 되므로
상대적으로 빠르다.
**의존성:** 3.1.

---

## Phase 4 — 보드 실측 (Stage 6, 이 프로젝트의 마지막 단계)

- 실제 PR latency(trigger→완료, ICAP 실효 대역폭 포함) — 2.1의 PR 컨트롤러가
  이미 있으므로 이번엔 정말로 잴 수 있다.
- 절대 전력(W), DPU/검출기 end-to-end.
- **1.1의 WB-완화 알고리즘 개선이 real-RAW에서도 유효한지 최종 확인**(SW proxy
  천장 가설의 최종 검증 지점).

---

## 요약 타임라인 (의존관계)

```text
Phase 0 (즉시, 병렬)          Phase 1 (SW, 병렬)         Phase 2 (HDL, 병렬)
0.1 golden CI 게이트          1.1 WB 완화 실험 ──▶ 1.2   2.1 PR 컨트롤러 ──▶ (재시도: 진짜 PR latency)
0.2 pblock 원인 규명 ──────────────────────────────────▶ 2.2 pblock 재floorplan
                                                              │
                                                              ▼
                                                    Phase 3: PS/DDR 통합 + 핀 배정
                                                              │
                                                              ▼
                                                    Phase 4: 보드 실측 (Stage 6)
```

**병목:** Phase 2.1(PR 컨트롤러)이 Phase 3 전체를 막는 유일한 진짜 blocking
item이다 — 나머지(0.1, 0.2, 1.1, 1.2)는 순서 상관없이 병렬로 진행해도 된다.

## 산출물
이 문서는 기존 두 보고서(`design-limitations-2026-07-03.md`,
`dfx-vivado-considerations-2026-07-03.md`)의 재구성이며 별도 코드 산출물 없음.
각 Phase 항목 실행 시 별도 dated 문서로 결과를 기록할 것.
