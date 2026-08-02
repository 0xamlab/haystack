"""reference_eval.py — the official FinQA evaluator's semantics, re-derived from
`code/evaluate/evaluate.py` in github.com/czyssrs/FinQA (Chen et al., EMNLP 2021, MIT
licensed), read line-by-line rather than assumed from any secondary summary.

This file is the SHARED vocabulary both `emit_specs.py` (builds progexec's flat input)
and `score.py` (builds the naive baselines) import, so the "what does the official
evaluator actually do" logic exists exactly once. Nothing here calls an LLM, and nothing
here is Mojo — it is the parsing/lookup half of the job (rule: PROGRAM GENERATION /
table-cell selection is a lookup, not arithmetic), matching `progexec.exec`'s own module
docstring about where the string-level work happens.
"""
from __future__ import annotations

ALL_OPS = [
    "add", "subtract", "multiply", "divide", "exp", "greater",
    "table_max", "table_min", "table_sum", "table_average",
]
OP_CODE = {name: i for i, name in enumerate(ALL_OPS)}
ARITH_OPS = frozenset(ALL_OPS[:6])
TABLE_OPS = frozenset(ALL_OPS[6:])


def str_to_num(text: str):
    """Byte-for-byte port of `evaluate.py:str_to_num`."""
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        if "%" in text:
            text = text.replace("%", "")
            try:
                return float(text) / 100.0
            except ValueError:
                return "n/a"
        elif "const" in text:
            text = text.replace("const_", "")
            if text == "m1":
                text = "-1"
            return float(text)
        else:
            return "n/a"


def process_row(row_in):
    """Byte-for-byte port of `evaluate.py:process_row`."""
    row_out = []
    for num in row_in:
        num = num.replace("$", "").strip()
        num = num.split("(")[0].strip()
        num = str_to_num(num)
        if num == "n/a":
            return "n/a"
        row_out.append(num)
    return row_out


def program_tokenization(original_program: str):
    """Byte-for-byte port of `evaluate.py:program_tokenization`."""
    original_program = original_program.split(", ")
    program = []
    for tok in original_program:
        cur_tok = ""
        for c in tok:
            if c == ")":
                if cur_tok != "":
                    program.append(cur_tok)
                    cur_tok = ""
            cur_tok += c
            if c in ["(", ")"]:
                program.append(cur_tok)
                cur_tok = ""
        if cur_tok != "":
            program.append(cur_tok)
    program.append("EOF")
    return program


def parse_steps(program_tokens):
    """Split a tokenized program (with trailing EOF) into (op, arg1, arg2) triples, or
    None if the structural check `evaluate.py:eval_program` itself runs first fails."""
    program = program_tokens[:-1]
    for ind, token in enumerate(program):
        if ind % 4 == 0 and token.strip("(") not in ALL_OPS:
            return None
        if (ind + 1) % 4 == 0 and token != ")":
            return None
    joined = "|".join(program)
    raw_steps = joined.split(")")[:-1]
    out = []
    for step in raw_steps:
        step = step.strip()
        if len(step.split("(")) > 2:
            return None
        op = step.split("(")[0].strip("|").strip()
        args = step.split("(")[1].strip("|").strip()
        arg1 = args.split("|")[0].strip()
        arg2 = args.split("|")[1].strip()
        out.append((op, arg1, arg2))
    return out


def eval_official(steps_parsed, table):
    """Byte-for-byte port of `evaluate.py:eval_program`'s semantics (unrounded
    intermediates, one `round(x, 5)` at the very end). Used ONLY as the source-of-truth
    cross-check that `emit_specs.py`'s resolved literals reproduce the dataset's own
    `exe_ans` — the actual claim is scored against `exe_ans` directly, never against this
    function, so a bug here cannot manufacture agreement."""
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


def eval_official_raw(steps_parsed, table):
    """Same as `eval_official`, but returns the FINAL step's value BEFORE the official
    evaluator's one `round(x, 5)` — the raw double `naive_scale_round_final` in
    `emit_specs.py` is applied to, so naive baseline B isolates exactly the final
    -rounding step and nothing upstream of it."""
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
        return this_res
    except Exception:
        return "n/a"


def resolve_program(steps_parsed, table):
    """Resolve a parsed program's operands into progexec's flat, tagged-operand shape:
    a list of dicts, one per step, each with op (str), and per-arg (kind, value) where
    kind is 'literal' (value: float), 'ref' (value: int index), or — for table ops —
    'table_row' (value: list[float], the already-extracted numeric row).

    Returns None if resolution hits anything the official evaluator would also refuse
    (unknown table key, non-numeric row, etc.) — the caller then excludes the program
    from the scored population rather than guessing, matching FinQA's own eval_program's
    refusal shape.
    """
    table_dict = {row[0]: row[1:] for row in table}
    out = []
    for op, arg1, arg2 in steps_parsed:
        if op not in ALL_OPS:
            return None
        if op in TABLE_OPS:
            if "#" in arg1:
                return None  # dead branch in the official evaluator (see exec.mojo docstring)
            if arg1 not in table_dict:
                return None
            num_row = process_row(table_dict[arg1])
            if num_row == "n/a" or len(num_row) == 0:
                return None
            out.append({"op": op, "arg1": ("table_row", num_row), "arg2": ("literal", 0.0)})
            continue

        def resolve_one(tok):
            if "#" in tok:
                return ("ref", int(tok.replace("#", "")))
            v = str_to_num(tok)
            if v == "n/a":
                return None
            return ("literal", float(v))

        r1 = resolve_one(arg1)
        r2 = resolve_one(arg2)
        if r1 is None or r2 is None:
            return None
        out.append({"op": op, "arg1": r1, "arg2": r2})
    return out
