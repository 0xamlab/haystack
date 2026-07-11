"""Resolve and execute the bundled Algenta native worker.

This is an implementation detail behind ``pip install algenta``. Users should
never install or configure a worker package manually; the runtime is an automatic
platform dependency of Algenta.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from algenta import paths
from algenta.native import verify


def _artifact_release_public_key(artifact_dir: Path):
    key_path = artifact_dir / "algenta_release_pub.pem"
    if not key_path.exists():
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = serialization.load_pem_public_key(key_path.read_bytes())
    except Exception as exc:  # noqa: BLE001
        raise verify.VerificationError(f"invalid runtime public key: {exc}") from exc
    if not isinstance(key, rsa.RSAPublicKey):
        raise verify.VerificationError("runtime public key must be RSA")
    return key


WORKER_BASENAME = "algenta-runtime-worker.exe" if os.name == "nt" else "algenta-runtime-worker"
MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"


class NativeWorkerUnavailable(RuntimeError):  # noqa: N818
    """No bundled Algenta runtime worker is available."""


@dataclass(frozen=True)
class NativeWorkerResolution:
    source: str
    path: Path
    verified: bool
    public_error: str | None = None

    @property
    def executable(self) -> bool:
        return self.path.exists() and os.access(self.path, os.X_OK)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


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

    repo_worker = _repo_root() / "mojo_build" / "simulate"
    candidates.append(("repo-dev runtime", repo_worker, False))
    return tuple(candidates)


def _verify_bundled_worker(path: Path) -> None:
    artifact_dir = path.parent
    manifest_path = artifact_dir / MANIFEST_NAME
    sig_path = artifact_dir / MANIFEST_SIG_NAME
    if not (manifest_path.exists() and sig_path.exists()):
        raise verify.VerificationError("signed runtime manifest missing")
    pubkey = _artifact_release_public_key(artifact_dir)
    manifest = verify.verify_manifest(
        manifest_path.read_bytes(), sig_path.read_bytes(), pubkey=pubkey
    )
    platform = manifest.get("platform")
    if platform != paths.platform_tag():
        raise verify.VerificationError(
            f"runtime built for {platform!r}, this machine is {paths.platform_tag()!r}"
        )
    seen_worker = False
    for entry in manifest.get("artifacts", []):
        name = entry.get("name")
        expected_sha = entry.get("sha256")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise verify.VerificationError(f"manifest artifact name is unsafe: {name!r}")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise verify.VerificationError(f"artifact {name!r} has a malformed sha256")
        artifact = path.parent / name
        if not artifact.exists():
            raise verify.VerificationError(f"signed runtime artifact is missing: {name}")
        verify.verify_artifact(str(artifact), expected_sha)
        seen_worker = seen_worker or name == path.name
    if not seen_worker:
        raise verify.VerificationError("runtime worker not listed in the signed manifest")


def _ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    if not os.access(path, os.X_OK):
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def resolve_worker(*, require_verified: bool = False) -> NativeWorkerResolution | None:
    last_public_error: str | None = None
    for source, path, must_verify in _candidate_paths():
        try:
            if not path.exists():
                continue
            if must_verify:
                try:
                    _verify_bundled_worker(path)
                except verify.VerificationError:
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


def require_worker(*, require_verified: bool = False) -> NativeWorkerResolution:
    resolved = resolve_worker(require_verified=require_verified)
    if resolved is None:
        raise NativeWorkerUnavailable(
            "The bundled Algenta runtime is unavailable for this platform. "
            "Upgrade Algenta or install a build that supports this platform."
        )
    if resolved.public_error:
        raise NativeWorkerUnavailable(resolved.public_error)
    return resolved


def execute(
    request: dict[str, Any],
    *,
    timeout: float = 60.0,
    require_verified: bool = False,
) -> dict[str, Any]:
    resolution = require_worker(require_verified=require_verified)
    try:
        proc = subprocess.run(  # noqa: S603
            [str(resolution.path)],
            input=json.dumps(request).encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeWorkerUnavailable("The bundled Algenta runtime could not execute.") from exc
    if proc.returncode != 0:
        raise NativeWorkerUnavailable("The bundled Algenta runtime exited unsuccessfully.")
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeWorkerUnavailable(
            "The bundled Algenta runtime returned invalid output."
        ) from exc
    if not isinstance(payload, dict):
        raise NativeWorkerUnavailable("The bundled Algenta runtime returned a non-object response.")
    return payload


def info(*, require_verified: bool = False) -> dict[str, Any]:
    resolution = resolve_worker(require_verified=require_verified)
    if resolution is None:
        return {"source": None, "path": None, "verified": False, "error": None}
    return {
        "source": resolution.source,
        "path": str(resolution.path),
        "verified": resolution.verified,
        "error": resolution.public_error,
    }
