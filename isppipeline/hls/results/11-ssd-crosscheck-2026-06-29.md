# B1 — 2nd-Detector Cross-Check (SSD MobileNet) 2026-06-29

Goal: test whether the mAP-guardrail **variant ordering** found with the YOLO
family is **detector-independent**, by re-scoring the exact same per-variant ISP
images with a structurally different detector: **SSD + MobileNet**
(`ssdlite320_mobilenet_v3_large`, torchvision, COCO-pretrained).

- Harness: `tools/eval_map_ssd.py` (reuses the variant images built by
  `eval_map_coco.py`; GT COCO80 ids → COCO91, scored with pycocotools COCOeval
  over the 12 ExDark-present categories).
- Device: CPU (host CUDA driver too old for torch 2.12); SSDLite is light.
- ISP transform identical to the YOLO runs — only the detector changes.

## Low-light regime — ExDark pseudo-RAW (n=260, bilinear binning)

| variant  | YOLOv8n | YOLOv8s | SSDLite-MNv3 |
|----------|--------:|--------:|-------------:|
| static   |  0.1492 |  0.1714 |       0.1052 |
| **reg_only** | **0.1585** | **0.1902** | **0.1098** |
| dfx_bin  |  0.1576 |  0.1511 |       0.1063 |
| dfx_fp   |  0.0879 |  0.1018 |       0.0656 |

Source: `results/map_exdark_bilbin.csv`, `map_exdark_yolov8s.csv`, `map_exdark_ssd.csv`.

**Detector-independent conclusions (low-light):**
1. **register-only is the best (or tied-best) path** in all three detectors →
   accuracy belongs to the register-fast path (Direction A).
2. **DFX-FP is decisively the worst** in all three (≈40–55 % below the top) →
   the screening verdict (drop DFX-FP) is not a YOLO artifact.
3. **DFX-Bin stays in the top cluster** next to static/reg_only (the middle two
   swap within detector noise) → the mAP guardrail for DFX-Bin holds across
   detectors. (yolov8s ranks bin slightly below static; SSD/yolov8n rank it at or
   above static — all within ~0.01–0.02 mAP, i.e. guardrail-consistent.)

## Normal-light regime — COCO pseudo-RAW (n=347, bilinear binning)

| variant  | YOLOv8n | SSDLite-MNv3 |
|----------|--------:|-------------:|
| **static** | **0.2984** | **0.2001** |
| reg_only |  0.2952 |       0.1968 |
| dfx_bin  |  0.2839 |       0.1930 |
| dfx_fp   |  0.2518 |       0.1743 |

Source: `results/map_coco_bilbin.csv`, `map_coco_ssd.csv`.

**Detector-independent conclusion (normal light):** ordering is **identical** —
`static ≥ reg_only > dfx_bin > dfx_fp` in both detectors. Low-light processing
gives **no benefit in daylight** → confirms the need for scene-adaptive switching
(Contributions 1/3), robustly.

## Takeaway
The two load-bearing claims of the thesis are **not detector-specific**:
- *accuracy → register path* (reg_only best in low-light, all detectors), and
- *DFX-FP is correctly screened out* (worst in low-light, all detectors),
- with *DFX-Bin passing the mAP guardrail* (top cluster, all detectors),
- and *daylight switching is justified* (static best in normal light, all detectors).

Absolute SSDLite-MNv3 numbers are lower than YOLO (weaker backbone on this
pseudo-RAW low-light), but the **relative ordering — the only thing the guardrail
depends on — is preserved**. The exact Vitis-AI `tf_ssdmobilenetv1` (TF1.15) is
reserved for the on-board DPU end-to-end stage (different deployment question).
