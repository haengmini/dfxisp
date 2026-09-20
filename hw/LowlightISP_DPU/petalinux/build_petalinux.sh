#!/bin/bash
# Build the PetaLinux 2024.1 image for the LowlightISP + DPU design, headless.
#
#   cd LowlightISP_DPU/petalinux && ./build_petalinux.sh
#   XSA=/path/to/other.xsa ./build_petalinux.sh          # override the hardware
#
# Method (docs/NormalISP_DPU.md SS2): do NOT configure a fresh project by hand -- clone the
# verified project-spec/ of normalisp_dpu_2024_1 (which already carries all five Vivado-flow
# deltas: xlnx_dpu + UIO kernel config, xrt/zocl removed, VART built with PACKAGECONFIG
# "python" instead of "vitis python", the bootargs, and numpy/pillow in the rootfs), then
# change exactly two things:
#   1. system-user.dtsi  -> overlay/system-user.dtsi   (&LowlightISP_0, lowlightisp-* UIO names)
#   2. the hardware      -> this design's XSA
# Everything else being identical is what makes the two board images comparable.
#
# petalinux-build exits non-zero even on success because petalinux.xilinx.com is dead and the
# sstate mirror times out; success is judged by "all succeeded" in the Tasks Summary, the same
# rule as docs/NormalISP.md SS8 and LowlightISP.md SS9.
#
#   RESUME=1 ./build_petalinux.sh      # keep an existing project, just re-run build+package
#
# bitbake is incremental, so a build killed part-way (this machine has 14 GB and the default
# BB_NUMBER_THREADS = nproc = 16 exhausts it around task ~3400/6900) is resumed, not restarted.
# Step 2 pins the thread counts for exactly that reason.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
DFX=$(cd "$HERE/../.." && pwd)
SETTINGS=${SETTINGS:-$HOME/petalinux/2024.1/settings.sh}
SRC_PROJ=${SRC_PROJ:-$DFX/NormalISP_DPU/petalinux/normalisp_dpu_2024_1}
PROJ=${PROJ:-$HERE/lowlightisp_dpu_2024_1}
XSA=${XSA:-$DFX/LowlightISP_DPU/LowlightISP_DPU_zcu104/LowlightISP_DPU_zcu104_wrapper.xsa}
SSTATE=${SSTATE:-$SRC_PROJ/build/sstate-cache}
DOWNLOADS=${DOWNLOADS:-$(sed -n 's/^CONFIG_PRE_MIRROR_URL="file:\/\/\(.*\)"$/\1/p' \
                          "$SRC_PROJ/project-spec/configs/config")}

for p in "$SETTINGS" "$SRC_PROJ/project-spec/configs/config" "$XSA" "$HERE/overlay/system-user.dtsi"; do
    [ -e "$p" ] || { echo "missing: $p"; exit 1; }
done
RESUME=${RESUME:-0}
if [ -e "$PROJ/project-spec/configs/config" ] && [ "$RESUME" != "1" ]; then
    echo "$PROJ already exists -- delete it to rebuild, or RESUME=1 to continue it"; exit 1
fi

# shellcheck disable=SC1090
source "$SETTINGS"

if [ "$RESUME" = "1" ]; then
    echo "=== resuming $PROJ (skipping create/clone/hw-import) ==="
else
echo "=== 1. create project + clone the verified project-spec ==="
# 2024.1's petalinux-create has no -p/--path: it creates the project in the CWD.
( cd "$(dirname "$PROJ")" && petalinux-create project -n "$(basename "$PROJ")" --template zynqMP ) || exit 1
rsync -a --exclude hw-description "$SRC_PROJ/project-spec/" "$PROJ/project-spec/"
cp "$HERE/overlay/system-user.dtsi" \
   "$PROJ/project-spec/meta-user/recipes-bsp/device-tree/files/system-user.dtsi"

# Sanity-check the deltas that came in with the clone, so a silent rsync miss cannot turn into
# a board that boots without /dev/dpu or without the UIO driver.
K=$PROJ/project-spec/meta-user/recipes-kernel/linux/linux-xlnx/bsp.cfg
for opt in CONFIG_XILINX_DPU=y CONFIG_UIO=y CONFIG_UIO_PDRV_GENIRQ=y; do
    grep -qx "$opt" "$K" || { echo "missing $opt in $K"; exit 1; }
done
grep -q 'PACKAGECONFIG:append = " python"' \
     "$PROJ/project-spec/meta-user/recipes-vitis-ai/vart/vart_3.5.bb" \
    || echo "WARN: vart_3.5.bb is not the non-XRT (\" python\") variant -- check docs SS2-1 delta 3"
grep -q "^&LowlightISP_0" "$PROJ/project-spec/meta-user/recipes-bsp/device-tree/files/system-user.dtsi" \
    || { echo "device tree overlay did not land"; exit 1; }

echo "=== 2. reuse the NormalISP_DPU sstate cache + download mirror ==="
C=$PROJ/project-spec/configs/config
sed -i "s|^CONFIG_YOCTO_LOCAL_SSTATE_FEEDS_URL=.*|CONFIG_YOCTO_LOCAL_SSTATE_FEEDS_URL=\"$SSTATE\"|" "$C"
sed -i "s|^CONFIG_PRE_MIRROR_URL=.*|CONFIG_PRE_MIRROR_URL=\"file://$DOWNLOADS\"|" "$C"

echo "=== 3. import hardware: $XSA ==="
cd "$PROJ" || exit 1
petalinux-config --get-hw-description="$XSA" --silentconfig 2>&1 | tail -5
fi
cd "$PROJ" || exit 1

BSPCONF=$PROJ/project-spec/meta-user/conf/petalinuxbsp.conf
grep -q '^SSTATE_MIRRORS' "$BSPCONF" || echo 'SSTATE_MIRRORS = ""' >> "$BSPCONF"
# Throttle bitbake: the defaults are nproc-wide and this 14 GB machine gets OOM-killed
# mid-build with them. Override BB_JOBS/MAKE_JOBS if you have the RAM.
grep -q '^BB_NUMBER_THREADS' "$BSPCONF" || {
    echo "BB_NUMBER_THREADS = \"${BB_JOBS:-4}\"" >> "$BSPCONF"
    echo "PARALLEL_MAKE = \"-j ${MAKE_JOBS:-4}\"" >> "$BSPCONF"
}

echo "=== 4. build (30-90 min with the cache; non-zero exit is expected) ==="
petalinux-build 2>&1 | tee "$PROJ/build_full.log"
if ! grep -q "all succeeded" "$PROJ/build_full.log"; then
    echo "BUILD FAILED -- 'all succeeded' not in the Tasks Summary; see $PROJ/build_full.log"
    exit 1
fi

echo "=== 5. package BOOT.BIN + SD image ==="
# petalinux-package must run from the project root (it locates the project by CWD).
cd "$PROJ" || exit 1
petalinux-package --boot --fsbl images/linux/zynqmp_fsbl.elf --u-boot images/linux/u-boot.elf \
                  --pmufw images/linux/pmufw.elf --fpga images/linux/system.bit --force || exit 1
petalinux-package --wic --bootfile "BOOT.BIN boot.scr Image system.dtb" || exit 1

echo
ls -la "$PROJ/images/linux/BOOT.BIN" "$PROJ/images/linux/petalinux-sdimage.wic"
cat <<EOF

Next:
  1. flash:  lsblk                                   # find the SD device (this machine: /dev/sda)
             sudo dd if=$PROJ/images/linux/petalinux-sdimage.wic of=/dev/sdX bs=4M status=progress conv=fsync
  2. stage:  board_test/lowlightisp/stage_exp100_lowlight.sh  -> /home/root/exp100L
  3. board:  cd /home/root/exp100L/app && MODELS=/home/root/exp100L/models ./run_smoke.sh
EOF
