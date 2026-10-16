---
type: stack
title: 2026-10-14 LowlightISP 개선 탐색 (노출·톤·WB·BLC 스윕, 보드 야간 열세 대응)
para: project
stage: organized
created: 2026-10-14
status: reviewed
project: dfxisp
---

# LowlightISP 개선 탐색

관련: [[2026-10-12-isp-sw-hw-gap-separation-experiments]], [[2026-10-12-zcu104-v5-batch-results]]

## 조건
- 야간 LOD 100장(평가) + Sony 야간 419장(홀드아웃, ft_hw train+val). 입력 1368x912 12bit HW 계약.
- 보드 하네스 전/후처리(PIL), 원본 가중치 3종(yolo3_silu/hswish, ssd4) PC FP32. INT8·보드 실측 아님.
- 배포 LowlightISP 재현: 최대 픽셀 차이 1 (반올림 수준).
- 코드/CSV: /opt/data/work/dfxisp_sep_exp/results/ (exp4~6, score_eval/hold.txt)
- 노트북: /home/mini/dfxisp_eval_20261007/sep_20261012/exp4~6

## 결과 (야간 mAP50-95, silu / hswish / ssd4)
| 변형 | 평가100 | 홀드419 |
|---|---|---|
| 배포(BLC32, gain2, gamma2) | .2308 .1878 .1974 | .2561 .2183 .2503 |
| BLC16 | .2773 .2666 .2146 | .2914 .2762 .2626 |
| BLC16 + gray-world WB | .2693 .2589 .2072 | .2924 .2726 .2653 |
| gain 4 (BLC16) | .2723 .2633 .2003 | .2820 .2756 .2439 |
| BLC0 | .2536 .2428 .2105 | .2643 .2561 .2505 |

- 밝기 gain(2~16)·gamma(2~3)·프레임 적응 gain: 배포값(gain2/gamma2)이 최선이거나 동급. 밝게 하는 것은 레버가 아니다 (평균 휘도를 19→45로 올려도 mAP 하락).
- WB: 고정/없음/gray-world/B절반 차이 작음. 홀드에서 gray vs fixed 차이는 CI가 0 포함 → 구분 불가.
- BLC: 12bit 32→16이 유일한 유의 개선. 부트스트랩 95% CI(16−32): 평가 silu +.047[.021,.073], hswish +.079[.048,.106], ssd4 +.017[0,.033]; 홀드 silu +.035[.024,.046], hswish +.058[.045,.070], ssd4 +.012[.006,.018]. 3모델 모두 같은 방향.
- 12~20 구간은 평평한 정점. 24 이상은 급락.

## 해석 (근거 수준)
- 실측: 배포 BLC 32는 이 데이터에 과도하며 16 근처가 낫다. 소스의 08-18 재스윕(LOD_test_hw)도 32에서 큰 하락을 보였고 방향이 일치.
- 미검증: 08-18 재스윕은 0이 최고였으나 여기서는 16이 최고. 데이터 생성 경로(hw1368 bin vs LOD_test_hw)가 달라 원인 미분리.
- 미검증: INT8 변환·보드 실측, BLC 변경 시 DFX 경로·체커 영향(체커는 BLC 독립), 주간 영향(LowlightISP는 야간 경로).

## HW 반영 시 필요 작업(미실시, 승인 필요)
- gen_lowlight_isp_golden.py: BLC_LEVEL12 32→16, BLC_MUL_Q8 258→257 (round(256·4095/4079))
- golden 재생성 + csim/rm-verify + csynth/cosim + RM 비트스트림 재빌드 (07-20 선례: 상수 변경만이라 자원 동일)

## 보드 실측 확인 (2026-10-14, ZCU104 콜드 부팅 후)
- 조건: 야간 LOD 100장, 기존 bs1 partial·BOOT.BIN(2d2a0454…) 그대로. BLC 16은 RAW+16 입력으로 BLC-32 비트스트림 위에서 흉내(실제 RM 재빌드 아님). 스모크 3건(Normal/Lowlight/Lowlight+16) 픽셀 불일치 0 확인 후 배치. 안전 오류 없음.
- 재현성: 기존 입력의 Normal·Lowlight mAP가 v5 배치값과 소수 4자리 일치.

| mAP50-95 (보드 INT8) | Normal | Lowlight(기존) | Lowlight + BLC16 흉내 |
|---|---|---|---|
| YOLOv8n | 0.2696 | 0.1876 | 0.2744 |
| SSDLite | 0.1892 | 0.1625 | 0.1748 |

- 부트스트랩 95% CI (100 리샘플): YOLO 흉내−기존 +0.0868 [+0.046, +0.113]; 흉내−Normal +0.0048 [−0.012, +0.020]. SSD 흉내−기존 +0.0123 [−0.006, +0.023]; 흉내−Normal −0.0144 [−0.032, +0.003].
- 해석: YOLO는 Normal과 구분 불가한 수준까지 회복(유의). SSD는 같은 방향이나 CI가 0 포함, Normal에는 미치지 못함. PC 예측과 방향 일치.
- 한계: 100장·리샘플 100회, 흉내 방식(곱셈 상수 258 vs 257, 픽셀 0.87% 차이≥2), 전력·지연 추가 개선 없음(ISP 지연 동일 410ms).
- 산출물: /opt/data/work/blc16_board_20261014/ (jsonl, 스크립트, board_scores.txt). 보드 /home/root/exp/results/blc16_night_20261014, /home/root/exp/blc16, app/por_blc16_session.py 추가(기존 파일 변경 없음).

## RM 반영 1~2단계 (복사본, 2026-10-14 승인)
- 복사본: 노트북 `~/dfxisp_eval_20261007/blc16_rm/isppipeline` (원본 `~/Desktop/dfxisp/isppipeline` 해시 불변 확인). 패치: `/opt/data/work/blc16_rm_20261014/blc16_patch.diff`.
- 변경 3곳: `hls/src/lowlight_isp.cpp` BLC_LEVEL12 32→16·BLC_MUL_Q8 258→257, `sw/gen_lowlight_isp_golden.py` 동일, `hls/tests/test_lowlight_isp_csim.cpp` 페데스탈 스모크 32→16(BLC에 묶인 기대값).
- 검증(통과): 변경 전 복사본에서 `make lowlight-isp-verify` 통과 및 golden 재생성 동일(재현성). 변경 후 `lowlight-isp-verify` 통과(golden 107행 변경, 147픽셀 일치, 스모크 통과), `verify-new-arms` 40 trials bit-exact, `default-isp-verify` 영향 없음.
- 미실시: csynth/cosim, RM 비트스트림 재빌드, 보드 재측정, 원본 반영. 흉내 방식(+16 입력)과 실제 RM은 곱셈 상수 차이로 픽셀 0.87%가 다름 → 재측정 필요.

## RM 반영 3단계(HLS) 결과와 4단계 위험 (2026-10-14)
- 배포 RM 소스는 `hw/LowlightISP/LowlightISP.cpp`(isppipeline 사본과 별개). 복사본 `blc16_rm/hwll`에서 BLC 16 적용(상수 2곳). 배포 RM 소스 vs isppipeline golden: 변경 전·후 모두 147픽셀 불일치 0, 옛 소스를 새 골든에 대면 107 불일치(검출력 확인).
- csim 통과, csynth 통과(대조군 BLC32와 자원·타이밍 동일: BRAM4/DSP14/FF4919/LUT7041, 추정 2.92ns/목표 4ns, 지연 동일). C/RTL cosim: 기존 TB는 대조군(BLC32)도 널포인터 케이스에서 실패(기존 한계). 전용 1트랜잭션 TB(16x16, m_axi depth=256/64, 복사본 한정)에서 대조군·신규 모두 PASS이며 RTL 출력이 파이썬 golden과 64/64 일치.
- 4단계: 복사본 `blc16_rm/por_fix_blc16`(1.3GB)에 새 IP 반영. 원본 `por_fix` 파일 목록·크기·시간 전체 불변 확인. 그러나 top BD 재생성(ip_revision 1줄 변경)만으로 static(synth_1/impl_1)과 Normal RM이 NEEDS_REFRESH=1이 됨 → 프로젝트 게이트 흐름(run_gate.py)으로 재빌드하면 static이 재합성·재배치되어 배포된 BOOT.BIN/Normal partial과 불일치할 수 있음. 잠긴 static 체크포인트 위에서 RM만 교체하는 수동 DFX 흐름 + pr_verify 필요(미실시, 결정 대기).

## 재빌드 RM 보드 실측 (2026-10-14, 콜드 부팅·ICAP 선택 후)
- 방식: 잠긴 static(`impl_1_routed_bb`) 위에서 Lowlight RM만 교체(UG909 수동 흐름). 대조군(옛 BLC32 RM)을 같은 흐름으로 재빌드하니 배포된 `partial_lowlight_bs1.icap.bin`(cbdfae84…)과 바이트 동일 → 흐름이 배포 빌드를 정확히 재현. 새 RM: pr_verify compatible, WNS +0.081/WHS +0.010, 라우팅 오류 0, 자원 동일 수준. 새 partial(bs1) sha b739f783….
- 보드: BOOT.BIN·Normal·기존 partial 불변(해시 확인), 새 partial은 `/home/root/exp/partials_blc16/`에 별도 설치. 스모크 픽셀 게이트 통과(Normal 0불일치, 새 Lowlight는 PC BLC16 기준 0불일치·옛 BLC32 기준과는 130,342픽셀 상이 → 새 RM 구동 확인). 야간 100장 4작업 오류 없이 완료.
- 재현성: Normal 검출 결과가 이전 세션과 100/100 동일.

| mAP50-95 (보드 INT8, 야간 100장) | Normal | Lowlight 배포(BLC32) | 흉내(BLC16 입력+16) | **재빌드 RM(BLC16)** |
|---|---|---|---|---|
| YOLOv8n | 0.2696 | 0.1876 | 0.2744 | **0.2758** |
| SSDLite | 0.1892 | 0.1625 | 0.1748 | **0.1729** |

- 95% CI(100 리샘플): YOLO RM−배포 +0.088 [+0.047,+0.118]; RM−Normal +0.006 [−0.009,+0.023]; RM−흉내 +0.0015 [−0.003,+0.007]. SSD RM−배포 +0.010 [−0.010,+0.026]; RM−Normal −0.016 [−0.036,−0.0003]; RM−흉내 −0.002 [−0.008,+0.003].
- 해석: YOLO는 유의한 개선이고 Normal과 구분 불가. SSD는 방향은 같으나 유의하지 않고 Normal에는 못 미침(95% CI가 0을 거의 걸침). 흉내와 실제 RM의 차이는 둘 다 0 포함 → 흉내가 타당했음.
- 한계: 야간 100장 1회. DFX 전환 경로·주간·전력은 미측정. 원본 저장소 미반영(복사본 산출물: blc16_rm/, /opt/data/work/blc16_rm_board_20261014/deliverable).


## 원본 반영 및 DFX 자동선택 경로 실측 완료
- 사용자 승인으로 소스·골든·테스트·문서 7개에 BLC16/257 반영. 백업: laptop-linux ~/dfxisp_eval_20261007/blc16_rm/pre_apply_backup_20261014. 커밋·푸시 없음. Normal 소스와 static/BOOT.BIN 불변. 원본 IP 패키지는 여전히 구버전이며 재빌드 산출물과 구분해야 함.
- 새 부팅 상태 DFXC=0x7/GUARD=0x0 확인, JTAG PCAP_PR=0 검증 후 DFX 자동선택 8작업 1200프레임 COMPLETE, error 없음. 스모크 Normal/새 Lowlight 픽셀 불일치 0.
- mAP50-95 (기존 DFX → BLC16 DFX): YOLO 주간 .6546→.6502, 야간 .1880→.2761, 혼합 .3116→.3672, 혼합블록 .3076→.3662. SSD 주간 .4439→.4520, 야간 .1625→.1732, 혼합 .2252→.2346, 혼합블록 .2266→.2395.
- 프레임 paired bootstrap 60회: YOLO 야간 차이 +.0880 CI [.0476,.1212], 혼합 +.0556 [.0266,.0690], 주간 -.0044 [-.0119,.0038]. SSD 야간 +.0107 [-.0090,.0215], 혼합 +.0094 [.0012,.0215], 주간 +.0081 [-.0006,.0187]. 탐색적 CI, 독립 보드 반복실험 아님.
- 동일 입력의 checker dark_count는 대조한 세트에서 동일. YOLO 일부 RM 선택 차이(야간 1프레임/주간 3/혼합블록 2)는 초기 상태·dwell 시간 영향과 부합하나 원인 확정 아님. 혼합은 두 모델 모두 RM 선택 200/200 동일.
- 자동 swap 총 184회, 각 작업 평균 약 3.9ms. 최종 DFXC=0x7/GUARD=0x5; BOOT.BIN/옛 Normal/옛 Lowlight/새 Lowlight 해시 확인. 서버 원자료·채점·CI: /opt/data/work/blc16_dfx_board_20261014/. 전력/프레임당 에너지 결론 없음.
