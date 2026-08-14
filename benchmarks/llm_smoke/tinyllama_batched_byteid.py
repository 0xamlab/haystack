"""feat/batched-llama (2026-08-14): the TinyLlama batched-vs-single-stream BYTE-IDENTITY gate.

Runs `algenta.inference.decode_batched` (the Slipstream continuous-batching tier, now generalized
to llama d_head=64 / qk_norm=0) at B=2 and B=4 and verifies every sequence's generated tokens are
BYTE-IDENTICAL to that same prompt's own single-stream `decode()` output on the SAME worker. This
is the acceptance gate for batched llama serving (Qwen3's own gate was token-identity at B=4 x24
steps; this harness makes the comparison direct per sequence).

Prompt lengths deliberately straddle the single-stream split-K threshold (128 keys): shallow
prompts run single-stream decode on the naive native table while the batched path always runs the
bf2u2 partial + merge; a deep prompt (>128 keys) runs single-stream on the f2s4 split-K table --
both regimes must stay token-identical to the batched path.

Usage (llama-aware STAGE_6144 worker with the batched blobs linked, built from THIS tree):

    ALGENTA_NATIVE_WORKER=$PWD/mojo_build/gpu-worker/algenta-gpu-worker-batchedllama \\
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \\
      scripts/run_repo_python.sh benchmarks/llm_smoke/tinyllama_batched_byteid.py

Exit code 0 iff every batched sequence is byte-identical to its single-stream twin. Skip-style
exit 77 when the checkpoint or worker is absent (there is nothing to gate on).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode, decode_batched  # noqa: E402

CHECKPOINT = Path(os.environ.get("ALGENTA_TINYLLAMA_DIR", "/private/tmp/tinyllama"))
WORKER = Path(
    os.environ.get(
        "ALGENTA_NATIVE_WORKER",
        str(ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker-batchedllama"),
    )
)
MAX_NEW = 32


def main() -> int:
    if not (CHECKPOINT / "config.json").is_file():
        print(f"SKIP: TinyLlama checkpoint absent at {CHECKPOINT}")
        return 77
    if not WORKER.is_file():
        print(f"SKIP: worker binary absent at {WORKER}")
        return 77

    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    os.environ["ALGENTA_NATIVE_WORKER"] = str(WORKER)
    runtime = MojoRuntime(mode="local", timeout=600.0)

    # Short prompts stay below the single-stream split-K threshold (128 keys); the deep prompts
    # cross it MID-GENERATION (170-token prompt + 32 generated -> 202 keys: single-stream
    # switches to its f2s4 split-K table while the batched path runs bf2u2 throughout).
    deep = ("The capital of Germany is Berlin. The capital of France is Paris. " * 12).strip()
    prompts = {
        "germany": "The capital of Germany is",
        "france": "The capital of France is",
        "deep": deep,
        "deep2": deep.replace("Germany", "Spain").replace("Berlin", "Madrid"),
    }

    single_gen: dict[str, list[int]] = {}
    single_ids: dict[str, list[int]] = {}
    for name, text in prompts.items():
        t0 = time.perf_counter()
        res = decode(
            runtime,
            checkpoint_dir=CHECKPOINT,
            prompt_text=text,
            max_new_tokens=MAX_NEW,
        )
        gen = list(res.token_ids[res.n_prompt :])
        single_gen[name] = gen
        single_ids[name] = [int(t) for t in res.token_ids[: res.n_prompt]]
        print(
            f"single-stream {name}: {len(gen)} tokens ({res.n_prompt}-tok prompt) in "
            f"{time.perf_counter() - t0:.2f}s stopped_on_eos={res.stopped_on_eos} "
            f"first={gen[:6]}"
        )
        if res.stopped_on_eos or len(gen) != MAX_NEW:
            print(f"FAIL: single-stream {name} stopped early; pick a prompt with no EOS in-horizon")
            return 1

    failures = 0

    def check_batch(label: str, names: list[str]) -> None:
        nonlocal failures
        t0 = time.perf_counter()
        res = decode_batched(
            runtime,
            checkpoint_dir=CHECKPOINT,
            prompt_token_ids_list=[single_ids[n] for n in names],
            max_new_tokens=MAX_NEW,
        )
        wall = time.perf_counter() - t0
        print(
            f"batched {label}: B={len(names)} system {res.decode_tokens_per_sec:.1f} tok/s "
            f"prefill {res.prefill_tokens_per_sec:.1f} tok/s wall {wall:.2f}s "
            f"dispatches/token {res.dispatches_per_token}"
        )
        for i, name in enumerate(names):
            got = list(res.generated_token_ids[i])
            want = single_gen[name]
            if got == want:
                print(f"  seq {i} ({name}): BYTE-IDENTICAL ({len(got)} tokens)")
            else:
                failures += 1
                diverge = next(
                    (k for k in range(min(len(got), len(want))) if got[k] != want[k]),
                    min(len(got), len(want)),
                )
                print(
                    f"  seq {i} ({name}): DIVERGED at token {diverge}: "
                    f"batched {got[diverge : diverge + 4]} vs single {want[diverge : diverge + 4]}"
                )

    check_batch("B=2 shallow+deep", ["germany", "deep"])
    check_batch("B=2 identical twins", ["germany", "germany"])
    check_batch("B=4 mixed depths", ["germany", "france", "deep", "deep2"])
    check_batch(
        "B=8 mixed depths",
        ["germany", "france", "deep", "deep2", "germany", "france", "deep", "deep2"],
    )

    if failures:
        print(f"FAIL: {failures} batched sequence(s) diverged from single-stream")
        return 1
    print("PASS: every batched sequence byte-identical to its single-stream twin")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:  # noqa: BLE001 -- debug aid: keep the worker log alive briefly
        print(f"ERROR: {exc!r}")
        time.sleep(3)
        raise
    raise SystemExit(code)
