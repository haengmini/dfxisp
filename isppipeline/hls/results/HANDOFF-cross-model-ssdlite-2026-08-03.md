<!--
=============================================================================
File   : HANDOFF-cross-model-ssdlite-2026-08-03.md
Date   : 2026-08-03 KST
Function: 노트북(RTX 5060) 에이전트에게 넘기는 인수인계 문서 — 교차 모델
          검증 2단계(SSDLite-MobileNetV3). 1단계(YOLOv8s,
          HANDOFF-cross-model-yolov8s-2026-08-03.md)와 정확히 같은 27개
          조합을 이번엔 SSDLite로 재실행한다.
Audience: 이 레포를 처음 보는 에이전트(별도 세션/노트북) -- "0. 결론부터"와
          "3. 지금 할 일"만 봐도 실행 가능하도록 작성.
Sources : lod-pascal-isp-simulation-2026-07-15.md(§3 시나리오/§6 결과표/§8.3
          부수발견 -- 이번 재검증 대상), tools/eval_map_isp_ssd.py(신규,
          이번 세션에 작성 -- eval_map_isp.py의 build_arm_images()/
          load_adaptive_verdicts()를 그대로 재사용해 이미지 렌더링은
          YOLOv8n/YOLOv8s 실행과 동일하게 만들고 검출기만 torchvision
          SSDLite로 교체), tools/eval_map_ssd.py·eval_map_newrm_ssd.py(기존
          SSDLite 채점 로직의 출처), model_paths.py(SSDLITE_MNV3_WEIGHTS
          경로), ROADMAP.md("즉시 다음" #2)
=============================================================================
-->
# 인수인계 — 교차 모델 검증 2단계: SSDLite-MobileNetV3 (2026-08-03)

## 0. 결론부터

`lod-pascal-isp-simulation-2026-07-15.md`의 27개 조합(LOD/PASCAL/
Shuffle_split × normal/lowlight/adaptive × BLC{16,1,2})을 YOLOv8n(원본)·
YOLOv8s(1단계, `HANDOFF-cross-model-yolov8s-2026-08-03.md`)에 이어 이번엔
**SSDLite-MobileNetV3**로 3번째 재현한다. §8.3 발견("lowlight arm이 100%
주간인 PASCAL에서도 normal과 같거나 우위, 9/9 조합")이 검출기 계열
전반(YOLO뿐 아니라 SSD+MobileNet 구조)에서도 유지되는지가 핵심 질문이다.

**이번 세션에서 새 코드를 작성했다** — 기존 `eval_map_isp.py`는 Ultralytics
YOLO 체크포인트만 지원해서 SSDLite를 못 돌렸다. 새로 만든
`tools/eval_map_isp_ssd.py`는 `eval_map_isp.py`의 `build_arm_images()`/
`load_adaptive_verdicts()`를 그대로 import해서 재사용하므로 **렌더링되는
이미지 자체는 YOLOv8n/YOLOv8s 실행과 바이트 단위로 동일**하고, 검출기만
torchvision `ssdlite320_mobilenet_v3_large`로 바뀐다(COCO80→91 id 리매핑 +
pycocotools COCOeval, 기존 `eval_map_ssd.py`/`eval_map_newrm_ssd.py`와 같은
채점 방식). 데스크탑에서 로컬 데이터(`data/pascalraw_test` 일부 stem)로
normal/lowlight/adaptive 세 arm 전부 스모크 테스트 완료 — 정상 동작 확인.
**데스크탑 GPU(GTX 1650)는 드라이버가 너무 오래돼 CUDA를 못 씀(`CUDA
initialization: driver too old`)이라 스모크 테스트는 `--device cpu`로만
했다** — 본 실행은 노트북 GPU로 하는 게 맞다.

## 1. 데이터 — 새로 전달할 것 없음

YOLOv8s 인수인계와 동일 — `lod-pascal-splits-2026-07-15.tar.gz`로 이미 이
노트북에 전달된 `data/{lod_split,pascal_split,shuffle_split}`를 그대로
재사용한다. 확인: `ls data/lod_split/raw_bin | wc -l` 등으로 321/321/642개가
남아있는지만 체크.

## 2. 코드 — git pull만

```bash
git pull
```

이걸로 `tools/eval_map_isp_ssd.py`(신규)와 이 문서가 반영된다.
`eval_map_isp.py`는 그대로 재사용만 하고 손대지 않았다.

## 3. 지금 할 일

### 3.1 SSDLite 가중치 확인

```bash
ls model/detectors/ssdlite320_mobilenet_v3_large/ssdlite320_mobilenet_v3_large_coco-a79551df.pth
```
`*.pth`는 git-ignored라 이미 없으면 07-02/07-05 세션 때처럼 별도 확보가
필요하다(Drive `paper/` 또는 재다운로드 — `configure_torch_model_cache()`가
`TORCH_HOME`을 `model/cache/torch`로 돌려놓으므로, 로컬 파일이 없어도
인터넷이 되면 torchvision이 `weights=COCO_V1`으로 자동 다운로드해 그
경로에 캐시한다).

### 3.2 스모크 테스트 (권장, 먼저)

```bash
cd isppipeline/hls/tools
python3 eval_map_isp_ssd.py \
    --root ../../../data/pascal_split --manifest ../results/pascal_split_2026-07-15.csv \
    --blc-offsets 2 --limit 10 --tag PASCAL-ssdlite-smoke --device cuda \
    --out /tmp/smoke_ssdlite.csv
```
normal/lowlight/adaptive 세 mAP가 서로 다른 값으로 나오는지(즉 `--manifest`가
실제로 로드되는지) 확인 — YOLOv8s 스모크 테스트 때와 같은 체크포인트다.

### 3.3 본 실행 — YOLOv8n/YOLOv8s 캠페인과 완전히 같은 27개 조합

```bash
cd isppipeline/hls/tools

python3 eval_map_isp_ssd.py \
    --root ../../../data/lod_split --manifest ../results/lod_split_2026-07-15.csv \
    --blc-offsets 16,1,2 --tag LOD-split-ssdlite-2026-08-03 --device cuda \
    --out ../results/map_isp_lod_split_ssdlite_2026-08-03.csv

python3 eval_map_isp_ssd.py \
    --root ../../../data/pascal_split --manifest ../results/pascal_split_2026-07-15.csv \
    --blc-offsets 16,1,2 --tag PASCAL-split-ssdlite-2026-08-03 --device cuda \
    --out ../results/map_isp_pascal_split_ssdlite_2026-08-03.csv

python3 eval_map_isp_ssd.py \
    --root ../../../data/shuffle_split --manifest ../results/shuffle_split_2026-07-15.csv \
    --blc-offsets 16,1,2 --tag Shuffle-split-ssdlite-2026-08-03 --device cuda \
    --out ../results/map_isp_shuffle_split_ssdlite_2026-08-03.csv
```

**소요 시간 실측 없음** — SSDLite320은 YOLOv8 계열보다 통상 가벼운
모델이지만, 07-15 캠페인에서 병목이 추론이 아니라 ISP 렌더링(특히 PASCAL/
Shuffle의 대형 프레임)이었으므로 YOLOv8n/YOLOv8s와 비슷한 규모(수 시간)로
예상 — 반드시 백그라운드로 돌릴 것. 실측 전에는 이 추정을 사실처럼
인용하지 말 것(SPEC.md §11). 시간이 부족하면 `--blc-offsets 2`(현재
배포값)만 먼저 돌려 핵심 질문(§4)에 먼저 답하고, 16/1은 여유 있을 때 추가.

## 4. 해석 기준 — YOLOv8n(07-15/16)·YOLOv8s(08-03) 결과와 3-way 대조

`lod-pascal-isp-simulation-2026-07-15.md` §6과 같은 축(split × BLC × arm)
이므로 세 검출기 결과를 나란히 놓고 비교한다. 확인할 것 우선순위:

1. **§8.3 재현 여부(가장 중요)**: PASCAL_split의 BLC×비교 9개 조합에서
   `lowlight ≥ normal`이 SSDLite에서도 유지되는가? YOLOv8s에서도 재현됐다면
   ("YOLOv8n 특이적이 아니다") 이번엔 "YOLO 계열 특이적도 아니다"까지
   범위를 넓혀 확인하는 것이 목적 — 구조가 완전히 다른 SSD+MobileNet에서도
   같은 방향이면 검출기-무관 현상이라는 근거가 강해진다. 방향이 뒤집히면
   정직하게 기록(과장 금지).
2. **§8.1 BLC 레버 재현**: 모든 split·arm에서 BLC=1/2가 BLC=16을
   압도하는가.
3. **§8.2 adaptive 거동 재현**: LOD에서 adaptive≈lowlight, Shuffle에서
   adaptive가 BLC=2일 때만 근소하게 둘 다 이기는 패턴이 재현되는가.

**주의:** 이미 배포된 결정(BLC 2/2, checker C1)을 이 결과가 뒤집지는
않는다(ROADMAP.md "즉시 다음") — 순수하게 논문의 일반화 주장 근거 보강용.
결과가 기대와 다르게 나와도 지우지 말고 정직하게 기록.

## 5. 결과 저장

`results/map_isp_{lod,pascal,shuffle}_split_ssdlite_2026-08-03.csv` 3개
CSV + 새 문서 `results/cross-model-ssdlite-2026-08-03.md`(§0 결론, §4
해석 기준의 3개 항목 각각에 대한 판정, YOLOv8n·YOLOv8s 대비 3-way 표)로
정리. `results/INDEX.md`에도 한 줄 추가. 이걸로 교차 모델 검증(YOLOv8s +
SSDLite) 2단계 모두 종결.
