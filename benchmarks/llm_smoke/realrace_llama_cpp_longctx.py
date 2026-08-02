"""realrace_llama_cpp_longctx.py — the LONG-GENERATION twin of `realrace_llama_cpp.py`.

Starts a real `llama-server` (brew-installed llama.cpp, this machine) on a GGUF conversion of the
SAME Qwen3-0.6B-Base checkpoint, posts one STREAMING `/completion` request (`"stream": true`) with
the SAME prompt, greedy decoding (`temperature=0, top_k=1`), for `--n-predict` tokens (thousands, not
16), and records the WALL-CLOCK ARRIVAL TIME of every SSE chunk as that token's own latency —
llama.cpp's server streams a chunk the instant a token is sampled (real decode-only per-token
timing on localhost loopback, network overhead sub-millisecond and constant, not growing with
position), which is what a per-position rate curve needs; the server's own aggregate `timings`
block (`predicted_per_second`) is ALSO recorded from the final chunk for a sanity cross-check
against the sum of this script's own per-chunk deltas, but is not itself position-resolved.

Run:
    /tmp/bb/bin/python -P realrace_llama_cpp_longctx.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf \
        --ngl 99 --n-predict 4096 --out /tmp/bb/qwen3_ckpt/llama_cpp_longctx_gpu_4096.json
    /tmp/bb/bin/python -P realrace_llama_cpp_longctx.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf \
        --ngl 0 --n-predict 1024 --out /tmp/bb/qwen3_ckpt/llama_cpp_longctx_cpu_1024.json
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--prompt", default="The capital of France is")
    ap.add_argument("--n-predict", type=int, default=4096)
    ap.add_argument("--port", type=int, default=8094)
    ap.add_argument("--ngl", type=int, default=99, help="GPU layers to offload; 0 = CPU-only")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    proc = subprocess.Popen(
        ["llama-server", "-m", args.gguf, "--port", str(args.port), "-ngl", str(args.ngl),
         "-c", str(max(args.n_predict + 64, 512))],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{args.port}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.25)

        body = json.dumps(
            {
                "prompt": args.prompt,
                "n_predict": args.n_predict,
                "temperature": 0,
                "top_k": 1,
                "cache_prompt": False,
                "stream": True,
            }
        ).encode()

        url = f"http://127.0.0.1:{args.port}/completion"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

        token_texts = []
        token_ids = []
        per_token_ms = []
        final_timings = None
        stopped_on_eos = False
        t_prev = time.perf_counter()
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload:
                    continue
                t_now = time.perf_counter()
                try:
                    d = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if d.get("tokens"):
                    per_token_ms.append((t_now - t_prev) * 1000.0)
                    token_texts.append(d.get("content", ""))
                    token_ids.extend(d["tokens"])
                    t_prev = t_now
                    n = len(token_ids)
                    if n <= 8 or n % 256 == 0:
                        print(f"[llama.cpp-longctx ngl={args.ngl}] token {n}: id={d['tokens']} {d.get('content')!r}",
                              file=sys.stderr)
                if d.get("stop"):
                    stopped_on_eos = bool(d.get("stopped_eos", False))
                    final_timings = d.get("timings")

        full_text = "".join(token_texts)
        print(f"[llama.cpp-longctx ngl={args.ngl}] generated {len(token_ids)} tokens, "
              f"stopped_on_eos={stopped_on_eos}", file=sys.stderr)
        print(f"[llama.cpp-longctx ngl={args.ngl}] text (repr, truncated): {full_text[:200]!r}...",
              file=sys.stderr)
        print(f"[llama.cpp-longctx ngl={args.ngl}] server timings: {final_timings}", file=sys.stderr)

        result = {
            "engine": f"llama.cpp-ngl{args.ngl}",
            "prompt": args.prompt,
            "n_predict": args.n_predict,
            "token_ids": token_ids,
            "token_texts": token_texts,
            "per_token_ms": per_token_ms,
            "stopped_on_eos": stopped_on_eos,
            "server_timings": final_timings,
        }
        with open(args.out, "w") as f:
            json.dump(result, f)
        print(f"[llama.cpp-longctx ngl={args.ngl}] -> {args.out}", file=sys.stderr)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
