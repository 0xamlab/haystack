"""Resolve and execute the bundled Algenta native worker.

This is an implementation detail behind ``pip install algenta``. Users should
never install or configure a worker package manually; the runtime is an automatic
platform dependency of Algenta.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
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
SHARD_MAP_NAME = "runtime-shards.json"
MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"
_MAX_FRAME_BYTES = 64 * 1024 * 1024
_STARTUP_TIMEOUT_SECONDS = 15.0


class NativeWorkerUnavailable(RuntimeError):  # noqa: N818
    """No bundled Algenta runtime worker is available."""


def _worker_environment(resolution: NativeWorkerResolution) -> dict[str, str]:
    """Return an isolated launch environment for the bundled CPython 3.14 worker."""
    env = os.environ.copy()
    if resolution.source == "bundled runtime":
        env["PYTHONHOME"] = sys.base_prefix
        # The Mojo runtime resolves libpython itself and fails closed on machines with no
        # system-wide Python in a layout it recognizes (bare containers, minimal servers):
        # "found no suitable Python library to link to". The runtime package bundles its own
        # libpython beside the worker, so point Mojo at it explicitly and keep the bundled
        # runtime self-contained. A MOJO_PYTHON_LIBRARY already in the environment wins.
        if "MOJO_PYTHON_LIBRARY" not in env:
            bundled = _bundled_libpython(resolution.path.parent)
            if bundled is not None:
                env["MOJO_PYTHON_LIBRARY"] = str(bundled)
    return env


def _bundled_libpython(artifact_dir: Path) -> Path | None:
    for pattern in ("libpython3*.so*", "libpython3*.dylib"):
        for candidate in sorted(artifact_dir.glob(pattern)):
            if candidate.is_file():
                return candidate
    return None


@dataclass(frozen=True)
class NativeWorkerResolution:
    source: str
    path: Path
    verified: bool
    public_error: str | None = None

    @property
    def executable(self) -> bool:
        return self.path.exists() and os.access(self.path, os.X_OK)


@dataclass(frozen=True)
class _RuntimeShardMap:
    default_worker: str
    module_workers: dict[str, str]

    @property
    def workers(self) -> frozenset[str]:
        return frozenset(self.module_workers.values())


class _WorkerSession:
    def __init__(self, resolution: NativeWorkerResolution) -> None:
        self._resolution = resolution
        self._lock = threading.Lock()
        self._owner_pid = os.getpid()
        self._proc: subprocess.Popen[bytes] | None = None
        self._client: socket.socket | None = None
        self._temp_dir: Path | None = None
        self._log_handle: Any | None = None

    @property
    def worker_path(self) -> Path:
        return self._resolution.path

    @property
    def ready(self) -> bool:
        return (
            self._owner_pid == os.getpid()
            and self._proc is not None
            and self._proc.poll() is None
            and self._client is not None
        )

    def _reset_after_fork(self) -> None:
        if self._owner_pid == os.getpid():
            return
        self._client = None
        self._proc = None
        self._temp_dir = None
        self._log_handle = None
        self._owner_pid = os.getpid()

    def _start(self, timeout: float) -> None:
        self._reset_after_fork()
        if self.ready:
            return
        self._close_unlocked()
        if os.name == "nt":
            raise NativeWorkerUnavailable(
                "The bundled Algenta runtime does not support this platform release."
            )
        temp_dir = Path(tempfile.mkdtemp(prefix="algenta-runtime-", dir="/tmp"))
        socket_path = temp_dir / "worker.sock"
        log_handle = (temp_dir / "worker.log").open("wb")
        proc: subprocess.Popen[bytes] | None = None
        try:
            proc = subprocess.Popen(  # noqa: S603
                [str(self._resolution.path), "--server", str(socket_path)],
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                close_fds=True,
                env=_worker_environment(self._resolution),
            )
            deadline = time.monotonic() + min(max(timeout, 0.1), _STARTUP_TIMEOUT_SECONDS)
            client: socket.socket | None = None
            last_error: OSError | None = None
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise NativeWorkerUnavailable(
                        "The bundled Algenta runtime exited during startup."
                    )
                if socket_path.exists():
                    candidate = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    candidate.settimeout(max(0.1, deadline - time.monotonic()))
                    try:
                        candidate.connect(str(socket_path))
                        client = candidate
                        break
                    except OSError as exc:
                        last_error = exc
                        candidate.close()
                time.sleep(0.01)
            if client is None:
                raise NativeWorkerUnavailable(
                    "The bundled Algenta runtime did not become ready."
                ) from last_error
            ready = _recv_frame(client)
            if ready != {"status": "ready"}:
                client.close()
                raise NativeWorkerUnavailable(
                    "The bundled Algenta runtime returned an invalid startup response."
                )
        except Exception:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            log_handle.close()
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        self._proc = proc
        self._client = client
        self._temp_dir = temp_dir
        self._log_handle = log_handle

    def execute(self, request: dict[str, Any], timeout: float) -> dict[str, Any]:
        with self._lock:
            for attempt in range(2):
                try:
                    self._start(timeout)
                    if self._client is None:
                        raise NativeWorkerUnavailable(
                            "The bundled Algenta runtime connection is unavailable."
                        )
                    self._client.settimeout(timeout)
                    _send_frame(self._client, request)
                    return _recv_frame(self._client)
                except (OSError, TimeoutError, NativeWorkerUnavailable) as exc:
                    self._close_unlocked()
                    if attempt == 1:
                        raise NativeWorkerUnavailable(
                            "The bundled Algenta runtime could not execute."
                        ) from exc
            raise AssertionError("unreachable")

    def ensure_ready(self, timeout: float) -> None:
        with self._lock:
            self._start(timeout)

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except OSError:
                pass
        self._client = None
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
        self._proc = None
        if self._log_handle is not None:
            self._log_handle.close()
        self._log_handle = None
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None


def _recv_exact(client: socket.socket, size: int) -> bytes:
    payload = bytearray()
    while len(payload) < size:
        chunk = client.recv(size - len(payload))
        if not chunk:
            raise NativeWorkerUnavailable(
                "The bundled Algenta runtime closed its connection unexpectedly."
            )
        payload.extend(chunk)
    return bytes(payload)


def _recv_frame(client: socket.socket) -> dict[str, Any]:
    frame_size = struct.unpack(">I", _recv_exact(client, 4))[0]
    if frame_size <= 0 or frame_size > _MAX_FRAME_BYTES:
        raise NativeWorkerUnavailable(
            "The bundled Algenta runtime returned an invalid response size."
        )
    try:
        payload = json.loads(_recv_exact(client, frame_size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeWorkerUnavailable(
            "The bundled Algenta runtime returned invalid output."
        ) from exc
    if not isinstance(payload, dict):
        raise NativeWorkerUnavailable("The bundled Algenta runtime returned a non-object response.")
    return payload


def _send_frame(client: socket.socket, request: dict[str, Any]) -> None:
    payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if not payload or len(payload) > _MAX_FRAME_BYTES:
        raise NativeWorkerUnavailable("The bundled Algenta runtime request is too large.")
    client.sendall(struct.pack(">I", len(payload)) + payload)


_SESSION_LOCK = threading.Lock()
_SESSIONS: dict[Path, _WorkerSession] = {}
_CACHE_LOCK = threading.RLock()
_SHARD_MAP_CACHE: dict[Path, tuple[int, int, _RuntimeShardMap]] = {}
_VERIFIED_RUNTIME_DIRS: set[Path] = set()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _runtime_package_dir() -> Path | None:
    try:
        return Path(str(resources.files("algenta_runtime_native")))
    except (ModuleNotFoundError, ImportError, TypeError, FileNotFoundError, NotADirectoryError):
        return None


def _load_shard_map(artifact_dir: Path) -> _RuntimeShardMap:
    path = artifact_dir / SHARD_MAP_NAME
    try:
        file_stat = path.stat()
    except OSError as exc:
        raise verify.VerificationError("runtime shard map missing") from exc
    cache_key = (file_stat.st_mtime_ns, file_stat.st_size)
    with _CACHE_LOCK:
        cached = _SHARD_MAP_CACHE.get(path)
        if cached is not None and cached[:2] == cache_key:
            return cached[2]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise verify.VerificationError("runtime shard map is invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise verify.VerificationError("runtime shard map must use schema_version 1")
    default_worker = payload.get("default_worker")
    module_workers = payload.get("module_workers")
    if not isinstance(default_worker, str) or not _is_worker_name(default_worker):
        raise verify.VerificationError("runtime shard map has an invalid default worker")
    if not isinstance(module_workers, dict) or not module_workers:
        raise verify.VerificationError("runtime shard map has no module routes")
    normalized: dict[str, str] = {}
    for module_name, worker_name in module_workers.items():
        if (
            not isinstance(module_name, str)
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", module_name) is None
        ):
            raise verify.VerificationError("runtime shard map has an invalid module name")
        if not isinstance(worker_name, str) or not _is_worker_name(worker_name):
            raise verify.VerificationError("runtime shard map has an invalid worker name")
        normalized[module_name] = worker_name
    workers = set(normalized.values())
    if default_worker not in workers:
        raise verify.VerificationError("runtime shard map default worker is unrouted")
    if payload.get("module_count") != len(normalized):
        raise verify.VerificationError("runtime shard map module_count is inconsistent")
    if payload.get("shard_count") != len(workers):
        raise verify.VerificationError("runtime shard map shard_count is inconsistent")
    result = _RuntimeShardMap(default_worker=default_worker, module_workers=normalized)
    with _CACHE_LOCK:
        _SHARD_MAP_CACHE[path] = (*cache_key, result)
    return result


def _is_worker_name(name: str) -> bool:
    if os.name == "nt":
        return re.fullmatch(r"algenta-runtime-worker(?:-\d{3})?\.exe", name) is not None
    return re.fullmatch(r"algenta-runtime-worker(?:-\d{3})?", name) is not None


def _candidate_paths(
    module_name: str | None = None,
) -> tuple[tuple[str, Path, bool, str | None], ...]:
    candidates: list[tuple[str, Path, bool, str | None]] = []
    override = os.environ.get("ALGENTA_NATIVE_WORKER") or os.environ.get("ALGENTA_RUNTIME_WORKER")
    if override:
        candidates.append(("env override", Path(override), False, None))

    legacy_override = os.environ.get("ALGENTA_MOJO_BINARY")
    if legacy_override and legacy_override != override:
        candidates.append(("env override", Path(legacy_override), False, None))

    runtime_dir = _runtime_package_dir()
    if runtime_dir is not None:
        try:
            shard_map = _load_shard_map(runtime_dir)
            worker_name = shard_map.module_workers.get(module_name, shard_map.default_worker)
            candidates.append(("bundled runtime", runtime_dir / worker_name, True, None))
        except verify.VerificationError as exc:
            candidates.append(("bundled runtime", runtime_dir / WORKER_BASENAME, True, str(exc)))

    repo_worker = _repo_root() / "mojo_build" / "simulate"
    candidates.append(("repo-dev runtime", repo_worker, False, None))
    return tuple(candidates)


def _verify_bundled_worker(path: Path) -> None:
    artifact_dir = path.parent
    shard_map = _load_shard_map(artifact_dir)
    if path.name not in shard_map.workers:
        raise verify.VerificationError("selected runtime worker is not present in the shard map")
    resolved_artifact_dir = artifact_dir.resolve()
    with _CACHE_LOCK:
        if resolved_artifact_dir in _VERIFIED_RUNTIME_DIRS:
            return
    manifest_path = artifact_dir / MANIFEST_NAME
    sig_path = artifact_dir / MANIFEST_SIG_NAME
    if not (manifest_path.exists() and sig_path.exists()):
        raise verify.VerificationError("signed runtime manifest missing")
    artifact_pubkey = _artifact_release_public_key(artifact_dir)
    if artifact_pubkey is None:
        raise verify.VerificationError("runtime release public key is missing")
    trusted_pubkey = verify.release_public_key()
    if artifact_pubkey.public_numbers() != trusted_pubkey.public_numbers():
        raise verify.VerificationError(
            "runtime release public key does not match the embedded Algenta trust anchor"
        )
    manifest = verify.verify_manifest(
        manifest_path.read_bytes(), sig_path.read_bytes(), pubkey=trusted_pubkey
    )
    platform = manifest.get("platform")
    if platform != paths.platform_tag():
        raise verify.VerificationError(
            f"runtime built for {platform!r}, this machine is {paths.platform_tag()!r}"
        )
    signed_names: set[str] = set()
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
        signed_names.add(name)
    required_names = set(shard_map.workers) | {SHARD_MAP_NAME}
    missing_names = sorted(required_names - signed_names)
    if missing_names:
        raise verify.VerificationError(
            "runtime shard artifacts missing from signed manifest: " + ", ".join(missing_names)
        )
    with _CACHE_LOCK:
        _VERIFIED_RUNTIME_DIRS.add(resolved_artifact_dir)


def _ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    if not os.access(path, os.X_OK):
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def resolve_worker(
    *, module_name: str | None = None, require_verified: bool = False
) -> NativeWorkerResolution | None:
    last_public_error: str | None = None
    for source, path, must_verify, selection_error in _candidate_paths(module_name):
        try:
            if selection_error is not None:
                last_public_error = (
                    "The bundled Algenta runtime failed integrity verification. "
                    "Upgrade Algenta or install a build that supports this platform."
                )
                if require_verified:
                    return NativeWorkerResolution(source, path, False, last_public_error)
                continue
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


def require_worker(
    *, module_name: str | None = None, require_verified: bool = False
) -> NativeWorkerResolution:
    resolved = resolve_worker(module_name=module_name, require_verified=require_verified)
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
    module_name: str | None = None,
) -> dict[str, Any]:
    """Send one framed request to the worker that owns the routed module.

    `module_name` overrides shard routing. Needed for coarse message types such
    as `batch_execute`, whose frame has no single top-level "module" key: the
    caller groups its items by owning worker and names the routing module for
    each group. Omitting it preserves the previous behaviour exactly — derive
    from `request["module"]` for `library_execute`, otherwise the default worker.
    """
    if module_name is None:
        raw_module_name = (
            request.get("module") if request.get("type") == "library_execute" else None
        )
        module_name = raw_module_name if isinstance(raw_module_name, str) else None
    resolution = require_worker(module_name=module_name, require_verified=require_verified)
    return _session_for(resolution).execute(request, timeout)


def _session_for(resolution: NativeWorkerResolution) -> _WorkerSession:
    with _SESSION_LOCK:
        session = _SESSIONS.get(resolution.path)
        if session is None:
            session = _WorkerSession(resolution)
            _SESSIONS[resolution.path] = session
        return session


def ensure_ready(
    *, timeout: float = _STARTUP_TIMEOUT_SECONDS, require_verified: bool = False
) -> None:
    resolution = require_worker(require_verified=require_verified)
    _session_for(resolution).ensure_ready(timeout)


def shutdown() -> None:
    with _SESSION_LOCK:
        for session in _SESSIONS.values():
            session.close()
        _SESSIONS.clear()
    with _CACHE_LOCK:
        _SHARD_MAP_CACHE.clear()
        _VERIFIED_RUNTIME_DIRS.clear()


def runtime_module_filter() -> tuple[str, ...] | None:
    resolution = resolve_worker(require_verified=False)
    if resolution is None or resolution.public_error:
        return None
    if resolution.source == "bundled runtime":
        try:
            return tuple(sorted(_load_shard_map(resolution.path.parent).module_workers))
        except verify.VerificationError:
            return None
    manifest_path = resolution.path.with_name(f"{resolution.path.name}.manifest.json")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    module_filter = payload.get("module_filter")
    if module_filter == []:
        return None
    if not isinstance(module_filter, list) or any(
        not isinstance(item, str) or not item.strip() for item in module_filter
    ):
        return None
    return tuple(dict.fromkeys(item.strip() for item in module_filter))


def info(*, require_verified: bool = False) -> dict[str, Any]:
    resolution = resolve_worker(require_verified=require_verified)
    if resolution is None:
        return {
            "source": None,
            "path": None,
            "verified": False,
            "warm_session": False,
            "error": None,
        }
    with _SESSION_LOCK:
        warm_session = any(session.ready for session in _SESSIONS.values())
    return {
        "source": resolution.source,
        "path": str(resolution.path),
        "verified": resolution.verified,
        "warm_session": warm_session,
        "error": resolution.public_error,
    }


atexit.register(shutdown)
