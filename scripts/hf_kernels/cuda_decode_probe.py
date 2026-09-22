#!/usr/bin/env python3
"""Drive a resident Qwen3 decode session through the in-process C ABI on an NVIDIA host, exactly as
the published Python `DecodeSession` does, and compare the greedy tokens to a reference.

This is the HF-path CUDA execution proof: it loads the built `_native` closure by hand (bypassing
the `kernels` loader, which needs a CUDA build of PyTorch to pick the variant), selects the library
for the device's compute capability, and runs qwen3_decode_open/next*/close over the ABI.

    scripts/hf_kernels/cuda_decode_probe.py --native <dir>/_native --checkpoint <converted> --prompt-ids 785 ... --expect 279 ... --out probe.json
"""
from __future__ import annotations

import argparse
import ctypes
import json
import time
from pathlib import Path


def _cuda_cc() -> tuple[int, int]:
    cuda = None
    for name in ("libcuda.so.1", "libcuda.so"):
        try:
            cuda = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if cuda is None:
        raise SystemExit("libcuda.so.1 not found (need the NVIDIA driver)")
    cuda.cuInit(0)
    dev = ctypes.c_int(0)
    cuda.cuDeviceGet(ctypes.byref(dev), 0)
    major, minor = ctypes.c_int(0), ctypes.c_int(0)
    cuda.cuDeviceGetAttribute(ctypes.byref(major), 75, dev)
    cuda.cuDeviceGetAttribute(ctypes.byref(minor), 76, dev)
    name = ctypes.create_string_buffer(128)
    cuda.cuDeviceGetName(name, 128, dev)
    return major.value, minor.value, name.value.decode("utf-8", "ignore")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True, type=Path)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--prompt-ids", nargs="+", type=int, required=True)
    ap.add_argument("--max-new-tokens", type=int, default=8)
    ap.add_argument("--expect", nargs="*", type=int)
    ap.add_argument("--out")
    a = ap.parse_args()
    manifest = json.loads((a.native / "manifest.json").read_text())
    major, minor, dev_name = _cuda_cc()
    libs = manifest.get("cuda_libraries") or {}
    exact = f"sm_{major}{minor}"
    chosen = libs.get(exact)
    if chosen is None:
        same = sorted(int(t[3:]) for t in libs if t[3:].isdigit() and int(t[3:]) // 10 == major and int(t[3:]) <= major * 10 + minor)
        chosen = libs[f"sm_{same[-1]}"] if same else manifest["library"]
    print(f"device: {dev_name} (cc {major}.{minor}); selected {chosen}")
    for name in manifest["load_order"]:
        ctypes.CDLL(str(a.native / name))
    lib = ctypes.CDLL(str(a.native / chosen))
    lib.algenta_runtime_init.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_init.restype = ctypes.c_void_p
    lib.algenta_runtime_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; lib.algenta_runtime_execute.restype = ctypes.c_void_p
    lib.algenta_runtime_free.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_free.restype = None
    lib.algenta_runtime_shutdown.argtypes = [ctypes.c_void_p]; lib.algenta_runtime_shutdown.restype = None

    def call(handle, req):
        p = lib.algenta_runtime_execute(handle, json.dumps(req).encode())
        r = json.loads(ctypes.string_at(p)); lib.algenta_runtime_free(p); return r

    h = lib.algenta_runtime_init(b"{}")
    t0 = time.time()
    opened = call(h, {"type": "qwen3_decode_open", "checkpoint_dir": a.checkpoint, "prompt_token_ids": a.prompt_ids, "max_new_tokens": a.max_new_tokens})
    if "session" not in opened:
        print("OPEN FAILED:", json.dumps(opened)); return 1
    session = opened["session"]
    tokens, steps = [], []
    for _ in range(a.max_new_tokens):
        r = call(h, {"type": "qwen3_decode_next", "session": session})
        if "token_id" not in r:
            print("NEXT FAILED:", json.dumps(r)); break
        tokens.append(r["token_id"]); steps.append(r)
        if r.get("done"):
            break
    call(h, {"type": "qwen3_decode_close", "session": session})
    lib.algenta_runtime_shutdown(h)
    elapsed = time.time() - t0
    ok = (tokens == a.expect) if a.expect else bool(tokens)
    result = {"device": dev_name, "compute_capability": f"{major}.{minor}", "library": chosen, "tokens": tokens,
              "expected": a.expect, "match": ok, "seconds": round(elapsed, 2), "n_prompt": opened.get("n_prompt")}
    print(("PASS" if ok else "FAIL"), "CUDA decode tokens:", tokens, f"({elapsed:.1f}s)")
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
