# C-Sim Quickstart

새 컴퓨터에서 `dfxisp.git`를 clone한 뒤 현재 검증 가능한 HLS C-Sim을 실행하는 방법입니다.

## 1. Clone

```bash
git clone https://github.com/haengmini/dfxisp.git
cd dfxisp
```

## 2. 필요한 도구

최소 요구 도구:

```text
python3
g++
make
git
```

Ubuntu 계열 예시:

```bash
sudo apt update
sudo apt install -y build-essential python3 make git
```

> Vitis HLS가 없어도 아래 C-Sim/golden-vector 검증은 실행됩니다. `csynth`, `cosim`, Vivado DFX 통합은 별도 Vitis/Vivado 환경이 필요합니다.

## 3. C-Sim 실행

```bash
cd isppipeline/hls
make verify
```

현재 기대 출력:

```text
python3 tools/gen_golden_vectors.py --out tests/golden_vectors.csv
wrote tests/golden_vectors.csv (833 rows including header; 832 data rows; 7 cases)
./build/dfxisp_csim
DFXISP golden vector compare passed (832 pixels)
DFXISP C-sim smoke tests passed
```

## 4. 검증 리포트 생성

```bash
make report
```

출력 파일:

```text
isppipeline/hls/reports/latest.md
```

현재 기대 요약:

```text
Golden vectors | PASS | tests/golden_vectors.csv; 832 data rows; 7 cases
C-sim          | PASS | build/dfxisp_csim; return code 0
```

## 5. HLS dry-run 정보 확인

Vitis HLS를 실제 실행하지 않고 top, part, clock, 예상 report 경로만 확인합니다.

```bash
make hls-report
```

현재 기대 핵심:

```text
top     : dfxisp_accel
part    : xczu7ev-ffvc1156-2-e
clock   : 5.0 ns
flow    : csim
note: dry-run only; vitis_hls is not invoked.
```

## 6. Vitis HLS가 있는 경우

Vitis HLS 설치/환경 source가 된 머신에서만 실행합니다.

```bash
cd isppipeline/hls
make hls                         # default DFXISP_HLS_FLOW=csim
DFXISP_HLS_FLOW=csynth make hls   # C-Sim 후 synthesis
```

직접 Tcl 실행:

```bash
vitis_hls -f scripts/vitis_hls.tcl -- -part xczu7ev-ffvc1156-2-e -clock 5.0 -flow csynth
```

## 7. 현재 한계

현재 repo에서 즉시 재현 가능한 것은 C-Sim/golden-vector bit-exact 검증입니다.

아래 항목은 Vitis/Vivado 로그가 생성된 뒤에만 수치화합니다.

- LUT / FF / BRAM / DSP
- HLS latency / II
- Fmax / WNS / timing
- cosim 로그
- partial bitstream size
- 실제 reconfiguration latency
- frame drop / throughput / power estimate
