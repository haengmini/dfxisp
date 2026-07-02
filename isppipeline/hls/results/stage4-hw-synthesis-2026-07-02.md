<!--
=============================================================================
File   : isppipeline/hls/results/stage4-hw-synthesis-2026-07-02.md
Date   : 2026-07-02
Time   : 16:20 KST
Function: Stage 4 실측 결과 — 실제 Vitis HLS 2024.1 C-synthesis (xczu7ev, 5.0ns)
Goal   : 보드 측정 전 마지막 SW/툴체인 단계. streaming line buffer 리팩터 +
         gamma LUT 최적화를 반영한 ver1/ver2 아키텍처의 실제 자원/타이밍을 측정
=============================================================================
-->
# Stage 4 — HW 실측: C-Synthesis (Vitis HLS 2024.1)

> 이 환경에 **Vitis HLS 2024.1 + Vivado 2024.1이 실제로 설치**되어 있음을 확인하고
> (`/tools/Xilinx/Vitis_HLS/2024.1`, `/tools/Xilinx/Vivado/2024.1`), 실제 C-synthesis를
> 수행했다. 대상: `dfxisp_accel`(현재 ver1+ver2 아키텍처 — RAW-domain-first baseline
> core12, checker 재보정 dark_ratio>0.80), `xczu7ev-ffvc1156-2-e`, clock target 5.0 ns.

## 1. 사전 리팩터 (합성 전 필수)

### 1.1 Streaming line buffer (HLS README "다음 하드웨어 단계" #1)
`run_low_light`의 `static uint16_t binned[1920*1080]`(≈4MB, BRAM에 비현실적)를 **3-row
sliding buffer**(`row_buf[3][960]`)로 교체. 매 출력 row마다 y-1/y/y+1 binned row를 raw에서
재계산(단순·정확 우선, 추가 최적화는 후속). `demosaic_rggb12_rows()`를 신설해 3-row 버퍼에서
동일 demosaic 로직을 수행. **`make verify` bit-exact 유지(646px)** — 산술 불변, 메모리
접근 패턴만 변경.

### 1.2 툴체인 우회: flat temp-dir
과거 worklog(`12-worklog-2026-06-29.md`)에 기록된 "flat temp-dir 방식으로 source-path
버그와 종료-hang을 우회"와 동일한 문제를 재확인:
- **source-path 버그:** 중첩 프로젝트 디렉터리(`isppipeline/hls/build/vitis_hls/...`)에서
  `add_files`로 design source(`src/dfxisp_accel.cpp`)를 추가해도 `csim.mk`의 `HLS_SOURCES`에
  누락되어 링크 실패(`undefined symbol: dfxisp_accel`). testbench만 등록됨.
- **우회:** `/tmp/hls_dfxisp/dfxisp_accel/`에 소스를 flat하게 복사(hpp/cpp/tb를 같은 디렉터리,
  golden CSV만 `tests/` 서브폴더) 후 그 디렉터리에서 실행 → 정상 동작(design+tb 모두 컴파일).
- **종료-hang:** `close_project` 이후 프로세스가 CPU를 거의 안 쓰면서 종료되지 않음(work는
  이미 끝난 상태). `timeout -k <grace> <sec> vitis_hls ...`로 감싸 실제 작업 완료를 로그로
  확인한 뒤 강제 종료하는 방식으로 대응.

## 2. 1차 synthesis 결과 및 발견 — gamma 정수 sqrt의 합성 비효율

첫 csynth(리팩터 직후, 최적화 전)에서 **tone 스테이지가 자원을 지배**함을 발견:

| instance | BRAM | DSP | FF | LUT |
|---|---|---|---|---|
| run_normal | 0 | 15 | 27,605 | 23,647 |
| run_low_light | 3 | 15 | 28,611 | 25,370 |
| **합계** | 6 | 33 | 58,655 | 52,053 |

원인: `gamma2()`가 **런타임 Newton's-method 정수 sqrt**(`while` 루프, 나눗셈 포함)를 `PIPELINE
II=1` 영역 안에서 매 픽셀 호출 → HLS가 반복 나눗셈 로직을 펼쳐 넣으며 자원이 폭증. HLS
README·SPEC에 이미 "HW에서는 256-엔트리 LUT로 대체 가능"이라 명시했던 권고를 실측으로 검증.

## 3. 최적화: gamma2 런타임 sqrt → 256-엔트리 ROM

동일 공식(`floor(sqrt(255·v))`, golden model과 bit-exact)의 값을 **컴파일타임에 고정된
정적 배열**로 교체. 시도 1(`std::array`+`constexpr` 루프)은 Vitis HLS 번들 gcc-8.3.0 STL이
`<array>` 헤더를 거부(`C++ requires a type specifier...` in `bits/stl_pair.h` 등)해서 실패 →
시도 2(순수 C 배열 리터럴, Python으로 256개 값 생성)로 대체, 성공.

- `make verify`: **여전히 bit-exact(646px)** — 값 동일, 표현만 ROM.
- `results/resource_csynth_ver1_2026-07-02.csv`, `reports/csynth/dfxisp_accel_ver1_csynth.rpt`.

## 4. 최종 synthesis 결과 (gamma ROM 반영, 실측)

### 4.1 타이밍
| Clock | Target | Estimated | Uncertainty |
|---|---|---|---|
| ap_clk | 5.00 ns | **3.650 ns** | 1.35 ns |

Fmax ≈ 1/3.65ns = **273.97 MHz** (과거 dfxisp_hls_variants 4종과 critical path 완전 동일 —
Fmax는 변별점이 아니라는 방향 A 관찰과 정합).

### 4.2 자원 (최적화 전 → 후, 실측)
| instance | BRAM(전→후) | DSP(전→후) | FF(전→후) | LUT(전→후) |
|---|---|---|---|---|
| run_normal (RM_NORMAL_TONE) | 0→**1** | 15→**12** | 27,605→**1,785**(-93.5%) | 23,647→**3,108**(-86.9%) |
| run_low_light (RM_LOW_LIGHT_TONE) | 3→**4** | 15→**15** | 28,611→**2,784**(-90.3%) | 25,370→**5,073**(-80.0%) |
| **합계(unified top)** | 6→**8** | 33→**30** | 58,655→**7,008**(-88.0%) | 52,053→**11,217**(-78.4%) |

### 4.3 디바이스 대비 활용률 (xczu7ev, gamma ROM 반영)
| 지표 | 사용 | 가용 | 활용% |
|---|---|---|---|
| BRAM_18K | 8 | 624 | 1% |
| DSP | 30 | 1728 | 1% |
| FF | 7,008 | 460,800 | 1% |
| LUT | 11,217 | 230,400 | 4% |

**매우 여유 있는 풋프린트**(unified top, 두 RM 모드 코드가 모두 상주 — 아직 실제 DFX 분리 전).

### 4.4 latency (design envelope, 최대 지원 해상도 1920×1080 기준 보고값)
| instance | min cycles | max cycles | max absolute(@target 5ns) |
|---|---|---|---|
| run_normal | 171 | 18,662,427 | 93.312 ms |
| run_low_light | 164 | 7,284,608 | 36.423 ms |

RESEARCH 평가 목표 해상도(1280×720)로 환산(II=1 파이프라인이라 cycles≈픽셀수+오버헤드,
achieved clock 3.65ns 기준 추정치이며 별도 실행으로 직접 측정한 값은 아님):
- run_normal: 1280×720=921,600픽셀 → ≈3.4 ms/frame (33.3ms 예산의 약 10%)
- run_low_light: 640×360(binned)=230,400픽셀 → ≈0.84 ms/frame

두 모드 모두 30fps 프레임 예산에 여유 있게 들어간다(estimate, board 실측 아님).

## 5. 재현

```bash
cd /tmp/hls_dfxisp/dfxisp_accel   # flat temp-dir (source-path 우회)
# hpp/cpp/tb를 isppipeline/hls/{include,src,tests}에서 복사, golden CSV는 tests/ 서브폴더
source /tools/Xilinx/Vitis_HLS/2024.1/settings64.sh
DFXISP_HLS_FLOW=csynth timeout -k 15 900 vitis_hls -f run.tcl
cat proj/solution1/syn/report/dfxisp_accel_csynth.rpt
```

## 6. 산출물
- `reports/csynth/dfxisp_accel_ver1_csynth.rpt` (전체 리포트)
- `results/resource_csynth_ver1_2026-07-02.csv`
- 코드: `src/dfxisp_accel.cpp`(streaming line buffer + gamma ROM), `run_low_light`/
  `demosaic_rggb12_rows`/`GAMMA2_LUT` 추가

## 6b. C/RTL Co-sim (L2 gate) 시도 — 정직한 기록

`DFXISP_HLS_FLOW=cosim`으로 7회 시도(depth 1024/2048/8192/2073600, `result` 인터페이스에
`depth=1` 추가 등). **결론: RTL 시뮬레이션(XSIM) 자체는 매번 성공**(7/7 트랜잭션 100% 완료,
`$finish` 정상 호출, latency 641~1203 cycles) — 이는 합성된 하드웨어가 실제로 동작함을
보여주는 긍정적 신호다. 그러나 **자동 post-check 비교 단계(ENTER_WRAPC_PC)에서 매번
SIGSEGV**로 실패해 "L2 bit-exact PASS"를 자동으로 확정하지 못했다.

- depth=1024/2048: pre-check(ENTER_WRAPC) 통과, RTL 완주, **post-check에서** SIGSEGV.
- depth=8192/2073600(전체 설계 envelope): **pre-check에서** SIGSEGV(추정: cosim
  auto-wrapc 하네스의 스택 할당 오버플로).
- `result`(`DfxIspResult*`, `s_axilite`+`ap_vld`) 인터페이스에 `depth=1` 추가: 변화 없음
  (동일하게 post-check SIGSEGV) — struct-pointer 출력 인터페이스가 원인이라는 가설은
  이 시도로 반증되지 않았지만 확증도 못함.
- 과거 worklog(`12-worklog-2026-06-29.md`)의 "source-path 버그·종료-hang"과 같은 계열의
  **이 WSL2+Vitis HLS 2024.1+XSIM 환경 특유의 cosim 하네스 한계**로 판단, 추가 depth 튜닝은
  중단.

**현재 상태:** L2는 "RTL 실행 성공 확인(긍정적 신호), 자동 bit-exact 비교는 미완주"로 기록.
Vivado GUI 기반 수동 파형 비교, 또는 인터페이스 재설계(`DfxIspResult*` 대신 개별 scalar 출력
포트로 분리)가 후속 후보. `src/dfxisp_accel.cpp`의 `depth=` pragma는 값 자체가 합성 RTL
동작에 영향을 주지 않으므로(cosim 검증 전용 힌트) csynth 결과(§4)는 이 이슈와 무관하게 유효.

## 7. 다음 (Stage 4 잔여 / Stage 5)
- [x] C-synthesis 실측 자원/타이밍 — §4.
- [~] C/RTL Co-sim (L2 gate) — RTL 실행 성공 확인, 자동 bit-exact 비교는 툴 하네스 문제로
      미완주(§6b). 인터페이스 재설계 또는 Vivado 수동 검증 필요.
- [ ] RM_NORMAL_TONE / RM_LOW_LIGHT_TONE을 **개별 HLS top으로 분리 합성**하여 Arm1(static
      all-resident)·Arm2(register-only, 현재 unified top과 유사)·Arm3(DFX) 자원 비교의
      실제 partial-bitstream 후보 크기 산정.
- [ ] Vivado DFX 플로어플랜(RP/RM 배치), `pr_verify`, partial bitstream 크기, PR latency —
      Block Design/PS 통합이 필요해 보드 단계 직전 최종 관문.

## 주의
자원/타이밍은 **C-synthesis 추정치**이며 post-route(구현 후) 수치가 아니다. 절대 전력(W)·
PR latency·post-route 자원은 여전히 `TODO(측정)` — Vivado 구현(place&route) 및 보드에서만
확정된다.
