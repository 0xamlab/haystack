from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"


def _pythonpath() -> str:
    return os.pathsep.join([str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)])


def test_algenta_demo_module_runs_cleanly() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "algenta.demo"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Algenta Runtime Demo" in proc.stdout
    assert "Walkthrough" in proc.stdout
    assert "Step 1/6 - Register bundled source" in proc.stdout
    assert "Step 2/6 - Select scenario" in proc.stdout
    assert "Step 3/6 - Inspect deterministic plan" in proc.stdout
    assert "Step 4/6 - Verify executable plan" in proc.stdout
    assert "Step 5/6 - Execute deterministic query" in proc.stdout
    assert "Step 6/6 - Reproduce on your own data" in proc.stdout
    assert "Algenta Source Import" not in proc.stdout


def test_algenta_demo_lists_available_scenarios() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "algenta.demo", "--list"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Available scenarios" in proc.stdout
    assert "Executive leaderboard: top product lines [product_line]" in proc.stdout
    assert "Guardrail: reject an unresolvable metric [guardrail]" in proc.stdout
    assert "recipes. Show local, CLI, and API integration recipes" in proc.stdout


def test_algenta_demo_interactive_action_parser_accepts_chained_actions() -> None:
    sys.path.insert(0, str(ALGENTA_CORE))
    try:
        from algenta import demo as demo_module
    finally:
        sys.path.pop(0)

    assert demo_module._parse_interactive_actions("1,recipes") == ["product_line", "recipes"]
    assert demo_module._parse_interactive_actions("all quit") == ["all", "quit"]
    assert demo_module._parse_interactive_actions("r") == ["recipes"]


def test_algenta_cli_demo_runs_selected_scenario() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "algenta.cli",
            "demo",
            "--scenario",
            "canada_filter",
            "--no-interactive",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Recovery drilldown: Canada-only product mix" in proc.stdout
    assert '"dimension_hint": "region"' in proc.stdout
    assert "Step 4/6 - Verify executable plan" in proc.stdout
    assert "Electronics   1204000.0  1" in proc.stdout
    assert "Canada leader: Electronics at 1,204,000.0." in proc.stdout


def test_runtime_docs_primary_examples_present() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    local_runtime = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md"
    ).read_text(encoding="utf-8")
    python_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text(
        encoding="utf-8"
    )
    cli_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md").read_text(encoding="utf-8")

    assert "from algenta import Runtime" in readme
    assert "from algenta import Runtime" in local_runtime
    assert "from decision_engine import AlgentaClient" in python_sdk
    assert "algenta import" in readme
    assert "algenta demo --all --no-interactive" in readme
    assert "algenta demo --scenario region --no-interactive" in readme
    assert "ALGENTA_API_KEY=de_live_..." in local_runtime
    assert "algenta import" in cli_sdk
    assert "all` -> run every scenario" in cli_sdk
    assert "1,recipes" in cli_sdk
    assert "algenta demo --scenario region --no-interactive" in cli_sdk
