"""Tests for infra/ci/az_orchestrator.py's warm-pool floor logic.

Isolates `manage_warm_pool` from its real GitHub/Azure dependencies (patched out) and pins the
one behavioral contract this change adds -- a permanent warm floor that is never drained to
zero, so the first job after any quiet period still gets warm-pool pickup speed instead of
paying a full cold boot.
"""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"


class _SyncThread:
    """Runs the target synchronously so provision_worker's dispatch is deterministic to assert
    on, instead of racing a real background thread."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        if self._target is not None:
            self._target(*self._args)


def _load_orchestrator(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orchestrator_warm_pool_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    # STATE = "/var/lib/az-orch" is a hardcoded absolute path the real module
    # os.makedirs()'s unconditionally at import time; only root can write there off the
    # real ci-orch VM, so the makedirs call is patched out for the duration of the import.
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _make_vm(name, loc="eastus"):
    return (name, "Standard_D8s_v3", loc)


def _wire(mod, monkeypatch, *, idle: bool, deleted: list, provisioned: list):
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)  # writes to a VM-only real path
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])
    monkeypatch.setattr(mod, "gh", lambda *a, **kw: {"runners": []})
    monkeypatch.setattr(mod, "_read_last_activity", lambda: 0.0 if idle else mod.time.time())
    monkeypatch.setattr(mod, "delete_vm", lambda name, loc, **kw: deleted.append(name))
    monkeypatch.setattr(mod, "provision_worker", lambda name: provisioned.append(name))
    monkeypatch.setattr(threading, "Thread", _SyncThread)
    monkeypatch.setattr(mod, "_inflight", set())
    monkeypatch.setattr(mod, "_inflight_names", set())


def test_idle_drain_keeps_the_floor_never_drains_to_zero(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    monkeypatch.setattr(mod, "WARM_FLOOR", 1)
    monkeypatch.setattr(mod, "WARM_MIN", 3)
    deleted, provisioned = [], []
    _wire(mod, monkeypatch, idle=True, deleted=deleted, provisioned=provisioned)
    warm_vms = [_make_vm("ci-warm-1"), _make_vm("ci-warm-2"), _make_vm("ci-warm-3")]

    mod.manage_warm_pool(warm_vms)

    # Exactly 2 of the 3 warm VMs are deleted (drained down to the floor); the floor VM
    # itself is never in the deleted set.
    assert len(deleted) == 2
    assert "ci-warm-1" not in deleted   # warm[:WARM_FLOOR] is kept
    # Already at the floor after the drain -> no new provisioning needed.
    assert provisioned == []


def test_idle_below_floor_replenishes_to_the_floor_not_the_burst_target(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    monkeypatch.setattr(mod, "WARM_FLOOR", 2)
    monkeypatch.setattr(mod, "WARM_MIN", 5)
    deleted, provisioned = [], []
    _wire(mod, monkeypatch, idle=True, deleted=deleted, provisioned=provisioned)

    mod.manage_warm_pool([])   # nothing warm at all, idle

    assert deleted == []
    # Replenishes toward the FLOOR (2), not the burst target WARM_MIN (5).
    assert len(provisioned) == 1


def test_active_bursts_to_warm_min_not_just_the_floor(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    monkeypatch.setattr(mod, "WARM_FLOOR", 1)
    monkeypatch.setattr(mod, "WARM_MIN", 4)
    deleted, provisioned = [], []
    _wire(mod, monkeypatch, idle=False, deleted=deleted, provisioned=provisioned)
    warm_vms = [_make_vm("ci-warm-1")]   # already at the floor, but NOT idle

    mod.manage_warm_pool(warm_vms)

    assert deleted == []   # no drain while active
    assert len(provisioned) == 1   # tops up toward WARM_MIN (4), past the floor (1)


def test_warm_floor_is_capped_at_warm_min_even_if_env_requests_more(monkeypatch):
    monkeypatch.setenv("AZ_ORCH_WARM", "2")
    monkeypatch.setenv("AZ_ORCH_WARM_FLOOR", "10")   # a misconfigured floor above the burst target
    mod = _load_orchestrator(monkeypatch)
    assert mod.WARM_FLOOR == 2   # min(WARM_MIN, requested floor) -- never exceeds the burst target
