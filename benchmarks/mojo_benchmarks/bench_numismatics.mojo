"""bench_numismatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from numismatics import melt_value, premium_over_melt, grade_numeric_to_scale, population_scarcity, annual_return, insurance_value, mintage_per_capita, survival_rate_estimate, price_trend, auction_fee, total_cost_acquisition, bullion_content_troy_oz
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

    var _acc_melt_value: Float64 = 0.0
    var _t0_melt_value = perf_counter_ns()
    for _ in range(N):
        _acc_melt_value += melt_value(0.5, 0.5)
    var _t1_melt_value = perf_counter_ns()
    var _ns_melt_value = Float64(_t1_melt_value - _t0_melt_value) / Float64(N)
    print("MOJO_TIMING numismatics::melt_value", _ns_melt_value, _acc_melt_value)
    var _result_melt_value = melt_value(0.5, 0.5)
    var _summary_melt_value = _summary_float64(_result_melt_value)
    print("MOJO_RESULT numismatics::melt_value", _summary_melt_value)
    var _acc_premium_over_melt: Float64 = 0.0
    var _t0_premium_over_melt = perf_counter_ns()
    for _ in range(N):
        _acc_premium_over_melt += premium_over_melt(0.5, 0.5)
    var _t1_premium_over_melt = perf_counter_ns()
    var _ns_premium_over_melt = Float64(_t1_premium_over_melt - _t0_premium_over_melt) / Float64(N)
    print("MOJO_TIMING numismatics::premium_over_melt", _ns_premium_over_melt, _acc_premium_over_melt)
    var _result_premium_over_melt = premium_over_melt(0.5, 0.5)
    var _summary_premium_over_melt = _summary_float64(_result_premium_over_melt)
    print("MOJO_RESULT numismatics::premium_over_melt", _summary_premium_over_melt)
    var _acc_grade_numeric_to_scale: Float64 = 0.0
    var _t0_grade_numeric_to_scale = perf_counter_ns()
    for _ in range(N):
        _acc_grade_numeric_to_scale += grade_numeric_to_scale(0.5)
    var _t1_grade_numeric_to_scale = perf_counter_ns()
    var _ns_grade_numeric_to_scale = Float64(_t1_grade_numeric_to_scale - _t0_grade_numeric_to_scale) / Float64(N)
    print("MOJO_TIMING numismatics::grade_numeric_to_scale", _ns_grade_numeric_to_scale, _acc_grade_numeric_to_scale)
    var _result_grade_numeric_to_scale = grade_numeric_to_scale(0.5)
    var _summary_grade_numeric_to_scale = _summary_float64(_result_grade_numeric_to_scale)
    print("MOJO_RESULT numismatics::grade_numeric_to_scale", _summary_grade_numeric_to_scale)
    var _acc_population_scarcity: Float64 = 0.0
    var _t0_population_scarcity = perf_counter_ns()
    for _ in range(N):
        _acc_population_scarcity += population_scarcity(0.5, 0.5)
    var _t1_population_scarcity = perf_counter_ns()
    var _ns_population_scarcity = Float64(_t1_population_scarcity - _t0_population_scarcity) / Float64(N)
    print("MOJO_TIMING numismatics::population_scarcity", _ns_population_scarcity, _acc_population_scarcity)
    var _result_population_scarcity = population_scarcity(0.5, 0.5)
    var _summary_population_scarcity = _summary_float64(_result_population_scarcity)
    print("MOJO_RESULT numismatics::population_scarcity", _summary_population_scarcity)
    var _acc_annual_return: Float64 = 0.0
    var _t0_annual_return = perf_counter_ns()
    for _ in range(N):
        _acc_annual_return += annual_return(0.5, 0.5, 0.5)
    var _t1_annual_return = perf_counter_ns()
    var _ns_annual_return = Float64(_t1_annual_return - _t0_annual_return) / Float64(N)
    print("MOJO_TIMING numismatics::annual_return", _ns_annual_return, _acc_annual_return)
    var _result_annual_return = annual_return(0.5, 0.5, 0.5)
    var _summary_annual_return = _summary_float64(_result_annual_return)
    print("MOJO_RESULT numismatics::annual_return", _summary_annual_return)
    var _acc_insurance_value: Float64 = 0.0
    var _t0_insurance_value = perf_counter_ns()
    for _ in range(N):
        _acc_insurance_value += insurance_value(0.5, 0.5)
    var _t1_insurance_value = perf_counter_ns()
    var _ns_insurance_value = Float64(_t1_insurance_value - _t0_insurance_value) / Float64(N)
    print("MOJO_TIMING numismatics::insurance_value", _ns_insurance_value, _acc_insurance_value)
    var _result_insurance_value = insurance_value(0.5, 0.5)
    var _summary_insurance_value = _summary_float64(_result_insurance_value)
    print("MOJO_RESULT numismatics::insurance_value", _summary_insurance_value)
    var _acc_mintage_per_capita: Float64 = 0.0
    var _t0_mintage_per_capita = perf_counter_ns()
    for _ in range(N):
        _acc_mintage_per_capita += mintage_per_capita(0.5, 0.5)
    var _t1_mintage_per_capita = perf_counter_ns()
    var _ns_mintage_per_capita = Float64(_t1_mintage_per_capita - _t0_mintage_per_capita) / Float64(N)
    print("MOJO_TIMING numismatics::mintage_per_capita", _ns_mintage_per_capita, _acc_mintage_per_capita)
    var _result_mintage_per_capita = mintage_per_capita(0.5, 0.5)
    var _summary_mintage_per_capita = _summary_float64(_result_mintage_per_capita)
    print("MOJO_RESULT numismatics::mintage_per_capita", _summary_mintage_per_capita)
    var _acc_survival_rate_estimate: Float64 = 0.0
    var _t0_survival_rate_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_survival_rate_estimate += survival_rate_estimate(0.5, 0.5)
    var _t1_survival_rate_estimate = perf_counter_ns()
    var _ns_survival_rate_estimate = Float64(_t1_survival_rate_estimate - _t0_survival_rate_estimate) / Float64(N)
    print("MOJO_TIMING numismatics::survival_rate_estimate", _ns_survival_rate_estimate, _acc_survival_rate_estimate)
    var _result_survival_rate_estimate = survival_rate_estimate(0.5, 0.5)
    var _summary_survival_rate_estimate = _summary_float64(_result_survival_rate_estimate)
    print("MOJO_RESULT numismatics::survival_rate_estimate", _summary_survival_rate_estimate)
    var _acc_price_trend: Float64 = 0.0
    var _t0_price_trend = perf_counter_ns()
    for _ in range(N):
        _acc_price_trend += price_trend(0.5, 0.5)
    var _t1_price_trend = perf_counter_ns()
    var _ns_price_trend = Float64(_t1_price_trend - _t0_price_trend) / Float64(N)
    print("MOJO_TIMING numismatics::price_trend", _ns_price_trend, _acc_price_trend)
    var _result_price_trend = price_trend(0.5, 0.5)
    var _summary_price_trend = _summary_float64(_result_price_trend)
    print("MOJO_RESULT numismatics::price_trend", _summary_price_trend)
    var _acc_auction_fee: Float64 = 0.0
    var _t0_auction_fee = perf_counter_ns()
    for _ in range(N):
        _acc_auction_fee += auction_fee(0.5, 0.5)
    var _t1_auction_fee = perf_counter_ns()
    var _ns_auction_fee = Float64(_t1_auction_fee - _t0_auction_fee) / Float64(N)
    print("MOJO_TIMING numismatics::auction_fee", _ns_auction_fee, _acc_auction_fee)
    var _result_auction_fee = auction_fee(0.5, 0.5)
    var _summary_auction_fee = _summary_float64(_result_auction_fee)
    print("MOJO_RESULT numismatics::auction_fee", _summary_auction_fee)
    var _acc_total_cost_acquisition: Float64 = 0.0
    var _t0_total_cost_acquisition = perf_counter_ns()
    for _ in range(N):
        _acc_total_cost_acquisition += total_cost_acquisition(0.5, 0.5, 0.5)
    var _t1_total_cost_acquisition = perf_counter_ns()
    var _ns_total_cost_acquisition = Float64(_t1_total_cost_acquisition - _t0_total_cost_acquisition) / Float64(N)
    print("MOJO_TIMING numismatics::total_cost_acquisition", _ns_total_cost_acquisition, _acc_total_cost_acquisition)
    var _result_total_cost_acquisition = total_cost_acquisition(0.5, 0.5, 0.5)
    var _summary_total_cost_acquisition = _summary_float64(_result_total_cost_acquisition)
    print("MOJO_RESULT numismatics::total_cost_acquisition", _summary_total_cost_acquisition)
    var _acc_bullion_content_troy_oz: Float64 = 0.0
    var _t0_bullion_content_troy_oz = perf_counter_ns()
    for _ in range(N):
        _acc_bullion_content_troy_oz += bullion_content_troy_oz(0.5, 0.5)
    var _t1_bullion_content_troy_oz = perf_counter_ns()
    var _ns_bullion_content_troy_oz = Float64(_t1_bullion_content_troy_oz - _t0_bullion_content_troy_oz) / Float64(N)
    print("MOJO_TIMING numismatics::bullion_content_troy_oz", _ns_bullion_content_troy_oz, _acc_bullion_content_troy_oz)
    var _result_bullion_content_troy_oz = bullion_content_troy_oz(0.5, 0.5)
    var _summary_bullion_content_troy_oz = _summary_float64(_result_bullion_content_troy_oz)
    print("MOJO_RESULT numismatics::bullion_content_troy_oz", _summary_bullion_content_troy_oz)
