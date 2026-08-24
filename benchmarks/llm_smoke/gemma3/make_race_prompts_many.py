"""make_race_prompts_many.py — build N DISTINCT token-exact sonnet-shaped race prompts.

The C=50 open-loop aggregate cell needs the MAX sonnet workload shape at volume: 500
prompts, each sonnet_input_len tokens, a shared sonnet_prefix_len-token head (the MAX
cell's prefix-200), distinct tails. Same construction as make_race_prompts.py (MAX cell
replica: "Pick as many lines as you can from these poem lines:\\n" + fixed poem-line
prefix + sampled poem lines, truncated to EXACTLY the target length), with a per-prompt
seed so every prompt is distinct but reproducible. Writes:

  prompt_{i:04d}.txt    comma-joined token ids   (the algenta JSONL driver's token_ids)
  prompt_{i:04d}.text   decoded text             (OpenAI-compatible opponents)

Usage:
  python3 make_race_prompts_many.py --tokenizer ~/models/gemma-3-27b-it \
      --sonnet <path>/sonnet_4x.txt --count 500 --in-len 550 --prefix 200 \
      --out-dir /tmp/g3race500
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--sonnet", required=True, help="path to sonnet_4x.txt")
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--in-len", type=int, default=550)
    ap.add_argument("--prefix", type=int, default=200,
                    help="shared prefix tokens (MAX cell prefix length)")
    ap.add_argument("--seed", type=int, default=24301)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.tokenizer)
    poem_lines = Path(args.sonnet).read_text().splitlines(keepends=True)
    base_prompt = "Pick as many lines as you can from these poem lines:\n"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # the shared prefix: one fixed draw, encoded and truncated to args.prefix tokens —
    # every prompt starts with exactly these ids (the MAX cell's shared head)
    rng0 = random.Random(args.seed)
    head_text = base_prompt + "".join(poem_lines[:6]
                                      + rng0.sample(poem_lines, max(8, args.prefix // 3)))
    head_ids = tok.encode(head_text)[: args.prefix]

    n_written = 0
    for i in range(args.count):
        rng = random.Random(args.seed + 1000003 * (i + 1))
        tail_lines = rng.sample(poem_lines, max(8, (args.in_len - args.prefix) // 3 + 4))
        tail_ids = tok.encode("".join(tail_lines))
        ids = head_ids + tail_ids
        ids = ids[: args.in_len]
        if len(ids) < args.in_len:
            # tail too short — pad with another draw (rare; keeps the length exact)
            extra = tok.encode("".join(rng.sample(poem_lines, 8)))
            ids = (head_ids + tail_ids + extra)[: args.in_len]
        (out_dir / f"prompt_{i:04d}.txt").write_text(",".join(map(str, ids)))
        (out_dir / f"prompt_{i:04d}.text").write_text(tok.decode(ids))
        n_written += 1
    print(f"wrote {n_written} prompts x {args.in_len} tokens "
          f"(shared prefix {args.prefix}) to {out_dir}")


if __name__ == "__main__":
    main()
