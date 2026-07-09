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
**마지막 갱신:** 2026-07-09 (트랙별 세부 진행 표 추가)

## 상태 범례

| 기호 | 의미 |
|---|---|
| ✅ | 완료 — 실측/실행 완료, 근거 문서 있음 |
| ⚠️ | 완료했으나 알려진 한계·트레이드오프가 있음(정직하게 기록됨) |
| 🔄 | 부분 진행 — 1차 결과 있음, 후속 필요 |
| ⬜ | 미착수 — 대부분 실물 보드가 필요해서 지금 못 함 |

## 트랙 구조 (정본, experiment-stages-2026-07-02.md)

```text
SW 트랙 (data/, model/, tools/)            HW 트랙 (isppipeline/hls, Vivado)
  Stage 0 golden/baseline core 확정   ─┐
  Stage 1 checker + 히스테리시스        │      Stage 4 HLS 합성 + C/RTL Co-sim
  Stage 2 tone RM 산술 + 이미지 지표    ├─(golden 정합에서 합류)─▶ Stage 5 DFX 컨트롤러 + 전환 sim
  Stage 3 정확도(mAP) arm/조건표        ─┘                          Stage 6 보드 실장 + end-to-end
```

SW 트랙(0~3)은 보드 없이 수행 가능 — **전부 완료**. HW 트랙(4~6) 중 4~5는
Vivado로 완료, **Stage 6만 실물 보드가 필요해 유일하게 남았다**.

## 전체 진행률 한눈에

```text
Stage 0  SW golden + shared baseline core 확정        ✅  2026-07-01 ~ 07-03(누적 보강)
Stage 1  checker + N-frame 히스테리시스                ✅  2026-07-01 ~ 02
Stage 2  tone RM 산술 확정 + 이미지 지표               ✅  2026-07-01 ~ 02
Stage 3  정확도(mAP) 평가 + 알고리즘 개정(ver1/2/BLC)  ✅  2026-07-01 ~ 07-03(3라운드)
Stage 4  HLS 합성 + C/RTL Co-sim                       ✅⚠️ 2026-07-02 ~ 07-03(cosim 자동비교 미완주)
Stage 5  DFX(PR) 구현 + pr_verify + latency/PR 컨트롤러 ✅⚠️🔄 2026-07-02 ~ 07-03(4라운드, PR컨트롤러 1차만)
Stage 6  보드 실장 + DPU end-to-end                    ⬜  미착수(유일하게 남은 단계)
```

## 트랙별 세부 진행 표 (Stage + 라운드 단위)

Stage 3/4/5는 여러 라운드(round)로 나뉘어 진행됐다. 아래 표는 그 라운드
하나하나를 진행 순서대로 펼쳐, 트랙·내용·상태·최종 작업 날짜를 한 번에
보여준다. 각 행의 근거 문서는 해당 Stage 절의 "근거:" 목록을 참조.

| 트랙 | Stage | 순서 | 내용 | 상태 | 최종 작업 날짜 |
|---|---|---|---|---|---|
| SW | Stage 0 | (단일) | golden(Python) ↔ C-sim(C++) bit-exact 확정, 아키텍처 gate 6종 + 독립 교차검증 게이트(binning fuzz 500회) | ✅ 완료 | 2026-07-03 (2026-07-01~03 누적 보강) |
| SW | Stage 1 | (단일) | dark-ratio 기반 checker + N-frame 히스테리시스, 스케줄러 파라미터 스윕(narrow band+N=3 최적), 전환 임계값 재보정(0.40→0.80) | ✅ 완료 | 2026-07-02 |
| SW | Stage 2 | (단일) | tone RM 산술 확정(Policy A, H/2×W/2), arm별 이미지 지표(Y mean/std/포화율/dark-ratio), gain·gamma 중복없음 확인 | ✅ 완료 | 2026-07-02 |
| SW | Stage 3 | R1 | 최초 조건표 A~G, 3-detector(YOLOv8n/s+SSDLite) 교차검증 → 모든 조건 `none` 최고, guardrail 최초 탈락 확인 | ✅ 완료 | 2026-07-02 |
| SW | Stage 3 | R2 | ver1(RAW-domain-first, exposure gain 추가) + ver2(checker 재보정) 알고리즘 개정 → 개선됐으나 여전히 `none`이 최고 | ✅ 완료 | 2026-07-02 |
| SW | Stage 3 | R3 | 저조도 root-cause 규명(BLC가 손실의 70%, 해상도 손실은 −1.4%) + BLC 완화(`BLC_OFFSET12_LOWLIGHT=128`) 반영 → ExDark lowlight mAP +78%, 최초로 normal 상회 | ✅ 완료 | 2026-07-03 |
| HW | Stage 4 | R1 | 최초 실합성(streaming line buffer 리팩터, gamma Newton→ROM LUT화), unified+RM독립 top 2종 Fmax 273.97MHz 실측 | ✅⚠️ 완료(cosim 자동비교 미완주) | 2026-07-02 |
| HW | Stage 4 | R2 | adversarial 수정(binning 스칼라평균 버그, 메타데이터 미검증 포인터) 반영 재합성 → LUT 대폭 감소(unified −26.3%, low-light RM −41.3%) | ✅ 완료 | 2026-07-02 |
| HW | Stage 4 | R3 | BLC 완화 반영 재합성 → 3개 top 자원 완전 불변(순수 파라미터 변경이라 mAP 개선이 HW 비용 없이 달성됨을 확인) | ✅ 완료 | 2026-07-03 |
| HW | Stage 5 | R1 | 최초 DFX 구현(config1 static+NORMAL / config2 static+LOW_LIGHT), 트러블슈팅 5건 해결, pr_verify PASS | ✅ 완료 | 2026-07-02 |
| HW | Stage 5 | R2 | adversarial 수정 반영 재구현 → pr_verify PASS 유지, partition pin 2→15(메타데이터 수정이 물리 계층에 반영된 증거) | ✅ 완료 | 2026-07-02 |
| HW | Stage 5 | R3 | Vivado 시뮬레이션 latency 실측 시도(한계 확인) + pblock 클럭리전 편중 원인 규명 + PR 컨트롤러 1차 FSM 설계·시뮬레이션(word-count 기반) + pblock 재floorplan(용량 2배) | ✅⚠️🔄 완료(latency 실측 한계, PR컨트롤러 1차만) | 2026-07-02~03 |
| HW | Stage 5 | R4 | BLC fix + pblock 확장 결합 최종 재구현 → pr_verify PASS 유지, partial bitstream 2.11배 증가(자원여유 vs 재구성지연 트레이드오프 기록) | ✅ 완료 | 2026-07-03 |
| HW | Stage 6 | 1 | PS/DDR 통합(Block Design), GIC+DMA+PR 루프 드라이버 (Stage 5 PR컨트롤러 1차 설계 완성이 선결) | ⬜ 미착수 | — (보드 필요) |
| HW | Stage 6 | 2 | 실제 clock/reset 핀 배정 + 타이밍 제약(신 pblock 기준 WNS 재검증 포함) | ⬜ 미착수 | — (보드 필요) |
| HW | Stage 6 | 3 | 실제 PR latency 실측(trigger→완료, ICAP 실효 대역폭, XSA+JTAG+ILA) | ⬜ 미착수 | — (보드 필요) |
| HW | Stage 6 | 4 | 절대 전력(W) 측정, Arm1/2/3 비교 | ⬜ 미착수 | — (보드 필요) |
| HW | Stage 6 | 5 | DPU/검출기 end-to-end 실행(Vitis-AI, real-RAW, RGB32 직결) | ⬜ 미착수 | — (보드 필요) |
| HW | Stage 6 | 6 | Stage 3 BLC 완화가 real-RAW에서도 유효한지 최종 확인(DPU mAP vs SW 예측 정합) | ⬜ 미착수 | — (보드 필요) |

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

---

## Stage 2 — tone RM 산술 확정 + 이미지 지표 ✅

**목표:** RM_LOW_LIGHT_TONE(2x2 binning + gain×1.25 + gamma-4.0)과
RM_NORMAL_TONE(identity/옵션 gain·γ)의 파라미터를 이미지 지표로 확정.

- Policy A(H/2×W/2 그대로, upsample 없음) 채택 — DPU ABI 요구 시에만 Policy B 검토.
- arm별(none/normal/lowlight/adaptive) Y mean·std·포화율·dark-ratio 집계,
  gain/gamma 중복 플래그 항상 false(baseline core 무침범) 확인.

**근거:** `isppipeline/hls/results/stage1-3-results-2026-07-02.md`.

---

## Stage 3 — 정확도(mAP) 평가: arm & 조건표 + 알고리즘 개정 ✅ (3라운드)

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
[x] Stage 1  checker + 히스테리시스 시퀀스              (narrow band + N=3 최적)
[x] Stage 2  tone RM 산술 + 이미지 지표                 (Policy A 확정)
[x] Stage 3  정확도 mAP arm/조건표 + 알고리즘 개정       (3라운드: 최초→ver1/2→BLC완화, lowlight가 처음 normal 상회)
[x] Stage 4  HLS 합성 + C/RTL Co-sim                    (csynth 3라운드 완료; cosim 자동비교만 미완주)
[x] Stage 5  DFX PR 구현 + pr_verify + latency/컨트롤러  (4라운드, pr_verify 매 라운드 PASS; PR컨트롤러는 1차만)
[ ] Stage 6  보드 실장 + DPU end-to-end                  (보드 필요 — 유일하게 남은 단계)
범례: [x] 완료(⚠️/🔄 세부 한계 있어도 완료로 집계) · [ ] 미착수
```

> **핵심 발견(SW, Stage 0~3):** 모든 조건에서 `none`(무처리)이 mAP 최고라는
> 결론은 3라운드 내내 불변(SW proxy 천장 가설) — 그러나 BLC 완화로 `lowlight`가
> 처음으로 `normal`을 앞질렀고 격차가 크게 좁혀짐. DFX 정당화는 여전히
> 자원/전력이 우선이어야 함(방향 A 유지).
> **핵심 발견(HW, Stage 4~5):** gamma를 런타임 sqrt→ROM LUT로 바꿔 자원
> −88%/−78%; adversarial 수정으로 저조도 RM 자원 추가 −41.3%; **pr_verify는
> 4라운드 전부 PASS**로 DFX 전환 가능함을 실측 확인; pblock 확장(용량 2배)은
> partial bitstream·재구성 지연을 2.1배로 늘리는 명시적 트레이드오프.

## 즉시 다음 (우선순위)

1. **Stage 6 착수 선결 과제** — PR 컨트롤러의 `drain_ready`를 실제 RM
   `ap_idle`에 연결, BRAM 시뮬레이션 소스를 실제 SD/DDR 경로로 교체.
2. **Stage 6 순서 1~2** — PS/DDR 통합(Block Design) → 신 pblock 기준
   clock/reset 핀 배정 + WNS 재검증.
3. **(선택) Stage 5 open item** — partition pin 수 15→3 감소 원인 조사
   (SPEC.md §10에 미조사로 기록됨).
4. **(선택) Stage 4 cosim 완주** — WSL2+XSIM 하네스 SIGSEGV 원인(struct-pointer
   인터페이스 추정) 해소.

## 주의 (지어내지 않기)

- Stage 6(보드) 수치는 실물 보드 없이는 `TODO(측정)`(재구성 지연 실측치,
  전력, DPU 정확도) — 분석적 추정치(§Stage 5)와 시뮬레이션 실측치(PR 컨트롤러)는
  있으나 보드 실측으로 반드시 재검증해야 한다.
- 구 08/11(2026-06-29 이전) mAP 수치는 ablation arm(구 variant) 기준 —
  현재 서사(Stage 3 최종 라운드)에 직접 인용 금지.

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
