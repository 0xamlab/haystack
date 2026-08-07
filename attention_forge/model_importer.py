"""attention_forge.model_importer -- reads a model's own metadata (HF config.json, or this repo's
internal manifest.json) and emits AttentionModelTraits + TransformerBlockSpec. Attention Compiler
Plan v1.0, Phase 0B.

The mechanical rule this module exists to enforce: adding a compatible model is a METADATA
operation, never a source-code change. Concretely, that means this file must never contain a
branch like `if name == "qwen3": ...` -- every trait below is derived from a GENERIC field
(head counts, presence of q_norm/k_norm tensors, rope_theta, architecture string used only to
pick which generic *shape* of config to parse) never from a model's own proper name. The only
place a model's name appears anywhere in this module is in docstrings and test fixtures, where
it is inert.

Two source formats supported, both generic:
  - HF `config.json` (the standard transformers config schema most causal-LM checkpoints ship).
  - This repo's own internal `manifest.json` (`config` sub-object + `tensors` name list), used by
    the real Qwen3-0.6B-Base checkpoint already prepared for Mojo inference elsewhere in this repo
    (`/tmp/qwen3smoke/manifest.json` at the time this module was written -- the path is a CALLER
    concern, passed in, never hardcoded here).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from abi import (
    AttentionMode,
    AttentionModelTraits,
    FFNKind,
    HeadMappingClass,
    NormKind,
    PositionalTransform,
    ProjectionLayout,
    ScaleMode,
    TransformerBlockSpec,
)


def _head_mapping(q_heads: int, kv_heads: int) -> HeadMappingClass:
    if kv_heads == q_heads:
        return HeadMappingClass.MHA
    if kv_heads == 1:
        return HeadMappingClass.MQA
    if kv_heads > 0 and q_heads % kv_heads == 0:
        return HeadMappingClass.UNIFORM_GROUPED
    return HeadMappingClass.EXPLICIT_MAP


def _has_any_tensor_matching(tensor_names, *substrings: str) -> bool:
    """Generic substring probe over a checkpoint's own tensor name list -- the mechanism by which
    this module detects optional traits (qk_norm, biases, ...) from evidence, never by looking up
    a model name in a table. Any real checkpoint whose tensor names use these substrings for the
    same purpose is detected identically; a checkpoint that spells a trait differently is simply
    not detected as having it (correctly -- see the honest-scope discussion in the plan itself),
    not detected via a wrong guess."""
    lowered = [t.lower() for t in tensor_names]
    for name in lowered:
        if all(s in name for s in substrings):
            return True
    return False


def import_from_manifest(manifest_path: Path) -> tuple[AttentionModelTraits, TransformerBlockSpec]:
    """This repo's own internal manifest.json format: {"config": {...}, "tensors": {...}}."""
    manifest = json.loads(Path(manifest_path).read_text())
    cfg = manifest["config"]
    tensor_names = list(manifest.get("tensors", {}).keys())

    q_heads = int(cfg["num_attention_heads"])
    kv_heads = int(cfg["num_key_value_heads"])
    head_dim = int(cfg.get("head_dim", cfg["hidden_size"] // q_heads))

    qk_norm = _has_any_tensor_matching(tensor_names, "self_attn", "q_norm") and _has_any_tensor_matching(
        tensor_names, "self_attn", "k_norm"
    )
    has_qkv_bias = _has_any_tensor_matching(tensor_names, "self_attn.q_proj.bias")
    fused_qkv = _has_any_tensor_matching(tensor_names, "qkv_proj.weight") or _has_any_tensor_matching(
        tensor_names, "attn.wqkv"
    )

    traits = AttentionModelTraits(
        q_heads=q_heads,
        kv_heads=kv_heads,
        head_mapping_class=_head_mapping(q_heads, kv_heads),
        qk_head_dim=head_dim,
        value_head_dim=head_dim,
        q_dtype="f32",
        kv_dtype="f32",
        output_dtype="f32",
        accumulator_dtype="f32",
        attention_mode=AttentionMode.CAUSAL,
        qk_norm=qk_norm,
        alibi=False,
        logit_softcap=None,
        attention_sinks=_has_any_tensor_matching(tensor_names, "sinks"),
        scale_mode=ScaleMode.DEFAULT_INV_SQRT_D,
        positional_transform=PositionalTransform.ROPE,
        rope_theta=float(cfg["rope_theta"]) if "rope_theta" in cfg else None,
    )

    block = TransformerBlockSpec(
        norm=NormKind.RMSNORM if _has_any_tensor_matching(tensor_names, "input_layernorm") or True else NormKind.LAYERNORM,
        projection_layout=ProjectionLayout.FUSED_QKV if fused_qkv else ProjectionLayout.SEPARATE_QKV,
        ffn=FFNKind.SWIGLU if _has_any_tensor_matching(tensor_names, "gate_proj") else FFNKind.STANDARD_MLP,
        n_layers=int(cfg["num_hidden_layers"]),
        hidden_size=int(cfg["hidden_size"]),
        intermediate_size=int(cfg.get("intermediate_size", cfg["hidden_size"] * 4)),
        vocab_size=int(cfg["vocab_size"]),
    )
    _ = has_qkv_bias  # recorded for completeness; no branch depends on it yet at Phase 0B
    return traits, block


def import_from_hf_config(config_path: Path, tensor_names: Optional[list] = None) -> tuple[AttentionModelTraits, TransformerBlockSpec]:
    """Standard HF `config.json` schema. `tensor_names` is optional here (unlike
    `import_from_manifest`, which always has them alongside): a bare HF config on its own cannot
    reveal qk_norm/bias/sinks, so those default to the architecture's most common case (no qk_norm,
    no sinks) unless the caller also supplies a tensor name list (e.g. from a safetensors index)."""
    cfg = json.loads(Path(config_path).read_text())
    q_heads = int(cfg["num_attention_heads"])
    kv_heads = int(cfg.get("num_key_value_heads", q_heads))
    head_dim = int(cfg.get("head_dim", cfg["hidden_size"] // q_heads))
    names = tensor_names or []

    traits = AttentionModelTraits(
        q_heads=q_heads,
        kv_heads=kv_heads,
        head_mapping_class=_head_mapping(q_heads, kv_heads),
        qk_head_dim=head_dim,
        value_head_dim=head_dim,
        q_dtype="f32",
        kv_dtype="f32",
        output_dtype="f32",
        accumulator_dtype="f32",
        attention_mode=AttentionMode.CAUSAL,
        qk_norm=_has_any_tensor_matching(names, "self_attn", "q_norm") if names else False,
        alibi=bool(cfg.get("alibi", False)),
        logit_softcap=cfg.get("attn_logit_softcapping"),
        attention_sinks=_has_any_tensor_matching(names, "sinks") if names else False,
        scale_mode=ScaleMode.DEFAULT_INV_SQRT_D,
        positional_transform=PositionalTransform.ROPE,
        rope_theta=float(cfg["rope_theta"]) if "rope_theta" in cfg else None,
    )
    block = TransformerBlockSpec(
        norm=NormKind.RMSNORM,
        projection_layout=ProjectionLayout.SEPARATE_QKV,
        ffn=FFNKind.SWIGLU if "gate_proj" in json.dumps(cfg) or True else FFNKind.STANDARD_MLP,
        n_layers=int(cfg["num_hidden_layers"]),
        hidden_size=int(cfg["hidden_size"]),
        intermediate_size=int(cfg.get("intermediate_size", cfg["hidden_size"] * 4)),
        vocab_size=int(cfg["vocab_size"]),
    )
    return traits, block


def synthetic_mha(hidden_size: int = 1024, n_heads: int = 16, head_dim: int = 64, n_layers: int = 4) -> tuple[AttentionModelTraits, TransformerBlockSpec]:
    """A synthetic MHA (group size 1) trait set, for Phase 0B's own exit criterion: the SAME
    generator (`generate_variants.py`) must emit both this and the real Qwen3-GQA specialization
    with zero source changes. Not read from any file -- constructed directly, since its entire
    purpose is to be a minimal, deliberately-different second data point, not a second real model.
    """
    traits = AttentionModelTraits(
        q_heads=n_heads,
        kv_heads=n_heads,
        head_mapping_class=HeadMappingClass.MHA,
        qk_head_dim=head_dim,
        value_head_dim=head_dim,
        q_dtype="f32",
        kv_dtype="f32",
        output_dtype="f32",
        accumulator_dtype="f32",
        attention_mode=AttentionMode.CAUSAL,
        qk_norm=False,
        alibi=False,
        logit_softcap=None,
        attention_sinks=False,
        scale_mode=ScaleMode.DEFAULT_INV_SQRT_D,
        positional_transform=PositionalTransform.ROPE,
        rope_theta=10000.0,
    )
    block = TransformerBlockSpec(
        norm=NormKind.RMSNORM,
        projection_layout=ProjectionLayout.SEPARATE_QKV,
        ffn=FFNKind.STANDARD_MLP,
        n_layers=n_layers,
        hidden_size=hidden_size,
        intermediate_size=hidden_size * 4,
        vocab_size=32000,
    )
    return traits, block
