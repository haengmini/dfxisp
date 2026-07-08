<!--
=============================================================================
File   : isppipeline/hls/results/principled-v3-refinement-2026-07-05.md
Date   : 2026-07-05 23:56 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3 (refinement pass, 세분화)
Function: principled-v3 재검토 → Codex 고급 리뷰 → 전략 고도화 → 세분화 버전
          생성·실험·분석. goal(2차) 4파트의 통합 결과 문서.
Inputs : self-review(코드 정독) + Codex review(§4) + 세분화 실험
         (checker_versions_fine.py, rm_versions_fine.py, eval_map_rmversions_fine.py)
=============================================================================
-->
# principled-v3 재검토·고도화 및 세분화 실험 종합 (refinement, 2026-07-05)

**작성:** 2026-07-05 23:56 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` ·
**캠페인:** `principled-v3` (refinement pass)

> 1차 결과(`principled-comparison-2026-07-05.md` 및 트랙별 문서)를 **비판적으로 재검토**하고,
> **Codex 고급 리뷰**(§4)를 받아 전략을 고도화한 뒤, 갭을 메우는 **세분화 버전**을 만들어
> 실험·분석했다. 핵심은 1차의 두 서사를 **정직하게 교정**한 것이다:
> (i) 저조도 RM 이득은 "VST 톤"이 아니라 **binning 제거(해상도)**에서 오며, **COCO/정상조도에서
> 견고**하고 **저조도(ExDark)에서는 검출기 의존적 wash**다 — 배포본은 이미 원리적 sqrt(VST계열)
> 톤을 써서 VST-param LUT·soft-knee는 순효과가 없다.
> (ii) 최적 checker dark 임계는 16이 아니라 **더 낮은 대역(dark8~10)**이며, 정직한 held-out
> CV에서 유지되고 C3/C4 기각은 nested-CV로 확정된다.

---

## 1. 자체 재검토 — 발견한 갭 (놓친·허술한 부분)

1차 산출물을 코드 수준까지 재검토해 다음 5개 갭을 특정했다:

| # | 갭 | 심각도 | 영향 |
|---|---|---|---|
| **G-RM-1** | **R0 baseline tone confound.** 실험 R0는 `isp_pipeline_ver1` lowlight = **gamma2.5**인데, 실제 배포되는 canonical HLS(`dfxisp_accel.cpp` `gamma2()`=`floor(sqrt(255·v))`)는 **sqrt=gamma2.0(이미 VST계열)**. R0→R1 한 스텝이 해상도(bin→full)와 톤(g2.5→VST)을 **동시에** 바꿔 이득 귀속이 불가능. | 높음 | "VST 톤이 이득" 서사가 아티팩트일 수 있음 |
| **G-CHK-1** | dark-ratio를 coarse grid{16,24,32,48,50,64}에서만 평가. 노이즈 플로어 원리(원리3)가 시사하는 **16 미만** 대역 미탐색. | 중 | 최적 임계 미확정 |
| **G-CHK-2** | C1..C4의 J/임계가 **in-sample**(같은 1150프레임에 적합·채점). C3/C4는 그리드 적합이라 낙관 편향. | 중 | 기각 결론의 정직성 |
| **G-STAT-1** | mAP n=150 단일런, **CI/유의성 없음**. 여러 델타가 noise 대역일 가능성. | 중~높 | 결론 신뢰도 |
| **G-HW-1** | "HW 0/감소"를 **csynth로 미측정**, 주장에 그침. | 중 | 정량 근거 부재 |

세분화 실험은 G-RM-1(§3), G-CHK-1·2(§2), G-STAT-1(§2·3 부트스트랩/전수)을 직접 해소한다.
G-HW-1은 §5 전략에 board-track 항목으로 이관.

## 2. Checker 세분화 — 정직한 held-out CV + 미세 임계 (G-CHK-1·2 해소)

`tools/checker_versions_fine.py` (전수 1150프레임, 5-fold CV로 **held-out** recall/FT/J).
비용 C_miss=0.1118 / C_FA=0.0387, R=½(miss·C_miss+FT·C_FA).

| 통계량 | AUC | in-sample J | **CV held-out J** | CV recall | CV FT | **CV risk R** |
|---|---:|---:|---:|---:|---:|---:|
| **dark8** | 0.9769 | 0.852 | **0.850** | 0.926 | 0.076 | 0.00563 |
| dark10 | 0.9775 | 0.854 | 0.838 | 0.933 | 0.095 | 0.00561 |
| dark12 | 0.9774 | 0.850 | 0.832 | 0.919 | 0.087 | 0.00623 |
| dark16 (1차 채택) | 0.9766 | 0.849 | 0.838 | 0.918 | 0.080 | 0.00613 |
| dark20 | 0.9759 | 0.842 | 0.826 | 0.911 | 0.085 | 0.00662 |
| dark32 | 0.9712 | 0.830 | 0.821 | 0.931 | 0.110 | 0.00600 |
| logmean | 0.9780 | 0.849 | 0.843 | 0.935 | 0.092 | **0.00543** |
| entropy | 0.9773 | 0.854 | 0.838 | 0.934 | 0.096 | 0.00557 |
| **C1 fixed dark16>0.62** | 0.9766 | — | — | 0.936 | 0.089 | **0.00531** |
| C2 fixed dark16>0.553 | 0.9766 | — | — | 0.965 | 0.134 | 0.00454 |

**분석:**
1. **최적 임계는 16보다 낮다.** honest held-out J 최고는 **dark8(0.850)**, risk 최저(J-fit 계열)는 **logmean/dark10**. 이는 원리3("임계를 read-noise 플로어=black level로 내려라")을 **더 낮은 임계일수록 유리**로 정량 확인 — 1차의 dark16은 near-optimal이었으나 THE optimum은 아니었다.
2. **어떤 통계량도 dark-ratio를 지배하지 못한다(정직 확인).** logmean·entropy의 CV J(0.843/0.838)가 dark8(0.850)을 못 넘음 → **C3/C4 기각은 in-sample이 아니라 held-out에서도 성립**. G-CHK-2 우려가 결론을 뒤집지 않음.
3. **in-sample↔held-out 격차는 작다**(dark16 0.849→0.838, Δ0.011) → 1차 in-sample 수치의 낙관 편향은 경미.
4. **risk는 통계량보다 운영점이 좌우.** 고정 dark16>0.62(R=0.00531)·Bayes 0.553(0.00454)이 모든 J-fit 점보다 낮음 — miss 비대칭(2.89:1) 하에서 **임계를 J-max보다 약간 낮춰 recall을 사는** 것이 옳다는 원리1 재확인.

**Refined checker 권고:** 배포는 **dark8~dark12 대역 + 낮은 운영점(recall 우선)** 을 채택 후보로 승격하되, pseudo-RAW 절대값 한계(원리 문서 §한계) 때문에 **실센서 black level 재보정 전에는 dark16>0.62를 안전 기본값으로 유지**하고 dark10을 A/B 후보로 병기. HW 비용은 세 안 모두 동일(레지스터값만).

## 3. Low-light RM 세분화 — resolution×tone factorial (G-RM-1 해소)

`tools/rm_versions_fine.py`: 2×3 factorial(해상도{full,bin}×톤{gamma2.5, sqrt/gamma2.0, VST})
+ soft-knee/denoise probe. `eval_map_rmversions_fine.py`(COCOeval size-AP + **image-level 부트스트랩
95% CI**). 이로써 "binning 제거"와 "톤 변경"을 **독립적으로** 귀속한다.

### 3.1 전수(ExDark n=260*, COCO n=347*), yolov8n, mAP@[.5:.95] (부트스트랩 300)

\* **정직한 n 정정:** raw16 크기가 JPEG와 일치하는 프레임만 유효 → ExDark 260(491 이미지 중), COCO 347(575 raw 중). `--limit 575`를 줬어도 실제 평가 n은 이 값이다(두 검출기 런 동일, apples-to-apples). 1차 문서들이 "전수 n=575"라 표기한 것은 부정확했고 여기서 정정한다(부호·순위 결론은 불변, 표본 크기 표기만 교정).

| 셀 | 구성 | ExDark (95%CI) | COCO (95%CI) |
|---|---|---:|---:|
| B_g25 | bin+gamma2.5 (**≈1차 R0**) | 0.0849 [.074,.110] | 0.2650 [.238,.312] |
| **B_g20** | bin+sqrt (**실제 배포 톤, 정직한 control**) | 0.0898 [.077,.115] | 0.2671 [.240,.313] |
| **F_g20** ★ | **full-res+sqrt (binning만 제거)** | **0.0962** [.083,.122] | **0.2847** [.255,.332] |
| F_vst_knee | full-res+VST+soft-knee (**≈1차 R1**) | 0.0967 [.083,.125] | 0.2814 [.255,.331] |
| B_vst_dn | bin+VST+denoise (**≈1차 R2**) | 0.0787 [.067,.103] | 0.2508 [.226,.300] |

### 3.2 깨끗한 귀속 (factorial 대비)

| 대비 | 격리 요인 | ExDark | COCO |
|---|---|---:|---:|
| F_g20 − B_g20 | **binning 제거(해상도)** | **+0.0064** | **+0.0176** |
| B_g20 − B_g25 | 톤 gamma2.5→sqrt | +0.0049 | +0.0021 |
| F_vst_knee − F_g20 | VST offset + soft-knee | +0.0005 | **−0.0033** |
| B_vst_dn − B_g20 | edge-preserving denoise | −0.0111 | −0.0163 |

**분석 (핵심 교정, yolov8n; detector 의존성은 §3.4):**
1. **저조도 RM의 유의미한 이득은 "binning 제거"에서 온다(단, ExDark는 검출기 의존 — §3.4).** yolov8n에서 F_g20−B_g20 = +0.0064(ExDark)/+0.0176(COCO). COCO **AP_small 0.0495→0.1958 (+296%)** — 해상도 보존이 소형 객체를 되살리는 것이 지배 메커니즘(size-AP로 확증). ExDark의 +0.0064는 CI 내이고 yolov8s에서 부호가 뒤집힌다(§3.4).
2. **1차 "VST 톤이 이득" 서사는 아티팩트였다(G-RM-1, Codex finding 1 확정).** 배포본은 이미 sqrt 톤이라 VST와 사실상 동일(톤 대비 +0.001급). 1차 R1이 F_g20보다 나아 보인 몫은 **약한 baseline(gamma2.5)과 비교**했기 때문. VST offset+soft-knee의 순효과는 무의미: **COCO에선 F_g20>R1(−0.0033), ExDark에선 R1이 근소 우위(+0.0005)** — 둘 다 noise 대역, 방향 불일치.
3. **따라서 3rd RM은 F_g20 = "binning 제거 + 기존 배포 sqrt 톤 유지"가 (동급 성능·더 낮은 HW로) 우선.** 1차 권고 R1(RM_TONE_LUT_PARAM: VST-param LUT + soft-knee)은 **과설계** — 새 LUT 없이 기존 `gamma2()` ROM을 그대로 쓰고 binning만 제거하면 되며, COCO에서 R1보다 낫고 ExDark에선 통계적 동급이다.
4. **denoise(R2)는 두 데이터셋 모두 명확한 음수** — pseudo-RAW에서 반증 재확인(real-RAW 유보는 유지).

### 3.3 1차 대비 정직성 개선

- 1차 보고 "R1 vs R0 COCO +0.0274, ExDark +0.0061"은 (i) **약한 baseline(gamma2.5)** 과 (ii) **n=150 특정 부분집합**의 합작. 전수(COCO 347/ExDark 260)·배포 baseline(B_g20) 기준으로 재산정하면 **의미 있는 순이득은 yolov8n COCO +0.018(견고)·ExDark +0.006(검출기 의존, CI 내)**, 귀속은 **전량 해상도(binning 제거)**. 부호·귀속·표본크기가 정정됨(첫 문서 상단 배너).

### 3.4 Cross-detector — binning 제거 효과의 견고성 (yolov8n vs yolov8s)

동일 셀을 yolov8s로 재평가(Codex finding 5대로 부트스트랩 OOM 회피 위해 점추정). **binning 제거 효과 = F_g20 − B_g20:**

| 검출기 | ExDark (n=260) | COCO (n=347) |
|---|---:|---:|
| yolov8n | **+0.0064** (full 우위) | **+0.0176** (full 우위) |
| yolov8s | **−0.0063** (bin 우위) | **+0.0360** (full 우위) |
| SSD(1차, R1 vs R0 근사) | 역전(bin 우위) | + (full 우위) |

**판정 (정직):** **COCO(정상조도)에서는 binning 제거가 3개 검출기 모두에서 견고하게 우위**(+0.018~+0.036, AP_small 주도). 반면 **저조도 목표도메인 ExDark에서는 검출기 의존적**이다 — yolov8n은 full-res, **yolov8s·SSD는 binning**을 선호하고 CI가 겹친다. 이는 원리적으로 정합한다: pseudo-RAW엔 binning이 회수할 실제 Poisson-Gaussian 노이즈가 없어 저조도에서 "해상도 vs SNR" 트레이드가 진짜로 균형점에 있고, 검출기 backbone(작은 v8n vs 큰 v8s의 receptive field/downsample)에 따라 저울이 기운다. **⇒ 1차의 무조건적 "binning 제거=이득" 서사를 "COCO 견고·ExDark 검출기의존/wash"로 조건화**한다.

### 3.5 Bit-exact 배포 톤 확인 (Codex finding 1 해소)

Codex가 지적한 대로 `_gamma_lut(2.0)`(round)는 배포 HLS `gamma2()`(floor(√(255·v)))와 **136/256 항목이 +1 LSB** 다르다. 정확한 `_gamma2_floor_lut()`로 결정 비교를 재실행:

| 셀(bit-exact floor 톤) | ExDark (n=260) | COCO (n=347) |
|---|---:|---:|
| B_g20f (binned, 배포 톤 정확) | 0.0906 [.078,.117] | 0.2680 [.241,.312] |
| F_g20f (full-res, 배포 톤 정확) | 0.0947 [.080,.122] | 0.2843 [.257,.331] |
| **binning 제거 효과** | **+0.0041** | **+0.0163** |

**round LUT(§3.1) 대비 차이는 mAP <0.002** (COCO +0.0176→+0.0163, ExDark +0.0064→+0.0041) — 결론(binning 제거가 COCO 견고 우위·ExDark 소폭/wave) **불변**. Codex finding 1은 **라벨 정확성 이슈였고 결론을 바꾸지 않음**을 실측 확인. 이후 "배포 톤" 대조는 bit-exact `B_g20f`를 정본으로 한다.

### 3.6 순수 해상도 vs demosaic 품질 분해 (Codex finding 2 해소 → 새 설계 통찰)

Codex finding 2("full-res vs binned는 demosaic 의미론도 바꾼다")를 board-track에서 **당겨 해소**했다. `F_g20ds` = full-res proper demosaic → **2×2 area-downsample to H/2×W/2**(binned와 동일 출력 크기, bit-exact 배포 톤). 세 셀로 이득을 분해:

| 셀 (bit-exact 배포 톤) | 출력 | ExDark (n=260) | COCO (n=347) |
|---|---|---:|---:|
| B_g20f (fused-RGGB binning) | H/2×W/2 | 0.0906 | 0.2680 |
| **F_g20ds** (proper demosaic→downsample) | H/2×W/2 | **0.0951** | 0.2707 |
| F_g20f (full-res) | H×W | 0.0947 | **0.2843** |

**분해 (binning 제거 총이득 = F_g20f − B_g20f):**

| 요인 | 격리 대비 | ExDark | COCO |
|---|---|---:|---:|
| **demosaic 품질** (proper vs fused-RGGB, 동일 크기) | F_g20ds − B_g20f | **+0.0045 (전량)** | +0.0027 (17%) |
| **픽셀 수** (H/2×W/2 → H×W) | F_g20f − F_g20ds | −0.0004 (0) | **+0.0136 (83%)** |

**핵심 통찰 (조도별로 이득의 성격이 다르다):**
1. **COCO/정상조도: 이득은 픽셀 수다.** +0.0163 중 +0.0136(83%)가 해상도 그 자체 — COCO AP_small이 F_g20ds 0.058(≈binned)→F_g20f 0.197로 뛰는 것이 직접 증거. 정상조도 소형 객체는 픽셀이 있어야 검출된다.
2. **ExDark/저조도: 이득은 demosaic 품질이고 픽셀 수는 무의미하다.** proper-demosaic→downsample(F_g20ds)이 이미 full-res(F_g20f)와 동급(0.0951 vs 0.0947)이고 둘 다 binning(0.0906)을 앞선다. 저조도에서 추가 픽셀은 노이즈 지배라 도움이 안 된다는 SNR 논리(원리 정본 §1)와 정합.
3. **⇒ 저조도 RM의 진짜 약점은 "해상도 축소"가 아니라 "fused-RGGB binning-demosaic 품질"이다.** 따라서 저조도용으로 **proper-demosaic→2×2 downsample(F_g20ds)** 이 binning의 크기/throughput 이점을 유지하면서 품질 페널티를 제거하는 **새 후보**다 — 현행 binning보다 낫고, full-res보다 싸다(출력 H/2×W/2 유지). ExDark 검출기 의존성(§3.4)도 이 관점에서 재해석된다: yolov8s/SSD가 binning을 선호한 것은 "작은 입력"이 아니라 fused-RGGB의 산물일 수 있다.

## 4. Codex 고급 리뷰 결과 및 반영

**실행 이력(정직):** 1차 Codex 리뷰(`task-mr7sq2gu`)는 21:58경 **리소스 경합으로 프로세스가 죽었다**(당시 병렬 mAP 실험들이 16코어·메모리를 점유). companion이 "running"으로 오인해 좀비 상태였고, 취소 후 mAP 작업 종료 뒤 **재실행(범위 축소)해 완료**했다. Codex 로그상 죽기 직전 조사 대상이 정확히 §1의 R0 tone confound("conclusions are stronger than the design supports")여서, 자체 재검토와 Codex의 착안점이 독립적으로 수렴했음이 확인된다.

**Codex 발견사항(우선순위순) 및 반영:**

| # | 발견 (verdict) | 반영 |
|---|---|---|
| 1 | **B_g20이 배포 톤과 bit-exact 아님 (CONFIRMED).** `_gamma_lut(2.0)`는 `np.round`, 배포 HLS `gamma2()`는 `floor(sqrt(255·v))` — **136/256 항목이 +1 LSB 차이**. "DEPLOYED" 라벨 부정확. | **정확한 `_gamma2_floor_lut()` 추가**(`rm_versions_fine.py`), bit-exact 셀 `B_g20f`/`F_g20f`로 결정 비교 **재실행**(§3.5), B_g20 라벨을 "≈deployed(±1 LSB)"로 정정. |
| 2 | **full-res vs binned는 해상도뿐 아니라 demosaic 의미론도 바꾼다 (CONFIRMED).** full은 `_demosaic_rggb16`(보간), binned는 fused RGGB 추출 — F_g20−B_g20은 "binning 제거"이지 순수 리샘플만은 아님. | **본질적 결합으로 인정**(binning=demosaic 선택 자체). "순수 해상도"가 아니라 "binning 제거(=RGGB quad 추출→보간 demosaic 전환 포함)"로 서술 정정. "full-res→downsample" 순수-해상도 분리는 board-track 추가 실험으로 이관. |
| 3 | soft-knee는 factorial에서 깨끗이 배제됨 (CONFIRMED). B_g25==ver1 lowlight 확인. | 유지. "≈old R0/R1" 근사 표기 유지. |
| 4 | size-AP 좌표 처리 방법론적으로 공정 (CONFIRMED). | 유지(§3.2 size-AP 신뢰). |
| 5 | **yolov8s 부트스트랩 실패=OOM/복잡도, 버그 아님 (PLAUSIBLE).** 로직 크래시 재현 안 됨; CSV에 nan CI. | yolov8s 교차검증은 **bootstrap=0(점추정)**으로 재실행(§3.4). paired-delta 1-pass 부트스트랩은 개선안으로 기록. |
| 6 | **C4 2-feature가 정직한 CV 안 됨 (CONFIRMED).** 스칼라만 CV, C4 그리드는 in-sample → "C4 기각" 미완결. | **nested-CV C4 추가**(`checker_versions_fine.py nested_cv_c4`): held-out J=0.838 < 최고 스칼라 dark8(0.850), Δ−0.012 → **reject-C4가 정직한 nested-CV에서도 성립**. Codex 지적으로 결론이 오히려 강화됨. |
| 7 | risk 모델 일관 적용 (CONFIRMED); CV-J·CV-risk winner 병기 권고. | 이미 §2에서 병기. |

**Codex의 사전-주장 검증(내 주장 반박 포함):**
- "F_g20 ≥ R1 everywhere"는 **부분 반박**: COCO에선 F_g20>R1이나 **ExDark에선 R1이 근소 우위**(yolov8n 0.0967 vs 0.0962, yolov8s 0.1119 vs 0.1100 — 모두 noise 대역). → §3.2·§5 서술을 "F_g20≈R1(ExDark), F_g20>R1(COCO); VST/knee 순효과 무의미"로 정정.
- "reject-C3/C4"는 C4 정직 CV 전엔 미완결이라는 지적 → finding 6으로 해소(위).
- n=347/260, 해상도 우위의 COCO-견고·ExDark-detector의존은 **CONFIRMED**.

## 5. 고도화된 전략 (refined)

| 트랙 | 1차 권고 | **고도화 권고** | 근거 |
|---|---|---|---|
| Checker | C1 dark16>0.62 | **dark10~12 + 낮은 운영점**을 승격 후보로, 실센서 재보정 전엔 dark16>0.62 유지(dark10 A/B). C3/C4는 정직 CV·nested-CV에서 기각 확정. | §2 held-out J 최적이 16 미만; §4 finding6 |
| Low-light RM | R1 VST-param LUT | **저조도 mode = F_g20ds**(proper-demosaic→2×2 downsample, 배포 톤 유지): binning의 크기/throughput 유지하며 fused-RGGB 품질 페널티 제거. 소형객체·정상 mode는 F_g20(full-res). 새 VST LUT·soft-knee 불채택. | §3.6 저조도 이득=demosaic 품질(픽셀수 무의미); §3.4 검출기 의존 |
| Denoise RM | R2 유보 | 유보 유지(real-RAW에서만) | §3.2 두 데이터셋 음수 |

**핵심 정정:** 1차의 "R1(VST-param LUT) 3rd RM 채택 + small-obj +50% 무조건 우위" → **"F_g20(binning 제거, 톤 무변경)로 단순화. 이득은 COCO/정상조도에서 견고하고 소형객체 주도이나, 저조도(ExDark)에서는 검출기 의존적 wash."** VST-param LUT과 soft-knee는 순효과가 없어 불채택 — 배포 파이프라인은 이미 원리적 sqrt(VST계열) 톤을 쓰고 있었다.

**board-track (G-HW-1 및 Codex finding 2):**
1. F_g20 = 기존 low-light RM에서 2×2 binning 제거 + gain2.0/`gamma2()` 유지. csynth로 (a) binning line-buffer 제거 BRAM 감소, (b) full-res 처리량(H×W vs H/2×W/2) latency/throughput 트레이드 정량화 — "HW 감소" 주장 마감.
2. **순수 해상도 vs demosaic 분리(Codex finding 2):** "full-res→H/2×W/2 downsample" 대조군으로 검출 이득이 "픽셀 수"에서 오는지 "보간 demosaic 품질"에서 오는지 분리.
3. **real-RAW 재검증:** ExDark 검출기 의존성/wash은 pseudo-RAW 노이즈 부재의 산물일 수 있음 — 보드 실센서에서 binning +6dB가 물리적으로 존재할 때 재측정(F_g20 vs binned).

## 6. 한계 (정직)

1. **pseudo-RAW 노이즈 부재** 지속 — binning의 +6dB·denoise 이득이 과소평가. F_g20의 "해상도 우위" 결론은 real-RAW에서 binning SNR 이득과 재경쟁 필요(§3.2 R2 유보와 동일 취지).
2. **n=575도 부트스트랩 CI가 넓다**(ExDark ±0.02). 부호·순위는 안정적이나 소수 델타(VST/knee)는 noise 대역 — 그래서 "순효과 0~음수"로 보수적 기술.
3. **단일 detector(yolov8n)** 전수 — yolov8s/SSD 교차검증은 1차(§SSD)에 있고 F_g20은 그 결론(해상도 우위)과 정합하나, F_g20 자체의 교차검증은 board-track 항목.
4. **Codex 절(§4) 완료 대기** — 자체 재검토로 주요 갭은 이미 해소, Codex는 교차검증.

## 7. 산출물 (refinement)

- 코드: `tools/checker_versions_fine.py`(+`nested_cv_c4`), `tools/rm_versions_fine.py`(+`_gamma2_floor_lut`, `B_g20f`/`F_g20f`), `tools/eval_map_rmversions_fine.py`(+부트스트랩 CI)
- CSV(checker): `results/checker_fine_2026-07-05.csv`
- CSV(RM factorial n=150): `results/map_rmfine_{coco,exdark}_yolov8n_2026-07-05.csv`
- CSV(RM 전수 yolov8n): `results/map_rmfine575_{coco,exdark}_yolov8n_2026-07-05.csv`
- CSV(RM cross-detector yolov8s): `results/map_rmfine575_{coco,exdark}_yolov8s_2026-07-05.csv`
- CSV(bit-exact 배포톤): `results/map_rmfine_deployexact_{coco,exdark}_yolov8n_2026-07-05.csv`
- CSV(순수해상도 분해): `results/map_rmfine_pureres_{coco,exdark}_yolov8n_2026-07-05.csv`
- 본 문서: `results/principled-v3-refinement-2026-07-05.md` (1차 정정: `principled-comparison-2026-07-05.md` 상단 배너)
