<!--
=============================================================================
File   : HANDOFF-lod-pascal-isp-simulation-2026-07-15.md
Date   : 2026-07-15 KST
Function: 노트북(RTX 5060) 에이전트에게 넘기는 인수인계 문서. LOD_split/
          PASCAL_split/Shuffle_split(동수 매칭, pascalraw-adapter-2026-07-13.md
          §7의 후속) 3개 데이터셋에 baseline/lowlight/adaptive ISP 암을
          렌더링해 mAP로 실측한다. GPU 필요(디코드+YOLO val)라 이 데스크톱
          (GTX 1650)에는 부적합, 노트북(RTX 5060)으로 이관.
Audience: 이 레포를 처음 보는 에이전트(별도 세션/노트북) -- 아래 "0. 결론부터"
          와 "3. 지금 할 일"만 봐도 실행 가능하도록 작성.
Sources : pascalraw-adapter-2026-07-13.md §7 (false-trigger 실측),
          checker-adaptive-tau-realdata-2026-07-13.md (recall 실측),
          checker-status-2026-07-10.md §4 (다음 관문),
          HANDOFF-checker-adaptive-tau-canonical-rerun-2026-07-13.md
          (동일 형식의 선례 -- 정본 파이프라인 트리오),
          tools/build_matched_splits.py, tools/materialize_split.py,
          tools/eval_map_isp.py, tools/checker.py,
          tools/baseline_isp_pipeline.py, tools/low_light_isp_pipeline.py
=============================================================================
-->
# 인수인계 — LOD/PASCAL 매칭 split, ISP baseline/lowlight/adaptive mAP 실측 (2026-07-15)

## 0. 결론부터

`pascalraw-adapter-2026-07-13.md` §7이 checker의 **판정 정확도**(LOW_LIGHT
verdict의 recall/false-trigger)를 raw dark-ratio 통계로만 측정했다 --
"판정이 틀렸을 때 실제로 mAP가 얼마나 나빠지는가"는 아직 답한 적이 없다.
이번 캠페인은 그 질문에 답한다: checker의 `adaptive` 모드(프레임마다
baseline/lowlight 파이프라인 중 하나를 동적으로 고르는 실제 배포 동작)를
**이미 구현돼 있는 그대로**(`tools/checker.py` + `tools/eval_map_isp.py`의
`arm == "adaptive"` 분기, 새 코드 불필요) 세 데이터셋에 돌려 mAP를 잰다:

- **LOD_split** (321장, SonyNOD 전량, 100% 실저조도) -- adaptive가
  lowlight 암과 거의 같은 mAP를 내야 정상(체커가 대부분 LOW_LIGHT로
  맞게 판정하는 인구, `checker-adaptive-tau-realdata-2026-07-13.md`의
  recall 실측과 정합해야 함).
- **PASCAL_split** (321장, PASCALRAW ISO층화 샘플, 100% 주간) -- adaptive가
  baseline 암과 얼마나 벌어지는지가 관건. §7 실측(adaptive false-trigger
  38.4%)대로면 약 38%의 프레임이 (틀리게) lowlight 파이프라인을 타게 되고,
  이게 mAP를 baseline 대비 얼마나 깎는지 여기서 처음 잰다.
- **Shuffle_split** (642장, 둘을 합쳐 셔플) -- 가장 현실적인 "실배포
  인구" 근사. adaptive의 mAP가 normal-전용/lowlight-전용 강제 암보다
  나은지가 이 캠페인의 핵심 결론이 된다.

## 1. 데이터 전달 방식 (git 아님 -- 용량 문제)

LOD_split(12.5G)+PASCAL_split(15.2G) raw_bin 픽셀 데이터는 git으로 넘기지
않았다 -- 이 레포는 `data/`를 통째로 `.gitignore`하고 git-lfs도 이
데스크톱엔 없어서, 28G를 git push하면 GitHub 100MB/파일 하드리밋에
걸리거나 억지로 넣으면 레포 역사에 영구 블로트로 남는다. 대신 **Google
Drive**로 gzip 압축 아카이브를 올렸다 (shift8 raw16 포맷은 하위 8비트가
항상 0이라 gzip이 잘 먹는다 -- 39.9MB 프레임 하나가 gzip -1로 9.7MB,
약 4배 압축 확인됨).

- 아카이브: `lod-pascal-splits-2026-07-15.tar.gz` (14.03GiB, 27.7G raw
  대비 gzip으로 절반 정도 -- jpg 이미지가 섞여 있어 raw_bin 단독(shift8,
  gzip -1 기준 약 4배)보다는 압축률이 낮음)
- Drive 위치: `paper/data-handoff/lod-pascal-splits-2026-07-15.tar.gz`
  (Drive root "paper/", fileId `10ysAtpc77ZG4QE8AO0pnrKffWfJcU-eE`)
  공유 링크: https://drive.google.com/open?id=1-F5wN6sKTzTIBMYgmT7qtfkpX9AYB5j6
  (업로드 2026-07-15 12:46 KST, rclone gdrive 리모트로 25분 소요, 9.5MB/s)
- 내용물: `lod_split/{raw_bin,images,labels}`(321장, SonyNOD 전량),
  `pascal_split/{raw_bin,images,labels}`(321장), 매니페스트 3개(`*_split_
  2026-07-15.csv`), `build_matched_splits.py`, `materialize_split.py`,
  `README.md`(압축해제+shuffle_split 재구성 커맨드 포함).
  **`shuffle_split`은 픽셀 데이터를 따로 담지 않는다** -- `lod_split`∪
  `pascal_split`과 완전히 같은 프레임(642장)이라 중복 저장 대신 로컬에서
  심볼릭 링크로 재구성한다 (아래 3.1).

## 2. 매칭 split이 뭔지 (모르면 먼저 읽을 것)

`pascalraw-adapter-2026-07-13.md` §7에서 LOD(SonyNOD, 321장)의 ISO
분포(88%가 [6400,12800))와 PASCAL(PASCALRAW, 4259장)의 ISO 분포(90%가
[400,800))가 거의 안 겹친다는 게 드러났다. `build_matched_splits.py`는
LOD 321장 전량 + PASCAL에서 자기 ISO 형태를 유지한 채 321장 층화샘플을
뽑아 **프레임 수만** 맞춘 것 -- ISO별 균형은 아니다(그건 애초에 두
데이터셋의 물리적 특성상 불가능, README/커밋 메시지 참고). 이 사실은
mAP 결과를 ISO-stratified로 쪼갤 때(선택사항) 그대로 주의사항이 된다.

## 3. 지금 할 일 (실행 커맨드)

### 3.1 압축 해제 + shuffle_split 재구성

```bash
mkdir -p data
tar xzf lod-pascal-splits-2026-07-15.tar.gz -C data
cd data
python3 materialize_split.py --manifest shuffle_split_2026-07-15.csv \
    --out shuffle_split --mode symlink \
    --source-dir lod=lod_split --source-dir pascal=pascal_split
cd ..
```

각 디렉터리에 321/321/642개 `.bin`이 있는지 확인:
`ls data/lod_split/raw_bin | wc -l` 등.

### 3.2 detector 가중치 확인

```bash
ls model/detectors/yolo/yolov8n.pt   # 없으면 eval_map_isp.py 첫 실행 시
                                       # resolve_yolo_model()이 에러를 낼 것
```

### 3.3 ISP 암(baseline/lowlight/adaptive) 렌더 + mAP

`tools/eval_map_isp.py`는 이미 `ARMS = ["normal", "lowlight", "adaptive"]`가
기본값이고, `"adaptive"` 암은 `checker.py`의 `selected_mode()`로 프레임마다
동적으로 normal/lowlight를 고른다 -- **원하는 그대로 구현돼 있음, 새
코드 불필요**. BLC_OFFSET=16이 현재 배포값(주 비교 대상), 1/2은 07-08이
찾은 후보 정점(참고용).

```bash
cd isppipeline/hls/tools

python3 eval_map_isp.py \
    --root ../../../data/lod_split --blc-offsets 16,1,2 \
    --tag LOD-split-2026-07-15 --model yolov8n.pt \
    --out ../results/map_isp_lod_split_2026-07-15.csv

python3 eval_map_isp.py \
    --root ../../../data/pascal_split --blc-offsets 16,1,2 \
    --tag PASCAL-split-2026-07-15 --model yolov8n.pt \
    --out ../results/map_isp_pascal_split_2026-07-15.csv

python3 eval_map_isp.py \
    --root ../../../data/shuffle_split --blc-offsets 16,1,2 \
    --tag Shuffle-split-2026-07-15 --model yolov8n.pt \
    --out ../results/map_isp_shuffle_split_2026-07-15.csv
```

**먼저 `--limit 10`으로 스모크 테스트 권장** -- PASCAL 프레임(6034×4012)이
SonyNOD 크롭(5472×3648)보다 크고, 이 조합(LOD/PASCAL split, adaptive 암)은
한 번도 실행해본 적이 없어서 렌더/라벨 정합성을 소수 프레임으로 먼저
확인하는 게 안전하다 (이 프로젝트의 관례 -- `pascalraw_adapter.py`도
`--limit 20`으로 먼저 검증했다).

세 런 다 `--blc-offsets 16,1,2` × `arms=normal,lowlight,adaptive` ×
프레임수라 렌더 총량이 크다(특히 PASCAL/Shuffle) -- 시간이 오래 걸리면
BLC=16만 먼저(`--blc-offsets 16`) 돌려 핵심 질문에 먼저 답하고, 1/2은
여유 있을 때 추가로.

### 3.4 라벨 클래스 공간 호환성 (이미 확인됨, 참고만)

SonyNOD(`category_remap {"1":0,"2":1,"3":2}`)와 PASCALRAW 둘 다 최종
라벨은 **동일한 COCO-80 0-indexed id**(person=0/bicycle=1/car=2, `tools/
aodraw_adapter.py`의 COCO80 순서)를 쓴다 -- Shuffle_split처럼 두 출처를
한 mAP run에 섞어도 클래스 id가 어긋나지 않는다는 것 확인됨(2026-07-15,
샘플 라벨 대조). `eval_map_isp.py`의 `nc: 80` 설정 그대로 사용.

## 4. 해석 기준

- **LOD_split**: `adaptive` mAP ≈ `lowlight` mAP가 기대값. 크게 갈리면
  체커의 recall miss(특히 ISO≤1600 저표본 구간,
  `checker-adaptive-tau-realdata-2026-07-13.md` §5)가 실제 mAP에 어떻게
  반영되는지 보여주는 것 -- 흥미로운 발견이니 기록.
- **PASCAL_split**: `adaptive` mAP vs `normal`(=baseline) mAP 격차가
  핵심. §7의 adaptive false-trigger 38.4%가 이 격차의 원인 -- 격차가
  크면 "판정 오류가 실제 성능에 미치는 비용"을 처음으로 정량화하는 것.
- **Shuffle_split**: `adaptive`가 `normal`/`lowlight` **둘 다보다 나은지**가
  이 캠페인 전체의 결론. 하나라도 못 이기면 checker #1(적응 τ) 강화안이
  recall/false-trigger 개별 지표는 개선해도 실제 배포 이득으로 안
  이어질 수 있다는 뜻 -- 정직하게 기록할 것 (이 프로젝트는 과장 금지
  원칙을 반복 강조해왔다, `HANDOFF-checker-adaptive-tau-canonical-rerun-
  2026-07-13.md` §5 참고).
- **BLC=1/2 후보값**: `checker-adaptive-tau-realdata-2026-07-13.md` §8/§9가
  이미 "13/31장 소표본에서 BLC=1/2가 방향을 뒤집었다가 31장에서 복귀"를
  겪었다 -- 이번 321/642장은 그보다 표본이 크지만, BLC=16과 방향이
  다르게 나오면 표본 크기·프레임 구성 차이부터 의심하고 바로 결론 내지
  말 것.

## 5. 결과 저장

`results/map_isp_{lod,pascal,shuffle}_split_2026-07-15.csv` 3개 CSV +
새 문서 `results/lod-pascal-isp-simulation-2026-07-15.md`(§0 결론, §1~3
데이터/커맨드 요약, §4 세 데이터셋 mAP 표 + 해석)로 정리. `results/
INDEX.md`에도 한 줄 추가. 기존 관례대로 결과가 기대와 다르게 나와도
지우지 말고 정직하게 기록(과거 ver0/ver1 오류도 삭제 대신 정정 표시로
남겨온 전례, §4 마지막 항목 참고).
