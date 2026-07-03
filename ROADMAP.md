<!--
=============================================================================
File   : ROADMAP.md
Date   : 2026-07-03
Time   : 09:10 KST
Function: DFXISP 프로젝트 전체 과정을 시작부터 현재까지 단계별로 정리하고,
          각 단계의 현재 상태를 표시하는 최상위 내비게이션 문서.
Goal   : "우리의 프로젝트 전 과정을 모두 단계별로 작성하고 현재 상태를 같이
          표시해" 요청에 대한 응답. 이 문서는 새 실험이 아니라 지금까지의
          57개 커밋·수십 개 dated 문서를 하나의 타임라인으로 재구성한 것.
=============================================================================
-->
# ROADMAP.md — DFXISP 프로젝트 로드맵

**프로젝트:** DFXISP — Zynq UltraScale+ ZCU104를 위한 Resource-Aware Register/DFX
분할 적응형 ISP (mAP는 register-fast path, 면적·전력은 DFX 부분재구성이 담당)
**대상 보드:** ZCU104, `xczu7ev-ffvc1156-2-e`
**목표:** 석사 학위논문(제주대 전자공학과, 목표 2026.10)
**정본 문서:** 아키텍처 `RESEARCH.md`, 시스템 스펙 `SPEC.md`, 이 문서는 진행 상태 추적용
**마지막 갱신:** 2026-07-03 09:10 KST

## 상태 범례

| 기호 | 의미 |
|---|---|
| ✅ | 완료 — 실측/실행 완료, 근거 문서 있음 |
| ⚠️ | 완료했으나 알려진 한계·트레이드오프가 있음(정직하게 기록됨) |
| 🔄 | 부분 진행 — 1차 결과 있음, 후속 필요 |
| ⬜ | 미착수 — 대부분 실물 보드가 필요해서 지금 못 함 |

## 전체 진행률 한눈에

```text
Phase 0  초기 RM 스크리닝(방향 A 발견)          ✅  2026-06-08 ~ 06-29
Phase 1  아키텍처 reset                          ✅  2026-07-01
Phase 2  SW 트랙 Stage 0~3(checker/mAP)          ✅  2026-07-01 ~ 02
Phase 3  알고리즘 개정 ver1/ver2                 ✅  2026-07-02
Phase 4  HW Stage 4: 실제 Vitis HLS C-synthesis  ✅  2026-07-02
Phase 5  HW Stage 5: 실제 Vivado DFX 구현        ✅  2026-07-02
Phase 6  Adversarial review + 결함 수정           ✅  2026-07-02
Phase 7  수정 반영 전체 재합성                    ✅  2026-07-02
Phase 8  마이크로아키텍처 문서화                  ✅  2026-07-02
Phase 9  DFX latency 분해 + low-light 원인 규명   ✅  2026-07-02
Phase 10 Vivado 시뮬레이션 기반 latency 실측 시도 ⚠️  2026-07-02  (방법론 한계 발견)
Phase 11 설계 한계 종합 + 개선 전략 수립           ✅  2026-07-03
Phase 12 개선 전략 Phase 0~2 즉시 실행(6항목)     ✅  2026-07-03
Phase 13 BLC 완화 정본 반영 + 최종 재합성          ✅  2026-07-03
─────────────────────────────────────────────────────────────────
Stage 6  보드 실장 + DPU end-to-end               ⬜  미착수(유일하게 남은 단계)
```

---

## Phase 0 — 초기 RM 후보 스크리닝 (2026-06-08 ~ 06-29) ✅

**목표:** DFX Reconfigurable Module 후보들(binning, feature-preserving 등)을
mAP guardrail과 자원/전력 기준으로 스크리닝.

- `dfxisp_hls_variants.cpp`에 4개 top(`normal`/`reg_only`/`dfx_bin`/`dfx_fp`) 실제
  Vitis HLS csynth: 모두 동일 critical path(3.65ns, 273.97MHz) — **타이밍은 변별점이
  아니고 면적·전력이 변별점**임을 최초로 확인.
- YOLOv8n/s + SSDLite-MobileNetV3 3-detector 교차검증(ExDark n=260): **register-only가
  최고**, **DFX-FP가 최저**(guardrail 탈락, detector 무관하게 재현) → **"방향 A"**
  (mAP는 register가 담당, DFX는 자원/전력 절감 근거) 확립.
- DFX(2-RM 배치, reg+bin) 정적 면적 절감은 미미(0.7% LUT)하지만, 저조도에서만
  binning datapath(fabric의 75%)가 상주하는 **전력 절감**이 지배적 이득으로 식별.
- **결론:** 논문 방향을 "mAP 향상"에서 "**자원/전력 근거의 register/DFX 분할
  방법론**"으로 재편. 이 재편이 이후 모든 단계의 전제가 됨.

**근거:** `isppipeline/hls/results/10-hw-csynth-resource-2026-06-29.md`,
`11-ssd-crosscheck-2026-06-29.md`, `archive/docs-reorg-2026-07-01/paper/00-thesis-outline.md`.

---

## Phase 1 — 아키텍처 reset (2026-07-01) ✅

**목표:** Phase 0의 scaffold(demosaic 후 RGB8 gain/lift)가 의도한 연구 아키텍처
(**공유 baseline ISP core + 상호배타 mode-specific tone RM slot**)에서 벗어났음을
확인하고 정본을 다시 정렬.

- `RESEARCH.md` 확립: RM_NORMAL_TONE / RM_LOW_LIGHT_TONE 상호배타 tone RM slot 설계.
- Stage 0~6 단계별 실험 계획 수립(SW 트랙 0~3 + HW 트랙 4~6).
- de-duplication 불변식 확정: gain/gamma는 tone RM에만, baseline core는 절대 중복 없음.

**근거:** `RESEARCH.md` §0, `isppipeline/hls/results/experiment-stages-2026-07-02.md`,
`experiment-plan-2026-07-01.md`.

---

## Phase 2 — SW 트랙 Stage 0~3 (2026-07-01 ~ 02) ✅

**목표:** 보드 없이 SW proxy(pseudo-RAW)로 golden model·checker·mAP guardrail 확정.

- Stage 0: shared baseline core + tone RM golden model bit-exact 확정(`make verify`).
- Stage 1: checker + 히스테리시스 스케줄러 튜닝 — narrow 밴드+temporal_N=3이 최적
  (mismatch 0.015, thrashing 0, 기본값 대비 9배 개선).
- Stage 2: arm별(none/normal/lowlight/adaptive) 이미지 지표 집계.
- Stage 3: 3-detector mAP 조건표 A~G — **모든 조건에서 `none`이 최고**,
  `normal`/`lowlight`가 오히려 mAP를 낮춤(guardrail 최초 탈락 확인).

**근거:** `isppipeline/hls/results/stage1-3-results-2026-07-02.md`,
`experiment-report-2026-07-02.md` §4.

---

## Phase 3 — 알고리즘 개정 ver1/ver2 (2026-07-02) ✅

**목표:** Phase 2의 guardrail 탈락 원인(정상모드가 오히려 어두워지는 버그 등)을 수정.

- **ver1(RAW-domain-first):** 보정을 demosaic 전 12/16-bit RAW 도메인에서 수행,
  normal에도 exposure gain 추가, 모든 모드에 gamma 적용(저조도는 완화).
  ExDark normal mAP +17~21%, lowlight도 개선 — 그러나 **여전히 `none`이 최고**
  (SW proxy 천장 가설, guardrail 유지).
- **ver2(checker 재보정):** dark-level 임계값을 Youden's J 스윕으로 0.40→**0.80**
  재보정 — COCO 과트리거 79.5%→11%로 감소.

**근거:** `results/experiment_ver1_2026-07-02.md`, `experiment_ver2_2026-07-02.md`.

---

## Phase 4 — HW Stage 4: 실제 Vitis HLS C-synthesis (2026-07-02) ✅

**목표:** SW golden model을 실제 Vitis HLS 2024.1로 C-synthesis해 자원/타이밍 확보.

- streaming line buffer 리팩터(4MB scratch → O(3×960) BRAM), gamma를 런타임
  Newton's-method isqrt에서 256-entry ROM LUT로 교체(FF -88%, LUT -78%).
- unified top(`dfxisp_accel`) + RM_NORMAL_TONE/RM_LOW_LIGHT_TONE 독립 top 3종
  모두 실측: Fmax 273.97MHz(수정 없이 5.0ns 타깃 충족).
- C/RTL Co-sim: RTL 실행 자체는 7/7 성공(긍정 신호)했으나 자동 bit-exact
  비교 단계가 WSL2+XSIM 환경 특유의 하네스 문제로 SIGSEGV — **자동 비교 미완주**.

**근거:** `results/stage4-hw-synthesis-2026-07-02.md`. ⚠️ **한계:** Co-sim 자동
비교 미완주(§6b), 최초 수치는 이후 Phase 6/7에서 갱신됨.

---

## Phase 5 — HW Stage 5: 실제 Vivado DFX 구현 (2026-07-02) ✅

**목표:** RM 2종을 실제 Reconfigurable Partition으로 플로어플랜·구현·검증.

- AMD UG909 표준 절차(non-project batch Tcl): static wrapper 자동 생성, pblock
  플로어플랜, config1(static+NORMAL)/config2(static+LOW_LIGHT, black-box+lock
  방법론) 구현.
- 트러블슈팅 5건 실전 해결: I/O 핀 초과, RP 인스턴스 삭제, SNAPPING_MODE 빈
  pblock, static 배치 불일치(→black-box+lock으로 해결), DRC 우회.
- **pr_verify PASS**, full/partial bitstream 생성 — "보드 측정 전단계" 완료 선언.

**근거:** `results/stage5-dfx-implementation-2026-07-02.md`.

---

## Phase 6 — Adversarial review + 결함 수정 (2026-07-02) ✅

**목표:** `/codex:adversarial-review`로 Phase 1~5 전체 커밋을 독립 검토.

- **Finding 1(high):** 저조도 binning이 4샘플을 스칼라 평균 후 재-demosaic —
  색 정보 파괴 버그. golden model도 같은 버그를 미러링해 `make verify`가
  못 잡음(검증 방법론 자체의 맹점).
- **Finding 2(medium):** 메타데이터 출력이 검증 안 된 구조체 포인터 `s_axilite`.
- **수정:** binning-demosaic 융합(채널 보존) + 4개 scalar 출력 포인터로 교체.
  `make verify` 646px bit-exact 유지, 새 회귀 테스트 추가.

**근거:** `SPEC.md` §11.5, 커밋 `a2d1b6d`.

---

## Phase 7 — 수정 반영 전체 재합성 (2026-07-02) ✅

**목표:** Phase 6 수정을 반영해 Vitis HLS + Vivado 전체를 처음부터 재실행.

- 자원 감소: unified top LUT -26.3%, low-light RM LUT -41.3%(버그였던 2차
  demosaic 로직 제거 효과).
- **pr_verify PASS 유지**, partition pin **2개→15개**로 증가 — 메타데이터
  수정이 실제 하드웨어(post-route)에서도 물리적으로 반영됐다는 직접 증거.
- bitstream 크기 byte 단위로 불변(로직 감소와 무관, pblock 프레임 수로 결정됨을 재확인).

**근거:** `results/stage4-hw-synthesis-2026-07-02.md`(갱신), `stage5-dfx-implementation-2026-07-02.md`(갱신).

---

## Phase 8 — 마이크로아키텍처 문서화 (2026-07-02) ✅

**목표:** Arm2(register-only)와 Arm3(DFX)의 실제 합성 구조를 다이어그램화.

- 실제 코드 기준(개념도 아님)으로 SVG+drawio 제작 — RP 경계가 baseline core를
  포함해 모드별 전체 파이프라인을 통째로 감싼다는 사실을 정확히 반영.
- Visio 호환(.vsdx 직접 생성 대신 drawio→Vivado-safe export 경로 채택).

**근거:** `isppipeline/hls/results/dfxisp-microarchitecture-2026-07-02.{svg,drawio}`.

---

## Phase 9 — DFX latency 분해 + low-light mAP 원인 규명 (2026-07-02) ✅

**목표:** DFX 전환 latency 단계별 분해, low-light RM이 mAP를 못 올리는 진짜 원인 규명.

- **Latency:** drain(실측 74~171cyc)+ICAP 전송(스펙 유도 peak 1.72ms/전형
  6.87ms)+warm-up(실측) — ICAP이 전체의 >99.9% 지배.
- **mAP 원인(5단계 ablation):** 기존 "해상도 손실" 추정을 반증 — **ExDark(저조도)
  에서는 BLC/WB(공유 core)가 손실의 70%**, 해상도 손실은 −1.4%뿐. COCO(정상조도)
  에서는 반대로 해상도 손실이 지배적. **원인이 조도 조건별로 정반대**라는 게 핵심 발견.

**근거:** `results/pr-latency-breakdown-2026-07-02.md`,
`lowlight-rm-map-rootcause-2026-07-02.md`.

---

## Phase 10 — Vivado 시뮬레이션 기반 latency 실측 시도 (2026-07-02) ⚠️

**목표:** 계산이 아니라 실제 Vivado 시뮬레이션으로 trigger→완료 latency를 측정.

- 실제 partial bitstream을 ICAPE3 UNISIM 모델에 직접 스트리밍하는 테스트벤치 제작,
  5회 반복 실행. SYNC는 성공(bitstream 구조 유효성 확인)했지만 **PRDONE 완료
  신호를 3가지 독립 방법으로도 못 얻음**.
- **원인:** `PRDONE`이 `eos_startup`(`STARTUPE3` 필요)에 의존하는데, 격리된
  ICAPE3 단독 테스트벤치엔 그 인프라가 없음 — **방법론 자체의 한계**로 판명
  (Phase 11에서 "설계에 ICAPE3/STARTUPE3가 아예 없다"는 사실로 재확인/설명됨).
- **상태를 ⚠️로 표시하는 이유:** 목표(실측 latency 확보)는 못 이뤘지만, 시도
  자체가 이후 Phase 12(PR 컨트롤러 설계)에 직접적인 설계 힌트(word-count 기반
  완료판정)를 제공했다 — 헛수고가 아니었음을 명시.

**근거:** `results/pr-latency-vivado-sim-2026-07-02.md`.

---

## Phase 11 — 설계 한계 종합 + 개선 전략 수립 (2026-07-03) ✅

**목표:** Phase 0~10에서 흩어져 있던 한계·가정·TODO를 종합하고 실행 전략으로 재구성.

- 5개 층위(알고리즘/SW eval/HW synthesis/DFX 구현/시뮬레이션)로 구조화한 한계 종합.
- Vivado DFX 실무 트러블슈팅 체크리스트 + **신규 발견**: pblock이 2개 클럭
  리전에 걸쳐 있다고 정의해도 실제로는 한쪽이 PS 하드매크로에 점유돼 0.06%만
  기여(X0Y0), timing 제약을 걸어 실제 WNS 확보(config1 +0.619ns/config2 +1.930ns).
- 6개 즉시 실행 가능 항목(Phase 0~2)과 보드 필요 항목(Phase 3~4)으로 분류한
  실행 전략 수립 — **유일한 진짜 blocking item: PR 컨트롤러 부재**.

**근거:** `results/design-limitations-2026-07-03.md`,
`dfx-vivado-considerations-2026-07-03.md`, `improvement-strategy-2026-07-03.md`.

---

## Phase 12 — 개선 전략 Phase 0~2 즉시 실행 (2026-07-03) ✅

**목표:** Phase 11이 "의존성 없음"으로 분류한 6개 항목 전부 실행.

| 항목 | 결과 |
|---|---|
| golden model 독립 교차검증 게이트 | `make verify`에 통합, 과거 버그 재현 시 검출 확인 |
| pblock 클럭 리전 편중 원인 규명 | X0 컬럼 Y0~Y3 = PS 매크로, SLICE 0개 확정 |
| 저조도 BLC/WB 분리 ablation | **BLC 완화가 진짜 승자**(WB 아님) — ExDark mAP +141%(ablation 기준) |
| PR 컨트롤러 1차 FSM 설계+시뮬레이션 | word-count 기반 완료판정으로 Phase 10 한계 우회, trigger→완료 1.716ms 실측(분석 추정과 교차검증 일치) |
| pblock 재floorplan | X1Y0:X2Y0으로 용량 2배(LUT 8,640→19,200), pr_verify PASS 유지 |

**근거:** `results/phase0-2-execution-2026-07-03.md`,
`results/pr_controller/pr_controller{,_tb}.v`, `tools/verify_binning_cross_check.py`.

---

## Phase 13 — BLC 완화 정본 반영 + 최종 재합성 (2026-07-03) ✅

**목표:** Phase 12의 ablation 승자(BLC 완화)를 정본 파이프라인에 반영하고 전체 재합성.

- `apply_blc_wb12()`를 파라미터화, low-light만 BLC 128(정상 256의 절반) 적용.
  C++/golden/SW eval 3파일 동기화, `make verify`+cross-check 게이트 통과.
- **mAP(표준 n=71/80):** ExDark lowlight 0.0586→**0.1043**(+78%, **처음으로
  normal을 상회**), COCO 0.2647→0.2857(+8%, 무해).
- HLS csynth 3종 **자원 완전 불변**(상수 하나만 바뀐 순수 파라미터 변경 —
  mAP 개선이 HW 비용 없이 달성됨).
- Phase 12의 pblock fix와 결합 재구현: **pr_verify PASS 유지**하지만 partial
  bitstream이 **2.11배 커짐**(686,664B→1,447,424B, pblock 용량 확장의 직접적
  대가로 정직하게 기록 — 재구성 지연도 2.11배).

**근거:** `results/blc-fix-resynthesis-2026-07-03.md`.

---

## Stage 6 — 보드 실장 + DPU end-to-end ⬜ (유일하게 남은 단계)

Phase 1~13으로 "보드 측정 전단계"가 완료됐다. 남은 것은 실물 ZCU104에서만
확인 가능한 항목들이며, `improvement-strategy-2026-07-03.md` Phase 3~4에
이미 순서가 정의돼 있다:

| 순서 | 항목 | 의존성 | 상태 |
|---|---|---|---|
| 1 | PS/DDR 통합(Block Design) | Phase 12의 PR 컨트롤러 1차 설계 | ⬜ |
| 2 | 실제 clock/reset 핀 배정 + 타이밍 제약 | 1 | ⬜ |
| 3 | 실제 PR latency 실측(trigger→완료, ICAP 실효 대역폭) | 1, 2 | ⬜ |
| 4 | 절대 전력(W) 측정 | 1, 2 | ⬜ |
| 5 | DPU/검출기 end-to-end 실행(Vitis-AI, real-RAW) | 1~4 | ⬜ |
| 6 | Phase 13 BLC 완화가 real-RAW에서도 유효한지 최종 확인 | 5 | ⬜ |

**PR 컨트롤러 1차 설계(Phase 12)는 됐지만 아직 "1차"다** — `drain_ready`는
테스트벤치가 임의로 생성한 신호이지 실제 RM의 `ap_idle`이 아니고, BRAM은
실제 SD/DDR 저장 경로가 아니라 시뮬레이션 전용이다. Stage 6 착수 전 이 부분의
완성이 사실상 남은 유일한 진짜 선결 과제다.

---

## 문서 지도 (전체 산출물, 시간순)

```text
Phase 0   isppipeline/hls/results/10-hw-csynth-resource-2026-06-29.md
          isppipeline/hls/results/11-ssd-crosscheck-2026-06-29.md
Phase 1   RESEARCH.md · isppipeline/hls/results/experiment-stages-2026-07-02.md
Phase 2   isppipeline/hls/results/stage1-3-results-2026-07-02.md
Phase 3   isppipeline/hls/results/experiment_ver{1,2}-2026-07-02.md
Phase 4   isppipeline/hls/results/stage4-hw-synthesis-2026-07-02.md
Phase 5   isppipeline/hls/results/stage5-dfx-implementation-2026-07-02.md
Phase 6   SPEC.md §11.5 (커밋 a2d1b6d)
Phase 7   (stage4/5 문서 2026-07-02 내 갱신 이력 참조)
Phase 8   isppipeline/hls/results/dfxisp-microarchitecture-2026-07-02.{svg,drawio}
Phase 9   isppipeline/hls/results/pr-latency-breakdown-2026-07-02.md
          isppipeline/hls/results/lowlight-rm-map-rootcause-2026-07-02.md
Phase 10  isppipeline/hls/results/pr-latency-vivado-sim-2026-07-02.md
Phase 11  isppipeline/hls/results/design-limitations-2026-07-03.md
          isppipeline/hls/results/dfx-vivado-considerations-2026-07-03.md
          isppipeline/hls/results/improvement-strategy-2026-07-03.md
Phase 12  isppipeline/hls/results/phase0-2-execution-2026-07-03.md
Phase 13  isppipeline/hls/results/blc-fix-resynthesis-2026-07-03.md
전체 종합  isppipeline/hls/results/experiment-report-2026-07-02.md (SW+HW 통합 서사)
```

---

문서 끝 — 새 Phase를 시작하면 이 파일 상단 요약표와 해당 Phase 섹션에 추가할 것.
`SPEC.md`(시스템 스펙)·`RESEARCH.md`(아키텍처 정본)와 함께 최신 상태 유지.
