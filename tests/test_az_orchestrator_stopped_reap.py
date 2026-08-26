"""A worker that has already powered off must be reaped at once, not after ORPHAN_AGE_S.

A "stopped" (not deallocated) Azure VM still holds its full vCPU quota, so every finished
ephemeral worker pinned 8 vCPU for ten more minutes while being useless. Measured live
2026-08-26: 13 VMs but only 3 registered runners, 10 of them "VM stopped"; centralus
standardDSv5Family sat at 96/140 cores with 80 held by those corpses -- room for 5 workers while
6 checks were QUEUED. Deleting them by hand took quota to 8/140 and the orchestrator provisioned
8 workers within 3 seconds (journal 18:16:00). Same mechanism produced the earlier warm-pool
failures logging "exceeding approved standardDSv5Family Cores quota".

The ORPHAN_AGE_S grace exists for a DIFFERENT case, named in its own comment: a VM still booting
(stock-image boot runs apt-get plus the runner download, 3-6 min, and a 3-min sweep was killing
workers mid-bootstrap). A booting VM is running-but-unregistered. A stopped VM can never
register, so the grace buys nothing there. These tests pin both halves of that distinction --
reaping the dead fast must not start reaping the booting.
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
    spec = importlib.util.spec_from_file_location("az_orch_stopped_reap_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _wire(mod, monkeypatch, *, vms, runners=(), busy=(), power=None):
    """vms: list of (name, age_seconds). Returns the list of deleted (name, reason)."""
    deleted: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "log", lambda m: None)
    monkeypatch.setattr(mod, "runner_names", lambda: set(runners))
    monkeypatch.setattr(mod, "busy_runner_names", lambda: set(busy))
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])
    monkeypatch.setattr(mod, "_sweep_stale_registrations", lambda live: None)
    monkeypatch.setattr(mod, "vm_power_state", lambda n: (power or {}).get(n))
    monkeypatch.setattr(
        mod, "delete_vm",
        lambda name, loc, reason="", was_busy=False: deleted.append((name, reason)))

    now = 1_800_000_000.0
    monkeypatch.setattr(mod.time, "time", lambda: now)
    import time as _t
    live = [(n, _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime(now - age)), "centralus")
            for n, age in vms]
    monkeypatch.setattr(mod, "live_vms", lambda: live)
    # No NICs -- that sweep is covered by its own test module.
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {"value": []})
    return deleted


def test_stopped_and_unregistered_is_reaped_immediately(monkeypatch):
    """THE fix. Age 30s, far inside ORPHAN_AGE_S, but powered off -> gone now."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-1-1", 30)], power={"ci-az-1-1": "stopped"})
    mod.cleanup()
    assert [n for n, _ in deleted] == ["ci-az-1-1"], deleted
    assert "stopped-no-runner" in deleted[0][1], deleted[0][1]


def test_deallocated_counts_as_stopped(monkeypatch):
    """Azure reports both; a deallocated VM is equally never coming back."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-1-1", 30)], power={"ci-az-1-1": "deallocated"})
    mod.cleanup()
    assert [n for n, _ in deleted] == ["ci-az-1-1"], deleted


def test_a_booting_vm_is_still_protected(monkeypatch):
    """The case ORPHAN_AGE_S exists for: running, not yet registered, young. Reaping this is
    the regression that killed wave-2 workers mid-bootstrap -- it must NOT come back."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-1-1", 120)], power={"ci-az-1-1": "running"})
    mod.cleanup()
    assert deleted == [], deleted


def test_unknown_power_state_falls_back_to_the_age_rule(monkeypatch):
    """vm_power_state returns None when the instanceView call fails. Unknown must NOT read as
    stopped -- otherwise one flaky ARM call deletes a healthy booting worker."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, vms=[("ci-az-1-1", 120)], power={})  # -> None
    mod.cleanup()
    assert deleted == [], deleted


def test_a_busy_worker_is_never_reaped_even_if_reported_stopped(monkeypatch):
    """busy wins over everything. Preserves the #898 guarantee unconditionally."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch, vms=[("ci-az-1-1", 30)],
                    runners=["ci-az-1-1"], busy=["ci-az-1-1"],
                    power={"ci-az-1-1": "stopped"})
    mod.cleanup()
    assert deleted == [], deleted


def test_a_registered_idle_worker_is_not_reaped(monkeypatch):
    """Registered means alive and available -- power state is not even consulted."""
    mod = _load(monkeypatch)
    calls: list[str] = []

    def spy(n):
        calls.append(n)
        return "stopped"

    deleted = _wire(mod, monkeypatch, vms=[("ci-az-1-1", 30)], runners=["ci-az-1-1"])
    monkeypatch.setattr(mod, "vm_power_state", spy)
    mod.cleanup()
    assert deleted == [], deleted
    assert calls == [], f"power state queried for a registered VM: {calls}"


def test_power_state_is_not_queried_past_the_grace_window(monkeypatch):
    """Past ORPHAN_AGE_S the age rule already deletes, so the extra per-VM call would be pure
    cost. One call per VM is the only working shape (see vm_power_state), so keep it narrow."""
    mod = _load(monkeypatch)
    calls: list[str] = []

    def spy(n):
        calls.append(n)
        return "running"

    deleted = _wire(mod, monkeypatch, vms=[("ci-az-old", 10_000)])
    monkeypatch.setattr(mod, "vm_power_state", spy)
    mod.cleanup()
    assert [n for n, _ in deleted] == ["ci-az-old"], deleted
    assert "orphan-no-runner" in deleted[0][1], deleted[0][1]
    assert calls == [], f"power state queried outside the decision window: {calls}"


def test_power_state_parses_the_azure_status_code(monkeypatch):
    """Real payload shape from a live instanceView call:
    statuses = [ProvisioningState/succeeded, PowerState/running]."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {"statuses": [
        {"code": "ProvisioningState/succeeded"}, {"code": "PowerState/stopped"}]})
    assert mod.vm_power_state("ci-az-1-1") == "stopped"


def test_power_state_is_none_when_the_call_raises(monkeypatch):
    mod = _load(monkeypatch)

    def boom(*a, **kw):
        raise RuntimeError("502 ProviderError")

    monkeypatch.setattr(mod, "arm", boom)
    assert mod.vm_power_state("ci-az-1-1") is None


def test_power_state_is_none_when_no_powerstate_status_present(monkeypatch):
    """statusOnly-style payloads carry no PowerState entry at all -- must read as unknown."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {"statuses": [
        {"code": "ProvisioningState/succeeded"}]})
    assert mod.vm_power_state("ci-az-1-1") is None
