# DFXISP: ZCU104 FPGA 기반 리소스 인식형 적응형 AI-ISP 설계 현황 브리핑

본 문서는 머신비전용 RAW/AI-ISP에서 장면 조건에 따라 ISP 구성을 동적으로 변경하는 **DFXISP(Dynamic Function eXchange AI-ISP)** 프로젝트의 설계 확정 사항, 구현 사양 및 실험 프로토콜을 정리한 종합 브리핑 문서이다.

---

## 1. 개요 (Executive Summary)

DFXISP 프로젝트는 Zynq UltraScale+ ZCU104 FPGA 환경에서 머신비전 성능(mAP)을 최적화하기 위해 ISP를 실시간으로 적응시키는 하드웨어 방법론을 제안한다. 핵심 전략은 ISP 적응 동작을 **빠른 레지스터 업데이트(Register-fast path)**와 **구조적 하드웨어 교체(DFX-RM slow path)**의 두 계층으로 분리하는 것이다. 이를 통해 정상 조도(Normal)와 저조도(Low-light) 환경 간의 상호 배타적인 연산 구조를 시분할로 공유함으로써 면적과 전력 효율성을 극대화하고, 머신비전 정확도를 보존한다.

---

## 2. 핵심 연구 기여 (Key Contributions)

### 2.1 하이브리드 레지스터/DFX 적응 정책
단순 파라미터(Gain, Gamma 등) 변화는 AXI-Lite 레지스터 및 LUT 업데이트로 처리하고, 구조 자체가 변경되어야 하는 무거운 연산 블록(Binning, 저조도 전용 프런트엔드)만 DFX(Dynamic Function eXchange)를 통해 교체한다.

### 2.2 태스크 인식형 저조도 재구성 모듈(RM)
인간의 시각적 품질(PSNR/SSIM) 개선이 아닌, 객체 검출(Object Detection)의 mAP 향상을 목표로 하는 저조도 전용 RM(DFX-Bin, DFX-FP)을 설계한다.

### 2.3 DFX 인식형 모드 스케줄러
단순 조도 임계값 기반 전환이 아니라, 부분 재구성 지연(PR Latency), 프레임 드레인(Drain), 스위칭 횟수 및 진동(Thrashing) 리스크를 고려한 장면 단위 스케줄러를 도입한다.

### 2.4 ZCU104 실증 패키지
이론적 주장에 그치지 않고 ZCU104 보드 상에서 자원 사용량, 전력, FPS, mAP, 재구성 지연 시간 등 하드웨어 증거를 정량적으로 제시한다.

---

## 3. 상세 설계 및 구현 사양 (Implementation Specifications)

### 3.1 적응 계층 분리 가이드라인
분석 결과, 정상 조도와 저조도 간의 ISP 델타 중 대부분은 파라미터 스왑으로 해결 가능하나, 구조적 이득을 위해 DFX가 필요한 영역을 다음과 같이 정의한다.

| 항목 | 적응 방식 | 구현 세부사항 | 비고 |
| :--- | :--- | :--- | :--- |
| **Gain, Gamma, AWB/CCM** | 레지스터/LUT 스왑 | AXI-Lite Register / LUT Pointer | 빠르고 PR 불필요 |
| **Binning Path** | DFX RM 교체 | 2x2 Binning 연산 구조 | 데이터패스 변화 |
| **Low-light Front-end** | DFX RM 교체 | Feature-preserving RM (DFX-FP) | 면적 효율성 확보 |

### 3.2 저조도 RM(Reconfigurable Module) 상세
현재 두 가지 형태의 저조도 RM이 확정되었다.

1.  **DFX-Bin (Baseline):** 2x2 Binning + Gain + Gamma를 수행한다. SNR 향상에는 유리하나 해상도 손실 리스크가 있다.
2.  **DFX-FP (핵심 제안):** Green-guided feature-preserving RM이다. 해상도를 유지하면서 Green 채널 가이드를 통해 로컬 대비를 향상시키며, 객체 검출 특징점 보존에 집중한다.

### 3.3 운영 제약 사항
*   **해상도 및 FPS:** 평가 기준 1280×720 @ 30fps (프레임 예산 33.3ms).
*   **PR 지연 예산:** 재구성은 프레임 단위가 아닌 장면 단위로 수행하며, 재구성 지연은 장면 체류 시간(Dwell time) 내에서 관리한다.

---

## 4. 실험 프로토콜 (Experiment Protocol)

실험은 소프트웨어(SW) 검증 단계와 하드웨어(HW) 실측 단계로 구분되어 진행된다.

### 4.1 SW 단계 (보드 불필요)
*   **E1. Golden Bit-exact:** Python 참조 모델과 HLS C-sim 결과 간의 비트 일치 여부를 검증한다.
*   **E2. pseudo-RAW mAP:** COCO 및 ExDark 데이터셋을 ISP C-모델에 통과시킨 후 검출기(Detector)를 통해 mAP를 측정한다.
*   **E3. Scheduler 시뮬레이션:** 히스테리시스 및 시간적 안정화 알고리즘의 성능을 시뮬레이션한다.

### 4.2 HW 단계 (ZCU104 실측)
*   **E4. HLS Synthesis:** 자원 사용량 추정치 및 레이턴시 리포트를 확보한다.
*   **E5. Vivado Implementation:** 최종 비트스트림을 생성하고 정확한 자원 점유량(LUT/FF/BRAM/DSP)을 기록한다.
*   **E6. 보드 실측:** 전력 소모, 실제 PR 지연 시간, 스케줄러 안정성을 ZCU104에서 직접 측정한다.

---

## 5. 종합 현황 측정 레이아웃 (Measurement Layout)

모든 측정값은 아래 표 형식으로 기록될 예정이며, 현재는 실측 전 단계로 **TODO(측정)** 상태이다.

### [표 1] 하드웨어 자원 및 성능 비교
| 항목 | Static (고정) | Register-only | DFX-Bin (RM) | DFX-FP (RM) |
| :--- | :--- | :--- | :--- | :--- |
| **LUT (#, %)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **FF (#, %)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **BRAM (#, %)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **DSP (#, %)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **Power (W)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **PR Latency (ms)** | N/A | N/A | TODO(측정) | TODO(측정) |

### [표 2] 머신비전 성능 (mAP)
| 데이터셋 | Static (고정) | Register-only | DFX-Bin | DFX-FP |
| :--- | :--- | :--- | :--- | :--- |
| **mAP (COCO)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **mAP (ExDark)** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |
| **Golden Mismatch** | TODO(측정) | TODO(측정) | TODO(측정) | TODO(측정) |

---

## 6. 주요 인용구 및 통찰 (Important Quotes & Insights)

> "본 연구의 novelty는 'DFX를 썼다'가 아니라, **task-aware AI-ISP adaptation을 register-fast path와 DFX-RM slow path로 나누고, mAP·resource·power·PR latency를 함께 평가하는 resource-aware adaptive AI-ISP 방법론**이다."

> "DFX의 신규성 주장 = '상호배타 + 면적 큰 low-light 프런트엔드를 부분재구성으로 시분할'. 단순 gain/gamma는 비교군(register baseline)으로 두고 **DFX가 면적/전력에서 이기는 지점**을 실험 변인으로 설계한다."

**통찰:** 
*   **YAGNI(You Ain't Gonna Need It) 대응:** 레지스터 스왑만으로 충분하지 않은 '구조적 변화'를 DFX로 처리함으로써 하드웨어 신규성을 확보한다.
*   **스케줄러의 현실성:** 기존 연구들이 무시해온 PR Latency와 Frame Stall 비용을 스케줄러 알고리즘에 직접 포함시켜 실제 임베디드 환경에서의 실용성을 높인다.

---

## 7. 실행 가이드 및 리스크 관리 (Actionable Insights)

1.  **레지스터 전용 베이스라인 확립:** DFX의 순수 이득을 증명하기 위해 레지스터 업데이트만 지원하는 적응형 모델을 대조군으로 고정한다.
2.  **DFX-FP 튜닝 리스크:** Green-guided 알고리즘의 경우 색잡음 증폭 리스크가 있으므로 Edge-aware gating 등을 통해 보완 설계가 필요하다.
3.  **장면 단위 전환 준수:** PR Latency가 프레임 예산을 초과할 가능성이 높으므로, 반드시 히스테리시스 알고리즘을 적용하여 빈번한 재구성을 억제한다.
4.  **HLS 설계 최적화:** DFX-FP의 5x5 윈도우 연산 시 II(Initiation Interval)=1을 달성하여 실시간 스트리밍 성능을 확보한다.