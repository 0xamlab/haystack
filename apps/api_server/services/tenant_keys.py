"""B10: per-tenant LLM/engine key resolution seam (fail-closed in multi-tenant).

Today the LLM provider key and the engine key are resolved from GLOBAL env — correct for a
single-tenant self-hosted deployment, but in a multi-tenant SaaS every org would share that one
key (cross-tenant key reuse). This module is the SEAM a per-org key store plugs into WITHOUT
touching every call site:

  1. a request/run-scoped ContextVar override (the authenticated org's keys, set server-side —
     never caller-supplied) takes precedence, PER BACKEND;
  2. otherwise a single-tenant deployment (the default) uses the pooled env key — unchanged behavior;
  3. an explicit multi-tenant deployment (``ALGENTA_REQUIRE_PER_TENANT_KEYS=1``) with no per-org
     override FAILS CLOSED (returns None) rather than silently borrowing the shared global env key.

Default behavior (no override set, require flag off) is byte-for-byte the current env path, so this
carries zero risk for the self-hosted-via-SDK use case; it adds the seam + the fail-closed
multi-tenant guarantee for the GitHub/Cursor BYOK use case.

PR11a fills the store: the ContextVar carries an :class:`OrgKeys` resolved per request (API auth
hook) or per run (worker/fire-and-forget hook) from ``org_id`` via ``tenant_key_store``. The carrier
is per-process/per-request only — a key is never serialized into a job payload (the worker
re-resolves from org_id) and ``OrgKeys.__repr__`` never exposes key material."""

from __future__ import annotations

import os
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrgKeys:
    """A tenant's resolved keys for the current request/run. Provider keys are per-backend
    (openai/anthropic/...), matching the existing ``api_key_env`` model; the engine key is a single
    per-org value. ``__repr__`` is redacted so key material never reaches logs/reprs/snapshots."""

    org_id: uuid.UUID | None
    provider_keys: dict[str, str] = field(default_factory=dict)  # backend -> key
    engine_key: str | None = None

    def __repr__(self) -> str:
        return (
            f"OrgKeys(org_id={self.org_id}, "
            f"provider_backends={sorted(self.provider_keys)}, "
            f"engine_key={'set' if self.engine_key else 'unset'})"
        )


_org_keys_override: ContextVar[OrgKeys | None] = ContextVar(
    "algenta_org_keys_override", default=None
)

_TRUE = {"1", "true", "yes", "on"}


def require_per_tenant_keys() -> bool:
    """True in an explicit multi-tenant deployment, where a missing per-org key must FAIL CLOSED
    instead of borrowing the shared global env key."""
    return os.environ.get("ALGENTA_REQUIRE_PER_TENANT_KEYS", "").strip().lower() in _TRUE


def set_org_keys_override(keys: OrgKeys | None) -> Token:
    """Bind the request/run-scoped org keys (server-derived from the authenticated org). Returns a
    token the caller MUST reset in a finally, so a pooled async task never inherits another
    request's keys."""
    return _org_keys_override.set(keys)


def reset_org_keys_override(token: Token) -> None:
    _org_keys_override.reset(token)


def current_org_keys() -> OrgKeys | None:
    return _org_keys_override.get()


def resolve_provider_api_key(api_key_env: str | None, backend: str | None = None) -> str | None:
    """Resolve the LLM provider key for ``backend``. Precedence: per-request org override (for that
    backend) > (single-tenant) pooled env key. In a multi-tenant deployment with no override,
    returns None so the caller FAILS CLOSED — the shared env key is never reused across tenants."""
    keys = _org_keys_override.get()
    if keys is not None and backend is not None:
        override = keys.provider_keys.get(backend)
        if override:
            return override
    if require_per_tenant_keys():
        return None
    if not api_key_env:
        return None
    return os.environ.get(api_key_env) or None


def resolve_engine_api_key() -> str | None:
    """Resolve the repository-engine key with the same precedence + multi-tenant fail-closed rule."""
    keys = _org_keys_override.get()
    if keys is not None and keys.engine_key:
        return keys.engine_key
    if require_per_tenant_keys():
        return None
    return os.environ.get("ALGENTA_ENGINE_API_KEY") or os.environ.get("ALGENTA_API_KEY") or None
