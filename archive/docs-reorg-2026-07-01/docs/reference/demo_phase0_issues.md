# Phase 0 — 기준선 검증 결과 보고서

**검증일:** 2026-05-19  
**대상:** `~/isp/pr_cnn/project/isppipeline/demo`  
**툴:** Vitis HLS 2024.1 / Vivado 2024.1 / xsim (standalone)

---

## 1. HLS C-Simulation 결과 (#1~#3)

| 커널            | 테스트 케이스                                | 결과               |
| --------------- | -------------------------------------------- | ------------------ |
| `checker`       | Normal Light / Low Light                     | ✅ PASS (0 errors) |
| `pr_controller` | Draining→Reconfiguring / Reconfiguring→Ready | ✅ PASS (0 errors) |
| `binning_gain`  | Mode 0 pass-through / Mode 1 binning+gain    | ✅ PASS (0 errors) |

**판정:** HLS 커널 3개 기능 정확성 이상 없음.

---

## 2. RTL 시뮬레이션 결과 (#4~#5)

### 2-1. NORMAL → LOW_LIGHT 전환 (tb_top_transition.v)

| Phase   | 검증 항목                                    | 결과          |
| ------- | -------------------------------------------- | ------------- |
| PHASE 1 | NORMAL 모드 pass-through (pixel_out=100)     | ✅ 16/16 PASS |
| PHASE 2 | FSM: IDLE→DRAINING→RECONFIGURING→DONE        | ✅ 정상 전이  |
| PHASE 2 | `rp_reset=1` DRAINING 구간 유지              | ✅ 확인       |
| PHASE 3 | LOW_LIGHT 모드 (pixel_out=60, 4픽셀당 1출력) | ✅ 5/5 PASS   |

### 2-2. LOW_LIGHT → NORMAL 역전환 (tb_top_reverse.v, 신규)

| Phase   | 검증 항목                          | 결과          |
| ------- | ---------------------------------- | ------------- |
| PHASE 1 | LOW_LIGHT 진입 FSM 구동            | ✅ 정상       |
| PHASE 2 | LOW_LIGHT 동작 검증 (pixel_out=60) | ✅ 5/5 PASS   |
| PHASE 3 | NORMAL 역전환 FSM 재구동           | ✅ 정상       |
| PHASE 4 | NORMAL 모드 복귀 (pixel_out=100)   | ✅ 16/16 PASS |
| 최종    | `[PASS] 역전환 시뮬레이션 완료`    | ✅            |

**판정:** 양방향 PR 전환 시나리오 기능적으로 정상 동작 확인.

---

## 3. pr_verify 결과 (#6)

```text
INFO: PR Verify Summary
  Static tiles compared       : 21,125
  Static sites compared       : 35
  Static cells compared       : 120
  Static routed nodes compared: 1,227
  Static routed pips compared : 1,135
  Partition pins compared     : 20

INFO: check points config1/routed.dcp and config2/routed.dcp are compatible
```

**판정: ✅ PASS** — Config 1 / Config 2 Static Region 완전 일치. DFX 요건 충족.

---

## 4. DRC / Timing 결과 (#7)

### 4-1. Timing (모두 통과)

|                   | Config 1               | Config 2               |
| ----------------- | ---------------------- | ---------------------- |
| WNS               | **+6.603 ns**          | **+6.121 ns**          |
| WHS               | +0.057 ns              | +0.046 ns              |
| Failing endpoints | 0 / 57                 | 0 / 101                |
| 판정              | ✅ All constraints met | ✅ All constraints met |

10 ns 클럭 기준 크리티컬 패스 ≈ 3.4 ns. 여유 매우 충분.

### 4-2. DRC 위반 목록

| ID  | Rule       | Severity         | Config1 | Config2 | 내용                                        | 조치                      |
| --- | ---------- | ---------------- | ------- | ------- | ------------------------------------------- | ------------------------- |
| D-1 | `UCIO-1`   | Critical Warning | ✗       | ✅      | 20/22 포트 LOC 미지정 (bitstream 생성 차단) | Phase 1에서 pin 할당      |
| D-2 | `HDPR-32`  | Warning          | ✗       | ✗       | `RESET_AFTER_RECONFIG` ZCU104 불필요        | `pblocks_zcu104.xdc` 수정 |
| D-3 | `HDPRA-56` | Advisory         | ✗×2     | ✗×2     | pblock narrow gap (X53/X56 열)              | `resize_pblock` 적용 권장 |

> Config2에서 UCIO-1이 사라지는 이유: `design_utils.tcl`의 `generate_dfx_bitstreams`에서 `set_property SEVERITY {Warning}` 처리가 포함되기 때문. Config1 단독 DRC에는 해당 처리가 없어 그대로 노출됨.

---

## 5. 버그 목록 (Phase 0 발견)

| ID      | 파일                              | 유형        | 내용                                                                                    | 상태             |
| ------- | --------------------------------- | ----------- | --------------------------------------------------------------------------------------- | ---------------- |
| **B-1** | RTL 5개 파일                      | 컴파일 오류 | `` `timescale `` 선언 누락 → xsim FATAL ERROR                                           | ✅ **수정 완료** |
| **B-2** | `hdl/tb/tb_top_transition.v:L110` | TB 결함     | 700 ns timeout으로 final summary 미출력 (테스트 결과는 정상)                            | ⚠️ 미수정        |
| **B-3** | `hdl/static/checker_wrapper.v`    | 로직 의심   | mode_changed가 8픽셀이 아닌 6~7픽셀에서 발생 (reset 경계 cnt 초기화 타이밍 불일치 의심) | 🔍 조사 필요     |

---

## 6. Phase 1 진입 조건 (Go / No-Go)

| 조건                               | 상태                                        |
| ---------------------------------- | ------------------------------------------- |
| HLS C-Sim 3개 PASS                 | ✅                                          |
| pr_verify PASS                     | ✅                                          |
| 양방향 RTL 시뮬 기능 PASS          | ✅                                          |
| Timing violations 없음             | ✅                                          |
| Critical DRC (bitstream 차단) 해소 | ⚠️ D-1 미해소 (HW 실증 전에 해결 필요)      |
| B-3 checker 오프셋 원인 규명       | ⚠️ Phase 1에서 histogram 방식으로 교체 예정 |

**→ Phase 1 진입 가능.** D-1(pin 할당)은 HW 실증 단계 전까지 해결, B-3는 Phase 1 checker 강화 작업에서 근본 해결.
