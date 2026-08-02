#!/usr/bin/env python3
"""mutate_h2o_stats.py — anti-vacuity for `query.topk_dense`,
`query.comoments_packed` and `query.median_packed` (H2O q8/q9/q6).

Same shape as `mutate_composed.py`: apply one mutation at a time to an
engine file, run the hand suite that exists to catch it, restore from a
pristine snapshot, and report which mutations were CAUGHT vs VACUOUS. A
VACUOUS mutation is a hole in the suite unless it is marked
`expect_caught=False` because the mutation is genuinely behaviour-preserving.

Usage:
    mutate_h2o_stats.py snapshot
    mutate_h2o_stats.py [name ...]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPK = ROOT / "mojo" / "engine" / "query" / "topk_dense.mojo"
COMOMENTS = ROOT / "mojo" / "engine" / "query" / "comoments_packed.mojo"
MEDIAN = ROOT / "mojo" / "engine" / "query" / "median_packed.mojo"
SUITE_TOPK = ROOT / "mojo" / "tests" / "libs" / "test_query_topk_dense.mojo"
SUITE_COMOMENTS = ROOT / "mojo" / "tests" / "libs" / "test_query_comoments_packed.mojo"
SUITE_MEDIAN = ROOT / "mojo" / "tests" / "libs" / "test_query_median_packed.mojo"
ALL_FILES = [TOPK, COMOMENTS, MEDIAN, SUITE_TOPK, SUITE_COMOMENTS, SUITE_MEDIAN]
SNAP = ROOT / "benchmarks" / "h2o_groupby" / ".pristine_stats"
MOJO_ENV = Path("/Users/angel/Developer/decision-engine/mojo_env")


@dataclass
class Mutation:
    name: str
    target: Path
    old: str
    new: str
    why: str
    suite: Path
    expect_caught: bool = True


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_topk_wrong_compare_variable",
        target=TOPK,
        old="    if value >= top1:\n        top2 = top1\n        top1 = value\n        return",
        new="    if value >= top2:\n        top2 = top1\n        top1 = value\n        return",
        why="the 'does this beat the CURRENT LARGEST' test reads the wrong "
        "slot (top2 instead of top1), so a value that beats the runner-up "
        "but not the leader gets wrongly promoted to top1 — the top-2 "
        "ORDERING invariant (top1 >= top2) breaks on exactly the data shape "
        "(three or more distinct values per group) block1's random "
        "crosscheck exists to exercise.",
        suite=SUITE_TOPK,
    ),
    Mutation(
        name="M2_topk_seed_wrong_slot",
        target=TOPK,
        old="    if not (top1 == top1):\n        # First real value this pair has ever seen.\n        top1 = value\n        return",
        new="    if not (top1 == top1):\n        # First real value this pair has ever seen.\n        top2 = value\n        return",
        why="the FIRST real value a pair ever sees is written into top2 "
        "instead of top1, so top1 stays the unseeded NaN sentinel forever — "
        "every group's present1 is wrongly False and top1 is never reported, "
        "which the size-1 and random-crosscheck blocks both catch.",
        suite=SUITE_TOPK,
    ),
    Mutation(
        name="M3_topk_nan_check_inverted",
        target=TOPK,
        old="    if value != value:\n        # NaN ranks nothing — this plane's extremum policy, unchanged.\n        return",
        new="    if value == value:\n        # NaN ranks nothing — this plane's extremum policy, unchanged.\n        return",
        why="inverts the NaN guard, so every ORDINARY (non-NaN) value now "
        "returns immediately without updating anything, and only NaN values "
        "reach the ranking logic. No group's top1/top2 is ever set from a "
        "real value again — the most totalizing possible break of the fold, "
        "and every block that reads a real number back out catches it.",
        suite=SUITE_TOPK,
    ),
    Mutation(
        name="M4_comoment_sign_flip",
        target=COMOMENTS,
        old="    var num = n * sxy - sx * sy",
        new="    var num = n * sxy + sx * sy",
        why="flips the sign of the cross term in Pearson's numerator. The "
        "hand-checkable PERFECT correlation fixtures (y=2x+1 and y=-x) each "
        "assert r^2 == 1.0 to 1e-9, and a sign-flipped numerator gives a "
        "different, non-1.0 number on both — the co-moment SUM formula is "
        "load-bearing precisely because those fixtures were built to prove it.",
        suite=SUITE_COMOMENTS,
    ),
    Mutation(
        name="M5_comoment_present_threshold",
        target=COMOMENTS,
        old="    if n < 2.0:\n        r2 = 0.0\n        present = False\n        return",
        new="    if n < 1.0:\n        r2 = 0.0\n        present = False\n        return",
        why="weakens the count gate from n<2 to n<1 — genuinely VACUOUS, and "
        "worth recording as such rather than forcing a fake catch: for n=1, "
        "`denx = n*sx2 - sx*sx` is EXACTLY `x^2 - x^2 = 0.0` in floating "
        "point (one point has no spread), so the very next line's "
        "zero-variance gate (`not (denx > 0.0)`) already reports absent by a "
        "second, independent route. The n<2 guard is redundant defense in "
        "depth for THIS module's specific algebra, not the only thing "
        "standing between a 1-row group and a wrong answer — unlike "
        "`M4_comoment_sign_flip`/`M6`, which the zero-variance gate cannot "
        "rescue.",
        suite=SUITE_COMOMENTS,
        expect_caught=False,
    ),
    Mutation(
        name="M6_comoment_incomplete_pair_drops_group",
        target=COMOMENTS,
        old="            elif seenp[ebase_w + slot] == 0:\n                # The key names a group even when this row's (x, y) pair is\n                # incomplete — matching \"a row whose value is null still\n                # belongs to the group\" elsewhere in this plane. The group\n                # exists; this row simply moves no moment.\n                seenp[ebase_w + slot] = 1\n                op_ptr[w].append(slot)",
        new="            elif False:\n                seenp[ebase_w + slot] = 1\n                op_ptr[w].append(slot)",
        why="a group whose only rows have a null x or y is never registered "
        "at all — it silently disappears from the answer instead of "
        "reporting present=False. block3's null test asserts the group DOES "
        "exist (count 0, present False), which is the 'a row without a full "
        "pair still belongs to the group' contract this module's header "
        "states.",
        suite=SUITE_COMOMENTS,
        expect_caught=True,
    ),
    Mutation(
        name="M7_median_even_selection_broken",
        target=MEDIAN,
        old="    if n % 2 == 1:\n        return sorted_vals[n // 2]\n    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0",
        new="    if n % 2 == 1:\n        return sorted_vals[n // 2]\n    return sorted_vals[n // 2]",
        why="an EVEN-count group's median stops averaging the two middle "
        "values and just returns the upper-middle one — exactly the "
        "hand-checkable [1, 2, 3, 100] fixture exists to catch (expects 2.5, "
        "a value that equals NEITHER input; the mutant returns 3.0).",
        suite=SUITE_MEDIAN,
    ),
    Mutation(
        name="M8_median_offset_prefix_shifted",
        target=MEDIAN,
        old="    for slot in range(slots):\n        slot_offset[slot] = running\n        var total = 0\n        for w in range(bands):\n            total += Int(statp[w * slots + slot].count)\n        running += total",
        new="    for slot in range(slots):\n        var total = 0\n        for w in range(bands):\n            total += Int(statp[w * slots + slot].count)\n        running += total\n        slot_offset[slot] = running",
        why="the per-slot scatter OFFSET is computed AFTER adding this "
        "slot's own count instead of before, so every group's region starts "
        "one group's-worth too late and overlaps its neighbour's. This is "
        "caught either by the in-pass self-check (refuses with "
        "GROUP_MEDIAN_STATE_TOO_LARGE, failing every ok() assertion) or, if "
        "that guard were absent, by wrong medians in the random crosscheck — "
        "the exact 'median's partition offsets' claim this file makes.",
        suite=SUITE_MEDIAN,
    ),
    Mutation(
        name="M9_median_merge_worker0_only",
        target=MEDIAN,
        old="        var merged = GroupAccumulator(0.0)\n        for w in range(bands):\n            merged.merge_from(state[w * slots + slot])",
        new="        var merged = GroupAccumulator(0.0)\n        for w in range(bands):\n            if w == 0:\n                merged.merge_from(state[w * slots + slot])",
        why="the PARALLEL MERGE across bands for the sd/count side stops "
        "folding any worker but the first, so any group whose rows landed in "
        "more than one band reports sd/count computed from a PARTIAL slice. "
        "The random crosscheck runs at up to 16 workers over ~10 000 groups "
        "sized to span multiple bands, so this is caught broadly rather than "
        "by a single fixture.",
        suite=SUITE_MEDIAN,
    ),
]


def snapshot() -> None:
    SNAP.mkdir(exist_ok=True)
    for p in ALL_FILES:
        shutil.copy2(p, SNAP / p.name)
    print(f"snapshot -> {SNAP}")


def restore() -> None:
    for p in ALL_FILES:
        src = SNAP / p.name
        if src.exists():
            shutil.copy2(src, p)


def run_suite(suite: Path) -> tuple[bool, str]:
    cmd = ["pixi", "run", "mojo", "run", f"-I{ROOT}/mojo/engine", str(suite)]
    proc = subprocess.run(cmd, cwd=MOJO_ENV, capture_output=True, text=True, timeout=600)
    out = proc.stdout
    lines = [
        ln for ln in out.splitlines()
        if ln.startswith(("  FAIL", "checks=", "ALL PASS", "FAILED"))
    ]
    tail = "\n".join(lines[-6:])
    if proc.returncode != 0 and "error:" in proc.stderr:
        return False, "COMPILE ERROR: " + proc.stderr.strip().splitlines()[-1][:200]
    return ("ALL PASS" in out and "FAILED" not in out), tail


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "snapshot":
        snapshot()
        return 0
    if not SNAP.exists():
        snapshot()
    wanted = set(sys.argv[1:])
    restore()

    baselines: dict[Path, bool] = {}
    for suite in (SUITE_TOPK, SUITE_COMOMENTS, SUITE_MEDIAN):
        passed, tail = run_suite(suite)
        baselines[suite] = passed
        print(f"BASELINE {suite.name} pass={passed}\n{tail}\n")
        if not passed:
            print(f"baseline {suite.name} is not green; refusing to attribute anything to a mutation")
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
        passed, tail = run_suite(m.suite)
        restore()
        was_caught = not passed
        verdict = "CAUGHT" if was_caught else "VACUOUS"
        agree = was_caught == m.expect_caught
        flag = "" if agree else "   <<< UNEXPECTED"
        print(f"{m.name} [{m.suite.name}]: {verdict} (expected "
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
