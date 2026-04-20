"""bench_spectroscopy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from spectroscopy import wavenumber_from_wavelength, wavelength_from_wavenumber, energy_from_wavelength, absorbance_from_transmittance, transmittance_from_absorbance, beer_lambert_concentration, resolution_spectrometer, snr_coadd, raman_shift, fluorescence_quantum_yield, stokes_shift, spectral_bandwidth
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_wavenumber_from_wavelength: Float64 = 0.0
    var _t0_wavenumber_from_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_wavenumber_from_wavelength += wavenumber_from_wavelength(0.5)
    var _t1_wavenumber_from_wavelength = perf_counter_ns()
    var _ns_wavenumber_from_wavelength = Float64(_t1_wavenumber_from_wavelength - _t0_wavenumber_from_wavelength) / Float64(N)
    print("MOJO_TIMING spectroscopy::wavenumber_from_wavelength", _ns_wavenumber_from_wavelength, _acc_wavenumber_from_wavelength)
    var _acc_wavelength_from_wavenumber: Float64 = 0.0
    var _t0_wavelength_from_wavenumber = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_from_wavenumber += wavelength_from_wavenumber(0.5)
    var _t1_wavelength_from_wavenumber = perf_counter_ns()
    var _ns_wavelength_from_wavenumber = Float64(_t1_wavelength_from_wavenumber - _t0_wavelength_from_wavenumber) / Float64(N)
    print("MOJO_TIMING spectroscopy::wavelength_from_wavenumber", _ns_wavelength_from_wavenumber, _acc_wavelength_from_wavenumber)
    var _acc_energy_from_wavelength: Float64 = 0.0
    var _t0_energy_from_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_energy_from_wavelength += energy_from_wavelength(0.5)
    var _t1_energy_from_wavelength = perf_counter_ns()
    var _ns_energy_from_wavelength = Float64(_t1_energy_from_wavelength - _t0_energy_from_wavelength) / Float64(N)
    print("MOJO_TIMING spectroscopy::energy_from_wavelength", _ns_energy_from_wavelength, _acc_energy_from_wavelength)
    var _acc_absorbance_from_transmittance: Float64 = 0.0
    var _t0_absorbance_from_transmittance = perf_counter_ns()
    for _ in range(N):
        _acc_absorbance_from_transmittance += absorbance_from_transmittance(0.5)
    var _t1_absorbance_from_transmittance = perf_counter_ns()
    var _ns_absorbance_from_transmittance = Float64(_t1_absorbance_from_transmittance - _t0_absorbance_from_transmittance) / Float64(N)
    print("MOJO_TIMING spectroscopy::absorbance_from_transmittance", _ns_absorbance_from_transmittance, _acc_absorbance_from_transmittance)
    var _acc_transmittance_from_absorbance: Float64 = 0.0
    var _t0_transmittance_from_absorbance = perf_counter_ns()
    for _ in range(N):
        _acc_transmittance_from_absorbance += transmittance_from_absorbance(0.5)
    var _t1_transmittance_from_absorbance = perf_counter_ns()
    var _ns_transmittance_from_absorbance = Float64(_t1_transmittance_from_absorbance - _t0_transmittance_from_absorbance) / Float64(N)
    print("MOJO_TIMING spectroscopy::transmittance_from_absorbance", _ns_transmittance_from_absorbance, _acc_transmittance_from_absorbance)
    var _acc_beer_lambert_concentration: Float64 = 0.0
    var _t0_beer_lambert_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_beer_lambert_concentration += beer_lambert_concentration(0.5, 0.5, 0.5)
    var _t1_beer_lambert_concentration = perf_counter_ns()
    var _ns_beer_lambert_concentration = Float64(_t1_beer_lambert_concentration - _t0_beer_lambert_concentration) / Float64(N)
    print("MOJO_TIMING spectroscopy::beer_lambert_concentration", _ns_beer_lambert_concentration, _acc_beer_lambert_concentration)
    var _acc_resolution_spectrometer: Float64 = 0.0
    var _t0_resolution_spectrometer = perf_counter_ns()
    for _ in range(N):
        _acc_resolution_spectrometer += resolution_spectrometer(0.5, 0.5)
    var _t1_resolution_spectrometer = perf_counter_ns()
    var _ns_resolution_spectrometer = Float64(_t1_resolution_spectrometer - _t0_resolution_spectrometer) / Float64(N)
    print("MOJO_TIMING spectroscopy::resolution_spectrometer", _ns_resolution_spectrometer, _acc_resolution_spectrometer)
    var _acc_snr_coadd: Float64 = 0.0
    var _t0_snr_coadd = perf_counter_ns()
    for _ in range(N):
        _acc_snr_coadd += snr_coadd(0.5, 0.5)
    var _t1_snr_coadd = perf_counter_ns()
    var _ns_snr_coadd = Float64(_t1_snr_coadd - _t0_snr_coadd) / Float64(N)
    print("MOJO_TIMING spectroscopy::snr_coadd", _ns_snr_coadd, _acc_snr_coadd)
    var _acc_raman_shift: Float64 = 0.0
    var _t0_raman_shift = perf_counter_ns()
    for _ in range(N):
        _acc_raman_shift += raman_shift(0.5, 0.5)
    var _t1_raman_shift = perf_counter_ns()
    var _ns_raman_shift = Float64(_t1_raman_shift - _t0_raman_shift) / Float64(N)
    print("MOJO_TIMING spectroscopy::raman_shift", _ns_raman_shift, _acc_raman_shift)
    var _acc_fluorescence_quantum_yield: Float64 = 0.0
    var _t0_fluorescence_quantum_yield = perf_counter_ns()
    for _ in range(N):
        _acc_fluorescence_quantum_yield += fluorescence_quantum_yield(0.5, 0.5)
    var _t1_fluorescence_quantum_yield = perf_counter_ns()
    var _ns_fluorescence_quantum_yield = Float64(_t1_fluorescence_quantum_yield - _t0_fluorescence_quantum_yield) / Float64(N)
    print("MOJO_TIMING spectroscopy::fluorescence_quantum_yield", _ns_fluorescence_quantum_yield, _acc_fluorescence_quantum_yield)
    var _acc_stokes_shift: Float64 = 0.0
    var _t0_stokes_shift = perf_counter_ns()
    for _ in range(N):
        _acc_stokes_shift += stokes_shift(0.5, 0.5)
    var _t1_stokes_shift = perf_counter_ns()
    var _ns_stokes_shift = Float64(_t1_stokes_shift - _t0_stokes_shift) / Float64(N)
    print("MOJO_TIMING spectroscopy::stokes_shift", _ns_stokes_shift, _acc_stokes_shift)
    var _acc_spectral_bandwidth: Float64 = 0.0
    var _t0_spectral_bandwidth = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_bandwidth += spectral_bandwidth(0.5)
    var _t1_spectral_bandwidth = perf_counter_ns()
    var _ns_spectral_bandwidth = Float64(_t1_spectral_bandwidth - _t0_spectral_bandwidth) / Float64(N)
    print("MOJO_TIMING spectroscopy::spectral_bandwidth", _ns_spectral_bandwidth, _acc_spectral_bandwidth)
