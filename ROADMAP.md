<!--
=============================================================================
File   : ROADMAP.md
Date   : 2026-07-03
Function: DFXISP 프로젝트 전체 과정을 정본 Stage 구조(Stage 0~6, RESEARCH.md
          및 results/experiment-stages-2026-07-02.md에 정의됨)로 재구성하고,
          각 Stage의 현재 상태를 표시하는 최상위 내비게이션 문서.
Goal   : "ROADMAP.md를 stage1~stage6까지 모두 작성해줘" 요청에 대한 응답.
          이전 버전은 임시 Phase 0~13 번호로 작업 순서를 기록했으나, 이 버전은
          그 내용을 프로젝트의 정본 실험 계획 번호(Stage 0~6)에 재매핑해
          "우리가 실제로 무엇을 계획했고 그중 무엇을 끝냈는가"를 한 축으로
          보여준다. Phase 로그는 부록 A에 원문 그대로 보존.
=============================================================================
-->
# ROADMAP.md — DFXISP 프로젝트 로드맵 (Stage 0~6)

**프로젝트:** DFXISP — Zynq UltraScale+ ZCU104를 위한 Resource-Aware Register/DFX
분할 적응형 ISP (mAP는 register-fast path, 면적·전력은 DFX 부분재구성이 담당)
**대상 보드:** ZCU104, `xczu7ev-ffvc1156-2-e`
**목표:** 석사 학위논문(제주대 전자공학과, 목표 2026.10)
**정본 문서:** 아키텍처 `RESEARCH.md`, 시스템 스펙 `SPEC.md`, Stage 계획
`isppipeline/hls/results/experiment-stages-2026-07-02.md`. 이 문서는 그
계획 대비 진행 상태 추적용.
**마지막 갱신:** 2026-08-04 — **저조도 WB 모드별 분리 기각**(Stage 3 R8): 배포
공유 WB가 저조도에 잘못 맞춰져 있다는 진단은 실측 확인됐으나(SonyNOD 요구 B
게인의 0.50배, 두 조건 간 B 1.84배 차) mAP가 반응하지 않아 분리하지 않는다
(전 범위 spread 0.0020 = BLC 레버의 1/44, 채널 분리 실험이 효과 반증;
`lowlight-wb-mode-split-2026-08-03.md`). 이로써 **모드별 분리 후보였던 색보정
상수 두 개가 모두 "분리 불필요"로 수렴**(BLC 07-20, WB 08-03) — 두 모드의 실질적
차이는 색보정 상수가 아니라 구조(binning, 노출 게인)에 있다. 같은 날 **RP 경계
서술의 문서-구현 불일치 해소**(`SPEC.md` §7·§11.12): 합성된 RP는 tone만이 아니라
모드별 전체 파이프라인을 감싸며 BLC/WB는 소스 레벨에서만 공유된다는 사실
(`design-limitations-2026-07-03.md` §4.3에 있었으나 정본 스펙 미반영이던 것)을
명시. 아래는 2026-07-20 이후 진행 반영: BLC 2/2 + checker C1
반영 csynth/cosim 재실행 완료(자원/타이밍 완전 동일, `blc-c1-csynth-cosim-
rerun-2026-07-20.md`), 그 상수를 반영한 Vivado DFX fabric-only 재구현 완료
(`dfx-reimplementation-2026-08-01.md` — BRAM/DSP/timing/pr_verify/partition
pin/bitstream 크기 전부 07-03 기준과 일치, CLB LUT만 34~37% 감소했으나
08-03 후속 조사로 근본 원인 확정: RM RTL 차이는 BLC 상수에서 유도된 리터럴
6개뿐, 나머지 전부 바이트 단위로 동일 — Vivado 상수 기반 technology
mapping의 정상 거동으로 결론, 추가 조치 불필요), 교차 모델 검증
1단계(YOLOv8s) 노트북 RTX 5060에 인수인계·진행 중
(`HANDOFF-cross-model-yolov8s-2026-08-03.md`). **체커·BLC·DFX 트랙은 이제
보드 없이 할 수 있는 절차가 전부 완료** — 남은 것은 교차 모델 검증 결과
회수·정리(YOLOv8s 진행 중, SSDLite는 별도 인수인계 예정)뿐, Stage 6(보드)만
유일하게 남은 실질 단계. 상세는 Stage 1·3 절의 신규 라운드와 "즉시 다음"의
갱신된 우선순위 참고.

## 상태 범례

| 기호 | 의미 |
|---|---|
| ✅ | 완료 — 실측/실행 완료, 근거 문서 있음 |
| ⚠️ | 완료했으나 알려진 한계·트레이드오프가 있음(정직하게 기록됨) |
| 🔄 | 부분 진행 — 1차 결과 있음, 후속 필요 |
| ⬜ | 미착수 — 대부분 실물 보드가 필요해서 지금 못 함 |

## 트랙 구조 (정본 계획, experiment-stages-2026-07-02.md)

**계획상의 트랙(선형):** 두 트랙이 golden 정합에서 합류한다.

```text
SW 트랙 (data/, model/, tools/)            HW 트랙 (isppipeline/hls, Vivado)
  Stage 0 golden/baseline core 확정   ─┐
  Stage 1 checker + 히스테리시스        │      Stage 4 HLS 합성 + C/RTL Co-sim
  Stage 2 tone RM 산술 + 이미지 지표    ├─(golden 정합에서 합류)─▶ Stage 5 DFX 컨트롤러 + 전환 sim
  Stage 3 정확도(mAP) arm/조건표        ─┘                          Stage 6 보드 실장 + end-to-end
```

## 실제 진행 모델 (나선형 — 이게 현재 상황이다)

**실제 실행은 선형이 아니라 나선형이다.** Stage를 0→5까지 올라간 뒤,
어떤 발견이 나오면 **SW의 Stage 3(정확도 재검증)으로 되돌아와** 알고리즘을
고치고, 그 수정이 다시 HW 재합성(Stage 4/5)으로 전파된다. **Stage 3은
한 번 통과하고 끝나는 관문이 아니라, 새 발견이 들어올 때마다 재진입하는
"정확도 재검증 허브"**다. 지금(2026-07-10)도 이 상태다 — Stage 5까지
올라갔다가 SW로 내려와 checker/ISP 파이프라인을 고치는 중.

```text
   [정본 척추]  Stage 0 → 1 → 2 → 3 ──합류──▶ 4 → 5 → 6(보드)
                                  ▲
                                  │  되먹임(re-validate): SW Stage 3으로 회귀
                                  │
   되먹임 트리거 3종 (실제로 발생한 것):
     ① HW 합성 중 버그 발견        → Stage 0/4 재검증 (binning 스칼라평균 버그, 07-02)
     ② 실센서 RAW 데이터 도착      → Stage 3 R3b 재검증 (SonyNOD, 07-07)
     ③ 병렬 코드리뷰/정합성 감사   → Stage 3 R4·R5 재검증 (Hermes gamma·demosaic, 07-08~09)
```

**함의:** "SW 트랙 완료"는 **절차를 한 바퀴 다 돌렸다**는 뜻이지 **수치가
동결됐다**는 뜻이 아니다. Stage 3의 정성적 결론(`lowlight`가 dark 조건에서
`normal` 상회)은 되먹임을 여러 번 거치며 오히려 **더 견고해졌지만**, 정밀
mAP 수치는 매 되먹임마다 갱신되어 왔고 지금도 R5(demosaic 수정 반영)가
GPU 대기 중이다. HW 트랙(4~5)은 Vivado로 완료됐고 **Stage 6(보드)만 실물
장비가 필요해 유일하게 미착수**지만, 위 되먹임이 알고리즘을 바꿀 때마다
Stage 4 재합성이 원칙적으로 다시 필요할 수 있다(단 지금까지의 SW 수정은
전부 HW 상수 불변이라 재합성 불필요였음 — Stage 4 절 참고).

> **연구 프레이밍 (2026-07-10 갱신, 정본은 RESEARCH.md §1):** 이 로드맵의
> 모든 결론은 두 목표에 종속된다 — **목표 1**(저조도 특화 모듈이 CV에
> 필요; 단일 모듈은 각각 자기 조건 데이터셋에서 최고 → 전환 필요),
> **목표 2**(DFX로 상황별 모듈 전환 → 효율·성능 개선, SW→HW 순 증명).
> 이에 따른 결정 3가지: **(a) `none`(무처리) arm은 비교에서 제외**(색보정
> 안 된 배포 불가 출력 — 아래 R1/R2 기록의 "none 최고"는 **당시 관찰일
> 뿐 기여 비교 대상 아님**). **(b) 정본 평가 데이터셋 = PASCAL RAW(밝음)
> + LOD RAW(저조도)** real-RAW 쌍(§Stage 3, 이전 COCO/ExDark/SonyNOD는
> superseded proxy). **(c) 저조도 모듈의 기술·기대·실측 이득은
> `results/lowlight-module-techniques-2026-07-10.md`에 정본화.**

## 전체 진행률 한눈에

```text
Stage 0  SW golden + shared baseline core 확정        ✅   2026-07-01 ~ 07-03(누적 보강)
Stage 1  checker + N-frame 히스테리시스                ✅+  2026-07-01 ~ 07-20(+principled-v3 C1 권장 → real-RAW 재확인 → C1 배포 → 오라클 라벨 재정의, 4관문 전부 완료)
Stage 2  tone RM 산술 확정 + 이미지 지표               ✅+  2026-07-01 ~ 07-05(+RM 이득원인 정정: binning 제거)
Stage 3  정확도(mAP) 평가 + 알고리즘 개정              ✅+  2026-07-01 ~ 08-03(R1~R4 완료, R5는 R6에 흡수, R6 정본 real-RAW 교차검증 완료, R7 BLC 2/2 배포, R8 WB 모드별 분리 기각)
Stage 4  HLS 합성 + C/RTL Co-sim                       ✅⚠️ 2026-07-02 ~ 07-03(3라운드; cosim 자동비교 미완주; BLC/C1 반영 재합성은 open item)
Stage 5  DFX(PR) 구현 + pr_verify + latency/PR 컨트롤러 ✅⚠️🔄 2026-07-02 ~ 07-03(4라운드; PR컨트롤러 1차만)
Stage 6  보드 실장 + DPU end-to-end                    ⬜   미착수(실물 보드 필요 — 유일하게 시작조차 못한 단계)

범례: ✅ 완료 · ✅+ 완료 후 후속 개정 있었음 · 🔄 재진입/진행중 · ⚠️ 알려진 한계 · ⬜ 미착수
```

**한 줄로:** 척추(0→5)는 다 올라갔고, Stage 1·3의 나선(SW 재검증)도
2026-07-20에 한 바퀴 완주했다(real-RAW 교차검증 + BLC/checker 재보정·배포 +
오라클 라벨까지) — **보드 없이 할 수 있는 절차는 이제 전부 완료**. 남은
비-보드 작업은 csynth/cosim 재실행(BLC/C1 상수 변경분, 형식 확인)과 교차
모델 검증(부차 발견의 견고성 확인)뿐이고, 보드가 필요한 Stage 6만 유일하게
남은 실질 단계다.

## 트랙별 세부 진행 표 (Stage + 라운드 단위)

아래 표는 계획 Stage를 실제 실행된 라운드(round) 단위로 펼친 것이다.
**"되먹임" 열은 그 행이 왜 생겼는가** — 처음 계획대로 나온 행인지(계획),
아니면 위 나선 모델의 트리거 ①/②/③ 중 무엇 때문에 SW로 되돌아온
재검증 행인지 — 를 표시한다. 각 행의 근거 문서는 해당 Stage 절의
"근거:" 목록 참조.

| 트랙 | Stage·순서 | 내용 | 되먹임 | 상태 | 최종 작업일 |
|---|---|---|---|---|---|
| SW | Stage 0 | golden(Python) ↔ C-sim(C++) bit-exact 확정, 아키텍처 gate 6종 + 독립 교차검증 게이트(binning fuzz 500회) | 계획 | ✅ 완료 | 07-03 |
| SW | Stage 1 | dark-ratio checker + N-frame 히스테리시스, 스케줄러 스윕(narrow+N=3), 임계값 재보정(0.40→0.80) | 계획 | ✅ 완료 | 07-02 |
| SW | Stage 1 후속 | principled-v3: 체커 5원리 정본화 + C0~C4 비교, C1(dark16>0.62) 권장 | 트리거③(감사) | ✅ 완료(권장; 당시 배포 보류) | 07-05 |
| SW | Stage 1 후속 · 관문4 | R6/R7 실측 근거로 **C1 정식 배포**(구 C0 dark50>0.80 폐기) — HW `DARK_RATIO_PCT` 80→62, `checker.py`를 raw 도메인 직접비교로 전환(구 luminance 근사 제거), 실 RAW 642장 대조 판정 불일치 0 | R6에서 전파 | ✅ 완료 | 07-20 |
| SW | Stage 1 후속 · 관문2 | **오라클 라벨 재정의(강화안 #4, 마지막 관문)** — Shuffle_split 642장 dual-arm 렌더+YOLOv8n 프레임별 F1 델타로 프레임별 정답 재정의. C1 잔존오차의 89.6%가 라벨 아티팩트(진짜 오류 10.4%), dark16 판별력은 naive-라벨 J 0.847→오라클 J 0.008로 붕괴하나 C1 임계의 비용-중립점(C_miss≈C_FA)은 오라클 기준에서도 유지 → **C1 재조정 불필요** 결론 | 계획(강화안 §4 최우선) | ✅ 완료 | 07-20 |
| SW | Stage 1 후속 · adaptive-τ | adaptive-τ(Path A) 개선 실험 3종(Codex) — 센서별 τ8 피팅은 sensor/label confounding 누설로 기각, tau_floor-only가 최선 비누설 변형이나 ISO[800,1600) 역전 못 고침, 공동보정은 표본부족으로 악화 — **정직한 부정적 결과**, Path-A를 C1 대신 배포할 근거 없음 확정 | 트리거③(재검토) | ✅ 완료(부정적 결과, adaptive-τ는 실험코드로만 유지) | 07-20 |
| SW | Stage 2 | tone RM 산술 확정(Policy A), arm별 이미지 지표, gain·gamma 중복없음 | 계획 | ✅ 완료 | 07-02 |
| SW | Stage 2 정정 | RM 저조도 이득 원인 규명 — 톤커브 아님, binning 제거(해상도)가 지배. 권장 arm `F_g20` | 트리거③(감사) | ✅ 완료(1차 서사 정정) | 07-05 |
| SW | Stage 3 · R1 | 최초 조건표 A~G, 3-detector 교차검증 → 전 조건 `none` 최고, guardrail 최초 탈락 | 계획 | ✅ 완료 | 07-02 |
| SW | Stage 3 · R2 | ver1(RAW-domain-first) + ver2(checker 재보정) 개정 → 개선됐으나 여전히 `none` 최고 | 계획(R1 되짚기) | ✅ 완료 | 07-02 |
| SW | Stage 3 · R3 | 저조도 root-cause(BLC=손실 70%) + BLC 완화 반영 → ExDark lowlight +78%, 최초로 normal 상회 | 계획(R2 되짚기) | ✅ 완료 | 07-03 |
| SW | Stage 3 · R3b | SonyNOD 실센서 RAW(321장) BLC ablation → 역전이 실센서에서도 재현 | **트리거②(실데이터)** | ✅ 완료 | 07-07 |
| SW | Stage 3 · R4 | canonical 파이프라인 재보정(Hermes가 발견한 SW/HW gamma 불일치 수정) → 결론 유지, 마진 +76%→+12.6%, "normal 단조감소" 정정 | **트리거③(감사)** | ✅ 완료(수치 재검증) | 07-08 |
| SW | Stage 3 · R5 | demosaic R/B bilinear 수정(PR #9) 반영 mAP 재실행 | **트리거③(감사)** | ✅ 완료 — R6(canonical 파이프라인이 이미 이 수정을 포함) 실행분으로 흡수, 별도 라운드 불필요 | 07-16 |
| SW | Stage 3 · R6 | **정본 real-RAW 교차검증(§10.2 요구 이행)** — LOD_split(SonyNOD 321)/PASCAL_split(PASCALRAW ISO층화 321)/Shuffle_split(642) × normal/lowlight/adaptive × BLC{16,1,2} 27조합 mAP(YOLOv8n). 핵심: BLC 재보정이 checker/adaptive보다 훨씬 큰 mAP 레버(최대 5.7배); LOD에서 adaptive≈lowlight; Shuffle에서 "adaptive가 둘 다 이김" 기준은 BLC=2에서만 근소 충족 | **트리거②(실데이터, PASCALRAW 도착)** | ✅ 완료(노트북 RTX 5060, 6h50m) | 07-15~16 |
| SW | Stage 3 · R7 | R6 실측 근거로 **BLC 재보정 배포**: normal 16→2, low-light 8→2(단일값, 모드별 완화 폐기) — HW golden 재생성, `make verify`/`rm-verify` bit-exact 통과 | R6에서 전파 | ✅ 완료 | 07-20 |
| SW | Stage 3 · R8 | **저조도 WB 모드별 분리 검토 → 기각.** 07-03 분리 ablation이 pseudo-RAW(이미 카메라 AWB됨)·BLC=16 클리핑이라는 두 결함 위에서 측정됐다는 문제 제기로 실 RAW 재검증(SonyNOD 321, BLC=2, 후보 6종). **진단은 확인**(배포 WB는 PASCAL 요구값의 0.92배지만 SonyNOD 요구값의 0.50배, 두 조건 간 B 1.84배 차) **그러나 mAP 무반응**(전 범위 spread 0.0020 = BLC 레버의 1/44; 채널 분리에서 R만 −0.05%/B만 −0.19%/둘 다 +0.61% = 초가산 = jitter). **HW 상수 불변, 재합성 불필요.** 부수 성과: `design-limitations` §1.4의 포화율 공백 해소(최대 2.13%) | **트리거③(아키텍처 검토)** — normal/low-light 독립 모듈화 제안의 하위 질문 | ✅ 완료(기각) | 08-03 |
| HW | Stage 4 · R1 | 최초 실합성(streaming line buffer 리팩터, gamma Newton→ROM LUT), unified+RM독립 top 2종 Fmax 273.97MHz | 계획 | ✅⚠️ 완료(cosim 자동비교 미완주) | 07-02 |
| HW | Stage 4 · R2 | adversarial 수정(binning 스칼라평균 버그, 메타데이터 포인터) 재합성 → LUT −26.3%/−41.3% | **트리거①(HW감사)** | ✅ 완료 | 07-02 |
| HW | Stage 4 · R3 | BLC 완화 반영 재합성 → 3개 top 자원 완전 불변(순수 파라미터 변경) | R3(SW)에서 전파 | ✅ 완료 | 07-03 |
| HW | Stage 5 · R1 | 최초 DFX 구현(config1/config2), 트러블슈팅 5건 해결, pr_verify PASS | 계획 | ✅ 완료 | 07-02 |
| HW | Stage 5 · R2 | adversarial 수정 반영 재구현 → pr_verify PASS, partition pin 2→15 | **트리거①(HW감사)** | ✅ 완료 | 07-02 |
| HW | Stage 5 · R3 | latency 실측 시도(한계) + pblock 편중 원인규명 + PR 컨트롤러 1차 FSM(word-count) + pblock 재floorplan(용량 2배) | 계획(심화) | ✅⚠️🔄 완료(latency 한계, 컨트롤러 1차만) | 07-02~03 |
| HW | Stage 5 · R4 | BLC fix + pblock 확장 결합 최종 재구현 → pr_verify PASS, partial bitstream 2.11배↑(트레이드오프 기록) | R3(SW)에서 전파 | ✅ 완료 | 07-03 |
| HW | Stage 6 · 1 | PS/DDR 통합(Block Design), GIC+DMA+PR 루프 드라이버(PR컨트롤러 1차 완성이 선결) | 계획 | ⬜ 미착수 | — (보드) |
| HW | Stage 6 · 2 | 실제 clock/reset 핀 배정 + 타이밍 제약(신 pblock WNS 재검증) | 계획 | ⬜ 미착수 | — (보드) |
| HW | Stage 6 · 3 | 실제 PR latency 실측(trigger→완료, ICAP 대역폭, XSA+JTAG+ILA) | 계획 | ⬜ 미착수 | — (보드) |
| HW | Stage 6 · 4 | 절대 전력(W) 측정, Arm1/2/3 비교 | 계획 | ⬜ 미착수 | — (보드) |
| HW | Stage 6 · 5 | DPU/검출기 end-to-end(Vitis-AI, real-RAW, RGB32 직결) | 계획 | ⬜ 미착수 | — (보드) |
| HW | Stage 6 · 6 | Stage 3 BLC 완화가 real-RAW에서도 유효한지 최종 확인(DPU mAP vs SW 예측 정합) | 계획 | ⬜ 미착수 | — (보드) |
| SW | Stage 3 후속(SOTA) | checker SOTA 강화 7항목 판정 완료(#1·#6 채택 / #2·#3·#5 기각 / #4·#7 대기) + AODRaw/LOD 어댑터. 종합=`checker-status-2026-07-10.md` | 트리거③(감사) | ✅ 판정완료(배포는 LOD 대기) | 07-10 |
| SW | Stage 3 후속(SOTA) · 관문1~4 마감 | `checker-status-2026-07-10.md` §4의 4개 관문(LOD real-RAW 확보 / 오라클 라벨 / 적응τ 스트라텀 검증 / C1·τ 정식 배포) **전부 완료** — 위 R6/R7·관문2·관문4·adaptive-τ 행이 각 관문의 실행 기록. 종합 갱신은 같은 문서(`checker-status-2026-07-10.md`) §4에 in-place 반영 | 계획(§4 로드맵) | ✅ 4/4 완료 | 07-20 |
| 거버넌스 | — | "Hermes" 병렬 리뷰 → Python robustness 수정(경계 문서화, edge-clamp demosaic 버그) | 트리거③ 원천 | ✅ 완료(PR #6) | 07-08 |
| 거버넌스 | — | PR #3(references) 브랜치 삭제로 자동 종료 → 리베이스 후 PR #5로 복구, 데이터 유실 없음 | 프로세스 | ✅ 완료 | 07-08 |

> **표 밖 참고 — 브랜치 상태(2026-07-10, 통합 완료):** 모든 작업이 단일
> 브랜치 `exp/principled-checker-rm-2026-07-05`로 통합됐다 — main을 병합해
> canonical 파이프라인을 유입(behind 0)하고, demosaic 수정(구 PR #9)까지
> 접어 넣었다. stale 병합 브랜치 5개(docs/checker-theory·docs/daily-report·
> exp/isp-recalibration·fix/python-robustness·sw-stage-rm-variants) 삭제.
> 보존: `main`, 이 통합 브랜치, `backup/local-work-*` 2개(의도적 백업).
> 이 브랜치를 `main`으로 올리는 최종 통합은 리뷰 후 진행한다.

---

## Stage 0 — SW golden & shared baseline core 확정 ✅

**목표:** shared baseline core(demosaic + BLC + AWB + CCM, **gain/gamma 없음**)와
tone RM slot(RM_NORMAL_TONE identity / RM_LOW_LIGHT_TONE = 2x2 bin + gain +
gamma-4.0)의 결정적 golden 모델을 확정하고, C-sim이 이를 bit-exact 재현함을 증명.

- `tools/gen_golden_vectors.py`(Python 기준) ↔ `src/dfxisp_accel.cpp`(C++) 정수
  산술 미러. Policy A(저조도 H/2×W/2). gamma-4.0 = 정수 4제곱근.
- 아키텍처 gate 6종 PASS: baseline core / RM_NORMAL_TONE / RM_LOW_LIGHT_TONE /
  상호배타 / gain·gamma 중복없음 / 형상정책.
- `make verify` bit-exact 유지: 초기 566px → adversarial 수정 후 646px(Finding
  1/2 반영, 아래 Stage 4/5) → BLC 완화(Stage 3 최종 라운드) 반영 후에도 계속 bit-exact.
- **신규 검증 인프라(2026-07-03):** golden model 독립 교차검증 게이트
  (`tools/verify_binning_cross_check.py`, RGGB 500회 fuzz, `make verify`의
  `cross-check` target에 통합) — 과거 스칼라-평균 binning 버그를 재현했을 때
  실제로 잡아냄을 확인, `make verify` 자체의 맹점(golden과 C++가 같은 버그를
  미러링하면 bit-exact가 못 잡는 문제)을 구조적으로 보완.

**근거:** `RESEARCH.md` §0, `tests/golden_vectors.csv`, `reports/latest.md`,
`isppipeline/hls/results/experiment-stages-2026-07-02.md`.

---

## Stage 1 — 환경 감지 checker + 히스테리시스 시퀀스 ✅

**목표:** dark-ratio 기반 mode 결정 + N-frame 히스테리시스로 flicker 없는
장면 단위 전환을 SW 시뮬레이션으로 검증(RESEARCH §5).

- checker: `Y=(R+2G+B)/4` 기반 dark-pixel 비율, `dark_ratio = count(<thr)/N`.
- 스케줄러 파라미터 스윕(narrow/wide band × temporal_N) — **narrow 밴드 +
  temporal_N=3**이 최적: mismatch 0.015, thrashing 0(기본값 대비 9배 개선).
- 전환 임계값 재보정(Stage 3 ver2와 연동): `NORMAL→LOW_LIGHT: dark_ratio>0.80`
  (Youden's J 스윕, 구 0.40에서 재보정 — COCO 과트리거 79.5%→11%).

**근거:** `isppipeline/hls/results/stage1-3-results-2026-07-02.md`.

**후속(2026-07-04~05, principled-v3, 브랜치 `exp/principled-checker-rm-2026-07-05`,
PR #4로 2026-07-08 main 병합):** checker를 결정이론·광도계·노이즈물리·표본론·
시간축 5개 원리로 정본화하고 후보 C0(현행 dark50>0.80) ~ C4(2-feature)를
1,150프레임(COCO+ExDark) 전수로 비교. **C1(dark16>0.62, 히스테리시스
δ=2%p) 채택 권장** — 전 지표에서 C0 지배 + HW 변경 0. **단, 이 권장은 아직
배포되지 않았다**: `src/dfxisp_accel.cpp`의 `DARK_RATIO_PCT`는 여전히 80
(dark50 기준)이며, 실센서 재보정(τ(s,g) 적응) 및 오라클 라벨 재검증을
선결 조건으로 남겨둔 상태다(2026-07-09 진행 중, 아래 "체커 SOTA 강화" 참고).
**근거:** `results/checker-principles-2026-07-05.md`,
`results/checker-principled-versions-2026-07-05.md`.

---

## Stage 2 — tone RM 산술 확정 + 이미지 지표 ✅

**목표:** RM_LOW_LIGHT_TONE(2x2 binning + gain×1.25 + gamma-4.0)과
RM_NORMAL_TONE(identity/옵션 gain·γ)의 파라미터를 이미지 지표로 확정.

- Policy A(H/2×W/2 그대로, upsample 없음) 채택 — DPU ABI 요구 시에만 Policy B 검토.
- arm별(none/normal/lowlight/adaptive) Y mean·std·포화율·dark-ratio 집계,
  gain/gamma 중복 플래그 항상 false(baseline core 무침범) 확인.

**근거:** `isppipeline/hls/results/stage1-3-results-2026-07-02.md`.

**정정(2026-07-05, principled-v3 refinement, 위와 동일 PR #4로 병합):**
1차 서사("저조도 RM 이득은 VST 톤커브 덕분")가 **베이스라인 혼입 오류**로
판명됐다 — 1차 비교 대상이 실제 배포된 sqrt/gamma-2.0이 아니라 약한
gamma-2.5였다. 정정된 결론: **저조도 RM의 유의미한 이득은 톤커브가 아니라
2x2 binning 제거(해상도 보존)에서 온다** — COCO AP_small 0.0495→0.1958
(+296%, 소형 객체 회복이 지배 메커니즘). 권장 arm이 `F_g20`(binning만
제거한 full-res+sqrt)으로 변경됨. **근거:**
`results/principled-v3-refinement-2026-07-05.md`.

---

## Stage 3 — 정확도(mAP) 평가: arm & 조건표 + 알고리즘 개정 ✅+ (7라운드, 2026-07-20 완료)

> **상태(2026-07-20 갱신):** 비교 arm은 normal/lowlight/adaptive다(`none` 제외 —
> 상단 프레이밍 노트). 목표 1 관점의 결론(**저조도 모듈이 dark 조건에서
> `normal` 상회**)은 R1~R7 전 라운드에서 안정적으로 재확인됐다. §10.2가
> 요구한 **정본 데이터셋(PASCAL RAW/LOD RAW) real-RAW 교차검증도 R6에서
> 완료**됐고(demosaic 수정은 R6 실행분에 이미 포함돼 있어 R5가 별도로
> 필요 없어짐), 그 실측 근거로 R7에서 BLC 재보정(16/8→2/2)이 배포됐다.
> "완료"는 여전히 "보드 없이 할 수 있는 절차를 다 돌렸다"는 뜻이지만,
> 이제 Stage 3의 정성적 결론과 배포 파라미터가 **둘 다 real-RAW 실측
> 기준으로 동결**됐다는 점이 R4까지와 다르다.

**목표:** H1(적응 이득)·H2(중복제거해도 정확도 유지)를 조건별 mAP로 검증하고,
탈락 시 원인을 규명해 알고리즘을 개정.

**라운드 1 — 최초 조건표 A~G (2026-07-01~02):** 3-detector(YOLOv8n/s +
SSDLite-MNv3) 교차검증. **모든 조건에서 `none`(무처리)이 최고**, `normal`/
`lowlight`가 오히려 mAP를 낮춤 — guardrail 최초 탈락 확인.

**라운드 2 — ver1/ver2 개정 (2026-07-02):**
- ver1(RAW-domain-first): 보정을 demosaic 전 RAW 도메인에서 수행, normal에도
  exposure gain 추가. ExDark normal mAP +17~21%, lowlight도 개선 — 그러나
  **여전히 `none`이 최고**(SW proxy 천장 가설, guardrail 결론 유지).
- ver2: checker 재보정(Stage 1과 연동, 0.40→0.80).

**라운드 3 — 저조도 root-cause 규명 + BLC 완화 반영 (2026-07-03):**
- 5단계 ablation으로 기존 "해상도 손실" 가설을 반증: **ExDark(저조도)에서는
  BLC(공유 core)가 mAP 손실의 70%**, 해상도 손실은 −1.4%뿐. COCO(정상조도)는
  반대로 해상도 손실이 지배적 — **원인이 조도 조건별로 정반대**라는 핵심 발견.
- BLC vs WB 분리 ablation: **BLC가 진짜 승자**(WB 아님) — BLC 완화 단독으로
  ExDark ablation 기준 +141%, WB 관련 변형은 +7%/−0.5%에 그침.
- **정본 반영:** `apply_blc_wb12()`를 파라미터화, low-light만
  `BLC_OFFSET12_LOWLIGHT=128`(정상 256의 절반) 적용. C++/golden/SW eval
  3파일 동기화, `make verify` + cross-check 게이트 통과.
- **최종 mAP(표준 표본 n=71/80):** ExDark lowlight 0.0586→**0.1043**(+78%,
  **처음으로 normal(0.0826)을 상회**), COCO lowlight 0.2647→**0.2857**(+8%, 무해).
  `none`은 여전히 최고(SW proxy 천장 가설 불변, guardrail 결론 유지)이나
  격차가 크게 좁혀짐.

**근거:** `results/stage1-3-results-2026-07-02.md`,
`results/experiment_ver{1,2}-2026-07-02.md`,
`results/lowlight-rm-map-rootcause-2026-07-02.md`,
`results/phase0-2-execution-2026-07-03.md`,
`results/blc-fix-resynthesis-2026-07-03.md`.

**라운드 3b — SonyNOD 실센서 RAW로 BLC 재보정 ablation (2026-07-07):**
지금까지의 BLC 결론은 전부 합성 pseudo-RAW(COCO/ExDark 역감마) 기준이었다.
**진짜 카메라 RAW(Sony RX100 VII, 321장)**로 같은 BLC 스윕을 처음 실행 —
`lowlight/adaptive > normal` 역전이 **모든 BLC 값에서 재현**됨을 확인,
Stage 3 R3 결론이 합성 데이터의 인공물이 아니라 실센서에서도 성립함을
독립 검증. **근거:** `results/realraw-sonynod-benchmark-2026-07-06.md` §6ter.

**라운드 4 — canonical-matched 파이프라인 재보정 (2026-07-08, PR #8):**
후속 코드 리뷰("Hermes" 병렬 검토)에서 R1~R3와 R3b의 mAP 계산에 쓰인
SW-eval 도구(`newrm_pipeline*.py`, `isp_pipeline_ver1.py` 등)가 **실제
배포 HW의 gamma 곡선과 어긋나 있었음**이 드러났다(HW는 공유 `GAMMA2_LUT`
sqrt/감마-2.0인데, SW eval은 파일마다 2.2/2.5/4.0/무감마를 혼용). 18개
구 도구를 `tools/archive/`로 옮기고, HW 상수를 그대로 미러링하는 3종
canonical 파일(`baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`/
`checker.py`) + `eval_map_isp.py`를 신설, R3b의 SonyNOD 스윕을 재실행:
- **정성적 결론 유지:** `lowlight/adaptive > normal` 역전은 BLC 0~16 전
  구간에서 그대로 성립(이중으로 견고해짐).
- **정량 마진은 축소:** BLC=2에서 역전폭이 +76%→**+12.6%**로 줄었다 —
  구 마진의 상당 부분이 잘못된 gamma 곡선의 인공물이었음이 밝혀짐.
- **부차 결론 정정:** "`normal`은 BLC에 대해 무조건 단조감소"라는 R3의
  주장이 철회됨 — 올바른 gamma에서는 `normal`도 BLC≈1에서 약한 정점을
  찍는 비단조 곡선.
- **정정(2026-07-09, 검토 후 수정 확정, PR #9
  `fix/canonical-demosaic-bilinear-2026-07-09`, main 기준 분기 —
  `origin/main`에만 있는 canonical 파일 대상이라 이 브랜치와 별도):**
  위 미결 항목("canonical `checker.py`/`baseline_isp_pipeline.py`의 R/B
  채널 단일탭 보간이 golden model의 bilinear와 다르다")을 검토한 결과
  **수정하기로 판단** — BLC/체커 임계값과 달리 이건 설계 트레이드오프가
  아니라 이미 정답(golden/`dfxisp_accel.cpp`)이 있는데 잘못 베낀 버그였다.
  `_demosaic_rggb16`을 tap 단위로 golden과 동일하게 재작성하고, 신규 3자
  교차검증 게이트(`verify_demosaic_bilinear_cross_check.py`)로 300회
  랜덤 그리드 bit-exact 확인, 수정 전 코드가 실제로 이 검증에 실패함도
  회귀 확인(`results/demosaic-bilinear-fix-2026-07-09.md`). SonyNOD
  8프레임 픽셀 단위 사전측정: 평균 변화 0.377/255(8-bit 환산), 34.5%
  픽셀·채널 값 이동, 에지에 집중 — 정성적 결론 반전 가능성은 낮으나 정밀
  mAP는 다시 움직일 것으로 예상. **mAP 재검증은 GPU 필요(이 세션은
  CUDA 불가)라 별도 R5 라운드로 미룸.** 코드 수정은 통합 브랜치에 반영
  완료(구 PR #9를 접어 넣음), mAP 재실행만 GPU 대기.
- **범위:** 이 재보정은 SW 평가 도구만 바꿨다 — Stage 4/5의 HLS/Vivado
  수치는 재합성 대상이 아니며(알고리즘 상수 자체는 불변), Stage 3의
  R1~R3·R3b **정성적 결론은 재확인**됐으나 그 **정밀 mAP 수치는 canonical
  파이프라인 기준으로 대체(superseded)**된 것으로 취급한다.

**근거:** `results/isp-pipeline-recalibration-2026-07-08.md`,
`daily-reports/2026-07-08.md`, PR #6(`fix/python-robustness-hermes-2026-07-08`).

**라운드 5 — demosaic bilinear 수정 반영 mAP 재검증 ✅ 완료(R6에 흡수):**
PR #9(위 R4 절의 2026-07-09 정정)가 canonical `_demosaic_rggb16`의 R/B
단일탭 버그를 고쳤다. 코드 수정과 bit-exact 교차검증은 07-09에 완료됐고
(`results/demosaic-bilinear-fix-2026-07-09.md`), 이 수정을 반영한 mAP
재실행은 별도 라운드로 하지 않고 **R6(아래, PASCALRAW 도착 후 canonical
파이프라인으로 실행)에 자연스럽게 포함**됐다 — R6이 쓰는
`baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`/`checker.py`는
이미 수정된 demosaic을 담고 있다.

**근거:** `results/demosaic-bilinear-fix-2026-07-09.md`.

**라운드 6 — 정본 real-RAW 교차검증: LOD/PASCAL/Shuffle_split (2026-07-15~16,
노트북 RTX 5060):** §10.2가 요구한 정본 평가를 처음 실행했다. PASCALRAW
도착(07-14, 4,259장 Nikon `.NEF`, 100% 주간)으로 LOD_split(SonyNOD 전량
321)과 크기 매칭한 PASCAL_split(ISO층화 샘플 321)·Shuffle_split(합쳐서
셔플 642)을 구성, normal/lowlight/adaptive arm × BLC{16,1,2} = 27조합
mAP(YOLOv8n)를 전수 실측했다. 실행 중 `eval_map_isp.py`의 "adaptive" arm이
채택된 adaptive-τ가 아니라 배포 C0를 측정하던 버그를 발견·수정(`--manifest`
인자 추가)하고 재실행했다.

- **핵심 발견 1(이 캠페인의 최대 레버):** BLC 재보정(16→1/2)이 checker/adaptive
  선택보다 훨씬 큰 mAP 효과 — LOD 최대 5.7배, PASCAL +35%, Shuffle 최대
  2.2배. 2026-07-08 recalibration(`isp-pipeline-recalibration-2026-07-08.md`)의
  결론을 **처음으로 real 센서 RAW(LOD+PASCAL)로 재확인**.
- **핵심 발견 2:** LOD(야간)에서 adaptive≈lowlight(모든 BLC에서 ±0.0001) —
  §1.3 알고리즘 주장과 정합.
- **핵심 발견 3:** Shuffle(혼합)에서 "adaptive가 normal·lowlight 둘 다
  이겨야 pass"라는 목표 2 통과 기준은 **BLC=2에서만, 근소하게(+0.0002)**
  충족 — "확실한 승리"로 과장하지 않음(정직한 기록 원칙 유지).
- **부수 발견:** lowlight arm이 100% 주간인 PASCAL에서도 9/9 BLC×비교
  조합 전부 normal과 같거나 우위 — 단일 모델·단일 run이라 확대해석 금지,
  교차 모델 검증 필요(§4 관문 항목, 아직 open).

**근거:** `results/HANDOFF-lod-pascal-isp-simulation-2026-07-15.md`(인수인계),
`results/lod-pascal-isp-simulation-2026-07-15.md`(정본 결과+버그 수정 기록).

**라운드 7 — BLC 재보정 배포 (2026-07-20):** R6 실측(BLC 1~2가 전 split·전
arm에서 정점)을 근거로 배포 상수를 변경 — `BLC_OFFSET12`(normal) 16→2,
`BLC_OFFSET12_LOWLIGHT` 8→2(모드별 완화 폐기, 단일값 2로 통일 — 1/2 혼합은
측정된 적 없음). `src/dfxisp_accel.cpp` + SW 미러 3파일 동기화, HW golden
재생성, `make verify`/`rm-verify` bit-exact 전부 통과, 새 기본값이 스윕의
`blc_offset=2` 출력과 bit-exact 동일 확인.

**근거:** `results/blc-recalibration-deploy-2026-07-20.md`. **남은 것:**
csynth/cosim 재실행(비트스트림 배포 전, 상수만 변경이라 자원 영향 없음
예상 — 아직 미실행).

---

## Stage 4 — HLS 합성 + C/RTL Co-sim ✅⚠️ (3라운드)

**목표:** baseline core / RM_NORMAL_TONE / RM_LOW_LIGHT_TONE 각각의 합성
자원·타이밍을 확보하고, 합성 RTL이 golden을 bit-exact 재현함을 co-sim으로 증명.

**라운드 1 — 최초 실합성 (2026-07-02):** streaming line buffer 리팩터(4MB
scratch → O(3×960) BRAM), gamma를 런타임 Newton's-method isqrt에서 256-entry
ROM LUT로 교체(FF −88%, LUT −78%). unified top(`dfxisp_accel`) + RM 독립 top
2종 모두 실측: **Fmax 273.97MHz**(5.0ns 타깃 충족, 수정 불필요).
C/RTL Co-sim: RTL 실행 7/7 성공(긍정 신호)했으나 자동 bit-exact 비교 단계가
WSL2+XSIM 하네스 문제로 SIGSEGV — **⚠️ 자동 비교 미완주**(수동 확인으로 대체).

**라운드 2 — adversarial 수정 반영 재합성 (2026-07-02):** 저조도 binning의
스칼라-평균 후 재-demosaic 버그(색 정보 파괴) + 메타데이터 미검증 포인터를
수정 후 재합성 — unified top LUT −26.3%, low-light RM LUT −41.3%(버그였던
2차 demosaic 로직 제거 효과).

**라운드 3 — BLC 완화 반영 재합성 (2026-07-03):** 3개 top **자원 완전 불변**
(상수 하나만 바뀐 순수 파라미터 변경 — Stage 3의 mAP 개선이 HW 비용 없이
달성됨을 의미).

| top | LUT | FF | BRAM | DSP | Fmax |
|---|---:|---:|---:|---:|---:|
| `dfxisp_accel`(unified) | 8,264 | 5,536 | 9 | 24 | 273.97MHz |
| `rm_normal_tone_top` | 5,202 | 3,797 | 4 | 12 | 273.97MHz |
| `rm_low_light_tone_top` | 4,204 | 3,243 | 8 | 9 | 273.97MHz |

**근거:** `results/stage4-hw-synthesis-2026-07-02.md`,
`SPEC.md` §11.5(커밋 `a2d1b6d`), `results/blc-fix-resynthesis-2026-07-03.md`.

---

## Stage 5 — DFX(PR) 구현 + pr_verify + latency/PR 컨트롤러 ✅⚠️🔄 (4라운드)

**목표(당시 v1 서술):** static region(checker·baseline core·컨트롤러)과 tone RM
slot(재구성)을 분리하고, checker 트리거 → drain → PR 적재 → RM swap의 무손실
전환을 검증. **정정(2026-08-04, `SPEC.md` §7 "RP 경계"):** 실제 합성된 RP는
baseline core를 포함한 모드별 전체 파이프라인이었다 — "static+baseline core
공유"는 처음부터 실리콘에 존재한 적이 없다. 아래 라운드 기록은 원문 그대로
보존한다(구현 이력이므로).

**라운드 1 — 최초 구현 (2026-07-02):** AMD UG909 표준 절차(non-project batch
Tcl), config1(static+NORMAL)/config2(static+LOW_LIGHT, black-box+lock 방법론)
구현. 트러블슈팅 5건 실전 해결(I/O 핀 초과, RP 인스턴스 삭제, SNAPPING_MODE
빈 pblock, static 배치 불일치, DRC 우회). **pr_verify PASS**, full 19.3MB /
partial 686,664B(구 pblock X0Y0:X1Y0).

**라운드 2 — adversarial 수정 반영 재구현 (2026-07-02):** **pr_verify PASS
유지**, partition pin **2개→15개**로 증가(메타데이터 수정이 post-route
물리 계층에도 실제 반영된 직접 증거). bitstream 크기는 byte 단위로 불변
(로직 감소와 무관 — partial 크기는 pblock 프레임 수로 결정됨을 재확인).

**라운드 3 — 시뮬레이션/한계 조사 + 개선 (2026-07-02~03):**
- **Vivado 시뮬레이션 latency 실측 시도 ⚠️:** 실제 partial bitstream을 ICAPE3
  UNISIM 모델에 스트리밍하는 테스트벤치 제작, 3가지 독립 방법(PRDONE 신호,
  DESYNC 바이트패턴, `desync_flag` 전이)으로도 완료 신호를 못 얻음. 원인:
  `PRDONE`이 `STARTUPE3` 인프라(`eos_startup`)에 의존하는데 격리 테스트벤치엔
  없음 — 다음날 `report_utilization`이 실제 설계에 ICAPE3/STARTUPE3가 0개임을
  보여 이 한계를 독립적으로 재확인. 헛수고는 아니었음 — 이 실패가 아래 PR
  컨트롤러의 word-count 기반 설계를 직접 유도.
- **pblock 클럭리전 편중 원인 규명:** X0 컬럼(Y0~Y3)이 PS 하드매크로에 점유돼
  SLICE 0개, 실제 기여는 X1 컬럼 99.94%뿐임을 확정. timing 제약 적용 후 실측
  WNS: config1 +0.619ns(Fmax≈228.3MHz), config2 +1.930ns(Fmax≈325.7MHz) —
  둘 다 200MHz 타깃 충족. **(주의: 이 WNS는 구 pblock 기준 측정, 신 pblock
  재검증 TODO.)**
- **PR 컨트롤러 1차 FSM 설계+시뮬레이션 🔄:** `pr_controller.v`(states
  `S_IDLE→S_DRAIN_WAIT→S_ICAP_ARM→S_ICAP_FETCH→S_ICAP_WRITE→S_DONE`) —
  ICAPE3 PRDONE 대신 **word-count 기반 완료판정**(NWORDS=171,633)으로 위
  한계를 우회. 실제 partial bitstream을 BRAM 모델로 스트리밍해 측정한
  trigger→완료 latency = **1,716,450 ns**, 순수 분석적 추정치(1.716ms)와
  교차검증 일치. **단, "1차"일 뿐**: `drain_ready`는 테스트벤치가 임의로
  만든 신호이지 실제 RM의 `ap_idle`이 아니고, BRAM 소스도 시뮬레이션 전용
  (실제 SD/DDR 경로 아님) — Stage 6 착수 전 완성 필요한 실질적 유일한 선결 과제.
- **pblock 재floorplan:** `CLOCKREGION_X1Y0:CLOCKREGION_X2Y0`으로 재정의,
  **용량 2배**(LUT 8,640→19,200 / BRAM 12→24 tile / DSP 96→216), `pr_verify`
  PASS 유지.

**라운드 4 — BLC fix + pblock fix 결합 최종 재구현 (2026-07-03):**
**pr_verify PASS 유지**하지만 partial bitstream이 pblock 용량 확장의 직접적
대가로 **2.11배 커짐**(686,664B→1,447,424B, LUT 용량 증가율 2.22배와 근접
— "용량 크기는 로직 사용량이 아니라 pblock 프레임 수로 결정된다"는 기존
발견의 재확인). ICAP latency도 동일 비율로 재계산: peak 1.716ms→**3.618ms**,
전형 6.865ms→**14.473ms**. **트레이드오프를 정직히 기록:** 자원 여유(2배) vs
재구성 지연(2.1배)를 맞바꾼 것 — 실제 RM 크기(LUT 3~4천대)에는 원래 좁은
pblock으로도 충분했으므로, 실배포 시 RM 후보 크기 확정 후 필요한 만큼만
넓히는 것이 맞다.

| 산출물 | 값 |
|---|---|
| full bitstream | 19,311,211 B(전체 라운드 불변) |
| partial bitstream(최종, 양 RM 동일) | 1,447,424 B |
| pr_verify(최종) | ✅ PASS |
| partition pin(최종 pblock 기준) | 3(구 pblock 기준 15 — 원인 미조사, SPEC.md §10에 open item으로 기록) |

**부가 산출물:** 마이크로아키텍처 다이어그램(SVG+drawio, Arm2 register-only /
Arm3 DFX 구조를 실제 코드 기준으로 시각화), 오늘 최종 산출물 일체를
`deliverables/`(verilog/bitstreams/checkpoints/reports 4종, git 비추적,
재현 절차는 본 로드맵의 각 결과 문서 참조)로 정리.

**근거:** `results/stage5-dfx-implementation-2026-07-02.md`,
`results/pr-latency-breakdown-2026-07-02.md`,
`results/pr-latency-vivado-sim-2026-07-02.md`,
`results/design-limitations-2026-07-03.md`,
`results/dfx-vivado-considerations-2026-07-03.md`,
`results/phase0-2-execution-2026-07-03.md`,
`results/pr_controller/pr_controller{,_tb}.v`,
`results/blc-fix-resynthesis-2026-07-03.md`,
`results/dfxisp-microarchitecture-2026-07-02.{svg,drawio}`.

---

## Stage 6 — 보드 실장 + DPU end-to-end (Arm 1/2/3 비교) ⬜ (유일하게 남은 단계)

**목표:** ZCU104에서 Arm 1(static+normal)/Arm 2(register-only)/Arm 3(DFX)을
실증 비교하여 H3(자원/전력 순이득)를 확정.

Stage 0~5로 "보드 측정 전단계"가 완료됐다. 남은 항목은 실물 ZCU104에서만
확인 가능하며, `improvement-strategy-2026-07-03.md`에 이미 순서가 정의돼 있다:

| 순서 | 항목 | 의존성 | 상태 |
|---|---|---|---|
| 1 | PS/DDR 통합(Block Design), GIC+DMA+PR 루프 드라이버 | Stage 5의 PR 컨트롤러 1차 설계 완성 | ⬜ |
| 2 | 실제 clock/reset 핀 배정 + 타이밍 제약(신 pblock 기준 WNS 재검증 포함) | 1 | ⬜ |
| 3 | 실제 PR latency 실측(trigger→완료, ICAP 실효 대역폭, XSA+JTAG+ILA) | 1, 2 | ⬜ |
| 4 | 절대 전력(W) 측정, Arm1/2/3 비교 | 1, 2 | ⬜ |
| 5 | DPU/검출기 end-to-end 실행(Vitis-AI, real-RAW, RGB32 직결) | 1~4 | ⬜ |
| 6 | Stage 3 BLC 완화가 real-RAW에서도 유효한지 최종 확인(DPU mAP vs SW 예측 정합) | 5 | ⬜ |

**검증 기준:** 3 arm이 동일 파이프라인에서 end-to-end 동작; DPU mAP가 SW
예측과 정합. **기대(H3):** 정상 모드에서 `Arm3 fabric·전력 < Arm2`(저조도
블록 미상주), 재구성 지연이 장면 단위 예산(33ms) 대비 수용 가능.

**착수 전 남은 선결 과제:** Stage 5의 PR 컨트롤러는 "1차"일 뿐이다 —
`drain_ready`를 실제 RM의 `ap_idle`에 연결하고, BRAM 시뮬레이션 소스를 실제
SD/DDR 경로로 교체해야 Stage 6의 1번 항목(PS/DDR 통합)에 들어갈 수 있다.

**산출물(예정):** `results/power_perf_newrm.csv`, 보드 실증 리포트, 최종
arm 비교표.

---

## 진행 보드 (상태 요약)

```text
[x] Stage 0  SW golden + baseline core 정합            (gate 6종 + cross-check 게이트)
[x] Stage 1  checker + 히스테리시스 시퀀스              (narrow band + N=3 최적; +principled-v3 C1 권장 → real-RAW 재확인 → C1 배포 → 오라클 라벨, 4관문 완료)
[x] Stage 2  tone RM 산술 + 이미지 지표                 (Policy A 확정; +RM 이득원인 정정)
[x] Stage 3  정확도 mAP arm/조건표 + 알고리즘 개정       (재검증 허브 — R1~R7 완료: real-RAW 교차검증(R6) + BLC 2/2 배포(R7)까지 완주)
[x] Stage 4  HLS 합성 + C/RTL Co-sim                    (csynth 3라운드 완료; cosim 자동비교만 미완주; BLC/C1 반영 재합성은 open)
[x] Stage 5  DFX PR 구현 + pr_verify + latency/컨트롤러  (4라운드, pr_verify 매 라운드 PASS; PR컨트롤러는 1차만)
[ ] Stage 6  보드 실장 + DPU end-to-end                  (보드 필요 — 유일하게 시작조차 못한 단계)
범례: [x] 절차 완료 · [~] 재진입/재검증 진행중 · [ ] 미착수 · (⚠️/🔄 = 세부 한계)
```

> **읽는 법:** `[x]`는 "절차를 다 돌렸다"는 뜻이다. Stage 3은 2026-07-20에
> R6(real-RAW 교차검증)·R7(BLC 배포)로 나선의 이번 바퀴를 완주해 `[~]`에서
> `[x]`로 승격했다 — 정성적 결론 유지, 정밀 mAP는 이제 real-RAW·배포값
> 기준으로 동결.

> **핵심 발견(SW, Stage 0~3) — 목표 1 관점:** 비교 arm은 normal/lowlight/
> adaptive다(`none` 제외, 위 프레이밍 노트). **저조도 모듈이 dark 조건에서
> `normal`을 앞지른다**는 것이 핵심 성과 — 완화 BLC가 결정타였다(ExDark
> `lowlight` 처음으로 `normal` 상회). 이 역전은 실센서 RAW(R3b)·canonical
> 파이프라인(R4)·**정본 real-RAW 교차검증(R6, LOD/PASCAL/Shuffle)**으로
> 3중 재확인됐다. **BLC 재보정(16/8→2/2)이 checker/adaptive 선택보다 훨씬
> 큰 mAP 레버**(최대 5.7배)임이 R6에서 처음 정량화돼 R7에서 배포됐다.
> Shuffle_split(혼합 스트림)에서 adaptive가 normal·lowlight 둘 다 이긴다는
> 목표 2 통과 기준은 BLC=2에서만 근소하게 충족(과장 금지). DFX 정당화는
> 자원/전력(목표 2 효율)이 우선(방향 A 유지), Stage 6에서 최종 확인.
> **핵심 발견(HW, Stage 4~5):** gamma를 런타임 sqrt→ROM LUT로 바꿔 자원
> −88%/−78%; adversarial 수정으로 저조도 RM 자원 추가 −41.3%; **pr_verify는
> 4라운드 전부 PASS**로 DFX 전환 가능함을 실측 확인; pblock 확장(용량 2배)은
> partial bitstream·재구성 지연을 2.1배로 늘리는 명시적 트레이드오프. **HW
> 소스(`src/dfxisp_accel.cpp`)는 2026-07-20 BLC/checker 상수 변경까지 반영
> 완료(값만 변경, 구조 불변) — 단 csynth/cosim 재실행은 아직 안 함(open).**
> **핵심 발견(SW, Stage 1~3 후속, 2026-07-04~20):** checker 5원리
> 정본화로 C1(dark16>0.62) 채택 권장 → real-RAW로 재확인 → **2026-07-20
> 정식 배포**, RM 이득의 실제 원인이 톤커브가 아니라 binning 제거임을 규명,
> checker SOTA 강화 4개 관문(LOD real-RAW/오라클 라벨/적응τ 검증/C1·τ
> 배포) **전부 완료** — 오라클 라벨 재정의로 잔존오차의 89.6%가 라벨
> 아티팩트임을 확인하고 C1은 재조정 불필요로 결론, adaptive-τ 개선은
> 정직한 부정적 결과로 실험코드에 남김.

## 즉시 다음 (우선순위)

**완료(2026-07-10 통합):** 브랜치 정리·통합이 끝났다 — `exp/principled-checker
-rm-2026-07-05`가 main을 병합(canonical 파이프라인 유입, behind 0)하고 demosaic
수정(구 PR #9)까지 접어 넣어 **모든 작업을 담은 단일 브랜치**가 됐다. checker
현행 상태는 `results/checker-status-2026-07-10.md`에 정본화(배포 C0 / 권장 C1 /
강화안 7항목 판정: #1·#6 채택, #2·#3·#5 기각, #4·#7 대기). stale 병합 브랜치 5개
삭제 완료. 아래는 남은 실질 과제다.

**완료(2026-07-20, 이전 "즉시 다음" 전부 종결):** 정본 데이터셋 재평가(R6),
BLC 재보정 배포(R7), checker C1 배포(관문 4), 오라클 라벨 재정의(관문 2),
adaptive-τ 개선 실험(부정적 결과 확정) — 위 Stage 1·3 절 신규 라운드 참고.
Stage 3의 mAP 수치는 이제 R6/R7(real-RAW, canonical 파이프라인, 배포값
기준)이 최신 정본이다 — R1~R4(및 R3b)는 여전히 정성적 근거로 유효하나
정밀 수치 인용 시 R6/R7로 대체됐음을 명시할 것.

**완료(2026-07-20~08-03):** csynth/cosim 재실행(구 항목 1 — 자원/타이밍 완전
동일 확인, `blc-c1-csynth-cosim-rerun-2026-07-20.md`), 그 상수 반영 Vivado DFX
fabric-only 재구현(`dfx-reimplementation-2026-08-01.md`) 및 그 안에서 나온
CLB LUT 34~37% 감소의 근본 원인 확정(RM RTL 차이는 BLC 상수 유도 리터럴
6개뿐 — 상수 기반 technology mapping의 정상 거동, 08-03 후속 조사로 종결).
교차 모델 검증(구 항목 2)은 1단계 착수 — YOLOv8s 재실행을 노트북 RTX 5060에
인수인계(`HANDOFF-cross-model-yolov8s-2026-08-03.md`), 실행 중.

**완료(2026-08-03~04):** 저조도 **WB 모드별 분리 검토·기각**(위 "마지막 갱신" 참조)
— 07-03 분리 ablation이 pseudo-RAW(이미 카메라 AWB됨)와 BLC=16 클리핑이라는 두
결함 위에서 측정됐다는 문제 제기로 실 RAW·BLC=2·n=321에서 재검증했으나 결론이
그대로였다(가설 기각). WB는 3회 검증 수렴으로 **재실험 불필요**. 도구
(`--wb-lowlight`)는 남겨둠. 같은 기간 **HW 인터페이스 브리핑 문서** 작성
(`HW-INTERFACE-PIN-MODULE-PROTOCOL-2026-08-03.md` — 핀 매핑/모듈 관계/프로토콜)과
**RP 경계 서술 정정**(`SPEC.md` §7·§11.12) 완료.

**완료(2026-08-04): Arm1 정적 baseline-only 자원/타이밍 실측** — 3-arm 비교표의
빈 축을 메웠다(`SPEC.md` §10·§10.1). **Arm1은 알고리즘적으로 `run_normal()` 그
자체라 이미 합성돼 있던 `rm_normal_tone_top`과 같은 설계였고, `TODO`는 측정
공백이 아니라 장부 공백**이었다 — Arm1·Arm2를 동일 소스·동일 세션에서 재합성해
확정(Arm1 = LUT 5,202/FF 3,797/BRAM 4/DSP 12 @ 273.97MHz, 07-03 수치와 완전 일치).
**적응성의 비용 = LUT +58.9%**이고 그중 **DFX 회수 상한은 2,110 LUT(Arm2 총계의
25.5%)**, 나머지 31%(checker/mux)는 제거 불가 — **DFX 순이득의 이론적 천장**이
이 수치로 규정된다. 세 arm의 Fmax는 동일(273.97MHz).

**완료(2026-08-04): 세 arm post-route 축 통일 — DFX 절감 정본 확보** —
Arm1(3,363 LUT)·Arm2(4,768)·RM_LOW_LIGHT(2,344)를 동일 래퍼·동일 플로우로
배치·배선해 **DFX 절감을 같은 축에서 확정**했다: Arm2 대비 **normal 모드 −29.5%,
low-light 모드 −50.8%**. §10.1의 csynth 기반 추정(상한 25.5%)은 과소평가였다.
`published config1도 정확히 재현`됐다(2,630/1.5/12, 수정 없는 `dfx_flow.tcl`).
상세: `SPEC.md` §10.2·§10.3.

> **정정:** 같은 날 앞선 커밋에서 "Arm3 수치 재현 불가"를 최우선 항목으로 올렸으나
> **오류였다** — RTL 이관 시 `cp *.v`로 감마 ROM `.dat`이 누락된 채 합성한 결과였다.
> `.dat` 포함 재복사 후 즉시 일치. 해당 최우선 항목은 철회한다. 다만 **파티션 빌드와
> flat 빌드의 자원 수치를 섞으면 안 된다**는 제약은 실재하므로(동일 넷리스트에서
> 24% 차이, 원인 미규명) 자원 비교는 flat 축, 파티션 빌드는 bitstream/pr_verify
> 용도로 분리해 쓴다.

**즉시 다음 (최우선, 서로 막고 있지 않음 — 병행 가능):**

1. **교차 모델 검증 YOLOv8s 결과 회수·정리** — 노트북 완료 후
   `cross-model-yolov8s-2026-08-03.md` 작성, §8.3(lowlight≥normal-on-PASCAL
   9/9) 재현 여부 우선 판정.
2. **교차 모델 검증 2단계(SSDLite-MobileNetV3)** — `eval_map_isp.py`가 아직
   torchvision SSDLite 경로를 지원하지 않음(`eval_map_ssd.py`에만 있음) —
   글루 코드 작성 후 별도 인수인계. YOLOv8s와 마찬가지로 이미 배포된 결정
   (BLC 2/2, C1)을 막고 있지 않음, 논문 일반화 주장 보강용.

**Stage 6 착수 준비 (순서 유지, 실질적으로 유일하게 남은 큰 단계):**

3. **Stage 6 착수 선결 과제** — PR 컨트롤러의 `drain_ready`를 실제 RM
   `ap_idle`에 연결, BRAM 시뮬레이션 소스를 실제 SD/DDR 경로로 교체.
4. **Stage 6 순서 1~2** — PS/DDR 통합(Block Design) → 신 pblock 기준
   clock/reset 핀 배정 + WNS 재검증.
5. **(선택) Stage 5 open item** — partition pin 수 15→3 감소 원인 조사
   (SPEC.md §10에 미조사로 기록됨).
6. **(선택) Stage 4 cosim 완주** — WSL2+XSIM 하네스 SIGSEGV 원인(struct-pointer
   인터페이스 추정) 해소.
7. **(선택, 우선순위 미정) STRATEGY.md Vitis-first 리팩터** — 2026-07-03에
   제안됐으나 착수되지 않았다(`src/`에 `base_vitis.cpp` 등 Task 1~18 산출물
   없음) — checker/BLC real-RAW 재보정 트랙이 대신 우선됐다. Stage 6 착수
   전에 할지, 논문 마감(2026-10) 압박을 고려해 보류할지 결정 필요. **이 항목은
   `SPEC.md` §11.12(RP 경계)와 연동된다** — Vitis-first가 선호하는 "RP=Tone만"과
   현재 구현인 "RP=모드별 전체 파이프라인"은 양립 불가라, 어느 논문 서사를
   택할지가 곧 이 리팩터의 착수 여부다(`STRATEGY.md` 열린 질문 #4).
8. **(신규 2026-08-04, 목표 2 직결) Arm1의 Vivado 구현(post-route)** — §10.1이
   확보한 Arm1 vs Arm2 델타는 **둘 다 csynth 추정치**라 유효하지만, Arm3
   config1/config2는 **post-route 실측치**라 단계가 달라 직접 비교가 불가하다.
   Arm1을 Vivado로 구현하면 세 arm이 같은 축(post-route)에 놓여 **"DFX가 정적
   baseline 대비 실제로 얼마나 이득인가"**를 처음으로 말할 수 있다. 비용은
   Vivado 구현 1회(수시간, 보드 불필요).
9. **(선택, 신규 2026-08-04) BLC=0 미검증** — 정본 캠페인(07-15)은
   `--blc-offsets 16,1,2`만 돌렸고 **0은 한 번도 테스트되지 않았다**. WB 조사
   중 실측된 바로는 BLC=2에서도 저조도 픽셀의 **52~73%가 0으로 클리핑**되므로
   (`lowlight-wb-mode-split-2026-08-03.md` §2), BLC=0이 근-흑색 픽셀(8-bit 1~2 →
   gamma 2.0 후 15~22)을 살려 이득을 줄 가능성이 열려 있다. 비용은 WB 스윕과
   동일(SonyNOD 321 × 후보 1~2개, GPU 약 15분). 도구는 이미 있음(`--blc-offsets 0`).
   → **철회(2026-08-04 당일, 전제 오류).** "정본 캠페인이 `16,1,2`만 돌렸으니
   0은 미검증"이라 적었으나 **틀렸다**: 07-08 재보정이 이미 SonyNOD 321장에
   대해 `{0,1,2,4,8,16}` 전 구간을 canonical 파이프라인(gamma 버그 수정본)으로
   스윕했고(`isp-pipeline-recalibration-2026-07-08.md`,
   `map_isp_sonynod_blcfix_yolov8n.csv`), 07-15가 `16,1,2`로 좁힌 것은 그때
   최적 구간이 이미 확정돼 있었기 때문이다. **BLC=0은 배포값보다 나쁘다**
   (lowlight 0.1965 vs 0.2140 = **−8.2%**, normal 0.1849 vs 0.1900). 해석은
   `SPEC.md` §4 각주 참조 — 클리핑률이 높은 것이 오히려 유리하다.

## 주의 (지어내지 않기)

- Stage 6(보드) 수치는 실물 보드 없이는 `TODO(측정)`(재구성 지연 실측치,
  전력, DPU 정확도) — 분석적 추정치(§Stage 5)와 시뮬레이션 실측치(PR 컨트롤러)는
  있으나 보드 실측으로 반드시 재검증해야 한다.
- 구 08/11(2026-06-29 이전) mAP 수치는 ablation arm(구 variant) 기준 —
  현재 서사(Stage 3 최종 라운드)에 직접 인용 금지.
- **2026-07-08 이전에 계산된 Stage 3 mAP 수치(R1~R3, R3b 포함)는 SW-eval
  도구가 배포 HW의 gamma 곡선과 어긋난 상태에서 얻어졌다** — 정성적 결론
  (`lowlight`가 `normal`을 앞지름, `none`이 여전히 최고)은 R4에서 재확인
  됐지만, 정밀한 숫자를 인용할 때는 반드시 R4(`isp-pipeline-recalibration
  -2026-07-08.md`)의 재보정 값을 우선하고 구 값은 "당시 서술"로만 취급할 것.
- `data/aodraw_test`는 아직 다운로드 완료 전이라 존재하지 않는다 —
  `tools/aodraw_adapter.py`의 실 `.ARW` 디코드 경로는 셀프테스트로만
  검증됐고 실파일로는 아직 실행되지 않았음을 인용 시 명시할 것.

---

## 부록 A — 작업 이력 로그 (Phase 0~13, 날짜순, 원문 보존)

이 절은 위 Stage 기반 재구성 이전에 실제로 작업이 진행된 시간 순서를 그대로
보존한다. **Stage는 "무엇을 계획했는가"의 축, Phase는 "언제 무엇을 했는가"의
축**이다 — 같은 작업이 여러 Stage에 걸치기도 하고(예: Phase 13은 Stage 3+4+5
전부에 해당), 한 Phase가 이전 Phase의 결함을 수정하며 같은 Stage를 여러
라운드로 되짚기도 한다(Phase 6/7, Phase 13 등). 아래 표는 각 Phase가 위의
어느 Stage(들)에 대응하는지 보여준다.

| Phase | 날짜 | 내용 | 대응 Stage | 상태 |
|---|---|---|---|---|
| 0 | 06-08~06-29 | 초기 RM 후보 스크리닝, "방향 A" 확립 | (Stage 0~5 이전 탐색) | ✅ |
| 1 | 07-01 | 아키텍처 reset, Stage 0~6 계획 수립 | Stage 0 계획 확정 | ✅ |
| 2 | 07-01~02 | SW 트랙 Stage 0~3 최초 실행 | Stage 0, 1, 2, 3(R1) | ✅ |
| 3 | 07-02 | 알고리즘 개정 ver1/ver2 | Stage 3(R2), Stage 1 재보정 | ✅ |
| 4 | 07-02 | 실제 Vitis HLS C-synthesis 최초 | Stage 4(R1) | ✅⚠️ |
| 5 | 07-02 | 실제 Vivado DFX 구현 최초 | Stage 5(R1) | ✅ |
| 6 | 07-02 | Adversarial review + 결함 수정 | Stage 0 검증 강화 | ✅ |
| 7 | 07-02 | 수정 반영 전체 재합성 | Stage 4(R2), Stage 5(R2) | ✅ |
| 8 | 07-02 | 마이크로아키텍처 문서화 | Stage 5 부가 산출물 | ✅ |
| 9 | 07-02 | DFX latency 분해 + low-light 원인 규명 | Stage 5(R3 latency), Stage 3(R3 원인규명) | ✅ |
| 10 | 07-02 | Vivado 시뮬레이션 latency 실측 시도 | Stage 5(R3) | ⚠️ |
| 11 | 07-03 | 설계 한계 종합 + 개선 전략 수립 | Stage 5(R3 pblock/timing 조사) | ✅ |
| 12 | 07-03 | 개선 전략 Phase 0~2 즉시 실행(6항목) | Stage 0(cross-check), Stage 3(R3 ablation), Stage 5(R3 PR컨트롤러+pblock) | ✅🔄 |
| 13 | 07-03 | BLC 완화 정본 반영 + 최종 재합성 | Stage 3(R3 최종), Stage 4(R3), Stage 5(R4) | ✅ |

### 문서 지도 (전체 산출물, 시간순)

```text
Phase 0   isppipeline/hls/results/10-hw-csynth-resource-2026-06-29.md
          isppipeline/hls/results/11-ssd-crosscheck-2026-06-29.md
Phase 1   RESEARCH.md · isppipeline/hls/results/experiment-stages-2026-07-02.md
Phase 2   isppipeline/hls/results/stage1-3-results-2026-07-02.md
Phase 3   isppipeline/hls/results/experiment_ver{1,2}-2026-07-02.md
Phase 4   isppipeline/hls/results/stage4-hw-synthesis-2026-07-02.md
Phase 5   isppipeline/hls/results/stage5-dfx-implementation-2026-07-02.md
Phase 6   SPEC.md §11.5 (커밋 a2d1b6d)
Phase 7   (stage4/5 문서 2026-07-02 내 갱신 이력 참조)
Phase 8   isppipeline/hls/results/dfxisp-microarchitecture-2026-07-02.{svg,drawio}
Phase 9   isppipeline/hls/results/pr-latency-breakdown-2026-07-02.md
          isppipeline/hls/results/lowlight-rm-map-rootcause-2026-07-02.md
Phase 10  isppipeline/hls/results/pr-latency-vivado-sim-2026-07-02.md
Phase 11  isppipeline/hls/results/design-limitations-2026-07-03.md
          isppipeline/hls/results/dfx-vivado-considerations-2026-07-03.md
          isppipeline/hls/results/improvement-strategy-2026-07-03.md
Phase 12  isppipeline/hls/results/phase0-2-execution-2026-07-03.md
Phase 13  isppipeline/hls/results/blc-fix-resynthesis-2026-07-03.md
전체 종합  isppipeline/hls/results/experiment-report-2026-07-02.md (SW+HW 통합 서사)
```

---

문서 끝 — 새 작업을 시작하면 해당 Stage 섹션과 위 진행률 요약표, 필요 시
부록 A 표에 추가할 것. `SPEC.md`(시스템 스펙)·`RESEARCH.md`(아키텍처 정본)·
`isppipeline/hls/results/experiment-stages-2026-07-02.md`(Stage 계획 정본)와
함께 최신 상태 유지.
