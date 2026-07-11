"""Lazy, fail-closed loader for the bundled native Algenta runtime.

``pip install algenta`` resolves a per-platform runtime wheel that contains the
prebuilt native artifacts and a signed manifest. This loader opens the
in-process ABI when available, or runs the bundled worker otherwise. It does not
start a separate service, open a local TCP port, download build tools, or use
a Python computation fallback in release mode.

Stable C ABI:
    int32 algenta_runtime_version(void)
    char* algenta_runtime_platform(void)
    void* algenta_runtime_init(const char* config_json)
    char* algenta_runtime_execute(void* h, const char* req)
    void  algenta_runtime_free(char* ptr)
    void  algenta_runtime_shutdown(void* h)

Resolver order:
    1. $ALGENTA_NATIVE_KERNEL override for internal/debug builds
    2. verified cache under ~/.algenta/runtime/<platform>/
    3. bundled ``algenta_runtime_native`` wheel
    4. repo development build output

The manifest signature, artifact SHA-256, ABI version, and platform tag are
verified before execution. The release default is fail-closed.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import threading

from algenta import __version__, paths
from algenta.native import verify, worker

# The native lib returns this from algenta_runtime_version(). A mismatch
# means the installed wheel and native lib disagree, so execution fails closed.
ABI_VERSION = 1


class RuntimeUnavailable(RuntimeError):  # noqa: N818
    """The bundled native runtime could not be loaded or verified."""


def _fallback_mode() -> str:
    # Release default is deny. Internal/dev builds can opt into a permissive
    # resolver via ALGENTA_RUNTIME_FALLBACK_MODE=allow.
    return (os.environ.get("ALGENTA_RUNTIME_FALLBACK_MODE") or "deny").strip().lower()


def _candidate_paths() -> list[tuple[str, str]]:
    """(source_label, path) candidates in resolver order. Existence is checked by the caller."""
    ext = paths.lib_ext()
    stem = paths.RUNTIME_STEM
    out: list[tuple[str, str]] = []
    override = os.environ.get("ALGENTA_NATIVE_KERNEL")
    if override:
        out.append(("env ALGENTA_NATIVE_KERNEL", override))
    # verified cache (dev): ~/.algenta/runtime/<platform>/libalgenta_runtime.<ext>
    cache = os.path.join(paths.algenta_home(), "runtime", paths.platform_tag(), f"{stem}.{ext}")
    out.append(("verified cache", cache))
    # bundled runtime package (PUBLIC default): separate import namespace, automatic dependency
    runtime_dir = paths.runtime_native_dir()
    if runtime_dir:
        out.append(("bundled runtime", os.path.join(runtime_dir, f"{stem}.{ext}")))
    # repo-dev in-tree
    here = os.path.dirname(__file__)
    out.append(
        (
            "repo-dev build output",
            os.path.abspath(
                os.path.join(here, "..", "..", "..", "..", "mojo_build", f"{stem}.{ext}")
            ),
        )
    )
    return out


def _resolve_native_lib() -> tuple[str, str] | None:
    """Return (source_label, path) of the first existing candidate, or None."""
    for label, path in _candidate_paths():
        try:
            if path and os.path.exists(path):
                return label, path
        except OSError:
            continue
    return None


def _fail_closed(
    reason: str, *, path: str | None = None, source: str | None = None
) -> RuntimeUnavailable:
    """Build an Algenta-language fail-closed error without toolchain setup text."""
    lines = [
        "The bundled Algenta runtime is unavailable, so this command was refused (fail-closed).",
        f"  reason:          {reason}",
        f"  platform:        {paths.platform_tag()}",
        f"  algenta version: {__version__}",
        "  expected:        bundled Algenta runtime for this platform",
    ]
    if source:
        lines.append(f"  runtime source:  {source}")
    if path:
        lines.append(f"  looked at:       {path}")
    lines.append("  fallback:        denied")
    lines.append(
        "  fix:             upgrade Algenta (`pip install --upgrade algenta`) "
        "or install a build that supports this platform. "
        "See https://docs.algenta.ai/runtime."
    )
    return RuntimeUnavailable("\n".join(lines))


def _verify_bundle(lib_path: str, source: str) -> None:
    """Verify the signed manifest + this artifact's SHA-256 + platform tag + ABI, next to the lib.

    Skipped only for an explicit $ALGENTA_NATIVE_KERNEL override in a
    permissive internal/dev build. Public bundled/cache paths are always
    verified.
    """
    lib_dir = os.path.dirname(lib_path)
    manifest_path = os.path.join(lib_dir, paths.MANIFEST_NAME)
    sig_path = os.path.join(lib_dir, paths.MANIFEST_SIG_NAME)
    if not (os.path.exists(manifest_path) and os.path.exists(sig_path)):
        raise _fail_closed(
            "signed manifest missing next to the runtime", path=manifest_path, source=source
        )
    try:
        with open(manifest_path, "rb") as fh:
            manifest_bytes = fh.read()
        with open(sig_path, "rb") as fh:
            sig = fh.read()
        manifest = verify.verify_manifest(manifest_bytes, sig)
    except verify.VerificationError as exc:
        raise _fail_closed(
            f"manifest signature invalid: {exc}", path=manifest_path, source=source
        ) from exc
    plat = manifest.get("platform")
    if plat != paths.platform_tag():
        raise _fail_closed(
            f"runtime built for {plat!r}, this machine is {paths.platform_tag()!r}",
            path=lib_path,
            source=source,
        )
    entry = next(
        (a for a in manifest.get("artifacts", []) if a.get("name") == os.path.basename(lib_path)),
        None,
    )
    if entry is None:
        raise _fail_closed(
            "runtime not listed in the signed manifest", path=lib_path, source=source
        )
    try:
        verify.verify_artifact(lib_path, entry["sha256"])
    except verify.VerificationError as exc:
        raise _fail_closed(
            f"runtime integrity check failed: {exc}", path=lib_path, source=source
        ) from exc


_LIB: ctypes.CDLL | None = None
_LIB_PATH: str | None = None
_LIB_SOURCE: str | None = None
_HANDLE: ctypes.c_void_p | None = None
_LOCK = threading.Lock()


def _bind_abi(lib: ctypes.CDLL) -> None:
    lib.algenta_runtime_version.argtypes = []
    lib.algenta_runtime_version.restype = ctypes.c_int32
    lib.algenta_runtime_platform.argtypes = []
    lib.algenta_runtime_platform.restype = ctypes.c_char_p
    lib.algenta_runtime_init.argtypes = [ctypes.c_char_p]
    lib.algenta_runtime_init.restype = ctypes.c_void_p
    lib.algenta_runtime_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.algenta_runtime_execute.restype = (
        ctypes.c_void_p
    )  # char* we copy then free (avoid ctypes auto-free)
    lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]
    lib.algenta_runtime_free.restype = None
    lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]
    lib.algenta_runtime_shutdown.restype = None


def _load() -> ctypes.CDLL:
    """Resolve, verify, dlopen, and perform the ABI handshake."""
    global _LIB, _LIB_PATH, _LIB_SOURCE
    if _LIB is not None:
        return _LIB
    with _LOCK:
        if _LIB is not None:
            return _LIB
        resolved = _resolve_native_lib()
        if resolved is None:
            raise _fail_closed(
                "no native runtime found on any resolver path", source="bundled wheel"
            )
        source, path = resolved
        # A permissive dev override may skip verification; every other path is verified.
        skip_verify = source.startswith("env ") and _fallback_mode() == "allow"
        if not skip_verify:
            _verify_bundle(path, source)
        try:
            lib = ctypes.CDLL(path)
        except OSError as exc:
            raise _fail_closed(
                f"could not load the native runtime: {exc}", path=path, source=source
            ) from exc
        try:
            _bind_abi(lib)
            abi = int(lib.algenta_runtime_version())
        except Exception as exc:  # noqa: BLE001 — a missing/renamed symbol = wrong/corrupt lib
            raise _fail_closed(
                f"native runtime ABI not recognized: {exc}", path=path, source=source
            ) from exc
        if abi != ABI_VERSION:
            raise _fail_closed(
                f"native runtime ABI v{abi} != this package's v{ABI_VERSION}",
                path=path,
                source=source,
            )
        _LIB, _LIB_PATH, _LIB_SOURCE = lib, path, source
        return lib


def _ensure_handle(lib: ctypes.CDLL, config: dict | None = None) -> ctypes.c_void_p:
    global _HANDLE
    if _HANDLE is not None:
        return _HANDLE
    cfg = json.dumps(config or {}).encode("utf-8")
    handle = lib.algenta_runtime_init(cfg)
    if not handle:
        raise _fail_closed(
            "native runtime failed to initialize", path=_LIB_PATH, source=_LIB_SOURCE
        )
    _HANDLE = ctypes.c_void_p(handle)
    return _HANDLE


def execute(request: dict, *, config: dict | None = None) -> dict:
    """Run one request through the bundled native runtime.

    Prefer the in-process ABI when present. If a platform release ships the
    executable worker instead, execute that bundled worker directly. Neither path
    uses a Python computation fallback in a release build.
    """
    try:
        lib = _load()
    except RuntimeUnavailable as lib_exc:
        try:
            return worker.execute(request, require_verified=_fallback_mode() == "deny")
        except worker.NativeWorkerUnavailable as worker_exc:
            raise _fail_closed(str(worker_exc) or str(lib_exc)) from worker_exc
    handle = _ensure_handle(lib, config)
    req = json.dumps(request).encode("utf-8")
    ptr = lib.algenta_runtime_execute(handle, req)
    if not ptr:
        raise RuntimeUnavailable("native runtime returned no result")
    try:
        raw = ctypes.cast(ptr, ctypes.c_char_p).value or b"{}"
    finally:
        lib.algenta_runtime_free(ptr)  # the lib owns the returned buffer
    return json.loads(raw.decode("utf-8"))


def available() -> bool:
    """True if a bundled native runtime can execute right now. Never raises."""
    try:
        _load()
        return True
    except RuntimeUnavailable:
        resolved_worker = worker.resolve_worker(require_verified=_fallback_mode() == "deny")
        return bool(
            resolved_worker and not resolved_worker.public_error and resolved_worker.executable
        )


def info() -> dict:
    """Diagnostics for ``algenta runtime doctor`` — never raises."""
    resolved = _resolve_native_lib()
    source = resolved[0] if resolved else None
    path = resolved[1] if resolved else None
    loaded = _LIB is not None
    abi: int | str | None = None
    verified = False
    error = None
    mode = "in-process"
    if resolved is not None:
        try:
            _load()
            loaded = True
            verified = True
            abi = int(_LIB.algenta_runtime_version()) if _LIB is not None else None
        except RuntimeUnavailable as exc:
            error = str(exc).splitlines()[0] if str(exc) else "unavailable"

    if not loaded:
        worker_info = worker.info(require_verified=_fallback_mode() == "deny")
        if worker_info["path"]:
            source = str(worker_info["source"] or "bundled runtime")
            path = str(worker_info["path"])
            verified = bool(worker_info["verified"])
            loaded = worker_info.get("error") is None
            abi = "worker" if loaded else None
            mode = "bundled worker"
            error = worker_info.get("error")

    return {
        "runtime_source": source or "bundled runtime (not found)",
        "path": path,
        "platform_tag": paths.platform_tag(),
        "package_version": __version__,
        "abi_version_expected": ABI_VERSION,
        "abi_version_native": abi,
        "loaded": loaded,
        "verified": verified,
        "mode": mode,
        "fallback": _fallback_mode(),
        "tcp_listeners": [],
        "python": sys.version.split()[0],
        "error": error,
    }


def shutdown() -> None:
    """Dispose the runtime handle (best-effort). Mostly for tests / clean process exit."""
    global _HANDLE
    with _LOCK:
        if _LIB is not None and _HANDLE is not None:
            try:
                _LIB.algenta_runtime_shutdown(_HANDLE)
            except Exception:  # noqa: BLE001, S110
                pass
        _HANDLE = None
