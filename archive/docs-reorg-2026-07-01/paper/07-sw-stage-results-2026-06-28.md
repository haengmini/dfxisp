---
type: sw-stage-results
title: "DFXISP — SW 단계 실행 결과 (보드 불필요 단계 완료)"
project: DFXISP
created: 2026-06-28
note: "실제 실행 결과. 측정값은 SW 환경(C-sim/numpy) 산출이며 보드 수치(자원/전력/PR latency/실 mAP)와 별개."
---

# SW 단계 실행 결과 (2026-06-28)

재현: `cd isppipeline/hls && make sw-stage` (= verify + rm-verify + scheduler + analysis)

## E1 — 4-variant RM bit-exact (S1~S3)
- 구현: `src/dfxisp_rm.cpp` ↔ `tools/rm_model.py` (Python 캐노니컬, 정수 연산 동일).
- 변종: STATIC / REG_ONLY / DFX_BIN(2×2 binning+gain, HxW 복원) / DFX_FP(soft-knee + green-gated local contrast).
- 골든: `tests/rm_golden_vectors.csv` (5 케이스 × 4 변종 = 2816 px).
- **결과: mismatch=0 / 2816 px (bit-exact 통과).** → Tab6 `bit_exact_mismatch=0`.
- 기존 baseline C-sim(48px, 3케이스)도 통과 유지. (참고: reports/latest.md의 "832px/7케이스"는 커밋된 golden_vectors.csv(48px)와 불일치 — 문서 과대표기, 정정 필요.)

## E3 — DFX-aware scheduler 시뮬 (실수치)
`tools/scheduler_sim.py`, 1000 프레임 노이즈 시퀀스, seed=7.

| metric | baseline | +hysteresis | +temporal | +min_dwell |
|---|---|---|---|---|
| mode_mismatch_rate | 0.054 | 0.021 | 0.140 | 0.140 |
| switch/1k | 86.0 | 28.0 | 4.0 | 4.0 |
| thrashing_rate | 0.884 | 0.571 | 0.000 | 0.000 |
| skipped/invalid | 344 | 112 | 16 | 16 |

**분석:** hysteresis+temporal로 **switch 86→4/1k(≈21×↓), thrashing 0.88→0(제거), skipped 344→16(≈21×↓)**. 단 temporal smoothing의 lag로 **mismatch는 0.054→0.140 증가**(경계 구간 모드 지연). → DFX는 전환비용이 크므로 안정성↑이 정당, 단 TEMPORAL_N 튜닝으로 mismatch-안정성 균형 필요. (정직한 trade-off; "전부 개선"이 아님.)

## E2(proxy) — ISP 변종 분석 (detector 없이)
`tools/isp_variant_analysis.py`, 합성 저조도 96×96, seed=11.

| metric | static | reg_only | dfx_bin | dfx_fp |
|---|---|---|---|---|
| mean_luma | 4.49 | 14.62 | 14.11 | 42.74 |
| texture_hf | 0.392 | 0.597 | 0.197 | 0.159 |
| hf_retention | 1.000 | 1.526 | 0.504 | 0.406 |
| flat_snr | 4.47 | 19.75 | 29.66 | 91.48 |

**정직한 평결 (음성/미결):**
- **feature 보존:** texture HF 보존에서 **현 정수 DFX-FP(0.406) < DFX-Bin(0.504)** → 이 프록시 기준 "FP가 feature를 더 보존한다"는 **가설을 지지하지 못함**. 원인: soft-knee lift가 미세 디테일을 압축.
- **denoise:** flat_snr는 FP가 높지만 mean-lift에 부풀려져(밝기 교란) 단독 근거 불가.
- **가시성:** 저조도 밝기 향상(static 4.5→FP 42.7)은 명확.
- **결론:** no-reference proxy로는 DFX-FP 우위를 확증 못 함. 두 경로: **(1) DFX-FP RM 재설계**(약한 tone + guided detail/unsharp 강화) **(2) 실제 pseudo-RAW mAP**(`tools/eval_map.py`)로 확정. **SW 단계가 보드 투입 전에 이 리스크를 조기 노출**한 것이 핵심 가치.

## E2(full mAP) — 하니스 준비 완료, 실행은 의존성/데이터 필요
`tools/eval_map.py` — pseudo-RAW → variant ISP(rm_model, C-sim과 bit-exact) → YOLO → COCO mAP. 
실행 전제: `pip install numpy pillow torch torchvision ultralytics pycocotools` + `DFXISP/dataset/COCO_5000_raw` + COCO ann json. (현 환경 미설치 → 미실행.)

## 산출 파일
- 코드: `src/dfxisp_rm.cpp`, `include/dfxisp_rm.hpp`, `tests/test_rm_csim.cpp`
- 도구: `tools/{rm_model,gen_rm_golden,scheduler_sim,isp_variant_analysis,eval_map}.py`
- 결과: `results/{scheduler.csv,isp_analysis.csv,isp_analysis.md}`, `tests/rm_golden_vectors.csv`
- Make: `make sw-stage` (재현)

## 다음 (보드 단계 / 또는 SW 재설계)
1. (권장) DFX-FP RM 재설계 후 E2(proxy)·E2(mAP) 재평가 — RM 사양 04 §2 갱신.
2. 실제 mAP: eval_map.py로 COCO/ExDark 평가 → Tab6.
3. 보드: csynth/cosim → Vivado DFX → ZCU104 → Tab4/5, Fig7/8.
