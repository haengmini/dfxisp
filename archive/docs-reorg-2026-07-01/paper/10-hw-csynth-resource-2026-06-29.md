# HW 단계 — Vitis HLS C-합성 자원 결과 (2026-06-29)

대상: ZCU104 `xczu7ev-ffvc1156-2-e`, Vitis HLS 2024.1, clock target 5.0 ns (200 MHz).
흐름: top별 `csynth_design`, flat temp-dir 방식(`/tmp/hls/<top>`), `-std=c++17`.
소스: `src/dfxisp_hls_variants.cpp` (합성 가능한 `extern "C"` top 4개, `m_axi`+`s_axilite`).

## variant별 합성 후 추정치 (실측)

| variant  | 역할                         | BRAM_18K | DSP | FF     | LUT    | CP (ns) | Fmax (MHz) |
|----------|------------------------------|---------:|----:|-------:|-------:|--------:|-----------:|
| normal   | static base (demosaic)       |        3 |  14 |  3,537 |  4,654 |   3.650 |     273.97 |
| reg_only | 레지스터 fast-path (gain/γ)  |        3 |  14 |  3,564 |  4,780 |   3.650 |     273.97 |
| dfx_bin  | RM 저조도 (2×2 bin + bilinear) | 4 | 56 | 16,183 | 18,783 |   3.650 |     273.97 |
| dfx_fp   | RM ablation (green-guided B/D)| 4 |  47 | 24,372 | 22,216 |   3.650 |     273.97 |

네 variant 모두 동일한 3.650 ns critical path(273.97 MHz)로 5.0 ns target을 충족한다.
즉 타이밍은 변별점이 아니며, 변별 축은 면적·전력이다(방향 A).
출처: `results/resource_csynth.csv` 및 top별 `*_csynth.rpt`.

## 방향 A 자원 분석

RM 증분 logic (variant − base `normal`):

| RM       | ΔLUT   | ΔFF    | ΔDSP | ΔBRAM |
|----------|-------:|-------:|-----:|------:|
| reg      |    126 |     27 |    0 |     0 |
| bin      | 14,129 | 12,646 |   42 |     1 |
| fp       | 17,562 | 20,835 |   33 |     1 |

**static all-resident**는 모든 variant의 datapath를 동시에 상주시켜야 한다.
**DFX**는 하나의 RM만 단일 Reconfigurable Partition에 시분할 적재하며, RP는 가장 큰
RM 크기로 잡힌다(base 영역은 고정). 출처: `results/resource_dfx_savings.csv`.

| 시나리오 | metric | static-all-resident | DFX (time-mux) | 절감 |
|----------|--------|--------------------:|---------------:|-------:|
| 배치 2-RM (reg+bin)     | LUT | 18,909 | 18,783 |  **0.7 %** (126) |
| 후보 3-RM (reg+bin+fp) | LUT | 36,471 | 22,216 | **39.1 %** (14,255) |
| 후보 3-RM (reg+bin+fp) | DSP |     89 |     47 | **47.2 %** (42) |
| 전력 proxy (주간/normal) | active-LUT | 18,909 | 4,780 | **74.7 %** (binning datapath dark) |

### 정직한 해석
- **최종 배치 2-RM(reg + bin)** 에서는 **정적 면적 절감이 미미하다(0.7 % LUT)** — 하나의
  RM(bin)이 지배하고 reg RM은 거의 0이라, 한쪽이 매우 작은 두 RM을 시분할해도 정적 면적은
  거의 줄지 않는다. 과장 없이 그대로 보고한다.
- DFX 면적 이득은 **RM 라이브러리 규모에 비례한다**: `fp`가 screening으로 탈락하지 않았다면
  3-RM 후보 집합은 static-all-resident 대비 이미 **39 % LUT / 47 % DSP** 절감을 보인다.
  static 비용은 #RM에 ~선형으로 증가하는 반면 DFX는 `base + max(RM)` 에 고정되기 때문이다.
- 현 RM 수에서 지배적 이득은 면적이 아니라 **전력**이다: binning datapath(14,129 LUT,
  42 DSP ≈ fabric의 75 %)는 **저조도에서만** 구성·클럭된다. 주간에는 RP에 reg RM만
  올라가므로(4,780 active LUT) binning logic은 동적 전력을 소비하지 않는다 — 위의
  `*_active_daylight` 행.
- `dfx_fp`는 가장 큰 RM이지만 screening으로 탈락한 **음성 사례**다(저조도 mAP 실패,
  `results/map_exdark.csv` 참조): screening 방법론이 작동함을 입증하는 동시에 3-RM
  scalability 수치의 worked example이다.

## 재현

```bash
source /tools/Xilinx/Vitis_HLS/2024.1/settings64.sh
for top in dfxisp_normal dfxisp_regonly dfxisp_bin_rm dfxisp_fp_rm; do
  W=/tmp/hls/$top; rm -rf "$W"; mkdir -p "$W"
  cp src/dfxisp_hls_variants.cpp "$W/"
  printf 'open_project -reset proj\nset_top %s\nadd_files dfxisp_hls_variants.cpp -cflags "-std=c++17"\nopen_solution -reset sol\nset_part xczu7ev-ffvc1156-2-e\ncreate_clock -period 5.0 -name default\ncsynth_design\n' "$top" > "$W/run.tcl"
  ( cd "$W" && timeout 360 vitis_hls -f run.tcl )
done
# 리포트: /tmp/hls/<top>/proj/sol/syn/report/<top>_csynth.rpt
```

참고: Vitis HLS 2024.1은 `close_project` 이후 프로세스 종료 시 가끔 hang에 걸린다.
위처럼 `close_project`를 생략하거나 잔존 `vitis_hls` PID를 kill하면 된다 — 리포트는
hang 이전에 이미 기록된다.

## 빈 레이아웃 — ZCU104 보드 측정 (채울 항목)

| 측정 항목 | static-all-resident | DFX normal | DFX 저조도 | 단위 | 도구 |
|-----------|---------------------|-----------|------------|------|------|
| full-bitstream LUT/FF/DSP/BRAM (post-route) | — | — | — | count | Vivado impl |
| partial-bitstream 크기 (bin RM)             | n/a | — | — | KB | write_bitstream |
| ICAP/PR 재구성 지연                          | n/a | — | — | ms | board timer |
| 정적 전력 (PL)                               | — | — | — | W | BEAM/INA226 |
| 동적 전력, 주간                              | — | — | — | W | board rail |
| 동적 전력, 저조도                            | — | — | — | W | board rail |
