#!/usr/bin/env python3
"""Adversarial + lifecycle probe for an Algenta HF-kernel shared library (ABI v1).

Every corpus case runs in its OWN subprocess so a native abort is contained and recorded as an
outcome instead of killing the probe. Cases are tagged `supported` (ABI.md §5.1: must yield an
envelope, never abort) or `undefined` (§5.2: behaviour is only documented).

Usage: abi_probe.py --lib PATH [--rss-calls N] [--out results.json]
Set DYLD_LIBRARY_PATH / LD_LIBRARY_PATH to the Mojo runtime closure when the library is not yet
staged with @loader_path/$ORIGIN rpaths.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import multiprocessing as mp
import os
import resource
import sys
import threading
import time

REQ = {"type": "library_execute", "module": "ab_testing", "function": "z_test_proportions", "args": [50, 1000, 65, 1000]}


def load(lib_path: str):
    lib = ctypes.CDLL(lib_path)
    lib.algenta_runtime_version.restype = ctypes.c_int32
    lib.algenta_runtime_init.argtypes = [ctypes.c_void_p]
    lib.algenta_runtime_init.restype = ctypes.c_void_p
    lib.algenta_runtime_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.algenta_runtime_execute.restype = ctypes.c_void_p  # ABI 7.1
    lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]
    lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]
    if lib.algenta_runtime_version() != 1:
        raise SystemExit("ABI version mismatch")
    return lib


def call(lib, h, payload: bytes) -> str:
    p = lib.algenta_runtime_execute(h, payload)
    if not p:
        raise MemoryError("execute returned NULL")
    try:
        return ctypes.string_at(p).decode("utf-8", "replace")
    finally:
        lib.algenta_runtime_free(p)


def j(**kw) -> bytes:
    return json.dumps({**REQ, **kw}).encode()


def corpus():
    yield "valid", "supported", j()
    yield "not-json", "supported", b"this is not json"
    yield "empty", "supported", b""
    yield "type-missing", "supported", b'{"module":"ab_testing"}'
    yield "type-undeclared", "supported", b'{"type":"dataset_open"}'
    yield "args-not-list", "supported", j(args="notalist")
    yield "args-too-few", "supported", j(args=[50])
    yield "args-too-many", "supported", j(args=[50, 1000, 65, 1000, 7, 8])
    yield "args-wrong-type", "supported", j(args=["a", "b", "c", "d"])
    yield "args-huge-number", "supported", j(args=[1e308, 1e308, 1e308, 1e308])
    yield "args-overflow-literal", "supported", b'{"type":"library_execute","module":"ab_testing","function":"z_test_proportions","args":[1e999,1,1,1]}'
    yield "args-negative", "supported", j(function="mde", args=[-1000, 0.1, 0.05, 0.8])
    yield "args-zero", "supported", j(args=[0, 0, 0, 0])
    yield "args-nested-depth-63", "supported", b'{"type":"library_execute","module":"ab_testing","function":"mde","args":' + b"[" * 61 + b"]" * 61 + b"}"
    yield "args-nested-depth-70", "supported", b'{"type":"library_execute","module":"ab_testing","function":"mde","args":' + b"[" * 68 + b"]" * 68 + b"}"
    yield "pearson-unequal-lengths", "supported", j(module="stat_tests", function="pearson_r", args=[[1.0, 2.0, 3.0, 4.0], [1.0, 2.0]])
    yield "pearson-empty-lists", "supported", j(module="stat_tests", function="pearson_r", args=[[], []])
    yield "pearson-single", "supported", j(module="stat_tests", function="pearson_r", args=[[1.0], [2.0]])
    yield "pearson-100k", "supported", j(module="stat_tests", function="pearson_r", args=[[float(i) for i in range(100000)], [float(i * 2) for i in range(100000)]])
    yield "ttest-unequal", "supported", j(module="stat_tests", function="t_test_2sample", args=[[1.0, 2.0, 3.0], [1.0]])
    yield "unicode", "supported", j(module="ab_tésting", function="ünïcode")
    yield "invalid-utf8", "supported", b'{"type":"library_execute","module":"\xff\xfe\xfd","function":"x","args":[]}'
    yield "interior-nul", "supported", b'{"type":"library_execute","module":"ab\x00_testing","function":"mde","args":[1000,0.1,0.05,0.8]}'
    yield "64MiB-no-nul", "supported", b"a" * (64 * 1024 * 1024 + 16)  # ABI 2.2: must return request_too_large without copying
    yield "1MiB-garbage", "supported", os.urandom(1024 * 1024).replace(b"\x00", b"\x01")


def run_case(lib_path: str, payload: bytes) -> str:
    lib = load(lib_path)
    h = lib.algenta_runtime_init(b"{}")
    assert h
    t0 = time.perf_counter()
    out = call(lib, h, payload)
    dt = time.perf_counter() - t0
    lib.algenta_runtime_shutdown(h)
    return json.dumps({"ms": round(dt * 1000, 3), "response": out[:400]})


def run_lifecycle(lib_path: str, rss_calls: int) -> str:
    lib = load(lib_path)
    h = lib.algenta_runtime_init(b"{}")
    lib.algenta_runtime_free(None)
    lib.algenta_runtime_shutdown(None)
    for _ in range(200):
        call(lib, h, j())
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t0 = time.perf_counter()
    for _ in range(rss_calls):
        call(lib, h, j())
    dt = time.perf_counter() - t0
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ABI 6.1: distinct threads on ONE handle without the wrapper lock — documents raw behaviour.
    errors: list[str] = []
    results: list[str] = []
    def worker():
        try:
            for _ in range(500):
                results.append(call(lib, h, j()))
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    distinct = len(set(results))
    h2 = lib.algenta_runtime_init(None)  # NULL config is supported
    r2 = call(lib, h2, j())
    lib.algenta_runtime_shutdown(h2)
    lib.algenta_runtime_shutdown(h)
    return json.dumps({"calls": rss_calls, "seconds": round(dt, 3), "us_per_call": round(dt / rss_calls * 1e6, 1),
                       "maxrss_before_kb": rss0, "maxrss_after_kb": rss1, "rss_growth_kb": rss1 - rss0,
                       "threads8x500_errors": errors, "threads8x500_distinct_responses": distinct, "null_config_init": r2[:80]})


def run_undefined(lib_path: str, case: str) -> str:
    lib = load(lib_path)
    h = lib.algenta_runtime_init(b"{}")
    if case == "double-shutdown":
        lib.algenta_runtime_shutdown(h); lib.algenta_runtime_shutdown(h)
    elif case == "double-free":
        p = lib.algenta_runtime_execute(h, j()); lib.algenta_runtime_free(p); lib.algenta_runtime_free(p)
    elif case == "execute-after-shutdown":
        lib.algenta_runtime_shutdown(h); return call(lib, h, j())[:120]
    elif case == "free-foreign-pointer":
        buf = ctypes.create_string_buffer(b"x" * 64); lib.algenta_runtime_free(ctypes.addressof(buf))
    elif case == "bogus-handle":
        return call(lib, 0xDEADBEEF, j())[:120]
    elif case == "fork-after-load":
        # ABI 4.8: fork after init is not promised. Child calls execute; parent reports the child's exit.
        pid = os.fork()
        if pid == 0:
            try:
                r = call(lib, h, j())
                os._exit(0 if "result" in r else 3)
            except Exception:  # noqa: BLE001
                os._exit(4)
        _, status = os.waitpid(pid, 0)
        return f"child exit={os.waitstatus_to_exitcode(status)} (0=execute worked in forked child)"
    elif case == "execute-during-shutdown":
        # ABI 4.8/5.2: concurrent execute and shutdown on one handle is undefined misuse; documented only.
        stop = threading.Event(); errs: list[str] = []
        def hammer():
            while not stop.is_set():
                try:
                    call(lib, h, j())
                except Exception as exc:  # noqa: BLE001
                    errs.append(repr(exc)); break
        t = threading.Thread(target=hammer); t.start(); time.sleep(0.05)
        lib.algenta_runtime_shutdown(h); stop.set(); t.join(timeout=5)
        return f"returned; thread errors={errs[:1]}"
    return "returned"


def _isolated(target, *args, timeout: float = 600.0) -> tuple[int | None, str]:
    """Run `target(*args)` in a fresh spawned process; return (exit code, captured text).

    A native abort in the child surfaces as a negative exit code here instead of killing the probe.
    """
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_child_entry, args=(queue, target.__name__, args))
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.kill(); proc.join(5)
        return None, "TIMEOUT"
    text = ""
    try:
        text = queue.get_nowait()
    except Exception:  # noqa: BLE001 - empty queue after a crash
        pass
    return proc.exitcode, text


def _child_entry(queue, target_name: str, args) -> None:
    fn = {"run_case": run_case, "run_lifecycle": run_lifecycle, "run_undefined": run_undefined}[target_name]
    try:
        queue.put(str(fn(*args)))
    except Exception as exc:  # noqa: BLE001 - reported to the parent verbatim
        queue.put(f"EXC {type(exc).__name__}: {exc}")
        raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True)
    ap.add_argument("--rss-calls", type=int, default=100000)
    ap.add_argument("--out")
    ap.add_argument("--_undefined", help="run one undefined-misuse case in this process (used by the isolated runner)")
    a = ap.parse_args()
    lib_path = os.path.realpath(a.lib)
    if a._undefined:
        print(run_undefined(lib_path, a._undefined)); return 0
    results = {"lib": lib_path, "cases": [], "lifecycle": None, "undefined": []}
    for name, klass, payload in corpus():
        rc, detail = _isolated(run_case, lib_path, payload)
        status = "ok" if rc == 0 else (f"ABORT rc={rc}" if rc is not None else "TIMEOUT")
        verdict = "PASS" if rc == 0 else ("FAIL" if klass == "supported" else "DOCUMENTED")
        results["cases"].append({"case": name, "class": klass, "status": status, "verdict": verdict, "detail": detail[:500]})
        print(f"{verdict:10} {name:26} {status:14} {detail[:150]}")
    rc, detail = _isolated(run_lifecycle, lib_path, a.rss_calls, timeout=1800)
    results["lifecycle"] = {"status": "ok" if rc == 0 else f"ABORT rc={rc}", "detail": detail[-800:]}
    print("LIFECYCLE ", results["lifecycle"])
    for case in ["double-shutdown", "double-free", "execute-after-shutdown", "free-foreign-pointer", "bogus-handle", "fork-after-load", "execute-during-shutdown"]:
        rc, detail = _isolated(run_undefined, lib_path, case, timeout=120)
        results["undefined"].append({"case": case, "status": "returned" if rc == 0 else f"ABORT rc={rc}", "detail": detail[-200:]})
        print(f"UNDEFINED  {case:26} {results['undefined'][-1]['status']:14} {results['undefined'][-1]['detail'][:120]}")
    if a.out:
        with open(a.out, "w") as f: json.dump(results, f, indent=1)
    failed = [c for c in results["cases"] if c["verdict"] == "FAIL"]
    print(f"\nsupported-space failures: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
