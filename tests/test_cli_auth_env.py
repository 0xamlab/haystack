from __future__ import annotations

import contextlib
import io
import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

cli_main = importlib.import_module("apps.cli.main")


def _capture_stdout(fn, *args):  # type: ignore[no-untyped-def]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        fn(*args)
    return buffer.getvalue()


def test_cmd_login_uses_shared_env_api_key_resolution(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_load_env_api_key", lambda: "de_live_shared_env")

    issue_calls: list[str] = []

    fake_device_module = types.SimpleNamespace(
        get_device_info=lambda: {"device_id": "device_12345678", "platform": "darwin"},
    )
    fake_license_module = types.SimpleNamespace(
        issue_and_store=lambda api_key: issue_calls.append(api_key) or types.SimpleNamespace(valid=True),
        license_summary=lambda lic: "ok",
    )
    monkeypatch.setitem(sys.modules, "apps.runtime.device", fake_device_module)
    monkeypatch.setitem(sys.modules, "apps.runtime.license", fake_license_module)

    output = _capture_stdout(cli_main.cmd_login)

    assert issue_calls == ["de_live_shared_env"]
    assert "License issued" in output


def test_cmd_license_status_uses_shared_env_api_key_resolution(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_load_env_api_key", lambda: "de_live_shared_env")

    load_calls: list[str] = []

    fake_device_module = types.SimpleNamespace(
        get_device_info=lambda: {"platform": "darwin"},
    )
    fake_license_module = types.SimpleNamespace(
        load_license=lambda api_key: load_calls.append(api_key)
        or types.SimpleNamespace(
            device_id="device_12345678",
            plan="enterprise",
            device_limit=0,
            permitted_modules=["*"],
            source="offline",
            expires_at=None,
            message="",
            is_in_grace=lambda: False,
            is_hard_expired=lambda: False,
        ),
    )
    monkeypatch.setitem(sys.modules, "apps.runtime.device", fake_device_module)
    monkeypatch.setitem(sys.modules, "apps.runtime.license", fake_license_module)

    output = _capture_stdout(cli_main.cmd_license_status)

    assert load_calls == ["de_live_shared_env"]
    assert "Plan:       enterprise" in output


def test_cmd_login_empty_key_uses_private_profile_self_hosted_guidance(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_load_env_api_key", lambda: "")
    monkeypatch.setattr(cli_main, "_private_profile_enabled", lambda: True)
    monkeypatch.setattr(cli_main, "_get_base_url", lambda: "http://localhost:8000")
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    output = _capture_stdout(cli_main.cmd_login)

    assert "self-hosted admin surface or API base URL: http://localhost:8000" in output
    assert "app.algenta.ai/dashboard/api-keys" not in output


def test_cmd_login_empty_key_private_profile_requires_explicit_origin(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_load_env_api_key", lambda: "")
    monkeypatch.setattr(cli_main, "_private_profile_enabled", lambda: True)
    monkeypatch.setattr(
        cli_main,
        "_get_base_url",
        lambda: (_ for _ in ()).throw(
            ValueError("CLI private profiles require an explicit self-hosted API origin.")
        ),
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    output = _capture_stdout(cli_main.cmd_login)

    assert "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL" in output
    assert "save base_url in CLI config" in output


def test_cmd_login_empty_key_uses_cloud_managed_guidance_when_private_profile_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_load_env_api_key", lambda: "")
    monkeypatch.setattr(cli_main, "_private_profile_enabled", lambda: False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    output = _capture_stdout(cli_main.cmd_login)

    assert "https://app.algenta.ai/dashboard/api-keys" in output
