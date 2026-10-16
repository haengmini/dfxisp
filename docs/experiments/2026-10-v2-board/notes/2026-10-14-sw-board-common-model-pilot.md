# SW–보드 공통 검출 모델 재현 파일럿

## 상태
1) 모델/활성화/resize/NMS 분리 72조건 실행 완료.
2) 공통 FP32 후보 및 동일 전처리 검증 완료.
3) 시험/검증과 분리된 보정, host INT8 평가, xmodel export 및 DPU compile 완료.
4) 보드 DPU-only 재생 640회 완료. 이후 사용자 콜드 부팅 확인·ICAP 검증 후 RAW→ISP→DPU live 야간100장 측정 완료. 총200 ISP 출력 SHA256 일치, 400 DPU검출 모두 replay와 완전동일. YOLO Normal/Lowlight mAP50-95 .06045/.08611, SSD .07664/.09440. 상세 원자료·보고서 `/opt/data/work/blc16_dfx_board_20261014/common_dpu_pilot/live/`. 자동선택 DFX·주간/혼합·BLC16 새후보 조합은 이번 범위 아님.

## 범위 및 중요한 한계
- 기존 고성능 프로젝트 모델을 교체하지 않았다. 새 모델은 공식 COCO YOLOv8n의 Hardswish 치환 및 공식 COCO SSDLite의 raw head. COCO-Hardswish는 원형보다 절대 정확도가 낮으므로 최종 성능 설계로 채택한 것이 아니다.
- 기존 채택 SW 설계 재현을 위해 BLC32를 사용했다. 이번 BLC16 개선안의 성능 실험과 별도이다. 원본에 반영된 BLC16 소스와 새 partial은 되돌리지 않았다.
- 같은 무손실 RGB, half-pixel float bilinear no-antialias, YOLO unit/SSD pm1, 동일 CPU decode/NMS 및 eval_map 채점. 공통 NumPy resize는 대표 8조건에서 torch interpolate와 최대 오차 <1e-6.
- 보정: ft_hw/train의 사전 결정된 32프레임 × Normal/Lowlight = 모델별 64 입력. 야간 데이터만 사용하므로 주간·혼합 대표성은 확보하지 않았다. val60과 LOD test100 프레임 ID 교집합 없음. 학습·미세조정 및 시험 데이터 보정 없음. val60은 기존 연구에서도 사용된 분할이므로 프로젝트 전체 관점의 완전히 새로운 데이터는 아니다.
- CPU 양자화 환경: Vitis AI 3.5 CPU image + 별도 폴더 vendor ultralytics 8.3.0. GPU FP32 환경의 torch/torchvision/ultralytics 버전과 차이가 있으나 CPU FP32에서도 야간 경향 유지 확인.
- 새 모델 DPU fingerprint 72339070457545735가 기존 모델과 일치. 두 모델 각각 DPU subgraph 1개, YOLO 6 raw-head 출력(64/80채널), SSD 2 출력(4/91채널) 확인.

## 실제 결과 (mAP50-95)
| 검증60장 | YOLO Normal | YOLO Lowlight | SSD Normal | SSD Lowlight |
|---|---|---|---|---|
| 공통 CPU FP32 | .10646 | .13401 | .14144 | .15460 |
| host INT8 | .08664 | .11449 | .09338 | .10849 |
| 보드 DPU 재생 | .08799 | .11416 | .09450 | .10910 |

| 시험100장, 보드 DPU 재생 | Normal | Lowlight |
|---|---|---|
| COCO-Hardswish YOLO | .06045 | .08611 |
| COCO SSD | .07664 | .09440 |

두 모델에서 Lowlight 우세가 host INT8→compiled DPU까지 유지됐다. 독립 반복·신뢰구간은 계산하지 않았다.

## 재생 검증의 출처
- 야간 시험100장 × ISP2의 RGB는 과거 실제 보드 프레임별 SHA256 기록과 모두 일치하는 Python 재생성 영상. 검증60장 × ISP2는 PC 생성 영상이며 보드 ISP에서 나온 영상으로 주장하지 않는다.
- 두 영상 집합320개를 새 모델2종으로 실제 보드 VART/DPU 실행해 총640레코드 회수·개수 및 중복 검사 완료.
- DPU-only 과정은 ISP/DFXC/guard에 접근하지 않음. final DFXC=0x7/GUARD=0x5, BOOT.BIN SHA256 2d2a045485568b847eddf7a39d6b235f046b6c78ea15997f332d2d59ab1dbb3a 불변 확인. 이전 ISP 출력 해시와의 연결을 확인했지만 새 live ISP 측정을 대체하지 않는다.
- COCO CPU NMS 병목 최적화: 같은 greedy 순서, per-class topk300, global max_det300을 유지한 pairwise-IoU 구현. 임의80조건 및 실제12출력에서 원래 NMS와 완전일치 검증. 완료된 보드 추론95개 SSD 및320개 YOLO를 보존하고 나머지를 이어 실행. 원본 run_detector.py 미수정.

## 저장 위치
- 원자료·점수·모델: /opt/data/work/blc16_dfx_board_20261014/common_dpu_pilot/
- 실험 스크립트: /opt/data/work/blc16_dfx_board_20261014/{isolate_detectors,pilot_models,pilot_run,pilot_detector,common_preprocess,board_pilot_live,fast_nms}.py
- laptop-linux: /home/mini/dfxisp_eval_20261007/common_dpu_pilot/
- 보드 신규 폴더: /home/root/exp/common_dpu_replay/
- live script 실행 및 결과 검증 완료. 사용자 콜드 부팅 후 root 셸·PCAP_PR=0 확인, 기존 BLC32 partial 두 개와 기존 static으로 측정했으며 기존 소스·모델·부팅 파일 교체 없음.
