<!--
=============================================================================
File   : isppipeline/hls/results/blc-fix-resynthesis-2026-07-03.md
Date   : 2026-07-03
Time   : 08:55 KST
Function: Low-light BLC relaxation applied to the canonical HW/SW pipeline
          (src/dfxisp_accel.cpp, tools/gen_golden_vectors.py,
          tools/isp_pipeline_ver1.py) and the full Vitis HLS + Vivado DFX
          flow re-run end to end, combined with the pblock floorplan fix
          from phase0-2-execution-2026-07-03.md.
Goal   : "반영해서 재합성 해봐" (apply it and re-synthesize) -- close the loop
          on the low-light mAP root-cause finding with real HW numbers.
=============================================================================
-->
# BLC 완화 정본 반영 + 전체 재합성 (2026-07-03)

> `phase0-2-execution-2026-07-03.md`의 1.1/1.2 ablation에서 검증된 저조도 BLC
> 완화(16→8)를 `src/dfxisp_accel.cpp`/`gen_golden_vectors.py`/`isp_pipeline_ver1.py`
> **정본 파이프라인에 반영**하고, Vitis HLS csynth 3종 + Vivado DFX 전체 흐름을
> **2.2에서 검증한 수정된 pblock floorplan(X1Y0:X2Y0)과 함께 재실행**했다.

## 1. 코드 변경

`apply_blc_wb12()`에 `blc_offset` 매개변수 추가 — WB/CCM은 두 모드가 여전히
완전히 같은 코드 경로(동일 함수)를 쓰고, BLC 오프셋만 모드별로 분기:
- `baseline_core12()`(NORMAL 경로): `BLC_OFFSET12`(16<<4=256, 불변)
- `run_low_light()`(LOW_LIGHT 경로): **`BLC_OFFSET12_LOWLIGHT`(8<<4=128, 신규)**

세 파일(C++ `dfxisp_accel.cpp`, golden `gen_golden_vectors.py`, SW eval
`isp_pipeline_ver1.py`)에 동일 로직을 반영. `make verify`(646px bit-exact) +
신규 cross-check 게이트(0.1) 모두 통과. `isp_pipeline_ver1.py`의 `lowlight` arm이
`isp_pipeline_ablation.py`의 검증된 `ll_blc_relaxed` 변형과 **numpy 배열
단위로 완전히 동일**함을 재확인(`np.array_equal` True).

## 2. mAP 재측정 (표준 표본 크기 n=71/80, 기존 Stage 3와 직접 비교 가능)

| dataset·arm | 수정 전(ver1) | **수정 후** | Δ |
|---|---:|---:|---:|
| ExDark·none | 0.1561 | 0.1561(참조 불변) | — |
| ExDark·normal | 0.0826 | 0.0826(참조 불변) | — |
| **ExDark·lowlight** | 0.0586 | **0.1043** | **+78.0%**, normal 대비 +26.3% |
| ExDark·adaptive | 0.0606(ver2) | **0.1018** | **+68.0%** |
| COCO·none | 0.3276 | 0.3276(참조 불변) | — |
| COCO·normal | 0.2772 | 0.2772(참조 불변) | — |
| **COCO·lowlight** | 0.2647 | **0.2857** | **+7.9%** |
| COCO·adaptive | 0.2752(ver2) | **0.2795** | +1.6% |

**처음으로 `lowlight`가 `normal`을 앞질렀다**(ExDark 0.1043 > 0.0826). `none`은
여전히 최고(SW proxy 천장 가설 불변, guardrail 결론 유지)지만, 격차가 크게
좁혀졌고 COCO에서도 개선되어 안전성이 재확인됐다.

## 3. HLS C-synthesis 재실행 — 자원 변화 없음(예상대로)

| top | LUT | FF | BRAM | DSP | Fmax |
|---|---:|---:|---:|---:|---:|
| `dfxisp_accel`(unified) | 8,264(불변) | 5,536(불변) | 9(불변) | 24(불변) | 273.97MHz |
| `rm_normal_tone_top` | 5,202(불변) | 3,797(불변) | 4(불변) | 12(불변) | 273.97MHz |
| `rm_low_light_tone_top` | 4,204(불변) | 3,243(불변) | 8(불변) | 9(불변) | 273.97MHz |

**세 top 모두 수정 전과 완전히 동일.** 이 fix는 상수값 하나(BLC 오프셋)만
바꾸는 순수 파라미터 변경이라 HLS가 생성하는 회로 구조 자체는 그대로다 —
**mAP 개선이 하드웨어 자원 관점에서는 "공짜"**였다는 뜻. (unified/normal RM은
정의상 당연하고, low-light RM도 constant 하나만 바뀌었을 뿐 연산 구조는
`apply_blc_wb12` 그대로라 동일하게 나왔다.)

## 4. Vivado DFX 재구현 — BLC fix + pblock fix 결합

이번 재구현은 **두 가지 개선을 동시에** 반영한다: (a) 이 문서의 BLC fix,
(b) `phase0-2-execution-2026-07-03.md` §2.2에서 검증한 pblock floorplan 수정
(`CLOCKREGION_X1Y0:X2Y0` — PS 매크로가 차지한 X0 컬럼을 피함, 용량 2배).

| 지표 | Config1(static+RM_NORMAL) | Config2(static+RM_LOW_LIGHT) |
|---|---|---|
| CLB LUT | 3,972(1.73%, 구 8,640 기준 용량 대비 pblock 재검토 전과 거의 동일) | 2,927(1.27%) |
| Block RAM Tile | 1.5(0.48%) | 3.5(1.12%) |
| DSP | 12(0.69%) | 8(0.46%) |
| pblock 용량(수정된 floorplan) | LUT 19,200 / BRAM 24 tile / DSP 216 | 동일(static 공유) |
| **pr_verify** | — | **✅ PASS**(static tile 29,573·cell 256 동일, 재구현 후에도 유지) |

## 5. Bitstream — partial 크기가 pblock 확장의 직접적 대가

| 산출물 | 수정 전(686,664B 기준) | **수정 후(pblock 2배)** | 비 |
|---|---:|---:|---:|
| full bitstream | 19,311,211 B(불변) | 19,311,211 B(불변) | 1.00x |
| partial bitstream(양쪽 RM 동일) | 686,664 B | **1,447,424 B** | **2.11x** |

**중요한 트레이드오프(정직하게 기록):** §2.2에서 확보한 "용량 2배"는 공짜가
아니다 — pblock의 reconfigurable frame 수가 늘어난 만큼 **partial bitstream도
거의 정확히 비례해서 커진다**(2.11배, LUT 용량 증가율 2.22배와 근접). 이는
"partial bitstream 크기는 로직 사용량이 아니라 pblock 프레임 수로 결정된다"는
기존 발견(`stage5-dfx-implementation-2026-07-02.md`)의 직접적 재확인이자,
**§6의 ICAP latency 재계산에 그대로 반영**된다.

### 5.1 ICAP latency 재계산 (파일 직접 파싱, 🧮스펙 유도)

| 지표 | 수정 전 | **수정 후(2.11x 큰 payload)** |
|---|---:|---:|
| payload(헤더 제외) | 686,532 B | **1,447,292 B** |
| word 수 | 171,633 | **361,823** |
| ICAP peak(400MB/s) | 1.716 ms | **3.618 ms** |
| ICAP 전형(100MB/s) | 6.865 ms | **14.473 ms** |

**결론:** pblock 확장(§2.2)이 자원 여유는 늘렸지만 **재구성 지연은 약 2.1배로
늘어난다** — 여유 있는 RP 영역을 고를 때는 이 트레이드오프를 명시적으로
고려해야 한다. 이번 프로젝트의 실제 RM 크기(LUT 3~4천대)에는 원래의 좁은
pblock(X0Y0:X1Y0, 용량 8,640이었지만 실은 PS 매크로 때문에 사실상 불량한
선택)으로도 충분했다는 뜻이기도 하다 — **더 큰 RP가 필요할 미래 후보를 위해
용량을 확보해둔 대가로 지금 당장은 재구성 지연만 늘어난 상태.**

## 6. 종합 평가

1. **알고리즘 개선은 성공적으로 정본에 반영됐고 HW 비용이 없다** — 자원/타이밍
   전부 불변, mAP만 개선(ExDark +78%, COCO +8%, 둘 다 안전).
2. **pblock 확장은 별도의 트레이드오프다** — 자원 여유(2배) vs 재구성 지연(2.1배)를
   맞바꾼 것이므로, "무조건 좋은 개선"으로 포장하지 않는다. 실제 배포 시에는
   RM 후보 크기가 확정된 뒤 필요한 만큼만 pblock을 넓히는 것이 맞다(현재
   RM들은 원래 좁은 pblock으로도 충분히 들어갔다).
3. **pr_verify PASS가 두 독립적 개선(알고리즘+floorplan)을 동시에 적용한
   뒤에도 유지됐다** — DFX 방법론(black-box+lock)이 여러 변경을 누적해도
   견고하게 작동함을 재확인.

## 산출물
- 코드: `src/dfxisp_accel.cpp`, `tools/gen_golden_vectors.py`,
  `tools/isp_pipeline_ver1.py`(BLC 파라미터화).
- 결과: `results/map_ver1_{exdark,coco}_yolov8n_blcfix.csv`.
- `/tmp` 산출물(git 비추적): `config{1,2}_final.util.rpt`, `pr_verify_final.rpt`,
  `pblock_capacity_final.rpt`, `config1_full_final.bit`,
  `rm_{normal,lowlight}_partial_final.bit`.
