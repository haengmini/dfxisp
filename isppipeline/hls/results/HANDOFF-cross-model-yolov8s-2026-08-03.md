<!--
=============================================================================
File   : HANDOFF-cross-model-yolov8s-2026-08-03.md
Date   : 2026-08-03 KST
Function: 노트북(RTX 5060) 에이전트에게 넘기는 인수인계 문서. lod-pascal-
          isp-simulation-2026-07-15.md(YOLOv8n, 27조합)와 정확히 같은
          시나리오를 YOLOv8s로 재실행 -- 단일 모델(YOLOv8n) 특이적
          아티팩트인지 확인하는 교차 모델 검증의 1단계.
Audience: 이 레포를 처음 보는 에이전트(별도 세션/노트북) -- "0. 결론부터"와
          "3. 지금 할 일"만 봐도 실행 가능하도록 작성.
Sources : lod-pascal-isp-simulation-2026-07-15.md(§3 시나리오/§6 결과표/§8.3
          부수발견 -- 이번 재검증 대상), tools/eval_map_isp.py(--manifest
          인자, 07-16 버그 수정 반영된 현재 버전), tools/model_paths.py
          (YOLO_WEIGHTS에 yolov8s.pt 슬롯 이미 존재), ROADMAP.md(675줄,
          "즉시 다음" §2 교차 모델 검증)
=============================================================================
-->
# 인수인계 — 교차 모델 검증 1단계: YOLOv8s (2026-08-03)

## 0. 결론부터

`lod-pascal-isp-simulation-2026-07-15.md`의 27개 조합(LOD/PASCAL/
Shuffle_split × normal/lowlight/adaptive × BLC{16,1,2})은 전부 **YOLOv8n
하나로만** 측정됐다. 그 문서 §8.3이 발견한 "lowlight arm이 100% 주간인
PASCAL에서도 normal과 같거나 우위(9/9 조합)"라는 결과가 YOLOv8n
특이적 아티팩트가 아님을 확인하려면 다른 검출기로 같은 실험을 재현해야
한다. 이번 인수인계는 **정확히 같은 27개 조합을 YOLOv8s로만** 다시
돌린다 -- 새 코드 없음, `--model yolov8s.pt` 하나만 바꾼다. (SSDLite-
MobileNetV3는 `eval_map_isp.py`가 아직 지원하지 않아 별도 인수인계로
분리 -- 이번 범위 아님.)

## 1. 데이터 -- 새로 전달할 것 없음

`lod-pascal-splits-2026-07-15.tar.gz`(Google Drive `paper/data-handoff/`)로
이미 이 노트북에 전달된 `data/{lod_split,pascal_split,shuffle_split}`를
그대로 재사용한다. 07-15/07-16 세션에서 이미 압축 해제·shuffle_split
심볼릭 링크 재구성까지 끝냈을 것 -- `ls data/lod_split/raw_bin | wc -l`
등으로 321/321/642개가 남아있는지만 먼저 확인. 없으면
`HANDOFF-lod-pascal-isp-simulation-2026-07-15.md` §3.1을 그대로 재실행
(같은 Drive 아카이브, 재다운로드 불필요하면 로컬 캐시 확인).

## 2. 코드 -- git pull만

```bash
git pull
```
이걸로 이번 세션의 커밋(BLC 2/2 배포, checker C1 배포, Vivado DFX
재구현)이 반영된다. `eval_map_isp.py`는 07-16에 `--manifest` 인자가
추가된 버전 그대로이며, 이후 손대지 않았다 -- **07-15/07-16 캠페인과
완전히 같은 하네스**를 쓴다는 뜻(교차 모델 비교의 전제조건).

## 3. 지금 할 일

### 3.1 YOLOv8s 가중치 확인
```bash
ls model/detectors/yolo/yolov8s.pt   # 없으면 ultralytics가 첫 실행 시
                                       # 자동 다운로드 (인터넷 필요)
```

### 3.2 스모크 테스트 (권장, 먼저)
```bash
cd isppipeline/hls/tools
python3 eval_map_isp.py \
    --root ../../../data/pascal_split --manifest ../results/pascal_split_2026-07-15.csv \
    --blc-offsets 2 --limit 10 --tag PASCAL-yolov8s-smoke --model yolov8s.pt \
    --out /tmp/smoke_yolov8s.csv
```
07-16 재실행 때 이 조합(PASCAL, --limit 10)에서 adaptive arm 버그가
처음 드러났던 조합과 동일 -- 여기서 normal/lowlight/adaptive 세 mAP가
서로 다른 값으로 나오는지(즉 `--manifest`가 실제로 로드되는지)만 확인.

### 3.3 본 실행 -- YOLOv8n 캠페인과 완전히 같은 27개 조합

```bash
cd isppipeline/hls/tools

python3 eval_map_isp.py \
    --root ../../../data/lod_split --manifest ../results/lod_split_2026-07-15.csv \
    --blc-offsets 16,1,2 --tag LOD-split-yolov8s-2026-08-03 --model yolov8s.pt \
    --out ../results/map_isp_lod_split_yolov8s_2026-08-03.csv

python3 eval_map_isp.py \
    --root ../../../data/pascal_split --manifest ../results/pascal_split_2026-07-15.csv \
    --blc-offsets 16,1,2 --tag PASCAL-split-yolov8s-2026-08-03 --model yolov8s.pt \
    --out ../results/map_isp_pascal_split_yolov8s_2026-08-03.csv

python3 eval_map_isp.py \
    --root ../../../data/shuffle_split --manifest ../results/shuffle_split_2026-07-15.csv \
    --blc-offsets 16,1,2 --tag Shuffle-split-yolov8s-2026-08-03 --model yolov8s.pt \
    --out ../results/map_isp_shuffle_split_yolov8s_2026-08-03.csv
```

07-15 캠페인 실측 기준 이 규모(27조합, PASCAL/Shuffle 대형 프레임)는
**약 6시간 50분** 걸렸다(`lod-pascal-isp-simulation-2026-07-15.md` §7.2,
YOLOv8s는 YOLOv8n보다 추론 자체는 느리지만 렌더 비용이 병목이라 비슷한
규모로 예상) -- 반드시 백그라운드로 돌릴 것. 시간이 부족하면
`--blc-offsets 2`(현재 배포값)만 먼저 돌려 핵심 질문(§4 해석 기준)에
먼저 답하고, 16/1은 여유 있을 때 추가.

## 4. 해석 기준 -- YOLOv8n 결과(07-15/16)와 셀 단위로 대조

`lod-pascal-isp-simulation-2026-07-15.md` §6의 표와 같은 축(split ×
BLC × arm)으로 나오므로 나란히 놓고 비교한다. 확인할 것 우선순위:

1. **§8.3 재현 여부(가장 중요)**: PASCAL_split의 BLC×비교 9개 조합에서
   `lowlight ≥ normal`이 YOLOv8s에서도 유지되는가? 9/9까지는 아니어도
   방향이 대체로 같으면 "YOLOv8n 특이적 아티팩트가 아니다"를 뒷받침.
   방향이 뒤집히면(다수 조합에서 `normal > lowlight`) 이건 YOLOv8n
   특이적이었다는 뜻 -- 정직하게 기록(과장 금지, 이 프로젝트 관례).
2. **§8.1 BLC 레버 재현**: 모든 split·arm에서 BLC=1/2가 BLC=16을
   압도하는가 (YOLOv8n에서 최대 5.7배).
3. **§8.2 adaptive 거동 재현**: LOD에서 adaptive≈lowlight, Shuffle에서
   adaptive가 BLC=2일 때만 근소하게 둘 다 이기는 패턴이 재현되는가.

**주의:** 이미 배포된 결정(BLC 2/2, checker C1)을 이 결과가 뒤집지는
않는다(ROADMAP.md "즉시 다음" §2) -- 순수하게 논문의 일반화 주장 근거
보강용. 결과가 기대와 다르게 나와도 지우지 말고 정직하게 기록.

## 5. 결과 저장

`results/map_isp_{lod,pascal,shuffle}_split_yolov8s_2026-08-03.csv` 3개
CSV + 새 문서 `results/cross-model-yolov8s-2026-08-03.md`(§0 결론, §4
해석 기준의 3개 항목 각각에 대한 판정, YOLOv8n 대비 표)로 정리.
`results/INDEX.md`에도 한 줄 추가. SSDLite는 별도 인수인계(추후) --
이 문서 범위 아님.
