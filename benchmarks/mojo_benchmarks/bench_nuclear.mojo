"""bench_nuclear.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nuclear import radioactive_decay, half_life_from_lambda, lambda_from_half_life, activity, decay_constant_from_activity, binding_energy_per_nucleon, mass_defect, q_value, neutron_multiplication, dose_rate_inverse_square, shielding_attenuation, critical_mass_estimate
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

    var _acc_radioactive_decay: Float64 = 0.0
    var _t0_radioactive_decay = perf_counter_ns()
    for _ in range(N):
        _acc_radioactive_decay += radioactive_decay(0.5, 0.5, 0.5)
    var _t1_radioactive_decay = perf_counter_ns()
    var _ns_radioactive_decay = Float64(_t1_radioactive_decay - _t0_radioactive_decay) / Float64(N)
    print("MOJO_TIMING nuclear::radioactive_decay", _ns_radioactive_decay, _acc_radioactive_decay)
    var _acc_half_life_from_lambda: Float64 = 0.0
    var _t0_half_life_from_lambda = perf_counter_ns()
    for _ in range(N):
        _acc_half_life_from_lambda += half_life_from_lambda(0.5)
    var _t1_half_life_from_lambda = perf_counter_ns()
    var _ns_half_life_from_lambda = Float64(_t1_half_life_from_lambda - _t0_half_life_from_lambda) / Float64(N)
    print("MOJO_TIMING nuclear::half_life_from_lambda", _ns_half_life_from_lambda, _acc_half_life_from_lambda)
    var _acc_lambda_from_half_life: Float64 = 0.0
    var _t0_lambda_from_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_lambda_from_half_life += lambda_from_half_life(0.5)
    var _t1_lambda_from_half_life = perf_counter_ns()
    var _ns_lambda_from_half_life = Float64(_t1_lambda_from_half_life - _t0_lambda_from_half_life) / Float64(N)
    print("MOJO_TIMING nuclear::lambda_from_half_life", _ns_lambda_from_half_life, _acc_lambda_from_half_life)
    var _acc_activity: Float64 = 0.0
    var _t0_activity = perf_counter_ns()
    for _ in range(N):
        _acc_activity += activity(0.5, 0.5)
    var _t1_activity = perf_counter_ns()
    var _ns_activity = Float64(_t1_activity - _t0_activity) / Float64(N)
    print("MOJO_TIMING nuclear::activity", _ns_activity, _acc_activity)
    var _acc_decay_constant_from_activity: Float64 = 0.0
    var _t0_decay_constant_from_activity = perf_counter_ns()
    for _ in range(N):
        _acc_decay_constant_from_activity += decay_constant_from_activity(0.5, 0.5)
    var _t1_decay_constant_from_activity = perf_counter_ns()
    var _ns_decay_constant_from_activity = Float64(_t1_decay_constant_from_activity - _t0_decay_constant_from_activity) / Float64(N)
    print("MOJO_TIMING nuclear::decay_constant_from_activity", _ns_decay_constant_from_activity, _acc_decay_constant_from_activity)
    var _acc_binding_energy_per_nucleon: Float64 = 0.0
    var _t0_binding_energy_per_nucleon = perf_counter_ns()
    for _ in range(N):
        _acc_binding_energy_per_nucleon += binding_energy_per_nucleon(0.5, 0.5)
    var _t1_binding_energy_per_nucleon = perf_counter_ns()
    var _ns_binding_energy_per_nucleon = Float64(_t1_binding_energy_per_nucleon - _t0_binding_energy_per_nucleon) / Float64(N)
    print("MOJO_TIMING nuclear::binding_energy_per_nucleon", _ns_binding_energy_per_nucleon, _acc_binding_energy_per_nucleon)
    var _acc_mass_defect: Float64 = 0.0
    var _t0_mass_defect = perf_counter_ns()
    for _ in range(N):
        _acc_mass_defect += mass_defect(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_mass_defect = perf_counter_ns()
    var _ns_mass_defect = Float64(_t1_mass_defect - _t0_mass_defect) / Float64(N)
    print("MOJO_TIMING nuclear::mass_defect", _ns_mass_defect, _acc_mass_defect)
    var _acc_q_value: Float64 = 0.0
    var _t0_q_value = perf_counter_ns()
    for _ in range(N):
        _acc_q_value += q_value(0.5, 0.5, 0.5)
    var _t1_q_value = perf_counter_ns()
    var _ns_q_value = Float64(_t1_q_value - _t0_q_value) / Float64(N)
    print("MOJO_TIMING nuclear::q_value", _ns_q_value, _acc_q_value)
    var _acc_neutron_multiplication: Float64 = 0.0
    var _t0_neutron_multiplication = perf_counter_ns()
    for _ in range(N):
        _acc_neutron_multiplication += neutron_multiplication(0.5, 0.5)
    var _t1_neutron_multiplication = perf_counter_ns()
    var _ns_neutron_multiplication = Float64(_t1_neutron_multiplication - _t0_neutron_multiplication) / Float64(N)
    print("MOJO_TIMING nuclear::neutron_multiplication", _ns_neutron_multiplication, _acc_neutron_multiplication)
    var _acc_dose_rate_inverse_square: Float64 = 0.0
    var _t0_dose_rate_inverse_square = perf_counter_ns()
    for _ in range(N):
        _acc_dose_rate_inverse_square += dose_rate_inverse_square(0.5, 0.5, 0.5)
    var _t1_dose_rate_inverse_square = perf_counter_ns()
    var _ns_dose_rate_inverse_square = Float64(_t1_dose_rate_inverse_square - _t0_dose_rate_inverse_square) / Float64(N)
    print("MOJO_TIMING nuclear::dose_rate_inverse_square", _ns_dose_rate_inverse_square, _acc_dose_rate_inverse_square)
    var _acc_shielding_attenuation: Float64 = 0.0
    var _t0_shielding_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_shielding_attenuation += shielding_attenuation(0.5, 0.5, 0.5)
    var _t1_shielding_attenuation = perf_counter_ns()
    var _ns_shielding_attenuation = Float64(_t1_shielding_attenuation - _t0_shielding_attenuation) / Float64(N)
    print("MOJO_TIMING nuclear::shielding_attenuation", _ns_shielding_attenuation, _acc_shielding_attenuation)
    var _acc_critical_mass_estimate: Float64 = 0.0
    var _t0_critical_mass_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_critical_mass_estimate += critical_mass_estimate(0.5, 0.5, 0.5)
    var _t1_critical_mass_estimate = perf_counter_ns()
    var _ns_critical_mass_estimate = Float64(_t1_critical_mass_estimate - _t0_critical_mass_estimate) / Float64(N)
    print("MOJO_TIMING nuclear::critical_mass_estimate", _ns_critical_mass_estimate, _acc_critical_mass_estimate)
