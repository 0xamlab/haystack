"""prepare_qwen3_checkpoint.py — convert a real Qwen3-0.6B-Base checkpoint into the flat, row-major
float64 buffers the Mojo LLM-plane kernels expect, plus a matching `transformers`-CPU reference
forward pass to check the Mojo result against.

This is a one-time, local data-prep step. It writes NOTHING into git: every artifact lands under
`--out` (default `/tmp/bb/qwen3_ckpt`), which is regenerable from the HuggingFace checkpoint alone.

Why the weights are pre-transposed
-----------------------------------
`gemm.blocked.sgemm_flat`'s fast SIMD path takes `B` as `[k, n]` row-major. PyTorch's `nn.Linear`
weight is `[out, in]` row-major (`y = x @ W^T`). Transposing once here — rather than calling
`sgemm_flat(..., trans_b=True)` at every layer — means the forward pass exercises the kernel's fast
path instead of its scalar fallback, without changing a single frozen kernel.

Why the embedding table is NOT transposed
-------------------------------------------
Qwen3-0.6B-Base ties `lm_head` to `embed_tokens` (`tie_word_embeddings: true`). The embedding gather
wants `[vocab, d_model]` row-major (`mlpk.embedding.embedding_fwd_flat`'s contract), and the untied
`lm_head` projection `logits = hidden @ embed^T` is exactly `gemm.blocked.gemv_flat(embed, hidden,
m=vocab, n=d_model, trans=False)` on that SAME storage — `y[i] = sum_j embed[i,j] * hidden[j]`. So one
copy of the table serves both the gather and the untied-projection-in-disguise, and there is no
177 MB-per-buffer ceiling to route around (`gemv_flat` does not carry `gemm.contract`'s
`GEMM_MAX_DIM_ELEMS` per-operand check — `sgemm_flat` does, and `k * n = 1024 * 151936` would trip it).
"""

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
import torch
from safetensors import safe_open


def log(msg: str) -> None:
    print(f"[prepare_qwen3_checkpoint] {msg}", file=sys.stderr, flush=True)


def dump_f64(path: Path, arr: np.ndarray) -> None:
    arr = np.ascontiguousarray(arr.astype("<f8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(arr.tobytes())


def dump_i64(path: Path, arr: np.ndarray) -> None:
    arr = np.ascontiguousarray(arr.astype("<i8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(arr.tobytes())


def to_f64(t: torch.Tensor) -> np.ndarray:
    """bf16 (or whatever the checkpoint stores) -> float32 -> float64, the same upcast path a
    `torch_dtype=torch.float32` reference load takes, so the two sides start from the same bits."""
    return t.to(torch.float32).to(torch.float64).numpy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True, help="local HF snapshot dir (config.json + model.safetensors)")
    ap.add_argument("--out", default="/tmp/bb/qwen3_ckpt")
    ap.add_argument("--prompt", default="The capital of France is")
    args = ap.parse_args()

    ckpt = Path(args.checkpoint)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with open(ckpt / "config.json") as f:
        cfg = json.load(f)
    log(f"config: {cfg}")

    n_layers = cfg["num_hidden_layers"]
    d_model = cfg["hidden_size"]
    n_heads = cfg["num_attention_heads"]
    n_kv_heads = cfg["num_key_value_heads"]
    head_dim = cfg["head_dim"]
    d_ff = cfg["intermediate_size"]
    vocab = cfg["vocab_size"]
    eps = cfg["rms_norm_eps"]
    theta = float(cfg["rope_theta"])
    assert cfg["tie_word_embeddings"] is True
    assert cfg["attention_bias"] is False
    assert cfg["hidden_act"] == "silu"

    manifest = {
        "n_layers": n_layers,
        "d_model": d_model,
        "n_heads": n_heads,
        "n_kv_heads": n_kv_heads,
        "head_dim": head_dim,
        "d_ff": d_ff,
        "vocab": vocab,
        "eps": eps,
        "rope_theta": theta,
    }

    st_path = ckpt / "model.safetensors"
    with safe_open(str(st_path), framework="pt") as f:
        def get(name: str) -> torch.Tensor:
            return f.get_tensor(name)

        embed = get("model.embed_tokens.weight")  # [vocab, d_model]
        dump_f64(out / "embed_tokens.f64.bin", to_f64(embed))
        log(f"embed_tokens {tuple(embed.shape)} -> {out/'embed_tokens.f64.bin'}")

        final_norm = get("model.norm.weight")
        dump_f64(out / "final_norm.f64.bin", to_f64(final_norm))

        for i in range(n_layers):
            p = f"model.layers.{i}."
            ln1 = get(p + "input_layernorm.weight")
            ln2 = get(p + "post_attention_layernorm.weight")
            wq = get(p + "self_attn.q_proj.weight")  # [n_heads*head_dim, d_model]
            wk = get(p + "self_attn.k_proj.weight")  # [n_kv_heads*head_dim, d_model]
            wv = get(p + "self_attn.v_proj.weight")
            wo = get(p + "self_attn.o_proj.weight")  # [d_model, n_heads*head_dim]
            qn = get(p + "self_attn.q_norm.weight")  # [head_dim]
            kn = get(p + "self_attn.k_norm.weight")
            wg = get(p + "mlp.gate_proj.weight")  # [d_ff, d_model]
            wu = get(p + "mlp.up_proj.weight")  # [d_ff, d_model]
            wd = get(p + "mlp.down_proj.weight")  # [d_model, d_ff]

            dump_f64(out / f"layer_{i}_input_layernorm.f64.bin", to_f64(ln1))
            dump_f64(out / f"layer_{i}_post_attention_layernorm.f64.bin", to_f64(ln2))
            # Pre-transposed to [in, out] row-major for sgemm_flat's fast (non-transposed) path.
            dump_f64(out / f"layer_{i}_q_proj_T.f64.bin", to_f64(wq.T))
            dump_f64(out / f"layer_{i}_k_proj_T.f64.bin", to_f64(wk.T))
            dump_f64(out / f"layer_{i}_v_proj_T.f64.bin", to_f64(wv.T))
            dump_f64(out / f"layer_{i}_o_proj_T.f64.bin", to_f64(wo.T))
            dump_f64(out / f"layer_{i}_q_norm.f64.bin", to_f64(qn))
            dump_f64(out / f"layer_{i}_k_norm.f64.bin", to_f64(kn))
            dump_f64(out / f"layer_{i}_gate_proj_T.f64.bin", to_f64(wg.T))
            dump_f64(out / f"layer_{i}_up_proj_T.f64.bin", to_f64(wu.T))
            dump_f64(out / f"layer_{i}_down_proj_T.f64.bin", to_f64(wd.T))
            log(f"layer {i} dumped")

    # Tokenize the prompt with the real tokenizer and dump the id sequence.
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(ckpt))
    ids = tok(args.prompt, return_tensors=None)["input_ids"]
    log(f"prompt {args.prompt!r} -> {len(ids)} tokens: {ids}")
    manifest["prompt"] = args.prompt
    manifest["n_tok"] = len(ids)
    dump_i64(out / "prompt_ids.i64.bin", np.array(ids, dtype=np.int64))

    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    log(f"manifest -> {out/'manifest.json'}")

    # ---- Reference forward pass, transformers on CPU, float32 (same upcast as the Mojo weights) ----
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(str(ckpt), torch_dtype=torch.float32)
    model.eval()
    input_ids = torch.tensor([ids], dtype=torch.long)
    with torch.no_grad():
        out_obj = model(input_ids, output_hidden_states=True)
    logits = out_obj.logits[0].to(torch.float64).numpy()  # [n_tok, vocab]
    hidden_states = out_obj.hidden_states  # tuple: embeddings, then one per layer (n_layers+1 total)

    dump_f64(out / "ref_logits.f64.bin", logits)
    for i, hs in enumerate(hidden_states):
        dump_f64(out / f"ref_hidden_{i}.f64.bin", hs[0].to(torch.float64).numpy())
    log(f"reference logits shape {logits.shape}, {len(hidden_states)} hidden-state snapshots dumped")

    top5 = np.argsort(-logits[-1])[:5]
    log(f"reference greedy next-token top5 (last position): {[(int(t), float(logits[-1][t])) for t in top5]}")
    decoded = tok.decode([int(top5[0])])
    log(f"reference argmax next token decodes to: {decoded!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
