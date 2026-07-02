# DFXISP 검출기 모델 자산

이 폴더는 DFXISP mAP 실험에서 사용하는 검출기 모델 자산의 표준 보관 위치다. 목적은 YOLO, TorchVision, TensorFlow 계열 detector weight가 작업 디렉터리나 `~/.cache`에 흩어지지 않도록, repo-local `model/` 아래에 모아 관리하는 것이다.

## 폴더 구조

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

## 실험 스크립트 연동 방식

- YOLO 계열 평가 스크립트는 `tools/model_paths.py::resolve_yolo_model()`을 사용한다.
  - `yolov8n.pt`, `yolov8s.pt`처럼 파일명만 넘기면 `model/detectors/yolo/` 아래의 local weight로 자동 해석된다.
- SSD-MobileNetV3 평가 스크립트는 `tools/model_paths.py::configure_torch_model_cache()`를 사용한다.
  - `TORCH_HOME`을 `model/cache/torch`로 지정한다.
  - TorchVision이 기대하는 checkpoint 파일명을 `model/cache/torch/hub/checkpoints/` 아래에 mirror해서, 가능하면 네트워크 재다운로드 없이 repo-local weight를 사용한다.
- SSD-MobileNetV1은 TensorFlow Object Detection API의 COCO 모델 `ssd_mobilenet_v1_coco_2018_01_28`이다.
  - `frozen_inference_graph.pb`와 `saved_model/`을 local에 보관해 TF1/TF-compatible 평가, Vitis-AI 변환, DPU 준비 단계에서 사용할 수 있게 한다.

## 모델 출처

| 모델 | 출처 |
|---|---|
| YOLOv8n | `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt` |
| YOLOv8s | `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt` |
| SSDLite MobileNetV3 Large COCO | `https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth` |
| SSD MobileNetV1 COCO | `http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v1_coco_2018_01_28.tar.gz` |

## Git 관리 정책

대용량 binary weight는 runtime/model asset으로 취급한다. 명시적으로 release 자산으로 추적하기로 결정하지 않는 한 Git에는 올리지 않는다. Git에는 다음만 versioning한다.

- 이 `README.md`
- `model/detectors/manifest.json`
- 각 모델 폴더의 `SOURCE.txt`
- 실험 스크립트와 model path helper
- 작은 설정 파일: 예를 들어 `pipeline.config`, `checkpoint`

무거운 weight 파일은 local `model/detectors/`에 유지하거나, 필요하면 Google Drive 또는 GitHub release artifact로 별도 배포한다.
