"""B10 PR11b (decision-engine side): the per-tenant LLM provider key the engine sends to the
agent-core sidecar in task_spec.engine.

_agent_provider_key_fields() sends the org OVERRIDE only (never the decision-engine env key — the
sidecar keeps its own env as the pooled fallback), keyed by the agent's backend, and sets the
require flag in multi-tenant so the sidecar fails closed. Pairs with the Algenta-side plumbing that
prefers task_spec.engine.provider_api_key over the sidecar env.
"""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.services import tenant_keys as tk
from apps.api_server.services.repository_intelligence_verified_agentic import (
    _agent_provider_key_fields,
)
from apps.api_server.services.tenant_keys import OrgKeys


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("ALGENTA_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)


def _override(provider_keys: dict[str, str]):
    return tk.set_org_keys_override(OrgKeys(org_id=uuid.uuid4(), provider_keys=provider_keys))


def test_single_tenant_no_override_sends_nothing():
    # Sidecar uses its own pooled env key; nothing is threaded.
    assert _agent_provider_key_fields() == {}


def test_override_for_agent_backend_is_sent():
    token = _override({"anthropic": "org-anthropic"})  # default agent backend = anthropic
    try:
        assert _agent_provider_key_fields() == {"provider_api_key": "org-anthropic"}
    finally:
        tk.reset_org_keys_override(token)


def test_override_for_a_different_backend_is_not_sent():
    # Org brought an OpenAI key but the agent runs anthropic -> not its key, send nothing.
    token = _override({"openai": "org-openai"})
    try:
        assert _agent_provider_key_fields() == {}
    finally:
        tk.reset_org_keys_override(token)


def test_respects_configured_agent_provider(monkeypatch):
    monkeypatch.setenv("ALGENTA_AGENT_PROVIDER", "openai")
    token = _override({"openai": "org-openai", "anthropic": "unused"})
    try:
        assert _agent_provider_key_fields() == {"provider_api_key": "org-openai"}
    finally:
        tk.reset_org_keys_override(token)


def test_multitenant_sets_require_flag_even_without_override(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    # No override -> no key, but the require flag tells the sidecar to fail closed (no env borrow).
    assert _agent_provider_key_fields() == {"require_provider_api_key": True}


def test_multitenant_with_override_sends_key_and_require(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    token = _override({"anthropic": "org-anthropic"})
    try:
        assert _agent_provider_key_fields() == {
            "provider_api_key": "org-anthropic",
            "require_provider_api_key": True,
        }
    finally:
        tk.reset_org_keys_override(token)
