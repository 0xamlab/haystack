from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def _choose_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def isolated_cline_runtime_environment(
    *, prefix: str = "algenta-cline-runtime-"
) -> Iterator[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
        runtime_root = Path(temp_dir)
        cline_dir = runtime_root / ".cline"
        cline_data_dir = cline_dir / "data"
        db_dir = cline_data_dir / "db"
        session_dir = cline_data_dir / "sessions"
        team_dir = cline_data_dir / "teams"
        for directory in (cline_dir, cline_data_dir, db_dir, session_dir, team_dir):
            directory.mkdir(parents=True, exist_ok=True)
        yield {
            "HOME": str(runtime_root),
            "CLINE_DIR": str(cline_dir),
            "CLINE_DATA_DIR": str(cline_data_dir),
            "CLINE_DB_DATA_DIR": str(db_dir),
            "CLINE_SESSION_DATA_DIR": str(session_dir),
            "CLINE_TEAM_DATA_DIR": str(team_dir),
        }


@contextlib.contextmanager
def agent_core_runtime(
    root: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> Iterator[str]:
    run_server = root / "agent-core" / "run-server.mjs"
    if shutil.which("node") is None:
        raise RuntimeError("node is required to collect Cline runtime proofs")
    if shutil.which("bun") is None:
        raise RuntimeError("bun is required to collect Cline runtime proofs")
    if not run_server.exists():
        raise RuntimeError(f"missing agent-core runtime launcher: {run_server}")

    with isolated_cline_runtime_environment() as runtime_env:
        env = {
            **os.environ,
            **runtime_env,
            "AGENT_CORE_PORT": "0",
            **(extra_env or {}),
        }
        proc = subprocess.Popen(
            [shutil.which("node") or "node", str(run_server)],
            cwd=str(run_server.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        try:
            port = None
            deadline = time.monotonic() + 30.0
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


@contextlib.contextmanager
def local_api_server(
    root: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> Iterator[str]:
    python_bin = root / ".venv" / "bin" / "python"
    if not python_bin.exists():
        python_name = shutil.which("python3")
        if python_name is None:
            raise RuntimeError("python3 is required to start the local API server")
        python_bin = Path(python_name)

    port = _choose_free_port()
    env = {
        **os.environ,
        "PYTHONPATH": str(root),
        **(extra_env or {}),
    }
    with tempfile.NamedTemporaryFile(
        prefix="algenta-local-api-", suffix=".log", mode="w+", encoding="utf-8"
    ) as log_file:
        proc = subprocess.Popen(
            [
                str(python_bin),
                "-m",
                "uvicorn",
                "apps.api_server.main:app",
                "--port",
                str(port),
                "--timeout-graceful-shutdown",
                "10",
            ],
            cwd=str(root),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    log_file.flush()
                    log_file.seek(0)
                    raise RuntimeError(
                        "local API server exited before readiness:\n"
                        + log_file.read()[-4000:]
                    )
                try:
                    status, payload = request_json("GET", f"{base_url}/v1/health")
                except Exception:
                    time.sleep(0.25)
                    continue
                if status == 200 and isinstance(payload, dict):
                    yield base_url
                    return
                time.sleep(0.25)
            log_file.flush()
            log_file.seek(0)
            raise RuntimeError(
                "local API server did not become ready within 30s:\n"
                + log_file.read()[-4000:]
            )
        finally:
            proc.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=5)
            if proc.poll() is None:
                proc.kill()


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 20,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"content-type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def request_text(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 20,
) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"content-type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
