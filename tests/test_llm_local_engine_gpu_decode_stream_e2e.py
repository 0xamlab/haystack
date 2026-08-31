"""Real-GPU proof for Track C3 (token-by-token streaming): `algenta.inference.decode_stream()`
against the rebuilt Metal GPU worker binary. Skip-unless-present, mirroring
`tests/test_llm_local_engine_gpu_e2e.py`'s own pattern exactly: needs the GPU worker binary and a
real Qwen3-0.6B-Base checkpoint. `decode()` itself is never modified by this change -- these tests
prove `decode_stream()` reproduces its exact token sequence, not that `decode()` changed.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

_WORKER = ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker"
_CHECKPOINT = Path(os.environ.get("ALGENTA_QWEN3_TEST_CHECKPOINT", "/private/tmp/qwen3-0.6b-base"))

pytestmark = pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)


@pytest.fixture(autouse=True)
def _worker_env(monkeypatch):
    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", str(_WORKER))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    yield
    from algenta.native import worker

    worker.shutdown()


def test_decode_stream_is_byte_identical_to_decode_greedy() -> None:
    """THE single most important correctness proof for this whole change: for a fixed real
    prompt, fixed max_new_tokens, temperature=0 (greedy, deterministic), the EXISTING, completely
    untouched `decode()` and the NEW `decode_stream()` must produce the EXACT SAME token_ids,
    element for element."""
    from algenta import MojoRuntime
    from algenta.inference import decode, decode_stream

    runtime = MojoRuntime(mode="local", timeout=600.0)
    prompt_text = "The capital of France is"
    max_new_tokens = 10

    one_shot = decode(
        runtime,
        checkpoint_dir=_CHECKPOINT,
        prompt_text=prompt_text,
        max_new_tokens=max_new_tokens,
        temperature=0.0,
    )
    one_shot_generated = one_shot.token_ids[one_shot.n_prompt :]
    assert len(one_shot_generated) == max_new_tokens
    print(f"\n[decode() one-shot]      n_prompt={one_shot.n_prompt} generated={one_shot_generated}")
    print(f"[decode() generated_text] {one_shot.generated_text!r}")

    streamed_tokens: list[int] = []
    streamed_deltas: list[str] = []
    for step in decode_stream(
        checkpoint_dir=_CHECKPOINT,
        prompt_text=prompt_text,
        max_new_tokens=max_new_tokens,
        temperature=0.0,
    ):
        streamed_tokens.append(step.token_id)
        streamed_deltas.append(step.text_delta or "")
    print(f"[decode_stream() streamed] generated={streamed_tokens}")
    print(f"[decode_stream() deltas]   {streamed_deltas}")

    assert len(streamed_tokens) == max_new_tokens, (
        f"decode_stream() yielded {len(streamed_tokens)} tokens, expected {max_new_tokens}"
    )
    assert streamed_tokens == one_shot_generated, (
        "STREAMING PRODUCED A DIFFERENT GENERATION THAN decode() -- a real correctness regression.\n"
        f"decode():        {one_shot_generated}\n"
        f"decode_stream(): {streamed_tokens}"
    )
    assert "".join(streamed_deltas) == one_shot.generated_text


def test_decode_stream_tokens_arrive_progressively_not_all_at_once() -> None:
    """Real incremental-delivery proof: timestamp each yield and show tokens do not all land in
    one final burst -- i.e. this is REAL streaming, not one-shot generation with the delivery
    faked to look incremental."""
    from algenta.inference import decode_stream

    gaps: list[float] = []
    last = time.perf_counter()
    n = 0
    for _step in decode_stream(
        checkpoint_dir=_CHECKPOINT,
        prompt_text="The largest planet in the solar system is",
        max_new_tokens=8,
        temperature=0.0,
    ):
        now = time.perf_counter()
        gaps.append(now - last)
        last = now
        n += 1
    print(f"\n[incremental timing] per-yield wall-clock gaps (s): {[round(g, 4) for g in gaps]}")
    assert n == 8
    # Every yield after the first involves a real `.step()` dispatch through the wire protocol --
    # a non-trivial, measurable amount of real wall-clock time each, not zero (which would mean
    # every token was actually ready before the first yield and delivery was merely staggered).
    assert all(g > 0.0005 for g in gaps[1:]), gaps


def test_decode_stream_abandonment_releases_the_gpu_session() -> None:
    """The real resource-safety proof (step 6/7d): start consuming, stop after 2 tokens WITHOUT
    exhausting the generator, confirm the abandoned session was actually released -- proven by a
    fresh session opening and generating correctly right afterward. This is a sensitive proof: the
    Mojo-side registry refuses a second `qwen3_decode_open` while ANY session is still tracked as
    open on this connection (`qwen3_session_already_open`), so if the abandoned session's `close`
    never ran, the second open below would fail outright."""
    from algenta.inference import decode_stream

    gen = decode_stream(
        checkpoint_dir=_CHECKPOINT,
        prompt_text="The chemical symbol for gold is",
        max_new_tokens=8,
        temperature=0.0,
    )
    first_two = [next(gen).token_id, next(gen).token_id]
    print(f"\n[abandonment] consumed 2 of 8 tokens: {first_two}")
    gen.close()  # deterministic -- runs the generator's `finally` block synchronously, right now,
    # rather than relying on unpredictable GC timing to prove the cleanup path at all.

    # A second, independent, FULL session on the very next call. If the abandoned session had
    # leaked (its close_from_json never ran), this open would raise
    # Qwen3DecodeSessionError("qwen3_session_already_open", ...) instead of succeeding.
    second_tokens = [
        step.token_id
        for step in decode_stream(
            checkpoint_dir=_CHECKPOINT,
            prompt_text="The chemical symbol for gold is",
            max_new_tokens=8,
            temperature=0.0,
        )
    ]
    print(f"[abandonment] second (fresh) session generated: {second_tokens}")
    assert len(second_tokens) == 8
    # Determinism check for free: same prompt, greedy, so the second session's tokens should
    # start with the SAME first two tokens the abandoned session already produced.
    assert second_tokens[:2] == first_two


def test_decode_stream_abandonment_via_garbage_collection() -> None:
    """Same proof as above, but through the path a real caller is most likely to actually hit:
    the generator is simply dropped (an HTTP handler returning early, a `for` loop `break`) and
    Python's own refcounting/GC closes it -- never an explicit `.close()` call."""
    import gc

    from algenta.inference import decode_stream

    def _abandon_after_two() -> list[int]:
        collected = []
        for step in decode_stream(
            checkpoint_dir=_CHECKPOINT,
            prompt_text="The tallest mountain on Earth is",
            max_new_tokens=8,
            temperature=0.0,
        ):
            collected.append(step.token_id)
            if len(collected) == 2:
                break  # the generator object goes out of scope right after this function returns
        return collected

    first_two = _abandon_after_two()
    gc.collect()  # force the now-unreferenced generator's __del__ / GeneratorExit path to run
    print(f"\n[gc abandonment] consumed 2 of 8 tokens via break: {first_two}")

    second_tokens = [
        step.token_id
        for step in decode_stream(
            checkpoint_dir=_CHECKPOINT,
            prompt_text="The tallest mountain on Earth is",
            max_new_tokens=8,
            temperature=0.0,
        )
    ]
    print(f"[gc abandonment] second (fresh) session generated: {second_tokens}")
    assert len(second_tokens) == 8
    assert second_tokens[:2] == first_two


def test_decode_stream_multiple_sequential_sessions_in_a_row() -> None:
    """Rules out a registry/handle-reuse bug: open/generate/close, then immediately open another,
    three times in a row, same connection, asserting each session's own handle-scoped generation
    is correct and independent."""
    from algenta.inference import decode_stream

    prompts = [
        "The speed of light is approximately",
        "Water boils at a temperature of",
        "The author of Romeo and Juliet is",
    ]
    all_runs: list[list[int]] = []
    for prompt in prompts:
        tokens = [
            step.token_id
            for step in decode_stream(
                checkpoint_dir=_CHECKPOINT, prompt_text=prompt, max_new_tokens=6, temperature=0.0
            )
        ]
        assert len(tokens) == 6
        all_runs.append(tokens)
        print(f"[sequential sessions] {prompt!r} -> {tokens}")

    # Three different prompts is very unlikely to produce three identical 6-token generations by
    # chance -- a real registry/handle-reuse bug (e.g. session B silently reading session A's
    # stale KV cache) would tend to show up as suspiciously repeated output across runs.
    assert len({tuple(run) for run in all_runs}) == len(prompts)


def test_decode_stream_rejects_sampling() -> None:
    from algenta.inference import InferenceError, decode_stream

    with pytest.raises(InferenceError) as exc_info:
        next(
            decode_stream(
                checkpoint_dir=_CHECKPOINT,
                prompt_text="The capital of France is",
                max_new_tokens=4,
                temperature=0.7,
            )
        )
    assert exc_info.value.code == "sampling_not_supported_in_stream"


def test_decode_stream_unknown_session_handle_fails_cleanly() -> None:
    """Direct wire-level proof that a stale/unknown handle on next/close is a clean, named error,
    never a crash -- exercised through the same rebuilt worker binary the other tests use."""
    from algenta.qwen3_decode_session import Qwen3DecodeSessionError, step_qwen3_decode_session

    with pytest.raises(Qwen3DecodeSessionError) as exc_info:
        step_qwen3_decode_session(
            "qd_this_handle_was_never_opened",
            routing_module="metaldispatch.qwen3_prefill_decode",
            timeout=30.0,
            require_verified=False,
        )
    assert exc_info.value.code == "qwen3_session_not_found"
