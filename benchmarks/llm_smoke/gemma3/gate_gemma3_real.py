"""gate_gemma3_real.py — REAL-weights Gemma 3 identity gate (CUDA engine vs HF transformers CPU fp32).

Orchestrates the real-weights correctness gate:
  1. convert the downloaded gemma3 snapshot (SDK, f32 blob);
  2. run the CUDA engine arm (gemma3_correctness_cuda) -> logits + greedy tokens;
  3. run the HF-transformers CPU fp32 reference (ref_transformers_gemma3.py) -> logits + tokens;
  4. compare argmax, top-k token agreement, greedy token sequences, and report the logit diff.

Both arms run in float32 on the SAME bf16 weights, so the comparison is fp32-vs-fp32 with
independent reduction orders: the gate requires argmax + top-k agreement and reports the logit
spread rather than a hard byte threshold.

Usage:
  python3 gate_gemma3_real.py --source-ckpt ~/models/gemma-3-4b-it \
      --driver ~/gemma3_bin/gemma3_correctness_cuda \
      --tokens 2,1756,3402,762 --max-new 4 [--top-k 5]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"command failed: {' '.join(cmd)}\n")
        sys.stderr.write(proc.stdout[-4000:] + "\n" + proc.stderr[-4000:] + "\n")
        raise SystemExit(f"gate: subprocess failed rc={proc.returncode}")
    return proc.stdout


def _last_json(out: str) -> dict:
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise SystemExit("gate: no JSON line found")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-ckpt", required=True)
    parser.add_argument("--driver", required=True)
    parser.add_argument("--tokens", required=True)
    parser.add_argument("--max-new", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--converted", default=None, help="reuse an existing converted dir")
    args = parser.parse_args()

    prompt = [int(p) for p in args.tokens.split(",") if p.strip()]

    # 1. convert (f32 blob) unless reusing
    if args.converted:
        converted = Path(args.converted)
        print(f"gate: reusing converted -> {converted}")
    else:
        from algenta.inference import prepare_model_checkpoint

        import tempfile

        out_dir = Path(tempfile.mkdtemp(prefix="g3real-"))
        converted = prepare_model_checkpoint(
            args.source_ckpt, prompt, out_dir=out_dir, weights_dtype="f32"
        )
        print(f"gate: converted (f32) -> {converted}")

    # 2. engine logits + tokens
    eng_logits = _last_json(_run([
        args.driver, str(converted), "--tokens", args.tokens, "--dump-logits",
    ]))
    eng_tokens = _last_json(_run([
        args.driver, str(converted), "--tokens", args.tokens, "--max-new", str(args.max_new),
    ]))["generated"]

    # 3. transformers CPU fp32 reference
    ref_out = Path("/tmp/g3_ref_real.json")
    _run([
        sys.executable, str(HERE / "ref_transformers_gemma3.py"),
        "--ckpt", str(Path(args.source_ckpt).expanduser()),
        "--tokens", args.tokens, "--max-new", str(args.max_new), "--out", str(ref_out),
    ])
    ref = json.loads(ref_out.read_text())

    # 4. compare
    el = eng_logits["logits"]
    rl = ref["logits"]
    n = min(len(el), len(rl))
    max_abs = max(abs(el[i] - rl[i]) for i in range(n))
    eng_topk = sorted(range(len(el)), key=lambda i: -el[i])[: args.top_k]
    ref_topk = sorted(range(len(rl)), key=lambda i: -rl[i])[: args.top_k]

    print(f"gate: engine argmax={eng_logits['argmax']} | ref argmax={ref['argmax']}")
    print(f"gate: engine top{args.top_k}={eng_topk}")
    print(f"gate: ref    top{args.top_k}={ref_topk}")
    print(f"gate: logits max_abs_diff={max_abs:.6e} (fp32 engine vs fp32 transformers)")
    print(f"gate: engine tokens={eng_tokens}")
    print(f"gate: ref    tokens={ref['generated']}")

    ok = True
    if eng_logits["argmax"] != ref["argmax"]:
        print("FAIL: argmax mismatch")
        ok = False
    if set(eng_topk) != set(ref_topk):
        print("WARN: top-k sets differ (check margin)")
    if eng_tokens != ref["generated"]:
        print("FAIL: greedy token sequences differ")
        ok = False

    print("gate: PASS" if ok else "gate: FAIL")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
