# DFX-AIISP: ZCU104 FPGA를 위한 DFX 기반 Resource-Aware Task-Aware AI-ISP 설계 리포트

## 1. 연구 개요 및 문제 정의 (Research Overview & Problem Definition)

### 1.1 하드웨어 관점의 적응형 ISP 정의 및 한계
본 연구는 머신비전용 AI-ISP에서 조도 및 장면 조건(Scene Condition)에 따라 ISP 파이프라인을 동적으로 변경하는 문제를 **하드웨어 자원 효율적(Resource-Aware) 구현 관점**에서 재정의한다. 기존의 Task-aware ISP 연구(DynamicISP, TA-ISP 등)는 주로 소프트웨어적 모듈 선택이나 신경망 기반 파라미터 튜닝에 집중해 왔다. 그러나 고정된 하드웨어 구조(Static Architecture) 내에서 복잡한 저조도 강화 알고리즘을 모두 배치할 경우, ZCU104와 같은 임베디드 FPGA에서는 로직 게이트 용량 초과 및 전력 소비 급증이라는 한계에 직면하게 된다.

### 1.2 DFXISP의 핵심 가설: Resource-mAP Trade-off 최적화
본 설계는 적응형 동작(Adaptation)을 두 개의 계층(Register-fast path vs. DFX-RM slow path)으로 분리하는 **DFXISP(Dynamic Function eXchange ISP)** 아키텍처를 제안한다.

*   **Register-fast path:** Gain, Gamma, Threshold 등 파이프라인 전반에 흩어져 있는 경량 파라미터 변화를 AXI-Lite Register 및 LUT Pointer 업데이트를 통해 즉각 처리한다.
*   **DFX-RM slow path:** 하드웨어 면적을 많이 차지하여 정적으로 구현 시 리소스 예산을 초과하는 무거운 연산(Low-light Front-end 등)을 **Partial Reconfiguration(PR)** 기술을 통해 시분할(Time-sharing) 방식으로 교체한다.

**연구 가설:** ISP 구조를 '구조적 시분할(Structural Time-sharing)' 기반의 DFX로 설계함으로써, 단일 정적 ISP로는 구현 불가능한 고성능 알고리즘을 탑재하여 인식 성능(mAP)을 극대화하고, 동시에 임베디드 환경의 물리적 리소스 제약을 극복할 수 있을 것이다.

---

## 2. 핵심 기여 4가지 (Four Core Contributions)

1.  **Hybrid Register/DFX Adaptation Policy:** 머신비전 ISP 적응을 빠른 파라미터 업데이트(Register/LUT)와 구조적 교체(DFX-RM)로 분리하여 FPGA 구현 효율을 극대화하는 설계 방법론을 제시한다.
2.  **Task-aware Low-light RM:** 인간의 시각적 화질 개선이 아닌, 실제 객체 탐지 알고리즘의 **mAP(mean Average Precision)** 향상을 최우선 목표로 하는 저조도 대응 Reconfigurable Module(RM)을 설계한다.
3.  **DFX-aware Mode Scheduler:** 단순 조도 임계값을 넘어, **ICAP(Internal Configuration Access Port)** 대역폭에 따른 PR Latency, **AXI-Stream Drain** 프로세스, 전환 빈도(Thrashing)를 고려한 장면 단위 스케줄러를 제안한다.
4.  **ZCU104 Evidence Package:** Zynq UltraScale+ ZCU104 보드 상에서 구현된 4가지 비교군의 리소스, 전력, 성능, 지연 시간 및 Bit-exact 검증 데이터를 포함한 실측 패키지를 제공한다.

---

## 3. 확정 설계 결정 및 근거 (Confirmed Design Decisions & Rationale)

### 3.1 Register vs DFX 분리 및 Pblock 배치 정책
ZCU104의 하드웨어 제약을 분석한 결과(A1 Analysis), Gain 및 Gamma 모듈은 ISP 파이프라인의 프런트엔드와 백엔드에 각각 분산되어 존재한다. DFX의 **Reconfigurable Partition(RP)**은 물리적으로 연속된 **Pblock** 영역에 할당되어야 하므로, 흩어진 모듈을 하나의 RP로 묶는 것은 라우팅 복잡도를 급증시키고 RP 크기를 비효율적으로 키우는 결과를 초래한다. 따라서 비연속적인 파라미터 변화는 Register-path로, 연속된 연산 구조가 바뀌는 프런트엔드(Binning/Denoise)만 DFX-path로 확정 분리하였다.

| 구분 | 대상 항목 (Examples) | 구현 방식 (Implementation) | PR 필요 여부 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **Parameter Adaptation** | Gain, Gamma, AWB/CCM Coeff | AXI-Lite Register / LUT Pointer | No (Fast) | 파이프라인 내 분산 배치 |
| **Structural Adaptation** | Binning, Feature-preserving Front-end | DFX Reconfigurable Module (RM) | Yes (Slow) | 연속된 Pblock 영역 할당 |

### 3.2 Low-light RM 선정 근거: SimROD 기반 DFX-FP
*   **DFX-Bin (Baseline):** 2x2 Binning을 통해 SNR을 확보하나 해상도 손실로 인해 원거리 객체 mAP 하락 리스크가 존재한다.
*   **DFX-FP (Main Contribution):** 해상도를 유지하며 탐지 성능을 보존하는 **Feature-preserving RM**이다. Bayer G 채널의 Edge 정보를 활용하는 **Green-guided(SimROD 계열)** 알고리즘을 하드웨어 네이티브 구조로 재설계하여 적용한다. 이는 고정된 연산량 내에서 mAP를 극대화하기 위한 결정이다.

### 3.3 Scheduler 동작 원리 및 하드웨어 연동
DFX 전환은 시스템 정지 최소화를 위해 다음의 원리를 적용한다.
1.  **AXI-Stream Drain:** 모드 전환 전 파이프라인 내 잔류 데이터를 소거하여 Reconfiguration 시 데이터 오염을 방지한다.
2.  **ICAP 제어:** DFX Controller를 통해 부분 비트스트림을 내부 설정 액세스 포트(ICAP)로 전송한다.
3.  **Hysteresis & Temporal Smoothing:** 조도 통계값에 히스테리시스를 적용하고 N-프레임 이상 안정될 때만 전환하여 빈번한 스위칭(Thrashing)을 억제한다.

---

## 4. 비교군 및 평가 계획 (Comparison Variants & Evaluation Plan)

### 4.1 실험 비교군 (Variants)

| Variant | Adaptation 방식 | 저조도 처리 블록 | DFX 사용 여부 | 목적 |
| :--- | :--- | :--- | :--- | :--- |
| **Static** | None | None | No | 리소스 및 성능 베이스라인 |
| **Register-only** | Gain/Gamma/Threshold | Resident/Bypass | No | 파라미터 적응의 한계 측정 |
| **DFX-Bin** | Register + RM | 2x2 Binning | Yes | 기존 제안 방식의 검증 및 비교 |
| **DFX-FP** | Register + RM | Feature-preserving (SimROD) | Yes | **본 연구의 핵심 제안 성능 확인** |

### 4.2 평가지표 및 환경 (Metrics)
*   **Target:** 1280x720 (720p) @ 30fps (Frame budget: 33.3ms)
*   **Dataset:** COCO (일반), ExDark (저조도) pseudo-RAW 데이터셋

| 평가지표 (Evidence Package) | Static | Reg-only | DFX-Bin | DFX-FP |
| :--- | :--- | :--- | :--- | :--- |
| **mAP (COCO / ExDark)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **Resource (LUT / FF / BRAM / DSP)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **Power (W)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **FPS / Throughput** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **Register Update Latency (ms)** | N/A | TODO(측정) | TODO(측정) | TODO(측정) |
| **PR Latency (via ICAP) (ms)** | N/A | N/A | TODO(측정) | TODO(측정) |
| **Partial Bitstream Size (MB)** | N/A | N/A | TODO(측정) | TODO(측정) |
| **Bit-exact Golden Mismatch** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |

---

## 5. 관련 연구 대비 차별점 (Differentiation from Related Research)

| 연구명 | 적응 방식 | HW 구현 형태 | 주요 목표 | DFXISP와의 차이점 |
| :--- | :--- | :--- | :--- | :--- |
| **DynamicISP** | Parameter | Static | 인식 성능 향상 | 구조적 변경 불가능 |
| **AdaptiveISP** | Structural (Selection) | Software-based | 파이프라인 최적화 | 실시간 HW PR 제약 미고려 |
| **Dark-ISP / SimROD** | Algorithm | Neural / Static | 저조도 탐지 개선 | 하드웨어 자원 공유 불가 |
| **Vitis Vision** | Static Block | Static Library | ISP 빌딩 블록 | 동적 재구성 기능 부재 |
| **DFXISP (본 연구)** | **Hybrid (Reg+DFX)** | **Dynamic (DFX)** | **Resource-Aware mAP** | **시분할 기반 구조적 교체** |

본 연구는 SimROD 등의 알고리즘에서 영감을 얻었으나, 이를 단순히 고정된 가속기로 구현하는 것이 아니라 **하드웨어 네이티브 구조의 시분할(Structural Time-sharing)**을 통해 제한된 리소스 내에서 고성능 모듈을 교체 운용한다는 점에서 독창성을 가진다.

---

## 6. 리스크 및 한계 (Risks & Limitations)

1.  **Pseudo-RAW 정합성 리스크:** 현재 실험에 사용되는 pseudo-RAW 데이터셋이 실제 센서의 물리적 노이즈 특성을 완벽히 반영하지 못할 수 있다. 향후 LOD/NOD 등 Real RAW 데이터셋을 통한 추가 검증이 필요하다.
2.  **PR Latency 및 프레임 드랍:** 33.3ms 프레임 예산 내에서 ICAP을 통한 부분 비트스트림 로딩과 AXI-Stream Drain이 완료되어야 한다. RM 크기가 커질 경우 지연 시간으로 인한 일시적 프레임 드랍 리스크가 존재한다.
3.  **HLS 리소스 및 Pblock 라우팅:** DFX-FP(Green-guided) 알고리즘의 복잡도가 증가함에 따라 HLS 리소스 사용량이 할당된 **Pblock 물리 영역**을 초과할 수 있다. 이 경우 비트스트림 라우팅 실패(Routing failure)가 발생할 수 있으므로 엄격한 리소스 관리가 요구된다.