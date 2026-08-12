"""load_test_3way.py -- enterprise load comparison across the three Apple-Silicon engines
(beat-llama.cpp campaign, 2026-08-10): Algenta (int8 Metal) vs llama.cpp F16 vs MLX-LM bf16.

Runs the SAME large-token stress matrix through all three engines on identical prompts (the prompt
BYTES are shared, and every engine uses the Qwen3 tokenizer, so token counts match), greedy, each
engine resident/warm. Reports prefill and decode throughput per engine per cell, plus a head-to-head
table. This is the cross-engine companion to `load_test.py` (the Algenta-only harness, which also
carries the concurrent-request lane).

Engines and precisions (stated, not smoothed over -- this is how each engine actually ships):
  * Algenta   int8 weights (the engine's native quantized format) -> MojoRuntime -> Metal.
  * llama.cpp F16 GGUF, resident `llama-server`, /completion HTTP.
  * MLX-LM    bf16 HF checkpoint, resident model in its own venv (load_test_mlx_worker.py).

Method: `passes` passes with ROTATING engine order (so no engine always rides the same DVFS/thermal
slot); each pass runs the full matrix once per engine (n_timed=1 per pass), results pooled per
(engine, cell) and reported as median. Prompt construction is whole-unit (no mid-token truncation),
so all three engines see byte-identical prompts.

Usage (repo root):
  python3 benchmarks/llm_smoke/load_test_3way.py \
      --checkpoint /private/tmp/qwen3-0.6b-base \
      --gguf /tmp/qwen3-0.6b-base-f16.gguf \
      --in-sizes 1024,4096,8192 --out-fixed 512 \
      --out-sizes 512,2048,4096 --in-fixed 1024 \
      --passes 2 --out /tmp/load_3way.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta import MojoRuntime  # noqa: E402
from algenta.inference import decode  # noqa: E402
from algenta.tokenizer import load_tokenizer  # noqa: E402

PROMPT_UNIT = "The capital of France is Paris. The largest planet in the solar system is Jupiter. "
PROMPT_TAIL = "The capital of France"
LLAMA_PORT = 8199
LLAMA_NGL = 99
MLX_PY = "/tmp/mlm_venv/bin/python"
MLX_WORKER = str(ROOT / "benchmarks" / "llm_smoke" / "load_test_mlx_worker.py")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def build_prompt_text(target_tokens: int, tokenizer) -> tuple[str, int]:
    """Whole-unit prompt of >= target_tokens; returns (text, actual_token_count)."""
    k = 1
    while True:
        text = PROMPT_UNIT * k + PROMPT_TAIL
        n = len(tokenizer.encode(text))
        if n >= target_tokens:
            return text, n
        k += 1


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def start_llama_server(gguf: str, port: int, ctx: int):
    proc = subprocess.Popen(
        ["llama-server", "-m", gguf, "--port", str(port), "-ngl", str(LLAMA_NGL),
         "-c", str(ctx), "--no-webui"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return proc
        except Exception:
            time.sleep(0.25)
    proc.terminate()
    raise RuntimeError("llama-server did not become healthy within 60 s")


def stop_llama_server(proc) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def llama_completion(port: int, prompt_text: str, n_predict: int) -> dict:
    body = json.dumps({
        "prompt": prompt_text, "n_predict": n_predict,
        "temperature": 0, "top_k": 1, "cache_prompt": False,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def run_algenta(cells, runtime, tokenizer, checkpoint: str) -> list[dict]:
    out = []
    for cell in cells:
        prompt_ids = tokenizer.encode(cell["prompt"])
        wall, result = 0.0, None
        t0 = time.time()
        result = decode(
            runtime, checkpoint_dir=checkpoint,
            prompt_token_ids=prompt_ids, max_new_tokens=cell["out"],
        )
        wall = time.time() - t0
        out.append({
            "cell": cell["idx"], "in": cell["in"], "out": cell["out"],
            "prefill_tok_s": result.prefill_tokens_per_sec,
            "decode_tok_s": result.decode_tokens_per_sec,
            "wall_s": wall, "n_prompt": result.n_prompt,
        })
    return out


def run_llama(cells, port: int) -> list[dict]:
    out = []
    for cell in cells:
        d = llama_completion(port, cell["prompt"], cell["out"])
        t = d.get("timings", {})
        out.append({
            "cell": cell["idx"], "in": cell["in"], "out": cell["out"],
            "prefill_tok_s": float(t.get("prompt_per_second", 0.0)),
            "decode_tok_s": float(t.get("predicted_per_second", 0.0)),
            "wall_s": (float(t.get("prompt_ms", 0)) + float(t.get("predicted_ms", 0))) / 1000.0,
            "n_prompt": int(t.get("prompt_n", 0)),
        })
    return out


def run_mlx(cells, checkpoint: str) -> list[dict]:
    spec = {
        "checkpoint": checkpoint, "n_timed": 1, "n_warmup": 1,
        "cells": [{"prompt": cell["prompt"], "out": cell["out"]} for cell in cells],
    }
    spec_path = "/tmp/load_3way_mlx_spec.json"
    Path(spec_path).write_text(json.dumps(spec), encoding="utf-8")
    r = subprocess.run(
        [MLX_PY, MLX_WORKER, spec_path], capture_output=True, text=True, timeout=1800
    )
    if r.returncode != 0:
        raise RuntimeError(f"mlx worker failed: {r.stdout[-400:]} {r.stderr[-400:]}")
    out = []
    pat = re.compile(
        r"mlx_load_run: cell= (\d+) out= (\d+) run= \d+ prompt_tokens= (\d+) "
        r"gen_tokens= (\d+) prompt_tps= ([0-9.]+) gen_tps= ([0-9.]+)"
    )
    for line in r.stdout.splitlines():
        m = pat.search(line)
        if m:
            idx = int(m.group(1))
            out.append({
                "cell": idx, "in": cells[idx]["in"], "out": int(m.group(2)),
                "prefill_tok_s": float(m.group(5)),
                "decode_tok_s": float(m.group(6)),
                "wall_s": 0.0, "n_prompt": int(m.group(3)),
            })
    return out


def build_cells(args, tokenizer) -> list[dict]:
    seen = set()
    cells = []
    for in_t in args.in_sizes:
        cells.append((in_t, args.out_fixed))
    for out_t in args.out_sizes:
        cells.append((args.in_fixed, out_t))
    uniq = []
    for c in cells:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    built = []
    for idx, (in_t, out_t) in enumerate(uniq):
        text, actual = build_prompt_text(in_t, tokenizer)
        built.append({"idx": idx, "in": actual, "in_target": in_t, "out": out_t, "prompt": text})
    return built


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--in-sizes", default="1024,4096,8192")
    ap.add_argument("--out-fixed", type=int, default=512)
    ap.add_argument("--out-sizes", default="512,2048,4096")
    ap.add_argument("--in-fixed", type=int, default=1024)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--engine-cooldown", type=float, default=0.0,
                    help="idle seconds before EACH engine's run (DVFS-controlled protocol: "
                         "decouples engines from each other's heat; 0 = legacy behavior)")
    ap.add_argument("--llama-ctx", type=int, default=12288)
    ap.add_argument("--out", default="/tmp/load_3way.json")
    args = ap.parse_args()

    args.in_sizes = [int(x) for x in args.in_sizes.split(",") if x.strip()]
    args.out_sizes = [int(x) for x in args.out_sizes.split(",") if x.strip()]

    tokenizer = load_tokenizer(args.checkpoint)
    cells = build_cells(args, tokenizer)
    log(f"cells: {[(c['in'], c['out']) for c in cells]}")

    # Warm the Algenta resident session once (weights load) before timing.
    runtime = MojoRuntime(mode="local", timeout=900.0)
    decode(
        runtime, checkpoint_dir=args.checkpoint,
        prompt_token_ids=tokenizer.encode(PROMPT_UNIT + PROMPT_TAIL), max_new_tokens=4,
    )

    log("starting llama-server ...")
    llama = start_llama_server(args.gguf, LLAMA_PORT, args.llama_ctx)
    log("llama-server healthy")

    engines = ["algenta", "llama.cpp", "mlx-lm"]
    collected = {e: [] for e in engines}
    try:
        for p in range(args.passes):
            order = engines[p % 3:] + engines[:p % 3]
            log(f"--- pass {p + 1}/{args.passes}: order = {order}")
            for eng in order:
                if args.engine_cooldown > 0:
                    log(f"    idle cooldown {args.engine_cooldown:.0f}s before {eng} ...")
                    time.sleep(args.engine_cooldown)
                if eng == "algenta":
                    # Warm the session on this pass's largest cell once (untimed) is already done
                    # globally; just time the matrix.
                    collected[eng] += run_algenta(cells, runtime, tokenizer, args.checkpoint)
                elif eng == "llama.cpp":
                    collected[eng] += run_llama(cells, LLAMA_PORT)
                elif eng == "mlx-lm":
                    collected[eng] += run_mlx(cells, args.checkpoint)
    finally:
        stop_llama_server(llama)

    # Aggregate per (engine, cell).
    results = {}
    for eng in engines:
        results[eng] = []
        for cell in cells:
            rows = [r for r in collected[eng] if r["cell"] == cell["idx"]]
            if not rows:
                continue
            pf = sorted(r["prefill_tok_s"] for r in rows)
            dc = sorted(r["decode_tok_s"] for r in rows)
            results[eng].append({
                "in": cell["in"], "out": cell["out"], "runs": len(rows),
                "prefill_tok_s_median": percentile(pf, 50),
                "decode_tok_s_median": percentile(dc, 50),
            })

    # Head-to-head table.
    log("=== HEAD-TO-HEAD (median tok/s) ===")
    log(f"{'in':>6} {'out':>6} | {'Algenta pf/dc':>18} | {'llama.cpp pf/dc':>18} "
        f"| {'MLX pf/dc':>18}")
    for cell in cells:
        row = {}
        for eng in engines:
            match = [r for r in results[eng]
                     if r["in"] == cell["in"] and r["out"] == cell["out"]]
            row[eng] = match[0] if match else None

        def fmt(e, _row=row):
            r = _row[e]
            if not r:
                return "        n/a       "
            return f"{r['prefill_tok_s_median']:7.0f}/{r['decode_tok_s_median']:6.0f}"

        log(f"{cell['in']:>6} {cell['out']:>6} | {fmt('algenta'):>18} | "
            f"{fmt('llama.cpp'):>18} | {fmt('mlx-lm'):>18}")

    report = {
        "config": {
            "checkpoint": args.checkpoint, "gguf": args.gguf, "passes": args.passes,
            "in_sizes": args.in_sizes, "out_fixed": args.out_fixed,
            "out_sizes": args.out_sizes, "in_fixed": args.in_fixed,
            "precisions": {"algenta": "int8", "llama.cpp": "F16", "mlx-lm": "bf16"},
        },
        "cells": [{"in": c["in"], "out": c["out"]} for c in cells],
        "results": results,
    }
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"results -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
