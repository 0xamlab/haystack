"""batched_decode_smoke.py -- beat-llama.cpp campaign concurrent front (2026-08-11): the smoke
gate for the Slipstream batched decode serving path (engine `qwen3_batched_prefill_decode_anyqwen3`
+ SDK `decode_batched`). Invariant under test: B copies of the SAME prompt must produce B
BYTE-IDENTICAL generations, each byte-identical to the single-stream `decode()` of that prompt
(greedy determinism through a different kernel tier: batched GEMM/attention/merge vs the
single-stream table). Run through the production worker shape:

    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_NATIVE_WORKER="$PWD/mojo_build/gpu-worker/algenta-gpu-worker-batch" \
    bash scripts/run_repo_python.sh benchmarks/llm_smoke/batched_decode_smoke.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode, decode_batched  # noqa: E402

CKPT = "/private/tmp/qwen3-0.6b-base"
B = 4
N_OUT = 32


def main() -> int:
    rt = MojoRuntime(mode="local")
    prompt = list(range(1000, 1000 + 128))  # deterministic pseudo-prompt ids

    ref = decode(rt, checkpoint_dir=CKPT, prompt_token_ids=list(prompt), max_new_tokens=N_OUT)
    ref_gen = ref.token_ids[len(prompt):]
    print(f"single-stream: {N_OUT} tokens, decode={ref.decode_tokens_per_sec:.1f} tok/s")
    print(f"  first 8: {ref_gen[:8]}")

    res = decode_batched(
        rt, checkpoint_dir=CKPT, prompt_token_ids_list=[list(prompt) for _ in range(B)],
        max_new_tokens=N_OUT,
    )
    print(
        f"batched B={B}: system decode={res.decode_tokens_per_sec:.1f} tok/s, "
        f"prefill={res.prefill_tokens_per_sec:.0f} tok/s, "
        f"dispatches/token={res.dispatches_per_token}"
    )
    ok = True
    for b in range(B):
        gen = res.generated_token_ids[b]
        if len(gen) != N_OUT:
            print(f"  seq {b}: WRONG LENGTH {len(gen)}")
            ok = False
            continue
        if gen != ref_gen:
            first_diff = next(i for i, (a, c) in enumerate(zip(gen, ref_gen)) if a != c)
            print(f"  seq {b}: MISMATCH, first diff at index {first_diff}")
            print(f"    batched: {gen[:8]}")
            print(f"    ref    : {ref_gen[:8]}")
            ok = False
        else:
            print(f"  seq {b}: byte-identical to single-stream ({N_OUT} tokens)")
    if not ok:
        print("SMOKE FAILED")
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
