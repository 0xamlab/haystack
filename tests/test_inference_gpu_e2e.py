"""End-to-end proof for `algenta.inference.decode` on the REAL GPU worker -- the beat-llama.cpp
campaign's parity cheap win "route the SDK to the existing anyqwen3 arm" (2026-08-09/10).

`tests/test_inference_model_agnostic.py` covers everything this module needs a GPU for nothing of:
architecture validation and multi-shard checkpoint conversion. This file covers the rest of the
wire -- SDK `decode()` -> `MojoRuntime` -> runtime worker -> `metaldispatch.qwen3_prefill_decode.
qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3` -> Metal GPU -> greedy tokens checked against
the campaign's known-correct oracle (first generated token 374 for the 256-token race prompt on
BOTH Qwen3-0.6B-Base and Qwen3-1.7B, established by every oracle gate that campaign ran).

Everything here is opt-in, not a hard CI requirement. It needs, per model:
  * a GPU worker binary built with `-D ALGENTA_GPU` + the campaign's Metal blobs linked (the
    3072-tier default for 0.6B, `-D ALGENTA_STAGE_6144` for 1.7B -- per-model staging is a
    build-time specialization, see `residentk/contract.mojo`'s `RESIDENT_MAX_D_MODEL`),
  * the matching HuggingFace checkpoint snapshot on disk (the README-documented manual download),
  * a converted `manifest.json` + `weights.blob` pair for the 256-token race prompt.
Each test is skipped -- never failed -- when its own prerequisites are absent, the same convention
`test_qwen3_decode_checkpoint_conversion.py` established. The dev-machine paths below are exactly
the ones the campaign itself used; override any of them with the `ALGENTA_*` environment names
each helper reads.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.inference import InferenceError, decode  # noqa: E402

# The campaign's race prompt, tokenized with the Qwen3 tokenizer family (identical ids for both
# models -- same 151,936-vocab tokenizer). "The capital of France is Paris. " * 36 + a trailing
# clause; the exact ids are read from whichever converted manifest the run uses, never restated
# here (a second literal would be a second thing to keep in sync).
_RACE_PROMPT_TOKEN_COUNT = 256
_ORACLE_FIRST_TOKEN = 374
_ORACLE_CONTINUATION = [374, 12095, 13, 576, 6722, 315, 9625, 374]


def _worker_binary(env_name: str, default: Path) -> Path | None:
    override = os.environ.get(env_name)
    path = Path(override) if override else default
    return path if path.is_file() and os.access(path, os.X_OK) else None


def _gpu_worker() -> Path | None:
    return _worker_binary(
        "ALGENTA_GPU_WORKER", ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker"
    )


def _gpu_worker_stage6144() -> Path | None:
    return _worker_binary(
        "ALGENTA_GPU_WORKER_STAGE6144",
        ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker-stage6144",
    )


def _converted_dir(env_name: str, default: Path) -> Path | None:
    override = os.environ.get(env_name)
    path = Path(override) if override else default
    if (path / "manifest.json").is_file() and (path / "weights.blob").is_file():
        return path
    return None


def _checkpoint_dir(env_name: str, default: Path) -> Path | None:
    override = os.environ.get(env_name)
    path = Path(override) if override else default
    return path if (path / "config.json").is_file() else None


def _runtime(worker: Path):
    # Dev worker binaries are not the signed bundled runtime; the permissive resolver is the
    # documented dev knob (release builds stay fail-closed -- the default is untouched here).
    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(worker)
    from algenta import MojoRuntime

    return MojoRuntime(mode="local", timeout=600.0)


def _race_prompt_ids(converted_dir: Path) -> list[int]:
    manifest = json.loads((converted_dir / "manifest.json").read_text(encoding="utf-8"))
    ids = list(manifest["input_ids"])
    assert manifest["config"]["n_tokens"] == len(ids) == _RACE_PROMPT_TOKEN_COUNT
    return ids


def test_max_ctx_guard_refuses_below_need_without_any_runtime(tmp_path: Path) -> None:
    """Client-side, no worker, no real checkpoint: `max_ctx` below `n_prompt + max_new_tokens` is
    refused before any wire call -- the guard half of the cheap-win-3 contract (the engine's own
    auto-raise half is exercised by the GPU tests). The converted-dir stub only needs the two file
    NAMES to exist: decode()'s existence check runs before the guard, and the guard fires before
    either file is ever read."""
    converted = tmp_path / "converted"
    converted.mkdir()
    (converted / "manifest.json").write_text("{}", encoding="utf-8")
    (converted / "weights.blob").write_bytes(b"")
    with pytest.raises(InferenceError) as excinfo:
        decode(
            object(),  # never reached -- the guard refuses first
            checkpoint_dir="/nonexistent",
            prompt_token_ids=[785, 6722, 315],
            max_new_tokens=4,
            max_ctx=6,  # needs 3 + 4 = 7
            converted_checkpoint_dir=converted,
        )
    assert excinfo.value.code == "invalid_arguments"
    assert "below the 7 context" in str(excinfo.value)


def test_converted_dir_missing_files_refused_without_any_runtime() -> None:
    with pytest.raises(InferenceError) as excinfo:
        decode(
            object(),
            checkpoint_dir="/nonexistent",
            prompt_token_ids=[785],
            max_new_tokens=1,
            converted_checkpoint_dir="/nonexistent-converted-dir",
        )
    assert excinfo.value.code == "checkpoint_not_found"


@pytest.mark.skipif(
    _gpu_worker() is None
    or _converted_dir("ALGENTA_QWEN3_CONVERTED_06B", Path("/tmp/qwen3smoke")) is None
    or _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base"))
    is None,
    reason=(
        "needs the 3072-tier GPU worker (mojo_build/gpu-worker/algenta-gpu-worker), the "
        "Qwen3-0.6B-Base snapshot, and a converted race-prompt checkpoint; this is the campaign "
        "dev machine's e2e gate, never built or downloaded by a test"
    ),
)
def test_sdk_decode_06b_matches_campaign_oracle() -> None:
    """First-ever SDK -> runtime-worker -> Metal GPU decode of Qwen3-0.6B-Base through the
    model-agnostic anyqwen3 arm: 256-token race prompt, 8 greedy tokens, checked against the
    campaign oracle (first token 374 and the exact known continuation)."""
    worker = _gpu_worker()
    converted = _converted_dir("ALGENTA_QWEN3_CONVERTED_06B", Path("/tmp/qwen3smoke"))
    checkpoint = _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base"))
    prompt_ids = _race_prompt_ids(converted)

    result = decode(
        _runtime(worker),
        checkpoint_dir=checkpoint,
        prompt_token_ids=prompt_ids,
        max_new_tokens=8,
        converted_checkpoint_dir=converted,
    )

    assert result.n_prompt == _RACE_PROMPT_TOKEN_COUNT
    assert len(result.token_ids) == _RACE_PROMPT_TOKEN_COUNT + 8
    assert result.token_ids[:_RACE_PROMPT_TOKEN_COUNT] == prompt_ids
    assert result.token_ids[_RACE_PROMPT_TOKEN_COUNT] == _ORACLE_FIRST_TOKEN
    assert result.token_ids[_RACE_PROMPT_TOKEN_COUNT:] == _ORACLE_CONTINUATION
    assert not result.stopped_on_eos
    # Campaign bands: cold first prefill lands well under the warm resident rate but far above
    # anything CPU-shaped; decode sits in the long-established 250-280 tok/s single-stream band.
    assert result.prefill_tokens_per_sec > 1000.0
    assert 200.0 < result.decode_tokens_per_sec < 330.0
    assert result.dispatches_per_token > 0


@pytest.mark.skipif(
    _gpu_worker() is None
    or _converted_dir("ALGENTA_QWEN3_CONVERTED_06B", Path("/tmp/qwen3smoke")) is None
    or _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base"))
    is None,
    reason="same prerequisites as test_sdk_decode_06b_matches_campaign_oracle",
)
def test_sdk_decode_06b_long_generation_past_512_context() -> None:
    """The any-token-amount gate: 600 NEW tokens off the 256-token race prompt (total context 856,
    past the 512 default and deep into the split-K decode regime), and every one of them must stay
    on the model's exact repeating continuation -- a drift or a budget mismatch (the entry point
    asserts its dispatch budget EVERY step and returns an error instead of tokens on disagreement)
    fails this test. The 2048-token soak numbers live in REALRACE_RESULTS.md's cheap-wins entry;
    this test keeps the permanent gate at 600 so the suite stays under a minute."""
    worker = _gpu_worker()
    converted = _converted_dir("ALGENTA_QWEN3_CONVERTED_06B", Path("/tmp/qwen3smoke"))
    checkpoint = _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base"))
    prompt_ids = _race_prompt_ids(converted)

    result = decode(
        _runtime(worker),
        checkpoint_dir=checkpoint,
        prompt_token_ids=prompt_ids,
        max_new_tokens=600,
        converted_checkpoint_dir=converted,
    )

    assert result.n_prompt == _RACE_PROMPT_TOKEN_COUNT
    assert len(result.token_ids) == _RACE_PROMPT_TOKEN_COUNT + 600
    assert result.token_ids[_RACE_PROMPT_TOKEN_COUNT] == _ORACLE_FIRST_TOKEN
    # The generation is the model repeating "Paris.\nThe capital of France is" forever: token 0 is
    # 374 ("is"), then a 7-token cycle [12095, 13, 576, 6722, 315, 9625, 374] ("Paris . The capital
    # of France is") -- the 8-token oracle window shows "is" twice because it wraps that cycle
    # boundary. Every one of the 600 tokens must sit exactly on that cycle; the 2048-token soak in
    # REALRACE_RESULTS.md's cheap-wins entry was verified against the same invariant.
    cycle = _ORACLE_CONTINUATION[1:]  # [12095, 13, 576, 6722, 315, 9625, 374]
    assert len(cycle) == 7
    generated = result.token_ids[_RACE_PROMPT_TOKEN_COUNT :]
    for position, token in enumerate(generated[1:], start=1):
        assert token == cycle[(position - 1) % len(cycle)], (
            f"long-gen drift at generated token {position}: {token}"
        )
    assert not result.stopped_on_eos


@pytest.mark.skipif(
    _gpu_worker() is None
    or _converted_dir("ALGENTA_QWEN3_CONVERTED_06B", Path("/tmp/qwen3smoke")) is None
    or _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base"))
    is None,
    reason="same prerequisites as test_sdk_decode_06b_matches_campaign_oracle",
)
def test_sdk_decode_06b_quantized_cache_token_identical() -> None:
    """Cheap win 2 (2026-08-10): the anyqwen3 arm persists the EXACT post-quantization device
    bytes to `weights_i8.cache` on the first call and restores them on the second -- skipping the
    f64 blob read and the quantization pass. What this test asserts is the only part that is not
    allowed to change: three consecutive decodes (f64 path writing the cache, cache path reading
    it, then a deliberately CORRUPTED cache falling honestly back to the f64 path) must produce
    the SAME greedy token sequence, oracle first token included."""
    worker = _gpu_worker()
    converted = _converted_dir("ALGENTA_QWEN3_CONVERTED_06B", Path("/tmp/qwen3smoke"))
    checkpoint = _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base"))
    prompt_ids = _race_prompt_ids(converted)
    cache_path = converted / "weights_i8.cache"
    cache_path.unlink(missing_ok=True)

    runtime = _runtime(worker)

    def _run() -> tuple[list[int], Path | None]:
        result = decode(
            runtime,
            checkpoint_dir=checkpoint,
            prompt_token_ids=prompt_ids,
            max_new_tokens=8,
            converted_checkpoint_dir=converted,
        )
        return result.token_ids, cache_path if cache_path.is_file() else None

    cold_tokens, cache_after_cold = _run()
    assert cold_tokens[_RACE_PROMPT_TOKEN_COUNT] == _ORACLE_FIRST_TOKEN
    assert cache_after_cold is not None, "the f64 path did not write weights_i8.cache"
    # ~1 byte/param + scales for 0.6B lands near 600 MB -- assert the ballpark, not the exact
    # count (the exact one is quantized_state_bytes's own arithmetic, already length-gated by the
    # loader).
    assert cache_path.stat().st_size > 500_000_000

    cached_tokens, _ = _run()
    assert cached_tokens == cold_tokens, "the cache path changed the greedy sequence"

    # Corrupt the validity gate (flip a byte inside the stored manifest SHA-256) -- the entry
    # point must refuse the cache and fall back to the f64 path, which rewrites a valid cache.
    raw = bytearray(cache_path.read_bytes())
    raw[10] ^= 0xFF
    cache_path.write_bytes(bytes(raw))
    fallback_tokens, cache_after_fallback = _run()
    assert fallback_tokens == cold_tokens, "the corrupted-cache fallback changed the sequence"
    assert cache_after_fallback is not None, "the fallback path did not rewrite the cache"
    assert cache_path.read_bytes() != bytes(raw), "the fallback left the corrupted cache in place"


@pytest.mark.skipif(
    _gpu_worker_stage6144() is None
    or _converted_dir("ALGENTA_QWEN3_CONVERTED_17B", Path("/tmp/qwen3smoke_17b")) is None
    or _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT_17B", Path("/private/tmp/qwen3-1.7b"))
    is None,
    reason=(
        "needs the ALGENTA_STAGE_6144-tier GPU worker (mojo_build/gpu-worker/"
        "algenta-gpu-worker-stage6144), the Qwen3-1.7B snapshot, and a converted race-prompt "
        "checkpoint; per-model staging is a build-time specialization (residentk/contract.mojo)"
    ),
)
def test_sdk_decode_17b_matches_campaign_oracle() -> None:
    """The model-agnostic proof: the SAME SDK call shape decodes Qwen3-1.7B (hidden 2048 / d_ff
    6144, 28 layers, two-shard checkpoint) through the 6144-tier worker, matching the same oracle
    first token the campaign's model-agnostic verification recorded on 2026-08-09."""
    worker = _gpu_worker_stage6144()
    converted = _converted_dir("ALGENTA_QWEN3_CONVERTED_17B", Path("/tmp/qwen3smoke_17b"))
    checkpoint = _checkpoint_dir("ALGENTA_QWEN3_TEST_CHECKPOINT_17B", Path("/private/tmp/qwen3-1.7b"))
    prompt_ids = _race_prompt_ids(converted)

    result = decode(
        _runtime(worker),
        checkpoint_dir=checkpoint,
        prompt_token_ids=prompt_ids,
        max_new_tokens=8,
        converted_checkpoint_dir=converted,
    )

    assert result.n_prompt == _RACE_PROMPT_TOKEN_COUNT
    assert len(result.token_ids) == _RACE_PROMPT_TOKEN_COUNT + 8
    assert result.token_ids[_RACE_PROMPT_TOKEN_COUNT] == _ORACLE_FIRST_TOKEN
    assert not result.stopped_on_eos
    assert result.prefill_tokens_per_sec > 500.0
    assert result.decode_tokens_per_sec > 50.0
    assert result.dispatches_per_token > 0
