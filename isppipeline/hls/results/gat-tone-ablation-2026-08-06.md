<!--
File   : isppipeline/hls/results/gat-tone-ablation-2026-08-06.md
Added  : 2026-08-06
Function: lowlight_ISP stage (5)의 톤 커브를 단독으로 분리해 GAT/VST의 기여를
          측정한다. denoise 영구 제거 후의 자원 재측정도 함께 기록한다.
Sources: results/map_gat_ablation_nod100_2026-08-06.csv
         (csynth) 본문 §3, flat-tempdir 워크어라운드로 재측정
-->

# GAT 톤 커브 단독 ablation — NOD 100장 (2026-08-06)

## 0. 결론부터

1. **톤 커브 자체는 결정적이다.** 커브를 빼고 단순 절단(12→8)만 하면
   `−0.0481 / −0.1059`로 무너진다. 비선형 톤 매핑이 필요하다는 설계
   전제는 강하게 지지된다.
2. **그러나 GAT는 그 자리에서 최선이 아니다.** GAT가 대체하려던 평범한
   gamma 2.0이 **두 지표 모두에서 GAT를 이긴다**(`+0.0101 / +0.0087`).
   주 지표 차이는 이 프로젝트의 ~0.005 잡음대의 2배이고, 두 지표의 부호가
   **일치**한다 — denoise 스윕에서 부호가 엇갈렸던 것과 대조적이다.
3. 따라서 `src/lowlight_isp.md` §2.1이 "이 설계의 중심"이라고 적은 GAT는
   **측정으로 지지되지 않는다.** 본 문서는 측정 결과만 확정하고, 배포 커브
   교체는 별도 결정으로 남긴다(§5).
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
| `lowlight_isp` | GAT/Anscombe VST (배포 커브) |
| `lowlight_isp_gamma` | gamma 2.0 — `default_ISP` 골든에서 **import**해 표류 불가 |
| `lowlight_isp_linear` | 커브 없음, `z >> 4` 절단 (바닥 대조군) |
| `lowlight_isp_subsample` | GAT, 단 binning만 구 subsample (①의 대조) |

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
- 검출기: YOLOv8n (Ultralytics 8.4.82), CPU
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
  증폭은 YOLOv8n에게 순비용이 아니었던 것으로 보인다.

## 5. 판정과 남긴 결정

**확정:** stage (5)를 없애는 선택지는 배제된다. GAT는 이 조건에서 gamma
2.0보다 열세다.

**남긴 결정(사용자 몫):** 배포 RM의 커브를 gamma 2.0으로 교체할지. 이는
제안 arm의 서사 중심(§2.1)을 바꾸는 결정이라 측정 하나로 자동 반영하지
않았다. `rm_lowlight_isp_top`은 이번 변경에서 GAT를 유지한다.

교체할 경우 남는 저조도 고유 요소는 **binning + 2.0× 노출 게인 +
H/2×W/2 출력**이며, binning은 §4에서 독립적으로 이득이 확인됐다.

## 6. 한계

- 100장 단일 야간 split, 단일 검출기(YOLOv8n), 단일 실행.
- GAT 파라미터 `a, b`는 이 split 자체로 캘리브레이션됐다. 즉 GAT는
  홈그라운드에서 졌다 — 파라미터 오차로 설명하기 어렵다는 뜻이다.
- gamma 2.0의 우위가 다른 검출기(YOLOv8s/SSDLite)나 다른 조도에서도
  유지되는지는 미검증. 배포 교체 전 교차검증 권고.
- 주광(PASCAL) 조건에서는 미측정.

## 7. 함께 수행한 denoise 영구 제거와 자원 재측정

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

자원 서사:

- v1 저조도(`rm_low_light_tone_top`, LUT 4,204) 대비 **3.05배 → 1.65배**
- v2 일반(`rm_default_isp_top`, LUT 12,659) 대비 **45% 작다**

검증: `make lowlight-isp-verify` PASS(golden 147 pixels + C-sim smoke),
`make verify-new-arms` PASS(40 trials / 15,966 samples).

## 8. 참고

- 선행: `results/denoise-k-sweep-2026-08-06.md`(denoise 제거 근거),
  `results/v2-arm-ablation-2026-08-06.md`
- 설계 문서: `src/lowlight_isp.md` §2.1(GAT), §5(자원)
- 원시 수치: `results/map_gat_ablation_nod100_2026-08-06.csv`
