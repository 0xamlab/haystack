"""Tests for test_credit_bucket: consume_credit.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


def test_consume_credit_permits_when_available():
    import apps.runtime.credits as cmod

    store = _tmp_store()
    store.initialize_sync(5000, "2026-04")
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is True
    finally:
        cmod._store = old_store


def test_consume_credit_blocks_when_exhausted():
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState

    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=0)))
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is False
    finally:
        cmod._store = old_store


def test_consume_credit_blocks_without_credit_file():
    """No credit file → execution is blocked by default."""
    import apps.runtime.credits as cmod

    store = _tmp_store()  # empty temp dir, no file
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is False
    finally:
        cmod._store = old_store


def test_consume_credit_allows_key_bound_offline_license_without_credit_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    runtime_dir = tmp_path / "runtime"
    _seed_key_bound_offline_license(monkeypatch, runtime_dir)
    sys.modules.pop("apps.runtime.credits", None)
    cmod = importlib.import_module("apps.runtime.credits")
    store = cmod.CreditStore(runtime_dir / "credits.json")
    old_store = cmod._store
    cmod._store = store
    try:
        assert run(cmod.consume_credit()) is True
    finally:
        cmod._store = old_store


def test_consume_credit_allows_key_bound_offline_license_with_exhausted_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    runtime_dir = tmp_path / "runtime"
    _seed_key_bound_offline_license(monkeypatch, runtime_dir)
    sys.modules.pop("apps.runtime.credits", None)
    cmod = importlib.import_module("apps.runtime.credits")
    store = cmod.CreditStore(runtime_dir / "credits.json")
    old_store = cmod._store
    cmod._store = store
    try:
        store.initialize_sync(credits_granted=0, billing_period="2026-04")
        assert run(cmod.consume_credit()) is True
    finally:
        cmod._store = old_store


def test_consume_credit_ignores_key_bound_license_outside_store_runtime_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    licensed_runtime_dir = tmp_path / "licensed-runtime"
    _seed_key_bound_offline_license(monkeypatch, licensed_runtime_dir)
    sys.modules.pop("apps.runtime.credits", None)
    cmod = importlib.import_module("apps.runtime.credits")
    isolated_runtime_dir = tmp_path / "isolated-runtime"
    store = cmod.CreditStore(isolated_runtime_dir / "credits.json")
    old_store = cmod._store
    cmod._store = store
    try:
        assert run(cmod.consume_credit()) is False
    finally:
        cmod._store = old_store


def test_consume_credit_allows_explicit_dev_mode(monkeypatch):
    """Explicit local dev mode preserves the dev-stub escape hatch."""
    monkeypatch.setenv("ALGENTA_RUNTIME_DEV_MODE", "1")
    import apps.runtime.credits as cmod

    store = _tmp_store()
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is True
    finally:
        cmod._store = old_store
        monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)


def test_consume_credit_triggers_refresh_when_low():
    """When credits <= 10%, background refresh is scheduled."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState

    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=500, total=10_000)))  # 5% <= threshold
    old_store = cmod._store
    cmod._store = store

    refresh_called = []

    async def _fake_refresh():
        refresh_called.append(True)

    with patch.object(cmod, "_background_refresh", _fake_refresh):
        cmod._store._refreshing = False
        run(cmod.consume_credit())

    # should_refresh() is True because 500/10000 = 5% <= 10% threshold
    assert store.should_refresh() is True
    cmod._store = old_store


def test_consume_credit_no_double_refresh():
    """If _refreshing=True, don't schedule another refresh."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState

    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=100, total=10_000)))
    store._refreshing = True
    old_store = cmod._store
    cmod._store = store

    tasks_created = []

    async def _noop():
        tasks_created.append(True)

    with patch.object(cmod, "_background_refresh", _noop):
        run(cmod.consume_credit())

    # refresh was not triggered (already refreshing)
    assert len(tasks_created) == 0
    cmod._store = old_store
    store._refreshing = False


def test_consume_credit_can_disable_background_refresh():
    """Callers can enforce a fully local quota drain without scheduling refresh."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState

    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=100, total=10_000)))
    old_store = cmod._store
    cmod._store = store

    refresh_called = []

    async def _fake_refresh():
        refresh_called.append(True)

    try:
        with patch.object(cmod, "_background_refresh", _fake_refresh):
            run(cmod.consume_credit(allow_background_refresh=False))
    finally:
        cmod._store = old_store

    assert refresh_called == []
    assert store.should_refresh() is True


