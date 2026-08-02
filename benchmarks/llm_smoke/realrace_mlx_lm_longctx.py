"""realrace_mlx_lm_longctx.py — the LONG-GENERATION twin of `realrace_mlx_lm.py`.

Same checkpoint, same greedy (temp=0) decode, but generates `--max-tokens` (thousands, not 16) and
records INSTANTANEOUS per-token wall time (time between consecutive `stream_generate` yields, not
`GenerationResponse.generation_tps`'s own cumulative-average-since-start metric, which cannot show a
per-position slowdown) so this race can be checked for the same abnormal-degradation question the
Mojo `..._longctx_probe.mojo` binary's `generated_ids.txt` answers for Algenta's side.

Writes a JSON file with every generated token id and its own per-token latency in ms, for both the
per-position rate table and the correctness cross-check against `reference_generate.py`.

Run (uses the isolated pip env — never bare `python`, never cwd=/tmp):
    /tmp/bb/bin/python -P /path/to/realrace_mlx_lm_longctx.py --checkpoint /private/tmp/qwen3-0.6b-base \
        --max-tokens 4096 --out /tmp/bb/qwen3_ckpt/mlx_lm_longctx_4096.json
"""

import argparse
import json
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True, help="local HF snapshot dir (config.json + model.safetensors)")
    ap.add_argument("--prompt", default="The capital of France is")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(args.checkpoint)
    sampler = make_sampler(temp=0.0)  # temp=0 -> argmax, the same greedy rule the Mojo driver uses

    token_ids = []
    per_token_ms = []
    text = ""
    last = None
    t_prev = time.perf_counter()
    stopped_on_eos = True  # stream_generate's own loop breaks on eos; False only if max_tokens truncated first
    for response in stream_generate(model, tokenizer, args.prompt, max_tokens=args.max_tokens, sampler=sampler):
        t_now = time.perf_counter()
        per_token_ms.append((t_now - t_prev) * 1000.0)
        t_prev = t_now
        token_ids.append(int(response.token))
        text += response.text
        last = response
        n = len(token_ids)
        if n <= 8 or n % 256 == 0:
            print(f"[mlx-lm-longctx] token {n}: id={response.token} cum_tps={response.generation_tps:.2f}",
                  file=sys.stderr)

    if last is not None and last.finish_reason == "length":
        stopped_on_eos = False

    print(f"[mlx-lm-longctx] generated {len(token_ids)} tokens, stopped_on_eos={stopped_on_eos}", file=sys.stderr)
    print(f"[mlx-lm-longctx] generated text (repr, truncated): {text[:200]!r}...", file=sys.stderr)
    if last is not None:
        print(
            f"[mlx-lm-longctx] prompt: {last.prompt_tokens} tok, {last.prompt_tps:.3f} tok/s | "
            f"generation: {last.generation_tokens} tok, FINAL cumulative {last.generation_tps:.3f} tok/s "
            f"(peak mem {last.peak_memory:.3f} GB)",
            file=sys.stderr,
        )

    result = {
        "engine": "mlx-lm",
        "prompt": args.prompt,
        "max_tokens": args.max_tokens,
        "token_ids": token_ids,
        "per_token_ms": per_token_ms,
        "stopped_on_eos": stopped_on_eos,
        "final_cumulative_tps": last.generation_tps if last is not None else None,
    }
    with open(args.out, "w") as f:
        json.dump(result, f)
    print(f"[mlx-lm-longctx] -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
