"""BENCH_GATE for exactnum: shape and correctness, never nanoseconds.

What it gates, and why each one is a gate rather than a report:

1. `eft_selfcheck_code() == EFT_OK`. If the fused multiply-add stops being fused, or a future
   toolchain reassociates float addition, every double-double result in the package silently
   becomes a plain float64 result. Nothing downstream would fail loudly.

2. Both hand-written Mojo suites report `Failed: 0`. Those carry the exact-rational goldens and
   the anti-vacuity cases.

3. SHAPE. Eleven datasets, each returning exactly as many coefficients as the published model
   has certified parameters, with `status == LSTSQ_OK`.

4. CORRECTNESS, expressed cap-free. Every coefficient of the shipped arm
   (`D_ddpow_matrix__dd_solve`) must be BIT-IDENTICAL to the exact least-squares solution of
   the same design matrix, computed over the rationals in `ceilings.py` and rounded once to
   float64. That is a 0-ulp requirement, and it is a stronger gate than any digit count: digits
   saturate at 15.95 and at NIST's own ~15-significant-digit publication of the certified
   values, so a regression from "exactly optimal" to "one ulp off" can be invisible in digits
   while being plainly visible here.

No timing is gated. The cost multiple is measured in
`benchmarks/mojo_benchmarks/measure_exactnum_lstsq_cost.mojo` and reported, not asserted: a
nanosecond threshold on a shared machine fails for reasons that have nothing to do with the
code, and this gate has to mean something when it goes red.

Run: /tmp/bb/bin/python -P bench_gate.py [--prebuilt]
     --prebuilt runs the `measure_exactnum_strd` binary found in $BENCH_BIN_DIR (then PATH)
     instead of compiling the driver through pixi for every dataset.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import load  # noqa: E402

load.HERE = os.path.join(HERE, "data")

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "benchmarks"))
from bench_tools import ToolError, run_tool, tool_path  # noqa: E402

MOJO_ENV = "/Users/angel/Developer/decision-engine/mojo_env"
ENGINE = os.path.join(REPO, "mojo", "engine")
DRIVER = os.path.join(REPO, "benchmarks", "mojo_benchmarks", "measure_exactnum_strd.mojo")
SUITES = [
    os.path.join(REPO, "mojo", "tests", "libs", "test_exactnum_eft.mojo"),
    os.path.join(REPO, "mojo", "tests", "libs", "test_exactnum_lstsq.mojo"),
]

SHIPPED_ARM = "D_ddpow_matrix__dd_solve"


def mojo_run(path: str, args: list[str]) -> str:
    proc = subprocess.run(
        ["pixi", "run", "mojo", "run", "-I" + ENGINE, path] + args,
        cwd=MOJO_ENV, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return "MOJO_FAILED\n" + proc.stderr[-2000:]
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--prebuilt", action="store_true",
        help="run the measure_exactnum_strd binary from $BENCH_BIN_DIR / PATH instead of pixi",
    )
    args = ap.parse_args()
    binary = None
    if args.prebuilt:
        try:
            binary = tool_path("measure_exactnum_strd")
        except ToolError as exc:
            ap.error(str(exc))

    failures: list[str] = []
    checks = 0

    # ── 2. the hand-written suites ───────────────────────────────────────────
    for suite in SUITES:
        out = mojo_run(suite, [])
        checks += 1
        tail = [ln for ln in out.splitlines() if "Passed:" in ln]
        if not tail:
            failures.append("suite produced no summary line: " + os.path.basename(suite))
        elif "Failed: 0" not in tail[-1]:
            failures.append("suite not green: " + tail[-1].strip())

    ceilings = json.load(open(os.path.join(HERE, "ceilings.json")))
    manifest = json.load(open(os.path.join(HERE, "specs", "manifest.json")))

    for name in load.ORDER:
        spec = os.path.join(HERE, "specs", name + ".spec")
        if binary is not None:
            proc = run_tool(binary, spec, capture_output=True, text=True)
            out = proc.stdout if proc.returncode == 0 else "MOJO_FAILED"
        else:
            out = mojo_run(DRIVER, [spec])

        # ── 1. the arithmetic self-check ─────────────────────────────────────
        checks += 1
        sc = [ln for ln in out.splitlines() if ln.startswith("SELFCHECK")]
        if not sc or sc[0].split()[1] != "800":
            failures.append("%s: arithmetic selfcheck not EFT_OK: %r" % (name, sc))
            continue

        arms: dict[str, list[str]] = {}
        statuses: dict[str, int] = {}
        for line in out.splitlines():
            t = line.split()
            if t and t[0] == "ARM":
                statuses[t[1]] = int(t[3])
                arms.setdefault(t[1], [])
            elif t and t[0] == "COEF":
                arms[t[1]].append(t[3])

        # ── 3. shape ─────────────────────────────────────────────────────────
        checks += 1
        want = manifest[name]["params"]
        got = arms.get(SHIPPED_ARM, [])
        if statuses.get(SHIPPED_ARM) != 810:
            failures.append(
                "%s: shipped arm status %r, expected 810" % (name, statuses.get(SHIPPED_ARM))
            )
            continue
        if len(got) != want:
            failures.append("%s: %d coefficients, expected %d" % (name, len(got), want))
            continue

        # ── 4. bit-identical to the exact solution ───────────────────────────
        checks += 1
        target = ceilings[name]["c_exactpow_hex"]
        if got != target:
            bad = [
                (j, got[j], target[j]) for j in range(want) if got[j] != target[j]
            ]
            failures.append(
                "%s: shipped arm is NOT the correctly-rounded exact solution, %d/%d "
                "coefficients differ: %r" % (name, len(bad), want, bad[:4])
            )

    print("BENCH_GATE checks: %d" % checks)
    if failures:
        print("BENCH_GATE FAIL (%d)" % len(failures))
        for f in failures:
            print("  -", f)
        return 1
    print("BENCH_GATE PASS — 11/11 datasets bit-identical to the exact LS solution, both")
    print("hand-written suites green, arithmetic selfcheck EFT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
