# 순차 에이전트 배치 작업로그 — 2026-06-26

## Drive-first 원칙

모든 durable 산출물은 가능한 한 Google Drive에 먼저/정본으로 업데이트했다. 로컬 `/opt/data` 경로는 staging/build cache 및 repo 미러로 사용했다.

## 에이전트 배치 순서

### 1. Coder 에이전트 — Vitis HLS/ZCU104 TCL 스캐폴드

`Agent OS / DFXISP / hls-csim` 및 로컬 미러 `/opt/data/dfxisp_md/isppipeline/hls`에 구현.

산출물:

- `scripts/vitis_hls.tcl`
- Makefile `hls` 타깃
- README HLS 명령 문서

검증:

```text
make csim: PASS
C++ syntax check: PASS
make hls: fails clearly when vitis_hls is not installed
```

### 2. HW Coder 에이전트 — line-buffer/window-ready 아키텍처 + DFX RM 경계

HLS C++를 명시적인 하드웨어 친화적 경계로 리팩터링:

- `checker_scene_average()`
- `checker_select_low_light()`
- `load_bayer_window3x3()`
- `demosaic_grbg_window()`
- `normal_pixel_kernel()`
- `normal_pipeline()`
- `low_light_pipeline()`
- `low_light_reconfigurable_module()`

`low_light_reconfigurable_module()`은 의도한 DFX reconfigurable module 경계로 표시/주석되어 있다.

검증:

```text
make -C /opt/data/dfxisp_md/isppipeline/hls csim: PASS
```

### 3. Research/Coder 에이전트 — Python golden vector + bit-compare

결정적 golden-vector 생성과 C-sim bit 비교를 추가.

산출물:

- `tools/gen_golden_vectors.py`
- `tests/golden_vectors.csv`
- packed RGB 출력을 golden CSV와 비교하도록 C++ 테스트 업데이트
- Makefile `golden` 및 `verify` 타깃

검증:

```text
make -C /opt/data/dfxisp_md/isppipeline/hls verify
DFXISP golden vector compare passed (48 pixels)
DFXISP C-sim smoke tests passed
```

### 4. Dashboard 에이전트 — hq-dashboard에 루프 health 임베드

`/opt/data/scripts/agent_os_drive_first_loop.py`와 Drive 정본 대시보드를 업데이트해, 최신 루프 상태가 file URL의 sidecar `fetch()`에 의존하지 않고 `window.STATE.loop_status`에 임베드되도록 했다.

Drive 대시보드:

- `hq-dashboard.html`
- Drive ID: `1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0`
- 링크: https://drive.google.com/file/d/1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0/view?usp=drivesdk

검증:

```text
node --check: PASS
/opt/data/scripts/agent_os_drive_first_loop.sh: PASS
```

## Drive 정본 DFXISP HLS 폴더

폴더:

- `Agent OS / DFXISP / hls-csim`
- Drive folder ID: `1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML`
- 링크: https://drive.google.com/drive/folders/1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML

업데이트/생성한 Drive 파일:

| 파일 | 상태 | Drive ID |
|---|---|---|
| `.gitignore` | updated | `1WPHkesxezKZrJtINzFaVf_LxCWdpdiSU` |
| `README.md` | updated | `1-wXNhlK4IsjOVh-zQvhS5CfdV1VVRSmT` |
| `Makefile` | updated | `1I5b1kD6oOhTw9ei535aU80A-WBTohzJv` |
| `include/dfxisp_accel.hpp` | updated | `1us6QwxvWoMBnahg0Oy6p215HTrBUrpub` |
| `src/dfxisp_accel.cpp` | updated | `17MqS_XkTrXKgexGnofhNqmqiMYYkTVv7` |
| `tests/test_dfxisp_csim.cpp` | updated | `1QYx2HyI7iVC_0VBC9k_S9ixk-0sNSxaM` |
| `scripts/vitis_hls.tcl` | created | `1fhpvnbuqU-Y391yfVRTKWit78OV9Wv_y` |
| `tools/gen_golden_vectors.py` | created | `1A-zEbdAgmNuSdn1r1tc51lYXAEkAB78r` |
| `tests/golden_vectors.csv` | created | `18dt49Qp376F5sQk686KlQlXJUpBju6L6` |

## 루프 상태

최근 루프 결과:

- `loop-status-latest.md`: https://drive.google.com/file/d/1qRVLAKN4bRCPazQuYnv_OhjngTbCH5z1/view?usp=drivesdk
- 종합: `PASS`

점검:

```text
✅ drive_hq_dashboard_js
✅ drive_dfxisp_hls_files
✅ dfxisp_local_csim
```

## Git 상태

로컬 커밋:

```text
547af2f feat: extend DFXISP HLS verification loop
c5b920d feat: add DFXISP HLS C-sim scaffold
```

GitHub push는 이 런타임에서 HTTPS 자격증명 부재로 여전히 차단됨:

```text
fatal: could not read Username for 'https://github.com': No such device or address
```

소스 push는 완료되지 않음. Drive 정본 artifact는 저장됨.

## 다음 순차 배치 목표

1. Admin 에이전트: GitHub auth 구성 또는 remote를 인증된 SSH/token flow로 전환.
2. HW Coder 에이전트: `vitis_hls` 사용 가능 시 Vitis HLS export synthesis 타깃 추가.
3. Reviewer 에이전트: Python golden vector를 `isppipeline/unprocess`의 더 고정밀 ISP golden 모델과 비교.
4. Dashboard 에이전트: HLS 검증 이력과 GitHub push 상태에 대한 가시적 UI drill-down 추가.
