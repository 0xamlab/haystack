"""`algenta login` must send a real User-Agent, or every login is rejected at the Cloudflare edge.

algenta 1.0.4 could not log in AT ALL. `login._request` sent only ``{"Accept": "application/json"}``,
so urllib supplied its default ``Python-urllib/X.Y``, which the api.algenta.ai edge rejects with
Cloudflare Error 1010 (``browser_signature_banned``) BEFORE the request reaches the control plane.
Measured against the published 1.0.4 wheel on 2026-07-28:

    no User-Agent            -> HTTP 403, body contains 1010 / browser_signature_banned
    User-Agent: algenta-cli… -> HTTP 401 (reached the origin, rejected for missing auth)

Every one of api.telys.ai / api.algenta.ai / api.codna.ai / api.sqai.com blocks the urllib default,
so this failure mode is fatal by construction for any stdlib-urllib CLI. telys shipped the identical
bug (fixed in telys#90 / 0.1.0b4) — algenta/login.py even says "Mirrors telys-sdk telys/login.py".
codna 0.1.46 and sqai 0.1.13 already send a UA and were never affected.

These tests read login.py from disk rather than importing it. `algenta` is a distributable package,
not an installed dependency of this repo's test environment, so ``pytest.importorskip`` would SKIP
them in CI — and a regression guard that skips guards nothing.
"""
from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGIN_SOURCE = REPO_ROOT / "packages" / "algenta" / "algenta" / "login.py"
_LOGIN_SRC = LOGIN_SOURCE.read_text("utf-8")


def test_login_module_defines_a_user_agent() -> None:
    m = re.search(r'^_USER_AGENT\s*=\s*f?"([^"]*)"', _LOGIN_SRC, re.M)
    assert m, "_USER_AGENT missing — every control-plane call will be 403'd by Cloudflare 1010"
    ua = m.group(1)
    # It is an f-string, so the literal holds placeholders rather than values:
    #   f"{_CLIENT_ID}/{_cli_version} python-urllib/{platform.python_version()}"
    assert "_CLIENT_ID" in ua or "algenta-cli" in ua, f"UA should identify the CLI, got {ua!r}"
    assert "python-urllib/" in ua, f"UA should record the interpreter, got {ua!r}"
    assert re.search(r'^_CLIENT_ID\s*=\s*"algenta-cli"', _LOGIN_SRC, re.M), (
        "the UA interpolates _CLIENT_ID, so that constant must be the CLI name"
    )


def test_request_actually_sends_the_user_agent_header() -> None:
    """Defining the constant is not enough — it has to reach the request headers."""
    body = _LOGIN_SRC.split("def _request", 1)
    assert len(body) == 2, "login.py no longer defines _request"
    headers = re.search(r"headers\s*=\s*\{[^}]*\}", body[1])
    assert headers, "could not find the headers dict in _request"
    assert "User-Agent" in headers.group(0), (
        f"_request builds headers without a User-Agent (the 1.0.4 bug): {headers.group(0)!r}"
    )
    assert "_USER_AGENT" in headers.group(0), "use the module constant, not a literal"


def test_user_agent_is_not_the_urllib_default() -> None:
    """``Python-urllib/…`` is the exact signature Cloudflare bans."""
    assert "Python-urllib" not in _LOGIN_SRC.split("_USER_AGENT", 1)[1][:200]


def test_bundled_worker_python_pin_is_intact() -> None:
    """The 3.14-only pin on `algenta` is LOAD-BEARING. Do not widen it as a metadata edit.

    This guard exists because widening it looks safe and is not. `algenta` bundles its own CPython
    3.14 worker binary and launches it with ``PYTHONHOME = sys.base_prefix`` — the HOST
    interpreter's prefix (see algenta/native/worker.py::_worker_environment, added in #377 alongside
    this very pin). On a mismatched host the worker gets the wrong stdlib.

    Verified empirically on 2026-07-28, host Python 3.12 vs 3.14, same wheels:

        3.14   `algenta simulate` -> Expected outcome 29,812, "Engine: bundled native runtime"
        3.12   `algenta simulate` -> "fallback: denied", no result produced

    Crucially the failure is SILENT at install and import time: on 3.12 the package installs,
    imports, and `algenta runtime doctor` even reports ``status: READY``. Only a real workload
    fails. So a widened floor would ship something strictly worse than the current clean
    install-time error — users would get a package that appears to work and then does not compute.

    Widening genuinely requires shipping per-Python worker builds (or decoupling PYTHONHOME from the
    host), not a pyproject change. `python-sdk` and `mcp` are pure Python and correctly declare
    >=3.10; only `algenta` and `algenta-runtime-native` carry the bundled worker and its pin.
    """
    for pkg in ("algenta", "algenta-runtime-native"):
        pyproject = REPO_ROOT / "packages" / pkg / "pyproject.toml"
        spec = re.search(r'^requires-python\s*=\s*"([^"]+)"', pyproject.read_text("utf-8"), re.M)
        assert spec, f"no requires-python in {pkg}"
        assert spec.group(1) == ">=3.14,<3.15", (
            f"{pkg} requires-python is {spec.group(1)!r}; the bundled CPython 3.14 worker makes this "
            "pin load-bearing — see this test's docstring before changing it"
        )
