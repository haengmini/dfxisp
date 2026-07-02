---
type: spec
title: "DFXISP 시스템 사양서 (입력 데이터셋 → 출력)"
project: DFXISP
version: 1.0
created: 2026-07-02
target: Zynq UltraScale+ ZCU104 / XCZU7EV (xczu7ev-ffvc1156-2-e)
status: active — reset 아키텍처(shared baseline core + 상호배타 tone RM slot)
refs: "README.md · RESEARCH.md · isppipeline/hls · results/experiment-report-2026-07-02.md"
---

# DFXISP 시스템 사양서

> 입력(pseudo-RAW 데이터셋) → checker → tone RM slot → baseline ISP core → RGB32 출력 →
> 검출기/mAP 까지 전 구간의 데이터 포맷·산술·인터페이스·파라미터를 정의한다.
> 정본 아키텍처는 `RESEARCH.md`, 구현은 `isppipeline/hls/`. 모든 산술은 **정수(bit-exact)**.

---

## 0. 범위와 두 도메인 구분

DFXISP는 두 실행 도메인을 가지며, **입력 Bayer 포맷이 다르다**(중요):

| 도메인 | 목적 | 입력 RAW | demosaic | 정본 |
|---|---|---|---|---|
| **HW / C-sim** | 하드웨어 경로·bit-exact 검증 | pseudo-RAW **GRBG**, 12-bit in uint16 | GRBG 3x3 | `src/dfxisp_accel.cpp` ↔ `tools/gen_golden_vectors.py` |
| **SW eval** | 데이터셋 규모 mAP/지표 | 데이터셋 pseudo-RAW **RGGB16**(shift8) | RGGB nearest | `tools/newrm_pipeline.py` |

두 도메인은 동일한 아키텍처 의미(baseline core + tone RM slot)를 구현하되, 데이터셋 레이아웃
차이로 demosaic 종류가 다르다. 판단 근거는 **arm 간 상대 순서**이며 절대 bit-exact는 HW 도메인
내부에서만 보장된다.

---

## 1. 시스템 개요 (end-to-end)

```text
[입력 데이터셋]                    [DFXISP 파이프라인]                         [출력/평가]
 pseudo-RAW Bayer  ──▶  ① Scene checker (mode 결정: dark_ratio + hysteresis)
 (raw_bin / fixture)          │
 + labels(COCO-80)            ├─ NORMAL  ─▶ RM_NORMAL_TONE(identity)
                              │                 └─▶ ② baseline ISP core
                              │                       (demosaic+BLC+AWB+CCM, gain/gamma 없음)
                              │                       └─▶ RGB32 (H×W)
                              │
                              └─ LOW_LIGHT ─▶ ③ RM_LOW_LIGHT_TONE.front(2x2 RAW binning)
                                                └─▶ ② baseline ISP core
                                                     └─▶ ③ RM_LOW_LIGHT_TONE.back(gain+gamma4)
                                                          └─▶ RGB32 (H/2 × W/2, Policy A)
                                                                       │
                                     ④ 메타데이터 DfxIspResult ─────────┤
                                        {out_w,out_h,selected_mode,selected_rm}
                                                                       ▼
                                                        packed RGB888 0x00RRGGBB
                                                        ─▶ DPU / detector(YOLO·SSD) ─▶ mAP
```

**불변식:** 프레임당 tone RM 정확히 1개(상호배타); gain/gamma는 tone RM에만 존재(baseline core
중복 없음); 출력 메타데이터가 mode·RM·형상을 보고. (C-sim gate로 자동 검증)

---

## 2. 입력 사양

### 2.1 데이터셋 구성
| 데이터셋 | 조도 | 경로 | 이미지 수 | 유효(raw==jpg) |
|---|---|---|---|---|
| COCO_val | 정상 | `data/coco_val/` | 575 | 347 |
| ExDark_val | 저조도 | `data/exdark_val/` | 491 | 260 |

각 데이터셋은 `raw_bin/`(pseudo-RAW), `images/`(해상도 출처 jpg), `labels/`(YOLO txt)로 구성.
`raw_bin` 크기가 jpg 해상도와 불일치하는 프레임은 스킵(유효 프레임만 사용).

### 2.2 raw_bin 포맷 (SW eval 입력)
- **레이아웃:** RGGB Bayer. `(0,0)=R (0,1)=G (1,0)=G (1,1)=B`.
- **자료형:** headerless little-endian `uint16` 배열, 길이 = `W*H`(행 우선).
- **스케일:** 값은 8-bit를 상위로 shift한 형태(`유효8bit = value >> 8`, `SHIFT=8`). 범위 0~65280.
- **해상도(W,H):** 동명 `images/<stem>.jpg`의 SOF 마커에서 파싱.

### 2.3 HW / C-sim 입력 포맷 (정본 하드웨어 경로)
- **레이아웃:** GRBG Bayer.
- **자료형:** 12-bit 값을 `uint16`에 저장(`raw12_to_u8(v) = min(v,4095) >> 4`).
- **fixture:** 합성 grid 프레임(`gen_golden_vectors.py`), 시나리오 `NORMAL×3 → LOW_LIGHT×3 →
  NORMAL×1` + threshold-boundary + bright-recovery + odd-dimension.

### 2.4 라벨 포맷
- YOLO txt: 한 줄 `class cx cy w h` (정규화 0~1, 이미지 크기 무관).
- **클래스 id:** 두 데이터셋 모두 **COCO-80 id** `{0,1,2,3,5,8,15,16,39,41,56,60}` (12클래스).
  → detector가 COCO 사전학습이므로 **remap 불필요**.

### 2.5 입력 해상도 분포 (측정)
| 데이터셋 | width min/median/max | height min/median/max | 대표 크기 |
|---|---|---|---|
| ExDark | 200 / 640 / 3200 | 178 / 499 / 3443 | 640×480, 640×427, 500×375 |
| COCO | 240 / 640 / 640 | 160 / 480 / 640 | 640×480, 640×427, 480×640 |
가변 해상도(고정 아님). RESEARCH의 1280×720@30fps는 HW 프레임예산 목표치이며 SW 데이터셋 입력과 별개.

---

## 3. 파이프라인 스테이지 사양

### 3.1 ① Scene checker / mode decision (static region)
입력 mode ∈ {NORMAL(0), LOW_LIGHT(1), AUTO(2)}.

```text
NORMAL     -> selected_mode = NORMAL
LOW_LIGHT  -> selected_mode = LOW_LIGHT
AUTO       -> dark_ratio = count(dark) / (W*H)
              HW/C-sim: dark = (raw < dark_pixel_threshold)          # RAW 도메인
              SW eval : dark = (Y < 50),  Y = (R + 2G + B) / 4        # 8-bit 휘도
              selected_mode = LOW_LIGHT  if  dark_ratio > 0.40  else NORMAL
              (정수 비교: dark_count*100 > 40*(W*H))
```
- **히스테리시스(시퀀스 레벨):** 단일 프레임 entry에는 없음. 장면 단위 안정화(N 안정프레임,
  히스테리시스 밴드, min-dwell)는 스케줄러(`tools/scheduler_sim.py`/`scheduler_sweep.py`)가 담당.
  권장 파라미터(실측): narrow 밴드 + temporal_N=3 (mismatch 0.015, thrashing 0).

### 3.2 ② Baseline ISP core (shared, static, mode 무관)
**gain/gamma 없음.** 입력(선택된 tone RM 출력 또는 raw)에 대해 픽셀당:

```text
1. demosaic
     HW/C-sim: GRBG 3x3 window -> R,G,B (raw12_to_u8: >>4)
     SW eval : RGGB nearest    -> R,G,B (>>8)
2. BLC   : v' = clip(v - 16, 0, 255)                      # black-level
3. AWB   : R = clip(R' * 286 / 256, 0, 255)               # Q8 채널 color calibration
           G = clip(G' * 256 / 256, 0, 255)
           B = clip(B' * 307 / 256, 0, 255)
4. CCM   : identity (placeholder, Q8 scale 256)           # 구조 유지, 색변환 없음
```

### 3.3 ③ Tone RM slot (상호배타, reconfigurable)
tone RM slot이 baseline core를 **감싼다**(front/back).

**RM_NORMAL_TONE (NORMAL):** identity bypass. 출력 = baseline_core(raw), 형상 H×W.
(계획된 개정: identity 대신 register gain — §11 참조.)

**RM_LOW_LIGHT_TONE (LOW_LIGHT), Policy A:**
```text
front (RAW):  2x2 binning
    HW/C-sim: binned(bx,by) = (p00+p01+p10+p11)/4  over GRBG raw  -> (W/2, H/2)
    SW eval : R=cell TL, G=(TR+BL)/2, B=cell BR     over RGGB raw -> (W/2, H/2)
core       :  baseline_isp_core(binned)                            # 위 §3.2
back (tone):  gain  : v = clip(v * 5 / 4, 0, 255)                   # 1.25x 노출
              gamma : v = gamma4(v)                                 # γ=4.0
출력 형상   :  H/2 × W/2   (bin_dim(d) = max(1, d/2))
```
- **gamma4(v)** = `floor((255^3 · v)^(1/4))` = `isqrt(isqrt(16581375 · v))` (정수 4제곱근,
  Python `math.isqrt`와 C++ 동일 → bit-exact, 부동소수 없음). gamma4(0)=0, gamma4(255)=255.

### 3.4 데이터 흐름 순서 결정
tone RM이 core를 감싸는 순서로 확정(2026-07-01): 저조도 binning은 **RAW에서 precision loss 전**에
수행하고, gain/gamma는 8-bit tone으로 core 뒤에 둔다(RESEARCH §4.2). de-dup 불변식 유지.

---

## 4. 파라미터 표 (전체 상수, 정수)

| 스테이지 | 파라미터 | 값 | 비고 |
|---|---|---|---|
| checker | DARK_Y (SW) | 50 | Y<50 = dark 픽셀 |
| checker | DARK_RATIO | 0.40 | AUTO→LOW_LIGHT 임계 |
| baseline core | BLC_OFFSET | 16 | black-level |
| baseline core | AWB_R / G / B | 286 / 256 / 307 | Q8(/256) color cal |
| baseline core | CCM | identity(256) | placeholder |
| low-light tone | LL_GAIN | 5/4 (1.25×) | 노출 게인 |
| low-light tone | GAMMA | γ=4.0 | `(255^3·v)^(1/4)` |
| raw 변환 | SHIFT (SW) | 8 | 16→8 bit |
| raw 변환 | raw12_to_u8 (HW) | `>>4` | 12→8 bit |
| 형상 | bin_dim | `max(1, d/2)` | Policy A |

> 계획된 개정(Stage 1~3 실측 반영): normal RM=register gain, low-light γ≈2.5~3.0/Policy B,
> checker dark-level 재보정. §11 참조.

---

## 5. 출력 사양

### 5.1 픽셀 포맷
- **packed RGB888**, `uint32`, `0x00RRGGBB` = `[31:24]=0x00, [23:16]=R, [15:8]=G, [7:0]=B`.
- AXI DMA 정합을 위해 24-bit가 아닌 32-bit 패킹(2의 거듭제곱 폭).

### 5.2 형상 정책 (Policy A, shape-changing)
| mode | 출력 형상 |
|---|---|
| NORMAL | H × W (입력과 동일) |
| LOW_LIGHT | ⌊H/2⌋ × ⌊W/2⌋ (min 1) |
- `rgb_out` 버퍼 용량 ≥ `W*H` (저조도는 그 이하만 사용).
- (Policy B = upsample/pad로 H×W 복원은 DPU 고정 ABI가 필요할 때만; §11 미래.)

### 5.3 출력 메타데이터
```c
struct DfxIspResult {
    int out_width;      // 실제 출력 폭
    int out_height;     // 실제 출력 높이
    int selected_mode;  // 0=NORMAL, 1=LOW_LIGHT (AUTO 해소값)
    int selected_rm;    // 0=RM_NORMAL_TONE, 1=RM_LOW_LIGHT_TONE
};
```
HW에서는 AXI-Lite 레지스터로 노출; DPU 전단이 출력 크기/모드를 알 수 있어야 함.

---

## 6. 인터페이스 사양

### 6.1 HLS top 함수
```c
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,     // 입력 pseudo-RAW GRBG (W*H)
    uint32_t*       rgb_out,       // 출력 RGB32 (용량 >= W*H)
    int             width,
    int             height,
    int             mode,          // DfxIspMode
    uint16_t        dark_pixel_threshold,  // AUTO checker RAW 임계
    DfxIspResult*   result);       // 출력 메타데이터
```
AXI: `raw_bayer`/`rgb_out` = `m_axi`(gmem0/gmem1); 스칼라·`result`·`return` = `s_axilite`(control).

### 6.2 Golden vector CSV 포맷 (검증 계약)
헤더: `case,in_w,in_h,mode,threshold,out_w,out_h,sel_mode,sel_rm,kind,idx,val`
- 케이스별 메타데이터 반복 + `kind=raw`(입력 RAW, val=10진) / `kind=rgb`(기대 출력, val=`0xRRGGBB`).
- 입력 픽셀 수(in_w×in_h)와 출력 픽셀 수(out_w×out_h)가 다를 수 있어 행을 분리.

---

## 7. 하드웨어 / DFX 사양

| 항목 | 값 |
|---|---|
| 타깃 디바이스 | ZCU104, `xczu7ev-ffvc1156-2-e` |
| 합성 도구 | Vitis HLS 2024.1 |
| 클럭 타깃 | 5.0 ns (200 MHz) |
| static region | AXI/control wrapper, checker/mode FSM, baseline ISP core, DFX/PR controller, output/metadata packer |
| RM slot(재구성) | RM_NORMAL_TONE / RM_LOW_LIGHT_TONE (상호배타, 동일 downstream 계약 또는 shape 메타 노출) |
| 전환 정책 | 장면 단위(프레임 단위 아님), 히스테리시스 checker |
| 재구성 지연 | partial bitstream ÷ ICAP 대역폭 (TODO 측정) |

**실험 arm:** Arm1(static baseline+normal tone) / Arm2(register-only 적응, DFX 없음) /
Arm3(DFX가 tone RM slot 교체). ablation: post-RGB8 gain/lift, dfx_bin, dfx_fp(`dfxisp_rm.*`).

---

## 8. 검증 사양 (bit-exact 전파 체인)

| Lv | 대상 | 도구 | 상태 |
|---|---|---|---|
| L0 | Python golden(기준) | `gen_golden_vectors.py` | ✅ |
| L1 | HLS C-sim (C++==Python) | `make verify` | ✅ 566px bit-exact |
| L2 | C/RTL Co-sim (합성 RTL==C TB) | `DFXISP_HLS_FLOW=cosim make hls` | ⬜ |
| L3 | RTL wrapper sim (AXI-Stream) | Vivado xsim | ⬜ |
| L4 | DFX 멀티프레임 전환 sim | RTL TB | ⬜ |
| L5 | 보드 HIL (실제 PR) | ZCU104 | ⬜ |

**아키텍처 gate(전부 PASS, `reports/latest.md`):** baseline core bit-exact / RM_NORMAL_TONE /
RM_LOW_LIGHT_TONE / 상호배타 RM 선택 / gain·gamma 중복 없음 / 형상정책(LOW_LIGHT H/2×W/2).

---

## 9. 평가 사양 (검출 정확도)

- **검출기:** YOLOv8n, YOLOv8s(ultralytics `val`, imgsz=640, mAP@[.5:.95]·@50),
  SSDLite-MobileNetV3(torchvision, COCOeval) 교차검증. 정확한 Vitis-AI `tf_ssdmobilenetv1`은
  가중치 부재·TF1.15로 이 환경 실행 불가 → **보드 DPU end-to-end 단계**용.
- **조건표 A~G:** ExDark{A none, B normal, C lowlight} / COCO{D none, E normal, F lowlight} /
  G adaptive(checker 프레임별 선택).
- **주지표:** mAP@[.5:.95] (0~1 분수, ×100=%). 판단 근거 = **arm 순서**(guardrail).

---

## 10. 성능 / 자원 목표 (TODO 측정)

| 지표 | Arm1 | Arm2 | Arm3(DFX) |
|---|---|---|---|
| LUT/FF/BRAM/DSP | TODO | TODO | TODO |
| Fmax @5.0ns | TODO | TODO | TODO |
| partial bitstream size | — | — | TODO |
| 재구성 지연(ms) | — | — | TODO |
| 정상모드 전력(W) | TODO | TODO | TODO |
기대(H3): 정상모드에서 Arm3 fabric/전력 < Arm2(저조도 블록 미상주).

---

## 11. 제약 · 가정 · 알려진 이슈

1. **SW eval은 proxy:** pseudo-RAW는 이미 ISP된 JPEG 역변환, RGGB nearest, n=71~113, CPU.
   절대값 아닌 arm 순서가 판단 근거.
2. **HW(GRBG) vs SW(RGGB) demosaic 차이:** 상대 behaviour 비교 관례.
3. **Stage 1~3 실측 발견(중요):** 현재 tone RM(normal=identity, low-light=bin+gain+gamma-4.0,
   Policy A)은 세 detector·두 데이터셋 모두에서 **무처리(none)보다 mAP 낮음** = mAP guardrail 탈락.
   → 방향 A와 정합(mAP는 최소/register 처리, DFX/RM은 자원·전력으로 정당화).
   **계획된 사양 개정:** (a) RM_NORMAL_TONE = register gain, (b) low-light γ 완화·Policy B·denoise,
   (c) checker dark-level 재보정 → 개정 후 재측정으로 guardrail 재판정.
4. **HW 수치 위조 금지:** Vivado/보드 없이 §10·L2~L5 수치를 만들지 않음(TODO 유지).

---

## 12. 용어

| 용어 | 의미 |
|---|---|
| DFX / DPR | Dynamic Function eXchange / 부분 재구성 |
| RM | Reconfigurable Module(부분 비트스트림 교체 단위) |
| tone RM slot | gain/gamma/binning을 담는 상호배타 재구성 영역 |
| baseline ISP core | demosaic+BLC+AWB+CCM 공통 후단(정확히는 tone에 감싸임), gain/gamma 없음 |
| Policy A / B | 형상변경(H/2×W/2) / 형상보존(upsample-pad) |
| guardrail | mAP가 기준선(예: none/register-only) 이상이어야 RM 채택 |
| arm | 실험 비교군(static / register-only / DFX / ablation) |
```

문서 끝 — 변경 시 `RESEARCH.md`·`src/dfxisp_accel.cpp`·`tools/*`와 동기 유지.
