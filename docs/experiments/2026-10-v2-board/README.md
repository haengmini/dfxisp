# 2026-10 v2 보드 실험 (균형학습 YOLOv8n / SSD-MobileNet, ZCU104)

LowlightISP 개선 방안을 보드에서 확인한 실험의 결과, 근거 자료, 재현 스크립트 모음이다. 모델 파일(xmodel)과 대용량 원자료는 포함하지 않으며 모델 해시는 `notes/2026-10-14-v2-balanced-model-board-replay.md`와 `results/ssd/fix/` 분석 로그에 있다.

## 한 줄 요약
- 주야간 균형학습으로 야간 정확도가 두 검출기 모두 올랐다(보드 mAP50-95, DFX live, 3시드 평균).
  - YOLOv8n 야간 0.2751 → 0.4097, 혼합 0.3653 → 0.4636, 주간 0.6502 → 0.6314
  - SSD-MobileNet 야간 0.2013 → 0.2482, 혼합 0.3039 → 0.3304, 주간 0.5977 → 0.5828
- 주간 평균은 낮아졌고 비열등은 입증하지 못했다.
- DFX 자동 전환이 최선의 고정 ISP보다 정확하다는 근거는 없다(27개 구성 부트스트랩, 최선 고정 방식 대비 차이의 신뢰구간이 모두 0을 포함한다).
- SSD의 보드 대 호스트 INT8 불일치는 SE 블록의 hard-sigmoid 직전 고정소수점 위치(11)에서 시작했다. 두 fc2 출력 위치를 8로 제한하면 진단 이미지의 최종 정수 출력이 100% 일치한다. 400장 전체 검출 일치는 393~397장이다.

## 구성
| 경로 | 내용 |
|---|---|
| `notes/` | 정본 실험 기록, 확대 검증 계획, holdout 계약 |
| `results/final_live_comparison/` | YOLO와 SSD의 고정 ISP 및 실제 DFX live 최종 비교표(CSV, Markdown)와 그래프(PNG, PDF, SVG) |
| `results/figures/` | 단계별 그래프 |
| `results/ssd/` | SSD 수정(SE), 이분 탐색, DFX live 분석 JSON과 로그 |
| `results/yolo_dfx_live/` | YOLO DFX live 분석 JSON |
| `results/dfx_extra_bootstrap.*` | 주간, 혼합, 혼합 블록 27개 구성 부트스트랩 |
| `scripts/` | 보드 실행, 분석, 감사, 그래프 스크립트 |

## 한계
- 시험 프레임을 재사용했다. 새 장면 holdout은 아직 없다(`notes/2026-10-16-scene-holdout-contract.md`).
- 시드 3개는 같은 학습 절차의 반복이고 표준편차는 시드 변동이다.
- 부트스트랩은 프레임 단위 재표집이며 시간, 장면 군집과 다중 비교 보정을 반영하지 않는다.
- 보드는 프레임을 순차 처리했다. 처리량, 프레임 드롭, 프레임당 에너지는 평가하지 않았다.
- SSD 기준선은 기존 가중치를 재보정하고 SE를 수정한 모델이라 원래 배포 모델과 다르다.

## 하드웨어 변경 (별도 커밋)
LowlightISP의 블랙 레벨 보정(BLC_LEVEL12)을 32에서 16으로 바꾼 7개 파일은 이 문서 묶음과 분리된 커밋에 있다.
