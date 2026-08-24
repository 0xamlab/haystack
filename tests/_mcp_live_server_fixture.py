"""Shared helper for A3 MCP behavioral-matrix tests: a REAL live API server (real Postgres,
real routers, real MCP tool handlers going over real HTTP) bound to a fresh ephemeral loopback
port, plus a real org + owner API key seeded directly in Postgres.

This intentionally reuses tests/conftest.py's own live-server plumbing
(``_build_live_subprocess_env`` / ``_wait_for_live_server``) rather than re-implementing it, and
mirrors tests/e2e/test_agentic_headline_journey.py's ``_seed_org_and_keys`` for org/key seeding —
both are the repo's own, already-exercised patterns for "real running server, real DB" tests.

Not a test module itself (no ``test_*`` functions) — imported by the new A3 test files.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

from tests.conftest import _build_live_subprocess_env, _wait_for_live_server

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    """Bind to port 0 to let the OS hand back an unused loopback port."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def live_api_server(*, runtime_dir: Path, extra_env: dict[str, str] | None = None) -> Iterator[str]:
    """Boot a REAL ``apps.api_server.main:app`` uvicorn subprocess on a fresh loopback port.

    Yields the server's base URL (``http://127.0.0.1:<port>``). Terminates the subprocess on exit.
    ``ALGENTA_EGRESS_ALLOWLIST=127.0.0.1,localhost`` matches the established CI convention (see
    ci.yml's "Repository object-store + coordination s3 integration" step) for letting an
    explicitly-configured loopback destination (here: a test webhook receiver) through the SSRF
    guard via the ``destination_allowlisted`` decision path, without arming
    ``ALGENTA_ALLOW_OUTBOUND_NETWORK`` (which would instead arm the private-destination block).
    """
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_dir = Path(tempfile.mkdtemp(prefix="a3-mcp-live-api-"))
    log_path = log_dir / f"api_server_{port}.log"
    env = _build_live_subprocess_env(
        ALGENTA_RUNTIME_DIR=str(runtime_dir),
        ALGENTA_EGRESS_ALLOWLIST="127.0.0.1,localhost",
        # The embedded MCP mount (apps/mcp_server/transports/http_sse.py's
        # _embedded_downstream_base_url) forwards tool calls back to "this same API process" by
        # reading PORT (default 8000) unless ALGENTA_MCP_LOOPBACK_URL is set. Since this server
        # binds a fresh ephemeral port (not 8000), it must be told its own real port explicitly,
        # or every embedded tool call 503s with mcp_upstream_unavailable trying to reach :8000.
        ALGENTA_MCP_LOOPBACK_URL=base_url,
        **(extra_env or {}),
    )
    log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api_server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_handle.close()
    try:
        _wait_for_live_server(base_url, proc=proc, log_path=log_path)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


async def seed_owner_org_and_key(label: str) -> tuple[str, str]:
    """Create a real org + a real owner API key directly in Postgres.

    Mirrors ``tests/e2e/test_agentic_headline_journey.py::_seed_org_and_keys`` (owner half only).
    Returns ``(owner_raw_key, org_id_str)``.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import (
        APIKey,
        Organization,
        OrgPlan,
        OrgStatus,
        User,
        UserRole,
        UserStatus,
    )
    from apps.api_server.services.auth_service import hash_api_key

    owner_key = f"de_live_a3_{label}_{uuid.uuid4().hex}"
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            org = Organization(
                name=f"A3 {label}",
                slug=f"a3-{label}-{uuid.uuid4().hex[:8]}",
                plan=OrgPlan.PRO,
                status=OrgStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()
            user = User(
                org_id=org.id,
                email=f"a3-{label}-{uuid.uuid4().hex[:8]}@example.com",
                password_hash="x",
                name="A3 Owner",
                role=UserRole.OWNER,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            session.add(
                APIKey(
                    org_id=org.id,
                    user_id=user.id,
                    label=f"A3 {label} Owner Key",
                    key_prefix=owner_key[:12],
                    hashed_key=hash_api_key(owner_key),
                )
            )
            await session.commit()
            return owner_key, str(org.id)
    finally:
        await engine.dispose()
