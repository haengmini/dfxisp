#!/usr/bin/env python3
"""Validate DFX phase-1 prerequisites without modifying Vivado projects."""
from __future__ import annotations
import json
import re
import shutil
import subprocess
from pathlib import Path

DFX = Path(__file__).resolve().parents[1]
HW = DFX.parent
ROOT = HW.parent
BUILD = DFX / "build"

REQUIRED = {
    "normal_cpp": HW / "NormalISP/NormalISP.cpp",
    "normal_hpp": HW / "NormalISP/NormalISP.hpp",
    "lowlight_cpp": HW / "LowlightISP/LowlightISP.cpp",
    "lowlight_hpp": HW / "LowlightISP/LowlightISP.hpp",
    "normal_project": HW / "NormalISP/NormalISP_zcu104/NormalISP_zcu104.xpr",
    "lowlight_project": HW / "LowlightISP/LowlightISP_zcu104/LowlightISP_zcu104.xpr",
    "normal_ip_header": HW / "NormalISP/NormalISP_hls/NormalISP/hls/impl/ip/drivers/NormalISP_v1_0/src/xnormalisp_hw.h",
    "lowlight_ip_header": HW / "LowlightISP/LowlightISP_hls/LowlightISP/hls/impl/ip/drivers/LowlightISP_v1_0/src/xlowlightisp_hw.h",
    "normal_xsa": HW / "NormalISP/NormalISP_zcu104/NormalISP_zcu104_design1_wrapper.xsa",
    "lowlight_xsa": HW / "LowlightISP/LowlightISP_zcu104/LowlightISP_zcu104_wrapper.xsa",
}


def function_args(path: Path, name: str) -> list[str]:
    text = path.read_text(errors="replace")
    match = re.search(rf"\bvoid\s+{re.escape(name)}\s*\((.*?)\)\s*;", text, re.S)
    if not match:
        raise RuntimeError(f"missing declaration {name} in {path}")
    return [re.sub(r"\s+", " ", part.strip()) for part in match.group(1).split(",")]


def register_offsets(path: Path) -> dict[str, str]:
    offsets: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"#define\s+\S+_CONTROL_ADDR_(\S+)_DATA\s+(0x[0-9A-Fa-f]+)", line)
        if m:
            offsets[m.group(1)] = m.group(2).lower()
    return offsets


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED.values() if not path.exists()]
    normal_args = function_args(REQUIRED["normal_hpp"], "NormalISP") if not missing else []
    lowlight_args = function_args(REQUIRED["lowlight_hpp"], "LowlightISP") if not missing else []
    normal_regs = register_offsets(REQUIRED["normal_ip_header"]) if not missing else {}
    lowlight_regs = register_offsets(REQUIRED["lowlight_ip_header"]) if not missing else {}
    vivado = Path("/tools/Xilinx/Vivado/2024.1/bin/vivado")
    version = "missing"
    if vivado.exists():
        out = subprocess.run([str(vivado), "-version"], capture_output=True, text=True, check=False)
        version = (out.stdout.splitlines() or ["unknown"])[0]
    git_status = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True
    ).splitlines()
    unrelated_changes = [line for line in git_status if "hw/DFX/" not in line]
    report = {
        "repo": str(ROOT),
        "vivado": version,
        "required_missing": missing,
        "top_arg_count": {"NormalISP": len(normal_args), "LowlightISP": len(lowlight_args)},
        "top_signatures_identical": normal_args == lowlight_args,
        "normal_top_args": normal_args,
        "lowlight_top_args": lowlight_args,
        "axi_register_map_identical": normal_regs == lowlight_regs,
        "normal_registers": normal_regs,
        "lowlight_registers": lowlight_regs,
        "static_rtl_present": all((DFX / "rtl" / n).exists() for n in [
            "checker_hysteresis.v", "dfxc_trigger_adapter.v", "pr_latency_probe.v"
        ]),
        "unrelated_git_changes": unrelated_changes,
    }
    report["pass"] = (
        not missing
        and not unrelated_changes
        and report["top_signatures_identical"]
        and report["axi_register_map_identical"]
        and report["static_rtl_present"]
        and version.startswith("vivado v2024.1")
    )
    output = BUILD / "preflight.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWrote {output}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
