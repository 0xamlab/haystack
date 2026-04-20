"""Tests for Wave 81 — Antenna, Toxicology, Elevator Engineering."""

from antenna import (
    dipole_length,
    wavelength_from_freq,
    friis_path_loss,
    eirp,
    received_power,
    directivity_from_beamwidths,
    antenna_efficiency,
    effective_aperture,
    link_budget_margin,
    noise_figure_to_noise_temp,
    free_space_loss_db,
    beamwidth_from_aperture,
)
from toxicology import (
    ld50_dose,
    therapeutic_index,
    margin_of_safety,
    bioconcentration_factor,
    hazard_quotient,
    hazard_index,
    cancer_risk,
    average_daily_dose,
    no_observed_adverse_effect_level,
    reference_dose,
    dose_response_hill,
    acute_exposure_ratio,
)
from elevator import (
    round_trip_time,
    handling_capacity,
    interval_time,
    probable_stops,
    motor_power,
    counterweight_mass,
    shaft_area,
    annual_energy_consumption,
    waiting_time_average,
    traffic_intensity,
    rope_factor_of_safety,
    pit_depth_requirement,
)
from std.testing import assert_true, assert_false, assert_equal
from std.math import abs as fabs, sqrt, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


fn approx_eq(a: Float64, b: Float64, tol: Float64 = 1e-4) -> Bool:
    return fabs(a - b) < tol


fn rel_eq(a: Float64, b: Float64, tol: Float64 = 1e-3) -> Bool:
    if fabs(b) < 1e-15:
        return fabs(a) < tol
    return fabs(a - b) / fabs(b) < tol


# ── Antenna Tests ────────────────────────────────────────────────────────────


fn test_antenna() raises:
    print("== Antenna Tests ==")

    # dipole_length: L = λ/2
    assert_true(approx_eq(dipole_length(1.0), 0.5), "dipole_length(1.0)")
    assert_true(approx_eq(dipole_length(0.3), 0.15), "dipole_length(0.3)")

    # wavelength_from_freq: λ = c/f
    assert_true(approx_eq(wavelength_from_freq(1.0e9), 0.3), "wavelength 1GHz")
    assert_true(approx_eq(wavelength_from_freq(3.0e8), 1.0), "wavelength 300MHz")
    assert_true(approx_eq(wavelength_from_freq(1.0e6), 300.0), "wavelength 1MHz")

    # friis_path_loss: 20*log10(4π*d/λ)
    # d=1000, λ=0.3 → 4π*1000/0.3 = 41887.9 → 20*log10(41887.9) ≈ 92.44
    var pl = friis_path_loss(1000.0, 0.3)
    assert_true(rel_eq(pl, 92.44, 0.01), "friis_path_loss")

    # eirp: Ptx + Gant
    assert_true(approx_eq(eirp(30.0, 6.0), 36.0), "eirp")
    assert_true(approx_eq(eirp(20.0, 10.0), 30.0), "eirp 2")

    # received_power: EIRP - PL + Grx
    assert_true(approx_eq(received_power(36.0, 92.0, 3.0), -53.0), "rx power")

    # directivity_from_beamwidths: 41253 / (θ * φ)
    assert_true(approx_eq(directivity_from_beamwidths(10.0, 10.0), 412.53), "directivity")
    assert_true(approx_eq(directivity_from_beamwidths(30.0, 30.0), 45.8366, 0.01), "directivity 2")

    # antenna_efficiency: η = G/D
    assert_true(approx_eq(antenna_efficiency(8.0, 10.0), 0.8), "efficiency")
    assert_true(approx_eq(antenna_efficiency(5.0, 10.0), 0.5), "efficiency 2")

    # effective_aperture: Ae = G*λ²/(4π)
    # G=10, λ=0.3 → 10*0.09/(4π) ≈ 0.07162
    var ae = effective_aperture(10.0, 0.3)
    assert_true(rel_eq(ae, 0.07162, 0.01), "effective_aperture")

    # link_budget_margin
    assert_true(approx_eq(link_budget_margin(-50.0, -90.0), 40.0), "link margin")
    assert_true(approx_eq(link_budget_margin(-80.0, -90.0), 10.0), "link margin 2")

    # noise_figure_to_noise_temp: Te = T0*(10^(NF/10) - 1)
    # NF=3dB → 10^0.3 ≈ 1.9953 → Te = 290*(0.9953) ≈ 288.63
    var te = noise_figure_to_noise_temp(3.0)
    assert_true(rel_eq(te, 288.63, 0.01), "noise_temp 3dB")
    # NF=0 → Te=0
    assert_true(approx_eq(noise_figure_to_noise_temp(0.0), 0.0, 0.01), "noise_temp 0dB")

    # free_space_loss_db: 32.45 + 20*log10(d_km) + 20*log10(f_MHz)
    # d=10km, f=1000MHz → 32.45 + 20 + 60 = 112.45
    assert_true(rel_eq(free_space_loss_db(10.0, 1000.0), 112.45, 0.001), "fsl_db")

    # beamwidth_from_aperture: θ ≈ 70*λ/D
    assert_true(approx_eq(beamwidth_from_aperture(0.03, 1.0), 2.1), "beamwidth")
    assert_true(approx_eq(beamwidth_from_aperture(0.3, 3.0), 7.0), "beamwidth 2")

    print("  All antenna tests passed ✓")


# ── Toxicology Tests ─────────────────────────────────────────────────────────


fn test_toxicology() raises:
    print("== Toxicology Tests ==")

    # ld50_dose: LD50 * BW
    assert_true(approx_eq(ld50_dose(50.0, 70.0), 3500.0), "ld50_dose")
    assert_true(approx_eq(ld50_dose(10.0, 80.0), 800.0), "ld50_dose 2")

    # therapeutic_index: TD50/ED50
    assert_true(approx_eq(therapeutic_index(100.0, 10.0), 10.0), "TI")
    assert_true(approx_eq(therapeutic_index(50.0, 25.0), 2.0), "TI 2")

    # margin_of_safety: TD01/ED99
    assert_true(approx_eq(margin_of_safety(20.0, 10.0), 2.0), "MOS")

    # bioconcentration_factor: Corg/Cwater
    assert_true(approx_eq(bioconcentration_factor(500.0, 0.5), 1000.0), "BCF")
    assert_true(approx_eq(bioconcentration_factor(10.0, 2.0), 5.0), "BCF 2")

    # hazard_quotient: ED/RfD
    assert_true(approx_eq(hazard_quotient(0.05, 0.01), 5.0), "HQ")
    assert_true(approx_eq(hazard_quotient(0.001, 0.01), 0.1), "HQ 2")

    # hazard_index: pass-through
    assert_true(approx_eq(hazard_index(3.5), 3.5), "HI")

    # cancer_risk: CDI * SF
    assert_true(approx_eq(cancer_risk(0.001, 0.05), 0.00005), "cancer_risk")

    # average_daily_dose: (C*IR*EF*ED)/(BW*AT)
    # C=0.1, IR=2, EF=350, ED=30, BW=70, AT=25550 → (0.1*2*350*30)/(70*25550)
    # = 2100 / 1788500 ≈ 0.001174
    var add = average_daily_dose(0.1, 2.0, 350.0, 30.0, 70.0, 25550.0)
    assert_true(rel_eq(add, 0.001174, 0.01), "ADD")

    # no_observed_adverse_effect_level: LOAEL/UF
    assert_true(approx_eq(no_observed_adverse_effect_level(100.0, 10.0), 10.0), "NOAEL")

    # reference_dose: NOAEL/UF
    assert_true(approx_eq(reference_dose(10.0, 100.0), 0.1), "RfD")
    assert_true(approx_eq(reference_dose(50.0, 1000.0), 0.05), "RfD 2")

    # dose_response_hill: Emax*D^n/(EC50^n + D^n)
    # D=50, Emax=100, EC50=50, n=1 → 100*50/(50+50) = 50
    assert_true(approx_eq(dose_response_hill(50.0, 100.0, 50.0, 1.0), 50.0), "Hill n=1")
    # D=100, Emax=100, EC50=50, n=1 → 100*100/(50+100) = 66.667
    assert_true(rel_eq(dose_response_hill(100.0, 100.0, 50.0, 1.0), 66.6667, 0.001), "Hill n=1 D=100")
    # D=50, Emax=100, EC50=50, n=2 → 100*2500/(2500+2500) = 50
    assert_true(approx_eq(dose_response_hill(50.0, 100.0, 50.0, 2.0), 50.0), "Hill n=2")
    # D=0 → 0
    assert_true(approx_eq(dose_response_hill(0.0, 100.0, 50.0, 1.0), 0.0), "Hill D=0")

    # acute_exposure_ratio: Cmeas/ATV
    assert_true(approx_eq(acute_exposure_ratio(5.0, 10.0), 0.5), "AER")
    assert_true(approx_eq(acute_exposure_ratio(20.0, 10.0), 2.0), "AER 2")

    print("  All toxicology tests passed ✓")


# ── Elevator Tests ───────────────────────────────────────────────────────────


fn test_elevator() raises:
    print("== Elevator Tests ==")

    # round_trip_time: 2*H/v + floors*door + passengers*2
    # floors=10, h=3, v=2, accel=1, door=3, pass=8
    # H=30, travel=30, doors=30, transfer=16 → 76
    var rtt = round_trip_time(10.0, 3.0, 2.0, 1.0, 3.0, 8.0)
    assert_true(approx_eq(rtt, 76.0), "RTT")

    # handling_capacity: cap*300/RTT
    # cap=10, RTT=76 → 39.4737
    assert_true(rel_eq(handling_capacity(10.0, 76.0), 39.4737, 0.001), "HC")

    # interval_time: RTT/n_cars
    assert_true(approx_eq(interval_time(76.0, 4.0), 19.0), "interval")
    assert_true(approx_eq(interval_time(100.0, 5.0), 20.0), "interval 2")

    # probable_stops: N*(1-(1-1/N)^P)
    # N=10, P=8 → 10*(1-(0.9)^8) = 10*(1-0.43047) = 5.6953
    var ps = probable_stops(10.0, 8.0)
    assert_true(rel_eq(ps, 5.6953, 0.001), "probable_stops")
    # N=1 → 1*(1-0^P) = 1
    assert_true(approx_eq(probable_stops(1.0, 5.0), 1.0), "probable_stops N=1")

    # motor_power: m*g*v/η
    # m=2000, g=9.81, v=2.5, η=0.85 → 57705.88
    var mp = motor_power(2000.0, 2.5, 9.81, 0.85)
    assert_true(rel_eq(mp, 57705.88, 0.001), "motor_power")

    # counterweight_mass: car + balance*load
    assert_true(approx_eq(counterweight_mass(3000.0, 2000.0, 0.4), 3800.0), "CW")
    assert_true(approx_eq(counterweight_mass(2500.0, 1500.0, 0.5), 3250.0), "CW 2")

    # shaft_area: (w+cl)*(d+cl)
    assert_true(approx_eq(shaft_area(2.0, 2.5, 0.2), 2.2 * 2.7), "shaft_area")

    # annual_energy_consumption: P*trips*t*days/3600
    # P=15, trips=200, t=30, days=365 → 15*200*30*365/3600 = 9125
    var aec = annual_energy_consumption(15.0, 200.0, 30.0, 365.0)
    assert_true(rel_eq(aec, 9125.0, 0.001), "annual_energy")

    # waiting_time_average: interval/2
    assert_true(approx_eq(waiting_time_average(20.0), 10.0), "avg_wait")
    assert_true(approx_eq(waiting_time_average(30.0), 15.0), "avg_wait 2")

    # traffic_intensity: arrivals/HC
    assert_true(approx_eq(traffic_intensity(30.0, 40.0), 0.75), "TI")
    assert_true(approx_eq(traffic_intensity(50.0, 50.0), 1.0), "TI 2")

    # rope_factor_of_safety: strength/load
    assert_true(approx_eq(rope_factor_of_safety(80000.0, 10000.0), 8.0), "FOS")

    # pit_depth_requirement: 0.5*v²/(2*g) + 0.5
    # v=2.5 → 0.5*6.25/19.62 + 0.5 = 0.15926 + 0.5 = 0.65926
    var pd = pit_depth_requirement(2.5)
    assert_true(rel_eq(pd, 0.65926, 0.01), "pit_depth")
    # v=0 → 0.5
    assert_true(approx_eq(pit_depth_requirement(0.0), 0.5), "pit_depth v=0")

    print("  All elevator tests passed ✓")


# ── main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 81 Tests ===")
    test_antenna()
    test_toxicology()
    test_elevator()
    print("=== All Wave 81 tests passed ✓ ===")
