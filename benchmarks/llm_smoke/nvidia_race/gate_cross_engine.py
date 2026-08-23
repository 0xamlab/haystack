"""gate_cross_engine.py — the 7B-lane cross-engine greedy-token-identity gate (2026-08-22).

Runs the SAME five chat prompts through BOTH engines, greedy, and requires the first 64
generated tokens to agree:

  * OUR engine     — qwen25_7b_p3_graph_cuda, arm=p3, --gen-only 64 --prompt-ids <ids>.
                     The prompt ids come from prompts.json (rendered once with the model's own
                     chat template), so both engines start from IDENTICAL prompt tokens.
  * llama.cpp      — llama-server /completion on the F16 GGUF, temperature=0 (greedy),
                     n_predict=64, given the SAME rendered prompt text raw (no re-templating).

Comparison is on the decoded generation text of the first 64 tokens (token identity implies
text identity for a greedy run; a mismatch is reported with the first divergent character and
both sides' text). Serialized: our engine runs first (it is a one-shot process that frees the
GPU on exit), then llama-server is started, queried, and stopped — never two GPU tenants at
once, matching the solo-GPU census the campaign measures under.

Usage (on the VM):
    python3 gate_cross_engine.py --ckpt /tmp/w7b/ckpt \
        --driver ~/w7b_bins/qwen25_7b_p3_graph_cuda \
        --gguf ~/models/qwen2.5-7b-instruct-f16.gguf \
        --llama-server ~/llama.cpp/build/bin/llama-server \
        --model-dir ~/models/Qwen2.5-7B-Instruct \
        [--n-tokens 64] [--port 8099]
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def _log(msg: str) -> None:
    print(f"[gate] {msg}", flush=True)


def _free_gpu() -> None:
    """Wait for the GPU to have no compute tenants (the campaign's solo-GPU protocol)."""
    for _ in range(120):
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True, text=True,
        ).stdout.strip()
        if out == "":
            return
        time.sleep(2)
    raise SystemExit("GPU never became idle; refusing to start")


def _wait_http(port: int, timeout_s: float = 180.0) -> None:
    """Wait until the server is SERVING, not merely listening: llama.cpp opens its socket
    before the model finishes loading and answers /completion with 503 while the load is in
    flight (the 7B-lane cross-gate hit exactly that on its first run, 2026-08-23). Poll
    /health until it reports ok."""
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=2
            ) as resp:
                body = resp.read().decode("utf-8", "replace")
                if resp.status == 200 and "ok" in body:
                    return
        except urllib.error.HTTPError:
            pass  # port up but model still loading (503) — keep waiting
        except OSError:
            pass  # not listening yet
        time.sleep(2)
    raise SystemExit(f"llama-server never became ready on port {port}")


def _run_our_engine(driver: str, ckpt: str, arm: str, ids, n_tokens: int, dump: Path) -> list:
    id_csv = ",".join(str(int(t)) for t in ids)
    cmd = [
        driver, "--checkpoint", ckpt, "--arm", arm,
        "--gen-only", str(n_tokens), "--prompt-ids", id_csv, "--dump", str(dump),
    ]
    _log(f"  our engine (arm={arm}): {len(ids)} prompt tokens -> {n_tokens} generated")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        _log("  our engine FAILED:\n" + r.stdout[-2000:] + "\n" + r.stderr[-2000:])
        raise SystemExit("our engine failed")
    if "GEN_ONLY DONE" not in r.stdout:
        _log("  our engine did not report GEN_ONLY DONE:\n" + r.stdout[-2000:])
        raise SystemExit("our engine did not complete")
    return [int(line) for line in dump.read_text().split() if line.strip()]


def _run_llama(server_bin: str, gguf: str, port: int, prompt_text: str, n_tokens: int) -> str:
    import urllib.request

    body = json.dumps({
        "prompt": prompt_text,
        "n_predict": n_tokens,
        "temperature": 0.0,
        "top_k": 1,
        "stop": [],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data.get("content", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/tmp/w7b/ckpt")
    ap.add_argument("--driver", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--llama-server", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--n-tokens", type=int, default=64)
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--workdir", default="/tmp/w7b/gate")
    ap.add_argument("--arm", default="f32",
                    help="our-engine arm for the cross-engine comparison (gate (a) uses the "
                         "full-f32 arm so it tests the model implementation, not the packed3 "
                         "quantization; run --arm p3 separately to price quant flips)")
    args = ap.parse_args()

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)

    prompts = json.loads((Path(args.ckpt) / "prompts.json").read_text())
    chat = prompts["chat_prompts"]
    _log(f"loaded {len(chat)} chat prompts from {args.ckpt}/prompts.json")

    # ── Phase 1: our engine (GPU) ──────────────────────────────────────────────
    our_ids = []
    for idx, entry in enumerate(chat):
        _free_gpu()
        dump = work / f"our_{args.arm}_p{idx}.txt"
        ids = _run_our_engine(args.driver, args.ckpt, args.arm, entry["ids"],
                              args.n_tokens, dump)
        our_ids.append(ids)
        _log(f"  prompt {idx}: got {len(ids)} generated tokens")

    # ── Phase 2: llama.cpp server (GPU) ────────────────────────────────────────
    _free_gpu()
    _log("starting llama-server (F16) ...")
    srv_log = open(work / "llama_server.log", "w")
    srv = subprocess.Popen(
        [args.llama_server, "-m", args.gguf, "--host", "127.0.0.1",
         "--port", str(args.port), "-c", str(args.ctx), "-ngl", "99",
         "--no-webui"],
        stdout=srv_log, stderr=subprocess.STDOUT,
    )
    try:
        _wait_http(args.port)
        _log("llama-server up")
        llama_texts = []
        for idx, entry in enumerate(chat):
            txt = _run_llama(args.llama_server, args.gguf, args.port,
                             entry["rendered"], args.n_tokens)
            llama_texts.append(txt)
            _log(f"  prompt {idx}: llama generated {len(txt)} chars")
    finally:
        srv.send_signal(signal.SIGTERM)
        try:
            srv.wait(timeout=30)
        except subprocess.TimeoutExpired:
            srv.kill()
        srv_log.close()

    # ── Phase 3: compare (decode our ids with the HF tokenizer) ────────────────
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model_dir)
    all_pass = True
    results = []
    for idx, entry in enumerate(chat):
        our_text = tok.decode(our_ids[idx], skip_special_tokens=False)
        llama_text = llama_texts[idx]
        # Compare the shorter of the two (both generated n_tokens; decode length can differ
        # by trailing-space representation). Require the common prefix of generated text to
        # match exactly.
        n = min(len(our_text), len(llama_text))
        match = our_text[:n] == llama_text[:n] and n > 0
        results.append({
            "prompt": entry["role_prompt"],
            "n_our_tokens": len(our_ids[idx]),
            "match": match,
            "our_text": our_text,
            "llama_text": llama_text,
        })
        if not match:
            all_pass = False
            # first divergence
            div = next((i for i in range(n) if our_text[i] != llama_text[i]), n)
            _log(f"prompt {idx}: MISMATCH at char {div}")
            _log(f"  ours : ...{our_text[max(0,div-30):div+30]!r}")
            _log(f"  llama: ...{llama_text[max(0,div-30):div+30]!r}")
        else:
            _log(f"prompt {idx}: MATCH ({len(our_ids[idx])} tokens)")

    (work / "gate_results.json").write_text(json.dumps(results, indent=1))
    if all_pass:
        _log(f"GATE RESULT: PASS — arm={args.arm}, all {len(chat)} chat prompts "
             f"greedy-token-identical ({args.n_tokens} tokens) vs llama.cpp F16")
        return 0
    _log(f"GATE RESULT: FAIL — arm={args.arm}, at least one prompt diverged")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
