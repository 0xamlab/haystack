"""
polymer.mojo — Polymer Science Library. Zero Python imports.

Pure Mojo implementations of fundamental polymer science equations
including molecular weight averages, polydispersity, intrinsic viscosity,
glass transition blending, Flory-Huggins thermodynamics, chain dimensions,
and composite mechanics.

Public API:
  degree_of_polymerization         — DP = Mn / M0
  number_average_mw                — Mn = DP * M0
  weight_average_mw                — Mw = Mn * PDI
  polydispersity_index             — PDI = Mw / Mn
  mark_houwink                     — [η] = K * M^a
  glass_transition_fox             — 1/Tg = w1/Tg1 + w2/Tg2
  flory_huggins_free_energy        — ΔG/kT blend free energy
  end_to_end_distance              — R = l*sqrt(n) freely jointed chain
  radius_of_gyration               — Rg = R/sqrt(6)
  carothers_conversion             — p = 1 - 1/DP
  melt_flow_index_approx           — MFI ∝ shear/η (simplified)
  tensile_modulus_rule_of_mixtures  — E = Vf*Ef + (1-Vf)*Em
"""
from std.math import sqrt, exp, log, abs as fabs


# ── degree_of_polymerization ─────────────────────────────────────────────────


def degree_of_polymerization(mn: Float64, m0: Float64) -> Float64:
    """DP = Mn / M0 (number-average MW / monomer MW)."""
    if m0 == 0.0:
        return 0.0
    return mn / m0


# ── number_average_mw ────────────────────────────────────────────────────────


def number_average_mw(dp: Float64, m0: Float64) -> Float64:
    """Mn = DP * M0."""
    return dp * m0


# ── weight_average_mw ────────────────────────────────────────────────────────


def weight_average_mw(mn: Float64, pdi: Float64) -> Float64:
    """Mw = Mn * PDI."""
    return mn * pdi


# ── polydispersity_index ─────────────────────────────────────────────────────


def polydispersity_index(mw: Float64, mn: Float64) -> Float64:
    """PDI = Mw / Mn."""
    if mn == 0.0:
        return 0.0
    return mw / mn


# ── mark_houwink ─────────────────────────────────────────────────────────────


def mark_houwink(k: Float64, mw: Float64, a: Float64) -> Float64:
    """[η] = K * M^a  (intrinsic viscosity via Mark-Houwink equation).
    Uses exp(a * log(M)) for fractional power."""
    if mw <= 0.0:
        return 0.0
    return k * exp(a * log(mw))


# ── glass_transition_fox ─────────────────────────────────────────────────────


def glass_transition_fox(
    w1: Float64, tg1: Float64, w2: Float64, tg2: Float64
) -> Float64:
    """1/Tg = w1/Tg1 + w2/Tg2  (Fox equation for polymer blends).
    Tg values in Kelvin."""
    if tg1 == 0.0 or tg2 == 0.0:
        return 0.0
    var inv_tg = w1 / tg1 + w2 / tg2
    if inv_tg == 0.0:
        return 0.0
    return 1.0 / inv_tg


# ── flory_huggins_free_energy ────────────────────────────────────────────────


def flory_huggins_free_energy(
    phi: Float64, n: Float64, chi: Float64
) -> Float64:
    """ΔG/kT = phi*ln(phi)/n + (1-phi)*ln(1-phi) + chi*phi*(1-phi).
    phi = volume fraction of polymer, n = degree of polymerization,
    chi = Flory-Huggins interaction parameter."""
    if phi <= 0.0 or phi >= 1.0 or n == 0.0:
        return 0.0
    var term1 = phi * log(phi) / n
    var term2 = (1.0 - phi) * log(1.0 - phi)
    var term3 = chi * phi * (1.0 - phi)
    return term1 + term2 + term3


# ── end_to_end_distance ─────────────────────────────────────────────────────


def end_to_end_distance(n_bonds: Float64, bond_length: Float64) -> Float64:
    """R = l * sqrt(n)  (freely jointed chain model)."""
    if n_bonds <= 0.0:
        return 0.0
    return bond_length * sqrt(n_bonds)


# ── radius_of_gyration ──────────────────────────────────────────────────────


def radius_of_gyration(r_end: Float64) -> Float64:
    """Rg = R / sqrt(6)."""
    return r_end / sqrt(6.0)


# ── carothers_conversion ────────────────────────────────────────────────────


def carothers_conversion(dp: Float64) -> Float64:
    """p = 1 - 1/DP  (Carothers equation for conversion)."""
    if dp == 0.0:
        return 0.0
    return 1.0 - 1.0 / dp


# ── melt_flow_index_approx ─────────────────────────────────────────────────


def melt_flow_index_approx(
    viscosity: Float64, shear_rate: Float64
) -> Float64:
    """MFI ∝ shear_rate / viscosity  (simplified approximation)."""
    if viscosity == 0.0:
        return 0.0
    return shear_rate / viscosity


# ── tensile_modulus_rule_of_mixtures ────────────────────────────────────────


def tensile_modulus_rule_of_mixtures(
    vf: Float64, ef: Float64, em: Float64
) -> Float64:
    """E = Vf*Ef + (1-Vf)*Em  (rule of mixtures for fiber composites)."""
    return vf * ef + (1.0 - vf) * em
