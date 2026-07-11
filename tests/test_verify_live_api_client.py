from __future__ import annotations

import importlib.util
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_live_api.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_live_api_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    status = 200

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"status":"ok"}'


def test_req_sends_live_audit_user_agent(monkeypatch: Any) -> None:
    script = _load_script()
    seen_headers: dict[str, str | None] = {}

    def fake_urlopen(request: urllib.request.Request) -> _FakeResponse:
        seen_headers["user_agent"] = request.get_header("User-agent")
        seen_headers["accept"] = request.get_header("Accept")
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    status, body = script.req(base_url="https://api.algenta.ai", method="GET", path="/v1/health")

    assert status == 200
    assert body == {"status": "ok"}
    assert seen_headers == {
        "user_agent": script.AUDIT_USER_AGENT,
        "accept": "application/json",
    }


def test_req_returns_structured_error_for_non_json_http_error(monkeypatch: Any) -> None:
    script = _load_script()

    def fake_urlopen(request: urllib.request.Request) -> object:
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {},
            BytesIO(b"<html>blocked by edge</html>"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    status, body = script.req(base_url="https://api.algenta.ai", method="GET", path="/v1/health")

    assert status == 403
    assert body["error"]["code"] == "non_json_response"
    assert body["error"]["details"]["status_code"] == 403
    assert "blocked by edge" in body["error"]["details"]["body_prefix"]
