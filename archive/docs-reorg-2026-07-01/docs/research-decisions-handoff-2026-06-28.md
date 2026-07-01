# DFXISP research decision handoff — low-light RM / ZCU104 / variants / metrics

Created: 2026-06-28T13:34:49+00:00
Owner/requester: 이형민
Context: Slack thread `C0BA8DR4VV1 / 1782653639.454439`

## User request

이형민 asked whether we had already discussed/decided the following DFXISP research items:

- low-light RM 범위
- ZCU104 타깃 해상도
- FPGA 확정 여부
- 비교군 고정: `Static / register-only / DFX-bin / DFX-FP` 4 variants
- machine-vision metric

The user then instructed: “찾아보고 있으면 로그 남기고 클로드한테 넘겨”.

## Evidence found so far from Hermes session search

### Source A — Slack session `20260626_065145_f81aa35a`, title “AI-ISP Novelty Ideas”

Key assistant statement found in the prior decision thread:

> 지금 novelty를 키우려면 “DFX를 쓴 ISP”가 아니라 “task-aware AI-ISP에서 register 적응과 DFX 적응을 분리하고, 구조적으로 무거운 저조도 perception block만 ZCU104에서 부분재구성하는 resource-aware AI-ISP”로 재정의하는 게 가장 좋습니다.

Confirmed/proposed points from that session:

1. **Novelty framing**
   - Main claim should be: decide what is enough with register adaptation and what deserves DFX RM replacement, evaluated by task mAP/resource/latency on ZCU104.
   - Quote-level summary: “AI-ISP에서 무엇은 register로 충분하고, 무엇은 DFX RM으로 교체할 가치가 있는지를 task mAP·resource·latency 기준으로 분리하고 ZCU104에서 검증한다.”

2. **Low-light RM scope / candidates**
   - DFX should not be used for simple parameter changes (`gain`, `gamma`, threshold). Those belong in register/LUT adaptation.
   - DFX RM should be reserved for structural or heavier low-light perception blocks.
   - Candidate low-light RM set discussed:
     - Current/baseline: `2x2 binning + gain + gamma`
     - Improved: non-binning low-light RM
     - Stronger: soft-knee clipping prevention + local contrast + small denoise
     - Paper-style: Dark-ISP-inspired linear/nonlinear split reduced to fixed-point HLS
   - Important caveat: `2x2 binning + gain + gamma` is implementation-simple but risks hurting detection because of resolution loss. Therefore, a feature-preserving RM is needed.
   - No exact numeric illuminance/lux range was found yet in session search. What was decided is *functional scope* of the RM, not a calibrated lux range.

3. **Comparison variants**
   A 4-variant table was explicitly proposed/fixed for paper evaluation:

   | Variant | Adaptation | Low-light block | DFX? |
   |---|---|---|---|
   | Static | none | none | no |
   | Reg-only | gain/gamma | resident | no |
   | DFX-Bin | reg + binning RM | 2x2 binning | yes |
   | DFX-FP | reg + feature-preserving RM | denoise/soft-knee | yes |

   This was also recorded in the Slack archive as: “DFXISP 실험 variant 후보는 `Static`, `Reg-only`, `DFX-Bin`, `DFX-FP(feature-preserving low-light RM)`로 고정하는 방향이 제안됨.”

4. **Machine-vision metric**
   - The evaluation should prioritize downstream task metric, especially object detection `mAP`, rather than human visual quality.
   - Table plan fixed:
     - `Tab6 — machine-vision mAP`
     - Variant table columns included `mAP ExDark` and `mAP COCO`.
   - Supporting metrics also planned: resource, power, FPS, PR/reconfiguration latency, scheduler stability.

5. **ZCU104 / FPGA target**
   - The proposed title and framing use Zynq UltraScale+ / ZCU104 explicitly:
     - “DFX-AIISP: A Resource-Aware Dynamically Reconfigurable Task-Aware ISP for Low-Light Object Detection on Zynq UltraScale+”
     - Korean outline title: “ZCU104 FPGA를 위한 DFX 기반 Resource-Aware Task-Aware AI-ISP 설계”
   - HLS target part documented later: `xczu7ev-ffvc1156-2-e`, which is the ZCU104 Zynq UltraScale+ MPSoC part.

### Source B — Slack session `20260628_064313_e49be360`, title “DFXISP 진행 상황 점검”

Relevant HLS/manual decisions already reflected in `docs/HLS_SYNTH_COSIM.md`:

- Canonical GitHub repo: `https://github.com/haengmini/dfxisp.git`
- Executable HLS flow path: `isppipeline/hls/`
- HLS top: `dfxisp_accel`
- HLS part: `xczu7ev-ffvc1156-2-e`
- Clock: `5.0 ns` default
- Current test fixtures are synthetic 8x8/16x16 grid/brightness scenarios.
- Current default output shape is `H x W` for NORMAL/LOW_LIGHT/AUTO because the top interface has one output buffer and no output width/height metadata.
- `2x2 binning` or `H/2 x W/2` output should stay a separate ablation/RM variant until explicit shape metadata or resize/pad/upsample stage exists.

Important interpretation:

- **ZCU104 FPGA target is effectively fixed** at board/part level for HLS docs.
- **Target image/application resolution is not yet fixed** in the evidence found. Current 8x8/16x16 sizes are verification fixtures, not final camera/DPU resolution.
- Need to avoid claiming final target resolution unless a real decision document or Slack message is found.

## Current decision status table

| Item | Current status | Evidence / note |
|---|---|---|
| FPGA / board | Mostly fixed | ZCU104 / Zynq UltraScale+ repeatedly used; HLS part `xczu7ev-ffvc1156-2-e`. |
| HLS top/part/clock | Fixed for current flow | `dfxisp_accel`, `xczu7ev-ffvc1156-2-e`, `5.0 ns`. |
| Target resolution | Not found as final decision | Current 8x8/16x16 are fixtures only. Current HLS ABI preserves `H x W`; final camera/DPU resolution needs explicit decision. |
| Low-light RM scope | Functionally decided, numeric range not found | Register handles gain/gamma/threshold; DFX handles heavier structural low-light perception block. Need numeric low-light thresholds/ranges if required. |
| Comparison variants | Strongly proposed/fixed for evaluation | `Static`, `Reg-only`, `DFX-Bin`, `DFX-FP`. |
| Machine-vision metric | Decided direction | Primary: detection mAP, with ExDark/COCO columns. Supporting: resource, power, FPS, PR latency, scheduler stability. |

## Suggested next action for Claude

Claude should independently inspect local project docs and archives, then produce a concise “decision ledger” that separates:

1. **Confirmed decisions** — backed by repo docs/session/archive text.
2. **Proposed but not formally locked** — e.g., 4 variants may be described as “fixed direction” unless docs say final.
3. **Still missing / needs 이형민 decision** — likely final target resolution and numeric low-light RM threshold/range.
4. **Recommended canonical place to record** — likely `DFXISP/docs/` and Drive `DFXISP/docs/`.

Claude should not fabricate values for:

- final image resolution,
- lux/EV thresholds,
- real HLS csynth/cosim resource numbers,
- board PR latency,
- mAP numbers.

## Files/locations Claude should inspect

Local repo:

- `/opt/data/dfxisp_md/docs/HLS_SYNTH_COSIM.md`
- `/opt/data/dfxisp_md/docs/README.md`
- `/opt/data/dfxisp_md/isppipeline/hls/reports/latest.md`
- `/opt/data/dfxisp_md/isppipeline/hls/Makefile`
- `/opt/data/dfxisp_md/isppipeline/hls/scripts/vitis_hls.tcl`

Local Drive mirror / research docs, if needed:

- `/opt/data/agent_os_archive/files/06-production/DFXISP/dfxisp-4-contribution-research-plan-2026-06-26.md`
- `/opt/data/agent_os_archive/files/06-production/DFXISP/novelty-aiisp-ideas-2026-06-26.md`
- `/opt/data/agent_os_archive/files/06-production/DFXISP/paper/00-thesis-outline.md`
- `/opt/data/agent_os_archive/files/06-production/DFXISP/paper/01-thesis-draft.md`
- `/opt/data/agent_os_archive/files/06-production/DFXISP/paper/03-figures-tables.md`
- `/opt/data/slack_channel_archive/C0BA8DR4VV1.md`

## Hermes note

Hermes found enough evidence to answer that many items were discussed, but not enough to claim all were formally finalized. Most importantly:

- 4-variant matrix and machine-vision mAP direction are well-supported.
- ZCU104/FPGA target is well-supported at board/part level.
- Final target resolution and numeric low-light range are not yet found as locked decisions.

## Claude Code handoff attempt

Attempted: 2026-06-28T13:34:49+00:00

Command attempted from `/opt/data/dfxisp_md` using Claude Code print mode, read-only tools, and this handoff file as the task context.

Result:

```text
Claude Code is installed at /usr/local/bin/claude, version 2.1.169.
Handoff execution failed because Claude Code is not logged in: "Not logged in · Please run /login".
```

Action needed before Claude can continue:

```bash
claude auth login
# or inside interactive Claude Code: /login
```

After login, rerun the handoff prompt against this file.
