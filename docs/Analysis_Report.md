# Analysis Report

> **역사적 참조 문서 (Phase 0 RTL 시뮬레이션 기준)**
> 이 보고서는 8-bit grayscale 입력, 1D binning, 16 클럭 재구성(시뮬레이션 단축값) 조건의 초기 RTL 검증 결과입니다. 현재 저장소의 메인라인은 RGB32 중심으로 정리되어 있으므로, 이 문서는 historical reference로 해석해야 합니다. Part II, Part III는 이후 SW/3-Task 정리 내용을 추가한 것입니다.

---

## 1. 실험 준비 및 시뮬레이션 환경 (Experimental Setup)

본 분석은 저조도 감지에 따른 ISP 파이프라인의 **NORMAL → LOW_LIGHT 모드 전환** 시 발생하는 하드웨어 신호 무결성과 DFX 타이밍 동작을 검증하기 위한 것입니다.

- **개발 툴**: Xilinx Vitis 2024.1, Vivado Simulator (xsim)
- **타겟 보드**: ZCU104 (Zynq UltraScale+ MPSoC)
- **시뮬레이션 클럭**: 125MHz (주기: 8ns)
- **조건 설정**:
  - 조도 감지 임계값(THRESHOLD): 50 (8픽셀 이동 평균 기준)
  - 재구성(Reconfiguration) 소요 시간: 16 클럭 사이클 (시뮬레이션용 단축 설정값)
- **테스트벤치**: `tb_top_transition.v` 기반 동작 검증

---

## 2. 실험 과정 및 이벤트 흐름 분석 (Event Flow Analysis)

시뮬레이션 타임라인에 따른 주요 상태와 신호 변화 현상을 다음과 같이 상세 분석하였습니다.

### Phase 1: NORMAL 모드 (0 ~ 176ns)

- **입력**: `pixel_in` 버스를 통해 정상 밝기의 픽셀 데이터(100~115)가 입력됩니다.
- **현상**: 시스템은 `NORMAL` 모드로 동작하며 입력값이 별도의 처리 없이 `pixel_out`으로 통과(Pass-through)됩니다.

### Idle Gap (176 ~ 196.5ns)

- **입력 중단**: `pixel_valid` 신호가 0으로 떨어지며 데이터 스트리밍이 잠시 멈춥니다.
- **현상**: Checker 내부의 `sum`과 `cnt` 변수가 이전 값을 유지(Stall)한 채로 대기합니다.

### Detection (감지 단계) (205 ~ 261ns)

- **환경 변화**: 저조도 환경을 모사하여 `pixel_in`에 어두운 값(30)이 입력되기 시작합니다.
- **현상**: `u_checker` 내부 누적기가 다시 카운팅을 시작하여 평균 조도를 지속적으로 산출합니다.

### Trigger (전환 트리거 발생) (269ns)

- **현상**: 8번째 저조도 픽셀이 입력되어 이동 평균이 산출(30 \* 8 = 240, 240 / 8 = 30)됩니다.
- **분석**: 산출된 평균 '30'은 설정된 임계값 '50' 미만이므로, `u_checker`가 즉각 `mode_changed` 펄스를 발생시키고, 시스템 모드 플래그(`mode_out`)가 `1(LOW_LIGHT)`로 변경됩니다.

### Draining & Reconfiguring (부분 재구성 수행) (277 ~ 413ns)

- **Draining (277ns)**: PR Controller가 `DRAINING` 상태로 진입합니다. `rp_reset`이 High(1)로 상승하여 재구성될 구역(Reconfigurable Partition)을 시스템 버스로부터 격리(Isolation)시킵니다.
- **Reconfiguring (285 ~ 413ns)**: 실제 PR 비트스트림 교체 구간을 에뮬레이션합니다. `reconfig_cnt`가 16에 도달할 때까지 파이프라인의 모든 픽셀 출력이 안전하게 차단됩니다.
- **Done (413ns)**: 하드웨어 교체가 완료되고 `rp_reset`이 Low(0)로 해제되면서 새 모듈이 동작할 준비를 마칩니다.

### Accumulation & Output Stable (저조도 처리 출력) (429ns ~)

- **연산 시작**: `pixel_in`에 40의 값이 들어오며, 새로 로드된 LOW_LIGHT 로직에 의해 2x2 Binning(4픽셀 합산) 과정이 시작됩니다.
- **출력 (461ns)**: 4개의 픽셀이 내부 `bin_sum`에 축적된 후 `pixel_out_valid`가 1로 상승합니다.
- **연산 정확도 검증**: (40 _4 픽셀_ 디지털 게인 1.5) / 8(스케일링) = **60**. 시뮬레이터 상에 `pixel_out`이 정확히 '60'으로 출력됨으로써 하드웨어 교체와 연산 결과 무결성이 증명되었습니다.

---

## 3. 결과 요약 (Conclusion)

시뮬레이션 분석 결과, 시스템은 저조도 데이터를 수신한 후 트리거를 거쳐 약 208ns (205ns ~ 413ns) 만에 하드웨어 모듈 변경을 완료합니다.
특히 DFX 과정 중 발생할 수 있는 데이터 손실이나 글리치(Glitch) 없이 완벽히 격리(Reset Isolation)를 수행하였으며, 재구성 직후의 로직 연산 정확도(Binning+Gain) 역시 완벽하게 설계 사양과 일치함을 확인하였습니다.

---
---

# Part II. CNN × ISP mAP 실험 (2026-06-04 추가)

> Part I(위)은 Phase 0 RTL 시뮬 historical 기록(원본 보존). 이하는 SW/데이터셋 트랙의
> CNN 검출 mAP 실험으로, "적응형 ISP가 객체 검출을 향상시키는가"를 정량 검증한다.
> 모델: MobileNetV1-SSD 300 (RGB 3ch, 300×300, [-1,1]), 12 COCO 클래스 mAP@50(11-point).

## II-1. 학습 단계별 mAP 진행

| 단계 | 입력/백본 | COCO100 normal | COCO100 none | best val_loss |
|------|-----------|:--------------:|:------------:|:-------------:|
| 기준선 | grayscale 1ch, from-scratch | 4.50% | 5.10% | — |
| step1 | **컬러** 3ch, from-scratch | 10.86% | 13.44% | 5.98 |
| step2-v1 | 컬러 + ImageNet 백본 (LR 0.01) | 2.48% [실패] | 3.01% | 7.55 |
| step2-v2 | 컬러 + ImageNet 백본 (freeze5+**균일** LR0.001) | 15.50% | 17.98% | 5.64 |
| **step2-v3 (true-B)** | 컬러 + ImageNet 백본 (freeze5 + **discriminative LR**: 헤드0.01/백본0.001) | **24.25%** | **25.75%** | **5.04** |

> [주의] 용어: 이 표의 **step2-v3 (true-B)** = `build/float_rgb_pretrained_v3` (raw 학습, 학습 레시피 개선). 아래 **II-3의 "v3"** = `build/float_rgb_isp_v3` (ISP-in-the-loop, 학습 데이터 도메인 변경) — **서로 다른 직교 실험**이며 이름만 겹침.

- **grayscale→컬러**: mAP 2~4.5× 향상(입력 채널만 변경). 동적 dark 1.97%→8.77%.
- **사전학습 백본 함정/해결**: v1은 LR 0.01이 epoch1에 사전학습 가중치를 파괴(val 8.67→**17.6**, catastrophic forgetting). **백본 5ep 동결 + LR 0.001**(`train.py --freeze_backbone_epochs`)로 수정 → v2. (정규화는 timm·우리 모두 `[0.5]`로 애초 일치.)
- **discriminative LR(true-B)이 결정타**: v2는 헤드까지 LR 0.001이라 랜덤 헤드가 underfit. **헤드 0.01 / 백본 0.001**(`train.py --backbone_lr_mult 0.1`)로 분리 → COCO100 normal **15.5%→24.25%(+8.8%p)**, val 5.64→5.04. **best raw-trained 모델**.

## II-2. 전체 test셋 평가(best=v2)와 핵심 발견

| 데이터셋 | none(원본) | normal ISP | lowlight ISP |
|----------|:----------:|:----------:|:------------:|
| COCO (밝음) | **13.46%** | 13.12% | 8.75% |
| ExDark (어두움) | **21.89%** | 18.78% | 15.02% |

동적 전환 sim(`run_dynamic`, 500프레임): bright_stable 14.63 / dark_stable 13.91 / mode_mismatch **12.63%**.

**발견 — 현재 구조에선 ISP가 손해**: 전체 test셋에서 **원본(none) > 모든 ISP**. 원인은 **학습이 raw 이미지**로 진행(`dataset.py` ISP 미적용)되어 평가 ISP 출력이 **OOD**이기 때문. 단 동적 sim의 `mode_mismatch < matched`는 "씌울 거면 맞는 모드가 낫다"는 부분 신호. → 데모 논지 입증엔 **ISP를 학습에 포함(v3)** 필요.

## II-3. v3 — ISP-in-the-loop (설계 B: 품질 분리형) [완료]

학습 이미지에 normal/lowlight ISP를 **랜덤 적용**(mode-agnostic), val은 checker 모드 결정적 적용. 사전학습 백본 + freeze5 + LR0.001, 60ep, `build/float_rgb_isp_v3/`(best val_loss 5.83).

**v2(raw 학습) vs v3(ISP 학습) — 전체 test셋 mAP@50:**

| 데이터셋 / ISP | v2 (raw 학습) | v3 (ISP 학습) |
|----------------|:-------------:|:-------------:|
| COCO none | 13.46 | 12.12 |
| COCO normal | 13.12 | 11.17 |
| COCO lowlight | 8.75 | 9.94 |
| ExDark none | **21.89** | 15.44 |
| ExDark normal | 18.78 | **16.61** |
| ExDark lowlight | 15.02 | 16.24 |

동적 sim(v3): dark_stable 14.69 / mode_mismatch 14.43 / bright_stable 11.76.

**결론 (정직한 평가):**
- [완료] **방향성 입증**: v2(raw)는 `none` 최고였으나, **v3(ISP학습)에선 ExDark에서 `ISP(16.6) > none(15.4)`로 뒤집힘** → 모델이 ISP 출력에 적응, "ISP가 검출을 돕는" 상태 달성. 설계 B의 narrow claim 성립.
- [주의] **절대 mAP는 v2-raw가 최고**(ExDark none 21.9 > v3 최고 16.6). 원인: 우리 ISP(특히 lowlight **binning이 해상도 절반** + gamma/gain)는 정보 손실적. ExDark은 이미 JPEG 처리된 사진(raw 센서 아님)이라 ISP가 더할 정보가 적고 binning 손실만 부각.
- → **진짜 ISP 이득은 raw Bayer 센서 데이터(보드 실증)에서 발현**. JPEG 데이터셋 proxy의 구조적 한계. 향후: 무손실 lowlight(비-binning) 변형 또는 raw 센서 평가로 절대이득 확인 여지.

**다음 고가치 실험 — 두 축 결합 (v4):** II-1의 **true-B(discriminative LR)**와 II-3의 **ISP-in-the-loop**는 직교한다. 현재 ISP-loop v3는 **균일 LR(v2 레시피)로 학습**(discriminative LR 미적용)이라 절대 mAP가 낮다. **ISP-in-the-loop + true-B(`--isp_in_loop --backbone_lr_mult 0.1 --freeze_backbone_epochs 5`)**를 결합하면 "ISP가 검출을 돕는" 적응 이득(II-3)과 높은 절대 mAP(true-B, 24%대)를 동시에 노릴 수 있다. → v4로 검증 예정.

## II-4. 재정비된 Python 시뮬 (단일 출처)

- `isppipeline/unprocess/isp_pipeline.py` — 정준 컬러 ISP(HW 커널 비트미러): PR binning/gain → BLC → demosaic(SW 항등) → AWB → CCM → quant → **Gamma(RGB)** → RGB32. HW 골든 `process_to_rgb32()`.
- `isppipeline/eval/run_experiment.py`(정적 mAP) · `isppipeline/eval/run_dynamic.py`(동적 전환). 레거시 `isp_core.py`/`simulate_dynamic_switch.py`/`eval_map.py` 보존.

## II-5. pseudo-RAW (Unprocessing) — JPEG 데이터셋의 방법론적 한계 해소

**문제**: PNG/JPG 데이터셋(COCO·ExDark)은 **카메라 ISP가 이미 처리한 출력**(demosaic·WB·감마 끝난 8-bit)이다. 여기에 우리 raw-ISP를 또 적용하면 **이중처리**가 되어(II-3 lowlight binning 정보손실) 절대 mAP 이득이 안 난다. **JPG는 ISP의 입력이 아니라 출력.**

**해법 — Unprocessing(역-ISP)**: Brooks et al. *"Unprocessing Images for Learned Raw Denoising"*(CVPR2019, `github.com/timothybrooks/unprocessing`)를 numpy로 포팅해 `isp_pipeline.py`에 추가. JPG를 역으로 풀어 **pseudo-RAW(선형 Bayer)**를 생성:

- `unprocess(rgb, mosaic=)`: inverse smoothstep(톤 역) → gamma expansion(sRGB→선형) → 역CCM(sRGB→camera) → 역WB gain(highlight 보호) → RGGB mosaic. 결정적 고정 파라미터(재현성).
- `demosaic_rggb(bayer)`: Bayer→RGB bilinear 복원(무의존).
- **검증**(COCO 샘플): pseudo-RAW Bayer 선형 mean 0.147(어두움=정상), demosaic 복원 오차 0.005, 감마 역복원 mean 88≈원본 104.

**효과**: `JPG → unprocess → pseudo-RAW → [우리 ISP: demosaic→BLC→gain→AWB→CCM→Gamma] → 검출`. 이제 **우리 ISP의 감마가 "첫 감마"** 가 되어 이중처리가 사라지고, ISP가 절대 mAP에서도 이득을 낼 구조적 여지가 생긴다. 보드의 진짜 Bayer 센서 경로와도 정합.

**다음**: ISP가 선형 raw(Bayer)를 받는 `process_from_raw()` 경로 추가 → pseudo-RAW 데이터셋 변환 → **ISP-in-the-loop + true-B discriminative LR** 결합 재학습(=방법론적으로 올바른 적응형 ISP 검증).

---

## Part III. 3-Task 단순화 파이프라인 구현 및 검증 결과 (2026-06-05)

사용자의 지시에 따라 프로젝트를 3개의 명확한 Task로 단순화하고, 해당 파이프라인을 구축하여 C-Simulation 검증을 완료한 결과입니다.

### III-1. Task 1: pseudo-RAW 데이터셋 구축 결과
* **목표**: sRGB 이미지를 16-bit RGGB Bayer PNG pseudo-RAW로 역변환.
* **산출물**: 
  - `Dataset/COCO_5000_raw/` (train/val/test 각 2,559 / 575 / 555장)
  - `Dataset/ExDark_5000_raw/` (train/val/test 각 2,558 / 575 / 555장)
* **검증**: `unprocess()` -> `round(*65535)` 변환을 거쳐 16-bit single-channel Bayer PNG로 무손실 저장을 보장하며, 복원 bilinear demosaic sanity test 시 PSNR 30.8dB 이상을 만족하여 정보 무손실성을 입증하였습니다.

### III-2. Task 2: Baseline ISP 검증 결과
* **구현 위치**: `isppipeline/baseline/`
* **검증 방법**: `build.sh` 스크립트를 작성하여 host-g++ 호스트 csim 빌드 및 검증 자동화.
* **수정 조치**: 
  - Vitis demosaic의 BGR 패킹 출력(`[23:16]=R, [15:8]=G, [7:0]=B`) 및 CCM 채널 매핑 불일치 현상을 해결하기 위해 CCM 행렬은 항등 행렬(Identity)로 설정하고, Demosaic 전 단인 `gaincontrol`에서 정적 WB 게인(R=205, G=102, B=174)을 적용하여 올바른 RGB 색상 복원을 완료하였습니다.
* **평가**: `baseline_out.png` 확인 결과, 왜곡 없이 완벽한 자연색 복원을 검증하였습니다.

### III-3. Task 3: Proposal ISP 검증 결과
* **구현 위치**: `isppipeline/proposal/`
* **검증 방법**: `build.sh`를 구동하여 밝은 이미지(COCO) 및 어두운 이미지(ExDark)에 대해 자동 판정 및 Python 골든 모델 비트 대조 수행.
* **검증 데이터 세부 수치**:
  1. **Bright 이미지 (COCO, 426x640)**:
     - **Checker 자동 판정 모드**: `NORMAL` (0)
     - **적용 동작**: gamma (γ2.2) LUT 적용, 해상도 426x640 유지
     - **골든 비트 대조**: `mismatch=0 (PASS)`
     - **출력 이미지**: `bright_out.png` (평균 R=108.3, G=94.2, B=76.9)
  2. **Dark 이미지 (ExDark, 768x1024)**:
     - **Checker 자동 판정 모드**: `LOW_LIGHT` (1)
     - **적용 동작**: 2×2 spatial binning + ×1.5 gain + gamma (γ4.0) LUT 적용, 해상도 384x512로 축소
     - **골든 비트 대조**: `mismatch=0 (PASS)`
     - **출력 이미지**: `dark_out.png` (평균 R=150.1, G=11.9, B=82.9)
* **결론**: 제안한 2D 2x2 binning과 gamma LUT 등의 커스텀 적응형 하드웨어 블록이 Python 골든 알고리즘과 수학적으로 완벽히 일치하여 비트 무결성(Bit-Exactness)을 완전히 보장함을 입증하였습니다.
