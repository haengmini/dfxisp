# DFXISP 확대 검증 및 절대성능 개선 실험안

## 최신 상태: 보드 실측 및 추가 통계 검증 반영
이 절은 아래의 최초 계획·중간 기록보다 우선한다. 상세 근거는 [보드 재생 및 DFX live 기록](2026-10-14-v2-balanced-model-board-replay.md)에 있다.

YOLOv8n은 균형학습 3시드, FP32, 호스트 INT8, 보드 재생, DFX live를 완료했다. 보드 재생은 호스트와 400/400 검출 일치. 야간 Lowlight 고정에서 기존 약 0.276 대비 새 모델 0.402~0.414, DFX live에서도 약 0.402~0.414였다. 주간은 시드별 퇴행이 남아 전체 성능 개선이나 비열등 통과로 판정하지 않는다.

SSD-MobileNet도 균형학습 3시드와 보드 DFX live를 완료했다. 보드와 호스트의 큰 불일치를 SE hard-sigmoid 경로로 좁혔고, 두 fc2 출력의 고정소수점 위치를 11에서 8로 제한한 별도 수정본을 검증했다. 진단 2장의 최종 정수 출력은 100% 일치했지만 400장 검출 일치는 393~397/400으로 잔여 불일치가 있다. 원본 배포 xmodel은 보존했다. 같은 v2 학습 보정으로 재양자화한 기존 가중치 수정본과 새 수정본끼리 비교하면 야간 Lowlight mAP50-95는 0.2012 대비 0.2476~0.2487, 혼합 Adaptive는 0.3014 대비 0.3324~0.3346이다. 주간 Normal은 0.6035 대비 0.5811~0.5881로 낮다. CI가 0을 포함한다는 이유로 동등·비열등이라고 부르지 않는다.

SSD DFX live 600프레임이 완료됐고 보드 RGB 해시는 모두 기준과 일치했다. 새 모델 야간 live는 0.2478/0.2486/0.2482였다. 보드 종료 상태는 마지막 실측 기준 DFXC 0x107 / GUARD 0x45이며 이후 ISP·DFX 실측에는 새 콜드 부팅과 ICAP 선택이 필요하다. 현재 상태를 새로 읽은 값은 아니다.

추가 부트스트랩은 YOLO 4모델·SSD 5모델 × 주간/혼합/혼합 블록 27구성, 프레임 재표집 1,000회 완료. SSD 혼합 블록에서 더 좋은 고정 RM 대비 DFX 차이는 +0.0018~+0.0045이나 모든 CI가 0을 포함한다. YOLO도 더 좋은 고정 RM 대비 우위가 확인되지 않았다. YOLO 혼합은 Normal 고정보다 세 시드 모두 높은 CI지만 Lowlight 고정 대비는 아니다. DFX의 정확도 우위를 일반화하지 않는다. 시간·장면 군집을 보존한 블록 부트스트랩이나 다중 비교 보정은 수행하지 않았다.

### 남은 게이트
1. 새 장면 holdout 확보 및 독립성 감사. 기존 시험은 회고적 benchmark로 유지한다.
2. SSD 잔여 검출 불일치 3~7장의 원인 분리. 완전한 400/400 일치라고 보고하지 않는다.
3. 주간 비열등 허용폭과 장면 단위 평가 계약을 독립 시험 전에 고정한다. 현재 비열등 통과 주장은 보류한다.
4. 클래스·객체 크기·밝기별 분석, YOLO 시드별 주간 손실 및 SSD 수렴 문제는 개발 자료에서만 진단한다. 새 holdout 점수로 모델·ISP·정책을 고르지 않는다.

### holdout 후보 메타데이터 감사
로컬 Sony 라벨 3,213개 ID에서 기존 train359/val60/test100과 신규 선택 1,200개 전체(학습에서 제외된 ID도 보수적으로 포함)를 제외했다. 제외 ID는 1,719개, 미사용 ID는 1,494개다. 그러나 사용 ID와 번호 거리가 3을 넘는 것은 15개뿐이며 20을 넘는 것은 0개다. 번호 거리는 장면 독립성의 증명이 아니므로 이 1,494개를 새 장면 holdout으로 선언하지 않는다. 촬영 세션·장소 정보, RAW 해시·지각 중복, 원래 프로젝트 모델 학습 이력을 확인해야 한다. 주간 replay JPG도 독립 주간 RAW를 대체하지 않는다.

감사 산출물: `/opt/data/work/blc16_dfx_board_20261014/expanded_scope_audit/holdout_candidate_inventory.json` 및 `audit_holdout_candidates.py`. 구성 계약은 [새 장면 holdout 계획](2026-10-16-scene-holdout-contract.md) 참조.

## 목적 및 현재 상태
사용자 요청: 기존 실험 환경·결과와 유사하거나 더 나은 결과를 얻을 방안 모색. 최초 작성 시점에는 기존 원자료 재분석·환경/분할 감사·실행안 작성만 수행했고 새 대규모 학습이나 보드 실험은 하지 않았다. 최종 가설: 낮은 절대성능 COCO 파일럿 확대가 아니라 기존 프로젝트 검출모델의 분포 적응·활성화·기하변환 계약을 먼저 개선한다. 개선 성능을 보장하지 않는다.

## 확인된 근거
- 채택 SW: 주간100/야간100/혼합200, COCO 공식YOLO/SSD, BLC32, 원본해상도→shift8→JPEG95, pycocotools. 목표 경향은 주간Normal, 야간Lowlight, 혼합Adaptive 우세. 보드의 1368×912 RAW12/직접RGB/3클래스INT8과 절대 AP는 직접 비교 불가.
- 최신 프로젝트 DFX BLC16: YOLO day/night/mixed .6502/.2761/.3672, SSD .4520/.1732/.2346. 기존 Normal 야간 .2696/.1892. 이는 보드 eval_map 채점 기준.
- COCO 공통 live 파일럿 야간YOLO N/L .06045/.08611, SSD .07664/.09440. 경향 확인에는 유효하나 교체안 아님.
- 기존 exp3 파인튜닝은 이미 완료된 실험. ft_results.csv 180행 회수해 summarize_ft.py 실행, 24요약행 생성 및 그룹별3시드 확인. Hardswish base Lowlight day/night/mixed .6263/.1889/.3015; ft_lowlight3시드평균 .3941/.2669/.2846. 야간 개선과 심한 주간 회귀가 함께 발생. 이 수치는 해당 pycocotools 하네스이며 보드AP와 동일하지 않음.
- exp3.py는 SiLU 학습 후 exp3_eval.py에서 Hardswish 교체. 새 모델은 지원 활성화를 학습 전에 지정하고 학습 전후 구조를 검증해야 함.
- 기존 exp3 학습 Ultralytics 데이터변환/검증은 보드 RD stretch와 같은 계약이 아님. 설치된 YOLODataset.build_transforms는 검증에 LetterBox 사용. imgsz640만 같다고 기하변환 동일이라 주장하지 않음.
- ft_hw train359/val60과 기존 시험(day100/night100) ID 교집합 모두0. 장면/근접촬영 그룹 또는 perceptual중복은 미검증. 기존 test는 이미 많은 후보에서 반복 평가되어 회고적 benchmark로 간주.
- laptop RTX5060 8GB, GPU memory15MiB 사용, /home/mini 39GB가용(96%사용) 확인. 보드는 지난실험후 약423MB가용이므로 새대규모RGB패키지는 피하고 RAW재사용/분할전송/결과jsonl만 회수. 자동삭제 없음.
- 실제 HW RAW train/val은 야간 분할만 확인. 균형학습용 주간 train/val 원본·라벨은 조사위치에서 확보 확인 못함. 기존 PASCAL_test100장을 새 학습으로 재사용하면 안 됨.

## 목표를 두 트랙으로 분리
A. 원 실험 재현: 원본 SW입력·공식검출기·기존scorer 그대로 재현하고 동일 모델에 board형 RAW/무손실RGB/명시전처리를 적용한 bridge 실험. 원본크기와 보드크기 효과·JPEG 효과·scorer 효과를 따로 기록. 같은 백분율이 나오게 조건을 고르는 실험 금지.
B. 실제 성능 개선: 프로젝트 모델+기존보드계약을 기준으로 절대 AP/주간회귀/야간개선/혼합DFX 이득 동시 확인. 모든 후보와 기준선은 같은 입력과 같은 전후처리로 재평가. 공통 전처리 변경 시 옛점수와 직접 비교하지 않고 기준선도 다시 측정.

## 단계1: 확대 평가 하네스(새 학습 전)
- 조건: Normal/BLC32/BLC16, 동일 검출 모델 하나를 ISP3종에 공통사용. 기존프로젝트모델2종과 COCO파일럿은 별도군. ISP별 다른 모델은 별도 시스템 실험으로만 취급.
- 데이터: 기존 day100/night100, mixed200 셔플과 mixed_blocks 동일프레임 순서변화. mixed200은 새200장 아님; 고유시험프레임은200.
- 채점: 보드eval_map primary, 동일검출에 pycocotools secondary. IoU범위/maxDets/class mapping/박스clipping/빈클래스처리 차이를 명시, AP차이를 model차이로 잘못 해석하지 않음.
- 지표: 전체/클래스별 AP50-95·AP50, Recall, 작은객체 및 brightness구간, 검출입력좌표 기준 객체크기, 포화율, checker오선택, ISP와 DPU 및 전후처리 지연 분리.
- 알려진 COCO소객체기준을 단순 출력해상도에 적용하면 binning에 따라 층이 바뀜. 공통 detector입력좌표 또는 원본정규화면적에서 구간을 사전 고정.
- 테스트 확대: 가용 미사용 장면을 확보하고 장면/촬영그룹 기준 holdout. frame ID뿐 아니라 RAW해시·근접/지각중복 확인. 기존train359/val60의 새분할은 개발검증이며 자동으로 독립시험이 되지 않음.

## 단계2: 절대성능 후보(우선순위)
1. 기존 프로젝트 weight 기반 공통 단일모델, Hardswish를 학습 전에 적용. Normal/Lowlight16 + day/night 균형 sampling. 원프레임그룹 먼저 split하고 ISP파생영상은 같은 split에 묶음. 중복ISP팔로 데이터양이 늘어난 효과를 막기 위해 원프레임별 총학습빈도와 optimizer step 수를 대조군과 같게 함.
2. 위 조건에 사전 제한된 backbone freeze/낮은learning rate를 적용, 기존 지식을 유지하는 대조후보. 검증에서 효과없으면 중지. 후보마다 seed0/1/2, 동일초기가중치·학습예산·검증규칙. 기존야간전용exp3 단순재실행은 제외.
3. 필요시 SiLU teacher→Hardswish student distillation. 높은SiLU성능이 실제개발검증에서 확인되고 직접학습이 불충분할 때만 추가. COCO3클래스 head 재학습도 후순위; 무학습채널삭제는 금지.
4. SSD도 동일 train split·정규화·anchor/decode 계약으로 균형미세조정. YOLO결과를 SSD성과로 전용하지 않음.
- 기하변환은 기존board stretch 유지후보를 우선해 학습도 같은변환/박스변환으로 구성. LetterBox는 학습·검증·보드 역좌표변환까지 묶인 별도 ablation. 시험AP로 resize를 선택하지 않음.
- 첫 화면/소량1epoch smoke: 지원활성화수, class 순서, 실제resize pixel parity, label box변환, raw head shape, inspector/compile확인. 설치Ultralytics 최신학습과VAI3.5/vendor8.3 export 호환이 확인돼야 장기학습 진행.

## 단계3: 양자화 손실 분리
- FP32가 절대성능/주간회귀 기준을 통과한 후보만 PTQ.
- calibration은 day/night와 Normal/Lowlight16, 저조도/하이라이트 및 클래스 대표성을 확보한 train 전용. 샘플수는 가용자료 내 사전선언된 단계로 확대하되 test/val은 제외. 현재야간32프레임 파일럿은 주간보정대표성 근거가 없음.
- hostINT8 vs FP32, compiledDPU vs hostINT8를 동일영상에서 확인. AP뿐 아니라 raw-head numerical편차도 기록.
- FP32는 좋은데 INT8손실이 남을 때만 QAT. FP32부족을 QAT가 해결한다고 가정하지 않음.
- VAI3.5 Model Inspector/compile과기존 DPUfingerprint 확인, static/BOOT변경없음. 지원안되는연산은 graph분할상태 보고.

## 단계4: DFX 선택 정책(마지막 최적화)
- checker C1 및현재 threshold 대조유지. 개발검증에서 brightness/포화/scene그룹별오선택을 보고 threshold/hysteresis 제한탐색.
- global AP는 개별프레임AP평균이 아니므로 프레임별GT oracle AP 선택을 배포정책으로 주장하지 않음. test GT로 threshold를 선정하지 않음.
- 하나의 검출모델을 Normal/Lowlight에 공통사용하여 ISP기여를 분리. RM별 detector2개는 로딩시간/메모리/기여혼동 때문에 나중에 별도System 실험.

## 단계5: 보드 최종 평가
- PTQ/replay gate 통과후 새콜드부팅 + PCAP_PR=0 + freshguard, raw→ISP pixel gate→DPU. 기존fixedNormal/fixedLowlight32/fixedLowlight16 및DFX16, day/night/mixed/mixed_blocks 비교.
- 기존동일입력재평가는paired bootstrap, 충분한 반복수 사전선언. 서로다른 장면새holdout은 장면단위 bootstrap. 독립보드반복은 장면표본불확실성과 다른개념으로 따로 보고.
- mAP50-95 primary. '개선'은 동일조건paired차이CI가0을넘는지를확인. '유사'는 사전에 합의한 절대 AP 비열등허용폭이 필요하며 CI가0을포함한다는이유만으로 동등이라주장하지 않음. 주간·야간·혼합의다중비교및선택편향기록. 전체성능유지와Lowlight우세를 별도판정.
- 최소목표: 새후보가 기존BLC16 DFX와고정Normal 기준에 비열등한주간·혼합, 야간정확도향상. 목표값을통과해도 새holdout/seed재현없으면최종채택보류.

## 게이트와 즉시 실행 가능한 순서
1. 기존결과/모델/RGB 재사용해 두 scorer와조건별분해보고서 구축(장기학습전).
2. 주간train/val 확보와새holdout분리확인. 못확보하면 균형학습및주간유지성과주장보류.
3. train geometry·activation·export smoke, 공통모델균형학습후보2개, 검증고정.
4. FP32선별→대표PTQ→필요시QAT→보드재생→최종liveDFX.
5. BLC/WB/Gain/CCM 추가탐색은 위모델/분할기준고정후 검증에만 수행. 후보별RM빌드는소수에한정, lockedstatic pr_verify 및대조bit-identical원칙.

## 산출물
/opt/data/work/blc16_dfx_board_20261014/expanded_scope_audit/{ft_results.csv,ft_bootstrap.csv,summarize_ft.py,ft_summary.json}
검증실행: python3 summarize_ft.py → 180source/24summary/3seed그룹확인PASS.

## 참고
AMD Vitis AI 3.5 Developing a Model: https://xilinx.github.io/Vitis-AI/3.5/html/docs/workflow-model-development.html
ModelInspector 지원연산/순서 및정확한 arch.json 필요. 실제우리지원범위는검사/컴파일결과로최종확인한다.

---

## 2026-10-14 진행 기록: 1~2단계 중간 결과
(작성 중 파일을 실수로 덮어써 위 본문을 원문대로 복구한 뒤 이 기록을 추가함.)

### 1단계 세부 재채점 완료
- 기존 v5·BLC16 DFX 28개 실행 결과에 대해 보드 scorer와 pycocotools를 같은 검출 결과로 재채점: 224 점수행. 보드 scorer 값은 기존 보고 수치와 일치하고 pycocotools 값과는 최대 약 0.003 차이.
- BLC16 DFX YOLO 야간 클래스별 AP50-95(v5→BLC16): person .167→.210, car .207→.334, bicycle .191→.285. 혼합: .253→.280, .387→.458, .295→.363. SSD는 야간 car .152→.160, bicycle .186→.211, person 변화 없음.
- 야간 YOLO APsmall .025→.034, AR100 .274→.344. 소표본 100/200프레임이며 클래스별 CI는 계산하지 않았다.
- 산출물: expanded_scope_audit/rescore/{rescore.csv,coverage.json,DONE.json}, rescore_baselines.py.

### 2단계 진행 (사용자 승인 후)
- Stanford 1번 조각만 받아(10.7GB, 크기 일치) 주간 600×400 JPG·XML 4,259쌍 확인. NEF 원본은 이 조각에 없고 JPG는 축소본이라 **ISP 학습용 주간 RAW가 아니라 기억 유지(replay)용**으로만 사용.
- Drive 읽기 전용: Sony ARW 4,043장, COCO 라벨 3,213장(공식 train 2,571/val 321/test 321). 기존 사용 519장과 시험 ±3프레임을 제외한 후보 2,277장에서 seed 20261014로 1,200장 선택, 서버에서 변환 완료(1368×912 12bit, 라벨 4,871/848/1,640, 시험·기존 학습과 겹침 0).
- 변환 동일성 게이트: 기존 학습 3장을 Drive에서 다시 변환해 BIN·라벨이 **바이트 단위 일치**.
- 누수 감사(픽셀 상관 기반): 시험 100장의 최근접 기존 학습 상관 중앙값 0.48, 0.9 이상 0건. 시험과 번호가 3 이내인 쌍도 상관이 높지 않아(중앙 0.16) 번호 근접이 곧 같은 장면은 아님. 다만 이전 학습 419장 중 417장은 시험과 같은 연속 촬영 군집(번호차 ≤3 연쇄)에 속함 → 군집 분리는 번호 규칙이 아니라 블록 분할+±3 제거로 처리.
- 주간 replay: PASCALRAW 600×400 JPG 중 시험 ±3 제외 1,100장(학습 899/검증 201, 라벨 1,693박스) 노트북에 준비.
- 학습 스크립트 smoke: Hardswish를 학습 전에 적용해 trainer 재구성 후에도 57개 Conv 활성화가 Hardswish로 유지됨(SiLU 0) 확인.
- 평가 하네스 기준선(보드 계약, 같은 모델을 두 ISP에 공통): 기존 프로젝트 Hardswish FP32, BLC16 Lowlight — 야간 Normal .2699/Lowlight .2651/Adaptive .2642, 주간 .6200/.6179/.6386, 혼합 .3563/.3536/.3563. (PC FP32, 보드 INT8 수치와 직접 비교 불가)

### 3단계 균형 학습 시드0 결과 (FP32, PC, 보드 계약 평가)
데이터: 야간 학습 1,335원본(기존 359+신규 976)×(Normal+Lowlight BLC16) + 주간 replay 899 / 검증은 신규 야간 260·주간 201. 모델 1개를 두 ISP에 공통 사용, Hardswish를 학습 전에 적용, 640 stretch 사전 적용, SGD lr0 .002, 30epoch, 마지막 가중치만 평가.
mAP50-95 (시험: 야간100·주간100·혼합200, 시험 프레임은 학습·검증·보정에 쓰지 않음)
| 구성 | 기준(기존 모델) | A_full | B_freeze10 |
|---|---:|---:|---:|
| 야간 Normal / Lowlight | .2699 / .2651 | .4141 / .4185 | .3579 / .3585 |
| 주간 Normal / Lowlight | .6200 / .6179 | .6696 / .6646 | .6879 / .6756 |
| 혼합 Normal / Lowlight | .3563 / .3536 | .4772 / .4822 | .4420 / .4411 |
- A_full을 개발 검증(야간 신규 val .4535/.4635, 주간 .8072)으로 선택. 시험 점수로 선택하지 않음(B도 같은 시험 점수를 보고).
- 주의: 공통 모델이 학습한 뒤 Normal과 Lowlight의 야간 격차는 +.004로 거의 사라짐(기존 기준에서는 Lowlight가 야간에 불리). 이 개선의 대부분은 모델/데이터 효과이며 ISP 효과가 아님.
- 아직 단일 시드, 신뢰구간 미계산, PC FP32. 양자화·보드 미검증.

### 2단계 데이터 확보 blocker (승인 전 상태)
- laptop 확인 범위에서 시험과 분리된 주간 원본 RAW·라벨 학습자료 없음. Downloads/dataset.zip, fpage_ai.zip, ai_train.zip, repo dataset 모두 기존 test 100/100 또는 코드만 있고 PASCAL_train은 없음. ft_hw 419장은 야간 전처리 BIN.
- 공유 Drive 폴더는 LOD_test, PASCAL_test와 *_hw 압축만 확인. 공개 원본 PASCALRAW는 Stanford 14개 tar.gz 조각(약 150GB). laptop 여유 약39GB라 전체 보관 불가. 외부 대용량 다운로드와 스트리밍 일부 추출은 사용자 승인 필요.
- 기존 prepare_pascal_yolo.py는 test를 val로 재사용하므로 그대로 사용하지 않는다.
