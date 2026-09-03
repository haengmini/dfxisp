<!--
=============================================================================
File   : isppipeline/sw/sim/blc/blc12bit_resweep_report.md
Date   : 2026-08-18 KST
Function: 2026-08-18 12-bit 네이티브 BLC_OFFSET 재스윕(LOD_test_hw,
          PASCAL_test_hw, `../../../hls/results/map_isp_{lod,pascal}_
          blc12bit_yolov8n.csv`)의 결과가 왜 07-08/07-15 SonyNOD 재보정
          캠페인이 시사했던 "BLC 16~32 근처가 최적"과 다른 모양(offset=0이
          항상 최고, 커질수록 단조 감소)으로 나왔는지에 대한 원인 분석.
          실제 스윕 실행은 다른 머신(Remote Control로 연결된 노트북
          세션)에서 이뤄졌고, 실행 환경/데이터 통계는 그 세션에 질의해
          교차 확인했다.
Sources: ../../../hls/results/map_isp_lod_blc12bit_yolov8n.csv,
         ../../../hls/results/map_isp_pascal_blc12bit_yolov8n.csv,
         ../../../hls/results/isp-pipeline-recalibration-2026-07-08.md,
         ../../../hls/results/blc-recalibration-deploy-2026-07-20.md,
         ../../../hls/results/hw-dataset-geometry-2026-08-13.md §3.2,
         ../../../hls/tools/build_hw_dataset.py (to_raw12()),
         blc.md, blc_report.md (동일 디렉터리, BLC pedestal 클립 편향 시뮬레이션 -- 별개 축)
=============================================================================
-->

# 12-bit BLC_OFFSET 재스윕 원인 분석 (2026-08-18)

## 0. 결론부터

1. **2026-08-18 재스윕(LOD_test_hw, PASCAL_test_hw, 12-bit 네이티브 그리드
   0~256)은 두 데이터셋·양 arm(normal/lowlight) 전부에서 BLC_OFFSET=0이
   최고 mAP이고, 값이 커질수록 단조 감소한다.** 현 배포값(12-bit 32)에서
   이미 LOD는 mAP@.5:.95가 0.1317→0.0156(−88%), PASCAL은
   0.6239→0.2383(−62%)까지 떨어져 있다.
2. **이것은 2026-07-08/07-15 SonyNOD 기반 재보정 캠페인의 결론을
   뒤집는 것이 아니다.** 그 캠페인 원문(`isp-pipeline-recalibration-
   2026-07-08.md`)도 "BLC=2(12-bit 32)가 최적"이 아니라 **"1~2 구간이
   노이즈 수준 차이의 평평한 정점"**이라고 스스로 명시했고, 32는
   최적성이 실측으로 증명된 값이 아니라 "이미 실측된 구성 중에서
   고른다"는 정책적 제약(`blc-recalibration-deploy-2026-07-20.md` §1)으로
   선택된 값이었다. 이번 재스윕은 그 애매했던 결론을, 8-bit 정밀도 손실이
   없는 12-bit 데이터와 더 촘촘한 그리드(0,8,16,24,32...)로 재검증한 것에
   가깝다.
3. **근본 원인은 데이터 자체의 구조에 있다.** `build_hw_dataset.py`의
   `to_raw12()`가 데이터셋 생성 시점에 이미 카메라 실측 채널별 black
   level을 정확히 빼고 정규화해서, `*_hw` 원시 데이터에는 파이프라인이
   추가로 제거할 잔여 black level이 애초에 거의 없다. PASCAL은 카메라
   보고 black level이 **정확히 0**이라 이 사실을 가장 깨끗하게 보여주는
   대조군이다.

## 1. 재스윕 결과 요약

| BLC_OFFSET(12bit) | LOD normal | LOD lowlight | PASCAL normal | PASCAL lowlight |
|---:|---:|---:|---:|---:|
| 0 | 0.1317 | 0.1960 | 0.6239 | 0.6707 |
| 8 | 0.0620 | 0.0933 | 0.5228 | 0.5734 |
| 16 | 0.0389 | 0.0539 | 0.4041 | 0.4717 |
| 24 | 0.0235 | 0.0337 | 0.2926 | 0.3642 |
| **32 (배포값)** | **0.0156** | **0.0226** | **0.2383** | **0.2781** |
| 64 | 0.0032 | 0.0043 | 0.0627 | 0.0840 |
| 128 | 0.0016 | 0.0023 | 0.0169 | 0.0212 |
| 256 | 0.0003 | 0.0003 | 0.0002 | 0.0002 |

(mAP@.5:.95, yolov8n, n=100/dataset. 전체 11점 그리드는 원본 CSV 참고.)

그림: `blc12bit_resweep_map.png` (본 리포트와 같은 디렉터리,
`blc12bit_resweep_plot.py`로 재생성 가능).

## 2. 데이터 근거 -- `*_hw` 데이터셋은 이미 black-corrected

`build_hw_dataset.py`의 `to_raw12()`:

```python
blk = np.asarray(black, dtype=np.float64)[colors]
denom = max(float(white) - float(np.median(blk)), 1.0)
lin = np.clip((visible - blk) / denom, 0.0, 1.0)
return np.round(lin * RAW12_MAX).astype("<u2")
```

카메라(rawpy)가 보고하는 채널별 `black_level_per_channel`을 프레임 생성
시점에 정확히 빼고 정규화한다. `meta.json` 전수 통계(100프레임씩,
노트북 세션 교차 확인):

| | black | white | raw12_mean (min/avg/max) | raw12_max (min/avg) |
|---|---|---|---|---|
| LOD_test_hw | (800,800,800,800) 전 프레임 고정 | 16380 고정 | 16.09 / **84.24** / 378.61 | 389 / 3823.0 |
| PASCAL_test_hw | (0,0,0,0) 전 프레임 고정 | 4095 고정 | 139.97 / **344.92** / 623.92 | 2213 / 3987.4 |

**PASCAL이 결정적 대조군이다**: 카메라가 보고하는 black level이 전
프레임에서 정확히 0이므로, 파이프라인이 추가로 빼는 BLC_OFFSET은
이론상 처음부터 지울 잔여 black level이 없는 순수 신호 파괴다. 그런데도
offset=8에서 이미 normal mAP가 0.6239→0.5228(−16%)로 떨어지고 이후
단조 감소가 이어진다 -- 이건 데이터셋 특이 현상이 아니라 구조적 문제라는
뜻이다.

**LOD는 절대 신호량 자체가 극히 작다**: black=800이 이미 제거된 상태에서
`raw12_mean` 평균이 84.24, 가장 어두운 프레임은 16.09(4095 스케일 기준)까지
내려간다. 배포값 offset=32는 평균 신호의 38%, 최암흑 프레임에서는 신호
자체보다 크다 -- offset=8만 빼도 mAP가 반토막 나는 게 산술적으로 당연하다.

## 3. 07-08/07-15 SonyNOD 결론과의 관계 -- 뒤집힌 게 아니라 재검증됐다

`isp-pipeline-recalibration-2026-07-08.md`를 다시 읽으면:

- 그리드가 성겼다: `{0,1,2,4,8,16}`(구 8-bit-등가 단위, 12-bit로는
  `{0,16,32,64,128,256}`) -- 8, 24 같은 저역 세부 지점이 아예 없었다.
- "정점"으로 지목된 offset=1~2(12-bit 16~32) 구간을 문서 스스로
  **"노이즈 수준 차이의 평평한 정점"**이라 표현했다(§3 결론 3, BLC=1과
  2의 차이 0.0010을 "노이즈 수준"으로 명시). offset=0 대비 우위도 normal
  +4.5%, lowlight +8.4% 수준으로, 321장 단일 실행의 통계적 잡음과
  구분하기 애매한 크기다.
- 배포값 32(구 표기 2)는 이 정점이 최적이라 증명돼서가 아니라
  `blc-recalibration-deploy-2026-07-20.md` §1이 명시하듯 "실측된 구성
  중에서 고른다"는 정책 제약 때문에 선택됐다 -- normal arm 단독으로는
  오히려 더 작은 값(구 표기 1)이 근소 우위였다.
- 그 스윕은 **8-bit로 정밀도가 손실된 shift8 원시 데이터** 위에서 돌았다.
  `hw-dataset-geometry-2026-08-13.md` §3.2가 이미 지적한 대로, 구
  shift8 LOD raw_bin 평균은 8-bit 환산 0.98 LSB -- 어두운 프레임 신호의
  대부분이 256단계 중 0~6 코드에 뭉개져 있었다. 이런 정밀도 손실 위에서
  얻은 "정점" 위치는 신뢰도가 낮다.

즉 이번 12-bit + 촘촘한 그리드 재스윕은 기존 결론을 반증한 게 아니라,
정밀도 손실과 성긴 그리드 위에서 "노이즈 수준의 평평한 정점"이라고
스스로 헤징했던 결과를 정밀 재측정해서, 그 정점이 애초에 존재하지
않았을 가능성(혹은 있었어도 SonyNOD 특유의 현상이었을 가능성)을 보여준
것에 가깝다.

## 4. 실행 환경 (노트북 세션, Remote Control로 교차 확인)

- 명령: `eval_map_isp.py --root <.../LOD_test_hw|PASCAL_test_hw>
  --arms normal,lowlight --model yolov8n.pt --tag {LOD,PASCAL}-BLC12bit
  --out isppipeline/hls/results/map_isp_{lod,pascal}_blc12bit_yolov8n.csv`,
  `--blc-offsets`는 스크립트 기본 그리드(0,8,16,24,32,48,64,96,128,192,256)
  그대로 사용.
- 로그: warning/error/traceback 0건.
- GPU: NVIDIA GeForce RTX 5060 Laptop GPU (8151 MiB, driver 572.97).
- 버전: Python 3.10.12 / numpy 2.2.6 / rawpy 0.27.0 / ultralytics 8.4.90 /
  torch 2.11.0+cu128.
- 소요 시간: LOD 2m32s + PASCAL 2m31s(합계 ~5분) -- 1368x912 4x 데시메이션
  세트라 `eval_map_isp.py` docstring이 언급하는 원 SonyNOD 풀해상도 기준
  "GPU 수시간"보다 훨씬 빠르다.

## 5. 남은 것 / 한계

- **sonynod_test 원본 데이터가 이 노트북에 없다** (`find / -iname
  "*sonynod*"` 재확인해도 빈 결과). "SonyNOD가 LOD_test_hw보다 신호
  헤드룸(평균 raw12 값)이 더 컸을 것"이라는 보조 가설은 직접 대조하지
  못했다 -- 원본 데이터나 그 raw12_mean 통계가 있는 다른 위치에서
  재확인 필요.
- `*_hw`는 4x 데시메이션 축소판이라 절대 mAP 수치는 원본 풀해상도와
  직접 비교할 수 없다(`hw-dataset-geometry-2026-08-13.md` §5의 기존
  경고 그대로 유효) -- 이번 분석은 "형태"(단조 감소 vs 정점)에 대한
  것이고 절대값 비교가 아니다.
- 이 리포트는 mAP 관점의 BLC_OFFSET 재스윕이고, 같은 디렉터리의
  `blc_report.md`가 다루는 "BLC pedestal 클립 순서(평균 후 감산 vs
  감산 후 평균)에 따른 통계적 편향" 축과는 별개 질문이다 -- 두 리포트
  모두 "저조도에서 BLC 상수가 신호를 크게 깎아낸다"는 방향은 공유하지만
  측정 방법과 결론의 범위가 다르다.

## 6. 권고

- 배포 BLC_OFFSET=32(12-bit)를 이 두 real-RAW 세트 기준 mAP 최적값으로
  재해석하지 말 것 -- 07-20 배포 근거는 여전히 "실측된 구성 중 정책적
  선택"이었을 뿐, 이번 재스윕이 그 근거를 강화하지도 약화하지도 않는다.
  다만 32가 이 두 세트에서 **공짜가 아니라는 것**(LOD -88%, PASCAL -62%)은
  이번에 처음 정량화됐다.
- 헤드룸 가설을 마저 검증하려면 SonyNOD 원본(혹은 그 raw12_mean 통계)을
  구해 LOD_test_hw/PASCAL_test_hw와 같은 방식으로 비교할 것.
- BLC 상수를 실제로 재조정할 근거로 쓰려면, checker.py의 dark-ratio
  선택 로직(adaptive arm)과 결합한 end-to-end 영향까지 봐야 한다 --
  이번 재스윕은 `normal`/`lowlight`arm 단독 결과이고 `adaptive`는
  포함하지 않았다.
