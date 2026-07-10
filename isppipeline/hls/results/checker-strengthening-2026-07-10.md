<!--
=============================================================================
File   : isppipeline/hls/results/checker-strengthening-2026-07-10.md
Date   : 2026-07-10 KST
Function: checker SOTA 강화의 전체 서사를 하나로 종합 — SOTA 리뷰(왜 이
          레버들인가) + 7항목 실행전략 + 각 캠페인의 실측 결과·판정·재현을
          한 문서에 담는다. 2026-07-09~10에 분산됐던 review/strategy/lrt/
          tile/temporal/adaptive-tau 6개 문서를 대체(원문은 git 이력).
          빠른 결정 요약은 checker-status-2026-07-10.md.
Sources: (대체된 원문, git 이력) checker-sota-review/strategy-2026-07-09,
         checker-lrt-2026-07-09, checker-tile-probe/temporal/adaptive-tau-2026-07-10
Repro   : 각 §3 하위절의 명령 참조. 도구는 tools/checker_*.py (결정적).
=============================================================================
-->
# Checker SOTA 강화 — 종합 (2026-07-10)

> checker를 SOTA 기준으로 검토하고 7개 강화안을 실험한 전 과정을 한 장에
> 종합한다. **빠른 결정 요약**은 `checker-status-2026-07-10.md`, 여기서는
> **근거와 실측**을 담는다. 목표 매핑: checker는 목표 2(조건별 모듈 전환)의
> 판단 축이다(RESEARCH.md §1).

## 1. SOTA 리뷰 — 어디가 한계이고 무엇을 강화해야 하나

현행 checker(`checker_select_mode`, 1-pass dark-ratio)는 **단일 프레임·고전
결정이론 축에서는 이미 포화**다: 5원리 정본화(결정이론·광도계·노이즈물리·
표본론·시간축, `checker-principles-2026-07-05.md`)로 후보 C0~C4를 1150프레임
전수 비교했고 AUC 0.978에서 잔존오차는 튜닝 불가한 라벨/정보이론 한계였다.

따라서 진짜 레버는 임계값 재튜닝이 아니라 **축을 바꾸는 것**이다 — SOTA
문헌(task-driven ISP, EMVA1288 SNR, Wald SPRT/CUSUM, calibration)에서 7개
강화안을 도출했다(§2).

## 2. 7개 강화안 — 실행전략과 판정

공통 규율: 모든 후보는 C4를 기각시킨 것과 같은 **nested-CV + fold-분산 마진
(±0.03~0.04)** 을 통과해야 채택. 비교 기준선 C1(dark16>0.62, held-out J 0.847).

| # | 강화안 | 접근 | HW | 판정 | 근거(§3) |
|---|---|---|---|---|---|
| #1 | 센서 적응 임계 τ(exp,gain,blc) | τ=BLC+k·σ_read(g), EXIF 기반 | 레지스터(RTL 0) | **채택(Path A)** | §3.4 |
| #2 | 히스토그램 우도비(LRT) | 256-bin 학습형 선형 LRT | ROM+MAC | **기각** | §3.1 |
| #3 | 순차 변화탐지(CUSUM/SPRT) | 우도비 누산, ARL 보정 | 누산기1 | **기각(Schmitt)** | §3.3 |
| #4 | 평가·라벨 재정의(오라클) | dual-arm 렌더 → 검출델타 라벨 | (평가) | **대기(최우선)** | §4 |
| #5 | 공간 타일 미터링 | 4×4 타일 dark 카운터 | 카운터16 | **기각** | §3.2 |
| #6 | 확률 캘리브레이션 | isotonic/Platt → ECE | LUT1 | **채택** | §3.3 |
| #7 | 3-모드 이산화 | normal/low/extreme-low | RM 슬롯+ | **게이트 대기** | §4 |

**한 줄:** 정보축(#2)·공간축(#5)·시간축(#3)에서 모두 포화 — 잔존오차는
알고리즘이 아니라 **라벨(#4)** 문제다. 남은 실질 레버는 **#1·#4**뿐이고
둘 다 **LOD real-RAW**에 걸려 있다.

## 3. 캠페인 실측

### 3.1 #2 히스토그램 LRT — 기각
256-bin(이미 계산됨) 위 학습형 선형 LRT(ridge+평활, int8 양자화) + coarse
log16/log8 변형을 nested 5×3-fold CV로 평가. **held-out J: LRT-256 0.824 /
log16 0.829 / log8 0.835 — 모두 C1(0.847) 미달.** 학습된 가중치가 dark-ratio
형태를 재발견(저 bin +, 고 bin −), oof AUC도 dark16과 동률(0.977). 잔존오차
회수 ≈0(순이득 0), **공통 병목 78장**이 그대로 — 라벨 아티팩트 확증.
→ dark16이 히스토그램의 선형 정보를 이미 소진. `python3 checker_lrt.py --analyze`.

### 3.2 #5 공간 타일 미터링 — 기각
4×4 타일별 dark16. **게이트 PASS**: C1 오차 88장 중 86%가 공간구조,
bimodal(밝은+어두운 타일 공존)이 오차에서 **5.17배 enriched**. 그러나
전수 nested-CV에서 최선 규칙(dark16 OR max_tile) **J 0.863±0.036 = C1 대비
+0.016 < fold-std**. 핵심: ExDark miss(밝은 피사체+어두운 배경)와 COCO
FT(그라디언트)의 **공간 시그니처가 반대**라 한쪽을 살리면 다른 쪽을 재트리거.
→ #4 오라클 후 조건부 재평가. `python3 checker_tile_probe.py`.

### 3.3 #3 순차 시간층 + #6 캘리브레이션
5개 시간층(단일/Schmitt/K-of-N/CUSUM/SPRT)을 측정 지터(σ median 0.0023/p95
0.0055)로 만든 시퀀스(steady/ramp/flicker/step)에서 비교. **측정 지터가
δ=0.02 밴드의 ~1/10이라 CUSUM/SPRT가 Schmitt 대비 무이득**(ramp만 K-of-N이
근소 우위). ν=δ/2에서 **CUSUM≡SPRT bit-identical**(Page=반복SPRT 확인).
→ **Schmitt(δ=2%p)+옵션 K-of-N 채택**, 누산기 레지스터 불필요. 보드 실지터
측정 후 재검토. **#6:** ECE raw 0.162 → **isotonic 0.033**(<0.05 통과).
부수: **p(H1|dark16=0.62)=0.516** — C1 임계가 사후확률 중립점(C1 독립 정당화).
`python3 checker_temporal.py`.

### 3.4 #1 센서 적응 임계 τ — 채택(Path A)
저조도 = 노이즈 플로어 상 신호 부족으로 정의: **τ(g)=BLC(g)+k·σ_read,DN(g)**,
σ_read,DN(g)=σ_read,e·g/K (EMVA1288, Rose k≈5). 노출 정규화: 판정을 상대노출
r=(s·g)/(s0·g0)로 스케일(또는 히스토그램 정수 시프트)해 (s·g) 재스케일에
불변. 셀프테스트 4종 PASS(gain 단조·노출불변·k스윕·EXIF폴백).
**HW = Path A(권장): `dark_pixel_threshold`가 이미 AXI-lite 런타임
레지스터라 드라이버가 센서 설정 변경마다 τ를 계산해 기록 → RTL 변경 0.**
실데이터 검증(LOD를 ISO로 층화, 고정 vs 적응 τ)은 PENDING.
`python3 checker_adaptive_tau.py --selftest`.

## 4. 남은 실질 과제 (LOD real-RAW 대기)

- **#4 오라클 라벨(최우선):** 프레임을 두 arm(normal/lowlight)으로 렌더 →
  검출 델타로 "정답 모드" 재정의, |Δ|<ε는 don't-care. 잔존오차(공통 78장)의
  라벨-아티팩트 비율 정량화 + C_miss/C_FA 재추정. #2·#5의 기각이 라벨 때문
  이었으므로, 오라클 라벨 후 두 강화안 1회 조건부 재평가.
- **#1 적응 τ 실검증:** LOD ISO 스트라텀별 고정 vs 적응 τ recall/FT.
- **#7 3-모드:** #4 조도축에서 "저조도 arm으로도 붕괴하는 lux 구간"이
  확인될 때만 착수(그 전 금지 — 프록시 라벨 위 경계는 재작업).

**차단:** LOD/PASCAL 데이터(다운로드 대기) + GPU(mAP). 그 전까지 checker
알고리즘 축 작업은 완료로 동결.
