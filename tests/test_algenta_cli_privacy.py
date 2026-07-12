from __future__ import annotations

import contextlib
import importlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
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


def test_algenta_cmd_benchmark_uses_only_bundled_runtime(monkeypatch) -> None:
    calls: list[int] = []

    def _execute(*, runs: int) -> dict[str, object]:
        calls.append(runs)
        return {}

    monkeypatch.setattr(algenta_cli, "_execute_native_simulation_or_exit", _execute)

    output = _capture_stdout(algenta_cli.cmd_benchmark)

    assert calls == [10_000] * 11
    assert "bundled native runtime" in output
    assert "Python fallback:    disabled" in output
    assert "free tier" not in output.lower()
    assert "speedup" not in output.lower()


def test_algenta_cmd_simulate_uses_bundled_runtime(monkeypatch) -> None:
    monkeypatch.setattr(
        algenta_cli,
        "_execute_native_simulation_or_exit",
        lambda *, runs: {
            "summary": {"mean": 30_000.0},
            "risk": {"probability_of_loss": 0.05},
            "percentiles": {"p5": 100.0, "p95": 59_000.0},
            "scenarios_run": runs,
        },
    )

    output = _capture_stdout(algenta_cli.cmd_simulate_quick)

    assert "bundled native runtime" in output
    assert "Python fallback:    disabled" in output


def test_algenta_cmd_upgrade_private_profile_uses_self_hosted_guidance(monkeypatch) -> None:
    monkeypatch.setattr(algenta_cli, "private_profile_enabled", lambda: True)
    monkeypatch.setattr(
        algenta_cli,
        "resolve_console_base_url",
        lambda *, component: "http://localhost:8000",
    )
    monkeypatch.setattr(
        algenta_cli,
        "credential_setup_help_text",
        lambda *, component, fallback_base_url=None: (
            "Create a key from your self-hosted admin surface or API base URL: http://localhost:8000"
        ),
    )

    output = _capture_stdout(algenta_cli.cmd_upgrade)

    assert "Connect Algenta SDK to your deployment" in output
    assert 'export ALGENTA_BASE_URL="http://localhost:8000"' in output
    assert 'export DE_BASE_URL="http://localhost:8000"' in output
    assert 'export ALGENTA_API_URL="http://localhost:8000"' in output
    assert "self-hosted admin surface or API base URL: http://localhost:8000" in output
    assert "https://algenta.ai/dashboard" not in output
