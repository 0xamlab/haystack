"""Production deploy dependency guards."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON314_SAFE_DATABASE_PINS = {
    "sqlalchemy": "2.0.51",
    "asyncpg": "0.31.0",
    "alembic": "1.18.5",
    "greenlet": "3.5.3",
}
VERIFIED_MOJO_IMAGE = "ghcr.io/thyn-ai/algenta/mojo:git-53359d3"
MOJO_EMBEDDED_PREFIX_SYMLINK = "ln -s /app/mojo_env /build/mojo_env"
PRODUCTION_DOCKERFILES = (
    "infra/docker/Dockerfile.api.prod",
    "infra/docker/Dockerfile.worker.prod",
    "infra/docker/Dockerfile.engine.prod",
)

REQUIREMENT_PIN_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==(?P<version>[^#;\s]+)"
)
MOJO_IMAGE_RE = re.compile(r"^ARG MOJO_IMAGE=(?P<image>\S+)$", re.MULTILINE)


def _exact_pins(requirements_path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in requirements_path.read_text().splitlines():
        match = REQUIREMENT_PIN_RE.match(line)
        if match is None:
            continue
        pins[match.group("name").lower().replace("_", "-")] = match.group("version")
    return pins


def test_fly_python314_database_stack_uses_verified_import_safe_pins() -> None:
    """Fly's release command imports Alembic under the production Python 3.14 image."""

    for relative_path in ("requirements-dev.txt", "apps/api-server/requirements.txt"):
        pins = _exact_pins(ROOT / relative_path)
        assert {
            name: pins.get(name) for name in PYTHON314_SAFE_DATABASE_PINS
        } == PYTHON314_SAFE_DATABASE_PINS


def test_production_dockerfiles_share_verified_mojo_image_pin() -> None:
    """API/worker/engine must copy the same server-mode verified Mojo binary image."""

    pins: dict[str, str] = {}
    for relative_path in PRODUCTION_DOCKERFILES:
        text = (ROOT / relative_path).read_text()
        match = MOJO_IMAGE_RE.search(text)
        assert match is not None, f"{relative_path} must pin ARG MOJO_IMAGE"
        pins[relative_path] = match.group("image")

    assert pins == {path: VERIFIED_MOJO_IMAGE for path in PRODUCTION_DOCKERFILES}
    assert not VERIFIED_MOJO_IMAGE.endswith(":latest")


def test_production_runtime_disables_subprocess_fallbacks() -> None:
    """The Fly production path must fail closed instead of spawning per-request fallbacks."""

    for relative_path in (*PRODUCTION_DOCKERFILES, "fly.api.toml", "fly.engine.toml"):
        text = (ROOT / relative_path).read_text()
        assert "RUNTIME_FALLBACK_MODE = \"deny\"" in text or "RUNTIME_FALLBACK_MODE=deny" in text
        assert (
            "MOJO_ALLOW_SUBPROCESS_FALLBACK = \"false\"" in text
            or "MOJO_ALLOW_SUBPROCESS_FALLBACK=false" in text
        )


def test_production_dockerfiles_preserve_mojo_embedded_python_prefix() -> None:
    """Mojo worker server mode must find its bundled Python stdlib without global PYTHONHOME."""

    for relative_path in PRODUCTION_DOCKERFILES:
        text = (ROOT / relative_path).read_text()
        assert MOJO_EMBEDDED_PREFIX_SYMLINK in text, relative_path
        assert "PYTHONHOME=/app/mojo_env" not in text, relative_path


def test_api_production_image_includes_embedded_mcp_router_sources() -> None:
    """The public API image must not lose /mcp routes by omitting the MCP source package."""

    text = (ROOT / "infra/docker/Dockerfile.api.prod").read_text()
    assert "COPY --from=builder /build/context/packages/mcp/ /app/packages/mcp/" in text


def test_api_image_smoke_verifies_embedded_mcp_router() -> None:
    """The deploy-time image smoke must fail before Fly if embedded MCP routes are missing."""

    text = (ROOT / "scripts/verify_api_image_mojo_server_mode.sh").read_text()
    assert "/app/packages/mcp/algenta_mcp/products.py" in text
    assert "create_fastapi_router" in text
    assert '"/mcp/tools"' in text


def test_deploy_workflows_smoke_api_image_mojo_server_mode_before_fly() -> None:
    """The API image must prove bundled Mojo server mode before Fly rolls machines."""

    script_path = "scripts/verify_api_image_mojo_server_mode.sh"
    assert (ROOT / script_path).is_file()
    ci_text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "api-image-mojo-smoke:" in ci_text
    assert "docker build --pull -f infra/docker/Dockerfile.api.prod" in ci_text
    assert f"bash {script_path} algenta-api-smoke:pr" in ci_text

    for relative_path in (".github/workflows/ci.yml", ".github/workflows/deploy.yml"):
        text = (ROOT / relative_path).read_text()
        pull_command = (
            'docker pull  "$SRC/api:$TAG"'
            if 'docker pull  "$SRC/api:$TAG"' in text
            else 'docker pull "$SRC/api:$TAG"'
        )
        pull_index = text.index(pull_command)
        smoke_index = text.index(f"bash {script_path} \"$SRC/api:$TAG\"")
        fly_index = text.index("flyctl deploy -c fly.api.toml")
        assert pull_index < smoke_index < fly_index, relative_path
