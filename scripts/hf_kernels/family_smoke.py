#!/usr/bin/env python3
"""Publish gate: every function of a generated kernel package survives one contract-valid call.

For each module, a fresh subprocess imports the generated package from `build/<variant>` and calls
every function once with synthesized arguments that satisfy the published contract (types, struct
fields, length rules). The point is not the answer: a function may legitimately report an engine
status or a KernelError for a shape it does not accept. The point is that the host process is
still alive afterwards. Any module whose subprocess dies (signal, abort, non-zero exit) fails the
gate and is bisected to the function.

  scripts/hf_kernels/family_smoke.py --variant hub/algenta-llm/build/torch214-cpu-aarch64-darwin [--out report.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

LIST_LEN = 8
INT_VALUE = 2
FLOAT_VALUE = 0.5


def synth(type_name: str, structs: dict, depth: int = 0):
    if type_name == "None":
        return None
    if type_name == "Bool":
        return True
    if type_name == "String":
        return "algenta"
    if type_name in ("Int", "UInt8", "UInt16", "UInt32", "UInt64"):
        return INT_VALUE
    if type_name in ("Float32", "Float64"):
        return FLOAT_VALUE
    if type_name.startswith("List["):
        inner = type_name[5:-1]
        n = LIST_LEN if depth == 0 else 4
        return [synth(inner, structs, depth + 1) for _ in range(n)]
    struct = structs.get(type_name)
    if struct is None:
        raise KeyError(f"cannot synthesize an argument of type {type_name!r}: not a primitive, list or declared struct")
    return {f["name"]: synth(f["type"], structs, depth + 1) for f in struct["fields"]}


def arguments(function: dict, structs: dict) -> list:
    args = [synth(p["type"], structs) for p in function["params"]]
    # Length rules: make every bounded list long enough for the product of its factors.
    by_name = {p["name"]: i for i, p in enumerate(function["params"])}
    for rel in function.get("count_relations") or []:
        need = 1
        for f in rel["factors"]:
            v = args[by_name[f]] if f in by_name else INT_VALUE
            need *= v if isinstance(v, int) else INT_VALUE
        need += rel.get("plus", 0) + 1
        for name in rel["bounds"]:
            if name not in by_name:
                continue
            i = by_name[name]
            p = function["params"][i]
            inner = p["type"][5:-1] if p["type"].startswith("List[") else None
            if inner is None:
                continue
            if rel.get("scope") == "length":
                if isinstance(args[i], list) and len(args[i]) < need:
                    args[i] = [synth(inner, structs, 1) for _ in range(need)]
            elif isinstance(args[i], list):
                args[i] = [[synth(inner[5:-1], structs, 2) for _ in range(need)] if inner.startswith("List[") else synth(inner, structs, 1) for _ in args[i]]
    return args


def _run_module(variant: str, module: str, only: list[str] | None, queue) -> None:
    sys.path.insert(0, variant)
    pkg_name = next(p.name for p in Path(variant).iterdir() if p.is_dir() and p.name.startswith("algenta_"))
    pkg = __import__(pkg_name)
    spec = pkg.CONTRACT["modules"][module]
    results = {}
    for fname, f in sorted(spec["functions"].items()):
        if only and fname not in only:
            continue
        queue.put(("start", fname))
        t0 = time.time()
        try:
            out = pkg.execute(module, fname, arguments(f, spec["structs"]))
            results[fname] = {"outcome": "result", "type": type(out).__name__, "ms": round((time.time() - t0) * 1000, 2)}
        except pkg.KernelError as exc:
            results[fname] = {"outcome": "kernel_error", "code": exc.code, "ms": round((time.time() - t0) * 1000, 2)}
        except Exception as exc:  # noqa: BLE001 - the gate records the class; the tests forbid it
            results[fname] = {"outcome": "python_exception", "type": type(exc).__name__, "message": str(exc)[:200]}
        queue.put(("done", fname, results[fname]))
    queue.put(("end", results))


def run_module(variant: str, module: str, only: list[str] | None = None, timeout: float = 600.0) -> dict:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_run_module, args=(variant, module, only, queue))
    proc.start()
    results: dict = {}
    current = None
    deadline = time.time() + timeout
    while True:
        try:
            msg = queue.get(timeout=1.0)
        except Exception:  # noqa: BLE001 - queue.Empty or a dead child
            msg = None
        if msg is not None:
            if msg[0] == "start":
                current = msg[1]
            elif msg[0] == "done":
                results[msg[1]] = msg[2]
                current = None
            elif msg[0] == "end":
                proc.join(30)
                return {"status": "ok", "functions": results}
        if not proc.is_alive() and msg is None:
            proc.join(1)
            return {"status": "crashed", "exitcode": proc.exitcode, "crashed_in": current, "functions": results}
        if time.time() > deadline:
            proc.kill()
            proc.join(5)
            return {"status": "timeout", "hung_in": current, "functions": results}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", required=True, help="build/<variant> directory of a generated repo")
    ap.add_argument("--modules", nargs="*", default=None)
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=float, default=600.0)
    a = ap.parse_args()
    variant = str(Path(a.variant).resolve())
    sys.path.insert(0, variant)
    pkg_name = next(p.name for p in Path(variant).iterdir() if p.is_dir() and p.name.startswith("algenta_"))
    spec = importlib.util.spec_from_file_location("_hf_smoke_contract", Path(variant) / pkg_name / "_contract.py")
    contract_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract_module)
    namespace = {"CONTRACT": contract_module.CONTRACT}
    modules = a.modules or sorted(namespace["CONTRACT"]["modules"])
    report = {"variant": variant, "modules": {}, "crashes": [], "hangs": [], "python_exceptions": []}
    for m in modules:
        r = run_module(variant, m, timeout=a.timeout)
        if r["status"] == "crashed":
            # bisect: run the rest one function at a time to name every crasher
            spec = namespace["CONTRACT"]["modules"][m]
            for fname in sorted(spec["functions"]):
                if fname in r["functions"]:
                    continue
                single = run_module(variant, m, [fname], timeout=a.timeout)
                if single["status"] == "crashed":
                    report["crashes"].append({"module": m, "function": fname, "exitcode": single["exitcode"]})
                    r["functions"][fname] = {"outcome": "crash", "exitcode": single["exitcode"]}
                elif single["status"] == "timeout":
                    report["hangs"].append({"module": m, "function": fname})
                    r["functions"][fname] = {"outcome": "hang"}
                else:
                    r["functions"].update(single["functions"])
        elif r["status"] == "timeout":
            report["hangs"].append({"module": m, "function": r["hung_in"]})
        for fname, res in r["functions"].items():
            if res.get("outcome") == "python_exception":
                report["python_exceptions"].append({"module": m, "function": fname, **res})
        report["modules"][m] = r
        counts = {}
        for res in r["functions"].values():
            counts[res["outcome"]] = counts.get(res["outcome"], 0) + 1
        print(f"{m:40s} {r['status']:8s} {counts}")
    total = sum(len(r["functions"]) for r in report["modules"].values())
    print(f"\n{total} functions; crashes={len(report['crashes'])} hangs={len(report['hangs'])} python_exceptions={len(report['python_exceptions'])}")
    for c in report["crashes"]:
        print("CRASH", c)
    for h in report["hangs"]:
        print("HANG", h)
    for e in report["python_exceptions"]:
        print("EXC", e)
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1) + "\n")
    return 1 if (report["crashes"] or report["hangs"] or report["python_exceptions"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
