<!--
=============================================================================
File    : adaptive-tau-improvement-2026-07-20.md
Date    : 2026-07-20 KST
Function: Path-A sensor-adaptive dark-threshold scaffold 개선 실험 3종
          (sensor c fitting, floor-only/r<=1, joint tau/cutoff calibration).
Sources : tools/experiment_adaptive_tau_improvement.py,
          tools/checker_adaptive_tau.py (import/수정 없이 수식 대조),
          results/adaptive_tau_pascalraw_results.csv,
          results/adaptive_tau_sonynod_2026-07-13.csv,
          results/adaptive-tau-improvement-metrics-2026-07-20.csv,
          results/adaptive-tau-improvement-frames-2026-07-20.csv,
          results/adaptive-tau-improvement-run-2026-07-20.json,
          results/adaptive_tau_histograms-2026-07-20.npz
=============================================================================
-->
# Path-A adaptive tau 개선 실험 (2026-07-20)

## 0. 결론부터

**정직하게 일반화 가능한 결과만 보면, ISO [800,1600) 역전은 고치지 못했다.**
가장 나은 비누설(non-leaking) 변형은 `tau_floor_only`였고, 전체 recall 98.44%,
FT 37.54%, Youden J 0.6090으로 C1의 96.26% / 41.82% / 0.5444보다 낫다.
holdout에서도 J 0.6125로 C1 0.5674보다 높았다. 그러나 문제 구간 FT는
현 adaptive와 똑같이 **96.4%(27/28)** 이며 C1 32.1%(9/28)보다 훨씬 나쁘다.
SonyNOD recall도 이 구간에서는 66.7%(2/3)로 C1과 같아, “FT를 C1 이하로
낮추면서 recall을 잃지 않는다”는 핵심 조건을 만족하지 않는다.

`tau8=c*g`를 센서별로 맞추면 `c_Nikon=0.0`, `c_Sony=4.0`이 선택되어 train과
holdout 모두 recall 100%, FT 0%가 나온다. **이는 개선 증거가 아니라 명백한
sensor/corpus-label leakage**다. Nikon corpus는 전부 daylight, Sony corpus는
전부 night이므로 센서 ID 자체가 정답 라벨이다. 같은 센서의 day/night 양쪽을
전혀 보지 못한 split은 이 누설을 검증할 수 없다. 따라서 배포 후보와 실험 3의
“best tau” 선택에서 제외했다.

scene term 제거와 `r<=1` cap은 전체 지표를 소폭 개선했지만 역전을 건드리지
못했다. floor-only에 대해 ISO별 tau scale과 ratio cutoff를 train에서 공동
최적화해도 holdout J가 0.3779로 악화했고 문제 구간 FT는 100%(7/7)였다.
즉 현재 두 corpus로 뒷받침되는 답은 다음과 같다.

- **C1 전체 J는 이기는가?** floor-only는 그렇다(전체 +0.0646, holdout +0.0451).
- **ISO [800,1600) 역전을 고치는가?** 아니다. 신뢰할 수 있는 변형은 하나도
  96.4% FT를 C1의 32.1% 근처로 낮추지 못했다.
- 따라서 Path-A adaptive tau를 C1 대신 배포할 근거는 아직 부족하다.

## 1. 실험·검증 공통 설정

판정은 HW와 동일하게 `pixel8 < tau8` 및 `dark_ratio > cutoff`의 두 strict
비교를 썼다. SHA-256(stem, corpus, ISO bucket) 기반 결정적 70/30 split으로
train 209 Sony / 2,933 PASCAL, holdout 112 Sony / 1,326 PASCAL을 만들었다.
파라미터와 cutoff는 train에서만 선택했다.

RAW pass는 단 한 번 수행했다. 4,580개 frame마다
`np.bincount(raw >> 8, minlength=256)`을 정확히 한 번 호출해 하나의 NPZ에
저장했다(초기 build 2,004.8 s, raw read 4,580회, cache `build_count=1`). 이후
모든 sweep은 `np.cumsum` lookup만 사용했고 재실행 manifest의
`cache_status_this_run=reused`로 확인했다.

버킷별 표본 수 합은 SonyNOD 1+3+3+8+24+282=**321**, PASCALRAW
380+3,850+28+1+0+0=**4,259**다. histogram-derived C1 ratio는 기존 CSV와
전 frame max absolute diff **0.0**였고, current adaptive도 ratio diff 0.0 및
threshold mismatch 0건이었다. 따라서 C1 FT 41.82%와 Sony recall 96.26%가
기존 CSV 판정과 정확히 일치한다.

### 전체 baseline 및 변형

| variant (fixed cutoff) | recall | FT | Youden J | holdout recall | holdout FT | holdout J |
|---|---:|---:|---:|---:|---:|---:|
| C0: dark50 > 0.80 | 99.07% | 92.91% | 0.0616 | 99.11% | 91.70% | 0.0740 |
| C1: dark16 > 0.62 | 96.26% | 41.82% | 0.5444 | 98.21% | 41.48% | 0.5674 |
| current adaptive > 0.62 | 98.75% | 38.39% | 0.6036 | 99.11% | 38.69% | 0.6042 |
| tau floor-only > 0.62 | 98.44% | **37.54%** | **0.6090** | 99.11% | **37.86%** | **0.6125** |
| r cap 1 > 0.62 | 98.75% | 38.30% | 0.6046 | 99.11% | 38.69% | 0.6042 |

## 2. 실험 1 — sensor-param fitting

placeholder `sigma_read_e/K` 대신 shift8 domain에서 `tau8(g)=round(c*g)`를
사용했다. `c`는 0.00..32.00, step 0.25를 train에서 sensor별 탐색했다. fixed
cutoff 0.62에서 Sony는 recall 최대, Nikon은 FT 최소로 맞추고 동률이면 작은
`c`를 골랐다.

선택값은 **Nikon/PASCALRAW c=0.0**, **Sony/SonyNOD c=4.0**이다. 아래의
완벽한 숫자는 holdout을 두었어도 센서와 class가 완전히 confounded라서
일반화 검증이 아니다.

| ISO bucket | Sony n | recall | PASCAL n | FT | J |
|---|---:|---:|---:|---:|---:|
| [0,400) | 1 | 100.0% | 380 | 0.0% | 1.000 |
| [400,800) | 3 | 100.0% | 3,850 | 0.0% | 1.000 |
| [800,1600) | 3 | 100.0% | 28 | 0.0% | 1.000 |
| [1600,3200) | 8 | 100.0% | 1 | 0.0% | 1.000 |
| [3200,6400) | 24 | 100.0% | 0 | N/A | N/A |
| [6400,inf) | 282 | 100.0% | 0 | N/A | N/A |
| overall | 321 | 100.0% | 4,259 | 0.0% | 1.000 |

holdout도 112/112 recall, 0/1,326 FT였지만 동일 sensor/corpus를 나눈 것뿐이다.
특히 `c_Nikon=0`은 tau8=0, dark ratio=0으로 daylight 판정을 하드코딩하는
퇴행적 해다. Nikon 야간 또는 Sony 주간 외부검증 전에는 사용하면 안 된다.

## 3. 실험 2 — floor-only 및 r<=1 cap

`tau_floor_only`는 scene-referred term을 완전히 버리고 placeholder noise
floor만 유지했다. `r_cap_1`은 scene term의 r을 `min(r,1)`로 제한했다.

### 3.1 tau floor-only

| ISO bucket | Sony n | recall | PASCAL n | FT | J |
|---|---:|---:|---:|---:|---:|
| [0,400) | 1 | 0.0% | 380 | 2.1% | -0.021 |
| [400,800) | 3 | 0.0% | 3,850 | 40.6% | -0.406 |
| [800,1600) | 3 | 66.7% | 28 | **96.4%** | -0.298 |
| [1600,3200) | 8 | 100.0% | 1 | 100.0% | 0.000 |
| [3200,6400) | 24 | 100.0% | 0 | N/A | N/A |
| [6400,inf) | 282 | 100.0% | 0 | N/A | N/A |
| overall | 321 | 98.44% | 4,259 | 37.54% | **0.6090** |

전체 FT 개선은 exposure term이 크게 작동한 일부 frame을 줄인 효과지만,
문제의 ISO [800,1600)에서는 floor가 이미 threshold를 지배한다. 따라서 scene
term을 없애도 adaptive threshold median 34 문제를 고치지 못한다. 저ISO Sony
recall도 [0,800)에서 0/4로, C1의 1/4보다 나쁘다.

### 3.2 r cap 1

| ISO bucket | Sony n | recall | PASCAL n | FT | J |
|---|---:|---:|---:|---:|---:|
| [0,400) | 1 | 100.0% | 380 | 2.1% | 0.979 |
| [400,800) | 3 | 0.0% | 3,850 | 41.4% | -0.414 |
| [800,1600) | 3 | 66.7% | 28 | **96.4%** | -0.298 |
| [1600,3200) | 8 | 100.0% | 1 | 100.0% | 0.000 |
| [3200,6400) | 24 | 100.0% | 0 | N/A | N/A |
| [6400,inf) | 282 | 100.0% | 0 | N/A | N/A |
| overall | 321 | 98.75% | 4,259 | 38.30% | 0.6046 |

cap은 current adaptive 대비 전체 FT를 0.09%p 낮췄을 뿐이며 recall은 같다.
가설처럼 scene-referred objective의 영향은 일부 줄지만, 역전 원인은 scene
term보다 과대한 placeholder floor이므로 핵심 실패에는 변화가 없다.

## 4. 실험 3 — tau(g)와 ratio cutoff 공동 보정

누설된 sensor fit을 제외하고 train J가 가장 높은 구조 변형인 floor-only를
사용했다. 각 ISO bucket에서 `tau_floor(g)` scale 0.00..3.00(step 0.05)와 strict
ratio cutoff를 train Youden J로 함께 선택했다. 양 class가 train에 모두 없는
bucket은 global train pair `(scale=0.55, cutoff=0.66945)`를 상속했다.

선택 pair는 [0,400) `(0.50, 0.35505)`, [400,800) `(0.15, 0.03289)`,
[800,1600) `(0.55, 0.35537)`, 나머지는 global pair다. 작은 cutoff는 Sony
recall을 살리지만 daylight ratio도 함께 올라오는 overlap을 해결하지 못한다.

| ISO bucket | Sony n | recall | PASCAL n | FT | J |
|---|---:|---:|---:|---:|---:|
| [0,400) | 1 | 100.0% | 380 | 6.1% | 0.939 |
| [400,800) | 3 | 100.0% | 3,850 | 67.0% | 0.330 |
| [800,1600) | 3 | 100.0% | 28 | **96.4%** | 0.036 |
| [1600,3200) | 8 | 100.0% | 1 | 100.0% | 0.000 |
| [3200,6400) | 24 | 95.8% | 0 | N/A | N/A |
| [6400,inf) | 282 | 100.0% | 0 | N/A | N/A |
| overall | 321 | 99.69% | 4,259 | 61.73% | 0.3796 |

holdout은 recall 99.11%, FT 61.31%, J 0.3779였다. 특히 [800,1600) holdout은
recall 2/2이나 FT 7/7(100%)다. fixed-0.62 floor-only의 holdout J 0.6125보다
명백히 나쁘다. cutoff만 ISO별 재보정한 보조 실험도 holdout J 0.0786으로 더
나빴다. 공동 보정은 이 데이터의 낮은 ISO Sony 표본(각 bucket 0~2 holdout)에
민감하며, 분포 overlap을 파라미터 두 개로 없앨 수 없었다.

## 5. 제한사항

1. 가장 큰 한계는 sensor와 label의 완전한 confounding이다. per-sensor fitting의
   100%/0%는 같은 센서에서 day/night 양쪽을 가진 독립 corpus 없이는 평가할
   수 없다. 이 결과는 likely overfit으로 취급했다.
2. SonyNOD 저ISO 표본은 [0,400) n=1, [400,800) n=3, [800,1600) n=3뿐이다.
   ISO별 공동 보정은 train positive가 1~2장이라 cutoff 분산이 매우 크다.
3. PASCALRAW는 ISO 3200 이상 daylight 표본이 없고 [1600,3200)도 1장뿐이다.
   따라서 고ISO J는 계산할 수 없으며 global aggregate는 주로 ISO 400~800이
   지배한다.
4. `tau8=c*g`의 c=0을 금지하는 물리 제약이나 sensor-independent regularizer를
   사후 추가하지 않았다. 결과가 나쁜 이유를 숨기는 임의 제약보다 누설 자체를
   명시하는 편이 정직하다.
5. 본 실험은 checker 분류 지표만 다룬다. downstream mAP이나 실제 보드의
   sensor noise characterization을 대체하지 않는다.

결론적으로, scene term 제거는 작은 전체 J 개선을 주지만 **ISO [800,1600)
reversal의 직접 원인은 placeholder gain-scaled noise floor**다. 다음 유효한
실험은 같은 sensor에서 day/night가 모두 있는 데이터 또는 실제 dark-frame
기반 `sigma_read/K` 측정 없이는 진행하기 어렵다.
