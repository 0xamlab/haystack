"""Lazy, fail-closed loader for the bundled, in-process native Algenta runtime.

The public contract: ``pip install algenta`` ships a per-platform wheel that CONTAINS the prebuilt native
runtime (``algenta/runtime/_native/libalgenta_runtime.*`` + a signed manifest). This loader opens it
IN-PROCESS via ctypes on first use — no daemon, no local TCP port, no download, no compiler, and it never
mentions Mojo.

Stable C ABI (the ONLY surface the Python layer knows — Mojo can change internally without touching this):
    int32   algenta_runtime_version(void)                       # ABI/format version handshake
    char*   algenta_runtime_platform(void)                      # platform tag the lib was built for
    void*   algenta_runtime_init(const char* config_json)       # opaque runtime handle
    char*   algenta_runtime_execute(void* h, const char* req)   # request json -> result json (owned by lib)
    void    algenta_runtime_free(char* ptr)                     # free a string returned by execute/platform
    void    algenta_runtime_shutdown(void* h)                   # dispose the handle

Resolver order (PUBLIC builds normalize to bundled-in-wheel):
    1. $ALGENTA_NATIVE_KERNEL           — the ONLY sanctioned override (internal / dev / debug)
    2. verified cache ~/.algenta/runtime/<platform>/   — dev
    3. bundled-in-wheel algenta/runtime/_native/       — PUBLIC default
    4. repo-dev mojo_build/                             — dev

Before executing, the manifest signature (RS256 over the exact shipped bytes) + the per-artifact SHA-256 +
the ABI version + the platform tag are verified. ``ALGENTA_RUNTIME_FALLBACK_MODE=deny`` (the release default)
means ANY failure raises a fail-closed error in Algenta language — there is no readable-Python fallback.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading

from algenta import __version__, paths
from algenta.native import verify

# The ABI/format contract number. The native lib returns this from algenta_runtime_version(); a mismatch
# means the installed wheel and the native lib disagree → fail closed (never silently run a wrong ABI).
ABI_VERSION = 1


class RuntimeUnavailable(RuntimeError):
    """The bundled native runtime could not be loaded/verified. Fail closed — never fall back silently."""


def _fallback_mode() -> str:
    # Release default is deny. There is no Python fallback for Algenta; the mode exists for parity + so an
    # internal/dev build can opt into a permissive resolver via ALGENTA_RUNTIME_FALLBACK_MODE=allow.
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
    # sidecar package (PUBLIC default): the algenta-runtime-native dist, its own import namespace
    sidecar = paths.sidecar_native_dir()
    if sidecar:
        out.append(("bundled sidecar", os.path.join(sidecar, f"{stem}.{ext}")))
    # repo-dev in-tree
    here = os.path.dirname(__file__)
    out.append(("repo-dev mojo_build", os.path.abspath(os.path.join(here, "..", "..", "..", "..", "mojo_build", f"{stem}.{ext}"))))
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


def _fail_closed(reason: str, *, path: str | None = None, source: str | None = None) -> RuntimeUnavailable:
    """Build the Algenta-language fail-closed error. Speaks platform / package version / expected lib /
    upgrade — NEVER 'mojo command not found' / 'install Mojo' / 'install Modular'."""
    lines = [
        "The bundled Algenta runtime is unavailable, so this command was refused (fail-closed).",
        f"  reason:          {reason}",
        f"  platform:        {paths.platform_tag()}",
        f"  algenta version: {__version__}",
        f"  expected lib:    {paths.runtime_lib_filename()} (bundled in the wheel)",
    ]
    if source:
        lines.append(f"  runtime source:  {source}")
    if path:
        lines.append(f"  looked at:       {path}")
    lines.append("  fallback:        denied")
    lines.append(
        "  fix:             upgrade Algenta (`pip install --upgrade algenta`) or install a build that "
        "supports this platform. See https://docs.algenta.ai/runtime."
    )
    return RuntimeUnavailable("\n".join(lines))


def _verify_bundle(lib_path: str, source: str) -> None:
    """Verify the signed manifest + this artifact's SHA-256 + platform tag + ABI, next to the lib.

    Skipped ONLY for an explicit $ALGENTA_NATIVE_KERNEL override in a permissive (allow) dev build — the
    public bundled/cache paths are ALWAYS verified.
    """
    lib_dir = os.path.dirname(lib_path)
    manifest_path = os.path.join(lib_dir, paths.MANIFEST_NAME)
    sig_path = os.path.join(lib_dir, paths.MANIFEST_SIG_NAME)
    if not (os.path.exists(manifest_path) and os.path.exists(sig_path)):
        raise _fail_closed("signed manifest missing next to the runtime", path=manifest_path, source=source)
    try:
        with open(manifest_path, "rb") as fh:
            manifest_bytes = fh.read()
        with open(sig_path, "rb") as fh:
            sig = fh.read()
        manifest = verify.verify_manifest(manifest_bytes, sig)
    except verify.VerificationError as exc:
        raise _fail_closed(f"manifest signature invalid: {exc}", path=manifest_path, source=source) from exc
    plat = manifest.get("platform")
    if plat != paths.platform_tag():
        raise _fail_closed(
            f"runtime built for {plat!r}, this machine is {paths.platform_tag()!r}", path=lib_path, source=source
        )
    entry = next((a for a in manifest.get("artifacts", []) if a.get("name") == os.path.basename(lib_path)), None)
    if entry is None:
        raise _fail_closed("runtime not listed in the signed manifest", path=lib_path, source=source)
    try:
        verify.verify_artifact(lib_path, entry["sha256"])
    except verify.VerificationError as exc:
        raise _fail_closed(f"runtime integrity check failed: {exc}", path=lib_path, source=source) from exc


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
    lib.algenta_runtime_execute.restype = ctypes.c_void_p  # char* we copy then free (avoid ctypes auto-free)
    lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]
    lib.algenta_runtime_free.restype = None
    lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]
    lib.algenta_runtime_shutdown.restype = None


def _load() -> ctypes.CDLL:
    """Resolve → verify → dlopen → ABI handshake. Singleton; raises RuntimeUnavailable (fail closed)."""
    global _LIB, _LIB_PATH, _LIB_SOURCE
    if _LIB is not None:
        return _LIB
    with _LOCK:
        if _LIB is not None:
            return _LIB
        resolved = _resolve_native_lib()
        if resolved is None:
            raise _fail_closed("no native runtime found on any resolver path", source="bundled wheel")
        source, path = resolved
        # An explicit override in a permissive dev build may skip verification; every other path is verified.
        skip_verify = source.startswith("env ") and _fallback_mode() == "allow"
        if not skip_verify:
            _verify_bundle(path, source)
        try:
            lib = ctypes.CDLL(path)
        except OSError as exc:
            raise _fail_closed(f"could not load the native runtime: {exc}", path=path, source=source) from exc
        try:
            _bind_abi(lib)
            abi = int(lib.algenta_runtime_version())
        except Exception as exc:  # noqa: BLE001 — a missing/renamed symbol = wrong/corrupt lib
            raise _fail_closed(f"native runtime ABI not recognized: {exc}", path=path, source=source) from exc
        if abi != ABI_VERSION:
            raise _fail_closed(
                f"native runtime ABI v{abi} != this package's v{ABI_VERSION}", path=path, source=source
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
        raise _fail_closed("native runtime failed to initialize", path=_LIB_PATH, source=_LIB_SOURCE)
    _HANDLE = ctypes.c_void_p(handle)
    return _HANDLE


def execute(request: dict, *, config: dict | None = None) -> dict:
    """Run one request through the in-process native runtime. Lazy-loads + verifies on first call.

    Raises RuntimeUnavailable (fail closed) if the runtime is missing/unverified/wrong-ABI — never a Python
    fallback in a release build."""
    lib = _load()
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
    """True if the runtime can be loaded + verified right now (no exception). Never raises."""
    try:
        _load()
        return True
    except RuntimeUnavailable:
        return False


def info() -> dict:
    """Diagnostics for ``algenta runtime doctor`` — never raises. Reports resolution + load state without
    requiring a successful load."""
    resolved = _resolve_native_lib()
    source = resolved[0] if resolved else None
    path = resolved[1] if resolved else None
    loaded = _LIB is not None
    abi = None
    verified = False
    error = None
    if resolved is not None:
        try:
            _load()
            loaded = True
            verified = True
            abi = int(_LIB.algenta_runtime_version()) if _LIB is not None else None
        except RuntimeUnavailable as exc:
            error = str(exc).splitlines()[0] if str(exc) else "unavailable"
    return {
        "runtime_source": source or "bundled wheel (not found)",
        "path": path,
        "platform_tag": paths.platform_tag(),
        "package_version": __version__,
        "abi_version_expected": ABI_VERSION,
        "abi_version_native": abi,
        "loaded": loaded,
        "verified": verified,
        "mode": "in-process",
        "fallback": _fallback_mode(),
        "tcp_listeners": [],  # in-process ctypes: this path opens NO sockets, by construction
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
            except Exception:  # noqa: BLE001
                pass
        _HANDLE = None
