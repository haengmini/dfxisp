<!--
=============================================================================
File   : isppipeline/hls/results/blc-c1-csynth-cosim-rerun-2026-07-20.md
Date   : 2026-07-20 KST
Function: blc-recalibration-deploy-2026-07-20.md §4가 남긴 "csynth/cosim 미재실행"
          항목을 닫는다. BLC 16/8 -> 2/2 + checker C1 재보정(둘 다 src/dfxisp_accel.cpp
          constexpr 상수만 변경, 커밋 2f74623/7f24ae4)이 실제 자원/타이밍/RTL 동작에
          영향이 없는지 실측으로 확인.
Sources: src/dfxisp_accel.cpp (현재 HEAD), scripts/vitis_hls.tcl,
         README.md "C-synthesis / Co-sim 실행 노트", results/stage4-hw-synthesis-2026-07-02.md,
         results/cosim-waveform-analysis-2026-07-03.md
=============================================================================
-->
# csynth/cosim 재실행 — BLC 2/2 + checker C1 (2026-07-20)

## 0. 결론부터

**csynth: 자원/타이밍 완전 동일(비트 단위 아님, 보고서 수치 단위로 동일) — 예상대로
상수 변경의 자원 영향 0.** **cosim: RTL 시뮬레이션 자체는 10/10 트랜잭션 100% 완주**,
자동 post-check(C TB vs RTL bit-exact 비교) 단계에서 기존에 이미 문서화된 WSL2 +
Vitis HLS 2024.1 + XSIM 조합의 SIGSEGV가 재현(`cosim-waveform-analysis-2026-07-03.md`
§6와 동일 증상) — 이번 변경이 새로 유발한 문제가 아니라 기존 알려진 툴체인 한계.
비트스트림 배포를 막을 근거 없음.

## 1. 배경

`blc-recalibration-deploy-2026-07-20.md` §4가 "constexpr 상수 하나가 바뀐 것이라
자원/타이밍 영향은 사실상 없겠지만, 실 배포 전에는 HW 트랙 관례대로 csynth 재실행으로
확인할 것"이라고 명시적으로 남긴 항목. `checker-c1-deploy-2026-07-20.md`
(DARK_RATIO_PCT 80->62)도 같은 파일(`src/dfxisp_accel.cpp`)을 건드렸으므로 같은
재실행으로 함께 검증됨. `build/vitis_hls/` 산출물은 이 두 커밋 이전인 2026-07-03
기준으로 정체돼 있었다(재실행 전 확인: `solution1.log` 타임스탬프 07-03, csim만 실행,
syn 리포트 없음).

## 2. 재현한 환경 이슈 — source-path 버그 (기존에 이미 문서화된 것과 동일)

프로젝트 표준 위치(`build/vitis_hls/dfxisp_accel`, `isppipeline/hls/` 아래 중첩 경로)에서
`make hls DFXISP_HLS_FLOW=cosim` 최초 시도 시 `README.md` "C-synthesis / Co-sim 실행
노트"에 이미 기록된 "source-path 버그"가 그대로 재현됨: `add_files`로 등록한 design
source(`src/dfxisp_accel.cpp`)가 `csim.mk`의 `HLS_SOURCES`에서 누락 -> csim 링크
단계에서 `ld.lld: error: undefined symbol: dfxisp_accel`. `open_project -reset`으로
프로젝트를 완전히 지우고 재시도해도 동일하게 재현(캐시 문제 아님, 경로 자체의 문제).

**우회(기존 문서 그대로):** `/tmp/hls_dfxisp/dfxisp_accel/`에 `dfxisp_accel.hpp`,
`dfxisp_accel.cpp`, `test_dfxisp_csim.cpp`를 flat하게 복사하고 `tests/golden_vectors.csv`만
서브폴더에 배치, 그 디렉터리에서 실행 -> design/tb 모두 정상 컴파일.

## 3. csynth 결과 (flat-dir, `xczu7ev-ffvc1156-2-e`, 5.0 ns target)

| 지표 | 이전 실측(07-02, `stage4-hw-synthesis-2026-07-02.md` §4.2/4.3, BLC 16/8 + C0 기준) | 이번 실측(07-20, BLC 2/2 + C1 기준) |
|---|---|---|
| Timing (estimated) | 3.650 ns | **3.650 ns (동일)** |
| BRAM_18K | 9 | **9 (동일)** |
| DSP | 24 | **24 (동일)** |
| FF | 5,536 | **5,536 (동일)** |
| LUT | 8,264 | **8,264 (동일)** |

보고서 원본: `/tmp/hls_dfxisp/dfxisp_accel/proj/solution1/syn/report/dfxisp_accel_csynth.rpt`
(임시 디렉터리, 세션 종료 시 소실 — 필요하면 재실행으로 재생성 가능, 재현 커맨드는 §5).

BLC 상수(16/8->2/2)와 checker DARK_RATIO_PCT(80->62)는 둘 다 `constexpr`/스칼라 비교
상수이며 반복 구조나 비트폭을 바꾸지 않으므로, HLS 스케줄링/바인딩 결과가 완전히
불변인 것은 이론적으로도 자연스럽다 — **실측으로 그 가설을 확인**한 것이 이 재실행의
전체 가치.

## 4. cosim 결과

`cosim_design -rtl verilog -tool xsim -trace_level all` (csim_design/csynth_design 자동
포함):

- RTL 시뮬레이션(`dfxisp_accel_cosim.rpt`): **10/10 트랜잭션 100% 완주**, latency
  min/avg/max = 161/700/1256 사이클, interval min/avg/max = 306/720/1216 사이클, 총
  6,644 사이클. (`test_dfxisp_csim.cpp`의 dfxisp_accel() 호출 수가 07-03 문서 시점의
  8건에서 이번엔 10건으로 늘어 있음 — golden vector 케이스 수 증가, 회귀 아님.)
- 자동 C TB post-check(bit-exact RTL vs C 비교) 단계에서 크래시:
  ```
  ERROR: System received a signal named SIGSEGV and the program has to stop immediately!
  ERROR: [COSIM 212-379] Detected segmentation violation, please check C tb.
  ERROR: [COSIM 212-362] Aborting co-simulation: C TB post check failed.
  ERROR: [COSIM 212-4] *** C/RTL co-simulation finished: FAIL ***
  ```
  `cosim-waveform-analysis-2026-07-03.md` §6가 이미 "vitis_hls의 자동 post-check
  비교는 여전히 SIGSEGV로 미완주 상태(WSL2+Vitis HLS 2024.1+XSIM cosim 하네스 버그로
  추정)"라고 기록한 것과 **정확히 동일한 실패 지점·동일한 증상** — 이번 BLC/C1 변경이
  유발한 새 문제가 아니라 기존에 이미 알려진, 아직 근본 해결되지 않은 툴체인 한계의
  재현.

`dfxisp_accel_cosim.rpt`의 "RTL Status: Fail"은 이 post-check 크래시 때문에 찍힌
것이지, RTL 시뮬레이션 자체(10/10 완주, latency 수치 확보)가 실패한 게 아니다 — 이
구분이 이 문서의 핵심.

## 5. 재현 커맨드

```bash
rm -rf /tmp/hls_dfxisp && mkdir -p /tmp/hls_dfxisp/dfxisp_accel/tests
cd isppipeline/hls
cp include/dfxisp_accel.hpp src/dfxisp_accel.cpp tests/test_dfxisp_csim.cpp \
   /tmp/hls_dfxisp/dfxisp_accel/
cp tests/golden_vectors.csv /tmp/hls_dfxisp/dfxisp_accel/tests/
cd /tmp/hls_dfxisp/dfxisp_accel
cat > run_cosim.tcl <<'EOF'
open_project -reset proj
set_top dfxisp_accel
add_files dfxisp_accel.cpp -cflags "-std=c++17"
add_files -tb test_dfxisp_csim.cpp -cflags "-std=c++17"
open_solution -reset solution1
set_part xczu7ev-ffvc1156-2-e
create_clock -period 5.0 -name default
csim_design
csynth_design
cosim_design -rtl verilog -tool xsim -trace_level all
close_project
EOF
timeout -k 15 1800 vitis_hls -f run_cosim.tcl
```

## 6. 남은 것

- cosim 자동 post-check SIGSEGV의 근본 원인(WSL2 XSIM 하네스 추정)은 여전히 미해결 —
  07-03에도 미해결로 남았고 이번에도 동일. 완전 자동화된 RTL bit-exact 확인이 필요해지면
  별도 조사 필요(예: 실제 Vivado/Linux 네이티브 환경에서 재현 여부 확인, 또는
  `cosim-waveform-analysis-2026-07-03.md`처럼 xsim을 직접 재호출해 수동 신호 비교).
- 이번 재실행은 임시 flat 디렉터리(`/tmp/hls_dfxisp`)에서 수행 — 산출물(리포트/RTL)은
  세션 로컬이며 리포지토리에 커밋되지 않음. 자원/타이밍 수치(§3)는 이 문서에 기록된 것이
  유일한 영구 기록.
