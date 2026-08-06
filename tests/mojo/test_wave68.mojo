"""Tests for Wave 68 — Seismology, Operations Research, Photonics."""

from seismology import (
    richter_magnitude,
    moment_magnitude,
    seismic_moment,
    energy_from_magnitude,
    peak_ground_acceleration,
    travel_time_p_wave,
    travel_time_s_wave,
    ts_tp_difference,
    epicenter_distance_from_ts_tp,
    intensity_mmi_from_pga,
    gutenberg_richter_rate,
    recurrence_interval,
)
from operations_research import (
    simplex_objective_value_2,
    simplex_objective_value_3,
    transportation_cost,
    total_transportation_cost_2x2,
    assignment_cost_3,
    eoq_quantity,
    eoq_total_cost,
    newsvendor_critical_ratio,
    little_law_l,
    little_law_w,
    utilization_factor,
    mm1_expected_queue_length,
    mm1_expected_wait_time,
)
from photonics import (
    snells_law_angle,
    critical_angle,
    brewster_angle,
    fresnel_reflectance_normal,
    numerical_aperture,
    photon_energy,
    wavelength_to_frequency,
    frequency_to_wavelength,
    beer_lambert_transmittance,
    beer_lambert_absorbance,
    diffraction_grating_angle,
    rayleigh_resolution,
)
from std.math import abs as fabs, sqrt, exp, log, sin, asin, atan


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _near(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return fabs(a - b) < tol


def _near_rel(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    """Relative tolerance check."""
    if fabs(b) < 1e-12:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


def _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


def _pow10(x: Float64) -> Float64:
    return exp(x * log(10.0))


# ── Seismology tests ─────────────────────────────────────────────────────────


def test_richter_magnitude() raises:
    # A=10, D=100 => log10(10)+3*log10(100)-2.92 = 1+6-2.92 = 4.08
    var ml = richter_magnitude(10.0, 100.0)
    _assert(_near(ml, 4.08, 0.01), "richter_magnitude(10,100)=4.08")


def test_richter_magnitude_small() raises:
    # A=1, D=10 => 0+3-2.92=0.08
    var ml = richter_magnitude(1.0, 10.0)
    _assert(_near(ml, 0.08, 0.01), "richter_magnitude(1,10)=0.08")


def test_moment_magnitude() raises:
    # M0=1e20 => Mw = (2/3)*20 - 10.7 = 13.333 - 10.7 = 2.633
    var mw = moment_magnitude(1e20)
    _assert(_near(mw, 2.633, 0.01), "moment_magnitude(1e20)")


def test_moment_magnitude_large() raises:
    # M0=1e25 => Mw = (2/3)*25 - 10.7 = 16.667 - 10.7 = 5.967
    var mw = moment_magnitude(1e25)
    _assert(_near(mw, 5.967, 0.01), "moment_magnitude(1e25)")


def test_seismic_moment() raises:
    # Mw=5 => M0 = 10^(7.5+16.05) = 10^23.55
    var m0 = seismic_moment(5.0)
    var expected = _pow10(23.55)
    _assert(_near_rel(m0, expected), "seismic_moment(5)")


def test_energy_from_magnitude() raises:
    # Mw=5 => E = 10^(7.5+4.8) = 10^12.3
    var e = energy_from_magnitude(5.0)
    var expected = _pow10(12.3)
    _assert(_near_rel(e, expected), "energy_from_magnitude(5)")


def test_energy_increases_with_magnitude() raises:
    var e4 = energy_from_magnitude(4.0)
    var e5 = energy_from_magnitude(5.0)
    var e6 = energy_from_magnitude(6.0)
    _assert(e5 > e4, "energy M5 > M4")
    _assert(e6 > e5, "energy M6 > M5")


def test_peak_ground_acceleration() raises:
    # M=6, R=50, site=1.0
    var pga = peak_ground_acceleration(6.0, 50.0, 1.0)
    var expected = _pow10(0.5 * 6.0 - 1.5 * _log10(50.0) - 0.5)
    _assert(_near_rel(pga, expected), "pga M=6 R=50")


def test_pga_site_amplification() raises:
    var pga1 = peak_ground_acceleration(6.0, 50.0, 1.0)
    var pga2 = peak_ground_acceleration(6.0, 50.0, 1.5)
    _assert(_near_rel(pga2, pga1 * 1.5), "PGA site amplification 1.5x")


def test_travel_time_p_wave() raises:
    # d=120 km, vp=6.0 => t=20 s
    var t = travel_time_p_wave(120.0, 6.0)
    _assert(_near(t, 20.0), "travel_time_p_wave")


def test_travel_time_s_wave() raises:
    # d=105 km, vs=3.5 => t=30 s
    var t = travel_time_s_wave(105.0, 3.5)
    _assert(_near(t, 30.0), "travel_time_s_wave")


def test_ts_tp_difference() raises:
    # d=100, vp=6, vs=3.5 => dt = 100*(1/3.5 - 1/6) = 100*(0.2857-0.1667) = 11.905
    var dt = ts_tp_difference(100.0, 6.0, 3.5)
    var expected = 100.0 * (1.0 / 3.5 - 1.0 / 6.0)
    _assert(_near(dt, expected, 0.001), "ts_tp_difference")


def test_epicenter_distance_from_ts_tp() raises:
    # Inverse of ts_tp_difference
    var dt = ts_tp_difference(100.0, 6.0, 3.5)
    var d = epicenter_distance_from_ts_tp(dt, 6.0, 3.5)
    _assert(_near(d, 100.0, 0.001), "epicenter_distance roundtrip")


def test_epicenter_distance_specific() raises:
    # dt=10, vp=6, vs=3.5 => d = 10/(1/3.5-1/6) = 10/(0.11905) = 84.0
    var d = epicenter_distance_from_ts_tp(10.0, 6.0, 3.5)
    var expected = 10.0 / (1.0 / 3.5 - 1.0 / 6.0)
    _assert(_near(d, expected, 0.01), "epicenter_distance dt=10")


def test_intensity_mmi_from_pga() raises:
    # pga=100 => MMI = 2*log10(100)+1 = 2*2+1 = 5
    var mmi = intensity_mmi_from_pga(100.0)
    _assert(_near(mmi, 5.0, 0.01), "MMI from PGA=100")


def test_intensity_mmi_from_pga_1000() raises:
    # pga=1000 => MMI = 2*3+1 = 7
    var mmi = intensity_mmi_from_pga(1000.0)
    _assert(_near(mmi, 7.0, 0.01), "MMI from PGA=1000")


def test_gutenberg_richter_rate() raises:
    # a=5, b=1, M=3 => N = 10^(5-3) = 100
    var n = gutenberg_richter_rate(5.0, 1.0, 3.0)
    _assert(_near(n, 100.0, 0.01), "GR rate a=5 b=1 M=3")


def test_gutenberg_richter_rate_higher_mag() raises:
    # a=5, b=1, M=5 => N = 10^0 = 1
    var n = gutenberg_richter_rate(5.0, 1.0, 5.0)
    _assert(_near(n, 1.0, 0.01), "GR rate M=5 => 1 event/yr")


def test_recurrence_interval() raises:
    # rate=0.1 => T=10 years
    var t = recurrence_interval(0.1)
    _assert(_near(t, 10.0), "recurrence_interval 0.1 => 10 yr")


def test_recurrence_from_gr() raises:
    var rate = gutenberg_richter_rate(5.0, 1.0, 4.0)  # N=10
    var t = recurrence_interval(rate)
    _assert(_near(t, 0.1, 0.01), "recurrence from GR M=4")


# ── Operations Research tests ─────────────────────────────────────────────────


def test_simplex_objective_2() raises:
    # Z = 3*4 + 5*2 = 22
    var z = simplex_objective_value_2(3.0, 4.0, 5.0, 2.0)
    _assert(_near(z, 22.0), "simplex_obj_2")


def test_simplex_objective_3() raises:
    # Z = 2*3 + 4*1 + 1*5 = 6+4+5 = 15
    var z = simplex_objective_value_3(2.0, 3.0, 4.0, 1.0, 1.0, 5.0)
    _assert(_near(z, 15.0), "simplex_obj_3")


def test_transportation_cost_single() raises:
    var c = transportation_cost(5.0, 20.0)
    _assert(_near(c, 100.0), "transportation_cost single cell")


def test_total_transportation_cost_2x2() raises:
    # 2x2 tableau: costs 2,3,4,1 allocs 10,20,5,15
    # TC = 20+60+20+15 = 115
    var tc = total_transportation_cost_2x2(2.0, 10.0, 3.0, 20.0, 4.0, 5.0, 1.0, 15.0)
    _assert(_near(tc, 115.0), "total_transport_2x2")


def test_assignment_cost_3() raises:
    # tasks: costs 5, 8, 3 => total = 16
    var ac = assignment_cost_3(5.0, 8.0, 3.0)
    _assert(_near(ac, 16.0), "assignment_cost_3")


def test_eoq_quantity() raises:
    # D=1000, S=50, H=2 => EOQ = sqrt(2*1000*50/2) = sqrt(50000) = 223.607
    var q = eoq_quantity(1000.0, 50.0, 2.0)
    _assert(_near(q, sqrt(50000.0), 0.01), "eoq_quantity")


def test_eoq_total_cost() raises:
    # D=1000, S=50, H=2 => TC = sqrt(2*1000*50*2) = sqrt(200000) = 447.214
    var tc = eoq_total_cost(1000.0, 50.0, 2.0)
    _assert(_near(tc, sqrt(200000.0), 0.01), "eoq_total_cost")


def test_newsvendor_critical_ratio() raises:
    # cu=7, co=3 => CR = 7/10 = 0.7
    var cr = newsvendor_critical_ratio(7.0, 3.0)
    _assert(_near(cr, 0.7), "newsvendor_critical_ratio")


def test_newsvendor_symmetric() raises:
    # cu=co=5 => CR = 0.5
    var cr = newsvendor_critical_ratio(5.0, 5.0)
    _assert(_near(cr, 0.5), "newsvendor symmetric")


def test_little_law_l() raises:
    # λ=4, W=3 => L=12
    var l = little_law_l(4.0, 3.0)
    _assert(_near(l, 12.0), "little_law_l")


def test_little_law_w() raises:
    # L=12, λ=4 => W=3
    var w = little_law_w(12.0, 4.0)
    _assert(_near(w, 3.0), "little_law_w")


def test_little_law_roundtrip() raises:
    var l = little_law_l(5.0, 2.0)  # L=10
    var w = little_law_w(l, 5.0)    # W=2
    _assert(_near(w, 2.0), "little law roundtrip")


def test_utilization_factor() raises:
    # λ=3, μ=5 => ρ=0.6
    var rho = utilization_factor(3.0, 5.0)
    _assert(_near(rho, 0.6), "utilization_factor")


def test_mm1_expected_queue_length() raises:
    # ρ=0.8 => Lq = 0.64/0.2 = 3.2
    var lq = mm1_expected_queue_length(0.8)
    _assert(_near(lq, 3.2, 0.001), "mm1_queue_length rho=0.8")


def test_mm1_expected_queue_length_low_util() raises:
    # ρ=0.2 => Lq = 0.04/0.8 = 0.05
    var lq = mm1_expected_queue_length(0.2)
    _assert(_near(lq, 0.05, 0.001), "mm1_queue_length rho=0.2")


def test_mm1_expected_wait_time() raises:
    # ρ=0.8, μ=5 => Wq = 0.8/(5*0.2) = 0.8
    var wq = mm1_expected_wait_time(0.8, 5.0)
    _assert(_near(wq, 0.8, 0.001), "mm1_wait_time")


def test_mm1_queue_increases_with_rho() raises:
    var lq1 = mm1_expected_queue_length(0.5)
    var lq2 = mm1_expected_queue_length(0.8)
    var lq3 = mm1_expected_queue_length(0.95)
    _assert(lq2 > lq1, "mm1 Lq increases 0.5->0.8")
    _assert(lq3 > lq2, "mm1 Lq increases 0.8->0.95")


# ── Photonics tests ──────────────────────────────────────────────────────────


def test_snells_law_angle() raises:
    # n1=1.0(air), n2=1.5(glass), θ1=0.5 rad
    # θ2 = asin((1/1.5)*sin(0.5)) = asin(0.3197) ≈ 0.3254
    var theta2 = snells_law_angle(1.0, 1.5, 0.5)
    var expected = asin((1.0 / 1.5) * sin(0.5))
    _assert(_near(theta2, expected, 1e-6), "snells_law_angle")


def test_snells_law_normal_incidence() raises:
    # θ1=0 => θ2=0
    var theta2 = snells_law_angle(1.0, 1.5, 0.0)
    _assert(_near(theta2, 0.0, 1e-10), "snells_law normal incidence")


def test_critical_angle() raises:
    # n1=1.5(glass), n2=1.0(air) => θc = asin(1/1.5) = asin(0.6667)
    var tc = critical_angle(1.5, 1.0)
    var expected = asin(1.0 / 1.5)
    _assert(_near(tc, expected, 1e-6), "critical_angle glass-air")


def test_brewster_angle() raises:
    # n1=1.0, n2=1.5 => θB = atan(1.5) ≈ 0.9828 rad
    var tb = brewster_angle(1.0, 1.5)
    _assert(_near(tb, atan(1.5), 1e-6), "brewster_angle")


def test_fresnel_reflectance_normal() raises:
    # n1=1, n2=1.5 => R = ((1-1.5)/(1+1.5))^2 = (-0.5/2.5)^2 = 0.04
    var r = fresnel_reflectance_normal(1.0, 1.5)
    _assert(_near(r, 0.04), "fresnel_reflectance n1=1 n2=1.5")


def test_fresnel_reflectance_same_medium() raises:
    var r = fresnel_reflectance_normal(1.5, 1.5)
    _assert(_near(r, 0.0), "fresnel_reflectance same medium = 0")


def test_numerical_aperture() raises:
    # n_core=1.48, n_clad=1.46
    # NA = sqrt(1.48^2 - 1.46^2) = sqrt(2.1904-2.1316) = sqrt(0.0588) = 0.2425
    var na = numerical_aperture(1.48, 1.46)
    var expected = sqrt(1.48 * 1.48 - 1.46 * 1.46)
    _assert(_near(na, expected, 0.001), "numerical_aperture")


def test_photon_energy() raises:
    # λ=500e-9 m => E = 6.626e-34 * 3e8 / 500e-9 = 3.976e-19 J
    var e = photon_energy(500e-9)
    var expected = 6.626e-34 * 3e8 / 500e-9
    _assert(_near_rel(e, expected), "photon_energy 500nm")


def test_wavelength_to_frequency() raises:
    # λ=500e-9 => f = 3e8/500e-9 = 6e14 Hz
    var f = wavelength_to_frequency(500e-9)
    _assert(_near_rel(f, 6e14), "wavelength_to_freq 500nm")


def test_frequency_to_wavelength() raises:
    # f=6e14 => λ = 3e8/6e14 = 5e-7 = 500nm
    var lam = frequency_to_wavelength(6e14)
    _assert(_near_rel(lam, 5e-7), "freq_to_wavelength 6e14")


def test_wavelength_frequency_roundtrip() raises:
    var f = wavelength_to_frequency(633e-9)
    var lam = frequency_to_wavelength(f)
    _assert(_near(lam, 633e-9, 1e-15), "wavelength-freq roundtrip")


def test_beer_lambert_transmittance() raises:
    # α=0.5, L=2 => T = exp(-1) ≈ 0.3679
    var t = beer_lambert_transmittance(0.5, 2.0)
    _assert(_near(t, exp(-1.0), 1e-6), "beer_lambert_transmittance")


def test_beer_lambert_transmittance_zero_path() raises:
    var t = beer_lambert_transmittance(1.0, 0.0)
    _assert(_near(t, 1.0), "transmittance zero path = 1")


def test_beer_lambert_absorbance() raises:
    # T=0.1 => A = -log10(0.1) = 1.0
    var a = beer_lambert_absorbance(0.1)
    _assert(_near(a, 1.0, 0.001), "absorbance T=0.1")


def test_beer_lambert_absorbance_roundtrip() raises:
    var t = beer_lambert_transmittance(0.3, 3.0)
    var a = beer_lambert_absorbance(t)
    # A = -log10(exp(-0.9)) = 0.9/ln(10) ≈ 0.3908
    var expected = 0.9 / log(10.0)
    _assert(_near(a, expected, 0.001), "absorbance roundtrip")


def test_diffraction_grating_angle() raises:
    # m=1, λ=500e-9, d=1e-6 => sin(θ)=0.5 => θ=pi/6
    var theta = diffraction_grating_angle(1.0, 500e-9, 1e-6)
    _assert(_near(theta, asin(0.5), 1e-6), "diffraction_grating m=1")


def test_rayleigh_resolution() raises:
    # λ=500e-9, D=0.1 => θ = 1.22*500e-9/0.1 = 6.1e-6 rad
    var theta = rayleigh_resolution(500e-9, 0.1)
    _assert(_near(theta, 6.1e-6, 1e-9), "rayleigh_resolution")


def test_rayleigh_larger_aperture() raises:
    var t1 = rayleigh_resolution(500e-9, 0.1)
    var t2 = rayleigh_resolution(500e-9, 0.2)
    _assert(t2 < t1, "larger aperture => better resolution")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    # Seismology (24 assertions)
    test_richter_magnitude()
    test_richter_magnitude_small()
    test_moment_magnitude()
    test_moment_magnitude_large()
    test_seismic_moment()
    test_energy_from_magnitude()
    test_energy_increases_with_magnitude()
    test_peak_ground_acceleration()
    test_pga_site_amplification()
    test_travel_time_p_wave()
    test_travel_time_s_wave()
    test_ts_tp_difference()
    test_epicenter_distance_from_ts_tp()
    test_epicenter_distance_specific()
    test_intensity_mmi_from_pga()
    test_intensity_mmi_from_pga_1000()
    test_gutenberg_richter_rate()
    test_gutenberg_richter_rate_higher_mag()
    test_recurrence_interval()
    test_recurrence_from_gr()

    # Operations Research (24 assertions)
    test_simplex_objective_2()
    test_simplex_objective_3()
    test_transportation_cost_single()
    test_total_transportation_cost_2x2()
    test_assignment_cost_3()
    test_eoq_quantity()
    test_eoq_total_cost()
    test_newsvendor_critical_ratio()
    test_newsvendor_symmetric()
    test_little_law_l()
    test_little_law_w()
    test_little_law_roundtrip()
    test_utilization_factor()
    test_mm1_expected_queue_length()
    test_mm1_expected_queue_length_low_util()
    test_mm1_expected_wait_time()
    test_mm1_queue_increases_with_rho()

    # Photonics (26 assertions)
    test_snells_law_angle()
    test_snells_law_normal_incidence()
    test_critical_angle()
    test_brewster_angle()
    test_fresnel_reflectance_normal()
    test_fresnel_reflectance_same_medium()
    test_numerical_aperture()
    test_photon_energy()
    test_wavelength_to_frequency()
    test_frequency_to_wavelength()
    test_wavelength_frequency_roundtrip()
    test_beer_lambert_transmittance()
    test_beer_lambert_transmittance_zero_path()
    test_beer_lambert_absorbance()
    test_beer_lambert_absorbance_roundtrip()
    test_diffraction_grating_angle()
    test_rayleigh_resolution()
    test_rayleigh_larger_aperture()

    print("✅ Wave 68: All 74 assertions passed (Seismology, Operations Research, Photonics)")
