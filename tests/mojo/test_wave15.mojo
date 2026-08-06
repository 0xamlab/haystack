"""Wave 15 test suite — ODE Solver, Markov Chain, Tensor."""

from ode import ODEResult, rk4_solve, rk4_step, euler_step, euler_solve, exponential_decay, logistic_growth
from markov import MarkovChain
from tensor import (
    Tensor1D,
    zeros,
    ones,
    arange,
    linspace,
    full,
    add,
    sub,
    mul,
    scale,
    dot,
    sum_t,
    mean_t,
    max_t,
    min_t,
    argmax,
    argmin,
    apply_fn,
    concat,
    slice_t,
    norm,
    reverse,
    clip,
    allclose,
    equal,
    neg,
    div_t,
    count_nonzero,
)
from std.math import abs as fabs


def _make_list1(v0: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    return l^


def _make_list2(v0: Float64, v1: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    return l^


def _make_list3(v0: Float64, v1: Float64, v2: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    return l^


def main() raises:
    print("━━━ Wave 15 test suite (ODE Solver, Markov Chain, Tensor) ━━━\n")

    # ── ODE ──
    # Exponential decay: y' = -0.5*y, y0=100
    var coeffs = _make_list1(-0.5)
    var result = rk4_solve(100.0, coeffs, 0.0, 4.0, 0.1)
    # At t=4, y should be 100*exp(-2) ≈ 13.53
    var y_final = result.y_values[len(result.y_values) - 1]
    assert_true(fabs(y_final - 13.53) < 1.0, "RK4: exponential decay y(4) ≈ 13.53")

    # Analytical check
    assert_true(
        fabs(exponential_decay(100.0, 0.5, 4.0) - 13.534) < 0.1,
        "Analytical exponential decay",
    )

    # Logistic growth check
    var lg = logistic_growth(10.0, 100.0, 0.5, 10.0)
    assert_true(lg > 10.0 and lg <= 100.0, "Logistic growth within bounds")

    # Euler method basic check
    var euler_y0 = _make_list1(100.0)
    var euler_dy = _make_list1(-5.0)
    var euler_result = euler_step(euler_y0, euler_dy, 0.1)
    assert_true(
        fabs(euler_result[0] - 99.5) < 0.01, "Euler step: 100 - 0.5 = 99.5"
    )

    # RK4 step check
    var rk_coeffs = _make_list1(-0.5)
    var y_step = rk4_step(100.0, rk_coeffs, 0.0, 0.1)
    assert_true(y_step < 100.0 and y_step > 90.0, "RK4 step decreases value")

    print("✅ ODE solver")

    # ── Markov Chain ──
    var mc = MarkovChain(3)
    mc.set_transition(0, 0, 0.7)
    mc.set_transition(0, 1, 0.2)
    mc.set_transition(0, 2, 0.1)
    mc.set_transition(1, 0, 0.3)
    mc.set_transition(1, 1, 0.5)
    mc.set_transition(1, 2, 0.2)
    mc.set_transition(2, 0, 0.1)
    mc.set_transition(2, 1, 0.3)
    mc.set_transition(2, 2, 0.6)
    var history = mc.simulate(100)
    assert_true(len(history) == 101, "Markov: 100 steps + initial = 101")

    # All states should be valid (0, 1, or 2)
    var valid_states = True
    for i in range(len(history)):
        if history[i] < 0 or history[i] >= 3:
            valid_states = False
            break
    assert_true(valid_states, "Markov: all states in valid range")

    var ss = mc.steady_state()
    assert_true(len(ss) == 3, "Markov: steady state has 3 entries")

    # Probabilities should sum to 1.0
    var ss_sum: Float64 = 0.0
    for i in range(3):
        ss_sum += ss[i]
    assert_true(fabs(ss_sum - 1.0) < 0.01, "Markov: steady state sums to 1")

    # All steady state probabilities should be positive
    var all_pos = True
    for i in range(3):
        if ss[i] < 0.0:
            all_pos = False
    assert_true(all_pos, "Markov: all steady state probs >= 0")

    # Test get/set transition
    assert_true(
        fabs(mc.get_transition(0, 0) - 0.7) < 0.001,
        "Markov: get_transition matches set",
    )

    # Test expected visits
    var ev = mc.expected_visits(50)
    assert_true(len(ev) == 3, "Markov: expected visits has 3 entries")
    var ev_sum: Float64 = 0.0
    for i in range(3):
        ev_sum += ev[i]
    # Total expected visits should be approximately steps+1
    assert_true(ev_sum > 40.0, "Markov: total expected visits reasonable")

    # Test mean first passage
    var mfp = mc.mean_first_passage(0)
    assert_true(len(mfp) == 3, "Markov: mean first passage has 3 entries")
    assert_true(fabs(mfp[0]) < 0.001, "Markov: mfp to self is 0")
    assert_true(mfp[1] > 0.0, "Markov: mfp from 1 to 0 is positive")
    assert_true(mfp[2] > 0.0, "Markov: mfp from 2 to 0 is positive")

    print("✅ Markov chain")

    # ── Tensor ──
    var t1 = arange(0.0, 5.0, 1.0)
    assert_true(t1.size == 5, "Tensor: arange size")
    assert_true(t1.data[0] == 0.0, "Tensor: arange start")
    assert_true(t1.data[4] == 4.0, "Tensor: arange end")

    var t2 = ones(5)
    var t3 = add(t1, t2)
    assert_true(t3.data[0] == 1.0, "Tensor: add [0]")
    assert_true(t3.data[4] == 5.0, "Tensor: add [4]")

    assert_true(fabs(dot(t1, t2) - 10.0) < 0.001, "Tensor: dot product")
    assert_true(fabs(sum_t(t1) - 10.0) < 0.001, "Tensor: sum")
    assert_true(argmax(t1) == 4, "Tensor: argmax")
    assert_true(argmin(t1) == 0, "Tensor: argmin")

    var sq = apply_fn(t2, "square")
    assert_true(sq.data[0] == 1.0, "Tensor: apply square")

    # Test zeros
    var tz = zeros(3)
    assert_true(tz.size == 3 and tz.data[0] == 0.0, "Tensor: zeros")

    # Test scale
    var ts = scale(t1, 2.0)
    assert_true(ts.data[2] == 4.0, "Tensor: scale")

    # Test mul (element-wise)
    var tm = mul(t1, t1)
    assert_true(tm.data[3] == 9.0, "Tensor: element-wise mul 3*3=9")

    # Test mean
    assert_true(fabs(mean_t(t1) - 2.0) < 0.001, "Tensor: mean of [0,1,2,3,4]=2.0")

    # Test max/min
    assert_true(max_t(t1) == 4.0, "Tensor: max")
    assert_true(min_t(t1) == 0.0, "Tensor: min")

    # Test concat
    var tc = concat(ones(2), zeros(3))
    assert_true(tc.size == 5, "Tensor: concat size")
    assert_true(tc.data[0] == 1.0, "Tensor: concat [0]")
    assert_true(tc.data[3] == 0.0, "Tensor: concat [3]")

    # Test slice
    var tsl = slice_t(t1, 1, 4)
    assert_true(tsl.size == 3, "Tensor: slice size")
    assert_true(tsl.data[0] == 1.0, "Tensor: slice [0]")
    assert_true(tsl.data[2] == 3.0, "Tensor: slice [2]")

    # Test apply_fn with exp
    var te = apply_fn(zeros(3), "exp")
    assert_true(fabs(te.data[0] - 1.0) < 0.001, "Tensor: exp(0) = 1.0")

    # Test apply_fn with abs
    var neg_data = _make_list3(-1.0, -2.0, 3.0)
    var neg_t = Tensor1D(neg_data)
    var abs_t = apply_fn(neg_t, "abs")
    assert_true(abs_t.data[0] == 1.0, "Tensor: abs(-1) = 1")
    assert_true(abs_t.data[1] == 2.0, "Tensor: abs(-2) = 2")

    # Test linspace
    var tl = linspace(0.0, 1.0, 5)
    assert_true(tl.size == 5, "Tensor: linspace size")
    assert_true(fabs(tl.data[0]) < 0.001, "Tensor: linspace start")
    assert_true(fabs(tl.data[4] - 1.0) < 0.001, "Tensor: linspace end")

    # Test norm
    var norm_data = _make_list2(3.0, 4.0)
    var tn = Tensor1D(norm_data)
    assert_true(fabs(norm(tn) - 5.0) < 0.001, "Tensor: norm [3,4] = 5")

    # Test reverse
    var tr = reverse(t1)
    assert_true(tr.data[0] == 4.0, "Tensor: reverse [0]")
    assert_true(tr.data[4] == 0.0, "Tensor: reverse [4]")

    # Test clip
    var tcl = clip(t1, 1.0, 3.0)
    assert_true(tcl.data[0] == 1.0, "Tensor: clip 0 -> 1")
    assert_true(tcl.data[4] == 3.0, "Tensor: clip 4 -> 3")
    assert_true(tcl.data[2] == 2.0, "Tensor: clip 2 unchanged")

    print("✅ Tensor")

    print("\n✅ All Wave 15 tests passed")


def assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)
