<!--
=============================================================================
File   : isppipeline/hls/results/hw-dataset-geometry-2026-08-13.md
Date   : 2026-08-13 KST
Branch : exp/adaptive-tau-realdata-2026-07-13
Function: LOD/PASCALRAW 실 RAW를 FPGA에 넣을 수 있는 단일 해상도로 통일한
          CFA-보존 4× 축소 데이터셋(`*_test_hw`)의 설계 근거·계약·검증 기록.
Sources: tools/build_hw_dataset.py (신규, 본 작업)
         src/dfxisp_accel.cpp:279 (MAX_BINNED_W=960 하드 배열 바운드)
         SPEC.md §3.1/§4 (BLC=2, dark16, DARK_RATIO_PCT=62 — 2026-07-20 배포)
         results/pascalraw-adapter-2026-07-13.md (기존 shift8 SW-eval 계약)
Repro  : python3 tools/build_hw_dataset.py --selftest
         python3 tools/build_hw_dataset.py --raw-dir dataset/LOD_test/raw \
             --labels-dir dataset/LOD_test/labels --out dataset/LOD_test_hw --preview 3
         python3 tools/build_hw_dataset.py --raw-dir dataset/PASCAL_test/raw \
             --labels-dir dataset/PASCAL_test/labels --out dataset/PASCAL_test_hw --preview 3
=============================================================================
-->
# HW 입력 해상도 통일: CFA-보존 4× 축소 데이터셋 (2026-08-13)

## 1. 문제

실 RAW 두 세트는 가속기에 그대로 못 넣는다.

- LOD(Sony `.ARW`): visible **5496×3672**, 유효 crop 5472×3648, black 800 / white 16380 → **14-bit**
- PASCALRAW(Nikon `.NEF`): visible **6034×4012**, black 0 / white 4095 → **12-bit**
- `dfxisp_accel.cpp:279`의 `static uint16_t row_r[MAX_BINNED_W]`, `MAX_BINNED_W = 960`은
  **배열 하드 바운드**다 → raw 폭 1920 초과 시 조용히 깨진다. 20 MPix는 프레임당
  DDR 40 MB이기도 하다.
- 두 세트의 크기·화면비(1.5000 vs 1.5040)가 달라 **전 화각 유지와 동일 해상도는 동시에 불가**.

## 2. 계약 (두 데이터셋 동일)

```
visible → RGGB phase 정렬 → 짝수 오프셋 중앙 crop 5472×3648
        → 동색 데시메이션 4×                    → 1368×912
        → 채널별 BLC + white-level 정규화        → 12-bit in uint16 LE
```

| | LOD | PASCAL |
|---|---|---|
| 출력 | **1368×912** | **1368×912** |
| crop origin(실측, 전 프레임 동일) | (12, 12) | (280, 182) |
| 화각 | 100% (rawpy 문서상 crop margin과 정확히 일치) | ~82% |
| low-light RM 출력 | 684×456 | 684×456 |

684 ≤ MAX_BINNED_W(960) → 저조도 경로 안전. 프레임당 2.44 MB(uint16).
출력은 `dataset/{LOD,PASCAL}_test_hw/{raw_bin,labels,preview,meta.json}`, 원본 무수정.

## 3. 설계 판단 두 가지 (일반적 권고와 다른 부분)

### 3.1 동색 "평균"이 아니라 동색 **데시메이션**

4×4 동색 평균은 `RM_LOW_LIGHT`가 하는 2×2 binning과 **같은 연산**이다. 전처리에서
그걸 먼저 적용하면 (a) 검증 대상인 효과를 전처리에 선반영하고, (b) 노이즈를 줄여
2026-07-20 배포 캘리브레이션(BLC=2 / dark16 / DARK_RATIO_PCT=62 — 전부 full-res
화소당 노이즈 기준으로 튜닝)을 무효화한다. 데시메이션은 화소당 노이즈 통계를
원본 그대로 유지한다. 대가는 에일리어싱이고, 대상 클래스(person/car/bicycle)가
커서 감수 가능하다. 유지되는 quad는 통째로(co-sited R/G/G/B) 가져오므로 8×8
화소 이웃에서 완전한 RGGB quad 하나를 뽑는 형태다.

### 3.2 shift8이 아니라 **12-bit**

`dfxisp_accel`은 12-bit(`RAW12_MAX=4095`)를 먹는데 shift8은 최대 65280이라 그대로
넣으면 전 화소 포화된다. 정보량 쪽이 더 중요한데, 기존 shift8 LOD `raw_bin` 실측이
평균 250.7/65280 = **8-bit 환산 0.98 LSB**, p99 = 6 LSB였다 — 저조도 신호 99%가
255단계 중 0~6에 몰려 있었다(SPEC §11의 "BLC=2에서도 52~73% 0 클리핑"의 정체).
12-bit는 손해가 없다: 기존 shift8 뷰는 `(v>>4)<<8`로 되뽑히고(반올림 ±1 code),
역방향은 불가능하다.

## 4. 검증

1. **선형 로직**(`--selftest`): 데시메이션의 색 위상·소스 인덱스, PASCAL 기하에서
   짝수 오프셋 중앙 crop이 (280,182)로 떨어지는지, 12-bit 정규화 양 끝점,
   라벨 재사상 4종(항등/완전 이탈 drop/부분 clip). 전부 PASS.
2. **위상**: 데시메이션 후 (0,0) quad가 `RGGB`인지 프레임마다 해석적으로 assert
   (가정 아님). 200/200 프레임 통과, 변환 에러 0.
3. **checker 통계 연속성** (핵심): 축소 전 full-res crop과 축소본의
   dark_ratio(raw12 < 256)를 12프레임씩 비교.

   | | max &#124;Δ&#124; | mean Δ |
   |---|---|---|
   | LOD | **0.021 %p** | +0.001 %p |
   | PASCAL | **0.067 %p** | −0.003 %p |

   화소당 std도 보존(예: LOD DSC01432 521.8 → 523.0). 즉 62% 임계가 걸려 있는
   양이 축소로 흔들리지 않는다. 참고로 같은 프레임의 구 shift8 dark_ratio와는
   최대 ~0.5 %p 차이가 나는데, 이는 8→12 bit 양자화 경계 효과다(§5).
4. **라벨**: 미리보기에 박스 오버레이해 육안 확인(PASCAL 2장, 정렬 정확·경계
   clip 정상). 집계 — LOD kept 530 / clipped 29 / dropped 0,
   PASCAL kept 162 / clipped 33 / **dropped 2**(1.2%).
   `--min-visible 0.25`: crop 후 원면적 25% 미만만 남는 박스는 탐지 불가능한
   GT라 제외(기본값, 플래그로 조정 가능).

## 5. 남은 것 / 주의

- **임계 재확인(저비용)**: dark_ratio 자체는 보존되지만 8→12 bit로 양자화 경계가
  바뀌어 구 shift8 대비 최대 ~0.5 %p 차가 있다. 62% 경계 근처 프레임만 재확인하면
  된다. BLC=2(=12-bit 32)는 단위 환산이 정확해 그대로 유효.
- **라벨 기준 프레임의 기존 어긋남**(이번 변경과 무관, 이번에 정합됨): LOD 라벨은
  visible 5496×3672 기준인데 구 `raw_bin`은 5472×3648이었고(0.2~0.4% 어긋남),
  PASCAL 라벨은 정확히 3:2인 600×400 기준인데 raw는 1.5040이다. 본 도구는 라벨을
  visible 전 프레임 정규화 좌표로 보고 crop 기준으로 재사상하므로 LOD 쪽 어긋남은
  해소된다.
- **PASCAL 화각 9%**(가로·세로 각각) 손실은 통일 해상도를 얻기 위한 의도된 대가다.
  false-trigger 집계는 장면 통계 기반이라 영향이 거의 없지만(§4.3), mAP 절대값은
  구 full-res 수치와 직접 비교하면 안 된다.
- 데이터셋 디렉터리는 `.gitignore`의 `dataset/` 규칙에 걸려 커밋되지 않는다
  (2×240 MB). 재생성은 위 Repro 명령 두 줄.
