#!/usr/bin/env python3
"""Stage 2 coexistence probe: several HF-kernel family libraries in ONE Python process.

Answers, with recorded evidence: do two families load in both orders; do overlapping calls from
threads across families (and across two handles / two loaded revisions) return correct results;
does each family bind its own copy of the Mojo runtime closure (runtime identity); what happens on
cross-instance free (undefined misuse, isolated). Each scenario runs in its own spawned process.

Usage: coexistence_probe.py --lib A.dylib --lib B.dylib [--lib A-copy.dylib ...] --out results.json
"""
from __future__ import annotations

import argparse
import ctypes
import json
import multiprocessing as mp
import os
import sys
import threading
import time

REQS = {
    "stats": {"type": "library_execute", "module": "ab_testing", "function": "z_test_proportions", "args": [50, 1000, 65, 1000]},
    "ml": None,  # filled from --probe module:function:args-json
}


def load(path: str):
    lib = ctypes.CDLL(path)
    lib.algenta_runtime_version.restype = ctypes.c_int32
    lib.algenta_runtime_init.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_init.restype = ctypes.c_void_p
    lib.algenta_runtime_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; lib.algenta_runtime_execute.restype = ctypes.c_void_p
    lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]
    assert lib.algenta_runtime_version() == 1
    return lib


def call(lib, h, req) -> str:
    p = lib.algenta_runtime_execute(h, json.dumps(req).encode())
    if not p:
        raise MemoryError
    try:
        return ctypes.string_at(p).decode()
    finally:
        lib.algenta_runtime_free(p)


def scenario(args) -> dict:
    libs_spec = [json.loads(s) for s in args.libs]  # [{"path":..., "req":{...}, "expect":"..."}]
    order = [int(i) for i in args.order.split(",")]
    out = {"order": order, "loaded": [], "results": {}, "threads": None, "identity": None}
    handles = []
    for i in order:
        spec = libs_spec[i]
        lib = load(spec["path"])
        h = lib.algenta_runtime_init(b"{}")
        handles.append((i, lib, h))
        out["loaded"].append(os.path.basename(spec["path"]))
    for i, lib, h in handles:
        out["results"][str(i)] = call(lib, h, libs_spec[i]["req"])
    if args.threads:
        errors, bad = [], []
        def worker(i, lib, h, n):
            try:
                for _ in range(n):
                    r = call(lib, h, libs_spec[i]["req"])
                    if json.loads(r) != json.loads(libs_spec[i].get("expect") or out["results"][str(i)]):
                        bad.append((i, r[:100]))
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))
        ts = []
        for i, lib, h in handles:
            for _ in range(args.threads):
                ts.append(threading.Thread(target=worker, args=(i, lib, h, args.calls)))
        t0 = time.perf_counter()
        for t in ts: t.start()
        for t in ts: t.join()
        out["threads"] = {"threads_per_lib": args.threads, "calls_per_thread": args.calls, "seconds": round(time.perf_counter() - t0, 3), "errors": errors, "mismatches": bad[:5], "mismatch_count": len(bad)}
    if args.identity:
        # Which copies of the Mojo runtime are mapped? (dyld image list via _dyld_get_image_name)
        libsys = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        libsys._dyld_image_count.restype = ctypes.c_uint32
        libsys._dyld_get_image_name.argtypes = [ctypes.c_uint32]; libsys._dyld_get_image_name.restype = ctypes.c_char_p
        names = [libsys._dyld_get_image_name(k).decode() for k in range(libsys._dyld_image_count())]
        out["identity"] = sorted(n for n in names if any(t in n for t in ("KGENCompilerRT", "AsyncRT", "MSupport", "libalgenta_")))
    for i, lib, h in handles:
        lib.algenta_runtime_shutdown(h)
    return out


def undefined_cross_free(args) -> str:
    a, b = [json.loads(s) for s in args.libs][:2]
    la, lb = load(a["path"]), load(b["path"])
    ha = la.algenta_runtime_init(b"{}")
    p = la.algenta_runtime_execute(ha, json.dumps(a["req"]).encode())
    lb.algenta_runtime_free(p)  # ABI 4.2: cross-instance free is undefined misuse
    return "returned"


class _Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _child(queue, kind: str, kw: dict) -> None:
    try:
        if kind == "scenario":
            queue.put(json.dumps(scenario(_Args(**kw))))
        else:
            queue.put(undefined_cross_free(_Args(**kw)))
    except Exception as exc:  # noqa: BLE001 - reported verbatim
        queue.put(f"EXC {type(exc).__name__}: {exc}")
        raise SystemExit(2)


def _isolated(kind: str, timeout: float, **kw) -> tuple[int | None, str]:
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_child, args=(queue, kind, kw))
    proc.start(); proc.join(timeout)
    if proc.is_alive():
        proc.kill(); proc.join(5); return None, "TIMEOUT"
    try:
        return proc.exitcode, queue.get_nowait()
    except Exception:  # noqa: BLE001
        return proc.exitcode, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--libs", action="append", default=[], help='JSON {"path","req","expect"} per library')
    ap.add_argument("--calls", type=int, default=200)
    ap.add_argument("--out")
    a = ap.parse_args()
    libs = a.libs
    n = len(libs)
    results = {"libs": [json.loads(s)["path"] for s in libs], "scenarios": []}
    orders = [",".join(map(str, range(n))), ",".join(map(str, reversed(range(n))))]
    for order in orders:
        for threads in (0, 8):
            rc, out = _isolated("scenario", 1800, libs=libs, order=order, threads=threads, calls=a.calls, identity=True)
            entry = {"order": order, "threads": threads, "rc": rc, "out": json.loads(out) if rc == 0 and out.startswith("{") else out[-400:]}
            results["scenarios"].append(entry)
            summary = entry["out"] if isinstance(entry["out"], str) else {k: entry["out"][k] for k in ("loaded", "threads")} | {"identity_count": len(entry["out"]["identity"] or [])}
            print(f"order={order} threads={threads} rc={rc} {json.dumps(summary)[:300]}")
    rc, out = _isolated("cross_free", 300, libs=libs)
    results["undefined_cross_free"] = {"rc": rc, "detail": out[-200:]}
    print("UNDEFINED cross-instance free:", results["undefined_cross_free"])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
