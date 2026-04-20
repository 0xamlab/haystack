"""bench_apiculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from apiculture import honey_yield_per_hive, colony_strength_estimate, varroa_infestation_rate, sugar_syrup_ratio, foraging_range_area, nectar_to_honey_ratio, brood_viability, winter_feed_requirement, queen_laying_rate, pollination_value, hive_density_per_hectare, overwintering_survival_rate
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

    var _acc_honey_yield_per_hive: Float64 = 0.0
    var _t0_honey_yield_per_hive = perf_counter_ns()
    for _ in range(N):
        _acc_honey_yield_per_hive += honey_yield_per_hive(0.5, 0.5)
    var _t1_honey_yield_per_hive = perf_counter_ns()
    var _ns_honey_yield_per_hive = Float64(_t1_honey_yield_per_hive - _t0_honey_yield_per_hive) / Float64(N)
    print("MOJO_TIMING apiculture::honey_yield_per_hive", _ns_honey_yield_per_hive, _acc_honey_yield_per_hive)
    var _acc_colony_strength_estimate: Float64 = 0.0
    var _t0_colony_strength_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_colony_strength_estimate += colony_strength_estimate(0.5, 0.5)
    var _t1_colony_strength_estimate = perf_counter_ns()
    var _ns_colony_strength_estimate = Float64(_t1_colony_strength_estimate - _t0_colony_strength_estimate) / Float64(N)
    print("MOJO_TIMING apiculture::colony_strength_estimate", _ns_colony_strength_estimate, _acc_colony_strength_estimate)
    var _acc_varroa_infestation_rate: Float64 = 0.0
    var _t0_varroa_infestation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_varroa_infestation_rate += varroa_infestation_rate(0.5, 0.5)
    var _t1_varroa_infestation_rate = perf_counter_ns()
    var _ns_varroa_infestation_rate = Float64(_t1_varroa_infestation_rate - _t0_varroa_infestation_rate) / Float64(N)
    print("MOJO_TIMING apiculture::varroa_infestation_rate", _ns_varroa_infestation_rate, _acc_varroa_infestation_rate)
    var _acc_sugar_syrup_ratio: Float64 = 0.0
    var _t0_sugar_syrup_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sugar_syrup_ratio += sugar_syrup_ratio(0.5, 0.5)
    var _t1_sugar_syrup_ratio = perf_counter_ns()
    var _ns_sugar_syrup_ratio = Float64(_t1_sugar_syrup_ratio - _t0_sugar_syrup_ratio) / Float64(N)
    print("MOJO_TIMING apiculture::sugar_syrup_ratio", _ns_sugar_syrup_ratio, _acc_sugar_syrup_ratio)
    var _acc_foraging_range_area: Float64 = 0.0
    var _t0_foraging_range_area = perf_counter_ns()
    for _ in range(N):
        _acc_foraging_range_area += foraging_range_area(0.5)
    var _t1_foraging_range_area = perf_counter_ns()
    var _ns_foraging_range_area = Float64(_t1_foraging_range_area - _t0_foraging_range_area) / Float64(N)
    print("MOJO_TIMING apiculture::foraging_range_area", _ns_foraging_range_area, _acc_foraging_range_area)
    var _acc_nectar_to_honey_ratio: Float64 = 0.0
    var _t0_nectar_to_honey_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_nectar_to_honey_ratio += nectar_to_honey_ratio(0.5)
    var _t1_nectar_to_honey_ratio = perf_counter_ns()
    var _ns_nectar_to_honey_ratio = Float64(_t1_nectar_to_honey_ratio - _t0_nectar_to_honey_ratio) / Float64(N)
    print("MOJO_TIMING apiculture::nectar_to_honey_ratio", _ns_nectar_to_honey_ratio, _acc_nectar_to_honey_ratio)
    var _acc_brood_viability: Float64 = 0.0
    var _t0_brood_viability = perf_counter_ns()
    for _ in range(N):
        _acc_brood_viability += brood_viability(0.5, 0.5)
    var _t1_brood_viability = perf_counter_ns()
    var _ns_brood_viability = Float64(_t1_brood_viability - _t0_brood_viability) / Float64(N)
    print("MOJO_TIMING apiculture::brood_viability", _ns_brood_viability, _acc_brood_viability)
    var _acc_winter_feed_requirement: Float64 = 0.0
    var _t0_winter_feed_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_winter_feed_requirement += winter_feed_requirement(0.5, 0.5, 0.5)
    var _t1_winter_feed_requirement = perf_counter_ns()
    var _ns_winter_feed_requirement = Float64(_t1_winter_feed_requirement - _t0_winter_feed_requirement) / Float64(N)
    print("MOJO_TIMING apiculture::winter_feed_requirement", _ns_winter_feed_requirement, _acc_winter_feed_requirement)
    var _acc_queen_laying_rate: Float64 = 0.0
    var _t0_queen_laying_rate = perf_counter_ns()
    for _ in range(N):
        _acc_queen_laying_rate += queen_laying_rate(0.5)
    var _t1_queen_laying_rate = perf_counter_ns()
    var _ns_queen_laying_rate = Float64(_t1_queen_laying_rate - _t0_queen_laying_rate) / Float64(N)
    print("MOJO_TIMING apiculture::queen_laying_rate", _ns_queen_laying_rate, _acc_queen_laying_rate)
    var _acc_pollination_value: Float64 = 0.0
    var _t0_pollination_value = perf_counter_ns()
    for _ in range(N):
        _acc_pollination_value += pollination_value(0.5, 0.5)
    var _t1_pollination_value = perf_counter_ns()
    var _ns_pollination_value = Float64(_t1_pollination_value - _t0_pollination_value) / Float64(N)
    print("MOJO_TIMING apiculture::pollination_value", _ns_pollination_value, _acc_pollination_value)
    var _acc_hive_density_per_hectare: Float64 = 0.0
    var _t0_hive_density_per_hectare = perf_counter_ns()
    for _ in range(N):
        _acc_hive_density_per_hectare += hive_density_per_hectare(0.5, 0.5)
    var _t1_hive_density_per_hectare = perf_counter_ns()
    var _ns_hive_density_per_hectare = Float64(_t1_hive_density_per_hectare - _t0_hive_density_per_hectare) / Float64(N)
    print("MOJO_TIMING apiculture::hive_density_per_hectare", _ns_hive_density_per_hectare, _acc_hive_density_per_hectare)
    var _acc_overwintering_survival_rate: Float64 = 0.0
    var _t0_overwintering_survival_rate = perf_counter_ns()
    for _ in range(N):
        _acc_overwintering_survival_rate += overwintering_survival_rate(0.5, 0.5)
    var _t1_overwintering_survival_rate = perf_counter_ns()
    var _ns_overwintering_survival_rate = Float64(_t1_overwintering_survival_rate - _t0_overwintering_survival_rate) / Float64(N)
    print("MOJO_TIMING apiculture::overwintering_survival_rate", _ns_overwintering_survival_rate, _acc_overwintering_survival_rate)
