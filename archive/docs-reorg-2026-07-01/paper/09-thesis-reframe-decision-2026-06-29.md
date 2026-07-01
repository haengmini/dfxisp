---
type: decision-log
title: "DFXISP — 논문 방향 A 채택 (resource/power 재편)"
created: 2026-06-29
---

# 방향 A 채택 결정 (2026-06-29)

## 결정
논문을 **방향 A**로 재편: DFX의 가치를 **mAP 향상이 아니라 자원/전력 절감**으로 재정의. **정확도(mAP)는 register-fast path**가 담당, mAP는 **guardrail**로만 사용.

## 근거 (실측, [[08-e2-map-results]])
- real-low-light(ExDark, n=260, yolov8n/s 동일): reg_only 최고, DFX-FP 최저 → detail-boost RM은 저조도 mAP에 해로움.
- COCO 전체: 저조도 처리는 정상조도에서 무익 → 장면 적응 스위칭 필요.

## 세부 결정 완료 (2026-06-29)
1. **DFX 1순위 RM = DFX-Bin(2×2 binning).** (DFX-FP는 ablation/부정사례)
2. **mAP guardrail Δ = register-only 대비 절대 1.0 mAP point(@[.5:.95], ≈ 상대 5%) 이내.**
3. **자원 비교 main baseline = static all-resident**(normal+저조도 블록 상시 상주, DFX 없음).

> 용어 주의: mAP 변종 `static`(demosaic-only, 정확도 참조) ≠ 자원 baseline `static all-resident`(HW 구성, 면적/전력 참조).

## 변경된 문서
- `00-thesis-outline.md`(제목·statement·기여4·지표·결정), `01-thesis-draft.md`(1.3/1.4/5.1/6.1/6.2),
  `04-implementation-rm-spec.md`(DFX-FP ablation화), `05-experiment-protocol.md`(baseline/guardrail), 본 문서.

## 재편 프레임 (4기여)
C1 Resource-aware register/DFX partitioning · C2 mAP-guardrail RM screening ·
C3 DFX-aware scene scheduler · C4 ZCU104 resource/power evidence(mAP guardrail).

## 다음 (구현/측정)
- DFX-Bin RM HLS(csynth 자원수치) → static all-resident 대비 절감 측정.
- guardrail 확인: DFX-Bin mAP가 register-only −1.0pt 이내인지(예비: COCO n=347 bin 0.246 vs reg 0.295 → 현 binning은 guardrail 초과, RM/게인 튜닝 필요).
