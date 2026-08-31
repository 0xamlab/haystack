"""Model-agnostic LLM inference on Apple Silicon, through the real compiled runtime.

This is the model-agnostic door onto the Metal GPU kernel path. Unlike `algenta.qwen3_decode`
(which is pinned to Qwen3-0.6B-Base's exact shape), this module accepts ANY model whose architecture
the kernels support and routes it to the model-agnostic entry point, so one call works across model
sizes without a per-shape SDK function.

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
* **Architecture family, not one shape.** The kernels implement the Qwen3/llama decoder family (GQA,
  SiLU-gated FFN, RoPE, no attention bias; per-head QK RMSNorm optional -- present in Qwen3, absent
  in llama-family -- and the lm_head either tied to the input embedding or its own matrix). Any model
  matching those structural invariants and the kernel alignment gates (d_model / d_ff / n_q divisible
  by 32, GQA ratio integral) runs; anything else raises `UnsupportedArchitectureError` naming the exact
  mismatch. This is "any model within the supported family," not "any architecture ever" -- no other
  architecture family has kernels yet. Rope scaling: the llama-3.1+ `rope_scaling` ("llama3" scheme)
  is applied to the rope frequency table; GGUF files carrying llama.cpp's baked `rope_freqs.weight`
  tensor reproduce those frequencies verbatim; any other scaling scheme is refused (never silently
  unscaled).
* **One hardware family**: Apple Silicon with Metal. A binary built without `-D ALGENTA_GPU`, or a
  host with no Metal accelerator, raises `InferenceError` with a status naming exactly that -- never a
  silent CPU fallback.
* **Greedy by default, seeded sampling on request.** `temperature=0` (default) is the fused
  lm_head+argmax kernel path. `temperature > 0` draws each token from the model's own distribution
  (penalties -> temperature -> top-k -> min-p -> top-p -> seeded weighted draw), deterministic per
  seed.
* **Text or token ids in; both out.** Pass `prompt_text` for the checkpoint's own tokenizer
  (`algenta.tokenizer`, a from-scratch implementation of its `tokenizer.json` -- no external
  tokenizer dependency, oracle-validated byte-for-byte against `transformers` in
  `tests/test_tokenizer_qwen3.py`), or `prompt_token_ids` if you already have ids. With
  `prompt_text` the result also carries the detokenized `generated_text`; token ids are always
  returned either way. (The tokenizer is BPE encode/decode only -- no chat template yet.)

Usage
-----
    from algenta import MojoRuntime
    from algenta.inference import decode, prepare_model_checkpoint

    runtime = MojoRuntime(mode="local")
    result = decode(
        runtime,
        checkpoint_dir="/path/to/any/supported-model",   # your own downloaded HF snapshot
        prompt_text="The capital of France is",          # text in (uses the checkpoint's tokenizer)
        max_new_tokens=16,
        # The engine sizes its own context as max(512, n_prompt + max_new_tokens); `max_ctx`
        # is a caller-side guard only (values below that need are refused).
    )
    result.generated_text                                  # text out (because prompt_text was used)
    result.token_ids                                       # ids always available
    result.decode_tokens_per_sec
    result.prefill_tokens_per_sec

Checkpoint conversion, and why it is a separate, inspectable step
------------------------------------------------------------------
The kernel reads weights from a flat `manifest.json` + `weights.blob` pair, not from a raw
HuggingFace snapshot directly. `prepare_model_checkpoint()` is a model-agnostic converter (reads the
checkpoint's own `config.json` for the shape, handles single- or multi-shard safetensors, pre-
transposes the GEMM weights the kernels expect, and writes the same flat format the production
session reads). Conversion STREAMS one tensor at a time -- peak host memory is O(one tensor / one
tile), independent of model size, so small hosts convert models far bigger than their RAM (the
pre-streaming path materialized the whole model several times at once and peaked ~30 GB on a
Qwen3-0.6B checkpoint). `decode()` calls it for you; call it directly to convert once and reuse
the result across many decode calls.

GGUF model files, the llama.cpp interchange format
--------------------------------------------------
`prepare_model_checkpoint_from_gguf()` is the SAME converter with a GGUF front door: a dependency-
free, byte-level GGUF container reader (struct parsing, the same style as the safetensors reader)
that reads the metadata hyperparameters and the tensor table, widens F16/F32 tensors and
dequantizes Q8_0 / Q4_0 / Q5_0 and the Q4_K / Q5_K / Q6_K K-quants (ggml's exact block formulas)
to the same Float64 weight stream, maps the llama.cpp tensor names (`blk.N.attn_q.weight`,
`token_embd.weight`, ...) onto the HF names the manifest contract uses, and writes the IDENTICAL
`manifest.json` + `weights.blob` pair -- so everything past conversion is the untouched production
path. `decode()` accepts a `.gguf` file directly as `checkpoint_dir`, with `prompt_token_ids` OR
`prompt_text` -- a GGUF EMBEDS its tokenizer in its metadata, and `algenta.tokenizer` builds it
from those tables (the llama SentencePiece BPE, llama.cpp's exact conventions). `messages` works
the same way when the GGUF embeds one of the chat-template revisions `algenta.chat_template`
implements.
"""

from __future__ import annotations

import json
import struct
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = [
    "InferenceError",
    "InferenceResult",
    "BatchedInferenceResult",
    "StreamedToken",
    "UnsupportedArchitectureError",
    "prepare_model_checkpoint",
    "prepare_model_checkpoint_from_gguf",
    "decode",
    "decode_batched",
    "decode_stream",
]

_MODULE_NAME = "metaldispatch.qwen3_prefill_decode"
_FUNCTION_NAME = "qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3"
_FUNCTION_NAME_SAMPLED = "qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3_sampled"
_FUNCTION_NAME_BATCHED = "qwen3_batched_prefill_decode_anyqwen3"
_CONVERSION_CACHE_DIRNAME = ".algenta-cache"
_BATCH_DECODE_MAX_SEQS = 32

# GEMM weights the engine consumes pre-transposed [out,in] -> [in,out]; embed and norm weights stay
# native. Same set as `generate_manifest_anyqwen3.py`'s `_TRANSPOSE_SUFFIXES`.
_TRANSPOSE_SUFFIXES = (
    "self_attn.q_proj.weight",
    "self_attn.k_proj.weight",
    "self_attn.v_proj.weight",
    "self_attn.o_proj.weight",
    "mlp.gate_proj.weight",
    "mlp.up_proj.weight",
    "mlp.down_proj.weight",
)

# Structural invariants the kernels rely on for ANY supported-family model. Checked from the
# checkpoint's own config.json before any conversion or GPU work.
_STRUCTURAL_FIELDS = (
    "hidden_size",
    "num_hidden_layers",
    "num_attention_heads",
    "num_key_value_heads",
    "head_dim",
    "intermediate_size",
    "vocab_size",
    "rope_theta",
    "rms_norm_eps",
)


class InferenceError(RuntimeError):
    """An inference call refused to run, or the runtime call itself failed.

    `code` is a stable string: either one of `metaldispatch.contract`'s own status names surfaced
    verbatim from the Mojo side, or a client-side code raised before the wire call was attempted.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UnsupportedArchitectureError(InferenceError):
    """The checkpoint's architecture is not one the kernels support.

    Raised on the Python side, before any conversion or GPU work, from the checkpoint's own
    `config.json` -- the cheapest possible point to refuse a shape or family the kernels cannot run.
    """

    def __init__(self, message: str) -> None:
        super().__init__("unsupported_architecture", message)


@dataclass(frozen=True)
class InferenceResult:
    """One inference call's whole outcome. `token_ids` is prompt tokens followed by every generated
    token, in order -- empty only when the call raised before this result could be built.
    `generated_text` is the detokenized generation, present only when the call was made with
    `prompt_text` (token-id calls stay pure token math and never load the tokenizer)."""

    token_ids: list[int]
    n_prompt: int
    stopped_on_eos: bool
    dispatches_per_token: int
    decode_tokens_per_sec: float
    prefill_tokens_per_sec: float
    generated_text: str | None = None


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Fill in shape fields a family may leave implicit, so validation + the manifest see a complete
    config. Llama-family checkpoints omit `head_dim` (it is implicit `hidden_size //
    num_attention_heads`); Qwen3 carries it explicitly -- and note the two are NOT the same formula
    for Qwen3 (its q/k/v project to `h_q * head_dim`, which differs from `hidden_size`), so an
    already-present `head_dim` is always trusted, never re-derived. Gemma 3 checkpoints ship a
    MULTIMODAL wrapper config (`model_type=gemma3`) whose text shape lives in the nested
    `text_config`; this lifts that nested config (tagged `model_type=gemma3_text`) and carries the
    wrapper's `eos_token_id` list with it. Returns a new dict; the caller's config is not
    mutated."""
    if config.get("model_type") == "gemma3" and isinstance(config.get("text_config"), dict):
        text = dict(config["text_config"])
        text["model_type"] = "gemma3_text"
        if "eos_token_id" in config and config["eos_token_id"] is not None:
            text.setdefault("_gemma3_eos_token_ids", config["eos_token_id"])
        config = text
    # Gemma 3's head_dim is INDEPENDENT of hidden_size // heads (q/k/v project to h_q*head_dim,
    # a different number), exactly like Qwen3 -- so the implicit-head_dim derivation below must not
    # run for it; _gemma3_prepare_config supplies the Gemma3TextConfig class default instead.
    if (
        "head_dim" not in config
        and config.get("model_type") != "gemma3_text"
        and "hidden_size" in config
        and "num_attention_heads" in config
    ):
        h_q = config["num_attention_heads"]
        if isinstance(h_q, int) and h_q > 0:
            return {**config, "head_dim": config["hidden_size"] // h_q}
    return config


# Gemma 3 (Gemma 3 lane, 2026-08-23): architecture facts VERIFIED against the shipped
# google/gemma-3-27b-it config.json + transformers 5.15.1's configuration_gemma3.py /
# modeling_gemma3.py (the checkpoint's own config.json omits them; transformers' Gemma3TextConfig
# class defaults supply exactly these values when the file loads):
#   * rms_norm_eps 1e-6; EVERY RMSNorm (layer norms, q/k norm, final norm) uses Gemma's
#     `(1.0 + weight)` gain convention -- weights ship zero-centered, so (1+w) is the gain.
#   * rope theta: GLOBAL (full-attention) layers 1_000_000.0, LOCAL (sliding-window) layers
#     10_000.0 (`default_theta = {"global": 1_000_000.0, "local": 10_000.0}`).
#   * the config's rope_scaling {rope_type: linear, factor: 8.0} applies to the GLOBAL layers ONLY
#     (transformers' convert_rope_params_to_dict updates `full_attention` with it): the global
#     inverse frequencies are divided by the factor. Local layers stay unscaled.
#   * layer types derive from sliding_window_pattern=6 when the config omits `layer_types`:
#     layer i is full-attention iff (i + 1) % 6 == 0.
#   * attention score scale is `query_pre_attn_scalar ** -0.5` (27B ships 168), NOT head_dim-based.
#   * input embeddings are scaled by sqrt(hidden_size); the lm_head is the TIED embedding table
#     WITHOUT that scale; MLP activation is GeGLU with the tanh-approx GELU (gelu_pytorch_tanh).
#   * eos: the wrapper config ships [1, 106] (<eos>, <end_of_turn>).
_GEMMA3_DEFAULT_RMS_NORM_EPS = 1e-6
_GEMMA3_DEFAULT_ROPE_THETA_GLOBAL = 1_000_000.0
_GEMMA3_DEFAULT_ROPE_THETA_LOCAL = 10_000.0
_GEMMA3_DEFAULT_SLIDING_WINDOW_PATTERN = 6
_GEMMA3_DEFAULT_QUERY_PRE_ATTN_SCALAR = 256
_GEMMA3_DEFAULT_VOCAB_SIZE = 262_208  # Gemma3TextConfig class default; the 27B file omits it
_GEMMA3_ACTIVATION_CODE_GELU_TANH = 1  # manifest int: 0 = silu (Qwen3/llama), 1 = gelu_pytorch_tanh


def _gemma3_layer_types(config: dict[str, Any], checkpoint_dir: Path) -> list[str]:
    """The per-layer attention class list, exactly as transformers derives it: the config's own
    `layer_types` when present (values validated), else the sliding_window_pattern=6 rule --
    layer i is `full_attention` iff (i + 1) % pattern == 0."""
    n_layers = config["num_hidden_layers"]
    layer_types = config.get("layer_types")
    if layer_types is not None:
        if (
            not isinstance(layer_types, list)
            or len(layer_types) != n_layers
            or any(value not in ("sliding_attention", "full_attention") for value in layer_types)
        ):
            raise UnsupportedArchitectureError(
                f"unsupported model architecture: {checkpoint_dir} gemma3 config declares "
                f"layer_types={layer_types!r}; expected {n_layers} entries, each "
                "'sliding_attention' or 'full_attention'."
            )
        return list(layer_types)
    pattern = config.get("sliding_window_pattern", _GEMMA3_DEFAULT_SLIDING_WINDOW_PATTERN)
    if isinstance(pattern, bool) or not isinstance(pattern, int) or pattern < 1:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} gemma3 config declares "
            f"sliding_window_pattern={pattern!r}; expected a positive int."
        )
    return [
        "full_attention" if (i + 1) % pattern == 0 else "sliding_attention"
        for i in range(n_layers)
    ]


def _gemma3_prepare_config(config: dict[str, Any], checkpoint_dir: Path) -> dict[str, Any]:
    """Complete + validate a lifted gemma3_text config, returning the manifest's gemma3-specific
    entries. Refuses (never silently adapts) any Gemma 3 feature the kernels do not implement:
    logit softcapping of either kind, bidirectional attention, q/k/v projection biases, any
    rope_scaling other than the shipped linear scheme, and any activation other than
    gelu_pytorch_tanh -- each would otherwise run with silently-wrong math."""
    if config.get("attn_logit_softcapping") is not None or config.get("final_logit_softcapping") is not None:
        raise UnsupportedArchitectureError(
            "unsupported model architecture: this gemma3 checkpoint enables logit softcapping "
            "(attn_logit_softcapping / final_logit_softcapping); the kernels do not implement it."
        )
    if config.get("use_bidirectional_attention"):
        raise UnsupportedArchitectureError(
            "unsupported model architecture: gemma3 use_bidirectional_attention=true is not "
            "supported (causal generation only)."
        )
    if config.get("attention_bias"):
        raise UnsupportedArchitectureError(
            "unsupported model architecture: gemma3 attention_bias=true (q/k/v projection "
            "biases) is not supported."
        )
    hidden_activation = config.get("hidden_activation", "gelu_pytorch_tanh")
    if hidden_activation != "gelu_pytorch_tanh":
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: gemma3 hidden_activation={hidden_activation!r}; "
            "only 'gelu_pytorch_tanh' (the shipped Gemma 3 activation) is implemented."
        )

    # Shape fields transformers' Gemma3TextConfig defaults supply when the file omits them.
    config = {**config}
    if "rms_norm_eps" not in config:
        config["rms_norm_eps"] = _GEMMA3_DEFAULT_RMS_NORM_EPS
    if "vocab_size" not in config:
        config["vocab_size"] = _GEMMA3_DEFAULT_VOCAB_SIZE
    # The head fields are OMITTED by the smaller shipped checkpoints (1B/4B set none of them;
    # 12B/27B set them explicitly), and transformers supplies these exact class defaults at load
    # -- verified for the 4B against its safetensors (q_proj [2048, 2560] = 8 heads x head_dim
    # 256). Reproduce that here rather than deriving head_dim from hidden_size // heads, which is
    # wrong for Gemma 3 (its q/k/v project to h_q * head_dim != hidden_size).
    config.setdefault("num_attention_heads", 8)
    config.setdefault("num_key_value_heads", 4)
    config.setdefault("head_dim", 256)
    sliding_window = config.get("sliding_window")
    if isinstance(sliding_window, bool) or not isinstance(sliding_window, int) or sliding_window < 1:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: gemma3 sliding_window={sliding_window!r}; expected "
            "a positive int."
        )

    layer_types = _gemma3_layer_types(config, checkpoint_dir)

    # Rope: global theta (+ the config's linear rope_scaling, global layers ONLY), local theta.
    rope_theta_global = _GEMMA3_DEFAULT_ROPE_THETA_GLOBAL
    rope_theta_local = _GEMMA3_DEFAULT_ROPE_THETA_LOCAL
    rope_global_scaling_factor = 1.0
    rope_scaling = config.get("rope_scaling")
    if isinstance(rope_scaling, dict):
        rope_type = str(rope_scaling.get("rope_type", rope_scaling.get("type", ""))).lower()
        factor = rope_scaling.get("factor")
        if rope_type not in ("none", "") or factor is not None:
            if rope_type != "linear":
                raise UnsupportedArchitectureError(
                    f"unsupported model architecture: gemma3 rope_scaling type {rope_type!r}; "
                    "only the shipped linear scheme (or none) is implemented."
                )
            if (
                isinstance(factor, bool)
                or not isinstance(factor, int | float)
                or factor <= 0
            ):
                raise UnsupportedArchitectureError(
                    f"unsupported model architecture: gemma3 rope_scaling.factor={factor!r}; "
                    "expected a positive number."
                )
            rope_global_scaling_factor = float(factor)
    elif rope_scaling is not None:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: gemma3 rope_scaling={rope_scaling!r}; expected a "
            "dict or null."
        )
    if isinstance(config.get("rope_theta"), int | float) and not isinstance(
        config.get("rope_theta"), bool
    ):
        rope_theta_global = float(config["rope_theta"])
    if isinstance(config.get("rope_local_theta"), int | float) and not isinstance(
        config.get("rope_local_theta"), bool
    ):
        rope_theta_local = float(config["rope_local_theta"])

    query_pre_attn_scalar = config.get(
        "query_pre_attn_scalar", _GEMMA3_DEFAULT_QUERY_PRE_ATTN_SCALAR
    )
    if (
        isinstance(query_pre_attn_scalar, bool)
        or not isinstance(query_pre_attn_scalar, int | float)
        or query_pre_attn_scalar <= 0
    ):
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: gemma3 query_pre_attn_scalar="
            f"{query_pre_attn_scalar!r}; expected a positive number."
        )

    eos = config.get("_gemma3_eos_token_ids", config.get("eos_token_id"))
    eos_ids: list[int] = []
    if isinstance(eos, int) and not isinstance(eos, bool):
        eos_ids = [eos]
    elif isinstance(eos, list) and all(
        isinstance(value, int) and not isinstance(value, bool) for value in eos
    ):
        eos_ids = list(eos)
    if not eos_ids:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: gemma3 config carries no usable eos_token_id "
            f"({eos!r})."
        )

    import math

    manifest_entries: dict[str, Any] = {
        "model_family": "gemma3",
        # Family-convention flags the gemma3 session branches on (ints, json_get_int pattern):
        # activation 1 = GeGLU with gelu_pytorch_tanh; norm_weight_plus_one 1 = every RMSNorm
        # applies (1.0 + weight) as its gain (the converter rebases the shipped weights so the
        # engine's gain-multiply kernels compute exactly Gemma's math); embed_scale = the
        # sqrt(hidden_size) input-embedding factor (NOT applied on the tied lm_head side).
        "activation_code": _GEMMA3_ACTIVATION_CODE_GELU_TANH,
        "norm_weight_plus_one": 1,
        "embed_scale": math.sqrt(config["hidden_size"]),
        "query_pre_attn_scalar": float(query_pre_attn_scalar),
        "sliding_window": int(sliding_window),
        # 1 = full-attention layer, 0 = sliding-window (local) layer -- the engine's per-layer
        # window + rope-table selection reads this verbatim.
        "layer_types": [1 if layer == "full_attention" else 0 for layer in layer_types],
        "rope_theta": rope_theta_global,
        "rope_local_theta": rope_theta_local,
        "rope_global_scaling_factor": rope_global_scaling_factor,
        "eos_token_ids": eos_ids,
    }
    config["_gemma3_manifest_entries"] = manifest_entries
    # rope_theta now present for _validate_architecture's structural-field gate.
    config["rope_theta"] = rope_theta_global
    # Single-id compat key for readers that predate the eos_token_ids list: prefer <end_of_turn>
    # (the stop token gemma3-it actually emits at turn end), else the first declared id. The
    # gemma3 engine reads the FULL list from eos_token_ids and stops on any of them.
    config["eos_token_id"] = 106 if 106 in eos_ids else eos_ids[0]
    return config


def _validate_architecture(
    checkpoint_dir: Path, config: dict[str, Any], *, config_source: str = "config.json"
) -> None:
    """Validate the structural invariants the kernels rely on, from the checkpoint's own shape
    declaration alone (`config_source` names where that declaration came from -- config.json for a
    HuggingFace snapshot, GGUF metadata for a .gguf file -- so refusals point at the right file).

    Model-agnostic conformance (2026-08-23): the gate is a PURE lookup into the declared
    capability table (`algenta.model_capabilities`) -- every fact the kernels rely on is judged by
    `refusals_for_facts` against the SUPPORTED FACT RANGES, never against a family name. Facts the
    config declares but no kernel implements (a sliding window, an attention-logit softcap, a
    non-SiLU activation, a per-layer layer-type pattern, a second rope base, a partial rotary
    factor, a non-1/sqrt(head_dim) attention scale) are REFUSED here -- never silently ignored,
    because ignoring them runs fluent-but-wrong math. The weight-level facts (qk_norm/bias tensor
    presence, unsupported-tensor sweep) are judged by `prepare_model_checkpoint` AFTER the tensors
    are probed -- tensors are the truth, configs can lie or omit."""
    missing = [key for key in _STRUCTURAL_FIELDS if key not in config]
    if missing:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} {config_source} is missing required "
            f"fields: {', '.join(missing)}. This module runs decoder configs whose facts meet the "
            "declared capability table (hidden_size, num_hidden_layers, num_attention_heads, "
            "num_key_value_heads, head_dim, intermediate_size, vocab_size, rope_theta, "
            "rms_norm_eps)."
        )
    # The architecture gate is BACKEND-AGNOSTIC: conversion serves every backend
    # (the gemma3 CUDA lane converts through this same door as the Metal path),
    # so it judges the structural + family fact ranges only (enforce_backend=
    # False) -- backend membership, bias availability and staging tiers are facts
    # of the backend that RUNS the model, judged by the conform CLI and the
    # probe-stage gates below, never by conversion. The probe facts stay None
    # here (judged after the tensors are read), so the bias gate cannot fire on
    # the config's own `attention_bias` key -- tensors are the truth.
    from algenta.model_capabilities import extract_facts_from_config, refusals_for_facts

    facts = extract_facts_from_config(config)
    refusals = refusals_for_facts(facts, backend="metal", probed=True, enforce_backend=False)
    if refusals:
        problems = "; ".join(
            f"{refusal.fact}={refusal.value!r} is not supported (supported: {refusal.supported})"
            for refusal in refusals
        )
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} ({config_source}) is not a "
            f"supported model. Problems: {problems}."
        )


def _read_safetensors_header(path: Path) -> tuple[dict[str, Any], int]:
    """Byte-level safetensors header parse: 8-byte little-endian length, then that many bytes of
    JSON. Returns `(header, data_start)`."""
    with path.open("rb") as handle:
        (header_len,) = struct.unpack("<Q", handle.read(8))
        header = json.loads(handle.read(header_len))
    return header, 8 + header_len


def _bf16_bytes_to_f64(raw: bytes) -> Any:
    """Exact BF16 -> Float64 widen (BF16 is the top 16 bits of FP32)."""
    import numpy as np

    u16 = np.frombuffer(raw, dtype="<u2")
    u32 = u16.astype(np.uint32) << 16
    return u32.view(np.float32).astype(np.float64)


# Host-memory ceiling of the streaming converter (2026-08-20): the BF16 -> Float64 widen and the
# blob write run in tiles of this many elements, so conversion peaks at O(one tensor / one tile)
# of host RAM, independent of model size. The pre-streaming path materialized EVERY tensor's
# Float64 values at once and then ran the whole model through three more full copies (entries
# list + np.concatenate + astype + tobytes) -- a Qwen3-0.6B BF16 checkpoint peaked at ~30 GB and
# OOMed the NVIDIA race's 16 GB VMs. At 4 Mi elements one tile's transient footprint is ~56 MiB
# (2 B/element of BF16 view + 4 B/element u32 widen + 8 B/element f64 out).
_STREAM_TILE_ELEMENTS = 4 * 1024 * 1024


def _bf16_bytes_to_f64_tiles(raw: bytes) -> Iterator[Any]:
    """Exact BF16 -> Float64 widen streamed in `_STREAM_TILE_ELEMENTS` tiles: concatenating the
    yielded arrays is BIT-identical to `_bf16_bytes_to_f64(raw)` -- the widen is element-wise, so
    tiling it cannot change a single value. The tiles VIEW `raw` (no copy of the BF16 bytes)."""
    import numpy as np

    n_elements = len(raw) // 2
    for start in range(0, n_elements, _STREAM_TILE_ELEMENTS):
        count = min(_STREAM_TILE_ELEMENTS, n_elements - start)
        u16 = np.frombuffer(raw, dtype="<u2", count=count, offset=start * 2)
        yield (u16.astype(np.uint32) << 16).view(np.float32).astype(np.float64)


def _bf16_bytes_to_f64_transposed(raw: bytes, shape: list[int]) -> Any:
    """Exact BF16 -> Float64 widen of a `[rows, cols]` tensor, returned flat in the PRE-TRANSPOSED
    order (`[cols, rows]` row-major) the kernels consume -- the exact values
    `_bf16_bytes_to_f64(raw).reshape(shape).T.copy().reshape(-1)` produces, but filled row-tile by
    row-tile so the transient ON TOP of the output buffer is O(tile), never a second full-tensor
    copy. The output buffer itself is the one tensor-sized allocation an exact in-memory transpose
    cannot avoid (and the GEMM weights it serves are the small hidden-x-hidden matrices, never the
    embedding table)."""
    import numpy as np

    rows, cols = shape
    out = np.empty((cols, rows), dtype=np.float64)
    tile_rows = max(1, _STREAM_TILE_ELEMENTS // cols)
    for r0 in range(0, rows, tile_rows):
        r1 = min(rows, r0 + tile_rows)
        u16 = np.frombuffer(raw, dtype="<u2", count=(r1 - r0) * cols, offset=r0 * cols * 2)
        wide = (u16.astype(np.uint32) << 16).view(np.float32).astype(np.float64)
        out[:, r0:r1] = wide.reshape(r1 - r0, cols).T
    return out.reshape(-1)


def _write_f64_streamed(handle: Any, values: Any) -> None:
    """Write one tensor's Float64 values as the exact little-endian f8 bytes the session weight
    loaders read, in tiles so the transient `tobytes()` copy is O(tile). `astype("<f8",
    copy=False)` is a no-op view on a little-endian float64 array -- the bytes written are exactly
    what the pre-streaming path's `values.astype("<f8").tobytes()` wrote."""
    arr = values.astype("<f8", copy=False)
    for start in range(0, arr.size, _STREAM_TILE_ELEMENTS):
        handle.write(arr[start : start + _STREAM_TILE_ELEMENTS].tobytes())


def _write_f32_streamed(handle: Any, values: Any) -> None:
    """The Float32-blob twin (Gemma 3 lane): the same streamed write narrowed to little-endian f4.
    Used ONLY when the converter is asked for a `weights_dtype="f32"` blob (a 27B-class model's
    f64 blob exceeds a race VM's disk; every value written originates as BF16, which Float32
    represents EXACTLY, so the narrowed blob is bit-exact the session's own f32 weights)."""
    arr = values.astype("<f4")
    for start in range(0, arr.size, _STREAM_TILE_ELEMENTS):
        handle.write(arr[start : start + _STREAM_TILE_ELEMENTS].tobytes())


def _resolve_shard_for_tensor(
    checkpoint_dir: Path, tensor_name: str, index: dict[str, Any] | None
) -> Path:
    """Map a tensor name to its safetensors shard. Single-shard checkpoints have no index; multi-
    shard checkpoints carry `model.safetensors.index.json` with a `weight_map`."""
    if index is None:
        single = checkpoint_dir / "model.safetensors"
        if single.is_file():
            return single
        raise InferenceError(
            "checkpoint_not_found",
            f"{checkpoint_dir} has no model.safetensors and no model.safetensors.index.json.",
        )
    weight_map = index.get("weight_map") or {}
    shard_name = weight_map.get(tensor_name)
    if shard_name is None:
        raise InferenceError(
            "checkpoint_not_found",
            f"tensor {tensor_name!r} is not listed in {checkpoint_dir}/model.safetensors.index.json.",
        )
    shard_path = checkpoint_dir / shard_name
    if not shard_path.is_file():
        raise InferenceError(
            "checkpoint_not_found", f"{shard_path} (shard for {tensor_name!r}) is missing."
        )
    return shard_path


# The manifest's `rope_scaling_type` code for the llama-3.1 "llama3" scheme -- an int because the
# Mojo side reads it with json_get_int (same family-convention pattern as has_qk_norm). 0/absent
# means no scaling. The Mojo half (metaldispatch.qwen3_prefill_decode._rope_table_from_manifest +
# attnk.rope.rope_table_llama3) adjusts the rope inverse frequencies on these keys.
_ROPE_SCALING_TYPE_LLAMA3_CODE = 3

# HF transformers defaults for the llama3 scheme when a config omits the factors (every shipped
# llama-3.1 checkpoint uses exactly these values).
_ROPE_SCALING_DEFAULT_LOW_FREQ_FACTOR = 1.0
_ROPE_SCALING_DEFAULT_HIGH_FREQ_FACTOR = 4.0


def _validate_rope_scaling(config: dict[str, Any], *, config_source: str) -> None:
    """Llama-3.1+ rope_scaling (llama-3.1+ configs carry `rope_scaling: {rope_type: llama3, ...}`):
    the ONLY scheme the engine implements is "llama3" -- absent/none/`None` needs nothing, and any
    other scheme (linear, yarn, longrope, ...) is REFUSED here rather than silently running with an
    unscaled rope (a wrong rope does not crash; it produces fluent text that degrades with context
    -- the exact silent-wrong-math hazard the architecture gate exists to prevent)."""
    rope_scaling = config.get("rope_scaling")
    if rope_scaling is None:
        return
    if not isinstance(rope_scaling, dict):
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {config_source} declares rope_scaling="
            f"{rope_scaling!r}; expected a rope-scaling dict or null."
        )
    rope_type = rope_scaling.get("rope_type", rope_scaling.get("type"))
    if rope_type is None or str(rope_type).lower() == "none":
        return
    if str(rope_type).lower() != "llama3":
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {config_source} declares rope_scaling type "
            f"{rope_type!r}; only the llama3 scheme is implemented (absent/none or "
            "rope_type='llama3'). Running with an unimplemented scaling silently would leave the "
            "rope unscaled -- fluent output that degrades with context."
        )

    def _positive_number(name: str, value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            raise UnsupportedArchitectureError(
                f"unsupported model architecture: rope_scaling.{name} is {value!r}; expected a "
                "positive number."
            )
        return float(value)

    factor = _positive_number("factor", rope_scaling.get("factor"))
    orig = _positive_number(
        "original_max_position_embeddings",
        rope_scaling.get("original_max_position_embeddings"),
    )
    low = _positive_number(
        "low_freq_factor",
        rope_scaling.get("low_freq_factor", _ROPE_SCALING_DEFAULT_LOW_FREQ_FACTOR),
    )
    high = _positive_number(
        "high_freq_factor",
        rope_scaling.get("high_freq_factor", _ROPE_SCALING_DEFAULT_HIGH_FREQ_FACTOR),
    )
    if high <= low:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: rope_scaling.high_freq_factor ({high}) must exceed "
            f"low_freq_factor ({low}) or the llama3 interpolation is degenerate."
        )
    if orig < 1:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: rope_scaling.original_max_position_embeddings is "
            f"{orig!r}; expected at least 1."
        )
    del factor  # validated here, re-read by _rope_scaling_manifest_entries


def _rope_scaling_manifest_entries(config: dict[str, Any]) -> dict[str, Any]:
    """The flat numeric manifest keys the Mojo entry points read (json_get_int/json_get_float)
    when the checkpoint carries a llama3 rope_scaling -- validated by `_validate_rope_scaling`
    before this runs. Absent/none scaling contributes nothing (a pre-scaling manifest consumer
    then sees no new keys at all)."""
    rope_scaling = config.get("rope_scaling")
    if not isinstance(rope_scaling, dict):
        return {}
    rope_type = rope_scaling.get("rope_type", rope_scaling.get("type"))
    if rope_type is None or str(rope_type).lower() == "none":
        return {}
    return {
        "rope_scaling_type": _ROPE_SCALING_TYPE_LLAMA3_CODE,
        "rope_scaling_factor": float(rope_scaling["factor"]),
        "rope_scaling_low_freq_factor": float(
            rope_scaling.get("low_freq_factor", _ROPE_SCALING_DEFAULT_LOW_FREQ_FACTOR)
        ),
        "rope_scaling_high_freq_factor": float(
            rope_scaling.get("high_freq_factor", _ROPE_SCALING_DEFAULT_HIGH_FREQ_FACTOR)
        ),
        "rope_scaling_original_max_position_embeddings": int(
            rope_scaling["original_max_position_embeddings"]
        ),
    }


_QK_NORM_PROBE_TENSOR = "model.layers.0.self_attn.q_norm.weight"


def _detect_has_qk_norm(checkpoint_dir: Path, index: dict[str, Any] | None) -> bool:
    """Llama-family support (2026-08-13): whether the checkpoint carries per-head QK RMSNorm gain
    tensors, detected by the presence of layer 0's `self_attn.q_norm.weight` in the safetensors
    (never by config.json -- some configs lie about or omit this; the tensors are the truth the
    engine consumes). Qwen3 checkpoints have them; llama-family checkpoints do not. The engine gets
    the answer as the manifest's `has_qk_norm` and routes the ropewrt kernels' norm block on it."""
    if index is None:
        single = checkpoint_dir / "model.safetensors"
        if not single.is_file():
            raise InferenceError(
                "checkpoint_not_found",
                f"{checkpoint_dir} has no model.safetensors and no model.safetensors.index.json.",
            )
        header, _ = _read_safetensors_header(single)
        return _QK_NORM_PROBE_TENSOR in header
    weight_map = index.get("weight_map") or {}
    if _QK_NORM_PROBE_TENSOR not in weight_map:
        return False
    shard_path = checkpoint_dir / weight_map[_QK_NORM_PROBE_TENSOR]
    if not shard_path.is_file():
        raise InferenceError(
            "checkpoint_not_found",
            f"{shard_path} (shard for {_QK_NORM_PROBE_TENSOR!r}) is missing.",
        )
    header, _ = _read_safetensors_header(shard_path)
    return _QK_NORM_PROBE_TENSOR in header


_ATTENTION_BIAS_PROBE_TENSOR = "model.layers.0.self_attn.q_proj.bias"


def _detect_attention_bias(checkpoint_dir: Path, index: dict[str, Any] | None) -> bool:
    """7B-lane support (2026-08-23): whether the checkpoint carries q/k/v projection BIAS tensors,
    detected by the presence of layer 0's `self_attn.q_proj.bias` in the safetensors -- the same
    tensors-are-the-truth convention `_detect_has_qk_norm` uses, for the same reason: Qwen2.5's
    config.json OMITS `attention_bias` entirely while the model defaults it TRUE (its q/k/v
    projections carry biases), so a config-key check silently let a bias-carrying checkpoint
    through unconverted -- the 7B lane's layer-0 qkv divergence root cause. Qwen3 has no biases;
    Qwen2/Qwen2.5 do. The engine gets the answer as the manifest's `attention_bias`."""
    if index is None:
        single = checkpoint_dir / "model.safetensors"
        if not single.is_file():
            raise InferenceError(
                "checkpoint_not_found",
                f"{checkpoint_dir} has no model.safetensors and no model.safetensors.index.json.",
            )
        header, _ = _read_safetensors_header(single)
        return _ATTENTION_BIAS_PROBE_TENSOR in header
    weight_map = index.get("weight_map") or {}
    if _ATTENTION_BIAS_PROBE_TENSOR not in weight_map:
        return False
    shard_path = checkpoint_dir / weight_map[_ATTENTION_BIAS_PROBE_TENSOR]
    if not shard_path.is_file():
        raise InferenceError(
            "checkpoint_not_found",
            f"{shard_path} (shard for {_ATTENTION_BIAS_PROBE_TENSOR!r}) is missing.",
        )
    header, _ = _read_safetensors_header(shard_path)
    return _ATTENTION_BIAS_PROBE_TENSOR in header


# Gemma 3 safetensors tensor naming (Gemma 3 lane, 2026-08-23): the shipped
# google/gemma-3-27b-it snapshot is a MULTIMODAL export -- its text tensors live under the
# `language_model.` wrapper (transformers v5 convention: `language_model.model.embed_tokens.weight`);
# older exports nest one level deeper (`model.language_model.model.*`). The converter probes these
# prefixes and remaps onto the canonical `model.*` names the manifest contract uses, skipping the
# vision tower entirely (text-only engine).
_GEMMA3_TEXT_PREFIX_CANDIDATES = ("language_model.", "model.language_model.", "")

# RMSNorm gain tensors the gemma3 converter REBASES to (1.0 + w) before writing the blob: Gemma's
# convention is out = norm(x) * (1.0 + weight) and the engine's norm kernels multiply by the
# stored gain -- storing the rebased gain makes those kernels compute Gemma's math EXACTLY with
# zero kernel changes. The manifest's norm_weight_plus_one=1 records the blob convention.
_GEMMA3_NORM_GAIN_SUFFIXES = (
    "input_layernorm.weight",
    "post_attention_layernorm.weight",
    "pre_feedforward_layernorm.weight",
    "post_feedforward_layernorm.weight",
    "self_attn.q_norm.weight",
    "self_attn.k_norm.weight",
)


def _safetensors_has_tensor(checkpoint_dir: Path, index: dict[str, Any] | None, name: str) -> bool:
    """Whether `name` exists in the checkpoint's safetensors (single-shard header or the index's
    weight_map), used for prefix/tie probes where absence is an answer, not an error."""
    if index is None:
        single = checkpoint_dir / "model.safetensors"
        if not single.is_file():
            return False
        header, _ = _read_safetensors_header(single)
        return name in header
    return name in (index.get("weight_map") or {})


def _gemma3_probe_prefix(checkpoint_dir: Path, index: dict[str, Any] | None) -> str:
    """The text-tensor prefix of a gemma3 snapshot (probed by embed_tokens presence); raises when
    no candidate matches (corrupt/partial snapshot)."""
    for prefix in _GEMMA3_TEXT_PREFIX_CANDIDATES:
        if _safetensors_has_tensor(checkpoint_dir, index, f"{prefix}model.embed_tokens.weight"):
            return prefix
    raise InferenceError(
        "checkpoint_not_found",
        f"{checkpoint_dir} is a gemma3 checkpoint with no recognizable text-tensor prefix "
        f"(probed for model.embed_tokens.weight under {_GEMMA3_TEXT_PREFIX_CANDIDATES}).",
    )


# Tensors the engine does NOT consume and would therefore SILENTLY DROP if the
# conversion proceeded: biases beyond the supported q/k/v set (an o_proj or an
# mlp bias changes the math), probed at layer 0 in the same tensors-are-the-
# truth convention as the qk-norm/bias probes. A checkpoint carrying any of
# these is refused with the exact tensor name -- never converted with the
# weights dropped (the exact silent-wrong-math hazard the fact gates exist to
# prevent). The q/k/v projection biases are NOT here: they are the supported
# `attention_bias` fact when the backend applies them. (Gemma 3 snapshots use
# prefixed tensor names and their own validated required set; this sweep is
# the qwen3/llama naming convention.)
_UNSUPPORTED_PROBE_TENSORS = (
    "model.layers.0.self_attn.o_proj.bias",
    "model.layers.0.mlp.gate_proj.bias",
    "model.layers.0.mlp.up_proj.bias",
    "model.layers.0.mlp.down_proj.bias",
    "model.layers.0.mlp.bias",
)


def _detect_unsupported_tensors(checkpoint_dir: Path, index: dict[str, Any] | None) -> list[str]:
    """The unsupported probe tensors the checkpoint actually carries (empty for
    every supported-family checkpoint). Same probe mechanics as
    `_detect_has_qk_norm`: single-shard header or multi-shard weight map."""
    if index is None:
        single = checkpoint_dir / "model.safetensors"
        if not single.is_file():
            return []
        header, _ = _read_safetensors_header(single)
        present = {name for name in _UNSUPPORTED_PROBE_TENSORS if name in header}
    else:
        weight_map = index.get("weight_map") or {}
        present = set()
        for name in _UNSUPPORTED_PROBE_TENSORS:
            shard_name = weight_map.get(name)
            if shard_name is None:
                continue
            shard_path = checkpoint_dir / shard_name
            if not shard_path.is_file():
                continue
            header, _ = _read_safetensors_header(shard_path)
            if name in header:
                present.add(name)
    return sorted(present)


def _load_checkpoint_index(checkpoint_dir: Path) -> Any:
    """The shard-index fact for a checkpoint: `False` when NO safetensors are
    present at all (a config-only conform run -- nothing to probe), `None` for
    a single-shard `model.safetensors`, and the parsed
    `model.safetensors.index.json` dict for a multi-shard snapshot. `None` vs
    dict is exactly the argument `_detect_has_qk_norm`/`_detect_attention_bias`
    take."""
    index_path = checkpoint_dir / "model.safetensors.index.json"
    if index_path.is_file():
        return json.loads(index_path.read_text(encoding="utf-8"))
    if (checkpoint_dir / "model.safetensors").is_file():
        return None
    return False


def _validate_prompt_token_ids(prompt_token_ids: Any) -> None:
    """The prompt-id contract every converter shares: a non-empty list of non-negative ints."""
    if not isinstance(prompt_token_ids, list) or not prompt_token_ids:
        raise InferenceError(
            "invalid_arguments", "prompt_token_ids must be a non-empty list of token ids"
        )
    for token_id in prompt_token_ids:
        if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
            raise InferenceError(
                "invalid_arguments", f"prompt_token_ids must be non-negative ints, got {token_id!r}"
            )


def _required_hf_tensor_names(
    n_layers: int, tied_embeddings: bool, has_qk_norm: bool,
    attention_bias: bool = False,
    gemma3: bool = False,
) -> list[str]:
    """The HF tensor names a supported-family checkpoint must deliver to the manifest, in the same
    convention both converters (safetensors and GGUF) agree on."""
    required = ["model.embed_tokens.weight", "model.norm.weight"]
    if not tied_embeddings:
        # Untied llama-family checkpoints carry their OWN output projection; the engine binds it
        # as a separate lm_head matrix. A tied checkpoint (Qwen3) reuses the embedding table and
        # has no lm_head.weight tensor to convert.
        required.append("lm_head.weight")
    for layer in range(n_layers):
        prefix = f"model.layers.{layer}."
        suffixes = [
            "input_layernorm.weight",
            "post_attention_layernorm.weight",
        ]
        if gemma3:
            # Gemma 3 keeps gemma2's four-norm layer: post_attention_layernorm normalizes the
            # attention output BEFORE its residual add, and the MLP path carries its own
            # pre/post_feedforward pair around the GeGLU block.
            suffixes += [
                "pre_feedforward_layernorm.weight",
                "post_feedforward_layernorm.weight",
            ]
        if has_qk_norm:
            # Qwen3 convention. Llama-family checkpoints have no q_norm/k_norm tensors; the engine
            # runs the ropewrt kernels with the norm block skipped (manifest `has_qk_norm`=0).
            suffixes += ["self_attn.q_norm.weight", "self_attn.k_norm.weight"]
        suffixes += [
            "self_attn.q_proj.weight",
            "self_attn.k_proj.weight",
            "self_attn.v_proj.weight",
            "self_attn.o_proj.weight",
            "mlp.gate_proj.weight",
            "mlp.up_proj.weight",
            "mlp.down_proj.weight",
        ]
        if attention_bias:
            # Qwen2/Qwen2.5 convention (7B-lane, 2026-08-23): the q/k/v projections carry BIAS
            # vectors the engine adds to the fused QKV output before RoPE. 1-D, never transposed.
            suffixes += [
                "self_attn.q_proj.bias",
                "self_attn.k_proj.bias",
                "self_attn.v_proj.bias",
            ]
        required += [prefix + suffix for suffix in suffixes]
    return required


def _write_converted_checkpoint(
    resolved_out_dir: Path,
    *,
    entries: Iterable[tuple[str, Iterable[Any], list[int], bool]],
    config: dict[str, Any],
    prompt_token_ids: list[int],
    has_qk_norm: bool,
    tied_embeddings: bool,
    rope_freq_factors: list[float] | None = None,
    attention_bias: bool = False,
    extra_manifest_config: dict[str, Any] | None = None,
    weights_dtype: str = "f64",
    llama_rope_scaling: bool = True,
) -> Path:
    """The shared converter tail: STREAM the per-tensor Float64 values (already widened and,
    where the kernels want it, pre-transposed) into `weights.blob` one tensor at a time, and
    write the `manifest.json` the production session reads. Both `prepare_model_checkpoint()`
    (safetensors) and `prepare_model_checkpoint_from_gguf()` (GGUF) end here, so the pair they
    produce is the SAME format, written by the SAME code.

    `weights_dtype` selects the blob element width: "f64" (default -- byte-for-byte the
    pre-Gemma-3 format; the manifest carries no `weights_dtype` key, so an older reader sees no
    difference) or "f32" (half the disk, exact for BF16-origin weights; the manifest carries
    `weights_dtype: "f32"` so readers size their slices correctly). `extra_manifest_config`
    merges family-specific keys (e.g. the gemma3 convention set) into the manifest's config
    object after the shared keys.

    `entries` is an iterable of `(hf_name, f64 value chunks, shape, transposed)` -- a GENERATOR
    keeps host memory at O(one tensor): the blob grows by sequential append and no whole-model
    buffer ever exists. (The pre-streaming tail held every tensor's Float64 values in an entries
    list and then ran the whole model through np.concatenate, astype and tobytes -- four
    whole-model buffers at once.) Each tensor's chunks concatenate to exactly its flat values, so
    the bytes written are exactly the pre-streaming tail's. """
    if weights_dtype not in ("f64", "f32"):
        raise InferenceError(
            "invalid_arguments", f"weights_dtype must be 'f64' or 'f32', got {weights_dtype!r}"
        )
    write_streamed = _write_f64_streamed if weights_dtype == "f64" else _write_f32_streamed
    blob_path = resolved_out_dir / "weights.blob"
    manifest_tensors: dict[str, Any] = {}
    cursor = 0
    try:
        with blob_path.open("wb") as blob_out:
            for name, value_chunks, shape, transposed in entries:
                n_elements = 1
                for dim in shape:
                    n_elements *= dim
                written = 0
                for chunk in value_chunks:
                    write_streamed(blob_out, chunk)
                    written += chunk.size
                if written != n_elements:
                    raise InferenceError(
                        "checkpoint_not_found",
                        f"tensor {name!r} converted to {written} Float64 values but its shape "
                        f"{shape} declares {n_elements} -- the converter and the checkpoint "
                        "disagree about this tensor's contents.",
                    )
                manifest_tensors[name] = {
                    "offset": cursor,
                    "n_elements": int(n_elements),
                    "shape": shape,
                    "transposed": transposed,
                }
                cursor += n_elements
    except BaseException:
        # A mid-stream failure (a later shard missing or corrupt) must not leave a PARTIAL blob
        # behind: the pre-streaming tail converted every tensor before writing anything, so a
        # failure left the output directory empty. Keep that contract.
        blob_path.unlink(missing_ok=True)
        raise

    manifest_config: dict[str, Any] = {
        "hidden_size": config["hidden_size"],
        "num_hidden_layers": config["num_hidden_layers"],
        "num_attention_heads": config["num_attention_heads"],
        "num_key_value_heads": config["num_key_value_heads"],
        "head_dim": config["head_dim"],
        "intermediate_size": config["intermediate_size"],
        "vocab_size": config["vocab_size"],
        "rope_theta": float(config["rope_theta"]),
        "rms_norm_eps": config["rms_norm_eps"],
        "n_tokens": len(prompt_token_ids),
        # Family-convention flags the engine's kernels branch on (llama-family support, 2026-08-13):
        # has_qk_norm=1 applies the Qwen3 per-head QK RMSNorm before RoPE, 0 rotates the raw
        # projections (llama-family, whose checkpoints carry no q_norm/k_norm tensors);
        # tie_word_embeddings=1 reuses the embedding table as lm_head, 0 binds the separately
        # converted lm_head.weight; attention_bias=1 adds the converted q/k/v projection biases
        # to the fused QKV output before RoPE (Qwen2/Qwen2.5), 0 leaves the pre-bias convention.
        # Ints (0/1) because the Mojo side reads them with json_get_int.
        "has_qk_norm": 1 if has_qk_norm else 0,
        "tie_word_embeddings": 1 if tied_embeddings else 0,
        "attention_bias": 1 if attention_bias else 0,
    }
    if weights_dtype == "f32":
        # Absent key == f64: a pre-Gemma-3 reader sees no difference on an f64 blob.
        manifest_config["weights_dtype"] = "f32"
    if extra_manifest_config:
        manifest_config.update(extra_manifest_config)
    # End-of-sequence id(s) the engine should stop on, carried from the checkpoint's own config
    # instead of a hardcoded constant. Absent on some configs -- only written when present, so an
    # older manifest consumer sees no new key unless the checkpoint declares one.
    if "eos_token_id" in config and config["eos_token_id"] is not None:
        manifest_config["eos_token_id"] = config["eos_token_id"]

    # Rope scaling (llama-3.1+, 2026-08-14). EXPLICIT per-pair frequency factors (a GGUF
    # `rope_freqs.weight` tensor, the exact divisors ggml applies) take precedence -- they carry
    # the source's own baked values verbatim; otherwise the parametric llama3 scheme from the
    # checkpoint config (validated by `_validate_rope_scaling` before either converter reaches
    # here). A checkpoint with NO scaling writes neither key, and a pre-scaling engine reading
    # this manifest behaves byte-for-byte as it always did. Gemma 3 sets llama_rope_scaling=False:
    # its rope is a DIFFERENT convention (dual per-layer-class theta + a linear factor on the
    # global layers) carried by its own extra_manifest_config keys, so the llama3 entries must
    # not fire on its `rope_scaling` dict.
    if llama_rope_scaling:
        if rope_freq_factors:
            manifest_config["rope_freq_factors"] = [float(value) for value in rope_freq_factors]
        else:
            manifest_config.update(_rope_scaling_manifest_entries(config))

    manifest = {
        "config": manifest_config,
        "input_ids": list(prompt_token_ids),
        "tensors": manifest_tensors,
    }
    (resolved_out_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return resolved_out_dir


# --- GGUF loading (beat-llama.cpp campaign, model-coverage front: llama.cpp users have .gguf
# model files; this is the door that runs them on the same engine) ------------------------------
#
# A dependency-free, byte-level GGUF container reader, the same style as the safetensors reader
# above: struct parsing only, no external dependency. GGUF layout (versions 2 and 3): 4-byte magic
# `GGUF`, u32 version, u64 tensor count, u64 metadata-kv count, then that many metadata kv pairs
# (string key, u32 type tag, typed value), then the tensor-info table (string name, u32 n_dims,
# u64 dims[n_dims], u32 ggml dtype, u64 offset), then padding up to the alignment (default 32,
# `general.alignment` metadata overrides), then the raw tensor bytes -- each tensor's data at
# `data_start + offset`. GGUF records a matrix's dims in REVERSE of HuggingFace row-major order
# (ggml's contiguous dim first: [in, out]), so the HF shape is the dims list reversed.

_GGUF_MAGIC = b"GGUF"
_GGUF_DEFAULT_ALIGNMENT = 32

# ggml tensor data types this converter reads. F16 + F32 cover the common `--outtype f16` export
# (weight matrices F16, norm vectors F32); Q8_0 (per-32-element-block f16 scale + 32 int8) covers
# the most common quantized export. Q4_0/Q5_0 (32-element blocks) and the Q4_K/Q5_K/Q6_K
# "K-quant" super-blocks (256 elements) cover llama.cpp's common quantized formats; each
# dequantizes verbatim from ggml's own block layouts (see the _gguf_dequant_* helpers). Anything
# else is refused by name with its type id.
_GGML_TYPE_F32 = 0
_GGML_TYPE_F16 = 1
_GGML_TYPE_Q4_0 = 2
_GGML_TYPE_Q5_0 = 6
_GGML_TYPE_Q8_0 = 8
_GGML_TYPE_Q4_K = 12
_GGML_TYPE_Q5_K = 13
_GGML_TYPE_Q6_K = 14

# Per-block byte sizes and element counts for the quantized types (ggml's exact block structs,
# little-endian, no padding: Q4_0 {f16 d, u8 qs[16]}, Q5_0 {f16 d, u32 qh, u8 qs[16]},
# Q8_0 {f16 d, i8 qs[32]}, Q4_K {f16 d, f16 dmin, u8 scales[12], u8 qs[128]},
# Q5_K {f16 d, f16 dmin, u8 scales[12], u8 qh[32], u8 qs[128]},
# Q6_K {u8 ql[128], u8 qh[64], i8 scales[16], f16 d}).
_GGUF_QUANT_BLOCK_SPECS = {
    _GGML_TYPE_Q4_0: (32, 18),
    _GGML_TYPE_Q5_0: (32, 22),
    _GGML_TYPE_Q8_0: (32, 34),
    _GGML_TYPE_Q4_K: (256, 144),
    _GGML_TYPE_Q5_K: (256, 176),
    _GGML_TYPE_Q6_K: (256, 210),
}

# GGUF tensor names (llama.cpp convention) -> the HF names the manifest contract uses.
_GGUF_GLOBAL_TENSOR_NAMES = {
    "token_embd.weight": "model.embed_tokens.weight",
    "output_norm.weight": "model.norm.weight",
    "output.weight": "lm_head.weight",
}
_GGUF_LAYER_TENSOR_NAMES = {
    "attn_norm.weight": "input_layernorm.weight",
    "ffn_norm.weight": "post_attention_layernorm.weight",
    "attn_q_norm.weight": "self_attn.q_norm.weight",
    "attn_k_norm.weight": "self_attn.k_norm.weight",
    "attn_q.weight": "self_attn.q_proj.weight",
    "attn_k.weight": "self_attn.k_proj.weight",
    "attn_v.weight": "self_attn.v_proj.weight",
    "attn_output.weight": "self_attn.o_proj.weight",
    "ffn_gate.weight": "mlp.gate_proj.weight",
    "ffn_up.weight": "mlp.up_proj.weight",
    "ffn_down.weight": "mlp.down_proj.weight",
}

# GGUF `general.architecture` -> the LAYOUT that arch's metadata + tensors follow, declared as a
# table instead of a family-string tuple (model-agnostic conformance, 2026-08-23): every arch the
# reader accepts uses the SAME tensor-name convention above and the SAME `<arch>.*` metadata key
# set, so one layout record serves both -- a new arch is one table row verified against a real
# file, never a code change. `metadata_convention` names the `<arch>.` key prefix family;
# `tensor_convention` is the llama.cpp name map above. Selection stays a pure lookup: the file's
# own `general.architecture` string indexes the table, and anything absent from it is refused by
# name with the table's contents as the supported set.
_GGUF_ARCH_LAYOUTS: dict[str, dict[str, str]] = {
    "llama": {"metadata_convention": "llama", "tensor_convention": "llama.cpp blk.N.*"},
    "qwen3": {"metadata_convention": "llama", "tensor_convention": "llama.cpp blk.N.*"},
}
_GGUF_SUPPORTED_ARCHITECTURES = tuple(_GGUF_ARCH_LAYOUTS)


def _gguf_read_string(handle: Any) -> str:
    (length,) = struct.unpack("<Q", handle.read(8))
    raw = handle.read(length)
    if len(raw) != length:
        raise InferenceError(
            "unsupported_gguf", "the GGUF file is truncated inside a string field"
        )
    return raw.decode("utf-8")


def _gguf_read_metadata_value(handle: Any, value_type: int) -> Any:
    """One GGUF metadata value of a known type tag (recursing into arrays)."""
    if value_type == 0:
        return struct.unpack("<B", handle.read(1))[0]
    if value_type == 1:
        return struct.unpack("<b", handle.read(1))[0]
    if value_type == 2:
        return struct.unpack("<H", handle.read(2))[0]
    if value_type == 3:
        return struct.unpack("<h", handle.read(2))[0]
    if value_type == 4:
        return struct.unpack("<I", handle.read(4))[0]
    if value_type == 5:
        return struct.unpack("<i", handle.read(4))[0]
    if value_type == 6:
        return struct.unpack("<f", handle.read(4))[0]
    if value_type == 7:
        return struct.unpack("<B", handle.read(1))[0] != 0
    if value_type == 8:
        return _gguf_read_string(handle)
    if value_type == 9:
        (element_type,) = struct.unpack("<I", handle.read(4))
        (count,) = struct.unpack("<Q", handle.read(8))
        return [_gguf_read_metadata_value(handle, element_type) for _ in range(count)]
    if value_type == 10:
        return struct.unpack("<Q", handle.read(8))[0]
    if value_type == 11:
        return struct.unpack("<q", handle.read(8))[0]
    if value_type == 12:
        return struct.unpack("<d", handle.read(8))[0]
    raise InferenceError(
        "unsupported_gguf", f"unknown GGUF metadata value type {value_type}"
    )


def _read_gguf_header(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """Byte-level GGUF parse: magic, version, counts, the metadata kv pairs, and the tensor-info
    table. Returns `(metadata, tensor_infos, data_start)`; each tensor's raw bytes live at
    `data_start + tensor.offset`."""
    with path.open("rb") as handle:
        magic = handle.read(4)
        if magic != _GGUF_MAGIC:
            raise InferenceError(
                "unsupported_gguf",
                f"{path} is not a GGUF file (magic {magic!r}, expected {_GGUF_MAGIC!r}).",
            )
        (version,) = struct.unpack("<I", handle.read(4))
        if version not in (2, 3):
            raise InferenceError(
                "unsupported_gguf",
                f"{path} is GGUF version {version}; only versions 2 and 3 are read.",
            )
        tensor_count, metadata_count = struct.unpack("<QQ", handle.read(16))
        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key = _gguf_read_string(handle)
            (value_type,) = struct.unpack("<I", handle.read(4))
            metadata[key] = _gguf_read_metadata_value(handle, value_type)
        tensor_infos: list[dict[str, Any]] = []
        for _ in range(tensor_count):
            name = _gguf_read_string(handle)
            (n_dims,) = struct.unpack("<I", handle.read(4))
            dims = list(struct.unpack(f"<{n_dims}Q", handle.read(8 * n_dims)))
            (ggml_type,) = struct.unpack("<I", handle.read(4))
            (offset,) = struct.unpack("<Q", handle.read(8))
            tensor_infos.append(
                {"name": name, "dims": dims, "ggml_type": ggml_type, "offset": offset}
            )
        alignment = metadata.get("general.alignment", _GGUF_DEFAULT_ALIGNMENT)
        if (
            isinstance(alignment, bool)
            or not isinstance(alignment, int)
            or alignment < 1
            or (alignment & (alignment - 1)) != 0
        ):
            raise InferenceError(
                "unsupported_gguf",
                f"{path} declares general.alignment={alignment!r}; only powers of two are read.",
            )
        data_start = (handle.tell() + alignment - 1) // alignment * alignment
    return metadata, tensor_infos, data_start


def _gguf_map_tensor_name(name: str) -> str | None:
    """A llama.cpp-convention GGUF tensor name -> the HF name the manifest contract uses; None for
    tensors the engine does not consume (rope factors, tokenizer tables, ...)."""
    if name in _GGUF_GLOBAL_TENSOR_NAMES:
        return _GGUF_GLOBAL_TENSOR_NAMES[name]
    if name.startswith("blk."):
        layer_text, _, suffix = name[len("blk.") :].partition(".")
        if layer_text.isdigit():
            hf_suffix = _GGUF_LAYER_TENSOR_NAMES.get(suffix)
            if hf_suffix is not None:
                return f"model.layers.{int(layer_text)}.{hf_suffix}"
    return None


def _gguf_dequant_q8_0(np: Any, raw: bytes) -> Any:
    """Q8_0: per 32-element block `scale * int8` (f16 scale)."""
    blocks = np.frombuffer(raw, dtype=np.dtype([("d", "<f2"), ("qs", "i1", (32,))]))
    return (
        blocks["qs"].astype(np.float64) * blocks["d"].astype(np.float64)[:, None]
    ).reshape(-1)


def _gguf_dequant_q4_0(np: Any, raw: bytes) -> Any:
    """Q4_0 (ggml's dequantize_row_q4_0 verbatim): per 32-element block an f16 scale `d` and 16
    nibble bytes; element j is the LOW nibble of byte j, element j+16 the HIGH nibble, each
    `(nibble - 8) * d`."""
    blocks = np.frombuffer(raw, dtype=np.dtype([("d", "<f2"), ("qs", "u1", (16,))]))
    d = blocks["d"].astype(np.float64)[:, None]
    qs = blocks["qs"]
    out = np.empty((qs.shape[0], 32), dtype=np.float64)
    out[:, :16] = ((qs & np.uint8(0x0F)).astype(np.float64) - 8.0) * d
    out[:, 16:] = ((qs >> np.uint8(4)).astype(np.float64) - 8.0) * d
    return out.reshape(-1)


def _gguf_dequant_q5_0(np: Any, raw: bytes) -> Any:
    """Q5_0 (ggml's dequantize_row_q5_0 verbatim): per 32-element block an f16 scale `d`, a u32
    `qh` holding each element's 5th bit, and 16 nibble bytes; element j is the LOW nibble of byte
    j ORed with bit j of qh, element j+16 the HIGH nibble ORed with bit j+16, each
    `(value - 16) * d`."""
    blocks = np.frombuffer(raw, dtype=np.dtype([("d", "<f2"), ("qh", "<u4"), ("qs", "u1", (16,))]))
    d = blocks["d"].astype(np.float64)[:, None]
    qs = blocks["qs"]
    qh = blocks["qh"][:, None]
    j = np.arange(16, dtype=np.uint32)[None, :]
    high_lo = ((qh >> j) & np.uint32(1)) << np.uint32(4)  # bit j -> element j's 5th bit
    high_hi = ((qh >> (j + 16)) & np.uint32(1)) << np.uint32(4)  # bit j+16 -> element j+16
    out = np.empty((qs.shape[0], 32), dtype=np.float64)
    out[:, :16] = (((qs & np.uint8(0x0F)) | high_lo.astype(np.uint8)).astype(np.float64) - 16.0) * d
    out[:, 16:] = (((qs >> np.uint8(4)) | high_hi.astype(np.uint8)).astype(np.float64) - 16.0) * d
    return out.reshape(-1)


def _gguf_k4_scales_mins(np: Any, scales: Any) -> tuple[Any, Any]:
    """The Q4_K/Q5_K shared 6-bit scale/min unpacking (ggml's get_scale_min_k4 verbatim), for all
    8 sub-blocks of every super-block: sub-blocks 0..3 read scales[j] & 63 / scales[j+4] & 63;
    4..7 split scales[j+4]'s nibbles with scales[j-4]/scales[j]'s top two bits as the high bits.
    Returns (sc, m), each (n_blocks, 8) float64."""
    sc = np.empty((scales.shape[0], 8), dtype=np.float64)
    m = np.empty((scales.shape[0], 8), dtype=np.float64)
    sc[:, :4] = scales[:, :4] & np.uint8(63)
    m[:, :4] = scales[:, 4:8] & np.uint8(63)
    sc[:, 4:] = (scales[:, 8:12] & np.uint8(0x0F)) | ((scales[:, 0:4] >> np.uint8(6)) << np.uint8(4))
    m[:, 4:] = (scales[:, 8:12] >> np.uint8(4)) | ((scales[:, 4:8] >> np.uint8(6)) << np.uint8(4))
    return sc, m


def _gguf_dequant_q4_k(np: Any, raw: bytes) -> Any:
    """Q4_K (ggml's dequantize_row_q4_K verbatim): per 256-element super-block f16 `d`/`dmin`, 12
    scale/min bytes (6-bit packed, `_gguf_k4_scales_mins`), and 128 nibble bytes. The bytes are
    read in four 64-element groups; in group g, byte l's LOW nibble is element 64g+l (sub-block
    2g) and its HIGH nibble element 64g+32+l (sub-block 2g+1), each `d*sc*q - dmin*m`."""
    blocks = np.frombuffer(
        raw, dtype=np.dtype([("d", "<f2"), ("dmin", "<f2"), ("scales", "u1", (12,)), ("qs", "u1", (128,))])
    )
    d = blocks["d"].astype(np.float64)[:, None]  # (n_blocks, 1)
    dmin = blocks["dmin"].astype(np.float64)[:, None]
    sc, m = _gguf_k4_scales_mins(np, blocks["scales"])
    qs = blocks["qs"].reshape(-1, 4, 32)
    d1 = (d * sc[:, 0::2])[:, :, None]  # (n_blocks, 4, 1) -- sub-blocks 0,2,4,6
    m1 = (dmin * m[:, 0::2])[:, :, None]
    d2 = (d * sc[:, 1::2])[:, :, None]  # sub-blocks 1,3,5,7
    m2 = (dmin * m[:, 1::2])[:, :, None]
    out = np.empty((qs.shape[0], 4, 64), dtype=np.float64)
    out[:, :, :32] = (qs & np.uint8(0x0F)).astype(np.float64) * d1 - m1
    out[:, :, 32:] = (qs >> np.uint8(4)).astype(np.float64) * d2 - m2
    return out.reshape(-1)


def _gguf_dequant_q5_k(np: Any, raw: bytes) -> Any:
    """Q5_K (ggml's dequantize_row_q5_K verbatim): Q4_K's layout plus 32 `qh` bytes carrying each
    element's 5th bit -- element 64g+l takes bit 2g of qh[l], element 64g+32+l bit 2g+1 -- and the
    5-bit value is `low4 + 16*bit` (NO minus-16; the per-sub-block min carries the offset)."""
    blocks = np.frombuffer(
        raw,
        dtype=np.dtype(
            [("d", "<f2"), ("dmin", "<f2"), ("scales", "u1", (12,)), ("qh", "u1", (32,)), ("qs", "u1", (128,))]
        ),
    )
    d = blocks["d"].astype(np.float64)[:, None]  # (n_blocks, 1)
    dmin = blocks["dmin"].astype(np.float64)[:, None]
    sc, m = _gguf_k4_scales_mins(np, blocks["scales"])
    ql = blocks["qs"].reshape(-1, 4, 32)
    qh = blocks["qh"]  # (n_blocks, 32) -- indexed qh[l] for every group g
    d1 = (d * sc[:, 0::2])[:, :, None]
    m1 = (dmin * m[:, 0::2])[:, :, None]
    d2 = (d * sc[:, 1::2])[:, :, None]
    m2 = (dmin * m[:, 1::2])[:, :, None]
    groups = np.arange(4, dtype=np.uint8)
    u1 = np.uint8(1) << (2 * groups)  # per group g: bit 2g
    u2 = np.uint8(2) << (2 * groups)  # bit 2g+1
    high_lo = ((qh[:, None, :] & u1[None, :, None]) != np.uint8(0)).astype(np.float64) * 16.0
    high_hi = ((qh[:, None, :] & u2[None, :, None]) != np.uint8(0)).astype(np.float64) * 16.0
    out = np.empty((ql.shape[0], 4, 64), dtype=np.float64)
    out[:, :, :32] = ((ql & np.uint8(0x0F)).astype(np.float64) + high_lo) * d1 - m1
    out[:, :, 32:] = ((ql >> np.uint8(4)).astype(np.float64) + high_hi) * d2 - m2
    return out.reshape(-1)


def _gguf_dequant_q6_k(np: Any, raw: bytes) -> Any:
    """Q6_K (ggml's dequantize_row_q6_K verbatim): per 256-element super-block 128 `ql` bytes
    (low nibbles), 64 `qh` bytes (2 high bits each), 16 int8 sub-block scales (one per 16
    elements), and an f16 `d`. In each 128-element half, for l in 0..31 (is = l//16):
    element l     = d*sc[is]  * (ql[l]&0xF    | (qh[l]&0x3)<<4    - 32)
    element l+32  = d*sc[is+2]* (ql[l+32]&0xF | (qh[l]>>2&0x3)<<4 - 32)
    element l+64  = d*sc[is+4]* (ql[l]>>4     | (qh[l]>>4&0x3)<<4 - 32)
    element l+96  = d*sc[is+6]* (ql[l+32]>>4  | (qh[l]>>6&0x3)<<4 - 32)"""
    blocks = np.frombuffer(
        raw, dtype=np.dtype([("ql", "u1", (128,)), ("qh", "u1", (64,)), ("scales", "i1", (16,)), ("d", "<f2")])
    )
    d = blocks["d"].astype(np.float64)[:, None, None]  # (n_blocks, 1, 1)
    n_blocks = blocks.shape[0]
    ql = blocks["ql"].reshape(n_blocks, 2, 2, 32)  # (block, half, low/high row, l)
    qh = blocks["qh"].reshape(n_blocks, 2, 32)
    scales = blocks["scales"].astype(np.float64).reshape(n_blocks, 2, 8)
    ql_lo = ql[:, :, 0, :]  # ql[l]
    ql_hi = ql[:, :, 1, :]  # ql[l+32]
    q1 = (ql_lo & np.uint8(0x0F)) | ((qh & np.uint8(0x03)) << np.uint8(4))
    q2 = (ql_hi & np.uint8(0x0F)) | (((qh >> np.uint8(2)) & np.uint8(0x03)) << np.uint8(4))
    q3 = (ql_lo >> np.uint8(4)) | (((qh >> np.uint8(4)) & np.uint8(0x03)) << np.uint8(4))
    q4 = (ql_hi >> np.uint8(4)) | (((qh >> np.uint8(6)) & np.uint8(0x03)) << np.uint8(4))
    l_idx = np.arange(32)
    is_idx = l_idx // 16  # 0 for l<16, 1 otherwise
    sc1 = scales[:, :, is_idx]          # sc[is]
    sc2 = scales[:, :, is_idx + 2]      # sc[is+2]
    sc3 = scales[:, :, is_idx + 4]      # sc[is+4]
    sc4 = scales[:, :, is_idx + 6]      # sc[is+6]
    out = np.empty((n_blocks, 2, 4, 32), dtype=np.float64)
    out[:, :, 0, :] = d * sc1 * (q1.astype(np.float64) - 32.0)
    out[:, :, 1, :] = d * sc2 * (q2.astype(np.float64) - 32.0)
    out[:, :, 2, :] = d * sc3 * (q3.astype(np.float64) - 32.0)
    out[:, :, 3, :] = d * sc4 * (q4.astype(np.float64) - 32.0)
    return out.reshape(-1)


_GGUF_DEQUANTIZERS = {
    _GGML_TYPE_Q8_0: _gguf_dequant_q8_0,
    _GGML_TYPE_Q4_0: _gguf_dequant_q4_0,
    _GGML_TYPE_Q5_0: _gguf_dequant_q5_0,
    _GGML_TYPE_Q4_K: _gguf_dequant_q4_k,
    _GGML_TYPE_Q5_K: _gguf_dequant_q5_k,
    _GGML_TYPE_Q6_K: _gguf_dequant_q6_k,
}


def _gguf_read_tensor_values(
    path: Path, info: dict[str, Any], data_start: int
) -> tuple[Any, list[int]]:
    """One GGUF tensor's raw bytes widened to a flat Float64 numpy array. Returns
    `(values, shape)` with `shape` in HuggingFace row-major order (the GGUF dims reversed).
    F16/F32 widen exactly; the quantized types dequantize block-by-block (ggml's exact formulas,
    the f16 scales widening exactly -- the only rounding is the quantization the file already
    carries)."""
    import numpy as np

    dims = info["dims"]
    ggml_type = info["ggml_type"]
    n_elements = 1
    for dim in dims:
        n_elements *= int(dim)
    if ggml_type == _GGML_TYPE_F16:
        n_bytes = 2 * n_elements
    elif ggml_type == _GGML_TYPE_F32:
        n_bytes = 4 * n_elements
    elif ggml_type in _GGUF_QUANT_BLOCK_SPECS:
        block_elements, block_bytes = _GGUF_QUANT_BLOCK_SPECS[ggml_type]
        if n_elements % block_elements != 0:
            raise InferenceError(
                "unsupported_gguf",
                f"tensor {info['name']!r} is ggml type {ggml_type} with {n_elements} elements; "
                f"its blocks cover exactly {block_elements} elements each.",
            )
        n_bytes = (n_elements // block_elements) * block_bytes
    else:
        raise InferenceError(
            "unsupported_gguf",
            f"tensor {info['name']!r} is ggml type {ggml_type}; this converter reads F32, F16, "
            "Q8_0, Q4_0, Q5_0 and the Q4_K/Q5_K/Q6_K K-quants. Re-export the GGUF with one of "
            "those (llama.cpp's convert_hf_to_gguf.py --outtype f16 is the common choice).",
        )
    with path.open("rb") as handle:
        handle.seek(data_start + info["offset"])
        raw = handle.read(n_bytes)
    if len(raw) != n_bytes:
        raise InferenceError(
            "unsupported_gguf", f"{path} is truncated inside tensor {info['name']!r}."
        )
    if ggml_type == _GGML_TYPE_F16:
        values = np.frombuffer(raw, dtype="<f2").astype(np.float64)
    elif ggml_type == _GGML_TYPE_F32:
        values = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    else:
        values = _GGUF_DEQUANTIZERS[ggml_type](np, raw)
    return values, list(reversed(dims))


def _gguf_architecture_config(
    path: Path, metadata: dict[str, Any], tensor_infos: list[dict[str, Any]]
) -> dict[str, Any]:
    """The HF-style config the manifest carries, derived from the GGUF's `<arch>.*` metadata the way
    llama.cpp's own convention defines it (embedding_length=hidden_size, block_count=layers,
    attention.head_count/[_kv]=heads, feed_forward_length=intermediate_size,
    attention.layer_norm_rms_epsilon=rms_norm_eps, rope.freq_base=rope_theta). head_dim comes from
    `<arch>.attention.key_length` when present, else it is derived (hidden_size // heads) by the
    shared `_normalize_config`. The tie/qk-norm/eos conventions are FACTS of the file (tensor
    presence and tokenizer metadata), never assumptions."""
    arch = metadata.get("general.architecture")
    if not isinstance(arch, str) or arch not in _GGUF_SUPPORTED_ARCHITECTURES:
        raise InferenceError(
            "unsupported_gguf",
            f"{path} is a {arch!r} GGUF; this converter reads "
            f"{'/'.join(_GGUF_SUPPORTED_ARCHITECTURES)} GGUF files.",
        )

    def meta(key: str) -> Any:
        return metadata.get(f"{arch}.{key}")

    def require_int(gguf_key: str) -> int:
        value = meta(gguf_key)
        if value is None:
            raise InferenceError(
                "unsupported_gguf",
                f"{path} carries no {arch}.{gguf_key} GGUF metadata; the architecture "
                "hyperparameters are required.",
            )
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise InferenceError(
                "unsupported_gguf",
                f"{path} GGUF metadata {arch}.{gguf_key} is {value!r}; expected a positive int.",
            )
        return value

    hidden_size = require_int("embedding_length")
    n_layers = require_int("block_count")
    num_attention_heads = require_int("attention.head_count")
    intermediate_size = require_int("feed_forward_length")
    num_kv_heads = meta("attention.head_count_kv")
    if num_kv_heads is None:
        num_kv_heads = num_attention_heads
    if isinstance(num_kv_heads, bool) or not isinstance(num_kv_heads, int) or num_kv_heads < 1:
        raise InferenceError(
            "unsupported_gguf",
            f"{path} GGUF metadata {arch}.attention.head_count_kv is {num_kv_heads!r}; expected "
            "a positive int.",
        )
    rms_norm_eps = meta("attention.layer_norm_rms_epsilon")
    if rms_norm_eps is None:
        rms_norm_eps = meta("attention.layer_norm_epsilon")
    if (
        rms_norm_eps is None
        or isinstance(rms_norm_eps, bool)
        or not isinstance(rms_norm_eps, int | float)
        or rms_norm_eps < 0
    ):
        raise InferenceError(
            "unsupported_gguf",
            f"{path} carries no usable {arch}.attention.layer_norm_rms_epsilon GGUF metadata.",
        )
    rope_theta = meta("rope.freq_base")
    if rope_theta is None:
        rope_theta = 10000.0
    if isinstance(rope_theta, bool) or not isinstance(rope_theta, int | float):
        raise InferenceError(
            "unsupported_gguf",
            f"{path} GGUF metadata {arch}.rope.freq_base is {rope_theta!r}; expected a number.",
        )
    # Rope scaling metadata (llama.cpp convention: `<arch>.rope.scaling.type`). For the llama3
    # scheme llama.cpp does NOT write scaling metadata at all -- it bakes the adjusted frequencies
    # into a `rope_freqs.weight` tensor (handled in prepare_model_checkpoint_from_gguf). A
    # NON-none type WITHOUT that tensor would otherwise run silently unscaled, so it is carried
    # here for that cross-check.
    rope_scaling_type = meta("rope.scaling.type")
    if rope_scaling_type is not None and not isinstance(rope_scaling_type, str):
        raise InferenceError(
            "unsupported_gguf",
            f"{path} GGUF metadata {arch}.rope.scaling.type is {rope_scaling_type!r}; expected "
            "a string.",
        )

    vocab_size = None
    tied_embeddings = True
    for info in tensor_infos:
        if info["name"] == "token_embd.weight" and len(info["dims"]) == 2:
            vocab_size = int(info["dims"][1])
        if info["name"] == "output.weight":
            tied_embeddings = False
    if vocab_size is None:
        raise InferenceError(
            "unsupported_gguf",
            f"{path} has no token_embd.weight tensor to read the vocab size from.",
        )

    config: dict[str, Any] = {
        "hidden_size": hidden_size,
        "num_hidden_layers": n_layers,
        "num_attention_heads": num_attention_heads,
        "num_key_value_heads": num_kv_heads,
        "intermediate_size": intermediate_size,
        "vocab_size": vocab_size,
        "rope_theta": float(rope_theta),
        "rms_norm_eps": float(rms_norm_eps),
        "tie_word_embeddings": tied_embeddings,
    }
    if rope_scaling_type is not None:
        # Underscore-prefixed: a private carrier for the rope_freqs.weight cross-check in
        # prepare_model_checkpoint_from_gguf, popped before the manifest is written.
        config["_gguf_rope_scaling_type"] = rope_scaling_type.lower()
    head_dim = meta("attention.key_length")
    if head_dim is not None:
        if isinstance(head_dim, bool) or not isinstance(head_dim, int) or head_dim < 1:
            raise InferenceError(
                "unsupported_gguf",
                f"{path} GGUF metadata {arch}.attention.key_length is {head_dim!r}; expected a "
                "positive int.",
            )
        config["head_dim"] = head_dim
    config = _normalize_config(config)

    eos_token_id = metadata.get("tokenizer.ggml.eos_token_id")
    if isinstance(eos_token_id, int) and not isinstance(eos_token_id, bool):
        config["eos_token_id"] = eos_token_id
    return config


def prepare_model_checkpoint_from_gguf(
    gguf_path: str | Path,
    prompt_token_ids: list[int],
    *,
    out_dir: str | Path | None = None,
) -> Path:
    """Validate a GGUF model file's architecture, then convert it into the SAME `manifest.json` +
    `weights.blob` pair `prepare_model_checkpoint()` produces from a HuggingFace snapshot -- the
    rest of the engine is untouched. Reads the GGUF container (versions 2/3) with struct parsing
    only, widens F16/F32 tensors (and dequantizes Q8_0) to the converter's Float64 weight stream,
    and maps the llama.cpp tensor names onto the HF names the manifest contract uses.

    `gguf_path` is a single `.gguf` file (e.g. one produced by llama.cpp's convert_hf_to_gguf.py).
    Raises `UnsupportedArchitectureError` for a shape the kernels refuse, `InferenceError(
    "unsupported_gguf")` for a container/dtype this reader does not parse, and `InferenceError(
    "checkpoint_not_found")` for a missing file or tensor. Returns the directory the manifest +
    blob were written to.
    """
    try:
        import numpy as np  # noqa: F401
    except ImportError as exc:
        raise InferenceError(
            "numpy_required",
            "prepare_model_checkpoint_from_gguf() needs numpy to convert GGUF weights; install it "
            "with `pip install numpy`.",
        ) from exc

    gguf_path = Path(gguf_path)
    if not gguf_path.is_file():
        raise InferenceError("checkpoint_not_found", f"{gguf_path} is not a file.")
    metadata, tensor_infos, data_start = _read_gguf_header(gguf_path)
    config = _gguf_architecture_config(gguf_path, metadata, tensor_infos)
    _validate_architecture(gguf_path, config, config_source="GGUF metadata")
    _validate_prompt_token_ids(prompt_token_ids)

    # Rope scaling, GGUF shape: llama.cpp's conversion for a llama3-scaled checkpoint bakes the
    # adjusted frequencies into a `rope_freqs.weight` tensor (one F32 DIVISOR per head-dim pair;
    # ggml applies `theta / factor` per pair), and writes no scaling metadata -- so that tensor is
    # the authoritative representation here, carried into the manifest verbatim.
    rope_freq_factors: list[float] | None = None
    rope_freqs_info = next(
        (info for info in tensor_infos if info["name"] == "rope_freqs.weight"), None
    )
    if rope_freqs_info is not None:
        values, _ = _gguf_read_tensor_values(gguf_path, rope_freqs_info, data_start)
        rope_freq_factors = [float(value) for value in values]
        expected_pairs = config["head_dim"] // 2
        if len(rope_freq_factors) != expected_pairs:
            raise InferenceError(
                "unsupported_gguf",
                f"{gguf_path} rope_freqs.weight carries {len(rope_freq_factors)} factors but "
                f"head_dim={config['head_dim']} needs exactly {expected_pairs} (one per "
                "dimension pair).",
            )
    else:
        scaling_type = config.pop("_gguf_rope_scaling_type", None)
        if scaling_type is not None and scaling_type != "none":
            raise InferenceError(
                "unsupported_gguf",
                f"{gguf_path} declares rope.scaling.type={scaling_type!r} but carries no "
                "rope_freqs.weight tensor to apply it; only conversions that bake the scaled "
                "frequencies into that tensor (llama.cpp's llama3 handling) are supported. "
                "Running with the scaling silently dropped would leave the rope unscaled.",
            )
    config.pop("_gguf_rope_scaling_type", None)

    hf_tensors: dict[str, dict[str, Any]] = {}
    for info in tensor_infos:
        hf_name = _gguf_map_tensor_name(info["name"])
        if hf_name is not None:
            hf_tensors[hf_name] = info
    # Model-agnostic conformance (2026-08-23): the same tensors-are-the-truth gates the safetensors
    # front door applies. Bias tensors the engine would silently drop (any q/k/v/o projection or FFN
    # bias -- the Metal dispatch path applies none of them, and the GGUF reader does not convert
    # them) are a typed refusal naming the exact tensor, never a silent drop.
    _gguf_unsupported = sorted(
        info["name"]
        for info in tensor_infos
        if info["name"].startswith("blk.") and info["name"].endswith(".bias")
    )
    if _gguf_unsupported:
        raise InferenceError(
            "unsupported_gguf",
            f"{gguf_path} carries bias tensors the engine does not consume and would silently "
            f"drop: {', '.join(_gguf_unsupported[:4])}"
            + (f" (+{len(_gguf_unsupported) - 4} more)" if len(_gguf_unsupported) > 4 else "")
            + ". The Metal dispatch path applies no projection/FFN biases; re-export without "
            "them or use a backend whose kernel set applies them.",
        )
    # Same truth as the safetensors path: the TENSORS decide qk-norm presence (config metadata can
    # lie or omit), layer 0's probe tensor standing in for all layers.
    has_qk_norm = "model.layers.0.self_attn.q_norm.weight" in hf_tensors
    tied_embeddings = config["tie_word_embeddings"]
    required = _required_hf_tensor_names(config["num_hidden_layers"], tied_embeddings, has_qk_norm)

    resolved_out_dir = (
        Path(out_dir)
        if out_dir is not None
        else Path(tempfile.mkdtemp(prefix="algenta-gguf-ckpt-"))
    )
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    def _iter_entries() -> Iterator[tuple[str, Iterable[Any], list[int], bool]]:
        # One tensor in flight at a time, same discipline as the safetensors front door: the GGUF
        # reader seek+reads one tensor's bytes per call, the streaming writer appends them, and no
        # whole-model buffer ever exists.
        for name in sorted(required):
            info = hf_tensors.get(name)
            if info is None:
                raise InferenceError(
                    "checkpoint_not_found",
                    f"the GGUF file {gguf_path} is missing the tensor the manifest needs as "
                    f"{name!r}.",
                )
            values, shape = _gguf_read_tensor_values(gguf_path, info, data_start)
            transposed = False
            if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
                values = values.reshape(shape).T.copy().reshape(-1)
                shape = [shape[1], shape[0]]
                transposed = True
            yield name, (values,), shape, transposed

    return _write_converted_checkpoint(
        resolved_out_dir,
        entries=_iter_entries(),
        config=config,
        prompt_token_ids=prompt_token_ids,
        has_qk_norm=has_qk_norm,
        tied_embeddings=tied_embeddings,
        rope_freq_factors=rope_freq_factors,
    )


def _gguf_checkpoint_file(checkpoint_dir: str | Path) -> Path | None:
    """The GGUF front door for `decode()`: an EXISTING file as the checkpoint is a GGUF model file
    (the magic check inside the reader is the validator); a directory stays the HuggingFace path."""
    path = Path(checkpoint_dir)
    return path if path.is_file() else None


@lru_cache(maxsize=8)
def _gguf_tokenizer(gguf_path_str: str, mtime_ns: int, size: int) -> Any:
    """The tokenizer EMBEDDED in a GGUF file's metadata (tokenizer.ggml.*), cached per file
    identity (path + mtime + size -- the same staleness contract as the conversion cache: an
    in-place re-export of the file is picked up, a byte-identical overwrite is not). Raises
    `InferenceError("unsupported_gguf")` when the file embeds no tokenizer this module
    implements. The mtime/size arguments are cache keys only; the path is re-read on a miss."""
    from algenta.tokenizer import Tokenizer, TokenizerFormatError

    del mtime_ns, size  # cache-key only
    gguf_path = Path(gguf_path_str)
    metadata, _, _ = _read_gguf_header(gguf_path)
    try:
        return Tokenizer.from_gguf_metadata(metadata)
    except TokenizerFormatError as exc:
        raise InferenceError(
            "unsupported_gguf",
            f"{gguf_path} embeds no usable tokenizer for text prompts: {exc}",
        ) from exc


def _load_gguf_tokenizer(gguf_file: Path) -> Any:
    """`_gguf_tokenizer` keyed by the file's current identity."""
    stat = gguf_file.stat()
    return _gguf_tokenizer(str(gguf_file), stat.st_mtime_ns, stat.st_size)


def prepare_model_checkpoint(
    checkpoint_dir: str | Path,
    prompt_token_ids: list[int],
    *,
    out_dir: str | Path | None = None,
    weights_dtype: str = "f64",
    backend: str = "metal",
) -> Path:
    """Validate `checkpoint_dir`'s architecture, then convert it into the `manifest.json` +
    `weights.blob` pair the model-agnostic kernel entry point reads. Handles any supported-family
    model, single- or multi-shard -- Qwen3/llama-family AND Gemma 3 (the multimodal wrapper config
    lifts to its text model; the text tensors remap from their `language_model.` snapshot prefix
    onto the canonical manifest names; every RMSNorm gain is written REBASED to Gemma's
    (1.0 + weight) convention the kernels then apply verbatim).

    `checkpoint_dir` is a local HuggingFace snapshot directory (`config.json` + one or more
    `model*.safetensors`). `weights_dtype` selects the blob element width: "f64" (default -- the
    historical format) or "f32" (exact for BF16-origin checkpoints, half the disk -- a 27B-class
    f64 blob exceeds a race VM's disk). `backend` selects the backend-specific fact gates the
    tensor probe applies ("metal", the SDK door's default, or "cuda"): the q/k/v projection-bias
    fact is refused where the backend does not apply it and accepted where it does (the CUDA
    lane's five 7B paths apply biases; the Metal descriptor tables do not). Raises
    `UnsupportedArchitectureError` for an unsupported architecture and
    `InferenceError("checkpoint_not_found", ...)` for missing files. Returns the directory the
    manifest + blob were written to.
    """
    try:
        import numpy as np  # noqa: F401
    except ImportError as exc:
        raise InferenceError(
            "numpy_required",
            "prepare_model_checkpoint() needs numpy to convert checkpoint weights; install it with "
            "`pip install numpy`.",
        ) from exc

    checkpoint_dir = Path(checkpoint_dir)
    config_path = checkpoint_dir / "config.json"
    if not config_path.is_file():
        raise InferenceError(
            "checkpoint_not_found",
            f"{checkpoint_dir} does not look like a HuggingFace checkpoint snapshot: "
            f"{config_path.name} is missing.",
        )
    config = _normalize_config(json.loads(config_path.read_text(encoding="utf-8")))
    is_gemma3 = config.get("model_type") == "gemma3_text"
    if is_gemma3:
        config = _gemma3_prepare_config(config, checkpoint_dir)
    _validate_architecture(checkpoint_dir, config)
    if not is_gemma3:
        # Gemma 3's rope (dual per-layer-class theta + the linear factor on global layers only)
        # is fully validated inside _gemma3_prepare_config; the llama3-only validator below would
        # refuse its linear scheme.
        _validate_rope_scaling(config, config_source=str(config_path))
    _validate_prompt_token_ids(prompt_token_ids)

    # Load the shard index if present (multi-shard checkpoints).
    index_path = checkpoint_dir / "model.safetensors.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else None

    # Gemma 3 snapshots prefix their text tensors with the multimodal wrapper path; the manifest
    # contract keeps the canonical `model.*` names, so a rename map bridges the two.
    tensor_prefix = ""
    if is_gemma3:
        tensor_prefix = _gemma3_probe_prefix(checkpoint_dir, index)

    if is_gemma3:
        # Tie is a FACT of the tensors: the wrapper's lm_head aliases the text embedding table
        # when the snapshot ships no lm_head weight (the 27B-it checkpoint is tied; the probe
        # handles any future untied gemma3 export too).
        tied_embeddings = not any(
            _safetensors_has_tensor(checkpoint_dir, index, candidate)
            for candidate in (
                f"{tensor_prefix}lm_head.weight",
                "language_model.lm_head.weight",
                "model.language_model.lm_head.weight",
                "lm_head.weight",
            )
        )
        has_qk_norm = _safetensors_has_tensor(
            checkpoint_dir, index, f"{tensor_prefix}model.layers.0.self_attn.q_norm.weight"
        )
        attention_bias = False  # _gemma3_prepare_config already refused attention_bias=true
    else:
        tied_embeddings = config.get("tie_word_embeddings", True) is True
        has_qk_norm = _detect_has_qk_norm(checkpoint_dir, index)
        attention_bias = _detect_attention_bias(checkpoint_dir, index)

        # Model-agnostic conformance (2026-08-23): the TENSOR-LEVEL fact gates, judged after the
        # probe (tensors are the truth). Two typed refusals, never silent drops:
        # (1) weights the engine does not consume (o_proj/mlp biases) would otherwise be
        #     converted into the blob and silently NEVER READ -- refused naming the exact tensor;
        # (2) q/k/v projection biases on the METAL dispatch path: the bias add is wired into the
        #     CUDA lane's five 7B paths (PR #821) but NOT into metaldispatch's descriptor tables,
        #     so a bias-carrying checkpoint on Metal would run with the biases silently dropped --
        #     the exact 7B-lane hazard -- refused with the exact fact instead.
        unsupported = _detect_unsupported_tensors(checkpoint_dir, index)
        if unsupported:
            raise UnsupportedArchitectureError(
                f"unsupported model architecture: {checkpoint_dir} carries tensors the engine "
                f"does not consume and would silently drop: {', '.join(unsupported)}. Supported "
                "tensors are the manifest's required set (q/k/v projection biases included when "
                "the backend applies them)."
            )
        if attention_bias:
            from algenta.model_capabilities import BACKEND_FACT_RANGES

            backend_ranges = BACKEND_FACT_RANGES.get(backend)
            if backend_ranges is None or 1 not in backend_ranges["attention_bias"]:
                raise UnsupportedArchitectureError(
                    f"unsupported model architecture: {checkpoint_dir} carries q/k/v projection "
                    f"biases (attention_bias=1), which the {backend} dispatch path does not "
                    "apply -- the bias kernels are wired into the CUDA lane's 7B paths only. "
                    "Refusing rather than running with the biases silently dropped."
                )
    required = _required_hf_tensor_names(
        config["num_hidden_layers"], tied_embeddings, has_qk_norm, attention_bias,
        gemma3=is_gemma3,
    )

    resolved_out_dir = (
        Path(out_dir) if out_dir is not None else Path(tempfile.mkdtemp(prefix="algenta-model-ckpt-"))
    )
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    def _iter_entries() -> Iterator[tuple[str, Iterable[Any], list[int], bool]]:
        # One tensor in flight at a time: read its BF16 bytes out of the shard, widen in tiles,
        # yield to the streaming writer -- the full model is never resident in host memory.
        for name in sorted(required):
            actual = f"{tensor_prefix}{name}"
            shard_path = _resolve_shard_for_tensor(checkpoint_dir, actual, index)
            header, data_start = _read_safetensors_header(shard_path)
            info = header.get(actual)
            if info is None:
                raise InferenceError(
                    "checkpoint_not_found", f"tensor {actual!r} not found in {shard_path}."
                )
            if info.get("dtype") != "BF16":
                raise InferenceError(
                    "checkpoint_not_found",
                    f"{actual} in {shard_path} is {info.get('dtype')}, expected BF16 -- this "
                    "converter handles BF16 checkpoints.",
                )
            shape = list(info["shape"])
            start, end = info["data_offsets"]
            with shard_path.open("rb") as handle:
                handle.seek(data_start + start)
                raw = handle.read(end - start)
            transposed = False
            if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
                chunks = (_bf16_bytes_to_f64_transposed(raw, shape),)
                shape = [shape[1], shape[0]]
                transposed = True
            else:
                chunks = _bf16_bytes_to_f64_tiles(raw)
            if is_gemma3 and (
                name.endswith(_GEMMA3_NORM_GAIN_SUFFIXES) or name == "model.norm.weight"
            ):
                # Gemma's (1.0 + weight) gain convention, rebased HERE so every engine norm kernel
                # (gain-multiply by construction) computes it exactly, with zero kernel changes.
                chunks = (chunk + 1.0 for chunk in chunks)
            yield name, chunks, shape, transposed

    extra_manifest_config = config.pop("_gemma3_manifest_entries", None) if is_gemma3 else None
    return _write_converted_checkpoint(
        resolved_out_dir,
        entries=_iter_entries(),
        config=config,
        prompt_token_ids=prompt_token_ids,
        has_qk_norm=has_qk_norm,
        tied_embeddings=tied_embeddings,
        attention_bias=attention_bias,
        extra_manifest_config=extra_manifest_config,
        weights_dtype=weights_dtype,
        llama_rope_scaling=not is_gemma3,
    )


def _envelope_error(envelope: Any) -> str | None:
    if not isinstance(envelope, dict):
        return "the local runtime returned a malformed response"
    if envelope.get("success") is True:
        return None
    return str(envelope.get("error") or envelope.get("error_code") or "runtime_execution_failed")


def decode(
    runtime: Any,
    *,
    checkpoint_dir: str | Path,
    prompt_token_ids: list[int] | None = None,
    prompt_text: str | None = None,
    messages: list[dict] | None = None,
    tools: list[dict] | None = None,
    max_new_tokens: int = 16,
    max_ctx: int | None = None,
    use_msl_parity_all_roles: bool = True,
    use_native_grouped_fa_attn_no_mirror: bool = True,
    warmup_prefills: int = 0,
    converted_checkpoint_dir: str | Path | None = None,
    temperature: float = 0.0,
    top_k: int = 40,
    top_p: float = 0.95,
    min_p: float = 0.0,
    repeat_penalty: float = 1.0,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    seed: int = 0,
) -> InferenceResult:
    """Decode a prompt with a supported model's Metal GPU kernel path.

    `checkpoint_dir` is a HuggingFace checkpoint snapshot directory -- OR a single GGUF model
    file (the llama.cpp interchange format, converted by `prepare_model_checkpoint_from_gguf`).
    A GGUF checkpoint accepts `prompt_token_ids` and `prompt_text` (its tokenizer is EMBEDDED in
    the file's metadata and built by `algenta.tokenizer.from_gguf_metadata`), and `messages`
    when it embeds one of the chat-template revisions `algenta.chat_template` implements.

    Pass EXACTLY ONE of:
    * `messages` -- a list of OpenAI-style chat dicts, formatted with the checkpoint's OWN chat
      template (`algenta.chat_template`) and tokenized with its tokenizer. Refuses with
      `InferenceError("unsupported_chat_template")` if the checkpoint ships no supported template.
    * `prompt_text` -- raw text tokenized with the checkpoint's own tokenizer.json via
      `algenta.tokenizer` (no chat template applied).
    * `prompt_token_ids` -- pure token math, no tokenizer loaded.
    With `messages` or `prompt_text` the result also carries `generated_text`.

    `tools` -- OpenAI-shaped tool definitions (`[{"type": "function", "function": {...}}, ...]`),
    forwarded to the chat template's tools preamble (only valid alongside `messages`; refused with
    `InferenceError("invalid_arguments")` otherwise). The template only renders the preamble that
    tells the model it MAY call a function -- it cannot force a call, and the response comes back
    as plain `generated_text` like any other completion. Pull structured calls back out of it with
    `algenta.chat_template.split_tool_calls_from_generated_text`.

    GREEDY BY DEFAULT. `temperature=0` (the default) runs the fused lm_head+argmax kernel path --
    exactly the pre-sampling behavior, byte for byte. `temperature > 0` switches to the sampled
    path: the tail emits the full logits row and the engine draws each token (the first included)
    through the conventional chain -- repetition/presence/frequency penalties -> temperature ->
    top-k -> min-p -> top-p -> weighted draw -- seeded by `seed`. Same prompt + parameters + seed
    gives a byte-identical sequence; `top_k=1` at any temperature reproduces the greedy sequence
    exactly. The sampled pass always runs the no-mirror + MSL-parity combination arm (the two
    `use_*` flags and `warmup_prefills` apply to the greedy pass only), and it materializes logits
    host-side, so it is slower per token than greedy; it exists for generation quality parity, not
    speed.

    Model-agnostic across any model whose architecture the kernels support (see module docstring).
    The engine sizes its own context as `max(512, n_prompt + max_new_tokens)` (auto-raised past
    the 512 default whenever this call needs more, up to the engine's 65536 ceiling); `max_ctx`
    here is a caller-side guard only -- a value below `n_prompt + max_new_tokens` is refused, and
    a larger value is accepted but cannot change a one-shot run (nothing inside a single call can
    consume context beyond what the prompt + generation uses).

    Converts `checkpoint_dir` once per call (pass `converted_checkpoint_dir` to reuse an already-
    converted checkpoint). Raises `UnsupportedArchitectureError` for an unsupported architecture and
    `InferenceError` for every other refusal.
    """
    provided = sum(
        value is not None for value in (prompt_token_ids, prompt_text, messages)
    )
    if provided != 1:
        raise InferenceError(
            "invalid_arguments",
            "pass exactly one of prompt_token_ids, prompt_text, or messages",
        )
    if tools is not None and messages is None:
        raise InferenceError(
            "invalid_arguments",
            "tools is only valid alongside messages -- it is rendered into the prompt by the "
            "chat template, which prompt_text/prompt_token_ids bypass entirely",
        )
    # The GGUF front door (beat-llama.cpp campaign, model coverage): an EXISTING FILE as the
    # checkpoint is a GGUF model file, decoded through the same conversion+engine path. A GGUF
    # EMBEDS its tokenizer in its metadata, so text prompts work directly (llama.cpp's exact
    # SentencePiece conventions, algenta.tokenizer.from_gguf_metadata); chat prompts work when
    # the file embeds one of the template revisions algenta.chat_template implements.
    gguf_file = _gguf_checkpoint_file(checkpoint_dir)
    tokenizer = None
    if messages is not None:
        if not isinstance(messages, list) or not messages:
            raise InferenceError(
                "invalid_arguments",
                f"messages must be a non-empty list of message dicts, got {messages!r}",
            )
        from algenta.chat_template import (
            ChatTemplateError,
            apply_chat_template,
            is_qwen3_chat_template,
            render_qwen3_chat_template,
        )
        from algenta.tokenizer import load_tokenizer

        if gguf_file is not None:
            metadata, _, _ = _read_gguf_header(gguf_file)
            template = metadata.get("tokenizer.chat_template")
            if not isinstance(template, str) or not is_qwen3_chat_template(template):
                raise InferenceError(
                    "unsupported_chat_template",
                    f"{gguf_file} embeds no chat_template this module implements (only the "
                    "Qwen3 template revisions are implemented); pass prompt_text or "
                    "prompt_token_ids instead.",
                )
            prompt_text = render_qwen3_chat_template(
                messages, add_generation_prompt=True, tools=tools
            )
            tokenizer = _load_gguf_tokenizer(gguf_file)
        else:
            try:
                prompt_text = apply_chat_template(checkpoint_dir, messages, tools=tools)
            except ChatTemplateError as exc:
                raise InferenceError("unsupported_chat_template", str(exc)) from exc
            tokenizer = load_tokenizer(checkpoint_dir)
        # add_special_tokens=True is the transformers default-encode convention: a no-op on
        # Qwen3 prompts, and the BOS prepend a llama-family prompt expects (a GGUF honors its
        # own tokenizer.ggml.add_bos flag).
        prompt_token_ids = tokenizer.encode(prompt_text, add_special_tokens=True)
    elif prompt_text is not None:
        if not isinstance(prompt_text, str) or not prompt_text:
            raise InferenceError(
                "invalid_arguments", f"prompt_text must be a non-empty str, got {prompt_text!r}"
            )
        from algenta.tokenizer import load_tokenizer

        if gguf_file is not None:
            tokenizer = _load_gguf_tokenizer(gguf_file)
        else:
            tokenizer = load_tokenizer(checkpoint_dir)
        # add_special_tokens=True is the transformers default-encode convention: a no-op on
        # Qwen3 prompts, and the BOS prepend a llama-family prompt expects (a GGUF honors its
        # own tokenizer.ggml.add_bos flag).
        prompt_token_ids = tokenizer.encode(prompt_text, add_special_tokens=True)
    if not isinstance(prompt_token_ids, list) or not prompt_token_ids:
        raise InferenceError(
            "invalid_arguments", "the prompt must tokenize to at least one token id"
        )
    sampling = temperature > 0.0
    if sampling:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise InferenceError(
                "invalid_arguments", f"top_k must be an int >= 1 when sampling, got {top_k!r}"
            )
        if not 0.0 < top_p <= 1.0:
            raise InferenceError(
                "invalid_arguments", f"top_p must be in (0, 1] when sampling, got {top_p!r}"
            )
        if not 0.0 <= min_p < 1.0:
            raise InferenceError(
                "invalid_arguments", f"min_p must be in [0, 1) when sampling, got {min_p!r}"
            )

    if converted_checkpoint_dir is not None:
        resolved_dir = Path(converted_checkpoint_dir)
        if not (resolved_dir / "manifest.json").is_file() or not (
            resolved_dir / "weights.blob"
        ).is_file():
            raise InferenceError(
                "checkpoint_not_found",
                f"{resolved_dir} has no manifest.json/weights.blob; convert it first with "
                "prepare_model_checkpoint(), or omit converted_checkpoint_dir to convert "
                "automatically.",
            )
    else:
        # Conversion cache (serving increment, parity gap 2, 2026-08-10): the prompt travels over
        # the wire separately from the converted weights, so ONE conversion per checkpoint serves
        # every prompt. For a directory checkpoint the pair lives in
        # `<checkpoint_dir>/.algenta-cache`; for a GGUF FILE it sits BESIDE the file
        # (`<file>.algenta-cache` -- a cache directory inside a file is nonsense). The validity
        # gate is the same documented residual class as `weights_i8.cache` (keyed by the manifest,
        # which is stable per checkpoint -- an in-place edit of the source weights would not be
        # caught).
        if gguf_file is not None:
            cache_dir = Path(str(gguf_file) + _CONVERSION_CACHE_DIRNAME)
            if (cache_dir / "manifest.json").is_file() and (
                cache_dir / "weights.blob"
            ).is_file():
                resolved_dir = cache_dir
            else:
                resolved_dir = prepare_model_checkpoint_from_gguf(
                    gguf_file, prompt_token_ids, out_dir=cache_dir
                )
        else:
            cache_dir = Path(checkpoint_dir) / _CONVERSION_CACHE_DIRNAME
            if (cache_dir / "manifest.json").is_file() and (
                cache_dir / "weights.blob"
            ).is_file():
                resolved_dir = cache_dir
            else:
                resolved_dir = prepare_model_checkpoint(
                    checkpoint_dir, prompt_token_ids, out_dir=cache_dir
                )

    if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or max_new_tokens < 1:
        raise InferenceError(
            "invalid_arguments", f"max_new_tokens must be a positive int, got {max_new_tokens!r}"
        )
    if max_ctx is not None:
        if not isinstance(max_ctx, int) or isinstance(max_ctx, bool):
            raise InferenceError("invalid_arguments", f"max_ctx must be an int, got {max_ctx!r}")
        needed = len(prompt_token_ids) + max_new_tokens
        if max_ctx < needed:
            raise InferenceError(
                "invalid_arguments",
                f"max_ctx={max_ctx} is below the {needed} context this call needs "
                f"(n_prompt={len(prompt_token_ids)} + max_new_tokens={max_new_tokens}).",
            )

    if sampling:
        function_name = _FUNCTION_NAME_SAMPLED
        wire_args: list[Any] = [
            str(resolved_dir),
            max_new_tokens,
            float(temperature),
            top_k,
            float(top_p),
            float(min_p),
            float(repeat_penalty),
            float(presence_penalty),
            float(frequency_penalty),
            seed,
            list(prompt_token_ids),
        ]
    else:
        function_name = _FUNCTION_NAME
        wire_args = [
            str(resolved_dir),
            max_new_tokens,
            use_native_grouped_fa_attn_no_mirror,
            use_msl_parity_all_roles,
            list(prompt_token_ids),
            warmup_prefills,
        ]

    envelope = runtime.execute(_MODULE_NAME, function_name, wire_args)
    error = _envelope_error(envelope)
    if error is not None:
        raise InferenceError("runtime_execution_failed", error)

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise InferenceError(
            "runtime_execution_failed", "the local runtime returned a malformed inference result"
        )
    status = result.get("status")
    if status != 620:  # metaldispatch.contract.MB_OK
        code = _status_code_name(status)
        raise InferenceError(code, str(result.get("error_message") or code))

    return InferenceResult(
        token_ids=list(result.get("token_ids") or []),
        n_prompt=int(result.get("n_prompt") or 0),
        stopped_on_eos=bool(result.get("stopped_on_eos")),
        dispatches_per_token=int(result.get("dispatches_per_token") or 0),
        decode_tokens_per_sec=float(result.get("decode_tokens_per_sec") or 0.0),
        prefill_tokens_per_sec=float(result.get("prefill_tokens_per_sec") or 0.0),
        generated_text=(
            tokenizer.decode(
                list(result.get("token_ids") or [])[int(result.get("n_prompt") or 0) :]
            )
            if tokenizer is not None
            else None
        ),
    )


@dataclass(frozen=True)
class StreamedToken:
    """One token yielded by `decode_stream()`.

    `text_delta` is the incremental text this ONE new token decodes to -- set only when a
    tokenizer is in play (`messages`/`prompt_text` input), `None` for `prompt_token_ids` input,
    matching `InferenceResult.generated_text`'s own "only when a tokenizer was loaded" convention.
    """

    token_id: int
    text_delta: str | None
    position: int
    done: bool
    stopped_on_eos: bool


def decode_stream(
    *,
    checkpoint_dir: str | Path,
    prompt_token_ids: list[int] | None = None,
    prompt_text: str | None = None,
    messages: list[dict] | None = None,
    tools: list[dict] | None = None,
    max_new_tokens: int = 16,
    use_msl_parity_all_roles: bool = True,
    use_native_grouped_fa_attn_no_mirror: bool = True,
    converted_checkpoint_dir: str | Path | None = None,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> Iterator[StreamedToken]:
    """Real, token-by-token streaming twin of `decode()` -- same inputs, same resolved GPU
    execution plan, same token sequence for the same prompt + params, delivered one token at a
    time instead of all at once. `decode()` itself is completely untouched by this function; the
    validation and tokenization logic below intentionally mirrors (not calls) the corresponding
    section of `decode()`, since this function's scope -- see below -- is a real subset of
    `decode()`'s own, not the same set of inputs forwarded through a shared helper.

    Unlike `decode()`, this takes no `runtime: MojoRuntime` parameter: the wire messages this
    drives (`qwen3_decode_open`/`_next`/`_close`) are bespoke, connection-scoped operations reached
    directly through `algenta.native.worker` -- exactly like `algenta.session.open_dataset`/
    `stream_chunks` -- not `library_execute` capability calls a `MojoRuntime.execute(module,
    function, args)` would route through.

    Scope narrower than `decode()`, deliberately (the full account is in `mojo/engine/
    algenta_runtime/qwen3_decode_session.mojo`'s module docstring):
    * GREEDY ONLY -- `temperature` must be 0 (the default). `temperature > 0` raises
      `InferenceError("sampling_not_supported_in_stream", ...)` rather than silently running
      greedy, or silently running the sampled path with no way to stream its per-step RNG/penalty
      state (which this function's session registry does not carry).
    * HuggingFace checkpoint directories only -- a GGUF file path raises
      `InferenceError("gguf_not_supported_in_stream", ...)`; call `decode()` for GGUF checkpoints.
    * No caller-facing `max_ctx` guard -- the resident session always sizes its own context from
      `len(prompt_token_ids) + max_new_tokens` (bucketed to a power of two on the Mojo side), so
      there is no one-shot-call-only ceiling to mirror here.

    CRITICAL correctness property, not a nicety: the underlying GPU session is closed in a
    `finally` block, so a caller that stops iterating before the last token (an early `break`, an
    HTTP client disconnecting mid-stream) still releases the session instead of leaking it -- proven
    by this function's own abandonment test (partially consume, drop the generator, confirm a fresh
    session opens and generates correctly right afterward -- impossible if the abandoned one were
    still holding the connection's one resident-session slot).
    """
    if temperature > 0.0:
        raise InferenceError(
            "sampling_not_supported_in_stream",
            "decode_stream() only implements the greedy (temperature=0) code path; sampled"
            " streaming is a separate, not-yet-built follow-up. Call decode() for temperature > 0.",
        )

    provided = sum(value is not None for value in (prompt_token_ids, prompt_text, messages))
    if provided != 1:
        raise InferenceError(
            "invalid_arguments",
            "pass exactly one of prompt_token_ids, prompt_text, or messages",
        )
    if tools is not None and messages is None:
        raise InferenceError(
            "invalid_arguments",
            "tools is only valid alongside messages -- it is rendered into the prompt by the "
            "chat template, which prompt_text/prompt_token_ids bypass entirely",
        )

    gguf_file = _gguf_checkpoint_file(checkpoint_dir)
    if gguf_file is not None:
        raise InferenceError(
            "gguf_not_supported_in_stream",
            f"{gguf_file} is a GGUF file; decode_stream() supports HuggingFace checkpoint "
            "directories only. Call decode() for GGUF checkpoints.",
        )

    # Run the SAME comprehensive, fact-based architecture gate prepare_model_checkpoint() uses,
    # unconditionally -- not only on the code path that actually converts. A caller that already
    # has a converted_checkpoint_dir (or a cached one from a prior call) would otherwise skip this
    # entirely, trusting an old manifest's shape forever even if the config it came from declares
    # a fact no kernel implements (e.g. a mixture-of-experts routing field): "ignoring an
    # unimplemented fact runs fluent-but-wrong math" (_validate_architecture's own words) is
    # exactly the failure mode this call exists to prevent, on every entry into this function, not
    # just the first.
    _config_path = Path(checkpoint_dir) / "config.json"
    if not _config_path.is_file():
        raise InferenceError(
            "checkpoint_not_found",
            f"{checkpoint_dir} does not look like a HuggingFace checkpoint snapshot: "
            f"{_config_path.name} is missing.",
        )
    _config = _normalize_config(json.loads(_config_path.read_text(encoding="utf-8")))
    _is_gemma3 = _config.get("model_type") == "gemma3_text"
    if _is_gemma3:
        _config = _gemma3_prepare_config(_config, Path(checkpoint_dir))
    _validate_architecture(Path(checkpoint_dir), _config, config_source=str(_config_path))
    if not _is_gemma3:
        _validate_rope_scaling(_config, config_source=str(_config_path))

    # _validate_architecture above is backend-agnostic by design (conversion serves every
    # backend). This path only ever runs on the metal resident session, so also run the
    # backend-aware gate -- family membership, q/k/v bias availability, and the THEORETICAL
    # metal staging-tier ceiling (any shipped tier, not necessarily the one THIS binary was
    # built with) -- so a model metal can never run on ANY tier is refused here, with the
    # real reason, rather than reaching the Mojo layer at all.
    from algenta.model_capabilities import extract_facts_from_config, refusals_for_facts

    _facts = extract_facts_from_config(_config)
    # probed=True to match _validate_architecture's exact convention above: the probe-only
    # facts (attention_bias, qk_norm) are never populated by extract_facts_from_config() from a
    # config alone, so this cannot let a real hazard through -- it only keeps this check's
    # behavior consistent with the gate immediately above it rather than introducing a second,
    # differently-tuned variant of the same call.
    _refusals = refusals_for_facts(_facts, backend="metal", probed=True, enforce_backend=True)
    if _refusals:
        raise InferenceError(
            "unsupported_architecture",
            f"{checkpoint_dir} {_config_path.name}: " + "; ".join(r.message() for r in _refusals),
        )

    # Narrower than the theoretical check above: THIS SPECIFIC worker binary's own compiled
    # staging tier, self-reported in its ready handshake (a value fixed at build time by
    # -D ALGENTA_STAGE_6144 or its absence, never runtime-detected -- see main.mojo). A model
    # can pass the theoretical metal-family check above (needs <=6144) yet still exceed the
    # tier THIS particular binary shipped with (e.g. the default 3072 build) -- refuse that
    # here, by name and by number, instead of a build-time specialization failing deep inside
    # a Metal preflight with a bare status code.
    from algenta.model_capabilities import stage_needed
    from algenta.native import worker as _native_worker
    from algenta.native.loader import _fallback_mode

    _needed = stage_needed(_facts)
    if _needed is not None:
        try:
            _tier = _native_worker.handshake(
                module_name=_MODULE_NAME, require_verified=_fallback_mode() != "allow",
            ).get("resident_max_d_model")
        except _native_worker.NativeWorkerUnavailable:
            _tier = None
        if isinstance(_tier, int) and _needed > _tier:
            raise InferenceError(
                "stage_needed_exceeds_compiled_tier",
                f"{checkpoint_dir} needs a staging tier of at least {_needed} "
                "(max(hidden_size, num_attention_heads*head_dim, intermediate_size)), but this "
                f"worker binary was compiled with a staging ceiling of {_tier} "
                "(RESIDENT_MAX_D_MODEL, fixed by -D ALGENTA_STAGE_6144 at build time). Rebuild "
                "the worker with a larger staging tier to run this model.",
            )

    tokenizer = None
    if messages is not None:
        if not isinstance(messages, list) or not messages:
            raise InferenceError(
                "invalid_arguments",
                f"messages must be a non-empty list of message dicts, got {messages!r}",
            )
        from algenta.chat_template import ChatTemplateError, apply_chat_template
        from algenta.tokenizer import load_tokenizer

        try:
            prompt_text = apply_chat_template(checkpoint_dir, messages, tools=tools)
        except ChatTemplateError as exc:
            raise InferenceError("unsupported_chat_template", str(exc)) from exc
        tokenizer = load_tokenizer(checkpoint_dir)
        prompt_token_ids = tokenizer.encode(prompt_text, add_special_tokens=True)
    elif prompt_text is not None:
        if not isinstance(prompt_text, str) or not prompt_text:
            raise InferenceError(
                "invalid_arguments", f"prompt_text must be a non-empty str, got {prompt_text!r}"
            )
        from algenta.tokenizer import load_tokenizer

        tokenizer = load_tokenizer(checkpoint_dir)
        prompt_token_ids = tokenizer.encode(prompt_text, add_special_tokens=True)
    if not isinstance(prompt_token_ids, list) or not prompt_token_ids:
        raise InferenceError(
            "invalid_arguments", "the prompt must tokenize to at least one token id"
        )

    if (
        not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool)
        or max_new_tokens < 1
    ):
        raise InferenceError(
            "invalid_arguments", f"max_new_tokens must be a positive int, got {max_new_tokens!r}"
        )

    if converted_checkpoint_dir is not None:
        resolved_dir = Path(converted_checkpoint_dir)
        if not (resolved_dir / "manifest.json").is_file() or not (
            resolved_dir / "weights.blob"
        ).is_file():
            raise InferenceError(
                "checkpoint_not_found",
                f"{resolved_dir} has no manifest.json/weights.blob; convert it first with "
                "prepare_model_checkpoint(), or omit converted_checkpoint_dir to convert "
                "automatically.",
            )
    else:
        # Same conversion cache decode() uses (parity gap 2): one conversion per checkpoint,
        # reused across many prompts/sessions.
        cache_dir = Path(checkpoint_dir) / _CONVERSION_CACHE_DIRNAME
        if (cache_dir / "manifest.json").is_file() and (cache_dir / "weights.blob").is_file():
            resolved_dir = cache_dir
        else:
            resolved_dir = prepare_model_checkpoint(
                checkpoint_dir, prompt_token_ids, out_dir=cache_dir
            )

    from algenta.native.loader import _fallback_mode
    from algenta.qwen3_decode_session import (
        Qwen3DecodeSessionError,
        close_qwen3_decode_session,
        open_qwen3_decode_session,
        step_qwen3_decode_session,
    )

    require_verified = _fallback_mode() != "allow"
    routing_module = _MODULE_NAME  # see that module's own docstring on why this is a no-op for
    # actual shard selection today (algenta_runtime.* is excluded from the shard inventory) and
    # kept anyway for a consistent, self-documenting call shape.

    try:
        handle = open_qwen3_decode_session(
            str(resolved_dir),
            list(prompt_token_ids),
            max_new_tokens=max_new_tokens,
            routing_module=routing_module,
            timeout=timeout,
            require_verified=require_verified,
            use_native_grouped_fa_attn_no_mirror=use_native_grouped_fa_attn_no_mirror,
            use_msl_parity_all_roles=use_msl_parity_all_roles,
        )
    except Qwen3DecodeSessionError as exc:
        raise InferenceError(exc.code, str(exc)) from exc

    # Decoding one token id in isolation drops cross-token spacing state a SentencePiece-style
    # tokenizer (Llama family) tracks between tokens -- a lone token decodes with no leading
    # space, even when the same id decodes WITH one as part of a longer sequence (a BPE-style
    # tokenizer like Qwen3's bakes the space into the token's own text and has no such state,
    # which is why this was never caught by the Qwen3-only test suite). The correct, standard
    # streaming-tokenizer pattern: decode the WHOLE sequence generated so far on every step and
    # take the suffix past what was already emitted, matching e.g. HuggingFace's
    # TextIteratorStreamer.
    generated_ids: list[int] = []
    emitted_text = ""

    try:
        while True:
            try:
                step = step_qwen3_decode_session(
                    handle,
                    routing_module=routing_module,
                    timeout=timeout,
                    require_verified=require_verified,
                )
            except Qwen3DecodeSessionError as exc:
                raise InferenceError(exc.code, str(exc)) from exc

            token_id = int(step["token_id"])
            text_delta: str | None = None
            if tokenizer is not None:
                generated_ids.append(token_id)
                full_text = tokenizer.decode(generated_ids)
                text_delta = full_text[len(emitted_text) :]
                emitted_text = full_text
            yield StreamedToken(
                token_id=token_id,
                text_delta=text_delta,
                position=int(step["position"]),
                done=bool(step["done"]),
                stopped_on_eos=bool(step["stopped_on_eos"]),
            )
            if step["done"]:
                break
    finally:
        # Runs on normal completion, on an early break/return in the caller's loop, and on the
        # caller's generator being garbage-collected without being fully consumed -- the ONE path
        # that must never leak the resident GPU session (see this function's own docstring).
        try:
            close_qwen3_decode_session(
                handle, routing_module=routing_module, timeout=timeout,
                require_verified=require_verified,
            )
        except Qwen3DecodeSessionError:
            # The connection may already be gone, or the session already closed by an earlier
            # path through this same block -- a leaked handle dies with the connection either way.
            pass


@dataclass(frozen=True)
class BatchedInferenceResult:
    """A batched decode call's whole outcome (beat-llama.cpp campaign concurrent front,
    2026-08-11). `generated_token_ids[b]` is sequence b's generated tokens (exactly
    `max_new_tokens` each; prompts are NOT echoed back -- the caller supplied them).
    `decode_tokens_per_sec` is the SYSTEM throughput: all B sequences' decode steps divided by
    the shared decode wall (this is the concurrent-throughput number). `prefill_tokens_per_sec`
    covers all B prompt ingests. `prefill_chunks` reports B."""

    generated_token_ids: list[list[int]]
    n_prompt_total: int
    stopped_on_eos: bool
    dispatches_per_token: int
    decode_tokens_per_sec: float
    prefill_tokens_per_sec: float
    prefill_chunks: int


def decode_batched(
    runtime: Any,
    *,
    checkpoint_dir: str | Path,
    prompt_token_ids_list: list[list[int]],
    max_new_tokens: int = 16,
    use_msl_parity_all_roles: bool = True,
    converted_checkpoint_dir: str | Path | None = None,
    timeout: float | None = None,
) -> BatchedInferenceResult:
    """Decode B prompts TOGETHER through the Slipstream batched decode path: one weight sweep
    per generated token for all B sequences (continuous-batching kernel tier, B <= 32), greedy.

    Wire contract mirrors the engine entry point: the prompts are flattened into one list with
    per-sequence lengths; the engine ingests each into its own batched KV-cache slot and steps
    all B in one descriptor-table submission per token. Every sequence generates exactly
    `max_new_tokens` (v1 has no per-sequence early stop). Returns a `BatchedInferenceResult`
    whose `decode_tokens_per_sec` is the SYSTEM throughput across the batch.

    Raises `InferenceError` for any refusal (invalid B, empty/oversized prompts, engine
    refusals) with the same stable `code` discipline as `decode()`.

    `timeout` bounds the single runtime call (ingest of ALL prompts + the whole shared decode
    loop); the default is budgeted from the batch's total token count because deep batches run
    far past the runtime's 30s single-request default."""
    if not isinstance(prompt_token_ids_list, list) or not prompt_token_ids_list:
        raise InferenceError(
            "invalid_arguments", "prompt_token_ids_list must be a non-empty list of id lists"
        )
    n_seqs = len(prompt_token_ids_list)
    if n_seqs > _BATCH_DECODE_MAX_SEQS:
        raise InferenceError(
            "invalid_arguments",
            f"batched decode supports at most {_BATCH_DECODE_MAX_SEQS} sequences, got {n_seqs}",
        )
    prompt_lens: list[int] = []
    flat_ids: list[int] = []
    for b, ids in enumerate(prompt_token_ids_list):
        if not isinstance(ids, list) or not ids:
            raise InferenceError(
                "invalid_arguments", f"prompt {b} must be a non-empty list of token ids"
            )
        prompt_lens.append(len(ids))
        flat_ids.extend(int(t) for t in ids)
    if n_seqs == 1:
        # The batched decode kernel tier faults at B=1 (out-of-bounds write in the split-K
        # epilogues' padded rows, which are all-but-one of the 32-row tiles at B=1). A single
        # sequence has nothing to batch anyway, so delegate to the serial path -- token-identical
        # and it never touches the faulty B=1 batched table.
        single = decode(
            runtime,
            checkpoint_dir=checkpoint_dir,
            prompt_token_ids=prompt_token_ids_list[0],
            max_new_tokens=max_new_tokens,
            use_msl_parity_all_roles=use_msl_parity_all_roles,
            converted_checkpoint_dir=converted_checkpoint_dir,
        )
        return BatchedInferenceResult(
            generated_token_ids=[list(single.token_ids[single.n_prompt :])],
            n_prompt_total=single.n_prompt,
            stopped_on_eos=single.stopped_on_eos,
            dispatches_per_token=single.dispatches_per_token,
            decode_tokens_per_sec=single.decode_tokens_per_sec,
            prefill_tokens_per_sec=single.prefill_tokens_per_sec,
            prefill_chunks=1,
        )
    if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or max_new_tokens < 1:
        raise InferenceError(
            "invalid_arguments", f"max_new_tokens must be a positive int, got {max_new_tokens!r}"
        )

    checkpoint_dir = str(checkpoint_dir)
    if converted_checkpoint_dir is not None:
        resolved_dir = Path(converted_checkpoint_dir)
        if not (resolved_dir / "manifest.json").is_file() or not (
            resolved_dir / "weights.blob"
        ).is_file():
            raise InferenceError(
                "checkpoint_not_found",
                f"{resolved_dir} has no manifest.json/weights.blob; convert it first with "
                "prepare_model_checkpoint(), or omit converted_checkpoint_dir to convert "
                "automatically.",
            )
    else:
        cache_dir = Path(checkpoint_dir) / _CONVERSION_CACHE_DIRNAME
        if (cache_dir / "manifest.json").is_file() and (cache_dir / "weights.blob").is_file():
            resolved_dir = cache_dir
        else:
            # The manifest bakes ONE input_ids array; the batched entry point never reads it
            # (prompts travel over the wire), so the FIRST sequence's prompt stands in.
            resolved_dir = prepare_model_checkpoint(
                checkpoint_dir, prompt_token_ids_list[0], out_dir=cache_dir
            )

    wire_args: list[Any] = [
        str(resolved_dir),
        max_new_tokens,
        use_msl_parity_all_roles,
        flat_ids,
        prompt_lens,
    ]
    # One call ingests ALL prompts and generates B*max_new_tokens tokens -- deep batches run far
    # longer than the runtime's 30s single-request default (measured: 8K x B=16 needs ~30s for the
    # ingest alone). Budget >=1000 tok/s aggregate plus headroom unless the caller overrides.
    if timeout is None:
        total_tokens = sum(prompt_lens) + n_seqs * max_new_tokens
        timeout = max(60.0, total_tokens / 1000.0 + 30.0)
    envelope = runtime.execute(_MODULE_NAME, _FUNCTION_NAME_BATCHED, wire_args, timeout=timeout)
    error = _envelope_error(envelope)
    if error is not None:
        raise InferenceError("runtime_execution_failed", error)

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise InferenceError(
            "runtime_execution_failed", "the local runtime returned a malformed inference result"
        )
    status = result.get("status")
    if status != 620:  # metaldispatch.contract.MB_OK
        code = _status_code_name(status)
        raise InferenceError(code, str(result.get("error_message") or code))

    flat_gen = list(result.get("token_ids") or [])
    per_seq: list[list[int]] = []
    for b in range(n_seqs):
        per_seq.append(flat_gen[b * max_new_tokens : (b + 1) * max_new_tokens])
    return BatchedInferenceResult(
        generated_token_ids=per_seq,
        n_prompt_total=int(result.get("n_prompt") or 0),
        stopped_on_eos=bool(result.get("stopped_on_eos")),
        dispatches_per_token=int(result.get("dispatches_per_token") or 0),
        decode_tokens_per_sec=float(result.get("decode_tokens_per_sec") or 0.0),
        prefill_tokens_per_sec=float(result.get("prefill_tokens_per_sec") or 0.0),
        prefill_chunks=int(result.get("prefill_chunks") or 0),
    )


_STATUS_NAMES: dict[int, str] = {
    620: "metaldispatch_ok",
    621: "metaldispatch_shader_toolchain_absent",
    622: "metaldispatch_no_device",
    623: "metaldispatch_session_open_failed",
    624: "metaldispatch_pipeline_not_found",
    625: "metaldispatch_buffer_alloc_failed",
    626: "metaldispatch_upload_length",
    627: "metaldispatch_context_full",
    628: "metaldispatch_dispatch_failed",
    629: "metaldispatch_dispatch_count_mismatch",
    630: "metaldispatch_code_out_of_range",
    631: "metaldispatch_checkpoint_unreadable",
    632: "metaldispatch_unsupported_architecture",
}


def _status_code_name(status: Any) -> str:
    if isinstance(status, int) and status in _STATUS_NAMES:
        return _STATUS_NAMES[status]
    return "metaldispatch_code_out_of_range"
