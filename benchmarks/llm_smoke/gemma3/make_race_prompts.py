"""make_race_prompts.py — build the token-id race prompts for the Gemma 3 TTFT cells.

Replicates the SHAPE of Modular's official sonnet benchmark cell (max benchmark sonnet:
"Pick as many lines as you can from these poem lines:\\n" + fixed poem-line prefix +
randomly sampled poem lines, seed 24301), then truncates the encoded ids to EXACTLY the
target input length — the engine gate wants raw token ids, and TTFT is a function of the
input-token count, so an exact-length prompt is the fair cell. Raw-text encoding (no chat
template) keeps the builder dependency-free; the template only changes a handful of leading
tokens, never the cell's token count.

Usage:
  python3 make_race_prompts.py --tokenizer ~/models/gemma-3-27b-it \
      --sonnet <path>/sonnet_4x.txt --lens 256,550 --out-dir ~/g3race_prompts
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--sonnet", required=True, help="path to sonnet_4x.txt")
    ap.add_argument("--lens", default="256,550")
    ap.add_argument("--seed", type=int, default=24301)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.tokenizer)
    poem_lines = Path(args.sonnet).read_text().splitlines(keepends=True)
    base_prompt = "Pick as many lines as you can from these poem lines:\n"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for n_target in [int(x) for x in args.lens.split(",") if x.strip()]:
        rng = random.Random(args.seed + n_target)
        # prefix lines fixed + sampled tail, exactly like the MAX cell's prompt body
        n_sample = max(8, n_target // 3)
        lines = poem_lines[:6] + rng.sample(poem_lines, n_sample)
        text = base_prompt + "".join(lines)
        ids = tok.encode(text)[:n_target]
        out = out_dir / f"prompt_{n_target}.txt"
        out.write_text(",".join(str(i) for i in ids))
        # the truncated-id sequence decoded back to text: what an OpenAI-compatible
        # opponent (vLLM / llama-server) ingests so both engines see the SAME prompt
        (out_dir / f"prompt_{n_target}.text").write_text(tok.decode(ids))
        print(f"wrote {out} | {len(ids)} tokens (+ .text twin)")


if __name__ == "__main__":
    main()
