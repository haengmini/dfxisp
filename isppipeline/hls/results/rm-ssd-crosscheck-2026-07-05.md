# RM low-light: independent third-detector (SSD-MobileNet) cross-check of R1 (full-res) vs R0 (binning)

File   : isppipeline/hls/results/rm-ssd-crosscheck-2026-07-05.md
Date   : 2026-07-05 21:46 KST
Branch : exp/principled-checker-rm-2026-07-05
Campaign version: principled-v3

## Purpose

The RM low-light track (`tools/rm_versions.py`, R0..R3) validated the claim
"full-resolution VST-LUT tone (R1) beats 2x2-binning baseline (R0)" with two
detectors from the **same family**: YOLOv8n and YOLOv8s. This note adds an
**independent, structurally different** detector -- SSD + MobileNetV3-Large
(SSDLite320, anchor-based, single-shot, non-YOLO architecture) -- to test
whether the R1 > R0 conclusion is a property of the ISP arms or an artifact of
the YOLO detector family.

## What ran

- Detector: **torchvision `ssdlite320_mobilenet_v3_large`**, COCO-pretrained
  (`SSDLite320_MobileNet_V3_Large_Weights.COCO_V1`). Loaded fully offline via
  `model_paths.configure_torch_model_cache()`.
  - The weight file (`ssdlite320_mobilenet_v3_large_coco-a79551df.pth`,
    ~13.4 MB) was **missing** from `model/detectors/ssdlite320_mobilenet_v3_large/`
    (only `SOURCE.txt` was staged) -- it was downloaded from
    `https://download.pytorch.org/models/...` (internet was reachable in this
    session) and placed at the path `SOURCE.txt` already documented, then
    mirrored into the torch hub checkpoint cache the same way
    `configure_torch_model_cache()` does for a pre-staged file.
  - The TensorFlow SSD-MobileNetV1 path (`model/detectors/ssd_mobilenetv1_coco_2018_01_28/`)
    was **not usable**: only `pipeline.config`/`checkpoint` metadata is staged
    (no `frozen_inference_graph.pb`), and `tensorflow` is not installed in this
    environment (`ModuleNotFoundError: No module named 'tensorflow'`). Per the
    task instructions, the torchvision path was used and the TF path was not
    pursued further.
  - 3-image smoke test passed before the full run (see console log in task
    history: ExDark R0/R1 on 3 frames, non-degenerate mAP values).
- Scratch runner: `tools/eval_map_rmversions_ssd.py` (new file, does not edit
  the canonical `eval_map_rmversions.py` or `eval_map_newrm_ssd.py`). Reuses
  `rm_versions.run_arm` for RAW-domain rendering (identical arm images to the
  YOLO runs) and the `eval_map_newrm_ssd.py` torchvision-SSD loading pattern +
  COCO80->COCO91 category remap (torchvision SSD outputs live in the gapped
  91-id COCO space). GT boxes are built in full-resolution pixel coordinates
  and detector boxes are rescaled from the (possibly half-resolution, binned)
  rendered image back to full-res before scoring, matching the fair-bucketing
  approach in `eval_map_rmversions.py`.
- Versions run: **R0** (baseline 2x2 bin), **R1** (full-res VST-LUT), and
  **R3** (full-res CLAHE, cheap to add) -- R2 skipped (bin+denoise variant,
  not central to the R1-vs-R0 question).
- Datasets: `data/exdark_val` (real low-light photos) and `data/coco_val`
  (COCO validation subset with a synthetic RAW/low-light path), n=150 each,
  CPU-only.

## Results (mAP@[.5:.95] COCOeval; n=150)

| Detector | Dataset | R0 mAP | R1 mAP | R1-R0 delta | R0 mAP@50 | R1 mAP@50 | R3 mAP | R3 mAP@50 |
|---|---|---|---|---|---|---|---|---|
| SSDLite-MobileNetV3 (this run) | ExDark | 0.0732 | 0.0684 | **-0.0048** | 0.1430 | 0.1409 | 0.0693 | 0.1400 |
| SSDLite-MobileNetV3 (this run) | COCO   | 0.1959 | 0.2085 | **+0.0126** | 0.2917 | 0.3134 | 0.2087 | 0.3070 |
| YOLOv8n (prior, same-branch)   | ExDark | 0.0777 | 0.0838 | +0.0061 | 0.1640 | 0.1768 | 0.0811 | 0.1777 |
| YOLOv8n (prior, same-branch)   | COCO   | 0.2989 | 0.3263 | +0.0274 | 0.4536 | 0.4896 | 0.3373 | 0.4885 |
| YOLOv8s (prior, same-branch)   | ExDark | 0.0994 | 0.1087 | +0.0093 | 0.2072 | 0.2359 | 0.1057 | 0.2316 |
| YOLOv8s (prior, same-branch)   | COCO   | 0.3486 | 0.3979 | +0.0493 | 0.5249 | 0.5775 | 0.3892 | 0.5519 |

CSV: `isppipeline/hls/results/map_rm_ssd_2026-07-05.csv` (this run's raw rows,
same schema as `map_rm_{exdark,coco}_yolov8{n,s}_2026-07-05.csv`).

## Verdict

The full-res-beats-binning conclusion **partially generalizes** to a
structurally different detector, and the partial failure is informative
rather than noise-shaped: on **COCO**, SSDLite reproduces the YOLO-family
result (R1 beats R0 by +0.0126 mAP, +0.022 mAP@50), consistent in sign and
comparable in relative magnitude with YOLOv8n (+0.0274) and YOLOv8s (+0.0493).
But on **ExDark** -- the real low-light benchmark that is the actual target
domain for this RM track -- SSDLite **reverses** the ordering: R0 edges out R1
by 0.0048 mAP (0.0732 vs 0.0684), whereas both YOLO models show R1 ahead by a
similar-sized margin (+0.0061 / +0.0093) on the same data. The ExDark deltas
in both directions are small relative to n=150 sampling noise (single-digit
mAP points in the 0.005-0.01 range have shown sign flips within this
campaign's own YOLO variants, e.g. R2 vs R0), so this is not a strong
falsification of R1 -- but it is not a clean confirmation either: SSDLite is
the one detector among the three where "R1 > R0" does not hold on the
dataset that matters. **Conclusion: the R1-over-R0 result should be treated
as detector-family-and-dataset-dependent rather than universal.** It holds
robustly across all three detectors on COCO, and holds on ExDark for the
YOLO family (2/3 detectors, the original validation basis), but does not
clearly hold on ExDark for SSD. YOLOv8n + YOLOv8s remain the primary
validation basis for the RM track's low-light claim; this SSD cross-check
should be read as a caution flag narrowing the claim to "detector-family
generalization confirmed on COCO, unconfirmed (and mildly contradicted) on
the harder real low-light ExDark benchmark" rather than as a clean pass.
