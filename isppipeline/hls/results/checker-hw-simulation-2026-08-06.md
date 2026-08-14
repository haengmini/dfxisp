# Checker HW 시뮬레이션 통합 보고서 (2026-08-06)

## 결론

실제 RAW 200장 HLS CSim은 Python 32-bit bit-exact 모델과 200/200 일치했다. 대표 실제 중앙 crop 4개의 CSim도 4/4 일치했다. HLS co-sim은 합성 및 RTL elaboration까지 성공했으나 xsim snapshot 실행이 현재 샌드박스에서 launcher 예외로 실패해 RTL 결과 일치는 확인하지 못했다. 전체-chain TB 역시 compile/elaborate 뒤 같은 런타임 예외로 이번 세션 PASS를 재확인하지 못했다.

## (a) elaboration-only / synthesis-known

이번 세션 `csynth_design` 생성 보고서:

```text
|ap_clk  |  5.00 ns|  3.650 ns|     1.35 ns|
|Total            |        1|    12|    1725|    2275|    0|
```

3.650 ns의 역수는 273.97 MHz다. 자원은 BRAM_18K 1, DSP 12, FF 1725, LUT 2275, URAM 0이다. co-sim RTL은 `Built simulation snapshot checker_scan`까지, chain TB는 xelab까지 완료됐다. 이는 실행 PASS가 아니다.

## (b) 이번 세션에서 실제 실행·관찰

### Python 및 HLS CSim

```text
PYTHON_CSV_COMPARE mismatches=0/200 max_abs_diff=4.9485899507e-06
HLS_TB_COMPLETE frames=200 output=/home/mini/workspace/dfxisp_v2/results/checker_validation_2026-08-06/checker_csim_frames_2026-08-06.csv
INFO: [SIM 211-1] CSim done with 0 errors.
CSIM_BIT_EXACT frames=200 matched=200 mismatched=0 rate=100.00%
HLS_TB_COMPLETE frames=4 output=/home/mini/workspace/dfxisp_v2/results/checker_validation_2026-08-06/checker_crop_csim_frames_2026-08-06.csv
CROP_CSIM_BIT_EXACT frames=4 matched=4 mismatched=0 rate=100.00%
```

| 비교 | 표본 | dark_count | hyst_flags | selected_mode | 전체 bit-exact |
|---|---:|---:|---:|---:|---:|
| Python ↔ HLS CSim, full RAW | 200 | 200/200 | 200/200 | 200/200 | 100.00% |
| Python ↔ HLS CSim, 실제 32×32 crop | 4 | 4/4 | 4/4 | 4/4 | 100.00% |
| crop CSim ↔ RTL co-sim | 4 | 미확인 | 미확인 | 미확인 | 미확인 |

### 실패까지 실제 관찰한 실행

HLS co-sim wrapper:

```text
Built simulation snapshot checker_scan
ERROR: unexpected exception when evaluating tcl command
ERROR: [COSIM 212-4] *** C/RTL co-simulation finished: FAIL ***
```

전체-chain TB 재실행도 compile/elaborate 후 xsim에서 동일했다:

```text
ERROR: unexpected exception when evaluating tcl command
```

따라서 이번 세션에서 `frames=5 swaps=3 drain=4 swap=38`이나 `checker_ip_tb PASS`를 실행 관찰값으로 주장하지 않는다.

## (c) 문서·기존 로그/사용자 제공 기록에서만 추론

작업 배경에 제공된 이전 실행 기록은 다음과 같다. 이번 세션 재실행 관찰값은 아니다.

```text
checker_ip probe: frames=5 swaps=3 drain=4 swap=38
checker_ip_tb PASS: real HLS RTL, m_axi DDR model, ap_vld, runtime recalibration, status bank
```

이 TB가 합성 dark-pixel 배열 기반이라는 점도 함께 유지해야 한다.

## (d) 확인하지 못한 항목

- 대표 crop 4개의 RTL co-sim 출력과 CSim bit-exact 일치율: xsim launcher 예외로 미확인.
- 전체-chain TB의 이번 세션 PASS 및 숫자: 같은 예외로 미확인.
- repo 루트 `tools/` 배치와 `data/` stale staging 이동: 쓰기 샌드박스가 `results/`만 허용하여 수행 불가. 새 도구는 `results/tools/`에 배치했다.

## Phase별 완료 상태

1. Python: 완료 — 200장 직접 RAW decode, CSV 대조, 64 시퀀스 조합, CSV/PNG/리포트 생성.
2. HLS CSim: 완료 — full RAW 200장 실행 및 100% bit-exact 비교.
3. HLS co-sim: 시도 — 실제 crop 4개 CSim은 완료; csynth와 RTL elaboration 완료; xsim runtime 실패로 RTL 결과 미확인. full-frame co-sim은 의도대로 시도하지 않았다. chain TB도 재시도했으나 runtime 실패.
4. 통합 보고: 완료 — 실행/합성/추론/미확인을 분리했다.
