"""bench_urban_planning.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from urban_planning import population_density, floor_area_ratio, lot_coverage, green_space_ratio, walk_score_distance_decay, vehicle_miles_traveled, parking_requirement, traffic_level_of_service, housing_affordability_ratio, jobs_housing_balance, infrastructure_cost_per_unit, impervious_surface_ratio
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

    var _acc_population_density: Float64 = 0.0
    var _t0_population_density = perf_counter_ns()
    for _ in range(N):
        _acc_population_density += population_density(0.5, 0.5)
    var _t1_population_density = perf_counter_ns()
    var _ns_population_density = Float64(_t1_population_density - _t0_population_density) / Float64(N)
    print("MOJO_TIMING urban_planning::population_density", _ns_population_density, _acc_population_density)
    var _acc_floor_area_ratio: Float64 = 0.0
    var _t0_floor_area_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_floor_area_ratio += floor_area_ratio(0.5, 0.5)
    var _t1_floor_area_ratio = perf_counter_ns()
    var _ns_floor_area_ratio = Float64(_t1_floor_area_ratio - _t0_floor_area_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::floor_area_ratio", _ns_floor_area_ratio, _acc_floor_area_ratio)
    var _acc_lot_coverage: Float64 = 0.0
    var _t0_lot_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_lot_coverage += lot_coverage(0.5, 0.5)
    var _t1_lot_coverage = perf_counter_ns()
    var _ns_lot_coverage = Float64(_t1_lot_coverage - _t0_lot_coverage) / Float64(N)
    print("MOJO_TIMING urban_planning::lot_coverage", _ns_lot_coverage, _acc_lot_coverage)
    var _acc_green_space_ratio: Float64 = 0.0
    var _t0_green_space_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_green_space_ratio += green_space_ratio(0.5, 0.5)
    var _t1_green_space_ratio = perf_counter_ns()
    var _ns_green_space_ratio = Float64(_t1_green_space_ratio - _t0_green_space_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::green_space_ratio", _ns_green_space_ratio, _acc_green_space_ratio)
    var _acc_walk_score_distance_decay: Float64 = 0.0
    var _t0_walk_score_distance_decay = perf_counter_ns()
    for _ in range(N):
        _acc_walk_score_distance_decay += walk_score_distance_decay(0.5, 0.5)
    var _t1_walk_score_distance_decay = perf_counter_ns()
    var _ns_walk_score_distance_decay = Float64(_t1_walk_score_distance_decay - _t0_walk_score_distance_decay) / Float64(N)
    print("MOJO_TIMING urban_planning::walk_score_distance_decay", _ns_walk_score_distance_decay, _acc_walk_score_distance_decay)
    var _acc_vehicle_miles_traveled: Float64 = 0.0
    var _t0_vehicle_miles_traveled = perf_counter_ns()
    for _ in range(N):
        _acc_vehicle_miles_traveled += vehicle_miles_traveled(0.5, 0.5)
    var _t1_vehicle_miles_traveled = perf_counter_ns()
    var _ns_vehicle_miles_traveled = Float64(_t1_vehicle_miles_traveled - _t0_vehicle_miles_traveled) / Float64(N)
    print("MOJO_TIMING urban_planning::vehicle_miles_traveled", _ns_vehicle_miles_traveled, _acc_vehicle_miles_traveled)
    var _acc_parking_requirement: Float64 = 0.0
    var _t0_parking_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_parking_requirement += parking_requirement(0.5, 0.5)
    var _t1_parking_requirement = perf_counter_ns()
    var _ns_parking_requirement = Float64(_t1_parking_requirement - _t0_parking_requirement) / Float64(N)
    print("MOJO_TIMING urban_planning::parking_requirement", _ns_parking_requirement, _acc_parking_requirement)
    var _acc_traffic_level_of_service: Float64 = 0.0
    var _t0_traffic_level_of_service = perf_counter_ns()
    for _ in range(N):
        _acc_traffic_level_of_service += traffic_level_of_service(0.5, 0.5)
    var _t1_traffic_level_of_service = perf_counter_ns()
    var _ns_traffic_level_of_service = Float64(_t1_traffic_level_of_service - _t0_traffic_level_of_service) / Float64(N)
    print("MOJO_TIMING urban_planning::traffic_level_of_service", _ns_traffic_level_of_service, _acc_traffic_level_of_service)
    var _acc_housing_affordability_ratio: Float64 = 0.0
    var _t0_housing_affordability_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_housing_affordability_ratio += housing_affordability_ratio(0.5, 0.5)
    var _t1_housing_affordability_ratio = perf_counter_ns()
    var _ns_housing_affordability_ratio = Float64(_t1_housing_affordability_ratio - _t0_housing_affordability_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::housing_affordability_ratio", _ns_housing_affordability_ratio, _acc_housing_affordability_ratio)
    var _acc_jobs_housing_balance: Float64 = 0.0
    var _t0_jobs_housing_balance = perf_counter_ns()
    for _ in range(N):
        _acc_jobs_housing_balance += jobs_housing_balance(0.5, 0.5)
    var _t1_jobs_housing_balance = perf_counter_ns()
    var _ns_jobs_housing_balance = Float64(_t1_jobs_housing_balance - _t0_jobs_housing_balance) / Float64(N)
    print("MOJO_TIMING urban_planning::jobs_housing_balance", _ns_jobs_housing_balance, _acc_jobs_housing_balance)
    var _acc_infrastructure_cost_per_unit: Float64 = 0.0
    var _t0_infrastructure_cost_per_unit = perf_counter_ns()
    for _ in range(N):
        _acc_infrastructure_cost_per_unit += infrastructure_cost_per_unit(0.5, 0.5)
    var _t1_infrastructure_cost_per_unit = perf_counter_ns()
    var _ns_infrastructure_cost_per_unit = Float64(_t1_infrastructure_cost_per_unit - _t0_infrastructure_cost_per_unit) / Float64(N)
    print("MOJO_TIMING urban_planning::infrastructure_cost_per_unit", _ns_infrastructure_cost_per_unit, _acc_infrastructure_cost_per_unit)
    var _acc_impervious_surface_ratio: Float64 = 0.0
    var _t0_impervious_surface_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_impervious_surface_ratio += impervious_surface_ratio(0.5, 0.5)
    var _t1_impervious_surface_ratio = perf_counter_ns()
    var _ns_impervious_surface_ratio = Float64(_t1_impervious_surface_ratio - _t0_impervious_surface_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::impervious_surface_ratio", _ns_impervious_surface_ratio, _acc_impervious_surface_ratio)
