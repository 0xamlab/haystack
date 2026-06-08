from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
README = ROOT / "README.md"


def test_makefile_exposes_repository_intelligence_channel_parity_target() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "repository-intelligence-channel-parity:" in text
    assert "## repository-intelligence-channel-parity:" in text
    assert "RI_CHANNEL_PARITY_FILTER ?= repository" in text
    assert "RI_CHANNEL_PARITY_OUTPUT ?= build/repository_intelligence_channel_parity_summary.json" in text
    assert "RI_CHANNEL_PARITY_LOGS_DIR ?= build/repository_intelligence_channel_parity_logs" in text
    assert "RI_CHANNEL_PARITY_JOBS ?= 1" in text
    assert "$(REPO_PYTHON) scripts/run_repository_intelligence_channel_parity.py \\" in text
    assert '--filter "$(RI_CHANNEL_PARITY_FILTER)" \\' in text
    assert '--output "$(RI_CHANNEL_PARITY_OUTPUT)" \\' in text
    assert '--jobs "$(RI_CHANNEL_PARITY_JOBS)" \\' in text
    assert '--logs-dir "$(RI_CHANNEL_PARITY_LOGS_DIR)"' in text


def test_make_help_lists_repository_intelligence_channel_parity_target() -> None:
    proc = subprocess.run(  # noqa: S603
        ["make", "help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "repository-intelligence-channel-parity" in proc.stdout


def test_readme_surfaces_repository_intelligence_channel_parity_entrypoint() -> None:
    text = README.read_text(encoding="utf-8")

    assert "Repository Intelligence channel parity proof" in text
    assert "make repository-intelligence-channel-parity" in text
    assert "build/repository_intelligence_channel_parity_summary.json" in text
    assert "build/repository_intelligence_channel_parity_logs/" in text
    assert "RI_CHANNEL_PARITY_FILTER" in text
    assert "RI_CHANNEL_PARITY_OUTPUT" in text
    assert "RI_CHANNEL_PARITY_LOGS_DIR" in text
    assert "RI_CHANNEL_PARITY_JOBS" in text
