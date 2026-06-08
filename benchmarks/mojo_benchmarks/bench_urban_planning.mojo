"""bench_urban_planning.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from urban_planning import population_density, floor_area_ratio, lot_coverage, green_space_ratio, walk_score_distance_decay, vehicle_miles_traveled, parking_requirement, traffic_level_of_service, housing_affordability_ratio, jobs_housing_balance, infrastructure_cost_per_unit, impervious_surface_ratio
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_population_density: Float64 = 0.0
    var _t0_population_density = perf_counter_ns()
    for _ in range(N):
        _acc_population_density += population_density(0.5, 0.5)
    var _t1_population_density = perf_counter_ns()
    var _ns_population_density = Float64(_t1_population_density - _t0_population_density) / Float64(N)
    print("MOJO_TIMING urban_planning::population_density", _ns_population_density, _acc_population_density)
    var _result_population_density = population_density(0.5, 0.5)
    var _summary_population_density = _summary_float64(_result_population_density)
    print("MOJO_RESULT urban_planning::population_density", _summary_population_density)
    var _acc_floor_area_ratio: Float64 = 0.0
    var _t0_floor_area_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_floor_area_ratio += floor_area_ratio(0.5, 0.5)
    var _t1_floor_area_ratio = perf_counter_ns()
    var _ns_floor_area_ratio = Float64(_t1_floor_area_ratio - _t0_floor_area_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::floor_area_ratio", _ns_floor_area_ratio, _acc_floor_area_ratio)
    var _result_floor_area_ratio = floor_area_ratio(0.5, 0.5)
    var _summary_floor_area_ratio = _summary_float64(_result_floor_area_ratio)
    print("MOJO_RESULT urban_planning::floor_area_ratio", _summary_floor_area_ratio)
    var _acc_lot_coverage: Float64 = 0.0
    var _t0_lot_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_lot_coverage += lot_coverage(0.5, 0.5)
    var _t1_lot_coverage = perf_counter_ns()
    var _ns_lot_coverage = Float64(_t1_lot_coverage - _t0_lot_coverage) / Float64(N)
    print("MOJO_TIMING urban_planning::lot_coverage", _ns_lot_coverage, _acc_lot_coverage)
    var _result_lot_coverage = lot_coverage(0.5, 0.5)
    var _summary_lot_coverage = _summary_float64(_result_lot_coverage)
    print("MOJO_RESULT urban_planning::lot_coverage", _summary_lot_coverage)
    var _acc_green_space_ratio: Float64 = 0.0
    var _t0_green_space_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_green_space_ratio += green_space_ratio(0.5, 0.5)
    var _t1_green_space_ratio = perf_counter_ns()
    var _ns_green_space_ratio = Float64(_t1_green_space_ratio - _t0_green_space_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::green_space_ratio", _ns_green_space_ratio, _acc_green_space_ratio)
    var _result_green_space_ratio = green_space_ratio(0.5, 0.5)
    var _summary_green_space_ratio = _summary_float64(_result_green_space_ratio)
    print("MOJO_RESULT urban_planning::green_space_ratio", _summary_green_space_ratio)
    var _acc_walk_score_distance_decay: Float64 = 0.0
    var _t0_walk_score_distance_decay = perf_counter_ns()
    for _ in range(N):
        _acc_walk_score_distance_decay += walk_score_distance_decay(0.5, 0.5)
    var _t1_walk_score_distance_decay = perf_counter_ns()
    var _ns_walk_score_distance_decay = Float64(_t1_walk_score_distance_decay - _t0_walk_score_distance_decay) / Float64(N)
    print("MOJO_TIMING urban_planning::walk_score_distance_decay", _ns_walk_score_distance_decay, _acc_walk_score_distance_decay)
    var _result_walk_score_distance_decay = walk_score_distance_decay(0.5, 0.5)
    var _summary_walk_score_distance_decay = _summary_float64(_result_walk_score_distance_decay)
    print("MOJO_RESULT urban_planning::walk_score_distance_decay", _summary_walk_score_distance_decay)
    var _acc_vehicle_miles_traveled: Float64 = 0.0
    var _t0_vehicle_miles_traveled = perf_counter_ns()
    for _ in range(N):
        _acc_vehicle_miles_traveled += vehicle_miles_traveled(0.5, 0.5)
    var _t1_vehicle_miles_traveled = perf_counter_ns()
    var _ns_vehicle_miles_traveled = Float64(_t1_vehicle_miles_traveled - _t0_vehicle_miles_traveled) / Float64(N)
    print("MOJO_TIMING urban_planning::vehicle_miles_traveled", _ns_vehicle_miles_traveled, _acc_vehicle_miles_traveled)
    var _result_vehicle_miles_traveled = vehicle_miles_traveled(0.5, 0.5)
    var _summary_vehicle_miles_traveled = _summary_float64(_result_vehicle_miles_traveled)
    print("MOJO_RESULT urban_planning::vehicle_miles_traveled", _summary_vehicle_miles_traveled)
    var _acc_parking_requirement: Float64 = 0.0
    var _t0_parking_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_parking_requirement += parking_requirement(0.5, 0.5)
    var _t1_parking_requirement = perf_counter_ns()
    var _ns_parking_requirement = Float64(_t1_parking_requirement - _t0_parking_requirement) / Float64(N)
    print("MOJO_TIMING urban_planning::parking_requirement", _ns_parking_requirement, _acc_parking_requirement)
    var _result_parking_requirement = parking_requirement(0.5, 0.5)
    var _summary_parking_requirement = _summary_float64(_result_parking_requirement)
    print("MOJO_RESULT urban_planning::parking_requirement", _summary_parking_requirement)
    var _acc_traffic_level_of_service: Float64 = 0.0
    var _t0_traffic_level_of_service = perf_counter_ns()
    for _ in range(N):
        _acc_traffic_level_of_service += traffic_level_of_service(0.5, 0.5)
    var _t1_traffic_level_of_service = perf_counter_ns()
    var _ns_traffic_level_of_service = Float64(_t1_traffic_level_of_service - _t0_traffic_level_of_service) / Float64(N)
    print("MOJO_TIMING urban_planning::traffic_level_of_service", _ns_traffic_level_of_service, _acc_traffic_level_of_service)
    var _result_traffic_level_of_service = traffic_level_of_service(0.5, 0.5)
    var _summary_traffic_level_of_service = _summary_float64(_result_traffic_level_of_service)
    print("MOJO_RESULT urban_planning::traffic_level_of_service", _summary_traffic_level_of_service)
    var _acc_housing_affordability_ratio: Float64 = 0.0
    var _t0_housing_affordability_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_housing_affordability_ratio += housing_affordability_ratio(0.5, 0.5)
    var _t1_housing_affordability_ratio = perf_counter_ns()
    var _ns_housing_affordability_ratio = Float64(_t1_housing_affordability_ratio - _t0_housing_affordability_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::housing_affordability_ratio", _ns_housing_affordability_ratio, _acc_housing_affordability_ratio)
    var _result_housing_affordability_ratio = housing_affordability_ratio(0.5, 0.5)
    var _summary_housing_affordability_ratio = _summary_float64(_result_housing_affordability_ratio)
    print("MOJO_RESULT urban_planning::housing_affordability_ratio", _summary_housing_affordability_ratio)
    var _acc_jobs_housing_balance: Float64 = 0.0
    var _t0_jobs_housing_balance = perf_counter_ns()
    for _ in range(N):
        _acc_jobs_housing_balance += jobs_housing_balance(0.5, 0.5)
    var _t1_jobs_housing_balance = perf_counter_ns()
    var _ns_jobs_housing_balance = Float64(_t1_jobs_housing_balance - _t0_jobs_housing_balance) / Float64(N)
    print("MOJO_TIMING urban_planning::jobs_housing_balance", _ns_jobs_housing_balance, _acc_jobs_housing_balance)
    var _result_jobs_housing_balance = jobs_housing_balance(0.5, 0.5)
    var _summary_jobs_housing_balance = _summary_float64(_result_jobs_housing_balance)
    print("MOJO_RESULT urban_planning::jobs_housing_balance", _summary_jobs_housing_balance)
    var _acc_infrastructure_cost_per_unit: Float64 = 0.0
    var _t0_infrastructure_cost_per_unit = perf_counter_ns()
    for _ in range(N):
        _acc_infrastructure_cost_per_unit += infrastructure_cost_per_unit(0.5, 0.5)
    var _t1_infrastructure_cost_per_unit = perf_counter_ns()
    var _ns_infrastructure_cost_per_unit = Float64(_t1_infrastructure_cost_per_unit - _t0_infrastructure_cost_per_unit) / Float64(N)
    print("MOJO_TIMING urban_planning::infrastructure_cost_per_unit", _ns_infrastructure_cost_per_unit, _acc_infrastructure_cost_per_unit)
    var _result_infrastructure_cost_per_unit = infrastructure_cost_per_unit(0.5, 0.5)
    var _summary_infrastructure_cost_per_unit = _summary_float64(_result_infrastructure_cost_per_unit)
    print("MOJO_RESULT urban_planning::infrastructure_cost_per_unit", _summary_infrastructure_cost_per_unit)
    var _acc_impervious_surface_ratio: Float64 = 0.0
    var _t0_impervious_surface_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_impervious_surface_ratio += impervious_surface_ratio(0.5, 0.5)
    var _t1_impervious_surface_ratio = perf_counter_ns()
    var _ns_impervious_surface_ratio = Float64(_t1_impervious_surface_ratio - _t0_impervious_surface_ratio) / Float64(N)
    print("MOJO_TIMING urban_planning::impervious_surface_ratio", _ns_impervious_surface_ratio, _acc_impervious_surface_ratio)
    var _result_impervious_surface_ratio = impervious_surface_ratio(0.5, 0.5)
    var _summary_impervious_surface_ratio = _summary_float64(_result_impervious_surface_ratio)
    print("MOJO_RESULT urban_planning::impervious_surface_ratio", _summary_impervious_surface_ratio)
