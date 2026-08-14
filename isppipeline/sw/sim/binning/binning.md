<!--
=============================================================================
File   : isppipeline/sw/sim/binning.md
Date   : 2026-08-10 KST
Function: lowlight_isp stage (1) same-color 2x2 binning의 SNR 이득 주장에 대한
          재현 가능한 시뮬레이션 방법론. §1-2는 목표와 이론적 배경(노이즈
          모델, 캘리브레이션, SNR 유도, 기존 근거 재현성 검토), §3부터는
          새로 설계한 스펙(2026-08-12 구현·최초 실행 완료, binning_report.md
          참고) — 조사 결과 이 주장을 뒷받침하는 원본
          스크립트가 리포 어디에도 남아있지 않았다.
Sources: isppipeline/hls/src/lowlight_isp.md §2.5, §4.1, isppipeline/hls/
         results/lowlight-feature-principles-2026-07-05.md §4.1,
         isppipeline/hls/results/v2-arm-ablation-2026-08-06.md,
         isppipeline/sw/gen_lowlight_isp_golden.py.
=============================================================================
-->
# binning — same-color 2×2 binning 시뮬레이션 방법론

## 1. 시뮬레이션 목표

`lowlight_isp.md` §2.5가 배포한 주장:

> same-color 2×2 평균(중첩 창)으로 R/B는 4샘플 평균(**+6 dB**), G는 8샘플
> 평균(**+9 dB**)의 SNR 이득을 얻는다. 출력 크기는 H/2×W/2 그대로다.

**목표**: `binned_raw()`가 실제로 이론값(+6 dB R/B, +9 dB G)에 부합하는
노이즈 저감을 만들어내는지, **임의의 합성 분포가 아니라 이 파이프라인이
이미 캘리브레이션한 실센서 노이즈 모델**로 직접 측정한다. 검증에 필요한
이론적 배경(노이즈 모델·캘리브레이션·SNR 유도·기존 근거 검토)은 §2에서,
그 위에 세운 신규 시뮬레이션 설계는 §3에서 다룬다.

## 2. 시뮬레이션 이론

### 2.1 야간 환경의 이미지 처리와 binning

저조도(야간) 촬영은 도달 광자 수 자체가 적어 신호 대비 노이즈가 근본적으로
나쁘다. 노출시간·아날로그 게인을 늘리는 데는 모션 블러·포화 등 한계가
있으므로, ISP 단에서 공간적으로 여러 샘플을 합쳐 노이즈를 줄이는 binning이
저조도 대응의 1차 수단으로 쓰인다.

`lowlight_isp` 파이프라인이 실제로 배포하는 binning 알고리즘은
`gen_lowlight_isp_golden.py`의 `binned_raw(..., bin_mode=BIN_BINNING)`다 —
같은 색끼리 2×2 셀 이웃(중첩 창)을 평균한다: R 4샘플, B 4샘플, G 8샘플
(이웃 2×2 셀 × 셀당 2 G사이트). 출력 인접 픽셀이 샘플을 공유하므로 출력
크기는 H/2×W/2 그대로 유지된다.

이 문서가 검증하려는 것은 정확히 이 알고리즘이 **"binning을 전혀 하지
않은 경우"(단일 샘플, n=1) 대비** 이론값만큼의 SNR 이득을 내는가다 — v1/v2
최초 구현은 이름만 binning이고 실제로는 이 이득을 낸 적이 없었다는 이력이
있어(`lowlight_isp.md` §2.5의 "발견" 항목), 이득이 이론값에 부합하는지
직접 측정해 확인해야 한다.

binning은 BLC(black-level correction)보다 먼저 적용된다 — 개별 샘플에
클리핑을 먼저 걸면 음의 노이즈가 0으로 접혀 양의 바이어스가 생기기
때문에, 먼저 평균하고 pedestal(Black level 바닥값)을 한 번 빼는 순서가 비편향(unbiased)이다. 이
시뮬레이션은 이 순서 상호작용은 다루지 않고 binning 자체의 SNR만
격리한다(§3.4).

### 2.2 포이슨-가우시안 노이즈 모델

센서 노이즈 분산을 신호 세기 `y`(DN)의 선형함수로 두는 표준 모델이다:

```
variance(y) = a·y + b
```

- `a`(shot-noise 기울기): 광자 산탄노이즈. 광자 도달이 Poisson 과정이므로
  분산이 평균 신호에 비례해서 커진다.
- `b`(read noise 분산, σ_read²): 신호와 무관한 고정항(증폭기·ADC 등 회로
  노이즈). 신호가 작을수록(저조도일수록) 전체 노이즈에서 이 항의 비중이
  커진다.

### 2.3 캘리브레이션

여기 쓰는 `a`, `b`는 임의로 가정한 값이 아니라 **이 파이프라인이 실제
평가에 쓰는 데이터셋 자체**(`data/split_nod`의 ISO 6400 `raw_arw` 91장)에서
`tools/calibrate_noise_model.py`로 photon-transfer 방식으로 실측한 값이다
(8×8 블록별 분산 → 밝기 구간 2% 백분위 → χ² 편향보정 → 선형 적합).

| 도메인 | a | b | σ_read | R² |
|---|---:|---:|---:|---:|
| 14-bit 센서 | 60.63 DN | 10,878 DN² | 104 DN | 0.999 |
| 12-bit 파이프라인(s=4080/15580) | **15.878** | **746** | **27.3** | — |

→ `A_Q8 = 4065`, `B_DN2 = 746`(Q8 고정소수점, a×256).

적합값(σ_read=104 DN, 14-bit 도메인)은 가장 어두운 평탄 영역의 직접 관측
표준편차(94~98 DN)와 일치해 교차검증됐다 — 곡선 적합만의 산물이 아니라는
뜻이다. 참고로 그 직전 커밋값(A_Q8=1202, B_DN2=50)은 다른 세트로 잰
자기모순 측정(적합 σ_read=27 vs 같은 프레임 직접관측 σ≈68)이었는데 당시
넘어갔다가 이번에 정정됐다 — 유도 과정과 폐기 경위는 `lowlight_isp.md`
§4.1 참고.

이 값은 **ISO 6400 상수**다(a는 아날로그 게인에 비례, b는 제곱에
비례하므로 다른 ISO에는 그대로 적용되지 않는다). PASCALRAW 같은 주광 센서
데이터와는 a가 66배 차이나 아예 다른 노이즈 체제다 — 자세한 제약은
`lowlight_isp.md` §4.1의 "ISO 단서"/"PASCALRAW 참고" 항목.

> **독립 재캘리브레이션(2026-08-13)**: `dataset/LOD_test`의 ISO 6400
> 서브셋(81장)으로 같은 절차를 독립 실행해 `a=61.36 DN`, `b=11,705 DN²`
> (14-bit, R²=0.997) → `A_Q8=4114`, `B_DN2=803`을 얻었다. 위 배포값과
> 1~8% 내로 일치해 이 캘리브레이션을 교차검증한다. **"ISO 6400 상수"라는
> 위 경고가 실제로 얼마나 중요한지도 함께 확인됐다** — 같은 100장을
> ISO를 섞은 채(ISO 500~6400) 적합하면 R²가 0.001~0.53으로 붕괴하고 B채널
> 기울기가 음수로 나온다. 상세는 `binning_report.md` §2.

### 2.4 SNR 이득 이론

n개의 독립 샘플을 평균하면 표준편차는 1/√n로 줄어든다
(σ_binned = σ_single/√n). dB로 환산하면:

```
gain_dB = 20·log10(σ_single/σ_binned) = 20·log10(√n) = 10·log10(n)
```

R/B는 4샘플 평균이므로 `10·log10(4)` ≈ **+6.0 dB**, G는 8샘플 평균이므로
`10·log10(8)` ≈ **+9.0 dB**다.

이 관계는 read-limited든 shot-limited든 성립한다 — SNR은 신호 스케일에
불변이기 때문에, 산탄노이즈가 지배적인 영역이라 해도 "shot-limited에서는
+3 dB만 얻는다"는 원리 문서의 원래 서술(§2.1 참조)은 틀렸다.
`lowlight_isp.md` §2.5가 이를 정정했고, §1에서 이 문서가 검증 대상으로
삼는 것도 이 정정된 +6/+9 dB다.

### 2.5 기존 근거와 재현 가능성

| 근거 | 위치 | 재현 가능성 |
|---|---|---|
| σ(subsample) vs σ(samecolor) 실측 표(신호준위 100/400/1600에서 +5.6~+7.1 dB) | `lowlight_isp.md` §2.5 | **불가 — 원본 스크립트 없음.** "합성 Poisson-Gaussian 프레임, denoise OFF로 binning만 분리"라고만 서술되어 있고, 저장소 전체(현재 tree, `archive/`, 두 워크트리)를 검색해도 이 표를 만든 스크립트가 없다. 파라미터(프레임 크기, 신호준위 선택 근거, 반복 횟수)도 기록이 없어 표만으로는 재현할 수 없다. |
| binning 알고리즘 자체(`BIN_BINNING` vs `BIN_SUBSAMPLE`) | `isppipeline/sw/gen_lowlight_isp_golden.py`의 `binned_raw()` (line 120) | ✅ 라이브 트리, 정본 구현. 아래 §3이 이 함수를 그대로 시뮬레이션 대상으로 삼는다. |
| 검출 mAP 수준 교차검증(같은-색 vs subsample) | `isppipeline/hls/results/v2-arm-ablation-2026-08-06.md` §0.2 | ✅ 라이브 트리. **결과가 엇갈린다**: `data/split_nod` 야간 100장에서 mAP@[.5:.95] −0.0022, mAP@50 +0.0085. "합성 프레임의 +5.6~7.1 dB SNR 이득은 검출 mAP의 일관된 이득으로 이어졌다고 볼 수 없다"고 문서 자신이 명시. |
| gamma 교체 후 재측정(같은 비교, 배포 커브 기준) | `.claude/worktrees/hw-interface-prompt/isppipeline/hls/results/gat-tone-ablation-2026-08-06.md` §5 (**현재 브랜치엔 없음** — `docs/gat-doc-consistency-2026-08-06` 브랜치, 해당 워크트리에만 존재) | 참고용 인용만. same-color가 subsample을 +0.0185/+0.0360으로 앞선다 — GAT 기준(+0.0040/+0.0281)보다 뚜렷해졌다는 결과. 이 리포에 사본을 두지 않기로 했으므로(사용자 결정) 원본 경로만 인용한다. |

**요약**: 알고리즘 구현과 그 검출-수준 mAP 효과는 재현 가능한 근거가 있다.
그러나 "SNR 자체가 이론값만큼 개선되는가"라는 물리 수준의 주장은 **재현
불가능한 표 하나**로만 뒷받침되고 있다 — 이게 이 문서가 채우려는 공백이다.

## 3. 시뮬레이션 방법 (구현 완료 — binning_sim.py, binning_report.md 참고)

### 3.1 합성 데이터 생성

§2.2/§2.3의 캘리브레이션된 Poisson-Gaussian 파라미터를 그대로 쓴다
(재도출하지 않음):

```python
A_Q8 = 4065   # a = 15.878 DN (shot-noise 기울기)
B_DN2 = 746   # b = 746 DN^2 (sigma_read = 27.3 DN)
```

노이즈 모델: `variance(y) = (A_Q8/256) * y + B_DN2`. 각 Bayer 사이트 값을
`y ~ max(0, round(true_signal + N(0, sqrt(variance(true_signal)))))`로
생성한다(음수 방지 위해 0에서 clip — 이 clip 자체가 BLC 문서(`blc.md`)가
다루는 편향의 원천이므로, binning 단계 자체의 SNR만 격리하려면 clip 이후의
raw 도메인 신호를 그대로 두고 BLC/gain은 적용하지 않은 채 측정한다).

- **프레임 크기**: 64×64 Bayer 그리드 (16×16 binned 출력) — 반복 수렴에
  충분하고 계산량이 작다.
- **신호준위**: 기존 표의 3점(100/400/1600)보다 촘촘하고 넓게, **log 간격
  16점**으로 확장한다 — `0, 8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512,
  768, 1024, 1536, 2048, 3072` (12-bit DN, 배수 ≈1.5×). 하한(16)은
  `BLC_LEVEL12=32`의 절반, 즉 pedestal 바로 아래에서 클리핑이 시작되는
  구간을 포함하도록 잡았고, 상한(3072)은 `RAW12_MAX=4095`의 75%로 포화
  근처에서 분산 추정이 clip으로 왜곡되는 걸 피한다. 이 정도 밀도면 저조도
  실사용 범위(BLC pedestal 근방)부터 중간톤까지 이득이 신호준위에 따라
  어떻게 변하는지 곡선으로 볼 수 있다 — 3점으로는 안 보이던 비선형성(예:
  포화 근처에서 이득이 줄어드는지)이 드러나면 그 자체가 기록할 결과.
- **반복 횟수**: 신호준위당 200회 독립 프레임 생성(시드 고정, `numpy.random.
  default_rng(seed)`로 재현성 보장) — 표준편차 추정 자체의 분산을 줄인다.

### 3.2 측정 대상 함수 — binning 적용 vs 미적용 직접 비교

"binning을 적용했을 때"와 "안 했을 때"를 직접 비교한다 — **binning을 아예
하지 않은 상태(단일 샘플, n=1)를 0 dB 기준선**으로 두고, `BIN_BINNING`을
그 기준선 대비로 측정한다.

`binned_raw()`에는 "no binning" 모드가 없으므로, 시뮬레이션 스크립트에
로컬 함수 `unbinned_raw()`를 추가한다(원본 `gen_lowlight_isp_golden.py`는
수정하지 않음):

```python
def unbinned_raw(raw, width, height, bx, by):
    """No binning at all: one raw Bayer sample per channel, n=1.
    Baseline for measuring binning's SNR gain directly.
    G: two raw sub-pixel sites g0/g1 exist per cell; the true n=1 baseline
    uses only one (g0) -- averaging both would already be a 2-sample bin
    and defeat the purpose of a no-binning baseline."""
    r, g0, g1, b = cell_sites(raw, width, height, bx, by)
    return r, g0, b
```

`isppipeline/sw/gen_lowlight_isp_golden.py`의 `binned_raw(raw, width, height,
bw, bh, bx, by, bin_mode=BIN_BINNING)`와 위 `unbinned_raw()`를 **동일한
합성 프레임**에 대해 호출한다(같은 시드로 생성한 프레임을 두 경로가
공유해야 공정한 비교가 된다 — §2.5 표에 이 보장이 기록돼 있지 않은 것도
재현 불가 사유 중 하나였다).

채널별(R/G/B)로 두 경로의 표본표준편차 σ_none, σ_samecolor를 계산하고,
**σ_none을 분모로 고정한** dB 이득을 잰다:

```text
gain_dB(ch) = 20 * log10(sigma_none[ch] / sigma_samecolor[ch])
```

### 3.3 비교 기준선과 판정 기준

§2.4에서 유도했듯, n(none)=1을 0 dB 기준으로 두면:

| 채널 | n(samecolor) | 기대 gain_dB |
|---|---:|---:|
| R, B | 4 | **+6.0 dB** |
| G | 8 | **+9.0 dB** |

**판정 기준**: 각 신호준위 × 채널에서 측정값이 기대값 ±1.5 dB 범위 밖이면
실패. 16개 신호준위 전부에서 통과해야 "이론값에 부합"으로 판정한다 —
신호준위 의존성이 있다면(예: 포화 근처에서 이득이 줄어듦) 그 자체가 기록할
결과다.

판정 기준 폭(±1.5dB)은 200회 반복에서 기대되는 표본표준편차 추정 오차
(자유도 199 기준 σ의 상대오차 약 5%, dB 환산 약 0.4dB)의 3배 이상으로
설정해 거짓 실패를 피한다.

### 3.4 BLC-순서 상호작용과의 경계 (`lowlight_isp.md` §2.5)

이 시뮬레이션은 BLC 이전 순수 binning만 격리한다. BLC를 먼저 적용한 뒤
평균하는 경로(클리핑 후 평균)와의 비교는 `blc.md` §3의 범위이며, 이 문서는
"두 binning 모드의 SNR 차이"만 다룬다 — 혼동하지 않도록 §4에도 명시.

## 4. 알려진 한계

- 이 시뮬레이션은 **물리적 SNR**만 검증한다. §2.5가 이미 보여주듯 물리적
  SNR 개선이 검출 mAP 개선으로 이어진다는 보장은 없다(v2-arm-ablation의
  엇갈린 결과). 이 문서의 결과를 "SNR이 개선됐다"는 근거로만 쓰고, "그러니
  검출이 개선된다"는 결론으로 확장하지 말 것 — 그 결론은 mAP 실측(§2.5
  표)의 몫이다.
- 200회/16신호준위는 최소 스펙이다. 실측 결과가 판정 경계에 가깝다면
  반복 횟수를 늘려 재확인해야 한다.
- `unbinned_raw()`의 G 채널은 `g0`/`g1` 중 하나를 임의로 고른 것이다(둘 다
  같은 노이즈 분포에서 나온 표본이므로 어느 쪽을 골라도 기댓값은 같지만,
  특정 시행에서 우연히 한쪽이 이상치를 뽑을 수 있다). 반복 횟수(200회)가
  이 표본 편차를 평균으로 눌러주긴 하지만, 결과가 애매하면 `g0`/`g1` 둘 다
  기준선으로 따로 계산해 일치하는지 교차확인하는 걸 권장한다.
- 실센서 프레임(SonyNOD raw_arw)으로 같은 실험을 반복하면 합성 모델의
  타당성 자체를 교차검증할 수 있다 — 이번 스펙 범위 밖이지만 §5의 계획
  산출물에 포함해둔다.

## 5. 산출물 (구현 완료)

- `isppipeline/sw/sim/binning_sim.py` — §3의 생성/측정/판정을 구현.
  `isppipeline/sw/gen_lowlight_isp_golden.py`를 import해서 `binned_raw()`를
  직접 호출하고(알고리즘 재구현 금지 — 원본과의 drift 방지), `unbinned_raw()`
  (§3.2)는 이 스크립트 안에만 로컬로 둔다.
- `isppipeline/sw/sim/binning_results.csv` — 신호준위(16점) × 채널(R/G/B) ×
  경로(none/samecolor) 반복 통계(σ, gain_dB, 판정) 원자료.
- `isppipeline/sw/sim/binning_report.md` (실행 후 자동 또는 수동 생성) —
  §3.3 판정 결과 요약 표. 이 스펙 문서(§1~4)는 고정, 실행 결과는 별도 파일로
  분리해 방법론과 결과를 섞지 않는다.
