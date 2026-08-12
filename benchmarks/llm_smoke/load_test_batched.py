"""load_test_batched.py -- beat-llama.cpp campaign concurrent front (2026-08-11): the BATCHED
serving load test. Measures the Slipstream batched decode path END-TO-END through the production
shape (SDK `decode_batched` -> MojoRuntime -> GPU worker -> Metal): B sequences ingested into the
per-sequence batched KV caches, then ALL B stepped together in one descriptor-table submission
per token (weights swept ONCE per token for the whole batch -- the tokens-per-weight-sweep win).

Reports SYSTEM throughput (all B sequences' tokens / wall) across a B sweep, with the campaign's
correctness discipline: (1) all B sequences get the SAME prompt, so all B generations must be
byte-identical to each other; (2) one reference single-stream decode() of the same prompt must
match every batched sequence byte-for-byte (greedy determinism across kernel tiers); (3) repeated
iterations are medians.

The comparison frame for the ledger: single-stream controls (llama.cpp/MLX, from the three-way)
serve ONE request at a time -- this harness measures B served TOGETHER.

    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_NATIVE_WORKER="$PWD/mojo_build/gpu-worker/algenta-gpu-worker-batch" \
    bash scripts/run_repo_python.sh benchmarks/llm_smoke/load_test_batched.py \
        --checkpoint /private/tmp/qwen3-0.6b-base --input-tokens 512 --output-tokens 128 \
        --batch-sizes 4,8,16,32 --iterations 3 --out /tmp/load_batched.json
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode, decode_batched  # noqa: E402

VOCAB = 151936


def build_prompt(n_tokens: int) -> list[int]:
    """Deterministic pseudo-prompt (same discipline as the smoke gate -- greedy determinism
    matters, not semantic content)."""
    return [(i * 7 + 13) % VOCAB for i in range(n_tokens)]


def run(args) -> dict:
    rt = MojoRuntime(mode="local")
    prompt = build_prompt(args.input_tokens)

    # Reference: single-stream decode of the same prompt (also the per-request baseline).
    t0 = time.perf_counter()
    ref = decode(rt, checkpoint_dir=args.checkpoint, prompt_token_ids=list(prompt),
                 max_new_tokens=args.output_tokens)
    ref_wall = time.perf_counter() - t0
    ref_gen = ref.token_ids[len(prompt):]
    print(
        f"[reference] single-stream: decode={ref.decode_tokens_per_sec:.1f} tok/s "
        f"(wall {ref_wall:.2f}s), first tokens {ref_gen[:6]}"
    )

    results = []
    for B in args.batch_sizes:
        prefs, decs, walls = [], [], []
        ok = True
        for it in range(args.iterations):
            t1 = time.perf_counter()
            res = decode_batched(
                rt, checkpoint_dir=args.checkpoint,
                prompt_token_ids_list=[list(prompt) for _ in range(B)],
                max_new_tokens=args.output_tokens,
            )
            wall = time.perf_counter() - t1
            walls.append(wall)
            prefs.append(res.prefill_tokens_per_sec)
            decs.append(res.decode_tokens_per_sec)
            for b in range(B):
                gen = res.generated_token_ids[b]
                if gen != ref_gen:
                    print(f"[B={B} iter={it}] seq {b} MISMATCH vs single-stream reference")
                    ok = False
            if it == 0:
                distinct = {tuple(g) for g in res.generated_token_ids}
                if len(distinct) != 1:
                    print(f"[B={B}] sequences with identical prompts diverged from each other")
                    ok = False
        results.append({
            "B": B,
            "system_prefill_tok_s_median": statistics.median(prefs),
            "system_decode_tok_s_median": statistics.median(decs),
            "wall_s_median": statistics.median(walls),
            "per_seq_decode_tok_s": statistics.median(decs) / B,
            "correct": ok,
        })
        print(
            f"[batched] B={B:2d} system pf/dc = "
            f"{statistics.median(prefs):7.0f}/{statistics.median(decs):6.1f} tok/s "
            f"wall={statistics.median(walls):.2f}s correct={ok}"
        )

    return {
        "config": {
            "checkpoint": args.checkpoint,
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "batch_sizes": args.batch_sizes,
            "iterations": args.iterations,
        },
        "single_stream_reference": {
            "decode_tok_s": ref.decode_tokens_per_sec,
            "prefill_tok_s": ref.prefill_tokens_per_sec,
        },
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="batched (continuous-batching) decode load test")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--input-tokens", type=int, default=512)
    ap.add_argument("--output-tokens", type=int, default=128)
    ap.add_argument("--batch-sizes", type=str, default="4,8,16,32")
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    args.batch_sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]

    report = run(args)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"results -> {args.out}")
    if not all(r["correct"] for r in report["results"]):
        print("CORRECTNESS FAILED")
        return 1
    print("ALL CORRECT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
