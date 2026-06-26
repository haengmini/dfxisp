#!/usr/bin/env python3
"""Generate a compact local DFXISP HLS verification report.

The report is intentionally stdlib-only.  It inspects Makefile state, validates
``tests/golden_vectors.csv`` shape/content, runs the local C-sim binary when it
exists, and writes Markdown to ``reports/latest.md`` by default.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class GoldenCase:
    name: str
    width: int
    height: int
    mode: int
    threshold: int
    rows: int


def parse_makefile(path: Path) -> tuple[dict[str, str], list[str]]:
    variables: dict[str, str] = {}
    targets: list[str] = []
    assign_re = re.compile(r"^([A-Za-z0-9_]+)\s*(?::=|\?=|=)\s*(.*)$")
    target_re = re.compile(r"^([A-Za-z0-9_.-]+)\s*:")

    if not path.exists():
        return variables, targets

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or raw.startswith("\t"):
            continue
        m = assign_re.match(line)
        if m:
            variables[m.group(1)] = m.group(2).strip()
            continue
        m = target_re.match(line)
        if m:
            targets.append(m.group(1))
    return variables, targets


def expand_make_value(value: str, variables: dict[str, str]) -> str:
    # Small, non-recursive Make variable expansion loop for simple $(NAME) refs.
    pattern = re.compile(r"\$\(([^)]+)\)")
    result = value
    for _ in range(8):
        new = pattern.sub(lambda m: variables.get(m.group(1), m.group(0)), result)
        if new == result:
            break
        result = new
    return result


def analyze_golden(path: Path) -> tuple[str, list[str], list[GoldenCase], int]:
    notes: list[str] = []
    cases: dict[tuple[str, int, int, int, int], int] = {}
    total_rows = 0

    if not path.exists():
        return "missing", [f"{path} not found"], [], 0

    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected_header = ["case", "width", "height", "mode", "threshold", "index", "x", "y", "raw", "expected_rgb_hex"]
            if reader.fieldnames != expected_header:
                notes.append(f"unexpected CSV header: {reader.fieldnames}")
            for row in reader:
                total_rows += 1
                name = row["case"]
                width = int(row["width"])
                height = int(row["height"])
                mode = int(row["mode"])
                threshold = int(row["threshold"])
                index = int(row["index"])
                int(row["x"])
                int(row["y"])
                raw = int(row["raw"])
                rgb = int(row["expected_rgb_hex"], 16)
                if not (0 <= index < width * height):
                    notes.append(f"{name}: index {index} outside {width}x{height}")
                if not (0 <= raw <= 4095):
                    notes.append(f"{name}: RAW value {raw} outside RAW12 range")
                if not (0 <= rgb <= 0xFFFFFF):
                    notes.append(f"{name}: RGB value 0x{rgb:x} outside RGB888 range")
                key = (name, width, height, mode, threshold)
                cases[key] = cases.get(key, 0) + 1
    except Exception as exc:  # Keep report useful on malformed local files.
        return "fail", [f"failed to parse {path}: {exc}"], [], total_rows

    golden_cases = [GoldenCase(*key, rows=count) for key, count in cases.items()]
    for case in golden_cases:
        expected = case.width * case.height
        if case.rows != expected:
            notes.append(f"{case.name}: {case.rows} rows, expected {expected}")

    names = {case.name for case in golden_cases}
    sizes = {(case.width, case.height) for case in golden_cases}
    for required_size in [(8, 8), (16, 16)]:
        if required_size not in sizes:
            notes.append(f"missing required {required_size[0]}x{required_size[1]} golden-vector coverage")
    for required_label in ["bright", "dark", "mixed", "threshold_boundary"]:
        if not any(required_label in name for name in names):
            notes.append(f"missing required {required_label} golden-vector coverage")

    status = "pass" if total_rows > 0 and not notes else "fail"
    return status, notes, golden_cases, total_rows


def run_csim(binary: Path) -> tuple[str, str, int | None]:
    if not binary.exists():
        return "missing", f"{binary} not found", None
    if not os.access(binary, os.X_OK):
        return "fail", f"{binary} is not executable", None
    proc = subprocess.run([str(binary)], cwd=binary.parent.parent, text=True, capture_output=True, check=False)
    output = (proc.stdout + proc.stderr).strip()
    status = "pass" if proc.returncode == 0 else "fail"
    return status, output, proc.returncode


def write_report(root: Path, out: Path) -> None:
    makefile = root / "Makefile"
    variables, targets = parse_makefile(makefile)
    golden_rel = expand_make_value(variables.get("GOLDEN_CSV", "tests/golden_vectors.csv"), variables)
    csim_rel = expand_make_value(variables.get("CSIM_BIN", "build/dfxisp_csim"), variables)
    golden_path = root / golden_rel
    csim_path = root / csim_rel

    golden_status, golden_notes, golden_cases, total_rows = analyze_golden(golden_path)
    csim_status, csim_output, csim_returncode = run_csim(csim_path)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rel_out = out.relative_to(root) if out.is_relative_to(root) else out
    lines: list[str] = [
        "# DFXISP HLS Verification Report",
        "",
        f"Generated: {generated}",
        f"Report: `{rel_out}`",
        "",
        "## Status",
        "",
        "| Check | Status | Evidence |",
        "|---|---:|---|",
        f"| Golden vectors | {golden_status.upper()} | `{golden_rel}`; {total_rows} data rows; {len(golden_cases)} cases |",
        f"| C-sim | {csim_status.upper()} | `{csim_rel}`; return code {csim_returncode if csim_returncode is not None else 'n/a'} |",
        "",
        "## Makefile state",
        "",
        f"- `CXX`: `{variables.get('CXX', 'g++')}`",
        f"- `PYTHON`: `{variables.get('PYTHON', 'python3')}`",
        f"- `CSIM_BIN`: `{csim_rel}`",
        f"- `GOLDEN_CSV`: `{golden_rel}`",
        f"- Targets include: `{', '.join(targets)}`",
        "",
        "## Golden vector cases",
        "",
        "| Case | Mode | Threshold | Dimensions | Rows |",
        "|---|---:|---:|---:|---:|",
    ]
    if golden_cases:
        for case in golden_cases:
            lines.append(f"| {case.name} | {case.mode} | {case.threshold} | {case.width}x{case.height} | {case.rows} |")
    else:
        lines.append("| n/a | n/a | n/a | n/a | 0 |")

    lines.extend([
        "",
        "## DPU-facing shape policy",
        "",
        "Decision for this C2 verification set: keep the default HLS/C-sim output shape at `H x W` for NORMAL, LOW_LIGHT, and AUTO outputs. This preserves a fixed-size DPU-facing ABI while the H/2 x W/2 low-light binning path remains an explicit ablation/future RM variant rather than the default golden-vector contract.",
        "",
        "- Rationale: current `dfxisp_accel` signature exposes one output buffer without output-width/output-height metadata, so H/2 emission would make bit-exact comparison ambiguous and would force downstream resize/pad policy before DPU integration.",
        "- Ablation policy: evaluate `H/2 x W/2` low-light binning separately once the interface includes output shape metadata or an explicit post-binning upsample/pad stage. Compare it against the preserve-shape path using the same bright/dark/mixed/threshold-boundary fixtures.",
        "- Current golden-vector contract: packed RGB888 `0x00RRGGBB`, one output pixel per input pixel, with low-light represented by deterministic gain/lift at preserved shape.",
    ])

    lines.extend(["", "## C-sim output", "", "```text", csim_output or "(no output)", "```"])

    if golden_notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in golden_notes)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} (golden={golden_status}, csim={csim_status})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path, help="HLS root directory")
    parser.add_argument("--out", default=None, help="output Markdown path (default: <root>/reports/latest.md)")
    args = parser.parse_args()

    root = args.root.resolve()
    out = Path(args.out).resolve() if args.out else root / "reports" / "latest.md"
    write_report(root, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
