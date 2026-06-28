# ISP variant analysis (proxy, no detector)

Synthetic dark scene 96x96, seed=11. Proxy for mAP hypothesis.

| metric | static | reg_only | dfx_bin | dfx_fp |
|---|---|---|---|---|
| mean_luma | 4.491 | 14.618 | 14.107 | 42.743 |
| edge_energy | 0.439 | 0.710 | 0.374 | 0.315 |
| texture_hf | 0.392 | 0.597 | 0.197 | 0.159 |
| hf_retention | 1.000 | 1.526 | 0.504 | 0.406 |
| flat_snr | 4.467 | 19.754 | 29.657 | 91.484 |
| clip_rate | 0.000 | 0.000 | 0.000 | 0.000 |

## 해석 (정직한 평결)
- **feature 보존(핵심):** texture hf_retention Bin=0.504 vs FP=0.406 → 현 정수 DFX-FP는 HF 보존에서 Bin 미달 → **가설 미지지(이 프록시 기준)**. soft-knee lift가 미세 디테일을 압축. RM 재설계(약한 tone+guided detail) 또는 실제 mAP로 판정 필요.
- **denoise:** flat_snr Bin=29.66 vs FP=91.48 — 단, flat_snr는 mean lift에 의해 부풀려지므로(밝기 교란) 단독 결론 금지.
- **밝기:** mean_luma static=4.5 → FP=42.7 (저조도 가시성↑은 명확).
- 전역 edge_energy는 단일 매크로 에지 지배로 변종 구분력 약함 → texture_hf로 판정.
- **결론:** no-reference proxy로는 DFX-FP>DFX-Bin을 확증 못 함. (1) DFX-FP 재설계, (2) 실제 pseudo-RAW mAP(tools/eval_map.py)로 확정. SW단계가 보드 전 이 리스크를 조기 노출함.
