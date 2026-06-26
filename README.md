# JNU Research DFX ISP

이 프로젝트는 **조명 환경에 따라 동작을 바꾸는 FPGA 기반 ISP(Image Signal Processor)** 를 연구합니다.  
핵심 아이디어는 **DFX(Dynamic Function eXchange, 부분 재구성)** 를 이용해, 낮은 조도에서는 저조도 전용 처리 로직을, 일반 조도에서는 일반 처리 로직을 선택적으로 사용하도록 만드는 것입니다.  
최종 목표는 단순히 "보기 좋은 영상"이 아니라, **후단 AI 객체검출 모델이 더 잘 인식할 수 있는 영상 전처리 파이프라인**을 만드는 것입니다.

## 🔍 한눈에 보기

- **연구 주제**: DFX 기반 적응형 ISP와 AI 객체검출 성능 향상
- **플랫폼**: Xilinx ZCU104, Vitis HLS, Vivado, Vitis AI
- **입력 데이터**: COCO, ExDark 기반 일반 조도 / 저조도 이미지
- **출력 목표**: 조도에 따라 적절히 처리된 RGB 이미지와 그에 대한 DPU 추론 성능 개선
- **현재 구조**: Python 골든모델 + HLS ISP 커널 + DFX 전환 로직 + CNN 평가 파이프라인

## 🎯 왜 이 연구를 하나

일반적인 ISP는 하나의 고정된 파이프라인으로 동작합니다. 하지만 실제 환경은 항상 같지 않습니다.  
밝은 실외, 어두운 실내, 야간 장면에서는 필요한 전처리 방식이 다르고, 고정 ISP는 이런 변화에 유연하게 대응하기 어렵습니다.

이 연구는 다음 질문에 답하려고 합니다.

1. **조도 변화에 따라 ISP를 바꾸면 객체검출 성능이 좋아지는가?**
2. **그 전환을 FPGA의 부분 재구성으로 구현할 수 있는가?**
3. **하드웨어 자원과 성능을 모두 고려했을 때 실용적인 구조인가?**

즉, 이 저장소는 "적응형 ISP를 설계하고", "그 효과를 AI 성능으로 검증하고", "실제로 FPGA에서 동작시키는" 연구 전체를 담고 있습니다.

## 🧭 연구가 다루는 시스템

전체 흐름은 아래처럼 보면 됩니다.

```text
입력 이미지
  -> 조도/조건에 맞는 ISP 처리
  -> 처리 결과를 AI 모델 입력으로 사용
  -> 객체검출 성능(mAP) 비교
```

하드웨어 관점에서는 다음 구조를 가집니다.

```text
Image
  -> Checker(밝기/상태 판단)
  -> PR/DFX로 모드 선택
  -> ISP Pipeline
  -> DPU / CNN Inference
  -> 성능 평가
```

현재 프로젝트는 이 과정을 두 트랙으로 병행합니다.

- **SW 트랙**: Python ISP 골든모델, 데이터셋 구축, CNN 학습/평가
- **HW 트랙**: HLS ISP 커널, PR 제어기, ZCU104용 DFX 구현

## 💡 핵심 아이디어

### 1. 🌗 적응형 ISP

고정된 하나의 ISP 대신, 장면 특성에 따라 다른 처리 방식을 사용합니다.

- **Normal 모드**: 일반 조도용 처리
- **Low-Light 모드**: 저조도용 처리

저조도 모드에서는 예를 들어 2x2 binning, gain, gamma 강화 같은 처리를 사용해 어두운 영역을 더 잘 살리고, 그 결과가 후단 AI 모델에 더 유리한지 평가합니다.

### 2. 🔄 DFX 기반 모드 전환

FPGA 전체를 다시 구성하는 대신, 일부 영역만 교체합니다.

- 조도 판단용 `checker`
- 부분 재구성 대상 모듈
- 고정 ISP 후처리 파이프라인

이렇게 하면 하드웨어 자원을 아끼면서도 환경 적응형 구조를 만들 수 있습니다.

### 3. 🤖 AI 성능 기준 평가

이 연구에서 ISP의 품질은 사람 눈 기준만으로 판단하지 않습니다.  
중요한 기준은 **객체검출 성능이 실제로 좋아졌는가** 입니다.

- ExDark: 저조도 데이터셋
- COCO: 일반 조도 데이터셋
- DynamicSwitch: 밝은 장면과 어두운 장면을 섞어 동적 전환 실험

## 🗂️ 프로젝트 구조

처음 보는 사람은 아래 디렉터리만 먼저 이해하면 됩니다.

```text
.
├── Dataset/                # 데이터셋, RAW 변환 결과, 데이터 준비 관련 자원
├── docs/                   # 연구 문서, 구조 설명, 분석 보고서
├── isppipeline/            # ISP 핵심 구현
│   ├── baseline/           # 기준 ISP
│   ├── proposal/           # 제안 ISP (checker, PR 포함)
│   ├── eval/               # 실험/평가 스크립트
│   └── unprocess/          # Python ISP 골든모델, raw 변환 관련 코드
├── model/                  # CNN 학습/평가 코드와 모델 자원
├── scripts/                # 데이터 준비, 학습/평가, 빌드 보조 스크립트
├── xmodel/                 # Vitis AI 컴파일 결과물 보관 위치
├── zcu104_platform/        # 보드 플랫폼 관련 파일
├── include/ ext/ lib/      # Vitis/Vision 관련 의존 헤더 및 라이브러리
└── meta/                   # 참조 메타데이터
```

## 📁 디렉터리별 상세 설명

### `Dataset/` 📦

실험에 사용하는 이미지와 RAW 변환 산출물이 모여 있습니다.

- `COCO_5000/`, `ExDark_5000/`: 일반 조도 / 저조도 평가용 데이터셋
- `COCO_5000_raw/`, `ExDark_5000_raw/`: sRGB 이미지를 pseudo-RAW Bayer 형태로 변환한 데이터
- `tmp/`: 임시 산출물

이 폴더는 코드 저장소이면서 동시에 실험용 데이터 구조를 설명하는 역할도 합니다.

### `isppipeline/` 🧪

이 저장소의 핵심입니다.

- `baseline/`: 비교 기준이 되는 ISP 구현
- `proposal/`: 연구의 핵심 제안 구조
  - `binning_gain.*`
  - `checker.*`
  - `pr_controller.*`
  - `isp_proposal.*`
- `eval/`: mAP 평가, 동적 전환 실험, 결과 비교 스크립트
- `unprocess/isp_pipeline.py`: Python 기준 ISP 골든모델

처음 코드를 읽을 때는 보통 아래 순서가 가장 이해하기 쉽습니다.

1. `isppipeline/unprocess/isp_pipeline.py`
2. `isppipeline/eval/run_experiment.py`
3. `isppipeline/proposal/`

### `model/` 🧠

객체검출 모델 관련 코드와 자원이 있습니다.

- MobileNet SSD 기반 학습/평가 코드
- TensorFlow SSD MobileNet 관련 자원
- Vitis AI 양자화/컴파일에 연결되는 모델 자산

즉, ISP 출력이 실제 AI 성능에 어떤 영향을 주는지 검증하는 축입니다.

### `scripts/` 🛠️

반복 작업을 줄이기 위한 보조 스크립트입니다.

- `dataset_prep/`: 데이터셋 준비 및 변환
- `run_train.sh`, `run_test.sh`, `run_quant.sh`, `run_compile.sh`: 실험 실행 보조

### `docs/` 📚

이 프로젝트를 이해할 때 가장 먼저 봐야 할 문서가 모여 있습니다.

- [docs/README.md](docs/README.md): 문서 읽기 순서와 reference/historical 구분
- [docs/C_SIM_QUICKSTART.md](docs/C_SIM_QUICKSTART.md): clone 후 C-Sim 실행 방법
- [docs/SCENARIO.md](docs/SCENARIO.md): 현재 조도 변화 시나리오 설명
- [docs/PONYTAIL_REVIEW.md](docs/PONYTAIL_REVIEW.md): Ponytail 관점 검수
- [Architecture.md](docs/Architecture.md): 전체 구조와 데이터 흐름
- [Research_Roadmap.md](docs/Research_Roadmap.md): 연구 목표, 단계, 진행 현황
- [Analysis_Report.md](docs/Analysis_Report.md): 실험 결과와 분석
- [HW_SW_Interface.md](docs/HW_SW_Interface.md): 하드웨어/소프트웨어 인터페이스

## 🔬 연구 흐름

이 저장소의 작업 흐름은 대략 아래와 같습니다.

### 1. 데이터셋 준비 📥

sRGB 이미지와 라벨을 정리하고, 필요하면 pseudo-RAW Bayer 데이터로 변환합니다.

관련 위치:

- `scripts/dataset_prep/`
- `isppipeline/unprocess/build_raw_dataset.py`

### 2. Python 골든모델 검증 🐍

하드웨어로 옮기기 전에, Python ISP 파이프라인으로 알고리즘을 먼저 검증합니다.

관련 위치:

- `isppipeline/unprocess/isp_pipeline.py`

### 3. HLS ISP 구현 ⚙️

검증된 알고리즘을 HLS 커널로 구현합니다.

관련 위치:

- `isppipeline/baseline/`
- `isppipeline/proposal/`

### 4. 동적 전환 검증 🔁

Checker가 장면을 판단하고, 필요한 경우 low-light 모드로 넘어가는 구조를 검증합니다.

관련 위치:

- `isppipeline/eval/simulate_dynamic_switch.py`
- `isppipeline/eval/run_dynamic.py`

### 5. AI 성능 평가 📈

각 ISP 조건에서 객체검출 성능(mAP)을 비교합니다.

관련 위치:

- `isppipeline/eval/run_experiment.py`
- `isppipeline/eval/eval_core.py`
- `isppipeline/eval/eval_map.py`

### 6. FPGA / DPU 통합 🧩

ZCU104 환경에서 HLS, DFX, DPU를 통합해 보드 실증으로 이어집니다.

관련 위치:

- `zcu104_platform/`
- `xmodel/`

## 🚀 처음 보는 사람을 위한 추천 읽기 순서

### 연구 개요부터 파악하고 싶다면 📝

1. 이 `README.md`
2. [docs/Research_Roadmap.md](docs/Research_Roadmap.md)
3. [docs/Architecture.md](docs/Architecture.md)

### 코드부터 보고 싶다면 💻

1. [isppipeline/unprocess/isp_pipeline.py](isppipeline/unprocess/isp_pipeline.py)
2. [isppipeline/eval/run_experiment.py](isppipeline/eval/run_experiment.py)
3. [isppipeline/proposal/README.md](isppipeline/proposal/README.md)
4. `isppipeline/proposal/*.cpp`, `*.hpp`

### 하드웨어 구조를 보고 싶다면 🔌

1. [docs/HW_SW_Interface.md](docs/HW_SW_Interface.md)
2. `zcu104_platform/`
3. `isppipeline/proposal/pr_controller.*`

## 📌 현재 상태

이 저장소는 단순 예제가 아니라, **진행 중인 연구 저장소**입니다.  
따라서 아래 내용이 함께 섞여 있습니다.

- 논문/실험 설계용 문서
- Python 기준 모델
- HLS 하드웨어 구현
- 데이터셋 준비 코드
- CNN 학습 및 평가 코드
- 보드 통합 자원

즉, 이 프로젝트는 "하나의 ISP 코드"가 아니라 **연구 전체 실험 환경**입니다.

## 🧱 참고 기술

- **Vitis Vision Library**: ISP 관련 HLS 함수 레퍼런스
- **Vitis AI**: DPU, 양자화, `.xmodel` 생성
- **Vivado / Vitis HLS**: 하드웨어 합성 및 플랫폼 통합
- **COCO / ExDark**: 일반 조도 / 저조도 평가 데이터셋

## 📝 문서 관리 원칙

구조, 실험 흐름, 인터페이스가 바뀌면 `docs/` 문서도 함께 갱신해야 합니다.  
특히 아래 문서는 항상 최신 상태를 유지하는 것이 중요합니다.

- [docs/Architecture.md](docs/Architecture.md)
- [docs/Research_Roadmap.md](docs/Research_Roadmap.md)
- [docs/Analysis_Report.md](docs/Analysis_Report.md)
- [docs/HW_SW_Interface.md](docs/HW_SW_Interface.md)
