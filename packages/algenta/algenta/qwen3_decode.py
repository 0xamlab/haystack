"""Qwen3-0.6B-Base greedy decode on Apple Silicon, through the real compiled runtime.

This is the Python-side door onto `metaldispatch.qwen3_decode.qwen3_i8_allsimd7_decode_flat` — the
ONE new, additive Mojo entry point that makes `_MBQwen3I8AllSimd7` (an int8-weight, SIMD-shuffle
SDPA/GEMV/lm_head/argmax-reduce, dynamic-split-K Metal GPU decode kernel path, race-verified against
`mlx-lm` and `llama.cpp` on Qwen3-0.6B-Base) callable from `pip install algenta`, not only from a
hand-run benchmark driver.

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
* **One model shape**: Qwen3-0.6B-Base, exactly — `hidden_size=1024`, `num_hidden_layers=28`,
  `num_attention_heads=16`, `num_key_value_heads=8`, `head_dim=128`, `intermediate_size=3072`,
  `vocab_size=151936`, tied embeddings, no attention bias, SiLU-gated FFN. A checkpoint of any other
  shape (including other Qwen3 sizes) raises `UnsupportedCheckpointArchitectureError` naming the
  mismatch — it is never silently run through the wrong-shaped kernel.
* **One hardware family**: Apple Silicon with Metal. A binary built without `-D ALGENTA_GPU`, or a
  host with no Metal accelerator, raises `Qwen3DecodeError` with a status naming exactly that — never
  a silent CPU fallback.
* **One decode mode**: greedy (argmax), one-shot. This kernel path has never supported step-by-step
  invocation from outside one process — every existing driver for this arm opens a session, prefills,
  decodes to `max_new_tokens` or EOS, and exits. `qwen3_i8_allsimd7_decode()` matches that shape
  exactly rather than offering a streaming API this kernel does not back.
* **Tokens in, tokens out.** This module does not tokenize text. Pass `prompt_token_ids` you already
  produced with the checkpoint's own tokenizer (e.g. `transformers.AutoTokenizer`) — the same
  network-independent, separate-artifact-acquisition-stage pattern this project already uses for the
  checkpoint download itself. Building a tokenizer here would be a second, un-audited implementation
  of a correctness-sensitive component nothing in this task asked for.

Usage
-----
    from algenta import MojoRuntime, qwen3_i8_allsimd7_decode

    runtime = MojoRuntime(mode="local")
    result = qwen3_i8_allsimd7_decode(
        runtime,
        checkpoint_dir="/path/to/Qwen3-0.6B-Base",   # your own downloaded HF snapshot
        prompt_token_ids=[785, 6722, 315, 9625, 374],  # "The capital of France is"
        max_new_tokens=16,
    )
    result.token_ids            # prompt ids followed by every generated id
    result.decode_tokens_per_sec
    result.prefill_tokens_per_sec

Checkpoint conversion, and why it is a separate, inspectable step
------------------------------------------------------------------
`_MBQwen3I8AllSimd7` reads weights from a flat `manifest.json` + `weights.blob` pair, not from a raw
HuggingFace snapshot directly — the same format
`benchmarks/llm_smoke/generate_manifest.py` produces for every existing benchmark driver of this arm.
`prepare_checkpoint()` is a second, independent implementation of that exact conversion (byte-level
safetensors header parse, exact BF16->Float64 widen, the same seven weight tensors pre-transposed for
`sgemm_flat`'s fast path) — proven byte-for-byte equivalent to `generate_manifest.py`'s own output by
direct diff (see `tests/test_qwen3_decode_checkpoint_conversion.py`), not merely "should produce the
same thing". `qwen3_i8_allsimd7_decode()` calls it for you; call `prepare_checkpoint()` directly to
convert once and reuse the result across many decode calls without repeating the conversion cost.
"""

from __future__ import annotations

import json
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "Qwen3DecodeError",
    "Qwen3DecodeResult",
    "UnsupportedCheckpointArchitectureError",
    "QWEN3_0_6B_BASE_ARCHITECTURE",
    "prepare_checkpoint",
    "qwen3_i8_allsimd7_decode",
]

_MODULE_NAME = "metaldispatch.qwen3_decode"
_FUNCTION_NAME = "qwen3_i8_allsimd7_decode_flat"

#: The EXACT (and only) architecture `_MBQwen3I8AllSimd7`'s compiled kernels were sized for. Mirrors
#: `mojo/engine/metaldispatch/qwen3_decode.mojo`'s own `QWEN3_0_6B_BASE_*` constants and
#: `benchmarks/llm_smoke/generate_manifest.py`'s module-level constants — kept as its own literal
#: (rather than importing either) because this package must not depend on `mojo/` or `benchmarks/`
#: source files at runtime; cross-checked against both by
#: `tests/test_qwen3_decode_checkpoint_conversion.py`.
QWEN3_0_6B_BASE_ARCHITECTURE: dict[str, Any] = {
    "hidden_size": 1024,
    "num_hidden_layers": 28,
    "num_attention_heads": 16,
    "num_key_value_heads": 8,
    "head_dim": 128,
    "intermediate_size": 3072,
    "vocab_size": 151936,
    "tie_word_embeddings": True,
    "attention_bias": False,
    "hidden_act": "silu",
}

# Weight tensors pre-transposed from HF's [out_features, in_features] to [in_features, out_features]
# so the Mojo driver's GEMM calls take the fast (non-transposed) path — identical set and identical
# reasoning to `generate_manifest.py`'s own `_TRANSPOSE_SUFFIXES`.
_TRANSPOSE_SUFFIXES = (
    "self_attn.q_proj.weight",
    "self_attn.k_proj.weight",
    "self_attn.v_proj.weight",
    "self_attn.o_proj.weight",
    "mlp.gate_proj.weight",
    "mlp.up_proj.weight",
    "mlp.down_proj.weight",
)


class Qwen3DecodeError(RuntimeError):
    """A `qwen3_i8_allsimd7_decode()` call refused to run, or the runtime call itself failed.

    `code` is a stable string: either one of `metaldispatch.contract`'s own status names (e.g.
    `"metaldispatch_no_device"`, `"metaldispatch_shader_toolchain_absent"`) surfaced verbatim from
    the Mojo side, or a client-side code raised before the wire call was even attempted (e.g.
    `"checkpoint_not_found"`).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UnsupportedCheckpointArchitectureError(Qwen3DecodeError):
    """The checkpoint at `checkpoint_dir` does not match Qwen3-0.6B-Base's exact shape.

    Raised on the Python side, before any conversion or GPU work, from the checkpoint's own
    `config.json` — the cheapest possible point to refuse a shape this kernel path cannot run.
    """

    def __init__(self, message: str) -> None:
        super().__init__("unsupported_architecture", message)


@dataclass(frozen=True)
class Qwen3DecodeResult:
    """One decode call's whole outcome. `token_ids` is prompt tokens followed by every generated
    token, in order — empty only when the call raised before this result could be built."""

    token_ids: list[int]
    n_prompt: int
    stopped_on_eos: bool
    dispatches_per_token: int
    decode_tokens_per_sec: float
    prefill_tokens_per_sec: float


def _describe_architecture(config: dict[str, Any]) -> str:
    return ", ".join(f"{key}={config.get(key)!r}" for key in QWEN3_0_6B_BASE_ARCHITECTURE)


def _validate_architecture(checkpoint_dir: Path, config: dict[str, Any]) -> None:
    mismatches = [
        f"{key}={config.get(key)!r} (expected {expected!r})"
        for key, expected in QWEN3_0_6B_BASE_ARCHITECTURE.items()
        if config.get(key) != expected
    ]
    if mismatches:
        raise UnsupportedCheckpointArchitectureError(
            f"unsupported model architecture: {checkpoint_dir} is not Qwen3-0.6B-Base's exact "
            "shape. qwen3_i8_allsimd7_decode() runs ONLY that shape, via a kernel compiled "
            f"specifically for it. Mismatched fields: {'; '.join(mismatches)}. Expected: "
            f"{_describe_architecture(QWEN3_0_6B_BASE_ARCHITECTURE)}."
        )


def _read_safetensors_header(path: Path) -> tuple[dict[str, Any], int]:
    """Byte-level `safetensors` header parse: 8-byte little-endian length, then that many bytes of
    JSON. Returns `(header, data_start)`, where a tensor's absolute byte range is
    `data_start + data_offsets[0] .. data_start + data_offsets[1]`. Deliberately not
    `safetensors.torch`'s loader, matching `generate_manifest.py`'s own reasoning: the byte-level
    parse is real, not delegated to a second library this task would then have to trust blindly."""
    with path.open("rb") as handle:
        (header_len,) = struct.unpack("<Q", handle.read(8))
        header = json.loads(handle.read(header_len))
    return header, 8 + header_len


def prepare_checkpoint(
    checkpoint_dir: str | Path,
    prompt_token_ids: list[int],
    *,
    out_dir: str | Path | None = None,
) -> Path:
    """Validate `checkpoint_dir`'s architecture, then convert it into the `manifest.json` +
    `weights.blob` pair `qwen3_i8_allsimd7_decode_flat` reads.

    `checkpoint_dir` is a local HuggingFace snapshot directory (`config.json` + `model.safetensors`)
    — a real, caller-owned filesystem path, never a hardcoded one and never downloaded here (that
    stays a separate, explicit stage: `huggingface_hub.snapshot_download`, or any other means of
    getting the checkpoint onto disk).

    Raises `UnsupportedCheckpointArchitectureError` if the checkpoint is not Qwen3-0.6B-Base's exact
    shape, and `Qwen3DecodeError("checkpoint_not_found", ...)` if the expected files are missing.
    Returns the directory the manifest + blob were written to (`out_dir`, or a fresh temporary
    directory when omitted). Conversion STREAMS one tensor at a time -- peak host memory is
    O(one tensor / one tile), independent of model size; the output bytes are exactly the
    pre-streaming converter's.
    """
    try:
        import numpy as np  # noqa: F401
    except ImportError as exc:
        raise Qwen3DecodeError(
            "numpy_required",
            "prepare_checkpoint() needs numpy to convert BF16 checkpoint weights; install it with "
            "`pip install algenta[benchmark]` or `pip install numpy`.",
        ) from exc

    checkpoint_dir = Path(checkpoint_dir)
    config_path = checkpoint_dir / "config.json"
    safetensors_path = checkpoint_dir / "model.safetensors"
    # config.json alone decides the architecture gate. Checked BEFORE looking for
    # model.safetensors at all: a checkpoint whose shape is already wrong should be told that,
    # not "and also a file is missing" — the shape mismatch is the actionable, specific reason,
    # and it can be found from the smaller, cheaper file.
    if not config_path.is_file():
        raise Qwen3DecodeError(
            "checkpoint_not_found",
            f"{checkpoint_dir} does not look like a HuggingFace checkpoint snapshot: "
            f"{config_path.name} is missing.",
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_architecture(checkpoint_dir, config)

    if not safetensors_path.is_file():
        raise Qwen3DecodeError(
            "checkpoint_not_found",
            f"{checkpoint_dir} does not look like a HuggingFace checkpoint snapshot: "
            f"{safetensors_path.name} is missing.",
        )

    if not isinstance(prompt_token_ids, list) or not prompt_token_ids:
        raise Qwen3DecodeError(
            "invalid_arguments", "prompt_token_ids must be a non-empty list of token ids"
        )
    for token_id in prompt_token_ids:
        if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
            raise Qwen3DecodeError(
                "invalid_arguments", f"prompt_token_ids must be non-negative ints, got {token_id!r}"
            )

    resolved_out_dir = Path(out_dir) if out_dir is not None else Path(
        tempfile.mkdtemp(prefix="algenta-qwen3-checkpoint-")
    )
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    header, data_start = _read_safetensors_header(safetensors_path)
    header.pop("__metadata__", None)
    n_layers = config["num_hidden_layers"]
    expected_tensor_count = n_layers * 11 + 2
    names = sorted(header.keys())
    if len(names) != expected_tensor_count:
        raise Qwen3DecodeError(
            "checkpoint_not_found",
            f"{safetensors_path} has {len(names)} tensors, expected {expected_tensor_count} for a "
            f"{n_layers}-layer Qwen3-0.6B-Base checkpoint.",
        )

    # Streaming conversion (2026-08-20): one tensor in flight at a time, the blob written by
    # sequential append -- the pre-streaming path read the WHOLE safetensors file into one bytes
    # object and then ran the whole model through four full Float64 buffers at once (every
    # tensor's values held at once + np.concatenate + astype + tobytes), peaking ~30 GB of host
    # RAM on this very checkpoint. The widen/transpose/write primitives are `algenta.inference`'s
    # own streaming helpers -- the exact same bit operations this module always used, tiled.
    from algenta.inference import (
        _bf16_bytes_to_f64_tiles,
        _bf16_bytes_to_f64_transposed,
        _write_f64_streamed,
    )

    blob_path = resolved_out_dir / "weights.blob"
    manifest_tensors: dict[str, Any] = {}
    cursor = 0
    try:
        with blob_path.open("wb") as blob_out:
            for name in names:
                info = header[name]
                if info.get("dtype") != "BF16":
                    raise Qwen3DecodeError(
                        "checkpoint_not_found",
                        f"{name} in {safetensors_path} is {info.get('dtype')}, expected BF16 — this "
                        "converter only handles Qwen3-0.6B-Base's own published (BF16) checkpoint.",
                    )
                shape = list(info["shape"])
                start, end = info["data_offsets"]
                n_elements = 1
                for dim in shape:
                    n_elements *= dim
                with safetensors_path.open("rb") as handle:
                    handle.seek(data_start + start)
                    raw = handle.read(end - start)
                transposed = False
                if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
                    chunks = (_bf16_bytes_to_f64_transposed(raw, shape),)
                    shape = [shape[1], shape[0]]
                    transposed = True
                else:
                    chunks = _bf16_bytes_to_f64_tiles(raw)
                written = 0
                for chunk in chunks:
                    _write_f64_streamed(blob_out, chunk)
                    written += chunk.size
                if written != n_elements:
                    raise Qwen3DecodeError(
                        "checkpoint_not_found",
                        f"tensor {name!r} converted to {written} Float64 values but its shape "
                        f"{shape} declares {n_elements} — the converter and the checkpoint "
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
        # A mid-stream failure must not leave a PARTIAL blob behind: the pre-streaming path
        # converted every tensor before writing anything, so a failure left the directory empty.
        blob_path.unlink(missing_ok=True)
        raise

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


def qwen3_i8_allsimd7_decode(
    runtime: Any,
    *,
    checkpoint_dir: str | Path,
    prompt_token_ids: list[int],
    max_new_tokens: int = 16,
    converted_checkpoint_dir: str | Path | None = None,
) -> Qwen3DecodeResult:
    """Greedy-decode `prompt_token_ids` with Qwen3-0.6B-Base's int8 Metal GPU kernel path.

    `runtime` is a `MojoRuntime(mode="local")` (or anything exposing the same `.execute(module,
    function, args)` — this is compute, not a call to somebody else's compute, matching every other
    local-runtime-backed module in this package).

    Converts `checkpoint_dir` once per call (pass `converted_checkpoint_dir` to reuse an
    already-converted checkpoint across calls and skip the conversion cost — see
    `prepare_checkpoint()`), then calls straight through the bundled worker's existing AF_UNIX frame
    protocol via `runtime.execute("metaldispatch.qwen3_decode", "qwen3_i8_allsimd7_decode_flat",
    ...)` — the same `library_execute` message every other flat-list contract function already uses;
    no bespoke wire message was added for this.

    Raises `UnsupportedCheckpointArchitectureError` for the wrong model shape, and `Qwen3DecodeError`
    for every other refusal (no Metal accelerator, this worker built without `-D ALGENTA_GPU`, or a
    `metaldispatch` shim-level failure) — the status name from `metaldispatch.contract` is always
    `error.code`, and the full message from the Mojo side is always `str(error)`.
    """
    if converted_checkpoint_dir is not None:
        resolved_dir = Path(converted_checkpoint_dir)
        if not (resolved_dir / "manifest.json").is_file() or not (
            resolved_dir / "weights.blob"
        ).is_file():
            raise Qwen3DecodeError(
                "checkpoint_not_found",
                f"{resolved_dir} has no manifest.json/weights.blob; convert it first with "
                "prepare_checkpoint(), or omit converted_checkpoint_dir to convert automatically.",
            )
    else:
        resolved_dir = prepare_checkpoint(checkpoint_dir, prompt_token_ids)

    if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or max_new_tokens < 1:
        raise Qwen3DecodeError(
            "invalid_arguments", f"max_new_tokens must be a positive int, got {max_new_tokens!r}"
        )

    envelope = runtime.execute(_MODULE_NAME, _FUNCTION_NAME, [str(resolved_dir), max_new_tokens])
    error = _envelope_error(envelope)
    if error is not None:
        raise Qwen3DecodeError("runtime_execution_failed", error)

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise Qwen3DecodeError(
            "runtime_execution_failed", "the local runtime returned a malformed decode result"
        )
    status = result.get("status")
    if status != 620:  # metaldispatch.contract.MB_OK
        code = _status_code_name(status)
        raise Qwen3DecodeError(code, str(result.get("error_message") or code))

    return Qwen3DecodeResult(
        token_ids=list(result.get("token_ids") or []),
        n_prompt=int(result.get("n_prompt") or 0),
        stopped_on_eos=bool(result.get("stopped_on_eos")),
        dispatches_per_token=int(result.get("dispatches_per_token") or 0),
        decode_tokens_per_sec=float(result.get("decode_tokens_per_sec") or 0.0),
        prefill_tokens_per_sec=float(result.get("prefill_tokens_per_sec") or 0.0),
    )


# Mirrors `metaldispatch.contract.metaldispatch_status_name` verbatim, so a raised `Qwen3DecodeError`
# names the same thing the Mojo side does without a second wire round trip just to translate a code
# this package already knows the vocabulary for.
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
