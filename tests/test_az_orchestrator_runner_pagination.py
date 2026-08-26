"""Regression: the org runner listing must follow pagination, not truncate at 100.

Every runner listing used `?per_page=100` with no `page=` follow-up. 100 is the API maximum, so
the request silently returns only the FIRST 100 registrations and drops the rest with no error.

That is not a theoretical ceiling here. Ephemeral workers leave their registration behind when
their VM is deleted, so the org list grows well past the live fleet -- measured 2026-08-26 on
thyn-ai: 32 registrations for 6 online runners (21 stale `ci-az-*` plus 5 retired blacksmith
entries). The stale set accumulates, so crossing 100 is a matter of time, not of load.

Why truncation is dangerous rather than merely inaccurate: cleanup() and manage_warm_pool()
both build their `busy` set from this listing, and a busy runner MISSING from that set is a
runner both reapers consider idle -- so it gets deleted mid-job. That is exactly the failure
#898 fixed by a different route (the unconditional age cap killed sdk-audit's execution-sweep
20 minutes into a real build, surfacing as a build failure rather than an infra kill).
Truncation would silently reintroduce it once the registration count passed 100.
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
    spec = importlib.util.spec_from_file_location("az_orch_pagination_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _paged(mod, monkeypatch, pages):
    """Serve `pages` (a list of runner-dict lists) as successive ?page=N responses.

    Records every requested path so the tests can assert how many pages were actually fetched --
    a fix that over-fetches on every poll would be its own (rate-limit) problem.
    """
    calls: list[str] = []

    def fake_gh(path, *a, **kw):
        calls.append(path)
        idx = 1
        for part in path.split("&"):
            if part.startswith("page="):
                idx = int(part.split("=", 1)[1])
        return {"runners": pages[idx - 1] if idx - 1 < len(pages) else []}

    monkeypatch.setattr(mod, "gh", fake_gh)
    return calls


def _entries(prefix, n, busy=False):
    return [{"name": f"{prefix}-{i}", "busy": busy} for i in range(n)]


def test_all_runners_follows_pagination_past_one_hundred(monkeypatch):
    mod = _load(monkeypatch)
    pages = [_entries("ci-az-p1", 100), _entries("ci-az-p2", 30)]
    _paged(mod, monkeypatch, pages)

    got = mod.all_runners()

    assert len(got) == 130, f"truncated at a page boundary: got {len(got)}"
    names = {r["name"] for r in got}
    assert "ci-az-p2-29" in names, "runners past the first page were dropped"


def test_a_busy_runner_on_page_two_is_still_seen_as_busy(monkeypatch):
    """THE safety property. A busy runner missing from this set gets reaped under a live job."""
    mod = _load(monkeypatch)
    pages = [
        _entries("ci-az-idle", 100, busy=False),
        [{"name": "ci-az-running-a-real-build", "busy": True}],
    ]
    _paged(mod, monkeypatch, pages)

    busy = mod.busy_runner_names()

    assert "ci-az-running-a-real-build" in busy, (
        "a BUSY runner beyond the first page was invisible to the reapers -- it would be "
        "deleted mid-job, exactly the #898 failure mode")
    assert busy == {"ci-az-running-a-real-build"}, f"idle runners leaked into the busy set: {busy}"


def test_stops_on_the_first_short_page(monkeypatch):
    """A short page means the end of the list: fetching further pages every poll would just
    spend rate-limit budget on empty responses."""
    mod = _load(monkeypatch)
    calls = _paged(mod, monkeypatch, [_entries("ci-az", 7)])

    assert len(mod.all_runners()) == 7
    assert len(calls) == 1, f"kept paging past a short page: {calls}"


def test_exactly_full_page_then_empty_terminates(monkeypatch):
    """Boundary: 100 is indistinguishable from "maybe more", so page 2 must be requested --
    and an empty page 2 must end the walk rather than loop."""
    mod = _load(monkeypatch)
    calls = _paged(mod, monkeypatch, [_entries("ci-az", 100), []])

    assert len(mod.all_runners()) == 100
    assert len(calls) == 2, f"expected exactly 2 requests (full page, then empty): {calls}"


def test_runaway_pages_are_bounded(monkeypatch):
    """A pathological always-full response must not spin the poll loop forever."""
    mod = _load(monkeypatch)
    calls: list[str] = []

    def always_full(path, *a, **kw):
        calls.append(path)
        return {"runners": _entries("ci-az", 100)}

    monkeypatch.setattr(mod, "gh", always_full)

    mod.all_runners()

    assert len(calls) <= 20, f"unbounded pagination: {len(calls)} requests"


def test_missing_runners_key_is_not_fatal(monkeypatch):
    """gh() returns {} on an empty body (see its own `or b'{}'`); that must read as "no
    runners", not raise inside the poll loop and take the orchestrator down."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "gh", lambda *a, **kw: {})

    assert mod.all_runners() == []
    assert mod.busy_runner_names() == set()
    assert mod.runner_names() == set()
