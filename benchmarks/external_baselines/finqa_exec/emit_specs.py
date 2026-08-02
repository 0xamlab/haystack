#!/usr/bin/env python3
"""emit_specs.py — build progexec's flat-list input spec from the REAL FinQA dataset.

Usage:
    python3 emit_specs.py <finqa_dataset_dir> <out_dir>

<finqa_dataset_dir> is the `dataset/` directory of a clone of
https://github.com/czyssrs/FinQA (MIT licensed) containing train.json, dev.json,
test.json. The dataset (>100MB across the three splits) is not vendored into this repo;
clone it yourself:

    git clone https://github.com/czyssrs/FinQA /tmp/FinQA

Writes, into <out_dir>:
    finqa_progexec.spec   — progexec's flat input, one block per scored program, read by
                             benchmarks/mojo_benchmarks/measure_progexec_finqa.mojo
    finqa_gold.json        — one record per scored program, in the SAME order as the spec
                             file's blocks: id, source file, program text, gold exe_ans
                             (float or "yes"/"no"), and both naive-baseline outcomes
                             (computed here in Python — no Mojo, no arithmetic dispute
                             possible about what the naive baseline does)

A program is EXCLUDED (not scored, not silently miscounted as a pass) when its program
text does not parse under the official evaluator's own structural check, or its operand
resolution hits the one dead branch (`code/evaluate/evaluate.py`'s table-by-back-reference
case) that never occurs in the real data — see reference_eval.resolve_program.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_eval import (  # noqa: E402
    ARITH_OPS,
    OP_CODE,
    eval_official,
    eval_official_raw,
    parse_steps,
    process_row,
    program_tokenization,
    resolve_program,
    str_to_num,
)

ARG_LITERAL, ARG_REF, ARG_TABLE_ROW = 0, 1, 2


def f64_hex(v: float) -> str:
    return struct.pack(">d", float(v)).hex()


def naive_round_every_step(steps_parsed, table):
    """Naive baseline A: identical arithmetic, EXCEPT every intermediate result is
    rounded to 5 decimals before reuse, not only the final one. This is not a strawman:
    the official evaluator's OWN source has a commented-out
    `# this_res = round(this_res, 5)` inside its table branch (`code/evaluate/evaluate.py`
    line 180) — someone re-implementing this spec from that source, applying the same
    "round to 5 and move on" instinct everywhere rather than reading closely enough to see
    it is deliberately commented out ONLY there and absent from the arithmetic branch
    entirely, writes exactly this function."""
    table_dict = {row[0]: row[1:] for row in table}
    res_dict = {}
    this_res = "n/a"
    try:
        for ind, (op, arg1, arg2) in enumerate(steps_parsed):
            if op in ARITH_OPS:
                a1 = res_dict[int(arg1.replace("#", ""))] if "#" in arg1 else str_to_num(arg1)
                a2 = res_dict[int(arg2.replace("#", ""))] if "#" in arg2 else str_to_num(arg2)
                if a1 == "n/a" or a2 == "n/a":
                    return "n/a"
                if op == "add":
                    this_res = a1 + a2
                elif op == "subtract":
                    this_res = a1 - a2
                elif op == "multiply":
                    this_res = a1 * a2
                elif op == "divide":
                    if a2 == 0:
                        return "n/a"
                    this_res = a1 / a2
                elif op == "exp":
                    this_res = a1 ** a2
                elif op == "greater":
                    this_res = "yes" if a1 > a2 else "no"
                if this_res not in ("yes", "no"):
                    this_res = round(this_res, 5)  # THE BUG: every step, not just the last
                res_dict[ind] = this_res
            else:
                if "#" in arg1:
                    return "n/a"
                if arg1 not in table_dict:
                    return "n/a"
                num_row = process_row(table_dict[arg1])
                if num_row == "n/a":
                    return "n/a"
                if op == "table_max":
                    this_res = max(num_row)
                elif op == "table_min":
                    this_res = min(num_row)
                elif op == "table_sum":
                    this_res = sum(num_row)
                elif op == "table_average":
                    this_res = sum(num_row) / len(num_row)
                this_res = round(this_res, 5)
                res_dict[ind] = this_res
        return this_res
    except Exception:
        return "n/a"


def naive_scale_round_final(raw_official_final: float) -> float:
    """Naive baseline B: identical unrounded-intermediates arithmetic, but the FINAL
    round(x, 5) is done the "obvious" way a non-Python re-implementation reaches for:
    multiply by 100000.0 in float64 (a single, silently imprecise rounding step), round
    to the nearest integer, divide back. This is the SAME shape as this tree's own
    `currency.round_currency` (see progexec/roundexact.mojo's docstring)."""
    scaled = raw_official_final * 100000.0
    return round(scaled) / 100000.0


def naive_steps_annotation_substitution(steps_parsed, table, steps_annotation):
    """Naive baseline C: whenever a step references an earlier step via `#i`, substitute
    the DATASET'S OWN human-readable `steps[i]['res']` display string (re-parsed with the
    official str_to_num) instead of the raw float `res_dict[i]` carries. Real, dataset-
    shipped artifact — not invented — documented in this task's own construction."""
    table_dict = {row[0]: row[1:] for row in table}
    res_dict = {}
    this_res = "n/a"
    try:
        for ind, (op, arg1, arg2) in enumerate(steps_parsed):
            if op in ARITH_OPS:
                if "#" in arg1:
                    ref = int(arg1.replace("#", ""))
                    disp = steps_annotation[ref].get("res") if ref < len(steps_annotation) else None
                    a1 = str_to_num(disp) if disp is not None else "n/a"
                    if a1 == "n/a":
                        a1 = res_dict.get(ref, "n/a")
                else:
                    a1 = str_to_num(arg1)
                if "#" in arg2:
                    ref = int(arg2.replace("#", ""))
                    disp = steps_annotation[ref].get("res") if ref < len(steps_annotation) else None
                    a2 = str_to_num(disp) if disp is not None else "n/a"
                    if a2 == "n/a":
                        a2 = res_dict.get(ref, "n/a")
                else:
                    a2 = str_to_num(arg2)
                if a1 == "n/a" or a2 == "n/a":
                    return "n/a"
                if op == "add":
                    this_res = a1 + a2
                elif op == "subtract":
                    this_res = a1 - a2
                elif op == "multiply":
                    this_res = a1 * a2
                elif op == "divide":
                    if a2 == 0:
                        return "n/a"
                    this_res = a1 / a2
                elif op == "exp":
                    this_res = a1 ** a2
                elif op == "greater":
                    this_res = "yes" if a1 > a2 else "no"
                res_dict[ind] = this_res
            else:
                if "#" in arg1:
                    return "n/a"
                if arg1 not in table_dict:
                    return "n/a"
                num_row = process_row(table_dict[arg1])
                if num_row == "n/a":
                    return "n/a"
                if op == "table_max":
                    this_res = max(num_row)
                elif op == "table_min":
                    this_res = min(num_row)
                elif op == "table_sum":
                    this_res = sum(num_row)
                elif op == "table_average":
                    this_res = sum(num_row) / len(num_row)
                res_dict[ind] = this_res
        if this_res not in ("yes", "no", "n/a"):
            this_res = round(this_res, 5)
        return this_res
    except Exception:
        return "n/a"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    dataset_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for split in ("train.json", "dev.json", "test.json"):
        p = dataset_dir / split
        if not p.is_file():
            print(f"missing {p}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(p.read_text())
        for rec in data:
            records.append((split, rec))

    spec_lines = []
    gold_records = []
    excluded = 0

    for split, rec in records:
        qa = rec["qa"]
        program_str = qa.get("program")
        gold_res = qa.get("exe_ans")
        if not program_str or gold_res is None:
            excluded += 1
            continue
        tokens = program_tokenization(program_str)
        steps_parsed = parse_steps(tokens)
        if steps_parsed is None:
            excluded += 1
            continue
        resolved = resolve_program(steps_parsed, rec["table"])
        if resolved is None:
            excluded += 1
            continue

        # Cross-check: this file's own resolution, replayed through the reference
        # evaluator, must reproduce exe_ans. If it does not, EXCLUDE rather than emit a
        # spec block progexec could only "pass" by luck.
        official_replay = eval_official(steps_parsed, rec["table"])
        if official_replay != gold_res:
            excluded += 1
            continue

        table_values: list[float] = []
        table_offsets: list[int] = []
        table_lens: list[int] = []
        step_lines = []
        for step in resolved:
            op_code = OP_CODE[step["op"]]
            a1_kind, a1_val = step["arg1"]
            a2_kind, a2_val = step["arg2"]

            if a1_kind == "table_row":
                off = len(table_values)
                table_values.extend(a1_val)
                ln = len(a1_val)
                table_offsets.append(off)
                table_lens.append(ln)
                arg1_kind_code, arg1_hex = ARG_TABLE_ROW, f64_hex(0.0)
                arg2_kind_code, arg2_hex = ARG_LITERAL, f64_hex(0.0)
            else:
                table_offsets.append(0)
                table_lens.append(0)
                if a1_kind == "ref":
                    arg1_kind_code, arg1_hex = ARG_REF, f64_hex(float(a1_val))
                else:
                    arg1_kind_code, arg1_hex = ARG_LITERAL, f64_hex(float(a1_val))
                if a2_kind == "ref":
                    arg2_kind_code, arg2_hex = ARG_REF, f64_hex(float(a2_val))
                else:
                    arg2_kind_code, arg2_hex = ARG_LITERAL, f64_hex(float(a2_val))

            step_lines.append(
                f"{op_code} {arg1_kind_code} {arg1_hex} {arg2_kind_code} {arg2_hex} "
                f"{table_offsets[-1]} {table_lens[-1]}"
            )

        spec_lines.append(f"{rec['id']} {len(resolved)} {len(table_values)}")
        spec_lines.append(" ".join(f64_hex(v) for v in table_values))
        spec_lines.extend(step_lines)

        naive_a = naive_round_every_step(steps_parsed, rec["table"])
        raw_official = eval_official_raw(steps_parsed, rec["table"])
        naive_b = (
            naive_scale_round_final(raw_official)
            if isinstance(raw_official, float)
            else raw_official
        )
        steps_annotation = qa.get("steps") or []
        naive_c = naive_steps_annotation_substitution(steps_parsed, rec["table"], steps_annotation)

        gold_records.append(
            {
                "id": rec["id"],
                "split": split,
                "program": program_str,
                "gold": gold_res,
                "naive_round_every_step": naive_a,
                "naive_scale_round_final": naive_b,
                "naive_steps_substitution": naive_c,
            }
        )

    (out_dir / "finqa_progexec.spec").write_text(
        str(len(gold_records)) + "\n" + "\n".join(spec_lines) + "\n"
    )
    (out_dir / "finqa_gold.json").write_text(json.dumps(gold_records))

    print(f"scored programs: {len(gold_records)}")
    print(f"excluded: {excluded}")


if __name__ == "__main__":
    main()
