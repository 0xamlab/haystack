"""Dynamic model discovery — query each provider's own list-models API for the LATEST models, instead of a
static ``model_name``.

Opt-in per provider: an ``ALGENTA_LLM_PROVIDER_MODELS_JSON`` entry with ``model_name: "*"`` (i.e.
``upstream_model == "*"``) means "discover every model this backend offers". The catalog (GET /v1/models)
expands such an entry into one live, routable model per discovered id, named ``<entry-id>:<model>`` (e.g.
``provider.openai:gpt-5``); a chat/embeddings request to that id routes to the entry's backend with the
discovered model as the upstream — no static list to keep current.

Discovery calls are egress-guarded (they reuse ``_provider_get_json``, so the fail-closed / SSRF policy
applies to the customer-configured base_url) + TTL-cached. Failures are best-effort: they degrade to "no
discovered models for this entry", never a 500 on the catalog.
"""
from __future__ import annotations

import os
import time
from dataclasses import replace

from apps.api_server.services.llm_provider_service._config import ProviderModelConfig
from apps.api_server.services.llm_provider_service._http_layer import _provider_get_json

DISCOVERY_SENTINEL = "*"

# Per-backend list-models path, relative to the entry's base_url (whose /v1 or /v1beta convention the
# operator already set for chat). Absent = discovery unsupported for that backend (e.g. the `router` alias).
_LIST_MODELS_PATH: dict[str, str] = {
    "openai": "/models",
    "openai_compatible": "/models",
    "mistral": "/models",
    "groq": "/models",
    "xai": "/models",
    "cohere": "/models",
    "anthropic": "/models",
    "google_genai": "/models",
    "ollama": "/api/tags",
}


def is_discovery_entry(config: ProviderModelConfig) -> bool:
    """True if this provider entry is a discovery entry (model_name == '*')."""
    return (config.upstream_model or "").strip() == DISCOVERY_SENTINEL


def discovery_supported(backend: str) -> bool:
    return backend in _LIST_MODELS_PATH


def _ttl_seconds() -> int:
    try:
        return max(0, int(os.environ.get("ALGENTA_LLM_DISCOVERY_TTL_SECONDS", "600")))
    except (TypeError, ValueError):
        return 600


def _parse_models(backend: str, data: dict) -> list[str]:
    """Extract model ids from a backend's list-models response (openai `{data:[{id}]}`, ollama
    `{models:[{name}]}`, google native `{models:[{name:'models/...'}]}`)."""
    out: list[str] = []
    if backend == "ollama":
        for m in data.get("models") or []:
            if isinstance(m, dict):
                name = str(m.get("name") or m.get("model") or "").strip()
                if name:
                    out.append(name)
    elif backend == "google_genai" and isinstance(data.get("models"), list):
        for m in data["models"]:
            if not isinstance(m, dict):
                continue
            name = str(m.get("name") or "").strip()
            if name.startswith("models/"):
                name = name[len("models/"):]
            if name:
                out.append(name)
    else:
        # openai-compatible shape: {data: [{id}]} (also google's /v1beta/openai base)
        for m in data.get("data") or []:
            if isinstance(m, dict):
                mid = str(m.get("id") or "").strip()
                if mid:
                    out.append(mid)
    seen: set[str] = set()
    uniq: list[str] = []
    for i in out:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


# {entry_model_id: (expiry_epoch, [models])}
_CACHE: dict[str, tuple[float, list[str]]] = {}


def clear_discovery_cache() -> None:
    _CACHE.clear()


async def discover_provider_models(
    config: ProviderModelConfig, *, now: float | None = None, force: bool = False
) -> list[str]:
    """Latest model ids for this entry's backend (egress-guarded GET, TTL-cached). Best-effort: on any
    failure returns the last cached value (or []) and never raises — a provider hiccup must not 500 the
    catalog. Only meaningful for discovery entries, but callable on any entry with a supported backend."""
    now = time.time() if now is None else now
    path = _LIST_MODELS_PATH.get(config.backend)
    if path is None:
        return []
    cached = _CACHE.get(config.model_id)
    if cached and not force and cached[0] > now:
        return cached[1]
    timeout = config.chat_timeout_seconds or config.timeout_seconds or 15.0
    try:
        data = await _provider_get_json(config=config, path=path, timeout_seconds=timeout)
        models = _parse_models(config.backend, data)
    except Exception:  # noqa: BLE001 — discovery is best-effort (LLMAPIError, network, parse); never break the catalog
        _CACHE[config.model_id] = (now + min(_ttl_seconds(), 60), cached[1] if cached else [])
        return cached[1] if cached else []
    _CACHE[config.model_id] = (now + _ttl_seconds(), models)
    return models


def discovered_model_id(entry: ProviderModelConfig, model: str) -> str:
    return f"{entry.model_id}:{model}"


def resolve_discovered_model(model_id: str) -> ProviderModelConfig | None:
    """Sync routing: if ``model_id`` is a discovered model (``<entry-id>:<model>`` for a discovery entry),
    return a ProviderModelConfig for it (the entry with ``upstream_model`` set to ``<model>`` + that id).
    No network — routing only. Returns None if it isn't a discovered-model id."""
    from apps.api_server.services import llm_provider_service as _facade

    for entry in _facade.load_provider_model_configs():
        if not is_discovery_entry(entry):
            continue
        prefix = f"{entry.model_id}:"
        if model_id.startswith(prefix):
            upstream = model_id[len(prefix):]
            if upstream:
                return replace(entry, model_id=model_id, upstream_model=upstream)
    return None
