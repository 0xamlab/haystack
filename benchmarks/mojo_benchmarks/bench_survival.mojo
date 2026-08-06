"""bench_survival.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from survival import kaplan_meier, nelson_aalen, log_rank_statistic, hazard_rate, life_table
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

    var _acc_kaplan_meier: Float64 = 0.0
    var _t0_kaplan_meier = perf_counter_ns()
    for _ in range(N):
        var _r_kaplan_meier = kaplan_meier(_lf5, _lb5)
        _acc_kaplan_meier += Float64(len(_r_kaplan_meier))
    var _t1_kaplan_meier = perf_counter_ns()
    var _ns_kaplan_meier = Float64(_t1_kaplan_meier - _t0_kaplan_meier) / Float64(N)
    print("MOJO_TIMING survival::kaplan_meier", _ns_kaplan_meier, _acc_kaplan_meier)
    var _acc_nelson_aalen: Float64 = 0.0
    var _t0_nelson_aalen = perf_counter_ns()
    for _ in range(N):
        var _r_nelson_aalen = nelson_aalen(_lf5, _lb5)
        _acc_nelson_aalen += Float64(len(_r_nelson_aalen))
    var _t1_nelson_aalen = perf_counter_ns()
    var _ns_nelson_aalen = Float64(_t1_nelson_aalen - _t0_nelson_aalen) / Float64(N)
    print("MOJO_TIMING survival::nelson_aalen", _ns_nelson_aalen, _acc_nelson_aalen)
    var _result_nelson_aalen = nelson_aalen(_lf5, _lb5)
    var _summary_nelson_aalen = _summary_list_list_float64(_result_nelson_aalen)
    print("MOJO_RESULT survival::nelson_aalen", _summary_nelson_aalen)
    var _acc_log_rank_statistic: Float64 = 0.0
    var _t0_log_rank_statistic = perf_counter_ns()
    for _ in range(N):
        _acc_log_rank_statistic += log_rank_statistic(_lf5, _lb5, _lf5, _lb5)
    var _t1_log_rank_statistic = perf_counter_ns()
    var _ns_log_rank_statistic = Float64(_t1_log_rank_statistic - _t0_log_rank_statistic) / Float64(N)
    print("MOJO_TIMING survival::log_rank_statistic", _ns_log_rank_statistic, _acc_log_rank_statistic)
    var _result_log_rank_statistic = log_rank_statistic(_lf5, _lb5, _lf5, _lb5)
    var _summary_log_rank_statistic = _summary_float64(_result_log_rank_statistic)
    print("MOJO_RESULT survival::log_rank_statistic", _summary_log_rank_statistic)
    var _acc_hazard_rate: Float64 = 0.0
    var _t0_hazard_rate = perf_counter_ns()
    for _ in range(N):
        var _r_hazard_rate = hazard_rate(_lf5, _lb5, 0.5)
        _acc_hazard_rate += Float64(len(_r_hazard_rate))
    var _t1_hazard_rate = perf_counter_ns()
    var _ns_hazard_rate = Float64(_t1_hazard_rate - _t0_hazard_rate) / Float64(N)
    print("MOJO_TIMING survival::hazard_rate", _ns_hazard_rate, _acc_hazard_rate)
    var _result_hazard_rate = hazard_rate(_lf5, _lb5, 0.5)
    var _summary_hazard_rate = _summary_list_list_float64(_result_hazard_rate)
    print("MOJO_RESULT survival::hazard_rate", _summary_hazard_rate)
    var _acc_life_table: Float64 = 0.0
    var _t0_life_table = perf_counter_ns()
    for _ in range(N):
        var _r_life_table = life_table(_lf5, _lb5, _lf5)
        _acc_life_table += Float64(len(_r_life_table))
    var _t1_life_table = perf_counter_ns()
    var _ns_life_table = Float64(_t1_life_table - _t0_life_table) / Float64(N)
    print("MOJO_TIMING survival::life_table", _ns_life_table, _acc_life_table)
    var _result_life_table = life_table(_lf5, _lb5, _lf5)
    var _summary_life_table = _summary_list_list_float64(_result_life_table)
    print("MOJO_RESULT survival::life_table", _summary_life_table)
