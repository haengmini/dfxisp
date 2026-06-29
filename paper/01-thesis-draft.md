---
type: paper-draft
title: "DFXISP 학위논문 — 본문 (Working Draft)"
project: DFXISP
status: drafting (서술 완결, 측정값만 TODO)
created: 2026-06-26
updated: 2026-06-28
note: "서술 섹션은 완결. [TODO:측정]은 ZCU104 실측 후 채움. 미검증 수치 단정 금지. 그림/표는 03-figures-tables.md, RM 사양은 04-implementation-rm-spec.md, 실험 절차는 05-experiment-protocol.md."
---

# DFXISP 학위논문 — 본문 (Working Draft)

> 표기: **[TODO:측정]** 실측 필요 · `(refs: …)` → `02-references.md` · `[FigN]/[TabN]` → `03-figures-tables.md`

---

## 1. 서론

### 1.1 배경
머신비전에서 ISP(Image Signal Processing)는 센서 RAW 신호를 인식 가능한 영상으로 변환하는 핵심 전처리 단계다 (refs: isp-npu, hisp). 그러나 최적의 ISP 동작은 장면 조건, 특히 **저조도(low-light)** 여부에 따라 크게 달라진다. 고정 파이프라인은 모든 조건에 단일 동작만 제공하므로, 저조도에서 검출 성능이 급락하거나 정상 조도에서 불필요한 연산을 수행한다 (refs: seeindark, darkisp). FPGA는 ISP를 실시간·저전력으로 구현하기에 적합하지만, 통상 **정적(고정) 회로**로 합성되어 런타임 적응이 어렵다 (refs: hisp, hwllie).

### 1.2 문제 정의
Normal과 low-light는 서로 다른 ISP 동작을 요구한다. 두 경로를 동시에 fabric에 상주시키면 면적·전력이 낭비된다. repo 분석상 두 모드 차이의 **대부분은 파라미터**(gain 256→320, γ 2.2→4.0, 2×2 binning on/off 등; [Tab1])지만, **연산 구조가 바뀌는 부분(binning 경로, 저조도 보정 프런트엔드)** 은 별도 하드웨어를 필요로 한다 (A1 §1). 즉 "무엇을 빠르게 바꾸고(파라미터), 무엇을 구조적으로 교체할지(데이터패스)"를 하드웨어 비용 기준으로 분리하는 문제가 핵심이다.

### 1.3 동기 — 왜 DFX인가
DFX(Dynamic Function eXchange)는 런타임에 부분 비트스트림으로 회로 일부를 교체하는 기술이다 (refs: amd-dfx, amd-dfxctrl). 본 연구의 가설은 **normal·low-light 데이터패스가 상호배타**(동시 불필요)이므로 같은 fabric 영역을 **시분할**하면 면적/전력을 절감할 수 있다는 것이다 (A1 §2). 다만 단순 gain/γ 변화는 register/LUT로 충분하므로, **DFX는 "구조가 바뀌고 면적이 큰 저조도 프런트엔드"에만** 정당화된다. 더 나아가, 예비 실측([08-e2-map-results])에서 **저조도 detection mAP는 register-only 적응이 가장 높았다.** 따라서 본 논문은 역할을 명확히 분리한다: **정확도(mAP)는 register-fast path가, 면적/전력 효율은 DFX-RM slow path가 담당한다.** DFX의 정당성은 "mAP를 올린다"가 아니라 "상시 상주 비용이 큰 상호배타 블록을 필요할 때만 적재해 자원/전력을 아낀다(mAP는 guardrail로 유지)"이다. 이 자원-인식 분리가 본 논문의 중심 논지다 ([Fig2]).

### 1.4 기여 (resource-aware 재편)
적응의 **정확도(mAP)는 register-fast path**가, **면적/전력 효율은 DFX-RM slow path**가 담당하도록 역할을 분리한다. 근거: 예비 실측([08-e2-map-results])에서 real-low-light mAP는 register-only가 최고였고 detail-boost형 DFX-RM은 낮았다.
- **Contribution 1 — Resource-aware register/DFX partitioning policy:** 어떤 연산을 register/LUT(빠름·mAP)로, 어떤 블록을 DFX-RM(면적/전력 큰 상호배타 구조)으로 둘지 결정하는 기준 ([Fig2], [Tab1]).
- **Contribution 2 — mAP-guardrail RM screening:** DFX-RM 후보(DFX-Bin, DFX-FP)를 자원/전력 이득과 **mAP guardrail(≥ register-only)** 로 선별. detail-boost형(DFX-FP)이 저조도 mAP를 해쳐 탈락함을 실측으로 보임(방법론 작동의 증거) ([04-implementation-rm-spec], [08-e2-map-results]).
- **Contribution 3 — DFX-aware scene scheduler:** register 전환(무중단)과 DFX 전환(장면 단위, PR latency·drain·switch·thrashing 고려)을 비용에 맞게 분리 ([Fig6]).
- **Contribution 4 — ZCU104 resource/power evidence package:** static/register-only/DFX-Bin(/DFX-FP ablation) 비교. **1차 지표 = LUT/FF/BRAM/DSP·power·partial bitstream size·PR latency**, **mAP는 guardrail**. DFX가 normal 모드 fabric/전력을 register-only 대비 줄이는지 정량화 ([Tab3]–[Tab7]).

### 1.5 논문 구성
2장에서 DFX/DPR 메커니즘, 적응형·AI-ISP, FPGA ISP 구현을 검토하고 본 연구의 빈자리를 규정한다. 3장은 제안 설계(파이프라인, register/DFX 적응 분리, RP 분할, 모드 전환)를 기술한다. 4장은 ZCU104 구현(툴체인, DFX-Bin/DFX-FP RM, 부분 비트스트림, 비교군)을 다룬다. 5장은 실험 설계와 평가(mAP·자원·전력·PR latency·scheduler 안정성)를 제시한다. 6장은 요약·한계·향후연구로 맺는다. 본 논문은 한글 본문에 영어 기술용어를 병기하며, 미검증 수치는 단정하지 않고 실측 전까지 `TODO(측정)`으로 표기한다.

---

## 2. 관련 연구

### 2.1 DFX / DPR 메커니즘
AMD DFX는 static region과 Reconfigurable Partition(RP)/Module(RM)을 구분하고, 부분 비트스트림을 ICAP로 로드한다 (refs: amd-dfx, amd-dfxctrl, amd-zynqmp-pl). DPR 일반 연구는 재구성 지연·면적·throughput 사이의 트레이드오프를 다룬다 (refs: csur-dpr, eurasip-dpr, dpr-rt). 본 연구는 이 메커니즘을 ISP 저조도 프런트엔드에 적용한다.

### 2.2 적응형 / Task-aware AI-ISP
파라미터 적응 진영(**DynamicISP, TA-ISP, SimROD**)은 인식 성능을 위해 ISP 파라미터/표현을 동적으로 제어한다 (refs: dynamicisp, ta-isp, simrod) → 본 연구의 register/LUT fast path와 정렬된다. 모듈/파이프라인 선택 진영(**AdaptiveISP, POS-ISP**)은 검출용 ISP 파이프라인을 software적으로 최적화한다 (refs: adaptiveisp, pos-isp) → 본 연구의 DFX-aware scheduler의 비교 대상이다. 저조도 RAW machine vision(**Dark-ISP, GenISP, Beyond RGB, AODRaw, SID**)은 RAW에서 검출 mAP를 개선하나 대부분 GPU/소프트웨어다 (refs: darkisp, genisp, beyond-rgb-ram, aodraw, seeindark).

### 2.3 FPGA ISP 구현
HISP는 전통+딥러닝 ISP를 FPGA에 올렸고, Vitis Vision은 HLS ISP 빌딩블록을, FOLD/FPGA Retinex는 저조도 enhancement 가속기를 제공한다 (refs: hisp, vitis-vision-isp, fold-fpga, fpga-retinex). 이들은 대부분 **static accelerator**로, 런타임 RM 교체와 대비된다.

### 2.4 차별점 (positioning)
[Tab2]에 정리한 대로, DFX 진영은 풍부하고 AI-ISP 진영도 활발하지만 **"DFX 부분재구성으로 ISP 저조도 프런트엔드를 장면 단위 시분할 교체하고, machine-vision mAP와 하드웨어 evidence(자원/전력/PR latency)를 동시 검증"하는 자리는 비어 있다**. 기존 task-aware ISP는 FPGA PR cost·partial bitstream·RP 합법성을 고려하지 않으며, 기존 FPGA 저조도 가속기는 정적이다. 단, 본 연구는 novelty 주장에 그치지 않고 **register-only 대비 면적/전력/mAP trade-off가 실재함을 evidence package로 증명**해야 기여가 성립한다(YAGNI 반박). 이 검증 부담을 5장 실험이 담당한다.

---

## 3. 제안 설계

### 3.1 전체 파이프라인 ([Fig1], [Fig3])
baseline 고정 ISP는 BLC→demosaic→AWB→CCM→gamma 순이며, normal/low-light가 공유하는 모듈과 모드 의존 모듈로 나뉜다. 확정 파라미터(설계 기본값)는 [Tab1]에 정리한다(BLC16, gain N256/LL320, AWB R286/G256/B307, CCM288, γ 2.2(N)/4.0(LL)). 제안 파이프라인은 front-end/back-end를 static으로 두고, 저조도 perception block만 RP 슬롯으로 분리한다.

### 3.2 적응 메커니즘 분리 (핵심 방법론) ([Fig2], [Tab1])
- **Register/LUT fast path:** gain·gamma·threshold·AWB/CCM 계수를 AXI-Lite register/LUT로 갱신 → PR 불필요, 수 µs 무중단. DynamicISP/TA-ISP/SimROD류 parameter adaptation의 HW 대응.
- **DFX-RM slow path:** 구조가 바뀌거나 면적이 큰 저조도 블록(DFX-Bin, DFX-FP)만 부분재구성 대상.
- **설계 원칙:** DFX는 장식이 아니라 register-only 대비 resource/power/mAP trade-off가 있을 때만 정당화한다.

### 3.3 RP 분할 결정 ([Fig4])
모드 의존 연산이 파이프라인상 흩어져 있고(binning 프런트, gamma 백엔드) RP는 물리적 연속 영역(Pblock)이어야 하므로, **gain·gamma는 register, 저조도 perception block만 단일 RP=RM**으로 둔다. 흩어진 모듈을 하나의 RP로 묶으면 라우팅 복잡도와 RP 크기가 비효율적으로 커진다(A1 §1). RM 슬롯 ABI는 입출력 H×W를 고정해 DPU-facing 계약을 보존한다([04-implementation-rm-spec] §0).

### 3.4 DFX-aware 모드 전환 ([Fig5], [Fig6])
재구성 지연 ≈ 부분비트스트림 크기 ÷ ICAP 대역폭이므로 프레임 단위(33.3ms@720p30) 스왑은 비현실적이며 **장면 단위 전환**을 택한다(A1 §3). repo baseline checker의 COCO 모드 일치율은 0.216로 낮고 clipping이 많아(A1 §4), scheduler는 **히스테리시스(Th_hi/Th_lo) + 시간 안정화(N-frame) + minimum dwell time + drain/invalid window + soft-knee headroom**을 도입한다. 목적함수는 `task_gain − λ1·PR_latency − λ2·frame_stall − λ3·power − λ4·switch_penalty`로, AdaptiveISP/POS-ISP와 달리 **PR cost를 명시**한다.

---

## 4. 구현

### 4.1 타깃·툴체인
ZCU104(Zynq UltraScale+ MPSoC), Vivado/Vitis 2024.1, Vitis AI(DPU). 검증 체인은 Python golden → HLS C-sim(bit-exact) → Vitis HLS csynth/cosim → Vivado DFX flow(부분 비트스트림) → ZCU104 측정 순이다([04-implementation-rm-spec] §4).

### 4.2 기존 자산 위에 구축
repo `isppipeline/{baseline, proposal}` C/C++ 레퍼런스와 현재 HLS C-sim(`dfxisp_accel`, golden 832px/7케이스 통과)을 기반으로 한다. proposal = checker + binning_gain + pr_controller + isp_proposal.

### 4.3 DFX-RM 구현 ([04-implementation-rm-spec])
- **DFX-Bin:** 2×2 binning + gain + gamma RM. 단순·결정적, SNR↑, 해상도 손실 리스크. baseline/fallback.
- **DFX-FP:** green-guided feature-preserving RM(soft-knee global tone + green-guided local contrast + edge-aware detail). 해상도 보존, mAP 유리(가설), 자원·timing 리스크. **핵심 제안.**
- 각 RM은 Python golden → HLS C-sim bit-exact → csynth/cosim → 부분 비트스트림 순으로 검증한다. 고정소수점 라운딩은 Python/HLS 동일 규칙(±0 목표).

### 4.4 비교군
Static / Register-only / DFX-Bin / DFX-FP의 4-variant를 동일 pipeline·동일 평가 프로토콜로 비교한다([Tab3]). register-only는 "DFX 없이 가능한 적응의 한계"를 보이는 핵심 대조군이다.

---

## 5. 실험 및 평가

### 5.1 실험 설계 (resource-aware 재편)
- 변인: Static / Register-only / **DFX-Bin(DFX 1순위 RM = 2×2 binning)** / (DFX-FP는 ablation).
- **자원 main baseline = static all-resident**(normal+저조도 블록 상시 상주, DFX 없음). DFX-Bin이 이 대비 normal 모드 fabric/전력을 얼마나 줄이는지가 핵심 결과. (※ mAP 변종의 `static`(demosaic-only)과는 다른 개념.)
- **1차 지표 = 자원/전력:** LUT/FF/BRAM/DSP, power, partial bitstream size, PR latency, frame stall, switch count, FPS. (static all-resident 대비 절감)
- **Guardrail 지표 = mAP:** DFX-Bin의 COCO/ExDark pseudo-RAW mAP가 **register-only 대비 절대 1.0 mAP point(@[.5:.95], ≈ 상대 5%) 이내**면 통과(향상은 목표 아님). 예비 실측은 §5.4.
- 해상도: 개발 640×480 → 평가 1280×720@30fps(frame budget 33.3ms). 상세 절차는 [05-experiment-protocol].

### 5.2 재구성 지연 [TODO:측정] ([Fig7])
RM 크기 확정 후 ICAP 대역폭으로 계산/실측. minimum dwell time과 frame invalid window를 PR latency에 맞춰 정의한다. 데이터: `measurements/pr_latency.csv`.

### 5.3 면적·전력 ([Tab4], [Tab5])
저조도 RM을 normal 모드에서 fabric에서 제거했을 때의 LUT/FF/BRAM/DSP·전력 절감을 register-only/static-all-resident 대비로 측정한다.

**자원 — Vitis HLS C-synth 실측(ZCU104 `xczu7ev`, 2024.1, 5.0 ns target; [Tab4a], [10-hw-csynth-resource]).** 4개 top 모두 동일 critical path 3.650 ns(**273.97 MHz**)로 타이밍을 충족 → Fmax는 변별점이 아니며 면적·전력이 변별 축이다(Direction A 일관). LUT: normal 4,654 / reg-only 4,780 / DFX-Bin 18,783 / DFX-FP 22,216, DSP: 14/14/56/47. RM 증분(variant−base)은 reg ΔLUT 126, bin ΔLUT 14,129, fp ΔLUT 17,562로, **저조도 binning 데이터패스가 fabric의 약 75%를 차지**한다.

**DFX vs static-all-resident(도출, [Tab4b], `resource_dfx_savings.csv`).** (i) 최종 배치 2-RM(reg+bin)에서 정적 면적 절감은 **0.7% LUT(126)** 로 미미하다 — bin RM이 지배하고 reg RM은 거의 0이라, 큰 RM 하나를 시분할해도 정적 면적은 거의 줄지 않는다(과장 없이 그대로 보고). (ii) DFX 면적 이득은 **RM 라이브러리 규모에 비례**한다: 후보 3-RM(reg+bin+fp) 기준 static-all-resident 대비 **39.1% LUT / 47.2% DSP** 절감(static은 #RM에 ~선형, DFX는 base+max(RM)에 고정). (iii) 현 RM 수의 지배적 이득은 면적이 아니라 **전력**이다: 주간(normal) 모드에서 RP에 reg RM(4,780 LUT)만 적재되고 binning 데이터패스(14,129 LUT·42 DSP)는 미구성/미클럭 → active-LUT 기준 **74.7%** 가 dark 상태로 동적 전력을 소비하지 않는다. 절대 power(W)·partial bitstream size·PR latency 정량값은 보드 단계에서 확정한다([Tab4c], [Tab5]).

### 5.4 Machine-vision 정확도 — 예비 실측 ([Tab6], [08-e2-map-results])
SW 단계에서 pseudo-RAW mAP를 실제 측정했다(보드 불필요). golden bit-exact는 4-variant 2816px 0 mismatch.
**예비 결과(yolov8n):** COCO 전체(n=347) static 0.298 / reg 0.295 / bin 0.246 / fp 0.252 — 정상조도 위주에서 저조도 처리는 이득이 없어 **적응형 스위칭의 필요성을 실측 검증**(기여 1/3 지지). **ExDark real-low-light(n=260)** reg 0.159 / static 0.149 / bin 0.142 / **fp 0.088** — yolov8s 교차검증도 순서 동일(견고).
**중요(정직):** real-low-light에서 **DFX-FP가 최저, register-only가 최고** → "feature-preserving DFX-FP가 저조도 mAP에서 우월"이라는 가정은 지지되지 않아 DFX-FP는 ablation으로 둔다.
**DFX-Bin guardrail 통과:** DFX 1순위 RM인 DFX-Bin은 nearest→**integer bilinear** 업샘플 개선으로 ExDark(동작 regime) mAP 0.142→0.158로, register-only(0.159) 대비 **0.09pt 이내** → mAP guardrail 통과([08-e2-map-results] 부록). 따라서 DFX-Bin은 mAP를 거의 유지하면서 자원/전력 절감을 노리는 본 방법론의 정당한 DFX RM이다. 정량 자원/전력 결론은 보드 측정 후 확정한다.

### 5.5 Scheduler 안정성 [TODO:측정] ([Tab7])
baseline checker(0.216) → hysteresis/temporal smoothing/minimum dwell 적용 후 mode mismatch·thrashing·switch count·skipped frames 감소를 측정한다(A1 §4).

---

## 6. 결론

### 6.1 요약
본 논문은 머신비전 ISP의 장면 적응을 **register-fast path(정확도 담당)와 DFX-RM slow path(자원/전력 담당)로 역할 분리**하는 resource-aware 설계 방법론을 제안했다. 핵심은 "무엇을 register로, 무엇을 DFX로 둘지를 mAP guardrail 하에 자원/전력 기준으로 결정"하는 partitioning policy와 RM screening 절차, 그리고 이를 검증하는 ZCU104 evidence package다. 예비 실측은 (i) 정상조도에서 저조도 처리가 무익해 **장면 적응 스위칭이 필요**함을 보였고, (ii) real-low-light mAP에서 **register-only가 최고, detail-boost형 DFX-RM이 최저**임을 보여 "DFX=mAP 향상" 가정을 기각하고 "DFX=자원/전력 절감" 재정의를 뒷받침했다. 따라서 본 방법론은 자원이 정당화되지 않는 RM(예: DFX-FP)을 guardrail로 걸러낸다. 설계·구현 사양·실험 프로토콜·그림/표·예비 mAP는 완성되었고, 자원/전력·PR latency 실측은 보드 단계에서 채운다.

### 6.2 한계
- DFX×AI-ISP "빈자리" 판정은 검색 범위 내 결론으로 전수조사가 아니다(R1 Verification).
- **pseudo-RAW**는 실제 센서 노이즈를 완전히 반영하지 못한다 → real RAW(LOD/NOD/AODRaw) 검증은 향후 과제.
- DFX-FP의 RP Pblock 면적·timing, PR latency의 dwell 예산 초과 가능성이 핵심 리스크다([04-implementation-rm-spec] §5).
- **핵심 가정 재검토 필요:** 예비 실측(§5.4)에서 real-low-light mAP는 register-only가 가장 높고 DFX-FP가 가장 낮았다. 따라서 기여 2(feature-preserving 저조도 RM의 mAP 우위)는 현재 데이터로 지지되지 않으며, DFX의 가치를 mAP가 아닌 **자원/전력 절감**으로 재정의하거나 저조도 RM을 denoise 지향으로 재설계하는 방향을 검토한다.
- 정량 결론은 real-RAW·대규모·ZCU104 실측 완료 전까지 유보한다.

### 6.3 향후 연구
- 저조도 RM에 소형 CNN 보정 추가, 다중 RM(날씨/역광), Vitis AI 연계.
- real RAW 벤치마크 확장, PR latency 압축(부분 비트스트림 압축/ICAP DMA).
- scheduler를 RL 기반(AdaptiveISP 연계)으로 확장하되 PR cost를 보상함수에 포함.

---

## 부록/메모
- 확정 설계 결정(2026-06-28): `00-thesis-outline.md`.
- RM 사양·HLS 계획: `04-implementation-rm-spec.md`. 실험 절차·빈 레이아웃: `05-experiment-protocol.md`, `measurements/*.csv`.
- 모든 [TODO:측정]은 실측 전까지 수치 단정 금지.
