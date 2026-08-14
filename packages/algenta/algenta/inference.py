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
  architecture family has kernels yet.
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
session reads). `decode()` calls it for you; call it directly to convert once and reuse the result
across many decode calls.

GGUF model files, the llama.cpp interchange format
--------------------------------------------------
`prepare_model_checkpoint_from_gguf()` is the SAME converter with a GGUF front door: a dependency-
free, byte-level GGUF container reader (struct parsing, the same style as the safetensors reader)
that reads the metadata hyperparameters and the tensor table, widens F16/F32/Q8_0 tensors to the
same Float64 weight stream, maps the llama.cpp tensor names (`blk.N.attn_q.weight`, `token_embd.
weight`, ...) onto the HF names the manifest contract uses, and writes the IDENTICAL
`manifest.json` + `weights.blob` pair -- so everything past conversion is the untouched production
path. `decode()` accepts a `.gguf` file directly as `checkpoint_dir` (token-id prompts; a GGUF
carries no `tokenizer.json`, so text prompts stay a HuggingFace-directory feature).
"""

from __future__ import annotations

import json
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "InferenceError",
    "InferenceResult",
    "BatchedInferenceResult",
    "UnsupportedArchitectureError",
    "prepare_model_checkpoint",
    "prepare_model_checkpoint_from_gguf",
    "decode",
    "decode_batched",
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
    already-present `head_dim` is always trusted, never re-derived. Returns a new dict; the caller's
    config is not mutated."""
    if "head_dim" not in config and "hidden_size" in config and "num_attention_heads" in config:
        h_q = config["num_attention_heads"]
        if isinstance(h_q, int) and h_q > 0:
            return {**config, "head_dim": config["hidden_size"] // h_q}
    return config


def _validate_architecture(
    checkpoint_dir: Path, config: dict[str, Any], *, config_source: str = "config.json"
) -> None:
    """Validate the structural invariants the kernels rely on, from the checkpoint's own shape
    declaration alone (`config_source` names where that declaration came from -- config.json for a
    HuggingFace snapshot, GGUF metadata for a .gguf file -- so refusals point at the right file)."""
    missing = [key for key in _STRUCTURAL_FIELDS if key not in config]
    if missing:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} {config_source} is missing required "
            f"fields: {', '.join(missing)}. This module runs models with a Qwen3-style decoder "
            "config (hidden_size, num_hidden_layers, num_attention_heads, num_key_value_heads, "
            "head_dim, intermediate_size, vocab_size, rope_theta, rms_norm_eps)."
        )
    problems = []
    h_q = config["num_attention_heads"]
    h_kv = config["num_key_value_heads"]
    d_model = config["hidden_size"]
    d_ff = config["intermediate_size"]
    d_head = config["head_dim"]
    if h_kv < 1 or h_q % h_kv != 0:
        problems.append(
            f"GQA requires num_attention_heads ({h_q}) % num_key_value_heads ({h_kv}) == 0"
        )
    if d_model % 32 != 0:
        problems.append(f"hidden_size ({d_model}) must be divisible by 32 (GEMM tile alignment)")
    if d_ff % 32 != 0:
        problems.append(f"intermediate_size ({d_ff}) must be divisible by 32 (GEMM tile alignment)")
    if (h_q * d_head) % 32 != 0:
        problems.append(
            f"num_attention_heads*head_dim ({h_q * d_head}) must be divisible by 32 "
            "(GEMM tile alignment)"
        )
    # Llama-family support (2026-08-13): the embedding/lm_head convention is now a BRANCH, not a
    # refusal -- `tie_word_embeddings` true (Qwen3) reuses the embed table as lm_head; false (llama-
    # family) converts the checkpoint's own `lm_head.weight` and the engine binds it separately.
    # Absent means tied (the transformers default). The engine half of this gate (a dedicated
    # lm_head buffer pair in the session) landed in the same change; the manifest carries
    # `tie_word_embeddings` so the kernel side knows which branch it is running.
    if config.get("attention_bias") not in (False, None):
        problems.append("the kernels expect no attention bias (attention_bias=false)")
    if problems:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} is not a supported model. "
            f"Problems: {'; '.join(problems)}. This module runs Qwen3/llama-family decoders whose "
            "dims meet the kernel alignment gates."
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
    n_layers: int, tied_embeddings: bool, has_qk_norm: bool
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
        required += [prefix + suffix for suffix in suffixes]
    return required


def _write_converted_checkpoint(
    resolved_out_dir: Path,
    *,
    entries: list[tuple[str, Any, list[int], bool]],
    config: dict[str, Any],
    prompt_token_ids: list[int],
    has_qk_norm: bool,
    tied_embeddings: bool,
) -> Path:
    """The shared converter tail: concatenate the per-tensor Float64 values (already widened and,
    where the kernels want it, pre-transposed) into `weights.blob`, and write the `manifest.json`
    the production session reads. Both `prepare_model_checkpoint()` (safetensors) and
    `prepare_model_checkpoint_from_gguf()` (GGUF) end here, so the pair they produce is the SAME
    format, written by the SAME code. `entries` is (hf_name, flat f64 values, shape, transposed)."""
    import numpy as np

    blob_chunks = []
    manifest_tensors: dict[str, Any] = {}
    cursor = 0
    for name, values, shape, transposed in entries:
        n_elements = 1
        for dim in shape:
            n_elements *= dim
        blob_chunks.append(values)
        manifest_tensors[name] = {
            "offset": cursor,
            "n_elements": int(n_elements),
            "shape": shape,
            "transposed": transposed,
        }
        cursor += n_elements

    blob = np.concatenate(blob_chunks)
    (resolved_out_dir / "weights.blob").write_bytes(blob.astype("<f8").tobytes())

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
        # converted lm_head.weight. Ints (0/1) because the Mojo side reads them with json_get_int.
        "has_qk_norm": 1 if has_qk_norm else 0,
        "tie_word_embeddings": 1 if tied_embeddings else 0,
    }
    # End-of-sequence id(s) the engine should stop on, carried from the checkpoint's own config
    # instead of a hardcoded constant. Absent on some configs -- only written when present, so an
    # older manifest consumer sees no new key unless the checkpoint declares one.
    if "eos_token_id" in config and config["eos_token_id"] is not None:
        manifest_config["eos_token_id"] = config["eos_token_id"]

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
# the most common quantized export. Anything else is refused by name with its type id.
_GGML_TYPE_F32 = 0
_GGML_TYPE_F16 = 1
_GGML_TYPE_Q8_0 = 8

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

# GGUF `general.architecture` values whose layout matches the supported decoder family (both use
# the identical tensor-name convention above). More archs land as their metadata conventions are
# verified against real files.
_GGUF_SUPPORTED_ARCHITECTURES = ("llama", "qwen3")


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


def _gguf_read_tensor_values(
    path: Path, info: dict[str, Any], data_start: int
) -> tuple[Any, list[int]]:
    """One GGUF tensor's raw bytes widened to a flat Float64 numpy array. Returns
    `(values, shape)` with `shape` in HuggingFace row-major order (the GGUF dims reversed).
    F16/F32 widen exactly; Q8_0 dequantizes as `scale * int8` per 32-element block (the f16 scale
    widens exactly too, so the only rounding is the int8 quantization the file already carries)."""
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
    elif ggml_type == _GGML_TYPE_Q8_0:
        if n_elements % 32 != 0:
            raise InferenceError(
                "unsupported_gguf",
                f"tensor {info['name']!r} is Q8_0 with {n_elements} elements; Q8_0 blocks cover "
                "exactly 32 elements each.",
            )
        n_bytes = (n_elements // 32) * 34  # f16 scale + 32 int8 per block
    else:
        raise InferenceError(
            "unsupported_gguf",
            f"tensor {info['name']!r} is ggml type {ggml_type}; this converter reads F32, F16 and "
            "Q8_0 tensors. Re-export the GGUF with one of those (llama.cpp's "
            "convert_hf_to_gguf.py --outtype f16 is the common choice).",
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
    else:  # Q8_0
        block_dtype = np.dtype([("scale", "<f2"), ("qs", "i1", (32,))])
        blocks = np.frombuffer(raw, dtype=block_dtype)
        values = (
            blocks["qs"].astype(np.float64) * blocks["scale"].astype(np.float64)[:, None]
        ).reshape(-1)
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

    hf_tensors: dict[str, dict[str, Any]] = {}
    for info in tensor_infos:
        hf_name = _gguf_map_tensor_name(info["name"])
        if hf_name is not None:
            hf_tensors[hf_name] = info
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

    entries: list[tuple[str, Any, list[int], bool]] = []
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
        entries.append((name, values, shape, transposed))

    return _write_converted_checkpoint(
        resolved_out_dir,
        entries=entries,
        config=config,
        prompt_token_ids=prompt_token_ids,
        has_qk_norm=has_qk_norm,
        tied_embeddings=tied_embeddings,
    )


def _gguf_checkpoint_file(checkpoint_dir: str | Path) -> Path | None:
    """The GGUF front door for `decode()`: an EXISTING file as the checkpoint is a GGUF model file
    (the magic check inside the reader is the validator); a directory stays the HuggingFace path."""
    path = Path(checkpoint_dir)
    return path if path.is_file() else None


def prepare_model_checkpoint(
    checkpoint_dir: str | Path,
    prompt_token_ids: list[int],
    *,
    out_dir: str | Path | None = None,
) -> Path:
    """Validate `checkpoint_dir`'s architecture, then convert it into the `manifest.json` +
    `weights.blob` pair the model-agnostic kernel entry point reads. Handles any supported-family
    model, single- or multi-shard.

    `checkpoint_dir` is a local HuggingFace snapshot directory (`config.json` + one or more
    `model*.safetensors`). Raises `UnsupportedArchitectureError` for an unsupported architecture and
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
    _validate_architecture(checkpoint_dir, config)
    _validate_prompt_token_ids(prompt_token_ids)

    # Load the shard index if present (multi-shard checkpoints).
    index_path = checkpoint_dir / "model.safetensors.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else None

    tied_embeddings = config.get("tie_word_embeddings", True) is True
    has_qk_norm = _detect_has_qk_norm(checkpoint_dir, index)
    required = _required_hf_tensor_names(config["num_hidden_layers"], tied_embeddings, has_qk_norm)

    resolved_out_dir = (
        Path(out_dir) if out_dir is not None else Path(tempfile.mkdtemp(prefix="algenta-model-ckpt-"))
    )
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[str, Any, list[int], bool]] = []
    for name in sorted(required):
        shard_path = _resolve_shard_for_tensor(checkpoint_dir, name, index)
        header, data_start = _read_safetensors_header(shard_path)
        info = header.get(name)
        if info is None:
            raise InferenceError(
                "checkpoint_not_found", f"tensor {name!r} not found in {shard_path}."
            )
        if info.get("dtype") != "BF16":
            raise InferenceError(
                "checkpoint_not_found",
                f"{name} in {shard_path} is {info.get('dtype')}, expected BF16 -- this converter "
                "handles BF16 checkpoints.",
            )
        shape = list(info["shape"])
        start, end = info["data_offsets"]
        with shard_path.open("rb") as handle:
            handle.seek(data_start + start)
            raw = handle.read(end - start)
        values = _bf16_bytes_to_f64(raw)
        transposed = False
        if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
            values = values.reshape(shape).T.copy().reshape(-1)
            shape = [shape[1], shape[0]]
            transposed = True
        entries.append((name, values, shape, transposed))

    return _write_converted_checkpoint(
        resolved_out_dir,
        entries=entries,
        config=config,
        prompt_token_ids=prompt_token_ids,
        has_qk_norm=has_qk_norm,
        tied_embeddings=tied_embeddings,
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
    A GGUF checkpoint accepts `prompt_token_ids` only (it carries no tokenizer.json for text or
    chat prompts).

    Pass EXACTLY ONE of:
    * `messages` -- a list of OpenAI-style chat dicts, formatted with the checkpoint's OWN chat
      template (`algenta.chat_template`) and tokenized with its tokenizer. Refuses with
      `InferenceError("unsupported_chat_template")` if the checkpoint ships no supported template.
    * `prompt_text` -- raw text tokenized with the checkpoint's own tokenizer.json via
      `algenta.tokenizer` (no chat template applied).
    * `prompt_token_ids` -- pure token math, no tokenizer loaded.
    With `messages` or `prompt_text` the result also carries `generated_text`.

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
    # The GGUF front door (beat-llama.cpp campaign, model coverage): an EXISTING FILE as the
    # checkpoint is a GGUF model file, decoded through the same conversion+engine path. A GGUF
    # carries no tokenizer.json, so text/chat prompts stay a HuggingFace-directory feature.
    gguf_file = _gguf_checkpoint_file(checkpoint_dir)
    if gguf_file is not None and (prompt_text is not None or messages is not None):
        raise InferenceError(
            "invalid_arguments",
            f"{gguf_file} is a GGUF model file; GGUF checkpoints decode from prompt_token_ids "
            "only (a GGUF carries no tokenizer.json for text prompts -- point prompt_text/"
            "messages at the matching HuggingFace checkpoint directory instead).",
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
            prompt_text = apply_chat_template(checkpoint_dir, messages)
        except ChatTemplateError as exc:
            raise InferenceError("unsupported_chat_template", str(exc)) from exc
        tokenizer = load_tokenizer(checkpoint_dir)
        # add_special_tokens=True is the transformers default-encode convention: a no-op on
        # Qwen3 prompts, and the BOS prepend a llama-family prompt expects.
        prompt_token_ids = tokenizer.encode(prompt_text, add_special_tokens=True)
    elif prompt_text is not None:
        if not isinstance(prompt_text, str) or not prompt_text:
            raise InferenceError(
                "invalid_arguments", f"prompt_text must be a non-empty str, got {prompt_text!r}"
            )
        from algenta.tokenizer import load_tokenizer

        tokenizer = load_tokenizer(checkpoint_dir)
        # add_special_tokens=True is the transformers default-encode convention: a no-op on
        # Qwen3 prompts, and the BOS prepend a llama-family prompt expects.
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
