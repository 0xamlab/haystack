from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "scripts" / "verify_local_api_key_runtime.py"


def _load_verify_module():
    spec = importlib.util.spec_from_file_location(
        "verify_local_api_key_runtime_under_test",
        VERIFY_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runtime_ledger_events(runtime_dir: Path) -> list[dict[str, object]]:
    ledger_path = runtime_dir / "history.jsonl"
    assert ledger_path.exists()
    return [json.loads(line) for line in ledger_path.read_text().splitlines()]


def test_verify_local_api_key_runtime_help_prefers_bounded_lifetime_replacement_key() -> None:
    proc = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    normalized = " ".join(proc.stdout.split())
    assert "Prefer a bounded-lifetime replacement key" in normalized
    assert "not the one-time bootstrap key" in normalized
    assert "Prefer a rotated bounded-lifetime key" in normalized
    assert "de_live_..." not in proc.stdout
    assert "Defaults to ALGENTA_API_KEY / DE_API_KEY." in proc.stdout

    script_text = VERIFY_SCRIPT.read_text()
    assert "ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>" in script_text
    assert "DE_API_KEY=<YOUR_LEGACY_DECISION_ENGINE_API_KEY>" in script_text
    assert "de_live_..." not in script_text


def test_verify_local_api_key_runtime_missing_key_message_mentions_both_env_families() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--base-url",
            "http://127.0.0.1:9",
        ],
        cwd=ROOT,
        env={key: value for key, value in os.environ.items() if key not in {"ALGENTA_API_KEY", "DE_API_KEY"}},
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "ALGENTA_API_KEY or DE_API_KEY or pass --api-key" in proc.stdout


def test_verify_local_api_key_runtime_executes_past_apps_import_when_health_is_reachable() -> None:
    class _HealthOnlyHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/v1/health":
                body = json.dumps({"status": "ok"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthOnlyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(VERIFY_SCRIPT),
                "--api-key",
                "de_live_dummy_key_for_import_path_check",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}",
                "--timeout",
                "2",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert proc.returncode != 0
    assert "ModuleNotFoundError" not in proc.stderr
    assert "No module named 'apps'" not in proc.stderr
    assert "API health check" in proc.stdout


def test_verify_local_api_key_runtime_hydrates_license_secret_from_api_settings(
    monkeypatch,
) -> None:
    verify_mod = _load_verify_module()

    monkeypatch.delenv("ALGENTA_LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("ALGENTA_JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    env_updates = verify_mod._license_verification_env()

    assert "ALGENTA_JWT_SECRET" in env_updates or "ALGENTA_LICENSE_SIGNING_SECRET" in env_updates


def test_verify_local_api_key_runtime_private_profile_requires_explicit_base_url(
    monkeypatch,
) -> None:
    verify_mod = _load_verify_module()

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)

    with pytest.raises(ValueError, match="requires an explicit --base-url"):
        verify_mod._base_url(argparse.Namespace(base_url=""))


def test_verify_local_api_key_runtime_private_profile_rejects_algenta_owned_base_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    verify_mod = _load_verify_module()

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")

    with pytest.raises(
        ValueError,
        match="ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL or pass --base-url",
    ):
        verify_mod._base_url(argparse.Namespace(base_url="https://api.algenta.ai"))

    events = _runtime_ledger_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "deny"
    assert event["target"] == "api.algenta.ai"
    assert event["error"] == "algenta_cloud_disabled"


def test_verify_local_api_key_runtime_private_profile_allows_self_hosted_base_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    verify_mod = _load_verify_module()

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "control.customer.internal")

    assert (
        verify_mod._base_url(argparse.Namespace(base_url="https://control.customer.internal"))
        == "https://control.customer.internal"
    )

    events = _runtime_ledger_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "allow"
    assert event["target"] == "internal-host"
    assert event["error"] is None


def test_verify_local_api_key_runtime_execution_env_exports_all_base_url_aliases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    verify_mod = _load_verify_module()

    monkeypatch.delenv("ALGENTA_LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("ALGENTA_JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    env_updates = verify_mod._runtime_execution_env(
        runtime_dir=tmp_path / "runtime",
        daemon_sock=tmp_path / "daemon.sock",
        mojo_sock=tmp_path / "mojo.sock",
        base_url="https://control.customer.internal",
        api_key="de_live_test_key",
    )

    assert env_updates["ALGENTA_BASE_URL"] == "https://control.customer.internal"
    assert env_updates["DE_BASE_URL"] == "https://control.customer.internal"
    assert env_updates["ALGENTA_API_URL"] == "https://control.customer.internal"
    assert env_updates["ALGENTA_CONTROL_PLANE_URL"] == "https://control.customer.internal"
    assert env_updates["ALGENTA_API_KEY"] == "de_live_test_key"
    assert env_updates["DE_API_KEY"] == "de_live_test_key"
