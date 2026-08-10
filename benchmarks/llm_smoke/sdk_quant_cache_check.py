"""sdk_quant_cache_check.py -- beat-llama.cpp campaign parity cheap win 2 (2026-08-10): the
measurement for the quantized-state cache (`weights_i8.cache`) the anyqwen3 entry point now
writes/restores. The one-shot SDK shape re-uploads weights on EVERY call (parity gap 4): read the
flat f64 blob (8 bytes/param), run the two-pass per-row quantization, fill the device buffers.
The cache persists the EXACT post-quantization device bytes (~1 byte/param + per-row Float32
scales), so the second-and-later call reads ~1/8 the bytes and quantizes nothing.

Protocol (one worker binary, one converted checkpoint per run):
  A  cold        weights_i8.cache deleted -> f64 path, cache WRITTEN at the end
  B  cached      valid cache present      -> quantized state RESTORED (no f64 read, no quantize)
  C  corrupt     cache's stored manifest SHA-256 flipped -> honest FALLBACK to the f64 path,
                  cache rewritten valid
Each leg runs the 256-token race prompt with 8 greedy tokens; every leg's token sequence must be
BYTE-IDENTICAL (the cache is the very bytes the GPU kernels read, so this is the correctness gate,
not just a nice-to-have). Wall is measured around the whole SDK call -- load + prefill + decode,
the honest one-shot shape.

Usage (repo root, GPU worker built from this tree):
  ALGENTA_RUNTIME_FALLBACK_MODE=allow \
  ALGENTA_NATIVE_WORKER=$PWD/mojo_build/gpu-worker/algenta-gpu-worker \
  python3 benchmarks/llm_smoke/sdk_quant_cache_check.py \
      --converted /tmp/qwen3smoke --checkpoint /private/tmp/qwen3-0.6b-base
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--converted", required=True, help="dir with manifest.json + weights.blob")
    ap.add_argument("--checkpoint", required=True, help="HuggingFace snapshot dir (config.json)")
    ap.add_argument("--max-new-tokens", type=int, default=8)
    args = ap.parse_args()

    converted = Path(args.converted)
    manifest = json.loads((converted / "manifest.json").read_text(encoding="utf-8"))
    prompt_ids = list(manifest["input_ids"])
    cache = converted / "weights_i8.cache"
    blob_gb = (converted / "weights.blob").stat().st_size / 1e9

    runtime = MojoRuntime(mode="local", timeout=600.0)

    def run(label: str) -> tuple[float, list[int]]:
        t0 = time.time()
        result = decode(
            runtime,
            checkpoint_dir=args.checkpoint,
            prompt_token_ids=prompt_ids,
            max_new_tokens=args.max_new_tokens,
            converted_checkpoint_dir=converted,
        )
        wall = time.time() - t0
        gen = result.token_ids[result.n_prompt :]
        print(
            f"  {label:<8} wall={wall:7.2f}s  prefill={result.prefill_tokens_per_sec:8.1f} tok/s"
            f"  decode={result.decode_tokens_per_sec:6.1f} tok/s  gen={gen}"
        )
        return wall, result.token_ids

    print(f"[check] {converted.name}: blob={blob_gb:.2f} GB, prompt={len(prompt_ids)} tokens")

    cache.unlink(missing_ok=True)
    wall_a, tokens_a = run("A cold")
    if not cache.is_file():
        print("FAIL: the f64 path did not write weights_i8.cache")
        return 1
    cache_gb = cache.stat().st_size / 1e9
    print(f"  cache written: {cache_gb:.3f} GB ({blob_gb / cache_gb:.1f}x smaller than the f64 blob)")

    wall_b, tokens_b = run("B cached")
    if tokens_b != tokens_a:
        print("FAIL: the cached path changed the greedy sequence")
        return 1

    raw = bytearray(cache.read_bytes())
    raw[10] ^= 0xFF  # flip one byte of the stored manifest SHA-256 -> gate must refuse
    cache.write_bytes(bytes(raw))
    wall_c, tokens_c = run("C fallbk")
    if tokens_c != tokens_a:
        print("FAIL: the corrupted-cache fallback changed the greedy sequence")
        return 1
    if cache.read_bytes() == bytes(raw):
        print("FAIL: the fallback left the corrupted cache in place")
        return 1

    print(
        f"PASS: byte-identical greedy tokens on all three legs; cold {wall_a:.2f}s ->"
        f" cached {wall_b:.2f}s ({wall_a / wall_b:.2f}x wall), corrupt-cache fallback honest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
