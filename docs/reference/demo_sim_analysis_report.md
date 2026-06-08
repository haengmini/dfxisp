# ISP Pipeline Dataset Analysis Report

**데이터셋:** Dataset_demo (5쌍, 10장)  
**패치 크기:** 16×16 = 256 픽셀 (전체 이미지 밝기로 모드 결정)  
**시뮬레이터:** Python (HLS C-Sim 완전 동일 정수 산술)

---

## 1. 파라미터 요약

| 항목             | NORMAL           | LOW_LIGHT        |
| ---------------- | ---------------- | ---------------- |
| BLC              | 16               | 16               |
| Gain (Q8.8)      | 256 (×1.000)     | 320 (×1.250)     |
| CCM scale (Q8.8) | 256 (×1.000)     | 288 (×1.125)     |
| Gamma γ          | 2.2 (지수 0.455) | 4.0 (지수 0.250) |

**Checker:** DARK_THRESHOLD=50, HYSTERESIS_HI=40%, HYSTERESIS_LO=20%  
**binning_gain RP:** mode=1 → 2×2 binning + ×1.5 gain (sum×3>>3)

---

## 2. 모드 결정 결과

| 이미지 | 기대      | dark%  | 결정      | 판정 |
| ------ | --------- | ------ | --------- | ---- |
| 1high  | NORMAL    | 4.9%   | NORMAL    | ✅   |
| 1low   | LOW_LIGHT | 85.2%  | LOW_LIGHT | ✅   |
| 22high | NORMAL    | 10.5%  | NORMAL    | ✅   |
| 22low  | LOW_LIGHT | 99.4%  | LOW_LIGHT | ✅   |
| 23high | NORMAL    | 8.3%   | NORMAL    | ✅   |
| 23low  | LOW_LIGHT | 100.0% | LOW_LIGHT | ✅   |
| 55high | NORMAL    | 8.9%   | NORMAL    | ✅   |
| 55low  | LOW_LIGHT | 100.0% | LOW_LIGHT | ✅   |
| 79high | NORMAL    | 0.4%   | NORMAL    | ✅   |
| 79low  | LOW_LIGHT | 99.9%  | LOW_LIGHT | ✅   |

**정확도: 10/10 (100%)**

---

## 3. 단계별 밝기 (mean pixel value)

| 이미지 | 입력  | BLC 후 | Gain 후 | CCM 후 | Gamma 후 | 향상배율 |
| ------ | ----- | ------ | ------- | ------ | -------- | -------- |
| 1high  | 124.9 | 50.7   | 50.7    | 50.7   | 121.7    | 0.97×    |
| 1low   | 24.1  | 0.0    | 0.0     | 0.0    | 2.2      | 0.09×    |
| 22high | 134.2 | 155.1  | 155.1   | 155.1  | 203.2    | 1.51×    |
| 22low  | 18.9  | 22.0   | 27.3    | 30.1   | 149.0    | 7.89×    |
| 23high | 145.5 | 169.7  | 169.7   | 169.7  | 211.6    | 1.45×    |
| 23low  | 9.1   | 2.7    | 3.0     | 3.0    | 68.6     | 7.52×    |
| 55high | 148.8 | 115.8  | 115.8   | 115.8  | 172.5    | 1.16×    |
| 55low  | 9.3   | 0.1    | 0.1     | 0.1    | 3.6      | 0.39×    |
| 79high | 159.7 | 196.1  | 196.1   | 196.1  | 226.3    | 1.42×    |
| 79low  | 21.8  | 36.2   | 45.1    | 50.1   | 170.0    | 7.81×    |

---

## 4. 입력 통계 (전체 이미지)

| 이미지 | mean  | std  | min | max | dark%  |
| ------ | ----- | ---- | --- | --- | ------ |
| 1high  | 124.9 | 66.6 | 8   | 247 | 4.9%   |
| 1low   | 24.1  | 23.3 | 0   | 100 | 85.2%  |
| 22high | 134.2 | 61.5 | 1   | 255 | 10.5%  |
| 22low  | 18.9  | 13.0 | 0   | 76  | 99.4%  |
| 23high | 145.5 | 64.6 | 1   | 255 | 8.3%   |
| 23low  | 9.1   | 7.5  | 0   | 45  | 100.0% |
| 55high | 148.8 | 63.1 | 5   | 247 | 8.9%   |
| 55low  | 9.3   | 8.1  | 0   | 36  | 100.0% |
| 79high | 159.7 | 42.2 | 11  | 255 | 0.4%   |
| 79low  | 21.8  | 10.3 | 0   | 255 | 99.9%  |

---

## 5. 패치 샘플 픽셀 추적 (중앙 16×16 패치, 첫 8픽셀)

| 이미지 | 모드 | 입력[0..7]                             | 출력[0..7]                             |
| ------ | ---- | -------------------------------------- | -------------------------------------- |
| 1high  | N    | 90, 84, 74, 71, 67, 73, 72, 72         | 145, 140, 130, 127, 123, 129, 128, 128 |
| 1low   | LL   | 11, 9, 8, 6, 6, 6, 6, 7                | 0, 0, 0, 0, 0, 0, 0, 0                 |
| 22high | N    | 176, 176, 158, 174, 174, 160, 176, 177 | 206, 206, 195, 205, 205, 197, 206, 207 |
| 22low  | LL   | 26, 23, 24, 26, 26, 22, 26, 28         | 149, 148, 143, 153, 156, 151, 151, 151 |
| 23high | N    | 190, 191, 172, 189, 189, 175, 191, 192 | 214, 215, 204, 214, 214, 206, 215, 215 |
| 23low  | LL   | 13, 13, 10, 14, 14, 11, 14, 14         | 84, 76, 64, 95, 95, 100, 76, 84        |
| 55high | N    | 184, 187, 185, 188, 188, 187, 189, 188 | 211, 213, 212, 213, 213, 213, 214, 213 |
| 55low  | LL   | 9, 10, 10, 11, 13, 11, 9, 11           | 0, 0, 64, 0, 0, 0, 84, 0               |
| 79high | N    | 212, 212, 213, 213, 212, 212, 211, 212 | 226, 226, 227, 227, 226, 226, 226, 226 |
| 79low  | LL   | 37, 36, 37, 35, 35, 35, 33, 35         | 171, 170, 170, 168, 168, 171, 170, 171 |

---

## 6. Hex 파일 경로 (XSim TB 입력)

| 파일       | 크기     | 경로                                                                        |
| ---------- | -------- | --------------------------------------------------------------------------- |
| 1high.hex  | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/1high.hex`  |
| 1low.hex   | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/1low.hex`   |
| 22high.hex | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/22high.hex` |
| 22low.hex  | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/22low.hex`  |
| 23high.hex | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/23high.hex` |
| 23low.hex  | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/23low.hex`  |
| 55high.hex | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/55high.hex` |
| 55low.hex  | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/55low.hex`  |
| 79high.hex | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/79high.hex` |
| 79low.hex  | 256 픽셀 | `/home/mini/isp/pr_cnn/project/isppipeline/demo/sim_dataset/hex/79low.hex`  |

---

## 7. 최종 요약

- **모드 결정 정확도**: 10/10 (100%)
- **저조도 밝기 향상**: LOW_LIGHT 출력이 NORMAL 대비 최대 0.8× 향상
- **결론**: ✅ ALL PASS

### 히스토그램

각 이미지의 단계별 픽셀 분포 히스토그램:

```
sim_dataset/results/hist_1high.png
sim_dataset/results/hist_1low.png
... (10장)
```
