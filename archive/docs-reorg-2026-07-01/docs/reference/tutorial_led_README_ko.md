# Vivado Partial Reconfiguration Tutorial (Tcl_HD)

> **관련 문서**: UG947, Vivado Design Suite Tutorial: Dynamic Function eXchange
> **관련 파일명**: `ug947-vivado-partial-reconfiguration-tutorial.zip`

---

## 📋 파일 정보

- **공급업체**: AMD
- **현재 버전**: 2.0
- **최종 수정일**: 2023년 10월 19일
- **생성일**: 2020년 4월 17일
- **지원 장치**: 모든 AMD FPGA 및 SoC

---

## ⚖️ 저작권 및 면책 조항 (Copyright & Legal)

© Copyright 2023 Advanced Micro Devices, Inc. All rights reserved.
본 파일은 Advanced Micro Devices, Inc.의 기밀 및 독점 정보를 포함하고 있으며, 미국 및 국제 저작권법과 기타 지적 재산권법에 의해 보호받습니다.

<details>
<summary>자세한 면책 조항 및 중요 애플리케이션 정보 보기</summary>

### 면책 조항

본 면책 조항은 라이선스가 아니며 여기에 배포된 자료에 대한 어떠한 권리도 부여하지 않습니다. Xilinx에서 귀하에게 발행한 유효한 라이선스에 별도로 규정된 경우를 제외하고, 관련 법률이 허용하는 최대 범위 내에서:

1. 이 자료는 "있는 그대로" 모든 결함을 포함하여 제공되며, Xilinx는 상품성, 비침해성 또는 특정 목적에의 적합성에 대한 보증을 포함하여 명시적, 묵시적 또는 법적 모든 보증 및 조건을 거부합니다.
2. Xilinx는 계약상 또는 불법 행위(과실 포함) 또는 기타 책임 이론에 관계없이 이 자료와 관련하여 발생하는 모든 종류의 손실이나 피해(직접적, 간접적, 특별, 부수적 또는 결과적 손해 포함, 데이터 손실, 이익, 영업권 또는 제3자의 소송 결과로 입은 모든 유형의 손실이나 피해 포함)에 대해 책임을 지지 않습니다. 이는 그러한 손해나 손실이 합리적으로 예측 가능했거나 Xilinx가 그 가능성에 대해 조언을 받은 경우에도 마찬가지입니다.

### 중요 애플리케이션

Xilinx 제품은 고장 안전(fail-safe)으로 설계되거나 의도되지 않았으며, 생명 유지 또는 안전 장치나 시스템, 클래스 III 의료 기기, 원자력 시설, 에어백 전개와 관련된 애플리케이션 또는 사망, 개인 부상, 심각한 재산 또는 환경 피해를 초래할 수 있는 기타 애플리케이션(개별적 및 집합적으로 "중요 애플리케이션")에서의 사용을 위해 설계되지 않았습니다.
고객은 제품 책임 제한에 관한 관련 법률 및 규정을 준수하며 중요 애플리케이션에서 Xilinx 제품을 사용하는 데 따른 모든 위험과 책임을 단독으로 부담합니다.

_본 저작권 고지 및 면책 조항은 항상 이 파일의 일부로 유지되어야 합니다._

</details>

---

## 🛠️ 스크립트 버전 및 `design.tcl`

> **요구 사항**: Vivado 2020.1 이상 버전을 사용해야 합니다.

이 스크립트들은 모든 디자인에 대해 단일 파일(예: `run_dfx.tcl`)만 정의하거나 수정하면 되도록 설계되었습니다. 이 파일은 주어진 디자인에 대한 다양한 합성(모듈) 및 구현 실행을 설명하는 데 사용됩니다.

### `design.tcl` 핵심 명령

- `add_module` : 하향식(bottom-up) 합성으로 실행될 최상위 또는 하위 레벨 모듈을 정의합니다.
- `add_implementation` : 플랫(flat) 디자인 구현, OOC 디자인 어셈블(모듈 재사용), 또는 OOC 구현을 위한 제약 조건 생성(TopDown)을 정의합니다.
- `set_attribute` : 정의된 각 모듈 또는 구현에 대한 속성을 정의합니다. (기본값 이외의 값이 필요한 속성만 정의, `design_utils.tcl` 참조)

### 📌 유효한 모듈 속성 (Valid Module Attributes)

| 속성(Attribute)   | 설명                                                      |
| ----------------- | --------------------------------------------------------- |
| `moduleName`      | 실제 모듈 이름 (기본값: `add_module` 지정 값)             |
| `top_level`       | 모듈이 디자인의 최상위 레벨인지 지정                      |
| `prj`             | PRJ 파일의 위치 (정의 시 sysvlog, vlog, vhdl 무시됨)      |
| `includes`        | 포함 파일(include files) 지정                             |
| `generics`        | 제네릭(generics) 값 지정                                  |
| `vlog_headers`    | Verilog 헤더 파일 지정                                    |
| `vlog_defines`    | Verilog define 문 지정                                    |
| `sysvlog`         | System Verilog 파일 지정                                  |
| `vlog`            | Verilog 파일 지정                                         |
| `vhdl`            | VHDL 파일 지정                                            |
| `ip`              | 생성해야 하는 Vivado IP (XCI) 파일 지정                   |
| `ipRepo`          | 디자인에 필요한 IP 리포지토리 지정                        |
| `bd`              | 생성해야 하는 Vivado IPI (BD) 시스템 지정                 |
| `cores`           | 합성된 IP 코어(NGC, EDN, EDF) 지정                        |
| `xdc`             | 합성과 구현에 사용할 모듈 XDC 파일 지정                   |
| `synthXDC`        | 합성 전용 모듈 XDC 파일 지정                              |
| `implXDC`         | 구현 전용 모듈 XDC 파일 지정                              |
| `synth`           | 모듈에 대해 합성을 실행할지 여부 지정                     |
| `synth_options`   | 모듈의 합성 옵션 지정                                     |
| `synthCheckpoint` | 예상 위치 외부의 `post-synth_design` 체크포인트 위치 지정 |

### 📌 유효한 구현 속성 (Valid Implementation Attributes)

| 속성(Attribute)                                            | 설명                                                                   |
| ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| `top`                                                      | 구현의 최상위 모듈 이름                                                |
| `implXDC`                                                  | 최상위 XDC 파일 (Top/Static 구현 시에만 읽힘)                          |
| `cellXDC`                                                  | 셀별 XDC (예: BRAM LOC). `implXDC`와 다르며 모든 인스턴스에 적용 안 됨 |
| `cores`                                                    | 네트리스트에 없는 합성된 IP 코어(NGC, EDF, EDN) 지정                   |
| `hd.impl`                                                  | OOC 모듈 포함 여부 지정                                                |
| `td.impl`                                                  | OOC 제약 조건 생성을 위한 TopDown 실행 여부                            |
| `dfx.impl`                                                 | Dynamic Function eXchange 사용 여부 지정                               |
| `impl`                                                     | 구현 실행 여부 (기본값: `0`)                                           |
| `link`                                                     | `link_design` 실행 여부 (기본값: `1`)                                  |
| `opt`                                                      | `opt_design` 실행 여부 (기본값: `1`)                                   |
| `opt.pre`                                                  | `opt_design` 이전 실행 스크립트                                        |
| `opt_options` / `opt_directive`                            | `opt_design` 옵션 / 디렉티브                                           |
| `place`                                                    | `place_design` 실행 여부 (기본값: `1`)                                 |
| `place.pre`                                                | `place_design` 이전 실행 스크립트                                      |
| `place_options` / `place_directive`                        | `place_design` 옵션 / 디렉티브                                         |
| `phys`                                                     | `phys_opt_design` 실행 여부 (기본값: `1`)                              |
| `phys.pre`                                                 | `phys_opt_design` 이전 실행 스크립트                                   |
| `phys_options` / `phys_directive`                          | `phys_opt_design` 옵션 / 디렉티브                                      |
| `route`                                                    | `route_design` 실행 여부 (기본값: `1`)                                 |
| `route.pre`                                                | `route_design` 이전 실행 스크립트                                      |
| `route_options` / `route_directive`                        | `route_design` 옵션 / 디렉티브                                         |
| `bitstream`                                                | `write_bitstream` 실행 여부 (기본값: `0`)                              |
| `bitstream.pre`                                            | `write_bitstream` 이전 실행 스크립트                                   |
| `bitstream_options` / `bitstream_settings`                 | `write_bitstream` 옵션 / 구성 비트스트림 설정 (UG908)                  |
| `partial_bitstream_options` / `partial_bitstream_settings` | 파셜(partial) 비트파일 전용 옵션 및 구성 설정                          |

---

## 📂 `Tcl_HD` 디렉토리 스크립트 구성

다음은 `./Tcl_HD` 디렉토리에 제공된 추가 Tcl 스크립트와 내부 프로시저입니다.

### 유틸리티 스크립트 (Utility Scripts)

- **`design_utils.tcl`** (`design.tcl`에서 사용)
  - `add_module`, `add_implementation`, `set_attribute`, `get_attribute`, `check_attribute`, `check_attribute_value`, `check_list`, `set_directives`, `sort_configurations`, `set_paramaters`
- **`hd_utils.tcl`** (OOC 제약 조건 생성에 사용)
  - `get_partitions`, `get_bb` (blackbox), `bb` (blackbox), `gb` (greybox), `create_partition_budget`, `export_pblocks`
- **`dfx_utils.tcl`** (OOC 제약 조건 생성에 사용)
  - `get_rps`, `toggle_dfx`, `get_pp_range`, `export_partpins`, `convert_pblocks`
- **`synth_utils.tcl`** (합성 흐름에 사용)
  - `add_prj`, `add_ip`, `add_sysvlog`, `add_vlog`, `add_vhdl`, `add_bd`
- **`impl_utils.tcl`** (구현 흐름에 사용)
  - `get_module_file`, `generate_dfx_binfiles`, `generate_dfx_bitstreams`, `verify_configs`, `add_xdc`, `readXDC`, `add_ip`, `add_cores`, `check_drc`
- **`eco_utils.tcl`** (메모리 내 디자인 편집 예제)
  - `insert_ibuf`, `insert_clock_buffer`, `remover_buffer`, `swap_clock_buffers`, `insert_flop`, `split_BUFG_GT_load`
- **`log_utils.tcl`** (명령 및 로깅)
  - `log_time`, `command`, `parse_log`, `getTimingInfo`, `read_file_lines`, `print_table`

### 실행 스크립트 (Execution Scripts)

- **`run.tcl`**: `design.tcl`에서 호출되며 실행 흐름을 제어.
- **`synthesize.tcl`**: 모든 합성 실행에 사용.
- **`implement.tcl`**: Dynamic Function eXchange, HD-Platform 또는 플랫 구현 실행에 사용.
- **`step.tcl`**: 구현의 각 단계를 호출하는 데 사용.
