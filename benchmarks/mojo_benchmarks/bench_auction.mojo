"""bench_auction.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from auction import first_price_sealed, second_price_sealed, english_auction_revenue, dutch_auction_revenue, all_pay_revenue, revenue_equivalence_check, vcg_payment, reserve_price_filter, bid_shading_optimal, expected_revenue_uniform, winners_curse_adjustment
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

    var _acc_first_price_sealed: Float64 = 0.0
    var _t0_first_price_sealed = perf_counter_ns()
    for _ in range(N):
        var _r_first_price_sealed = first_price_sealed(_lf5, 5)
        _acc_first_price_sealed += Float64(len(_r_first_price_sealed))
    var _t1_first_price_sealed = perf_counter_ns()
    var _ns_first_price_sealed = Float64(_t1_first_price_sealed - _t0_first_price_sealed) / Float64(N)
    print("MOJO_TIMING auction::first_price_sealed", _ns_first_price_sealed, _acc_first_price_sealed)
    var _result_first_price_sealed = first_price_sealed(_lf5, 5)
    var _summary_first_price_sealed = _summary_list_float64(_result_first_price_sealed)
    print("MOJO_RESULT auction::first_price_sealed", _summary_first_price_sealed)
    var _acc_second_price_sealed: Float64 = 0.0
    var _t0_second_price_sealed = perf_counter_ns()
    for _ in range(N):
        var _r_second_price_sealed = second_price_sealed(_lf5, 5)
        _acc_second_price_sealed += Float64(len(_r_second_price_sealed))
    var _t1_second_price_sealed = perf_counter_ns()
    var _ns_second_price_sealed = Float64(_t1_second_price_sealed - _t0_second_price_sealed) / Float64(N)
    print("MOJO_TIMING auction::second_price_sealed", _ns_second_price_sealed, _acc_second_price_sealed)
    var _result_second_price_sealed = second_price_sealed(_lf5, 5)
    var _summary_second_price_sealed = _summary_list_float64(_result_second_price_sealed)
    print("MOJO_RESULT auction::second_price_sealed", _summary_second_price_sealed)
    var _acc_english_auction_revenue: Float64 = 0.0
    var _t0_english_auction_revenue = perf_counter_ns()
    for _ in range(N):
        _acc_english_auction_revenue += english_auction_revenue(_lf5, 5)
    var _t1_english_auction_revenue = perf_counter_ns()
    var _ns_english_auction_revenue = Float64(_t1_english_auction_revenue - _t0_english_auction_revenue) / Float64(N)
    print("MOJO_TIMING auction::english_auction_revenue", _ns_english_auction_revenue, _acc_english_auction_revenue)
    var _result_english_auction_revenue = english_auction_revenue(_lf5, 5)
    var _summary_english_auction_revenue = _summary_float64(_result_english_auction_revenue)
    print("MOJO_RESULT auction::english_auction_revenue", _summary_english_auction_revenue)
    var _acc_dutch_auction_revenue: Float64 = 0.0
    var _t0_dutch_auction_revenue = perf_counter_ns()
    for _ in range(N):
        _acc_dutch_auction_revenue += dutch_auction_revenue(_lf5, 5)
    var _t1_dutch_auction_revenue = perf_counter_ns()
    var _ns_dutch_auction_revenue = Float64(_t1_dutch_auction_revenue - _t0_dutch_auction_revenue) / Float64(N)
    print("MOJO_TIMING auction::dutch_auction_revenue", _ns_dutch_auction_revenue, _acc_dutch_auction_revenue)
    var _result_dutch_auction_revenue = dutch_auction_revenue(_lf5, 5)
    var _summary_dutch_auction_revenue = _summary_float64(_result_dutch_auction_revenue)
    print("MOJO_RESULT auction::dutch_auction_revenue", _summary_dutch_auction_revenue)
    var _acc_all_pay_revenue: Float64 = 0.0
    var _t0_all_pay_revenue = perf_counter_ns()
    for _ in range(N):
        _acc_all_pay_revenue += all_pay_revenue(_lf5, 5)
    var _t1_all_pay_revenue = perf_counter_ns()
    var _ns_all_pay_revenue = Float64(_t1_all_pay_revenue - _t0_all_pay_revenue) / Float64(N)
    print("MOJO_TIMING auction::all_pay_revenue", _ns_all_pay_revenue, _acc_all_pay_revenue)
    var _result_all_pay_revenue = all_pay_revenue(_lf5, 5)
    var _summary_all_pay_revenue = _summary_float64(_result_all_pay_revenue)
    print("MOJO_RESULT auction::all_pay_revenue", _summary_all_pay_revenue)
    var _acc_revenue_equivalence_check: Float64 = 0.0
    var _t0_revenue_equivalence_check = perf_counter_ns()
    for _ in range(N):
        _acc_revenue_equivalence_check += Float64(revenue_equivalence_check(_lf5, 5))
    var _t1_revenue_equivalence_check = perf_counter_ns()
    var _ns_revenue_equivalence_check = Float64(_t1_revenue_equivalence_check - _t0_revenue_equivalence_check) / Float64(N)
    print("MOJO_TIMING auction::revenue_equivalence_check", _ns_revenue_equivalence_check, _acc_revenue_equivalence_check)
    var _result_revenue_equivalence_check = revenue_equivalence_check(_lf5, 5)
    var _summary_revenue_equivalence_check = _summary_bool(_result_revenue_equivalence_check)
    print("MOJO_RESULT auction::revenue_equivalence_check", _summary_revenue_equivalence_check)
    var _acc_vcg_payment: Float64 = 0.0
    var _t0_vcg_payment = perf_counter_ns()
    for _ in range(N):
        _acc_vcg_payment += vcg_payment(_lf5, 5, 5)
    var _t1_vcg_payment = perf_counter_ns()
    var _ns_vcg_payment = Float64(_t1_vcg_payment - _t0_vcg_payment) / Float64(N)
    print("MOJO_TIMING auction::vcg_payment", _ns_vcg_payment, _acc_vcg_payment)
    var _result_vcg_payment = vcg_payment(_lf5, 5, 5)
    var _summary_vcg_payment = _summary_float64(_result_vcg_payment)
    print("MOJO_RESULT auction::vcg_payment", _summary_vcg_payment)
    var _acc_reserve_price_filter: Float64 = 0.0
    var _t0_reserve_price_filter = perf_counter_ns()
    for _ in range(N):
        var _r_reserve_price_filter = reserve_price_filter(_lf5, 5, 0.5)
        _acc_reserve_price_filter += Float64(len(_r_reserve_price_filter))
    var _t1_reserve_price_filter = perf_counter_ns()
    var _ns_reserve_price_filter = Float64(_t1_reserve_price_filter - _t0_reserve_price_filter) / Float64(N)
    print("MOJO_TIMING auction::reserve_price_filter", _ns_reserve_price_filter, _acc_reserve_price_filter)
    var _result_reserve_price_filter = reserve_price_filter(_lf5, 5, 0.5)
    var _summary_reserve_price_filter = _summary_list_float64(_result_reserve_price_filter)
    print("MOJO_RESULT auction::reserve_price_filter", _summary_reserve_price_filter)
    var _acc_bid_shading_optimal: Float64 = 0.0
    var _t0_bid_shading_optimal = perf_counter_ns()
    for _ in range(N):
        _acc_bid_shading_optimal += bid_shading_optimal(0.5, 5)
    var _t1_bid_shading_optimal = perf_counter_ns()
    var _ns_bid_shading_optimal = Float64(_t1_bid_shading_optimal - _t0_bid_shading_optimal) / Float64(N)
    print("MOJO_TIMING auction::bid_shading_optimal", _ns_bid_shading_optimal, _acc_bid_shading_optimal)
    var _result_bid_shading_optimal = bid_shading_optimal(0.5, 5)
    var _summary_bid_shading_optimal = _summary_float64(_result_bid_shading_optimal)
    print("MOJO_RESULT auction::bid_shading_optimal", _summary_bid_shading_optimal)
    var _acc_expected_revenue_uniform: Float64 = 0.0
    var _t0_expected_revenue_uniform = perf_counter_ns()
    for _ in range(N):
        _acc_expected_revenue_uniform += expected_revenue_uniform(5, 0.5)
    var _t1_expected_revenue_uniform = perf_counter_ns()
    var _ns_expected_revenue_uniform = Float64(_t1_expected_revenue_uniform - _t0_expected_revenue_uniform) / Float64(N)
    print("MOJO_TIMING auction::expected_revenue_uniform", _ns_expected_revenue_uniform, _acc_expected_revenue_uniform)
    var _result_expected_revenue_uniform = expected_revenue_uniform(5, 0.5)
    var _summary_expected_revenue_uniform = _summary_float64(_result_expected_revenue_uniform)
    print("MOJO_RESULT auction::expected_revenue_uniform", _summary_expected_revenue_uniform)
    var _acc_winners_curse_adjustment: Float64 = 0.0
    var _t0_winners_curse_adjustment = perf_counter_ns()
    for _ in range(N):
        _acc_winners_curse_adjustment += winners_curse_adjustment(0.5, 5)
    var _t1_winners_curse_adjustment = perf_counter_ns()
    var _ns_winners_curse_adjustment = Float64(_t1_winners_curse_adjustment - _t0_winners_curse_adjustment) / Float64(N)
    print("MOJO_TIMING auction::winners_curse_adjustment", _ns_winners_curse_adjustment, _acc_winners_curse_adjustment)
    var _result_winners_curse_adjustment = winners_curse_adjustment(0.5, 5)
    var _summary_winners_curse_adjustment = _summary_float64(_result_winners_curse_adjustment)
    print("MOJO_RESULT auction::winners_curse_adjustment", _summary_winners_curse_adjustment)
