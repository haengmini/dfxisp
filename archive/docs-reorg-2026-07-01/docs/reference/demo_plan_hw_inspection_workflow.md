# HW (HLS/RTL) 점검 Workflow — 설계 (pre-plan)

> 목적: 컬러 end-to-end 결정에 따라 ISP 커널을 **컬러 + 요구 스테이지 순서**로 재작성한 뒤,
> SW 골든 모델(`isppipeline/unprocess/isp_pipeline.py`)과 **비트정확 대조**하며 기존 DFX 플로우 전 단계를 검증.
> 작성 2026-06-02. 학습/sim 재정비 완료 후 실행. 최종 결과는 `phase4_report.md`로 문서화.
>
> **[인터페이스 확정 2026-06-04] RGB32 in / RGB32 out.**
> - 입력: 32-bit RGB `ap_axiu<32>` (`[31:24]=0x00 / [23:16]=B / [15:8]=G / [7:0]=R`), DMA MM2S `{32}`
> - 출력: 32-bit RGB `ap_axiu<32>` (동일 패킹), DMA S2MM `{32}` → **DPU 직결**(YUYV→RGB 변환 불요)
> - demosaic: 데이터셋이 이미 RGB이므로 **bypass(항등)**, 보드 Bayer 센서 연동 시에만 실동작하도록 스테이지는 구조적으로 유지
> - SW↔HW 대조는 **단일 RGB 도메인에서 직접** 수행(YUYV round-trip 제약 소멸)
> - 근거: DPU-ready, 검증 최단경로, 컬러 재학습이 활용하는 색정보 full 보존. 비용(DDR 2배)은 오프라인 sim/데모에서 무관.
> - 이 결정으로 `Research_Roadmap.md §4`(RGB32 방향)와 합치, 구 YUYV 유지안 폐기.

## 환경
- Vitis HLS 2024.1 / Vivado 2024.1 / xsim, ZCU104 `xczu7ev-ffvc1156-2-e`
- Vitis Vision 가용: `xf_demosaicing.hpp`, `xf_awb.hpp`, `xf_colorcorrectionmatrix.hpp`, `xf_gammacorrection.hpp`, `xf_quantizationdithering.hpp`, `xf_gaincontrol.hpp`
- 기존 플로우: `csim_*.tcl` / `csynth_*.tcl` / `run_*.tcl`(HLS), `Tcl_HD/run.tcl`(DFX 진입), `run_pr_verify.tcl`, `Tcl_HD/run_sim*.tcl`(RTL)

## 요구 스테이지 (golden)
`PR[Binning,Gain] → BLC → Demosaic(bypass) → AWB → CCM → Quantization → Gamma(normal/LL, RGB) → RGB32 출력`
(YUV 변환·YUYV 패킹 스테이지 제거)

## 현재 격차 (점검 결과)
| 단계 | 현재 | 조치 |
|------|------|------|
| Demosaic | Y-only 플레이스홀더(R=G=B) | **bypass(항등)** — RGB 입력 전제. Bayer 센서 연동 시에만 실 demosaic 활성 |
| Gamma | YUV 後 Y채널 | **RGB 3채널 LUT**로 변경 (YUV 단계 제거) |
| YUV/YUYV | BT.601 변환 + 16b 패킹 | **완전 제거** (RGB32 직출력) |
| Quantization | no-op | 명시 스테이지(`xf_quantizationdithering`, 8-bit=항등) |
| CCM | 공통 scale+offset | 3×3 행렬 옵션화(Q8.8) |
| pre-gain | 사양밖 | 유지/정리 판단 |
| 인터페이스 | 8b Bayer in / 16b YUYV out | **`ap_axiu<8>`→`ap_axiu<32>` (in/out), DMA MM2S/S2MM `{32}`, `int width` 파라미터 추가** |

---

## Phase A — 골든 계약 동기화 (SW↔HW)
- **A1 ✅(2026-06-04 완료)**: `isp_pipeline.py`에 `process_to_rgb32()` + `pack_rgb32()`/`unpack_rgb32()` 추가. **RGB32 직출력**이라 round-trip 없이 RGB 도메인 직접 대조. `process(..., yuv_roundtrip=False)`와 동일 스테이지 시퀀스 재사용 → CNN 이미지 ↔ HW 골든 자동 정합. `process_to_yuyv()`는 레거시로 강등. self-test(`python isp_pipeline.py`) ALL PASS: pack↔unpack 무손실, [31:24]=0x00 패딩, 배치 `00|B|G|R`, 골든==CNN(normal/lowlight).
- **A2 ✅(2026-06-04 완료)**: `sim_dataset/gen_golden_rgb32.py` 신규 — 정준 `process_to_rgb32()` 호출. bright=COCO/dark=ExDark 자동 선별(dark_ratio 0.0/1.0), 중앙 16×16 패치. 산출 `sim_dataset/golden/`: `input_{bright,dark}_rgb.hex`, `expected_normal_rgb.hex`(256px), `expected_lowlight_rgb.hex`(64px=binning), `stage_trace.csv`, `golden_vector_log.csv`, `golden_report.md`. **ALL PASS**: 픽셀수 일치 + trace==process_to_rgb32. 컬러 보존(AWB 채널게인)·lowlight shadow lift(입력~27→출력~156) 확인.
- **PASS**: ✅ SW 스테이지별 수치(stage_trace.csv)가 Q8.8/Gamma LUT 기대값과 일치.

> **Phase A 완료** — 다음은 Phase C(컬러 커널 재작성) 후 B1(C-Sim에서 이 골든 hex와 memcmp).

## Phase B — HLS C-Sim (단위 기능)
- **B0(회귀)**: 현 grayscale 커널 `csim_isp_pipeline.tcl` → 기존 TC1~5 PASS 재확인(변경 전 baseline).
- **B1 ✅(isp_pipeline)**: 컬러 커널 재작성 후 — TB를 골든 벡터 **벡터 기반 비트대조**로 교체(구 13 TC YUYV 하드코딩 폐기). `isp_pipeline_tb.cpp`가 `load_hex()`로 입력/기대/LUT 로드 → 픽셀 비교. **NORMAL 256 / LOWLIGHT 64 mismatch=0**. (binning_gain/checker TB 벡터화는 해당 커널 RGB32화와 함께 진행 예정.)
- **PASS**: ✅ isp_pipeline 전 픽셀 HW==golden(RGB32), mismatch=0.

## Phase C — 컬러 커널 재작성 (수정 본체)
- **C1 Demosaic ✅**: **bypass(항등)** — 입력이 이미 RGB32. unpack `{B,G,R}`만 수행. (보드 Bayer 센서 연동은 별도 옵션 플래그로 추후; 이때만 RGGB bilinear/`xf_demosaicing`)
- **C2 순서 ✅**: unpack RGB → BLC → (demosaic bypass) → AWB → CCM(공통 scale+offset; 3×3 향후 옵션) → quant → **Gamma(RGB 3채널 동일 LUT)** → pack RGB32. **YUV/YUYV 단계 삭제.**
- **C3 I/F ✅**: `src_axis<8>`→**`ap_axiu<32>`**(RGB in) + `int width` 추가; `dst_axis<16>`→**`ap_axiu<32>`**(RGB out). `isp_pipeline_kernel.hpp` 갱신. gamma_lut `ARRAY_PARTITION complete`(3 read/cycle, II=1).
- **C4 래퍼 ⬜**: `hdl/static/isp_pipeline_wrapper.v` (32-bit 포트, Gamma ROM 3채널화, YCbCr 로직 제거), `top.v` 포트 정합, `create_bd.tcl` DMA MM2S/S2MM `{32}`. (RTL sim 전용 — Phase F에서 검증)
- 산출: ✅ 갱신된 `isp_pipeline/isp_pipeline_kernel.cpp/.hpp/tb.cpp`.

> **C(커널 본체) + B1(C-Sim) 완료 (2026-06-04)** — `/tools/Xilinx/Vitis_HLS/2024.1/include` 호스트 컴파일(=csim 등가)로 **3개 데이터패스 커널 전부 골든 비트대조 PASS**:
> - **isp_pipeline_kernel**: NORMAL 256px / LOWLIGHT(binned) 64px, mismatch=0, max_ch_err=0
> - **binning_gain_kernel**: `ap_axiu<8>`→`<32>`, **진짜 2D 2×2 binning**(라인버퍼+width, 골든 `apply_binning_2x2` 일치) mode1 64px + mode0 pass 256px, mismatch=0
> - **checker_kernel**: `ap_axiu<32>` 입력, `Y=(R+2G+B)>>2`, bright→NORMAL/dark→LOW_LIGHT 4/4 PASS
> - **pr_controller**: 제어 FSM이라 픽셀폭 무관 → 변경 불요.
> **남은 Phase C/주변**: C4 Verilog 래퍼(`isp_pipeline_wrapper.v` 등 RTL, Phase F에서 검증), `binning_gain.hpp`·`checker.hpp`에 `width` 추가로 BD/`create_bd.tcl` axilite 정합 필요.

## Phase D — HLS C-Synth (합성성/타이밍/리소스)
- `csynth_isp_pipeline.tcl` (+ 전 커널). **II 확인**(demosaic 라인버퍼로 II>1 가능 → 데이터플로우/파이프라인 조정), 목표 클럭(~97MHz pl_clk0) WNS>0, BRAM/DSP/LUT 예산(ZCU104) 내. `export.zip` 재생성.
- **PASS**: II=1(또는 허용치), WNS>0, 리소스 예산 내, export 생성.

## Phase E — Co-Sim (RTL=C 등가)
- HLS cosim(골든 벡터 입력). RTL 시뮬 출력 == C-sim 출력.
- **PASS**: cosim mismatch=0.

## Phase F — RTL 통합 시뮬
- `Tcl_HD/run_sim.tcl`(NORMAL/LOWLIGHT) + `run_sim_transition.tcl`(전환). TB: `hdl/tb/tb_top{,_transition,_reverse,_dataset}.v`.
- 경로: `checker → pr_controller_wrapper → icap_controller → isp_pipeline_wrapper`, **32-bit RGB 출력** 확인. `tb_top_dataset.v`로 실 데이터 패치.
- **PASS**: error=0(NORMAL/LOWLIGHT), 전환 양방향 PASS, RGB32 정상.

## Phase G — PR Verify (정적 영역 일관성)
- `run_pr_verify.tcl`. Config1(normal) vs Config2(lowlight) static tiles/cells 일치.
- **PASS**: static tiles/partition pins 일치(기존 22,379 tiles 기준 대비).

## Phase H — Implementation / Timing / DRC
- `Tcl_HD/run.tcl` → `implement.tcl` (Synth→P&R Config1/2→PR Verify→Bitstream). 컬러 로직 추가로 WNS 여유 감소 예상 → 모니터.
- **PASS**: WNS>0, DRC Critical 0.

## Phase I — Bitstream
- full + partial(.bit) 생성, **파셜 크기/비율** 확인(기존 ~1.48MB). DDR 레이아웃(`ddr_layout.h`) 정합.
- **PASS**: 4개 bit 생성, 파셜 비율 합리적.

## Phase J — (옵션) ICAP/DDR 경로
- `tb_icap_controller.v`(DDR_LAT 가변), `axi_hp_reader.v`. mem_valid handshake.
- **PASS**: TC1~4 PASS, 양방향 전환 PASS.

---

## 검증 매트릭스 (요약)
| Phase | 도구/스크립트 | 산출 | 핵심 PASS |
|-------|----------------|------|-----------|
| A 골든 | isp_pipeline.py, gen_hex | golden CSV/hex | 수치 검산 일치 |
| B Csim | csim_*.tcl | 로그 | HW==golden(YUYV) |
| C 재작성 | 수기 | kernel/TB | 빌드 |
| D Csynth | csynth_*.tcl | export.zip | II/WNS/리소스 |
| E Cosim | cosim | 로그 | RTL==C |
| F RTLsim | run_sim*.tcl | 파형/로그 | error=0, 전환 |
| G PRverify | run_pr_verify.tcl | 로그 | static 일치 |
| H Impl | run.tcl/implement | dcp | WNS>0,DRC0 |
| I Bit | implement | .bit×4 | 크기 합리 |
| J ICAP | tb_icap | 로그 | 양방향 |

## 리스크
1. **타이밍** — 컬러 경로(3채널 AWB/CCM/Gamma)로 WNS 여유↓. Phase H에서 조기 확인.
2. **인터페이스 변경**(8b→32b, width) → BD/`create_bd.tcl`(DMA `{32}`)/`address_map.h`/RP 파티션 핀 폭 영향. Phase F 전 정합. **RP 핀 폭 변경 → DFX 전체 재합성 필요**(D.1).
3. **DDR 대역폭 2배** — RGB32(32bpp)는 YUYV(16bpp) 대비 2배. 오프라인 sim 무관, 보드 실시간 단계에서 throughput 확인.
4. **데모 vs 진짜 ISP** — demosaic bypass라 "Bayer 복원 없는 RGB-도메인 ISP". 보드 Bayer 센서 연동 시 demosaic 활성 옵션 필요(별도 작업).
(해소됨: 구 YUYV round-trip 비트대조 리스크 — RGB 단일 도메인 직접 대조로 소멸)

## 실행 순서 한 줄
A(골든) → B0(회귀) → C(재작성) → B1(Csim 대조) → D(Csynth) → E(Cosim) → F(RTLsim) → G(PRverify) → H(Impl) → I(Bit) → [J]. → `phase4_report.md` 문서화.
