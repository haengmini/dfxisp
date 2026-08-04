# Vitis-First DFXISP Refactor Strategy

> **상태(2026-07-20): 제안됐으나 미착수.** 이 문서는 2026-07-03에 작성된
> 계획이다 — `src/`에 `base_vitis.cpp`/`check.cpp`/`tone.cpp`/`ctrl.cpp`/
> `shell.cpp`/`TERMS.md` 등 Task 1~18의 어떤 산출물도 아직 존재하지 않는다.
> 2026-07-04~20 사이 실제로 진행된 작업은 이 문서와 무관한 checker/BLC
> real-RAW 재보정 트랙(`ROADMAP.md` Stage 1·3 후속)이었다 — 이 문서가
> 폐기된 것은 아니고, 우선순위상 뒤로 밀렸을 뿐이다. 착수 여부·시점은
> 미결정(`ROADMAP.md` "즉시 다음" §7 참고). 아래 계획 본문은 착수 시
> 그대로 유효하다.

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

> **정본 프레이밍 (2026-07-10):** 연구 목표는 RESEARCH.md §1이 정본이다 —
> 목표 1(저조도 특화 모듈 필요성, 단일 모듈이 각각 자기 조건 데이터셋에서
> 최고 → 전환 필요) + 목표 2(DFX 전환으로 효율·성능, SW→HW 증명). 본
> Vitis-first 재정렬은 이 두 목표를 **HW 구현 측면에서 뒷받침하는 리팩터
> 방향**이다. arm은 normal/lowlight/adaptive(`none` 제외).

> **⚠️ 개정 (2026-07-10, 같은 날 후속 — RESEARCH.md §0 reset v2와 동기화):**
> 이 문서를 처음 쓸 때는 "Base(Vitis Vision ISP)는 static, DFX는 그 앞에 붙는 작은
> Tone 모듈만 swap"(§9 Q4 구 답변: "RP = Tone only")이 권장안이었다. **그 결정은
> 뒤집혔다.** 이유: Tone만 스왑하면 재구성 단위가 너무 작아서(gain/gamma 수준)
> register-only(Arm 2)로 둘 다 상주시켜도 자원 비용이 무시할 만해, DFX(Arm 3)의
> 존재 이유(목표 2) 자체가 약해진다. **새 결정: Base와 Tone을 합쳐 전체 ISP
> pipeline 하나로 만들고, 그 전체를 RP로 스왑한다.** Base는 더 이상 별도 static
> 스테이지가 아니라 `RM_NORMAL`의 내용물이 되고, Tone(저조도 전용)은 `RM_LOW_LIGHT`의
> 내용물이 된다. 이 변경이 아래 §0/§3.1/§3.4/§3.5/§9 Q2·Q4/§11에 반영됐다 —
> 코드 파일 분리(Base/Check/Tone/Ctrl/Shell 모듈) 자체는 여전히 유효한 조직화이지만,
> **HLS synthesis top 단위**가 달라진다: `base_vitis_top`/`tone_normal_top`처럼
> 따로 합성하던 것을, `rm_normal_top`(Base+Normal Tone 통합)과 `rm_low_light_top`
> (Base+Dark Tone 통합) 두 개로 합친다(§Phase 4 Task 16~18 갱신).

**Goal:** 현재 DFXISP 파일들을 "Vitis Vision Library 기준 ISP를 `RM_NORMAL`로, 저조도 특화 ISP를 `RM_LOW_LIGHT`로 나란히 구현하고, DFX가 그 둘을 통째로 swap"하는 구조로 재정렬한다.

**Architecture:** AMD Vitis Vision L1 `xf::cv` ISP stage를 `RM_NORMAL`의 구현으로 삼고, 저조도 특화 ISP를 `RM_LOW_LIGHT`로 나란히 둔다. 두 ISP 파이프라인 모두 재구성 영역(RP) 안에 있다 — "자체 ISP를 새로 만든다"도 아니고 "Vitis Base를 고정한 채 작은 확장만 붙인다"도 아니다. Static으로 남는 것은 Check(checker)와 DFX Ctrl뿐이다.

**Tech Stack:** Vitis HLS 2024.1, Vitis Vision L1 `xf::cv`, C++17, ZCU104, AXI4-MM, AXI-Lite, DFX/RP shell, Python verification scripts.

---

## 0. 핵심 방향

기존(v0) 방향:

```text
자체 baseline core + 자체 RM + 자체 checker + 자체 controller
```

v1(2026-07-03, superseded) 방향:

```text
Vitis Vision Base(static) + DFXISP 확장 Tone 모듈(RP)
```

**v2(2026-07-10, 정본) 방향:**

```text
Vitis Vision 기준 RM_NORMAL + 저조도 특화 RM_LOW_LIGHT, 둘 다 RP
```

새 top-level 개념:

```text
RAW frame
  -> Check          # 장면 판단 (static)
  -> DFX Ctrl       # mode/RM 선택 (static)
  -> ISP RP         # RM_NORMAL 또는 RM_LOW_LIGHT, 전체 ISP pipeline 통째로 재구성
                    #   RM_NORMAL     = Vitis Vision 기준 ISP (구 "Base"+"Normal Tone")
                    #   RM_LOW_LIGHT  = 저조도 특화 ISP (구 "Base"+"Dark Tone")
  -> RGB frame
```

중요 원칙:

1. **`RM_NORMAL`은 Vitis Vision 기준으로 구현한다.** ("Base"라는 이름의 별도 static
   스테이지는 없다 — Vitis Vision 구현이 곧 `RM_NORMAL`의 전체 내용물이다.)
2. **DFXISP는 ISP를 대체하는 게 아니라, 조도별로 다른 ISP 전체를 RP로 스왑한다.**
3. **짧고 직관적인 용어만 사용.**
4. **기존 자체 구현(v0)은 바로 삭제하지 말고 `legacy`/`ref`로 격리.**
5. **논문에서는 "static Check/DFX Ctrl + RP 전체 ISP(Normal/Low-light)" 구조로 설명.**

---

## 1. 짧은 용어 표준

앞으로 긴 이름을 줄인다.

| 새 용어 | 의미 | 기존/긴 표현 |
|---|---|---|
| **Base** | **(v1 한정, superseded)** Vitis Vision 기준 static baseline ISP. v2에서는 별도 static 스테이지가 아니라 `RM_NORMAL`의 내부 구현을 가리키는 이름으로만 남는다 | shared baseline ISP core, baseline_isp_core |
| **Check** | 조도/장면 판단기 (static) | scene checker, checker_select_mode |
| **Tone** | **(v1 한정, superseded)** mode별 전처리/톤 보정만 담당하던 RM. v2에서는 각 RM이 ISP 전체(BLC/AWB/demosaic/CCM/gain/gamma)를 소유하므로 "Tone"은 그 안의 gain/gamma 부분만 가리키는 좁은 의미로 축소 | mode-specific tone RM |
| **RM_NORMAL** | 일반 조도 전체 ISP pipeline RM (구 Base+Normal Tone 통합, Vitis Vision 기준) | RM_NORMAL_TONE |
| **RM_LOW_LIGHT** | 저조도 특화 전체 ISP pipeline RM (구 Base+Dark Tone 통합) | RM_LOW_LIGHT_TONE |
| **DFX Ctrl** | mode/RM 선택 및 재구성 제어 (static) | DFX controller, PR controller |
| **Shell** | static(Check+DFX Ctrl+AXI+packer) + RP(ISP RM) 연결 top | DFX static shell |
| **RP** | 재구성 영역 — v2에서는 전체 ISP pipeline(`RM_NORMAL`/`RM_LOW_LIGHT`) 단위 | Reconfigurable Partition |
| **Ref** | 비교용/legacy 구현(v0, v1 모두 포함) | old in-house baseline |

코드 네이밍도 가능하면 아래처럼 맞춘다.

```text
base_*       Vitis Vision baseline
check_*      scene checker
 tone_*      normal/dark tone modules
ctrl_*       DFX controller
shell_*      top/static wrapper
ref_*        old reference/legacy path
```

---

## 2. 목표 파일 구조

현재 `isppipeline/hls/`를 한 번에 뒤엎지 말고, Vitis-first 구조를 병렬로 만든 뒤 전환한다.

```text
isppipeline/
  hls/
    include/
      dfxisp_accel.hpp              # 기존 top API, 전환 기간 유지
      dfxisp_types.hpp              # 공통 type/mode/metadata
      base_vitis.hpp                # Vitis Vision ISP 구현 선언 (RM_NORMAL 내부에서 호출)
      check.hpp                     # Check 선언
      tone.hpp                      # Normal/Dark 저조도 전용 tone 처리 선언
      ctrl.hpp                      # DFX Ctrl 선언
      rm_normal.hpp                 # RM_NORMAL top 선언 (base_vitis 통합, RP)
      rm_low_light.hpp              # RM_LOW_LIGHT top 선언 (tone_dark + 저조도 ISP 통합, RP)
      shell.hpp                     # Shell/top 선언
    src/
      dfxisp_accel.cpp              # 최종 top wrapper, shell 호출
      base_vitis.cpp                # Vitis Vision 구현 (RM_NORMAL의 내부 building block)
      check.cpp                     # Check 구현 (static)
      tone.cpp                      # 저조도 전용 tone 처리 구현 (RM_LOW_LIGHT의 내부 building block)
      ctrl.cpp                      # DFX Ctrl 구현 (static)
      rm_normal.cpp                 # RM_NORMAL top: base_vitis 호출, RP 단위
      rm_low_light.cpp              # RM_LOW_LIGHT top: tone + 저조도 ISP 호출, RP 단위
      ref_legacy.cpp                # 기존 자체 baseline/RM 보존
    tests/
      test_base_vitis_csim.cpp
      test_check_csim.cpp
      test_tone_csim.cpp
      test_rm_normal_csim.cpp
      test_rm_low_light_csim.cpp
      test_shell_csim.cpp
    tools/
      gen_base_vectors.py
      compare_base_ref.py
      gen_shell_vectors.py
    reports/
      latest.md
      vitis_first_refactor.md
```

**v2 변경(2026-07-10):** `base_vitis.*`/`tone.*`는 내부 building block으로 남지만, **HLS
합성/DFX 대상 top은 더 이상 `base_vitis_top` 하나가 아니다** — `rm_normal_top`(base_vitis
호출)과 `rm_low_light_top`(tone + 저조도 ISP 호출) 두 개가 RP 후보가 된다. `base_vitis_top`은
단독 검증(csim/csynth)용으로는 유지해도 되지만, Vivado DFX partition 정의에는 쓰지 않는다(§Phase 4).

기존 `src/dfxisp_accel.cpp`의 로직은 최종적으로 줄인다.

```cpp
extern "C" void dfxisp_accel(...) {
    shell_run(...);
}
```

---

## 3. 새 아키텍처 정의

### 3.1 RM_NORMAL — Vitis Vision 기준 전체 ISP pipeline (구 "Base", RP)

**역할:** 일반 조도 ISP 전체. AMD Vitis Vision Library로 만들고, 그 자체가 `RM_NORMAL`의
전체 내용물이다 — 이 파이프라인 앞뒤에 별도 static core가 없다.

RM_NORMAL pipeline:

```text
RAW Bayer
  -> black level
  -> demosaic
  -> AWB / color correction
  -> CCM
  -> gain
  -> gamma
  -> RGB
```

가능한 Vitis Vision block:

```text
xf::cv::blackLevelCorrection
xf::cv::gaincontrol or AWB-equivalent gain stage
xf::cv::demosaicing
xf::cv::colorcorrectionmatrix
xf::cv::gammacorrection
```

`RM_NORMAL`은 DFXISP 논문의 기준선이자, 동시에 **재구성 영역(RP)의 한 variant**다 — static이
아니다(§9 Q4 참고, 2026-07-10 결정 변경).

### 3.2 Check — 장면 판단

**역할:** RAW frame이 어두운지 판단한다.

입력:

```text
raw_bayer, width, height, threshold
```

출력:

```text
mode = NORMAL or DARK
```

초기 구현은 단순하게 유지한다.

```text
dark_ratio = dark_pixel_count / total_pixel_count
if dark_ratio > ratio_threshold: DARK
else: NORMAL
```

나중에 평균 밝기, histogram, tile 기반 판단으로 확장 가능하지만 초기에는 추가하지 않는다.

### 3.3 RM_LOW_LIGHT — 저조도 특화 전체 ISP pipeline (구 "Dark Tone + Base", RP)

**역할:** 저조도 ISP 전체. `RM_NORMAL`과 마찬가지로 이 자체가 전체 내용물이며, 별도
static core를 거치지 않는다.

```text
RAW -> 2x2 binning-demosaic -> 완화 BLC -> 저조도 AWB/CCM -> 저조도 gain -> 저조도 gamma -> RGB
```

중요(2026-07-10 변경): 이전 버전은 "Tone이 Base 입력을 개선해 Base로 넘긴다"는 전제였다 —
이 전제는 폐기됐다. `RM_LOW_LIGHT`는 Base를 거치지 않는다. **자기 자신이 BLC/AWB/CCM까지
포함한 완결된 ISP다.** 이래야 저조도 전용 BLC/AWB 파라미터(또는 알고리즘 자체)를 정상조도
파이프라인과 독립적으로 튜닝할 수 있다 — RESEARCH.md §2.3 "v1 대비 근거" 참고(공유 core의
정적 WB/BLC가 저조도 mAP 손실의 ~70% 원인이었던 실측 결과).

### 3.4 DFX Ctrl — RM 선택

**역할:** Check 결과에 따라 `RM_NORMAL`/`RM_LOW_LIGHT` **전체 ISP pipeline**을 선택한다
(Tone만 고르던 구 버전과 달리, 전체 RP variant를 고른다).

시뮬레이션 단계:

```text
selected_mode
selected_rm
out_width
out_height
```

DFX 단계:

```text
rp_select
pr_start
pr_done
pr_error
```

### 3.5 Shell — 전체 연결

Shell은 top-level static wrapper다. Shell 자체는 ISP 데이터패스를 포함하지 않는다 — RM
전체(`RM_NORMAL` 또는 `RM_LOW_LIGHT`)를 통째로 호출/스왑할 뿐이다.

```text
Shell(static) = Check + DFX Ctrl + AXI/packer
RP            = RM_NORMAL 또는 RM_LOW_LIGHT (전체 ISP pipeline, mutually exclusive)
```

최종 `dfxisp_accel`은 Shell을 호출하고, Shell은 선택된 RM을 호출한다.

---

## 4. 단계별 수정 전략

## Phase 1 — 문서/용어 먼저 고정

### Task 1: `TERMS.md` 생성

**Objective:** 짧은 용어를 repo 전체 기준으로 고정한다.

**Files:**
- Create: `TERMS.md`
- Modify: `README.md`
- Modify: `RESEARCH.md`
- Modify: `SPEC.md`

**Content:**

```markdown
# DFXISP Terms

| Term | Meaning |
|---|---|
| Check | scene/darkness checker (static) |
| DFX Ctrl | DFX/RM selection controller (static) |
| RM_NORMAL | full ISP pipeline, Vitis Vision based (reconfigurable) |
| RM_LOW_LIGHT | full ISP pipeline, low-light specialized (reconfigurable) |
| Shell | static top wrapper: Check + DFX Ctrl + AXI/packer only (no ISP datapath) |
| RP | reconfigurable partition — holds RM_NORMAL or RM_LOW_LIGHT, mutually exclusive |
| Ref | old or comparison implementation (v0/v1) |
| Base (deprecated) | v1 term for a static shared ISP core; superseded — see RM_NORMAL |
| Tone (deprecated) | v1 term for a small pre-Base tone RM; superseded — each RM now owns the full pipeline |
```

**Verification:**

```bash
rg -n "shared baseline ISP core|mode-specific tone RM|RM_LOW_LIGHT_TONE|checker_select_mode" README.md RESEARCH.md SPEC.md isppipeline/hls/README.md
```

Expected: old terms may remain in historical/v1 sections (explicitly marked as superseded), but active architecture sections use RM_NORMAL/RM_LOW_LIGHT/Check/DFX Ctrl/Shell.

> **완료 상태(2026-07-10):** README.md/RESEARCH.md/SPEC.md의 아키텍처 섹션은 이미 이
> 문서 초입의 "⚠️ 개정" 노트에 따라 갱신됐다(v2: RP=전체 ISP pipeline). 아래 Task 2~4의
> 문구는 v1 결정("Static Base, RP Tone only") 기준으로 작성된 예시라 실제 반영된 문구와
> 다르다 — 실제로는 아래를 대체하는 방향(RM_NORMAL/RM_LOW_LIGHT 전체가 RP)으로 반영됐다.
> Task 2~4 예시 문구는 과거 결정을 보여주는 기록으로만 남기고, 코드 마이그레이션
> 단계에서 실제 문서 최신본(README.md/RESEARCH.md/SPEC.md)을 참조할 것.

---

### Task 2: `README.md`를 Vitis-first 구조로 수정 (v1 예시, 실제로는 다르게 반영됨 — 위 노트 참고)

**Objective:** 첫 화면에서 연구 방향이 바로 보이게 한다.

**Files:**
- Modify: `README.md`

**v1 예시(superseded) — 실제로는 반영되지 않음:**

```text
DFXISP = Vitis Base + DFX Extension

RAW
  -> Check
  -> DFX Ctrl
  -> Tone(Normal/Dark)
  -> Base(Vitis Vision ISP)
  -> RGB
```

**v2 실제 반영(README.md "Active architecture" 참고):**

```text
RAW
  -> Check (static)
  -> DFX Ctrl (static)
  -> RM_NORMAL 또는 RM_LOW_LIGHT (전체 ISP pipeline, RP)
  -> output packer (static)
  -> RGB
```

```markdown
DFXISP는 static shell(checker + DFX 컨트롤러)만 고정하고, 조도 조건에 따라
Vitis Vision 기준 ISP 전체(RM_NORMAL) 또는 저조도 특화 ISP 전체(RM_LOW_LIGHT)를
DFX로 통째로 교체하는 구조다.
```

**Avoid:**

```text
자체 baseline core가 기준이다
Base는 static이고 Tone만 재구성된다   # v1 결정, superseded
```

---

### Task 3: `RESEARCH.md` 핵심 논지를 재작성 (v1 예시, 실제로는 다르게 반영됨 — 위 노트 참고)

**Objective:** 논문 논지를 갱신한다.

**Files:**
- Modify: `RESEARCH.md`

**v1 예시(superseded):**

```markdown
Core thesis:
A Vitis Vision based Base ISP can be kept as a stable reference path, while DFXISP adds a small reconfigurable Tone stage and DFX Ctrl around it to improve dark-scene machine-vision robustness without rewriting the whole ISP pipeline.
```

**v2 실제 반영(RESEARCH.md §0/§1.3 참고):**

```markdown
Core thesis:
DFXISP keeps only non-ISP control/routing (Check, DFX Ctrl, AXI shell, output packer)
static, and reconfigures the entire ISP datapath (BLC/AWB/demosaic/CCM/gain/gamma) as
one mutually-exclusive RM per lighting mode — RM_NORMAL (Vitis Vision based) or
RM_LOW_LIGHT (low-light specialized) — so that the DFX swap unit is large enough to
make the resource/power benefit over a register-only design (Arm 2) defensible.
```

```markdown
핵심 논지(한글):
DFXISP는 비-ISP 제어/라우팅(Check, DFX 컨트롤러, AXI 셸, output packer)만 static으로
남기고, ISP 데이터패스 전체(BLC/AWB/demosaic/CCM/gain/gamma)를 조도별로 상호배타적인
하나의 RM(RM_NORMAL 또는 RM_LOW_LIGHT)으로 재구성한다 — 스왑 단위를 충분히 크게 잡아야
register-only 설계(Arm 2) 대비 자원/전력 이득(목표 2)이 방어 가능하기 때문이다.
```

---

### Task 4: `SPEC.md`에 module contract 추가 (v1 예시, 실제로는 다르게 반영됨 — 위 노트 참고)

**Objective:** Check/DFX Ctrl/RM_NORMAL/RM_LOW_LIGHT/Shell의 입출력 계약을 고정한다.

**Files:**
- Modify: `SPEC.md`

**v2 방향으로 갱신한 Add section (v1 "Base"/"Tone" 분리는 superseded):**

```markdown
## Module Contracts

### RM_NORMAL (reconfigurable, full ISP pipeline)
- Input: RAW Bayer frame
- Output: RGB888/RGB32 frame
- Implementation target: Vitis Vision L1
- Owns: BLC, demosaic, AWB/CCM, gain, gamma
- Must not contain DFX policy logic

### RM_LOW_LIGHT (reconfigurable, full ISP pipeline)
- Input: RAW Bayer frame
- Output: RGB888/RGB32 frame
- Owns: binning-demosaic, relaxed BLC, AWB/CCM, gain, gamma
- Must not contain DFX policy logic

### Check (static)
- Input: RAW Bayer frame, threshold
- Output: mode
- Must be deterministic and cheap

### DFX Ctrl (static)
- Input: mode from Check
- Output: selected RM (RM_NORMAL or RM_LOW_LIGHT), metadata, optional PR control signals

### Shell (static)
- Input: top-level AXI buffers and scalar controls
- Output: RGB buffer and metadata
- Composition: Check + DFX Ctrl + AXI/packer, calling into the selected RM (RP)
```

---

## Phase 2 — 코드 구조 분리

### Task 5: 공통 type header 생성

**Objective:** 기존 enum/metadata를 짧은 이름으로 정리한다.

**Files:**
- Create: `isppipeline/hls/include/dfxisp_types.hpp`
- Modify: `isppipeline/hls/include/dfxisp_accel.hpp`

**Proposed content:**

```cpp
#pragma once

#include <cstdint>

namespace dfxisp {

enum class Mode : int {
    Normal = 0,
    Dark = 1,
    Auto = 2,
};

enum class ToneId : int {
    Normal = 0,
    Dark = 1,
};

struct Meta {
    int out_w;
    int out_h;
    int mode;
    int tone;
};

} // namespace dfxisp
```

**Compatibility rule:** keep old C ABI enum values in `dfxisp_accel.hpp` until all tests are migrated.

---

### Task 6: Check module 분리

**Objective:** `checker_select_mode()`를 `check.cpp/hpp`로 이동한다.

**Files:**
- Create: `isppipeline/hls/include/check.hpp`
- Create: `isppipeline/hls/src/check.cpp`
- Create: `isppipeline/hls/tests/test_check_csim.cpp`
- Modify later: `isppipeline/hls/src/dfxisp_accel.cpp`

**API:**

```cpp
#pragma once
#include <cstdint>
#include "dfxisp_types.hpp"

namespace dfxisp {

Mode check_frame(const uint16_t* raw, int width, int height, Mode req_mode, uint16_t dark_threshold);

}
```

**Test cases:**

- forced Normal returns Normal
- forced Dark returns Dark
- Auto bright returns Normal
- Auto dark returns Dark
- boundary case documented: `dark * 100 > ratio * n`

**Verification:**

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -Iinclude src/check.cpp tests/test_check_csim.cpp -o build/test_check_csim
./build/test_check_csim
```

Expected:

```text
Check C-sim PASS
```

---

### Task 7: Base module 생성 — Vitis Vision target wrapper

**Objective:** Base를 별도 파일로 만들고, Vitis Vision implementation target을 명시한다.

**Files:**
- Create: `isppipeline/hls/include/base_vitis.hpp`
- Create: `isppipeline/hls/src/base_vitis.cpp`
- Create: `isppipeline/hls/tests/test_base_vitis_csim.cpp`

**Two-step implementation rule:**

1. **Stage 1:** host C-sim fallback implementation with identical API, so CI can run without Vitis include path.
2. **Stage 2:** real `xf::cv` implementation guarded by a compile flag.

**API:**

```cpp
#pragma once
#include <cstdint>

namespace dfxisp {

void base_run(
    const uint16_t* raw,
    uint32_t* rgb,
    int width,
    int height);

}
```

**Compile flags:**

```cpp
#ifdef DFXISP_USE_VITIS_VISION
// include xf::cv headers and use Vitis Vision L1
#else
// host fallback for local tests
#endif
```

**Why fallback is allowed:** local Ubuntu/Hermes may not have Vitis Vision headers loaded. The fallback is for testability only. The paper baseline claim requires the `DFXISP_USE_VITIS_VISION` build to pass.

---

### Task 8: Vitis Vision Base 실제 구현 경로 작성

**Objective:** `base_vitis.cpp`에 실제 Vitis Vision L1 path를 추가한다.

**Files:**
- Modify: `isppipeline/hls/src/base_vitis.cpp`
- Modify: `isppipeline/hls/Makefile`
- Modify: `isppipeline/hls/scripts/vitis_hls.tcl`

**Target stage order:**

```text
blackLevelCorrection
gaincontrol/AWB static gain
xf::cv::demosaicing
colorcorrectionmatrix identity
gammacorrection
```

**Implementation note:** exact function signatures must be checked against installed Vitis Vision 2024.1 headers before coding. Do not invent signatures.

**Verification command:**

```bash
cd isppipeline/hls
DFXISP_USE_VITIS_VISION=1 DFXISP_HLS_TOP=base_vitis_top make hls
```

Expected:

```text
Vitis HLS csim PASS
```

If Vitis headers are unavailable, stop and report:

```text
Blocked: Vitis Vision headers not found in configured Vitis HLS environment.
```

---

### Task 9: Tone module 분리

**Objective:** Normal/Dark 전처리를 `tone.cpp/hpp`로 이동한다.

**Files:**
- Create: `isppipeline/hls/include/tone.hpp`
- Create: `isppipeline/hls/src/tone.cpp`
- Create: `isppipeline/hls/tests/test_tone_csim.cpp`

**API:**

```cpp
#pragma once
#include <cstdint>
#include "dfxisp_types.hpp"

namespace dfxisp {

void tone_normal(
    const uint16_t* raw_in,
    uint16_t* raw_out,
    int width,
    int height);

void tone_dark(
    const uint16_t* raw_in,
    uint16_t* raw_out,
    int width,
    int height,
    int* out_w,
    int* out_h);

}
```

**Design choice:** Tone output should be Base-compatible. If Dark changes shape, metadata must report it clearly.

**Initial behavior:**

- Normal: pass-through or light exposure normalize.
- Dark: current binning/gain logic, but format adjusted so Base can consume it.

**Verification:**

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -Iinclude src/tone.cpp tests/test_tone_csim.cpp -o build/test_tone_csim
./build/test_tone_csim
```

Expected:

```text
Tone C-sim PASS
```

---

### Task 10: DFX Ctrl module 생성

**Objective:** mode/RM 선택과 metadata 생성을 분리한다.

**Files:**
- Create: `isppipeline/hls/include/ctrl.hpp`
- Create: `isppipeline/hls/src/ctrl.cpp`
- Create: `isppipeline/hls/tests/test_ctrl_csim.cpp`

**API:**

```cpp
#pragma once
#include "dfxisp_types.hpp"

namespace dfxisp {

ToneId ctrl_select_tone(Mode mode);

void ctrl_write_meta(
    int out_w,
    int out_h,
    Mode mode,
    ToneId tone,
    int* meta_w,
    int* meta_h,
    int* meta_mode,
    int* meta_tone);

}
```

**Future DFX extension:** PR start/done signals are not added in this first refactor unless a Vivado DFX shell is being integrated.

---

### Task 11: Shell module 생성

**Objective:** Check/DFX Ctrl(static)과 RM_NORMAL/RM_LOW_LIGHT(RP)를 하나로 연결한다.

**Files:**
- Create: `isppipeline/hls/include/shell.hpp`
- Create: `isppipeline/hls/src/shell.cpp`
- Create: `isppipeline/hls/tests/test_shell_csim.cpp`
- Modify: `isppipeline/hls/src/dfxisp_accel.cpp`

**API:**

```cpp
#pragma once
#include <cstdint>

namespace dfxisp {

void shell_run(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t dark_pixel_threshold,
    int* out_width,
    int* out_height,
    int* selected_mode,
    int* selected_tone);

}
```

**Flow (v2 — RM은 전체 ISP pipeline, Base 단계로 다시 넘기지 않는다):**

```cpp
Mode m = check_frame(...);
RmId r = ctrl_select_rm(m);
if (r == RmId::LowLight) rm_low_light(raw_bayer, rgb_out, width, height, out_w, out_h);
else                      rm_normal(raw_bayer, rgb_out, width, height, out_w, out_h);
ctrl_write_meta(...);
```

**Important:** `rm_normal`/`rm_low_light` 각각 내부에서 `base_vitis`/`tone` building block을
호출해 BLC→demosaic→AWB/CCM→gain→gamma까지 전부 끝낸다 — shell은 그 출력을 그대로 받아
metadata만 채운다. HLS로 옮길 때는 각 RM 내부를 streaming/line-buffer로 바꾼다.

---

### Task 12: 기존 구현을 Ref로 보존

**Objective:** 현재 자체 구현을 잃지 않고 비교 대상으로 격리한다.

**Files:**
- Create: `isppipeline/hls/src/ref_legacy.cpp`
- Create: `isppipeline/hls/include/ref_legacy.hpp`
- Modify: `isppipeline/hls/src/dfxisp_accel.cpp`

**Move or copy:**

- `demosaic_rggb12`
- `apply_blc_wb12`
- `run_normal`
- `run_low_light`
- current gamma LUT

**Rule:** Ref는 논문 기준 baseline이 아니다. Ref는 regression comparison 용도다.

---

## Phase 3 — 검증 체계 재작성

### Task 13: Base vs Ref 비교 스크립트 작성

**Objective:** Vitis Base와 기존 Ref의 차이를 수치로 남긴다.

**Files:**
- Create: `isppipeline/hls/tools/compare_base_ref.py`
- Output: `isppipeline/hls/results/base_ref_compare.csv`
- Output: `isppipeline/hls/results/base_ref_compare.md`

**Metrics:**

```text
MAE_R, MAE_G, MAE_B
MAXE_R, MAXE_G, MAXE_B
PSNR_RGB
exact_match_ratio
channel_swap_check
```

**Fixtures:**

```text
gray ramp
color patch
bright grid
dark visible grid
mixed brightness grid
```

**Verification:**

```bash
python3 tools/compare_base_ref.py --out results/base_ref_compare.md
```

Expected:

```text
Base/Ref comparison written
```

---

### Task 14: Golden vector naming 정리

**Objective:** golden이 무엇의 golden인지 명확히 한다.

**Files:**
- Rename or create:
  - `tests/base_golden.csv`
  - `tests/shell_golden.csv`
  - `tests/ref_golden.csv`
- Modify: `tools/gen_golden_vectors.py` or split into:
  - `tools/gen_base_vectors.py`
  - `tools/gen_shell_vectors.py`

**Rule:**

```text
base_golden = Vitis Base expected output
shell_golden = full DFXISP output
ref_golden = legacy comparison output
```

Avoid generic `golden_vectors.csv` once refactor starts.

---

### Task 15: Makefile targets 정리

**Objective:** 짧은 명령으로 Base/Check/Tone/Shell을 따로 검증한다.

**Files:**
- Modify: `isppipeline/hls/Makefile`

**Add targets:**

```make
check-csim:
	$(CXX) $(CXXFLAGS) src/check.cpp tests/test_check_csim.cpp -o $(BUILD_DIR)/check_csim
	./$(BUILD_DIR)/check_csim

tone-csim:
	$(CXX) $(CXXFLAGS) src/tone.cpp tests/test_tone_csim.cpp -o $(BUILD_DIR)/tone_csim
	./$(BUILD_DIR)/tone_csim

base-csim:
	$(CXX) $(CXXFLAGS) src/base_vitis.cpp tests/test_base_vitis_csim.cpp -o $(BUILD_DIR)/base_csim
	./$(BUILD_DIR)/base_csim

shell-csim:
	$(CXX) $(CXXFLAGS) src/base_vitis.cpp src/check.cpp src/tone.cpp src/ctrl.cpp src/shell.cpp tests/test_shell_csim.cpp -o $(BUILD_DIR)/shell_csim
	./$(BUILD_DIR)/shell_csim

vitis-first-verify: check-csim tone-csim base-csim shell-csim
```

**Verification:**

```bash
make vitis-first-verify
```

Expected:

```text
Check C-sim PASS
Tone C-sim PASS
Base C-sim PASS
Shell C-sim PASS
```

---

## Phase 4 — HLS/DFX 정렬

> **2026-07-10 결정 변경:** 아래 Task 16~18은 원래 "Base는 static, Tone만 RP"
> 결정(v1) 기준으로 쓰여 있었다. §0 상단 개정 노트대로 뒤집혔다 — `base_vitis_top`은
> standalone 검증용으로만 남고, **실제 DFX partition은 `rm_normal_top`/`rm_low_light_top`
> (각각 Base+Tone 통합)**이다.

### Task 16: Vitis Base standalone 검증 target 추가 (DFX partition 아님)

**Objective:** `base_vitis`만 따로 C-sim/csynth로 검증할 수 있게 한다 — 단, 이 top은
DFX partition으로 쓰이지 않는다(그건 Task 17의 `rm_normal_top`/`rm_low_light_top`).

**Files:**
- Modify: `isppipeline/hls/scripts/vitis_hls.tcl`
- Modify: `isppipeline/hls/Makefile`

**Targets:**

```text
base_vitis_top     # standalone 검증 전용, Vivado DFX partition 아님
shell_top / dfxisp_accel
```

**Command:**

```bash
DFXISP_HLS_TOP=base_vitis_top DFXISP_HLS_FLOW=csynth make hls
```

**Expected report:**

```text
reports/csynth/base_vitis_top_csynth.rpt
```

---

### Task 17: RM_NORMAL/RM_LOW_LIGHT top을 RP-compatible하게 맞춤 (Base+Tone 통합)

**Objective:** `RM_NORMAL`과 `RM_LOW_LIGHT`가 각각 Base+Tone을 내부에서 호출하는
완결된 top이 되게 하고, 둘이 같은 RP port list를 갖게 한다.

**Files:**
- Modify: `isppipeline/hls/src/rm_normal.cpp` (base_vitis 호출)
- Modify: `isppipeline/hls/src/rm_low_light.cpp` (tone + 저조도 ISP 호출)
- Modify: `isppipeline/hls/include/rm_normal.hpp`, `rm_low_light.hpp`
- Modify: `isppipeline/hls/scripts/vitis_hls.tcl`

**Required top signatures:**

```cpp
extern "C" void rm_normal_top(
    const uint16_t* raw_in,
    uint32_t* rgb_out,
    int width,
    int height,
    int* out_width,
    int* out_height);

extern "C" void rm_low_light_top(
    const uint16_t* raw_in,
    uint32_t* rgb_out,
    int width,
    int height,
    int* out_width,
    int* out_height);
```

Same ports, same bundles, same control interface. **각 top은 raw 입력부터 RGB32
출력까지 전체 ISP를 끝낸다** — Base로 다시 넘기는 중간 단계가 없다.

**Verification:**

```bash
DFXISP_HLS_TOP=rm_normal_top DFXISP_HLS_FLOW=csynth make hls
DFXISP_HLS_TOP=rm_low_light_top DFXISP_HLS_FLOW=csynth make hls
```

Expected: both synthesize and expose compatible ports.

---

### Task 18: DFX Ctrl을 Vivado DFX 연결용으로 문서화

**Objective:** C-sim controller와 실제 PR controller의 boundary를 명확히 한다.

**Files:**
- Modify: `isppipeline/hls/results/dfx-vivado-considerations-2026-07-03.md`
- Create: `isppipeline/hls/results/vitis-first-dfx-boundary.md`

**채택된 결정(2026-07-10, RESEARCH.md §0/§2.3과 동기화):**

```text
Static: Check + DFX Ctrl + AXI shell (ISP 데이터패스 없음)
RP: RM_NORMAL(Base+Normal Tone 통합) 또는 RM_LOW_LIGHT(Base+Dark Tone 통합)
```

**폐기된 대안(v1, 2026-07-03 당시 권장이었으나 뒤집힘):**

```text
Static: Check + DFX Ctrl + Base + AXI shell
RP: Tone(Normal/Dark)만
```

Reason(폐기 사유): Tone만 스왑하면 재구성 단위가 너무 작아(gain/gamma 수준) register-only
(Arm 2)로 둘 다 상주시켜도 자원 비용이 무시할 만해, DFX(Arm 3)의 자원/전력 이득(목표 2)이
방어되지 않는다. Base까지 RP에 포함해야 Arm 2(두 개 full ISP 상주) 대비 Arm 3(하나만 상주)의
격차가 실질적으로 커진다.

---

## 5. 논문/발표 서술 전략

### 짧은 구조 표현

```text
DFXISP = Check + DFX Ctrl (static) + [RM_NORMAL | RM_LOW_LIGHT] (RP, 전체 ISP)
```

### 한 문장 설명

```text
Check와 DFX Ctrl만 static이고, DFXISP는 Vitis Vision 기준 ISP 전체(RM_NORMAL)와
저조도 특화 ISP 전체(RM_LOW_LIGHT)를 장면에 따라 통째로 재구성하는 구조다.
```

### English wording

```text
DFXISP keeps only Check and DFX Ctrl static, and reconfigures the entire ISP datapath
as one mutually-exclusive RM per lighting mode: RM_NORMAL (Vitis Vision based) or
RM_LOW_LIGHT (low-light specialized).
```

### Korean wording

```text
DFXISP는 Check와 DFX Ctrl만 static으로 두고, Vitis Vision 기준 ISP 전체(RM_NORMAL)와
저조도 특화 ISP 전체(RM_LOW_LIGHT) 중 조도에 따라 하나를 통째로 재구성하는 구조다.
```

### Figure label

```text
RAW -> Check -> DFX Ctrl -> [RM_NORMAL | RM_LOW_LIGHT] RP -> RGB
```

---

## 6. 파일별 수정 방향 요약

| File | Direction |
|---|---|
| `README.md` | v2 아키텍처(static shell + 전체 ISP pipeline RM)로 재작성 — 완료(2026-07-10) |
| `RESEARCH.md` | 논지: static shell + 전체 ISP pipeline RM — 완료(2026-07-10, §0 reset v2) |
| `SPEC.md` | v1 구현 기술 유지 + v2 마이그레이션 note 추가 — 완료(2026-07-10) |
| `ROADMAP.md` | v2 reset을 우선순위/다음 task에 반영 |
| `isppipeline/hls/README.md` | module map과 Make targets 갱신 |
| `isppipeline/hls/include/dfxisp_accel.hpp` | C ABI 유지, 내부 type은 `dfxisp_types.hpp`로 이동 |
| `isppipeline/hls/src/dfxisp_accel.cpp` | Shell wrapper로 축소 |
| `isppipeline/hls/src/base_vitis.cpp` | Vitis Vision 구현 — `rm_normal.cpp`의 내부 building block |
| `isppipeline/hls/src/check.cpp` | Check 분리 (static) |
| `isppipeline/hls/src/tone.cpp` | 저조도 전용 tone 처리 — `rm_low_light.cpp`의 내부 building block |
| `isppipeline/hls/src/ctrl.cpp` | DFX Ctrl 분리 (static) |
| `isppipeline/hls/src/rm_normal.cpp` | RM_NORMAL top(RP): base_vitis 호출 |
| `isppipeline/hls/src/rm_low_light.cpp` | RM_LOW_LIGHT top(RP): tone + 저조도 ISP 호출 |
| `isppipeline/hls/src/shell.cpp` | Check+DFX Ctrl+선택된 RM 호출 연결 |
| `isppipeline/hls/src/ref_legacy.cpp` | 기존 자체 구현(v0) 보존 |
| `isppipeline/hls/Makefile` | `base/check/tone/rm_normal/rm_low_light/shell` targets 추가 |
| `isppipeline/hls/scripts/vitis_hls.tcl` | 여러 top 합성 지원 |

---

## 7. 검증 기준

### Minimal local verification

```bash
cd /opt/data/dfxisp_md/isppipeline/hls
make vitis-first-verify
```

Must pass:

```text
Check C-sim PASS
Tone C-sim PASS
Base C-sim PASS
RM_NORMAL C-sim PASS
RM_LOW_LIGHT C-sim PASS
Shell C-sim PASS
```

### Vitis verification

```bash
DFXISP_USE_VITIS_VISION=1 DFXISP_HLS_TOP=base_vitis_top DFXISP_HLS_FLOW=csim make hls
DFXISP_USE_VITIS_VISION=1 DFXISP_HLS_TOP=base_vitis_top DFXISP_HLS_FLOW=csynth make hls
```

Must produce (standalone verification only, not the DFX partition target):

```text
base_vitis_top csim PASS
base_vitis_top csynth report exists
```

### DFX module verification

```bash
DFXISP_HLS_TOP=rm_normal_top DFXISP_HLS_FLOW=csynth make hls
DFXISP_HLS_TOP=rm_low_light_top DFXISP_HLS_FLOW=csynth make hls
```

Must confirm:

```text
same port list
same AXI bundles
same control interface
```

### End-to-end shell verification

```bash
DFXISP_USE_VITIS_VISION=1 DFXISP_HLS_TOP=dfxisp_accel DFXISP_HLS_FLOW=csim make hls
```

Must pass fixtures:

- bright grid -> RM_NORMAL (전체 ISP, Base+Normal Tone 통합)
- dark visible grid -> RM_LOW_LIGHT (전체 ISP, Base+Dark Tone 통합)
- forced Normal
- forced Dark
- Auto boundary

---

## 8. Risks

### Risk 1: Vitis Vision function signatures differ

Do not guess signatures. Implementation must inspect installed Vitis Vision 2024.1 headers first.

### Risk 2: RM_LOW_LIGHT output shape/format (구 "Tone output may not be Base-compatible")

`RM_LOW_LIGHT`는 더 이상 Base로 output을 넘기지 않으므로(자신이 곧 완결된 ISP), 이 리스크는
"두 RM(`RM_NORMAL`/`RM_LOW_LIGHT`)이 같은 downstream(RGB32 + metadata) 계약을 지키는가"로
좁혀진다. `RM_LOW_LIGHT`의 binning-demosaic이 shape을 바꾸면(H/2×W/2, Policy A) `out_width/
out_height` 메타데이터로 명시해야 한다(RESEARCH.md §4.3).

### Risk 3: (v1에서 폐기) Static Base + RP Tone may reduce visual flexibility

이 리스크는 v1 결정(Base=static)에서만 유효했다. v2(Base가 RM 안에 있음)에서는 오히려
반대 방향의 트레이드오프가 생긴다 — **RM_NORMAL과 RM_LOW_LIGHT가 각자 자체 Base 구현을
가지면 두 파이프라인 사이의 코드 중복이 늘어난다.** 이건 목표한 결과다(§0 개정 노트):
코드 공유보다 저조도 전용 파라미터/알고리즘 자유도(BLC/AWB를 저조도에 맞게 독립적으로
튜닝하는 능력)를 우선한 트레이드오프.

### Risk 4: Existing results become legacy

Past mAP/resource results based on in-house Base(v0) 또는 v1(Base static + Tone RP)
become `Ref`/ablation 결과. `RM_NORMAL`/`RM_LOW_LIGHT`(v2, 전체 ISP pipeline RP) 기준
결과는 재생성해야 한다.

### Risk 5 (신규): RM_NORMAL과 RM_LOW_LIGHT의 코드 중복

두 RM이 각자 BLC/AWB/CCM을 구현하면 (v1 대비) 코드량이 늘어난다. 완화책: 공통으로 재사용
가능한 산술(예: gamma LUT 생성기, CCM 곱셈 루틴)은 헤더 단위 유틸리티로 공유하되, **RP
경계 안쪽의 구현 디테일**로만 두고 static shell로 끌어올리지 않는다 — 공유하는 건 코드이지
합성 스테이지가 아니다.

---

## 9. Open design questions

1. `RM_LOW_LIGHT`의 binning-demosaic 출력을 그대로 자체 BLC/AWB/CCM/gain/gamma로 이어갈지,
   아니면 중간에 표준 Bayer-shape로 복원하는 단계를 넣을지?
   - Preferred first: binning 이후 shape 그대로(H/2×W/2) 자체 ISP 계속 진행 — Policy A.

2. **(2026-07-10 결정 변경)** Gamma는 누가 소유하는가?
   - v1 답변("Base가 표준 gamma 소유, Tone은 exposure만")은 폐기됐다.
   - **v2 답변:** `RM_NORMAL`의 gamma와 `RM_LOW_LIGHT`의 gamma는 각 RM 내부에 완전히
     귀속된다 — 서로 다른 파이프라인이므로 "중복 적용" 개념 자체가 없다(RESEARCH.md §3.1).

```text
RM_NORMAL owns its own gamma (Vitis Vision 표준 gamma 또는 그에 준하는 구현).
RM_LOW_LIGHT owns its own (별도) low-light gamma.
공유 gamma 스테이지는 없다.
```

3. Should Normal 쪽에 identity/bypass 옵션을 남길지?
   - **v2 답변(변경):** 아니오. `RM_NORMAL`은 stock Vitis Vision ISP 전체이며 "identity
     bypass"라는 옵션은 없다 — BLC/demosaic/CCM은 생략할 수 없는 필수 연산이기 때문이다
     (v1에서는 tone(gain/gamma)만 다뤄서 identity가 의미 있었지만, v2는 전체 파이프라인이라
     의미가 없어짐).

4. **(2026-07-10 결정 변경, 이 리팩터의 핵심 결정)** Should RP include only Tone or Tone+Base?
   - **v1 답변(폐기):** RP = Tone only. Reason(당시): Base is library baseline and should
     stay stable.
   - **v2 답변(채택):** **RP = Tone + Base 전체(= `RM_NORMAL`/`RM_LOW_LIGHT`).**
     Reason: Tone만 스왑하면 재구성 단위가 너무 작아 register-only(Arm 2)와 DFX(Arm 3)의
     자원/전력 격차가 실질적으로 크지 않다 — DFX를 쓸 이유 자체가 약해진다. Base까지 RP에
     포함해야 Arm 2(두 개 full ISP 상주) vs Arm 3(하나만 상주)의 격차가 방어 가능해진다.
     상세 근거: RESEARCH.md §0.

---

## 10. Recommended execution order

1. Update docs and terms first: `TERMS.md`, `README.md`, `RESEARCH.md`, `SPEC.md`. — **완료(2026-07-10)**
2. Split current(v1) code into modules without changing behavior: Check/Tone/Ctrl/Shell/Ref.
3. Add Base API with host fallback (`base_vitis.cpp`, standalone verification target).
4. Add real Vitis Vision Base behind `DFXISP_USE_VITIS_VISION`.
5. Wire `rm_normal.cpp`(calls base_vitis)와 `rm_low_light.cpp`(calls tone + 저조도 ISP)를
   각각 완결된 top으로 만든다 — **이 단계가 v1과 v2를 가르는 지점**이다.
6. Compare `RM_NORMAL`/`RM_LOW_LIGHT` vs Ref(v0/v1)하고 결과를 재생성한다.
7. Promote Shell(Check+DFX Ctrl+선택된 RM 호출)을 최종 `dfxisp_accel` top으로 승격한다.
8. `rm_normal_top`/`rm_low_light_top`을 RP-compatible top으로 개별 합성한다 (`base_vitis_top`은
   standalone 검증용으로만 유지, DFX partition 아님).
9. Update diagrams and paper wording.

---

## 11. Final target statement

When this refactor is complete, the project should be able to state:

```text
DFXISP keeps only Check and DFX Ctrl static. The proposed contribution is not a small
DFX extension bolted onto a static Vitis Vision baseline, but a full reconfigurable ISP
datapath: RM_NORMAL (Vitis Vision based full ISP pipeline) and RM_LOW_LIGHT (low-light
specialized full ISP pipeline) are swapped in and out as a single Reconfigurable
Partition, so the DFX resource/power benefit over a register-only design is large
enough to be defensible.
```

Korean:

```text
DFXISP는 Check와 DFX Ctrl만 static으로 둔다. 제안점은 static인 Vitis Vision 기준선에
작은 DFX 확장을 붙이는 것이 아니라, ISP 데이터패스 전체를 재구성 가능하게 만드는 것이다 —
RM_NORMAL(Vitis Vision 기준 전체 ISP)과 RM_LOW_LIGHT(저조도 특화 전체 ISP)를 하나의
재구성 영역(RP)으로 통째로 교체해, register-only 설계 대비 DFX의 자원·전력 이득이
충분히 크고 방어 가능하도록 만든다.
```
