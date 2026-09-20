# checker — 가이드

`~/Desktop/dfxisp/checker/{checker.cpp, checker.hpp}`

## 무엇인가

프레임의 조도를 판정해 `NORMAL`/`LOW_LIGHT` 모드를 고르는 static-region 측정 모듈. `NormalISP`/`LowlightISP`처럼 재구성 대상 모듈이 아니라 — **always-on static shell**에 상주하는 것을 전제로 설계됐다. DFX 아키텍처에서 어느 ISP 모듈을 스왑할지를 결정하는 판단부다.

원래 `checker_select_mode()` 로직은 통합 top(`dfxisp_accel.cpp`) 안에도 인라인되어 있는데, 이 `checker.cpp`는 그걸 **별도 static-region HLS top(`checker_scan`)으로 분리**한 버전이다 — checker만 따로 합성해서 static 영역 IP로 패키징할 때 이걸 쓴다(원본 레포의 `checker_ip.v`/`package_checker_ip.tcl` 흐름과 연결).

## 판정 로직

```
mode == NORMAL     → selected_mode = NORMAL (강제)
mode == LOW_LIGHT  → selected_mode = LOW_LIGHT (강제)
mode == AUTO       → dark_ratio = dark_count / (W*H)
                      dark = (raw[i] < dark_pixel_threshold)   # RAW 도메인 직접 비교
                      selected_mode = LOW_LIGHT  if  dark_count*100 > verdict_pct*(W*H)  else NORMAL
```

- `dark_pixel_threshold`: HW raw12 규약값 256(=16<<4), "dark16" 통계라고 부름.
- 배포 판정 임계 `verdict_pct = DARK_RATIO_PCT = 62` (C1, 2026-07-20 배포) — Youden's J 기준 C0(dark50>0.80)를 전 지표에서 지배.
- **강제 모드(NORMAL/LOW_LIGHT)일 때도 `hyst_flags`를 그 상태에 맞게 채워서 반환** — 하위 히스테리시스 블록이 강제 오버라이드와 싸우지 않고 그대로 따라가게 하기 위함.

## Schmitt 히스테리시스 (프레임 단위 플리커 방지)

AUTO 모드에서는 단일 임계값 대신 **진입/이탈 두 개의 밴드**를 같이 계산해서 내보낸다 — 이건 `checker_scan` 자체가 상태를 갖는 게 아니라(무상태 유지), 프레임마다 두 비교 결과를 플래그 비트로 얹어 내보내는 것뿐이다:

- `DFXISP_HYST_ABOVE_ENTER` (bit 0): dark_ratio > 64%
- `DFXISP_HYST_BELOW_EXIT` (bit 1): dark_ratio < 60%
- 중심 62% ± 2%p 밴드

실제 모드 상태(FF), min-dwell, PR 컨트롤러 트리거 request/ack는 **이 모듈 밖의 static-region Verilog(`checker_hysteresis.v`)**가 소유한다 — `checker.cpp`는 그 입력이 되는 플래그만 계산해서 넘긴다. `checker_hysteresis.v`는 이 폴더에 없음(cpp/hpp만 우선 확보 — Verilog가 필요해지면 원본 레포의 `isppipeline/hls/checker/` 참고).

## 인터페이스

```cpp
extern "C" void checker_scan(
    const uint16_t* raw_bayer,      // RAW RGGB 12-bit in uint16 (W*H)
    int width, int height,
    int mode,                       // DFXISP_MODE_NORMAL/LOW_LIGHT/AUTO
    uint16_t dark_pixel_threshold,  // AUTO 판정용 RAW 임계값 (규약: 256)
    int verdict_pct,                // 단일 임계 판정 % (배포값 62)
    int enter_pct, int exit_pct,    // 히스테리시스 진입/이탈 % (배포값 64/60)
    int* selected_mode,             // 출력: 최종 판정 모드
    int* hyst_flags,                // 출력: Schmitt 밴드 플래그 (ap_vld wire)
    int* dark_count);                // 출력: 측정된 dark 픽셀 수
```

### HLS 인터페이스 프라그마

| 포트 | 인터페이스 | 비고 |
|---|---|---|
| `raw_bayer` | `m_axi` bundle=gmem0, depth=2048, `max_widen_bitwidth=128` | AXI Master, 풀스캔 read |
| `hyst_flags` | **`ap_vld`** (fabric wire) | s_axilite 레지스터가 **아님** — 프레임 완료당 1펄스로 `checker_hysteresis.v`에 직결되는 fabric 신호. PS는 관측만 하고 판단 경로에 끼지 않음 |
| 나머지 스칼라(`width`/`height`/`mode`/`dark_pixel_threshold`/`verdict_pct`/`enter_pct`/`exit_pct`/`selected_mode`/`dark_count`) | `s_axilite` bundle=control | |
| `return` | `s_axilite` bundle=control | |

`hyst_flags`가 `ap_vld` wire라는 게 이 모듈에서 가장 특이한 부분이다 — Vivado에서 static-region 배선을 할 때 이 포트는 AXI-Lite 레지스터 read-back이 아니라 **fabric 신호로 직접 연결**해야 한다.

## 핵심 상수

| 상수 | 값 | 의미 |
|---|---|---|
| `DARK_RATIO_PCT` | 62 | C1 배포 판정 임계(%) — real RAW 642장 검증, 오라클 라벨 재검증까지 통과 |
| `HYST_ENTER_PCT` | 64 | 진입 임계(%) |
| `HYST_EXIT_PCT` | 60 | 이탈 임계(%) |
| `DFXISP_MODE_NORMAL/LOW_LIGHT/AUTO` | 0/1/2 | 모드 enum (원래 `dfxisp_accel.hpp`에서 정의되던 것을 이 hpp에 inline) |
| `DFXISP_HYST_ABOVE_ENTER/BELOW_EXIT` | 1/2 | 히스테리시스 플래그 비트 (역시 inline) |

`checker.hpp`는 이 저장소 안에서 **완전히 자립적**이다(원래 `dfxisp_accel.hpp`를 include했으나, enum 6개만 쓰길래 값 그대로 inline 처리 — 원본과 값 동일).

## 검증 상태 (원본 SPEC.md 기준)

- ✅ 배포 임계 C1(62%): recall 0.936, false-trigger 0.089, Youden's J 0.847 — C0(80%) 지배
- ✅ 오라클 라벨 재검증(2026-07-20): C1 잔존오차의 89.6%가 라벨 아티팩트, 비용-중립점 성질은 유지 → 재조정 불필요로 결론
- ✅ 히스테리시스 체인 end-to-end xsim PASS(`checker_to_dfxc_tb.v`, 원본 레포)
- ⬜ **보드 미검증** — 이번 브링업에서 NormalISP와 함께 실물로 처음 확인되는 부분

## DFX 실장 가이드: RP/RM 구성 → checker 하드웨어 트리거 → ZCU104

`~/Desktop/tutorials/dfx_calculator`(원작 [vandinhtranengg/zcu104-dfx-calculator-demo](https://github.com/vandinhtranengg/zcu104-dfx-calculator-demo), `docs/DFX_Note.md`)는 같은 ZCU104 보드에서 ADD/SUB 두 HLS 모듈을 실제 Reconfigurable Partition(RP)으로 교체하는 **완전히 검증된 DFX 데모**다 — HLS 소스, `dfx_pblock.xdc`, 실물 `ADD.BIT`/`SUB.BIT`, 베어메탈 `main.c`까지 전부 포함되어 있다. 이 절은 그 데모의 RP/RM 구축 절차를 `NormalISP`/`LowlightISP`에 매핑하고, `checker`가 실제로 어디에 끼워지는지를 정리한다.

> **범위와 전제:** `docs/NormalISP.md`/`docs/LowlightISP.md`의 static 브링업(각자 독립된 정적 비트스트림으로 보드에서 검증)이 이미 끝났다고 가정한다. 이 절이 그 둘을 **진짜 하나의 DFX 시스템**으로 합치는 단계다.

### 0. 두 가지 트리거 전략 — 계산기 데모 그대로 vs 이 프로젝트의 목표

계산기 데모와 이 프로젝트는 **RP/RM을 만드는 Vivado 절차는 동일**하지만, **런타임에 누가 재구성을 트리거하는가**가 다르다:

| | 계산기 데모 (검증용 1단계로 그대로 활용) | 이 프로젝트의 목표(SPEC.md §7) |
|---|---|---|
| 트리거 주체 | PS 소프트웨어(`main.c`)가 `sleep(10)` 같은 하드코딩된 순서로 결정 | `checker` + `checker_hysteresis.v`가 fabric에서 자율 결정 |
| 비트스트림 로드 | 베어메탈 `XFpga_BitStream_Load()`, SD카드 `ADD.BIT`/`SUB.BIT` | AMD DFX Controller IP(PG374)가 DDR의 bitstream table에서 직접 fetch, ICAP 구동 |
| AXI 격리 | DFX AXI Shutdown Manager, 소프트웨어가 enable/disable | PG374 내장 shutdown handshake + DFX Decoupler |
| PS의 역할 | 판단 + 로드 + 격리 전부 담당 | **관측만**(`selected_mode` AXI-Lite read-back) — 판단 경로에 없음 |

**권장 순서:** 계산기 데모를 **그대로**(ADD→SUB 자리에 `NormalISP`→`LowlightISP`) 먼저 재현해서 "이 두 모듈이 실제로 같은 RP 계약을 만족하는가"를 검증하고(§2), 그다음 소프트웨어 트리거를 걷어내고 `checker`/`checker_hysteresis.v`/PG374 체인으로 교체한다(§3). 계산기 데모가 검증한 건 RP/RM 메커니즘 자체이지 이 프로젝트의 최종 트리거 방식이 아니다 — 이 순서를 건너뛰고 곧장 PG374부터 시작하면 RP 경계 자체의 문제와 트리거 체인의 문제를 구분할 수 없다.

### 1. checker의 실측 AXI-Lite 레지스터 맵

`NormalISP`/`LowlightISP`와 달리 `checker_scan`은 **이 프로젝트에서 이미 실제로 csynth가 돌아간 적이 있다**(원본 레포 `isppipeline/hls/results/hls_work/checker_cosim/`) — 아래는 지어낸 값이 아니라 그 산출물(`xchecker_scan_hw.h`)에서 그대로 가져온 실측 맵이다:

| 오프셋 | 레지스터 | 폭 | 설명 |
|---|---|---|---|
| `0x00` | Control | 32 | bit0 ap_start / bit1 ap_done / bit2 ap_idle / bit3 ap_ready |
| `0x04` | GIER | 32 | Global Interrupt Enable |
| `0x08` | IP_IER | 32 | IP Interrupt Enable |
| `0x0c` | IP_ISR | 32 | IP Interrupt Status |
| `0x10`/`0x14` | `raw_bayer` | 64 | m_axi 포인터 물리주소 하위/상위 32비트 |
| `0x1c` | `width` | 32 | |
| `0x24` | `height` | 32 | |
| `0x2c` | `mode` | 32 | |
| `0x34` | `dark_pixel_threshold` | 16 | |
| `0x3c` | `verdict_pct` | 32 | |
| `0x44` | `enter_pct` | 32 | |
| `0x4c` | `exit_pct` | 32 | |
| `0x54` | `selected_mode` | 32 | 출력 read-only |
| `0x58` | `selected_mode` ap_vld | 1 | |
| `0x64` | `dark_count` | 32 | 출력 read-only |
| `0x68` | `dark_count` ap_vld | 1 | |

`hyst_flags`는 이 표에 **없다** — s_axilite 레지스터가 아니라 순수 fabric `ap_vld` wire이기 때문이다(§인터페이스). 이 맵은 `NormalISP.md`/`LowlightISP.md`가 아직 실측하지 못한 것과 대조적으로, 이미 검증된 실물이니 checker를 static-region IP로 패키징할 때 그대로 참고해도 된다(단 재합성하면 값이 유지되는지 반드시 재확인 — Vitis HLS는 인자 목록이 같으면 동일 오프셋을 안정적으로 재생성하지만, 이 프로젝트 자체가 "재합성해도 값이 바뀌는지 검증 없이 재사용하지 말 것"을 반복적으로 강조해 온 원칙이다).

`checker_scan`의 `raw_bayer` m_axi 포트는 **`NormalISP`/`LowlightISP`가 읽는 것과 같은 물리 버퍼**(`docs/NormalISP.md` §5의 `0x70000000` raw 슬롯)를 가리켜야 한다 — checker는 별도 입력이 아니라 ISP가 처리할 바로 그 프레임을 보고 모드를 판정하는 것이므로, 버퍼를 두 벌 만들 필요가 없다.

### 2. 1단계 — 계산기 데모를 그대로: `NormalISP`↔`LowlightISP` 소프트웨어 스왑 검증

`docs/DFX_Note.md` §6의 절차를 그대로 따라가되 이름만 바꾼다:

1. `NormalISP` IP를 캔버스에 추가 → **Create Hierarchy**(`isp_rp`) → **Create Block Design Container**(`normal_isp_rm`).
2. **Tools → Enable Dynamic Function eXchange → Convert**.
3. `isp_rp` BDC 설정에서 **Enable DFX on this container** + **Freeze the boundary** 체크.
4. **DFX AXI Shutdown Manager** 추가, `Is the RP the Master? = 해제`, `Control Interface Type = AXI LITE`, `Datapath Protocol = AXI4LITE`, `AXI Response to rejected transaction = OKAY`.
5. `axi_interconnect_0`의 Master Interface 수를 2로 늘리고 계산기 데모와 동일하게 배선: `M00_AXI → shutdown_man/S_AXI`, `M01_AXI → shutdown_man/S_AXI_CTRL`, `shutdown_man/M_AXI → isp_rp/s_axi_control`.
6. Address Editor: `isp_rp/NormalISP_0/s_axi_control = 0xA000_0000`(64K), `dfx_axi_shutdown_man_0/S_AXI_CTRL = 0xA001_0000`(64K) — `docs/NormalISP.md` §3이 이미 이 주소를 예약해 둔 이유가 여기다.
7. `isp_rp`를 우클릭 → **Create Reconfigurable Module** → `lowlight_isp_rm` → 그 안에 `LowlightISP` IP 배치, `ap_clk`/`ap_rst_n`/`s_axi_control` 연결, Address Editor에서 **`NormalISP`와 동일한 `0xA000_0000`** 할당.
8. **DFX Wizard**: Edit Reconfigurable Modules에서 두 RM 확인 → Edit Configurations에서 automatically create configurations → Edit Configuration Runs에서 automatically create configuration run.

**pblock — 계산기의 작은 예시가 아니라 이 프로젝트 실측치를 쓸 것.** 계산기 데모의 `dfx_pblock.xdc`(`SLICE_X60Y120:SLICE_X79Y159`, 덧셈기 하나 들어갈 정도의 작은 영역)는 문법 템플릿으로만 참고한다. `NormalISP`(csynth LUT 12,659)/`LowlightISP`(csynth LUT 8,115, denoise OFF 기준)는 훨씬 크므로, 원 연구가 이미 실측해 둔 pblock을 그대로 쓴다(SPEC.md §10.1~§10.3):

```tcl
set_property HD.RECONFIGURABLE true [get_cells dfx_demo_i/isp_rp]
create_pblock pblock_isp_rp
add_cells_to_pblock [get_pblocks pblock_isp_rp] [get_cells dfx_demo_i/isp_rp]
resize_pblock [get_pblocks pblock_isp_rp] -add {CLOCKREGION_X1Y0:CLOCKREGION_X2Y0}
set_property CONTAIN_ROUTING true [get_pblocks pblock_isp_rp]
set_property SNAPPING_MODE ON [get_pblocks pblock_isp_rp]
```

이 pblock은 원 연구에서 LUT 19,200 / BRAM 24 tile / DSP 216 용량을 실측한 영역이다(2026-07-03 재floorplan, `ROADMAP.md` Stage 5·R3) — `NormalISP`(LUT 12,659) 하나만 놓기엔 넉넉하지만, `default_isp`류 두 모듈이 번갈아 들어갈 걸 감안하면 이 정도가 실용적 출발점이다.

**소프트웨어 검증(베어메탈, 계산기 `main.c` 패턴 그대로):** 계산기 데모의 `run_calculator()`가 `result`/`module_id` 레지스터를 비교하는 것과 달리, `NormalISP`/`LowlightISP`는 스칼라 결과가 아니라 **프레임 버퍼**를 만든다. 그래서 검증 로직만 바뀐다 — 나머지(`dfx_shutdown_enable/disable`, `load_partial_bitstream`, `XFpga_BitStream_Load`)는 그대로 재사용 가능하다:

```c
/* main.c의 offset 상수들은 docs/NormalISP.md §2에서 확정한 실제
 * xnormalisp_hw.h 값으로 교체할 것 — 계산기의 CALC_A_OFFSET류를
 * 그대로 복붙하지 말 것(인자 목록이 다르므로 오프셋도 다르다). */
#define ISP_BASEADDR         0xA0000000U
#define ISP_RAW_ADDR_OFFSET  /* xnormalisp_hw.h에서 확인 */
#define ISP_RGB_ADDR_OFFSET  /* 〃 */
#define ISP_WIDTH_OFFSET     /* 〃 */
#define ISP_HEIGHT_OFFSET    /* 〃 */
#define ISP_OUT_W_OFFSET     /* 〃 */
#define ISP_OUT_H_OFFSET     /* 〃 */

/* 계산기의 Step 1/2 구조 그대로: */
dfx_shutdown_enable();
load_partial_bitstream(NORMAL_BIT_FILE);   /* Vivado가 생성한 부분 비트스트림 */
dfx_shutdown_disable();
run_isp(raw_test_frame, DDR_RAW_ADDR, DDR_RGB_ADDR, W, H);
/* 검증: rgb_out을 Python golden(원본 레포 tools/gen_default_isp_golden.py)의
 * 같은 케이스 출력과 바이트 비교 — result==sum 비교의 ISP 버전 */

dfx_shutdown_enable();
load_partial_bitstream(LOWLIGHT_BIT_FILE);
dfx_shutdown_disable();
run_isp(raw_test_frame, DDR_RAW_ADDR, DDR_RGB_ADDR, W, H);
/* out_width/out_height가 bin_dim(W)/bin_dim(H)로 줄어들어 있는지,
 * 값이 gen_lowlight_isp_golden.py와 맞는지 확인 */
```

이 단계가 통과하면(두 RM이 같은 주소에서 문제없이 스왑되고, 각자 golden과 맞는 출력을 낸다) **RP 경계 자체는 검증된 것**이다 — 남은 건 트리거를 소프트웨어에서 하드웨어로 옮기는 것뿐이다.

### 3. 2단계 — 소프트웨어 트리거를 checker/PG374 체인으로 교체

§2가 통과한 뒤, `DFX AXI Shutdown Manager` + 베어메탈 트리거 로직을 걷어내고 이 프로젝트의 실제 목표 구조로 바꾼다. 원본 레포가 2026-08-06에 이미 이 IP를 실제로 생성해 포트 계약까지 확인해 뒀다(`results/pr_controller/dfxc_adapter.md`) — 아래는 그 확인된 내용 그대로다.

**연결 체인:**

```
checker_scan.hyst_flags (ap_vld) ──▶ checker_hysteresis.v ──pr_trigger/pr_busy──▶ dfxc_trigger_adapter.v ──▶ AMD DFX Controller IP (PG374)
    (이 폴더, static IP)              (mode FF + Schmitt +          (request-until-ack 유지,        │ m_axi → DDR (bitstream table)
                                        min-dwell, 원본 레포)         per-RM one-hot 트리거 변환)      │ ICAP → 설정 엔진
                                                                                                    │ decouple → DFX Decoupler
                              rm_ap_idle(활성 RM) ────────────────────────────────▶ shutdown-ack shim
```

**PG374가 실제로 생성하는 포트(원본 레포 2026-08-06 프로브, Vivado 2024.1, `dfx_controller` v1.0 — 지어낸 값 아님):**

| 포트 | 방향/폭 | 역할 |
|---|---|---|
| `vsm_VS_0_hw_triggers` | in [1:0] | 트리거 0→RM_NORMAL, 트리거 1→RM_LOW_LIGHT (one-hot) |
| `vsm_VS_0_rm_shutdown_req` / `_ack` | out 1 / in 1 | shutdown handshake — `_ack`는 `req & rm_ap_idle`로 합성 |
| `vsm_VS_0_rm_decouple` | out 1 | DFX Decoupler 구동 |
| `vsm_VS_0_rm_reset` | out 1 | 활성 RM의 리셋 트리로 배선 (Stage 6 TODO) |
| `clk`/`reset`, `icap_clk`/`icap_reset` | in | **ICAP은 별도 클럭 도메인 — IP가 자체 CDC를 포함**(CDC_STAGES 파라미터), 그냥 100MHz를 `icap_clk`에 넣으면 됨 |
| `icap_o`/`icap_i`/`icap_csib`/`icap_rdwrb` | — | ICAPE3 관점 이름(주의: IP의 `icap_o`가 ICAPE3의 `I`로 들어감) + `icap_avail`/`icap_prdone`/`icap_prerror` |
| `m_axi_mem_*` | AR/R only | DDR에서 bitstream을 읽어오는 전용 read-only 마스터 |
| `s_axi_reg_*` | AXI4-Lite | SW 트리거/상태 레지스터 접근 — **PS가 재구성 경로에서 유일하게 관여하는 지점**(그나마도 관측/수동 트리거용) |

**Stage 6 체크리스트(원본 레포가 이미 정리해 둔 것, 순서 그대로):**

1. `gen_dfx_controller.tcl`(원본 레포 `scripts/dfx/`)로 IP 생성 — GUI/BD에서 per-RM `SHUTDOWN_REQUIRED=hw`, RESET 설정, DDR bitstream ADDRESS/SIZE table을 추가 설정해야 함(dotted-path Tcl API로는 RM-level 키가 안 먹힘, 알려진 한계).
2. RP 경계에 **DFX Decoupler** IP 추가, IP의 decouple 출력으로 구동.
3. 재합성한 `dfxisp_accel`(또는 이 프로젝트에서는 `NormalISP`/`LowlightISP` 각각)의 `hyst_flags`/`ap_vld` → `checker_hysteresis` → adapter → IP HW 트리거로 배선. 활성 RM의 진짜 `ap_idle`을 adapter에 연결(지금까지는 테스트벤치가 임의로 만든 신호였다는 점을 `docs/checker.md`가 이미 지적한 그 자리). `vsm_VS_0_rm_reset`을 RM 리셋 트리로.
4. 스왑 직후 `ap_start`를 누가 다시 걸지(static 로직 vs PS) — **아직 미결정**, 이 프로젝트에서 직접 결정해야 하는 항목.
5. PS는 관측만(`selected_mode`, IP 상태 레지스터를 AXI4-Lite로).
6. (선택, 있어도 없어도 스왑 체인은 동작함) 레이턴시 계측: IP 자체엔 내장 카운터가 없으므로 `pr_latency_probe.v`를 handshake 경계에 붙여 drain/end-to-end swap을 잰다(원본 레포 contract model 기준 drain=4, swap=38 cycles — 아직 실물 IP 기준 재검증 전).

이 다섯(+선택 하나) 항목이 §2에서 검증한 RP 경계 위에 얹히는 마지막 조각이다 — 계산기 데모가 "DFX AXI Shutdown Manager + 베어메탈 트리거"로 보여준 자리에, 이 프로젝트는 "checker + checker_hysteresis.v + PG374"를 대신 앉히는 것뿐이라는 관점으로 보면 두 문서(이 문서와 계산기 데모)가 같은 골격 위에서 갈라지는 지점이 명확해진다.

### 4. checker_hysteresis.v 자체가 아직 못 다한 것 (원본 레포 기준, 2026-08-06)

`checker_hysteresis.v`는 §3 체인의 왼쪽 절반(checker → 트리거 요청)을 담당하는 static-region 모듈로, 이미 xsim으로 검증됐지만 다음은 여전히 미해결이다:

1. 재합성된 HLS 코어의 실제 `hyst_flags[1:0]` + `hyst_flags_ap_vld` RTL 포트를 이 블록에 배선(포트 자체는 `ap_vld` 프라그마 덕에 이미 존재 — 배선만 남음).
2. `drain_ready`를 활성 RM의 **진짜** `ap_idle`로 교체(지금은 테스트벤치가 모델링한 신호).
3. BRAM 비트스트림 소스를 SD/DDR로 교체하고 ICAPE3/STARTUPE3 인스턴스화(§3의 PG374 도입으로 이 항목 자체는 우회됨 — IP가 ICAP을 대신 구동).
4. `pr_controller` 관련 옛 상수(`NWORDS=171,633`)는 구 floorplan 비트스트림 기준값이라 새 pblock(1,447,424B ≈ 361,856 words)에 맞게 갱신 필요 — **다만 PG374를 쓰면 이 FSM 자체가 archive로 빠지므로 이 항목도 §3 도입 이후엔 무의미해진다.**
5. RM이 2개면 컨트롤러가 RM별 base address/bitstream 선택을 해야 하는데, 구 `pr_controller.v`는 미리 로드된 페이로드 하나만 스트리밍했다 — PG374의 DDR bitstream table(§3 체크리스트 1번)이 이 문제를 대신 해결한다.

즉 3·4·5번은 커스텀 `pr_controller.v`를 계속 썼을 때의 문제였고, **PG374 채택(§3)으로 이미 해소됐거나 무의미해졌다** — 실제로 남은 신규 작업은 1·2번(배선)과 §3의 체크리스트뿐이다.

## 더 깊은 배경이 필요하면

원본 레포의 `isppipeline/hls/checker/checker_hysteresis.md`(히스테리시스 상태기계, dwell, request/ack 프로토콜), `dfxc_adapter.md`(AMD DFX Controller IP 연동 체크리스트), `results/checker-*-2026-07-*.md`(임계값 재보정 근거)를 참고. Verilog 소스(`checker_hysteresis.v`, `dfxc_trigger_adapter.v`)도 지금은 이 폴더에 없고 원본에 있다.
