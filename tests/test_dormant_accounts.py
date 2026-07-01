"""Dormant-account policy: the 12-month classify() + warning cadence (pure logic)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.api_server.services import dormant_accounts as da

NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


def test_classify_stages():
    assert da.classify(_ago(10), NOW) == "active"      # 355 days left
    assert da.classify(_ago(300), NOW) == "active"     # 65 left
    assert da.classify(_ago(340), NOW) == "warn_30"    # 25 left
    assert da.classify(_ago(352), NOW) == "warn_14"    # 13 left
    assert da.classify(_ago(359), NOW) == "warn_7"     # 6 left
    assert da.classify(_ago(364), NOW) == "warn_1"     # 1 left
    assert da.classify(_ago(365), NOW) == "delete"     # 0 left
    assert da.classify(_ago(400), NOW) == "delete"
    assert da.classify(None, NOW) == "delete"          # never signed in


def test_warning_is_at_least_one_month_ahead():
    # the earliest warning fires with >= 30 days of notice before deletion
    assert max(da.WARNING_SCHEDULE) >= 30
    assert da.days_left_for_stage("warn_30") == 30
    assert da.days_left_for_stage("warn_1") == 1
    assert da.days_left_for_stage("delete") == 0
    assert da.days_left_for_stage("active") is None


def test_naive_datetimes_handled():
    naive = datetime(2025, 7, 1)  # 365 days before NOW, tz-naive
    assert da.classify(naive, NOW) == "delete"


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


async def test_run_sweep_dry_run_classifies(monkeypatch):
    from apps.api_server.db.session import AsyncSessionLocal

    async def _no_paid(db, email):
        return False

    monkeypatch.setattr(da, "_has_active_paid_sub", _no_paid)
    users = [
        {"id": "1", "email": "active@x.com", "last_sign_in_at": _iso(_ago(10))},
        {"id": "2", "email": "warn30@x.com", "last_sign_in_at": _iso(_ago(340))},
        {"id": "3", "email": "warn1@x.com", "last_sign_in_at": _iso(_ago(364))},
        {"id": "4", "email": "dead@x.com", "last_sign_in_at": _iso(_ago(400))},
    ]
    async with AsyncSessionLocal() as db:
        s = await da.run_sweep(db, execute=False, now=NOW, users=users)
    assert s["dry_run"] is True
    assert s["active"] == 1
    assert s["warned"] == {"warn_30": 1, "warn_1": 1}
    assert s["deleted"] == 1
    assert s["skipped_paid"] == 0


async def test_run_sweep_never_deletes_paid_subscriber(monkeypatch):
    from apps.api_server.db.session import AsyncSessionLocal

    async def _paid(db, email):
        return True  # everyone has an active paid sub

    monkeypatch.setattr(da, "_has_active_paid_sub", _paid)
    users = [{"id": "9", "email": "payer@x.com", "last_sign_in_at": _iso(_ago(400))}]
    async with AsyncSessionLocal() as db:
        s = await da.run_sweep(db, execute=False, now=NOW, users=users)
    assert s["deleted"] == 0
    assert s["skipped_paid"] == 1
