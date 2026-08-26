"""The stale-runner-registration sweep: prune dead registrations, never a live one.

Ephemeral workers leave their registration behind when the VM is deleted, and nothing removed
them. Measured 2026-08-26 on thyn-ai: 32 registrations for 6 online runners (21 stale
ci-az-/ci-warm- plus 5 retired blacksmith entries), growing monotonically.

Deleting the WRONG registration is strictly worse than keeping a stale one: GitHub cancels a job
whose runner registration disappears. So every test below is really about what must NOT be
deleted -- the one test asserting a deletion exists mostly to prove the others aren't vacuous.
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
    spec = importlib.util.spec_from_file_location("az_orch_reg_sweep_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _wire(mod, monkeypatch, runners):
    """Serve `runners` from all_runners(); record every DELETE the sweep issues."""
    deleted: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: None)
    monkeypatch.setattr(mod, "all_runners", lambda: runners)

    def fake_gh(path, method="GET", body=None):
        if method == "DELETE":
            deleted.append(path)
        return {}

    monkeypatch.setattr(mod, "gh", fake_gh)
    return deleted


def _runner(name, *, status="offline", busy=False, rid=1):
    return {"name": name, "status": status, "busy": busy, "id": rid}


def test_stale_registration_with_no_live_vm_is_pruned(monkeypatch):
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [_runner("ci-az-111-222", rid=42)])

    mod._sweep_stale_registrations(set())

    assert deleted == ["orgs/thyn-ai/actions/runners/42"], deleted


def test_online_runner_is_never_pruned(monkeypatch):
    """An online runner may be about to accept work."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [_runner("ci-az-111-222", status="online")])
    mod._sweep_stale_registrations(set())
    assert deleted == [], deleted


def test_busy_runner_is_never_pruned(monkeypatch):
    """Belt and braces: busy implies mid-job even if status were reported oddly."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [_runner("ci-az-111-222", status="offline", busy=True)])
    mod._sweep_stale_registrations(set())
    assert deleted == [], deleted


def test_registration_of_a_live_vm_is_never_pruned(monkeypatch):
    """The decisive guard. A VM that exists still owns its registration even while offline
    (rebooting, or between jobs) -- pruning it would strand the worker."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [_runner("ci-az-111-222")])
    mod._sweep_stale_registrations({"ci-az-111-222"})
    assert deleted == [], deleted


def test_foreign_runners_are_never_pruned(monkeypatch):
    """ci-orch is itself a runner (repo-level, which is why an org-only listing does not even show
    it), and other systems register their own. Only this fleet's own prefixes are in scope."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [
        _runner("ci-orch", rid=1),
        _runner("blacksmith-01m0y1xzqqddwyqm29wqymk875-4vcpu", rid=2),
        _runner("some-other-teams-runner", rid=3),
    ])
    mod._sweep_stale_registrations(set())
    assert deleted == [], deleted


def test_warm_workers_are_in_scope(monkeypatch):
    """16 of the 21 stale entries measured were ci-warm-, so the prefix guard must cover both."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [_runner("ci-warm-1787682004", rid=7)])
    mod._sweep_stale_registrations(set())
    assert deleted == ["orgs/thyn-ai/actions/runners/7"], deleted


def test_a_listing_failure_is_not_fatal(monkeypatch):
    """cleanup() runs this every reconcile pass; a transient API error must not take the
    orchestrator's poll loop down or abort the sweeps that already ran before it."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda m: None)

    def boom():
        raise RuntimeError("network blip")

    monkeypatch.setattr(mod, "all_runners", boom)
    mod._sweep_stale_registrations(set())  # must simply return


def test_a_failed_delete_does_not_abort_the_remaining_prunes(monkeypatch):
    """One 422/404 must not strand every later stale registration for good."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda m: None)
    monkeypatch.setattr(mod, "all_runners", lambda: [
        _runner("ci-az-a", rid=1), _runner("ci-az-b", rid=2), _runner("ci-az-c", rid=3),
    ])
    seen: list[int] = []

    def flaky_gh(path, method="GET", body=None):
        if method == "DELETE":
            rid = int(path.rsplit("/", 1)[-1])
            seen.append(rid)
            if rid == 2:
                raise RuntimeError("422 unprocessable")
        return {}

    monkeypatch.setattr(mod, "gh", flaky_gh)
    mod._sweep_stale_registrations(set())

    assert seen == [1, 2, 3], f"a failed delete aborted the loop: {seen}"


def test_mixed_fleet_prunes_only_the_dead(monkeypatch):
    """End-to-end shape of the real measured fleet: a few live, many stale, foreign entries."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, [
        _runner("ci-az-live-1", status="online", busy=True, rid=1),   # working
        _runner("ci-az-live-2", rid=2),                               # offline but VM exists
        _runner("ci-warm-dead-1", rid=3),                             # stale
        _runner("ci-az-dead-2", rid=4),                               # stale
        _runner("ci-orch", rid=5),                                    # foreign
    ])
    mod._sweep_stale_registrations({"ci-az-live-1", "ci-az-live-2"})
    assert sorted(deleted) == [
        "orgs/thyn-ai/actions/runners/3", "orgs/thyn-ai/actions/runners/4",
    ], deleted
