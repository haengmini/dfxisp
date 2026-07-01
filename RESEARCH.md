# RESEARCH.md — DFXISP research source of truth

Last updated: 2026-07-01  
Owner: 이형민  
Target: Zynq UltraScale+ ZCU104 / XCZU7EV  
Main thesis: **shared baseline ISP core + mutually exclusive mode-specific tone RMs**

---

## 0. Purpose of this reset

This document resets the DFXISP research direction after finding that the current HLS C-sim scaffold drifted away from the intended architecture.

The intended design is:

```text
mode-specific tone RM slot + shared baseline ISP core

NORMAL:
  RM_NORMAL_TONE = normal gain + normal gamma, or identity bypass

LOW_LIGHT:
  RM_LOW_LIGHT_TONE = 2x2 binning + low-light gain + low-light gamma
```

The RM slot is **mutually exclusive**: normal frames and low-light frames do not pass through both tone/gain/gamma implementations. The shared baseline ISP core remains the default common path after the selected RM and is the reference for comparison.

The current HLS scaffold under `isppipeline/hls/` is useful as a C-sim/golden-vector harness, but its low-light behavior is not the intended final RM behavior. It currently performs post-demosaic RGB8 gain/lift. That is now treated as a temporary scaffold or ablation baseline, not the research architecture.

---

## 1. Research objective

DFXISP studies how FPGA Dynamic Function eXchange can make an ISP pipeline adaptive for machine vision.

The core research question is:

> Can a shared baseline ISP core be paired with a mutually exclusive tone RM slot, where normal scenes use `RM_NORMAL_TONE` and dark scenes switch to `RM_LOW_LIGHT_TONE`, improving low-light machine-vision robustness without duplicating gain/gamma logic in the baseline core?

This leads to three claims that must be separated experimentally:

1. **Algorithmic claim**  
   Mode-specific tone processing can support both normal-scene and dark-scene image conditioning without applying gain/gamma twice. Low-light preprocessing uses binning + low-light gain + low-light gamma.

2. **Architecture claim**  
   Gain/gamma can be removed from the shared baseline ISP core and isolated into mutually exclusive tone RMs: `RM_NORMAL_TONE` and `RM_LOW_LIGHT_TONE`.

3. **DFX efficiency claim**  
   Compared with a register-only or always-on adaptive design, DFX can reduce static resource pressure or power while paying an acceptable reconfiguration overhead.

---

## 2. Canonical architecture

### 2.1 High-level block diagram

```text
Input frame
  Bayer / pseudo-RAW / RGB32 fixture
        │
        ▼
Scene checker / mode decision
  - compute luminance or dark ratio
  - apply threshold + hysteresis
  - decide NORMAL or LOW_LIGHT
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
                                # no duplicate gain/gamma here
                                        │
                                        ▼
                                  RGB32 output
                                  DPU / detector input
```

### 2.2 Operational rule

The tone/exposure RM slot is mode-specific. Normal and low-light do not run through the same gain/gamma twice.

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

### 2.3 Static region vs RM boundary

Recommended partition:

```text
Static region:
  - AXI/control wrapper
  - frame metadata handling
  - checker / mode-decision FSM
  - baseline ISP core control
  - DFX/PR controller interface
  - output packer / metadata packer
  - baseline ISP core blocks that are common to all modes

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

This boundary keeps duplicate gain/gamma out of the baseline core. The baseline core remains common/shared, while mode-specific tone/exposure behavior is isolated into mutually exclusive RMs. In normal lighting the system uses `RM_NORMAL_TONE` or an identity bypass. In dark lighting it switches to `RM_LOW_LIGHT_TONE`. The two RMs must expose the same downstream interface contract or must emit explicit output metadata if their shapes differ.

---

## 3. Baseline ISP core

The baseline ISP core is the normal-mode reference path after selected tone RM insertion. To prevent duplicated arithmetic, this core must not contain gain/gamma that already belongs to `RM_NORMAL_TONE` or `RM_LOW_LIGHT_TONE`.

Conceptual stages:

```text
Input or RM output
  -> black-level correction, BLC
  -> AWB / color calibration only
  -> demosaic or RGB bypass
  -> color correction matrix, CCM
  -> RGB32 pack/output
```

### 3.1 De-duplication rule

There must be exactly one owner for each operation. Gain/gamma are needed in both normal and low-light operation, but they should not be duplicated in both the baseline core and an RM. Therefore gain/gamma become **mode-specific tone RMs** rather than permanent baseline-core stages.

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

Default for the reset:

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

This design avoids duplicate gain/gamma while preserving the fact that normal-mode gain/gamma may still be required.

### 3.2 Role of baseline

The baseline is used for:

1. Normal-scene output.
2. Bright-scene comparison against low-light mode.
3. Golden-vector reference for fixed pipeline correctness.
4. Resource/timing baseline for DFX benefit analysis.
5. Fallback path when the RM is inactive or reconfiguration is in progress.

### 3.2 Baseline must remain stable

The baseline path should not be repeatedly modified while low-light RM experiments are being performed. If baseline and RM change simultaneously, it becomes impossible to attribute output differences to the RM.

Recommended discipline:

```text
Phase A: lock baseline arithmetic
Phase B: add low-light RM arithmetic
Phase C: add checker/mode controller
Phase D: add DFX/RP mechanics
Phase E: run DPU/mAP evaluation
```

---

## 4. Low-light RM specification

### 4.1 Required operations

The first low-light RM must implement:

```text
2x2 binning + gain + gamma
```

Minimum functional definition:

1. **2x2 binning**
   - Combine neighboring pixels to improve signal strength / reduce noise sensitivity.
   - Candidate formula per channel:

     ```text
     binned = (p00 + p01 + p10 + p11) / 4
     ```

   - If operating on Bayer/RAW, preserve Bayer semantics or explicitly define channel grouping.
   - If operating on RGB32, apply per-channel binning.

2. **Gain**
   - Linear gain applied after binning.
   - Candidate initial value:

     ```text
     gain = 1.25x or 1.5x
     ```

   - Must include clipping or soft-knee policy to prevent highlight destruction.

3. **Gamma**
   - Nonlinear dark-region lift.
   - Candidate initial values:

     ```text
     normal gamma:    γ = 2.2
     low-light gamma: γ = 4.0
     ```

   - Implementation may use LUT, piecewise approximation, or fixed-point power approximation.
   - LUT is preferred for HLS/Vivado feasibility.

### 4.2 Why RM must operate before or inside the low-light path

The currently observed scaffold applies gain/lift after normal demosaic and RAW12-to-RGB8 conversion. That is not sufficient because:

1. RAW precision is reduced before enhancement.
2. Binning is absent, so SNR does not improve.
3. Gamma is absent, so dark-region expansion is crude.
4. It brightens output but does not act as a real low-light front-end.

The corrected RM should operate at a stage where binning and gamma are meaningful and measurable.

### 4.3 Output shape policy

2x2 binning naturally changes shape:

```text
Input  H x W
Output H/2 x W/2
```

There are two allowed policies:

#### Policy A — Shape-changing RM

```text
LOW_LIGHT output = H/2 x W/2
```

Pros:
- Clean binning semantics.
- Lower pixel count after low-light processing.
- Easier to prove binning operation.

Cons:
- DPU integration must handle variable shape.
- Golden vectors and metadata must include output width/height.

#### Policy B — Shape-preserving RM

```text
2x2 binning -> low-light enhancement -> upsample/pad back to H x W
```

Pros:
- DPU ABI stays stable.
- Easier frame-to-frame comparison.

Cons:
- Adds extra logic.
- Binning benefit may be partially blurred by resize policy.

Current recommendation:

```text
Milestone 1: implement Policy A explicitly with output metadata.
Milestone 2: add Policy B only if DPU integration requires fixed H x W.
```

---

## 5. Checker and trigger policy

### 5.1 Checker role

The checker decides whether the low-light RM should be active.

It should not simply switch every frame based on a noisy threshold. It must use scene-level or window-level stability.

Candidate metric:

```text
Y = (R + 2G + B) / 4
```

Candidate dark ratio:

```text
dark_ratio = count(Y < dark_pixel_threshold) / frame_pixels
```

Candidate transition thresholds:

```text
NORMAL -> LOW_LIGHT: dark_ratio > 0.40
LOW_LIGHT -> NORMAL: dark_ratio < 0.20
```

### 5.2 Hysteresis requirement

Use hysteresis to avoid mode flicker.

```text
if mode == NORMAL and dark_ratio > high_threshold for N stable frames:
    trigger LOW_LIGHT

if mode == LOW_LIGHT and dark_ratio < low_threshold for N stable frames:
    return NORMAL
```

Minimum metadata to log:

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

The document-level requirement is:

```text
NORMAL uses RM_NORMAL_TONE or identity bypass.
LOW_LIGHT uses RM_LOW_LIGHT_TONE.
The two tone RMs are mutually exclusive.
The shared baseline ISP core never applies a second gain/gamma pass.
```

Implementation can represent this in stages:

1. C-sim stage: select exactly one tone function from `RM_NORMAL_TONE`, `RM_LOW_LIGHT_TONE`, or identity.
2. RTL stage: mode select routes through exactly one RM slot implementation.
3. DFX stage: PR controller swaps the RM slot between normal-tone and low-light-tone implementations, or uses identity as the normal resident module.
4. Board stage: measure actual reconfiguration latency and dropped-frame behavior.

---

## 6. Corrected implementation target

### 6.1 Current scaffold problem

Current HLS scaffold, simplified:

```text
raw_bayer
  -> normal_pixel_kernel
       3x3 Bayer window
       GRBG demosaic
       RAW12 -> RGB8
  -> low_light_reconfigurable_module
       RGB8 gain/lift only
```

This is not the target low-light RM.

It is useful only as:

1. C-sim harness proof.
2. Golden-vector flow proof.
3. Temporary post-RGB enhancement ablation.

### 6.2 Target C-sim structure

Target HLS C-sim should become:

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

This ordering is now the project default: a single mode-specific tone RM slot feeds the shared baseline ISP core. The system must select exactly one tone path per frame/segment to avoid duplicated gain/gamma.

---

## 7. Experimental arms

To prove the research contribution, compare at least three arms.

### Arm 1 — Static baseline core + normal tone

```text
RM_NORMAL_TONE or identity
shared baseline ISP core
no low-light RM
no DFX
```

Purpose:
- Fixed normal-scene reference.
- Normal-scene correctness.
- Resource/timing baseline for shared ISP core plus normal tone.

### Arm 2 — Register-only adaptive

```text
same bitstream
mode selects normal-tone vs low-light-tone parameters/functions
no PR/DFX
```

Purpose:
- Shows benefit of adaptation without DFX.
- Necessary to isolate the true DFX value.
- Confirms de-duplication before introducing partial reconfiguration.

### Arm 3 — DFX adaptive tone RM slot

```text
shared baseline ISP core remains static
DFX/RP swaps the tone RM slot:
  RM_NORMAL_TONE       = normal gain + gamma or identity
  RM_LOW_LIGHT_TONE    = 2x2 binning + low-light gain + low-light gamma
```

Purpose:
- Main research claim.
- Compare resource, timing, power, and reconfiguration overhead against Arm 2.

---

## 8. Verification plan

### 8.1 Golden model first

Before changing HLS/RTL, define Python golden behavior.

Required golden outputs:

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

Minimum C-sim pass criteria:

1. Golden vector generation succeeds.
2. HLS C++ output equals Python golden output bit-exactly.
3. Bright frames select `RM_NORMAL_TONE` or identity and do not route through `RM_LOW_LIGHT_TONE`.
4. Dark frames select `RM_LOW_LIGHT_TONE` and do not route through `RM_NORMAL_TONE`.
5. No frame applies both normal gain/gamma and low-light gain/gamma.
6. Output metadata matches expected mode, selected RM, and shape.
7. Boundary sizes are tested: even dimensions, odd dimensions, small frames.

### 8.3 RTL / Vivado gates

After C-sim passes:

1. C-synthesis report generated.
2. II/latency reported for shared baseline core, `RM_NORMAL_TONE`, and `RM_LOW_LIGHT_TONE`.
3. Resource table includes LUT, FF, BRAM, DSP for static region and each RM.
4. Timing report includes WNS/TNS and clock target.
5. DFX partition floorplan is defined for the mode-specific tone RM slot.
6. `pr_verify` or equivalent DFX verification passes for the RM slot variants.
7. Partial bitstream size is recorded for each RM variant.
8. Reconfiguration latency is measured or estimated from ICAP bandwidth.

---

## 9. Metrics

### 9.1 Image/algorithm metrics

For each fixture/case:

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

For detector integration:

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

## 10. Datasets and scenarios

### 10.1 Synthetic C-sim fixtures

Use small deterministic fixtures first:

```text
NORMAL x3 -> LOW_LIGHT x3 -> NORMAL x1
```

Purpose:
- Verify mode stability.
- Verify low-light trigger.
- Verify recovery.
- Keep bit-exact debugging easy.

### 10.2 Real/pseudo-real datasets

Use:

```text
COCO_5000        normal/bright condition
ExDark_5000      dark condition
COCO_5000_raw    pseudo-RAW normal
ExDark_5000_raw  pseudo-RAW dark
```

Caution:
- JPEG/PNG datasets are already ISP-processed.
- Applying a RAW-style ISP to already processed images can cause double-processing artifacts.
- The stronger claim should eventually use pseudo-RAW or real Bayer sensor data.

---

## 11. Archived documents

Previous documents were archived to reduce ambiguity and keep the active source of truth small.

Archive path:

```text
archive/docs-reorg-2026-07-01/
```

Archived material includes:

```text
root historical worklogs and plans
old docs/ Architecture, Research_Roadmap, HW_SW_Interface, Analysis_Report
old docs/reference reports and tutorials
paper/ thesis drafts and figure/reference plans
```

These files are not deleted. They are historical references only. If a claim from them is reused, it should be copied into this `RESEARCH.md` in current terminology.

---

## 12. Immediate next tasks

### Task 1 — Rewrite HLS architecture around shared core + mode-specific tone RMs

Implement or refactor toward:

```text
rm_normal_tone_gain_gamma_or_identity()
rm_low_light_tone_binning_gain_gamma()
baseline_isp_core_no_gain_gamma_duplication()
checker_select_mode()
dfxisp_accel() controller with selected_rm metadata
```

### Task 2 — Update Python golden model

Golden model must include:

```text
normal tone RM path or identity
low-light tone RM path
shared baseline ISP core path
shape policy
mode metadata
selected RM metadata
gain/gamma duplication flag
```

### Task 3 — Add fixtures

Required fixtures:

```text
bright_normal_grid
low_light_dark_grid
mixed_dark_grid
threshold_boundary
bright_recovery_after_lowlight
odd_dimension_lowlight
```

### Task 4 — Update reports

Report should explicitly say:

```text
Shared baseline core PASS/FAIL
RM_NORMAL_TONE or identity PASS/FAIL
RM_LOW_LIGHT_TONE PASS/FAIL
Mutually exclusive RM selection: PASS/FAIL
No duplicate gain/gamma: PASS/FAIL
Output shape policy: H/2 x W/2 or H x W restored
```

### Task 5 — Preserve ablations

Keep current post-RGB8 gain/lift as an ablation only:

```text
Ablation: post_rgb_gain_lift
Status: not the main low-light RM
Purpose: compare against true binning+gain+gamma RM
```

---

## 13. Non-goals for the current reset

Do not spend time on these until the corrected C-sim/golden structure passes:

1. Full board bring-up.
2. DPU runtime integration.
3. Real partial bitstream swapping.
4. Power measurement.
5. Large mAP sweep.
6. Thesis prose polish.

The immediate priority is architectural correctness:

```text
mode-specific tone RM slot + shared baseline ISP core
RM_NORMAL_TONE: normal gain + gamma, or identity
RM_LOW_LIGHT_TONE: 2x2 binning + low-light gain + low-light gamma
selected RM is mutually exclusive per frame/segment
baseline ISP core does not duplicate gain/gamma
```

---

## 14. Acceptance criteria for the reset

The reset is complete when:

1. `README.md` and `RESEARCH.md` are the only active top-level research documents.
2. Historical docs are archived, not deleted.
3. `RESEARCH.md` clearly defines shared baseline ISP core + mode-specific tone RM architecture.
4. Current scaffold mismatch is documented.
5. Next implementation target is unambiguous.
6. Future reports distinguish between:
   - shared baseline core path
   - `RM_NORMAL_TONE` or identity path
   - `RM_LOW_LIGHT_TONE` path
   - post-RGB gain/lift ablation
   - register-only adaptive baseline
   - DFX adaptive RM-slot variant
