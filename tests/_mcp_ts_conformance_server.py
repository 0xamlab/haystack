"""Standalone launcher for the TypeScript official-MCP-SDK conformance suite (Track A3b).

NOT a pytest test module (leading underscore, no ``test_*`` functions -- pytest never collects
this file) -- a small long-lived process spawned by
``packages/ts-sdk/src/mcp_official_sdk_conformance.test.ts`` via Node's ``child_process``.

This deliberately reuses ``tests/_mcp_live_server_fixture.py`` (``live_api_server`` /
``seed_owner_org_and_key``) VERBATIM rather than reimplementing any of it in TypeScript or in a
second Python copy -- the exact same real stack Track A3's Python conformance suite
(``tests/test_mcp_official_sdk_e2e.py``) already drives: a real ``apps.api_server.main:app``
uvicorn subprocess, real Postgres-backed auth, real embedded ``/mcp`` + legacy ``/mcp/sse``
mounts. The TS suite talks to that real server exclusively through the official
``@modelcontextprotocol/sdk`` TypeScript client, over a real loopback socket -- this script's
only job is to stand the server up, seed a real owner org/API key, and hand the connection
details to the Node parent.

Protocol with the parent Node process:
  1. Boots the real live server + seeds a real owner org/API key.
  2. Prints exactly one JSON line to stdout: ``{"base_url": ..., "owner_key": ..., "org_id": ...}``
     (the parent scans stdout for the first line that parses as JSON with a "base_url" key, so
     any incidental logging before/after it is harmless).
  3. Blocks until it receives SIGTERM, then tears the live server down cleanly (terminates the
     real uvicorn subprocess via ``live_api_server``'s own ``finally``).

Depends on the same ambient test environment ``tests/conftest.py`` establishes (DATABASE_URL,
JWT_SECRET, etc., via ``os.environ.setdefault`` at import time) and on the test database already
being migrated -- true whenever this runs as part of the repo's real check graph (``pnpm check``
runs ``test:hardening`` -- which already exercises pytest, and with it the migration -- before
``pnpm test`` reaches ``test:js``, the step that spawns this script). Not intended to be run
before any pytest invocation against a bare, unmigrated database.

Run directly (not via pytest):
  ./scripts/run_repo_python.sh tests/_mcp_ts_conformance_server.py
"""

from __future__ import annotations

import asyncio
import json
import signal
import tempfile
import time
from pathlib import Path
from types import FrameType

from tests._mcp_live_server_fixture import live_api_server, seed_owner_org_and_key


class _ShutdownError(Exception):
    """Raised from the SIGTERM handler to unwind the ``live_api_server`` context manager cleanly."""


def _handle_sigterm(signum: int, frame: FrameType | None) -> None:
    del signum, frame
    raise _ShutdownError()


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    runtime_dir = Path(tempfile.mkdtemp(prefix="a3b-ts-conformance-runtime-"))
    try:
        # The whole `with` block, not just the sleep loop below, is inside this try/except: the
        # parent Node process signals this script's entire process group at once (see
        # packages/ts-sdk/src/mcp_official_sdk_conformance.test.ts's stopLiveServer), so the real
        # uvicorn subprocess that `live_api_server` owns often receives its own independent SIGTERM
        # at the same moment this process does. If THIS process's handler fires again while already
        # unwinding (e.g. during live_api_server's own `finally: proc.wait(...)`), that second
        # _ShutdownError must not escape as an uncaught, traceback-printing exit -- teardown is already
        # underway, and the group-wide signal already covers the real uvicorn subprocess either way.
        with live_api_server(runtime_dir=runtime_dir) as base_url:
            owner_key, org_id = asyncio.run(seed_owner_org_and_key("ts-official-sdk"))
            print(
                json.dumps({"base_url": base_url, "owner_key": owner_key, "org_id": org_id}),
                flush=True,
            )
            while True:
                time.sleep(3600)
    except _ShutdownError:
        pass


if __name__ == "__main__":
    main()
