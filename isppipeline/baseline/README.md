# task2 — Baseline ISP (Vitis Vision L1)

Vitis Libraries(Vision L1) 함수만으로 구성한 **가장 기본적인 컬러 ISP 파이프라인**.
task1의 16-bit RGGB Bayer(`Dataset/*_raw`)를 입력받아 RGB 8-bit를 출력한다.
적응형(저조도) 처리는 없으며, `proposal/`(task3)의 비교 기준선(baseline)이다.

## 파이프라인

```
Bayer16 (RGGB, task1 raw)
  → scale16→8        (16-bit raw → 8-bit, 센서 ADC 등가)
  → blackLevelCorrection   xf_black_level.hpp     (BLC, 기본 identity)
  → gaincontrol            xf_gaincontrol.hpp     (정적 WB: R×1.60 G×0.80 B×1.36)
  → demosaicing            xf_demosaicing.hpp     (RGGB → RGB, XF_BAYER_RG)
  → colorcorrectionmatrix  xf_colorcorrectionmatrix.hpp (CCM identity)
  → gammacorrection        xf_gammacorrection.hpp (per-channel 256-LUT, sRGB γ2.2)
  → RGB8
```

- WB 게인은 task1 `unprocess`가 적용한 카메라 WB의 역으로 설정해 색을 복원한다.
- 채널 패킹 주의: xf demosaic 출력은 `[23:16]=R [15:8]=G [7:0]=B`. CCM은 내부적으로
  `r=[7:0]`로 추출(반대 명명)하므로 채널 섞임을 피하려 CCM은 identity로 둔다.

## 파일

| 파일 | 역할 |
|------|------|
| `isp_baseline.hpp` | 파이프라인 선언·파라미터(WB/CCM/크기) |
| `isp_baseline_accel.cpp` | `isp_baseline_core`(DATAFLOW) + `ISPBaseline_accel`(AXI top) |
| `isp_baseline_tb.cpp` | OpenCV-free csim 테스트벤치 (raw bin ↔ rgb bin) |
| `prep_and_check.py` | PNG↔bin 변환 + 출력 PNG/통계 sanity |
| `build.sh` | 호스트 g++ csim 일괄 실행 |
| `run_hls.tcl` | Vitis HLS csim + csynth |

## 실행

```bash
# 호스트 csim (Vitis HLS 헤더만 사용, OpenCV 불필요)
./build.sh                                   # 기본: COCO_5000_raw/test 첫 장
./build.sh ../../Dataset/ExDark_5000_raw/test/images/xxxx.png

# Vitis HLS (합성까지)
python3 prep_and_check.py prep <raw.png> bayer16.bin
vitis_hls -f run_hls.tcl
```

## 검증 결과

- 호스트 g++ csim: **컴파일 OK, end-to-end 실행 OK**.
- COCO `000000000724`(STOP 사인) → 색 정확 복원(빨강 사인/파란 하늘/초록 나무), 방향 보존.
- sanity(유효 RGB 이미지): **PASS**.
- 합성(csynth)/cosim은 `run_hls.tcl`로 수행(보드 단계, 후속).
