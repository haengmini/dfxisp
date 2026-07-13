<!--
=============================================================================
File   : HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md
Date   : 2026-07-13 KST
Function: 노트북(GTX 5060) 에이전트에게 넘기는 인수인계 문서. 오늘 세션에서
          진행한 checker 적응 τ 실데이터 검증(시나리오 A/B)의 mAP 재확인
          부분(시나리오 B)이 이미 archived된 비-정본 파이프라인(ver0/ver1)으로
          수행됐음이 뒤늦게 밝혀져, 정본 파이프라인으로 다시 실행해야 한다.
          이 문서 하나만 읽고도 처음부터 끝까지 이어갈 수 있도록 전체 맥락과
          정확한 재실행 커맨드를 담는다.
Audience: 이 레포를 처음 보는 에이전트(별도 세션/노트북) -- 아래 "0. 결론부터"
          와 "3. 지금 할 일"만 봐도 실행 가능하도록 작성.
Sources : (이 브랜치 exp/adaptive-tau-realdata-2026-07-13의 커밋들, 시간순)
          checker-adaptive-tau-realdata-2026-07-13.md (§1~§7 + 검증노트 2개),
          checker-adaptive-tau-scenario-b-plan-2026-07-13.md,
          checker-adaptive-tau-scenario-b-full321-plan-2026-07-13.md,
          isp-pipeline-recalibration-2026-07-08.md (정본 파이프라인의 출처),
          tools/baseline_isp_pipeline.py, tools/low_light_isp_pipeline.py,
          tools/checker.py, tools/eval_map_isp.py
=============================================================================
-->
# 인수인계 — checker 적응 τ 검증, 정본 파이프라인으로 mAP 재실행 (2026-07-13)

## 0. 결론부터

오늘(2026-07-13) checker 적응 τ(sensor-adaptive threshold) 실데이터 검증을
SonyNOD(RAW-NOD Sony RX100 VII 서브셋, 321장 test split)로 진행했다. 두
갈래로 나뉜다:

- **시나리오 A(ISO 층화 recall)** — `tools/analyze_adaptive_tau_sonynod.py`.
  **그대로 유효하다, 다시 할 필요 없음.** raw pixel의 dark-ratio를 직접
  계산하는 것이라 어떤 ISP RM 파이프라인(ver0/ver1/정본)을 쓰는지와
  무관하다.
- **시나리오 B(mAP 재확인)** — 13프레임(체커 판정이 갈린 프레임) 그리고
  321프레임 전체를 `normal`/`lowlight` 강제 arm으로 돌려 mAP 비교.
  **여기가 문제다.** 처음엔 `tools/archive/eval_map_newrm.py`(ver0, legacy),
  그다음 "공정 비교"라며 `tools/archive/eval_map_ver1.py`(ver1)를 썼는데,
  **`isp_pipeline_ver1.py`(ver1) 자체가 이미 2026-07-08에 archived되고
  superseded된 파이프라인이었다** — gamma-2.2 부동소수점 LUT를 쓰는데 실제
  배포 HW(`src/dfxisp_accel.cpp`)는 gamma-2.0 정수 sqrt LUT를 normal/
  lowlight 양쪽에 **공유**한다. 이 gamma 불일치 때문에 ver1으로 얻은 격차
  (13프레임 +19.7%, 321프레임 2.9배/+190%)는 **부풀려진 수치**였다.

**진짜 정본 파이프라인**은 `tools/baseline_isp_pipeline.py` +
`tools/low_light_isp_pipeline.py` + `tools/checker.py`(2026-07-08 작성,
07-09 demosaic bilinear fix까지 반영, **archive 안에 없고 `tools/`에
그대로 있음**)이고, 이걸로 이미 2026-07-08에 SonyNOD 321장 전체를
BLC 스윕까지 포함해 돌려놓은 결과가 있다
(`results/map_isp_sonynod_blcfix_yolov8n.csv`,
`results/isp-pipeline-recalibration-2026-07-08.md`):

| BLC_OFFSET | normal | lowlight | 격차 |
|---:|---:|---:|---:|
| 16 (현재 배포값) | 0.0344 | 0.0372 | **+8.1%** |
| 2 (제안/후보값) | 0.1900 | 0.2140 | **+12.6%** |

즉 **방향(`lowlight > normal`)은 여전히 맞지만, 격차는 오늘 ver1로 얻은
+190%가 아니라 +8~13% 수준**이다. 이건 07-08에 이미 확정된 결론이고 오늘
다시 발견할 필요는 없었다 — Scenario B를 시작하기 전에 이 문서를 먼저
찾아봤어야 했는데 놓쳤다.

## 1. 지금까지 이 브랜치(exp/adaptive-tau-realdata-2026-07-13)의 커밋 순서

```text
c24d50a feat: analyze_adaptive_tau_sonynod.py 작성 (시나리오 A 스크립트)
e8e4e8c exp: 시나리오 A 실행 -- ISO 층화 recall, 321장 전체 (그대로 유효)
8a50847 docs: 시나리오 B(13프레임) 계획
bc7adeb exp: 시나리오 B 실행 -- ver0(eval_map_newrm.py)로 13프레임 mAP
             (normal=0.1511/0.3161, lowlight=0.1808/0.3608, +19.7%)
             ⚠️ ver0 결과, 아래 §0 정정 대상
f620762 docs: 시나리오 B를 321장 전체로 확장하는 계획 (ver0 fairness 우려 제기)
76eb970 exp: 321장 전체를 ver1(eval_map_ver1.py, "공정 비교"라 여겼음)로 재실행
             (normal=0.0356/0.0807, lowlight=0.1035/0.2037, 2.9배)
             ⚠️ ver1도 비정본, 아래 §0 정정 대상
ab445d1 docs: normal/lowlight mAP 소수점 일치가 캐시버그 아님을 실 ARW로 검증
b38edd6 docs: ver0-lowlight와 ver1-normal이 게인 상수(1.25x)를 실제 공유함을
             발견 (스크립트 전수 감사) -- 이 감사 중에 ver1 자체가 이미
             archived/superseded라는 사실도 함께 드러남 (이 문서로 이어짐)
```

## 2. 왜 이렇게 됐는지 (교훈 -- 다음에 같은 실수 피하기)

- `tools/archive/`에 있다고 다 "완전히 죽은 코드"는 아니다 -- 파일별로
  archived된 **시점**이 다르다. ver0는 2026-07-02~03 reset 때, ver1은
  2026-07-08 canonical-pipeline 정리 때 각각 archived됐다. "archive에 있으면
  옛날 것"이라고만 보지 말고, **`tools/`(비-archive)에 같은 역할을 하는
  더 최신 파일이 있는지부터 확인**했어야 한다 -- 오늘의 경우
  `baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`가 바로 그것이었다.
- mAP 실험을 새로 설계하기 전에 `results/INDEX.md`에서 같은 데이터셋
  (SonyNOD)을 이미 다룬 문서가 있는지부터 검색했어야 한다 --
  `isp-pipeline-recalibration-2026-07-08.md`가 이미 있었다.

## 3. 지금 할 일 (실행 커맨드)

시나리오 A는 다시 할 필요 없음. **시나리오 B의 13프레임 비교만 정본
파이프라인으로 다시 돌리면 된다** -- 이건 07-08 결과에도 없는 진짜 새
정보다(07-08은 321장 전체 집계고, 13프레임만 따로 뽑은 적은 없음).

### 3.1 13프레임 서브셋 (이미 있으면 재사용)

`data/sonynod_flip13/`가 로컬에 이미 있으면(오늘 시나리오 B에서 만든 것)
이 단계는 생략. 없으면
`checker-adaptive-tau-scenario-b-plan-2026-07-13.md` §2의 필터링 스크립트로
재생성(13개 stem: DSC03637, DSC03786, DSC03585, DSC03864, DSC03792,
DSC03859, DSC03811, DSC03689, DSC03839, DSC03849, DSC03860, DSC03922,
DSC01901).

### 3.2 정본 파이프라인으로 mAP 비교

```bash
cd isppipeline/hls/tools
# PYTHONPATH 불필요 -- baseline_isp_pipeline/low_light_isp_pipeline/checker/
# model_paths 전부 같은 tools/ 안에 있음 (ver0/ver1 때와 달리 archive/ 경유 안 함)
python3 eval_map_isp.py \
    --root ../../../data/sonynod_flip13 \
    --blc-offsets 16,1,2 \
    --arms normal,lowlight \
    --tag SonyNOD-flip13-canonical \
    --model yolov8n.pt \
    --out ../results/map_isp_sonynod_flip13_canonical_yolov8n.csv
```

- `--blc-offsets 16,1,2`: **16이 현재 배포값**(주 비교 대상), 1과 2는
  07-08이 찾은 후보 정점 -- 참고용으로 같이 뽑아둔다.
- 13장뿐이라 CPU로도 금방 끝나지만 GPU(GTX 5060)면 더 빠르다.

### 3.3 해석 기준

- **BLC=16 기준으로 이 13프레임에서도 `lowlight`가 이기는지**가 핵심
  질문. 07-08의 321장 전체 결과(+8.1%)와 비슷한 폭이면, "체커 판정이
  갈리는 프레임"이라는 특수 조건에서도 정본 파이프라인 기준 결론이
  일관됨을 보여주는 것 -- 의미 있는 확인.
- **격차가 07-08의 전체-집계(+8.1%)보다 훨씬 크거나 작으면**, 이 13프레임이
  (체커 판정이 갈릴 만큼 경계선에 있는 프레임이라는 특성상) 일반 프레임과
  다른 mAP 거동을 보인다는 뜻 -- 그 자체로 흥미로운 발견이니 정직하게
  기록.
- **이전(ver0/ver1) 결과와의 관계**: ver0/ver1 결과를 "틀렸으니 삭제"하지
  말고, `checker-adaptive-tau-realdata-2026-07-13.md`에 이미 남겨둔 대로
  "비정본 파이프라인 기준이었음"이라는 정정 표시와 함께 **그대로 보존**할 것
  (관례상 이 프로젝트는 틀린 결과도 지우지 않고 superseded로 표시해왔다 --
  `isp-pipeline-recalibration-2026-07-08.md` §3이 그 전례).

## 4. 결과 저장

`results/checker-adaptive-tau-realdata-2026-07-13.md`에 "§8 시나리오 B --
13프레임, 정본 파이프라인" 섹션 추가. 표에 §6(ver0)/§7(ver1)/§8(정본) 세
결과를 나란히 놓고, §8을 "이 캠페인의 최종 정본 수치"로 명시할 것.
`results/INDEX.md`도 갱신.

## 5. 이 시점 이후 checker 강화안(#1) 전체 상태 요약

- `RESEARCH.md` §1.3 주장1("저조도 RM이 유효하다")은 **여전히 성립** --
  정본 파이프라인·정본 BLC(16)에서도 방향은 유지(+8.1%). 다만 이 프로젝트가
  반복해서 강조해온 "격차 크기를 과장하지 않는다"는 원칙상, +190% 같은
  숫자는 절대 다시 인용하지 말 것.
- checker의 #1(적응 τ) 자체는 시나리오 A 결과(ISO [3200,6400)에서 recall
  0.750→1.000)가 그대로 유효 -- 이건 이번 정정과 무관.
- 남은 진짜 blocker는 여전히 동일: **PASCALRAW**(정상조도 비교군, 다운로드
  중) 도착 전까지 false-trigger 검증은 불가.
