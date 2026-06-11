"""Wave A2: RUNTIME_FALLBACK_MODE=deny must fail closed (no /tmp spill).

The self-hosted/privacy default is ``deny``: when neither ALGENTA_RUNTIME_DIR nor the
default ~/.algenta/runtime is writable, the runtime dir must RAISE rather than silently
spill tenant artifacts to ephemeral storage (/tmp) — which is lost on restart and is
not the durable, access-controlled home tenant data must live in. ``allow`` keeps the
dev/test fallback chain.
"""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_runtime as rt
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    rt._RUNTIME_FALLBACK_CACHE = None
    monkeypatch.delenv("ALGENTA_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("RUNTIME_FALLBACK_MODE", raising=False)
    yield
    rt._RUNTIME_FALLBACK_CACHE = None


def test_deny_raises_instead_of_tmp_spill(monkeypatch):
    monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
    monkeypatch.setattr(rt, "_runtime_dir_writable", lambda _p: False)
    # tripwire: the ephemeral fallback candidates must never be consulted under deny
    monkeypatch.setattr(
        rt, "_runtime_fallback_candidates", lambda: pytest.fail("fallback consulted under deny")
    )
    with pytest.raises(RepositoryIntelligenceError) as exc:
        rt._runtime_dir()
    assert exc.value.code == "repository_runtime_unwritable"
    assert exc.value.details.get("fallback_mode") == "deny"


def test_allow_falls_back_to_candidate(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "allow")
    candidate = tmp_path / "fallback"
    # only the candidate is writable (configured absent, default unwritable)
    monkeypatch.setattr(rt, "_runtime_dir_writable", lambda p: str(p).startswith(str(candidate)))
    monkeypatch.setattr(rt, "_runtime_fallback_candidates", lambda: [candidate])
    assert rt._runtime_dir() == candidate.resolve()


def test_default_mode_allows_fallback(monkeypatch, tmp_path):
    # unset RUNTIME_FALLBACK_MODE => code default is permissive (dev/test)
    candidate = tmp_path / "fallback"
    monkeypatch.setattr(rt, "_runtime_dir_writable", lambda p: str(p).startswith(str(candidate)))
    monkeypatch.setattr(rt, "_runtime_fallback_candidates", lambda: [candidate])
    assert rt._runtime_dir() == candidate.resolve()


def test_configured_dir_used_no_spill_even_under_deny(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
    target = tmp_path / "configured"
    target.mkdir()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(target))
    # real writability check on a real writable dir -> honored, no fallback needed
    assert rt._runtime_dir() == target.resolve()
