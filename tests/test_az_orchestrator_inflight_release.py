"""Regression: cleanup() must release job claims whose worker is gone.

_inflight holds claimed job IDs so two dispatch paths cannot double-provision one job. It
used to be discarded from ONLY on provisioning failure, so every SUCCESSFUL dispatch leaked
its ID forever. Because every admission check gates on
``len(vms) + len(_inflight) >= MAX_CONCURRENCY``, the set grew monotonically until it alone
hit the cap -- after which every new job was refused (`dispatched=False`) and the fleet
drained to zero while jobs queued. Observed live 2026-08-26.
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
    spec = importlib.util.spec_from_file_location("az_orch_inflight_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _wire(mod, monkeypatch, *, vms):
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "runner_names", lambda: set())
    monkeypatch.setattr(mod, "live_vms", lambda: vms)
    monkeypatch.setattr(mod, "delete_vm", lambda *a, **kw: None)
    # cleanup()'s trailing nic sweep is a live ARM call; stub it to an empty listing.
    monkeypatch.setattr(mod, "arm", lambda *a, **kw: {"value": []})
    # cleanup() also queries GitHub for BUSY runners (added when busy runners stopped being
    # reaped). Unstubbed that is a REAL HTTPS call which 401s under the fake test token.
    monkeypatch.setattr(mod, "gh", lambda *a, **kw: {"runners": []})


def test_claim_for_a_vanished_worker_is_released(monkeypatch):
    mod = _load(monkeypatch)
    # Job 555's VM is gone (finished). Its claim must not hold a slot forever.
    _wire(mod, monkeypatch, vms=[])
    monkeypatch.setattr(mod, "_inflight", {555})
    monkeypatch.setattr(mod, "_inflight_names", set())

    mod.cleanup()

    assert 555 not in mod._inflight, "finished job's claim leaked -> permanent capacity loss"


def test_claim_is_kept_while_its_vm_is_still_live(monkeypatch):
    mod = _load(monkeypatch)
    # run_id 900, job_id 777 -> the claim is still doing its job; releasing it early would
    # let a second dispatch path double-provision the same job.
    _wire(mod, monkeypatch, vms=[("ci-az-900-777", "2099-01-01T00:00:00", "centralus")])
    monkeypatch.setattr(mod, "_inflight", {777})
    monkeypatch.setattr(mod, "_inflight_names", set())

    mod.cleanup()

    assert 777 in mod._inflight, "released a claim whose worker is still alive"


def test_claim_is_kept_during_the_provisioning_window(monkeypatch):
    mod = _load(monkeypatch)
    # VM not visible yet (ARM read-after-write lag) but the name is protected in
    # _inflight_names -- the claim must survive, else the job is dispatched twice.
    _wire(mod, monkeypatch, vms=[])
    monkeypatch.setattr(mod, "_inflight", {888})
    monkeypatch.setattr(mod, "_inflight_names", {"ci-az-901-888"})

    mod.cleanup()

    assert 888 in mod._inflight, "released a claim still inside the provisioning window"


def test_saturated_inflight_recovers_instead_of_wedging_forever(monkeypatch):
    """The live failure mode: _inflight alone at MAX_CONCURRENCY with an EMPTY fleet, so
    _dispatch_job refuses everything. After cleanup() the fleet must accept work again."""
    mod = _load(monkeypatch)
    _wire(mod, monkeypatch, vms=[])
    monkeypatch.setattr(mod, "MAX_CONCURRENCY", 20)
    monkeypatch.setattr(mod, "_inflight", set(range(1000, 1020)))  # 20 dead claims
    monkeypatch.setattr(mod, "_inflight_names", set())

    # Pre-condition: wedged -- a brand new job is refused despite zero live VMs.
    assert mod._dispatch_job({"id": 4242, "run_id": 1}, []) is False

    mod.cleanup()

    assert mod._inflight == set(), "dead claims survived cleanup"
    # Post-condition: dispatch is possible again. Patch the spawn so nothing real is created.
    monkeypatch.setattr(mod.threading, "Thread", lambda *a, **kw: type("T", (), {"start": lambda s: None})())
    assert mod._dispatch_job({"id": 4242, "run_id": 1}, []) is True
