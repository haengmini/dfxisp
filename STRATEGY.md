# Vitis-First DFXISP Refactor Strategy

> **상태(2026-08-04): 제안됐으나 미착수.** 이 문서는 2026-07-03에 작성된
> 계획이다 — `src/`에 `base_vitis.cpp`/`check.cpp`/`tone.cpp`/`ctrl.cpp`/
> `shell.cpp`/`TERMS.md` 등 Task 1~18의 어떤 산출물도 아직 존재하지 않는다.
> 2026-07-04~08-03 사이 실제로 진행된 작업은 이 문서와 무관한 checker/BLC
> real-RAW 재보정 트랙과 WB 분리 검토(`ROADMAP.md` Stage 1·3 후속)였다 — 이
> 문서가 폐기된 것은 아니고, 우선순위상 뒤로 밀렸을 뿐이다. 착수 여부·시점은
> 미결정(`ROADMAP.md` "즉시 다음" §7 참고). 아래 계획 본문은 착수 시
> 그대로 유효하다.
>
> **착수 결정의 실질적 쟁점은 §9 열린 질문 #4다(2026-08-04 추가).** 이 문서가
> 선호하는 **"RP = Tone만"** 과 현재 실제로 구현된 **"RP = 모드별 전체
> 파이프라인"**(`SPEC.md` §7 "RP 경계"·§11.12, `results/design-limitations
> -2026-07-03.md` §4.3)은 **양립 불가**다. Vitis Vision을 고정 Base로 쓰려면
> Base가 static이어야 하는데, 현재 구현은 Base에 해당하는 BLC/WB를 RM마다
> 중복 합성한다. 따라서 이 리팩터의 착수 여부는 곧 **어느 논문 서사를 택할
> 것인가**의 문제다 — (A) "검증된 라이브러리 Base + 작은 DFX 확장"(이 문서),
> (B) "DFX가 모드별 완결 ISP를 통째로 교체"(현재 구현, 자원 절감 논거가 더
> 크지만 partial bitstream·재구성 지연도 큼). 논문 마감(2026-10)을 고려하면
> (B) 유지가 저비용이다 — 이미 합성·`pr_verify`·bitstream까지 끝나 있고,
> 필요한 것은 서술 정정뿐이며 그 정정은 2026-08-04에 완료됐다.

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

> **정본 프레이밍 (2026-07-10):** 연구 목표는 RESEARCH.md §1이 정본이다 —
> 목표 1(저조도 특화 모듈 필요성, 단일 모듈이 각각 자기 조건 데이터셋에서
> 최고 → 전환 필요) + 목표 2(DFX 전환으로 효율·성능, SW→HW 증명). 본
> Vitis-first 재정렬은 이 두 목표를 **HW 구현 측면에서 뒷받침하는 리팩터
> 방향**이며, Base(Vitis)=공유 core, Check=체커, Dark=저조도 모듈, DFX
> Ctrl=전환에 각각 대응한다. arm은 normal/lowlight/adaptive(`none` 제외).

**Goal:** 현재 DFXISP 파일들을 “Vitis Vision Library 기준 baseline + 그 위에 DFXISP 확장 모듈” 구조로 재정렬한다.

**Architecture:** AMD Vitis Vision L1 `xf::cv` ISP stage를 **Base**로 두고, DFXISP 고유 기능은 Base 앞/뒤/주변에 붙는 짧은 모듈로 분리한다. 즉 “자체 ISP를 새로 만든다”가 아니라 “Vitis Base를 고정하고, Check/Dark/DFX Ctrl을 확장한다”가 새 방향이다.

**Tech Stack:** Vitis HLS 2024.1, Vitis Vision L1 `xf::cv`, C++17, ZCU104, AXI4-MM, AXI-Lite, DFX/RP shell, Python verification scripts.

---

## 0. 핵심 방향

기존 방향:

```text
자체 baseline core + 자체 RM + 자체 checker + 자체 controller
```

새 방향:

```text
Vitis Vision Base + DFXISP 확장 모듈
```

새 top-level 개념:

```text
RAW frame
  -> Check        # 장면 판단
  -> DFX Ctrl     # mode/RM 선택
  -> Tone RM      # Normal 또는 Dark 확장 모듈
  -> Vitis Base   # Vitis Vision Library 기준 ISP baseline
  -> RGB frame
```

중요 원칙:

1. **Base는 Vitis Vision 기준.**
2. **DFXISP는 Base를 대체하지 않고 확장.**
3. **짧고 직관적인 용어만 사용.**
4. **기존 자체 구현은 바로 삭제하지 말고 `legacy`/`ref`로 격리.**
5. **논문에서는 “Vitis Base + DFX Extension” 구조로 설명.**

---

## 1. 짧은 용어 표준

앞으로 긴 이름을 줄인다.

| 새 용어 | 의미 | 기존/긴 표현 |
|---|---|---|
| **Base** | Vitis Vision 기준 baseline ISP | shared baseline ISP core, baseline_isp_core |
| **Check** | 조도/장면 판단기 | scene checker, checker_select_mode |
| **Tone** | mode별 전처리/톤 보정 RM | mode-specific tone RM |
| **Normal** | 일반 조도 Tone | RM_NORMAL_TONE |
| **Dark** | 저조도 Tone | RM_LOW_LIGHT_TONE |
| **DFX Ctrl** | mode/RM 선택 및 재구성 제어 | DFX controller, PR controller |
| **Shell** | static + RP 연결 top | DFX static shell |
| **RP** | 재구성 영역 | Reconfigurable Partition |
| **Ref** | 비교용/legacy 구현 | old in-house baseline |

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
      base_vitis.hpp                # Vitis Base 선언
      check.hpp                     # Check 선언
      tone.hpp                      # Normal/Dark Tone 선언
      ctrl.hpp                      # DFX Ctrl 선언
      shell.hpp                     # Shell/top 선언
    src/
      dfxisp_accel.cpp              # 최종 top wrapper, shell 호출
      base_vitis.cpp                # Vitis Vision Base 구현
      check.cpp                     # Check 구현
      tone.cpp                      # Normal/Dark Tone 구현
      ctrl.cpp                      # DFX Ctrl 구현
      ref_legacy.cpp                # 기존 자체 baseline/RM 보존
    tests/
      test_base_vitis_csim.cpp
      test_check_csim.cpp
      test_tone_csim.cpp
      test_shell_csim.cpp
    tools/
      gen_base_vectors.py
      compare_base_ref.py
      gen_shell_vectors.py
    reports/
      latest.md
      vitis_first_refactor.md
```

기존 `src/dfxisp_accel.cpp`의 로직은 최종적으로 줄인다.

```cpp
extern "C" void dfxisp_accel(...) {
    shell_run(...);
}
```

---

## 3. 새 아키텍처 정의

### 3.1 Base — Vitis Vision baseline

**역할:** baseline ISP의 기준. AMD Vitis Vision Library로 만든다.

Base pipeline:

```text
RAW Bayer
  -> black level
  -> gain / AWB
  -> demosaic
  -> CCM
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

Base는 DFXISP 논문의 기준선이다.

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

### 3.3 Tone — DFXISP 확장 모듈

**역할:** Base 앞에서 조도별 RAW/tone 처리를 수행한다.

Normal:

```text
RAW -> pass or light gain -> Base
```

Dark:

```text
RAW -> 2x2 bin/gain/gamma or dark-enhance -> Base
```

중요: Tone은 Base를 대체하지 않는다. Tone은 Base 입력을 더 좋게 만드는 확장 모듈이다.

### 3.4 DFX Ctrl — mode/RM 선택

**역할:** Check 결과에 따라 Normal/Dark Tone을 선택한다.

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

Shell은 top-level static wrapper다.

```text
Shell = Check + DFX Ctrl + Tone slot + Base
```

최종 `dfxisp_accel`은 Shell을 호출한다.

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
| Base | Vitis Vision based baseline ISP |
| Check | scene/darkness checker |
| Tone | mode-specific pre-Base enhancement module |
| Normal | normal-light Tone |
| Dark | low-light Tone |
| DFX Ctrl | DFX/RM selection controller |
| Shell | static top wrapper: Check + DFX Ctrl + Tone + Base |
| RP | reconfigurable partition |
| Ref | old or comparison implementation |
```

**Verification:**

```bash
rg -n "shared baseline ISP core|mode-specific tone RM|RM_LOW_LIGHT_TONE|checker_select_mode" README.md RESEARCH.md SPEC.md isppipeline/hls/README.md
```

Expected: old terms may remain in historical sections, but active architecture sections use Base/Check/Tone/Dark/DFX Ctrl/Shell.

---

### Task 2: `README.md`를 Vitis-first 구조로 수정

**Objective:** 첫 화면에서 연구 방향이 바로 보이게 한다.

**Files:**
- Modify: `README.md`

**Replace active architecture block with:**

```text
DFXISP = Vitis Base + DFX Extension

RAW
  -> Check
  -> DFX Ctrl
  -> Tone(Normal/Dark)
  -> Base(Vitis Vision ISP)
  -> RGB
```

**Key wording:**

```markdown
DFXISP는 AMD Vitis Vision Library 기반 Base ISP를 기준선으로 두고,
조도 조건에 따라 Base 앞단의 Tone module을 DFX로 교체하는 구조다.
```

**Avoid:**

```text
자체 baseline core가 기준이다
baseline은 Vitis Vision과 유사하다
```

---

### Task 3: `RESEARCH.md` 핵심 논지를 재작성

**Objective:** 논문 논지를 “Vitis Base를 기준으로 한 DFX 확장”으로 변경한다.

**Files:**
- Modify: `RESEARCH.md`

**New thesis:**

```markdown
Core thesis:
A Vitis Vision based Base ISP can be kept as a stable reference path, while DFXISP adds a small reconfigurable Tone stage and DFX Ctrl around it to improve dark-scene machine-vision robustness without rewriting the whole ISP pipeline.
```

**Korean thesis:**

```markdown
핵심 논지:
Vitis Vision 기반 Base ISP를 고정 기준선으로 유지하고, 조도별 Tone module과 DFX Ctrl만 확장하면 전체 ISP를 새로 만들지 않고도 저조도 머신비전 성능을 개선할 수 있다.
```

---

### Task 4: `SPEC.md`에 module contract 추가

**Objective:** Base/Check/Tone/DFX Ctrl/Shell의 입출력 계약을 고정한다.

**Files:**
- Modify: `SPEC.md`

**Add section:**

```markdown
## Module Contracts

### Base
- Input: RAW Bayer frame or Tone output frame
- Output: RGB888/RGB32 frame
- Implementation target: Vitis Vision L1
- Must not contain DFX policy logic

### Check
- Input: RAW Bayer frame, threshold
- Output: mode
- Must be deterministic and cheap

### Tone
- Input: RAW Bayer frame
- Output: Base-compatible frame
- Variants: Normal, Dark
- DFX candidate: yes

### DFX Ctrl
- Input: mode from Check
- Output: selected Tone, metadata, optional PR control signals
- DFX candidate: static controller

### Shell
- Input: top-level AXI buffers and scalar controls
- Output: RGB buffer and metadata
- Composition: Check + DFX Ctrl + Tone + Base
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

**Objective:** Base/Check/Tone/DFX Ctrl을 하나로 연결한다.

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

**Flow:**

```cpp
Mode m = check_frame(...);
ToneId t = ctrl_select_tone(m);
if (t == ToneId::Dark) tone_dark(...); else tone_normal(...);
base_run(tone_output, rgb_out, out_w, out_h);
ctrl_write_meta(...);
```

**Important:** This requires an intermediate buffer for Tone output in C-sim. For HLS, convert to streaming/line-buffer later after functionally correct.

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

### Task 16: Vitis Base top 합성 target 추가

**Objective:** Base만 따로 HLS 합성할 수 있게 한다.

**Files:**
- Modify: `isppipeline/hls/scripts/vitis_hls.tcl`
- Modify: `isppipeline/hls/Makefile`

**Targets:**

```text
base_vitis_top
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

### Task 17: Tone top들을 RP-compatible하게 맞춤

**Objective:** Normal/Dark가 같은 RP port list를 갖게 한다.

**Files:**
- Modify: `isppipeline/hls/src/tone.cpp`
- Modify: `isppipeline/hls/include/tone.hpp`
- Modify: `isppipeline/hls/scripts/vitis_hls.tcl`

**Required top signatures:**

```cpp
extern "C" void tone_normal_top(
    const uint16_t* raw_in,
    uint16_t* raw_out,
    int width,
    int height,
    int* out_width,
    int* out_height);

extern "C" void tone_dark_top(
    const uint16_t* raw_in,
    uint16_t* raw_out,
    int width,
    int height,
    int* out_width,
    int* out_height);
```

Same ports, same bundles, same control interface.

**Verification:**

```bash
DFXISP_HLS_TOP=tone_normal_top DFXISP_HLS_FLOW=csynth make hls
DFXISP_HLS_TOP=tone_dark_top DFXISP_HLS_FLOW=csynth make hls
```

Expected: both synthesize and expose compatible ports.

---

### Task 18: DFX Ctrl을 Vivado DFX 연결용으로 문서화

**Objective:** C-sim controller와 실제 PR controller의 boundary를 명확히 한다.

**Files:**
- Modify: `isppipeline/hls/results/dfx-vivado-considerations-2026-07-03.md`
- Create: `isppipeline/hls/results/vitis-first-dfx-boundary.md`

**Content:**

```text
Static: Check + DFX Ctrl + Base + AXI shell
RP: Tone(Normal/Dark)
```

Potential alternative:

```text
Static: Check + DFX Ctrl + AXI shell
RP: Tone + Base
```

Recommended initial choice:

```text
Static Base, RP Tone
```

Reason: Base is stable library baseline; DFX benefit is isolated to small mode-specific extension.

---

## 5. 논문/발표 서술 전략

### 짧은 구조 표현

```text
DFXISP = Base + Tone + Check + DFX Ctrl
```

### 한 문장 설명

```text
Base는 Vitis Vision Library 기반 ISP이고, DFXISP는 Base 앞단의 Tone module을 장면에 따라 바꾸는 구조다.
```

### English wording

```text
DFXISP keeps a Vitis Vision based ISP as the Base path and adds a small reconfigurable Tone stage selected by Check and DFX Ctrl.
```

### Korean wording

```text
DFXISP는 Vitis Vision 기반 Base ISP를 그대로 기준선으로 두고, Check와 DFX Ctrl이 조도에 따라 Tone module만 선택·교체하는 구조다.
```

### Figure label

```text
RAW -> Check -> DFX Ctrl -> Tone RP -> Vitis Base -> RGB
```

---

## 6. 파일별 수정 방향 요약

| File | Direction |
|---|---|
| `README.md` | Vitis-first architecture로 재작성 |
| `RESEARCH.md` | 논지: Vitis Base + DFX Extension |
| `SPEC.md` | Base/Check/Tone/DFX Ctrl/Shell contract 추가 |
| `ROADMAP.md` | Stage 0을 “Vitis Base lock”으로 변경 |
| `isppipeline/hls/README.md` | module map과 Make targets 갱신 |
| `isppipeline/hls/include/dfxisp_accel.hpp` | C ABI 유지, 내부 type은 `dfxisp_types.hpp`로 이동 |
| `isppipeline/hls/src/dfxisp_accel.cpp` | Shell wrapper로 축소 |
| `isppipeline/hls/src/base_vitis.cpp` | 새 Vitis Base 구현 |
| `isppipeline/hls/src/check.cpp` | Check 분리 |
| `isppipeline/hls/src/tone.cpp` | Normal/Dark Tone 분리 |
| `isppipeline/hls/src/ctrl.cpp` | DFX Ctrl 분리 |
| `isppipeline/hls/src/shell.cpp` | 전체 연결 |
| `isppipeline/hls/src/ref_legacy.cpp` | 기존 자체 구현 보존 |
| `isppipeline/hls/Makefile` | `base/check/tone/shell` targets 추가 |
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
Shell C-sim PASS
```

### Vitis verification

```bash
DFXISP_USE_VITIS_VISION=1 DFXISP_HLS_TOP=base_vitis_top DFXISP_HLS_FLOW=csim make hls
DFXISP_USE_VITIS_VISION=1 DFXISP_HLS_TOP=base_vitis_top DFXISP_HLS_FLOW=csynth make hls
```

Must produce:

```text
base_vitis_top csim PASS
base_vitis_top csynth report exists
```

### DFX module verification

```bash
DFXISP_HLS_TOP=tone_normal_top DFXISP_HLS_FLOW=csynth make hls
DFXISP_HLS_TOP=tone_dark_top DFXISP_HLS_FLOW=csynth make hls
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

- bright grid -> Normal Tone -> Base
- dark visible grid -> Dark Tone -> Base
- forced Normal
- forced Dark
- Auto boundary

---

## 8. Risks

### Risk 1: Vitis Vision function signatures differ

Do not guess signatures. Implementation must inspect installed Vitis Vision 2024.1 headers first.

### Risk 2: Tone output may not be directly Base-compatible

If Dark Tone changes shape or format, Base contract must support `out_width/out_height`. If Vitis Base assumes Bayer pattern, Dark Tone must output a valid Bayer-like frame or Base must accept RGB/bypass mode. This is a key design decision.

### Risk 3: Static Base + RP Tone may reduce visual flexibility

Keeping Base static is clean for paper and DFX attribution, but some improvements might require changing Base internals. Treat those as later Stage, not first refactor.

### Risk 4: Existing results become legacy

Past mAP/resource results based on in-house Base become `Ref` results. New Vitis Base results must be regenerated before final paper claims.

---

## 9. Open design questions

1. Should Dark Tone output **Bayer-like RAW** into Base, or should Base support **RGB bypass**?
   - Preferred first: Bayer-like RAW if feasible.
   - If binning-demosaic produces RGB, add explicit Base RGB bypass path.

2. Should Base include gamma, or should Tone own gamma?
   - Vitis Vision baseline usually includes gamma.
   - DFXISP Dark enhancement may also need gamma.
   - To avoid double gamma, define:

```text
Base owns standard ISP gamma.
Tone owns only exposure/low-light preconditioning unless explicitly stated.
```

3. Should Normal Tone be identity?
   - Preferred first: identity.
   - This makes Base the clean baseline.

4. Should RP include only Tone or Tone+Base?
   - Preferred first: RP = Tone only.
   - Reason: Base is library baseline and should stay stable.

---

## 10. Recommended execution order

1. Update docs and terms first: `TERMS.md`, `README.md`, `RESEARCH.md`, `SPEC.md`.
2. Split current code into modules without changing behavior: Check/Tone/Ctrl/Shell/Ref.
3. Add Base API with host fallback.
4. Add real Vitis Vision Base behind `DFXISP_USE_VITIS_VISION`.
5. Compare Base vs Ref and regenerate results.
6. Promote Shell to final `dfxisp_accel` top.
7. Synthesize Base and Tone tops separately.
8. Update diagrams and paper wording.

---

## 11. Final target statement

When this refactor is complete, the project should be able to state:

```text
DFXISP uses AMD Vitis Vision as the Base ISP. The proposed contribution is not a replacement ISP, but a DFX extension composed of Check, DFX Ctrl, and a reconfigurable Tone module for dark scenes.
```

Korean:

```text
DFXISP는 AMD Vitis Vision을 Base ISP로 사용한다. 제안점은 ISP 전체를 새로 만드는 것이 아니라, Check·DFX Ctrl·Tone RP를 추가해 저조도 장면에서 Base 앞단을 동적으로 확장하는 것이다.
```
