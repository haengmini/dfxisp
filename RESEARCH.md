# RESEARCH.md — DFXISP 연구 정본

최종 수정: 2026-07-10 (아키텍처 reset v2 — RM 경계를 tone에서 전체 ISP 파이프라인으로 확장) · 파라미터/checker 각주 2026-07-20 갱신  
소유자: 이형민  
대상 보드: Zynq UltraScale+ ZCU104 / XCZU7EV  
핵심 논지: **static shell(비-ISP 제어/라우팅) + 상호 배타적인 mode-specific 전체 ISP pipeline RM**

> **현재 상태 한 줄 요약(2026-07-20):** 아래 §0~14의 아키텍처·증명전략은
> 그대로 유효하다(변경 없음). §10.2가 요구한 **PASCAL RAW/LOD RAW 실측
> 교차검증은 완료**됐다(2026-07-15/16, Shuffle_split 642장) — BLC/checker
> 파라미터가 그 실측을 근거로 재보정·배포됐고(BLC 2/2, checker C1
> dark16>0.62), checker의 마지막 관문(오라클 라벨 재정의)도 닫혔다. 최신
> 상태·수치는 `ROADMAP.md`(진행 추적)와 `SPEC.md`(파라미터 정본)를 따를 것 —
> 이 문서는 아키텍처·연구목표·증명전략의 정본이며 세부 파라미터 값은 여기서
> 동결하지 않는다.

---

## 0. 이 reset의 목적

**2026-07-10 reset v2:** 2026-07-02 reset(v1)은 "공유 baseline ISP core(BLC/AWB/demosaic/CCM) +
작은 tone RM(gain/gamma만 swap)" 구조를 정본으로 삼았다. 이 v2는 그 구조를 대체한다 — RM
경계를 **tone(gain/gamma)에서 ISP 데이터패스 전체(BLC/AWB/demosaic/CCM/gain/gamma)로 바깥으로
확장**하고, "공유 baseline ISP core"라는 static 스테이지 자체를 없앤다.

이유(상세는 §1.3, §2): v1의 tone-only RM은 스왑 단위가 너무 작아(gain 곱셈 + gamma LUT
수준) DFX의 존재 이유(목표 2)를 스스로 약화시켰다 — register-only(Arm 2)로 두 tone 구현을
동시 상주시켜도 자원 비용이 무시할 만해, "왜 부분재구성까지 필요한가"라는 반론에 취약했다.
ISP 파이프라인 전체를 RM으로 삼으면 Arm 2(두 개 full 파이프라인 상주)와 Arm 3(DFX, 하나만
상주) 사이의 자원/전력 격차가 실질적으로 커져 DFX 동기가 방어 가능해진다.

의도한 설계(v2)는 다음과 같다.

```text
static shell (비-ISP 제어/라우팅만) + mode-specific 전체 ISP pipeline RM

NORMAL:
  RM_NORMAL = stock Vitis Vision 기준 ISP pipeline 전체
              (BLC + AWB/color calibration + demosaic + CCM + gain + gamma)

LOW_LIGHT:
  RM_LOW_LIGHT = 저조도 특화 ISP pipeline 전체
                 (2x2 binning-demosaic + 저조도 BLC/AWB/CCM + 저조도 gain + 저조도 gamma)
```

RM은 **상호 배타적(mutually exclusive)** 이다 — 프레임/세그먼트당 정확히 하나의 전체 ISP
pipeline만 활성화된다. Static shell은 ISP 데이터패스를 전혀 포함하지 않는다: AXI/control
wrapper, checker/mode-FSM, DFX/PR 컨트롤러, output/metadata packer만 static이다.

**v1(공유 baseline core + tone RM)과의 핵심 차이:**

| | v1 (superseded) | v2 (정본) |
|---|---|---|
| Static 영역 | AXI/제어 + checker + **baseline ISP core(BLC/AWB/demosaic/CCM)** + DFX 컨트롤러 + packer | AXI/제어 + checker + DFX 컨트롤러 + packer (ISP 데이터패스 없음) |
| RM 내용물 | gain + gamma (+ low-light binning)만 | BLC/AWB/demosaic/CCM/gain/gamma **전체** |
| RM_NORMAL | gain 1.25× + gamma, or identity | stock Vitis Vision ISP pipeline 전체 |
| RM_LOW_LIGHT | binning + gain + gamma | 저조도 특화 ISP pipeline 전체(binning-demosaic + 저조도 BLC/AWB/CCM/gain/gamma) |
| de-dup 규칙(§3.1, v1) | gain/gamma가 baseline core와 RM에 중복 배치되지 않게 관리 | 불필요 — 각 RM이 자기 파이프라인을 통째로 소유, 공유 스테이지가 없음 |
| DFX 동기 | 약함(스왑 단위가 tone 곡선 수준) | 강함(스왑 단위가 전체 ISP 데이터패스) |

현재 `isppipeline/hls/`의 HLS C-sim 구현(`dfxisp_accel.cpp` 등)은 아직 **v1 구조**다 —
공유 baseline core + tone RM. v2로의 코드 마이그레이션은 이 문서 reset 다음 단계이며, 이
문서 자체는 문서 우선 정렬(architecture-first)만 다룬다. v1 코드는 그대로 유효한 ablation/
비교 기준(`Ref`, STRATEGY.md 참고)으로 취급하고, 성급히 지우지 않는다.

---

## 1. 연구 목표

### 1.0 논지 (thesis) — 왜 이 연구를 하는가

컴퓨터 비전(CV) 검출기는 **조도 조건에 따라 서로 다른 이미지 전처리**를
요구한다. 하나의 static ISP pipeline으로 밝은 장면과 어두운 장면을 모두
처리하면, 어느 한쪽(특히 저조도)에서 CV 성능·효율이 떨어진다. 따라서
**CV를 위한 ISP는 저조도에 특화된 vision processor 경로를 별도로 갖고,
상황에 맞는 모듈로 전환**해야 한다는 것이 본 연구의 논지다.

이 논지를 **두 개의 최종 목표**로 나눈다.

- **목표 1 (필요성 — 저조도 특화 모듈):** 저조도 환경에서 static/일반
  ISP 경로는 CV(검출기)에 대한 성능이 떨어진다. **저조도에 특화된 모듈이
  더 적합**하며, 각 모듈은 자기 조건의 데이터셋에서 상대 모듈보다 높은
  CV 성능을 낸다(§7 arm 비교, §10 데이터셋).
- **목표 2 (전환 — DFX 적응):** 조건이 바뀌므로 어느 한 모듈을 고정으로
  쓸 수 없다 — **상황에 맞춰 모듈을 전환(adaptive)**해야 하고, 이 전환을
  FPGA Dynamic Function eXchange(DFX)로 구현하면 static/always-on 설계
  대비 **자원·전력 효율**까지 개선한다.

**핵심 연구 질문:** ISP 데이터패스 전체를 static shell에서 분리해 상호 배타적인 전체
ISP pipeline RM으로 나누고, normal scene에서는 `RM_NORMAL`, dark scene에서는
`RM_LOW_LIGHT`로 (체커가 판단해) 전환하면, (목표 1) 저조도 CV 성능을 살리고 (목표 2)
register-only adaptive 대비 DFX로 자원·전력 효율을 얻을 수 있는가?

### 1.1 증명 전략 — 필요성 → 전환, SW 먼저 → HW

논증 순서는 다음과 같다.

1. **필요성(목표 1):** 단일 모듈이 **각각 자기 조건의 데이터셋에서 최고**임을
   보인다 — normal 모듈은 밝은 조도 RAW(§10: PASCAL RAW)에서, low-light
   모듈은 저조도 RAW(§10: LOD RAW)에서. 한 모듈이 두 조건을 모두 이기지
   못하므로 **고정 단일 모듈은 부적합 → 전환이 필요**하다는 결론이 나온다.
2. **전환(목표 2):** 따라서 체커가 조건을 판단해 모듈을 고르는 adaptive
   경로가 두 조건이 섞인 스트림에서 **최적 단일 static을 상회**함을 보인다.
3. **SW → HW 순서:** 위 두 주장을 먼저 **SW(golden/파이썬 mAP)로 확립**한
   뒤, **HW(HLS 합성 → DFX 부분재구성 → 보드)로 이식**한다. HW 트랙의
   고유 기여는 **효율(자원/전력)** — 특히 보드(Stage 6)에서 DFX가 always-on
   대비 static 자원·전력을 줄인다는 것을 실측한다.

### 1.2 비교 범위 (arm) — `none`은 제외

CV 성능 비교의 arm은 **`normal` / `lowlight` / `adaptive`** 세 가지다.
**demosaic만 하고 baseline core(BLC/AWB/CCM)·톤을 전혀 거치지 않는
`none`(무처리) arm은 본 연구의 비교 대상에서 제외**한다 — `none`은 색
보정된 배포 가능한 ISP 출력이 아니라(AWB/CCM 미적용, 색편향 잔존) 별개
계열의 문제이기 때문이다. 이후 모든 arm 비교·결론은 이 세 arm 안에서만
이루어진다.

### 1.3 실험적으로 분리하는 세 주장 (위 목표에 매핑)

1. **알고리즘 주장 (목표 1의 성능 근거)**  
   Mode-specific tone processing은 gain/gamma를 두 번 적용하지 않고도
   normal/dark 각 조건의 image conditioning을 지원한다. **Low-light 모듈은
   binning + low-light gain + low-light gamma + 완화된 black-level**을
   쓰며, 각 조건 데이터셋에서 상대 모듈 대비 CV 성능 우위를 낸다(구체
   기술·기대이득·실측이득은 `results/lowlight-module-techniques-2026-07-10.md`).

2. **아키텍처 주장 (목표 1·2의 구조 근거)**  
   ISP 데이터패스 전체(BLC/AWB/demosaic/CCM/gain/gamma)를 static shell에서 완전히
   분리해, 상호 배타적인 전체 ISP pipeline RM `RM_NORMAL`/`RM_LOW_LIGHT`로 나누고
   체커가 하나만 선택한다. Static shell은 checker/DFX 컨트롤러/AXI/packer만 담당하며
   ISP 연산을 전혀 포함하지 않는다 — 이래야 DFX가 스왑하는 단위가 충분히 커서
   register-only(Arm 2) 대비 실질적인 자원/전력 이득(목표 2)이 성립한다.

3. **DFX 효율 주장 (목표 2의 효율 근거)**  
   Register-only 또는 always-on adaptive 설계와 비교했을 때, DFX는 허용
   가능한 reconfiguration overhead를 지불하는 대신 static resource pressure
   또는 power를 줄인다(보드 실측은 Stage 6).

---

## 2. 정본 아키텍처

### 2.1 상위 block diagram

```text
Input frame
  Bayer / real-RAW / pseudo-RAW fixture
        │
        ▼
Scene checker / mode decision   (static)
  - luminance 또는 dark ratio 계산
  - threshold + hysteresis 적용
  - NORMAL 또는 LOW_LIGHT 결정
        │
        ▼
DFX / PR controller               (static)
  - selected RM 결정, reconfiguration 트리거
        │
        ├───────────────────────────────────────────────┐
        │                                               │
        ▼                                               ▼
RM_NORMAL (reconfigurable)                    RM_LOW_LIGHT (reconfigurable)
  전체 ISP pipeline:                            전체 ISP pipeline:
    BLC                                           2x2 binning-demosaic
    AWB / color calibration                       저조도 BLC(완화)
    demosaic                                       저조도 AWB / color calibration
    CCM                                            저조도 CCM
    gain                                           저조도 gain
    gamma                                          저조도 gamma
        │                                               │
        └───────────────────────────────┬───────────────┘
                                        ▼
                       output packer / metadata packer   (static)
                                        │
                                        ▼
                                  RGB32 output
                                  DPU / detector input
```

`RM_NORMAL`과 `RM_LOW_LIGHT`는 상호 배타적인 하나의 Reconfigurable Partition을 채우는 두
variant다 — 동시에 두 개가 fabric에 상주하지 않는다(Arm 3/DFX). Register-only 비교군(Arm 2)에서는
둘 다 상주하되 런타임에 하나만 선택한다.

### 2.2 동작 규칙

RM은 mode-specific 전체 ISP pipeline이다. Normal과 low-light는 서로 다른 BLC/AWB/demosaic/CCM/
gain/gamma 구현을 갖고, 한 프레임/세그먼트는 그중 정확히 하나만 통과한다. Baseline ISP core라는
별도 공유 스테이지는 없다 — 각 RM이 자신의 ISP 데이터패스 전체를 소유한다.

```text
Normal lighting:
  checker selects NORMAL
  DFX controller selects/activates RM_NORMAL
  RM_LOW_LIGHT is inactive (register-only) or not resident in fabric (DFX)
  RM_NORMAL runs its full ISP pipeline: BLC -> AWB -> demosaic -> CCM -> gain -> gamma
  output is marked NORMAL mode

Dark lighting:
  checker triggers LOW_LIGHT
  DFX controller swaps in RM_LOW_LIGHT (or selects it, register-only)
  RM_NORMAL is inactive (register-only) or not resident in fabric (DFX)
  RM_LOW_LIGHT runs its full ISP pipeline: binning-demosaic -> relaxed BLC -> AWB ->
    CCM -> gain -> gamma
  output is marked LOW_LIGHT mode

Return to bright lighting:
  checker sees recovery condition
  DFX controller swaps back to RM_NORMAL
  RM_LOW_LIGHT becomes inactive / is evicted from fabric
```

### 2.3 Static region과 RM boundary

권장 partition은 다음과 같다.

```text
Static region (non-ISP control/routing only):
  - AXI/control wrapper
  - frame metadata handling
  - checker / mode-decision FSM
  - DFX/PR controller interface
  - output packer / metadata packer
  # ISP 데이터패스(BLC/AWB/demosaic/CCM/gain/gamma)는 static region에 없다

Reconfigurable Partition (mutually exclusive, 전체 ISP pipeline 단위):
  RM_NORMAL:
    - stock Vitis Vision 기준 ISP pipeline (BLC, AWB/CCM, demosaic, gain, gamma)
    - active during normal lighting

  RM_LOW_LIGHT:
    - 저조도 특화 ISP pipeline
      (2x2 binning-demosaic, 완화 BLC, 저조도 AWB/CCM, 저조도 gain, 저조도 gamma)
    - active only after dark-scene trigger
```

이 boundary는 "baseline ISP core"라는 static 공유 스테이지를 없애고, ISP 연산 전체를 RM 안으로
옮긴다. 남는 static 로직은 프레임의 화소 데이터를 직접 건드리지 않는 제어/라우팅 뿐이다(checker,
DFX 컨트롤러, AXI 셸, output/metadata packer). 두 RM은 같은 downstream interface contract(RGB32
출력 + 메타데이터)를 제공해야 하며, shape이 다르면(§4.3 Policy A) 명시적인 output metadata를
내보내야 한다.

**v1 대비 근거:** v1의 static baseline core는 BLC/AWB/demosaic/CCM을 두 모드가 공유하게 해
자원을 아꼈지만, 그 결과 저조도 조건에서도 정상조도용 정적 WB/BLC 파라미터를 그대로 써야 했다
(§3.3 원인 규명 실측: 저조도 mAP 손실의 ~70%가 baseline core의 정적 BLC/WB에서 발생 — 아래
`results/lowlight-rm-map-rootcause-2026-07-02.md`). RM이 ISP 전체를 소유하면 저조도 전용
BLC/AWB/CCM 파라미터(또는 알고리즘 자체)를 자유롭게 바꿀 수 있어 목표 1(교차 우위)의 상한이
더는 공유 core에 눌리지 않는다.

---

## 3. ISP pipeline RM 명세 (공통 구조)

Baseline ISP core라는 별도 static 스테이지는 없다. 대신 `RM_NORMAL`과 `RM_LOW_LIGHT` 각각이
아래 stage 전체를 자체적으로 소유한다 — 두 RM 사이에 공유되는 ISP 연산 스테이지는 없다.

```text
RM 공통 개념 stage (각 RM이 독립적으로 자기 파라미터/알고리즘으로 구현):
  Input(raw)
    -> black-level correction, BLC
    -> demosaic (or binning-demosaic)
    -> AWB / color calibration
    -> color correction matrix, CCM
    -> gain
    -> gamma
    -> RGB32 pack/output
```

### 3.1 Ownership rule (v1의 de-dup rule을 대체)

v1에서는 "각 operation은 정확히 하나의 owner(baseline core 또는 tone RM)를 가져야 한다"는
de-dup 규칙으로 gain/gamma 중복을 막았다. v2에서는 이 규칙이 **불필요**하다 — BLC/AWB/
demosaic/CCM/gain/gamma 전부가 선택된 RM 하나에 귀속되고, 공유 스테이지가 없으므로 애초에
중복이 발생할 여지가 없다.

| Operation | Owner (mutually exclusive) |
|---|---|
| BLC | `RM_NORMAL` 자체 BLC, 또는 `RM_LOW_LIGHT` 자체(완화) BLC |
| demosaic | `RM_NORMAL` 표준 demosaic, 또는 `RM_LOW_LIGHT` binning-demosaic |
| AWB / color calibration | `RM_NORMAL` 자체 AWB, 또는 `RM_LOW_LIGHT` 자체 AWB |
| CCM | `RM_NORMAL` 자체 CCM, 또는 `RM_LOW_LIGHT` 자체 CCM |
| gain | `RM_NORMAL` normal gain, 또는 `RM_LOW_LIGHT` low-light gain |
| gamma | `RM_NORMAL` normal gamma, 또는 `RM_LOW_LIGHT` low-light gamma |
| RGB32 packing | static output packer(두 RM 모두 같은 output contract로 넘김) |

Reset 이후 기본 구조는 다음이다.

```text
NORMAL:
  input -> RM_NORMAL(BLC + demosaic + AWB/CCM + gain + gamma) -> RGB32

LOW_LIGHT:
  input -> RM_LOW_LIGHT(binning-demosaic + 완화 BLC + AWB/CCM + gain + gamma) -> RGB32
```

### 3.2 RM_NORMAL의 역할

`RM_NORMAL`(stock Vitis Vision 기준 ISP pipeline)은 다음 용도로 사용한다.

1. Normal-scene output.
2. Low-light mode와 비교하기 위한 bright-scene reference.
3. Fixed pipeline correctness를 위한 golden-vector reference.
4. DFX benefit analysis를 위한 resource/timing baseline(Arm 1).
5. 신뢰할 수 있는 표준 라이브러리(xf::cv) 기준선 — 리뷰어가 검증된 구현으로 인정하는 지점.

### 3.3 RM_NORMAL은 안정적으로 유지해야 한다

Low-light RM 실험을 수행하는 동안 `RM_NORMAL`을 반복적으로 바꾸면 안 된다. 둘 다 동시에
바뀌면 output 차이를 어느 RM 때문인지 attribution할 수 없다.

권장 discipline은 다음이다.

```text
Phase A: lock RM_NORMAL arithmetic (stock Vitis Vision 기준)
Phase B: add RM_LOW_LIGHT arithmetic
Phase C: add checker/mode controller
Phase D: add DFX/RP mechanics
Phase E: run DPU/mAP evaluation
```

---

## 4. Low-light RM(`RM_LOW_LIGHT`) 명세

이 절은 `RM_LOW_LIGHT` 전체 ISP pipeline 안에서 **저조도 고유 처리(binning + BLC 완화 +
gain + gamma)**를 다루며, BLC/AWB/CCM 같은 나머지 ISP 스테이지도 이 RM이 함께 소유한다는
전제(§3)는 바뀌지 않는다. v1 문서의 "tone RM"이라는 이름은 여기서는 "저조도 특화 pipeline
안의 tone/exposure 처리"로 좁혀 읽는다.

### 4.1 필수 operation

`RM_LOW_LIGHT`는 최소한 다음을 구현해야 한다.

```text
2x2 binning + gain + gamma   (+ 완화 BLC, §3의 나머지 ISP 스테이지)
```

최소 기능 정의는 다음과 같다.

1. **2x2 binning**
   - 인접 pixel을 결합해 signal strength를 높이고 noise sensitivity를 줄인다.
   - Channel별 후보 formula:

     ```text
     binned = (p00 + p01 + p10 + p11) / 4
     ```

   - Bayer/RAW에서 동작한다면 Bayer semantics를 보존하거나 channel grouping을 명시해야 한다.
   - RGB32에서 동작한다면 channel별 binning을 적용한다.

2. **Gain**
   - Binning 이후 linear gain을 적용한다.
   - 초기 후보값:

     ```text
     gain = 1.25x or 1.5x
     ```

   - Highlight destruction을 막기 위해 clipping 또는 soft-knee policy를 포함해야 한다.

3. **Gamma**
   - Dark-region lift를 위한 nonlinear transform.
   - 초기 후보값:

     ```text
     normal gamma:    γ = 2.2
     low-light gamma: γ = 4.0
     ```

   - 구현은 LUT, piecewise approximation, fixed-point power approximation 중 하나를 사용할 수 있다.
   - HLS/Vivado feasibility 관점에서는 LUT를 우선한다.

### 4.2 RM이 low-light path 앞 또는 내부에서 동작해야 하는 이유

현재 관찰된 scaffold는 normal demosaic와 RAW12-to-RGB8 conversion 이후 gain/lift를 적용한다. 이것만으로는 충분하지 않다.

1. Enhancement 전에 RAW precision이 줄어든다.
2. Binning이 없으므로 SNR이 개선되지 않는다.
3. Gamma가 없으므로 dark-region expansion이 조악하다.
4. Output을 밝게 만들 뿐, 실제 low-light front-end로 동작하지 않는다.

수정된 RM은 binning과 gamma가 의미 있고 측정 가능한 stage에서 동작해야 한다.

### 4.3 Output shape policy

2x2 binning은 자연스럽게 shape을 바꾼다.

```text
Input  H x W
Output H/2 x W/2
```

허용 가능한 정책은 두 가지다.

#### Policy A — Shape-changing RM

```text
LOW_LIGHT output = H/2 x W/2
```

장점:
- Binning semantics가 명확하다.
- Low-light processing 이후 pixel count가 줄어든다.
- Binning operation 증명이 쉽다.

단점:
- DPU integration이 variable shape을 처리해야 한다.
- Golden vector와 metadata에 output width/height가 포함되어야 한다.

#### Policy B — Shape-preserving RM

```text
2x2 binning -> low-light enhancement -> upsample/pad back to H x W
```

장점:
- DPU ABI가 안정적으로 유지된다.
- Frame-to-frame comparison이 쉽다.

단점:
- 추가 logic이 필요하다.
- Resize policy 때문에 binning benefit이 일부 흐려질 수 있다.

현재 권장안:

```text
Milestone 1: implement Policy A explicitly with output metadata.
Milestone 2: add Policy B only if DPU integration requires fixed H x W.
```

---

## 5. Checker와 trigger policy

### 5.1 Checker 역할

Checker는 low-light RM을 활성화해야 하는지 결정한다.

단순히 noisy threshold로 매 frame switch하면 안 된다. Scene-level 또는 window-level stability를 사용해야 한다.

후보 metric:

```text
Y = (R + 2G + B) / 4
```

후보 dark ratio:

```text
dark_ratio = count(Y < dark_pixel_threshold) / frame_pixels
```

후보 transition threshold:

```text
NORMAL -> LOW_LIGHT: dark16 ratio > 0.62   # deployed 2026-07-20 (C1, was C0 dark50>0.80
                                            # from 2026-07-02; see SPEC.md §3.1/§4)
LOW_LIGHT -> NORMAL: dark_ratio < 0.20     # exit/hysteresis stays scheduler-layer (§5.2);
                                            # dfxisp_accel's single-frame AUTO checker only
                                            # implements the enter-side ratio, no exit/hysteresis.
```

### 5.2 Hysteresis requirement

Mode flicker를 피하기 위해 hysteresis를 사용한다.

```text
if mode == NORMAL and dark_ratio > high_threshold for N stable frames:
    trigger LOW_LIGHT

if mode == LOW_LIGHT and dark_ratio < low_threshold for N stable frames:
    return NORMAL
```

최소 metadata log:

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

문서 수준 요구사항은 다음이다.

```text
NORMAL uses RM_NORMAL (전체 ISP pipeline).
LOW_LIGHT uses RM_LOW_LIGHT (전체 ISP pipeline).
The two RMs are mutually exclusive.
Static shell은 ISP 데이터패스를 전혀 포함하지 않으며, 따라서 gain/gamma를
두 번 적용할 여지 자체가 없다.
```

구현은 단계별로 다음과 같이 표현할 수 있다.

1. C-sim stage: `RM_NORMAL`, `RM_LOW_LIGHT` 중 정확히 하나의 전체 ISP pipeline 함수를 선택한다.
2. RTL stage: mode select가 정확히 하나의 RM implementation으로만 route한다.
3. DFX stage: PR controller가 RM을 `RM_NORMAL` 구현과 `RM_LOW_LIGHT` 구현 사이에서 swap한다.
4. Board stage: 실제 reconfiguration latency와 dropped-frame behavior를 측정한다.

---

## 6. 수정된 구현 목표

### 6.1 현재(v1) 코드의 상태

현재 `isppipeline/hls/`의 코드는 여전히 v1 구조(공유 baseline core + tone RM)다.
이것은 §0에서 설명한 대로 아직 v2로 마이그레이션되지 않은 **현재 구현**이며, v2 문서
reset 다음 단계에서 코드가 따라온다. v1 코드 자체는 유효한 golden/ablation 기준으로
계속 쓴다 — 지우지 않는다.

### 6.2 목표(v2) C-sim structure

목표 HLS C-sim은 다음 구조가 되어야 한다.

```text
raw/input frame
  -> checker_select_mode        (static)
  -> dfx_ctrl_select_rm         (static)
  -> if NORMAL:
         rm_normal(input)       # 전체 ISP pipeline: BLC+demosaic+AWB/CCM+gain+gamma
     if LOW_LIGHT:
         rm_low_light(input)    # 전체 ISP pipeline: binning-demosaic+완화BLC+AWB/CCM+gain+gamma
  -> output packer + metadata   (static)
```

이 순서가 v2 project default다. 정확히 하나의 전체 ISP pipeline RM이 선택되고, static
shell은 그 출력을 그대로 패킹/보고한다. gain/gamma 중복 적용 여지 자체가 없다(§3.1).

---

## 7. 실험 arm

연구 contribution을 증명하려면 최소 세 arm을 비교해야 한다.

### Arm 1 — Static RM_NORMAL only

```text
RM_NORMAL만 상주 (전체 ISP pipeline)
no low-light RM
no DFX
```

목적:
- 고정 normal-scene reference.
- Normal-scene correctness.
- RM_NORMAL 단독의 resource/timing baseline.

### Arm 2 — Register-only adaptive

```text
같은 bitstream에 RM_NORMAL과 RM_LOW_LIGHT(전체 ISP pipeline 2벌) 모두 상주
checker/컨트롤러가 런타임에 하나만 선택해서 실행
no PR/DFX
```

목적:
- DFX 없이 adaptation benefit을 보인다.
- 두 개의 **전체 ISP pipeline**을 동시 상주시키므로 자원 비용이 v1(tone RM 2개 상주)보다
  훨씬 크다 — 이것이 Arm 3(DFX) 이득을 실질적으로 만드는 지점이다.

### Arm 3 — DFX adaptive ISP pipeline RM

```text
static shell(checker + DFX 컨트롤러 + AXI + packer)만 상주
DFX/RP가 전체 ISP pipeline RM을 교체:
  RM_NORMAL     = stock Vitis Vision 기준 ISP pipeline
  RM_LOW_LIGHT  = 저조도 특화 ISP pipeline(binning-demosaic + 완화 BLC + AWB/CCM + gain + gamma)
```

목적:
- Main research claim.
- Arm 2와 비교해 resource, timing, power, reconfiguration overhead를 평가한다 —
  스왑 단위가 전체 ISP pipeline이라 Arm 2 대비 자원 절감폭이 v1보다 커야 한다(가설, Stage 4/5 재실측 필요).

---

## 8. 검증 계획

### 8.1 Golden model first

HLS/RTL을 바꾸기 전에 Python golden behavior를 먼저 정의한다.

필수 golden output:

```text
bright_normal
  expected mode: NORMAL
  expected selected RM: RM_NORMAL
  expected inactive RM: RM_LOW_LIGHT
  expected output shape: H x W

dark_lowlight
  expected mode: LOW_LIGHT
  expected selected RM: RM_LOW_LIGHT
  expected inactive RM: RM_NORMAL
  expected output shape: H/2 x W/2 if shape-changing policy is selected

bright_recovery
  expected mode: NORMAL after hysteresis
  expected selected RM: RM_NORMAL
  expected inactive RM: RM_LOW_LIGHT
```

### 8.2 HLS C-sim gates

최소 C-sim pass criteria:

1. Golden vector generation이 성공한다.
2. HLS C++ output이 Python golden output과 bit-exact하게 일치한다.
3. Bright frame은 `RM_NORMAL`을 선택하고 `RM_LOW_LIGHT`를 통과하지 않는다.
4. Dark frame은 `RM_LOW_LIGHT`를 선택하고 `RM_NORMAL`을 통과하지 않는다.
5. 정확히 하나의 전체 ISP pipeline RM만 실행됐는지 확인한다(gain/gamma 중복 검사는 불필요 —
   애초에 공유 스테이지가 없으므로).
6. Output metadata가 expected mode, selected RM, shape과 일치한다.
7. Boundary size를 test한다: even dimensions, odd dimensions, small frames.

### 8.3 RTL / Vivado gates

C-sim pass 이후:

1. C-synthesis report를 생성한다.
2. Static shell, `RM_NORMAL`, `RM_LOW_LIGHT` 각각의 II/latency를 보고한다.
3. Resource table에는 static region과 각 RM(전체 ISP pipeline)의 LUT, FF, BRAM, DSP를 포함한다.
4. Timing report에는 WNS/TNS와 clock target을 포함한다.
5. 전체 ISP pipeline RM에 대한 DFX partition floorplan을 정의한다.
6. RM variants에 대해 `pr_verify` 또는 equivalent DFX verification을 통과한다.
7. 각 RM variant의 partial bitstream size를 기록한다.
8. Reconfiguration latency를 측정하거나 ICAP bandwidth에서 추정한다.

---

## 9. Metrics

### 9.1 Image/algorithm metrics

각 fixture/case마다 다음을 기록한다.

```text
mode selected
selected RM (`RM_NORMAL` or `RM_LOW_LIGHT`)
inactive RM
input size
output size
Y mean/std/min/max
saturation percentage
dark-ratio before/after
optional PSNR/SSIM against reference
```

### 9.2 Machine-vision metrics

Detector integration에서는 다음을 기록한다.

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

## 10. Dataset과 scenario

### 10.1 Synthetic C-sim fixtures

먼저 작은 deterministic fixture를 사용한다.

```text
NORMAL x3 -> LOW_LIGHT x3 -> NORMAL x1
```

목적:
- Mode stability 검증.
- Low-light trigger 검증.
- Recovery 검증.
- Bit-exact debugging을 쉽게 유지.

### 10.2 평가 데이터셋 — 조건별 real-RAW 쌍 (정본)

**§1.1 증명 전략(단일 모듈이 각각 자기 조건에서 최고 → 전환 필요)을
그대로 실험으로 옮기려면, 밝은 조도와 저조도 각각의 real-RAW 데이터셋
쌍이 필요하다.** 정본 평가 쌍은 다음과 같다.

```text
밝은 조도(bright):  PASCAL RAW dataset   -> normal 모듈이 최고를 낼 조건
저조도(low-light):  LOD RAW dataset      -> low-light 모듈이 최고를 낼 조건
```

- 둘 다 **real Bayer sensor RAW** 기반 검출 데이터셋이다 — pseudo-RAW
  (sRGB 역감마 합성)와 달리 실제 Poisson-Gaussian 센서 노이즈를 담고
  있어, low-light 모듈의 핵심 연산인 **binning(광량 적분/SNR 회복)의
  정당성**을 비로소 제대로 검증할 수 있다(pseudo-RAW에는 binning이 회수할
  실제 노이즈가 없다 — `results/principled-v3-refinement-2026-07-05.md` §3.4).
- **필요성(목표 1) 검증:** PASCAL RAW에서 `normal` arm이, LOD RAW에서
  `lowlight` arm이 각각 상대 arm보다 높은 mAP를 내는지(교차 우위)를 본다.
- **전환(목표 2) 검증:** 두 데이터셋을 섞은(또는 조건 라벨이 붙은) 스트림
  에서 `adaptive`(체커 라우팅)가 최적 단일 static arm을 상회하는지를 본다.

**이력(superseded proxy):** 초기 실험은 COCO/ExDark를 JPEG→pseudo-RAW로
역감마해 사용했고(§Stage 3 R1~R4), 실센서 검증은 SonyNOD(RAW-NOD, .ARW)로
수행했다(R3b/R4). 이 결과들은 정성적 근거로 유효하나, **정본 평가는 위
PASCAL RAW / LOD RAW 쌍으로 재수립**한다.

주의:
- JPEG/PNG dataset은 이미 ISP 처리된 데이터라 RAW-style ISP를 다시 적용하면
  double-processing artifact가 생긴다 — pseudo-RAW/real-RAW를 써야 하는 이유.
- arm 비교는 `normal`/`lowlight`/`adaptive` 세 가지로 한정한다(§1.2, `none` 제외).

**완료(2026-07-15/16):** 위 정본 평가가 실행됐다 — LOD_split(SonyNOD 321,
전량)·PASCAL_split(PASCALRAW ISO-stratified 321)·Shuffle_split(둘의 합,
642) × normal/lowlight/adaptive arm × BLC{16,1,2} 스윕, 27개 조합 전수
(YOLOv8n, mAP@[.5:.95]/@50). 결과: (1) **BLC 재보정(16→1~2)이 checker/adaptive
선택보다 훨씬 큰 mAP 레버**(최대 5.7배, LOD) — §1.1의 목표 1·2 논증과는
별개로 발견된 가장 큰 단일 효과, 배포 반영됨(BLC 2/2, 2026-07-20). (2)
LOD(야간)에서 adaptive≈lowlight(예상대로, §1.3 알고리즘 주장 지지). (3)
Shuffle(혼합)에서 "adaptive가 normal·lowlight 둘 다 이겨야 pass"라는
목표 2 검증 기준은 BLC=2에서만, 근소한 차이(+0.0002)로 충족 — "확실한 승리"로
과장하지 않음. 상세: `results/lod-pascal-isp-simulation-2026-07-15.md`.
Checker의 오라클 라벨 관문(#4)도 이 real-RAW 데이터 위에서 닫혔다 —
`results/checker-oracle-label-gate2-2026-07-20.md`.

---

## 11. Archived documents

이전 문서들은 ambiguity를 줄이고 active source of truth를 작게 유지하기 위해 archive했다.

Archive path:

```text
archive/docs-reorg-2026-07-01/
```

Archived material에는 다음이 포함된다.

```text
root historical worklogs and plans
old docs/ Architecture, Research_Roadmap, HW_SW_Interface, Analysis_Report
old docs/reference reports and tutorials
paper/ thesis drafts and figure/reference plans
```

이 파일들은 삭제된 것이 아니다. 역사적 참고 자료일 뿐이다. 그 안의 claim을 재사용하려면 현재 terminology에 맞춰 이 `RESEARCH.md`로 옮겨야 한다.

---

## 12. 즉시 수행할 다음 task

**주의:** 이번 reset(v2)은 문서 우선 정렬이다. 아래 task는 다음 단계(코드 마이그레이션)의
목표이며, 이 세션에서 바로 구현하지는 않는다.

### Task 1 — 전체 ISP pipeline RM 중심으로 HLS architecture 재작성

다음 방향으로 구현 또는 refactor한다(static baseline core 스테이지를 제거하고, 각 RM이
자기 ISP 데이터패스 전체를 소유하도록).

```text
rm_normal()       // BLC + demosaic + AWB/CCM + gain + gamma, stock Vitis Vision 기준
rm_low_light()    // binning-demosaic + 완화 BLC + AWB/CCM + gain + gamma
checker_select_mode()
dfx_ctrl_select_rm()
dfxisp_accel() shell wrapper with selected_rm metadata
```

### Task 2 — Python golden model 업데이트

Golden model은 다음을 포함해야 한다.

```text
RM_NORMAL 전체 ISP pipeline path
RM_LOW_LIGHT 전체 ISP pipeline path
shape policy
mode metadata
selected RM metadata
```

### Task 3 — Fixture 추가

필수 fixture:

```text
bright_normal_grid
low_light_dark_grid
mixed_dark_grid
threshold_boundary
bright_recovery_after_lowlight
odd_dimension_lowlight
```

### Task 4 — Report 업데이트

Report는 다음을 명시해야 한다.

```text
RM_NORMAL PASS/FAIL
RM_LOW_LIGHT PASS/FAIL
Mutually exclusive RM selection: PASS/FAIL
Output shape policy: H/2 x W/2 or H x W restored
```

### Task 5 — Ablation 보존

현재(v1) 공유 baseline core + tone RM 구현은 ablation/`Ref`로 유지한다.

```text
Ablation: v1_shared_baseline_core_plus_tone_rm
Status: not the main architecture (superseded by v2, §0)
Purpose: v1 vs v2 자원/전력/mAP 비교 기준
```

---

## 13. 현재 reset의 non-goals

수정된 C-sim/golden structure가 pass하기 전까지 다음에는 시간을 쓰지 않는다.

1. Full board bring-up.
2. DPU runtime integration.
3. Real partial bitstream swapping.
4. Power measurement.
5. Large mAP sweep.
6. Thesis prose polish.

즉시 우선순위는 architectural correctness다.

```text
static shell(비-ISP 제어/라우팅) + mode-specific 전체 ISP pipeline RM
RM_NORMAL: stock Vitis Vision 기준 ISP pipeline 전체
RM_LOW_LIGHT: binning-demosaic + 완화 BLC + AWB/CCM + low-light gain + low-light gamma
selected RM is mutually exclusive per frame/segment
static shell은 ISP 데이터패스를 전혀 포함하지 않는다
```

---

## 14. Reset acceptance criteria

Reset(v2)은 다음 조건을 만족하면 완료로 본다.

1. `README.md`와 `RESEARCH.md`가 유일한 active top-level research documents다.
2. Historical docs는 삭제하지 않고 archive한다.
3. `RESEARCH.md`가 static shell + mode-specific 전체 ISP pipeline RM architecture를 명확히 정의한다.
4. v1(현재 코드) 대비 v2(목표 아키텍처)의 차이가 문서화되어 있다(§0).
5. Next implementation target이 모호하지 않다.
6. Future reports는 다음을 구분한다.
   - `RM_NORMAL` path (전체 ISP pipeline)
   - `RM_LOW_LIGHT` path (전체 ISP pipeline)
   - v1 shared-baseline-core + tone-RM ablation(`Ref`)
   - register-only adaptive baseline (Arm 2)
   - DFX adaptive RM variant (Arm 3)
