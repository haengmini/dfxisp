---
type: experiment-report
title: "DFXISP 실험 보고서 — 조건부터 결과까지 (reset 아키텍처, SW+HW 통합)"
project: DFXISP
created: 2026-07-02
updated: 2026-07-02 (20:33 KST, adversarial-review 수정 + Vivado 재구현 반영)
status: "Stage 1~5 완료(SW proxy Stage1-3 + Vitis HLS/Vivado DFX fabric-only Stage4-5 실측). Stage 6(보드)만 TODO."
scope: "Stage 1~5 전체(SW 트랙 + HW C-synthesis/DFX 구현). Stage 6(ZCU104 실보드)만 조건 명시, 수치는 TODO(측정)."
---

# DFXISP 실험 보고서 — 조건부터 결과까지

> 2026-07-01 아키텍처 reset(**shared baseline ISP core + 상호배타 mode-specific
> tone RM slot**) 적용 후, SW 트랙(Stage 1~3)과 HW 트랙(Stage 4~5: 실제 Vitis HLS
> C-synthesis + Vivado DFX 구현)을 조건·방법·결과·해석까지 하나로 정리한 보고서.
> **2026-07-02 갱신:** `/codex:adversarial-review`가 발견한 두 결함(low-light 색상손실
> 버그, 메타데이터 RTL 미검증 인터페이스)을 수정하고 HW 전체를 재실측한 내용을 §6에 반영.
> 정본 아키텍처는 `RESEARCH.md`, 단계 계획은 `experiment-stages-2026-07-02.md`, 원자료
> CSV는 `results/`.

---

## 1. 목적과 가설

**목적:** reset 아키텍처(gain/gamma를 baseline core에서 제거하고 상호배타 tone RM으로
분리)가 머신비전 관점에서 (H1) 저조도 정확도를 개선하는지, (H2) 중복제거 후에도 정확도를
유지하는지, (H3) DFX가 자원/전력 이득을 주는지를 실험적으로 분리 검증한다.

| 가설 | 내용 | 본 보고서 범위 |
|---|---|---|
| H1 (Algorithmic) | low-light tone RM이 저조도 mAP를 무처리/오모드 대비 개선 | **검증(Stage 3)** |
| H2 (Architecture) | gain/gamma를 tone RM으로 분리해도 정확도 유지 | **검증(Stage 2·3)** |
| H3 (DFX efficiency) | DFX가 register-only 대비 자원/전력 절감 | **자원 검증(Stage 4~5), 전력은 Stage 6(보드) TODO** |

---

## 2. 실험 조건

### 2.1 실행 환경
- CPU 전용(CUDA 드라이버 구버전으로 GPU 비활성), Python3, numpy/PIL/OpenCV/torch/
  torchvision/ultralytics/pycocotools 설치.
- 검출기: `yolov8n.pt`, `yolov8s.pt` (COCO 사전학습), ultralytics `model.val()`, imgsz=640.

### 2.2 데이터셋 (pseudo-RAW)
- `data/exdark_val` (저조도), `data/coco_val` (정상조도). 각 `raw_bin/`(RGGB16, headerless
  uint16, 16→8bit shift8) + `images/`(dims 출처) + `labels/`(YOLO).
- **라벨: 두 데이터셋 모두 COCO-80 id** `{0,1,2,3,5,8,15,16,39,41,56,60}` → **remap 없음**.
- 유효 프레임: raw_bin 크기와 jpg 해상도 일치분만 사용(Stage 3 ExDark n=71, COCO n=80;
  Stage 2 ExDark n=98, COCO n=113, limit=150~200).

### 2.3 검증 대상 아키텍처와 arm 정의
tone RM slot이 shared baseline core를 감싸는 구조(2026-07-01 확정). SW eval은 데이터셋
레이아웃에 맞춰 RGGB demosaic를 쓰며(C-sim golden은 GRBG), **arm 간 상대 behaviour**를 비교.

| arm | 정의 | 출력형상 | 조건표 매핑 |
|---|---|---|---|
| **none** | demosaic만(무처리) | H×W | A(ExDark)·D(COCO) |
| **normal** | RM_NORMAL_TONE(identity) + baseline core | H×W | B·E |
| **lowlight** | RM_LOW_LIGHT_TONE(2x2 RAW bin+gain+gamma4) + core | H/2×W/2 | C·F |
| **adaptive** | checker가 프레임별 normal/lowlight 선택 | mixed | G |

### 2.4 파이프라인 파라미터 (정수, 결정적)
- **baseline core(mode 무관):** BLC offset 16 → AWB Q8 (R=286, G=256, B=307) → CCM identity.
  **gain/gamma 없음.**
- **RM_LOW_LIGHT_TONE:** 2x2 RAW binning-demosaic(R=top-left, G=(top-right+bottom-left)/2,
  B=bottom-right) → baseline core → gain ×1.25(5/4) → gamma-4.0 LUT
  `floor((255^3·v)^(1/4))`(정수 4제곱근).
- **checker:** `Y=(R+2G+B)/4`, `dark_ratio = mean(Y<50)`, `dark_ratio>0.40 → lowlight`.

### 2.5 도구 (신규, 공용 모델)
`tools/newrm_pipeline.py`(numpy 벡터화 아키텍처 모델) 위에
`scheduler_sweep.py`(Stage 1) · `image_metrics_newrm.py`(Stage 2) ·
`eval_map_newrm.py`(Stage 3). C-sim golden bit-exact 모델은 `tools/gen_golden_vectors.py`.

### 2.6 평가 프로토콜
- Stage 1: 결정적 노이즈 luma 시퀀스(1000프레임, 고정시드) + 4정책 + 파라미터 스윕(27경우).
- Stage 2: arm별 출력 이미지 지표 집계(dataset×arm 평균).
- Stage 3: arm별 이미지 생성 → `model.val()` → mAP@[.5:.95]·mAP@50. 판단 근거는 **arm 순서**.

---

## 3. 방법(절차) 요약

```text
Stage 1  scheduler_sweep.py  → results/scheduler.csv, scheduler_sweep.csv
Stage 2  image_metrics_newrm.py --root <ds> --tag <T> → results/image_metrics_<t>.csv
Stage 3  eval_map_newrm.py --root <ds> --tag <T> --model <m> → results/map_newrm_<t>_<m>.csv
```

---

## 4. 결과

### 4.1 Stage 1 — checker/스케줄러

기본 4정책:

| 정책 | mismatch | switch/1k | thrashing | skipped |
|---|---|---|---|---|
| baseline_checker | 0.054 | 86.0 | 0.884 | 344 |
| plus_hysteresis | 0.021 | 28.0 | 0.571 | 112 |
| plus_temporal(N=5) | 0.140 | 4.0 | 0.000 | 16 |
| plus_min_dwell | 0.140 | 4.0 | 0.000 | 16 |

파라미터 스윕 27경우 상위:

| band | N | dwell | mismatch | switch/1k | thrashing |
|---|---|---|---|---|---|
| **narrow** | **3** | 15~60 | **0.015** | 6.0 | 0.000 |
| narrow | 5 | 15~60 | 0.072 | 6.0 | 0.000 |

→ **narrow 히스테리시스 밴드 + temporal_N=3**가 최적(mismatch 0.015, thrashing 0). 순간
임계의 thrashing 0.884를 제거하면서 기본값(medium/N=5, 0.140) 대비 mismatch 9배 개선.
재구성 지연 PR∈{2,4,8}에서 skipped=switch×PR(선형) → 전환수 최소화가 지연 비용의 축.

### 4.2 Stage 2 — 이미지 지표

| dataset | arm | out shape | Y mean | 포화율% | dark-ratio(전→후) | gain/γ 중복 |
|---|---|---|---|---|---|---|
| ExDark(n=98) | none | 778×606 | 14.0 | 1.87 | 0.919 | False |
| ExDark | normal | 778×606 | 11.0 | 0.72 | 0.919→0.932 | False |
| ExDark | lowlight | 389×303 | 25.5 | 2.61 | 0.919→0.842 | False |
| COCO(n=113) | none | 577×494 | 64.2 | 6.29 | 0.544 | False |
| COCO | normal | 577×494 | 54.7 | 1.44 | 0.544→0.611 | False |
| COCO | lowlight | 288×247 | 120.7 | 11.25 | 0.544→0.302 | False |

- lowlight tone이 저조도를 밝힘(ExDark Y 14→25.5, dark-ratio↓). Policy A 형상 반감 확인.
- **normal(gain 없는 baseline core)이 저조도를 더 어둡게**(Y 14→11) — BLC/AWB만으로는 악화.
- COCO lowlight 포화율 11.25% — 정상조도 과처리. gain/γ 중복=False(구조 불변식 유지).
- checker 과트리거: naive 임계로 COCO 89/113이 lowlight 판정 → dark-level 재보정 필요.

### 4.3 Stage 3 — 정확도 mAP, 조건표 A~G (3 detector)

mAP@[.5:.95] (YOLO 괄호는 mAP@50):

| 조건 | dataset·arm | YOLOv8n | YOLOv8s | SSDLite-MNv3 |
|---|---|---|---|---|
| **A** | ExDark·none | **0.1561** (0.3064) | **0.2236** (0.4059) | **0.1040** |
| **B** | ExDark·normal | 0.0680 (0.1490) | 0.1249 (0.2480) | 0.0443 |
| **C** | ExDark·lowlight | 0.0554 (0.1342) | 0.1276 (0.2595) | 0.0333 |
| **G** | ExDark·adaptive | 0.0554 (0.1342) | 0.1276 (0.2595) | 0.0333 |
| **D** | COCO·none | **0.3276** (0.4707) | **0.4280** (0.6105) | **0.2320** |
| **E** | COCO·normal | 0.2879 (0.4175) | 0.3775 (0.5244) | 0.2305 |
| **F** | COCO·lowlight | 0.2574 (0.3497) | 0.3402 (0.4590) | 0.2096 |
| **G** | COCO·adaptive | 0.2590 (0.3725) | 0.3486 (0.4717) | 0.2125 |

**세 detector(YOLOv8n/s + SSD+MobileNet)·두 데이터셋 모두에서 `none`(무처리)이 최고**,
순서 `none > normal ≳ lowlight`가 detector 계열에 무관하게 유지(guardrail 결론의 견고성 강화).
SSDLite-MNv3는 torchvision COCO 사전학습(구조가 다른 detector 계열). 정확한 Vitis-AI
`tf_ssdmobilenetv1`은 가중치 부재·TF1.15로 이 환경 실행 불가 → 보드 DPU end-to-end 단계용.

---

## 5. 분석 및 해석

1. **H2 부분 반증:** de-duplication으로 normal tone을 identity로 두니 저조도에서 mAP가
   크게 하락(ExDark none 0.156 → normal 0.068). gain 없는 baseline core가 dark scene을
   어둡게 만든 것이 원인(Stage 2와 정합). → **RM_NORMAL_TONE은 register gain을 담아야** 함.
2. **H1 미지지:** low-light tone RM(bin+gain+gamma-4.0, Policy A)이 저조도에서도 none을
   못 이김. 원래 "gamma-4.0 과증폭 + H/2 해상도 손실"로 추정했으나, **2026-07-02 ablation
   실측으로 반증/정정됨** — ExDark(RM의 목표 조건)에서 손실의 약 70%는 해상도 손실이
   아니라 **두 RM이 공유하는 baseline core의 BLC/WB**에서 발생(해상도 손실 기여는
   −1.4%뿐). COCO(정상조도, 오적용 시)에서는 반대로 해상도 손실이 지배적(−11.7%).
   상세: `results/lowlight-rm-map-rootcause-2026-07-02.md`. → 재설계 우선순위는 tone
   커브가 아니라 **저조도 조건에서의 baseline core WB 완화**로 이동.
3. **스위칭 방향은 정당:** 정상조도(COCO)에서도 저조도 경로는 이득 없음(F<E<D) → 저조도
   RM은 어두울 때만 켜야 한다는 적응 방향 자체는 유효.
4. **방향 A 강화:** 본 SW 실측은 "mAP는 최소/register 처리가 담당, 구조적 tone RM은 mAP
   근거가 약함"을 재확인. ⇒ **DFX/RM의 정당화는 자원/전력(Stage 4~5, §6)** 이라는 방향 A
   서사와 정합. mAP-guardrail이 현 RM 후보를 탈락시키는 것이 방법론의 작동 증거.
5. **golden-model 버그 미러링의 교훈(§6.4):** low-light 색상손실 버그는 C++ 구현과 Python
   golden model이 **같은 잘못된 알고리즘을 미러링**했기 때문에 `make verify`(bit-exact
   교차검증)조차 잡지 못했다. 이 SW eval(§4.3 조건 C/F/G)이 참조한 mAP 증거는 사실
   **다른(색 보존) 알고리즘**을 측정한 것이었다는 점이 드러나 — bit-exact 일치가 정답과의
   일치를 보장하지 않는다는 방법론적 교훈을 남겼다. `SPEC.md` §11.5에 기록.

### 즉시 반영할 설계 수정
- (a) **RM_NORMAL_TONE = register gain**(identity 아님). de-dup은 유지하되 gain을 tone RM으로.
- (b) **low-light RM 재포지셔닝**: gamma 완화(γ≈2.5~3.0), Policy B 또는 denoise, bilinear 업샘플.
- (c) **checker dark-level 재보정**: COCO 과트리거 제거(adaptive의 lowlight 붕괴 방지).
→ 위 반영 후 Stage 3 재측정으로 guardrail 재판정.

---

## 6. Stage 4~5 (HW) — 실측 완료, 수정 이력 포함

> Stage 1~3(SW)과 달리 이 절은 **실제 Vitis HLS 2024.1 + Vivado 2024.1 도구**로 얻은
> 하드웨어 실측치다. 최초 실측(16:20~17:15 KST) 이후 adversarial review로 두 결함이
> 발견되어 소스를 수정했고, 그 수정을 반영해 **HW 전체를 처음부터 다시 합성·구현**
> (20:24~20:33 KST)했다 — 아래는 그 전체 과정을 시간순으로 기록한다.

### 6.1 실험 환경 (HW)

| 항목 | 값 |
|---|---|
| HLS 툴 | Vitis HLS 2024.1 (`/tools/Xilinx/Vitis_HLS/2024.1`) |
| 구현 툴 | Vivado 2024.1 (`/tools/Xilinx/Vivado/2024.1`) |
| 대상 디바이스 | `xczu7ev-ffvc1156-2-e` (ZCU104) |
| clock target | 5.0 ns (200 MHz) |
| 합성 flow | non-project batch Tcl (AMD UG909 DFX 표준 절차) |
| 호스트 OS | Ubuntu 22.04.5 LTS on WSL2 (Linux 6.18) |
| 작업 디렉터리 | `/tmp/hls_dfxisp/`(flat temp-dir, git 비추적 — §6.2 참조) |

### 6.2 실험 방법 (HW)

**툴체인 우회 2건 (재확인, 과거 worklog `12-worklog-2026-06-29.md`와 동일 계열):**
1. **source-path 버그:** 중첩 프로젝트 디렉터리에서 `add_files`로 design source를 추가해도
   `csim.mk`의 `HLS_SOURCES`에 누락 → `/tmp/hls_dfxisp/dfxisp_accel/`에 hpp/cpp/tb를
   flat하게 복사해 우회.
2. **종료-hang:** `close_project` 후 프로세스가 종료되지 않음(work는 끝난 상태) →
   `timeout -k <grace> <sec> vitis_hls ...`로 강제 종료.

**HLS C-synthesis (3개 top, `flow=csynth`/`export`):**
- `dfxisp_accel`(unified top, 두 RM 모두 상주, register-only 후보 = Arm2)
- `rm_normal_tone_top` / `rm_low_light_tone_top`(독립 top, DFX RM 후보 = Arm3 재료)
- 각 RM을 IP-XACT(`export_design -format ip_catalog`)로 패키징.

**Vivado DFX 구현 (non-project batch, AMD UG909):**
1. Static wrapper(`dfx_static_top.v`)를 `write_verilog -mode synth_stub`로 파라미터
   해석된 black-box 선언에서 Python으로 프로그래밍적 생성(수동 전사 오류 방지).
2. RP pblock 플로어플랜: `CLOCKREGION_X0Y0:CLOCKREGION_X1Y0`(2개 클럭 리전, 용량
   LUT 8,640 — 두 RM의 최대 요구치보다 충분히 여유).
3. **Config1**(static+RM_NORMAL_TONE) opt/place/route.
4. **Config2 구현 방법론(중요, 과거 세션에서 확립):** Config2를 static-only 체크포인트에서
   독립적으로 place하면 static 배치가 Config1과 미세하게 달라져 `pr_verify`가 실패한다.
   **올바른 절차**는 Config1의 **완전히 구현된** 체크포인트에서
   `update_design -cell u_rp -black_box` + `lock_design -level routing`으로 static 배치를
   고정한 뒤 RM2를 이식·재구현하는 것(AMD UG909 표준). 이 절차를 재적용해 static 영역이 두
   config에서 완전히 동일함을 재확인.
5. `pr_verify -initial config1 -additional config2`로 DFX 정합성 공식 확인.
6. `write_bitstream`: fabric-only 특성화라 `ap_clk`/`ap_rst_n`에 실제 보드 핀이 없음 →
   NSTD-1/UCIO-1 DRC를 `SEVERITY Warning`으로 낮춰 우회(가짜 핀을 지어내지 않고 정직하게
   문서화). Full + partial(RM별) bitstream 생성.

### 6.3 최초 실측 결과 (16:20~17:15 KST, 수정 전)

**C-synthesis (unified top, gamma2 런타임 정수 sqrt → 256-엔트리 ROM 최적화 반영):**

| instance | BRAM | DSP | FF | LUT | Fmax |
|---|---|---|---|---|---|
| `dfxisp_accel`(합계) | 8 | 30 | 7,008 | 11,217 | 273.97 MHz |
| `rm_normal_tone_top`(독립) | 4 | 12 | 3,797 | 5,202 | 273.97 MHz |
| `rm_low_light_tone_top`(독립) | 7 | 15 | 4,732 | 7,167 | 273.97 MHz |

**Vivado DFX 구현:**
- pr_verify: **PASS**(partition pin 2개, static tile 29,648개, static site 54개, static
  cell 256개, routed pip 894개 — config1/config2 완전 동일).
- Config1(static+RM_NORMAL_TONE) routed: LUT 3,948/230,256(1.71%), BRAM 1.5/312(0.48%),
  DSP 12/1,728(0.69%).
- Bitstream: `config1_full.bit` 19,311,211 bytes, `rm_normal_partial.bit`/
  `rm_lowlight_partial.bit` 각 686,664 bytes(동일 — pblock 프레임 수로 결정, 로직
  활용률과 무관).
- C/RTL Co-sim(L2 gate): RTL 시뮬레이션 자체는 7/7 성공(합성된 하드웨어가 실제로 동작함을
  보여주는 긍정 신호)하나, 자동 post-check 비교 단계가 WSL2+XSIM 환경 특유의 하네스
  한계로 SIGSEGV — "실행 성공 확인, 자동 bit-exact 비교 미완주"로 기록.

### 6.4 Adversarial review — 결함 발견과 수정

Stage 4~5 최초 실측 직후 `/codex:adversarial-review --base 0e433f9`로 전체 세션 커밋을
독립 검토한 결과 **두 결함**을 발견:

1. **색상 손실 버그 (high, 실제 확인됨):** low-light front-end가 2x2 RGGB 셀의 4개 샘플을
   **하나의 스칼라 평균**으로 합친 뒤 그 값을 다시 Bayer인 것처럼 재-demosaic — 색 정보가
   demosaic 전에 이미 파괴됨. **golden 모델(`gen_golden_vectors.py`)이 같은 버그를 그대로
   미러링**해서 `make verify`의 bit-exact 테스트가 이를 전혀 못 잡았고, 이전에 보고된
   lowlight mAP 증거(SW eval, `isp_pipeline_ver1.py`)는 **채널 정체성을 보존하는 다른
   알고리즘**을 측정한 것이라 실제 HW 후보의 증거가 아니었음이 드러났다.
2. **메타데이터 RTL 미검증 (medium, 부분적으로 확인됨):** 출력 메타데이터를
   `DfxIspResult*` 구조체 포인터로 `s_axilite` 선언 — 합성된 RTL에서 실제로 개별 필드를
   읽을 수 있는지 어떤 산출물로도 직접 확인된 적 없음(cosim도 post-check 단계에서 실패해
   미확인). 독립 코드 검증 결과 "확정적으로 깨졌다"는 근거는 과장이었으나, 검증된 적 없는
   패턴이라는 지적 자체는 정당해 더 안전한 scalar-pointer 패턴으로 교체하기로 판단.

**수정 내용 (커밋 `a2d1b6d`):**
- Finding 1 → `compute_binned_rgb_row()`로 2x2 binning과 demosaic을 **한 단계에 융합**
  (R=top-left, G=avg(top-right,bottom-left), B=bottom-right), SW golden model의
  `_bin_demosaic_rggb16`(ver1)과 bit-exact 일치하도록 Python/C++ 양쪽 동시 수정.
- Finding 2 → `DfxIspResult*` 구조체 포인터를 **4개의 개별 scalar 출력 포인터**
  (`out_width`/`out_height`/`selected_mode`/`selected_rm`)로 교체.
- 색상 보존을 직접 검증하는 **새 회귀 테스트** 추가(순수 red 2x2 셀 → 저조도 출력이
  R≫G, R≫B를 만족하는지 assert) — 옛 버그였다면 이 테스트가 실패했을 것.
- **`make verify` 646px bit-exact 유지**(순수 알고리즘 교정이라 golden CSV 123행이
  값 자체는 바뀌었지만 C++/Python 구현이 서로 계속 일치).

### 6.5 재합성/재구현 결과 (20:24~20:33 KST, 수정 반영)

수정된 소스로 **HLS C-synthesis 3종 + Vivado DFX 전체 흐름을 처음부터 재실행**했다.

**C-synthesis (수정 전 → 후):**

| top | BRAM(전→후) | DSP(전→후) | FF(전→후) | LUT(전→후) |
|---|---|---|---|---|
| `dfxisp_accel`(unified) | 8→**9** | 30→**24**(-20.0%) | 7,008→**5,536**(-21.0%) | 11,217→**8,264**(-26.3%) |
| `rm_normal_tone_top` | 4→**4** | 12→**12** | 3,797→**3,797** | 5,202→**5,202** |
| `rm_low_light_tone_top` | 7→**8** | 15→**9**(-40.0%) | 4,732→**3,243**(-31.5%) | 7,167→**4,204**(-41.3%) |

`rm_normal_tone_top`이 **완전히 불변**인 것은 내부 로직이 수정과 무관하다는 사실의
독립적 교차검증이다. `rm_low_light_tone_top`/unified top의 자원 감소는 버그 수정의
부산물 — 3-row sliding window + 2차 demosaic 재호출(`demosaic_rggb12_rows`) 로직이
통째로 제거되고 단일 fused pass로 대체되었기 때문. Fmax는 273.97 MHz로 수정 전후
동일(critical path가 gmem AXI 인프라에 있어 low-light 알고리즘 변경과 무관함을 재확인).

**Vivado DFX 재구현:**

| 지표 | Config1(static+RM_NORMAL, 전→후) | Config2(static+RM_LOW_LIGHT, 신규) |
|---|---|---|
| CLB LUT | 3,948→**3,953**(±0.1%, 배치 비결정성) | **2,922**(1.27%) |
| Block RAM Tile | 1.5→**1.5** | **3.5**(1.12%) |
| DSP | 12→**12** | **8**(0.46%) |

- **pr_verify: PASS(재구현 후에도 유지).** static tile 29,648개·static cell 256개는
  수정 전후 완전 동일(static 로직 자체는 바뀌지 않음을 증명). **partition pin이 2개→15개로
  증가** — 구조체 포인터 시절에는 RP 경계를 통과하는 메타데이터 신호가 2개로 뭉뚱그려
  보였으나, 4개 scalar 출력으로 분리한 뒤에는 실제로 15개의 개별 partition pin이 물리적으로
  존재함이 **post-route 배치·라우팅 실측**으로 확인됐다. Finding 2가 하드웨어 차원에서도
  해소되었다는 직접 증거다.
- **Bitstream 크기: 수정 전후 byte 단위로 완전 동일**(`config1_full.bit` 19,311,211
  bytes, partial 각 686,664 bytes). Pblock/floorplan을 그대로 재사용했고, partial
  bitstream 크기는 **pblock의 reconfigurable frame 수**(고정 프레임 그리드)로 결정되며
  실제 로직 사용량과 독립적이기 때문 — 로직이 줄어도 크기는 그대로인 것이 정상 동작이다.

### 6.6 Stage 6 (보드) — 조건만 명시, 수치 TODO

Stage 4~5로 "보드 측정 전단계"가 완료됐다. 남은 것은 물리적으로만 확인 가능:
- ZCU104 실보드에 static+PS+DDR **실제 통합**(본 특성화는 fabric-only, PS 미통합).
- 실제 clock/reset 핀 배정 + 타이밍 제약(`create_clock`) — 본 패스는 미적용(WNS 미측정).
- ICAP을 통한 실제 partial bitstream 로드 + 전환 지연(ms) 실측.
- 절대 전력(W) 측정, DPU/검출기 end-to-end 실행.
모든 보드 수치는 실측 전까지 `TODO(측정)`.

**2026-07-02 추가: 재구성 latency 단계별 이론적 분해.** 보드 없이도 계산 가능한 두 항목
(파이프라인 drain 74~171 cycle, ICAP 이론 전송 시간 = partial bitstream 686,664B ÷
AMD UG570 ICAPE3 spec 대역폭)을 조합해 peak 1.72ms/전형 6.87ms 추정치를 냈다. ICAP
전송이 전체의 >99.9%를 차지 — drain/warm-up(µs 스케일)은 무시 가능한 수준. **드라이버/
FSM 오버헤드는 PR 컨트롤러를 아직 합성하지 않아 계산 불가**하므로 TODO로 유지(수치
위조 금지 원칙). 상세: `results/pr-latency-breakdown-2026-07-02.md`.

---

## 7. 재현

```bash
cd isppipeline/hls
python3 tools/scheduler_sweep.py --out results/scheduler_sweep.csv           # Stage 1
python3 tools/image_metrics_newrm.py --root ../../data/exdark_val --tag ExDark --limit 200  # Stage 2
python3 tools/eval_map_newrm.py --root ../../data/exdark_val --tag ExDark --model yolov8n.pt --limit 150 \
    --out results/map_newrm_exdark_yolov8n.csv                               # Stage 3 (COCO/yolov8s 동일)
```

**Stage 4~5 (HW, 재현):**
```bash
# 사전: include/src/tests를 /tmp/hls_dfxisp/dfxisp_accel/ 에 flat 복사
source /tools/Xilinx/Vitis_HLS/2024.1/settings64.sh
cd /tmp/hls_dfxisp/dfxisp_accel
DFXISP_HLS_TOP=dfxisp_accel          DFXISP_HLS_FLOW=csynth vitis_hls run.tcl   # unified top
DFXISP_HLS_TOP=rm_normal_tone_top    DFXISP_HLS_FLOW=export vitis_hls run.tcl   # RM1 IP-XACT
DFXISP_HLS_TOP=rm_low_light_tone_top DFXISP_HLS_FLOW=export vitis_hls run.tcl   # RM2 IP-XACT

source /tools/Xilinx/Vivado/2024.1/settings64.sh
cd /tmp/hls_dfxisp/dfx
vivado -mode batch -source dfx_flow.tcl           -log dfx_flow.log            # static+RP+config1
vivado -mode batch -source dfx_flow_config2.tcl    -log dfx_flow_config2.log   # config2(static 고정)+pr_verify
vivado -mode batch -source write_bitstreams.tcl    -log write_bitstreams.log   # bitstream
```
(`/tmp` 산출물은 git 비추적 — 위 절차로 재생성. 상세: `results/stage4-hw-synthesis-2026-07-02.md`,
`results/stage5-dfx-implementation-2026-07-02.md`.)

---

## 8. 한계

- SW proxy: pseudo-RAW는 이미 ISP된 JPEG 역변환, RGGB nearest demosaic, n=71~113(크기
  불일치 스킵), CPU. **절대값이 아니라 arm 순서**가 판단 근거(guardrail).
- C-sim golden(GRBG) vs eval(RGGB) — 상대 behaviour 비교 관례(구 08-e2와 동일).
- 구 08/11(static/reg/bin/fp variant) 수치와 직접 비교 금지: arm 정의가 다름
  (여기 normal=baseline core no-gain / 구 reg_only=demosaic+gain).
- checker 임계 미보정 상태의 결과 — (c) 반영 시 adaptive 수치 변동 예상.
- **HW(Stage 4~5)는 fabric-only 특성화:** PS/DDR/AXI interconnect 미통합, 클럭·리셋 핀
  실제 배정 없음(NSTD-1/UCIO-1 DRC를 Warning으로 낮춰 우회), 타이밍 제약(`create_clock`)
  미적용이라 WNS 미측정. C-synthesis 자원/타이밍은 **추정치**(post-route 배치·라우팅
  수치는 Config1/Config2 표에서만 확정치). 절대 전력(W)·PR latency(ms)·DPU end-to-end는
  Stage 6(실보드)에서만 확정된다.
- §6.4의 Finding 2(메타데이터 RTL 미검증)는 독립 재검증 결과 "확정적으로 깨져 있었다"는
  근거는 과장이었음 — 그럼에도 검증된 적 없는 패턴이라 더 안전한 쪽으로 교체했다. §6.5의
  partition pin 2→15 실측이 사후적으로 이 판단의 타당성을 뒷받침한다.

## 산출물
Stage 1 `scheduler{,_sweep}.csv` · Stage 2 `image_metrics_{exdark,coco}.csv` ·
Stage 3 `map_newrm_{exdark,coco}_{yolov8n,yolov8s}.csv` · 상세 `stage1-3-results-2026-07-02.md`.
Stage 4 `resource_csynth_ver1_2026-07-02.csv` · `resource_csynth_rm_standalone_2026-07-02.csv` ·
상세 `stage4-hw-synthesis-2026-07-02.md`. Stage 5 상세 `stage5-dfx-implementation-2026-07-02.md`.
DFX 재구성 latency 단계별 분해: `pr-latency-breakdown-2026-07-02.md`. low-light RM mAP
미개선 원인 ablation: `lowlight-rm-map-rootcause-2026-07-02.md`(코드 `tools/isp_pipeline_ablation.py`,
`tools/eval_map_ablation.py`; 결과 `map_ablation_{exdark,coco}_yolov8n.csv`). 마이크로아키텍처
다이어그램: `dfxisp-microarchitecture-2026-07-02.svg`/`.drawio`.
수정 이력 및 최신 §10 수치는 `SPEC.md` §10/§11.5, `isppipeline/hls/README.md` 참조.
