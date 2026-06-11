from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import pytest

from apps.api_server.services.cline_runtime_contract import (
    SCRUBBED_PROVIDER_ENV,
    collect_runtime_contract_report,
)


ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("bun") is None,
    reason="node and bun are required for Cline runtime contract tests",
)


def test_collect_runtime_contract_report_proves_core_session_routes(tmp_path: Path) -> None:
    payload = collect_runtime_contract_report(root=ROOT, output_path=tmp_path / "runtime_contract.json")

    assert payload["runtime_manifest"]["status_code"] == 200
    assert payload["runtime_manifest"]["payload"]["runtime"]["kind"] == "cline"
    assert payload["runtime_manifest"]["payload"]["runtime"]["is_stub"] is False
    assert payload["session_contract"]["create"]["status_code"] == 201
    assert payload["session_contract"]["list"]["status_code"] == 200
    assert payload["session_contract"]["get"]["status_code"] == 200
    assert payload["session_contract"]["messages"]["status_code"] == 200
    assert payload["session_contract"]["usage"]["status_code"] == 200
    assert payload["session_contract"]["events"]["status_code"] == 200
    assert payload["session_contract"]["events_ndjson"]["status_code"] == 200
    assert payload["session_contract"]["events_sse"]["status_code"] == 200
    assert payload["session_contract"]["delete"]["status_code"] == 200
    assert payload["session_contract"]["run_compatibility"]["status_code"] == 200
    assert payload["session_contract"]["run_compatibility"]["final_frame_present"] is True


def test_collect_runtime_contract_report_scrubs_live_provider_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_extra_env: dict[str, str] = {}

    @contextlib.contextmanager
    def _fake_runtime(root: Path, *, extra_env: dict[str, str] | None = None):
        assert root == ROOT
        observed_extra_env.update(extra_env or {})
        yield "http://runtime"

    request_rows = iter(
        [
            (200, {"runtime": {"kind": "cline", "is_stub": False}}),
            (201, {"session_id": "session_123"}),
            (200, {"sessions": []}),
            (200, {"session_id": "session_123"}),
            (200, {"messages": []}),
            (200, {"usage": {}}),
            (200, {"events": []}),
            (409, {"error": {"code": "session_start_failed"}}),
            (200, {"deleted": True}),
        ]
    )
    text_rows = iter(
        [
            (200, '{"event":"created"}\n'),
            (200, "event: created\n\n"),
            (200, '{"type":"final","status":"failed"}\n'),
        ]
    )

    monkeypatch.setattr(
        "apps.api_server.services.cline_runtime_contract.agent_core_runtime",
        _fake_runtime,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_runtime_contract.request_json",
        lambda *args, **kwargs: next(request_rows),
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_runtime_contract.request_text",
        lambda *args, **kwargs: next(text_rows),
    )

    payload = collect_runtime_contract_report(root=ROOT, output_path=tmp_path / "runtime_contract.json")

    assert observed_extra_env == SCRUBBED_PROVIDER_ENV
    assert payload["session_contract"]["start"]["status_code"] == 409
    assert payload["session_contract"]["run_compatibility"]["final_frame_present"] is True
