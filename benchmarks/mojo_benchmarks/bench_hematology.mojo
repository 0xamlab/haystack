"""bench_hematology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hematology import hematocrit, mean_corpuscular_volume, mean_corpuscular_hemoglobin, mchc, red_cell_distribution_width, oxygen_carrying_capacity, coagulation_inr, platelet_count_index, blood_viscosity_relative, erythrocyte_sedimentation
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

    var _acc_hematocrit: Float64 = 0.0
    var _t0_hematocrit = perf_counter_ns()
    for _ in range(N):
        _acc_hematocrit += hematocrit(0.5, 0.5)
    var _t1_hematocrit = perf_counter_ns()
    var _ns_hematocrit = Float64(_t1_hematocrit - _t0_hematocrit) / Float64(N)
    print("MOJO_TIMING hematology::hematocrit", _ns_hematocrit, _acc_hematocrit)
    var _acc_mean_corpuscular_volume: Float64 = 0.0
    var _t0_mean_corpuscular_volume = perf_counter_ns()
    for _ in range(N):
        _acc_mean_corpuscular_volume += mean_corpuscular_volume(0.5, 0.5)
    var _t1_mean_corpuscular_volume = perf_counter_ns()
    var _ns_mean_corpuscular_volume = Float64(_t1_mean_corpuscular_volume - _t0_mean_corpuscular_volume) / Float64(N)
    print("MOJO_TIMING hematology::mean_corpuscular_volume", _ns_mean_corpuscular_volume, _acc_mean_corpuscular_volume)
    var _acc_mean_corpuscular_hemoglobin: Float64 = 0.0
    var _t0_mean_corpuscular_hemoglobin = perf_counter_ns()
    for _ in range(N):
        _acc_mean_corpuscular_hemoglobin += mean_corpuscular_hemoglobin(0.5, 0.5)
    var _t1_mean_corpuscular_hemoglobin = perf_counter_ns()
    var _ns_mean_corpuscular_hemoglobin = Float64(_t1_mean_corpuscular_hemoglobin - _t0_mean_corpuscular_hemoglobin) / Float64(N)
    print("MOJO_TIMING hematology::mean_corpuscular_hemoglobin", _ns_mean_corpuscular_hemoglobin, _acc_mean_corpuscular_hemoglobin)
    var _acc_mchc: Float64 = 0.0
    var _t0_mchc = perf_counter_ns()
    for _ in range(N):
        _acc_mchc += mchc(0.5, 0.5)
    var _t1_mchc = perf_counter_ns()
    var _ns_mchc = Float64(_t1_mchc - _t0_mchc) / Float64(N)
    print("MOJO_TIMING hematology::mchc", _ns_mchc, _acc_mchc)
    var _acc_red_cell_distribution_width: Float64 = 0.0
    var _t0_red_cell_distribution_width = perf_counter_ns()
    for _ in range(N):
        _acc_red_cell_distribution_width += red_cell_distribution_width(0.5, 0.5)
    var _t1_red_cell_distribution_width = perf_counter_ns()
    var _ns_red_cell_distribution_width = Float64(_t1_red_cell_distribution_width - _t0_red_cell_distribution_width) / Float64(N)
    print("MOJO_TIMING hematology::red_cell_distribution_width", _ns_red_cell_distribution_width, _acc_red_cell_distribution_width)
    var _acc_oxygen_carrying_capacity: Float64 = 0.0
    var _t0_oxygen_carrying_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_carrying_capacity += oxygen_carrying_capacity(0.5)
    var _t1_oxygen_carrying_capacity = perf_counter_ns()
    var _ns_oxygen_carrying_capacity = Float64(_t1_oxygen_carrying_capacity - _t0_oxygen_carrying_capacity) / Float64(N)
    print("MOJO_TIMING hematology::oxygen_carrying_capacity", _ns_oxygen_carrying_capacity, _acc_oxygen_carrying_capacity)
    var _acc_coagulation_inr: Float64 = 0.0
    var _t0_coagulation_inr = perf_counter_ns()
    for _ in range(N):
        _acc_coagulation_inr += coagulation_inr(0.5, 0.5, 0.5)
    var _t1_coagulation_inr = perf_counter_ns()
    var _ns_coagulation_inr = Float64(_t1_coagulation_inr - _t0_coagulation_inr) / Float64(N)
    print("MOJO_TIMING hematology::coagulation_inr", _ns_coagulation_inr, _acc_coagulation_inr)
    var _acc_platelet_count_index: Float64 = 0.0
    var _t0_platelet_count_index = perf_counter_ns()
    for _ in range(N):
        _acc_platelet_count_index += platelet_count_index(0.5, 0.5)
    var _t1_platelet_count_index = perf_counter_ns()
    var _ns_platelet_count_index = Float64(_t1_platelet_count_index - _t0_platelet_count_index) / Float64(N)
    print("MOJO_TIMING hematology::platelet_count_index", _ns_platelet_count_index, _acc_platelet_count_index)
    var _acc_blood_viscosity_relative: Float64 = 0.0
    var _t0_blood_viscosity_relative = perf_counter_ns()
    for _ in range(N):
        _acc_blood_viscosity_relative += blood_viscosity_relative(0.5)
    var _t1_blood_viscosity_relative = perf_counter_ns()
    var _ns_blood_viscosity_relative = Float64(_t1_blood_viscosity_relative - _t0_blood_viscosity_relative) / Float64(N)
    print("MOJO_TIMING hematology::blood_viscosity_relative", _ns_blood_viscosity_relative, _acc_blood_viscosity_relative)
    var _acc_erythrocyte_sedimentation: Float64 = 0.0
    var _t0_erythrocyte_sedimentation = perf_counter_ns()
    for _ in range(N):
        _acc_erythrocyte_sedimentation += erythrocyte_sedimentation(0.5, 0.5, 0.5)
    var _t1_erythrocyte_sedimentation = perf_counter_ns()
    var _ns_erythrocyte_sedimentation = Float64(_t1_erythrocyte_sedimentation - _t0_erythrocyte_sedimentation) / Float64(N)
    print("MOJO_TIMING hematology::erythrocyte_sedimentation", _ns_erythrocyte_sedimentation, _acc_erythrocyte_sedimentation)
