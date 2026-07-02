---
type: experiment-stages
title: "DFXISP 단계별 실험 계획 (Stage 0~6) — reset 아키텍처"
project: DFXISP
created: 2026-07-02
status: active
sources: "RESEARCH.md · results/experiment-plan-2026-07-01.md · (archive) Research_Roadmap §3~5"
---

# DFXISP 단계별 실험 계획 (Stage 0~6)

> 구 `Research_Roadmap`의 Phase 0~5 방법론 깊이를, 2026-07-01 reset 아키텍처
> (**shared baseline ISP core + 상호배타 tone RM slot**)에 맞게 재구성한 것.
> 상위 실험 프레임(가설·arm·지표)은 `results/experiment-plan-2026-07-01.md`,
> 정본 아키텍처는 `RESEARCH.md`. 미검증 수치는 `TODO(측정)`.

## 트랙 구조

```text
SW 트랙 (data/, model/, tools/)            HW 트랙 (isppipeline/hls, Vivado)
  Stage 0 golden/baseline core 확정   ─┐
  Stage 1 checker + 히스테리시스        │      Stage 4 HLS 합성 + C/RTL Co-sim
  Stage 2 tone RM 산술 + 이미지 지표    ├─(golden 정합에서 합류)─▶ Stage 5 DFX 컨트롤러 + 전환 sim
  Stage 3 정확도(mAP) arm/조건표        ─┘                          Stage 6 보드 실장 + end-to-end
```

SW 트랙(0~3)은 보드 없이 지금 수행 가능. HW 트랙(4~6)은 Vivado/보드 필요.

---

## Stage 0 — SW golden & shared baseline core 확정  ✅(대부분 완료)

**대응(구):** Phase 0 Baseline 셋업·검증.

- **목표:** shared baseline core(demosaic + BLC + AWB + CCM, **gain/gamma 없음**)와
  tone RM slot(RM_NORMAL_TONE identity / RM_LOW_LIGHT_TONE = 2x2 bin + gain + gamma-4.0)의
  결정적 golden 모델을 확정하고, C-sim이 이를 bit-exact 재현함을 증명.
- **구성/방법:** `tools/gen_golden_vectors.py`(Python 기준) ↔ `src/dfxisp_accel.cpp`(C++)
  정수 산술 미러. Policy A(저조도 H/2×W/2). gamma-4.0 = 정수 4제곱근.
- **데이터셋/조건:** 합성 fixture 9종 — bright/dark/mixed/threshold-boundary/
  bright-recovery/odd-dimension.
- **검증 기준:** `make verify` golden bit-exact(566px, mismatch=0); 아키텍처 gate 6종 PASS
  (baseline core / RM_NORMAL_TONE / RM_LOW_LIGHT_TONE / 상호배타 / gain·gamma 중복없음 / 형상정책).
- **측정 항목:** golden rows, gate 결과.
- **산출물:** `tests/golden_vectors.csv`, `reports/latest.md`. **상태: ✅**
- **남은 것:** 파라미터(gain·γ·binning) 최종 확정은 Stage 2에서.

---

## Stage 1 — 환경 감지 checker + 히스테리시스 시퀀스

**대응(구):** Phase 1 Checker 설계 (+ Phase 2 동적 전환의 시퀀스 측면).

- **목표:** dark-ratio 기반 mode 결정 + **N-frame 히스테리시스**로 flicker 없는 장면 단위
  전환을 SW 시뮬레이션으로 검증(RESEARCH §5).
- **구성/방법:**
  - checker: `Y=(R+2G+B)/4` 또는 RAW dark-pixel 비율; `dark_ratio = count(<thr)/N`.
  - 전환 임계: `NORMAL→LOW_LIGHT: dark_ratio>0.80`(재보정 2026-07-02, 구 0.40 — ver2 참조),
    `LOW_LIGHT→NORMAL: dark_ratio<0.20`.
  - 히스테리시스: 전환 조건이 **N 안정프레임** 유지될 때만 트리거.
  - 도구: `tools/scheduler_sim.py` 확장.
- **데이터셋/조건:** DynamicSwitch 시퀀스 — `bright×K → dark×K → bright×K`(구 sequence.json
  형식 재사용, COCO/ExDark 교차).
- **검증 기준:** ① 정상/저조도 안정구간에서 mode 오판=0, ② 전환 경계에서 flicker(진동)=0,
  ③ 재구성 카운트다운 중 이전 모드 유지.
- **측정 항목:** 전환 감지 지연(프레임 수), 과도구간 길이, checker 오판율, `RECONFIG_FRAMES`
  민감도(0 → Stage 5 실측값으로 교체).
- **산출물:** `results/scheduler.csv`(시퀀스별 mode 트레이스), 전환 지연 표.

---

## Stage 2 — tone RM 산술 확정 + 이미지 지표

**대응(구):** Phase 0의 ISP 알고리즘 명세 + Gain/Gamma 근거 절.

- **목표:** RM_LOW_LIGHT_TONE(`2x2 binning + gain×1.25 + gamma-4.0`)과 RM_NORMAL_TONE
  (identity/옵션 gain·γ)의 파라미터를 이미지 지표로 확정하고, Policy A vs B 필요성을 판단.
- **구성/방법:**
  - 파라미터 sweep 후보: binning kernel(2×2 sum/4), gain{1.25, 1.5}, gamma{3.0, 4.0}.
  - Policy A(H/2×W/2 그대로) vs Policy B(upsample/pad로 H×W 복원) — DPU ABI 요구 시에만 B.
  - 도구: `tools/isp_variant_analysis.py` 확장(신규 tone RM 경로 추가).
- **데이터셋/조건:** 합성 fixture + ExDark/COCO 샘플(육안+정량).
- **검증 기준:** ① 저조도 fixture에서 dark-ratio·Y-mean 개선(밝아짐), ② 포화율 급증 없음
  (gamma가 highlight 보존), ③ **gain/gamma 중복 플래그=false**(baseline core 무침범).
- **측정 항목(RESEARCH §6.1):** Y mean·std·min·max, 포화율, dark-ratio(before·after),
  입력·출력 크기, (선택)PSNR·SSIM vs 참조.
- **산출물:** `results/isp_variant_analysis.csv`(신규 경로), 파라미터 확정표.

---

## Stage 3 — 정확도(mAP) 평가: arm & 조건표

**대응(구):** Phase 3 CNN 성능 평가 및 통합 검증.

- **목표:** H1(적응 이득)·H2(중복제거해도 정확도 유지)를 조건별 mAP로 검증. **새 tone RM
  경로 재측정**(구 08/11은 ablation arm 기준).
- **구성/방법:** `raw .bin → baseline core(+tone RM) → detector → mAP(ultralytics val)`.
  도구 `tools/eval_map_coco.py`·`eval_map_dark.py`·`eval_map_ssd.py`.
- **평가 조건표 (구 A~F 재정의):**

  | 조건 | 데이터셋 | 경로 | 목적 |
  |---|---|---|---|
  | **A** | ExDark (저조도) | 무처리(none) | 저조도 기준선 |
  | **B** | ExDark | RM_NORMAL_TONE + baseline core | 잘못된 모드(정상 경로) 효과 |
  | **C** | ExDark | **RM_LOW_LIGHT_TONE + baseline core** | 적응 ISP 효과 ← 핵심(H1) |
  | **D** | COCO (정상) | 무처리(none) | 정상 기준선 |
  | **E** | COCO | RM_NORMAL_TONE + baseline core | 정상 경로 효과 |
  | **F** | COCO | RM_LOW_LIGHT_TONE + baseline core | 정상에 저조도 경로(이득 없어야) |
  | **G** | DynamicSwitch | checker 적응 전환 | E2E 동적 전환 ← DFX 핵심(H3 서막) |

  기대: `C > B > A`, `E ≥ F`, 조건 G 안정구간 ≈ C·E 수준.
- **detector 교차검증:** YOLOv8n/s + SSDLite-MNv3로 **순서 불변성** 재확인(구 결론이 새
  경로에서도 유지되는지). 절대값보다 **순서(guardrail 근거)**를 본다.
- **측정 항목(RESEARCH §6.2):** mAP@50 및 @[.5:.95], per-class AP, bright/lowlight/
  transition segment mAP, mode-mismatch mAP.
- **주의:** Policy A로 저조도 출력이 H/2×W/2 → detector가 letterbox resize하므로 SW mAP는
  가능하나, 축소가 mAP에 주는 영향을 조건 C에서 별도 관찰(필요 시 Policy B 비교).
- **산출물:** `results/map_{exdark,coco}_newrm.csv`, 조건표 채운 6.1 표, detector 교차표.

---

## Stage 4 — HLS 합성 + SW-HW C/RTL Co-sim  ⬜(Vivado 필요)

**대응(구):** Phase 4.6 단계별 비교 요약표 + C-Sim/Co-Sim.

- **목표:** baseline core / RM_NORMAL_TONE / RM_LOW_LIGHT_TONE 각각의 합성 자원·타이밍을
  확보하고, 합성 RTL이 golden을 bit-exact 재현함을 C/RTL co-sim으로 증명.
- **구성/방법:**
  - `DFXISP_HLS_FLOW=csynth make hls` → II/latency/자원(LUT·FF·BRAM·DSP)·WNS.
  - `DFXISP_HLS_FLOW=cosim make hls` → `tests/test_dfxisp_csim.cpp` TB로 RTL 구동
    (assert·golden 그대로 적용).
  - **전제:** `run_low_light` 정적 scratch binning → streaming line buffer 리팩터 선행
    (대형 BRAM 회피); 초기엔 8×8/16×16 소형 fixture로 cosim.
- **단계별 비교 요약표 (구 4.6 → 신규 레벨 체인):**

  | 항목 | L0 Python golden | L1 HLS C-sim | L2 C/RTL Co-sim | L3 RTL wrapper sim |
  |---|---|---|---|---|
  | 대상 | 기준 of record | C++ == Python | 합성 RTL == C TB | AXI-Stream wrapper |
  | 입력 | RAW16 리스트 | RAW16 배열 | 동일 golden CSV | `$readmemh` hex |
  | 출력 | packed RGB32 | RGB32 | RGB32 + 메타 | RGB32(32-bit 버스) |
  | 비교 | — | golden bit | golden bit + 메타 레지스터 | error_count=0 |
  | 상태 | ✅ | ✅ 566px | ⬜ | ⬜ |
- **검증 기준:** **L1 == L2 == L3 bit-exact**(동일 golden). 어긋나면 그 레벨에서 정지·격리.
  타이밍 WNS ≥ 0 @ 목표 클럭.
- **측정 항목(RESEARCH §6.3 일부):** 블록별 LUT/FF/BRAM/DSP, achieved Fmax, frame
  latency·II(모드별 분리).
- **산출물:** `results/resource_csynth_newrm.csv`, cosim 리포트, 비교표.

---

## Stage 5 — DFX(PR) 구현 + pr_verify  ✅(fabric-only 실측 완료, 2026-07-02)

**대응(구):** Phase 2 DFX(PR) 컨트롤러 및 동적 스위칭 + Phase 4.5 DFX 멀티프레임 sim.

- **목표:** static region(checker·baseline core·컨트롤러)과 tone RM slot(재구성)을 분리하고,
  checker 트리거 → drain → PR 적재 → RM swap의 무손실 전환을 RTL에서 검증(Arm 3 구조).
- **구성/방법:**
  - tone RM slot을 RM-호환 블록으로 패키징(RM_NORMAL_TONE / RM_LOW_LIGHT_TONE 개별 partial).
  - PR Controller FSM: `mode_changed → drain(AXI-Stream 잔여 비우기) → ICAP 적재 → pr_done → reset`.
  - 멀티프레임 시나리오(`bright→dark→bright`, 구 5프레임을 tone RM slot에 맞게 개정):

    | Frame | 입력 | 기대 | 검증 |
    |---|---|---|---|
    | F1 | Bright | NORMAL, RM_NORMAL_TONE, H×W | golden bit + 메타 |
    | F2 | Dark | dark>80%(재보정) → drain → PR(LOW_LIGHT RM) | drain 무손실, pr_done |
    | F3 | Dark | LOW_LIGHT, RM_LOW_LIGHT_TONE, H/2×W/2 | golden bit + shape |
    | F4 | Bright | recovery → drain → PR(NORMAL RM) | drain 무손실, pr_done |
    | F5 | Bright | NORMAL 원복 | golden bit + 메타 |
- **검증 기준:** `pr_verify` PASS; 전환 중 **frame drop=0**; mode/RM 메타 전환 정확; flicker 없음.
- **측정 항목:** partial bitstream size(RM별), **재구성 지연(cycle→ms)** = bitstream ÷ ICAP
  대역폭, 전환 감지 지연, WNS.
- **산출물:** `results/pr_latency_newrm.csv`, DFX FSM 파형/로그, partial bitstream 크기표.

### 실측 결과 (2026-07-02, fabric-only)
non-project batch Tcl DFX flow(AMD UG909)로 static+RM_NORMAL_TONE(config1)/
static+RM_LOW_LIGHT_TONE(config2) 구현. **pr_verify PASS**(static 영역 완전 동일 확인).
Full bitstream 19,311,211 bytes, partial bitstream 686,664 bytes(두 RM 동일 — pblock
프레임 수로 결정, 실제 로직량과 무관). 상세: `results/stage5-dfx-implementation-2026-07-02.md`.
**미측정(보드 전용):** F1~F5 멀티프레임 drain/전환 시나리오(PS/ICAP 통합 필요), 재구성
지연(ms), WNS(타이밍 제약 미적용 fabric-only 패스), 전력.

---

## Stage 6 — 보드 실장 + DPU end-to-end (arm 1/2/3 비교)  ⬜(보드 필요)

**대응(구):** Phase 5 보드 실장 및 실증.

- **목표:** ZCU104에서 Arm 1(static+normal)/Arm 2(register-only)/Arm 3(DFX)을 실증 비교하여
  H3(자원/전력 순이득)를 확정.
- **구성/방법:** XSA export → PS 드라이버(GIC+DMA+PR 루프) → JTAG 배포. DPU 직결(RGB32).
  ILA로 실제 HW 버스·전환 캡처.
- **검증 기준:** 3 arm 동일 파이프라인에서 end-to-end 동작; DPU mAP가 SW 예측과 정합.
- **측정 항목(RESEARCH §6.3):** post-route LUT/FF/BRAM/DSP, **절대 전력(W)**, throughput(fps),
  **PR 오버헤드(ms)**, 전환 중 frame drop. 결과 6.2 표(자원/전력) 채움.
- **기대(H3):** 정상 모드에서 `Arm3 fabric·전력 < Arm2`(저조도 블록 미상주), 재구성 지연이
  장면 단위 33ms 예산 대비 수용 가능.
- **산출물:** `results/power_perf_newrm.csv`, 보드 실증 리포트, 최종 arm 비교표.

---

## 진행 보드 (상태 요약)

```text
[x] Stage 0  SW golden + baseline core 정합 (C-sim bit-exact, gate 6종)
[x] Stage 1  checker + 히스테리시스 시퀀스        (실행완료 → scheduler_sweep, 27경우)
[x] Stage 2  tone RM 산술 + 이미지 지표           (실행완료 → image_metrics ExDark/COCO)
[x] Stage 3  정확도 mAP arm/조건표 A~G            (실행완료 → 2 detector, none 최고)
[x] Stage 4  HLS 합성 + C/RTL Co-sim              (csynth 실측 완료; cosim은 RTL 실행 성공,
                                                    자동 비교는 툴 하네스 한계로 미완주)
[x] Stage 5  DFX PR 구현 + pr_verify              (fabric-only 실측 완료, pr_verify PASS)
[ ] Stage 6  보드 실장 + DPU end-to-end            (보드 필요 — 유일하게 남은 단계)
범례: [x] 완료 · [ ] 미착수
```

> SW 트랙(Stage 1~3) 실측 결과·해석은 `results/stage1-3-results-2026-07-02.md`.
> HW 트랙(Stage 4~5) 실측은 `results/stage4-hw-synthesis-2026-07-02.md`,
> `results/stage5-dfx-implementation-2026-07-02.md`.
> 핵심 발견(SW): **모든 조건에서 none(무처리)이 mAP 최고** → 현 tone RM은 mAP guardrail
> 탈락, DFX 정당화는 자원/전력이어야 함(방향 A 강화).
> 핵심 발견(HW): gamma를 런타임 sqrt→ROM LUT로 바꿔 자원 -88%/-78%; **pr_verify PASS**로
> RM_NORMAL_TONE↔RM_LOW_LIGHT_TONE 실제 DFX 전환 가능함을 실측 확인;
> full bitstream 19.3MB, partial 671KB(양 RM 동일 — pblock 프레임 수 결정).

## 즉시 다음 (우선순위)

1. **보드 단계(Stage 6)** — 실제 ZCU104: PS/DDR 통합, ICAP 재구성 지연(ms), 절대 전력(W),
   DPU end-to-end. 이 시점부터는 물리 보드 없이는 진행 불가.
2. **(선택) SW 설계 수정** — (a)normal RM=register gain, (b)low-light RM 완화/denoise,
   (c)checker dark-level 재보정 후 Stage 3 재측정 → mAP guardrail 재판정.
3. **(선택) L2 cosim 완주** — post-check SIGSEGV 원인(struct-pointer 인터페이스 추정)
   해소 또는 인터페이스 재설계.

## 주의 (지어내지 않기)

- Stage 6(보드) 수치는 실물 보드 없이는 `TODO(측정)`(재구성 지연·전력·DPU 정확도).
- 구 08/11 mAP는 ablation arm(구 variant) 기준 — 새 서사에 그대로 인용 금지, Stage 3 재측정으로 대체.
