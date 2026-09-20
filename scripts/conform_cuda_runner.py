#!/usr/bin/env python3
"""The CUDA arm runner for the synthetic fact-space battery: drives
`conform_generate_cuda` (the fact-driven CUDA generate driver) over every
converted battery cell and compares the tokens against the fp64 reference
recorded in the battery report. Prints a per-cell PASS/FAIL line and a final
summary; exit 0 only when every cell the table claims supported matches.

Usage: python3 conform_cuda_runner.py <cells_dir> <report.json> [--max-new 8]

The `conform_generate_cuda` binary is found by name in $BENCH_BIN_DIR, then PATH
(benchmarks/bench_tools.py); build it into one of those instead of passing a path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from bench_tools import ToolError, run_tool, tool_path

DRIVER_TOOL = "conform_generate_cuda"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    try:
        driver = tool_path(DRIVER_TOOL)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    cells_dir = Path(sys.argv[1])
    report = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    max_new = 8
    if "--max-new" in sys.argv:
        max_new = int(sys.argv[sys.argv.index("--max-new") + 1])

    supported = {
        name: entry
        for name, entry in report["cells"].items()
        if entry.get("expected") == "supported"
    }
    passed = failed = errored = 0
    for name in sorted(supported):
        entry = supported[name]
        converted = cells_dir / name / "converted"
        if not (converted / "manifest.json").is_file():
            print(f"SKIP {name}: no converted checkpoint")
            continue
        proc = run_tool(
            driver, converted, "--max-new", str(max_new),
            capture_output=True,
            text=True,
            timeout=300,
        )
        tokens = None
        for line in proc.stdout.splitlines():
            if line.startswith("CONFORM_TOKENS:"):
                tokens = [int(t) for t in line.split()[1:]]
        ref = entry.get("reference_tokens")
        if tokens is None:
            errored += 1
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or ["<no output>"]
            print(f"ERROR {name}: driver produced no tokens: {tail[0][:160]}")
            continue
        if tokens == ref:
            passed += 1
            print(f"PASS {name}")
        else:
            failed += 1
            print(f"FAIL {name}: ref={ref} cuda={tokens}")
    total = passed + failed + errored
    print(f"cuda battery: {passed}/{total} cells token-identical "
          f"({failed} mismatched, {errored} errored)")
    return 0 if failed == 0 and errored == 0 and total == len(supported) else 1


if __name__ == "__main__":
    raise SystemExit(main())
