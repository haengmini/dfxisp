# DFXISP C-Sim Scenario

현재 `isppipeline/hls/` C-Sim은 조도 변화 시나리오를 작은 synthetic grid frame으로 고정해 HLS C++ 출력과 Python golden output을 bit-exact 비교합니다.

## 핵심 용어

- `8x8`, `16x16`: 테스트 프레임 해상도입니다. 필터 크기나 binning 크기가 아닙니다.
- `3x3`: 현재 demosaic에서 쓰는 local sampling window입니다.
- `2x2 binning`: 과거/향후 low-light ablation 후보입니다. 현재 C2 default golden contract는 DPU 연결을 위해 `H x W` shape를 유지합니다.
- `grid`: 검정/흰색 단일 패치가 아니라 셀마다 다른 조도를 갖는 synthetic illumination pattern입니다.

## 현재 시퀀스

사용자 검토 요청에 따라 현재 golden-vector frame 순서는 다음과 같습니다.

```text
NORMAL x3 → LOW_LIGHT x3 → NORMAL x1
```

| Seq | Case | Mode | Size | 목적 |
|---:|---|---|---:|---|
| 1 | `seq1_bright_normal_grid_8x8` | NORMAL | 8x8 | 밝은 조도 정상 경로 |
| 2 | `seq2_bright_normal_grid_8x8` | NORMAL | 8x8 | 연속 normal 안정성 |
| 3 | `seq3_mixed_normal_grid_16x16` | NORMAL | 16x16 | 혼합 조도지만 normal 유지 |
| 4 | `seq4_dark_lowlight_grid_8x8` | LOW_LIGHT | 8x8 | 어두운 조도 low-light 경로 |
| 5 | `seq5_dark_lowlight_grid_8x8` | LOW_LIGHT | 8x8 | 연속 low-light 안정성 |
| 6 | `seq6_mixed_dark_lowlight_grid_16x16` | LOW_LIGHT | 16x16 | 혼합 저조도 low-light 처리 |
| 7 | `seq7_threshold_boundary_normal_grid_8x8` | AUTO/NORMAL | 8x8 | threshold 경계에서 normal 복귀 |

## 왜 이런 순서인가

원래 연구 시나리오는 다음 질문을 다룹니다.

```text
1. Bright  -> normal
2. Dark    -> checker trigger -> PR to low-light -> output
3. Bright  -> checker trigger -> PR to normal    -> output
```

현재 C-Sim은 실제 PR/DFX를 수행하지 않습니다. 대신 같은 목적을 C-Sim 단계에서 다음처럼 축소 검증합니다.

```text
밝은 구간 3프레임      -> NORMAL output correctness
어두운 구간 3프레임    -> LOW_LIGHT output correctness
경계/복귀 1프레임      -> AUTO threshold policy와 NORMAL 복귀 후보
```

즉 지금 단계의 목적은 DFX 재구성 latency 측정이 아니라, **각 조도 구간에서 HLS arithmetic output이 golden vector와 맞는지**를 먼저 고정하는 것입니다.

## 현재 측정 가능 항목

현재 repo만 clone해서 즉시 측정 가능한 항목:

- Normal path output correctness
- Low-light path output correctness
- AUTO threshold 경계 케이스
- golden-vector row count / case coverage
- C-Sim smoke test pass/fail

아직 Vitis/Vivado 환경 없이는 측정하지 않는 항목:

- LUT / FF / BRAM / DSP
- HLS latency / II
- Fmax / WNS / timing
- cosim
- real DFX integration
- partial bitstream size
- reconfiguration latency
- frame drop / throughput / power estimate

## 실행

```bash
cd isppipeline/hls
make verify
make report
```

기대 결과:

```text
DFXISP golden vector compare passed (832 pixels)
DFXISP C-sim smoke tests passed
```
