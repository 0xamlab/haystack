"""bench_paper_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paper_science import basis_weight, caliper_to_density, bulk, tearing_resistance_index, tensile_index, burst_index, freeness_csf, kappa_number_to_lignin, pulp_yield, moisture_content_paper, stiffness_index, recycled_fiber_content
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

    var _acc_basis_weight: Float64 = 0.0
    var _t0_basis_weight = perf_counter_ns()
    for _ in range(N):
        _acc_basis_weight += basis_weight(0.5, 0.5)
    var _t1_basis_weight = perf_counter_ns()
    var _ns_basis_weight = Float64(_t1_basis_weight - _t0_basis_weight) / Float64(N)
    print("MOJO_TIMING paper_science::basis_weight", _ns_basis_weight, _acc_basis_weight)
    var _acc_caliper_to_density: Float64 = 0.0
    var _t0_caliper_to_density = perf_counter_ns()
    for _ in range(N):
        _acc_caliper_to_density += caliper_to_density(0.5, 0.5)
    var _t1_caliper_to_density = perf_counter_ns()
    var _ns_caliper_to_density = Float64(_t1_caliper_to_density - _t0_caliper_to_density) / Float64(N)
    print("MOJO_TIMING paper_science::caliper_to_density", _ns_caliper_to_density, _acc_caliper_to_density)
    var _acc_bulk: Float64 = 0.0
    var _t0_bulk = perf_counter_ns()
    for _ in range(N):
        _acc_bulk += bulk(0.5, 0.5)
    var _t1_bulk = perf_counter_ns()
    var _ns_bulk = Float64(_t1_bulk - _t0_bulk) / Float64(N)
    print("MOJO_TIMING paper_science::bulk", _ns_bulk, _acc_bulk)
    var _acc_tearing_resistance_index: Float64 = 0.0
    var _t0_tearing_resistance_index = perf_counter_ns()
    for _ in range(N):
        _acc_tearing_resistance_index += tearing_resistance_index(0.5, 0.5)
    var _t1_tearing_resistance_index = perf_counter_ns()
    var _ns_tearing_resistance_index = Float64(_t1_tearing_resistance_index - _t0_tearing_resistance_index) / Float64(N)
    print("MOJO_TIMING paper_science::tearing_resistance_index", _ns_tearing_resistance_index, _acc_tearing_resistance_index)
    var _acc_tensile_index: Float64 = 0.0
    var _t0_tensile_index = perf_counter_ns()
    for _ in range(N):
        _acc_tensile_index += tensile_index(0.5, 0.5)
    var _t1_tensile_index = perf_counter_ns()
    var _ns_tensile_index = Float64(_t1_tensile_index - _t0_tensile_index) / Float64(N)
    print("MOJO_TIMING paper_science::tensile_index", _ns_tensile_index, _acc_tensile_index)
    var _acc_burst_index: Float64 = 0.0
    var _t0_burst_index = perf_counter_ns()
    for _ in range(N):
        _acc_burst_index += burst_index(0.5, 0.5)
    var _t1_burst_index = perf_counter_ns()
    var _ns_burst_index = Float64(_t1_burst_index - _t0_burst_index) / Float64(N)
    print("MOJO_TIMING paper_science::burst_index", _ns_burst_index, _acc_burst_index)
    var _acc_freeness_csf: Float64 = 0.0
    var _t0_freeness_csf = perf_counter_ns()
    for _ in range(N):
        _acc_freeness_csf += freeness_csf(0.5)
    var _t1_freeness_csf = perf_counter_ns()
    var _ns_freeness_csf = Float64(_t1_freeness_csf - _t0_freeness_csf) / Float64(N)
    print("MOJO_TIMING paper_science::freeness_csf", _ns_freeness_csf, _acc_freeness_csf)
    var _acc_kappa_number_to_lignin: Float64 = 0.0
    var _t0_kappa_number_to_lignin = perf_counter_ns()
    for _ in range(N):
        _acc_kappa_number_to_lignin += kappa_number_to_lignin(0.5)
    var _t1_kappa_number_to_lignin = perf_counter_ns()
    var _ns_kappa_number_to_lignin = Float64(_t1_kappa_number_to_lignin - _t0_kappa_number_to_lignin) / Float64(N)
    print("MOJO_TIMING paper_science::kappa_number_to_lignin", _ns_kappa_number_to_lignin, _acc_kappa_number_to_lignin)
    var _acc_pulp_yield: Float64 = 0.0
    var _t0_pulp_yield = perf_counter_ns()
    for _ in range(N):
        _acc_pulp_yield += pulp_yield(0.5, 0.5)
    var _t1_pulp_yield = perf_counter_ns()
    var _ns_pulp_yield = Float64(_t1_pulp_yield - _t0_pulp_yield) / Float64(N)
    print("MOJO_TIMING paper_science::pulp_yield", _ns_pulp_yield, _acc_pulp_yield)
    var _acc_moisture_content_paper: Float64 = 0.0
    var _t0_moisture_content_paper = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_paper += moisture_content_paper(0.5, 0.5)
    var _t1_moisture_content_paper = perf_counter_ns()
    var _ns_moisture_content_paper = Float64(_t1_moisture_content_paper - _t0_moisture_content_paper) / Float64(N)
    print("MOJO_TIMING paper_science::moisture_content_paper", _ns_moisture_content_paper, _acc_moisture_content_paper)
    var _acc_stiffness_index: Float64 = 0.0
    var _t0_stiffness_index = perf_counter_ns()
    for _ in range(N):
        _acc_stiffness_index += stiffness_index(0.5, 0.5)
    var _t1_stiffness_index = perf_counter_ns()
    var _ns_stiffness_index = Float64(_t1_stiffness_index - _t0_stiffness_index) / Float64(N)
    print("MOJO_TIMING paper_science::stiffness_index", _ns_stiffness_index, _acc_stiffness_index)
    var _acc_recycled_fiber_content: Float64 = 0.0
    var _t0_recycled_fiber_content = perf_counter_ns()
    for _ in range(N):
        _acc_recycled_fiber_content += recycled_fiber_content(0.5, 0.5)
    var _t1_recycled_fiber_content = perf_counter_ns()
    var _ns_recycled_fiber_content = Float64(_t1_recycled_fiber_content - _t0_recycled_fiber_content) / Float64(N)
    print("MOJO_TIMING paper_science::recycled_fiber_content", _ns_recycled_fiber_content, _acc_recycled_fiber_content)
