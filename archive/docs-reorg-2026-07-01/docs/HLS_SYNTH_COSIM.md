# DFXISP HLS Synthesis / RTL Cosimulation Tutorial

이 문서는 **이형민 로컬 PC에서 Vitis HLS로 DFXISP `csynth`와 `cosim`을 실행하는 작업 매뉴얼**입니다.  
Hermes 서버에는 `vitis_hls`가 없으므로 실제 synthesis/cosim 수치는 로컬 Vitis 설치 환경에서만 만들 수 있습니다.

현재 repo 기준에서 실행 가능한 HLS 정본 경로는 다음 하나입니다.

```text
dfxisp/isppipeline/hls/
```

GitHub canonical repository:

```text
https://github.com/haengmini/dfxisp.git
```

---

## 0. 전체 흐름 요약

HLS 작업은 아래 순서로 진행합니다.

```text
GitHub 최신 코드 받기
  → local g++ C-sim 확인
  → Vitis HLS 환경 확인
  → Vitis HLS C-sim 실행
  → C synthesis 실행
  → RTL cosimulation 실행
  → report/log 수집
  → 요약 Markdown 작성
  → GitHub / Drive에 결과 보관
```

명령 기준으로는 다음 순서입니다.

```bash
git clone https://github.com/haengmini/dfxisp.git
cd dfxisp

make -C isppipeline/hls verify
make -C isppipeline/hls report
make -C isppipeline/hls hls-report

# Vitis 환경 source 후
make -C isppipeline/hls DFXISP_HLS_FLOW=csim hls
make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls
make -C isppipeline/hls DFXISP_HLS_FLOW=cosim hls
```

---

## 1. 준비물

### 1.1 필수 프로그램

로컬 PC에 아래가 필요합니다.

| 구분 | 필요 항목 | 확인 명령 |
|---|---|---|
| Git | GitHub repo clone/pull | `git --version` |
| Python | golden vector 생성 | `python3 --version` 또는 `python --version` |
| C++ compiler | local C-sim 빌드 | `g++ --version` |
| Make | Makefile 실행 | `make --version` |
| Vitis HLS | csynth/cosim | `vitis_hls -version` |
| Vivado simulator | RTL cosim backend | Vitis 설치에 포함 |

Linux에서는 보통 `python3`, `g++`, `make`가 바로 동작합니다.  
Windows에서는 아래 중 하나를 권장합니다.

1. **Vitis 설치 경로의 `settings64.bat`를 실행한 Command Prompt / PowerShell 사용**
2. **WSL에서 local C-sim만 먼저 확인 후, Vitis HLS는 Windows native shell에서 실행**
3. **Vitis가 Linux 서버에 있으면 Linux에서 전체 실행**

> 주의: Windows native shell에서는 GNU `make`가 없을 수 있습니다. 이 경우 `vitis_hls -f scripts/vitis_hls.tcl -- -flow csynth`처럼 Tcl을 직접 실행하면 됩니다.

---

## 2. GitHub 최신 코드 받기

새 PC에서 처음 시작한다면:

```bash
git clone https://github.com/haengmini/dfxisp.git
cd dfxisp
```

이미 clone한 폴더가 있다면:

```bash
cd dfxisp
git remote -v
git status --short --branch
git pull --ff-only origin main
```

정상 remote는 다음이어야 합니다.

```text
origin  https://github.com/haengmini/dfxisp.git (fetch)
origin  https://github.com/haengmini/dfxisp.git (push)
```

작업 전 상태가 clean인지 확인합니다.

```bash
git status --short --branch
```

정상 예:

```text
## main...origin/main
```

---

## 3. HLS 작업 폴더 구조 확인

repo root에서 다음을 확인합니다.

```bash
cd dfxisp
ls isppipeline/hls
```

기대 구조:

```text
isppipeline/hls/
  Makefile
  README.md
  include/dfxisp_accel.hpp
  src/dfxisp_accel.cpp
  tests/test_dfxisp_csim.cpp
  tests/golden_vectors.csv
  tools/gen_golden_vectors.py
  tools/gen_verification_report.py
  scripts/vitis_hls.tcl
  reports/latest.md
```

각 파일의 역할:

| 파일 | 역할 |
|---|---|
| `src/dfxisp_accel.cpp` | HLS top 구현 |
| `include/dfxisp_accel.hpp` | HLS top interface/header |
| `tests/test_dfxisp_csim.cpp` | C-sim / HLS testbench |
| `tools/gen_golden_vectors.py` | synthetic grid golden vector 생성 |
| `tests/golden_vectors.csv` | bit-exact 비교용 입력/기대값 |
| `scripts/vitis_hls.tcl` | Vitis HLS project 생성/실행 script |
| `Makefile` | local C-sim 및 Vitis HLS wrapper |
| `reports/latest.md` | local C-sim 검증 요약 |

---

## 4. 현재 시나리오 이해

현재 golden vector 시나리오는 조도 변화 sequence입니다.

```text
NORMAL → NORMAL → NORMAL → LOW_LIGHT → LOW_LIGHT → LOW_LIGHT → NORMAL
```

현재 test-frame case:

```text
seq1_bright_normal_grid_8x8              NORMAL
seq2_bright_normal_grid_8x8              NORMAL
seq3_mixed_normal_grid_16x16             NORMAL
seq4_dark_lowlight_grid_8x8              LOW_LIGHT
seq5_dark_lowlight_grid_8x8              LOW_LIGHT
seq6_mixed_dark_lowlight_grid_16x16      LOW_LIGHT
seq7_threshold_boundary_normal_grid_8x8  AUTO/threshold boundary
```

중요한 용어:

- `8x8`, `16x16`은 **test-frame 해상도**입니다. filter 크기나 binning 크기가 아닙니다.
- 현재 default output shape은 모든 mode에서 `H x W` 유지입니다.
- `2x2 binning` 또는 `H/2 x W/2` 출력은 향후 ablation/RM 후보이며 현재 default ABI가 아닙니다.
- 현재 fixture는 사람이 봐도 밝기 차이가 보이도록 grid-style illumination을 사용합니다. 대부분 검은 이미지가 아닙니다.

---

## 5. 먼저 local g++ C-sim 확인

Vitis를 실행하기 전에, repo 자체가 정상인지 확인합니다.

```bash
cd dfxisp
make -C isppipeline/hls verify
```

성공하면 다음 메시지가 나옵니다.

```text
DFXISP golden vector compare passed (832 pixels)
DFXISP C-sim smoke tests passed
```

이 단계가 실패하면 **Vitis HLS로 넘어가지 말고 먼저 C++/golden mismatch를 해결**해야 합니다.

### 5.1 Markdown report 생성

```bash
make -C isppipeline/hls report
```

생성/갱신 파일:

```text
isppipeline/hls/reports/latest.md
```

현재 기대 내용:

```text
Golden vectors: PASS
C-sim: PASS
832 data rows / 7 cases
```

> 참고: `reports/latest.md`는 실행 시각이 들어가므로 실행할 때마다 timestamp만 바뀔 수 있습니다. Git commit할 때는 의미 있는 변경인지 확인하세요.

---

## 6. Vitis HLS 환경 설정

### 6.1 Linux 환경 예시

Vitis 설치 경로에 맞게 하나를 실행합니다.

```bash
source /tools/Xilinx/Vitis/2023.2/settings64.sh
```

또는:

```bash
source /opt/Xilinx/Vitis/2023.2/settings64.sh
```

설치 버전이 2024.1이면 예:

```bash
source /opt/Xilinx/Vitis/2024.1/settings64.sh
```

확인:

```bash
command -v vitis_hls
vitis_hls -version
```

정상 예:

```text
/tools/Xilinx/Vitis/2023.2/bin/vitis_hls
****** Vitis HLS - High-Level Synthesis ...
```

### 6.2 Windows 환경 예시

Windows에서는 Xilinx/Vitis 설치 폴더에서 `settings64.bat`를 먼저 적용해야 합니다.

Command Prompt 예:

```bat
call C:\Xilinx\Vitis\2023.2\settings64.bat
vitis_hls -version
```

PowerShell 예:

```powershell
cmd /c "call C:\Xilinx\Vitis\2023.2\settings64.bat && vitis_hls -version"
```

PowerShell에서 매번 `cmd /c`가 번거로우면, **Xilinx가 제공하는 Vitis Command Prompt**를 열어 작업하는 편이 쉽습니다.

### 6.3 `vitis_hls`가 안 잡힐 때

오류 예:

```text
ERROR: vitis_hls not found. Install/source Vitis HLS, or set VITIS_HLS=/path/to/vitis_hls.
```

해결:

1. Vitis가 설치되어 있는지 확인
2. `settings64.sh` 또는 `settings64.bat` 실행
3. 그래도 안 되면 직접 경로 지정

Linux 예:

```bash
make -C isppipeline/hls VITIS_HLS=/opt/Xilinx/Vitis/2023.2/bin/vitis_hls DFXISP_HLS_FLOW=csynth hls
```

---

## 7. 현재 HLS 설정 확인

실제 Vitis 실행 전에 dry-run report를 봅니다.

```bash
make -C isppipeline/hls hls-report
```

현재 기대 출력:

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
```

설정 의미:

| 항목 | 현재 값 | 의미 |
|---|---|---|
| top | `dfxisp_accel` | HLS top function |
| part | `xczu7ev-ffvc1156-2-e` | ZCU104의 Zynq UltraScale+ MPSoC part |
| clock | `5.0 ns` | 200 MHz target |
| project | `build/vitis_hls/dfxisp_accel` | Vitis HLS project output path |
| Tcl | `scripts/vitis_hls.tcl` | HLS automation script |

### 7.1 part/clock override

다른 part나 clock을 테스트하려면:

```bash
make -C isppipeline/hls \
  DFXISP_HLS_PART=xczu7ev-ffvc1156-2-e \
  DFXISP_HLS_CLOCK=10.0 \
  DFXISP_HLS_FLOW=csynth \
  hls
```

clock 예:

| Clock period | 주파수 |
|---:|---:|
| `10.0 ns` | 100 MHz |
| `6.667 ns` | 150 MHz |
| `5.0 ns` | 200 MHz |
| `3.333 ns` | 300 MHz |

처음에는 `5.0 ns`가 실패하면 `10.0 ns`로 낮춰서 baseline synthesis를 확보하세요.

---

## 8. Vitis HLS C-sim 실행

local `g++` C-sim과 별개로, Vitis HLS project 안에서 C-sim을 실행합니다.

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=csim hls
```

Tcl 내부 실행:

```tcl
csim_design
```

예상 산출물:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/csim/report/dfxisp_accel_csim.log
```

성공 확인:

```bash
tail -80 isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/csim/report/dfxisp_accel_csim.log
```

찾아야 할 문구:

```text
DFXISP golden vector compare passed
DFXISP C-sim smoke tests passed
```

만약 여기서 실패하면:

1. `tests/golden_vectors.csv`가 최신인지 확인
2. local `make verify`는 통과하는지 확인
3. Vitis HLS가 사용하는 compiler 표준/CFLAGS 차이 확인
4. include path가 맞는지 확인

---

## 9. C synthesis 실행

C-sim이 통과하면 C synthesis를 실행합니다.

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls
```

Tcl 내부 실행:

```tcl
csim_design
csynth_design
```

예상 report:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt
```

확인 명령:

```bash
ls isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/
less isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt
```

### 9.1 csynth report에서 볼 항목

최소한 아래를 기록합니다.

| 항목 | 봐야 하는 이유 |
|---|---|
| Latency min/max | 한 frame/case 처리 cycle 추정 |
| Initiation Interval / II | pipeline throughput 판단 |
| Pipeline status | loop pipelining이 되었는지 확인 |
| BRAM | line buffer / memory pressure 확인 |
| DSP | multiply/gain/gamma 계열 자원 확인 |
| FF/LUT | logic footprint 확인 |
| Clock estimate | target clock 만족 가능성 확인 |
| Interface summary | AXI/port shape가 기대와 맞는지 확인 |
| Warnings | synthesis 결과 신뢰성 판단 |

### 9.2 빠른 report 추출 명령

Linux/macOS/WSL/Git Bash에서:

```bash
RPT=isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt

grep -n "Performance Estimates\|Latency\|Interval\|Utilization Estimates\|BRAM\|DSP\|FF\|LUT\|Timing" "$RPT" | head -80
```

Windows PowerShell에서:

```powershell
$RPT="isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt"
Select-String -Path $RPT -Pattern "Performance Estimates|Latency|Interval|Utilization Estimates|BRAM|DSP|FF|LUT|Timing" | Select-Object -First 80
```

### 9.3 csynth 실패 시 우선순위

실패하면 아래 순서로 봅니다.

1. `dfxisp_accel_csynth.rpt`가 생성됐는지
2. `solution1/syn/report/` 안의 `.log`/`.rpt` 파일
3. Vitis console의 첫 번째 `ERROR:`
4. `unsupported C++` 또는 synthesis 불가 construct 여부
5. loop bound가 compile-time으로 결정되는지
6. array/port 크기가 HLS가 추론 가능한 형태인지
7. resource 폭증으로 synthesis가 멈춘 것인지

실패 로그는 그대로 보존해야 합니다. 실패도 중요한 연구 evidence입니다.

---

## 10. RTL cosimulation 실행

C synthesis가 통과하면 RTL cosimulation을 실행합니다.

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=cosim hls
```

Tcl 내부 실행:

```tcl
csim_design
csynth_design
cosim_design
```

예상 output 위치:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/sim/
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/
```

버전에 따라 cosim report 이름은 다를 수 있으니 아래처럼 찾습니다.

```bash
find isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1 -iname '*cosim*' -o -iname '*sim*report*'
```

PowerShell:

```powershell
Get-ChildItem -Recurse isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1 | Where-Object { $_.Name -match "cosim|sim.*report" }
```

### 10.1 cosim에서 확인할 항목

| 항목 | 의미 |
|---|---|
| PASS/FAIL | RTL과 C model이 일치하는지 |
| transaction latency | RTL cycle 기준 latency |
| mismatch line | bit-exact mismatch 위치 |
| simulator | xsim 등 사용 simulator |
| waveform path | waveform debug 가능 여부 |
| timeout 여부 | testbench/protocol deadlock 가능성 |

### 10.2 cosim 실패 시 해석

cosim 실패는 보통 다음 중 하나입니다.

| 증상 | 가능 원인 |
|---|---|
| C-sim PASS, cosim mismatch | HLS 합성 후 bit width/interface 변화, undefined behavior |
| cosim timeout | handshake/protocol deadlock, loop 종료 조건 문제 |
| compile error | testbench가 RTL cosim에서 지원 안 되는 construct 사용 |
| memory/array issue | HLS memory port 추론 문제 |
| simulator launch fail | Vivado simulator 설치/라이선스/환경 문제 |

처음 실패했을 때 바로 코드를 고치기보다, 반드시 report/log를 먼저 저장하세요.

---

## 11. IP export 실행

Vivado DFX integration으로 넘길 IP가 필요하면 export를 실행합니다.

```bash
make -C isppipeline/hls DFXISP_HLS_FLOW=export hls
```

Tcl 내부 실행:

```tcl
csim_design
csynth_design
export_design -format ip_catalog
```

예상 artifact:

```text
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/impl/export.zip
```

확인:

```bash
ls -lh isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/impl/export.zip
```

이 `export.zip`은 Vivado block design / DFX RM 통합으로 넘기는 HLS IP artifact입니다.

---

## 12. `make` 없이 Tcl 직접 실행하는 방법

Windows에서 `make`가 없거나 Vitis HLS GUI/Tcl shell만 쓰고 싶으면 `isppipeline/hls` 폴더로 이동해서 직접 실행합니다.

```bash
cd dfxisp/isppipeline/hls
vitis_hls -f scripts/vitis_hls.tcl -- -flow csim
vitis_hls -f scripts/vitis_hls.tcl -- -flow csynth
vitis_hls -f scripts/vitis_hls.tcl -- -flow cosim
vitis_hls -f scripts/vitis_hls.tcl -- -flow export
```

part/clock override:

```bash
vitis_hls -f scripts/vitis_hls.tcl -- -part xczu7ev-ffvc1156-2-e -clock 5.0 -flow csynth
```

Windows Command Prompt 예:

```bat
cd dfxisp\isppipeline\hls
vitis_hls -f scripts\vitis_hls.tcl -- -flow csynth
```

---

## 13. Vitis HLS GUI로 여는 방법

CLI 실행 후 GUI에서 report를 보고 싶으면:

```bash
cd dfxisp/isppipeline/hls
vitis_hls build/vitis_hls/dfxisp_accel
```

또는 Vitis HLS GUI에서:

1. Open Project
2. `dfxisp/isppipeline/hls/build/vitis_hls/dfxisp_accel` 선택
3. `solution1` 열기
4. `Synthesis Summary`, `Cosimulation Report` 확인

GUI에서 새로 실행할 때는 다음 설정을 확인합니다.

| 항목 | 값 |
|---|---|
| Top function | `dfxisp_accel` |
| Source | `src/dfxisp_accel.cpp` |
| Testbench | `tests/test_dfxisp_csim.cpp` |
| Include path | `include` |
| Part | `xczu7ev-ffvc1156-2-e` |
| Clock | `5.0 ns` |

---

## 14. 결과 수집 폴더 만들기

실행 후 결과를 따로 모아두면 GitHub/Drive 업로드가 쉽습니다.

repo root에서:

```bash
mkdir -p isppipeline/hls/reports/hls-run-$(date +%Y%m%d-%H%M)
RUN_DIR=$(ls -dt isppipeline/hls/reports/hls-run-* | head -1)
echo "$RUN_DIR"
```

주요 report 복사:

```bash
HLS_PROJ=isppipeline/hls/build/vitis_hls/dfxisp_accel
RUN_DIR=$(ls -dt isppipeline/hls/reports/hls-run-* | head -1)

cp "$HLS_PROJ/solution1/syn/report/dfxisp_accel_csynth.rpt" "$RUN_DIR/" 2>/dev/null || true
cp "$HLS_PROJ/solution1/csim/report/dfxisp_accel_csim.log" "$RUN_DIR/" 2>/dev/null || true
find "$HLS_PROJ/solution1" -iname '*cosim*' -o -iname '*sim*report*' | while read p; do cp "$p" "$RUN_DIR/" 2>/dev/null || true; done
```

Windows PowerShell 예:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$RUN_DIR = "isppipeline/hls/reports/hls-run-$stamp"
New-Item -ItemType Directory -Force $RUN_DIR
$HLS_PROJ = "isppipeline/hls/build/vitis_hls/dfxisp_accel"
Copy-Item "$HLS_PROJ/solution1/syn/report/dfxisp_accel_csynth.rpt" $RUN_DIR -ErrorAction SilentlyContinue
Copy-Item "$HLS_PROJ/solution1/csim/report/dfxisp_accel_csim.log" $RUN_DIR -ErrorAction SilentlyContinue
Get-ChildItem -Recurse "$HLS_PROJ/solution1" | Where-Object { $_.Name -match "cosim|sim.*report" } | Copy-Item -Destination $RUN_DIR -ErrorAction SilentlyContinue
```

---

## 15. 결과 요약 Markdown 작성

아래 파일을 새로 만듭니다.

```text
isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/summary.md
```

템플릿:

```md
# DFXISP HLS Run Summary

## Environment

- Date:
- OS:
- Vitis version:
- Vivado version:
- Part: xczu7ev-ffvc1156-2-e
- Clock target: 5.0 ns
- Git commit:

## Commands

```bash
make -C isppipeline/hls verify
make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls
make -C isppipeline/hls DFXISP_HLS_FLOW=cosim hls
```

## Results

| Step | Status | Evidence |
|---|---|---|
| local g++ C-sim | PASS/FAIL | `reports/latest.md` |
| Vitis HLS C-sim | PASS/FAIL | `dfxisp_accel_csim.log` |
| C synthesis | PASS/FAIL | `dfxisp_accel_csynth.rpt` |
| RTL cosim | PASS/FAIL | cosim report/log |
| IP export | PASS/FAIL/Not run | `export.zip` |

## C synthesis summary

| Metric | Value |
|---|---:|
| Latency min | |
| Latency max | |
| II | |
| LUT | |
| FF | |
| BRAM | |
| DSP | |
| Clock estimate | |

## Cosim summary

- Status:
- Latency:
- Mismatch lines:
- Timeout/deadlock:
- Waveform path:

## Warnings / Errors

```text
paste important warnings/errors here
```

## Interpretation

- What this proves:
- What this does not prove yet:
- Next action:
```

중요: 실제 report에서 읽은 값만 적습니다. 아직 없는 LUT/FF/BRAM/DSP/cosim 수치를 추정해서 쓰지 않습니다.

---

## 16. Git에 넣을 것 / 넣지 말 것

### 16.1 Git에 넣어도 되는 것

작고 의미 있는 evidence만 commit합니다.

```text
isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/summary.md
isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/dfxisp_accel_csynth.rpt
isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/dfxisp_accel_csim.log
isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/<small cosim report/log>
```

소스 수정이 있었다면:

```text
isppipeline/hls/src/dfxisp_accel.cpp
isppipeline/hls/include/dfxisp_accel.hpp
isppipeline/hls/tests/test_dfxisp_csim.cpp
isppipeline/hls/tools/*.py
isppipeline/hls/scripts/vitis_hls.tcl
```

### 16.2 Git에 넣지 말 것

아래는 너무 크거나 재생성 가능한 build artifact입니다.

```text
isppipeline/hls/build/
isppipeline/hls/build/vitis_hls/
*.wdb
*.jou
*.log 대용량 전체 dump
export.zip  # 필요하면 Drive에 보관하고 Git에는 링크/요약만
```

`.gitignore`는 이미 다음을 제외합니다.

```text
.hermes/
build/
isppipeline/hls/build/
__pycache__/
*.py[cod]
```

---

## 17. GitHub에 결과 올리는 절차

실행 결과 요약을 만든 뒤:

```bash
git status --short --branch
git add isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/summary.md
# 필요한 경우 작은 rpt/log만 추가
git add isppipeline/hls/reports/hls-run-YYYYMMDD-HHMM/dfxisp_accel_csynth.rpt

git commit -m "reports: add DFXISP HLS synthesis run summary"
git push origin main
```

push 후 확인:

```bash
git ls-remote https://github.com/haengmini/dfxisp.git refs/heads/main
git log -1 --oneline
```

---

## 18. Drive에 결과 올리는 절차

Drive는 큰 artifact와 사람이 볼 요약을 보관하는 곳입니다.

권장 위치:

```text
DFXISP/docs/HLS_SYNTH_COSIM.md                # 이 매뉴얼
DFXISP/hls-runs/YYYYMMDD-HHMM/summary.md      # 실행 요약
DFXISP/hls-runs/YYYYMMDD-HHMM/csynth.rpt      # synthesis report
DFXISP/hls-runs/YYYYMMDD-HHMM/cosim-report    # cosim report/log
DFXISP/hls-runs/YYYYMMDD-HHMM/export.zip      # 필요 시 IP export
```

Drive에 올릴 때는 최소한 다음을 포함하세요.

1. `summary.md`
2. `dfxisp_accel_csynth.rpt`
3. cosim pass/fail report/log
4. 필요 시 `export.zip`

Slack/Hermes에 결과를 알려줄 때는 Drive link와 Git commit을 같이 남기면 됩니다.

---

## 19. 문제 해결 체크리스트

### 19.1 `make verify` 실패

확인 순서:

```bash
python3 --version
g++ --version
make -C isppipeline/hls clean
make -C isppipeline/hls verify
```

가능 원인:

- Python command가 `python3`가 아니라 `python`인 Windows 환경
- compiler가 C++17을 지원하지 않음
- golden vector가 이전 버전
- source/testbench mismatch

Windows에서 Python 명령만 문제라면:

```bash
make -C isppipeline/hls PYTHON=python verify
```

### 19.2 `vitis_hls not found`

해결:

```bash
source /opt/Xilinx/Vitis/<version>/settings64.sh
command -v vitis_hls
```

Windows:

```bat
call C:\Xilinx\Vitis\<version>\settings64.bat
vitis_hls -version
```

### 19.3 csynth가 오래 걸림

처음에는 정상일 수 있습니다. 다만 너무 오래 걸리면:

- CPU/RAM 사용량 확인
- Vitis console에서 같은 warning/error 반복 여부 확인
- loop bound가 너무 큰지 확인
- clock을 `10.0 ns`로 완화해서 baseline synthesis 확보

```bash
make -C isppipeline/hls DFXISP_HLS_CLOCK=10.0 DFXISP_HLS_FLOW=csynth hls
```

### 19.4 cosim timeout

가능 원인:

- RTL handshake deadlock
- testbench가 RTL cosim에서 종료 조건을 못 만남
- output compare loop와 interface protocol 불일치
- HLS top function interface가 testbench 기대와 다름

해야 할 일:

1. timeout log 저장
2. csynth는 PASS였는지 확인
3. cosim report/log에서 마지막 transaction 확인
4. 필요하면 waveform enable 후 재실행

### 19.5 resource가 너무 큼

csynth report에서 LUT/BRAM/DSP가 과도하면:

- line buffer / array partition 확인
- loop unroll이 과한지 확인
- pipeline pragma가 resource를 폭증시키는지 확인
- 8x8/16x16 synthetic fixture와 실제 frame 설계 scale을 분리해서 해석

현재 synthetic frame은 검증용입니다. 실제 이미지 해상도 resource와 직접 동일시하면 안 됩니다.

---

## 20. 현재 단계에서 말할 수 있는 것 / 없는 것

### 말할 수 있는 것

- local C-sim/golden vector compare는 PASS입니다.
- 현재 HLS top은 `dfxisp_accel`입니다.
- 현재 ZCU104 target part는 `xczu7ev-ffvc1156-2-e`입니다.
- 현재 default DPU-facing output shape은 `H x W` 유지입니다.
- synthesis/cosim 실행 절차와 report 위치가 정리되어 있습니다.

### 아직 말하면 안 되는 것

실제 report가 생성되기 전에는 아래를 주장하지 않습니다.

- LUT/FF/BRAM/DSP 사용량
- latency / II
- Fmax / timing closure
- RTL cosim PASS
- Vivado DFX integration 성공
- partial bitstream 크기
- ZCU104 board에서 reconfiguration latency
- DPU mAP 개선 수치

---

## 21. 빠른 명령 모음

### Linux / WSL / Git Bash

```bash
git clone https://github.com/haengmini/dfxisp.git
cd dfxisp

make -C isppipeline/hls verify
make -C isppipeline/hls report
make -C isppipeline/hls hls-report

source /opt/Xilinx/Vitis/2023.2/settings64.sh
vitis_hls -version

make -C isppipeline/hls DFXISP_HLS_FLOW=csim hls
make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls
make -C isppipeline/hls DFXISP_HLS_FLOW=cosim hls
make -C isppipeline/hls DFXISP_HLS_FLOW=export hls
```

### Windows native without make

```bat
git clone https://github.com/haengmini/dfxisp.git
cd dfxisp\isppipeline\hls

call C:\Xilinx\Vitis\2023.2\settings64.bat
vitis_hls -version

vitis_hls -f scripts\vitis_hls.tcl -- -flow csim
vitis_hls -f scripts\vitis_hls.tcl -- -flow csynth
vitis_hls -f scripts\vitis_hls.tcl -- -flow cosim
vitis_hls -f scripts\vitis_hls.tcl -- -flow export
```

### Report paths

```text
C-sim log:
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/csim/report/dfxisp_accel_csim.log

C synthesis report:
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/syn/report/dfxisp_accel_csynth.rpt

HLS project:
isppipeline/hls/build/vitis_hls/dfxisp_accel/

Exported IP:
isppipeline/hls/build/vitis_hls/dfxisp_accel/solution1/impl/export.zip
```

---

## 22. 로컬 실행 후 Hermes에게 전달하면 좋은 정보

HLS 실행 후 Slack에 아래처럼 보내면, Hermes가 다음 정리를 이어갈 수 있습니다.

```text
DFXISP HLS 실행 완료.
Git commit: <commit SHA>
Vitis version: <version>
Flow: csynth/cosim/export
Result folder: <Drive link or local path>
csynth report: <path/link>
cosim report: <path/link>
핵심 결과:
- csynth: PASS/FAIL
- cosim: PASS/FAIL
- LUT/FF/BRAM/DSP:
- latency/II:
- 주요 warning/error:
```

report 파일을 Drive에 올려주면, Hermes가 다음을 할 수 있습니다.

1. `csynth.rpt`에서 resource/latency 표 추출
2. cosim PASS/FAIL 근거 요약
3. 논문/보고서용 표 생성
4. DFX RM integration 다음 task 작성
5. GitHub evidence commit 정리

---

## 23. 최종 체크리스트

작업 전:

- [ ] GitHub 최신 `main` pull 완료
- [ ] `make -C isppipeline/hls verify` PASS
- [ ] Vitis `settings64` 적용
- [ ] `vitis_hls -version` 확인
- [ ] `make -C isppipeline/hls hls-report`로 part/clock/top 확인

작업 중:

- [ ] Vitis HLS C-sim 실행
- [ ] C synthesis 실행
- [ ] RTL cosim 실행
- [ ] 필요 시 IP export 실행

작업 후:

- [ ] `dfxisp_accel_csynth.rpt` 저장
- [ ] cosim report/log 저장
- [ ] `summary.md` 작성
- [ ] 큰 build directory는 Git commit 제외
- [ ] 작은 요약/report만 GitHub에 commit
- [ ] 큰 artifact/export.zip은 Drive에 업로드
- [ ] Slack/Hermes에 Drive link + Git commit 공유
