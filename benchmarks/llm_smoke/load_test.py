"""load_test.py -- enterprise load/stress harness for the Algenta Apple-Silicon LLM engine
(beat-llama.cpp campaign, 2026-08-10).

Two measurement lanes, both against the REAL Metal GPU worker through the production SDK shape
(`algenta.inference.decode` -> `MojoRuntime` -> AF_UNIX worker -> anyqwen3 entry -> Metal):

1. STRESS (`--mode stress`): an input-x-output token-size matrix. For every (input_tokens,
   output_tokens) cell the harness measures prefill throughput, decode throughput, and end-to-end
   wall, and gates correctness on GREEDY DETERMINISM (the same prompt decoded twice must yield a
   byte-identical token sequence) plus a valid-token-range check. This is the "much larger token
   input and output" lane: it characterizes how prefill and decode rates scale as context grows.

2. CONCURRENT (`--mode concurrent`): N in-flight requests x R rounds. Each request is one
   `decode()` call at a fixed (input, output) size; threads issue them simultaneously against the
   shared resident worker. The harness records every request's end-to-end latency and computes
   aggregate throughput and latency percentiles (p50/p90/p95/p99) plus error rate. The current
   single-stream engine SERIALIZES requests in the worker (measured, recorded honestly): wall time
   grows ~linearly with concurrency, so this lane documents queueing behavior, not parallel scaling.

Correctness gate (both lanes): greedy decode is deterministic -- identical prompt + parameters must
reproduce the identical token ids -- and every generated id must be inside the model vocab. This is
the load-appropriate honesty gate; it does not depend on any particular prompt's continuation.

The prompt is built by repeating a factual sentence to reach the target input length, so the input
is real tokenized text (not padding). A leading warmup call loads the weights into the resident
worker so timed cells measure serving, not first-load.

Usage (repo root, GPU worker built from this tree):
  ALGENTA_RUNTIME_FALLBACK_MODE=allow \
  ALGENTA_NATIVE_WORKER=$PWD/mojo_build/gpu-worker/algenta-gpu-worker \
  python3 benchmarks/llm_smoke/load_test.py \
      --checkpoint /private/tmp/qwen3-0.6b-base --mode stress \
      --input-tokens 1024,4096 --output-tokens 512,1024
  ALGENTA_RUNTIME_FALLBACK_MODE=allow \
  ALGENTA_NATIVE_WORKER=$PWD/mojo_build/gpu-worker/algenta-gpu-worker \
  python3 benchmarks/llm_smoke/load_test.py \
      --checkpoint /private/tmp/qwen3-0.6b-base --mode concurrent \
      --concurrency 1,2,4,8 --requests-per-level 8 --input-tokens 512 --output-tokens 128
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode  # noqa: E402
from algenta.tokenizer import load_tokenizer  # noqa: E402

_PROMPT_UNIT = "The capital of France is Paris. The largest planet in the solar system is Jupiter. "


def build_prompt_ids(tokenizer, target_tokens: int) -> list[int]:
    """Real tokenized text of ~target_tokens by repeating a factual sentence, truncated to size."""
    unit_ids = tokenizer.encode(_PROMPT_UNIT)
    ids: list[int] = []
    while len(ids) < target_tokens:
        ids.extend(unit_ids)
    return ids[:target_tokens]


def percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile of an already-sorted list (p in [0,100])."""
    if not sorted_values:
        return 0.0
    k = max(0, min(len(sorted_values) - 1, int(round((pct / 100.0) * (len(sorted_values) - 1)))))
    return sorted_values[k]


def decode_once(runtime, checkpoint: str, prompt_ids: list[int], max_new: int):
    """One decode call; returns (wall_seconds, result)."""
    t0 = time.time()
    result = decode(
        runtime,
        checkpoint_dir=checkpoint,
        prompt_token_ids=prompt_ids,
        max_new_tokens=max_new,
    )
    return time.time() - t0, result


def correctness_ok(vocab_size: int, first: list[int], second: list[int]) -> tuple[bool, str]:
    """Greedy determinism + valid-token-range gate for one (input, output) cell."""
    if first != second:
        return False, "greedy determinism violated: two identical calls produced different ids"
    for token_id in first:
        if not 0 <= token_id < vocab_size:
            return False, f"generated id {token_id} outside vocab [0,{vocab_size})"
    return True, "ok"


def run_stress(args, runtime, tokenizer, checkpoint: str) -> dict:
    vocab_size = tokenizer.vocab_size
    cells = []
    for n_in in args.input_tokens:
        prompt_ids = build_prompt_ids(tokenizer, n_in)
        for n_out in args.output_tokens:
            walls, prefills, decodes = [], [], []
            gen_ids = None
            ok, why = True, "ok"
            for _ in range(args.iterations):
                wall, result = decode_once(runtime, checkpoint, prompt_ids, n_out)
                walls.append(wall)
                prefills.append(result.prefill_tokens_per_sec)
                decodes.append(result.decode_tokens_per_sec)
                this_gen = result.token_ids[result.n_prompt :]
                if gen_ids is None:
                    gen_ids = this_gen
                else:
                    ok, why = correctness_ok(vocab_size, gen_ids, this_gen)
            # One extra determinism check is folded into iterations>=2; for iterations==1 do a pair.
            if args.iterations < 2:
                wall2, result2 = decode_once(runtime, checkpoint, prompt_ids, n_out)
                ok, why = correctness_ok(
                    vocab_size, gen_ids, result2.token_ids[result2.n_prompt :]
                )
            cells.append(
                {
                    "input_tokens": n_in,
                    "output_tokens": n_out,
                    "context_tokens": n_in + n_out,
                    "iterations": args.iterations,
                    "wall_s_median": statistics.median(walls),
                    "prefill_tok_s_median": statistics.median(prefills),
                    "decode_tok_s_median": statistics.median(decodes),
                    "n_generated": len(gen_ids) if gen_ids is not None else 0,
                    "correct": ok,
                    "correctness_note": why,
                }
            )
            print(
                f"[stress] in={n_in} out={n_out} ctx={n_in + n_out} "
                f"wall={statistics.median(walls):.2f}s "
                f"prefill={statistics.median(prefills):.0f} tok/s "
                f"decode={statistics.median(decodes):.0f} tok/s correct={ok}",
                flush=True,
            )
    return {"mode": "stress", "cells": cells}


def run_concurrent(args, runtime, tokenizer, checkpoint: str) -> dict:
    # Concurrent lane uses ONE fixed request shape (the first listed size) across all levels.
    input_tokens = args.input_tokens[0]
    output_tokens = args.output_tokens[0]
    levels = []
    for n_conc in args.concurrency:
        latencies: list[float] = []
        errors = 0
        total_generated = 0
        prompt_ids = build_prompt_ids(tokenizer, input_tokens)

        level_t0 = time.time()
        for _round in range(args.requests_per_level):
            results: list = [None] * n_conc
            failures = [0]

            def worker(
                index: int,
                _prompt_ids: list = prompt_ids,
                _results: list = results,
                _failures: list = failures,
                _max_new: int = output_tokens,
            ) -> None:
                try:
                    wall, result = decode_once(runtime, checkpoint, _prompt_ids, _max_new)
                    _results[index] = (wall, result)
                except Exception:  # noqa: BLE001 - counted as an error, not a crash
                    _failures[0] += 1
                    _results[index] = None

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_conc)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            for entry in results:
                if entry is None:
                    errors += 1
                    continue
                wall, result = entry
                latencies.append(wall)
                total_generated += len(result.token_ids) - result.n_prompt

        sorted_lat = sorted(latencies)
        level_wall = time.time() - level_t0
        n_requests = args.requests_per_level * n_conc
        levels.append(
            {
                "concurrency": n_conc,
                "requests": n_requests,
                "errors": errors,
                "error_rate": errors / n_requests if n_requests else 0.0,
                "level_wall_s": level_wall,
                "latency_s_p50": percentile(sorted_lat, 50),
                "latency_s_p90": percentile(sorted_lat, 90),
                "latency_s_p95": percentile(sorted_lat, 95),
                "latency_s_p99": percentile(sorted_lat, 99),
                "latency_s_max": sorted_lat[-1] if sorted_lat else 0.0,
                "total_generated_tokens": total_generated,
                # System throughput: total generated tokens over the level's elapsed wall. For
                # the serialized single-stream engine this stays ~constant (the GPU emits one
                # token at a time); it is the honest aggregate, unlike per-request latency which
                # adds queue wait.
                "system_decode_tok_s": total_generated / level_wall if level_wall else 0.0,
            }
        )
        print(
            f"[concurrent] C={n_conc} reqs={n_requests} errors={errors} "
            f"p50={percentile(sorted_lat, 50):.3f}s p95={percentile(sorted_lat, 95):.3f}s "
            f"p99={percentile(sorted_lat, 99):.3f}s max={sorted_lat[-1] if sorted_lat else 0:.3f}s",
            flush=True,
        )
    return {"mode": "concurrent", "levels": levels}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--checkpoint", required=True, help="HuggingFace snapshot dir (config.json)")
    ap.add_argument("--mode", choices=("stress", "concurrent"), default="stress")
    ap.add_argument(
        "--input-tokens",
        type=str,
        default="512,1024",
        help="comma-separated prompt sizes (tokens)",
    )
    ap.add_argument(
        "--output-tokens",
        type=str,
        default="128",
        help="comma-separated generation sizes (tokens)",
    )
    ap.add_argument(
        "--concurrency", type=str, default="1,2,4", help="concurrent-request levels (concurrent)"
    )
    ap.add_argument(
        "--requests-per-level", type=int, default=4, help="rounds per concurrency level"
    )
    ap.add_argument("--iterations", type=int, default=2, help="timed iterations per stress cell")
    ap.add_argument("--json-out", type=str, default=None, help="write the JSON report here")
    args = ap.parse_args()

    args.input_tokens = [int(x) for x in args.input_tokens.split(",") if x.strip()]
    args.output_tokens = [int(x) for x in args.output_tokens.split(",") if x.strip()]
    args.concurrency = [int(x) for x in args.concurrency.split(",") if x.strip()]

    tokenizer = load_tokenizer(args.checkpoint)
    runtime = MojoRuntime(mode="local", timeout=900.0)

    # Warmup: load weights into the resident worker so timed work measures serving, not first-load.
    warm_prompt = build_prompt_ids(tokenizer, 64)
    decode(runtime, checkpoint_dir=args.checkpoint, prompt_token_ids=warm_prompt, max_new_tokens=4)

    started = time.time()
    if args.mode == "stress":
        report = run_stress(args, runtime, tokenizer, args.checkpoint)
    else:
        report = run_concurrent(args, runtime, tokenizer, args.checkpoint)
    report["total_wall_s"] = time.time() - started
    report["checkpoint"] = args.checkpoint

    print("\n=== JSON report ===")
    print(json.dumps(report, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}", file=sys.stderr)

    # Non-zero exit if any stress cell failed correctness, so this can gate CI.
    if args.mode == "stress" and any(not cell["correct"] for cell in report["cells"]):
        print("CORRECTNESS FAILURE in one or more stress cells", file=sys.stderr)
        return 1
    if args.mode == "concurrent" and any(level["errors"] for level in report["levels"]):
        print("ERRORS under concurrent load", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
