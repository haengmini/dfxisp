<!--
=============================================================================
File   : isppipeline/hls/results/blc-recalibration-deploy-2026-07-20.md
Date   : 2026-07-20 KST
Function: BLC 재보정(16/8 -> 2/2) 배포 반영 기록. 사용자 승인("BLC 1/2 재보정
          승인") 하에 lod-pascal-isp-simulation-2026-07-15.md §9의 다음 단계
          후보 1번을 실행 -- 상수 변경 + HW golden 재생성 + bit-exact 재검증.
Sources: lod-pascal-isp-simulation-2026-07-15.md (27개 조합 실측, 승인 근거),
         isp-pipeline-recalibration-2026-07-08.md (BLC {0,1,2,4,8,16} 스윕),
         src/dfxisp_accel.cpp, tools/gen_golden_vectors.py,
         tools/baseline_isp_pipeline.py, tools/low_light_isp_pipeline.py
=============================================================================
-->
# BLC 재보정 배포 반영 — 16/8 → 2/2 (2026-07-20)

## 0. 결론부터

사용자 승인에 따라 배포 BLC 상수를 **normal 16 → 2, lowlight 8 → 2**로
변경하고, HW golden 재생성 + `make verify`/`make rm-verify` bit-exact
재검증을 전부 통과시켰다. 커밋된 `tests/golden_vectors.csv`가 새 정본이다.

## 1. 값 선택 근거 — 왜 1이 아니라 2인가

승인 문구는 "BLC 1/2"였고 실측상 1과 2는 대부분 노이즈 수준 동률이다.
**단일값 2**를 택한 이유:

1. `isp-pipeline-recalibration-2026-07-08.md` §3 결론 3: lowlight/adaptive
   정점이 BLC=2(0.2140), 1과의 차이 0.0010은 노이즈 수준 — "1~2 평평한 정점".
2. `lod-pascal-isp-simulation-2026-07-15.md` §8.2: Shuffle_split(실배포 인구
   근사)에서 adaptive가 normal/lowlight 둘 다 이기는 유일한 지점이 BLC=2.
   PASCAL lowlight mAP@50 정점도 BLC=2(0.9007).
3. normal arm 단독으로는 BLC=1이 근소 우위(LOD 0.2005 vs 0.1935)지만,
   normal=1/lowlight=2 혼합 구성은 **한 번도 실측된 적이 없다** — 실측된
   구성 중에서 고른다는 원칙상 단일값 2가 유일한 선택지.
4. 모드 간 단일값 공유로 2026-07-03의 "lowlight 전용 완화" 특례가 자연
   소멸 — `BLC_OFFSET12_LOWLIGHT`는 값이 같아졌지만 파라미터 구조(콜사이트
   구분)는 유지해 향후 재분화 여지를 남김.

참고: 07-15 실험의 "BLC=16" 행은 lowlight arm에도 16을 강제한 것이라 실제
배포 구성(normal 16/lowlight 8)과 정확히 같지는 않다. 그러나 07-08 스윕이
BLC=8 lowlight 0.1030 vs BLC=2 0.2140을 별도 실측했으므로, 기존 배포값 8
대비로도 2가 약 2배 우위 — 어느 쪽 기준으로도 결론은 같다.

## 2. 변경 파일 (상수 4곳 + 주석)

| 파일 | 변경 |
|---|---|
| `src/dfxisp_accel.cpp` | `BLC_OFFSET12 = 2<<4`, `BLC_OFFSET12_LOWLIGHT = 2<<4` (기존 16<<4 / 8<<4) |
| `tools/gen_golden_vectors.py` | 동일 상수 미러 2곳 갱신 |
| `tools/baseline_isp_pipeline.py` | `BLK_RAW = 2 << SHIFT` |
| `tools/low_light_isp_pipeline.py` | `BLC_OFFSET_LOWLIGHT = 2 << SHIFT` + 구식 경고 주석 정정("optimal 2는 잘못된 gamma 스윕 산물이라 신뢰 불가" → 07-08/07-15 정본 파이프라인 재실측으로 반증됨) |

`tools/checker.py`는 **무변경** — 체커는 BLC 이전 단계(plain demosaic view,
`DARK_Y=50`)에서 동작하므로 BLC 상수와 독립. `tests/test_dfxisp_csim.cpp`의
256/512 값도 체커 dark 임계값 파라미터라 무관(무변경).

## 3. 검증 (전부 통과, 2026-07-20 데스크톱)

1. `make verify` — golden 재생성(13 cases/1913 rows) → csim 재빌드 →
   **golden vector compare passed (726 pixels)** + smoke 통과 →
   cross-check 2종(binning 500 grids, bilinear demosaic 200 grids) 통과.
2. `make rm-verify` — RM golden(2816 rows, 20 cases) **mismatch=0**. 톤 RM은
   BLC를 포함하지 않으므로 RM golden CSV는 변경 자체가 없음(예상대로).
3. 정합성 스모크: 새 기본값의 `run_normal()`/`run_lowlight()`가 07-08/07-15
   스윕에서 쓴 `blc_offset=2` 오버라이드 출력과 **bit-exact 동일** 확인
   (random 64×48 bayer, numpy array_equal).

## 4. 남은 것 / 리스크

- ~~**csynth/cosim 미재실행**~~ **완료(2026-07-20, 같은 날 늦게)** — csynth 자원/타이밍
  완전 동일(BRAM 9/DSP 24/FF 5,536/LUT 8,264/3.650ns, 상수 변경 전과 일치), cosim RTL
  시뮬레이션 10/10 트랜잭션 완주. 자동 post-check만 기존에 이미 알려진 WSL2+Vitis HLS
  2024.1+XSIM SIGSEGV 버그로 미완주(회귀 아님) — 상세:
  `results/blc-c1-csynth-cosim-rerun-2026-07-20.md`.
- **화질 vs detector-선호 미분리** — `lod-pascal-isp-simulation-2026-07-15.md`
  §8.4가 지적한 대로, BLC=2의 압도적 mAP 우위가 실제 화질 개선인지 detector가
  잔류 노이즈/암전류를 선호하는 것인지는 육안/PSNR로 별도 확인된 바 없다.
  mAP 최적화가 이 파이프라인의 명시적 목표라 배포 근거로는 충분하지만,
  타 지표 소비자가 생기면 재검토 필요.
- checker-status-2026-07-10.md §4 관문 4(C1/adaptive-τ 배포 결정)는 이번
  변경과 **별개로 미결** — adaptive-τ는 여전히 SW 실험 코드에만 존재.
