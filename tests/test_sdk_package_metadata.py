"""Release-integrity guard for the public client SDKs (D2: Apache-2.0, aligned versions).

Pure-stdlib (tomllib + json) — no app deps. Enforces, before any publish, that the three
distributable packages share ONE license (Apache-2.0, per the D2 decision — the engine stays
proprietary) and ONE version, and each ships a LICENSE file. The release workflow runs the same
checks; this also gates them in CI so a drift can't reach a tag.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGES = _REPO_ROOT / "packages"

# The public client SDKs + CLI + MCP server. The engine + server are NOT here and keep the ACL.
_EXPECTED_LICENSE = "Apache-2.0"
_PYPROJECT_PKGS = ("python-sdk", "algenta-core", "mcp")
_TS_PKG = "ts-sdk"


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


def test_ts_package_includes_license_in_published_files() -> None:
    assert "LICENSE" in _ts_meta().get("files", [])


# Runtime __version__ must match the packaged version, or `import algenta; algenta.__version__`
# disagrees with what PyPI served — and the bump that introduced this guard is exactly that drift.
_INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_RUNTIME_VERSION_INITS = {
    "python-sdk": "decision_engine/__init__.py",
    "algenta-core": "algenta/__init__.py",
}


@pytest.mark.parametrize("pkg, init_rel", _RUNTIME_VERSION_INITS.items())
def test_runtime_version_matches_packaged_version(pkg: str, init_rel: str) -> None:
    init_text = (_PACKAGES / pkg / init_rel).read_text("utf-8")
    match = _INIT_VERSION_RE.search(init_text)
    assert match, f"{pkg}: no __version__ in {init_rel}"
    assert match.group(1) == _py_meta(pkg)["version"], pkg
