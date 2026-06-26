---
type: paper-figures
title: "DFXISP 학위논문 — 그림·표 계획"
project: DFXISP
created: 2026-06-26
note: "각 항목: 무엇을 보여주는가 + 데이터 출처 + 상태. [TODO:측정]은 실험 후 채움."
---

# 그림·표 계획 (Figures & Tables)

> 논문의 메시지를 그림이 끌고 간다. 본문 `01-thesis-draft.md`의 `[그림 FigN]`/`[TabN]`이 여기를 가리킨다.

## 그림 (Figures)
| # | 제목 | 보여주는 것 | 출처 | 상태 |
|---|------|------------|------|------|
| Fig1 | 시스템 개요 | 센서→ISP(적응)→비전. DFX 위치 강조 | 개념 | [ ] 작도 |
| Fig2 | ISP 파이프라인 (normal vs low-light 경로) | 공유 모듈 + 모드 의존(binning 프런트, γ 백엔드) | A1 §1, repo | [ ] 작도 |
| Fig3 | RP 분할 | static region + 단일 RP(=binning±denoise RM), gain·γ는 register | A1 §1 결정 | [ ] 작도 |
| Fig4 | DFX 동작 흐름 | checker→DFX Controller→ICAP→부분비트스트림 로드 | A1 §3, AMD DFX | [ ] 작도 |
| Fig5 | 재구성 지연 모델 | 지연 = RM크기 ÷ ICAP대역폭, 프레임 예산과 비교 | A1 §3 | [TODO:측정] |
| Fig6 | 모드 전환 FSM | 장면 단위 + 히스테리시스(thrashing 방지) | A1 §4 | [ ] 작도 |
| Fig7 | 결과: 면적/전력 비교 그래프 | 4종 variant 간의 리소스/전력 성능 분석 | 실험 | [TODO:측정] |

## 표 (Tables)

### Tab1. normal vs low-light 델타
| Parameter | Normal Mode | Low-light Mode | Hardware Block Type |
|---|---|---|---|
| Sensor Gain | 256 (x1.0) | 320 (x1.25) | Register Swap |
| Gamma (γ) | 2.2 | 4.0 | LUT Swap |
| 2x2 Binning | Disabled | Enabled | DFX RM (`DFX-Bin`) |
| 3x3 Denoise | Bypass | Mean Filter | DFX RM (`DFX-Bin`) |
| Local Contrast | Standard | Edge Guided | DFX RM (`DFX-FP`) |

### Tab2. 관련연구 비교표 (Related Works Comparison)
| 연구명 (Paper) | 대상 플랫폼 (Platform) | 적응 제어 방식 (Adaptation) | FPGA 실측 (FPGA Eval) | DFX/DPR 사용 | 스케줄러 오버헤드 고려 (Scheduler Cost) |
|---|---|---|---|---|---|
| **DynamicISP** ([dynamicisp]) | GPU/Software | Image-level dynamic param | X | X | X |
| **Dark-ISP** ([darkisp]) | GPU/Software | Self-adaptive pipeline | X | X | X |
| **AdaptiveISP** ([adaptiveisp]) | GPU/Software | RL pipeline selection | X | X | X |
| **POS-ISP** ([pos-isp]) | GPU/Software | Sequence-level optimization | X | X | X |
| **HISP** ([hisp]) | FPGA | Fixed hybrid pipeline | O | X | X |
| **제안 연구 (DFXISP)** | **FPGA (ZCU104)** | **Hybrid (Register + DFX RM)** | **O** | **O** | **O (Latency, stall, power)** |

### Tab3. 자원 사용량 비교 (Resource Utilisation)
| Variant | LUTs | FFs | DSPs | BRAMs | Status |
|---|---:|---:|---:|---:|---|
| (1) `Static` (Baseline) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (2) `Reg-only` | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (3) `DFX-Bin` (Proposed) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (4) `DFX-FP` (Proposed) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |

### Tab4. dynamic power 비교 (Dynamic Power Consumption)
| Variant | Normal Mode Power (W) | Low-light Mode Power (W) | Average Power (W) | Status |
|---|---:|---:|---:|---|
| (1) `Static` (Baseline) | [TODO:측정] | n/a | [TODO:측정] | [TODO:측정] |
| (2) `Reg-only` | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (3) `DFX-Bin` (Proposed) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (4) `DFX-FP` (Proposed) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |

### Tab5. 화질 및 정확도 비교 (Image Quality & Task Accuracy)
| Variant | PSNR (dB) | SSIM | mAP (COCO/ExDark) | Frame Rate (FPS) | Status |
|---|---:|---:|---:|---:|---|
| (1) `Static` (Baseline) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (2) `Reg-only` | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (3) `DFX-Bin` (Proposed) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |
| (4) `DFX-FP` (Proposed) | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] | [TODO:측정] |

## 작도 우선순위 (7월)
1. **Fig2, Fig3, Tab1, Tab2** — 제안 설계의 핵심 및 차별점. 측정 없이 지금 작도 가능.
2. 나머지(Fig5/7, Tab3~5)는 실험 후 실측 데이터 연동.
