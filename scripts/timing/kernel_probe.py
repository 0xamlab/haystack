#!/usr/bin/env python3
"""Probe kernels through the real worker transport: framed JSON over a Unix socket.

Note on why this exists rather than piping to stdin: ``library_execute`` is routed only inside the
server loop (``mojo/engine/main.mojo``). Subprocess/stdin mode falls straight through to ``_run_raw``,
the simulation-engine path, so a library call piped to stdin silently returns a monte_carlo envelope
instead of an error. Server mode is also the production path -- the worker pool spawns
``simulate --server <sock>`` -- so probing this way exercises what actually ships.

Wire protocol: [4-byte big-endian length][UTF-8 JSON]. The worker sends {"status":"ready"} on connect.

Usage:
    python3 scripts/timing/kernel_probe.py --binary mojo_build/simulate_timing
    python3 scripts/timing/kernel_probe.py --binary ... --module counter_rng --function rng_version
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class Worker:
    def __init__(self, binary: Path) -> None:
        self._dir = tempfile.mkdtemp(prefix="algenta-kernel-probe-")
        self.sock_path = os.path.join(self._dir, "w.sock")
        # Gate 0 item 7: fallback denial, pinned on EVERY worker rather than assumed from the shell.
        # A Python fallback that answers a kernel call returns plausible numbers and invalidates every
        # speed and determinism claim without raising, so it must be impossible rather than unlikely.
        env = dict(os.environ)
        env["RUNTIME_FALLBACK_MODE"] = "deny"
        env["MOJO_ALLOW_SUBPROCESS_FALLBACK"] = "false"
        self.proc = subprocess.Popen(
            [str(binary), "--server", self.sock_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if os.path.exists(self.sock_path):
                break
            if self.proc.poll() is not None:
                err = (self.proc.stderr.read() or b"").decode()[-800:]
                raise RuntimeError(f"worker exited early: {err}")
            time.sleep(0.05)
        else:
            raise RuntimeError("worker socket never appeared")
        self.conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.conn.settimeout(60)
        self.conn.connect(self.sock_path)
        hello = json.loads(self._recv())
        if hello.get("status") != "ready":
            raise RuntimeError(f"unexpected handshake: {hello}")

    def _recv(self) -> bytes:
        head = self._recv_exact(4)
        (n,) = struct.unpack(">I", head)
        return self._recv_exact(n)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.conn.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("worker closed the connection")
            buf += chunk
        return buf

    def call(self, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        self.conn.sendall(struct.pack(">I", len(data)) + data)
        return json.loads(self._recv())

    def execute(self, module: str, function: str, args: list | None = None) -> dict:
        return self.call({
            "type": "library_execute",
            "engine_type": "library_execute",
            "module": module,
            "function": function,
            "args": args if args is not None else [],
        })

    def close(self) -> None:
        try:
            self.call({"type": "shutdown"})
        except Exception:
            pass
        try:
            self.conn.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# (module, function, args, expectation) — expectations are the values validated in
# scripts/timing/validate_rng.py and mojo/tests/libs/test_counter_rng.mojo
PROBES = [
    ("counter_rng", "rng_version", [], "philox4x64-10/v1"),
    ("counter_rng", "rng_global_sentinel", [], 65535),
    ("counter_rng", "rng_selftest", [], 13066461341573311292),
    ("counter_rng", "philox_word", [1, 2, 3, 4, 5, 4, 0], 5544217767837969664),
    ("counter_rng", "philox_word", [1, 2, 3, 4, 5, 4, 7], 8147541987183208929),
    ("counter_rng", "rng_uniform", [11, 22, 0, 4, 5, 4, 0], None),
    ("counter_rng", "rng_normal", [11, 22, 0, 4, 5, 4, 0], None),
    ("counter_rng", "rng_exponential", [11, 22, 0, 4, 5, 5, 0, 0.4166666666666667], None),
    ("linear_models", "logistic_fit", [[0.0, 1.0, 2.0, 3.0], [0, 0, 1, 1], 1, 50, 0.1], None),
    ("calibration", "platt_fit", [[0.1, 0.4, 0.6, 0.9], [0, 0, 1, 1], 50], None),
    ("model_compare", "diebold_mariano", [[0.1, 0.2, 0.15], [0.2, 0.3, 0.25], 1], None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--module")
    ap.add_argument("--function")
    ap.add_argument("--args", default="[]")
    args = ap.parse_args()

    binary = Path(args.binary)
    if not binary.exists():
        print(f"binary not found: {binary}", file=sys.stderr)
        return 2

    w = Worker(binary)
    try:
        if args.module and args.function:
            print(json.dumps(w.execute(args.module, args.function, json.loads(args.args)), indent=2))
            return 0

        failures = 0
        print(f"kernel dispatch probe — {binary}\n")
        for module, function, argv, expect in PROBES:
            resp = w.execute(module, function, argv)
            if "error" in resp:
                print(f"  FAIL {module}.{function}: {resp['error']}")
                failures += 1
                continue
            got = resp.get("result")
            if expect is not None and got != expect:
                print(f"  FAIL {module}.{function}: got {got!r} want {expect!r}")
                failures += 1
                continue
            shown = json.dumps(got)
            print(f"  ok   {module + '.' + function:<34} {shown[:74]}")
        print(f"\n{len(PROBES) - failures}/{len(PROBES)} probes passed")
        return 1 if failures else 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
