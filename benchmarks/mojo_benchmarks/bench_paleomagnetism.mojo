"""bench_paleomagnetism.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paleomagnetism import virtual_geomagnetic_pole_lat, sin_approx, cos_approx, atan_approx, paleolatitude, geomagnetic_intensity, declination_correction, magnetic_reversal_rate, koenigsberger_ratio, stability_index, rock_magnetic_susceptibility, anhysteretic_remanence, coercivity_spectrum_median
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

    var _acc_virtual_geomagnetic_pole_lat: Float64 = 0.0
    var _t0_virtual_geomagnetic_pole_lat = perf_counter_ns()
    for _ in range(N):
        _acc_virtual_geomagnetic_pole_lat += virtual_geomagnetic_pole_lat(0.5)
    var _t1_virtual_geomagnetic_pole_lat = perf_counter_ns()
    var _ns_virtual_geomagnetic_pole_lat = Float64(_t1_virtual_geomagnetic_pole_lat - _t0_virtual_geomagnetic_pole_lat) / Float64(N)
    print("MOJO_TIMING paleomagnetism::virtual_geomagnetic_pole_lat", _ns_virtual_geomagnetic_pole_lat, _acc_virtual_geomagnetic_pole_lat)
    var _result_virtual_geomagnetic_pole_lat = virtual_geomagnetic_pole_lat(0.5)
    var _summary_virtual_geomagnetic_pole_lat = _summary_float64(_result_virtual_geomagnetic_pole_lat)
    print("MOJO_RESULT paleomagnetism::virtual_geomagnetic_pole_lat", _summary_virtual_geomagnetic_pole_lat)
    var _acc_sin_approx: Float64 = 0.0
    var _t0_sin_approx = perf_counter_ns()
    for _ in range(N):
        _acc_sin_approx += sin_approx(0.5)
    var _t1_sin_approx = perf_counter_ns()
    var _ns_sin_approx = Float64(_t1_sin_approx - _t0_sin_approx) / Float64(N)
    print("MOJO_TIMING paleomagnetism::sin_approx", _ns_sin_approx, _acc_sin_approx)
    var _result_sin_approx = sin_approx(0.5)
    var _summary_sin_approx = _summary_float64(_result_sin_approx)
    print("MOJO_RESULT paleomagnetism::sin_approx", _summary_sin_approx)
    var _acc_cos_approx: Float64 = 0.0
    var _t0_cos_approx = perf_counter_ns()
    for _ in range(N):
        _acc_cos_approx += cos_approx(0.5)
    var _t1_cos_approx = perf_counter_ns()
    var _ns_cos_approx = Float64(_t1_cos_approx - _t0_cos_approx) / Float64(N)
    print("MOJO_TIMING paleomagnetism::cos_approx", _ns_cos_approx, _acc_cos_approx)
    var _result_cos_approx = cos_approx(0.5)
    var _summary_cos_approx = _summary_float64(_result_cos_approx)
    print("MOJO_RESULT paleomagnetism::cos_approx", _summary_cos_approx)
    var _acc_atan_approx: Float64 = 0.0
    var _t0_atan_approx = perf_counter_ns()
    for _ in range(N):
        _acc_atan_approx += atan_approx(0.5)
    var _t1_atan_approx = perf_counter_ns()
    var _ns_atan_approx = Float64(_t1_atan_approx - _t0_atan_approx) / Float64(N)
    print("MOJO_TIMING paleomagnetism::atan_approx", _ns_atan_approx, _acc_atan_approx)
    var _result_atan_approx = atan_approx(0.5)
    var _summary_atan_approx = _summary_float64(_result_atan_approx)
    print("MOJO_RESULT paleomagnetism::atan_approx", _summary_atan_approx)
    var _acc_paleolatitude: Float64 = 0.0
    var _t0_paleolatitude = perf_counter_ns()
    for _ in range(N):
        _acc_paleolatitude += paleolatitude(0.5)
    var _t1_paleolatitude = perf_counter_ns()
    var _ns_paleolatitude = Float64(_t1_paleolatitude - _t0_paleolatitude) / Float64(N)
    print("MOJO_TIMING paleomagnetism::paleolatitude", _ns_paleolatitude, _acc_paleolatitude)
    var _result_paleolatitude = paleolatitude(0.5)
    var _summary_paleolatitude = _summary_float64(_result_paleolatitude)
    print("MOJO_RESULT paleomagnetism::paleolatitude", _summary_paleolatitude)
    var _acc_geomagnetic_intensity: Float64 = 0.0
    var _t0_geomagnetic_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_geomagnetic_intensity += geomagnetic_intensity(0.5, 0.5)
    var _t1_geomagnetic_intensity = perf_counter_ns()
    var _ns_geomagnetic_intensity = Float64(_t1_geomagnetic_intensity - _t0_geomagnetic_intensity) / Float64(N)
    print("MOJO_TIMING paleomagnetism::geomagnetic_intensity", _ns_geomagnetic_intensity, _acc_geomagnetic_intensity)
    var _result_geomagnetic_intensity = geomagnetic_intensity(0.5, 0.5)
    var _summary_geomagnetic_intensity = _summary_float64(_result_geomagnetic_intensity)
    print("MOJO_RESULT paleomagnetism::geomagnetic_intensity", _summary_geomagnetic_intensity)
    var _acc_declination_correction: Float64 = 0.0
    var _t0_declination_correction = perf_counter_ns()
    for _ in range(N):
        _acc_declination_correction += declination_correction(0.5, 0.5)
    var _t1_declination_correction = perf_counter_ns()
    var _ns_declination_correction = Float64(_t1_declination_correction - _t0_declination_correction) / Float64(N)
    print("MOJO_TIMING paleomagnetism::declination_correction", _ns_declination_correction, _acc_declination_correction)
    var _result_declination_correction = declination_correction(0.5, 0.5)
    var _summary_declination_correction = _summary_float64(_result_declination_correction)
    print("MOJO_RESULT paleomagnetism::declination_correction", _summary_declination_correction)
    var _acc_magnetic_reversal_rate: Float64 = 0.0
    var _t0_magnetic_reversal_rate = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_reversal_rate += magnetic_reversal_rate(0.5, 0.5)
    var _t1_magnetic_reversal_rate = perf_counter_ns()
    var _ns_magnetic_reversal_rate = Float64(_t1_magnetic_reversal_rate - _t0_magnetic_reversal_rate) / Float64(N)
    print("MOJO_TIMING paleomagnetism::magnetic_reversal_rate", _ns_magnetic_reversal_rate, _acc_magnetic_reversal_rate)
    var _result_magnetic_reversal_rate = magnetic_reversal_rate(0.5, 0.5)
    var _summary_magnetic_reversal_rate = _summary_float64(_result_magnetic_reversal_rate)
    print("MOJO_RESULT paleomagnetism::magnetic_reversal_rate", _summary_magnetic_reversal_rate)
    var _acc_koenigsberger_ratio: Float64 = 0.0
    var _t0_koenigsberger_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_koenigsberger_ratio += koenigsberger_ratio(0.5, 0.5, 0.5)
    var _t1_koenigsberger_ratio = perf_counter_ns()
    var _ns_koenigsberger_ratio = Float64(_t1_koenigsberger_ratio - _t0_koenigsberger_ratio) / Float64(N)
    print("MOJO_TIMING paleomagnetism::koenigsberger_ratio", _ns_koenigsberger_ratio, _acc_koenigsberger_ratio)
    var _result_koenigsberger_ratio = koenigsberger_ratio(0.5, 0.5, 0.5)
    var _summary_koenigsberger_ratio = _summary_float64(_result_koenigsberger_ratio)
    print("MOJO_RESULT paleomagnetism::koenigsberger_ratio", _summary_koenigsberger_ratio)
    var _acc_stability_index: Float64 = 0.0
    var _t0_stability_index = perf_counter_ns()
    for _ in range(N):
        _acc_stability_index += stability_index(0.5, 0.5)
    var _t1_stability_index = perf_counter_ns()
    var _ns_stability_index = Float64(_t1_stability_index - _t0_stability_index) / Float64(N)
    print("MOJO_TIMING paleomagnetism::stability_index", _ns_stability_index, _acc_stability_index)
    var _result_stability_index = stability_index(0.5, 0.5)
    var _summary_stability_index = _summary_float64(_result_stability_index)
    print("MOJO_RESULT paleomagnetism::stability_index", _summary_stability_index)
    var _acc_rock_magnetic_susceptibility: Float64 = 0.0
    var _t0_rock_magnetic_susceptibility = perf_counter_ns()
    for _ in range(N):
        _acc_rock_magnetic_susceptibility += rock_magnetic_susceptibility(0.5, 0.5)
    var _t1_rock_magnetic_susceptibility = perf_counter_ns()
    var _ns_rock_magnetic_susceptibility = Float64(_t1_rock_magnetic_susceptibility - _t0_rock_magnetic_susceptibility) / Float64(N)
    print("MOJO_TIMING paleomagnetism::rock_magnetic_susceptibility", _ns_rock_magnetic_susceptibility, _acc_rock_magnetic_susceptibility)
    var _result_rock_magnetic_susceptibility = rock_magnetic_susceptibility(0.5, 0.5)
    var _summary_rock_magnetic_susceptibility = _summary_float64(_result_rock_magnetic_susceptibility)
    print("MOJO_RESULT paleomagnetism::rock_magnetic_susceptibility", _summary_rock_magnetic_susceptibility)
    var _acc_anhysteretic_remanence: Float64 = 0.0
    var _t0_anhysteretic_remanence = perf_counter_ns()
    for _ in range(N):
        _acc_anhysteretic_remanence += anhysteretic_remanence(0.5, 0.5)
    var _t1_anhysteretic_remanence = perf_counter_ns()
    var _ns_anhysteretic_remanence = Float64(_t1_anhysteretic_remanence - _t0_anhysteretic_remanence) / Float64(N)
    print("MOJO_TIMING paleomagnetism::anhysteretic_remanence", _ns_anhysteretic_remanence, _acc_anhysteretic_remanence)
    var _result_anhysteretic_remanence = anhysteretic_remanence(0.5, 0.5)
    var _summary_anhysteretic_remanence = _summary_float64(_result_anhysteretic_remanence)
    print("MOJO_RESULT paleomagnetism::anhysteretic_remanence", _summary_anhysteretic_remanence)
    var _acc_coercivity_spectrum_median: Float64 = 0.0
    var _t0_coercivity_spectrum_median = perf_counter_ns()
    for _ in range(N):
        _acc_coercivity_spectrum_median += coercivity_spectrum_median(0.5, 0.5)
    var _t1_coercivity_spectrum_median = perf_counter_ns()
    var _ns_coercivity_spectrum_median = Float64(_t1_coercivity_spectrum_median - _t0_coercivity_spectrum_median) / Float64(N)
    print("MOJO_TIMING paleomagnetism::coercivity_spectrum_median", _ns_coercivity_spectrum_median, _acc_coercivity_spectrum_median)
    var _result_coercivity_spectrum_median = coercivity_spectrum_median(0.5, 0.5)
    var _summary_coercivity_spectrum_median = _summary_float64(_result_coercivity_spectrum_median)
    print("MOJO_RESULT paleomagnetism::coercivity_spectrum_median", _summary_coercivity_spectrum_median)
