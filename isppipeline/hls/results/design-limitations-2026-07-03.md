<!--
=============================================================================
File   : isppipeline/hls/results/design-limitations-2026-07-03.md
Date   : 2026-07-03
Time   : 00:20 KST
Function: 현재 DFXISP 설계(reset 아키텍처, ver1, Stage 1~5 완료 시점)의 한계점을
          알고리즘/SW eval/HW synthesis/DFX 구현/시뮬레이션 5개 층위로 나눠 종합.
Goal   : "지금 설계의 한계점을 분석하고 보고서 작성해" 요청에 대한 응답. 이미
          개별 문서에 흩어져 있던 한계·가정·TODO를 하나로 모아 우선순위와 함께
          정리 — 새 발견보다는 지금까지 쌓인 근거의 종합/구조화가 목적.
=============================================================================
-->
# DFXISP 설계 한계점 종합 보고서 (2026-07-03)

> 이 문서는 새로운 실험이 아니라 **지금까지 Stage 1~5에서 실측·발견한 한계를 5개
> 층위(알고리즘/SW eval/HW synthesis/DFX 구현/시뮬레이션)로 구조화**한 종합
> 보고서다. 각 항목에 원본 근거 문서를 링크한다.

## 요약 (한 줄씩)

| # | 층위 | 한계 | 심각도 |
|---|---|---|---|
| 1 | 알고리즘 | tone RM이 mAP를 개선하지 못함(guardrail 탈락) | **높음** — 방향 A로 이미 우회 |
| 2 | 알고리즘 | low-light RM 손상의 원인이 baseline core의 정적 WB(저조도)/해상도 손실(정상조도)로 조건별 상이 | 높음 |
| 3 | SW eval | pseudo-RAW proxy — 실제 센서 노이즈·real-RAW 없음 | 높음(최종 판정 불가) |
| 4 | SW eval | 표본 크기 작음(n=31~150), 단일/소수 detector | 중간 |
| 5 | HW synthesis | csynth 자원/타이밍은 추정치(post-route WNS는 2026-07-03에 별도 확보 — §3.1) | 낮음(해소됨) |
| 6 | DFX 구현 | fabric-only 특성화 — PS/DDR 미통합, 실제 클럭/리셋 핀 없음 | 높음(보드 전 마지막 gap) |
| 7 | DFX 구현 | pblock 용량이 사실상 클럭 리전 1개분(2개 리전 중 1개가 0.06%만 기여) | 중간 |
| 8 | DFX 구현 | RP 경계가 "전체 모드 파이프라인" 단위 — baseline core가 RM마다 물리적으로 중복 | 중간 (설계 선택, 근본적 한계는 아님) |
| 9 | DFX 구현 | ICAPE3/STARTUPE3가 설계에 전혀 없음 — 실제 PR 컨트롤러 미존재 | **높음** — Stage 6 선결 과제 |
| 10 | 시뮬레이션 | Vivado XSIM으로 ICAP 완료 신호를 격리 환경에서 얻지 못함 | 중간(우회 가능, 대안 있음) |
| 11 | 검증 방법론 | golden model이 실제 버그를 미러링해 bit-exact 테스트가 못 잡은 전례 | 중간(재발 방지책 필요) |

---

## 1. 알고리즘 층위

### 1.1 mAP guardrail 탈락 (근본 한계)
YOLOv8n/s + SSDLite-MobileNetV3, ExDark+COCO 전 조건에서 **`none`(무처리)이 항상
최고**, `normal`/`lowlight` tone RM은 오히려 mAP를 낮춘다(`experiment-report-2026-07-02.md`
§4.3). ver1 개정(gain/gamma 추가)으로 격차를 좁혔지만 역전하지 못함
(`experiment_ver1_2026-07-02.md`). **이 프로젝트는 이 한계를 "방향 A"(mAP 근거가
아니라 자원/전력 근거로 DFX를 정당화)로 우회했지, 해결한 것이 아니다** — 최종
판정은 여전히 보드 DPU + real-RAW 재학습 검출기에서만 가능(SW proxy 천장 가설).

### 1.2 low-light RM 손상 원인이 조도 조건마다 다름
ablation 실측(`lowlight-rm-map-rootcause-2026-07-02.md`) 결과 **단일 원인이 아니다**:
- ExDark(저조도, RM의 목표 조건): 손실의 약 70%가 **두 RM이 공유하는 baseline
  core의 BLC/WB**에서 발생, 해상도 손실은 −1.4%뿐.
- COCO(정상조도, 오적용 시): 반대로 해상도 손실이 지배적(−11.7%), BLC/WB는 −1.9%.

**한계:** 이 발견은 "왜 안 되는지"는 밝혔지만 "어떻게 고칠지"는 아직 실험하지
않았다. 저조도 조건에서 WB를 완화하는 scene-adaptive 설계, Policy B(해상도 보존)
전환 등은 §5의 "다음 실험 후보"로만 남아있다.

### 1.3 checker 임계값의 대상 조건 한정성
`DARK_RATIO=0.80`(ver2 재보정, `experiment_ver2_2026-07-02.md`)은 `data/{coco_val,
exdark_val}` 두 데이터셋의 **분포 스윕으로 얻은 값**이라, 다른 조도 분포(예: 황혼,
실내조명 혼합)에서 일반화된다는 보장이 없다.

---

## 2. SW 평가(proxy) 층위

### 2.1 pseudo-RAW는 진짜 RAW가 아니다
데이터셋은 **이미 ISP된 JPEG을 역변환**한 것(RGGB nearest, shift8)이라 실제 센서의
포화 특성·색 잡음·CFA crosstalk을 반영하지 않는다. §1.2의 "저조도 WB가 색잡음을
증폭시킨다"는 가설은 **정량 검증되지 않았다**(실제 센서 노이즈 없이는 검증 불가) —
`lowlight-rm-map-rootcause-2026-07-02.md` §4.4/§7의 명시적 한계.

### 2.2 표본 크기와 검출기 종류
Stage 3 mAP는 n=71~150(dataset), ablation은 n=31~39로 더 작다 — 통계적 신뢰구간을
계산하지 않았고(단일 point estimate), 절대값이 아니라 **arm 순서**만 판단 근거로
쓴다는 전제가 프로젝트 전체에 깔려 있다. 검출기는 YOLOv8n/s(COCO 사전학습) +
SSDLite-MobileNetV3(torchvision, 다른 사전학습) 3종만 — 실제 목표인 Vitis-AI
`tf_ssdmobilenetv1`(양자화된 DPU 대상 모델)은 가중치 부재로 이 환경에서 실행
불가(`experiment-report-2026-07-02.md` §4.3).

---

## 3. HW C-synthesis 층위

### 3.1 자원/타이밍은 추정치 — WNS gap은 2026-07-03에 해소
Stage 4 수치(LUT/FF/BRAM/DSP, Fmax 273.97MHz)는 **Vitis HLS csynth 추정**이지
post-route 확정치가 아니다(단, Config1/Config2의 routed 자원 수치는 실측 확정치 —
`stage5-dfx-implementation-2026-07-02.md`). csynth의 273.97MHz는 **제약을 걸지 않은
achievable clock**이지, target(200MHz/5.0ns) 제약 하에서의 실제 WNS가 아니었다 —
**이 문서 작성과 동시에 timing-constrained 재구현을 실행해 실측 WNS를 확보**했다
(`dfx-vivado-considerations-2026-07-03.md` §6): Config1(+0.619ns)·Config2(+1.930ns)
모두 200MHz 제약을 만족하며, **두 RM의 post-route 여유가 서로 다르다**(환산 max
Fmax 228.3MHz vs 325.7MHz)는 사실은 csynth 추정만으로는 알 수 없었던 새 정보다.

### 3.2 latency/interval 수치의 대표성
csynth latency(run_normal min 171cyc / run_low_light min 74cyc)는 **파이프라인
depth**이지 실제 프레임 처리 시간이 아니다. §4.4의 프레임 예산 환산(1280×720
기준 ≈3.4ms/0.84ms)은 "II=1이라 cycles≈픽셀수"라는 가정에 기반한 **추정**이며
별도 실행으로 직접 측정한 값이 아니다(`stage4-hw-synthesis-2026-07-02.md` §4.4).

---

## 4. DFX(Vivado) 구현 층위

### 4.1 fabric-only 특성화 — 가장 큰 남은 gap
PS/DDR/AXI interconnect 미통합, 실제 clock/reset 핀 배정 없음(NSTD-1/UCIO-1 DRC를
Warning으로 낮춰 우회), 절대 전력·PR latency 실측·DPU end-to-end 전부 TODO(보드).
**이 프로젝트가 "보드 측정 전단계"라 자평하는 지점이 바로 여기** — Stage 6 하나로
남음.

### 4.2 pblock 용량이 사실상 클럭 리전 1개분
`pblock_capacity.rpt`(2026-07-03 재확인): 2개 클럭 리전(X0Y0:X1Y0)으로 floorplan
했지만 **실제로는 X1Y0이 용량의 99.94%, X0Y0은 0.06%만 기여**한다(Clock Region
Statistics 표). 즉 "2개 리전"이라는 이름과 달리 사실상 1개 리전 분량의 자원만
확보한 셈 — 여유(LUT 8,640/BRAM 12 tile/DSP 96)가 넉넉해 문제가 되지 않았을 뿐,
더 큰 RM을 설계했다면 이 착시가 용량 부족으로 이어질 수 있었다.

### 4.3 RP 경계 선택 — baseline core가 RM마다 물리적으로 중복
SPEC.md의 개념도는 "baseline core(BLC+WB+CCM)는 static, tone RM만 reconfigurable"
처럼 보이지만, **실제 합성된 Stage 5의 RP(`rm_normal_tone_top`/`rm_low_light_tone_top`)
는 데모자이크부터 tone까지 모드별 전체 파이프라인을 통째로 감싼다** — `apply_blc_wb12`
가 소스코드 레벨에서는 공유되지만, HLS가 이 RP 경계를 기준으로 각각 독립 합성하므로
실제 실리콘에는 BLC/WB 로직이 **RM마다 중복 구현**된다(`dfxisp-microarchitecture-2026-07-02.md`
설계 시 발견). 이것 자체가 버그는 아니지만, "baseline core 공유로 자원을 아낀다"는
직관적 기대와 실제 구현 사이의 간극이며, 더 세밀한 RP 분할(baseline core를 진짜
static 모듈로 분리)은 시도되지 않았다.

### 4.4 ICAP/PR 컨트롤러가 설계에 아예 없음
2026-07-03 재확인: config1/config2 어느 쪽 utilization report에도 **`ICAPE3`·
`STARTUPE3` 사용량이 0**이다(`config{1,2}_impl.util.rpt` §8 CONFIGURATION). 즉
지금까지의 "DFX 구현"은 **RP 스왑이 정적으로(pr_verify) 정합함을 증명했을 뿐,
실제로 무엇이 그 스왑을 트리거하고 수행할지(PR 컨트롤러)는 아직 설계되지 않았다.**
Stage 6 이전에 반드시 채워야 할 설계 공백.

---

## 5. 시뮬레이션 방법론 층위

### 5.1 격리된 ICAPE3 시뮬레이션의 한계
2026-07-02 시도(`pr-latency-vivado-sim-2026-07-02.md`): 실제 partial bitstream을
ICAPE3 UNISIM 모델에 흘렸을 때 SYNC는 성공했지만 PRDONE 및 내부 desync_flag
완료 신호를 3가지 독립 방법으로도 얻지 못함 — `eos_startup`이 `STARTUPE3` 기반의
전체 디바이스 시뮬레이션 컨텍스트를 요구하는 것으로 추정. **§4.4와 직접 연결**:
설계에 STARTUPE3가 아예 없으니 이 신호가 격리 환경에서 나올 수 없는 것이 당연했다
— 사후적으로 두 발견이 서로를 설명한다.

### 5.2 cosim(RTL/C 자동 bit-exact 비교) 미완주
Stage 4 §6b: RTL 시뮬레이션 자체는 7/7 성공했지만 자동 post-check 비교 단계가
WSL2+Vitis HLS 2024.1+XSIM 환경 특유의 하네스 문제로 SIGSEGV — "실행 성공 확인,
자동 비교 미완주"로 기록됐고 재시도되지 않았다.

### 5.3 golden model이 실제 버그를 미러링한 전례 (검증 방법론 자체의 맹점)
adversarial review로 발견된 색상손실 버그(`SPEC.md` §11.5)는 **C++ 구현과 Python
golden model이 같은 잘못된 알고리즘을 구현**했기 때문에 `make verify`(bit-exact
교차검증)로는 원리적으로 잡을 수 없었다 — 두 독립 구현이 아니라 사실상 "같은 저자가
같은 실수를 두 번 한" 상황. **재발 방지책이 아직 없다**: 예를 들어 SW eval
파이프라인(`isp_pipeline_ver1.py`)처럼 제3의 독립 구현과 상시 교차검증하는 CI
게이트는 없고, 이번에도 외부 adversarial review가 우연히 잡아낸 것.

---

## 6. 우선순위 제언 (Stage 6 착수 전)

1. **PR 컨트롤러 설계·합성** (§4.4) — ICAPE3/STARTUPE3 인스턴스화, drain 감지,
   partial bitstream 스트리밍 FSM. 이게 없으면 Stage 6에서 "trigger"를 정의할
   방법이 없다.
2. **저조도 baseline core WB 완화 실험** (§1.2) — 이미 원인은 알았으니 다음은 수정.
3. **golden model 교차검증 CI 게이트** (§5.3) — 같은 버그가 SW/HW에 동시에
   재발하지 않도록 제3의 독립 참조(예: 순수 수식 기반 unit test)를 추가.
4. **pblock 재검토** (§4.2) — 더 큰 RM 후보를 고려한다면 "2리전"이 아니라
   실질 용량 기준으로 floorplan을 다시 설계해야 한다.

## 산출물
이 문서는 기존 문서를 종합한 것으로 별도 코드/CSV 산출물 없음. 근거:
`experiment-report-2026-07-02.md`, `lowlight-rm-map-rootcause-2026-07-02.md`,
`stage4-hw-synthesis-2026-07-02.md`, `stage5-dfx-implementation-2026-07-02.md`,
`pr-latency-vivado-sim-2026-07-02.md`, `pblock_capacity.rpt`(2026-07-03 재확인),
`config{1,2}_impl.util.rpt`(§8 CONFIGURATION, 2026-07-03 재확인).
