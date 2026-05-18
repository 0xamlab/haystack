"""
water_chemistry.mojo — Water quality and chemistry calculations. Zero Python imports.

Public API:
  ph_from_hydrogen_ion         — pH = -log10([H+])
  hydrogen_ion_from_ph         — [H+] = 10^(-pH)
  water_hardness               — hardness in mg/L CaCO3
  alkalinity_as_caco3          — total alkalinity conversion
  langelier_saturation_index   — LSI for scale/corrosion tendency
  turbidity_ntu_to_sdd         — approximate Secchi depth from NTU
  chlorine_demand              — breakpoint chlorination residual
  dissolved_oxygen_deficit     — oxygen deficit from saturation
  conductivity_tds             — TDS from electrical conductivity
  bod_removal                  — BOD removal efficiency
"""
from std.math import log, exp, pow


fn _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


fn ph_from_hydrogen_ion(h_concentration: Float64) -> Float64:
    """pH from hydrogen ion concentration.

    pH = -log10([H+])

    Args:
        h_concentration: [H+] concentration (mol/L).

    Returns:
        pH value.
    """
    if h_concentration <= 0.0:
        return 14.0
    return -_log10(h_concentration)


fn hydrogen_ion_from_ph(ph: Float64) -> Float64:
    """[H+] from pH value: [H+] = 10^(-pH).

    Args:
        ph: pH value.

    Returns:
        Hydrogen ion concentration (mol/L).
    """
    return pow(10.0, -ph)


fn water_hardness(
    calcium_mg_l: Float64, magnesium_mg_l: Float64
) -> Float64:
    """Total hardness as CaCO3 equivalent.

    Hardness (mg/L CaCO3) = 2.5·[Ca²+] + 4.12·[Mg²+]

    Args:
        calcium_mg_l: Calcium concentration (mg/L).
        magnesium_mg_l: Magnesium concentration (mg/L).

    Returns:
        Total hardness (mg/L as CaCO3).
    """
    return 2.497 * calcium_mg_l + 4.118 * magnesium_mg_l


fn alkalinity_as_caco3(
    bicarbonate_mg_l: Float64, carbonate_mg_l: Float64, hydroxide_mg_l: Float64
) -> Float64:
    """Total alkalinity as CaCO3.

    Alk (mg/L CaCO3) = 0.82·HCO3⁻ + 1.67·CO3²⁻ + 2.94·OH⁻

    Args:
        bicarbonate_mg_l: HCO3⁻ (mg/L).
        carbonate_mg_l: CO3²⁻ (mg/L).
        hydroxide_mg_l: OH⁻ (mg/L).

    Returns:
        Total alkalinity (mg/L as CaCO3).
    """
    return 0.82 * bicarbonate_mg_l + 1.67 * carbonate_mg_l + 2.94 * hydroxide_mg_l


fn langelier_saturation_index(
    ph: Float64, ph_saturation: Float64
) -> Float64:
    """Langelier Saturation Index: LSI = pH - pHs.

    Args:
        ph: Actual measured pH.
        ph_saturation: Saturation pH (where CaCO3 is neither deposited nor dissolved).

    Returns:
        LSI. Positive = scale-forming, negative = corrosive.
    """
    return ph - ph_saturation


fn turbidity_ntu_to_sdd(turbidity_ntu: Float64) -> Float64:
    """Estimate Secchi disk depth from turbidity.

    Approximate empirical relationship: SDD ≈ 1.13 / NTU^0.59

    Args:
        turbidity_ntu: Turbidity (NTU).

    Returns:
        Estimated Secchi disk depth (m).
    """
    if turbidity_ntu <= 0.0:
        return 10.0
    return 1.13 / pow(turbidity_ntu, 0.59)


fn chlorine_demand(
    chlorine_applied: Float64, chlorine_residual: Float64
) -> Float64:
    """Chlorine demand of a water sample.

    Demand = Cl_applied - Cl_residual

    Args:
        chlorine_applied: Chlorine dose (mg/L).
        chlorine_residual: Residual free chlorine (mg/L).

    Returns:
        Chlorine demand (mg/L).
    """
    var demand = chlorine_applied - chlorine_residual
    if demand < 0.0:
        return 0.0
    return demand


fn dissolved_oxygen_deficit(do_saturation: Float64, do_actual: Float64) -> Float64:
    """Dissolved oxygen deficit from saturation.

    D = DO_sat - DO_actual

    Args:
        do_saturation: DO saturation at ambient T (mg/L).
        do_actual: Measured DO (mg/L).

    Returns:
        Oxygen deficit (mg/L). Positive = under-saturated.
    """
    var deficit = do_saturation - do_actual
    if deficit < 0.0:
        return 0.0
    return deficit


fn conductivity_tds(conductivity_us_cm: Float64, conversion_factor: Float64) -> Float64:
    """Total dissolved solids estimate from electrical conductivity.

    TDS = EC × f  (f typically 0.55–0.75)

    Args:
        conductivity_us_cm: Electrical conductivity (μS/cm).
        conversion_factor: Empirical TDS/EC conversion (mg/L per μS/cm).

    Returns:
        TDS (mg/L).
    """
    if conductivity_us_cm < 0.0 or conversion_factor < 0.0:
        return 0.0
    return conductivity_us_cm * conversion_factor


fn bod_removal(
    influent_bod: Float64, effluent_bod: Float64
) -> Float64:
    """BOD removal efficiency of a treatment system.

    E = (BOD_in - BOD_out) / BOD_in × 100

    Args:
        influent_bod: Influent BOD (mg/L).
        effluent_bod: Effluent BOD (mg/L).

    Returns:
        Removal efficiency (%).
    """
    if influent_bod <= 0.0:
        return 0.0
    var removal = (influent_bod - effluent_bod) / influent_bod * 100.0
    if removal < 0.0:
        return 0.0
    return removal
