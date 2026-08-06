"""Wave 96 tests — timber, spectroscopy, project_management (70+ assertions)."""

from std.testing import assert_true, assert_false, assert_equal
from std.math import abs, log, exp, sqrt

# -- timber imports --
from timber import (
    board_feet,
    moisture_content,
    allowable_stress,
    modulus_of_rupture_adjusted,
    section_modulus_beam,
    moment_capacity,
    column_slenderness,
    wood_density_from_sg,
    shrinkage_estimate,
    fire_char_rate,
    remaining_section,
    log_volume_doyle,
)

# -- spectroscopy imports --
from spectroscopy import (
    wavenumber_from_wavelength,
    wavelength_from_wavenumber,
    energy_from_wavelength,
    absorbance_from_transmittance,
    transmittance_from_absorbance,
    beer_lambert_concentration,
    resolution_spectrometer,
    snr_coadd,
    raman_shift,
    fluorescence_quantum_yield,
    stokes_shift,
    spectral_bandwidth,
)

# -- project_management imports --
from project_management import (
    earned_value,
    schedule_variance,
    cost_variance,
    schedule_performance_index,
    cost_performance_index,
    estimate_at_completion,
    estimate_to_complete,
    variance_at_completion,
    to_complete_performance_index,
    critical_path_duration,
    float_time,
    pert_estimate,
)


def approx(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    if abs(b) < 1e-12:
        return abs(a - b) < tol
    return abs(a - b) / abs(b) < tol


def main() raises:
    print("=== Wave 96 Tests ===")
    var t = 0

    # ── Timber ──────────────────────────────────────────
    # board_feet: 2 * 6 * 8 / 12 = 8.0
    assert_true(approx(board_feet(2.0, 6.0, 8.0), 8.0), "timber bf 1")
    t += 1
    # board_feet: 1 * 12 * 10 / 12 = 10.0
    assert_true(approx(board_feet(1.0, 12.0, 10.0), 10.0), "timber bf 2")
    t += 1

    # moisture_content: (150-100)/100*100 = 50
    assert_true(approx(moisture_content(150.0, 100.0), 50.0), "timber mc 1")
    t += 1
    # mc zero dry
    assert_true(approx(moisture_content(100.0, 0.0), 0.0), "timber mc zero")
    t += 1

    # allowable_stress: 1000*1.15*1.0*0.85 = 977.5
    assert_true(approx(allowable_stress(1000.0, 1.15, 1.0, 0.85), 977.5), "timber allow stress")
    t += 1

    # modulus_of_rupture_adjusted: 5000 * 0.9 = 4500
    assert_true(approx(modulus_of_rupture_adjusted(5000.0, 0.9), 4500.0), "timber mor adj")
    t += 1

    # section_modulus_beam: 5*10^2/6 = 83.3333
    assert_true(approx(section_modulus_beam(5.0, 10.0), 83.333333, 1e-4), "timber section mod")
    t += 1

    # moment_capacity: 1200 * 83.333 = 100000 (approx)
    assert_true(approx(moment_capacity(1200.0, 83.333333), 100000.0, 1e-3), "timber moment cap")
    t += 1

    # column_slenderness: 120 / 5.5 = 21.818...
    assert_true(approx(column_slenderness(120.0, 5.5), 21.818181, 1e-4), "timber col slender")
    t += 1
    # slenderness zero dim
    assert_true(approx(column_slenderness(120.0, 0.0), 0.0), "timber col slender zero")
    t += 1

    # wood_density_from_sg: 0.5 * 1000 = 500
    assert_true(approx(wood_density_from_sg(0.5, 1000.0), 500.0), "timber density")
    t += 1

    # shrinkage_estimate: 8.0 * (28-12)/30 = 4.2667
    assert_true(approx(shrinkage_estimate(28.0, 12.0, 8.0, 30.0), 4.266666, 1e-4), "timber shrinkage")
    t += 1
    # shrinkage fsp zero
    assert_true(approx(shrinkage_estimate(28.0, 12.0, 8.0, 0.0), 0.0), "timber shrinkage zero fsp")
    t += 1

    # fire_char_rate: 60 * 0.635 = 38.1
    assert_true(approx(fire_char_rate(60.0, 0.635), 38.1), "timber char rate")
    t += 1

    # remaining_section: 200 - 2*38.1 = 123.8
    assert_true(approx(remaining_section(200.0, 38.1), 123.8), "timber remaining")
    t += 1

    # log_volume_doyle: (20-4)^2*16/16 = 256
    assert_true(approx(log_volume_doyle(20.0, 16.0), 256.0), "timber doyle 1")
    t += 1
    # doyle: (12-4)^2*10/16 = 40
    assert_true(approx(log_volume_doyle(12.0, 10.0), 40.0), "timber doyle 2")
    t += 1

    # ── Spectroscopy ────────────────────────────────────
    # wavenumber_from_wavelength: 10000/2.5 = 4000
    assert_true(approx(wavenumber_from_wavelength(2.5), 4000.0), "spec wavenumber")
    t += 1
    # wavenumber zero
    assert_true(approx(wavenumber_from_wavelength(0.0), 0.0), "spec wavenumber zero")
    t += 1

    # wavelength_from_wavenumber: 10000/4000 = 2.5
    assert_true(approx(wavelength_from_wavenumber(4000.0), 2.5), "spec wavelength")
    t += 1
    # wavelength zero
    assert_true(approx(wavelength_from_wavenumber(0.0), 0.0), "spec wavelength zero")
    t += 1

    # energy_from_wavelength: hc/500e-9 = 3.9756e-19
    var e_val = energy_from_wavelength(500.0e-9)
    assert_true(approx(e_val, 3.9756e-19, 1e-3), "spec energy")
    t += 1
    # energy zero wavelength
    assert_true(approx(energy_from_wavelength(0.0), 0.0), "spec energy zero")
    t += 1

    # absorbance_from_transmittance: -log10(50/100) = 0.30103
    assert_true(approx(absorbance_from_transmittance(50.0), 0.30103, 1e-4), "spec absorbance")
    t += 1
    # absorbance 100% T => 0
    assert_true(approx(absorbance_from_transmittance(100.0), 0.0, 1e-6), "spec absorbance 100")
    t += 1
    # absorbance zero T
    assert_true(approx(absorbance_from_transmittance(0.0), 0.0), "spec absorbance zero T")
    t += 1

    # transmittance_from_absorbance: 10^(-0.30103)*100 = 50
    assert_true(approx(transmittance_from_absorbance(0.30103), 50.0, 1e-3), "spec transmittance")
    t += 1
    # transmittance A=0 => 100
    assert_true(approx(transmittance_from_absorbance(0.0), 100.0), "spec transmittance zero")
    t += 1

    # beer_lambert_concentration: 0.5 / (100 * 1.0) = 0.005
    assert_true(approx(beer_lambert_concentration(0.5, 1.0, 100.0), 0.005), "spec beer lambert")
    t += 1
    # beer lambert zero denom
    assert_true(approx(beer_lambert_concentration(0.5, 0.0, 100.0), 0.0), "spec beer lambert zero")
    t += 1

    # resolution_spectrometer: 500 / 0.1 = 5000
    assert_true(approx(resolution_spectrometer(500.0, 0.1), 5000.0), "spec resolution")
    t += 1
    # resolution zero delta
    assert_true(approx(resolution_spectrometer(500.0, 0.0), 0.0), "spec resolution zero")
    t += 1

    # snr_coadd: 10 * sqrt(16) = 40
    assert_true(approx(snr_coadd(10.0, 16.0), 40.0), "spec snr coadd")
    t += 1
    # snr_coadd: 5 * sqrt(100) = 50
    assert_true(approx(snr_coadd(5.0, 100.0), 50.0), "spec snr coadd 2")
    t += 1

    # raman_shift: (1/532 - 1/580) * 1e7 = 1556.66 approx
    var rs = raman_shift(532.0, 580.0)
    assert_true(approx(rs, 1556.17, 1e-2), "spec raman shift")
    t += 1
    # raman shift zero
    assert_true(approx(raman_shift(0.0, 580.0), 0.0), "spec raman zero")
    t += 1

    # fluorescence_quantum_yield: 80/100 = 0.8
    assert_true(approx(fluorescence_quantum_yield(80.0, 100.0), 0.8), "spec fluor qy")
    t += 1
    # qy zero absorbed
    assert_true(approx(fluorescence_quantum_yield(80.0, 0.0), 0.0), "spec fluor qy zero")
    t += 1

    # stokes_shift: 520 - 480 = 40
    assert_true(approx(stokes_shift(480.0, 520.0), 40.0), "spec stokes shift")
    t += 1

    # spectral_bandwidth: pass-through
    assert_true(approx(spectral_bandwidth(2.5), 2.5), "spec bandwidth")
    t += 1

    # ── Project Management ──────────────────────────────
    # earned_value: 100000 * 50/100 = 50000
    assert_true(approx(earned_value(100000.0, 50.0), 50000.0), "pm ev")
    t += 1

    # schedule_variance: 50000 - 45000 = 5000
    assert_true(approx(schedule_variance(50000.0, 45000.0), 5000.0), "pm sv")
    t += 1

    # cost_variance: 50000 - 48000 = 2000
    assert_true(approx(cost_variance(50000.0, 48000.0), 2000.0), "pm cv")
    t += 1

    # schedule_performance_index: 50000/45000 = 1.1111
    assert_true(approx(schedule_performance_index(50000.0, 45000.0), 1.111111, 1e-4), "pm spi")
    t += 1
    # spi zero pv
    assert_true(approx(schedule_performance_index(50000.0, 0.0), 0.0), "pm spi zero")
    t += 1

    # cost_performance_index: 50000/48000 = 1.04167
    assert_true(approx(cost_performance_index(50000.0, 48000.0), 1.041666, 1e-4), "pm cpi")
    t += 1
    # cpi zero ac
    assert_true(approx(cost_performance_index(50000.0, 0.0), 0.0), "pm cpi zero")
    t += 1

    # estimate_at_completion: 100000 / 1.04167 = 96000.3 approx
    var cpi_val = cost_performance_index(50000.0, 48000.0)
    var eac_val = estimate_at_completion(100000.0, cpi_val)
    assert_true(approx(eac_val, 96000.0, 1e-2), "pm eac")
    t += 1
    # eac zero cpi
    assert_true(approx(estimate_at_completion(100000.0, 0.0), 0.0), "pm eac zero")
    t += 1

    # estimate_to_complete: 96000 - 48000 = 48000
    assert_true(approx(estimate_to_complete(96000.0, 48000.0), 48000.0), "pm etc")
    t += 1

    # variance_at_completion: 100000 - 96000 = 4000
    assert_true(approx(variance_at_completion(100000.0, 96000.0), 4000.0), "pm vac")
    t += 1

    # to_complete_performance_index: (100000-50000)/(100000-48000) = 50000/52000 = 0.96154
    assert_true(approx(to_complete_performance_index(100000.0, 50000.0, 48000.0), 0.961538, 1e-4), "pm tcpi")
    t += 1
    # tcpi zero denom (bac==ac)
    assert_true(approx(to_complete_performance_index(100000.0, 50000.0, 100000.0), 0.0), "pm tcpi zero")
    t += 1

    # critical_path_duration: pass-through
    assert_true(approx(critical_path_duration(45.0), 45.0), "pm cp duration")
    t += 1

    # float_time: 20 - 15 = 5
    assert_true(approx(float_time(20.0, 15.0), 5.0), "pm float")
    t += 1

    # pert_estimate: (2 + 4*5 + 14)/6 = 36/6 = 6
    assert_true(approx(pert_estimate(2.0, 5.0, 14.0), 6.0), "pm pert")
    t += 1
    # pert: (1 + 4*3 + 11)/6 = 24/6 = 4
    assert_true(approx(pert_estimate(1.0, 3.0, 11.0), 4.0), "pm pert 2")
    t += 1

    # ── Additional edge-case / cross-check assertions ──
    # timber: board_feet with zeros
    assert_true(approx(board_feet(0.0, 6.0, 8.0), 0.0), "timber bf zero")
    t += 1

    # spectroscopy: roundtrip wavenumber <-> wavelength
    var wn = wavenumber_from_wavelength(5.0)
    var wl = wavelength_from_wavenumber(wn)
    assert_true(approx(wl, 5.0), "spec roundtrip wn wl")
    t += 1

    # spectroscopy: roundtrip absorbance <-> transmittance
    var a_val = absorbance_from_transmittance(25.0)
    var t_val = transmittance_from_absorbance(a_val)
    assert_true(approx(t_val, 25.0, 1e-4), "spec roundtrip A T")
    t += 1

    # PM: negative schedule variance (behind schedule)
    assert_true(approx(schedule_variance(40000.0, 50000.0), -10000.0), "pm sv negative")
    t += 1

    # PM: negative cost variance (over budget)
    assert_true(approx(cost_variance(40000.0, 55000.0), -15000.0), "pm cv negative")
    t += 1

    # PM: SPI < 1 means behind schedule
    var spi_val = schedule_performance_index(40000.0, 50000.0)
    assert_true(spi_val < 1.0, "pm spi behind")
    t += 1

    # PM: CPI < 1 means over budget
    var cpi_val2 = cost_performance_index(40000.0, 55000.0)
    assert_true(cpi_val2 < 1.0, "pm cpi over budget")
    t += 1

    # timber: moment_capacity with zero
    assert_true(approx(moment_capacity(0.0, 83.333), 0.0), "timber moment zero")
    t += 1

    # spectroscopy: stokes shift negative (anti-Stokes)
    assert_true(approx(stokes_shift(520.0, 480.0), -40.0), "spec anti-stokes")
    t += 1

    # PM: float_time zero
    assert_true(approx(float_time(15.0, 15.0), 0.0), "pm float zero")
    t += 1

    # PM: earned_value 100% complete
    assert_true(approx(earned_value(200000.0, 100.0), 200000.0), "pm ev 100pct")
    t += 1

    # timber: wood density typical Douglas Fir SG=0.48
    assert_true(approx(wood_density_from_sg(0.48, 1000.0), 480.0), "timber density df")
    t += 1

    # spectroscopy: beer lambert typical
    assert_true(approx(beer_lambert_concentration(1.0, 1.0, 1000.0), 0.001), "spec beer typ")
    t += 1

    print("All", t, "Wave 96 assertions passed!")
