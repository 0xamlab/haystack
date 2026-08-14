"""The llama-3.1 "llama3" rope_scaling, verified against an independent reference.

The engine's adjusted rope frequencies (`attnk.rope.rope_inv_freq_llama3`, wired through
`metaldispatch.qwen3_prefill_decode._rope_table_from_manifest`) must reproduce the standard
Hugging Face transformers formula for `rope_scaling.rope_type == "llama3"`:

    inv_freq[i] = theta ** (-2i / head_dim)            (the base frequency of pair i)
    wavelen     = 2*pi / inv_freq[i]
    low_wavelen  = original_max_position_embeddings / low_freq_factor
    high_wavelen = original_max_position_embeddings / high_freq_factor

    wavelen < high_wavelen  -> unchanged               (the high frequencies)
    wavelen > low_wavelen   -> inv_freq[i] / factor    (the low frequencies)
    otherwise               -> (1 - smooth) * inv_freq[i] / factor + smooth * inv_freq[i]
                               with smooth = (original_max_position_embeddings / wavelen
                                              - low_freq_factor) / (high_freq_factor
                                              - low_freq_factor)

`llama3_adjusted_inv_freq` below IS that reference, written independently of the Mojo kernel. The
Mojo half is cross-checked against the SAME golden numbers this reference produces:
`mojo/tests/libs/test_attnk_rope.mojo` hardcodes the values `_REPRESENTATIVE_GOLDEN` carries and
asserts the kernel's output on them (the only tolerance is the pow-libm difference between the
two toolchains, ~1e-11 -- never the formula).

What this file itself verifies:
* the reference formula's own band structure on the representative llama-3.1 config (factor=8,
  low_freq_factor=1, high_freq_factor=4, original_max_position_embeddings=8192);
* the SDK converter's validation (llama3 accepted with HF's default factors filled in; every
  other scheme -- yarn/linear/longrope -- REFUSED, never silently unscaled);
* the flat manifest keys the Mojo entry points read.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.inference import (  # noqa: E402
    UnsupportedArchitectureError,
    _rope_scaling_manifest_entries,
    _validate_rope_scaling,
)

# The task's representative config: llama-3.1-8B's rope scaling (factor 8 from 8192 to ~65k).
_REPRESENTATIVE = {
    "head_dim": 128,
    "theta": 500000.0,
    "factor": 8.0,
    "low_freq_factor": 1.0,
    "high_freq_factor": 4.0,
    "original_max_position_embeddings": 8192,
}


def llama3_adjusted_inv_freq(
    head_dim: int,
    theta: float,
    factor: float,
    low_freq_factor: float,
    high_freq_factor: float,
    original_max_position_embeddings: float,
) -> list[float]:
    """THE Python reference implementation of the standard llama3 frequency adjustment.

    Written from the published formula (HF transformers' LlamaRotaryEmbedding llama3 scaling and
    llama.cpp's convert generate_extra_tensors), independently of the Mojo kernel under test.
    """
    inv_freq = [theta ** (-2.0 * i / head_dim) for i in range(head_dim // 2)]
    low_freq_wavelen = original_max_position_embeddings / low_freq_factor
    high_freq_wavelen = original_max_position_embeddings / high_freq_factor
    adjusted: list[float] = []
    for freq in inv_freq:
        wavelen = 2.0 * math.pi / freq
        if wavelen < high_freq_wavelen:
            adjusted.append(freq)
        elif wavelen > low_freq_wavelen:
            adjusted.append(freq / factor)
        else:
            smooth = (
                original_max_position_embeddings / wavelen - low_freq_factor
            ) / (high_freq_factor - low_freq_factor)
            adjusted.append((1.0 - smooth) * freq / factor + smooth * freq)
    return adjusted


# Golden values for the representative config, produced ONCE by `llama3_adjusted_inv_freq` and
# frozen here so BOTH halves (this reference and the Mojo kernel's test) assert the same numbers.
_REPRESENTATIVE_GOLDEN = llama3_adjusted_inv_freq(**_REPRESENTATIVE)


# --- the reference formula's own structure ------------------------------------------------------


def test_reference_band_structure_on_representative_config() -> None:
    # For head_dim=128 theta=500000 factor=8 low=1 high=4 orig=8192: pairs 0..28 have
    # wavelengths under 8192/4=2048 (unchanged), pairs 35..63 above 8192/1=8192 (divided by 8),
    # pairs 29..34 in between (smoothly interpolated).
    inv = llama3_adjusted_inv_freq(**_REPRESENTATIVE)
    assert len(inv) == 64
    low_wl = _REPRESENTATIVE["original_max_position_embeddings"] / _REPRESENTATIVE["low_freq_factor"]
    high_wl = (
        _REPRESENTATIVE["original_max_position_embeddings"]
        / _REPRESENTATIVE["high_freq_factor"]
    )
    n_unchanged = n_scaled = n_smooth = 0
    for i, freq in enumerate(inv):
        base = _REPRESENTATIVE["theta"] ** (-2.0 * i / _REPRESENTATIVE["head_dim"])
        wavelen = 2.0 * math.pi / base
        if wavelen < high_wl:
            assert freq == base, f"pair {i} should be unchanged"
            n_unchanged += 1
        elif wavelen > low_wl:
            assert freq == base / _REPRESENTATIVE["factor"], f"pair {i} should be factor-scaled"
            n_scaled += 1
        else:
            assert base / _REPRESENTATIVE["factor"] < freq < base, (
                f"pair {i} should sit strictly inside the interpolation"
            )
            n_smooth += 1
    assert (n_unchanged, n_smooth, n_scaled) == (29, 6, 29)


def test_reference_golden_values_are_frozen() -> None:
    # Spot-pin the three bands so an accidental edit of the reference formula trips immediately.
    assert _REPRESENTATIVE_GOLDEN[0] == pytest.approx(1.0, abs=0.0)  # pair 0 is always 1.0
    assert _REPRESENTATIVE_GOLDEN[28] == pytest.approx(3.21144599475259090e-03, rel=1e-15)
    # the first smooth pair
    assert _REPRESENTATIVE_GOLDEN[29] == pytest.approx(2.16657076350335910e-03, rel=1e-15)
    # the first factor-scaled pair == base / 8 exactly
    base35 = _REPRESENTATIVE["theta"] ** (-2.0 * 35 / _REPRESENTATIVE["head_dim"])
    assert _REPRESENTATIVE_GOLDEN[35] == base35 / 8.0
    assert _REPRESENTATIVE_GOLDEN[63] == pytest.approx(3.06892598891451108e-07, rel=1e-15)


def test_reference_degenerate_factor_one_is_identity() -> None:
    plain = [10000.0 ** (-2.0 * i / 8) for i in range(4)]
    adjusted = llama3_adjusted_inv_freq(8, 10000.0, 1.0, 1.0, 4.0, 8192.0)
    assert adjusted == plain  # factor=1 leaves every arm a no-op


# --- the SDK converter's validation + manifest keys ---------------------------------------------


def _config_with_rope_scaling(**scaling) -> dict:
    return {
        "hidden_size": 4096,
        "num_hidden_layers": 32,
        "num_attention_heads": 32,
        "num_key_value_heads": 8,
        "head_dim": 128,
        "intermediate_size": 14336,
        "vocab_size": 128256,
        "rope_theta": 500000.0,
        "rms_norm_eps": 1e-5,
        "rope_scaling": scaling,
    }


def test_llama3_scheme_accepted_and_defaults_filled() -> None:
    config = _config_with_rope_scaling(
        rope_type="llama3",
        factor=8.0,
        low_freq_factor=1.0,
        high_freq_factor=4.0,
        original_max_position_embeddings=8192,
    )
    _validate_rope_scaling(config, config_source="config.json")  # no raise
    entries = _rope_scaling_manifest_entries(config)
    assert entries == {
        "rope_scaling_type": 3,
        "rope_scaling_factor": 8.0,
        "rope_scaling_low_freq_factor": 1.0,
        "rope_scaling_high_freq_factor": 4.0,
        "rope_scaling_original_max_position_embeddings": 8192,
    }


def test_llama3_scheme_with_omitted_factors_uses_hf_defaults() -> None:
    config = _config_with_rope_scaling(
        rope_type="llama3",
        factor=8.0,
        original_max_position_embeddings=8192,
    )
    _validate_rope_scaling(config, config_source="config.json")
    entries = _rope_scaling_manifest_entries(config)
    assert entries["rope_scaling_low_freq_factor"] == 1.0
    assert entries["rope_scaling_high_freq_factor"] == 4.0


def test_legacy_type_key_is_accepted_too() -> None:
    # Some configs use "type" instead of "rope_type".
    config = _config_with_rope_scaling(
        type="llama3",
        factor=8.0,
        original_max_position_embeddings=8192,
    )
    _validate_rope_scaling(config, config_source="config.json")
    assert _rope_scaling_manifest_entries(config)["rope_scaling_type"] == 3


@pytest.mark.parametrize("rope_type", ["yarn", "linear", "longrope", "su", "dynamic"])
def test_unimplemented_schemes_refused_not_silently_unscaled(rope_type: str) -> None:
    config = _config_with_rope_scaling(
        rope_type=rope_type,
        factor=8.0,
        original_max_position_embeddings=8192,
    )
    with pytest.raises(UnsupportedArchitectureError) as excinfo:
        _validate_rope_scaling(config, config_source="config.json")
    assert rope_type in str(excinfo.value)
    assert "llama3" in str(excinfo.value)


@pytest.mark.parametrize(
    "scaling",
    [
        None,  # absent
        {"rope_type": "none"},
        {"type": "none"},
        {},  # no type at all
    ],
)
def test_absent_or_none_scaling_writes_no_manifest_keys(scaling) -> None:
    config = _config_with_rope_scaling()
    if scaling is None:
        config.pop("rope_scaling")
    else:
        config["rope_scaling"] = scaling
    _validate_rope_scaling(config, config_source="config.json")
    assert _rope_scaling_manifest_entries(config) == {}


@pytest.mark.parametrize(
    "bad",
    [
        {"rope_type": "llama3", "original_max_position_embeddings": 8192},  # factor missing
        {"rope_type": "llama3", "factor": -8.0, "original_max_position_embeddings": 8192},
        {"rope_type": "llama3", "factor": 8.0},  # original_max_position_embeddings missing
        {
            "rope_type": "llama3",
            "factor": 8.0,
            "original_max_position_embeddings": 8192,
            "low_freq_factor": 4.0,
            "high_freq_factor": 1.0,  # high <= low -> degenerate interpolation
        },
        {
            "rope_type": "llama3",
            "factor": 8.0,
            "original_max_position_embeddings": 8192,
            "low_freq_factor": 0.0,
        },
    ],
)
def test_degenerate_llama3_configs_refused(bad: dict) -> None:
    config = _config_with_rope_scaling(**bad)
    with pytest.raises(UnsupportedArchitectureError):
        _validate_rope_scaling(config, config_source="config.json")
