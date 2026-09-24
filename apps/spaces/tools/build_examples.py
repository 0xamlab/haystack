"""Synthesise and VERIFY the prefilled arguments for every function of every family.

    python apps/spaces/tools/build_examples.py [--families stats text ...]
        [--out apps/spaces/algenta/examples] [--call-timeout 10]

For each function `algenta_spaces.examples.synthesize(form)` proposes the arguments the Playground
opens with; this tool runs them through the Playground's own validation (types, count relations,
field rules) and then EXECUTES them through the family's compiled kernel, in a child process
watched by the parent: a call that does not answer within `--call-timeout` seconds is a hang
(round 9 found one: a synthesised regression tree whose child indices formed a cycle), the child
is killed, the function is recorded as `timeout` and the child resumes from the next function.
A proposal the kernel refuses or that hangs gets the crash gate's own argument shapes
(`examples.plain_args`, the values `family_smoke.py` proved on every function) as a second try.
Whichever the kernel answers is written with `verified: true`; otherwise the rules proposal
stays with `verified: false` and the kernel's status, so no box is ever empty and the file says
what the kernel thought.

Output: one JSON per family, `<out>/<family>.json`, `functions` keyed `module.function`.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
SHARED = HERE.parents[1] / "_shared"
sys.path.insert(0, str(SHARED))

from algenta_spaces import examples, hubkernel, playground  # noqa: E402

DEFAULT_OUT = HERE.parents[1] / "algenta" / "examples"
DEFAULT_CALL_TIMEOUT = 10.0
OUTCOME_RESULT = "result"
OUTCOME_TIMEOUT = "timeout"


def _validated(form: playground.Form, args: dict[str, Any]) -> list[Any]:
    values = playground.parse_inputs(form, args)
    named = playground.named_args(form.fields, values)
    playground.enforce_count_relations(form, named)
    playground.enforce_field_rules(form, named)
    return values


def _attempt(loaded: Any, form: playground.Form, args: dict[str, Any]) -> tuple[str, float]:
    t0 = time.perf_counter()
    try:
        values = _validated(form, args)
    except playground.PlaygroundError as exc:
        return f"invalid:{type(exc).__name__}:{str(exc)[:80]}", 0.0
    try:
        hubkernel.execute(loaded, form.module, form.function, values)
    except hubkernel.HubKernelError as exc:
        return str(getattr(exc, "code", "kernel_error")), (time.perf_counter() - t0) * 1e3
    return OUTCOME_RESULT, (time.perf_counter() - t0) * 1e3


def function_list(loaded: Any) -> list[tuple[str, str]]:
    described = hubkernel.describe(loaded)
    excluded = hubkernel.excluded_keys(loaded)
    out: list[tuple[str, str]] = []
    for module_name, module in described["modules"].items():
        for function in module.get("functions", {}):
            if not hubkernel.is_excluded(module_name, function, excluded):
                out.append((module_name, function))
    return sorted(out)


def _child(family: str, start: int, skip_plain_for: str | None, queue: Any) -> None:
    """Verify the family's functions from index `start`; one message per step."""
    sys.path.insert(0, str(SHARED))
    loaded = hubkernel.load(family)
    functions = function_list(loaded)
    queue.put(("functions", functions))
    for index in range(start, len(functions)):
        module_name, function = functions[index]
        qual = f"{module_name}.{function}"
        form = playground.form_spec(loaded, module_name, function)
        args = examples.synthesize(form)
        queue.put(("start", index, qual, "rules", args))
        if skip_plain_for == qual:
            outcome, ms = OUTCOME_TIMEOUT, 0.0  # the rules proposal hung last time
        else:
            outcome, ms = _attempt(loaded, form, args)
        source = "rules"
        if outcome != OUTCOME_RESULT:
            plain = examples.plain_args(form)
            if plain != args:
                queue.put(("start", index, qual, "plain", plain))
                outcome2, ms2 = _attempt(loaded, form, plain)
                if outcome2 == OUTCOME_RESULT:
                    args, outcome, ms, source = plain, outcome2, ms2, "plain"
        queue.put(("done", index, qual, args, outcome, source, ms))
    queue.put(("end",))


def build_family(family: str, out_dir: Path, call_timeout: float) -> dict[str, int]:
    ctx = mp.get_context("spawn")
    entries: dict[str, Any] = {}
    functions: list[tuple[str, str]] = []
    start, skip_plain_for = 0, None
    pending: tuple[int, str, str, dict[str, Any]] | None = None
    while True:
        queue = ctx.Queue()
        child = ctx.Process(target=_child, args=(family, start, skip_plain_for, queue))
        child.start()
        skip_plain_for = None
        finished = False
        while True:
            try:
                msg = queue.get(timeout=call_timeout if pending else 600.0)
            except Exception:  # noqa: BLE001 - the queue's Empty: the call did not answer
                break
            kind = msg[0]
            if kind == "functions":
                functions = msg[1]
            elif kind == "start":
                pending = (msg[1], msg[2], msg[3], msg[4])
            elif kind == "done":
                _, index, qual, args, outcome, source, ms = msg
                entries[qual] = {
                    "args": args,
                    "verified": outcome == OUTCOME_RESULT,
                    "outcome": outcome,
                    "source": source,
                    "ms": round(ms, 3),
                }
                pending = None
            elif kind == "end":
                finished = True
                break
        if finished:
            child.join(timeout=30)
            break
        # a hang: kill the child, record the function, resume after it (or retry it plainly)
        child.kill()
        child.join(timeout=30)
        if pending is None:
            break  # the child died before naming a function
        index, qual, source, args = pending
        pending = None
        if source == "rules":
            # give the crash gate's shapes one chance for this function in a fresh child
            start, skip_plain_for = index, qual
            entries[qual] = {
                "args": args,
                "verified": False,
                "outcome": OUTCOME_TIMEOUT,
                "source": "rules",
                "ms": call_timeout * 1e3,
            }
            if os.environ.get("BUILD_EXAMPLES_TRACE"):
                print(f"  HANG {qual} (rules) -> retry plain", file=sys.stderr, flush=True)  # noqa: T201
        else:
            entries[qual] = {
                "args": args,
                "verified": False,
                "outcome": OUTCOME_TIMEOUT,
                "source": "plain",
                "ms": call_timeout * 1e3,
            }
            start = index + 1
            if os.environ.get("BUILD_EXAMPLES_TRACE"):
                print(f"  HANG {qual} (plain) -> skip", file=sys.stderr, flush=True)  # noqa: T201
        if start >= len(functions):
            break
    counts = {
        "functions": len(functions),
        "verified": sum(1 for e in entries.values() if e["verified"]),
        "plain": sum(1 for e in entries.values() if e["verified"] and e["source"] == "plain"),
        "timeouts": sum(1 for e in entries.values() if e["outcome"] == OUTCOME_TIMEOUT),
    }
    counts["unverified"] = counts["functions"] - counts["verified"]
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "family": family,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "harness": "apps/spaces/tools/build_examples.py",
        "rule": "arguments from algenta_spaces.examples rules, each executed through the"
        " compiled kernel; verified = the kernel returned a result; timeout = no answer in"
        f" {call_timeout:g} s",
        "counts": counts,
        "functions": dict(sorted(entries.items())),
    }
    (out_dir / f"{family}{examples.EXAMPLES_FILE_SUFFIX}").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--families", nargs="*", default=list(playground.FAMILIES))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--call-timeout", type=float, default=DEFAULT_CALL_TIMEOUT)
    a = ap.parse_args(argv)
    total = {"functions": 0, "verified": 0, "plain": 0, "timeouts": 0, "unverified": 0}
    for family in a.families:
        t0 = time.perf_counter()
        counts = build_family(family, a.out, a.call_timeout)
        for k in total:
            total[k] += counts[k]
        print(  # noqa: T201 - a build tool's report
            f"{family:14s} {counts['verified']:4d}/{counts['functions']:4d} verified"
            f" ({counts['plain']} plain, {counts['timeouts']} timeouts)"
            f" {counts['unverified']:3d} unverified  {time.perf_counter() - t0:6.1f} s",
            flush=True,
        )
    print(  # noqa: T201
        f"{'total':14s} {total['verified']:4d}/{total['functions']:4d} verified"
        f" ({total['plain']} plain, {total['timeouts']} timeouts)"
        f" {total['unverified']:3d} unverified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
