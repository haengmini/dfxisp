# JNU DFXISP AI

RAW 이미지 객체 탐지(Object Detection)를 위한 YOLOv8n 및 SSDLite-MobileNetV3 모델 가중치와 실험 결과를 담고 있는 저장소입니다.

## 모델 (Models)

- **YOLOv8n**: 경량 원스테이지 탐지 모델.
- **SSDLite-MobileNetV3**: 약 223만 개의 파라미터를 가지며, 모델 가중치 파일 크기는 약 17.41 MB입니다.

## 실험 결과 (Experimental Results)

LOD 및 PASCALRAW 메트릭은 각 데이터셋에서 100장의 테스트 이미지를 대상으로 측정되었습니다. Mixed 메트릭은 두 데이터셋을 통합한 검증 세트에서 측정되었습니다. MobileNet의 Precision, Recall, F1 지표는 신뢰도 임계값(confidence threshold) 0.25, IoU 임계값 0.50을 적용했습니다. YOLO 메트릭은 기록된 mAP50-95가 가장 높은 에포크(epoch)의 결과입니다. 체크포인트에 기록되지 않은 수치는 `—`로 표시했습니다.

| 데이터셋 | 탐지 모델 | Precision | Recall | F1 | mAP50 | mAP50-95 | 처리량 (Throughput) |
|---|---|---:|---:|---:|---:|---:|---:|
| LOD | SSDLite-MobileNetV3 | 0.6915 | 0.4736 | 0.5622 | 0.5114 | 0.2980 | 60.4 FPS, batch 8 |
| PASCALRAW | SSDLite-MobileNetV3 | 0.9338 | 0.8598 | 0.8952 | 0.9210 | 0.6775 | 79.1 FPS, batch 8 |
| LOD | YOLOv8n | 0.8695 | 0.6381 | — | 0.7161 | 0.4923 | — |
| PASCALRAW | YOLOv8n | 0.9710 | 0.9069 | — | 0.9448 | 0.7713 | — |
| Mixed (LOD + PASCALRAW) | SSDLite-MobileNetV3 | — | — | — | 0.6155 | 0.3929 | — |
| Mixed (LOD + PASCALRAW) | YOLOv8n | 0.9232 | 0.6370 | — | 0.7299 | 0.5250 | — |
