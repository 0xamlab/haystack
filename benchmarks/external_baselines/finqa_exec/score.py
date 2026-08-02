#!/usr/bin/env python3
"""score.py — run progexec over the real FinQA gold programs and score it, and two naive
baselines, against the dataset's own exe_ans, at the dataset's own exact-match rule.

Usage:
    python3 score.py <out_dir> [--mojo-binary /path/to/compiled/measure_progexec_finqa]

<out_dir> must already contain finqa_progexec.spec and finqa_gold.json (from
emit_specs.py). Without --mojo-binary, runs the Mojo side under the JIT via
`pixi run mojo run` from mojo_env/ (slower, and rule 1b applies — see the Reproduce
section this script's output is meant to back).
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOJO_ENGINE_DIR = REPO_ROOT / "mojo" / "engine"
MOJO_ENV_DIR = REPO_ROOT / "mojo_env"
BENCH_MOJO = REPO_ROOT / "benchmarks" / "mojo_benchmarks" / "measure_progexec_finqa.mojo"


def hex_to_f64(h: str) -> float:
    return struct.unpack(">d", bytes.fromhex(h))[0]


def run_mojo(spec_path: Path, mojo_binary: str | None) -> list[str]:
    if mojo_binary:
        proc = subprocess.run(
            [mojo_binary, str(spec_path)], capture_output=True, text=True, check=True
        )
    else:
        proc = subprocess.run(
            [
                "pixi", "run", "mojo", "run",
                "-I", str(MOJO_ENGINE_DIR),
                str(BENCH_MOJO), str(spec_path),
            ],
            cwd=str(MOJO_ENV_DIR),
            capture_output=True, text=True, check=True,
        )
    return proc.stdout.splitlines()


def parse_mojo_output(lines: list[str]):
    out = {}
    for line in lines:
        toks = line.split(" ")
        if not toks or toks[0] != "RESULT":
            continue
        prog_id = toks[1]
        status = int(toks[2])
        present = toks[3] == "1"
        kind = toks[4]
        if kind == "bool":
            out[prog_id] = {"present": present, "status": status, "value": toks[5]}
        else:
            out[prog_id] = {"present": present, "status": status, "value": hex_to_f64(toks[5])}
    return out


def matches_gold(value, gold) -> bool:
    """The official evaluator's own comparison: plain `==`, nothing fuzzy."""
    if value is None:
        return False
    return value == gold


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_dir = Path(sys.argv[1])
    mojo_binary = None
    if "--mojo-binary" in sys.argv:
        mojo_binary = sys.argv[sys.argv.index("--mojo-binary") + 1]

    gold = json.loads((out_dir / "finqa_gold.json").read_text())
    mojo_lines = run_mojo(out_dir / "finqa_progexec.spec", mojo_binary)
    mojo_results = parse_mojo_output(mojo_lines)

    n = len(gold)
    progexec_correct = 0
    naive_a_correct = 0
    naive_b_correct = 0
    naive_c_correct = 0

    progexec_wrong = []
    naive_a_wrong = []
    naive_b_wrong = []
    naive_c_wrong = []

    for rec in gold:
        prog_id = rec["id"]
        gold_val = rec["gold"]
        mres = mojo_results.get(prog_id)
        if mres is None:
            progexec_wrong.append((prog_id, "MISSING_FROM_MOJO_OUTPUT", gold_val))
            continue
        pe_val = mres["value"] if mres["present"] else None
        if matches_gold(pe_val, gold_val):
            progexec_correct += 1
        else:
            progexec_wrong.append((prog_id, pe_val, gold_val))

        naive_a_val = rec["naive_round_every_step"]
        if matches_gold(naive_a_val, gold_val):
            naive_a_correct += 1
        else:
            naive_a_wrong.append((prog_id, naive_a_val, gold_val, rec["program"]))

        naive_b_val = rec["naive_scale_round_final"]
        if matches_gold(naive_b_val, gold_val):
            naive_b_correct += 1
        else:
            naive_b_wrong.append((prog_id, naive_b_val, gold_val, rec["program"]))

        naive_c_val = rec["naive_steps_substitution"]
        if matches_gold(naive_c_val, gold_val):
            naive_c_correct += 1
        else:
            naive_c_wrong.append((prog_id, naive_c_val, gold_val, rec["program"]))

    arms = [
        ("progexec (Algenta, Mojo)", progexec_correct, progexec_wrong),
        ("naive: round every step", naive_a_correct, naive_a_wrong),
        ("naive: single-multiply final round", naive_b_correct, naive_b_wrong),
        ("naive: steps-annotation substitution", naive_c_correct, naive_c_wrong),
    ]

    print(f"scored programs: {n}")
    print()
    print(f"{'arm':40s} {'exact-match':>12s} {'wrong':>8s}")
    for label, correct, wrong in arms:
        print(f"{label:40s} {correct / n:>12.5%} {len(wrong):>8d}")
    print()

    if progexec_wrong:
        print(f"progexec DIVERGED from exe_ans on {len(progexec_wrong)} programs (should be zero):")
        for row in progexec_wrong[:20]:
            print("  ", row)

    print()
    print(f"naive-B (single-multiply final round) real divergences ({len(naive_b_wrong)}):")
    for row in naive_b_wrong:
        print("  ", row)

    print()
    print(f"naive-A (round every step) real divergences, first 15 of {len(naive_a_wrong)}:")
    for row in naive_a_wrong[:15]:
        print("  ", row)

    print()
    print(f"naive-C (steps substitution) real divergences, first 15 of {len(naive_c_wrong)}:")
    for row in naive_c_wrong[:15]:
        print("  ", row)

    # Persist full divergence lists for the benchmark page / adversarial review.
    (out_dir / "progexec_divergences.json").write_text(json.dumps(progexec_wrong, indent=2))
    (out_dir / "naive_a_divergences.json").write_text(json.dumps(naive_a_wrong, indent=2))
    (out_dir / "naive_b_divergences.json").write_text(json.dumps(naive_b_wrong, indent=2))
    (out_dir / "naive_c_divergences.json").write_text(json.dumps(naive_c_wrong, indent=2))

    if progexec_wrong:
        sys.exit(1)


if __name__ == "__main__":
    main()
