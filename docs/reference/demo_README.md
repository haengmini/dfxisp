# ISP Adaptive PR Demo

AMD Vivado **DFX(Dynamic Function eXchange)** 플로우(UG947 참조)를 기반으로,
Vitis HLS 커널 3개를 ZCU104 보드에서 부분 재구성(Partial Reconfiguration)하는
ISP 파이프라인 데모입니다.

밝기 통계에 따라 런타임에 ISP 커널(Binning/Gain)이 자동으로 교체되며,
RTL 기능 시뮬레이션부터 비트스트림 생성까지 Tcl 스크립트로 자동화됩니다.

> **검증 환경:** Vivado 2024.1 / Vitis HLS 2024.1 / xczu7ev-ffvc1156-2-e (ZCU104)

---

## 📁 폴더 구조

```text
demo/
├── checker/                        # HLS 커널 1: 밝기 통계 분석
│   ├── checker.cpp                 #   - 픽셀 이동평균 → NORMAL/LOW_LIGHT 판정
│   ├── checker.hpp
│   └── xf_checker_tb.cpp
│
├── pr_controller/                  # HLS 커널 2: PR 제어 FSM
│   ├── pr_controller.cpp           #   - IDLE→DRAINING→RECONFIGURING→DONE
│   ├── pr_controller.hpp
│   └── pr_controller_tb.cpp
│
├── partial_bitstream_demo/         # HLS 커널 3: 재구성 대상 ISP 커널
│   ├── binning_gain.cpp
│   └── binning_gain.hpp
│
├── checker_prj/solution1/impl/ip/          # Vitis HLS IP Export 결과 (checker)
├── pr_controller_prj/solution1/impl/ip/    # Vitis HLS IP Export 결과 (pr_controller)
├── partial_bitstream_demo_prj/solution1/impl/ip/  # Vitis HLS IP Export 결과 (binning_gain)
│
├── hdl/
│   ├── static/                     # 정적 영역 RTL (합성 + 시뮬레이션 공용)
│   │   ├── top.v                   #   - 최상위 모듈 (mode 포트 없음 — DFX 합성용)
│   │   ├── checker_wrapper.v       #   - 8픽셀 이동평균 밝기 판정
│   │   └── pr_controller_wrapper.v #   - IDLE/DRAIN/RECONFIG/DONE FSM
│   ├── rp/                         # 재구성 파티션 RTL
│   │   ├── rp_wrapper_normal.v     #   - Config 1 전용: 1x1 Binning (mode 포트 없음)
│   │   ├── rp_wrapper_lowlight.v   #   - Config 2 전용: 2x2 Binning + x1.5 Gain
│   │   └── rp_wrapper.v            #   - 통합 behavioral 모델 (전환 시뮬레이션 전용)
│   ├── sim/                        # 시뮬레이션 전용 RTL
│   │   └── top_sim.v               #   - mode → rp_wrapper 연결 (전환 시뮬레이션용)
│   └── tb/                         # 테스트벤치
│       ├── tb_top.v                #   - Config별 단독 검증 (`ifdef CONFIG_NORMAL/LOWLIGHT)
│       └── tb_top_transition.v     #   - NORMAL→LOW_LIGHT 전환 시나리오 검증
│
├── Tcl_HD/
│   ├── design_utils.tcl            # DFX 헬퍼 함수 (lock, pr_verify, bitstream)
│   ├── implement.tcl               # UG947 DFX 전체 구현 플로우
│   ├── run_sim.tcl                 # Config별 단독 RTL 시뮬레이션
│   └── run_sim_transition.tcl      # NORMAL→LOW_LIGHT 전환 시뮬레이션
│
├── xdc/
│   ├── top_zcu104.xdc              # I/O 핀 + 클럭 타이밍 제약 (TIMING-17 해결 포함)
│   └── pblocks_zcu104.xdc          # RP pblock 배치 제약
│
├── Synth/                          # 합성 DCP (implement.tcl 실행 후 생성)
│   ├── top_synth.dcp               #   - Static 합성 (HD.RECONFIGURABLE 설정)
│   ├── rp_normal_synth.dcp         #   - Config 1 RM OOC 합성 결과
│   └── rp_lowlight_synth.dcp       #   - Config 2 RM OOC 합성 결과
├── Impl/
│   ├── config1/                    # Config 1 (NORMAL) opt/place/route/locked DCP
│   └── config2/                    # Config 2 (LOW_LIGHT) opt/place/route DCP
├── Bitstreams/
│   ├── config1_normal_full.bit     # 전체 비트스트림 (보드 초기화용)
│   ├── config1_normal_partial.bit  # Config 1 파셜 비트스트림 (1.4MB)
│   └── config2_low_light_partial.bit  # Config 2 파셜 비트스트림 (1.4MB)
│
├── sim_out/                        # 시뮬레이션 출력
│   ├── xsim_proj/                  #   - Config별 단독 시뮬레이션 프로젝트
│   └── xsim_transition/            #   - 전환 시뮬레이션 프로젝트
├── create_project.tcl              # Vivado 프로젝트 생성 + HLS IP 등록
├── Makefile                        # HLS C-Sim + RTL 합성 + IP Export
└── README.md
```

---

## 🔗 설계 개요

```text
           ┌──────────────────────────── Static Region ──────────────────────────┐
 pixel_in  │  ┌─────────────────┐  mode_changed  ┌──────────────────────────┐   │
 ─────────►│  │ checker_wrapper │ ─────────────► │ pr_controller_wrapper    │   │
 pixel_valid  │ (밝기→모드 판정)  │                │ (IDLE/DRAIN/RECONFIG/DONE)│   │
           │  └────────┬────────┘                └───────────┬──────────────┘   │
           │           │ mode_out (내부)                       │ rp_reset         │
           └───────────────────────────────────────────────────┼──────────────────┘
                                                               │
                       ┌──────────────── RP Region (pblock) ───┼──────────────────┐
                       │                                       │                  │
                       │   rp_reset ──────────────────────► reset_n               │
                       │                                                          │
                       │   Config 1 (rp_wrapper_normal.v)  : 1x1 Binning         │
                       │   Config 2 (rp_wrapper_lowlight.v): 2x2 Bin + x1.5 Gain│
                       │                                       ↓                  │
 pixel_out ◄───────────────────────────────────────────── data_out                │
                       └──────────────────────────────────────────────────────────┘
```

**DFX 핵심 원리**: `mode_out` 신호가 아닌 **파셜 비트스트림 교체**로 RM이 전환됩니다.

- Config 1 → `config1_normal_partial.bit` 로드: `rp_wrapper_normal` (1x1 Binning)
- Config 2 → `config2_low_light_partial.bit` 로드: `rp_wrapper_lowlight` (2x2 Binning + x1.5 Gain)

| 신호             | 방향    | 설명                                                   |
| ---------------- | ------- | ------------------------------------------------------ |
| `pixel_in[7:0]`  | 입력    | 8비트 픽셀 스트림                                      |
| `pixel_valid`    | 입력    | 픽셀 유효 신호                                         |
| `mode_out`       | 내부    | checker 출력 — PR 트리거 판단용 (RP에 직접 연결 안 됨) |
| `mode_changed`   | 내부    | 1클럭 펄스: 모드 전환 감지                             |
| `rp_reset`       | RP 경계 | PR 중 RP 격리 신호                                     |
| `icap_start`     | 관찰    | ICAP 재구성 시작 신호                                  |
| `pixel_out[7:0]` | 출력    | 처리된 픽셀 출력                                       |

---

## ⚙️ 전제 조건

| 도구      | 검증 버전 | 용도                                         |
| --------- | --------- | -------------------------------------------- |
| Vitis HLS | 2024.1    | HLS 커널 C-시뮬레이션 + RTL 합성 + IP Export |
| Vivado    | 2024.1    | RTL 시뮬레이션 + DFX 구현 + 비트스트림 생성  |
| GNU Make  | 3.8+      | HLS 빌드 자동화                              |

> **DFX 라이선스:** Vivado DFX(Partial Reconfiguration) 기능은 별도 라이선스가 필요합니다.
> 시뮬레이션(`run_sim.tcl`, `run_sim_transition.tcl`)은 DFX 라이선스 없이 동작합니다.

---

## 🚀 실행 방법

### Step 1 — HLS 커널 합성 + IP Export (최초 1회)

```bash
cd /home/mini/isp/pr_cnn/project/isppipeline/demo
make all
```

완료 후 각 경로에 `component.xml` 생성 확인:

```text
checker_prj/solution1/impl/ip/component.xml
pr_controller_prj/solution1/impl/ip/component.xml
partial_bitstream_demo_prj/solution1/impl/ip/component.xml
```

> `make all` = `csim_design` + `csynth_design` + `export_design -format ip_catalog`

---

### Step 2 — RTL 기능 시뮬레이션

#### 2-A. Config별 단독 검증

```bash
vivado -mode tcl
```

```tcl
# Config 1 (NORMAL: rp_wrapper_normal.v)
source Tcl_HD/run_sim.tcl -notrace

# Config 2 (LOW_LIGHT: rp_wrapper_lowlight.v)
set RM_CONFIG "lowlight"
source Tcl_HD/run_sim.tcl -notrace
```

| Config    | Phase 1                      | Phase 2        | Phase 3      | 검증 기준               |
| --------- | ---------------------------- | -------------- | ------------ | ----------------------- |
| NORMAL    | pixel_out=100 (pass-through) | FSM rp_reset=1 | pixel_out=40 | `pixel_out == pixel_in` |
| LOW_LIGHT | 4픽셀마다 출력               | FSM rp_reset=1 | pixel_out=60 | `(40×4×3)>>3 = 60`      |

#### 2-B. NORMAL→LOW_LIGHT 전환 시뮬레이션

```tcl
source Tcl_HD/run_sim_transition.tcl -notrace
```

전환 흐름:

```text
[Phase 1] pixel_in=100 × 16클럭  → pixel_out=100, mode_out=0  (NORMAL)
[Phase 2] pixel_in=30  × 8클럭   → 8픽셀 평균 완료: mode_changed 펄스
                                    pr_controller: IDLE→DRAINING→RECONFIGURING→DONE
                                    mode_out: 0→1, rp_reset: 1→0
[Phase 3] pixel_in=40  × 20클럭  → pixel_out=60, mode_out=1   (LOW_LIGHT)
```

**타이밍 다이어그램 확인 (GUI):**

```tcl
# 1. GUI 열기
start_gui

# 2. 파형 파일 열기 (한 줄로 입력)
open_wave_database sim_out/xsim_transition/isp_sim_trans.sim/sim_1/behav/xsim/tb_top_transition_behav.wdb

# 3. 신호 추가
add_wave_group "Pixel 입출력"
add_wave /tb_top_transition/pixel_in
add_wave /tb_top_transition/pixel_valid
add_wave /tb_top_transition/pixel_out
add_wave /tb_top_transition/pixel_out_valid

add_wave_group "Checker"
add_wave /tb_top_transition/u_dut/u_checker/sum
add_wave /tb_top_transition/u_dut/u_checker/cnt
add_wave /tb_top_transition/u_dut/mode_out
add_wave /tb_top_transition/u_dut/mode_changed

add_wave_group "PR Controller FSM"
add_wave /tb_top_transition/u_dut/u_pr_ctrl/state
add_wave /tb_top_transition/u_dut/u_pr_ctrl/reconfig_cnt
add_wave /tb_top_transition/rp_reset_out
add_wave /tb_top_transition/icap_start_out

add_wave_group "RP 내부"
add_wave /tb_top_transition/u_dut/u_rp/bin_cnt
add_wave /tb_top_transition/u_dut/u_rp/bin_sum

# 4. FSM 상태를 이름으로 표시
set_property radix symbolic [get_waves /tb_top_transition/u_dut/u_pr_ctrl/state]
```

**GUI 조작:**

| 동작             | 방법                   |
| ---------------- | ---------------------- |
| 전체 시간 맞추기 | 파형 창 클릭 후 `F` 키 |
| 확대/축소        | `Ctrl + 마우스 휠`     |
| 구간 확대        | 타임라인에서 드래그    |
| 커서 이동        | 파형 클릭              |

---

## 🔍 타이밍 다이어그램 주요 관찰 포인트

### 포인트 1 — Checker 누적 구간 (~165ns ~ 245ns)

`sum`, `cnt`, `mode_out`, `mode_changed` 확인

- `pixel_in=30` 입력 시작 후 `cnt`: 0→1→2→...→7 증가
- `cnt=7` 시점에 `sum` 갱신 완료 (8클럭 이동평균)
- **`sum < 400`(= 50×8) 되는 순간 `mode_out: 0→1`**
- 바로 다음 클럭에 `mode_changed` 1클럭 펄스 발생

### 포인트 2 — PR Controller FSM 전환 (~245ns ~ 430ns)

`state`, `rp_reset_out`, `icap_start_out`, `reconfig_cnt` 확인

```text
mode_changed 펄스 → state: IDLE → DRAINING   (rp_reset=1)
pipeline_empty    → state: DRAINING → RECONFIGURING  (icap_start=1 펄스)
reconfig_cnt=16   → state: RECONFIGURING → DONE → IDLE  (rp_reset=0)
```

#### 상태별 의미 (FSM Encoding)

| 값 (Hex) | 상태명          | 역할                                                                                                        |
| -------- | --------------- | ----------------------------------------------------------------------------------------------------------- |
| 0        | S_IDLE          | 대기 상태. 모드 변경 신호(mode_changed)가 들어기를 기다림.                                                  |
| 1        | S_DRAINING      | 비우기 시작, RP Reset 활성화. RP 영역을 리셋(rp_reset=1)하여 내부 파이프라인에 남아있는 잔여 데이터를 처리. |
| 2        | S_RECONFIGURING | 파티션 재구성 시작. ICAP를 통해 비트스트림을 교체하는 구간                                                  |
| 3        | S_DONE          | 재구성 완료. 교체가 끝나고 새 로직을 활성화할 준비를 마친 단계.                                             |

> **체크:** `rp_reset=1` 구간 동안 `pixel_out_valid=0` 인지 확인 (RP 격리 동작)

### 포인트 3 — 모드 전환 경계 (~430ns)

`mode_out`, `bin_cnt`, `pixel_out`, `pixel_out_valid` 확인

- `rp_reset=0` 직후 `pixel_valid=1` 재개
- `bin_cnt`: 0→1→2→3 반복 시작
- **`bin_cnt=3` 시점에만 `pixel_out_valid=1`, `pixel_out=60` 출력**

### 포인트 4 — 전환 전후 pixel_out 패턴 비교

| 구간               | `pixel_out_valid` | `pixel_out` 패턴 |
| ------------------ | ----------------- | ---------------- |
| NORMAL (0~165ns)   | 매 클럭 HIGH      | 100 flat         |
| PR 중 (245~430ns)  | 계속 LOW          | X (무효)         |
| LOW_LIGHT (430ns~) | 4클럭마다 HIGH    | 60 펄스          |

> **이 패턴 변화(연속→간헐)가 DFX 전환의 핵심 증거입니다.**

---

### Step 3 — Vivado 프로젝트 생성 + HLS IP 등록

```tcl
source create_project.tcl -notrace
```

> `vivado -mode tcl -source create_project.tcl` (shell 명령) 형식이 아닌,
> **Vivado TCL 창 내에서 `source`** 로 실행해야 합니다.

---

### Step 4 — DFX 전체 구현 플로우 (비트스트림 생성)

```tcl
source Tcl_HD/implement.tcl -notrace
```

**내부 실행 순서:**

```text
[STEP 1a] synth_design (top + rp_wrapper_normal) + HD.RECONFIGURABLE
              → Synth/top_synth.dcp
[STEP 1b] synth_design -top rp_wrapper rp_wrapper_normal.v (OOC)
              → Synth/rp_normal_synth.dcp
[STEP 1c] synth_design -top rp_wrapper rp_wrapper_lowlight.v (OOC)
              → Synth/rp_lowlight_synth.dcp
[STEP 2 ] open_checkpoint top_synth.dcp + read_xdc
              → Impl/config1/linked.dcp
[STEP 3 ] opt → place → route (Config 1)
              → Impl/config1/routed.dcp
[STEP 4 ] update_design -cell u_rp -black_box + lock_design -level routing
              → Impl/config1/routed_locked.dcp
[STEP 5 ] open_checkpoint + read_checkpoint -cell u_rp rp_lowlight_synth.dcp
              → Impl/config2/linked.dcp
[STEP 6 ] opt → place → route (Config 2)
              → Impl/config2/routed.dcp
[STEP 7 ] pr_verify
              → Impl/pr_verify_report.rpt
[STEP 8 ] write_bitstream (Full + Partial)
              → Bitstreams/*.bit
```

**출력 비트스트림 (검증 완료):**

```text
Bitstreams/
├── config1_normal_full.bit          19MB  전체 비트스트림 (보드 초기화용)
├── config1_normal_partial.bit       1.4MB Config 1 파셜 (NORMAL RM)
└── config2_low_light_partial.bit    1.4MB Config 2 파셜 (LOW_LIGHT RM, 런타임 교체용)
```

> 파셜 비트스트림(1.4MB)이 전체(19MB)의 약 7% — RP 영역만 교체하므로 재구성 시간 단축

---

## 🛠️ 스크립트 상세

### `Tcl_HD/run_sim.tcl`

| 변수        | 값                | 설명                           |
| ----------- | ----------------- | ------------------------------ |
| `RM_CONFIG` | `"normal"` (기본) | `rp_wrapper_normal.v` 컴파일   |
| `RM_CONFIG` | `"lowlight"`      | `rp_wrapper_lowlight.v` 컴파일 |

`CONFIG_NORMAL` / `CONFIG_LOWLIGHT` define을 XSim에 전달해 `tb_top.v`의 Phase 3 기대값을 분기합니다.

### `Tcl_HD/run_sim_transition.tcl`

`top_sim.v`(mode 포트 연결) + `rp_wrapper.v`(통합 behavioral)를 사용해 단일 시뮬레이션에서 NORMAL→LOW_LIGHT 전환을 검증합니다.

### `Tcl_HD/implement.tcl`

- 실행 시 `close_project`로 non-project 모드 강제 전환
- Config 1: `link_design` 없이 `top_synth.dcp` 직접 사용 (srcset 충돌 방지)
- Config 2: `read_checkpoint -cell u_rp rp_lowlight_synth.dcp` 후 바로 구현

### `Tcl_HD/design_utils.tcl`

| 함수                                   | 설명                                                      |
| -------------------------------------- | --------------------------------------------------------- |
| `lock_static_design`                   | `update_design -black_box` + `lock_design -level routing` |
| `run_pr_verify <dcp1> <dcp2> <dir>`    | `pr_verify -full_check`로 두 Config 정적 영역 일치 검증   |
| `generate_dfx_bitstreams <name> <dir>` | UCIO-1 DRC Warning 처리 후 Full + Partial 비트스트림 생성 |

---

## 📝 RTL 파일 변경 이력

| 파일                                 | 상태     | 주요 변경 내용                                                     |
| ------------------------------------ | -------- | ------------------------------------------------------------------ |
| `hdl/static/top.v`                   | 수정     | mode 포트 제거 (DFX: RM 전환은 비트스트림으로), 내부 연결 완성     |
| `hdl/rp/rp_wrapper_normal.v`         | **신규** | Config 1 전용 RM — mode 포트 없음, 1x1 Binning                     |
| `hdl/rp/rp_wrapper_lowlight.v`       | **신규** | Config 2 전용 RM — mode 포트 없음, 2x2 Binning + x1.5 Gain         |
| `hdl/rp/rp_wrapper.v`                | 유지     | 전환 시뮬레이션 전용 통합 behavioral 모델 (mode 포트 있음)         |
| `hdl/sim/top_sim.v`                  | **신규** | 시뮬레이션 전용 top — mode → rp_wrapper 연결 복원                  |
| `hdl/tb/tb_top.v`                    | 수정     | `` `ifdef CONFIG_NORMAL/LOWLIGHT ``으로 Phase 3 검증 기준 분기     |
| `hdl/tb/tb_top_transition.v`         | **신규** | NORMAL→LOW_LIGHT 전환 시나리오 테스트벤치                          |
| `hdl/static/checker_wrapper.v`       | 신규     | 8픽셀 이동평균, `wire new_mode`로 non-blocking 경쟁 조건 해결      |
| `hdl/static/pr_controller_wrapper.v` | 신규     | IDLE→DRAINING→RECONFIGURING→DONE FSM                               |
| `xdc/top_zcu104.xdc`                 | 수정     | 클럭 핀 H9(GCIO), `create_generated_clock`으로 TIMING-17 해결      |
| `xdc/pblocks_zcu104.xdc`             | 수정     | `create_pblock` 순서 정정, 잘못된 속성 제거                        |
| `Tcl_HD/implement.tcl`               | 수정     | RM 분리 합성 (STEP 1b/1c), Config 2에 `rp_lowlight_synth.dcp` 사용 |
| `Tcl_HD/run_sim.tcl`                 | 수정     | `RM_CONFIG` 변수, Verilog define 전달                              |
| `Tcl_HD/run_sim_transition.tcl`      | **신규** | 전환 시뮬레이션 자동화 스크립트                                    |
| `Tcl_HD/design_utils.tcl`            | 수정     | UCIO-1 DRC Warning 처리, `lock_static_design` 표준화               |
| `create_project.tcl`                 | 수정     | `close_project` + `-force`, HLS IP 3개 경로 등록                   |
| `Makefile`                           | 수정     | `export_design -format ip_catalog` 추가                            |

---

## ⚠️ 알려진 제약 사항

### 1. 클럭 핀 검증 필요 (H9)

현재 `H9`(Bank 65 GCIO)를 ZCU104 SI570 User Clock 핀으로 설정했습니다.
GCIO 전용 클럭 경로를 사용하므로 TIMING-17(Non-clocked sequential cell) 이슈가 해결됩니다.
실제 보드 사용 전 ZCU104 schematic(UG1267)에서 H9 핀 번호를 반드시 확인하세요.

> `create_generated_clock`은 `open_checkpoint` 시점에 핀 경로가 없어 XDC 처리를 중단시키므로 제거했습니다.

### 2. 데이터 포트 핀 미할당 (UCIO-1)

`pixel_in`, `pixel_out` 등 데이터 포트의 PACKAGE_PIN이 미지정 상태입니다.
비트스트림 생성 시 UCIO-1 DRC를 Warning으로 처리하며, 실제 보드 연결 시 핀 할당이 필요합니다.

### 3. HLS IP → Block Design 연동 (TODO)

현재 HLS IP는 IP Catalog에만 등록되어 있습니다.
Zynq MPSoC PS-PL 연동 시 AXI4-Stream으로 연결하는 Block Design 구성이 필요합니다.

---

## 📖 참고 문서

- [UG947 — Vivado DFX Tutorial (UltraScale+ Basic DFX Flow)](https://docs.amd.com/r/en-US/ug947-vivado-partial-reconfiguration-tutorial/UltraScale-and-UltraScale-Basic-DFX-Flow)
- [UG909 — Vivado Dynamic Function eXchange User Guide](https://docs.amd.com/r/en-US/ug909-vivado-partial-reconfiguration)
- [ZCU104 Evaluation Board User Guide (UG1267)](https://docs.amd.com/v/u/en-US/ug1267-zcu104-eval-bd)
