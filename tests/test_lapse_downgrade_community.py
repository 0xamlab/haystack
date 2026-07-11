"""A lapsed paid license downgrades to Community (free-forever), it does NOT hard-block.

The engine runs on the customer's hardware; when a paid license expires and can't renew, a
connected deployment keeps running at Community limits (1 device / 1 worker / non-commercial) —
paid caps/features + updates resume on renewal. Enterprise air-gapped still hard-blocks (no
renewal path); that gate is asserted where `_local_license_required()` is honored.
"""

from __future__ import annotations

from apps.runtime.license import _make_community_license


def test_community_fallback_keeps_running_at_free_limits() -> None:
    lic = _make_community_license("apikey1234567")
    assert lic.valid is True  # engine keeps running — NOT hard-blocked
    assert lic.plan == "algenta_free"  # downgraded to Community
    assert lic.device_limit == 1  # free-forever on one node
    assert lic.concurrent_worker_limit == 1  # Community per-device worker cap
    assert lic.commercial_use is False  # Community is non-commercial
    assert lic.expires_at == 0  # free-forever — never expires
    assert lic.source == "community-fallback"
    assert lic.permitted_modules == ["*"]  # can use the engine, just capped


def test_community_fallback_message_names_the_prior_plan() -> None:
    lic = _make_community_license("k", reason="Your algenta_pro license expired — running on Community.")
    assert "Community" in lic.message
    assert "algenta_pro" in lic.message
