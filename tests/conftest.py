"""
Shared pytest fixtures for all test suites.

Unit tests: no external dependencies required.
Legacy live integration tests can auto-start a local API server under pytest.
"""

import asyncio
import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from tests.integration.live_local_defaults import (
    DEFAULT_LOCAL_LIVE_API_KEY,
    DEFAULT_LOCAL_LIVE_BASE_URL,
)

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment before importing app
os.environ.setdefault("API_ENV", "development")
os.environ.setdefault("PYTEST_RUNNING", "1")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://angel:@localhost:5432/decision_engine")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://angel:@localhost:5432/decision_engine")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")  # DB 1 for tests
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")
os.environ.setdefault("DE_BASE_URL", DEFAULT_LOCAL_LIVE_BASE_URL)
os.environ.setdefault("ALGENTA_BASE_URL", DEFAULT_LOCAL_LIVE_BASE_URL)

_ROOT = Path(__file__).resolve().parent.parent
_LIVE_SERVER_MARKER = DEFAULT_LOCAL_LIVE_BASE_URL
_LIVE_SERVER_LOG_DIR: Path | None = None
_LIVE_SERVER_LOG_PATH: Path | None = None
_LIVE_SERVER_PROC: subprocess.Popen[str] | None = None
_PYTEST_SOURCES_DIR = Path(tempfile.mkdtemp(prefix="algenta-pytest-sources-"))
_PYTEST_ARTIFACT_CACHE_DIR = Path(tempfile.mkdtemp(prefix="algenta-pytest-artifacts-"))
os.environ.setdefault("ALGENTA_SOURCES_DIR", str(_PYTEST_SOURCES_DIR))
os.environ.setdefault("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", str(_PYTEST_ARTIFACT_CACHE_DIR))
_BASE_PROCESS_ENV_KEYS = (
    "PATH",
    "HOME",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "SHELL",
    "USER",
    "LOGNAME",
    "VIRTUAL_ENV",
    "PYENV_ROOT",
    "PYENV_VERSION",
)
_BASE_TEST_ENV = {
    "API_ENV": os.environ["API_ENV"],
    "DATABASE_URL": os.environ["DATABASE_URL"],
    "DATABASE_URL_SYNC": os.environ["DATABASE_URL_SYNC"],
    "REDIS_URL": os.environ["REDIS_URL"],
    "S3_ENDPOINT_URL": os.environ["S3_ENDPOINT_URL"],
    "JWT_SECRET": os.environ["JWT_SECRET"],
    "ARROW_USER_SIMD_LEVEL": os.environ.get("ARROW_USER_SIMD_LEVEL", "NONE"),
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "KMP_INIT_AT_FORK": "FALSE",
    "DE_BASE_URL": DEFAULT_LOCAL_LIVE_BASE_URL,
    "ALGENTA_BASE_URL": DEFAULT_LOCAL_LIVE_BASE_URL,
    "ALGENTA_SOURCES_DIR": str(_PYTEST_SOURCES_DIR),
    "ALGENTA_SOURCE_ARTIFACT_CACHE_DIR": str(_PYTEST_ARTIFACT_CACHE_DIR),
}


def _build_live_subprocess_env(**overrides: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in _BASE_PROCESS_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env.update(_BASE_TEST_ENV)
    env["PYTHONPATH"] = str(_ROOT)
    env.update({key: value for key, value in overrides.items() if value is not None})
    return env


def _run_migrations() -> None:
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(_ROOT / "apps" / "api_server" / "alembic.ini"),
        "upgrade",
        "head",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(_ROOT),
        env=_build_live_subprocess_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Alembic upgrade failed:\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


async def _seed_legacy_live_api_key() -> str:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import (
        APIKey,
        APIKeyStatus,
        Organization,
        OrgPlan,
        OrgStatus,
        User,
        UserRole,
        UserStatus,
    )
    from apps.api_server.services.auth_service import hash_api_key

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    hashed_key = hash_api_key(DEFAULT_LOCAL_LIVE_API_KEY)

    async with session_factory() as session:
        org_result = await session.execute(
            select(Organization).where(Organization.slug == "pytest-live-localhost")
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            org = Organization(
                name="Pytest Live Localhost",
                slug="pytest-live-localhost",
                plan=OrgPlan.PRO,
                status=OrgStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()
        else:
            org.plan = OrgPlan.PRO
            org.status = OrgStatus.ACTIVE

        user_result = await session.execute(
            select(User).where(User.org_id == org.id).where(User.email == "pytest-live@example.com")
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(
                org_id=org.id,
                email="pytest-live@example.com",
                password_hash="pytest-live-localhost",
                name="Pytest Live",
                role=UserRole.OWNER,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()
        else:
            user.role = UserRole.OWNER
            user.status = UserStatus.ACTIVE
            user.email_verified = True

        key_result = await session.execute(select(APIKey).where(APIKey.hashed_key == hashed_key))
        api_key = key_result.scalar_one_or_none()
        if api_key is None:
            api_key = APIKey(
                org_id=org.id,
                user_id=user.id,
                label="Pytest Live Localhost",
                key_prefix=DEFAULT_LOCAL_LIVE_API_KEY[:12],
                hashed_key=hashed_key,
                status=APIKeyStatus.ACTIVE,
            )
            session.add(api_key)
        else:
            api_key.org_id = org.id
            api_key.user_id = user.id
            api_key.label = "Pytest Live Localhost"
            api_key.key_prefix = DEFAULT_LOCAL_LIVE_API_KEY[:12]
            api_key.status = APIKeyStatus.ACTIVE

        await session.commit()

    await engine.dispose()
    return DEFAULT_LOCAL_LIVE_API_KEY


def _read_live_server_log(log_path: Path | None) -> str:
    if log_path is None or not log_path.exists():
        return ""
    try:
        contents = log_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    contents = contents.strip()
    if not contents:
        return ""
    tail = contents[-4000:]
    return f"\nstartup log tail:\n{tail}"


def _wait_for_live_server(
    base_url: str,
    *,
    timeout: float = 45.0,
    proc: subprocess.Popen[str] | None = None,
    log_path: Path | None = None,
) -> None:
    start = time.monotonic()
    last_error = "no response"
    while time.monotonic() - start < timeout:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(
                f"Live API server exited before readiness probe with code {proc.returncode}."
                f"{_read_live_server_log(log_path)}"
            )
        try:
            resp = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if resp.status_code == 200:
                return
            last_error = f"status {resp.status_code}"
        except Exception as exc:  # pragma: no cover - best effort startup probe
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_live_server_log(log_path)}"
    )


def _port_open(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _legacy_live_test_requested(session: pytest.Session) -> bool:
    for item in session.items:
        path = Path(str(item.fspath))
        if not path.exists() or path.suffix != ".py":
            continue
        if "tests/integration" not in path.as_posix():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _LIVE_SERVER_MARKER in source and "DE_SKIP_API" in source:
            return True
    return False


def _start_live_server() -> tuple[subprocess.Popen[str], Path, Path]:
    log_dir = Path(tempfile.mkdtemp(prefix="pytest-live-api-"))
    log_path = log_dir / "api_server_8000.log"
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
            "8000",
            "--log-level",
            "warning",
        ],
        cwd=str(_ROOT),
        env=_build_live_subprocess_env(
            DE_API_KEY=DEFAULT_LOCAL_LIVE_API_KEY,
            ALGENTA_API_KEY=DEFAULT_LOCAL_LIVE_API_KEY,
        ),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_handle.close()
    _wait_for_live_server("http://127.0.0.1:8000", proc=proc, log_path=log_path)
    return proc, log_dir, log_path


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    """
    Keep plain `pytest` focused on pytest-native suites.

    Some legacy integration files under [`tests/integration/`](tests/integration) are
    standalone runner scripts: they execute work at import time, print their own
    summaries, and terminate with `sys.exit(...)`. Those files are intended to be
    run directly or through [`tests/run_all.py`](tests/run_all.py), not imported by
    pytest collection.
    """
    try:
        rel = (
            collection_path.resolve().relative_to(Path(__file__).resolve().parent.parent).as_posix()
        )
    except ValueError:
        return False

    if not rel.startswith(("tests/integration/", "tests/benchmark/")):
        return False
    if not rel.endswith(".py"):
        return False

    try:
        source = collection_path.read_text(encoding="utf-8")
    except OSError:
        return False

    if "sys.exit(" in source and 'if __name__ == "__main__":' not in source:
        return True

    # Some integration/benchmark files are standalone runners invoked directly
    # from the repo runbooks. Importing them during pytest collection loads heavy
    # optional runtime dependencies and can destabilize unrelated suites.
    has_pytest_style_tests = (
        "def test_" in source or "async def test_" in source or "class Test" in source
    )
    if not has_pytest_style_tests and 'if __name__ == "__main__":' in source:
        return True

    return False


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def legacy_live_api_server(request: pytest.FixtureRequest):
    global _LIVE_SERVER_LOG_DIR, _LIVE_SERVER_LOG_PATH, _LIVE_SERVER_PROC

    if os.environ.get("DE_SKIP_API", "0") == "1":
        yield
        return

    if not _legacy_live_test_requested(request.session):
        yield
        return

    _run_migrations()
    asyncio.run(_seed_legacy_live_api_key())
    os.environ["DE_API_KEY"] = DEFAULT_LOCAL_LIVE_API_KEY
    os.environ["ALGENTA_API_KEY"] = DEFAULT_LOCAL_LIVE_API_KEY

    started_here = False
    if not _port_open("127.0.0.1", 8000):
        _LIVE_SERVER_PROC, _LIVE_SERVER_LOG_DIR, _LIVE_SERVER_LOG_PATH = _start_live_server()
        started_here = True
    else:
        _wait_for_live_server("http://127.0.0.1:8000")

    yield

    if started_here and _LIVE_SERVER_PROC is not None:
        _LIVE_SERVER_PROC.terminate()
        try:
            _LIVE_SERVER_PROC.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _LIVE_SERVER_PROC.kill()
            _LIVE_SERVER_PROC.wait(timeout=5)
        _LIVE_SERVER_PROC = None
        _LIVE_SERVER_LOG_PATH = None


@pytest.fixture(scope="session")
def api_available() -> bool:
    try:
        resp = httpx.get("http://localhost:8000/v1/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def ensure_test_database_schema() -> None:
    _run_migrations()


@pytest.fixture
async def app():
    """FastAPI app instance for testing."""
    from apps.api_server.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
async def client(app):
    """
    Async HTTP client for testing FastAPI routes.
    Does NOT require a running server — uses ASGI transport.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
