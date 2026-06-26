# Ponytail Review — DFXISP HLS C-Sim Scenario

Ponytail 관점은 “큰 시스템을 먼저 만들지 말고, 가장 작은 재현 가능한 검증 루프를 먼저 고정한다”입니다.

## Verdict

현재 `isppipeline/hls/` 변경은 Ponytail 관점에서 적절합니다.

- 새 dependency 없음
- stdlib Python + g++ + make만 사용
- Vitis/Vivado 없는 환경에서도 C-Sim 재현 가능
- DFX/Vivado 수치를 만들어내지 않고, 가능한 검증만 명확히 제한
- 작은 grid synthetic frames로 output correctness를 먼저 고정

## Good

### 1. Smallest useful loop

현재 루프는 아래만 수행합니다.

```text
Python golden vector generation
→ local g++ C-Sim
→ bit-exact compare
→ Markdown report
```

이것은 Vitis/Vivado/board bring-up 전에 필요한 최소 검증 단위입니다.

### 2. No invented hardware metrics

현재 환경에 `vitis_hls`가 없으므로 다음 값은 생성하지 않습니다.

- LUT / FF / BRAM / DSP
- Latency / II
- WNS / Fmax
- cosim 결과
- DFX partial bitstream size
- power estimate

이 제한은 연구 신뢰성 측면에서 중요합니다.

### 3. Scenario-first but not overbuilt

사용자가 요구한 흐름:

```text
NORMAL x3 → LOW_LIGHT x3 → NORMAL x1
```

을 C-Sim vector 순서로 반영했습니다. 아직 실제 PR controller integration이 아니라 **path correctness fixture**로 취급합니다. 이 구분이 맞습니다.

### 4. Test images are understandable

검정색 단일 패치가 아니라 grid illumination frame을 써서 “어두운 조도”와 “검정색 이미지”가 구분됩니다.

## Risks / Watch-outs

### 1. C-Sim sequence is not DFX transition proof

현재 C-Sim은 frame sequence를 검증하지만, 실제 PR/DFX transition, frame drain, icap latency, frame drop을 측정하지 않습니다.

따라서 보고서 표현은 다음처럼 제한해야 합니다.

```text
PASS: NORMAL/LOW_LIGHT output correctness under scenario vectors
NOT YET: DFX transition latency, frame drop, partial bitstream integration
```

### 2. Current output shape is H x W

현재 default golden contract는 DPU 연결을 위해 `H x W`를 유지합니다. 과거 2x2 binning의 `H/2 x W/2`는 future ablation입니다.

### 3. Synthetic vectors are not dataset proof

Grid images는 hardware arithmetic 검증용입니다. COCO/ExDark/mAP 개선 증거가 아닙니다. 나중에 dataset-backed vectors를 별도 추가해야 합니다.

## Recommended next Ponytail steps

1. Keep current C-Sim sequence stable.
2. Add one dataset-backed pseudo-RAW vector only after current synthetic loop remains green.
3. Add Vitis HLS `csynth` only on a machine with Vitis installed.
4. Parse real `csynth.rpt` into a small table instead of manually copying metrics.
5. Only then start cosim / RTLsim / DFX integration.

## Acceptance now

Current acceptance command:

```bash
cd isppipeline/hls
make verify
make report
```

Expected:

```text
DFXISP golden vector compare passed (832 pixels)
DFXISP C-sim smoke tests passed
```
