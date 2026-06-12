"""B10 PR3: the runtime egress wrappers (runtime_urlopen / runtime_http_request).

The runtime plane's approved outbound transport: enforce the runtime egress policy BEFORE dispatch
(a deny raises before any socket), headers never reach dispatch through the ledger, and — crucially
for the SDK transport boundary — the wrapper does NOT import the api_server egress_guard."""

from __future__ import annotations

import urllib.request

import pytest

from apps.runtime import privacy_guard
from apps.runtime.privacy_guard import (
    RuntimeEgressPolicyDeniedError,
    runtime_http_request,
    runtime_urlopen,
)


@pytest.fixture(autouse=True)
def _runtime_dir(monkeypatch, tmp_path):
    # keep the append-only egress ledger out of the real runtime dir
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))


def _req(url: str = "https://api.public-unallowlisted.example/v1/x") -> urllib.request.Request:
    return urllib.request.Request(
        url, data=b"{}", headers={"Authorization": "Bearer secret"}, method="POST"
    )


def _deny_profile(monkeypatch):
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")


# --- runtime_urlopen ----------------------------------------------------------------------------


def test_runtime_urlopen_denies_before_dispatch(monkeypatch):
    _deny_profile(monkeypatch)
    calls = {"n": 0}

    def _sentinel(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("urlopen must not run after a policy deny")

    with pytest.raises(RuntimeEgressPolicyDeniedError):
        runtime_urlopen(_req(), surface="test_egress", timeout=5, urlopen_fn=_sentinel)
    assert calls["n"] == 0


def test_runtime_urlopen_allows_and_dispatches(monkeypatch):
    monkeypatch.setattr(privacy_guard, "enforce_runtime_egress", lambda *a, **k: None)
    captured = {}

    def _spy(request, timeout=None):
        captured["request"] = request
        captured["timeout"] = timeout
        return "RESP"

    out = runtime_urlopen(_req(), surface="test_egress", timeout=8, urlopen_fn=_spy)
    assert out == "RESP"
    assert captured["timeout"] == 8
    # exact-equality (not startswith) — a URL-host substring check trips CodeQL's
    # incomplete-url-substring-sanitization rule, and we want the precise URL anyway.
    assert captured["request"].full_url == "https://api.public-unallowlisted.example/v1/x"


# --- runtime_http_request -----------------------------------------------------------------------


async def test_runtime_http_request_denies_before_dispatch(monkeypatch):
    _deny_profile(monkeypatch)

    class _Client:
        async def post(self, *args, **kwargs):
            raise AssertionError("must not dispatch after a policy deny")

    with pytest.raises(RuntimeEgressPolicyDeniedError):
        await runtime_http_request(
            method="POST",
            url="https://api.public-unallowlisted.example/v1/x",
            surface="test_egress",
            client=_Client(),
            json={},
        )


async def test_runtime_http_request_allows_and_dispatches(monkeypatch):
    monkeypatch.setattr(privacy_guard, "enforce_runtime_egress", lambda *a, **k: None)
    captured = {}

    class _Client:
        async def get(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return "RESP"

    out = await runtime_http_request(
        method="GET",
        url="https://x.example/health",
        surface="test_egress",
        client=_Client(),
        headers={"h": "1"},
    )
    assert out == "RESP"
    assert captured["url"] == "https://x.example/health"
    assert captured["kwargs"]["headers"] == {"h": "1"}


# --- SDK transport boundary ---------------------------------------------------------------------


def test_runtime_wrapper_does_not_import_api_server_egress_guard():
    import inspect

    src = inspect.getsource(privacy_guard)
    assert "api_server.services.egress_guard" not in src
    assert "from apps.api_server" not in src
