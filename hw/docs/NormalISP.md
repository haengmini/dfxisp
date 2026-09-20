# NormalISP — 가이드

`~/Desktop/dfxisp/NormalISP/{NormalISP.cpp, NormalISP.hpp}`

## 무엇인가

AMD Vitis Vision L3 `isppipeline` 예제의 **스테이지 순서·도메인을 그대로 계승**한 표준(standard) ISP 모듈. 원 연구의 기존 정상-조도 구현은 demosaic **후** RGB 도메인에서 고정 WB + identity CCM으로 보정하는 반면, `NormalISP`는 Vitis처럼 **Bayer 도메인에서 먼저 BLC/gain을 걸고, demosaic 후 adaptive AWB + 실제 3×3 CCM**을 적용한다. 구조 자체가 다른 대조군이라 "표준 ISP baseline" 주장에 이쪽이 쓰인다.

DFXISP 구도에서 이 모듈은 **normal(주광) 조건용 후보**다. `LowlightISP`와 보정 백본(BLC/gain/CCM)을 공유하고, 저조도 특화 여부만 다르다 — 두 모듈을 나란히 두면 통제된 비교가 된다.

## 파이프라인 (Vitis Vision 순서)

```
RAW Bayer 12-bit
 → (1) blackLevelCorrection   [Bayer 도메인, subtract + range rescale]
 → (2) gaincontrol            [Bayer 도메인, position별 R/B 게인, G는 기준채널]
 → (3) demosaicing             [RGGB bilinear → RGB, 12-bit 유지]
 → (4) AWB                     [RGB 도메인, per-frame adaptive gray-world, bypass 가능]
 → (5) colorcorrectionmatrix   [RGB 도메인, 실제 3×3 Q8 행렬]
 → (6) quantization 12→8       [>>4; Vitis의 optional dithering은 생략]
 → (7) gammacorrection         [256-entry LUT, γ=2.0]
 → packed RGB888 0x00RRGGBB    [Vitis의 rgb2yuyv 출력 CSC는 생략 — DPU가 RGB 그대로 소비]
```

형상은 입력과 동일(H×W, shape-preserving) — `LowlightISP`(H/2×W/2)와 다른 점.

## Vitis 원본과의 의도적 차이 3가지

1. **출력 CSC(rgb2yuyv) 생략** — 후단이 DPU/detector라 RGB888을 그대로 쓰는 게 낫고, YUYV로 바꾸면 평가 파이프라인 전체를 바꿔야 함.
2. **Dithering 생략** — bit-depth 축소 시 밴딩 감소용 옵션 단계인데 mAP에 영향 없음을 확인, `>>4` truncation만 유지.
3. **AWB 통계 소스** — Vitis는 이전 프레임 히스토그램(1프레임 지연, 더블버퍼) 기반. `NormalISP`는 **현재 프레임의 Bayer-site 평균**(gray-world, 지연 없음) 사용 — 대신 raw를 한 번 더 읽음(§구현 노트 참고).

## 인터페이스 — 두 개의 top 함수

```cpp
// 보드 / DFX top — AWB 고정 ON, 실사용에는 이걸 쓸 것
extern "C" void NormalISP(
    const uint16_t* raw_bayer,   // RAW RGGB 12-bit in uint16 (W*H)
    uint32_t*       rgb_out,     // packed RGB888 0x00RRGGBB (용량 >= W*H)
    int width, int height,
    int* out_width, int* out_height);

// 개발/분석용 top — AWB on/off 런타임 스위치 노출 (ablation용)
extern "C" void NormalISP_dev(
    const uint16_t* raw_bayer, uint32_t* rgb_out,
    int width, int height,
    int awb_mode,                 // NORMAL_ISP_AWB_OFF(0) / NORMAL_ISP_AWB_ON(1)
    int* out_width, int* out_height);
```

**보드 브링업/Vivado IP 패키징에는 `NormalISP`를 쓸 것.** `LowlightISP()`와 포트 타입·순서·개수가 완전히 동일해서, 지금은 DFX 없이 정적으로 붙이더라도 나중에 같은 Reconfigurable Partition 슬롯에 `LowlightISP`로 갈아끼울 때 Vivado block design을 다시 짤 필요가 없다.

### HLS 인터페이스 프라그마 (두 top 공통)

| 포트 | 인터페이스 | 비고 |
|---|---|---|
| `raw_bayer` | `m_axi` bundle=gmem0, depth=2048 | AXI Master, DDR 직접 R/W |
| `rgb_out` | `m_axi` bundle=gmem1, depth=2048 | AXI Master, DDR 직접 R/W |
| 나머지 스칼라(`width`/`height`/`awb_mode`/`out_width`/`out_height`) | `s_axilite` bundle=control | AXI-Lite 제어/read-back 레지스터 |
| `return` | `s_axilite` bundle=control | |

`depth=2048`은 C/RTL co-sim BFM 사이징 힌트일 뿐 실합성 메모리 크기가 아님(주석 참고).

## 핵심 상수

| 스테이지 | 상수 | 값 | 근거 |
|---|---|---|---|
| (1) BLC | `BLC_LEVEL12` | 32 (=2<<4) | 2026-07-20 real-RAW 재보정 배포값 |
| (1) BLC | `BLC_MUL_Q8` | 258 | `round(256·4095/(4095−32))` — 감산으로 줄어든 range 복원 |
| (2) gain | `GAIN_R_Q8` / `GAIN_B_Q8` | 286 / 307 | `LowlightISP`의 WB 값과 동일 크기, 적용 **위치**만 다름(Bayer domain) |
| (4) AWB | clamp | Q8 [64, 1024] | 0.25×~4× |
| (5) CCM | 3×3 Q8 | row sum = 256 | 중립 회색 보존, **센서 캘리브레이션 전까지 placeholder** — 색 정확도 주장 근거로 쓰지 말 것 |
| (7) gamma | LUT | γ=2.0, `isqrt(255·v)` | `LowlightISP.cpp`와 byte-identical — gamma 축 비교 가능성 유지 |

## 구현 메모

- BLC/gain은 버퍼 없이 demosaic 윈도우가 픽셀을 읽을 때마다 즉석 계산(pointwise라 등가, 저장 공간 불필요 — 단 같은 픽셀이 최대 9번 재계산될 수 있음, 저장 vs 연산 트레이드오프).
- AWB가 raw 데이터를 통계용으로 한 번 더 읽음 — checker의 풀스캔과 합쳐지면 프레임당 gmem0 read가 늘어나므로 대역폭 예산에 반영할 것.
- 누산기 폭: 1920×1080×4095 ≈ 8.5e9 → 64-bit accumulator 사용.
- CCM 음수 계수로 누산값이 음수가 될 수 있어 shift 전에 0으로 floor — C++와 Python golden의 bit-exact 일치를 위함(음수 우측 시프트의 구현정의 동작 회피).
- **경계 픽셀은 Bayer parity를 보존하지 않는다.** `corrected_bayer()`의 index clamp는 좌표만 grid 안으로 되접을 뿐, 되접힌 좌표가 원래 기대했던 이웃의 색과 같은 parity인지는 보지 않는다 — 예: (0,0)의 왼쪽 이웃(`x=-1`)은 `x=0`으로 clamp되는데, 이는 (0,0) 자기 자신(R site)이라 원래 기대되던 G 이웃 값이 아니다. 그 결과 최외곽 1픽셀 링은 flat scene에서도 내부 픽셀과 다른 값을 낸다 — 의도된 버그는 아니지만 존재하는 특성이며, 골든/테스트 비교 시 반드시 내부 픽셀 기준으로 검증할 것(§C-sim 테스트벤치 참고). mAP에는 프레임당 1픽셀 링이라 영향이 없어 방치.

## 검증 상태 (원본 SPEC.md 기준, 2026-08-06)

- ✅ Python golden ↔ C++ bit-exact (528px, 10 케이스: flat/gradient/color-cast/saturated/odd/1×1)
- ✅ csynth 실측: LUT 12,659 / DSP 28 / FF 8,794, 3.650ns
- ✅ mAP 측정 완료(주광 PASCAL 100장): 원 연구의 기존 정상-조도 구현 대비 유의미한 차이 없음(잡음대 안)
- ⬜ **post-route 미실측, 보드 미검증** — 배포 모듈 아님, 이번 브링업이 사실상 첫 실물 검증

**이 저장소(`dfxisp`)에서의 로컬 검증 (2026-09-03):**

위 체크리스트는 원본 레포(`haengmini/dfxisp`)의 SPEC.md가 기록한 값이고, 이 워크스페이스에는 `NormalISP.cpp`/`.hpp`만 정적으로 옮겨져 있어 HLS 프로젝트 자체가 없었다. 이번 브링업에서 `vitis-run --mode hls --csim`으로 이 저장소 최초의 C-sim을 실행했다.

- ✅ **C-sim 구조적 sanity 통과** — `NormalISP_tb.cpp`(§C-sim 테스트벤치), 7개 체크 전부 PASS. **주의: bit-exact golden 비교가 아니다** — `tools/gen_default_isp_golden.py`(원본 레포)가 이 저장소엔 없어서 만든 대체 테스트다. bit-exact 검증은 여전히 미실시.
- ✅ **csynth 실측** (`NormalISP_hls/NormalISP/hls/syn/report/NormalISP_csynth.rpt`): 타이밍 target 4.00ns/estimated 2.920ns 통과, LUT 12,812(5%) / FF 9,518(2%) / DSP 28(1%) / BRAM 4(~0%). **메인 픽셀 루프 II=9** (목표 1) — 3×3 demosaic 윈도우가 픽셀당 `m_axi_gmem0`을 9회 개별 읽어(라인버퍼 캐싱 없음) 발생, 최대 트립카운트(1920×1080) 기준 latency 추정 ≈82.9ms/frame. 1280×720 목표로 비례 환산 시 ≈37ms/frame으로 30fps(33.3ms) 예산 초과 가능성 — §구현 메모의 "같은 픽셀 최대 9번 재계산" 트레이드오프가 실측 병목으로 확인된 사례. 최적화는 별도 결정 사항.
- ✅ **Vivado post-route 실측** (`NormalISP_zcu104.runs/impl_1/`, 2026-09-03): 100MHz(`clk_pl_0`)에서 WNS +4.301ns / WHS +0.010ns, 전체 제약 통과. DRC critical warning 0(warning 34건은 전부 DSP pipelining 권고 등 비차단), methodology DRC 3건. 전체 설계(PL 전체) 자원: CLB LUT 5,782(2.51%), CLB Register 8,573(1.86%), CARRY8 333(1.16%) — csynth 단독 추정치보다 낮은 건 Vivado synth+opt의 추가 최적화 결과로 정상.
- ✅ **Export Hardware 완료** — `NormalISP_zcu104/NormalISP_zcu104_design1_wrapper.xsa`(1.25MB), bitstream 포함 확인(`NormalISP_zcu104_design1_wrapper.bit` 내장, `unzip -l`로 확인). §4 PetaLinux 임포트로 진행 가능한 상태.
- ✅ **PetaLinux 임포트 + 보드 실물 부팅/UIO 검증 완료 (2026-09-04)** — static 브링업 전 과정(§4~§9) 실행, 실제 카메라 RAW 10장을 ZCU104 보드에서 `NormalISP` 하드웨어로 처리해 육안 확인까지 마침. 상세는 아래 "**PetaLinux 임포트 + 보드 실물 검증 (2026-09-04)**" 및 §4~§9 각 절의 실측 노트 참고.

**PetaLinux 임포트 + 보드 실물 검증 (2026-09-04):**

§4~§9를 순서대로 실행해 `NormalISP`를 ZCU104에 static으로 올리고, 실제 PASCALRAW(NEF)/SonyNOD(ARW) 원본 사진 10장(PASCAL 5 + LOD 5, `dataset/test/`)을 하드웨어로 처리했다. 원래 계획했던 절차 대비 실제로 달랐던 점들:

- **디바이스트리 노드 라벨이 예상과 다름** — §4가 예상한 `normalisp_0`(소문자)가 아니라 **`NormalISP_0`**(Vivado IP 인스턴스 이름 대소문자 그대로 보존)로 자동 생성됨. `system-user.dtsi`의 오버레이 타깃을 `&NormalISP_0`로 정정해야 UIO 노드가 실제로 붙는다 — §4 하단 정정 참고.
- **`CONFIG_UIO_PDRV_GENIRQ`가 인터랙티브 메뉴 선택만으로는 `=y`로 안 박힘** — §6에서 서술한 대로 `bsp.cfg`에 명시적으로 넣고 `kernel -x cleansstate` 후 재빌드해야 확정됨.
- **PetaLinux sstate 미러(`petalinux.xilinx.com`)가 죽어있음** — AMD 통합 이후 `https://edf.amd.com/`(인증 필요)으로 307 리다이렉트되어 매 빌드마다 타임아웃 에러(무해하지만 종료 코드는 비정상)가 남. `project-spec/meta-user/conf/petalinuxbsp.conf`에 `SSTATE_MIRRORS = ""` 추가로 해결 — §8 참고.
- **SD카드에 새로 쓴 파일이 `sync`만으로는 안 끝남** — 보드에서 SD카드로 결과 파일을 옮긴 뒤 `sync`만 하고 뽑으면 최초 1회는 반드시 0바이트로 깨짐(파일명이 새로 생성되는 경우 재현됨). `umount` 후 뽑아야 확실히 flush됨 — §8/§9 참고.
- **레지스터 맵(§2)은 실측과 100% 일치** — 8단계 호출 시퀀스, 오프셋 전부 별도 수정 없이 그대로 동작.

**실행 결과 (100MHz `pl_clk0`, 실측):**

| 해상도 | 지연시간(ap_start~ap_done) | 비고 |
|---|---|---|
| 602×400 (PASCAL, NEF) | 142.2ms | 전체 화각 유지 다운샘플(§7-1 참고), K=10 |
| 610×408 (LOD, ARW) | 147.0ms | 14bit→12bit 리스케일 포함, K=9 |
| 640×480 (초기 테스트, 중앙 크롭) | 181.4ms | 이후 폐기 — 화각이 너무 좁아 크롭 방식에서 전체화각 유지 다운샘플로 전환 |

같은 해상도의 모든 프레임이 지연시간까지 소수점 둘째자리까지 동일 — HLS 루프가 `width×height`로만 반복 횟수가 정해지는 고정 지연 파이프라인이라(§구현 메모 II=9) 데이터 의존적 타이밍 변동이 없다는 뜻으로, 정상이다.

10/10 프레임 전부 `out_width`/`out_height` 일치, `0x00RRGGBB` 포맷(상위 바이트 0) 정확, RGB 결과를 PNG로 변환해 육안으로 확인 — 건물/나무/사람/자전거 등 실제 장면이 뚜렷하게 재현됨(PASCAL은 밝고 선명, LOD는 노출보정이 없어 어둡고 노이즈 있음, 둘 다 예상대로).

## 보드 실장 가이드: Vitis HLS → Vivado → PetaLinux → ZCU104

`JNU_Lab_Petalinux`(`haengmini/JNU_Lab_Petalinux`) 레포의 튜토리얼(`docs/PetaLinux_tutorial_Note.md`, 원작 [vandinhtranengg/Xilinx-PetaLinux-Based-FPGA-Acceleration-Design-Tutorial](https://github.com/vandinhtranengg/Xilinx-PetaLinux-Based-FPGA-Acceleration-Design-Tutorial/))이 16×16 행렬곱셈(`mmult`) IP로 이미 실증한 **PetaLinux 통합 워크플로우**를, `NormalISP` 하나만 static 배치(DFX 없이)하는 첫 브링업에 그대로 옮긴 것이다. 이 워크플로우 자체는 mmult든 NormalISP든 CNN 가속기든 동일하게 적용된다 — mmult 튜토리얼이 이미 검증해 둔 부분이다.

> **범위:** 이 섹션은 default_isp만 정적으로(재구성 없이) 보드에 올리는 첫 단계를 다룬다. DFX(`LowlightISP`로의 런타임 스왑, `checker`의 static-region 배치)는 이 static 브링업이 성공한 뒤의 별도 단계다 — SPEC.md Arm1(정적 baseline)에 해당.

### 0. 툴체인/버전

| 구성 요소 | 버전 |
|---|---|
| Vivado / Vitis HLS / PetaLinux | 2024.1 (셋 다 반드시 동일 버전 — 다른 조합은 XSA/BSP 호환 실패) |
| ZCU104 BSP | `xilinx-zcu104-v2024.1-*.bsp` |
| 대상 보드 | ZCU104 Rev C, `xczu7ev-ffvc1156-2-e` |
| 호스트 OS | 네이티브 Ubuntu 24.04 LTS 권장 (WSL 아님 — Vivado/Vitis HLS/PetaLinux를 한 머신에 전부 설치하면 파일 복사가 `cp` 한 줄로 끝남) |

PetaLinux 설치·BSP 준비·SD카드 부팅 검증(2장)은 `NormalISP` 전용 내용이 없으므로 원본 튜토리얼 그대로 따라가면 된다. 아래는 3장(가속기 설계)부터 `NormalISP`에 맞춰 옮긴 것.

### 1. Vitis HLS — IP 빌드 및 검증

이 저장소에서는 2024.1 통합 IDE의 `vitis-run --mode hls` component 플로우로 검증했다(구 GUI/`vitis_hls -f <tcl>` 플로우도 동일하게 동작해야 한다):

```bash
vitis-run --mode hls --csim \
  --config /home/mini/Desktop/dfxisp/NormalISP/NormalISP_hls/hls_config.cfg \
  --work_dir NormalISP
```

`hls_config.cfg` (실제 사용, `NormalISP_hls/hls_config.cfg`):

```ini
part=xczu7ev-ffvc1156-2-e

[hls]
flow_target=vivado
package.output.format=ip_catalog
package.output.syn=false
syn.top=NormalISP
syn.file=/home/mini/Desktop/dfxisp/NormalISP/NormalISP.cpp
tb.file=/home/mini/Desktop/dfxisp/NormalISP/NormalISP.hpp
tb.file=/home/mini/Desktop/dfxisp/NormalISP/NormalISP_tb.cpp
clock=4ns
csim.code_analyzer=1
```

- **Top function은 `NormalISP`** (AWB 고정 ON, 6-인자 보드용 top). `NormalISP_dev`는 ablation용이라 `syn.top`/IP export 대상이 아니다.
- **합성 클럭 목표는 4ns(250MHz)** — §3의 `pl_clk0` 여유 계산(100MHz로 시작)은 이 값 기준으로도 여전히 유효(250MHz보다 훨씬 낮음).
- `.hpp`는 `tb.file`(Test Bench Sources)로 등록되어 있다 — 이유는 헤더에 합성 대상 함수 바디가 없고(선언뿐), Design Sources 목록은 Top Function 후보를 스캔하는 데 쓰이는데 헤더의 `extern "C"` 선언까지 걸리면 `.cpp`의 실제 정의와 중복 표시되는 걸 피하기 위함(관례, 필수 아님).
- 순서: C Simulation(PASS 확인, §C-sim 테스트벤치 참고) → C Synthesis → (선택) C/RTL Co-simulation → **Export RTL → Vivado IP 패키징**.
- **주의(이 프로젝트 실제 사례):** 원본 레포(`JNU_DFXISP_FPGA/README.md`)에 기록된 알려진 버그 — 중첩된 프로젝트 경로에서 `add_files`로 추가한 소스가 누락되어 `undefined symbol: dfxisp_accel` 같은 링크 에러가 난다. 위 `vitis-run` component 플로우로는 **flat 디렉토리 우회 없이(`NormalISP/` 그대로) C-sim이 정상 통과**했지만, 이 버그는 원래 csynth/Export RTL 단계에서 보고된 것이라 아직 재현 여부가 확인된 게 아니다 — 그 단계에서 동일한 링크 에러가 나면 `NormalISP.cpp`/`.hpp`/`NormalISP_tb.cpp`를 `/tmp/hls_normalisp/` 같은 flat 디렉토리로 옮겨서 재시도할 것.
- Export RTL로 생성되는 IP 이름은 top 함수명 기준(`NormalISP_v1_0` 형태)이므로, Vivado IP 카탈로그에서 `NormalISP`로 검색하면 나온다.

### 1-1. C-sim 테스트벤치 (`NormalISP_tb.cpp`)

이 저장소엔 원본 레포의 Python golden generator(`tools/gen_default_isp_golden.py`, 528px 10케이스: flat/gradient/color-cast/saturated/odd/1×1)가 없어서, `NormalISP_tb.cpp`는 **bit-exact golden 비교가 아니라 구조적/논리적 sanity check**다. `main()`은 Vitis HLS C-sim 관례대로 전부 통과 시 `0`, 하나라도 실패하면 `1`을 반환한다. 7개 체크:

| # | 케이스 | 확인 내용 |
|---|---|---|
| 1 | 형상/포맷 | 9×7, 1×1, 2×2, 64×48에서 `out_width/out_height`가 입력과 같고, 모든 픽셀이 `0x00RRGGBB`(상위 바이트 0) 범위인지 |
| 2 | 가드 입력 | `raw_bayer`/`rgb_out`이 `nullptr`이거나 `width<=0`일 때 `out_width/out_height`가 0으로 클리어되는지 |
| 3 | flat 프레임 균일성 | 균일한 색의 Bayer 프레임이 demosaic 후 공간적으로 동일한지 — **내부 픽셀만**(최외곽 1픽셀 링 제외, 아래 캐비앗 참고) |
| 4 | 그라디언트 단조성 | green 채널 램프 입력이 파이프라인 통과 후에도 비감소인지 (인접 x가 아닌 성긴 샘플로 확인, 반올림 노이즈 회피) |
| 5 | 포화 클램프 | 12-bit 만포화(4095) 입력이 `[0,255]`를 벗어나지 않고, CCM row-sum=256 성질대로 거의 무채색을 유지하는지 |
| 6 | AWB 방향성 | 강한 color-cast 입력에서 AWB ON이 OFF보다 내부 픽셀의 `\|R-G\|` 격차를 줄이는지 |
| 7 | 보드 top 일치 | `NormalISP()` 출력이 `NormalISP_dev(..., NORMAL_ISP_AWB_ON, ...)`과 bit-for-bit 동일한지 |

**케이스 3·6이 경계가 아닌 내부 픽셀을 쓰는 이유:** `corrected_bayer()`의 index clamp가 Bayer parity를 보존하지 않아 최외곽 1픽셀 링은 flat scene에서도 내부와 다른 값을 낸다(§구현 메모의 "경계 픽셀은 Bayer parity를 보존하지 않는다" 참고) — 처음엔 경계 포함 전체 균일성을 체크했다가 이 특성 때문에 FAIL이 나서, 원인을 손계산으로 확인한 뒤 내부 픽셀 기준으로 고쳤다.

**2026-09-03 결과:** 7개 전부 PASS (`vitis-run --mode hls --csim`, Code Analyzer 모드).

이 sanity check를 통과했다고 해서 mAP/색 정확도 주장의 근거가 되진 않는다 — bit-exact golden 비교는 여전히 원본 레포의 generator가 필요하다.

### 2. AXI-Lite 레지스터 맵 — csynth 실측으로 확정 (2026-09-03)

이 저장소에서 csynth를 돌려 생성된 실제 드라이버 헤더(`NormalISP_hls/NormalISP/hls/impl/misc/drivers/NormalISP_v1_0/src/xnormalisp_hw.h`)로 확정한 맵이다. 이전 버전의 이 절이 예상했던 "포인터는 8바이트, 스칼라는 각자 슬롯" 규칙은 맞았고, 아래처럼 세부가 확정됐다:

| 오프셋 | 레지스터 | 설명 |
|---|---|---|
| `0x00` | `AP_CTRL` | bit0 `ap_start`(R/W/COH) / bit1 `ap_done`(R/COR) / bit2 `ap_idle`(R) / bit3 `ap_ready`(R/COR) / **bit7 `auto_restart`(R/W)** / **bit9 `interrupt`(R)** |
| `0x04` | `GIE` | Global Interrupt Enable, bit0 |
| `0x08` | `IER` | IP Interrupt Enable — bit0 `ap_done` 인터럽트, bit1 `ap_ready` 인터럽트 |
| `0x0c` | `ISR` | IP Interrupt Status (R/TOW) |
| `0x10` / `0x14` | `raw_bayer` 하위32 / 상위32 | m_axi 포인터 물리주소 (R/W) |
| `0x1c` / `0x20` | `rgb_out` 하위32 / 상위32 | m_axi 포인터 물리주소 (R/W) |
| `0x28` | `width` | 입력 스칼라 (R/W) |
| `0x30` | `height` | 입력 스칼라 (R/W) |
| `0x38` | `out_width` data | 출력 스칼라 (R) |
| `0x3c` | `out_width` ctrl | bit0 `ap_vld`(R/COR) — read-back 전에 이 비트로 유효성 확인 |
| `0x48` | `out_height` data | 출력 스칼라 (R) |
| `0x4c` | `out_height` ctrl | bit0 `ap_vld`(R/COR) — read-back 전에 이 비트로 유효성 확인 |

(SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake — 헤더 원문 표기 그대로)

**입력 스칼라(`width`/`height`)와 출력 스칼라(`out_width`/`out_height`)의 슬롯 구성이 다르다:** `width`/`height`는 데이터 슬롯 하나만 쓰지만(값을 그대로 write), `out_width`/`out_height`는 `int*` write-back 인자라서 **데이터 슬롯 + `ap_vld` 컨트롤 슬롯 2개**를 쓴다. 유저스페이스 드라이버는 `out_width`/`out_height`를 읽기 전에 각각 `0x3c`/`0x4c`의 bit0(`ap_vld`)이 1인지 먼저 확인할 것 — §7의 8단계 호출 시퀀스에 이 확인을 추가해야 한다.

**`auto_restart`(bit7)/`interrupt`(bit9)는 §7 예시엔 없던 기능이다:** `AP_CTRL`에 `auto_restart=1`을 쓰면 `ap_done` 직후 자동으로 다음 `ap_start`가 걸려 폴링/재기동 없이 연속 프레임을 처리할 수 있다 — 정적 단일 프레임 브링업(현재 범위)에는 불필요하지만, 나중에 스트리밍/연속 처리로 전환할 때 폴링 오버헤드를 없애는 옵션으로 참고. `interrupt`(bit9)는 `GIE`/`IER`/`ISR`(0x04/0x08/0x0c)를 함께 설정해야 실제로 `pl_ps_irq0`까지 신호가 전달된다(§3 인터럽트 경로, 현재는 배선만 해두고 폴링 사용 권장과 동일한 맥락).

### 3. Vivado 하드웨어 통합

**제어 경로:** `PS (ARM Cortex-A53) → M_AXI_HPM0_FPD → AXI Interconnect → NormalISP_0/s_axi_control`

**데이터 경로 — mmult 튜토리얼과의 차이:** mmult는 `m_axi_gmem` 하나뿐이지만 `NormalISP`는 **`m_axi_gmem0`(raw_bayer 읽기)와 `m_axi_gmem1`(rgb_out 쓰기) 두 개의 AXI Master**를 갖는다. 둘 다 `S_AXI_HP0_FPD`(또는 서로 다른 HP 포트, 대역폭에 여유를 두려면 HP0/HP1로 분리) 앞의 AXI SmartConnect에 물린다.

```
NormalISP_0/m_axi_gmem0 (raw_bayer, read) ─┐
                                            ├─ AXI SmartConnect ─ S_AXI_HP0_FPD ─ PS DDR4
NormalISP_0/m_axi_gmem1 (rgb_out, write) ──┘
```

- 대역폭이 걱정되면(§구현 메모 — AWB가 raw를 두 번 읽는다는 점 참고) `gmem0`은 `HP0`, `gmem1`은 `HP1`로 분리해서 read/write가 서로 경합하지 않게 할 수 있다. 첫 브링업(기능 검증 목적)에서는 SmartConnect로 합쳐도 무방 — 성능 튜닝은 기능이 확인된 뒤.
- **클럭/리셋:** `pl_clk0`(예: 100MHz로 시작 — HLS 합성 타깃 4ns/250MHz(§1 `hls_config.cfg` 실측)보다 낮게 잡으면 타이밍 여유가 커서 첫 브링업에 안전) → `NormalISP_0/ap_clk`, Interconnect/SmartConnect 클럭, `proc_sys_reset_0/slowest_sync_clk`.
- **인터럽트(선택):** `NormalISP_0/interrupt → xlconcat → pl_ps_irq0`. 첫 브링업은 폴링으로 충분(§5 참고) — 배선만 미리 해두고 나중에 인터럽트 구동으로 전환 가능.

**Zynq UltraScale+ MPSoC PS IP 재구성(Re-customize IP) — 확인/추가할 항목:**

튜토리얼(mmult 예제)은 이 부분을 "선행 MemCopy 가이드에서 이미 다룬 내용"이라며 세부 체크박스 절차 없이 요약만 하고 지나간다 — 아래는 튜토리얼이 명시한 요구사항(어떤 인터페이스가 연결돼야 하는지)을 표준 Vivado Zynq PS 커스터마이징 다이얼로그에 대입한 것이다:

| 탭 | 항목 | 설정 | 이유 |
|---|---|---|---|
| PS-PL Configuration → Master Interface | `AXI HPM0 FPD` | Enable | 제어경로: `M_AXI_HPM0_FPD → s_axi_control` |
| PS-PL Configuration → Slave Interface | `AXI HP0 FPD` | Enable | 데이터경로: `gmem0`(raw_bayer read) 최소 하나는 필요 |
| PS-PL Configuration → Slave Interface | `AXI HP1 FPD` | **NormalISP 전용 추가 항목** — HP0/HP1 분리 시 Enable | `gmem0`/`gmem1`을 별도 HP 포트로 분리하려면 여기서 HP1도 켜야 함(위 대역폭 분리 옵션 참고). 합쳐 쓰면 HP0만으로 충분 |
| Clock Configuration → PL Fabric Clocks | `PL0` | 100 MHz | `pl_clk0` |
| Interrupts → PL-PS Interrupts | `IRQ0 [0:0]` | Enable (배선만, 첫 브링업은 폴링 사용) | `interrupt → xlconcat → pl_ps_irq0`, §2에서 확인한 `GIE`/`IER`/`ISR`/bit9 인터럽트 기능을 나중에 쓰려면 여기가 열려 있어야 함 |

mmult 튜토리얼(마스터 1개)은 `AXI HP0 FPD` 하나만 켜면 끝나지만, `NormalISP`는 마스터가 2개(`gmem0`/`gmem1`)라서 **HP1 FPD 활성화 여부를 결정하는 게 이 프로젝트에서 추가로 필요한 판단**이다.

(참고: `gmem0`은 csynth 인터페이스 리포트 기준 16-bit read-only, `gmem1`은 32-bit write-only로 합성됐다 — HP 포트 네이티브 폭과 다르지만 AXI SmartConnect가 자동으로 폭 변환하므로 PS IP 쪽 설정 항목은 아니다.)

**주소 할당(Address Editor):**

| 인터페이스 | 예시 Base | Range | 비고 |
|---|---|---|---|
| `NormalISP_0/s_axi_control` | `0xA000_0000` | 64 KiB | mmult 튜토리얼과 같은 관례. 이후 `checker`/`LowlightISP` IP를 추가할 계획이면 `0xA001_0000`, `0xA002_0000`처럼 64KiB 간격으로 미리 비워둘 것 |
| `NormalISP_0/m_axi_gmem0`, `m_axi_gmem1` | (자동) | PS DDR 전체 | HP 포트 통해 자동 매핑, 수동 설정 불필요 |

**Validate Design → Create HDL Wrapper → Run Synthesis & Implementation → Generate Bitstream → File → Export → Export Hardware (Include bitstream 체크)** 순서로 XSA를 내보낸다.

### 4. PetaLinux — 하드웨어 임포트 및 디바이스 트리

```bash
mkdir -p ~/project/normalisp_hw
cp /home/mini/Desktop/dfxisp/NormalISP/NormalISP_zcu104/NormalISP_zcu104_design1_wrapper.xsa ~/project/normalisp_hw/
source ~/petalinux/2024.1/settings.sh
cd ~/project/xilinx-zcu104-2024.1
petalinux-config --get-hw-description=~/project/normalisp_hw/
```

(2026-09-03 실측 경로/파일명. bitstream 포함 확인됨 — 검증 상태 참고.)

- `DTG Settings`에서 `MACHINE_NAME`은 **`(AUTO)` 그대로 둘 것** (ZCU104 BSP 기반 프로젝트라 임의로 바꾸면 보드 설정이 깨짐).
- `Remove PL from devicetree`는 **반드시 비활성화** — 안 그러면 NormalISP 노드가 디바이스 트리에서 통째로 빠진다.
- 검증:

```bash
petalinux-build -c device-tree
grep -Rni -A15 -B3 "normalisp" components/plnx_workspace/device-tree/
```

자동 생성된 노드가 대략 이런 모양이어야 한다(주소는 §3에서 정한 값과 일치해야 함):

```dts
normalisp_0: normalisp@a0000000 {
    compatible = "xlnx,normalisp-1.0";
    reg = <0x0 0xa0000000 0x0 0x10000>;
    ...
};
```

**실측 정정 (2026-09-04):** 실제로 생성되는 라벨/compatible 문자열은 **대소문자가 그대로 보존**되어 위 예시와 다르다 — Vivado IP 인스턴스 이름(`NormalISP_0`)을 그대로 따라간다:

```dts
NormalISP_0: NormalISP@a0000000 {
    compatible = "xlnx,NormalISP-1.0";
    reg = <0x0 0xa0000000 0x0 0x10000>;
    ...
};
```

§5의 `system-user.dtsi` 오버레이는 `&normalisp_0`가 아니라 **`&NormalISP_0`**를 타깃으로 해야 한다 — 소문자로 쓰면 오버레이가 조용히 무시되고 UIO 노드가 안 만들어진다(디바이스트리 컴파일 자체는 에러 없이 성공하므로 발견하기 어려움, `petalinux-build -c device-tree` 후 최종 `images/linux/system.dtb`를 `dtc -I dtb -O dts`로 디컴파일해서 직접 확인할 것 — 중간 생성물 `components/plnx_workspace/device-tree/`가 아니라 최종 산출물을 봐야 함).

- 새 XSA를 재임포트할 때 빌드 실패(`Failed to generate bsp ...`)가 나면 `petalinux-build -x mrproper` 후 다시 `--get-hw-description`부터.

### 5. UIO 구성 + DDR 버퍼 예약

`system-user.dtsi`(`project-spec/meta-user/recipes-bsp/device-tree/files/system-user.dtsi`)에 mmult 튜토리얼과 동일한 3가지 기능을 반영한다:

```dts
/include/ "system-conf.dtsi"
/ {
    reserved-memory {
        #address-cells = <2>;
        #size-cells = <2>;
        ranges;

        normalisp_reserved: buffer@70000000 {
            no-map;
            reg = <0x0 0x70000000 0x0 0x00800000>;   /* 8 MiB, 아래 §버퍼 레이아웃 참고 */
        };
    };

    normalisp_buffer: normalisp-buffer@70000000 {
        compatible = "generic-uio";
        linux,uio-name = "normalisp-buffer";
        reg = <0x0 0x70000000 0x0 0x00800000>;
    };
};

&NormalISP_0 {
    compatible = "generic-uio";
    linux,uio-name = "normalisp-control";
};
```

(라벨 대소문자는 §4의 실측 정정 참고 — `&normalisp_0`가 아니라 `&NormalISP_0`.)

**왜 예약 DDR이 필요한가:** `malloc()`이 주는 건 가상 주소이고, `NormalISP`의 `m_axi` 포트는 MMU를 거치지 않고 AXI 버스에 물리 주소를 직접 올린다. 커널이 예약하지 않은 영역은 다른 프로세스/힙/캐시가 언제든 가져다 쓸 수 있어 FPGA가 그 위에 쓰는 순간 커널 메모리 오염·크래시로 이어진다.

**버퍼 레이아웃 (8 MiB 예약, 1280×720 기준 여유 있게):**

SPEC.md가 명시한 HW 프레임 예산 목표(1280×720@30fps)를 기준으로 잡으면:

```
raw_bayer : 1280×720×2 bytes(uint16) = 1,843,200 B ≈ 1.76 MiB  → 2 MiB 슬롯에 배치
rgb_out   : 1280×720×4 bytes(uint32) = 3,686,400 B ≈ 3.52 MiB → 4 MiB 슬롯에 배치
```

```text
예약된 물리 DDR (8 MiB, 0x70000000 ~ 0x707FFFFF)
0x70000000  +----------------------------+  raw_bayer 슬롯 (2 MiB)
0x70200000  +----------------------------+  rgb_out 슬롯 (4 MiB)
0x70600000  +----------------------------+  미사용 예약 (확장용, 2 MiB)
0x707FFFFF  +----------------------------+
```

**첫 브링업은 이보다 훨씬 작은 해상도로 시작할 것을 권장한다** (§7 참고) — 640×480이면 raw 600 KiB / rgb 1.2 MiB로 여유가 커서 오프셋 계산 실수의 여파가 작다. 위 8 MiB 레이아웃은 1280×720까지 그대로 커버하므로 해상도를 나중에 키워도 재설계가 필요 없다.

**실측 (2026-09-04):** 실제 테스트 이미지는 정확히 640×480은 아니고 이미지마다 조금씩 다른데(PASCAL 602×400, LOD 610×408 — §7-1 참고), 전부 이 슬롯 예산 안에 여유롭게 들어간다(raw 최대 ≈500 KiB, rgb 최대 ≈1MB, 2MiB/4MiB 슬롯 대비 충분).

**제어 vs 데이터 공간 비교:**

| 항목 | 제어 공간 (`normalisp-control`) | 데이터 공간 (`normalisp-buffer`) |
|---|---|---|
| 물리 주소 | `0xA000_0000` | `0x7000_0000` |
| 크기 | 64 KiB | 8 MiB |
| 인터페이스 | AXI4-Lite (`s_axi_control`) | PS DDR4 (via `m_axi_gmem0`/`gmem1`) |
| 역할 | AP_CTRL, 포인터 주소, width/height, out_width/out_height read-back | raw_bayer 입력 / rgb_out 출력 |

### 6. Generic UIO 커널 활성화 + rootfs

mmult 튜토리얼 10~11장과 완전히 동일 — `NormalISP` 전용 특이사항 없음.

```bash
petalinux-config -c kernel
# Device Drivers ---> Userspace I/O drivers ---> <*> Userspace I/O platform driver with generic IRQ handling
# (모듈 [M] 아닌 빌트인 [*]로)

petalinux-build -c kernel
grep -E '^CONFIG_UIO=|^CONFIG_UIO_PDRV_GENIRQ=' build/tmp/work-shared/xilinx-zcu104/kernel-build-artifacts/.config
# 둘 다 =y 인지 확인. =m 이면 project-spec/meta-user/recipes-kernel/linux/linux-xlnx/bsp.cfg 에
# CONFIG_UIO=y / CONFIG_UIO_PDRV_GENIRQ=y 추가 후 kernel -x cleansstate && kernel 재빌드.
```

**실측 (2026-09-04):** 이 프로젝트에서 실제로 `=m`이 나왔다 — 메뉴에서 `<*>`를 선택하고 저장해도(인터랙티브 메뉴 조각이 `project-spec/meta-user/recipes-kernel/linux/linux-xlnx/user_*.cfg`에 `CONFIG_UIO_PDRV_GENIRQ=y`로 정확히 저장됐는데도) 최종 빌드된 `.config`에는 `=m`으로 남아 있었다. `bsp.cfg`(빈 파일 상태였음)에 아래 두 줄을 직접 써넣고,

```ini
CONFIG_UIO=y
CONFIG_UIO_PDRV_GENIRQ=y
```

`petalinux-build -c kernel -x cleansstate && petalinux-build -c kernel`로 재빌드하니 둘 다 `=y`로 확정됐다 — 인터랙티브 메뉴 조각보다 `bsp.cfg`(정식 레시피 config 조각)가 더 확실하다.

```bash
petalinux-config
# DTG Settings ---> Kernel Bootargs ---> generate boot args automatically 체크 해제
# User Set Kernel Bootargs 에 추가:
#   earlycon console=ttyPS0,115200 clk_ignore_unused init_fatal_sh=1 uio_pdrv_genirq.of_id=generic-uio

petalinux-config
# Image Packaging Configuration ---> INITRAMFS/INITRD Image name -> petalinux-image-minimal
petalinux-config -c rootfs
# Image Features ---> [*] auto-login (개발 편의)
```

### 7. 유저스페이스 앱 — mmult 패턴을 NormalISP로 이식

mmult 튜토리얼의 8단계 호출 시퀀스를 그대로 따르되, 인자를 `NormalISP`에 맞춘다:

```text
1. /sys/class/uio/uio*/name 검색 → "normalisp-control" / "normalisp-buffer" 탐색
2. 두 UIO open() 후 mmap() — control은 64 KiB, buffer는 8 MiB
3. buffer 오프셋 0x000000에 RAW 테스트 프레임(raw_bayer, RGGB uint16) 기록
4. control 레지스터에 raw_bayer 물리주소(0x70000000, 0x10/0x14), rgb_out 물리주소(0x70200000, 0x1c/0x20) 프로그램
5. control 레지스터에 width(0x28), height(0x30) 프로그램
6. AP_CTRL(0x00)의 AP_START 비트(bit0) 세트
7. AP_CTRL(0x00)의 AP_DONE 비트(bit1) 폴링 대기
8. out_width(0x38)/out_height(0x48)의 ap_vld 컨트롤 비트(각각 0x3c/0x4c bit0)가 1인지 먼저 확인한 뒤 데이터 read-back, buffer 오프셋 0x200000에서 rgb_out 판독
```

(오프셋은 §2에서 실측 확정한 값. `AP_CTRL`의 `auto_restart`/`interrupt` 비트는 이 정적 단일 프레임 시퀀스에선 쓰지 않음 — §2 참고.)

**권장 첫 테스트 프레임 (원안):** 실제 PASCALRAW/SonyNOD 원본 이미지보다, `NormalISP.cpp`가 bit-exact를 주장하는 Python golden(`tools/gen_default_isp_golden.py`, 원본 레포)의 **10개 합성 테스트 케이스**(flat/gradient/color-cast/saturated/odd/1×1, 528px) 중 작은 것 하나를 먼저 태워서 **C-sim/csynth 결과와 보드 출력이 일치하는지**부터 확인할 것 — mmult 튜토리얼의 `Result check: PASSED`에 해당하는, 이 프로젝트만의 정확성 검증 포인트다.

**실제로는 (2026-09-04):** 이 저장소엔 그 golden generator가 없어서(§검증 상태 참고), 합성 케이스 단계를 건너뛰고 바로 `dataset/test/`의 실제 PASCALRAW(NEF)/SonyNOD(ARW) 원본 10장으로 진행했다 — 결과적으로 문제없이 통과했지만, bit-exact golden 대비 검증은 여전히 안 된 상태라는 점은 유의(§C-sim 테스트벤치와 동일한 한계). §7-1에 실제 사용한 이미지 규격/변환 파이프라인을 정리한다.

**C++ vs Python:** 첫 브링업/디버깅은 Python(`mmap`+`struct`, 크로스컴파일 불필요, 코드 수정 후 즉시 재실행)으로 빠르게 돌리고, 반복 가능한 벤치마크/최종 검증은 C++(`petalinux-create -t apps --template c++ -n normalisp-app --enable`)로 굳히는 mmult 튜토리얼의 권장 순서를 그대로 따르면 된다. **실제로는 Python으로 충분히 끝냈다** — `petalinux-image-minimal`에 `python3`(3.10.6)이 이미 포함되어 있었고, C++ 포팅은 하지 않음.

### 7-1. 실제 사용한 이미지 규격 + 변환 파이프라인 (2026-09-04)

**호스트 측 변환 (`tools/raw_to_bayer_bin.py`):** `dataset/test/{PASCAL,LOD}/raw/*.{nef,ARW}` 원본을 `rawpy`/`libraw`로 읽어 `NormalISP`가 기대하는 순수 12-bit RGGB Bayer `.bin`(헤더 없는 uint16 배열, row-major)으로 변환한다.

- **크롭이 아니라 전체 화각을 보존하는 다운샘플링을 쓴다** — 처음엔 640×480 중앙 크롭으로 시작했으나(§4 이미지 원본 해상도가 6000×4000급이라 크롭하면 화면의 극히 일부만 확대되어 잡힘, 실제 사진처럼 안 보임) 이후 폐기했다. 현재 방식: Bayer를 4개 동색 평면(R/Gr/Gb/B)으로 분리 → 평면별로 정수 배율 `K`만큼 블록 평균(binning) → 다시 RGGB로 인터리빙. Bayer 위상이 절대 깨지지 않고, 평균화 덕에 노이즈도 줄어든다.
- `K`는 `--max-width`/`--max-height`(기본 640×480) 박스 안에 들어오는 최소 정수로 자동 계산 — 실제 출력 크기는 원본 센서 해상도에 따라 이미지마다 달라지므로 **파일명에 실측 W×H를 그대로 박아 넣는다**(`{원본이름}_raw12_{W}x{H}.bin`).
- Sony ARW(14-bit, `black_level=800`, `white_level=16380`)는 12-bit로 리스케일; Nikon NEF는 이미 12-bit 네이티브(`black=0, white=4095`)라 리스케일 없이 그대로 씀.
- 실제 결과: **PASCAL(NEF) 6034×4012 → 602×400 (K=10)**, **LOD(ARW) 5496×3672 → 610×408 (K=9)**. 둘 다 §5 버퍼 슬롯(raw 2MiB/rgb 4MiB) 예산에 여유 있게 들어간다.

**변환 산출물 위치:** `dataset/test/bayer/{PASCAL,LOD}/*.bin` — SD카드에 그대로 복사해서 보드로 옮긴다.

**보드 측 테스트 앱 (`board_test/`):**

| 파일 | 역할 |
|---|---|
| `board_test/normalisp_uio_test.py` | §7의 8단계 시퀀스를 구현한 단일 프레임 실행기. `run_one(raw_path, width, height, out_dir)`로 임포트 가능하게 리팩터링되어 있어 배치 스크립트가 재사용한다. |
| `board_test/run_all_bayer.py` | `bayer/PASCAL`, `bayer/LOD`를 전부 순회하며 `run_one()`을 호출, 파일명에서 실제 W×H를 파싱(정규식 `_(\d+)x(\d+)\.bin$`), PASS/FAIL 요약 테이블 출력. |

```bash
# 보드에서
cd /path/to/board_test
python3 run_all_bayer.py [BAYER_ROOT=/run/media/mmcblk0p1/bayer] [OUT_DIR=/root/normalisp_out]
```

`/root`는 initrd/ramdisk 기반 rootfs라 전원을 끄면 사라진다 — 결과는 반드시 SD카드로 옮긴 뒤(`umount` 필수, 아래 §8/§9 참고) 호스트로 가져올 것.

**호스트 측 결과 시각화 (`tools/rgb888_to_png.py`):** 보드가 만든 `0x00RRGGBB` packed uint32 결과(`*_rgb888.bin`, 파일명에서 W×H 파싱)를 PNG로 변환해 눈으로 확인한다.

```bash
python3 tools/rgb888_to_png.py board_test/normalisp_out board_test/normalisp_out_png
```

**결과:** 10/10 PASS, 실제 사진(건물/나무/사람/자전거 등)이 뚜렷하게 재현됨 — PASCAL은 밝고 선명, LOD는 노출보정 없이도 인식 가능한 수준(예상대로 어둡고 노이즈 있음).

### 8. 빌드 → 패키징 → SD카드

| 수정한 것 | 재생성 대상 |
|---|---|
| 유저스페이스 앱, `system-user.dtsi`, 커널/UIO 설정, bootargs | `image.ub`만 |
| Vivado 블록 디자인/비트스트림, 새 XSA 임포트 | `BOOT.BIN` + `image.ub` 둘 다 |

```bash
petalinux-build
petalinux-package --boot --fsbl images/linux/zynqmp_fsbl.elf --fpga images/linux/system.bit --u-boot --force
lsblk   # SD 카드 마운트 지점 확인
cp -f images/linux/BOOT.BIN images/linux/image.ub images/linux/boot.scr /media/$USER/BOOT/
```

**실측 트러블슈팅 (2026-09-04):**

- **`petalinux-build` sstate 미러 타임아웃 (오탐):** `SState: cannot test file://...: TimeoutError('timed out')` 에러가 매 빌드마다 나면서 `[ERROR] Command bitbake ... failed`로 종료 코드가 비정상이 되는데, `Tasks Summary: ... all succeeded`를 같이 보면 실제 태스크는 전부 성공한 오탐이다. 원인은 기본 `SSTATE_MIRRORS`가 가리키는 `petalinux.xilinx.com`이 AMD 통합 이후 `https://edf.amd.com/`(인증 필요)로 307 리다이렉트되어 접속 자체가 죽어있기 때문. `project-spec/meta-user/conf/petalinuxbsp.conf`(재생성되지 않는 영구 설정 파일, `build/conf/plnxtool.conf`는 auto-generated라 직접 고쳐도 다음 빌드에 초기화됨)에 아래를 추가해 미러 조회 자체를 끄면 해결된다:

  ```
  SSTATE_MIRRORS = ""
  ```

- **SD카드에 새로 옮긴 파일이 `sync`만으로는 0바이트로 남음:** 보드에서 결과 파일을 SD카드로 `cp -r` 한 뒤 `sync`만 하고 카드를 뽑으면, **새로 생성된 파일명은 첫 시도에서 거의 항상 0바이트**(모든 데이터 유실, 그런데 디렉토리 엔트리 자체는 만들어짐 — 파일 타임스탬프가 `1970`대 근처의 이상한 고정값으로 찍히는 것도 같이 관찰됨)로 깨지는 게 이 저장소에서 두 번 재현됐다. `sync`는 커널에 flush를 요청만 할 뿐 완료를 보장하지 않는 경우가 있어서다. **카드를 뽑기 전에 반드시 `umount`까지 할 것** — 언마운트는 완전히 flush될 때까지 블로킹되므로 훨씬 안전하다:

  ```bash
  cd /root   # 마운트 지점 밖으로 나가기 (안 그러면 "device busy")
  sync
  umount /run/media/mmcblk0p1
  ```

### 9. 보드에서 검증

```bash
# UIO 디바이스 이름 확인 — "normalisp-control", "normalisp-buffer"가 보여야 함
for d in /sys/class/uio/uio*; do echo "$d : $(cat $d/name)"; done

# 드라이버 바인딩 확인
ls -l /sys/bus/platform/drivers/uio_pdrv_genirq/   # a0000000.normalisp, 70000000.normalisp-buffer 존재해야 함

# 물리주소/크기 확인
cat /sys/class/uio/uioN/maps/map0/addr
cat /sys/class/uio/uioN/maps/map0/size
```

`/dev/uio*`가 아예 안 보이면 `cat /proc/cmdline`에서 `uio_pdrv_genirq.of_id=generic-uio` 누락 여부와 커널 `.config`의 `CONFIG_UIO(_PDRV_GENIRQ)=y`를 먼저 확인(mmult 튜토리얼 14.10 트러블슈팅과 동일 원인).

**실측 결과 (2026-09-04):**

```
uio0 : normalisp-buffer   addr=0x0000000070000000  size=0x0000000000800000
uio1 : normalisp-control  addr=0x00000000a0000000  size=0x0000000000010000
uio2~5 : axi-pmon (ZynqMP 플랫폼 기본 성능 모니터, 무관)
```

두 UIO 모두 §5에서 정한 주소/크기와 정확히 일치. `uio0`/`uio1` 인덱스는 부팅마다 바뀔 수 있으므로 유저스페이스 앱은 인덱스가 아니라 `/sys/class/uio/uioN/name`으로 찾아야 한다 — `board_test/normalisp_uio_test.py`의 `find_uio()`가 그렇게 구현되어 있다(§7-1 참고).

이어서 §7-1의 `run_all_bayer.py`로 실제 카메라 RAW 10장(PASCAL 5 + LOD 5)을 전부 처리 — 10/10 PASS, `out_width`/`out_height` 일치, `0x00RRGGBB` 포맷 정확, PNG 변환 후 육안으로도 실제 사진임을 확인. 지연시간은 100MHz `pl_clk0` 기준 602×400에서 142.2ms, 610×408에서 147.0ms(같은 해상도 내에서는 프레임마다 완전히 동일 — HLS 파이프라인이 데이터에 무관하게 `width×height`로만 반복 횟수가 정해지기 때문, 정상). 상세는 §검증 상태 및 §7-1 참고.

### 10. 이후 확장

이 static 브링업이 성공하면(제어/데이터 경로, UIO, DMA, golden 대비 정확성 전부 확인) 다음 단계는:

- **LowlightISP 스왑:** 포트 시그니처가 동일하므로 같은 슬롯에 `LowlightISP`를 올려 같은 유저스페이스 앱으로 재검증 — Vivado block design은 그대로 두고 IP만 교체.
- **checker 추가:** static shell에 `checker_scan`을 별도 IP로 얹고(§2의 실제 레지스터 맵이 이미 이 문서에 있음), `hyst_flags`(ap_vld wire)는 AXI-Lite가 아니라 fabric 신호로 배선해야 함(`docs/checker.md` 참고) — mmult/NormalISP처럼 UIO로 노출하는 패턴이 아니다.
- **DFX 전환:** SPEC.md §7의 AMD DFX Controller IP(PG374) 경로로, `NormalISP`/`LowlightISP`를 같은 Reconfigurable Partition의 상호배타 RM으로 승격.

## 더 깊은 배경이 필요하면

원본 레포(`haengmini/dfxisp`, `haengmini/JNU_DFXISP_FPGA`)의 `isppipeline/hls/src/default_isp.md`(원본 파일명, 아직 이 이름 체계 반영 전)에 Vitis 대비 3가지 편차의 상세 근거, ablation 결과, mAP 수치가 정리되어 있다. 이 폴더에는 의도적으로 cpp/hpp만 두었으므로 필요 시 원본에서 참고.
