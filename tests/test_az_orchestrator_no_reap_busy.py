"""Regression: a runner that is BUSY executing a job must never be reaped.

cleanup()'s age cap and manage_warm_pool()'s idle drain both used to delete VMs without
consulting busy state:

  * `or age > MAX_AGE_S` fired unconditionally. A warm worker's age clock starts when it is
    PRE-BOOTED, not when it picks up work, so the longer it waited in the pool the less
    budget remained for whatever job it accepted. Killed live 2026-08-26:
    ci-warm-1787745129 pre-booted 11:52:13, took sdk-audit's execution-sweep at 13:03:41,
    deleted 13:23:18 ("age=5465s, runner=aged") -- 20 min into a real build, surfacing as a
    build failure rather than as an infrastructure kill.
  * the idle drain sliced purely by position (`warm[WARM_FLOOR:]`), so a busy warm worker
    could be deleted just for sorting past the floor.
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
    spec = importlib.util.spec_from_file_location("az_orch_noreap_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _runners(mod, monkeypatch, entries):
    """entries: list of (name, busy)."""
    payload = {"runners": [{"name": n, "busy": b} for n, b in entries]}
    monkeypatch.setattr(mod, "gh", lambda *a, **kw: payload)
    monkeypatch.setattr(mod, "runner_names", lambda: {n for n, _ in entries})


def test_aged_but_busy_vm_is_not_reaped(monkeypatch):
    mod = _load(monkeypatch)
    deleted = []
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "delete_vm", lambda n, l: deleted.append(n))
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {"value": []})
    # Pre-booted well past MAX_AGE_S (90min) and mid-job -- the exact live failure.
    monkeypatch.setattr(mod, "live_vms", lambda: [("ci-warm-1", "2000-01-01T00:00:00", "centralus")])
    _runners(mod, monkeypatch, [("ci-warm-1", True)])
    monkeypatch.setattr(mod, "_inflight", set())
    monkeypatch.setattr(mod, "_inflight_names", set())

    mod.cleanup()

    assert deleted == [], f"reaped a BUSY runner mid-job: {deleted}"


def test_aged_and_idle_vm_is_still_reaped(monkeypatch):
    """The leak guard must keep working -- the fix must not disable age reaping entirely."""
    mod = _load(monkeypatch)
    deleted = []
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "delete_vm", lambda n, l: deleted.append(n))
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {"value": []})
    monkeypatch.setattr(mod, "live_vms", lambda: [("ci-warm-2", "2000-01-01T00:00:00", "centralus")])
    _runners(mod, monkeypatch, [("ci-warm-2", False)])
    monkeypatch.setattr(mod, "_inflight", set())
    monkeypatch.setattr(mod, "_inflight_names", set())

    mod.cleanup()

    assert deleted == ["ci-warm-2"], "aged IDLE vm must still be reaped (leak guard)"


def test_idle_drain_never_deletes_a_busy_warm_worker(monkeypatch, tmp_path):
    mod = _load(monkeypatch)
    deleted = []
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "delete_vm", lambda n, l: deleted.append(n))
    # STATE is a root-only absolute path on the real ci-orch host; manage_warm_pool writes
    # last_activity there whenever anything is busy.
    monkeypatch.setattr(mod, "STATE", str(tmp_path))
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])
    monkeypatch.setattr(mod, "_read_last_activity", lambda: 0.0)   # force idle
    monkeypatch.setattr(mod, "WARM_FLOOR", 1)
    monkeypatch.setattr(mod, "WARM_MIN", 1)
    monkeypatch.setattr(mod, "_inflight", set())
    monkeypatch.setattr(mod, "_inflight_names", set())
    # busy worker sorts LAST, i.e. inside the old positional drain slice.
    vms = [("ci-warm-a", "2099-01-01T00:00:00", "centralus"),
           ("ci-warm-b", "2099-01-01T00:00:00", "centralus")]
    _runners(mod, monkeypatch, [("ci-warm-a", False), ("ci-warm-b", True)])

    mod.manage_warm_pool(vms)

    assert "ci-warm-b" not in deleted, f"idle drain deleted a BUSY warm worker: {deleted}"
