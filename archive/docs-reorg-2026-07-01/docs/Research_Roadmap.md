# Research Roadmap

---

## 0. 연구 Flow 개요 및 진행 현황 (v2 · 2026-06-04 갱신)

> 본 연구는 **SW 트랙**(컬러 CNN + ISP Python 골든모델, `Dataset/`·`model/`)과 **HW 트랙**(FPGA DFX ISP, `isppipeline/proposal/`·`isppipeline/_ref/`·`zcu104_platform/`)이 병렬로 진행되어 **골든 벡터**에서 합류한 뒤, DPU 통합·보드 실증으로 마무리되는 구조입니다.

### 0.1 전체 구조

```
┌──── SW 트랙 (Dataset/, model/) ──────────────────────────────────────┐
│ 데이터셋 → 컬러 CNN 학습 → ISP Python 골든모델(isp_pipeline.py)        │
│                                    │ mAP 평가 · 동적전환 sim          │
│                                    ▼                                  │
│                          골든 벡터 (RGB32 .hex)  ◄── 알고리즘 확정     │
└────────────────────────────────────┬─────────────────────────────────┘
                                      │ (정답 기준)
┌──── HW 트랙 (isppipeline/proposal/, zcu104_platform/) ────▼──────────┐
│ HLS 컬러 커널 → C-Sim 비트대조 → C-Synth → RTL Sim → DFX 빌드 → 보드   │
└──────────────────────────────────────┬────────────────────────────────┘
                                        ▼
                              DPU 통합 + 보드 실증 (합류)
```

### 0.2 확정 파이프라인 (인터페이스: 전 구간 32-bit RGB)

```
RGB32 in → [RP] binning_gain(3ch, LL=2×2 bin) → [Static] BLC → demosaic(bypass)
         → AWB → CCM → Quant → Gamma(RGB 3ch LUT) → RGB32 out → DPU
```

- 패킹: `[31:24]=0x00 / [23:16]=B / [15:8]=G / [7:0]=R`
- **인터페이스 RGB32 in/out 확정 (2026-06-04)** — YUYV 폐기. 근거: DPU(RGB[-1,1]) 직결, SW↔HW를 단일 RGB 도메인에서 비트대조(round-trip 제약 소멸), 컬러 재학습이 활용하는 색정보 full 보존. 상세 §4.
- demosaic은 데이터셋이 RGB라 **bypass(항등)**, 보드 Bayer 센서 연동 시에만 실동작.

### 0.3 진행 현황

**✅ 완료**

| 트랙 | 항목 |
|------|------|
| HW (grayscale 기준) | HLS 커널 4종 · Block Design · ICAP/DDR · PS 드라이버 · DFX 빌드. pr_verify PASS, WNS +4.0 ns, 비트스트림 Full 19MB·Partial 1.48MB, RTL Sim 양방향 전환 error=0 |
| SW | 데이터셋(COCO_5000·ExDark_5000) · 평가 인프라(조건 A~F) · ISP Python 골든모델 · 컬러 재학습 step1/step2 학습 |
| SW 결과 | **적응형 ISP 이득 입증**: ExDark normal 14.6%→lowlight **38.4%**, COCO none 33%>normal 19% |
| 결정 | **인터페이스 RGB32 in/out 확정** (YUYV 폐기, demosaic bypass, DPU 직결) |
| **HW 컬러화 (2026-06-04)** | **HLS 3커널 RGB32 재작성 + C-Sim 골든 비트대조 mismatch=0** — isp_pipeline(3ch)·binning_gain(2D 2×2 라인버퍼)·checker(Y=(R+2G+B)/4). 골든모델/벡터(Phase A) 완비 |
| **SW 컬러 모델 (2026-06-05)** | 백본 망각 해결 → **true-B v3**(discriminative LR) COCO100 normal **24.25%**/none 25.75% = best raw-trained. **ISP-in-the-loop v3**로 저조도 적응 ISP 이득 입증(ExDark normal 16.6>none 15.4) |

> ✅ HW 데이터패스 커널은 **컬러 RGB32로 전환 완료(C-Sim 검증)**. 남은 HW는 RTL 래퍼(C4)·BD 정합·합성/구현(D~I).

**🔄 진행 중 / 재검토**

- **사전학습 백본 mAP 역전 → 해결(2026-06-04~05)**: 원인은 catastrophic forgetting(드리프트 282~575%). 수정 진행: v2(freeze5+균일LR0.001) 15.5% → **v3 true-B**(freeze5 + **discriminative LR** 헤드0.01/백본0.001) **COCO100 normal 24.25%/none 25.75%, val 5.04** = best raw-trained. **두 번째 발견**: raw 학습이라 ISP 출력이 eval에서 OOD(none≥normal) → **ISP-in-the-loop 학습**(`--isp_in_loop`)으로 ExDark에서 `ISP(16.6)>none(15.4)` 뒤집어 **적응 ISP 이득 입증**. 다음: 둘 결합(v4). 상세 `docs/Analysis_Report.md` Part II.

**📋 할 일** (✅ = 2026-06-04 완료분)

| 순번 | 작업 | 상태 |
|------|------|------|
| ① | HW 컬러 커널 재작성 — Phase A(골든)·C(커널)·B1(C-Sim) | ✅ 3커널 mismatch=0 |
| ①b | 남은 HW: C4 Verilog 래퍼 → D(Csynth)·E(Cosim)·F(RTLsim)·G/H/I(PR/Impl/Bit) + `create_bd.tcl` width/DMA{32} 정합 | ⬜ |
| ② | 백본 회귀 원인 분석 → 컬러 모델 확정 | ✅ v2 채택 (v3 검증 중) |
| ②b | 확정 모델로 555장 전체 mAP 재평가 (조건 A~F) | ⬜ |
| ③ | Vitis-AI 양자화 → DPU `.xmodel` | ⬜ |
| ④ | DPU 통합(RGB32 직결) + 보드 실증(오버헤드·throughput·전력) | ⬜ |
| ⑤ | 최종 문서화 (Analysis_Report·phase4_report) | ⬜ |

> **세션 진척(2026-06-04)**: 인터페이스 RGB32 확정 → 골든모델/벡터(Phase A) → HLS 3커널 RGB32 재작성+C-Sim 비트대조(Phase C/B1) 완료. SW는 백본 망각 해결(v2 채택). 관련 계획/기록은 `docs/reference/demo_plan_hw_inspection_workflow.md`에 보존되어 있습니다.

---

## 1. 연구 목적 (Objectives)

최근 자율주행, 보안 카메라, 로봇 비전 등 다양한 실시간 시스템에서 인공지능(CNN) 기반 객체 인식의 중요성이 커지고 있습니다. 하지만 이러한 시스템은 주야간, 터널 진출입 등 급격한 조도 변화 환경에 노출될 때 인식률이 급감하는 한계가 있습니다.

본 연구의 목적은 **DFX(Dynamic Function eXchange, 부분 재구성) 기술을 활용한 적응형 ISP(Image Signal Processor) 파이프라인 설계**입니다.
고정된 하드웨어 ISP 대신, 환경(밝기 등)의 변화를 실시간으로 감지하여 하드웨어 자원 일부를 환경에 가장 적합한 로직(예: 저조도 특화 이미지 처리 필터)으로 실시간으로 교체(Reconfiguration)함으로써, FPGA 리소스 효율을 극대화하고 후단 CNN 모델의 객체 인식 정확도를 향상시키는 것을 목표로 합니다.

---

## 2. 연구 배경 (Background)

- **기존의 한계**: 전통적인 하드웨어 ISP는 주간용, 야간용, 악천후용 필터를 모두 하드웨어 내에 구현해 두어야 하므로 실리콘 면적(Area)과 전력 소비가 비효율적으로 증가합니다.
- **DFX 기술의 가능성**: Xilinx의 DFX(부분 재구성) 기술을 사용하면 시스템을 재부팅하지 않고도 FPGA 내부의 특정 블록만을 다른 비트스트림(Bitstream)으로 교체할 수 있습니다.
- **CNN과의 결합**: 좋은 품질의 이미지는 CNN의 검출 성능과 직결됩니다. 외부 환경 변화에 실시간으로 대응하는 하드웨어 ISP는 궁극적으로 AI 인퍼런스의 안정성을 보장하는 가장 빠르고 효과적인 전처리 방법입니다.

---

## 3. 연구 방법 및 실험 과정 (Methodology)

### Phase 0: Baseline 셋업 및 검증 ✅

커스텀 HLS ISP 파이프라인(BLC, Pre-gain, Demosaic(Y-only), AWB, CCM, Gamma, YUV)과 DFX 부분 재구성 환경을 ZCU104(xczu7ev) 기반으로 구축합니다.
HLS C-Sim 및 RTL Sim을 통해 Normal/Low-Light 전환 정확성을 검증하고, Timing WNS와 pr_verify 결과로 기준선을 확인합니다.
MobileNet SSD 기반의 CNN 추론 환경을 연동하고 기본 조도에서의 Baseline 정확도를 측정합니다.

**결과**: HLS 커널 4종 + Block Design + ICAP Controller + DFX 비트스트림 생성. pr_verify PASS, WNS +4.0 ns.

### Phase 1: 환경 감지 모듈 (Checker) 설계 ✅

실시간 비디오 스트림에서 조도(Illuminance)를 연산하고, 급격한 변화나 임계값(Threshold) 도달 여부를 판단하는 경량화된 하드웨어 체커(Checker) 블록을 설계합니다.
시뮬레이션을 통해 체커가 올바르게 트리거 신호를 발생시키는지 검증합니다.

### Phase 2: DFX(PR) 컨트롤러 및 동적 스위칭 구현 ✅

`Normal Mode`와 `Low-Light Mode` 두 가지 하드웨어 커널(Reconfigurable Partition)을 각각 합성합니다.
체커의 트리거 신호를 받아 기존 파이프라인의 데이터를 안전하게 비우고(Draining) 새로운 비트스트림을 로드하는 `PR Controller` FSM을 설계합니다.
전환 과정에서 발생하는 지연 시간(Overhead)과 데이터 무결성을 검증합니다.

### Phase 3: CNN 성능 평가 및 통합 검증 (진행 중)

#### 평가 데이터셋: ExDark_5000 (저조도) & COCO_5000 (일반 조도)

| | ExDark_5000 | COCO_5000 |
|---|---|---|
| 원본 | ExDark (7,363장, 저조도 전용) | COCO val2017 (5,000장) |
| 유효 이미지 | 전체 (저조도 이미지는 모두 대상 클래스 포함) | 3,689장 (12개 대상 클래스 포함 이미지만) |
| train / val / test | 2,558 / 575 / 555 | 2,559 / 575 / 555 |
| 경로 | `Dataset/ExDark_5000/` | `Dataset/COCO_5000/` |
| 조명 조건 | 저조도 10종 (Low, Ambient, Object, Single, Weak, Strong, Screen, Window, Shadow, Twilight) | 일반 조도 (COCO val2017 원본) |
| 레이블 형식 | YOLO 포맷, 0-indexed 12클래스 | YOLO 포맷, 동일 0-indexed 12클래스 |

**12개 공통 클래스 (YOLO 0-indexed):**
`0:person, 1:bicycle, 2:car, 3:motorcycle, 5:bus, 8:boat, 15:cat, 16:dog, 39:bottle, 41:cup, 56:chair, 60:dining table`

**COCO_5000 레이블 생성 기준** (`regen_coco5000_labels.py`):
instances_val2017.json에서 COCO cat_id → YOLO 0-indexed로 올바르게 변환.
`1→0, 2→1, 3→2, 4→3, 6→5, 9→8, 17→15, 18→16, 44→39, 47→41, 62→56, 67→60`

**재구성 기준** (`restructure_datasets.py`):
COCO val2017 유효 이미지(3,689장)를 binding constraint로 삼아 두 데이터셋 동일 규모 정비.
빈 레이블 이미지는 제거하고, 별도 보존 폴더는 두지 않는다.

#### 평가 지표: mAP (Mean Average Precision)

각 데이터셋은 독립적으로 GT 사용 (동일 class ID 체계이므로 같은 평가 코드 적용 가능).
전체 mAP + 12개 클래스 per-class AP 보고 (person 편중 왜곡 방지).

| 조건 | 데이터셋 | ISP | 목적 |
|------|---------|-----|------|
| **A** | ExDark_5000/test | 없음 | 저조도 기준선 |
| **B** | ExDark_5000/test | Normal ISP | 잘못된 ISP 적용 효과 |
| **C** | ExDark_5000/test | Low-Light ISP | 적응형 ISP 효과 ← **핵심** |
| **D** | COCO_5000/test | 없음 | 일반 조도 기준선 |
| **E** | COCO_5000/test | Normal ISP | 일반 조도 ISP 효과 |
| **F** | DynamicSwitch (혼합 시퀀스) | 적응형 (Checker 시뮬) | E2E 동적 전환 검증 ← **DFX 핵심** |

기대 결과: `C > B > A`, `E ≈ D`, 조건 F의 안정 구간 ≈ C·D 수준

> **주의**: COCO_5000/test의 cat(28박스, 27장)·dog(25박스, 25장)는 샘플이 희박하여 AP 수치 변동이 클 수 있음. 결과 해석 시 참고치로만 활용.

#### 조건 F: DynamicSwitch — 적응형 동적 전환 시뮬레이션

COCO(일반 조도)와 ExDark(저조도) 이미지를 교차 배열한 시퀀스로 Checker 상태 기계를 Python에서 구동하여 DFX 모드 전환 동작을 E2E 검증합니다.

**데이터셋 구성** (`Dataset/DynamicSwitch/sequence.json`):

```
[COCO × 100] → [ExDark × 100] → [COCO × 100] → [ExDark × 100] → [COCO × 100]
  (Normal 안정)   (→ Low-Light 전환 유도)  (→ Normal 복귀 유도)   (2사이클)
```

- 총 500 프레임 (COCO_5000/test 처음 250장 + ExDark_5000/test 처음 250장)
- 파일 복사 없이 기존 두 데이터셋 경로 참조 (`sequence.json` 매니페스트)
- 각 이미지는 원본 GT 레이블 유지

**Checker 시뮬레이션 로직** (`simulate_dynamic_switch.py`):

```python
mode = "normal"
reconfig_countdown = 0

for img, label in sequence:
    Y = (img[...,0] + 2*img[...,1] + img[...,2]) / 4   # Y = (R+2G+B)/4
    dark_ratio = np.mean(Y < 50)

    if mode == "normal" and dark_ratio > 0.4:
        mode = "lowlight";  reconfig_countdown = RECONFIG_FRAMES
    elif mode == "lowlight" and dark_ratio < 0.2:
        mode = "normal";    reconfig_countdown = RECONFIG_FRAMES

    isp_mode = previous_mode if reconfig_countdown > 0 else mode
    reconfig_countdown = max(0, reconfig_countdown - 1)

    processed = apply_isp(img, isp_mode)
    run_and_evaluate(processed, label)
```

**측정 항목:**

| 항목 | 내용 |
|------|------|
| 세그먼트별 mAP | 안정-밝음 / 과도 구간 / 안정-어두움 각각 측정 |
| 전환 감지 지연 | Checker 트리거까지 소요 프레임 수 |
| 과도 구간 성능 저하 | 전환 중 "틀린 ISP 모드" 구간의 mAP 하락 폭 |
| `RECONFIG_FRAMES` 민감도 | 0 → RTL 검증 후 실제값으로 교체 가능 |

#### ISP Python 시뮬레이션

- 대상: `ExDark_5000/test/` (555장), `COCO_5000/test/` (555장)
- RGB JPEG/PNG → HLS ISP 동일 정수 산술 적용 → RGB PNG 저장
- **파이프라인**: `[Binning] → BLC → Pre-gain (Q8.8) → AWB (Q8.8, 채널별) → CCM (Q8.8) → Gamma LUT (R/G/B 채널별 독립)`
  - Python 시뮬레이션은 이미 RGB 복원된 이미지를 처리하므로 Demosaic 단계 바이패스
  - HW의 YUYV 출력과 달리 RGB PNG로 저장
- Normal: γ=2.2, gain×1.0 / Low-Light: γ=4.0, gain×1.25, 2×2 binning
- 출력 경로: 평가 시 `isp_pipeline`을 실시간 적용하며, 저장 파생 폴더는 두지 않는다.
- 스테이지별 평균 처리 시간: Normal ~21.6 ms/장, Low-Light ~6.4 ms/장 (binning으로 픽셀 수 1/4 감소)

#### Gain vs Gamma — 모드별 γ 값을 다르게 설정한 근거

| | Gain (선형) | Gamma (비선형) |
|---|---|---|
| 수식 | `output = input × k` | `output = (input/255)^(1/γ) × 255` |
| 어두운 픽셀 (30) | gain×2 → 60 | γ=4.0 → 134 |
| 밝은 픽셀 (150) | gain×2 → 300 → **clip 255** | γ=4.0 → 224 |
| 특성 | 모든 픽셀 동일 비율 상승 → 밝은 영역 포화 | 어두운 픽셀일수록 더 많이 상승 → highlight 손실 없음 |

- γ=2.2 (Normal): sRGB 표준 곡선. 일반 조도 CNN 학습 데이터 분포와 유사한 밝기 유지
- γ=4.0 (Low-Light): 어두운 픽셀 강하게 확장. 입력 30 기준 γ=2.2→75, γ=4.0→134

#### CNN 모델: MobileNetV1-SSD

- 체크포인트: `model/mobilenet_ssd/build/float/ssd_best.pth`
- 입력: 현재 연구 메인라인은 RGB 기반 평가를 사용하며, 과거 grayscale 실험 기록은 historical baseline으로만 참조
- 평가 클래스: ExDark 12클래스 (YOLO 0-indexed, COCO-80과 매핑 완료)

---

## 4. HW 32-bit RGB 전환 검증 전략 (✅ 인터페이스 확정 2026-06-04)

> **현재 구현(Phase 0~3)**: 8-bit grayscale 입력 / 16-bit YUYV 출력 기준.
> **확정 방향**: 전 구간 **32-bit RGB** in/out으로 전환 (YUYV 폐기, demosaic bypass). 이 절은 해당 전환의 단계별 기술 검증 계획이며, 관련 계획서는 `docs/reference/demo_plan_hw_inspection_workflow.md`에 보존되어 있습니다. Python SW 골든모델 확정 후 HLS → RTL → DFX 순서로 순차 진행하며, 일부 항목은 아직 구현 중입니다.

### 4.1 검증 목표

- **최종 목적**: 실시간 조도 변화에 따라 Normal/Low-Light 모드가 동적으로 전환되는 DFX ISP HW 파이프라인을 시뮬레이션으로 완벽히 검증하고, 처리된 결과물이 CNN mAP를 정상 보장하는지 평가합니다.
- **핵심 검증 기준**: `build_isp_outputs.py` 결과와 HLS C-Simulation, RTL Simulation 간의 **1:1 Pixel-exact(비트 수준 일치)** 정합성을 **32-bit RGB** (유효 24-bit, 상위 8-bit = 0x00) 수준에서 달성합니다.
- **AXI 폭 결정**: AXI DMA(PG021)는 2의 거듭제곱 폭만 지원하므로 RGB 3채널을 24-bit가 아닌 **32-bit**로 패킹합니다 (`[31:24]=0x00 / [23:16]=B / [15:8]=G / [7:0]=R`).
- **순차 구현/검증 흐름**: `Python ISP 알고리즘 확정 → HLS 커널 C++ 수정 및 CSim/CoSim → RTL Static/RP Wrapper 수정 및 검증`

### 4.2 ISP 파이프라인 알고리즘 명세 (Python 골든 모델 기준)

`build_isp_outputs.py`를 골든 모델로 삼아 32-bit RGB 입출력 픽셀 데이터(Hex 포맷)를 생성합니다.
HLS C-Sim은 이 골든 벡터와의 `memcmp` 비교로 pixel error = 0을 목표로 합니다.

1. **입력**: RGB 이미지 (3채널, 24-bit 유효, 픽셀당 `{B, G, R}`)
2. **2D 공간 2×2 Binning (Low-Light 모드 전용)**: R, G, B 채널별로 인접 2×2 영역의 4픽셀 합산 후 게인 처리.
   - $\text{sum} = p(2r, 2c) + p(2r, 2c+1) + p(2r+1, 2c) + p(2r+1, 2c+1)$
   - $\text{gained} = \text{clip}\left(\frac{\text{sum} \times 3}{8}, 0, 255\right)$
   - 출력 해상도: $(H/2, W/2, 3)$
3. **BLC (Black Level Correction)**: 각 채널별 $\text{clip}(\text{pixel} - 16, 0, 255)$
4. **Pre-gain**: 각 채널별 $\text{clip}\left(\frac{\text{pixel} \times \text{gain\_q8}}{256}, 0, 255\right)$ (Normal: ×1.0, Low-Light: ×1.25)
5. **AWB (Auto White Balance)**: 채널별 독립 게인 $\text{clip}\left(\frac{\text{ch} \times \text{awb\_gain\_ch}}{256}, 0, 255\right)$ (Low-Light: R=286, G=256, B=307)
6. **CCM (Color Correction Matrix)**: $\text{clip}\left(\frac{\text{ch} \times \text{ccm\_scale} + \text{ccm\_offset}}{256}, 0, 255\right)$ (Low-Light Scale: 288)
7. **Gamma Correction**: R, G, B 채널 각각 독립 감마 LUT 적용 (Normal: $\gamma=2.2$, Low-Light: $\gamma=4.0$)

**생성 골든 벡터:**
- `input_bright_rgb.hex` / `input_dark_rgb.hex`
- `expected_normal_rgb.hex` / `expected_lowlight_rgb.hex`

### 4.3 HLS 소스 수정 가이드 (C-Sim & Co-Sim)

- **타겟 디바이스**: ZCU104 (xczu7ev-ffvc1156-2-e), 250MHz 클럭(4ns 주기), II=1 목표
- **`binning_gain_kernel`**: `ap_axiu<8>` → `ap_axiu<32>`. 행 단위 라인 버퍼(Line Buffer)를 이식하여 2D 2×2 합산을 스트리밍 방식으로 구현.
- **`isp_pipeline_kernel`**: Demosaic / YCbCr 변환 / YUYV 패킹 로직 완전 제거. R, G, B 8-bit 데이터를 3채널 독립 처리하여 32-bit RGB로 직접 출력.
- **`checker_kernel`**: 32-bit RGB 입력에서 $Y = (R + 2G + B) / 4$ 휘도 연산으로 수정.
- **Gamma LUT 파티셔닝**: R, G, B 채널 동시 적용을 위해 `gamma_lut` 배열을 cyclic factor=3으로 `ARRAY_PARTITION` 하여 II=1 확보.
- **검증**: C-Simulation에서 Python 골든 벡터와 `memcmp` 비교 → 픽셀 에러 0 달성.

### 4.4 RTL 소스 수정 가이드 (단일 모드 정밀 검증)

- **`isp_pipeline_wrapper.v` / `rp_wrapper.v`**: 입출력 포트를 `data_in[31:0]`, `data_out[31:0]`으로 수정 (상위 8-bit 무시).
- **3채널 병렬 연산**: 내부 BLC, Gain, AWB, CCM, Gamma LUT 연산부가 R, G, B 8-bit 데이터 각각에 대해 독립 병렬 수행되도록 하드웨어 버스 복제.
- **파라미터 일치**: `BLC_NORMAL/LOWLIGHT = 8'd16`, `GAIN_LOWLIGHT = 16'd320`, `CCM_SCALE_LOWLIGHT = 16'd288` 등 수치를 `isp_params.h` 실제 값과 정확히 일치시킴.
- **`create_bd.tcl`**: AXI DMA 폭 수정 — MM2S `{8}` → `{32}`, S2MM `{16}` → `{32}`.
- **검증**: `top_sim.v`에서 `pixel_out` 32-bit 변경, `$readmemh`로 골든 벡터 로드 후 클럭 단위 비교 → `error_count = 0` 확인.

### 4.5 DFX 멀티프레임 동적 전환 시뮬레이션

32-bit RGB 인터페이스 사양에서 DFX FSM과 조도 감지 Checker가 정상 작동하는지 5프레임 시나리오로 최종 검증합니다.

**5프레임 검증 시나리오:**

1. **Frame 1 (Bright)**: NORMAL 모드 작동 → 32-bit RGB 출력 정합성 검증
2. **Frame 2 (Dark)**: NORMAL 상태로 처리 시작 → Checker에서 저조도 판정 → `mode_changed` 트리거 → PR FSM 작동 (LOW_LIGHT 비트스트림 재구성)
3. **Frame 3 (Dark)**: LOW_LIGHT 모드 작동 → 32-bit RGB 출력 정합성 검증 (해상도 $H/2 \times W/2$ 변환 확인)
4. **Frame 4 (Bright)**: LOW_LIGHT 상태로 처리 시작 → Checker에서 고조도 판정 → `mode_changed` 트리거 → PR FSM 작동 (NORMAL 비트스트림 재구성)
5. **Frame 5 (Bright)**: NORMAL 모드 원복 작동 → 32-bit RGB 출력 정합성 검증

**Checker 모듈 수정:**
- 32-bit RGB 입력 픽셀에서 실시간 휘도 $Y = (R + 2G + B) / 4$ 연산
- $Y < 50$인 어두운 픽셀 수 누적 → 프레임 윈도우 내 비율 판별
  - NORMAL → LOWLIGHT: 비율 > 40% 시 트리거
  - LOWLIGHT → NORMAL: 비율 < 20% 시 트리거

**PR Draining 검증:**
모드 전환 요청 시 파이프라인 내 잔여 AXI-Stream 데이터가 소실 없이 클리어(Drain)된 뒤 재구성 완료(`pr_done`)와 리셋 동작이 안정적으로 연계되는지 확인.

### 4.6 단계별 비교 요약표

| 비교 항목 | 1단계 (Python 골든) | 2단계 (HLS C-Sim) | 3단계 (RTL Sim) | 4단계 (RTL DFX Sim) |
| :--- | :--- | :--- | :--- | :--- |
| **입력 포맷** | PNG/JPEG RGB (24-bit 유효) | `.hex` RGB (32-bit, 상위 8-bit=0x00) | `.hex` RGB (32-bit) | `.hex` Bright/Dark RGB 프레임 교차 입력 |
| **출력 포맷** | PNG RGB (24-bit 유효) + `.hex` 골든 벡터 | `.hex` RGB (32-bit) | `.hex` RGB (32-bit) | `.hex` RGB (32-bit) |
| **핵심 변경점** | ISP 알고리즘 확정 + hex dump 추가 | `ap_axiu<32>`, Demosaic/YUYV 제거, 2D 라인버퍼 Binning, 3채널 Gamma 파티셔닝 | Wrapper 32-bit 수정, 3채널 병렬화, 파라미터 매칭 | Checker Y 연산기 추가, PR FSM 5프레임 검증 |
| **비교 대상** | CNN mAP 성능 확인 | Python 골든 `.hex` 파일 | Python 골든 `.hex` 파일 | Python 골든 `.hex` 및 DFX FSM 타이밍 |
| **최종 목표** | 알고리즘 확정 및 골든 벡터 획득 | C++ ↔ Python 1:1 정합성 | RTL ↔ Python 1:1 정합성 | 프레임 손실 없는 실시간 모드 재구성 완료 |

---

## 5. 보드 실장 및 실증 (미래 계획, TODO E)

실제 ZCU104 보드에서 DFX 기능 동작, 비트스트림 전송 오버헤드 측정 및 하드웨어 가속 성능을 검증합니다.

- **개발 도구 및 플랫폼**: Vivado Design Suite (비트스트림 생성 및 물리적 합성), Baremetal + FatFs (PS 드라이버 제어)
- **하드웨어 디바이스**: ZCU104 평가 보드 (xczu7ev-ffvc1156-2-e)
- **부분 재구성(DFX) 사양**: ICAP 인터페이스를 통한 Dynamic Reconfiguration 영역 교체, PR Controller IP 동작

**검증 절차 (TODO E.1~E.3):**

1. **XSA 내보내기** (`export_xsa.tcl`): Vivado Block Design → `top_bd_wrapper.xsa` 생성
2. **PS 드라이버 빌드**: `ps_driver/main.c` 작성 (GIC 초기화 + DMA + PR 루프 통합), XSCT 기반 Vitis workspace 자동화
3. **JTAG 배포 및 실증** (`deploy_jtag.tcl`): ZCU104 연결 후 PR 전환 실증

**검증 출력물:**
- ILA(Integrated Logic Analyzer)를 통해 캡처된 실제 HW 버스 신호
- 모드 전환 오버헤드(ms) 측정 결과
- 하드웨어 전력 소모(Watt) 리포트
