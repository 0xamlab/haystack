"""P5.1 gate tool — scripts/license_status.py reports "active + v2" correctly.

The owner runs this on each internal deployment before any fail-closed flip; the exit
code IS the gate (0 = ready). These tests pin the gate logic across the license states
that matter: valid (ready), invalid, and past-grace expiry.
"""

from __future__ import annotations

import json

import apps.runtime.license as license_mod
import scripts.license_status as cli
from apps.runtime.license import DeviceLicense


def _mk(**over: object) -> DeviceLicense:
    base: dict[str, object] = {
        "valid": True,
        "plan": "enterprise",
        "device_id": "d",
        "device_limit": 0,
        "permitted_modules": ["*"],
        "expires_at": 0,  # no entitlement expiry
        "key_expires_at": 9_999_999_999,  # key expiry set (stored-offline path requires > 0)
        "grace_days": 14,
        "api_key_prefix": "",
        "issued_at": 0,
        "license_version": 2,
    }
    base.update(over)
    return DeviceLicense(**base)  # type: ignore[arg-type]


def test_valid_v2_satisfies_gate(monkeypatch, capsys) -> None:
    monkeypatch.setattr(license_mod, "load_license", lambda *a, **k: _mk())
    assert cli.main([]) == 0
    assert capsys.readouterr().out.startswith("OK")


def test_invalid_license_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        license_mod,
        "load_license",
        lambda *a, **k: _mk(valid=False, message="no installed license"),
    )
    assert cli.main([]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_no_key_expiry_fails_unless_allowed(monkeypatch, capsys) -> None:
    # key_expires_at<=0 (issue_offline_license.py default) verifies but the stored-offline
    # enforcement path denies it — the gate must NOT green-light it by default.
    monkeypatch.setattr(license_mod, "load_license", lambda *a, **k: _mk(key_expires_at=0))
    assert cli.main([]) == 1
    assert "key_expires_at<=0" in capsys.readouterr().out
    assert cli.main(["--allow-no-key-expiry"]) == 0  # deliberate no-expiry under require_local


def test_hard_expired_v2_fails(monkeypatch) -> None:
    # expired long ago, past a zero grace window
    monkeypatch.setattr(
        license_mod,
        "load_license",
        lambda *a, **k: _mk(expires_at=1, grace_days=0),
    )
    assert cli.main([]) == 1


def test_json_output_is_parseable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        license_mod,
        "load_license",
        lambda *a, **k: _mk(
            deployment_class="server",
            org_id="org_x",
            named_seat_limit=25,
            active_node_limit=3,
            concurrent_worker_limit=12,
        ),
    )
    rc = cli.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["gate_satisfied"] is True
    assert payload["active_node_limit"] == 3
