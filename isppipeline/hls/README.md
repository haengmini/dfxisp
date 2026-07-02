# DFXISP HLS C-sim 스캐폴드

로컬 저장소 경로: `isppipeline/hls/`. 정본 아키텍처 문서: 저장소 루트 `RESEARCH.md`.

## 목표 (reset 2026-07-01)

이 스캐폴드는 **shared baseline ISP core + 상호배타 tone RM slot** 구조의 첫
결정적(deterministic) C-시뮬레이션 대상이다. tone RM slot이 shared baseline core를
**감싸는(wrap)** 형태다:

```text
NORMAL:
  pseudo-RAW Bayer RGGB uint16
    -> checker (mode 결정)
    -> RM_NORMAL_TONE (identity bypass)
    -> baseline ISP core (demosaic + BLC + AWB + CCM, gain/gamma 없음)
    -> packed RGB888 uint32  (H x W)

LOW_LIGHT:
  pseudo-RAW Bayer RGGB uint16
    -> checker (mode 결정)
    -> RM_LOW_LIGHT_TONE.front : 2x2 RAW binning (precision loss 전, RESEARCH §4.2)
    -> baseline ISP core (demosaic + BLC + AWB + CCM, gain/gamma 없음)
    -> RM_LOW_LIGHT_TONE.back  : low-light gain + gamma-4.0 tone
    -> packed RGB888 uint32  (H/2 x W/2, Policy A 형상변경)
```

C-sim이 증명하는 불변식(RESEARCH.md §8.2):

- 프레임마다 **정확히 하나의 tone RM**만 선택(mutually exclusive).
- gain/gamma는 **tone RM에만** 존재하고 baseline core에는 중복되지 않음.
- 출력 메타데이터가 mode·선택 RM·출력 형상을 보고.

의도적으로 Ponytail 스타일이다: 작은 HLS top 하나, stdlib만 쓰는 C-sim, 로컬 smoke
테스트에 Vitis 의존성 없음, Vitis HLS/Vitis flow용 HLS pragma는 보존.

## 파일

- `include/dfxisp_accel.hpp` — HLS top 인터페이스, mode/selected-RM enum, `DfxIspResult` 메타데이터
- `src/dfxisp_accel.cpp` — checker + baseline core(demosaic/BLC/AWB/CCM) + RM_NORMAL_TONE(identity) + RM_LOW_LIGHT_TONE(2x2 bin + gain + gamma-4.0)
- `tests/test_dfxisp_csim.cpp` — C-sim smoke 테스트 + golden CSV bit-compare + 아키텍처 불변식 검사
- `tools/gen_golden_vectors.py` — stdlib-only 결정적 golden 생성기(`src/dfxisp_accel.cpp` bit-exact 미러)
- `tools/gen_verification_report.py` — stdlib-only Markdown 검증/리포트 생성기
- `scripts/vitis_hls.tcl` — `dfxisp_accel`용 Vitis HLS 프로젝트 스캐폴드
- `Makefile` — g++ 로컬 C-sim, golden 생성, verify/report, Vitis HLS dry-run 리포트

> 실험 arm(§7)·ablation(§12 Task 5)은 `src/dfxisp_rm.cpp`·`tools/rm_model.py`
> (static / reg_only / dfx_bin / dfx_fp)에 별도로 있다. 현재 스캐폴드의 과거
> post-RGB8 gain/lift 경로는 그 dfx 변종 세트로 이관되어 ablation으로만 남는다.

## 로컬 C-sim 실행

```bash
cd isppipeline/hls
make csim      # smoke 테스트
make verify    # golden 재생성 + packed RGB888 bit 단위 비교
make report    # reports/latest.md 갱신 (아키텍처 gate 표 포함)
```

`make verify` 예상 출력:

```text
python3 tools/gen_golden_vectors.py --out tests/golden_vectors.csv
wrote tests/golden_vectors.csv (1498 rows including header; 1497 data rows; 9 cases)
./build/dfxisp_csim
DFXISP golden vector compare passed (566 pixels)
DFXISP C-sim smoke tests passed
```

## Golden vector 형식

CSV는 케이스별 메타데이터(mode·threshold·출력 형상·선택 RM)와 입력 RAW 행(`kind=raw`),
기대 출력 행(`kind=rgb`)을 함께 담는다. Policy A(저조도 H/2×W/2)로 인해 입력 픽셀 수와
출력 픽셀 수가 다르므로 두 종류의 행을 분리한다. 커버리지: bright/dark/mixed/
threshold-boundary/bright-recovery/odd-dimension.

## Vitis HLS 스캐폴드 실행

기본값은 ZCU104 파트 `xczu7ev-ffvc1156-2-e`, 5.0 ns 클럭. 설치가 다르면 재정의한다.
`make hls-report`는 `vitis_hls` 설치 없이 top/project/part/clock/소스/예상 출력 경로를 출력한다.

```bash
cd isppipeline/hls
make hls-report                              # dry-run
make hls                                     # 기본 DFXISP_HLS_FLOW=csim
DFXISP_HLS_PART=xczu7ev-ffvc1156-2-e \
DFXISP_HLS_CLOCK=5.0 \
DFXISP_HLS_FLOW=csynth make hls              # C-sim 후 synthesis
```

`vitis_hls`가 `PATH`에 없으면 `make hls`는 안내 메시지와 함께 종료한다.
비표준 경로는 `VITIS_HLS=/path/to/vitis_hls`로 지정한다.

## HLS top 함수

```cpp
struct DfxIspResult { int out_width, out_height, selected_mode, selected_rm; };

extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,             // capacity >= width*height
    int width,
    int height,
    int mode,                      // NORMAL / LOW_LIGHT / AUTO
    uint16_t dark_pixel_threshold, // AUTO: dark 픽셀 비율 > 40% 이면 LOW_LIGHT
    DfxIspResult* result);         // 선택된 mode / RM / 출력 형상
```

## 하드웨어/DFX 구조

`src/dfxisp_accel.cpp`는 로컬 C-sim을 위해 stdlib-only를 유지하면서도 의도한 static/RM
경계를 따라 분할되어 있다:

- `checker_select_mode()` — static-region scene checker. `AUTO`에서 dark-pixel 비율로
  NORMAL/LOW_LIGHT를 결정. 장면 단위 히스테리시스는 시퀀스 스케줄러(RESEARCH §5.2) 담당이며
  단일 프레임 C-sim entry에는 없다.
- `baseline_isp_core_pixel()` — **shared static** baseline core. demosaic(RGGB 3x3) +
  BLC + AWB(Q8 채널 게인) + CCM(identity placeholder). **gain/gamma 없음.**
- `run_normal()` — RM_NORMAL_TONE = identity bypass. baseline core를 full-res로 실행.
- `run_low_light()` — **RM_LOW_LIGHT_TONE**(DFX reconfigurable module 후보). RAW 2x2
  binning(front) → baseline core → low-light gain + gamma-4.0(back). Vivado DFX 구현에서는
  이 tone RM slot을 RM-호환 블록으로 패키징하고, checker·baseline core·controller는 static
  region에 둔다.
- `gamma4()` — γ=4.0을 정수 4제곱근 `floor((255^3·v)^(1/4))`로 정확히 실현(Python `isqrt`와
  bit-exact). HW에서는 256-엔트리 LUT로 대체 가능.

C-sim에는 Vitis 전용 헤더가 필요 없다; HLS pragma만 존재하며 로컬 g++ 빌드에서는 무시된다.

## 다음 하드웨어 단계

1. `run_low_light()`의 정적 scratch binning 버퍼를 진짜 streaming line buffer로 교체.
2. RM_LOW_LIGHT_TONE / RM_NORMAL_TONE을 독립 DFX RM slot 패키징 flow로 승격(§8.3 gate).
3. Policy B(형상보존 upsample/pad)는 DPU가 고정 H×W ABI를 요구할 때만 추가(§4.3).
4. Arm 2(register-only)·Arm 3(DFX) 자원/전력/PR-latency 비교(§7).
