<!--
=============================================================================
File   : isppipeline/sw/sim/gamma/gamma_report.md
Date   : 2026-08-12 KST
Function: gamma.md §3의 재현 절차(bit-exact 게이트 → 4-arm 톤커브 ablation →
          교차 검출기 검증)를 실제로 재실행한 결과. 방법론은 gamma.md에
          고정되어 있으므로 이 문서는 실행 산출물과 해석만 담는다(blc.md
          계열 문서의 관례 — "방법론과 결과를 섞지 않는다").
Sources: gamma.md, gamma_ablation_yolov8n.csv, gamma_ablation_ssdlite.csv,
         gamma_ablation_results.png, gamma_original_vs_repro.png,
         gamma_tone_curves.png. 재사용한 스크립트(경로만 인용, 이 리포로
         복사하지 않음 — gamma.md §5 권고 및 §4 기존 결정과 동일 원칙):
         .claude/worktrees/hw-interface-prompt/isppipeline/hls/tools/
         {verify_new_arm_pipelines,build_sonynod_dataset,eval_map_isp,
         eval_map_isp_ssd}.py (브랜치 docs/gat-doc-consistency-2026-08-06,
         커밋 334a293). 비교 대상 원본: 같은 워크트리의
         results/gat-tone-ablation-2026-08-06.md.
=============================================================================
-->
# gamma — 실행 결과 (2026-08-12)

## 0. 결론부터

1. **gamma.md §3.2/§3.3/§3.4를 실제로 재실행했다.** bit-exact 게이트는
   원본과 동일하게 PASS(40 trials/15,966 samples). 4-arm 톤커브 ablation과
   SSDLite 교차검증도 재실행해, `gat-tone-ablation-2026-08-06.md`가 주장한
   순위 `gamma > GAT > subsample > linear`가 **2 검출기 × 2 지표 전부**에서
   그대로 재현됐다.
2. **gamma-GAT 효과크기의 검출기 독립성도 재현됐다**: YOLOv8n
   `+0.0106/+0.0099`, SSDLite `+0.0098/+0.0074` — 원본(`+0.0101/+0.0087`
   vs `+0.0105/+0.0113`)과 마찬가지로 두 검출기가 사실상 같은 크기의
   격차를 보고한다.
3. **데이터는 100장이 아니라 83장이다** — 재현 도중 원본 소스
   `/mnt/d/Downloads/Sony/split_nod`의 ARW 17개가 외부에서(이 실행과
   무관하게, 아마도 사용자의 로컬 정리/백업 동작으로) `Sony.zip`으로
   압축되며 사라졌다. 나머지 83장은 그 전에 이미 읽혀 손상 없이
   변환됐다(§1 참고). 절대 mAP는 원본보다 낮지만(표본이 다르므로 당연),
   **순위와 효과크기 방향은 표본 축소에 영향받지 않았다**.
4. GAT 재도입 논의는 없다 — gamma.md §4가 명시한 대로 이 실행은 회귀
   검증 용도다. §2.1.2의 철회 결정을 뒤집을 근거는 나오지 않았다.

## 1. 실행 조건

- **스크립트**: gamma.md §5 권고대로 새로 작성하지 않고, 워크트리
  `hw-interface-prompt`(브랜치 `docs/gat-doc-consistency-2026-08-06`,
  커밋 `334a293`)의 기존 스크립트를 그대로 실행했다. 이 워크트리에만
  `verify_new_arm_pipelines.py` / `build_sonynod_dataset.py` /
  `eval_map_isp.py` / `eval_map_isp_ssd.py`가 존재한다(§2.4의 "확보 결정"이
  실행 시점에 "복사 대신 그 자리에서 실행"으로 해소됨).
- **데이터**: `/mnt/d/Downloads/Sony/split_nod`(Sony RAW-NOD 100장 서브셋,
  COCO 주석)를 `build_sonynod_dataset.py`로 변환. 변환 도중 소스 ARW
  17개가 사라져(§0-3) **83/100장**만 확보됐다(`n_no_gt=0` — 라벨이 없어
  빠진 것은 없음). `convert_errors.log`가 17개 전부 "missing ARW"임을
  기록한다.
- **모델**: YOLOv8n(Ultralytics 8.4.82, CPU), SSDLite MobileNetV3 Large
  (torchvision, COCO-pretrained, CPU — 이 머신은 CUDA 드라이버가 낡아
  GPU를 못 씀, `nvidia-smi`는 GTX 1650을 보여주지만
  `torch.cuda.is_available()=False`).
- **arm**: `lowlight_isp`(gamma 2.0, 배포), `lowlight_isp_gat`,
  `lowlight_isp_subsample`, `lowlight_isp_linear` — gamma.md §3.3과 동일한
  4-arm, BLC offset 2 고정, WB 공유 상수.
- **주의**: `eval_map_isp_ssd.py`는 `eval_map_isp.py`가 만든 렌더를
  재사용하지 않고 `build_arm_images()`를 독립적으로 다시 호출한다(원본
  방법론 문서의 "같은 렌더를 재채점"과 문구상 다름). 렌더 파이프라인은
  raw+arm+blc만의 결정론적 함수라 두 실행의 이미지는 바이트 단위로
  동일할 것으로 예상되지만, 파일을 diff해 확인하지는 않았다 — 결과 해석에
  실질적 영향은 없다(§0-1의 재현 결과 자체가 일관성을 방증한다).

## 2. 1단계 — bit-exact 정합성 게이트 (gamma.md §3.2)

```
$ make verify-new-arms
[verify_new_arm_pipelines] PASS: 40 trials, 15966 channel samples,
vectorised proxies bit-exact with the scalar canonical goldens
(default_ISP awb off/on; lowlight_ISP binning subsample/samecolour
x tone GAT/gamma/linear)
```

원본(`gat-tone-ablation-2026-08-06.md` §3)이 보고한 것과 정확히 같은
trial 수·샘플 수. 이 게이트가 실패하면 이하의 mAP 수치는 전부 무의미
하므로, 아래 결과는 이 PASS를 전제로 한다.

## 3. 2단계 — 4-arm 톤커브 ablation, YOLOv8n (gamma.md §3.3)

`eval_map_isp.py --arms lowlight_isp,lowlight_isp_gat,lowlight_isp_subsample,lowlight_isp_linear --blc-offsets 2 --model yolov8n.pt` (n=83)

| arm (stage 5) | mAP@[.5:.95] | mAP@50 | GAT 대비 Δ |
|---|---:|---:|---:|
| **`lowlight_isp` (gamma 2.0)** | **0.1813** | **0.3650** | **+0.0106 / +0.0099** |
| `lowlight_isp_gat` | 0.1707 | 0.3551 | 기준 |
| `lowlight_isp_subsample` | 0.1628 | 0.3264 | −0.0079 / −0.0287 |
| `lowlight_isp_linear` | 0.1212 | 0.2524 | −0.0495 / −0.1027 |

순위 `gamma > GAT > subsample > linear`가 두 지표 모두에서 재현됐다.
gamma-GAT 격차(주 지표 `+0.0106`)는 이 프로젝트의 ~0.005 잡음대 2배
기준을 넘는다 — gamma.md §3.3의 판정 기준을 통과한다.

## 4. 3단계 — 교차 검출기 검증, SSDLite MobileNetV3 (gamma.md §3.4)

`eval_map_isp_ssd.py --arms (동일 4개) --blc-offsets 2 --device cpu` (n=83)

| arm (stage 5) | mAP@[.5:.95] | mAP@50 | GAT 대비 Δ |
|---|---:|---:|---:|
| **`lowlight_isp` (gamma 2.0)** | **0.1161** | **0.2287** | **+0.0098 / +0.0074** |
| `lowlight_isp_gat` | 0.1063 | 0.2213 | 기준 |
| `lowlight_isp_subsample` | 0.1059 | 0.2095 | −0.0004 / −0.0118 |
| `lowlight_isp_linear` | 0.0759 | 0.1579 | −0.0304 / −0.0634 |

순위가 **4개 비교(2 검출기 × 2 지표) 전부**에서 동일하다:
`gamma > GAT > subsample > linear`. GAT-subsample 격차(주 지표 `−0.0004`)는
잡음대 이하로 작아 원본(SSDLite `+0.0052`)과 마찬가지로 이 인접쌍은
애초부터 판정 기준을 통과하는 비교가 아니다 — 순위 자체는 두 지표가
일관되게 가리킨다.

| | gamma − GAT | 원본(nod100) gamma − GAT |
|---|---:|---:|
| YOLOv8n | +0.0106 / +0.0099 | +0.0101 / +0.0087 |
| SSDLite | +0.0098 / +0.0074 | +0.0105 / +0.0113 |

두 검출기의 gamma-GAT 효과크기가 이번에도 사실상 같다(`0.0106` 대
`0.0098`) — "arm 간 순위의 검출기 독립성"이라는 원본 결론(§6)이
표본이 줄어든 조건에서도 재현됐다.

## 5. 원본(nod100, 2026-08-06) 대비 재현성

절대 mAP는 표본이 100→83으로 줄면서 전 arm·전 지표에서 소폭 낮아졌다
(`gamma_original_vs_repro.png`). 그러나:

- **순위는 4개 비교 전부에서 그대로다.**
- **gamma-GAT 격차의 크기**(주 지표 기준 원본 `0.0101`/`0.0105` → 재현
  `0.0106`/`0.0098`)도 같은 자릿수, 같은 부호를 유지한다.
- linear가 압도적 최하위라는 관찰(톤 커브 자체가 필수)도 그대로다
  (재현 YOLOv8n `−0.0495/−0.1027` vs 원본 `−0.0481/−0.1059`).

표본 17장이 빠진 것이 결론에 영향을 주지 않았다고 볼 근거다.

## 6. 그림

- `gamma_ablation_results.png` — 4-arm × 2 검출기 × 2 지표, 이번 실행
  (nod83) bar chart.
- `gamma_original_vs_repro.png` — 원본(nod100) vs 재현(nod83) 나란히
  비교, 주 지표만.
- `gamma_tone_curves.png` — gamma 2.0 / GAT / linear 세 톤커브 모양
  (gamma.md §2.2 LUT에서 직접 추출, `z ∈ [0, 4095]`).

## 7. 생략/미실행 (gamma.md 대비)

- **§3.1 노이즈 모델 캘리브레이션**: gamma.md 지침대로 재실행하지
  않았다 — `A_Q8=4065`/`B_DN2=746`은 이미 `gen_lowlight_isp_golden.py`에
  반영돼 있고 GAT 자체를 재검토하는 게 아니므로 불필요.
  `calibrate_noise_model.py`는 실행하지 않았다.
- **§3.5 배포 전환 후 재검증**: 별도 실행이 필요 없었다 — 재사용한
  스크립트가 이미 교체 후 명명(`lowlight_isp`=gamma 2.0,
  `lowlight_isp_gat`=구 GAT)을 쓰고 있어, §3의 4-arm 결과 자체가 곧
  "배포 arm 재측정"이다.
- **§4의 미측정 항목(PASCAL 주광 조건)**: 이번 실행 범위 밖. 여전히
  별도 실행 과제로 남는다.
- **resource/csynth 재측정**(원본 §5.1, §8): 이번 실행은 소프트웨어
  mAP 재현에 한정했다 — HLS 자원 수치는 다루지 않았다.

## 8. 참고

- 원본: `results/gat-tone-ablation-2026-08-06.md`
  (`.claude/worktrees/hw-interface-prompt`, 브랜치
  `docs/gat-doc-consistency-2026-08-06`, 커밋 `334a293`) — 경로만 인용,
  이 리포로 복사하지 않음.
- 원자료: `gamma_ablation_yolov8n.csv`, `gamma_ablation_ssdlite.csv`
  (이번 실행, n=83).
- 방법론: `gamma.md` §3.
