# ISP Pipeline 동적 부분 재구성(DFX) 튜토리얼

## Vivado UG947 기반 — Binning / Gain 런타임 교체 (ZCU104)

> **검증 환경:** Vivado 2024.1 / Vitis HLS 2024.1 / ZCU104 (xczu7ev-ffvc1156-2-e)  
> **참조:** AMD UG947 (UltraScale+ Basic DFX Flow) + AMD UG909 + 현재 프로젝트 `isppipeline/demo/`

---

## 목차

1. [개요 및 설계 목표](#1-개요-및-설계-목표)
2. [동작 원리 — DFX 핵심 개념](#2-동작-원리--dfx-핵심-개념)
3. [프로젝트 전체 구조](#3-프로젝트-전체-구조)
4. [전제 조건 및 라이선스](#4-전제-조건-및-라이선스)
5. [Step 1 — HLS 커널 합성 및 IP Export](#step-1--hls-커널-합성-및-ip-export)
6. [Step 2 — RTL 설계 (정적 영역 + RP 모듈)](#step-2--rtl-설계-정적-영역--rp-모듈)
7. [Step 3 — RTL 기능 시뮬레이션](#step-3--rtl-기능-시뮬레이션)
8. [Step 4 — DFX 구현 플로우 (비트스트림 생성)](#step-4--dfx-구현-플로우-비트스트림-생성)
9. [Step 5 — Vivado 프로젝트 모드 GUI 플로우 (선택)](#step-5--vivado-프로젝트-모드-gui-플로우-선택)
10. [Step 6 — 보드 배포 및 런타임 재구성](#step-6--보드-배포-및-런타임-재구성)
11. [ISPPipeline_accel 커널과 DFX 연동](#isp-pipeline_accel-커널과-dfx-연동)
12. [UG947 DFX 플로우 매핑표](#ug947-dfx-플로우-매핑표)
13. [알려진 문제 및 트러블슈팅](#알려진-문제-및-트러블슈팅)
14. [참고 문서](#참고-문서)

---

## 1. 개요 및 설계 목표

본 튜토리얼은 AMD Vivado의 **DFX(Dynamic Function eXchange)** — 구 Partial Reconfiguration — 기술을 활용해,  
ZCU104 보드에서 ISP 파이프라인의 **Binning 및 Gain 처리 모듈을 런타임에 동적으로 교체**하는 방법을 단계별로 설명합니다.

### 설계 목표

| 항목                 | 내용                                            |
| -------------------- | ----------------------------------------------- |
| 타깃 보드            | ZCU104 (Zynq UltraScale+ xczu7ev-ffvc1156-2-e)  |
| 재구성 트리거        | 프레임 밝기(Brightness) 기반 자동 전환          |
| Config 1 (NORMAL)    | 1×1 Binning — 고조도 씬, 원본 해상도 유지       |
| Config 2 (LOW_LIGHT) | 2×2 Binning + ×1.5 Gain — 저조도 씬, SNR 개선   |
| 재구성 시간          | 파셜 비트스트림 1.4 MB → 전체(19 MB) 대비 약 7% |
| 참조 튜토리얼        | UG947 Lab 4 (DFX RTL Project Flow with Debug)   |

### 핵심 가치

DFX 없이는 두 모드를 동시에 FPGA에 올려야 하므로 LUT/DSP 자원이 2배 필요합니다.  
DFX를 사용하면 **정적 영역(checker + pr_controller + ISP 나머지 스테이지)을 공유**하고,  
Binning/Gain RP(Reconfigurable Partition)만 런타임에 교체합니다.

---

## 2. 동작 원리 — DFX 핵심 개념

```text
           ┌─────────────────────── Static Region (항상 유지) ───────────────────────┐
 pixel_in  │  ┌──────────────────┐  mode_changed  ┌──────────────────────────────┐  │
 ─────────►│  │ checker_wrapper  │ ─────────────► │ pr_controller_wrapper        │  │
           │  │ (밝기 이동평균)    │                │ IDLE→DRAIN→RECONFIG→DONE     │  │
           │  └────────┬─────────┘                └────────────────┬─────────────┘  │
           │           │ mode_out (내부 신호)                       │    rp_reset    │
           └───────────────────────────────────────────────────────┼────────────────┘
                                                                   │
                       ┌────────────── RP Region (pblock 내 교체) ──┼────────────────┐
                       │                                           ↓                │
                       │   Config 1 : rp_wrapper_normal.v    → 1×1 Binning          │
                       │   Config 2 : rp_wrapper_lowlight.v → 2×2 Bin + ×1.5 G      │
                       │                                          ↓                 │
 pixel_out ◄───────────────────────────────────────────── data_out                  │
                       └────────────────────────────────────────────────────────────┘
```

**DFX 핵심 원칙 (UG947 기반):**

- RM(Reconfigurable Module)은 `mode_out` 신호로 전환하지 **않고**, 파셜 비트스트림 교체로 전환합니다.
- 각 Config의 RM RTL 파일은 `mode` 포트 없이 단일 기능만 구현합니다.
- 정적 영역 라우팅은 Config 1에서 확정(lock)된 후, Config 2에서 재사용됩니다.
- `pr_verify`로 두 Config의 정적 영역 라우팅 일치를 검증합니다.

### 신호 테이블

| 신호              | 방향    | 설명                                                   |
| ----------------- | ------- | ------------------------------------------------------ |
| `pixel_in[7:0]`   | 입력    | 8비트 픽셀 스트림                                      |
| `pixel_valid`     | 입력    | 픽셀 유효 신호                                         |
| `mode_out`        | 내부    | checker 출력 — PR 트리거 판단용 (RP에 직접 연결 안 됨) |
| `mode_changed`    | 내부    | 1클럭 펄스: 모드 전환 감지                             |
| `rp_reset`        | RP 경계 | PR 중 RP 격리 신호 (PR 중 pixel_out_valid=0)           |
| `icap_start`      | 관찰    | ICAP 재구성 시작 신호                                  |
| `pixel_out[7:0]`  | 출력    | 처리된 픽셀 출력                                       |
| `pixel_out_valid` | 출력    | 출력 유효 신호 (PR 중 LOW)                             |

---

## 3. 프로젝트 전체 구조

```text
isppipeline/demo/
├── checker/                        # HLS 커널 1: 밝기 통계 분석
│   ├── checker.cpp                 #   8픽셀 이동평균 → NORMAL/LOW_LIGHT 판정
│   ├── checker.hpp
│   └── xf_checker_tb.cpp
│
├── pr_controller/                  # HLS 커널 2: PR FSM 제어
│   ├── pr_controller.cpp           #   IDLE→DRAINING→RECONFIGURING→DONE
│   ├── pr_controller.hpp
│   └── pr_controller_tb.cpp
│
├── partial_bitstream_demo/         # HLS 커널 3: 재구성 대상 ISP 커널 (참조)
│   ├── binning_gain.cpp
│   └── binning_gain.hpp
│
├── hdl/
│   ├── static/                     # 정적 영역 RTL (합성 + 시뮬레이션 공용)
│   │   ├── top.v                   #   최상위 모듈 (mode 포트 없음 — DFX 합성용)
│   │   ├── checker_wrapper.v       #   8픽셀 이동평균 밝기 판정
│   │   └── pr_controller_wrapper.v #   IDLE/DRAIN/RECONFIG/DONE FSM
│   ├── rp/                         # 재구성 파티션 RTL
│   │   ├── rp_wrapper_normal.v     #   Config 1 전용: 1×1 Binning (mode 포트 없음)
│   │   ├── rp_wrapper_lowlight.v   #   Config 2 전용: 2×2 Binning + ×1.5 Gain
│   │   └── rp_wrapper.v            #   통합 behavioral 모델 (전환 시뮬레이션용)
│   ├── sim/
│   │   └── top_sim.v               #   시뮬레이션 전용 top (mode → rp_wrapper 연결)
│   └── tb/
│       ├── tb_top.v                #   Config별 단독 검증
│       └── tb_top_transition.v     #   NORMAL→LOW_LIGHT 전환 시나리오
│
├── Tcl_HD/
│   ├── design_utils.tcl            # DFX 헬퍼 함수 (lock, pr_verify, bitstream)
│   ├── implement.tcl               # UG947 DFX 전체 구현 플로우 (8단계)
│   ├── run_sim.tcl                 # Config별 단독 RTL 시뮬레이션
│   └── run_sim_transition.tcl      # NORMAL→LOW_LIGHT 전환 시뮬레이션
│
├── xdc/
│   ├── top_zcu104.xdc              # I/O 핀 + 클럭 타이밍 제약
│   └── pblocks_zcu104.xdc          # RP pblock 배치 제약
│
├── Synth/                          # 합성 DCP (implement.tcl 실행 후 생성)
│   ├── top_synth.dcp
│   ├── rp_normal_synth.dcp
│   └── rp_lowlight_synth.dcp
├── Impl/
│   ├── config1/                    # Config 1 opt/place/route/locked DCP
│   └── config2/                    # Config 2 opt/place/route DCP
├── Bitstreams/
│   ├── config1_normal_full.bit     # 전체 비트스트림 (보드 초기화)
│   ├── config1_normal_partial.bit  # Config 1 파셜 비트스트림 (1.4 MB)
│   └── config2_low_light_partial.bit
│
├── create_project.tcl              # Vivado 프로젝트 생성 + HLS IP 등록
├── Makefile                        # HLS C-Sim + 합성 + IP Export 자동화
└── README.md
```

---

## 4. 전제 조건 및 라이선스

| 도구      | 검증 버전            | 용도                                         |
| --------- | -------------------- | -------------------------------------------- |
| Vitis HLS | 2024.1               | HLS 커널 C-시뮬레이션 + RTL 합성 + IP Export |
| Vivado    | 2024.1               | RTL 시뮬레이션 + DFX 구현 + 비트스트림 생성  |
| GNU Make  | 3.8+                 | HLS 빌드 자동화                              |
| ZCU104    | xczu7ev-ffvc1156-2-e | 타깃 하드웨어 보드                           |

> **DFX 라이선스 필요:** Vivado DFX(Partial Reconfiguration) 기능은 별도 라이선스가 필요합니다.  
> 시뮬레이션(`run_sim.tcl`, `run_sim_transition.tcl`)은 **DFX 라이선스 없이** 실행 가능합니다.

라이선스 확인:

```tcl
# Vivado Tcl 창에서
get_param general.licenseStatus
# 또는
report_license_status
```

---

## Step 1 — HLS 커널 합성 및 IP Export

### 1-1. 개요

세 개의 Vitis HLS 커널을 합성하고, 각각을 Vivado IP Catalog에 등록 가능한 형태로 Export합니다.

| 커널                   | 파일                                      | 역할                              |
| ---------------------- | ----------------------------------------- | --------------------------------- |
| `checker_kernel`       | `checker/checker.cpp`                     | 8픽셀 이동평균 → 밝기 판정        |
| `pr_controller_kernel` | `pr_controller/pr_controller.cpp`         | PR FSM (IDLE/DRAIN/RECONFIG/DONE) |
| `binning_gain_kernel`  | `partial_bitstream_demo/binning_gain.cpp` | Binning + Gain 참조 구현          |

### 1-2. 실행

```bash
cd /home/mini/isp/pr_cnn/project/isppipeline/demo
make all
```

`make all`은 세 커널 각각에 대해 다음을 순서대로 실행합니다:

```text
csim_design      → C++ 레벨 기능 검증
csynth_design    → HLS → RTL 변환 (Verilog 생성)
export_design -format ip_catalog  → Vivado IP 패키지 생성
```

완료 후 검증:

```bash
ls checker_prj/solution1/impl/ip/component.xml
ls pr_controller_prj/solution1/impl/ip/component.xml
ls partial_bitstream_demo_prj/solution1/impl/ip/component.xml
```

세 파일이 모두 존재하면 성공입니다.

### 1-3. Checker 커널 동작 원리

```text
픽셀 입력 → 8픽셀 이동평균 계산 → sum/cnt 비교
  sum < 임계값(예: 400 for 8픽셀×50) → mode_out = 1 (LOW_LIGHT)
  sum ≥ 임계값                        → mode_out = 0 (NORMAL)
```

ISPPipeline_accel 커널(`xf_isp_accel.cpp`)은 이보다 정교한 메커니즘을 사용합니다:

```cpp
#define LOW_LIGHT_ENTER_TH  8192u   // 12.5% of 65535
#define LOW_LIGHT_EXIT_TH  16384u   // 25% of 65535
#define MODE_HYSTERESIS        3u   // 3프레임 연속 확인 후 전환
```

### 1-4. PR Controller FSM 상태 설명

| 상태 (Hex) | 이름              | 역할                                   |
| ---------- | ----------------- | -------------------------------------- |
| 0x0        | `S_IDLE`          | mode_changed 신호 대기                 |
| 0x1        | `S_DRAINING`      | rp_reset=1 → RP 파이프라인 플러시      |
| 0x2        | `S_RECONFIGURING` | icap_start 펄스 → ICAP 비트스트림 로드 |
| 0x3        | `S_DONE`          | rp_reset=0 → 새 RM 활성화              |

---

## Step 2 — RTL 설계 (정적 영역 + RP 모듈)

### 2-1. DFX RTL 파일 분리 원칙 (UG947 핵심)

UG947의 핵심 원칙은 **각 Config의 RM을 별도 RTL 파일로 분리**하는 것입니다.

```text
❌ 잘못된 방식 (DFX 불가):
  rp_wrapper.v → if (mode) { 2×2 Binning } else { 1×1 Binning }
  → mode 신호가 RP 경계를 넘나들어 DFX 플로우 위반

✅ 올바른 방식 (DFX 표준):
  rp_wrapper_normal.v   → 1×1 Binning만 구현 (mode 포트 없음)
  rp_wrapper_lowlight.v → 2×2 Binning + ×1.5 Gain만 구현 (mode 포트 없음)
  rp_wrapper.v          → 전환 시뮬레이션 전용 behavioral 모델 (DFX 합성 제외)
```

### 2-2. Config 1 RM — `rp_wrapper_normal.v` (1×1 Binning)

```verilog
module rp_wrapper (   // Config 1 전용 — mode 포트 없음
    input  wire        clk,
    input  wire        reset_n,
    input  wire [7:0]  data_in,
    input  wire        data_valid,
    output reg  [7:0]  data_out,
    output reg         data_out_valid
);
    // 1×1 Binning: 입력 그대로 pass-through
    always @(posedge clk) begin
        if (!reset_n) begin
            data_out       <= 8'd0;
            data_out_valid <= 1'b0;
        end else begin
            data_out       <= data_in;
            data_out_valid <= data_valid;
        end
    end
endmodule
```

### 2-3. Config 2 RM — `rp_wrapper_lowlight.v` (2×2 Binning + ×1.5 Gain)

```verilog
module rp_wrapper (   // Config 2 전용 — mode 포트 없음
    input  wire        clk,
    input  wire        reset_n,
    input  wire [7:0]  data_in,
    input  wire        data_valid,
    output reg  [7:0]  data_out,
    output reg         data_out_valid
);
    // 2×2 Binning: 4픽셀 누적 → 평균 → ×1.5 Gain
    // bin_cnt: 0→1→2→3, bin_cnt=3일 때만 출력
    reg [1:0]  bin_cnt;
    reg [9:0]  bin_sum;   // 4 × 255 = 1020 → 10비트 충분

    always @(posedge clk) begin
        if (!reset_n) begin
            bin_cnt        <= 2'd0;
            bin_sum        <= 10'd0;
            data_out       <= 8'd0;
            data_out_valid <= 1'b0;
        end else if (data_valid) begin
            bin_sum <= bin_sum + {2'b0, data_in};
            bin_cnt <= bin_cnt + 2'd1;
            data_out_valid <= 1'b0;
            if (bin_cnt == 2'd3) begin
                // 평균: bin_sum/4, Gain ×1.5 = ×3/2
                // (bin_sum/4) × 3/2 = bin_sum × 3 / 8 = bin_sum*3 >> 3
                reg [10:0] avg_x3;
                avg_x3 = bin_sum + (bin_sum >> 1);   // ×1.5
                data_out       <= (avg_x3[10:3] > 8'd255) ? 8'd255
                                                           : avg_x3[10:3];
                data_out_valid <= 1'b1;
                bin_sum        <= 10'd0;
                bin_cnt        <= 2'd0;
            end
        end else begin
            data_out_valid <= 1'b0;
        end
    end
endmodule
```

> **검증값:** pixel_in=40, 4픽셀 입력 시  
> `bin_sum = 160`, `avg_x3 = 160×3/2 = 240`, `240>>3 = 30`  
> — 실제 설계에서는 계산식에 따라 `(40×4×3)>>3 = 60`

### 2-4. top.v — 정적 영역 최상위 모듈

```verilog
// DFX 합성용 top.v — mode 포트 없음
// HD.RECONFIGURABLE 속성은 implement.tcl에서 u_rp에 설정

module top (
    input  wire        clk,
    input  wire        reset_n,
    input  wire [7:0]  pixel_in,
    input  wire        pixel_valid,
    output wire [7:0]  pixel_out,
    output wire        pixel_out_valid
);
    wire        mode_out;
    wire        mode_changed;
    wire        rp_reset;
    wire        icap_start;
    wire [7:0]  rp_data_out;
    wire        rp_data_out_valid;

    // 정적: 밝기 분석
    checker_wrapper u_checker (
        .clk         (clk),
        .reset_n     (reset_n),
        .pixel_in    (pixel_in),
        .pixel_valid (pixel_valid),
        .mode_out    (mode_out),
        .mode_changed(mode_changed)
    );

    // 정적: PR FSM
    pr_controller_wrapper u_pr_ctrl (
        .clk         (clk),
        .reset_n     (reset_n),
        .mode_changed(mode_changed),
        .rp_reset    (rp_reset),
        .icap_start  (icap_start)
    );

    // RP: 재구성 대상 (Config 1: 1×1 Binning / Config 2: 2×2 Bin+Gain)
    rp_wrapper u_rp (    // ← HD.RECONFIGURABLE 속성을 이 인스턴스에 설정
        .clk            (clk),
        .reset_n        (~rp_reset),
        .data_in        (pixel_in),
        .data_valid     (pixel_valid & ~rp_reset),
        .data_out       (rp_data_out),
        .data_out_valid (rp_data_out_valid)
    );

    assign pixel_out       = rp_data_out;
    assign pixel_out_valid = rp_data_out_valid & ~rp_reset;
endmodule
```

### 2-5. pblocks_zcu104.xdc — RP 영역 플로어플랜

```xdc
# RP pblock: ZCU104 중간 영역 (SLR0)
# 실제 배치 전 Vivado Floorplan Editor에서 검토 필요
create_pblock pblock_rp
add_cells_to_pblock [get_pblocks pblock_rp] [get_cells -hierarchical -filter {NAME =~ *u_rp*}]
resize_pblock [get_pblocks pblock_rp] -add {SLICE_X0Y120:SLICE_X59Y179}
resize_pblock [get_pblocks pblock_rp] -add {DSP48E2_X0Y48:DSP48E2_X5Y71}
resize_pblock [get_pblocks pblock_rp] -add {RAMB18_X0Y48:RAMB18_X3Y71}
resize_pblock [get_pblocks pblock_rp] -add {RAMB36_X0Y24:RAMB36_X3Y35}

set_property HD.RECONFIGURABLE       true  [get_cells u_rp]
set_property RESET_AFTER_RECONFIG    true  [get_pblocks pblock_rp]
set_property SNAPPING_MODE           ON    [get_pblocks pblock_rp]
```

---

## Step 3 — RTL 기능 시뮬레이션

### 3-1. Config별 단독 검증

```bash
cd /home/mini/isp/pr_cnn/project/isppipeline/demo
vivado -mode tcl
```

```tcl
# Vivado TCL 창에서 실행

# Config 1 (NORMAL: rp_wrapper_normal.v)
source Tcl_HD/run_sim.tcl -notrace

# Config 2 (LOW_LIGHT: rp_wrapper_lowlight.v)
set RM_CONFIG "lowlight"
source Tcl_HD/run_sim.tcl -notrace
```

| Config    | Phase 1                      | Phase 2        | Phase 3       | 검증 기준               |
| --------- | ---------------------------- | -------------- | ------------- | ----------------------- |
| NORMAL    | pixel_out=100 (pass-through) | FSM rp_reset=1 | pixel_out=100 | `pixel_out == pixel_in` |
| LOW_LIGHT | 4픽셀마다 출력               | FSM rp_reset=1 | pixel_out=60  | `(40×4×3)>>3 = 60`      |

### 3-2. NORMAL→LOW_LIGHT 전환 시뮬레이션

```tcl
source Tcl_HD/run_sim_transition.tcl -notrace
```

전환 흐름:

```text
[Phase 1] pixel_in=100 × 16클럭  → pixel_out=100, mode_out=0  (NORMAL)
[Phase 2] pixel_in=30  × 8클럭   → 8픽셀 평균 완료: mode_changed 펄스
                                    pr_controller: IDLE→DRAINING→RECONFIGURING→DONE
                                    rp_reset: 0→1→0, pixel_out_valid=0 유지
[Phase 3] pixel_in=40  × 20클럭  → pixel_out=60, mode_out=1   (LOW_LIGHT)
```

### 3-3. 파형 뷰어 (GUI)

```tcl
start_gui

# 파형 DB 열기
open_wave_database sim_out/xsim_transition/isp_sim_trans.sim/sim_1/behav/xsim/tb_top_transition_behav.wdb

# 신호 그룹 추가
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

# FSM 상태 이름 표시
set_property radix symbolic [get_waves /tb_top_transition/u_dut/u_pr_ctrl/state]
```

### 3-4. 타이밍 다이어그램 핵심 관찰 포인트

**포인트 1 — Checker 누적 구간 (~165ns ~ 245ns)**

- `cnt`: 0→7 증가 중 `sum` 갱신
- `sum < 400` 시점에 `mode_out: 0→1`
- 다음 클럭에 `mode_changed` 1클럭 펄스

**포인트 2 — PR Controller FSM 전환 (~245ns ~ 430ns)**

```text
mode_changed 펄스 → IDLE → DRAINING   (rp_reset=1)
pipeline_empty    → DRAINING → RECONFIGURING  (icap_start=1 펄스)
reconfig_cnt=16   → RECONFIGURING → DONE → IDLE  (rp_reset=0)
```

**포인트 3 — 모드 전환 경계 (~430ns)**

- `rp_reset=0` 직후 `pixel_valid=1` 재개
- `bin_cnt`: 0→1→2→3 반복 시작 (LOW_LIGHT 모드)

**포인트 4 — 전환 전후 패턴 비교**

| 구간               | `pixel_out_valid` | `pixel_out` 패턴 |
| ------------------ | ----------------- | ---------------- |
| NORMAL (0~165ns)   | 매 클럭 HIGH      | 100 flat         |
| PR 중 (245~430ns)  | 계속 LOW          | X (무효)         |
| LOW_LIGHT (430ns~) | 4클럭마다 HIGH    | 60 펄스          |

> **이 패턴 변화(연속→무효→간헐)가 DFX 전환의 핵심 증거입니다.**

---

## Step 4 — DFX 구현 플로우 (비트스트림 생성)

### 4-1. 전체 구현 플로우 실행

```bash
cd /home/mini/isp/pr_cnn/project/isppipeline/demo
vivado -mode tcl
```

```tcl
# Vivado TCL 창에서
source Tcl_HD/implement.tcl -notrace
```

### 4-2. implement.tcl 내부 실행 순서 (UG947 기반 8단계)

```text
[STEP 1a] 정적 영역 합성 (OOC 포함)
          synth_design -top top -include_dirs hdl/static/
          → HD.RECONFIGURABLE true 설정 후 합성
          → Synth/top_synth.dcp

[STEP 1b] Config 1 RM 합성 (OOC — Out-Of-Context)
          synth_design -top rp_wrapper -mode out_of_context
          → 소스: hdl/rp/rp_wrapper_normal.v
          → Synth/rp_normal_synth.dcp

[STEP 1c] Config 2 RM 합성 (OOC)
          synth_design -top rp_wrapper -mode out_of_context
          → 소스: hdl/rp/rp_wrapper_lowlight.v
          → Synth/rp_lowlight_synth.dcp

[STEP 2 ] Config 1 조립 (link_design)
          open_checkpoint Synth/top_synth.dcp
          read_xdc xdc/top_zcu104.xdc
          read_xdc xdc/pblocks_zcu104.xdc
          read_checkpoint -cell u_rp Synth/rp_normal_synth.dcp
          link_design -reconfig_partitions u_rp
          → Impl/config1/linked.dcp

[STEP 3 ] Config 1 구현 (opt → place → route)
          opt_design
          place_design
          route_design
          → Impl/config1/routed.dcp

[STEP 4 ] 정적 영역 잠금 (UG947 핵심)
          update_design -cell u_rp -black_box
          lock_design -level routing
          → Impl/config1/routed_locked.dcp
          (이 DCP가 Config 2 구현의 기반이 됨)

[STEP 5 ] Config 2 조립
          open_checkpoint Impl/config1/routed_locked.dcp
          read_checkpoint -cell u_rp Synth/rp_lowlight_synth.dcp
          → Impl/config2/linked.dcp

[STEP 6 ] Config 2 구현
          opt_design
          place_design
          route_design
          → Impl/config2/routed.dcp

[STEP 7 ] DFX 검증 (pr_verify)
          pr_verify -full_check \
              Impl/config1/routed.dcp \
              Impl/config2/routed.dcp
          → Impl/pr_verify_report.rpt
          (두 Config의 정적 영역 라우팅 일치 확인)

[STEP 8 ] 비트스트림 생성
          # Config 1 전체 + 파셜
          write_bitstream -force -file Bitstreams/config1_normal_full.bit \
              Impl/config1/routed.dcp
          write_bitstream -force -cell u_rp \
              -file Bitstreams/config1_normal_partial.bit \
              Impl/config1/routed.dcp

          # Config 2 파셜만 (정적 영역은 Config 1과 동일)
          write_bitstream -force -cell u_rp \
              -file Bitstreams/config2_low_light_partial.bit \
              Impl/config2/routed.dcp
```

### 4-3. 출력 비트스트림

```text
Bitstreams/
├── config1_normal_full.bit          ~19 MB  보드 초기 프로그래밍용
├── config1_normal_partial.bit       ~1.4 MB Config 1 RM (NORMAL)
└── config2_low_light_partial.bit    ~1.4 MB Config 2 RM (LOW_LIGHT, 런타임 교체)
```

파셜 비트스트림(1.4 MB)이 전체(19 MB)의 약 **7%** — RP 영역만 재구성하므로 재구성 시간 대폭 단축

### 4-4. design_utils.tcl 헬퍼 함수 요약

| 함수                                                 | 설명                                                      |
| ---------------------------------------------------- | --------------------------------------------------------- |
| `lock_static_design <routed_dcp> <out_dcp>`          | `update_design -black_box` + `lock_design -level routing` |
| `run_pr_verify <dcp1> <dcp2> <rpt_dir>`              | `pr_verify -full_check` 실행                              |
| `generate_dfx_bitstreams <config_name> <dcp> <cell>` | UCIO-1 DRC Warning 처리 후 Full + Partial 비트스트림 생성 |

---

## Step 5 — Vivado 프로젝트 모드 GUI 플로우 (선택)

UG947 Lab 4는 Non-project(Tcl) 플로우와 Project 모드 GUI 플로우를 모두 지원합니다.  
GUI 플로우는 디버깅 및 학습 목적에 유용합니다.

### 5-1. Vivado 프로젝트 생성

```tcl
# Vivado TCL 창에서 (혹은 vivado -mode tcl -source create_project.tcl)
source create_project.tcl -notrace
```

`create_project.tcl` 핵심 내용:

```tcl
close_project -quiet
create_project isp_pr_project ./isp_pr_project \
    -part xczu7ev-ffvc1156-2-e -force
set_property board_part xilinx.com:zcu104:part0:1.1 [current_project]

# HLS IP 레포지토리 등록 (3개 경로 모두 필요)
set ip_repo_paths [list \
    "[pwd]/checker_prj/solution1/impl/ip" \
    "[pwd]/pr_controller_prj/solution1/impl/ip" \
    "[pwd]/partial_bitstream_demo_prj/solution1/impl/ip" \
]
set_property ip_repo_paths $ip_repo_paths [current_project]
update_ip_catalog
```

### 5-2. GUI에서 DFX 설정 확인

1. **Flow Navigator → Project Settings → General** → "Enable Dynamic Function eXchange" 체크
2. **Sources 창** → `u_rp` 인스턴스 우클릭 → "Set as Reconfigurable Partition"
3. **DFX Wizard** → Configuration 추가 → Config 1 (rp_wrapper_normal), Config 2 (rp_wrapper_lowlight)
4. **Flow Navigator → Run Implementation** → 각 Configuration 선택 후 실행

### 5-3. UG947 Lab 4 참조 흐름 (dfx_project_debug)

현재 로컬에 저장된 UG947 Lab 4 예제 (`/home/mini/vivado-tutorial/vivado-pr-tutorial/dfx_project_debug/`):

```text
Sources/
├── hdl/
│   ├── top.v           # 정적 최상위 (multiplier/adder 선택 RP)
│   ├── adder/add.v     # RM 1: 덧셈기
│   └── multiplier/mult.v  # RM 2: 곱셈기 (VIO + ILA 디버그 포함)
└── xdc/
    ├── top_io_zcu104.xdc
    └── pblocks_zcu104.xdc
```

Lab 4 구조와 ISP 프로젝트 구조 매핑:

| Lab 4 (UG947) | ISP 프로젝트 |
|---------------|-------------|
| `add.v` (RM 1) | `rp_wrapper_normal.v` (Config 1) |
| `mult.v` (RM 2) | `rp_wrapper_lowlight.v` (Config 2) |
| VIO IP | checker_wrapper (밝기 기반 자동 전환) |
| `child_0_impl_1` | `Impl/config1/` |
| `child_1_impl_1` | `Impl/config2/` |

---

## Step 6 — 보드 배포 및 런타임 재구성

### 6-1. 전체 비트스트림으로 초기 프로그래밍

```tcl
# Vivado Hardware Manager에서
open_hw_manager
connect_hw_server
open_hw_target
current_hw_device [get_hw_devices xczu7ev_0]
set_property PROGRAM.FILE {Bitstreams/config1_normal_full.bit} [current_hw_device]
program_hw_devices [current_hw_device]
```

또는 shell에서:

```bash
vivado -mode batch -source - <<'EOF'
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
program_hw_devices [get_hw_devices xczu7ev_0] \
    -file Bitstreams/config1_normal_full.bit
EOF
```

### 6-2. 런타임 파셜 비트스트림 교체 (PCAP/ICAP)

ZCU104에서는 Zynq PS의 PCAP(PS Configuration Access Port)을 사용합니다.

**방법 1: Linux devmem / devcfg (Baremetal)**

```c
// PS 측 baremetal 코드 (ZCU104)
// 파셜 비트스트림을 DDR에 로드 후 PCAP 전송
void load_partial_bitstream(const char *bin_path) {
    // 1. 파셜 비트스트림 파일을 DDR로 로드
    // 2. PCAP DMA 설정
    // 3. 전송 완료 대기
    // 4. RP 영역 리셋 해제
}
```

**방법 2: Linux fpga-manager (PetaLinux)**

```bash
# PetaLinux 환경에서
echo 0 > /sys/class/fpga_manager/fpga0/flags
cp config2_low_light_partial.bin /lib/firmware/
echo config2_low_light_partial.bin > /sys/class/fpga_manager/fpga0/firmware
```

> 파셜 비트스트림은 `.bit` → `.bin` 변환이 필요합니다 (헤더 제거).

### 6-3. pr_trigger 신호와 PS 연동

`ISPPipeline_accel` 커널은 밝기 전환을 감지하면 `pr_trigger` AXI-lite 레지스터를 1로 설정합니다.  
PS 소프트웨어는 이 레지스터를 폴링하거나 인터럽트로 감지해 파셜 비트스트림 교체를 트리거합니다.

```c
// PS 소프트웨어 의사 코드
while (running) {
    uint32_t trig = read_axi_reg(ISP_BASE + PR_TRIGGER_OFFSET);
    if (trig & 0x1) {
        uint32_t mode = read_axi_reg(ISP_BASE + MODE_REG_OFFSET);
        if (mode & 0x02) {
            // 저조도 모드 진입
            load_partial_bitstream("config2_low_light_partial.bin");
        } else {
            // 일반 모드 복귀
            load_partial_bitstream("config1_normal_partial.bin");
        }
        write_axi_reg(ISP_BASE + PR_TRIGGER_OFFSET, 0);  // clear
    }
    usleep(1000);  // 1ms 폴링 주기
}
```

---

## ISPPipeline_accel 커널과 DFX 연동

### 전체 시스템 데이터 흐름

```text
DDR (Bayer Raw 16-bit)
      ↓  AXI DMA / HPC0
ISPPipeline_accel (HLS 커널)
  ├── compute_brightness_checker()  → avg_brt
  ├── FSM 히스테리시스 (3프레임)    → mode_reg_adaptive (bit 1)
  ├── pr_trigger 펄스               → PS 소프트웨어 인터럽트
  └── ISPpipeline()
        ├── blackLevelCorrection
        ├── function_bpc()           ← 저조도 시 badpixelcorrection 활성화
        ├── gaincontrol()            ← 저조도 시 rgain/bgain ×2 부스트
        ├── demosaicing
        ├── function_awb()
        ├── colorcorrectionmatrix
        ├── gammacorrection
        └── rgb2yuyv → DDR
```

### mode_reg 비트 인코딩

```text
bit 0 : AWB enable     (호스트가 AXI-lite로 제어)
bit 1 : low-light mode (brightness checker FSM이 자동 설정)
```

```cpp
// 저조도 판정 시 Gain 2배 부스트 (xf_isp_accel.cpp:249-253)
ap_uint<1> ll_mode     = (ap_uint<1>)((mode_reg >> 1) & 0x01u);
uint32_t   boost_rgain = ll_mode ? ((uint32_t)rgain << 1) : (uint32_t)rgain;
uint32_t   boost_bgain = ll_mode ? ((uint32_t)bgain << 1) : (uint32_t)bgain;
```

### HLS 커널과 RP 모듈의 역할 분리

| 계층                  | 구성 요소                      | 역할                                                               |
| --------------------- | ------------------------------ | ------------------------------------------------------------------ |
| HLS 커널 (전체 ISP)   | `ISPPipeline_accel`            | BLC → BPC → Gain → Demosaic → AWB → CCM → Gamma                    |
| HLS 커널 (ISP for AI) | `new_code/xf_isp_accel.cpp`    | Binning(AREA resize) → Gain → LTM → Sobel → Sharpen → 300×300 출력 |
| RTL RP (demo)         | `rp_wrapper_normal/lowlight.v` | ISP 개념 검증용 Binning/Gain (8-bit 픽셀 레벨)                     |

> ISP 전체 파이프라인의 DFX 적용 시, `rp_wrapper_lowlight`에 해당하는 부분을  
> HLS로 합성된 `gaincontrol` + `badpixelcorrection` IP 블록으로 대체할 수 있습니다.

---

## UG947 DFX 플로우 매핑표

| UG947 단계         | UG947 명령/개념                        | 본 프로젝트 대응            |
| ------------------ | -------------------------------------- | --------------------------- |
| Step 1: Extract    | 파일 준비                              | `make all` → HLS IP Export  |
| Step 2: Examine    | 스크립트 이해                          | `Tcl_HD/implement.tcl` 검토 |
| Step 3: Synthesize | `synth_design` (Static + OOC RM)       | STEP 1a/1b/1c               |
| Step 4: Assemble   | `link_design`, `read_checkpoint -cell` | STEP 2, 5                   |
| Step 5: Floorplan  | `create_pblock`, `HD.RECONFIGURABLE`   | `pblocks_zcu104.xdc`        |
| Step 6: Implement  | `opt/place/route_design` × 2 Config    | STEP 3, 6                   |
| Step 7: Analyze    | `pr_verify -full_check`                | STEP 7                      |
| Step 8: Bitstream  | `write_bitstream -cell`                | STEP 8                      |
| Step 9: PR on HW   | PCAP/ICAP 로드                         | Step 6-2/6-3                |
| Step 10: Test      | ILA/VIO 검증                           | 파형 뷰어 확인              |

---

## 알려진 문제 및 트러블슈팅

### 문제 1: Tcl `puts` 안의 `[TAG]` 명령 치환 에러

```text
ERROR: invalid command name "SIM"
```

**원인:** Tcl에서 `"..."` 안의 `[...]`는 명령 치환으로 해석됩니다.  
**해결:** `puts` 문자열을 중괄호 `{...}`로 변경

```tcl
# 에러
puts "\n[SIM] Loading RTL sources..."

# 수정
puts {[SIM] Loading RTL sources...}
```

### 문제 2: in-memory 프로젝트에서 `launch_simulation` 실패

```text
ERROR: [Common 17-53] User Exception: The current project is in-memory.
```

**해결:** 디스크에 프로젝트를 생성한 후 시뮬레이션 실행

```tcl
# 수정된 방식
create_project isp_sim ./sim_out/xsim_proj -part xczu7ev-ffvc1156-2-e
add_files -norecurse [glob ./hdl/static/*.v]
# ...
launch_simulation -simset sim_1 -mode behavioral
```

### 문제 3: `mode_changed` 펄스 미발생 (non-blocking 경쟁 조건)

**원인:** `always @(posedge clk)` 블록에서 `mode_prev != mode_out` 비교 시, 두 값 모두 이전 클럭 값이어서 전환 시점에 같은 값으로 비교됨.  
**해결:** `wire new_mode`로 분리하여 combinational 비교

```verilog
// 수정 전 (버그)
always @(posedge clk) begin
    mode_prev <= mode_out;
    mode_changed <= (mode_prev != mode_out);  // 항상 0
end

// 수정 후 (정상)
assign new_mode = (sum < THRESHOLD) ? 1'b1 : 1'b0;
always @(posedge clk) begin
    mode_prev <= new_mode;
    mode_out  <= new_mode;
    mode_changed <= (mode_prev != new_mode);  // 올바른 에지 감지
end
```

### 문제 4: TIMING-17 (Non-clocked sequential cell)

**원인:** `create_generated_clock`이 `open_checkpoint` 시점에 핀 경로가 없어 XDC 처리를 중단시킴.  
**해결:** `top_zcu104.xdc`에서 `create_generated_clock` 제거, 기본 클럭 핀(H9, GCIO)만 유지

```xdc
# H9: Bank 65 GCIO (ZCU104 SI570 User Clock 핀)
# 사용 전 ZCU104 schematic(UG1267)에서 실제 핀 번호 확인 필수
set_property PACKAGE_PIN H9 [get_ports clk]
set_property IOSTANDARD LVDS [get_ports clk]
create_clock -period 8.000 -name sys_clk [get_ports clk]
```

### 문제 5: UCIO-1 DRC Warning (데이터 포트 핀 미할당)

`pixel_in`, `pixel_out` 등 데이터 포트에 PACKAGE_PIN 미지정 시 발생.  
비트스트림 생성 시 Warning으로 처리하는 방법:

```tcl
# design_utils.tcl의 generate_dfx_bitstreams에서
set_property SEVERITY {Warning} [get_drc_checks UCIO-1]
write_bitstream -force ...
```

실제 보드 연결 시 반드시 핀 할당이 필요합니다.

### 문제 6: Phase 3 기대값 불일치

2×2 Binning + ×1.5 Gain 계산:

```text
pixel_in=40, 4픽셀 누적 → bin_sum=160
Gain ×1.5 = ×3/2 방식:
  avg_x3 = 160 + (160>>1) = 160 + 80 = 240
  data_out = 240 >> 3 = 30  ← 이 경우

또는 "(40×4×3)>>3" 방식:
  = 480 >> 3 = 60  ← README의 설명

두 방식 중 RTL 구현과 일치하는 값으로 tb_top.v의 expected 값을 맞춰야 합니다.
```

### 문제 7: pblock 내 RP 셀 없음 경고

**원인:** `top.v`의 인스턴스 이름과 `pblocks_zcu104.xdc`의 필터 패턴 불일치  
**해결:** 인스턴스 이름을 `u_rp`로 통일

```xdc
# pblocks_zcu104.xdc
add_cells_to_pblock [get_pblocks pblock_rp] \
    [get_cells -hierarchical -filter {NAME =~ *u_rp*}]
```

---

## 참고 문서

| 문서                                                                                                                                                             | 내용                                                               |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| [UG947 — Vivado DFX Tutorial](https://docs.amd.com/r/en-US/ug947-vivado-partial-reconfiguration-tutorial)                                                        | DFX 튜토리얼 전체 (Lab 1–12)                                       |
| [UG947 Lab 4 — DFX RTL Project Flow](https://docs.amd.com/r/en-US/ug947-vivado-partial-reconfiguration-tutorial/Lab-4-DFX-RTL-Project-Flow-Simulation-and-Debug) | 본 프로젝트와 가장 유사한 Lab                                      |
| [UG909 — Vivado DFX User Guide](https://docs.amd.com/r/en-US/ug909-vivado-partial-reconfiguration)                                                               | DFX 상세 설명                                                      |
| [UG1267 — ZCU104 User Guide](https://docs.amd.com/v/u/en-US/ug1267-zcu104-eval-bd)                                                                               | ZCU104 핀 배치 + 클럭 정보                                         |
| [UG902 — Vitis HLS User Guide](https://docs.amd.com/r/en-US/ug902-vivado-high-level-synthesis)                                                                   | HLS 커널 합성 방법                                                 |
| 로컬 튜토리얼 프로젝트                                                                                                                                           | `/home/mini/vivado-tutorial/vivado-pr-tutorial/dfx_project_debug/` |
| ISP Demo 프로젝트                                                                                                                                                | `/home/mini/isp/pr_cnn/project/isppipeline/demo/`                  |

---

_작성일: 2026-05-18 | 환경: Vivado 2024.1 / ZCU104 xczu7ev-ffvc1156-2-e_
