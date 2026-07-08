<!--
=============================================================================
File   : isppipeline/hls/results/isp-pipeline-recalibration-2026-07-08.md
Date   : 2026-07-08
Function: `realraw-sonynod-benchmark-2026-07-06.md` §6ter BLC 재보정 스윕을,
          gamma 버그가 수정된 새 canonical-matched 파이프라인
          (tools/baseline_isp_pipeline.py, tools/low_light_isp_pipeline.py,
          tools/checker.py, tools/eval_map_isp.py)으로 재실행.
Goal   : 커밋 3224dbe(`refactor(hls): replace stale SW-proxy ISP pipelines...`)가
          지적한 gamma 불일치 버그 수정 이후에도 §6ter의 두 결론 -- (1) arm 순서
          역전(lowlight/adaptive > normal)이 BLC 값과 무관하게 유지된다,
          (2) lowlight/adaptive의 mAP 정점이 BLC≈2 부근이다 -- 가 그대로
          성립하는지 검증.
=============================================================================
-->
# ISP 파이프라인 재보정 재측정 (2026-07-08)

## 1. 왜 다시 돌렸나 -- 구 SW-proxy 파이프라인의 gamma 버그

`realraw-sonynod-benchmark-2026-07-06.md` §6ter의 BLC 재보정 ablation은
`newrm_pipeline_blcfix.py`(현재 `tools/archive/`로 이동)로 측정됐다. 같은 날
이후 진행된 리팩터(커밋 `3224dbe`)에서 이 계열 파일들이 실제 HW 파이프라인
(`src/dfxisp_accel.cpp`)과 이미 상당히 어긋나 있었다는 사실이 드러났다:

- `normal` arm 한 곳은 게인/감마를 아예 적용하지 않고 있었다(항등 통과).
- 나머지 경로들은 gamma 지수로 2.2/2.5/4.0 등을 썼는데, 실제 배포된 HW는
  `GAMMA2_LUT`(감마 2.0, `sqrt(255*v)` 룩업)를 normal/low-light 양쪽 모드가
  **공유**한다 -- SW eval의 감마 곡선이 HW와 다른 커브였다는 뜻.

즉 §6ter에서 도출한 "BLC=2가 최적", "arm 순서 역전이 BLC와 무관하다"는 결론은
전부 **HW를 반영하지 않는 감마 곡선 위에서** 얻어진 것이었다. 리팩터로 새로
만들어진 `baseline_isp_pipeline.py`(normal)/`low_light_isp_pipeline.py`
(low-light)/`checker.py`(모드 선택기)는 `dfxisp_accel.cpp`의
`GAMMA2_LUT`/`GAIN_NORMAL`(1.25x)/`GAIN_LOWLIGHT`(2.0x)/`BLC_OFFSET12(_LOWLIGHT)`
상수를 그대로 미러링하는 독립 파일 3종이다. 이번 작업은 여기에 `blc_offset`
오버라이드 파라미터를 추가(순수 additive, 기본값은 기존 상수 그대로 유지)하고
`eval_map_isp.py`로 §6ter와 동일한 스윕(`BLC_OFFSET ∈ {0,1,2,4,8,16}` ×
normal/lowlight/adaptive × 321장)을 그 위에서 재실행한 것이다.

## 2. 새 mAP 표 (yolov8n, n=321, `map_isp_sonynod_blcfix_yolov8n.csv`)

| BLC_OFFSET | normal mAP@.5:.95 | normal mAP@50 | lowlight mAP@.5:.95 | lowlight mAP@50 | adaptive mAP@.5:.95 | adaptive mAP@50 |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.1849 | 0.3356 | 0.1965 | 0.3592 | 0.1967 | 0.3592 |
| 1 | 0.1932 | 0.3489 | 0.2130 | 0.3823 | 0.2129 | 0.3821 |
| **2** | 0.1900 | 0.3414 | **0.2140** | **0.3810** | **0.2140** | 0.3807 |
| 4 | 0.1625 | 0.2995 | 0.1759 | 0.3180 | 0.1758 | 0.3179 |
| 8 | 0.0918 | 0.1827 | 0.1030 | 0.2003 | 0.1030 | 0.1999 |
| 16 (현행) | 0.0344 | 0.0777 | 0.0372 | 0.0842 | 0.0372 | 0.0840 |

`adaptive`가 `lowlight`와 거의 완전히 겹치는 것은 §6ter와 같은 이유 --
SonyNOD 321장 전부가 checker 기준 dark 판정을 받아 `adaptive`가 사실상 매
프레임 `lowlight` 경로를 고르기 때문(`checker.py`의 `selected_mode`, 321장
전체 야간 촬영이라는 §7 한계와 동일).

## 3. 구(§6ter) vs 신(이번) 직접 비교

| BLC_OFFSET | 구 normal | **신 normal** | 구 lowlight/adaptive | **신 lowlight** | **신 adaptive** |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.1356 | **0.1849** | 0.1655 | **0.1965** | **0.1967** |
| 1 | 0.1270 | **0.1932** | 0.1871 | **0.2130** | **0.2129** |
| 2 | 0.1138 | **0.1900** | 0.2004 | **0.2140** | **0.2140** |
| 4 | 0.0892 | **0.1625** | 0.1676 | **0.1759** | **0.1758** |
| 8 | 0.0528 | **0.0918** | 0.0973 | **0.1030** | **0.1030** |
| 16 | 0.0216 | **0.0344** | 0.0356 | **0.0372** | **0.0372** |

(mAP@[.5:.95] 기준, 구 수치는 `map_newrm_sonynod_blcfix_yolov8n.csv` /
`realraw-sonynod-benchmark-2026-07-06.md` §6ter 인용)

**결론 1 -- arm 순서 역전은 gamma fix 이후에도 전 구간에서 유지된다.**
`lowlight/adaptive > normal`이 BLC 0~16 전부에서 그대로 성립한다(예:
BLC=0에서 0.1965 > 0.1849, BLC=16에서도 0.0372 > 0.0344). §6ter가 "BLC와
무관한 구조적 특성"이라 주장한 부분은 gamma 버그와도 무관하게 성립한다는
뜻 -- **이중으로 견고한 결론**이 됐다.

다만 **역전 폭(margin)은 gamma가 고쳐지면서 크게 줄었다.** 구 파이프라인에서는
BLC=2에서 lowlight가 normal 대비 +76%(0.2004 vs 0.1138)였는데, 신 파이프라인
동일 지점은 +12.6%(0.2140 vs 0.1900)에 불과하다. BLC=0에서도 구 +22.1% →
신 +6.3%로 축소. 즉 "lowlight가 이긴다"는 방향은 안 바뀌었지만, 그 격차의
상당 부분은 실제로는 **잘못된 gamma 곡선의 인공물**이었다 -- 정직하게 기록해야
할 부분이다.

**결론 2 -- `normal`은 더 이상 단조 감소하지 않는다.** 구 파이프라인에서는
`normal`이 BLC 0(0.1356)에서 16(0.0216)까지 완전히 단조 감소했다(§6ter, "BLC가
신호를 죽인다"는 가설의 근거). 신 파이프라인에서는 BLC=**1**(0.1932)이
BLC=0(0.1849)보다 오히려 높다 -- `normal`도 이제 **비단조** 곡선이 되어
BLC=1 부근에서 약한 정점을 찍은 뒤(1→2 사이는 사실상 동률, 0.1932 vs 0.1900)
4부터 급격히 감소한다. 올바른 gamma-2.0 곡선 하에서는 binning 없는 `normal`
경로도 아주 작은 BLC(read-noise bias 제거)로 소폭 이득을 보고, 그 이상부터는
§6ter와 동일하게 신호 절단이 손실을 지배한다는 뜻이다 -- 구 결과가 시사했던
"`normal`은 원리적으로 무조건 단조감소"라는 부차적 결론은 gamma 버그의
산물이었고 정정한다.

**결론 3 -- `lowlight`/`adaptive`의 새 정점은 여전히 BLC≈1~2 부근이다.**
BLC=1(0.2130)과 BLC=2(0.2140)가 사실상 동률(차이 0.0010, 노이즈 수준)이고
둘 다 0/4보다 뚜렷이 높다. §6ter가 "BLC=2가 최적"이라 특정했던 것은 정확히는
"1~2 구간이 평평한 정점"이라는 게 더 정확한 서술이지만, 방향과 대략적 위치
자체는 **잘못된 gamma 위에서 얻었음에도 우연히 맞았다** -- 이번 재측정으로
비로소 신뢰할 수 있는 근거가 생겼다.

**부가 관찰 -- 절대 mAP 수준이 전 구간에서 크게 올라갔다.** 예를 들어
BLC=0에서 `normal`은 0.1356→0.1849(+36.4%), `lowlight`는 0.1655→0.1965(+18.7%).
이는 예상된 결과다: 구 파이프라인의 감마 2.2/2.5/4.0(혹은 무-감마) 곡선이
실제 배포 감마-2.0보다 전반적으로 어둡거나 대비가 다른 이미지를 만들어
detector 성능을 체계적으로 낮췄기 때문 -- gamma fix 자체가 이 real-RAW
벤치마크에서 가장 큰 단일 개선이었다.

## 4. 로그/타이밍

- 스윕: `nohup python3 eval_map_isp.py --root ../../../sonynod_test
  --blc-offsets 0,1,2,4,8,16 --tag SonyNOD-ISPFix --model yolov8n.pt
  --out ../results/map_isp_sonynod_blcfix_yolov8n.csv`
- 6개 BLC 값 × 3 arm = 18회의 `model.val()`(321장씩), 각 BLC 값마다 이미지
  합성(321장 × 3 arm)도 포함. 시작 12:12 KST, 완료(CSV write) 16:44 KST --
  **총 약 4시간 32분** 소요 (GPU: RTX 5060 Laptop, CUDA).
- 로그(`eval_full_run.log`) 전체에 에러/트레이스백/NaN 없음, 18행 전부
  `wrote ../results/map_isp_sonynod_blcfix_yolov8n.csv`까지 정상 종료.

## 5. 남은 질문 / 한계

- §6ter와 마찬가지로 이 스윕도 gain/AWB/gamma 중 **BLC_OFFSET만 격리**한
  ablation이다 -- gain(1.25x/2.0x)이나 gamma 자체를 함께 재튜닝하면 정점
  위치가 다시 이동할 가능성은 이번 재측정으로도 해소되지 않았다.
- `checker.py`의 dark-ratio 임계값(`checker-principles-2026-07-05.md`)은
  이번 gamma fix와 무관하게 그대로 사용됐다 -- SonyNOD 321장 전부가 여전히
  dark 판정이라 `adaptive`≈`lowlight` 결과도 동일하게 재현됐다.
- 구 문서(`realraw-sonynod-benchmark-2026-07-06.md`)와 구 CSV
  (`map_newrm_sonynod_blcfix_yolov8n.csv`)는 **수정하거나 삭제하지 않았다**
  -- 이력 보존 목적으로 그대로 두고, 이 문서가 그 결과를 대체(supersede)함을
  여기 명시한다.

## 재현

```bash
cd isppipeline/hls/tools
python3 eval_map_isp.py --root ../../../sonynod_test \
    --blc-offsets 0,1,2,4,8,16 --tag SonyNOD-ISPFix --model yolov8n.pt \
    --out ../results/map_isp_sonynod_blcfix_yolov8n.csv
```

## 산출물

- 코드: `tools/baseline_isp_pipeline.py`(`blc_offset` 파라미터 추가),
  `tools/low_light_isp_pipeline.py`(`blc_offset` 파라미터 추가),
  `tools/eval_map_isp.py`(신규, 이 스윕 전용 드라이버).
- 결과: `results/map_isp_sonynod_blcfix_yolov8n.csv`(신규 18행).
- superseded(보존): `results/map_newrm_sonynod_blcfix_yolov8n.csv`,
  `results/realraw-sonynod-benchmark-2026-07-06.md` §6ter.
