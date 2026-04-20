"""bench_immunology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from immunology import antibody_titer, seroconversion_rate, antigen_antibody_binding, complement_activation, t_cell_proliferation, innate_response_decay, vaccine_efficacy, herd_immunity_threshold, antibody_avidity_index, opsonisation_index
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

    var _acc_antibody_titer: Float64 = 0.0
    var _t0_antibody_titer = perf_counter_ns()
    for _ in range(N):
        _acc_antibody_titer += antibody_titer(0.5, 0.5)
    var _t1_antibody_titer = perf_counter_ns()
    var _ns_antibody_titer = Float64(_t1_antibody_titer - _t0_antibody_titer) / Float64(N)
    print("MOJO_TIMING immunology::antibody_titer", _ns_antibody_titer, _acc_antibody_titer)
    var _acc_seroconversion_rate: Float64 = 0.0
    var _t0_seroconversion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_seroconversion_rate += seroconversion_rate(0.5, 0.5)
    var _t1_seroconversion_rate = perf_counter_ns()
    var _ns_seroconversion_rate = Float64(_t1_seroconversion_rate - _t0_seroconversion_rate) / Float64(N)
    print("MOJO_TIMING immunology::seroconversion_rate", _ns_seroconversion_rate, _acc_seroconversion_rate)
    var _acc_antigen_antibody_binding: Float64 = 0.0
    var _t0_antigen_antibody_binding = perf_counter_ns()
    for _ in range(N):
        _acc_antigen_antibody_binding += antigen_antibody_binding(0.5, 0.5, 0.5)
    var _t1_antigen_antibody_binding = perf_counter_ns()
    var _ns_antigen_antibody_binding = Float64(_t1_antigen_antibody_binding - _t0_antigen_antibody_binding) / Float64(N)
    print("MOJO_TIMING immunology::antigen_antibody_binding", _ns_antigen_antibody_binding, _acc_antigen_antibody_binding)
    var _acc_complement_activation: Float64 = 0.0
    var _t0_complement_activation = perf_counter_ns()
    for _ in range(N):
        _acc_complement_activation += complement_activation(0.5, 0.5, 0.5)
    var _t1_complement_activation = perf_counter_ns()
    var _ns_complement_activation = Float64(_t1_complement_activation - _t0_complement_activation) / Float64(N)
    print("MOJO_TIMING immunology::complement_activation", _ns_complement_activation, _acc_complement_activation)
    var _acc_t_cell_proliferation: Float64 = 0.0
    var _t0_t_cell_proliferation = perf_counter_ns()
    for _ in range(N):
        _acc_t_cell_proliferation += t_cell_proliferation(0.5, 0.5, 0.5, 0.5)
    var _t1_t_cell_proliferation = perf_counter_ns()
    var _ns_t_cell_proliferation = Float64(_t1_t_cell_proliferation - _t0_t_cell_proliferation) / Float64(N)
    print("MOJO_TIMING immunology::t_cell_proliferation", _ns_t_cell_proliferation, _acc_t_cell_proliferation)
    var _acc_innate_response_decay: Float64 = 0.0
    var _t0_innate_response_decay = perf_counter_ns()
    for _ in range(N):
        _acc_innate_response_decay += innate_response_decay(0.5, 0.5, 0.5)
    var _t1_innate_response_decay = perf_counter_ns()
    var _ns_innate_response_decay = Float64(_t1_innate_response_decay - _t0_innate_response_decay) / Float64(N)
    print("MOJO_TIMING immunology::innate_response_decay", _ns_innate_response_decay, _acc_innate_response_decay)
    var _acc_vaccine_efficacy: Float64 = 0.0
    var _t0_vaccine_efficacy = perf_counter_ns()
    for _ in range(N):
        _acc_vaccine_efficacy += vaccine_efficacy(0.5, 0.5)
    var _t1_vaccine_efficacy = perf_counter_ns()
    var _ns_vaccine_efficacy = Float64(_t1_vaccine_efficacy - _t0_vaccine_efficacy) / Float64(N)
    print("MOJO_TIMING immunology::vaccine_efficacy", _ns_vaccine_efficacy, _acc_vaccine_efficacy)
    var _acc_herd_immunity_threshold: Float64 = 0.0
    var _t0_herd_immunity_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_herd_immunity_threshold += herd_immunity_threshold(0.5)
    var _t1_herd_immunity_threshold = perf_counter_ns()
    var _ns_herd_immunity_threshold = Float64(_t1_herd_immunity_threshold - _t0_herd_immunity_threshold) / Float64(N)
    print("MOJO_TIMING immunology::herd_immunity_threshold", _ns_herd_immunity_threshold, _acc_herd_immunity_threshold)
    var _acc_antibody_avidity_index: Float64 = 0.0
    var _t0_antibody_avidity_index = perf_counter_ns()
    for _ in range(N):
        _acc_antibody_avidity_index += antibody_avidity_index(0.5, 0.5)
    var _t1_antibody_avidity_index = perf_counter_ns()
    var _ns_antibody_avidity_index = Float64(_t1_antibody_avidity_index - _t0_antibody_avidity_index) / Float64(N)
    print("MOJO_TIMING immunology::antibody_avidity_index", _ns_antibody_avidity_index, _acc_antibody_avidity_index)
    var _acc_opsonisation_index: Float64 = 0.0
    var _t0_opsonisation_index = perf_counter_ns()
    for _ in range(N):
        _acc_opsonisation_index += opsonisation_index(0.5, 0.5)
    var _t1_opsonisation_index = perf_counter_ns()
    var _ns_opsonisation_index = Float64(_t1_opsonisation_index - _t0_opsonisation_index) / Float64(N)
    print("MOJO_TIMING immunology::opsonisation_index", _ns_opsonisation_index, _acc_opsonisation_index)
