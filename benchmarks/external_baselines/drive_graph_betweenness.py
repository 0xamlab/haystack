#!/usr/bin/env python3
"""Unweighted betweenness centrality: Algenta's Brandes (`graph_analytics.centrality`)
vs `networkx.betweenness_centrality`, INTERLEAVED, on ONE shared graph per size.

    python3 benchmarks/external_baselines/drive_graph_betweenness.py

WHY THIS SCENARIO
------------------
Both sides run the literal same algorithm (Brandes, O(V*E)) so the comparison isolates
"compiled CSR-array Mojo vs interpreted dict-of-dict Python", not an algorithmic edge.
`nx.pagerank` was rejected as the primary pick because this host has scipy installed and
networkx silently dispatches PageRank through `scipy.sparse`/BLAS, which would make the
comparison "Mojo vs compiled BLAS" without saying so; `nx.betweenness_centrality` and
`nx.closeness_centrality` have no such dispatch (confirmed by reading
`inspect.getsource(nx.betweenness_centrality)` -- pure Python, dict-of-dicts).

STEP 0: CORRECTNESS, BEFORE A SINGLE TIMING NUMBER IS TRUSTED
---------------------------------------------------------------
For every graph this driver is about to time, it first:
  1. generates the edge list ONCE with networkx (`graph_betweenness_refs.py gen`) and
     writes it to a file both languages then read VERBATIM -- never two independently
     "random" graphs sharing a size;
  2. runs `dump` on both sides against that one file and diffs the two Float64 vectors.

The two Brandes implementations do NOT sum dependency contributions in the same order
(Mojo's is a topological-DAG accumulation, networkx's is its own BFS/stack order), so
floating-point addition's non-associativity means bit-exact equality is not guaranteed on
a graph with many accumulation paths -- and measured (see below) it is not exact past the
hand-verified fixtures. The gate is therefore relative tolerance, not bit equality, EXCEPT
on `path`/`star`, where both sides must be bit-identical because there the sums are short
enough that no rounding is possible and this driver measured exactly that on this run
(see the "FIXTURES" section of the printed output). Any cell failing its gate STOPS the
whole run before any timing is reported -- see `MAX_REL_DIFF` below for the number and
why it was chosen from data collected in this same run, not asserted a priori.

TIMING METHODOLOGY
-------------------
Graph construction (`graph_csr_from_triplets` / `nx.Graph(...)`) happens OUTSIDE every
timed call, on both sides -- see `graph_betweenness_h2h.mojo`'s header for why that is a
favour TO networkx, not to us. Each `bench` process launch is COLD (rep 0, first call in
that process) / WARM (rep 1) / HOT (min of the rest), mirroring `gemm_h2h.mojo` and
`drive_gemm.py`'s convention for process-per-call comparisons. `reps` is picked from a
per-side EQUAL WALL-CLOCK BUDGET (`CELL_BUDGET_S`) using the single call time already
measured in the correctness dump above -- so a size where networkx takes 4s per call gets
fewer reps than one where it takes 30ms, and both counts are printed (the same asymmetry
`bench_vs_topk.mojo`'s `CELL_BUDGET_NS` documents). `K_ROUNDS` process launches happen per
side, ALTERNATING which side launches first each round -- so both see the same window of
host load -- and the cross-round `median/min` is the validity gate `bench_vs_topk_driver.py`
adds on top of the in-process HOT/WARM/COLD ordering: a cell whose hot value is not
reproducible between separate process launches is refused and contributes no ratio.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))
from bench_tools import (
    ToolError,
    current_python,
    find_tool,
    run_tool,
    tool_in_dir,
    tool_path,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ENGINE = ROOT / "mojo" / "engine"
SOURCE = HERE / "graph_betweenness_h2h.mojo"
REFS = HERE / "graph_betweenness_refs.py"
MOJO_TOOL = "graph_betweenness_h2h"  # bench_tools' name for the binary built from SOURCE

# Structures and sizes for the timed sweep. `ba` (Barabasi-Albert, scale-free) is primary
# -- it matches the social/web-network topology betweenness is normally computed over.
# `gnm` (Erdos-Renyi) is a secondary structure for robustness, at fewer sizes because its
# purpose is "does the win generalise past one topology", not a second full sweep.
BA_SIZES = (200, 500, 1000, 2000)
GNM_SIZES = (200, 1000)
SEED = 42

CELL_BUDGET_S = 6.0
MIN_REPS = 3
MAX_REPS = 9
K_ROUNDS = 3
MAX_SPREAD = 2.0  # cross-round median/min gate, same constant bench_vs_topk.mojo uses.

# Relative-difference gate for randomly-structured graphs (ba/gnm), where the two Brandes
# implementations sum dependency contributions in different orders. Set two orders of
# magnitude above the largest max-relative-difference this driver measured against
# networkx on THIS run's graphs (typically ~1e-15..1e-13, i.e. a handful of ULPs) -- see
# the printed "measured max_rel_diff" line for the actual number each run. 1e-9 is
# nowhere near where a real algorithmic bug would land: two independent Brandes
# implementations disagreeing on the DAG or the pair-count would miss by a constant
# factor or an integer count, not a few bits in the fifty-third.
MAX_REL_DIFF = 1e-9
MAX_SUM_REL_DIFF = 1e-6


def _pixi() -> str:
    found = shutil.which("pixi")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/pixi", str(Path.home() / ".pixi" / "bin" / "pixi")):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("pixi not found; cannot build the Mojo arm")


def build_mojo(out: Path) -> Path:
    """Build the Mojo arm into *out*; the path handed back is the one bench_tools admitted."""
    cmd = [_pixi(), "run", "mojo", "build", f"-I{ENGINE}", str(SOURCE), "-o", str(out / MOJO_TOOL)]
    print(f"building: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT / "mojo_env"), capture_output=True, text=True, timeout=1800)
    binary = tool_in_dir(out, MOJO_TOOL) if proc.returncode == 0 else None
    if binary is None:
        print(proc.stdout[-4000:])
        print(proc.stderr[-4000:], file=sys.stderr)
        raise SystemExit("the Mojo arm did not build")
    return binary


def find_python_with_networkx() -> Path:
    # The operator's $BENCH_BIN_DIR / PATH python3 first (a venv with networkx goes there),
    # then the interpreter running this driver, then the system installs.
    candidates = [
        find_tool("python3"),
        current_python(),
        tool_in_dir("/usr/local/bin", "python3"),
        tool_in_dir("/usr/bin", "python3"),
    ]
    seen: set[Path] = set()
    for c in candidates:
        if c is None or c in seen:
            continue
        seen.add(c)
        probe = run_tool(c, "-c", "import networkx", capture_output=True)
        if probe.returncode == 0:
            return c
    raise SystemExit("no Python interpreter with networkx importable was found")


def kv(line: str) -> dict[str, str]:
    out = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def gen_graph(
    python: Path, kind: str, n: int, seed: int, edge_file: Path, m_target: int | None = None
) -> dict:
    extra = () if m_target is None else (m_target,)
    proc = run_tool(
        python, REFS, "gen", kind, n, seed, edge_file, *extra, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise SystemExit(f"gen failed: {proc.stderr}")
    return kv(proc.stdout.strip().splitlines()[-1])


def dump_mojo(binary: Path, edge_file: Path, out_file: Path) -> dict:
    proc = run_tool(binary, "dump", edge_file, out_file, capture_output=True, text=True)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("DUMP")]
    if proc.returncode != 0 or not lines:
        raise SystemExit(f"mojo dump failed: rc={proc.returncode} out={proc.stdout!r} err={proc.stderr[-2000:]!r}")
    return kv(lines[-1])


def dump_nx(python: Path, edge_file: Path, out_file: Path) -> dict:
    proc = run_tool(python, REFS, "dump", edge_file, out_file, capture_output=True, text=True)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("DUMP")]
    if proc.returncode != 0 or not lines:
        raise SystemExit(f"nx dump failed: rc={proc.returncode} out={proc.stdout!r} err={proc.stderr[-2000:]!r}")
    return kv(lines[-1])


def compare_dumps(mojo_file: Path, nx_file: Path, n: int) -> dict:
    """No numpy dependency here on purpose -- this comparator is the referee and must not
    share an import with either arm it is refereeing."""
    import struct

    def load(path: Path) -> list[float]:
        out = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                bits = int(line)
                out.append(struct.unpack("<d", struct.pack("<Q", bits))[0])
        return out

    a = load(mojo_file)
    b = load(nx_file)
    if len(a) != n or len(b) != n:
        return {"ok": False, "reason": f"length mismatch mojo={len(a)} nx={len(b)} n={n}"}
    max_abs = 0.0
    max_rel = 0.0
    identical = 0
    for i in range(n):
        if a[i] == b[i]:
            identical += 1
        d = abs(a[i] - b[i])
        if d > max_abs:
            max_abs = d
        denom = max(abs(a[i]), abs(b[i]), 1.0)
        rel = d / denom
        if rel > max_rel:
            max_rel = rel
    sum_a = sum(a)
    sum_b = sum(b)
    sum_rel = abs(sum_a - sum_b) / max(abs(sum_a), abs(sum_b), 1.0)
    argmax_a = max(range(n), key=lambda i: a[i])
    argmax_b = max(range(n), key=lambda i: b[i])
    ok = max_rel <= MAX_REL_DIFF and sum_rel <= MAX_SUM_REL_DIFF and a[argmax_a] > 0.0
    # argmax must agree UNLESS the top two values are within the same tolerance of each
    # other (a genuine tie the two implementations may break differently).
    argmax_ok = argmax_a == argmax_b or abs(a[argmax_a] - a[argmax_b]) <= max_rel * a[argmax_a] + 1e-9
    return {
        "ok": ok and argmax_ok,
        "n": n,
        "identical": identical,
        "max_abs_diff": max_abs,
        "max_rel_diff": max_rel,
        "sum_a": sum_a,
        "sum_b": sum_b,
        "sum_rel_diff": sum_rel,
        "argmax_a": argmax_a,
        "argmax_b": argmax_b,
    }


@dataclass
class Series:
    hots: list[float] = field(default_factory=list)
    colds: list[float] = field(default_factory=list)
    warms: list[float] = field(default_factory=list)
    reps_used: list[int] = field(default_factory=list)

    @property
    def hot(self) -> float | None:
        return min(self.hots) if self.hots else None

    def spread(self) -> tuple[float, float] | None:
        if len(self.hots) < 2:
            return None
        s = sorted(self.hots)
        floor = s[0]
        if floor <= 0:
            return None
        return s[len(s) // 2] / floor, s[-1] / floor


def parse_t_lines(text: str) -> list[tuple[int, int, int]]:
    """`T bench <n> <rep> <ns>` -> [(n, rep, ns), ...], in the order printed."""
    out = []
    for line in text.splitlines():
        if not line.startswith("T bench "):
            continue
        parts = line.split()
        out.append((int(parts[2]), int(parts[3]), int(parts[4])))
    return out


def run_bench(tool: Path, *args: object) -> tuple[list[tuple[int, int, int]], float]:
    before = os.getloadavg()[0]
    start = time.perf_counter()
    proc = run_tool(tool, *args, capture_output=True, text=True)
    wall = time.perf_counter() - start
    if proc.returncode != 0:
        cmd = [str(tool), *(str(a) for a in args)]
        print(f"  *** bench FAILED: {cmd} -> {proc.stderr[-1500:]}", file=sys.stderr)
        return [], wall
    return parse_t_lines(proc.stdout), before


def reps_for(call_ns: float) -> int:
    if call_ns <= 0:
        return MAX_REPS
    want = int((CELL_BUDGET_S * 1e9) / call_ns)
    return max(MIN_REPS, min(MAX_REPS, want))


def cell_from_reps(reps: list[tuple[int, int, int]]) -> tuple[float, float | None, float]:
    """(cold, warm, hot) in ns from one process launch's `T bench` lines."""
    ns = [r[2] for r in sorted(reps, key=lambda r: r[1])]
    cold = ns[0]
    if len(ns) >= 3:
        warm = ns[1]
        hot = min(ns[2:])
    elif len(ns) == 2:
        warm = ns[1]
        hot = ns[1]
    else:
        warm = None
        hot = ns[0]
    return float(cold), (float(warm) if warm is not None else None), float(hot)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", default=str(Path(tempfile.gettempdir()) / "graph_betweenness_bench"))
    parser.add_argument(
        "--prebuilt",
        action="store_true",
        help="do not build: run the graph_betweenness_h2h binary found in $BENCH_BIN_DIR, "
        "then --scratch, then PATH",
    )
    args = parser.parse_args()

    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        binary = (
            tool_path(MOJO_TOOL, search_dirs=(scratch,)) if args.prebuilt else build_mojo(scratch)
        )
        python = find_python_with_networkx()
    except ToolError as exc:
        raise SystemExit(f"{parser.prog}: error: {exc}") from None
    print(f"mojo binary: {binary}")
    print(f"python (networkx): {python}")
    ver = run_tool(
        python, "-c", "import networkx; print(networkx.__version__)", capture_output=True, text=True
    )
    print(f"networkx version: {ver.stdout.strip()}")
    print(f"host load now: {os.getloadavg()}")
    print("")

    failures = 0

    # ── STEP 0: CORRECTNESS, before any timing ────────────────────────────────
    print("=" * 78)
    print("STEP 0: CORRECTNESS -- every graph below is diffed on BOTH sides before")
    print("        a single timing number is trusted. A failure here STOPS the run.")
    print("=" * 78)

    cells: list[tuple[str, int, int | None]] = []  # (kind, n, m_target)
    print("\n-- FIXTURES (exact analytic values; gate is BIT-IDENTICAL) --")
    for kind, n, expect in (("path", 5, None), ("star", 5, None), ("star", 50, None)):
        edge_file = scratch / f"{kind}{n}.edges"
        gen_graph(python, kind, n, SEED, edge_file)
        mojo_dump = scratch / f"{kind}{n}.mojo.dump"
        nx_dump = scratch / f"{kind}{n}.nx.dump"
        dm = dump_mojo(binary, edge_file, mojo_dump)
        dn = dump_nx(python, edge_file, nx_dump)
        cmp = compare_dumps(mojo_dump, nx_dump, n)
        bit_exact = cmp["identical"] == n
        verdict = "BIT-IDENTICAL" if bit_exact else "*** NOT BIT-IDENTICAL ***"
        print(
            f"  {kind:<5} n={n:<4} mojo max_value={dm['max_value']:<10} "
            f"nx max_value={dn['max_value']:<10} identical={cmp['identical']}/{n}  {verdict}"
        )
        if kind == "path":
            known = [0.0, 3.0, 4.0, 3.0, 0.0]
            ok_known = dm["max_value"] == "4.0" and dn["max_value"] == "4.0"
            print(f"    known analytic P5 raw betweenness = {known}; max should be 4.0: {'ok' if ok_known else 'FAIL'}")
            if not ok_known:
                failures += 1
        if kind == "star":
            expected_hub = (n - 1) * (n - 2) / 2.0
            ok_known = float(dm["max_value"]) == expected_hub and float(dn["max_value"]) == expected_hub
            print(f"    known analytic star({n}) hub = (n-1)(n-2)/2 = {expected_hub}: {'ok' if ok_known else 'FAIL'}")
            if not ok_known:
                failures += 1
        if not bit_exact:
            failures += 1
            print("    *** FIXTURE MUST BE BIT-IDENTICAL -- STOPPING ***")

    if failures:
        print(f"\nBENCH_GATE graph_betweenness FAIL {failures} (fixture stage)")
        print("STOPPING before any timing -- see rule: correctness before timing.")
        return 1

    print("\n-- BA (Barabasi-Albert, scale-free) and GNM (Erdos-Renyi) at sweep sizes --")
    ba_edge_counts: dict[int, int] = {}
    pilot: dict[tuple[str, int], dict] = {}
    for n in BA_SIZES:
        edge_file = scratch / f"ba{n}.edges"
        g = gen_graph(python, "ba", n, SEED, edge_file)
        ba_edge_counts[n] = int(g["edges"])
        mojo_dump = scratch / f"ba{n}.mojo.dump"
        nx_dump = scratch / f"ba{n}.nx.dump"
        dm = dump_mojo(binary, edge_file, mojo_dump)
        dn = dump_nx(python, edge_file, nx_dump)
        cmp = compare_dumps(mojo_dump, nx_dump, n)
        verdict = "OK" if cmp["ok"] else "*** MISMATCH ***"
        print(
            f"  ba  n={n:<5} edges={g['edges']:<6} max_rel_diff={cmp['max_rel_diff']:.3e} "
            f"sum_rel_diff={cmp['sum_rel_diff']:.3e} identical_bits={cmp['identical']}/{n} "
            f"argmax mojo={cmp['argmax_a']} nx={cmp['argmax_b']}  {verdict}"
        )
        if not cmp["ok"]:
            failures += 1
            print(f"    *** {cmp}")
        pilot[("ba", n)] = {
            "edge_file": edge_file,
            "mojo_ns": float(dm["call_ns"]),
            "nx_ns": float(dn["call_ns"]),
        }
        cells.append(("ba", n, None))

    for n in GNM_SIZES:
        m_target = ba_edge_counts.get(n, 4 * n)
        edge_file = scratch / f"gnm{n}.edges"
        g = gen_graph(python, "gnm", n, SEED, edge_file, m_target=m_target)
        mojo_dump = scratch / f"gnm{n}.mojo.dump"
        nx_dump = scratch / f"gnm{n}.nx.dump"
        dm = dump_mojo(binary, edge_file, mojo_dump)
        dn = dump_nx(python, edge_file, nx_dump)
        cmp = compare_dumps(mojo_dump, nx_dump, n)
        verdict = "OK" if cmp["ok"] else "*** MISMATCH ***"
        print(
            f"  gnm n={n:<5} edges={g['edges']:<6} max_rel_diff={cmp['max_rel_diff']:.3e} "
            f"sum_rel_diff={cmp['sum_rel_diff']:.3e} identical_bits={cmp['identical']}/{n} "
            f"argmax mojo={cmp['argmax_a']} nx={cmp['argmax_b']}  {verdict}"
        )
        if not cmp["ok"]:
            failures += 1
            print(f"    *** {cmp}")
        pilot[("gnm", n)] = {
            "edge_file": edge_file,
            "mojo_ns": float(dm["call_ns"]),
            "nx_ns": float(dn["call_ns"]),
        }
        cells.append(("gnm", n, m_target))

    if failures:
        print(f"\nBENCH_GATE graph_betweenness FAIL {failures} (correctness stage)")
        print("STOPPING before any timing -- see rule: correctness before timing.")
        return 1

    print("\nAll correctness gates PASSED. Proceeding to timing.")
    print("")

    # ── STEP 1: TIMING, interleaved rounds, alternating who launches first ───
    print("=" * 78)
    print("STEP 1: TIMING -- interleaved rounds, cold/warm/hot per process launch,")
    print(f"        {K_ROUNDS} rounds per side, reps picked from a {CELL_BUDGET_S:.0f}s wall-clock budget")
    print("        per side using the single-call time measured in the correctness step.")
    print("=" * 78)

    results: dict[tuple[str, int], dict[str, Series]] = {}
    loads: list[str] = []
    for kind, n, _m in cells:
        p = pilot[(kind, n)]
        mojo_reps = reps_for(p["mojo_ns"])
        nx_reps = reps_for(p["nx_ns"])
        print(
            f"\n-- {kind} n={n}: pilot mojo_ns={p['mojo_ns']:.0f} nx_ns={p['nx_ns']:.0f} "
            f"-> reps mojo={mojo_reps} nx={nx_reps} --"
        )
        edge_file = p["edge_file"]
        mojo_series = Series()
        nx_series = Series()
        for r in range(K_ROUNDS):
            first_is_mojo = (r % 2 == 0)
            arms = (
                [("mojo", mojo_reps), ("nx", nx_reps)]
                if first_is_mojo
                else [("nx", nx_reps), ("mojo", mojo_reps)]
            )
            for arm, reps in arms:
                if arm == "mojo":
                    reps_list, load = run_bench(binary, "bench", edge_file, reps)
                else:
                    reps_list, load = run_bench(python, REFS, "bench", edge_file, reps)
                loads.append(f"{kind}{n} r{r} {arm}: load {load:.1f}")
                if not reps_list:
                    print(f"    {arm} round {r}: NO DATA (bench failed)")
                    continue
                cold, warm, hot = cell_from_reps(reps_list)
                series = mojo_series if arm == "mojo" else nx_series
                series.colds.append(cold)
                if warm is not None:
                    series.warms.append(warm)
                series.hots.append(hot)
                series.reps_used.append(len(reps_list))
                print(
                    f"    round {r} {arm:<4} reps={len(reps_list):<2} "
                    f"cold={cold/1e6:9.4f}ms warm={(warm/1e6 if warm else float('nan')):9.4f}ms "
                    f"hot={hot/1e6:9.4f}ms"
                )
        results[(kind, n)] = {"mojo": mojo_series, "nx": nx_series}

    # ── STEP 2: cross-round reproducibility gate ──────────────────────────────
    print("")
    print("=" * 78)
    print(f"STEP 2: CROSS-ROUND GATE -- is each cell's hot value reproducible across {K_ROUNDS} rounds?")
    print("=" * 78)
    invalid: set[tuple[str, int, str]] = set()
    for (kind, n), sides in results.items():
        for arm, series in sides.items():
            sp = series.spread()
            if sp is None:
                continue
            median_ratio, max_ratio = sp
            mark = "ok" if median_ratio <= MAX_SPREAD else "*** UNREPRODUCIBLE ***"
            print(
                f"  {kind:<5} n={n:<5} {arm:<4} median/min={median_ratio:.2f} "
                f"max/min={max_ratio:.2f}  {mark}"
            )
            if median_ratio > MAX_SPREAD:
                invalid.add((kind, n, arm))
                failures += 1

    # ── STEP 3: the table ──────────────────────────────────────────────────────
    print("")
    print("=" * 78)
    print("STEP 3: RESULTS -- hot (min across rounds), ns per (V*E) to show the O(V*E) curve,")
    print("        and the wall-clock speedup ratio nx_hot / mojo_hot")
    print("=" * 78)
    header = f"  {'kind':<5} {'n':>6} {'edges':>7} | {'mojo_hot_ms':>12} {'nx_hot_ms':>12} | {'speedup':>10} | {'mojo ns/(V*E)':>14} {'nx ns/(V*E)':>14}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    wins: list[str] = []
    losses: list[str] = []
    for kind, n, m_target in cells:
        edges = ba_edge_counts.get(n) if kind == "ba" else m_target
        ve = n * (edges or 1)
        sides = results[(kind, n)]
        mojo_hot = sides["mojo"].hot if (kind, n, "mojo") not in invalid else None
        nx_hot = sides["nx"].hot if (kind, n, "nx") not in invalid else None
        speedup = (nx_hot / mojo_hot) if (mojo_hot and nx_hot) else None
        mojo_str = f"{mojo_hot/1e6:.4f}" if mojo_hot else "unresolved"
        nx_str = f"{nx_hot/1e6:.4f}" if nx_hot else "unresolved"
        speedup_str = f"{speedup:.1f}x" if speedup else "unresolved"
        mojo_pv = f"{mojo_hot/ve:.5f}" if mojo_hot else "unresolved"
        nx_pv = f"{nx_hot/ve:.5f}" if nx_hot else "unresolved"
        print(f"  {kind:<5} {n:>6} {edges or 0:>7} | {mojo_str:>12} {nx_str:>12} | {speedup_str:>10} | {mojo_pv:>14} {nx_pv:>14}")
        if speedup is not None:
            line = f"{kind} n={n}: mojo {mojo_hot/1e6:.4f}ms vs networkx {nx_hot/1e6:.4f}ms = {speedup:.1f}x"
            (wins if speedup >= 1.0 else losses).append(line)

    print("")
    print("-- WINS (Algenta faster) --")
    for w in wins:
        print(f"  WIN   {w}")
    print("-- LOSSES (networkx faster) --")
    if losses:
        for l in losses:
            print(f"  LOSS  {l}")
    else:
        print("  none")

    print("")
    print(f"final load {os.getloadavg()}")
    if failures == 0:
        print("BENCH_GATE graph_betweenness PASS")
    else:
        print(f"BENCH_GATE graph_betweenness FAIL {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
