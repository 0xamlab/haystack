#!/usr/bin/env python3
"""Stage 2b probe: an accelerator-backed Qwen3 decode session through the in-process ABI, compared
with the same session driven through the shipped runtime worker (Unix-socket protocol).

ABI path: init -> qwen3_decode_open -> qwen3_decode_next (until done or --max-new-tokens) ->
qwen3_decode_close -> shutdown. Worker path: identical requests over the worker's frame protocol.
Pass criteria (SESSION_API.md): same token ids in the same order; every `next` returns only after
its token exists (synchronous completion); close releases the session (a second close ->
qwen3_session_not_found); shutdown with an open session does not crash.

Usage: session_probe.py --lib libalgenta_algenta_llm.dylib --checkpoint <converted dir> \
          --prompt-ids 785 3974 13876 --max-new-tokens 8 [--worker <algenta-runtime-worker>] [--out r.json]
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time


def load(path: str):
    lib = ctypes.CDLL(path)
    lib.algenta_runtime_version.restype = ctypes.c_int32
    lib.algenta_runtime_init.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_init.restype = ctypes.c_void_p
    lib.algenta_runtime_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; lib.algenta_runtime_execute.restype = ctypes.c_void_p
    lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]
    assert lib.algenta_runtime_version() == 1
    return lib


def abi_call(lib, h, req) -> dict:
    p = lib.algenta_runtime_execute(h, json.dumps(req).encode())
    if not p:
        raise MemoryError
    try:
        return json.loads(ctypes.string_at(p).decode())
    finally:
        lib.algenta_runtime_free(p)


def drive(send, checkpoint: str, prompt_ids: list[int], max_new: int) -> dict:
    out = {"open": None, "steps": [], "close": None, "close_again": None}
    t0 = time.perf_counter()
    r = send({"type": "qwen3_decode_open", "checkpoint_dir": checkpoint, "prompt_token_ids": prompt_ids, "max_new_tokens": max_new})
    out["open"] = {"ms": round((time.perf_counter() - t0) * 1000, 1), "response": r}
    handle = r.get("session")
    if not handle:
        return out
    for _ in range(max_new + 1):
        t1 = time.perf_counter()
        r = send({"type": "qwen3_decode_next", "session": handle})
        out["steps"].append({"ms": round((time.perf_counter() - t1) * 1000, 2), "token_id": r.get("token_id"), "position": r.get("position"), "done": r.get("done"), "error_code": r.get("error_code")})
        if r.get("done") or r.get("error_code"):
            break
    out["close"] = send({"type": "qwen3_decode_close", "session": handle})
    out["close_again"] = send({"type": "qwen3_decode_close", "session": handle})
    return out


def worker_sender(binary: str, pythonhome: str | None):
    sock_path = os.path.join(tempfile.mkdtemp(prefix="hfk-ref-"), "w.sock")
    env = os.environ.copy()
    if pythonhome:
        env["PYTHONHOME"] = pythonhome
    proc = subprocess.Popen([binary, "--server", sock_path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    for _ in range(400):
        if os.path.exists(sock_path) or proc.poll() is not None:
            break
        time.sleep(0.05)
    if proc.poll() is not None:
        raise SystemExit("worker exited early: " + proc.stderr.read().decode()[-300:])
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(600); s.connect(sock_path)
    def recv():
        hdr = b""
        while len(hdr) < 4: hdr += s.recv(4 - len(hdr))
        n = struct.unpack(">I", hdr)[0]; body = b""
        while len(body) < n: body += s.recv(n - len(body))
        return body.decode()
    recv()  # ready frame
    def send(req):
        data = json.dumps(req).encode(); s.sendall(struct.pack(">I", len(data)) + data)
        return json.loads(recv())
    return send, proc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True); ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--prompt-ids", nargs="+", type=int, required=True); ap.add_argument("--max-new-tokens", type=int, default=8)
    ap.add_argument("--worker"); ap.add_argument("--pythonhome"); ap.add_argument("--out")
    a = ap.parse_args()
    results = {"lib": a.lib, "checkpoint": a.checkpoint, "prompt_ids": a.prompt_ids}
    lib = load(a.lib)
    h = lib.algenta_runtime_init(b"{}")
    results["abi"] = drive(lambda r: abi_call(lib, h, r), a.checkpoint, a.prompt_ids, a.max_new_tokens)
    # shutdown-with-open-session: open again, then shutdown without closing (ABI 4.7 must not crash)
    r = abi_call(lib, h, {"type": "qwen3_decode_open", "checkpoint_dir": a.checkpoint, "prompt_token_ids": a.prompt_ids, "max_new_tokens": 2})
    results["abi"]["reopen_then_shutdown"] = {"reopened": bool(r.get("session")), "error_code": r.get("error_code")}
    lib.algenta_runtime_shutdown(h)
    results["abi"]["reopen_then_shutdown"]["shutdown"] = "returned"
    abi_tokens = [s["token_id"] for s in results["abi"]["steps"]]
    print("ABI   open:", json.dumps(results["abi"]["open"])[:160])
    print("ABI   tokens:", abi_tokens, "step ms:", [s["ms"] for s in results["abi"]["steps"]])
    print("ABI   close:", json.dumps(results["abi"]["close"])[:100], "| close again:", json.dumps(results["abi"]["close_again"])[:80])
    if a.worker:
        send, proc = worker_sender(a.worker, a.pythonhome)
        try:
            results["worker"] = drive(send, a.checkpoint, a.prompt_ids, a.max_new_tokens)
        finally:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass  # never mask the exception that is already propagating
        w_tokens = [s["token_id"] for s in results["worker"]["steps"]]
        print("WORKER open:", json.dumps(results["worker"]["open"])[:160])
        print("WORKER tokens:", w_tokens, "step ms:", [s["ms"] for s in results["worker"]["steps"]])
        abi_ok = bool(results["abi"]["open"]["response"].get("session")) and bool(abi_tokens)
        w_ok = bool(results["worker"]["open"]["response"].get("session")) and bool(w_tokens)
        results["parity"] = {"abi_session_opened": abi_ok, "worker_session_opened": w_ok,
                             "same_tokens": abi_ok and w_ok and abi_tokens == w_tokens, "abi": abi_tokens, "worker": w_tokens}
        print("PARITY:", "PASS" if results["parity"]["same_tokens"] else "FAIL", json.dumps({k: v for k, v in results["parity"].items() if k != "same_tokens"})[:200])
    if a.out:
        json.dump(results, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
