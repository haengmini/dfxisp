<!--
=============================================================================
File   : isppipeline/sw/sim/gamma.md
Date   : 2026-08-10 KST (재구성: 2026-08-11)
Function: lowlight_isp stage (5) 톤 커브(gamma 2.0, 이전 제안이던 GAT/VST 포함)
          시뮬레이션 방법론. 네 모듈 중 유일하게 완성된 방법론이 이미
          존재한다 — 단, 그 방법론과 산출물이 현재 브랜치가 아니라 다른
          워크트리에만 있어, 이 문서의 역할은 새로 설계하는 것이 아니라
          "그 방법론을 어떻게 재현하는지" 정리하는 것이다.
Sources: isppipeline/hls/src/lowlight_isp.md §2.1/§2.1.1/§2.1.2, isppipeline/sw/
         gen_lowlight_isp_golden.py, isppipeline/sw/gen_default_isp_golden.py.
         워크트리 전용(현재 브랜치엔 없음, docs/gat-doc-consistency-2026-08-06
         브랜치): .claude/worktrees/hw-interface-prompt/isppipeline/hls/
         results/gat-tone-ablation-2026-08-06.md, .../results/
         denoise-k-sweep-2026-08-06.md, .../tools/calibrate_noise_model.py,
         .../tools/verify_new_arm_pipelines.py.
=============================================================================
-->
# gamma — 톤 커브 시뮬레이션 방법론

## 1. 시뮬레이션 목표

`lowlight_isp.md` §2.1.2가 배포한 결론:

> 교차검증(SSDLite)까지 순위가 재현되어 GAT를 철회하고 stage ⑤를 gamma
> 2.0으로 교체했다.

이 결론에 이르기까지의 주장은 세 겹이다:
1. GAT(Generalized Anscombe Transform)는 원점에서 선형이라 read-noise floor
   과증폭을 피한다는 **설계 의도**(§2.1).
2. 그럼에도 실측 검출 mAP는 **gamma 2.0 > GAT > linear** 순서라는 **반증**(§2.1.1).
3. 이 순서가 YOLOv8n·SSDLite MobileNetV3 **두 검출기 모두**에서 재현된다는
   **교차검증**(§2.1.1 말미).

**이 문서가 검증할 것**: 이 결론에 이른 방법론이 실제로 얼마나 엄밀했는지
정리하고, 재현 절차를 명시한다. 다른 세 모듈(blc/gain/binning)과 달리 이
모듈은 이미 완성된 방법론이 존재하므로(§2.4), §3은 "신규 설계"가 아니라
"흩어진 걸 모아 재현 가능하게 만드는 것"이 과제다.

## 2. 시뮬레이션 이론

### 2.1 GAT(Generalized Anscombe Transform) 설계 의도

Poisson-Gaussian 노이즈에서 분산을 안정화하는 표준 분산안정화변환(VST)이
GAT다. 원점 근방에서 선형이라는 성질 때문에, 감마 커브처럼 어두운 영역을
강하게 들어올리지 않아 read-noise floor를 과증폭시키지 않는다는 것이
채택 배경의 설계 의도였다(`lowlight_isp.md` §2.1).

### 2.2 gamma 2.0 톤 커브

배포된 톤 커브는 단순 gamma 2.0(제곱근) LUT다:
`gen_default_isp_golden.py`의 `GAMMA2_LUT = [isqrt(255*v) for v in range(256)]`,
`gen_lowlight_isp_golden.py`의 `tone_lut(TONE_GAMMA)`가 정본 구현이다.
GAT LUT 자체(`gat_lut()`/`GAT_LUT`, `A_Q8`/`B_DN2` 상수)도 런타임 스위치는
없지만 golden 생성기 안에 `TONE_GAT`으로 여전히 남아 있어 재현 가능하다.

### 2.3 노이즈 모델 캘리브레이션 (배경)

GAT의 `a, b` 파라미터는 단일영상 photon-transfer(8×8 블록, 저백분위+χ²
편향보정, `mean<512` 구간 선형적합) 방식으로 SonyRX100VII 야간 ARW 91장
(ISO6400)에서 실측되어 `A_Q8=4065`, `B_DN2=746`으로 캘리브레이션됐다
(`calibrate_noise_model.py`, 워크트리 전용). GAT는 철회됐지만 이 상수는
`gen_lowlight_isp_golden.py`에 이미 반영돼 있고(binning.md/blc.md의
노이즈 모델과 동일 값), `binning.md`/`blc.md`가 재사용하는 값도 바로 이
캘리브레이션 결과다 — GAT를 재검토하지 않는 한 재도출 불필요.

### 2.4 기존 근거와 재현 가능성 — 네 모듈 중 유일하게 완비된 사례

| 근거 | 위치 | 재현 가능성 |
|---|---|---|
| 단일 축 4-arm 톤 커브 ablation(gamma2.0/GAT/linear/GAT+구binning) | `gat-tone-ablation-2026-08-06.md` | **현재 브랜치엔 없음.** `.claude/worktrees/hw-interface-prompt/isppipeline/hls/results/gat-tone-ablation-2026-08-06.md` (브랜치 `docs/gat-doc-consistency-2026-08-06`, 커밋 `334a293`가 tip)에만 존재. 사용자 결정에 따라 이 리포로 복사하지 않고 경로만 인용한다. |
| binning/BLC/WB/CCM을 고정하고 stage ⑤만 격리 | 위 문서 §2 | 방법 자체는 재현 가능 — `data/split_nod` 야간 100장, YOLOv8n 1차 측정, `tools/eval_map_newrm_ssd.py`(torchvision SSDLite MobileNetV3)로 2차 교차검증. **다만 `eval_map_newrm_ssd.py`도 현재 브랜치엔 없다**(`isppipeline/hls/tools/`가 대부분 삭제된 상태 — README 참고). |
| bit-exact 정합성 게이트(`make verify-new-arms`) | `verify_new_arm_pipelines.py` | **현재 브랜치엔 없음.** 워크트리 전용. 40회 시행 × 7형상 × 4콘텐츠모드 × binning 2종 × tone 3종 전조합, 15,966 채널 샘플. |
| GAT의 `a, b` 파라미터 캘리브레이션(비록 GAT는 철회됐지만 배경 이해에 필요) | `calibrate_noise_model.py` | **현재 브랜치엔 없음.** 워크트리 전용. §2.3의 캘리브레이션 절차. 이 상수는 `gen_lowlight_isp_golden.py`에 이미 반영돼 있다(현재 브랜치도 포함) — **스크립트는 없어도 결과 상수는 라이브 트리에 있다.** |
| denoise 제거와 톤 커브 경쟁의 인과관계 | `denoise-k-sweep-2026-08-06.md` | **현재 브랜치엔 없음.** 워크트리 전용. `lowlight_isp.md` §2.2가 요지를 이미 인라인으로 요약해뒀으므로(denoise가 k∈{1.0,1.5,2.4,4.0} 전 구간에서 mAP 이득을 못 만듦), 원본 없이도 결론은 라이브 트리 문서로 확인 가능. |
| gamma 2.0 LUT 자체(배포 구현) | §2.2 | ✅ 라이브 트리, 정본. |
| GAT LUT 자체(ablation 전용, 배포 안 됨) | §2.2 | ✅ 라이브 트리 — GAT 곡선 자체는 지금도 재현 가능하다(런타임 스위치는 없지만 golden 생성기에는 `TONE_GAT`으로 남아있음). |

**요약**: 이 모듈은 "새로 설계"가 아니라 "**흩어진 걸 모아 재현 가능하게
만드는 것**"이 과제다. 방법론의 뼈대(캘리브레이션 → 4-arm 격리 ablation →
2-검출기 교차검증 → bit-exact 정합성 게이트)는 이미 완성돼 있다.

## 3. 시뮬레이션 방법 (기존 방법론 재현)

### 3.1 1단계 — 노이즈 모델 캘리브레이션 (배경, 재실행 불필요)

`A_Q8=4065`, `B_DN2=746`은 이미 `gen_lowlight_isp_golden.py`에 반영돼 있다
(§2.3). GAT 자체를 재검토하지 않는 한 이 단계를 다시 돌릴 필요는 없다 —
재현할 경우에만 `calibrate_noise_model.py`(워크트리에서 확보)를 SonyNOD
raw_arw 소스에 대해 실행한다.

### 3.2 2단계 — bit-exact 정합성 게이트

스칼라 golden(`gen_lowlight_isp_golden.py`, `gen_default_isp_golden.py`)과
벡터화 numpy 프록시(`lowlight_isp_pipeline.py`, `default_isp_pipeline.py`,
현재 브랜치에 이미 존재)가 일치하는지 먼저 확인한다 — mAP 측정은 프록시로
하므로, 이 게이트가 실패하면 이후 모든 mAP 수치가 무의미해진다.
`verify_new_arm_pipelines.py`(워크트리 전용)의 조합 — 40 trials × 7 shapes
(1×1, odd dims 포함) × 4 content modes(uniform random/near-floor/extremes/
flat+noise) × binning 2종 × tone 3종 — 을 재현하려면 이 스크립트를
확보하거나(경로만 인용, 복사하지 않기로 함) 같은 조합 규칙으로 새로
작성해야 한다.

### 3.3 3단계 — 단일 축 격리 ablation

`gat-tone-ablation-2026-08-06.md` §2의 조건을 그대로 따른다:
- **고정**: binning(`BIN_SAMECOLOR`), BLC(`BLC_LEVEL12=32`), WB(공유 상수),
  CCM(공유 행렬) — stage ⑤ 톤 커브만 변수.
- **변수(4-arm)**: `TONE_GAMMA`, `TONE_GAT`, `TONE_LINEAR`(`tone_lut()`의
  세 모드를 그대로 사용), 그리고 GAT+구 subsample binning(2026-08-06 개정
  전 baseline과의 비교용).
- **데이터**: `data/split_nod` 야간 100장.
- **검출기 1차**: YOLOv8n.
- **판정 기준**: `lowlight_isp.md` §2.1.1과 동일 — mAP@[.5:.95]와 mAP@50
  두 지표의 부호가 같은 방향이고, 이 프로젝트의 잡음대(~0.005, `blc.md`/
  `gain.md`가 인용하는 것과 동일 기준)의 2배 이상이어야 "차이 있음"으로
  판정.

### 3.4 4단계 — 교차 검출기 검증

같은 렌더(§3.3에서 만든 4-arm 출력)를 SSDLite MobileNetV3(torchvision)로
재채점한다. 판정 기준: 순위(`gamma > GAT > subsample > linear`)가 **두
검출기 × 두 지표 전부(4개 비교)** 에서 동일해야 재현 성공으로 인정한다 —
`lowlight_isp.md` §2.1.1이 명시한 기준(gamma−GAT 효과 크기가 YOLO
+0.0101, SSD +0.0105로 사실상 같음)을 그대로 재현 목표로 삼는다.

### 3.5 5단계 — 배포 전환 후 재검증

`lowlight_isp.md` §2.1.2가 이미 수행한 절차: LUT를 gamma 2.0으로 교체한
뒤 `lowlight_isp` arm을 재측정해 §3.3의 gamma-arm 수치(0.1876/0.3797)와
정확히 일치하는지 확인 — end-to-end 회귀 테스트. 새로 배포를 바꿀 계획이
없다면 이 단계는 생략 가능(현재 배포 상태 확인용).

## 4. 알려진 한계

- 이 문서는 GAT를 재도입하자는 제안이 아니다 — §2.1.2의 철회 결정을
  뒤집을 근거가 나오지 않는 한, 재현 절차는 "결론이 여전히 성립하는지
  확인"하는 회귀 검증 용도로만 쓴다.
- §3.2/§3.4에 필요한 스크립트 4개가 전부 워크트리 전용이라, 이 문서만으로는
  즉시 실행할 수 없다 — 실행하려면 최소 `verify_new_arm_pipelines.py`와
  `tools/eval_map_newrm_ssd.py`(SSDLite 경로) 확보가 선행돼야 한다. 확보
  방법(다른 워크트리에서 복사 vs 새로 작성)은 이 문서의 범위 밖 — 실행
  시점에 별도 결정.
- 주광(PASCAL) 조건에서의 톤 커브 재확인은 `lowlight_isp.md` §6 "남은 일"
  항목 5에 아직 미측정으로 남아있다 — 이 문서의 §3 절차를 `data/split_nod`
  대신 PASCAL 100장에 그대로 적용하면 그 공백을 채울 수 있다(별도 실행
  과제로 남겨둠).

## 5. 계획 산출물 (구현 시)

- `isppipeline/sw/sim/gamma_report.md` — §3의 5단계를 재실행한 결과를
  `gat-tone-ablation-2026-08-06.md`의 원 수치와 나란히 비교하는 회귀
  리포트(방법론 스펙인 이 문서와는 분리).
- 스크립트는 새로 작성하기보다 워크트리의 `verify_new_arm_pipelines.py`
  / `tools/eval_map_newrm_ssd.py`를 그대로 재사용하는 쪽을 권장(§4의
  확보 결정이 선행돼야 함) — 다른 세 모듈과 달리 이 모듈은 스펙을 새로
  쓰는 것보다 기존 스크립트를 가져오는 편이 중복 작업이 적다.
