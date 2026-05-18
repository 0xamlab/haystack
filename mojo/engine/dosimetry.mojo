"""
dosimetry.mojo — Radiation dose and protection calculations. Zero Python imports.

Public API:
  absorbed_dose                — D = energy_deposited / mass
  equivalent_dose              — H = D * w_R (radiation weighting)
  effective_dose               — E = sum(w_T * H_T)
  dose_rate                    — rate from activity and geometry
  activity_decay               — A(t) = A0 * exp(-lambda*t)
  specific_activity            — A_sp = lambda * N_A / M
  tenth_value_layer            — TVL = HVL / log10(2)
  buildup_factor               — B from linear attenuation
  kerma                        — kinetic energy released per mass
  radiation_weighting          — weighting factor by particle type
"""
from std.math import exp, log, pow


fn absorbed_dose(energy_j: Float64, mass_kg: Float64) -> Float64:
    """Absorbed dose: D = E/m (in Gray).

    Args:
        energy_j: Energy deposited (J).
        mass_kg: Mass of absorbing material (kg).

    Returns:
        Absorbed dose (Gy = J/kg).
    """
    if mass_kg <= 0.0:
        return 0.0
    return energy_j / mass_kg


fn equivalent_dose(absorbed_dose_gy: Float64, radiation_weighting: Float64) -> Float64:
    """Equivalent dose: H = D × w_R.

    Args:
        absorbed_dose_gy: Absorbed dose (Gy).
        radiation_weighting: Radiation weighting factor w_R.

    Returns:
        Equivalent dose (Sv).
    """
    return absorbed_dose_gy * radiation_weighting


fn effective_dose(
    equivalent_dose_sv: Float64, tissue_weighting: Float64
) -> Float64:
    """Effective dose contribution from one tissue: E_T = w_T × H_T.

    Args:
        equivalent_dose_sv: Equivalent dose to tissue T (Sv).
        tissue_weighting: ICRP tissue weighting factor w_T.

    Returns:
        Effective dose contribution (Sv).
    """
    return equivalent_dose_sv * tissue_weighting


fn dose_rate(
    activity_bq: Float64, gamma_constant: Float64, distance_m: Float64
) -> Float64:
    """Dose rate from a point source at distance r.

    Rate = Γ·A / r²  (air kerma rate approximation)

    Args:
        activity_bq: Source activity (Bq).
        gamma_constant: Air kerma rate constant Γ (Gy·m²/Bq/s).
        distance_m: Distance from source (m).

    Returns:
        Dose rate (Gy/s).
    """
    if distance_m <= 0.0:
        return 0.0
    return gamma_constant * activity_bq / (distance_m * distance_m)


fn activity_decay(
    initial_activity: Float64, half_life: Float64, time: Float64
) -> Float64:
    """Radioactive decay: A(t) = A0·exp(-λt), λ = ln2/T½.

    Args:
        initial_activity: Activity at t=0 (Bq).
        half_life: Half-life (same units as time).
        time: Elapsed time.

    Returns:
        Activity at time t (Bq).
    """
    if half_life <= 0.0:
        return 0.0
    var lambda_decay = log(2.0) / half_life
    return initial_activity * exp(-lambda_decay * time)


fn specific_activity(half_life_s: Float64, molar_mass: Float64) -> Float64:
    """Specific activity of a radioisotope: A_sp = ln2·N_A / (T½·M).

    Args:
        half_life_s: Half-life (s).
        molar_mass: Molar mass (g/mol).

    Returns:
        Specific activity (Bq/g).
    """
    if half_life_s <= 0.0 or molar_mass <= 0.0:
        return 0.0
    var na = 6.022e23
    return log(2.0) * na / (half_life_s * molar_mass)


fn tenth_value_layer(hvl: Float64) -> Float64:
    """Tenth value layer from half value layer: TVL = HVL/log10(2) × log10(10).

    TVL = HVL × log(10)/log(2) = HVL × 3.322

    Args:
        hvl: Half value layer (cm, mm, or any length unit).

    Returns:
        TVL (same units).
    """
    return hvl * log(10.0) / log(2.0)


fn buildup_factor(mu: Float64, distance: Float64, b_factor: Float64) -> Float64:
    """Radiation intensity with buildup: I = B·I0·exp(-μx).

    Args:
        mu: Linear attenuation coefficient (cm⁻¹).
        distance: Shielding thickness (cm).
        b_factor: Buildup factor B (≥1.0 for photons in material).

    Returns:
        Relative intensity (I/I0 × B).
    """
    return b_factor * exp(-mu * distance)


fn kerma(
    fluence: Float64, mass_energy_transfer_coeff: Float64
) -> Float64:
    """Kerma from photon fluence: K = Φ·(μtr/ρ).

    Args:
        fluence: Photon fluence (m⁻²).
        mass_energy_transfer_coeff: Mass energy transfer coefficient (m²/kg).

    Returns:
        Kerma (Gy = J/kg).
    """
    return fluence * mass_energy_transfer_coeff


fn radiation_weighting(particle_type_code: Float64) -> Float64:
    """ICRP radiation weighting factor by particle type.

    Codes: 1=photon/electron (w=1), 2=proton (w=2),
           3=alpha (w=20), 4=neutron_fast (w=20), 5=neutron_thermal (w=5)

    Args:
        particle_type_code: Particle type code (1–5).

    Returns:
        Radiation weighting factor w_R.
    """
    if particle_type_code <= 1.5:
        return 1.0    # photons, electrons
    if particle_type_code <= 2.5:
        return 2.0    # protons
    if particle_type_code <= 3.5:
        return 20.0   # alpha particles
    if particle_type_code <= 4.5:
        return 20.0   # fast neutrons
    return 5.0        # thermal neutrons
