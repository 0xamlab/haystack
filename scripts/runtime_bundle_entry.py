#!/usr/bin/env python3
"""Entry point for the PyInstaller-built, self-contained Algenta runtime daemon.

This is what `scripts/runtime_bundle.spec` freezes into `daemon/algenta-runtime-daemon`
inside the signed managed-runtime bundle (see scripts/build_runtime_bundle.py).
It is a thin dispatcher over apps.runtime.daemon that additionally:

  1. Understands `--help` / `--version` (the raw daemon module does not), so the
     SQAI provisioner and the bundle acceptance gate have a zero-side-effect
     health path that exercises the full frozen import graph.
  2. Points the daemon at the bundle's own sharded workers (siblings of the
     daemon/ directory under engine/) when the worker env vars are unset, so a
     bundle extracted anywhere runs transparently — no repo checkout, no venv,
     no manual configuration. The daemon resolves the DEFAULT shard worker from
     runtime-shards.json; per-module routing across shards is carried by the
     shard map the bundle ships (engine/runtime-shards.json). Extra argv flags
     after the command (e.g. the provisioner's `--foreground`) are accepted and
     ignored: `start` is foreground/blocking by design.

Bundle layout the default resolution assumes (built by build_runtime_bundle.py):

    <bundle-root>/
      manifest.json / manifest.sig
      daemon/algenta-runtime-daemon   <- sys.executable when frozen
      daemon/_internal/...
      engine/algenta-runtime-worker[-NNN]   (sharded workers + dylib closure)
      engine/runtime-shards.json
      engine/runtime_library_inventory.json
      python/lib/python3.X/...              (trimmed CPython home)

Commands: start (foreground; default) | stop | status | --version | --help
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_VERSION = os.environ.get("ALGENTA_RUNTIME_BUNDLE_VERSION", "0.1.1")

_USAGE = """\
algenta-runtime-daemon — self-contained Algenta local runtime daemon

Usage:
  algenta-runtime-daemon [start]    Run the daemon in the foreground (blocks)
  algenta-runtime-daemon stop      Stop a running daemon (SIGTERM via pid file)
  algenta-runtime-daemon status    Report daemon / socket status
  algenta-runtime-daemon --version Print the daemon version
  algenta-runtime-daemon --help    Show this help

Environment:
  ALGENTA_RUNTIME_DIR    Runtime state dir (default: ~/.algenta/runtime)
  ALGENTA_NATIVE_WORKER  Runtime worker executable
                         (default: the bundle's engine/ default shard worker)
  ALGENTA_MOJO_SOCK      Mojo worker unix socket path
  ALGENTA_DAEMON_SOCK    gRPC daemon unix socket path
  ALGENTA_DAEMON_TCP     gRPC TCP loopback address (default: 127.0.0.1:50099)
"""


def _bundle_root() -> Path | None:
    """The extracted bundle root (parent of daemon/) when running frozen."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent.parent


def _default_worker_from_shard_map(engine_dir: Path) -> Path | None:
    """The shard map's default worker binary, if the bundle carries a shard map."""
    shard_map = engine_dir / "runtime-shards.json"
    if shard_map.is_file():
        try:
            payload = json.loads(shard_map.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            default_worker = payload.get("default_worker")
            if isinstance(default_worker, str) and default_worker:
                candidate = engine_dir / default_worker
                if candidate.exists():
                    return candidate
    fallback = engine_dir / "algenta-runtime-worker"
    return fallback if fallback.exists() else None


def _default_bundle_worker() -> None:
    """Point the daemon at the bundle's own default shard worker unless overridden."""
    if (
        os.environ.get("ALGENTA_NATIVE_WORKER")
        or os.environ.get("ALGENTA_RUNTIME_WORKER")
        or os.environ.get("ALGENTA_MOJO_BINARY")
    ):
        return
    root = _bundle_root()
    if root is None:
        return
    worker = _default_worker_from_shard_map(root / "engine")
    if worker is not None:
        os.environ["ALGENTA_NATIVE_WORKER"] = str(worker)


def main() -> int:
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv or "help" in argv:
        sys.stdout.write(_USAGE)
        return 0
    if "--version" in argv or "version" in argv:
        sys.stdout.write(f"algenta-runtime-daemon {_VERSION}\n")
        return 0

    # Must happen BEFORE importing apps.runtime.daemon — it resolves the worker
    # at module import time.
    _default_bundle_worker()

    from apps.runtime import daemon

    cmd = argv[0] if argv else "start"
    if cmd == "start":
        daemon.cmd_start(foreground=True)
    elif cmd == "stop":
        daemon.cmd_stop()
    elif cmd == "status":
        daemon.cmd_status()
    else:
        sys.stderr.write(f"Unknown command: {cmd}. Use: start | stop | status | --help\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
