#!/usr/bin/env python3
"""ttft_probe.py — TTFT-only microbench for the JSONL serve drivers (cell-A semantics).

Sends ONE request at a time (concurrency exactly 1, serial) with `max_tokens=1` through the
same JSON-lines protocol `enterprise_bench.py`'s JsonlDriverAdapter speaks, and reports the
driver-reported TTFT distribution — the prefill cost ALONE, no decode contamination. The
prompt is the harness's own synthesized chat prompt (enterprise_bench.synthesize_prompt,
char/4 tokenizer contract), so its token count is exactly `prompt_tokens_approx`.

Usage (the driver is selected by allowlisted NAME and found in $BENCH_BIN_DIR, then PATH,
through benchmarks/bench_tools.py -- copied beside this file like enterprise_bench.py):
    BENCH_BIN_DIR=$HOME/leverpush python3 ttft_probe.py --driver qwen3_serve_batched_cuda \
        --driver-args /tmp/qwen3smoke --tokens 1024 --repeats 9 --mix chat

The driver subprocess is started once; one request per repeat (the driver keeps its KV
resident across repeats exactly like the harness's closed-loop cells). Exit code 0 when all
repeats answered; non-zero on timeout/error. The probe is measurement-only: it never
imports anything from the engine, so it runs on any host with python3.
"""

import argparse
import json
import math
import os
import shlex
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [".", HERE, os.path.dirname(os.path.dirname(HERE))]
from bench_tools import SERVE_DRIVERS, ToolError, popen_tool, tool_path  # noqa: E402
from enterprise_bench import MIX_SPECS, synthesize_prompt  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver", required=True, choices=SERVE_DRIVERS,
                    help="which JSON-lines serve driver to launch (found by name in "
                         "$BENCH_BIN_DIR, then PATH)")
    ap.add_argument("--driver-args", default="",
                    help="arguments after the driver binary, e.g. '/tmp/qwen3smoke' "
                         "(shlex-split; data, never a shell)")
    ap.add_argument("--tokens", type=int, default=0,
                    help="nominal prompt tokens (0 = the chat mix default)")
    ap.add_argument("--mix", default="chat")
    ap.add_argument("--repeats", type=int, default=9)
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()
    try:
        driver = tool_path(args.driver)
    except ToolError as exc:
        raise SystemExit(f"{ap.prog}: error: {exc}") from None

    n_in = args.tokens or MIX_SPECS[args.mix]["in_tokens"]
    prompt = synthesize_prompt(0, n_in, 20260820)
    approx = max(1, math.ceil(len(prompt) / 4))

    proc = popen_tool(
        driver, *shlex.split(args.driver_args),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    ttfts = []
    try:
        for r in range(args.repeats):
            req = {
                "id": r,
                "prompt": prompt,
                "prompt_tokens_approx": approx,
                "max_tokens": 1,
                "stream": True,
            }
            t0 = time.perf_counter()
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            wall_ms = 0.0
            resp = None
            while True:
                line = proc.stdout.readline()
                if not line:
                    print("ERROR: driver closed stdout at repeat", r)
                    return 2
                wall_ms = (time.perf_counter() - t0) * 1000.0
                try:
                    resp = json.loads(line)
                except json.JSONDecodeError:
                    continue  # the protocol allows non-JSON diagnostic lines
                if resp.get("id") == r:
                    break
            if "error" in resp:
                print("ERROR: driver error:", resp["error"])
                return 2
            ttfts.append(float(resp["ttft_ms"]))
            print(f"  repeat {r}: ttft_ms={resp['ttft_ms']} wall_ms={wall_ms:.1f}",
                  flush=True)
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    ttfts_sorted = sorted(ttfts)
    p50 = statistics.median(ttfts)
    print(f"RESULT tokens={approx} repeats={args.repeats} "
          f"ttft_p50_ms={p50:.1f} min_ms={ttfts_sorted[0]:.1f} "
          f"max_ms={ttfts_sorted[-1]:.1f} all_ms={[round(x, 1) for x in ttfts]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
