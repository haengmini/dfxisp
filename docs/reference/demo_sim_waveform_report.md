# 파형 분석 레포트 — Dataset_demo 10장 순차 입력

**데이터셋:** 1high→1low→22high→22low→23high→23low→55high→55low→79high→79low  
**DUT:** top_sim.v — checker(FRAME_SIZE=16) + pr_controller + icap_controller(8 words) + RP + ISP  
**클럭:** 100 MHz (10 ns) | **전체 시뮬:** 31,405 ns (31.4 µs)

---

## 0. 파형 열기 (Vivado TCL)

### 방법 A — 터미널에서 직접 (가장 간단)

```bash
! xsim --gui /home/mini/isp/pr_cnn/project/isppipeline/demo/sim_out/xsim_dataset/sim_dataset.wdb
```

### 방법 B — Vivado TCL 콘솔에서 실행

Vivado GUI의 **Tcl Console** 탭에 입력:

```tcl
exec xsim /home/mini/isp/pr_cnn/project/isppipeline/demo/sim_out/xsim_dataset/sim_dataset.wdb --gui &
```

### 방법 C — xsim 스냅샷 재컴파일 후 GUI 열기

```bash
! cd /home/mini/isp/pr_cnn/project/isppipeline/demo/sim_out/xsim_dataset && \
  xsim tb_dataset_snap --gui --wdb sim_dataset.wdb
```

---

### xsim GUI에서 신호 추가 방법

**GUI 방법:**

1. 좌측 **Scope** 패널 → `tb_top_dataset` 클릭
2. 하단 **Objects** 패널에 신호 목록 표시
3. 아래 신호 그룹 선택 → 우클릭 → **Add to Wave Window**
4. `F` 키 → **Zoom Fit** (전체 타임라인)

**TCL 방법 (xsim TCL 콘솔에서):**

```tcl
# 핵심 신호만 선택 추가
add_wave {{/tb_top_dataset/clk}}
add_wave {{/tb_top_dataset/pixel_valid}}
add_wave {{/tb_top_dataset/pixel_in}}
add_wave {{/tb_top_dataset/mode_out}}
add_wave {{/tb_top_dataset/mode_changed}}
add_wave {{/tb_top_dataset/rp_reset_out}}
add_wave {{/tb_top_dataset/icap_start_out}}
add_wave {{/tb_top_dataset/pixel_out_valid}}
add_wave {{/tb_top_dataset/pixel_out}}
```

**확인 권장 구간:**

| 구간         | 내용                                                 |
| ------------ | ---------------------------------------------------- |
| 0 ~ 4 µs     | 1high 입력 → 전환 없음, 1low 입력 → LOW_LIGHT 전환 ① |
| 3.3 ~ 6.1 µs | mode_changed → rp_reset → icap_start → icap_done     |
| 0 ~ 31 µs    | 전체 9회 반복 전환 패턴                              |

---

## 1. 전체 이벤트 타임라인

| 이미지 | 기대모드  | mode_changed (ns) | 전환 방향            | ICAP_START (ns) | ICAP_DONE (ns) | 판정 |
| ------ | --------- | ----------------- | -------------------- | --------------- | -------------- | ---- |
| 1high  | NORMAL    | —                 | 변화 없음 (dark≈5%)  | —               | —              | ✅   |
| 1low   | LOW_LIGHT | 3,335             | NORMAL→**LOW_LIGHT** | 5,735           | 6,085          | ✅   |
| 22high | NORMAL    | 6,475             | LOW_LIGHT→**NORMAL** | 8,875           | 9,225          | ✅   |
| 22low  | LOW_LIGHT | 9,615             | NORMAL→**LOW_LIGHT** | 12,015          | 12,365         | ✅   |
| 23high | NORMAL    | 12,755            | LOW_LIGHT→**NORMAL** | 15,155          | 15,505         | ✅   |
| 23low  | LOW_LIGHT | 15,895            | NORMAL→**LOW_LIGHT** | 18,295          | 18,645         | ✅   |
| 55high | NORMAL    | 19,035            | LOW_LIGHT→**NORMAL** | 21,435          | 21,785         | ✅   |
| 55low  | LOW_LIGHT | 22,175            | NORMAL→**LOW_LIGHT** | 24,575          | 24,925         | ✅   |
| 79high | NORMAL    | 25,315            | LOW_LIGHT→**NORMAL** | 27,715          | 28,065         | ✅   |
| 79low  | LOW_LIGHT | 28,455            | NORMAL→**LOW_LIGHT** | 30,855          | 31,205         | ✅   |

**모드 결정 정확도: 10/10 (100%) | mode_changed: 9회 | icap_done: 9회**

---

## 2. 반복 모드 전환 패턴 (ASCII 파형)

```
시각(µs)  0    3    6    9   12   15   18   21   24   27   31
          |────|────|────|────|────|────|────|────|────|────|
pixel_val _↑‾‾‾‾‾‾‾‾↓_↑‾‾‾‾‾‾↓_↑‾‾‾‾‾‾↓_↑‾‾‾‾‾‾↓_↑‾‾‾‾‾‾↓_↑‾↓
mode_out  ____________↑‾‾‾↓‾‾‾↑‾‾‾↓‾‾‾↑‾‾‾↓‾‾‾↑‾‾‾↓‾‾‾↑‾‾‾
rp_reset  ___________↑‾‾↓__↑‾‾↓__↑‾‾↓__↑‾‾↓__↑‾‾↓__↑‾‾↓__↑‾
icap_strt ____________↑↓___↑↓___↑↓___↑↓___↑↓___↑↓___↑↓___↑↓

이미지:   1h   1L  22h 22L  23h 23L  55h 55L  79h 79L
모드:      N    LL   N   LL   N   LL   N   LL   N   LL
```

> **N** = NORMAL, **LL** = LOW_LIGHT  
> 1high: dark≈5% < HYSTERESIS_HI(40%) → 전환 없음 (히스테리시스 정상)

---

## 3. 전환 타이밍 분석 (9회 동일)

| 전환# | 이미지 | MC (ns) | ICAP_START | ICAP_DONE | DRAINING | ICAP   | 전체 PR 지연 |
| ----- | ------ | ------- | ---------- | --------- | -------- | ------ | ------------ |
| ①     | 1low   | 3,335   | 5,735      | 6,085     | 2,400 ns | 350 ns | **2,750 ns** |
| ②     | 22high | 6,475   | 8,875      | 9,225     | 2,400 ns | 350 ns | **2,750 ns** |
| ③     | 22low  | 9,615   | 12,015     | 12,365    | 2,400 ns | 350 ns | **2,750 ns** |
| ④     | 23high | 12,755  | 15,155     | 15,505    | 2,400 ns | 350 ns | **2,750 ns** |
| ⑤     | 23low  | 15,895  | 18,295     | 18,645    | 2,400 ns | 350 ns | **2,750 ns** |
| ⑥     | 55high | 19,035  | 21,435     | 21,785    | 2,400 ns | 350 ns | **2,750 ns** |
| ⑦     | 55low  | 22,175  | 24,575     | 24,925    | 2,400 ns | 350 ns | **2,750 ns** |
| ⑧     | 79high | 25,315  | 27,715     | 28,065    | 2,400 ns | 350 ns | **2,750 ns** |
| ⑨     | 79low  | 28,455  | 30,855     | 31,205    | 2,400 ns | 350 ns | **2,750 ns** |

- **DRAINING 2,400 ns (240 클럭)**: pipeline_empty 대기 — PR 지연의 87%
- **ICAP 전송 350 ns (35 클럭)**: 8 words × (REQ+WAIT+SEND) = 24 clk
- **전환 주기 3,140 ns**: 이미지 입력(2,560ns) + checker(320ns) + 간격(260ns)
- **9회 완전히 동일**: 결정론적 동작 확인

---

## 4. pr_controller FSM 상태 전이 (1회 기준, ×9 반복)

```
  IDLE ──(trigger)──▶ DRAINING ──(pipeline_empty)──▶ RECONFIGURING
   ▲                                                         │
   └──────────────── DONE ◀──────────(icap_done) ───────────┘

시뮬 타이밍 (첫 번째 전환):
  IDLE→DRAINING     : 235 → 245 ns   (10 ns, 1 클럭)
  DRAINING→RECONFIG : 245 → 2,635 ns (2,390 ns, pipeline_empty 대기)
  RECONFIG→DONE     : 2,635 → 2,985 ns (350 ns, ICAP 전송)
  DONE→IDLE         : 2,985 → 3,005 ns (20 ns, 2 클럭)
```

---

## 5. 실제 하드웨어 환경 추정 (97 MHz, 370,560 words)

| 단계                         | 시뮬 (8 words) | 실제 (370,560 words, single-beat) | 실제 (burst 최적화) |
| ---------------------------- | -------------- | --------------------------------- | ------------------- |
| DRAINING                     | 2,400 ns       | 동일 (픽셀 스트림 의존)           | 동일                |
| ICAP 전송                    | 350 ns         | **~45 ms**                        | **~9 ms**           |
| 전체 PR 지연                 | 2,750 ns       | **~50 ms**                        | **~15 ms**          |
| AXI-Lite params (Strategy A) | 병렬 실행      | ~52 µs (ICAP 중 선처리)           | 동일                |
| icap_done → ap_start         | 10 ns          | ~200 ns                           | ~200 ns             |

---

## 6. 검증 요약

| 검증 항목            | 결과            | 근거                                     |
| -------------------- | --------------- | ---------------------------------------- |
| 모드 결정 정확도     | ✅ 10/10 (100%) | dark% 기준 정확 분류                     |
| 반복 mode_changed    | ✅ 9회          | 9장 이미지 전환마다 펄스                 |
| 반복 icap_done       | ✅ 9회          | 전환마다 ICAP 완료                       |
| pr_controller FSM ×9 | ✅              | IDLE→DRAIN→RECONFIG→DONE→IDLE 반복       |
| 전환 방향 교번       | ✅              | N↔LL 정확히 교번                         |
| 1high 전환 없음      | ✅              | dark=5% < 40% 히스테리시스 정상          |
| icap_done 펄스       | ✅              | 매회 정확히 1클럭(10 ns)                 |
| 타이밍 결정론적      | ✅              | 9회 모두 DRAINING=2400, ICAP=350 ns 동일 |
| **전체 결론**        | **✅ ALL PASS** |                                          |

**전체 시뮬 시간:** 31,405 ns (31.4 µs)  
**VCD 파형:** `sim_out/xsim_dataset/sim_dataset.vcd` (69 KB)  
**WDB 파형:** `sim_out/xsim_dataset/sim_dataset.wdb` (86 KB)
