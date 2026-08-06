"""
orthodontics.mojo — Dental and orthodontic biomechanics calculations. Zero Python imports.

Public API:
  tooth_movement_rate           — from force and PDL stiffness
  moment_to_force_ratio         — M/F for tooth rotation type
  anchorage_loss_estimate       — reciprocal reaction force
  arch_wire_force               — deflection force from beam theory
  levelling_torque              — bracket-wire torque expression
  bolton_ratio                  — mandibular to maxillary tooth size
  pont_index                    — arch width from tooth sizes
  arch_perimeter_estimate       — Little's irregularity-based
  growth_prediction_cephalometric — skeletal growth from indices
  retainer_force_decay          — viscoelastic force relaxation
"""
from std.math import sqrt, exp, pow


def tooth_movement_rate(
    applied_force_g: Float64, optimal_force_g: Float64
) -> Float64:
    """Expected tooth movement rate relative to optimal force.

    rate_factor = min(F / F_opt, 1)  (optimal ~150-200 g for tipping)

    Args:
        applied_force_g: Applied orthodontic force (grams).
        optimal_force_g: Optimal force for PDL remodelling (grams).

    Returns:
        Rate factor (0–1; 1 = optimal movement ~1 mm/month).
    """
    if optimal_force_g <= 0.0:
        return 0.0
    var ratio = applied_force_g / optimal_force_g
    if ratio > 1.0:
        return 1.0
    return ratio


def moment_to_force_ratio(
    moment_g_mm: Float64, force_g: Float64
) -> Float64:
    """M/F ratio determining type of tooth movement.

    Args:
        moment_g_mm: Applied moment (g·mm).
        force_g: Horizontal/vertical force (g).

    Returns:
        M/F ratio (mm; 0=tipping, 10=translation, ~15=torque).
    """
    if force_g <= 0.0:
        return 0.0
    return moment_g_mm / force_g


def anchorage_loss_estimate(
    reactive_force_g: Float64, anchor_teeth: Float64
) -> Float64:
    """Anchorage unit load per anchor tooth.

    load_per_tooth = reactive_force / n_anchor_teeth

    Args:
        reactive_force_g: Total reactive (anchorage) force (g).
        anchor_teeth: Number of anchor units (teeth).

    Returns:
        Force per anchor tooth (g; <100 g = minimal loss expected).
    """
    if anchor_teeth <= 0.0:
        return 0.0
    return reactive_force_g / anchor_teeth


def arch_wire_force(
    deflection_mm: Float64, wire_diameter_mm: Float64,
    elastic_modulus_gpa: Float64, span_mm: Float64
) -> Float64:
    """3-point bending force for a round wire (Euler beam theory).

    F = 48 × E × I × δ / L³  where I = π d⁴ / 64

    Args:
        deflection_mm: Wire deflection (mm).
        wire_diameter_mm: Wire diameter (mm).
        elastic_modulus_gpa: Young's modulus (GPa; SS ~170, NiTi ~41).
        span_mm: Interbracket span (mm).

    Returns:
        Force (N).
    """
    if span_mm <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    var d_m = wire_diameter_mm * 1e-3
    var I = pi * pow(d_m, 4.0) / 64.0  # m⁴
    var E = elastic_modulus_gpa * 1e9  # Pa
    var L_m = span_mm * 1e-3
    var delta_m = deflection_mm * 1e-3
    return 48.0 * E * I * delta_m / pow(L_m, 3.0)


def levelling_torque(
    third_order_angle_deg: Float64, wire_dimension_mm: Float64,
    elastic_modulus_gpa: Float64, bracket_width_mm: Float64
) -> Float64:
    """Torque expressed from bracket-wire mismatch (simplified).

    T = E × J × θ / L  where J = πd⁴/32 for round or approx for rect

    Args:
        third_order_angle_deg: Angular play between wire and slot (degrees).
        wire_dimension_mm: Wire diameter or edge dimension (mm).
        elastic_modulus_gpa: Elastic modulus (GPa).
        bracket_width_mm: Bracket slot width (mm).

    Returns:
        Torque expression (N·mm).
    """
    var pi = 3.141592653589793
    var theta_rad = third_order_angle_deg * pi / 180.0
    var d_m = wire_dimension_mm * 1e-3
    var J = pi * pow(d_m, 4.0) / 32.0
    var E = elastic_modulus_gpa * 1e9
    var L_m = bracket_width_mm * 1e-3
    if L_m <= 0.0:
        return 0.0
    return E * J * theta_rad / L_m * 1000.0  # convert to N·mm


def bolton_ratio(
    mandibular_sum_mm: Float64, maxillary_sum_mm: Float64
) -> Float64:
    """Bolton overall tooth-size ratio (6 anterior teeth).

    ratio = lower_sum / upper_sum × 100

    Args:
        mandibular_sum_mm: Sum of 6 lower anterior mesiodistal widths (mm).
        maxillary_sum_mm: Sum of 6 upper anterior widths (mm).

    Returns:
        Bolton ratio (%; ideal ~77.2%).
    """
    if maxillary_sum_mm <= 0.0:
        return 0.0
    return mandibular_sum_mm / maxillary_sum_mm * 100.0


def pont_index(
    upper_four_premolars_sum_mm: Float64, region: Float64
) -> Float64:
    """Pont's index: predicted arch width at premolars or molars.

    W_premolar = sum × 100 / 80  (premolar = 80, molar = 64)

    Args:
        upper_four_premolars_sum_mm: Sum of four upper incisors (mm).
        region: 0 for premolar region, 1 for molar region.

    Returns:
        Predicted transverse arch width (mm).
    """
    var factor = 80.0
    if region > 0.5:
        factor = 64.0
    return upper_four_premolars_sum_mm * 100.0 / factor


def arch_perimeter_estimate(
    irregularity_index_mm: Float64, available_space_mm: Float64
) -> Float64:
    """Required arch perimeter from Little's irregularity index.

    required = available + irregularity_index

    Args:
        irregularity_index_mm: Little's irregularity index (mm).
        available_space_mm: Available arch perimeter (mm).

    Returns:
        Required arch perimeter (mm).
    """
    return available_space_mm + irregularity_index_mm


def growth_prediction_cephalometric(
    sna_deg: Float64, snb_deg: Float64, ans_pns_mm: Float64
) -> Float64:
    """Skeletal growth pattern index from cephalometric landmarks.

    Wits_approx = SNA - SNB - (ANS-PNS / 10)

    Args:
        sna_deg: SNA angle (°; normal 82°).
        snb_deg: SNB angle (°; normal 80°).
        ans_pns_mm: ANS-PNS palatal plane length (mm).

    Returns:
        Skeletal discrepancy index (mm equivalent).
    """
    return sna_deg - snb_deg - ans_pns_mm / 10.0


def retainer_force_decay(
    initial_force_g: Float64, time_weeks: Float64, decay_constant: Float64
) -> Float64:
    """Viscoelastic force relaxation in orthodontic retainers/elastics.

    F(t) = F0 × exp(-k × t)

    Args:
        initial_force_g: Initial elastic force (g).
        time_weeks: Elapsed time (weeks).
        decay_constant: Viscoelastic decay constant k (per week).

    Returns:
        Remaining force (g).
    """
    return initial_force_g * exp(-decay_constant * time_weeks)
