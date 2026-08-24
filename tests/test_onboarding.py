"""The onboarding loop is a pure function of the facts: these tests fix the
decision layer (facts -> per-backend verdict -> staging-gap analysis -> row/
ledger) so a new model is onboarded by the table, never by a name. Unconditional
(no weights, no GPU): the verdicts need only a config declaration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.onboarding import (  # noqa: E402
    backend_staging_ceiling,
    backend_verdicts,
    emit_ledger,
    emit_support_row,
    onboard_facts,
    resolve_config,
    staging_tier_gap,
)


def _supported_config(**overrides) -> dict:
    cfg = {
        "model_type": "llama",
        "hidden_size": 2048,
        "num_hidden_layers": 22,
        "num_attention_heads": 32,
        "num_key_value_heads": 4,
        "intermediate_size": 5632,
        "vocab_size": 32000,
        "rope_theta": 10000.0,
        "rms_norm_eps": 1e-6,
        "tie_word_embeddings": False,
        "hidden_act": "silu",
    }
    cfg.update(overrides)
    return cfg


# ── resolve_config ───────────────────────────────────────────────────────────


def test_resolve_config_local_dir(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps(_supported_config()))
    config, desc, weights = resolve_config(str(tmp_path))
    assert config["hidden_size"] == 2048
    assert desc == str(tmp_path)
    assert weights is None  # no safetensors present


def test_resolve_config_bare_json(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_supported_config()))
    config, desc, weights = resolve_config(str(cfg_path))
    assert config["num_hidden_layers"] == 22
    assert desc == str(cfg_path)
    assert weights is None


def test_resolve_config_lifts_gemma3_wrapper(tmp_path: Path) -> None:
    wrapper = {
        "model_type": "gemma3",
        "text_config": _supported_config(model_type="gemma3_text"),
        "eos_token_id": [106, 107],
    }
    (tmp_path / "config.json").write_text(json.dumps(wrapper))
    config, _, _ = resolve_config(str(tmp_path))
    assert config["model_type"] == "gemma3_text"
    assert config["hidden_size"] == 2048


# ── facts + per-backend verdicts ─────────────────────────────────────────────


def test_backend_verdicts_supported_everywhere() -> None:
    facts = onboard_facts(_supported_config())
    verdicts = backend_verdicts(facts)
    assert set(verdicts) == {"metal", "cuda"}
    for v in verdicts.values():
        assert v.supported
        assert v.refusals == ()


def test_backend_verdicts_silu_refusal_both_backends() -> None:
    facts = onboard_facts(_supported_config(hidden_act="gelu_pytorch_tanh"))
    verdicts = backend_verdicts(facts)
    for backend in ("metal", "cuda"):
        assert verdicts[backend].status == "refused"
        assert any(r.fact == "hidden_act" for r in verdicts[backend].refusals)


def test_backend_verdicts_staging_refuses_metal_only() -> None:
    # d_ff 14336 stages past Metal's tiers but inside CUDA's 18944 tier.
    facts = onboard_facts(_supported_config(intermediate_size=14336))
    verdicts = backend_verdicts(facts)
    assert verdicts["metal"].status == "refused"
    assert any(r.fact == "stage_needed" for r in verdicts["metal"].refusals)
    assert verdicts["cuda"].supported


def test_backend_verdicts_bias_refused_on_metal_supported_cuda() -> None:
    facts = onboard_facts(_supported_config())
    from dataclasses import replace

    facts = replace(facts, attention_bias=1, probed=True)
    verdicts = backend_verdicts(facts)
    assert verdicts["metal"].status == "refused"
    assert any(r.fact == "attention_bias" for r in verdicts["metal"].refusals)
    assert verdicts["cuda"].supported


# ── staging-tier gap analysis ────────────────────────────────────────────────


def test_staging_tier_gap_pure_staging() -> None:
    facts = onboard_facts(_supported_config(intermediate_size=14336))
    assert staging_tier_gap(facts, "metal") == 14336
    # CUDA supports it (fits the 18944 tier), so there is no gap there.
    assert staging_tier_gap(facts, "cuda") is None


def test_staging_tier_gap_not_pure_when_other_refusals() -> None:
    facts = onboard_facts(
        _supported_config(intermediate_size=14336, hidden_act="gelu_pytorch_tanh")
    )
    # Two refusals (activation + staging) -> not a pure staging gap.
    assert staging_tier_gap(facts, "metal") is None


def test_backend_staging_ceiling() -> None:
    assert backend_staging_ceiling("metal") == 6144
    assert backend_staging_ceiling("cuda") > 18944  # the big tiers live on CUDA


# ── row + ledger emission ────────────────────────────────────────────────────


def test_emit_support_row_and_ledger() -> None:
    facts = onboard_facts(_supported_config())
    verdicts = backend_verdicts(facts)
    row = emit_support_row("TestModel", facts, verdicts)
    assert row.startswith("| TestModel |")
    assert "metal: supported" in row and "cuda: supported" in row

    ledger = emit_ledger("TestModel", facts, verdicts)
    assert ledger["model"] == "TestModel"
    assert ledger["facts"]["hidden_size"] == 2048
    assert ledger["verdicts"]["metal"]["status"] in ("supported", "supported_pending_probe")
    assert ledger["verdicts"]["cuda"]["status"] in ("supported", "supported_pending_probe")
    assert ledger["gates"] == {}


def test_emit_support_row_refusal_names_fact() -> None:
    facts = onboard_facts(_supported_config(hidden_act="gelu_pytorch_tanh"))
    verdicts = backend_verdicts(facts)
    row = emit_support_row("GeluModel", facts, verdicts)
    assert "refused" in row
    assert "hidden_act" in row
