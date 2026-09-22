"""pytest configuration for tests/spaces."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# --- algenta_spaces import path (shared package) -------------------------------
# The shared package lives outside any installed distribution; make it importable
# as `algenta_spaces` exactly as a vendored Space would see it.
_SHARED = Path(__file__).resolve().parents[2] / "apps" / "spaces" / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
# The shared-package tests import their rule helpers (`_rules.py`) from this
# directory whether or not tests/spaces is collected as a package.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# --- end algenta_spaces import path --------------------------------------------

# --- fleet tooling import path (apps/spaces/tools) ------------------------------
# manifest.py, stage.py, deploy.py, verify_remote.py, copy_lint.py, pin_drift.py and
# board_check.py are scripts that import each other by bare name; tests import them
# the same way the CLI does (sys.path[0] = the tools directory).
_TOOLS = Path(__file__).resolve().parents[2] / "apps" / "spaces" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def apps_spaces_dir(repo_root: Path) -> Path:
    return repo_root / "apps" / "spaces"


# --- end fleet tooling import path ----------------------------------------------
