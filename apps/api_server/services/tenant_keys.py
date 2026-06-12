"""B10: per-tenant LLM/engine key resolution seam (fail-closed in multi-tenant).

Today the LLM provider key and the engine key are resolved from GLOBAL env — correct for a
single-tenant self-hosted deployment, but in a multi-tenant SaaS every org would share that one
key (cross-tenant key reuse). This module is the SEAM a per-org key store plugs into WITHOUT
touching every call site:

  1. a request-scoped ContextVar override (set server-side from the authenticated org — never
     caller-supplied — once a per-org key store + auth middleware exist) takes precedence;
  2. otherwise a single-tenant deployment (the default) uses the env key — unchanged behavior;
  3. an explicit multi-tenant deployment (``ALGENTA_REQUIRE_PER_TENANT_KEYS=1``) with no per-org
     override FAILS CLOSED (returns None) rather than silently borrowing the shared global env key.

Default behavior is byte-for-byte the current env path (no override set, require flag off), so this
carries zero production risk; it only adds the seam + the fail-closed multi-tenant guarantee. The
per-org key STORE (where an org's key is read from — connector config / a credentials table) is a
deliberate follow-up tied to the SaaS onboarding model; when it lands it just sets the ContextVar.
B3 already removed the sidecar's cross-tenant engine-env bleed; this is the API side."""

from __future__ import annotations

import os
from contextvars import ContextVar, Token

_provider_key_override: ContextVar[str | None] = ContextVar(
    "algenta_provider_key_override", default=None
)
_engine_key_override: ContextVar[str | None] = ContextVar(
    "algenta_engine_key_override", default=None
)

_TRUE = {"1", "true", "yes", "on"}


def require_per_tenant_keys() -> bool:
    """True in an explicit multi-tenant deployment, where a missing per-org key must FAIL CLOSED
    instead of borrowing the shared global env key."""
    return os.environ.get("ALGENTA_REQUIRE_PER_TENANT_KEYS", "").strip().lower() in _TRUE


def set_provider_key_override(key: str | None) -> Token:
    """Set the request-scoped LLM provider key (server-derived from the authenticated org). Returns
    a token the caller MUST reset in a finally, so a pooled async task never inherits another
    request's key."""
    return _provider_key_override.set(key)


def reset_provider_key_override(token: Token) -> None:
    _provider_key_override.reset(token)


def set_engine_key_override(key: str | None) -> Token:
    return _engine_key_override.set(key)


def reset_engine_key_override(token: Token) -> None:
    _engine_key_override.reset(token)


def resolve_provider_api_key(api_key_env: str | None) -> str | None:
    """Resolve the LLM provider key. Precedence: per-request org override > (single-tenant) env key.
    In a multi-tenant deployment with no override, returns None so the caller FAILS CLOSED — the
    shared global env key is never reused across tenants."""
    override = _provider_key_override.get()
    if override:
        return override
    if require_per_tenant_keys():
        return None
    if not api_key_env:
        return None
    return os.environ.get(api_key_env) or None


def resolve_engine_api_key() -> str | None:
    """Resolve the repository-engine key with the same precedence + multi-tenant fail-closed rule."""
    override = _engine_key_override.get()
    if override:
        return override
    if require_per_tenant_keys():
        return None
    return os.environ.get("ALGENTA_ENGINE_API_KEY") or os.environ.get("ALGENTA_API_KEY") or None
