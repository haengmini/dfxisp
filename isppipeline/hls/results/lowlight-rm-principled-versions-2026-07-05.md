<!--
File   : isppipeline/hls/results/lowlight-rm-principled-versions-2026-07-05.md
Date   : 2026-07-05 21:40 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3
Track  : Low-light RM (goal 명령 Part 2) — 원리기반 버전 구현 + mAP 실험 결과
-->
# 저조도 RM 원리기반 버전(R0..R3) mAP 실험 결과 (principled-v3)

**작성:** 2026-07-05 21:40 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` · **캠페인:** `principled-v3`

원리 정본: `lowlight-feature-principles-2026-07-05.md`.
구현: `tools/rm_versions.py` (numpy 정수 reference, HW 매핑 가능). 평가: `tools/eval_map_rmversions.py`.

---

## 1. 버전 정의 (구현됨)

| 버전 | 구성 | 출력 | 원리(§ = 원리 정본) |
|---|---|---|---|
| **R0** baseline (현행) | 2×2 bin-demosaic → BLC8+WB+gain2.0 → **gamma2.5** | H/2×W/2 | 현행 canonical (ver1 'lowlight') |
| **R1** RM_TONE_LUT_PARAM | **full-res** → BLC8+WB+gain2.0(상류)+soft-knee → **VST/GAT sqrt LUT** | H×W | P2·P3 §4.2/4.3 |
| **R2** RM_LL_BIN_DN | 2×2 bin → BLC8+WB+gain2.0+soft-knee → **edge-preserving 3×3** → VST LUT | H/2×W/2 | P0·P3 §4.1/4.4 |
| **R3** RM_TONE_CLAHE | full-res → BLC8+WB+gain2.0+soft-knee → **CLAHE local tone** (clip=2, 8×8 tile) | H×W | P2·P3 §4.2 local |

R0는 대조군으로 현행 HW 정합 low-light RM(`isp_pipeline_ver1.lowlight`)을 그대로 호출.
R1~R3는 공유 baseline core(demosaic/BLC/WB) 위에 원리적 tone/denoise를 얹음.

## 2. 실험 방법 (정직한 명세)

- **평가기 = pycocotools COCOeval.** overall mAP@[.5:.95], mAP@.5, 그리고 **객체크기별
  AP(small/medium/large)를 단일 표준 COCO 평가 pass에서 동시 산출**. (ultralytics val 대신
  COCOeval을 쓴 이유: size 분해가 native로 나오고 arm 간 버킷을 동일하게 고정할 수 있음.)
- **공정한 size 버킷팅:** 모든 arm을 **공통 full-resolution 좌표계**에서 채점. binning arm
  (R0,R2)은 H/2×W/2로 렌더되지만, 검출 박스를 렌더 dims로 정규화 후 **원해상도 픽셀 그리드로
  재스케일**하고 GT area도 원해상도 area로 계산. → 한 객체의 size 버킷이 arm 간 동일하므로
  S/M/L 분해가 좌표 아티팩트가 아닌 **binning의 순수 검출 효과**를 격리한다(survey B.2.2).
- 검출: YOLOv8n(주), YOLOv8s(교차검증). conf=0.001, iou=0.7, imgsz=640, CPU-only.
- 표본: n=150 (raw==jpg 크기 일치 프레임, 각 데이터셋 앞 150장). GT = YOLO 라벨(COCO-80).

## 3. 결과 — mAP 표 (핵심)

### 3.1 YOLOv8n · mAP@[.5:.95] / mAP@0.5

| 버전 | ExDark @[.5:.95] | ExDark @0.5 | COCO @[.5:.95] | COCO @0.5 |
|---|---:|---:|---:|---:|
| R0 baseline | 0.0777 | 0.1640 | 0.2989 | 0.4536 |
| **R1** RM_TONE_LUT_PARAM | **0.0838** | 0.1768 | 0.3263 | **0.4896** |
| R2 RM_LL_BIN_DN | 0.0726 | 0.1594 | 0.3027 | 0.4412 |
| **R3** RM_TONE_CLAHE | 0.0811 | **0.1777** | **0.3373** | 0.4885 |
| Δ(best−R0) | **+0.0061 (R1, +7.9%)** | +0.0137 (R3) | **+0.0384 (R3, +12.8%)** | +0.0360 (R1) |

### 3.2 YOLOv8s (교차검증) · mAP@[.5:.95] / mAP@0.5

| 버전 | ExDark @[.5:.95] | ExDark @0.5 | COCO @[.5:.95] | COCO @0.5 |
|---|---:|---:|---:|---:|
| R0 baseline | 0.0994 | 0.2072 | 0.3486 | 0.5249 |
| **R1** RM_TONE_LUT_PARAM | **0.1087** | **0.2359** | **0.3979** | **0.5775** |
| R2 RM_LL_BIN_DN | 0.0845 | 0.1902 | 0.3393 | 0.5173 |
| R3 RM_TONE_CLAHE | 0.1057 | 0.2316 | 0.3892 | 0.5519 |
| Δ(best−R0) | **+0.0093 (R1, +9.4%)** | +0.0287 (R1) | **+0.0493 (R1, +14.1%)** | +0.0526 (R1) |

**교차검증 결론:** YOLOv8s에서 **R1이 두 데이터셋 모두 단독 최고**. YOLOv8n에서는 R1(ExDark)·
R3(COCO)가 갈리나 **full-res 두 arm(R1,R3)이 항상 binning 두 arm(R0,R2)을 능가**. 즉 검출기·
데이터셋에 걸쳐 **"binning 제거(해상도 보존)"가 가장 견고한 이득 축**이다.

## 4. 결과 — 객체 크기별 AP 분해 (named 기여, survey B.2.2)

### 4.1 YOLOv8n AP small / medium / large

| | ExDark S | ExDark M | ExDark L | COCO S | COCO M | COCO L |
|---|---:|---:|---:|---:|---:|---:|
| R0 (binned) | 0.0039 | 0.0258 | 0.1095 | 0.0697 | 0.2518 | 0.4526 |
| **R1 (full-res)** | **0.0075** | 0.0282 | **0.1190** | **0.1045** | 0.2577 | 0.4726 |
| R2 (binned) | 0.0044 | 0.0251 | 0.1054 | 0.0761 | 0.2346 | 0.4628 |
| **R3 (full-res)** | 0.0054 | **0.0322** | 0.1138 | **0.1059** | **0.2622** | **0.4868** |

### 4.2 Binning의 해상도 비용 — 정량화

동일 VST 톤을 공유하는 **R1(full-res) vs R2(binned)** 직접 대비 = binning(+denoise)의 순효과:

| 지표 | 데이터·검출기 | R1(full-res) | R2(binned) | binning 효과 |
|---|---|---:|---:|---:|
| **AP_small** | COCO·v8n | 0.1045 | 0.0761 | **−27%** |
| AP_medium | COCO·v8n | 0.2577 | 0.2346 | −9.0% |
| AP_large | COCO·v8n | 0.4726 | 0.4628 | −2.1% |
| mAP | COCO·v8n | 0.3263 | 0.3027 | −7.2% |
| mAP | ExDark·v8n | 0.0838 | 0.0726 | −13.4% |

→ **binning 손실은 small object에 집중**(−27%), large는 거의 무해(−2%) — survey B.2.2가
예측한 "binning이 32–64px 객체를 small 구간으로 밀어 넣는다"를 실측으로 확증. 현행 R0 대비
full-res(R1/R3)의 COCO small-object AP는 **0.0697 → ~0.105 (+50%)**.

## 5. 해석 — 왜 각 버전이 움직이는가 (원리 연결)

1. **해상도 보존이 지배적 이득 (P2 §3.1(1)).** full-res R1/R3가 binned R0/R2를 두 데이터셋·
   두 검출기에서 일관 능가. CNN detection이 의존하는 고주파/소형 객체 픽셀 면적을 binning이
   1/4로 없애는 손실이, pseudo-RAW에서 binning의 명목상 +6dB SNR 이득보다 크다. 이는
   rootcause 문서(2026-07-02)가 COCO에서 "해상도 손실이 압도적"이라 한 것, 그리고 Policy B
   (해상도 보존)가 더 안전하다는 제언과 정합.
2. **VST/CLAHE 톤은 검출기 분포 정합으로 이득 (P2·P3 §4.2).** full-res 상에서 VST(R1)·
   CLAHE(R3) 모두 R0의 gamma2.5+binning을 크게 상회. gain 상류 배치(§4.3)+soft-knee가
   highlight 구조를 보존해 COCO large AP까지 상승(R3 L 0.4868, 최고).
3. **binned 그리드에서 톤 종류 차이는 작다.** R0(bin+gamma2.5) vs R2(bin+VST+denoise)는
   ExDark 0.0777 vs 0.0726, COCO 0.2989 vs 0.3027로 근접 — 이득의 원천은 톤 미세조정이 아니라
   **binning 제거**임을 재확인.
4. **denoise가 pseudo-RAW에서 무익 (정직한 한계).** R2의 edge-preserving denoise는 이득을
   주지 못했다(오히려 R0보다 낮음). 원인: 데이터셋 pseudo-RAW에는 억제할 실제 Poisson-Gaussian
   노이즈가 거의 없어(원리 정본 §6.1) denoise가 순수 정보 손실로만 작동. **real-RAW에서는
   +6dB 이득이 물리적으로 존재**하므로 결론이 바뀔 수 있음 — binning/denoise는 real-RAW
   재검증 대상으로 유보.

## 6. 3rd / 4th RM 권고

| 순위 | RM | 근거(실측) | HW 비용 | 판정 |
|---|---|---|---|---|
| **3rd** | **R1 RM_TONE_LUT_PARAM** | YOLOv8s에서 두 데이터셋 **단독 최고**; v8n ExDark 최고·COCO 준최고. 모든 검출기/데이터셋에서 R0 초과. | **극소**: BRAM LUT 1개, line buffer 0, binning 없음 → partial bitstream 최소 | **채택.** survey #1 예측 실측 확인 |
| **4th** | **R3 RM_TONE_CLAHE** | v8n COCO **최고**(0.3373), ExDark mAP50 최고. full-res local tone이 medium/large까지 개선. | 중: tile-hist BRAM + frame-lag 통계 | **채택(보완재).** R1의 global tone에 local 대비 추가 |
| 강등 | R2 RM_LL_BIN_DN (=survey #2) | pseudo-RAW에서 최하위. binning 해상도 비용이 회수되지 않음. | line buffer(반폭)+DSP | **보류.** real-RAW에서만 재고 |

**핵심 실행 제언:** 현행 low-light RM(R0, Policy A binning)을 **full-res tone RM(R1)** 으로
교체하면 저조도(ExDark)와 정상조도(COCO) **양쪽에서, 두 검출기 모두에서** mAP가 오르며
특히 **small-object AP가 +50%(COCO)** 개선된다. survey의 3rd/4th 랭킹 중 **RM_TONE_LUT_PARAM은
확증, RM_LL_BIN_DN은 pseudo-RAW 조건에서 반증**됨.

## 7. 한계

1. **pseudo-RAW 노이즈 부재** → binning/denoise의 SNR 이득 과소평가(§5.4). real-RAW(보드 DPU)
   재검증 시 R2/binning 결론이 바뀔 수 있음. tone/해상도 결론은 유효.
2. **n=150, CPU-only.** 경향(부호·상대크기) 검증 목적. 절대값은 표본 의존.
3. **정적 WB/BLC 공유 core 고정.** rootcause(2026-07-02)가 지목한 ExDark의 정적 WB 색잡음
   증폭 문제는 baseline core 소관으로 본 RM 트랙 범위 밖(별도 개선축).
4. size-AP는 pycocotools 표준 + 공통 full-res 좌표 방법(§2)으로 산출 — arm 간 공정하나
   pseudo-RAW·n=150 한계는 동일 적용.

## 8. 재현

```bash
cd isppipeline/hls
# YOLOv8n (주)
python3 tools/eval_map_rmversions.py --root ../../data/exdark_val --tag ExDark \
    --model yolov8n.pt --limit 150 --out results/map_rm_exdark_yolov8n_2026-07-05.csv
python3 tools/eval_map_rmversions.py --root ../../data/coco_val   --tag COCO \
    --model yolov8n.pt --limit 150 --out results/map_rm_coco_yolov8n_2026-07-05.csv
# YOLOv8s (교차검증)
python3 tools/eval_map_rmversions.py --root ../../data/exdark_val --tag ExDark \
    --model yolov8s.pt --limit 150 --work data/_rmver_work_s \
    --out results/map_rm_exdark_yolov8s_2026-07-05.csv
python3 tools/eval_map_rmversions.py --root ../../data/coco_val   --tag COCO \
    --model yolov8s.pt --limit 150 --work data/_rmver_work_s \
    --out results/map_rm_coco_yolov8s_2026-07-05.csv
```

## 산출물

- 코드: `tools/rm_versions.py`, `tools/eval_map_rmversions.py`
- CSV: `results/map_rm_{exdark,coco}_yolov8{n,s}_2026-07-05.csv`
- 원리 정본: `results/lowlight-feature-principles-2026-07-05.md`
