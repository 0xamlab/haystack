from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
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
    assert "Algenta Source Import" in proc.stdout
    assert "Resolved plan" in proc.stdout
    assert "Query result" in proc.stdout


def test_runtime_docs_primary_examples_present() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = (ROOT / "apps" / "docs" / "docs" / "quickstart.md").read_text(encoding="utf-8")
    python_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text(encoding="utf-8")
    cli_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md").read_text(encoding="utf-8")

    assert "from algenta import Runtime" in readme
    assert "from algenta import Runtime" in quickstart
    assert "from algenta import Runtime" in python_sdk
    assert "algenta import" in readme
    assert "algenta import" in quickstart
    assert "algenta import" in cli_sdk
