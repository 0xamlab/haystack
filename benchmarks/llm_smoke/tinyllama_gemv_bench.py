"""tinyllama_gemv_bench.py -- TinyLlama single-stream decode throughput harness for the
feat/gemv-streaming GEMV kernel campaign (UNTRACKED dev file, same convention as the other
metal_batch_dispatch campaign drivers).

Runs the production SDK path end-to-end -- decode() -> MojoRuntime -> native GPU worker ->
legacy parametric Metal path -- on TinyLlama-1.1B-Chat-v1.0, warmup first, median of N timed
runs, and prints the FULL greedy token sequence so correctness (byte-identical output) can be
checked against the baseline worker in the same sitting.

    ALGENTA_NATIVE_WORKER=mojo_build/gpu-worker/algenta-gpu-worker-llama \
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
      scripts/run_repo_python.sh benchmarks/llm_smoke/tinyllama_gemv_bench.py [runs]
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
PROMPT_IDS = [1576, 263, 3290, 338, 262, 3303]  # the France prompt
MAX_NEW = 128


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    worker = os.environ.get("ALGENTA_NATIVE_WORKER", "<unset>")
    print(f"harness: worker={worker} runs={runs} max_new={MAX_NEW}", flush=True)

    rt = MojoRuntime(mode="local", timeout=600.0)

    # Warmup: resident-session adoption, PSO first-dispatch, DVFS ramp.
    warm = decode(
        rt,
        checkpoint_dir=CHECKPOINT,
        prompt_token_ids=PROMPT_IDS,
        max_new_tokens=MAX_NEW,
    )
    print(
        f"warmup: decode={warm.decode_tokens_per_sec:.1f} tok/s "
        f"prefill={warm.prefill_tokens_per_sec:.1f} tok/s",
        flush=True,
    )

    samples = []
    tokens = None
    for i in range(runs):
        res = decode(
            rt,
            checkpoint_dir=CHECKPOINT,
            prompt_token_ids=PROMPT_IDS,
            max_new_tokens=MAX_NEW,
        )
        samples.append(res.decode_tokens_per_sec)
        gen = res.token_ids[len(PROMPT_IDS):]
        if tokens is None:
            tokens = gen
        elif gen != tokens:
            print(f"RUN {i} TOKEN MISMATCH vs run 0", flush=True)
        print(
            f"run {i}: decode={res.decode_tokens_per_sec:.1f} tok/s "
            f"n_gen={len(gen)} stopped_on_eos={res.stopped_on_eos}",
            flush=True,
        )

    med = statistics.median(samples)
    print(f"MEDIAN decode: {med:.1f} tok/s (samples: {[round(s, 1) for s in samples]})")
    print(f"first16: {tokens[:16]}")
    print(f"tokens_all: {tokens}")


if __name__ == "__main__":
    main()
