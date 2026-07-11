"""Resolve the bundled Algenta native worker executable.

Public contract: users install ``algenta`` and the runtime is included for their
platform. They do not install a language toolchain, run a build command, or manage
any runtime artifact manually. Internally, release wheels carry the worker in the
``algenta_runtime_native`` package so package ownership stays explicit.
"""

from __future__ import annotations

import os
import platform
import stat
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from apps.runtime.native_manifest import NativeVerificationError, verify_bundled_artifact

WORKER_BASENAME = "algenta-runtime-worker.exe" if os.name == "nt" else "algenta-runtime-worker"
MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"


class NativeWorkerUnavailable(RuntimeError):  # noqa: N818
    """No verified bundled Algenta runtime worker is available."""


@dataclass(frozen=True)
class NativeWorkerResolution:
    source: str
    path: Path
    verified: bool
    public_error: str | None = None

    @property
    def executable(self) -> bool:
        return self.path.exists() and os.access(self.path, os.X_OK)


def _platform_tag() -> str:
    machine = platform.machine().lower()
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}.get(
        machine, machine
    )
    if sys.platform == "darwin":
        os_name = "macos"
    elif sys.platform.startswith("linux"):
        os_name = "linux"
    elif sys.platform.startswith("win"):
        os_name = "windows"
    else:
        os_name = sys.platform
    return f"{os_name}-{arch}"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runtime_package_dir() -> Path | None:
    try:
        return Path(str(resources.files("algenta_runtime_native")))
    except (ModuleNotFoundError, ImportError, TypeError, FileNotFoundError, NotADirectoryError):
        return None


def _candidate_paths() -> tuple[tuple[str, Path, bool], ...]:
    candidates: list[tuple[str, Path, bool]] = []
    override = os.environ.get("ALGENTA_NATIVE_WORKER") or os.environ.get("ALGENTA_RUNTIME_WORKER")
    if override:
        candidates.append(("env override", Path(override), False))

    legacy_override = os.environ.get("ALGENTA_MOJO_BINARY")
    if legacy_override and legacy_override != override:
        candidates.append(("env override", Path(legacy_override), False))

    runtime_dir = _runtime_package_dir()
    if runtime_dir is not None:
        candidates.append(("bundled runtime", runtime_dir / WORKER_BASENAME, True))

    candidates.append(("repo-dev runtime", _repo_root() / "mojo_build" / "simulate", False))
    return tuple(candidates)


def _verify_bundled_worker(path: Path) -> None:
    artifact_dir = path.parent
    manifest = verify_bundled_artifact(
        str(path),
        str(artifact_dir / MANIFEST_NAME),
        str(artifact_dir / MANIFEST_SIG_NAME),
        expected_name=WORKER_BASENAME,
    )
    if manifest.get("platform") != _platform_tag():
        raise NativeVerificationError(
            f"runtime built for {manifest.get('platform')!r}, this machine is {_platform_tag()!r}"
        )


def _ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    if not os.access(path, os.X_OK):
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def resolve_native_worker(*, require_verified: bool = False) -> NativeWorkerResolution | None:
    """Return the first available runtime worker.

    ``require_verified`` is for public installed-package paths. Repo-dev and env
    overrides are intentionally allowed for local development, but release gates
    verify the bundled runtime manifest before executing the worker.
    """
    last_public_error: str | None = None
    for source, path, must_verify in _candidate_paths():
        try:
            if not path.exists():
                continue
            if must_verify:
                try:
                    _verify_bundled_worker(path)
                except NativeVerificationError:
                    last_public_error = (
                        "The bundled Algenta runtime failed integrity verification. "
                        "Upgrade Algenta or install a build that supports this platform."
                    )
                    if require_verified:
                        return NativeWorkerResolution(source, path, False, last_public_error)
                    continue
            elif require_verified:
                continue
            _ensure_executable(path)
            if not os.access(path, os.X_OK):
                last_public_error = (
                    "The bundled Algenta runtime is present but is not executable. "
                    "Upgrade Algenta or install a build that supports this platform."
                )
                continue
            return NativeWorkerResolution(source, path, must_verify, None)
        except OSError:
            continue
    if last_public_error:
        return NativeWorkerResolution(
            "bundled runtime", Path(WORKER_BASENAME), False, last_public_error
        )
    return None


def require_native_worker(*, require_verified: bool = False) -> NativeWorkerResolution:
    resolved = resolve_native_worker(require_verified=require_verified)
    if resolved is None:
        raise NativeWorkerUnavailable(
            "The bundled Algenta runtime is unavailable for this platform. "
            "Upgrade Algenta or install a build that supports this platform."
        )
    if resolved.public_error:
        raise NativeWorkerUnavailable(resolved.public_error)
    return resolved
