# RGB32 골든 벡터 (Phase A2)

확정 인터페이스(2026-06-04): 전 구간 32-bit RGB `[31:24]=0x00|B|G|R`.  
정준 모델 `isppipeline/unprocess/isp_pipeline.py::process_to_rgb32()` 호출. 패치 16×16.

- bright = `COCO/000000008690.jpg` (dark_ratio 0.000) → NORMAL
- dark   = `ExDark/2015_00034.jpg` (dark_ratio 1.000) → LOW_LIGHT (2×2 binning)

## 골든 파일
| 파일 | 샘플 | 모드 | 픽셀수 | 첫픽셀 |
|------|------|------|-------:|--------|
| `input_bright_rgb.hex` | bright | - | 256 | `0x002D305D` |
| `input_dark_rgb.hex` | dark | - | 256 | `0x00282729` |
| `expected_normal_rgb.hex` | bright | normal | 256 | `0x005F6394` |
| `expected_lowlight_rgb.hex` | dark | lowlight | 64 | `0x00B8AFB6` |

검증: ✅ ALL PASS (픽셀수 일치 + trace==process_to_rgb32).

Phase B1(C-Sim)/C2(RTL)에서 이 hex를 `$readmemh`/`memcmp` 정답으로 사용.
