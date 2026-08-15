"""Release-integrity guard for the public client SDKs (D2: Apache-2.0, aligned versions).

Pure-stdlib (tomllib + json) — no app deps. Enforces, before any publish, that the three
distributable packages share ONE license (Apache-2.0, per the D2 decision — the engine stays
proprietary) and ONE version, and each ships a LICENSE file. The release workflow runs the same
checks; this also gates them in CI so a drift can't reach a tag.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGES = _REPO_ROOT / "packages"

# The public client SDKs + CLI + MCP server. The engine + server are NOT here and keep the ACL.
_EXPECTED_LICENSE = "Apache-2.0"
# `algenta` owns the `algenta` import/command. The proprietary native runtime lives in
# `algenta-runtime-native` (a separate distribution) and is intentionally not in this
# Apache/version guard.
_PYPROJECT_PKGS = ("python-sdk", "algenta", "mcp")
_TS_PKG = "ts-sdk"
_SDK_PYTHON_CLASSIFIERS = {
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
}
_RUNTIME_PYTHON_CLASSIFIERS = {"Programming Language :: Python :: 3.14"}
_PYTHON_CONTRACTS = {
    "python-sdk": (">=3.10", _SDK_PYTHON_CLASSIFIERS),
    "algenta": (">=3.14,<3.15", _RUNTIME_PYTHON_CLASSIFIERS),
    "mcp": (">=3.10", _SDK_PYTHON_CLASSIFIERS),
}
_TRUST_ANCHOR_DER_SHA256 = {
    "algenta_release_pub.pem": "121aaf4a3f298d4ea09a337860a4ef2031c0ec4ef0af645c5bb06a56bc169468",
    "algenta_license_pub.pem": "73a5ccb64e12aef2581fed60010f1648d60da0fd833897802b2ad8b7eea3de6b",
}


def _py_meta(pkg: str) -> dict:
    return tomllib.loads((_PACKAGES / pkg / "pyproject.toml").read_text("utf-8"))["project"]


def _ts_meta() -> dict:
    return json.loads((_PACKAGES / _TS_PKG / "package.json").read_text("utf-8"))


def test_all_public_sdks_are_apache_2_0() -> None:
    for pkg in _PYPROJECT_PKGS:
        assert _py_meta(pkg)["license"] == _EXPECTED_LICENSE, pkg
    assert _ts_meta()["license"] == _EXPECTED_LICENSE


def test_engine_root_license_stays_proprietary() -> None:
    # Guard against accidentally relicensing the engine: the root LICENSE is the proprietary ACL.
    root_license = (_REPO_ROOT / "LICENSE").read_text("utf-8")
    assert "Algenta Community License" in root_license
    assert "Apache License" not in root_license.split("\n", 1)[0]


def test_public_sdk_versions_are_aligned() -> None:
    versions = {pkg: _py_meta(pkg)["version"] for pkg in _PYPROJECT_PKGS}
    versions[_TS_PKG] = _ts_meta()["version"]
    assert len(set(versions.values())) == 1, f"SDK versions diverge: {versions}"


def test_public_package_descriptions_use_algenta_branding_and_agent_discovery() -> None:
    descriptions = {
        pkg: str(_py_meta(pkg)["description"]) for pkg in _PYPROJECT_PKGS
    }
    descriptions[_TS_PKG] = str(_ts_meta()["description"])

    for pkg, description in descriptions.items():
        assert "decision engine" not in description.casefold(), pkg

    mcp_metadata = _py_meta("mcp")
    assert "Cursor" in mcp_metadata["description"]
    assert "Codex" in mcp_metadata["description"]
    assert {"cursor", "codex", "model-context-protocol"} <= set(
        mcp_metadata["keywords"]
    )


def test_mcp_registry_manifest_matches_packaged_version() -> None:
    manifest = json.loads((_REPO_ROOT / "server.json").read_text("utf-8"))
    package_version = _py_meta("mcp")["version"]

    assert manifest["$schema"] == (
        "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    )
    assert 1 <= len(manifest["description"]) <= 100
    assert manifest["version"] == package_version
    packages = manifest.get("packages")
    assert isinstance(packages, list) and len(packages) == 1
    assert packages[0]["registryType"] == "pypi"
    assert packages[0]["identifier"] == "algenta-mcp"
    assert packages[0]["version"] == package_version

    remotes = manifest.get("remotes")
    assert isinstance(remotes, list) and len(remotes) == 1
    assert remotes[0]["type"] == "streamable-http"
    assert remotes[0]["url"] == "https://api.algenta.ai/mcp"
    assert remotes[0]["headers"] == [
        {
            "name": "Authorization",
            "description": (
                "Bearer <ALGENTA_API_KEY>. Create a key in the Algenta dashboard "
                "or authenticate with `algenta login`."
            ),
            "placeholder": "Bearer <ALGENTA_API_KEY>",
            "isRequired": True,
            "isSecret": True,
        }
    ]


def test_algenta_package_embeds_pinned_public_trust_anchors() -> None:
    key_dir = _PACKAGES / "algenta" / "algenta" / "_keys"
    for filename, expected_sha256 in _TRUST_ANCHOR_DER_SHA256.items():
        pem = (key_dir / filename).read_text("ascii")
        assert "PRIVATE KEY" not in pem
        assert pem.startswith("-----BEGIN PUBLIC KEY-----\n")
        assert pem.endswith("-----END PUBLIC KEY-----\n")
        payload = "".join(line for line in pem.splitlines() if not line.startswith("-----"))
        der = base64.b64decode(payload, validate=True)
        assert hashlib.sha256(der).hexdigest() == expected_sha256


@pytest.mark.parametrize("pkg", (*_PYPROJECT_PKGS, _TS_PKG))
def test_each_public_sdk_ships_an_apache_license_file(pkg: str) -> None:
    license_path = _PACKAGES / pkg / "LICENSE"
    assert license_path.is_file(), f"{pkg} missing LICENSE"
    text = license_path.read_text("utf-8")
    assert "Apache License" in text and "Version 2.0" in text, pkg


def test_pyproject_declares_license_files() -> None:
    # PEP 639: the LICENSE must be declared so it lands in the sdist + wheel.
    for pkg in _PYPROJECT_PKGS:
        assert "LICENSE" in _py_meta(pkg).get("license-files", []), pkg


@pytest.mark.parametrize("pkg", _PYPROJECT_PKGS)
def test_public_python_packages_declare_current_supported_python_versions(pkg: str) -> None:
    expected_requires_python, expected_classifiers = _PYTHON_CONTRACTS[pkg]
    metadata = _py_meta(pkg)
    assert metadata["requires-python"] == expected_requires_python, pkg

    classifiers = set(metadata.get("classifiers", []))
    missing = sorted(expected_classifiers - classifiers)
    assert not missing, f"{pkg} missing Python support classifiers: {missing}"
    if pkg == "algenta":
        unsupported = sorted(classifiers & (_SDK_PYTHON_CLASSIFIERS - expected_classifiers))
        assert not unsupported, f"{pkg} advertises unsupported Python classifiers: {unsupported}"


def test_ci_verifies_python_314_sdk_artifacts_and_repo_tests() -> None:
    ci = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    release = (_REPO_ROOT / ".github" / "workflows" / "release-sdks.yml").read_text("utf-8")
    docs = (_REPO_ROOT / ".github" / "workflows" / "docs-audit.yml").read_text("utf-8")

    assert 'PYTHON_VERSION: "3.14"' in ci
    assert 'python-version: ["3.14"]' in ci
    assert ci.count('python-version: ["3.14"]') == 2
    assert 'PYTHON_VERSION: "3.14"' in release
    # No actions/setup-python here (its macOS .pkg install needs passwordless sudo, not
    # configured on the self-hosted runner) -- python3.14 is a Homebrew binary invoked
    # directly instead of a `with: python-version: "3.14"` key.
    assert "python3.14" in docs

    pixi = (_REPO_ROOT / "mojo_env" / "pixi.toml").read_text(encoding="utf-8")
    assert 'python = ">=3.14,<3.15"' in pixi


def test_sdk_release_workflow_is_idempotent() -> None:
    release = (_REPO_ROOT / ".github" / "workflows" / "release-sdks.yml").read_text(
        "utf-8"
    )
    runtime_release = (_REPO_ROOT / ".github" / "workflows" / "build-runtime.yml").read_text(
        "utf-8"
    )

    # The SDK publish moved from the Linux-only pypa container action (`skip-existing: true`
    # inputs, four: testpypi x2 + pypi x2) to native twine calls on the macOS fleet
    # (`--skip-existing`, one per publish job); the idempotence markers moved with it.
    assert release.count("--skip-existing") == 3
    assert 'npm view "algenta-sdk@$VERSION" version' in release
    assert 'if [ "$PUBLISHED_VERSION" = "$VERSION" ]' in release
    # The runtime publish moved from the Linux-only pypa container action (`skip-existing: true`
    # input) to a native twine call on the macOS fleet; the idempotence marker is the twine flag.
    assert runtime_release.count("--skip-existing") == 1


def test_python_release_builds_use_safe_import_path() -> None:
    workflows = {
        name: (_REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8")
        for name in ("release-sdks.yml", "build-runtime.yml")
    }

    for name, workflow in workflows.items():
        assert "python -m build" not in workflow, (
            f"{name} must use `python -P -m build`; the repository's build/ directory "
            "otherwise shadows the PyPA build package"
        )
        assert "python -P -m build" in workflow, name


def test_sdk_release_workflow_only_targets_existing_pypi_projects() -> None:
    release = (_REPO_ROOT / ".github" / "workflows" / "release-sdks.yml").read_text(
        "utf-8"
    )
    production = release.split("\n  publish-pypi:\n", 1)[1].split("\n  publish-npm:\n", 1)[0]
    assert "algenta-core" not in release
    assert not (_PACKAGES / "algenta-core" / "pyproject.toml").exists()
    assert "id-token: write" not in production
    # Native-twine migration: the pypa action's `password:` inputs became TWINE_PASSWORD env
    # blocks (one per package step); the production publish still consumes PYPI_TOKEN exactly
    # twice -- once per existing project.
    assert production.count("TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}") == 2


def test_ts_package_publishes_runtime_and_metadata_files() -> None:
    # The npm "files" allowlist is the ONLY thing that lands in the published tarball (no
    # .npmignore). dist/ holds the compiled JS+types; proto/ is loaded at runtime by the gRPC
    # client; README+LICENSE are the published docs/legal. Missing any => a broken or bare package.
    files = _ts_meta().get("files", [])
    for required in ("dist", "proto", "README.md", "LICENSE"):
        assert required in files, f"ts-sdk 'files' allowlist missing {required!r}: {files}"


def test_ts_package_builds_dist_before_publish() -> None:
    # dist/ is gitignored and NOT committed, so the publish MUST build it. A `prepack` hook makes
    # `npm pack`/`npm publish`/`pnpm publish` always emit a fresh dist/ — without it the tarball
    # ships empty (the failure the artifact-install gate proves against). Lock the hook in place.
    scripts = _ts_meta().get("scripts", {})
    build_hooks = {k: scripts[k] for k in ("prepack", "prepublishOnly", "prepare") if k in scripts}
    assert build_hooks, (
        "ts-sdk must build dist/ before publish via a prepack/prepublishOnly/prepare hook; "
        f"found scripts: {sorted(scripts)}"
    )
    assert any("tsc" in v or "build" in v for v in build_hooks.values()), (
        f"ts-sdk publish hook does not run the build: {build_hooks}"
    )


# Runtime __version__ must match the packaged version, or `import algenta; algenta.__version__`
# disagrees with what PyPI served — and the bump that introduced this guard is exactly that drift.
_INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_RUNTIME_VERSION_INITS = {
    "python-sdk": "decision_engine/__init__.py",
    # `algenta` owns the `algenta` import package.
    "algenta": "algenta/__init__.py",
}


@pytest.mark.parametrize("pkg, init_rel", _RUNTIME_VERSION_INITS.items())
def test_runtime_version_matches_packaged_version(pkg: str, init_rel: str) -> None:
    init_text = (_PACKAGES / pkg / init_rel).read_text("utf-8")
    match = _INIT_VERSION_RE.search(init_text)
    assert match, f"{pkg}: no __version__ in {init_rel}"
    assert match.group(1) == _py_meta(pkg)["version"], pkg
