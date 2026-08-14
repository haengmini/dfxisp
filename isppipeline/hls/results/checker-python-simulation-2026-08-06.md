# Checker Python 실제 RAW 시뮬레이션 (2026-08-06)

## 실행 결과

이번 세션에서 주광 100장과 야간 100장의 RAW `.bin`을 `<u2`로 직접 읽고 원 해상도로 reshape한 뒤 `raw < 4096`을 계수했다.

```text
PYTHON_DECODE frames=200 day=100 night=100 threshold=4096
PYTHON_CSV_COMPARE mismatches=0/200 max_abs_diff=4.9485899507e-06
PYTHON_SEQUENCE combinations=64
```

Pascal CSV는 원 정밀도 기준 `1e-12`, NOD CSV는 소수점 5자리 저장에 따른 `5.0000001e-6`을 허용했다. 따라서 불일치는 0건이며 최대 차이도 NOD 반올림 범위 안이다.

## 시퀀스 결과 요약

아래는 dwell=0의 무밴드(62/62)와 배포 밴드(64/60) 비교다. 모든 값은 직접 디코딩한 `dark_count`로 계산했다.

| 순서 | 밴드 | swaps | recall | 주광 LOW 비율 | thrashing/100 |
|---|---|---:|---:|---:|---:|
| day→night | 62/62 | 57 | 98% | 41% | 28.5 |
| day→night | 64/60 | 47 | 98% | 36% | 23.5 |
| night→day | 62/62 | 57 | 98% | 41% | 28.5 |
| night→day | 64/60 | 47 | 98% | 37% | 23.5 |
| random | 62/62 | 82 | 98% | 41% | 41.0 |
| random | 64/60 | 78 | 98% | 41% | 39.0 |
| chunk shuffle | 62/62 | 65 | 98% | 41% | 32.5 |
| chunk shuffle | 64/60 | 57 | 98% | 37% | 28.5 |

전체 4 순서 × 4 밴드 × dwell 0..3의 64개 조합은 상세 CSV에 있다.

## 중요 발견: 32-bit overflow

HLS `int`를 bit-exact하게 재현하면 한 주광 프레임에서 `dark_count*100`이 signed 32-bit 범위를 넘는다.

```text
OVERFLOW_FRAME stem=2014_000886 n=24208408 dark_count=22635573 decoded_pct=93.502939 dark_pct100_math=2263557300 dark_pct100_int32=-2031409996 selected_mode=0 hyst_flags=2
```

즉 실제 93.50% dark인데 wrap으로 NORMAL/below-exit가 된다. 원본 수정 금지 조건 때문에 구현은 변경하지 않았으며, 최종 통합 시 위험으로 기록한다.

## 산출물

- `checker_validation_2026-08-06/checker_raw_decode_frames_2026-08-06.csv`
- `checker_validation_2026-08-06/checker_hysteresis_sequence_metrics_2026-08-06.csv`
- `checker_validation_2026-08-06/checker_raw_swaps_*.png`
- `checker_validation_2026-08-06/checker_band_comparison_2026-08-06.png`
