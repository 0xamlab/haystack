"""bench_sports_analytics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sports_analytics import batting_average, on_base_percentage, slugging_percentage, ops, era, whip, passer_rating_nfl, pythagorean_wins, elo_expected_score, elo_new_rating, true_shooting_percentage, player_efficiency_rating_approx
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

    var _acc_batting_average: Float64 = 0.0
    var _t0_batting_average = perf_counter_ns()
    for _ in range(N):
        _acc_batting_average += batting_average(0.5, 0.5)
    var _t1_batting_average = perf_counter_ns()
    var _ns_batting_average = Float64(_t1_batting_average - _t0_batting_average) / Float64(N)
    print("MOJO_TIMING sports_analytics::batting_average", _ns_batting_average, _acc_batting_average)
    var _result_batting_average = batting_average(0.5, 0.5)
    var _summary_batting_average = _summary_float64(_result_batting_average)
    print("MOJO_RESULT sports_analytics::batting_average", _summary_batting_average)
    var _acc_on_base_percentage: Float64 = 0.0
    var _t0_on_base_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_on_base_percentage += on_base_percentage(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_on_base_percentage = perf_counter_ns()
    var _ns_on_base_percentage = Float64(_t1_on_base_percentage - _t0_on_base_percentage) / Float64(N)
    print("MOJO_TIMING sports_analytics::on_base_percentage", _ns_on_base_percentage, _acc_on_base_percentage)
    var _result_on_base_percentage = on_base_percentage(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_on_base_percentage = _summary_float64(_result_on_base_percentage)
    print("MOJO_RESULT sports_analytics::on_base_percentage", _summary_on_base_percentage)
    var _acc_slugging_percentage: Float64 = 0.0
    var _t0_slugging_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_slugging_percentage += slugging_percentage(0.5, 0.5)
    var _t1_slugging_percentage = perf_counter_ns()
    var _ns_slugging_percentage = Float64(_t1_slugging_percentage - _t0_slugging_percentage) / Float64(N)
    print("MOJO_TIMING sports_analytics::slugging_percentage", _ns_slugging_percentage, _acc_slugging_percentage)
    var _result_slugging_percentage = slugging_percentage(0.5, 0.5)
    var _summary_slugging_percentage = _summary_float64(_result_slugging_percentage)
    print("MOJO_RESULT sports_analytics::slugging_percentage", _summary_slugging_percentage)
    var _acc_ops: Float64 = 0.0
    var _t0_ops = perf_counter_ns()
    for _ in range(N):
        _acc_ops += ops(0.5, 0.5)
    var _t1_ops = perf_counter_ns()
    var _ns_ops = Float64(_t1_ops - _t0_ops) / Float64(N)
    print("MOJO_TIMING sports_analytics::ops", _ns_ops, _acc_ops)
    var _result_ops = ops(0.5, 0.5)
    var _summary_ops = _summary_float64(_result_ops)
    print("MOJO_RESULT sports_analytics::ops", _summary_ops)
    var _acc_era: Float64 = 0.0
    var _t0_era = perf_counter_ns()
    for _ in range(N):
        _acc_era += era(0.5, 0.5)
    var _t1_era = perf_counter_ns()
    var _ns_era = Float64(_t1_era - _t0_era) / Float64(N)
    print("MOJO_TIMING sports_analytics::era", _ns_era, _acc_era)
    var _result_era = era(0.5, 0.5)
    var _summary_era = _summary_float64(_result_era)
    print("MOJO_RESULT sports_analytics::era", _summary_era)
    var _acc_whip: Float64 = 0.0
    var _t0_whip = perf_counter_ns()
    for _ in range(N):
        _acc_whip += whip(0.5, 0.5, 0.5)
    var _t1_whip = perf_counter_ns()
    var _ns_whip = Float64(_t1_whip - _t0_whip) / Float64(N)
    print("MOJO_TIMING sports_analytics::whip", _ns_whip, _acc_whip)
    var _result_whip = whip(0.5, 0.5, 0.5)
    var _summary_whip = _summary_float64(_result_whip)
    print("MOJO_RESULT sports_analytics::whip", _summary_whip)
    var _acc_passer_rating_nfl: Float64 = 0.0
    var _t0_passer_rating_nfl = perf_counter_ns()
    for _ in range(N):
        _acc_passer_rating_nfl += passer_rating_nfl(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_passer_rating_nfl = perf_counter_ns()
    var _ns_passer_rating_nfl = Float64(_t1_passer_rating_nfl - _t0_passer_rating_nfl) / Float64(N)
    print("MOJO_TIMING sports_analytics::passer_rating_nfl", _ns_passer_rating_nfl, _acc_passer_rating_nfl)
    var _result_passer_rating_nfl = passer_rating_nfl(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_passer_rating_nfl = _summary_float64(_result_passer_rating_nfl)
    print("MOJO_RESULT sports_analytics::passer_rating_nfl", _summary_passer_rating_nfl)
    var _acc_pythagorean_wins: Float64 = 0.0
    var _t0_pythagorean_wins = perf_counter_ns()
    for _ in range(N):
        _acc_pythagorean_wins += pythagorean_wins(0.5, 0.5, 0.5)
    var _t1_pythagorean_wins = perf_counter_ns()
    var _ns_pythagorean_wins = Float64(_t1_pythagorean_wins - _t0_pythagorean_wins) / Float64(N)
    print("MOJO_TIMING sports_analytics::pythagorean_wins", _ns_pythagorean_wins, _acc_pythagorean_wins)
    var _result_pythagorean_wins = pythagorean_wins(0.5, 0.5, 0.5)
    var _summary_pythagorean_wins = _summary_float64(_result_pythagorean_wins)
    print("MOJO_RESULT sports_analytics::pythagorean_wins", _summary_pythagorean_wins)
    var _acc_elo_expected_score: Float64 = 0.0
    var _t0_elo_expected_score = perf_counter_ns()
    for _ in range(N):
        _acc_elo_expected_score += elo_expected_score(0.5, 0.5)
    var _t1_elo_expected_score = perf_counter_ns()
    var _ns_elo_expected_score = Float64(_t1_elo_expected_score - _t0_elo_expected_score) / Float64(N)
    print("MOJO_TIMING sports_analytics::elo_expected_score", _ns_elo_expected_score, _acc_elo_expected_score)
    var _result_elo_expected_score = elo_expected_score(0.5, 0.5)
    var _summary_elo_expected_score = _summary_float64(_result_elo_expected_score)
    print("MOJO_RESULT sports_analytics::elo_expected_score", _summary_elo_expected_score)
    var _acc_elo_new_rating: Float64 = 0.0
    var _t0_elo_new_rating = perf_counter_ns()
    for _ in range(N):
        _acc_elo_new_rating += elo_new_rating(0.5, 0.5, 0.5, 0.5)
    var _t1_elo_new_rating = perf_counter_ns()
    var _ns_elo_new_rating = Float64(_t1_elo_new_rating - _t0_elo_new_rating) / Float64(N)
    print("MOJO_TIMING sports_analytics::elo_new_rating", _ns_elo_new_rating, _acc_elo_new_rating)
    var _result_elo_new_rating = elo_new_rating(0.5, 0.5, 0.5, 0.5)
    var _summary_elo_new_rating = _summary_float64(_result_elo_new_rating)
    print("MOJO_RESULT sports_analytics::elo_new_rating", _summary_elo_new_rating)
    var _acc_true_shooting_percentage: Float64 = 0.0
    var _t0_true_shooting_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_true_shooting_percentage += true_shooting_percentage(0.5, 0.5, 0.5)
    var _t1_true_shooting_percentage = perf_counter_ns()
    var _ns_true_shooting_percentage = Float64(_t1_true_shooting_percentage - _t0_true_shooting_percentage) / Float64(N)
    print("MOJO_TIMING sports_analytics::true_shooting_percentage", _ns_true_shooting_percentage, _acc_true_shooting_percentage)
    var _result_true_shooting_percentage = true_shooting_percentage(0.5, 0.5, 0.5)
    var _summary_true_shooting_percentage = _summary_float64(_result_true_shooting_percentage)
    print("MOJO_RESULT sports_analytics::true_shooting_percentage", _summary_true_shooting_percentage)
    var _acc_player_efficiency_rating_approx: Float64 = 0.0
    var _t0_player_efficiency_rating_approx = perf_counter_ns()
    for _ in range(N):
        _acc_player_efficiency_rating_approx += player_efficiency_rating_approx(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_player_efficiency_rating_approx = perf_counter_ns()
    var _ns_player_efficiency_rating_approx = Float64(_t1_player_efficiency_rating_approx - _t0_player_efficiency_rating_approx) / Float64(N)
    print("MOJO_TIMING sports_analytics::player_efficiency_rating_approx", _ns_player_efficiency_rating_approx, _acc_player_efficiency_rating_approx)
    var _result_player_efficiency_rating_approx = player_efficiency_rating_approx(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_player_efficiency_rating_approx = _summary_float64(_result_player_efficiency_rating_approx)
    print("MOJO_RESULT sports_analytics::player_efficiency_rating_approx", _summary_player_efficiency_rating_approx)
