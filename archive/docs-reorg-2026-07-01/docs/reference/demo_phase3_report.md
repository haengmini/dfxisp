# Phase 3 — PS-PL 통합 결과 보고서

**작성일:** 2026-05-19  
**대상:** `~/isp/pr_cnn/project/isppipeline/demo`  
**툴:** Vivado 2024.1 / Vitis HLS 2024.1

---

## 1. Block Design 구성 (#32~#34)

**스크립트:** `create_bd.tcl` (Vivado batch 실행 완료, validation PASSED)

### IP 구성

| IP                      | 인스턴스                | 역할                         |
| ----------------------- | ----------------------- | ---------------------------- |
| Zynq UltraScale+ MPSoC  | `zynq_ultra_ps_e_0`     | PS, PL 클럭(~97 MHz), DDR    |
| Proc Sys Reset          | `proc_sys_reset_0`      | 리셋 분배                    |
| AXI Smart Connect (3→1) | `axi_smc_0`             | DMA×2 + HP_READER → HP0_FPD  |
| AXI Interconnect (1→2)  | `ps8_0_axi_periph_0`    | PS HPM0_FPD → DMA, ISP 제어  |
| AXI DMA                 | `axi_dma_0`             | 픽셀 스트림 PS↔PL            |
| isp_pipeline_kernel     | `isp_pipeline_kernel_0` | HLS ISP (BLC→Gain→CCM→Gamma) |
| Concat                  | `xlconcat_0`            | DMA 인터럽트 묶음 → IRQ0     |

### AXI-Lite 주소 맵 (Vivado 자동 할당)

| IP                      | 주소        | 크기  |
| ----------------------- | ----------- | ----- |
| `axi_dma_0`             | 0xA000_0000 | 64 KB |
| `isp_pipeline_kernel_0` | 0xA001_0000 | 64 KB |

### 외부 포트 (top_bd_wrapper.v 연결용)

| 포트              | 방향   | 용도                                       |
| ----------------- | ------ | ------------------------------------------ |
| `PIXEL_OUT_AXIS`  | Master | DMA MM2S → top.v pixel_in (RP 입력)        |
| `PIXEL_IN_AXIS`   | Slave  | top.v pixel_out → isp_pipeline src_stream  |
| `S_AXI_HP_READER` | Slave  | axi_hp_reader M_AXI → HP0 (비트스트림 DDR) |

### 클럭

- `pl_clk0` = **96,968,727 Hz** (~97 MHz)  
  외부 포트 FREQ_HZ 정렬 완료 (BD 41-237 오류 해결)

---

## 2. axi_hp_reader (#36 연계)

- `axi_hp_reader.v` (RTL): `top_bd_wrapper.v`에서 인스턴스화
- `S_AXI_HP_READER` 포트를 통해 SmartConnect → HP0 → DDR 접근
- Partial bitstream DDR 위치: `ddr_layout.h` 참조 (NORMAL=0x1000_0000, LOWLIGHT=0x1020_0000)

---

## 3. Phase 3 완료 태스크 목록

| 태스크 | 내용                                        | 결과      |
| ------ | ------------------------------------------- | --------- |
| #32    | AXI DMA 인스턴스화 + HP0 연결               | ✅        |
| #33    | isp_pipeline_kernel AXI-Lite 연결           | ✅        |
| #34    | 주소 할당 및 BD validation                  | ✅ PASSED |
| #36    | DDR 저장 전략 (axi_hp_reader, ddr_layout.h) | ✅        |
| #41    | icap_controller.v RTL + TB                  | ✅        |
| #42    | pr_controller_wrapper icap_done 연결        | ✅        |
| #43    | 통합 RTL 시뮬 재검증                        | ✅        |
| #44    | isp_pipeline_wrapper Gamma LUT ROM          | ✅        |

---

## 4. PS 소프트웨어 드라이버 파일

| 파일                               | 역할                                             |
| ---------------------------------- | ------------------------------------------------ |
| `ps_driver/address_map.h`          | AXI-Lite 주소 (DMA 0xA000_0000, ISP 0xA001_0000) |
| `ps_driver/isp_params.h`           | ISP 파라미터 (Gamma γ=2.2/4.0, Gain, CCM, BLC)   |
| `ps_driver/isp_mode_switch.h/.c`   | AXI-Lite 파라미터 교체 함수                      |
| `ps_driver/ddr_layout.h`           | DDR 메모리 맵 (partial bitstream 위치)           |
| `ps_driver/pr_bitstream_init.h/.c` | 부팅 시 SD→DDR 비트스트림 로딩                   |

---

## 5. 남은 작업 (Phase 4 — 하드웨어 검증)

| 태스크     | 내용                                                   |
| ---------- | ------------------------------------------------------ |
| #37        | PS 인터럽트 루프 (DMA 완료 → 파라미터 교체)            |
| BD 통합    | `top_bd_wrapper.v` 완성 (icap*mem*\* 포트 외부 노출)   |
| DFX 재빌드 | `source Tcl_HD/run.tcl` (BD 변경 후 비트스트림 재생성) |
| #38        | ZCU104 보드 전원 투입 + Full bitstream 플래싱          |
| #39        | PS 소프트웨어 빌드 (Vitis Baremetal)                   |
| #40        | 카메라 센서 연동 + 자동 PR 전환 실증                   |
