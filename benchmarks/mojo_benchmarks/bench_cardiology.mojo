"""bench_cardiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cardiology import cardiac_output, stroke_volume, ejection_fraction, mean_arterial_pressure, pulse_pressure, systemic_vascular_resistance, rate_pressure_product, left_ventricular_work, coronary_perfusion_pressure, fick_cardiac_output
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_cardiac_output: Float64 = 0.0
    var _t0_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_cardiac_output += cardiac_output(0.5, 0.5)
    var _t1_cardiac_output = perf_counter_ns()
    var _ns_cardiac_output = Float64(_t1_cardiac_output - _t0_cardiac_output) / Float64(N)
    print("MOJO_TIMING cardiology::cardiac_output", _ns_cardiac_output, _acc_cardiac_output)
    var _result_cardiac_output = cardiac_output(0.5, 0.5)
    var _summary_cardiac_output = _summary_float64(_result_cardiac_output)
    print("MOJO_RESULT cardiology::cardiac_output", _summary_cardiac_output)
    var _acc_stroke_volume: Float64 = 0.0
    var _t0_stroke_volume = perf_counter_ns()
    for _ in range(N):
        _acc_stroke_volume += stroke_volume(0.5, 0.5)
    var _t1_stroke_volume = perf_counter_ns()
    var _ns_stroke_volume = Float64(_t1_stroke_volume - _t0_stroke_volume) / Float64(N)
    print("MOJO_TIMING cardiology::stroke_volume", _ns_stroke_volume, _acc_stroke_volume)
    var _result_stroke_volume = stroke_volume(0.5, 0.5)
    var _summary_stroke_volume = _summary_float64(_result_stroke_volume)
    print("MOJO_RESULT cardiology::stroke_volume", _summary_stroke_volume)
    var _acc_ejection_fraction: Float64 = 0.0
    var _t0_ejection_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_ejection_fraction += ejection_fraction(0.5, 0.5)
    var _t1_ejection_fraction = perf_counter_ns()
    var _ns_ejection_fraction = Float64(_t1_ejection_fraction - _t0_ejection_fraction) / Float64(N)
    print("MOJO_TIMING cardiology::ejection_fraction", _ns_ejection_fraction, _acc_ejection_fraction)
    var _result_ejection_fraction = ejection_fraction(0.5, 0.5)
    var _summary_ejection_fraction = _summary_float64(_result_ejection_fraction)
    print("MOJO_RESULT cardiology::ejection_fraction", _summary_ejection_fraction)
    var _acc_mean_arterial_pressure: Float64 = 0.0
    var _t0_mean_arterial_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_mean_arterial_pressure += mean_arterial_pressure(0.5, 0.5)
    var _t1_mean_arterial_pressure = perf_counter_ns()
    var _ns_mean_arterial_pressure = Float64(_t1_mean_arterial_pressure - _t0_mean_arterial_pressure) / Float64(N)
    print("MOJO_TIMING cardiology::mean_arterial_pressure", _ns_mean_arterial_pressure, _acc_mean_arterial_pressure)
    var _result_mean_arterial_pressure = mean_arterial_pressure(0.5, 0.5)
    var _summary_mean_arterial_pressure = _summary_float64(_result_mean_arterial_pressure)
    print("MOJO_RESULT cardiology::mean_arterial_pressure", _summary_mean_arterial_pressure)
    var _acc_pulse_pressure: Float64 = 0.0
    var _t0_pulse_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_pressure += pulse_pressure(0.5, 0.5)
    var _t1_pulse_pressure = perf_counter_ns()
    var _ns_pulse_pressure = Float64(_t1_pulse_pressure - _t0_pulse_pressure) / Float64(N)
    print("MOJO_TIMING cardiology::pulse_pressure", _ns_pulse_pressure, _acc_pulse_pressure)
    var _result_pulse_pressure = pulse_pressure(0.5, 0.5)
    var _summary_pulse_pressure = _summary_float64(_result_pulse_pressure)
    print("MOJO_RESULT cardiology::pulse_pressure", _summary_pulse_pressure)
    var _acc_systemic_vascular_resistance: Float64 = 0.0
    var _t0_systemic_vascular_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_systemic_vascular_resistance += systemic_vascular_resistance(0.5, 0.5, 0.5)
    var _t1_systemic_vascular_resistance = perf_counter_ns()
    var _ns_systemic_vascular_resistance = Float64(_t1_systemic_vascular_resistance - _t0_systemic_vascular_resistance) / Float64(N)
    print("MOJO_TIMING cardiology::systemic_vascular_resistance", _ns_systemic_vascular_resistance, _acc_systemic_vascular_resistance)
    var _result_systemic_vascular_resistance = systemic_vascular_resistance(0.5, 0.5, 0.5)
    var _summary_systemic_vascular_resistance = _summary_float64(_result_systemic_vascular_resistance)
    print("MOJO_RESULT cardiology::systemic_vascular_resistance", _summary_systemic_vascular_resistance)
    var _acc_rate_pressure_product: Float64 = 0.0
    var _t0_rate_pressure_product = perf_counter_ns()
    for _ in range(N):
        _acc_rate_pressure_product += rate_pressure_product(0.5, 0.5)
    var _t1_rate_pressure_product = perf_counter_ns()
    var _ns_rate_pressure_product = Float64(_t1_rate_pressure_product - _t0_rate_pressure_product) / Float64(N)
    print("MOJO_TIMING cardiology::rate_pressure_product", _ns_rate_pressure_product, _acc_rate_pressure_product)
    var _result_rate_pressure_product = rate_pressure_product(0.5, 0.5)
    var _summary_rate_pressure_product = _summary_float64(_result_rate_pressure_product)
    print("MOJO_RESULT cardiology::rate_pressure_product", _summary_rate_pressure_product)
    var _acc_left_ventricular_work: Float64 = 0.0
    var _t0_left_ventricular_work = perf_counter_ns()
    for _ in range(N):
        _acc_left_ventricular_work += left_ventricular_work(0.5, 0.5)
    var _t1_left_ventricular_work = perf_counter_ns()
    var _ns_left_ventricular_work = Float64(_t1_left_ventricular_work - _t0_left_ventricular_work) / Float64(N)
    print("MOJO_TIMING cardiology::left_ventricular_work", _ns_left_ventricular_work, _acc_left_ventricular_work)
    var _result_left_ventricular_work = left_ventricular_work(0.5, 0.5)
    var _summary_left_ventricular_work = _summary_float64(_result_left_ventricular_work)
    print("MOJO_RESULT cardiology::left_ventricular_work", _summary_left_ventricular_work)
    var _acc_coronary_perfusion_pressure: Float64 = 0.0
    var _t0_coronary_perfusion_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_coronary_perfusion_pressure += coronary_perfusion_pressure(0.5, 0.5)
    var _t1_coronary_perfusion_pressure = perf_counter_ns()
    var _ns_coronary_perfusion_pressure = Float64(_t1_coronary_perfusion_pressure - _t0_coronary_perfusion_pressure) / Float64(N)
    print("MOJO_TIMING cardiology::coronary_perfusion_pressure", _ns_coronary_perfusion_pressure, _acc_coronary_perfusion_pressure)
    var _result_coronary_perfusion_pressure = coronary_perfusion_pressure(0.5, 0.5)
    var _summary_coronary_perfusion_pressure = _summary_float64(_result_coronary_perfusion_pressure)
    print("MOJO_RESULT cardiology::coronary_perfusion_pressure", _summary_coronary_perfusion_pressure)
    var _acc_fick_cardiac_output: Float64 = 0.0
    var _t0_fick_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_fick_cardiac_output += fick_cardiac_output(0.5, 0.5, 0.5)
    var _t1_fick_cardiac_output = perf_counter_ns()
    var _ns_fick_cardiac_output = Float64(_t1_fick_cardiac_output - _t0_fick_cardiac_output) / Float64(N)
    print("MOJO_TIMING cardiology::fick_cardiac_output", _ns_fick_cardiac_output, _acc_fick_cardiac_output)
    var _result_fick_cardiac_output = fick_cardiac_output(0.5, 0.5, 0.5)
    var _summary_fick_cardiac_output = _summary_float64(_result_fick_cardiac_output)
    print("MOJO_RESULT cardiology::fick_cardiac_output", _summary_fick_cardiac_output)
