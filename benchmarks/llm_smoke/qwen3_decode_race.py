"""qwen3_decode_race.py -- Qwen3-0.6B single-stream decode throughput race harness for
feat/metal-beat (campaign driver, same convention as tinyllama_deep_bench.py).

Runs the production SDK path end-to-end -- decode() -> MojoRuntime -> native GPU worker -> Metal
-- on Qwen3-0.6B-Base with the campaign's 256-token race prompt at a FIXED generation length N
(one shape per process, so the per-shape session-rebuild tax never touches the timed calls:
warmup call first, then `runs` timed calls, ALL at the same max_new_tokens=N).

Two rates are reported per call:
  * decode  = the worker-reported decode rate (res.decode_tokens_per_sec) -- the single-stream
              decode function itself, the functional twin of llama-bench's tg column.
  * walldec = n_gen / (call wall - prefill wall) -- the delivered-path decode window with the
              measured prefill subtracted (protocol framing stays inside the window, honestly).

Median + relative IQR over `runs` samples; the full greedy token sequence is printed so
byte-identity can be checked in the same sitting.

    ALGENTA_NATIVE_WORKER=mojo_build/gpu-worker/algenta-gpu-worker-mb-qwen3 \
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
      scripts/run_repo_python.sh benchmarks/llm_smoke/qwen3_decode_race.py [n_gen] [runs]
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode  # noqa: E402

CHECKPOINT = "/private/tmp/qwen3-0.6b-base"
CONVERTED = "/tmp/qwen3smoke"


def race_prompt_ids() -> list[int]:
    manifest = json.loads((Path(CONVERTED) / "manifest.json").read_text(encoding="utf-8"))
    ids = list(manifest["input_ids"])
    assert manifest["config"]["n_tokens"] == len(ids) == 256
    return ids


def main() -> None:
    n_gen = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    worker = os.environ.get("ALGENTA_NATIVE_WORKER", "<unset>")
    prompt = race_prompt_ids()
    print(f"harness: worker={worker} n_gen={n_gen} runs={runs} prompt=256", flush=True)

    rt = MojoRuntime(mode="local", timeout=600.0)

    def one_call() -> tuple[float, float, float, list[int]]:
        t0 = time.perf_counter()
        res = decode(
            rt,
            checkpoint_dir=CHECKPOINT,
            converted_checkpoint_dir=CONVERTED,
            prompt_token_ids=prompt,
            max_new_tokens=n_gen,
        )
        wall = time.perf_counter() - t0
        gen = res.token_ids[256:]
        pf_wall = 256.0 / res.prefill_tokens_per_sec if res.prefill_tokens_per_sec > 0 else 0.0
        walldec = len(gen) / (wall - pf_wall) if wall > pf_wall else 0.0
        return res.decode_tokens_per_sec, walldec, wall, gen

    warm = one_call()
    print(
        f"warmup: decode={warm[0]:.1f} walldec={warm[1]:.1f} wall={warm[2] * 1000:.0f}ms "
        f"n_gen={len(warm[3])}",
        flush=True,
    )

    samples: list[float] = []
    wall_samples: list[float] = []
    call_samples: list[float] = []
    tokens = None
    for i in range(runs):
        rate, walldec, wall, gen = one_call()
        samples.append(rate)
        wall_samples.append(walldec)
        call_samples.append(wall)
        if tokens is None:
            tokens = gen
        elif gen != tokens:
            print(f"RUN {i} TOKEN MISMATCH vs run 0", flush=True)
        print(f"run {i}: decode={rate:.1f} walldec={walldec:.1f} wall={wall * 1000:.0f}ms", flush=True)

    med = statistics.median(samples)
    iqr = statistics.quantiles(samples, n=4)
    rel_iqr = (iqr[2] - iqr[0]) / med if med > 0 else 0.0
    wmed = statistics.median(wall_samples)
    print(f"MEDIAN decode: {med:.1f} tok/s (relIQR={rel_iqr * 100:.2f}%)")
    print(f"MEDIAN walldec: {wmed:.1f} tok/s")
    print(f"samples: {[round(s, 1) for s in samples]}")
    print(f"first8: {tokens[:8]}")


if __name__ == "__main__":
    main()
