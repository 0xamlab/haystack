from __future__ import annotations

import runpy
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_CONFTEST = runpy.run_path(str(_TESTS_DIR / "conftest.py"))
_pytest_ignore_collect = _CONFTEST["pytest_ignore_collect"]


def test_pytest_ignore_collect_skips_standalone_go_live_runner():
    path = _TESTS_DIR / "integration" / "test_go_live_connectivity_real.py"
    assert _pytest_ignore_collect(path, None) is True


def test_pytest_ignore_collect_keeps_pytest_native_integration_suite():
    path = _TESTS_DIR / "integration" / "test_adversarial.py"
    assert _pytest_ignore_collect(path, None) is False


def test_pytest_ignore_collect_skips_standalone_typescript_runtime_runner():
    path = _TESTS_DIR / "integration" / "test_typescript_runtime_live.py"
    assert _pytest_ignore_collect(path, None) is True
