"""A job that failed because we deleted its runner must say so, automatically.

Autopsy, 2026-08-26 (Azure activity log + orchestrator log + GitHub job):
    11:52:13  ci-warm-1787745129 pre-booted into the warm pool
    13:03:41  sdk-audit `execution-sweep` starts on it
    13:23:18  virtualMachines/delete Started   (caller = orchestrator SP)
    13:23:18  networkInterfaces/delete FAILED  BadRequest / NicInUse (VM still attached)
    13:23:39  virtualMachines/delete Succeeded
    13:32:42  GitHub reports the job FAILED    <- NINE MINUTES after the VM died

The job log held no error of its own, so the red check pointed at the build. GitHub's
workflow_job `completed` event carries runner_name AND conclusion and we already receive it --
only `queued` was handled. Cross-referencing the deletion ledger makes this self-diagnosing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"


def _load(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orch_attrib_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _capture(mod, monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: lines.append(str(m)))
    return lines


def test_failure_on_a_runner_we_deleted_is_attributed(monkeypatch):
    mod = _load(monkeypatch)
    lines = _capture(mod, monkeypatch)
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {})
    # Reproduce the real sequence: delete the VM, then GitHub reports the failure later.
    mod.delete_vm("ci-warm-1787745129", "centralus", reason="max-age age=5465s", was_busy=False)
    mod._note_completed_job(
        {"id": 98187658902, "conclusion": "failure", "runner_name": "ci-warm-1787745129"},
        "thyn-ai/algenta",
    )
    blob = "\n".join(lines)
    assert "INFRA-KILL ATTRIBUTION" in blob, f"failure was not attributed:\n{blob}"
    assert "98187658902" in blob and "ci-warm-1787745129" in blob
    assert "max-age" in blob, "the deletion REASON must be carried into the attribution"
    assert "do not debug the build" in blob, "must tell the reader where NOT to look"


def test_success_is_never_attributed(monkeypatch):
    mod = _load(monkeypatch)
    lines = _capture(mod, monkeypatch)
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {})
    mod.delete_vm("ci-warm-9", "centralus", reason="idle-drain")
    mod._note_completed_job(
        {"id": 1, "conclusion": "success", "runner_name": "ci-warm-9"}, "thyn-ai/algenta"
    )
    assert not any("INFRA-KILL ATTRIBUTION" in l for l in lines), "attributed a SUCCESSFUL job"


def test_unrelated_failure_is_not_blamed_on_infra(monkeypatch):
    """A genuine build failure on a runner we never touched must stay the developer's problem."""
    mod = _load(monkeypatch)
    lines = _capture(mod, monkeypatch)
    mod._note_completed_job(
        {"id": 2, "conclusion": "failure", "runner_name": "ci-az-never-deleted"},
        "thyn-ai/algenta",
    )
    assert not any("INFRA-KILL" in l for l in lines), "blamed infra for an unrelated failure"


def test_deleting_a_busy_runner_screams_immediately(monkeypatch):
    mod = _load(monkeypatch)
    lines = _capture(mod, monkeypatch)
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {})
    mod.delete_vm("ci-warm-busy", "centralus", reason="max-age", was_busy=True)
    assert any("INFRA-KILL: deleting ci-warm-busy while BUSY" in l for l in lines), \
        "a mid-job delete must be loud at the moment it happens"


def test_ledger_entry_expires(monkeypatch):
    """Stale entries must not mis-attribute a much later, unrelated failure."""
    mod = _load(monkeypatch)
    lines = _capture(mod, monkeypatch)
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {})
    mod.delete_vm("ci-warm-old", "centralus", reason="idle-drain")
    # Age the entry past the TTL, then trigger the pruning path via another delete.
    mod._deleted["ci-warm-old"]["at"] -= mod._DELETED_TTL_S + 60
    mod.delete_vm("ci-warm-new", "centralus", reason="idle-drain")
    assert "ci-warm-old" not in mod._deleted, "expired ledger entry was not pruned"
    mod._note_completed_job(
        {"id": 3, "conclusion": "failure", "runner_name": "ci-warm-old"}, "thyn-ai/algenta"
    )
    assert not any("ATTRIBUTION" in l for l in lines), "mis-attributed via an expired entry"
