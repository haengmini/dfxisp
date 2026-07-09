<!--
=============================================================================
File   : isppipeline/hls/results/lowlight-module-techniques-2026-07-10.md
Date   : 2026-07-10 KST
Function: 제안하는 low-light ISP 모듈(RM_LOW_LIGHT_TONE)이 쓰는 기술/기법을
          나열하고, 각각 (a) 어떤 이득을 기대하는가 (b) 실제로 어떤 이득이
          측정됐는가를 근거 수치와 함께 정직하게 서술. RESEARCH.md §1.3
          주장1(알고리즘)의 상세 근거 문서.
Sources: src/dfxisp_accel.cpp (배포 구현), gen_golden_vectors.py (golden),
         blc-fix-resynthesis-2026-07-03.md, lowlight-rm-map-rootcause-2026-07-02.md,
         principled-v3-refinement-2026-07-05.md (binning 귀속),
         realraw-sonynod-benchmark-2026-07-06.md (실센서 arm 역전),
         isp-pipeline-recalibration-2026-07-08.md (canonical 재보정)
=============================================================================
-->
# 저조도 ISP 모듈 — 제안 기술과 기대·실측 이득 (2026-07-10)

> 대상: `RM_LOW_LIGHT_TONE` (저조도 tone RM). 공유 baseline ISP core
> (BLC/AWB/CCM) 앞뒤를 감싸는 mode-specific 모듈이며, 체커가 dark 판정을
> 내렸을 때만 활성화된다(RESEARCH.md §2). 본 문서는 이 모듈이 쓰는 기법을
> 하나씩 나열하고 **기대이득 vs 실측이득**을 대조한다.
>
> **비교 범위:** 모든 mAP는 `normal`/`lowlight`/`adaptive` arm 안에서만
> 비교한다(`none` 제외, RESEARCH.md §1.2). **정본 재평가는 real-RAW 쌍
> (PASCAL RAW/LOD RAW, §10)에서 수행 예정** — 아래 실측치는 pseudo-RAW
> (COCO/ExDark) + 실센서 SonyNOD 기준의 현재까지 근거다.

## 1. 제안 기술 목록 (모듈 구성)

`RM_LOW_LIGHT_TONE`의 프레임 처리 순서:

```text
RAW(Bayer)
  ─▶ ① 2x2 RAW binning-demosaic        (front, 광량 적분 + 데모자이크 융합)
  ─▶    [공유 baseline core: BLC(완화) → AWB → CCM]
  ─▶ ② low-light exposure gain 2.0x    (back)
  ─▶ ③ gamma-2.0 톤 (공유 sqrt LUT)     (back)
  ─▶ RGB (H/2 × W/2, Policy A)
       └ ④ 완화된 black-level(BLC_OFFSET12_LOWLIGHT=128, normal의 절반)은
            공유 core 안에서 저조도 모드에만 적용되는 파라미터
```

## 2. 기법별 기대이득 vs 실측이득

| # | 기법 | 기대이득 (왜 넣었나) | 실측이득 (무엇이 나왔나) | 판정 |
|---|---|---|---|---|
| ① | **2x2 RAW binning-demosaic** | 인접 4픽셀 광량을 적분해 저조도 SNR↑(shot noise 평균화). 저조도에서 해상도를 일부 포기하고 신뢰도를 얻는 고전적 트레이드 | **pseudo-RAW: 순손해/wash.** binning 제거(full-res)가 COCO에서 +0.016(AP_small +296%)로 견고 우위, ExDark(저조도 타깃)에선 검출기 의존(yolov8n full 선호 / yolov8s·SSD binning 선호, CI 겹침). **실센서 SonyNOD: 역전 — binning 포함 `lowlight`(0.036) > `normal`(0.022).** 원리 정합: pseudo-RAW엔 회수할 실제 노이즈가 없어 "해상도 vs SNR"이 균형점, 실센서 노이즈에서 비로소 binning이 값을 한다 | **조건부** — real-RAW(LOD)에서 재검증 필요. binning의 정당성은 실센서 노이즈에 걸려 있음 |
| ② | **low-light exposure gain 2.0x** | 저조도 신호를 검출기 입력 다이내믹레인지로 끌어올림(정상 1.25x 대비 강한 증폭) | tone 계열 단독 이득은 미미(<0.002급). gain은 밝기 정규화 역할이지 그 자체가 mAP를 크게 올리는 축은 아님 | **보조** — 필요하나 주효인은 아님 |
| ③ | **gamma-2.0 톤 (공유 sqrt LUT)** | 저조도 톤 재분포로 어두운 영역 대비 확보 | **1차 "VST 톤이 이득" 서사는 아티팩트였다** — 배포본이 이미 sqrt 톤이라 VST와 사실상 동일(약한 gamma2.5 baseline과 비교해 이득처럼 보였던 것). 순 톤 효과는 noise 대역 | **기각(과설계)** — 별도 톤 LUT 불필요, 기존 공유 gamma 유지 |
| ④ | **완화된 black-level (128, normal 256의 절반)** | 저조도에서 과한 BLC가 어두운 신호를 잘라버리는 것을 방지 | **가장 큰 단일 이득.** 저조도 mAP 손실의 **70%가 BLC**임을 5단계 ablation으로 규명(해상도 손실은 −1.4%). 완화 반영 시 ExDark `lowlight` 0.0586→0.1043(+78%), **최초로 `normal`(0.0826) 상회**. HW 자원 완전 불변(상수 하나) | **채택(주효인)** — 저조도 모듈이 `normal`을 이기게 만든 결정타 |

(위 pseudo-RAW mAP 정밀 수치는 canonical 재보정(R4, `isp-pipeline-
recalibration-2026-07-08.md`) 및 demosaic 수정(R5, GPU 대기)으로 갱신
예정이나, **기법별 귀속(무엇이 이득의 원인인가)의 정성 결론은 불변**이다.)

## 3. 종합 — 저조도 모듈의 "이득 지도"

- **주효인은 ④ 완화 BLC**다 — 저조도 모듈이 일반 모듈을 이기는 핵심은
  "어두운 신호를 덜 잘라내는 것"이며, 이건 HW 비용 0(파라미터)으로 얻는다.
- **①binning은 조건부**다 — pseudo-RAW에선 해상도 손실이 더 커 wash지만,
  **실센서 노이즈에선 순이득으로 돌아선다**(SonyNOD arm 역전). 따라서
  binning은 "저조도 모듈이 real-RAW에서 필요한 이유"의 후보이며, LOD RAW
  (§10)에서 정본 검증한다.
- **②gain은 보조, ③별도 톤은 기각(과설계)**.
- **정직한 한계:** 지금까지의 정밀 mAP는 (i) pseudo-RAW proxy 또는 단일
  센서(SonyNOD, 전량 야간)에 기반하고, (ii) canonical/​demosaic 수정으로
  아직 한 번 더 움직인다. **목표 1의 최종 근거는 PASCAL RAW(normal 우위)
  ↔ LOD RAW(lowlight 우위)의 교차 우위**이며 그 실험은 미완이다.

## 4. 다음 (정본 재평가)

`results/` 관례대로, PASCAL RAW/LOD RAW 어댑터로 세 arm(normal/lowlight/
adaptive)을 재실행해 위 표의 실측이득 열을 real-RAW 정본 수치로 대체한다.
그때 ①binning의 조건부 판정이 "LOD에서 순이득"으로 확정되는지가 저조도
모듈 서사의 관문이다.

**어댑터 참고:** 저조도 LOD 데이터셋은 Sony `.ARW`(sonynod와 동일 포맷)라
`tools/aodraw_adapter.py`의 rawpy 디코드 경로가 그대로 쓰인다 — 파일별
흑레벨/화이트레벨/베이어 위상을 rawpy에서 읽고 shift8 규약으로 정규화하는
설계이므로 센서 상수 하드코딩이 필요 없다(어댑터 설계·검증은
`aodraw-adapter-2026-07-09.md`).
