"""Shared helpers for test_cli_data_* sub-modules.

Extracted from tests/test_cli_data.py during modularization.
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy

from apps.platform_contract import load_platform_contract_manifest


def _capture_stdout(fn, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def _capture_stderr(fn, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with redirect_stderr(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def _platform_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())
