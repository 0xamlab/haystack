"""Tests for Wave 93 — Welding, Apiculture, Color Science."""

from welding import (
    heat_input,
    heat_input_kj,
    preheat_carbon_equivalent,
    cooling_rate_2d,
    weld_dilution,
    electrode_consumption,
    welding_speed_from_deposition,
    joint_efficiency,
    throat_thickness_fillet,
    allowable_shear_fillet,
    interpass_temperature_max,
    hydrogen_cracking_risk,
)
from apiculture import (
    honey_yield_per_hive,
    colony_strength_estimate,
    varroa_infestation_rate,
    sugar_syrup_ratio,
    foraging_range_area,
    nectar_to_honey_ratio,
    brood_viability,
    winter_feed_requirement,
    queen_laying_rate,
    pollination_value,
    hive_density_per_hectare,
    overwintering_survival_rate,
)
from color_science import (
    delta_e_76,
    lab_to_lch_l,
    lab_to_lch_c,
    lab_to_lch_h,
    rgb_to_luminance,
    contrast_ratio,
    wcag_aa_pass,
    color_temperature_approx,
    metamerism_index,
    chromatic_adaptation_von_kries,
    cri_from_delta_e,
    whiteness_index_cie,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < eps


def approx_rel(a: Float64, b: Float64, rel: Float64 = 1e-4) -> Bool:
    if fabs(b) < 1e-12:
        return fabs(a) < 1e-12
    return fabs((a - b) / b) < rel


# ── Welding tests ────────────────────────────────────────────────────────────


def test_welding() raises:
    # heat_input: V=25, I=200, speed=5 mm/s => 25*200/5 = 1000 J/mm
    assert_true(approx(heat_input(25.0, 200.0, 5.0), 1000.0), "heat_input basic")

    # heat_input edge: V=30, I=150, speed=3 => 30*150/3 = 1500
    assert_true(approx(heat_input(30.0, 150.0, 3.0), 1500.0), "heat_input 1500")

    # heat_input_kj: V=25, I=200, speed=300 mm/min => 25*200*60/(300*1000) = 1.0
    assert_true(approx(heat_input_kj(25.0, 200.0, 300.0), 1.0), "heat_input_kj 1.0")

    # heat_input_kj: V=30, I=250, speed=500 => 30*250*60/(500*1000) = 0.9
    assert_true(approx(heat_input_kj(30.0, 250.0, 500.0), 0.9), "heat_input_kj 0.9")

    # preheat_carbon_equivalent: C=0.15, Mn=1.2, Cr=0.5, Mo=0.3, V=0.05, Ni=0.4, Cu=0.2
    # CE = 0.15 + 1.2/6 + (0.5+0.3+0.05)/5 + (0.4+0.2)/15
    # CE = 0.15 + 0.2 + 0.17 + 0.04 = 0.56
    assert_true(approx(preheat_carbon_equivalent(0.15, 1.2, 0.5, 0.3, 0.05, 0.4, 0.2), 0.56), "preheat CE")

    # preheat_carbon_equivalent: simple case C=0.20, all others 0
    assert_true(approx(preheat_carbon_equivalent(0.20, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0.20), "preheat CE simple")

    # cooling_rate_2d: HI=1000, T0=25, Tp=1500 => (1500-25)^2/1000 = 2175.625
    assert_true(approx(cooling_rate_2d(1000.0, 25.0, 1500.0), 2175.625), "cooling_rate_2d")

    # weld_dilution: base=20, weld=80 => 20/(20+80)*100 = 20%
    assert_true(approx(weld_dilution(20.0, 80.0), 20.0), "weld_dilution 20%")

    # weld_dilution: base=50, weld=50 => 50%
    assert_true(approx(weld_dilution(50.0, 50.0), 50.0), "weld_dilution 50%")

    # electrode_consumption: length=10, rate=0.5 => 5.0 kg
    assert_true(approx(electrode_consumption(10.0, 0.5), 5.0), "electrode_consumption")

    # welding_speed_from_deposition: rate=2.0, area=0.5, density=8.0 => 2/(0.5*8)=0.5
    assert_true(approx(welding_speed_from_deposition(2.0, 0.5, 8.0), 0.5), "welding_speed")

    # joint_efficiency: weld=400, base=500 => 80%
    assert_true(approx(joint_efficiency(400.0, 500.0), 80.0), "joint_efficiency 80%")

    # joint_efficiency: weld=500, base=500 => 100%
    assert_true(approx(joint_efficiency(500.0, 500.0), 100.0), "joint_efficiency 100%")

    # throat_thickness_fillet: leg=10 => 10*0.707 = 7.07
    assert_true(approx(throat_thickness_fillet(10.0), 7.07), "throat_fillet")

    # allowable_shear_fillet: throat=7.07, length=100, stress=100 => 70700
    assert_true(approx(allowable_shear_fillet(7.07, 100.0, 100.0), 70700.0), "allowable_shear")

    # interpass_temperature_max: CE=0.45 => 350 - 200*0.45 = 260
    assert_true(approx(interpass_temperature_max(0.45), 260.0), "interpass_temp")

    # interpass_temperature_max: CE=0.0 => 350
    assert_true(approx(interpass_temperature_max(0.0), 350.0), "interpass_temp zero CE")

    # hydrogen_cracking_risk: CE=0.45, H2=5, restraint=3 => 0.45*10+5*0.5+3 = 4.5+2.5+3=10.0
    assert_true(approx(hydrogen_cracking_risk(0.45, 5.0, 3.0), 10.0), "h2_cracking_risk")

    # hydrogen_cracking_risk: CE=0.6, H2=10, restraint=5 => 6+5+5=16
    assert_true(approx(hydrogen_cracking_risk(0.6, 10.0, 5.0), 16.0), "h2_cracking_risk high")

    print("  ✓ welding (20 assertions)")


# ── Apiculture tests ─────────────────────────────────────────────────────────


def test_apiculture() raises:
    # honey_yield_per_hive: 200 kg / 10 hives = 20
    assert_true(approx(honey_yield_per_hive(200.0, 10.0), 20.0), "honey_yield")

    # honey_yield_per_hive: 45 kg / 3 hives = 15
    assert_true(approx(honey_yield_per_hive(45.0, 3.0), 15.0), "honey_yield 15")

    # colony_strength_estimate: 8 frames * 2500 bees = 20000
    assert_true(approx(colony_strength_estimate(8.0, 2500.0), 20000.0), "colony_strength")

    # varroa_infestation_rate: 3 mites / 300 bees * 100 = 1.0%
    assert_true(approx(varroa_infestation_rate(3.0, 300.0), 1.0), "varroa_rate")

    # varroa_infestation_rate: 15 mites / 300 bees * 100 = 5.0%
    assert_true(approx(varroa_infestation_rate(15.0, 300.0), 5.0), "varroa_rate high")

    # sugar_syrup_ratio: 1 kg sugar, 1 kg water => 0.5
    assert_true(approx(sugar_syrup_ratio(1.0, 1.0), 0.5), "syrup_ratio 1:1")

    # sugar_syrup_ratio: 2 kg sugar, 1 kg water => 2/3 ≈ 0.6667
    assert_true(approx_rel(sugar_syrup_ratio(2.0, 1.0), 0.666666666), "syrup_ratio 2:1")

    # foraging_range_area: r=3 km => π*9 ≈ 28.2743
    assert_true(approx_rel(foraging_range_area(3.0), 28.274333882), "foraging_area")

    # nectar_to_honey_ratio: 20 kg nectar => 5 kg honey
    assert_true(approx(nectar_to_honey_ratio(20.0), 5.0), "nectar_to_honey")

    # nectar_to_honey_ratio: 100 kg nectar => 25 kg honey
    assert_true(approx(nectar_to_honey_ratio(100.0), 25.0), "nectar_to_honey 100")

    # brood_viability: 85 hatched / 100 total => 85%
    assert_true(approx(brood_viability(85.0, 100.0), 85.0), "brood_viability")

    # winter_feed_requirement: weight=25, months=5, consumption=3 => 5*3-(25-15)=15-10=5
    assert_true(approx(winter_feed_requirement(25.0, 5.0, 3.0), 5.0), "winter_feed")

    # winter_feed_requirement: weight=20, months=4, consumption=2.5 => 10-5=5
    assert_true(approx(winter_feed_requirement(20.0, 4.0, 2.5), 5.0), "winter_feed 2")

    # queen_laying_rate: identity
    assert_true(approx(queen_laying_rate(1500.0), 1500.0), "queen_laying")

    # pollination_value: increase=30%, crop_value=10000 => 3000
    assert_true(approx(pollination_value(30.0, 10000.0), 3000.0), "pollination_val")

    # hive_density_per_hectare: 5 hives / 2.5 ha = 2.0
    assert_true(approx(hive_density_per_hectare(5.0, 2.5), 2.0), "hive_density")

    # overwintering_survival_rate: 8 survived / 10 total => 80%
    assert_true(approx(overwintering_survival_rate(8.0, 10.0), 80.0), "overwinter_sr")

    # overwintering_survival_rate: 45 survived / 50 total => 90%
    assert_true(approx(overwintering_survival_rate(45.0, 50.0), 90.0), "overwinter_sr 90")

    print("  ✓ apiculture (19 assertions)")


# ── Color Science tests ──────────────────────────────────────────────────────


def test_color_science() raises:
    # delta_e_76: same color => 0
    assert_true(approx(delta_e_76(50.0, 20.0, -10.0, 50.0, 20.0, -10.0), 0.0), "delta_e zero")

    # delta_e_76: L diff only => sqrt((50-60)^2) = 10
    assert_true(approx(delta_e_76(50.0, 0.0, 0.0, 60.0, 0.0, 0.0), 10.0), "delta_e L only")

    # delta_e_76: (50,25,10) vs (60,30,15) => sqrt(100+25+25) = sqrt(150) ≈ 12.247
    assert_true(approx_rel(delta_e_76(50.0, 25.0, 10.0, 60.0, 30.0, 15.0), sqrt(150.0)), "delta_e general")

    # lab_to_lch_l: identity
    assert_true(approx(lab_to_lch_l(75.0), 75.0), "lch_l identity")

    # lab_to_lch_c: a=3, b=4 => sqrt(9+16) = 5
    assert_true(approx(lab_to_lch_c(3.0, 4.0), 5.0), "lch_c 345")

    # lab_to_lch_c: a=0, b=0 => 0
    assert_true(approx(lab_to_lch_c(0.0, 0.0), 0.0), "lch_c zero")

    # lab_to_lch_h: a=1, b=0 => atan2(0,1)*180/π = 0
    assert_true(approx(lab_to_lch_h(1.0, 0.0), 0.0), "lch_h 0deg")

    # lab_to_lch_h: a=0, b=1 => atan2(1,0)*180/π = 90
    assert_true(approx(lab_to_lch_h(0.0, 1.0), 90.0), "lch_h 90deg")

    # lab_to_lch_h: a=-1, b=0 => atan2(0,-1)*180/π = 180
    assert_true(approx(lab_to_lch_h(-1.0, 0.0), 180.0), "lch_h 180deg")

    # lab_to_lch_h: a=0, b=-1 => atan2(-1,0)*180/π = -90 => +360 = 270
    assert_true(approx(lab_to_lch_h(0.0, -1.0), 270.0), "lch_h 270deg")

    # rgb_to_luminance: white (1,1,1) => 0.2126+0.7152+0.0722 = 1.0
    assert_true(approx(rgb_to_luminance(1.0, 1.0, 1.0), 1.0), "luminance white")

    # rgb_to_luminance: black (0,0,0) => 0
    assert_true(approx(rgb_to_luminance(0.0, 0.0, 0.0), 0.0), "luminance black")

    # rgb_to_luminance: pure red (1,0,0) => 0.2126
    assert_true(approx(rgb_to_luminance(1.0, 0.0, 0.0), 0.2126), "luminance red")

    # contrast_ratio: white vs black => (1+0.05)/(0+0.05) = 21
    assert_true(approx(contrast_ratio(1.0, 0.0), 21.0), "contrast max")

    # contrast_ratio: same => 1.0
    assert_true(approx(contrast_ratio(0.5, 0.5), 1.0), "contrast same")

    # contrast_ratio: reversed order still works
    assert_true(approx(contrast_ratio(0.0, 1.0), 21.0), "contrast reversed")

    # wcag_aa_pass: CR=5.0, normal text (14pt) => pass (1.0)
    assert_true(approx(wcag_aa_pass(5.0, 14.0), 1.0), "wcag pass normal")

    # wcag_aa_pass: CR=3.5, normal text (14pt) => fail (0.0)
    assert_true(approx(wcag_aa_pass(3.5, 14.0), 0.0), "wcag fail normal")

    # wcag_aa_pass: CR=3.5, large text (18pt) => pass (1.0)
    assert_true(approx(wcag_aa_pass(3.5, 18.0), 1.0), "wcag pass large")

    # wcag_aa_pass: CR=2.5, large text (18pt) => fail (0.0)
    assert_true(approx(wcag_aa_pass(2.5, 18.0), 0.0), "wcag fail large")

    # color_temperature_approx: R=1, B=1 => 6500
    assert_true(approx(color_temperature_approx(1.0, 1.0), 6500.0), "cct neutral")

    # color_temperature_approx: R=0.5, B=1.0 => 13000
    assert_true(approx(color_temperature_approx(0.5, 1.0), 13000.0), "cct cool")

    # metamerism_index: |2.0 - 3.5| = 1.5
    assert_true(approx(metamerism_index(2.0, 3.5), 1.5), "metamerism")

    # metamerism_index: same => 0
    assert_true(approx(metamerism_index(4.0, 4.0), 0.0), "metamerism zero")

    # chromatic_adaptation_von_kries: x=0.95, gain=1.1 => 1.045
    assert_true(approx(chromatic_adaptation_von_kries(0.95, 1.1), 1.045), "von_kries")

    # cri_from_delta_e: ΔE=0 => CRI=100
    assert_true(approx(cri_from_delta_e(0.0), 100.0), "cri perfect")

    # cri_from_delta_e: ΔE=5 => 100-23=77
    assert_true(approx(cri_from_delta_e(5.0), 77.0), "cri 77")

    # whiteness_index_cie: big_y=95, x=0.3127, y=0.3290, xn=0.3127, yn=0.3290
    # W = 95 + 800*(0.3127-0.3127) + 1700*(0.3290-0.3290) = 95
    assert_true(approx(whiteness_index_cie(95.0, 0.3127, 0.3290, 0.3127, 0.3290), 95.0), "whiteness D65")

    # whiteness_index_cie: big_y=90, x=0.32, y=0.3290, xn=0.3127, yn=0.3290
    # W = 90 + 800*(0.3127-0.32) + 1700*(0.3290-0.3290)
    # W = 90 + 800*(-0.0073) = 90 - 5.84 = 84.16
    assert_true(approx_rel(whiteness_index_cie(90.0, 0.32, 0.3290, 0.3127, 0.3290), 84.16), "whiteness shifted")

    print("  ✓ color_science (29 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 93 tests — Welding, Apiculture, Color Science")
    test_welding()
    test_apiculture()
    test_color_science()
    print("All Wave 93 tests passed ✓  (68 assertions)")
