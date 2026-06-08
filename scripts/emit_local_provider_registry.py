from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Callable

ProviderTagsFetcher = Callable[[str], list[str]]

_PROVIDER_SPECS = (
    {
        "id": "provider.anthropic.local",
        "backend": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "model_env": "ALGENTA_LOCAL_ANTHROPIC_MODEL",
        "default_model": "claude-sonnet-4-0",
    },
    {
        "id": "provider.openai.local",
        "backend": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model_env": "ALGENTA_LOCAL_OPENAI_MODEL",
        "default_model": "gpt-4.1-mini",
    },
    {
        "id": "provider.google.local",
        "backend": "google_genai",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model_env": "ALGENTA_LOCAL_GOOGLE_MODEL",
        "default_model": "gemini-2.5-flash",
    },
    {
        "id": "provider.mistral.local",
        "backend": "mistral",
        "api_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "model_env": "ALGENTA_LOCAL_MISTRAL_MODEL",
        "default_model": "mistral-large-latest",
    },
    {
        "id": "provider.cohere.local",
        "backend": "cohere",
        "api_key_env": "COHERE_API_KEY",
        "base_url": "https://api.cohere.com/compatibility/v1",
        "model_env": "ALGENTA_LOCAL_COHERE_MODEL",
        "default_model": "command-r-plus",
    },
    {
        "id": "provider.groq.local",
        "backend": "groq",
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model_env": "ALGENTA_LOCAL_GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
    },
    {
        "id": "provider.xai.local",
        "backend": "xai",
        "api_key_env": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "model_env": "ALGENTA_LOCAL_XAI_MODEL",
        "default_model": "grok-4.1",
    },
)
_ROUTER_RETRYABLE_CODES = [
    "backend_unavailable",
    "provider_timeout",
    "provider_rate_limited",
    "provider_backend_error",
]


def _fetch_ollama_tags(base_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=1.5) as response:
            payload = json.load(response)
    except Exception:
        return []
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    tags: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            tags.append(name.strip())
    return tags


def parse_provider_registry_json(raw: str) -> list[dict[str, object]]:
    text = raw.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Provider registry must be valid JSON.") from exc
    if not isinstance(payload, list):
        raise ValueError("Provider registry must be a JSON array.")
    normalized_payload: list[dict[str, object]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Provider registry entry {index} must be a JSON object.")
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"Provider registry entry {index} must include a non-empty string id.")
        normalized_payload.append(item)
    return normalized_payload


def provider_router_enabled(raw: str) -> bool:
    payload = parse_provider_registry_json(raw)
    return any(item.get("id") == "provider.router" for item in payload)


def derive_local_provider_registry(
    env: dict[str, str] | os._Environ[str],
    *,
    fetch_ollama_tags: ProviderTagsFetcher = _fetch_ollama_tags,
) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    router_targets: list[str] = []
    for spec in _PROVIDER_SPECS:
        if not str(env.get(spec["api_key_env"], "")).strip():
            continue
        model_name = str(env.get(spec["model_env"], "")).strip() or str(spec["default_model"])
        payload.append(
            {
                "id": spec["id"],
                "backend": spec["backend"],
                "base_url": spec["base_url"],
                "api_key_env": spec["api_key_env"],
                "model_name": model_name,
                "capabilities": ["chat_completions"],
                "description": (
                    f"Local start-local provider surface for backend '{spec['backend']}' "
                    f"using upstream model '{model_name}'."
                ),
            }
        )
        router_targets.append(str(spec["id"]))

    if not router_targets:
        ollama_base_url = (
            str(env.get("ALGENTA_LOCAL_OLLAMA_BASE_URL", "")).strip()
            or str(env.get("OLLAMA_HOST", "")).strip()
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        ollama_model = str(env.get("ALGENTA_LOCAL_OLLAMA_MODEL", "")).strip()
        if not ollama_model:
            tags = fetch_ollama_tags(ollama_base_url)
            if tags:
                ollama_model = tags[0]
        if ollama_model:
            payload.append(
                {
                    "id": "provider.ollama.local",
                    "backend": "ollama",
                    "base_url": ollama_base_url,
                    "model_name": ollama_model,
                    "capabilities": ["chat_completions"],
                    "description": (
                        f"Local Ollama chat model '{ollama_model}' exposed for Mission-ready "
                        "local chat flows."
                    ),
                }
            )
            router_targets.append("provider.ollama.local")

    if router_targets:
        router_entry: dict[str, object] = {
            "id": "provider.router",
            "backend": "router",
            "capabilities": ["chat_completions"],
            "targets": router_targets,
            "description": "Deterministic local provider router alias for Mission-ready Algenta chat flows.",
        }
        if len(router_targets) > 1:
            router_entry["fallback_policy"] = "retryable_only"
            router_entry["fallback_on"] = list(_ROUTER_RETRYABLE_CODES)
        payload.append(router_entry)
    return payload


def main(argv: list[str]) -> int:
    if not argv:
        payload = derive_local_provider_registry(os.environ)
        print(json.dumps(payload, separators=(",", ":")) if payload else "")
        return 0
    if len(argv) == 2 and argv[0] == "--has-router":
        try:
            print("1" if provider_router_enabled(argv[1]) else "0")
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0
    print("usage: emit_local_provider_registry.py [--has-router <registry-json>]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
