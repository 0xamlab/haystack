"""bench_lottery.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lottery import combinations, permutations, lottery_odds, expected_value, expected_value_net, house_edge, probability_at_least_one_win, annuity_vs_lump_sum, tax_after_winnings, odds_to_probability, probability_to_odds, jackpot_ev_threshold
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

    var _acc_combinations: Float64 = 0.0
    var _t0_combinations = perf_counter_ns()
    for _ in range(N):
        _acc_combinations += combinations(5, 5)
    var _t1_combinations = perf_counter_ns()
    var _ns_combinations = Float64(_t1_combinations - _t0_combinations) / Float64(N)
    print("MOJO_TIMING lottery::combinations", _ns_combinations, _acc_combinations)
    var _result_combinations = combinations(5, 5)
    var _summary_combinations = _summary_float64(_result_combinations)
    print("MOJO_RESULT lottery::combinations", _summary_combinations)
    var _acc_permutations: Float64 = 0.0
    var _t0_permutations = perf_counter_ns()
    for _ in range(N):
        _acc_permutations += permutations(5, 5)
    var _t1_permutations = perf_counter_ns()
    var _ns_permutations = Float64(_t1_permutations - _t0_permutations) / Float64(N)
    print("MOJO_TIMING lottery::permutations", _ns_permutations, _acc_permutations)
    var _result_permutations = permutations(5, 5)
    var _summary_permutations = _summary_float64(_result_permutations)
    print("MOJO_RESULT lottery::permutations", _summary_permutations)
    var _acc_lottery_odds: Float64 = 0.0
    var _t0_lottery_odds = perf_counter_ns()
    for _ in range(N):
        _acc_lottery_odds += lottery_odds(5, 5, 5)
    var _t1_lottery_odds = perf_counter_ns()
    var _ns_lottery_odds = Float64(_t1_lottery_odds - _t0_lottery_odds) / Float64(N)
    print("MOJO_TIMING lottery::lottery_odds", _ns_lottery_odds, _acc_lottery_odds)
    var _result_lottery_odds = lottery_odds(5, 5, 5)
    var _summary_lottery_odds = _summary_float64(_result_lottery_odds)
    print("MOJO_RESULT lottery::lottery_odds", _summary_lottery_odds)
    var _acc_expected_value: Float64 = 0.0
    var _t0_expected_value = perf_counter_ns()
    for _ in range(N):
        _acc_expected_value += expected_value(0.5, 0.5)
    var _t1_expected_value = perf_counter_ns()
    var _ns_expected_value = Float64(_t1_expected_value - _t0_expected_value) / Float64(N)
    print("MOJO_TIMING lottery::expected_value", _ns_expected_value, _acc_expected_value)
    var _result_expected_value = expected_value(0.5, 0.5)
    var _summary_expected_value = _summary_float64(_result_expected_value)
    print("MOJO_RESULT lottery::expected_value", _summary_expected_value)
    var _acc_expected_value_net: Float64 = 0.0
    var _t0_expected_value_net = perf_counter_ns()
    for _ in range(N):
        _acc_expected_value_net += expected_value_net(0.5, 0.5)
    var _t1_expected_value_net = perf_counter_ns()
    var _ns_expected_value_net = Float64(_t1_expected_value_net - _t0_expected_value_net) / Float64(N)
    print("MOJO_TIMING lottery::expected_value_net", _ns_expected_value_net, _acc_expected_value_net)
    var _result_expected_value_net = expected_value_net(0.5, 0.5)
    var _summary_expected_value_net = _summary_float64(_result_expected_value_net)
    print("MOJO_RESULT lottery::expected_value_net", _summary_expected_value_net)
    var _acc_house_edge: Float64 = 0.0
    var _t0_house_edge = perf_counter_ns()
    for _ in range(N):
        _acc_house_edge += house_edge(0.5, 0.5)
    var _t1_house_edge = perf_counter_ns()
    var _ns_house_edge = Float64(_t1_house_edge - _t0_house_edge) / Float64(N)
    print("MOJO_TIMING lottery::house_edge", _ns_house_edge, _acc_house_edge)
    var _result_house_edge = house_edge(0.5, 0.5)
    var _summary_house_edge = _summary_float64(_result_house_edge)
    print("MOJO_RESULT lottery::house_edge", _summary_house_edge)
    var _acc_probability_at_least_one_win: Float64 = 0.0
    var _t0_probability_at_least_one_win = perf_counter_ns()
    for _ in range(N):
        _acc_probability_at_least_one_win += probability_at_least_one_win(0.5, 5)
    var _t1_probability_at_least_one_win = perf_counter_ns()
    var _ns_probability_at_least_one_win = Float64(_t1_probability_at_least_one_win - _t0_probability_at_least_one_win) / Float64(N)
    print("MOJO_TIMING lottery::probability_at_least_one_win", _ns_probability_at_least_one_win, _acc_probability_at_least_one_win)
    var _result_probability_at_least_one_win = probability_at_least_one_win(0.5, 5)
    var _summary_probability_at_least_one_win = _summary_float64(_result_probability_at_least_one_win)
    print("MOJO_RESULT lottery::probability_at_least_one_win", _summary_probability_at_least_one_win)
    var _acc_annuity_vs_lump_sum: Float64 = 0.0
    var _t0_annuity_vs_lump_sum = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_vs_lump_sum += annuity_vs_lump_sum(0.5, 0.5, 0.5)
    var _t1_annuity_vs_lump_sum = perf_counter_ns()
    var _ns_annuity_vs_lump_sum = Float64(_t1_annuity_vs_lump_sum - _t0_annuity_vs_lump_sum) / Float64(N)
    print("MOJO_TIMING lottery::annuity_vs_lump_sum", _ns_annuity_vs_lump_sum, _acc_annuity_vs_lump_sum)
    var _result_annuity_vs_lump_sum = annuity_vs_lump_sum(0.5, 0.5, 0.5)
    var _summary_annuity_vs_lump_sum = _summary_float64(_result_annuity_vs_lump_sum)
    print("MOJO_RESULT lottery::annuity_vs_lump_sum", _summary_annuity_vs_lump_sum)
    var _acc_tax_after_winnings: Float64 = 0.0
    var _t0_tax_after_winnings = perf_counter_ns()
    for _ in range(N):
        _acc_tax_after_winnings += tax_after_winnings(0.5, 0.5, 0.5)
    var _t1_tax_after_winnings = perf_counter_ns()
    var _ns_tax_after_winnings = Float64(_t1_tax_after_winnings - _t0_tax_after_winnings) / Float64(N)
    print("MOJO_TIMING lottery::tax_after_winnings", _ns_tax_after_winnings, _acc_tax_after_winnings)
    var _result_tax_after_winnings = tax_after_winnings(0.5, 0.5, 0.5)
    var _summary_tax_after_winnings = _summary_float64(_result_tax_after_winnings)
    print("MOJO_RESULT lottery::tax_after_winnings", _summary_tax_after_winnings)
    var _acc_odds_to_probability: Float64 = 0.0
    var _t0_odds_to_probability = perf_counter_ns()
    for _ in range(N):
        _acc_odds_to_probability += odds_to_probability(0.5)
    var _t1_odds_to_probability = perf_counter_ns()
    var _ns_odds_to_probability = Float64(_t1_odds_to_probability - _t0_odds_to_probability) / Float64(N)
    print("MOJO_TIMING lottery::odds_to_probability", _ns_odds_to_probability, _acc_odds_to_probability)
    var _result_odds_to_probability = odds_to_probability(0.5)
    var _summary_odds_to_probability = _summary_float64(_result_odds_to_probability)
    print("MOJO_RESULT lottery::odds_to_probability", _summary_odds_to_probability)
    var _acc_probability_to_odds: Float64 = 0.0
    var _t0_probability_to_odds = perf_counter_ns()
    for _ in range(N):
        _acc_probability_to_odds += probability_to_odds(0.5)
    var _t1_probability_to_odds = perf_counter_ns()
    var _ns_probability_to_odds = Float64(_t1_probability_to_odds - _t0_probability_to_odds) / Float64(N)
    print("MOJO_TIMING lottery::probability_to_odds", _ns_probability_to_odds, _acc_probability_to_odds)
    var _result_probability_to_odds = probability_to_odds(0.5)
    var _summary_probability_to_odds = _summary_float64(_result_probability_to_odds)
    print("MOJO_RESULT lottery::probability_to_odds", _summary_probability_to_odds)
    var _acc_jackpot_ev_threshold: Float64 = 0.0
    var _t0_jackpot_ev_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_jackpot_ev_threshold += jackpot_ev_threshold(0.5, 0.5)
    var _t1_jackpot_ev_threshold = perf_counter_ns()
    var _ns_jackpot_ev_threshold = Float64(_t1_jackpot_ev_threshold - _t0_jackpot_ev_threshold) / Float64(N)
    print("MOJO_TIMING lottery::jackpot_ev_threshold", _ns_jackpot_ev_threshold, _acc_jackpot_ev_threshold)
    var _result_jackpot_ev_threshold = jackpot_ev_threshold(0.5, 0.5)
    var _summary_jackpot_ev_threshold = _summary_float64(_result_jackpot_ev_threshold)
    print("MOJO_RESULT lottery::jackpot_ev_threshold", _summary_jackpot_ev_threshold)
