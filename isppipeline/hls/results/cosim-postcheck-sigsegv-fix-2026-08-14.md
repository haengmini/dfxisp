<!--
=============================================================================
File   : isppipeline/hls/results/cosim-postcheck-sigsegv-fix-2026-08-14.md
Date   : 2026-08-14 KST
Function: dfxisp_accel C/RTL co-sim의 C TB post-check SIGSEGV 원인을 AMD
          UG1399의 인터페이스/TB 계약에 맞춰 재분석하고, 수정 및 실제 PASS를 기록한다.
Sources: src/dfxisp_accel.cpp, tests/test_dfxisp_{csim,cosim}.cpp,
         scripts/vitis_hls{,_wave}.tcl, README.md,
         AMD Vitis HLS UG1399 (Interface, Running C/RTL Co-Simulation,
         Running C Simulation, Basic Pointers), Vitis HLS 2024.1/XSIM 실측 로그
=============================================================================
-->
# C/RTL co-sim post-check SIGSEGV 원인 분석 및 해결 (2026-08-14)

## 0. 결론

기존 실패는 합성 RTL의 기능 오류가 아니라 **Vitis HLS가 생성한 co-sim verification
adapter와 범용 C TB 사이의 계약 불일치**였다. 구체적으로 다음 두 조건이 겹쳐 있었다.

1. `m_axi depth`를 “TB 여러 호출의 누적 주소 범위”로 잘못 해석해 1024/2048/8192/
   1920×1080으로 경험적으로 조정했다.
2. 범용 C-sim TB가 top-level 출력 포인터 `hyst_flags`에 `nullptr`를 전달했다. 순수 C
   실행에서는 DUT 내부 null guard로 안전하지만, co-sim wrapper가 포트 값을 기록하고
   C post-check에서 비교하는 인터페이스로는 안전한 입력 계약이 아니다.

범용 SW 회귀 TB와 wrapper-facing co-sim TB를 분리하고, 전용 TB의 한 트랜잭션 최대
샘플 수 64에 맞춰 `depth=64`로 지정한 결과, 동일한 **WSL2 + Vitis HLS 2024.1 + XSIM**
환경에서 RTL 2/2 트랜잭션과 자동 C post-check가 모두 통과했다.

```text
RTL Simulation : 2 / 2 [100.00%]
INFO: [COSIM 212-316] Starting C post checking ...
DFXISP C/RTL co-simulation checks passed
INFO: [COSIM 212-1000] *** C/RTL co-simulation finished: PASS ***
```

따라서 과거 문서의 “WSL2+Vitis HLS 2024.1+XSIM 환경 특유 하네스 한계”는 이번
재현 범위에서는 기각됐다. 같은 환경에서 정식 인터페이스/TB 계약으로 구성하면
post-check가 정상 종료한다.

## 1. 기존 증상과 잘못된 가설

### 1.1 관찰된 증상

과거 실행은 XSIM RTL 트랜잭션을 모두 완료하고 `$finish`까지 호출한 뒤 다음과 같이
실패했다.

```text
ERROR: System received a signal named SIGSEGV and the program has to stop immediately!
ERROR: [COSIM 212-379] Detected segmentation violation, please check C tb.
ERROR: [COSIM 212-362] Aborting co-simulation: C TB post check failed.
ERROR: [COSIM 212-4] *** C/RTL co-simulation finished: FAIL ***
```

작은 `depth`에서는 `ENTER_WRAPC_PC` post-check, 큰 `depth`에서는 RTL 실행 전
`ENTER_WRAPC`에서 크래시했다. RTL이 모든 트랜잭션을 끝낸 실행도 `RTL Status: Fail`로
표시됐지만, 이는 자동 post-check 프로세스의 비정상 종료가 전체 상태에 전파된 결과였다.

### 1.2 과거 해석의 문제

`depth=1024`에서 post-check가 죽고 `depth=2048`에서 SIGSEGV가 사라진 관찰을 근거로
“여러 DUT 호출의 누적 주소 범위가 약 1800 sample이므로 2048이 필요하다”고 설명했다.
그러나 AMD UG1399의 정의는 다르다. `depth`는 verification adapter가 처리할 **최대
sample 수**를 지정하며, 포인터 인자의 RTL co-sim에 필요하다. 함수 호출 횟수를 곱한
누적 주소 공간이라는 정의는 없다.

관련 AMD 정식 문서:

- [UG1399 — Interface](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Interface)
- [UG1399 — Running C/RTL Co-Simulation](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Running-C/RTL-Co-Simulation)
- [UG1399 — Running C Simulation](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Running-C-Simulation)
- [UG1399 — Basic Pointers](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Basic-Pointers)

AMD가 여러 transaction을 금지하는 것도 아니다. UG1399는 II를 계산하려면 RTL
simulation에 최소 두 transaction이 있어야 한다고 명시한다. 문제는 다중 호출 자체가
아니라 각 transaction의 포인터 저장공간과 adapter depth 계약이었다.

## 2. 원인 분리

### 2.1 `m_axi depth`의 올바른 범위

`depth`는 합성된 AXI master가 보드에서 접근할 수 있는 실제 DDR 크기 제한이 아니다.
co-sim 시 C 배열과 RTL memory model 사이에서 데이터를 전달하는 verification adapter의
크기 힌트다. 그러므로 TB가 8×8 프레임만 사용한다면 입력과 출력 포트 모두 64 sample이면
충분하다.

최신 UG1399에는 `depth=height*width` 형태도 예시로 제시된다. 이를 먼저 적용해 실제
Vitis HLS 2024.1로 합성했으나 다음 경고와 함께 pragma가 무시됐다.

```text
expression is not an integral constant expression
read of non-const variable 'width' is not allowed in a constant expression
MAXI Interface pragma is ignored, because 'depth' is not const integer
```

즉 최신 문서의 동적 표현 지원을 2024.1에 소급 적용할 수 없다. 이 저장소의 고정
툴 버전에서는 전용 TB의 최대 크기를 상수로 선언하는 `depth=64`가 검증된 해법이다.

### 2.2 nullable top-level 출력 포인터 제거

기존 `tests/test_dfxisp_csim.cpp`는 `hyst_flags` 결과가 필요 없는 호출에서 `nullptr`를
전달한다. DUT는 `if (hyst_flags)`로 쓰기를 보호하므로 g++ C-sim에는 문제가 없다.
그러나 HLS top의 포인터 인자는 RTL 포트가 되고, co-sim wrapper는 그 포트의 pre/post
데이터를 관리한다. 따라서 전용 TB는 `out_width`, `out_height`, `selected_mode`,
`selected_rm`, `hyst_flags` 전부에 실제 scalar 저장공간을 제공한다.

이번 수정은 `depth`와 nullable 포인터를 함께 정상화했으므로, 과거 각 SIGSEGV에서 두
조건 중 어느 하나가 단독으로 직접 fault를 일으켰는지는 core dump/backtrace 없이
단정하지 않는다. 다만 정식 계약을 만족한 조합에서 동일 환경의 자동 post-check가 PASS한
것은 확인됐다.

## 3. 수정 내용

| 파일 | 변경 |
|---|---|
| `src/dfxisp_accel.cpp` | unified top의 `raw_bayer`/`rgb_out` co-sim depth를 2048→64로 변경하고 UG1399/2024.1 버전 근거 주석 추가 |
| `tests/test_dfxisp_cosim.cpp` | 8×8 normal/low-light 두 transaction, 유효한 출력 포인터, 명시적 return code를 갖는 전용 self-checking TB 추가 |
| `scripts/vitis_hls.tcl` | `DFXISP_HLS_FLOW=cosim`이고 TB override가 없을 때 전용 TB 자동 선택 |
| `scripts/vitis_hls_wave.tcl` | waveform co-sim에도 같은 전용 TB 선택 규칙 적용 |
| `Makefile` | 전용 TB의 일반 C++ 빌드 규칙 추가 |
| `README.md` | 누적 주소 범위 가설 및 미해결 하네스 버그 설명을 이번 실측 결과로 교정 |

일반 `csim`/`csynth`는 기존의 넓은 `test_dfxisp_csim.cpp` 회귀를 유지한다. `cosim`만
작고 결정적인 wrapper-facing TB를 사용한다. 기능 회귀와 인터페이스 프로토콜 회귀의
목적을 분리한 것이다. `DFXISP_HLS_TB`를 명시하면 사용자가 다른 TB로 override할 수 있다.

## 4. 실측 환경과 결과

### 4.1 환경

| 항목 | 값 |
|---|---|
| OS | Ubuntu 22.04.5 LTS on WSL2 |
| Vitis HLS | 2024.1, SW build 5069499 |
| XSIM | 2024.1, SW build 5076996 |
| FPGA part | `xczu7ev-ffvc1156-2-e` |
| target clock | 5.0 ns |
| RTL | Verilog |
| TB transaction | 2회, 각 8×8=64 input/output capacity |

표준 중첩 프로젝트의 별도 source-path 버그 때문에 기존 README 절차대로 source/header/TB를
flat temporary directory에 배치해 실행했다. 이 문제는 SIGSEGV와 독립적이다.

### 4.2 결과

| 검증 | 결과 |
|---|---|
| 전용 TB 일반 g++ 실행 | PASS |
| Vitis `csim_design` | PASS, 0 errors |
| Vitis `csynth_design` | PASS |
| XSIM RTL transactions | 2/2 완료 |
| Vitis C post-check | PASS |
| 최종 co-sim status | **Verilog Pass** |

co-sim report의 cycle 실측:

| latency min/avg/max | interval min/avg/max | total cycles |
|---:|---:|---:|
| 346 / 753 / 1160 | 1120 / 1120 / 1120 | 1466 |

기존 범용 C 회귀도 다시 실행해 726 pixels golden bit-exact PASS를 확인했다. 즉 TB 분리는
기능 회귀 범위를 줄이지 않는다.

## 5. 재현 절차

현재 Vitis HLS 2024.1에는 저장소 중첩 경로의 design source가 생성 `csim.mk`의
`HLS_SOURCES`에서 누락되는 별도 문제가 있다. README의 flat-dir 우회를 적용한 뒤 다음
순서로 실행한다.

```tcl
open_project -reset proj
set_top dfxisp_accel
add_files dfxisp_accel.cpp -cflags "-std=c++17 -Iinclude"
add_files -tb test_dfxisp_cosim.cpp -cflags "-std=c++17 -Iinclude"
open_solution -reset solution1
set_part xczu7ev-ffvc1156-2-e
create_clock -period 5.0 -name default
csim_design
csynth_design
cosim_design -rtl verilog -tool xsim -trace_level none
close_project
```

`close_project` 뒤 Vitis 프로세스가 prompt에서 종료되지 않는 기존 종료-hang은 여전히
별개로 존재한다. 실행은 `timeout -k 15 900 ...`로 감싸되, 성공 판정은 timeout 종료 코드가
아니라 로그의 `COSIM 212-1000 ... PASS`와 cosim report의 `Verilog Pass`로 한다.

## 6. 운영 규칙

향후 co-sim TB 변경 시 다음을 함께 갱신한다.

1. 모든 synthesized top pointer argument에 유효한 저장공간을 전달한다.
2. `m_axi depth`는 TB의 **단일 transaction 최대 element 수 이상**으로 둔다.
3. 2024.1에서는 `depth`에 runtime top argument 표현식을 사용하지 않는다.
4. TB는 결정적 입력만 사용하고 성공 시 0, 실패 시 non-zero를 반환한다.
5. 기능 전체 회귀는 C-sim TB, RTL 인터페이스 회귀는 작고 결정적인 co-sim TB로 분리한다.
6. TB 크기를 8×8보다 키우면 두 `depth=64` pragma도 동시에 갱신한다.
7. `RTL Simulation N/N`만으로 PASS라 하지 않고 자동 C post-check와 최종 report status까지 확인한다.

## 7. 남은 독립 이슈

- 표준 중첩 project에서 design source가 `HLS_SOURCES`에서 누락되는 source-path 문제.
- `close_project` 뒤 `vitis_hls` 프로세스가 종료되지 않는 prompt hang.
- 이번 2-transaction co-sim은 인터페이스/두 datapath smoke gate다. 726-pixel 전체 기능
  정합성은 C-sim golden 회귀가 담당하며, 더 넓은 RTL vector coverage가 필요하면 nullable
  pointer 없는 별도 co-sim case를 점진적으로 추가해야 한다.

위 세 항목은 해결된 C post-check SIGSEGV와 혼동하지 않는다.
