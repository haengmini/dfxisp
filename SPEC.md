---
type: spec
title: "DFXISP 시스템 사양서 (입력 데이터셋 → 출력)"
project: DFXISP
version: 1.1
created: 2026-07-02
updated: 2026-07-20 — BLC/checker 파라미터를 07-13~07-20 real-RAW 캠페인
  배포값으로 갱신(§3.1, §4). 정본 근거: `results/blc-recalibration-deploy-2026-07-20.md`,
  `results/checker-c1-deploy-2026-07-20.md`, `results/checker-oracle-label-gate2-2026-07-20.md`.
target: Zynq UltraScale+ ZCU104 / XCZU7EV (xczu7ev-ffvc1156-2-e)
status: active — 아래 본문은 현재 구현(v1: shared baseline core + 상호배타 tone RM slot)을 기술한다. 목표 아키텍처(v2)는 RESEARCH.md §0 참고
refs: "README.md · RESEARCH.md · isppipeline/hls · results/experiment-report-2026-07-02.md"
---

# DFXISP 시스템 사양서

> **아키텍처 note (2026-07-10):** `RESEARCH.md`가 2026-07-10 reset v2에서 RM 경계를
> tone(gain/gamma)에서 ISP 데이터패스 전체로 넓혔다 — static shell(checker/DFX 컨트롤러/
> AXI/packer)만 남기고, BLC/AWB/demosaic/CCM/gain/gamma 전부를 `RM_NORMAL`/`RM_LOW_LIGHT`
> 두 개의 전체 ISP pipeline RM이 각자 소유한다. **이 SPEC.md 본문은 아직 그 v2로
> 마이그레이션되지 않은 현재(v1) 구현**을 기술한다 — `isppipeline/hls/src/dfxisp_accel.cpp`가
> 여전히 공유 baseline core + tone RM slot 구조이기 때문이다. v1 산술(파라미터 값, 인터페이스)
> 자체는 정확하고 유효하며, v2 코드 마이그레이션 시 이 문서도 함께 갱신한다. 아래 내용을 읽을
> 때 "baseline ISP core"는 v1 한정 개념이라는 점을 염두에 둘 것.

> 입력(pseudo-RAW 데이터셋) → checker → tone RM slot → baseline ISP core → RGB32 출력 →
> 검출기/mAP 까지 전 구간의 데이터 포맷·산술·인터페이스·파라미터를 정의한다(v1, 현재 구현).
> 아키텍처 정본은 `RESEARCH.md`, 구현은 `isppipeline/hls/`. 모든 산술은 **정수(bit-exact)**.

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

**정본 평가 쌍 (real-RAW, 목표 1의 교차 우위 실증용 — RESEARCH.md §10):**

| 데이터셋 | 조도 | 포맷 | 역할 |
|---|---|---|---|
| **PASCAL RAW** | 밝음 | real Bayer RAW | `normal` 모듈이 최고를 낼 조건 |
| **LOD RAW** | 저조도 | **Sony `.ARW`** | `lowlight` 모듈이 최고를 낼 조건 |

- 둘 다 real 센서 RAW라 실제 Poisson-Gaussian 노이즈를 담아, low-light 모듈의 binning(SNR 회복) 정당성을 제대로 검증한다(pseudo-RAW엔 회수할 노이즈 없음).
- 어댑터: LOD는 Sony `.ARW`라 `tools/aodraw_adapter.py`의 rawpy 경로 그대로 적용(파일별 흑레벨/화이트레벨/베이어를 rawpy에서 읽음). shift8 규약으로 정규화 → 아래 §2.2 포맷과 동일.
- **arm 비교는 `normal`/`lowlight`/`adaptive` 세 가지로 한정**한다(색보정 안 된 `none`은 배포 가능한 ISP 출력이 아니므로 제외 — RESEARCH.md §1.2).

**이력 (superseded proxy — 초기 실험용, 정성 결론만 유효):**

| 데이터셋 | 조도 | 경로 | 이미지 수 | 유효(raw==jpg) |
|---|---|---|---|---|
| COCO_val | 정상 | `data/coco_val/` | 575 | 347 |
| ExDark_val | 저조도 | `data/exdark_val/` | 491 | 260 |
| SonyNOD | 저조도(실센서) | `data/sonynod_test/` | 321 | 321 |

각 데이터셋은 `raw_bin/`(pseudo-RAW 또는 shift8 real-RAW), `images/`(해상도 출처 jpg), `labels/`(YOLO txt)로 구성.
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
              dark = (raw < dark_pixel_threshold)     # RAW 도메인, HW·SW(checker.py) 동일
              # dark_pixel_threshold: raw16(SW 사전계산)에서는 16<<8, HW raw12
              # 레지스터값은 규약상 256(=16<<4) — "dark16" 통계
              selected_mode = LOW_LIGHT  if  dark_ratio > 0.62  else NORMAL
              (정수 비교: dark_count*100 > 62*(W*H))
```
- **배포 이력:** 최초 0.40(2026-07-01) → **C0** dark50>0.80(2026-07-02 ver2 재보정,
  Youden's J 관점 최적화) → **C1** dark16>0.62(**2026-07-20 정식 배포, 관문 4**) — C0를
  전 지표에서 지배(recall 0.936 vs 0.918, false-trigger 0.089 vs 0.125, J 0.847 vs 0.793)
  하면서 HW 변경 0(`DARK_RATIO_PCT` 상수 + 런타임 `dark_pixel_threshold` 레지스터값만
  변경). 이번 배포에서 SW 미러(`checker.py`)도 **raw 도메인 직접비교**로 바뀌어 구
  luminance<50 근사(demosaic 후 판정)를 제거, HW·보정 도메인과 정확히 일치시켰다.
  실 RAW 642장(SonyNOD 321 + PASCALRAW 321)에서 manifest 사전계산 dark16/verdict와
  불일치 0. 상세: `results/checker-c1-deploy-2026-07-20.md`.
- **오라클 라벨 재검증(2026-07-20, 관문 2, 최종 관문):** dual-arm 렌더(normal/lowlight) +
  프레임별 YOLOv8n 검출 델타로 "정답 모드"를 데이터셋 provenance가 아니라 실제 검출
  개선 여부로 재정의했다. C1의 naive-라벨 잔존오차 154장 중 **89.6%가 라벨
  아티팩트**(진짜 오류 10.4%뿐)임을 확인 — dark16의 판별력은 "장면이 야간이냐"에는
  강하지만(J 0.847) "이 프레임에서 lowlight가 실제로 검출을 돕는가"에는 약함(오라클
  기준 J 0.008)에도, C1 임계의 **비용-중립점 성질(C_miss≈C_FA)은 오라클 기준에서도
  유지**되어 **재조정 불필요**로 결론. 상세: `results/checker-oracle-label-gate2-2026-07-20.md`.
- **히스테리시스(시퀀스 레벨):** 단일 프레임 entry에는 없음. 장면 단위 안정화(N 안정프레임,
  히스테리시스 밴드, min-dwell)는 스케줄러(`tools/scheduler_sim.py`/`scheduler_sweep.py`)가
  담당. 권장 파라미터(실측): narrow 밴드 + temporal_N=3 (mismatch 0.015, thrashing 0).
  C1 스펙의 Schmitt δ=2%p 히스테리시스는 드라이버측 정책(레포 밖, mode FF 1개).

### 3.2 ② Baseline ISP core (shared code path, mode-specific BLC) — ver1
**gain/gamma 없음.** 보정을 **12-bit RAW 도메인에서 수행**하고 최종 `>>4`는 tone에서 한다
(ver1 핵심: precision 보존). WB/CCM은 두 모드가 완전히 같은 함수(`apply_blc_wb12`)를
공유하지만, **BLC 오프셋은 모드별로 다르다**(2026-07-03, §11.9의 root-cause 결과 반영).
픽셀당:

```text
1. demosaic (RGGB) -> R,G,B 12-bit (0..4095)     # HW/C-sim: >>4 안 함(여기선 유지)
2. BLC   : v = clip(v - blc_offset, 0, 4095)     # normal: 256(16<<4) / low-light: 128(8<<4, 완화)
3. WB    : R = clip(R * 286 / 256, 0, 4095)      # Q8 채널 white balance(color), 모드 무관
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
core       :  apply_blc_wb12(front 출력, blc_offset=128)        # 위 §3.2, demosaic 재실행 없음,
                                                                  # BLC만 완화(2026-07-03)
back (tone):  gain **2.0×**(2/1) + gamma2.0
출력 형상   :  H/2 × W/2   (bin_dim(d) = max(1, d/2))
```
**주의(2026-07-02 수정):** 이전엔 4개 샘플을 `(p00+p01+p10+p11)/4` 스칼라 하나로 평균한 뒤
그 값을 다시 Bayer인 것처럼 demosaic — 색 정보가 이미 파괴된 뒤라 사실상 흑백에 가까운
출력이 나오는 버그였다(adversarial review로 발견). 채널별 정체성을 보존하는 위 방식으로
수정(`tools/isp_pipeline_ver1.py`의 `_bin_demosaic_rggb16`과 bit-exact 일치).

**주의(2026-07-03 수정, BLC 완화):** root-cause ablation(§11.6)에서 저조도 mAP 손실의
~70%가 BLC(WB 아님)에서 발생함을 확인 — low-light 경로의 BLC 오프셋을 256(16<<4)에서
**128(8<<4)로 절반 완화**. ExDark mAP 0.0586→0.1043(+78%, normal을 처음으로 상회),
COCO도 안전(0.2647→0.2857). HW 자원/타이밍은 상수값만 바뀌어 **완전히 불변**. 상세:
`results/blc-fix-resynthesis-2026-07-03.md`.

### 3.4 데이터 흐름 순서 결정 (ver1)
ver1(2026-07-02): 보정(BLC/WB)을 **demosaic 직후 12-bit에서** 수행(선형이라 RAW-domain과 동치,
최종 `>>4` 전까지 정밀도 보존). 저조도 binning은 **RAW에서 precision loss 전**에, gain·gamma는
tone RM(core 뒤)에 둔다(RESEARCH §4.2). de-dup 불변식 유지(gain/gamma는 tone RM에만).

---

## 4. 파라미터 표 (전체 상수, 정수)

| 스테이지 | 파라미터 | 값 | 비고 |
|---|---|---|---|
| checker | DARK_RATIO_PCT | **62**(C1, 2026-07-20 배포, 관문 4·2 완료) — dark16 raw 도메인 직접비교, 구 80(C0, dark50, demosaic 후 Y<50 근사)는 폐기 | AUTO→LOW_LIGHT 임계, `dark_pixel_threshold` 레지스터(HW raw12 규약값 256=16<<4)와 짝 |
| baseline core | BLC_OFFSET12 | **32(=2<<4)**, normal (2026-07-20 재보정, 구 256=16<<4) | 12-bit black-level |
| baseline core | BLC_OFFSET12_LOWLIGHT | **32(=2<<4)**, low-light (2026-07-20 재보정, 구 128=8<<4) — normal과 동일값(모드별 완화 불필요, 2가 양쪽 실측 정점) | 12-bit black-level |
| baseline core | AWB_R / G / B | 286 / 256 / 307 | Q8(/256) white balance |
| baseline core | CCM | identity(256) | placeholder |
| normal tone | GAIN_NORMAL | 5/4 (1.25×) | 노출 게인 (ver1 추가) |
| low-light tone | GAIN_LOWLIGHT | 2/1 (2.0×) | 노출 게인 |
| tone (공통) | GAMMA | γ=2.0 | `floor(sqrt(255·v))` = isqrt, 정수 exact |
| raw 변환 | RAW12_MAX / `>>4` (HW) | 4095 / 12→8 bit | tone에서 >>4 |
| raw 변환 | SHIFT (SW proxy) | 8 | 16→8 bit |
| 형상 | bin_dim | `max(1, d/2)` | Policy A |

> ver1(2026-07-02) 반영 완료: 보정 12-bit RAW-domain, normal에 gain+gamma, low-light γ4.0→2.0(완화).
> SW proxy(`isp_pipeline_ver1.py`)는 float γ2.2/2.5·8-bit 근사(정본은 HW 정수 γ2.0) — 이 파일
> 자체는 이후 `baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`/`checker.py`(canonical,
> HW 상수 직접 미러)로 대체됐다(2026-07-08, `results/isp-pipeline-recalibration-2026-07-08.md`).
> BLC/checker 값은 2026-07-20 실 RAW(SonyNOD+PASCALRAW) 캠페인으로 재보정·배포됐다 — 위 표가
> 현재 정본.

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
| static region (v1, 현재) | AXI/control wrapper, checker/mode FSM, baseline ISP core, DFX/PR controller, output/metadata packer — **v2 목표는 baseline ISP core를 static에서 제거**하고 RM 안으로 옮기는 것(RESEARCH.md §0/§2.3) |
| RM slot(재구성, v1) | RM_NORMAL_TONE / RM_LOW_LIGHT_TONE (상호배타, 동일 downstream 계약 또는 shape 메타 노출). v2에서는 각 RM이 전체 ISP pipeline(`RM_NORMAL`/`RM_LOW_LIGHT`)이 된다 |
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

| 지표 | Arm1(static) | **Arm2(register-only, 실측)** | **Arm3(DFX, 실측 — BLC fix+pblock fix 반영 최종, 2026-07-03)** |
|---|---|---|---|
| LUT / FF / BRAM / DSP | TODO | **8,264 / 5,536 / 9 / 24**(BLC fix 반영해도 자원 불변) | config1(static+RM_NORMAL) routed: LUT 3,972/BRAM 1.5tile/DSP 12; config2(static+RM_LOW_LIGHT) routed: LUT 2,927/BRAM 3.5tile/DSP 8(`results/blc-fix-resynthesis-2026-07-03.md`) |
| Fmax @5.0ns | TODO | **273.97 MHz**(critical path 3.650ns, 수정 전후 동일) | 기존 pblock(X0Y0:X1Y0)에서 **200MHz 제약 만족** 확인(WNS config1 +0.619ns/config2 +1.930ns, 2026-07-03; `results/dfx-vivado-considerations-2026-07-03.md` §6) — **신규 pblock(X1Y0:X2Y0)에서는 아직 타이밍 제약 재검증 TODO** |
| pr_verify | — | — | **✅ PASS**(BLC fix+pblock fix 동시 반영 후에도 static 완전 동일; partition pin **3개** — 구 floorplan의 15개와 다름, 원인 미조사) |
| full bitstream size | — | — | **19,311,211 bytes ≈ 19.3 MB**(불변) |
| partial bitstream size | — | — | **1,447,424 bytes ≈ 1.38 MB**(신규 pblock, 구 686,664B 대비 **2.11배** — pblock 용량 2배 확장의 직접적 대가, `results/blc-fix-resynthesis-2026-07-03.md` §5) |
| 재구성 지연(ms) | — | — | 신규 bitstream 기준 재계산: peak **3.618ms**/전형 **14.473ms**(구 1.72/6.87ms의 2.11배); 드라이버/FSM 포함 실측은 TODO(보드) |
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
   ICAP 전송(686,532B payload ÷ AMD UG570 ICAPE3 spec 대역폭, peak 1.72ms/전형 6.87ms)과
   warm-up(측정)으로 분해. ICAP 전송이 전체의 >99.9%를 차지(drain/warm-up은 µs, ICAP는
   ms 스케일). 드라이버/FSM 오버헤드는 PR 컨트롤러 미합성으로 계산 불가 — TODO(보드) 유지.
   **Vivado(XSIM) 시뮬레이션으로 더 정밀한 값을 시도했으나(실제 partial bitstream을
   ICAPE3 UNISIM 모델에 직접 스트리밍), 격리된 테스트벤치에서는 trigger→완료 신호를
   끝내 얻지 못함(SYNC는 성공, 완료 신호는 3가지 방법 모두 실패 — 원인·한계 분석 포함,
   정직하게 기록)** — payload word 수(171,633)는 파일에서 직접 검증해 반영.
   상세: `results/pr-latency-breakdown-2026-07-02.md`, `results/pr-latency-vivado-sim-2026-07-02.md`.
8. **설계 한계 종합 + DFX 실무 고려사항(2026-07-03):** 알고리즘/SW eval/HW synthesis/
   DFX 구현/시뮬레이션 5개 층위의 한계를 종합(`results/design-limitations-2026-07-03.md`).
   같은 날 timing-constrained 재구현으로 실제 WNS 확보(§10 Fmax 행), pblock이 실제로는
   클럭 리전 1개분(2개 중 1개가 0.06%만 기여)만 확보됐다는 사실, 설계에 `ICAPE3`/
   `STARTUPE3`가 전혀 없어 PR 컨트롤러가 아직 존재하지 않는다는 사실을 새로 확인.
   Vivado DFX 트러블슈팅 전체(I/O 핀 초과, SNAPPING_MODE, black-box+lock 방법론,
   DRC 우회 등)를 체크리스트로 정리. 상세: `results/dfx-vivado-considerations-2026-07-03.md`.
   위 두 문서를 실행 가능한 단계별 전략으로 재구성한 문서:
   `results/improvement-strategy-2026-07-03.md`(유일한 진짜 blocking item은 PR
   컨트롤러 부재 — 이것만 해결하면 나머지는 병렬 진행 가능).
9. **Phase 0~2 즉시 실행(같은 날 후속):** 6개 항목 전부 실행 완료 —
   golden-model 독립 교차검증 게이트(`make verify`에 통합), pblock 클럭 리전
   편중 원인 확정(X0 컬럼 Y0~Y3 = PS 매크로, SLICE 0개), 저조도 WB/BLC 분리
   ablation(**BLC 완화가 진짜 승자** — ExDark mAP 0.062→0.150, normal을 42%
   상회, COCO 무해), PR 컨트롤러 1차 FSM 설계+시뮬레이션(word-count 기반 완료
   판정으로 어제의 PRDONE 한계 우회, trigger→완료 1.716ms 실측 — 스펙 유도
   추정과 교차검증 일치), pblock 재floorplan(X1Y0:X2Y0으로 용량 2배: LUT
   8,640→19,200). 상세: `results/phase0-2-execution-2026-07-03.md`.
10. **BLC 완화 정본 반영 + 전체 재합성(같은 날 후속):** 9번의 ablation 승자(BLC
    완화)를 `src/dfxisp_accel.cpp`/`gen_golden_vectors.py`/`isp_pipeline_ver1.py`
    정본에 반영(`apply_blc_wb12`에 `blc_offset` 매개변수 추가, low-light만
    128, normal은 256 불변). 표준 표본(n=71/80) 재측정: ExDark lowlight
    0.0586→**0.1043**(+78%, **처음으로 normal을 상회**), COCO 0.2647→0.2857(+8%,
    무해). HLS csynth 3종 전부 자원 불변(상수 하나만 바뀐 순수 파라미터 변경).
    Vivado DFX를 9번의 pblock fix와 함께 재구현: pr_verify PASS 유지하지만
    **partial bitstream이 2.11배 커짐**(686,664B→1,447,424B) — pblock 용량 2배
    확장의 직접적 대가(재구성 지연도 2.11배: peak 1.72ms→3.62ms). 상세:
    `results/blc-fix-resynthesis-2026-07-03.md`.

---

## 12. 용어

| 용어 | 의미 |
|---|---|
| DFX / DPR | Dynamic Function eXchange / 부분 재구성 |
| RM | Reconfigurable Module(부분 비트스트림 교체 단위) |
| tone RM slot | **(v1 한정)** gain/gamma/binning을 담는 상호배타 재구성 영역. v2(RESEARCH.md §0)에서는 RM 경계가 ISP 데이터패스 전체로 확장돼 이 개념은 superseded |
| baseline ISP core | **(v1 한정)** demosaic+BLC+WB+CCM 공통(12-bit, tone에 감싸임), gain/gamma 없음. v2에서는 이 공유 static 스테이지 자체가 사라지고 각 RM이 전체를 소유(RESEARCH.md §0/§3) |
| Policy A / B | 형상변경(H/2×W/2) / 형상보존(upsample-pad) |
| guardrail | mAP가 기준선(예: none/register-only) 이상이어야 RM 채택 |
| arm | 실험 비교군(static / register-only / DFX / ablation) |
```

문서 끝 — 변경 시 `RESEARCH.md`·`src/dfxisp_accel.cpp`·`tools/*`와 동기 유지.
