---
type: claude-feedback
title: "Claude feedback — DFXISP research audit"
project: DFXISP
created: 2026-06-29
auditor: Hermes Agent
recipient: Claude / Claude Code
status: action-required
---

# Claude feedback — DFXISP research audit

이 문서는 DFXISP 연구 활동 산출물 점검 후 Claude/Claude Code에게 남기는 피드백이다.

## 1. 총평

연구 방향 설정 자체는 의미 있게 진전되었다. 특히 `08-e2-map-results-2026-06-29.md`와 `measurements/map.csv`에서 기존 가설을 억지로 유지하지 않고, mAP 실측 결과에 따라 논문 포지셔닝을 바꾼 점은 좋다.

핵심 방향 전환은 타당하다.

```text
기존: DFX-RM이 low-light mAP를 직접 향상시킨다.
수정: register-fast path가 mAP를 확보하고, DFX-RM은 자원/전력 절감 및 상호배타 구조 블록의 시분할 적재를 담당한다.
```

다만 현재 상태는 "좋은 연구 노트와 예비 결과가 Drive에 있음"이지, "재현 가능한 연구 패키지"는 아니다. Claude는 아래 문제를 우선 정리해야 한다.

## 2. 잘한 점

### 2.1 반증 결과를 정직하게 반영함

`08-e2-map-results-2026-06-29.md`에서 다음 결과가 명확히 기록되어 있다.

| variant | COCO 전체 n=347 | ExDark real-lowlight n=260 |
|---|---:|---:|
| static | 0.2984 | 0.1492 |
| reg_only | 0.2952 | **0.1585** |
| dfx_bin | 0.2455 | 0.1420 |
| dfx_fp | 0.2518 | **0.0879** |

또한 yolov8s 교차검증에서도 순서가 유지된다.

| variant | ExDark yolov8n | ExDark yolov8s |
|---|---:|---:|
| static | 0.1492 | 0.1714 |
| reg_only | **0.1585** | **0.1902** |
| dfx_bin | 0.1420 | 0.1511 |
| dfx_fp | 0.0879 | 0.1018 |

따라서 DFX-FP를 main mAP-improving RM으로 주장하기 어렵다는 판단은 옳다.

### 2.2 방향 A 전환은 연구적으로 타당함

`00-thesis-outline.md`, `01-thesis-draft.md`에서 다음 논리로 전환한 것은 타당하다.

- mAP는 register-only/parameter adaptation이 담당한다.
- DFX는 mAP 향상보다 resource/power/partial bitstream/PR latency trade-off의 근거로 정당화한다.
- DFX-Bin은 mAP guardrail을 통과하는 자원 절감 후보로 둔다.
- DFX-FP는 핵심 제안이 아니라 failed ablation 또는 재설계 후보로 둔다.

### 2.3 DFX-Bin bilinear 개선 대응은 좋음

`measurements/map.csv` 기준:

| regime | DFX-Bin nearest | DFX-Bin bilinear | register-only | 판정 |
|---|---:|---:|---:|---|
| ExDark | 0.1420 | **0.1576** | 0.1585 | guardrail PASS, 0.09pt 차이 |
| COCO 전체 | 0.2455 | 0.2839 | 0.2952 | 1.13pt 차이, normal에서는 scheduler가 RM 미사용 |

이 결과는 "DFX-Bin이 mAP를 올린다"가 아니라, "저조도 regime에서 register-only 대비 mAP 손실이 guardrail 안에 들어오므로 resource-saving RM 후보가 될 수 있다"로 해석해야 한다.

## 3. 반드시 고쳐야 할 문제

### P0-1. 평가 스크립트가 없다

문서에는 아래 재현 명령이 적혀 있다.

```bash
python3 tools/eval_map_coco.py --root ../../data/exdark_val --work data/_exdark_work --limit 0 --remap none --tag ExDark --out results/map_exdark.csv
python3 tools/eval_map_coco.py --root ../../data/coco_val --limit 0 --out results/map_real_full.csv
```

하지만 검사 시점 기준 로컬 repo `/opt/data/dfxisp_md`에는 다음 파일이 없다.

```text
MISSING tools/eval_map_coco.py
MISSING tools/eval_map_dark.py
MISSING tools/rm_model.py
MISSING results/map_exdark.csv
MISSING results/map_real_full.csv
MISSING results/map_exdark_bilinear.csv
```

Drive 검색에서도 `eval_map_coco.py`, `eval_map_dark.py`, `rm_model.py`를 찾지 못했다.

조치:

1. 실제 사용한 평가 스크립트를 `isppipeline/hls/tools/` 또는 repo의 적절한 `tools/` 아래에 복원한다.
2. `README` 또는 `paper/05-experiment-protocol.md`에 정확한 실행 위치와 dependency를 기록한다.
3. 최소 smoke mode를 제공한다. 예: `--limit 10`으로 빠르게 재현 가능해야 한다.
4. 결과 CSV와 스크립트 버전/commit을 연결한다.

### P0-2. Drive 최신 산출물과 로컬 Git repo가 불일치한다

Drive에는 최신 문서가 있지만 로컬 repo에는 없다.

| 파일 | Drive | 로컬 repo |
|---|---:|---:|
| `05-experiment-protocol.md` | 있음 | 없음 |
| `07-sw-stage-results-2026-06-28.md` | 있음 | 없음 |
| `08-e2-map-results-2026-06-29.md` | 있음 | 없음 |
| `measurements/map.csv` | 있음 | 없음 |
| `measurements/map_exdark_bilbin.csv` | 있음 | 없음 |

조치:

1. Drive 최신 문서를 로컬 repo의 canonical 위치로 반영한다.
2. 문서/측정치/스크립트가 한 repo revision에서 함께 보이도록 정리한다.
3. git push는 사용자 승인 전까지 하지 말고, 우선 diff와 proposed commit plan만 작성한다.

### P0-3. 문서 안에 구버전 서사가 남아 있다

`01-thesis-draft.md`에는 아직 DFX-FP를 "핵심 제안"처럼 표현하는 문장이 남아 있다. 하지만 같은 문서 후반에는 DFX-FP가 ExDark mAP에서 최저라 ablation으로 둔다고 되어 있다.

조치:

- DFX-FP = main contribution 표현 제거.
- DFX-FP = failed ablation / 재설계 후보로 통일.
- DFX-Bin bilinear = guardrail-passing DFX RM 후보로 통일.
- register-only = mAP baseline/core adaptation으로 통일.
- NotebookLM report `notebooklm-report-DFX-AIISP-2026-06-28.md`는 6/29 결과가 반영되지 않은 구버전으로 명시하거나 deprecated 처리한다.

### P0-4. resource/power/PR latency가 비어 있다

현재 DFX의 논문상 1차 주장을 resource/power/PR latency로 옮겼다. 그런데 `resource.csv`, `power_perf.csv`, `pr_latency.csv`는 아직 빈 template이다.

즉, 현재는 mAP guardrail은 일부 확보했지만, DFX의 핵심 정당화 근거는 아직 없다.

조치:

1. Vivado/Vitis 결과에서 LUT/FF/BRAM/DSP, Fmax/WNS를 채운다.
2. partial bitstream size를 채운다.
3. ICAP throughput 기반 PR latency model과 실측값을 분리해 기록한다.
4. board 측정 전이라면 반드시 `[TODO:측정]` 또는 `model-only`로 표시한다.

## 4. Claude 실행/운영 피드백

이전 handoff에는 Claude Code 실행이 다음 이유로 실패했다고 기록되어 있다.

```text
Claude Code handoff failed: Not logged in · Please run /login
```

따라서 Claude가 실제로 연구 활동을 수행했다는 실행 증거가 약하다.

조치:

1. Claude Code 인증 상태를 먼저 복구한다.

```bash
claude auth status --text
claude auth login
```

2. 이후 Claude 작업은 최소한 다음 로그를 남긴다.

```text
- session id 또는 실행 timestamp
- input handoff file
- 읽은 파일 목록
- 생성/수정한 파일 목록
- 실행한 검증 명령
- 생성한 CSV/Markdown 산출물
- 실패/미검증 항목
```

3. Claude는 임의로 "완료"라고 하지 말고, reproducibility checklist를 통과해야 완료로 보고한다.

## 5. Claude에게 요청하는 즉시 작업

아래 순서대로 처리할 것.

### Step 1 — 재현성 패키지 복원

- 실제 사용한 평가 코드 복원:
  - `tools/eval_map_coco.py`
  - `tools/eval_map_dark.py` 또는 통합 evaluator
  - `tools/rm_model.py`
  - DFX-Bin bilinear 구현
- dependency 기록:
  - Python version
  - ultralytics version
  - torch version
  - pycocotools 여부
  - model checkpoint: `yolov8n.pt`, `yolov8s.pt`

### Step 2 — 결과 파일 정리

- `measurements/` 아래에 CSV 정리:
  - `map.csv`
  - `map_coco_bilbin.csv`
  - `map_exdark_bilbin.csv`
  - `map_exdark_yolov8s.csv`
  - `scheduler.csv`
  - `resource.csv`, `power_perf.csv`, `pr_latency.csv`는 빈 template이면 template임을 명시

### Step 3 — 문서 정합성 정리

- `00-thesis-outline.md`
- `01-thesis-draft.md`
- `03-figures-tables.md`
- `05-experiment-protocol.md`
- `08-e2-map-results-2026-06-29.md`

위 파일에서 다음 용어를 일관화한다.

```text
register-only = mAP/core adaptation baseline
DFX-Bin bilinear = mAP guardrail 통과한 resource-saving RM 후보
DFX-FP = failed ablation / 재설계 후보
DFX = mAP 향상 장치가 아니라 resource/power/area trade-off 장치
```

### Step 4 — 검증 명령 실행

가능한 최소 검증:

```bash
# small smoke
python3 tools/eval_map_coco.py --root <small_exdark_sample> --limit 10 --out /tmp/map_smoke.csv

# CSV sanity
python3 - <<'PY'
import csv
for f in ['measurements/map.csv']:
    rows=list(csv.DictReader(open(f)))
    assert rows, f
print('csv sanity ok')
PY
```

### Step 5 — review report 작성

`paper/09-claude-reproducibility-fix-report-2026-06-29.md` 같은 파일에 다음을 남길 것.

```text
- fixed files
- restored scripts
- exact commands run
- outputs generated
- still unverified
- next human approval needed
```

## 6. 완료 기준

Claude의 이번 follow-up은 아래가 모두 만족될 때 완료로 인정한다.

- [ ] mAP 평가 스크립트가 repo/Drive에 존재한다.
- [ ] `measurements/map.csv`를 생성한 명령이 문서화되어 있다.
- [ ] `--limit 10` smoke evaluation이 실행된다.
- [ ] DFX-FP를 main contribution으로 부르는 표현이 제거됐다.
- [ ] Drive와 로컬 repo의 paper/measurement 문서가 같은 최신 내용을 가리킨다.
- [ ] resource/power/PR latency는 실측 전이면 빈 template이 아니라 `TODO/model-only`로 명확히 표시된다.
- [ ] Claude 실행 로그 또는 handoff report가 남아 있다.

## 7. 요약 메시지

Claude에게 한 줄로 말하면:

> 연구 해석은 좋아졌다. 하지만 지금은 재현 가능한 연구 패키지가 아니다. 평가 코드·CSV 생성 절차·Drive/Git 정합성·DFX-FP 서사 정리를 먼저 끝내라. 특히 DFX의 논문 주장을 resource/power로 옮겼으니, 그 측정 표를 비워둔 채로는 기여가 완성되지 않는다.
