"""Streaming checkpoint conversion: host memory O(one tensor / one tile), byte-identical output.

The pre-streaming converter (the one the NVIDIA race's `prepare_smoke_checkpoint.py` ran on the
VMs) materialized EVERY tensor's Float64 values at once and then ran the whole model through three
more full copies (entries list + np.concatenate + astype + tobytes): a Qwen3-0.6B BF16 checkpoint
peaked ~30 GB of host RAM and OOMed 16 GB VMs. `prepare_model_checkpoint()` now STREAMS -- one
tensor in flight, widened in tiles, the blob written by sequential append. This file gates the two
contracts that matter, on a synthetic BF16 fixture small enough for CI (no model download, no GPU):

* BYTE-COMPAT -- the streamed `weights.blob` + `manifest.json` are byte-for-byte what the
  pre-streaming algorithm produced: checked against an in-test restatement of that exact algorithm
  (per-tensor full widen + transpose + concatenate + astype + tobytes), not "should be the same".
  The session weight loaders (Metal + CUDA) read the blob by manifest offset, so byte-identity is
  the contract -- same bytes, same oracle tokens, no engine change.
* MEMORY BOUND -- converting a model whose Float64 form is N bytes peaks below 2N of incremental
  RSS in a fresh subprocess (the pre-streaming algorithm needs ~4N: entries + concatenate +
  astype + tobytes all alive at once). The subprocess keeps this pytest process's own high-water
  mark from masking the converter's, and the bound would fail the pre-streaming implementation.
* NO PARTIAL OUTPUT ON FAILURE -- a mid-stream refusal (a later tensor with the wrong dtype)
  leaves no half-written `weights.blob` behind: the pre-streaming tail validated every tensor
  before writing anything, and the streaming tail keeps that contract by removing partial output.

The GGUF front door shares the streaming tail; its own byte-compat check builds a tiny synthetic
GGUF and compares against the same restated algorithm (the GGUF tensor reader is unchanged -- the
oracle anchors exactly what this change touched: iteration order + the streamed write).
"""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.inference import (  # noqa: E402
    _TRANSPOSE_SUFFIXES,
    InferenceError,
    _gguf_map_tensor_name,
    _gguf_read_tensor_values,
    _read_gguf_header,
    _read_safetensors_header,
    prepare_model_checkpoint,
    prepare_model_checkpoint_from_gguf,
)

numpy = pytest.importorskip("numpy", reason="the checkpoint converters need numpy")

_PROMPT_TOKEN_IDS = [785, 6722, 315, 9625, 374]

# The GEMM weights the kernels consume pre-transposed -- imported from the converter itself (the
# very contract the legacy oracle restates), never restated as a second literal.

# A small Qwen3-style shape that passes every structural gate (hidden/intermediate divisible by
# 32, GQA ratio integral, h_q*head_dim divisible by 32) -- 8 layers, one dominant tensor (the
# embedding table), qk-norm tensors present, tied embeddings. Sized so the model's Float64 form
# (~336 MB) dwarfs the fixed overheads inside the bound (interpreter + numpy import): the
# streaming converter peaks far below 2N, the pre-streaming algorithm needed ~4N, and neither
# claim is close to the boundary -- in either direction -- run to run.
_CONFIG = {
    "hidden_size": 512,
    "num_hidden_layers": 8,
    "num_attention_heads": 8,
    "num_key_value_heads": 4,
    "head_dim": 128,
    "intermediate_size": 2048,
    "vocab_size": 8192,
    "rope_theta": 1000000.0,
    "rms_norm_eps": 1e-6,
    "tie_word_embeddings": True,
    "attention_bias": False,
}


def _fixture_tensor_shapes() -> dict[str, list[int]]:
    """The fixture's HF tensor shapes: embed + final norm + 11 tensors per layer (qk-norm present,
    tied embeddings) -- exactly the set the converter's required-name rule asks this config for."""
    h_q_dim = _CONFIG["num_attention_heads"] * _CONFIG["head_dim"]  # 1024
    h_kv_dim = _CONFIG["num_key_value_heads"] * _CONFIG["head_dim"]  # 512
    hidden = _CONFIG["hidden_size"]
    d_ff = _CONFIG["intermediate_size"]
    shapes = {
        "model.embed_tokens.weight": [_CONFIG["vocab_size"], hidden],
        "model.norm.weight": [hidden],
    }
    for layer in range(_CONFIG["num_hidden_layers"]):
        prefix = f"model.layers.{layer}."
        shapes.update(
            {
                prefix + "input_layernorm.weight": [hidden],
                prefix + "post_attention_layernorm.weight": [hidden],
                prefix + "self_attn.q_norm.weight": [_CONFIG["head_dim"]],
                prefix + "self_attn.k_norm.weight": [_CONFIG["head_dim"]],
                prefix + "self_attn.q_proj.weight": [h_q_dim, hidden],
                prefix + "self_attn.k_proj.weight": [h_kv_dim, hidden],
                prefix + "self_attn.v_proj.weight": [h_kv_dim, hidden],
                prefix + "self_attn.o_proj.weight": [hidden, h_q_dim],
                prefix + "mlp.gate_proj.weight": [d_ff, hidden],
                prefix + "mlp.up_proj.weight": [d_ff, hidden],
                prefix + "mlp.down_proj.weight": [hidden, d_ff],
            }
        )
    return shapes


def _write_bf16_checkpoint(ckpt_dir: Path, seed: int = 20260820) -> None:
    """Write the fixture checkpoint: config.json + one safetensors file whose tensors are
    deterministic pseudo-random BF16 bit patterns (every u16 is a valid BF16 -- NaN/Inf patterns
    included on purpose, so the widen is exercised past the finite values)."""
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    (ckpt_dir / "config.json").write_text(json.dumps(_CONFIG), encoding="utf-8")
    rng = numpy.random.default_rng(seed)
    header: dict[str, dict] = {}
    body = bytearray()
    for name, shape in _fixture_tensor_shapes().items():
        n_elements = 1
        for dim in shape:
            n_elements *= dim
        raw = rng.integers(0, 65536, n_elements, dtype=numpy.uint16).tobytes()
        start = len(body)
        body += raw
        header[name] = {"dtype": "BF16", "shape": shape, "data_offsets": [start, len(body)]}
    header_json = json.dumps(header).encode("utf-8")
    (ckpt_dir / "model.safetensors").write_bytes(
        struct.pack("<Q", len(header_json)) + header_json + bytes(body)
    )


def _legacy_bf16_to_f64(raw: bytes):
    """The pre-streaming widen, restated: BF16 is the top 16 bits of FP32."""
    u16 = numpy.frombuffer(raw, dtype="<u2")
    return ((u16.astype(numpy.uint32) << 16).view(numpy.float32)).astype(numpy.float64)


def _legacy_reference(ckpt_dir: Path) -> tuple[bytes, dict[str, dict]]:
    """The pre-streaming algorithm restated as the byte-compat oracle: one tensor read per shard
    lookup, full-tensor widen + transpose, everything held at once, concatenated, astype-copied,
    tobytes-copied. Returns (blob bytes, manifest tensors dict)."""
    safetensors = ckpt_dir / "model.safetensors"
    header, data_start = _read_safetensors_header(safetensors)
    entries = []
    for name in sorted(_fixture_tensor_shapes()):
        info = header[name]
        shape = list(info["shape"])
        start, end = info["data_offsets"]
        with safetensors.open("rb") as handle:
            handle.seek(data_start + start)
            raw = handle.read(end - start)
        values = _legacy_bf16_to_f64(raw)
        transposed = False
        if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
            values = values.reshape(shape).T.copy().reshape(-1)
            shape = [shape[1], shape[0]]
            transposed = True
        entries.append((name, values, shape, transposed))

    blob = numpy.concatenate([values for _, values, _, _ in entries])
    manifest_tensors: dict[str, dict] = {}
    cursor = 0
    for name, values, shape, transposed in entries:
        manifest_tensors[name] = {
            "offset": cursor,
            "n_elements": int(values.size),
            "shape": shape,
            "transposed": transposed,
        }
        cursor += values.size
    return blob.astype("<f8").tobytes(), manifest_tensors


def test_streaming_output_is_byte_identical_to_the_legacy_algorithm(tmp_path: Path) -> None:
    ckpt = tmp_path / "ckpt"
    _write_bf16_checkpoint(ckpt)
    out_dir = prepare_model_checkpoint(ckpt, _PROMPT_TOKEN_IDS, out_dir=tmp_path / "out")

    expected_blob, expected_tensors = _legacy_reference(ckpt)
    assert (out_dir / "weights.blob").read_bytes() == expected_blob, (
        "the streaming converter's weights.blob differs byte-for-byte from the pre-streaming "
        "algorithm's output on the same fixture -- the session weight loaders read this blob by "
        "manifest offset, so ANY difference changes the weights the kernels run"
    )

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["tensors"] == expected_tensors
    assert manifest["input_ids"] == _PROMPT_TOKEN_IDS
    assert manifest["config"] == {
        "hidden_size": _CONFIG["hidden_size"],
        "num_hidden_layers": _CONFIG["num_hidden_layers"],
        "num_attention_heads": _CONFIG["num_attention_heads"],
        "num_key_value_heads": _CONFIG["num_key_value_heads"],
        "head_dim": _CONFIG["head_dim"],
        "intermediate_size": _CONFIG["intermediate_size"],
        "vocab_size": _CONFIG["vocab_size"],
        "rope_theta": _CONFIG["rope_theta"],
        "rms_norm_eps": _CONFIG["rms_norm_eps"],
        "n_tokens": len(_PROMPT_TOKEN_IDS),
        "has_qk_norm": 1,
        "tie_word_embeddings": 1,
        "attention_bias": 0,
    }


# The subprocess that measures the converter's own peak RSS: baseline after import, peak after the
# conversion, reported in BYTES (macOS ru_maxrss is bytes, Linux KiB). The conversion must run in
# its own process -- this pytest process's high-water mark (fixture construction, other tests)
# would otherwise mask the converter's footprint in both directions.
_RSS_SCRIPT = """
import json
import resource
import sys

sys.path.insert(0, {algenta!r})
from algenta.inference import prepare_model_checkpoint


def peak_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024


baseline = peak_bytes()
out = prepare_model_checkpoint({ckpt!r}, {prompt!r}, out_dir={out!r})
print(json.dumps({{"baseline": baseline, "peak": peak_bytes(), "out": str(out)}}))
"""


@pytest.mark.skipif(
    sys.platform not in ("darwin", "linux"),
    reason="ru_maxrss peak measurement needs macOS or Linux",
)
def test_streaming_conversion_peak_rss_is_bounded_by_the_model_size(tmp_path: Path) -> None:
    """The fixture's Float64 form is N bytes; the streaming converter must peak below 2N of
    incremental RSS. The pre-streaming algorithm held ~4N alive at once (every tensor's values +
    the concatenate + the astype + the tobytes copies), so it fails this bound by a factor of two
    at minimum -- a regression back to whole-model materialization turns this test red."""
    ckpt = tmp_path / "ckpt"
    _write_bf16_checkpoint(ckpt)
    total_f64_bytes = sum(
        8 * int(numpy.prod(shape)) for shape in _fixture_tensor_shapes().values()
    )

    script = _RSS_SCRIPT.format(
        algenta=str(_ALGENTA),
        ckpt=str(ckpt),
        prompt=_PROMPT_TOKEN_IDS,
        out=str(tmp_path / "out"),
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"the conversion subprocess failed:\n{result.stderr}"
    report = json.loads(result.stdout.strip().splitlines()[-1])

    out_dir = Path(report["out"])
    assert (out_dir / "weights.blob").stat().st_size == total_f64_bytes
    incremental = report["peak"] - report["baseline"]
    assert incremental < 2 * total_f64_bytes, (
        f"the conversion peaked {incremental} bytes above its import baseline -- more than twice "
        f"the model's Float64 size ({total_f64_bytes} bytes). The streaming converter should peak "
        "at O(one tensor / one tile), not at whole-model copies."
    )


def test_mid_stream_refusal_leaves_no_partial_blob(tmp_path: Path) -> None:
    """A wrong-dtype tensor discovered MID-stream (after earlier tensors were already written)
    must not leave a half-written weights.blob: the pre-streaming tail converted everything before
    writing anything, so a failure left the output directory empty -- the streaming tail removes
    its partial output to keep that exact contract."""
    ckpt = tmp_path / "ckpt"
    _write_bf16_checkpoint(ckpt)
    # Rewrite the LAST tensor (sorted) as F32: embed + every layer convert and stream before the
    # refusal fires, so this exercises the mid-stream cleanup, not an early refusal.
    safetensors = ckpt / "model.safetensors"
    header, data_start = _read_safetensors_header(safetensors)
    last_name = sorted(header)[-1]
    header[last_name]["dtype"] = "F32"
    header_json = json.dumps(header).encode("utf-8")
    payload = safetensors.read_bytes()[data_start:]
    safetensors.write_bytes(struct.pack("<Q", len(header_json)) + header_json + payload)

    out_dir = tmp_path / "out"
    with pytest.raises(InferenceError) as excinfo:
        prepare_model_checkpoint(ckpt, _PROMPT_TOKEN_IDS, out_dir=out_dir)
    assert excinfo.value.code == "checkpoint_not_found"
    assert "F32" in str(excinfo.value)
    assert not (out_dir / "weights.blob").exists(), (
        "a failed conversion left a partial weights.blob behind -- the engine would read "
        "truncated weights instead of getting a clean refusal"
    )


# --- GGUF front door: same streaming tail, same byte-compat gate -------------------------------


def _gguf_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _gguf_kv(key: str, value) -> bytes:
    # The three metadata types this fixture needs: string, float32 and uint32 (type tags 8, 6, 4
    # -- the same encoding the reader parses).
    if isinstance(value, str):
        return _gguf_string(key) + struct.pack("<I", 8) + _gguf_string(value)
    if isinstance(value, float):
        return _gguf_string(key) + struct.pack("<I", 6) + struct.pack("<f", value)
    return _gguf_string(key) + struct.pack("<I", 4) + struct.pack("<I", value)


def _write_test_gguf(path: Path, metadata: dict, tensors: list[tuple]) -> None:
    """GGUF v3 container: metadata kvs, tensor-info table (dims in ggml's REVERSED order), data
    aligned to 32. `tensors` is (name, ggml_type, dims, raw_bytes) -- the same convention
    test_gguf_loading.py's synthetic writer uses."""
    alignment = 32
    infos = []
    offset = 0
    for name, ggml_type, dims, raw in tensors:
        infos.append((name, ggml_type, dims, offset))
        offset += len(raw)
        offset = (offset + alignment - 1) // alignment * alignment
    body = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(metadata))
    for key, value in metadata.items():
        body += _gguf_kv(key, value)
    for name, ggml_type, dims, tensor_offset in infos:
        body += _gguf_string(name)
        body += struct.pack("<I", len(dims))
        body += struct.pack(f"<{len(dims)}Q", *dims)
        body += struct.pack("<IQ", ggml_type, tensor_offset)
    data_start = (len(body) + alignment - 1) // alignment * alignment
    body += b"\x00" * (data_start - len(body))
    cursor = 0
    for _, _, _, raw in tensors:
        body += raw
        cursor += len(raw)
        pad = ((cursor + alignment - 1) // alignment * alignment) - cursor
        body += b"\x00" * pad
        cursor += pad
    path.write_bytes(body)


def _tiny_llama_gguf(tmp_path: Path) -> Path:
    """A one-layer llama-shaped GGUF (untied, so the lm_head branch is exercised too): F16 weight
    matrices + F32 norm vectors, the common `--outtype f16` export shape."""
    d_model, d_ff, vocab, n_heads, head_dim = 64, 128, 32, 2, 32

    def f16(pattern: int, count: int) -> bytes:
        base = numpy.arange(count, dtype=numpy.float64) + pattern
        return (base % 7 - 3).astype(numpy.float16).tobytes()

    def f32(pattern: int, count: int) -> bytes:
        return ((numpy.arange(count, dtype=numpy.float64) + pattern) % 5 - 2).astype(
            numpy.float32
        ).tobytes()

    metadata = {
        "general.architecture": "llama",
        "llama.embedding_length": d_model,
        "llama.block_count": 1,
        "llama.feed_forward_length": d_ff,
        "llama.attention.head_count": n_heads,
        "llama.attention.head_count_kv": 1,
        "llama.attention.layer_norm_rms_epsilon": 1e-5,
        "llama.rope.freq_base": 10000.0,
    }
    tensors = [
        # (ggml name, F16=1 / F32=0, dims in ggml's reversed [in, out] order, raw bytes)
        ("token_embd.weight", 1, [d_model, vocab], f16(1, vocab * d_model)),
        ("output.weight", 1, [d_model, vocab], f16(2, vocab * d_model)),
        ("output_norm.weight", 0, [d_model], f32(3, d_model)),
        ("blk.0.attn_norm.weight", 0, [d_model], f32(4, d_model)),
        ("blk.0.ffn_norm.weight", 0, [d_model], f32(5, d_model)),
        ("blk.0.attn_q.weight", 1, [d_model, n_heads * head_dim], f16(6, n_heads * head_dim * d_model)),
        ("blk.0.attn_k.weight", 1, [d_model, head_dim], f16(7, head_dim * d_model)),
        ("blk.0.attn_v.weight", 1, [d_model, head_dim], f16(8, head_dim * d_model)),
        ("blk.0.attn_output.weight", 1, [n_heads * head_dim, d_model], f16(9, n_heads * head_dim * d_model)),
        ("blk.0.ffn_gate.weight", 1, [d_model, d_ff], f16(10, d_ff * d_model)),
        ("blk.0.ffn_up.weight", 1, [d_model, d_ff], f16(11, d_ff * d_model)),
        ("blk.0.ffn_down.weight", 1, [d_ff, d_model], f16(12, d_ff * d_model)),
    ]
    gguf = tmp_path / "tiny.gguf"
    _write_test_gguf(gguf, metadata, tensors)
    return gguf


def test_gguf_front_door_streams_byte_identical_output(tmp_path: Path) -> None:
    gguf = _tiny_llama_gguf(tmp_path)
    out_dir = prepare_model_checkpoint_from_gguf(gguf, _PROMPT_TOKEN_IDS, out_dir=tmp_path / "out")

    # The oracle: the pre-streaming algorithm restated over the GGUF reader's per-tensor values,
    # iterating in the SAME sorted-HF-name order the converter uses (the reader itself is
    # unchanged by the streaming work -- this anchors exactly what changed: the iteration order
    # and the streamed write).
    _, tensor_infos, data_start = _read_gguf_header(gguf)
    hf_infos: dict[str, dict] = {}
    for info in tensor_infos:
        hf_name = _gguf_map_tensor_name(info["name"])
        if hf_name is not None:
            hf_infos[hf_name] = info
    chunks = []
    for hf_name in sorted(hf_infos):
        values, shape = _gguf_read_tensor_values(gguf, hf_infos[hf_name], data_start)
        if len(shape) == 2 and hf_name.endswith(_TRANSPOSE_SUFFIXES):
            values = values.reshape(shape).T.copy().reshape(-1)
        chunks.append(values)
    expected_blob = numpy.concatenate(chunks).astype("<f8").tobytes()

    assert (out_dir / "weights.blob").read_bytes() == expected_blob
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["tie_word_embeddings"] == 0  # output.weight present -> untied
    assert "lm_head.weight" in manifest["tensors"]
