# default_ISP — Vitis Vision 정렬 표준 ISP arm (2026-08-06)

`src/default_isp.cpp` / `include/default_isp.hpp` 설계 노트. 소스 주석에서
분리한 배경·근거 문서.

## 0. 왜 만들었나

기존 `RM_NORMAL_TONE`(`dfxisp_accel.cpp`)은 AMD Vitis Vision L3
`isppipeline` 예제와 **스테이지 순서와 도메인이 다르다**(2026-08-06 실소스
대조). 논문에서 normal arm을 "표준 ISP 기준선"으로 서술하려면 상수 차이가
아니라 **구조 차이**를 메워야 하므로, Vitis Vision 순서를 그대로 따르는
별도 arm을 만들었다. `STRATEGY.md`가 2026-07-03에 제안하고 ROADMAP #7이
미착수로 기록해온 **Vitis-first 리팩터의 첫 산출물**이다.

**추가형(additive)이다** — `RM_NORMAL_TONE`, 그 golden 계약, 배포된
BLC/checker 결정은 손대지 않았다. default_ISP를 normal 모드 RM으로 채택할지
여부는 별개 결정(`STRATEGY.md` 열린 질문 #4).

## 1. 파이프라인 대조 (Vitis Vision vs 두 arm)

| # | Vitis Vision `isppipeline` | **default_ISP (신규)** | RM_NORMAL_TONE (기존) |
|---|---|---|---|
| 1 | blackLevelCorrection — **Bayer** | ✅ 동일 (감산 + 레인지 복원) | demosaic 먼저 |
| 2 | gaincontrol — **Bayer**, R/B 위치별 | ✅ 동일 (Q8 286/307) | — |
| 3 | demosaicing | ✅ RGGB bilinear | RGGB bilinear |
| 4 | AWB — **RGB, 프레임 적응** | ✅ gray-world 적응(bypass 가능) | 고정 상수 WB (RGB) |
| 5 | colorcorrectionmatrix | ✅ **실제 3×3 Q8 행렬** | identity placeholder |
| 6 | quantization & dithering | △ `>>4`만 (디더링 생략) | `>>4` |
| 7 | gammacorrection (LUT) | ✅ 동일 LUT(γ2.0) | 동일 LUT |
| 8 | rgb2yuyv (출력 CSC) | ✗ 의도적 생략 → RGB888 | RGB888 |
| — | (게인) | 없음 — 노출 게인은 tone RM 고유 | gain 1.25× (tone) |

## 2. 의도적 편차 3건 (Vitis와 다르게 한 것, 근거 포함)

1. **출력 CSC(rgb2yuyv) 생략** — 하류가 DPU/검출기라 RGB888을 그대로
   받는다(SPEC.md §5.1의 AXI 정렬용 32-bit 패킹 유지). YUYV로 바꾸면 평가
   경로 전체를 바꿔야 하고 이득이 없다.
2. **디더링 생략** — Vitis의 quantization&dithering은 비트심도 축소 시
   밴딩을 줄이는 옵션 단계다. 검출 mAP 목적에는 영향이 확인된 바 없어
   `>>4` 절단만 남겼다(향후 필요 시 추가 가능).
3. **AWB 통계원** — Vitis는 **직전 프레임 히스토그램**(1프레임 지연,
   double-buffer)으로 게인을 만든다. default_ISP는 **현재 프레임의 Bayer
   사이트 평균(gray-world)** 을 쓴다: 프레임 버퍼가 필요 없고 지연이 없는
   대신 raw를 한 번 더 읽는다(§4). 통계량 종류도 히스토그램 정규화 대신
   gray-world라 **더 단순하다** — "Vitis와 동일 알고리즘"이 아니라 "동일
   위치·동일 역할의 적응형 AWB 스테이지"로 이해할 것.

## 3. 상수

| 스테이지 | 상수 | 값 | 근거 |
|---|---|---|---|
| (1) BLC | `BLC_LEVEL12` | 32 (= 8-bit 2 << 4) | 2026-07-20 실 RAW 재보정 배포값 |
| (1) BLC | `BLC_MUL_Q8` | 258 | `round(256 × 4095/(4095−32))` — 감산으로 잃은 레인지 복원(Vitis 방식) |
| (2) gain | `GAIN_R_Q8` / `GAIN_B_Q8` | 286 / 307 | 기존 arm의 WB 값과 동일 — 두 arm은 게인 **크기**가 아니라 **적용 위치**가 다르다 |
| (4) AWB | 클램프 | Q8 [64, 1024] | 0.25×~4× |
| (5) CCM | 3×3 Q8 | 행 합 = 256 | 중성 회색 보존. **센서 캘리브레이션 전까지는 placeholder** — 색정확도 주장 금지 |
| (7) gamma | LUT | γ2.0 `isqrt(255v)` | `dfxisp_accel.cpp`와 byte-identical(arm 간 tone 축 비교 가능하게) |

## 4. 구현상 알아둘 점

- **BLC/gain은 버퍼 없이 on-the-fly**: demosaic 윈도우가 픽셀을 읽을 때마다
  보정을 적용한다. 보정이 pointwise라 결과는 동일하고 프레임 버퍼가
  불필요하지만, 같은 픽셀이 최대 9회 재보정된다(연산 중복 ↔ 저장 없음
  트레이드오프).
- **AWB는 raw를 한 번 더 읽는다**(통계 패스). checker의 전수 스캔과 합치면
  프레임당 gmem0 읽기 횟수가 늘어난다 — 실장 시 대역폭 예산에서 고려할 것.
- **누산기 폭**: 1920×1080×4095 ≈ 8.5e9 → 64-bit 누산기 사용.
- CCM 음수 계수 때문에 누산값이 음수가 될 수 있어 **shift 전에 0으로
  floor** 한다 — C++의 음수 우측 시프트 구현정의 동작을 피하고 Python
  golden과 bit-exact를 보장하기 위함.

## 5. 검증

| 게이트 | 상태 |
|---|---|
| Python golden ↔ C++ bit-exact (`make default-isp-verify`) | ✅ 528 px, 10 케이스(평탄/그라디언트/색캐스트/포화/홀수·1×1) |
| BLC가 Bayer 도메인 선행 (pedestal 이하 → 순흑) | ✅ |
| AWB 적응 동작 (색캐스트에서 채널 불균형 감소) | ✅ |
| CCM 중성 보존 (행 합 256 → 평탄 입력 채널 편차 ≤ 8) | ✅ |
| 포화 입력 RGB8 오버플로 없음 | ✅ |
| DFX 계약 (`rm_default_isp_top` 6-인자, `default_isp(AWB_ON)`과 동일 출력) | ✅ |

## 6. 실측 자원/타이밍 (Vitis HLS 2024.1, xczu7ev, 5.0 ns)

`reports/csynth/rm_default_isp_top_csynth.rpt` — flat-tempdir 우회로 합성.

| top | BRAM_18K | DSP | FF | LUT | Est. period |
|---|---:|---:|---:|---:|---:|
| **`rm_default_isp_top`** (default_ISP) | 4 | **28** | **8,803** | **12,659** | 3.650 ns |
| `rm_normal_tone_top` (RM_NORMAL_TONE) | 4 | 12 | 3,797 | 5,202 | 3.650 ns |

**해석:** default_ISP는 기존 normal arm 대비 **LUT 2.43배, DSP 2.33배**다.
증가분의 출처는 구조 그 자체다 — (a) AWB 통계 패스(전수 스캔 + 64-bit
누산기 + 나눗셈), (b) 실제 CCM(항등이 아니라 9-곱셈 행렬), (c) BLC 레인지
복원 곱셈. **타이밍은 동일**(3.650 ns = 273.97 MHz)이라 표준 구조를 채택해도
Fmax는 희생되지 않는다.

> **주의:** 위는 csynth 추정치다. SPEC.md §10.3의 arm 비교표는 post-route
> flat 축이므로 **섞어 쓰지 말 것**. default_ISP를 arm 비교에 넣으려면
> 동일 tie-off 래퍼로 post-route를 따로 떠야 한다(미실행).

## 7. 남은 일

1. **mAP 평가 미실시** — default_ISP의 검출 성능은 아직 측정하지 않았다.
   SW proxy(`tools/baseline_isp_pipeline.py`)는 여전히 RM_NORMAL_TONE을
   미러링하므로, default_ISP를 평가하려면 대응하는 Python proxy(또는
   `gen_default_isp_golden.py` 재사용)를 mAP 하네스에 연결해야 한다.
2. **post-route 실측** — §6 주의 참조.
3. **채택 여부 결정** — default_ISP를 `RM_NORMAL`로 승격할지는
   `STRATEGY.md` 열린 질문 #4(RP 경계 서사)와 함께 결정한다. 승격 시
   golden 재생성·checker 상수 재검토가 따라온다.
4. **CCM 캘리브레이션** — 현재 행렬은 placeholder(§3).
