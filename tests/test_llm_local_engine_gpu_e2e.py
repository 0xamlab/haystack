"""End-to-end proof for the `algenta_local` provider backend (parity gap 2, 2026-08-10):
registry entry -> descriptor -> create_chat_completion -> local executor -> algenta SDK -> the
real Metal GPU worker -> generated text back through the service shape. Skip-unless-present like
the other GPU gates: needs the GPU worker binary, the Qwen3-0.6B-Base snapshot, and the race
checkpoint's model directory. The first run converts the checkpoint (~1 min); runs after that
reuse nothing (one-shot shape) but stay well under the timeout."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

_WORKER = ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker"
_CHECKPOINT = Path(os.environ.get("ALGENTA_QWEN3_TEST_CHECKPOINT", "/private/tmp/qwen3-0.6b-base"))


@pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)
def test_local_backend_chat_completion_through_real_gpu(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.algenta_local",
                    "backend": "algenta_local",
                    "model_name": "qwen3-0.6b-base",
                    "capabilities": ["chat_completions"],
                }
            ]
        ),
    )
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON",
        json.dumps({"qwen3-0.6b-base": str(_CHECKPOINT)}),
    )
    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", str(_WORKER))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")

    from apps.api_server.services import llm_api_service
    from apps.api_server.services import llm_provider_service
    from apps.api_server.services.llm_provider_service import _executors_local

    llm_provider_service.load_provider_model_configs.cache_clear()
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    try:
        descriptor = llm_api_service.get_llm_model_descriptor("provider.algenta_local")
        assert descriptor.provider_backend == "algenta_local"
        assert "chat_completions" in descriptor.capabilities
        assert "/v1/chat/completions" in descriptor.supported_endpoints

        descriptor, completion = asyncio.run(
            llm_api_service.create_chat_completion(
                model_id="provider.algenta_local",
                messages=[{"role": "user", "content": "The capital of France is"}],
                max_output_tokens=8,
            )
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    assert completion.provider.provider_backend == "algenta_local"
    assert completion.prompt_tokens == 5  # "The capital of France is" in the Qwen3 tokenizer
    assert completion.completion_tokens == 8
    # Greedy is deterministic: the first generated token after "...France is" is always " Paris"
    # (id 12095). What follows is the model's own encyclopedic continuation (this short prompt
    # does not force the race prompt's repetitive pattern), so only the start is pinned.
    assert completion.content.startswith(" Paris."), repr(completion.content)
    assert len(completion.content) > len(" Paris.")


@pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)
def test_local_backend_second_prompt_reuses_conversion_and_quantized_caches(monkeypatch) -> None:
    """The serving shape: the prompt travels separately from the converted weights, so ONE
    conversion per checkpoint serves every prompt. First call converts (~seconds) and writes
    `.algenta-cache/` (with `weights_i8.cache` inside it); a second call with a DIFFERENT prompt
    reuses both caches and must complete far faster -- and answer ITS prompt, not the first
    one's."""
    import shutil
    import time

    from algenta import MojoRuntime
    from algenta.inference import decode

    cache_dir = _CHECKPOINT / ".algenta-cache"
    shutil.rmtree(cache_dir, ignore_errors=True)
    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", str(_WORKER))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")

    runtime = MojoRuntime(mode="local", timeout=600.0)

    t0 = time.time()
    first = decode(
        runtime,
        checkpoint_dir=_CHECKPOINT,
        prompt_text="The capital of France is",
        max_new_tokens=8,
    )
    cold_wall = time.time() - t0

    assert (cache_dir / "manifest.json").is_file()
    assert (cache_dir / "weights.blob").is_file()
    assert (cache_dir / "weights_i8.cache").is_file()

    t0 = time.time()
    second = decode(
        runtime,
        checkpoint_dir=_CHECKPOINT,
        prompt_text="The largest planet in the solar system is",
        max_new_tokens=8,
    )
    cached_wall = time.time() - t0

    assert first.generated_text.startswith(" Paris."), repr(first.generated_text)
    # Different prompt, different answer -- the cache serves weights, not answers.
    assert "Jupiter" in second.generated_text, repr(second.generated_text)
    assert cached_wall * 2 < cold_wall, (
        f"the cached second call ({cached_wall:.2f}s) was not clearly faster than the cold "
        f"first call ({cold_wall:.2f}s)"
    )
