"""bench_finance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from finance import npv, irr, payback_period, roi, compound_interest, present_value, future_value, annuity_payment, sharpe_ratio, max_drawdown, cagr, wacc
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

    var _acc_npv: Float64 = 0.0
    var _t0_npv = perf_counter_ns()
    for _ in range(N):
        _acc_npv += npv(0.5, _lf5)
    var _t1_npv = perf_counter_ns()
    var _ns_npv = Float64(_t1_npv - _t0_npv) / Float64(N)
    print("MOJO_TIMING finance::npv", _ns_npv, _acc_npv)
    var _result_npv = npv(0.5, _lf5)
    var _summary_npv = _summary_float64(_result_npv)
    print("MOJO_RESULT finance::npv", _summary_npv)
    var _acc_irr: Float64 = 0.0
    var _t0_irr = perf_counter_ns()
    for _ in range(N):
        _acc_irr += irr(_lf5, 0.5, 0.5, 5)
    var _t1_irr = perf_counter_ns()
    var _ns_irr = Float64(_t1_irr - _t0_irr) / Float64(N)
    print("MOJO_TIMING finance::irr", _ns_irr, _acc_irr)
    var _result_irr = irr(_lf5, 0.5, 0.5, 5)
    var _summary_irr = _summary_float64(_result_irr)
    print("MOJO_RESULT finance::irr", _summary_irr)
    var _acc_payback_period: Float64 = 0.0
    var _t0_payback_period = perf_counter_ns()
    for _ in range(N):
        _acc_payback_period += payback_period(_lf5)
    var _t1_payback_period = perf_counter_ns()
    var _ns_payback_period = Float64(_t1_payback_period - _t0_payback_period) / Float64(N)
    print("MOJO_TIMING finance::payback_period", _ns_payback_period, _acc_payback_period)
    var _result_payback_period = payback_period(_lf5)
    var _summary_payback_period = _summary_float64(_result_payback_period)
    print("MOJO_RESULT finance::payback_period", _summary_payback_period)
    var _acc_roi: Float64 = 0.0
    var _t0_roi = perf_counter_ns()
    for _ in range(N):
        _acc_roi += roi(0.5, 0.5)
    var _t1_roi = perf_counter_ns()
    var _ns_roi = Float64(_t1_roi - _t0_roi) / Float64(N)
    print("MOJO_TIMING finance::roi", _ns_roi, _acc_roi)
    var _result_roi = roi(0.5, 0.5)
    var _summary_roi = _summary_float64(_result_roi)
    print("MOJO_RESULT finance::roi", _summary_roi)
    var _acc_compound_interest: Float64 = 0.0
    var _t0_compound_interest = perf_counter_ns()
    for _ in range(N):
        _acc_compound_interest += compound_interest(0.5, 0.5, 5)
    var _t1_compound_interest = perf_counter_ns()
    var _ns_compound_interest = Float64(_t1_compound_interest - _t0_compound_interest) / Float64(N)
    print("MOJO_TIMING finance::compound_interest", _ns_compound_interest, _acc_compound_interest)
    var _result_compound_interest = compound_interest(0.5, 0.5, 5)
    var _summary_compound_interest = _summary_float64(_result_compound_interest)
    print("MOJO_RESULT finance::compound_interest", _summary_compound_interest)
    var _acc_present_value: Float64 = 0.0
    var _t0_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_present_value += present_value(0.5, 0.5, 5)
    var _t1_present_value = perf_counter_ns()
    var _ns_present_value = Float64(_t1_present_value - _t0_present_value) / Float64(N)
    print("MOJO_TIMING finance::present_value", _ns_present_value, _acc_present_value)
    var _result_present_value = present_value(0.5, 0.5, 5)
    var _summary_present_value = _summary_float64(_result_present_value)
    print("MOJO_RESULT finance::present_value", _summary_present_value)
    var _acc_future_value: Float64 = 0.0
    var _t0_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_future_value += future_value(0.5, 0.5, 5)
    var _t1_future_value = perf_counter_ns()
    var _ns_future_value = Float64(_t1_future_value - _t0_future_value) / Float64(N)
    print("MOJO_TIMING finance::future_value", _ns_future_value, _acc_future_value)
    var _result_future_value = future_value(0.5, 0.5, 5)
    var _summary_future_value = _summary_float64(_result_future_value)
    print("MOJO_RESULT finance::future_value", _summary_future_value)
    var _acc_annuity_payment: Float64 = 0.0
    var _t0_annuity_payment = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_payment += annuity_payment(0.5, 0.5, 5)
    var _t1_annuity_payment = perf_counter_ns()
    var _ns_annuity_payment = Float64(_t1_annuity_payment - _t0_annuity_payment) / Float64(N)
    print("MOJO_TIMING finance::annuity_payment", _ns_annuity_payment, _acc_annuity_payment)
    var _result_annuity_payment = annuity_payment(0.5, 0.5, 5)
    var _summary_annuity_payment = _summary_float64(_result_annuity_payment)
    print("MOJO_RESULT finance::annuity_payment", _summary_annuity_payment)
    var _acc_sharpe_ratio: Float64 = 0.0
    var _t0_sharpe_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sharpe_ratio += sharpe_ratio(_lf5, 0.5)
    var _t1_sharpe_ratio = perf_counter_ns()
    var _ns_sharpe_ratio = Float64(_t1_sharpe_ratio - _t0_sharpe_ratio) / Float64(N)
    print("MOJO_TIMING finance::sharpe_ratio", _ns_sharpe_ratio, _acc_sharpe_ratio)
    var _result_sharpe_ratio = sharpe_ratio(_lf5, 0.5)
    var _summary_sharpe_ratio = _summary_float64(_result_sharpe_ratio)
    print("MOJO_RESULT finance::sharpe_ratio", _summary_sharpe_ratio)
    var _acc_max_drawdown: Float64 = 0.0
    var _t0_max_drawdown = perf_counter_ns()
    for _ in range(N):
        _acc_max_drawdown += max_drawdown(_lf5)
    var _t1_max_drawdown = perf_counter_ns()
    var _ns_max_drawdown = Float64(_t1_max_drawdown - _t0_max_drawdown) / Float64(N)
    print("MOJO_TIMING finance::max_drawdown", _ns_max_drawdown, _acc_max_drawdown)
    var _result_max_drawdown = max_drawdown(_lf5)
    var _summary_max_drawdown = _summary_float64(_result_max_drawdown)
    print("MOJO_RESULT finance::max_drawdown", _summary_max_drawdown)
    var _acc_cagr: Float64 = 0.0
    var _t0_cagr = perf_counter_ns()
    for _ in range(N):
        _acc_cagr += cagr(0.5, 0.5, 0.5)
    var _t1_cagr = perf_counter_ns()
    var _ns_cagr = Float64(_t1_cagr - _t0_cagr) / Float64(N)
    print("MOJO_TIMING finance::cagr", _ns_cagr, _acc_cagr)
    var _result_cagr = cagr(0.5, 0.5, 0.5)
    var _summary_cagr = _summary_float64(_result_cagr)
    print("MOJO_RESULT finance::cagr", _summary_cagr)
    var _acc_wacc: Float64 = 0.0
    var _t0_wacc = perf_counter_ns()
    for _ in range(N):
        _acc_wacc += wacc(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_wacc = perf_counter_ns()
    var _ns_wacc = Float64(_t1_wacc - _t0_wacc) / Float64(N)
    print("MOJO_TIMING finance::wacc", _ns_wacc, _acc_wacc)
    var _result_wacc = wacc(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_wacc = _summary_float64(_result_wacc)
    print("MOJO_RESULT finance::wacc", _summary_wacc)
