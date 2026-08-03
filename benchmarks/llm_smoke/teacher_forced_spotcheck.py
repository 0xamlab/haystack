"""teacher_forced_spotcheck.py — deep teacher-forced spot-check against a transformers-CPU
reference, at multiple positions on a real, already-agreed generation trajectory.

Fills a gap `verify_generation.py` and `verify_forward_pass.py` do not cover: `verify_generation.py`
compares two independently-run AUTOREGRESSIVE greedy decodes (Mojo's and `transformers`'), which is
only comparable while both sides keep making identical choices -- once either side's own logit noise
flips a single argmax, both trajectories diverge and every later position stops being informative.
`verify_forward_pass.py` checks a single PREFILL-only forward pass. Neither checks Mojo's own
correctness at a DEEP decode position without that position depending on an unbroken chain of prior
autoregressive agreement.

This script instead takes a token trajectory some Mojo arm actually generated (`generated_ids.txt`),
and for each requested position feeds the EXACT prefix up to that position into `transformers` in ONE
forward call (genuine teacher forcing -- the real prior tokens this run actually produced, not
`transformers`' own accumulated autoregressive guesses), then checks `argmax(logits[-1])` against
Mojo's own recorded next token there. Every spot position is checked independently of every other, so
this is exactly the "multiple positions" staged-correctness step a kernel change at depth needs: does
Mojo agree with an independent CPU reference AT this depth, given the identical history, regardless of
whether an earlier position happened to diverge.
"""
import argparse
import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401 (import parity with reference_generate.py)


def find_snapshot(ckpt_root: str) -> str:
    """`ckpt_root` may be a HuggingFace cache root (with a `snapshots/` subdir) or an already-
    resolved snapshot directory -- returns the latter unchanged, resolves the former to its one
    snapshot (this checkpoint is never fetched with more than one revision cached locally)."""
    snap_dir = Path(ckpt_root) / "snapshots"
    if snap_dir.is_dir():
        snaps = sorted(snap_dir.iterdir())
        if snaps:
            return str(snaps[0])
    return ckpt_root


def load_generated_ids(path: str):
    lines = Path(path).read_text().splitlines()
    n_prompt = int(lines[0].split()[1])
    n_generated = int(lines[1].split()[1])
    ids = []
    for line in lines[3:3 + n_generated]:
        parts = line.split()
        ids.append(int(parts[2]))
    return n_prompt, ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("generated_ids", help="path to a qwen3_generate_batch*'s own generated_ids.txt")
    ap.add_argument(
        "positions", nargs="+", type=int,
        help="the `pos` argument step() was called with at each spot to check (n_keys = pos + 1)",
    )
    ap.add_argument(
        "--checkpoint", default="/Users/angel/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B-Base",
        help="HF cache root or resolved snapshot dir for the Qwen3-0.6B-Base checkpoint",
    )
    ap.add_argument("--manifest", default="/tmp/qwen3smoke/manifest.json")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    prompt_ids = manifest["input_ids"]
    n_prompt = len(prompt_ids)

    n_prompt_check, mojo_new_ids = load_generated_ids(args.generated_ids)
    if n_prompt_check != n_prompt:
        print(f"FAIL: manifest n_prompt={n_prompt} but generated_ids.txt says {n_prompt_check}", file=sys.stderr)
        return 1
    full_traj = list(prompt_ids) + mojo_new_ids

    snapshot = find_snapshot(args.checkpoint)
    print(f"[spotcheck] loading checkpoint from {snapshot}", file=sys.stderr)
    model = AutoModelForCausalLM.from_pretrained(snapshot, torch_dtype=torch.float32)
    model.eval()

    n_ok = 0
    n_total = 0
    with torch.no_grad():
        for pos in args.positions:
            if pos + 1 >= len(full_traj):
                print(f"pos={pos}: no recorded next token in this trajectory (too shallow a run) -- skipped")
                continue
            # `pos` is the same `pos` argument step() was called with; n_keys = pos + 1. The token
            # Mojo PRODUCED at that step is full_traj[pos + 1] (0-indexed, prompt-then-generated).
            # The prefix teacher-forced into transformers is full_traj[0 : pos + 1] -- everything up
            # to and including position `pos`, exactly what step()'s own KV cache held at that call.
            prefix = full_traj[: pos + 1]
            mojo_next = full_traj[pos + 1]
            inp = torch.tensor([prefix], dtype=torch.long)
            out = model(inp, use_cache=False)
            logits_last = out.logits[0, -1].to(torch.float64)
            ref_next = int(torch.argmax(logits_last).item())
            ref_logit = float(logits_last[ref_next].item())
            n_total += 1
            status = "OK" if ref_next == mojo_next else "MISMATCH"
            if ref_next == mojo_next:
                n_ok += 1
            print(
                f"pos={pos:6d} (n_keys={pos+1:6d}, prefix_len={len(prefix):6d}) "
                f"mojo_next={mojo_next:6d} ref_next={ref_next:6d} ref_logit={ref_logit:.6f} [{status}]"
            )

    print(f"\n{n_ok}/{n_total} spot positions agree with the teacher-forced transformers-CPU reference")
    return 0 if n_ok == n_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
