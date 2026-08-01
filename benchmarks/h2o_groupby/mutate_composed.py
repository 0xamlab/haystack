#!/usr/bin/env python3
"""mutate_composed.py — anti-vacuity for `query.composed`.

A green suite proves nothing until it has been shown RED against code that is
wrong in a way the suite claims to catch. This applies one mutation at a time
to `mojo/engine/query/composed.mojo`, runs the target (the hand suite, or the
H2O bench for the BENCH_GATEs), restores from a pristine snapshot, and reports
which mutations were caught.

A mutation reported VACUOUS is a hole in the suite, not a pass — unless the
mutation is BEHAVIOUR-PRESERVING, in which case the expectation says so and the
vacuity is the correct answer.

Usage:
    mutate_composed.py snapshot            # re-take the pristine copy
    mutate_composed.py [name ...]          # run all, or the named ones
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "mojo" / "engine" / "query" / "composed.mojo"
PACKED = ROOT / "mojo" / "engine" / "query" / "packedkey.mojo"
SUITE = ROOT / "mojo" / "tests" / "libs" / "test_query_composed.mojo"
BENCH = ROOT / "benchmarks" / "mojo_benchmarks" / "bench_h2o_composed.mojo"
SNAP = ROOT / "benchmarks" / "h2o_groupby" / ".pristine"
MOJO_ENV = Path("/Users/angel/Developer/decision-engine/mojo_env")


@dataclass
class Mutation:
    name: str
    target: Path
    old: str
    new: str
    why: str
    expect_caught: bool = True
    run: str = "suite"  # "suite" | "bench:<q>"


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_merge_descending",
        target=ENGINE,
        old="                for w in range(workers):\n"
        "                    var base = w * region + code * stride",
        new="                for wr in range(workers):\n"
        "                    var w = workers - 1 - wr\n"
        "                    var base = w * region + code * stride",
        why="folds each group's bands in DESCENDING worker order. Legal "
        "arithmetic, different association — the exact ulp-level defect a "
        "checksum waves through and the whole reason identity is bitwise.",
    ),
    Mutation(
        name="M2_merge_range_overlap",
        target=ENGINE,
        old="            var g_hi = g_lo + gband\n"
        "            if g_hi > n_groups:\n"
        "                g_hi = n_groups",
        new="            var g_hi = g_lo + gband + 1\n"
        "            if g_hi > n_groups:\n"
        "                g_hi = n_groups",
        why="parallel merge ranges OVERLAP by one group. Each overlapped cell "
        "is written twice with the same value, so the answer survives — the "
        "point is whether anything notices a racing double write.",
        expect_caught=False,
    ),
    Mutation(
        name="M3_seed_zero_not_nan",
        target=ENGINE,
        old="                    if opp[j] == AGG_MIN or opp[j] == AGG_MAX:\n"
        "                        accw[base + pay0 + j * paystep] = nan_seed",
        new="                    if opp[j] == AGG_MIN or opp[j] == AGG_MAX:\n"
        "                        accw[base + pay0 + j * paystep] = 0.0",
        why="the in-band extremum seed becomes 0.0 instead of the canonical "
        "NaN. An all-NaN group then reports a minimum of 0.0 — a value nobody "
        "observed. This is the #459 defect's shape, reintroduced through the "
        "seed move the composition performs.",
    ),
    Mutation(
        name="M4_no_worker_cap",
        target=ENGINE,
        old="    var w = requested\n    if w < 1:\n        w = 1\n"
        "    while w >= 1:\n"
        "        if dense_state_bytes(cardinality, n_aggs, w, shared_count)"
        " <= DENSE_MAX_STATE_BYTES:\n"
        "            return w\n"
        "        w -= 1\n"
        "    return 0",
        new="    var w = requested\n    if w < 1:\n        w = 1\n    return w",
        why="the router stops capping the band count at the dense state "
        "budget. The 1e5-code questions then ask for a state the engine "
        "refuses, and the route silently becomes a fallback — a lost win that "
        "no correctness check would see.",
        run="bench:q3",
    ),
    Mutation(
        name="M5_domain_drops_integrality",
        target=ENGINE,
        old="            var code = Int(k)\n"
        "            if Float64(code) != k:\n"
        "                ok = False\n"
        "                break",
        new="            var code = Int(k)",
        why="the exact domain scan stops rejecting a fractional key, so it "
        "reports dense for a column that is not. The engine's own guard still "
        "refuses, so the answer stays right — what breaks is the ROUTE's "
        "honesty, and a route that lies costs a whole wasted scan.",
    ),
    Mutation(
        name="M6_bound_off_by_one",
        target=ENGINE,
        old="    return _ExactDomain(True, best + 1)",
        new="    return _ExactDomain(True, best)",
        why="the exact bound becomes max instead of max+1, so the single "
        "largest code falls outside the dense array. The guard catches it and "
        "the route falls back, which is safe and WRONG: the whole point of the "
        "exact scan is a bound that cannot refuse.",
    ),
    Mutation(
        name="M7_status_collision_restored",
        target=PACKED,
        old="comptime GROUP_PACKED_DOMAIN_TOO_LARGE: Int = 336",
        new="comptime GROUP_PACKED_DOMAIN_TOO_LARGE: Int = 334",
        why="puts packedkey's refusal back on 334, where coded_dense already "
        "lives. This is the real collision composition found; the registry "
        "block exists to make it fail a test instead of shipping.",
    ),
    Mutation(
        name="M8_present_from_count",
        target=ENGINE,
        old="                var answerable = acc_g.has_answer(op)",
        new="                var answerable = acc_g.count >= 1.0",
        why="presence stops asking the frozen contract and guesses from the "
        "count. SUM and COUNT of an empty group ARE answerable (0.0 and 0), so "
        "this reports absent where the contract reports present.",
    ),
    Mutation(
        name="M9_always_parallel_merge",
        target=ENGINE,
        old="comptime COMPOSE_PARALLEL_MERGE_MIN_FOLDS: Int = 262_144",
        new="comptime COMPOSE_PARALLEL_MERGE_MIN_FOLDS: Int = 0",
        why="drops the parallel-merge threshold to 0 so every call fans out. "
        "CAUGHT, but read WHICH checks fail: the threshold assertions and the "
        "plan read-out, and ZERO of block1's `par_eq_ser` bit comparisons. "
        "That split is the evidence the switch is a performance switch — a "
        "correctness failure here would mean the merge decomposition is "
        "illegal. It also exposed a real coupling: the saturation ceiling in "
        "`compose_merge_folds` was a multiple of this threshold, so a tuning "
        "change silently disabled an overflow guard. Now its own constant.",
        expect_caught=True,
    ),
    Mutation(
        name="M10_bench_identity_reference",
        target=BENCH,
        old="            reference = group_by_many_banded(\n"
        "                batch, key_cols, value_cols, opcodes, plan.workers\n"
        "            )",
        new="            reference = group_by_many_banded(\n"
        "                batch, key_cols, value_cols, opcodes, plan.workers + 1\n"
        "            )",
        why="points the bench's identity reference at a DIFFERENT band count. "
        "Bit identity is per worker count, so this must fail. Run on q3 and "
        "NOT q1: q1 sums an integer-valued column, so every association gives "
        "the same bits and the mutation is genuinely behaviour-preserving "
        "there — it passed on q1, which is a fact about q1's weakness as an "
        "identity fixture, not about the gate. q3 carries a Welford mean over "
        "continuous v3, where the association is observable in the last ulp.",
        run="bench:q3",
    ),
]


def snapshot() -> None:
    SNAP.mkdir(exist_ok=True)
    for p in (ENGINE, PACKED, SUITE, BENCH):
        shutil.copy2(p, SNAP / p.name)
    print(f"snapshot -> {SNAP}")


def restore() -> None:
    for p in (ENGINE, PACKED, SUITE, BENCH):
        src = SNAP / p.name
        if src.exists():
            shutil.copy2(src, p)


def run_target(m: Mutation) -> tuple[bool, str]:
    """(passed, tail) — `passed` means the target reported success."""
    if m.run == "suite":
        cmd = [
            "pixi", "run", "mojo", "run",
            f"-I{ROOT}/mojo/engine", str(SUITE),
        ]
    else:
        q = m.run.split(":", 1)[1]
        cmd = [
            "pixi", "run", "mojo", "run",
            f"-I{ROOT}/mojo/engine", str(BENCH), q, "1", "0",
        ]
    proc = subprocess.run(
        cmd, cwd=MOJO_ENV, capture_output=True, text=True, timeout=3600
    )
    out = proc.stdout
    lines = [
        ln for ln in out.splitlines()
        if ln.startswith(("  FAIL", "checks=", "ALL PASS", "FAILED",
                          "BENCH_GATE", "BENCH_OK", "BENCH ", "REP "))
    ]
    tail = "\n".join(lines[-6:])
    if proc.returncode != 0 and "error:" in proc.stderr:
        return False, "COMPILE ERROR: " + proc.stderr.strip().splitlines()[-1][:160]
    if m.run == "suite":
        return ("ALL PASS" in out and "FAILED" not in out), tail
    return (proc.returncode == 0 and "BENCH_OK" in out), tail


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "snapshot":
        snapshot()
        return 0
    if not SNAP.exists():
        snapshot()
    wanted = set(sys.argv[1:])
    restore()

    base_pass, base_tail = run_target(
        Mutation("baseline", ENGINE, "", "", "", run="suite")
    )
    print(f"BASELINE suite pass={base_pass}\n{base_tail}\n")
    if not base_pass:
        print("baseline is not green; refusing to attribute anything to a mutation")
        return 2

    caught, missed, surprises = 0, 0, 0
    for m in MUTATIONS:
        if wanted and m.name not in wanted:
            continue
        restore()
        text = m.target.read_text()
        if m.old not in text:
            print(f"{m.name}: ANCHOR NOT FOUND in {m.target.name} — mutation skipped")
            surprises += 1
            continue
        m.target.write_text(text.replace(m.old, m.new, 1))
        passed, tail = run_target(m)
        restore()
        was_caught = not passed
        verdict = "CAUGHT" if was_caught else "VACUOUS"
        agree = was_caught == m.expect_caught
        flag = "" if agree else "   <<< UNEXPECTED"
        print(f"{m.name} [{m.run}]: {verdict} (expected "
              f"{'CAUGHT' if m.expect_caught else 'VACUOUS'}){flag}")
        print(f"    why: {m.why}")
        if tail:
            print("    " + tail.replace("\n", "\n    "))
        print()
        if was_caught:
            caught += 1
        else:
            missed += 1
        if not agree:
            surprises += 1

    restore()
    print(f"caught={caught} vacuous={missed} unexpected={surprises}")
    return 1 if surprises else 0


if __name__ == "__main__":
    raise SystemExit(main())
