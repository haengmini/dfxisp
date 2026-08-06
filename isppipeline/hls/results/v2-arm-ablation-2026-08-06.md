<!--
=============================================================================
File   : isppipeline/hls/results/v2-arm-ablation-2026-08-06.md
Date   : 2026-08-06 KST
Function: DFXISP v2 default_ISP/lowlight_ISP의 첫 검출 mAP 측정과
          denoise/binning/AWB ablation, v1 arm 대비 채택 근거를 판정한다.
Sources: tools/eval_map_isp.py, tools/default_isp_pipeline.py,
         tools/lowlight_isp_pipeline.py, data/split_nod (야간 100장),
         data/_transfer/pascal_split_100 (주광 100장), YOLOv8n,
         results/map_ablation_nod100_2026-08-06.csv,
         results/map_ablation_pascal100_2026-08-06.csv
=============================================================================
-->
# DFXISP v2 arm ablation — NOD/PASCAL 각 100장 (2026-08-06)

## 0. 결론부터

1. **Denoise가 값어치를 하는가: 아니오.** `lowlight_isp`는
   `lowlight_isp_nodenoise`보다 mAP@[.5:.95]가 **+0.0044** 높지만,
   mAP@50은 오히려 **−0.0022** 낮다. 두 지표가 엇갈리고 이득이 작아,
   출력 픽셀당 27회 비교/선택이라는 자원 지배 비용을 정당화하지 못한다.
   **denoise 제거를 권고한다.**
2. **Same-color 2×2 binning이 검출에 기여하는가: 불확실.** 구 subsample 대비
   mAP@[.5:.95]는 **−0.0022**, mAP@50은 **+0.0085**로 지표가 엇갈린다.
   합성 프레임의 +5.6~7.1 dB SNR 이득은 검출 mAP의 일관된 이득으로 이어졌다고
   볼 수 없다. 현 100장 결과만으로 검출 기여를 입증하지 못했다.
3. **v2가 v1보다 나은가: 조건별로 다르다.** 야간 `lowlight_isp`는 v1
   `lowlight`보다 **+0.0119 / +0.0220**(mAP@[.5:.95] / mAP@50)으로 두 지표
   모두 우위다. 반면 주광 `default_isp`는 v1 `normal`보다 **−0.0042 /
   +0.0027**로 엇갈려, v2 전체가 v1보다 낫다는 결론은 **불확실**하다.
   AWB도 no-AWB 대비 **−0.0050 / +0.0002**여서 기여가 입증되지 않았다.

저조도 v2는 야간에서 검출 이득이 있으나, v1의 약 3배 자원을 쓰는 채택 근거로
충분한지는 별도 자원-효용 판단이 필요하다. 특히 자원 지배 denoise는 제거하는 편이
현재 실측에 부합한다.

---

## 1. 실험 조건

- 검출기: `yolov8n.pt`, Ultralytics 8.4.82, `imgsz=640`, CPU 추론
- 야간: `split_nod`, 100장, 539 instances, 6 arms
- 주광: `pascal_split_100`, 100장, 150 instances, 3 arms
- 모든 arm: `blc_offset=2` 단일값. v1에는 배포 BLC로 실제 적용하고, v2는
  black level/range-restore 결합 상수를 그대로 사용한다.
- `eval_map_isp.py` 기본 worker 수를 사용했다. 각 CSV의 모든 행에서 `n=100`과
  `blc_offset=2`를 재확인했다.
- 최초 야간 실행은 지시된 상대경로가 이 worktree에서 존재하지 않아 0장을 찾아
  실패했다. 공유 데이터의 절대경로를 확인한 뒤 측정 로직과 arm 구현을 바꾸지 않고
  동일 명령을 재실행했다. 최종 CSV는 재실행 결과다.

## 2. 야간 결과 — split_nod 100장

| arm | mAP@[.5:.95] | mAP@50 |
|---|---:|---:|
| normal (v1) | 0.1568 | 0.3252 |
| lowlight (v1) | 0.1700 | 0.3468 |
| **lowlight_isp (v2)** | **0.1819** | **0.3688** |
| lowlight_isp_nodenoise | 0.1775 | 0.3710 |
| lowlight_isp_subsample | 0.1841 | 0.3603 |
| lowlight_isp_nodenoise_subsample | 0.1735 | 0.3429 |

### 2.1 Denoise 판정

동일한 same-color binning 조건에서 denoise를 켜면 mAP@[.5:.95]는
`0.1775 → 0.1819`(**+0.0044**)이지만 mAP@50은 `0.3710 → 0.3688`
(**−0.0022**)이다. 주 지표의 작은 이득 하나만으로 출력 픽셀당 27회
비교/선택 비용을 정당화할 수 없다. **판정: 아니오, 제거 권고.**

참고로 구 subsample 조건에서 denoise를 켠 비교는 mAP@[.5:.95]
`0.1735 → 0.1841`(+0.0106), mAP@50 `0.3429 → 0.3603`(+0.0174)으로
양수다. 그러나 채택 arm의 same-color 경로에서 결과가 일관되지 않고, denoise와
binning 사이 상호작용이 있음을 보여주므로 denoise의 독립적 보편 이득으로
해석하지 않는다.

### 2.2 Binning 판정

Denoise를 고정한 채 same-color binning을 구 subsample과 비교하면
mAP@[.5:.95]는 `0.1841 → 0.1819`(**−0.0022**), mAP@50은
`0.3603 → 0.3688`(**+0.0085**)이다. 두 지표가 반대 방향이므로 합성 프레임에서
측정된 SNR 개선이 검출 성능에도 기여한다고 단정할 수 없다. **판정: 불확실.**

### 2.3 v2 lowlight 대 v1 lowlight

`lowlight_isp`는 v1 `lowlight` 대비 mAP@[.5:.95] `0.1700 → 0.1819`
(**+0.0119**, 상대 +7.0%), mAP@50 `0.3468 → 0.3688`
(**+0.0220**, 상대 +6.3%)이다. **야간 표본에서는 예.** 다만 약 3배의 자원을
정당화하기에는 이득 규모가 제한적이며, denoise 제거 후의 실제 저자원 구성은
`0.1775 / 0.3710`으로 별도 고려해야 한다.

### 2.4 2×2 요인 배치 — denoise의 한계효용이 binning에 의해 무너진다

(검토 시 추가. 위 §2.1·2.2가 각각 한 축만 보므로, 네 조합을 한 표로 놓으면
상호작용이 드러난다. 값은 CSV 재계산으로 대조했다.)

| binning | denoise OFF | denoise ON | denoise 효과 |
|---|---|---|---|
| **same-color (진짜)** | 0.1775 / 0.3710 | 0.1819 / 0.3688 | **+0.0044 / −0.0022** |
| subsample (구, R/B 0 dB) | 0.1735 / 0.3429 | 0.1841 / 0.3603 | **+0.0106 / +0.0174** |

*(각 칸: mAP@[.5:.95] / mAP@50)*

**노이즈 저감이 약한 조건(subsample)에서는 denoise가 두 지표 모두 뚜렷이
이롭지만, 진짜 same-color binning이 들어간 순간 그 이득이 절반 이하로
줄고 지표 부호까지 갈린다.** 즉 denoise와 binning은 **같은 일(노이즈 저감)을
중복해서** 하고 있고, binning이 무조건적 √4 저감을 제공하면 σ-clip denoise가
추가로 할 일이 거의 남지 않는다.

이는 `src/lowlight_isp.md` §2.5에 미리 적어둔 예측과 일치한다 — *"binning이
무조건적 저감을 하고 난 뒤 denoise의 한계효용은 줄어들 수 있으므로 denoise
ablation의 우선순위가 올라갔다."* 이 표가 그 예측을 실측으로 확인한다.

**§2.1의 제거 권고를 강화한다:** denoise는 자원 지배 요인(출력 픽셀당 27회
비교/선택)인데, 채택 구성(same-color binning)에서는 그 비용에 상응하는 이득이
남아 있지 않다.

## 3. 주광 결과 — pascal_split_100 100장

| arm | mAP@[.5:.95] | mAP@50 |
|---|---:|---:|
| normal (v1) | 0.4197 | 0.9205 |
| default_isp (v2) | 0.4155 | **0.9232** |
| **default_isp_noawb (v2)** | **0.4205** | 0.9230 |

### 3.1 v2 default 대 v1 normal

`default_isp`는 v1 `normal` 대비 mAP@[.5:.95]가 **−0.0042**이고
mAP@50은 **+0.0027**이다. 주 지표는 악화되고 mAP@50만 근소 개선되어,
표준 v2 arm이 v1보다 낫다고 할 수 없다. **판정: 불확실(주 지표 기준 열세).**

### 3.2 AWB 기여

AWB를 켠 `default_isp`는 `default_isp_noawb` 대비 mAP@[.5:.95]
**−0.0050**, mAP@50 **+0.0002**다. mAP@50 차이는 반올림 해상도에 가까운 반면
주 지표는 더 낮다. **판정: 아니오, 이 100장에서는 AWB 기여가 입증되지 않음.**

## 4. 채택 시사점과 한계

- 저조도 v2의 야간 이득 자체는 실측됐지만, 자원 3배 증가를 그대로 수용할 근거는
  약하다. 최소한 denoise를 제거한 구성으로 자원 재산정이 필요하다.
- Same-color binning은 물리적 SNR 이득과 별개로 검출 지표가 혼합 결과다.
  이 문서는 검출 기여를 주장하지 않는다.
- 각 조건 100장의 단일 YOLOv8n 측정이며 반복실행 분산이나 다른 검출기 교차검증은
  측정하지 않았다. 따라서 0.002~0.005 수준 차이를 일반화하지 않는다.
- 측정하지 않은 통계적 유의성, 화질 지표, 제거 후 HLS 자원 수치는 제시하지 않는다.

## 5. 산출물

- `results/map_ablation_nod100_2026-08-06.csv` — 야간 6행
- `results/map_ablation_pascal100_2026-08-06.csv` — 주광 3행
- 이 문서 — CSV 표시값과 표·차이값을 재대조함
