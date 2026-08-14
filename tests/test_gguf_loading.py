"""GGUF loading (beat-llama.cpp campaign, model-coverage front): llama.cpp users have `.gguf`
model files; `prepare_model_checkpoint_from_gguf()` is the door that runs them on the same engine.
This file checks:

* the GGUF container reader and name mapping, unconditionally (a synthetic GGUF is built in
  tmp_path -- struct-written, the same dependency-free style as the reader itself): header/kv
  parsing, alignment/padding, exact F16/F32 widening, exact Q8_0 dequantization, and the refusal
  paths (bad magic, unsupported version, unsupported tensor dtype, unsupported architecture);
* the real-file conversion, opt-in (needs the campaign's GGUF files on disk, never fetched by a
  test): the F16 Qwen3-0.6B GGUF converts to the SAME manifest+blob contract as the safetensors
  converter, and the TinyLlama F16/Q8_0 GGUFs convert to the llama-family contract (untied
  lm_head, no QK-norm, eos=2);
* the end-to-end GPU proof, opt-in (needs the matching GPU worker + converted safetensors oracle):
  the Qwen3 GGUF decodes BYTE-IDENTICAL to the safetensors path (oracle first token 374 and the
  exact known continuation), and the TinyLlama GGUF decodes token-identical to an independent
  fp64 CPU reference computed from the SAME GGUF weights (the safetensors directory is a different
  quantization of the base model, so same-source tokens are the honest gate there).

The opt-in convention mirrors `tests/test_inference_gpu_e2e.py`'s: skipped -- never failed -- when
the prerequisites are absent.
"""

from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.inference import (  # noqa: E402
    InferenceError,
    _gguf_architecture_config,
    _gguf_map_tensor_name,
    _gguf_read_tensor_values,
    _read_gguf_header,
    decode,
    prepare_model_checkpoint_from_gguf,
)

numpy = pytest.importorskip("numpy", reason="GGUF conversion needs numpy")

_QWEN3_GGUF = Path(os.environ.get("ALGENTA_QWEN3_GGUF", "/private/tmp/qwen3-0.6b-base-f16.gguf"))
_TINYLLAMA_GGUF = Path(os.environ.get("ALGENTA_TINYLLAMA_GGUF", "/private/tmp/tinyllama-f16.gguf"))
_TINYLLAMA_Q8_GGUF = Path(
    os.environ.get("ALGENTA_TINYLLAMA_Q8_GGUF", "/private/tmp/tinyllama-q8_0.gguf")
)
_QWEN3_CHECKPOINT = Path(
    os.environ.get("ALGENTA_QWEN3_TEST_CHECKPOINT", "/private/tmp/qwen3-0.6b-base")
)
_QWEN3_CONVERTED = Path(os.environ.get("ALGENTA_QWEN3_CONVERTED_06B", "/tmp/qwen3smoke"))
_TINYLLAMA_CHECKPOINT = Path(os.environ.get("ALGENTA_TINYLLAMA_CHECKPOINT", "/private/tmp/tinyllama"))
_PROMPT_TOKEN_IDS = [785, 6722, 315, 9625, 374]

_ORACLE_FIRST_TOKEN = 374
_ORACLE_CONTINUATION = [374, 12095, 13, 576, 6722, 315, 9625, 374]
_TINYLLAMA_PROMPT = [1576, 263, 3290, 338, 262, 3303]  # the campaign's France prompt


# --- synthetic GGUF writer (dependency-free, mirrors the reader's struct style) ----------------


def _gguf_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _gguf_kv(key: str, value) -> bytes:
    if isinstance(value, str):
        return _gguf_string(key) + struct.pack("<I", 8) + _gguf_string(value)
    if isinstance(value, float):
        return _gguf_string(key) + struct.pack("<I", 6) + struct.pack("<f", value)
    if isinstance(value, int):
        return _gguf_string(key) + struct.pack("<I", 4) + struct.pack("<I", value)
    raise AssertionError(f"test writer does not handle {type(value)}")


def _write_test_gguf(path: Path, metadata: dict, tensors: list[tuple], alignment: int = 32) -> None:
    """`tensors` is (name, ggml_type, dims, raw_bytes). Offsets are assigned the way llama.cpp
    does it: each tensor starts at the previous end rounded up to the alignment."""
    infos = []
    offset = 0
    data_blobs = []
    for name, ggml_type, dims, raw in tensors:
        infos.append((name, ggml_type, dims, offset))
        data_blobs.append(raw)
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
    for raw in data_blobs:
        body += raw
        cursor += len(raw)
        pad = ((cursor + alignment - 1) // alignment * alignment) - cursor
        body += b"\x00" * pad
        cursor += pad
    path.write_bytes(body)


def _llama_metadata(**overrides) -> dict:
    meta = {
        "general.architecture": "llama",
        "llama.embedding_length": 64,
        "llama.block_count": 1,
        "llama.feed_forward_length": 128,
        "llama.attention.head_count": 2,
        "llama.attention.head_count_kv": 1,
        "llama.attention.layer_norm_rms_epsilon": 1e-5,
        "llama.rope.freq_base": 10000.0,
    }
    meta.update(overrides)
    return meta


# --- unconditional parser checks ---------------------------------------------------------------


def test_gguf_name_mapping_covers_both_architectures() -> None:
    assert _gguf_map_tensor_name("token_embd.weight") == "model.embed_tokens.weight"
    assert _gguf_map_tensor_name("output_norm.weight") == "model.norm.weight"
    assert _gguf_map_tensor_name("output.weight") == "lm_head.weight"
    assert _gguf_map_tensor_name("blk.0.attn_norm.weight") == "model.layers.0.input_layernorm.weight"
    assert (
        _gguf_map_tensor_name("blk.3.ffn_norm.weight")
        == "model.layers.3.post_attention_layernorm.weight"
    )
    assert (
        _gguf_map_tensor_name("blk.12.attn_q.weight") == "model.layers.12.self_attn.q_proj.weight"
    )
    assert (
        _gguf_map_tensor_name("blk.12.attn_output.weight")
        == "model.layers.12.self_attn.o_proj.weight"
    )
    assert _gguf_map_tensor_name("blk.5.ffn_gate.weight") == "model.layers.5.mlp.gate_proj.weight"
    assert _gguf_map_tensor_name("blk.5.ffn_up.weight") == "model.layers.5.mlp.up_proj.weight"
    assert _gguf_map_tensor_name("blk.5.ffn_down.weight") == "model.layers.5.mlp.down_proj.weight"
    # qwen3's per-head QK-norm tensors
    assert (
        _gguf_map_tensor_name("blk.0.attn_q_norm.weight")
        == "model.layers.0.self_attn.q_norm.weight"
    )
    assert (
        _gguf_map_tensor_name("blk.0.attn_k_norm.weight")
        == "model.layers.0.self_attn.k_norm.weight"
    )
    # tensors the engine does not consume map to None
    assert _gguf_map_tensor_name("blk.0.attn_rot.weight") is None
    assert _gguf_map_tensor_name("rope_freqs.weight") is None
    assert _gguf_map_tensor_name("nonsense") is None


def test_gguf_header_metadata_and_alignment_roundtrip(tmp_path: Path) -> None:
    # F16 weight [2,4] ggml dims (HF shape [4,2] reversed), F32 norm [4]. Values chosen to be
    # exactly representable in F16 so the widening is exact.
    f16_vals = [1.5, -2.25, 0.125, -0.5, 3.0, 6.5, -1.0, 0.25]
    f16_raw = b"".join(struct.pack("<e", v) for v in f16_vals)
    f32_vals = [0.5, 1.25, -2.0, 4.5]
    f32_raw = b"".join(struct.pack("<f", v) for v in f32_vals)
    gguf = tmp_path / "mini.gguf"
    _write_test_gguf(
        gguf,
        _llama_metadata(),
        [
            ("blk.0.attn_q.weight", 1, [2, 4], f16_raw),  # odd-ish size -> exercises padding
            ("blk.0.attn_norm.weight", 0, [4], f32_raw),
        ],
    )
    metadata, infos, data_start = _read_gguf_header(gguf)
    assert metadata["general.architecture"] == "llama"
    assert metadata["llama.embedding_length"] == 64
    assert metadata["llama.rope.freq_base"] == pytest.approx(10000.0)
    assert data_start % 32 == 0
    assert [info["name"] for info in infos] == ["blk.0.attn_q.weight", "blk.0.attn_norm.weight"]
    assert infos[0]["dims"] == [2, 4] and infos[0]["ggml_type"] == 1
    assert infos[1]["offset"] == 32  # the F16 blob (16 bytes) padded up to the 32-byte alignment

    values, shape = _gguf_read_tensor_values(gguf, infos[0], data_start)
    assert shape == [4, 2]  # ggml dims reversed to HuggingFace row-major
    assert list(values) == f16_vals  # F16 -> Float64 widens EXACTLY
    values, shape = _gguf_read_tensor_values(gguf, infos[1], data_start)
    assert shape == [4] and list(values) == f32_vals


def test_gguf_q8_0_dequantization_exact(tmp_path: Path) -> None:
    # Q8_0: per 32-element block an f16 scale followed by 32 int8; dequant = scale * int8, exact
    # once widened to Float64.
    scale = 2.0
    qs = list(range(-16, 16))  # 32 int8
    raw = struct.pack("<e", scale) + struct.pack("<32b", *qs)
    gguf = tmp_path / "q8.gguf"
    _write_test_gguf(gguf, _llama_metadata(), [("blk.0.ffn_gate.weight", 8, [32, 1], raw)])
    _, infos, data_start = _read_gguf_header(gguf)
    values, shape = _gguf_read_tensor_values(gguf, infos[0], data_start)
    assert shape == [1, 32]
    assert list(values) == [scale * q for q in qs]


def test_gguf_bad_magic_refused(tmp_path: Path) -> None:
    gguf = tmp_path / "not.gguf"
    gguf.write_bytes(b"XXXX" + b"\x00" * 64)
    with pytest.raises(InferenceError) as excinfo:
        _read_gguf_header(gguf)
    assert excinfo.value.code == "unsupported_gguf"


def test_gguf_unsupported_version_refused(tmp_path: Path) -> None:
    gguf = tmp_path / "future.gguf"
    gguf.write_bytes(b"GGUF" + struct.pack("<IQQ", 4, 0, 0))
    with pytest.raises(InferenceError) as excinfo:
        _read_gguf_header(gguf)
    assert excinfo.value.code == "unsupported_gguf"
    assert "version 4" in str(excinfo.value)


def test_gguf_unsupported_tensor_dtype_refused(tmp_path: Path) -> None:
    # Q4_0 (ggml type 2) is not one of the dtypes this increment reads.
    gguf = tmp_path / "q4.gguf"
    _write_test_gguf(gguf, _llama_metadata(), [("blk.0.attn_q.weight", 2, [32, 1], b"\x00" * 18)])
    _, infos, data_start = _read_gguf_header(gguf)
    with pytest.raises(InferenceError) as excinfo:
        _gguf_read_tensor_values(gguf, infos[0], data_start)
    assert excinfo.value.code == "unsupported_gguf"
    assert "ggml type 2" in str(excinfo.value)


def test_gguf_unsupported_architecture_refused(tmp_path: Path) -> None:
    gguf = tmp_path / "gpt2.gguf"
    _write_test_gguf(
        gguf,
        _llama_metadata(**{"general.architecture": "gpt2"}),
        [("token_embd.weight", 1, [64, 8], b"\x00" * (64 * 8 * 2))],
    )
    with pytest.raises(InferenceError) as excinfo:
        prepare_model_checkpoint_from_gguf(gguf, _PROMPT_TOKEN_IDS, out_dir=tmp_path / "out")
    assert excinfo.value.code == "unsupported_gguf"
    assert "gpt2" in str(excinfo.value)


def test_gguf_metadata_derives_llama_config(tmp_path: Path) -> None:
    # head_dim absent from the metadata (llama convention) -> derived hidden//heads; kv heads
    # absent -> defaults to the q head count; eos carried from the tokenizer metadata.
    gguf = tmp_path / "cfg.gguf"
    meta = _llama_metadata()
    del meta["llama.attention.head_count_kv"]
    meta["tokenizer.ggml.eos_token_id"] = 2
    _write_test_gguf(
        gguf, meta, [("token_embd.weight", 1, [64, 512], b"\x00" * (64 * 512 * 2))]
    )
    metadata, infos, _ = _read_gguf_header(gguf)
    config = _gguf_architecture_config(gguf, metadata, infos)
    assert config["hidden_size"] == 64
    assert config["head_dim"] == 32  # 64 // 2, derived
    assert config["num_key_value_heads"] == 2  # defaulted to the q head count
    assert config["vocab_size"] == 512  # from token_embd's dims, not metadata
    assert config["tie_word_embeddings"] is True  # no output.weight tensor present
    assert config["eos_token_id"] == 2


def _full_synthetic_llama_tensors() -> list[tuple]:
    """A COMPLETE one-layer tied llama tensor set (all-zero weights) so a conversion runs to the
    manifest: hidden=64, heads=2 (head_dim=32 -> 16 rope pairs), kv heads=1, ffn=128, vocab=16.
    GGUF dims are the HF shape REVERSED (ggml's contiguous dim first): q/o are HF [64, 64], the
    single-kv-head k/v are HF [32, 64] (the engine's upload checks these lengths)."""
    f16_zeros_64_64 = b"\x00" * (64 * 64 * 2)
    f16_zeros_32_64 = b"\x00" * (32 * 64 * 2)
    return [
        ("token_embd.weight", 1, [64, 16], b"\x00" * (64 * 16 * 2)),
        ("output_norm.weight", 0, [64], b"\x00" * (64 * 4)),
        ("blk.0.attn_norm.weight", 0, [64], b"\x00" * (64 * 4)),
        ("blk.0.ffn_norm.weight", 0, [64], b"\x00" * (64 * 4)),
        ("blk.0.attn_q.weight", 1, [64, 64], f16_zeros_64_64),
        ("blk.0.attn_k.weight", 1, [64, 32], f16_zeros_32_64),
        ("blk.0.attn_v.weight", 1, [64, 32], f16_zeros_32_64),
        ("blk.0.attn_output.weight", 1, [64, 64], f16_zeros_64_64),
        ("blk.0.ffn_gate.weight", 1, [64, 128], b"\x00" * (64 * 128 * 2)),
        ("blk.0.ffn_up.weight", 1, [64, 128], b"\x00" * (64 * 128 * 2)),
        ("blk.0.ffn_down.weight", 1, [128, 64], b"\x00" * (64 * 128 * 2)),
    ]


def test_gguf_rope_freqs_tensor_carried_into_manifest(tmp_path: Path) -> None:
    # llama.cpp's conversion for a llama3-scaled checkpoint bakes the adjusted frequencies into
    # rope_freqs.weight (one F32 DIVISOR per head-dim pair) and writes no scaling metadata -- the
    # converter must carry those factors into the manifest verbatim (head_dim=32 -> 16 pairs).
    factors = [1.0, 2.5, 8.0, 0.5] + [1.0 + 0.25 * i for i in range(12)]
    rope_raw = b"".join(struct.pack("<f", v) for v in factors)
    gguf = tmp_path / "rope.gguf"
    _write_test_gguf(
        gguf,
        _llama_metadata(),
        _full_synthetic_llama_tensors() + [("rope_freqs.weight", 0, [16], rope_raw)],
    )
    out = prepare_model_checkpoint_from_gguf(gguf, _PROMPT_TOKEN_IDS, out_dir=tmp_path / "out")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["rope_freq_factors"] == pytest.approx(factors)
    # the parametric keys stay absent -- the explicit factors take precedence
    assert "rope_scaling_type" not in manifest["config"]
    # rope_freqs.weight never lands in the engine's weight tensors
    assert "rope_freqs.weight" not in manifest["tensors"]


def test_gguf_rope_freqs_wrong_pair_count_refused(tmp_path: Path) -> None:
    rope_raw = b"".join(struct.pack("<f", v) for v in [1.0, 2.0, 3.0])  # 3 factors, 16 needed
    gguf = tmp_path / "ropebad.gguf"
    _write_test_gguf(
        gguf,
        _llama_metadata(),
        _full_synthetic_llama_tensors() + [("rope_freqs.weight", 0, [3], rope_raw)],
    )
    with pytest.raises(InferenceError) as excinfo:
        prepare_model_checkpoint_from_gguf(gguf, _PROMPT_TOKEN_IDS, out_dir=tmp_path / "out")
    assert excinfo.value.code == "unsupported_gguf"
    assert "exactly 16" in str(excinfo.value)


def test_gguf_rope_scaling_type_without_freqs_tensor_refused(tmp_path: Path) -> None:
    # A non-none rope.scaling.type with NO rope_freqs.weight tensor would otherwise run
    # silently unscaled -- refused instead.
    gguf = tmp_path / "yarn.gguf"
    _write_test_gguf(
        gguf,
        _llama_metadata(**{"llama.rope.scaling.type": "yarn"}),
        _full_synthetic_llama_tensors(),
    )
    with pytest.raises(InferenceError) as excinfo:
        prepare_model_checkpoint_from_gguf(gguf, _PROMPT_TOKEN_IDS, out_dir=tmp_path / "out")
    assert excinfo.value.code == "unsupported_gguf"
    assert "yarn" in str(excinfo.value)


def test_gguf_missing_file_refused() -> None:
    with pytest.raises(InferenceError) as excinfo:
        prepare_model_checkpoint_from_gguf("/tmp/definitely-not-a-model.gguf", _PROMPT_TOKEN_IDS)
    assert excinfo.value.code == "checkpoint_not_found"


def test_gguf_text_prompt_refused_without_any_runtime(tmp_path: Path) -> None:
    # An existing file as the checkpoint is the GGUF door, and a GGUF carries no tokenizer.json --
    # text prompts are refused BEFORE any file parsing or wire call.
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"GGUF")
    with pytest.raises(InferenceError) as excinfo:
        decode(object(), checkpoint_dir=gguf, prompt_text="The capital of France is")
    assert excinfo.value.code == "invalid_arguments"
    assert "prompt_token_ids" in str(excinfo.value)


# --- real-file conversion checks (opt-in: the GGUF files are a manual download) -----------------


@pytest.mark.skipif(
    not _QWEN3_GGUF.is_file(),
    reason=f"no Qwen3 F16 GGUF at {_QWEN3_GGUF} (set ALGENTA_QWEN3_GGUF); manual download",
)
def test_qwen3_gguf_converts_to_the_manifest_contract(tmp_path: Path) -> None:
    out = prepare_model_checkpoint_from_gguf(_QWEN3_GGUF, _PROMPT_TOKEN_IDS, out_dir=tmp_path)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    config = manifest["config"]
    assert config["hidden_size"] == 1024
    assert config["num_hidden_layers"] == 28
    assert config["num_attention_heads"] == 16
    assert config["num_key_value_heads"] == 8
    assert config["head_dim"] == 128
    assert config["intermediate_size"] == 3072
    assert config["vocab_size"] == 151936
    assert config["rope_theta"] == 1000000.0
    assert config["has_qk_norm"] == 1
    assert config["tie_word_embeddings"] == 1
    assert config["eos_token_id"] == 151643
    assert len(manifest["tensors"]) == 28 * 11 + 2  # q/k/v norms included (Qwen3)
    # The GEMM weights land pre-transposed, exactly as the safetensors converter writes them.
    q = manifest["tensors"]["model.layers.0.self_attn.q_proj.weight"]
    assert q["shape"] == [1024, 2048] and q["transposed"] is True
    embed = manifest["tensors"]["model.embed_tokens.weight"]
    assert embed["shape"] == [151936, 1024] and embed["transposed"] is False
    blob = out / "weights.blob"
    assert blob.is_file()
    total = sum(t["n_elements"] for t in manifest["tensors"].values())
    assert blob.stat().st_size == total * 8  # Float64


@pytest.mark.skipif(
    not _TINYLLAMA_GGUF.is_file(),
    reason=f"no TinyLlama F16 GGUF at {_TINYLLAMA_GGUF} (set ALGENTA_TINYLLAMA_GGUF)",
)
def test_tinyllama_gguf_converts_to_the_llama_contract(tmp_path: Path) -> None:
    out = prepare_model_checkpoint_from_gguf(_TINYLLAMA_GGUF, _TINYLLAMA_PROMPT, out_dir=tmp_path)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    config = manifest["config"]
    assert config["hidden_size"] == 2048
    assert config["num_hidden_layers"] == 22
    assert config["head_dim"] == 64  # derived: 2048 // 32 (llama carries no explicit head_dim)
    assert config["num_key_value_heads"] == 4
    assert config["intermediate_size"] == 5632
    assert config["rope_theta"] == 10000.0
    assert config["has_qk_norm"] == 0  # llama family: no q_norm/k_norm tensors
    assert config["tie_word_embeddings"] == 0  # output.weight present -> untied
    assert config["eos_token_id"] == 2
    assert "lm_head.weight" in manifest["tensors"]
    assert len(manifest["tensors"]) == 22 * 9 + 3  # 9/layer + embed + norm + lm_head


@pytest.mark.skipif(
    not _TINYLLAMA_Q8_GGUF.is_file(),
    reason=f"no TinyLlama Q8_0 GGUF at {_TINYLLAMA_Q8_GGUF} (set ALGENTA_TINYLLAMA_Q8_GGUF)",
)
def test_tinyllama_q8_0_gguf_converts(tmp_path: Path) -> None:
    # The quantized export path: Q8_0 tensors dequantize into the same manifest contract.
    out = prepare_model_checkpoint_from_gguf(_TINYLLAMA_Q8_GGUF, _TINYLLAMA_PROMPT, out_dir=tmp_path)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["hidden_size"] == 2048
    assert len(manifest["tensors"]) == 22 * 9 + 3
    assert (out / "weights.blob").stat().st_size > 0


# --- GPU end-to-end (opt-in: worker binary + checkpoints + converted safetensors oracle) -------


def _worker_binary(env_name: str, default: Path) -> Path | None:
    override = os.environ.get(env_name)
    path = Path(override) if override else default
    return path if path.is_file() and os.access(path, os.X_OK) else None


def _gpu_worker() -> Path | None:
    return _worker_binary(
        "ALGENTA_GPU_WORKER", ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker"
    )


def _gpu_worker_stage6144() -> Path | None:
    # TinyLlama's d_ff=5632 needs a STAGE_6144-tier build, and llama-family support (untied
    # lm_head + QK-norm skip) must be IN the binary -- the llama-dedicated workers are that tier
    # with that support; the original plain stage6144 build predates llama support, so it is only
    # a last-resort fallback.
    override = os.environ.get("ALGENTA_GPU_WORKER_STAGE6144")
    if override:
        path = Path(override)
        return path if path.is_file() and os.access(path, os.X_OK) else None
    for default in (
        ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker-llama",
        ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker-stage6144",
    ):
        if default.is_file() and os.access(default, os.X_OK):
            return default
    return None


def _runtime(worker: Path):
    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(worker)
    from algenta import MojoRuntime

    return MojoRuntime(mode="local", timeout=600.0)


def _race_prompt_ids(converted_dir: Path) -> list[int]:
    manifest = json.loads((converted_dir / "manifest.json").read_text(encoding="utf-8"))
    return list(manifest["input_ids"])


@pytest.mark.skipif(
    _gpu_worker() is None
    or not _QWEN3_GGUF.is_file()
    or not (_QWEN3_CONVERTED / "manifest.json").is_file()
    or not (_QWEN3_CHECKPOINT / "config.json").is_file(),
    reason=(
        "needs the 3072-tier GPU worker, the Qwen3 F16 GGUF, the Qwen3-0.6B snapshot, and the "
        "converted race-prompt safetensors checkpoint"
    ),
)
def test_qwen3_gguf_decode_byte_identical_to_safetensors(tmp_path: Path) -> None:
    """The decisive gate: the GGUF front door produces the SAME greedy token ids as the
    safetensors path on the same race prompt -- oracle first token 374 and the exact known
    continuation included."""
    worker = _gpu_worker()
    prompt_ids = _race_prompt_ids(_QWEN3_CONVERTED)
    runtime = _runtime(worker)

    converted = prepare_model_checkpoint_from_gguf(_QWEN3_GGUF, prompt_ids, out_dir=tmp_path)
    gguf_result = decode(
        runtime,
        checkpoint_dir=_QWEN3_CHECKPOINT,
        prompt_token_ids=prompt_ids,
        max_new_tokens=8,
        converted_checkpoint_dir=converted,
    )
    safetensors_result = decode(
        runtime,
        checkpoint_dir=_QWEN3_CHECKPOINT,
        prompt_token_ids=prompt_ids,
        max_new_tokens=8,
        converted_checkpoint_dir=_QWEN3_CONVERTED,
    )
    assert gguf_result.token_ids[len(prompt_ids) :] == _ORACLE_CONTINUATION
    assert gguf_result.token_ids[0] == prompt_ids[0]
    assert gguf_result.token_ids == safetensors_result.token_ids  # byte-identical, prompt included


@pytest.mark.skipif(
    _gpu_worker() is None
    or not _QWEN3_GGUF.is_file()
    or not (_QWEN3_CONVERTED / "manifest.json").is_file(),
    reason="needs the 3072-tier GPU worker, the Qwen3 F16 GGUF, and the race-prompt manifest",
)
def test_qwen3_gguf_decode_front_door(tmp_path: Path) -> None:
    """decode() accepts the .gguf FILE itself as checkpoint_dir (converts once, caches beside the
    file) and still lands on the oracle continuation."""
    worker = _gpu_worker()
    prompt_ids = _race_prompt_ids(_QWEN3_CONVERTED)
    # Hermetic cache dir: decode()'s GGUF cache sits at `<file>.algenta-cache`; point the env
    # override at a tmp copy so the campaign's real file's cache is never churned by a test.
    import shutil

    gguf_copy = tmp_path / "qwen3.gguf"
    shutil.copyfile(_QWEN3_GGUF, gguf_copy)
    result = decode(
        _runtime(worker),
        checkpoint_dir=gguf_copy,
        prompt_token_ids=prompt_ids,
        max_new_tokens=8,
    )
    assert result.token_ids[len(prompt_ids) :] == _ORACLE_CONTINUATION
    cache = Path(str(gguf_copy) + ".algenta-cache")
    assert (cache / "manifest.json").is_file() and (cache / "weights.blob").is_file()


def _tinyllama_cpu_reference_tokens(gguf_path: Path, prompt: list[int], n_new: int) -> list[int]:
    """Independent fp64 CPU greedy reference (llama forward: RMSNorm, GQA attention, split-half
    RoPE, SiLU-gated FFN) computed from the GGUF's OWN weights -- the honest gate for a GGUF
    whose source weights differ from any safetensors snapshot on disk."""
    import numpy as np

    metadata, infos, data_start = _read_gguf_header(gguf_path)
    weights: dict[str, Any] = {}
    for info in infos:
        values, shape = _gguf_read_tensor_values(gguf_path, info, data_start)
        weights[info["name"]] = values.reshape(shape)
    arch = metadata["general.architecture"]
    eps = float(metadata[f"{arch}.attention.layer_norm_rms_epsilon"])
    n_layers = metadata[f"{arch}.block_count"]
    h_q = metadata[f"{arch}.attention.head_count"]
    h_kv = metadata[f"{arch}.attention.head_count_kv"]
    hidden = metadata[f"{arch}.embedding_length"]
    d_head = hidden // h_q
    theta = float(metadata[f"{arch}.rope.freq_base"])
    embed = weights["token_embd.weight"]
    lm_head = weights.get("output.weight", embed)
    out_norm = weights["output_norm.weight"]

    def rms_norm(x, gain):
        return x / np.sqrt(np.mean(x * x) + eps) * gain

    def rope(vec: Any, pos: int) -> Any:
        heads = vec.reshape(-1, d_head)
        half = d_head // 2
        idx = np.arange(half)
        angles = pos * (1.0 / (theta ** (2 * idx / d_head)))
        cos, sin = np.cos(angles), np.sin(angles)
        out = np.empty_like(heads)
        out[:, :half] = heads[:, :half] * cos - heads[:, half:] * sin
        out[:, half:] = heads[:, half:] * cos + heads[:, :half] * sin
        return out.reshape(-1)

    cache: dict[int, tuple[list, list]] = {}
    generated: list[int] = []
    ratio = h_q // h_kv
    scale = 1.0 / np.sqrt(d_head)
    for step in range(len(prompt) + n_new):
        token = prompt[step] if step < len(prompt) else generated[-1]
        x = embed[token]
        for layer in range(n_layers):
            prefix = f"blk.{layer}."
            xn = rms_norm(x, weights[prefix + "attn_norm.weight"])
            q = rope(xn @ weights[prefix + "attn_q.weight"].T, step)
            k = rope(xn @ weights[prefix + "attn_k.weight"].T, step)
            v = xn @ weights[prefix + "attn_v.weight"].T
            keys, vals = cache.setdefault(layer, ([], []))
            keys.append(k)
            vals.append(v)
            keys_mat = np.stack(keys).reshape(-1, h_kv, d_head)
            vals_mat = np.stack(vals).reshape(-1, h_kv, d_head)
            q2 = q.reshape(h_q, d_head)
            attn_out = np.zeros(h_q * d_head)
            for head in range(h_q):
                kv_head = head // ratio
                scores = keys_mat[:, kv_head, :] @ q2[head] * scale
                exp = np.exp(scores - scores.max())
                attn_out[head * d_head : (head + 1) * d_head] = (
                    (exp / exp.sum()) @ vals_mat[:, kv_head, :]
                )
            x = x + attn_out @ weights[prefix + "attn_output.weight"].T
            xn = rms_norm(x, weights[prefix + "ffn_norm.weight"])
            gate = xn @ weights[prefix + "ffn_gate.weight"].T
            up = xn @ weights[prefix + "ffn_up.weight"].T
            x = x + ((1.0 / (1.0 + np.exp(-gate))) * gate * up) @ weights[prefix + "ffn_down.weight"].T
        x = rms_norm(x, out_norm)
        generated.append(int(np.argmax(x @ lm_head.T)))
    # The first generated token is the final prefill step's argmax.
    return generated[len(prompt) - 1 : len(prompt) - 1 + n_new]


@pytest.mark.skipif(
    _gpu_worker_stage6144() is None or not _TINYLLAMA_GGUF.is_file(),
    reason=(
        "needs a STAGE_6144-tier GPU worker (mojo_build/gpu-worker/algenta-gpu-worker-stage6144 "
        "or -llama) and the TinyLlama F16 GGUF"
    ),
)
def test_tinyllama_gguf_decode_matches_cpu_reference(tmp_path: Path) -> None:
    """The llama-architecture GGUF proof: the engine's greedy tokens from the GGUF weights match
    an independent fp64 CPU reference computed from the SAME GGUF weights (the campaign's
    /private/tmp/tinyllama safetensors directory is a BF16 re-save of the same base model, a
    genuinely different quantization -- same-source tokens are the honest gate)."""
    worker = _gpu_worker_stage6144()
    converted = prepare_model_checkpoint_from_gguf(
        _TINYLLAMA_GGUF, _TINYLLAMA_PROMPT, out_dir=tmp_path
    )
    result = decode(
        _runtime(worker),
        checkpoint_dir=_TINYLLAMA_GGUF,  # any checkpoint_dir; converted_checkpoint_dir wins
        prompt_token_ids=_TINYLLAMA_PROMPT,
        max_new_tokens=8,
        converted_checkpoint_dir=converted,
    )
    engine_tokens = result.token_ids[len(_TINYLLAMA_PROMPT) :]
    reference_tokens = _tinyllama_cpu_reference_tokens(_TINYLLAMA_GGUF, _TINYLLAMA_PROMPT, 8)
    assert engine_tokens == reference_tokens
    # The model answers the France prompt coherently (" Paris" is token 3900 -- the campaign's
    # TinyLlama oracle first token).
    assert engine_tokens[0] == 3900


@pytest.mark.skipif(_gpu_worker() is None, reason="no GPU worker binary built")
def test_gguf_rope_freqs_decode_runs_end_to_end(tmp_path: Path) -> None:
    """The rope_freqs.weight GGUF tensor reaches the ENGINE's rope table (the manifest's
    rope_freq_factors -> _rope_table_from_manifest's explicit-factors branch ->
    attnk.rope.rope_table_freq_factors): a synthetic llama GGUF carrying baked frequency
    divisors converts, decodes on the real Metal path, and stays deterministic. All-zero
    weights: this is a wiring/no-crash proof, not an output-quality claim."""
    factors = [1.0, 2.0, 4.0, 8.0] + [1.5] * 12  # 16 divisors = head_dim 32 / 2 pairs
    rope_raw = b"".join(struct.pack("<f", v) for v in factors)
    gguf = tmp_path / "rope_run.gguf"
    metadata = _llama_metadata(**{"tokenizer.ggml.eos_token_id": 2})
    _write_test_gguf(
        gguf,
        metadata,
        _full_synthetic_llama_tensors() + [("rope_freqs.weight", 0, [16], rope_raw)],
    )
    converted = prepare_model_checkpoint_from_gguf(gguf, [1, 2, 3], out_dir=tmp_path / "out")
    manifest = json.loads((converted / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["rope_freq_factors"] == pytest.approx(factors)
    result = decode(
        _runtime(_gpu_worker()),
        checkpoint_dir=gguf,
        prompt_token_ids=[1, 2, 3],
        max_new_tokens=4,
        converted_checkpoint_dir=converted,
    )
    assert len(result.token_ids) == 7
    assert all(0 <= token < 16 for token in result.token_ids)
    again = decode(
        _runtime(_gpu_worker()),
        checkpoint_dir=gguf,
        prompt_token_ids=[1, 2, 3],
        max_new_tokens=4,
        converted_checkpoint_dir=converted,
    )
    assert again.token_ids == result.token_ids
