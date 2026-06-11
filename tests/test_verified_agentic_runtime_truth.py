"""Wave B4: a live verified_agentic decision plan must be backed by a REAL Cline runtime,
never the offline stub. _assert_live_runtime rejects any result explicitly marked stub /
offline-contract; absent markers (unit-test mocks) pass; an offline-contract test opts out."""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_verified_agentic as va
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)


@pytest.fixture(autouse=True)
def _clear_run_class(monkeypatch):
    monkeypatch.delenv("ALGENTA_RUN_CLASS", raising=False)


def test_live_runtime_passes_without_or_with_real_markers():
    va._assert_live_runtime({"status": "completed"})  # no markers -> treated as live
    va._assert_live_runtime({"runtime": {"kind": "cline", "is_stub": False}})


@pytest.mark.parametrize(
    "result",
    [
        {"runtime": {"is_stub": True}},
        {"runtime": {"offline_contract_only": True}},
        {"artifacts": {"offline_contract_only": True}},
        {"terminal_state": "offline_contract_only"},
    ],
)
def test_stub_or_offline_run_is_rejected(result):
    with pytest.raises(RepositoryIntelligenceError) as exc:
        va._assert_live_runtime(result)
    assert exc.value.code == "repository_agent_runtime_not_live"
    assert exc.value.status_code == 502


def test_offline_contract_test_opts_out(monkeypatch):
    monkeypatch.setenv("ALGENTA_RUN_CLASS", "offline_contract_only")
    # under the explicit offline-contract run class, a stub result is allowed (it's a test)
    va._assert_live_runtime({"runtime": {"is_stub": True}, "terminal_state": "offline_contract_only"})
