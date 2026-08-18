#!/usr/bin/env python3
"""Repository-local detector model path helpers for DFXISP experiments.

Detector weights are kept under the top-level `model/` directory so evaluation
scripts do not scatter YOLO/Torch/TensorFlow downloads across cwd or ~/.cache.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_ROOT = REPO_ROOT / "model"
DETECTOR_ROOT = MODEL_ROOT / "detectors"

YOLO_WEIGHTS = {
    "yolov8n.pt": DETECTOR_ROOT / "yolo" / "yolov8n.pt",
    "yolov8s.pt": DETECTOR_ROOT / "yolo" / "yolov8s.pt",
}

TORCH_HOME = MODEL_ROOT / "cache" / "torch"
TORCHVISION_CHECKPOINTS = TORCH_HOME / "hub" / "checkpoints"
SSDLITE_MNV3_WEIGHTS = (
    DETECTOR_ROOT
    / "ssdlite320_mobilenet_v3_large"
    / "ssdlite320_mobilenet_v3_large_coco-a79551df.pth"
)
SSD_MNV1_FROZEN_GRAPH = (
    DETECTOR_ROOT
    / "ssd_mobilenetv1_coco_2018_01_28"
    / "ssd_mobilenet_v1_coco_2018_01_28"
    / "frozen_inference_graph.pb"
)


def resolve_yolo_model(model: str) -> str:
    """Resolve known YOLO weight names to repo-local model/detectors paths."""
    p = Path(model)
    if p.exists() or p.is_absolute() or any(sep in model for sep in ("/", "\\")):
        return str(p)
    local = YOLO_WEIGHTS.get(model)
    if local and local.exists():
        return str(local)
    return model


def configure_torch_model_cache() -> None:
    """Point torchvision/torch hub at repo-local model/cache/torch.

    If the SSDLite MobileNetV3 checkpoint exists under model/detectors, mirror it
    into the checkpoint name expected by torchvision so `weights=COCO_V1` works
    offline and uses the model-folder asset.
    """
    os.environ.setdefault("TORCH_HOME", str(TORCH_HOME))
    TORCHVISION_CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    dst = TORCHVISION_CHECKPOINTS / SSDLITE_MNV3_WEIGHTS.name
    if SSDLITE_MNV3_WEIGHTS.exists() and not dst.exists():
        try:
            dst.write_bytes(SSDLITE_MNV3_WEIGHTS.read_bytes())
        except OSError:
            # If the mirror fails, torchvision may still download to TORCH_HOME.
            pass

