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

DFXISP는 두 실행 도메인을 가진다. **Bayer 패턴은 RGGB로 통일**(2026-07-02)되었고, 남은 차이는
RAW 비트 표현뿐이다:

| 도메인 | 목적 | 입력 RAW | demosaic | 정본 |
|---|---|---|---|---|
| **HW / C-sim** | 하드웨어 경로·bit-exact 검증 | pseudo-RAW **RGGB**, 12-bit in uint16 (`>>4`) | RGGB 3x3 | `src/dfxisp_accel.cpp` ↔ `tools/gen_golden_vectors.py` |
| **SW eval** | 데이터셋 규모 mAP/지표 | 데이터셋 pseudo-RAW **RGGB16**(shift8, `>>8`) | RGGB nearest | `tools/newrm_pipeline.py` |

두 도메인은 이제 **같은 Bayer 규약(RGGB)**을 쓴다(2026-07-02 통일: C-sim GRBG→RGGB). 남은 차이는
RAW 비트 표현(HW 12-bit vs SW 8-bit shift8)뿐이며, 이로 인해 데이터셋 raw를 C-sim/HW에 직접
흘려 end-to-end bit 대조하는 것이 향후 가능해진다. 절대 bit-exact는 HW 도메인 내부(합성 fixture)에서
보장되고, SW mAP는 **arm 간 상대 순서**로 판단한다.

---

## 1. 시스템 개요 (end-to-end)

```text
[입력 데이터셋]                    [DFXISP 파이프라인]                         [출력/평가]
 pseudo-RAW Bayer  ──▶  ① Scene checker (mode 결정: dark_ratio + hysteresis)
 (raw_bin / fixture)          │
 + labels(COCO-80)            ├─ NORMAL  ─▶ ② baseline core12 (demosaic+BLC+WB+CCM, 12-bit)
                              │                 └─▶ ③ RM_NORMAL_TONE (gain 1.25× + gamma2.0)
                              │                       └─▶ RGB32 (H×W)
                              │
                              └─ LOW_LIGHT ─▶ ③ RM_LOW_LIGHT_TONE.front(2x2 RAW binning-demosaic,
                                                  융합: R=TL·G=avg(TR,BL)·B=BR, 채널 보존)
                                                └─▶ ② baseline core12 (BLC+WB+CCM, 12-bit, demosaic 재실행 없음)
                                                     └─▶ ③ RM_LOW_LIGHT_TONE.back(gain 2.0× + gamma2.0)
                                                          └─▶ RGB32 (H/2 × W/2, Policy A)
                                                                       │
                              ④ 메타데이터(4개 scalar 출력 포인터) ─────┤
                                 out_w, out_h, selected_mode, selected_rm
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
- **레이아웃:** RGGB Bayer (SW 데이터셋과 통일, 2026-07-02).
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
              selected_mode = LOW_LIGHT  if  dark_ratio > 0.80  else NORMAL
              (정수 비교: dark_count*100 > 80*(W*H))
```
- **임계 재보정(2026-07-02, ver2):** 기존 0.40은 Youden's J 관점에서 사실상 미분류(ExDark
  recall=1.00이지만 COCO false-trigger=0.80 — 정상조도도 거의 다 저조도로 오판). 실측
  데이터셋(`data/{coco_val,exdark_val}`)에서 임계를 스윕한 결과 **0.80이 근사 최적**
  (recall=0.90, false-trigger=0.11, J=0.79; J-max는 0.83에서 0.80). 상세: `results/experiment_ver2_2026-07-02.md`.
- **히스테리시스(시퀀스 레벨):** 단일 프레임 entry에는 없음. 장면 단위 안정화(N 안정프레임,
  히스테리시스 밴드, min-dwell)는 스케줄러(`tools/scheduler_sim.py`/`scheduler_sweep.py`)가 담당.
  권장 파라미터(실측): narrow 밴드 + temporal_N=3 (mismatch 0.015, thrashing 0).

### 3.2 ② Baseline ISP core (shared, static, mode 무관) — ver1
**gain/gamma 없음.** 보정을 **12-bit RAW 도메인에서 수행**하고 최종 `>>4`는 tone에서 한다
(ver1 핵심: precision 보존). 픽셀당:

```text
1. demosaic (RGGB) -> R,G,B 12-bit (0..4095)     # HW/C-sim: >>4 안 함(여기선 유지)
2. BLC   : v = clip(v - 256, 0, 4095)            # 12-bit black-level (16<<4)
3. WB    : R = clip(R * 286 / 256, 0, 4095)      # Q8 채널 white balance(color)
           G = clip(G * 256 / 256, 0, 4095)
           B = clip(B * 307 / 256, 0, 4095)
4. CCM   : identity                              # 구조 유지, 색변환 없음
반환      : R,G,B 12-bit  (>>4 및 gamma는 tone RM에서)
```
> SW eval proxy(`isp_pipeline_ver1.py`)는 8-bit 도메인(>>8) + float γ LUT를 쓰는 근사이며,
> HW/C-sim이 정본(12-bit, 정수 γ). 상세 §0.

### 3.3 ③ Tone RM slot (상호배타, reconfigurable) — ver1
tone RM slot이 baseline core를 **감싼다**(front/back). tone = exposure gain(12-bit) → `>>4` → gamma.

```text
tone(v12, gnum, gden) = gamma2( clip(v12*gnum/gden, 0, 4095) >> 4 )
gamma2(v8) = floor(sqrt(255 * v8)) = isqrt(255*v8)     # γ=2.0, 정수 exact, bit-exact
```

**RM_NORMAL_TONE (NORMAL):** gain **1.25×**(5/4) + gamma2.0. 형상 H×W. (ver1: identity → gain+gamma)

**RM_LOW_LIGHT_TONE (LOW_LIGHT), Policy A:**
```text
front (RAW):  2x2 RAW binning-demosaic, 융합(fused) — R=top-left, G=avg(top-right,
              bottom-left), B=bottom-right  -> (W/2, H/2) R,G,B triple
core       :  apply_blc_wb12(front 출력)                        # 위 §3.2, demosaic 재실행 없음
back (tone):  gain **2.0×**(2/1) + gamma2.0
출력 형상   :  H/2 × W/2   (bin_dim(d) = max(1, d/2))
```
**주의(2026-07-02 수정):** 이전엔 4개 샘플을 `(p00+p01+p10+p11)/4` 스칼라 하나로 평균한 뒤
그 값을 다시 Bayer인 것처럼 demosaic — 색 정보가 이미 파괴된 뒤라 사실상 흑백에 가까운
출력이 나오는 버그였다(adversarial review로 발견). 채널별 정체성을 보존하는 위 방식으로
수정(`tools/isp_pipeline_ver1.py`의 `_bin_demosaic_rggb16`과 bit-exact 일치).

### 3.4 데이터 흐름 순서 결정 (ver1)
ver1(2026-07-02): 보정(BLC/WB)을 **demosaic 직후 12-bit에서** 수행(선형이라 RAW-domain과 동치,
최종 `>>4` 전까지 정밀도 보존). 저조도 binning은 **RAW에서 precision loss 전**에, gain·gamma는
tone RM(core 뒤)에 둔다(RESEARCH §4.2). de-dup 불변식 유지(gain/gamma는 tone RM에만).

---

## 4. 파라미터 표 (전체 상수, 정수)

| 스테이지 | 파라미터 | 값 | 비고 |
|---|---|---|---|
| checker | DARK_Y (SW) | 50 | Y<50 = dark 픽셀 |
| checker | DARK_RATIO | **0.80**(재보정 2026-07-02, 구 0.40) | AUTO→LOW_LIGHT 임계 |
| baseline core | BLC_OFFSET12 | 256 (=16<<4) | 12-bit black-level |
| baseline core | AWB_R / G / B | 286 / 256 / 307 | Q8(/256) white balance |
| baseline core | CCM | identity(256) | placeholder |
| normal tone | GAIN_NORMAL | 5/4 (1.25×) | 노출 게인 (ver1 추가) |
| low-light tone | GAIN_LOWLIGHT | 2/1 (2.0×) | 노출 게인 |
| tone (공통) | GAMMA | γ=2.0 | `floor(sqrt(255·v))` = isqrt, 정수 exact |
| raw 변환 | RAW12_MAX / `>>4` (HW) | 4095 / 12→8 bit | tone에서 >>4 |
| raw 변환 | SHIFT (SW proxy) | 8 | 16→8 bit |
| 형상 | bin_dim | `max(1, d/2)` | Policy A |

> ver1(2026-07-02) 반영 완료: 보정 12-bit RAW-domain, normal에 gain+gamma, low-light γ4.0→2.0(완화).
> SW proxy(`isp_pipeline_ver1.py`)는 float γ2.2/2.5·8-bit 근사(정본은 HW 정수 γ2.0).

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
**4개 개별 scalar 출력 포인터**(2026-07-02 수정, 아래 §6.1 참조):
`out_width`(실제 출력 폭) · `out_height`(실제 출력 높이) · `selected_mode`(0=NORMAL,
1=LOW_LIGHT, AUTO 해소값) · `selected_rm`(0=RM_NORMAL_TONE, 1=RM_LOW_LIGHT_TONE).
HW에서는 각각 AXI-Lite read-back 레지스터로 노출; DPU 전단이 출력 크기/모드를 알 수 있어야 함.

> **이전 설계(구조체 포인터, adversarial review로 폐기):** `DfxIspResult*` 구조체 하나를
> `s_axilite`로 선언했었으나, s_axilite는 slave-only 제어 인터페이스라 구조체 필드 write-back이
> 실제로 합성되는지 어떤 산출물로도 검증되지 않았다(cosim도 미완주). 개별 scalar 포인터로
> 교체 — 완료 후 read-back되는 정형화된(well-established) Vitis HLS 패턴이라 신뢰도가 높다.

---

## 6. 인터페이스 사양

### 6.1 HLS top 함수
```c
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,     // 입력 pseudo-RAW RGGB (W*H)
    uint32_t*       rgb_out,       // 출력 RGB32 (용량 >= W*H)
    int             width,
    int             height,
    int             mode,          // DfxIspMode
    uint16_t        dark_pixel_threshold,  // AUTO checker RAW 임계
    int*            out_width,     // 출력 메타데이터 (개별 scalar 포인터)
    int*            out_height,
    int*            selected_mode,
    int*            selected_rm);
```
AXI: `raw_bayer`/`rgb_out` = `m_axi`(gmem0/gmem1); 나머지 스칼라 인자·메타데이터 출력 4종·
`return` = `s_axilite`(control).

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
| 재구성 지연 | drain+ICAP+warm-up 이론적 분해: **peak 1.72 ms / 전형 6.87 ms**(스펙 유도, 보드 미실측). 상세 `results/pr-latency-breakdown-2026-07-02.md`. 드라이버/FSM 오버헤드는 TODO(보드) |

**실험 arm:** Arm1(static baseline+normal tone) / Arm2(register-only 적응, DFX 없음) /
Arm3(DFX가 tone RM slot 교체). ablation: post-RGB8 gain/lift, dfx_bin, dfx_fp(`dfxisp_rm.*`).

---

## 8. 검증 사양 (bit-exact 전파 체인)

| Lv | 대상 | 도구 | 상태 |
|---|---|---|---|
| L0 | Python golden(기준) | `gen_golden_vectors.py` | ✅ |
| L1 | HLS C-sim (C++==Python) | `make verify` | ✅ 646px bit-exact |
| L1.5 | C-synthesis(실제 Vitis HLS) | `DFXISP_HLS_FLOW=csynth` | ✅ 실측(§10) |
| L2 | C/RTL Co-sim (합성 RTL==C TB) | `DFXISP_HLS_FLOW=cosim` | 🟡 RTL 실행 성공(7/7 트랜잭션), 자동 bit-exact 비교는 툴 하네스 SIGSEGV로 미완주(`results/stage4-hw-synthesis-2026-07-02.md` §6b) |
| L3 | RTL wrapper sim (AXI-Stream) | Vivado xsim | ⬜ |
| **L4** | **DFX 구현·pr_verify(fabric-only, non-project batch flow)** | **Vivado 2024.1** | **✅ pr_verify PASS, 실제 partial bitstream 생성**(`results/stage5-dfx-implementation-2026-07-02.md`) |
| L5 | 보드 HIL (실제 PR, PS/DDR 통합, 전력·PR latency 실측) | ZCU104 | ⬜ 유일하게 남은 단계 |

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

## 10. 성능 / 자원 (Stage 4 실측, 2026-07-02 — Vitis HLS 2024.1 C-synthesis)

**실측 완료(C-synthesis + 실제 Vivado DFX 구현, xczu7ev, 2024.1) — 2026-07-02 20:33 KST
adversarial-review 수정(chroma-preserving binning-demosaic + scalar 메타데이터 포인터,
커밋 `a2d1b6d`) 반영 재합성.** unified top (`dfxisp_accel`, 두 tone RM 모두 상주·런타임
mode 선택, DFX 없음)은 **Arm2(register-only)**. RM_NORMAL_TONE/RM_LOW_LIGHT_TONE을 실제
Reconfigurable Partition으로 재구현·**pr_verify PASS**·partial bitstream 재생성까지
완료해 **Arm3(DFX) fabric-only 실측**을 확보(PS/DDR 미통합, 절대 전력·PR latency(ms)는
보드 전용). Arm1(정적 baseline-only)은 여전히 TODO.
상세: `results/stage4-hw-synthesis-2026-07-02.md`(csynth), `results/stage5-dfx-implementation-2026-07-02.md`(DFX 구현).

| 지표 | Arm1(static) | **Arm2(register-only, 실측)** | **Arm3(DFX, 실측)** |
|---|---|---|---|
| LUT / FF / BRAM / DSP | TODO | **8,264 / 5,536 / 9 / 24** | config1(static+RM_NORMAL) routed: LUT 3,953/BRAM 1.5tile/DSP 12; config2(static+RM_LOW_LIGHT) routed: LUT 2,922/BRAM 3.5tile/DSP 8(§Stage5) |
| Fmax @5.0ns | TODO | **273.97 MHz**(critical path 3.650ns, 수정 전후 동일) | TODO(제약 미인가 fabric-only 패스, WNS 미측정) |
| pr_verify | — | — | **✅ PASS**(config 간 static 완전 동일 확인, partition pin 15개) |
| full bitstream size | — | — | **19,311,211 bytes ≈ 19.3 MB**(수정 전후 byte 단위 동일) |
| partial bitstream size | — | — | **686,664 bytes ≈ 671 KB**(두 RM 동일, pblock 프레임 수로 결정, 수정 전후 동일) |
| 재구성 지연(ms) | — | — | 이론적 분해 peak 1.72ms/전형 6.87ms(`results/pr-latency-breakdown-2026-07-02.md`); 드라이버/FSM 포함 실측은 TODO(보드) |
| 정상모드 전력(W) | TODO | TODO | TODO(보드 실측 필요) |

Arm2 인스턴스 분해(unified top 내부, DFX 순이득 추정의 참조점, 재합성 후):

| instance | BRAM | DSP | FF | LUT |
|---|---|---|---|---|
| RM_NORMAL_TONE(`run_normal`) | 1 | 12 | 1,785 | 3,108 |
| RM_LOW_LIGHT_TONE(`run_low_light`) | 5 | 9 | 1,295 | 2,110 |
| AXI/제어 인프라 | 3 | 3 | 2,456 | 3,046 |

**활용률(xczu7ev 대비):** BRAM 1%, DSP 1%, FF 1%, LUT 4% — 매우 여유 있음.

기대(H3): 정상모드에서 Arm3 fabric/전력 < Arm2(저조도 블록 미상주). `run_low_light`
인스턴스(5 BRAM/9 DSP/1,295 FF/2,110 LUT — 버그 수정으로 구 수치 대비 대폭 축소)가 DFX로
제거 가능한 상한 추정치 — Arm1/Arm3 확정에는 정적 baseline-only top 분리 합성과 Vivado DFX
플로어플랜(PR/pr_verify/partial bitstream)이 필요.

**RM 독립 top 실측(Stage 5 준비, 재합성 후):** `RM_NORMAL_TONE`/`RM_LOW_LIGHT_TONE`을
각자 자체 AXI 인프라를 가진 독립 top으로 분리 합성(DFX partial bitstream 크기의 더 현실적
추정치):

| top | BRAM | DSP | FF | LUT | Fmax |
|---|---|---|---|---|---|
| `rm_normal_tone_top` | 4 | 12 | 3,797 | 5,202 | 273.97 MHz |
| `rm_low_light_tone_top` | 8 | 9 | 3,243 | 4,204 | 273.97 MHz |

`rm_normal_tone_top`은 수정으로 내부 로직이 바뀌지 않아 이전 실측치와 완전히 동일(교차검증).
`rm_low_light_tone_top`은 2차 demosaic 재호출 제거로 LUT -41.3%/FF -31.5%/DSP -40.0%.

> **참고(사전 최적화 이력):** 최초 csynth에서 `gamma2()`가 런타임 정수 sqrt(반복 나눗셈)를
> 써서 자원이 5배 이상 부풀었음(합계 FF 58,655/LUT 52,053). 256-엔트리 ROM LUT로 교체해
> 위 수치로 개선(FF -88%, LUT -78%). 상세 §Stage4 문서.

---

## 11. 제약 · 가정 · 알려진 이슈

1. **SW eval은 proxy:** pseudo-RAW는 이미 ISP된 JPEG 역변환, RGGB nearest, n=71~113, CPU.
   절대값 아닌 arm 순서가 판단 근거.
2. **Bayer 패턴 통일(2026-07-02):** HW/C-sim·SW 모두 RGGB. 남은 차이는 RAW 비트표현
   (HW 12-bit `>>4` vs SW shift8 `>>8`)뿐. (과거 실험 보고서의 "GRBG vs RGGB" 캐비어트는 통일 전 기록.)
3. **Stage 1~3 실측 발견(중요):** ver0(normal=identity, low-light=bin+gain+gamma-4.0)은 세
   detector·두 데이터셋 모두에서 **무처리(none)보다 mAP 낮음** = mAP guardrail 탈락.
   **ver1 반영(2026-07-02):** (a) RM_NORMAL_TONE = gain 1.25×+gamma **완료**, (b) low-light
   γ4.0→2.0 완화 **완료**, 보정 12-bit RAW-domain **완료**. ver1은 저조도 arm을 +약20% 개선했으나
   **여전히 none이 최고**(SW proxy 천장) → 방향 A 유지(mAP는 최소 처리, DFX/RM은 자원·전력 정당화).
   남은 개정: (c) checker dark-level 재보정, (d) Policy B/denoise형 RM. 최종 판정은 보드 DPU+real-RAW.
4. **HW 수치 위조 금지:** Vivado/보드 없이 §10·L2~L5 수치를 만들지 않음(TODO 유지).
5. **Adversarial review 수정(2026-07-02):** `/codex:adversarial-review --base 0e433f9`가
   두 결함을 발견·수정: (a) low-light binning이 4샘플을 스칼라 평균한 뒤 재-demosaic해
   색 정보를 파괴하는 버그(golden 모델도 같은 버그를 미러링해 bit-exact 테스트가 못 잡음;
   보고된 lowlight mAP 증거는 다른(색 보존) 알고리즘을 측정한 것이었음) — binning-demosaic
   융합으로 수정, `_bin_demosaic_rggb16`과 bit-exact 일치(§3.3). (b) 메타데이터가 검증 안 된
   구조체 포인터 `s_axilite` 패턴이었던 것 — 4개 scalar 출력 포인터로 교체(§5.3/§6.1).
   **`make verify` 646px bit-exact 유지, 새 색상보존 회귀 테스트 추가.**
   **2026-07-02 20:33 KST: 수정 반영 소스로 Vitis HLS csynth + Vivado DFX 재구현 완주
   (pr_verify PASS 유지, bitstream 크기 byte 단위로 동일). §10이 최신 수치로 갱신됨.**
6. **low-light RM이 mAP를 못 올리는 이유 — ablation 실측 완료(2026-07-02):** 기존
   "H/2 해상도 손실이 원인"이라는 추정(experiment-report §5.2)을 5단계 ablation
   (`tools/isp_pipeline_ablation.py`)으로 검증한 결과 **원인은 조도 조건에 따라 다르다**:
   ExDark(저조도)에서는 해상도 손실 기여가 −1.4%에 불과하고 **BLC/WB(두 RM이 공유하는
   baseline core)가 손실의 약 70%를 차지**(−49.6%p) — RM 고유 문제가 아니라 공유 core의
   정적 WB 게인이 저조도 색 통계를 왜곡하는 문제. 반대로 COCO(정상조도)에서는 해상도
   손실이 지배적(−11.7%, BLC/WB는 −1.9%뿐). 상세: `results/lowlight-rm-map-rootcause-2026-07-02.md`.
7. **DFX 재구성 latency — 단계별 이론적 분해(2026-07-02):** drain(측정, 74~171 cycle)와
   ICAP 전송(686,664B ÷ AMD UG570 ICAPE3 spec 대역폭, peak 1.72ms/전형 6.87ms)과
   warm-up(측정)으로 분해. ICAP 전송이 전체의 >99.9%를 차지(drain/warm-up은 µs, ICAP는
   ms 스케일). 드라이버/FSM 오버헤드는 PR 컨트롤러 미합성으로 계산 불가 — TODO(보드) 유지.
   상세: `results/pr-latency-breakdown-2026-07-02.md`.

---

## 12. 용어

| 용어 | 의미 |
|---|---|
| DFX / DPR | Dynamic Function eXchange / 부분 재구성 |
| RM | Reconfigurable Module(부분 비트스트림 교체 단위) |
| tone RM slot | gain/gamma/binning을 담는 상호배타 재구성 영역 |
| baseline ISP core | demosaic+BLC+WB+CCM 공통(12-bit, tone에 감싸임), gain/gamma 없음 |
| Policy A / B | 형상변경(H/2×W/2) / 형상보존(upsample-pad) |
| guardrail | mAP가 기준선(예: none/register-only) 이상이어야 RM 채택 |
| arm | 실험 비교군(static / register-only / DFX / ablation) |
```

문서 끝 — 변경 시 `RESEARCH.md`·`src/dfxisp_accel.cpp`·`tools/*`와 동기 유지.
