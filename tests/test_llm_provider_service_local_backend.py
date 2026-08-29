"""Tests for the `algenta_local` provider backend (parity gap 2, 2026-08-10): the local
Apple-Silicon GPU engine registry entry, the checkpoint-map loader, the prompt flattening, and
the executor's result shaping / error mapping. The executor's GPU call itself is mocked -- the
real GPU path is covered end to end by tests/test_inference_gpu_e2e.py."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from apps.api_server.services import llm_provider_service
from apps.api_server.services.llm_api_service import LLMAPIError
from apps.api_server.services.llm_provider_service import _executors_local


def _set_provider_registry(monkeypatch, entries: list[dict]) -> None:
    monkeypatch.setenv("ALGENTA_LLM_PROVIDER_MODELS_JSON", json.dumps(entries))
    llm_provider_service.load_provider_model_configs.cache_clear()


def _local_entry() -> dict:
    return {
        "id": "provider.algenta_local",
        "backend": "algenta_local",
        "model_name": "qwen3-0.6b-base",
        "capabilities": ["chat_completions"],
    }


def test_local_backend_config_loads_without_base_url_or_key(monkeypatch) -> None:
    _set_provider_registry(monkeypatch, [_local_entry()])
    try:
        config = llm_provider_service.get_configured_provider_model("provider.algenta_local")
        assert config is not None
        assert config.backend == "algenta_local"
        assert config.base_url == ""
        assert config.api_key_env is None
        assert config.upstream_model == "qwen3-0.6b-base"
        assert config.capabilities == ("chat_completions",)
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_local_backend_rejects_embeddings_capability(monkeypatch) -> None:
    entry = _local_entry()
    entry["capabilities"] = ["chat_completions", "embeddings"]
    _set_provider_registry(monkeypatch, [entry])
    try:
        with pytest.raises(ValueError):
            llm_provider_service.load_provider_model_configs()
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()


def test_local_checkpoint_map_parses_and_caches(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON",
        json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b", "qwen3-1.7b": "/tmp/ckpt-17b"}),
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    try:
        assert _executors_local.load_local_llm_checkpoint_map() == {
            "qwen3-0.6b-base": "/tmp/ckpt-06b",
            "qwen3-1.7b": "/tmp/ckpt-17b",
        }
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()


def test_local_checkpoint_map_refuses_non_object(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps(["not", "an", "object"]))
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    try:
        with pytest.raises(ValueError):
            _executors_local.load_local_llm_checkpoint_map()
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()


def test_local_prompt_flattening() -> None:
    single = [{"role": "user", "content": "The capital of France is"}]
    assert (
        _executors_local.local_prompt_text_from_messages(single)
        == "The capital of France is"
    )
    multi = [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "Hello."},
    ]
    assert (
        _executors_local.local_prompt_text_from_messages(multi)
        == "system: Be brief.\nuser: Hello."
    )


def _fake_decode_result() -> SimpleNamespace:
    return SimpleNamespace(
        token_ids=[1, 2, 3, 9, 8, 7],
        n_prompt=3,
        generated_text="Paris.",
    )


def test_execute_local_chat_completion_shapes_result(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b"})
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_decode_result()

    monkeypatch.setattr(_executors_local, "_run_local_decode", fake_run)
    config = SimpleNamespace(
        model_id="provider.algenta_local",
        upstream_model="qwen3-0.6b-base",
    )
    try:
        result = asyncio.run(
            _executors_local.execute_local_chat_completion(
                config=config,
                messages=[{"role": "user", "content": "The capital of France is"}],
                max_output_tokens=8,
                temperature=0.8,
                top_p=0.95,
                seed=1234,
            )
        )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    assert captured["checkpoint_dir"] == "/tmp/ckpt-06b"
    assert captured["prompt_text"] == "The capital of France is"
    assert captured["max_new_tokens"] == 8
    assert captured["temperature"] == 0.8
    assert captured["top_p"] == 0.95
    assert captured["seed"] == 1234
    assert result.content == "Paris."
    assert result.prompt_tokens == 3
    assert result.completion_tokens == 3
    assert result.provider.provider_backend == "algenta_local"
    assert result.provider.provider_model_id == "provider.algenta_local"
    assert [attempt.outcome for attempt in result.provider_attempts] == ["selected"]


def test_execute_local_chat_completion_missing_model_mapping(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({}))
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    config = SimpleNamespace(
        model_id="provider.algenta_local",
        upstream_model="qwen3-0.6b-base",
    )
    try:
        with pytest.raises(LLMAPIError) as excinfo:
            asyncio.run(
                _executors_local.execute_local_chat_completion(
                    config=config,
                    messages=[{"role": "user", "content": "hi"}],
                )
            )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()
    assert excinfo.value.code == "model_not_supported"


# ── Track C3: tool calling ──────────────────────────────────────────────────────────────────────
#
# The checkpoint dirs used elsewhere in this file ("/tmp/ckpt-06b" etc.) don't exist on disk, so
# `is_qwen3_chat_template(load_chat_template(checkpoint_dir))` naturally comes back False (no
# tokenizer_config.json to read) -- exactly what exercises the plain-text-flattening branch above.
# To exercise the chat-template branch here without a real checkpoint, these tests monkeypatch
# `algenta.chat_template.is_qwen3_chat_template` directly: `_executors_local.py` imports it with a
# fresh `from algenta.chat_template import ...` inside the function body on every call, so patching
# the module attribute takes effect on the next call exactly like a real byte-exact template match
# would.


def _force_chat_template_present(monkeypatch) -> None:
    import algenta.chat_template as chat_template_module

    monkeypatch.setattr(chat_template_module, "is_qwen3_chat_template", lambda template: True)


def test_execute_local_chat_completion_passes_tools_to_decode(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b"})
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    _force_chat_template_present(monkeypatch)

    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_decode_result()

    monkeypatch.setattr(_executors_local, "_run_local_decode", fake_run)
    config = SimpleNamespace(model_id="provider.algenta_local", upstream_model="qwen3-0.6b-base")
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    try:
        result = asyncio.run(
            _executors_local.execute_local_chat_completion(
                config=config,
                messages=[{"role": "user", "content": "weather in Paris?"}],
                tools=tools,
            )
        )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    assert "prompt_text" not in captured
    assert captured["messages"] == [{"role": "user", "content": "weather in Paris?"}]
    assert captured["tools"] == tools
    assert result.tool_calls is None  # the fake result's text has no tool_call block
    assert result.finish_reason == "stop"


def test_execute_local_chat_completion_tool_choice_none_drops_tools(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b"})
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    _force_chat_template_present(monkeypatch)

    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_decode_result()

    monkeypatch.setattr(_executors_local, "_run_local_decode", fake_run)
    config = SimpleNamespace(model_id="provider.algenta_local", upstream_model="qwen3-0.6b-base")
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    try:
        asyncio.run(
            _executors_local.execute_local_chat_completion(
                config=config,
                messages=[{"role": "user", "content": "weather in Paris?"}],
                tools=tools,
                tool_choice="none",
            )
        )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    # tool_choice="none" -- no preamble rendered at all: _run_local_decode (and therefore the
    # real decode()) never sees a truthy tools value.
    assert not captured.get("tools")
    assert captured["messages"] == [{"role": "user", "content": "weather in Paris?"}]


def test_execute_local_chat_completion_tools_without_chat_template_refused(monkeypatch) -> None:
    # No monkeypatch of is_qwen3_chat_template here: "/tmp/ckpt-06b" has no tokenizer_config.json,
    # so the checkpoint genuinely has no chat template to render a tools preamble into.
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b"})
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    config = SimpleNamespace(model_id="provider.algenta_local", upstream_model="qwen3-0.6b-base")
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    try:
        with pytest.raises(LLMAPIError) as excinfo:
            asyncio.run(
                _executors_local.execute_local_chat_completion(
                    config=config,
                    messages=[{"role": "user", "content": "weather?"}],
                    tools=tools,
                )
            )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()
    assert excinfo.value.code == "model_capability_unsupported"


def test_execute_local_chat_completion_parses_tool_call_from_generated_text(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b"})
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()
    _force_chat_template_present(monkeypatch)

    # Shaped exactly like the tools preamble instructs the model to answer (see chat_template.py's
    # tools-preamble text and tests/test_chat_template_qwen3.py's parser coverage).
    generated_text = (
        "<tool_call>\n"
        '{"name": "get_weather", "arguments": {"city": "Paris"}}'
        "\n</tool_call>"
    )

    def fake_run(**kwargs):
        return SimpleNamespace(token_ids=list(range(20)), n_prompt=10, generated_text=generated_text)

    monkeypatch.setattr(_executors_local, "_run_local_decode", fake_run)
    config = SimpleNamespace(model_id="provider.algenta_local", upstream_model="qwen3-0.6b-base")
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    try:
        result = asyncio.run(
            _executors_local.execute_local_chat_completion(
                config=config,
                messages=[{"role": "user", "content": "weather in Paris?"}],
                tools=tools,
            )
        )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()

    assert result.content is None  # tool-call-only turn
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    tool_call = result.tool_calls[0]
    assert tool_call.id == f"call_{result.completion_id}_0"
    assert tool_call.type == "function"
    assert tool_call.function.name == "get_weather"
    assert json.loads(tool_call.function.arguments) == {"city": "Paris"}


def test_execute_local_chat_completion_maps_engine_refusal(monkeypatch) -> None:
    from algenta.inference import InferenceError

    monkeypatch.setenv(
        "ALGENTA_LOCAL_LLM_MODELS_JSON", json.dumps({"qwen3-0.6b-base": "/tmp/ckpt-06b"})
    )
    _executors_local.load_local_llm_checkpoint_map.cache_clear()

    def refusing_run(**kwargs):
        raise InferenceError("invalid_arguments", "prompt_token_ids must be a non-empty list")

    monkeypatch.setattr(_executors_local, "_run_local_decode", refusing_run)
    config = SimpleNamespace(
        model_id="provider.algenta_local",
        upstream_model="qwen3-0.6b-base",
    )
    try:
        with pytest.raises(LLMAPIError) as excinfo:
            asyncio.run(
                _executors_local.execute_local_chat_completion(
                    config=config,
                    messages=[{"role": "user", "content": "hi"}],
                )
            )
    finally:
        _executors_local.load_local_llm_checkpoint_map.cache_clear()
    assert excinfo.value.code == "invalid_provider_request"
    assert excinfo.value.details["engine_code"] == "invalid_arguments"
