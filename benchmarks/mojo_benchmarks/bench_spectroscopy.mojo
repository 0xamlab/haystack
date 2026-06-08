"""bench_spectroscopy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from spectroscopy import wavenumber_from_wavelength, wavelength_from_wavenumber, energy_from_wavelength, absorbance_from_transmittance, transmittance_from_absorbance, beer_lambert_concentration, resolution_spectrometer, snr_coadd, raman_shift, fluorescence_quantum_yield, stokes_shift, spectral_bandwidth
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_wavenumber_from_wavelength = wavenumber_from_wavelength(0.5)
    var _summary_wavenumber_from_wavelength = _summary_float64(_result_wavenumber_from_wavelength)
    print("MOJO_RESULT spectroscopy::wavenumber_from_wavelength", _summary_wavenumber_from_wavelength)
    var _acc_wavelength_from_wavenumber: Float64 = 0.0
    var _t0_wavelength_from_wavenumber = perf_counter_ns()
    for _ in range(N):
        _acc_wavelength_from_wavenumber += wavelength_from_wavenumber(0.5)
    var _t1_wavelength_from_wavenumber = perf_counter_ns()
    var _ns_wavelength_from_wavenumber = Float64(_t1_wavelength_from_wavenumber - _t0_wavelength_from_wavenumber) / Float64(N)
    print("MOJO_TIMING spectroscopy::wavelength_from_wavenumber", _ns_wavelength_from_wavenumber, _acc_wavelength_from_wavenumber)
    var _result_wavelength_from_wavenumber = wavelength_from_wavenumber(0.5)
    var _summary_wavelength_from_wavenumber = _summary_float64(_result_wavelength_from_wavenumber)
    print("MOJO_RESULT spectroscopy::wavelength_from_wavenumber", _summary_wavelength_from_wavenumber)
    var _acc_energy_from_wavelength: Float64 = 0.0
    var _t0_energy_from_wavelength = perf_counter_ns()
    for _ in range(N):
        _acc_energy_from_wavelength += energy_from_wavelength(0.5)
    var _t1_energy_from_wavelength = perf_counter_ns()
    var _ns_energy_from_wavelength = Float64(_t1_energy_from_wavelength - _t0_energy_from_wavelength) / Float64(N)
    print("MOJO_TIMING spectroscopy::energy_from_wavelength", _ns_energy_from_wavelength, _acc_energy_from_wavelength)
    var _result_energy_from_wavelength = energy_from_wavelength(0.5)
    var _summary_energy_from_wavelength = _summary_float64(_result_energy_from_wavelength)
    print("MOJO_RESULT spectroscopy::energy_from_wavelength", _summary_energy_from_wavelength)
    var _acc_absorbance_from_transmittance: Float64 = 0.0
    var _t0_absorbance_from_transmittance = perf_counter_ns()
    for _ in range(N):
        _acc_absorbance_from_transmittance += absorbance_from_transmittance(0.5)
    var _t1_absorbance_from_transmittance = perf_counter_ns()
    var _ns_absorbance_from_transmittance = Float64(_t1_absorbance_from_transmittance - _t0_absorbance_from_transmittance) / Float64(N)
    print("MOJO_TIMING spectroscopy::absorbance_from_transmittance", _ns_absorbance_from_transmittance, _acc_absorbance_from_transmittance)
    var _result_absorbance_from_transmittance = absorbance_from_transmittance(0.5)
    var _summary_absorbance_from_transmittance = _summary_float64(_result_absorbance_from_transmittance)
    print("MOJO_RESULT spectroscopy::absorbance_from_transmittance", _summary_absorbance_from_transmittance)
    var _acc_transmittance_from_absorbance: Float64 = 0.0
    var _t0_transmittance_from_absorbance = perf_counter_ns()
    for _ in range(N):
        _acc_transmittance_from_absorbance += transmittance_from_absorbance(0.5)
    var _t1_transmittance_from_absorbance = perf_counter_ns()
    var _ns_transmittance_from_absorbance = Float64(_t1_transmittance_from_absorbance - _t0_transmittance_from_absorbance) / Float64(N)
    print("MOJO_TIMING spectroscopy::transmittance_from_absorbance", _ns_transmittance_from_absorbance, _acc_transmittance_from_absorbance)
    var _result_transmittance_from_absorbance = transmittance_from_absorbance(0.5)
    var _summary_transmittance_from_absorbance = _summary_float64(_result_transmittance_from_absorbance)
    print("MOJO_RESULT spectroscopy::transmittance_from_absorbance", _summary_transmittance_from_absorbance)
    var _acc_beer_lambert_concentration: Float64 = 0.0
    var _t0_beer_lambert_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_beer_lambert_concentration += beer_lambert_concentration(0.5, 0.5, 0.5)
    var _t1_beer_lambert_concentration = perf_counter_ns()
    var _ns_beer_lambert_concentration = Float64(_t1_beer_lambert_concentration - _t0_beer_lambert_concentration) / Float64(N)
    print("MOJO_TIMING spectroscopy::beer_lambert_concentration", _ns_beer_lambert_concentration, _acc_beer_lambert_concentration)
    var _result_beer_lambert_concentration = beer_lambert_concentration(0.5, 0.5, 0.5)
    var _summary_beer_lambert_concentration = _summary_float64(_result_beer_lambert_concentration)
    print("MOJO_RESULT spectroscopy::beer_lambert_concentration", _summary_beer_lambert_concentration)
    var _acc_resolution_spectrometer: Float64 = 0.0
    var _t0_resolution_spectrometer = perf_counter_ns()
    for _ in range(N):
        _acc_resolution_spectrometer += resolution_spectrometer(0.5, 0.5)
    var _t1_resolution_spectrometer = perf_counter_ns()
    var _ns_resolution_spectrometer = Float64(_t1_resolution_spectrometer - _t0_resolution_spectrometer) / Float64(N)
    print("MOJO_TIMING spectroscopy::resolution_spectrometer", _ns_resolution_spectrometer, _acc_resolution_spectrometer)
    var _result_resolution_spectrometer = resolution_spectrometer(0.5, 0.5)
    var _summary_resolution_spectrometer = _summary_float64(_result_resolution_spectrometer)
    print("MOJO_RESULT spectroscopy::resolution_spectrometer", _summary_resolution_spectrometer)
    var _acc_snr_coadd: Float64 = 0.0
    var _t0_snr_coadd = perf_counter_ns()
    for _ in range(N):
        _acc_snr_coadd += snr_coadd(0.5, 0.5)
    var _t1_snr_coadd = perf_counter_ns()
    var _ns_snr_coadd = Float64(_t1_snr_coadd - _t0_snr_coadd) / Float64(N)
    print("MOJO_TIMING spectroscopy::snr_coadd", _ns_snr_coadd, _acc_snr_coadd)
    var _result_snr_coadd = snr_coadd(0.5, 0.5)
    var _summary_snr_coadd = _summary_float64(_result_snr_coadd)
    print("MOJO_RESULT spectroscopy::snr_coadd", _summary_snr_coadd)
    var _acc_raman_shift: Float64 = 0.0
    var _t0_raman_shift = perf_counter_ns()
    for _ in range(N):
        _acc_raman_shift += raman_shift(0.5, 0.5)
    var _t1_raman_shift = perf_counter_ns()
    var _ns_raman_shift = Float64(_t1_raman_shift - _t0_raman_shift) / Float64(N)
    print("MOJO_TIMING spectroscopy::raman_shift", _ns_raman_shift, _acc_raman_shift)
    var _result_raman_shift = raman_shift(0.5, 0.5)
    var _summary_raman_shift = _summary_float64(_result_raman_shift)
    print("MOJO_RESULT spectroscopy::raman_shift", _summary_raman_shift)
    var _acc_fluorescence_quantum_yield: Float64 = 0.0
    var _t0_fluorescence_quantum_yield = perf_counter_ns()
    for _ in range(N):
        _acc_fluorescence_quantum_yield += fluorescence_quantum_yield(0.5, 0.5)
    var _t1_fluorescence_quantum_yield = perf_counter_ns()
    var _ns_fluorescence_quantum_yield = Float64(_t1_fluorescence_quantum_yield - _t0_fluorescence_quantum_yield) / Float64(N)
    print("MOJO_TIMING spectroscopy::fluorescence_quantum_yield", _ns_fluorescence_quantum_yield, _acc_fluorescence_quantum_yield)
    var _result_fluorescence_quantum_yield = fluorescence_quantum_yield(0.5, 0.5)
    var _summary_fluorescence_quantum_yield = _summary_float64(_result_fluorescence_quantum_yield)
    print("MOJO_RESULT spectroscopy::fluorescence_quantum_yield", _summary_fluorescence_quantum_yield)
    var _acc_stokes_shift: Float64 = 0.0
    var _t0_stokes_shift = perf_counter_ns()
    for _ in range(N):
        _acc_stokes_shift += stokes_shift(0.5, 0.5)
    var _t1_stokes_shift = perf_counter_ns()
    var _ns_stokes_shift = Float64(_t1_stokes_shift - _t0_stokes_shift) / Float64(N)
    print("MOJO_TIMING spectroscopy::stokes_shift", _ns_stokes_shift, _acc_stokes_shift)
    var _result_stokes_shift = stokes_shift(0.5, 0.5)
    var _summary_stokes_shift = _summary_float64(_result_stokes_shift)
    print("MOJO_RESULT spectroscopy::stokes_shift", _summary_stokes_shift)
    var _acc_spectral_bandwidth: Float64 = 0.0
    var _t0_spectral_bandwidth = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_bandwidth += spectral_bandwidth(0.5)
    var _t1_spectral_bandwidth = perf_counter_ns()
    var _ns_spectral_bandwidth = Float64(_t1_spectral_bandwidth - _t0_spectral_bandwidth) / Float64(N)
    print("MOJO_TIMING spectroscopy::spectral_bandwidth", _ns_spectral_bandwidth, _acc_spectral_bandwidth)
    var _result_spectral_bandwidth = spectral_bandwidth(0.5)
    var _summary_spectral_bandwidth = _summary_float64(_result_spectral_bandwidth)
    print("MOJO_RESULT spectroscopy::spectral_bandwidth", _summary_spectral_bandwidth)
