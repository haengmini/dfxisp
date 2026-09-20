# NormalISP + DPU(Vitis-AI) 통합 워크플로우 계획 — ZCU104, Vivado 플로우

## Context

지금까지 두 개의 독립 브링업이 끝나 있다.

| 완료된 것 | 위치 | 핵심 산출물 |
|---|---|---|
| **NormalISP static 브링업** (2026-09-04) | `dfxisp/NormalISP/{NormalISP_zcu104.xpr, project/xilinx-zcu104-2024.1}` | UIO(`normalisp-control` @0xA000_0000, `normalisp-buffer` @0x7000_0000 8MiB) + `board_test/normalisp/normalisp_uio_test.py::run_one()` — `dataset/test/bayer/*.bin` 10장 처리 완료 |
| **DPU(Vitis 플로우) 브링업** (2026-09-10) | `tutorials/vitisAI/dpu_zcu104/{DPUCZDX8G_VAI_v3.0, zcu104_dpu_2024_1}` | B4096+URAM DPU, fingerprint `0x101000056010407`, VART 4.0(modern-XRT 소스) + Python 바인딩, `Vitis-AI/app/run_detector.py` (YOLOv8n mAP50 PASCAL 0.911 / SSDLite 0.849) |

목표: **한 장의 SD카드/한 비트스트림**에서 `dataset/test/` RAW Bayer → **NormalISP(HW)** → RGB888 → **DPU(HW) 추론** → 검출 결과 JSON + mAP까지 이어지는 워크플로우.

사용자 결정: **Vivado 플로우**(기존 NormalISP 블록 디자인에 DPU IP 추가, XRT 없음) / 작업물은 **`dfxisp/` 안**.

`VitisAI_Tutorial.md` §24가 이 경로의 근거를 이미 정리해 두었다: (a) VART는 `vitis` PACKAGECONFIG만 빼면 XRT 없이 `/dev/dpu` ioctl(dnndk 경로)로 빌드됨(v4.0 소스에 `dpu_controller_dnndk.cpp` 존재 확인), (b) 2024.1 커널에 `drivers/misc/xlnx_dpu.c`가 이미 있고 TRD 패치는 upstream 반영 완료, (c) 리소스는 DPU B4096이 LUT 23%/DSP 41%/BRAM 27%/URAM 48%, NormalISP가 LUT ~5%/DSP 28 → 여유 충분.

---

## 목표 아키텍처

```
PS (A53, PetaLinux 2024.1, ext4 rootfs)
 ├─ M_AXI_HPM0_FPD ─ AXI Interconnect ─┬─ NormalISP_0/s_axi_control  @0xA000_0000 (UIO generic-uio)
 │                                     └─ DPUCZDX8G_0/S_AXI         @0xA100_0000 (xlnx_dpu 드라이버, /dev/dpu)
 ├─ S_AXI_HPC0_FPD ◄─ DPUCZDX8G_0/DPU0_M_AXI_INSTR
 ├─ S_AXI_HP0_FPD  ◄─ DPUCZDX8G_0/DPU0_M_AXI_DATA0
 ├─ S_AXI_HP1_FPD  ◄─ DPUCZDX8G_0/DPU0_M_AXI_DATA1
 ├─ S_AXI_HP2_FPD  ◄─ SmartConnect ◄─ NormalISP_0/m_axi_gmem0, m_axi_gmem1   (기존 HP0 → HP2로 이동)
 ├─ pl_clk0 100MHz ─► NormalISP ap_clk, DPU s_axi_aclk, Interconnect, clk_wiz 입력
 │                    clk_wiz ─► 300MHz m_axi_dpu_aclk / 600MHz dpu_2x_clk (+ proc_sys_reset ×2)
 └─ pl_ps_irq0 ◄─ xlconcat ◄─ [0] DPUCZDX8G_0/dpu0_interrupt, [1] NormalISP_0/interrupt(배선만)

보드 SW:  isp_dpu_pipeline.py
  bayer .bin ─UIO─► NormalISP ─► 0x00RRGGBB(DDR 0x70200000) ─numpy 언팩─► HxWx3 uint8
           ─resize/정규화─► vart.Runner(DPU) ─numpy 후처리─► dets JSON ─► eval_map.py(mAP)
```

---

## Phase 0 (선택, ~30분, HW 작업 전) — 기존 DPU SD카드로 "ISP 출력 도메인" 먼저 검증

모델은 JPG로 학습됐고 NormalISP 출력(γ=2.0, placeholder CCM)은 색 도메인이 다르다. HW 통합 전에 이 영향만 분리해서 보는 단계 — 이미 있는 것만 조합하면 된다.

1. 호스트: `board_test/normalisp/normalisp_out_png/{PASCAL,LOD}/*.png` (2026-09-04 보드 결과)를 라벨 stem과 맞게 복사 (`2014_000888_raw12_602x400_rgb888.png` → `2014_000888.png`) — 작은 스크립트 `tools/isp_png_for_eval.py` 또는 셸 한 줄.
2. 현재 DPU SD카드(`zcu104_dpu_2024_1`)로 부팅, `scp` → `run_detector.py --images isp_png --conf 0.001` (yolov8n / ssdlite `--norm pm1`) → `eval_map.py dets.json labels/` (`dataset/test/labels/`, 10장).
3. 같은 10장의 `dataset/test/images/*.jpg`(레퍼런스 JPG)로도 돌려 **JPG vs ISP-출력 mAP 차이**를 기록 → 이후 Phase 4의 기대값/디버그 기준선.

결과는 `tutorials/vitisAI/results/board/dets_<model>_isp0_{PASCAL,LOD}.json` 규칙으로 백업.

---

## Phase 1 — Vivado: NormalISP 블록 디자인에 DPU IP 추가 → XSA

작업 디렉토리: `dfxisp/NormalISP_DPU/vivado/NormalISP_DPU_zcu104/` (기존 `NormalISP/NormalISP_zcu104.xpr`를 **File → Project → Save As**로 복제, 원본은 손대지 않음).

1. **IP repo 추가**: Settings → IP → Repository → `tutorials/vitisAI/dpu_zcu104/DPUCZDX8G_VAI_v3.0/dpu_ip/` (`DPUCZDX8G_v4_1_0/component.xml`).
2. **DPU IP 인스턴스 `DPUCZDX8G_0` 추가 + 파라미터** — 검증된 Vitis 빌드 xci(`.../prj.srcs/sources_1/bd/vitis_design/ip/vitis_design_DPUCZDX8G_1_0/*.xci`)와 **동일하게** 맞춘다(fingerprint 유지 = xmodel 재컴파일 불필요):

   | GUI 항목 | 값 | 근거(xci) |
   |---|---|---|
   | Number of cores | 1 | `prj_config_1dpu` |
   | Arch | **B4096** | ICP16/OCP16/PP8 |
   | RAM usage | Low | RAM_DEPTH_* 3 |
   | Channel augmentation | Enable | LOAD_AUGM 1 |
   | ALU parallel | 4 (default) | ALU_PARALLEL 4 |
   | Conv ReLU type | ReLU+LeakyReLU+ReLU6 | CONV_LEAKYRELU 1, CONV_RELU6 1 |
   | ALU LeakyReLU | Disable | ALU_LEAKYRELU 0 |
   | Save Argmax/Max | Enable | SAVE_ARGMAX_ENA 1 |
   | DSP usage | High, cascade 4 | CONV_DSP_ACCU_ENA 1, CASC_MAX 4 |
   | URAM per DPU | Img 5 / Wgt 17 / Bias 1 | UBANK 5/17/1 (DBANK 0) |
   | Softmax | Disable | 1DPU 구성에 sfm 커널 없음 |
   | S_AXI clock independent | Enable (100MHz 레지스터 클럭) | TRD REG_CLK 100 |
   | Clock gating / Timestamp | TRD 기본값 | fingerprint 무관 |

   **게이트**: Generate Output Products 후 `NormalISP_DPU_zcu104.gen/sources_1/bd/<bd>/ip/<bd>_DPUCZDX8G_0/arch.json`의 fingerprint가 **`0x101000056010407`** 인지 확인. 다르면 파라미터를 되짚거나(ARGMAX/LeakyReLU가 흔한 원인) 최후엔 이 arch.json으로 Docker에서 `vai_c_xir` 재컴파일(튜토리얼 §20 절차).
3. **PS 재구성**: Slave `S_AXI_HPC0_FPD`, `HP0`, `HP1`, `HP2` Enable(128-bit); `PL-PS IRQ0` Enable; `pl_clk0` 100MHz 유지.
4. **클럭/리셋**: `clk_wiz_0` (입력 pl_clk0 100MHz, MMCM, clk_out1 **300MHz** → `m_axi_dpu_aclk`, clk_out2 **600MHz** → `dpu_2x_clk`, 두 출력 같은 MMCM·Matched Routing 체크, `locked` 사용) + `proc_sys_reset` 300/600 각 1개(`dcm_locked`←clk_wiz.locked). `s_axi_aclk` ← pl_clk0(기존 `rst_ps8_0_100M`). HP 포트 클럭: HPC0/HP0/HP1 ← 300MHz, HP2 ← 100MHz(NormalISP 그대로).
5. **연결**: 위 다이어그램대로. NormalISP `axi_smc`는 HP0 → **HP2**로 옮긴다(DPU와 포트 경합 방지). `xlconcat`(2-in) → `pl_ps_irq0`.
6. **Address Editor**: `DPUCZDX8G_0/S_AXI` → `0xA100_0000` 범위 16MB(HPM0_FPD 창 0xA000_0000~0xAFFF_FFFF 안이어야 함 — TRD의 0x8F00_0000은 이 창 밖이라 거부됨), `NormalISP_0` 0xA000_0000 유지. DPU 3개 마스터는 DDR_LOW/DDR_HIGH 자동 할당(OCM/QSPI 제외).
7. Validate → Wrapper 재생성 → Synthesis/Implementation → Bitstream → **Export Hardware(include bitstream)** → `NormalISP_DPU_zcu104_wrapper.xsa`.
   - 확인: 타이밍(600MHz 도메인 WNS≥0), 리소스, `DPUCZDX8G_0` 인스턴스명(디바이스트리 라벨이 됨), `top.gen/.../arch.json` 보관(→ SD카드에 함께 넣음).
   - 참고 배선 필요 시: `prj/Vivado/hw/scripts/trd_prj.tcl`을 `prj_part xczu7ev-ffvc1156-2-e`, `DPU_NUM 1`로 별도 디렉토리에서 돌려 레퍼런스 BD를 열어 보기만(그 프로젝트는 쓰지 않음 — zcu102 xdc 포함).
   - 실패 시 순서: 600MHz 타이밍 미달 → clk gating off → 275/550MHz(fingerprint 불변, `xdputil`/드라이버 로그 주파수만 달라짐).

---

## Phase 2 — PetaLinux 2024.1: Vivado 플로우 이미지 (xlnx_dpu + VART + UIO)

작업 디렉토리: `dfxisp/NormalISP_DPU/petalinux/normalisp_dpu_2024_1/`. **`zcu104_dpu_2024_1`을 베이스로 복제**(검증된 recipe/rootfs 선택 유지)하고 Vivado 플로우 델타만 적용한다.

1. **프로젝트 생성**: `petalinux-create -t project --template zynqMP -n normalisp_dpu_2024_1` → `project-spec/meta-user/{recipes-vitis-ai, recipes-vai-kernel, recipes-kernel, conf/user-rootfsconfig}` 및 `project-spec/configs/rootfs_config`를 `zcu104_dpu_2024_1`에서 복사 → `petalinux-config --get-hw-description=<Phase1 xsa>` (MACHINE_NAME `zcu104-revc`, rootfs **EXT4**, `/dev/mmcblk0p2`).
2. **빌드 시간 단축**: `petalinux-config` → Yocto Settings → Local sstate feeds = `.../zcu104_dpu_2024_1/build/sstate-cache`(4GB), Pre-mirror = `file://.../zcu104_dpu_2024_1/build/downloads`(28GB); `petalinuxbsp.conf`에 `SSTATE_MIRRORS = ""` (NormalISP 프로젝트에서 검증된 우회).
3. **커널** `recipes-kernel/linux/linux-xlnx/bsp.cfg` (현재 빈 파일):
   ```
   CONFIG_XILINX_DPU=y
   CONFIG_UIO=y
   CONFIG_UIO_PDRV_GENIRQ=y
   ```
   (TRD의 `0001-misc-xlnx_dpu-...patch`는 **적용하지 않음** — 2024.1 upstream 반영 완료.) `petalinux-build -c kernel -x cleansstate` 후 `.config`에서 셋 다 `=y` 확인(NormalISP 때 `=m`로 남던 이슈).
4. **rootfs**: `rootfs_config`에서 `CONFIG_xrt`, `CONFIG_xrt-dev`, `CONFIG_zocl` → not set. `user-rootfsconfig`에 `CONFIG_python3-numpy`, `CONFIG_python3-pillow` 명시 추가(현재는 vitis-ai-library 경유로만 들어옴).
5. **VART**: `recipes-vitis-ai/vart/vart_3.5.bb`의 `PACKAGECONFIG:append = " vitis python"` → `" python"` (17-4의 modern-XRT 소스 교체·`remove test`는 그대로). `vitis-ai-library_3.5.bb`는 그대로 시도(`ENABLE_XRT` 가드 있음) — 빌드 실패 시 rootfs에서 `vitis-ai-library*`, `vai-benchmark`, `vai-sample` 제거(파이프라인은 `vart`+`xir` Python 바인딩만 필요). `petalinux-build -c vart -x cleansstate && petalinux-build -c vart`로 먼저 단독 통과.
6. **디바이스트리** `recipes-bsp/device-tree/files/system-user.dtsi` — NormalISP 것(`NormalISP/project/.../system-user.dtsi`)에 DPU 오버라이드를 합친다. DTG는 `compatible = "xlnx,DPUCZDX8G-4.1"`(대소문자 보존)로 만들고 커널 드라이버는 `xlnx,dpuczdx8g-4.1`만 매치하므로 **오버라이드 필수**:
   ```dts
   &DPUCZDX8G_0 {
       compatible = "xlnx,dpuczdx8g-4.1";
       clock-names = "s_axi_aclk", "dpu_2x_clk", "m_axi_dpu_aclk";   /* DTG 생성 clocks 순서와 맞출 것 */
       interrupt-names = "dpu0_interrupt";
   };
   &NormalISP_0 { compatible = "generic-uio"; linux,uio-name = "normalisp-control"; };
   /* reserved-memory 0x70000000 8MiB + normalisp-buffer UIO 노드는 기존 그대로 */
   ```
   빌드 후 `dtc -I dtb -O dts images/linux/system.dtb | grep -A12 -i dpuczdx8g` 로 최종 dtb 확인(중간 산출물 아님).
7. **bootargs**(AUTO 해제): `earlycon console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait clk_ignore_unused uio_pdrv_genirq.of_id=generic-uio cma=512M` — CMA(DPU 드라이버 `dpcma`)와 `0x70000000` no-map 예약이 겹치지 않는지 부팅 로그 `cma: Reserved 512 MiB at 0x...`로 확인. 겹치면 예약 버퍼를 `0x7F80_0000`(상단 8MiB)로 이동하고 `normalisp_uio_test.py::BUF_PHYS_BASE`만 바꾼다.
8. `petalinux-build` → `petalinux-package --boot --fsbl zynqmp_fsbl.elf --u-boot u-boot.elf --pmufw pmufw.elf --fpga system.bit --force` → `petalinux-package --wic --bootfile "BOOT.BIN boot.scr Image system.dtb"` → `petalinux-sdimage.wic`.

---

## Phase 3 — SD카드 + 부팅 검증

1. `dd` (장치 `lsblk`로 확인, 이 머신은 `/dev/sda`), 파티션 2개 확인. 기존 DPU SD는 `sd_backup_zcu104_dpu20260910/`에 백업돼 있으니 그 카드를 재사용해도 됨.
2. rootfs 파티션에 미리 배치: `/home/root/models/*.xmodel`, `app/{run_detector.py, eval_map.py, ssdlite_anchors.npy}`, `board_test/normalisp/normalisp_uio_test.py`, 새 `isp_dpu_pipeline.py`, `dataset/test/bayer/`, `dataset/test/labels/`, `dpu_sw_optimize.tar.gz`, `arch.json`.
3. 부팅 후 체크리스트(root):
   - `dmesg | grep -i dpu` → `xlnx-dpu ... TARGET_ID 0x101000056010407`, `IP_VER_INFO`, `/dev/dpu` 존재
   - `for d in /sys/class/uio/uio*; do echo $d $(cat $d/name); done` → `normalisp-control`, `normalisp-buffer`
   - `python3 -c "import vart, xir"` 통과; `xdputil query`(vitis-ai-library가 남아 있으면)
   - `./dpu_sw_optimize/zynqmp/zynqmp_dpu_optimize.sh` 실행(PMIC/QoS)
   - 회귀: `python3 run_all_bayer.py /home/root/bayer /home/root/normalisp_out` → 10/10 PASS, 602×400에서 ~142ms(변화 없어야 함)
   - 회귀: `xdputil benchmark models/yolov8n_dpu.xmodel 1` 또는 `run_detector.py --images test_jpg` 로 DPU 단독 동작 확인
4. 이더넷 직결/SSH는 튜토리얼 19-2 그대로(`192.168.10.1/2`, `/home/root/.ssh`).

---

## Phase 4 — 보드 파이프라인 스크립트 (신규) + 실행

**신규 `dfxisp/board_test/normalisp_dpu/isp_dpu_pipeline.py`** — 기존 코드를 import로 재사용, 새 로직은 "RGB888 언팩 + 루프 + 리포트"뿐:

- `from normalisp_uio_test import run_one` (`board_test/normalisp/`) — 8단계 UIO 시퀀스 그대로.
- `from run_detector import DpuSubgraphRunner, preprocess, yolov8_postprocess, ssdlite_postprocess, CLASSES` (`Vitis-AI/app/`).
- 입력: `--bayer-root`(`PASCAL/`, `LOD/` 순회, 파일명 `_(\d+)x(\d+)\.bin$`에서 W×H 파싱 — `run_all_bayer.py`와 동일 정규식), `--model/--xmodel/--anchors/--norm/--conf/--iou`(run_detector와 동일 옵션), `--out JSON`, `--save-png DIR`(검출 박스를 그린 ISP 출력 PNG, PIL).
- 프레임당: `run_one()` → `np.fromfile(out_path, '<u4')` → `((w>>16)&255, (w>>8)&255, w&255)` → `(H,W,3) uint8` → `preprocess` → `dpu.run` → 후처리 → 원본 W×H 좌표로 환산.
- 출력 JSON은 `run_detector.py` 포맷 그대로(키 = 원본 stem + `.png`, 예 `2014_000888.png`)라서 **`eval_map.py`와 `results/recompute.py`를 수정 없이 재사용**. `timing`에 `isp_ms`를 추가.
- 실행 예:
  ```bash
  python3 isp_dpu_pipeline.py --model yolov8n --xmodel models/yolov8n_dpu.xmodel \
      --bayer-root /home/root/bayer --conf 0.001 --out dets_yolov8n_ispdpu.json --save-png vis_yolo
  python3 isp_dpu_pipeline.py --model ssdlite --xmodel models/ssdlite_mbv3_dpu.xmodel \
      --anchors ssdlite_anchors.npy --norm pm1 --bayer-root /home/root/bayer --conf 0.001 --out dets_ssdlite_ispdpu.json
  python3 eval_map.py dets_yolov8n_ispdpu.json /home/root/labels
  ```
- 작은 `run_all.sh`(보드)로 두 모델 + eval을 한 번에.

주의: LOD 5장은 NormalISP(주광용)로 처리하므로 어둡게 나오고 mAP가 낮은 게 정상 — 이번 범위는 "파이프라인 동작 + PASCAL 기준 수치". LowlightISP 스왑은 후속.

---

## Phase 5 — 결과 회수 + 문서

- 회수: `scp root@192.168.10.2:'/home/root/dets_*_ispdpu.json' tutorials/vitisAI/results/board/` (기존 명명 규칙 `dets_<model>_<version>_<SET>.json`에 맞춰 `ispdpu` 버전으로), 시각화 PNG는 `board_test/normalisp_dpu/vis/`.
- 비교표: 같은 10장에 대해 **JPG 레퍼런스 vs (Phase 0) 호스트-체이닝 ISP PNG vs (Phase 4) 온보드 ISP→DPU** mAP50 — 세 번째와 두 번째가 일치해야 정상(같은 픽셀이 들어가므로 bit-동일 기대).
- 문서 **신규 `dfxisp/docs/NormalISP_DPU.md`**: 이 계획의 실측판(NormalISP.md와 같은 형식 — 아키텍처, DPU 파라미터표, 디바이스트리, 레지스터/주소, 실측 수치, 트러블슈팅). `tutorials/vitisAI/docs/VitisAI_Tutorial.md` §24 끝과 `dfxisp/docs/NormalISP.md` §10에 포인터 한 줄씩.

---

## 만들거나 수정하는 파일

| 구분 | 경로 |
|---|---|
| 신규(Vivado) | `dfxisp/NormalISP_DPU/vivado/NormalISP_DPU_zcu104/` (Save As 복제 + DPU 추가), 내보낸 `*.xsa`, `arch.json` |
| 신규(PetaLinux) | `dfxisp/NormalISP_DPU/petalinux/normalisp_dpu_2024_1/` — `bsp.cfg`, `system-user.dtsi`, `rootfs_config`, `user-rootfsconfig`, `vart_3.5.bb`(1줄), `petalinuxbsp.conf` |
| 신규(보드) | `dfxisp/board_test/normalisp_dpu/isp_dpu_pipeline.py`, `run_all.sh` |
| 신규(호스트, 선택) | `dfxisp/tools/isp_png_for_eval.py` (Phase 0 파일명 정리) |
| 신규(문서) | `dfxisp/docs/NormalISP_DPU.md` |
| 수정(문서 포인터) | `dfxisp/docs/NormalISP.md` §10, `tutorials/vitisAI/docs/VitisAI_Tutorial.md` §24 |
| 재사용(수정 없음) | `board_test/normalisp/normalisp_uio_test.py`, `Vitis-AI/app/{run_detector.py, eval_map.py, ssdlite_anchors.npy}`, `Vitis-AI/compiled_output/*.xmodel`, `tools/rgb888_to_png.py`, `results/recompute.py` |

---

## 검증 (end-to-end)

1. **fingerprint 게이트**(Phase 1): Vivado 생성 `arch.json` == `0x101000056010407` == `xir`로 읽은 xmodel `dpu_fingerprint` == 부팅 로그 `TARGET_ID`.
2. **하드웨어 개별 회귀**(Phase 3): `run_all_bayer.py` 10/10 PASS·지연 142/147ms 유지; DPU 단독 `run_detector.py`가 JPG 10장에서 기존 mAP(PASCAL YOLOv8n 0.911급) 재현.
3. **통합**(Phase 4): `isp_dpu_pipeline.py` 10장 전부 예외 없이 완료, JSON의 `isp_ms≈142`, `dpu_ms≈56(YOLO)/16(SSD)`, PNG에 박스가 실제 객체 위에 그려짐.
4. **일관성**: Phase 4 mAP == Phase 0 mAP(같은 ISP 출력 픽셀) — 다르면 언팩 순서(R/G/B 바이트) 또는 리사이즈 경로(cv2 vs PIL) 차이부터 확인.
5. 반복 실행 중 보드 리부팅 없음(`dpu_sw_optimize` 적용).

## 리스크 / 폴백

- **VART vivado 빌드(dnndk 경로) 미검증** → `vart` 단독 빌드로 먼저 확인; `vitis-ai-library`가 깨지면 rootfs에서 제외(파이프라인 영향 없음).
- **DTG가 만드는 DPU 노드 형태**(clocks 순서/interrupts) → 최종 `system.dtb` 디컴파일로 확인 후 dtsi 조정; 드라이버는 clocks를 optional로 취급하므로 compatible+interrupts만 맞으면 probe됨.
- **600MHz 타이밍** → clk gating off → 275/550MHz.
- **fingerprint 불일치** → 새 arch.json으로 `vai_c_xir` 재컴파일(Docker 환경 유지 중).
- **CMA/예약메모리 충돌** → 예약 버퍼 주소 이동(스크립트 상수 1개).

---

## 진행 로그

### Phase 1 완료 (2026-09-11)

- 프로젝트: `NormalISP_DPU/NormalISP_DPU_zcu104/NormalISP_DPU_zcu104.xpr` (BD 이름은 `NormalISP_zcu104_design1` 유지). XSA: `NormalISP_DPU_zcu104/NormalISP_DPU_zcu104_wrapper.xsa` (bit 포함, 4.5MB). `NormalISP_DPU/arch.json` = **`0x101000056010407`** (Vitis 빌드와 동일 → xmodel 재컴파일 불필요).
- DPU 인스턴스 이름은 **`dpuczdx8g_0`**(소문자, VLNV `xilinx.com:ip:dpuczdx8g:4.1`) — 디바이스트리 라벨/compatible이 이걸 따라감. 레지스터 **`0xA100_0000`/16M** (HPM0_FPD 창 0xA000_0000~0xAFFF_FFFF 제약 때문에 TRD의 0x8F00_0000은 불가).
- 배선 확정: `INSTR→smc_dpu_instr→HPC0`, `DATA0→smc_dpu_data0→HP1`, `DATA1→smc_dpu_data1(셀명 smartconnect_0)→HP2` (각 SmartConnect 1:1, 300MHz 도메인, `rst_dpu_300M`), NormalISP는 기존 `axi_smc→HP0` 유지. `clk_wiz_0`: 600(clk_out1→dpu_2x_clk)/300(clk_out2→m_axi_dpu_aclk) Matched Routing, Clock Gating 0. 인터럽트 `xlconcat_0`: In0=dpu0_interrupt, In1=NormalISP interrupt → pl_ps_irq0.
- 실측: WNS +0.072 / WHS +0.010 / WPWS +0.167 ns(전 클럭 통과), LUT 65,525(28.4%) / FF 117,259 / BRAM 84 / **URAM 46** / DSP 738(42.7%).
- 함정 기록: (1) Connection Automation이 DPU 마스터 3개를 NormalISP용 `axi_smc`(100MHz)에 합쳐 HP0 하나로 몰았음 → 수동으로 분리(SmartConnect는 주소 기반 라우팅이라 같은 DDR 범위를 여러 MI로 못 나눔). (2) 재배선 후 stale 주소 세그먼트가 남아 `incomplete addressing path` 에러 → 세그먼트 삭제 후 포트별 명시 배정(`SAXIGP0/HPC0_DDR_LOW`, `SAXIGP3/HP1_DDR_LOW`, `SAXIGP4/HP2_DDR_LOW`, 각 0x0/2G). (3) `report_bd_address`는 없는 명령 — `get_bd_addr_segs`로 확인. (4) 리셋 셀 rename(`rst_dpu_600M`) 후 재생성 안 해 `Could not find module ..._proc_sys_reset_1_0` critical warning — 기능 무관(false-path 제약만 누락).

### Phase 2 완료 (2026-09-11)

- 프로젝트: `NormalISP_DPU/petalinux/normalisp_dpu_2024_1/` — `zcu104_dpu_2024_1`의 `project-spec/`를 rsync로 이식 후 `--get-hw-description`(새 XSA). 오버레이 파일 원본은 `NormalISP_DPU/petalinux/overlay/`.
- 적용한 델타: `bsp.cfg`(XILINX_DPU/UIO/UIO_PDRV_GENIRQ=y), `system-user.dtsi`(NormalISP UIO + 예약메모리 0x70000000/8MiB + `&dpuczdx8g_0` 오버라이드), rootfs `xrt/xrt-dev/zocl` 제거 + `python3-numpy/pillow` 명시, `vart_3.5.bb` `PACKAGECONFIG:append = " python"`(vitis 제거), bootargs `earlycon console=ttyPS0,115200 clk_ignore_unused root=/dev/mmcblk0p2 rw rootwait uio_pdrv_genirq.of_id=generic-uio cma=512M`, 로컬 sstate/downloads 재사용 + 네트워크 sstate 끔, hostname `normalisp-dpu`.
- **DTG가 DPU 노드를 바인딩 그대로 생성** (`compatible = "xlnx,dpuczdx8g-4.1"`, `interrupt-names = "dpu0_interrupt"`, irq 89, clocks dpu_2x/m_axi/s_axi) — IP VLNV가 `xilinx.com:ip:dpuczdx8g:4.1`(소문자)라 별도 compatible 수정이 필요 없었음(dtsi 오버라이드는 동일 값 재기입).
- **VART Vivado 플로우 빌드 통과**: configure `XRT_INCLUDE_DIRS-NOTFOUND` → `dpu_controller_dnndk.cpp`/`sfm_controller_dnndk.cpp`(`/dev/dpu` ioctl) 컴파일, xrt 계열 소스 0건, `site-packages/vart.so` 생성. vitis-ai-library도 XRT 없이 빌드됨(xdputil 사용 가능).
- 전체 빌드 6930 tasks all succeeded. rootfs.manifest: vart/xir/unilog/target-factory/vitis-ai-library 3.5, numpy 1.23.3, pillow 9.4.0, **xrt/zocl 없음**. 최종 `system.dtb`에서 DPU/NormalISP/예약메모리/bootargs 전부 확인. `BOOT.BIN` 21MB(비트스트림 포함).
- 보드용 스크립트 작성: `board_test/normalisp_dpu/{isp_dpu_pipeline.py, run_all.sh, stage_sd.sh}` — 호스트에서 `rgb888_to_array`가 기존 `tools/rgb888_to_png.py` 결과와 픽셀 단위 동일함을 확인.

### 다음 세션 재개 지점 (2026-09-11 종료 시점)

- ✅ Phase 1(Vivado), Phase 2(PetaLinux) 완료. `images/linux/petalinux-sdimage.wic`(6.4GB), `BOOT.BIN`(21MB) 생성됨.
- ⬜ **Phase 3 시작 전**: `dd`는 아직 실행 안 됨(SD카드 `/dev/sda`에 이전 v++ 이미지 976M+2.5G 파티션 그대로). 재개 순서:
  1. `cd ~/Desktop/dfxisp/board_test/normalisp_dpu && ./stage_sd.sh` → `stage/`
  2. `lsblk`로 장치 확인 → `sudo dd if=.../images/linux/petalinux-sdimage.wic of=/dev/sda bs=4M status=progress conv=fsync`
  3. `sda2`(ext4) 마운트 → `stage/.`를 `/home/root/`에 복사, `chown root:root`, `umount`
  4. 부팅 체크리스트(§Phase 3) → `run_all_bayer.py`(ISP 회귀) → `run_detector.py`(DPU 회귀) → `app/run_all.sh`(통합, Phase 4)

### Phase 3~4 완료 — 보드 실물 통합 검증 (2026-09-14)

SD카드(`petalinux-sdimage.wic`) 부팅 → 드라이버/UIO 확인 → 회귀 2종 → 통합 파이프라인까지 전부 통과.

**브링업 확인:**
- `/dev/dpu`(misc 10,126) 생성, `xdputil query` → `fingerprint 0x101000056010407`(빌드값 일치), `DPUCZDX8G_ISA1_B4096`, IP v4.1.0, DPU 300MHz / **XRT(s_axi) 100MHz**.
- UIO: `uio0 normalisp-buffer` 0x70000000/0x800000, `uio1 normalisp-control` 0xa0000000/0x10000 (uio2~5는 axi-pmon).
- `import vart, xir, numpy, PIL` OK (XRT/zocl 없이 동작).
- 예약메모리 `0x70000000..0x707fffff nomap`, `cma: Reserved 512 MiB at 0x50000000` — 겹침 없음.
- **DPU/UIO 드라이버는 probe 성공 시 dmesg에 아무것도 안 찍는다**(`dev_dbg`만) — 노드 존재로 판정할 것.

**회귀:** NormalISP 단독 10/10 PASS, 602×400 **142.22ms** / 610×408 **146.99ms** — 2026-09-04 단독 이미지와 소수점까지 동일(DPU 추가가 ISP 경로에 영향 없음). DPU 단독(JPG) 검출 정상.

**통합 실행** (`board_test/normalisp_dpu/run_all.sh`, conf 0.001):

| 모델 | ISP | pre | DPU | post | total |
|---|---|---|---|---|---|
| YOLOv8n | 144.6ms | 52.0 | **64.8** | 110.9 | 372.3ms (2.69 FPS) |
| SSDLite | 144.6ms | 27.0 | **16.0** | 302.5 | 490.2ms (2.04 FPS) |

post가 큰 건 mAP용 `--conf 0.001` 때문(클래스별 top-300이 전부 NMS). DPU 64.8ms는 이전 Vitis 이미지의 55.7ms보다 ~16% 느린데, 유력 원인은 **`s_axi_aclk`를 pl_clk0(100MHz)에 물린 것**(Vitis 빌드 IP는 `S_AXI_FREQ_MHZ=300`). 고치려면 BD에서 `dpuczdx8g_0/s_axi_aclk`를 `clk_wiz_0/clk_out2`로 옮기고 재합성 — 기능 영향 없음, 선택 사항.

**mAP (보드 INT8, 같은 10장, conf 0.001, labels=dataset/test/labels):**

| 입력 | 셋 | YOLOv8n mAP50 / 50-95 | SSDLite mAP50 / 50-95 |
|---|---|---|---|
| JPG 레퍼런스 | PASCAL(13 GT) | 0.7917 / 0.5893 | 0.7834 / 0.4960 |
| **NormalISP 출력** | PASCAL | **0.7917 / 0.5762** | **0.7865 / 0.4632** |
| JPG 레퍼런스 | LOD(68 GT) | 0.5046 / 0.3104 | 0.3223 / 0.1857 |
| **NormalISP 출력** | LOD | **0.3213 / 0.1256** | **0.1524 / 0.0774** |

- **주광(PASCAL)에서는 NormalISP 출력이 레퍼런스 JPG와 동등** (mAP50 동일, 50-95만 −0.01~−0.03) — ISP 색/감마 도메인이 검출기에 문제되지 않음을 실측으로 확인.
- **저조도(LOD)는 큰 폭 하락**(YOLO −0.18, SSDLite −0.17). 원인 두 가지: (1) 레퍼런스 JPG는 1280×855인데 ISP 입력은 RAW 전체화각 비닝으로 610×408, (2) NormalISP에는 노출 게인이 없어 프레임 평균 밝기 2.5~8. → LowlightISP 스왑의 정량적 근거.
- 표본이 도메인당 5장(13/68 GT)이라 절대값보다 JPG-대비 차이를 볼 것.

**PMIC(`irps5401`) 함정:** `zynqmp_dpu_optimize.sh`는 `set -e`인데 첫 단계 `ext4_resize`가 `parted`/`resize2fs` 없어서 실패 → **QoS/PMIC 단계가 아예 실행되지 않는다.** QoS는 `source functions/zynqmp_qos_en.sh && qos_config`로 수동 적용(HP0~3/HPC0~1 RD/WRISSUE 0x7→0xf, 적용해도 DPU 시간은 변화 없었음). PMIC 툴은 커널 `CONFIG_SENSORS_IRPS5401=y`가 0x43을 점유해 `EBUSY` → `echo 4-0043 > /sys/bus/i2c/drivers/irps5401/unbind` 후 실행해야 하며, 그래도 `OC fault limit is not 37A`가 나온다(툴이 LINEAR11 비트패턴 `0xF094`와 정확히 일치하는지만 보는데 칩이 다른 지수로 정규화해 돌려주면 실패). 확인용 스크립트 `board_test/normalisp_dpu/pmbus_oc_check.py`(i2c-tools 없이 ioctl로 페이지별 값을 A 단위로 디코드). **PMIC 미적용 상태로 전체 실행에서 리부팅 없음** — DPU 1코어라 TRD 기본(3코어)보다 소비전류가 낮음.

### 100장 본 실험 (2026-09-14)

`dataset/{PASCAL_test,LOD_test}`의 RAW 200장을 두 해상도로 변환해 보드에서 4회(모델2×해상도2) + JPG 대조군 4회 실행.

- 호스트 변환: `tools/batch_raw_to_bayer.sh`(신규, xargs 병렬) → `dataset/bayer100/`(640 박스: PASCAL 602×400, LOD 610×408, 94MB), `dataset/bayer100_hi/`(1280 박스: PASCAL 1206×802, LOD 1098×734, 339MB). 최대 프레임도 예약 슬롯(raw 2MiB/rgb 4MiB) 안에 들어감(1.84/3.69 MiB).
- 보드 스크립트: `board_test/normalisp_dpu/{stage_exp100.sh, run_exp100.sh}`, `isp_dpu_pipeline.py`에 `--drop-isp`(프레임마다 RGB888 삭제 — 고해상도 200장이면 ~800MB 절약)와 `--progress N` 추가.
- 결과: `board_test/normalisp_dpu/results100/`. 상세 표와 해석은 `docs/NormalISP_DPU.md` §6-1/6-2로 이관.
- 핵심: **주광 YOLOv8n은 JPG 상한과 동등**(0.9068 vs 0.9105), **저해상도 손해는 색이 아니라 비닝 배율**(isp_lo 602×400은 JPG와 같은 크기인데 −0.037, K만 낮춘 isp_hi에서 −0.004로 소멸), **저조도는 해상도를 올려도 −0.20 잔존**(노출 게인 부재 → LowlightISP 근거). ISP 지연은 픽셀 수에 정확히 비례(144.6ms → 523.6ms, 예측과 일치), DPU 시간은 입력 해상도와 무관(65/16ms).
- 운영 함정: 보드 rootfs가 3.8G(wic가 이미지 크기만큼만 파티션 생성) → 호스트에서 `parted resizepart 2 100%` + `e2fsck -f` + `resize2fs`로 확장(재굽기 불필요). 보드에 `rsync`/`parted`/`resize2fs`/`i2c-tools` 없음. `scp -r dir/.`는 OpenSSH 9.x에서 거부되므로 `tar -cf - . | ssh ... tar -xf -` 사용. `/home/root`는 root 소유라 petalinux 계정으로 전송하려면 대상 디렉토리를 미리 만들고 `chown`. 수동 설정한 보드 IP는 재부팅 시 사라짐(영구화: `/etc/systemd/network/10-eth0-static.network`).
