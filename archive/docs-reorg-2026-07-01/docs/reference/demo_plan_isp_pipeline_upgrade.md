# ISP 파이프라인 업그레이드 구현 계획

**작성일:** 2026-05-19  
**Scope:** binning 1x1/2x2 + 전체 ISP 파이프라인 재구성

---

## 0. 현황 파악

### 현재 데이터 경로

```text
PS DDR → DMA MM2S [8-bit Bayer]
  → top.v pixel_in [7:0]
    → checker_wrapper  (조도 감지 → mode 0/1 → PR trigger)
    → rp_wrapper       (RP: 1x1 pass-through or 2x2 binning+gain)
  → isp_pipeline_wrapper [8-bit Bayer/gray]
    → BLC → Gain → [Demosaic placeholder] → CCM → Gamma
  → top.v pixel_out [7:0]
  → DMA S2MM [8-bit]
→ PS DDR
```

### 현재 구현 상태

| 항목                      | 현재 상태                    | 문제                     |
| ------------------------- | ---------------------------- | ------------------------ |
| `binning_gain.cpp` mode 0 | 픽셀 1개 read/write          | **프레임 루프 없음**     |
| `binning_gain.cpp` mode 1 | 픽셀 4개 read, 1개 write     | **프레임 루프 없음**     |
| `isp_pipeline_kernel.cpp` | `for(i < num_pixels)` 루프 O | Demosaic placeholder     |
| `rp_wrapper_normal.v`     | 1x1 pass-through RTL         | 정상                     |
| `rp_wrapper_lowlight.v`   | 2x2 binning+×1.5 gain RTL    | 정상                     |
| DMA AXIS width            | 8-bit                        | 16-bit 출력 시 변경 필요 |

---

## 1. 핵심 아키텍처 결정 (변경 후)

### 데이터 경로 (목표)

```text
PS DDR → DMA MM2S [8-bit Bayer]
  → RP binning_gain:
      mode 0 (1x1): 원본 그대로 pass-through  (출력 W×H 픽셀)
      mode 1 (2x2): 4→1 평균+gain              (출력 W×H 픽셀, 해상도 개념은 RP에서)
  → isp_pipeline_kernel [8-bit in → 16-bit out]:
      BLC → Demosaic(Y-only) → AWB → CCM → Quant → Gamma → YUV
  → DMA S2MM [16-bit YUYV]
→ PS DDR
```

### 출력 포맷: **YUYV 16-bit (YUV 4:2:2)**

- 짝수 픽셀: `{Cb[7:0], Y0[7:0]}` (16-bit word)
- 홀수 픽셀: `{Cr[7:0], Y1[7:0]}` (16-bit word)
- → 메모리 레이아웃: `Y0 Cb Y1 Cr Y2 Cb Y3 Cr ...` (표준 YUYV)

> **Demosaic 전략**: Bayer 입력 → 단채널 luminance(Y)만 추출.  
> 진짜 RGB Demosaic은 2D 라인 버퍼가 필요하므로 Phase 4 데모 범위 밖.  
> YUV 출력 시 U=128, V=128 (중성 색상) → 그레이스케일 YUV.

---

## 2. 파일별 변경 내역

### A. `partial_bitstream_demo/binning_gain.hpp`

```text
변경 전: num_pixels 파라미터 없음
변경 후:
  - pixel_axis_t: ap_axiu<8,1,1,1>  (입출력 8-bit 유지)
  - 함수 시그니처:
    void binning_gain_kernel(
        hls::stream<pixel_axis_t>& src,
        hls::stream<pixel_axis_t>& dst,
        int mode,
        int num_pixels   // ← 추가: 전체 픽셀 수 (W×H)
    )
```

### B. `partial_bitstream_demo/binning_gain.cpp`

```text
변경 전: mode별 단일 read (1개 또는 4개)
변경 후: 프레임 전체 루프 추가

Mode 0 (1x1 pass-through):
  for (int i = 0; i < num_pixels; i++) {
  #pragma HLS PIPELINE II=1
      src.read() → dst.write()  // data + last 그대로 전달
  }

Mode 1 (2x2 binning):
  for (int i = 0; i < num_pixels; i += 4) {
  #pragma HLS PIPELINE II=4
      4픽셀 read → sum → gained=(sum*3)>>3 → clamp 255 → write
      last: i+4 >= num_pixels 일 때 set
  }

인터페이스 pragma:
  #pragma HLS INTERFACE axis      port=src
  #pragma HLS INTERFACE axis      port=dst
  #pragma HLS INTERFACE s_axilite port=mode        bundle=control
  #pragma HLS INTERFACE s_axilite port=num_pixels  bundle=control
  #pragma HLS INTERFACE s_axilite port=return      bundle=control
```

> 주의: 2x2 모드에서 num_pixels는 4의 배수여야 함. RP 출력 픽셀 수 = num_pixels/4.

### C. `isp_pipeline/isp_pipeline_kernel.hpp`

```text
변경 전: 단일 pixel_axis_t = ap_axiu<8,1,1,1>
변경 후:
  typedef ap_axiu<8,1,1,1>   src_axis_t;   // 입력 유지
  typedef ap_axiu<16,1,1,1>  dst_axis_t;   // ← 출력 16-bit로 변경

  파라미터 추가:
    ap_uint<16> awb_r_gain;   // AWB Red gain (Q8.8, 256=×1.0)
    ap_uint<16> awb_g_gain;   // AWB Green gain
    ap_uint<16> awb_b_gain;   // AWB Blue gain

  기존 파라미터 유지:
    int num_pixels, black_level, gain_q8, ccm_scale, ccm_offset, gamma_lut[256]

  함수 시그니처:
    void isp_pipeline_kernel(
        hls::stream<src_axis_t>& src_stream,
        hls::stream<dst_axis_t>& dst_stream,
        int         num_pixels,
        ap_uint<8>  black_level,
        ap_uint<16> gain_q8,       // Bayer pre-gain (기존 유지)
        ap_uint<16> awb_r_gain,    // AWB (신규)
        ap_uint<16> awb_g_gain,
        ap_uint<16> awb_b_gain,
        ap_int<16>  ccm_scale,
        ap_int<16>  ccm_offset,
        ap_uint<8>  gamma_lut[256]
    )
```

### D. `isp_pipeline/isp_pipeline_kernel.cpp`

```text
파이프라인 단계 (픽셀 단위 처리):

for (int i = 0; i < num_pixels; i++) {
#pragma HLS PIPELINE II=1

    src_axis_t p_in = src_stream.read();
    ap_uint<8> bayer = p_in.data;

    // Stage 1: BLC
    ap_int<16> p_blc = (ap_int<16>)bayer - black_level;
    if (p_blc < 0) p_blc = 0;
    ap_uint<8> p_b = (p_blc > 255) ? 255 : (ap_uint<8>)p_blc;

    // Stage 2: Pre-gain (기존 gain_q8)
    ap_uint<24> p_g_full = (ap_uint<24>)p_b * gain_q8;
    ap_uint<8>  p_g = (p_g_full >> 8 > 255) ? 255 : (ap_uint<8>)(p_g_full >> 8);

    // Stage 3: Demosaic (Y-only: R=G=B=Y)
    ap_uint<8> R = p_g, G = p_g, B = p_g;

    // Stage 4: AWB
    ap_uint<24> Rf = (ap_uint<24>)R * awb_r_gain;
    ap_uint<24> Gf = (ap_uint<24>)G * awb_g_gain;
    ap_uint<24> Bf = (ap_uint<24>)B * awb_b_gain;
    ap_uint<8> Ra = clamp8(Rf >> 8);
    ap_uint<8> Ga = clamp8(Gf >> 8);
    ap_uint<8> Ba = clamp8(Bf >> 8);

    // Stage 5: CCM (간소화: 동일 scale+offset 3채널 공통 적용)
    ap_uint<8> Rc = ccm_apply(Ra, ccm_scale, ccm_offset);
    ap_uint<8> Gc = ccm_apply(Ga, ccm_scale, ccm_offset);
    ap_uint<8> Bc = ccm_apply(Ba, ccm_scale, ccm_offset);

    // Stage 6: Quantization (이미 clamp8 적용 중)

    // Stage 7: Gamma LUT (Y 채널에 적용)
    ap_uint<8> Y_val = (ap_uint<8>)((Rc*66 + Gc*129 + Bc*25 + 128) >> 8) + 16;
    ap_uint<8> Y_g   = gamma_lut[Y_val];

    // Stage 8: YUV + YUYV 패킹
    ap_uint<8> Cb = (ap_uint<8>)((-(ap_int<16>)Rc*38 - (ap_int<16>)Gc*74
                                   + (ap_int<16>)Bc*112 + 128) >> 8) + 128;
    ap_uint<8> Cr = (ap_uint<8>)(((ap_int<16>)Rc*112 - (ap_int<16>)Gc*94
                                   - (ap_int<16>)Bc*18 + 128) >> 8) + 128;

    dst_axis_t p_out;
    p_out.keep = 0x3; p_out.strb = 0x3; p_out.user = 0;
    p_out.last = p_in.last;
    if (i % 2 == 0)
        p_out.data = (ap_uint<16>)(Cb, Y_g);   // {Cb[7:0], Y0[7:0]}
    else
        p_out.data = (ap_uint<16>)(Cr, Y_g);   // {Cr[7:0], Y1[7:0]}
    dst_stream.write(p_out);
}
```

> Gamma는 Y 채널에만 적용 (간소화). 필요시 R/G/B 별도 LUT 3개로 확장 가능.

### E. `isp_pipeline/isp_pipeline_tb.cpp`

```text
변경사항:
  - run_pipeline() 반환형: ap_uint<8> → ap_uint<16>
  - 새 파라미터(awb_r/g/b_gain) 추가
  - YUYV 포맷 검증 TC 추가:
      TC_YUYV: 같은 그레이 픽셀 → Y0≈Y1, Cb≈128, Cr≈128
      TC_BRIGHT: 흰색(255) → Y≈235 (BT.601 상한)
      TC_DARK: 검정(0) → Y=16 (BT.601 하한)
  - 기존 BLC/Gain/CCM/Gamma TC는 Y채널로 검증

모든 기존 TC 유지 (TC1~TC9), 기대값만 16-bit YUYV로 업데이트
```

### F. `hdl/static/top.v`

```text
변경:
  output wire [7:0]  pixel_out        →  output wire [15:0] pixel_out
  wire        [7:0]  isp_data_out     →  wire        [15:0] isp_data_out

isp_pipeline_wrapper 포트:
  .data_out(isp_data_out)   // 16-bit으로 변경됨
```

### G. `hdl/static/isp_pipeline_wrapper.v`

```text
변경:
  output reg [7:0]  data_out  →  output reg [15:0] data_out
  내부 파이프라인 Stage 7~8에 YUV 변환 로직 추가
  (RTL 시뮬레이션용 - HLS 합성 IP와 동일 결과 검증)

  parity 레지스터(1-bit)로 짝수/홀수 픽셀 판단 → Cb or Cr 선택
```

### H. `hdl/static/top_bd_wrapper.v`

```text
변경:
  wire [7:0]  bd_pixel_in_tdata  →  wire [15:0] bd_pixel_in_tdata
  wire [7:0]  pixel_out          →  wire [15:0] pixel_out

  assign bd_pixel_in_tdata = pixel_out;  // 폭 자동 반영
  .PIXEL_IN_AXIS_tdata(bd_pixel_in_tdata)  // 16-bit 연결
```

### I. `create_bd.tcl`

```text
변경:
  CONFIG.c_s_axis_s2mm_tdata_width {8}   →  {16}

PIXEL_IN_AXIS 외부 포트 폭도 8→16으로 업데이트 필요
(Vivado가 create_bd 실행 시 자동 반영)
```

### J. PS 드라이버 (`ps_driver/`)

```text
최소 변경:
  address_map.h: 변경 없음
  isp_params.h:  awb_r_gain, awb_g_gain, awb_b_gain 파라미터 추가
  isp_mode_switch.c: write_awb_gains() 함수 추가

DMA 전송 크기: 2배 (픽셀당 2 bytes → PS가 DMA 설정 시 length 업데이트)
```

---

## 3. 실행 순서 (Dependency 기준)

```text
Phase A (병렬 가능):
  A1. binning_gain.cpp 프레임 루프 추가 + TB 업데이트   → C-Sim
  A2. isp_pipeline_kernel.cpp 전면 재작성 + TB 재작성  → C-Sim

Phase B (A2 완료 후):
  B1. C-Sim 검증 (두 커널 모두 PASS 확인)

Phase C (B1 완료 후):
  C1. top.v pixel_out 폭 변경
  C2. isp_pipeline_wrapper.v YUV 출력 변경
  C3. top_bd_wrapper.v 16-bit 연결
  C4. create_bd.tcl DMA S2MM 폭 변경

Phase D (C1~C4 완료 후):
  D1. RTL 시뮬레이션 재검증 (tb_top.v)
  D2. Vivado DFX 재빌드 source Tcl_HD/run.tcl
       → 새 full bitstream + partial bitstreams
```

---

## 4. 리스크 및 대응

| 리스크                                               | 영향도 | 대응                                                    |
| ---------------------------------------------------- | ------ | ------------------------------------------------------- |
| 16-bit 출력 → DFX 재빌드 필요                        | HIGH   | Phase C~D는 C-Sim 완료 후 진행. 재빌드 ~2시간           |
| 2x2 binning이 1D 스트림 처리 → 실제 Bayer 패턴 왜곡  | MEDIUM | 데모 용도로는 허용. 추후 라인 버퍼 도입 시 개선         |
| DMA 전송 크기 2배 → PS 드라이버 DMA length 설정 수정 | LOW    | isp_mode_switch.c에서 num_bytes = num_pixels × 2로 변경 |
| RTL tb_top.v 기대값 변경                             | MEDIUM | isp_pipeline_wrapper.v YUV 출력 후 시뮬 기대값 업데이트 |

---

## 5. 완료 기준 (각 태스크)

| 태스크                 | 완료 기준                                                                     |
| ---------------------- | ----------------------------------------------------------------------------- |
| #3 binning_gain        | `vitis_hls -f csim_binning_gain.tcl` → 0 fail                                 |
| #2 isp_pipeline_kernel | `vitis_hls -f csim_isp_pipeline.tcl` → 0 fail                                 |
| #4 RTL/BD              | `vivado -mode batch -source Tcl_HD/run.tcl` → 오류 없음 또는 tb_top 시뮬 통과 |
| #5 TB 전체             | C-Sim + RTL 시뮬 모두 PASS                                                    |
