# DFXISP — NotebookLM 소스팩 (2026-06-28)

> 목적: NotebookLM이 이 문서를 source로 삼아 **(1) 리포트, (2) 표(Tab1~Tab4) 내용**을 생성하게 한다.
> Figure(Fig2/Fig3)는 NotebookLM이 벡터 도식을 못 만들므로, 아래 ASCII 초안·사양을 근거로 별도 작도 단계에서 그린다.
> 함께 넣을 source: `00-thesis-outline.md`, `dfxisp-A1-architecture-fpga-constraints-2026-06-23.md`, `dfxisp-4-contribution-research-plan-2026-06-26.md`.

## 1. 확정된 설계 결정 (2026-06-28)
1. **low-light RM:** DFX-Bin + DFX-FP 둘 다. DFX-FP = main(=green-guided, Bayer G채널 활용, SimROD 계열), DFX-Bin = 비교/ablation·fallback.
2. **해상도·FPS:** 개발 640×480 → 평가 1280×720@30fps. frame budget 33.3ms = PR latency 예산 기준.
3. **비교군:** static / register-only / DFX-Bin / DFX-FP 4-variant 고정.
4. **Metric:** COCO/ExDark pseudo-RAW mAP 1차. real RAW(LOD/NOD/AODRaw)는 관련연구+향후연구.

## 2. 핵심 기여 4가지
1. Hybrid register/DFX adaptation policy (빠른 파라미터 = register/LUT, 구조적 = DFX-RM)
2. Task-aware low-light RM (mAP 목표, human-quality 아님)
3. DFX-aware mode scheduler (PR latency·drain·switch·thrashing 고려, 장면 단위)
4. ZCU104 evidence package (4-variant 실측)

## 3. 표 사양 — NotebookLM이 내용 채울 것

### Tab1 — Adaptation 분리 정책 (기여 1)
열: Adaptation type | Examples | Implementation | PR 필요? | 근거
행: Parameter adaptation(gain/gamma/AWB/CCM/threshold/LUT) / Structural adaptation(binning, low-light denoise, local contrast/tone, feature-preserving RM)

### Tab2 — Low-light RM 후보 비교 (기여 2)
열: Variant | RM | Core op | 기대 강점 | 리스크
행: DFX-Bin / DFX-FP(green-guided, 확정 main) / (참고: DarkISP-lite, Guided)

### Tab3 — 실험 비교군 (4-variant)
열: Variant | Adaptation | Low-light block | DFX? | 목적
행: static / register-only / DFX-Bin / DFX-FP

### Tab4 — ZCU104 Evidence Package (값은 TODO(측정))
열: Evidence | static | reg-only | DFX-Bin | DFX-FP
행: mAP(COCO) / mAP(ExDark) / LUT·FF·BRAM·DSP / Power / FPS / Register update latency / Partial bitstream size / PR latency / Switch·thrashing / bit-exact mismatch
※ 모든 값은 `TODO(측정)`로 표기, 단정 금지.

## 4. Figure 사양 (별도 작도용 — ASCII 초안)

### Fig2 — 제안 파이프라인 + 적응 분리
```
RAW Bayer(pseudo-RAW) ─► [Front-end: demosaic/AWB/CCM]
        │                         │ register/LUT (fast path)
        │                         ▼
        │                 gain·gamma·threshold (AXI-Lite)
        ▼
  Scene checker(dark_ratio) ─► Mode FSM
        │                         │ DFX (slow path)
        ▼                         ▼
   [DFX Region(RP)] ◄── partial bitstream ── {DFX-Bin | DFX-FP}
        ▼
   RGB out ─► DPU (object detection)
```
사양: fast path(register/LUT)와 slow path(DFX-RM 교체)를 시각적으로 분리, RP 경계 강조.

### Fig3 — DFX-aware mode scheduler 상태도
```
        dark_ratio>Th_hi (N프레임 지속)
NORMAL ───────────────────────────────► LOW_LIGHT
   ▲   dwell≥Dmin & dark_ratio<Th_lo        │
   └────────────────────────────────────────┘
   (drain/reconfig invalid window 동안 frame skip 표시)
```
사양: hysteresis(Th_hi/Th_lo), minimum dwell, drain/invalid window, switch count 로깅 포인트 표시.

## 5. 리포트 요청 (NotebookLM 생성)
다음 구조의 한글 리포트:
1. 연구 개요·문제정의 (machine-vision AI-ISP를 HW 적응 관점으로 재정의)
2. 기여 4가지 요약
3. 확정 설계 결정과 근거
4. 비교군·평가 계획 (Tab3·Tab4 기반)
5. 관련연구 대비 차별점 (DynamicISP/AdaptiveISP/Dark-ISP/SimROD/Vitis Vision 대비)
6. 리스크·한계 (pseudo-RAW 한계, PR latency, DFX-FP 튜닝)

## 6. 작성 원칙
- 한글 본문 + 영어 기술용어.
- 미검증 수치는 `TODO(측정)`. 성능 주장은 데이터셋·조건·모델·입력경로 함께.
- 확인된 사실과 가설 구분.
