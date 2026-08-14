// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read/COR)
//        bit 7  - auto_restart (Read/Write)
//        bit 9  - interrupt (Read)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0 - enable ap_done interrupt (Read/Write)
//        bit 1 - enable ap_ready interrupt (Read/Write)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0 - ap_done (Read/TOW)
//        bit 1 - ap_ready (Read/TOW)
//        others - reserved
// 0x10 : Data signal of raw_bayer
//        bit 31~0 - raw_bayer[31:0] (Read/Write)
// 0x14 : Data signal of raw_bayer
//        bit 31~0 - raw_bayer[63:32] (Read/Write)
// 0x18 : reserved
// 0x1c : Data signal of width
//        bit 31~0 - width[31:0] (Read/Write)
// 0x20 : reserved
// 0x24 : Data signal of height
//        bit 31~0 - height[31:0] (Read/Write)
// 0x28 : reserved
// 0x2c : Data signal of mode
//        bit 31~0 - mode[31:0] (Read/Write)
// 0x30 : reserved
// 0x34 : Data signal of dark_pixel_threshold
//        bit 15~0 - dark_pixel_threshold[15:0] (Read/Write)
//        others   - reserved
// 0x38 : reserved
// 0x3c : Data signal of verdict_pct
//        bit 31~0 - verdict_pct[31:0] (Read/Write)
// 0x40 : reserved
// 0x44 : Data signal of enter_pct
//        bit 31~0 - enter_pct[31:0] (Read/Write)
// 0x48 : reserved
// 0x4c : Data signal of exit_pct
//        bit 31~0 - exit_pct[31:0] (Read/Write)
// 0x50 : reserved
// 0x54 : Data signal of selected_mode
//        bit 31~0 - selected_mode[31:0] (Read)
// 0x58 : Control signal of selected_mode
//        bit 0  - selected_mode_ap_vld (Read/COR)
//        others - reserved
// 0x64 : Data signal of dark_count
//        bit 31~0 - dark_count[31:0] (Read)
// 0x68 : Control signal of dark_count
//        bit 0  - dark_count_ap_vld (Read/COR)
//        others - reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define CONTROL_ADDR_AP_CTRL                   0x00
#define CONTROL_ADDR_GIE                       0x04
#define CONTROL_ADDR_IER                       0x08
#define CONTROL_ADDR_ISR                       0x0c
#define CONTROL_ADDR_RAW_BAYER_DATA            0x10
#define CONTROL_BITS_RAW_BAYER_DATA            64
#define CONTROL_ADDR_WIDTH_DATA                0x1c
#define CONTROL_BITS_WIDTH_DATA                32
#define CONTROL_ADDR_HEIGHT_DATA               0x24
#define CONTROL_BITS_HEIGHT_DATA               32
#define CONTROL_ADDR_MODE_DATA                 0x2c
#define CONTROL_BITS_MODE_DATA                 32
#define CONTROL_ADDR_DARK_PIXEL_THRESHOLD_DATA 0x34
#define CONTROL_BITS_DARK_PIXEL_THRESHOLD_DATA 16
#define CONTROL_ADDR_VERDICT_PCT_DATA          0x3c
#define CONTROL_BITS_VERDICT_PCT_DATA          32
#define CONTROL_ADDR_ENTER_PCT_DATA            0x44
#define CONTROL_BITS_ENTER_PCT_DATA            32
#define CONTROL_ADDR_EXIT_PCT_DATA             0x4c
#define CONTROL_BITS_EXIT_PCT_DATA             32
#define CONTROL_ADDR_SELECTED_MODE_DATA        0x54
#define CONTROL_BITS_SELECTED_MODE_DATA        32
#define CONTROL_ADDR_SELECTED_MODE_CTRL        0x58
#define CONTROL_ADDR_DARK_COUNT_DATA           0x64
#define CONTROL_BITS_DARK_COUNT_DATA           32
#define CONTROL_ADDR_DARK_COUNT_CTRL           0x68
