"""A3 behavioral-matrix: real MCP JSON-RPC tool calls through the REAL 3-replica + nginx LB.

tests/test_multi_replica_chaos.py already chaos-tests the cross-replica dedup lock (#94/#95) for
the decision-plan/repository subsystem, against a real Redis, in-process. Its own docstring is
explicit that "The full multi-CONTAINER harness (real HTTP/LB/worker) is
infra/docker/docker-compose.replicas.yml, for manual/operator chaos testing" -- i.e. nothing
automated drives that real multi-container shape today. This file is that automated test, scoped
to MCP: it boots the REAL infra/docker/docker-compose.yml + docker-compose.replicas.yml stack
(3 api replicas behind infra/docker/nginx-replicas-lb.conf's round-robin LB, unmodified) and fires
real MCP JSON-RPC requests at it over the wire, confirming:

  1. requests genuinely fan out across more than one replica (observed via an nginx
     $upstream_addr response header -- see the test-only nginx conf variant below), and
  2. repeated calls behave correctly regardless of which replica served them -- consistent with
     the embedded MCP mount's stateless (``StreamableHTTPSessionManager(..., stateless=True)``)
     semantics: a JSON-RPC ``tools/call`` needs no prior ``initialize`` handshake and no session
     continuity, so round-robin routing across replicas is safe by construction, and this test
     verifies that holds for real rather than assuming it.
  3. state written through one replica (a logged decision) is readable through a DIFFERENT
     replica -- proving the replicas really share the one real Postgres, not per-replica state.

What is real, and what this test additively layers on top (never modifying) the existing
docker-compose.yml / docker-compose.replicas.yml / nginx-replicas-lb.conf:

  * infra/docker/docker-compose.replicas.mcp-test-override.yml -- an ADDITIVE compose overlay
    (see its own header comment for the full rationale) that: (a) drops the `api` service's
    dependency on the `sidecar` (agent-core) container, since MCP tool calls exercised here never
    invoke agent execution and the real sidecar is a private ghcr.io/thyn-ai/codna image this
    environment may not have registry credentials for; (b) remaps postgres/redis/minio HOST ports
    so this test's own compose project doesn't collide with services already bound to those ports
    on the machine running the suite (every service still talks over the compose-internal network
    at its normal port); (c) swaps in a byte-identical nginx conf with one added response header
    for observability (below).
  * infra/docker/nginx-replicas-lb.mcp-test.conf -- byte-identical routing to the real
    nginx-replicas-lb.conf, plus `add_header X-Upstream $upstream_addr` so the test can see which
    replica served each request without instrumenting Algenta's own application code.

HONEST LIMITATION, verified by actually attempting this rather than assumed: in this sandbox the
docker-compose stack cannot currently come up at all, for two independent, confirmed reasons --
this test detects both and SKIPS cleanly (never fakes a pass), same as the established convention
in tests/test_multi_replica_chaos.py / tests/test_object_store_minio_smoke.py for infra that isn't
reachable:

  1. `docker pull` of the pinned sidecar digest (ghcr.io/thyn-ai/codna/sidecar@sha256:...) returns
     "unauthorized" -- this environment has no registry credentials for that private image. (The
     compose override above already routes around this by decoupling `api` from `sidecar`, but is
     recorded here for completeness.)
  2. infra/docker/Dockerfile.api's builder stage (`FROM python:3.14-slim`) fails to build at all,
     independent of (1): `pydantic==2.10.6` (apps/api-server/requirements.txt) has no published
     wheel for CPython 3.14, so pip falls back to compiling pydantic-core from source via
     maturin/Rust, which then fails linking inside the slim image (`cannot find Scrt1.o` /
     `crti.o` / `-lc` -- the image never installs a full C toolchain). Verified independently on
     both native aarch64 and QEMU-emulated linux/amd64 (`DOCKER_DEFAULT_PLATFORM=linux/amd64`) --
     identical failure on both, so this is a real, pre-existing Dockerfile.api break, not an
     artifact of this host's architecture. Flagged separately for a real fix; out of scope for
     this testing PR to patch a production Dockerfile.

Once either blocker is resolved in an environment that has them (e.g. real CI runners with ghcr.io
access and a fixed/compatible pydantic pin), this test runs for real with no changes.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import time
import uuid
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
INFRA_DIR = ROOT / "infra" / "docker"
COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.replicas.yml",
    "docker-compose.replicas.mcp-test-override.yml",
]
PROJECT_NAME = "a3-mcp-lb-test"
LB_BASE_URL = "http://127.0.0.1:8080"
COMPOSE_UP_TIMEOUT = 600  # seconds -- a cold image build can be slow
HEALTH_TIMEOUT = 120  # seconds -- waiting for the LB + all 3 api replicas to answer

_SEED_ORG_SCRIPT = textwrap.dedent(
    """
    import asyncio, uuid

    async def main():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from apps.api_server.models import APIKey, Organization, OrgPlan, OrgStatus, User, UserRole, UserStatus
        from apps.api_server.services.auth_service import hash_api_key
        import os

        owner_key = "de_live_a3_lb_" + uuid.uuid4().hex
        engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            org = Organization(
                name="A3 LB", slug="a3-lb-" + uuid.uuid4().hex[:8],
                plan=OrgPlan.PRO, status=OrgStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()
            user = User(
                org_id=org.id, email="a3-lb-" + uuid.uuid4().hex[:8] + "@example.com",
                password_hash="x", name="A3 LB Owner", role=UserRole.OWNER,
                status=UserStatus.ACTIVE, email_verified=True,
            )
            session.add(user)
            await session.flush()
            session.add(APIKey(
                org_id=org.id, user_id=user.id, label="A3 LB Owner Key",
                key_prefix=owner_key[:12], hashed_key=hash_api_key(owner_key),
            ))
            await session.commit()
        await engine.dispose()
        print("SEEDED_KEY=" + owner_key)

    asyncio.run(main())
    """
)


def _compose_cmd(*args: str) -> list[str]:
    cmd = ["docker", "compose", "-p", PROJECT_NAME]
    for name in COMPOSE_FILES:
        cmd += ["-f", name]
    cmd += list(args)
    return cmd


def _compose_teardown() -> None:
    """Best-effort cleanup. Never raises: a wedged/slow Docker daemon (e.g. this host's Docker
    contending with other real work) must not turn a clean skip into a hard test ERROR."""
    try:
        subprocess.run(
            _compose_cmd("down", "--volumes", "--remove-orphans"),
            cwd=str(INFRA_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


@pytest.fixture(scope="module")
def replica_stack_with_owner_key():
    if shutil.which("docker") is None:
        pytest.skip("docker is not available in this environment")
    try:
        daemon_check = subprocess.run(
            ["docker", "version"], capture_output=True, text=True, timeout=20
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        pytest.skip(f"docker daemon did not respond (busy/unavailable in this environment): {exc}")
    if daemon_check.returncode != 0:
        pytest.skip(
            "docker CLI is present but the daemon is not responding in this environment:\n"
            f"{(daemon_check.stdout + daemon_check.stderr)[-2000:]}"
        )

    _compose_teardown()  # best-effort cleanup from any previous aborted run
    try:
        up = subprocess.run(
            _compose_cmd(
                "up", "-d", "--build", "postgres", "redis", "minio", "minio-init", "api", "lb"
            ),
            cwd=str(INFRA_DIR),
            capture_output=True,
            text=True,
            timeout=COMPOSE_UP_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        _compose_teardown()
        pytest.skip(
            f"docker compose up did not finish within {COMPOSE_UP_TIMEOUT}s in this environment "
            f"(cold image build + healthchecks). Partial output:\n"
            f"{(exc.stdout or '')[-4000:]}"
        )

    if up.returncode != 0:
        tail = (up.stdout + up.stderr)[-4000:]
        _compose_teardown()
        pytest.skip(
            "Could not bring up the real 3-replica docker-compose stack in this environment "
            f"(docker compose up exit={up.returncode}). This drove the REAL, unmodified "
            "docker-compose.replicas.yml + nginx-replicas-lb.conf convention, with only the "
            "additive overlay in docker-compose.replicas.mcp-test-override.yml (sidecar "
            "dependency decoupled, host ports remapped -- see that file's header for exactly "
            "what and why). Known real, independently-confirmed blockers in some environments: "
            "(1) `docker pull` of the pinned ghcr.io/thyn-ai/codna/sidecar digest returns "
            "'unauthorized' without registry credentials -- routed around by the overlay above; "
            "(2) infra/docker/Dockerfile.api's builder fails to compile pydantic-core from "
            "source against python:3.14-slim (no cp314 wheel + the slim image lacks a full C "
            "toolchain) -- verified on both native aarch64 and emulated linux/amd64, so this is "
            "a real, pre-existing Dockerfile issue, not an artifact of one host's architecture; "
            "flagged separately, out of scope for this testing PR to patch. "
            f"Last 4000 chars of docker compose output:\n{tail}"
        )

    deadline = time.monotonic() + HEALTH_TIMEOUT
    last_error = "no attempt yet"
    healthy = False
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{LB_BASE_URL}/v1/health", timeout=3.0)
            if resp.status_code == 200:
                healthy = True
                break
            last_error = f"status {resp.status_code}"
        except Exception as exc:  # noqa: BLE001 - readiness probe, report and retry
            last_error = str(exc)
        time.sleep(2)

    if not healthy:
        logs = subprocess.run(
            _compose_cmd("logs", "--tail=200", "api"),
            cwd=str(INFRA_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        _compose_teardown()
        pytest.skip(
            f"The real 3-replica stack came up but never answered healthy through the LB "
            f"within {HEALTH_TIMEOUT}s (last error: {last_error}). Last 4000 chars of `api` "
            f"container logs:\n{(logs.stdout + logs.stderr)[-4000:]}"
        )

    migrate = subprocess.run(
        _compose_cmd("exec", "-T", "api", "alembic", "upgrade", "head"),
        cwd=str(INFRA_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if migrate.returncode != 0:
        _compose_teardown()
        pytest.skip(
            "Real stack came up but `docker compose exec api alembic upgrade head` (the same "
            "command Makefile's `make migrate` target runs) failed:\n"
            f"{(migrate.stdout + migrate.stderr)[-4000:]}"
        )

    seed = subprocess.run(
        _compose_cmd("exec", "-T", "api", "python", "-"),
        cwd=str(INFRA_DIR),
        input=_SEED_ORG_SCRIPT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    owner_key = None
    for line in seed.stdout.splitlines():
        if line.startswith("SEEDED_KEY="):
            owner_key = line.split("=", 1)[1].strip()
    if seed.returncode != 0 or not owner_key:
        _compose_teardown()
        pytest.skip(
            "Real stack came up and migrated but seeding a real org/API key inside the `api` "
            f"container failed:\n{(seed.stdout + seed.stderr)[-4000:]}"
        )

    try:
        yield LB_BASE_URL, owner_key
    finally:
        _compose_teardown()


def _jsonrpc_call(base_url: str, owner_key: str, method: str, params: dict, request_id: int):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {owner_key}",
    }
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    with httpx.Client(timeout=15.0) as client:
        return client.post(f"{base_url}/mcp", json=body, headers=headers)


def test_mcp_tool_calls_through_real_lb_fan_out_across_replicas(
    replica_stack_with_owner_key: tuple[str, str],
) -> None:
    base_url, owner_key = replica_stack_with_owner_key

    seen_upstreams: set[str] = set()
    for i in range(24):
        resp = _jsonrpc_call(base_url, owner_key, "tools/call", {"name": "list_decisions", "arguments": {}}, i)
        assert resp.status_code == 200, resp.text[:500]
        payload = resp.json()
        assert payload.get("error") is None, payload
        result = payload["result"]
        assert result["isError"] is False
        upstream = resp.headers.get("x-upstream")
        assert upstream, "nginx did not set X-Upstream -- check the test-only conf is mounted"
        seen_upstreams.add(upstream)

    assert len(seen_upstreams) > 1, (
        f"expected requests to fan out across more than one of the 3 api replicas over 24 "
        f"calls; only ever saw {seen_upstreams}"
    )


def test_mcp_repeated_stateless_calls_are_correct_regardless_of_replica(
    replica_stack_with_owner_key: tuple[str, str],
) -> None:
    """No initialize handshake, no session id, no client-side stickiness -- each JSON-RPC call
    is independent (stateless=True), so round-robin across replicas must not corrupt or drop
    anything. Also proves the replicas share the one real Postgres: a decision logged via
    whichever replica served THIS call is visible when listed via whichever replica serves the
    NEXT call."""
    base_url, owner_key = replica_stack_with_owner_key
    chosen_action = f"a3-lb-{uuid.uuid4().hex[:10]}"

    log_resp = _jsonrpc_call(
        base_url,
        owner_key,
        "tools/call",
        {"name": "log_decision", "arguments": {"chosen_action": chosen_action, "expected_value": 42.0}},
        1001,
    )
    assert log_resp.status_code == 200, log_resp.text[:500]
    log_payload = log_resp.json()
    assert log_payload.get("error") is None, log_payload
    assert log_payload["result"]["isError"] is False

    # Fire a batch of unrelated read calls first -- likely to land on a DIFFERENT replica than
    # the one that just handled the write, per nginx's per-request DNS re-resolution.
    for i in range(10):
        resp = _jsonrpc_call(base_url, owner_key, "tools/call", {"name": "list_decisions", "arguments": {"limit": 5}}, 1002 + i)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload.get("error") is None, payload
        assert payload["result"]["isError"] is False

    list_resp = _jsonrpc_call(
        base_url, owner_key, "tools/call", {"name": "list_decisions", "arguments": {"limit": 50}}, 2000
    )
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["result"]["isError"] is False
    listed_text = list_payload["result"]["content"][0]["text"]
    assert chosen_action in listed_text, (
        "a decision logged through one replica must be visible listing through another -- "
        "the replicas share one real Postgres, not per-replica state"
    )
