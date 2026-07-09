<!--
=============================================================================
File   : isppipeline/hls/results/checker-tile-probe-2026-07-10.md
Date   : 2026-07-10 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign: checker-sota #5 (공간/타일 메터링)
Function: 강화전략 #5(spatial/tile 메터링) 실행 결과 — C1(global dark16>0.62)의
          잔존오차 88장이 backlit/spotlight 같은 '공간 구조' 프레임인지 4x4
          타일 dark16으로 검증. 값싼 게이트(에러부분집합)는 통과(구조화 86%,
          bimodal 에러 x5.17 부화)했으나, 전체 1150장 정직한 5-fold CV에서
          3개 결합규칙 모두 held-out J 개선이 fold-분산 마진 이내 → 기각.
Sources: checker-sota-strategy-2026-07-09.md (#5 설계/수용기준)
         tools/checker_tile_probe.py (신규, 본 캠페인)
         tools/checker_stat_sweep.py (load/kfold_cv/eval_at 재사용)
         results/scratch_frame_stats.csv (dark16 등 프레임 통계)
         data/{coco_val,exdark_val}/raw_bin/*.bin (프레임별 RAW)
         checker-lrt-2026-07-09.md (#2, 공통 병목 78장 근거)
Repro  : cd isppipeline/hls/tools
         python3 checker_tile_probe.py       # ~37s, 결정적(seed=0)
=============================================================================
-->
# 공간(타일) dark 메터링 프로브 결과 (강화전략 #5, 2026-07-10)

**작성:** 2026-07-10 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05`

> 사전 등록된 수용 기준(strategy #5): held-out J > C1(0.847) + fold-분산
> 마진(±0.03~0.04), 그리고 global recall/FT 미손상.
> 결과: **값싼 게이트는 통과**(에러 88장 중 86% 공간 구조화, bimodal 에러
> x5.17 부화) — backlit/spotlight 가설은 **실재 신호가 있다**. 그러나 전체
> 1150장 정직한 5-fold CV에서 최고 결합규칙조차 J=0.863±0.036으로 C1 대비
> **+0.016 (fold-std 1개 이내, 마진 미달)** → **기각.** 이는 C4(2-feature)/
> #2(LRT)를 기각시킨 것과 같은 정직성 기준의 결과다.

---

## 1. 대상 · C1 잔존오차

- C1 = `dark16 > 0.62` (global dark-pixel 비율, dark16 = raw>>8 < 16 픽셀 분율).
- N=1150 (COCO/label0 575 + ExDark/label1 575). C1 in-sample recall=0.936
  FT=0.089 **J=0.847**.
- C1 오차 **88장** = ExDark **미스 37** + COCO **오발 51**.

## 2. 타일 메터링 (HW 충실)

프레임별 RAW를 CSV의 (W,H)로 reshape → **4×4 타일** 분할, 타일당 dark16 비율
16개 산출. 타일 인덱스는 HW를 미러: `ty = min(y // (H//4), 3)`,
`tx = min(x // (W//4), 3)`. `H//4`,`W//4`는 HW 블록이 프레임당 1회 래치하는
상수이고 `min()` 클램프로 비정수배 해상도를 처리 — 픽셀당 곱셈 없음.
(count-가중 타일 평균 = global dark16, 정합성 확인.)

## 3. 값싼 게이트 (go/no-go, 오차부분집합 88장)

"공간 구조화" = (타일 spread = max−min ≥ 0.50) **또는** bimodal(≥3 매우어두운
타일 AND ≥3 매우밝은 타일). "globally borderline" = |dark16−0.62| ≤ 0.08.

```
Error frames: 88
  spatially structured (spread>=0.50 OR bimodal>=3/3): 76 (86.4%)
  bimodal (>=3 dark AND >=3 bright tiles):             24 (27.3%)
  globally borderline (|dark16-0.62|<=0.08):           40 (45.5%)
  borderline AND NOT structured (pure global-border):   3 (3.4%)

Enrichment of spatial structure (errors vs correct):
  spread   : err median=0.813 p75=0.951 | correct median=0.559 p75=0.754
  tile std : err median=0.247 p75=0.322 | correct median=0.166 p75=0.233
  P[structured] err=0.864 correct=0.570 enrichment x1.52
  P[bimodal]    err=0.273 correct=0.053 enrichment x5.17

  misses (ExDark):   N=37 structured=37 bimodal=23 borderline=18
  false-trig (COCO): N=51 structured=39 bimodal=1  borderline=22

GATE decision: structured fraction of errors = 0.864 (threshold 0.333)
               errors enriched vs correct    = True
  => GATE PASS (escalate to full CV)
```

**게이트 판정: 통과.** 오차의 86%가 공간 구조화, bimodal은 correct 대비
**x5.17 부화** → 가설(어두운 배경 속 밝은 피사체 / 밝은 장면 속 어두운 영역)에
실재 신호가 있음. 특기할 비대칭:
- **ExDark 미스 37/37 전부 구조화, 23장 bimodal** — 진짜 backlit/spotlight
  저조도(밝은 피사체가 global dark16을 0.62 아래로 끌어내림).
- **COCO 오발은 spread 기준 39/51 구조화지만 bimodal은 단 1장** — 밝은
  피사체가 아니라 어두운 그라디언트 장면(코너만 밝음). 두 오차 유형의 공간
  서명이 **정반대**여서, 미스를 살리는 규칙(타일 어두움 강조)은 오발을 늘리고
  그 역도 성립 → 단일 타일 규칙으로 동시 교정 불가라는 첫 경고.

## 4. 전체 1150장 정직한 5-fold CV (seed=0, C1 baseline J=0.847)

동일 프로토콜(J-max 임계를 4/5 학습, 1/5 평가; 2-feature는 nested 그리드)로
비교. baseline global dark16의 CV J는 0.838(in-sample 0.847과의 차이는
정직-CV의 정상적 축소).

| 규칙 | recall | FT | held-out J |
|---|---|---|---|
| baseline global dark16 (C1 계열) | 0.918±0.008 | 0.080±0.038 | **0.838** |
| (a) center-weighted 타일 평균(내부2×2 w=2) | 0.918±0.020 | 0.091±0.039 | 0.827 |
| (b) M-of-16 (#타일 ratio>0.62, M*≈8.3) | 0.940±0.016 | 0.102±0.027 | 0.838 |
| (c) dark16 **OR** max_tile>tb | 0.957±0.006 | 0.094±0.035 | **0.863±0.036** |
| (c) dark16 **OR** median_tile>tb | 0.928±0.015 | 0.067±0.032 | 0.860±0.045 |
| (c) dark16 **AND** min_tile>tb | 0.917±0.011 | 0.083±0.031 | 0.834±0.038 |

최고는 `dark16 OR max_tile` (J=**0.863±0.036**): recall 0.918→0.957로 ExDark
미스를 실제로 회수하나 FT도 0.080→0.094로 동반 상승. C1(0.847) 대비 **+0.016
— fold-std(±0.036) 1개 이내**, 사전 등록 마진(0.847+0.03~0.04 ≈ 0.877~0.887)
**미달**. `median_tile` OR도 0.860±0.045로 동일 결론.

## 5. 판정: 기각 (REJECT)

- **수용 기준 미충족.** held-out J 최댓값 0.863이 C1 0.847을 마진(≥+0.03)만큼
  넘지 못하고, 개선폭(+0.016)이 fold-분산(±0.036)보다 작아 잡음과 구별 불가.
- **구조적 이유.** 게이트가 드러낸 두 오차 유형(bimodal ExDark 미스 vs
  그라디언트 COCO 오발)은 공간 서명이 반대라, 타일 극단값을 쓰는 어떤 단일
  결합규칙도 한쪽을 살리면 다른 쪽을 해쳐 J가 상쇄된다. `OR max_tile`이
  recall을 올려도 FT가 따라 올라 J 순증이 마진 미만인 이유.
- **#2(LRT)와 정합.** 히스토그램 LRT가 남긴 '공통 병목 ~78장'(라벨 아티팩트
  후보)과 본 오차집합이 겹친다 — 이 프레임들은 global이든 타일이든 현행 프록시
  라벨(COCO=normal/ExDark=lowlight)로는 분리 불가능한 성분이 지배적이다.
- **결론.** 잔존오차는 공간 구조가 **관찰**되긴 하나(게이트 통과), 그 구조가
  현행 라벨 하에서 held-out 분리력으로 **전환되지 않는다.** 타일 메터링을
  체커 개선책으로 **기각**한다.

## 6. HW 비용 노트 (기각 — 미도입)

채택되지 않았으므로 비용은 발생하지 않는다. 참고로 도입 시 예상 비용은
16개 타일 dark 카운터(각 log2(픽셀수)비트) + 프레임 경계에서의 결합기
(OR/AND 또는 M-of-16 비교기)로, 1-pass 정수 스트리밍 계약은 만족했을 것이나
(타일 인덱스는 곱셈 없는 시프트/클램프) J 이득이 없어 불필요.

**조건부 재평가.** #4 오라클 라벨 확보 후, 공통 병목 78장의 라벨이 정정되면
ExDark backlit 미스(37/37 구조화·bimodal 23)에 한해 타일 신호가 실이득으로
전환될 여지가 있어 1회 재검토 대상. 현행 프록시 라벨 하에서는 기각 확정.

## 7. 재현

```
cd isppipeline/hls/tools
python3 checker_tile_probe.py       # ~37s, 결정적(seed=0)
```

산출물: `tools/checker_tile_probe.py` (신규), 본 문서 (신규). 공유 파일 무변경.
