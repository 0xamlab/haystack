"""
test_wave13.mojo — Tests for Wave 13 libraries: Finance, Differentiation, State Machine.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave13.mojo
"""
from finance import (
    npv,
    irr,
    payback_period,
    roi,
    compound_interest,
    present_value,
    future_value,
    annuity_payment,
    sharpe_ratio,
    max_drawdown,
    cagr,
    wacc,
)
from differentiate import (
    derivative_forward,
    derivative_central,
    derivative_backward,
    second_derivative,
    gradient,
    poly_derivative_coeffs,
)
from automata.state_machine import Transition, StateMachine
from std.math import abs as fabs


def main() raises:
    # ── Finance ──────────────────────────────────────────────────────────────

    # NPV: -1000 initial, then 300/year for 5 years at 10%
    var cf = List[Float64]()
    cf.append(-1000.0)
    for i in range(5):
        cf.append(300.0)
    var npv_val = npv(0.10, cf)
    assert_true(fabs(npv_val - 137.24) < 1.0, "NPV ≈ 137.24")

    # IRR of same cashflows should make NPV = 0
    var irr_val = irr(cf)
    assert_true(fabs(npv(irr_val, cf)) < 1.0, "NPV at IRR ≈ 0")

    # ROI
    assert_true(fabs(roi(150.0, 100.0) - 0.5) < 0.001, "ROI = 50%")

    # Compound interest: $1000 at 5% for 10 years
    assert_true(
        fabs(compound_interest(1000.0, 0.05, 10) - 1628.89) < 1.0,
        "Compound interest",
    )

    # Present value: inverse of compound interest
    var fv = compound_interest(1000.0, 0.05, 10)
    var pv = present_value(fv, 0.05, 10)
    assert_true(fabs(pv - 1000.0) < 0.01, "PV inverse of CI")

    # Future value
    var fv2 = future_value(1000.0, 0.05, 10)
    assert_true(fabs(fv2 - fv) < 0.01, "FV matches CI")

    # Annuity payment
    var pmt = annuity_payment(100000.0, 0.05, 30)
    assert_true(pmt > 0.0, "PMT positive")
    assert_true(fabs(pmt - 6505.15) < 1.0, "PMT ≈ 6505.15")

    # Sharpe ratio
    var rets = List[Float64]()
    rets.append(0.1)
    rets.append(0.05)
    rets.append(0.08)
    rets.append(-0.02)
    rets.append(0.12)
    var sr = sharpe_ratio(rets, 0.02)
    assert_true(sr > 0, "Sharpe positive")

    # Max drawdown
    var vals = List[Float64]()
    vals.append(100.0)
    vals.append(110.0)
    vals.append(90.0)
    vals.append(95.0)
    vals.append(120.0)
    var mdd = max_drawdown(vals)
    # Peak 110, trough 90 → dd = 20/110 ≈ 0.1818
    assert_true(fabs(mdd - 0.1818) < 0.01, "Max drawdown ≈ 18.18%")

    # CAGR
    var growth = cagr(1000.0, 2000.0, 5.0)
    assert_true(fabs(growth - 0.1487) < 0.01, "CAGR ≈ 14.87%")

    # WACC
    var w = wacc(600.0, 400.0, 0.10, 0.05, 0.30)
    # (0.6 * 0.10) + (0.4 * 0.05 * 0.7) = 0.06 + 0.014 = 0.074
    assert_true(fabs(w - 0.074) < 0.001, "WACC ≈ 7.4%")

    # Payback period
    var pb_cf = List[Float64]()
    pb_cf.append(-1000.0)
    pb_cf.append(400.0)
    pb_cf.append(400.0)
    pb_cf.append(400.0)
    var pp = payback_period(pb_cf)
    assert_true(pp > 1.0 and pp < 4.0, "Payback period in range")

    print("✅ Finance")

    # ── Differentiation ──────────────────────────────────────────────────────

    # Derivative of y=x^2 at various points: dy/dx = 2x
    var y = List[Float64]()
    for i in range(11):
        var x = Float64(i)
        y.append(x * x)
    var dy = derivative_central(y, 1.0)
    # At x=5 (index 5), dy/dx should be ≈10
    assert_true(fabs(dy[5] - 10.0) < 0.1, "Central diff at x=5 ≈ 10")

    # Forward difference
    var dy_fwd = derivative_forward(y, 1.0)
    # dy_fwd[5] = (y[6] - y[5]) / 1.0 = (36 - 25) = 11
    assert_true(fabs(dy_fwd[5] - 11.0) < 0.1, "Forward diff at x=5 ≈ 11")

    # Backward difference
    var dy_bwd = derivative_backward(y, 1.0)
    # dy_bwd[4] = (y[5] - y[4]) / 1.0 = (25 - 16) = 9
    assert_true(fabs(dy_bwd[4] - 9.0) < 0.1, "Backward diff at index 4 ≈ 9")

    # Second derivative of x^2 should be ≈ 2
    var d2y = second_derivative(y, 1.0)
    assert_true(fabs(d2y[3] - 2.0) < 0.1, "Second deriv of x^2 ≈ 2")

    # Polynomial derivative: d/dx(3x^2 + 2x + 1) = 6x + 2
    var poly = List[Float64]()
    poly.append(1.0)
    poly.append(2.0)
    poly.append(3.0)
    var dpoly = poly_derivative_coeffs(poly)
    assert_true(fabs(dpoly[0] - 2.0) < 0.001, "poly deriv const = 2")
    assert_true(fabs(dpoly[1] - 6.0) < 0.001, "poly deriv linear = 6")

    # Gradient (non-uniform spacing)
    var gx = List[Float64]()
    var gy = List[Float64]()
    gx.append(0.0)
    gx.append(1.0)
    gx.append(3.0)
    gx.append(6.0)
    gy.append(0.0)
    gy.append(1.0)
    gy.append(9.0)
    gy.append(36.0)
    var g = gradient(gy, gx)
    assert_true(len(g) == 4, "Gradient length matches input")

    print("✅ Differentiation")

    # ── State Machine ────────────────────────────────────────────────────────

    var sm = StateMachine("idle")
    sm.add_state("idle")
    sm.add_state("running")
    sm.add_state("completed")
    sm.add_state("failed")
    sm.add_transition("idle", "start", "running")
    sm.add_transition("running", "finish", "completed")
    sm.add_transition("running", "error", "failed")
    sm.add_transition("failed", "retry", "idle")

    assert_true(sm.current_state == "idle", "Initial state is idle")
    assert_true(sm.state_count() == 4, "4 states")
    assert_true(sm.transition_count() == 4, "4 transitions")

    assert_true(sm.fire("start", 0.0), "fire start")
    assert_true(sm.current_state == "running", "State is running")
    assert_true(not sm.can_fire("start", 0.0), "can't start again")

    assert_true(sm.fire("finish", 0.0), "fire finish")
    assert_true(sm.current_state == "completed", "State is completed")
    assert_true(len(sm.history) == 3, "History: idle → running → completed")

    sm.reset()
    assert_true(sm.current_state == "idle", "Reset to idle")
    assert_true(len(sm.history) == 1, "History reset")

    # Possible events
    var events = sm.get_possible_events()
    assert_true(len(events) == 1, "One event from idle")
    assert_true(events[0] == "start", "Event is start")

    # Guard test: add a guarded transition
    sm.add_state("approved")
    sm.add_transition("idle", "approve", "approved", guard=100.0)
    # Should fail with value < guard
    assert_true(not sm.fire("approve", 50.0), "Guard blocks low value")
    assert_true(sm.current_state == "idle", "Still idle after blocked")
    # Should succeed with value >= guard
    assert_true(sm.fire("approve", 100.0), "Guard passes at threshold")
    assert_true(sm.current_state == "approved", "State is approved")

    # Error path
    sm.reset()
    _ = sm.fire("start", 0.0)
    assert_true(sm.fire("error", 0.0), "fire error")
    assert_true(sm.current_state == "failed", "State is failed")
    assert_true(sm.fire("retry", 0.0), "fire retry")
    assert_true(sm.current_state == "idle", "Back to idle after retry")

    print("✅ State machine")

    print("✅ All Wave 13 tests passed")


def assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)
