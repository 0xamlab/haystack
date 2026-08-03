"""The Qwen3-0.6B-Base architecture Qwen3 decode refuses everything else against.

`_MBQwen3I8AllSimd7`'s kernels are compiled for one exact shape. That shape is stated as a literal
in THREE independent places, each for its own good reason (see each file's own comment):

* `mojo/engine/metaldispatch/qwen3_decode.mojo` — the Mojo-side gate, closest to the kernel.
* `packages/algenta/algenta/qwen3_decode.py` — the Python-side gate, checked before any conversion
  work starts (this package must not depend on `mojo/` or `benchmarks/` source files at runtime).
* `benchmarks/llm_smoke/generate_manifest.py` — the benchmark's own checkpoint-prep constants.

A duplicated invariant that drifts is worse than one that never existed (`docs/mojo/new-kernel-
package-rules.md` rule 3's "the rule applies inside your own package too" — restated across
languages here rather than within one package). This is the ledger: it fails the moment any one of
the three disagrees with the other two, naming exactly which field and which two files disagree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

MOJO_PATH = ROOT / "mojo" / "engine" / "metaldispatch" / "qwen3_decode.mojo"
PY_PATH = ROOT / "packages" / "algenta" / "algenta" / "qwen3_decode.py"
GENERATE_MANIFEST_PATH = ROOT / "benchmarks" / "llm_smoke" / "generate_manifest.py"

# Maps each side's own field/constant name to the SAME logical architecture field, so the three
# sources can be compared despite spelling their constants differently (Mojo comptime names are
# UPPER_SNAKE with a QWEN3_0_6B_BASE_ prefix; the Python dict and the benchmark script both use
# HuggingFace's own config.json field names, but the benchmark script's are UPPER_SNAKE too).
_MOJO_TO_LOGICAL = {
    "QWEN3_0_6B_BASE_D_MODEL": "hidden_size",
    "QWEN3_0_6B_BASE_N_LAYERS": "num_hidden_layers",
    "QWEN3_0_6B_BASE_H_Q": "num_attention_heads",
    "QWEN3_0_6B_BASE_H_KV": "num_key_value_heads",
    "QWEN3_0_6B_BASE_D_HEAD": "head_dim",
    "QWEN3_0_6B_BASE_D_FF": "intermediate_size",
    "QWEN3_0_6B_BASE_VOCAB": "vocab_size",
}
_GENERATE_MANIFEST_TO_LOGICAL = {
    "HIDDEN_SIZE": "hidden_size",
    "NUM_LAYERS": "num_hidden_layers",
    "NUM_HEADS": "num_attention_heads",
    "NUM_KV_HEADS": "num_key_value_heads",
    "HEAD_DIM": "head_dim",
    "INTERMEDIATE_SIZE": "intermediate_size",
    "VOCAB_SIZE": "vocab_size",
}


def _mojo_architecture() -> dict[str, int]:
    text = MOJO_PATH.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for mojo_name, logical_name in _MOJO_TO_LOGICAL.items():
        match = re.search(rf"comptime {mojo_name}: Int = (\d+)", text)
        assert match, f"{MOJO_PATH} no longer declares {mojo_name} as a plain Int literal"
        out[logical_name] = int(match.group(1))
    return out


def _generate_manifest_architecture() -> dict[str, int]:
    text = GENERATE_MANIFEST_PATH.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for const_name, logical_name in _GENERATE_MANIFEST_TO_LOGICAL.items():
        match = re.search(rf"^{const_name} = (\d+)", text, re.MULTILINE)
        assert match, f"{GENERATE_MANIFEST_PATH} no longer declares {const_name} as a plain int literal"
        out[logical_name] = int(match.group(1))
    return out


@pytest.fixture()
def python_architecture() -> dict[str, object]:
    import importlib

    module = importlib.import_module("algenta.qwen3_decode")
    return dict(module.QWEN3_0_6B_BASE_ARCHITECTURE)


def test_mojo_and_python_agree_on_every_shared_dimension(python_architecture: dict[str, object]) -> None:
    mojo = _mojo_architecture()
    mismatches = [
        f"{field}: mojo={mojo[field]!r} python={python_architecture[field]!r}"
        for field in mojo
        if mojo[field] != python_architecture[field]
    ]
    assert not mismatches, (
        "metaldispatch/qwen3_decode.mojo and algenta/qwen3_decode.py disagree on the architecture "
        f"this kernel path supports: {mismatches}"
    )


def test_generate_manifest_and_python_agree_on_every_shared_dimension(
    python_architecture: dict[str, object],
) -> None:
    benchmark = _generate_manifest_architecture()
    mismatches = [
        f"{field}: generate_manifest={benchmark[field]!r} python={python_architecture[field]!r}"
        for field in benchmark
        if benchmark[field] != python_architecture[field]
    ]
    assert not mismatches, (
        "benchmarks/llm_smoke/generate_manifest.py and algenta/qwen3_decode.py disagree on the "
        f"architecture this kernel path supports: {mismatches}"
    )


def test_mojo_and_generate_manifest_agree_on_every_shared_dimension() -> None:
    mojo = _mojo_architecture()
    benchmark = _generate_manifest_architecture()
    mismatches = [
        f"{field}: mojo={mojo[field]!r} generate_manifest={benchmark[field]!r}"
        for field in mojo
        if mojo[field] != benchmark[field]
    ]
    assert not mismatches, (
        "metaldispatch/qwen3_decode.mojo and benchmarks/llm_smoke/generate_manifest.py disagree on "
        f"the architecture this kernel path supports: {mismatches}"
    )


def test_python_gate_names_every_field_the_mojo_side_checks(
    python_architecture: dict[str, object],
) -> None:
    """The Python side ALSO validates fields the flat-int comparison above cannot express
    (`tie_word_embeddings`, `attention_bias`, `hidden_act`) — asserted so a future edit cannot
    quietly narrow the gate back down to only the dimensions."""
    for field in ("tie_word_embeddings", "attention_bias", "hidden_act"):
        assert field in python_architecture, (
            f"algenta.qwen3_decode.QWEN3_0_6B_BASE_ARCHITECTURE dropped {field!r} — a checkpoint "
            "that matches every dimension but not this field would no longer be refused"
        )


def test_eos_token_id_matches_the_benchmark_drivers_own_constant() -> None:
    """`QWEN3_0_6B_BASE_EOS_TOKEN_ID` is a tokenizer property, not a `manifest.json` field, so it
    cannot be cross-checked the same way as the dimensions above — pinned against one real driver's
    own literal instead, so a typo here does not silently stop recognizing end-of-text."""
    driver_path = (
        ROOT / "benchmarks" / "llm_smoke" / "metal_batch_dispatch"
        / "qwen3_generate_batch_i8_allsimd7.mojo"
    )
    driver_text = driver_path.read_text(encoding="utf-8")
    driver_match = re.search(r"comptime EOS_TOKEN_ID: Int = (\d+)", driver_text)
    assert driver_match, f"{driver_path} no longer declares EOS_TOKEN_ID as a plain Int literal"

    mojo_text = MOJO_PATH.read_text(encoding="utf-8")
    mojo_match = re.search(r"comptime QWEN3_0_6B_BASE_EOS_TOKEN_ID: Int = (\d+)", mojo_text)
    assert mojo_match, f"{MOJO_PATH} no longer declares QWEN3_0_6B_BASE_EOS_TOKEN_ID"

    assert int(driver_match.group(1)) == int(mojo_match.group(1))
