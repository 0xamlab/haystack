"""tinyllama_deep_bench.py -- TinyLlama DEEP-context single-stream decode throughput harness for
feat/llama-native-deep (UNTRACKED-style campaign driver, same convention as tinyllama_gemv_bench).

Runs the production SDK path end-to-end -- decode() -> MojoRuntime -> native GPU worker -> Metal --
on TinyLlama-1.1B-Chat-v1.0 at a CHOSEN prompt depth (default prompt = the France prompt's ids
repeated to the target length, no llama tokenizer needed), warmup first, median of N timed runs,
and prints the FULL greedy token sequence so correctness (byte-identical output across workers)
can be checked in the same sitting.

    ALGENTA_NATIVE_WORKER=mojo_build/gpu-worker/algenta-gpu-worker-llamanat \
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
      scripts/run_repo_python.sh benchmarks/llm_smoke/tinyllama_deep_bench.py [depth] [runs] [max_new]
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


def build_prompt(depth: int) -> list[int]:
    """Repeat the France id-sequence to the target length (task-prescribed tokenizer-free way to
    get a long prompt)."""
    out: list[int] = []
    while len(out) < depth:
        out.extend(FRANCE_IDS)
    return out[:depth]


def main() -> None:
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    max_new = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    worker = os.environ.get("ALGENTA_NATIVE_WORKER", "<unset>")
    prompt = build_prompt(depth)
    print(f"harness: worker={worker} depth={depth} runs={runs} max_new={max_new}", flush=True)

    rt = MojoRuntime(mode="local", timeout=600.0)

    # Warmup: resident-session adoption, PSO first-dispatch, DVFS ramp (untimed, SAME shape).
    warm = decode(
        rt,
        checkpoint_dir=CHECKPOINT,
        prompt_token_ids=prompt,
        max_new_tokens=max_new,
    )
    print(
        f"warmup: decode={warm.decode_tokens_per_sec:.1f} tok/s "
        f"prefill={warm.prefill_tokens_per_sec:.1f} tok/s n_gen={len(warm.token_ids) - depth}",
        flush=True,
    )

    samples = []
    pf_samples = []
    tokens = None
    for i in range(runs):
        res = decode(
            rt,
            checkpoint_dir=CHECKPOINT,
            prompt_token_ids=prompt,
            max_new_tokens=max_new,
        )
        samples.append(res.decode_tokens_per_sec)
        pf_samples.append(res.prefill_tokens_per_sec)
        gen = res.token_ids[depth:]
        if tokens is None:
            tokens = gen
        elif gen != tokens:
            print(f"RUN {i} TOKEN MISMATCH vs run 0", flush=True)
        print(
            f"run {i}: decode={res.decode_tokens_per_sec:.1f} tok/s "
            f"prefill={res.prefill_tokens_per_sec:.1f} tok/s "
            f"n_gen={len(gen)} stopped_on_eos={res.stopped_on_eos}",
            flush=True,
        )

    med = statistics.median(samples)
    pf_med = statistics.median(pf_samples)
    print(f"MEDIAN decode: {med:.1f} tok/s (samples: {[round(s, 1) for s in samples]})")
    print(f"MEDIAN prefill: {pf_med:.1f} tok/s")
    print(f"first16: {tokens[:16]}")
    print(f"tokens_all: {tokens}")


if __name__ == "__main__":
    main()
