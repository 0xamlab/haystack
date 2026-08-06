"""bench_veterinary.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from veterinary import dose_mg, fluid_rate_ml_hr, fluid_deficit, maintenance_fluid_dog, caloric_requirement_dog, body_condition_score_ideal, anesthesia_mac, gestation_period_days, heart_rate_normal_range_low, heart_rate_normal_range_high, packed_cell_volume_normal, blood_volume_estimate
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

    var _acc_dose_mg: Float64 = 0.0
    var _t0_dose_mg = perf_counter_ns()
    for _ in range(N):
        _acc_dose_mg += dose_mg(0.5, 0.5)
    var _t1_dose_mg = perf_counter_ns()
    var _ns_dose_mg = Float64(_t1_dose_mg - _t0_dose_mg) / Float64(N)
    print("MOJO_TIMING veterinary::dose_mg", _ns_dose_mg, _acc_dose_mg)
    var _result_dose_mg = dose_mg(0.5, 0.5)
    var _summary_dose_mg = _summary_float64(_result_dose_mg)
    print("MOJO_RESULT veterinary::dose_mg", _summary_dose_mg)
    var _acc_fluid_rate_ml_hr: Float64 = 0.0
    var _t0_fluid_rate_ml_hr = perf_counter_ns()
    for _ in range(N):
        _acc_fluid_rate_ml_hr += fluid_rate_ml_hr(0.5, 0.5)
    var _t1_fluid_rate_ml_hr = perf_counter_ns()
    var _ns_fluid_rate_ml_hr = Float64(_t1_fluid_rate_ml_hr - _t0_fluid_rate_ml_hr) / Float64(N)
    print("MOJO_TIMING veterinary::fluid_rate_ml_hr", _ns_fluid_rate_ml_hr, _acc_fluid_rate_ml_hr)
    var _result_fluid_rate_ml_hr = fluid_rate_ml_hr(0.5, 0.5)
    var _summary_fluid_rate_ml_hr = _summary_float64(_result_fluid_rate_ml_hr)
    print("MOJO_RESULT veterinary::fluid_rate_ml_hr", _summary_fluid_rate_ml_hr)
    var _acc_fluid_deficit: Float64 = 0.0
    var _t0_fluid_deficit = perf_counter_ns()
    for _ in range(N):
        _acc_fluid_deficit += fluid_deficit(0.5, 0.5)
    var _t1_fluid_deficit = perf_counter_ns()
    var _ns_fluid_deficit = Float64(_t1_fluid_deficit - _t0_fluid_deficit) / Float64(N)
    print("MOJO_TIMING veterinary::fluid_deficit", _ns_fluid_deficit, _acc_fluid_deficit)
    var _result_fluid_deficit = fluid_deficit(0.5, 0.5)
    var _summary_fluid_deficit = _summary_float64(_result_fluid_deficit)
    print("MOJO_RESULT veterinary::fluid_deficit", _summary_fluid_deficit)
    var _acc_maintenance_fluid_dog: Float64 = 0.0
    var _t0_maintenance_fluid_dog = perf_counter_ns()
    for _ in range(N):
        _acc_maintenance_fluid_dog += maintenance_fluid_dog(0.5)
    var _t1_maintenance_fluid_dog = perf_counter_ns()
    var _ns_maintenance_fluid_dog = Float64(_t1_maintenance_fluid_dog - _t0_maintenance_fluid_dog) / Float64(N)
    print("MOJO_TIMING veterinary::maintenance_fluid_dog", _ns_maintenance_fluid_dog, _acc_maintenance_fluid_dog)
    var _result_maintenance_fluid_dog = maintenance_fluid_dog(0.5)
    var _summary_maintenance_fluid_dog = _summary_float64(_result_maintenance_fluid_dog)
    print("MOJO_RESULT veterinary::maintenance_fluid_dog", _summary_maintenance_fluid_dog)
    var _acc_caloric_requirement_dog: Float64 = 0.0
    var _t0_caloric_requirement_dog = perf_counter_ns()
    for _ in range(N):
        _acc_caloric_requirement_dog += caloric_requirement_dog(0.5)
    var _t1_caloric_requirement_dog = perf_counter_ns()
    var _ns_caloric_requirement_dog = Float64(_t1_caloric_requirement_dog - _t0_caloric_requirement_dog) / Float64(N)
    print("MOJO_TIMING veterinary::caloric_requirement_dog", _ns_caloric_requirement_dog, _acc_caloric_requirement_dog)
    var _result_caloric_requirement_dog = caloric_requirement_dog(0.5)
    var _summary_caloric_requirement_dog = _summary_float64(_result_caloric_requirement_dog)
    print("MOJO_RESULT veterinary::caloric_requirement_dog", _summary_caloric_requirement_dog)
    var _acc_body_condition_score_ideal: Float64 = 0.0
    var _t0_body_condition_score_ideal = perf_counter_ns()
    for _ in range(N):
        _acc_body_condition_score_ideal += body_condition_score_ideal(5)
    var _t1_body_condition_score_ideal = perf_counter_ns()
    var _ns_body_condition_score_ideal = Float64(_t1_body_condition_score_ideal - _t0_body_condition_score_ideal) / Float64(N)
    print("MOJO_TIMING veterinary::body_condition_score_ideal", _ns_body_condition_score_ideal, _acc_body_condition_score_ideal)
    var _result_body_condition_score_ideal = body_condition_score_ideal(5)
    var _summary_body_condition_score_ideal = _summary_float64(_result_body_condition_score_ideal)
    print("MOJO_RESULT veterinary::body_condition_score_ideal", _summary_body_condition_score_ideal)
    var _acc_anesthesia_mac: Float64 = 0.0
    var _t0_anesthesia_mac = perf_counter_ns()
    for _ in range(N):
        _acc_anesthesia_mac += anesthesia_mac(5, 5)
    var _t1_anesthesia_mac = perf_counter_ns()
    var _ns_anesthesia_mac = Float64(_t1_anesthesia_mac - _t0_anesthesia_mac) / Float64(N)
    print("MOJO_TIMING veterinary::anesthesia_mac", _ns_anesthesia_mac, _acc_anesthesia_mac)
    var _result_anesthesia_mac = anesthesia_mac(5, 5)
    var _summary_anesthesia_mac = _summary_float64(_result_anesthesia_mac)
    print("MOJO_RESULT veterinary::anesthesia_mac", _summary_anesthesia_mac)
    var _acc_gestation_period_days: Float64 = 0.0
    var _t0_gestation_period_days = perf_counter_ns()
    for _ in range(N):
        _acc_gestation_period_days += gestation_period_days(5)
    var _t1_gestation_period_days = perf_counter_ns()
    var _ns_gestation_period_days = Float64(_t1_gestation_period_days - _t0_gestation_period_days) / Float64(N)
    print("MOJO_TIMING veterinary::gestation_period_days", _ns_gestation_period_days, _acc_gestation_period_days)
    var _result_gestation_period_days = gestation_period_days(5)
    var _summary_gestation_period_days = _summary_float64(_result_gestation_period_days)
    print("MOJO_RESULT veterinary::gestation_period_days", _summary_gestation_period_days)
    var _acc_heart_rate_normal_range_low: Float64 = 0.0
    var _t0_heart_rate_normal_range_low = perf_counter_ns()
    for _ in range(N):
        _acc_heart_rate_normal_range_low += heart_rate_normal_range_low(5)
    var _t1_heart_rate_normal_range_low = perf_counter_ns()
    var _ns_heart_rate_normal_range_low = Float64(_t1_heart_rate_normal_range_low - _t0_heart_rate_normal_range_low) / Float64(N)
    print("MOJO_TIMING veterinary::heart_rate_normal_range_low", _ns_heart_rate_normal_range_low, _acc_heart_rate_normal_range_low)
    var _result_heart_rate_normal_range_low = heart_rate_normal_range_low(5)
    var _summary_heart_rate_normal_range_low = _summary_float64(_result_heart_rate_normal_range_low)
    print("MOJO_RESULT veterinary::heart_rate_normal_range_low", _summary_heart_rate_normal_range_low)
    var _acc_heart_rate_normal_range_high: Float64 = 0.0
    var _t0_heart_rate_normal_range_high = perf_counter_ns()
    for _ in range(N):
        _acc_heart_rate_normal_range_high += heart_rate_normal_range_high(5)
    var _t1_heart_rate_normal_range_high = perf_counter_ns()
    var _ns_heart_rate_normal_range_high = Float64(_t1_heart_rate_normal_range_high - _t0_heart_rate_normal_range_high) / Float64(N)
    print("MOJO_TIMING veterinary::heart_rate_normal_range_high", _ns_heart_rate_normal_range_high, _acc_heart_rate_normal_range_high)
    var _result_heart_rate_normal_range_high = heart_rate_normal_range_high(5)
    var _summary_heart_rate_normal_range_high = _summary_float64(_result_heart_rate_normal_range_high)
    print("MOJO_RESULT veterinary::heart_rate_normal_range_high", _summary_heart_rate_normal_range_high)
    var _acc_packed_cell_volume_normal: Float64 = 0.0
    var _t0_packed_cell_volume_normal = perf_counter_ns()
    for _ in range(N):
        _acc_packed_cell_volume_normal += packed_cell_volume_normal(5)
    var _t1_packed_cell_volume_normal = perf_counter_ns()
    var _ns_packed_cell_volume_normal = Float64(_t1_packed_cell_volume_normal - _t0_packed_cell_volume_normal) / Float64(N)
    print("MOJO_TIMING veterinary::packed_cell_volume_normal", _ns_packed_cell_volume_normal, _acc_packed_cell_volume_normal)
    var _result_packed_cell_volume_normal = packed_cell_volume_normal(5)
    var _summary_packed_cell_volume_normal = _summary_float64(_result_packed_cell_volume_normal)
    print("MOJO_RESULT veterinary::packed_cell_volume_normal", _summary_packed_cell_volume_normal)
    var _acc_blood_volume_estimate: Float64 = 0.0
    var _t0_blood_volume_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_blood_volume_estimate += blood_volume_estimate(0.5, 5)
    var _t1_blood_volume_estimate = perf_counter_ns()
    var _ns_blood_volume_estimate = Float64(_t1_blood_volume_estimate - _t0_blood_volume_estimate) / Float64(N)
    print("MOJO_TIMING veterinary::blood_volume_estimate", _ns_blood_volume_estimate, _acc_blood_volume_estimate)
    var _result_blood_volume_estimate = blood_volume_estimate(0.5, 5)
    var _summary_blood_volume_estimate = _summary_float64(_result_blood_volume_estimate)
    print("MOJO_RESULT veterinary::blood_volume_estimate", _summary_blood_volume_estimate)
