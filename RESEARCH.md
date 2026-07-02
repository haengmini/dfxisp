# RESEARCH.md — DFXISP 연구 정본

최종 수정: 2026-07-02  
소유자: 이형민  
대상 보드: Zynq UltraScale+ ZCU104 / XCZU7EV  
핵심 논지: **공유 baseline ISP core + 상호 배타적인 mode-specific tone RM**

---

## 0. 이 reset의 목적

이 문서는 현재 HLS C-sim scaffold가 의도한 연구 아키텍처에서 벗어난 것을 확인한 뒤, DFXISP 연구 방향을 다시 정렬하기 위한 정본 문서다.

의도한 설계는 다음과 같다.

```text
mode-specific tone RM slot + shared baseline ISP core

NORMAL:
  RM_NORMAL_TONE = normal gain + normal gamma, or identity bypass

LOW_LIGHT:
  RM_LOW_LIGHT_TONE = 2x2 binning + low-light gain + low-light gamma
```

RM slot은 **상호 배타적(mutually exclusive)** 이다. Normal frame과 low-light frame은 tone/gain/gamma 구현을 둘 다 통과하지 않는다. 공유 baseline ISP core는 선택된 RM 뒤에 오는 공통 경로이며, 비교 기준(reference path)으로 유지한다.

현재 `isppipeline/hls/` 아래 HLS scaffold는 C-sim/golden-vector harness로는 유용하지만, 그 low-light 동작은 최종 의도한 RM 동작이 아니다. 현재 scaffold는 demosaic 이후 RGB8 gain/lift를 수행한다. 따라서 이것은 연구 아키텍처가 아니라 임시 scaffold 또는 ablation baseline으로 취급한다.

---

## 1. 연구 목표

DFXISP는 FPGA Dynamic Function eXchange가 머신비전용 ISP pipeline을 조도 조건에 따라 adaptive하게 만들 수 있는지를 연구한다.

핵심 연구 질문은 다음이다.

> 공유 baseline ISP core에 상호 배타적인 tone RM slot을 결합하고, normal scene에서는 `RM_NORMAL_TONE`, dark scene에서는 `RM_LOW_LIGHT_TONE`으로 전환하면, baseline core 안에 gain/gamma logic을 중복 배치하지 않으면서 low-light 머신비전 robustness를 개선할 수 있는가?

이 질문은 실험적으로 분리해야 할 세 가지 주장으로 이어진다.

1. **알고리즘 주장**  
   Mode-specific tone processing은 gain/gamma를 두 번 적용하지 않고도 normal scene과 dark scene의 image conditioning을 지원할 수 있다. Low-light preprocessing은 binning + low-light gain + low-light gamma를 사용한다.

2. **아키텍처 주장**  
   Gain/gamma를 공유 baseline ISP core에서 제거하고, 상호 배타적인 tone RM인 `RM_NORMAL_TONE`과 `RM_LOW_LIGHT_TONE`으로 분리할 수 있다.

3. **DFX 효율 주장**  
   Register-only 또는 always-on adaptive 설계와 비교했을 때, DFX는 허용 가능한 reconfiguration overhead를 지불하는 대신 static resource pressure 또는 power를 줄일 수 있다.

---

## 2. 정본 아키텍처

### 2.1 상위 block diagram

```text
Input frame
  Bayer / pseudo-RAW / RGB32 fixture
        │
        ▼
Scene checker / mode decision
  - luminance 또는 dark ratio 계산
  - threshold + hysteresis 적용
  - NORMAL 또는 LOW_LIGHT 결정
        │
        ├───────────────────────────────────────────────┐
        │                                               │
        ▼                                               ▼
NORMAL path                                     LOW_LIGHT trigger path
RM_NORMAL_TONE                                  RM_LOW_LIGHT_TONE
  normal gain / gamma                            2x2 binning
  or identity bypass                             low-light gain
                                                  low-light gamma
        │                                               │
        └───────────────────────────────┬───────────────┘
                                        ▼
                              Baseline ISP core
                                BLC
                                AWB / color calibration
                                demosaic or RGB bypass
                                CCM
                                RGB32 pack
                                # gain/gamma 중복 없음
                                        │
                                        ▼
                                  RGB32 output
                                  DPU / detector input
```

### 2.2 동작 규칙

Tone/exposure RM slot은 mode-specific이다. Normal과 low-light는 동일 gain/gamma를 두 번 통과하지 않는다.

```text
Normal lighting:
  checker selects NORMAL
  RM_NORMAL_TONE is active, or identity bypass is used if normal gain/gamma is not needed
  RM_LOW_LIGHT_TONE is inactive
  baseline ISP core consumes the selected tone output
  output is marked NORMAL mode

Dark lighting:
  checker triggers LOW_LIGHT
  controller activates or swaps in RM_LOW_LIGHT_TONE
  RM_NORMAL_TONE is inactive
  RM_LOW_LIGHT_TONE applies binning + gain + gamma before the baseline ISP core
  baseline ISP core consumes the selected RM output
  output is marked LOW_LIGHT mode

Return to bright lighting:
  checker sees recovery condition
  controller switches back to RM_NORMAL_TONE or identity bypass
  RM_LOW_LIGHT_TONE becomes inactive
```

### 2.3 Static region과 RM boundary

권장 partition은 다음과 같다.

```text
Static region:
  - AXI/control wrapper
  - frame metadata handling
  - checker / mode-decision FSM
  - baseline ISP core control
  - DFX/PR controller interface
  - output packer / metadata packer
  - all baseline ISP core blocks common to every mode

Reconfigurable Module candidates:
  RM_NORMAL_TONE:
    - normal gain / normal gamma or identity tone curve
    - active during normal lighting

  RM_LOW_LIGHT_TONE:
    - 2x2 binning
    - low-light gain
    - low-light gamma LUT or piecewise approximation
    - active only after dark-scene trigger
```

이 boundary는 baseline core에서 gain/gamma 중복을 제거한다. Baseline core는 공통/shared 경로로 남고, mode-specific tone/exposure 동작은 상호 배타적인 RM으로 분리된다. Normal lighting에서는 `RM_NORMAL_TONE` 또는 identity bypass를 사용한다. Dark lighting에서는 `RM_LOW_LIGHT_TONE`으로 전환한다. 두 RM은 같은 downstream interface contract를 제공해야 하며, shape이 다르면 명시적인 output metadata를 내보내야 한다.

---

## 3. Baseline ISP core

Baseline ISP core는 선택된 tone RM 삽입 이후의 normal-mode reference path다. 중복 연산을 막기 위해 이 core는 `RM_NORMAL_TONE` 또는 `RM_LOW_LIGHT_TONE`에 속한 gain/gamma를 다시 포함하면 안 된다.

개념적 stage는 다음과 같다.

```text
Input or RM output
  -> black-level correction, BLC
  -> AWB / color calibration only
  -> demosaic or RGB bypass
  -> color correction matrix, CCM
  -> RGB32 pack/output
```

### 3.1 De-duplication rule

각 operation에는 정확히 하나의 owner만 있어야 한다. Gain/gamma는 normal과 low-light 동작 모두에 필요할 수 있지만, baseline core와 RM 양쪽에 중복 배치하면 안 된다. 따라서 gain/gamma는 영구적인 baseline-core stage가 아니라 **mode-specific tone RM**이 된다.

| Operation | Owner | Normal mode | Low-light mode |
|---|---|---|---|
| normal gain / normal gamma | `RM_NORMAL_TONE` or identity bypass | active | inactive |
| 2x2 binning | `RM_LOW_LIGHT_TONE` | inactive | active |
| low-light exposure gain | `RM_LOW_LIGHT_TONE` | inactive | active |
| low-light gamma/tone curve | `RM_LOW_LIGHT_TONE` | inactive | active |
| BLC | baseline ISP core | active | active after selected RM |
| AWB / color calibration | baseline ISP core | active | active after selected RM |
| demosaic / RGB bypass | baseline ISP core | active | active after selected RM |
| CCM | baseline ISP core | active | active after selected RM |
| RGB32 packing | baseline ISP core/output wrapper | active | active |

Reset 이후 기본 구조는 다음이다.

```text
NORMAL:
  input
    -> RM_NORMAL_TONE(gain + gamma) or identity bypass
    -> baseline_isp_core(no gain/gamma duplication)
    -> RGB32

LOW_LIGHT:
  input
    -> RM_LOW_LIGHT_TONE(2x2 binning + gain + gamma)
    -> baseline_isp_core(no gain/gamma duplication)
    -> RGB32
```

이 설계는 normal-mode gain/gamma가 여전히 필요할 수 있다는 사실은 보존하면서, gain/gamma 중복을 피한다.

### 3.2 Baseline의 역할

Baseline은 다음 용도로 사용한다.

1. Normal-scene output.
2. Low-light mode와 비교하기 위한 bright-scene reference.
3. Fixed pipeline correctness를 위한 golden-vector reference.
4. DFX benefit analysis를 위한 resource/timing baseline.
5. RM이 비활성 상태이거나 reconfiguration 중일 때의 fallback path.

### 3.3 Baseline은 안정적으로 유지해야 한다

Low-light RM 실험을 수행하는 동안 baseline path를 반복적으로 바꾸면 안 된다. Baseline과 RM이 동시에 바뀌면 output 차이를 RM 때문인지 baseline 때문인지 attribution할 수 없다.

권장 discipline은 다음이다.

```text
Phase A: lock baseline arithmetic
Phase B: add low-light RM arithmetic
Phase C: add checker/mode controller
Phase D: add DFX/RP mechanics
Phase E: run DPU/mAP evaluation
```

---

## 4. Low-light RM 명세

### 4.1 필수 operation

첫 번째 low-light RM은 다음을 구현해야 한다.

```text
2x2 binning + gain + gamma
```

최소 기능 정의는 다음과 같다.

1. **2x2 binning**
   - 인접 pixel을 결합해 signal strength를 높이고 noise sensitivity를 줄인다.
   - Channel별 후보 formula:

     ```text
     binned = (p00 + p01 + p10 + p11) / 4
     ```

   - Bayer/RAW에서 동작한다면 Bayer semantics를 보존하거나 channel grouping을 명시해야 한다.
   - RGB32에서 동작한다면 channel별 binning을 적용한다.

2. **Gain**
   - Binning 이후 linear gain을 적용한다.
   - 초기 후보값:

     ```text
     gain = 1.25x or 1.5x
     ```

   - Highlight destruction을 막기 위해 clipping 또는 soft-knee policy를 포함해야 한다.

3. **Gamma**
   - Dark-region lift를 위한 nonlinear transform.
   - 초기 후보값:

     ```text
     normal gamma:    γ = 2.2
     low-light gamma: γ = 4.0
     ```

   - 구현은 LUT, piecewise approximation, fixed-point power approximation 중 하나를 사용할 수 있다.
   - HLS/Vivado feasibility 관점에서는 LUT를 우선한다.

### 4.2 RM이 low-light path 앞 또는 내부에서 동작해야 하는 이유

현재 관찰된 scaffold는 normal demosaic와 RAW12-to-RGB8 conversion 이후 gain/lift를 적용한다. 이것만으로는 충분하지 않다.

1. Enhancement 전에 RAW precision이 줄어든다.
2. Binning이 없으므로 SNR이 개선되지 않는다.
3. Gamma가 없으므로 dark-region expansion이 조악하다.
4. Output을 밝게 만들 뿐, 실제 low-light front-end로 동작하지 않는다.

수정된 RM은 binning과 gamma가 의미 있고 측정 가능한 stage에서 동작해야 한다.

### 4.3 Output shape policy

2x2 binning은 자연스럽게 shape을 바꾼다.

```text
Input  H x W
Output H/2 x W/2
```

허용 가능한 정책은 두 가지다.

#### Policy A — Shape-changing RM

```text
LOW_LIGHT output = H/2 x W/2
```

장점:
- Binning semantics가 명확하다.
- Low-light processing 이후 pixel count가 줄어든다.
- Binning operation 증명이 쉽다.

단점:
- DPU integration이 variable shape을 처리해야 한다.
- Golden vector와 metadata에 output width/height가 포함되어야 한다.

#### Policy B — Shape-preserving RM

```text
2x2 binning -> low-light enhancement -> upsample/pad back to H x W
```

장점:
- DPU ABI가 안정적으로 유지된다.
- Frame-to-frame comparison이 쉽다.

단점:
- 추가 logic이 필요하다.
- Resize policy 때문에 binning benefit이 일부 흐려질 수 있다.

현재 권장안:

```text
Milestone 1: implement Policy A explicitly with output metadata.
Milestone 2: add Policy B only if DPU integration requires fixed H x W.
```

---

## 5. Checker와 trigger policy

### 5.1 Checker 역할

Checker는 low-light RM을 활성화해야 하는지 결정한다.

단순히 noisy threshold로 매 frame switch하면 안 된다. Scene-level 또는 window-level stability를 사용해야 한다.

후보 metric:

```text
Y = (R + 2G + B) / 4
```

후보 dark ratio:

```text
dark_ratio = count(Y < dark_pixel_threshold) / frame_pixels
```

후보 transition threshold:

```text
NORMAL -> LOW_LIGHT: dark_ratio > 0.80   # recalibrated 2026-07-02 (was 0.40; see SPEC.md §3.1)
LOW_LIGHT -> NORMAL: dark_ratio < 0.20   # exit/hysteresis stays scheduler-layer (§5.2);
                                         # dfxisp_accel's single-frame AUTO checker only
                                         # implements the enter-side ratio, no exit/hysteresis.
```

### 5.2 Hysteresis requirement

Mode flicker를 피하기 위해 hysteresis를 사용한다.

```text
if mode == NORMAL and dark_ratio > high_threshold for N stable frames:
    trigger LOW_LIGHT

if mode == LOW_LIGHT and dark_ratio < low_threshold for N stable frames:
    return NORMAL
```

최소 metadata log:

```text
frame_id
scene_avg or dark_ratio
selected_mode
trigger_event
reconfig_state
output_width
output_height
```

### 5.3 RM selection semantics

문서 수준 요구사항은 다음이다.

```text
NORMAL uses RM_NORMAL_TONE or identity bypass.
LOW_LIGHT uses RM_LOW_LIGHT_TONE.
The two tone RMs are mutually exclusive.
The shared baseline ISP core never applies a second gain/gamma pass.
```

구현은 단계별로 다음과 같이 표현할 수 있다.

1. C-sim stage: `RM_NORMAL_TONE`, `RM_LOW_LIGHT_TONE`, identity 중 정확히 하나의 tone function을 선택한다.
2. RTL stage: mode select가 정확히 하나의 RM slot implementation으로만 route한다.
3. DFX stage: PR controller가 RM slot을 normal-tone과 low-light-tone 구현 사이에서 swap하거나, normal resident module로 identity를 사용한다.
4. Board stage: 실제 reconfiguration latency와 dropped-frame behavior를 측정한다.

---

## 6. 수정된 구현 목표

### 6.1 현재 scaffold의 문제

현재 HLS scaffold를 단순화하면 다음과 같다.

```text
raw_bayer
  -> normal_pixel_kernel
       3x3 Bayer window
       GRBG demosaic
       RAW12 -> RGB8
  -> low_light_reconfigurable_module
       RGB8 gain/lift only
```

이것은 목표 low-light RM이 아니다.

다음 용도로만 유용하다.

1. C-sim harness proof.
2. Golden-vector flow proof.
3. Temporary post-RGB enhancement ablation.

### 6.2 목표 C-sim structure

목표 HLS C-sim은 다음 구조가 되어야 한다.

```text
raw/input frame
  -> checker_select_mode
  -> if NORMAL:
         RM_NORMAL_TONE(input) or identity_bypass(input)
         baseline_isp_core(normal_tone_output)
     if LOW_LIGHT:
         RM_LOW_LIGHT_TONE(input)  # 2x2 binning + gain + gamma
         baseline_isp_core(low_light_tone_output)
  -> output + metadata
```

이 순서가 현재 project default다. 단일 mode-specific tone RM slot이 공유 baseline ISP core로 들어간다. 시스템은 frame/segment마다 정확히 하나의 tone path만 선택해야 하며, gain/gamma 중복 적용을 피해야 한다.

---

## 7. 실험 arm

연구 contribution을 증명하려면 최소 세 arm을 비교해야 한다.

### Arm 1 — Static baseline core + normal tone

```text
RM_NORMAL_TONE or identity
shared baseline ISP core
no low-light RM
no DFX
```

목적:
- 고정 normal-scene reference.
- Normal-scene correctness.
- Shared ISP core plus normal tone의 resource/timing baseline.

### Arm 2 — Register-only adaptive

```text
same bitstream
mode selects normal-tone vs low-light-tone parameters/functions
no PR/DFX
```

목적:
- DFX 없이 adaptation benefit을 보인다.
- 진짜 DFX value를 분리하기 위해 필요한 baseline.
- Partial reconfiguration을 도입하기 전에 de-duplication을 확인한다.

### Arm 3 — DFX adaptive tone RM slot

```text
shared baseline ISP core remains static
DFX/RP swaps the tone RM slot:
  RM_NORMAL_TONE       = normal gain + gamma or identity
  RM_LOW_LIGHT_TONE    = 2x2 binning + low-light gain + low-light gamma
```

목적:
- Main research claim.
- Arm 2와 비교해 resource, timing, power, reconfiguration overhead를 평가한다.

---

## 8. 검증 계획

### 8.1 Golden model first

HLS/RTL을 바꾸기 전에 Python golden behavior를 먼저 정의한다.

필수 golden output:

```text
bright_normal
  expected mode: NORMAL
  expected selected RM: RM_NORMAL_TONE or identity
  expected inactive RM: RM_LOW_LIGHT_TONE
  expected output shape: H x W

dark_lowlight
  expected mode: LOW_LIGHT
  expected selected RM: RM_LOW_LIGHT_TONE
  expected inactive RM: RM_NORMAL_TONE
  expected output shape: H/2 x W/2 if shape-changing policy is selected

bright_recovery
  expected mode: NORMAL after hysteresis
  expected selected RM: RM_NORMAL_TONE or identity
  expected inactive RM: RM_LOW_LIGHT_TONE
```

### 8.2 HLS C-sim gates

최소 C-sim pass criteria:

1. Golden vector generation이 성공한다.
2. HLS C++ output이 Python golden output과 bit-exact하게 일치한다.
3. Bright frame은 `RM_NORMAL_TONE` 또는 identity를 선택하고 `RM_LOW_LIGHT_TONE`을 통과하지 않는다.
4. Dark frame은 `RM_LOW_LIGHT_TONE`을 선택하고 `RM_NORMAL_TONE`을 통과하지 않는다.
5. 어떤 frame도 normal gain/gamma와 low-light gain/gamma를 둘 다 적용하지 않는다.
6. Output metadata가 expected mode, selected RM, shape과 일치한다.
7. Boundary size를 test한다: even dimensions, odd dimensions, small frames.

### 8.3 RTL / Vivado gates

C-sim pass 이후:

1. C-synthesis report를 생성한다.
2. Shared baseline core, `RM_NORMAL_TONE`, `RM_LOW_LIGHT_TONE`의 II/latency를 보고한다.
3. Resource table에는 static region과 각 RM의 LUT, FF, BRAM, DSP를 포함한다.
4. Timing report에는 WNS/TNS와 clock target을 포함한다.
5. Mode-specific tone RM slot에 대한 DFX partition floorplan을 정의한다.
6. RM slot variants에 대해 `pr_verify` 또는 equivalent DFX verification을 통과한다.
7. 각 RM variant의 partial bitstream size를 기록한다.
8. Reconfiguration latency를 측정하거나 ICAP bandwidth에서 추정한다.

---

## 9. Metrics

### 9.1 Image/algorithm metrics

각 fixture/case마다 다음을 기록한다.

```text
mode selected
selected RM (`RM_NORMAL_TONE`, `RM_LOW_LIGHT_TONE`, or identity)
inactive RM
input size
output size
Y mean/std/min/max
saturation percentage
dark-ratio before/after
gain/gamma duplication flag, expected false
optional PSNR/SSIM against reference
```

### 9.2 Machine-vision metrics

Detector integration에서는 다음을 기록한다.

```text
mAP@50 overall
per-class AP
bright segment mAP
low-light segment mAP
transition segment mAP
mode mismatch mAP
```

### 9.3 Hardware metrics

```text
LUT / FF / BRAM / DSP
clock target and achieved Fmax
latency per frame
II
partial bitstream size
reconfiguration latency
frame drops during transition
estimated or measured power
```

---

## 10. Dataset과 scenario

### 10.1 Synthetic C-sim fixtures

먼저 작은 deterministic fixture를 사용한다.

```text
NORMAL x3 -> LOW_LIGHT x3 -> NORMAL x1
```

목적:
- Mode stability 검증.
- Low-light trigger 검증.
- Recovery 검증.
- Bit-exact debugging을 쉽게 유지.

### 10.2 Real/pseudo-real datasets

사용 dataset:

```text
COCO_5000        normal/bright condition
ExDark_5000      dark condition
COCO_5000_raw    pseudo-RAW normal
ExDark_5000_raw  pseudo-RAW dark
```

주의:
- JPEG/PNG dataset은 이미 ISP 처리된 데이터다.
- 이미 처리된 image에 RAW-style ISP를 적용하면 double-processing artifact가 생길 수 있다.
- 더 강한 주장은 최종적으로 pseudo-RAW 또는 real Bayer sensor data를 사용해야 한다.

---

## 11. Archived documents

이전 문서들은 ambiguity를 줄이고 active source of truth를 작게 유지하기 위해 archive했다.

Archive path:

```text
archive/docs-reorg-2026-07-01/
```

Archived material에는 다음이 포함된다.

```text
root historical worklogs and plans
old docs/ Architecture, Research_Roadmap, HW_SW_Interface, Analysis_Report
old docs/reference reports and tutorials
paper/ thesis drafts and figure/reference plans
```

이 파일들은 삭제된 것이 아니다. 역사적 참고 자료일 뿐이다. 그 안의 claim을 재사용하려면 현재 terminology에 맞춰 이 `RESEARCH.md`로 옮겨야 한다.

---

## 12. 즉시 수행할 다음 task

### Task 1 — Shared core + mode-specific tone RM 중심으로 HLS architecture 재작성

다음 방향으로 구현 또는 refactor한다.

```text
rm_normal_tone_gain_gamma_or_identity()
rm_low_light_tone_binning_gain_gamma()
baseline_isp_core_no_gain_gamma_duplication()
checker_select_mode()
dfxisp_accel() controller with selected_rm metadata
```

### Task 2 — Python golden model 업데이트

Golden model은 다음을 포함해야 한다.

```text
normal tone RM path or identity
low-light tone RM path
shared baseline ISP core path
shape policy
mode metadata
selected RM metadata
gain/gamma duplication flag
```

### Task 3 — Fixture 추가

필수 fixture:

```text
bright_normal_grid
low_light_dark_grid
mixed_dark_grid
threshold_boundary
bright_recovery_after_lowlight
odd_dimension_lowlight
```

### Task 4 — Report 업데이트

Report는 다음을 명시해야 한다.

```text
Shared baseline core PASS/FAIL
RM_NORMAL_TONE or identity PASS/FAIL
RM_LOW_LIGHT_TONE PASS/FAIL
Mutually exclusive RM selection: PASS/FAIL
No duplicate gain/gamma: PASS/FAIL
Output shape policy: H/2 x W/2 or H x W restored
```

### Task 5 — Ablation 보존

현재 post-RGB8 gain/lift는 ablation으로만 유지한다.

```text
Ablation: post_rgb_gain_lift
Status: not the main low-light RM
Purpose: compare against true binning+gain+gamma RM
```

---

## 13. 현재 reset의 non-goals

수정된 C-sim/golden structure가 pass하기 전까지 다음에는 시간을 쓰지 않는다.

1. Full board bring-up.
2. DPU runtime integration.
3. Real partial bitstream swapping.
4. Power measurement.
5. Large mAP sweep.
6. Thesis prose polish.

즉시 우선순위는 architectural correctness다.

```text
mode-specific tone RM slot + shared baseline ISP core
RM_NORMAL_TONE: normal gain + gamma, or identity
RM_LOW_LIGHT_TONE: 2x2 binning + low-light gain + low-light gamma
selected RM is mutually exclusive per frame/segment
baseline ISP core does not duplicate gain/gamma
```

---

## 14. Reset acceptance criteria

Reset은 다음 조건을 만족하면 완료로 본다.

1. `README.md`와 `RESEARCH.md`가 유일한 active top-level research documents다.
2. Historical docs는 삭제하지 않고 archive한다.
3. `RESEARCH.md`가 shared baseline ISP core + mode-specific tone RM architecture를 명확히 정의한다.
4. Current scaffold mismatch가 문서화되어 있다.
5. Next implementation target이 모호하지 않다.
6. Future reports는 다음을 구분한다.
   - shared baseline core path
   - `RM_NORMAL_TONE` or identity path
   - `RM_LOW_LIGHT_TONE` path
   - post-RGB gain/lift ablation
   - register-only adaptive baseline
   - DFX adaptive RM-slot variant
