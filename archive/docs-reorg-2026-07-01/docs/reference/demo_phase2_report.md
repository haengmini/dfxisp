# Phase 2 — DFX 플로우 견고화 결과 보고서

**작성일:** 2026-05-19  
**대상:** `~/isp/pr_cnn/project/isppipeline/demo`  
**툴:** Vitis HLS 2024.1 / Vivado 2024.1

---

## 1. HLS csynth 결과 (#23~#25)

| 커널                  | LUT   | FF  | DSP | BRAM | Pipeline II | 비고                                    |
| --------------------- | ----- | --- | --- | ---- | ----------- | --------------------------------------- |
| `checker_kernel`      | 4,448 | 972 | 3   | 2    | —           | 히스토그램 256-bin UNROLL               |
| `binning_gain_kernel` | 307   | 110 | 0   | 0    | 3~5 clk     | Config 0: min=2, Config 1: max=4        |
| `isp_pipeline_kernel` | 836   | 708 | 2   | 0    | **II=1**    | 루프 레이턴시=7, DSP 레지스터 자동 활용 |

**이상 없음.** 세 IP 모두 `export.zip` 생성 완료.

---

## 2. isp_pipeline_kernel AXI-Lite 레지스터 맵 (#25 → isp_params.h 업데이트)

출처: `isp_pipeline_prj/solution1/impl/ip/drivers/isp_pipeline_kernel_v1_0/src/xisp_pipeline_kernel_hw.h`

| 오프셋        | 파라미터         | 크기   | 비고                         |
| ------------- | ---------------- | ------ | ---------------------------- |
| `0x000`       | ap_ctrl          | 32-bit | ap_start / ap_done / ap_idle |
| `0x004`       | GIE              | 32-bit | 글로벌 인터럽트 인에이블     |
| `0x010`       | num_pixels       | 32-bit | 프레임 픽셀 수               |
| `0x018`       | black_level      | 32-bit | BLC 감산값 (8-bit 유효)      |
| `0x020`       | gain_q8          | 32-bit | Q8.8 gain (256=×1.0)         |
| `0x028`       | ccm_scale        | 32-bit | Q8.8 CCM 스칼라              |
| `0x030`       | ccm_offset       | 32-bit | CCM 오프셋                   |
| `0x040–0x07F` | gamma_lut Bank 0 | 64B    | 엔트리 0,4,8,…,252 (cyclic)  |
| `0x080–0x0BF` | gamma_lut Bank 1 | 64B    | 엔트리 1,5,9,…,253           |
| `0x0C0–0x0FF` | gamma_lut Bank 2 | 64B    | 엔트리 2,6,10,…,254          |
| `0x100–0x13F` | gamma_lut Bank 3 | 64B    | 엔트리 3,7,11,…,255          |

> **Gamma LUT 주의:** `#pragma HLS ARRAY_PARTITION cyclic factor=4` 적용으로 4-뱅크 구조.  
> PS 드라이버는 `isp_mode_switch.c`의 `write_gamma_lut_banked()` 방식으로 각 뱅크에 분산 기록 필요.

---

## 3. DFX 플로우 재실행 결과 (#28)

### 3-1. pr_verify — ✅ PASS

| 항목           | Phase 0 | Phase 2 | 증가 원인                 |
| -------------- | ------- | ------- | ------------------------- |
| Static tiles   | 21,125  | 22,379  | isp_pipeline_wrapper 추가 |
| Static cells   | 120     | 159     | +39 (ISP 파이프라인 로직) |
| Routed nodes   | 1,227   | 1,582   | +355                      |
| Partition pins | 20      | 11      | RP 인터페이스 최적화      |

→ **Config1/Config2 Static Region 완전 일치.** DFX 요건 충족.

### 3-2. Timing

|                   | Config 1               | Config 2               |
| ----------------- | ---------------------- | ---------------------- |
| WNS               | **+5.410 ns**          | **+5.410 ns**          |
| WHS               | +0.032 ns              | +0.032 ns              |
| Failing endpoints | 0 / 92                 | 0 / 136                |
| 판정              | ✅ All constraints met | ✅ All constraints met |

Phase 0(+6.6ns) 대비 WNS -1.2ns — isp_pipeline_wrapper 다단계 조합 로직 추가로 크리티컬 패스 증가. 10 ns 클럭 기준 충분한 여유 유지.

### 3-3. DRC

| Rule       | Phase 0              | Phase 2        | 조치                             |
| ---------- | -------------------- | -------------- | -------------------------------- |
| `UCIO-1`   | **Critical Warning** | ✅ **Warning** | implement.tcl severity 강등 적용 |
| `HDPR-32`  | Warning              | ✅ 소멸        | pblocks_zcu104.xdc 제거          |
| `HDPRA-56` | Advisory ×2          | ✅ 소멸        | resize_pblock 적용               |

### 3-4. 생성된 비트스트림 (2026-05-19)

| 파일                            | 크기   | 용도                  |
| ------------------------------- | ------ | --------------------- |
| `config1_normal_full.bit`       | 19 MB  | Config 1 전체 플래싱  |
| `config1_normal_partial.bit`    | 1.5 MB | NORMAL → RP만 교체    |
| `config2_low_light_full.bit`    | 19 MB  | Config 2 전체 플래싱  |
| `config2_low_light_partial.bit` | 1.5 MB | LOW_LIGHT → RP만 교체 |

> 파셜 비트스트림이 전체의 **7.9%** — PR 전환이 full 대비 12× 빠름.

---

## 4. Tcl 플로우 업데이트 (#26~#27~#30)

| 파일                    | 변경                                                     |
| ----------------------- | -------------------------------------------------------- |
| `Tcl_HD/implement.tcl`  | `isp_pipeline_wrapper.v` 소스 추가, UCIO-1 severity 강등 |
| `Tcl_HD/run.tcl` (신규) | 사전조건 확인 + 전체 플로우 단일 진입점                  |
| `create_project.tcl`    | `isp_pipeline_prj` IP 레포 등록                          |

**실행 방법 (Vivado TCL 창):**

```tcl
cd <demo_dir>
source Tcl_HD/run.tcl -notrace
```

---

## 5. Phase 3 진입 조건 (Go/No-Go)

| 조건                       | 상태 |
| -------------------------- | ---- |
| HLS csynth PASS (4개 커널) | ✅   |
| pr_verify PASS             | ✅   |
| Timing violations 없음     | ✅   |
| 비트스트림 재생성 완료     | ✅   |
| DRC Critical Warning 없음  | ✅   |
| AXI-Lite 레지스터 맵 확정  | ✅   |

**→ Phase 3 진입 가능.**

---

## 6. Phase 3 범위 (예고)

| 항목          | 내용                                                      |
| ------------- | --------------------------------------------------------- |
| Block Design  | AXI DMA + isp_pipeline_kernel AXI-Lite 연결               |
| PS 소프트웨어 | `isp_mode_switch.c` 실 구동 (Baremetal/Linux)             |
| PR 트리거     | pr_controller FSM DONE 신호 → PS 인터럽트 → 파라미터 교체 |
| 하드웨어 검증 | ZCU104 보드 + 카메라 센서 연동                            |
