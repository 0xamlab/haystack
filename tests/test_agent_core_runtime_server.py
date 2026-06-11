from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_RUN_SERVER = _ROOT / "agent-core" / "run-server.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("bun") is None or not _RUN_SERVER.exists(),
    reason="node, bun, and agent-core/run-server.mjs are required for runtime server tests",
)


@contextlib.contextmanager
def _agent_core_runtime(*, extra_env: dict[str, str] | None = None) -> Iterator[str]:
    env = {**os.environ, "AGENT_CORE_PORT": "0", **(extra_env or {})}
    proc = subprocess.Popen(
        [shutil.which("node") or "node", str(_RUN_SERVER)],
        cwd=str(_RUN_SERVER.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        port = None
        deadline = time.monotonic() + 20.0
        assert proc.stdout is not None
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    raise RuntimeError("agent-core runtime exited before readiness")
                continue
            if line.startswith("AGENT_CORE_LISTENING "):
                port = int(line.strip().split()[1])
                break
        if port is None:
            raise RuntimeError("agent-core runtime did not report a listening port")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
        if proc.poll() is None:
            proc.kill()


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _post_json(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _delete(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, headers=headers or {}, method="DELETE")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_runtime_manifest_reports_real_cline_runtime() -> None:
    with _agent_core_runtime() as base_url:
        status, payload = _get_json(f"{base_url}/manifest")

    assert status == 200
    assert payload["runtime"]["kind"] == "cline"
    assert payload["runtime"]["is_stub"] is False
    assert payload["capabilities"]["sessions"] is True
    assert payload["capabilities"]["streaming_events"] is True
    assert payload["offline_contract_only"] is False


def test_runtime_session_surfaces_owner_scope_and_delete() -> None:
    headers = {"x-session-owner": "alice"}
    with _agent_core_runtime() as base_url:
        status, created = _post_json(
            f"{base_url}/sessions",
            {
                "working_dir": str(_ROOT),
                "prompt": "Inspect the repository.",
                "repository_scope": "repo_123",
                "approval_profile": "repository_fix_gated",
                "idempotency_key": "runtime-test-1",
            },
            headers=headers,
        )
        assert status == 201
        session_id = created["session_id"]

        status, listed = _get_json(f"{base_url}/sessions", headers=headers)
        assert status == 200
        assert listed["sessions"][0]["session_id"] == session_id
        assert listed["sessions"][0]["owner"] == "alice"

        status, denied = _get_json(
            f"{base_url}/sessions/{session_id}",
            headers={"x-session-owner": "bob"},
        )
        assert status == 403
        assert denied["error"]["code"] == "session_owner_mismatch"

        status, deleted = _delete(f"{base_url}/sessions/{session_id}", headers=headers)
        assert status == 200
        assert deleted["deleted"] is True


def test_runtime_wrapper_does_not_enter_stub_without_full_quarantine() -> None:
    with _agent_core_runtime(extra_env={"ALGENTA_ALLOW_STUB_RUNTIME": "1"}) as base_url:
        status, payload = _get_json(f"{base_url}/manifest")

    assert status == 200
    assert payload["runtime"]["is_stub"] is False


def test_runtime_wrapper_enters_stub_only_with_full_quarantine() -> None:
    with _agent_core_runtime(
        extra_env={
            "ALGENTA_ALLOW_STUB_RUNTIME": "1",
            "ALGENTA_RUN_CLASS": "offline_contract_only",
            "NODE_ENV": "test",
        }
    ) as base_url:
        status, payload = _get_json(f"{base_url}/manifest")

    assert status == 200
    assert payload["runtime"]["is_stub"] is True
    assert payload["offline_contract_only"] is True
