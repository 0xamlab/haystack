"""The model support system is declared facts, never family names: these tests
fix the verdict logic of `algenta.model_capabilities` -- the capability table
lookup, the typed refusals, and the path selection -- so a change to any gate
is a deliberate, reviewed table edit, not a branch buried in a converter.

Unconditional (no checkpoint, no GPU): the verdicts are pure functions of the
facts. The fact-space synthetic battery (`scripts/algenta_synthetic_battery.py`)
extends this proof onto the engine itself: every fact combination the table
claims SUPPORTED runs token-identical to an independent fp64 reference."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.model_capabilities import (  # noqa: E402
    BACKEND_FACT_RANGES,
    KERNEL_PATH_CAPABILITIES,
    POWER_OF_TWO_HEAD_DIMS,
    STAGING_TIERS,
    ModelFacts,
    extract_facts_from_config,
    refusals_for_facts,
    select_paths,
    stage_needed,
    unverified_facts,
)

_CONFORM = ROOT / "scripts" / "algenta_conform.py"


def _supported_facts(**overrides) -> ModelFacts:
    """A fact set inside the table on every axis (Qwen3-style d128 shape)."""
    facts = ModelFacts(
        hidden_size=1024,
        num_hidden_layers=28,
        num_attention_heads=16,
        num_key_value_heads=8,
        head_dim=128,
        intermediate_size=3072,
        vocab_size=151936,
        rope_theta=1000000.0,
        rms_norm_eps=1e-6,
        rope_class="plain",
        tie_word_embeddings=1,
        has_qk_norm=1,
        attention_bias=0,
        activation="silu",
        probed=True,
    )
    for key, value in overrides.items():
        facts = facts.__class__(**{**facts.as_dict(), key: value})
    return facts


def _refused_facts(facts: ModelFacts, backend: str = "metal") -> list:
    return refusals_for_facts(facts, backend=backend)


def _refusal_names(facts: ModelFacts, backend: str = "metal") -> set:
    return {refusal.fact for refusal in _refused_facts(facts, backend)}


# ── the supported core: facts inside the table on every axis ────────────────


def test_supported_core_has_no_refusals() -> None:
    assert refusals_for_facts(_supported_facts(), backend="metal") == []


def test_llama_style_d64_facts_supported() -> None:
    facts = _supported_facts(
        hidden_size=2048,
        num_hidden_layers=22,
        num_attention_heads=32,
        num_key_value_heads=4,
        head_dim=64,
        intermediate_size=5632,
        vocab_size=32000,
        rope_theta=10000.0,
        tie_word_embeddings=0,
        has_qk_norm=0,
    )
    assert refusals_for_facts(facts, backend="metal") == []


def test_qwen25_style_bias_refused_on_metal_supported_on_cuda() -> None:
    # The bias kernels are wired into the CUDA lane's five 7B paths, not the
    # Metal descriptor tables: the SAME facts are refused on metal and
    # supported on cuda. The refusal names the exact fact.
    facts = _supported_facts(attention_bias=1)
    metal = _refused_facts(facts, backend="metal")
    assert [refusal.fact for refusal in metal] == ["attention_bias"]
    assert metal[0].value == 1
    assert "metal" in metal[0].supported
    # On cuda the staging tier must cover the dims too (it does here: 3072).
    assert refusals_for_facts(facts, backend="cuda") == []


def test_every_structural_fact_refused_when_missing() -> None:
    for field in (
        "hidden_size",
        "num_hidden_layers",
        "num_attention_heads",
        "num_key_value_heads",
        "head_dim",
        "intermediate_size",
        "vocab_size",
    ):
        facts = _supported_facts(**{field: None})
        assert field in _refusal_names(facts), field


# ── head_dim: the capability table's own range ──────────────────────────────


def test_head_dim_range_matches_table() -> None:
    for d_head in POWER_OF_TWO_HEAD_DIMS:
        # Keep h_q * d_head inside the metal staging tiers (the stage_needed
        # fact is derived from dims) and the GQA ratio integral.
        h_q = min(32, 6144 // d_head)
        facts = _supported_facts(
            head_dim=d_head, num_attention_heads=h_q, num_key_value_heads=max(1, h_q // 2)
        )
        assert refusals_for_facts(facts, backend="metal") == [], d_head


@pytest.mark.parametrize("d_head", [48, 96, 160, 192, 384, 512])
def test_head_dim_outside_table_refused(d_head: int) -> None:
    facts = _supported_facts(head_dim=d_head, num_attention_heads=32)
    names = _refusal_names(facts)
    assert "head_dim" in names


def test_phi35_style_head_dim_96_refusal_message() -> None:
    facts = _supported_facts(head_dim=96, num_attention_heads=32)
    refusals = [r for r in _refused_facts(facts) if r.fact == "head_dim"]
    assert len(refusals) == 1
    assert "96" in refusals[0].message()
    assert "{32, 64, 128, 256}" in refusals[0].message()


def test_non_divisible_dims_refused() -> None:
    assert "hidden_size" in _refusal_names(_supported_facts(hidden_size=1000))
    assert "intermediate_size" in _refusal_names(_supported_facts(intermediate_size=3000))
    assert "num_attention_heads/num_key_value_heads" in _refusal_names(
        _supported_facts(num_attention_heads=16, num_key_value_heads=7)
    )


# ── the silent-hazard facts: refused, never ignored ─────────────────────────


@pytest.mark.parametrize(
    ("override", "expected_fact"),
    [
        ({"activation": "gelu_pytorch_tanh"}, "hidden_act"),
        ({"activation": "gelu"}, "hidden_act"),
        ({"sliding_window": 4096}, "sliding_window"),
        ({"attention_softcap": 50.0}, "attn_logit_softcapping"),
        ({"final_logit_softcap": 30.0}, "final_logit_softcapping"),
        ({"layer_types": ("sliding_attention", "full_attention")}, "layer_types"),
        ({"dual_theta_rope": True}, "rope_theta"),
        ({"partial_rotary_factor": 0.5}, "partial_rotary_factor"),
        ({"rope_class": "yarn"}, "rope_scaling"),
        ({"rope_class": "linear"}, "rope_scaling"),
    ],
)
def test_silent_hazard_facts_refused(override: dict, expected_fact: str) -> None:
    facts = _supported_facts(**override)
    assert expected_fact in _refusal_names(facts)


def test_llama3_rope_scaling_supported() -> None:
    facts = _supported_facts(rope_class="llama3")
    assert refusals_for_facts(facts, backend="metal") == []


def test_attention_scale_fact_refused_when_not_sqrt() -> None:
    facts = _supported_facts(query_pre_attn_scalar=256)  # head_dim=128 -> scale mismatch
    assert "query_pre_attn_scalar" in _refusal_names(facts)
    # equal to head_dim is the 1/sqrt(head_dim) convention itself: supported
    facts = _supported_facts(query_pre_attn_scalar=128)
    assert "query_pre_attn_scalar" not in _refusal_names(facts)


# ── staging tiers: derived from dims, judged per backend ────────────────────


def test_stage_needed_derivation() -> None:
    facts = _supported_facts(hidden_size=3584, num_attention_heads=28, head_dim=128, intermediate_size=18944)
    assert stage_needed(facts) == 18944  # max(d_model, h_q*d_head, d_ff)


def test_staging_refusal_names_the_tiers() -> None:
    facts = _supported_facts(intermediate_size=8192)  # stage_needed 8192 > metal's 6144 tier
    refusals = [r for r in _refused_facts(facts, backend="metal") if r.fact == "stage_needed"]
    assert len(refusals) == 1
    assert refusals[0].value == 8192
    assert "6144" in refusals[0].supported
    # the cuda family tiers to 18944: the same facts pass there
    assert refusals_for_facts(facts, backend="cuda") == []


def test_staging_tiers_declared() -> None:
    assert STAGING_TIERS == (3072, 6144, 8192, 18944)
    assert BACKEND_FACT_RANGES["metal"]["staging_tiers"] == (3072, 6144)
    assert BACKEND_FACT_RANGES["cuda"]["staging_tiers"] == STAGING_TIERS


# ── path selection: a pure lookup from the facts ────────────────────────────


def test_d128_selects_steel_and_f4u2() -> None:
    assignment = select_paths(_supported_facts(head_dim=128, has_qk_norm=1))
    assert assignment.prefill_attention == "prefill_attention/steel_grouped_fa_d128"
    assert assignment.decode_splitk_partial == "decode_attention/splitk_f4u2"
    assert assignment.kv_producer == "kvprod/v2"
    assert assignment.batched_decode is True
    assert assignment.plan == "grouped_fa_steel"


def test_d64_qkn0_selects_steel_d64_and_fused_partial() -> None:
    facts = _supported_facts(head_dim=64, num_attention_heads=32, num_key_value_heads=4, has_qk_norm=0)
    assignment = select_paths(facts)
    assert assignment.prefill_attention == "prefill_attention/steel_grouped_fa_d64"
    assert assignment.decode_splitk_partial == "decode_attention/splitk_f2s4k_kvprod_fused"
    assert assignment.kv_producer == "kvprod/naive_flagged"
    assert assignment.batched_decode is True


def test_d64_qkn1_degrades_to_parametric_native_decode() -> None:
    # The d64 steel twin and the batched d64 partial implement the no-QK-norm
    # pairing only: qk_norm=1 at d64 degrades to the parametric prefill +
    # norm-agnostic split-K decode path -- the engine's own resolution order.
    facts = _supported_facts(head_dim=64, num_attention_heads=32, num_key_value_heads=4, has_qk_norm=1)
    assignment = select_paths(facts)
    assert assignment.prefill_attention == "prefill_attention/parametric"
    assert assignment.decode_splitk_partial == "decode_attention/splitk_f2s4"
    assert assignment.batched_decode is False
    assert assignment.plan == "parametric_native_decode"


def test_d32_and_d256_take_parametric_paths() -> None:
    for d_head in (32, 256):
        facts = _supported_facts(head_dim=d_head, num_attention_heads=32, has_qk_norm=0)
        assignment = select_paths(facts)
        assert assignment.prefill_attention == "prefill_attention/parametric", d_head
        assert assignment.decode_splitk_partial is None, d_head
        assert assignment.plan == "parametric_off", d_head


def test_availability_degrades_like_the_engine() -> None:
    # A binary without the steel blobs degrades the d128 session exactly as
    # metaldispatch.session_prefill does: closest-capability-first to the
    # parametric path, never a hard error.
    facts = _supported_facts(head_dim=128, has_qk_norm=1)
    assignment = select_paths(
        facts,
        availability={
            "prefill_attention/steel_grouped_fa_d128": False,
            "decode_attention/splitk_f4u2": False,
        },
    )
    assert assignment.prefill_attention == "prefill_attention/parametric"
    assert assignment.decode_splitk_partial is None


def test_per_layer_assignment_uniform() -> None:
    facts = _supported_facts(num_hidden_layers=4)
    layers = select_paths(facts).per_layer(4)
    assert len(layers) == 4
    assert [layer["layer"] for layer in layers] == [0, 1, 2, 3]
    assert all(layer["prefill_attention"] == layers[0]["prefill_attention"] for layer in layers)


def test_capability_table_covers_every_selected_path() -> None:
    # Selection can only ever name paths declared in the table.
    for d_head in POWER_OF_TWO_HEAD_DIMS:
        for qk_norm in (0, 1):
            facts = _supported_facts(head_dim=d_head, num_attention_heads=32, has_qk_norm=qk_norm)
            assignment = select_paths(facts)
            assert assignment.prefill_attention in KERNEL_PATH_CAPABILITIES
            assert assignment.kv_producer in KERNEL_PATH_CAPABILITIES
            if assignment.decode_splitk_partial is not None:
                assert assignment.decode_splitk_partial in KERNEL_PATH_CAPABILITIES


# ── config extraction + the config-only verdict ─────────────────────────────


def test_extract_derives_implicit_head_dim_and_trusts_explicit() -> None:
    cfg = {"hidden_size": 2048, "num_attention_heads": 32, "num_key_value_heads": 4}
    assert extract_facts_from_config(cfg).head_dim == 64
    # Qwen3's explicit head_dim is NOT hidden_size//heads: trusted, never re-derived.
    cfg = {"hidden_size": 1024, "num_attention_heads": 16, "head_dim": 128}
    assert extract_facts_from_config(cfg).head_dim == 128


def test_extract_window_normalized_against_max_position() -> None:
    # A window that covers the whole context is no window (phi-3.5 convention);
    # a genuine window stays a fact.
    cfg = {"sliding_window": 262144, "max_position_embeddings": 262144}
    assert extract_facts_from_config(cfg).sliding_window is None
    cfg = {"sliding_window": 4096, "max_position_embeddings": 32768}
    assert extract_facts_from_config(cfg).sliding_window == 4096
    cfg = {"sliding_window": 4096, "use_sliding_window": False}
    assert extract_facts_from_config(cfg).sliding_window is None


def test_unverified_facts_reports_pending_probe() -> None:
    facts = _supported_facts(has_qk_norm=None, attention_bias=None, probed=False)
    assert set(unverified_facts(facts)) == {"has_qk_norm", "attention_bias"}
    assert unverified_facts(_supported_facts()) == []


# ── the conform CLI end to end (subprocess, exit codes are the contract) ────


def _run_conform(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_CONFORM), *args], capture_output=True, text=True, check=False
    )


def test_conform_cli_supported_exit_code(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "hidden_size": 1024,
                "num_hidden_layers": 4,
                "num_attention_heads": 16,
                "num_key_value_heads": 8,
                "head_dim": 128,
                "intermediate_size": 3072,
                "vocab_size": 32000,
                "rope_theta": 10000.0,
                "rms_norm_eps": 1e-6,
            }
        )
    )
    # A bare config.json owes the tensor-level probe (qk_norm/bias presence
    # are facts of the WEIGHTS): the honest config-only verdict is pending.
    result = _run_conform(str(tmp_path / "config.json"), "--backend", "metal")
    assert result.returncode == 3, result.stdout + result.stderr
    assert "verdict: supported_pending_probe" in result.stdout
    assert "pending probe: has_qk_norm, attention_bias" in result.stdout


def test_conform_cli_typed_refusal_exit_code(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "hidden_size": 3072,
                "num_hidden_layers": 32,
                "num_attention_heads": 32,
                "num_key_value_heads": 32,
                "head_dim": 96,
                "intermediate_size": 8192,
                "vocab_size": 32064,
                "rope_theta": 10000.0,
                "rms_norm_eps": 1e-5,
            }
        )
    )
    result = _run_conform(str(tmp_path / "config.json"))
    assert result.returncode == 2
    assert "head_dim=96" in result.stdout
    assert "{32, 64, 128, 256}" in result.stdout


def test_conform_cli_json_output(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "hidden_size": 2048,
                "num_hidden_layers": 22,
                "num_attention_heads": 32,
                "num_key_value_heads": 4,
                "intermediate_size": 5632,
                "vocab_size": 32000,
                "rope_theta": 10000.0,
                "rms_norm_eps": 1e-6,
                "tie_word_embeddings": False,
            }
        )
    )
    out_path = tmp_path / "verdict.json"
    result = _run_conform(str(cfg_path), "--json", str(out_path), "--quiet")
    assert result.returncode == 3  # config-only: tensor facts owe a probe
    verdict = json.loads(out_path.read_text())
    assert verdict["status"] == "supported_pending_probe"
    assert verdict["facts"]["head_dim"] == 64
    # With the qk_norm probe still owed, the d64 steel twin (qk_norm=0 only)
    # is NOT selectable -- a pending probe can never flip the assignment, so
    # selection conservatively takes the both-facts parametric path. The
    # probed d64/qk_norm=0 assignment is fixed by
    # test_d64_qkn0_selects_steel_d64_and_fused_partial.
    assert verdict["assignment"]["prefill_attention"] == "prefill_attention/parametric"
    assert len(verdict["assignment"]["layers"]) == 22


def test_conform_cli_table_prints_capabilities() -> None:
    result = _run_conform("/tmp/unused", "--table")
    assert result.returncode == 0
    assert "prefill_attention/steel_grouped_fa_d128" in result.stdout
    assert "attention_bias" in result.stdout
