"""
phytochemistry.mojo — Plant secondary metabolite calculations. Zero Python imports.

Public API:
  phenolic_content_folin        — GAE from Folin-Ciocalteu absorbance
  flavonoid_content             — QE from AlCl3 method
  anthocyanin_concentration     — pH differential method
  tannin_content                — precipitable tannins from protein binding
  essential_oil_yield           — EO% from distillation
  alkaloid_gravimetric          — alkaloid% from crude extract
  chlorophyll_a                 — from spectrophotometric absorbance
  chlorophyll_b                 — from spectrophotometric absorbance
  carotenoid_content            — from hexane extract absorbance
  dpph_radical_scavenging       — IC50 from dose-response
"""
from std.math import log, exp, pow


def phenolic_content_folin(
    absorbance: Float64, slope: Float64, intercept: Float64, dilution: Float64
) -> Float64:
    """Total phenolic content by Folin-Ciocalteu: TPC = (A - b) / m × dilution.

    Args:
        absorbance: Absorbance at 765 nm.
        slope: Calibration curve slope (GAE per AU).
        intercept: Calibration intercept.
        dilution: Sample dilution factor.

    Returns:
        Total phenolics (mg GAE/g extract).
    """
    if slope <= 0.0:
        return 0.0
    return (absorbance - intercept) / slope * dilution


def flavonoid_content(
    absorbance: Float64, slope: Float64, intercept: Float64, dilution: Float64
) -> Float64:
    """Total flavonoid content (AlCl3 method).

    Args:
        absorbance: Absorbance at 510 nm.
        slope: Calibration slope (QE per AU).
        intercept: Calibration intercept.
        dilution: Dilution factor.

    Returns:
        Flavonoid content (mg QE/g extract).
    """
    if slope <= 0.0:
        return 0.0
    return (absorbance - intercept) / slope * dilution


def anthocyanin_concentration(
    abs_ph1: Float64, abs_ph45: Float64,
    epsilon: Float64, mw: Float64, path_cm: Float64, dilution: Float64
) -> Float64:
    """Monomeric anthocyanin by pH differential: C = ΔA × MW / (ε × l) × df.

    Args:
        abs_ph1: ΔA = (A520 - A700) at pH 1.0.
        abs_ph45: ΔA = (A520 - A700) at pH 4.5.
        epsilon: Molar absorptivity (L/mol/cm).
        mw: Molecular weight (g/mol, e.g. 449.2 for cyanidin-3-glucoside).
        path_cm: Path length (cm).
        dilution: Dilution factor.

    Returns:
        Anthocyanin concentration (mg/L).
    """
    var delta_a = abs_ph1 - abs_ph45
    if epsilon <= 0.0 or path_cm <= 0.0:
        return 0.0
    return delta_a * mw / (epsilon * path_cm) * dilution * 1000.0


def tannin_content(
    total_phenolics: Float64, non_tannin_phenolics: Float64
) -> Float64:
    """Condensed tannin content by difference method.

    Args:
        total_phenolics: TPC before PVPP treatment (mg TAE/g).
        non_tannin_phenolics: TPC after PVPP absorption (mg TAE/g).

    Returns:
        Tannin content (mg TAE/g).
    """
    var t = total_phenolics - non_tannin_phenolics
    if t < 0.0:
        return 0.0
    return t


def essential_oil_yield(
    oil_volume_ml: Float64, plant_mass_g: Float64
) -> Float64:
    """Essential oil yield by hydrodistillation.

    Args:
        oil_volume_ml: Volume of oil collected (mL).
        plant_mass_g: Mass of plant material (g, dry weight).

    Returns:
        Essential oil yield (% v/w).
    """
    if plant_mass_g <= 0.0:
        return 0.0
    return oil_volume_ml / plant_mass_g * 100.0


def alkaloid_gravimetric(
    alkaloid_mass_mg: Float64, extract_mass_mg: Float64
) -> Float64:
    """Total alkaloid content by gravimetric method.

    Args:
        alkaloid_mass_mg: Mass of precipitated alkaloids (mg).
        extract_mass_mg: Mass of crude extract (mg).

    Returns:
        Alkaloid content (% w/w).
    """
    if extract_mass_mg <= 0.0:
        return 0.0
    return alkaloid_mass_mg / extract_mass_mg * 100.0


def chlorophyll_a(abs_663: Float64, abs_646: Float64) -> Float64:
    """Chlorophyll a concentration (Lichtenthaler 1987).

    Chl a = 12.21·A663 - 2.81·A646  (μg/mL in 80% acetone)

    Args:
        abs_663: Absorbance at 663 nm.
        abs_646: Absorbance at 646 nm.

    Returns:
        Chlorophyll a (μg/mL).
    """
    return 12.21 * abs_663 - 2.81 * abs_646


def chlorophyll_b(abs_663: Float64, abs_646: Float64) -> Float64:
    """Chlorophyll b concentration (Lichtenthaler 1987).

    Chl b = 20.13·A646 - 5.03·A663

    Args:
        abs_663: Absorbance at 663 nm.
        abs_646: Absorbance at 646 nm.

    Returns:
        Chlorophyll b (μg/mL).
    """
    return 20.13 * abs_646 - 5.03 * abs_663


def carotenoid_content(abs_470: Float64, chl_a: Float64, chl_b: Float64) -> Float64:
    """Total carotenoids (Lichtenthaler 1987).

    Cx+c = (1000·A470 - 3.27·Chl_a - 104·Chl_b) / 229

    Args:
        abs_470: Absorbance at 470 nm.
        chl_a: Chlorophyll a concentration (μg/mL).
        chl_b: Chlorophyll b concentration (μg/mL).

    Returns:
        Total carotenoids (μg/mL).
    """
    var cx = (1000.0 * abs_470 - 3.27 * chl_a - 104.0 * chl_b) / 229.0
    if cx < 0.0:
        return 0.0
    return cx


def dpph_radical_scavenging(
    abs_control: Float64, abs_sample: Float64
) -> Float64:
    """DPPH radical scavenging activity.

    % inhibition = (A_control - A_sample) / A_control × 100

    Args:
        abs_control: Absorbance of DPPH control at 517 nm.
        abs_sample: Absorbance after adding antioxidant.

    Returns:
        % radical scavenging activity.
    """
    if abs_control <= 0.0:
        return 0.0
    return (abs_control - abs_sample) / abs_control * 100.0
