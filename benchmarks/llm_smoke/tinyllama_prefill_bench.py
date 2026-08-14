"""tinyllama_prefill_bench.py -- TinyLlama single-stream PREFILL throughput + correctness
harness for the feat/llama-prefill campaign (steel d64 AF prefill for llama).

Runs the production SDK path end-to-end -- decode() -> MojoRuntime -> native GPU worker ->
Metal -- on TinyLlama-1.1B-Chat-v1.0. Two sections:

  1. CORRECTNESS: the 6-token France prompt greedy first tokens (must start [3900, 29889, 13]
     = " Paris."), plus a longer greedy continuation, printed so byte-identity vs a baseline
     worker can be checked in the same sitting.
  2. PREFILL THROUGHPUT: long prompts (France ids repeated to 512 / 1024 tokens), max_new=1,
     warmup first, median of N timed runs -- the number to race against llama.cpp's
     llama-bench -p 512 -n 0.

    ALGENTA_NATIVE_WORKER=mojo_build/gpu-worker/algenta-gpu-worker-llamapf \
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
      scripts/run_repo_python.sh benchmarks/llm_smoke/tinyllama_prefill_bench.py [runs]
"""

from __future__ import annotations

import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode  # noqa: E402

CHECKPOINT = "/private/tmp/tinyllama"
FRANCE_IDS = [1576, 263, 3290, 338, 262, 3303]  # the France prompt
MAX_NEW = 128
PREFILL_DEPTHS = (512, 1024)


def _prompt_of(n: int) -> list[int]:
    out: list[int] = []
    while len(out) < n:
        out.extend(FRANCE_IDS)
    return out[:n]


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    worker = os.environ.get("ALGENTA_NATIVE_WORKER", "<unset>")
    print(f"harness: worker={worker} runs={runs}", flush=True)

    rt = MojoRuntime(mode="local", timeout=900.0)

    # ── correctness: short France prompt, greedy continuation.
    res = decode(rt, checkpoint_dir=CHECKPOINT, prompt_token_ids=FRANCE_IDS, max_new_tokens=MAX_NEW)
    gen = res.token_ids[len(FRANCE_IDS):]
    print(f"france first8: {gen[:8]}")
    print(f"france gen64: {gen[:64]}")

    # ── deep correctness: 1024-token prompt, 64 generated tokens (exercises the AF chunk at
    # depth and the decode handoff from the AF-written KV cache).
    deep_prompt = _prompt_of(1024)
    res_deep = decode(rt, checkpoint_dir=CHECKPOINT, prompt_token_ids=deep_prompt, max_new_tokens=64)
    gen_deep = res_deep.token_ids[len(deep_prompt):]
    print(f"deep1024 first_tok: {gen_deep[:1]}")
    print(f"deep1024 gen64: {gen_deep[:64]}")

    # ── prefill throughput at each depth: warmup (untimed) + N timed, median.
    for n in PREFILL_DEPTHS:
        prompt = _prompt_of(n)
        warm = decode(rt, checkpoint_dir=CHECKPOINT, prompt_token_ids=prompt, max_new_tokens=1)
        samples = []
        for _ in range(runs):
            r = decode(rt, checkpoint_dir=CHECKPOINT, prompt_token_ids=prompt, max_new_tokens=1)
            samples.append(r.prefill_tokens_per_sec)
        med = statistics.median(samples)
        print(f"prefill@{n}: median {med:.1f} tok/s (samples: {[round(s, 1) for s in samples]})")


if __name__ == "__main__":
    main()
