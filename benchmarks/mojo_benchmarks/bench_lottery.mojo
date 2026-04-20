"""bench_lottery.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lottery import combinations, permutations, lottery_odds, expected_value, expected_value_net, house_edge, probability_at_least_one_win, annuity_vs_lump_sum, tax_after_winnings, odds_to_probability, probability_to_odds, jackpot_ev_threshold
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

    var _acc_combinations: Float64 = 0.0
    var _t0_combinations = perf_counter_ns()
    for _ in range(N):
        _acc_combinations += combinations(5, 5)
    var _t1_combinations = perf_counter_ns()
    var _ns_combinations = Float64(_t1_combinations - _t0_combinations) / Float64(N)
    print("MOJO_TIMING lottery::combinations", _ns_combinations, _acc_combinations)
    var _acc_permutations: Float64 = 0.0
    var _t0_permutations = perf_counter_ns()
    for _ in range(N):
        _acc_permutations += permutations(5, 5)
    var _t1_permutations = perf_counter_ns()
    var _ns_permutations = Float64(_t1_permutations - _t0_permutations) / Float64(N)
    print("MOJO_TIMING lottery::permutations", _ns_permutations, _acc_permutations)
    var _acc_lottery_odds: Float64 = 0.0
    var _t0_lottery_odds = perf_counter_ns()
    for _ in range(N):
        _acc_lottery_odds += lottery_odds(5, 5, 5)
    var _t1_lottery_odds = perf_counter_ns()
    var _ns_lottery_odds = Float64(_t1_lottery_odds - _t0_lottery_odds) / Float64(N)
    print("MOJO_TIMING lottery::lottery_odds", _ns_lottery_odds, _acc_lottery_odds)
    var _acc_expected_value: Float64 = 0.0
    var _t0_expected_value = perf_counter_ns()
    for _ in range(N):
        _acc_expected_value += expected_value(0.5, 0.5)
    var _t1_expected_value = perf_counter_ns()
    var _ns_expected_value = Float64(_t1_expected_value - _t0_expected_value) / Float64(N)
    print("MOJO_TIMING lottery::expected_value", _ns_expected_value, _acc_expected_value)
    var _acc_expected_value_net: Float64 = 0.0
    var _t0_expected_value_net = perf_counter_ns()
    for _ in range(N):
        _acc_expected_value_net += expected_value_net(0.5, 0.5)
    var _t1_expected_value_net = perf_counter_ns()
    var _ns_expected_value_net = Float64(_t1_expected_value_net - _t0_expected_value_net) / Float64(N)
    print("MOJO_TIMING lottery::expected_value_net", _ns_expected_value_net, _acc_expected_value_net)
    var _acc_house_edge: Float64 = 0.0
    var _t0_house_edge = perf_counter_ns()
    for _ in range(N):
        _acc_house_edge += house_edge(0.5, 0.5)
    var _t1_house_edge = perf_counter_ns()
    var _ns_house_edge = Float64(_t1_house_edge - _t0_house_edge) / Float64(N)
    print("MOJO_TIMING lottery::house_edge", _ns_house_edge, _acc_house_edge)
    var _acc_probability_at_least_one_win: Float64 = 0.0
    var _t0_probability_at_least_one_win = perf_counter_ns()
    for _ in range(N):
        _acc_probability_at_least_one_win += probability_at_least_one_win(0.5, 5)
    var _t1_probability_at_least_one_win = perf_counter_ns()
    var _ns_probability_at_least_one_win = Float64(_t1_probability_at_least_one_win - _t0_probability_at_least_one_win) / Float64(N)
    print("MOJO_TIMING lottery::probability_at_least_one_win", _ns_probability_at_least_one_win, _acc_probability_at_least_one_win)
    var _acc_annuity_vs_lump_sum: Float64 = 0.0
    var _t0_annuity_vs_lump_sum = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_vs_lump_sum += annuity_vs_lump_sum(0.5, 0.5, 0.5)
    var _t1_annuity_vs_lump_sum = perf_counter_ns()
    var _ns_annuity_vs_lump_sum = Float64(_t1_annuity_vs_lump_sum - _t0_annuity_vs_lump_sum) / Float64(N)
    print("MOJO_TIMING lottery::annuity_vs_lump_sum", _ns_annuity_vs_lump_sum, _acc_annuity_vs_lump_sum)
    var _acc_tax_after_winnings: Float64 = 0.0
    var _t0_tax_after_winnings = perf_counter_ns()
    for _ in range(N):
        _acc_tax_after_winnings += tax_after_winnings(0.5, 0.5, 0.5)
    var _t1_tax_after_winnings = perf_counter_ns()
    var _ns_tax_after_winnings = Float64(_t1_tax_after_winnings - _t0_tax_after_winnings) / Float64(N)
    print("MOJO_TIMING lottery::tax_after_winnings", _ns_tax_after_winnings, _acc_tax_after_winnings)
    var _acc_odds_to_probability: Float64 = 0.0
    var _t0_odds_to_probability = perf_counter_ns()
    for _ in range(N):
        _acc_odds_to_probability += odds_to_probability(0.5)
    var _t1_odds_to_probability = perf_counter_ns()
    var _ns_odds_to_probability = Float64(_t1_odds_to_probability - _t0_odds_to_probability) / Float64(N)
    print("MOJO_TIMING lottery::odds_to_probability", _ns_odds_to_probability, _acc_odds_to_probability)
    var _acc_probability_to_odds: Float64 = 0.0
    var _t0_probability_to_odds = perf_counter_ns()
    for _ in range(N):
        _acc_probability_to_odds += probability_to_odds(0.5)
    var _t1_probability_to_odds = perf_counter_ns()
    var _ns_probability_to_odds = Float64(_t1_probability_to_odds - _t0_probability_to_odds) / Float64(N)
    print("MOJO_TIMING lottery::probability_to_odds", _ns_probability_to_odds, _acc_probability_to_odds)
    var _acc_jackpot_ev_threshold: Float64 = 0.0
    var _t0_jackpot_ev_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_jackpot_ev_threshold += jackpot_ev_threshold(0.5, 0.5)
    var _t1_jackpot_ev_threshold = perf_counter_ns()
    var _ns_jackpot_ev_threshold = Float64(_t1_jackpot_ev_threshold - _t0_jackpot_ev_threshold) / Float64(N)
    print("MOJO_TIMING lottery::jackpot_ev_threshold", _ns_jackpot_ev_threshold, _acc_jackpot_ev_threshold)
