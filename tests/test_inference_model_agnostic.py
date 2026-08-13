"""`algenta.inference` is the model-agnostic door onto the Metal GPU kernel path: it accepts any
model whose architecture the kernels support (structural invariants + alignment gates, read from the
checkpoint's own config.json) and routes it to the model-agnostic entry point, so one call works
across model sizes without a per-shape SDK function. This file checks:

* the architecture gate, unconditionally (no checkpoint needed): a supported structural config is
  accepted (tied OR untied embeddings -- both conventions are now branches the engine handles), and
  configs that violate the GQA / divisibility invariants are refused with
  `UnsupportedArchitectureError`;
* the multi-shard conversion, opt-in (needs a real multi-shard Qwen3 checkpoint on disk, never
  fetched by a test): `prepare_model_checkpoint` produces a `manifest.json` + `weights.blob` with the
  expected tensor count and config.

This mirrors `test_qwen3_decode_checkpoint_conversion.py`'s own convention (unconditional refusal
tests + opt-in real-checkpoint conversion check).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.inference import (  # noqa: E402
    InferenceError,
    UnsupportedArchitectureError,
    _normalize_config,
    _validate_architecture,
    prepare_model_checkpoint,
)

numpy = pytest.importorskip("numpy", reason="prepare_model_checkpoint needs numpy")

_REAL_MULTISHARD_DIR = Path(
    os.environ.get("ALGENTA_QWEN3_MULTISHARD_CHECKPOINT", "/private/tmp/qwen3-1.7b")
)
_PROMPT_TOKEN_IDS = [785, 6722, 315, 9625, 374]


def _supported_config(**overrides) -> dict:
    cfg = {
        "hidden_size": 1024,
        "num_hidden_layers": 28,
        "num_attention_heads": 16,
        "num_key_value_heads": 8,
        "head_dim": 128,
        "intermediate_size": 3072,
        "vocab_size": 151936,
        "rope_theta": 1000000.0,
        "rms_norm_eps": 1e-6,
        "tie_word_embeddings": True,
        "attention_bias": False,
    }
    cfg.update(overrides)
    return cfg


def test_supported_config_accepted() -> None:
    _validate_architecture(Path("/tmp/unused"), _supported_config())  # must not raise


def test_larger_supported_config_accepted() -> None:
    # A larger Qwen3-style shape (e.g. 1.7B: hidden 2048) is also structurally supported.
    _validate_architecture(
        Path("/tmp/unused"),
        _supported_config(hidden_size=2048, intermediate_size=6144),
    )


def test_normalize_config_trusts_explicit_head_dim() -> None:
    # Qwen3 carries head_dim explicitly (and it is NOT hidden_size//num_attention_heads: the q/k/v
    # project to h_q*head_dim=2048, past hidden_size=1024), so it must be trusted, never re-derived.
    cfg = _supported_config()
    assert _normalize_config(cfg)["head_dim"] == 128
    assert _normalize_config(cfg) == cfg  # nothing rewritten when head_dim is present


def test_normalize_config_derives_implicit_head_dim() -> None:
    # Llama-family configs omit head_dim (it is implicit hidden_size // num_attention_heads).
    cfg = _supported_config(hidden_size=2048, num_attention_heads=32, num_key_value_heads=4)
    del cfg["head_dim"]
    assert _normalize_config(cfg)["head_dim"] == 2048 // 32  # 64
    assert "head_dim" not in cfg  # the caller's dict is not mutated
    # And the derived shape passes the architecture gate end to end.
    _validate_architecture(Path("/tmp/unused"), _normalize_config(cfg))


def test_missing_field_refused() -> None:
    cfg = _supported_config()
    del cfg["head_dim"]
    with pytest.raises(UnsupportedArchitectureError):
        _validate_architecture(Path("/tmp/unused"), cfg)


def test_non_divisible_hidden_refused() -> None:
    with pytest.raises(UnsupportedArchitectureError):
        _validate_architecture(Path("/tmp/unused"), _supported_config(hidden_size=1000))


def test_bad_gqa_ratio_refused() -> None:
    with pytest.raises(UnsupportedArchitectureError):
        _validate_architecture(
            Path("/tmp/unused"),
            _supported_config(num_attention_heads=16, num_key_value_heads=7),
        )


def test_untied_embeddings_accepted() -> None:
    # Llama-family checkpoints untie the lm_head from the input embedding. That convention is now
    # a BRANCH the engine handles (a separate lm_head buffer pair), not a refusal -- so the gate
    # must accept it. The engine half of this gate landed with the llama-family increment.
    _validate_architecture(Path("/tmp/unused"), _supported_config(tie_word_embeddings=False))


def test_absent_tie_word_embeddings_defaults_to_tied() -> None:
    # A config that omits tie_word_embeddings is treated as tied (the transformers default), which
    # is also accepted -- the gate refuses neither convention, only the structural alignment gates.
    cfg = _supported_config()
    del cfg["tie_word_embeddings"]
    _validate_architecture(Path("/tmp/unused"), cfg)


def test_missing_checkpoint_dir_refused() -> None:
    with pytest.raises(InferenceError):
        prepare_model_checkpoint("/tmp/definitely-not-a-checkpoint-dir", _PROMPT_TOKEN_IDS)


def test_empty_prompt_refused(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps(_supported_config()))
    with pytest.raises(InferenceError):
        prepare_model_checkpoint(tmp_path, [])


def _has_real_multishard_checkpoint() -> bool:
    return (_REAL_MULTISHARD_DIR / "config.json").is_file() and (
        _REAL_MULTISHARD_DIR / "model.safetensors.index.json"
    ).is_file()


@pytest.mark.skipif(
    not _has_real_multishard_checkpoint(),
    reason=(
        f"no real multi-shard checkpoint at {_REAL_MULTISHARD_DIR} (set "
        "ALGENTA_QWEN3_MULTISHARD_CHECKPOINT); this is a manual download, never fetched by a test"
    ),
)
def test_prepare_model_checkpoint_multishard(tmp_path: Path) -> None:
    """Converts a real multi-shard Qwen3 checkpoint and checks the manifest + blob are shaped right
    (correct tensor count, config echoed, blob present)."""
    cfg = json.loads((_REAL_MULTISHARD_DIR / "config.json").read_text())
    n_layers = cfg["num_hidden_layers"]
    expected_tensors = n_layers * 11 + 2  # embed + final norm + 11 per layer
    out_dir = prepare_model_checkpoint(_REAL_MULTISHARD_DIR, _PROMPT_TOKEN_IDS, out_dir=tmp_path)
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["config"]["hidden_size"] == cfg["hidden_size"]
    assert manifest["config"]["num_hidden_layers"] == n_layers
    assert manifest["config"]["vocab_size"] == cfg["vocab_size"]
    assert manifest["config"]["n_tokens"] == len(_PROMPT_TOKEN_IDS)
    assert len(manifest["tensors"]) == expected_tensors
    assert (out_dir / "weights.blob").is_file()
    assert (out_dir / "weights.blob").stat().st_size > 0
