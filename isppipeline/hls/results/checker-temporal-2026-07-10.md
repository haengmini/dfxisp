<!--
=============================================================================
File   : isppipeline/hls/results/checker-temporal-2026-07-10.md
Date   : 2026-07-10 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign: checker-sota #3 (sequential temporal layer) + #6 (probability calibration)
Function: 강화전략 #3 실행 결과 — 체커 점수 스트림 위의 5개 시간층
          (단일임계 / Schmitt / K-of-N / CUSUM / SPRT)을 측정된 프레임
          지터로 만든 합성 시퀀스에서 동일 오전환 예산 하에 비교. CUSUM/SPRT
          이 Schmitt+K-of-N을 실제로 이기는지 정량화. + #6 확률 캘리브레이션
          (isotonic/Platt, 5-fold held-out ECE). 결론: 측정 지터(~0.002)에서
          CUSUM/SPRT는 단순 시간층을 이기지 못함 → Schmitt(+선택적 K-of-N)
          충분, CUSUM은 보드 실지터 측정 후 재검토. ECE는 isotonic 0.033.
Sources: checker-sota-strategy-2026-07-09.md (#3 설계/수용·기각 기준, #6)
         tools/checker_temporal.py (신규, 본 캠페인)
         tools/checker_stat_sweep.py (flap_sim/load 재사용)
         results/scratch_frame_stats.csv (1150프레임, ph16_dark16_std 지터)
         tools/scheduler_sim.py (기존 스케줄러 정책 시뮬 선행)
Repro  : cd isppipeline/hls/tools
         python3 checker_temporal.py        # ~1.5s, 결정적(seed 고정)
=============================================================================
-->
# 순차 변화탐지 시간층 + 확률 캘리브레이션 (강화전략 #3 + #6, 2026-07-10)

**작성:** 2026-07-10 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05`

> 사전 등록된 수용 기준(strategy #3): 동일 오전환율에서 Schmitt+K-of-N 대비
> 탐지지연 ≥30% 단축 + steady flap 0 유지 → **채택**. 기각 조항: 지터 σ가
> 작아(측정 0.002 수준) Schmitt만으로 이미 flap≈0이고 지연 이득이 미미하면
> "Schmitt 충분, CUSUM은 실센서 지터 측정 후 재검토"로 기록.
>
> **결과: 기각 조항 발동.** 측정 지터(median 0.00226 / p95 0.00548)에서
> CUSUM/SPRT는 더 단순한 Schmitt·K-of-N을 **어느 지표에서도 지배하지 못한다**
> (step 지연은 Schmitt와 동률 0, ramp 지연은 K-of-N이 더 빠름, flicker 억제는
> Schmitt가 더 좋음). 게다가 CUSUM과 SPRT는 슬랙을 맞추면 **비트 동일**한
> 검정임을 실증(Page-CUSUM = 반복-SPRT). **최종 채택은 보드 실지터 없이는
> 확정 불가** — 본 결과는 합성 지터 상한이며, 보드 비디오 지터가 크게 나오면
> 재평가한다.

## 1. 설계 요약

- **점수 스트림.** 배포 운영점 C1(`dark16 > 0.62`)의 per-frame dark16 비율
  s_t. 임계 t=0.62, Schmitt 반폭 δ=0.02.
- **합성 시퀀스(측정 지터 기반).** base는 실제 경계 근방 프레임
  (`|dark16−0.62|≤0.03`, n=40, [0.5947, 0.6499])에서 추출, 여기에 측정
  1/16-phase 지터 σ(ph16_dark16_std: median 0.00226 / p95 0.00548)의 i.i.d.
  가우시안을 더한다. 4개 시나리오: **steady**(정적, 이상 전환 0),
  **ramp**(bright→dark 선형, 완만 크로싱, 이상 1), **flicker**(진폭 0.015 <
  δ의 주기 조명 진동, 이상 0), **step**(급변 t∓0.06, 이상 1).
- **5개 시간층.** (a) 단일임계 (b) Schmitt 히스테리시스(enter t+δ / leave
  t−δ) (c) K-of-N 다수결(N=5) (d) 양측 Page CUSUM
  (e) Wald SPRT(반복형). 슬랙(drift) ν는 히스테리시스 δ의 순차판으로 잡아
  ν=δ/2=0.01 (CUSUM·SPRT 공통).
- **동일 오전환 예산.** 목표 ARL을 "오전환 ≤ 1회 / 10분 @ 30fps = 1/18000
  프레임"으로 고정. **worst-case(장면이 임계 t에 정확히 걸린 정적 스트림)**
  18000프레임에서 오전환 ≤ 1이 되는 **가장 민감한(가장 빠른) 설정**을 각
  검출기에 부여 — 이렇게 해야 파레토 비교가 "동일 오전환율에서의 지연"이
  된다. worst-case=base=t는 ARL의 정의점(오전환 압력 최대)이라 랜덤 base 1개에
  의존하던 초기 캘리브(비대표적)를 대체했다.
- **비대칭.** miss가 costlier(C_miss=0.1118 vs C_FA=0.0387, 비 2.889)이므로
  진입(NORMAL→LOW)은 낮은 경계, 해제는 h_leave = h_enter × 2.889. SPRT도
  동일 비로 b_leave = b_enter × 2.889.
- **구현.** `tools/checker_temporal.py`, numpy 단독, seed 고정(결정적).
  `checker_stat_sweep.load`/`flap_sim` 아이디어 재사용.

## 2. 파레토 결과 (전부 실행 출력, 결정적)

지표: FS/100fr steady(정적 근경계 장면 오전환), flicker sw/100fr(진동 억제
실패), ramp/step 탐지지연(프레임, 이벤트 대비), det%(탐지율).

**σ = 0.00226 (median)**

| detector | FS/100fr steady | flicker sw/100fr | ramp delay | ramp det% | step delay | step det% |
|---|---|---|---|---|---|---|
| single | 2.958 | 25.000 | 0.83 | 0.955 | 0.00 | 1.000 |
| schmitt | 0.000 | 0.172 | 24.10 | 1.000 | 0.00 | 1.000 |
| kofn (5/5) | 0.035 | 2.755 | 6.52 | 1.000 | 4.00 | 1.000 |
| cusum | 0.000 | 23.238 | 12.82 | 1.000 | 0.00 | 1.000 |
| sprt | 0.000 | 23.238 | 12.82 | 1.000 | 0.00 | 1.000 |

calibrated: kofn `k=5,n=5` · cusum `nu=0.01, h_enter=0.001, h_leave=0.0029` ·
sprt `sep=0.02, b_enter=3.931, b_leave=11.355 (eff_h=0.001)`

**σ = 0.00548 (p95)**

| detector | FS/100fr steady | flicker sw/100fr | ramp delay | ramp det% | step delay | step det% |
|---|---|---|---|---|---|---|
| single | 7.067 | 26.383 | 1.02 | 0.995 | 0.00 | 1.000 |
| schmitt | 0.000 | 3.610 | 18.88 | 1.000 | 0.00 | 1.000 |
| kofn (5/5) | 0.092 | 2.785 | 9.52 | 0.993 | 4.00 | 1.000 |
| cusum | 0.007 | 6.482 | 12.18 | 0.993 | 0.00 | 1.000 |
| sprt | 0.007 | 6.482 | 12.18 | 0.993 | 0.00 | 1.000 |

calibrated: kofn `k=5,n=5` · cusum `nu=0.01, h_enter=0.005, h_leave=0.0144` ·
sprt `sep=0.02, b_enter=3.335, b_leave=9.634 (eff_h=0.005)`

### 판독 (정직하게)

1. **단일임계는 탈락.** 근경계 정적 장면에서 오전환 3~7회/100fr, flicker
   25회/100fr — 어떤 시간층이든 필요함을 재확인. (현 배포 C1은 임계 자체이며
   스케줄러 시간층은 계획 단계라는 전제와 정합.)
2. **step에서는 CUSUM/SPRT가 Schmitt를 못 이긴다.** 급변은 즉시 밴드를
   벗어나므로 single·schmitt·cusum·sprt 모두 지연 0. CUSUM/SPRT의 순차 누산이
   더해주는 것이 **없다**. (K-of-N만 5표 채우느라 지연 4.)
3. **ramp(완만 크로싱)에서만 순차/투표층이 Schmitt보다 빠르다** — 단,
   **가장 단순한 K-of-N(6.52/9.52)이 CUSUM/SPRT(12.82/12.18)를 더 이긴다.**
   즉 "완만 전이에서 빠른 탐지"라는 유일한 이점조차 principled 순차검정이
   아니라 5-of-5 다수결이 더 잘한다. CUSUM/SPRT가 느린 이유: 슬랙 ν=0.01이
   완만한 ramp 초반 잔차를 상쇄해 누산 시작이 늦다.
4. **flicker(진폭 0.015 < δ=0.02) 억제는 Schmitt가 최고**(0.17/3.61).
   CUSUM/SPRT는 median에서 오히려 23.2회 — 캘리브가 at-threshold 예산만
   맞추다 보니 슬랙 ν=0.01 < 진동진폭 0.015가 되어 진동 피크마다 누산이
   임계를 넘는다. Schmitt의 고정 밴드(0.02 > 0.015)가 구조적으로 우월.
5. **CUSUM ≡ SPRT.** 슬랙을 ν=δ/2로 맞추면 SPRT 누산 L_t = k·g_t^{CUSUM}
   (k=sep/σ², 경계 b=k·h)로 **정확히 같은 검정**이다. 두 행이 비트 동일하게
   나온 것은 이 등가성(Page-CUSUM = 반복-SPRT)의 실증이지 버그가 아니다.
   "SPRT가 CUSUM보다 낫다"는 여지는 이 문제 구조에 없다.

**요약 지배관계:** step·steady에서 Schmitt = CUSUM/SPRT(둘 다 최적), ramp에서
K-of-N > CUSUM/SPRT > Schmitt, flicker에서 Schmitt > K-of-N > CUSUM/SPRT.
**CUSUM/SPRT는 어느 축에서도 파레토 정점이 아니다.** 사전 등록 수용 기준
("Schmitt 대비 지연 30%↓")은 CUSUM/SPRT가 아니라 **K-of-N**이 달성한다.

## 3. 확률 캘리브레이션 (#6): 5-fold held-out ECE

dark16 점수를 P(H1=LOW_LIGHT | dark16)로 보내는 단조 사상을 isotonic(PAV) 및
Platt로 적합, 5-fold held-out ECE(equal-width 10-bin) 보고.

| map | ECE mean±std |
|---|---|
| raw (min–max 정규화) | 0.1615±0.0233 |
| **isotonic (PAV)** | **0.0327±0.0020** |
| Platt (1-D logistic) | 0.0347±0.0073 |

- **isotonic ECE 0.033 < 0.05** — strategy #6 수용 기준(ECE<0.05) 통과.
  raw 점수(0.162)는 확률로 해석 불가하나, 단조 보정 후 잘 정렬된 확률이 된다.
- 전체데이터 isotonic 사상(HW는 이 곡선을 256-entry LUT로 샘플):

  ```
  dark16: 0.009 0.132 0.256 0.380 0.504 0.628 0.752 0.876 1.000
  p(H1) : 0.000 0.000 0.000 0.021 0.143 0.516 0.818 0.970 1.000
  ```
  **p(H1 | dark16=0.62) = 0.516** — 배포 임계가 확률축의 ≈0.5 등가점에
  거의 정확히 놓인다(운영점 t=0.62가 사후확률 중립점과 일치, C1 선택의
  독립적 사후 근거).
- **기대효용 전환으로의 일반화.** 보정 확률 p_t가 있으면 전환 결정은
  `E[ΔRisk] = p·C_miss − (1−p)·C_FA`가 부호를 바꾸고 **기대 체류프레임에
  곱한 이득이 c_PR을 넘을 때만** 전환하는 renewal-reward 규칙으로 통일된다.
  히스테리시스 밴드 δ와 CUSUM 슬랙 ν는 이 규칙의 특수해다(밴드 = c_PR을
  흡수하는 무전환 영역). 즉 §2의 5개 시간층은 모두 "보정확률 위의 기대효용
  임계"의 근사이며, c_PR(=PR 재구성 비용, 보드 측정 전 미지)이 들어와야
  경계가 원리적으로 고정된다.

## 4. 판정 및 다음 액션

**기각(측정 지터 기준) — 사전 등록 기각 조항대로 기록.** 측정 지터가 작아
(σ≈0.002, δ=0.02의 1/10) Schmitt만으로 steady/step/flicker가 이미 최적이고,
순차검정의 유일한 이점(ramp 지연)마저 더 단순한 K-of-N이 더 잘한다. CUSUM과
SPRT는 같은 검정이며 파레토 정점이 아니다.

**권고 시간층: Schmitt(δ=0.02) 단독, 완만 전이 대응이 필요하면 K-of-N(5/5)
추가.** CUSUM/SPRT는 **채택하지 않는다(현 단계).**

**보드 없이는 최종 확정 불가 — 명시.** 본 결과는 **합성 지터**(1/16-phase
proxy) 위의 상한이다. 보드 비디오의 실제 per-frame 지터가 크게(예: 5~10×)
나오면 Schmitt 고정 밴드가 오전환하기 시작하고, 그때 잡음을 아는 순차누산의
이점이 살아날 수 있다. **최종 채택/기각은 보드 실지터 측정 후로 연기**한다
(strategy #3의 "실검증은 보드 비디오로 연기" 조항). AODRaw는 스틸이라
시간축 실검증 불가 — EXIF 노출 램프 합성은 근사일 뿐임을 재확인.

## 5. 승자의 HW 비용

| 시간층 | 추가 상태 | 산술 | 비고 |
|---|---|---|---|
| single | 없음 | 비교기 1 | 현 배포 |
| **Schmitt (권고)** | **mode FF 1개** | 비교기 2(t±δ) | δ는 상수/AXI-lite |
| K-of-N (선택) | N-bit shift-reg + popcount | 비교기 2 | N=5 → 5-bit |
| CUSUM | **누산 레지스터 1개** | 가·감산 1, 비교기 1 | ν·h는 레지스터 |
| SPRT | 누산 레지스터 1개 | 곱 1(k) + 가감 | CUSUM과 동일 검정 |

Schmitt = mode FF 1개(+비교기 1 추가)로 끝. CUSUM/SPRT는 누산 레지스터 1개
추가지만 §2가 보인 대로 **이득이 없어 그 1 레지스터를 지불할 이유가 없다.**
`checker_select_mode`(src/dfxisp_accel.cpp) 인터페이스는 이전 모드 입력 1개만
추가하면 Schmitt까지 수용(스트리밍 계약 유지). 확률 LUT(#6)는 채택 시
256-entry BRAM 1개, isotonic 곡선을 굽는다 — #2 LRT 채택 시 무료에 가깝다.

## 6. 산출물

- `tools/checker_temporal.py` — 캠페인 코드(재현 헤더 참조, 결정적, numpy 단독).
- 본 문서.

**재현:**
```
cd isppipeline/hls/tools
python3 checker_temporal.py        # ~1.5s, 고정 seed(20260710)
```
