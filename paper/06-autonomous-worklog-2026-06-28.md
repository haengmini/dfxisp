---
type: worklog
title: "DFXISP — 자율 실행 worklog & 자기피드백 (ZCU104 실측 직전까지)"
project: DFXISP
created: 2026-06-28
scope: "설계·구현사양·실험설계·문서·figure·table·report 완성 + 보드 실측 빈 레이아웃"
---

# 자율 실행 worklog (2026-06-28)

## 0. 목표
"ZCU104 실측 직전까지" 모든 단계를 스스로 계획·작업·피드백·분석하고 figure/table/report를 생성. 보드 실측은 빈 레이아웃으로 남김.

## 1. 한 일 (산출물)
| # | 산출물 | 위치(paper/) | 상태 |
|---|---|---|---|
| 결정 | 4 Open Q 확정, outline 갱신 | 00-thesis-outline.md | 완료 |
| 그림 | Fig1–Fig6 Mermaid 작도, Fig7/8 빈 레이아웃 | 03-figures-tables.md | 완료 |
| 표 | Tab1–Tab3 작성, Tab4–Tab7 빈 레이아웃 | 03-figures-tables.md | 완료 |
| 구현사양 | DFX-Bin/DFX-FP 알고리즘·ABI·HLS 계획·골든 | 04-implementation-rm-spec.md | 완료 |
| 본문 | 1~6장 서술 완결(측정값만 TODO) | 01-thesis-draft.md | 완료 |
| 실험 | 프로토콜(SW/HW 단계 분리) + 빈 CSV 5종 | 05-experiment-protocol.md, measurements/ | 완료 |
| 리포트 | NotebookLM 종합 브리핑 + 4-contribution 리포트 | notebooklm-*.md | 완료 |
| 표(데이터) | NotebookLM evidence 표(CSV) | notebooklm-evidence-table-*.csv | 완료 |
| 슬라이드 | NotebookLM 발표 덱(PDF) | notebooklm-slides-*.pdf | 완료 |

## 2. 단계 지도 — 어디까지 했나
```
[SW · 보드 불필요]  ✅ 설계 ─ ✅ RM 사양 ─ ✅ 본문 ─ ✅ figure/table ─ ✅ 실험설계 ─ ✅ report/slides
        │                                  (가능: C-sim S1~S3, pseudo-RAW mAP E1~E2, scheduler sim E3)
        ▼
[HW · ZCU104 필요]  ⬜ csynth/cosim ─ ⬜ Vivado DFX ─ ⬜ 보드 측정   ← 빈 레이아웃(measurements/*.csv)
```

## 3. 자기피드백 / 분석 (산출물 비평)
- **figure:** Mermaid는 구조 전달엔 충분하나 학위논문 제출본은 vector(eps/pdf) 재작도 필요(03 문서에 명시). Fig4 플로어플랜은 개념도 — 실제 Pblock은 Vivado 후 확정.
- **본문:** 서술은 완결됐으나 2.4 차별점·6장 결론은 실측 결과가 들어가야 설득력이 완성됨(현재는 "검증 틀"까지). 인용은 02-references의 임시 BibTeX key — 학교 양식 확정 후 정식 변환 필요.
- **RM 사양:** DFX-FP의 파라미터(knee/strength/α)가 많아 튜닝 부담 → SW 단계(E2)에서 mAP 기준으로 먼저 좁히는 것을 권장. RP 면적 초과 시 fallback(3×3, strength 축소) 명시함.
- **실험:** mAP 평가(E2)는 detector·평가코드 버전 고정이 결과 신뢰성의 핵심 — 프로토콜에 비고로 강제함. pseudo-RAW 한계는 6.2에 명시.
- **NotebookLM:** report/table/slide 모두 TODO(측정) 규칙을 지켜 생성됨. 다만 LLM 생성물이라 수치·인용은 본문 정본과 교차검증 후 채택할 것(생성물=초안).
- **리스크 Top3:** ① DFX-FP RP timing/면적 ② PR latency vs dwell 예산 ③ pseudo-RAW↔real RAW gap.

## 4. 보드 단계에서 할 일 (인계)
1. Vitis HLS: `make -C isppipeline/hls DFXISP_HLS_FLOW=csynth hls` → resource.csv/pr_latency.csv 초기치.
2. Vivado DFX flow: static+RP, 부분 비트스트림 2종 → resource.csv 확정.
3. ZCU104: power/FPS/PR latency/frame stall → power_perf.csv, pr_latency.csv.
4. measurements/*.csv 채우면 [Tab4–Tab7], [Fig7/8] 자동 완성 → 5장·6장 정량 결론 작성.

## 5. SW 단계 추가 권장(보드 전 선행 가능)
- C-sim RP 분리(S1) + DFX-FP C-sim(S3) + 확장 golden → bit-exact 확보.
- pseudo-RAW mAP(E2)로 DFX-Bin vs DFX-FP 사전 비교 → DFX-FP 파라미터 1차 고정.
- scheduler 시뮬(E3)으로 hysteresis 효과 사전 확인.
→ 이 3가지는 보드 없이 가능하며, 끝내두면 보드 단계가 측정-only로 단축됨.

## 6. 메모
- Drive 정리(데이터셋/실험기록 정본 통합, 중복 archive)와 GitHub 정본화는 2026-06-28 완료.
- NotebookLM notebook: "DFXISP Thesis (2026-06-28)" (소스 8종).
