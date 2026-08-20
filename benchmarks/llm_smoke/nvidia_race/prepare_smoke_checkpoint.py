"""prepare_smoke_checkpoint.py — build the `/tmp/qwen3smoke/{manifest.json,weights.blob}` dump
the CUDA race drivers read, on a fresh VM, through the repo's OWN numpy-only conversion path
(`algenta.inference.prepare_model_checkpoint`, no torch) — the exact path PR #778's Phase 2 used.

The race prompt is the campaign's 256-token fixture: "The capital of France is Paris. " repeated
36 times plus the trailing clause "The capital of France". It is tokenized here with the repo's
own Qwen3 tokenizer loaded from the SAME checkpoint being converted, and the script refuses to
write anything unless the result is exactly 256 ids — a length mismatch means the prompt text and
the ledger's fixture drifted apart, and that must be investigated, not papered over.

Usage (on the VM, pixi env python):
    python benchmarks/llm_smoke/nvidia_race/prepare_smoke_checkpoint.py /opt/qwen3-0.6b-base
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta.inference import prepare_model_checkpoint  # noqa: E402
from algenta.tokenizer import load_tokenizer  # noqa: E402

_RACE_PROMPT = "The capital of France is Paris. " * 36 + "The capital of France"
_EXPECTED_TOKENS = 256
_EXPECTED_FIRST_GENERATED = 374  # the campaign oracle's first greedy token for this fixture


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <hf-checkpoint-dir>", file=sys.stderr)
        return 2
    checkpoint_dir = Path(sys.argv[1])

    tokenizer = load_tokenizer(checkpoint_dir)
    prompt_ids = tokenizer.encode(_RACE_PROMPT)
    print(f"[prepare_smoke] race prompt -> {len(prompt_ids)} tokens")
    if len(prompt_ids) != _EXPECTED_TOKENS:
        print(
            f"[prepare_smoke] FAIL: the race fixture must tokenize to {_EXPECTED_TOKENS} ids, "
            f"got {len(prompt_ids)} — the prompt text and the ledger fixture drifted apart",
            file=sys.stderr,
        )
        return 1

    out_dir = prepare_model_checkpoint(checkpoint_dir, prompt_ids, out_dir="/tmp/qwen3smoke")
    manifest = out_dir / "manifest.json"
    blob = out_dir / "weights.blob"
    if not manifest.is_file() or not blob.is_file():
        print("[prepare_smoke] FAIL: conversion did not write manifest.json + weights.blob",
              file=sys.stderr)
        return 1
    print(f"[prepare_smoke] wrote {manifest} ({manifest.stat().st_size} B) "
          f"and {blob} ({blob.stat().st_size} B)")
    print(f"[prepare_smoke] oracle note: first generated token for this fixture must be "
          f"{_EXPECTED_FIRST_GENERATED} (the drivers enforce it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
