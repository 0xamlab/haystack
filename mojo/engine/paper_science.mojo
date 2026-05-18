"""
paper_science.mojo — Paper Science & Pulp Library. Zero Python imports.

Pure Mojo implementations of fundamental paper and pulp science equations
including basis weight, density, bulk, tearing/tensile/burst indices,
freeness, kappa number, pulp yield, moisture, stiffness, and recycled
fiber content.

Public API:
  basis_weight                 — BW = mass/area (g/m², GSM)
  caliper_to_density           — density = BW/(caliper*1000) (g/cm³)
  bulk                         — bulk = caliper*1000/BW (cm³/g)
  tearing_resistance_index     — TI = tear/BW (mN·m²/g)
  tensile_index                — TI = tensile*1000/BW (N·m/g)
  burst_index                  — BI = burst/BW (kPa·m²/g)
  freeness_csf                 — Returns drainage value directly (CSF mL)
  kappa_number_to_lignin       — Lignin% ≈ kappa * 0.15
  pulp_yield                   — Yield = pulp/wood * 100
  moisture_content_paper       — MC = (wet-dry)/wet * 100
  stiffness_index              — SI = stiffness/BW^3 (simplified)
  recycled_fiber_content       — RFC = recycled/total * 100
"""


# ── basis_weight ─────────────────────────────────────────────────────────────


fn basis_weight(mass_g: Float64, area_m2: Float64) -> Float64:
    """BW = mass / area  (g/m², GSM)."""
    return mass_g / area_m2


# ── caliper_to_density ───────────────────────────────────────────────────────


fn caliper_to_density(basis_weight_gsm: Float64, caliper_mm: Float64) -> Float64:
    """Density = BW / (caliper * 1000)  (g/cm³)."""
    return basis_weight_gsm / (caliper_mm * 1000.0)


# ── bulk ─────────────────────────────────────────────────────────────────────


fn bulk(caliper_mm: Float64, basis_weight_gsm: Float64) -> Float64:
    """Bulk = caliper * 1000 / BW  (cm³/g)."""
    return caliper_mm * 1000.0 / basis_weight_gsm


# ── tearing_resistance_index ─────────────────────────────────────────────────


fn tearing_resistance_index(tear_mn: Float64, basis_weight_gsm: Float64) -> Float64:
    """Tearing index = tear / BW  (mN·m²/g)."""
    return tear_mn / basis_weight_gsm


# ── tensile_index ────────────────────────────────────────────────────────────


fn tensile_index(tensile_kn_m: Float64, basis_weight_gsm: Float64) -> Float64:
    """Tensile index = tensile*1000 / BW  (N·m/g)."""
    return tensile_kn_m * 1000.0 / basis_weight_gsm


# ── burst_index ──────────────────────────────────────────────────────────────


fn burst_index(burst_kpa: Float64, basis_weight_gsm: Float64) -> Float64:
    """Burst index = burst / BW  (kPa·m²/g)."""
    return burst_kpa / basis_weight_gsm


# ── freeness_csf ─────────────────────────────────────────────────────────────


fn freeness_csf(drainage_ml: Float64) -> Float64:
    """Returns drainage value directly (CSF mL)."""
    return drainage_ml


# ── kappa_number_to_lignin ───────────────────────────────────────────────────


fn kappa_number_to_lignin(kappa: Float64) -> Float64:
    """Lignin% ≈ kappa * 0.15."""
    return kappa * 0.15


# ── pulp_yield ───────────────────────────────────────────────────────────────


fn pulp_yield(pulp_mass: Float64, wood_mass: Float64) -> Float64:
    """Yield = pulp / wood * 100  (%)."""
    return pulp_mass / wood_mass * 100.0


# ── moisture_content_paper ───────────────────────────────────────────────────


fn moisture_content_paper(wet_mass: Float64, dry_mass: Float64) -> Float64:
    """Moisture content = (wet - dry) / wet * 100  (%)."""
    return (wet_mass - dry_mass) / wet_mass * 100.0


# ── stiffness_index ──────────────────────────────────────────────────────────


fn stiffness_index(bending_stiffness: Float64, basis_weight_gsm: Float64) -> Float64:
    """Stiffness index = stiffness / BW^3  (simplified)."""
    var bw3 = basis_weight_gsm * basis_weight_gsm * basis_weight_gsm
    return bending_stiffness / bw3


# ── recycled_fiber_content ───────────────────────────────────────────────────


fn recycled_fiber_content(recycled: Float64, total: Float64) -> Float64:
    """Recycled fiber content = recycled / total * 100  (%)."""
    return recycled / total * 100.0
