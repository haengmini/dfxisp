<!--
=============================================================================
File   : isppipeline/sw/sim/AWB/AWB_figures.md
Date   : 2026-08-13 KST
Function: AWB 실험 결과의 figure 세트(F1~F6) — 각 그림이 무엇을 주장하고
          어떤 실측에서 나왔는지, 그리고 이번에 새로 측정된 값과 정직하게
          남겨야 할 불일치를 기록한다.
Scope   : 전부 **현재 dataset/ 기준**(LOD_test 100 + PASCAL_test 100). 파생
          디렉터리는 dataset/ 안에 만들지 않았다 — mAP 하네스가 요구하는
          {images,labels,raw_bin} eval root는 scratchpad에 만들어 쓰고 버렸다.
Sources : AWB.md, AWB_report.md(2026-08-12, LOD_test_eval 기준),
          results/lowlight-wb-mode-split-2026-08-03.md(SonyNOD 321 원본),
          awb_figure_data.py / awb_figures.py / awb_qualitative.py (신규),
          .claude/worktrees/hw-interface-prompt/.../eval_map_isp.py (그 자리 실행)
=============================================================================
-->
# AWB figure 세트 (2026-08-13, LOD_test + PASCAL_test)

## 0. 결론부터

figure 6종을 현재 데이터셋으로 산출했다. 전달하려는 서사는 하나다 —
**색은 객관적으로 틀렸고, 그것을 고쳐도 검출은 움직이지 않으며, 왜 그런지도
보인다.** 논문 본문에 넣는다면 **F1 → F5 → F2** 순(무엇 → 왜 → 규모)이고,
F4는 F1(a)를 대체할 만큼 강하며, F3·F6은 각각 한계 절과 정성 근거다.

이번 실행에서 **AWB.md/AWB_report.md가 미결로 남겼던 3개가 메워졌고**(§3),
**새로운 불일치 1개가 나왔다**(§4). 결론(WB는 레버가 아니다)은 유지된다.

---

## 1. figure 목록

| | 파일 | 무엇을 주장하는가 |
|---|---|---|
| **F1** | `figures/F1_diagnosis_vs_response.*` | 진단은 맞다(배포 WB가 저조도에 절반) + 검출은 무반응(전 후보가 noise band 안) |
| **F2** | `figures/F2_lever_scale.*` | WB spread 0.0010 vs BLC spread 0.0501 — **같은 100장에서 50배** |
| **F3** | `figures/F3_reproducibility.*` | 두 데이터셋이 주 지표에서 **부호까지 엇갈린다** — 일관된 승자 없음 |
| **F4** | `figures/F4_as_shot_wb_scatter.*` | 배포 상수가 두 데이터셋의 as-shot 구름 **바깥**에 있다 |
| **F5** | `figures/F5_channel_histogram.*` | 저조도 화소 51~71%가 BLC에서 0 — WB가 작용할 여지가 없다 |
| **F6** | `figures/F6_qualitative_wb.png` | 색은 확 바뀌는데 박스·신뢰도는 그대로 |

PNG(dpi 200) + PDF 동시 저장(F6은 이미지 몽타주라 PNG만).
팔레트는 dataviz 레퍼런스 categorical 슬롯 1~3 — light 모드 all-pairs 검증
통과(CVD ΔE 9.2, normal-vision ΔE 24.0), 전 계열 직접 라벨 병행.

---

## 2. 측정값 (신규, 현재 데이터셋)

### 2.1 채널 진단 — 두 데이터셋

post-BLC / pre-gain 도메인(`AWB.md §2.1`과 동일, `blc_only()` 재사용):

| | LOD_test (야간, n=100) | PASCAL_test (주간, n=100) |
|---|---:|---:|
| 채널 평균 R / G / B | 45.6 / 85.3 / 31.9 | 186.1 / 391.3 / 295.3 |
| R/G · B/G | 0.535 · **0.373** | 0.476 · **0.755** |
| gray-world WB (Q8) | R **479** / B **686** | R **538** / B **339** |
| 배포(286/307) ÷ gray-world | R 0.60× / **B 0.45×** | R 0.53× / **B 0.91×** |
| BLC 0 클리핑 R/G/B [%] | 64.2 / 51.0 / **71.5** | 16.3 / 7.6 / 11.3 |
| 포화 [%] | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |

**핵심**: 배포 WB는 주간(PASCAL)에서 B가 0.91×로 거의 정확한데 야간(LOD)에서는
0.45×다. 즉 **배포된 상수는 사실상 주간용 캘리브레이션**이다.

### 2.2 as-shot 카메라 WB (F4, 신규 측정)

| | 고유 조합 수 | R/G | B/G |
|---|---:|---|---|
| LOD (Sony, auto WB) | **100 / 100 (전부 다름)** | 1.559 ~ 2.520 (중앙 1.963) | 1.621 ~ 2.984 (중앙 2.090) |
| PASCAL (Nikon, 고정) | **1 / 100 (전부 동일)** | 2.449 | 1.051 |
| **배포 상수** | — | **1.117** | **1.199** |

두 데이터셋은 WB 평면의 **반대 구석**에 있고(LOD는 청색 보정 요구, PASCAL은
적색 보정 요구), 배포 상수는 **양쪽 구름 모두의 바깥**이다. PASCALRAW가 전
프레임 동일한 as-shot 값을 갖는 것(카메라 고정 프리셋)은 이번에 처음 확인됐다.

### 2.3 mAP 스윕

`lowlight` arm 단독, BLC=2, YOLOv8n, imgsz 640, n=100.
`--wb-lowlight`가 저조도 경로만 바꾸므로 PASCAL도 같은 arm으로 측정했다
(주간 데이터에 저조도 arm을 태운 off-design 조건 — 절대값이 아니라 **후보 간
차이**만 읽을 것).

| 후보 | LOD @[.5:.95] | LOD @50 | PASCAL @[.5:.95] | PASCAL @50 |
|---|---:|---:|---:|---:|
| WB off | 0.0714 | 0.1390 | 0.0991 | 0.2895 |
| **배포** | **0.0720** | **0.1389** | **0.1001** | **0.2903** |
| R만 | 0.0722 | 0.1437 | 0.1007 | 0.2984 |
| B만 | 0.0719 | 0.1411 | 0.0992 | 0.2946 |
| R+B 중간 | 0.0724 | 0.1446 | 0.0995 | 0.2991 |
| gray-world(479/686) | 0.0723 | 0.1416 | 0.0987 | 0.3016 |
| **spread** | **0.0010** | 0.0057 | **0.0020** | **0.0121** |

### 2.4 BLC 스윕 (F2, 신규 — 같은 데이터셋)

| BLC offset | 0 | 1 | **2(배포)** | 4 | 8 | 16 |
|---|---:|---:|---:|---:|---:|---:|
| mAP@[.5:.95] | 0.0705 | **0.0745** | 0.0720 | 0.0611 | 0.0398 | 0.0244 |
| mAP@50 | 0.1321 | 0.1431 | 0.1389 | 0.1242 | 0.0764 | 0.0459 |

spread **0.0501**. WB(0.0010) 대비 **50배**.

### 2.5 정성 비교 (F6)

밝은 상위 3프레임, WB off / 배포 / gray-world:

| 프레임 | off | 배포 | gray-world |
|---|---:|---:|---:|
| DSC03817 | 1 | 1 | 1 |
| DSC03833 | 2 | 2 | 2 |
| DSC03631 | 1 (0.87) | 1 (0.86) | 1 (0.85) |

색 캐스트는 초록에서 중성으로 눈에 띄게 바뀌지만 **검출 수는 전부 동일**하고
신뢰도는 0.87→0.86→0.85로 소수점 둘째 자리만 움직인다.

---

## 3. 이번에 메워진 공백

1. **BLC 레버를 같은 데이터셋에서 실측** — `AWB_report.md §3.1`과 §4는 BLC
   비교가 "원본 SonyNOD 수치를 교차 데이터셋으로 참고"한 것이라고 단서를
   달았다. LOD_test 자체에서 재면서 그 단서가 필요 없어졌다: 0.0010/0.0501 =
   **1/50**(교차 참조 추정치였던 1/88과 같은 자릿수).
2. **BLC=0 측정** — `AWB_report.md §7`의 미착수 후속 후보. 결과는 **0.0705로
   배포값 2(0.0720)보다 낮다.** "BLC=0이 근-흑색 픽셀을 살려 이득을 줄
   가능성"은 이 데이터셋에서 부정됐다. 다만 **정점은 배포값 2가 아니라 1**
   (0.0745, +3.5%)이다 — SPEC §11의 "1~2 평평한 정점"과 정합하나, LOD_test에서는
   1쪽이 높다.
3. **PASCAL WB 스윕** — 지금까지 WB 스윕은 저조도 데이터에서만 돌았다. 주간
   데이터에서도 주 지표는 평평하다(§4의 단서 포함).

---

## 4. 정직하게 남겨야 할 것

### 4.1 PASCAL의 mAP@50 spread는 프로젝트 기준선을 넘는다

PASCAL @50 spread = **0.0121**로, 이 프로젝트가 관례로 쓰는 잡음대(0.005)의
2배이자 `AWB_report.md §3.1`이 언급한 "2배 이상(0.01)" 기준도 넘는다. 게다가
LOD의 지터와 달리 **off(0.2895) → gray-world(0.3016)로 대체로 단조 증가**한다
(+4.2%).

그러나 **주 지표(mAP@[.5:.95])는 0.0020으로 평평하고, gray-world가 오히려
최저(0.0987)** 다. 두 지표가 엇갈린다는 사실 자체를 결론으로 남긴다:
전역 색 게인은 IoU 0.5 경계에 걸친 약한 검출을 넘기게 할 수는 있어도
**국소화(localization)를 개선하지 못한다** — 그래서 엄격한 IoU 평균에서는
사라진다. "WB는 레버가 아니다"는 주 지표 기준으로 유지되지만, **"@50에서도
아무 일도 없다"고 쓰면 틀린다.**

### 4.2 두 데이터셋은 주 지표에서 부호가 엇갈린다 (F3)

gray-world는 LOD에서 +0.42%인데 PASCAL에서 −1.35%, R+B 중간은 +0.56% vs
−0.61%다. 6후보 중 부호가 일치하는 것은 `WB off`(양쪽 음)와 `R만`(양쪽 양)
둘뿐이다. **어떤 후보도 두 데이터셋에서 함께 이기지 못한다** — 배포값을 바꿀
근거가 없다는 뜻이고, 동시에 개별 후보의 부호를 근거로 삼는 논증(원본 §3.2의
초가산적 파라독스 포함)이 표본 의존적이라는 `AWB_report.md §4`의 관찰을
데이터셋 축에서 다시 확인한 것이다.

### 4.3 조건 단서

- PASCAL 수치는 **주간 데이터에 저조도 arm을 태운 off-design 조건**이다
  (`--wb-lowlight`가 그 경로만 바꾸기 때문). 데이터셋 간 mAP 절대값 비교 금지.
- 전부 YOLOv8n 단일 모델(2026-08-13 결정: YOLO 계열은 v8n만).

---

## 5. 검증

1. **채널 진단 재현** — LOD에서 B/G 0.373, gray-world R479/B686, 배포/gray
   0.60×/0.45×로 `AWB_report.md §2`와 **완전 일치**. PASCAL도 08-03 원본
   (R/G 0.476, gray-world R538, 배포/gray 0.53×/0.92×)과 일치(B는 0.91× —
   321장 vs 100장 표본 차이).
   즉 삭제된 `dataset/LOD_test_eval/raw_bin` 없이 ARW/NEF에서 직접 읽은 값이
   기존 경로와 정합한다(shift8 → `>>4` 규약을 메모리에서 그대로 재현).
2. **하네스 provenance** — 새로 만든 eval root에서 배포값 control만 재실행:
   **0.0720 / 0.1389**로 08-12 CSV의 배포 행과 정확히 일치.
   `build_lod_test_eval_root.py`에 추가한 `--sensor`가 기본(LOD) 경로를
   바꾸지 않았음도 함께 확인된다.
3. **팔레트** — `validate_palette.js` all-pairs light 통과(§1).

---

## 6. 산출물 · 재현

**신규 스크립트**
- `awb_figure_data.py` — ARW/NEF 직접 측정(채널 통계·히스토그램·클리핑·as-shot WB).
  `awb_channel_diagnostic.blc_only`를 import해 도메인 정의를 공유(복사 아님).
- `awb_figures.py` — F1~F5.
- `awb_qualitative.py` — F6.
- `build_lod_test_eval_root.py`에 `SENSORS` + `--sensor nikon_pascal` 추가
  (순수 추가, `sony_lod` 기본 경로는 기존과 바이트 동일).

**데이터**
- `awb_stats_{lod,pascal}.json`, `awb_hist_{lod,pascal}.npz`
- `awb_wb_sweep_pascaltest.csv`(신규), `awb_blc_sweep_lodtest.csv`(신규)
- `awb_wb_sweep_lodtest.csv`(08-12, 재사용 — §5.2로 검증)
- `awb_lod_control_recheck.csv`(§5.2 provenance 검증 원자료, 1행)

**재현**
```bash
cd isppipeline/sw/sim/AWB
python3 awb_figure_data.py --dataset LOD       # ~15분
python3 awb_figure_data.py --dataset PASCAL    # ~15분
python3 awb_figures.py                          # F1~F5, 수초

# mAP 스윕은 {images,labels,raw_bin} eval root가 필요하다. dataset/ 안에
# 만들지 말고 임시 경로에 만들 것(SW 실험 중 dataset/은 원본 2개만 유지):
python3 ../build_lod_test_eval_root.py --src dataset/LOD_test    --out <tmp>/LOD_test_eval
python3 ../build_lod_test_eval_root.py --src dataset/PASCAL_test --out <tmp>/PASCAL_test_eval \
        --sensor nikon_pascal
# 이후 워크트리의 eval_map_isp.py를 그 자리에서 실행(--root <tmp>/...,
# --arms lowlight, --blc-offsets, --wb-lowlight) — AWB_report.md §3과 동일 원칙.

python3 awb_qualitative.py --root <tmp>/LOD_test_eval \
        --stems DSC03817,DSC03833,DSC03631      # F6
```

문서 끝.
