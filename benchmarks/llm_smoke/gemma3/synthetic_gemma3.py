"""Synthetic Gemma 3 checkpoint generator (Gemma 3 lane, 2026-08-23).

Real Gemma 3 weights are license-gated and huge, so the ENGINE gates run on a SYNTHETIC
checkpoint that carries the gemma3 STRUCTURE verbatim -- every feature the kernels must honor,
at tiny dims:

  * the multimodal wrapper config (`model_type: gemma3`, text shape nested under `text_config`)
    exactly as google/gemma-3-27b-it ships it (same omissions: no rope_theta / rms_norm_eps /
    layer_types in the file -- the transformers class defaults the converter reproduces);
  * the safetensors tensor naming of the shipped snapshot (`language_model.model.*` prefix);
  * alternating sliding-window / full attention layers (the pattern-6 rule, or an explicit
    layer_types list), dual rope theta (global 1e6 + the config's linear factor 8 on global
    layers ONLY, local 1e4), per-head QK RMSNorm with Gemma's (1 + weight) gain convention on
    EVERY norm, the sqrt(hidden) input-embedding scale, GeGLU with gelu_pytorch_tanh, GQA,
    tied lm_head (untied variant optional), eos [1, 106].

Weight VALUES are seeded random dyadic fractions (k/128) -- exactly representable in BF16, F16
and F32 alike, so a byte/greedy identity gate cannot be perturbed by a storage-format round.

CLI:  python3 benchmarks/llm_smoke/gemma3/synthetic_gemma3.py --out /tmp/g3syn [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

# Default synthetic shape: small, but structurally COMPLETE. hidden/heads derive head_dim 32;
# every dim passes the kernel alignment gates (hidden%32, d_ff%32, h_q*d_head%32, h_q%h_kv).
DEFAULT_SHAPE: dict[str, Any] = {
    "hidden_size": 64,
    "num_hidden_layers": 6,
    "num_attention_heads": 4,
    "num_key_value_heads": 2,
    "head_dim": 32,
    "intermediate_size": 128,
    "vocab_size": 128,
    "sliding_window": 8,
    # pattern 2 -> layers 1, 3, 5 are full-attention; 0, 2, 4 sliding (a dense mix, so BOTH rope
    # tables and BOTH window classes are exercised within a few layers).
    "sliding_window_pattern": 2,
    "query_pre_attn_scalar": 32,
    # The real 27B config's exact rope_scaling shape: linear factor 8 on GLOBAL layers only.
    "rope_scaling": {"factor": 8.0, "rope_type": "linear"},
    "eos_token_id": [1, 106],
}


def layer_types_for(shape: dict[str, Any]) -> list[str]:
    """The transformers derivation: explicit layer_types win; else full iff (i+1)%pattern==0."""
    n_layers = shape["num_hidden_layers"]
    explicit = shape.get("layer_types")
    if explicit is not None:
        assert len(explicit) == n_layers
        return list(explicit)
    pattern = shape.get("sliding_window_pattern", 6)
    return [
        "full_attention" if (i + 1) % pattern == 0 else "sliding_attention"
        for i in range(n_layers)
    ]


def bf16_bytes(values: Any) -> bytes:
    """Float32/64 ndarray -> BF16 bytes (BF16 = the top 16 bits of FP32; the generator only
    emits dyadic values exactly representable at every width, so this is lossless)."""
    import numpy as np

    u32 = values.astype(np.float32).view(np.uint32)
    return (u32 >> 16).astype(np.uint16).tobytes()


def build_synthetic_gemma3(
    checkpoint_dir: str | Path,
    *,
    seed: int = 20260823,
    shape: dict[str, Any] | None = None,
    prefix: str = "language_model.",
    untied: bool = False,
    explicit_layer_types: bool = False,
    extra_text_config: dict[str, Any] | None = None,
) -> Path:
    """Write `config.json` + `model.safetensors` (+ an untied lm_head when asked) into
    `checkpoint_dir`. `prefix` selects the snapshot tensor naming (`language_model.` = the
    shipped v5 export, `model.language_model.` = older exports, `` = plain).
    `extra_text_config` merges arbitrary keys into the text config (the refusal tests use it to
    POISON the config with features the engine must reject)."""
    import numpy as np

    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULT_SHAPE, **(shape or {})}
    rng = np.random.default_rng(seed)

    hidden = merged["hidden_size"]
    n_layers = merged["num_hidden_layers"]
    h_q = merged["num_attention_heads"]
    h_kv = merged["num_key_value_heads"]
    d_head = merged["head_dim"]
    d_ff = merged["intermediate_size"]
    vocab = merged["vocab_size"]

    text_config: dict[str, Any] = {
        "model_type": "gemma3_text",
        "hidden_size": hidden,
        "num_hidden_layers": n_layers,
        "num_attention_heads": h_q,
        "num_key_value_heads": h_kv,
        "head_dim": d_head,
        "intermediate_size": d_ff,
        "vocab_size": vocab,
        "sliding_window": merged["sliding_window"],
        "query_pre_attn_scalar": merged["query_pre_attn_scalar"],
        "torch_dtype": "bfloat16",
        # Deliberately OMITTED, exactly like the shipped 27B config: rope_theta,
        # rope_local_theta, rms_norm_eps, layer_types, hidden_activation -- the converters must
        # supply the transformers class defaults (global theta 1e6 / local 1e4 / eps 1e-6 /
        # pattern-6 layer mix / gelu_pytorch_tanh).
    }
    if merged.get("rope_scaling") is not None:
        text_config["rope_scaling"] = merged["rope_scaling"]
    if explicit_layer_types:
        text_config["layer_types"] = layer_types_for(merged)
    else:
        text_config["sliding_window_pattern"] = merged.get("sliding_window_pattern", 6)
    if extra_text_config:
        text_config.update(extra_text_config)

    config = {
        "architectures": ["Gemma3ForConditionalGeneration"],
        "model_type": "gemma3",
        "eos_token_id": merged["eos_token_id"],
        "text_config": text_config,
        "torch_dtype": "bfloat16",
    }
    (checkpoint_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def dyadic(*shape_dims: int, scale_pow: int) -> Any:
        """Integers scaled by 2**-scale_pow: exact in BF16/F16/F32."""
        integers = rng.integers(-8, 9, size=shape_dims)
        return integers.astype(np.float64) * (2.0 ** (-scale_pow))

    tensors: dict[str, tuple[list[int], bytes]] = {}

    def add(name: str, *shape_dims: int, scale_pow: int = 7) -> None:
        tensors[name] = (list(shape_dims), bf16_bytes(dyadic(*shape_dims, scale_pow=scale_pow)))

    # Scale choices: wide enough that the greedy logits are DIVERSE (a repetition attractor
    # would mask an engine bug in the identity gate), still dyadic = exact at every width.
    p = prefix  # text-tensor prefix inside the snapshot
    add(p + "model.embed_tokens.weight", vocab, hidden, scale_pow=5)
    add(p + "model.norm.weight", hidden, scale_pow=3)
    for layer in range(n_layers):
        base = f"{p}model.layers.{layer}."
        add(base + "input_layernorm.weight", hidden, scale_pow=3)
        add(base + "post_attention_layernorm.weight", hidden, scale_pow=3)
        add(base + "pre_feedforward_layernorm.weight", hidden, scale_pow=3)
        add(base + "post_feedforward_layernorm.weight", hidden, scale_pow=3)
        add(base + "self_attn.q_norm.weight", d_head, scale_pow=3)
        add(base + "self_attn.k_norm.weight", d_head, scale_pow=3)
        add(base + "self_attn.q_proj.weight", h_q * d_head, hidden, scale_pow=3)
        add(base + "self_attn.k_proj.weight", h_kv * d_head, hidden, scale_pow=3)
        add(base + "self_attn.v_proj.weight", h_kv * d_head, hidden, scale_pow=3)
        add(base + "self_attn.o_proj.weight", hidden, h_q * d_head, scale_pow=3)
        add(base + "mlp.gate_proj.weight", d_ff, hidden, scale_pow=3)
        add(base + "mlp.up_proj.weight", d_ff, hidden, scale_pow=3)
        add(base + "mlp.down_proj.weight", hidden, d_ff, scale_pow=3)
    if untied:
        lm_prefix = prefix if prefix else ""
        add(lm_prefix + "lm_head.weight", vocab, hidden, scale_pow=5)

    header: dict[str, Any] = {}
    body = b""
    for name, (shape, raw) in tensors.items():
        header[name] = {
            "dtype": "BF16",
            "shape": shape,
            "data_offsets": [len(body), len(body) + len(raw)],
        }
        body += raw
    header_json = json.dumps(header).encode("utf-8")
    (checkpoint_dir / "model.safetensors").write_bytes(
        struct.pack("<Q", len(header_json)) + header_json + body
    )
    return checkpoint_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--untied", action="store_true")
    parser.add_argument(
        "--prefix", default="language_model.",
        help="snapshot tensor prefix (language_model. | model.language_model. | '')",
    )
    args = parser.parse_args()
    path = build_synthetic_gemma3(args.out, seed=args.seed, untied=args.untied, prefix=args.prefix)
    print(f"synthetic gemma3 checkpoint -> {path}")
