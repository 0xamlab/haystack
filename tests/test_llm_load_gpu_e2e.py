"""End-to-end gate for the enterprise load/stress harness (`benchmarks/llm_smoke/load_test.py`,
2026-08-10). The harness measures large-token prefill/decode and concurrent-request behavior on the
REAL Metal GPU worker; this test keeps a small, fast slice of it permanently green so a regression
in the decode path (correctness or a gross throughput collapse) is caught here, while the full
matrix runs as the on-demand measurement the harness is. Skip-unless-present like the other GPU
gates: needs the GPU worker binary and the Qwen3-0.6B-Base snapshot.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))
_BENCH = ROOT / "benchmarks" / "llm_smoke"
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))

_WORKER = ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker"
_CHECKPOINT = Path(os.environ.get("ALGENTA_QWEN3_TEST_CHECKPOINT", "/private/tmp/qwen3-0.6b-base"))


@pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)
def test_load_harness_stress_correctness_and_throughput() -> None:
    """The stress lane's honesty gate on small cells: greedy determinism + valid-token range must
    hold, and single-stream decode must stay in a sane band (a collapse would be a real engine
    regression, not measurement noise)."""
    import load_test as lt
    from algenta import MojoRuntime
    from algenta.tokenizer import load_tokenizer

    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(_WORKER)

    tokenizer = load_tokenizer(_CHECKPOINT)
    runtime = MojoRuntime(mode="local", timeout=600.0)

    # Warmup so the timed cells measure serving, not first-load.
    lt.decode_once(runtime, str(_CHECKPOINT), lt.build_prompt_ids(tokenizer, 64), 4)

    for n_in, n_out in ((256, 64), (512, 128)):
        prompt_ids = lt.build_prompt_ids(tokenizer, n_in)
        wall_a, result_a = lt.decode_once(runtime, str(_CHECKPOINT), prompt_ids, n_out)
        wall_b, result_b = lt.decode_once(runtime, str(_CHECKPOINT), prompt_ids, n_out)
        gen_a = result_a.token_ids[result_a.n_prompt :]
        gen_b = result_b.token_ids[result_b.n_prompt :]
        ok, why = lt.correctness_ok(tokenizer.vocab_size, gen_a, gen_b)
        assert ok, f"in={n_in} out={n_out}: {why}"
        assert len(gen_a) == n_out
        # Conservative floors: short-context single-stream decode on 0.6B sits ~250-280 tok/s;
        # anything far below this is a regression, not noise.
        assert result_a.decode_tokens_per_sec > 100.0, result_a.decode_tokens_per_sec
        assert result_a.prefill_tokens_per_sec > 1000.0, result_a.prefill_tokens_per_sec
        assert wall_a > 0.0 and wall_b > 0.0


@pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)
def test_load_harness_concurrent_no_errors() -> None:
    """Concurrent requests against the shared resident worker must all complete without error. The
    single-stream engine serializes them (documented), so this asserts liveness + determinism under
    queueing, not parallel speedup."""
    import threading

    import load_test as lt
    from algenta import MojoRuntime
    from algenta.tokenizer import load_tokenizer

    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(_WORKER)

    tokenizer = load_tokenizer(_CHECKPOINT)
    runtime = MojoRuntime(mode="local", timeout=600.0)
    lt.decode_once(runtime, str(_CHECKPOINT), lt.build_prompt_ids(tokenizer, 64), 4)  # warmup

    prompt_ids = lt.build_prompt_ids(tokenizer, 256)
    n = 3
    results: list = [None] * n

    def worker(i: int) -> None:
        results[i] = lt.decode_once(runtime, str(_CHECKPOINT), prompt_ids, 32)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r is not None for r in results), "a concurrent request failed"
    # Serialized: all requests see the same prompt + greedy params, so all outputs must be identical.
    first = results[0][1].token_ids
    for _, r in results[1:]:
        assert r.token_ids == first, "concurrent greedy outputs diverged"
