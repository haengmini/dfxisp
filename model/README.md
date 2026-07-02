# DFXISP detector model assets

이 폴더는 DFXISP mAP 실험에서 사용하는 검출기 모델 자산의 표준 위치다. 목적은 YOLO/TorchVision/TensorFlow가 weight를 작업 디렉터리나 `~/.cache`에 흩뿌리지 않도록 repo-local `model/` 아래에 모으는 것이다.

## Layout

```text
model/
  detectors/
    yolo/
      yolov8n.pt
      yolov8s.pt
    ssdlite320_mobilenet_v3_large/
      ssdlite320_mobilenet_v3_large_coco-a79551df.pth
    ssd_mobilenetv1_coco_2018_01_28/
      ssd_mobilenet_v1_coco_2018_01_28/
        frozen_inference_graph.pb
        saved_model/saved_model.pb
        model.ckpt.*
        pipeline.config
      ssd_mobilenet_v1_coco_2018_01_28.tar.gz
  cache/
    torch/hub/checkpoints/
      ssdlite320_mobilenet_v3_large_coco-a79551df.pth
```

## Experiment integration

- YOLO scripts call `tools/model_paths.py::resolve_yolo_model()`.
  - Bare names like `yolov8n.pt` and `yolov8s.pt` resolve to `model/detectors/yolo/`.
- SSD-MobileNetV3 scripts call `tools/model_paths.py::configure_torch_model_cache()`.
  - `TORCH_HOME` is pointed at `model/cache/torch`.
  - TorchVision's expected checkpoint filename is mirrored into `model/cache/torch/hub/checkpoints/`.
- SSD-MobileNetV1 is the TensorFlow Object Detection API COCO model `ssd_mobilenet_v1_coco_2018_01_28`.
  - The frozen graph and saved model are staged locally for TF1/TF-compatible evaluation or Vitis-AI/DPU preparation.

## Source URLs

| Model | Source |
|---|---|
| YOLOv8n | `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt` |
| YOLOv8s | `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt` |
| SSDLite MobileNetV3 Large COCO | `https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth` |
| SSD MobileNetV1 COCO | `http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v1_coco_2018_01_28.tar.gz` |

## Git policy

Large binary weights are runtime/model assets. They are intentionally ignored by git unless a release explicitly decides to track a small checkpoint. Keep this README and scripts versioned; keep heavyweight downloaded files local or publish them through Drive/release artifacts.
