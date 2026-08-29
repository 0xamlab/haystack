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
    """Realistic chat-completions serving: the request's messages are formatted with the
    checkpoint's OWN chat template before reaching the GPU (parity with llama-server), not
    flattened. We assert the prompt that hit the engine is EXACTLY the template-formatted +
    tokenized messages (a count derived from the oracle-validated `algenta.chat_template` +
    `algenta.tokenizer`, not a magic number) and that the GPU generated the requested tokens.

    NOTE on the assertion shape: the checkpoint under test is a BASE model, which is not
    instruction-tuned, so it does not answer a chat prompt -- it continues text. Asserting a
    specific answer (e.g. " Paris.") would therefore be wrong here; the realistic check is that
    the template was applied and the engine generated. (Raw-prompt base-model answer quality is
    covered by the sibling test below, which uses `prompt_text` and does assert " Paris.".)"""
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

    from algenta.chat_template import apply_chat_template
    from algenta.tokenizer import load_tokenizer

    from apps.api_server.services import llm_api_service, llm_provider_service
    from apps.api_server.services.llm_provider_service import _executors_local

    # The exact prompt ids the serving path must feed the engine: the checkpoint's chat template
    # applied to the messages, then tokenized by the checkpoint's own tokenizer. Both pieces are
    # independently oracle-validated byte-for-byte against transformers.
    messages = [{"role": "user", "content": "The capital of France is"}]
    expected_prompt_ids = load_tokenizer(_CHECKPOINT).encode(
        apply_chat_template(_CHECKPOINT, messages)
    )

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
                messages=messages,
                max_output_tokens=8,
            )
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    assert completion.provider.provider_backend == "algenta_local"
    # The chat template was actually applied end to end (not a hardcoded count -- derived from the
    # template + tokenizer the serving path is supposed to use).
    assert completion.prompt_tokens == len(expected_prompt_ids), (
        f"serving did not apply the chat template: got {completion.prompt_tokens} prompt tokens, "
        f"expected {len(expected_prompt_ids)} for the template-formatted prompt"
    )
    assert completion.completion_tokens == 8
    assert completion.content, "the GPU generated no content"


@pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)
def test_local_backend_chat_completion_with_tools_through_real_gpu(monkeypatch) -> None:
    """Track C3 wiring proof, real GPU: `tools` reaches the real Metal decode path end to end
    (chat_template's tools preamble -> tokenization -> algenta.inference.decode() -> generated
    text), with no exception anywhere in that chain.

    NOTE on the assertion shape: the checkpoint under test is a BASE model (not instruction-tuned)
    -- like the sibling test above, it does not reliably follow the tools preamble's instruction to
    answer with a `<tool_call>` block, so this does not assert that a tool was actually called
    (that would be asserting the model's behavior, not the serving path's). What IS asserted, the
    same way the sibling test asserts the chat template applied: the real engine tokenized and
    decoded the TOOLS-AUGMENTED prompt (a token count derived from `apply_chat_template(...,
    tools=tools)` + the real tokenizer, not a magic number) and generated without raising --
    proving `tools` genuinely reaches the chat template and the engine, not silently dropped."""
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

    from algenta.chat_template import apply_chat_template
    from algenta.tokenizer import load_tokenizer

    from apps.api_server.services import llm_api_service, llm_provider_service
    from apps.api_server.services.llm_provider_service import _executors_local

    messages = [{"role": "user", "content": "What is the weather in Paris?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    expected_prompt_ids = load_tokenizer(_CHECKPOINT).encode(
        apply_chat_template(_CHECKPOINT, messages, tools=tools)
    )

    llm_provider_service.load_provider_model_configs.cache_clear()
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    try:
        descriptor, completion = asyncio.run(
            llm_api_service.create_chat_completion(
                model_id="provider.algenta_local",
                messages=messages,
                tools=tools,
                max_output_tokens=32,
            )
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    assert completion.provider.provider_backend == "algenta_local"
    assert completion.prompt_tokens == len(expected_prompt_ids), (
        f"serving did not apply the tools-augmented chat template: got {completion.prompt_tokens} "
        f"prompt tokens, expected {len(expected_prompt_ids)} for the tools-augmented prompt"
    )
    assert completion.completion_tokens == 32
    # A tool-call-only turn sets content=None; either way, a real generation happened.
    assert completion.content or completion.tool_calls, "the GPU generated nothing"
    # finish_reason is only "tool_calls" when the parser actually found a <tool_call> block --
    # this base checkpoint is not expected to emit one, so "stop" is the expected, honest outcome.
    assert completion.finish_reason in ("stop", "tool_calls")


@pytest.mark.skipif(
    not _WORKER.is_file() or not (_CHECKPOINT / "config.json").is_file(),
    reason="needs the GPU worker binary and the Qwen3-0.6B-Base snapshot",
)
def test_local_backend_second_prompt_reuses_conversion_and_quantized_caches(monkeypatch) -> None:
    """The serving shape: the prompt travels separately from the converted weights, so ONE
    conversion per checkpoint serves every prompt. Two call shapes are both valid depending on
    the worker's resident state (persistent sessions, parity gap 4): a cold worker loads through
    `weights_i8.cache` (written on the f64 path); a worker whose resident buffers already hold
    this checkpoint skips even the cache read (the quantized state lives in the buffers). Either
    way: different prompt -> different answer, conversion reused, second call fast."""
    import shutil
    import time

    from algenta import MojoRuntime
    from algenta.inference import decode

    cache_dir = _CHECKPOINT / ".algenta-cache"
    shutil.rmtree(cache_dir, ignore_errors=True)
    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", str(_WORKER))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")

    runtime = MojoRuntime(mode="local", timeout=600.0)

    first = decode(
        runtime,
        checkpoint_dir=_CHECKPOINT,
        prompt_text="The capital of France is",
        max_new_tokens=8,
    )

    # Conversion reuse: the pair now exists and a second decode must not reconvert it.
    assert (cache_dir / "manifest.json").is_file()
    assert (cache_dir / "weights.blob").is_file()
    manifest_mtime = (cache_dir / "manifest.json").stat().st_mtime_ns

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
    # The second call reused the conversion (file untouched)...
    assert (cache_dir / "manifest.json").stat().st_mtime_ns == manifest_mtime
    # ...and stayed on a fast path (resident buffers or the quantized cache, either one).
    assert cached_wall < 2.0, f"second call took {cached_wall:.2f}s; expected a fast path"
