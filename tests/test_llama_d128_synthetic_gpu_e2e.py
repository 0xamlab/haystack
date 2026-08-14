"""Synthetic llama d_head=128 (qk_norm=0) end-to-end gate.

Real llama-3 checkpoints are HuggingFace-GATED and not on this machine, so the llama-3-8B-class
shape (d_head=128, no QK-norm, untied lm_head) is verified with a SYNTHETIC checkpoint instead:
small random BF16 weights in a llama config whose head_dim derives to 128 (hidden 256 / 2 heads),
kv heads 1 (GQA), untied, no q_norm/k_norm tensors, rope_theta 10000.

What this proves (honestly scoped):
* the SDK converter accepts the llama d_head=128 shape and writes the right manifest convention
  flags (has_qk_norm=0, tie_word_embeddings=0, derived head_dim=128, lm_head converted);
* the engine RUNS it through the real Metal path -- no crash, every emitted token id inside the
  vocab, greedy-deterministic;
* the FAST AF prefill path is what actually runs (the paired run with
  use_native_grouped_fa_attn_no_mirror=False dispatches a DIFFERENT per-token dispatch count --
  the steel-AF table vs the parametric one -- proving the widened pairing gate routes d128
  qk_norm=0 onto the AF arm, not the parametric fallback);
* the same checkpoint with a llama-3.1 rope_scaling converts (flat rope_scaling_* manifest keys)
  and runs just as deterministically -- the end-to-end wiring proof for the scaling table.

What this CANNOT prove: output correctness against a real llama-3 (impossible without the gated
weights -- random weights produce random tokens). The rope FREQUENCIES themselves are verified
against an independent Python reference in tests/test_rope_scaling_llama3.py and
mojo/tests/libs/test_attnk_rope.mojo.
"""

from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.inference import (  # noqa: E402
    UnsupportedArchitectureError,
    decode,
    prepare_model_checkpoint,
)

# Synthetic llama d_head=128 shape: hidden 256 / 2 heads -> head_dim derives to 128 (the llama
# convention carries no explicit head_dim), GQA 2:1, untied, no QK-norm. Small enough for the
# default 3072 staging tier (stage_needed = max(256, 2*128, 512) = 512).
_HIDDEN = 256
_N_LAYERS = 2
_H_Q = 2
_H_KV = 1
_D_FF = 512
_VOCAB = 256
_HEAD_DIM = _HIDDEN // _H_Q  # 128 -- the point of this fixture
_PROMPT = [1, 5, 10, 20, 30]


def _bf16_bytes(values) -> bytes:
    """Float32 -> BF16 widening bytes (BF16 is the top 16 bits of FP32)."""
    import numpy as np

    u32 = values.astype(np.float32).view(np.uint32)
    return (u32 >> 16).astype(np.uint16).tobytes()


def _write_synthetic_llama_d128(
    checkpoint_dir: Path, rope_scaling: dict | None = None, seed: int = 20260814
) -> Path:
    """A single-shard BF16 llama checkpoint (config.json + model.safetensors) with seeded random
    weights -- the exact structural family of llama-3-8B (d_head=128, no QK-norm, untied)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "architectures": ["LlamaForCausalLM"],
        "attention_bias": False,
        "bos_token_id": 1,
        "eos_token_id": 2,
        "hidden_act": "silu",
        "hidden_size": _HIDDEN,
        "intermediate_size": _D_FF,
        "max_position_embeddings": 2048,
        "model_type": "llama",
        "num_attention_heads": _H_Q,
        "num_hidden_layers": _N_LAYERS,
        "num_key_value_heads": _H_KV,
        "rms_norm_eps": 1e-5,
        "rope_scaling": rope_scaling,
        "rope_theta": 10000.0,
        "tie_word_embeddings": False,
        "torch_dtype": "bfloat16",
        "vocab_size": _VOCAB,
    }
    (checkpoint_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def rand(*shape: int):
        return rng.normal(0.0, 0.02, size=shape).astype(np.float32)

    tensors: dict[str, tuple[list[int], bytes]] = {}

    def add(name: str, *shape: int) -> None:
        tensors[name] = (list(shape), _bf16_bytes(rand(*shape)))

    add("model.embed_tokens.weight", _VOCAB, _HIDDEN)
    add("model.norm.weight", _HIDDEN)
    add("lm_head.weight", _VOCAB, _HIDDEN)
    for layer in range(_N_LAYERS):
        prefix = f"model.layers.{layer}."
        add(prefix + "input_layernorm.weight", _HIDDEN)
        add(prefix + "post_attention_layernorm.weight", _HIDDEN)
        add(prefix + "self_attn.q_proj.weight", _H_Q * _HEAD_DIM, _HIDDEN)
        add(prefix + "self_attn.k_proj.weight", _H_KV * _HEAD_DIM, _HIDDEN)
        add(prefix + "self_attn.v_proj.weight", _H_KV * _HEAD_DIM, _HIDDEN)
        add(prefix + "self_attn.o_proj.weight", _HIDDEN, _H_Q * _HEAD_DIM)
        add(prefix + "mlp.gate_proj.weight", _D_FF, _HIDDEN)
        add(prefix + "mlp.up_proj.weight", _D_FF, _HIDDEN)
        add(prefix + "mlp.down_proj.weight", _HIDDEN, _D_FF)

    header: dict = {}
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


def _runtime(worker: Path):
    os.environ["ALGENTA_RUNTIME_FALLBACK_MODE"] = "allow"
    os.environ["ALGENTA_NATIVE_WORKER"] = str(worker)
    from algenta import MojoRuntime

    return MojoRuntime(mode="local", timeout=600.0)


def _gpu_worker() -> Path | None:
    override = os.environ.get("ALGENTA_GPU_WORKER")
    path = Path(override) if override else ROOT / "mojo_build" / "gpu-worker" / "algenta-gpu-worker"
    return path if path.is_file() and os.access(path, os.X_OK) else None


# --- unconditional converter checks --------------------------------------------------------------


def test_synthetic_llama_d128_converts_to_the_llama_contract(tmp_path: Path) -> None:
    ckpt = _write_synthetic_llama_d128(tmp_path / "ckpt")
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    config = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["config"]
    assert config["head_dim"] == 128  # derived llama-style: hidden // heads
    assert config["has_qk_norm"] == 0
    assert config["tie_word_embeddings"] == 0
    assert config["eos_token_id"] == 2
    assert "rope_scaling_type" not in config  # rope_scaling null -> no scaling keys


def test_synthetic_llama_d128_rope_scaling_converts_to_manifest_keys(tmp_path: Path) -> None:
    ckpt = _write_synthetic_llama_d128(
        tmp_path / "ckpt",
        rope_scaling={
            "rope_type": "llama3",
            "factor": 8.0,
            "low_freq_factor": 1.0,
            "high_freq_factor": 4.0,
            "original_max_position_embeddings": 8192,
        },
    )
    out = prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    config = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["config"]
    assert config["rope_scaling_type"] == 3
    assert config["rope_scaling_factor"] == 8.0
    assert config["rope_scaling_low_freq_factor"] == 1.0
    assert config["rope_scaling_high_freq_factor"] == 4.0
    assert config["rope_scaling_original_max_position_embeddings"] == 8192


def test_synthetic_llama_d128_yarn_scaling_refused(tmp_path: Path) -> None:
    ckpt = _write_synthetic_llama_d128(
        tmp_path / "ckpt", rope_scaling={"rope_type": "yarn", "factor": 8.0}
    )
    with pytest.raises(UnsupportedArchitectureError) as excinfo:
        prepare_model_checkpoint(ckpt, _PROMPT, out_dir=tmp_path / "out")
    assert "yarn" in str(excinfo.value)


# --- GPU engine runs (opt-in: need a GPU worker binary) ------------------------------------------


def _worker_resolved_plan_lines() -> list[str]:
    """The entry point prints its resolved execution plan into the worker's own log; the runtime
    keeps that log under /tmp/algenta-runtime-* for as long as the runtime (and its worker) is
    alive, so reading it from inside the test is safe."""
    import glob

    lines: list[str] = []
    for log in glob.glob("/tmp/algenta-runtime-*/worker.log"):
        try:
            text = Path(log).read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        lines.extend(
            line.strip() for line in text.splitlines() if "resolved plan" in line
        )
    return lines


@pytest.mark.skipif(_gpu_worker() is None, reason="no GPU worker binary built")
def test_synthetic_llama_d128_runs_fast_path_greedy_deterministic(tmp_path: Path) -> None:
    """The engine RUNS a llama d_head=128 qk_norm=0 model -- and routes it onto the FAST AF arm,
    proven by the worker's own resolved-plan line (attention = 2 = PF_ATTN_GROUPED_FA_NO_MIRROR,
    not the parametric 0) and by the parametric arm computing the SAME greedy sequence. Output
    VALUES are random-weights noise: this is a routing/kernels/no-crash proof, not a quality
    claim (impossible without the gated real llama-3 weights)."""
    ckpt = _write_synthetic_llama_d128(tmp_path / "ckpt")
    runtime = _runtime(_gpu_worker())
    common = {"checkpoint_dir": ckpt, "prompt_token_ids": _PROMPT, "max_new_tokens": 8}

    def _new_plan_line_count(marker: str, before: list[str]) -> int:
        after = _worker_resolved_plan_lines()
        return sum("attention" in line and marker in line for line in after) - sum(
            "attention" in line and marker in line for line in before
        )

    plan_lines_before = _worker_resolved_plan_lines()
    fast = decode(runtime, **common)
    assert len(fast.token_ids) == len(_PROMPT) + 8
    assert all(0 <= token < _VOCAB for token in fast.token_ids)
    assert fast.prefill_tokens_per_sec > 0.0
    assert fast.decode_tokens_per_sec > 0.0
    fast_again = decode(runtime, **common)
    assert fast_again.token_ids == fast.token_ids, "greedy decode is deterministic"

    parametric = decode(runtime, use_native_grouped_fa_attn_no_mirror=False, **common)
    # Both arms compute the SAME model: identical greedy sequences across the steel-AF and the
    # parametric dispatch tables.
    assert parametric.token_ids == fast.token_ids, (
        "the AF and parametric arms disagree on a greedy sequence -- the fast path is not "
        "computing the same model"
    )

    # The routing proof: the worker's own NEW plan lines (this test's calls only -- occurrence
    # counts diffed against the pre-test state) show the d128 qk_norm=0 session resolved the FAST
    # no-mirror AF attention (2), while the paired arm resolved OFF (0). Before the pairing gate
    # widened, a d128 qk_norm=0 model degraded to the parametric paths.
    assert _new_plan_line_count("attention = 2", plan_lines_before) >= 1, (
        "no AF no-mirror plan resolved for the d128 qk_norm=0 model -- the pairing gate did not "
        "route it onto the fast path"
    )
    assert _new_plan_line_count("attention = 0", plan_lines_before) >= 1, (
        "the parametric arm did not resolve OFF"
    )


@pytest.mark.skipif(_gpu_worker() is None, reason="no GPU worker binary built")
def test_synthetic_llama_d128_deep_context_splitk_decode(tmp_path: Path) -> None:
    """Decode past the split-K threshold on qk_norm=0 KV: a 300-token prompt puts every decode
    step at >128 keys, where the d_head=128 flash-decoding partial (f4u2) reads the packed-F16
    KV the flagged kvprod wrote. Must stay in-vocab and deterministic."""
    ckpt = _write_synthetic_llama_d128(tmp_path / "ckpt")
    runtime = _runtime(_gpu_worker())
    prompt = _PROMPT * 60  # 300 tokens
    common = {"checkpoint_dir": ckpt, "prompt_token_ids": prompt, "max_new_tokens": 6}
    result = decode(runtime, **common)
    assert result.n_prompt == 300
    assert len(result.token_ids) == 306
    assert all(0 <= token < _VOCAB for token in result.token_ids)
    assert result.decode_tokens_per_sec > 0.0
    again = decode(runtime, **common)
    assert again.token_ids == result.token_ids


@pytest.mark.skipif(_gpu_worker() is None, reason="no GPU worker binary built")
def test_synthetic_llama_d128_rope_scaling_runs_end_to_end(tmp_path: Path) -> None:
    """The llama3-scaled rope table reaches the GPU path: the scaled checkpoint converts, runs,
    and stays deterministic. (The frequencies themselves are verified against the Python
    reference in test_rope_scaling_llama3.py / test_attnk_rope.mojo.)"""
    ckpt = _write_synthetic_llama_d128(
        tmp_path / "ckpt",
        rope_scaling={
            "rope_type": "llama3",
            "factor": 8.0,
            "low_freq_factor": 1.0,
            "high_freq_factor": 4.0,
            "original_max_position_embeddings": 8192,
        },
    )
    runtime = _runtime(_gpu_worker())
    common = {"checkpoint_dir": ckpt, "prompt_token_ids": _PROMPT, "max_new_tokens": 8}
    result = decode(runtime, **common)
    assert len(result.token_ids) == len(_PROMPT) + 8
    assert all(0 <= token < _VOCAB for token in result.token_ids)
    again = decode(runtime, **common)
    assert again.token_ids == result.token_ids
