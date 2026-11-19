# DFXISP

어두운 곳에서도 물체를 잘 찾는 카메라 영상 처리 연구입니다. 장면이 밝은지 어두운지 판단기(checker)가 보고, FPGA 위에서 일반 ISP와 저조도 ISP를 실제로 바꿔 끼운(DFX, 동적 부분 재구성) 뒤, 그 영상에서 검출 AI가 사람, 자동차, 자전거를 찾습니다. ZCU104 보드에서 실험했습니다.

이 저장소는 연구의 **안내판**입니다. 연구를 직접 따라 해 보려면 아래 튜토리얼로 가세요.

## 연구를 따라 하려면

**[DFXISP-Tutorials](https://github.com/haengmini/DFXISP-Tutorials)** 에서 시작하세요. ISP, HLS, DFX, 데이터셋, PetaLinux, 처음부터 끝까지의 흐름을 단계별로 안내하며, 각 단계에 기대 결과와 확인한 환경을 적었습니다. MIT 라이선스입니다.

| 하고 싶은 것 | 바로 가기 |
|---|---|
| 보드 없이 PC에서 ISP 계산 확인 | [ISP 튜토리얼](https://github.com/haengmini/DFXISP-Tutorials/tree/main/ISP_Feature_Tutorials/01-default_ISP_and_lowlight_ISP) |
| 회로(HLS) 합성과 C 시뮬레이션 | [HLS 튜토리얼](https://github.com/haengmini/DFXISP-Tutorials/tree/main/HLS_Feature_Tutorials/01-RM_synthesis_and_csim) |
| 두 ISP를 바꿔 끼우는 DFX 구현 | [DFX 튜토리얼](https://github.com/haengmini/DFXISP-Tutorials/tree/main/DFX_Feature_Tutorials/01-Fabric_only_DFX_flow) |
| 처음부터 끝까지 | [Design 튜토리얼](https://github.com/haengmini/DFXISP-Tutorials/tree/main/Design_Tutorials/01-DFXISP_End_to_End) |

## 선행 저장소

| 저장소 | 내용 |
|---|---|
| [JNU_Lab_Petalinux](https://github.com/haengmini/JNU_Lab_Petalinux) | ZCU104에서 PetaLinux와 HLS 가속기를 쓰는 기본 흐름 |
| [JNU_DFXISP_FPGA](https://github.com/haengmini/JNU_DFXISP_FPGA) | HLS 회로 소스, Vivado DFX 흐름, 실제 RAW 샘플 |
| [JNU_DFXISP_AI](https://github.com/haengmini/JNU_DFXISP_AI) | 물체 검출 모델 가중치, 데이터셋 안내 |
| [JNU_DFXISP_ISP](https://github.com/haengmini/JNU_DFXISP_ISP) | ISP만 PC에서 실험 |

## 결과를 읽을 때 알아 둘 점

- 야간 정확도(mAP50-95)는 YOLOv8n 기준 0.28에서 0.41로 올랐습니다. 이 개선의 대부분은 **낮과 밤 사진을 함께 학습한 AI 모델** 덕분이며, 회로를 바꿔 끼우는 방식 자체가 정확도를 높였다는 근거는 없습니다.
- DFX로 확인한 것은 정확도가 아니라 **자원 절감**입니다. 항상 두 ISP를 모두 올려 두는 방식 대비 LUT를 normal 모드에서 29.5%, low-light 모드에서 50.8% 줄였습니다.
- 시험 사진은 이전 실험에서 쓴 것을 다시 썼습니다. 새로운 장면으로 검증하지 않았습니다.
- 사진을 한 장씩 차례로 처리했습니다. 영상이 실시간으로 들어올 때 프레임을 놓치는지, 전력이 얼마나 드는지는 측정하지 않았습니다.

## 이 저장소의 상태

연구의 설계 근거, 실험 기록, 보드 작업 원본은 비공개로 보관하고 있습니다. 공개용 내용은 위 튜토리얼과 선행 저장소에 정리되어 있습니다.
