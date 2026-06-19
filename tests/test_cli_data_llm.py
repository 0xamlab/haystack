"""Tests for CLI llm commands.

Extracted from tests/test_cli_data.py during modularization.
"""
from __future__ import annotations

import json

import pytest

from apps.cli import main as cli
from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS_DISPLAY,
    MANIFEST_BACKED_READ_ONLY_DISPLAY,
    assert_manifest_backed_integrations,
)
from tests._cli_data_helpers import (
    _capture_stdout,
    _capture_stderr,
    _platform_contract_payload,
)


def test_cmd_llm_models_prints_available_models(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "data": [
                    {
                        "id": "text.tokenizer",
                        "runtime_module": "tokenizer",
                        "capabilities": ["tokenize", "count_tokens"],
                        "supported_endpoints": ["/v1/models", "/v1/tokenize"],
                    },
                    {
                        "id": "embeddings.cosine_similarity",
                        "runtime_module": "embeddings",
                        "capabilities": ["similarity"],
                        "supported_endpoints": ["/v1/embeddings/similarity", "/v1/rerank"],
                    },
                    {
                        "id": "provider.router",
                        "runtime_module": "provider.router",
                        "capabilities": ["chat_completions", "embeddings"],
                        "supported_endpoints": [
                            "/v1/models",
                            "/v1/chat/completions",
                            "/v1/embeddings",
                        ],
                        "provider_backend": "router",
                        "routing_targets": ["provider.primary"],
                        "resolved_routing_targets": ["provider.primary"],
                        "chat_routing_targets": ["provider.fast", "provider.primary"],
                        "resolved_chat_routing_targets": [
                            "provider.fast",
                            "provider.primary",
                        ],
                        "embedding_routing_targets": ["provider.primary"],
                        "resolved_embedding_routing_targets": ["provider.primary"],
                        "routing_fallback_policy": "retryable_only",
                        "chat_routing_fallback_policy": "retryable_only",
                        "embedding_routing_fallback_policy": "disabled",
                        "routing_fallback_on": ["provider_rate_limited", "provider_timeout"],
                        "chat_routing_fallback_on": ["provider_rate_limited"],
                        "embedding_routing_fallback_on": ["provider_backend_error"],
                        "routing_max_attempts": 2,
                        "chat_routing_max_attempts": 2,
                        "embedding_routing_max_attempts": 1,
                        "timeout_seconds": 18.0,
                        "chat_timeout_seconds": 12.5,
                        "embedding_timeout_seconds": 9.0,
                        "required_provider_headers": ["OpenAI-Organization"],
                        "chat_required_provider_headers": [
                            "OpenAI-Organization",
                            "X-Groq-Project",
                        ],
                        "embedding_required_provider_headers": ["OpenAI-Organization"],
                        "provider_auth_env_vars": ["OPENAI_API_KEY", "OPENAI_ORG_ID"],
                        "chat_provider_auth_env_vars": [
                            "GROQ_API_KEY",
                            "GROQ_PROJECT_ID",
                            "OPENAI_API_KEY",
                            "OPENAI_ORG_ID",
                        ],
                        "embedding_provider_auth_env_vars": [
                            "OPENAI_API_KEY",
                            "OPENAI_ORG_ID",
                        ],
                        "provider_auth_configured": True,
                        "chat_provider_auth_configured": True,
                        "embedding_provider_auth_configured": False,
                    },
                ]
            },
        ),
    )

    output = _capture_stdout(cli.cmd_llm_models, "table")

    assert "Algenta models (3 available)" in output
    assert "text.tokenizer  [tokenizer]" in output
    assert "capabilities: tokenize, count_tokens" in output
    assert "/v1/embeddings/similarity, /v1/rerank" in output
    assert "provider.router  [provider.router]" in output
    assert "provider:     router" in output
    assert "declared:     provider.primary" in output
    assert "chat route:   provider.fast, provider.primary" in output
    assert "chat leafs:   provider.fast, provider.primary" in output
    assert "embed route:  provider.primary" in output
    assert "embed leafs:  provider.primary" in output
    assert "fallback:     retryable_only" in output
    assert "chat failover: retryable_only" in output
    assert "embed failover: disabled" in output
    assert "on errors:    provider_rate_limited, provider_timeout" in output
    assert "chat on:      provider_rate_limited" in output
    assert "embed on:     provider_backend_error" in output
    assert "attempts:     2" in output
    assert "chat tries:   2" in output
    assert "embed tries:  1" in output
    assert "timeout:      18.0s" in output
    assert "chat timeout: 12.5s" in output
    assert "embed timeout: 9.0s" in output
    assert "headers:      OpenAI-Organization" in output
    assert "chat headers: OpenAI-Organization, X-Groq-Project" in output
    assert "embed headers: OpenAI-Organization" in output
    assert "auth envs:    OPENAI_API_KEY, OPENAI_ORG_ID" in output
    assert "chat envs:    GROQ_API_KEY, GROQ_PROJECT_ID, OPENAI_API_KEY, OPENAI_ORG_ID" in output
    assert "embed envs:   OPENAI_API_KEY, OPENAI_ORG_ID" in output
    assert "auth ready:   True" in output
    assert "chat ready:   True" in output
    assert "embed ready:  False" in output


def test_cmd_llm_tokenize_posts_payload_and_prints_tokens(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/tokenize"
        assert body == {"input": "hello world", "model": "text.tokenizer"}
        return 200, {
            "model": "text.tokenizer",
            "tokenizer_kind": "bpe",
            "token_count": 2,
            "tokens": ["hello", "world"],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_llm_tokenize, "hello world", "text.tokenizer", "table")

    assert "Model:          text.tokenizer" in output
    assert "Tokenizer kind: bpe" in output
    assert "Token count:    2" in output
    assert "Tokens:         hello, world" in output


def test_cmd_llm_resolve_artifact_posts_payload_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "artifact_resolve.json"
    request_path.write_text(
        json.dumps(
            {
                "repo_id": "org/model",
                "filename": "model.safetensors",
                "revision": "main",
                "local_files_only": True,
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/artifacts/resolve"
        assert body == {
            "repo_id": "org/model",
            "filename": "model.safetensors",
            "revision": "main",
            "local_files_only": True,
        }
        return 200, {
            "backend": "huggingface_hub",
            "artifact_backend": "safetensors",
            "repo_id": "org/model",
            "filename": "model.safetensors",
            "revision": "main",
            "status": "not_cached",
            "cache_root": "/tmp/algenta-hf-cache",
            "local_files_only": True,
            "auth_configured": True,
            "auth_env_var_used": "HF_TOKEN",
            "resolved_path": None,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_llm_resolve_artifact, str(request_path), "table")

    assert "Backend:         huggingface_hub" in output
    assert "Filename:        model.safetensors" in output
    assert "Status:          not_cached" in output
    assert "Resolved path:   (not cached)" in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "response", "expected_lines"),
    [
        (
            "cmd_llm_chat",
            "/v1/chat/completions",
            {
                "model": "text.tokenizer",
                "messages": [{"role": "user", "content": "hello"}],
            },
            {
                "id": "chatcmpl_123",
                "model": "text.tokenizer",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "HELLO"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
            ["Completion ID:  chatcmpl_123", "Assistant:      HELLO"],
        ),
        (
            "cmd_llm_responses",
            "/v1/responses",
            {"model": "text.tokenizer", "input": "hello"},
            {
                "id": "resp_123",
                "model": "text.tokenizer",
                "status": "completed",
                "output": [{"type": "output_text", "text": "HELLO"}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
            ["Response ID:    resp_123", "Output items:   1"],
        ),
        (
            "cmd_llm_embeddings",
            "/v1/embeddings",
            {"model": "text.lexical_embedding", "input": ["hello"]},
            {
                "model": "text.lexical_embedding",
                "dimensions": 4,
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
            ["Model:          text.lexical_embedding", "Vectors:        1"],
        ),
        (
            "cmd_llm_embedding_similarity",
            "/v1/embeddings/similarity",
            {
                "model": "embeddings.cosine_similarity",
                "left": [1.0, 0.0],
                "right": [0.5, 0.5],
            },
            {
                "model": "embeddings.cosine_similarity",
                "similarity_metric": "cosine",
                "dimension": 2,
                "score": 0.71,
            },
            ["Similarity metric: cosine", "Score:            0.71"],
        ),
        (
            "cmd_llm_rerank",
            "/v1/rerank",
            {
                "model": "embeddings.cosine_similarity",
                "query_embedding": [1.0, 0.0],
                "documents": [
                    {"id": "doc_1", "embedding": [1.0, 0.0]},
                    {"id": "doc_2", "embedding": [0.0, 1.0]},
                ],
            },
            {
                "model": "embeddings.cosine_similarity",
                "similarity_metric": "cosine",
                "returned_documents": 2,
                "total_documents": 2,
                "data": [
                    {"id": "doc_1", "rank": 1, "score": 1.0},
                    {"id": "doc_2", "rank": 2, "score": 0.0},
                ],
            },
            ["Documents:         2 returned / 2 total", "#1 doc_1 score=1.0"],
        ),
    ],
)
def test_llm_request_commands_post_payload_and_render_summary(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    response: dict[str, object],
    expected_lines: list[str],
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / f"{func_name}.json"
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == payload
        return 200, response

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "table")

    for expected in expected_lines:
        assert expected in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "streamed_payloads"),
    [
        (
            "cmd_llm_chat",
            "/v1/chat/completions",
            {
                "model": "text.tokenizer",
                "messages": [{"role": "user", "content": "hello"}],
            },
            [
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"content": "HELLO"}, "finish_reason": None}],
                },
            ],
        ),
        (
            "cmd_llm_responses",
            "/v1/responses",
            {"model": "text.tokenizer", "input": "hello"},
            [
                {
                    "type": "response.created",
                    "response": {
                        "id": "resp_123",
                        "object": "response",
                        "status": "in_progress",
                        "model": "text.tokenizer",
                    },
                },
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_123",
                        "object": "response",
                        "status": "completed",
                        "model": "text.tokenizer",
                    },
                },
            ],
        ),
    ],
)
def test_llm_stream_commands_post_stream_payload_and_render_json_lines(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    streamed_payloads: list[dict[str, object]],
) -> None:
    request_path = tmp_path / f"{func_name}.json"
    request_path.write_text(json.dumps(payload))

    def _fake_api_stream_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == {**payload, "stream": True}
        return iter(streamed_payloads)

    monkeypatch.setattr(cli, "api_stream_request", _fake_api_stream_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "json", stream=True)
    lines = [json.loads(line) for line in output.splitlines() if line.strip()]
    assert lines == streamed_payloads


def test_cmd_llm_chat_stream_renders_table_summary(monkeypatch, tmp_path) -> None:
    request_path = tmp_path / "chat-stream.json"
    request_path.write_text(
        json.dumps(
            {
                "model": "text.tokenizer",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
    )

    monkeypatch.setattr(
        cli,
        "api_stream_request",
        lambda method, path, body=None: iter(  # type: ignore[no-untyped-def]
            [
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"content": "HEL"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {"content": "LO"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl_123",
                    "object": "chat.completion.chunk",
                    "model": "text.tokenizer",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            ]
        ),
    )

    output = _capture_stdout(cli.cmd_llm_chat, str(request_path), "table", stream=True)

    assert "Completion ID:  chatcmpl_123" in output
    assert "Model:          text.tokenizer" in output
    assert "Assistant:      HELLO" in output
    assert "Finish reason:  stop" in output


def test_cmd_llm_responses_stream_renders_table_summary(monkeypatch, tmp_path) -> None:
    request_path = tmp_path / "responses-stream.json"
    request_path.write_text(json.dumps({"model": "text.tokenizer", "input": "hello"}))

    monkeypatch.setattr(
        cli,
        "api_stream_request",
        lambda method, path, body=None: iter(  # type: ignore[no-untyped-def]
            [
                {
                    "type": "response.created",
                    "response": {
                        "id": "resp_123",
                        "status": "in_progress",
                        "model": "text.tokenizer",
                    },
                },
                {
                    "type": "response.output_item.done",
                    "output_index": 0,
                    "item": {"content": [{"type": "output_text", "text": "HELLO"}]},
                },
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_123",
                        "status": "completed",
                        "usage": {"total_tokens": 1},
                    },
                },
            ]
        ),
    )

    output = _capture_stdout(cli.cmd_llm_responses, str(request_path), "table", stream=True)

    assert "Response created: resp_123 status=in_progress model=text.tokenizer" in output
    assert "Output item #0: HELLO" in output
    assert "Response completed: resp_123 status=completed total_tokens=1" in output


def test_cmd_llm_chat_rejects_non_object_request_payload(tmp_path) -> None:
    request_path = tmp_path / "chat.json"
    request_path.write_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(ValueError, match="Request payload must be a JSON object."):
        cli.cmd_llm_chat(str(request_path), "table")


def test_main_dispatches_llm_models(monkeypatch) -> None:
    called: list[str] = []

    def _fake_cmd_llm_models(format: str = "table") -> None:
        called.append(format)

    monkeypatch.setattr(cli, "cmd_llm_models", _fake_cmd_llm_models)
    monkeypatch.setattr(cli.sys, "argv", ["de", "llm", "models", "--format", "json"])

    cli.main()

    assert called == ["json"]


def test_main_dispatches_llm_tokenize(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_llm_tokenize(
        text: str, model: str = "text.tokenizer", format: str = "table"
    ) -> None:
        called["text"] = text
        called["model"] = model
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_llm_tokenize", _fake_cmd_llm_tokenize)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "llm",
            "tokenize",
            "--input",
            "hello world",
            "--model",
            "text.tokenizer",
            "--format",
            "json",
        ],
    )

    cli.main()

    assert called == {
        "text": "hello world",
        "model": "text.tokenizer",
        "format": "json",
    }


def test_main_dispatches_llm_resolve_artifact(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_llm_resolve_artifact(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_llm_resolve_artifact", _fake_cmd_llm_resolve_artifact)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["de", "llm", "resolve-artifact", "artifact.json", "--format", "json"],
    )

    cli.main()

    assert called == {"request_path": "artifact.json", "format": "json"}


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["de", "llm", "chat", "chat.json", "--stream", "--format", "json"],
            {"request_path": "chat.json", "format": "json", "stream": True},
        ),
        (
            ["de", "llm", "responses", "responses.json", "--stream"],
            {"request_path": "responses.json", "format": "table", "stream": True},
        ),
    ],
)
def test_main_dispatches_llm_stream_commands(monkeypatch, argv: list[str], expected: dict[str, object]) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table", *, stream: bool = False) -> None:
        called["request_path"] = request_path
        called["format"] = format
        called["stream"] = stream

    target = "cmd_llm_chat" if argv[2] == "chat" else "cmd_llm_responses"
    monkeypatch.setattr(cli, target, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


