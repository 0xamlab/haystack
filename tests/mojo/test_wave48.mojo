"""Tests for Wave 48 — Neural Network Layers, Options Pricing, Fluid Dynamics."""

from nn_layers import (
    dense_forward,
    relu,
    sigmoid_activation,
    tanh_activation,
    softmax_layer,
    mse_loss,
    cross_entropy_loss,
    dropout,
    batch_norm,
    leaky_relu,
    init_weights_xavier,
)
from option_pricing import (
    norm_cdf,
    black_scholes_call,
    black_scholes_put,
    delta_call,
    gamma,
    vega,
    theta_call,
    put_call_parity,
    binomial_tree_call,
    implied_volatility,
)
from fluid import (
    reynolds_number,
    is_turbulent,
    bernoulli_velocity,
    friction_factor_laminar,
    darcy_weisbach,
    flow_rate,
    pipe_velocity,
    hydraulic_diameter,
    mach_number,
    drag_force,
    buoyancy_force,
    stokes_drag,
)

from std.math import abs as fabs, exp, sqrt


# ── Helpers ──────────────────────────────────────────────────────────────────


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _lf1(a: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    return r^


def _lf3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c)
    return r^


def _lf4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    return r^


# ── NN: relu ─────────────────────────────────────────────────────────────────


def test_relu() raises:
    var x = _lf4(1.0, -2.0, 3.0, -4.0)
    var y = relu(x)
    _assert_close(y[0], 1.0, 1e-12, "relu[0]")          # 1
    _assert_close(y[1], 0.0, 1e-12, "relu[1]")          # 2
    _assert_close(y[2], 3.0, 1e-12, "relu[2]")          # 3
    _assert_close(y[3], 0.0, 1e-12, "relu[3]")          # 4
    print("  ✓ relu")


# ── NN: sigmoid ──────────────────────────────────────────────────────────────


def test_sigmoid() raises:
    var x = _lf1(0.0)
    var y = sigmoid_activation(x)
    _assert_close(y[0], 0.5, 1e-10, "sigmoid(0)=0.5")   # 5
    var x2 = _lf1(100.0)
    var y2 = sigmoid_activation(x2)
    _assert(y2[0] > 0.999, "sigmoid(100)~1")             # 6
    var x3 = _lf1(-100.0)
    var y3 = sigmoid_activation(x3)
    _assert(y3[0] < 0.001, "sigmoid(-100)~0")            # 7
    print("  ✓ sigmoid_activation")


# ── NN: tanh ─────────────────────────────────────────────────────────────────


def test_tanh() raises:
    var x = _lf1(0.0)
    var y = tanh_activation(x)
    _assert_close(y[0], 0.0, 1e-12, "tanh(0)=0")        # 8
    print("  ✓ tanh_activation")


# ── NN: softmax ──────────────────────────────────────────────────────────────


def test_softmax() raises:
    var x = _lf3(0.0, 0.0, 0.0)
    var y = softmax_layer(x)
    _assert_close(y[0], 1.0 / 3.0, 1e-10, "softmax uniform[0]")   # 9
    _assert_close(y[1], 1.0 / 3.0, 1e-10, "softmax uniform[1]")   # 10
    _assert_close(y[2], 1.0 / 3.0, 1e-10, "softmax uniform[2]")   # 11

    # softmax sums to 1
    var x2 = _lf3(1.0, 2.0, 3.0)
    var y2 = softmax_layer(x2)
    var total: Float64 = y2[0] + y2[1] + y2[2]
    _assert_close(total, 1.0, 1e-10, "softmax sums to 1")          # 12

    # softmax ordering preserved
    _assert(y2[2] > y2[1], "softmax order 2>1")                    # 13
    _assert(y2[1] > y2[0], "softmax order 1>0")                    # 14
    print("  ✓ softmax_layer")


# ── NN: mse_loss ─────────────────────────────────────────────────────────────


def test_mse_loss() raises:
    var p = _lf3(1.0, 2.0, 3.0)
    var a = _lf3(1.0, 2.0, 3.0)
    _assert_close(mse_loss(p, a), 0.0, 1e-12, "mse_loss perfect")  # 15

    var p2 = _lf3(1.0, 2.0, 3.0)
    var a2 = _lf3(2.0, 3.0, 4.0)
    _assert_close(mse_loss(p2, a2), 1.0, 1e-12, "mse_loss=1")      # 16
    print("  ✓ mse_loss")


# ── NN: cross_entropy_loss ───────────────────────────────────────────────────


def test_cross_entropy() raises:
    var p = _lf3(0.9, 0.1, 0.8)
    var a = _lf3(1.0, 0.0, 1.0)
    var loss = cross_entropy_loss(p, a)
    _assert(loss > 0.0, "cross_entropy > 0")                        # 17
    _assert(loss < 10.0, "cross_entropy finite")                     # 18
    print("  ✓ cross_entropy_loss")


# ── NN: dense_forward ────────────────────────────────────────────────────────


def test_dense_forward() raises:
    # 2x3 weights, input of size 3 -> output of size 2
    var w = List[List[Float64]]()
    var row1 = _lf3(1.0, 0.0, 0.0)
    var row2 = _lf3(0.0, 1.0, 0.0)
    w.append(row1^)
    w.append(row2^)
    var bias = List[Float64]()
    bias.append(0.5)
    bias.append(-0.5)
    var inp = _lf3(2.0, 3.0, 4.0)
    var out = dense_forward(inp, w, bias)
    _assert_eq(len(out), 2, "dense output dim")                     # 19
    _assert_close(out[0], 2.5, 1e-12, "dense out[0]")              # 20
    _assert_close(out[1], 2.5, 1e-12, "dense out[1]")              # 21
    print("  ✓ dense_forward")


# ── NN: batch_norm ───────────────────────────────────────────────────────────


def test_batch_norm() raises:
    var x = _lf4(1.0, 2.0, 3.0, 4.0)
    var y = batch_norm(x)
    # mean of output should be ~0 (beta=0)
    var mean: Float64 = (y[0] + y[1] + y[2] + y[3]) / 4.0
    _assert_close(mean, 0.0, 1e-6, "batch_norm mean~0")             # 22

    # With beta=5
    var y2 = batch_norm(x, 1.0, 5.0)
    var mean2: Float64 = (y2[0] + y2[1] + y2[2] + y2[3]) / 4.0
    _assert_close(mean2, 5.0, 1e-6, "batch_norm mean~beta")         # 23
    print("  ✓ batch_norm")


# ── NN: leaky_relu ───────────────────────────────────────────────────────────


def test_leaky_relu() raises:
    var x = _lf1(-1.0)
    var y = leaky_relu(x, 0.1)
    _assert_close(y[0], -0.1, 1e-12, "leaky_relu(-1,0.1)")         # 24

    var x2 = _lf1(5.0)
    var y2 = leaky_relu(x2, 0.1)
    _assert_close(y2[0], 5.0, 1e-12, "leaky_relu(5,0.1)=5")        # 25
    print("  ✓ leaky_relu")


# ── NN: dropout ──────────────────────────────────────────────────────────────


def test_dropout() raises:
    var x = _lf4(1.0, 2.0, 3.0, 4.0)
    var y = dropout(x, 0.0)  # rate=0 -> no dropout
    _assert_close(y[0], 1.0, 1e-12, "dropout rate=0 [0]")           # 26
    _assert_close(y[3], 4.0, 1e-12, "dropout rate=0 [3]")           # 27
    print("  ✓ dropout")


# ── NN: init_weights_xavier ──────────────────────────────────────────────────


def test_xavier() raises:
    var w = init_weights_xavier(3, 2)
    _assert_eq(len(w), 2, "xavier n_out=2")                         # 28
    _assert_eq(len(w[0]), 3, "xavier n_in=3")                       # 29
    var limit = sqrt(6.0 / 5.0)
    for i in range(2):
        for j in range(3):
            _assert(w[i][j] >= -limit and w[i][j] <= limit,
                    "xavier in bounds")                               # 30-35
    print("  ✓ init_weights_xavier")


# ── Options: norm_cdf ────────────────────────────────────────────────────────


def test_norm_cdf() raises:
    _assert_close(norm_cdf(0.0), 0.5, 1e-6, "norm_cdf(0)=0.5")     # 36
    _assert(norm_cdf(3.0) > 0.99, "norm_cdf(3)>0.99")               # 37
    _assert(norm_cdf(-3.0) < 0.01, "norm_cdf(-3)<0.01")             # 38
    print("  ✓ norm_cdf")


# ── Options: black_scholes_call ──────────────────────────────────────────────


def test_bs_call() raises:
    var c = black_scholes_call(100.0, 100.0, 1.0, 0.05, 0.2)
    _assert_close(c, 10.4506, 0.05, "BS call≈10.45")                # 39
    print("  ✓ black_scholes_call")


# ── Options: put_call_parity ─────────────────────────────────────────────────


def test_parity() raises:
    var S: Float64 = 100.0
    var K: Float64 = 100.0
    var T: Float64 = 1.0
    var r: Float64 = 0.05
    var sigma: Float64 = 0.2
    var c = black_scholes_call(S, K, T, r, sigma)
    var p = black_scholes_put(S, K, T, r, sigma)
    var p_parity = put_call_parity(c, K, T, r, S)
    _assert_close(p, p_parity, 1e-8, "put-call parity")             # 40

    # C - P = S - K*exp(-rT)
    var lhs = c - p
    var rhs = S - K * exp(-r * T)
    _assert_close(lhs, rhs, 1e-8, "C-P = S-Ke^-rT")                # 41
    print("  ✓ put_call_parity")


# ── Options: delta_call ──────────────────────────────────────────────────────


def test_delta() raises:
    var d = delta_call(100.0, 100.0, 1.0, 0.05, 0.2)
    _assert(d > 0.0, "delta > 0")                                    # 42
    _assert(d < 1.0, "delta < 1")                                    # 43
    _assert_close(d, 0.6368, 0.01, "delta~0.64")                    # 44
    print("  ✓ delta_call")


# ── Options: gamma ───────────────────────────────────────────────────────────


def test_gamma() raises:
    var g = gamma(100.0, 100.0, 1.0, 0.05, 0.2)
    _assert(g > 0.0, "gamma > 0")                                    # 45
    print("  ✓ gamma")


# ── Options: vega ────────────────────────────────────────────────────────────


def test_vega() raises:
    var v = vega(100.0, 100.0, 1.0, 0.05, 0.2)
    _assert(v > 0.0, "vega > 0")                                     # 46
    print("  ✓ vega")


# ── Options: theta_call ─────────────────────────────────────────────────────


def test_theta() raises:
    var t = theta_call(100.0, 100.0, 1.0, 0.05, 0.2)
    _assert(t < 0.0, "theta < 0 (time decay)")                       # 47
    print("  ✓ theta_call")


# ── Options: binomial_tree_call ──────────────────────────────────────────────


def test_binomial() raises:
    var bs = black_scholes_call(100.0, 100.0, 1.0, 0.05, 0.2)
    var bt = binomial_tree_call(100.0, 100.0, 1.0, 0.05, 0.2, 200)
    _assert_close(bt, bs, 0.1, "binomial converges to BS")           # 48
    print("  ✓ binomial_tree_call")


# ── Options: implied_volatility ──────────────────────────────────────────────


def test_iv() raises:
    var sigma: Float64 = 0.25
    var price = black_scholes_call(100.0, 100.0, 1.0, 0.05, sigma)
    var iv = implied_volatility(price, 100.0, 100.0, 1.0, 0.05, True)
    _assert_close(iv, sigma, 1e-4, "IV roundtrip")                   # 49
    print("  ✓ implied_volatility")


# ── Fluid: reynolds_number ───────────────────────────────────────────────────


def test_reynolds() raises:
    var re = reynolds_number(1.0, 1.0, 1e-6)
    _assert_close(re, 1e6, 1.0, "Re=1e6")                            # 50
    print("  ✓ reynolds_number")


# ── Fluid: is_turbulent ─────────────────────────────────────────────────────


def test_turbulent() raises:
    _assert(is_turbulent(5000.0) == True, "Re=5000 turbulent")       # 51
    _assert(is_turbulent(2000.0) == False, "Re=2000 laminar")        # 52
    print("  ✓ is_turbulent")


# ── Fluid: friction_factor_laminar ───────────────────────────────────────────


def test_friction() raises:
    var f = friction_factor_laminar(100.0)
    _assert_close(f, 0.64, 1e-10, "f=64/100=0.64")                  # 53
    print("  ✓ friction_factor_laminar")


# ── Fluid: mach_number ──────────────────────────────────────────────────────


def test_mach() raises:
    var m = mach_number(343.0)
    _assert_close(m, 1.0, 1e-10, "mach(343)=1.0")                   # 54
    var m2 = mach_number(686.0)
    _assert_close(m2, 2.0, 1e-6, "mach(686)~2.0")                   # 55
    print("  ✓ mach_number")


# ── Fluid: flow_rate ─────────────────────────────────────────────────────────


def test_flow_rate() raises:
    _assert_close(flow_rate(2.0, 5.0), 10.0, 1e-12, "Q=2*5=10")    # 56
    print("  ✓ flow_rate")


# ── Fluid: drag_force ───────────────────────────────────────────────────────


def test_drag() raises:
    var fd = drag_force(0.47, 1.225, 10.0, 0.5)
    _assert(fd > 0.0, "drag > 0")                                    # 57
    # 0.5*0.47*1.225*100*0.5 = 14.39375
    _assert_close(fd, 14.39375, 1e-4, "drag value")                  # 58
    print("  ✓ drag_force")


# ── Fluid: buoyancy_force ───────────────────────────────────────────────────


def test_buoyancy() raises:
    var fb = buoyancy_force(1000.0, 0.01)
    _assert(fb > 0.0, "buoyancy > 0")                                # 59
    _assert_close(fb, 98.1, 1e-4, "buoyancy=1000*0.01*9.81")        # 60
    print("  ✓ buoyancy_force")


# ── Fluid: stokes_drag ──────────────────────────────────────────────────────


def test_stokes() raises:
    var fs = stokes_drag(0.001, 0.01, 0.1)
    _assert(fs > 0.0, "stokes > 0")                                  # 61
    print("  ✓ stokes_drag")


# ── Fluid: bernoulli_velocity ────────────────────────────────────────────────


def test_bernoulli() raises:
    var v = bernoulli_velocity(200000.0, 100000.0, 1000.0)
    _assert(v > 0.0, "bernoulli v > 0 for p1>p2")                   # 62
    # v = sqrt(2*(200000-100000)/1000) = sqrt(200) ≈ 14.14
    _assert_close(v, sqrt(200.0), 1e-6, "bernoulli value")          # 63
    print("  ✓ bernoulli_velocity")


# ── Fluid: pipe_velocity ────────────────────────────────────────────────────


def test_pipe_velocity() raises:
    var v = pipe_velocity(0.01, 0.1)
    _assert(v > 0.0, "pipe velocity > 0")                            # 64
    print("  ✓ pipe_velocity")


# ── Fluid: hydraulic_diameter ────────────────────────────────────────────────


def test_hydraulic_diameter() raises:
    # Square duct: D_h = 4*w*h / (2*(w+h)) = 4*1*1/4 = 1
    var dh = hydraulic_diameter(1.0, 1.0)
    _assert_close(dh, 1.0, 1e-12, "Dh square=1")                    # 65
    print("  ✓ hydraulic_diameter")


# ── Fluid: darcy_weisbach ───────────────────────────────────────────────────


def test_darcy_weisbach() raises:
    var dp = darcy_weisbach(0.02, 100.0, 0.5, 2.0, 1000.0)
    # 0.02 * (100/0.5) * (1000*4/2) = 0.02 * 200 * 2000 = 8000
    _assert_close(dp, 8000.0, 1e-4, "darcy_weisbach dp")            # 66
    _assert(dp > 0.0, "darcy dp > 0")                                # 67
    print("  ✓ darcy_weisbach")


# ── main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 48 Tests ===")

    # Neural Network
    print("── Neural Network Layers ──")
    test_relu()
    test_sigmoid()
    test_tanh()
    test_softmax()
    test_mse_loss()
    test_cross_entropy()
    test_dense_forward()
    test_batch_norm()
    test_leaky_relu()
    test_dropout()
    test_xavier()

    # Options Pricing
    print("── Options Pricing ──")
    test_norm_cdf()
    test_bs_call()
    test_parity()
    test_delta()
    test_gamma()
    test_vega()
    test_theta()
    test_binomial()
    test_iv()

    # Fluid Dynamics
    print("── Fluid Dynamics ──")
    test_reynolds()
    test_turbulent()
    test_friction()
    test_mach()
    test_flow_rate()
    test_drag()
    test_buoyancy()
    test_stokes()
    test_bernoulli()
    test_pipe_velocity()
    test_hydraulic_diameter()
    test_darcy_weisbach()

    print("=== All 67 assertions passed ✅ ===")
