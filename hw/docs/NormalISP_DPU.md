# NormalISP + DPU(Vitis-AI) 통합 — 가이드

`~/Desktop/dfxisp/NormalISP_DPU/`, `~/Desktop/dfxisp/board_test/normalisp_dpu/`

## 무엇인가

**하나의 비트스트림·하나의 SD 이미지**에서 `dataset/test/`의 RAW Bayer를 `NormalISP`(PL 가속기)로 현상하고, 그 RGB888을 곧바로 **DPUCZDX8G**(Vitis-AI)에 넣어 객체 검출까지 끝내는 워크플로우다. 두 개의 선행 브링업 — `docs/NormalISP.md`(NormalISP static, 2026-09-04)와 `tutorials/vitisAI/docs/VitisAI_Tutorial.md`(DPU 단독, Vitis 플로우, 2026-09-10) — 을 **Vivado 플로우**에서 하나의 블록 디자인으로 합친 결과물이다.

```
RAW Bayer(.bin) ─UIO─► NormalISP (PL) ─► 0x00RRGGBB @DDR ─numpy 언팩─► HxWx3 uint8
                                                              │
                          ┌───────────────────────────────────┘
                          ▼
        resize/정규화 ─► vart.Runner (DPU, /dev/dpu) ─► numpy 디코드+NMS ─► dets JSON ─► mAP
```

`tutorials/vitisAI/docs/VitisAI_Tutorial.md` §24가 "dfxisp 통합에는 Vivado 플로우가 맞다"고 결론 내린 경로를 실제로 실행한 것이고, 그 판단(VART가 XRT 없이 `/dev/dpu`로 빌드된다, 2024.1 커널에 `xlnx_dpu`가 이미 있다)은 이 문서의 §2·§3에서 실측으로 확인됐다.

**왜 Vivado 플로우인가:** DFX(추후 `LowlightISP` 스왑)·`checker` 추가가 전부 Vivado 블록 디자인 작업이라 `.xo`/플랫폼을 다시 만드는 Vitis 플로우와 어긋난다. 부수 효과로 XRT/zocl 의존이 사라져 VART 블로커(튜토리얼 §17-4)도 애초에 성립하지 않는다.

## 상태 (2026-09-14)

- ✅ Vivado 통합 → 비트스트림/XSA, 타이밍 통과, **fingerprint 불변**(`0x101000056010407`) → xmodel 재컴파일 불필요
- ✅ PetaLinux 2024.1 Vivado-플로우 이미지 (xlnx_dpu + UIO + VART(non-XRT) + Python 바인딩)
- ✅ 보드 실물: `/dev/dpu` + UIO 2개, `xdputil query` fingerprint 일치
- ✅ NormalISP 단독 회귀 10/10, 지연시간 통합 전과 **소수점까지 동일**
- ✅ end-to-end **200장**(PASCAL_test 100 + LOD_test 100) × 2해상도 × 2모델 + JPG 대조군 — **주광에서 레퍼런스 JPG와 동등**(§6-2)
- ⬜ `s_axi_aclk` 100MHz(선택 최적화, §7), PMIC OC 한계 미적용(§6-3), LowlightISP 스왑/DFX(§8)

---

## 1. 하드웨어 — Vivado 블록 디자인

`NormalISP_DPU/NormalISP_DPU_zcu104/` (기존 `NormalISP/NormalISP_zcu104.xpr`를 Save As로 복제, BD 이름은 `NormalISP_zcu104_design1` 유지). IP repo에 `tutorials/vitisAI/dpu_zcu104/DPUCZDX8G_VAI_v3.0/dpu_ip` 추가.

```
PS (A53)
 ├─ M_AXI_HPM0_FPD ─ ps8_0_axi_periph ─┬─ M00 ─ NormalISP_0/s_axi_control   @0xA000_0000 (64K)
 │                                     └─ M01 ─ dpuczdx8g_0/S_AXI           @0xA100_0000 (16M)
 ├─ S_AXI_HPC0_FPD ◄─ smc_dpu_instr ◄─ dpuczdx8g_0/DPU0_M_AXI_INSTR
 ├─ S_AXI_HP1_FPD  ◄─ smc_dpu_data0 ◄─ dpuczdx8g_0/DPU0_M_AXI_DATA0
 ├─ S_AXI_HP2_FPD  ◄─ smc_dpu_data1 ◄─ dpuczdx8g_0/DPU0_M_AXI_DATA1
 ├─ S_AXI_HP0_FPD  ◄─ axi_smc       ◄─ NormalISP_0/m_axi_gmem0, gmem1   (기존 그대로)
 ├─ pl_clk0 100MHz ─► NormalISP ap_clk, dpuczdx8g_0/s_axi_aclk, ps8_0_axi_periph, clk_wiz_0/clk_in1
 │      clk_wiz_0 ─► clk_out1 600MHz → dpu_2x_clk (+ rst_dpu_600M)
 │                └─ clk_out2 300MHz → m_axi_dpu_aclk, smc_dpu_*, saxihpc0/hp1/hp2_fpd_aclk (+ rst_dpu_300M)
 └─ pl_ps_irq0 ◄─ xlconcat_0 ◄─ [In0] dpu0_interrupt, [In1] NormalISP interrupt(배선만)
```

### 1-1. DPU IP 파라미터 — fingerprint를 고정하는 값들

Vitis 플로우로 검증된 빌드(`DPUCZDX8G_VAI_v3.0/prj/Vitis/binary_container_1/.../vitis_design_DPUCZDX8G_1_0.xci`)와 **동일하게** 맞췄다. 같으면 `arch.json` fingerprint가 같고, 이미 컴파일해 둔 xmodel을 그대로 쓸 수 있다.

| GUI 탭 | 항목 | 값 | xci 근거 |
|---|---|---|---|
| Arch | Number of cores | 1 | `VER_DPU_NUM 1` |
| Arch | Arch | **B4096** | ICP16 / OCP16 / PP8 |
| Arch | RAM Usage | Low | `ARCH_IMG_BKGRP 2` |
| Arch | Channel Augmentation | Enable | `LOAD_AUGM 1` |
| Arch | Save Argmax/Max | Enable | `SAVE_ARGMAX_ENA 1` |
| Arch→Conv | ReLU Type | ReLU+LeakyReLU+ReLU6 | `CONV_LEAKYRELU 1`, `CONV_RELU6 1` |
| Arch→Alu | ALU Parallel | 4 | `ALU_PARALLEL 4` |
| Arch→Alu | ALU LeakyReLU | Disable | `ALU_LEAKYRELU 0` |
| Arch→Softmax | Softmax | Disable | 1DPU 구성에 sfm 없음 |
| Advanced | S-AXI Clock Independent | Enable | `S_AXI_CLK_INDEPENDENT 1` |
| Advanced | Clock Gating | Disable | `CLK_GATING_ENA 0` (BUFGCE_DIV 배선 생략) |
| Advanced | DSP Cascade / Usage | 4 / High | `CONV_DSP_CASC_MAX 4`, `CONV_DSP_ACCU_ENA 1` |
| Advanced | **UltraRAM per DPU** | **46** | `UBANK_IMG_N 5` + `WGT_N 17` + `BIAS 1` = 23뱅크 × 2 URAM |

**게이트:** Generate Output Products 후

```bash
cat NormalISP_DPU_zcu104.gen/sources_1/bd/NormalISP_zcu104_design1/ip/NormalISP_zcu104_design1_dpuczdx8g_0_0/arch.json
# {"fingerprint":"0x101000056010407"}
```
다르면 파라미터를 다시 대조할 것(ARGMAX·ReLU 타입·RAM Usage·URAM이 흔한 원인). 그래도 다르면 이 `arch.json`으로 Docker에서 `vai_c_xir` 재컴파일(튜토리얼 §20).

### 1-2. 주소/포트에서 걸린 것 2가지

- **DPU 레지스터는 `0xA100_0000`** — TRD 문서의 `0x8F00_0000`은 쓸 수 없다. ZynqMP `M_AXI_HPM0_FPD`가 PL 쪽으로 여는 창이 `0xA000_0000[256M]` / `0x4_0000_0000[4G]` / `0x10_0000_0000[224G]` 뿐이라 Vivado가 거부한다(`must fit an available aperture through master interface`). `NormalISP_0`(0xA000_0000, 64K) 다음 16M 정렬 자리를 잡았고, 그 사이 `0xA001_0000~0xA0FF_FFFF`는 checker/LowlightISP용으로 비어 있다.
- **Connection Automation을 그대로 믿으면 안 된다** — DPU 마스터 3개를 NormalISP용 `axi_smc`에 S02~S04로 합쳐 버리는데, SmartConnect는 주소 기반 라우팅이라 같은 DDR 범위(0x0~2G)를 여러 MI로 나눌 수 없다. 결과적으로 DPU 트래픽 전부가 100MHz 인터커넥트를 거쳐 HP0 한 포트로 몰린다(주소맵에서 HP1/HP2/HPC0_DDR_LOW가 전부 EXCL로 보이면 이 상태다). **마스터마다 1:1 SmartConnect를 따로 만들어 300MHz 도메인에 물릴 것.**
- 재배선 뒤엔 stale 세그먼트가 남아 `Cannot assign ... incomplete addressing path`가 난다. 해당 세그먼트를 지우고 포트별로 명시 배정:
  ```tcl
  assign_bd_address -offset 0x00000000 -range 2G -target_address_space [get_bd_addr_spaces dpuczdx8g_0/DPU0_M_AXI_INSTR] [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP0/HPC0_DDR_LOW] -force
  assign_bd_address -offset 0x00000000 -range 2G -target_address_space [get_bd_addr_spaces dpuczdx8g_0/DPU0_M_AXI_DATA0] [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP3/HP1_DDR_LOW]  -force
  assign_bd_address -offset 0x00000000 -range 2G -target_address_space [get_bd_addr_spaces dpuczdx8g_0/DPU0_M_AXI_DATA1] [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP4/HP2_DDR_LOW]  -force
  ```
  (HPC0=`SAXIGP0`, HP1=`SAXIGP3`, HP2=`SAXIGP4`. `report_bd_address`는 **없는 명령**이다 — `get_bd_addr_segs`로 확인.)

### 1-3. 구현 결과 (impl_1, 2026-09-11)

| 항목 | 값 |
|---|---|
| 타이밍 | WNS **+0.072** / WHS +0.010 / WPWS +0.167 ns, failing endpoint 0 (600/300/100MHz 전부) |
| 리소스 | CLB LUT 65,525 (28.4%) / FF 117,259 (25.5%) / BRAM 84 (26.9%) / **URAM 46 (47.9%)** / DSP 738 (42.7%) |
| 라우팅 | 186,661 nets fully routed |
| 산출물 | `NormalISP_DPU_zcu104_wrapper.xsa`(4.5MB, bit 포함), `NormalISP_DPU/arch.json` |

DPU 단독(Vitis 빌드) 대비 증가분이 LUT +12.9k / DSP +28로, `NormalISP` csynth 추정치와 일치한다. ZCU104(xczu7ev)에 B4096 + ISP 1벌은 여유 있게 들어간다 — 튜토리얼 §24-2가 "실측 필요"라고 남긴 항목에 대한 답.

리셋 블록 이름을 바꾼 뒤 재생성하지 않아 `Could not find module ..._proc_sys_reset_1_0 ... XDC will not be read` critical warning 2건이 남는데, 셀은 넷리스트에 정상 존재하고 누락되는 건 리셋 동기화기의 false-path 제약뿐이라 기능 영향 없다(타이밍만 보수적으로 계산됨).

---

## 2. PetaLinux 2024.1 — Vivado 플로우 이미지

`NormalISP_DPU/petalinux/normalisp_dpu_2024_1/`. **검증된 `tutorials/vitisAI/dpu_zcu104/zcu104_dpu_2024_1`의 `project-spec/`를 통째로 이식**하고(recipe·rootfs 선택 유지) Vivado 플로우 델타만 얹는 방식이 가장 빠르다. 오버레이 원본은 `NormalISP_DPU/petalinux/overlay/`에 보관.

```bash
petalinux-create -t project --template zynqMP -n normalisp_dpu_2024_1
rsync -a --exclude hw-description $OLD/project-spec/ $NEW/project-spec/
cd $NEW && petalinux-config --get-hw-description=$XSA --silentconfig   # MACHINE zcu104-revc, rootfs EXT4
```

### 2-1. 델타 5가지

| # | 무엇 | 내용 |
|---|---|---|
| 1 | 커널 | `recipes-kernel/linux/linux-xlnx/bsp.cfg` ← `CONFIG_XILINX_DPU=y`, `CONFIG_UIO=y`, `CONFIG_UIO_PDRV_GENIRQ=y`. **TRD의 `0001-misc-xlnx_dpu-...patch`는 적용하지 않는다**(2024.1 upstream에 이미 반영). `-x cleansstate` 후 재빌드해 `.config`에서 셋 다 `=y` 확인 |
| 2 | rootfs | `CONFIG_xrt`/`xrt-dev`/`zocl` → not set, `CONFIG_python3-numpy`/`python3-pillow` 추가 |
| 3 | VART | `recipes-vitis-ai/vart/vart_3.5.bb`의 `PACKAGECONFIG:append = " vitis python"` → **`" python"`** (튜토리얼 §17-4의 modern-XRT 소스 교체·`remove test`는 그대로 유지) |
| 4 | 디바이스트리 | `system-user.dtsi`에 NormalISP UIO + 예약메모리(§3) + `&dpuczdx8g_0` 오버라이드 |
| 5 | bootargs | `earlycon console=ttyPS0,115200 clk_ignore_unused root=/dev/mmcblk0p2 rw rootwait uio_pdrv_genirq.of_id=generic-uio cma=512M` |

빌드 시간은 이전 프로젝트의 캐시를 재사용하면 크게 줄어든다(`CONFIG_YOCTO_LOCAL_SSTATE_FEEDS_URL`=이전 `build/sstate-cache`, `CONFIG_PRE_MIRROR_URL`=`file://...build/downloads`, `CONFIG_YOCTO_NETWORK_SSTATE_FEEDS` 해제). `petalinux-build`는 성공해도 죽은 AMD 미러 타임아웃 때문에 **exit code가 non-zero**다 — `Tasks Summary: ... all succeeded`로 판단할 것.

### 2-2. VART가 XRT 없이 빌드되는지 — 실측 확인법

이 통합의 유일한 소프트웨어 리스크였고, 통과했다(2026-09-11):

```bash
petalinux-build -c vart -x cleansstate && petalinux-build -c vart
W=build/tmp/work/cortexa72-cortexa53-xilinx-linux/vart/3.5-r0/temp
grep -m1 "XRT" $W/log.do_configure          # WARNXRT FOUND: ... XRT_INCLUDE_DIRS-NOTFOUND
grep -c "dpu_controller_dnndk.cpp" $W/log.do_compile    # 2 (dnndk 경로 컴파일됨)
grep -c "xrt_cu.cpp\|dpu_control_xrt"  $W/log.do_compile # 0 (XRT 경로 미컴파일)
grep -oE "site-packages/vart\.so" $W/log.do_package      # Python 바인딩 생성 확인
```

`vitis-ai-library`도 XRT 없이 빌드된다(`ENABLE_XRT` 가드) — 덕분에 `xdputil`을 쓸 수 있다. 전체 빌드 6930 tasks all succeeded, rootfs에 `vart/xir/unilog/target-factory/vitis-ai-library 3.5`, `python3-numpy 1.23.3`, `python3-pillow 9.4.0`이 들어가고 `xrt`/`zocl`은 없다.

### 2-3. 디바이스트리 — DTG가 알아서 맞춰 준다

Vivado IP의 VLNV가 `xilinx.com:ip:dpuczdx8g:4.1`(소문자)이라, DTG가 만드는 노드가 커널 드라이버(`drivers/misc/xlnx_dpu.c`의 `of_match`)와 바인딩 문서(`xlnx,dpu.yaml`) 요구사항을 **그대로 충족**한다:

```dts
dpuczdx8g_0: dpuczdx8g@a1000000 {
    clock-names = "dpu_2x_clk", "m_axi_dpu_aclk", "s_axi_aclk";
    clocks = <&misc_clk_0>, <&misc_clk_1>, <&zynqmp_clk 71>;
    compatible = "xlnx,dpuczdx8g-4.1";
    interrupt-names = "dpu0_interrupt";
    interrupts = <0 89 4>;
    reg = <0x0 0xa1000000 0x0 0x1000000>;
};
```

(`NormalISP.md` §4의 `NormalISP_0` 대소문자 이슈와 달리 이쪽은 손댈 게 없다. `system-user.dtsi`의 `&dpuczdx8g_0` 오버라이드는 같은 값을 재기입하는 안전장치일 뿐이다.)

---

## 3. 메모리 레이아웃 — 두 종류의 버퍼가 공존한다

| 용도 | 주체 | 영역 | 확보 방식 |
|---|---|---|---|
| ISP 입출력 | `NormalISP` m_axi | **`0x7000_0000`~`0x707F_FFFF` (8MiB)** raw @+0x000000 / rgb @+0x200000 | 디바이스트리 `reserved-memory ... no-map` + generic-uio |
| DPU 텐서/명령 | `xlnx_dpu` 드라이버(`dpcma`) | **CMA 512MiB @ `0x5000_0000`** | bootargs `cma=512M` |

부팅 로그로 확인:

```
OF: reserved mem: 0x0000000070000000..0x00000000707fffff (8192 KiB) nomap non-reusable buffer@70000000
cma: Reserved 512 MiB at 0x0000000050000000
```

CMA가 `0x5000_0000`부터 512MiB면 끝이 정확히 `0x7000_0000`이라 **예약 버퍼와 맞닿되 겹치지 않는다.** 만약 겹치게 배치되면 `system-user.dtsi`의 예약 주소를 상단(예 `0x7F80_0000`)으로 옮기고 `normalisp_uio_test.py`의 `BUF_PHYS_BASE` 상수 하나만 바꾸면 된다.

---

## 4. 보드 브링업 검증

**중요:** `xlnx_dpu`와 `uio_pdrv_genirq`는 **probe에 성공하면 dmesg에 아무것도 남기지 않는다**(성공 경로가 전부 `dev_dbg`). "DPU 관련 로그가 없다"는 실패 신호가 아니다 — 디바이스 노드로 판정할 것.

```bash
ls -l /dev/dpu /dev/uio*                                     # /dev/dpu = misc 10,126
for d in /sys/class/uio/uio*; do echo "$d : $(cat $d/name)"; done
cat /sys/class/uio/uio*/maps/map0/addr
python3 -c "import vart, xir, numpy, PIL; print('ok')"
xdputil query | grep -iE "fingerprint|DPU Arch|Frequency|IP version"
```

실측 (2026-09-14):

```
/dev/dpu                                  crw------- 10,126
uio0 : normalisp-buffer   0x0000000070000000 / 0x800000
uio1 : normalisp-control  0x00000000a0000000 / 0x10000
uio2~5 : axi-pmon (ZynqMP 기본, 무관)
xdputil query -> "IP version":"v4.1.0", "DPU Arch":"DPUCZDX8G_ISA1_B4096",
                 "DPU Frequency (MHz)":300, "XRT Frequency (MHz)":100,
                 "fingerprint":"0x101000056010407"
```

fingerprint가 §1-1의 빌드값과 같으므로 기존 xmodel을 그대로 쓴다.

- `xdputil query`/파이프라인은 **root로** 실행할 것 — `/dev/dpu`, `/dev/uio*`가 `crw------- root root`다(일반 계정은 `cannot open /dev/dpu`).
- 보드에 RTC가 없어 로그 시각이 `2022`/`Nov 8`처럼 찍히는 건 무해.

---

## 5. 보드 소프트웨어

| 파일 | 역할 |
|---|---|
| `board_test/normalisp_dpu/isp_dpu_pipeline.py` | 본체. 프레임마다 `run_one()`(ISP) → RGB888 언팩 → `preprocess`/`DpuSubgraphRunner`/`*_postprocess`(DPU) → 원본 좌표 환산. 출력 JSON은 `run_detector.py` 포맷이라 `eval_map.py`·`results/recompute.py`가 그대로 먹는다 |
| `board_test/normalisp_dpu/run_all.sh` | 두 모델 실행 + 도메인별 mAP, 결과를 `/home/root/results_ispdpu/`에 모음 |
| `board_test/normalisp_dpu/stage_sd.sh` | 호스트에서 보드용 파일 일괄 수집(17MB): 스크립트 7개 / xmodel 2개 / bayer 10 / labels / 레퍼런스 JPG / arch.json / dpu_sw_optimize |
| `board_test/normalisp_dpu/pmbus_oc_check.py` | PMIC OC 한계 진단(§6-3) |

**재사용(수정 없음):** `board_test/normalisp/normalisp_uio_test.py`(UIO 8단계 시퀀스), `tutorials/vitisAI/Vitis-AI/app/{run_detector.py, eval_map.py, ssdlite_anchors.npy}`, `compiled_output/*.xmodel`.

새로 짠 로직은 사실상 언팩 한 줄이다 — `0x00RRGGBB` uint32 → `(H,W,3) uint8`:

```python
words = np.fromfile(path, dtype="<u4")
rgb = np.stack([(words >> 16) & 0xFF, (words >> 8) & 0xFF, words & 0xFF], -1).astype(np.uint8).reshape(H, W, 3)
```
(호스트에서 `tools/rgb888_to_png.py` 결과와 픽셀 단위로 동일함을 확인했다.)

실행:

```bash
# 보드(root)
cd /home/root/app && ./run_all.sh            # CONF=0.25 ./run_all.sh 로 육안 확인용 실행
# 개별 실행
python3 isp_dpu_pipeline.py --model yolov8n --xmodel /home/root/models/yolov8n_dpu.xmodel \
    --bayer-root /home/root/bayer --conf 0.001 --out dets.json --out-per-domain --save-png vis
```
- SSDLite는 반드시 **`--norm pm1`** (calibration이 `(x/255-0.5)/0.5`였음, 튜토리얼 5장), YOLOv8n은 `--norm unit`.
- mAP용은 `--conf 0.001`, P/R·시각화는 `0.25`.

---

## 6. 실측 결과 (2026-09-14, 보드 INT8)

### 6-1. 지연시간

**ISP 지연은 픽셀 수에 정확히 비례한다** — 저해상도 평균 144.6 ms, 고해상도 평균 523.6 ms이고 픽셀 비(3.621)를 곱한 예측값 523.6 ms와 소수점까지 일치한다(HLS 루프가 `width×height`로만 반복 횟수가 정해지는 고정 지연 파이프라인, `NormalISP.md` §구현 메모 II=9).

| 구성 | ISP | pre | DPU | post | total |
|---|---|---|---|---|---|
| YOLOv8n · 저해상도(602×400/610×408) | 144.6 | 51.6 | **65.7** | 109.1 | 371.1 ms (2.7 FPS) |
| YOLOv8n · 고해상도(1206×802/1098×734) | 523.6 | 72.3 | **63.5** | 108.4 | 767.8 ms (1.3 FPS) |
| SSDLite · 저해상도 | 144.6 | 27.7 | **16.3** | 292.9 | 481.5 ms (2.1 FPS) |
| SSDLite · 고해상도 | 523.6 | 46.2 | **16.1** | 292.9 | 878.9 ms (1.1 FPS) |
| (대조) YOLOv8n · JPG PASCAL/LOD | — | 50.9 / 77.7 | 65.0 / 65.7 | 83.9 / 128.8 | 199.8 / 272.2 ms |
| (대조) SSDLite · JPG PASCAL/LOD | — | 26.3 / 51.6 | 15.8 / 15.8 | 267.9 / 315.1 | 310.0 / 382.5 ms |

- **DPU 시간은 입력 해상도와 무관**(64~66 ms / 16 ms) — 전처리에서 640×640·320×320으로 리사이즈하므로 당연하지만, ISP 해상도를 올려도 가속기 쪽 비용이 늘지 않는다는 확인.
- **ISP 지연이 통합 전 단독 이미지와 동일**(602×400 142.2 / 610×408 147.0 ms) — DPU를 HPC0/HP1/HP2로 분리한 덕분에 NormalISP(HP0 전용) 대역폭이 그대로다.
- 후처리가 큰 건 mAP용 `--conf 0.001` 때문(클래스별 top-300이 전부 NMS). SSDLite 292.9 ms는 3234개 앵커 전수 디코드 + 3클래스 NMS의 numpy 비용이고, `--conf 0.25`면 수십 ms로 떨어진다.
- DPU 65 ms는 DPU 단독 이미지(Vitis 플로우)의 55.7 ms보다 ~16% 느리다 → §7.

### 6-2. 정확도 — 100장 본 실험 (LOD_test / PASCAL_test 각 100장)

같은 보드·같은 xmodel·같은 후처리·conf 0.001. `isp_lo`는 640×480 박스(K=10/9 비닝), `isp_hi`는 1280×960 박스(K=5 비닝), `jpg`는 데이터셋이 제공하는 레퍼런스 렌더링(= 검출기 입장에서의 상한).

| 모델 | 셋 | 입력 | mAP50 | mAP50-95 | person / car / bicycle (AP50) |
|---|---|---|---|---|---|
| YOLOv8n | PASCAL | jpg 600×400 | 0.9105 | 0.6311 | 0.900 / 0.904 / 0.927 |
| YOLOv8n | PASCAL | **isp_hi 1206×802** | **0.9068** | **0.6328** | 0.895 / 0.883 / 0.942 |
| YOLOv8n | PASCAL | isp_lo 602×400 | 0.8733 | 0.5660 | 0.882 / 0.855 / 0.882 |
| YOLOv8n | LOD | jpg 1280×855 | 0.5896 | 0.3285 | 0.611 / 0.527 / 0.631 |
| YOLOv8n | LOD | **isp_hi 1098×734** | **0.3886** | **0.1820** | 0.405 / 0.350 / 0.411 |
| YOLOv8n | LOD | isp_lo 610×408 | 0.3021 | 0.1275 | 0.315 / 0.281 / 0.311 |
| SSDLite | PASCAL | jpg 600×400 | 0.8487 | 0.5035 | 0.780 / 0.852 / 0.915 |
| SSDLite | PASCAL | **isp_hi 1206×802** | **0.7742** | **0.4293** | 0.644 / 0.800 / 0.878 |
| SSDLite | PASCAL | isp_lo 602×400 | 0.7096 | 0.3904 | 0.552 / 0.715 / 0.862 |
| SSDLite | LOD | jpg 1280×855 | 0.4893 | 0.2644 | 0.456 / 0.483 / 0.529 |
| SSDLite | LOD | **isp_hi 1098×734** | **0.3332** | **0.1621** | 0.329 / 0.260 / 0.410 |
| SSDLite | LOD | isp_lo 610×408 | 0.2759 | 0.1310 | 0.307 / 0.239 / 0.281 |

**읽는 법 — JPG 상한 대비 손해(mAP50):**

| | YOLOv8n PASCAL | YOLOv8n LOD | SSDLite PASCAL | SSDLite LOD |
|---|---|---|---|---|
| isp_lo | −0.037 | −0.288 | −0.139 | −0.213 |
| **isp_hi** | **−0.004** | **−0.201** | −0.075 | −0.156 |
| 해상도 기여(hi−lo) | +0.034 | +0.087 | +0.065 | +0.057 |

1. **주광(PASCAL) + YOLOv8n에서 NormalISP는 레퍼런스와 사실상 동등하다** — mAP50 0.9068 vs 0.9105(−0.004), mAP50-95는 오히려 +0.002. ISP의 γ=2.0·placeholder CCM 색 도메인이 JPG로 학습한 검출기에 실질적 손해를 주지 않는다는 뜻으로, 통합 전 가장 큰 불확실성(`VitisAI_Tutorial.md` 머리말의 "ISP 출력의 정규화 스케일/색공간 일치" 경고)에 대한 답이다.
2. **저해상도에서의 손해는 색이 아니라 비닝 배율 때문이다.** `isp_lo`(602×400)는 PASCAL JPG(600×400)와 **거의 같은 출력 크기인데도** −0.037인데, 같은 색 파이프라인으로 K만 10→5로 낮춘 `isp_hi`에서 −0.004로 사라진다. 즉 손실은 RAW 도메인에서 10×10 블록을 평균하며 버린 디테일이고, ISP 연산이 아니다.
3. **저조도(LOD)는 해상도를 올려도 −0.20이 남는다.** `isp_lo`→`isp_hi`로 +0.087 회복되지만 JPG 상한과는 여전히 멀다. NormalISP에 노출 게인이 없어 출력 평균 밝기가 2.5~8에 머무는 것이 지배적 원인 — **`LowlightISP`(2× 노출 게인 + 2×2 same-colour binning)가 필요한 이유이자, 그 개선폭을 재는 대조군이 이 표다.**
4. **SSDLite는 어느 조건에서나 YOLOv8n보다 도메인 변화에 취약하다**(PASCAL에서도 −0.075, person AP50이 0.780→0.644). INT8 양자화 손실이 크고 calibration이 LOD 전용이었던 기존 관측(`VitisAI_Tutorial.md` 20장)과 같은 방향이다.
5. 참고: 10장 예비실험(2026-09-14)의 수치(PASCAL 0.7917 등)는 표본이 도메인당 5장이라 편차가 컸다 — 100장 기준인 이 표가 정본이다.

원자료: `board_test/normalisp_dpu/results100/` (`dets_*.json` 16개, `map_summary.log`, 실행 로그 8개). 재계산은 호스트에서
`python3 -c "import sys;sys.path.insert(0,'../../../tutorials/vitisAI/Vitis-AI/app');from eval_map import evaluate;import json;evaluate(json.load(open('dets_yolov8n_isp_hi_PASCAL.json')),'../../../dataset/PASCAL_test/labels')"` 형태로 언제든 가능(결정적).

### 6-3. `zynqmp_dpu_optimize.sh` 함정 — QoS/PMIC가 조용히 건너뛰어진다

스크립트가 `set -e`인데 첫 단계 `ext4_resize`가 **이 rootfs에 `parted`/`resize2fs`가 없어서** 실패한다. 그러면 `Auto resize ext4 partition ...`만 찍고 **QoS와 PMIC 단계가 아예 실행되지 않는다**(성공 표시 `[✔]`가 안 나오면 이 상태).

```bash
cd /home/root/dpu_sw_optimize/zynqmp
source functions/zynqmp_qos_en.sh && qos_config     # DDR QoS 수동 적용
./functions/irps5401                                 # PMIC — 아래 참고
```
- QoS는 정상 적용됨(HP0~3/HPC0~1의 RD/WRISSUE `0x7`→`0xf`, PORT_TYPE은 이미 `0xa845`). **적용해도 DPU 시간은 64.8ms 그대로**였다 — 1코어 + 단일 프레임 워크로드라 대역폭이 병목이 아니라는 뜻.
- PMIC 툴은 `/dev/i2c-4: Device or resource busy`로 실패한다. 커널에 `CONFIG_SENSORS_IRPS5401=y`가 있어 hwmon 드라이버가 0x43을 점유하기 때문. 떼었다 붙이면 접근은 되지만,
  ```bash
  echo 4-0043 > /sys/bus/i2c/drivers/irps5401/unbind
  ./functions/irps5401            # -> "OC fault limit is not 37A"
  echo 4-0043 > /sys/bus/i2c/drivers/irps5401/bind
  ```
  이 에러는 **쓰기 실패가 아닐 수 있다**: 툴이 읽은 워드가 `0xF094`와 비트패턴까지 같은지만 보는데, PMBus LINEAR11은 같은 값을 여러 지수로 표현하므로(37A = `0xF094` = `0xE250`) 칩이 자기 지수로 정규화해 돌려주면 무조건 실패한다. 실제 값을 보려면 `board_test/normalisp_dpu/pmbus_oc_check.py`(i2c-tools 없이 ioctl로 페이지별 값을 A 단위로 디코드, `--set 37`로 쓰기도 가능).
- **PMIC 미적용 상태로 전체 실행에서 리부팅은 없었다.** TRD 기본이 3코어인 데 비해 이 설계는 1코어라 소비전류가 훨씬 낮다. 추론 중 보드가 리셋되면 그때 위 절차로 OC 한계를 올릴 것.

---

## 7. 알려진 개선 여지

1. **DPU `s_axi_aclk`가 100MHz** (`xdputil query`의 `"XRT Frequency (MHz)":100`). Vitis 플로우 빌드의 IP는 `S_AXI_FREQ_MHZ=300`이었고, DPU 시간 차이(64.8 vs 55.7ms, +16%)의 유력한 원인이다. 고치려면 BD에서 `dpuczdx8g_0/s_axi_aclk`를 `clk_wiz_0/clk_out2`로 옮기고 `ps8_0_axi_periph`의 해당 MI 세그먼트도 300MHz로 맞춘 뒤 재합성(~1시간). **fingerprint는 안 바뀌므로 xmodel 재컴파일 불필요.**
2. **전처리/후처리가 CPU 병목**(52~302ms). 후처리는 conf 임계값과 top-k로 바로 줄고, 전처리는 PIL→직접 numpy 리사이즈 또는 ISP 출력 해상도를 모델 입력(640/320)에 맞춰 뽑는 방식으로 줄일 수 있다.
3. **평가 표본 확대** — 현재 10장. `tools/raw_to_bayer_bin.py`로 PASCAL/LOD RAW를 더 변환하면 같은 파이프라인이 그대로 돈다.

## 8. 다음 단계

- **LowlightISP 스왑** — 포트 시그니처가 `NormalISP`와 동일하므로 BD에서 IP만 교체(출력이 H/2×W/2인 점만 스크립트에 반영). §6-2의 LOD 수치가 대조군. → **진행 중: `docs/LowlightISP_DPU.md`** (BD/PetaLinux 빌드 스크립트, 보드 실험 스크립트, 해상도 매칭 설계 완료)
- **checker 추가** — static shell에 `checker_scan`을 얹고 `hyst_flags`는 AXI-Lite가 아니라 fabric 신호로 배선(`docs/checker.md`). 주소는 `0xA001_0000`대가 비어 있다.
- **DFX 전환** — `NormalISP`/`LowlightISP`를 같은 Reconfigurable Partition의 상호배타 RM으로 승격(SPEC.md §7, AMD DFX Controller PG374). DPU는 static 영역에 그대로 둔다.

## 참고

- `docs/NormalISP.md` — ISP 자체(파이프라인, 레지스터 맵, UIO/예약메모리, RAW 변환 규격)
- `docs/NormalISP_DPU_plan.md` — 이 통합의 계획 + 단계별 진행 로그(시행착오 원문)
- `docs/LowlightISP_DPU.md` — 같은 셸에서 ISP만 LowlightISP로 바꾼 후속 실험(§8의 첫 항목)
- `tutorials/vitisAI/docs/VitisAI_Tutorial.md` — 모델 양자화/컴파일(1~8장), DPU 단독 브링업(Vitis 플로우), §17-4 VART/XRT 소스 교체, §24 Vivado vs Vitis 플로우 비교
- `tutorials/vitisAI/dpu_zcu104/DPUCZDX8G_VAI_v3.0/prj/Vivado/README.md` — DPU IP 설정별 "Model Recompile Required" 표
