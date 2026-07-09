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

### 1.0 논지 (thesis) — 왜 이 연구를 하는가

컴퓨터 비전(CV) 검출기는 **조도 조건에 따라 서로 다른 이미지 전처리**를
요구한다. 하나의 static ISP pipeline으로 밝은 장면과 어두운 장면을 모두
처리하면, 어느 한쪽(특히 저조도)에서 CV 성능·효율이 떨어진다. 따라서
**CV를 위한 ISP는 저조도에 특화된 vision processor 경로를 별도로 갖고,
상황에 맞는 모듈로 전환**해야 한다는 것이 본 연구의 논지다.

이 논지를 **두 개의 최종 목표**로 나눈다.

- **목표 1 (필요성 — 저조도 특화 모듈):** 저조도 환경에서 static/일반
  ISP 경로는 CV(검출기)에 대한 성능이 떨어진다. **저조도에 특화된 모듈이
  더 적합**하며, 각 모듈은 자기 조건의 데이터셋에서 상대 모듈보다 높은
  CV 성능을 낸다(§7 arm 비교, §10 데이터셋).
- **목표 2 (전환 — DFX 적응):** 조건이 바뀌므로 어느 한 모듈을 고정으로
  쓸 수 없다 — **상황에 맞춰 모듈을 전환(adaptive)**해야 하고, 이 전환을
  FPGA Dynamic Function eXchange(DFX)로 구현하면 static/always-on 설계
  대비 **자원·전력 효율**까지 개선한다.

**핵심 연구 질문:** 공유 baseline ISP core에 상호 배타적인 tone RM slot을
결합해 normal scene에서는 `RM_NORMAL_TONE`, dark scene에서는
`RM_LOW_LIGHT_TONE`으로 (체커가 판단해) 전환하면, gain/gamma를 core에
중복 배치하지 않으면서 (목표 1) 저조도 CV 성능을 살리고 (목표 2) DFX로
효율을 얻을 수 있는가?

### 1.1 증명 전략 — 필요성 → 전환, SW 먼저 → HW

논증 순서는 다음과 같다.

1. **필요성(목표 1):** 단일 모듈이 **각각 자기 조건의 데이터셋에서 최고**임을
   보인다 — normal 모듈은 밝은 조도 RAW(§10: PASCAL RAW)에서, low-light
   모듈은 저조도 RAW(§10: LOD RAW)에서. 한 모듈이 두 조건을 모두 이기지
   못하므로 **고정 단일 모듈은 부적합 → 전환이 필요**하다는 결론이 나온다.
2. **전환(목표 2):** 따라서 체커가 조건을 판단해 모듈을 고르는 adaptive
   경로가 두 조건이 섞인 스트림에서 **최적 단일 static을 상회**함을 보인다.
3. **SW → HW 순서:** 위 두 주장을 먼저 **SW(golden/파이썬 mAP)로 확립**한
   뒤, **HW(HLS 합성 → DFX 부분재구성 → 보드)로 이식**한다. HW 트랙의
   고유 기여는 **효율(자원/전력)** — 특히 보드(Stage 6)에서 DFX가 always-on
   대비 static 자원·전력을 줄인다는 것을 실측한다.

### 1.2 비교 범위 (arm) — `none`은 제외

CV 성능 비교의 arm은 **`normal` / `lowlight` / `adaptive`** 세 가지다.
**demosaic만 하고 baseline core(BLC/AWB/CCM)·톤을 전혀 거치지 않는
`none`(무처리) arm은 본 연구의 비교 대상에서 제외**한다 — `none`은 색
보정된 배포 가능한 ISP 출력이 아니라(AWB/CCM 미적용, 색편향 잔존) 별개
계열의 문제이기 때문이다. 이후 모든 arm 비교·결론은 이 세 arm 안에서만
이루어진다.

### 1.3 실험적으로 분리하는 세 주장 (위 목표에 매핑)

1. **알고리즘 주장 (목표 1의 성능 근거)**  
   Mode-specific tone processing은 gain/gamma를 두 번 적용하지 않고도
   normal/dark 각 조건의 image conditioning을 지원한다. **Low-light 모듈은
   binning + low-light gain + low-light gamma + 완화된 black-level**을
   쓰며, 각 조건 데이터셋에서 상대 모듈 대비 CV 성능 우위를 낸다(구체
   기술·기대이득·실측이득은 `results/lowlight-module-techniques-2026-07-10.md`).

2. **아키텍처 주장 (목표 1·2의 구조 근거)**  
   Gain/gamma를 공유 baseline ISP core에서 제거하고, 상호 배타적인 tone RM
   `RM_NORMAL_TONE`/`RM_LOW_LIGHT_TONE`으로 분리해 체커가 하나만 선택한다.

3. **DFX 효율 주장 (목표 2의 효율 근거)**  
   Register-only 또는 always-on adaptive 설계와 비교했을 때, DFX는 허용
   가능한 reconfiguration overhead를 지불하는 대신 static resource pressure
   또는 power를 줄인다(보드 실측은 Stage 6).

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

### 10.2 평가 데이터셋 — 조건별 real-RAW 쌍 (정본)

**§1.1 증명 전략(단일 모듈이 각각 자기 조건에서 최고 → 전환 필요)을
그대로 실험으로 옮기려면, 밝은 조도와 저조도 각각의 real-RAW 데이터셋
쌍이 필요하다.** 정본 평가 쌍은 다음과 같다.

```text
밝은 조도(bright):  PASCAL RAW dataset   -> normal 모듈이 최고를 낼 조건
저조도(low-light):  LOD RAW dataset      -> low-light 모듈이 최고를 낼 조건
```

- 둘 다 **real Bayer sensor RAW** 기반 검출 데이터셋이다 — pseudo-RAW
  (sRGB 역감마 합성)와 달리 실제 Poisson-Gaussian 센서 노이즈를 담고
  있어, low-light 모듈의 핵심 연산인 **binning(광량 적분/SNR 회복)의
  정당성**을 비로소 제대로 검증할 수 있다(pseudo-RAW에는 binning이 회수할
  실제 노이즈가 없다 — `results/principled-v3-refinement-2026-07-05.md` §3.4).
- **필요성(목표 1) 검증:** PASCAL RAW에서 `normal` arm이, LOD RAW에서
  `lowlight` arm이 각각 상대 arm보다 높은 mAP를 내는지(교차 우위)를 본다.
- **전환(목표 2) 검증:** 두 데이터셋을 섞은(또는 조건 라벨이 붙은) 스트림
  에서 `adaptive`(체커 라우팅)가 최적 단일 static arm을 상회하는지를 본다.

**이력(superseded proxy):** 초기 실험은 COCO/ExDark를 JPEG→pseudo-RAW로
역감마해 사용했고(§Stage 3 R1~R4), 실센서 검증은 SonyNOD(RAW-NOD, .ARW)로
수행했다(R3b/R4). 이 결과들은 정성적 근거로 유효하나, **정본 평가는 위
PASCAL RAW / LOD RAW 쌍으로 재수립**한다.

주의:
- JPEG/PNG dataset은 이미 ISP 처리된 데이터라 RAW-style ISP를 다시 적용하면
  double-processing artifact가 생긴다 — pseudo-RAW/real-RAW를 써야 하는 이유.
- arm 비교는 `normal`/`lowlight`/`adaptive` 세 가지로 한정한다(§1.2, `none` 제외).

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
