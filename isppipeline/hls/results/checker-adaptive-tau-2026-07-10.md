<!--
=============================================================================
File   : isppipeline/hls/results/checker-adaptive-tau-2026-07-10.md
Date   : 2026-07-10 KST
Branch : exp/principled-checker-rm-2026-07-05
Function: 강화안 #1(센서 메타데이터 적응 dark 임계 τ(s,g,BLC))의 파라메트릭
          모델 유도 + 자가검증 스캐폴드. 고정 dark_pixel_threshold(합성
          pseudo-RAW 보정 상수)를 read-noise floor 기반 적응 τ로 대체하는
          이론·코드·셀프테스트를 확정한다. 실데이터(LOD/AODRaw ARW EXIF +
          GPU mAP) 스트라텀 검증은 PENDING으로 명시.
Sources: checker-sota-strategy-2026-07-09.md #1 (모델 정의: τ(g)=BLC+k·σ_read,DN)
         checker-principles-2026-07-05.md 원리 3 (노이즈물리: 임계는 read-noise floor)
         tools/checker_adaptive_tau.py (본 캠페인 산출물, --selftest 직접 실행)
         tools/aodraw_adapter.py (extract_exif / to_shift8_bin 재사용 패턴)
         src/dfxisp_accel.cpp (checker_select_mode:145, dark_pixel_threshold AXI-lite:403)
         EMVA 1288 (σ_read, K 캘리브레이션 절차; 보드 단계)
Repro  : cd isppipeline/hls && python3 tools/checker_adaptive_tau.py --selftest
         (예시 τ:  python3 tools/checker_adaptive_tau.py --tau --iso 6400 \
                    --exposure 0.033 --black 512 --white 16383)
=============================================================================
-->
# 센서 메타데이터 적응 dark 임계 τ(s,g,BLC) — 유도 + 스캐폴드 (2026-07-10)

**작성:** 2026-07-10 KST · **브랜치:** `exp/principled-checker-rm-2026-07-05`
· **산출물:** `tools/checker_adaptive_tau.py`, 본 문서

> 강화안 #1(`checker-sota-strategy-2026-07-09.md`)의 **1단계(수식·스캐폴드,
> AODRaw 불필요)** 만 수행한다. 2–3단계(프레임별 τ 산출 → ISO/노출 스트라텀별
> 고정-τ vs 적응-τ recall/FT 스윕)는 실 ARW EXIF + GPU mAP가 필요하므로 마지막
> 절에 **PENDING**으로 못박는다. 본 문서의 셀프테스트 수치는 전부 위 Repro
> 커맨드의 **실제 출력**이며, 지어낸 값이 아니다.

---

## 1. 문제 — 고정 임계의 도메인 붕괴

현행 체커(`src/dfxisp_accel.cpp:145` `checker_select_mode`)는 RAW를 1-pass로
읽어 `raw[i] < dark_pixel_threshold`인 dark 픽셀을 세고, 그 비율이
`DARK_RATIO_PCT`(80%)를 넘으면 LOW_LIGHT RM을 선택한다. `dark_pixel_threshold`는
이미 AXI-lite 런타임 레지스터(`dfxisp_accel.cpp:403`)다.

이 상수는 **합성 pseudo-RAW** 위에서 보정되었다. 실센서에서는 노출시간 s,
아날로그 게인 g, 블랙레벨 BLC가 프레임마다 달라져 임계의 **절대값 의미가
붕괴**한다(원리 3, 노이즈물리). 실HW 이식 시 최대 실패요인이다.

---

## 2. 유도 — read-noise floor 위의 적응 임계

### 2.1 dark 픽셀의 원리적 정의

"dark 픽셀"을 **노이즈 플로어에서 유의하게 벗어나지 못한 픽셀**로 정의한다.
아날로그 게인 g에서 read noise를 RAW DN 축으로 투영하면

```
σ_read,DN(g) = σ_read,e⁻ · g / K
```

- `σ_read,e⁻` = 전자 도메인 read noise(RMS), EMVA 1288 다크프레임 시퀀스로 측정.
- `K` = 변환게인(e⁻/DN), 광자전달곡선(EMVA 1288)으로 측정.
- 게인 g는 전자 도메인 read noise를 더 많은 DN으로 증폭하므로 σ_read,DN ∝ g.

임계는 이 플로어에서 k-시그마(Rose criterion, k≈5) 위에 둔다:

```
τ(g) = BLC(g) + k · σ_read,DN(g) = BLC(g) + k · σ_read,e⁻ · g / K
```

τ 미만 픽셀은 흑레벨 위로 k 노이즈시그마도 못 올라온, 통계적으로 "빛 없음"과
구별 불가능한 픽셀이다. k는 검출성 요구를 반영하는 스윕 파라미터다.
`tau_from_sensor(black_level, gain, sigma_read_e, K, k=5.0)`가 이 τ를 native
RAW DN(=rawpy `black_level_per_channel`/`white_level`와 동일 단위)으로 반환한다.

### 2.2 노출 정규화 — scene-referred 광량 축

LOW_LIGHT 판정은 **장면의 밝기**에 대한 것이므로 scene-referred 축에서 내려야
한다. 흑레벨 위 신호는 노출곱 `r = (s·g)/(s₀·g₀)` 에 선형 비례한다. 따라서
동일 장면이 (s·g)만 바뀌면 판정이 **불변**이어야 한다. 두 등가 실현:

```
(형태 1, 임계 스케일)   τ_meas = BLC + r · τ_signal
(형태 2, 히스토그램 정규화)  x_ref = BLC + (x − BLC)/r,  고정 τ_ref와 비교
```

`τ_signal`은 기준게인에서의 흑레벨 위 신호 임계(= k·σ_read,DN(g₀)). 등가성:
`x < τ_meas ⇔ (x−BLC)/r < τ_signal`. 형태 2는 HW에서 r이 2의 거듭제곱이면
히스토그램 bin에 대한 **정수 뺄셈+시프트**로 실현되어 1-pass 정수 스트리밍
계약을 지킨다. 코드: `exposure_scaled_tau`, `normalize_to_reference`.

### 2.3 프레임 결합 규칙

프레임 운영 임계는 두 조건을 **모두** 만족해야 하므로 더 엄격한(높은) 쪽을 택한다:

```
τ_frame = max( BLC + k·σ_read,DN(g),          # 절대 read-noise floor
               BLC + r · k·σ_read,DN(g₀) )     # 노출정규화 scene 임계
```

`tau_for_frame(exif, black, white, SensorParams, k)`가 EXIF(ISO→g, ExposureTime→s)
+ per-file black/white + 센서 파라미터에서 이 τ_frame과 레지스터 값을 조립한다.
ISO/노출이 없으면 기준설정으로 폴백(r=1).

### 2.4 레지스터 도메인 매핑

체커가 소비하는 스케일은 데이터셋 어댑터의 "shift8" pseudo-RAW다
(`aodraw_adapter.to_shift8_bin`). 드라이버가 `dark_pixel_threshold`에 써넣을 값:

```
lin = (τ_dn − black)/(white − black);  u8 = round(lin·255);  reg = u8 << 8   (uint16 클램프)
```

`to_register_domain()`이 이 매핑을 담당한다.

---

## 3. HW 실현 — Path A(권장) / Path B

**Path A (권장, RTL 변경 0).** `dark_pixel_threshold`가 이미 AXI-lite 런타임
레지스터이므로, 호스트 드라이버가 **센서 설정 변경 시점마다** τ_frame을 계산해
레지스터에 써넣는다. RTL/HLS 재합성 불필요, 논리비용 0. §2.4 매핑을 드라이버가
1회 계산. EXIF/센서 캘리브가 SW에 있고 프레임 레이트 대비 설정 변경이 드물어
가장 자연스럽다. **본 캠페인 권장안.**

**Path B (완전 자율일 때만).** (게인 인덱스 × 노출 버킷) 소형 **2D LUT**를 체커
앞단에 합성 — 드라이버 개입 없이 HW 단독으로 τ를 인출. LUT는 §2 모델을
오프라인으로 양자화해 채운다(예: 게인 8단 × 노출 8버킷 = 64 entry, 1 BRAM
미만). 노출 정규화의 정수-시프트 형태(형태 2)와 결합하면 곱셈 없이 실현된다.
드라이버가 없거나 센서 설정을 HW가 직접 관측하는 시나리오에서만 정당화된다.

> **권장 결론:** Path A. `dark_pixel_threshold`가 이미 레지스터라 HW 변경 비용이
> 0이고, 스트라텀 검증이 τ 모델을 기각하더라도 회수 비용이 없다. Path B는
> AODRaw 검증이 τ 이득을 확인하고 **또한** 자율 동작이 요구될 때만 착수.

---

## 4. 셀프테스트 결과 (실제 출력)

`python3 tools/checker_adaptive_tau.py --selftest` (exit 0):

```
[ok] tau monotone in gain: g=[1.0, 2.0, 4.0, 8.0, 16.0] -> tau=[572.0, 632.0, 752.0, 992.0, 1472.0]
[ok] exposure-normalized dark count invariant under 4x (s*g): ref=6 scaled_tau=6 hist_norm=6 (naive-fixed would give 4)
[ok] k sweep: k=[0.0, 3.0, 5.0, 7.0] -> tau=[512.0, 656.0, 752.0, 848.0] (k=0 -> BLC)
[ok] extract_exif graceful null fallback (no tool)
[ok] tau_for_frame ISO6400: tau_dn=8192.00 r=16.000 register(shift8)=31488

selftest: ALL PASS
```

검증 항목:
- **(a) 게인 단조성** — τ가 게인에 대해 순증(σ_read,DN ∝ g), 항상 τ > BLC.
- **(b) 노출 불변성** — 동일 합성 장면을 4×(s·g)로 리스케일해도 노출정규화
  dark 카운트 불변(임계-스케일/히스토그램-정규화 두 형태 모두 6). 대조로
  **naive 고정 임계는 6→4로 붕괴** — 정규화의 필요성을 정량 확인.
- **(c) k 스윕** — τ가 k에 순증, k=0에서 τ=BLC(순수 플로어)로 수렴.
- **(d) EXIF 폴백** — exiftool 부재 시 예외 없이 `{iso,exposure_s,f_number}=null`.
- (e) 종단 `tau_for_frame`(ISO6400) — 레지스터 값이 uint16 범위, τ_dn>BLC.

**커버되지 않는 것:** 실 ARW 디코드/EXIF 파싱 정확도, 그리고 τ 이득의 실검출
성능(다음 절). 순수 로직은 전부 검증됨.

---

## 5. 실데이터 검증 — PENDING (LOD ARW EXIF + GPU mAP 필요)

아래 층화 실험은 **데이터셋 다운로드 + GPU가 준비되면** 실행한다. 현재는 미착수.

1. **데이터 어댑팅.** LOD/AODRaw Sony .ARW를 `tools/aodraw_adapter.py`로 인제스트
   → `frames_meta.csv`(stem, iso, exposure_s, black_level, white_level, ...).
   EXIF는 exiftool best-effort(§Repro의 폴백 계약).
2. **스트라텀 분할.** 프레임을 EXIF ISO로 3~5개 스트라텀으로 나눈다(예:
   ISO≤400 / 800–1600 / 3200–6400 / ≥12800).
3. **프레임별 τ.** 각 프레임에 `tau_for_frame(...)["register"]`로 적응 τ 산출
   (§본 파일 하단 HOOK 주석: 레지스터에 써넣고 체커 실행 — Path A).
4. **비교.** 스트라텀별로 **고정-τ(현 dark16=raw12 256)** vs **적응-τ** 의
   recall / FT / J 를 비교. 특히 **고정 τ의 스트라텀 간 성능 분산(열화) 자체가
   ablation 근거**다(전략 문서 평가 프로토콜).
5. **수용/기각.** 적응 τ가 (i) 전 스트라텀에서 J ≥ 고정 τ, (ii) 스트라텀 간
   recall 분산을 유의하게 축소하면 채택. AODRaw의 노출 다양성이 낮아 차이가
   5-fold FT fold-분산(±0.03~0.04) 이내면 "이 데이터셋 범위에서는 고정 τ 충분"
   으로 기록하고 **Path A만 문서화**(HW는 이미 레지스터라 기각 비용 0).
6. **센서 캘리브.** `σ_read,e⁻`, `K`의 EMVA 1288 실측은 **보드 단계로 연기**.
   그 전까지 `SensorParams` 기본값(placeholder, Sony-class CMOS)으로 근사하며,
   EXIF ISO→게인 매핑의 iso_base/기준(s₀,g₀)은 데이터셋 중앙값으로 캠페인별 고정.

> 요약: 이론·코드·자가검증은 확정(ALL PASS). 남은 것은 실 ARW로 τ 이득을
> 증명하는 스트라텀 검증뿐이며, HW 경로는 Path A(RTL 변경 0)로 이미 열려 있다.
