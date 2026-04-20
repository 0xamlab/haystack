"""bench_paleomagnetism.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paleomagnetism import virtual_geomagnetic_pole_lat, sin_approx, cos_approx, atan_approx, paleolatitude, geomagnetic_intensity, declination_correction, magnetic_reversal_rate, koenigsberger_ratio, stability_index, rock_magnetic_susceptibility, anhysteretic_remanence, coercivity_spectrum_median
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

    var _acc_virtual_geomagnetic_pole_lat: Float64 = 0.0
    var _t0_virtual_geomagnetic_pole_lat = perf_counter_ns()
    for _ in range(N):
        _acc_virtual_geomagnetic_pole_lat += virtual_geomagnetic_pole_lat(0.5)
    var _t1_virtual_geomagnetic_pole_lat = perf_counter_ns()
    var _ns_virtual_geomagnetic_pole_lat = Float64(_t1_virtual_geomagnetic_pole_lat - _t0_virtual_geomagnetic_pole_lat) / Float64(N)
    print("MOJO_TIMING paleomagnetism::virtual_geomagnetic_pole_lat", _ns_virtual_geomagnetic_pole_lat, _acc_virtual_geomagnetic_pole_lat)
    var _acc_sin_approx: Float64 = 0.0
    var _t0_sin_approx = perf_counter_ns()
    for _ in range(N):
        _acc_sin_approx += sin_approx(0.5)
    var _t1_sin_approx = perf_counter_ns()
    var _ns_sin_approx = Float64(_t1_sin_approx - _t0_sin_approx) / Float64(N)
    print("MOJO_TIMING paleomagnetism::sin_approx", _ns_sin_approx, _acc_sin_approx)
    var _acc_cos_approx: Float64 = 0.0
    var _t0_cos_approx = perf_counter_ns()
    for _ in range(N):
        _acc_cos_approx += cos_approx(0.5)
    var _t1_cos_approx = perf_counter_ns()
    var _ns_cos_approx = Float64(_t1_cos_approx - _t0_cos_approx) / Float64(N)
    print("MOJO_TIMING paleomagnetism::cos_approx", _ns_cos_approx, _acc_cos_approx)
    var _acc_atan_approx: Float64 = 0.0
    var _t0_atan_approx = perf_counter_ns()
    for _ in range(N):
        _acc_atan_approx += atan_approx(0.5)
    var _t1_atan_approx = perf_counter_ns()
    var _ns_atan_approx = Float64(_t1_atan_approx - _t0_atan_approx) / Float64(N)
    print("MOJO_TIMING paleomagnetism::atan_approx", _ns_atan_approx, _acc_atan_approx)
    var _acc_paleolatitude: Float64 = 0.0
    var _t0_paleolatitude = perf_counter_ns()
    for _ in range(N):
        _acc_paleolatitude += paleolatitude(0.5)
    var _t1_paleolatitude = perf_counter_ns()
    var _ns_paleolatitude = Float64(_t1_paleolatitude - _t0_paleolatitude) / Float64(N)
    print("MOJO_TIMING paleomagnetism::paleolatitude", _ns_paleolatitude, _acc_paleolatitude)
    var _acc_geomagnetic_intensity: Float64 = 0.0
    var _t0_geomagnetic_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_geomagnetic_intensity += geomagnetic_intensity(0.5, 0.5)
    var _t1_geomagnetic_intensity = perf_counter_ns()
    var _ns_geomagnetic_intensity = Float64(_t1_geomagnetic_intensity - _t0_geomagnetic_intensity) / Float64(N)
    print("MOJO_TIMING paleomagnetism::geomagnetic_intensity", _ns_geomagnetic_intensity, _acc_geomagnetic_intensity)
    var _acc_declination_correction: Float64 = 0.0
    var _t0_declination_correction = perf_counter_ns()
    for _ in range(N):
        _acc_declination_correction += declination_correction(0.5, 0.5)
    var _t1_declination_correction = perf_counter_ns()
    var _ns_declination_correction = Float64(_t1_declination_correction - _t0_declination_correction) / Float64(N)
    print("MOJO_TIMING paleomagnetism::declination_correction", _ns_declination_correction, _acc_declination_correction)
    var _acc_magnetic_reversal_rate: Float64 = 0.0
    var _t0_magnetic_reversal_rate = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_reversal_rate += magnetic_reversal_rate(0.5, 0.5)
    var _t1_magnetic_reversal_rate = perf_counter_ns()
    var _ns_magnetic_reversal_rate = Float64(_t1_magnetic_reversal_rate - _t0_magnetic_reversal_rate) / Float64(N)
    print("MOJO_TIMING paleomagnetism::magnetic_reversal_rate", _ns_magnetic_reversal_rate, _acc_magnetic_reversal_rate)
    var _acc_koenigsberger_ratio: Float64 = 0.0
    var _t0_koenigsberger_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_koenigsberger_ratio += koenigsberger_ratio(0.5, 0.5, 0.5)
    var _t1_koenigsberger_ratio = perf_counter_ns()
    var _ns_koenigsberger_ratio = Float64(_t1_koenigsberger_ratio - _t0_koenigsberger_ratio) / Float64(N)
    print("MOJO_TIMING paleomagnetism::koenigsberger_ratio", _ns_koenigsberger_ratio, _acc_koenigsberger_ratio)
    var _acc_stability_index: Float64 = 0.0
    var _t0_stability_index = perf_counter_ns()
    for _ in range(N):
        _acc_stability_index += stability_index(0.5, 0.5)
    var _t1_stability_index = perf_counter_ns()
    var _ns_stability_index = Float64(_t1_stability_index - _t0_stability_index) / Float64(N)
    print("MOJO_TIMING paleomagnetism::stability_index", _ns_stability_index, _acc_stability_index)
    var _acc_rock_magnetic_susceptibility: Float64 = 0.0
    var _t0_rock_magnetic_susceptibility = perf_counter_ns()
    for _ in range(N):
        _acc_rock_magnetic_susceptibility += rock_magnetic_susceptibility(0.5, 0.5)
    var _t1_rock_magnetic_susceptibility = perf_counter_ns()
    var _ns_rock_magnetic_susceptibility = Float64(_t1_rock_magnetic_susceptibility - _t0_rock_magnetic_susceptibility) / Float64(N)
    print("MOJO_TIMING paleomagnetism::rock_magnetic_susceptibility", _ns_rock_magnetic_susceptibility, _acc_rock_magnetic_susceptibility)
    var _acc_anhysteretic_remanence: Float64 = 0.0
    var _t0_anhysteretic_remanence = perf_counter_ns()
    for _ in range(N):
        _acc_anhysteretic_remanence += anhysteretic_remanence(0.5, 0.5)
    var _t1_anhysteretic_remanence = perf_counter_ns()
    var _ns_anhysteretic_remanence = Float64(_t1_anhysteretic_remanence - _t0_anhysteretic_remanence) / Float64(N)
    print("MOJO_TIMING paleomagnetism::anhysteretic_remanence", _ns_anhysteretic_remanence, _acc_anhysteretic_remanence)
    var _acc_coercivity_spectrum_median: Float64 = 0.0
    var _t0_coercivity_spectrum_median = perf_counter_ns()
    for _ in range(N):
        _acc_coercivity_spectrum_median += coercivity_spectrum_median(0.5, 0.5)
    var _t1_coercivity_spectrum_median = perf_counter_ns()
    var _ns_coercivity_spectrum_median = Float64(_t1_coercivity_spectrum_median - _t0_coercivity_spectrum_median) / Float64(N)
    print("MOJO_TIMING paleomagnetism::coercivity_spectrum_median", _ns_coercivity_spectrum_median, _acc_coercivity_spectrum_median)
