from __future__ import annotations

import contextlib
import importlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta_cli = importlib.import_module("algenta.cli")


def _capture_stdout(fn, *args):  # type: ignore[no-untyped-def]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        fn(*args)
    return buffer.getvalue()


def test_algenta_cmd_benchmark_private_profile_uses_self_hosted_guidance(monkeypatch) -> None:
    monkeypatch.setattr(algenta_cli, "_bench_normal", lambda n=100_000: 10.0)
    monkeypatch.setattr(algenta_cli, "_bench_simulate", lambda n=100_000: 1.0)
    monkeypatch.setattr(algenta_cli, "private_profile_enabled", lambda: True)
    monkeypatch.setattr(
        algenta_cli,
        "resolve_dashboard_url",
        lambda *, component: "http://localhost:8000/dashboard",
    )

    output = _capture_stdout(algenta_cli.cmd_benchmark)

    assert "http://localhost:8000/dashboard" in output
    assert "free tier: 500 simulations/month" not in output.lower()
    assert "codna.ai/dashboard" not in output


def test_algenta_cmd_upgrade_private_profile_uses_self_hosted_guidance(monkeypatch) -> None:
    monkeypatch.setattr(algenta_cli, "private_profile_enabled", lambda: True)
    monkeypatch.setattr(
        algenta_cli,
        "resolve_console_base_url",
        lambda *, component: "http://localhost:8000",
    )
    monkeypatch.setattr(
        algenta_cli,
        "api_key_help_text",
        lambda *, component, fallback_base_url=None: (
            "Create a key from your self-hosted admin surface or API base URL: http://localhost:8000"
        ),
    )

    output = _capture_stdout(algenta_cli.cmd_upgrade)

    assert "Connect Codna SDK to your deployment" in output
    assert 'export ALGENTA_BASE_URL="http://localhost:8000"' in output
    assert 'export DE_BASE_URL="http://localhost:8000"' in output
    assert 'export ALGENTA_API_URL="http://localhost:8000"' in output
    assert "self-hosted admin surface or API base URL: http://localhost:8000" in output
    assert "https://codna.ai/dashboard" not in output
