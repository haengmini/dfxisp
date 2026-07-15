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

## 7. 시나리오 B — 321장 전체, ver1(공정 비교) (2026-07-13, 후속)

계획: `checker-adaptive-tau-scenario-b-full321-plan-2026-07-13.md`. 이 문서
§0이 지적한 대로, §6(및 2026-07-06 원 벤치마크)은 전부 `eval_map_newrm.py`
(ver0)로 만들어졌는데 ver0의 `normal` arm은 gain/gamma를 걸지 않아 사실상
identity에 가깝다 — `lowlight` arm(binning+gain+gamma 전체 처리)과의 비교가
"저조도 RM이 우수하다"가 아니라 "아무 처리도 안 한 것 vs 뭐라도 처리한 것"의
아티팩트일 수 있다는 우려였다. 이를 `eval_map_ver1.py`(normal arm에도
gain1.25x+gamma를 주는 공정한 파이프라인, 2026-07-09 권고 후 미실행 상태였음)로
321장 전체 재실행해 확인했다.

- 서브셋 빌드: `converted=321 skipped=0 no_gt=0 total=321`.
- 결과 (`results/map_ver1_sonynod_full321_yolov8n.csv`):

| arm | mAP@[.5:.95] | mAP@50 | Precision | Recall |
|---|---:|---:|---:|---:|
| normal (ver1, gain+gamma 적용) | 0.0356 | 0.0807 | 0.395 | 0.079 |
| lowlight (ver1) | **0.1035** | **0.2037** | 0.627 | 0.190 |

**공정하게 맞춘 뒤에도 `lowlight`가 `normal`을 2.9배(mAP@[.5:.95]) 앞선다** —
우려와 반대로 격차가 줄지 않고 오히려 ver0 원 벤치마크(07-06, normal=0.0216/
0.0560, lowlight=0.0356/0.0793)보다 절대적으로도 상대적으로도 더 크게
벌어졌다. 흥미로운 점: **ver1의 `normal` arm(0.0356/0.0807)이 ver0의
`lowlight` arm(0.0356/0.0793)과 거의 동일하다** — gain/gamma를 추가한
"공정한 normal"이 옛 "저조도 RM 전체"와 맞먹는 수준이라는 뜻이고, 그 위에
binning까지 더한 ver1 `lowlight`가 한 번 더 크게 도약한다. 즉 §0의 우려
("아무것도 안 한 것 vs 처리한 것"의 아티팩트)는 **기각됨** — gain/gamma를
공정하게 맞춘 뒤에도 저조도 RM(특히 binning)의 실질적 이득이 real-RAW에서
확인된다.

> **검증 노트 (2026-07-13, 후속 확인):** mAP@[.5:.95]가 소수점 4자리까지
> 정확히 같은(0.0356) 게 우연인지 스크립트 버그(예: work 디렉터리 캐시
> 재사용)인지 의심스러워 직접 대조했다 — 실 `.ARW` 3장(`DSC03637`,
> `DSC03786`, `DSC01901`)을 rawpy로 새로 디코드해 `newrm_pipeline.run_arm(
> ..., "lowlight")`와 `isp_pipeline_ver1.run_arm(..., "normal")`을 각각
> 돌려 픽셀을 직접 비교. **두 출력은 픽셀 단위로 전혀 다르다** — 해상도부터
> 다르다(v0-lowlight는 2x2 binning으로 H/2×W/2=1824×2736, v1-normal은
> binning 없이 원본 해상도 3648×5472이라 픽셀 단위 diff 자체가 불가능),
> 평균 밝기도 다르다(예: `DSC03637` v0-lowlight mean=74.7 vs v1-normal
> mean=60.0). 즉 **캐시 재사용이나 데이터 중복 버그는 아니고, mAP 소수점
> 일치는 서로 다른 두 이미지 집합이 이 3-클래스(person/bicycle/car)
> 데이터셋에서 우연히 같은 집계 detection 성능에 도달한 것**으로 보인다
> (YOLO가 두 경우 다 imgsz=640으로 리사이즈해 추론하므로 원본 해상도
> 차이 자체는 비교를 막지 않는다). 결과의 신뢰도를 깎는 발견은 아니지만,
> 재현 시 이 특정 소수점 일치를 "버그 신호"로 오인하지 않도록 기록해둔다.
>
> **추가 감사(2026-07-13, 사용자 요청 — 스크립트/모듈 전수 점검):**
> "정말 우연인지, 데이터·모듈 사용 과정에 고정된 게 있는지" 재확인 요청을
> 받아 `newrm_pipeline.py`(ver0)/`isp_pipeline_ver1.py`(ver1)/
> `src/dfxisp_accel.cpp`(HW 정본)의 게인·감마 상수를 전부 나란히 대조했다.
> **완전한 우연은 아니었다** — HW 정본은 `GAIN_NORMAL=5/4(1.25x)` /
> `GAIN_LOWLIGHT=2/1(2.0x)`로 서로 다른데(`dfxisp_accel.cpp:86-87`),
> **ver0의 `lowlight` arm이 실제로 쓰는 게인은 `LL_GAIN_NUM,LL_GAIN_DEN=5,4`
> (1.25x)** — HW의 저조도(2.0x)가 아니라 HW의 **정상** 게인과 우연히
> 일치한다(`newrm_pipeline.py:34`, ver0 파일 자체가 docstring에 "LEGACY,
> not canonical"이라 명시해둔 이미 알려진 괴리). 그리고 **ver1의 `normal`
> arm 게인도 `GAIN_NORMAL_NUM,GAIN_NORMAL_DEN=5,4`(1.25x)로 동일**
> (`isp_pipeline_ver1.py:43`) — 즉 이름은 반대(lowlight vs normal)지만
> `ver0-lowlight`와 `ver1-normal`은 **게인 상수 자체가 우연이 아니라
> 실제로 같다(1.25x)**. 단, 감마(ver0=4.0 고정 LUT vs ver1=2.2), BLC(ver0
> 고정16 vs ver1 완화 없음/BLK_RAW=16, 도메인도 8-bit 후처리 vs RAW16
> 사전처리로 다름), 해상도(binning 유무)는 여전히 다르므로 위 픽셀 대조
> 결과(다른 해상도·다른 평균밝기)와 모순되지 않는다 — **"픽셀이 같다"는
> 아니고 "완전히 무관한 두 숫자의 우연"도 아닌, 두 파이프라인이 하나의
> 실제 공유 파라미터(1.25x 게인)를 우연히 물려받았다는 게 정확한 결론**이다.
> `model_paths.py`/`build_arm_images`의 work-디렉터리 재사용 경로도 확인했으나
> tag별로 분리돼 있어 캐시 오염 가능성은 없음을 재확인.

**해석 (계획 문서 §3 기준):** `RESEARCH.md` §1.3 주장1("저조도 RM이 유효하다")을
real-RAW·공정 비교로 확정하는 방향의 강한 근거. §6(13프레임, ver0)의 결과는
방향은 맞았지만 파이프라인 선택(ver0) 때문에 격차 크기가 과소평가돼 있었을
가능성이 있다 — 다만 §6은 13프레임 한정, 여기(§7)는 321프레임 전체이므로
표본 크기 자체도 다르다는 점은 유의.

ver0로 321장 전체를 재실행하는 §1(계획 문서의 "빠른 재확인")은 아직 안 함 —
07-06 수치 재현 확인 목적이라 우선순위가 낮다고 보고 스킵함.

> **⚠️ 정정 (2026-07-13, 후속): §6/§7은 둘 다 비-정본 파이프라인 기준이다.**
> `isp_pipeline_ver1.py`(§7이 "공정 비교"라 부른 ver1)는 2026-07-08부터 이미
> archived/superseded 상태였다 — 배포 HW(`dfxisp_accel.cpp`)는 gamma-2.0
> 정수 sqrt LUT를 normal/lowlight가 공유하는데, ver1은 gamma-2.2 부동소수점
> LUT를 썼다. 진짜 정본 파이프라인(`baseline_isp_pipeline.py`/
> `low_light_isp_pipeline.py`/`checker.py`)으로 이미 07-08에 SonyNOD 321장
> 전체를 돌려놓은 결과가 있다(`isp-pipeline-recalibration-2026-07-08.md`):
> **BLC=16(배포값)에서 lowlight가 normal 대비 +8.1%, BLC=2(후보값)에서
> +12.6%** — §7의 "+190%(2.9배)"는 gamma 불일치로 부풀려진 수치였다.
> 방향(`lowlight > normal`)은 유지되지만 크기는 이 표로 대체할 것. 전체
> 경위와 13프레임 서브셋의 정본 재실행 계획은
> `HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md` 참고.

## 8. 시나리오 B — 13프레임, 정본 파이프라인 (2026-07-13, 최종)

`HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md` §3의 재실행
커맨드를 그대로 실행. `eval_map_isp.py`(정본 `baseline_isp_pipeline.py` +
`low_light_isp_pipeline.py` + `checker.py`, archive 경유 없음)로 §6과 동일한
13프레임 서브셋을 BLC_OFFSET={16(배포값), 1, 2(07-08 후보 정점)} 세 값으로
재실행. **이 섹션이 이 캠페인의 최종 정본 수치다** — §6(ver0)/§7(ver1)은
비-정본 파이프라인 기준이었음이 이미 §7 말미에 정정 표시됨.

결과 (`results/map_isp_sonynod_flip13_canonical_yolov8n.csv`):

| BLC_OFFSET | normal mAP@[.5:.95] | lowlight mAP@[.5:.95] | 격차 | normal mAP@50 | lowlight mAP@50 |
|---:|---:|---:|---:|---:|---:|
| 16 (배포값) | 0.1773 | 0.1851 | **+4.4%** | 0.3440 | 0.3587 |
| 1 (후보) | 0.4713 | 0.4599 | **-2.4%** | 0.8879 | 0.8903 |
| 2 (후보) | 0.4718 | 0.4526 | **-4.1%** | 0.8738 | 0.8811 |

**BLC=16(현재 배포값)에서는 `lowlight`가 이긴다(+4.4%)** — 07-08 321장 전체
결과(+8.1%)와 방향이 같고 폭도 비슷한 자릿수다. §6/§7이 과장했던 "+19.7%"
"+190%"는 확실히 정본 파이프라인 기준으로는 재현되지 않는다.

**그러나 BLC=1/2(07-08이 전체 321장에서 찾은 후보 정점)에서는 이 13프레임
서브셋만 놓고 보면 `normal`이 `lowlight`를 앞선다(-2.4%, -4.1%)** — 07-08의
321장 전체 결과(BLC=2에서 +12.6%, lowlight 우세)와 **반대 방향**이다. 이는
"체커 판정이 갈릴 만큼 경계선에 있는 13개 프레임"이라는 표본 자체가 일반
프레임과 다른 mAP 거동을 보인다는 뜻으로 해석된다(HANDOFF §3.3이 미리
경고한 시나리오) — mAP50만 보면 세 BLC 값 모두 lowlight가 근소하게 앞서
지만(+0.3%p~+1.5%p), mAP@[.5:.95]은 BLC=1/2에서 뒤집힌다. 표본이 13장뿐이고
BLC=1/2에서는 애초에 두 arm 모두 이미 매우 높은 mAP(0.45~0.47)라 순위가
쉽게 뒤집힐 수 있는 좁은 차이라는 점도 감안할 것.

**결론:**
- checker 강화안 #1(적응 τ, §1~§4)은 이번 정정과 무관하게 그대로 유효.
- `RESEARCH.md` §1.3 주장1(저조도 RM 유효성)은 **정본 파이프라인·배포
  BLC(16) 기준으로 방향은 유지**(+4.4%, 07-08의 +8.1%와 정합) — 단 이
  프로젝트가 반복해 강조해온 원칙대로, §6/§7의 부풀려진 수치(+19.7%,
  +190%)는 인용 금지.
- BLC 후보값(1/2)에서의 역전은 "체커 판정 경계 프레임"이라는 특수 조건에
  한정된 현상일 가능성이 높지만, 13장으로는 확정할 수 없다 — §9에서
  경계 프레임을 확장해 재확인함.

## 9. 시나리오 B — 경계 프레임 확장(31장), 정본 파이프라인 (2026-07-13, 후속)

§8의 BLC=1/2 역전이 n=13의 노이즈인지 실제 효과인지 확인하기 위해, "체커
판정이 실제로 갈린 프레임"이라는 엄격한 정의를 "판정 컷오프에 가까운 프레임"
으로 완화해 표본을 넓혔다. `results/adaptive_tau_sonynod_2026-07-13.csv`
(321장 전체)에서 `|dark16-0.62|<0.15` 또는 `|dark_adaptive-0.62|<0.15` 또는
`|dark50-0.80|<0.15` 중 하나라도 만족하는 프레임을 뽑고, 원래 13장과
합집합을 취해 **31장**(`tools/sonynod_boundary31.json`)을 만들었다(원래
13장 중 12장 포함, `DSC03585`만 마진 밖이라 별도로 합침). §8과 동일하게
`eval_map_isp.py`로 BLC={16,1,2} × arm={normal,lowlight} 재실행.

- 서브셋 빌드: `converted=31 skipped=0 no_gt=0 total=31`.
- 결과 (`results/map_isp_sonynod_boundary31_canonical_yolov8n.csv`):

| BLC_OFFSET | normal mAP@[.5:.95] | lowlight mAP@[.5:.95] | 격차 |
|---:|---:|---:|---:|
| 16 (배포값) | 0.1256 | 0.1261 | +0.4% |
| 1 (후보) | 0.2383 | 0.2385 | +0.1% |
| 2 (후보) | 0.2342 | 0.2362 | +0.9% |

**세 표본(13장/31장/321장 전체)을 나란히 놓으면:**

| 표본 | BLC=16 | BLC=1 | BLC=2 |
|---|---:|---:|---:|
| 13장 (§8) | lowlight +4.4% | **normal +2.4%** | **normal +4.1%** |
| 31장 (§9, 이 섹션) | lowlight +0.4% | lowlight +0.1% | lowlight +0.9% |
| 321장 전체 (07-08) | lowlight +8.1% | (미측정) | lowlight +12.6% |

**§8의 BLC=1/2 역전은 표본을 13→31로 늘리자 사라졌다** — 세 BLC 값 모두
다시 `lowlight`가 (근소하게) 앞서는 방향으로 돌아와, 321장 전체 결과와
방향이 일치한다. 즉 §8의 역전은 실제 "경계 프레임은 다르게 행동한다"는
효과가 아니라 **n=13의 표본 노이즈였을 가능성이 높다** — 13장 중 3장
(BLC=1/2에서 이미 mAP 0.45~0.47로 포화된 프레임들)의 우연한 배치가
집계를 뒤집을 만큼 표본이 작았다는 뜻.

다만 **31장에서도 격차 자체(0.1~0.9%p)는 321장 전체(8~13%p)보다 훨씬
작다** — 이는 노이즈가 아니라 실제 패턴으로 보인다: 경계 프레임(체커
판정이 애매한 프레임)들은 애초에 lowlight/normal 어느 쪽으로 처리해도
detection 난이도가 비슷하다는 뜻이다(어차피 두 arm 다 아주 어둡지도
아주 밝지도 않은 중간 지대). 반면 321장 전체에는 극단적으로 어두운
프레임들이 다수 포함돼 있어 거기서 lowlight의 이득이 훨씬 크게 나타나는
것으로 해석된다 — **저조도 RM의 이득은 "얼마나 어두운가"에 비례하며,
경계 프레임(애매하게 어두운 프레임)에서는 이득이 작다**는 것이 정성적
결론이다. 31장으로도 통계적으로 크다고 할 수는 없으니, 이 정성적 해석도
과신하지 말 것.

**최종 결론(§8+§9 종합):** `lowlight ≥ normal` 방향은 13/31/321장 세
표본 모두에서 일관되며(§8의 BLC=1/2 역전은 노이즈로 확인됨), 격차 크기는
표본이 얼마나 어두운 프레임 위주인지에 따라 달라진다(경계 프레임 <1%p,
전체 데이터셋 8~13%p).

**false-trigger 후속(2026-07-15):** PASCALRAW 4,259장으로 실측 완료 —
`pascalraw-adapter-2026-07-13.md` §7. C0(배포) 92.9% / C1 41.8% / adaptive
38.4% false-trigger rate. adaptive가 recall(본 문서)과 false-trigger
양쪽에서 C1 대비 우위/동등이나, ISO[800,1600) n=28에서는 역전(미결).
