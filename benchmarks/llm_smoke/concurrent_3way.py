"""concurrent_3way.py -- the campaign's concurrent-throughput axis, measured the way production
actually serves (beat-llama.cpp campaign, 2026-08-12): B prompts in flight at once, aggregate
SYSTEM decode tok/s, across the three engines.

Why this harness exists: the dual-stream test (REALRACE_RESULTS.md "DUAL-STREAM CONCURRENCY TEST")
proved concurrent scaling on this GPU does NOT come from concurrent dispatch streams (both
engines serialize across command buffers) -- it comes from BATCHED weight-sweeps (one sweep per
token across B sequences). Algenta ships exactly that as `algenta.inference.decode_batched`
(Slipstream Phase 3, B <= 32); llama.cpp ships it as llama-server's multi-slot continuous
batching; MLX-LM ships no server and serves one sequence at a time. This harness measures each
engine's OWN production concurrent story at identical prompts:

  * algenta-batched : ONE decode_batched() call carrying all B prompts (system tok/s reported
                      by the engine: B sequences x steps / shared decode wall).
  * algenta-serial  : B sequential single-stream decode() calls (the pre-Slipstream behavior;
                      internal control showing what batching buys).
  * llama.cpp       : B concurrent /completion HTTP requests against ONE resident llama-server
                      started with --parallel B (its slot-based continuous batching does the
                      grouping server-side); system tok/s = total generated tokens / client wall.
  * mlx-lm          : B sequential generations in the resident worker (its honest concurrent
                      story -- no batching, no server); system tok/s = total tokens / summed
                      per-cell walls (computed from the worker's own per-cell gen_tps).

Method: untimed warmup at the exact timed shape per engine per cell (warm-vs-warm protocol from
the 2026-08-12 session-warmth diagnosis), rotating engine order across passes, medians pooled
per (engine, B). Greedy everywhere. Prompts: B DISTINCT whole-unit prompts (shared bytes across
engines via the Qwen3 tokenizer, so token counts match), each ~in_tokens long.

Usage (repo root):
  # The SDK resolves the local dev GPU worker through the documented dev knobs (release builds
  # stay fail-closed); point ALGENTA_NATIVE_WORKER at the campaign worker binary:
  ALGENTA_NATIVE_WORKER=$PWD/mojo_build/gpu-worker/algenta-gpu-worker \
  ALGENTA_RUNTIME_FALLBACK_MODE=allow \
  python3 benchmarks/llm_smoke/concurrent_3way.py \
      --checkpoint /private/tmp/qwen3-0.6b-base \
      --gguf /tmp/qwen3-0.6b-base-f16.gguf \
      --batch-sizes 8,16,32 --in-tokens 256 --out-tokens 128 \
      --passes 2 --out /tmp/concurrent_3way.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode, decode_batched  # noqa: E402
from algenta.tokenizer import load_tokenizer  # noqa: E402

PROMPT_UNIT = "The capital of France is Paris. The largest planet in the solar system is Jupiter. "
PROMPT_TAIL = "The capital of France"
LLAMA_PORT = 8199
LLAMA_NGL = 99
MLX_PY = "/tmp/mlm_venv/bin/python"
MLX_WORKER = str(ROOT / "benchmarks" / "llm_smoke" / "load_test_mlx_worker.py")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def build_prompt_set(b: int, target_tokens: int, tokenizer) -> tuple[list[str], list[int]]:
    """B DISTINCT whole-unit prompts of >= target_tokens each; returns (texts, token_counts).
    Distinctness: per-sequence unit-count offset and an index marker in the tail, so the batched
    KV slots and llama-server slots genuinely hold different sequences."""
    texts, counts = [], []
    for i in range(b):
        k = 1 + (i % 3)
        text = PROMPT_UNIT * k + f"Sequence {i}. " + PROMPT_UNIT * 2 + PROMPT_TAIL
        ids = tokenizer.encode(text)
        # extend to target length with whole units
        while len(ids) < target_tokens:
            text += PROMPT_UNIT
            ids = tokenizer.encode(text)
        texts.append(text)
        counts.append(len(ids))
    return texts, counts


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def start_llama_server(gguf: str, port: int, ctx: int, parallel: int):
    proc = subprocess.Popen(
        ["llama-server", "-m", gguf, "--port", str(port), "-ngl", str(LLAMA_NGL),
         "-c", str(ctx), "--parallel", str(parallel), "--no-webui"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return proc
        except Exception:
            time.sleep(0.25)
    proc.terminate()
    raise RuntimeError("llama-server did not become healthy within 90 s")


def stop_llama_server(proc) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def llama_one(port: int, prompt_text: str, n_predict: int) -> dict:
    body = json.dumps({
        "prompt": prompt_text, "n_predict": n_predict,
        "temperature": 0, "top_k": 1, "cache_prompt": False,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=1200) as resp:
        return json.loads(resp.read())


def run_algenta_batched(b: int, prompts: list[str], tokenizer, runtime, checkpoint: str,
                        out_tokens: int) -> float:
    ids_list = [tokenizer.encode(p) for p in prompts]
    # untimed warmup at the exact timed shape (session warmth + DVFS ramp), then one timed call
    decode_batched(
        runtime, checkpoint_dir=checkpoint,
        prompt_token_ids_list=ids_list, max_new_tokens=out_tokens,
    )
    t0 = time.time()
    res = decode_batched(
        runtime, checkpoint_dir=checkpoint,
        prompt_token_ids_list=ids_list, max_new_tokens=out_tokens,
    )
    wall = time.time() - t0
    total = sum(len(g) for g in res.generated_token_ids)
    engine_sys = res.decode_tokens_per_sec
    client_sys = total / wall if wall > 0 else 0.0
    log(f"    algenta-batched B={b}: engine system {engine_sys:.1f} tok/s, "
        f"client system {client_sys:.1f} tok/s (wall {wall:.2f}s, {total} tokens)")
    return engine_sys


def run_algenta_serial(b: int, prompts: list[str], tokenizer, runtime, checkpoint: str,
                       out_tokens: int) -> float:
    ids_list = [tokenizer.encode(p) for p in prompts]
    # untimed warmup (one sequence at the timed shape), then B sequential timed calls
    decode(runtime, checkpoint_dir=checkpoint,
           prompt_token_ids=ids_list[0], max_new_tokens=out_tokens)
    t0 = time.time()
    total = 0
    for ids in ids_list:
        r = decode(runtime, checkpoint_dir=checkpoint,
                   prompt_token_ids=ids, max_new_tokens=out_tokens)
        total += max(0, len(r.token_ids) - r.n_prompt)
    wall = time.time() - t0
    sys_tps = total / wall if wall > 0 else 0.0
    log(f"    algenta-serial  B={b}: system {sys_tps:.1f} tok/s (wall {wall:.2f}s, {total} tokens)")
    return sys_tps


def run_llama_concurrent(b: int, prompts: list[str], port: int, out_tokens: int) -> float:
    # untimed warmup: one concurrent burst at the timed shape
    with concurrent.futures.ThreadPoolExecutor(max_workers=b) as ex:
        list(ex.map(lambda p: llama_one(port, p, out_tokens), prompts))
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=b) as ex:
        results = list(ex.map(lambda p: llama_one(port, p, out_tokens), prompts))
    wall = time.time() - t0
    total = 0
    per_req = []
    for d in results:
        t = d.get("timings", {})
        total += int(t.get("predicted_n", 0))
        per_req.append(float(t.get("predicted_per_second", 0.0)))
    sys_tps = total / wall if wall > 0 else 0.0
    per_req_med = percentile(sorted(per_req), 50)
    log(f"    llama.cpp conc  B={b}: system {sys_tps:.1f} tok/s (wall {wall:.2f}s, {total} tokens; "
        f"per-request decode median {per_req_med:.1f} tok/s)")
    return sys_tps


def run_mlx_serial(b: int, prompts: list[str], checkpoint: str, out_tokens: int) -> float:
    spec = {
        "checkpoint": checkpoint, "n_timed": 1, "n_warmup": 1,
        "cells": [{"prompt": p, "out": out_tokens} for p in prompts],
    }
    spec_path = "/tmp/concurrent_3way_mlx_spec.json"
    Path(spec_path).write_text(json.dumps(spec), encoding="utf-8")
    r = subprocess.run(
        [MLX_PY, MLX_WORKER, spec_path], capture_output=True, text=True, timeout=3600
    )
    if r.returncode != 0:
        raise RuntimeError(f"mlx worker failed: {r.stdout[-400:]} {r.stderr[-400:]}")
    pat = re.compile(
        r"mlx_load_run: cell= (\d+) out= (\d+) run= \d+ prompt_tokens= (\d+) "
        r"gen_tokens= (\d+) prompt_tps= ([0-9.]+) gen_tps= ([0-9.]+)"
    )
    total_tokens = 0
    total_wall = 0.0
    for line in r.stdout.splitlines():
        m = pat.search(line)
        if m:
            gen_tokens = int(m.group(4))
            gen_tps = float(m.group(6))
            if gen_tps > 0:
                total_tokens += gen_tokens
                total_wall += gen_tokens / gen_tps
    sys_tps = total_tokens / total_wall if total_wall > 0 else 0.0
    log(f"    mlx-lm serial   B={b}: system {sys_tps:.1f} tok/s "
        f"({total_tokens} tokens over summed {total_wall:.2f}s)")
    return sys_tps


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--batch-sizes", default="8,16,32")
    ap.add_argument("--in-tokens", type=int, default=256)
    ap.add_argument("--out-tokens", type=int, default=128)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--engines", default="algenta-batched,algenta-serial,llama.cpp,mlx-lm")
    ap.add_argument("--engine-cooldown", type=float, default=0.0)
    ap.add_argument("--llama-ctx", type=int, default=12288)
    ap.add_argument("--out", default="/tmp/concurrent_3way.json")
    args = ap.parse_args()

    batch_sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    known = ("algenta-batched", "algenta-serial", "llama.cpp", "mlx-lm")
    for e in engines:
        if e not in known:
            print(f"unknown engine: {e}")
            return 1
    max_b = max(batch_sizes)
    if max_b > 32:
        print("batched decode supports at most 32 sequences")
        return 1

    tokenizer = load_tokenizer(args.checkpoint)
    prompt_sets = {b: build_prompt_set(b, args.in_tokens, tokenizer) for b in batch_sizes}
    log(f"B cells: {batch_sizes}, in~{args.in_tokens}, out={args.out_tokens}")

    runtime = MojoRuntime(mode="local", timeout=1200.0)
    decode(
        runtime, checkpoint_dir=args.checkpoint,
        prompt_token_ids=tokenizer.encode(PROMPT_UNIT + PROMPT_TAIL), max_new_tokens=4,
    )

    need_llama = "llama.cpp" in engines
    llama = None
    if need_llama:
        log(f"starting llama-server (--parallel {max_b}, ctx {args.llama_ctx}) ...")
        llama = start_llama_server(args.gguf, LLAMA_PORT, args.llama_ctx, max_b)
        log("llama-server healthy")

    collected: dict[str, dict[int, list[float]]] = {
        e: {b: [] for b in batch_sizes} for e in engines
    }
    try:
        for p in range(args.passes):
            order = engines[p % len(engines):] + engines[:p % len(engines)]
            log(f"--- pass {p + 1}/{args.passes}: order = {order}")
            for eng in order:
                if args.engine_cooldown > 0:
                    log(f"    idle cooldown {args.engine_cooldown:.0f}s before {eng} ...")
                    time.sleep(args.engine_cooldown)
                for b in batch_sizes:
                    texts, counts = prompt_sets[b]
                    log(f"  {eng} B={b} (prompt tokens {counts[0]}..{counts[-1]})")
                    if eng == "algenta-batched":
                        collected[eng][b].append(
                            run_algenta_batched(b, texts, tokenizer, runtime,
                                                args.checkpoint, args.out_tokens))
                    elif eng == "algenta-serial":
                        collected[eng][b].append(
                            run_algenta_serial(b, texts, tokenizer, runtime,
                                               args.checkpoint, args.out_tokens))
                    elif eng == "llama.cpp":
                        collected[eng][b].append(
                            run_llama_concurrent(b, texts, LLAMA_PORT, args.out_tokens))
                    elif eng == "mlx-lm":
                        collected[eng][b].append(
                            run_mlx_serial(b, texts, args.checkpoint, args.out_tokens))
    finally:
        stop_llama_server(llama)

    log("=== CONCURRENT SYSTEM DECODE THROUGHPUT (median tok/s) ===")
    header = f"{'B':>4}"
    for e in engines:
        header += f" | {e:>16}"
    log(header)
    report_rows = []
    for b in batch_sizes:
        row = f"{b:>4}"
        entry = {"B": b}
        for e in engines:
            vals = sorted(collected[e][b])
            med = percentile(vals, 50)
            entry[e] = med
            row += f" | {med:>16.1f}"
        report_rows.append(entry)
        log(row)

    report = {
        "config": {
            "checkpoint": args.checkpoint, "gguf": args.gguf, "passes": args.passes,
            "batch_sizes": batch_sizes, "in_tokens": args.in_tokens,
            "out_tokens": args.out_tokens,
            "precisions": {"algenta": "int8", "llama.cpp": "F16", "mlx-lm": "bf16"},
            "protocol": "untimed warmup at timed shape per engine per cell; rotating order; "
                        "medians pooled per (engine, B)",
        },
        "rows": report_rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"results -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
