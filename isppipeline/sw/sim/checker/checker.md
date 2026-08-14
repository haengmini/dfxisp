
=============================================================================
File   : isppipeline/sw/sim/checker/checker.md
Date   : 2026-08-13 KST
Function: Stage ① 씬 체커(dark-ratio + hysteresis, NORMAL/LOW_LIGHT 모드
          결정)의 재현 방법론. blc/gain/binning/gamma/AWB와 같은 계열의
          문서지만 대상이 가장 크다 — 5개 원리(결정이론/광도계/노이즈물리/
          표본론/시간축)와 C0→C1→HW hysteresis RTL화까지 걸친 캠페인이
          10편 넘는 문서에 흩어져 있다. 이 문서의 역할은 새로 설계하는
          것이 아니라 그 전체를 하나의 재현 가능한 절차로 압축하는 것.
Sources: isppipeline/hls/results/checker-principles-2026-07-05.md(5원리 정본),
         checker-status-2026-07-10.md(종합), checker-c1-deploy-2026-07-20.md
         (배포 기록), checker-oracle-label-gate2-2026-07-20.md(오라클 게이트,
         인용만), isppipeline/hls/checker/checker_hysteresis.md(HW RTL),
         hw-dataset-geometry-2026-08-13.md(오늘 라이브 트리에 만들어진
         `dataset/{LOD,PASCAL}_test_hw` 및 그 checker 통계 연속성 검증),
         isppipeline/hls/include/checker.hpp, isppipeline/hls/src/
         dfxisp_accel.cpp(배포 구현, 라이브), isppipeline/sw/checker.py
         (SW 미러, 라이브), SPEC.md §3.1/§4.
=============================================================================


# checker — 씬 체커(dark-ratio + hysteresis) 재현 방법론

## 1. 시뮬레이션 목표

`checker-status-2026-07-10.md`가 종합하고 이후 두 문서가 마감한 결론:

> C1(dark16 ratio > 0.62)이 C0(dark50 ratio > 0.80)를 recall/FT/J 전
> 지표에서 지배하며 HW 변경은 상수 1개뿐이다 — 2026-07-20 정식 배포.
> 잔존 판정오차의 89.6%는 라벨 아티팩트이지 알고리즘 결함이 아니다
> (`checker-oracle-label-gate2-2026-07-20.md`) — **C1 재조정 불필요.**

이 결론은 네 겹 주장으로 이뤄진다:
1. **설계 의도**: 5개 원리(결정이론·광도계·노이즈물리·표본론·시간축, §2)가
   dark50을 dark16+Schmitt로 바꿔야 하는 이유를 수식으로 고정한다.
2. **실측이 그 설계를 뒷받침**: C1이 C0를 recall(0.936>0.918)·FT(0.089<
   0.125)·J(0.847>0.793) 전부에서 이기고, 실 RAW 642장(SonyNOD+PASCALRAW)
   대조에서 SW/HW 판정 불일치가 0건이다.
3. **시간축은 이미 HW에 있다**: Schmitt 밴드(진입 64%/해제 60%)가
   2026-08-06 `checker_hysteresis.v`로 RTL화됐다(§2.6) — 애초 배포
   문서가 "드라이버측 정책"이라 적었던 것은 그 시점의 미구현 상태였고
   지금은 대체됐다.
4. **포화 판정**: 정보축(#2)·공간축(#5)·시간축(#3) 강화안은 전부 기각/
   무이득으로 판정났고(`checker-strengthening-2026-07-10.md`), 남은 오차는
   라벨 문제다(§2.7) — 알고리즘을 더 손볼 레버가 별로 없다는 뜻.

**이 문서가 검증할 것**: gamma.md/AWB.md와 같은 성격 — 이미 완성된
방법론을 재현 가능하게 정리한다. 다만 규모가 다르다: gamma/AWB는 결론
하나(D "어느 톤커브/WB가 이기나")를 재현하면 됐지만, checker는 5개
독립 원리 + 3세대 배포(C0→C1→HW hysteresis) + 오라클 라벨 게이트까지
재현 대상이 계층을 이룬다. 각 층을 §2.8 표로 라이브 트리 재현 가능성별로
분리한다.

**단, 위 결론과 §2의 수치(dark16/dark50, 62%/55.3%, J\*/R\* 등)를 정답으로
전제하지 않는다.** 원 캠페인은 COCO/ExDark 프레임 라벨·전 픽셀 스윕
스크립트로 나온 결과이고, 이 문서의 §3.3/3.4/3.5/3.6은 **다른 데이터
(LOD/PASCAL 원본 RAW)로 처음부터 다시 찾거나 다시 재는 실험**이다.
원 캠페인 수치는 **사전 실험/참고 자료**로만 쓴다 — 비교 대상이지
채점 기준이 아니다. §3.3이 다른 τ_pixel을, §3.4가 다른 C_miss/C_FA를,
§3.5가 다른 비율 절단점을 찾아내더라도 그 자체가 유효한 결과이며,
"원 결론과 다르니 재현 실패"로 판정하지 않는다(각 절의 "판정 기준"은
이 원칙을 전제로 다시 표현했다).

## 2. 시뮬레이션 이론

### 2.1 원리 1 — 결정이론: 체커는 비대칭 비용 이진 가설검정이다

Bayes 최적 판정은 우도비 검정 `Λ(x) = p(x|H₁)/p(x|H₀) ≷ η`
(Neyman–Pearson). 레포 실측 비용(mAP ablation, COCO/ExDark, YOLOv8n):

| 상황 | Δ mAP(오판 비용) |
|---|---:|
| COCO를 저조도로 오판(C_FA) | 0.0387 |
| ExDark를 정상으로 놓침(C_miss) | 0.1118 |

`C_miss ≈ 2.89×C_FA` — 비대칭이 뚜렷해 **목적함수는 Youden's J가 아니라
프레임당 기대 mAP 손실 R = ½(miss·C_miss + FT·C_FA)**이어야 한다. 재실행값:

| 규칙 | recall | FT | J | R |
|---|---:|---:|---:|---:|
| C0 dark50>0.80 | 0.918 | 0.125 | 0.793 | 0.00699 |
| **C1 dark16>0.62 (J\*, 배포)** | 0.936 | 0.089 | **0.847** | 0.00531 (−24%) |
| C2 dark16>0.553 (R\*, Bayes-opt, 미배포) | 0.965 | 0.134 | 0.831 | **0.00454 (−35%)** |

C1은 균등-비용 최적점(J\*)이고, 비대칭 비용을 반영한 진짜 R-최적점은
C2다 — 이 간극은 §4에 그대로 남겨둔다(원리가 가리키는 곳과 배포 지점이
다르다).

### 2.2 원리 2 — 광도계: dark 임계는 감마 공간의 진짜 암부에서 잰다

pseudo-RAW는 linear-light다(역감마 2.2 선형화 가설 MAE 4.3~6.0 vs
sRGB-그대로 가설 33~45.5, 실측 대조로 확인). linear dark50(sRGB 등가
≈122)는 "어두운 픽셀"이 아니라 "중간톤 이하"를 세고 있었다 — 정상 장면도
질량 상당분이 거기 있어 dark50이 쉽게 오른다. 대역 분해: **[0,16)에
판별정보가 전부** 있다(단독 AUC 0.977) — [16,50) 대역은 COCO 질량이
ExDark의 3배라 오히려 반신호(단독 AUC 0.089, 역방향). **원리 확정**:
dark16(감마 공간 진짜 암부)로 자른다.

### 2.3 원리 3 — 노이즈 물리: 저조도의 본질은 SNR 붕괴, metering은 log 도메인

EMVA 1288 선형 카메라 모델에서 shot-limited SNR ≈ √(η·µ_p)(Poisson) —
"밝기가 낮다"가 아니라 "전자 수가 적어 SNR이 무너진다"가 저조도의 물리적
정의다. 원리적으로는 dark 임계가 gain에 선형인 τ(s,g) = µ_dark + g·K₀·e\*(s)
여야 하나(적응 τ, §2.6 미배포), pseudo-RAW엔 광자 통계가 없어 현재는
경험적 절대값(dark16)이 차선이다. 재실행 ROC: logmean(log-평균 휘도)
AUC 0.978이 mean8(선형 평균) 0.963을 이기고, dark16(0.977)은 그 log
정보를 비교기 1개로 근사한다 — 셋은 사실상 동률.

### 2.4 원리 4 — 표본론: 전 픽셀 판독은 불필요하다 (1/16 무손실)

Hoeffding 부등식으로 ε=0.02, 신뢰 1−10⁻⁶에 n≈18,100(≈1/51 샘플링)이면
충분. Bayer quad를 통째로 유지하는 1/16 systematic subsample 재현값:
dark16 AUC 0.9766→0.9766(ΔAUC≤0.0001), 대역폭 16배 절감. **HW엔 아직
반영 안 됨** — `checker_select_mode`는 여전히 전 픽셀 스캔(§4).

### 2.5 원리 5 — 시간축: hysteresis는 전환비용 하 최적정책이다

전환비용 c_PR > 0이면 단일 임계(밴드 폭 0)는 결코 최적이 아니다(Dixit
1989, 전환비용 하 최적정지). 설계식 `h ≥ σ_T·Q⁻¹(α)` — 실측
σ_T≈0.0055(p95), α=10⁻⁴ → h≈0.020. **재현값**: δ=0.02(진입 64%/해제
60%, 중심 62%)에서 steady-state flapping이 4개 버전(C0~C3) 전부 0회로
수렴(단일임계는 프레임당 최대 16.7회).

### 2.6 배포 이력 — C0 → C1(2026-07-20) → HW hysteresis RTL화(2026-08-06)

| 시점 | 사건 | 근거 |
|---|---|---|
| ~07-20 | C0 배포: dark50>0.80, demosaic 후 luminance 근사 | (구 배포) |
| **2026-07-20** | **C1 배포**: dark16>0.62, raw Bayer 직접비교로 SW/HW 정합. HW는 `DARK_RATIO_PCT` 상수 1개 + 런타임 레지스터값(256=16<<4)만 변경 — RTL 구조 불변 | `checker-c1-deploy-2026-07-20.md` |
| " | 실 RAW 642장(SonyNOD 321+PASCALRAW 321) 대조: max\|diff\|=0.0, 판정 불일치 0 | 동 문서 §4 |
| **2026-08-06** | Schmitt 히스테리시스가 "드라이버측 정책"에서 **fabric RTL**(`checker_hysteresis.v`, `HYST_ENTER_PCT=64`/`HYST_EXIT_PCT=60`)로 실제 구현. `dfxc_trigger_adapter.v`가 AMD DFX Controller IP(PG374)와 request/ack로 연결. xsim 유닛+통합 테스트 PASS | `checker_hysteresis.md` |

**현재 라이브 트리의 정본 상수** (`isppipeline/hls/include/checker.hpp`):
`DARK_RATIO_PCT=62`(단일프레임 판정, golden 계약과 별개로 고정),
`HYST_ENTER_PCT=64`, `HYST_EXIT_PCT=60`(Schmitt 밴드). `checker_select_mode()`
는 두 값을 독립적으로 유지한다 — 단일프레임 verdict는 62%로 golden
계약을 보존하고, Schmitt state machine은 `hyst_flags`(진입/해제 비교기
2개)를 core 밖에서 소비한다.

**SW 미러**(`isppipeline/sw/checker.py`)는 raw Bayer를 이 branch의
pseudo-RAW16(shift8) 도메인에서 `DARK_RAW = 16<<8 = 4096`과 비교한다 —
HW의 raw12 레지스터값(256=16<<4)과 **비트 폭이 다른 표현일 뿐 같은
dark16 임계**다(`raw16 = raw12<<4`이므로 `4096 = 256<<4`, 배율만 다름).
새 스크립트를 짤 때 이 도메인 차이를 섞으면 안 된다(§3.2에서 실제로
부딪히는 지점).

### 2.7 오라클 라벨 게이트 (강화안 #4, 2026-07-20 완료)

Shuffle_split 642장에서 dual-arm 렌더 델타로 프레임을 재라벨링한 결과
(`checker-oracle-label-gate2-2026-07-20.md`, 요지만 인용): C1 잔존오차의
**89.6%가 라벨 아티팩트**(진짜 판정오류는 10.4%뿐)이고, naive 라벨
기준 J=0.847이 오라클 기준에서는 J=0.008로 붕괴하지만 — **C1 임계
(0.62)의 사후확률-중립점 성질(p(H1|0.62)=0.510, 비용 C_miss≈C_FA)은
오라클 기준에서도 유지**된다. 즉 dark16이라는 통계량 자체의 판별력은
"라벨이 얼마나 정확한가"에 크게 좌우되지만, **그 통계량 위에서 62%가
올바른 절단점이라는 결론은 라벨 정의와 무관하게 안정적**이다 — 그래서
"C1 재조정 불필요"로 마감됐다.

### 2.8 기존 근거와 재현 가능성

| 근거 | 위치 | 재현 가능성 |
|---|---|---|
| 5원리의 원자료(1150프레임 스윕, `checker_stat_sweep.py`/`checker_versions.py`) | `checker-principles-2026-07-05.md` 및 그 Sources 3편 | **현재 브랜치엔 없음.** 도구 전부 `isppipeline/hls/tools/`에서 삭제됨(git status D) — 워크트리(`hw-interface-prompt`/`consolidate-references`)에만 있다. 결론(표의 수치)은 라이브 문서로 인용 가능. |
| C0/C1 배포 구현 자체(`DARK_RATIO_PCT`, `HYST_ENTER/EXIT_PCT`, `checker_select_mode`) | `checker.hpp`, `dfxisp_accel.cpp` | ✅ **라이브 트리, 정본.** |
| SW 미러(`checker.py`, dark_ratio, raw 도메인 직접비교) | `isppipeline/sw/checker.py` | ✅ **라이브 트리.** |
| HW hysteresis RTL(`checker_hysteresis.v`) + xsim TB | `isppipeline/hls/checker/` | ✅ **라이브 트리**(RTL/TB 파일 존재) — 재시뮬레이션은 Vivado xsim 필요(이 세션 범위 밖, §4). |
| 오라클 라벨 원자료(dual-arm 렌더, Shuffle_split 642장) | `checker-oracle-label-gate2-2026-07-20.md` | **재현 불가 — 원본 스크립트 없음.** 결론은 인용 가능(§2.7), 새 데이터로 재실행하려면 dual-arm 렌더+델타 재라벨링 로직을 새로 짜야 한다. |
| **실 RAW dark-ratio 통계 연속성 검증** (checker 전용, full-res vs 4× CFA-preserving decimation, **FPGA 실험 전용 — checker SW 시뮬레이션은 사용하지 않음**) | `hw-dataset-geometry-2026-08-13.md`, `dataset/{LOD,PASCAL}_test_hw` | ✅ 라이브 트리, 오늘 생성. dark_ratio(raw12<256) 보존이 max\|Δ\|≤0.067%p로 검증됨 — 참고용 배경 지식으로만 인용(§3.2). checker SW 시뮬레이션의 데이터 소스는 이 `_hw` 세트가 **아니라** 아래 행. |
| **원본 RAW 직접(SW 시뮬레이션의 실제 데이터 소스)** | `dataset/LOD_test/raw`(.ARW), `dataset/PASCAL_test/raw`(.nef) | ✅ **완료(2026-08-13).** `dataset/LOD_test_eval`(gamma 작업 산물)·`dataset/{LOD,PASCAL}_test_hw`(FPGA 산물)는 정리돼 더 이상 없다 — memory 지침(dataset/엔 LOD_test/PASCAL_test 원본만)에 따라 두 eval-root 산출물은 `dataset/`가 아니라 `isppipeline/sw/sim/checker/_cache/{LOD,PASCAL}_test_eval/`에 둔다(gitignore됨). `build_lod_test_eval_root.py`(LOD)는 라이브 트리 재실행, `build_pascal_test_eval_root.py`(PASCAL, 신규 작성)는 이번에 만들었다 — 둘 다 100/100 성공. |
| adaptive-τ Path A(ISO 적응, `checker_adaptive_tau.py`) | `checker-adaptive-tau-realdata-2026-07-13.md` | **현재 브랜치엔 없음**, 워크트리 전용. ISO[800,1600) 역전 미해명 상태로 실험 코드에 머물러 있다 — 이 문서의 재현 대상이 아니다(§4). |

**요약**: checker는 gamma/AWB보다 잃어버린 조각(이론축 원자료, 오라클
원자료)이 많지만, **핵심 배포 구현(HW+SW)은 잘 갖춰져 있다.** 실데이터는
`_hw`(FPGA 전용, 4× 데시메이션 + 두 세트 공통 기하로 통일)가 아니라
**원본 RAW를 직접** 쓴다 — checker의 dark_ratio는 프레임 크기에 무관한
평균 통계라 detector 추론(gamma)과도, FPGA 배열 바운드(`_hw`)와도 달리
LOD/PASCAL이 서로 다른 원본 해상도를 유지해도 무방하다(§3.2).

## 3. 시뮬레이션 방법 (기존 방법론 재현)

### 3.1 1단계 — SW/HW 정합성 재확인 (라이브 트리, 즉시 가능)

`checker.py`의 `dark_ratio()`/`selected_mode()`가 `checker.hpp`의
`checker_select_mode()`와 같은 판정을 내리는지: 두 구현 다 `raw < threshold`
비교이므로 도메인만 맞추면(§2.6의 raw16↔raw12 배율) bit-exact
동치를 스크립트로 fuzz-검증할 수 있다 — gamma_sim.py Part A(§3.2 bit-exact
게이트)와 같은 성격의, checker에서 처음 만드는 자체완결형 검증.

### 3.2 2단계 — dark16 판별력 재현 (`dataset/LOD_test/raw` + `PASCAL_test/raw` 원본 직접)

`dataset/{LOD,PASCAL}_test_hw`는 **FPGA 실험 전용**이다(4× CFA-preserving
데시메이션 + 두 세트 공통 1368×912으로 통일 — `MAX_BINNED_W=960` 배열
바운드 때문에 필요했던 FPGA 쪽 제약, `hw-dataset-geometry-2026-08-13.md`).
checker SW 시뮬레이션은 이 제약을 받지 않는다 — dark_ratio는 프레임
크기와 무관한 평균 통계이므로, **원본 RAW를 있는 그대로**(각 세트 고유
해상도, 데시메이션 없음) 쓰는 편이 더 정확하다(데시메이션은 노이즈
통계를 바꾸므로 §2.3의 원리 검증엔 오히려 잡음원).

**2026-08-13 갱신(완료)**: `dataset/LOD_test_eval`(gamma 작업 산물)과
`dataset/{LOD,PASCAL}_test_hw`(FPGA 산물)가 정리돼 `dataset/{LOD,PASCAL}
_test/raw`(원본 `.ARW`/`.nef`)만 남아 있다. eval-root(raw_bin)는 memory
지침에 따라 `dataset/`가 아니라 `isppipeline/sw/sim/checker/_cache/
{LOD,PASCAL}_test_eval/`에 만든다(gitignore됨) — 아래 둘 다 실행 완료:

- **LOD**(Sony `.ARW`, n=100): `python3 isppipeline/sw/sim/
  build_lod_test_eval_root.py --src dataset/LOD_test --out
  isppipeline/sw/sim/checker/_cache/LOD_test_eval` — shift8 정규화
  (`round(clip((raw-800)/(16380-800),0,1)*255)<<8`, black=800/white=16380)
  이므로 SW `checker.py`의 `DARK_RAW=16<<8=4096` 임계와 도메인이 그대로
  맞는다. 100/100 성공.
- **PASCAL**(Nikon `.nef`, n=100): `isppipeline/sw/sim/
  build_pascal_test_eval_root.py`(신규 작성)를 `python3 ... --src
  dataset/PASCAL_test --out isppipeline/sw/sim/checker/_cache/
  PASCAL_test_eval`로 실행. rawpy로 직접 확인한 값은 `visible
  6034×4012, black_level_per_channel=[0,0,0,0], white_level=4095`
  (hw-dataset-geometry 문서의 기재값과 일치, 15/100 표본 전부 동일).
  black=0이라 정규화가 LOD보다 단순하다: `round(clip(raw/4095,0,1)
  *255)<<8`. 100/100 성공.

두 세트 모두 같은 shift8(raw16) 도메인으로 정규화되면, 두 세트의 소속
자체를 근사 라벨로 쓴다: LOD(전부 야간) = H₁, PASCAL(전부 주간) = H₀.
`dark16 = mean(raw16 < 4096)`을 계산해 C0(dark50 상당,
threshold raw16<12800)/C1(dark16)의 분리도(AUC/overlap)를 비교한다.
두 세트 해상도가 달라도(LOD 5472×3648 vs PASCAL 6034×4012) 평균 통계라
문제없다.

**주의(§2.8 caveat 상속)**: 이 근사 라벨은 원 캠페인의 프레임 단위
COCO/ExDark 라벨과 다르다 — "이 데이터셋 전체가 H1"이라는 가정은 세트
내부의 밝은/어두운 프레임 변이를 무시한다. AUC 절대값은 원 캠페인
수치(0.977)와 직접 비교하지 않는다. **C0/C1의 분리도 순위(§1의 사전
참고 자료)를 참고점으로만 삼고**, 이 데이터에서 실제로 어느 쪽이
우위로 나오는지는 §3.3/3.4가 직접 다시 찾는다 — 다르게 나와도 그
자체가 결과다.

### 3.3 3단계 — dark 픽셀 임계값(τ) 탐색: "어느 밝기부터 어둡다고 셀 것인가"

원리 2(§2.2)의 주장 — "판별정보는 [0,16)에 전부 있고 [16,50)은 오히려
반신호" — 를 배포된 상수(16/50)를 그대로 믿지 않고 직접 스윕해서
재도출한다. 픽셀 단위 dark-cutoff 자체를 찾는 실험이다(비율 τ_ratio가
아니라 픽셀값 τ_pixel).

- 후보 τ_pixel(8-bit-환산): `{4, 8, 12, 16, 20, 24, 32, 40, 50, 64, 80,
  96, 128}` — 16(C1)과 50(C0)을 반드시 포함해 배포 이력과 직접 비교
  가능하게 한다.
- 각 τ_pixel마다 두 세트(LOD/PASCAL, §3.2의 shift8 정규화 raw_bin)
  전 프레임에서 `dark_ratio_τ(frame) = mean(raw16 < τ_pixel<<8)`을 계산.
- `dark_ratio_τ`를 LOD(H₁) vs PASCAL(H₀) 분류기로 놓고 τ_pixel별 ROC
  AUC를 구해 `τ_pixel* = argmax AUC`를 찾는다.
- **관찰 지점**(정답을 전제하지 않음): τ_pixel*가 실제로 어디서 나오는지가
  1차 결과다. 16(C1)·50(C0)은 원 캠페인의 사전 참고점일 뿐이므로,
  τ_pixel*가 그 근방이면 원리 2의 "[0,16) 대 [16,50)" 주장과 궤를
  같이하는 것이고, 다른 값(예: LOD/PASCAL 특유의 노출 분포 때문에
  더 낮거나 높은 τ)이 나오면 그것대로 기록한다 — AUC-τ 곡선의 형태
  (단조인지, 16 부근에서 꺾이는지)도 있는 그대로 보고한다.

### 3.4 4단계 — C_miss/C_FA 재도출 (dual-arm mAP ablation, LOD_test/PASCAL_test, YOLOv8n)

원 캠페인의 `C_miss=0.1118`/`C_FA=0.0387`(§2.1)은 COCO/ExDark 기반
mAP ablation(n=31/39)이고, 이 브랜치엔 그 원자료가 없다(§2.8). 하지만
이 문서엔 그걸 대체할 재료가 이미 다 있다 — §3.2가 준비하는 raw_bin
(원본 직접, `LOD_test_eval`/`PASCAL_test_eval`)과, 이 브랜치에 살아있는
정본 렌더 파이프라인·검출기·mAP 도구를 그대로 쓰면 **워크트리 없이
직접 재도출**할 수 있다:

- normal arm = `isppipeline/sw/default_isp_pipeline.py::run_default_isp()`(라이브)
- lowlight arm = `isppipeline/sw/lowlight_isp_pipeline.py::run_lowlight_isp()`,
  `arm="lowlight_isp"`(배포 조합, BIN_BINNING+TONE_GAMMA, 라이브)
- 검출기 = YOLOv8n(`ultralytics` 8.4.82, 이 환경에 설치돼 있음, 확인됨)
- mAP 계산 = `pycocotools`(이 환경에 설치돼 있음, 확인됨) 또는
  `ultralytics.utils.metrics`

원 캠페인과 동형인 정의(§2.1 "COCO를 저조도로 오판(C_FA)" / "ExDark를
정상으로 놓침(C_miss)"을 LOD/PASCAL로 그대로 치환):

1. `PASCAL_test_eval`(H₀, 주간, n=100)을 두 arm 모두로 렌더 → YOLOv8n
   추론 → arm별 mAP@[.5:.95] 계산.
   `C_FA = mAP(normal arm, PASCAL) − mAP(lowlight arm, PASCAL)`
   (밝은 장면에 저조도 처리를 잘못 트리거했을 때 잃는 mAP).
2. `LOD_test_eval`(H₁, 야간, n=100)을 두 arm 모두로 렌더 → YOLOv8n
   추론 → arm별 mAP@[.5:.95] 계산.
   `C_miss = mAP(lowlight arm, LOD) − mAP(normal arm, LOD)`
   (저조도 장면에서 트리거를 놓쳤을 때 잃는 mAP).
3. 이렇게 새로 잰 `C_miss`/`C_FA`(와 그 비율)를 §3.5의 Bayes risk
   계산에 쓴다. 원 캠페인 값(0.1118/0.0387, 비율 2.89:1)은 §1 원칙대로
   **비교 참고점일 뿐**이다 — 이 재도출이 다른 절대값이나 다른 비율을
   내더라도(예: 카메라·조명 분포·클래스 구성이 다르므로 충분히 가능)
   그것이 이 데이터의 결과이고, §4에 있는 그대로 기록한다.

**주의**: 이 단계만 §3.1-3.3/3.5-3.7과 달리 **detector 추론이 필요**하다
(gamma의 mAP ablation과 같은 성격 — checker의 다른 실험들이 dark_ratio
평균 통계만으로 끝나는 것과 다른 지점). 100장×2 arm×2 데이터셋 = 400회
추론을 원본 해상도(LOD 5472×3648, PASCAL 6034×4012)로 돌려야 해서
CPU에서 gamma_report.md의 유사 규모 실행(n=100, YOLOv8n, CPU)만큼
시간이 걸릴 수 있다. 두 데이터셋 다 §3.2/§5가 준비하는 raw_bin을
그대로 재사용하므로 이 단계만을 위한 별도 데이터 준비는 없다.

### 3.5 5단계 — dark_ratio 판정 기준점(cutoff) 탐색: "몇 % 넘으면 어둡다고 판단할 것인가"

§3.3에서 고른 τ_pixel(들)로 만든 `dark_ratio` 분포 위에서, **비율
자체의 절단점**을 탐색한다 — C0(80%)/C1(62%)/C2(55.3%)를 후보로만
검증하는 §3.6과 달리, 여기는 그 세 후보가 어떻게 나왔는지의 도출
과정 자체를 재현한다(원리 1, §2.1).

1. τ_pixel = 16(C1이 쓰는 픽셀 임계, 비교 참고점)으로 고정하고, ratio
   절단점 r ∈ [0, 1](0.01 간격)마다 recall(r) = P(dark_ratio > r | LOD)와
   FT(r) = P(dark_ratio > r | PASCAL)을 계산해 ROC 곡선을 그린다.
2. **Youden's J 최적점**: `r_J* = argmax(recall(r) − FT(r))`을 이
   데이터에서 직접 구한다 — C1(62%)은 원 캠페인이 다른 데이터로
   구한 J\*이므로, r_J*가 62%와 같을 근거는 없다. 다르게 나오면
   그것이 이 데이터의 결과다.
3. **Bayes risk 최적점**: `R(r) = ½(miss(r)·C_miss + FT(r)·C_FA)`,
   이번엔 §3.4에서 **이 데이터로 직접 재도출한** `C_miss`/`C_FA`를
   쓴다(원 캠페인 값을 상속하지 않는다 — 그게 이번 수정의 요지다)로
   `r_R* = argmin R(r)`을 구한다. C2(55.3%, 원 캠페인의 R-최적점)는
   비교 참고점일 뿐, r_R*가 거기서 벗어나도 이상한 게 아니다 — 비용비
   자체가 §3.4에서 새로 잰 값이므로 원 캠페인과 다르게 나오는 것이
   당연할 수 있다.
4. τ_pixel = τ_pixel*(§3.3에서 이 데이터로 직접 찾은 픽셀임계)로도
   1-3을 반복해, "픽셀임계까지 데이터로 새로 뽑으면 비율 절단점이
   얼마나 달라지는가"를 확인한다 — 배포값(16, 62%) 근처로 수렴하든
   멀어지든, 둘 다 §4에 있는 그대로 기록할 결과다.

`r_R*`는 이제 "원 비용비를 그대로 믿는다면"이라는 조건부 결론이 아니라
§3.4가 이 데이터로 직접 잰 비용비 위에서 나온 결과다 — 다만 §3.4 자체가
LOD/PASCAL·YOLOv8n·shift8 정규화라는 특정 조건에 묶여 있다는 점은
여전히 남는다(§4).

### 3.6 6단계 — 후보 규칙 종합 비교 (recall/FT proxy, dark16/dark50을 승자로 전제하지 않음)

이전 초안은 "C0 vs C1"만 비교했다 — 이 자체가 §1 원칙과 어긋난다.
C1(dark16)이 C0(dark50)를 이긴다는 것도 원 캠페인의 결과이지, 이 데이터가
증명해야 할 정답이 아니다. §1~§5 단계를 거치며 실제로 여러 후보가
나왔으므로, 이 단계는 그 후보 전부를 **같은 표에 나란히** 놓고 recall/
FT/J/R을 계산한다 — "이 데이터에서 뭐가 이기는지"를 사전 승자 없이
관찰하는 것이 목적이다. detector 추론은 필요 없다(§3.4와 다른 지점 —
recall/FT 모두 §3.2/§3.5가 이미 계산한 dark_ratio 분포에서 나온다).

| # | 후보 (τ_pixel, ratio cutoff) | 출처 | 성격 |
|---|---|---|---|
| 1 | (50, 80%) | C0, 원 캠페인 | 구 배포 — 참고점 |
| 2 | (16, 62%) | C1, 원 캠페인 | 현 배포 — 참고점 |
| 3 | (16, 55.3%) | C2, 원 캠페인 | R-최적(미배포) — 참고점 |
| 4 | (16, r_J\*) | §3.5-2 | 배포 픽셀임계 유지 + 이 데이터의 Youden 최적 비율 |
| 5 | (16, r_R\*) | §3.5-3 | 배포 픽셀임계 유지 + §3.4 새 비용비의 Bayes-risk 최적 비율 |
| 6 | (τ_pixel\*, r_J\*) | §3.3 + §3.5-4 | 픽셀임계·비율 둘 다 이 데이터에서 새로 찾은 규칙 |
| 7 | (τ_pixel\*, r_R\*) | §3.3 + §3.5-4 | 위와 동일하되 Bayes-risk 기준 |

1~3은 이 데이터로 재현한 게 아니라 §1 원칙대로 비교용 참고 행이다
(τ=50/16을 이 표 계산에 실제로 다시 적용해 recall/FT를 낸 것 — 즉
"C0/C1 규칙 자체를 LOD/PASCAL에 적용하면 얼마가 나오는가"는 재현이지만,
"그 규칙이 최선이다"는 전제하지 않는다). 4~7이 이번 실험이 실제로
찾아낸 신규 후보다.

각 후보의 recall(LOD를 LOW_LIGHT로 맞히는 비율)/FT(PASCAL을 LOW_LIGHT로
오판하는 비율)/J(recall−FT)/R(§3.4의 재도출 비용으로 계산, 후보 1~3도
동일 비용으로 재계산해 공정 비교)을 표로 낸다. **판정 기준은 없다** —
7개 중 R이 가장 낮은(또는 J가 가장 높은) 후보가 무엇인지 있는 그대로
보고한다. 그 후보가 1·2(dark16/50)가 아니어도 "더 나은 규칙을 찾았다"는
관찰일 뿐, 이 문서가 배포 전환을 제안하는 것은 아니다(§4) — 다만 그런
후보가 나온다면 §4에 숨기지 않고 적는다.

### 3.7 7단계 — hysteresis flapping 재현 (필요 시)

`dark_ratio` 시계열에 실측 지터 σ(§2.5, p95≈0.0055)를 얹은 synthetic
스윕으로 δ=0.02 밴드의 steady-state flapping이 0인지 재현한다 — 이
부분은 실측 σ 자체가 "공간 샘플링 노이즈 proxy"였다는 한계가 원 문서에
이미 명시돼 있다(§4).

### 3.8 워크트리 필요 항목 (이번 문서의 재현 범위 밖)

- 5원리 원자료 재생성(1150프레임 COCO/ExDark 전수 스윕) — `checker_stat_sweep.py`
  확보 없이는 §2.1~2.5 표의 절대값을 다시 낼 수 없다. §3.3/3.4/3.5/3.6이
  대신 제공하는 것은 "같은 방법론을 다른 데이터로 재실행한 결과"이지
  원 캠페인 수치의 "원 수치 재현"이 아니다. (C_miss/C_FA 자체는 더 이상
  이 목록에 없다 — §3.4가 이 문서 범위 안에서 재도출한다.)
- 오라클 라벨 게이트 재실행(dual-arm 렌더 + Shuffle_split) — §2.7 결론은
  인용만 가능.
- adaptive-τ ISO 역전 재검증 — 이 문서의 범위 밖(§1의 "C1은 이미 마감된
  결론" 전제와 별개 트랙).
- HW hysteresis RTL 재시뮬레이션(xsim) — Vivado 필요, 이 세션 범위 밖.

## 4. 알려진 한계

- **§3.3/3.4/3.5가 원 캠페인 수치와 다른 τ_pixel*/C_miss·C_FA/r_J*/r_R*를
  찾아내도 그 자체가 결과다, 오류가 아니다**(§1에서 이미 명시). 이 문서의 5원리
  수치(§2)는 COCO/ExDark 기반 사전 실험/참고 자료이지, LOD/PASCAL로
  다시 찾은 값이 그와 달라야 "틀렸다"고 판단할 근거가 되지 않는다 —
  카메라·조명 분포·라벨 정의가 전부 다른 데이터이기 때문이다.
- **원리 1이 가리키는 곳과 배포 지점이 다르다.** R-최적(C2, dark16>0.553)
  이 이론상 R을 C1보다 −11%p 더 낮추지만 배포되지 않았다 — 이유는
  `checker-principles-2026-07-05.md` 한계 §2가 이미 밝혔다: C_miss/C_FA
  추정이 n=31/39 소표본이라 55% vs 62% 선택은 보드 c_PR 실측 후
  재검토 대상으로 남겨졌다. 이 문서는 C2 배포를 제안하지 않는다 —
  이 간극이 존재한다는 사실만 정직하게 남긴다.
- **원리 4(1/16 subsample)는 이론·시뮬레이션만 있고 HW엔 없다.**
  `checker_select_mode()`는 지금도 전 픽셀을 스캔한다(§2.4) — 대역폭
  절감은 채택된 적 없는 미반영 최적화다.
- **§3.2의 데이터셋-소속 근사 라벨**(그리고 이를 그대로 쓰는 §3.3/3.5/3.6
  — §3.4는 제외, mAP ablation은 프레임별 실제 YOLO 라벨을 쓰지 이
  근사 라벨을 쓰지 않는다)은 원 캠페인의 프레임 단위 라벨보다 거칠다
  — 절대 AUC/recall/FT 수치를 원 문서와 직접 비교하지 않는다(§3.2
  주의 참고).
- **두 세트 다 raw_bin이 지금 없다(2026-08-13 정리로 삭제됨).** LOD는
  스크립트(`build_lod_test_eval_root.py`)가 라이브 트리에 있어 재실행만
  하면 되지만, PASCAL은 `build_pascal_test_eval_root.py` 자체가 아직
  없다 — §3.2를 실행하려면 최소 이 스크립트 작성 + 두 세트 raw_bin
  재생성이 선행돼야 한다(§5). 이 문서 자체는 그 스크립트를 아직
  포함하지 않는다.
- **LOD·PASCAL 두 세트의 정규화 도메인 유도 경로가 다르다.** LOD는
  14-bit 센서(black=800/white=16380)를, PASCAL은 12-bit 센서(black=0/
  white=4095)를 shift8로 정규화한다 — 최종 도메인(0..65280)은 같지만
  센서 비트폭·black level 보정의 "정도"가 달라, 두 세트의 dark16
  통계를 직접 비교할 때 이 차이가 잔류 편향으로 남을 가능성을 배제하지
  않는다(카메라 자체가 다르므로 원 캠페인의 SonyNOD/PASCALRAW 대비도
  같은 한계를 이미 안고 있었다).
- adaptive-τ, 오라클 라벨 원자료, HW xsim 재실행은 미착수(§3.8).
- `_hw` 데이터셋의 checker 통계 연속성 검증(§2.8)은 FPGA 파이프라인
  자체를 검증한 것이지 이 문서의 SW 재현 경로를 검증한 것이 아니다 —
  혼동하지 않는다.

## 5. 산출물 (구현 완료, 2026-08-13)

- `isppipeline/sw/sim/checker/_cache/LOD_test_eval/`,
  `.../PASCAL_test_eval/` — §3.2의 선행 조건, 완료. `build_lod_test_eval_root.py`
  재실행 + 신규 작성한 `isppipeline/sw/sim/build_pascal_test_eval_root.py`
  실행. 둘 다 `dataset/`가 아니라 `_cache/`에 둔다(memory 지침, gitignore됨).
  각 100/100 성공.
- `isppipeline/sw/sim/checker/checker_sim.py` — §3.1(SW/HW 정합성
  bit-exact 게이트) + §3.2/3.3/3.5/3.6(위 `_cache/` eval-root 기반
  dark16/dark50 분리도 재현, τ_pixel/ratio cutoff 탐색, 후보 규칙 종합
  비교) + §3.7(flapping)을 구현하는 자체완결형 스크립트 — 전부 numpy
  통계뿐, detector 불필요. gamma_sim.py와 같은 원칙(재구현 대신
  `checker.py`의 상수·로직 재사용, HW 쪽은 `checker.hpp`를 Python으로
  로컬 미러링 — C++이라 직접 import 불가). `_hw` 데이터셋은 참조하지
  않는다. §3.4의 `checker_costs_derived.csv`가 있으면 자동으로 읽어
  Bayes-risk 계산까지 채우고, 없으면 그 부분만 건너뛴다(원 캠페인 값으로
  대체하지 않음, §1).
- `isppipeline/sw/sim/checker/checker_map_ablation.py` — §3.4(C_miss/
  C_FA 재도출)를 별도 스크립트로 분리(YOLOv8n 추론이 필요해 `checker_sim.py`
  의 나머지보다 훨씬 오래 걸림 — gamma_sim.py가 detector 기반 mAP
  ablation을 아예 별도로 뺀 것과 같은 이유). `default_isp_pipeline.py`/
  `lowlight_isp_pipeline.py`의 `run_arm()`을 재사용(재구현 없음), YOLOv8n
  mAP 계산은 `ultralytics`의 표준 `model.val()` 경로를 그대로 씀(직접
  구현 없음). `C_miss`/`C_FA`를 `checker_costs_derived.csv`(csv 한 줄)로
  남겨 `checker_sim.py`가 읽는다.
- `isppipeline/sw/sim/checker/checker_report.md` — 실행 산출물과 원
  캠페인 수치를 나란히 놓은 비교 리포트(§1의 원칙대로 "재현 성공/실패"
  판정이 아니라 관찰 결과로 서술).
