"""bench_real_estate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from real_estate import cap_rate, gross_rent_multiplier, cash_on_cash_return, debt_service_coverage, loan_to_value, net_operating_income, mortgage_payment, price_per_sqft, break_even_ratio, internal_rate_of_return_approx, equity_buildup, appreciation_value
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

    var _acc_cap_rate: Float64 = 0.0
    var _t0_cap_rate = perf_counter_ns()
    for _ in range(N):
        _acc_cap_rate += cap_rate(0.5, 0.5)
    var _t1_cap_rate = perf_counter_ns()
    var _ns_cap_rate = Float64(_t1_cap_rate - _t0_cap_rate) / Float64(N)
    print("MOJO_TIMING real_estate::cap_rate", _ns_cap_rate, _acc_cap_rate)
    var _result_cap_rate = cap_rate(0.5, 0.5)
    var _summary_cap_rate = _summary_float64(_result_cap_rate)
    print("MOJO_RESULT real_estate::cap_rate", _summary_cap_rate)
    var _acc_gross_rent_multiplier: Float64 = 0.0
    var _t0_gross_rent_multiplier = perf_counter_ns()
    for _ in range(N):
        _acc_gross_rent_multiplier += gross_rent_multiplier(0.5, 0.5)
    var _t1_gross_rent_multiplier = perf_counter_ns()
    var _ns_gross_rent_multiplier = Float64(_t1_gross_rent_multiplier - _t0_gross_rent_multiplier) / Float64(N)
    print("MOJO_TIMING real_estate::gross_rent_multiplier", _ns_gross_rent_multiplier, _acc_gross_rent_multiplier)
    var _result_gross_rent_multiplier = gross_rent_multiplier(0.5, 0.5)
    var _summary_gross_rent_multiplier = _summary_float64(_result_gross_rent_multiplier)
    print("MOJO_RESULT real_estate::gross_rent_multiplier", _summary_gross_rent_multiplier)
    var _acc_cash_on_cash_return: Float64 = 0.0
    var _t0_cash_on_cash_return = perf_counter_ns()
    for _ in range(N):
        _acc_cash_on_cash_return += cash_on_cash_return(0.5, 0.5)
    var _t1_cash_on_cash_return = perf_counter_ns()
    var _ns_cash_on_cash_return = Float64(_t1_cash_on_cash_return - _t0_cash_on_cash_return) / Float64(N)
    print("MOJO_TIMING real_estate::cash_on_cash_return", _ns_cash_on_cash_return, _acc_cash_on_cash_return)
    var _result_cash_on_cash_return = cash_on_cash_return(0.5, 0.5)
    var _summary_cash_on_cash_return = _summary_float64(_result_cash_on_cash_return)
    print("MOJO_RESULT real_estate::cash_on_cash_return", _summary_cash_on_cash_return)
    var _acc_debt_service_coverage: Float64 = 0.0
    var _t0_debt_service_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_debt_service_coverage += debt_service_coverage(0.5, 0.5)
    var _t1_debt_service_coverage = perf_counter_ns()
    var _ns_debt_service_coverage = Float64(_t1_debt_service_coverage - _t0_debt_service_coverage) / Float64(N)
    print("MOJO_TIMING real_estate::debt_service_coverage", _ns_debt_service_coverage, _acc_debt_service_coverage)
    var _result_debt_service_coverage = debt_service_coverage(0.5, 0.5)
    var _summary_debt_service_coverage = _summary_float64(_result_debt_service_coverage)
    print("MOJO_RESULT real_estate::debt_service_coverage", _summary_debt_service_coverage)
    var _acc_loan_to_value: Float64 = 0.0
    var _t0_loan_to_value = perf_counter_ns()
    for _ in range(N):
        _acc_loan_to_value += loan_to_value(0.5, 0.5)
    var _t1_loan_to_value = perf_counter_ns()
    var _ns_loan_to_value = Float64(_t1_loan_to_value - _t0_loan_to_value) / Float64(N)
    print("MOJO_TIMING real_estate::loan_to_value", _ns_loan_to_value, _acc_loan_to_value)
    var _result_loan_to_value = loan_to_value(0.5, 0.5)
    var _summary_loan_to_value = _summary_float64(_result_loan_to_value)
    print("MOJO_RESULT real_estate::loan_to_value", _summary_loan_to_value)
    var _acc_net_operating_income: Float64 = 0.0
    var _t0_net_operating_income = perf_counter_ns()
    for _ in range(N):
        _acc_net_operating_income += net_operating_income(0.5, 0.5, 0.5)
    var _t1_net_operating_income = perf_counter_ns()
    var _ns_net_operating_income = Float64(_t1_net_operating_income - _t0_net_operating_income) / Float64(N)
    print("MOJO_TIMING real_estate::net_operating_income", _ns_net_operating_income, _acc_net_operating_income)
    var _result_net_operating_income = net_operating_income(0.5, 0.5, 0.5)
    var _summary_net_operating_income = _summary_float64(_result_net_operating_income)
    print("MOJO_RESULT real_estate::net_operating_income", _summary_net_operating_income)
    var _acc_mortgage_payment: Float64 = 0.0
    var _t0_mortgage_payment = perf_counter_ns()
    for _ in range(N):
        _acc_mortgage_payment += mortgage_payment(0.5, 0.5, 5)
    var _t1_mortgage_payment = perf_counter_ns()
    var _ns_mortgage_payment = Float64(_t1_mortgage_payment - _t0_mortgage_payment) / Float64(N)
    print("MOJO_TIMING real_estate::mortgage_payment", _ns_mortgage_payment, _acc_mortgage_payment)
    var _result_mortgage_payment = mortgage_payment(0.5, 0.5, 5)
    var _summary_mortgage_payment = _summary_float64(_result_mortgage_payment)
    print("MOJO_RESULT real_estate::mortgage_payment", _summary_mortgage_payment)
    var _acc_price_per_sqft: Float64 = 0.0
    var _t0_price_per_sqft = perf_counter_ns()
    for _ in range(N):
        _acc_price_per_sqft += price_per_sqft(0.5, 0.5)
    var _t1_price_per_sqft = perf_counter_ns()
    var _ns_price_per_sqft = Float64(_t1_price_per_sqft - _t0_price_per_sqft) / Float64(N)
    print("MOJO_TIMING real_estate::price_per_sqft", _ns_price_per_sqft, _acc_price_per_sqft)
    var _result_price_per_sqft = price_per_sqft(0.5, 0.5)
    var _summary_price_per_sqft = _summary_float64(_result_price_per_sqft)
    print("MOJO_RESULT real_estate::price_per_sqft", _summary_price_per_sqft)
    var _acc_break_even_ratio: Float64 = 0.0
    var _t0_break_even_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_break_even_ratio += break_even_ratio(0.5, 0.5, 0.5)
    var _t1_break_even_ratio = perf_counter_ns()
    var _ns_break_even_ratio = Float64(_t1_break_even_ratio - _t0_break_even_ratio) / Float64(N)
    print("MOJO_TIMING real_estate::break_even_ratio", _ns_break_even_ratio, _acc_break_even_ratio)
    var _result_break_even_ratio = break_even_ratio(0.5, 0.5, 0.5)
    var _summary_break_even_ratio = _summary_float64(_result_break_even_ratio)
    print("MOJO_RESULT real_estate::break_even_ratio", _summary_break_even_ratio)
    var _acc_internal_rate_of_return_approx: Float64 = 0.0
    var _t0_internal_rate_of_return_approx = perf_counter_ns()
    for _ in range(N):
        _acc_internal_rate_of_return_approx += internal_rate_of_return_approx(0.5, 0.5, 5)
    var _t1_internal_rate_of_return_approx = perf_counter_ns()
    var _ns_internal_rate_of_return_approx = Float64(_t1_internal_rate_of_return_approx - _t0_internal_rate_of_return_approx) / Float64(N)
    print("MOJO_TIMING real_estate::internal_rate_of_return_approx", _ns_internal_rate_of_return_approx, _acc_internal_rate_of_return_approx)
    var _result_internal_rate_of_return_approx = internal_rate_of_return_approx(0.5, 0.5, 5)
    var _summary_internal_rate_of_return_approx = _summary_float64(_result_internal_rate_of_return_approx)
    print("MOJO_RESULT real_estate::internal_rate_of_return_approx", _summary_internal_rate_of_return_approx)
    var _acc_equity_buildup: Float64 = 0.0
    var _t0_equity_buildup = perf_counter_ns()
    for _ in range(N):
        _acc_equity_buildup += equity_buildup(0.5, 0.5)
    var _t1_equity_buildup = perf_counter_ns()
    var _ns_equity_buildup = Float64(_t1_equity_buildup - _t0_equity_buildup) / Float64(N)
    print("MOJO_TIMING real_estate::equity_buildup", _ns_equity_buildup, _acc_equity_buildup)
    var _result_equity_buildup = equity_buildup(0.5, 0.5)
    var _summary_equity_buildup = _summary_float64(_result_equity_buildup)
    print("MOJO_RESULT real_estate::equity_buildup", _summary_equity_buildup)
    var _acc_appreciation_value: Float64 = 0.0
    var _t0_appreciation_value = perf_counter_ns()
    for _ in range(N):
        _acc_appreciation_value += appreciation_value(0.5, 0.5, 5)
    var _t1_appreciation_value = perf_counter_ns()
    var _ns_appreciation_value = Float64(_t1_appreciation_value - _t0_appreciation_value) / Float64(N)
    print("MOJO_TIMING real_estate::appreciation_value", _ns_appreciation_value, _acc_appreciation_value)
    var _result_appreciation_value = appreciation_value(0.5, 0.5, 5)
    var _summary_appreciation_value = _summary_float64(_result_appreciation_value)
    print("MOJO_RESULT real_estate::appreciation_value", _summary_appreciation_value)
