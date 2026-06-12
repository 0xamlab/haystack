"""B10 PR8: no telemetry / phone-home, fail-closed by policy.

There is no analytics/telemetry SDK wired (sentry_dsn is an inert config Field; no
sentry_sdk/posthog/segment/datadog import anywhere). These assertions LOCK that: under a private
profile (self_hosted/air_gapped) the metering + heartbeat background tasks never start, the
metering flush is a transport no-op, and no telemetry SDK can creep into the app via a future
vendored-merge or a manual METERING_MODE override (the unguarded socket was removed in PR3)."""

from __future__ import annotations

import asyncio
import pathlib
import re

import pytest

from apps.privacy_policy import build_privacy_policy
from apps.runtime import metering
from apps.runtime.metering import MeteringQueue

_APPS = pathlib.Path(__file__).resolve().parents[1] / "apps"


@pytest.mark.parametrize("mode", ["self_hosted", "air_gapped"])
def test_private_profile_telemetry_is_fail_closed(mode):
    p = build_privacy_policy(deployment_mode=mode)
    assert p.private_profile is True
    assert p.disable_telemetry is True
    assert p.allow_outbound_network is False
    assert p.metering_mode != "control_plane_sync"
    assert p.mandatory_heartbeat_enabled is False
    assert p.metering_flush_enabled is False


async def test_start_background_flush_starts_no_tasks_in_private(monkeypatch):
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_METERING_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", raising=False)
    queue = MeteringQueue()
    queue.start_background_flush(asyncio.get_running_loop())
    assert queue._flush_task is None
    assert queue._heartbeat_task is None


def test_metering_flush_send_is_transport_noop_in_private(monkeypatch):
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_METERING_MODE", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("no metering transport may run under a private profile")

    monkeypatch.setattr(metering, "runtime_urlopen", _boom)
    # returns before building/sending any request (metering_mode != control_plane_sync)
    MeteringQueue()._send_metering_batch_sync([])


def test_no_phone_home_telemetry_sdk_is_imported():
    pat = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(sentry_sdk|posthog|segment|analytics|mixpanel|amplitude|datadog|ddtrace|opentelemetry)\b",
        re.M,
    )
    offenders = []
    for p in _APPS.rglob("*.py"):
        sp = str(p)
        if "/vendor/" in sp or "/node_modules/" in sp:
            continue
        if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(p.relative_to(_APPS.parent)))
    assert offenders == [], f"telemetry/analytics SDK imported in apps/: {offenders}"
