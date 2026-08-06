"""bench_ophthalmology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ophthalmology import visual_acuity_decimal, refractive_error_spherical, lens_power, intraocular_pressure, corneal_radius_from_keratometry, retinal_image_size, depth_of_focus, critical_flicker_frequency, contrast_sensitivity, dark_adaptation_kinetics
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

    var _acc_visual_acuity_decimal: Float64 = 0.0
    var _t0_visual_acuity_decimal = perf_counter_ns()
    for _ in range(N):
        _acc_visual_acuity_decimal += visual_acuity_decimal(0.5, 0.5)
    var _t1_visual_acuity_decimal = perf_counter_ns()
    var _ns_visual_acuity_decimal = Float64(_t1_visual_acuity_decimal - _t0_visual_acuity_decimal) / Float64(N)
    print("MOJO_TIMING ophthalmology::visual_acuity_decimal", _ns_visual_acuity_decimal, _acc_visual_acuity_decimal)
    var _result_visual_acuity_decimal = visual_acuity_decimal(0.5, 0.5)
    var _summary_visual_acuity_decimal = _summary_float64(_result_visual_acuity_decimal)
    print("MOJO_RESULT ophthalmology::visual_acuity_decimal", _summary_visual_acuity_decimal)
    var _acc_refractive_error_spherical: Float64 = 0.0
    var _t0_refractive_error_spherical = perf_counter_ns()
    for _ in range(N):
        _acc_refractive_error_spherical += refractive_error_spherical(0.5)
    var _t1_refractive_error_spherical = perf_counter_ns()
    var _ns_refractive_error_spherical = Float64(_t1_refractive_error_spherical - _t0_refractive_error_spherical) / Float64(N)
    print("MOJO_TIMING ophthalmology::refractive_error_spherical", _ns_refractive_error_spherical, _acc_refractive_error_spherical)
    var _result_refractive_error_spherical = refractive_error_spherical(0.5)
    var _summary_refractive_error_spherical = _summary_float64(_result_refractive_error_spherical)
    print("MOJO_RESULT ophthalmology::refractive_error_spherical", _summary_refractive_error_spherical)
    var _acc_lens_power: Float64 = 0.0
    var _t0_lens_power = perf_counter_ns()
    for _ in range(N):
        _acc_lens_power += lens_power(0.5, 0.5, 0.5, 0.5)
    var _t1_lens_power = perf_counter_ns()
    var _ns_lens_power = Float64(_t1_lens_power - _t0_lens_power) / Float64(N)
    print("MOJO_TIMING ophthalmology::lens_power", _ns_lens_power, _acc_lens_power)
    var _result_lens_power = lens_power(0.5, 0.5, 0.5, 0.5)
    var _summary_lens_power = _summary_float64(_result_lens_power)
    print("MOJO_RESULT ophthalmology::lens_power", _summary_lens_power)
    var _acc_intraocular_pressure: Float64 = 0.0
    var _t0_intraocular_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_intraocular_pressure += intraocular_pressure(0.5, 0.5)
    var _t1_intraocular_pressure = perf_counter_ns()
    var _ns_intraocular_pressure = Float64(_t1_intraocular_pressure - _t0_intraocular_pressure) / Float64(N)
    print("MOJO_TIMING ophthalmology::intraocular_pressure", _ns_intraocular_pressure, _acc_intraocular_pressure)
    var _result_intraocular_pressure = intraocular_pressure(0.5, 0.5)
    var _summary_intraocular_pressure = _summary_float64(_result_intraocular_pressure)
    print("MOJO_RESULT ophthalmology::intraocular_pressure", _summary_intraocular_pressure)
    var _acc_corneal_radius_from_keratometry: Float64 = 0.0
    var _t0_corneal_radius_from_keratometry = perf_counter_ns()
    for _ in range(N):
        _acc_corneal_radius_from_keratometry += corneal_radius_from_keratometry(0.5)
    var _t1_corneal_radius_from_keratometry = perf_counter_ns()
    var _ns_corneal_radius_from_keratometry = Float64(_t1_corneal_radius_from_keratometry - _t0_corneal_radius_from_keratometry) / Float64(N)
    print("MOJO_TIMING ophthalmology::corneal_radius_from_keratometry", _ns_corneal_radius_from_keratometry, _acc_corneal_radius_from_keratometry)
    var _result_corneal_radius_from_keratometry = corneal_radius_from_keratometry(0.5)
    var _summary_corneal_radius_from_keratometry = _summary_float64(_result_corneal_radius_from_keratometry)
    print("MOJO_RESULT ophthalmology::corneal_radius_from_keratometry", _summary_corneal_radius_from_keratometry)
    var _acc_retinal_image_size: Float64 = 0.0
    var _t0_retinal_image_size = perf_counter_ns()
    for _ in range(N):
        _acc_retinal_image_size += retinal_image_size(0.5, 0.5, 0.5)
    var _t1_retinal_image_size = perf_counter_ns()
    var _ns_retinal_image_size = Float64(_t1_retinal_image_size - _t0_retinal_image_size) / Float64(N)
    print("MOJO_TIMING ophthalmology::retinal_image_size", _ns_retinal_image_size, _acc_retinal_image_size)
    var _result_retinal_image_size = retinal_image_size(0.5, 0.5, 0.5)
    var _summary_retinal_image_size = _summary_float64(_result_retinal_image_size)
    print("MOJO_RESULT ophthalmology::retinal_image_size", _summary_retinal_image_size)
    var _acc_depth_of_focus: Float64 = 0.0
    var _t0_depth_of_focus = perf_counter_ns()
    for _ in range(N):
        _acc_depth_of_focus += depth_of_focus(0.5, 0.5)
    var _t1_depth_of_focus = perf_counter_ns()
    var _ns_depth_of_focus = Float64(_t1_depth_of_focus - _t0_depth_of_focus) / Float64(N)
    print("MOJO_TIMING ophthalmology::depth_of_focus", _ns_depth_of_focus, _acc_depth_of_focus)
    var _result_depth_of_focus = depth_of_focus(0.5, 0.5)
    var _summary_depth_of_focus = _summary_float64(_result_depth_of_focus)
    print("MOJO_RESULT ophthalmology::depth_of_focus", _summary_depth_of_focus)
    var _acc_critical_flicker_frequency: Float64 = 0.0
    var _t0_critical_flicker_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_critical_flicker_frequency += critical_flicker_frequency(0.5, 0.5, 0.5)
    var _t1_critical_flicker_frequency = perf_counter_ns()
    var _ns_critical_flicker_frequency = Float64(_t1_critical_flicker_frequency - _t0_critical_flicker_frequency) / Float64(N)
    print("MOJO_TIMING ophthalmology::critical_flicker_frequency", _ns_critical_flicker_frequency, _acc_critical_flicker_frequency)
    var _result_critical_flicker_frequency = critical_flicker_frequency(0.5, 0.5, 0.5)
    var _summary_critical_flicker_frequency = _summary_float64(_result_critical_flicker_frequency)
    print("MOJO_RESULT ophthalmology::critical_flicker_frequency", _summary_critical_flicker_frequency)
    var _acc_contrast_sensitivity: Float64 = 0.0
    var _t0_contrast_sensitivity = perf_counter_ns()
    for _ in range(N):
        _acc_contrast_sensitivity += contrast_sensitivity(0.5, 0.5)
    var _t1_contrast_sensitivity = perf_counter_ns()
    var _ns_contrast_sensitivity = Float64(_t1_contrast_sensitivity - _t0_contrast_sensitivity) / Float64(N)
    print("MOJO_TIMING ophthalmology::contrast_sensitivity", _ns_contrast_sensitivity, _acc_contrast_sensitivity)
    var _result_contrast_sensitivity = contrast_sensitivity(0.5, 0.5)
    var _summary_contrast_sensitivity = _summary_float64(_result_contrast_sensitivity)
    print("MOJO_RESULT ophthalmology::contrast_sensitivity", _summary_contrast_sensitivity)
    var _acc_dark_adaptation_kinetics: Float64 = 0.0
    var _t0_dark_adaptation_kinetics = perf_counter_ns()
    for _ in range(N):
        _acc_dark_adaptation_kinetics += dark_adaptation_kinetics(0.5, 0.5, 0.5)
    var _t1_dark_adaptation_kinetics = perf_counter_ns()
    var _ns_dark_adaptation_kinetics = Float64(_t1_dark_adaptation_kinetics - _t0_dark_adaptation_kinetics) / Float64(N)
    print("MOJO_TIMING ophthalmology::dark_adaptation_kinetics", _ns_dark_adaptation_kinetics, _acc_dark_adaptation_kinetics)
    var _result_dark_adaptation_kinetics = dark_adaptation_kinetics(0.5, 0.5, 0.5)
    var _summary_dark_adaptation_kinetics = _summary_float64(_result_dark_adaptation_kinetics)
    print("MOJO_RESULT ophthalmology::dark_adaptation_kinetics", _summary_dark_adaptation_kinetics)
