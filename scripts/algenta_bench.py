#!/usr/bin/env python3
"""algenta bench — the model-agnostic throughput battery, driven by facts.

One entry point benches ANY onboarded model through the EXISTING resident doors
— no per-model harness code, no forked drivers:

* Metal arm: the production SDK path (`algenta.inference.decode` for the
  single-stream TTFT + decode rate; `algenta.inference.decode_batched` for the
  concurrent aggregate sweep). The converter + engine already read every fact
  from the manifest, so the bench inherits that fact-driven property verbatim.
* CUDA arm: the resident/serve driver protocol (`enterprise_bench.py` over the
  `qwen3_serve*_cuda` binaries), invoked on the converted checkpoint when the
  driver is present.

The battery sweeps the canonical race shapes (prefill lengths) at each
concurrency, reporting prefill TTFT and aggregate decode tok/s — the same
quantities REALRACE_RESULTS.md ledgers.

Usage:
    python3 scripts/algenta_bench.py metal <checkpoint_dir> \
        [--shapes 160,256,550] [--concurrency 1,8] [--gen 64] [--runs 3]

Output: one JSON record per (shape, concurrency) cell on stdout, plus a compact
table. The exit code is 0 when every cell ran.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = _ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))


def _prompt_ids(n_tokens: int) -> list[int]:
    """A deterministic prompt of exactly `n_tokens` ids (a fixed cycle), so the
    prefill length is the controlled variable and no tokenizer is needed."""
    base = [785, 6722, 315, 9625, 374, 12095, 13, 576]
    return [base[i % len(base)] for i in range(n_tokens)]


def bench_metal(
    checkpoint_dir: str,
    shapes: list[int],
    concurrency: list[int],
    gen: int,
    runs: int,
    worker: str | None,
) -> list[dict]:
    from algenta import MojoRuntime
    from algenta.inference import decode, decode_batched

    if worker:
        os.environ["ALGENTA_NATIVE_WORKER"] = worker
    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    runtime = MojoRuntime(mode="local", timeout=900.0)

    cells: list[dict] = []
    for shape in shapes:
        prompt = _prompt_ids(shape)
        # Single-stream: TTFT (prefill wall) + decode rate, median over runs.
        ttft_ms_samples, decode_samples = [], []
        for _ in range(runs):
            res = decode(
                runtime,
                checkpoint_dir=checkpoint_dir,
                prompt_token_ids=prompt,
                max_new_tokens=gen,
            )
            ttft = (
                shape / res.prefill_tokens_per_sec * 1000.0
                if res.prefill_tokens_per_sec > 0
                else float("nan")
            )
            ttft_ms_samples.append(ttft)
            decode_samples.append(res.decode_tokens_per_sec)
        cells.append(
            {
                "backend": "metal",
                "shape": shape,
                "concurrency": 1,
                "ttft_ms": round(statistics.median(ttft_ms_samples), 3),
                "decode_tok_s": round(statistics.median(decode_samples), 2),
            }
        )
        # Concurrent aggregate sweep at this shape.
        for conc in concurrency:
            if conc == 1:
                continue
            prompts = [prompt for _ in range(conc)]
            agg_samples = []
            for _ in range(runs):
                res = decode_batched(
                    runtime,
                    checkpoint_dir=checkpoint_dir,
                    prompt_token_ids_list=prompts,
                    max_new_tokens=gen,
                )
                agg_samples.append(res.decode_tokens_per_sec)
            cells.append(
                {
                    "backend": "metal",
                    "shape": shape,
                    "concurrency": conc,
                    "agg_decode_tok_s": round(statistics.median(agg_samples), 2),
                }
            )
    return cells


def bench_cuda(
    checkpoint_dir: str,
    driver: str,
    shapes: list[int],
    gen: int,
    runs: int,
) -> list[dict]:
    """The CUDA arm: the fact-driven `conform_generate_cuda` resident binary,
    converted once and swept across prefill shapes via its `--prompt-len`
    override (the blob is prompt-independent). Single-stream TTFT + decode rate
    — the batched/concurrent CUDA sweep needs the serve driver's fact
    generalization and is reported separately."""
    import subprocess
    import tempfile

    from algenta.inference import prepare_model_checkpoint

    converted = Path(tempfile.mkdtemp(prefix="algenta-bench-cuda-"))
    prepare_model_checkpoint(checkpoint_dir, _prompt_ids(8), out_dir=str(converted), backend="cuda")

    cells: list[dict] = []
    for shape in shapes:
        ttft_samples, decode_samples = [], []
        for _ in range(runs):
            proc = subprocess.run(
                [driver, str(converted), "--max-new", str(gen), "--prompt-len", str(shape)],
                capture_output=True,
                text=True,
                timeout=900,
            )
            prefill_ms = decode_tok_s = None
            for line in proc.stdout.splitlines():
                if line.startswith("CONFORM_TIMING:"):
                    for token in line.split():
                        if token.startswith("prefill_ms="):
                            prefill_ms = float(token.split("=", 1)[1])
                        elif token.startswith("decode_tok_s="):
                            decode_tok_s = float(token.split("=", 1)[1])
            if prefill_ms is None:
                tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or ["<no output>"]
                raise RuntimeError(f"conform driver produced no timing: {tail[0][:160]}")
            ttft_samples.append(prefill_ms)
            if decode_tok_s is not None:
                decode_samples.append(decode_tok_s)
        cells.append(
            {
                "backend": "cuda",
                "shape": shape,
                "concurrency": 1,
                "ttft_ms": round(statistics.median(ttft_samples), 3),
                "decode_tok_s": round(statistics.median(decode_samples), 2) if decode_samples else None,
            }
        )
    return cells


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="algenta_bench", description="Fact-driven throughput battery over the existing doors."
    )
    parser.add_argument(
        "backend", choices=["metal", "cuda"], help="the backend whose resident door to drive"
    )
    parser.add_argument("checkpoint", help="an onboarded checkpoint directory (config.json + safetensors)")
    parser.add_argument("--shapes", default="160,256,550", help="comma-separated prefill lengths")
    parser.add_argument("--concurrency", default="1,8", help="comma-separated concurrency levels")
    parser.add_argument("--gen", type=int, default=64, help="tokens to generate per request")
    parser.add_argument("--runs", type=int, default=3, help="timed runs per cell (median)")
    parser.add_argument("--worker", help="override ALGENTA_NATIVE_WORKER (metal arm)")
    parser.add_argument(
        "--driver",
        help="the fact-driven conform_generate_cuda binary (cuda arm) or ALGENTA_CONFORM_CUDA_DRIVER",
    )
    args = parser.parse_args(argv)

    shapes = [int(s) for s in args.shapes.split(",") if s.strip()]
    concurrency = [int(c) for c in args.concurrency.split(",") if c.strip()]

    # Fact-driven preflight: the onboard verdict must support this backend before
    # any GPU work, so the bench inherits the capability table's typed refusals.
    from algenta.inference import _normalize_config
    from algenta.onboarding import backend_verdicts, onboard_facts, resolve_config

    config, source_desc, _ = resolve_config(args.checkpoint)
    facts = onboard_facts(config)
    verdict = backend_verdicts(facts, backends=(args.backend,))[args.backend]
    if not verdict.supported:
        for refusal in verdict.refusals:
            print(f"REFUSED [{args.backend}]: {refusal.message()}", file=sys.stderr)
        return 2
    print(f"bench: {source_desc} on {args.backend} (plan={verdict.plan})", file=sys.stderr)

    if args.backend == "metal":
        cells = bench_metal(args.checkpoint, shapes, concurrency, args.gen, args.runs, args.worker)
    else:
        driver = args.driver or os.environ.get("ALGENTA_CONFORM_CUDA_DRIVER")
        if not driver or not Path(driver).is_file():
            print("cuda arm needs --driver <conform_generate_cuda binary>", file=sys.stderr)
            return 2
        cells = bench_cuda(args.checkpoint, driver, shapes, args.gen, args.runs)

    for cell in cells:
        print(json.dumps(cell))
    # Compact table.
    print("\nshape  conc  ttft_ms  decode/agg tok_s", file=sys.stderr)
    for cell in cells:
        metric = cell.get("decode_tok_s", cell.get("agg_decode_tok_s"))
        ttft = cell.get("ttft_ms", "-")
        print(
            f"{cell['shape']:<6} {cell['concurrency']:<5} {ttft:<8} {metric}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
