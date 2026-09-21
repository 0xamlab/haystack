#!/usr/bin/env python3
"""External-user smoke test against the PUBLISHED kernels on the Hub (what a fresh install sees).

Run in a fresh virtualenv with `pip install kernels torch` (or without torch to record that outcome):
  python scripts/hf_kernels/hub_smoke.py --repo thyn-ai/algenta-stats --backend cpu \
      --reference scratch/worker_reference.json [--checkpoint <converted dir> --prompt-ids 785 3974 ...]

Uses a clean cache directory unless --keep-cache is given, so every run downloads what a user downloads.
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
import tempfile
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--backend", default=None)
    ap.add_argument("--reference", help="worker_reference.json to compare library_execute results against")
    ap.add_argument("--checkpoint"); ap.add_argument("--prompt-ids", nargs="*", type=int); ap.add_argument("--max-new-tokens", type=int, default=8)
    ap.add_argument("--expect-tokens", nargs="*", type=int)
    ap.add_argument("--keep-cache", action="store_true")
    ap.add_argument("--call", action="append", default=[], help="module.function=<json args>; executed and printed (e.g. normk.rmsnorm.rmsnorm_fwd_flat=[[1,2,3,4],[1,1],2,2,1e-6])")
    a = ap.parse_args()
    if not a.keep_cache:
        cache = tempfile.TemporaryDirectory(prefix="hf-smoke-")
        atexit.register(cache.cleanup)
        os.environ["HF_HOME"] = cache.name
    from kernels import get_kernel  # noqa: PLC0415 - after HF_HOME is set

    t0 = time.time()
    kernel = get_kernel(a.repo, version=a.version, backend=a.backend, trust_remote_code=[a.repo])
    variant = kernel.__file__.split("/build/")[1].split("/")[0]
    print(f"{a.repo}: loaded {variant} in {time.time() - t0:.1f}s from a clean cache")
    failures = 0
    if a.reference:
        ref = json.load(open(a.reference))
        for row in ref["results"]:
            r = row["request"]; exp = json.loads(row["response"])
            try:
                got = kernel.execute(r["module"], r["function"], r["args"]); raw = exp.get("result")
                same = (got == raw) or (isinstance(raw, dict) and isinstance(got, dict) and list(got.values()) == raw.get("v"))
            except Exception as exc:  # noqa: BLE001
                same = getattr(exc, "code", None) == exp.get("error_code"); got = f"error {getattr(exc, 'code', type(exc).__name__)}"
            failures += not same
            print(("PASS" if same else "FAIL"), f"{r['module']}.{r['function']} -> {str(got)[:70]}")
        print(f"reference parity: {len(ref['results']) - failures}/{len(ref['results'])}")
    for spec in a.call:
        target, _, raw = spec.partition("=")
        module, function = target.rsplit(".", 1)
        try:
            got = kernel.execute(module, function, json.loads(raw))
            print("PASS", f"{target} -> {str(got)[:90]}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print("FAIL", f"{target} -> {type(exc).__name__}: {exc}")
    if a.checkpoint and a.prompt_ids:
        t0 = time.time()
        with kernel.DecodeSession(a.checkpoint, a.prompt_ids, max_new_tokens=a.max_new_tokens) as s:
            toks = list(s)
        ok = (toks == a.expect_tokens) if a.expect_tokens else bool(toks)
        failures += not ok
        print(("PASS" if ok else "FAIL"), "DecodeSession tokens:", toks, f"({time.time() - t0:.1f}s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
