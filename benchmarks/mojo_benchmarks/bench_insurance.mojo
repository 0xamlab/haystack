"""bench_insurance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from insurance import pure_premium, gross_premium, loss_ratio, expense_ratio, combined_ratio, expected_claim_frequency, expected_claim_severity, burning_cost, credibility_buhlmann, risk_load, aggregate_deductible_savings, retention_rate
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

    var _acc_pure_premium: Float64 = 0.0
    var _t0_pure_premium = perf_counter_ns()
    for _ in range(N):
        _acc_pure_premium += pure_premium(0.5, 0.5)
    var _t1_pure_premium = perf_counter_ns()
    var _ns_pure_premium = Float64(_t1_pure_premium - _t0_pure_premium) / Float64(N)
    print("MOJO_TIMING insurance::pure_premium", _ns_pure_premium, _acc_pure_premium)
    var _result_pure_premium = pure_premium(0.5, 0.5)
    var _summary_pure_premium = _summary_float64(_result_pure_premium)
    print("MOJO_RESULT insurance::pure_premium", _summary_pure_premium)
    var _acc_gross_premium: Float64 = 0.0
    var _t0_gross_premium = perf_counter_ns()
    for _ in range(N):
        _acc_gross_premium += gross_premium(100.0, 0.2, 0.1)
    var _t1_gross_premium = perf_counter_ns()
    var _ns_gross_premium = Float64(_t1_gross_premium - _t0_gross_premium) / Float64(N)
    print("MOJO_TIMING insurance::gross_premium", _ns_gross_premium, _acc_gross_premium)
    var _result_gross_premium = gross_premium(100.0, 0.2, 0.1)
    var _summary_gross_premium = _summary_float64(_result_gross_premium)
    print("MOJO_RESULT insurance::gross_premium", _summary_gross_premium)
    var _acc_loss_ratio: Float64 = 0.0
    var _t0_loss_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_loss_ratio += loss_ratio(0.5, 0.5)
    var _t1_loss_ratio = perf_counter_ns()
    var _ns_loss_ratio = Float64(_t1_loss_ratio - _t0_loss_ratio) / Float64(N)
    print("MOJO_TIMING insurance::loss_ratio", _ns_loss_ratio, _acc_loss_ratio)
    var _result_loss_ratio = loss_ratio(0.5, 0.5)
    var _summary_loss_ratio = _summary_float64(_result_loss_ratio)
    print("MOJO_RESULT insurance::loss_ratio", _summary_loss_ratio)
    var _acc_expense_ratio: Float64 = 0.0
    var _t0_expense_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_expense_ratio += expense_ratio(0.5, 0.5)
    var _t1_expense_ratio = perf_counter_ns()
    var _ns_expense_ratio = Float64(_t1_expense_ratio - _t0_expense_ratio) / Float64(N)
    print("MOJO_TIMING insurance::expense_ratio", _ns_expense_ratio, _acc_expense_ratio)
    var _result_expense_ratio = expense_ratio(0.5, 0.5)
    var _summary_expense_ratio = _summary_float64(_result_expense_ratio)
    print("MOJO_RESULT insurance::expense_ratio", _summary_expense_ratio)
    var _acc_combined_ratio: Float64 = 0.0
    var _t0_combined_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_combined_ratio += combined_ratio(0.5, 0.5)
    var _t1_combined_ratio = perf_counter_ns()
    var _ns_combined_ratio = Float64(_t1_combined_ratio - _t0_combined_ratio) / Float64(N)
    print("MOJO_TIMING insurance::combined_ratio", _ns_combined_ratio, _acc_combined_ratio)
    var _result_combined_ratio = combined_ratio(0.5, 0.5)
    var _summary_combined_ratio = _summary_float64(_result_combined_ratio)
    print("MOJO_RESULT insurance::combined_ratio", _summary_combined_ratio)
    var _acc_expected_claim_frequency: Float64 = 0.0
    var _t0_expected_claim_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_expected_claim_frequency += expected_claim_frequency(0.5, 0.5)
    var _t1_expected_claim_frequency = perf_counter_ns()
    var _ns_expected_claim_frequency = Float64(_t1_expected_claim_frequency - _t0_expected_claim_frequency) / Float64(N)
    print("MOJO_TIMING insurance::expected_claim_frequency", _ns_expected_claim_frequency, _acc_expected_claim_frequency)
    var _result_expected_claim_frequency = expected_claim_frequency(0.5, 0.5)
    var _summary_expected_claim_frequency = _summary_float64(_result_expected_claim_frequency)
    print("MOJO_RESULT insurance::expected_claim_frequency", _summary_expected_claim_frequency)
    var _acc_expected_claim_severity: Float64 = 0.0
    var _t0_expected_claim_severity = perf_counter_ns()
    for _ in range(N):
        _acc_expected_claim_severity += expected_claim_severity(0.5, 0.5)
    var _t1_expected_claim_severity = perf_counter_ns()
    var _ns_expected_claim_severity = Float64(_t1_expected_claim_severity - _t0_expected_claim_severity) / Float64(N)
    print("MOJO_TIMING insurance::expected_claim_severity", _ns_expected_claim_severity, _acc_expected_claim_severity)
    var _result_expected_claim_severity = expected_claim_severity(0.5, 0.5)
    var _summary_expected_claim_severity = _summary_float64(_result_expected_claim_severity)
    print("MOJO_RESULT insurance::expected_claim_severity", _summary_expected_claim_severity)
    var _acc_burning_cost: Float64 = 0.0
    var _t0_burning_cost = perf_counter_ns()
    for _ in range(N):
        _acc_burning_cost += burning_cost(0.5, 0.5)
    var _t1_burning_cost = perf_counter_ns()
    var _ns_burning_cost = Float64(_t1_burning_cost - _t0_burning_cost) / Float64(N)
    print("MOJO_TIMING insurance::burning_cost", _ns_burning_cost, _acc_burning_cost)
    var _result_burning_cost = burning_cost(0.5, 0.5)
    var _summary_burning_cost = _summary_float64(_result_burning_cost)
    print("MOJO_RESULT insurance::burning_cost", _summary_burning_cost)
    var _acc_credibility_buhlmann: Float64 = 0.0
    var _t0_credibility_buhlmann = perf_counter_ns()
    for _ in range(N):
        _acc_credibility_buhlmann += credibility_buhlmann(0.5, 0.5)
    var _t1_credibility_buhlmann = perf_counter_ns()
    var _ns_credibility_buhlmann = Float64(_t1_credibility_buhlmann - _t0_credibility_buhlmann) / Float64(N)
    print("MOJO_TIMING insurance::credibility_buhlmann", _ns_credibility_buhlmann, _acc_credibility_buhlmann)
    var _result_credibility_buhlmann = credibility_buhlmann(0.5, 0.5)
    var _summary_credibility_buhlmann = _summary_float64(_result_credibility_buhlmann)
    print("MOJO_RESULT insurance::credibility_buhlmann", _summary_credibility_buhlmann)
    var _acc_risk_load: Float64 = 0.0
    var _t0_risk_load = perf_counter_ns()
    for _ in range(N):
        _acc_risk_load += risk_load(0.5, 0.5)
    var _t1_risk_load = perf_counter_ns()
    var _ns_risk_load = Float64(_t1_risk_load - _t0_risk_load) / Float64(N)
    print("MOJO_TIMING insurance::risk_load", _ns_risk_load, _acc_risk_load)
    var _result_risk_load = risk_load(0.5, 0.5)
    var _summary_risk_load = _summary_float64(_result_risk_load)
    print("MOJO_RESULT insurance::risk_load", _summary_risk_load)
    var _acc_aggregate_deductible_savings: Float64 = 0.0
    var _t0_aggregate_deductible_savings = perf_counter_ns()
    for _ in range(N):
        _acc_aggregate_deductible_savings += aggregate_deductible_savings(0.5, 0.5, 0.5)
    var _t1_aggregate_deductible_savings = perf_counter_ns()
    var _ns_aggregate_deductible_savings = Float64(_t1_aggregate_deductible_savings - _t0_aggregate_deductible_savings) / Float64(N)
    print("MOJO_TIMING insurance::aggregate_deductible_savings", _ns_aggregate_deductible_savings, _acc_aggregate_deductible_savings)
    var _result_aggregate_deductible_savings = aggregate_deductible_savings(0.5, 0.5, 0.5)
    var _summary_aggregate_deductible_savings = _summary_float64(_result_aggregate_deductible_savings)
    print("MOJO_RESULT insurance::aggregate_deductible_savings", _summary_aggregate_deductible_savings)
    var _acc_retention_rate: Float64 = 0.0
    var _t0_retention_rate = perf_counter_ns()
    for _ in range(N):
        _acc_retention_rate += retention_rate(0.5, 0.5)
    var _t1_retention_rate = perf_counter_ns()
    var _ns_retention_rate = Float64(_t1_retention_rate - _t0_retention_rate) / Float64(N)
    print("MOJO_TIMING insurance::retention_rate", _ns_retention_rate, _acc_retention_rate)
    var _result_retention_rate = retention_rate(0.5, 0.5)
    var _summary_retention_rate = _summary_float64(_result_retention_rate)
    print("MOJO_RESULT insurance::retention_rate", _summary_retention_rate)
