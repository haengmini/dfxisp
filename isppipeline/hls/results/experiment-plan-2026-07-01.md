---
type: experiment-plan
title: "DFXISP 실험 계획 — shared baseline core + 상호배타 tone RM (reset 반영)"
project: DFXISP
created: 2026-07-01
status: active
sources: "RESEARCH.md §7~§14 · isppipeline/hls (구현/C-sim) · results/08·10·11 (구 variant 결과)"
---

# DFXISP 실험 계획 (2026-07-01 reset 아키텍처 반영)

> 본 문서는 2026-07-01 아키텍처 reset(**shared baseline ISP core + 상호배타
> mode-specific tone RM slot**)을 코드에 반영한 뒤의 실험 실행 계획이다.
> 정본 아키텍처는 `RESEARCH.md`, 검증 스캐폴드는 `isppipeline/hls/`.
> 미검증 수치는 `TODO(측정)`으로 남긴다.

---

## 0. 현재 상태 (실험 출발점)

| 항목 | 상태 |
|---|---|
| baseline core + tone RM slot C-sim 구현 | ✅ `src/dfxisp_accel.cpp` (RM이 core를 감싸는 순서) |
| Python golden(bit-exact 미러) | ✅ `tools/gen_golden_vectors.py` |
| C-sim bit-exact | ✅ `make verify` — golden 566픽셀 mismatch=0 |
| 아키텍처 gate 6종 | ✅ 전부 PASS (`reports/latest.md`) |
| ablation arm(static/reg_only/dfx_bin/dfx_fp) | ✅ `src/dfxisp_rm.cpp` 유지, `make rm-verify` 2816픽셀 mismatch=0 |
| HW 자원/전력/PR-latency | ⬜ 보드/Vivado 단계(TODO) |

> **주의:** 기존 mAP 실측(`results/08-e2`, `11-ssd`)은 **구 variant 모델**
> (`rm_model.py`: static/reg_only/dfx_bin/dfx_fp) 기준이다. reset된 새 경로
> (RAW binning + gamma-4.0, Policy A H/2×W/2)는 **재측정 대상**이며, 구 결과는
> ablation arm 해석에만 그대로 유효하다.

---

## 1. 검증 대상 아키텍처 (구현 확정본)

```text
NORMAL:
  raw HxW
    -> checker_select_mode        (dark 픽셀 비율 < 40%)
    -> RM_NORMAL_TONE (identity)
    -> baseline_isp_core          (demosaic + BLC + AWB + CCM, gain/gamma 없음)
    -> RGB32 (H x W)

LOW_LIGHT:
  raw HxW
    -> checker_select_mode        (dark 픽셀 비율 > 40%)
    -> RM_LOW_LIGHT_TONE.front    (2x2 RAW binning; precision loss 전)
    -> baseline_isp_core          (demosaic + BLC + AWB + CCM, gain/gamma 없음)
    -> RM_LOW_LIGHT_TONE.back     (low-light gain ×1.25 + gamma-4.0)
    -> RGB32 (H/2 x W/2, Policy A)
```

핵심 불변식: **tone RM은 프레임당 정확히 1개(상호배타), gain/gamma는 tone RM에만
존재(baseline core 중복 없음).** C-sim gate로 자동 검증된다.

---

## 2. 실험 가설 (검증할 3가지 claim)

RESEARCH.md §1의 세 claim을 **실험적으로 분리**해서 검증한다.

- **H1 (Algorithmic):** low-light tone RM(`binning + gain + gamma`)이 저조도 장면의
  머신비전 강건성(mAP)을 **정상 ISP(잘못된 모드)나 무처리 대비** 개선한다.
- **H2 (Architecture):** gain/gamma를 baseline core에서 제거하고 tone RM으로 분리해도
  (중복 제거) 정상/저조도 출력 정확도가 유지된다. baseline core는 mode-independent.
- **H3 (DFX efficiency):** DFX가 register-only/always-on 대비 **정적 자원 또는 전력**을
  줄이면서 재구성 오버헤드가 수용 가능하다.

> reset 이전 방향 A의 핵심 관찰(저조도 mAP는 register 경로가 최고, detail-boost RM은
> 탈락, [08-e2·11-ssd])은 **ablation arm 해석**으로 계속 쓰되, 새 tone RM 경로의 H1은
> 재측정으로 확인한다.

---

## 3. 실험 arm 정의 (RESEARCH §7)

| Arm | 구성 | DFX | 목적 | 구현 상태 |
|---|---|---|---|---|
| **Arm 1** | baseline core + RM_NORMAL_TONE(identity) | 없음 | 정상장면 고정 기준·정확도·자원 baseline | ✅ C-sim |
| **Arm 2** | 동일 비트스트림, mode로 tone RM 함수/파라미터 선택 | 없음(register-only) | DFX 없는 적응 이득 분리, 중복제거 확인 | ✅ C-sim(모드 선택) |
| **Arm 3** | static baseline core + DFX가 tone RM slot 교체 | 있음(PR) | 본 연구 핵심 주장, 자원/전력/재구성 비교 | ⬜ Vivado/보드 |
| **Abl.** | post-RGB8 gain/lift, dfx_bin, dfx_fp | — | 새 tone RM 대비 참조/부정사례 | ✅ `dfxisp_rm.cpp` |

핵심 비교축: **Arm 2 vs Arm 3** (register-only 대비 DFX 순이득), **Arm 1 vs Arm 2**
(적응 자체의 이득), **새 RM vs ablation** (설계 선택 정당화).

---

## 4. 단계별 실행 계획 (Phase A~E, RESEARCH §3.2/§8)

### Phase A — golden/정합 잠금 ✅ (완료)
- [x] Python golden = C++ bit-exact (`make verify`, 566px)
- [x] 아키텍처 gate 6종 PASS
- [x] fixture: bright / dark / mixed / threshold-boundary / bright-recovery / odd-dimension
- 산출물: `tests/golden_vectors.csv`, `reports/latest.md`

### Phase B — 저조도 RM 산술 확정 (다음)
- [ ] gain(×1.25)·gamma(γ=4.0)·binning 파라미터 sweep 후보 고정
- [ ] Policy A(H/2×W/2) vs Policy B(upsample/pad) 필요성 판단 — DPU ABI 요구 시에만 B
- [ ] 이미지 지표(§6.1)로 새 RM의 밝기/포화/dark-ratio 개선 정량화
- 도구: `tools/isp_variant_analysis.py` 확장, 신규 fixture

### Phase C — checker/모드 컨트롤러 + 시퀀스
- [ ] 히스테리시스(N 안정프레임) 시퀀스 스케줄러 검증 — `tools/scheduler_sim.py`
- [ ] bright→dark→bright 전환에서 mode flicker 없음, 전환 감지 지연 프레임 수 측정
- [ ] 과도구간(잘못된 모드) mAP 하락 폭 측정(§6.2)

### Phase D — HLS 합성 / RTL / DFX (보드 필요)
- [ ] `make hls DFXISP_HLS_FLOW=csynth` — baseline core / RM_NORMAL_TONE / RM_LOW_LIGHT_TONE
      각각 II/latency/자원(LUT·FF·BRAM·DSP) 리포트
- [ ] tone RM slot DFX floorplan, `pr_verify`, partial bitstream 크기
- [ ] 재구성 지연 = partial bitstream ÷ ICAP 대역폭 (측정 또는 추정)

### Phase E — DPU/mAP end-to-end (보드 필요)
- [ ] Arm 1/2/3 동일 파이프라인으로 COCO/ExDark pseudo-RAW mAP
- [ ] 절대 전력(W), throughput, 전환 오버헤드 실측

> **Non-goals(§13):** Phase A~C(C-sim/golden 정합)가 끝나기 전에는 보드 bring-up,
> DPU 런타임, 실제 비트스트림 스왑, 전력 측정, 대규모 mAP sweep, 논문 문장 다듬기에
> 시간을 쓰지 않는다.

---

## 5. 측정 지표 (RESEARCH §9)

### 5.1 이미지/알고리즘 (Phase B)
`선택 mode / 선택 RM / 입력·출력 크기 / Y mean·std·min·max / 포화율 /
dark-ratio(before·after) / gain·gamma 중복 플래그(기대 false) / (선택)PSNR·SSIM`

### 5.2 머신비전 (Phase C/E)
`mAP@50 및 @[.5:.95] / per-class AP / bright·lowlight·transition segment mAP /
mode-mismatch mAP`. 도구: `tools/eval_map_coco.py`, `eval_map_dark.py`, `eval_map_ssd.py`.

### 5.3 하드웨어 (Phase D/E)
`LUT/FF/BRAM/DSP / clock target·achieved Fmax / frame latency·II /
partial bitstream size / 재구성 지연 / 전환 중 frame drop / 전력(추정·실측)`.

---

## 6. 결과 기록 표 (채울 대상)

### 6.1 정확도 — 새 tone RM 경로 (재측정, TODO)

| dataset | Arm1(정상 tone) | Arm2 저조도 RM | 무처리(none) | 잘못된 모드 |
|---|---|---|---|---|
| ExDark pseudo-RAW (저조도) | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| COCO pseudo-RAW (정상) | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |

기대: 저조도에서 `Arm2 저조도 RM > 무처리`, 정상조도에서 `Arm1 ≥ 저조도 RM`
(→ 장면 적응 스위칭 정당화).

### 6.2 자원/전력 (Phase D, TODO)

| 지표 | Arm1(static+normal) | Arm2(register-only) | Arm3(DFX) |
|---|---|---|---|
| LUT / FF / BRAM / DSP | TODO(측정) | TODO(측정) | TODO(측정) |
| partial bitstream size | — | — | TODO(측정) |
| 재구성 지연 | — | — | TODO(측정) |
| 전력(정상 모드) | TODO(측정) | TODO(측정) | TODO(측정) |

기대(H3): 정상 모드에서 `Arm3 fabric/전력 < Arm2`(저조도 블록 미상주),
재구성 지연은 장면 단위(33ms 프레임 예산 대비) 수용 가능.

---

## 7. 데이터셋/시나리오 (RESEARCH §10)

- **합성 fixture(C-sim):** `NORMAL×3 → LOW_LIGHT×3 → NORMAL×1` + threshold-boundary +
  odd-dimension. bit-exact 디버깅용. (Phase A 완료)
- **pseudo-real:** `data/coco_val`(정상), `data/exdark_val`(저조도). 주의: JPEG/PNG는
  이미 ISP 처리됨 → RAW형 ISP 재적용 시 double-processing 아티팩트 가능. 강한 주장은
  pseudo-RAW/real Bayer로 확정.

재현 예:
```bash
cd isppipeline/hls
python3 tools/eval_map_coco.py --root ../../data/exdark_val --work data/_exdark_work \
    --limit 0 --remap none --tag ExDark --out results/map_exdark_newrm.csv
python3 tools/eval_map_coco.py --root ../../data/coco_val --limit 0 --out results/map_coco_newrm.csv
```

---

## 8. 리스크 / 주의사항

1. **Policy A 형상변경:** 저조도 출력이 H/2×W/2라 DPU 입력 크기가 정상 모드와 다르다.
   end-to-end mAP 전에 DPU ABI 정책(가변 shape 허용 vs Policy B upsample) 결정 필요.
2. **binning-후-demosaic 순서:** 새 경로는 RAW 2x2 binning 뒤 baseline core가 demosaic.
   물리적 화질은 Phase B에서 정량 확인(§4.2가 요구한 "binning이 의미있는 단계"는 충족).
3. **구 mAP 결과 오용 금지:** 08/11은 ablation arm(구 variant) 기준. 새 RM 서사에
   그대로 인용하지 말고 재측정 수치로 대체.
4. **HW 수치 위조 금지:** Vivado/Vitis 없는 환경에서 csynth/전력/PR 수치를 지어내지 않음.

---

## 9. 산출물 / 수용 기준 (RESEARCH §14)

- **산출물:** 본 계획서, `reports/latest.md`(gate), `results/map_*_newrm.csv`,
  Phase D 자원/전력 표, scheduler 로그.
- **수용 기준(현 단계):** ① C-sim/golden 정합 PASS(완료) ② 아키텍처 gate 6종 PASS(완료)
  ③ 향후 리포트가 baseline core / RM_NORMAL_TONE / RM_LOW_LIGHT_TONE / post-RGB ablation /
  register-only / DFX arm을 **명시적으로 구분**할 것.

## 10. 즉시 다음 작업 (우선순위)

1. **Phase B** — 새 tone RM의 이미지 지표 정량화 + gain/γ/binning 파라미터 확정.
2. **Phase C** — scheduler 히스테리시스 시퀀스 + 과도구간 mAP.
3. **정확도 재측정** — 6.1 표를 새 경로 수치로 채움(Arm1/Arm2, ExDark·COCO).
4. **Phase D 준비** — 빈 레이아웃 확보 시 csynth 3-슬롯 자원·partial bitstream.
5. **Co-sim 준비** — §11의 레벨 체인(L2 C/RTL cosim)까지 bit-exact 전파 확인.

---

## 11. SW-HW Co-simulation 상세 계획

새 아키텍처의 SW golden ↔ HW(RTL/DFX) 정합을 **동일 golden vector 하나로 전 레벨에서
bit-exact 전파**시키는 것이 co-sim의 핵심 목표다. golden CSV가 이미 케이스별
`out_w/out_h/sel_mode/sel_rm` 메타데이터와 `kind=raw/rgb` 행을 담고 있어 SW·HW 공통
참조로 그대로 재사용한다.

### 11.1 검증 레벨 체인 (bit-exact 전파)

| Lv | 대상 | 도구 | 참조 | 상태 |
|---|---|---|---|---|
| **L0** | Python golden (기준 of record) | `gen_golden_vectors.py` | — | ✅ |
| **L1** | HLS C-sim (C++ == Python) | `make verify` | L0 golden CSV | ✅ 566px |
| **L2** | **HLS C/RTL Co-sim** (합성 RTL == C TB) | `DFXISP_HLS_FLOW=cosim make hls` | L0 golden CSV(동일 TB) | ⬜ |
| **L3** | RTL 단독 sim (wrapper·AXI-Stream) | Vivado xsim / Verilator | golden `$readmemh` hex | ⬜ |
| **L4** | DFX 멀티프레임 전환 sim (checker+PR FSM+RM swap) | RTL TB `top_sim` | 프레임 시퀀스 golden | ⬜ |
| **L5** | 보드 HIL (실제 PR, ILA 캡처) | ZCU104 + Vitis | golden + ILA | ⬜ |

**불변 계약: L1 == L2 == L3 결과가 동일 golden에 대해 bit-exact.** 어긋나면 그 레벨에서
정지하고 원인(합성 최적화, 정수 반올림, AXI 폭/정렬)을 격리한다.

### 11.2 Co-sim DUT 경계 결정

- **Option A (초기, 권장):** `dfxisp_accel` top 전체(checker + RM front + baseline core +
  RM back)를 **단일 HLS IP**로 C/RTL cosim. 가장 빠르게 L2 정합을 얻는다.
- **Option B (Phase D 후반, DFX 정합):** `baseline_isp_core`(static) + `RM_NORMAL_TONE` +
  `RM_LOW_LIGHT_TONE`를 **개별 HLS IP**로 분리해 각자 cosim한 뒤, tone RM slot(재구성
  영역) + static region 통합. Arm 3(DFX)의 슬롯 구조와 1:1 대응.

> 경계 분리 시 각 IP는 **동일 downstream 인터페이스 계약**(또는 출력 shape 메타데이터)을
> 노출해야 한다(RESEARCH §2.3). RM_NORMAL_TONE(identity)과 RM_LOW_LIGHT_TONE(H/2×W/2)의
> 출력 shape가 다르므로 슬롯 계약에 out_w/out_h를 포함한다.

### 11.3 인터페이스 / 데이터 계약 (co-sim)

- 입력: pseudo-RAW Bayer uint16 (m_axi / 스트리밍 시 `ap_axiu`).
- 출력: packed RGB32 `0x00RRGGBB`.
- 메타데이터: `DfxIspResult{out_width,out_height,selected_mode,selected_rm}` → HW에서는
  **AXI-Lite 레지스터**로 노출, co-sim TB가 값 비교.
- **Policy A 형상변경 대응:** 저조도 출력이 H/2×W/2라 II/latency/출력크기가 모드마다
  다르다 → **모드별로 cosim을 분리 실행**(normal 케이스 묶음 / low-light 케이스 묶음),
  각 실행에서 출력 픽셀 수 = out_w×out_h, 메타데이터 레지스터를 golden과 대조.

### 11.4 C/RTL Co-sim 절차 (L2)

```bash
cd isppipeline/hls
# csim -> csynth -> cosim_design 순으로 실행 (동일 testbench + golden CSV 사용)
DFXISP_HLS_PART=xczu7ev-ffvc1156-2-e DFXISP_HLS_CLOCK=5.0 \
DFXISP_HLS_FLOW=cosim make hls
```

- 드라이버: `tests/test_dfxisp_csim.cpp`(golden CSV bit-compare + 메타데이터 gate) 그대로.
  cosim이 합성 RTL을 이 TB로 구동하므로 **C-sim에서 쓰던 assert가 RTL에도 적용**된다.
- 확인 리포트: `build/vitis_hls/dfxisp_accel/solution1/sim/report/` (cosim pass/fail,
  latency/II 관측치).
- **전제(§11.6): `run_low_light`의 정적 scratch binning 배열을 streaming line buffer로
  리팩터한 뒤 cosim 권장** — 안 하면 큰 BRAM/긴 cosim이 되므로 초기엔 8×8/16×16 소형
  fixture만 cosim.

### 11.5 DFX 멀티프레임 전환 co-sim (L4)

`bright → dark → bright` 시퀀스로 조도 감지 checker + PR 컨트롤러 + RM slot 교체를
RTL에서 검증한다(RESEARCH §5, 구 아키텍처의 5프레임 시나리오를 tone RM slot에 맞게 개정).

| Frame | 입력 | 기대 동작 | 검증 |
|---|---|---|---|
| F1 | Bright | NORMAL, RM_NORMAL_TONE(identity), 출력 H×W | golden bit-compare + 메타 |
| F2 | Dark | checker dark>40% → `mode_changed` → **drain** → PR(LOW_LIGHT RM 적재) | drain 무손실, pr_done |
| F3 | Dark | LOW_LIGHT, RM_LOW_LIGHT_TONE, 출력 H/2×W/2 | golden bit-compare + shape |
| F4 | Bright | checker recovery → drain → PR(NORMAL RM 적재) | drain 무손실, pr_done |
| F5 | Bright | NORMAL 원복 | golden bit-compare + 메타 |

측정: **전환 감지 지연(프레임)**, **재구성 지연(cycle → ms)**, **drain 중 frame drop=0**,
히스테리시스로 flicker 없음. 재구성 중에는 이전 RM 또는 identity fallback 경로 유지
(RESEARCH §5.3의 PR 진행 중 fallback).

### 11.6 Co-sim 전제조건 / 리스크

1. **streaming 리팩터 선행:** `run_low_light`의 `static uint16_t binned[...]`(현재 결정적
   C-sim용)은 합성 시 대형 BRAM. cosim/합성 전에 진짜 2-라인 버퍼 producer로 교체
   (README "다음 하드웨어 단계" 1번). 초기 L2는 소형 fixture로 우회.
2. **정수 정합:** gamma-4.0을 `floor((255^3·v)^(1/4))` 정수 4제곱근으로 구현했으므로
   부동소수 합성 불일치 위험이 없다(SW·HW 동일 정수식). AWB/BLC도 정수 Q8 → L2에서
   bit-exact 기대.
3. **모드별 II/latency 상이:** normal(full-res)과 low-light(binning, 1/4 픽셀)의 latency가
   다르므로 리포트를 arm/모드별로 분리 기록.
4. **AXI 폭/정렬:** 출력 RGB32는 2의 거듭제곱 폭이라 DMA 정합 용이. 입력 RAW16 스트리밍
   폭·패킹은 L3에서 확정.

### 11.7 Co-sim 수용 gate

```text
[L2] C/RTL cosim: golden bit-exact PASS + 메타데이터(out_w/out_h/sel_rm) 일치
[L3] RTL wrapper sim: $readmemh golden 대비 error_count=0 (normal·low-light 각각)
[L4] DFX 전환: frame drop=0, mode/RM 메타 전환 정확, 재구성 지연 기록, flicker 없음
[전체] L1==L2==L3 동일 golden에 bit-exact; 불일치 시 해당 레벨에서 정지·격리
```

> co-sim은 Phase D(HW)의 일부다. Vivado/Vitis HLS가 없는 환경에서는 L2~L5 수치를
> 만들지 않고 `TODO(측정)`으로 둔다(§8 주의 4).
