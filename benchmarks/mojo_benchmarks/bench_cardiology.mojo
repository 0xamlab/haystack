"""bench_cardiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cardiology import cardiac_output, stroke_volume, ejection_fraction, mean_arterial_pressure, pulse_pressure, systemic_vascular_resistance, rate_pressure_product, left_ventricular_work, coronary_perfusion_pressure, fick_cardiac_output
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

    var _acc_cardiac_output: Float64 = 0.0
    var _t0_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_cardiac_output += cardiac_output(0.5, 0.5)
    var _t1_cardiac_output = perf_counter_ns()
    var _ns_cardiac_output = Float64(_t1_cardiac_output - _t0_cardiac_output) / Float64(N)
    print("MOJO_TIMING cardiology::cardiac_output", _ns_cardiac_output, _acc_cardiac_output)
    var _acc_stroke_volume: Float64 = 0.0
    var _t0_stroke_volume = perf_counter_ns()
    for _ in range(N):
        _acc_stroke_volume += stroke_volume(0.5, 0.5)
    var _t1_stroke_volume = perf_counter_ns()
    var _ns_stroke_volume = Float64(_t1_stroke_volume - _t0_stroke_volume) / Float64(N)
    print("MOJO_TIMING cardiology::stroke_volume", _ns_stroke_volume, _acc_stroke_volume)
    var _acc_ejection_fraction: Float64 = 0.0
    var _t0_ejection_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_ejection_fraction += ejection_fraction(0.5, 0.5)
    var _t1_ejection_fraction = perf_counter_ns()
    var _ns_ejection_fraction = Float64(_t1_ejection_fraction - _t0_ejection_fraction) / Float64(N)
    print("MOJO_TIMING cardiology::ejection_fraction", _ns_ejection_fraction, _acc_ejection_fraction)
    var _acc_mean_arterial_pressure: Float64 = 0.0
    var _t0_mean_arterial_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_mean_arterial_pressure += mean_arterial_pressure(0.5, 0.5)
    var _t1_mean_arterial_pressure = perf_counter_ns()
    var _ns_mean_arterial_pressure = Float64(_t1_mean_arterial_pressure - _t0_mean_arterial_pressure) / Float64(N)
    print("MOJO_TIMING cardiology::mean_arterial_pressure", _ns_mean_arterial_pressure, _acc_mean_arterial_pressure)
    var _acc_pulse_pressure: Float64 = 0.0
    var _t0_pulse_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_pressure += pulse_pressure(0.5, 0.5)
    var _t1_pulse_pressure = perf_counter_ns()
    var _ns_pulse_pressure = Float64(_t1_pulse_pressure - _t0_pulse_pressure) / Float64(N)
    print("MOJO_TIMING cardiology::pulse_pressure", _ns_pulse_pressure, _acc_pulse_pressure)
    var _acc_systemic_vascular_resistance: Float64 = 0.0
    var _t0_systemic_vascular_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_systemic_vascular_resistance += systemic_vascular_resistance(0.5, 0.5, 0.5)
    var _t1_systemic_vascular_resistance = perf_counter_ns()
    var _ns_systemic_vascular_resistance = Float64(_t1_systemic_vascular_resistance - _t0_systemic_vascular_resistance) / Float64(N)
    print("MOJO_TIMING cardiology::systemic_vascular_resistance", _ns_systemic_vascular_resistance, _acc_systemic_vascular_resistance)
    var _acc_rate_pressure_product: Float64 = 0.0
    var _t0_rate_pressure_product = perf_counter_ns()
    for _ in range(N):
        _acc_rate_pressure_product += rate_pressure_product(0.5, 0.5)
    var _t1_rate_pressure_product = perf_counter_ns()
    var _ns_rate_pressure_product = Float64(_t1_rate_pressure_product - _t0_rate_pressure_product) / Float64(N)
    print("MOJO_TIMING cardiology::rate_pressure_product", _ns_rate_pressure_product, _acc_rate_pressure_product)
    var _acc_left_ventricular_work: Float64 = 0.0
    var _t0_left_ventricular_work = perf_counter_ns()
    for _ in range(N):
        _acc_left_ventricular_work += left_ventricular_work(0.5, 0.5)
    var _t1_left_ventricular_work = perf_counter_ns()
    var _ns_left_ventricular_work = Float64(_t1_left_ventricular_work - _t0_left_ventricular_work) / Float64(N)
    print("MOJO_TIMING cardiology::left_ventricular_work", _ns_left_ventricular_work, _acc_left_ventricular_work)
    var _acc_coronary_perfusion_pressure: Float64 = 0.0
    var _t0_coronary_perfusion_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_coronary_perfusion_pressure += coronary_perfusion_pressure(0.5, 0.5)
    var _t1_coronary_perfusion_pressure = perf_counter_ns()
    var _ns_coronary_perfusion_pressure = Float64(_t1_coronary_perfusion_pressure - _t0_coronary_perfusion_pressure) / Float64(N)
    print("MOJO_TIMING cardiology::coronary_perfusion_pressure", _ns_coronary_perfusion_pressure, _acc_coronary_perfusion_pressure)
    var _acc_fick_cardiac_output: Float64 = 0.0
    var _t0_fick_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_fick_cardiac_output += fick_cardiac_output(0.5, 0.5, 0.5)
    var _t1_fick_cardiac_output = perf_counter_ns()
    var _ns_fick_cardiac_output = Float64(_t1_fick_cardiac_output - _t0_fick_cardiac_output) / Float64(N)
    print("MOJO_TIMING cardiology::fick_cardiac_output", _ns_fick_cardiac_output, _acc_fick_cardiac_output)
