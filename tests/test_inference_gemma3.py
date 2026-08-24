"""The Gemma 3 converter gates (Gemma 3 lane, 2026-08-23).

The engine runs google/gemma-3-27b-it-class checkpoints through the SAME manifest+blob format
the Qwen3/llama families use, plus a gemma3 convention set. These tests pin that set against a
SYNTHETIC gemma3 checkpoint (benchmarks/llm_smoke/gemma3/synthetic_gemma3.py -- tiny dims, every
structural feature present) and against a replica of the shipped 27B config.json, BEFORE any GPU
work happens:

* the multimodal wrapper config lifts to the text model; the shipped file's OMISSIONS
  (no rope_theta / rms_norm_eps / layer_types in text_config) resolve to the transformers class
  defaults VERIFIED from configuration_gemma3.py (global theta 1e6 + linear factor on global
  layers only, local theta 1e4, eps 1e-6, pattern-6 layer mix);
* the snapshot's `language_model.` tensor prefix remaps onto the canonical manifest names;
* every RMSNorm gain lands in the blob REBASED to Gemma's (1.0 + weight) convention;
* the f32 blob option is EXACT (BF16-origin values fit float32) and half the size;
* features the kernels do not implement are REFUSED, never silently dropped (softcapping,
  bidirectional attention, qkv biases, non-linear rope scaling, non-tanh GELU).

The token-level engine half of this gate lives in the CUDA lane (benchmarks/llm_smoke/gemma3/),
which runs the same synthetic checkpoint against ref_gemma3_torch.py.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
_GEMMA3_TOOLS = ROOT / "benchmarks" / "llm_smoke" / "gemma3"
for _path in (_ALGENTA, _GEMMA3_TOOLS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from algenta.inference import (  # noqa: E402
    UnsupportedArchitectureError,
    _gemma3_prepare_config,
    _normalize_config,
    _validate_architecture,
    prepare_model_checkpoint,
)
from synthetic_gemma3 import DEFAULT_SHAPE, build_synthetic_gemma3  # noqa: E402

_PROMPT = [1, 5, 10, 20]


def _manifest_config(out_dir: Path) -> dict:
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))["config"]


def _read_blob_slice(out_dir: Path, manifest: dict, name: str):
    import numpy as np

    tensor = manifest["tensors"][name]
    dtype = manifest["config"].get("weights_dtype", "f64")
    element = np.dtype("<f8") if dtype == "f64" else np.dtype("<f4")
    raw = (out_dir / "weights.blob").read_bytes()
    start = tensor["offset"] * element.itemsize
    values = np.frombuffer(
        raw, dtype=element, count=tensor["n_elements"], offset=start
    )
    return values, tensor["shape"]


def test_gemma3_synthetic_converts_to_the_gemma3_contract(tmp_path: Path) -> None:
    ckpt = build_synthetic_gemma3(tmp_path / "ckpt")
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    config = _manifest_config(out)

    # The structural fields survive the lift from the multimodal wrapper.
    assert config["hidden_size"] == DEFAULT_SHAPE["hidden_size"]
    assert config["num_hidden_layers"] == DEFAULT_SHAPE["num_hidden_layers"]
    assert config["head_dim"] == DEFAULT_SHAPE["head_dim"]
    assert config["vocab_size"] == DEFAULT_SHAPE["vocab_size"]

    # The gemma3 convention set, pinned exactly.
    assert config["model_family"] == "gemma3"
    assert config["activation_code"] == 1  # GeGLU gelu_pytorch_tanh
    assert config["norm_weight_plus_one"] == 1
    assert config["embed_scale"] == pytest.approx(math.sqrt(DEFAULT_SHAPE["hidden_size"]))
    assert config["query_pre_attn_scalar"] == DEFAULT_SHAPE["query_pre_attn_scalar"]
    assert config["sliding_window"] == DEFAULT_SHAPE["sliding_window"]
    # pattern 2 -> layers 1,3,5 full.
    assert config["layer_types"] == [0, 1, 0, 1, 0, 1]
    assert config["rope_theta"] == 1_000_000.0  # transformers default_theta["global"]
    assert config["rope_local_theta"] == 10_000.0  # default_theta["local"]
    assert config["rope_global_scaling_factor"] == 8.0  # the config's linear factor
    assert config["has_qk_norm"] == 1
    assert config["tie_word_embeddings"] == 1  # no lm_head tensor in the snapshot
    assert config["attention_bias"] == 0
    assert config["eos_token_ids"] == [1, 106]
    assert config["eos_token_id"] == 106  # compat single-id key
    assert config["rms_norm_eps"] == pytest.approx(1e-6)  # class default, file omits it
    assert "weights_dtype" not in config  # f64 by default -- no new key for old readers


def test_gemma3_norm_gains_land_rebased_in_the_blob(tmp_path: Path) -> None:
    """The blob's norm gains are (1.0 + shipped weight): the engine's gain-multiply kernels then
    compute Gemma's math EXACTLY. Checked tensor-by-tensor against the synthetic source."""
    import numpy as np

    ckpt = build_synthetic_gemma3(tmp_path / "ckpt")
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    # Read the synthetic's own shipped weights back for comparison.
    raw = (ckpt / "model.safetensors").read_bytes()
    (header_len,) = struct.unpack("<Q", raw[:8])
    header = json.loads(raw[8 : 8 + header_len])
    data_start = 8 + header_len

    def shipped(name: str) -> np.ndarray:
        info = header[f"language_model.{name}"]
        start, end = info["data_offsets"]
        u16 = np.frombuffer(raw[data_start + start : data_start + end], dtype="<u2")
        return (u16.astype(np.uint32) << 16).view(np.float32).astype(np.float64)

    for canonical in (
        "model.norm.weight",
        "model.layers.0.input_layernorm.weight",
        "model.layers.1.post_attention_layernorm.weight",
        "model.layers.2.pre_feedforward_layernorm.weight",
        "model.layers.3.post_feedforward_layernorm.weight",
        "model.layers.4.self_attn.q_norm.weight",
        "model.layers.5.self_attn.k_norm.weight",
    ):
        values, shape = _read_blob_slice(out, manifest, canonical)
        expected = shipped(canonical) + 1.0
        assert values.shape[0] == expected.shape[0]
        np.testing.assert_array_equal(values, expected)

    # A NON-norm tensor lands verbatim (transposed for GEMMs): q_proj [out,in] -> [in,out].
    values, shape = _read_blob_slice(out, manifest, "model.layers.0.self_attn.q_proj.weight")
    h_q = DEFAULT_SHAPE["num_attention_heads"]
    d_head = DEFAULT_SHAPE["head_dim"]
    hidden = DEFAULT_SHAPE["hidden_size"]
    assert shape == [hidden, h_q * d_head]
    original = shipped("model.layers.0.self_attn.q_proj.weight").reshape(h_q * d_head, hidden)
    np.testing.assert_array_equal(values.reshape(shape), original.T)


def test_gemma3_f32_blob_is_exact_and_half_size(tmp_path: Path) -> None:
    ckpt = build_synthetic_gemma3(tmp_path / "ckpt")
    out64 = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out64")
    out32 = prepare_model_checkpoint(
        ckpt, _PROMPT, out_dir=tmp_path / "out32", weights_dtype="f32"
    )
    config32 = _manifest_config(out32)
    assert config32["weights_dtype"] == "f32"

    size64 = (out64 / "weights.blob").stat().st_size
    size32 = (out32 / "weights.blob").stat().st_size
    assert size32 * 2 == size64

    manifest32 = json.loads((out32 / "manifest.json").read_text(encoding="utf-8"))
    for name in ("model.embed_tokens.weight", "model.layers.1.mlp.gate_proj.weight",
                 "model.norm.weight"):
        values64, _ = _read_blob_slice(out64, json.loads((out64 / "manifest.json").read_text()), name)
        values32, _ = _read_blob_slice(out32, manifest32, name)
        # BF16-origin values are EXACT in float32: the narrow is lossless.
        import numpy as np

        np.testing.assert_array_equal(values32.astype(np.float64), values64)


@pytest.mark.parametrize("prefix", ["model.language_model.", ""])
def test_gemma3_alternate_tensor_prefixes(tmp_path: Path, prefix: str) -> None:
    ckpt = build_synthetic_gemma3(tmp_path / "ckpt", prefix=prefix)
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    assert _manifest_config(out)["model_family"] == "gemma3"


def test_gemma3_untied_variant_converts(tmp_path: Path) -> None:
    ckpt = build_synthetic_gemma3(tmp_path / "ckpt", untied=True)
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    config = _manifest_config(out)
    assert config["tie_word_embeddings"] == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "lm_head.weight" in manifest["tensors"]


def test_gemma3_explicit_layer_types(tmp_path: Path) -> None:
    shape = {
        "num_hidden_layers": 4,
        "layer_types": [
            "sliding_attention",
            "full_attention",
            "full_attention",
            "sliding_attention",
        ],
    }
    ckpt = build_synthetic_gemma3(tmp_path / "ckpt", shape=shape, explicit_layer_types=True)
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    assert _manifest_config(out)["layer_types"] == [0, 1, 1, 0]


def test_gemma3_real_27b_config_replica_resolves_to_shipped_facts() -> None:
    """The shipped google/gemma-3-27b-it text_config EXACTLY as downloaded (2026-08-23) -- its
    omissions must resolve to the transformers class defaults, and its present keys must land
    verbatim in the manifest entries."""
    text_config = {
        "head_dim": 128,
        "hidden_size": 5376,
        "intermediate_size": 21504,
        "model_type": "gemma3_text",
        "num_attention_heads": 32,
        "num_hidden_layers": 62,
        "num_key_value_heads": 16,
        "query_pre_attn_scalar": 168,
        "rope_scaling": {"factor": 8.0, "rope_type": "linear"},
        "sliding_window": 1024,
        # The wrapper's eos_token_id [1, 106], carried onto the lifted config by _normalize_config.
        "_gemma3_eos_token_ids": [1, 106],
    }
    config = _gemma3_prepare_config(dict(text_config), Path("config.json replica"))
    entries = config["_gemma3_manifest_entries"]
    assert entries["query_pre_attn_scalar"] == 168.0
    assert entries["sliding_window"] == 1024
    assert entries["rope_theta"] == 1_000_000.0
    assert entries["rope_local_theta"] == 10_000.0
    assert entries["rope_global_scaling_factor"] == 8.0
    assert entries["embed_scale"] == pytest.approx(math.sqrt(5376))
    assert entries["eos_token_ids"] == [1, 106]
    layer_types = entries["layer_types"]
    assert len(layer_types) == 62
    # pattern-6 mix: full at 5, 11, ..., 59 -> 10 global layers, 52 local.
    assert sum(layer_types) == 10
    assert all(layer_types[i] == 1 for i in range(5, 62, 6))
    assert all(layer_types[i] == 0 for i in range(0, 62, 6))


def test_gemma3_wrapper_lift_carries_eos() -> None:
    wrapper = {
        "model_type": "gemma3",
        "eos_token_id": [1, 106],
        "text_config": {"hidden_size": 64},
    }
    lifted = _normalize_config(wrapper)
    assert lifted["model_type"] == "gemma3_text"
    assert lifted["_gemma3_eos_token_ids"] == [1, 106]
    assert lifted["hidden_size"] == 64
    assert "text_config" not in lifted


def test_gemma3_omitted_head_fields_resolve_to_class_defaults() -> None:
    """The shipped 1B/4B checkpoints omit num_attention_heads / num_key_value_heads / head_dim;
    they must resolve to the Gemma3TextConfig class defaults (8 / 4 / 256 -- verified for the 4B
    against its q_proj [2048, 2560] = 8 heads x 256), NOT to hidden_size // heads."""
    text_config = {
        "model_type": "gemma3_text",
        "hidden_size": 2560,
        "num_hidden_layers": 34,
        "intermediate_size": 10240,
        "sliding_window": 1024,
        "rope_scaling": {"factor": 8.0, "rope_type": "linear"},
        "_gemma3_eos_token_ids": [1, 106],
    }
    # _normalize_config must NOT derive head_dim for gemma3 (hidden//heads is wrong here).
    lifted = _normalize_config(dict(text_config, model_type="gemma3", text_config=text_config))
    assert "head_dim" not in lifted or lifted.get("head_dim") != 2560 // 8
    prepared = _gemma3_prepare_config(lifted, Path("4b replica"))
    assert prepared["num_attention_heads"] == 8
    assert prepared["num_key_value_heads"] == 4
    assert prepared["head_dim"] == 256
    _validate_architecture(Path("4b replica"), prepared)


@pytest.mark.parametrize(
    "poison_key,poison_value",
    [
        ("attn_logit_softcapping", 50.0),
        ("final_logit_softcapping", 30.0),
        ("use_bidirectional_attention", True),
        ("attention_bias", True),
        ("hidden_activation", "gelu_erf"),
        ("rope_scaling", {"rope_type": "yarn", "factor": 8.0}),
        ("layer_types", ["sliding_attention", "bogus"]),
    ],
)
def test_gemma3_unimplemented_features_refused(
    tmp_path: Path, poison_key: str, poison_value: object
) -> None:
    """Every Gemma 3 feature the kernels do NOT implement is refused at conversion -- never
    silently dropped into a run with wrong math."""
    if poison_key == "layer_types":
        # A layer_types list whose LENGTH disagrees with num_hidden_layers.
        ckpt = build_synthetic_gemma3(tmp_path / "ckpt")
        config_path = ckpt / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["text_config"]["layer_types"] = poison_value  # len 2 vs 6 layers
        config["text_config"].pop("sliding_window_pattern", None)
        config_path.write_text(json.dumps(config), encoding="utf-8")
    else:
        ckpt = build_synthetic_gemma3(
            tmp_path / "ckpt", extra_text_config={poison_key: poison_value}
        )
    with pytest.raises(UnsupportedArchitectureError):
        prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
