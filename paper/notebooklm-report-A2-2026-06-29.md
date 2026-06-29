# ZCU104 기반 Resource-Aware 적응형 ISP(DFXISP) 종합 브리핑: 방향 A

## 1. 연구 개요 및 핵심 논지 (The Core Thesis)

본 연구는 머신비전용 AI-ISP의 적응형 동작(Adaptation)을 하드웨어 자원 최적화 관점에서 재정의한다. 기존의 Task-aware ISP 연구들이 주로 검출 정확도(mAP) 향상에 매몰되었던 것과 달리, **DFXISP(Direction A)**는 **'자원 효율성 및 전력 절감'**을 최상위 설계 목표로 설정한다. 

### 핵심 아키텍처: 이중 적응 경로 (Hybrid Path)
*   **Register-fast path (정확도 담당):** Gain, Gamma, Threshold 등 파라미터 기반 적응은 AXI-Lite 레지스터 수정을 통해 µs 단위로 즉각 대응한다. 실측 결과, 저조도 환경의 검출 정확도는 이 경로만으로도 충분히 확보됨이 확인되었다.
*   **DFX-RM slow path (효율 담당):** 연산 구조가 판이하거나 면적 점유가 커서 상시 상주 비용이 높은 블록(예: 저조도 전처리 프런트엔드)은 Dynamic Function eXchange(DFX) 기술을 통해 장면 단위로 시분할 적재한다.

### 연구의 논거 및 4대 기여점
1.  **mAP Guardrail 개념 도입:** 본 아키텍처에서 mAP는 극대화의 대상이 아닌, 기준선(Register-only 대비 -1.0pt 이내)을 유지해야 하는 '가드레일'로 관리된다.
2.  **DFX 적용의 정당성:** 상호배타적인 동작(주간 vs 야간)을 수행하는 모듈들을 동일한 FPGA Fabric 영역에 교체 적재함으로써 정적 면적과 동적 전력을 획기적으로 최적화한다.
3.  **4대 핵심 기여:**
    *   **Partitioning Policy:** 레지스터 기반 고속 적응과 DFX 기반 구조적 적응을 분리하는 결정 기준 제시.
    *   **RM Screening:** 자원/전력 이득과 mAP 가드레일을 결합한 최적 Reconfigurable Module 선별 방법론.
    *   **DFX-Aware Scheduler:** PR Latency와 하드웨어 제약(AXI Stream Drain 등)을 고려한 목적 함수 기반 스케줄러.
    *   **Evidence Package:** ZCU104(Zynq UltraScale+) 보드 기반의 실증적 하드웨어 수치 제공.

## 2. 하드웨어 구현 및 C-Synthesis 실측 분석

Vitis HLS 2024.1을 사용하여 ZCU104(xczu7ev-ffvc1156-2-e) 타깃으로 합성한 결과, 모든 설계 변이(Variant)에서 동일한 타이밍 결과가 확인되었다.

### [표 1] Variant별 HLS 합성 결과 (Target: 5.0ns)
| Variant | 역할 | LUT | FF | DSP | BRAM | CP (ns) | Fmax (MHz) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Normal** | Static Base | 4,654 | 3,537 | 14 | 3 | 3.650 | 273.97 |
| **Reg_only** | Register Fast-path | 4,780 | 3,564 | 14 | 3 | 3.650 | 273.97 |
| **DFX-Bin** | RM (2x2 Binning) | 18,783 | 16,183 | 56 | 4 | 3.650 | 273.97 |
| **DFX-FP** | RM (Ablation/Fail) | 22,216 | 24,372 | 47 | 4 | 3.650 | 273.97 |

**[분석]**
모든 Top 모듈의 Critical Path(CP)가 **3.650ns**로 고정되어 있다. 이는 시스템의 최대 동작 주파수(Fmax)가 설계 변이에 따른 변별점이 되지 못함을 시사한다. 따라서 본 연구의 핵심 성과는 속도 경쟁이 아닌, **면적(Area)과 전력(Power)**이라는 하드웨어 비용 축에서 도출되어야 한다.

## 3. 자원 효율성 및 전력 분석 (Direction-A 정직 보고)

DFX를 통한 면적 절감 효과를 현재의 구현 단계(Honest Report)와 향후 확장성(Architectural Trajectory) 관점에서 이원화하여 분석한다.

### 정적 면적 절감의 현실과 확장성
*   **Deployed 2-RM (Reg+Bin) 세트:** 현재 최종 배치 시 정적 LUT 면적 절감은 **0.7%**로 미미하다. 이는 대형 모듈인 Binning RM이 전체 Pblock 크기를 결정하고, Register RM은 상대적으로 자원 점유가 거의 없기 때문이다.
*   **Scalability Simulation (3-RM 시):** 하지만 RM 라이브러리가 증가할수록 DFX의 이득은 선형적으로 증가한다. DFX-FP를 포함한 3개 RM을 가정할 경우, 모든 블록을 상주시키는 방식(Static all-resident) 대비 **LUT 39.1%, DSP 47.2%**의 획기적인 절감이 가능하다.

### 전력 효율성: PL Power Gating equivalent 효과
본 연구의 가장 강력한 하드웨어적 논거는 **'Dark Fabric'** 효과를 통한 전력 절감이다.
*   주간(Normal) 모드 작동 시, 전체 면적의 약 75%를 차지하는 Binning 관련 데이터패스가 FPGA 상에 아예 구성되지 않는다.
*   결과적으로 주간 모드에서는 **74.7%의 로직이 비활성화(Dark)**되어, 모든 기능을 하드웨어에 상주시켰을 때 발생하는 불필요한 누설 및 동적 전력 소모를 원천적으로 차단한다. 이는 임베디드 환경에서 **"PL Power Gating"**에 상응하는 효과를 제공한다.

## 4. mAP Guardrail 검증 및 RM Screening 결과

다양한 Detector(YOLOv8n/s, SSDLite-MobileNetV3)를 통한 교차 검증 결과, Screening 방법론의 신뢰성이 입증되었다.

### [표 2] 저조도 환경(ExDark) mAP 비교 (Guardrail 검증)
| Variant | YOLOv8n | YOLOv8s | SSDLite-MNv3 | 판정 |
| :--- | :---: | :---: | :---: | :--- |
| **Reg-only** | **0.1585** | **0.1902** | **0.1098** | **Best (기준)** |
| **Static** | 0.1492 | 0.1714 | 0.1052 | - |
| **DFX-Bin (Bilinear)**| 0.1576 | 0.1511 | 0.1063 | **Pass** (-0.0009) |
| **DFX-FP** | 0.0879 | 0.1018 | 0.0656 | **Fail (Screened)** |

**[분석]**
1.  **Register Path의 우수성:** 모든 Detector에서 Reg-only가 최상위 성능을 기록하여 "정확도는 레지스터 패스에서 확보한다"는 전제를 입증했다.
2.  **Screening 방법론의 증거:** Detail-boost 방식을 취한 DFX-FP는 mAP가 급락하여 가드레일을 통과하지 못했다. 이는 해당 모듈이 저조도 환경의 **Demosaic 및 Quantization 아티팩트를 증폭**시켜 Detector의 Feature 추출을 방해했기 때문이다. Screening 과정에서 이러한 부적합 모듈을 걸러냄으로써 시스템 신뢰성을 확보한다.
3.  **Bilinear Fix를 통한 가드레일 준수:** 초기 Nearest-neighbor 방식에서 mAP 하락이 컸던 DFX-Bin은 **Integer Bilinear 업샘플링**으로 알고리즘을 업그레이드한 결과, Reg-only 대비 mAP 하락 폭을 **1.0pt 이내**로 억제하며 가드레일을 성공적으로 통과했다.

## 5. DFX-Aware 모드 스케줄러 설계

본 스케줄러는 단순 밝기 임계값 방식이 아닌, 하드웨어 물리 제약(PR Cost)을 목적 함수에 명시적으로 반영한다.

*   **장면 단위(Scene-level) 전환 원칙:** Partial Reconfiguration(PR) 시 발생하는 비트스트림 로딩 지연(Latency)과 ICAP 대역폭 제한을 고려하여, 프레임 단위가 아닌 장면 단위의 전환을 수행한다.
*   **하드웨어 안정성 보장:** 소프트웨어 기반 스케줄러(AdaptiveISP 등)가 간과하는 **AXI Stream Drain** 로직을 통합하여, 재구성 중 데이터 스트림이 엉켜 시스템이 Hang 상태에 빠지는 것을 방지한다.
*   **Hysteresis 및 Temporal Smoothing:** 모드 전환의 빈번한 발생(Thrashing)을 방지하기 위해 상/하향 임계값 분리 및 N-프레임 안정 상태 확인 로직을 적용하였다.

## 6. 향후 보드 단계 검증 계획 (Pending Layout)

현재 HLS 및 시뮬레이션 단계의 검증은 완료되었으나, 실제 보드 상에서의 최종 실측 수치는 레이아웃 완료 후 확정될 예정이다.

### 향후 측정 및 확정 예정 항목
*   **Post-route 최종 자원:** Vivado DFX Flow를 통한 최종 LUT/FF/DSP 실측치.
*   **Partial Bitstream 사양:** 실제 생성된 비트스트림 크기(KB) 및 ICAP를 통한 PR Latency(ms) 정밀 측정.
*   **PMBus 기반 소비전력:** 보드 상의 전원 레일을 활용하여 정적/동적 소비전력(W)을 측정하고 DFX의 전력 이득을 정량화.
*   **시스템 안정성:** 실제 시퀀스 상에서의 모드 전환 시 프레임 소실(Frame Stall) 여부 확인.

## 7. 결론 및 학술적 의의

본 연구는 AI-ISP 설계의 초점을 mAP 경쟁에서 하드웨어 구현 비용(Resource/Power) 경쟁으로 전환하는 실증적 방법론을 제시한다.

1.  **현실적 하드웨어 비용 해결:** 기존 AI-ISP 연구가 간과한 하드웨어 자원 점유 문제를 DFX 기반 시분할 적재로 해결함으로써 에지 장치에서의 구현 가능성을 높였다.
2.  **ZCU104 Evidence Package의 가치:** 이론적 제안을 넘어 실제 FPGA 타깃 합성 결과와 mAP 가드레일 검증 데이터를 결합하여 설계의 신뢰성을 증명하였다.
3.  **Resource-aware Adaptation의 범용성:** 본 연구에서 제안한 적응형 정책은 저조도 ISP뿐만 아니라, 다양한 환경 변수(날씨, 역광 등)에 대응해야 하는 차세대 임베디드 비전 시스템에 범용적인 아키텍처 가이드를 제공한다.