"""bench_finance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from finance import npv, irr, payback_period, roi, compound_interest, present_value, future_value, annuity_payment, sharpe_ratio, max_drawdown, cagr, wacc
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

    var _acc_npv: Float64 = 0.0
    var _t0_npv = perf_counter_ns()
    for _ in range(N):
        _acc_npv += npv(0.5, _lf5)
    var _t1_npv = perf_counter_ns()
    var _ns_npv = Float64(_t1_npv - _t0_npv) / Float64(N)
    print("MOJO_TIMING finance::npv", _ns_npv, _acc_npv)
    var _acc_irr: Float64 = 0.0
    var _t0_irr = perf_counter_ns()
    for _ in range(N):
        _acc_irr += irr(_lf5, 0.5, 0.5, 5)
    var _t1_irr = perf_counter_ns()
    var _ns_irr = Float64(_t1_irr - _t0_irr) / Float64(N)
    print("MOJO_TIMING finance::irr", _ns_irr, _acc_irr)
    var _acc_payback_period: Float64 = 0.0
    var _t0_payback_period = perf_counter_ns()
    for _ in range(N):
        _acc_payback_period += payback_period(_lf5)
    var _t1_payback_period = perf_counter_ns()
    var _ns_payback_period = Float64(_t1_payback_period - _t0_payback_period) / Float64(N)
    print("MOJO_TIMING finance::payback_period", _ns_payback_period, _acc_payback_period)
    var _acc_roi: Float64 = 0.0
    var _t0_roi = perf_counter_ns()
    for _ in range(N):
        _acc_roi += roi(0.5, 0.5)
    var _t1_roi = perf_counter_ns()
    var _ns_roi = Float64(_t1_roi - _t0_roi) / Float64(N)
    print("MOJO_TIMING finance::roi", _ns_roi, _acc_roi)
    var _acc_compound_interest: Float64 = 0.0
    var _t0_compound_interest = perf_counter_ns()
    for _ in range(N):
        _acc_compound_interest += compound_interest(0.5, 0.5, 5)
    var _t1_compound_interest = perf_counter_ns()
    var _ns_compound_interest = Float64(_t1_compound_interest - _t0_compound_interest) / Float64(N)
    print("MOJO_TIMING finance::compound_interest", _ns_compound_interest, _acc_compound_interest)
    var _acc_present_value: Float64 = 0.0
    var _t0_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_present_value += present_value(0.5, 0.5, 5)
    var _t1_present_value = perf_counter_ns()
    var _ns_present_value = Float64(_t1_present_value - _t0_present_value) / Float64(N)
    print("MOJO_TIMING finance::present_value", _ns_present_value, _acc_present_value)
    var _acc_future_value: Float64 = 0.0
    var _t0_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_future_value += future_value(0.5, 0.5, 5)
    var _t1_future_value = perf_counter_ns()
    var _ns_future_value = Float64(_t1_future_value - _t0_future_value) / Float64(N)
    print("MOJO_TIMING finance::future_value", _ns_future_value, _acc_future_value)
    var _acc_annuity_payment: Float64 = 0.0
    var _t0_annuity_payment = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_payment += annuity_payment(0.5, 0.5, 5)
    var _t1_annuity_payment = perf_counter_ns()
    var _ns_annuity_payment = Float64(_t1_annuity_payment - _t0_annuity_payment) / Float64(N)
    print("MOJO_TIMING finance::annuity_payment", _ns_annuity_payment, _acc_annuity_payment)
    var _acc_sharpe_ratio: Float64 = 0.0
    var _t0_sharpe_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sharpe_ratio += sharpe_ratio(_lf5, 0.5)
    var _t1_sharpe_ratio = perf_counter_ns()
    var _ns_sharpe_ratio = Float64(_t1_sharpe_ratio - _t0_sharpe_ratio) / Float64(N)
    print("MOJO_TIMING finance::sharpe_ratio", _ns_sharpe_ratio, _acc_sharpe_ratio)
    var _acc_max_drawdown: Float64 = 0.0
    var _t0_max_drawdown = perf_counter_ns()
    for _ in range(N):
        _acc_max_drawdown += max_drawdown(_lf5)
    var _t1_max_drawdown = perf_counter_ns()
    var _ns_max_drawdown = Float64(_t1_max_drawdown - _t0_max_drawdown) / Float64(N)
    print("MOJO_TIMING finance::max_drawdown", _ns_max_drawdown, _acc_max_drawdown)
    var _acc_cagr: Float64 = 0.0
    var _t0_cagr = perf_counter_ns()
    for _ in range(N):
        _acc_cagr += cagr(0.5, 0.5, 0.5)
    var _t1_cagr = perf_counter_ns()
    var _ns_cagr = Float64(_t1_cagr - _t0_cagr) / Float64(N)
    print("MOJO_TIMING finance::cagr", _ns_cagr, _acc_cagr)
    var _acc_wacc: Float64 = 0.0
    var _t0_wacc = perf_counter_ns()
    for _ in range(N):
        _acc_wacc += wacc(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_wacc = perf_counter_ns()
    var _ns_wacc = Float64(_t1_wacc - _t0_wacc) / Float64(N)
    print("MOJO_TIMING finance::wacc", _ns_wacc, _acc_wacc)
