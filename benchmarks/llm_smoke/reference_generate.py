"""reference_generate.py — pure greedy autoregressive generation with `transformers` on CPU
(float32), for cross-checking `qwen3_generate.mojo`'s generated token sequence.

Deliberately NOT `model.generate(...)`: `.generate()` applies whatever the checkpoint's
`generation_config.json` defaults are (repetition penalties, min/max length heuristics, forced
tokens, ...) unless every one of them is overridden, and a silent mismatch there would look like a
Mojo bug. This script instead calls `model(...)` directly in a hand-written loop with its own
`past_key_values` (a REAL KV cache on the reference side too, for the same reason the Mojo side
holds one -- not because the two implementations need matching performance characteristics to agree
on OUTPUT, just because it is the natural, honest way to decode one token at a time), and the only
decision made at each step is `argmax(logits[-1])` -- pure greedy, nothing else. This is the exact
same decision `llmk.generate.greedy_argmax_flat` makes.
"""

import argparse
import json
import sys
from pathlib import Path

import torch


def log(msg: str) -> None:
    print(f"[reference_generate] {msg}", file=sys.stderr, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--prompt", default="The capital of France is")
    ap.add_argument("--n-new", type=int, default=16)
    ap.add_argument("--out", default="/tmp/bb/qwen3_ckpt/reference_generate")
    args = ap.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer

    ckpt = Path(args.checkpoint)
    tok = AutoTokenizer.from_pretrained(str(ckpt))
    model = AutoModelForCausalLM.from_pretrained(str(ckpt), torch_dtype=torch.float32)
    model.eval()

    prompt_ids = tok(args.prompt, return_tensors=None)["input_ids"]
    eos_id = model.config.eos_token_id
    log(f"prompt {args.prompt!r} -> {prompt_ids}, eos_token_id={eos_id}")

    generated = list(prompt_ids)
    past = None
    stopped_on_eos = False
    step_logits = []

    with torch.no_grad():
        for step in range(args.n_new):
            if past is None:
                inp = torch.tensor([generated], dtype=torch.long)
            else:
                inp = torch.tensor([[generated[-1]]], dtype=torch.long)
            out = model(inp, past_key_values=past, use_cache=True)
            past = out.past_key_values
            logits_last = out.logits[0, -1].to(torch.float64)
            next_id = int(torch.argmax(logits_last).item())
            step_logits.append(float(logits_last[next_id].item()))
            generated.append(next_id)
            log(f"step {step}: pos={len(generated) - 2} -> id={next_id} logit={step_logits[-1]:.6f}")
            if next_id == eos_id:
                stopped_on_eos = True
                break

    n_prompt = len(prompt_ids)
    new_ids = generated[n_prompt:]
    decoded_full = tok.decode(generated)
    decoded_new = tok.decode(new_ids)
    log(f"generated {len(new_ids)} new tokens, stopped_on_eos={stopped_on_eos}")
    log(f"full text: {decoded_full!r}")
    log(f"new text only: {decoded_new!r}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "prompt": args.prompt,
        "prompt_ids": prompt_ids,
        "n_prompt": n_prompt,
        "new_ids": new_ids,
        "step_logits": step_logits,
        "stopped_on_eos": stopped_on_eos,
        "eos_token_id": eos_id,
        "decoded_full": decoded_full,
        "decoded_new": decoded_new,
    }
    with open(out_dir / "reference_generated.json", "w") as f:
        json.dump(result, f, indent=2)
    log(f"-> {out_dir / 'reference_generated.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
