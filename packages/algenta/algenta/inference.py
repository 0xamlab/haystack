"""Model-agnostic LLM inference on Apple Silicon, through the real compiled runtime.

This is the model-agnostic door onto the Metal GPU kernel path. Unlike `algenta.qwen3_decode`
(which is pinned to Qwen3-0.6B-Base's exact shape), this module accepts ANY model whose architecture
the kernels support and routes it to the model-agnostic entry point, so one call works across model
sizes without a per-shape SDK function.

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
* **Architecture family, not one shape.** The kernels implement the Qwen3 decoder family (GQA with
  RMSNorm on Q/K, tied embeddings, SiLU-gated FFN, RoPE, no attention bias). Any model matching those
  structural invariants and the kernel alignment gates (d_model / d_ff / n_q divisible by 32, GQA ratio
  integral) runs; anything else raises `UnsupportedArchitectureError` naming the exact mismatch. This
  is "any model within the supported family," not "any architecture ever" -- no other architecture
  family has kernels yet.
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


def _validate_architecture(checkpoint_dir: Path, config: dict[str, Any]) -> None:
    """Validate the structural invariants the kernels rely on, from config.json alone."""
    missing = [key for key in _STRUCTURAL_FIELDS if key not in config]
    if missing:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} config.json is missing required "
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
    if config.get("tie_word_embeddings") is not True:
        problems.append("the kernels expect tied word embeddings (tie_word_embeddings=true)")
    if config.get("attention_bias") not in (False, None):
        problems.append("the kernels expect no attention bias (attention_bias=false)")
    if problems:
        raise UnsupportedArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} is not a supported model. "
            f"Problems: {'; '.join(problems)}. This module runs Qwen3-family decoders whose dims "
            "meet the kernel alignment gates."
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
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_architecture(checkpoint_dir, config)

    if not isinstance(prompt_token_ids, list) or not prompt_token_ids:
        raise InferenceError(
            "invalid_arguments", "prompt_token_ids must be a non-empty list of token ids"
        )
    for token_id in prompt_token_ids:
        if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
            raise InferenceError(
                "invalid_arguments", f"prompt_token_ids must be non-negative ints, got {token_id!r}"
            )

    # Load the shard index if present (multi-shard checkpoints).
    index_path = checkpoint_dir / "model.safetensors.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else None

    n_layers = config["num_hidden_layers"]
    required = ["model.embed_tokens.weight", "model.norm.weight"]
    for layer in range(n_layers):
        prefix = f"model.layers.{layer}."
        required += [
            prefix + suffix
            for suffix in (
                "input_layernorm.weight",
                "post_attention_layernorm.weight",
                "self_attn.q_norm.weight",
                "self_attn.k_norm.weight",
                "self_attn.q_proj.weight",
                "self_attn.k_proj.weight",
                "self_attn.v_proj.weight",
                "self_attn.o_proj.weight",
                "mlp.gate_proj.weight",
                "mlp.up_proj.weight",
                "mlp.down_proj.weight",
            )
        ]

    resolved_out_dir = (
        Path(out_dir) if out_dir is not None else Path(tempfile.mkdtemp(prefix="algenta-model-ckpt-"))
    )
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    blob_chunks = []
    manifest_tensors: dict[str, Any] = {}
    cursor = 0
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
        n_elements = 1
        for dim in shape:
            n_elements *= dim
        transposed = False
        if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
            values = values.reshape(shape).T.copy().reshape(-1)
            shape = [shape[1], shape[0]]
            transposed = True
        blob_chunks.append(values)
        manifest_tensors[name] = {
            "offset": cursor,
            "n_elements": int(n_elements),
            "shape": shape,
            "transposed": transposed,
        }
        cursor += n_elements

    import numpy as np

    blob = np.concatenate(blob_chunks)
    (resolved_out_dir / "weights.blob").write_bytes(blob.astype("<f8").tobytes())

    manifest = {
        "config": {
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
        },
        "input_ids": list(prompt_token_ids),
        "tensors": manifest_tensors,
    }
    (resolved_out_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return resolved_out_dir


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
        prompt_token_ids = tokenizer.encode(prompt_text)
    elif prompt_text is not None:
        if not isinstance(prompt_text, str) or not prompt_text:
            raise InferenceError(
                "invalid_arguments", f"prompt_text must be a non-empty str, got {prompt_text!r}"
            )
        from algenta.tokenizer import load_tokenizer

        tokenizer = load_tokenizer(checkpoint_dir)
        prompt_token_ids = tokenizer.encode(prompt_text)
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
        # every prompt. The pair lives in `<checkpoint_dir>/.algenta-cache`; its validity gate is
        # the same documented residual class as `weights_i8.cache` (keyed by the manifest, which is
        # stable per checkpoint -- an in-place edit of the source safetensors would not be caught).
        cache_dir = Path(checkpoint_dir) / _CONVERSION_CACHE_DIRNAME
        if (cache_dir / "manifest.json").is_file() and (cache_dir / "weights.blob").is_file():
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
) -> BatchedInferenceResult:
    """Decode B prompts TOGETHER through the Slipstream batched decode path: one weight sweep
    per generated token for all B sequences (continuous-batching kernel tier, B <= 32), greedy.

    Wire contract mirrors the engine entry point: the prompts are flattened into one list with
    per-sequence lengths; the engine ingests each into its own batched KV-cache slot and steps
    all B in one descriptor-table submission per token. Every sequence generates exactly
    `max_new_tokens` (v1 has no per-sequence early stop). Returns a `BatchedInferenceResult`
    whose `decode_tokens_per_sec` is the SYSTEM throughput across the batch.

    Raises `InferenceError` for any refusal (invalid B, empty/oversized prompts, engine
    refusals) with the same stable `code` discipline as `decode()`."""
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
    envelope = runtime.execute(_MODULE_NAME, _FUNCTION_NAME_BATCHED, wire_args)
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
