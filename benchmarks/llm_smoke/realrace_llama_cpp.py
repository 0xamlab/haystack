"""realrace_llama_cpp.py — the llama.cpp arm of the RealRace phase.

Starts a real `llama-server` (brew-installed llama.cpp, this machine) on a GGUF conversion of the
SAME Qwen3-0.6B-Base checkpoint, posts one `/completion` request with the SAME prompt, greedy
decoding (`temperature=0, top_k=1`), for the SAME generation length (`n_predict=16`) the Mojo
`qwen3_generate.mojo` driver uses, then prints the generated text plus llama.cpp's own `timings`
block (`predicted_per_second` is the real, on-device decode-only tokens/sec; `prompt_per_second`
is prefill).

GGUF conversion (one-time, not run by this script — needs a full llama.cpp source checkout for
`convert_hf_to_gguf.py`, which the brew bottle does not ship):
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git /tmp/bb/src/llama.cpp
    cd /tmp/bb/src/llama.cpp
    PYTHONPATH="$PWD:$PWD/gguf-py" /tmp/bb/bin/python -P convert_hf_to_gguf.py \
        --outfile /tmp/bb/qwen3-0.6b-base-f16.gguf --outtype f16 /private/tmp/qwen3-0.6b-base
    # optional, bonus/informational only (NOT sequence-verified against the reference — see
    # REALRACE_RESULTS.md for why quantization changes the greedy path on a model this small):
    llama-quantize /tmp/bb/qwen3-0.6b-base-f16.gguf /tmp/bb/qwen3-0.6b-base-q4_k_m.gguf Q4_K_M

Run:
    /tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 99
    /tmp/bb/bin/python -P realrace_llama_cpp.py --gguf /tmp/bb/qwen3-0.6b-base-f16.gguf --ngl 0
"""

import argparse
import subprocess
import sys
import time
import urllib.request
import json


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--prompt", default="The capital of France is")
    ap.add_argument("--n-predict", type=int, default=16)
    ap.add_argument("--port", type=int, default=8093)
    ap.add_argument("--ngl", type=int, default=99, help="GPU layers to offload; 0 = CPU-only")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    proc = subprocess.Popen(
        ["llama-server", "-m", args.gguf, "--port", str(args.port), "-ngl", str(args.ngl)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{args.port}/completion"
        # poll for the server socket instead of a fixed sleep
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
            }
        ).encode()

        for i in range(args.runs):
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.loads(resp.read())
            print(f"[llama.cpp ngl={args.ngl}] run {i + 1}: content={d['content']!r}", file=sys.stderr)
            print(f"[llama.cpp ngl={args.ngl}] run {i + 1}: timings={d['timings']}", file=sys.stderr)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
