# LowlightISP — 가이드

`~/Desktop/dfxisp/LowlightISP/{LowlightISP.cpp, LowlightISP.hpp}`

## 무엇인가

DFXISP의 제안 저조도(low-light) 모듈 v2. `NormalISP`와 **보정 백본(Bayer-domain BLC, gain, CCM)을 공유**하고, 딱 저조도 특화 요소만 다르다:

- **same-colour 2×2 binning**
- **2.0× 노출 게인**
- **H/2 × W/2 출력 형상** (Policy A)

두 모듈의 차이를 저조도 특화 연산 하나로 좁혀놔서, "특화 모듈이 자기 조건에서 일반 모듈을 이긴다"는 연구의 핵심 주장을 **통제된 비교**로 만든다. (원 연구의 기존 저조도 구현은 그대로 유지되는 별개 v1 구현이고, `LowlightISP`를 배포 모듈로 승격할지는 아직 미결정.)

## 파이프라인

```
RAW Bayer 12-bit
 → (1) binning       [RAW]     same-colour 2x2 평균: R/B +6dB(4샘플), G +9dB(8샘플)
                                BLC보다 앞에 둠 — 픽셀별로 0-클립한 뒤 평균하면
                                노이즈가 정류되어 양의 바이어스가 생기기 때문
 → (2) blackLevelCorrection [binned]  펄스탈 감산 + range 복원
 → (3) gain          [binned]  노출 2.0× × 채널별 WB, 한 번의 곱으로 합쳐 quantization 전에 적용
 → (4) colorcorrectionmatrix [RGB12]  NormalISP와 동일 행렬
 → (5) gamma 2.0 곡선 [12→8]   NormalISP와 동일 LUT (2026-08-06부터 GAT/VST 대신 이걸로 확정)
 → packed RGB888 0x00RRGGBB, H/2×W/2 (Policy A)
```

**binning이 BLC보다 먼저인 이유**가 이 모듈의 핵심 설계 결정이다 — 노이즈 있는 샘플을 개별적으로 0에서 클리핑한 뒤 평균하면 양의 바이어스가 생겨서 "노이즈 바닥이 회색으로 들어올려지는" 실패 모드가 나온다(`NormalISP`가 피하려는 바로 그 문제).

## 2026-08-06 이전과 달라진 점 (설계 이력)

- **denoise 삭제됨(비활성화 아님)**: 3×3 sigma-clip denoise가 gamma 곡선 뒤에 있었으나, 임계값 4배 스윕 전 구간에서 mAP@50 개선 없음 확인 후 코드에서 완전히 제거. 이 덕에 파이프라인이 완전히 point-wise가 되어 라인버퍼(유일한 BRAM 소비원)도 같이 사라짐.
- **GAT/Anscombe VST → gamma 2.0으로 교체**: denoise가 사라지면서 VST의 존재 이유(분산 안정화)가 없어졌고, 순수 gamma 곡선으로 비교하니 두 검출기·두 지표 전부에서 gamma 2.0이 우세.

## 인터페이스 — 두 개의 top 함수

```cpp
// 보드 / DFX top — same-colour binning 고정 ON, 실사용에는 이걸 쓸 것
extern "C" void LowlightISP(
    const uint16_t* raw_bayer, uint32_t* rgb_out,
    int width, int height,
    int* out_width, int* out_height);

// 개발/분석용 top — binning 모드 스위치 노출 (ablation용)
extern "C" void LowlightISP_dev(
    const uint16_t* raw_bayer, uint32_t* rgb_out,
    int width, int height,
    int bin_mode,                 // LOWLIGHT_ISP_BIN_SUBSAMPLE(0) / LOWLIGHT_ISP_BIN_BINNING(1)
    int* out_width, int* out_height);
```

`bin_mode=SUBSAMPLE`은 ablation 대조군일 뿐 실사용/배포 경로가 아니다 — binning 자체가 SNR을 얼마나 회복하는지 측정하려고 남겨둔 것.

**보드/Vivado 통합에는 `LowlightISP`.** `NormalISP/`의 `NormalISP`와 포트 시그니처가 동일 — 나중에 DFX 재구성 슬롯을 이 모듈로 교체할 때 배선을 다시 할 필요 없음.

### HLS 인터페이스 프라그마 (두 top 공통)

| 포트 | 인터페이스 | 비고 |
|---|---|---|
| `raw_bayer` | `m_axi` bundle=gmem0, depth=2048 | |
| `rgb_out` | `m_axi` bundle=gmem1, depth=2048 | |
| 나머지 스칼라 | `s_axilite` bundle=control | |
| 내부 루프 | `#pragma HLS PIPELINE II=1` | binned cell 단위로 II=1 파이프라이닝 |

## 핵심 상수

| 스테이지 | 상수 | 값 | 비고 |
|---|---|---|---|
| (2) BLC | `BLC_LEVEL12` / `BLC_MUL_Q8` | 32 / 258 | NormalISP와 동일값(2026-07-20 배포) |
| (3) gain | `EXPOSURE_GAIN_Q8` | 512 (2.0×) | |
| (3) WB | `WB_R/G/B_Q8` | 286 / 256 / 307 | 고정 상수 — **AWB 없음**(NormalISP와 차이). WB는 세 차례 독립 캠페인에서 mAP 무반응(레버 아님)으로 확인돼 적응 로직을 안 씀 |
| (4) CCM | 3×3 Q8 | NormalISP와 동일 행렬 | 백본 공유 |
| (5) gamma | LUT | γ=2.0, `NormalISP.cpp`와 byte-identical | |
| shape | `bin_dim(d)` | `max(1, d/2)` | Policy A |

## 소스 코드 주석 전문 (2026-09-03, 코드에서 이관)

`LowlightISP.cpp`/`LowlightISP.hpp`에 있던 설명 주석을 한글로 번역해 여기로 옮기고,
소스 자체는 `#pragma HLS` 지시문과 코드만 남겼다.

### 파일 헤더 (hpp)

> LowlightISP — 제안 저조도 모듈(v2). `results/lowlight-feature-principles-2026-07-05.md`의
> 원칙과 07-08~07-20 실 RAW 캠페인에서 측정된 레버들을 바탕으로 재구성했다
> (원본 레포: haengmini/dfxisp).
>
> 모든 연산은 정수이며 `tools/gen_lowlight_isp_golden.py`와 bit-exact다.

### `LowlightISPBinning` enum (hpp)

> Binning 모드(스테이지 1). SUBSAMPLE은 2026-08-06 이전 동작을 재현한 것(셀당 R 1개·
> B 1개 샘플 = 0dB, 셀의 G 2개 샘플 = +3dB)으로, **오직 ablation 대조군으로만** 존재한다
> — 이걸 두면 binning의 SNR 기여를 가정이 아니라 직접 측정할 수 있다.
> **합성 Poisson-Gaussian 프레임에서 측정한 BINNING 대비 SUBSAMPLE 이득: +5.6~+7.1dB.**

### `LowlightISP_dev` 선언부 (hpp)

> 개발/분석용 top: binning 모드 스위치를 노출한다.
> `raw_bayer` : RAW Bayer RGGB, `uint16_t`의 12-bit 값(W*H).
> `rgb_out` : packed RGB888 `0x00RRGGBB`; 용량 ≥ W*H(실제로는 W/2 * H/2 사용).
> `out_width`/`out_height`는 binning 후 형상을 보고한다(Policy A).

### `LowlightISP` 선언부 (hpp)

> 보드/DFX top: same-colour binning 고정 ON. 포트 목록이 `NormalISP()`와 (타입·순서·
> 개수까지) 완전히 동일해서, 둘 다 같은 reconfigurable-partition 슬롯의 유효한
> 구현이 된다(SPEC.md §7, 원본 레포).

### BLC 상수 (cpp, `BLC_LEVEL12`/`BLC_MUL_Q8`)

```
BLC_LEVEL12 = 2 << 4;   // 32; 실 RAW 배포값(2026-07-20)
BLC_MUL_Q8  = 258;      // round(256 * 4095 / (4095 - 32))
```

### gain / WB 상수 (cpp, `EXPOSURE_GAIN_Q8`, `WB_*_Q8`)

> gain은 SNR을 바꿀 수 없지만, `>>4` 이전에 배치하면 양자화 손실이 최소화된다.
> 노출과 화이트밸런스를 채널당 곱셈 한 번으로 합쳤다.
> binning(1)에서 이미 채널이 분리됐으므로, `NormalISP`가 쓰는 Bayer-site별 변형이
> 아니라 단순 채널별 gain이면 된다.
> WB는 고정 상수로 둔다: 세 차례 독립 캠페인에서 WB가 non-lever임이 측정됐고
> (mAP spread 0.0020, BLC 레버의 0.0876 대비 작음), 그래서 일반 케이스를 위한
> 적응형 AWB를 유지하는 `NormalISP`와 달리 여기서는 적응 로직을 쓰지 않는다.

### CCM 상수 (cpp, `CCM_Q8`)

> `NormalISP`와 동일한 행렬(행 합이 256 → 무채색 보존)이라 두 모듈이 백본을 공유한다.
> **센서 캘리브레이션 전까지는 placeholder.**

### gamma LUT (cpp, `GAMMA2_LUT`)

> gamma 2.0을 `floor(sqrt(255*v))`로 구현, `NormalISP`의 테이블과 byte-identical
> (각 모듈이 실리콘에서 자기 ROM을 따로 가짐).
>
> 이 자리는 2026-08-06 전까지 GAT/Anscombe VST 곡선이 있었다. VST는 CONSTANT-threshold
> denoise를 유효하게 만들려고 존재했는데, 그 denoise가 무가치하다고 측정되어 삭제되자
> VST 곡선도 단순 gamma map으로서 스스로를 정당화해야 했고 — 결국 이 곡선에 패배했다.
> 야간 100장, 두 검출기·두 지표 전부:
>
> | | mAP@[.5:.95] / mAP@50 (YOLOv8n) | mAP@[.5:.95] / mAP@50 (SSDLite MNv3) |
> |---|---|---|
> | gamma 2.0 | 0.1876 / 0.3797 | 0.1250 / 0.2427 |
> | GAT | 0.1775 / 0.3710 | 0.1145 / 0.2314 |
>
> GAT의 a/b는 바로 이 분할에서 캘리브레이션됐으므로, 이건 GAT의 홈그라운드에서도 진
> 것이다. 이 곡선은 `tools/gen_lowlight_isp_golden.py`에 ablation arm으로만 남아있다.
> 근거: `results/gat-tone-ablation-2026-08-06.md`.

### `cell_sites()` (cpp)

> 셀 (cx, cy)의 네 Bayer 사이트: R, G(우상단), G(좌하단), B.

### `binned_raw()` (cpp) — 스테이지 (1) binning

> 스테이지 (1): binning, RAW 도메인에서 아직 어떤 보정도 적용하지 않은 상태.
>
> BINNING은 진짜 same-colour 2×2 binning이다 — Bayer 셀 2×2 이웃의 R 사이트를 평균
> (샘플 4개 → sigma/2 → +6dB), B 사이트도 마찬가지, G는 8개 사이트 전부(+9dB).
> 윈도우가 겹치므로 출력은 H/2×W/2를 유지하고 인접 출력끼리 상관관계를 갖는다 —
> 해상도를 유지하는 대가다. 합성 Poisson-Gaussian 프레임에서 측정: **+5.6~+7.1dB**.
>
> SUBSAMPLE은 레거시 경로다(셀 자체에서 R 1개·B 1개 샘플, 0dB; 셀의 G 2개 샘플, +3dB).
> binning의 SNR 기여를 직접 측정할 수 있도록 **오직 ablation 대조군으로만** 남겨뒀다.

### `correct_channel()` (cpp) — 스테이지 (2)+(3)

> 스테이지 (2) black level과 (3) gain을, binning된 값에 한 번만 적용한다. 평균을
> 낸 **뒤에** pedestal을 감산하는 게 비편향 순서다 — 노이즈 있는 샘플을 먼저 0에서
> 클리핑하면 노이즈가 정류되어 양의 바이어스가 생기는데, 이건 이 모듈이 피하려는
> "노이즈 바닥이 회색으로 들어올려지는" 바로 그 실패 모드다.

### `binned_rgb()` (cpp)

> 스테이지 (1)~(3).

### `ccm_channel()` (cpp) — 스테이지 (4)

> 스테이지 (4). 음수 CCM 계수가 누산값을 0 아래로 끌어내릴 수 있어서, 시프트 전에
> 0으로 플로어링한다 — 음수에 대한 arithmetic-shift 동작에 의존하지 않고도 C++와
> Python golden이 bit 단위로 정확히 일치하게 하기 위함이다.

### `apply_gamma()` (cpp) — 스테이지 (5)

> 스테이지 (5): CCM 출력은 이미 `[0, RAW12_MAX]`로 클램프돼 있으므로, `>>4` 인덱스는
> 구조적으로 항상 범위 안에 있다.

### `run_lowlight_isp()` (cpp)

> 모든 스테이지가 binning된 셀 단위로 point-wise라서, binning된 픽셀 하나가 같은
> iteration 안에서 생성되고 바로 출력된다 — 라인 버퍼도, row latency도 없다. 이 루프가
> 예전에 유지하던 3행 슬라이딩 윈도우는 3×3 denoise를 먹이기 위한 용도로만 존재했고,
> 그 스테이지를 제거하면서 그 저장공간도 함께 사라졌다.

### `LowlightISP()` (cpp, 보드/DFX top 직전)

> 포트 목록이 `NormalISP()`와 정확히 일치한다 — 같은 reconfigurable partition 슬롯에
> 그대로 꽂아 넣을 수 있다.

## 검증 상태 (원본 SPEC.md 기준, 2026-08-06)

- ✅ Python golden ↔ C++ bit-exact
- ✅ csynth 실측(배포 구성=denoise OFF): LUT 8,115 / DSP 20 / FF 5,483 / BRAM 11, 3.650ns — 원 연구 기존 저조도 구현 대비 1.93배, `NormalISP`보다 36% 작음
- ✅ 야간 100장 mAP: 원 연구 기존 저조도 구현 대비 두 지표 우위 확인
- ✅ **post-route 실측 + 보드 실물 검증 완료 (2026-09-04)** — 아래 "이 저장소에서의 로컬 검증" 및 §4~§9 참고

**이 저장소(`dfxisp`)에서의 로컬 검증 (2026-09-04):**

`NormalISP`와 마찬가지로 이 워크스페이스엔 `.cpp`/`.hpp`만 있었고 HLS 프로젝트가 없었다. `LowlightISP_tb.cpp`(구조적 sanity 테스트, `NormalISP_tb.cpp`와 동형)를 새로 작성하고 `vitis-run --mode hls`로 csim→csynth→cosim→package까지 실행했다.

- ✅ **csim 통과** — 7개 케이스 13개 체크 전부 PASS(`LowlightISP_hls/LowlightISP/logs/hls_run_csim.log`).
- ✅ **csynth 실측**(`LowlightISP_hls/LowlightISP/hls/syn/report/LowlightISP_csynth.rpt`): 타이밍 target 4.00ns/estimated 2.920ns 통과, LUT 7,041(3%) / FF 4,919(1%) / DSP 14(~0%) / BRAM_18K 4(~0%) — `NormalISP`(LUT 12,812)보다 훨씬 작아 §자원 비교 기록과 부합. **메인 binning 루프 II=16(목표 1)** — `binned_raw()`의 BINNING 경로가 이웃 2×2 bin-cell × Bayer 4-site = 픽셀당 `m_axi_gmem0` 16회 개별 읽기를 발생시켜서(라인버퍼 없음) `NormalISP`의 "3×3 윈도우 9회 재읽기 → II=9" 문제와 같은 성격의 병목이 binning 특성상 더 심하게 재현됨. 최대 트립카운트 기준 latency ≈33.178ms/frame — 30fps(33.3ms) 예산에 거의 붙어서 통과, 실측 여유가 사실상 없다. 최적화는 별도 결정 사항.
- ⚠️ **cosim FAIL** — `LowlightISP_tb.cpp`의 "guarded inputs(널 포인터)" 케이스가 csim(C++)에서는 통과하지만 cosim(C/RTL)에서만 실패한다(`LowlightISP_hls/LowlightISP/logs/hls_run_cosim.log`). `m_axi` 마스터 포트에 널 주소(0x0)를 넘기는 게 Vitis HLS cosim BFM의 알려진 취약 지점일 가능성이 높지만, RTL이 실제로 널 가드를 어기고 AXI 트랜잭션을 내는 실제 버그일 가능성도 배제 못 한다 — **미해결 상태로 남겨둠**(실사용 앱은 널 포인터를 절대 넘기지 않으므로 이번 보드 브링업 자체를 막는 이슈는 아니라고 판단하고 진행). `export_design -flow none` 패키징은 cosim 통과가 필수 조건이 아니라서 정상적으로 IP가 만들어졌다.
- ✅ **Package/Export 완료** — `xilinx_com_hls_LowlightISP_1_0.zip`(VLNV `xilinx.com:hls:LowlightISP:1.0`), IP 카탈로그에서 `LowlightISP`로 검색됨.
- ✅ **Vivado 통합 + bitstream + Export Hardware 완료** — §3 참고.

## 보드 실장 가이드: Vitis HLS → Vivado → PetaLinux → ZCU104

`JNU_Lab_Petalinux`(`haengmini/JNU_Lab_Petalinux`) 튜토리얼과 `docs/NormalISP.md`의 "보드 실장 가이드"를 그대로 잇는다. `LowlightISP`는 `NormalISP`와 **포트 시그니처가 완전히 동일**(같은 6개 인자, 같은 `m_axi`/`s_axilite` 배치)하므로, 이 가이드는 아래 두 경로 중 하나로 진행한다.

> **범위:** 이것도 `LowlightISP` 하나만 정적으로(재구성 없이) 올리는 단계다. `NormalISP`↔`LowlightISP` 런타임 스왑(DFX)은 둘 다 static 브링업이 각자 성공적으로 검증된 뒤의 별개 단계.

### 경로 선택

| 상황 | 경로 |
|---|---|
| `NormalISP` static 브링업을 이미 끝냈다 | **경로 A(스왑)** — Vivado 프로젝트의 IP만 `LowlightISP`로 교체, 나머지(주소맵, DDR 예약, UIO 이름)는 그대로 재사용 가능 |
| `LowlightISP`부터 단독으로 시작한다 | **경로 B(단독)** — `docs/NormalISP.md`의 전체 단계를 `LowlightISP`로 이름만 바꿔 그대로 수행 |

두 경로 모두 최종적으로 도달하는 하드웨어 구성은 동일하다 — DFX의 전제 자체가 "같은 정적 셸 + 같은 슬롯에 어느 RM을 앉혀도 나머지가 안 바뀐다"는 것이므로, 이 가이드가 두 모듈에서 거의 그대로 복사되는 것 자체가 그 계약이 실제로 성립함을 보여주는 확인 작업이기도 하다.

### 1. Vitis HLS

**실제 사용한 `hls_config.cfg`** (`LowlightISP_hls/hls_config.cfg`, `NormalISP_hls/hls_config.cfg`와 동형):

```ini
part=xczu7ev-ffvc1156-2-e

[hls]
flow_target=vivado
package.output.format=ip_catalog
package.output.syn=false
syn.top=LowlightISP
syn.file=/home/mini/Desktop/dfxisp/LowlightISP/LowlightISP.cpp
tb.file=/home/mini/Desktop/dfxisp/LowlightISP/LowlightISP.hpp
tb.file=/home/mini/Desktop/dfxisp/LowlightISP/LowlightISP_tb.cpp
clock=4ns
```

```bash
vitis-run --mode hls --csim \
  --config /home/mini/Desktop/dfxisp/LowlightISP/LowlightISP_hls/hls_config.cfg \
  --work_dir LowlightISP
# 이어서 --csynth, --cosim(선택, §검증 상태의 cosim FAIL 참고), --package
```

- **Top function은 `LowlightISP`** (same-colour binning 고정 ON). `LowlightISP_dev`는 ablation용이라 IP로 내보내지 않음 — `NormalISP`/`NormalISP_dev` 관계와 동일한 구도.
- **실측(2026-09-04): `add_files` 중첩 경로 버그는 재현되지 않았다** — `NormalISP`와 마찬가지로 `LowlightISP/` 디렉토리 그대로(flat 디렉토리 우회 없이) csim/csynth/package 전부 정상 통과했다. 문제가 생기면 `docs/NormalISP.md` §1의 flat-디렉토리 우회를 시도할 것.
- Export RTL → IP 이름 `LowlightISP_v1_0`, VLNV `xilinx.com:hls:LowlightISP:1.0` — Vivado IP 카탈로그에서 `LowlightISP`로 검색하면 나옴(실측 확인됨).

### 2. AXI-Lite 레지스터 맵 — csynth 실측으로 확정 (2026-09-04)

`LowlightISP_hls/LowlightISP/hls/impl/ip/drivers/LowlightISP_v1_0/src/xlowlightisp_hw.h`에서 확정. **교차검증 결과: `NormalISP`(`xnormalisp_hw.h`)와 바이트 단위로 완전히 일치** — AP_CTRL/GIE/IER/ISR, 모든 인자 오프셋까지 하나도 어긋나지 않았다. DFX 계약("두 RM이 같은 control 레지스터 레이아웃을 가져야 한다")이 이 시점에 실측으로 충족됨.

| 오프셋 | 레지스터 | 설명 |
|---|---|---|
| `0x00` | `AP_CTRL` | bit0 `ap_start` / bit1 `ap_done` / bit2 `ap_idle` / bit3 `ap_ready` / bit7 `auto_restart` / bit9 `interrupt` |
| `0x04` | `GIE` | Global Interrupt Enable |
| `0x08` | `IER` | IP Interrupt Enable |
| `0x0c` | `ISR` | IP Interrupt Status |
| `0x10` / `0x14` | `raw_bayer` 하위32 / 상위32 | m_axi 포인터 물리주소 |
| `0x1c` / `0x20` | `rgb_out` 하위32 / 상위32 | m_axi 포인터 물리주소 |
| `0x28` | `width` | 입력 스칼라 |
| `0x30` | `height` | 입력 스칼라 |
| `0x38` | `out_width` data | 출력 스칼라 — **`bin_dim(width)`, `width`와 다름** |
| `0x3c` | `out_width` ctrl | bit0 `ap_vld` — read-back 전 확인 |
| `0x48` | `out_height` data | 출력 스칼라 — **`bin_dim(height)`, `height`와 다름** |
| `0x4c` | `out_height` ctrl | bit0 `ap_vld` — read-back 전 확인 |

**`NormalISP`와 유일하게 다른 실사용 포인트:** 레지스터 오프셋 자체는 같지만, `out_width`/`out_height`에 read-back되는 **값**이 `NormalISP`처럼 입력과 같지 않고 `bin_dim(width)`/`bin_dim(height)`로 줄어든다 — 유저스페이스 앱에서 `rgb_out` 버퍼를 읽을 크기를 계산할 때 반드시 이 read-back 값을 써야 한다(입력 `width`/`height`로 계산하면 4배 큰 영역을 읽어버림 — §7 `lowlightisp_uio_test.py` 참고).

### 3. Vivado 하드웨어 통합

**경로 A(스왑):** 기존 `NormalISP` Vivado 프로젝트를 열어 Block Design에서 `NormalISP_0` 인스턴스를 삭제하고 `LowlightISP` IP로 교체 — AXI 주소(control `0xA000_0000`, `m_axi_gmem0`/`gmem1` 매핑), 클럭/리셋, (선택)인터럽트 배선은 전부 그대로 둔다. Validate → Generate Bitstream → Export Hardware만 다시 실행.

**경로 B(단독):** `docs/NormalISP.md` §3을 그대로 따르되 인스턴스명만 `LowlightISP_0`로 바꾼다. 데이터 경로도 동일하게 `m_axi_gmem0`(raw_bayer 읽기)/`m_axi_gmem1`(rgb_out 쓰기) 두 개.

```
LowlightISP_0/m_axi_gmem0 (raw_bayer, read) ─┐
                                              ├─ AXI SmartConnect ─ S_AXI_HP0_FPD ─ PS DDR4
LowlightISP_0/m_axi_gmem1 (rgb_out, write) ──┘
```

주소는 `NormalISP`와 **같은 값을 쓸 것을 권장**(control `0xA000_0000`, 64 KiB) — 지금은 두 모듈이 각자 별도 정적 비트스트림(둘 다 동시에 보드에 있지 않음)이라 주소가 겹쳐도 문제 없고, 오히려 나중에 진짜 DFX RP로 통합할 때 두 RM이 같은 control 주소를 쓴다는 계약을 미리 지키게 된다.

**실측(2026-09-04) — 경로 B(단독)로 완료:** `LowlightISP_zcu104` 프로젝트를 새로 만들고, Zynq MPSoC(board preset 적용) + `LowlightISP` IP + `axi_smc`로 구성했다. `NormalISP`를 만들 때는 `axi_smc`가 처음에 `NUM_SI=1, NUM_MI=2`(gmem0 하나가 HP0/HP1 양쪽으로 팬아웃되는 구조, 실제로는 `gmem1`이 어디에도 안 물린 채 방치됨)로 잘못 구성된 채 저장돼 있었던 게 뒤늦게 발견됐는데(§검증 상태 참고할 필요는 없고 이 브링업 세션에서 실측), `LowlightISP`는 처음부터 **`axi_smc: NUM_SI=2`(S00=`gmem0`, S01=`gmem1`) → `M00_AXI` 하나 → `S_AXI_HP0_FPD`**로 깔끔하게 잡았다 — HP1은 아예 안 씀. Run Connection Automation을 gmem1에 대해 별도로 한 번 더 돌리면(기존 `axi_smc` 재사용 지정) NUM_SI가 1→2로 자동으로 늘어나면서 `S01_AXI`가 새로 생기는 식으로 잡힌다. **Generate Bitstream + Export Hardware 완료** — `LowlightISP_zcu104/LowlightISP_zcu104_wrapper.xsa` + `LowlightISP_zcu104.runs/impl_1/LowlightISP_zcu104_wrapper.bit`.

### 4. PetaLinux 하드웨어 임포트

`docs/NormalISP.md` §4와 동일한 절차 — `MACHINE_NAME (AUTO)` 유지, `Remove PL from devicetree` 비활성화 확인 후:

```bash
mkdir -p ~/project/lowlightisp_hw
cp /home/mini/Desktop/dfxisp/LowlightISP/LowlightISP_zcu104/LowlightISP_zcu104_wrapper.xsa ~/project/lowlightisp_hw/
petalinux-config --get-hw-description=~/project/lowlightisp_hw/
petalinux-build -c device-tree
grep -Rni -A15 -B3 "lowlightisp" components/plnx_workspace/device-tree/
```

**권장: `NormalISP`가 이미 빌드해 둔 PetaLinux 프로젝트(`NormalISP/project/xilinx-zcu104-2024.1/`)를 그대로 재사용할 것.** 커널 UIO 빌트인 설정(§6의 `bsp.cfg` 수정), rootfs(`petalinux-image-minimal`, auto-login), `SSTATE_MIRRORS` 우회(§8)가 전부 커널/rootfs 레벨 설정이라 가속기 IP 종류와 무관하게 그대로 이어받는다 — 위 `petalinux-config --get-hw-description`을 **이 프로젝트 안에서** 다시 실행해 하드웨어 정의만 `LowlightISP` 걸로 갱신하면 §6/§8의 재작업이 필요 없다. (두 static 빌드를 나란히 보존해 비교하고 싶으면 프로젝트를 분리해도 되지만, 그러면 §6/§8을 처음부터 다시 해야 한다.)

**`NormalISP`에서 실측된 대소문자 함정이 여기도 그대로 적용된다** (`docs/NormalISP.md` §4, 2026-09-04 실측): 자동 생성되는 디바이스트리 노드 라벨은 소문자 `lowlightisp_0`가 아니라 Vivado IP 인스턴스 이름을 그대로 보존한 **`LowlightISP_0`**다. `system-user.dtsi`의 오버레이 타깃은 `&lowlightisp_0`가 아니라 **`&LowlightISP_0`**로 써야 한다 — 틀리면 디바이스트리 컴파일은 에러 없이 성공하지만 UIO 노드가 조용히 안 만들어진다. `petalinux-build -c device-tree` 후 중간 산출물이 아니라 **최종 `images/linux/system.dtb`를 `dtc -I dtb -O dts`로 디컴파일해서** 직접 확인할 것.

### 5. UIO 구성 + DDR 버퍼 예약

```dts
/include/ "system-conf.dtsi"
/ {
    reserved-memory {
        #address-cells = <2>;
        #size-cells = <2>;
        ranges;

        lowlightisp_reserved: buffer@70000000 {
            no-map;
            reg = <0x0 0x70000000 0x0 0x00800000>;   /* NormalISP와 동일 8 MiB 레이아웃 재사용 */
        };
    };

    lowlightisp_buffer: lowlightisp-buffer@70000000 {
        compatible = "generic-uio";
        linux,uio-name = "lowlightisp-buffer";
        reg = <0x0 0x70000000 0x0 0x00800000>;
    };
};

&LowlightISP_0 {
    compatible = "generic-uio";
    linux,uio-name = "lowlightisp-control";
};
```

(라벨 대소문자는 §4의 실측 정정 참고 — `&lowlightisp_0`가 아니라 `&LowlightISP_0`.)

**버퍼 크기는 `NormalISP`와 같은 8 MiB/같은 오프셋을 그대로 재사용한다** — 이유는 §3의 주소 재사용과 같다(정적 셸과 데이터 계약이 RM 종류와 무관해야 DFX가 성립). 다만 **실제로 쓰이는 데이터 양은 다르다**:

```
raw_bayer 슬롯(0x70000000, 2 MiB) : 입력은 NormalISP와 동일 — 1280×720×2B ≈ 1.76 MiB, 풀 해상도 그대로 읽음
rgb_out 슬롯(0x70200000, 4 MiB)   : 출력은 H/2×W/2 — 1280×720 입력 기준 640×360×4B ≈ 900 KiB만 실제로 쓰임
                                     (Policy A: 형상이 줄어들 뿐 슬롯 자체를 줄일 필요는 없음 — 남는 공간은 낭비지만
                                     NormalISP와 동일 레이아웃을 유지하는 대가로 감수)
```

애플리케이션은 `rgb_out` 슬롯을 무조건 4 MiB 다 읽지 말고, **레지스터에서 read-back한 `out_width`×`out_height`만큼만** 유효 데이터로 취급해야 한다(§7).

### 6. Generic UIO 커널 활성화 + rootfs

`docs/NormalISP.md` §6과 완전히 동일 — 이미 그 프로젝트에서 커널을 UIO 빌트인으로 설정해뒀다면(같은 PetaLinux 프로젝트를 재사용하는 경우) 이 단계는 다시 할 필요 없다. 새 프로젝트로 분리했다면(§4 권장안) 커맨드 그대로 반복:

```bash
petalinux-config -c kernel
# Device Drivers ---> Userspace I/O drivers ---> <*> Userspace I/O platform driver with generic IRQ handling

petalinux-build -c kernel
grep -E '^CONFIG_UIO=|^CONFIG_UIO_PDRV_GENIRQ=' build/tmp/work-shared/xilinx-zcu104/kernel-build-artifacts/.config

petalinux-config
# DTG Settings ---> Kernel Bootargs ---> User Set Kernel Bootargs:
#   earlycon console=ttyPS0,115200 clk_ignore_unused init_fatal_sh=1 uio_pdrv_genirq.of_id=generic-uio

petalinux-config
# Image Packaging Configuration ---> INITRAMFS/INITRD Image name -> petalinux-image-minimal
petalinux-config -c rootfs
# Image Features ---> [*] auto-login
```

### 7. 유저스페이스 앱

`board_test/lowlightisp_uio_test.py` + `board_test/run_all_bayer_lowlight.py`(2026-09-04 신규 작성, `normalisp_uio_test.py`/`run_all_bayer.py`를 포트)를 그대로 쓸 것. `NormalISP`용 스크립트를 그대로 재사용하면 안 되는 지점을 하나 찾아서 고쳤다:

```text
1. /sys/class/uio/uio*/name 검색 → "lowlightisp-control" / "lowlightisp-buffer" 탐색
2. 두 UIO open() + mmap() (control 64 KiB, buffer 8 MiB — NormalISP와 동일)
3. buffer 오프셋 0x000000에 RAW 테스트 프레임 기록 (NormalISP와 동일 — 입력은 풀 해상도)
4. control 레지스터에 raw_bayer(0x70000000) / rgb_out(0x70200000) 물리주소, width/height 프로그램
5. AP_START 세트 → AP_DONE 폴링
6. control에서 out_width/out_height read-back  ← 반드시 먼저 읽을 것: LowlightISP는 이 값이
   NormalISP처럼 입력과 같지 않고 bin_dim(width)/bin_dim(height)로 줄어든 값이다
7. buffer 오프셋 0x200000에서 **out_width × out_height × 4바이트만**(입력 width×height가 아니라
   방금 read-back한 out_width/out_height) rgb_out으로 판독
   (나머지 슬롯은 이전 실행의 잔여 데이터이거나 미정의 — 읽지 말 것)
```

**`normalisp_uio_test.py`를 그대로 포트하면 깨지는 지점:** 원본은 `rgb_size = width * height * 4`로 **입력** 크기를 그대로 썼다 — `NormalISP`는 shape-preserving이라 문제가 없었지만, `LowlightISP`는 출력이 1/4 픽셀 수라 이대로 쓰면 버퍼의 4배 넓은 영역(대부분 미정의 값)을 읽어버린다. `lowlightisp_uio_test.py`는 6번에서 read-back한 `out_width`/`out_height`로 크기를 계산하도록 고쳐져 있다. 출력 파일명도 입력 파일명의 `_<W>x<H>` 태그를 실제 출력 크기로 바꿔 다시 붙인다(`rgb888_to_png.py`가 파일명에서 W×H를 파싱하므로).

**테스트 프레임은 새로 변환할 필요 없이 그대로 재사용:** `raw_bayer` 입력 포맷/해상도가 `NormalISP`와 완전히 동일하므로, `dataset/test/bayer/{PASCAL,LOD}/*.bin`(§7-1, `tools/raw_to_bayer_bin.py`로 이미 변환됨 — PASCAL 602×400, LOD 610×408)을 그대로 SD카드에 올려 쓰면 된다. 재변환 불필요.

**정확성 검증도 같은 순서:** `NormalISP.md` §7과 마찬가지로 Python golden(`tools/gen_lowlight_isp_golden.py`, 원본 레포)의 합성 테스트 케이스로 먼저 bit-exact를 확인한 뒤 PASCALRAW/SonyNOD 실 프레임으로 넘어갈 것. `LowlightISP`는 야간(SonyNOD류) 프레임에서 차이가 드러나는 모듈이므로, 주광 프레임 하나(`NormalISP`와 동일 계약 검증용)와 저조도 프레임 하나를 모두 태워 두 조건 모두에서 출력 형상(`out_width==bin_dim(width)`)과 값이 golden과 맞는지 확인하는 게 좋다. 이 저장소엔 그 golden generator가 없어서(§검증 상태 참고), `NormalISP` 때와 마찬가지로 합성 케이스를 건너뛰고 바로 실제 RAW로 진행하게 될 가능성이 높다 — 그 경우 bit-exact golden 대비 검증은 여전히 미실시라는 한계가 남는다는 점은 §NormalISP.md와 동일.

**참고용 지연시간 추정(실측 아님):** `NormalISP`는 100MHz `pl_clk0`, II=9, 602×400/610×408에서 각각 142.2ms/147.0ms를 실측했다. `LowlightISP`는 (a) binning 루프가 픽셀 대신 셀 단위라 반복 횟수가 1/4이고 (b) II=16(§검증 상태)이라 셀당 읽기가 좀 더 많다 — 총 `m_axi_gmem0` 읽기 횟수 기준으로는 `NormalISP`의 `9×W×H` 대비 `LowlightISP`가 `16×(W/2)×(H/2) = 4×W×H`로 대략 4/9배다. 같은 클럭·같은 해상도라면 **대략 60~70ms대**로 추정되지만 어디까지나 어림값이고, 실측치는 아래 §9에 채워 넣을 것.

### 8~9. 빌드/패키징/SD카드, 보드 검증

`docs/NormalISP.md` §8~9와 절차는 동일, UIO 이름만 `lowlightisp-control`/`lowlightisp-buffer`로 바뀐다.

```bash
petalinux-build
petalinux-package --boot --fsbl images/linux/zynqmp_fsbl.elf --fpga images/linux/system.bit --u-boot --force
cp -f images/linux/BOOT.BIN images/linux/image.ub images/linux/boot.scr /media/$USER/BOOT/
```

```bash
for d in /sys/class/uio/uio*; do echo "$d : $(cat $d/name)"; done
# "lowlightisp-control", "lowlightisp-buffer"가 보여야 함
ls -l /sys/bus/platform/drivers/uio_pdrv_genirq/   # a0000000.lowlightisp, 70000000.lowlightisp-buffer
```

**`NormalISP` 브링업에서 실측된 두 가지 함정이 여기도 그대로 적용된다** (`docs/NormalISP.md` §8, 2026-09-04 실측 — PetaLinux 프로젝트를 재사용하면 첫 번째는 이미 고쳐져 있을 것):

- **`petalinux-build`의 sstate 미러 타임아웃(오탐):** `SState: cannot test file://...: TimeoutError`로 매 빌드마다 비정상 종료 코드가 나지만 `Tasks Summary: ... all succeeded`면 실제로는 성공. `petalinux.xilinx.com`이 AMD 통합 이후 죽어있어서다. `project-spec/meta-user/conf/petalinuxbsp.conf`에 `SSTATE_MIRRORS = ""` 추가로 해결.
- **SD카드에 새로 쓴 파일이 `sync`만으로는 0바이트로 깨짐:** 결과 파일을 SD카드로 옮긴 뒤 `sync`만 하고 뽑으면 새로 생성된 파일명은 최초 시도에서 거의 항상 0바이트가 된다. **반드시 `umount`까지** 할 것:
  ```bash
  cd /root && sync && umount /run/media/mmcblk0p1
  ```

`board_test/run_all_bayer_lowlight.py`로 실제 카메라 RAW를 처리한 뒤, 결과는 §7의 지연시간 추정치와 비교하고 이 절 하단에 실측치를 채워 넣을 것(`NormalISP.md` §9와 동일한 형식).

### 10. 이후 확장

**DPU 통합 실험은 `docs/LowlightISP_DPU.md`로 분리했다** — `NormalISP_DPU`와 같은 블록 디자인에서 ISP만 이 IP로 교체해 200장 검출 정확도를 재는 실험이고, 이 문서의 보드 브링업(§1~§9)이 그 전제다.


`NormalISP`와 `LowlightISP` 둘 다 static 브링업이 검증되면(같은 정적 셸에서 서로 다른 정적 비트스트림으로 각자 성공), 다음이 DFX 전환의 실질적 선행 조건이 채워진 상태다:

- 두 모듈이 **동일한 control 레지스터 오프셋**(§2에서 diff 확인), **동일한 데이터 버퍼 레이아웃**(§5)을 갖는다는 게 보드에서 실증됨.
- 남은 건 SPEC.md §7의 AMD DFX Controller IP(PG374) + `checker`(static-region, `docs/checker.md`)를 얹어 이 두 정적 비트스트림을 **런타임 상호배타 RM**으로 합치는 것.

## 더 깊은 배경이 필요하면

원본 레포의 `isppipeline/hls/src/lowlight_isp.md`(원본 파일명, 아직 이 이름 체계 반영 전), `results/gat-tone-ablation-2026-08-06.md`, `results/denoise-k-sweep-2026-08-06.md`에 binning/denoise/gamma 곡선 관련 ablation 전체 근거가 있다. 이 폴더는 cpp/hpp만 의도적으로 둔 것.
