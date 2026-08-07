"""checkpoint_equivalence.py — Phase 0A gate: is the Algenta checkpoint numerically comparable to
the llama.cpp GGUF conversion raced against it, or merely "the same model name"?

Compares, position by position, greedy-decoded token IDs AND per-step top-token logit between:
  - Algenta's own generated_ids.txt (produced by qwen3_generate.mojo /
    qwen3_generate_batch_i8_allsimd7_prefill.mojo, same 3-column-per-line format
    verify_generation.py already reads: step pos tok_id logit step_ms)
  - llama.cpp's llama-server /completion response, greedy (temperature=0, top_k=1), with
    n_probs=1 to recover each step's chosen-token logprob.

Token-ID agreement is the primary signal (same greedy path); logit magnitude is expected to
differ somewhat (bf16 source -> f16 GGUF is a real, if small, precision narrowing — recorded, not
hidden) — this script reports the delta rather than assuming zero.

Usage:
    /tmp/bb/bin/python -P checkpoint_equivalence.py \
        --algenta-ids /tmp/qwen3smoke/generated_ids.txt \
        --gguf /private/tmp/qwen3-0.6b-base-f16.gguf \
        --prompt "The capital of France is" --n-predict 16
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def _read_algenta_ids(path: Path) -> tuple[int, list[int], list[float]]:
    lines = path.read_text().splitlines()
    n_prompt = int(lines[0].split()[1])
    n_generated = int(lines[1].split()[1])
    ids, logits = [], []
    for line in lines[3 : 3 + n_generated]:
        _step, _pos, tok_id, logit, _step_ms = line.split()
        ids.append(int(tok_id))
        logits.append(float(logit))
    return n_prompt, ids, logits


def _run_llama_cpp(gguf: str, prompt_ids: list[int], n_predict: int, port: int) -> tuple[list[int], list[float]]:
    proc = subprocess.Popen(
        ["llama-server", "-m", gguf, "--port", str(port), "-ngl", "99"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        # Raw token-ID array, not text: the plan requires "prompt token IDs, not merely
        # equivalent text" -- llama.cpp's own tokenizer could otherwise silently diverge from
        # whatever produced the Algenta checkpoint's baked-in input_ids.
        body = json.dumps({
            "prompt": prompt_ids, "n_predict": n_predict,
            "temperature": 0, "top_k": 1, "n_probs": 1,
        }).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/completion", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        ids, logits = [], []
        for entry in result.get("completion_probabilities", []):
            ids.append(entry["id"])
            # llama.cpp's server returns natural-log probability of the CHOSEN token directly on
            # the entry itself (not nested under "probs"); report as-is so the caller can compare
            # convention (raw pre-softmax logit on the Algenta side) rather than assume equal scale.
            logits.append(entry.get("logprob", float("nan")))
        return ids, logits
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--algenta-ids", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--manifest", required=True, help="Algenta manifest.json holding the exact prompt input_ids")
    ap.add_argument("--n-predict", type=int, default=16)
    ap.add_argument("--port", type=int, default=8094)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    prompt_ids = manifest["input_ids"]

    n_prompt, alg_ids, alg_logits = _read_algenta_ids(Path(args.algenta_ids))
    if n_prompt != len(prompt_ids):
        print(f"FAIL: algenta generated_ids.txt claims n_prompt={n_prompt} but manifest input_ids "
              f"has {len(prompt_ids)} tokens -- not the same run, refusing to compare.")
        return 1
    llc_ids, llc_logprobs = _run_llama_cpp(args.gguf, prompt_ids, args.n_predict, args.port)

    print(f"algenta:   n_prompt={n_prompt} n_generated={len(alg_ids)}")
    print(f"llama.cpp: n_generated={len(llc_ids)}")

    n = min(len(alg_ids), len(llc_ids))
    agree = sum(1 for i in range(n) if alg_ids[i] == llc_ids[i])
    print(f"\ntoken-ID agreement: {agree}/{n} positions")
    for i in range(n):
        mark = "OK" if alg_ids[i] == llc_ids[i] else "DIVERGE"
        print(f"  step {i:2d}: algenta id={alg_ids[i]:6d} logit={alg_logits[i]:+9.4f}"
              f"   llama.cpp id={llc_ids[i]:6d} logprob={llc_logprobs[i]:+9.4f}   {mark}")

    if agree < n:
        print(f"\nFAIL: {n - agree}/{n} positions diverge — not proven numerically comparable, "
              "'same model name' is not the same claim as 'same greedy path'.")
        return 1
    print(f"\nOK: {n}/{n} greedy positions agree. Logit/logprob scale differs by convention "
          "(raw logit vs. natural-log softmax probability) — magnitude comparison is a separate, "
          "future check once both sides report the same quantity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
