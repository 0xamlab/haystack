"""CI guard: self-host deployments must pin container images — never ``:latest`` (GTM Wave 1, item 5).

A self-host operator who pulls a floating tag (``:latest``, a ``:-latest`` default, or an UNTAGGED
image — Docker resolves a bare ``alpine`` to ``alpine:latest``) gets non-reproducible, silently
drifting deployments. This scans the user-facing self-host surface and fails on any floating tag:

  * ``install.sh`` (the curl|bash installer) and ``.env.example`` (docs say ``cp .env.example .env``)
  * ``infra/docker/docker-compose.selfhosted.yml`` + ``docker-compose.replicas.yml``
  * the self-host docs (``apps/docs/docs/self-hosting.md`` + ``operations*/``)
  * the operator-runnable self-host scripts (``scripts/self_host_*.sh``)

Also gated (added Wave 2 cleanup): the CI workflow's service images (``.github/workflows/ci.yml`` —
Postgres / Dragonfly / MinIO) must be pinned so CI is reproducible and can't silently drift on a
``:latest`` push; and the hosted-provisioning engine-image DEFAULT (``config.py``
``algenta_engine_image``) must not float (it would silently drift the deployed engine once
provisioning is wired).

Out of scope by design: ``infra/docker/docker-compose.yml`` is the LOCAL-DEV compose — it builds the
application images locally (no registry pull) and is a developer convenience, not a shipped self-host
artifact; its remaining infra ``:latest`` pulls (minio/mc) are intentionally not gated here.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

_ROOT = Path(__file__).resolve().parents[1]
_INSTALL = _ROOT / "install.sh"
_ENV_EXAMPLE = _ROOT / ".env.example"
_DOCKER_DIR = _ROOT / "infra" / "docker"
_SELFHOSTED = _DOCKER_DIR / "docker-compose.selfhosted.yml"
_REPLICAS = _DOCKER_DIR / "docker-compose.replicas.yml"
_DOCS_DIR = _ROOT / "apps" / "docs" / "docs"
_SCRIPTS_DIR = _ROOT / "scripts"
_CI_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_CONFIG = _ROOT / "apps" / "api_server" / "config.py"
_API_DOCKERFILE = _DOCKER_DIR / "Dockerfile.api.prod"
_API_REQUIREMENTS = _ROOT / "requirements-dev.txt"
_MCP_REQUIREMENTS = _ROOT / "requirements-mcp.txt"

# An image tag of `latest`, whether hardcoded (`foo:latest`) or a silent compose default
# (`${VAR:-latest}`), case-insensitive. The lookbehind requires an image-name char before the colon
# so prose ("the latest release") or a "...-latest.tgz" filename does not trip the guard.
_LATEST_TAG = re.compile(r"(?<=[\w}./-]):-?latest\b", re.IGNORECASE)

# A well-known base image referenced WITHOUT a tag (Docker resolves it to :latest). Tight lookarounds
# avoid matching pinned `*-alpine` tags (e.g. postgres:16-alpine) and `alpine/<repo>` namespaces.
_BARE_BASE = re.compile(r"(?<![:\w./-])(?:alpine|ubuntu|debian|busybox|golang)(?![:@\w./-])")


def _self_host_docs() -> list[Path]:
    return sorted([*_DOCS_DIR.glob("self-hosting.md"), *_DOCS_DIR.glob("operations*/*.md")])


def _scanned_files() -> list[Path]:
    return [
        _INSTALL,
        _ENV_EXAMPLE,
        _SELFHOSTED,
        _REPLICAS,
        *_self_host_docs(),
        *sorted(_SCRIPTS_DIR.glob("self_host_*.sh")),
    ]


def _violations(text: str, *, exempt_lines: set[int] | None = None) -> list[str]:
    """'lineno: reason -> snippet' for every floating tag, skipping comment lines."""
    out: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        if exempt_lines and lineno in exempt_lines:
            continue
        if _LATEST_TAG.search(line):
            out.append(f"{lineno}: floating :latest tag -> {line.strip()}")
        if _BARE_BASE.search(line):
            out.append(f"{lineno}: untagged base image (implicit :latest) -> {line.strip()}")
    return out


def test_no_floating_image_tags_in_self_host_surface() -> None:
    failures: dict[str, list[str]] = {}
    for path in _scanned_files():
        assert path.exists(), f"guard target missing: {path}"
        exempt: set[int] = set()
        if path == _INSTALL:
            # install.sh's ONLY floating reference is the transient PULL default
            # (${ALGENTA_IMAGE_TAG:-${ALGENTA_VERSION:-latest}}): images are pulled by that
            # tag and immediately PINNED BY DIGEST in the on-disk compose file
            # (pin_images_by_digest), so no floating reference ever reaches disk. The digest
            # pinning machinery itself is asserted in test_install_script_pins_the_image_tag.
            exempt = {
                lineno
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
                if 'IMAGE_TAG="${ALGENTA_IMAGE_TAG:-${ALGENTA_VERSION:-latest}}"' in line
            }
            assert len(exempt) == 1, (
                "install.sh must carry exactly one transient :latest pull default"
            )
        hits = _violations(path.read_text(encoding="utf-8"), exempt_lines=exempt)
        if hits:
            failures[str(path.relative_to(_ROOT))] = hits
    assert not failures, (
        "Self-host artifacts must pin images (never :latest / :-latest / untagged). Offending refs:\n"
        + "\n".join(f"  {f}\n    " + "\n    ".join(lines) for f, lines in failures.items())
    )


def test_compose_images_are_pinned() -> None:
    # Every compose `image:` value is a digest, an explicit tag, or a ${VAR}-provided tag — never a
    # bare `image: name` (which Docker resolves to :latest).
    for path in (_SELFHOSTED, _REPLICAS):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("image:"):
                continue
            value = stripped[len("image:"):].strip()
            if "${" in value or "@sha256:" in value:
                continue
            last_segment = value.rsplit("/", 1)[-1]
            assert ":" in last_segment, f"{path.name}:{lineno} image is not pinned to a tag: {value}"


def test_self_host_app_images_are_pin_required() -> None:
    # The Algenta API + bundled engine images must be fail-closed on a pinned tag/digest
    # (`${ALGENTA_IMAGE_TAG:?...}`), not a silent :-latest default. install.sh, the proof scripts,
    # the docs, and .env.example all provide ALGENTA_IMAGE_TAG, so this never blocks a real deploy.
    compose = _SELFHOSTED.read_text(encoding="utf-8")
    assert "/api:${ALGENTA_IMAGE_TAG:?" in compose, "api image must require a pinned ALGENTA_IMAGE_TAG"
    assert "/engine:${ALGENTA_IMAGE_TAG:?" in compose, "engine image must require a pinned ALGENTA_IMAGE_TAG"
    assert "${ALGENTA_IMAGE_TAG:-latest}" not in compose, "api/engine must not silently default to :latest"


def test_install_script_pins_the_image_tag() -> None:
    install = _INSTALL.read_text(encoding="utf-8")
    # The installer pulls by tag and then PINS BY DIGEST in the on-disk compose file — a
    # stronger guarantee than a git-sha tag: digests are content-addressed, and no GitHub
    # round-trip is needed (the repo is private). The machinery must resolve each image's
    # RepoDigests and rewrite the compose reference to @sha256.
    assert "pin_images_by_digest" in install, "install.sh must digest-pin after the pull"
    assert "RepoDigests" in install, "install.sh must resolve each image's digest"
    assert "@sha256" in install or "digest_ref" in install, (
        "install.sh must rewrite compose image refs to digests"
    )
    assert "ALGENTA_IMAGE_TAG=" in install, "install.sh must write the tag into .env"
    assert not _violations(
        install,
        exempt_lines={
            lineno
            for lineno, line in enumerate(install.splitlines(), start=1)
            if 'IMAGE_TAG="${ALGENTA_IMAGE_TAG:-${ALGENTA_VERSION:-latest}}"' in line
        },
    ), "install.sh must not reference a floating tag"


def test_ci_service_images_are_pinned() -> None:
    # CI service containers + `docker run` images must be pinned (reproducible CI; no surprise
    # :latest drift). Scans non-comment lines for a floating :latest tag — `runs-on: ubuntu-latest`
    # and `uses: actions/x@vN` carry no `:latest` so they don't trip _LATEST_TAG.
    assert _CI_WORKFLOW.exists(), f"guard target missing: {_CI_WORKFLOW}"
    hits = [
        f"{lineno}: {line.strip()}"
        for lineno, line in enumerate(_CI_WORKFLOW.read_text(encoding="utf-8").splitlines(), start=1)
        if not line.lstrip().startswith("#") and _LATEST_TAG.search(line)
    ]
    assert not hits, "CI service images must be pinned (never :latest):\n  " + "\n  ".join(hits)


def test_provisioning_engine_image_default_is_pinned() -> None:
    # The hosted-provisioning engine-image default must not float: empty (must-configure) or a pinned
    # tag/@sha256 — never :latest (which would silently drift the deployed engine once provisioning
    # is wired). config.py is not a shipped self-host artifact, so it lives in its own check.
    text = _CONFIG.read_text(encoding="utf-8")
    m = re.search(r'algenta_engine_image\s*:\s*str\s*=\s*Field\(\s*default="([^"]*)"', text)
    assert m, "could not locate the algenta_engine_image default in config.py"
    default = m.group(1)
    assert not _LATEST_TAG.search(default) and not _BARE_BASE.search(default), (
        f"algenta_engine_image default must not be a floating tag: {default!r}"
    )


def test_self_host_uses_bundled_engine_image() -> None:
    compose = _SELFHOSTED.read_text(encoding="utf-8")
    assert "ghcr.io/thyn-ai/algenta}/engine:${ALGENTA_IMAGE_TAG:?" in compose
    assert "ALGENTA_SIDECAR_IMAGE" not in compose
    assert "codna/sidecar" not in compose


def test_api_image_bundles_mcp_transport_dependencies() -> None:
    dockerfile = _API_DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY requirements-dev.txt requirements-mcp.txt ./" in dockerfile
    assert "-r requirements-mcp.txt" in dockerfile


def _direct_requirements(path: Path) -> dict[str, Requirement]:
    requirements: dict[str, Requirement] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        requirement = Requirement(line)
        requirements[canonicalize_name(requirement.name)] = requirement
    return requirements


def test_api_and_mcp_requirement_pins_are_compatible() -> None:
    api = _direct_requirements(_API_REQUIREMENTS)
    mcp = _direct_requirements(_MCP_REQUIREMENTS)

    failures: list[str] = []
    for name in sorted(api.keys() & mcp.keys()):
        exact_pins = [spec.version for spec in api[name].specifier if spec.operator == "=="]
        if len(exact_pins) != 1:
            continue
        pinned_version = Version(exact_pins[0])
        if pinned_version not in mcp[name].specifier:
            failures.append(f"{name}=={pinned_version} does not satisfy {mcp[name].specifier}")

    assert not failures, "API and MCP requirements cannot be installed together:\n  " + "\n  ".join(failures)
