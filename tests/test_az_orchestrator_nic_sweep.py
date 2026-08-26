"""Regression: the leaked-NIC sweep silently skipped Azure's own default NIC naming form.

`cleanup()`'s sweep derived the owning VM name from a NIC name by stripping `-{region}-nic` (what
nic_path_for() creates) or a trailing `-nic` (legacy). Azure's OWN auto-generated name -- used
whenever a VM is created without an explicit NIC, which is the `az vm create` path this
orchestrator used before the ARM REST rewrite -- is `<vm>VMNic`, with NO hyphen before "nic". It
matched neither form, so `base` stayed None and the NIC was skipped on every pass, forever.

Measured 2026-08-26 in resource group thyn-ci: 53 NICs for 14 VMs, 34 orphaned
(virtualMachine == null), of which **31 were this form** -- e.g.
ci-az-32854312574-97822446727VMNic, belonging to runs long since deleted.

Why it is a throttle and not just clutter: leaked NICs/PIPs occupy per-region quota (the module
already notes the PIP limit of 20), so they cap how many workers can be provisioned. And the
sweep's silence is what hid it -- an unparsed name produced no log line at all, so "sweep ran, 0
swept" and "sweep cannot see 31 NICs" were indistinguishable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"

# Verbatim from `az network nic list -g thyn-ci --query "[?virtualMachine==null].name"`.
REAL_LEAKED = [
    "ci-az-32854312574-97822446727VMNic",
    "ci-az-32853139151-97818619411VMNic",
    "ci-az-32852553062-97816677968VMNic",
    "ci-az-32845926457-97799340534VMNic",
]


def _load(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orch_nic_sweep_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def test_azure_default_vmnic_suffix_is_parsed(monkeypatch):
    """THE regression. Every one of these returned None before the fix."""
    mod = _load(monkeypatch)
    for name in REAL_LEAKED:
        base = mod._nic_base(name)
        assert base is not None, f"unparsed (would leak forever): {name}"
        assert base == name[: -len("VMNic")]
        assert base.startswith("ci-az-")


def test_region_scoped_and_legacy_forms_still_parse(monkeypatch):
    """The two forms that already worked must keep working."""
    mod = _load(monkeypatch)
    assert mod._nic_base("ci-az-123-456-centralus-nic") == "ci-az-123-456"
    assert mod._nic_base("ci-warm-1787764638-eastus2-nic") == "ci-warm-1787764638"
    assert mod._nic_base("ci-az-999-nic") == "ci-az-999"


def test_region_suffix_wins_over_the_legacy_suffix(monkeypatch):
    """Ordering matters: `-eastus2-nic` also ends with `-nic`, so a legacy-first match would
    swallow the region into the VM name and look for a VM that never existed -- leaving a real
    NIC unswept while reporting success."""
    mod = _load(monkeypatch)
    assert mod._nic_base("ci-az-77-88-eastus2-nic") == "ci-az-77-88"


def test_unknown_form_returns_none_rather_than_a_wrong_guess(monkeypatch):
    """Returning a bogus base would be worse than None: `base in vm_names` would be False, so the
    sweep would DELETE a NIC it cannot actually account for."""
    mod = _load(monkeypatch)
    for weird in ("ci-az-someting-else", "ci-az-trailing-NIC", "ci-az-x-nicky"):
        assert mod._nic_base(weird) is None, weird


def test_unparsable_names_are_reported_once_not_silently_skipped(monkeypatch):
    """The silence is what let 31 NICs accumulate. One WARNING per distinct name -- reported, but
    not re-logged every 90s poll."""
    mod = _load(monkeypatch)
    seen: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: seen.append(m))
    monkeypatch.setattr(mod, "REGIONS", [("centralus", "vnet", "subnet")])

    nics = {"value": [
        {"name": "ci-az-unparsable-form", "id": "/nics/ci-az-unparsable-form"},
    ]}

    def fake_arm(method, path, body=None, api=None):
        if method == "GET" and path.endswith("networkInterfaces"):
            return nics
        return {}

    monkeypatch.setattr(mod, "arm", fake_arm)
    monkeypatch.setattr(mod, "live_vms", lambda: [])
    monkeypatch.setattr(mod, "runner_names", lambda: set())
    monkeypatch.setattr(mod, "busy_runner_names", lambda: set())
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])

    mod.cleanup()
    warns = [m for m in seen if "cannot parse NIC name" in m]
    assert len(warns) == 1, f"expected exactly one warning, got {warns}"
    assert "ci-az-unparsable-form" in warns[0]

    seen.clear()
    mod.cleanup()  # second pass: same name must NOT re-log
    assert [m for m in seen if "cannot parse NIC name" in m] == [], "warning repeated every poll"


def test_a_vmnic_whose_vm_is_still_alive_is_never_swept(monkeypatch):
    """Parsing more names must not widen what gets DELETED. A live VM's NIC stays."""
    mod = _load(monkeypatch)
    deleted: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: None)
    monkeypatch.setattr(mod, "REGIONS", [("centralus", "vnet", "subnet")])

    live = "ci-az-32993833334-98257809670"
    nics = {"value": [{"name": f"{live}VMNic", "id": f"/nics/{live}VMNic"}]}

    def fake_arm(method, path, body=None, api=None):
        if method == "GET" and path.endswith("networkInterfaces"):
            return nics
        if method == "DELETE":
            deleted.append(path)
        return {}

    monkeypatch.setattr(mod, "arm", fake_arm)
    monkeypatch.setattr(mod, "live_vms", lambda: [(live, 0.0, "centralus")])
    monkeypatch.setattr(mod, "runner_names", lambda: {live})
    monkeypatch.setattr(mod, "busy_runner_names", lambda: {live})
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])

    mod.cleanup()
    mod.cleanup()  # twice: past the _absent_once two-strike guard
    assert deleted == [], f"swept a live VM's NIC: {deleted}"
