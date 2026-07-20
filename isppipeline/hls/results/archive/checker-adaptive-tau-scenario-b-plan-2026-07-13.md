<!--
=============================================================================
File   : checker-adaptive-tau-scenario-b-plan-2026-07-13.md
Date   : 2026-07-13 KST
Function: 시나리오 A(ISO 층화 recall, 이 브랜치의 e8e4e8c/c24d50a)에서 실제로
          13/321 프레임이 C0/C1/adaptive 사이에 분류가 갈렸으므로, 시나리오 B
          (mAP 재확인)를 진행할 근거가 생겼다. 이 문서는 그 실행 계획이다 —
          아직 실행 전(PLAN), 결과는 별도 문서로 추가될 것.
Context : 시나리오 A 결과 요약 -- adaptive가 C1과 다르게 분류한 8프레임은
          전부 miss(C1=normal) -> catch(adaptive=lowlight) 방향. 반대로
          ISO<=1600 4프레임은 adaptive가 C0이 잡은 걸 놓침(판정 컷오프
          0.62 고정 재사용 탓, 방법론적 발견 -- checker_adaptive_tau.py
          자체 결함 아님). 이 13프레임을 실제 normal/lowlight RM에 통과시켜
          mAP로 "adaptive의 재분류가 실제로 더 나은 선택이었는가"를 본다.
Sources : results/checker-adaptive-tau-realdata-2026-07-13.md,
          results/adaptive_tau_sonynod_2026-07-13.csv,
          tools/build_sonynod_dataset.py, tools/archive/eval_map_newrm.py,
          tools/archive/newrm_pipeline.py
=============================================================================
-->
# Checker 적응 τ — 시나리오 B(mAP 재확인) 실행 계획 (2026-07-13)

## 0. 전제

시나리오 A(이 브랜치에 이미 커밋됨, `checker-adaptive-tau-realdata-2026-07-13.md`)
에서 C0/C1/adaptive 판정이 갈린 프레임이 13/321장 나왔다 — 그 문서 §3 참고.
이 13장만 골라 `normal`/`lowlight` RM을 실제로 통과시켜 mAP를 비교한다.
**8장(C1→adaptive 개선 방향)이 핵심 관심 대상**이고, 4장(adaptive 회귀
방향)은 부수 확인용이다. 나머지 1장(`DSC01901`, ISO 2500 — C0만 다르고
C1/adaptive는 일치하는 회색지대 케이스)도 아래 스크립트에 포함해뒀다.

**주의 — 이름 충돌:** `newrm_pipeline.py`의 `adaptive` arm은 "checker가
normal/lowlight를 자동 선택"이라는 뜻이고, 이 세션에서 말하는 "적응 τ"와는
**다른 개념**이다(전자는 RM 선택 방식, 후자는 판정 임계값 자체). 이 시나리오는
`adaptive` arm을 쓰지 않고 **normal/lowlight 두 강제 arm만** 직접 비교한다 —
"이 13장을 normal로 처리하는 게 나은가, lowlight로 처리하는 게 나은가"를
mAP로 직접 재는 것이지, checker 자동선택 로직을 다시 테스트하는 게 아니다.

## 1. 알려진 경로 문제 (미리 적어둠)

`eval_map_newrm.py`와 `newrm_pipeline.py`는 `tools/archive/`로 이동돼 있다
(과거 문서 정리 커밋). `eval_map_newrm.py`는 `model_paths.py`(archive 밖,
`tools/`에 있음)를 import한다 — 그냥 실행하면 `ModuleNotFoundError:
model_paths`가 난다. `tools/`를 `PYTHONPATH`에 추가해서 실행할 것(아래
커맨드에 반영됨).

## 2. 13프레임 서브셋 만들기

전체 321장을 다시 빌드할 필요 없이, 어노테이션 JSON을 13개 stem만 남기고
필터링한 뒤 그 미니 JSON으로 `build_sonynod_dataset.py`를 돌린다.

```bash
cd isppipeline/hls/tools

python3 - <<'PYEOF'
import json
from pathlib import Path

FLIPPED = [
    # C1 -> adaptive 개선 (8장, 핵심)
    "DSC03637", "DSC03786", "DSC03585", "DSC03864",
    "DSC03792", "DSC03859", "DSC03811", "DSC03689",
    # adaptive 회귀 (4장, 부수 확인)
    "DSC03839", "DSC03849", "DSC03860", "DSC03922",
    # 13번째: c0=False, c1=True, adaptive=True (C0만 다른 회색지대, ISO 2500)
    "DSC01901",
]

ann_path = Path("<RAW-NOD>/annotations/Sony/raw_str_labeled_new_Sony_RX100m7_test.json")
coco = json.loads(ann_path.read_text())
keep_ids = {im["id"] for im in coco["images"] if Path(im["file_name"]).stem in FLIPPED}
coco["images"] = [im for im in coco["images"] if im["id"] in keep_ids]
coco["annotations"] = [a for a in coco["annotations"] if a["image_id"] in keep_ids]
Path("sonynod_flip13.json").write_text(json.dumps(coco))
print(f"kept {len(coco['images'])} images, {len(coco['annotations'])} annotations")
PYEOF

python3 build_sonynod_dataset.py sonynod_flip13.json \
    "<Drive 동기화 경로>/dataset/Sony/Sony-ARW" \
    ../../../data/sonynod_flip13
```

`converted=13 ...`(또는 그 이하 -- GT 없는 프레임은 스킵됨, 원 321장 빌드
때와 동일 규칙)이 뜨면 성공.

## 3. normal/lowlight 강제 mAP 비교

```bash
cd isppipeline/hls/tools
PYTHONPATH=. python3 archive/eval_map_newrm.py \
    --root ../../../data/sonynod_flip13 \
    --tag SonyNOD-flip13 \
    --arms normal,lowlight \
    --limit 13 \
    --model yolov8n.pt \
    --out ../results/map_newrm_sonynod_flip13_yolov8n.csv
```

`ultralytics` YOLO 추론이 여기서 GPU(GTX 5060)를 쓴다. 13장뿐이라 CPU로도
돌아가겠지만 GPU면 수 초 내 끝날 것.

## 4. 해석

- **`lowlight` mAP > `normal` mAP**면: adaptive τ가 재분류한 8장(그리고
  가능하면 4장도 별도로) 방향이 실제로 detection에 유리했다는 근거 —
  §3.4 채택 판정을 real-RAW로 강화.
- **차이가 없거나 반대**면: recall 개선처럼 보였던 8장이 실제 mAP엔
  중립/역효과일 수 있다는 뜻 — 정직하게 그대로 보고할 것, "그래도 recall은
  개선됐다"는 별개 사실로 남겨두되 mAP 결론과 섞지 말 것.
- 13장은 통계적으로 작은 표본이라 **이 결과 하나로 최종 결론을 내리지 말 것**
  — PASCALRAW 도착 후 정본 재평가(ROADMAP.md §4 item 2)가 여전히 최종
  근거다. 이건 "지금 가용한 데이터로 방향성만 먼저 보는" 중간 점검이다.

## 5. 결과 저장

`results/checker-adaptive-tau-realdata-2026-07-13.md`에 "§6 시나리오 B
(mAP 재확인)" 섹션을 추가하거나, 별도로
`results/checker-adaptive-tau-scenario-b-2026-MM-DD.md`로 저장 — 위 §4
해석을 그대로 채워서.
