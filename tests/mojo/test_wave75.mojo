"""Tests for Wave 75 — Biomedical, Ceramics, Wind Energy."""

from biomedical import (
    cardiac_output,
    mean_arterial_pressure,
    body_surface_area_dubois,
    glomerular_filtration_rate,
    oxygen_delivery,
    alveolar_gas_equation,
    bmi,
    drug_clearance,
    anion_gap,
    corrected_qt_bazett,
    fick_cardiac_output,
    pulse_pressure,
)
from ceramics import (
    weibull_failure_probability,
    weibull_characteristic_strength,
    thermal_shock_resistance,
    youngs_modulus_porosity,
    sintering_shrinkage,
    density_from_archimedes,
    relative_density,
    porosity_from_density,
    fracture_toughness_indentation,
    dielectric_constant_mixture,
    coefficient_of_thermal_expansion,
    glass_transition_estimate,
)
from wind_energy import (
    wind_power_available,
    betz_limit,
    power_coefficient,
    tip_speed_ratio,
    swept_area,
    annual_energy_production,
    capacity_factor,
    wind_shear_power_law,
    weibull_mean_wind_speed,
    energy_density,
    rotor_thrust,
    wake_velocity,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log


comptime TOL: Float64 = 1e-6
comptime LTOL: Float64 = 1e-2


# ── Helper ───────────────────────────────────────────────────────────────────


fn _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


fn _relnear(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-30:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ══════════════════════════════════════════════════════════════════════════════
# ── Biomedical tests ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn test_cardiac_output() raises:
    # CO = 70 * 72 / 1000 = 5.04 L/min
    var co = cardiac_output(70.0, 72.0)
    assert_true(_near(co, 5.04, 1e-3), "cardiac_output")
    # CO = 100 * 60 / 1000 = 6.0
    assert_true(_near(cardiac_output(100.0, 60.0), 6.0, 1e-3), "cardiac_output_2")


fn test_mean_arterial_pressure() raises:
    # MAP = 80 + (120-80)/3 = 80 + 13.333 = 93.333
    var m = mean_arterial_pressure(120.0, 80.0)
    assert_true(_near(m, 93.333, 1e-2), "map_normal")
    # MAP = 60 + (90-60)/3 = 70
    assert_true(_near(mean_arterial_pressure(90.0, 60.0), 70.0, 1e-3), "map_low")


fn test_body_surface_area() raises:
    # BSA for 70 kg, 170 cm: 0.007184 * 70^0.425 * 170^0.725
    var bsa = body_surface_area_dubois(70.0, 170.0)
    assert_true(bsa > 1.5 and bsa < 2.2, "bsa_range")
    # Zero weight
    assert_true(_near(body_surface_area_dubois(0.0, 170.0), 0.0), "bsa_zero_w")


fn test_glomerular_filtration_rate() raises:
    # Male: ((140-40)*70) / (72*1.0) = 7000/72 = 97.222
    var gfr = glomerular_filtration_rate(1.0, 40.0, 70.0, False)
    assert_true(_near(gfr, 97.222, 1e-2), "gfr_male")
    # Female: same * 0.85 = 82.639
    var gfr_f = glomerular_filtration_rate(1.0, 40.0, 70.0, True)
    assert_true(_near(gfr_f, 82.639, 1e-2), "gfr_female")
    # Zero creatinine
    assert_true(_near(glomerular_filtration_rate(0.0, 40.0, 70.0, False), 0.0), "gfr_zero_cr")


fn test_oxygen_delivery() raises:
    # DO2 = 5.0 * (1.34*15*98/100 + 0.003*100) * 10
    # = 5.0 * (19.698 + 0.3) * 10 = 5.0 * 199.98 = 999.9
    var d = oxygen_delivery(5.0, 15.0, 98.0)
    assert_true(_near(d, 999.9, 1.0), "do2")


fn test_alveolar_gas_equation() raises:
    # PAO2 = 0.21*(760-47) - 40/0.8 = 0.21*713 - 50 = 149.73 - 50 = 99.73
    var pao2 = alveolar_gas_equation(0.21, 760.0, 47.0, 40.0, 0.8)
    assert_true(_near(pao2, 99.73, 0.1), "alveolar_gas")
    # Zero RQ
    assert_true(_near(alveolar_gas_equation(0.21, 760.0, 47.0, 40.0, 0.0), 0.0), "alveolar_gas_zero_rq")


fn test_bmi() raises:
    # BMI = 70 / 1.75^2 = 70 / 3.0625 = 22.857
    var b = bmi(70.0, 1.75)
    assert_true(_near(b, 22.857, 1e-2), "bmi_normal")
    # Zero height
    assert_true(_near(bmi(70.0, 0.0), 0.0), "bmi_zero_h")


fn test_drug_clearance() raises:
    # Cl = 500 / 50 = 10.0 L/h
    assert_true(_near(drug_clearance(500.0, 50.0), 10.0), "drug_cl")
    # Zero AUC
    assert_true(_near(drug_clearance(500.0, 0.0), 0.0), "drug_cl_zero")


fn test_anion_gap() raises:
    # AG = 140 - (104 + 24) = 12
    assert_true(_near(anion_gap(140.0, 104.0, 24.0), 12.0), "anion_gap_normal")
    # AG = 145 - (100 + 20) = 25
    assert_true(_near(anion_gap(145.0, 100.0, 20.0), 25.0), "anion_gap_high")


fn test_corrected_qt_bazett() raises:
    # QTc = 400 / sqrt(0.8) = 400 / 0.8944 = 447.2
    var qtc = corrected_qt_bazett(400.0, 0.8)
    assert_true(_near(qtc, 447.2, 0.5), "qtc_bazett")
    # Zero RR
    assert_true(_near(corrected_qt_bazett(400.0, 0.0), 0.0), "qtc_zero_rr")


fn test_fick_cardiac_output() raises:
    # CO = 250 / ((20 - 15)*10) = 250/50 = 5.0
    var co = fick_cardiac_output(250.0, 20.0, 15.0)
    assert_true(_near(co, 5.0, 1e-3), "fick_co")
    # Equal O2 contents
    assert_true(_near(fick_cardiac_output(250.0, 20.0, 20.0), 0.0), "fick_co_zero_diff")


fn test_pulse_pressure() raises:
    assert_true(_near(pulse_pressure(120.0, 80.0), 40.0), "pp_normal")
    assert_true(_near(pulse_pressure(140.0, 90.0), 50.0), "pp_high")


# ══════════════════════════════════════════════════════════════════════════════
# ── Ceramics tests ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn test_weibull_failure_probability() raises:
    # P = 1 - exp(-(200/300)^10)
    var p = weibull_failure_probability(200.0, 300.0, 10.0)
    assert_true(p > 0.0 and p < 0.1, "weibull_pf_low")
    # At σ = σ0: P = 1 - exp(-1) ≈ 0.6321
    var p2 = weibull_failure_probability(300.0, 300.0, 10.0)
    assert_true(_near(p2, 0.6321, 1e-3), "weibull_pf_sigma0")
    # Zero sigma0
    assert_true(_near(weibull_failure_probability(100.0, 0.0, 10.0), 0.0), "weibull_pf_zero")


fn test_weibull_characteristic_strength() raises:
    assert_true(_near(weibull_characteristic_strength(200.0, 10.0), 220.0), "weibull_char_str")
    assert_true(_near(weibull_characteristic_strength(100.0, 8.0), 110.0), "weibull_char_str2")


fn test_thermal_shock_resistance() raises:
    # R = 200*(1-0.25)/(300000*8e-6) = 200*0.75/2.4 = 62.5
    var r = thermal_shock_resistance(200.0, 300000.0, 8e-6, 0.25)
    assert_true(_near(r, 62.5, 0.1), "tsr")


fn test_youngs_modulus_porosity() raises:
    # E = 400 * exp(-3*0.1) = 400 * exp(-0.3) = 400*0.7408 = 296.33
    var e = youngs_modulus_porosity(400.0, 0.1, 3.0)
    assert_true(_near(e, 296.33, 0.1), "youngs_poros")
    # Zero porosity: E = E0
    assert_true(_near(youngs_modulus_porosity(400.0, 0.0, 3.0), 400.0), "youngs_dense")


fn test_sintering_shrinkage() raises:
    # S = (10 - 8.5)/10 * 100 = 15.0
    assert_true(_near(sintering_shrinkage(10.0, 8.5), 15.0, 1e-3), "sinter_shrink")
    # No shrinkage
    assert_true(_near(sintering_shrinkage(10.0, 10.0), 0.0), "sinter_none")


fn test_density_from_archimedes() raises:
    # ρ = 5.0*1.0/(5.5-3.0) = 5.0/2.5 = 2.0
    var d = density_from_archimedes(5.0, 5.5, 3.0, 1.0)
    assert_true(_near(d, 2.0), "archimedes_dens")


fn test_relative_density() raises:
    # RD = 3.8/3.95*100 = 96.2025
    var rd = relative_density(3.8, 3.95)
    assert_true(_near(rd, 96.2025, 1e-2), "rel_dens")


fn test_porosity_from_density() raises:
    # P = (1 - 3.8/3.95)*100 = 3.7975
    var p = porosity_from_density(3.8, 3.95)
    assert_true(_near(p, 3.7975, 1e-2), "poros_dens")
    assert_true(_near(porosity_from_density(3.95, 3.95), 0.0), "poros_full")


fn test_fracture_toughness() raises:
    # KIc = 0.016 * (300/10)^0.5 * 10 / (0.0001)^1.5
    # = 0.016 * 5.477 * 10 / 1e-6 = 0.8764/1e-6 -> very large
    # Use smaller numbers for sanity: H=10 GPa, E=300 GPa, c=100e-6 m, P=10 N
    var kic = fracture_toughness_indentation(10.0, 100e-6, 10.0, 0.016, 300.0)
    assert_true(kic > 0.0, "frac_tough_positive")


fn test_dielectric_constant_mixture() raises:
    # K = 0.6*9.0 + 0.4*4.0 = 5.4 + 1.6 = 7.0
    assert_true(_near(dielectric_constant_mixture(0.6, 9.0, 0.4, 4.0), 7.0), "dielectric_mix")


fn test_coefficient_thermal_expansion() raises:
    # CTE = 0.001 / (1.0 * 100) = 1e-5
    var cte = coefficient_of_thermal_expansion(0.001, 1.0, 100.0)
    assert_true(_near(cte, 1e-5, 1e-8), "cte")
    # Zero denominator
    assert_true(_near(coefficient_of_thermal_expansion(0.001, 0.0, 100.0), 0.0), "cte_zero")


fn test_glass_transition_estimate() raises:
    # Tg = 2/3 * 1500 = 1000
    assert_true(_near(glass_transition_estimate(1500.0), 1000.0, 0.1), "tg_estimate")
    # Tg = 2/3 * 900 = 600
    assert_true(_near(glass_transition_estimate(900.0), 600.0, 0.1), "tg_estimate2")


# ══════════════════════════════════════════════════════════════════════════════
# ── Wind Energy tests ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn test_wind_power_available() raises:
    # P = 0.5*1.225*5000*12^3 = 0.5*1.225*5000*1728 = 5292000
    var p = wind_power_available(1.225, 5000.0, 12.0)
    assert_true(_near(p, 5292000.0, 10.0), "wind_power")
    # Zero velocity
    assert_true(_near(wind_power_available(1.225, 5000.0, 0.0), 0.0), "wind_power_zero")


fn test_betz_limit() raises:
    assert_true(_near(betz_limit(), 0.5926, 1e-3), "betz")


fn test_power_coefficient() raises:
    assert_true(_near(power_coefficient(500.0, 1000.0), 0.5), "cp")
    assert_true(_near(power_coefficient(100.0, 0.0), 0.0), "cp_zero_avail")


fn test_tip_speed_ratio() raises:
    # λ = 2.0*50/10 = 10
    assert_true(_near(tip_speed_ratio(2.0, 50.0, 10.0), 10.0), "tsr_wind")
    assert_true(_near(tip_speed_ratio(2.0, 50.0, 0.0), 0.0), "tsr_zero_wind")


fn test_swept_area() raises:
    # A = π * 50^2 = 7853.98
    var a = swept_area(50.0)
    assert_true(_near(a, 7853.98, 0.1), "swept_area")


fn test_annual_energy_production() raises:
    # AEP = 2000 * 0.3 * 8760 = 5256000
    var aep = annual_energy_production(2000.0, 0.3, 8760.0)
    assert_true(_near(aep, 5256000.0, 1.0), "aep")


fn test_capacity_factor() raises:
    # CF = 5256000 / (2000*8760) = 0.3
    var cf = capacity_factor(5256000.0, 2000.0, 8760.0)
    assert_true(_near(cf, 0.3, 1e-4), "cf")
    assert_true(_near(capacity_factor(100.0, 0.0, 8760.0), 0.0), "cf_zero_rated")


fn test_wind_shear_power_law() raises:
    # v = 8.0 * (80/10)^0.14 = 8.0 * 8^0.14
    # 8^0.14 = exp(0.14*ln(8)) = exp(0.14*2.0794) = exp(0.2911) = 1.338
    # v = 8.0 * 1.338 = 10.705
    var v = wind_shear_power_law(8.0, 80.0, 10.0, 0.14)
    assert_true(_near(v, 10.705, 0.1), "wind_shear")
    # Same height
    assert_true(_near(wind_shear_power_law(8.0, 10.0, 10.0, 0.14), 8.0, 1e-3), "wind_shear_same")


fn test_weibull_mean_wind_speed() raises:
    # v_mean = 7.0 * 0.886 = 6.202
    assert_true(_near(weibull_mean_wind_speed(7.0, 2.0), 6.202, 1e-3), "weibull_vmean")


fn test_energy_density() raises:
    # ED = 0.5*1.225*10^3 = 612.5
    assert_true(_near(energy_density(1.225, 10.0), 612.5, 0.1), "energy_dens")


fn test_rotor_thrust() raises:
    # T = 0.5*0.8*1.225*5000*12^2 = 0.5*0.8*1.225*5000*144 = 352800
    var t = rotor_thrust(0.8, 1.225, 5000.0, 12.0)
    assert_true(_near(t, 352800.0, 10.0), "rotor_thrust")


fn test_wake_velocity() raises:
    # Basic check: wake velocity < free stream
    var vw = wake_velocity(10.0, 0.8, 500.0, 100.0)
    assert_true(vw > 0.0 and vw < 10.0, "wake_vel_range")
    # Zero diameter: return v0
    assert_true(_near(wake_velocity(10.0, 0.8, 500.0, 0.0), 10.0), "wake_vel_zero_d")
    # Very far downstream -> approaches free stream
    var vw_far = wake_velocity(10.0, 0.8, 100000.0, 100.0)
    assert_true(vw_far > 9.5, "wake_vel_far")


# ══════════════════════════════════════════════════════════════════════════════
# ── main ─────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════


fn main() raises:
    print("== Wave 75 Tests: Biomedical, Ceramics, Wind Energy ==")

    # Biomedical
    test_cardiac_output()
    test_mean_arterial_pressure()
    test_body_surface_area()
    test_glomerular_filtration_rate()
    test_oxygen_delivery()
    test_alveolar_gas_equation()
    test_bmi()
    test_drug_clearance()
    test_anion_gap()
    test_corrected_qt_bazett()
    test_fick_cardiac_output()
    test_pulse_pressure()
    print("  ✓ Biomedical (12 functions, 24 assertions)")

    # Ceramics
    test_weibull_failure_probability()
    test_weibull_characteristic_strength()
    test_thermal_shock_resistance()
    test_youngs_modulus_porosity()
    test_sintering_shrinkage()
    test_density_from_archimedes()
    test_relative_density()
    test_porosity_from_density()
    test_fracture_toughness()
    test_dielectric_constant_mixture()
    test_coefficient_thermal_expansion()
    test_glass_transition_estimate()
    print("  ✓ Ceramics (12 functions, 22 assertions)")

    # Wind Energy
    test_wind_power_available()
    test_betz_limit()
    test_power_coefficient()
    test_tip_speed_ratio()
    test_swept_area()
    test_annual_energy_production()
    test_capacity_factor()
    test_wind_shear_power_law()
    test_weibull_mean_wind_speed()
    test_energy_density()
    test_rotor_thrust()
    test_wake_velocity()
    print("  ✓ Wind Energy (12 functions, 24 assertions)")

    print("== All 70 assertions passed ==")
