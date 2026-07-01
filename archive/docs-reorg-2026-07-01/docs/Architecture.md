# Architecture

이 문서는 현재 저장소 기준으로 연구 구조, 데이터 흐름, 디렉터리 역할을 정리한 최신 아키텍처 문서입니다.

이 프로젝트는 하나의 단일 프로그램이 아니라, 아래 세 축이 연결된 연구 저장소입니다.

1. pseudo-RAW 데이터셋 구축
2. Python ISP 골든모델 및 평가 파이프라인
3. FPGA DFX 기반 적응형 ISP 하드웨어 구현

---

## 1. 연구 전체 구조

프로젝트는 SW 트랙과 HW 트랙이 병렬로 진행된 뒤, 골든 벡터와 보드 통합 단계에서 합류하는 구조입니다.

```text
SW 트랙
  sRGB 데이터셋
    -> pseudo-RAW 변환
    -> Python ISP 골든모델
    -> CNN 학습 / mAP 평가
    -> RGB32 기준 정답 벡터 생성

HW 트랙
  HLS ISP 커널
    -> C-Sim / Co-Sim
    -> RTL / DFX 통합
    -> 보드 실행

합류 지점
  Python 골든모델과 HW 출력의 RGB32 비트대조
  + DPU / CNN 성능 평가
```

---

## 2. 현재 기준 핵심 데이터 흐름

현재 메인라인 알고리즘은 RGB32 중심으로 정리되어 있습니다.

```text
sRGB image
  -> unprocess()
  -> pseudo-RAW Bayer (16-bit PNG)
  -> ISP 처리
     - baseline: 고정 파이프라인
     - proposal: checker + 모드별 처리
  -> RGB32 output
  -> CNN inference / mAP evaluation
```

저장소 안에서 실제로는 두 가지 입력 경로를 함께 다룹니다.

1. sRGB 이미지를 직접 처리하는 Python 평가 경로
2. sRGB를 pseudo-RAW Bayer로 역변환한 뒤 ISP를 거치는 연구 경로

---

## 3. 현재 ISP 개념 구조

### 3.1 Baseline ISP

`isppipeline/baseline/`는 비교 기준이 되는 고정 ISP 파이프라인입니다.

주요 처리 단계:

1. Bayer16 -> Bayer8 축소
2. Black level correction
3. Gain control
4. Demosaicing
5. Color correction matrix
6. Gamma correction
7. RGB 출력

### 3.2 Proposal ISP

`isppipeline/proposal/`는 본 연구의 핵심 제안 구조입니다.

구성 요소:

1. `checker`
   - 입력 영상의 휘도를 바탕으로 장면 상태를 판단
2. `binning_gain`
   - 저조도 모드에서 2x2 binning + gain 수행
3. `pr_controller`
   - 모드 전환 및 부분 재구성 제어
4. `isp_proposal`
   - 고정 ISP + 모드별 처리 결합

현재 개념 흐름은 아래와 같습니다.

```text
input image
  -> checker
  -> mode selection
     - normal
     - low-light
  -> ISP pipeline
  -> RGB32 output
```

---

## 4. 디렉터리 역할

### 4.1 최상위 디렉터리

| 경로 | 역할 |
|------|------|
| `Dataset/` | 실험용 이미지, 라벨, pseudo-RAW 데이터 |
| `docs/` | 연구 문서, 분석 보고서, 인터페이스 명세 |
| `isppipeline/` | ISP 알고리즘과 HLS 구현 |
| `model/` | 객체검출 모델 학습/평가 코드 및 모델 자산 |
| `scripts/` | 데이터 준비, 학습, 평가, 빌드 보조 스크립트 |
| `xmodel/` | Vitis AI 컴파일 결과물 보관 |
| `zcu104_platform/` | 보드/플랫폼 관련 자산 |
| `include/`, `ext/`, `lib/` | Vitis Vision 및 관련 의존 자산 |
| `meta/` | 참조 메타데이터 |

### 4.2 `Dataset/`

| 경로 | 역할 |
|------|------|
| `Dataset/COCO_5000/` | 일반 조도 평가 데이터셋 |
| `Dataset/ExDark_5000/` | 저조도 평가 데이터셋 |
| `Dataset/COCO_5000_raw/` | COCO pseudo-RAW Bayer 데이터셋 |
| `Dataset/ExDark_5000_raw/` | ExDark pseudo-RAW Bayer 데이터셋 |
| `Dataset/tmp/` | 임시 산출물 |

### 4.3 `isppipeline/`

| 경로 | 역할 |
|------|------|
| `isppipeline/unprocess/` | Python ISP 골든모델 및 raw 변환 로직 |
| `isppipeline/eval/` | 정적 평가, 동적 전환 평가, mAP 계산 |
| `isppipeline/baseline/` | 기준 ISP HLS 구현 |
| `isppipeline/proposal/` | 제안 ISP HLS 구현 |
| `isppipeline/_ref/` | 레거시 DFX / grayscale 기준 참조 코드 보관 |

---

## 5. 코드 탐색 권장 순서

처음 구조를 파악할 때는 아래 순서가 가장 효율적입니다.

1. `isppipeline/unprocess/isp_pipeline.py`
2. `isppipeline/eval/run_experiment.py`
3. `isppipeline/eval/run_dynamic.py`
4. `isppipeline/proposal/README.md`
5. `isppipeline/proposal/*.cpp`
6. `model/mobilenet_ssd/code/train.py`

---

## 6. 현재 상태 해석

현재 저장소는 다음이 혼재된 연구 저장소입니다.

1. 현재 사용 중인 RGB32 기반 메인라인 코드
2. 보드/DFX 통합에 사용되던 과거 grayscale/YUYV 기준 참조 자료
3. 최신 Python 골든모델 및 CNN 평가 실험 결과

따라서 문서를 읽을 때는 다음 기준을 적용해야 합니다.

- `README.md`, `docs/Architecture.md`, `docs/Research_Roadmap.md`, `docs/TODO.md`는 현재 기준 문서
- `docs/reference/`와 `isppipeline/_ref/`는 역사적 참조 문서/코드
- 보드 통합 상세는 최신 RGB32 방향과 과거 DFX 구현 기록을 함께 비교해서 해석해야 함

---

## 7. 문서 유지 원칙

아래 항목이 바뀌면 이 문서도 같이 갱신해야 합니다.

1. 핵심 디렉터리 구조
2. 데이터 흐름
3. RGB32 / Bayer / DMA 인터페이스 기준
4. baseline / proposal 구현 위치
5. 현재 메인라인과 레거시 참조의 구분
