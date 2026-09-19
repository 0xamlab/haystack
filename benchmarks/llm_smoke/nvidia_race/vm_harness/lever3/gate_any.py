#!/usr/bin/env python3
"""gate_any.py -- oracle gate for any arm build. argv: <runs_dir> <out_json> <arm_label>

Same semantics as gemma_rerace/rr_gate2.py: every emitted token must equal the cache-free
fp32 oracle prefix, the 64-token run must be bit-identical across a repeat (determinism),
and an early stop is only admissible when the oracle has EOS at the same index.
"""
import json
import os
import sys
from pathlib import Path

RUNS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
ARM = sys.argv[3] if len(sys.argv) > 3 else "unknown"
ORC = Path("/home/angel/adj/oracle3")
EOS = (106, 1)
PLAN = {
    "pp256":   [(16, ["gate_pp256_maxnew16"]),
                (64, ["gate_pp256_maxnew64", "gate_pp256_maxnew64_rep2"])],
    "pp1024":  [(16, ["gate_pp1024_maxnew16"]),
                (64, ["gate_pp1024_maxnew64", "gate_pp1024_maxnew64_rep2"])],
    "val550":  [(16, ["gate_val550_maxnew16"]),
                (64, ["gate_val550_maxnew64", "gate_val550_maxnew64_rep2"])],
    "rag4096": [(64, ["gate_rag4096_maxnew64"])],
}

# ── SCOPE, AND WHY A REDUCED GATE MUST NOT READ AS A FAILED ONE ───────────────────────────────
# `PLAN` above enumerates all four prompts, and `all_pass` used to be False whenever any of them
# had not run. That is correct when the caller asked for all four and WRONG when the caller
# deliberately gated a subset: round 18 gated pp1024 alone (a 90-min cap cannot fund a full
# four-prompt gate at ~38 min AND an n=5 rag4096 bracket at ~41 min), the cells it did run passed
# 16/16 and 64/64 with a 2/2 bit-identical repeat, and this script still printed
# `GATE ALL_PASS = False` — which the chain read as a numerics failure and refused to time.
# A gate that reports FAIL for prompts nobody requested is not conservative, it is WRONG in the
# direction that hides a real result, and it is the mirror image of the failure mode this script
# exists to prevent.
#
# So: scope is an explicit input (argv[4], comma-separated, else $GATE_PROMPTS, else all four).
# `all_pass` is computed over the IN-SCOPE prompts only. Out-of-scope prompts are recorded as
# `OUT-OF-SCOPE` in the table and as `out_of_scope_prompts` in the JSON — never as NOT-RUN, never
# silently dropped, so a reader can always see exactly what was and was not certified. An
# in-scope prompt that did not run is still a hard failure. Backwards compatible: with no argv[4]
# and no $GATE_PROMPTS the scope is all four and the behaviour is byte-for-byte the old one.
_scope_arg = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("GATE_PROMPTS", "")
IN_SCOPE = {s.strip() for s in _scope_arg.replace(":", ",").split(",") if s.strip()} or set(PLAN)
OUT_OF_SCOPE = [p for p in PLAN if p not in IN_SCOPE]
UNKNOWN_SCOPE = sorted(IN_SCOPE - set(PLAN))
if UNKNOWN_SCOPE:
    print(f"FATAL: scope names no known prompt plan: {UNKNOWN_SCOPE} (known: {sorted(PLAN)})")
    sys.exit(2)


def last(path):
    if not path.exists():
        return {}
    for line in reversed(path.read_text(errors="replace").splitlines()):
        line = line.strip()
        if line.startswith("{") and '"generated"' in line:
            try:
                return json.loads(line)
            except Exception:
                pass
    return {}


out = {"gate": f"oracle gate on {ARM}", "arm": ARM,
       "oracle": "cache-free fp32 transformers (~/adj/oracle3)",
       "scope": sorted(IN_SCOPE), "out_of_scope_prompts": OUT_OF_SCOPE,
       "cells": {}, "all_pass": None}
rows, allpass = [], True

for p, specs in PLAN.items():
    if p not in IN_SCOPE:
        # RECORDED, NOT COUNTED. An out-of-scope prompt is a scope statement about what this gate
        # certified, never a failure of the arm — and never silently omitted either.
        out["cells"][p] = {"out_of_scope": True,
                           "note": "not requested by this gate's scope; NOT certified either way"}
        rows.append((p, "-", "OUT-OF-SCOPE", "not requested; not certified either way"))
        continue
    op = ORC / f"{p}.json"
    if not op.exists():
        rows.append((p, "-", "ORACLE-MISSING", str(op))); allpass = False; continue
    og = json.loads(op.read_text())["generated"]
    out["cells"][p] = {"oracle_n": len(og),
                       "oracle_first_eos_index": next((i for i, t in enumerate(og) if t in EOS), None)}
    for k, labels in specs:
        runs = {lb: last(RUNS / f"{lb}.out") for lb in labels}
        runs = {lb: d for lb, d in runs.items() if d.get("generated") is not None}
        if not runs:
            out["cells"][p][f"maxnew{k}"] = {"ran": False, "labels": labels}
            rows.append((p, k, "NOT-RUN", ",".join(labels))); allpass = False; continue
        d = runs.get(labels[0]) or next(iter(runs.values()))
        g = d["generated"]
        n = min(len(g), len(og))
        match = sum(1 for i in range(n) if g[i] == og[i])
        prefix_ok = match == n
        stopped_early = len(g) < k
        eos_stop = stopped_early and bool(g) and g[-1] in EOS
        oracle_agrees_eos = eos_stop and len(og) > len(g) and og[len(g) - 1] in EOS
        if not stopped_early:
            verdict = f"{match}/{k}" + (" PASS" if match == k else " FAIL"); passed = match == k
        else:
            verdict = (f"{match}/{len(g)} + EOS-stop PASS" if prefix_ok and oracle_agrees_eos
                       else f"{match}/{len(g)} FAIL")
            passed = prefix_ok and oracle_agrees_eos
        det_ok = True
        if len(runs) > 1:
            base = runs[labels[0]]["generated"] if labels[0] in runs else None
            for lb, dd in runs.items():
                if base is not None and dd["generated"] != base:
                    det_ok = False
        det = "n/a (single run)" if len(runs) < 2 else (
            f"{len(runs)}/{len(runs)} bit-identical" if det_ok else "DIVERGENT")
        passed = passed and det_ok
        allpass = allpass and passed
        fd = next((i for i in range(n) if g[i] != og[i]), None)
        out["cells"][p][f"maxnew{k}"] = {
            "ran": True, "requested": k, "labels": list(runs), "n_generated": len(g),
            "n_matching_oracle_prefix": match, "prefix_exact": prefix_ok,
            "first_divergent_index": fd,
            "arm_token_at_first_diff": g[fd] if fd is not None else None,
            "oracle_token_at_first_diff": og[fd] if fd is not None else None,
            "stopped_early": stopped_early, "last_token": g[-1] if g else None,
            "eos_stop": eos_stop, "oracle_also_eos_there": oracle_agrees_eos,
            "determinism": det, "determinism_pass": det_ok if len(runs) > 1 else None,
            "verdict": verdict, "pass": passed, "tokens": g,
            "ttft_ms": d.get("ttft_ms"), "decode_tok_s": d.get("decode_tok_s")}
        rows.append((p, k, verdict, f"n_gen={len(g)} det={det}"
                     + (f" first_diff@{fd}" if fd is not None else "")))

out["all_pass"] = allpass
OUT.write_text(json.dumps(out, indent=2))
print(f"\n=== ORACLE GATE -- {ARM} ===")
print("%-9s %8s %-30s %s" % ("prompt", "max_new", "verdict", "note"))
for p, k, v, note in rows:
    print("%-9s %8s %-30s %s" % (p, k, v, note))
print("\nGATE ALL_PASS =", allpass)
# NEVER PRINT ALL_PASS WITHOUT ITS SCOPE. A bare `ALL_PASS = True` over one prompt reads the same
# as one over four, and the whole point of a gate is that a reader knows what was certified.
print(f"GATE SCOPE = {sorted(IN_SCOPE)}"
      + (f"  (OUT OF SCOPE, NOT CERTIFIED: {OUT_OF_SCOPE})" if OUT_OF_SCOPE else "  (all four)"))
print(f"WROTE {OUT}")
