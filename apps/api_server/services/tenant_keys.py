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

# Provider-key resolution tiers (returned by ``provider_key_type``). The metering layer keys off
# MANAGED — only managed (platform-pooled-key) calls are billed + counted toward the spend cap.
KEY_TYPE_BYOK = "byok"  # the org's own key — customer pays the provider; not platform-metered
KEY_TYPE_MANAGED = "managed"  # platform pooled key (hosted, opted-in org) — metered + capped
KEY_TYPE_SELF_HOST = "self_host"  # single-tenant pooled env key — legacy, not metered
KEY_TYPE_NONE = "none"  # no key resolvable → caller fails closed


@dataclass(frozen=True)
class OrgKeys:
    """A tenant's resolved keys for the current request/run. Provider keys are per-backend
    (openai/anthropic/...), matching the existing ``api_key_env`` model; the engine key is a single
    per-org value. ``__repr__`` is redacted so key material never reaches logs/reprs/snapshots.

    ``managed_allowed`` / ``plan`` / ``managed_quota_usd_month`` carry the D3 managed-LLM posture
    resolved alongside the keys (from the org row) so the synchronous resolver + the spend gate can
    decide without another DB hit. ``managed_allowed`` is True only when the deployment runs in
    managed mode AND the org is opted in."""

    org_id: uuid.UUID | None
    provider_keys: dict[str, str] = field(default_factory=dict)  # backend -> key
    engine_key: str | None = None
    managed_allowed: bool = False
    plan: str | None = None
    managed_quota_usd_month: int = 0

    def __repr__(self) -> str:
        return (
            f"OrgKeys(org_id={self.org_id}, "
            f"provider_backends={sorted(self.provider_keys)}, "
            f"engine_key={'set' if self.engine_key else 'unset'}, "
            f"managed_allowed={self.managed_allowed})"
        )


_org_keys_override: ContextVar[OrgKeys | None] = ContextVar(
    "algenta_org_keys_override", default=None
)

_TRUE = {"1", "true", "yes", "on"}


def require_per_tenant_keys() -> bool:
    """True in an explicit multi-tenant deployment, where a missing per-org key must FAIL CLOSED
    instead of borrowing the shared global env key."""
    return os.environ.get("ALGENTA_REQUIRE_PER_TENANT_KEYS", "").strip().lower() in _TRUE


def managed_llm_mode_enabled() -> bool:
    """True if this deployment runs in managed-LLM mode (hosted). Default off (self-host/BYOK).

    Read directly from the environment (like ``require_per_tenant_keys``) so the synchronous key
    resolver can consult it. OFF preserves legacy behavior exactly: the pooled env key is THE key
    for the single tenant; no managed gating, no metering. (Re-exported from ``llm_spend_service``
    for callers that import it there.)"""
    return os.environ.get("ALGENTA_MANAGED_LLM", "").strip().lower() in _TRUE


def set_org_keys_override(keys: OrgKeys | None) -> Token:
    """Bind the request/run-scoped org keys (server-derived from the authenticated org). Returns a
    token the caller MUST reset in a finally, so a pooled async task never inherits another
    request's keys."""
    return _org_keys_override.set(keys)


def reset_org_keys_override(token: Token) -> None:
    _org_keys_override.reset(token)


def current_org_keys() -> OrgKeys | None:
    return _org_keys_override.get()


_KEYRING_SERVICE = "algenta"


def _local_secret(env_name: str | None) -> str | None:
    """Resolve a local (device / self-host) secret named ``env_name``, preferring the OS keychain
    over a plaintext env var so a user can keep BYOK keys out of their shell profile / process env.

    Precedence: OS keychain (``keyring``, service ``algenta``, username == ``env_name``) → env var.
    ``keyring`` is a SOFT dependency — if it's not installed, has no backend, or has no entry, this
    falls through to ``os.environ`` exactly as before (zero behavior change when unused). Opt out of
    the keychain probe entirely with ``ALGENTA_KEYRING=0``."""
    if not env_name:
        return None
    if os.environ.get("ALGENTA_KEYRING", "").strip().lower() not in {"0", "off", "false", "no"}:
        try:
            import keyring  # soft dep — absent on most installs

            secret = keyring.get_password(_KEYRING_SERVICE, env_name)
            if secret:
                return secret
        except Exception:  # noqa: BLE001 — no keyring / no backend / locked → fall back to env
            pass
    return os.environ.get(env_name) or None


def _classify_provider_key(
    api_key_env: str | None, backend: str | None
) -> tuple[str, str | None]:
    """Resolve (key_type, key) for ``backend`` under the D3 3-tier policy. Single source of truth so
    the key and its classification can never disagree (the metering layer trusts the type).

    Precedence:
      1. **BYOK** — the org's own per-backend key (any mode). Customer pays the provider.
      2. strict BYOK-only (``ALGENTA_REQUIRE_PER_TENANT_KEYS=1``) → fail closed (never a shared key).
      3. **managed** (hosted, ``ALGENTA_MANAGED_LLM=1``) — the pooled env key, but ONLY for an
         opted-in org (``managed_allowed``) and only when an env var is named (so the agentic
         sidecar path, which passes ``api_key_env=None``, can never draw the managed key). Metered.
         If managed mode is on but the org isn't allowed / no env key → fail closed.
      4. **self-host** (managed mode off) — the pooled env key is THE key for the single tenant.
         Byte-for-byte the legacy path; not metered.
    """
    keys = _org_keys_override.get()
    # Tier 1: BYOK
    if keys is not None and backend is not None:
        override = keys.provider_keys.get(backend)
        if override:
            return KEY_TYPE_BYOK, override
    # Tier 2: strict multi-tenant — never borrow a shared key
    if require_per_tenant_keys():
        return KEY_TYPE_NONE, None
    # Tier 3: managed pass-through (hosted)
    if managed_llm_mode_enabled():
        if keys is not None and keys.managed_allowed and api_key_env:
            env = os.environ.get(api_key_env) or None
            if env:
                return KEY_TYPE_MANAGED, env
        return KEY_TYPE_NONE, None  # managed mode + not-allowed / no env → fail closed
    # Tier 4: legacy single-tenant self-host / per-device offline. Resolve via the OS keychain first
    # (so a device's BYOK key need not sit in a plaintext env var), then the env var.
    if not api_key_env:
        return KEY_TYPE_NONE, None
    env = _local_secret(api_key_env)
    return (KEY_TYPE_SELF_HOST, env) if env else (KEY_TYPE_NONE, None)


def resolve_provider_api_key(api_key_env: str | None, backend: str | None = None) -> str | None:
    """Resolve the LLM provider key for ``backend`` under the 3-tier policy (see
    :func:`_classify_provider_key`). Returns None so the caller FAILS CLOSED when no key is
    resolvable (strict BYOK-only with no override, or managed mode without an opted-in org)."""
    return _classify_provider_key(api_key_env, backend)[1]


def provider_key_type(api_key_env: str | None, backend: str | None = None) -> str:
    """The tier that :func:`resolve_provider_api_key` would draw from, without exposing the key —
    one of KEY_TYPE_BYOK / KEY_TYPE_MANAGED / KEY_TYPE_SELF_HOST / KEY_TYPE_NONE. The metering layer
    uses this to bill + cap ONLY managed calls."""
    return _classify_provider_key(api_key_env, backend)[0]


def resolve_engine_api_key() -> str | None:
    """Resolve the repository-engine key with the same precedence + multi-tenant fail-closed rule."""
    keys = _org_keys_override.get()
    if keys is not None and keys.engine_key:
        return keys.engine_key
    if require_per_tenant_keys():
        return None
    return _local_secret("ALGENTA_ENGINE_API_KEY") or _local_secret("ALGENTA_API_KEY") or None
