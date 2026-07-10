<!--
=============================================================================
File   : isppipeline/hls/results/checker-status-2026-07-10.md
Date   : 2026-07-10 KST
Function: checker 모듈의 현행 상태 정본(single source of truth). 2026-07-04~10
          동안 산재한 캠페인(principled-v3, SOTA 강화 #1~#7, LRT/타일/시간층/
          적응τ)의 결론을 하나로 종합 — 배포 vs 권장 운영점, 채택/기각 확정,
          다음 관문(LOD real-RAW)을 한 장으로 고정. 세부 근거는 각 캠페인 문서.
Sources: checker-principles-2026-07-05.md, checker-principled-versions-2026-07-05.md,
         checker-sota-review-2026-07-09.md, checker-sota-strategy-2026-07-09.md,
         checker-lrt-2026-07-09.md, checker-tile-probe-2026-07-10.md,
         checker-temporal-2026-07-10.md, checker-adaptive-tau-2026-07-10.md,
         src/dfxisp_accel.cpp (배포 구현)
=============================================================================
-->
# Checker 현행 상태 (정본, 2026-07-10)

> 이 문서는 checker의 "지금 어디까지 왔고, 무엇이 최선이며, 다음은 무엇인가"를
> 한 장으로 고정한다. 개별 실험의 수치·유도는 위 Sources의 각 문서에 있고,
> 여기서는 **결정만** 종합한다. 목표 매핑: checker는 목표 2(상황에 맞는 모듈
> 전환)의 "조건 판단" 축이다(RESEARCH.md §1).

## 1. 운영점 — 배포 vs 권장

| | 규칙 | recall | FT | J | HW |
|---|---|---|---|---|---|
| **배포(현행 HLS)** | C0: dark50 ratio > 0.80 | 0.918 | 0.125 | 0.793 | 1 비교기 + 1 카운터 |
| **권장(검증됨, 미배포)** | C1: dark16 ratio > 0.62 + Schmitt δ=2%p | 0.936 | 0.089 | 0.847 | **동일 RTL** (레지스터값·PCT만 변경) |

- **C1이 C0를 전 지표에서 지배**하고 HW 변경이 0이다(`dark_pixel_threshold`는
  AXI-lite 런타임 레지스터 — 값만 다르게 쓰면 되고, `DARK_RATIO_PCT`만
  80→62 컴파일 상수 변경).
- **배포는 보류 중**: 근거가 pseudo-RAW(COCO/ExDark) + 단일센서(SonyNOD)라,
  dark16의 **절대 임계값**은 실센서(LOD)에서 재보정이 필요하다. 상대 결론
  ("낮은 dark 임계가 우월")은 견고해 유지 전망. LOD real-RAW 재평가 후
  C1(또는 재보정된 τ)을 정식 배포한다(§4).

## 2. 강화안 채택/기각 확정 (SOTA 검토 7항목)

`checker-sota-strategy-2026-07-09.md`의 7개 강화안을 fold-분산 마진 기준으로
정직하게 판정한 결과:

| # | 강화안 | 판정 | 근거 |
|---|---|---|---|
| #1 | 센서 적응 임계 τ(exp,gain,blc) | **채택(Path A)** | τ=BLC+k·σ_read(g) 유도·셀프테스트 통과. 드라이버가 AXI-lite 레지스터에 기록 → RTL 변경 0. 실데이터 검증만 PENDING. `checker-adaptive-tau-2026-07-10.md` |
| #2 | 히스토그램 우도비(LRT) | **기각** | 학습형 LRT가 dark-ratio를 재발견, held-out J 0.835<C1 0.847. dark16이 정보 소진. `checker-lrt-2026-07-09.md` |
| #3 | 순차 변화탐지(CUSUM/SPRT) | **기각(Schmitt 채택)** | 측정 지터(σ≈0.002)에서 CUSUM/SPRT가 Schmitt 대비 무이득, CUSUM≡SPRT. Schmitt(δ=2%p)+옵션 K-of-N 채택. 보드 지터 시 재검토. `checker-temporal-2026-07-10.md` |
| #4 | 평가·라벨 재정의(오라클) | **대기(최우선)** | 잔존오차가 라벨 아티팩트임이 #2·#5에서 반복 확인 → 오라클 라벨이 핵심. LOD/PASCAL real-RAW 필요 |
| #5 | 공간 타일 미터링 | **기각** | 게이트 PASS나 nested-CV J +0.016<fold-std. ExDark miss와 COCO FT의 공간 시그니처가 반대라 상쇄. `checker-tile-probe-2026-07-10.md` |
| #6 | 확률 캘리브레이션 | **채택(가능)** | ECE isotonic 0.033(<0.05). 부수 성과: p(H1\|dark16=0.62)=0.516 → **C1 임계가 사후확률 중립점**임을 독립 확인. `checker-temporal-2026-07-10.md` |
| #7 | 3-모드 이산화 | **게이트 대기** | #4 오라클 조도축 결과가 착수 게이트. 지금 착수 금지 |

**한 줄 요약:** checker는 **정보축(#2)·공간축(#5)·시간축(#3)에서 이미 포화**
됐다 — 잔존오차는 알고리즘이 아니라 **라벨(#4)** 문제다. 남은 실질 레버는
**#1(실센서 적응 τ) + #4(오라클 라벨)**뿐이며, 둘 다 **LOD real-RAW**에 걸려
있다.

## 3. 지금 코드에 반영된 것 / 안 된 것

- **반영됨:** 완화 BLC(저조도 모듈, 배포 완료), Schmitt 히스테리시스 설계
  (스케줄러), demosaic bilinear 정합 수정(SW eval, 2026-07-09).
- **미반영(의도적):** C1 운영점(dark16>0.62) — LOD 재보정 대기. 적응 τ Path A —
  실센서 EXIF 대기. 이들은 **런타임 레지스터/드라이버 사안이라 HW 재합성
  불필요**, LOD 결과 확정 즉시 반영 가능.

## 4. 다음 관문 (순서)

1. **LOD real-RAW(Sony .ARW) + PASCAL RAW 확보** → `aodraw_adapter.py`로 변환.
2. **#4 오라클 라벨 재정의** — dual-arm 렌더 → 검출 델타로 프레임 정답 재정의,
   잔존오차의 라벨-아티팩트 비율 정량화. C_miss/C_FA 재추정.
3. **#1 적응 τ 스트라텀 검증** — LOD를 ISO로 층화, 고정 vs 적응 τ recall/FT.
4. **C1(또는 재보정 τ) 정식 배포** — `DARK_RATIO_PCT` + 드라이버 레지스터값
   갱신, golden 재생성 + `make verify` bit-exact 재확인.

**차단 요인:** LOD/PASCAL 데이터(다운로드 대기) + GPU(mAP). 그 전까지 checker의
알고리즘 축 작업은 완료 상태로 동결한다.
