"""One boot window (BOOT_GRACE_S) for a worker in ANY power state, and what it costs.

HISTORY, because this module used to assert the opposite. The original rule reaped a
stopped-and-unregistered VM at once, on the reasoning that a powered-off worker can never
register so the grace window buys nothing. The quota argument for it was real and measured live
2026-08-26: 13 VMs but only 3 registered runners, 10 of them "VM stopped"; centralus
standardDSv5Family sat at 96/140 cores with 80 held by those corpses -- room for 5 workers while
6 checks were QUEUED. Deleting them by hand took quota to 8/140 and the orchestrator provisioned
8 workers within 3 seconds (journal 18:16:00).

It was nonetheless wrong, and 2026-09-16 is the proof. "Stopped means finished" holds only while
bootstraps succeed. That day GitHub raised the self-hosted-runner registration floor to 2.329.0
over a golden image baking 2.327.1, so EVERY worker failed config.sh and powered itself off ~55s
into its own boot. Reaping on sight then turned a fleet outage into a churn engine: the sweep
deleted the corpse, the reconcile loop provisioned a replacement, that one died identically, and
the plane ran roughly one VM per queued job per 90s -- 7 dead workers plus 7 leaked NICs inside
an hour, each ARM delete racing the next create into NicInUse. The operator had to stop the
service by hand to make it stop.

So the grace now covers stopped workers too, and these tests pin BOTH halves: a young VM is
untouched whatever its power state reads as, and a VM past the window is reaped whatever its
power state reads as. The quota cost of holding a corpse for BOOT_GRACE_S is accepted knowingly
(see the constant's comment for the arithmetic); the churn cost of not holding it is not.

Also pinned: power state is an ARM round-trip per VM, so it is asked ONLY for a VM already
condemned, purely to label the reason -- never for every young worker on every poll.
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


def test_a_stopped_worker_inside_the_boot_grace_is_not_reaped(monkeypatch):
    """THE 2026-09-16 fix. Age 30s and powered off: leave it alone.

    This is the exact state every worker was in during the outage -- config.sh had just been
    refused for a runner version below GitHub's floor, bootstrap had fallen through to
    `shutdown -h now`, and the sweep was about to delete it so the loop could build another one
    that died the same way. Reaping here is what turned a fleet outage into a churn storm.
    """
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-1-1", 30)], power={"ci-az-1-1": "stopped"})
    mod.cleanup()
    assert deleted == [], deleted


def test_a_stopped_worker_past_the_boot_grace_is_reaped(monkeypatch):
    """The other half: the grace bounds the corpse, it does not excuse it.

    A stopped VM still holds its full vCPU allocation, so past BOOT_GRACE_S it has to go or the
    2026-08-26 quota starvation comes back (80 of 140 cores held by 10 corpses, 6 checks queued).
    """
    mod = _load(monkeypatch)
    age = mod.BOOT_GRACE_S + 1
    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-1-1", age)], power={"ci-az-1-1": "stopped"})
    mod.cleanup()
    assert [n for n, _ in deleted] == ["ci-az-1-1"], deleted
    assert "stopped-no-runner" in deleted[0][1], deleted[0][1]


def test_deallocated_counts_as_stopped(monkeypatch):
    """Azure reports both; a deallocated VM is labelled the same way once it is reaped."""
    mod = _load(monkeypatch)
    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-1-1", mod.BOOT_GRACE_S + 1)],
                    power={"ci-az-1-1": "deallocated"})
    mod.cleanup()
    assert [n for n, _ in deleted] == ["ci-az-1-1"], deleted
    assert "stopped-no-runner" in deleted[0][1], deleted[0][1]


def test_the_two_reap_windows_cannot_drift_apart(monkeypatch):
    """ORPHAN_AGE_S is DERIVED from BOOT_GRACE_S, and this is why.

    The incident hot-patch this replaced wrote `stopped and age > 720` next to an unregistered
    rule that still fired at 600s. The 720 was therefore dead code: every stopped worker is also
    unregistered, so the 600s rule reaped it first and the grace never applied to anything. A
    constant that silently does nothing is worse than no constant, so pin the relationship.
    """
    mod = _load(monkeypatch)
    assert mod.ORPHAN_AGE_S == mod.BOOT_GRACE_S == 720
    assert mod.BOOT_GRACE_S < mod.MAX_AGE_S


def test_a_booting_vm_is_still_protected(monkeypatch):
    """The case BOOT_GRACE_S exists for: running, not yet registered, young. Reaping this is
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


def test_power_state_is_queried_only_for_a_condemned_vm(monkeypatch):
    """One ARM round-trip per DELETION, not one per young worker per poll.

    The old shape asked every young unregistered VM's power state on every 90s cycle, because
    the answer could reap it early. Now that the answer cannot change the verdict inside the
    grace, asking there is pure cost -- so it is asked only once a VM is already condemned, and
    only to label the reason. Both halves are pinned: a young VM costs nothing, a condemned one
    costs exactly one call.
    """
    mod = _load(monkeypatch)
    calls: list[str] = []

    def spy(n):
        calls.append(n)
        return "running"

    deleted = _wire(mod, monkeypatch,
                    vms=[("ci-az-young", 120), ("ci-az-old", 10_000)])
    monkeypatch.setattr(mod, "vm_power_state", spy)
    mod.cleanup()
    assert [n for n, _ in deleted] == ["ci-az-old"], deleted
    assert "orphan-no-runner" in deleted[0][1], deleted[0][1]
    assert calls == ["ci-az-old"], f"power state queried for a VM inside the grace: {calls}"


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
