"""bench_ophthalmology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ophthalmology import visual_acuity_decimal, refractive_error_spherical, lens_power, intraocular_pressure, corneal_radius_from_keratometry, retinal_image_size, depth_of_focus, critical_flicker_frequency, contrast_sensitivity, dark_adaptation_kinetics
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

    var _acc_visual_acuity_decimal: Float64 = 0.0
    var _t0_visual_acuity_decimal = perf_counter_ns()
    for _ in range(N):
        _acc_visual_acuity_decimal += visual_acuity_decimal(0.5, 0.5)
    var _t1_visual_acuity_decimal = perf_counter_ns()
    var _ns_visual_acuity_decimal = Float64(_t1_visual_acuity_decimal - _t0_visual_acuity_decimal) / Float64(N)
    print("MOJO_TIMING ophthalmology::visual_acuity_decimal", _ns_visual_acuity_decimal, _acc_visual_acuity_decimal)
    var _acc_refractive_error_spherical: Float64 = 0.0
    var _t0_refractive_error_spherical = perf_counter_ns()
    for _ in range(N):
        _acc_refractive_error_spherical += refractive_error_spherical(0.5)
    var _t1_refractive_error_spherical = perf_counter_ns()
    var _ns_refractive_error_spherical = Float64(_t1_refractive_error_spherical - _t0_refractive_error_spherical) / Float64(N)
    print("MOJO_TIMING ophthalmology::refractive_error_spherical", _ns_refractive_error_spherical, _acc_refractive_error_spherical)
    var _acc_lens_power: Float64 = 0.0
    var _t0_lens_power = perf_counter_ns()
    for _ in range(N):
        _acc_lens_power += lens_power(0.5, 0.5, 0.5, 0.5)
    var _t1_lens_power = perf_counter_ns()
    var _ns_lens_power = Float64(_t1_lens_power - _t0_lens_power) / Float64(N)
    print("MOJO_TIMING ophthalmology::lens_power", _ns_lens_power, _acc_lens_power)
    var _acc_intraocular_pressure: Float64 = 0.0
    var _t0_intraocular_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_intraocular_pressure += intraocular_pressure(0.5, 0.5)
    var _t1_intraocular_pressure = perf_counter_ns()
    var _ns_intraocular_pressure = Float64(_t1_intraocular_pressure - _t0_intraocular_pressure) / Float64(N)
    print("MOJO_TIMING ophthalmology::intraocular_pressure", _ns_intraocular_pressure, _acc_intraocular_pressure)
    var _acc_corneal_radius_from_keratometry: Float64 = 0.0
    var _t0_corneal_radius_from_keratometry = perf_counter_ns()
    for _ in range(N):
        _acc_corneal_radius_from_keratometry += corneal_radius_from_keratometry(0.5)
    var _t1_corneal_radius_from_keratometry = perf_counter_ns()
    var _ns_corneal_radius_from_keratometry = Float64(_t1_corneal_radius_from_keratometry - _t0_corneal_radius_from_keratometry) / Float64(N)
    print("MOJO_TIMING ophthalmology::corneal_radius_from_keratometry", _ns_corneal_radius_from_keratometry, _acc_corneal_radius_from_keratometry)
    var _acc_retinal_image_size: Float64 = 0.0
    var _t0_retinal_image_size = perf_counter_ns()
    for _ in range(N):
        _acc_retinal_image_size += retinal_image_size(0.5, 0.5, 0.5)
    var _t1_retinal_image_size = perf_counter_ns()
    var _ns_retinal_image_size = Float64(_t1_retinal_image_size - _t0_retinal_image_size) / Float64(N)
    print("MOJO_TIMING ophthalmology::retinal_image_size", _ns_retinal_image_size, _acc_retinal_image_size)
    var _acc_depth_of_focus: Float64 = 0.0
    var _t0_depth_of_focus = perf_counter_ns()
    for _ in range(N):
        _acc_depth_of_focus += depth_of_focus(0.5, 0.5)
    var _t1_depth_of_focus = perf_counter_ns()
    var _ns_depth_of_focus = Float64(_t1_depth_of_focus - _t0_depth_of_focus) / Float64(N)
    print("MOJO_TIMING ophthalmology::depth_of_focus", _ns_depth_of_focus, _acc_depth_of_focus)
    var _acc_critical_flicker_frequency: Float64 = 0.0
    var _t0_critical_flicker_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_critical_flicker_frequency += critical_flicker_frequency(0.5, 0.5, 0.5)
    var _t1_critical_flicker_frequency = perf_counter_ns()
    var _ns_critical_flicker_frequency = Float64(_t1_critical_flicker_frequency - _t0_critical_flicker_frequency) / Float64(N)
    print("MOJO_TIMING ophthalmology::critical_flicker_frequency", _ns_critical_flicker_frequency, _acc_critical_flicker_frequency)
    var _acc_contrast_sensitivity: Float64 = 0.0
    var _t0_contrast_sensitivity = perf_counter_ns()
    for _ in range(N):
        _acc_contrast_sensitivity += contrast_sensitivity(0.5, 0.5)
    var _t1_contrast_sensitivity = perf_counter_ns()
    var _ns_contrast_sensitivity = Float64(_t1_contrast_sensitivity - _t0_contrast_sensitivity) / Float64(N)
    print("MOJO_TIMING ophthalmology::contrast_sensitivity", _ns_contrast_sensitivity, _acc_contrast_sensitivity)
    var _acc_dark_adaptation_kinetics: Float64 = 0.0
    var _t0_dark_adaptation_kinetics = perf_counter_ns()
    for _ in range(N):
        _acc_dark_adaptation_kinetics += dark_adaptation_kinetics(0.5, 0.5, 0.5)
    var _t1_dark_adaptation_kinetics = perf_counter_ns()
    var _ns_dark_adaptation_kinetics = Float64(_t1_dark_adaptation_kinetics - _t0_dark_adaptation_kinetics) / Float64(N)
    print("MOJO_TIMING ophthalmology::dark_adaptation_kinetics", _ns_dark_adaptation_kinetics, _acc_dark_adaptation_kinetics)
