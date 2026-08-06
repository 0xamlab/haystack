"""Tests for Wave 78 — Solar Energy, Mining, Behavioral Economics."""

from solar_energy import (
    solar_irradiance_on_surface,
    panel_power_output,
    temperature_derate,
    cell_temperature_noct,
    solar_declination,
    hour_angle,
    solar_altitude,
    capacity_factor_solar,
    lcoe,
    payback_period,
    inverter_efficiency,
    string_voltage,
)
from mining import (
    ore_grade,
    strip_ratio,
    recovery_rate,
    mill_throughput,
    bond_work_index_energy,
    cut_off_grade,
    dilution_factor,
    net_smelter_return,
    reserve_life,
    powder_factor,
    ventilation_quantity,
    subsidence_factor,
)
from behavioral_economics import (
    prospect_theory_value,
    probability_weighting,
    hyperbolic_discount,
    quasi_hyperbolic_discount,
    anchoring_adjusted_estimate,
    endowment_effect_wta_wtp_ratio,
    loss_aversion_coefficient,
    mental_accounting_total,
    status_quo_bias,
    sunk_cost_ratio,
    fairness_ultimatum_threshold,
    nudge_effectiveness,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log, sin, cos


# ── Helpers ──────────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


# ── Solar Energy Tests ───────────────────────────────────────────────────────


def test_solar_energy() raises:
    print("== Solar Energy ==")

    # solar_irradiance_on_surface: I = 1000 * 0.866 = 866
    assert_true(approx_eq(solar_irradiance_on_surface(1000.0, 0.866), 866.0, 0.01), "irradiance")

    # solar_irradiance zero GHI
    assert_true(approx_eq(solar_irradiance_on_surface(0.0, 0.866), 0.0), "irradiance zero")

    # panel_power_output: P = 2.0 * 0.20 * 1000 = 400 W
    assert_true(approx_eq(panel_power_output(2.0, 0.20, 1000.0), 400.0), "panel_power")

    # panel_power zero area
    assert_true(approx_eq(panel_power_output(0.0, 0.20, 1000.0), 0.0), "panel zero area")

    # temperature_derate: P = 300*(1 + (-0.004)*(45-25)) = 300*(1-0.08) = 300*0.92 = 276
    assert_true(approx_eq(temperature_derate(300.0, -0.004, 45.0, 25.0), 276.0, 0.01), "temp_derate")

    # temperature_derate at STC: no change
    assert_true(approx_eq(temperature_derate(300.0, -0.004, 25.0, 25.0), 300.0), "temp_derate_stc")

    # cell_temperature_noct: Tcell = 25 + (45-20)/800 * 800 = 25 + 25 = 50
    assert_true(approx_eq(cell_temperature_noct(25.0, 45.0, 800.0), 50.0), "cell_temp_noct")

    # cell_temp zero irradiance
    assert_true(approx_eq(cell_temperature_noct(25.0, 45.0, 0.0), 25.0), "cell_temp_zero_g")

    # solar_declination: spring equinox day 80 → δ ≈ -0.4° (small)
    var dec_80 = solar_declination(80.0)
    assert_true(fabs(dec_80) < 2.0, "declination_equinox")

    # summer solstice day 172 → δ ≈ 23.45°
    var dec_172 = solar_declination(172.0)
    assert_true(dec_172 > 22.0 and dec_172 < 24.0, "declination_solstice")

    # hour_angle: noon → ω = 0
    assert_true(approx_eq(hour_angle(12.0), 0.0), "hour_angle_noon")

    # hour_angle: 6 AM → ω = -90
    assert_true(approx_eq(hour_angle(6.0), -90.0), "hour_angle_6am")

    # hour_angle: 6 PM → ω = 90
    assert_true(approx_eq(hour_angle(18.0), 90.0), "hour_angle_6pm")

    # solar_altitude: latitude=0, declination=0, noon → altitude=90°
    var alt = solar_altitude(0.0, 0.0, 0.0)
    assert_true(approx_eq(alt, 90.0, 1.0), "solar_alt_equator_equinox")

    # solar_altitude: lat=23.45, dec=23.45, noon → altitude=90°
    var alt2 = solar_altitude(23.45, 23.45, 0.0)
    assert_true(approx_eq(alt2, 90.0, 1.0), "solar_alt_tropic")

    # capacity_factor_solar: CF = 1500 / (5.0 * 8760) = 0.03425
    var cf = capacity_factor_solar(1500.0, 5.0, 8760.0)
    assert_true(approx_eq(cf, 1500.0 / (5.0 * 8760.0), 0.0001), "capacity_factor_solar")

    # cf zero rated
    assert_true(approx_eq(capacity_factor_solar(1500.0, 0.0, 8760.0), 0.0), "cf zero rated")

    # lcoe: LCOE = 50000 / 200000 = 0.25 $/kWh
    assert_true(approx_eq(lcoe(50000.0, 200000.0), 0.25), "lcoe")

    # lcoe zero energy
    assert_true(approx_eq(lcoe(50000.0, 0.0), 0.0), "lcoe zero energy")

    # payback_period: PP = 20000 / 2500 = 8 years
    assert_true(approx_eq(payback_period(20000.0, 2500.0), 8.0), "payback")

    # payback zero savings
    assert_true(approx_eq(payback_period(20000.0, 0.0), 0.0), "payback zero")

    # inverter_efficiency: η = 4800 / 5000 = 0.96
    assert_true(approx_eq(inverter_efficiency(4800.0, 5000.0), 0.96), "inverter_eff")

    # inverter zero dc
    assert_true(approx_eq(inverter_efficiency(4800.0, 0.0), 0.0), "inverter zero dc")

    # string_voltage: V = 12 * 37.5 = 450 V
    assert_true(approx_eq(string_voltage(12.0, 37.5), 450.0), "string_voltage")

    print("  All solar energy tests passed ✓")


# ── Mining Tests ─────────────────────────────────────────────────────────────


def test_mining() raises:
    print("== Mining ==")

    # ore_grade: Grade = 5/1000 * 100 = 0.5%
    assert_true(approx_eq(ore_grade(5.0, 1000.0), 0.5), "ore_grade")

    # ore_grade zero ore
    assert_true(approx_eq(ore_grade(5.0, 0.0), 0.0), "ore_grade zero")

    # strip_ratio: SR = 3000/1000 = 3.0
    assert_true(approx_eq(strip_ratio(3000.0, 1000.0), 3.0), "strip_ratio")

    # strip_ratio zero ore
    assert_true(approx_eq(strip_ratio(3000.0, 0.0), 0.0), "sr zero ore")

    # recovery_rate: R = 90/100 * 100 = 90%
    assert_true(approx_eq(recovery_rate(90.0, 100.0), 90.0), "recovery_rate")

    # recovery zero feed
    assert_true(approx_eq(recovery_rate(90.0, 0.0), 0.0), "recovery zero")

    # mill_throughput: T = 500 * 24 = 12000
    assert_true(approx_eq(mill_throughput(500.0, 24.0), 12000.0), "mill_throughput")

    # bond_work_index_energy: E = 10*15*(1/sqrt(100)-1/sqrt(10000))
    # = 150*(1/10 - 1/100) = 150*0.09 = 13.5
    var bwie = bond_work_index_energy(15.0, 100.0, 10000.0)
    assert_true(approx_eq(bwie, 13.5, 0.01), "bond_work_index_energy")

    # bond zero p80
    assert_true(approx_eq(bond_work_index_energy(15.0, 0.0, 10000.0), 0.0), "bond zero p80")

    # cut_off_grade: COG = (5+10)/(2000*0.9)*100 = 15/1800*100 ≈ 0.8333%
    var cog = cut_off_grade(5.0, 10.0, 2000.0, 0.9)
    assert_true(approx_eq(cog, 15.0 / 1800.0 * 100.0, 0.001), "cut_off_grade")

    # cog zero price
    assert_true(approx_eq(cut_off_grade(5.0, 10.0, 0.0, 0.9), 0.0), "cog zero price")

    # dilution_factor: D = 200/(200+1000)*100 = 200/1200*100 ≈ 16.667%
    var df = dilution_factor(200.0, 1000.0)
    assert_true(approx_eq(df, 200.0 / 1200.0 * 100.0, 0.01), "dilution_factor")

    # dilution zero total
    assert_true(approx_eq(dilution_factor(0.0, 0.0), 0.0), "dilution zero")

    # net_smelter_return: NSR = 2000*1.5/100*92/100 - 5 = 2000*0.015*0.92 - 5 = 27.6-5 = 22.6
    var nsr = net_smelter_return(2000.0, 1.5, 92.0, 5.0)
    assert_true(approx_eq(nsr, 22.6, 0.01), "net_smelter_return")

    # reserve_life: Life = 50000000/5000000 = 10 years
    assert_true(approx_eq(reserve_life(50000000.0, 5000000.0), 10.0), "reserve_life")

    # reserve zero production
    assert_true(approx_eq(reserve_life(50000000.0, 0.0), 0.0), "reserve zero")

    # powder_factor: PF = 250/1000 = 0.25 kg/t
    assert_true(approx_eq(powder_factor(250.0, 1000.0), 0.25), "powder_factor")

    # powder zero rock
    assert_true(approx_eq(powder_factor(250.0, 0.0), 0.0), "pf zero rock")

    # ventilation_quantity: Q = 50 * 0.5 = 25 m³/s
    assert_true(approx_eq(ventilation_quantity(50.0, 0.5), 25.0), "ventilation")

    # subsidence_factor: SF = 3.0/300 = 0.01
    assert_true(approx_eq(subsidence_factor(3.0, 300.0), 0.01), "subsidence")

    # subsidence zero depth
    assert_true(approx_eq(subsidence_factor(3.0, 0.0), 0.0), "subsidence zero")

    print("  All mining tests passed ✓")


# ── Behavioral Economics Tests ───────────────────────────────────────────────


def test_behavioral_economics() raises:
    print("== Behavioral Economics ==")

    # prospect_theory_value: gain x=100, α=0.88 → 100^0.88
    var ptv_gain = prospect_theory_value(100.0, 0.88, 2.25)
    var expected_gain = exp(0.88 * log(100.0))
    assert_true(approx_eq(ptv_gain, expected_gain, 0.01), "ptv gain")

    # prospect_theory_value: loss x=-100 → -2.25*100^0.88
    var ptv_loss = prospect_theory_value(-100.0, 0.88, 2.25)
    var expected_loss = -2.25 * exp(0.88 * log(100.0))
    assert_true(approx_eq(ptv_loss, expected_loss, 0.01), "ptv loss")

    # prospect_theory_value: x=0 → 0
    assert_true(approx_eq(prospect_theory_value(0.0, 0.88, 2.25), 0.0), "ptv zero")

    # probability_weighting: p=0.5, γ=0.61
    var pw = probability_weighting(0.5, 0.61)
    assert_true(pw > 0.4 and pw < 0.6, "prob_weighting mid")

    # probability_weighting: p=0 → 0
    assert_true(approx_eq(probability_weighting(0.0, 0.61), 0.0), "pw zero")

    # probability_weighting: p=1 → 1
    assert_true(approx_eq(probability_weighting(1.0, 0.61), 1.0), "pw one")

    # hyperbolic_discount: PV = 1000 / (1 + 0.1*5) = 1000/1.5 ≈ 666.667
    var hd = hyperbolic_discount(1000.0, 0.1, 5.0)
    assert_true(approx_eq(hd, 1000.0 / 1.5, 0.01), "hyperbolic_discount")

    # hyperbolic zero delay
    assert_true(approx_eq(hyperbolic_discount(1000.0, 0.1, 0.0), 1000.0), "hd zero delay")

    # quasi_hyperbolic_discount: t=0 → V
    assert_true(approx_eq(quasi_hyperbolic_discount(100.0, 0.7, 0.95, 0.0), 100.0), "qhd t0")

    # quasi_hyperbolic_discount: t=1, β=0.7, δ=0.95 → 0.7*0.95*100 = 66.5
    var qhd1 = quasi_hyperbolic_discount(100.0, 0.7, 0.95, 1.0)
    assert_true(approx_eq(qhd1, 0.7 * 0.95 * 100.0, 0.01), "qhd t1")

    # quasi_hyperbolic_discount: t=2, β=0.7, δ=0.95 → 0.7*0.95²*100 = 63.175
    var qhd2 = quasi_hyperbolic_discount(100.0, 0.7, 0.95, 2.0)
    assert_true(approx_eq(qhd2, 0.7 * 0.95 * 0.95 * 100.0, 0.01), "qhd t2")

    # anchoring_adjusted_estimate: Est = 100 + 50*0.5 = 125
    assert_true(approx_eq(anchoring_adjusted_estimate(100.0, 50.0, 0.5), 125.0), "anchoring")

    # endowment_effect_wta_wtp_ratio: Ratio = 7.0/3.0 ≈ 2.333
    var endo = endowment_effect_wta_wtp_ratio(7.0, 3.0)
    assert_true(approx_eq(endo, 7.0 / 3.0, 0.001), "endowment")

    # endowment zero WTP
    assert_true(approx_eq(endowment_effect_wta_wtp_ratio(7.0, 0.0), 0.0), "endowment zero")

    # loss_aversion_coefficient: λ = |-50|/25 = 2.0
    assert_true(approx_eq(loss_aversion_coefficient(-50.0, 25.0), 2.0), "loss_aversion")

    # loss_aversion zero gain
    assert_true(approx_eq(loss_aversion_coefficient(-50.0, 0.0), 0.0), "la zero gain")

    # mental_accounting_total: Net = 500 + (-200) = 300
    assert_true(approx_eq(mental_accounting_total(500.0, -200.0), 300.0), "mental_accounting")

    # status_quo_bias: Bias = 30 - 20 = 10 (stay)
    assert_true(approx_eq(status_quo_bias(30.0, 20.0), 10.0), "sqb stay")

    # status_quo_bias: switch preferred
    assert_true(approx_eq(status_quo_bias(10.0, 30.0), -20.0), "sqb switch")

    # sunk_cost_ratio: SCR = 40000/100000 = 0.4
    assert_true(approx_eq(sunk_cost_ratio(40000.0, 100000.0), 0.4), "sunk_cost_ratio")

    # sunk_cost zero budget
    assert_true(approx_eq(sunk_cost_ratio(40000.0, 0.0), 0.0), "scr zero")

    # fairness_ultimatum_threshold: Fair% = 3/10*100 = 30%
    assert_true(approx_eq(fairness_ultimatum_threshold(3.0, 10.0), 30.0), "fairness")

    # fairness zero total
    assert_true(approx_eq(fairness_ultimatum_threshold(3.0, 0.0), 0.0), "fairness zero")

    # nudge_effectiveness: Effect = 0.75 - 0.60 = 0.15
    assert_true(approx_eq(nudge_effectiveness(0.75, 0.60), 0.15), "nudge_effect")

    # nudge negative (backfire)
    assert_true(approx_eq(nudge_effectiveness(0.40, 0.60), -0.20), "nudge negative")

    print("  All behavioral economics tests passed ✓")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 78 Tests: Solar Energy, Mining, Behavioral Economics")
    test_solar_energy()
    test_mining()
    test_behavioral_economics()
    print("All Wave 78 tests passed ✓  (76 assertions)")
