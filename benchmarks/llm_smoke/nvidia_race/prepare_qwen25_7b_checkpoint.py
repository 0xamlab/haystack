"""prepare_qwen25_7b_checkpoint.py — build the 7B-lane resident checkpoint pair
(`/tmp/w7b/ckpt/{manifest.json,weights.blob}`) from a Qwen2.5-7B-Instruct HF snapshot,
through the repo's OWN streaming converter (`algenta.inference.prepare_model_checkpoint`,
numpy-only, peak host RAM O(one tensor / one tile) — a 60 GB Float64 blob streams through
a host that could never hold the model whole).

Qwen2.5-7B-Instruct vs the Qwen3 shapes the CUDA lanes were built on:
  * NO per-head QK-norm tensors (manifest `has_qk_norm`=0 — the engine rotates raw
    projections, llama-family branch);
  * `tie_word_embeddings=false` — a SEPARATE `lm_head.weight` is converted and the manifest
    carries `tie_word_embeddings`=0;
  * GQA 28 q / 4 kv heads, d_head=128, d_ff=18944 (a new resident staging tier), rope_theta
    1e6, no rope_scaling, vocab 152064, eos 151645.

Prompts: five chat prompts, rendered ONCE with the checkpoint's own chat template
(transformers on the VM) and frozen here as (rendered text, token ids) pairs — the SAME
rendered strings feed llama.cpp (raw /completion, no re-templating) and vLLM (/v1/completions),
so cross-engine token identity compares identical prompt tokens. Prompt 1 is padded
deterministically to EXACTLY 256 tokens and becomes the fixture: the manifest's `input_ids`,
the prefill-race prompt, and the gen64/gen256 decode seed.

Usage (on the VM, system python3 with numpy + transformers):
    python benchmarks/llm_smoke/nvidia_race/prepare_qwen25_7b_checkpoint.py \
        ~/models/Qwen2.5-7B-Instruct [/tmp/w7b/ckpt]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "algenta"))

from algenta.inference import prepare_model_checkpoint  # noqa: E402

_FIXTURE_TOKENS = 256

# The five gate/benchmark chat prompts (user-turn content only; the template rendering below
# wraps them). Diverse behaviours: exposition, concise factual, creative, translation, code.
_CHAT_USER_PROMPTS = [
    "Explain what a KV cache is in a large language model and why it matters for serving "
    "throughput.",
    "What are the key differences between TCP and UDP? Answer concisely.",
    "Write a short haiku about the ocean, then explain its imagery in one sentence.",
    "Translate 'The weather is beautiful today' into French, German, and Spanish.",
    "Write a Python function that computes Fibonacci numbers with memoization.",
]

# Deterministic filler sentences appended to prompt 1 until it tokenizes to exactly 256
# tokens (fixture-length discipline, the 0.6B race's 256-token convention carried over).
_FILLERS = [
    "Cover the memory cost of the cache as context grows.",
    "Mention how paged attention changes the allocation story.",
    "Keep the explanation suitable for a systems engineer.",
    "Describe what happens during prefill versus decode.",
    "Note the tradeoff between batch size and cache size.",
    "Explain why eviction policies matter under pressure.",
    "Give one concrete example with realistic numbers.",
    "Summarize the latency impact for long prompts.",
]


def _chat_ids(tokenizer, user_text: str) -> list:
    """Apply the checkpoint's own chat template once (add_generation_prompt on) and return the
    plain list of token ids. transformers >= 5 returns a dict ({'input_ids', 'attention_mask'})
    from apply_chat_template even with tokenize=True and no return_tensors, so unwrap both
    shapes — `len()` on the dict (2 keys) silently broke the fixture padding loop."""
    out = tokenizer.apply_chat_template(
        [{"role": "user", "content": user_text}],
        tokenize=True,
        add_generation_prompt=True,
    )
    # transformers >= 5 returns a BatchEncoding (a UserDict, NOT a dict subclass) holding
    # {'input_ids', 'attention_mask'} even with tokenize=True and no return_tensors; older
    # versions return a plain list. Unwrap by shape, not by isinstance(dict) — `len()` /
    # iteration on the mapping silently broke the fixture padding loop.
    if isinstance(out, (list, tuple)):
        ids_list = list(out)
    else:
        ids_list = out["input_ids"]
        if hasattr(ids_list, "tolist"):  # a tensor in some versions
            ids_list = ids_list.tolist()
    return [int(t) for t in ids_list]


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <hf-checkpoint-dir> [out-dir]", file=sys.stderr)
        return 2
    checkpoint_dir = Path(sys.argv[1]).expanduser()
    out_dir = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path("/tmp/w7b/ckpt")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)

    chat_entries = []
    fixture_ids = None
    fixture_text = None
    for index, user_text in enumerate(_CHAT_USER_PROMPTS):
        if index == 0:
            # Pad prompt 1 deterministically to exactly _FIXTURE_TOKENS tokens.
            texts = [user_text]
            ids = _chat_ids(tokenizer, "\n".join(texts))
            filler_index = 0
            while len(ids) < _FIXTURE_TOKENS:
                texts.append(_FILLERS[filler_index % len(_FILLERS)])
                filler_index += 1
                ids = _chat_ids(tokenizer, "\n".join(texts))
            if len(ids) != _FIXTURE_TOKENS:
                # Filler granularity overshot; pad token-exactly with neutral filler words.
                pad_words = ["cache", "batch", "token", "stream", "latency"]
                base = list(ids)
                while len(base) < _FIXTURE_TOKENS:
                    base.append(
                        tokenizer.encode(
                            " " + pad_words[len(base) % len(pad_words)],
                            add_special_tokens=False,
                        )[0]
                    )
                ids = base[:_FIXTURE_TOKENS]
            else:
                ids = ids[:_FIXTURE_TOKENS]
            fixture_ids = [int(t) for t in ids]
            fixture_text = tokenizer.decode(ids, skip_special_tokens=False)
            chat_entries.append(
                {"role_prompt": user_text, "rendered": fixture_text,
                 "ids": fixture_ids, "n_tokens": len(fixture_ids), "is_fixture": True}
            )
            continue
        ids = _chat_ids(tokenizer, user_text)
        rendered = tokenizer.decode(ids, skip_special_tokens=False)
        chat_entries.append(
            {"role_prompt": user_text, "rendered": rendered,
             "ids": [int(t) for t in ids], "n_tokens": len(ids), "is_fixture": False}
        )

    assert fixture_ids is not None and len(fixture_ids) == _FIXTURE_TOKENS
    print(f"[prepare_qwen25_7b] fixture prompt -> {len(fixture_ids)} tokens")
    for entry in chat_entries:
        print(f"[prepare_qwen25_7b] chat prompt ({entry['n_tokens']} tok): "
              f"{entry['role_prompt'][:60]}...")

    out = prepare_model_checkpoint(checkpoint_dir, fixture_ids, out_dir=out_dir)
    manifest_path = out / "manifest.json"
    blob_path = out / "weights.blob"
    if not manifest_path.is_file() or not blob_path.is_file():
        print("[prepare_qwen25_7b] FAIL: conversion did not write manifest.json + weights.blob",
              file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text())
    config = manifest["config"]
    checks = {
        "has_qk_norm": 0,           # Qwen2.5 has NO per-head QK-norm tensors
        "tie_word_embeddings": 0,   # Qwen2.5-7B-Instruct carries its own lm_head.weight
        "vocab_size": 152064,
        "head_dim": 128,
        "num_attention_heads": 28,
        "num_key_value_heads": 4,
        "intermediate_size": 18944,
    }
    for key, want in checks.items():
        got = config.get(key)
        if got != want:
            print(f"[prepare_qwen25_7b] FAIL: manifest config.{key} = {got!r}, want {want!r}",
                  file=sys.stderr)
            return 1
    if "lm_head.weight" not in manifest["tensors"]:
        print("[prepare_qwen25_7b] FAIL: lm_head.weight missing from the converted tensors",
              file=sys.stderr)
        return 1

    prompts_path = out / "prompts.json"
    prompts_path.write_text(json.dumps({
        "fixture": {"rendered": fixture_text, "ids": fixture_ids,
                    "n_tokens": len(fixture_ids)},
        "chat_prompts": chat_entries,
        "eos_token_id": config.get("eos_token_id"),
    }, indent=1), encoding="utf-8")

    print(f"[prepare_qwen25_7b] wrote {manifest_path} ({manifest_path.stat().st_size} B), "
          f"{blob_path} ({blob_path.stat().st_size} B), {prompts_path}")
    print(f"[prepare_qwen25_7b] manifest config: d_model={config['hidden_size']} "
          f"layers={config['num_hidden_layers']} h_q={config['num_attention_heads']} "
          f"h_kv={config['num_key_value_heads']} d_head={config['head_dim']} "
          f"d_ff={config['intermediate_size']} vocab={config['vocab_size']} "
          f"theta={config['rope_theta']} eps={config['rms_norm_eps']} "
          f"has_qk_norm={config['has_qk_norm']} tied={config['tie_word_embeddings']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
