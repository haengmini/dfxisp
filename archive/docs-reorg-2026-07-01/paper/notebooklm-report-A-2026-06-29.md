# DFXISP 논문 방향 A(Resource-Aware) 종합 브리핑

## 1. 논문 핵심 요지 및 연구 방향 전환 (Direction A)

본 연구는 임베디드 비전 시스템에서의 DFX(Dynamic Function eXchange) 기술 가치를 기존의 '인식 정확도(mAP) 향상'에서 **'자원(Resource) 및 전력(Power) 절감'**으로 재정의합니다. 이는 불필요한 하드웨어 로직을 상시 상주시키지 않는다는 **'YAGNI(You Ain't Gonna Need It)'** 설계 원칙을 하드웨어 레벨에서 실증하는 패러다임의 전환입니다.

이러한 전략에 따라 시스템의 역할을 다음과 같이 이원화합니다.
*   **Register-fast path:** 파라미터 기반의 신속한 적응(Gain, Gamma 등)을 담당하며, 실질적인 인식 정확도(mAP) 확보를 책임집니다.
*   **DFX (Slow path):** 면적 및 전력 소모가 큰 저조도 전용 구조 블록(Binning 등)을 시분할 적재하여 하드웨어 효율화를 담당합니다.
*   본 연구의 핵심 서사는 **"mAP는 Guardrail(안전장치)로 활용한다"**는 것이며, DFX의 존재 목적은 mAP의 극적인 향상이 아닌, 정확도를 보전하면서 가용 자원을 극대화하는 데 있습니다.

## 2. 4대 핵심 기여 (Core Contributions)

방향 A로의 재편에 따른 본 논문의 주요 기여점은 다음과 같습니다.

*   **C1. Resource-aware register/DFX partitioning policy:** 연산 특성에 따라 Register/LUT(빠른 전환, mAP 유지 담당)와 DFX-RM(구조적 변경, 자원 효율 담당)으로 분리하는 공학적 결정 기준 및 설계 정책을 제시합니다.
*   **C2. mAP-guardrail RM screening:** 자원/전력 이득과 mAP 하한선을 기준으로 Reconfigurable Module(RM) 후보를 선별하는 절차를 수립합니다. 실측 데이터를 근거로 mAP 하락이 큰 DFX-FP를 탈락시키고 DFX-Bin을 최종 선정하는 방법론적 근거를 제공합니다.
*   **C3. DFX-aware scene scheduler:** 부분 비트스트림 크기와 ICAP 대역폭에 따른 **PR Latency**, 프레임 안정성(Hysteresis), 전환 비용(Frame drop/Stall)을 종합적으로 고려한 장면 단위 적응형 스케줄러를 설계합니다.
*   **C4. ZCU104 resource/power evidence package:** 실제 ZCU104 보드 환경에서 `static all-resident` 구성 대비 DFX 적용 시의 자원 소모, 소모 전력, 비트스트림 크기 및 실측 PR Latency 데이터 세트를 제공합니다.

## 3. 실측 기반 mAP 결과 및 Guardrail 검증

예비 실험(E2)을 통해 확인된 pseudo-RAW 기반 mAP 실측 데이터입니다. (YOLOv8n, mAP@[.5:.95] 기준)

| Variant | COCO 전체 (n=347) | ExDark real-lowlight (n=260) | 비고 |
| :--- | :---: | :---: | :--- |
| **static (demosaic-only)** | 0.2984 | 0.1492 | 정확도 참조용 |
| **register-only** | 0.2952 | **0.1585** | **가장 강력한 Baseline** |
| **DFX-Bin (bilinear)** | 0.2839 | **0.1576** | **Guardrail 통과 (Δ0.09pt)** |
| **DFX-FP (detail-boost)** | 0.2518 | 0.0879 | Guardrail 탈락 (Ablation) |

### 데이터 분석 및 인사이트
*   **DFX-FP의 부정적 결과:** Feature-preserving 방식의 DFX-FP는 ExDark에서 0.0879를 기록, Register-only 대비 성능이 급락하였습니다. 이는 Detail-boost 과정에서 저조도 아티팩트가 증폭된 결과로, 본 연구에서는 이를 방법론적 Screening의 정당성을 입증하는 **Ablation 사례**로 활용합니다.
*   **DFX-Bin의 Guardrail 통과:** 기존 Nearest 업샘플 방식의 한계를 극복하기 위해 **9/3/3/1 Integer Bilinear 업샘플**을 도입하였습니다. 그 결과 ExDark 환경에서 Register-only 대비 단 0.09pt 차이로 하락을 억제하며 성공적으로 Guardrail을 통과하였습니다.
*   **결론:** 실측 결과 저조도 mAP에서는 Register-only 적응이 가장 강력한 성능을 보임을 확인하였습니다. 이는 "DFX의 가치는 mAP 향상이 아닌 자원 절감에 있다"는 본 연구의 논리적 정당성을 뒷받침합니다.

## 4. 평가 지표 및 Baseline 정의

실험의 공정성과 하드웨어적 엄밀성을 위해 다음과 같이 지표를 정의합니다.

*   **1차 지표 (Efficiency):** 
    *   자원 소모량(LUT, FF, BRAM, DSP) 및 소모 전력(Power)
    *   부분 비트스트림(Partial Bitstream) 크기 및 PR Latency
*   **Guardrail 지표 (Accuracy):** 
    *   Register-only 대비 mAP 하락폭이 **절대치 1.0pt(@[.5:.95], 상대치 약 5%) 이내**를 유지해야 함.
*   **자원 Baseline:** 
    *   **'Static all-resident'**를 기준으로 삼습니다. 이는 정상 조도와 저조도 처리 블록이 FPGA 내부에 상시 상주하는 구성을 의미하며, DFX를 통한 실제적인 면적 및 전력 절감 효과를 측정하는 대조군입니다.
    *   *주의: 정확도 참조용인 'static(demosaic-only)'과 자원 비교용인 'static all-resident'를 엄격히 구분하여 평가합니다.*

## 5. RM(Reconfigurable Module) 설계 사양 및 검증

### DFX-Bin (최종 제안 모듈)
*   **알고리즘:** 2x2 Binning 및 **9/3/3/1 가중치 기반 Integer Bilinear 업샘플** 구현.
*   **설계 의도:** SNR 향상에 집중하면서도 해상도 복원 시 아티팩트를 최소화하여 저조도 환경에서 안정적인 인식을 지원합니다.

### DFX-FP (Ablation 모듈)
*   **알고리즘:** Green-guided feature-preserving 및 Local contrast 강화 방식.
*   **설계 의도:** 해상도 보존을 목표로 설계되었으나, 실측 데이터 기반 Screening 과정에서 mAP 저하 리스크가 확인되어 방향 A에서는 성능 하한선 검증용 사례로 전환되었습니다.

### 신뢰성 검증 (Bit-exact Verification)
*   Python Golden 모델과 Vitis HLS C-sim 간의 연산 정밀도를 대조하여, 2816px 테스트 케이스에 대해 **'0 mismatch (Bit-exact)'**를 달성함으로써 하드웨어 구현의 신뢰성을 확보하였습니다. 모든 RM은 RP 슬롯의 ABI(입출력 HxW 고정)를 준수합니다.

## 6. 한계점 및 향후 로드맵

### 현재 구현의 한계
*   **노이즈 모델의 한계:** 현재 pseudo-RAW 환경은 실제 센서의 물리적 노이즈 특성을 완벽히 반영하지 못하므로, 향후 real-RAW 데이터를 통한 심화 검증이 필요합니다.
*   **실측 데이터 진행 상황:** 현재 알고리즘 검증은 완료되었으나, ZCU104 보드에서의 정밀 전력 및 지연 시간 측정은 최종 완료 단계(TODO)에 있습니다.

### 향후 단계 (Evidence Package 완성)
1.  **ZCU104 실측 수치 확보:** DFX-Bin RM의 HLS 합성을 통해 `static all-resident` 대비 정량적인 자원 및 전력 절감 수치를 산출합니다.
2.  **Resource-Efficiency Trade-off 정량화:** 측정된 데이터를 바탕으로 방향 A의 핵심 가설인 "인식 성능 보전 하의 자원 효율성 극대화"를 입증하는 **Primary Evidence Package**를 완성합니다.

## 7. 최종 브리핑 요약

**본 연구는 mAP 성능을 register-fast path로 보전하면서, DFX 기술을 통해 상시 자원 소모가 큰 저조도 모듈을 시분할 적재함으로써 FPGA의 자원 및 전력 효율을 극대화하는 방법론을 실증합니다.**