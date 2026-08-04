<!--
=============================================================================
File   : isppipeline/hls/results/checker-oracle-label-gate2-2026-07-20.md
Date   : 2026-07-20 KST (데스크톱, CPU-only)
Function: checker-status-2026-07-10.md §4 관문 2(오라클 라벨 재정의, 강화안
          #4) 실행 기록. Shuffle_split(642, LOD 321+PASCAL 321) 프레임을
          normal/lowlight 두 arm으로 렌더(배포 BLC=2, 양 모드 동일) →
          YOLOv8n 검출 델타(F1)로 프레임별 "정답 모드"를 재정의하고,
          C0/C1/adaptive-tau의 naive 데이터셋 라벨(LOD=전부 야간,
          PASCAL=전부 주간) 대비 잔존오차의 라벨-아티팩트 비율, 오라클 기준
          recall/FT, C_miss/C_FA 재추정을 산출한다. 이로써
          checker-status-2026-07-10.md §4의 남은 유일한 관문을 닫는다.
Sources: checker-strengthening-2026-07-10.md §4 (#4 정의: dual-arm 렌더 →
          검출델타 라벨, |Δ|<ε don't-care), checker-c1-deploy-2026-07-20.md
          (C1 배포, PASCAL FT 44.2% 실측 재확인 기준), lod-pascal-isp-
          simulation-2026-07-15.md (동일 dual-arm 렌더 소재, aggregate mAP만
          있었음 -- 이번에 프레임별로 재실행), tools/checker_temporal.py
          (isotonic p(H1|dark16) 재사용, 강화안 #6)
Repro   : tools/checker_oracle_label.py --manifest results/shuffle_split_2026-07-15.csv
          --out results/oracle_label_shuffle_2026-07-20.csv (렌더+검출, 642장,
          CPU 전용 약 63분/6.0s·frame) 후
          tools/checker_oracle_analysis.py --oracle <위 CSV>
          --manifest results/shuffle_split_2026-07-15.csv --out <이 문서>
=============================================================================
-->
# Checker 관문 2 — 오라클 라벨 재정의 (2026-07-20)

## 0. 결론부터

`checker-status-2026-07-10.md` §4의 남은 유일한 관문(#4 오라클 라벨)을
실행했다. Shuffle_split 642장 각각을 normal/lowlight 두 arm으로 렌더(배포
BLC=2)하고 YOLOv8n으로 프레임별 F1(IoU≥0.5, conf≥0.25, class-aware)을 측정,
Δ=F1_lowlight−F1_normal로 프레임별 "정답 모드"를 재정의했다(|Δ|≤0.05는
don't-care).

1. **잔존오차의 대부분은 라벨 아티팩트다 — 가설이 확증됐다.** C1이 naive
   라벨(LOD=전부 야간/PASCAL=전부 주간)과 어긋나는 154프레임 중 **89.6%**
   (artifact-confirmed 9.7% + don't-care 79.9%)는 검출 품질 관점에서 실제
   오류가 아니다. 진짜 오류(오라클도 C1과 불일치)는 **10.4%(16장)**뿐.
2. **하지만 dark16은 "정답 모드"(오라클) 자체를 잘 못 맞춘다.** naive
   라벨에서는 C1의 Youden J=0.847(구 배포값)이었지만, 오라클 라벨(don't-care
   제외 141장)에서는 J=0.008 — 사실상 무정보. dark16 임계로 오라클-최적
   임계를 다시 스윕해도 J=0.120(dark16>0.89)에 그친다. **dark16은 "장면이
   야간이냐"는 잘 예측하지만 "이 프레임에서 lowlight 처리가 실제로 검출을
   개선하느냐"는 거의 예측하지 못한다** — 두 질문이 다르다는 것 자체가 이번
   실험의 핵심 발견.
3. **그럼에도 C1의 배포 임계(0.62)는 사후확률 중립점 성질을 오라클
   기준에서도 유지한다.** naive 라벨 기준 p(H1|dark16=0.62)=0.099(구 강화안
   #6 측정치 0.516과는 다른 데이터셋·라벨이라 직접 비교 불가)였으나,
   **오라클 라벨 기준으로는 p(H1|dark16=0.62)=0.510** — 강화안 #6이 애초에
   프록시 라벨로 측정했던 "≈0.5 중립점"이 실 RAW·오라클 라벨에서도 거의
   그대로 재현됐다. 함의 C_miss/C_FA: naive 9.08(실질적으로 미스 비용이
   FA보다 9배 크다는, 부정확한 함의) → **오라클 0.96(거의 대칭)**.
4. **결론: C1 재조정은 불필요하다.** 판별력(J)은 낮지만 임계 위치(비용
   대칭성)는 정확하다 — dark16 하나로는 "이 프레임에서 lowlight가
   도움이 되는가"를 잘 못 맞히지만, 맞히지 못하는 방향이 편향돼 있지
   않다(비용 중립). 강화안 #2·#5(LRT/공간 타일)의 재검토 조건이었던 "오라클
   후 조건부 재평가"는, 이 낮은 J(0.008~0.120)를 보면 **정보가 실제로
   소진됐다는 원래 판정을 오히려 강화**한다 — dark16 스칼라 자체가 오라클
   문제에 대해 약한 신호이므로 LRT/타일도 같은 스칼라의 파생 정보만 가진 한
   개선 여지가 낮다(§5 한계 참고, 재실험은 안 함).

## 1. 방법

### 1.1 프레임별 오라클 라벨
- 대상: Shuffle_split 642장(LOD 321 + PASCAL 321, 07-15 캠페인 매니페스트
  그대로 재사용).
- 렌더: `baseline_isp_pipeline.run_arm(..., "normal")` /
  `low_light_isp_pipeline.run_arm(..., "lowlight")`, `blc_offset=None`
  기본값 → **배포 BLC=2**(양 모드 동일, 2026-07-20 재보정값,
  `blc-recalibration-deploy-2026-07-20.md`). 07-15 캠페인은 BLC 스윕
  {16,1,2}의 aggregate mAP만 냈고 프레임별 결과는 없었다 — 이번 실행이
  "재료를 상당 부분 제공"의 실제 소재화.
- 검출: YOLOv8n(`model/detectors/yolo/yolov8n.pt`), `predict(imgsz=640,
  conf=0.25, iou=0.45)`.
- 매칭: GT(YOLO 정규화 좌표, COCO-80 id)와 예측을 class-aware greedy
  매칭(신뢰도 내림차순, IoU≥0.5)으로 TP/FP/FN 산출, F1=2TP/(2TP+FP+FN)
  (GT·예측 모두 0이면 F1=1.0으로 정의 — 두 arm이 자명하게 동일).
- 정규화 좌표라 원본 해상도(normal)와 절반 해상도(lowlight, 2×2 binning)
  라벨을 재조정 없이 그대로 비교 가능.
- Δ = F1_lowlight − F1_normal. **|Δ| ≤ ε(=0.05)는 don't-care** — 강화안
  #4 원문 정의(`checker-strengthening-2026-07-10.md` §4) 그대로.
- 실행: CPU 전용(이 데스크톱은 CUDA 드라이버 불일치로 GPU 미가용, RTX 5060
  노트북 없이 진행) — normal 렌더 ~3.8초/프레임(20~24MP bilinear demosaic),
  lowlight ~0.3초, YOLO 추론 ~0.25초×2 → 실측 평균 5.92초/프레임, 총
  63분(642프레임, 전수 완주, 오류 0).

### 1.2 분석
- **라벨 아티팩트 비율**: 각 checker(C0/C1/adaptive-tau)의 naive-gt 대비
  잔존오차(verdict≠naive gt) 프레임을 오라클 라벨로 3분류 —
  artifact-confirmed(오라클==verdict, 즉 naive 라벨이 틀렸던 것),
  don't-care(오라클이 무판정, arm 선택이 검출에 무관), genuine
  error(오라클도 verdict와 불일치, 진짜 오류).
- **오라클 기준 recall/FT**: don't-care 제외, 결정된 141장만으로 재계산.
- **C_miss/C_FA 재추정**: `checker_temporal.py`의 isotonic(PAV) 보정을
  재사용해 p(H1|dark16=0.62)를 naive/오라클 각각 산출, Bayes-risk
  사후확률-중립점 조건 p(H1|t*)=C_FA/(C_FA+C_miss)로 역산
  (C_miss/C_FA=(1−p)/p).
- **Youden-J 재스윕**: 오라클 라벨(결정된 141장)의 dark16 값 전체를 후보
  임계로 스윕해 최적 J와 그 임계를 구함.

## 2. 결과

### 2.1 don't-care 비율
n=642, **don't-care 501장(78.0%)**, 결정된 프레임 141장(22.0%) — 대부분의
프레임에서 normal/lowlight 어느 쪽을 골라도 YOLOv8n 검출 품질에 큰 차이가
없다(작은 GT 수, 강건한 장면, 혹은 둘 다 완전히 miss).

### 2.2 오라클 vs naive 라벨 일치
결정된 141장 중 오라클이 naive gt_lowlight와 일치하는 비율 **54.6%(77/141)**
— 거의 동전 던지기 수준. 세부: LOD 59.3%(51/86, naive=야간), PASCAL
47.3%(26/55, naive=주간). 즉 naive 라벨은 "이 프레임에서 실제로 어느 arm이
검출에 유리한가"를 결정된 프레임 절반가량에서 틀린다 — dataset-provenance
기반 라벨이 프레임 단위 진실과 체계적으로 어긋난다는 것을 직접 확인.

### 2.3 라벨 아티팩트 비율 (checker별 naive-gt 잔존오차 분해)

| checker | 잔존오차(verdict≠naive gt) | artifact-confirmed | don't-care | genuine error |
|---|---|---|---|---|
| C0 | 300 | 29 (9.7%) | 245 (81.7%) | 26 (8.7%) |
| C1 | 154 | 15 (9.7%) | 123 (79.9%) | **16 (10.4%)** |
| adaptive-tau | 131 | 10 (7.6%) | 107 (81.7%) | 14 (10.7%) |

세 checker 모두 **잔존오차의 ~90%가 라벨 아티팩트(artifact-confirmed +
don't-care)**이고 진짜 오류는 ~9~11%에 불과 — 강화안 #4가 §4에서 세운
가설("잔존오차는 라벨 문제")이 실측으로 확증됐다.

### 2.4 오라클 기준 recall / false-trigger (don't-care 제외, n=141)

| checker | recall(오라클) | n | FT(오라클) | n | J(오라클) | recall(naive, 참고) | FT(naive, 참고) |
|---|---|---|---|---|---|---|---|
| C0 | 0.963 | 77/80 | 0.951 | 58/61 | 0.012 | 0.991 | 0.925 |
| C1 | 0.762 | 61/80 | 0.754 | 46/61 | 0.008 | 0.963 | 0.442 |
| adaptive-tau | 0.762 | 61/80 | 0.803 | 49/61 | **-0.041** | 0.988 | 0.396 |

naive 라벨 기준 J(C1=0.847 등, `checker-status-2026-07-10.md` §1)와
오라클 기준 J(0.008~-0.041)가 **완전히 다른 스케일**이다. naive-J는 "장면
provenance 분류" 성능, 오라클-J는 "프레임별 실제 검출 개선 예측" 성능 —
dark16은 전자에서는 강하지만(J 0.847) 후자에서는 거의 무정보(J≈0)다.
adaptive-tau가 결정된 141장에서 J<0(무작위보다 나쁨)인 것은, τ가 노출/ISO로
정규화한 "장면이 실측 저조도냐"를 잘 맞히도록 설계됐을 뿐 "이 프레임에서
lowlight arm이 검출에 유리한가"에 최적화된 적이 없기 때문 — 설계 목표와
오라클 질문의 불일치이지 τ 구현의 결함이 아니다.

### 2.5 C_miss/C_FA 재추정 (dark16>0.62 사후확률-중립점 조건)

| | p(H1\|dark16=0.62) | 함의 C_miss/C_FA |
|---|---|---|
| naive 라벨 (이번 Shuffle_split 실측) | 0.099 | 9.077 |
| 오라클 라벨 (don't-care 제외) | **0.510** | **0.960** |

참고: `checker-strengthening-2026-07-10.md` §3.3의 0.516은 이번과 다른
데이터셋(프록시 라벨 기반 원 SOTA 캠페인)에서 측정된 값이라 naive-gt 0.099와
직접 비교할 수 없다 — 하지만 **오라클 라벨로 재측정하니 0.510으로, 그
프록시 캠페인이 원래 찾았던 "≈0.5 중립점"과 사실상 같은 값이 나왔다**. 이는
① 프록시 라벨 기반 원 계산이 우연이 아니었고, ② naive 데이터셋 라벨(0.099)
쪽이 오히려 이번 실측에서의 아티팩트였음을 보여준다 — C1 임계 0.62는
비용-대칭(C_miss≈C_FA) 가정 하에서 정당했고, 이는 라벨을 오라클로
바꿔도 유지된다.

### 2.6 오라클 라벨 기준 Youden-J-최적 dark16 임계
- 오라클-최적: dark16 > **0.8922**, J=**0.120**(recall=0.562, FT=0.443)
- 배포 C1(dark16>0.62)의 오라클 기준 J=0.008

오라클-최적 임계로 옮겨도 J가 0.12에 그쳐 여전히 약한 판별력이다 — dark16
단일 스칼라가 "프레임별 실제 검출 개선" 문제 자체에 정보가 부족하다는 뜻이지,
0.62라는 특정 값이 잘못됐다는 뜻이 아니다. §0-4의 결론(재조정 불필요) 근거.

## 3. 재현성 확인

- `oracle_label_shuffle_2026-07-20.csv`의 C1 naive-gt FT(0.442, §2.4)가
  `checker-c1-deploy-2026-07-20.md` §4의 PASCAL_split 실측(142/321=44.2%)과
  정합 — 렌더/조인 파이프라인이 기존 실측과 독립적으로 같은 숫자를 재현,
  방법론 검증으로 사용.
- 642/642 프레임 전수 완주, 렌더/검출 오류 0건(누락 프레임 없음).

## 4. 한계

- **단일 모델(YOLOv8n)·단일 run**, GPU 미가용으로 CPU 전용 실행(교차 모델
  검증은 여전히 별도 open item, `pascalraw-false-trigger-campaign` 메모리
  참고).
- **F1 기반 오라클 지표의 양자화**: GT box 수가 적은 프레임(특히 n_gt=1~2)은
  F1이 {0, 0.5, 1.0} 등 성긴 값만 가능 — ε=0.05는 사실상 "정확히 같은 값이면
  don't-care"에 가깝다. 연속적 지표(예: 신뢰도 가중 IoU 합)로 바꾸면
  don't-care 비율(78.0%)이 달라질 수 있으나, artifact-confirmed 비율(라벨
  아티팩트 확증)은 F1이 정확히 반대로 갈린 프레임만 세므로 지표 선택에
  상대적으로 덜 민감할 것으로 예상 — 미검증.
- **Shuffle_split은 실 배포 유병률을 반영하지 않음**: LOD/PASCAL 각 321장
  균등 매칭(N-matched, `build_matched_splits.py` 설계 의도) — 실제 배포에서
  야간:주간 비율이 다르면 §2.5의 p(H1|dark16=0.62)와 함의 C_miss/C_FA도
  달라진다. 이번 값은 "N-matched 인공 유병률" 기준.
- **PASCAL_split은 PASCALRAW 4,259장 중 ISO-stratified 샘플(321)** — 전수가
  아님(`lod-pascal-isp-simulation-2026-07-15.md` §8.4와 동일한 한계 승계).
- ε(=0.05)은 강화안 #4 원문의 "|Δ|<ε" 정의를 그대로 따랐을 뿐 별도 최적화는
  하지 않음 — 민감도 스윕은 미실시.

## 5. 다음 단계 (참고, 이번 관문 실행 범위 밖)

- LRT(#2)/공간 타일(#5) "오라클 후 조건부 재평가"는 §2.4의 낮은 오라클-J를
  볼 때 낮은 우선순위로 재확인 — dark16이 오라클 문제 자체에 약한 신호라면
  같은 raw 통계의 파생물인 LRT/타일도 크게 나아지기 어려울 가능성이 높다.
  실제 재평가는 하지 않았음(원 판정 유지, 필요 시 별도 캠페인).
  **#7 3-모드 이산화**의 착수 게이트("저조도 arm으로도 붕괴하는 lux 구간"
  확인)는 이번 실험 범위 밖 — 여전히 미착수.
- csynth/cosim 재실행(BLC 재보정 건과 묶어서, HW golden 재생성 전 1회) —
  이번 관문과 무관하게 여전히 open.
- YOLOv8s/SSDLite 교차 모델 검증 — 여전히 open(§4 한계).
