from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from scripts.emit_local_provider_registry import (
    derive_local_provider_registry,
    parse_provider_registry_json,
    provider_router_enabled,
)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_derive_local_provider_registry_prefers_provider_credentials() -> None:
    payload = derive_local_provider_registry(
        {
            "ANTHROPIC_API_KEY": "anthropic-live",
            "COHERE_API_KEY": "cohere-live",
        },
        fetch_ollama_tags=lambda base_url: ["ignored:latest"],
    )

    assert [entry["id"] for entry in payload] == [
        "provider.anthropic.local",
        "provider.cohere.local",
        "provider.router",
    ]
    router = payload[-1]
    assert router["targets"] == ["provider.anthropic.local", "provider.cohere.local"]
    assert router["fallback_policy"] == "retryable_only"
    assert router["fallback_on"] == [
        "backend_unavailable",
        "provider_timeout",
        "provider_rate_limited",
        "provider_backend_error",
    ]


def test_derive_local_provider_registry_falls_back_to_ollama_when_no_provider_creds() -> None:
    payload = derive_local_provider_registry(
        {},
        fetch_ollama_tags=lambda base_url: ["qwen3-coder:latest"],
    )

    assert [entry["id"] for entry in payload] == [
        "provider.ollama.local",
        "provider.router",
    ]
    ollama = payload[0]
    assert ollama["backend"] == "ollama"
    assert ollama["model_name"] == "qwen3-coder:latest"
    assert ollama["base_url"] == "http://127.0.0.1:11434"
    router = payload[1]
    assert router["targets"] == ["provider.ollama.local"]
    assert "fallback_policy" not in router


def test_derive_local_provider_registry_uses_explicit_ollama_env_over_probe() -> None:
    payload = derive_local_provider_registry(
        {
            "ALGENTA_LOCAL_OLLAMA_BASE_URL": "http://localhost:22434",
            "ALGENTA_LOCAL_OLLAMA_MODEL": "custom-ollama:edge",
        },
        fetch_ollama_tags=lambda base_url: [],
    )

    assert [entry["id"] for entry in payload] == [
        "provider.ollama.local",
        "provider.router",
    ]
    assert payload[0]["base_url"] == "http://localhost:22434"
    assert payload[0]["model_name"] == "custom-ollama:edge"


def test_emit_local_provider_registry_cli_executes_as_script() -> None:
    env = {
        **os.environ,
        "ANTHROPIC_API_KEY": "anthropic-live",
    }
    for key in (
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "MISTRAL_API_KEY",
        "COHERE_API_KEY",
        "GROQ_API_KEY",
        "XAI_API_KEY",
        "ALGENTA_LOCAL_OLLAMA_MODEL",
        "OLLAMA_HOST",
        "ALGENTA_LOCAL_OLLAMA_BASE_URL",
    ):
        env.pop(key, None)

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "emit_local_provider_registry.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [entry["id"] for entry in payload] == [
        "provider.anthropic.local",
        "provider.router",
    ]


def test_parse_provider_registry_json_rejects_non_array_payload() -> None:
    with pytest.raises(ValueError, match="JSON array"):
        parse_provider_registry_json('{"id":"provider.router"}')


def test_parse_provider_registry_json_rejects_missing_entry_ids() -> None:
    with pytest.raises(ValueError, match="non-empty string id"):
        parse_provider_registry_json('[{"backend":"router"}]')


def test_provider_router_enabled_requires_real_router_entry() -> None:
    assert provider_router_enabled('[{"id":"provider.anthropic.local"}]') is False
    assert provider_router_enabled('[{"id":"provider.router"}]') is True


def test_emit_local_provider_registry_cli_has_router_mode_fails_closed_on_invalid_json() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "emit_local_provider_registry.py"),
            "--has-router",
            '{"id":"provider.router"}',
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "JSON array" in result.stderr


def test_derive_local_provider_registry_emits_algenta_local_entries() -> None:
    payload = derive_local_provider_registry(
        {
            "ALGENTA_LOCAL_LLM_MODELS_JSON": json.dumps(
                {"qwen3-1.7b": "/models/qwen3-1.7b", "qwen3-0.6b-base": "/models/qwen3-0.6b"}
            ),
        },
        fetch_ollama_tags=lambda base_url: [],
    )

    # Sorted model names, one entry each, and NO router entry (the local GPU backend is not an
    # HTTP failover target, and nothing else produced a router target here).
    assert [entry["id"] for entry in payload] == [
        "provider.algenta_local.qwen3-0.6b-base",
        "provider.algenta_local.qwen3-1.7b",
    ]
    first = payload[0]
    assert first["backend"] == "algenta_local"
    assert first["model_name"] == "qwen3-0.6b-base"
    assert first["capabilities"] == ["chat_completions"]
    assert "/models/qwen3-0.6b" in str(first["description"])


def test_derive_local_provider_registry_ignores_invalid_local_llm_map() -> None:
    payload = derive_local_provider_registry(
        {"ALGENTA_LOCAL_LLM_MODELS_JSON": "not-json"},
        fetch_ollama_tags=lambda base_url: [],
    )
    assert payload == []
