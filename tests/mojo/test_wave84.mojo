"""Tests for Wave 84 — Telecommunications, Composites, Demographics."""

from telecommunications import (
    shannon_capacity,
    erlang_b,
    bit_error_rate_bpsk,
    spectral_efficiency,
    link_margin,
    thermal_noise_power,
    signal_to_noise_ratio,
    snr_db,
    data_rate_nyquist,
    propagation_delay,
    throughput,
    availability_percentage,
)
from composites import (
    rule_of_mixtures_modulus,
    inverse_rule_of_mixtures,
    composite_density,
    fiber_volume_fraction,
    laminate_thickness,
    specific_stiffness,
    specific_strength,
    halpin_tsai,
    critical_fiber_length,
    shear_lag_stress_transfer,
    impact_energy_charpy,
    void_content,
)
from demographics import (
    crude_birth_rate,
    crude_death_rate,
    natural_increase_rate,
    total_fertility_rate,
    infant_mortality_rate,
    life_expectancy_approx,
    dependency_ratio,
    sex_ratio,
    population_growth_rate,
    doubling_time,
    urbanization_rate,
    median_age_estimate,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


fn rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Telecommunications Tests ─────────────────────────────────────────────────


fn test_telecommunications() raises:
    # shannon_capacity: 1MHz * log2(1+100) = 1e6 * log2(101) ≈ 6.66e6
    var sc = shannon_capacity(1e6, 100.0)
    assert_true(rel_eq(sc, 1e6 * log(101.0) / log(2.0)), "shannon cap")
    assert_true(approx_eq(shannon_capacity(0.0, 10.0), 0.0), "shannon zero bw")

    # erlang_b: N=0 → 1/(1) = 1.0 (all calls blocked)
    assert_true(approx_eq(erlang_b(0, 5.0), 1.0), "erlang_b N=0")
    # erlang_b: N=10, A=5.0 — should be small blocking prob
    var eb = erlang_b(10, 5.0)
    assert_true(eb > 0.0 and eb < 0.05, "erlang_b N=10 A=5")

    # bit_error_rate_bpsk: BER = 0.5*exp(-10) ≈ 2.27e-5
    assert_true(rel_eq(bit_error_rate_bpsk(10.0), 0.5 * exp(-10.0)), "ber bpsk 10")
    assert_true(approx_eq(bit_error_rate_bpsk(0.0), 0.5), "ber bpsk 0")
    # negative SNR → 0.5
    assert_true(approx_eq(bit_error_rate_bpsk(-1.0), 0.5), "ber bpsk neg")

    # spectral_efficiency: 10Mbps / 2MHz = 5.0 bits/s/Hz
    assert_true(approx_eq(spectral_efficiency(10e6, 2e6), 5.0), "spec eff")
    assert_true(approx_eq(spectral_efficiency(10e6, 0.0), 0.0), "spec eff zero bw")

    # link_margin: -50 - (-90) = 40 dB
    assert_true(approx_eq(link_margin(-50.0, -90.0), 40.0), "link margin")
    assert_true(approx_eq(link_margin(-90.0, -90.0), 0.0), "link margin zero")

    # thermal_noise_power: k*T*B = 1.38e-23 * 290 * 1e6 ≈ 4.002e-15
    var tn = thermal_noise_power(1e6, 290.0)
    assert_true(rel_eq(tn, 1.38e-23 * 290.0 * 1e6), "thermal noise")

    # signal_to_noise_ratio: 100/10 = 10.0
    assert_true(approx_eq(signal_to_noise_ratio(100.0, 10.0), 10.0), "snr lin")
    assert_true(approx_eq(signal_to_noise_ratio(100.0, 0.0), 0.0), "snr zero noise")

    # snr_db: 10*log10(100) = 20 dB
    assert_true(rel_eq(snr_db(100.0), 20.0), "snr_db 100")
    assert_true(rel_eq(snr_db(10.0), 10.0), "snr_db 10")
    assert_true(approx_eq(snr_db(0.0), 0.0), "snr_db zero")

    # data_rate_nyquist: 2*1e6*log2(16) = 2e6*4 = 8e6
    assert_true(rel_eq(data_rate_nyquist(1e6, 16.0), 8e6), "nyquist 16")
    assert_true(approx_eq(data_rate_nyquist(1e6, 1.0), 0.0), "nyquist 1 level")

    # propagation_delay: 300km / 3e8 m/s = 1e-3 s
    assert_true(rel_eq(propagation_delay(300000.0, 3e8), 1e-3), "prop delay")
    assert_true(approx_eq(propagation_delay(100.0, 0.0), 0.0), "prop delay zero v")

    # throughput: 1e6 bits / 0.5s = 2e6 bps
    assert_true(approx_eq(throughput(1e6, 0.5), 2e6), "throughput")
    assert_true(approx_eq(throughput(1e6, 0.0), 0.0), "throughput zero t")

    # availability_percentage: 8760/8760 = 100%
    assert_true(approx_eq(availability_percentage(8760.0, 8760.0), 100.0), "avail 100")
    assert_true(approx_eq(availability_percentage(8000.0, 8760.0), 8000.0 / 8760.0 * 100.0), "avail partial")

    print("  ✓ telecommunications (28 assertions)")


# ── Composites Tests ─────────────────────────────────────────────────────────


fn test_composites() raises:
    # rule_of_mixtures_modulus: 0.6*230 + 0.4*3.5 = 138+1.4 = 139.4
    assert_true(approx_eq(rule_of_mixtures_modulus(0.6, 230.0, 3.5), 139.4), "rom E1")
    # pure matrix: 0*230 + 1*3.5 = 3.5
    assert_true(approx_eq(rule_of_mixtures_modulus(0.0, 230.0, 3.5), 3.5), "rom pure matrix")

    # inverse_rule_of_mixtures: 1/(0.6/230 + 0.4/3.5) = 1/(0.002609+0.11429) = 8.555
    var irom = inverse_rule_of_mixtures(0.6, 230.0, 3.5)
    assert_true(rel_eq(irom, 1.0 / (0.6 / 230.0 + 0.4 / 3.5)), "irom E2")
    assert_true(approx_eq(inverse_rule_of_mixtures(0.5, 0.0, 3.5), 0.0), "irom zero Ef")

    # composite_density: 0.6*1800 + 0.4*1200 = 1080+480 = 1560
    assert_true(approx_eq(composite_density(0.6, 1800.0, 1200.0), 1560.0), "comp density")

    # fiber_volume_fraction: (100/1800)/((100/1800)+(200/1200)) = 0.05556/0.22222 = 0.25
    var fvf = fiber_volume_fraction(100.0, 1800.0, 200.0, 1200.0)
    assert_true(rel_eq(fvf, (100.0 / 1800.0) / (100.0 / 1800.0 + 200.0 / 1200.0)), "fvf")
    assert_true(approx_eq(fiber_volume_fraction(100.0, 0.0, 200.0, 1200.0), 0.0), "fvf zero ρf")

    # laminate_thickness: 16 * 0.125 = 2.0 mm
    assert_true(approx_eq(laminate_thickness(16.0, 0.125), 2.0), "lam thick")

    # specific_stiffness: 70e9 / 2700 ≈ 25925925.93
    assert_true(rel_eq(specific_stiffness(70e9, 2700.0), 70e9 / 2700.0), "spec stiff")
    assert_true(approx_eq(specific_stiffness(70e9, 0.0), 0.0), "spec stiff zero ρ")

    # specific_strength: 500e6 / 2700 ≈ 185185.19
    assert_true(rel_eq(specific_strength(500e6, 2700.0), 500e6 / 2700.0), "spec str")

    # halpin_tsai: Ef=230, Em=3.5, Vf=0.6, ξ=2
    # η = (230/3.5-1)/(230/3.5+2) = (65.714-1)/(65.714+2) = 64.714/67.714 ≈ 0.9557
    # E = 3.5*(1+2*0.9557*0.6)/(1-0.9557*0.6) = 3.5*(2.1469)/(0.4266) ≈ 17.62
    var ht = halpin_tsai(0.6, 230.0, 3.5, 2.0)
    var eta = (230.0 / 3.5 - 1.0) / (230.0 / 3.5 + 2.0)
    var expected_ht = 3.5 * (1.0 + 2.0 * eta * 0.6) / (1.0 - eta * 0.6)
    assert_true(rel_eq(ht, expected_ht), "halpin-tsai")
    assert_true(approx_eq(halpin_tsai(0.5, 100.0, 0.0, 2.0), 0.0), "ht zero Em")

    # critical_fiber_length: 3500*0.007/(2*50) = 24.5/100 = 0.245 mm
    assert_true(rel_eq(critical_fiber_length(3500.0, 0.007, 50.0), 0.245), "crit fiber len")
    assert_true(approx_eq(critical_fiber_length(3500.0, 0.007, 0.0), 0.0), "crit fiber zero τ")

    # shear_lag_stress_transfer: 100*(1+50*0.6/2) = 100*16 = 1600
    assert_true(approx_eq(shear_lag_stress_transfer(100.0, 50.0, 0.6), 1600.0), "shear lag")
    # zero fiber → just applied stress
    assert_true(approx_eq(shear_lag_stress_transfer(100.0, 50.0, 0.0), 100.0), "shear lag zero Vf")

    # impact_energy_charpy: 5.0 / 0.0001 = 50000 J/m²
    assert_true(approx_eq(impact_energy_charpy(5.0, 0.0001), 50000.0), "charpy")
    assert_true(approx_eq(impact_energy_charpy(5.0, 0.0), 0.0), "charpy zero area")

    # void_content: (1600-1560)/1600 * 100 = 2.5%
    assert_true(approx_eq(void_content(1600.0, 1560.0), 2.5), "void content")
    assert_true(approx_eq(void_content(0.0, 1560.0), 0.0), "void zero theo")

    print("  ✓ composites (24 assertions)")


# ── Demographics Tests ───────────────────────────────────────────────────────


fn test_demographics() raises:
    # crude_birth_rate: 50000/5000000 * 1000 = 10.0
    assert_true(approx_eq(crude_birth_rate(50000.0, 5000000.0), 10.0), "cbr")
    assert_true(approx_eq(crude_birth_rate(100.0, 0.0), 0.0), "cbr zero pop")

    # crude_death_rate: 40000/5000000 * 1000 = 8.0
    assert_true(approx_eq(crude_death_rate(40000.0, 5000000.0), 8.0), "cdr")
    assert_true(approx_eq(crude_death_rate(100.0, 0.0), 0.0), "cdr zero pop")

    # natural_increase_rate: 10.0 - 8.0 = 2.0
    assert_true(approx_eq(natural_increase_rate(10.0, 8.0), 2.0), "nir")
    assert_true(approx_eq(natural_increase_rate(8.0, 8.0), 0.0), "nir zero")

    # total_fertility_rate: 0.4 * 5 = 2.0 (sum of ASFR * interval)
    assert_true(approx_eq(total_fertility_rate(0.4, 5.0), 2.0), "tfr")
    assert_true(approx_eq(total_fertility_rate(0.0, 5.0), 0.0), "tfr zero rates")

    # infant_mortality_rate: 500/50000 * 1000 = 10.0
    assert_true(approx_eq(infant_mortality_rate(500.0, 50000.0), 10.0), "imr")
    assert_true(approx_eq(infant_mortality_rate(500.0, 0.0), 0.0), "imr zero births")

    # life_expectancy_approx: 350000000/5000000 = 70.0
    assert_true(approx_eq(life_expectancy_approx(350000000.0, 5000000.0), 70.0), "le")
    assert_true(approx_eq(life_expectancy_approx(100.0, 0.0), 0.0), "le zero pop")

    # dependency_ratio: (1500000+500000)/3000000 * 100 = 66.67
    assert_true(rel_eq(dependency_ratio(1500000.0, 500000.0, 3000000.0), 66.6667), "dr")
    assert_true(approx_eq(dependency_ratio(100.0, 50.0, 0.0), 0.0), "dr zero work")

    # sex_ratio: 2450000/2550000 * 100 = 96.08
    assert_true(rel_eq(sex_ratio(2450000.0, 2550000.0), 2450000.0 / 2550000.0 * 100.0), "sr")
    assert_true(approx_eq(sex_ratio(100.0, 0.0), 0.0), "sr zero females")

    # population_growth_rate: (50000-40000+5000)/5000000 * 100 = 0.3%
    assert_true(approx_eq(population_growth_rate(50000.0, 40000.0, 5000.0, 5000000.0), 0.3), "pgr")
    assert_true(approx_eq(population_growth_rate(50000.0, 40000.0, 5000.0, 0.0), 0.0), "pgr zero pop")

    # doubling_time: 70/2.0 = 35.0
    assert_true(approx_eq(doubling_time(2.0), 35.0), "dt rule70")
    assert_true(approx_eq(doubling_time(0.0), 0.0), "dt zero rate")

    # urbanization_rate: 3500000/5000000 * 100 = 70.0%
    assert_true(approx_eq(urbanization_rate(3500000.0, 5000000.0), 70.0), "urban rate")
    assert_true(approx_eq(urbanization_rate(100.0, 0.0), 0.0), "urban zero pop")

    # median_age_estimate: 15 + 50*(1-30/100) - 10*(15/100) = 15+35-1.5 = 48.5
    assert_true(approx_eq(median_age_estimate(30.0, 15.0), 48.5), "median age")
    # young=0, old=0 → 15+50 = 65
    assert_true(approx_eq(median_age_estimate(0.0, 0.0), 65.0), "median age zero")

    print("  ✓ demographics (26 assertions)")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 84 tests: Telecommunications, Composites, Demographics")
    test_telecommunications()
    test_composites()
    test_demographics()
    print("All Wave 84 tests passed! (78 assertions)")
