"""load_test_mlx_worker.py -- the MLX-LM arm of the enterprise load comparison
(benchmarks/llm_smoke/load_test_3way.py). Resident MLX worker: loads the checkpoint ONCE from its
HF snapshot, then runs the exact prompts the orchestrator hands it (via a JSON spec file, so the
prompt BYTES are identical to the other engines' -- no re-tokenization drift) and reports MLX's own
`prompt_tps` (prefill) and `generation_tps` (decode) per run. Greedy (temp=0).

CLI:
    /tmp/mlm_venv/bin/python load_test_mlx_worker.py <spec.json>
where spec.json is {"checkpoint": str, "n_timed": int, "n_warmup": int,
                     "cells": [{"prompt": str, "out": int}, ...]}

Output lines (machine-parsed by the orchestrator):
    mlx_load_run: cell=<i> out=<N> run=<j> prompt_tokens=<np> gen_tokens=<ng>
                  prompt_tps=<p> gen_tps=<g>
"""

import json
import sys


def main():
    spec_path = sys.argv[1]
    spec = json.load(open(spec_path))
    checkpoint = spec["checkpoint"]
    n_timed = int(spec.get("n_timed", 1))
    n_warmup = int(spec.get("n_warmup", 1))
    cells = spec["cells"]

    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(checkpoint)
    sampler = make_sampler(temp=0.0)  # greedy = argmax, same rule as the other arms

    def one_gen(prompt_text, max_tokens):
        last = None
        n_gen = 0
        for response in stream_generate(
            model, tokenizer, prompt_text, max_tokens=max_tokens, sampler=sampler
        ):
            last = response
            if getattr(response, "token", None) is not None:
                n_gen += 1
        return last, n_gen

    # Warmup (untimed): exercise each cell once so the timed runs are warm.
    for _ in range(max(1, n_warmup)):
        for cell in cells:
            _, _ = one_gen(cell["prompt"], cell["out"])
    print("  mlx warmup done", file=sys.stderr)

    for i, cell in enumerate(cells):
        out = int(cell["out"])
        for run in range(n_timed):
            last, n_gen = one_gen(cell["prompt"], out)
            prompt_tokens = getattr(last, "prompt_tokens", 0)
            prompt_tps = getattr(last, "prompt_tps", 0.0) or 0.0
            gen_tps = getattr(last, "generation_tps", 0.0) or 0.0
            print(
                f"mlx_load_run: cell= {i} out= {out} run= {run} "
                f"prompt_tokens= {prompt_tokens} gen_tokens= {n_gen} "
                f"prompt_tps= {prompt_tps:.2f} gen_tps= {gen_tps:.2f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
