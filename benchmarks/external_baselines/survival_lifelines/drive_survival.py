#!/usr/bin/env python3
"""Driver for the survival-analysis head-to-head: Algenta's `survival_analysis` package
(`km_fit`, `cox_fit`) against `lifelines` 0.30.0.

What this orchestrates, and in what order (rule: correctness before any timing)
---------------------------------------------------------------------------------
For every cell (a dataset -- real Rossi, or a synthetic size/shape):

  1. Build (once) and run `survival_h2h.mojo` under the pixi-env Mojo runtime. It fits the
     real kernel on the real (or realistically-shaped synthetic) input, DUMPS its output
     to raw float64 files, and times `reps` repeated in-process calls.
  2. Run `lifelines_refs.py` under the SYSTEM Python (has `lifelines`; the pixi env does
     not -- see `survival_h2h.mojo`'s docstring). It loads step 1's dump, fits the
     `lifelines` equivalent on the IDENTICAL bytes, COMPARES the two, and only after
     printing that comparison does it time its own `reps` repeated calls.
  3. This script parses both arms' `T <mode> <n> <rep> <ns>` lines into cold/warm/hot
     (rep 0 = cold, rep 1 = warm, min of the rest = hot, matching `gemm_h2h.mojo` /
     `bench_vs_sort.mojo`'s convention), parses `lifelines_refs.py`'s `CORRECTNESS_GATE`
     line, and enforces the same Tier validity used in `bench_vs_sort.mojo`
     (hot <= warm, hot_worst / hot <= MAX_SPREAD) on BOTH arms independently.

A cell's timing ratio is reported ONLY if its correctness gate passed AND both arms'
timing passed the validity gate. A cell whose correctness fails is a FAIL regardless of
how the timing looks -- there is no ratio a wrong answer can buy back.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "benchmarks"))
from bench_tools import (  # noqa: E402
    ToolError,
    env_path,
    run_tool,
    tool_from_env,
    tool_in_dir,
    tool_path,
)

MOJO_ENV = REPO / "mojo_env"
ENGINE = REPO / "mojo" / "engine"
H2H = HERE / "survival_h2h.mojo"
REFS = HERE / "lifelines_refs.py"
PREP = HERE / "prep_rossi.py"
DRIVESTATS_SUMMARY_CSV = env_path(
    "SURV_DRIVESTATS_SUMMARY", "/tmp/backblaze_q4_2025/drivestats_summary.csv"
)
MOTORSPORT_SUMMARY_CSV = env_path("SURV_MOTORSPORT_SUMMARY", "/tmp/motorsport_survival.csv")
PREP_DRIVESTATS = HERE / "prep_drivestats.py"
PREP_MOTORSPORT = HERE / "prep_motorsport.py"

DATA_DIR = env_path("SURV_DATA", "/tmp/survival_lifelines_data")
DUMP_ROOT = env_path("SURV_DUMP_ROOT", "/tmp/survival_lifelines_dump")
# Where `mojo build` writes the survival_h2h binary. With --skip-build the binary is found by that
# name in $BENCH_BIN_DIR, then here, then PATH -- never by a path taken from the environment.
BUILD_DIR = env_path("SURV_BUILD_DIR", "/tmp")
MOJO_TOOL = "survival_h2h"

MAX_SPREAD = 2.0  # matches bench_vs_sort.mojo's Tier.valid()


@functools.cache
def ref_python() -> Path:
    """The lifelines interpreter, resolved on first use so that importing this module needs none.

    SURV_BENCH_PYTHON selects it by allowlisted NAME ("python3" / "python"); the venv that has
    lifelines goes in $BENCH_BIN_DIR. /usr/local/bin is the historical default location.
    """
    return tool_from_env("SURV_BENCH_PYTHON", "python3", search_dirs=("/usr/local/bin",))


def build_mojo() -> Path:
    print(f"building {H2H.name} ...", file=sys.stderr)
    out = os.path.join(BUILD_DIR, MOJO_TOOL)
    proc = subprocess.run(
        ["pixi", "run", "mojo", "build", "-I", str(ENGINE), str(H2H), "-o", out],
        cwd=str(MOJO_ENV), capture_output=True, text=True,
    )
    binary = tool_in_dir(BUILD_DIR, MOJO_TOOL) if proc.returncode == 0 else None
    if binary is None:
        print(proc.stdout[-4000:])
        print(proc.stderr[-4000:])
        raise SystemExit("mojo build failed")
    return binary


def ensure_rossi_data() -> None:
    if os.path.exists(os.path.join(DATA_DIR, "rossi_week.f64")):
        return
    print("prepping Rossi dataset ...", file=sys.stderr)
    proc = run_tool(ref_python(), PREP, DATA_DIR, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        raise SystemExit("prep_rossi.py failed")


def ensure_drivestats_data() -> None:
    if os.path.exists(os.path.join(DATA_DIR, "drivestats_days.f64")):
        return
    if not os.path.exists(DRIVESTATS_SUMMARY_CSV):
        raise SystemExit(
            f"missing {DRIVESTATS_SUMMARY_CSV}. Drive Stats is an external ~1.2GB "
            "download, not fetched automatically -- see build_drivestats_summary.py's "
            "docstring for the two-step fetch + transform."
        )
    print("prepping Drive Stats dataset ...", file=sys.stderr)
    proc = run_tool(
        ref_python(), PREP_DRIVESTATS, DRIVESTATS_SUMMARY_CSV, DATA_DIR,
        capture_output=True, text=True,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        raise SystemExit("prep_drivestats.py failed")


def ensure_motorsport_data() -> None:
    if os.path.exists(os.path.join(DATA_DIR, "motorsport_laps.f64")):
        return
    if not os.path.exists(MOTORSPORT_SUMMARY_CSV):
        print("building motorsport survival summary from the local corpus ...", file=sys.stderr)
        proc = run_tool(
            ref_python(), HERE / "build_motorsport_survival.py",
            os.path.expanduser("~/.algenta/f1/raw"), MOTORSPORT_SUMMARY_CSV,
            capture_output=True, text=True,
        )
        print(proc.stdout, proc.stderr)
        if proc.returncode != 0:
            raise SystemExit("build_motorsport_survival.py failed -- corpus not present locally?")
    print("prepping motorsport dataset ...", file=sys.stderr)
    proc = run_tool(
        ref_python(), PREP_MOTORSPORT, MOTORSPORT_SUMMARY_CSV, DATA_DIR,
        capture_output=True, text=True,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        raise SystemExit("prep_motorsport.py failed")


class Tier:
    def __init__(self, reps_ns: list[int]):
        self.cold = reps_ns[0] if reps_ns else 0.0
        self.warm = reps_ns[1] if len(reps_ns) > 1 else 0.0
        hot = reps_ns[2:]
        self.hot = min(hot) if hot else 0.0
        self.hot_worst = max(hot) if hot else 0.0
        self.n_hot = len(hot)

    def spread(self) -> float:
        return self.hot_worst / self.hot if self.hot > 0 else 0.0

    def ordered(self) -> bool:
        return self.hot <= self.warm if self.warm > 0 else True

    def valid(self) -> bool:
        return self.hot > 0 and self.ordered() and self.spread() <= MAX_SPREAD

    def why_invalid(self) -> str:
        reasons = []
        if self.hot <= 0:
            reasons.append("no hot reading")
        if not self.ordered():
            reasons.append(f"hot({self.hot:.0f}) > warm({self.warm:.0f})")
        if self.spread() > MAX_SPREAD:
            reasons.append(f"spread {self.spread():.2f}x > {MAX_SPREAD}x")
        return "; ".join(reasons) if reasons else "(none)"


def parse_timing(output: str, mode: str) -> list[int]:
    reps = []
    for line in output.splitlines():
        t = line.split()
        if len(t) == 5 and t[0] == "T" and t[1] == mode:
            reps.append(int(t[4]))
    return reps


def run(
    tool: Path, *args: object, cwd: str | None = None, timeout: float = 300.0
) -> tuple[int, str]:
    proc = run_tool(tool, *args, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return proc.returncode, proc.stdout + proc.stderr


REAL_DATA_MODES = {"km_rossi", "km_drivestats", "km_motorsport", "cox_rossi", "cox_drivestats", "cox_motorsport"}


def run_km_cell(mojo: Path, mode: str, arg: str, reps: int) -> dict:
    dump_dir = os.path.join(DUMP_ROOT, f"{mode}_{arg}")
    os.makedirs(dump_dir, exist_ok=True)
    if mode in REAL_DATA_MODES:
        mojo_args = (mode, DATA_DIR, dump_dir, reps)
        py_args = (REFS, mode, DATA_DIR, dump_dir, reps)
    else:
        mojo_args = (mode, arg, dump_dir, reps)
        py_args = (REFS, mode, arg, dump_dir, reps)
    rc1, out1 = run(mojo, *mojo_args)
    rc2, out2 = run(ref_python(), *py_args, timeout=600.0)
    return {
        "mode": mode, "n": arg, "mojo_out": out1, "py_out": out2,
        "mojo_rc": rc1, "py_rc": rc2,
    }


def run_cox_cell(mojo: Path, mode: str, n: str, p: str, max_iter: int, reps: int) -> dict:
    dump_dir = os.path.join(DUMP_ROOT, f"{mode}_{n}_{p}")
    os.makedirs(dump_dir, exist_ok=True)
    if mode in REAL_DATA_MODES:
        mojo_args = (mode, DATA_DIR, dump_dir, max_iter, reps)
        py_args = (REFS, mode, DATA_DIR, dump_dir, max_iter, reps)
    else:
        mojo_args = (mode, n, p, max_iter, dump_dir, reps)
        py_args = (REFS, mode, n, p, max_iter, dump_dir, reps)
    rc1, out1 = run(mojo, *mojo_args)
    rc2, out2 = run(ref_python(), *py_args, timeout=600.0)
    return {
        "mode": mode, "n": n, "p": p, "mojo_out": out1, "py_out": out2,
        "mojo_rc": rc1, "py_rc": rc2,
    }


def judge(cell: dict) -> dict:
    mode, n = cell["mode"], cell["n"]
    mojo_reps = parse_timing(cell["mojo_out"], mode)
    py_reps = parse_timing(cell["py_out"], mode)
    mojo_tier = Tier(mojo_reps)
    py_tier = Tier(py_reps)

    gate_line = next(
        (ln for ln in cell["py_out"].splitlines() if ln.startswith("CORRECTNESS_GATE")), ""
    )
    correctness_ok = " PASS " in gate_line or gate_line.endswith(" PASS")
    correctness_detail = [
        ln for ln in cell["py_out"].splitlines()
        if ln.startswith("CORRECTNESS_KM") or ln.startswith("CORRECTNESS_COX")
    ]

    result = dict(cell)
    result.update({
        "mojo_tier": mojo_tier, "py_tier": py_tier,
        "correctness_ok": correctness_ok, "gate_line": gate_line,
        "correctness_detail": correctness_detail,
        "mojo_reps": mojo_reps, "py_reps": py_reps,
    })

    timing_valid = mojo_tier.valid() and py_tier.valid()
    result["timing_valid"] = timing_valid
    result["overall_ok"] = (
        correctness_ok and timing_valid and cell["mojo_rc"] == 0 and cell["py_rc"] == 0
    )
    if timing_valid and mojo_tier.hot > 0:
        result["ratio_hot"] = py_tier.hot / mojo_tier.hot
        result["ratio_cold"] = py_tier.cold / mojo_tier.cold if mojo_tier.cold else float("nan")
    return result


def print_cell(label: str, r: dict) -> None:
    print(f"--- {label} ---")
    if r["mojo_rc"] != 0:
        print("  MOJO_FAILED")
        print("  " + r["mojo_out"][-1500:])
    if r["py_rc"] != 0:
        print("  PYTHON_REF_FAILED")
        print("  " + r["py_out"][-1500:])
    for d in r.get("correctness_detail", []):
        print("  " + d)
    print(f"  correctness gate: {'PASS' if r['correctness_ok'] else 'FAIL'}  ({r['gate_line']})")
    mt, pt = r["mojo_tier"], r["py_tier"]
    print(
        f"  mojo(algenta)  cold={mt.cold/1e6:9.3f}ms warm={mt.warm/1e6:9.3f}ms "
        f"hot={mt.hot/1e6:9.3f}ms spread={mt.spread():.2f}x valid={mt.valid()}"
    )
    print(
        f"  lifelines      cold={pt.cold/1e6:9.3f}ms warm={pt.warm/1e6:9.3f}ms "
        f"hot={pt.hot/1e6:9.3f}ms spread={pt.spread():.2f}x valid={pt.valid()}"
    )
    if not r["timing_valid"]:
        if not mt.valid():
            print(f"  INVALID mojo timing: {mt.why_invalid()}")
        if not pt.valid():
            print(f"  INVALID lifelines timing: {pt.why_invalid()}")
    elif "ratio_hot" in r:
        ratio = r["ratio_hot"]
        if ratio >= 1.0:
            print(f"  WE WIN: Algenta is {ratio:.2f}x faster than lifelines (hot)")
        else:
            print(f"  WE LOSE: lifelines is {1.0/ratio:.2f}x faster than Algenta (hot)")
    print(f"  overall: {'OK' if r['overall_ok'] else 'NOT OK (see above)'}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--km-sizes", default="1000,10000,100000,1000000")
    ap.add_argument("--cox-grid", default="1000:2,1000:8,1000:32,10000:2,10000:8,10000:32,"
                                            "100000:2,100000:8,100000:32")
    ap.add_argument("--reps-cheap", type=int, default=6)
    ap.add_argument("--reps-expensive", type=int, default=3)
    args = ap.parse_args()

    os.makedirs(DUMP_ROOT, exist_ok=True)
    try:
        mojo = tool_path(MOJO_TOOL, search_dirs=(BUILD_DIR,)) if args.skip_build else build_mojo()
        ref_python()  # fail here, with the allowlist's message, not inside the first prep step
    except ToolError as exc:
        raise SystemExit(f"{ap.prog}: error: {exc}") from None
    ensure_rossi_data()
    ensure_drivestats_data()
    ensure_motorsport_data()

    load_before = os.getloadavg()
    print("=" * 96)
    print("SURVIVAL ANALYSIS HEAD-TO-HEAD: Algenta survival_analysis vs lifelines 0.30.0")
    print("=" * 96)
    print(f"load average BEFORE (1m/5m/15m): {load_before}")
    print(f"mojo binary: {mojo}")
    print(f"reference python: {ref_python()}")
    print()

    results = []

    # ── KM ───────────────────────────────────────────────────────────────────
    print("### PRIMARY: Kaplan-Meier (km_fit vs KaplanMeierFitter) ###")
    print()
    r = judge(run_km_cell(mojo, "km_drivestats", "", args.reps_cheap))
    print_cell("km_drivestats n=341664 (real hard-drive fleet, current quarter)", r)
    results.append(r)

    r = judge(run_km_cell(mojo, "km_motorsport", "", args.reps_cheap))
    print_cell("km_motorsport n=2596 (real car-racing retirement corpus, 2019-2026)", r)
    results.append(r)

    r = judge(run_km_cell(mojo, "km_rossi", "", args.reps_cheap))
    print_cell("km_rossi n=432 (real Rossi recidivism dataset, 1980 -- secondary cross-check, "
               "not featured: see the page for why)", r)
    results.append(r)

    for n in args.km_sizes.split(","):
        reps = args.reps_cheap
        r = judge(run_km_cell(mojo, "km_synth", n, reps))
        print_cell(f"km_synth n={n} (synthetic, 25% censored, ~2.4% tie rate)", r)
        results.append(r)

    # ── Cox ──────────────────────────────────────────────────────────────────
    print("### SECONDARY: Cox proportional hazards (cox_fit vs CoxPHFitter) ###")
    print()
    r = judge(run_cox_cell(mojo, "cox_motorsport", "", "", 100, args.reps_cheap))
    print_cell("cox_motorsport n=2596 p=2 (real car-racing corpus, 2019-2026)", r)
    results.append(r)

    print("--- cox_drivestats n=114453 p=4 (real hard-drive fleet, current quarter) ---")
    print("  ATTEMPTED, NOT REPORTED: at this event rarity (408 failures among 114,453")
    print("  drives) lifelines' unregularized Newton-Raphson does not converge reliably")
    print("  on real covariates -- checked directly (ConvergenceError / overflow in exp),")
    print("  not assumed. cox_fit itself converges, but a cell with no working reference")
    print("  arm to check against is not a comparison. See the page's Method section.")
    print()

    r = judge(run_cox_cell(mojo, "cox_rossi", "", "", 100, args.reps_cheap))
    print_cell("cox_rossi n=432 p=7 (real Rossi recidivism dataset, 1980 -- secondary "
               "cross-check, not featured: see the page for why)", r)
    results.append(r)

    sa_max_work = 1 << 30
    for cell in args.cox_grid.split(","):
        n_s, p_s = cell.split(":")
        n, p = int(n_s), int(p_s)
        max_iter = min(100, sa_max_work // (n * p * (p + 12)))
        max_iter = max(max_iter, 1)
        expensive = n * p >= 800_000
        reps = args.reps_expensive if expensive else args.reps_cheap
        r = judge(run_cox_cell(mojo, "cox_synth", n_s, p_s, max_iter, reps))
        print_cell(f"cox_synth n={n} p={p} (max_iter={max_iter}, synthetic proportional-hazards)", r)
        results.append(r)

    # ── summary ──────────────────────────────────────────────────────────────
    load_after = os.getloadavg()
    print("=" * 96)
    print("SUMMARY")
    print("=" * 96)
    n_ok = sum(1 for r in results if r["overall_ok"])
    n_correct = sum(1 for r in results if r["correctness_ok"])
    n_total = len(results)
    print(f"correctness: {n_correct}/{n_total} cells passed the correctness gate")
    print(f"overall (correctness + valid timing): {n_ok}/{n_total} cells OK")
    print()
    wins = 0
    losses = 0
    for r in results:
        if not r["overall_ok"] or "ratio_hot" not in r:
            continue
        tag = "WIN " if r["ratio_hot"] >= 1.0 else "LOSS"
        if r["ratio_hot"] >= 1.0:
            wins += 1
        else:
            losses += 1
        p_field = f" p={r['p']}" if "p" in r else ""
        print(f"  {tag}  {r['mode']:12s} n={r['n']:>8}{p_field:6s} ratio(lifelines/algenta hot)={r['ratio_hot']:.3f}x")
    print()
    print(f"wins={wins} losses={losses} (of {wins+losses} cells with a valid ratio)")
    print(f"load average AFTER (1m/5m/15m): {load_after}")

    failures = n_total - n_ok
    if failures == 0:
        print("BENCH_GATE survival_lifelines PASS")
    else:
        print(f"BENCH_GATE survival_lifelines FAIL {failures}")

    dump_path = "/tmp/survival_lifelines_results.json"
    with open(dump_path, "w") as fh:
        json.dump(
            [
                {
                    "mode": r["mode"], "n": r["n"], "p": r.get("p"),
                    "correctness_ok": r["correctness_ok"],
                    "timing_valid": r["timing_valid"],
                    "overall_ok": r["overall_ok"],
                    "mojo_hot_ns": r["mojo_tier"].hot, "py_hot_ns": r["py_tier"].hot,
                    "ratio_hot": r.get("ratio_hot"),
                }
                for r in results
            ],
            fh, indent=2,
        )
    print(f"machine-readable summary: {dump_path}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
