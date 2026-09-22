"""Native loader for this Algenta kernel (ABI v1). Standard library only.

One library instance per loaded kernel, one handle, one lock: calls into the native runtime are
serialised within this package (the wrapper's defined execution scope). Responses are copied out
of native memory and released through the same library instance that allocated them. Every file
the loader opens is named in `_native/manifest.json` and verified against its recorded size and
SHA-256 before it is loaded.
"""
from __future__ import annotations

import atexit
import ctypes
import hashlib
import json
import os
import platform
import sys
import threading

ABI_VERSION = 1
_LIBRARY = "__LIBRARY_NAME__"
_FAMILY = "__FAMILY__"
_BACKEND = "__BACKEND__"


class KernelError(RuntimeError):
    """A structured error from the Algenta kernel: `code`, `message`, optional `details`."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


class NativeUnavailable(KernelError):
    """The native library could not be loaded on this machine (see `code` and `message`)."""


def _native_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "_native")


def _read_manifest(native_dir: str) -> dict:
    try:
        with open(os.path.join(native_dir, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        raise NativeUnavailable("native_unavailable", "manifest.json is missing or unreadable; download the kernel again") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict) or not isinstance(manifest.get("load_order"), list) or not isinstance(manifest.get("library"), str):
        raise NativeUnavailable("native_unavailable", "manifest.json is not in the expected form; download the kernel again")
    return manifest


def _check_platform(manifest: dict) -> None:
    minos = manifest.get("minos")
    if sys.platform == "darwin" and isinstance(minos, str) and minos:
        running = platform.mac_ver()[0]
        try:
            have = tuple(int(x) for x in running.split(".")[:2])
            need = tuple(int(x) for x in minos.split(".")[:2])
        except ValueError:
            return
        if have < need:
            raise NativeUnavailable("platform_unsupported", f"{_FAMILY} ({_BACKEND}) needs macOS {minos} or later; this Mac runs {running}")


def _verified_path(native_dir: str, name: str, files: dict) -> str:
    """Resolve one manifest entry to a real path after checking it is exactly the file that was published."""
    if os.path.basename(name) != name or name not in files:
        raise NativeUnavailable("native_unavailable", f"manifest.json names an unexpected file {name!r}; download the kernel again")
    real = os.path.realpath(os.path.join(native_dir, name))
    try:
        with open(real, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise NativeUnavailable("native_unavailable", f"{name} is missing; download the kernel again") from exc
    if data.startswith(b"version https://git-lfs"):
        raise NativeUnavailable("native_unavailable", f"{name} is a Git LFS pointer, not the library; load the kernel with `kernels.get_kernel`, or run `git lfs pull`")
    spec = files[name] if isinstance(files[name], dict) else {}
    if len(data) != spec.get("bytes") or hashlib.sha256(data).hexdigest() != spec.get("sha256"):
        raise NativeUnavailable("native_unavailable", f"{name} is incomplete or altered; clear the cache and download the kernel again")
    return real


def _cuda_capability() -> tuple[int, int]:
    """(major, minor) of device 0 through the NVIDIA driver library (no CUDA toolkit needed)."""
    cuda = None
    for candidate in ("libcuda.so.1", "libcuda.so"):
        try:
            cuda = ctypes.CDLL(candidate)
            break
        except OSError:
            continue
    if cuda is None:
        raise NativeUnavailable("gpu_unavailable", "libcuda.so.1 was not found; the CUDA build needs the NVIDIA driver (580 or later)")
    if cuda.cuInit(0) != 0:
        raise NativeUnavailable("gpu_unavailable", "the NVIDIA driver reported no usable device (cuInit failed)")
    device = ctypes.c_int(0)
    if cuda.cuDeviceGet(ctypes.byref(device), 0) != 0:
        raise NativeUnavailable("gpu_unavailable", "no NVIDIA device 0")
    major, minor = ctypes.c_int(0), ctypes.c_int(0)
    cuda.cuDeviceGetAttribute(ctypes.byref(major), 75, device)  # CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR
    cuda.cuDeviceGetAttribute(ctypes.byref(minor), 76, device)  # CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR
    return major.value, minor.value


def _select_library(manifest: dict) -> str:
    """The primary library, or for CUDA the build matching the device: the exact `sm_<cc>` when it
    was built, else the newest built target of the same major generation not above the device."""
    libraries = manifest.get("cuda_libraries") or {}
    if _BACKEND != "cuda" or not libraries:
        return manifest["library"]
    forced = os.environ.get("ALGENTA_CUDA_ARCH")
    if forced:
        if forced not in libraries:
            raise NativeUnavailable("gpu_unsupported", f"ALGENTA_CUDA_ARCH={forced!r} is not one of the built targets {sorted(libraries)}")
        return libraries[forced]
    major, minor = _cuda_capability()
    # Every shipped NVIDIA compute capability has a single-digit minor (…, 8.9, 9.0, 10.0, 12.0),
    # which makes the `sm_<major><minor>` spelling and the `major*10+minor` ordinal agree with the
    # `sm_NNN` manifest keys (compared as int(key[3:])). Refuse a hypothetical two-digit minor
    # rather than silently conflate it with the next major generation.
    if not 0 <= minor <= 9:
        raise NativeUnavailable("gpu_unsupported", f"unexpected compute-capability minor in {major}.{minor}")
    device_cc = major * 10 + minor
    exact = f"sm_{major}{minor}"
    if exact in libraries:
        return libraries[exact]
    # Every Algenta CUDA build embeds PTX for its --target-accelerator sm_N (NVPTX backend; verified
    # by a `.target sm_N` section in each .so), and PTX is forward-compatible: it JIT-runs on any
    # device of capability >= N. So pick the highest built target not above the device (an sm_80
    # build serves A100, L4 sm_89, H100/H200 sm_90). A SASS-only build would break this, but the
    # toolchain path used here always emits PTX.
    usable = sorted(int(t[3:]) for t in libraries if t.startswith("sm_") and t[3:].isdigit() and int(t[3:]) <= device_cc)
    if usable:
        return libraries[f"sm_{usable[-1]}"]
    raise NativeUnavailable("gpu_unsupported", f"this build's oldest CUDA target is above the device's compute capability {major}.{minor}; it carries {', '.join(sorted(libraries))}")


def _dlopen(real: str, name: str) -> ctypes.CDLL:
    try:
        return ctypes.CDLL(real)
    except OSError as exc:
        reason = str(exc).splitlines()[0] if str(exc) else "the dynamic loader refused it"
        raise NativeUnavailable("native_unavailable", f"{name} could not be loaded: {reason}") from exc


class _Runtime:
    def __init__(self) -> None:
        native_dir = _native_dir()
        manifest = _read_manifest(native_dir)
        _check_platform(manifest)
        files = manifest["files"]
        # Dependencies first, by real path: the Hub cache stores files as symlinks into blobs/, and
        # the dynamic loader resolves sibling references from the real location. Loading each
        # dependency explicitly lets it satisfy the kernel library's references from images already
        # in the process (matched by install name).
        self._closure = [_dlopen(_verified_path(native_dir, name, files), name) for name in manifest["load_order"]]
        chosen = _select_library(manifest)
        lib = _dlopen(_verified_path(native_dir, chosen, files), chosen)
        self.library = chosen
        try:
            version_fn = lib.algenta_runtime_version
            init_fn = lib.algenta_runtime_init
            execute_fn = lib.algenta_runtime_execute
            free_fn = lib.algenta_runtime_free
            shutdown_fn = lib.algenta_runtime_shutdown
        except AttributeError as exc:
            raise NativeUnavailable("abi_mismatch", f"{chosen} does not export the Algenta ABI v{ABI_VERSION}") from exc
        version_fn.restype = ctypes.c_int32
        version_fn.argtypes = []
        init_fn.argtypes = [ctypes.c_void_p]
        init_fn.restype = ctypes.c_void_p
        execute_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        execute_fn.restype = ctypes.c_void_p  # never c_char_p: we must free the pointer
        free_fn.argtypes = [ctypes.c_void_p]
        free_fn.restype = None
        shutdown_fn.argtypes = [ctypes.c_void_p]
        shutdown_fn.restype = None
        version = int(version_fn())
        if version != ABI_VERSION:
            raise NativeUnavailable("abi_mismatch", f"native ABI v{version} != expected v{ABI_VERSION}")
        self._lib = lib
        self._execute = execute_fn
        self._free = free_fn
        self._shutdown = shutdown_fn
        self._lock = threading.Lock()  # execute and shutdown never nest; a re-entrant call is misuse and must block
        self._handle = init_fn(b"{}")
        if not self._handle:
            raise NativeUnavailable("init_failed", "the native runtime could not be initialised")
        atexit.register(self.shutdown)

    def execute(self, request: dict) -> dict:
        try:
            payload = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, OverflowError, UnicodeEncodeError) as exc:
            raise KernelError("invalid_arguments", f"the request cannot be encoded: {exc}") from exc
        with self._lock:
            if not self._handle:
                raise KernelError("runtime_closed", "the native runtime has been shut down")
            pointer = self._execute(self._handle, payload)
            if not pointer:
                raise KernelError("runtime_execution_failed", "the native runtime returned no response (out of memory)")
            try:
                raw = ctypes.string_at(pointer)
            finally:
                self._free(pointer)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise KernelError("runtime_execution_failed", "the native runtime returned malformed JSON") from exc

    def shutdown(self) -> None:
        with self._lock:
            if self._handle:
                self._shutdown(self._handle)
                self._handle = None


_runtime: _Runtime | None = None
_runtime_error: KernelError | None = None
_runtime_lock = threading.Lock()


def runtime() -> _Runtime:
    global _runtime, _runtime_error
    with _runtime_lock:
        if _runtime is None:
            if _runtime_error is not None:
                raise _runtime_error
            try:
                _runtime = _Runtime()
            except KernelError as exc:
                _runtime_error = exc
                raise
        return _runtime


def _forget_runtime() -> None:
    """After fork() the child must not reuse the parent's handle or its worker threads."""
    global _runtime, _runtime_error
    _runtime = None
    _runtime_error = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_forget_runtime)


def execute(request: dict) -> dict:
    """Send one request envelope to the native runtime and return the decoded reply."""
    return runtime().execute(request)
