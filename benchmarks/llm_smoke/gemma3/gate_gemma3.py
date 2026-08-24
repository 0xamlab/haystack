"""gate_gemma3.py — the Gemma 3 identity gate (Gemma 3 lane, 2026-08-23).

Runs the SAME prompt two ways and diffs them:

  1. the independent fp64 torch reference (`ref_gemma3_torch.py`) — the oracle, written straight
     from the verified architecture facts and itself cross-validated against HF transformers' own
     Gemma3 implementation;
  2. the CUDA engine arm (`gemma3_correctness_cuda`) over the SDK-converted checkpoint.

Two comparisons, both reported:
  * LOGITS: the full final logits vector after the prompt, element-wise. Random-weight synthetic
    models collapse to token attractors, so matching logits (not just the argmax token) is the
    proof that every kernel — embed scale, four (1+w) norms, dual rope, windowed attention,
    GeGLU, the tied unscaled lm_head — computes the verified math.
  * TOKENS: greedy generation, which must agree token-for-token.

Exit 0 = PASS, 1 = FAIL. The synthetic checkpoint is converted here via the SDK, so this gate
also exercises the converter end-to-end.

Usage:
  python3 gate_gemma3.py --source-ckpt /tmp/g3syn \
      --driver /path/to/gemma3_correctness_cuda \
      --tokens 3,17,42,8,91,5,66 --max-new 16 [--logit-atol 1e-3]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from algenta.inference import prepare_model_checkpoint  # noqa: E402
from ref_gemma3_torch import Gemma3Reference  # noqa: E402


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"command failed: {' '.join(cmd)}\n")
        sys.stderr.write(proc.stdout[-4000:] + "\n" + proc.stderr[-4000:] + "\n")
        raise SystemExit(f"gate: subprocess failed rc={proc.returncode}")
    return proc.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ckpt", required=True,
                        help="HF-format synthetic gemma3 checkpoint (config.json + safetensors)")
    parser.add_argument("--driver", required=True,
                        help="path to the gemma3_correctness_cuda binary")
    parser.add_argument("--tokens", required=True, help="comma-separated prompt ids")
    parser.add_argument("--max-new", type=int, default=16)
    parser.add_argument("--logit-atol", type=float, default=1e-3,
                        help="max abs logit difference tolerated (fp32 engine vs fp64 ref)")
    args = parser.parse_args()

    prompt = [int(p) for p in args.tokens.split(",") if p.strip()]

    # ── 1. convert the source checkpoint through the SDK ──
    out_dir = Path(tempfile.mkdtemp(prefix="g3gate-"))
    converted = prepare_model_checkpoint(args.source_ckpt, prompt, out_dir=out_dir)
    print(f"gate: converted -> {converted}")

    # ── 2. reference logits + tokens ──
    reference = Gemma3Reference(args.source_ckpt)
    ref_logits = reference.prefill_logits(prompt)
    ref_argmax = int(ref_logits.argmax(dim=-1).item())
    ref_tokens = reference.generate(prompt, args.max_new)[len(prompt):]
    ref_logits_list = [float(v) for v in ref_logits]

    # ── 3. engine logits ──
    eng_logits_out = _run([
        args.driver, str(converted), "--tokens", args.tokens, "--dump-logits",
    ])
    eng = json.loads(eng_logits_out.strip().splitlines()[-1])
    eng_logits_list = eng["logits"]
    eng_argmax = int(eng["argmax"])

    # ── 4. engine tokens ──
    eng_tokens_out = _run([
        args.driver, str(converted), "--tokens", args.tokens,
        "--max-new", str(args.max_new),
    ])
    eng_tokens = json.loads(eng_tokens_out.strip().splitlines()[-1])["generated"]

    # ── compare ──
    if len(eng_logits_list) != len(ref_logits_list):
        print(f"FAIL: logits length {len(eng_logits_list)} != {len(ref_logits_list)}")
        raise SystemExit(1)
    max_abs = max(abs(a - b) for a, b in zip(ref_logits_list, eng_logits_list))
    # top-1 / top-2 margin on the reference: how robust the argmax is to fp32 rounding
    srt = sorted(ref_logits_list, reverse=True)
    margin = srt[0] - srt[1]

    print(f"gate: logits max_abs_diff = {max_abs:.6e} (atol {args.logit_atol:.1e})")
    print(f"gate: ref argmax = {ref_argmax}, engine argmax = {eng_argmax}, "
          f"ref top1-top2 margin = {margin:.4f}")
    print(f"gate: ref tokens    = {ref_tokens}")
    print(f"gate: engine tokens = {eng_tokens}")

    ok = True
    if max_abs > args.logit_atol:
        print(f"FAIL: logits diverge by {max_abs:.6e} > atol {args.logit_atol:.1e}")
        ok = False
    if ref_argmax != eng_argmax:
        print("FAIL: argmax mismatch")
        ok = False
    if ref_tokens != eng_tokens:
        print("FAIL: greedy token sequences differ")
        ok = False

    if ok:
        print("gate: PASS — engine logits + greedy tokens match the independent reference")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
