#!/usr/bin/env python3
"""bench_vs_quantlib_heston_driver.py — interleaves the Mojo and QuantLib Heston arms.

    /tmp/bb/bin/python -P benchmarks/mojo_benchmarks/bench_vs_quantlib_heston_driver.py --rounds 3

WHY IT ALTERNATES, AND WHAT "HOT" MEANS HERE
----------------------------------------------
Same discipline as `bench_vs_topk_driver.py`: this host runs at a load average that moves by a
factor of several within minutes, from other agents' processes resident on the same machine. One
arm run to completion and then the other measures WHEN each ran as much as WHAT each does. So the
two arms alternate round by round — one full invocation of the compiled Mojo binary (covering
every cell), then one full invocation of the QuantLib script (covering every cell) — and every
cell's reported time is the MINIMUM across rounds, because contention can only make a reading
slower than the work actually takes, never faster. The 1-minute load average is sampled
immediately before and after every invocation and printed with it.

WHAT IS COMPARED, AND WHAT IS NOT
------------------------------------
European leg: both sides price the FULL Heston model (kappa=2, xi=0.5, rho=-0.7, Feller 0.64) —
a genuine like-for-like comparison, judged against EACH SIDE'S OWN semi-analytic Heston price
(Fourier inversion for us, `ql.AnalyticHestonEngine` for QuantLib — cross-checked against each
other below, since they should and do agree).

American leg: QuantLib's public American/LSM engines (`ql.MCAmericanEngine`,
`ql.BinomialVanillaEngine`) are wired to a Black-Scholes process, not Heston (see the header of
`bench_vs_quantlib_heston.py`). So this leg runs the Black-Scholes-DEGENERATE corner of our own
Heston model (`xi=0, rho=0, v0=theta=sigma^2`) on both sides — same contract, same true answer
(American call, no dividends, equals European exactly — a model-free theorem), different
implementations. `ql.FdHestonVanillaEngine` (a genuinely Heston-native PDE solver) is reported
separately in its own section and is NEVER averaged into the LSM-vs-LSM numbers: it is a
different numerical method, and a race between a PDE grid and a Monte Carlo estimator is not a
race between two estimators of the same kind.

VERSIONS, ASSERTED, NOT ASSUMED
----------------------------------
The QuantLib arm prints `QL_VERSION` at run time; the Mojo arm's git SHA is recorded from `git
rev-parse HEAD` on the tree that built the binary. Neither is taken on faith.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
_MOJO_ENV = _REPO / "mojo_env"
_ENGINE = _REPO / "mojo" / "engine"
_MOJO_SOURCE = _HERE / "bench_vs_quantlib_heston.mojo"
_QL_ARM = _HERE / "bench_vs_quantlib_heston.py"

_KV = re.compile(r"(\w+)=([^\s]+)")


def _kv(line: str) -> dict[str, str]:
    return dict(_KV.findall(line))


def _pixi() -> str:
    found = shutil.which("pixi")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/pixi", str(Path.home() / ".pixi" / "bin" / "pixi")):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("pixi not found; cannot build the Mojo arm")


def build_mojo(out: Path) -> Path:
    binary = out / "bench_vs_quantlib_heston"
    cmd = [
        _pixi(), "run", "mojo", "build", f"-I{_ENGINE}", "-O3",
        str(_MOJO_SOURCE), "-o", str(binary),
    ]
    print(f"building: {' '.join(cmd)}  (cwd={_MOJO_ENV})", flush=True)
    proc = subprocess.run(  # noqa: S603 - repo toolchain, fixed argv, no shell
        cmd, cwd=str(_MOJO_ENV), capture_output=True, text=True, timeout=1800
    )
    if proc.returncode != 0 or not binary.exists():
        print(proc.stdout[-4000:])
        print(proc.stderr[-4000:], file=sys.stderr)
        raise SystemExit("the Mojo arm did not build")
    return binary


def run(cmd: list[str], label: str, timeout_s: float) -> tuple[str, tuple[float, ...], tuple[float, ...]]:
    before = os.getloadavg()
    start = time.perf_counter()
    proc = subprocess.run(  # noqa: S603 - the benchmark itself, fixed argv, no shell
        cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(_REPO)
    )
    wall = time.perf_counter() - start
    after = os.getloadavg()
    print(
        f"  {label}: {wall:6.1f}s   load before {before[0]:5.1f} after {after[0]:5.1f}"
        f"   exit {proc.returncode}",
        flush=True,
    )
    if proc.returncode != 0:
        print(proc.stderr[-3000:], file=sys.stderr)
    return proc.stdout, before, after


@dataclass
class Cell:
    prices: list[float] = field(default_factory=list)
    rel_errs: list[float] = field(default_factory=list)
    wall_ms: list[float] = field(default_factory=list)

    def add(self, fields: dict[str, str]) -> None:
        try:
            self.prices.append(float(fields["price"]))
            self.rel_errs.append(float(fields["rel_err_pct"]))
            self.wall_ms.append(float(fields["wall_ms"]))
        except (KeyError, ValueError):
            pass

    @property
    def price(self) -> float | None:
        return self.prices[0] if self.prices else None

    @property
    def price_spread(self) -> float:
        """max - min price across rounds. Both sides use a fixed seed, so this should be ~0;
        a nonzero spread means a round was non-deterministic, which is itself worth knowing."""
        return (max(self.prices) - min(self.prices)) if len(self.prices) > 1 else 0.0

    @property
    def rel_err(self) -> float | None:
        return self.rel_errs[0] if self.rel_errs else None

    @property
    def hot_ms(self) -> float | None:
        return min(self.wall_ms) if self.wall_ms else None

    @property
    def spread(self) -> float | None:
        """max/min wall_ms across rounds. Reported so a reader can see whether the minimum
        was a fluke or the run was consistent — contention only ever makes a reading slower,
        so a small spread means the minimum is trustworthy, not lucky."""
        if len(self.wall_ms) < 2 or min(self.wall_ms) <= 0:
            return None
        return max(self.wall_ms) / min(self.wall_ms)


def absorb(text: str, prefix: str, into: dict[tuple[int, int], Cell]) -> None:
    """Keys by (n_paths, workers). QuantLib's lines carry no `workers` field — its Python MC
    engines here are single-threaded (no thread-count argument exists on them; confirmed by
    CPU-percentage sampling during a call), so a missing field defaults to workers=1, which is
    the true value, not a guess."""
    for line in text.splitlines():
        if not line.startswith(prefix + " "):
            continue
        fields = _kv(line)
        try:
            n_paths = int(fields["n_paths"])
            workers = int(fields.get("workers", "1"))
        except (KeyError, ValueError):
            continue
        into.setdefault((n_paths, workers), Cell()).add(fields)


def single_value(text: str, prefix: str, key: str) -> float | None:
    for line in text.splitlines():
        if line.startswith(prefix + " "):
            fields = _kv(line)
            if key in fields:
                try:
                    return float(fields[key])
                except ValueError:
                    return None
    return None


def find_line(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    return None


def _fmt(value: float | None, digits: int = 4) -> str:
    return "unresolved" if value is None else f"{value:.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=1200.0)
    parser.add_argument("--binary", default="", help="skip the build and use this prebuilt Mojo binary")
    parser.add_argument("--python", default="/tmp/bb/bin/python", help="interpreter with QuantLib importable")
    parser.add_argument("--scratch", default="/tmp/bb/work/qlbench")
    args = parser.parse_args()
    if args.rounds < 1:
        raise SystemExit("--rounds must be >= 1")

    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    binary = Path(args.binary) if args.binary else build_mojo(scratch)

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=str(_REPO), capture_output=True, text=True
    ).stdout.strip() or "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "mojo/engine/quantfin"],
        cwd=str(_REPO), capture_output=True, text=True,
    ).stdout.strip()

    print("== Heston-QE + Longstaff-Schwartz: Algenta (Mojo) vs QuantLib, INTERLEAVED ==")
    print(f"  rounds per side: {args.rounds}   host load now {os.getloadavg()}")
    print(f"  logical cores: {os.cpu_count()}")
    print(f"  mojo/engine/quantfin git SHA: {sha}{' (with UNCOMMITTED changes)' if dirty else ''}")
    print("")

    euro_ours: dict[tuple[int, int], Cell] = {}
    euro_theirs: dict[tuple[int, int], Cell] = {}
    amer_ours: dict[tuple[int, int], Cell] = {}
    amer_theirs: dict[tuple[int, int], Cell] = {}
    our_gate_fails = 0
    their_gate_fails = 0
    ql_version = None
    our_cf = None
    their_cf = None
    our_binref = None
    their_binref = None
    their_fd_line = None
    loads: list[tuple[str, tuple[float, ...], tuple[float, ...]]] = []

    for index in range(args.rounds):
        print(f"round {index + 1}/{args.rounds}", flush=True)
        text, before, after = run([str(binary)], "mojo   ", args.timeout)
        loads.append((f"mojo   r{index + 1}", before, after))
        absorb(text, "QLHEURO", euro_ours)
        absorb(text, "QLHAMER", amer_ours)
        our_cf = single_value(text, "QLHEURO_CLOSED_FORM", "price") or our_cf
        our_binref = single_value(text, "QLHAMER_BINOMIAL_REF", "price") or our_binref
        if "BENCH_GATE vs_quantlib_heston_mojo_arm FAIL" in text:
            our_gate_fails += 1

        text, before, after = run([args.python, "-P", str(_QL_ARM)], "quantlib", args.timeout)
        loads.append((f"quantlib r{index + 1}", before, after))
        absorb(text, "QLHEURO", euro_theirs)
        absorb(text, "QLHAMER", amer_theirs)
        their_cf = single_value(text, "QLHEURO_CLOSED_FORM", "price") or their_cf
        their_binref = single_value(text, "QLHAMER_BINOMIAL_REF", "price") or their_binref
        their_fd_line = find_line(text, "QLHFD") or their_fd_line
        vline = find_line(text, "QL_VERSION")
        if vline:
            ql_version = vline.split()[1]
        if "BENCH_GATE vs_quantlib_heston_ql_arm FAIL" in text:
            their_gate_fails += 1

    print("")
    print(f"QuantLib version (asserted at run time): {ql_version}")
    print(f"Mojo gate failures across {args.rounds} rounds: {our_gate_fails}")
    print(f"QuantLib gate failures across {args.rounds} rounds: {their_gate_fails}")
    print("")
    print("-- load average (1-min), immediately before/after every invocation --")
    for label, before, after in loads:
        print(f"  {label:<14} before {before[0]:6.1f}  after {after[0]:6.1f}")

    print("")
    print("-- ground truth cross-check: two INDEPENDENT semi-analytic Heston prices --")
    print(f"  ours (Fourier / Little Heston Trap):  {_fmt(our_cf, 5)}")
    print(f"  QuantLib (ql.AnalyticHestonEngine):   {_fmt(their_cf, 5)}")
    if our_cf is not None and their_cf is not None:
        agree_pct = abs(our_cf - their_cf) / their_cf * 100.0
        print(f"  agreement: {agree_pct:.5f}% relative difference")

    def leg_table(
        title: str,
        ours: dict[tuple[int, int], Cell],
        theirs: dict[tuple[int, int], Cell],
        workers: int,
    ) -> tuple[int, int]:
        print("")
        print(title)
        header = (
            f"  {'n_paths':>8} | {'ours price':>11} {'ours err%':>10} {'ours hot_ms':>12} {'spread':>7}"
            f" | {'ql price':>11} {'ql err%':>10} {'ql hot_ms':>10} {'spread':>7} | {'speed (ql/ours)':>16}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))
        wins = 0
        losses = 0
        n_paths_keys = sorted(
            {k[0] for k in ours if k[1] == workers} | {k[0] for k in theirs if k[1] == workers}
        )
        for n_paths in n_paths_keys:
            o = ours.get((n_paths, workers), Cell())
            t = theirs.get((n_paths, workers), Cell())
            ratio = (t.hot_ms / o.hot_ms) if (o.hot_ms and t.hot_ms) else None
            print(
                f"  {n_paths:>8} | {_fmt(o.price, 5):>11} {_fmt(o.rel_err):>10} {_fmt(o.hot_ms, 1):>12}"
                f" {(_fmt(o.spread, 2) + 'x') if o.spread else '  n/a':>7}"
                f" | {_fmt(t.price, 5):>11} {_fmt(t.rel_err):>10} {_fmt(t.hot_ms, 1):>10}"
                f" {(_fmt(t.spread, 2) + 'x') if t.spread else '  n/a':>7}"
                f" | {(_fmt(ratio, 2) + 'x') if ratio else 'unresolved':>16}"
            )
            if ratio is not None:
                if ratio > 1.0:
                    wins += 1
                else:
                    losses += 1
        return wins, losses

    euro_wins, euro_losses = leg_table(
        "-- 1a. EUROPEAN LEG, workers=1 (LIKE-FOR-LIKE: QuantLib's MC engine is single-threaded"
        " here — confirmed by CPU sampling, no thread-count arg on the engine) --",
        euro_ours, euro_theirs, 1,
    )
    leg_table(
        "-- 1b. EUROPEAN LEG, ours workers=8 (NOT LIKE-FOR-LIKE; QuantLib side unchanged,"
        " still 1 thread — shown for completeness, not counted in the summary) --",
        euro_ours, euro_theirs, 8,
    )

    print("")
    print("-- 2. AMERICAN LEG (BS-degenerate corner): LSM vs each side's own European anchor --")
    print("  Both sides' LSM price can legitimately be BELOW `european` here: the true premium")
    print("  is exactly zero (American call, no dividends), so any nonzero premium is finite-")
    print("  sample regression bias, and that bias runs negative for degree-2 LSM on BOTH")
    print("  engines (measured on QuantLib's own MCAmericanEngine across 9 seed/sample")
    print("  combinations in bench_vs_quantlib_heston.py's docstring). `rel_err%` below is")
    print("  against the (genuinely American) CRR binomial reference on each side.")
    print(f"  ours European-CRR-2048 reference:        {_fmt(our_binref, 5)}")
    print(f"  QuantLib American-CRR-2000 reference:    {_fmt(their_binref, 5)}")
    amer_wins, amer_losses = leg_table(
        "-- 2a. AMERICAN LEG, workers=1 (LIKE-FOR-LIKE) --", amer_ours, amer_theirs, 1,
    )
    leg_table(
        "-- 2b. AMERICAN LEG, ours workers=8 (NOT LIKE-FOR-LIKE, shown for completeness) --",
        amer_ours, amer_theirs, 8,
    )

    print("")
    print("-- 3. Heston-native PDE opponent (DIFFERENT METHOD, not raced against our LSM) --")
    print(f"  {their_fd_line or 'unresolved'}")

    print("")
    max_price_spread = max(
        (c.price_spread for c in (*euro_ours.values(), *amer_ours.values())), default=0.0
    )
    print(
        f"-- determinism check: max price spread across {args.rounds} independent Mojo "
        f"process launches (fixed seed) = {max_price_spread:.2e}  (expect 0.0)"
    )

    print("")
    print("-- SUMMARY (workers=1, LIKE-FOR-LIKE only; the workers=8 rows above are informational) --")
    print(f"  European leg:  {euro_wins} cell(s) faster than QuantLib, {euro_losses} slower")
    print(f"  American leg:  {amer_wins} cell(s) faster than QuantLib, {amer_losses} slower")
    all_wins = euro_wins + amer_wins
    all_losses = euro_losses + amer_losses
    if our_gate_fails or their_gate_fails:
        print("  NOT A CLEAN RUN: at least one side's own correctness gate failed at least once.")
        print("  No speed or accuracy claim above should be trusted until that is resolved.")
        return 1
    if all_losses == 0 and all_wins > 0:
        print("  Every measured cell was faster than QuantLib at matched path/step counts, 1 thread each.")
    elif all_wins == 0 and all_losses > 0:
        print("  Every measured cell was slower than QuantLib at matched path/step counts, 1 thread each.")
    else:
        print("  Mixed: some cells faster, some slower. See the tables above for which.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
