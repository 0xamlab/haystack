"""Vetting of operator-supplied runtime-worker launch parameters (``daemon.py`` spawns the worker).

The daemon lets an operator point it at a worker executable (``ALGENTA_NATIVE_WORKER`` /
``ALGENTA_RUNTIME_WORKER`` / legacy ``ALGENTA_MOJO_BINARY``) and at the unix socket the worker
should listen on (``ALGENTA_MOJO_SOCK``). Both values end up in the worker's argv, so they are
read and checked HERE, in one place, before ``daemon.py`` ever builds that argv:

  * the executable must be an absolute path to an existing regular file with the executable bit
    set — never a bare name left to PATH lookup, never a directory, never a non-executable blob;
  * the socket path must be absolute and short enough for ``sockaddr_un`` (macOS caps ``sun_path``
    at 104 bytes, Linux at 108): a too-long path otherwise fails deep inside the worker's ``bind()``
    with an error that does not name the cause.

Nothing here spawns anything; it only decides what the daemon may spawn. ``native_worker.py``
owns discovery and signature verification of the *bundled* worker; this module owns the
operator-override and launch-time checks that sit in front of ``subprocess``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from apps.runtime.native_worker import NativeWorkerUnavailable

__all__ = [
    "WORKER_OVERRIDE_ENV_VARS",
    "WORKER_SOCKET_ENV_VAR",
    "launchable_worker_executable",
    "launchable_worker_socket",
    "worker_override_path",
    "worker_socket_path",
]

# Precedence order — the first one set (non-empty after stripping) wins. Same order
# ``native_worker._candidate_paths`` uses for bundled-worker discovery.
WORKER_OVERRIDE_ENV_VARS: tuple[str, ...] = (
    "ALGENTA_NATIVE_WORKER",
    "ALGENTA_RUNTIME_WORKER",
    "ALGENTA_MOJO_BINARY",  # legacy dev override
)
WORKER_SOCKET_ENV_VAR = "ALGENTA_MOJO_SOCK"

# sizeof(sockaddr_un.sun_path) — the terminating NUL has to fit too.
_SUN_PATH_MAX = 104 if sys.platform == "darwin" else 108


def worker_override_path() -> Path | None:
    """The operator's explicit worker executable, or ``None`` when no override env var is set.

    Only the *choice* is made here (empty values count as unset — an empty override used to
    resolve to ``Path("")`` i.e. the current directory). Existence is deliberately not checked at
    this point: the daemon reports an absent override as "worker not found" instead of silently
    launching a fallback the operator did not ask for. :func:`launchable_worker_executable` vets
    the path right before it is spawned.
    """
    for var in WORKER_OVERRIDE_ENV_VARS:
        raw = (os.environ.get(var) or "").strip()
        if raw:
            return Path(raw)
    return None


def launchable_worker_executable(path: Path | str) -> Path:
    """Vet ``path`` immediately before it is handed to ``subprocess``; return it as a ``Path``.

    Accepts only an absolute path to an existing regular file that is executable. Anything else
    raises :class:`NativeWorkerUnavailable` — fail closed rather than let the OS resolve a bare
    name through ``PATH`` or attempt to exec a directory / data file.
    """
    candidate = Path(path)
    shown = str(candidate)
    if not candidate.is_absolute():
        raise NativeWorkerUnavailable(
            f"runtime worker path must be absolute (no PATH lookup for the worker): {shown!r}"
        )
    if not candidate.is_file():
        raise NativeWorkerUnavailable(f"runtime worker is not a regular file: {shown}")
    if not os.access(candidate, os.X_OK):
        raise NativeWorkerUnavailable(f"runtime worker is not executable: {shown}")
    return candidate


def worker_socket_path(default: Path | str) -> str:
    """The unix socket the worker listens on: ``ALGENTA_MOJO_SOCK`` when set, else ``default``.

    Resolution only (import-safe): returned absolute — a relative value is anchored at the current
    directory, which is what it meant before too — and an empty/blank value counts as unset. The
    ``sockaddr_un`` length check is :func:`launchable_worker_socket`, run right before the spawn.
    """
    raw = (os.environ.get(WORKER_SOCKET_ENV_VAR) or "").strip()
    sock = Path(raw) if raw else Path(default)
    if not sock.is_absolute():
        sock = sock.absolute()
    return str(sock)


def launchable_worker_socket(path: str) -> str:
    """Vet the worker socket path immediately before the worker is spawned with it.

    Refuses a path that cannot be bound: longer than ``sockaddr_un.sun_path`` allows (the worker
    would otherwise die inside ``bind()`` with an error that does not name the cause), or one that
    names an existing directory (the daemon clears a stale socket by unlinking that path — it must
    never be pointed at a directory or at anything but a socket). Raises ``ValueError``.
    """
    sock = Path(path)
    if len(os.fsencode(sock)) >= _SUN_PATH_MAX:
        raise ValueError(
            f"{WORKER_SOCKET_ENV_VAR} is too long for a unix socket path on this platform "
            f"(limit {_SUN_PATH_MAX - 1} bytes): {str(sock)!r}"
        )
    if sock.exists() and not sock.is_socket():
        raise ValueError(
            f"{WORKER_SOCKET_ENV_VAR} points at an existing non-socket path; refusing to replace "
            f"it: {str(sock)!r}"
        )
    return str(sock)
