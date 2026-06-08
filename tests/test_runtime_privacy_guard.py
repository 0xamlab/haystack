from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


def _reload(module_name: str):
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _ledger_events(runtime_dir: Path) -> list[dict[str, object]]:
    ledger_path = runtime_dir / "history.jsonl"
    assert ledger_path.exists()
    return [json.loads(line) for line in ledger_path.read_text().splitlines()]


def test_validated_control_plane_url_records_allowlisted_runtime_egress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_CONTROL_PLANE_URL", "https://control.customer.internal")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "control.customer.internal")
    monkeypatch.delenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", raising=False)

    license_mod = _reload("apps.runtime.license")

    assert (
        license_mod._validated_control_plane_url(surface="credits_refresh")
        == "https://control.customer.internal"
    )

    events = _ledger_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["surface"] == "runtime"
    assert event["action"] == "privacy_egress"
    assert event["status"] == "allow"
    assert event["target"] == "internal-host"
    assert event["success"] is True
    assert event["error"] is None
    assert event["details"] == {
        "surface": "credits_refresh",
        "egress_class": "operator_service",
        "decision": "allow",
        "reason": "destination_allowlisted",
        "deployment_mode": "self_hosted",
        "service_name": "runtime",
        "request_id": None,
        "destination_host_redacted": "internal-host",
        "destination_host_hash": event["details"]["destination_host_hash"],
    }


def test_validated_control_plane_url_records_denied_runtime_egress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_CONTROL_PLANE_URL", "https://control.customer.com")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.delenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", raising=False)

    license_mod = _reload("apps.runtime.license")

    with pytest.raises(ValueError, match="destination_not_allowlisted"):
        license_mod._validated_control_plane_url(surface="device_heartbeat")

    events = _ledger_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["surface"] == "runtime"
    assert event["action"] == "privacy_egress"
    assert event["status"] == "deny"
    assert event["target"] == "*.customer.com"
    assert event["success"] is False
    assert event["error"] == "destination_not_allowlisted"
    assert event["details"] == {
        "surface": "device_heartbeat",
        "egress_class": "operator_service",
        "decision": "deny",
        "reason": "destination_not_allowlisted",
        "deployment_mode": "self_hosted",
        "service_name": "runtime",
        "request_id": None,
        "destination_host_redacted": "*.customer.com",
        "destination_host_hash": event["details"]["destination_host_hash"],
    }
