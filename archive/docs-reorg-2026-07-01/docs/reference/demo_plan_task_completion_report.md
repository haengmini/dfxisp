# ISP 파이프라인 업그레이드 완료 보고서

**작성일:** 2026-05-19  
**기준 커밋:** session-ses_1c0c 이어받기 (Phase 4 연속)

---

## 완료된 태스크 요약

| #   | 태스크                                             | 상태 | 검증 방법                             |
| --- | -------------------------------------------------- | ---- | ------------------------------------- |
| #1  | 전체 파이프라인 구현 계획 수립 (Binning 제약 포함) | ✅   | `.plans/isp_pipeline_upgrade.md` 저장 |
| #2  | `isp_pipeline_kernel` HLS 커널 전면 재작성         | ✅   | C-Sim 13/13 PASS                      |
| #3  | `binning_gain` RP 모듈 1x1/2x2 프레임 루프 구현    | ✅   | C-Sim 10/10 PASS                      |
| #4  | RTL 및 Block Design 16-bit 데이터 경로 업데이트    | ✅   | 코드 검증                             |
| #5  | Testbench 업데이트 및 시뮬레이션 검증              | ✅   | RTL Sim PASS                          |

---

## Task #1: 구현 계획

**핵심 결정사항:**

- 출력 포맷: **16-bit YUYV** (BT.601 YCbCr 4:2:2)
- Demosaic: Y-only 방식 (R=G=B=luminance) — 2D 라인버퍼 없이 구현 가능
- Vitis Vision 미사용 → 커스텀 HLS로 전체 구현

---

## Task #2: isp_pipeline_kernel 재작성

### 변경 파일

- `isp_pipeline/isp_pipeline_kernel.hpp`
- `isp_pipeline/isp_pipeline_kernel.cpp`
- `isp_pipeline/isp_pipeline_tb.cpp`

### 파이프라인 단계

```text
Bayer 8-bit 입력
  → Stage 1: BLC (흑점 보정)
  → Stage 2: Pre-gain (Q8.8)
  → Stage 3: Demosaic (Y-only, R=G=B)
  → Stage 4: AWB (채널별 Q8.8 gain)
  → Stage 5: CCM (공통 scale+offset, Q8.8)
  → Stage 6: Quantization
  → Stage 7: BT.601 YCbCr + Gamma (Y채널)
  → Stage 8: YUYV 패킹
YUYV 16-bit 출력
  짝수 픽셀: {Cb[7:0], Y[7:0]}
  홀수 픽셀: {Cr[7:0], Y[7:0]}
```

### C-Sim 결과 (13/13 PASS)

| TC   | 검증 항목               | 기대값               | 결과 |
| ---- | ----------------------- | -------------------- | ---- |
| TC1  | 검정 픽셀               | Y=16 (BT.601 offset) | ✅   |
| TC2  | 흰색 픽셀               | Y=235 (BT.601 max)   | ✅   |
| TC3  | 중간회색 100            | Y=102                | ✅   |
| TC4  | 그레이스케일            | Cb=Cr=128 (중성)     | ✅   |
| TC5  | BLC 감산                | Y=30                 | ✅   |
| TC6  | BLC underflow clamp     | Y=16                 | ✅   |
| TC7  | Pre-gain ×2.0           | Y=102                | ✅   |
| TC8  | Pre-gain overflow       | Y=235                | ✅   |
| TC9  | AWB ×2.0                | Y=102                | ✅   |
| TC10 | CCM ×2.0 clamp          | Y=235                | ✅   |
| TC11 | NORMAL γ=2.2 전체       | Y=143                | ✅   |
| TC12 | LOW_LIGHT > NORMAL 밝기 | Y: 126 vs 173        | ✅   |
| TC13 | YUYV 페어 Y0=Y1         | Y0=Y1=102            | ✅   |

---

## Task #3: binning_gain RP 모듈

### 변경 파일

- `partial_bitstream_demo/binning_gain.hpp`
- `partial_bitstream_demo/binning_gain.cpp`
- `partial_bitstream_demo/binning_gain_tb.cpp`

### 변경 사항

- `num_pixels` 파라미터 추가
- Mode 0 (1x1): `for(i < num_pixels)` 프레임 루프
- Mode 1 (2x2): `for(i < num_pixels; i+=4)` II=4 파이프라인

### C-Sim 결과 (10/10 PASS)

| TC      | 검증 항목                            | 결과 |
| ------- | ------------------------------------ | ---- |
| TC1~TC4 | 1x1 pass-through (단일/4px/경계/8px) | ✅   |
| TC5     | 2x2: [10,20,30,40]→37                | ✅   |
| TC6     | 2x2: [40×4]→60                       | ✅   |
| TC7     | 2x2: 포화 clipping 255×4→255         | ✅   |
| TC8     | 2x2: 영 입력 0×4→0                   | ✅   |
| TC9     | 2x2: 8px 프레임 → [37, 60]           | ✅   |
| TC10    | 2x2: 16px 프레임 → 4 bins 모두 90    | ✅   |

---

## Task #4: RTL 및 Block Design 업데이트

### 변경 파일

| 파일                                | 변경 내용                                                     |
| ----------------------------------- | ------------------------------------------------------------- |
| `hdl/static/top.v`                  | `pixel_out = rp_data_out` (RP 출력→BD); `isp_data_out [15:0]` |
| `hdl/static/isp_pipeline_wrapper.v` | `data_out [15:0]` (16-bit YUYV); BT.601+Gamma 추가            |
| `create_bd.tcl`                     | `c_s_axis_s2mm_tdata_width {8}` → `{16}`                      |
| `hdl/static/top_bd_wrapper.v`       | 변경 없음 (pixel_out [7:0] 유지)                              |

### 확정 HW 아키텍처

```text
DMA MM2S [8-bit Bayer]
  → top.v RP (rp_wrapper: 1x1 or 2x2 binning)
  → pixel_out [7:0] → PIXEL_IN_AXIS → isp_pipeline_kernel HLS IP
  → dst_stream [16-bit YUYV] → DMA S2MM [16-bit]
  → PS DDR

RTL Sim 경로 (top_sim.v):
  → isp_pipeline_wrapper [15:0] → pixel_out[7:0] (Y 채널)
```

---

## Task #5: Testbench 업데이트 및 시뮬레이션 검증

### 변경 파일

| 파일                                | 변경 내용                                                        |
| ----------------------------------- | ---------------------------------------------------------------- |
| `hdl/static/isp_pipeline_wrapper.v` | gain 버그 수정 (`gain[7:0]` → `gain` 전체)                       |
| `hdl/sim/top_sim.v`                 | `isp_data_out [7:0]` → `[15:0]`; `pixel_out = isp_data_out[7:0]` |
| `hdl/tb/tb_top_transition.v`        | 기대값 갱신: NORMAL 167→168, LOWLIGHT 178→183                    |
| `Tcl_HD/run_sim.tcl`                | `icap_controller.v`, `isp_pipeline_wrapper.v` 추가               |
| `Tcl_HD/run_sim_transition.tcl`     | 동일 파일 추가                                                   |

### RTL 시뮬레이션 결과

**run_sim.tcl (NORMAL Config):**

```text
[PASS] 모든 검증 통과 (error=0)
  pixel_out = pixel_in (100~115, 40) — RP pass-through 확인
```

**run_sim_transition.tcl (NORMAL→LOW_LIGHT 전환):**

```text
[PASS] 전환 시뮬레이션 완료 — NORMAL→LOW_LIGHT 성공
  NORMAL   PASS : 15건  (pixel_out=168, Y=BT.601(100)=168)
  LOWLIGHT PASS : 4건   (pixel_out=183, RP:40×4→60→Y=183)
```

### 기대값 계산 근거

| 모드     | 입력       | 경로                 | BT.601 Y_in             | Gamma 출력    |
| -------- | ---------- | -------------------- | ----------------------- | ------------- |
| NORMAL   | pixel=100  | BLC=0→gain→R=G=B=100 | (220×100+128)>>8+16=102 | γ₂.₂[102]=168 |
| LOWLIGHT | pixel=40×4 | RP:160→60→R=G=B=60   | (220×60+128)>>8+16=68   | γ₄.₀[68]=183  |

---

## 남은 작업 (Phase 4 계속)

| 태스크       | 내용                                                                |
| ------------ | ------------------------------------------------------------------- |
| BD 재빌드    | `source create_bd.tcl` → `source Tcl_HD/run.tcl` (S2MM 16-bit 적용) |
| 새 Bitstream | Full + Partial bitstream 재생성 (~2시간)                            |
| #38          | ZCU104 보드 전원 투입 + Full bitstream 플래싱                       |
| #39          | PS 소프트웨어 빌드 (Vitis Baremetal) — DMA 전송 크기 ×2 수정 필요   |
| #40          | 카메라 센서 연동 + 자동 PR 전환 실증                                |

### PS 드라이버 수정 필요 사항 (#39 준비)

- `isp_mode_switch.c`: DMA length = `num_pixels * 2` (픽셀당 2 bytes)
- `isp_params.h`: `awb_r_gain`, `awb_g_gain`, `awb_b_gain` 파라미터 추가
  - NORMAL: `awb_r=256, awb_g=256, awb_b=256`
  - LOW_LIGHT: `awb_r=286, awb_g=256, awb_b=307` (색온도 보정 예시)
