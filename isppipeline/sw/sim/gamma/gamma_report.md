<!--
=============================================================================
File   : isppipeline/sw/sim/gamma/gamma_report.md
Date   : 2026-08-12 KST (LOD_test migration re-run); §9 added 2026-08-13.
Function: gamma.md §3의 재현 절차(bit-exact 게이트 → 4-arm 톤커브 ablation →
          교차 검출기 검증)를 dataset/LOD_test에 대해 다시 실행한 결과(§1-8).
          §9는 자체완결형 gamma_sim.py 신규 실행 결과 — bit-exact 게이트
          재확인 및 §2.1 설계 의도(GAT의 read-noise floor 증폭 억제) 자체의
          최초 직접 측정. 방법론은 gamma.md에 고정되어 있으므로 이 문서는
          실행 산출물과 해석만 담는다.
Sources: gamma.md, gamma_ablation_yolov8n_lodtest.csv,
         gamma_ablation_ssdlite_lodtest.csv (§1-8). 재사용한 스크립트(경로만
         인용, 이 리포로 복사하지 않음): .claude/worktrees/hw-interface-prompt/
         isppipeline/hls/tools/{verify_new_arm_pipelines,eval_map_isp,
         eval_map_isp_ssd}.py (브랜치 docs/gat-doc-consistency-2026-08-06,
         커밋 334a293). 비교 대상: 같은 워크트리 기준 오늘 앞서 만든
         archive/sim-lod-test-migration-2026-08-12/isppipeline/sw/sim/gamma/
         gamma_report.md(SonyNOD split_nod, n=83, 오늘 이른 시각 실행).
         §9: gamma_sim.py(신규), gamma_bitexact_results.csv,
         gamma_noise_floor_results.csv, gamma_lut_shapes.png,
         gamma_noise_floor.png (전부 이번 실행 신규 산출물).
=============================================================================
-->
# gamma — 실행 결과 (2026-08-12, LOD_test)

## 0. 결론부터

1. **"톤 커브 자체가 필수적이다"(gamma/GAT/subsample 모두가 linear를
   압도한다)는 결론은 LOD_test에서도 뚜렷이 재현됐다.** YOLOv8n에서
   subsample−linear = `+0.0184`/`+0.0334`, SSDLite에서 subsample−linear
   = `+0.0059`/`+0.0156` — 두 검출기·두 지표 모두 잡음대(~0.005) 기준을
   넉넉히 넘는다.
2. **그러나 `gamma > GAT > subsample` 순위의 세부 서수관계는 LOD_test
   에서 재현되지 않았다.** SSDLite에서는 원본과 같은 순서
   (gamma > GAT > subsample)가 나왔지만 효과크기가 잡음대 이하로
   줄었고, **YOLOv8n에서는 아예 subsample이 gamma/GAT보다 근소하게
   앞섰다**(mAP@[.5:.95] subsample 0.0716 > gamma 0.0710 > GAT
   0.0696). 이 결과를 숨기거나 완화해 서술하지 않는다 — gamma.md §3.3의
   판정 기준(부호 일치 + 잡음대 2배 이상)으로 보면, LOD_test에서
   gamma-GAT-subsample 3자 간 비교는 **"차이 있음"으로 판정할 수
   없다**(모든 쌍이 잡음대 이하이거나 검출기 간 부호가 엇갈림).
3. **gamma-GAT 방향(부호)만은 두 검출기 모두에서 유지됐다**
   (YOLO `+0.0014/+0.0019`, SSD `+0.0017/+0.0033` — 둘 다 양수) —
   원본의 "검출기 독립적 효과크기"라는 강한 주장까지는 아니지만, 최소한
   방향의 일관성은 남아있다.
4. bit-exact 게이트는 원본과 동일하게 PASS(40 trials/15,966 samples) —
   데이터셋과 무관한 검증이므로 당연한 결과다.
5. GAT 재도입 논의는 없다 — 이 실행은 회귀 검증 용도다. gamma.md §2.1.2의
   철회 결정을 뒤집을 근거가 나온 것도 아니다("linear는 명백히
   나쁘다"는 결론은 오히려 더 강하게 재현됐다) — 다만 gamma와 GAT/
   subsample 사이의 **세밀한 순위**는 데이터셋에 따라 잡음대 안에서
   흔들릴 수 있다는 것이 이번 실행의 새 정보다.

## 1. 실행 조건

- **스크립트**: 워크트리 `hw-interface-prompt`(브랜치
  `docs/gat-doc-consistency-2026-08-06`, 커밋 `334a293`)의
  `verify_new_arm_pipelines.py` / `eval_map_isp.py` / `eval_map_isp_ssd.py`를
  그 자리에서 실행(gamma.md §5 권고 그대로 — 복사하지 않음).
- **데이터**: `dataset/LOD_test`(신규 데이터셋, ARW/jpg/label 100장)를
  `isppipeline/sw/sim/build_lod_test_eval_root.py`(신규 어댑터)로
  `dataset/LOD_test_eval/{images,labels,raw_bin}` 레이아웃으로 변환 —
  **100/100장 전부 성공**(SonyNOD 재현 때와 달리 소스 파일 유실 없음).
  변환 세부사항(해상도 불일치 이슈 포함)은 최종 보고 "데이터 이슈" 참고.
- **모델**: YOLOv8n(Ultralytics 8.4.82, CPU), SSDLite MobileNetV3 Large
  (torchvision, COCO-pretrained, CPU — 이 머신은 `torch.cuda.is_available()
  =False`).
- **arm**: `lowlight_isp`(gamma 2.0, 배포), `lowlight_isp_gat`,
  `lowlight_isp_subsample`, `lowlight_isp_linear` — gamma.md §3.3과 동일한
  4-arm, BLC offset 2 고정, WB 공유 상수.
- **주의**: `eval_map_isp_ssd.py`는 `eval_map_isp.py`가 만든 렌더를
  재사용하지 않고 독립적으로 다시 렌더한다(원본 gamma_report.md와 동일한
  주의사항).

## 2. 1단계 — bit-exact 정합성 게이트 (gamma.md §3.2)

```
[verify_new_arm_pipelines] PASS: 40 trials, 15966 channel samples,
vectorised proxies bit-exact with the scalar canonical goldens
```

데이터셋과 무관한 게이트이므로 원본(SonyNOD 재현, 오늘 이른 시각)과
정확히 같은 숫자로 PASS했다.

## 3. 2단계 — 4-arm 톤커브 ablation, YOLOv8n (gamma.md §3.3)

`eval_map_isp.py --arms lowlight_isp,lowlight_isp_gat,lowlight_isp_subsample,lowlight_isp_linear --blc-offsets 2 --model yolov8n.pt` (n=100)

| arm (stage 5) | mAP@[.5:.95] | mAP@50 |
|---|---:|---:|
| **`lowlight_isp` (gamma 2.0)** | 0.0710 | 0.1422 |
| `lowlight_isp_gat` | 0.0696 | 0.1403 |
| **`lowlight_isp_subsample`** | **0.0716** | **0.1420** |
| `lowlight_isp_linear` | 0.0532 | 0.1086 |

| 비교 | Δ mAP@[.5:.95] | Δ mAP@50 | 잡음대(0.005) 대비 |
|---|---:|---:|---|
| gamma − GAT | +0.0014 | +0.0019 | 이하 |
| gamma − subsample | **−0.0006** | +0.0002 | 이하 (부호도 뒤집힘) |
| GAT − subsample | −0.0020 | −0.0017 | 이하 |
| subsample − linear | +0.0184 | +0.0334 | **2배 이상 초과** |

**subsample이 gamma/GAT를 근소하게 앞섰다** — mAP@[.5:.95] 기준으로
`subsample(0.0716) > gamma(0.0710) > GAT(0.0696)`. 세 arm 사이의 모든
쌍별 차이가 잡음대(0.005) 이하라 gamma.md §3.3의 "차이 있음" 판정 기준을
어느 쌍도 충족하지 못한다 — **YOLOv8n 단독으로는 gamma>GAT>subsample
순위를 재현했다고 말할 수 없다.** 반면 linear는 세 arm 모두에게 압도적으로
밀린다(잡음대 2배 이상, gamma.md §2.1.1의 "톤 커브 자체가 필수" 결론은
그대로 유지).

## 4. 3단계 — 교차 검출기 검증, SSDLite MobileNetV3 (gamma.md §3.4)

`eval_map_isp_ssd.py --arms (동일 4개) --blc-offsets 2 --device cpu` (n=100)

| arm (stage 5) | mAP@[.5:.95] | mAP@50 |
|---|---:|---:|
| **`lowlight_isp` (gamma 2.0)** | **0.0458** | **0.1031** |
| `lowlight_isp_gat` | 0.0441 | 0.0998 |
| `lowlight_isp_subsample` | 0.0403 | 0.0907 |
| `lowlight_isp_linear` | 0.0344 | 0.0751 |

| 비교 | Δ mAP@[.5:.95] | Δ mAP@50 | 잡음대(0.005) 대비 |
|---|---:|---:|---|
| gamma − GAT | +0.0017 | +0.0033 | 이하 |
| GAT − subsample | +0.0038 | +0.0091 | mAP50만 근접(2배 미만) |
| subsample − linear | +0.0059 | +0.0156 | mAP50만 2배 초과 |

SSDLite 단독으로 보면 순위(`gamma > GAT > subsample > linear`)는 원본과
같은 방향이다. 하지만 gamma-GAT 격차(0.0017/0.0033)는 원본(SonyNOD
`+0.0098/+0.0074`)보다 훨씬 작아졌고 잡음대 기준을 넘지 못한다 —
**"차이가 있다"고 판정할 근거로는 부족**하다.

## 5. 두 검출기 종합 — LOD_test에서는 순위가 확정되지 않는다

| 비교 | YOLOv8n 부호 | SSDLite 부호 | 부호 일치 | 잡음대 2배 통과(둘 다) |
|---|---|---|---|---|
| gamma vs GAT | + | + | ✅ | ❌ (둘 다 미달) |
| gamma vs subsample | **−**(mAP5095) / +(mAP50) | + / + | ❌(지표 간 불일치) | ❌ |
| GAT vs subsample | − / − | + / + | **❌(검출기 간 부호 반전)** | ❌ |
| subsample vs linear | + / + | + / + | ✅ | YOLO만 통과 |

gamma.md §3.4의 판정 기준("순위가 2검출기×2지표 전부에서 동일해야
재현 성공")을 엄격히 적용하면, LOD_test에서 재현에 성공한 것은
**"어떤 톤 커브를 쓰든 linear보다는 낫다"** 하나뿐이다. gamma·GAT·
subsample 세 arm 사이의 세부 순위는 검출기 간 부호까지 엇갈려(특히
GAT vs subsample) 확정할 수 없다.

## 6. 원본(SonyNOD nod83, 2026-08-12 이른 시각) 대비 비교

| | 원본(SonyNOD, n=83) | 이번(LOD_test, n=100) |
|---|---|---|
| gamma-GAT (YOLO) | +0.0106 / +0.0099 | +0.0014 / +0.0019 |
| gamma-GAT (SSD) | +0.0098 / +0.0074 | +0.0017 / +0.0033 |
| 4-arm 순위 재현 | 4개 비교 전부 일치 | **재현 안 됨**(§5) |
| linear가 최하위 | 압도적, 재현 | **압도적으로 재현**(오히려 격차 확대) |

**해석**: gamma-GAT 효과크기가 원본 대비 5~7배 작아졌다(YOLO
`0.0106→0.0014`, SSD `0.0098→0.0017`). 원인은 확정할 수 없지만
정황상 유력한 후보는: (a) LOD_test가 SonyNOD보다도 더 극단적인
저조도(§2 참고, raw 평균값이 black level에서 겨우 몇십~몇백 DN
위)라서 절대 mAP 자체가 낮고(YOLOv8n 주지표 0.07~0.18 vs SSD
0.03~0.11대) 검출기가 애초에 신뢰도 낮은 판단을 내려 톤 커브
차이에 덜 민감할 수 있다는 점, (b) 100장이라는 표본 크기에서
0.001~0.003 수준 효과크기는 통계적으로 잡음과 구분이 잘 안 된다는
점. **이 결과가 gamma 2.0 채택 결정 자체를 반증하는 것은 아니다**
— gamma는 여전히 두 검출기 모두에서 GAT보다 부호상 우위이고
linear보다는 확실히 우위다. 다만 "톤 커브 선택의 세부 순위가 데이터셋에
걸쳐 안정적으로 재현된다"는 더 강한 주장은 LOD_test로는 뒷받침되지
않는다 — 이 차이를 숨기지 않고 그대로 기록한다(프로젝트 원칙,
gain.md §3.2 "파괴적 결과가 나와도 지우지 말 것"과 동일 정신).

## 7. 생략/미실행 (gamma.md 대비)

- **§3.1 노이즈 모델 캘리브레이션**: `binning_report.md` §2에서 LOD_test
  ISO 6400 서브셋으로 **재캘리브레이션에 성공**했다(`A_Q8=4114`,
  `B_DN2=803`, R²=0.997 — 2026-08-13). 단, **이 절의 mAP 실행은 그 이전에
  배포 상수(4065/746)로 수행됐고 새 상수로 다시 돌리지 않았다.**
  판단 근거: 배포 톤커브인 gamma 2.0 LUT는 노이즈 모델 상수에 전혀
  의존하지 않으므로(`GAMMA2_LUT`은 순수 제곱근) 배포 arm의 수치는 상수와
  무관하다. 영향을 받는 것은 `TONE_GAT` arm의 LUT 하나뿐이며(GAT의 `a,b`가
  곧 이 상수), GAT는 이미 철회된 대조군이다. 다만 §3/§4의 gamma−GAT 격차
  수치는 엄밀히 말해 "구 상수로 만든 GAT 커브 기준"이라는 점을 명시해둔다
  — 새 상수로 GAT arm을 다시 렌더하면 이 격차는 소폭 달라질 수 있다(상수
  변화가 a +1.2%/b +7.6%로 작아 순위가 뒤집힐 가능성은 낮지만, 검증하지
  않았으므로 단정하지 않는다).
- **§3.5 배포 전환 후 재검증**: 원본과 동일하게 별도 실행 불필요.
- **§4의 미측정 항목(PASCAL 주광 조건)**: 이번 실행 범위 밖.
- **resource/csynth 재측정**: 이번 실행은 소프트웨어 mAP 재현에 한정.

## 8. 참고

- 이전 실행(SonyNOD, n=83, 2026-08-12 이른 시각):
  `archive/sim-lod-test-migration-2026-08-12/isppipeline/sw/sim/gamma/
  gamma_report.md` — 원본 산출물(csv/png)도 같은 경로에 보존.
- 원자료: `gamma_ablation_yolov8n_lodtest.csv`,
  `gamma_ablation_ssdlite_lodtest.csv` (이번 실행, n=100).
- 방법론: `gamma.md` §3.

## 9. `gamma_sim.py` — 자체완결형 재현 스크립트 실행 결과 (2026-08-13)

§1-8의 mAP ablation은 워크트리 전용 도구(`eval_map_isp*.py`)에 의존해
이 리포로 복사되지 않았다(gamma.md §5). 반면 gamma.md §2.4가 "라이브
트리에서 이미 재현 가능"으로 표시한 두 항목 — §3.2 bit-exact 게이트와
§2.2 LUT 자체 — 는 이 브랜치의 `gen_lowlight_isp_golden.py`/
`lowlight_isp_pipeline.py`만으로 완결되므로, 다른 세 모듈(blc/gain/
binning)처럼 자체완결형 `<module>_sim.py`로 만들어 `isppipeline/sw/sim/
gamma/gamma_sim.py`에 신규 작성했다. 추가로, §1-8이 측정한 것은 GAT
채택/철회의 **결과**(mAP)뿐이고 §2.1이 주장한 **설계 의도**(GAT가 원점에서
선형이라 read-noise floor를 덜 증폭시킨다)는 이 리포 어디에도 직접
측정된 적이 없었다는 것을 발견해, 이번 스크립트에 §2.1 자체를 검증하는
2부를 추가했다.

### 9.1 Part A — bit-exact 게이트 (gamma.md §3.2)

`python3 gamma_sim.py` 실행: 40 trials × 7 shapes(1×1, odd dims 포함) ×
4 content mode(uniform random/near-floor/extremes/flat+noise) × binning
2종(BINNING/SUBSAMPLE) × tone 3종(GAT/GAMMA2.0/LINEAR).

```
[gamma_sim] PASS: 40 trials, 6588 channel samples, lowlight_isp_pipeline.
run_lowlight_isp bit-exact with the scalar gen_lowlight_isp_golden.lowlight_isp
```

전량 PASS — 벡터화 numpy 프록시가 스칼라 golden과 bit-exact로 일치한다.
(워크트리의 `verify_new_arm_pipelines.py`가 보고한 15,966 채널 샘플은
`default_isp` 게이트까지 합친 수치라 이 스크립트의 6,588(lowlight_isp
전용)과 직접 비교되는 숫자는 아니다 — gamma.md 범위는 lowlight_isp뿐이므로
의도적으로 축소했다.)

### 9.2 Part B — read-noise-floor 증폭 측정 (gamma.md §2.1의 설계 의도 자체 검증)

방법: 캘리브레이션된 Poisson-Gaussian 잡음모델(`A_Q8=4065`, `B_DN2=746`)로
BLC_LEVEL12(32) 안팎의 참신호 15단계(0~512 DN)에서 노이즈가 낀 raw를
생성하고, **실제 파이프라인 함수를 그대로**(binning → BLC/gain → CCM,
`gen_lowlight_isp_golden.py`에서 재사용, 재구현 없음) 통과시킨 뒤 stage
⑤ LUT만 GAT/GAMMA2.0/LINEAR로 바꿔 8비트 출력의 표준편차를 비교했다
(n=4000 repeat/level).

**결과: 설계 의도는 21개 (신호레벨×채널) 지점 중 20개에서 성립했다**
(예외 1건은 신호=0, G채널에서 두 곡선의 표준편차가 모두 사실상 0으로
바닥을 쳐 순서가 무의미해지는 퇴화 케이스). pedestal 이하 구간에서 GAT의
출력 표준편차는 GAMMA2.0의 약 **42~51%**였다(예: s=32, R채널
std_GAT=5.957 vs std_GAMMA2.0=11.812, ratio=0.50). `gamma_lut_shapes.png`가
보여주듯 GAT는 원점에서 유한한 기울기(선형)인 반면 GAMMA2.0(제곱근)은
원점에서 기울기가 발산해, 낮은 신호의 잡음을 그대로 증폭시킨다 — §2.1이
설계 시점에 주장한 메커니즘이 정확히 이 방향으로 측정된다.

**§0(결론)과의 관계 — 메커니즘은 참이지만 결과를 뒤집지 않는다**: 이
측정은 §2.1의 설계 의도가 **틀리지 않았음**을 보여준다 — GAT는 실제로
read-noise floor를 덜 증폭시킨다. 그런데도 §1-8의 mAP ablation에서는
gamma 2.0이 GAT를 이긴다(SonyNOD 원본, LOD_test에서는 부호만 유지).
즉 "노이즈 증폭이 적다"는 국소적 신호 품질 이득이 검출기의 최종 mAP로
이어지지 않았다는 뜻이다 — 이 자체가 새로운 정보다: GAT 철회 결정
(`lowlight_isp.md` §2.1.2)은 재도입 논거가 없다는 결론을 이번 실행이
한 번 더 뒷받침하되, 이유는 "GAT가 설계대로 작동하지 않아서"가 아니라
"국소 잡음 억제가 검출 성능과 상관관계가 약해서"임을 처음으로 직접
보여준다.

### 9.3 생성 산출물

- `gamma_sim.py` — 스크립트(신규).
- `gamma_bitexact_results.csv` — Part A 원자료(trial별 pass/fail).
- `gamma_noise_floor_results.csv` — Part B 원자료(신호레벨×채널×tone별
  output_std).
- `gamma_lut_shapes.png` — 세 LUT의 전체/근접(0-256) 형태 비교.
- `gamma_noise_floor.png` — R/G/B별 output_std vs 신호레벨, tone 3종 비교.

### 9.4 미실행 (여전히)

§1-8의 mAP ablation(§3.3/§3.4)은 이번 스크립트로 대체되지 않았다 — 실제
검출기 추론이 필요해 자체완결형으로 재현할 수 없다는 gamma.md §5의
판단은 그대로 유효하다. §9는 §1-8을 대체가 아니라 보완한다: §1-8은
"철회가 결과적으로 옳았는가", §9는 "철회 이유였던 설계 가정이 실제로
참인가"를 답한다.
