# LowlightISP + DPU(Vitis-AI) 통합 — 실험 가이드

`~/Desktop/dfxisp/LowlightISP_DPU/`, `~/Desktop/dfxisp/board_test/lowlightisp/`

## 무엇인가

`NormalISP_DPU`(docs/NormalISP_DPU.md)와 **완전히 같은 조건**에서 ISP만 `LowlightISP`로 바꿔 돌리는 실험이다. 목적은 하나다 — `NormalISP_DPU.md` §6-2가 남긴 질문에 수치로 답하는 것:

> 저조도(LOD)는 해상도를 올려도 JPG 상한 대비 **−0.20**이 남는다. NormalISP에 노출 게인이 없어 출력 평균 밝기가 2.5~8에 머무는 것이 지배적 원인 — **`LowlightISP`(2× 노출 게인 + 2×2 same-colour binning)가 필요한 이유이자, 그 개선폭을 재는 대조군이 이 표다.**

즉 이 실험의 산출물은 "LowlightISP가 그 −0.20 중 얼마를 되찾는가"이고, 대조군은 이미 측정돼 있다(`board_test/normalisp_dpu/results100/`). 검출기·xmodel·후처리·평가 코드·입력 Bayer 파일까지 전부 동일하게 두고 **PL의 ISP 하나만 교체**한다.

```
RAW Bayer(.bin) ─UIO─► LowlightISP (PL) ─► 0x00RRGGBB @DDR ─numpy 언팩─► (H/2)x(W/2)x3 uint8
                          2× 노출 게인                        │
                          2×2 same-colour binning             ▼
                                            resize/정규화 ─► vart.Runner (DPU) ─► NMS ─► dets JSON ─► mAP
```

## 상태 (2026-09-15)

- ✅ 보드 스크립트 일체 + 호스트 스테이징 번들(446 MB) — `board_test/lowlightisp/`
- ✅ Vivado: IP 스왑 BD → 비트스트림/XSA, **타이밍 통과**(WNS +0.052 / WHS +0.010 ns), 리소스는 `NormalISP_DPU`와 거의 동일 (§1-1)
- ✅ PetaLinux 2024.1 이미지 — `BOOT.BIN`(21 MB) + `petalinux-sdimage.wic`(6.4 GB), 디바이스트리/rootfs 검증 완료 (§2-1)
- ✅ 보드 실물: SD 굽기 → 부팅 → UIO `lowlightisp-*` + `/dev/dpu`, fingerprint `0x101000056010407` 일치 → xmodel 재사용 확정
- ✅ end-to-end **200장 × 2해상도 × 2모델** 완료 — 저조도에서 NormalISP 대비 **+0.021/+0.030 mAP50**(해상도 맞춘 비교), 상세는 §7

---

## 1. 하드웨어 — IP 스왑

`NormalISP_DPU.md` §8의 "포트 시그니처가 동일하므로 BD에서 IP만 교체"를 그대로 실행한 것이다. 두 HLS IP의 인터페이스가 실제로 동일함을 `component.xml`에서 확인했다:

| | `s_axi_control` | `m_axi_gmem0/1` | 기타 |
|---|---|---|---|
| NormalISP | ADDR_WIDTH 7 | DATA_WIDTH 32 | `ap_clk`, `ap_rst_n`, `interrupt` |
| LowlightISP | ADDR_WIDTH 7 | DATA_WIDTH 32 | 동일 |

GUI 작업 대신 **재현 가능한 스크립트**로 만들었다:

```bash
cd LowlightISP_DPU/vivado
vivado -mode batch -source build_lowlightisp_dpu.tcl              # jobs 2 (기본)
```

| 파일 | 역할 |
|---|---|
| `LowlightISP_DPU/vivado/LowlightISP_DPU_design1_bd.tcl` | BD 정의. `NormalISP_DPU`에서 `write_bd_tcl -no_ip_version`으로 뽑아 `NormalISP`→`LowlightISP` 치환 |
| `LowlightISP_DPU/vivado/build_lowlightisp_dpu.tcl` | 프로젝트 생성 → IP repo 등록 → BD → wrapper → synth/impl → XSA(비트스트림 포함) |

**등가성 검증(치환을 되돌려 diff):** design name, 아래 exclude 처리 2건을 빼면 원본과 완전히 같다 — DPU IP의 CONFIG 전 항목, 세 클럭 도메인(100/300/600MHz), HPC0/HP1/HP2 분리, 인터럽트 concat, 주소 할당(`control @0xA000_0000`, `DPU @0xA100_0000`)이 모두 동일. 따라서 **fingerprint는 `0x101000056010407` 그대로**이고 컴파일해 둔 xmodel을 재사용한다(`run_smoke.sh` 2단계가 보드에서 이걸 실제로 확인한다).

**exclude_bd_addr_seg 처리 (빌드 시행착오):** 내보낸 스크립트는 `NormalISP_DPU`의 저장된 BD에 남아 있던 "도달 불가능한 master/slave 쌍"의 제외 지시까지 재생한다(ISP gmem→HP1, DPU INSTR→HP0). 깨끗한 프로젝트에서는 `ERROR: [BD 5-292] ... is not addressable by ...`로 죽는다. 도달 불가능한 세그먼트를 제외하는 건 정의상 no-op이므로 해당 호출을 `catch`로 감싸고(진짜 실패는 로그에 남는다), ISP→HP1 2줄은 삭제했다.

**병렬 작업 수:** 이 머신(14 GB)에서 `-jobs 8`은 스왑 13 GB를 쓰며 스래싱한다. 기본값을 2로 낮춰 두었다.

빌드 산출물: `LowlightISP_DPU/LowlightISP_DPU_zcu104/LowlightISP_DPU_zcu104_wrapper.xsa`(4.5 MB, 비트스트림 포함), `utilization_impl.rpt`, `timing_summary_impl.rpt`.

### 1-1. 구현 결과 (impl_1, 2026-09-15)

| 항목 | LowlightISP_DPU | NormalISP_DPU (대조, 2026-09-11) |
|---|---|---|
| 타이밍 | WNS **+0.052** / WHS +0.010 ns | +0.072 / +0.010 ns |
| CLB LUT | 65,004 (28.2%) | 65,525 (28.4%) |
| CLB FF | 115,453 (25.1%) | 117,259 (25.5%) |
| BRAM / URAM / DSP | 84 (26.9%) / 46 (47.9%) / 724 (41.9%) | 84 / 46 / 738 |

LowlightISP가 NormalISP보다 **LUT −521, DSP −14**로 근소하게 작다(비닝 ISP라 파이프라인이 짧다). DPU 영역은 손대지 않았으므로 타이밍 여유도 같은 수준이고, fingerprint 불변 가정이 리소스 면에서도 뒷받침된다.

---

## 2. PetaLinux 2024.1

```bash
cd LowlightISP_DPU/petalinux && ./build_petalinux.sh
```

`NormalISP_DPU.md` §2에서 검증된 `project-spec/`을 **통째로 복제**하고 딱 두 가지만 바꾼다. 커널 config(`CONFIG_XILINX_DPU`/`UIO`/`UIO_PDRV_GENIRQ`), rootfs(xrt/zocl 제거, numpy/pillow 추가), VART의 `PACKAGECONFIG:append = " python"`(XRT 없이 빌드), bootargs(`cma=512M` 등)는 복제로 그대로 따라온다 — 스크립트가 이 네 가지가 실제로 넘어왔는지 확인한 뒤 진행한다.

| 바뀌는 것 | 내용 |
|---|---|
| 디바이스트리 | `LowlightISP_DPU/petalinux/overlay/system-user.dtsi` — `&LowlightISP_0` → `lowlightisp-control`, 예약메모리 + `lowlightisp-buffer` |
| 하드웨어 | §1의 XSA |

빌드 산출물: `lowlightisp_dpu_2024_1/images/linux/{BOOT.BIN, petalinux-sdimage.wic, image.ub, system.dtb}`.

### 2-1. 이미지 검증 (호스트에서, 굽기 전)

`system.dtb`를 역컴파일해 확인한 것 — 보드에서 틀리면 되돌리는 비용이 큰 항목들이다:

```
LowlightISP@a0000000   compatible "generic-uio"  linux,uio-name "lowlightisp-control"  reg 0xa0000000/0x10000
lowlightisp-buffer@70000000  "generic-uio"  "lowlightisp-buffer"  reg 0x70000000/0x800000
reserved-memory/buffer@70000000  no-map  0x70000000/0x800000
dpuczdx8g@a1000000  "xlnx,dpuczdx8g-4.1"  interrupt-names "dpu0_interrupt"
bootargs: ... uio_pdrv_genirq.of_id=generic-uio cma=512M
__symbols__: LowlightISP_0, dpuczdx8g_0, lowlightisp_reserved, lowlightisp_buffer
```

rootfs: `vart`/`xir`/`vitis-ai-library` 3.5, `python3-numpy` 1.23.3, `python3-pillow` 9.4.0 포함, **`xrt`/`zocl` 0개**. 커널 `.config`에 `CONFIG_XILINX_DPU=y`, `CONFIG_UIO=y`, `CONFIG_UIO_PDRV_GENIRQ=y`.

### 2-2. 빌드 함정 (2026-09-15 실측)

- `petalinux-create`는 2024.1에서 **`-p/--path`가 없다** — 만들 위치로 `cd`한 뒤 실행해야 한다.
- `petalinux-package`는 **프로젝트 루트에서** 실행해야 한다(CWD로 프로젝트를 찾는다). `images/linux`에서 파일명만 주면 실패.
- **bitbake 기본 병렬도가 `nproc`(=16)이라 14 GB 머신에서 OOM으로 죽는다** — 태스크 3,448/6,887 부근에서 커널이 죽였다. `petalinuxbsp.conf`에 `BB_NUMBER_THREADS`/`PARALLEL_MAKE`를 박아 해결(스크립트가 자동으로 넣는다). bitbake는 증분이라 `RESUME=1 ./build_petalinux.sh`로 이어서 돌리면 된다 — 실제로 그렇게 끝냈다.
- 같은 이유로 Vivado도 `-jobs 8`이면 스왑 13 GB를 쓰며 스래싱한다(§1).

라벨은 **`&LowlightISP_0`**(대소문자 그대로, `docs/LowlightISP.md` §5). sstate 캐시와 다운로드 미러는 `normalisp_dpu_2024_1`의 것을 재사용하도록 스크립트가 `configs/config`를 고쳐 쓴다. `petalinux-build`는 죽은 AMD 미러 때문에 성공해도 exit code가 non-zero다 — 스크립트는 `Tasks Summary`의 `all succeeded`로 판정한다.

---

## 3. 메모리 레이아웃 — NormalISP와 동일, 단 쓰는 양이 다르다

정적 셸의 데이터 계약이 어느 ISP가 올라갔는지에 무관해야 나중에 DFX가 성립하므로 **주소·크기를 그대로 유지**한다.

| 슬롯 | 주소 | NormalISP가 쓰는 양 | LowlightISP가 쓰는 양 |
|---|---|---|---|
| raw_bayer | `0x7000_0000` +0 (2 MiB) | `W×H×2` | 동일 (입력 포맷 같음) |
| rgb_out | `0x7020_0000` (6 MiB) | `W×H×4` | **`(W/2)×(H/2)×4`** |

**입력이 2 MiB를 넘으면 안 된다** = 최대 1,048,576 픽셀. 이 실험의 최대 입력인 PASCAL `1206×802`가 1.93 MB로 상한 바로 아래다. `lowlight_isp_dpu_pipeline.py`의 `preflight()`가 프레임마다 미리 검사해서, 넘으면 IP를 건드리기 전에 중단한다(안 그러면 raw가 rgb 슬롯을 덮어쓴 채로 "동작하는 것처럼" 끝난다).

---

## 4. 실험 설계 — 어떤 쌍을 비교하는가

LowlightISP는 2×2로 비닝하므로 **검출기가 보는 해상도가 입력의 절반**이다. 그래서 "같은 파일을 넣는 것"과 "같은 해상도를 비교하는 것"이 서로 다른 실험이 된다. 둘 다 돌린다.

| 입력 세트 | 박스 | 입력 (PASCAL / LOD) | NormalISP 출력 | LowlightISP 출력 |
|---|---|---|---|---|
| `bayer_lo` (`dataset/bayer100`) | 640×480 | 602×400 / 610×408 | 602×400 / 610×408 | **301×200 / 305×204** |
| `bayer_hi` (`dataset/bayer100_hi`) | 1280×960 | 1206×802 / 1098×734 | 1206×802 / 1098×734 | **603×401 / 549×367** |

- **`llisp_hi` ↔ `isp_lo` 가 본 비교다.** 603×401 vs 602×400 — 출력 해상도가 사실상 같다. 같은 장면·같은 검출기·같은 픽셀 수이므로 차이는 ISP(노출 게인 + same-colour binning) 하나로 귀속된다. §6-2가 "저해상도에서의 손해는 색이 아니라 비닝 배율 때문"이라고 분리해 낸 것과 같은 논법.
- **`llisp_lo` ↔ `isp_lo` 는 같은 입력 파일 비교**다. 여기선 LowlightISP가 절반 해상도로 불리하므로, 게인의 이득과 해상도의 손실이 섞인 수치가 나온다.
- **NormalISP `isp_hi`에 대응하는 LowlightISP 조건은 만들 수 없다.** 1206×802를 출력하려면 입력이 ~2412×1604여야 하는데 (a) raw 슬롯 2 MiB를 3배 초과하고 (b) `raw_to_bayer_bin.py`의 비닝 배율 K는 정수라 그 크기가 애초에 나오지 않는다(PASCAL은 K=2→3010×2000, K=3→2006×1333). 디바이스트리 레이아웃을 바꾸면 가능하지만, 그러면 §3의 "정적 셸 데이터 계약 고정"을 깨므로 하지 않는다.
- **JPG 대조군은 다시 재지 않는다.** ISP와 무관하게 같은 값이므로 `normalisp_dpu/results100/dets_*_jpg_*.json`을 그대로 상한으로 쓴다(`JPG=1`로 재측정은 가능).

---

## 5. 보드/호스트 소프트웨어

| 파일 | 역할 |
|---|---|
| `board_test/lowlightisp/lowlight_isp_dpu_pipeline.py` | 본체. `isp_dpu_pipeline.py`의 LowlightISP판 — 프레임마다 `run_one()` → RGB888 언팩 → DPU → 원본 좌표 환산 |
| `board_test/lowlightisp/run_smoke.sh` | 본실험 전 5분 점검: 디바이스 노드 → fingerprint → ISP 단독 10장 → ISP→DPU 10장(PNG) |
| `board_test/lowlightisp/run_exp100_lowlight.sh` | 본실험: 2해상도 × 2모델 × 200장 + 도메인별 mAP |
| `board_test/lowlightisp/stage_exp100_lowlight.sh` | 호스트에서 보드용 일체(스크립트/xmodel/bayer/labels) 수집 → `stage100L/` |
| `board_test/lowlightisp/compare_lowlight_vs_normal.py` | 호스트에서 두 실험 결과를 합쳐 비교표(정확도/델타/지연) 생성 |
| `board_test/lowlightisp/lowlightisp_uio_test.py`, `run_all_bayer_lowlight.py` | 기존 브링업 스크립트, **수정 없이 재사용** |

**재사용(수정 없음):** `Vitis-AI/app/{run_detector.py, eval_map.py, ssdlite_anchors.npy}`, `compiled_output/*.xmodel`, `dataset/bayer100{,_hi}`의 Bayer 파일(입력 포맷이 NormalISP와 동일).

**NormalISP판과의 유일한 구조적 차이**는 "출력 크기를 입력에서 계산하지 않는다"는 점이다. 읽어 들일 RGB888 바이트 수, 모델 입력(정사각)에서 되돌리는 박스 스케일, `eval_map.py`가 라벨을 역정규화할 때 쓰는 JSON의 `width`/`height` — 셋 다 레지스터 `0x38`/`0x48`에서 read-back한 **출력** 크기를 쓴다. 한 군데라도 입력 크기를 넣으면 박스 좌표가 조용히 절반이 되고, mAP만 0에 가깝게 나온다.

---

## 6. 실행 순서

```bash
# 호스트
cd LowlightISP_DPU/vivado    && vivado -mode batch -source build_lowlightisp_dpu.tcl
cd ../petalinux              && ./build_petalinux.sh
lsblk                                                       # SD 장치 확인
sudo dd if=lowlightisp_dpu_2024_1/images/linux/petalinux-sdimage.wic of=/dev/sdX bs=4M status=progress conv=fsync
cd ../../board_test/lowlightisp && ./stage_exp100_lowlight.sh
rsync -a --info=progress2 stage100L/ petalinux@192.168.10.2:/home/root/exp100L/

# 보드 (root)
cd /home/root/exp100L/app
MODELS=/home/root/exp100L/models ./run_smoke.sh             # 여기서 fingerprint까지 확인됨
MODELS=/home/root/exp100L/models ./run_exp100_lowlight.sh   # ~30분

# 호스트 (결과 회수 + 표 생성)
rsync -a petalinux@192.168.10.2:/home/root/exp100L/results/ board_test/lowlightisp/results100L/
python3 board_test/lowlightisp/compare_lowlight_vs_normal.py
```

SD카드로 결과를 옮길 때는 **`sync`만으로 부족하고 `umount`까지** 해야 한다(`docs/LowlightISP.md` §9의 0바이트 파일 함정).

---

## 7. 결과 (2026-09-15, 보드 INT8, conf 0.001, 200장)

원자료: `board_test/lowlightisp/results100L/` (`dets_*.json` 12개, `map_summary.log`, 실행 로그 4개, `run_board.log`). 표 재생성은 호스트에서 `python3 board_test/lowlightisp/compare_lowlight_vs_normal.py` — 결정적이다.

### 7-1. 정확도

`jpg`/`NormalISP` 행은 `NormalISP_DPU.md` §6-2의 대조군을 같은 스크립트로 다시 계산한 것이다(값 일치).

| 모델 | 셋 | 입력 | 출력 해상도 | mAP50 | mAP50-95 | bicycle / car / person (AP50) |
|---|---|---|---|---|---|---|
| YOLOv8n | PASCAL | jpg | 600×400 | 0.9105 | 0.6311 | 0.927 / 0.904 / 0.900 |
| YOLOv8n | PASCAL | NormalISP lo | 602×400 | 0.8733 | 0.5660 | 0.882 / 0.855 / 0.882 |
| YOLOv8n | PASCAL | NormalISP hi | 1206×802 | 0.9068 | 0.6328 | 0.942 / 0.883 / 0.895 |
| YOLOv8n | PASCAL | **LowlightISP hi** | **603×401** | **0.8713** | **0.5908** | 0.920 / 0.871 / 0.823 |
| YOLOv8n | PASCAL | LowlightISP lo | 301×200 | 0.7073 | 0.4574 | 0.570 / 0.843 / 0.709 |
| YOLOv8n | LOD | jpg | 1280×855 | 0.5896 | 0.3285 | 0.631 / 0.527 / 0.611 |
| YOLOv8n | LOD | NormalISP lo | 610×408 | 0.3021 | 0.1275 | 0.311 / 0.281 / 0.315 |
| YOLOv8n | LOD | NormalISP hi | 1098×734 | 0.3886 | 0.1820 | 0.411 / 0.350 / 0.405 |
| YOLOv8n | LOD | **LowlightISP hi** | **549×367** | **0.3232** | **0.1504** | 0.290 / 0.324 / 0.355 |
| YOLOv8n | LOD | LowlightISP lo | 305×204 | 0.2071 | 0.0836 | 0.212 / 0.189 / 0.221 |
| SSDLite | PASCAL | jpg | 600×400 | 0.8487 | 0.5035 | 0.915 / 0.852 / 0.780 |
| SSDLite | PASCAL | NormalISP lo | 602×400 | 0.7096 | 0.3904 | 0.862 / 0.715 / 0.552 |
| SSDLite | PASCAL | NormalISP hi | 1206×802 | 0.7742 | 0.4293 | 0.878 / 0.800 / 0.644 |
| SSDLite | PASCAL | **LowlightISP hi** | **603×401** | **0.6672** | **0.3689** | 0.865 / 0.710 / 0.426 |
| SSDLite | PASCAL | LowlightISP lo | 301×200 | 0.6445 | 0.3370 | 0.850 / 0.672 / 0.411 |
| SSDLite | LOD | jpg | 1280×855 | 0.4893 | 0.2644 | 0.529 / 0.483 / 0.456 |
| SSDLite | LOD | NormalISP lo | 610×408 | 0.2759 | 0.1310 | 0.281 / 0.239 / 0.307 |
| SSDLite | LOD | NormalISP hi | 1098×734 | 0.3332 | 0.1621 | 0.410 / 0.260 / 0.329 |
| SSDLite | LOD | **LowlightISP hi** | **549×367** | **0.3056** | **0.1535** | 0.321 / 0.259 / 0.338 |
| SSDLite | LOD | LowlightISP lo | 305×204 | 0.2502 | 0.1147 | 0.247 / 0.203 / 0.300 |

### 7-2. 델타 (mAP50)

| 모델 | 셋 | **llisp_hi − isp_lo** (해상도 맞춘 본 비교) | llisp_hi − isp_hi | llisp_lo − isp_lo (같은 입력) | llisp_hi − jpg |
|---|---|---|---|---|---|
| YOLOv8n | PASCAL | −0.002 | −0.036 | −0.166 | −0.039 |
| YOLOv8n | **LOD** | **+0.021** | −0.065 | −0.095 | −0.266 |
| SSDLite | PASCAL | −0.042 | −0.107 | −0.065 | −0.182 |
| SSDLite | **LOD** | **+0.030** | −0.028 | −0.026 | −0.184 |

### 7-3. 읽는 법

1. **저조도에서 LowlightISP가 이긴다 — 다만 폭이 작다.** 해상도를 맞춘 비교에서 LOD는 YOLOv8n +0.021, SSDLite +0.030이다. 게다가 LOD에서는 LowlightISP 쪽이 픽셀이 **19% 적다**(549×367 = 201k vs 610×408 = 249k). 불리한 조건에서 이겼으니 게인·비닝의 효과는 실재한다. 그러나 §6-2가 남긴 jpg 상한까지의 −0.20~−0.29 중 되찾은 건 **10~15%뿐**이다.
2. **주광은 망가지지 않았다(YOLOv8n 기준).** PASCAL에서 −0.002로 사실상 동일 — 2× 게인이 하이라이트를 날리지 않는다는 뜻. 다만 **SSDLite PASCAL은 −0.042**이고 person AP50이 0.552→0.426으로 두드러지게 나쁘다. SSDLite가 도메인 변화에 약하다는 §6-2의 관측과 같은 방향이다.
3. **왜 폭이 작은가 — 출력이 여전히 너무 어둡다.** 같은 LOD 5장에서 출력 평균을 재 보면:

   | 프레임 | NormalISP (R/G/B) | LowlightISP (R/G/B) |
   |---|---|---|
   | DSC01845 | 4.9 / 8.3 / 4.0 | 5.7 / **12.4** / 4.5 |
   | DSC02077 | 5.2 / 6.6 / 4.4 | 4.3 / **10.6** / 2.7 |
   | DSC02790 | 5.1 / 8.4 / 4.4 | 5.1 / **13.3** / 2.9 |
   | DSC02903 | 2.5 / 3.3 / 2.0 | 3.3 / **5.5** / 1.3 |
   | DSC03927 | 45.4 / 52.1 / 37.2 | 51.9 / **76.2** / 28.3 |

   녹색만 1.5~1.7× 오르고 **R은 제자리, B는 오히려 낮아진다** — 두 ISP의 WB 상수(`WB_*_Q8`)가 다른 탓이라 실효 휘도 이득은 2×가 아니라 1.3~1.5×에 그친다. 평균 5~13/255는 여전히 "거의 검은 화면"이고, JPG 레퍼런스와의 간극 대부분이 여기서 나온다. **노출 게인을 더 올리는 것(`EXPOSURE_GAIN_Q8`)이 다음 레버이고, B 채널이 깎이는 WB 상수도 함께 봐야 한다.**
4. **비닝은 저조도에서 남는 장사, 주광에서는 손해다.** 같은 입력 비교(`llisp_lo − isp_lo`)에서 LOD는 −0.095/−0.026인데 PASCAL YOLOv8n은 −0.166이다. 저조도에서는 4픽셀 평균이 노이즈를 줄여 해상도 손실을 상당 부분 갚지만, 주광에서는 갚을 노이즈가 없어 손실만 남는다. PASCAL bicycle AP50이 0.882→0.570으로 무너지는 것이 그 증거(작은 객체가 먼저 사라진다).

### 7-4. 지연시간

| 구성 | ISP | pre | DPU | post | total |
|---|---|---|---|---|---|
| YOLOv8n · LowlightISP lo (→301×200) | **63.2** | 46.0 | 65.6 | 100.3 | 275.1 ms (3.63 FPS) |
| YOLOv8n · LowlightISP hi (→603×401) | **228.8** | 50.8 | 65.5 | 100.9 | 446.0 ms (2.24 FPS) |
| (대조) YOLOv8n · NormalISP lo | 144.6 | 51.6 | 65.7 | 109.1 | 371.1 ms (2.69 FPS) |
| (대조) YOLOv8n · NormalISP hi | 523.6 | 72.3 | 63.5 | 108.4 | 767.8 ms (1.30 FPS) |
| SSDLite · LowlightISP lo | 63.2 | 20.6 | 15.8 | 306.2 | 405.8 ms (2.46 FPS) |
| SSDLite · LowlightISP hi | 228.8 | 27.3 | 16.5 | 309.1 | 581.6 ms (1.72 FPS) |

- **입력 픽셀당으로는 LowlightISP가 2.4× 빠르다** (0.237 µs/px vs NormalISP 0.601 µs/px) — 픽셀 루프가 출력(비닝된) 격자를 도니 반복 횟수가 1/4이다. 같은 1206×802 입력에서 228.8 ms vs 523.6 ms.
- **출력 해상도당으로는 1.6× 느리다** (603×401을 만드는 데 228.8 ms, NormalISP가 602×400을 만드는 데 144.6 ms) — 4배 넓은 RAW를 읽어야 하기 때문. 정확도 +0.02~0.03을 이 비용으로 산 셈이다.
- DPU 시간은 여기서도 입력 해상도와 무관(65.5 / 16.5 ms), 전처리는 ISP 출력이 작아진 만큼 NormalISP보다 싸다(50.8 vs 72.3 ms).

### 7-5. 실행 중 잡은 버그 — Device 메모리 비정렬 SIGBUS

`hi` 런 두 개가 처음에 **에러 메시지 없이** 죽었다(exit 135 = SIGBUS). 예약 영역이 `no-map` + generic-uio라 **Device 메모리**로 매핑되는데, ARM64에서는 memcpy 길이가 8의 배수가 아니면 비정렬 접근이 정렬 폴트를 일으킨다. 보드 실측:

| 읽기 길이 | mod 8 | 결과 |
|---|---|---|
| 967,212 | 4 | SIGBUS |
| 967,216 | 0 | OK |
| 967,220 | 4 | SIGBUS |
| 967,224 | 0 | OK |

시작 오프셋은 무관했다 — **길이만의 문제**다. LowlightISP가 이 코드 경로에서 처음으로 그런 길이를 만든다: 2×2 비닝이라 출력이 603×401처럼 홀수×홀수가 될 수 있고 `603·401·4 = 967,212`가 4 mod 8이다. `lo`(301×200, 305×204)는 높이가 짝수라 우연히 16의 배수였고, NormalISP는 출력이 입력의 짝수 치수를 유지해 구조적으로 이 경우가 안 나온다. `lowlightisp_uio_test.py`가 이제 전송 길이를 16바이트로 올림해 읽고 잘라낸다(쓰기도 동일). **`normalisp_uio_test.py`에도 같은 잠재 버그가 있다** — 현재 입력 형상에서는 발현하지 않지만, 홀수 치수를 쓰게 되면 같은 한 줄 수정이 필요하다.

---

## 8. 다음 단계

- **checker 추가** — static shell에 `checker_scan`(`docs/checker.md`). 주소는 `0xA001_0000`대가 비어 있다.
- **DFX 전환** — 이 실험이 끝나면 "같은 정적 셸·같은 데이터 계약에서 두 ISP가 각각 동작함"이 DPU 포함 구성에서도 실증된 상태가 된다. 남은 건 두 정적 비트스트림을 상호배타 RM으로 합치는 것(SPEC.md §7, PG374).

## 참고

- `docs/NormalISP_DPU.md` — 대조군 실험 전체(하드웨어·PetaLinux·실측·함정)
- `docs/LowlightISP.md` — ISP 자체(파이프라인, 레지스터 맵, 비닝 정책 A, UIO/예약메모리)
- `docs/NormalISP.md` — RAW 변환 규격, UIO 8단계 시퀀스
