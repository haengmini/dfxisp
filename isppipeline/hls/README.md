# DFXISP HLS C-sim 스캐폴드

Drive-우선 정본 위치: Agent OS / 06-production / DFXISP / hls-csim.
로컬 저장소 경로: `isppipeline/hls/`.

## 목표

이 스캐폴드는 DFX AI-ISP 하드웨어 경로의 첫 결정적(deterministic) C-시뮬레이션
대상을 만든다:

```text
pseudo-RAW Bayer GRBG uint16
  -> scene checker
  -> normal pipeline 또는 low-light DFX RM path
  -> packed RGB888 uint32
```

의도적으로 Ponytail 스타일이다: 작은 HLS top 하나, stdlib만 쓰는 C-sim, 로컬 smoke
테스트에 Vitis 의존성 없음, 그리고 Vitis HLS/Vitis flow를 위해 HLS pragma는 보존.

## 파일

- `include/dfxisp_accel.hpp` — HLS top-level 인터페이스와 mode enum
- `src/dfxisp_accel.cpp` — checker + 3x3-window demosaic pipeline + low-light RM 경계
- `tests/test_dfxisp_csim.cpp` — C-sim smoke 테스트 + 선택적 golden CSV RGB bit-compare
- `tools/gen_golden_vectors.py` — stdlib만 쓰는 결정적 Bayer/RGB golden vector 생성기
- `tools/gen_verification_report.py` — stdlib만 쓰는 Markdown 검증/리포트 생성기
- `scripts/vitis_hls.tcl` — `dfxisp_accel`용 Vitis HLS 프로젝트 스캐폴드
- `Makefile` — `g++` 로컬 C-sim 빌드, golden 생성, verify/report 타깃, Vitis HLS dry-run 리포트

## 로컬에서 C-sim 실행

```bash
cd isppipeline/hls
make csim
```

`tests/golden_vectors.csv`가 없을 때 예상 출력:

```text
DFXISP golden vector compare skipped (tests/golden_vectors.csv not found)
DFXISP C-sim smoke tests passed
```

## Golden vector 생성·검증

`make golden`은 문서화된 C++ 알고리즘을 그대로 반영하는 stdlib-only Python 모델로
`tests/golden_vectors.csv`를 만든다: GRBG Bayer 입력, clamped 3x3 demosaic,
RAW12→RGB8 shift, 정수 low-light gain/lift. C2 커버리지는 이제 시나리오 프레임 순서로
정렬된 가시적 grid-style 합성 프레임을 사용한다: NORMAL x3, LOW_LIGHT x3, 그 다음
NORMAL x1. 8x8/16x16 값은 필터나 binning 크기가 아니라 테스트 프레임 해상도다.
`make verify`는 그 CSV를 재생성하고, C-sim을 실행하며, packed `0x00RRGGBB` 출력을
golden 값과 bit 단위로 비교한다.

```bash
cd isppipeline/hls
make verify
```

예상 출력:

```text
python3 tools/gen_golden_vectors.py --out tests/golden_vectors.csv
wrote tests/golden_vectors.csv (833 rows including header; 832 data rows; 7 cases)
./build/dfxisp_csim
DFXISP golden vector compare passed (832 pixels)
DFXISP C-sim smoke tests passed
```

## 간결 검증 리포트 생성

`make report`는 golden vector를 재생성하고, `Makefile` 상태를 점검하고, 로컬 C-sim
바이너리를 실행한 뒤 golden/C-sim 상태를 담은 `reports/latest.md`를 작성한다. 리포트
생성기는 Python 표준 라이브러리만 사용한다.

```bash
cd isppipeline/hls
make report
```

예상 출력:

```text
python3 tools/gen_golden_vectors.py --out tests/golden_vectors.csv
wrote tests/golden_vectors.csv (833 rows including header; 832 data rows; 7 cases)
python3 tools/gen_verification_report.py --out reports/latest.md
wrote /path/to/isppipeline/hls/reports/latest.md (golden=pass, csim=pass)
```

## Vitis HLS 스캐폴드 실행

이 TCL 스크립트는 기본값으로 ZCU104 Zynq UltraScale+ 파트 `xczu7ev-ffvc1156-2-e`와
5.0 ns 클럭을 사용한다. 보드 설치가 다른 speed grade나 타깃을 쓰면 part/clock/flow를
재정의하면 된다:

Vitis 호출 전에 `make hls-report`는 `vitis_hls` 설치 없이도 정확한 top 함수,
프로젝트 디렉터리, 파트, 클럭, source/testbench 파일, 예상 report/export 경로를
출력한다:

```bash
cd isppipeline/hls
make hls-report
```

예상 출력:

```text
DFXISP Vitis HLS dry-run report
  top     : dfxisp_accel
  project : build/vitis_hls/dfxisp_accel
  part    : xczu7ev-ffvc1156-2-e
  clock   : 5.0 ns
  flow    : csim
  tcl     : scripts/vitis_hls.tcl
  sources : src/dfxisp_accel.cpp include/dfxisp_accel.hpp
  testbench: tests/test_dfxisp_csim.cpp tests/golden_vectors.csv
  expected outputs:
    local csim binary : build/dfxisp_csim
    golden vectors    : tests/golden_vectors.csv
    HLS project       : build/vitis_hls/dfxisp_accel
    csim log          : build/vitis_hls/dfxisp_accel/solution1/csim/report/dfxisp_accel_csim.log
    synthesis report  : build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt (for csynth/cosim/export)
    exported IP       : build/vitis_hls/dfxisp_accel/solution1/impl/export.zip (for export)
  note: dry-run only; vitis_hls is not invoked.
```

```bash
cd isppipeline/hls
make hls                                    # 기본: DFXISP_HLS_FLOW=csim
DFXISP_HLS_FLOW=csynth make hls             # C-sim 후 synthesis 실행
DFXISP_HLS_PART=xczu7ev-ffvc1156-2-e \
DFXISP_HLS_CLOCK=5.0 \
DFXISP_HLS_FLOW=csynth make hls
```

Tcl 인자를 직접 넘길 수도 있다:

```bash
vitis_hls -f scripts/vitis_hls.tcl -- -part xczu7ev-ffvc1156-2-e -clock 5.0 -flow csynth
```

`vitis_hls`가 `PATH`에 없으면 `make hls`는 명확한 설치/source 안내 메시지와 함께
종료한다. 비표준 실행 경로를 쓰려면 `VITIS_HLS=/path/to/vitis_hls`를 설정하라.

## HLS top 함수

```cpp
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t low_light_threshold);
```

## 하드웨어/DFX 구조

`src/dfxisp_accel.cpp`는 로컬 C-sim을 위해 stdlib-only를 유지하면서도 의도한 하드웨어
경계를 따라 분할되어 있다:

- `checker_select_low_light()` / `checker_scene_average()`는 static-region scene
  checker 블록이다. `AUTO`에서는 평균 RAW 휘도와 `low_light_threshold`에 따라 프레임을
  normal 경로 또는 low-light 경로로 라우팅한다.
- `load_bayer_window3x3()`는 `demosaic_grbg_window()`가 소비하는 명시적 3x3 Bayer
  이웃을 만든다. 현재는 결정적 C-sim을 위해 clamped 메모리 읽기를 쓴다; 이 경계는
  demosaic 픽셀 연산자를 바꾸지 않고 하드웨어용 streaming line-buffer/window
  producer로 교체하도록 의도되었다.
- `normal_pipeline()`은 baseline static ISP 경로다.
- `low_light_reconfigurable_module()`은 명시적 DFX reconfigurable-module 경계
  후보다. Vivado DFX 구현에서는 이 low-light 단계를 RM-호환 블록으로 합성/패키징하고
  `dfxisp_accel`, checker, normal pipeline은 static region에 둔다. 이 함수는 HLS
  pragma로 `INLINE off` 표시되어 hierarchy가 synthesis에 보이도록 한다.

C-sim에는 Vitis 전용 헤더가 필요 없다; HLS pragma만 존재하며 로컬 `g++` 빌드에서는
무시된다.

## 다음 하드웨어 단계

1. `load_bayer_window3x3()`의 clamped 읽기를 진짜 streaming line buffer로 교체.
2. `low_light_reconfigurable_module()`을 독립 DFX RM 패키징 flow로 승격.
3. 현재 C2의 4x4/8x8/16x16 bright/dark/mixed/threshold-boundary 집합을 넘어 fixture
   필요가 늘어나면 Python golden vector 커버리지를 확장.
