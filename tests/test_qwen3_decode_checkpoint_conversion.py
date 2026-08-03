"""`algenta.qwen3_decode.prepare_checkpoint` is a second, independent implementation of
`benchmarks/llm_smoke/generate_manifest.py`'s own safetensors -> {manifest.json, weights.blob}
conversion (byte-level header parse, exact BF16->Float64 widen, the same seven weight tensors
pre-transposed). "Independent" only means something if it is actually checked against the original —
this file is that check, plus the architecture-gate unit tests that need no checkpoint at all.

The byte-for-byte comparison against a real checkpoint is opt-in, not a hard CI requirement: it
needs a real ~1.1 GiB Qwen3-0.6B-Base checkpoint on disk (this project's own README-documented
manual download step, never fetched by a test), `numpy`, and a prior, human-run
`generate_manifest.py` invocation to compare against (never re-run by this test — see that test's
own docstring for why). Skipped, not failed, when any of those is absent — the unit tests below
cover the refusal behavior unconditionally.
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

from algenta.qwen3_decode import (  # noqa: E402
    QWEN3_0_6B_BASE_ARCHITECTURE,
    Qwen3DecodeError,
    UnsupportedCheckpointArchitectureError,
    prepare_checkpoint,
)

numpy = pytest.importorskip("numpy", reason="prepare_checkpoint needs numpy")

_REAL_CHECKPOINT_DIR = Path(os.environ.get("ALGENTA_QWEN3_TEST_CHECKPOINT", "/tmp/qwen3-0.6b-base"))
_PROMPT_TOKEN_IDS = [785, 6722, 315, 9625, 374]  # "The capital of France is", this checkpoint's own tokenizer
# generate_manifest.py's own hardcoded output location (`OUT_MANIFEST`/`OUT_BLOB`) -- module-level
# constants reassigned unconditionally by that script's own top-level code, so they cannot be
# overridden from outside without editing the (frozen-in-spirit, untouched-by-this-task) script.
# Comparing against whatever it most recently wrote there is what "independent, then checked
# against the original" means without either re-running that exact script (which would clobber a
# shared machine's `/tmp/qwen3smoke` while other work may depend on its current contents) or
# duplicating its logic a third time just to regenerate a reference.
_GENERATE_MANIFEST_OUT_DIR = Path("/tmp/qwen3smoke")


def _has_real_checkpoint() -> bool:
    return (_REAL_CHECKPOINT_DIR / "config.json").is_file() and (
        _REAL_CHECKPOINT_DIR / "model.safetensors"
    ).is_file()


def _has_generate_manifest_reference() -> bool:
    return (_GENERATE_MANIFEST_OUT_DIR / "manifest.json").is_file() and (
        _GENERATE_MANIFEST_OUT_DIR / "weights.blob"
    ).is_file()


@pytest.mark.skipif(
    not _has_real_checkpoint(),
    reason=(
        f"no real checkpoint at {_REAL_CHECKPOINT_DIR} (set ALGENTA_QWEN3_TEST_CHECKPOINT); this is "
        "the documented manual download in benchmarks/llm_smoke/README.md, never fetched by a test"
    ),
)
@pytest.mark.skipif(
    not _has_generate_manifest_reference(),
    reason=(
        f"no generate_manifest.py output at {_GENERATE_MANIFEST_OUT_DIR} yet; run "
        "`python3 benchmarks/llm_smoke/generate_manifest.py` once first (see that script's own "
        "docstring) to produce the reference this test compares against"
    ),
)
def test_prepare_checkpoint_matches_generate_manifest_byte_for_byte(tmp_path: Path) -> None:
    """Converts the SAME real checkpoint and prompt `benchmarks/llm_smoke/generate_manifest.py`'s
    own most recent output at `/tmp/qwen3smoke` was produced from, and diffs both output files byte
    for byte against that unmodified script's own output -- not "should produce the same thing", an
    actual measured comparison against the real artifact today's races were run against."""
    reference_manifest = json.loads((_GENERATE_MANIFEST_OUT_DIR / "manifest.json").read_text())
    reference_input_ids = reference_manifest.get("input_ids")
    assert reference_input_ids, f"{_GENERATE_MANIFEST_OUT_DIR / 'manifest.json'} has no input_ids"

    mine_out = prepare_checkpoint(_REAL_CHECKPOINT_DIR, reference_input_ids, out_dir=tmp_path / "mine")
    mine_manifest = json.loads((mine_out / "manifest.json").read_text())
    assert mine_manifest == reference_manifest, (
        "prepare_checkpoint()'s manifest.json differs from generate_manifest.py's own most recent "
        f"output at {_GENERATE_MANIFEST_OUT_DIR} for the same real checkpoint and prompt"
    )

    reference_blob = (_GENERATE_MANIFEST_OUT_DIR / "weights.blob").read_bytes()
    mine_blob = (mine_out / "weights.blob").read_bytes()
    assert mine_blob == reference_blob, (
        "prepare_checkpoint()'s weights.blob differs byte-for-byte from generate_manifest.py's own "
        f"most recent output at {_GENERATE_MANIFEST_OUT_DIR} for the same real checkpoint and prompt "
        f"({len(mine_blob)} vs {len(reference_blob)} bytes)"
    )


def test_unsupported_architecture_is_refused_before_any_safetensors_read(tmp_path: Path) -> None:
    """The architecture gate fires from `config.json` alone -- a checkpoint with a mismatched shape
    and NO `model.safetensors` file at all still gets the specific, named shape refusal, not a
    missing-file error, because the shape check runs first and is the more actionable reason."""
    bad_config = dict(QWEN3_0_6B_BASE_ARCHITECTURE)
    bad_config["num_hidden_layers"] = 36  # Qwen3-1.7B's own layer count, a real different shape
    (tmp_path / "config.json").write_text(json.dumps(bad_config), encoding="utf-8")
    assert not (tmp_path / "model.safetensors").exists()

    with pytest.raises(UnsupportedCheckpointArchitectureError) as excinfo:
        prepare_checkpoint(tmp_path, _PROMPT_TOKEN_IDS)
    assert "num_hidden_layers" in str(excinfo.value)
    assert excinfo.value.code == "unsupported_architecture"


def test_missing_checkpoint_files_are_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(Qwen3DecodeError) as excinfo:
        prepare_checkpoint(tmp_path, _PROMPT_TOKEN_IDS)
    assert excinfo.value.code == "checkpoint_not_found"


def test_empty_prompt_token_ids_are_refused(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps(QWEN3_0_6B_BASE_ARCHITECTURE), encoding="utf-8")
    # A real (tiny, fabricated) safetensors header so the empty-prompt check is reached; if it were
    # not reached first, this would fail on the header instead and the test would prove nothing.
    header = json.dumps({}).encode("utf-8")
    (tmp_path / "model.safetensors").write_bytes(struct.pack("<Q", len(header)) + header)

    with pytest.raises(Qwen3DecodeError) as excinfo:
        prepare_checkpoint(tmp_path, [])
    assert excinfo.value.code == "invalid_arguments"


def test_negative_token_id_is_refused(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps(QWEN3_0_6B_BASE_ARCHITECTURE), encoding="utf-8")
    header = json.dumps({}).encode("utf-8")
    (tmp_path / "model.safetensors").write_bytes(struct.pack("<Q", len(header)) + header)

    with pytest.raises(Qwen3DecodeError) as excinfo:
        prepare_checkpoint(tmp_path, [1, 2, -3])
    assert excinfo.value.code == "invalid_arguments"
