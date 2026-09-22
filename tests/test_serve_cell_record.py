"""Unit tests for scripts/release/serve_cell_record.py -- the serve -> gate-cell-record parser.

These run with NO GPU, NO wheel, NO engine binary and NO network: the parser is the part of the
CUDA release-verify gate that decides whether a cell PASSED, so it is the part that must be pinned
by fabricated outputs rather than trusted because it worked once on a box.

The invariant every case checks is the one gate_any.py depends on: a cell that did not produce
tokens has NO `generated` key, so the evaluator takes its NOT-RUN branch and the gate FAILS. A
refusal that could be read as a pass is the failure mode this whole leg exists to prevent.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[1] / "scripts" / "release" / "serve_cell_record.py"
_spec = importlib.util.spec_from_file_location("serve_cell_record", _MODULE)
serve_cell_record = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serve_cell_record)

parse = serve_cell_record.parse_serve_output
build = serve_cell_record.build_serve_command

QWEN_EOS = 151645
COMMON = dict(
    label="gate_pp256_maxnew16",
    prompt="pp256",
    n_prompt=256,
    requested=16,
    worker_sha256_16="af7b4c6071826bca",
    wheel_sha256_16="ad2b852798ff33c9",
    cell_seconds=12.34,
    eos_tokens=(QWEN_EOS,),
)


def _payload(token_ids, **extra):
    body = {
        "ok": True,
        "token_ids": list(token_ids),
        "text": "###",
        "timing": {"ttft_ms": 24.2, "decode_tokens_per_sec": 83.1},
        "engine": {"returncode": 0},
        "refusal": None,
        "error": None,
        "plan": {"gate": {"accepted": True, "refusals": []}},
    }
    body.update(extra)
    return json.dumps(body)


# ── 1. CLEAN ───────────────────────────────────────────────────────────────────────────────────
def test_clean_run_produces_a_gated_record():
    ids = list(range(1000, 1016))
    record, error = parse(returncode=0, stdout=_payload(ids), stderr="", **COMMON)
    assert error is None
    assert record["generated"] == ids
    assert record["n_generated"] == 16
    # A PASS record carries no `ran` key at all; only refusals carry `ran: False`. Asserting the
    # absence (rather than `record["ran"] is not False`) also catches a future refactor that starts
    # writing ran:True into passing records and thereby changes what gate_any.py sees.
    assert "ran" not in record
    assert record["arm"] == "cuda_release_wheel_serve"
    assert record["worker_sha256_16"] == "af7b4c6071826bca"
    assert record["wheel_sha256_16"] == "ad2b852798ff33c9"
    assert record["ttft_ms"] == 24.2
    assert record["decode_tok_s"] == 83.1
    assert record["requested"] == 16 and record["n_prompt"] == 256


def test_generated_ids_are_not_sliced_by_n_prompt():
    """THE regression this module exists to prevent.

    decode() returns prompt+generated and its caller slices [n_prompt:]. The serve engine's
    CONFORM_TOKENS line carries GENERATED ids only. If the parser ever sliced here, a 256-token
    prompt with a 16-token generation would yield an EMPTY list (256 > 16) and every cell would read
    as an empty generation -- or, for a short prompt, as the wrong tokens compared to the oracle.
    """
    ids = [7, 8, 9]
    record, error = parse(returncode=0, stdout=_payload(ids), stderr="", **COMMON)
    assert error is None
    assert record["generated"] == [7, 8, 9], "generated must be the serve ids verbatim, unsliced"
    assert record["n_generated"] == 3
    assert record["stopped_on_eos"] is True  # 3 < 16 requested
    assert record["eos_stop"] is False  # stopped early, but not on an eos


def test_early_stop_on_the_tokenizer_eos_sets_eos_stop():
    ids = [11, 12, QWEN_EOS]
    record, error = parse(returncode=0, stdout=_payload(ids), stderr="", **COMMON)
    assert error is None
    assert record["eos_stop"] is True
    assert record["last_token"] == QWEN_EOS


def test_gemma_eos_does_not_set_eos_stop_for_a_qwen_engine():
    """An eos set from the wrong tokenizer must not corroborate anything."""
    record, error = parse(
        returncode=0, stdout=_payload([11, 12, 106]), stderr="", eos_tokens=(QWEN_EOS,),
        label=COMMON["label"], prompt=COMMON["prompt"], n_prompt=256, requested=16,
        worker_sha256_16="w", wheel_sha256_16="h", cell_seconds=1.0,
    )
    assert error is None
    assert record["eos_stop"] is False


# ── 2. rc=2 TYPED REFUSAL ──────────────────────────────────────────────────────────────────────
def test_rc2_refusal_is_a_record_without_generated_and_keeps_the_refusal_verbatim():
    payload = {
        "ok": False,
        "token_ids": [],
        "text": None,
        "timing": None,
        "engine": None,
        "refusal": {
            "code": "no_nvidia_gpu",
            "stage": "host",
            "detail": "no NVIDIA driver interface answered on this host",
            "fact": "nvidia_driver",
            "value": "absent",
            "supported": "NVIDIA driver >= 580.0",
            "remedy": "install an NVIDIA driver",
            "message": "no_nvidia_gpu: no NVIDIA driver interface answered on this host",
        },
        "error": None,
        "plan": {"gate": {"accepted": False, "refusals": [
            {"code": "no_nvidia_gpu", "stage": "host"}]}},
    }
    record, error = parse(returncode=2, stdout=json.dumps(payload), stderr="", **COMMON)
    assert error is not None
    assert "generated" not in record, "a refused cell must be NOT-RUN to gate_any.py"
    assert record["ran"] is False
    assert record["serve_rc"] == 2
    # VERBATIM: the product's own code and message, not a paraphrase of them.
    assert "no_nvidia_gpu" in error
    assert "no NVIDIA driver interface answered on this host" in error
    assert record["serve_refusal"]["code"] == "no_nvidia_gpu"


def test_rc2_with_an_error_object_reports_it_verbatim():
    payload = {"ok": False, "token_ids": [], "refusal": None,
               "error": {"code": "engine_launch_failed",
                         "message": "the engine binary exited 3 without producing tokens"}}
    record, error = parse(returncode=2, stdout=json.dumps(payload), stderr="", **COMMON)
    assert error is not None and "generated" not in record
    assert "engine_launch_failed" in error
    assert "the engine binary exited 3 without producing tokens" in error


def test_rc1_with_no_json_falls_back_to_the_stderr_tail():
    record, error = parse(
        returncode=1, stdout="", stderr="error: invalid_arguments: --model is required", **COMMON
    )
    assert error is not None and "generated" not in record
    assert record["ran"] is False and record["serve_rc"] == 1
    assert "--model is required" in error


def test_the_real_observed_metal_preflight_refusal_is_preserved():
    """The exact failure that ended the first r1115-cert window, as the engine reported it."""
    payload = {"ok": False, "token_ids": [], "refusal": None,
               "error": {"code": "unsupported_architecture",
                         "message": "preflight refused this run: metaldispatch_code_out_of_range"}}
    record, error = parse(returncode=1, stdout=json.dumps(payload), stderr="", **COMMON)
    assert "generated" not in record
    assert "metaldispatch_code_out_of_range" in error


# ── 3. TRUNCATED / MALFORMED JSON ──────────────────────────────────────────────────────────────
def test_truncated_json_is_a_refusal_not_a_crash():
    truncated = '{"ok": true, "token_ids": [1000, 1001, 10'
    record, error = parse(returncode=0, stdout=truncated, stderr="", **COMMON)
    assert error is not None
    assert "generated" not in record
    assert record["ran"] is False
    assert "not parseable" in error
    # The raw text is kept, because "the JSON was truncated" without the JSON is not diagnosable.
    assert record["stdout_tail"].endswith("10")


def test_empty_stdout_with_rc0_is_a_refusal():
    record, error = parse(returncode=0, stdout="", stderr="", **COMMON)
    assert error is not None and "generated" not in record
    assert "no parseable JSON" in error


def test_json_that_is_not_an_object_is_a_refusal():
    record, error = parse(returncode=0, stdout="[1,2,3]", stderr="", **COMMON)
    assert error is not None and "generated" not in record
    assert "not an object" in error


def test_whitespace_around_the_json_is_tolerated():
    ids = [5, 6, 7]
    record, error = parse(returncode=0, stdout="\n\n" + _payload(ids) + "\n", stderr="", **COMMON)
    assert error is None and record["generated"] == ids


# ── 4. EXIT 0 BUT NO TOKENS ────────────────────────────────────────────────────────────────────
def test_rc0_with_an_empty_token_list_is_a_refusal():
    record, error = parse(returncode=0, stdout=_payload([]), stderr="", **COMMON)
    assert error is not None
    assert "generated" not in record
    assert "ZERO tokens" in error


def test_rc0_with_token_ids_absent_is_a_refusal():
    payload = {"ok": False, "timing": None, "refusal": None, "error": None}
    record, error = parse(returncode=0, stdout=json.dumps(payload), stderr="", **COMMON)
    assert error is not None and "generated" not in record
    assert "no token_ids list" in error


def test_rc0_with_token_ids_not_a_list_is_a_refusal():
    payload = {"ok": True, "token_ids": "1000,1001"}
    record, error = parse(returncode=0, stdout=json.dumps(payload), stderr="", **COMMON)
    assert error is not None and "generated" not in record


def test_a_timeout_is_a_refusal():
    record, error = parse(
        returncode=-1, stdout="", stderr="serve cell exceeded its 1860s timeout", **COMMON
    )
    assert error is not None and "generated" not in record
    assert record["serve_rc"] == -1
    assert "timeout" in error


# ── 5. THE COMMAND ITSELF ──────────────────────────────────────────────────────────────────────
def test_build_serve_command_targets_the_bundled_cuda_engine():
    argv = build(
        python="/env/bin/python3.14",
        model="/models/Qwen2.5-7B-Instruct",
        converted_dir="/w7b/ckpt",
        prompt_token_ids=[2, 1756, 3402],
        max_new_tokens=64,
    )
    assert argv[0] == "/env/bin/python3.14"
    assert argv[1:3] == ["-m", "algenta.cli"], "no console_script exists in an unpacked wheel"
    assert "--backend" in argv and argv[argv.index("--backend") + 1] == "cuda"
    assert "--json" in argv
    # --model is the HF snapshot, --converted-dir the converted pair: serve/cli.py documents them
    # this way, and swapping them would make every cell re-convert a 57 GB blob.
    assert argv[argv.index("--model") + 1] == "/models/Qwen2.5-7B-Instruct"
    assert argv[argv.index("--converted-dir") + 1] == "/w7b/ckpt"
    assert argv[argv.index("--prompt-token-ids") + 1] == "2,1756,3402"
    assert argv[argv.index("--max-new-tokens") + 1] == "64"
    assert "--engine-binary" not in argv, (
        "the claim under test is that the resolver FINDS the engine from this wheel"
    )


def test_build_serve_command_optional_flags():
    argv = build(
        python="python3.14", model="/m", converted_dir="/c", prompt_token_ids=[1],
        max_new_tokens=16, weights_dtype="f64", timeout=900.0,
    )
    assert argv[argv.index("--weights-dtype") + 1] == "f64"
    assert argv[argv.index("--timeout") + 1] == "900.0"


# ── 6. RECORD SHAPE PARITY WITH THE decode() PATH ──────────────────────────────────────────────
def test_the_record_carries_the_same_keys_the_decode_path_carries():
    """gate_any.py and the coverage evaluator read specific keys; a serve cell that omitted one
    would be scored differently from a decode cell for the same tokens."""
    ids = list(range(16))
    record, error = parse(returncode=0, stdout=_payload(ids), stderr="", **COMMON)
    assert error is None
    required = {
        "label", "prompt", "n_prompt", "requested", "generated", "n_generated",
        "stopped_on_eos", "last_token", "eos_stop", "ttft_ms", "decode_tok_s",
        "dispatches_per_token", "arm", "worker_sha256_16", "wheel_sha256_16", "cell_seconds",
    }
    missing = required - set(record)
    assert not missing, "serve record is missing keys the decode path supplies: %s" % sorted(missing)


def test_unknown_timing_keys_yield_none_rather_than_a_guessed_rate():
    record, error = parse(
        returncode=0, stdout=_payload([1, 2, 3], timing={"something_else": 9.9}), stderr="",
        **COMMON
    )
    assert error is None
    assert record["ttft_ms"] is None and record["decode_tok_s"] is None
    assert record["serve_timing"] == {"something_else": 9.9}, "the raw block is carried, not guessed"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
