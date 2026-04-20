"""bench_kinetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from kinetics import reaction_rate_first_order, reaction_rate_second_order, arrhenius_rate_constant, half_life_first_order, half_life_second_order, concentration_first_order, activation_energy, collision_frequency, michaelis_menten_rate, turnover_number
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

    var _acc_reaction_rate_first_order: Float64 = 0.0
    var _t0_reaction_rate_first_order = perf_counter_ns()
    for _ in range(N):
        _acc_reaction_rate_first_order += reaction_rate_first_order(0.5, 0.5)
    var _t1_reaction_rate_first_order = perf_counter_ns()
    var _ns_reaction_rate_first_order = Float64(_t1_reaction_rate_first_order - _t0_reaction_rate_first_order) / Float64(N)
    print("MOJO_TIMING kinetics::reaction_rate_first_order", _ns_reaction_rate_first_order, _acc_reaction_rate_first_order)
    var _acc_reaction_rate_second_order: Float64 = 0.0
    var _t0_reaction_rate_second_order = perf_counter_ns()
    for _ in range(N):
        _acc_reaction_rate_second_order += reaction_rate_second_order(0.5, 0.5, 0.5)
    var _t1_reaction_rate_second_order = perf_counter_ns()
    var _ns_reaction_rate_second_order = Float64(_t1_reaction_rate_second_order - _t0_reaction_rate_second_order) / Float64(N)
    print("MOJO_TIMING kinetics::reaction_rate_second_order", _ns_reaction_rate_second_order, _acc_reaction_rate_second_order)
    var _acc_arrhenius_rate_constant: Float64 = 0.0
    var _t0_arrhenius_rate_constant = perf_counter_ns()
    for _ in range(N):
        _acc_arrhenius_rate_constant += arrhenius_rate_constant(0.5, 0.5, 0.5)
    var _t1_arrhenius_rate_constant = perf_counter_ns()
    var _ns_arrhenius_rate_constant = Float64(_t1_arrhenius_rate_constant - _t0_arrhenius_rate_constant) / Float64(N)
    print("MOJO_TIMING kinetics::arrhenius_rate_constant", _ns_arrhenius_rate_constant, _acc_arrhenius_rate_constant)
    var _acc_half_life_first_order: Float64 = 0.0
    var _t0_half_life_first_order = perf_counter_ns()
    for _ in range(N):
        _acc_half_life_first_order += half_life_first_order(0.5)
    var _t1_half_life_first_order = perf_counter_ns()
    var _ns_half_life_first_order = Float64(_t1_half_life_first_order - _t0_half_life_first_order) / Float64(N)
    print("MOJO_TIMING kinetics::half_life_first_order", _ns_half_life_first_order, _acc_half_life_first_order)
    var _acc_half_life_second_order: Float64 = 0.0
    var _t0_half_life_second_order = perf_counter_ns()
    for _ in range(N):
        _acc_half_life_second_order += half_life_second_order(0.5, 0.5)
    var _t1_half_life_second_order = perf_counter_ns()
    var _ns_half_life_second_order = Float64(_t1_half_life_second_order - _t0_half_life_second_order) / Float64(N)
    print("MOJO_TIMING kinetics::half_life_second_order", _ns_half_life_second_order, _acc_half_life_second_order)
    var _acc_concentration_first_order: Float64 = 0.0
    var _t0_concentration_first_order = perf_counter_ns()
    for _ in range(N):
        _acc_concentration_first_order += concentration_first_order(0.5, 0.5, 0.5)
    var _t1_concentration_first_order = perf_counter_ns()
    var _ns_concentration_first_order = Float64(_t1_concentration_first_order - _t0_concentration_first_order) / Float64(N)
    print("MOJO_TIMING kinetics::concentration_first_order", _ns_concentration_first_order, _acc_concentration_first_order)
    var _acc_activation_energy: Float64 = 0.0
    var _t0_activation_energy = perf_counter_ns()
    for _ in range(N):
        _acc_activation_energy += activation_energy(0.5, 0.5, 0.5, 0.5)
    var _t1_activation_energy = perf_counter_ns()
    var _ns_activation_energy = Float64(_t1_activation_energy - _t0_activation_energy) / Float64(N)
    print("MOJO_TIMING kinetics::activation_energy", _ns_activation_energy, _acc_activation_energy)
    var _acc_collision_frequency: Float64 = 0.0
    var _t0_collision_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_collision_frequency += collision_frequency(0.5, 0.5, 0.5, 0.5)
    var _t1_collision_frequency = perf_counter_ns()
    var _ns_collision_frequency = Float64(_t1_collision_frequency - _t0_collision_frequency) / Float64(N)
    print("MOJO_TIMING kinetics::collision_frequency", _ns_collision_frequency, _acc_collision_frequency)
    var _acc_michaelis_menten_rate: Float64 = 0.0
    var _t0_michaelis_menten_rate = perf_counter_ns()
    for _ in range(N):
        _acc_michaelis_menten_rate += michaelis_menten_rate(0.5, 0.5, 0.5)
    var _t1_michaelis_menten_rate = perf_counter_ns()
    var _ns_michaelis_menten_rate = Float64(_t1_michaelis_menten_rate - _t0_michaelis_menten_rate) / Float64(N)
    print("MOJO_TIMING kinetics::michaelis_menten_rate", _ns_michaelis_menten_rate, _acc_michaelis_menten_rate)
    var _acc_turnover_number: Float64 = 0.0
    var _t0_turnover_number = perf_counter_ns()
    for _ in range(N):
        _acc_turnover_number += turnover_number(0.5, 0.5)
    var _t1_turnover_number = perf_counter_ns()
    var _ns_turnover_number = Float64(_t1_turnover_number - _t0_turnover_number) / Float64(N)
    print("MOJO_TIMING kinetics::turnover_number", _ns_turnover_number, _acc_turnover_number)
