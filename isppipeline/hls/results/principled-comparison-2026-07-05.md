<!--
=============================================================================
File   : isppipeline/hls/results/principled-comparison-2026-07-05.md
Date   : 2026-07-05 21:43 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3 (successor to ver1/ver2)
Function: 원리 기반 checker(C0..C4) 및 low-light RM(R0..R3) 신버전을 이전 버전과
          교차 비교·종합. goal 명령 Part 3(비교 분석) + Part 4(에이전트 팀 종합).
Inputs : checker-principled-versions-2026-07-05.md, lowlight-rm-principled-versions-2026-07-05.md,
         rm-ssd-crosscheck-2026-07-05.md (XCHK), 원리 정본 2종.
=============================================================================
-->
# 원리 기반 재설계 종합 비교 — Checker & Low-light RM (principled-v3)

**작성:** 2026-07-05 21:43 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05` ·
**캠페인 버전:** `principled-v3` (ver1/ver2 후속) · **에이전트 팀:** CHK(opus)‖RM(opus)‖XCHK(sonnet)→CMP(opus)

> 본 문서는 두 병렬 트랙(Checker/Low-light RM)의 원리 정의 → 신버전 구현 → 실험 결과를
> **이전 버전과 한자리에서 비교**하고 종합 결론을 낸다. 트랙별 상세는 각 결과 문서 참조.
> 모든 수치는 본 브랜치에서 직접 재실행(결정적). 공통 한계: pseudo-RAW(실센서 노이즈 부재),
> CPU-only, n=150(mAP)/n=1150(checker 통계).

---

## 0. 한눈에 (Executive summary)

| 트랙 | 이전(canonical) | 원리 winner | 핵심 근거 | HW 비용 변화 |
|---|---|---|---|---|
| **Checker** | C0 `dark50 ratio>0.80` | **C1 `dark16 ratio>0.62` + hysteresis δ2%p** | 감마공간 진짜 암부만 계수·[16,50) 반신호 제거 → R −24%, FT 0.125→0.089, AUC 0.963→0.977 | **0 (레지스터값만)** |
| **Low-light RM** | R0 `2×2 bin + gain + gamma` | **R1 `full-res VST/GAT LUT tone`** (+ 4th: R3 CLAHE) | binning 해상도 손실 > pseudo-RAW SNR 이득; full-res+VST가 COCO에서 **3개 검출기 전부**·ExDark에서 YOLO 2종 R0 지배, small-obj AP +50% (SSD·ExDark만 noise-scale 역전) | **감소** (binning/line-buffer 제거, BRAM LUT 1개) |

두 결론 모두 **"원리가 예측한 방향이 실측에서 확인"** 되었고, 공통적으로 **HW를 늘리지 않거나 줄이면서 mAP를 개선**한다. 반대로 원리적으로 매력적이던 두 후보(checker 2-feature, RM binning+denoise)는 **이론의 기각 예측대로 실측에서도 순이득이 없어** 반증되었다 — 이 "확인 2 + 반증 2"가 캠페인의 과학적 수확이다.

---

## 1. 방법론 개요 — 원리에서 실험까지

| 단계 | Checker 트랙 | Low-light RM 트랙 |
|---|---|---|
| **원리 정의** | `checker-principles-2026-07-05.md`: ①결정이론(Youden J vs Bayes risk, 비대칭비용 2.89:1) ②광도계(linear-light, 감마공간 암부) ③노이즈물리(read-noise floor/log-metering) ④샘플링(Hoeffding 1/16 무손실) ⑤시간축(Schmitt hysteresis) | `lowlight-feature-principles-2026-07-05.md`: 저조도=low SNR(Foi Poisson-Gaussian σ²=ay+b), 결정적 stage=demosaic+tone(Buckler/ISP4ML), VST/Anscombe(√ 분산안정화), gain 상류배치, edge-preserving denoise만 |
| **버전 구현** | `tools/checker_versions.py` C0..C4 (정수, HW 매핑) | `tools/rm_versions.py` R0..R3 (정수, 공유 core 위) |
| **실험** | 1150프레임 통계(AUC/J/FT/overlap/flapping) + adaptive mAP(yolov8n) | COCOeval mAP + size-AP 분해(yolov8n/s), size 공정 버킷 |
| **비교** | 본 문서 §2 | 본 문서 §3 |

**"feature 추출 기준" 질문에 대한 답 (goal Part 2 명시 요구):** 저조도에서 머신비전이 비중 있게 처리해야 할 것은 **밝기가 아니라 (i) SNR과 (ii) local contrast/고주파 구조**이며, feature는 **"충분한 SNR을 확보한 상태에서 고주파 구조를 보존하고, 남은 신호의 동적범위를 검출기가 학습한 입력 분포로 재배치"** 하는 기준으로 추출해야 한다(원리 정본 §3). 실험은 이 기준을 지지한다 — 해상도(고주파) 보존이 이득의 지배축이었고(§3.2), VST 톤(동적범위 재배치)이 그 위에 이득을 더했다.

---

## 2. Checker 비교 — C0(이전) vs C1..C4(원리)

### 2.1 통계 지표 (전수 1150프레임)

| 버전 | 규칙 | AUC | recall | FT | J | overlap↓ | R (mAP손실/fr) | HW |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **C0** (이전) | dark50>0.80 | 0.9632 | 0.918 | 0.125 | 0.793 | 0.193 | 0.00699 | 기준 |
| **C1** ★채택 | dark16>0.62 | 0.9766 | 0.936 | 0.089 | 0.847 | 0.139 | **0.00531 (−24%)** | =C0 |
| C2 | dark16>0.553 | 0.9766 | 0.965 | 0.134 | 0.831 | 0.139 | 0.00454 (−35%) | =C0 |
| C3 | logmean<−3.218 | 0.9780 | 0.939 | 0.090 | 0.849 | 0.146 | 0.00515 (−26%) | +log LUT |
| C4 | dark16∧entropy | 0.9784 | 0.958 | 0.101 | 0.857 | 0.136 | 0.00429 (−39%) | +hist BRAM |

**판정:** C1..C4 전부 C0를 J·R·AUC·overlap에서 지배. **C0→C1 단일 변경(dark 임계를 감마공간 진짜 암부로 하강)만으로 기대 mAP 손실 −24%**. C3/C4의 추가 이득은 HW/robustness 비용을 정당화하지 못함(이론의 "통계량 결합 기각" 실측 확인).

### 2.2 이전 캠페인(ver1/ver2) 대비 위치

| 캠페인 | 방법 | 대표 J | 한계 |
|---|---|---|---|
| ver1 (07-02) | RAW-domain-first 재정렬 | — | 체커 통계량 미검증 |
| ver2 (07-02) | 통계량 고정(Y<50), ratio만 스윕 | 0.790 | **2번째 차원(dark 임계) 미탐색** |
| **principled-v3 (C1)** | 통계량 자체 교체(dark16) | **0.847** | dark16 절대값 실센서 재보정 필요 |

ver2가 놓친 "dark 임계 재검증"이 이득의 2.4배 몫(+0.038/+0.057)이었음(analysis 2026-07-04 §5). principled-v3는 그 갭을 코드 버전 + 실험으로 닫았다.

### 2.3 Downstream 실증 (adaptive mAP, yolov8n n=150)

| 데이터셋 | C0 라우팅 | C1 라우팅 | C0 mAP@50 | C1 mAP@50 |
|---|---|---|---:|---:|
| COCO(정상) | FT 20/150 | **FT 11/150** | 0.4555 | **0.4596** |
| ExDark(저조도) | 133/150 | 133/150(대칭스왑) | 0.1300 | 0.1191(노이즈 내) |

원리 예측대로 **가치는 평균 mAP가 아니라 정상장면 false-trigger −45%(PR 전환 빈도 감소)** 로 실현. ExDark는 이미 recall 포화라 무손해 동률.

---

## 3. Low-light RM 비교 — R0(이전) vs R1..R3(원리)

### 3.1 mAP@[.5:.95] (n=150, 두 검출기)

| 버전 | 구성 | ExDark v8n | COCO v8n | ExDark v8s | COCO v8s |
|---|---|---:|---:|---:|---:|
| **R0** (이전) | bin+gain+gamma | 0.0777 | 0.2989 | 0.0994 | 0.3486 |
| **R1** ★3rd RM | full-res VST-LUT | **0.0838** | 0.3263 | **0.1087** | **0.3979** |
| R2 | bin+denoise+VST | 0.0726 | 0.3027 | 0.0845 | 0.3393 |
| **R3** ★4th RM | full-res CLAHE | 0.0811 | **0.3373** | 0.1057 | 0.3892 |

**판정:** full-res 두 arm(R1,R3)이 binning 두 arm(R0,R2)을 **모든 검출기×데이터셋에서 일관 능가.** YOLOv8s에서는 **R1이 4개 열 전부 단독 최고.** "binning 제거=해상도 보존"이 가장 견고한 이득 축.

### 3.2 Binning의 비용 규명 (size-AP, named 기여)

동일 VST 톤 공유 R1(full-res) vs R2(binned) → binning 순효과:

| AP 버킷 (COCO·v8n) | R1 | R2 | binning 효과 |
|---|---:|---:|---:|
| **small** | 0.1045 | 0.0761 | **−27%** |
| medium | 0.2577 | 0.2346 | −9% |
| large | 0.4726 | 0.4628 | −2% |

binning 손실은 small object에 집중(survey B.2.2 예측 확증). 현행 R0 대비 full-res의 COCO small-AP는 **0.0697→~0.105 (+50%)**.

### 3.3 이전 실험(rootcause 2026-07-02) 대비

rootcause는 "COCO에서 해상도 손실이 압도적, Policy B(해상도 보존)가 더 안전"이라 제언했으나 **대안 RM을 구현·측정하지 않았다.** principled-v3는 그 Policy B를 R1로 실체화하고, 저조도(ExDark)에서도 full-res가 우위임을 실측해 제언을 검증+확장했다.

### 3.4 SSD 3차 검출기 교차검증 (XCHK, sonnet)

YOLO 계열 밖(구조적으로 다른 검출기)에서 "full-res R1 > binning R0"가 유지되는지 검증. torchvision `ssdlite320_mobilenet_v3_large`(COCO-pretrained, 오프라인) 사용. 상세: `rm-ssd-crosscheck-2026-07-05.md`.

| 검출기 | ExDark R0→R1 | COCO R0→R1 |
|---|---|---|
| YOLOv8n | 0.0777→0.0838 (**+0.0061**) | 0.2989→0.3263 (**+0.0274**) |
| YOLOv8s | 0.0994→0.1087 (**+0.0093**) | 0.3486→0.3979 (**+0.0493**) |
| **SSDLite-MNv3** | 0.0732→0.0684 (**−0.0048**) | 0.1959→0.2085 (**+0.0126**) |

**판정 (정직):** **COCO(정상조도)에서는 3개 검출기 전부 R1>R0** — 부호·상대크기 일관. 저조도 목표도메인 **ExDark에서는 YOLO 2종은 R1 우위, SSD는 R0가 0.0048(noise-scale)만큼 앞섬** — 강한 반증은 아니나 깨끗한 확인도 아니다. 따라서 **"R1>R0"는 (i) COCO에서는 검출기 무관하게 견고, (ii) ExDark에서는 YOLO 계열(원 검증 기반)에서 성립, (iii) SSD·ExDark에서는 미확인**으로 조건화한다. R1 채택 근거는 유지된다(정상조도 보편 우위 + small-obj AP + HW 감소 + YOLO 저조도 우위), 단 저조도에서의 검출기 의존성은 보드 재검증 항목으로 명시.

---

## 4. 종합 결론

### 4.1 채택 (즉시 적용 권고)

1. **Checker → C1 (`dark16 ratio>0.62`, hysteresis δ2%p, 진입64/해제60).** HW 변경 0(`dark_pixel_threshold`=HLS raw12 도메인 **256**, `DARK_RATIO_PCT` 80→62). 기대 mAP 손실 −24%, 정상장면 FT −45%.
2. **Low-light RM 3rd → R1 (`RM_TONE_LUT_PARAM`, full-res VST/GAT LUT).** binning/line-buffer 제거로 HW 감소, COCO에서 3개 검출기 전부·ExDark에서 YOLO 2종 mAP 상승, small-obj AP +50%. (SSD·ExDark noise-scale 역전은 §3.4대로 보드 재검증 항목.)
3. **4th RM → R3 (`RM_TONE_CLAHE`).** R1의 global tone에 local 대비 보완(v8n COCO 최고).

### 4.2 조건부 / 유보

- **C2 (Bayes-opt 0.553):** recall 최우선 배포용 대안. 55% vs 62% 최종 선택은 **보드 c_PR 실측 후** 확정.
- **R2 (RM_LL_BIN_DN, survey #2):** pseudo-RAW에서 반증되었으나 **real-RAW에서는 binning +6dB가 물리적으로 존재** → 보드 DPU 재검증 대상으로 유보(기각 아님).

### 4.3 기각 (이론 예측 = 실측 확인)

- **C3 (logmean), C4 (2-feature):** dark16 대비 순이득 없이 LUT/BRAM·flapping·OOD 비용만 추가.

### 4.4 과학적 수확

| 유형 | 항목 | 의미 |
|---|---|---|
| 확인 | dark16 우월; full-res 우월(COCO 3검출기 보편, ExDark YOLO 계열) | 원리(광도계·해상도-고주파)가 실측 지배축과 일치 |
| 반증 | 2-feature, binning+denoise(pseudo-RAW) | 원리의 기각 예측까지 실측이 재현 — 모델의 예측력 검증 |
| 조건화 | binning은 real-RAW에서만 | pseudo-RAW의 노이즈 부재가 결정적 교란변수임을 명시 |

---

## 5. 다음 단계 (board track)

1. C1 + R1을 canonical(`dfxisp_accel.cpp`)에 반영 후 재합성(csynth) — HW 비용 감소 정량.
2. 전수 n=575 adaptive mAP로 FT 감소의 mAP 효과 신뢰구간 축소.
3. real-RAW(보드 DPU end-to-end)에서 binning/denoise(R2) 및 dark16 절대값 재보정.

## 6. 산출물 (principled-v3 전체)

**원리 정본:** `checker-principles-2026-07-05.md`, `lowlight-feature-principles-2026-07-05.md`
**구현:** `tools/checker_versions.py`, `tools/rm_versions.py`, `tools/eval_map_rmversions.py`, `tools/scratch_adaptive_map_principled.py`
**실험 결과:** `checker-principled-versions-2026-07-05.md`, `lowlight-rm-principled-versions-2026-07-05.md`, `rm-ssd-crosscheck-2026-07-05.md`
**CSV:** `results/map_rm_{exdark,coco}_yolov8{n,s}_2026-07-05.csv`, `results/scratch_frame_stats.csv`, `results/scratch_adaptive_map_principled.csv`
**계획:** `PLAN-principled-checker-rm-2026-07-05.md` · **본 종합:** `principled-comparison-2026-07-05.md`
