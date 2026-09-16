"""The stopped-but-registered reaper gap: a registration is not evidence of life.

WHAT THE GAP WAS. cleanup() had exactly two ways to condemn a worker:

    (unregistered and age > BOOT_GRACE_S) or age > MAX_AGE_S

`unregistered` is the only term that fires before MAX_AGE_S. So a worker that powered itself
off AFTER registering -- which is the bootstrap's own SUCCESS path, `run.sh` returns and the
script ends in `shutdown -h now` while GitHub still lists the runner -- matched neither term
and survived to MAX_AGE_S: 90 minutes of 8 pinned vCPU per corpse.

Measured live 2026-09-16 after the restart burst that followed the runner-version fix (#997):
15 of 19 VMs in the resource group were in exactly this state. That is 120 vCPU held by
machines that could never run another job, against per-family caps of 10 cores in most regions,
with checks sitting queued behind them. The reaper was not broken; it was blind, and the thing
it treated as proof of life was proof only that a life had started.

THE FIX. Past the boot grace, a worker seen stopped/deallocated on TWO CONSECUTIVE polls at
least STOPPED_CONFIRM_S apart is reaped regardless of its registration -- and its registration
is deleted FIRST, so the org runner list can never again assert a runner with no machine behind
it. Both actions are logged.

WHY THE GRACE STILL APPLIES. test_az_orchestrator_stopped_reap.py pins the other half of
2026-09-16: reaping stopped workers on sight turned a fleet outage into a provision/delete
storm (7 dead workers plus 7 leaked NICs in an hour, every ARM delete racing the next create
into NicInUse). This rule therefore reaps at BOOT_GRACE_S + one confirming poll, not on sight.
A worker self-powering-off 55s into a broken bootstrap is still held for the whole window.

WHY TWO POLLS. One instanceView read is allowed to be wrong -- ARM returns stale power states,
and a worker rebooting between two jobs is genuinely stopped for a moment. Two agreeing reads
a minute apart are not. Same guard shape the leaked-nic and leaked-disk sweeps already use.

BUSY STAYS ABSOLUTE. A runner GitHub reports mid-job is never reaped by this path or any other,
and its registration is never deleted -- GitHub cancels a job whose registration disappears.
That is the #898 guarantee and these tests re-pin it against the new rule specifically, because
the new rule is the first one that deletes a registration as part of reaping.
"""

from __future__ import annotations

import importlib.util
import re
import time as _time
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"

_T0 = 1_800_000_000.0


def _load(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orch_stopped_registered_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


class _Clock:
    """A clock the test advances by hand, so "two polls 90s apart" is a real interval.

    cleanup() reads time.time() once per pass and computes every age from it, so advancing this
    between two cleanup() calls reproduces two reconcile cycles exactly -- including the VM
    ageing, which is what makes the second cycle cross BOOT_GRACE_S."""

    def __init__(self, t0=_T0):
        self.t = t0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class _Plane:
    """A fake Azure + GitHub pair, recording every call in the order it happened.

    `events` is the assertion surface: ordering between the registration DELETE and the VM
    DELETE is the whole point of the fix, so it has to be observable rather than inferred.
    """

    def __init__(self, mod, monkeypatch, *, vms, runners=(), busy=(), power=None):
        self.mod = mod
        self.events: list[str] = []
        self.logs: list[str] = []
        self.clock = _Clock()
        # runners: [(name, id)] -- the org registration list. Ids are real ints so the DELETE
        # path under test has something to address; a None id is its own test case below.
        self.runners = [{"name": n, "id": i, "busy": n in busy} for n, i in runners]
        self.power = dict(power or {})
        # vms: [(name, created_epoch)] -- absolute, so the age grows as the clock advances.
        live = [(n, _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime(c)), "centralus")
                for n, c in vms]

        monkeypatch.setattr(mod, "log", lambda m: self.logs.append(m))
        monkeypatch.setattr(mod, "live_vms", lambda: list(live))
        monkeypatch.setattr(mod, "queued_jobs", lambda: [])
        monkeypatch.setattr(mod, "_sweep_stale_registrations", lambda live_names: None)
        monkeypatch.setattr(mod, "gh", self._gh)
        monkeypatch.setattr(mod, "arm", self._arm)
        monkeypatch.setattr(mod, "delete_vm", self._delete_vm)
        monkeypatch.setattr(mod.time, "time", self.clock)

    # -- GitHub -------------------------------------------------------------------------
    def _gh(self, path, method="GET", body=None):
        self.events.append(f"gh {method} {path}")
        if method == "DELETE":
            rid = int(path.rsplit("/", 1)[-1])
            self.runners = [r for r in self.runners if r["id"] != rid]
            return {}
        # `[&?]page=` not `page=`: the query also carries `per_page=100`, and a bare `page=`
        # search matches inside it first -- which silently returns an empty page and reads as
        # "no registrations at all" rather than as a broken test harness.
        page = int(re.search(r"[&?]page=(\d+)", path).group(1))
        chunk = self.runners[(page - 1) * 100: page * 100]
        return {"runners": chunk}

    # -- Azure ----------------------------------------------------------------------------
    def _arm(self, method, path, body=None, api="2023-07-01"):
        self.events.append(f"arm {method} {path.rsplit('/providers/', 1)[-1]}")
        if path.endswith("/instanceView"):
            state = self.power.get(path.split("/")[-2])
            statuses = [{"code": "ProvisioningState/succeeded"}]
            if state:
                statuses.append({"code": f"PowerState/{state}"})
            return {"statuses": statuses}
        return {"value": []}

    def _delete_vm(self, name, location, reason="", was_busy=False):
        self.events.append(f"delete_vm {name} reason={reason} was_busy={was_busy}")

    # -- helpers --------------------------------------------------------------------------
    def instance_view_calls(self):
        return [e for e in self.events if e.endswith("/instanceView")]

    def runner_deletes(self):
        return [e for e in self.events if e.startswith("gh DELETE")]

    def vm_deletes(self):
        return [e for e in self.events if e.startswith("delete_vm")]

    def cleanup(self):
        self.events.clear()
        self.logs.clear()
        self.mod.cleanup()


def _past_grace(mod, extra=1):
    """A created-at epoch that puts the worker `extra` seconds past the boot grace at _T0."""
    return _T0 - mod.BOOT_GRACE_S - extra


# --------------------------------------------------------------------------- the gap itself


def test_a_stopped_registered_worker_past_the_grace_is_reaped_on_the_second_poll(monkeypatch):
    """THE FIX. Registered, powered off, past BOOT_GRACE_S: two polls and it is gone.

    Before this, the same worker sat until MAX_AGE_S -- 90 minutes of 8 vCPU that could never
    run another job, times 15 of 19 VMs on 2026-09-16.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})

    plane.cleanup()  # sighting 1/2
    assert plane.vm_deletes() == [], plane.events
    assert plane.runner_deletes() == [], plane.events

    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()  # sighting 2/2 -> confirmed
    assert [e.split()[1] for e in plane.vm_deletes()] == ["ci-az-1-1"], plane.events
    assert "stopped-registered" in plane.vm_deletes()[0], plane.vm_deletes()


def test_the_registration_is_deleted_before_the_vm(monkeypatch):
    """Ordering is the fix, not a detail.

    Deleting the VM first leaves a window in which the org runner list asserts a runner that
    has no machine behind it -- the stale fact cleanup() itself reads as "alive". Registration
    first means the two can never disagree, and GitHub cannot dispatch into the gap.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()

    order = [e for e in plane.events if e.startswith(("gh DELETE", "delete_vm"))]
    assert order[0] == "gh DELETE orgs/thyn-ai/actions/runners/101", order
    assert order[1].startswith("delete_vm ci-az-1-1"), order


def test_both_actions_are_logged(monkeypatch):
    """The task is explicit that both are logged: a reap that frees quota silently is a reap
    nobody can distinguish from a churn storm when it shows up in the journal."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()

    blob = "\n".join(plane.logs)
    assert "deleted runner registration ci-az-1-1 (id=101)" in blob, plane.logs
    assert "deleting ci-az-1-1" in blob and "stopped-registered" in blob, plane.logs


def test_deallocated_confirms_the_same_way(monkeypatch):
    """Azure reports both; a deallocated worker is the cheaper corpse but the same verdict."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "deallocated"})
    plane.cleanup()
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()
    assert "stopped-registered" in plane.vm_deletes()[0], plane.vm_deletes()


# --------------------------------------------------------------------- the two-poll guard


def test_one_stopped_sighting_inside_the_grace_changes_nothing(monkeypatch):
    """A worker self-powering-off 55s into a broken bootstrap must NOT be reaped early.

    This is the 2026-09-16 churn storm (see test_az_orchestrator_stopped_reap.py): reaping on
    sight made the reconcile loop build a replacement that died identically, one VM per queued
    job per 90s. The registration makes no difference to that argument, so the grace still
    covers a registered worker too.

    Polled only while the worker is INSIDE the grace. Past it the new rule is supposed to fire
    -- that is the first test in this file -- so driving the clock further here would assert
    against the fix rather than for the grace.
    """
    mod = _load(monkeypatch)
    for start_age in (30, mod.BOOT_GRACE_S - 1):
        plane = _Plane(mod, monkeypatch,
                       vms=[("ci-az-1-1", _T0 - start_age)],
                       runners=[("ci-az-1-1", 101)],
                       power={"ci-az-1-1": "stopped"})
        polls = 0
        while start_age + polls * mod.RECONCILE_S <= mod.BOOT_GRACE_S:
            plane.cleanup()
            age = start_age + polls * mod.RECONCILE_S
            assert plane.vm_deletes() == [], f"start={start_age} age={age}: {plane.events}"
            assert plane.runner_deletes() == [], f"start={start_age} age={age}: {plane.events}"
            polls += 1
            plane.clock.advance(mod.RECONCILE_S)
        assert polls >= 1, start_age


def test_the_second_sighting_must_be_a_full_confirm_window_later(monkeypatch):
    """Two cleanup() calls inside the same minute are ONE observation, not two.

    RECONCILE_S is 90s so this cannot happen in production today -- but cleanup() is not
    contractually reconcile-only, and one stale instanceView read must never be enough to
    delete a VM GitHub still lists as a runner.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    plane.clock.advance(mod.STOPPED_CONFIRM_S - 1)
    plane.cleanup()
    assert plane.vm_deletes() == [], plane.events
    plane.clock.advance(1)
    plane.cleanup()
    assert [e.split()[1] for e in plane.vm_deletes()] == ["ci-az-1-1"], plane.events


def test_the_two_sightings_must_be_consecutive(monkeypatch):
    """A running sighting in between resets the streak.

    Without the reset, "two stopped sightings ever" would condemn a worker that rebooted itself
    and came back -- and a worker between two jobs is genuinely stopped for a moment.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()                                   # sighting 1
    plane.clock.advance(mod.RECONCILE_S)
    plane.power["ci-az-1-1"] = "running"
    plane.cleanup()                                   # streak broken
    plane.clock.advance(mod.RECONCILE_S)
    plane.power["ci-az-1-1"] = "stopped"
    plane.cleanup()                                   # sighting 1 again, NOT 2
    assert plane.vm_deletes() == [], plane.events
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()                                   # now confirmed
    assert [e.split()[1] for e in plane.vm_deletes()] == ["ci-az-1-1"], plane.events


def test_an_unknown_power_state_is_not_a_stopped_sighting(monkeypatch):
    """vm_power_state returns None when instanceView fails. Unknown must never read as stopped,
    or one flaky ARM call deletes a healthy registered worker."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={})  # no PowerState status at all -> None
    for _ in range(4):
        plane.cleanup()
        plane.clock.advance(mod.RECONCILE_S)
    assert plane.vm_deletes() == [], plane.events


def test_the_streak_dict_is_pruned_when_a_vm_goes_away(monkeypatch):
    """Unbounded per-worker state is how _inflight once wedged the whole plane at MAX_CONCURRENCY.

    A recycled name must also not inherit a dead worker's sighting 1/2 -- that would let a fresh
    VM be condemned on one observation of its own.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    assert mod._stopped_seen == {"ci-az-1-1": plane.clock.t}, mod._stopped_seen
    plane.mod.live_vms = lambda: []  # the VM is gone (deleted by something else)
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()
    assert mod._stopped_seen == {}, mod._stopped_seen


# ------------------------------------------------------------------------- busy protection


def test_a_busy_stopped_registered_worker_is_never_reaped(monkeypatch):
    """BUSY WINS, unconditionally, over the new rule too.

    The new rule is the first reaper that deletes a registration as part of reaping, so this is
    the guard that matters most: GitHub cancels a job whose runner registration disappears.
    The #898 incident was an age cap killing sdk-audit's execution-sweep 20 minutes into a
    build and reporting it as a build failure.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-warm-1", _T0 - 4 * mod.MAX_AGE_S)],
                   runners=[("ci-warm-1", 101)], busy=["ci-warm-1"],
                   power={"ci-warm-1": "stopped"})
    for _ in range(4):
        plane.cleanup()
        plane.clock.advance(mod.RECONCILE_S)
    assert plane.vm_deletes() == [], plane.events
    assert plane.runner_deletes() == [], plane.events
    assert plane.instance_view_calls() == [], (
        f"power state was even queried for a BUSY worker: {plane.instance_view_calls()}")


def test_busy_is_read_through_the_pagination_safe_listing(monkeypatch):
    """busy_runner_names() must see a runner on page 2, or a busy runner missing from the set is
    a runner this reaper will delete mid-job -- the exact truncation failure all_runners() exists
    to prevent. 100 filler registrations push the target onto the second page."""
    mod = _load(monkeypatch)
    fillers = [(f"ci-az-9-{i}", 1000 + i) for i in range(100)]
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-busy", _past_grace(mod))],
                   runners=fillers + [("ci-az-busy", 4242)], busy=["ci-az-busy"],
                   power={"ci-az-busy": "stopped"})
    assert mod.busy_runner_names() == {"ci-az-busy"}, "the busy set did not follow pagination"
    plane.cleanup()
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()
    assert plane.vm_deletes() == [], plane.events
    assert plane.runner_deletes() == [], plane.events


def test_the_registration_is_found_past_page_one_when_it_is_deleted(monkeypatch):
    """The other half of the same claim: the DELETE has to find an id on page 2 as well.

    delete_runner_registration() matches by NAME through all_runners(), so a fleet with more
    than 100 stale registrations -- measured 2026-08-26 at 32 for 6 runners, and the list only
    grows -- must not silently skip the prune.
    """
    mod = _load(monkeypatch)
    fillers = [(f"ci-az-9-{i}", 1000 + i) for i in range(100)]
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=fillers + [("ci-az-1-1", 4242)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()
    assert "gh DELETE orgs/thyn-ai/actions/runners/4242" in plane.events, plane.events
    assert [e.split()[1] for e in plane.vm_deletes()] == ["ci-az-1-1"], plane.events


# ------------------------------------------------------------- registration-delete failures


def test_a_failed_registration_delete_still_frees_the_quota(monkeypatch):
    """Degrade, do not wedge.

    If GitHub refuses the DELETE, the VM must still go: freeing quota is the point of the reap,
    and _sweep_stale_registrations collects the leftover on a later pass once the VM is gone.
    The alternative -- skipping the VM delete -- would let one GitHub 500 pin 8 vCPU for 90 min,
    which is the gap this change exists to close.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})

    def refusing_gh(path, method="GET", body=None):
        if method == "DELETE":
            plane.events.append(f"gh DELETE {path}")
            raise RuntimeError("502 Bad Gateway")
        return plane._gh(path, method, body)

    plane.mod.gh = refusing_gh
    plane.cleanup()
    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()

    assert [e.split()[1] for e in plane.vm_deletes()] == ["ci-az-1-1"], plane.events
    assert any("FAILED" in l for l in plane.logs), plane.logs


def test_a_runner_entry_with_no_id_is_reported_not_skipped_silently(monkeypatch):
    """No id means nothing addressable to delete. Say so, keep the return value honest, and let
    the VM reap proceed -- silence here is the failure mode, not the missing id."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "all_runners", lambda: [{"name": "ci-az-1-1", "busy": False}])
    logs = []
    monkeypatch.setattr(mod, "log", lambda m: logs.append(m))
    assert mod.delete_runner_registration("ci-az-1-1") is False
    assert any("carries no id" in l for l in logs), logs


def test_no_registration_by_that_name_is_a_success_not_an_error(monkeypatch):
    """The VM delete must not be held up by a registration that was already collected."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "all_runners", lambda: [])
    logs = []
    monkeypatch.setattr(mod, "log", lambda m: logs.append(m))
    assert mod.delete_runner_registration("ci-az-1-1") is True
    assert any("nothing to delete" in l for l in logs), logs


def test_only_this_fleets_own_registration_is_addressable(monkeypatch):
    """Exact-name match, never a prefix or substring match: some other system's runner whose
    name merely starts with the same characters must not be deleted by this reaper."""
    mod = _load(monkeypatch)
    runners = [{"name": "ci-az-1-11", "id": 7, "busy": False},
               {"name": "ci-orch", "id": 29, "busy": False}]
    monkeypatch.setattr(mod, "all_runners", lambda: list(runners))
    deleted = []
    monkeypatch.setattr(mod, "gh", lambda p, method="GET", body=None: deleted.append(p) or {})
    monkeypatch.setattr(mod, "log", lambda m: None)
    assert mod.delete_runner_registration("ci-az-1-1") is True
    assert deleted == [], deleted


# ----------------------------------------------------------- the rules that must not change


def test_an_unregistered_stopped_worker_keeps_its_own_reason(monkeypatch):
    """The pre-existing path is untouched: unregistered + past grace reaps on the FIRST poll
    (there is no registration to protect, so nothing to confirm) and stays labelled
    stopped-no-runner. It must not start paying for a registration delete it has no use for."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    assert [e.split()[1] for e in plane.vm_deletes()] == ["ci-az-1-1"], plane.events
    assert "stopped-no-runner" in plane.vm_deletes()[0], plane.vm_deletes()
    assert plane.runner_deletes() == [], plane.events


def test_a_max_age_registered_worker_also_drops_its_registration_first(monkeypatch):
    """MAX_AGE_S is the leak guard and still fires -- but a registered worker now loses the
    registration first on that path too, for the same reason: the org must not keep asserting a
    runner whose machine this orchestrator just deleted."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-warm-1", _T0 - mod.MAX_AGE_S - 1)],
                   runners=[("ci-warm-1", 101)],
                   power={"ci-warm-1": "running"})
    plane.cleanup()
    order = [e for e in plane.events if e.startswith(("gh DELETE", "delete_vm"))]
    assert order[0] == "gh DELETE orgs/thyn-ai/actions/runners/101", order
    assert order[1].startswith("delete_vm ci-warm-1"), order
    assert "max-age" in order[1], order


def test_a_registered_running_worker_past_the_grace_is_left_alone(monkeypatch):
    """The new rule is about STOPPED workers. A registered, running, long-lived worker is a
    healthy long job and must not be touched -- this is the #898 guarantee from the other side."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-warm-1", _past_grace(mod, extra=600))],
                   runners=[("ci-warm-1", 101)],
                   power={"ci-warm-1": "running"})
    for _ in range(3):
        plane.cleanup()
        plane.clock.advance(mod.RECONCILE_S)
    assert plane.vm_deletes() == [], plane.events
    assert plane.runner_deletes() == [], plane.events


def test_power_state_is_still_not_queried_for_a_worker_inside_the_grace(monkeypatch):
    """The cost rule from test_az_orchestrator_stopped_reap.py survives the new one.

    An instanceView call is a per-VM ARM round-trip (neither collection form works on this
    subscription -- see vm_power_state). The new rule widens WHO is asked to registered workers
    past the grace; it must not widen it to young workers, or every poll pays a round-trip per
    booting VM for a verdict that cannot change anything.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-young", _T0 - 120), ("ci-az-old-reg", _past_grace(mod))],
                   runners=[("ci-az-old-reg", 101)],
                   power={"ci-az-young": "stopped", "ci-az-old-reg": "running"})
    plane.cleanup()
    asked = [e.rsplit("/", 2)[-2] for e in plane.instance_view_calls()]
    assert asked == ["ci-az-old-reg"], asked
    assert plane.vm_deletes() == [], plane.events


def test_a_registered_stopped_worker_at_the_cap_is_labelled_by_what_it_is(monkeypatch):
    """The label cascade used to make `max-age` UNREACHABLE for any stopped VM.

    The deployed build tested `stopped` first, so a registered corpse condemned by the
    `age > MAX_AGE_S` leak guard was reported as "stopped-no-runner" -- a VM that very much had
    a runner. Measured live 2026-09-16, two populations of stopped corpse in one journal:

        20:32:11 deleting ci-az-...-104955239379 (age=762s,  reason=stopped-no-runner)
        20:37:58 deleting ci-az-...-104936938215 (age=5472s, reason=stopped-no-runner)

    Identical reasons, 7.2x apart in hold time, and the only difference between them is whether
    the worker had registered. Telling them apart required correlating every age against
    timeCreated by hand, because the label described the POWER STATE rather than the rule that
    fired. `stopped-registered` is the label that makes the two populations separable in the
    journal, which is the whole diagnostic value of the change.

    Note this path needs no second sighting: MAX_AGE_S already condemns it, so the power state
    is read once, purely to label.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-warm-1", _T0 - mod.MAX_AGE_S - 100)],
                   runners=[("ci-warm-1", 101)],
                   power={"ci-warm-1": "stopped"})
    plane.cleanup()
    assert len(plane.vm_deletes()) == 1, plane.events
    assert "stopped-registered" in plane.vm_deletes()[0], plane.vm_deletes()
    assert "max-age" not in plane.vm_deletes()[0], plane.vm_deletes()
    assert plane.runner_deletes() == ["gh DELETE orgs/thyn-ai/actions/runners/101"], plane.events


def test_a_registered_running_worker_at_the_cap_is_still_labelled_max_age(monkeypatch):
    """The other half of the cascade: max-age is now reachable exactly when it is TRUE -- a
    registered worker still powered on that has simply run out of clock. Paired with the test
    above so the label cannot collapse back into describing the power state."""
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-warm-1", _T0 - mod.MAX_AGE_S - 100)],
                   runners=[("ci-warm-1", 101)],
                   power={"ci-warm-1": "running"})
    plane.cleanup()
    assert len(plane.vm_deletes()) == 1, plane.events
    assert "max-age" in plane.vm_deletes()[0], plane.vm_deletes()


def test_a_candidate_costs_at_most_one_log_line_per_cycle(monkeypatch):
    """The journal requirement: the new path must be visible without being noise.

    One line when a streak starts, and one deletion line when it confirms -- never a per-cycle
    repeat of the sighting, and never more than one deletion for one worker.
    """
    mod = _load(monkeypatch)
    plane = _Plane(mod, monkeypatch,
                   vms=[("ci-az-1-1", _past_grace(mod))],
                   runners=[("ci-az-1-1", 101)],
                   power={"ci-az-1-1": "stopped"})
    plane.cleanup()
    assert [l for l in plane.logs if "stopped-but-registered" in l] != []
    assert len([l for l in plane.logs if "ci-az-1-1" in l]) == 1, plane.logs
    assert plane.vm_deletes() == [], plane.events

    plane.clock.advance(mod.RECONCILE_S)
    plane.cleanup()
    assert len(plane.vm_deletes()) == 1, plane.events
    assert len(plane.runner_deletes()) == 1, plane.events
    # the confirming cycle announces the two actions and nothing else about this worker
    assert len([l for l in plane.logs if "ci-az-1-1" in l]) == 2, plane.logs


def test_the_confirm_window_is_not_longer_than_a_reconcile_cycle(monkeypatch):
    """STOPPED_CONFIRM_S must stay below RECONCILE_S, or two consecutive polls could never
    satisfy it and the rule would be dead code -- the same silent-no-op failure the
    BOOT_GRACE_S/ORPHAN_AGE_S pairing is derived to avoid."""
    mod = _load(monkeypatch)
    assert mod.STOPPED_CONFIRM_S <= mod.RECONCILE_S
    assert mod.STOPPED_CONFIRM_S == 60
    assert mod.BOOT_GRACE_S < mod.MAX_AGE_S
