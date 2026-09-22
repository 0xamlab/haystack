#!/usr/bin/env python3
"""Independent greedy-decode reference for the resident decode probes: Hugging Face `transformers`
in float32 on the CPU, from the same snapshot the converted checkpoint came from.

    scripts/hf_kernels/transformers_reference.py --snapshot ~/qwen3-0.6b-base --prompt-ids 785 3974 ... --max-new-tokens 8 --out reference.json
"""
from __future__ import annotations

import argparse
import json
import time

import torch
from transformers import AutoModelForCausalLM


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--prompt-ids", nargs="+", type=int, required=True)
    ap.add_argument("--max-new-tokens", type=int, default=8)
    ap.add_argument("--out")
    a = ap.parse_args()
    torch.manual_seed(0)
    model = AutoModelForCausalLM.from_pretrained(a.snapshot, torch_dtype=torch.float32)
    model.eval()
    ids = torch.tensor([a.prompt_ids], dtype=torch.long)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(ids, max_new_tokens=a.max_new_tokens, do_sample=False, num_beams=1)
    generated = out[0, ids.shape[1]:].tolist()
    result = {"snapshot": a.snapshot, "prompt_ids": a.prompt_ids, "reference": "transformers float32 greedy, CPU", "tokens": generated,
              "torch": torch.__version__, "seconds": round(time.time() - t0, 2)}
    print(json.dumps(result))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
