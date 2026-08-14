# DFXISP HLS C-sim 스캐폴드

로컬 저장소 경로: `isppipeline/hls/`. 정본 아키텍처 문서: 저장소 루트 `RESEARCH.md`.

## 목표 (reset 2026-07-01)

이 스캐폴드는 **shared baseline ISP core + 상호배타 tone RM slot** 구조의 첫
결정적(deterministic) C-시뮬레이션 대상이다. tone RM slot이 shared baseline core를
**감싸는(wrap)** 형태다:

```text
NORMAL:
  pseudo-RAW Bayer RGGB uint16
    -> checker (mode 결정)
    -> RM_NORMAL_TONE (gain 1.25x + gamma2.0)
    -> baseline ISP core (demosaic + BLC + WB + CCM, 12-bit, gain/gamma 없음)
    -> packed RGB888 uint32  (H x W)

LOW_LIGHT:
  pseudo-RAW Bayer RGGB uint16
    -> checker (mode 결정)
    -> RM_LOW_LIGHT_TONE.front : 2x2 RAW binning (precision loss 전, RESEARCH §4.2)
    -> baseline ISP core (demosaic + BLC + WB + CCM, 12-bit, gain/gamma 없음)
    -> RM_LOW_LIGHT_TONE.back  : low-light gain 2.0x + gamma2.0 tone
    -> packed RGB888 uint32  (H/2 x W/2, Policy A 형상변경)
```

C-sim이 증명하는 불변식(RESEARCH.md §8.2):

- 프레임마다 **정확히 하나의 tone RM**만 선택(mutually exclusive).
- gain/gamma는 **tone RM에만** 존재하고 baseline core에는 중복되지 않음.
- 출력 메타데이터가 mode·선택 RM·출력 형상을 보고.

의도적으로 Ponytail 스타일이다: 작은 HLS top 하나, stdlib만 쓰는 C-sim, 로컬 smoke
테스트에 Vitis 의존성 없음, Vitis HLS/Vitis flow용 HLS pragma는 보존.

## 파일 구조

```text
isppipeline/hls/
├── Makefile                — csim/golden/report/HLS 진입점. `rm-golden`/`rm-csim`/
│                              `rm-verify`/`analysis`는 은퇴한 v1 RM 트랙을 가리키는
│                              명시적 stub(§"로컬 C-sim 실행" 참고)
├── README.md                — 이 문서
├── vitis_hls.log             — 마지막 vitis_hls 실행 세션 로그(잔여물)
│
├── src/                      — HLS C++ 소스(csim + Vitis HLS 합성 대상)
│   ├── dfxisp_accel.cpp      — 배포 unified top: checker + baseline core + RM_NORMAL_TONE/RM_LOW_LIGHT_TONE
│   ├── checker.cpp           — standalone checker HLS IP 소스(checker_scan top, checker/ 패키징용)
│   ├── default_isp.cpp       — default_ISP arm(Vitis Vision 정렬, 2026-08-06 신규)
│   ├── default_isp.md / default_isp_v2.md
│   ├── lowlight_isp.cpp      — lowlight_ISP v2 arm(2026-08-06 신규, binning+gain+gamma2.0)
│   └── lowlight_isp.md
├── include/                  — 각 top의 헤더(mode/RM enum, 인터페이스, 4-scalar 메타데이터 출력)
│   └── {dfxisp_accel,checker,default_isp,lowlight_isp}.hpp
├── tests/                    — C-sim 테스트벤치 + bit-exact golden CSV
│   ├── test_dfxisp_csim.cpp + golden_vectors.csv
│   ├── test_default_isp_csim.cpp + default_isp_golden_vectors.csv
│   ├── test_lowlight_isp_csim.cpp + lowlight_isp_golden_vectors.csv
│   ├── test_rm_csim.cpp + rm_golden_vectors.csv      (rm-verify는 비활성 — 은퇴한 v1 RM 트랙, 아래 참고)
│   └── golden_csv.hpp         — 공용 CSV 파서(2026-08-06 ponytail 리뷰로 3중복 통합)
├── tools/                    — golden 생성기·검증 스크립트(2026-08-14: 2026-08-07 restructure로
│   │                           archive에 갔던 7개를 복원, 아래 참고)
│   ├── gen_golden_vectors.py     — `src/dfxisp_accel.cpp` bit-exact golden 생성기(`make golden`)
│   ├── gen_verification_report.py — `reports/latest.md` 생성기(`make report`)
│   ├── verify_binning_cross_check.py / verify_demosaic_bilinear_cross_check.py
│   │     — 독립 3자 fuzz 교차검증 gate(`make cross-check`)
│   ├── internal_edge_smoke.py    — 극소/홀수 그리드 + demosaic 경계 회귀(`make py-verify`)
│   ├── baseline_isp_pipeline.py / low_light_isp_pipeline.py — 위 cross-check들의 독립
│   │     구현 오라클(v1 SW-eval proxy, v2 이관 후 이 용도로만 복원)
│   ├── scheduler_sim.py / scheduler_sweep.py — 스케줄러 정책 시뮬레이션(`make scheduler`)
│   ├── build_hw_dataset.py
│   ├── calibrate_noise_model.py  — 실 RAW 노이즈 모델(σ²=a·y+b) 추정, GAT ablation 상수용
│   └── camera_wb.json / sonynod_{boundary31,flip13}.json
├── scripts/                  — Vitis HLS / Vivado DFX Tcl
│   ├── vitis_hls.tcl          — HLS 프로젝트 스캐폴드(csim/csynth/cosim/export, top은 env로 지정)
│   ├── vitis_hls_wave.tcl
│   └── dfx/                   — DFX flow(controller 생성, flat-arm impl, bitstream 작성)
├── checker/                  — standalone checker HLS IP 패키징(Vivado IP repo)
│   ├── checker_ip.v / checker_hysteresis.v(+tb) / dfxc_trigger_adapter.v(+tb)
│   ├── package_checker_ip.tcl / synth_checker.tcl
│   └── ip_repo/                — 패키징된 Vivado IP(component.xml + 합성 RTL)
├── reports/                  — 최신 csynth/postroute 실측 리포트(git 추적, 정본)
│   ├── latest.md               — make report 산출물(2026-08-14 재생성, 동작)
│   ├── csynth/*.rpt            — top별 C-synthesis 리포트
│   └── postroute/*.rpt         — arm1/2/3 post-route timing/utilization
├── results/                  — 실험/HW 실측 산출물 아카이브 — **읽을 땐 results/INDEX.md부터**
│   ├── INDEX.md
│   ├── pr_controller/, icap_sim/  — PR latency RTL/TB
│   └── archive/                — superseded 문서/CSV(git mv만, 삭제 없음)
│
├── build/            (gitignored) — g++ 로컬 csim 바이너리 + build/vitis_hls/<top>/ HLS 프로젝트
├── data/             (gitignored) — 실험 렌더 산출물(대용량 데이터셋 파생물)
└── runs/             (gitignored) — YOLO 검출 val 산출물
```

관련 위치(`isppipeline/hls/` 바깥):

- `isppipeline/sw/` — v2 golden 생성기/검증 스크립트의 **정본** 위치: `checker.py`,
  `default_isp_pipeline.py` + `gen_default_isp_golden.py`, `lowlight_isp_pipeline.py` +
  `gen_lowlight_isp_golden.py`, `verify_new_arm_pipelines.py`(2026-08-14 이관).
  `sw/sim/{AWB,blc,binning,checker,gain,gamma}/`에 관련 실험 노트. `isppipeline/hls/tools/`의
  cross-check 스크립트들이 여기 `checker.py`/`low_light_isp_pipeline.py`(*)를
  `sys.path.insert`로 import한다(*이건 sw/에 없고 hls/tools/ 자체에 오라클로 복원돼 있음,
  아래 참고).
- `archive/isppipeline-sw-cleanup-2026-08-07/tools/` — **2026-08-14에 대부분 복원 완료.**
  `gen_golden_vectors.py`/`gen_verification_report.py`/`scheduler_sim.py`/
  `scheduler_sweep.py`/`verify_binning_cross_check.py`/`verify_demosaic_bilinear_cross_check.py`
  /`internal_edge_smoke.py`/`baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`를
  `isppipeline/hls/tools/`로 `git mv`, Makefile `golden`/`verify`/`report`/`cross-check`/
  `scheduler`/`py-verify` 전부 재확인 완료(PASS, golden CSV byte-identical). 이 archive
  경로엔 이제 **`isp_variant_analysis.py`/`gen_rm_golden.py`/`rm_model.py`만** 남아있고
  이건 아래 은퇴한 v1 RM 트랙 전용이라 복원 안 했다.
- `archive/dfxisp-v2-renewal-2026-08-07/isppipeline-hls-superseded-files/` — 구
  `dfxisp_rm.{cpp,hpp}`(v1 RM ablation top) — `archive/isppipeline-sw-cleanup-2026-08-07/tools/`의
  `rm_model.py`와 함께 **진짜로 은퇴한 v1 RM 트랙**(static/reg_only/dfx_bin/dfx_fp 변종
  비교용, 2026-08-06 GAT 실험과 무관). `rm-golden`/`rm-csim`/`rm-verify`/`analysis`는 이
  둘이 없어서 비활성 — 위 7개와 달리 단순 경로 문제가 아니라 대상 자체가 의도적으로
  은퇴했으므로 코드는 복원하지 않고 Makefile 타겟 4개를 명시적 stub으로 정리했다
  (§"로컬 C-sim 실행" 참고).

## 핵심 파일 상세

- `include/dfxisp_accel.hpp` — HLS top 인터페이스, mode/selected-RM enum, 4개 scalar 메타데이터 출력 포인터
- `src/dfxisp_accel.cpp` — checker + baseline core12(demosaic/BLC/WB/CCM, 12-bit) + RM_NORMAL_TONE(gain 1.25x + gamma2.0) + RM_LOW_LIGHT_TONE(2x2 bin + gain 2.0x + gamma2.0)
- `tests/test_dfxisp_csim.cpp` — C-sim smoke 테스트 + golden CSV bit-compare + 아키텍처 불변식 검사
- `tools/gen_golden_vectors.py` — stdlib-only 결정적 golden 생성기(`src/dfxisp_accel.cpp` bit-exact 미러).
  2026-08-07 restructure로 잠시 `archive/`로 이동했었으나 **2026-08-14에 복원**, `make golden`
  정상 동작 확인(재생성한 CSV가 커밋된 것과 byte-identical — 드리프트 없었음)
- `tools/gen_verification_report.py` — stdlib-only Markdown 검증/리포트 생성기. 같은 이유로
  잠시 이동했다가 **2026-08-14에 복원**, `make report` 정상 동작(`reports/latest.md` 재생성 확인)
- `scripts/vitis_hls.tcl` — `dfxisp_accel`용 Vitis HLS 프로젝트 스캐폴드(`DFXISP_HLS_TOP` 등을
  바꾸면 다른 top에도 재사용 가능)
- `Makefile` — g++ 로컬 C-sim, golden 생성, verify/report, Vitis HLS dry-run 리포트(일부 타겟
  비활성 — §"로컬 C-sim 실행")
- `include/default_isp.hpp` · `src/default_isp.cpp` — **default_ISP**(2026-08-06 신규):
  AMD Vitis Vision L3 `isppipeline`의 스테이지 순서·도메인을 따르는 표준 ISP arm
  (Bayer 도메인 BLC/gain → demosaic → 적응 AWB → 실제 CCM → gamma). `RM_NORMAL_TONE`과
  **병존**하며 기존 golden 계약을 건드리지 않는다. 상세: `src/default_isp.md`
- `isppipeline/sw/gen_default_isp_golden.py`(구 `tools/`, 2026-08-14 이관) ·
  `tests/test_default_isp_csim.cpp` — 위 arm의 canonical golden + C-sim
  (`make default-isp-verify`)
- `include/lowlight_isp.hpp` · `src/lowlight_isp.cpp` — **lowlight_ISP**(2026-08-06 신규):
  제안 저조도 arm v2. default_ISP와 보정 백본·톤 커브를 공유하고
  **{binning, 2.0× 상류 게인, H/2×W/2 출력}** 만 다르다 → 통제된 arm 비교가 가능하다.
  denoise(한계효용 0)와 GAT/VST 톤(gamma 2.0에 열세, 두 검출기 교차검증)은
  2026-08-06 측정으로 각각 제거·교체됐고, csynth LUT 12,826 → 4,150으로 줄어
  **v1 저조도 arm과 사실상 동등**해졌다.
  배포 arm(RM_LOW_LIGHT_TONE)은 무변경. 상세: `src/lowlight_isp.md`
- `isppipeline/sw/gen_lowlight_isp_golden.py`(구 `tools/`, 2026-08-14 이관) ·
  `tests/test_lowlight_isp_csim.cpp` — 위 arm의 canonical golden + C-sim
  (`make lowlight-isp-verify`)

> 실험 arm(§7)·ablation(§12 Task 5)은 원래 `src/dfxisp_rm.cpp`·`tools/rm_model.py`
> (static / reg_only / dfx_bin / dfx_fp)에 있었다(현재 스캐폴드의 과거 post-RGB8
> gain/lift 경로가 그 dfx 변종 세트로 이관되어 ablation으로만 남던 시절 기록). **둘 다
> 2026-08-07 restructure로 은퇴** — `dfxisp_rm.cpp`는
> `archive/dfxisp-v2-renewal-2026-08-07/isppipeline-hls-superseded-files/src/`,
> `rm_model.py`는 `archive/isppipeline-sw-cleanup-2026-08-07/tools/`에 있다. `tests/test_rm_csim.cpp`
> + `tests/rm_golden_vectors.csv`는 여전히 `isppipeline/hls/`에 남아 있지만, 그 테스트가
> `#include`하는 `src/dfxisp_rm.cpp`/`include/dfxisp_rm.hpp` 자체가 없다. **2026-08-14에
> `rm-golden`/`rm-csim`/`rm-verify`/`analysis` Makefile 타겟을 명시적 stub으로 정리**했다
> (되살리는 대신 — 은퇴가 의도적이라는 판단, §"로컬 C-sim 실행" 참고) — 실행하면 이유를
> 설명하는 메시지와 함께 exit 1, 더는 `No such file or directory` 같은 불친절한 에러가 아니다.

## `tools/` 파일 상태 (canonical / proxy / legacy, 2026-07-08 Hermes 리뷰 + 같은 날 gamma 재정합)

> **2026-08-14 경로 갱신(당일 두 번):** 아래 표는 2026-07-08 시점 배치를 기록한 것이라
> 파일 경로가 그때와 다르다. 오전엔 2026-08-07 restructure로 이 표의 대부분이 저장소 루트
> `archive/isppipeline-sw-cleanup-2026-08-07/tools/`로, `default_isp_pipeline.py`/
> `lowlight_isp_pipeline.py`/`verify_new_arm_pipelines.py`는 `isppipeline/sw/`로 이관됐다.
> **오후에 `gen_golden_vectors.py`/`gen_verification_report.py`/`scheduler_sim.py`/
> `scheduler_sweep.py`/`verify_binning_cross_check.py`/`verify_demosaic_bilinear_cross_check.py`
> /`internal_edge_smoke.py`/`baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`를 archive에서
> 다시 `isppipeline/hls/tools/`로 복원**(cross-check 3개는 `isppipeline/sw/`의
> `checker.py`를 가리키도록 `sys.path.insert` 추가), `checker.py`/`default_isp_pipeline.py`/
> `lowlight_isp_pipeline.py`/`verify_new_arm_pipelines.py`는 여전히 `isppipeline/sw/`가
> 정본. `newrm_pipeline.py`/`isp_pipeline_ver1.py`는 archive 하위 `archive/`(2026-07-08
> 아카이브)에 그대로. 표 자체는 2026-07-08 시점의 canonical/proxy/legacy **분류 근거**를
> 보존하려고 그대로 두고, 현재 위치는 위 "파일 구조" 절과 각 행의 굵은 경로 주석을 참고할 것.

golden/C-sim/cross-check 경로 자체는 견고하나, canonical golden ↔ SW-eval proxy ↔
legacy/ver0 코드 사이 경계가 문서화되어 있지 않아 혼동 위험이 있었다. 아래 표가 그
경계를 명시한다 — 새 코드는 이 표에 맞춰 어느 범주인지 표시할 것.

> **2026-07-08 같은 날 두 번째 갱신:** Hermes 리뷰(위 표의 최초 버전)와 독립적으로,
> `isp_pipeline_ver1.py`/`newrm_pipeline.py`의 gamma 곡선이 canonical(양쪽 모드
> 공유 gamma-2.0 정수 sqrt LUT)과 다르다는 문제(gamma 2.2/2.5/없음)가 발견되어,
> 이 두 파일은 `tools/archive/`로 이동하고 `baseline_isp_pipeline.py`
> (normal)/`low_light_isp_pipeline.py` (low-light)/`checker.py` (dark-ratio
> checker, 디커플)로 대체됐다. Hermes가 고친 demosaic wrap-around 버그
> (`np.roll` → clamp-to-edge)는 새 파일들에도 동일하게 이식됐다 — 두 수정이
> 서로 다른 실제 버그를 독립적으로 잡았고, rebase 시 병합됐다. 자세한 내용은
> `results/isp-pipeline-recalibration-2026-07-08.md` 참조.

| 파일 | 상태 | 용도 |
|---|---|---|
| `gen_golden_vectors.py` | **canonical golden** | `src/dfxisp_accel.cpp`의 bit-exact 미러 |
| `verify_binning_cross_check.py` | **검증 gate** | binning-demosaic 독립 fuzz 교차검증 (`make verify`에 포함). `low_light_isp_pipeline.py`의 `_bin_demosaic_rggb16`과 교차검증(2026-07-08 이전엔 `isp_pipeline_ver1.py` 대상) |
| `baseline_isp_pipeline.py` | **SW eval proxy (canonical-matched)** | normal arm: BLC+WB+gain(1.25x)+gamma-2.0, gain/gamma까지 `dfxisp_accel.cpp`와 일치하도록 재작성(2026-07-08). `isp_pipeline_ver1.py` 대체 |
| `low_light_isp_pipeline.py` | **SW eval proxy (canonical-matched)** | low-light arm: 2x2 bin-demosaic+BLC+WB+gain(2.0x)+gamma-2.0(normal과 동일 LUT 공유, canonical과 일치). BLC_OFFSET 재보정값은 미확정 상태로 명시(파일 내 주석 참조) |
| `checker.py` | **SW eval proxy (canonical-matched)** | dark-ratio 기반 adaptive 모드 선택기, 두 파이프라인 파일과 독립(상호 import 없음) |
| `newrm_pipeline.py` / `isp_pipeline_ver1.py` | **archived (2026-07-08)** | `tools/archive/`로 이동. gamma가 canonical과 달라(2.2/2.5/없음) 위 3개 파일로 대체됨 — 신규 작업에서 참조 금지, 과거 ablation 계보 참조용으로만 보존 |
| `scheduler_sim.py` / `scheduler_sweep.py` | **정책 시뮬레이션** | hysteresis/temporal/min-dwell 스케줄러 트레이드오프 실험. synthetic luminance 시퀀스 사용 — checker 구현 자체의 검증이 아님 |
| `calibrate_noise_model.py` | **측정 도구**(08-06) | 실 RAW 원본에서 Poisson-Gaussian 노이즈 모델(σ²=a·y+b) 추정 — GAT 상수용. **GAT는 2026-08-06에 배포에서 내려갔고**(gamma 2.0으로 교체) 이 상수는 `lowlight_isp_gat` ablation arm 전용이다. 단일영상 photon-transfer(블록 분산 저백분위 + χ² 편향 보정). **`raw_bin`은 쓸 수 없다**(shift8이라 12-bit 노이즈가 양자화로 소실) — rawpy로 원본 NEF/ARW를 읽어야 한다. 결과·한계: `src/lowlight_isp.md` §4.1 |
| `default_isp_pipeline.py` · `lowlight_isp_pipeline.py` | **SW eval proxy (canonical-matched)**(08-06 신규) | v2 arm(default_ISP / lowlight_ISP)의 **벡터화** 렌더러 — 스칼라 golden 생성기는 픽셀 루프라 20MP 프레임을 못 돌린다. 모든 상수를 golden에서 **import**해 드리프트를 원천 차단. `eval_map_isp.py`가 이 둘로 디스패치 |
| `verify_new_arm_pipelines.py` | **검증 gate**(08-06 신규) | 위 벡터화 프록시가 스칼라 golden과 **bit-exact**인지 퍼징(`make verify-new-arms`). 2026-07-02 chroma-collapse와 같은 부류의 위험(두 번째 구현이 조용히 어긋남)을 막는다 |
| `internal_edge_smoke.py` | **검증 gate**(2026-08-06 신규) | 1x1~8x8 극소/홀수 그리드 스모크 + demosaic 경계 clamp 회귀 테스트 (`make py-verify`). `baseline_isp_pipeline.py`/`checker.py` 양쪽의 독립 demosaic 사본을 각각 검사(2026-07-08 이전엔 `isp_pipeline_ver1.py` 대상). (이 행의 파일명은 원래 `calibrate_noise_model.py`로 오기재돼 있었음 — 2026-08-14 정정) |

## Ponytail 리뷰 기록 (2026-08-06)

**2차(모듈 범위: checker / default_ISP / lowlight_ISP), findings 4 — 전부 절단:**
default_ISP의 AWB 녹색 게인(기준 채널이라 항상 256 = 항등 연산),
checker의 `dark*100` 3회 반복, `sigma_clip`의 인자 재조립,
`checker_hysteresis`의 16-bit dwell 카운터(파라미터 기반 폭으로).
재합성 결과 default_ISP **FF 8,803 → 8,794**, LUT/DSP/타이밍 불변 —
합성기가 ×256>>8을 이미 접고 있어 절감은 파이프라인 레지스터였다.
golden 4종 + xsim 2종 전부 재통과(수치 무변화).

**1차(전체 diff 범위) 기록:**

`/ponytail-review` 게이트를 세 arm 추가분에 적용한 결과(findings 11, 실행
가능 −195줄) 중 **테스트 CSV 파서 3중복만 잘라냈다** — `tests/golden_csv.hpp`
헤더 기반 로더 하나로 통합(−134줄). 나머지 둘은 **근거를 남기고 유지**한다:

- **`src/`의 헬퍼·상수 중복**(`clamp_i`/`pack_rgb`/`bin_dim`/`CCM_Q8`/
  `GAMMA2_LUT`, ~45줄): HLS는 arm마다 별도 translation unit으로 합성하므로
  헤더로 빼도 **실리콘 결과가 동일**하다 — 이득 0인데 bit-exact golden 계약
  3건을 건드리는 리팩터라, 사다리 1번("이 작업이 필요한가")에서 기각.
- **Python golden 2종의 공통 상수/헬퍼**(~30줄): C++ 쪽은 중복인데 Python만
  공유하면 **정본이 비대칭**이 되어 유지보수 혼동이 절감분보다 크다.

## 로컬 C-sim 실행

> **2026-08-14 기준 타겟 상태:** 2026-08-07 restructure가 `isppipeline/hls/tools/`의
> golden 생성기·검증 스크립트 대부분을 저장소 루트 `archive/`로 옮기면서 Makefile의
> `golden`/`cross-check`/`verify`/`report`/`py-verify`/`scheduler`가 한동안 그 옛 경로를
> 참조해 실패했다(`c7e182e`가 `default-isp-golden`/`lowlight-isp-golden`/`verify-new-arms`
> 세 타겟만 먼저 `../sw/`로 재배선). **같은 날 나머지도 마저 고쳤다:** `gen_golden_vectors.py`
> · `gen_verification_report.py` · `scheduler_sim.py` · `scheduler_sweep.py` ·
> `verify_binning_cross_check.py` · `verify_demosaic_bilinear_cross_check.py` ·
> `internal_edge_smoke.py`를 archive에서 `isppipeline/hls/tools/`로 복원(`git mv`), 뒤
> 세 개가 이제 `isppipeline/sw/`에 있는 `baseline_isp_pipeline.py`/`low_light_isp_pipeline.py`
> /`checker.py`를 import하도록 `sys.path.insert`를 추가했다(이 중 앞 둘은 v2로 대체된 뒤
> sw/로 안 옮겨져서 archive에서 같이 복원 — 지금은 이 cross-check 용도로만 쓰인다). 전부
> 실행해서 검증 완료: `golden`/`report`/`scheduler`/`cross-check`/`verify`/`py-verify` 모두
> PASS, 재생성한 `tests/golden_vectors.csv`는 커밋된 것과 byte-identical(드리프트 없음).
>
> **`rm-golden`/`rm-csim`/`rm-verify`/`analysis` — 명시적 stub으로 정리(2026-08-14, 같은 날
> 두 번째 조치):** 이건 경로 문제가 아니라 대상 자체가 없다. `rm-csim`이 컴파일하는
> `src/dfxisp_rm.cpp`/`include/dfxisp_rm.hpp`(v1 RM ablation top)와 `analysis`가 쓰는
> `rm_model.py`는 2026-08-07 restructure에서 **superseded로 명시**되어 별도 archive
> 버킷(`archive/dfxisp-v2-renewal-2026-08-07/isppipeline-hls-superseded-files/`)으로
> 옮겨진, 진짜로 은퇴한 실험 트랙이다 — 위 7개처럼 단순 이관이 아니라 되살리는 순간 죽은
> 코드를 부활시키는 셈이라 복원하지 않기로 했다. 대신 네 타겟 모두 이유를 설명하고 exit 1
> 하는 stub으로 교체(`Makefile` 참고) — `make rm-verify`가 이제 `No such file or
> directory`가 아니라 "은퇴한 트랙이고 archive 경로가 어디인지"를 바로 알려준다. `sw-stage`도
> `rm-verify`/`analysis` 의존을 빼고 `verify scheduler`만 돌리도록 재정의했다.

```bash
cd isppipeline/hls
make csim                 # smoke 테스트 — 동작
make golden                # golden CSV 재생성 — 동작(2026-08-14 복원)
make verify                # golden 재생성 + packed RGB888 bit 단위 비교 — 동작(2026-08-14 복원)
make report                 # reports/latest.md 갱신(아키텍처 gate 표 포함) — 동작(2026-08-14 복원)
make cross-check            # binning/demosaic 독립 fuzz 교차검증 — 동작(2026-08-14 복원)
make scheduler              # 스케줄러 정책 시뮬레이션 — 동작(2026-08-14 복원)
make py-verify              # 위 검증들 + tools/*.py py_compile — 동작(2026-08-14 복원)
make sw-stage                # verify + scheduler(rm-verify/analysis 제외, 2026-08-14 재정의) — 동작
make default-isp-verify   # default_ISP(Vitis Vision 정렬 arm) golden + C-sim — 동작
make lowlight-isp-verify  # lowlight_ISP(제안 저조도 arm v2) golden + C-sim — 동작
make verify-new-arms      # 벡터화 SW proxy vs 스칼라 golden 퍼징(isppipeline/sw/ 경유) — 동작
make rm-verify               # v1 RM ablation top 골든+C-sim — stub, exit 1로 은퇴 사유 안내
make analysis                 # ISP variant 자원/전력 분석 — stub, exit 1로 은퇴 사유 안내
```

`make csim` 실제 출력(2026-08-14):

```text
./build/dfxisp_csim
DFXISP hysteresis-flag export tests passed
DFXISP golden vector compare passed (726 pixels)
DFXISP C-sim smoke tests passed
```

## Golden vector 형식

CSV는 케이스별 메타데이터(mode·threshold·출력 형상·선택 RM)와 입력 RAW 행(`kind=raw`),
기대 출력 행(`kind=rgb`)을 함께 담는다. Policy A(저조도 H/2×W/2)로 인해 입력 픽셀 수와
출력 픽셀 수가 다르므로 두 종류의 행을 분리한다. 커버리지: bright/dark/mixed/
threshold-boundary/bright-recovery/odd-dimension.

## Vitis HLS 스캐폴드 실행

기본값은 ZCU104 파트 `xczu7ev-ffvc1156-2-e`, 5.0 ns 클럭. 설치가 다르면 재정의한다.
`make hls-report`는 `vitis_hls` 설치 없이 top/project/part/clock/소스/예상 출력 경로를 출력한다.

```bash
cd isppipeline/hls
make hls-report                              # dry-run
make hls                                     # 기본 DFXISP_HLS_FLOW=csim
DFXISP_HLS_FLOW=csynth make hls              # C-sim 후 synthesis
DFXISP_HLS_FLOW=cosim  make hls              # + co-simulation(RTL)
```

`vitis_hls`가 `PATH`에 없으면 `make hls`는 안내 메시지와 함께 종료한다.
비표준 경로는 `VITIS_HLS=/path/to/vitis_hls`로 지정한다. `DFXISP_HLS_TOP`을 바꾸면
`dfxisp_accel` 외 다른 top(예: `default_isp`/`lowlight_isp`/`checker_scan`)도 같은 흐름으로
돌릴 수 있다(`DFXISP_HLS_SRC`/`DFXISP_HLS_TB`도 함께 지정). **csynth/cosim을 실행하기
전에 §"C-synthesis / Co-sim 실행 노트"의 source-path 우회를 먼저 읽을 것** — 표준 중첩
경로(`build/vitis_hls/...`)에서 그대로 돌리면 링크 실패로 막힌다.

## HLS top 함수

```cpp
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,             // capacity >= width*height
    int width,
    int height,
    int mode,                      // NORMAL / LOW_LIGHT / AUTO
    uint16_t dark_pixel_threshold, // AUTO: dark 픽셀 비율 > 80%(재보정 2026-07-02) 이면 LOW_LIGHT
    int* out_width,                // 선택된 RM의 출력 폭
    int* out_height,               // 선택된 RM의 출력 높이
    int* selected_mode,            // 해소된 mode (AUTO 해소값)
    int* selected_rm,              // 선택된 tone RM
    int* hyst_flags);              // Schmitt 밴드 플래그 (ap_vld fabric wire, 2026-08-06)
```
메타데이터가 구조체 포인터 하나가 아니라 **4개의 개별 scalar 출력 포인터**인 이유: 구조체
포인터를 `s_axilite`로 선언하는 방식은 검증된 바 없는(비표준) 패턴이라 adversarial review에서
지적됨(§ 하드웨어/DFX 구조 하단 참조). 개별 scalar 포인터는 Vitis HLS에서 완료 후 read-back
레지스터로 신뢰성 있게 합성되는 정형화된 패턴이다.

## 하드웨어/DFX 구조

`src/dfxisp_accel.cpp`는 로컬 C-sim을 위해 stdlib-only를 유지하면서도 의도한 static/RM
경계를 따라 분할되어 있다:

- `checker_select_mode()` — static-region scene checker. `AUTO`에서 dark-pixel 비율로
  NORMAL/LOW_LIGHT를 결정하고, (2026-08-06부터) 프레임당 Schmitt 밴드 비교 2개
  (`hyst_flags`: enter 64% 초과 / exit 60% 미만 — 중심 62% ±2%p)를 추가로 내보낸다. 장면 단위
  히스테리시스 **상태**는 static-region RTL 모듈
  `results/pr_controller/checker_hysteresis.v`가 소유하며 PR 컨트롤러 trigger를
  직접 구동한다(request/ack, PS 무개입 — `checker_hysteresis.md` 참조). 단일
  프레임 C-sim entry는 무상태 유지(golden 계약 불변).
- `baseline_core12()`/`apply_blc_wb12()` — **shared static** baseline core (ver1).
  BLC + WB(Q8 채널 게인) + CCM(identity)을 **12-bit로 수행**(최종 >>4는 tone에서). **gain/gamma
  없음.** normal 경로는 `demosaic_rggb12()`(RGGB 3x3 Bayer 데모자이크) 결과를 받고, low-light
  경로는 binning-demosaic 결과를 받는다(아래).
- `tone()` — tone RM 스테이지: exposure gain(12-bit) → >>4 → gamma2.0. mode별 gain.
- `run_normal()` — RM_NORMAL_TONE = **gain 1.25× + gamma2.0**. baseline core를 full-res로 실행.
- `run_low_light()`/`compute_binned_rgb_row()` — **RM_LOW_LIGHT_TONE**(DFX reconfigurable
  module 후보). RAW 2x2 **binning-demosaic 융합**(front, R=top-left·G=avg(top-right,
  bottom-left)·B=bottom-right — 채널별 정체성 보존) → baseline core → **gain 2.0× +
  gamma2.0**(back). Vivado DFX 구현에서는 이 tone RM slot을 RM-호환 블록으로 패키징하고,
  checker·baseline core·controller는 static region에 둔다.
- `gamma2()` — γ=2.0을 정수 sqrt `floor(sqrt(255·v))`로 정확히 실현(Python `isqrt`와
  bit-exact). HW에서는 256-엔트리 LUT로 대체 가능.

### 2026-07-02 adversarial-review 수정 (중요)
`/codex:adversarial-review --base 0e433f9`가 두 결함을 발견해 수정했다:
1. **색상 손실 버그(high):** 이전 low-light front-end는 2x2 RGGB 셀의 4개 샘플을
   **하나의 스칼라 평균**으로 합친 뒤 그 값을 다시 Bayer인 것처럼 재-demosaic — 색 정보가
   demosaic 전에 이미 파괴됨. golden 모델(`gen_golden_vectors.py`)이 같은 버그를 그대로
   미러링해서 `make verify`의 bit-exact 테스트가 이를 전혀 못 잡았고, 보고된 lowlight mAP
   증거(`isp_pipeline_ver1.py`)는 **채널 정체성을 보존하는 다른 알고리즘**을 측정한 것이라
   실제 HW 후보의 증거가 아니었음. → `compute_binned_rgb_row()`로 binning+demosaic을 한
   단계에 융합, `_bin_demosaic_rggb16`(SW ver1)과 bit-exact 일치하도록 수정.
2. **메타데이터 RTL 미검증(medium):** `DfxIspResult*` 구조체 포인터를 `s_axilite`로 선언 —
   합성된 RTL에서 실제로 읽을 수 있는지 어떤 산출물로도 확인된 적 없음(cosim도 post-check
   단계에서 실패해 미확인). → 4개 개별 scalar 포인터로 교체(위 HLS top 함수 참조).

**2026-07-02 20:33 KST 갱신:** 이 수정을 반영해 `results/stage4-hw-synthesis-2026-07-02.md`·
`results/stage5-dfx-implementation-2026-07-02.md`를 재합성/재구현하고 수치를 최신화했다
(pr_verify PASS 유지, LUT/FF/DSP 감소 — 버그로 인한 불필요한 2차 demosaic 로직이 제거된
결과). 상세는 두 문서와 `SPEC.md` §10 참조.

C-sim에는 Vitis 전용 헤더가 필요 없다; HLS pragma만 존재하며 로컬 g++ 빌드에서는 무시된다.

## 다음 하드웨어 단계

1. ~~`run_low_light()`의 정적 scratch binning 버퍼를 진짜 streaming line buffer로 교체.~~
   **완료(2026-07-02)** — `row_buf[3][MAX_BINNED_W]` 3-row 슬라이딩 버퍼로 교체, bit-exact 유지.
2. RM_LOW_LIGHT_TONE / RM_NORMAL_TONE을 독립 DFX RM slot 패키징 flow로 승격(§8.3 gate).
3. Policy B(형상보존 upsample/pad)는 DPU가 고정 H×W ABI를 요구할 때만 추가(§4.3).
4. Arm 2(register-only)·Arm 3(DFX) 자원/전력/PR-latency 비교(§7). **Arm2 실측 완료**
   (unified top, C-synthesis) — `results/stage4-hw-synthesis-2026-07-02.md`. Arm1/Arm3와
   전력/PR-latency는 여전히 TODO(Vivado DFX 플로어플랜·구현 필요).
5. **(시뮬레이션 완료 2026-08-06)** fabric 내부 모드 전환:
   `checker_hysteresis.v`가 신규 `hyst_flags` ap_vld wire를 소비해
   `pr_controller.trigger`를 request/ack로 구동 — end-to-end xsim PASS
   (`checker_to_pr_tb.v`). **같은 날 production 경로로 AMD DFX Controller
   IP(PG374)를 채택** — `dfxc_trigger_adapter.v`가 동일 req/ack 계약으로
   IP에 연결(계약 모델 TB `checker_to_dfxc_tb.v` xsim PASS), 자체
   pr_controller는 레이턴시 특성화 전용. 통합 체크리스트는
   `results/pr_controller/dfxc_adapter.md` 참조.

## C-synthesis / Co-sim 실행 노트 (Vitis HLS 2024.1)

과거 worklog와 동일한 두 가지 환경 이슈가 재현된다:

- **source-path 버그:** 중첩된 `build/vitis_hls/...` 프로젝트 경로에서 `add_files`로 design
  source를 추가해도 csim/csynth의 `HLS_SOURCES`에서 누락되어 링크 실패(`undefined symbol:
  dfxisp_accel`). **우회:** flat temp-dir(예: `/tmp/hls_dfxisp/dfxisp_accel/`)에 소스를 같은
  디렉터리로 복사하고 그 디렉터리에서 실행. **`dfxisp_accel`의 경우 복사해야 하는 전체
  집합**(2026-08-14 기준, `#include` 사슬 그대로): `include/dfxisp_accel.hpp`,
  `include/checker.hpp`(dfxisp_accel.cpp가 include, 2026-08-14부터), `src/dfxisp_accel.cpp`,
  `tests/test_dfxisp_csim.cpp`, `tests/golden_csv.hpp`(2026-08-06 신설, tb가 include — tb와
  **같은 디렉터리**에 둬야 함) — 넷 다 flat-dir 루트에, golden CSV만 그 아래 `tests/`
  서브폴더에(코드가 `"tests/golden_vectors.csv"`로 상대경로 하드코딩). 이 두 헤더 중 하나라도
  빠지면 각각 `'checker.hpp' file not found` / `'golden_csv.hpp' file not found`로 csim
  컴파일부터 실패한다(2026-08-14에 실제로 재현·정정).
- **종료-hang:** `close_project` 이후 프로세스가 종료되지 않음(작업 자체는 이미 끝난 상태).
  `timeout -k <grace> <sec> vitis_hls -f run.tcl`로 감싸고 로그의 완료 마커를 확인.
- **cosim `depth=`와 전용 TB:** AMD UG1399에서 `depth`는 C/RTL co-sim 검증 어댑터가
  처리할 **한 TB 트랜잭션의 최대 샘플 수**다. 과거의 1024/2048 값은 여러 TB 호출의
  누적 주소 범위라는 잘못된 가정으로 튜닝한 값이었다. Vitis HLS 2024.1은 최신 문서의
  `depth=width*height` 표현도 const integer가 아니라며 무시하므로, 현재 전용 8×8 co-sim
  TB(`tests/test_dfxisp_cosim.cpp`)에 맞춰 `depth=64`를 사용한다. 전용 TB는 모든 top-level
  출력 포인터(`hyst_flags` 포함)에 유효한 저장공간을 전달하며 normal/low-light 두
  트랜잭션을 검사한다. 2026-08-14 WSL2 + Vitis HLS 2024.1 + XSIM 실측에서 RTL 2/2와
  C post-check가 모두 통과해 `C/RTL co-simulation finished: PASS`를 확인했다. 이 depth는
  co-sim 어댑터 전용이며 합성된 AXI master의 실제 프레임 크기를 제한하지 않는다.
