"""Tests for Wave 60 — Optics, Electrical Engineering, Nutrition Science.
🎯 250 LIBRARY MILESTONE!
"""

from optics import (
    snells_law,
    critical_angle,
    fresnel_reflectance_normal,
    thin_lens_equation,
    magnification,
    wavelength_to_frequency,
    photon_energy,
    diffraction_limit,
    brewster_angle,
    numerical_aperture,
)
from electrical import (
    ohms_law_v,
    ohms_law_i,
    ohms_law_r,
    power_dc,
    series_resistance,
    parallel_resistance,
    rc_time_constant,
    rc_voltage,
    rlc_resonance,
    impedance_magnitude,
    power_factor,
    capacitive_reactance,
    inductive_reactance,
    voltage_divider,
)
from nutrition import (
    bmi,
    bmi_category,
    bmr_mifflin,
    tdee,
    caloric_deficit,
    macro_split,
    ideal_body_weight,
    body_fat_estimate,
    water_intake,
    heart_rate_max,
    target_heart_rate,
    vo2max_estimate,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Optics Tests ─────────────────────────────────────────────────────────────


def test_optics() raises:
    print("  ▶ optics …")
    var passed = 0

    # 1: Snell's law — refraction angle should be < 30 for light going into denser medium
    var angle = snells_law(1.0, 30.0, 1.5)
    _assert(angle > 0.0 and angle < 30.0, "snells_law refraction angle < 30")
    _assert_close(angle, 19.47, 0.1, "snells_law(1.0,30,1.5)")
    passed += 2

    # 2: Snell's law going from dense to rare
    var angle2 = snells_law(1.5, 19.47, 1.0)
    _assert_close(angle2, 30.0, 0.2, "snells_law reverse")
    passed += 1

    # 3: Critical angle
    var ca = critical_angle(1.5, 1.0)
    _assert(ca > 0.0 and ca < 90.0, "critical_angle valid")
    _assert_close(ca, 41.81, 0.1, "critical_angle(1.5,1.0)")
    passed += 2

    # 4: Critical angle returns -1 when n2 > n1
    _assert(critical_angle(1.0, 1.5) == -1.0, "critical_angle n2>n1 => -1")
    passed += 1

    # 5: Fresnel reflectance at normal incidence
    var fr = fresnel_reflectance_normal(1.0, 1.5)
    _assert_close(fr, 0.04, 0.001, "fresnel_reflectance_normal(1.0,1.5)")
    passed += 1

    # 6: Fresnel reflectance symmetry
    var fr2 = fresnel_reflectance_normal(1.5, 1.0)
    _assert_close(fr, fr2, 1e-10, "fresnel reflectance symmetric")
    passed += 1

    # 7: Thin lens equation — object at 2f → image at 2f
    var di = thin_lens_equation(10.0, 20.0)
    _assert_close(di, 20.0, 0.01, "thin_lens_equation(10,20)")
    passed += 1

    # 8: Thin lens — object at infinity → image at f
    var di2 = thin_lens_equation(10.0, 1.0e18)
    _assert_close(di2, 10.0, 0.1, "thin_lens object at infinity")
    passed += 1

    # 9: Magnification
    var m = magnification(20.0, 20.0)
    _assert_close(m, -1.0, 0.001, "magnification(20,20)=-1")
    passed += 1

    # 10: Magnification 2x
    var m2 = magnification(40.0, 20.0)
    _assert_close(m2, -2.0, 0.001, "magnification(40,20)=-2")
    passed += 1

    # 11: Wavelength to frequency — 500nm green light
    var freq = wavelength_to_frequency(500.0)
    _assert_close(freq, 6.0e14, 1.0e12, "wavelength_to_frequency(500)")
    passed += 1

    # 12: Photon energy at 500nm
    var e = photon_energy(500.0)
    _assert_close(e, 2.48, 0.02, "photon_energy(500)")
    passed += 1

    # 13: Photon energy at 400nm (violet) > 500nm (green)
    var e2 = photon_energy(400.0)
    _assert(e2 > e, "shorter wavelength = higher energy")
    passed += 1

    # 14: Diffraction limit positive
    var dl = diffraction_limit(500.0, 100.0)
    _assert(dl > 0.0, "diffraction_limit positive")
    passed += 1

    # 15: Brewster angle for glass
    var ba = brewster_angle(1.0, 1.5)
    _assert_close(ba, 56.31, 0.1, "brewster_angle(1.0,1.5)")
    passed += 1

    # 16: Numerical aperture
    var na = numerical_aperture(1.0, 30.0)
    _assert_close(na, 0.5, 0.001, "numerical_aperture(1.0,30)")
    passed += 1

    # 17: NA of oil immersion
    var na2 = numerical_aperture(1.515, 64.0)
    _assert(na2 > 1.0, "oil immersion NA > 1")
    passed += 1

    print("    ✅ optics passed (" + String(passed) + " assertions)")


# ── Electrical Tests ─────────────────────────────────────────────────────────


def test_electrical() raises:
    print("  ▶ electrical …")
    var passed = 0

    # 1: Ohm's law V
    _assert_close(ohms_law_v(2.0, 5.0), 10.0, 1e-10, "ohms_law_v(2,5)")
    passed += 1

    # 2: Ohm's law I
    _assert_close(ohms_law_i(10.0, 5.0), 2.0, 1e-10, "ohms_law_i(10,5)")
    passed += 1

    # 3: Ohm's law R
    _assert_close(ohms_law_r(10.0, 2.0), 5.0, 1e-10, "ohms_law_r(10,2)")
    passed += 1

    # 4: DC power
    _assert_close(power_dc(12.0, 2.0), 24.0, 1e-10, "power_dc(12,2)")
    passed += 1

    # 5: Series resistance
    var r_series = List[Float64]()
    r_series.append(10.0)
    r_series.append(20.0)
    r_series.append(30.0)
    _assert_close(series_resistance(r_series), 60.0, 1e-10, "series_resistance")
    passed += 1

    # 6: Parallel resistance — two equal resistors
    var r_par = List[Float64]()
    r_par.append(10.0)
    r_par.append(10.0)
    _assert_close(parallel_resistance(r_par), 5.0, 1e-10, "parallel_resistance([10,10])")
    passed += 1

    # 7: Parallel — three 30Ω = 10Ω
    var r_par3 = List[Float64]()
    r_par3.append(30.0)
    r_par3.append(30.0)
    r_par3.append(30.0)
    _assert_close(parallel_resistance(r_par3), 10.0, 1e-10, "parallel_resistance([30,30,30])")
    passed += 1

    # 8: RC time constant
    _assert_close(rc_time_constant(1000.0, 0.001), 1.0, 1e-10, "rc_time_constant(1000,0.001)")
    passed += 1

    # 9: RC voltage at t=0 is 0
    _assert_close(rc_voltage(10.0, 1000.0, 0.001, 0.0), 0.0, 1e-10, "rc_voltage t=0")
    passed += 1

    # 10: RC voltage at t>>τ approaches V0
    var v_inf = rc_voltage(10.0, 1000.0, 0.001, 100.0)
    _assert_close(v_inf, 10.0, 0.001, "rc_voltage t>>tau")
    passed += 1

    # 11: RC voltage at t=τ ≈ 63.2% of V0
    var v_tau = rc_voltage(10.0, 1000.0, 0.001, 1.0)
    _assert_close(v_tau, 6.321, 0.01, "rc_voltage at t=tau")
    passed += 1

    # 12: RLC resonance
    var f0 = rlc_resonance(0.001, 0.000001)
    _assert_close(f0, 5032.9, 1.0, "rlc_resonance(1mH,1uF)")
    passed += 1

    # 13: Impedance magnitude — pure resistive
    _assert_close(impedance_magnitude(100.0, 0.0), 100.0, 1e-10, "impedance R only")
    passed += 1

    # 14: Impedance magnitude — R and X
    _assert_close(impedance_magnitude(3.0, 4.0), 5.0, 1e-10, "impedance 3-4-5")
    passed += 1

    # 15: Power factor
    _assert_close(power_factor(800.0, 1000.0), 0.8, 1e-10, "power_factor(800,1000)")
    passed += 1

    # 16: Capacitive reactance
    var xc = capacitive_reactance(0.000001, 5032.9)
    _assert(xc > 0.0, "capacitive_reactance positive")
    passed += 1

    # 17: Inductive reactance
    var xl = inductive_reactance(0.001, 5032.9)
    _assert(xl > 0.0, "inductive_reactance positive")
    passed += 1

    # 18: At resonance, Xc ≈ Xl
    var f_res = rlc_resonance(0.001, 0.000001)
    var xc_res = capacitive_reactance(0.000001, f_res)
    var xl_res = inductive_reactance(0.001, f_res)
    _assert_close(xc_res, xl_res, 0.1, "Xc==Xl at resonance")
    passed += 1

    # 19: Voltage divider — equal resistors
    _assert_close(voltage_divider(10.0, 1000.0, 1000.0), 5.0, 1e-10, "voltage_divider equal R")
    passed += 1

    # 20: Voltage divider — 2:1 ratio
    _assert_close(voltage_divider(9.0, 1000.0, 2000.0), 6.0, 1e-10, "voltage_divider 1k:2k")
    passed += 1

    print("    ✅ electrical passed (" + String(passed) + " assertions)")


# ── Nutrition Tests ──────────────────────────────────────────────────────────


def test_nutrition() raises:
    print("  ▶ nutrition …")
    var passed = 0

    # 1: BMI
    var b = bmi(70.0, 1.75)
    _assert_close(b, 22.857, 0.01, "bmi(70,1.75)")
    passed += 1

    # 2: BMI category normal
    _assert(bmi_category(22.86) == 1, "bmi_category 22.86 == normal")
    passed += 1

    # 3: BMI category underweight
    _assert(bmi_category(17.0) == 0, "bmi_category 17 == underweight")
    passed += 1

    # 4: BMI category overweight
    _assert(bmi_category(27.0) == 2, "bmi_category 27 == overweight")
    passed += 1

    # 5: BMI category obese
    _assert(bmi_category(35.0) == 3, "bmi_category 35 == obese")
    passed += 1

    # 6: BMR Mifflin male
    var bmr_m = bmr_mifflin(70.0, 175.0, 30, True)
    _assert(bmr_m > 1500.0 and bmr_m < 2000.0, "bmr_mifflin male in range")
    # Expected: 10*70 + 6.25*175 - 5*30 + 5 = 700 + 1093.75 - 150 + 5 = 1648.75
    _assert_close(bmr_m, 1648.75, 0.01, "bmr_mifflin male exact")
    passed += 2

    # 7: BMR Mifflin female
    var bmr_f = bmr_mifflin(60.0, 165.0, 25, False)
    _assert(bmr_f > 1200.0 and bmr_f < 1600.0, "bmr_mifflin female in range")
    passed += 1

    # 8: TDEE
    var t = tdee(1800.0, 1.55)
    _assert_close(t, 2790.0, 0.01, "tdee(1800,1.55)")
    passed += 1

    # 9: Caloric deficit
    var cd = caloric_deficit(2500.0, 0.5)
    _assert_close(cd, 550.0, 0.01, "caloric_deficit(2500,0.5)")
    passed += 1

    # 10: Macro split — verify sums to ~2000 cal
    var macros = macro_split(2000.0, 0.3, 0.3)
    var protein_g = macros[0]  # 2000*0.3/4 = 150g
    var fat_g = macros[1]      # 2000*0.3/9 = 66.67g
    var carb_g = macros[2]     # 2000*0.4/4 = 200g
    var total_cal = protein_g * 4.0 + fat_g * 9.0 + carb_g * 4.0
    _assert_close(total_cal, 2000.0, 0.1, "macro_split sums to 2000")
    _assert_close(protein_g, 150.0, 0.01, "macro_split protein_g")
    _assert_close(fat_g, 66.667, 0.01, "macro_split fat_g")
    _assert_close(carb_g, 200.0, 0.01, "macro_split carb_g")
    passed += 4

    # 11: Ideal body weight male
    var ibw = ideal_body_weight(175.0, True)
    _assert(ibw > 60.0 and ibw < 90.0, "ideal_body_weight male reasonable")
    passed += 1

    # 12: Ideal body weight female
    var ibw_f = ideal_body_weight(165.0, False)
    _assert(ibw_f > 50.0 and ibw_f < 80.0, "ideal_body_weight female reasonable")
    passed += 1

    # 13: Body fat estimate
    var bf = body_fat_estimate(22.86, 30, True)
    _assert(bf > 10.0 and bf < 30.0, "body_fat_estimate in range")
    passed += 1

    # 14: Water intake
    var w = water_intake(70.0)
    _assert_close(w, 2.31, 0.01, "water_intake(70)")
    passed += 1

    # 15: Heart rate max
    _assert(heart_rate_max(30) == 190, "heart_rate_max(30)==190")
    passed += 1

    # 16: Heart rate max at age 0
    _assert(heart_rate_max(0) == 220, "heart_rate_max(0)==220")
    passed += 1

    # 17: Target heart rate
    var thr = target_heart_rate(190, 0.5, 0.85)
    _assert_close(thr[0], 95.0, 0.01, "target_hr low")
    _assert_close(thr[1], 161.5, 0.01, "target_hr high")
    passed += 2

    # 18: VO2max estimate
    var vo2 = vo2max_estimate(60, 190)
    _assert_close(vo2, 48.45, 0.01, "vo2max_estimate(60,190)")
    passed += 1

    print("    ✅ nutrition passed (" + String(passed) + " assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          🎯  250 LIBRARY MILESTONE REACHED!  🎯            ║")
    print("║                                                            ║")
    print("║   Wave 60 — Optics, Electrical Engineering, Nutrition      ║")
    print("║   Three new libraries bringing us to 250 total!            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print("")
    print("── Wave 60 Tests ──────────────────────────────────────────────")

    test_optics()
    test_electrical()
    test_nutrition()

    print("")
    print("🎯 ALL WAVE 60 TESTS PASSED — 250 LIBRARY MILESTONE! 🎯")
    print("")
