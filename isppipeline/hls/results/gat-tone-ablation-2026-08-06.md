<!--
File   : isppipeline/hls/results/gat-tone-ablation-2026-08-06.md
Added  : 2026-08-06
Function: lowlight_ISP stage (5)의 톤 커브를 단독으로 분리해 GAT/VST의 기여를
          측정한다. denoise 영구 제거 후의 자원 재측정도 함께 기록한다.
Sources: results/map_gat_ablation_nod100_2026-08-06.csv (YOLOv8n)
         results/map_gat_ablation_nod100_ssdlite_2026-08-06.csv (SSDLite MNv3)
         (csynth) 본문 §3, flat-tempdir 워크어라운드로 재측정
-->

# GAT 톤 커브 단독 ablation — NOD 100장 (2026-08-06)

## 0. 결론부터

1. **톤 커브 자체는 결정적이다.** 커브를 빼고 단순 절단(12→8)만 하면
   `−0.0481 / −0.1059`로 무너진다. 비선형 톤 매핑이 필요하다는 설계
   전제는 강하게 지지된다.
2. **그러나 GAT는 그 자리에서 최선이 아니다.** GAT가 대체하려던 평범한
   gamma 2.0이 **두 지표 모두에서 GAT를 이긴다**(YOLOv8n `+0.0101 / +0.0087`).
   주 지표 차이는 이 프로젝트의 ~0.005 잡음대의 2배이고, 두 지표의 부호가
   **일치**한다 — denoise 스윕에서 부호가 엇갈렸던 것과 대조적이다.
   **구조가 다른 검출기(SSDLite MobileNetV3)로 교차검증한 결과 순위와
   효과 크기가 그대로 재현됐다**(`+0.0105 / +0.0113`, §6).
3. 따라서 `src/lowlight_isp.md` §2.1이 "이 설계의 중심"이라고 적은 GAT는
   **측정으로 지지되지 않는다.** 교차검증까지 확인한 뒤 **배포 커브를
   gamma 2.0으로 교체했다**(§5) — 자원도 함께 크게 줄었다(§5.1).
4. binning(①)은 유지가 옳다: same-color가 subsample을 `+0.0040 / +0.0281`로
   앞선다.

## 1. 왜 지금 이 실험인가

denoise를 영구 제거하면서 **GAT의 원래 명분이 함께 사라졌다.** VST는
"밝기와 무관하게 분산을 균일화해서 *상수 임계 denoise*를 성립시키는" 변환인데,
그 소비자가 없어졌기 때문이다. 남은 역할은 톤 커브 하나뿐이므로 질문이
바뀐다 — "VST가 있으면 좋은가"가 아니라 **"노이즈 모델에서 유도한 커브가
평범한 gamma보다 나은가"**이다.

## 2. 설계

stage (5)의 4096-entry LUT **하나만** 바꾼다. binning·BLC·게인·CCM·출력
포맷은 전부 동일하므로 단일 축 실험이다.

| arm | stage (5) |
|---|---|
| `lowlight_isp` | GAT/Anscombe VST (**측정 당시의** 배포 커브) |
| `lowlight_isp_gamma` | gamma 2.0 — `default_ISP` 골든에서 **import**해 표류 불가 |
| `lowlight_isp_linear` | 커브 없음, `z >> 4` 절단 (바닥 대조군) |
| `lowlight_isp_subsample` | GAT, 단 binning만 구 subsample (①의 대조) |

> arm 이름은 측정 당시 기준이다. §5의 교체 이후 `lowlight_isp` = gamma 2.0,
> 구 GAT arm은 `lowlight_isp_gat`으로 이름이 바뀌었다.

세 커브의 모양(입력 12-bit → 출력 8-bit):

| 입력 z | 16 | 256 | 1024 | 4095 |
|---|---:|---:|---:|---:|
| linear | 1 | 16 | 64 | 255 |
| **GAT** | **4** | **45** | **114** | **255** |
| gamma 2.0 | 15 | 63 | 127 | 255 |

즉 GAT는 어두운 쪽에서 gamma보다 **덜 들어올린다**. 이것이 설계 의도였다
(read-noise floor 과증폭 방지). 측정 결과는 검출기가 그 반대를 선호한다는
것을 보여준다.

## 3. 조건

- 데이터: `data/split_nod` 야간 100장, ISO 6400, Sony RX100 VII
- 검출기: YOLOv8n (Ultralytics 8.4.82), CPU — 교차검증 SSDLite MobileNetV3 §6
- 고정: BLC offset 2, shared WB, same-color binning(subsample arm 제외)
- 하니스: `tools/eval_map_isp.py`, 렌더 병렬 6워커
- 프록시 정합: `make verify-new-arms` PASS — 40 trials / 15,966 channel
  samples, 스칼라 정본과 bit-exact (binning 2종 × tone 3종 전조합)

## 4. 결과

| arm (stage 5) | mAP@[.5:.95] | mAP@50 | GAT 대비 Δ |
|---|---:|---:|---:|
| **`lowlight_isp_gamma`** | **0.1876** | **0.3797** | **+0.0101 / +0.0087** |
| `lowlight_isp` (GAT, 배포) | 0.1775 | 0.3710 | 기준 |
| `lowlight_isp_subsample` | 0.1735 | 0.3429 | −0.0040 / −0.0281 |
| `lowlight_isp_linear` | 0.1294 | 0.2651 | −0.0481 / −0.1059 |

읽는 법:

- **linear → GAT** 구간이 압도적으로 크다(`+0.0481 / +0.1059`). 톤 커브
  단계는 반드시 있어야 한다.
- **GAT → gamma** 구간이 그다음이고, 방향이 GAT에 불리하다. 두 지표가
  같은 방향이고 크기도 잡음대를 넘는다.
- 그림자 리프트가 강한 커브일수록 좋다는 단조 경향으로 읽힌다
  (linear < GAT < gamma, 입력 16에서 각각 1 / 4 / 15로 리프트).
  검출기는 어두운 영역의 대비를 원하고, GAT가 억제하려던 read-noise floor
  증폭은 순비용이 아니었던 것으로 보인다. 이 단조 순서는 SSDLite에서도
  그대로 재현된다(§6).

## 5. 판정과 실행된 결정

**확정:** stage (5)를 없애는 선택지는 배제된다. GAT는 이 조건에서 gamma
2.0보다 열세이며, 이는 검출기 계열을 바꿔도 유지된다(§6).

**실행:** 교차검증까지 확인한 뒤 **GAT를 철회하고 배포 커브를 gamma 2.0으로
교체했다**(2026-08-06). `default_ISP`와 같은 256-entry LUT를 `>>4`로
인덱싱한다. 교체 후 `lowlight_isp` arm 재측정값이 **0.1876 / 0.3797**로
교체 전 `lowlight_isp_gamma`와 정확히 일치해 엔드투엔드로 확인됐다
(`results/map_gamma_swap_nod100_2026-08-06.csv`).

GAT는 Python 골든의 `lowlight_isp_gat` ablation arm으로만 남으며, HLS RM에는
런타임 스위치를 두지 않았다.

남은 저조도 고유 요소는 **binning + 2.0× 노출 게인 + H/2×W/2 출력**이다.
배포 커브 기준으로 binning 기여를 재측정하니 same-color가 subsample을
**+0.0185 / +0.0360**으로 앞선다 — GAT 기준(+0.0040 / +0.0281)보다 오히려
뚜렷해졌다.

### 5.1 교체가 자원에 미친 영향

4096-entry GAT ROM이 256-entry LUT로 바뀌면서 자원이 다시 크게 줄었다:

| 구성 | BRAM | DSP | FF | LUT | period |
|---|---:|---:|---:|---:|---:|
| GAT + denoise (최초) | 11 | 20 | 7,555 | 12,826 | 3.650 ns |
| GAT, denoise 제거 | 5 | 14 | 4,417 | 6,939 | 3.650 ns |
| **gamma 2.0 (현재 배포)** | **1** | **10** | **2,089** | **4,150** | **3.650 ns** |

v1 저조도 arm(LUT 4,204) 대비 **0.99배**로 사실상 동등하고 BRAM은 8 → 1이며,
v2 일반 arm(12,659) 대비 **67% 작다**. csynth 기준이며 post-route는 미실시.

## 6. 교차검증 — SSDLite MobileNetV3 (2026-08-06)

같은 렌더 결과를 **구조가 다른 검출기 계열**로 재채점했다. 렌더는 재실행하지
않았으므로 검출기 외의 모든 조건이 동일하다.
도구: `tools/eval_map_newrm_ssd.py` (torchvision
`ssdlite320_mobilenet_v3_large`, COCO-pretrained, CPU).

| stage ⑤ | YOLOv8n @[.5:.95] / @50 | SSDLite @[.5:.95] / @50 |
|---|---:|---:|
| **gamma 2.0** | **0.1876 / 0.3797** | **0.1250 / 0.2427** |
| GAT (배포) | 0.1775 / 0.3710 | 0.1145 / 0.2314 |
| GAT + 구 subsample | 0.1735 / 0.3429 | 0.1093 / 0.2174 |
| linear (커브 없음) | 0.1294 / 0.2651 | 0.0844 / 0.1699 |

| | gamma − GAT |
|---|---:|
| YOLOv8n | +0.0101 / +0.0087 |
| SSDLite | +0.0105 / +0.0113 |

**순위가 4개 비교(2 검출기 × 2 지표) 전부에서 동일하다:**
`gamma > GAT > subsample > linear`. 주 지표 효과 크기도 `+0.0101` 대
`+0.0105`로 사실상 같다.

> **절대값은 비교하지 말 것.** Ultralytics 경로와 pycocotools 경로는 평가
> 프로토콜이 다르고 SSDLite는 더 약한 검출기다. 교차검증이 확인하는 것은
> **arm 간 순위의 검출기 독립성**이지 절대 성능이 아니다.

이로써 "gamma 2.0이 GAT보다 낫다"는 판정은 단일 검출기 우연으로 설명되지
않는다. GAT 반증은 확정으로 본다.

## 7. 한계

- 100장 단일 야간 split, 단일 실행.
- GAT 파라미터 `a, b`는 이 split 자체로 캘리브레이션됐다. 즉 GAT는
  홈그라운드에서 졌다 — 파라미터 오차로 설명하기 어렵다는 뜻이다.
- 주광(PASCAL) 조건에서는 미측정. 저조도 arm이 주광에서 선택되지 않으므로
  배포 판단에는 부차적이나, 논문의 일반화 주장에는 필요하다.
- 두 검출기 모두 COCO-pretrained이며 이 데이터로 파인튜닝하지 않았다.

## 8. 함께 수행한 denoise 영구 제거와 자원 재측정

denoise 단계와 그것을 먹이던 3행 슬라이딩 버퍼를 코드에서 제거했다
(스위치 OFF가 아니라 삭제). `rm_lowlight_isp_top` csynth
(Vitis HLS 2024.1, xczu7ev-ffvc1156-2-e, 5.0 ns):

| | denoise ON | denoise OFF (스위치) | **denoise 제거(현재)** |
|---|---:|---:|---:|
| BRAM_18K | 11 | 11 | **5** |
| DSP | 20 | 20 | **14** |
| FF | 7,555 | 5,483 | **4,417** |
| LUT | 12,826 | 8,115 | **6,939** |
| Est. period | 3.650 ns | 3.650 ns | **3.650 ns** |

**예측했던 BRAM 회수가 실제로 일어났다**(11 → 5, −55%). 이전 문서가
"BRAM이 11로 불변인 이유는 행 버퍼가 아직 할당된 채이기 때문"이라고
적었던 미실행 항목이 이번에 닫혔다. DSP 20 → 14 감소는 예상 밖이었는데,
σ-clip의 `total / count`가 **가변 제수 나눗셈**이었기 때문으로 보인다.

자원 서사(이 시점 기준 — 이후 gamma 교체로 §5.1의 값까지 더 내려갔다):

- v1 저조도(`rm_low_light_tone_top`, LUT 4,204) 대비 **3.05배 → 1.65배**
- v2 일반(`rm_default_isp_top`, LUT 12,659) 대비 **45% 작다**

검증: `make lowlight-isp-verify` PASS(golden 147 pixels + C-sim smoke),
`make verify-new-arms` PASS(40 trials / 15,966 samples).

## 9. 참고

- 선행: `results/denoise-k-sweep-2026-08-06.md`(denoise 제거 근거),
  `results/v2-arm-ablation-2026-08-06.md`
- 설계 문서: `src/lowlight_isp.md` §2.1(GAT), §5(자원)
- 원시 수치: `results/map_gat_ablation_nod100_2026-08-06.csv`(YOLOv8n),
  `results/map_gat_ablation_nod100_ssdlite_2026-08-06.csv`(SSDLite)
