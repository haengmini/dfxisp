<!--
=============================================================================
File   : checker-adaptive-tau-scenario-b-full321-plan-2026-07-13.md
Date   : 2026-07-13 KST
Function: 시나리오 B(mAP 재확인, 갈린 13프레임 한정)를 321장 전체로 확장하는
          실행 계획. 실행 전 반드시 읽어야 할 기존 caveat 하나를 §0에 먼저
          적는다 -- 이걸 모르고 그냥 재실행하면 숫자만 재생산하고 끝난다.
Context : 사용자가 "전체 데이터셋에 대해 할 필요는 없어?"라고 물어 확인 결과
          "시나리오 B를 321장 전부에" 진행하기로 함. 단, 321장 중 308장은
          C0/C1/adaptive 세 스킴이 전부 동일하게 LOW_LIGHT로 분류하므로,
          이 308장을 normal/lowlight 강제 arm으로 다시 돌리는 것은 이미
          2026-07-06 벤치마크(realraw-sonynod-benchmark-2026-07-06.md §5)가
          만든 숫자(normal=0.0216/0.0560, lowlight=0.0356/0.0793)를 그대로
          재생산할 가능성이 높다 -- 새 정보가 거의 없다.
Sources : results/checker-adaptive-tau-realdata-2026-07-13.md §6,
          results/realraw-sonynod-benchmark-2026-07-06.md §5,
          performance-scenario-lowlight-review-2026-07-09.md (Drive, §1 "핵심 문제"),
          tools/archive/eval_map_newrm.py, tools/archive/eval_map_ver1.py
=============================================================================
-->
# Checker 적응 τ — 시나리오 B 321장 전체 확장 계획 (2026-07-13)

## 0. 실행 전 반드시 알아야 할 것 — ver0 파이프라인의 공정성 문제

오늘 13프레임 결과와 2026-07-06 원 벤치마크(321장) 둘 다 **같은 스크립트
(`tools/archive/eval_map_newrm.py` + `tools/archive/newrm_pipeline.py`,
"ver0/legacy")로 만들어졌다.** 이 스크립트는 Drive에 있는
`performance-scenario-lowlight-review-2026-07-09.md`가 이미 지적한 알려진
결함을 갖고 있다:

> ver0의 `normal` arm은 BLC+AWB만 하고 gain도 gamma도 걸지 않는다(identity에
> 가까움). 반면 `lowlight` arm은 binning+gain1.25x+gamma4.0을 전부 건다.
> 즉 SonyNOD의 crossover는 "정상용 RM vs 저조도용 RM"의 공정한 대결이
> 아니라 "**아무것도 안 한 것 vs 풀 처리한 것**"의 대결일 위험이 있다.

즉 오늘 13프레임에서 나온 "`lowlight`가 `normal`보다 +19.7%" 결과도 **일부는
"저조도 RM이 우수하다"가 아니라 "아무 처리도 안 한 것보다 뭐라도 처리한 게
낫다"는 아티팩트일 수 있다.** 같은 문서는 해결책도 이미 제시해뒀다 —
`tools/archive/eval_map_ver1.py`(+ `isp_pipeline_ver1.py`)로 재실행하면
`normal` arm도 gain1.25x+gamma를 받아 공정한 비교가 된다. **이 스크립트는
이미 레포에 있고 실행만 하면 된다**(2026-07-09에 권고됐으나 아직 한 번도
실행되지 않음).

그래서 이 문서는 두 갈래로 나눈다: **§1(빠른 재확인, ver0)**과
**§2(공정한 재확인, ver1 — 더 가치 있음, 권장)**. 시간이 없으면 §2만
해도 된다.

## 1. (선택, 빠른 확인) ver0로 321장 전체 재실행

이미 07-06에 한 번 나온 숫자를 오늘 환경(같은 GPU, 같은 ultralytics
버전)으로 재생산해 "환경 차이로 숫자가 달라지지 않는가"만 확인하는
용도다. 새로운 결론을 기대하지 말 것.

```bash
cd isppipeline/hls/tools
# 전체 321장 빌드 (없으면)
python3 build_sonynod_dataset.py \
    "<Drive 동기화 경로>/dataset/Sony/RAW-NOD/annotations/Sony/raw_str_labeled_new_Sony_RX100m7_test.json" \
    "<Drive 동기화 경로>/dataset/Sony/Sony-ARW" \
    ../../../data/sonynod_test

PYTHONPATH=. python3 archive/eval_map_newrm.py \
    --root ../../../data/sonynod_test \
    --tag SonyNOD-full \
    --arms normal,lowlight \
    --limit 321 \
    --model yolov8n.pt \
    --out ../results/map_newrm_sonynod_full321_ver0_yolov8n.csv
```

기대치: `normal≈0.0216/0.0560`, `lowlight≈0.0356/0.0793`(07-06과 거의 동일)
근처면 "환경은 문제 아니었다"만 확인하고 끝. 크게 다르면 그게 오히려
흥미로운 신호(환경/모델버전 차이 조사 필요).

## 2. (권장) ver1로 321장 전체 재실행 — 공정한 비교

`normal` arm에도 gain/gamma를 주는 공정한 파이프라인으로, **07-06 벤치마크
이후 한 번도 실행된 적 없는 새 정보**다.

```bash
cd isppipeline/hls/tools
PYTHONPATH=. python3 archive/eval_map_ver1.py \
    --root ../../../data/sonynod_test \
    --tag SonyNOD-full \
    --arms normal,lowlight \
    --limit 321 \
    --model yolov8n.pt \
    --out ../results/map_ver1_sonynod_full321_yolov8n.csv
```

(§1을 이미 실행해 `data/sonynod_test`가 있으면 재사용 가능 — build 단계
생략.)

## 3. 해석 기준

- **§2(ver1)에서도 `lowlight > normal`이 유지되면**: crossover가 "아무것도
  안 한 것 vs 처리한 것" 아티팩트가 아니라 진짜 저조도 RM의 이득이라는
  훨씬 강한 근거 — `RESEARCH.md` §1.3 주장1을 real-RAW로 확정할 수 있다.
- **§2에서 격차가 크게 줄거나 뒤집히면**: 오늘 13프레임 결과(및 07-06
  원 벤치마크)가 부분적으로 ver0의 공정성 결함 때문이었다는 뜻 — 정직하게
  그렇게 기록하고, `checker-adaptive-tau-realdata-2026-07-13.md` §6에
  "ver0 한정 결과였음"이라는 정정 노트를 추가할 것.
- §1과 §2를 **반드시 둘 다 표로 나란히 남길 것** — 어느 쪽 파이프라인
  기준인지 헷갈리지 않도록 CSV 파일명에 `ver0`/`ver1`을 붙여뒀다(위 커맨드
  참고).

## 4. 결과 저장

`results/checker-adaptive-tau-realdata-2026-07-13.md`에 "§7 시나리오 B —
321장 전체(ver0/ver1)" 섹션을 추가. §2(ver1) 결과가 이 캠페인 전체의
신뢰도를 좌우하므로 반드시 포함할 것.
