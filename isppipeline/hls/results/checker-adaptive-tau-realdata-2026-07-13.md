<!--
=============================================================================
File    : checker-adaptive-tau-realdata-2026-07-13.md
Date    : 2026-07-13 KST
Function: checker-adaptive-tau-realdata-test-plan-2026-07-13.md 시나리오 A
          (ISO 층화 fixed-vs-adaptive tau recall) 실행 결과. checker-status
          -2026-07-10.md §4 "다음 관문" #1(적응 τ 스트라텀 검증)에 대한 첫
          실데이터 답.
Sources : tools/analyze_adaptive_tau_sonynod.py,
          tools/checker_adaptive_tau.py,
          results/adaptive_tau_sonynod_2026-07-13.csv,
          checker-adaptive-tau-realdata-test-plan-2026-07-13.md
=============================================================================
-->
# Checker 적응 τ — SonyNOD 실데이터 검증 결과 (2026-07-13)

## 0. 한계 (먼저 읽을 것)

RAW-NOD Sony 서브셋(321장, test split)은 **전량 저녁/야간 촬영**이다. 이 문서의
숫자는 **recall(야간 장면을 LOW_LIGHT로 정확히 잡는가)만** answer한다.
"정상조도인데 low-light로 오판"하는 false-trigger는 이 데이터셋에 정상조도
비교군이 없어 측정 불가 — PASCALRAW 다운로드 완료 후 별도로 봐야 한다.

또한 ISO 400 이하 구간은 표본이 1~3장뿐이라 통계적으로 약하다. 아래 결론은
그 한계 안에서 읽을 것.

## 1. 처리 규모

- 처리된 프레임: 321 / 321 (누락 0)
- ISO 결측(exiftool 실패) 프레임: 0 / 321
- 스크립트: `tools/analyze_adaptive_tau_sonynod.py` (`checker_adaptive_tau.py`
  재사용, 로직 중복 없음)
- 실행 환경: exiftool 12.40 (root 권한 없이 `.deb` 추출해 사용), rawpy 0.27.0

## 2. ISO 구간별 recall

| ISO bucket | n | C0 recall (dark50>0.80) | C1 recall (dark16>0.62) | adaptive recall |
|---|---:|---:|---:|---:|
| [0, 400) | 1 | 1.000 | 1.000 | 1.000 |
| [400, 800) | 3 | 1.000 | 0.000 | 0.000 |
| [800, 1600) | 3 | 1.000 | 0.667 | 0.667 |
| [1600, 3200) | 8 | 0.875 | 1.000 | 1.000 |
| [3200, 6400) | 24 | 0.958 | 0.750 | **1.000** |
| [6400, 12800) | 282 | 0.996 | 0.993 | 1.000 |

(원본 콘솔 출력 및 프레임별 값은 `results/adaptive_tau_sonynod_2026-07-13.csv`.
30장 스모크런은 `results/adaptive_tau_sonynod_smoke.csv`.)

## 3. 세 스킴 사이에 분류가 갈린 프레임

C0/C1/adaptive 셋 중 하나라도 다르게 분류한 프레임: **13 / 321**.

adaptive가 C1과 다르게 분류한 프레임(가장 가까운 비교 대상): **8 / 321**,
전부 **C1이 놓친 것을 adaptive가 잡은 방향**(recall 개선):

| stem | ISO | dark16 | dark_adaptive | 판정(C1→adaptive) |
|---|---:|---:|---:|---|
| DSC03637 | 3200 | 0.540 | 0.659 | miss → catch |
| DSC03786 | 4000 | 0.564 | 0.965 | miss → catch |
| DSC03585 | 5000 | 0.457 | 0.977 | miss → catch |
| DSC03864 | 4000 | 0.557 | 0.854 | miss → catch |
| DSC03792 | 4000 | 0.599 | 0.978 | miss → catch |
| DSC03859 | 6400 | 0.548 | 0.829 | miss → catch |
| DSC03811 | 4000 | 0.618 | 0.857 | miss → catch |
| DSC03689 | 6400 | 0.504 | 0.846 | miss → catch |

반대로 **ISO 400~1600 구간(n=4)에서는 adaptive가 C0이 잡은 것을 놓친다**(C0=True,
C1=False, adaptive=False로 C1과 같이 실패): DSC03839, DSC03849, DSC03860
(ISO 500), DSC03922(ISO 1250). 이 프레임들은 `adaptive_thr8`이 5~12로 매우
낮게 계산되어(낮은 ISO → 낮은 read-noise floor라는 모델대로 정상 동작)
`dark_adaptive`가 0.12~0.52까지 떨어지고, 이를 **고정된 C1 판정 컷오프
(dark-ratio > 0.62)** 에 그대로 대입하면서 recall을 놓친다.

## 4. 결론

**적응 τ는 이 데이터셋에서 recall을 개선/유지/악화 중 "중간 ISO(3200~6400)에서
개선, 저ISO(≤1600, n=7뿐)에서는 C1과 동일하게 실패"로 나타났다** — 하나의
방향으로 요약되지 않는다.

- **개선이 실제로 있다**: ISO [3200,6400) 구간(n=24, 이 데이터셋에서 두 번째로
  큰 버킷)에서 C1 recall 0.750 → adaptive recall 1.000. 8개 프레임에서
  구체적으로 C1이 놓친 야간 장면을 adaptive가 잡아낸다 — §3.4 캠페인이
  기대했던 방향의 실측 증거.
- **개선이 없는(오히려 나쁜) 구간도 있다**: ISO 400~1600 사이 4개 프레임에서는
  adaptive가 C1과 함께 실패한다. 원인은 τ 모델 자체의 결함이 아니라 **이
  스크립트가 adaptive 경로에도 C1의 고정 판정 컷오프(0.62)를 그대로 재사용**한
  것 — τ(register)는 ISO에 맞게 낮아지는데, 그 결과로 나온 dark-ratio를
  비교하는 문턱값은 안 낮아진다. 이는 스크립트/방법론상의 발견이지
  `checker_adaptive_tau.py`의 버그는 아니다: 실전 배치 시엔 판정 컷오프도
  τ와 함께 재보정하거나, register 값 자체(절대 픽셀 카운트 대신 절대 threshold
  DN)로 직접 판정해야 한다는 뜻이다. 표본이 4장뿐이라 과대해석은 금지.
- **ISO 6400~12800(n=282, 데이터셋의 88%)은 이미 거의 천장(C0/C1/adaptive
  모두 ≥0.99)** — 2026-07-06 벤치마크의 우려(포화된 데이터셋)가 대체로
  맞았다. 이 대다수 구간에서는 "퇴행 없음"이 유일하게 말할 수 있는 것.

**false-trigger 쪽은 이 실행으로 전혀 답할 수 없다** — PASCALRAW 필요, 여전히
미완.

## 5. 다음 단계

1. §3의 "판정 컷오프도 τ와 함께 스케일해야 하는가" 발견을 `checker_adaptive_tau.py`
   설계 문서에 반영할지 결정 (신규 이슈로 등록 권장).
2. ISO ≤1600 구간은 표본이 너무 작다 — PASCALRAW 또는 추가 저ISO 야간 프레임
   없이는 이 구간 결론을 강화할 수 없다.
3. ~~시나리오 B(mAP 재확인)는 §3에서 실제로 13개 프레임이 갈렸으므로 진행할
   가치가 생겼다~~ → §6에서 실행 완료.

## 6. 시나리오 B (mAP 재확인) — 실행 결과 (2026-07-13, 후속)

계획: `checker-adaptive-tau-scenario-b-plan-2026-07-13.md`. §3에서 갈린
13프레임(개선 방향 8 + 회귀 방향 4 + 회색지대 1)을 `build_sonynod_dataset.py`로
서브셋 빌드 후 `archive/eval_map_newrm.py`로 `normal`/`lowlight` 강제 arm
mAP를 직접 비교(GPU: RTX 5060 Laptop, ultralytics 8.4.90, yolov8n).

- 서브셋 빌드: `converted=13 skipped=0 no_gt=0 total=13` (13장 전부 GT 포함,
  스킵 없음).
- 결과 (`results/map_newrm_sonynod_flip13_yolov8n.csv`):

| arm | mAP@[.5:.95] | mAP@50 | Precision | Recall |
|---|---:|---:|---:|---:|
| normal | 0.1511 | 0.3161 | 0.928 | 0.284 |
| lowlight | **0.1808** | **0.3608** | 0.950 | 0.304 |

`lowlight` arm이 `normal` 대비 mAP@[.5:.95] +19.7%, mAP@50 +14.1%, Precision·
Recall도 둘 다 소폭 개선 — 이 13장에 한해서는 **§4 계획 문서의 "해석" 기준으로
개선 방향이 확인됨**: adaptive τ가 재분류한 프레임들을 `lowlight`로 처리하는
것이 이 13장에서는 실제 detection에도 유리했다. §2의 recall 개선(ISO
[3200,6400) 0.750→1.000)이 mAP에서도 뒷받침되는 결과다.

**단, 계획 문서 §4가 미리 경고한 대로 13장은 통계적으로 작은 표본이다.**
이 mAP 차이가 8개 recall-개선 프레임 때문인지, 4개 회귀 프레임이나 1개
회색지대 프레임의 우연한 기여인지는 이 집계만으로 분리되지 않는다(arm별
per-frame AP를 뽑지 않았음 — 필요하면 재실행 시 `--limit`을 프레임 단위로
쪼개거나 스크립트에 per-image 출력을 추가해야 함). PASCALRAW 도착 후 정본
재평가가 여전히 최종 근거라는 계획 문서의 입장은 유지.
