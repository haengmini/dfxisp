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
**마지막 갱신:** 2026-07-09 — 트랙별 세부 진행 표 추가 + 2026-07-04~08 사이
main에 병합된 후속 사건 반영: checker principled-v3(5원리, C1 권장)와
RM 서사 정정(binning 제거가 실이득, PR #4), SonyNOD 실센서 BLC ablation
(R3b), canonical-matched 파이프라인 재보정으로 Stage 3 수치 재검증(R4,
PR #8), Hermes 병렬 리뷰(PR #6)와 PR #3 복구(PR #5). 상세는 각 Stage
절의 "후속/정정/R3b/R4" 항목과 "즉시 다음"의 신규 우선순위 참고.

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
Stage 1  checker + N-frame 히스테리시스                ✅+  2026-07-01 ~ 07-05(+principled-v3 후속, C1 권장·미배포)
Stage 2  tone RM 산술 확정 + 이미지 지표               ✅+  2026-07-01 ~ 07-05(+RM 이득원인 정정: binning 제거)
Stage 3  정확도(mAP) 평가 + 알고리즘 개정              🔄⚠️ 2026-07-01 ~ 진행중(R1~R4 완료 + R5 mAP 재검증 GPU 대기 — 재검증 허브)
Stage 4  HLS 합성 + C/RTL Co-sim                       ✅⚠️ 2026-07-02 ~ 07-03(3라운드; cosim 자동비교 미완주)
Stage 5  DFX(PR) 구현 + pr_verify + latency/PR 컨트롤러 ✅⚠️🔄 2026-07-02 ~ 07-03(4라운드; PR컨트롤러 1차만)
Stage 6  보드 실장 + DPU end-to-end                    ⬜   미착수(실물 보드 필요 — 유일하게 시작조차 못한 단계)

범례: ✅ 완료 · ✅+ 완료 후 후속 개정 있었음 · 🔄 재진입/진행중 · ⚠️ 알려진 한계 · ⬜ 미착수
```

**한 줄로:** 척추(0→5)는 다 올라갔다. 지금은 **Stage 3으로 되돌아와 SW를
재검증·수정하는 나선의 한 바퀴 안**에 있고(demosaic 수정 → R5 대기), 보드가
필요한 Stage 6만 아직 시작 못했다.

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
| SW | Stage 1 후속 | principled-v3: 체커 5원리 정본화 + C0~C4 비교, C1(dark16>0.62) 권장 | 트리거③(감사) | ✅ 완료(권장; 배포 보류) | 07-05 |
| SW | Stage 2 | tone RM 산술 확정(Policy A), arm별 이미지 지표, gain·gamma 중복없음 | 계획 | ✅ 완료 | 07-02 |
| SW | Stage 2 정정 | RM 저조도 이득 원인 규명 — 톤커브 아님, binning 제거(해상도)가 지배. 권장 arm `F_g20` | 트리거③(감사) | ✅ 완료(1차 서사 정정) | 07-05 |
| SW | Stage 3 · R1 | 최초 조건표 A~G, 3-detector 교차검증 → 전 조건 `none` 최고, guardrail 최초 탈락 | 계획 | ✅ 완료 | 07-02 |
| SW | Stage 3 · R2 | ver1(RAW-domain-first) + ver2(checker 재보정) 개정 → 개선됐으나 여전히 `none` 최고 | 계획(R1 되짚기) | ✅ 완료 | 07-02 |
| SW | Stage 3 · R3 | 저조도 root-cause(BLC=손실 70%) + BLC 완화 반영 → ExDark lowlight +78%, 최초로 normal 상회 | 계획(R2 되짚기) | ✅ 완료 | 07-03 |
| SW | Stage 3 · R3b | SonyNOD 실센서 RAW(321장) BLC ablation → 역전이 실센서에서도 재현 | **트리거②(실데이터)** | ✅ 완료 | 07-07 |
| SW | Stage 3 · R4 | canonical 파이프라인 재보정(Hermes가 발견한 SW/HW gamma 불일치 수정) → 결론 유지, 마진 +76%→+12.6%, "normal 단조감소" 정정 | **트리거③(감사)** | ✅ 완료(수치 재검증) | 07-08 |
| SW | Stage 3 · R5 | demosaic R/B bilinear 수정(PR #9) 반영 mAP 재실행 — **코드·bit-exact 검증 완료, mAP 재실행만 GPU 대기** | **트리거③(감사)** | 🔄 대기(미착수) | — (GPU 필요) |
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
| SW | Stage 3 후속(SOTA) | checker SOTA 강화: 히스토그램 LRT(정직하게 기각) + AODRaw 어댑터 선작성(셀프테스트 통과, 데이터 대기) | 트리거③(감사) | 🔄 진행중(미병합) | 07-09 |
| 거버넌스 | — | "Hermes" 병렬 리뷰 → Python robustness 수정(경계 문서화, edge-clamp demosaic 버그) | 트리거③ 원천 | ✅ 완료(PR #6) | 07-08 |
| 거버넌스 | — | PR #3(references) 브랜치 삭제로 자동 종료 → 리베이스 후 PR #5로 복구, 데이터 유실 없음 | 프로세스 | ✅ 완료 | 07-08 |

> **표 밖 참고 — 브랜치 상태(2026-07-10 기준):** 되먹임 작업이 두 브랜치로
> 갈라져 있다.
> - **`exp/principled-checker-rm-2026-07-05`** (이 문서가 있는 브랜치): 위
>   "Stage 3 후속(SOTA)" 및 이 로드맵 갱신들이 여기 쌓여 있다. `main`보다
>   **11커밋 앞, 4커밋 뒤** — PR #4로 한 번 병합된 뒤에도 계속 커밋됐고 그
>   사이 main에 PR #5~#8이 들어왔기 때문. 병합 전 main 리베이스 필요.
> - **`fix/canonical-demosaic-bilinear-2026-07-09`** (PR #9, 열림·병합가능):
>   R5의 demosaic 수정. `main`에 있는 canonical 파일이 대상이라 main 기준
>   분기했다. 이게 먼저 병합돼야 R5 mAP 재검증이 정본 위에서 돌아간다.
> 정리 순서는 아래 "즉시 다음" 참고.

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

## Stage 3 — 정확도(mAP) 평가: arm & 조건표 + 알고리즘 개정 ✅⚠️ (4라운드 + R5 대기)

> **상태 주의:** 비교 arm은 normal/lowlight/adaptive다(`none` 제외 —
> 상단 프레이밍 노트). 목표 1 관점의 결론(**저조도 모듈이 dark 조건에서
> `normal` 상회**)은 안정적으로 재확인돼 왔으나, **R4까지의 정밀 mAP는
> 아직 두 번 더 갱신될 예정이다:** (1) PR #9 demosaic 수정 반영(R5, GPU
> 대기), (2) **정본 데이터셋(PASCAL RAW/LOD RAW) 재평가** — 아래 R1~R4는
> COCO/ExDark pseudo-RAW + 단일센서 SonyNOD 기반이라, real-RAW 쌍에서의
> 교차 우위(normal@PASCAL / lowlight@LOD)로 재수립해야 목표 1의 최종
> 근거가 된다. "완료"는 보드 없이 할 수 있는 절차가 최소 한 번씩 실행됐다는
> 뜻이지 수치·데이터셋이 동결됐다는 뜻이 아니다.

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
  CUDA 불가)라 별도 R5 라운드로 미룸.** PR 상태: 리뷰 대기, `main`
  미병합.
- **범위:** 이 재보정은 SW 평가 도구만 바꿨다 — Stage 4/5의 HLS/Vivado
  수치는 재합성 대상이 아니며(알고리즘 상수 자체는 불변), Stage 3의
  R1~R3·R3b **정성적 결론은 재확인**됐으나 그 **정밀 mAP 수치는 canonical
  파이프라인 기준으로 대체(superseded)**된 것으로 취급한다.

**근거:** `results/isp-pipeline-recalibration-2026-07-08.md`,
`daily-reports/2026-07-08.md`, PR #6(`fix/python-robustness-hermes-2026-07-08`).

**라운드 5 — demosaic bilinear 수정 반영 mAP 재검증 🔄 대기 중 (착수 미정):**
PR #9(위 R4 절의 2026-07-09 정정)가 canonical `_demosaic_rggb16`의 R/B
단일탭 버그를 고쳤다. 코드 수정과 bit-exact 교차검증은 완료됐지만
(`results/demosaic-bilinear-fix-2026-07-09.md`), **이 수정을 반영한 mAP
재실행은 아직 하지 않았다** — R4와 같은 카테고리의 재보정이 한 번 더
필요하다는 뜻이며, 이번에도 SW 트랙 소관이다. 착수 조건: (1) PR #9
main 병합, (2) GPU 가용 세션(07-08 R4는 RTX 5060에서 4.5시간 소요 —
이 저장소 작업이 이뤄진 샌드박스는 CUDA 불가라 완료 못함). 예상 결과
(픽셀 단위 사전측정 기반): 정성적 결론 반전 가능성은 낮고, R4의 정밀
수치(마진 +12.6% 등)가 다시 소폭 이동할 것으로 예상.

**근거:** `results/demosaic-bilinear-fix-2026-07-09.md`,
PR #9(`fix/canonical-demosaic-bilinear-2026-07-09`, 리뷰 대기).

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

**목표:** static region(checker·baseline core·컨트롤러)과 tone RM slot(재구성)을
분리하고, checker 트리거 → drain → PR 적재 → RM swap의 무손실 전환을 검증.

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
[x] Stage 1  checker + 히스테리시스 시퀀스              (narrow band + N=3 최적; +principled-v3 후속 C1 권장)
[x] Stage 2  tone RM 산술 + 이미지 지표                 (Policy A 확정; +RM 이득원인 정정)
[~] Stage 3  정확도 mAP arm/조건표 + 알고리즘 개정       (재검증 허브 — R1~R4 완료, R5 대기: demosaic 수정 mAP 재실행이 GPU 대기 ⚠️ 아래 Stage 3 절)
[x] Stage 4  HLS 합성 + C/RTL Co-sim                    (csynth 3라운드 완료; cosim 자동비교만 미완주)
[x] Stage 5  DFX PR 구현 + pr_verify + latency/컨트롤러  (4라운드, pr_verify 매 라운드 PASS; PR컨트롤러는 1차만)
[ ] Stage 6  보드 실장 + DPU end-to-end                  (보드 필요 — 유일하게 시작조차 못한 단계)
범례: [x] 절차 완료 · [~] 재진입/재검증 진행중 · [ ] 미착수 · (⚠️/🔄 = 세부 한계)
```

> **읽는 법:** `[x]`는 "절차를 다 돌렸다"이지 "수치 동결"이 아니다. Stage
> 3이 `[~]`인 것은 위 나선 모델대로 새 발견(demosaic 수정)이 들어와 다시
> 재검증 중이기 때문 — 정성적 결론은 안 바뀌고, 정밀 mAP만 R5에서 갱신된다.

> **핵심 발견(SW, Stage 0~3) — 목표 1 관점:** 비교 arm은 normal/lowlight/
> adaptive다(`none` 제외, 위 프레이밍 노트). **저조도 모듈이 dark 조건에서
> `normal`을 앞지른다**는 것이 핵심 성과 — 완화 BLC가 결정타였다(ExDark
> `lowlight` 처음으로 `normal` 상회). 이 역전은 실센서 RAW(R3b)·canonical
> 파이프라인(R4)으로 독립 재확인됐고, **정량 마진은 R4에서 축소**(+76%→
> +12.6%, 이전 마진 상당부분이 gamma 불일치 인공물). **아직 최종 아님** —
> demosaic 수정(R5) mAP 재검증 GPU 대기 + **정본 근거는 PASCAL RAW(normal
> 우위)↔LOD RAW(lowlight 우위) 교차 우위**로 재수립 예정(그게 "전환 필요"
> = 목표 1→2 연결의 실증). 정성적 결론 반전 가능성은 낮음. DFX 정당화는
> 자원/전력(목표 2 효율)이 우선(방향 A 유지).
> **핵심 발견(HW, Stage 4~5):** gamma를 런타임 sqrt→ROM LUT로 바꿔 자원
> −88%/−78%; adversarial 수정으로 저조도 RM 자원 추가 −41.3%; **pr_verify는
> 4라운드 전부 PASS**로 DFX 전환 가능함을 실측 확인; pblock 확장(용량 2배)은
> partial bitstream·재구성 지연을 2.1배로 늘리는 명시적 트레이드오프. **HW
> 소스(`src/dfxisp_accel.cpp`)는 이 SW 재보정과 무관하게 전 라운드 불변.**
> **핵심 발견(SW, Stage 1~3 후속, 2026-07-04~09):** checker 5원리
> 정본화로 C1(dark16>0.62) 채택 권장(미배포)했고, RM 이득의 실제 원인이
> 톤커브가 아니라 binning 제거임을 규명(1차 서사 정정, 권장 arm `F_g20`로
> 변경). 이후 checker를 SOTA 기준으로 더 강화하는 후속 작업(히스토그램
> LRT는 정직하게 기각, AODRaw 실센서 데이터 어댑터는 선작성 완료)이 별도
> 브랜치에서 진행 중.

## 즉시 다음 (우선순위)

**신규(2026-07-09 파악, 최우선):**

1. **브랜치 정리** — `exp/principled-checker-rm-2026-07-05`가 이미 병합된
   PR #4 이후로도 계속 커밋되고 있어, main의 PR #5~#8(참고문헌 정리,
   Hermes 수정, canonical 파이프라인 재보정)과 별도로 갈라진 상태다.
   다음 병합 전에 main 기준 리베이스 필요.
2. **Stage 3 수치 재확인 대상 정리** — 2026-07-08 이전에 계산된 mAP
   수치(R1~R3, R3b 포함)는 canonical 파이프라인 기준으로 최종 확정된 것이
   아니므로, 앞으로 이 수치들을 인용할 때는 R4(`isp-pipeline-recalibration
   -2026-07-08.md`)로 대체(superseded)됐음을 명시할 것.
3. **PR #9 (`fix/canonical-demosaic-bilinear-2026-07-09`) 리뷰·병합** —
   R/B 채널 단일탭→bilinear 수정은 완료·검증됐으나(Stage 3 R4 절 정정
   참고) main 미병합. 병합 후 GPU 가용 시 mAP 재검증(R5) 착수.
4. **정본 데이터셋 재평가(목표 1·2의 핵심 실증)** — PASCAL RAW(밝음)/
   LOD RAW(저조도) real-RAW 쌍으로 세 arm(normal/lowlight/adaptive) 재실행:
   (a) normal이 PASCAL RAW, lowlight가 LOD RAW에서 각각 우위인지(교차 우위
   = 전환 필요성), (b) 혼합 스트림에서 adaptive가 최적 단일 static 상회인지.
   저조도 모듈 이득표(`lowlight-module-techniques-2026-07-10.md`)의 실측
   열을 이 real-RAW 수치로 대체. **어댑터: 저조도 LOD는 Sony `.ARW`라
   기존 `aodraw_adapter.py`의 rawpy 경로가 그대로 적용된다**(sonynod 선례와
   동일 포맷; 파일별 흑레벨/화이트레벨/베이어를 rawpy에서 읽으므로 하드코딩
   불필요). PASCAL RAW(밝음)도 rawpy가 처리하는 RAW 포맷이면 같은 경로 —
   실 다운로드 파일로 `read_raw()` 한 함수만 확인하면 된다.
5. **checker SOTA 강화 후속** — 오라클 라벨 재정의(#4)·센서 적응 임계 τ(#1)는
   위 real-RAW 데이터셋 위에서 착수 (`checker-sota-strategy-2026-07-09.md`).

**기존(Stage 6 착수 준비, 순서 유지):**

5. **Stage 6 착수 선결 과제** — PR 컨트롤러의 `drain_ready`를 실제 RM
   `ap_idle`에 연결, BRAM 시뮬레이션 소스를 실제 SD/DDR 경로로 교체.
6. **Stage 6 순서 1~2** — PS/DDR 통합(Block Design) → 신 pblock 기준
   clock/reset 핀 배정 + WNS 재검증.
7. **(선택) Stage 5 open item** — partition pin 수 15→3 감소 원인 조사
   (SPEC.md §10에 미조사로 기록됨).
8. **(선택) Stage 4 cosim 완주** — WSL2+XSIM 하네스 SIGSEGV 원인(struct-pointer
   인터페이스 추정) 해소.

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
