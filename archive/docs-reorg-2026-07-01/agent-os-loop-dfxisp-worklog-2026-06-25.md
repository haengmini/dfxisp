# Agent OS All-in-One 플랫폼 루프 + DFXISP HLS C-sim 작업로그 — 2026-06-25

## 요약

이 작업은 Google Drive 정본을 기준으로 수행했다. 로컬 `/opt/data`는 Drive 파일 검증/빌드용 staging cache로만 사용했다.

## Drive 대시보드 수정

정본 대시보드 파일:

- `hq-dashboard.html`
- Drive ID: `1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0`
- 링크: https://drive.google.com/file/d/1AjhJOMeSnmMtrnMeRDIDH1v9VoK_RwT0/view?usp=drivesdk

적용한 수정:

- `에이전트/agent` local-answer 경로의 JS 문법 오류를 패치.
- 업데이트 후 Drive 파일을 재다운로드해 `node --check`로 검증.

검증:

```text
title Agent OS — Command Center
node --check /tmp/drive_hq_redownload.js: PASS
```

## Drive-first 루프 엔지니어링

Drive-first watchdog 루프를 생성·실행:

- 로컬 실행 캐시: `/opt/data/scripts/agent_os_drive_first_loop.py`
- 래퍼: `/opt/data/scripts/agent_os_drive_first_loop.sh`
- Drive 스크립트 ID:
  - `agent_os_drive_first_loop.py`: `1Sfg0bP0-F_w8d-HDXrlP-4VzgyObx7Wp`
  - `agent_os_drive_first_loop.sh`: `14JCv3jTp2G_A6JgTief9iov51ja28d2j`
- Cron job: `agent-os-drive-first-loop`
- 주기: 30분마다
- 전달: local, script-only/no_agent

루프 점검 항목:

1. 정본 Drive `hq-dashboard.html`을 다운로드해 JS 문법 검사.
2. Drive DFXISP HLS C-sim 폴더에 필요한 소스 파일이 있는지 확인.
3. 로컬 C-sim 미러 실행: `make -C /opt/data/dfxisp_md/isppipeline/hls csim`.
4. 상태 artifact를 Drive `05-dashboard`에 upsert:
   - `loop-status-latest.json`
   - `loop-status-latest.md`

최근 루프 결과:

```text
Agent OS loop PASS — Drive status updated: https://drive.google.com/file/d/1qRVLAKN4bRCPazQuYnv_OhjngTbCH5z1/view?usp=drivesdk
```

## DFXISP HLS C-sim / 하드웨어 스캐폴드

정본 Drive 폴더:

- `Agent OS / DFXISP / hls-csim`
- Drive folder ID: `1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML`
- 링크: https://drive.google.com/drive/folders/1LbQkwIckkJpWBbR4c4ip2l5f_X3M-DML

업로드한 파일:

| 파일 | Drive ID |
|---|---|
| `README.md` | `1-wXNhlK4IsjOVh-zQvhS5CfdV1VVRSmT` |
| `Makefile` | `1I5b1kD6oOhTw9ei535aU80A-WBTohzJv` |
| `.gitignore` | `1WPHkesxezKZrJtINzFaVf_LxCWdpdiSU` |
| `include/dfxisp_accel.hpp` | `1us6QwxvWoMBnahg0Oy6p215HTrBUrpub` |
| `src/dfxisp_accel.cpp` | `17MqS_XkTrXKgexGnofhNqmqiMYYkTVv7` |
| `tests/test_dfxisp_csim.cpp` | `1QYx2HyI7iVC_0VBC9k_S9ixk-0sNSxaM` |

로컬 미러/repo 경로:

- `/opt/data/dfxisp_md/isppipeline/hls/`

구현한 하드웨어 대면 top:

```cpp
extern "C" void dfxisp_accel(
    const uint16_t* raw_bayer,
    uint32_t* rgb_out,
    int width,
    int height,
    int mode,
    uint16_t low_light_threshold);
```

지원 모드:

- `DFXISP_MODE_NORMAL`
- `DFXISP_MODE_LOW_LIGHT`
- `DFXISP_MODE_AUTO`

현재 알고리즘:

```text
pseudo-RAW Bayer GRBG uint16
  -> scene average checker
  -> normal / low-light mode select
  -> border-clamped demosaic
  -> low-light integer gain + lift
  -> packed RGB888 uint32
```

C-sim 검증:

```text
make -C isppipeline/hls csim
DFXISP C-sim smoke tests passed
```

Git 로컬 커밋:

```text
c5b920d feat: add DFXISP HLS C-sim scaffold
```

GitHub push 상태:

```text
blocked: GitHub HTTPS credentials unavailable in this environment
fatal: could not read Username for 'https://github.com': No such device or address
```

Drive 정본 artifact는 이미 저장됨; GitHub auth 구성 후 push 재시도 가능.

## 다음 루프 목표

1. ZCU104 part/clock 및 export target용 Vitis HLS TCL 추가.
2. 레퍼런스 demosaic을 line-buffer/window HLS 아키텍처로 교체.
3. low-light 경로에 명시적 DFX reconfigurable-module 경계 도입.
4. Python golden vector 생성 및 RGB888/RGB32 출력 bit-compare.
5. 루프 상태를 status-only artifact 대신 `hq-dashboard.html` 시각 카드로 반영.
