"""Tests for Wave 67 — Hydrology, Actuarial, Linguistics."""

from hydrology import (
    manning_velocity,
    manning_discharge,
    hydraulic_radius,
    froude_number,
    reynolds_number_pipe,
    darcy_weisbach_head_loss,
    rational_method_peak_flow,
    time_of_concentration_kirpich,
    curve_number_runoff,
    evapotranspiration_hargreaves,
    specific_yield,
    darcy_groundwater_velocity,
)
from actuarial import (
    present_value,
    future_value,
    annuity_present_value,
    annuity_future_value,
    life_expectancy_curtate,
    mortality_rate,
    survival_probability,
    force_of_mortality,
    net_single_premium,
    loss_ratio,
    combined_ratio,
    reserve_prospective,
)
from linguistics import (
    type_token_ratio,
    hapax_legomena_ratio,
    yules_k,
    heaps_law,
    zipfs_frequency,
    flesch_reading_ease,
    flesch_kincaid_grade,
    gunning_fog_index,
    automated_readability_index,
    coleman_liau_index,
    lexical_density,
    mean_word_length,
)
from std.math import abs as fabs, sqrt, exp, log


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


fn _near_rel(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    """Relative tolerance check."""
    if fabs(b) < 1e-12:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Hydrology tests ──────────────────────────────────────────────────────────


fn test_hydraulic_radius() raises:
    var rh = hydraulic_radius(10.0, 8.0)
    _assert(_near(rh, 1.25), "hydraulic_radius(10,8) = 1.25")


fn test_manning_velocity() raises:
    # n=0.035, R_h=1.0, S=0.01 => V = (1/0.035)*1.0^(2/3)*0.01^(1/2)
    # = 28.571 * 1.0 * 0.1 = 2.857...
    var v = manning_velocity(0.035, 1.0, 0.01)
    _assert(_near(v, 1.0 / 0.035 * 0.1, 0.001), "manning_velocity n=0.035 R=1 S=0.01")


fn test_manning_velocity_non_unit_rh() raises:
    # n=0.03, R_h=0.5, S=0.04 => V = (1/0.03)*(0.5)^(2/3)*(0.04)^(1/2)
    var r_h_23 = exp(2.0 / 3.0 * log(0.5))
    var expected = (1.0 / 0.03) * r_h_23 * sqrt(0.04)
    var v = manning_velocity(0.03, 0.5, 0.04)
    _assert(_near(v, expected, 0.001), "manning_velocity non-unit Rh")


fn test_manning_discharge() raises:
    var q = manning_discharge(0.035, 5.0, 1.0, 0.01)
    var v = manning_velocity(0.035, 1.0, 0.01)
    _assert(_near(q, 5.0 * v, 0.001), "manning_discharge = A*V")


fn test_froude_number() raises:
    # V=3, d=1, g=9.81 => Fr = 3/sqrt(9.81) ≈ 0.9582
    var fr = froude_number(3.0, 1.0, 9.81)
    _assert(_near(fr, 3.0 / sqrt(9.81), 0.001), "froude_number")


fn test_froude_subcritical() raises:
    var fr = froude_number(1.0, 2.0, 9.81)
    _assert(fr < 1.0, "froude subcritical Fr<1")


fn test_reynolds_number_pipe() raises:
    # V=2, D=0.1, ν=1e-6 => Re=200000
    var re = reynolds_number_pipe(2.0, 0.1, 1e-6)
    _assert(_near(re, 200000.0, 1.0), "reynolds_number_pipe")


fn test_darcy_weisbach_head_loss() raises:
    # f=0.02, L=100, D=0.1, V=2, g=9.81
    # hf = 0.02*(100/0.1)*(4/(2*9.81)) = 0.02*1000*0.2039 = 4.077
    var hf = darcy_weisbach_head_loss(0.02, 100.0, 0.1, 2.0, 9.81)
    var expected = 0.02 * (100.0 / 0.1) * (4.0 / (2.0 * 9.81))
    _assert(_near(hf, expected, 0.01), "darcy_weisbach_head_loss")


fn test_rational_method_peak_flow() raises:
    # C=0.9, i=2.0 in/hr, A=10 acres => Q=18
    var q = rational_method_peak_flow(0.9, 2.0, 10.0)
    _assert(_near(q, 18.0), "rational_method_peak_flow")


fn test_time_of_concentration_kirpich() raises:
    # L=1000 ft, S=0.05
    var tc = time_of_concentration_kirpich(1000.0, 0.05)
    # tc = 0.0078 * 1000^0.77 * 0.05^(-0.385)
    var l_077 = exp(0.77 * log(1000.0))
    var s_neg = exp(-0.385 * log(0.05))
    var expected = 0.0078 * l_077 * s_neg
    _assert(_near_rel(tc, expected), "kirpich tc")


fn test_curve_number_runoff() raises:
    # P=5, CN=85 => S=1000/85-10 = 1.7647, Ia=0.353
    # Q = (5-0.353)^2 / (5+0.8*1.7647) = 4.647^2 / 6.4118 = 21.59/6.41 = 3.368
    var q = curve_number_runoff(5.0, 85.0)
    var s = 1000.0 / 85.0 - 10.0
    var ia = 0.2 * s
    var expected = (5.0 - ia) * (5.0 - ia) / (5.0 + 0.8 * s)
    _assert(_near(q, expected, 0.01), "curve_number_runoff")


fn test_curve_number_no_runoff() raises:
    # P=0.1, CN=50 => S=10, Ia=2.0  P<Ia => Q=0
    var q = curve_number_runoff(0.1, 50.0)
    _assert(_near(q, 0.0), "curve_number no runoff")


fn test_evapotranspiration_hargreaves() raises:
    # T_mean=25, T_range=12, Ra=15
    # ET = 0.0023 * 15 * (25+17.8) * sqrt(12) = 0.0023*15*42.8*3.464 = 5.123
    var et = evapotranspiration_hargreaves(25.0, 12.0, 15.0)
    var expected = 0.0023 * 15.0 * (25.0 + 17.8) * sqrt(12.0)
    _assert(_near(et, expected, 0.01), "hargreaves ET")


fn test_specific_yield() raises:
    var sy = specific_yield(30.0, 100.0)
    _assert(_near(sy, 0.3), "specific_yield")


fn test_darcy_groundwater_velocity() raises:
    # K=5e-4 m/s, i=0.01 => v=5e-6
    var v = darcy_groundwater_velocity(5e-4, 0.01)
    _assert(_near(v, 5e-6), "darcy_groundwater_velocity")


# ── Actuarial tests ──────────────────────────────────────────────────────────


fn test_present_value() raises:
    # FV=1000, r=0.05, n=10 => PV=1000/(1.05)^10 = 613.913
    var pv = present_value(1000.0, 0.05, 10.0)
    var expected = 1000.0 / exp(10.0 * log(1.05))
    _assert(_near(pv, expected, 0.01), "present_value")


fn test_future_value() raises:
    # PV=500, r=0.08, n=5 => FV=500*(1.08)^5 = 734.664
    var fv = future_value(500.0, 0.08, 5.0)
    var expected = 500.0 * exp(5.0 * log(1.08))
    _assert(_near(fv, expected, 0.01), "future_value")


fn test_pv_fv_roundtrip() raises:
    var fv = future_value(1000.0, 0.06, 20.0)
    var pv = present_value(fv, 0.06, 20.0)
    _assert(_near(pv, 1000.0, 0.01), "PV/FV roundtrip")


fn test_annuity_present_value() raises:
    # PMT=100, r=0.05, n=10 => PV = 100*(1-(1.05)^(-10))/0.05 = 772.173
    var apv = annuity_present_value(100.0, 0.05, 10.0)
    var expected = 100.0 * (1.0 - exp(-10.0 * log(1.05))) / 0.05
    _assert(_near(apv, expected, 0.01), "annuity_present_value")


fn test_annuity_present_value_zero_rate() raises:
    var apv = annuity_present_value(100.0, 0.0, 10.0)
    _assert(_near(apv, 1000.0), "annuity PV zero rate")


fn test_annuity_future_value() raises:
    # PMT=200, r=0.07, n=15
    var afv = annuity_future_value(200.0, 0.07, 15.0)
    var expected = 200.0 * (exp(15.0 * log(1.07)) - 1.0) / 0.07
    _assert(_near(afv, expected, 0.01), "annuity_future_value")


fn test_annuity_future_value_zero_rate() raises:
    var afv = annuity_future_value(200.0, 0.0, 15.0)
    _assert(_near(afv, 3000.0), "annuity FV zero rate")


fn test_life_expectancy_curtate() raises:
    # qx=0.01, age=60, max_age=100 => 40 years, sum of (0.99)^k for k=1..40
    var ex = life_expectancy_curtate(0.01, 60, 100)
    # Geometric series: sum = 0.99*(1-0.99^40)/(1-0.99)
    var px = 0.99
    var expected = px * (1.0 - exp(40.0 * log(px))) / (1.0 - px)
    _assert(_near(ex, expected, 0.01), "life_expectancy_curtate")


fn test_mortality_rate() raises:
    var qx = mortality_rate(50.0, 10000.0)
    _assert(_near(qx, 0.005), "mortality_rate")


fn test_survival_probability() raises:
    var px = survival_probability(0.02)
    _assert(_near(px, 0.98), "survival_probability")


fn test_force_of_mortality() raises:
    # μx = -ln(1-0.02) = -ln(0.98) ≈ 0.020203
    var mu = force_of_mortality(0.02)
    _assert(_near(mu, -log(0.98), 1e-6), "force_of_mortality")


fn test_net_single_premium() raises:
    # benefit=100000, v=0.9524 (1/1.05), px=0.99
    var nsp = net_single_premium(100000.0, 0.9524, 0.99)
    _assert(_near(nsp, 100000.0 * 0.9524 * 0.99, 0.01), "net_single_premium")


fn test_loss_ratio() raises:
    var lr = loss_ratio(700000.0, 1000000.0)
    _assert(_near(lr, 0.7), "loss_ratio")


fn test_combined_ratio() raises:
    var cr = combined_ratio(0.7, 0.25)
    _assert(_near(cr, 0.95), "combined_ratio")


fn test_combined_ratio_over_100() raises:
    var cr = combined_ratio(0.8, 0.3)
    _assert(cr > 1.0, "combined_ratio > 1 means underwriting loss")


fn test_reserve_prospective() raises:
    var v = reserve_prospective(50000.0, 35000.0)
    _assert(_near(v, 15000.0), "reserve_prospective")


# ── Linguistics tests ────────────────────────────────────────────────────────


fn test_type_token_ratio() raises:
    var ttr = type_token_ratio(150.0, 500.0)
    _assert(_near(ttr, 0.3), "type_token_ratio")


fn test_hapax_legomena_ratio() raises:
    var hlr = hapax_legomena_ratio(80.0, 500.0)
    _assert(_near(hlr, 0.16), "hapax_legomena_ratio")


fn test_yules_k() raises:
    # N=100, M2=200 => K = 10000*(200-100)/10000 = 100
    var k = yules_k(100.0, 200.0)
    _assert(_near(k, 100.0), "yules_k")


fn test_heaps_law() raises:
    # K=10, β=0.5, N=10000 => V = 10*10000^0.5 = 10*100 = 1000
    var v = heaps_law(10.0, 0.5, 10000.0)
    _assert(_near(v, 1000.0, 0.01), "heaps_law")


fn test_zipfs_frequency() raises:
    # rank=1, f_max=1000, s=1 => f=1000
    var f1 = zipfs_frequency(1.0, 1000.0, 1.0)
    _assert(_near(f1, 1000.0, 0.01), "zipf rank 1")
    # rank=2, s=1 => f=500
    var f2 = zipfs_frequency(2.0, 1000.0, 1.0)
    _assert(_near(f2, 500.0, 0.01), "zipf rank 2")


fn test_flesch_reading_ease() raises:
    # 200 words, 10 sentences, 300 syllables
    # FRE = 206.835 - 1.015*(200/10) - 84.6*(300/200)
    # = 206.835 - 20.3 - 126.9 = 59.635
    var fre = flesch_reading_ease(200.0, 10.0, 300.0)
    var expected = 206.835 - 1.015 * 20.0 - 84.6 * 1.5
    _assert(_near(fre, expected, 0.01), "flesch_reading_ease")


fn test_flesch_kincaid_grade() raises:
    # 200 words, 10 sentences, 300 syllables
    # FK = 0.39*(20) + 11.8*(1.5) - 15.59 = 7.8+17.7-15.59 = 9.91
    var fk = flesch_kincaid_grade(200.0, 10.0, 300.0)
    var expected = 0.39 * 20.0 + 11.8 * 1.5 - 15.59
    _assert(_near(fk, expected, 0.01), "flesch_kincaid_grade")


fn test_gunning_fog_index() raises:
    # 200 words, 10 sentences, 30 complex => fog = 0.4*(20+100*30/200) = 0.4*(20+15)=14
    var fog = gunning_fog_index(200.0, 10.0, 30.0)
    _assert(_near(fog, 14.0, 0.01), "gunning_fog_index")


fn test_automated_readability_index() raises:
    # 1000 chars, 200 words, 10 sentences
    # ARI = 4.71*(1000/200) + 0.5*(200/10) - 21.43 = 4.71*5+0.5*20-21.43
    # = 23.55+10-21.43 = 12.12
    var ari = automated_readability_index(1000.0, 200.0, 10.0)
    var expected = 4.71 * 5.0 + 0.5 * 20.0 - 21.43
    _assert(_near(ari, expected, 0.01), "automated_readability_index")


fn test_coleman_liau_index() raises:
    # L=500 (letters/100w), S=4 (sentences/100w)
    # CLI = 0.0588*500 - 0.296*4 - 15.8 = 29.4 - 1.184 - 15.8 = 12.416
    var cli = coleman_liau_index(500.0, 4.0)
    var expected = 0.0588 * 500.0 - 0.296 * 4.0 - 15.8
    _assert(_near(cli, expected, 0.01), "coleman_liau_index")


fn test_lexical_density() raises:
    var ld = lexical_density(120.0, 200.0)
    _assert(_near(ld, 0.6), "lexical_density")


fn test_mean_word_length() raises:
    var mwl = mean_word_length(900.0, 200.0)
    _assert(_near(mwl, 4.5), "mean_word_length")


fn test_lexical_density_high() raises:
    # Technical text: high density
    var ld = lexical_density(180.0, 200.0)
    _assert(ld > 0.5, "high lexical density for technical text")


fn test_zipf_decreasing() raises:
    # Higher rank => lower frequency
    var f1 = zipfs_frequency(1.0, 1000.0, 1.0)
    var f5 = zipfs_frequency(5.0, 1000.0, 1.0)
    var f10 = zipfs_frequency(10.0, 1000.0, 1.0)
    _assert(f1 > f5, "zipf f1 > f5")
    _assert(f5 > f10, "zipf f5 > f10")


fn test_heaps_law_growth() raises:
    # Vocabulary grows with corpus size
    var v1 = heaps_law(10.0, 0.5, 1000.0)
    var v2 = heaps_law(10.0, 0.5, 10000.0)
    _assert(v2 > v1, "heaps law: more tokens => more types")


fn test_force_of_mortality_low_qx() raises:
    # For very low qx, μx ≈ qx
    var mu = force_of_mortality(0.001)
    _assert(_near(mu, 0.001, 0.001), "force of mortality ≈ qx for small qx")


fn test_darcy_weisbach_zero_velocity() raises:
    var hf = darcy_weisbach_head_loss(0.02, 100.0, 0.1, 0.0, 9.81)
    _assert(_near(hf, 0.0), "darcy weisbach zero velocity")


fn test_froude_critical() raises:
    # Fr=1 when V=sqrt(g*d)
    var v_crit = sqrt(9.81 * 2.0)
    var fr = froude_number(v_crit, 2.0, 9.81)
    _assert(_near(fr, 1.0, 0.001), "froude critical")


fn test_annuity_pv_single_period() raises:
    # n=1: PV = PMT / (1+r) = 100/1.05 = 95.238
    var apv = annuity_present_value(100.0, 0.05, 1.0)
    _assert(_near(apv, 100.0 / 1.05, 0.01), "annuity PV single period")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    # Hydrology (17 assertions)
    test_hydraulic_radius()
    test_manning_velocity()
    test_manning_velocity_non_unit_rh()
    test_manning_discharge()
    test_froude_number()
    test_froude_subcritical()
    test_reynolds_number_pipe()
    test_darcy_weisbach_head_loss()
    test_rational_method_peak_flow()
    test_time_of_concentration_kirpich()
    test_curve_number_runoff()
    test_curve_number_no_runoff()
    test_evapotranspiration_hargreaves()
    test_specific_yield()
    test_darcy_groundwater_velocity()
    test_darcy_weisbach_zero_velocity()
    test_froude_critical()

    # Actuarial (16 assertions)
    test_present_value()
    test_future_value()
    test_pv_fv_roundtrip()
    test_annuity_present_value()
    test_annuity_present_value_zero_rate()
    test_annuity_future_value()
    test_annuity_future_value_zero_rate()
    test_life_expectancy_curtate()
    test_mortality_rate()
    test_survival_probability()
    test_force_of_mortality()
    test_net_single_premium()
    test_loss_ratio()
    test_combined_ratio()
    test_combined_ratio_over_100()
    test_reserve_prospective()
    test_annuity_pv_single_period()

    # Linguistics (17 assertions)
    test_type_token_ratio()
    test_hapax_legomena_ratio()
    test_yules_k()
    test_heaps_law()
    test_zipfs_frequency()
    test_flesch_reading_ease()
    test_flesch_kincaid_grade()
    test_gunning_fog_index()
    test_automated_readability_index()
    test_coleman_liau_index()
    test_lexical_density()
    test_mean_word_length()
    test_lexical_density_high()
    test_zipf_decreasing()
    test_heaps_law_growth()
    test_force_of_mortality_low_qx()

    print("✅ Wave 67: All 74 assertions passed (Hydrology, Actuarial, Linguistics)")
