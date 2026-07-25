"""test_hmm.mojo — known-value tests for hmm (forward/backward/viterbi/Baum-Welch)."""
from hmm import (
    HMMForward,
    HMMModel,
    hmm_forward,
    hmm_backward,
    hmm_viterbi,
    hmm_baum_welch,
)
from std.math import abs as fabs

# Correctly-rounded ln reference values (std.math.log here is a ~1e-10
# approximation, so expected values are hardcoded instead).
comptime LN_0152544: Float64 = -1.8803021999597218  # ln(0.152544)
comptime LN_056: Float64 = -0.579818495252942  # ln(0.56)
comptime LN_008: Float64 = -2.5257286443082556  # ln(0.08)
comptime LN_01128: Float64 = -2.1821389399181785  # ln(0.1128)
comptime LN_01584: Float64 = -1.8426317996018116  # ln(0.1584)
comptime LN_0102816: Float64 = -2.2748142960486892  # ln(0.102816)
comptime LN_0049728: Float64 = -3.0011871242369548  # ln(0.049728)
comptime LN_064: Float64 = -0.4462871026284195  # ln(0.64)
comptime LN_058: Float64 = -0.5447271754416722  # ln(0.58)
comptime LN_055: Float64 = -0.5978370007556204  # ln(0.55)
comptime LN_02364: Float64 = -1.4422299934501939  # ln(0.2364)
comptime LN_0252: Float64 = -1.3783261914707137  # ln(0.252)


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ hmm::" + name)
    else:
        failed += 1
        print("  ❌ hmm::" + name)


fn _close(x: Float64, y: Float64, tol: Float64) -> Bool:
    return fabs(x - y) < tol


fn _paths_equal(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _row(v0: Float64, v1: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(v0)
    r.append(v1)
    return r^


fn _row3(v0: Float64, v1: Float64, v2: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(v0)
    r.append(v1)
    r.append(v2)
    return r^


fn _row_sum(r: List[Float64]) -> Float64:
    var s = 0.0
    for i in range(len(r)):
        s += r[i]
    return s


# 2-state / 2-symbol hand model for forward/backward:
#   pi = [0.8, 0.2]; A = [[0.6, 0.4], [0.5, 0.5]]; B = [[0.7, 0.3], [0.4, 0.6]]
fn _fwd_a() -> List[List[Float64]]:
    var a = List[List[Float64]]()
    a.append(_row(0.6, 0.4))
    a.append(_row(0.5, 0.5))
    return a^


fn _fwd_b() -> List[List[Float64]]:
    var b = List[List[Float64]]()
    b.append(_row(0.7, 0.3))
    b.append(_row(0.4, 0.6))
    return b^


# Classic 2-state weather model (Rainy=0, Sunny=1; walk=0, shop=1, clean=2):
#   pi = [0.6, 0.4]; A = [[0.7, 0.3], [0.4, 0.6]]
#   B  = [[0.1, 0.4, 0.5], [0.6, 0.3, 0.1]]
fn _wx_a() -> List[List[Float64]]:
    var a = List[List[Float64]]()
    a.append(_row(0.7, 0.3))
    a.append(_row(0.4, 0.6))
    return a^


fn _wx_b() -> List[List[Float64]]:
    var b = List[List[Float64]]()
    b.append(_row3(0.1, 0.4, 0.5))
    b.append(_row3(0.6, 0.3, 0.1))
    return b^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── hmm_forward: hand-computed 3-step sequence ───────────────────────────
    # obs = [0, 1, 0]:
    #   alpha0 = [0.8*0.7, 0.2*0.4]                      = [0.56, 0.08]
    #   alpha1 = [(0.56*0.6+0.08*0.5)*0.3,
    #             (0.56*0.4+0.08*0.5)*0.6]               = [0.1128, 0.1584]
    #   alpha2 = [(0.1128*0.6+0.1584*0.5)*0.7,
    #             (0.1128*0.4+0.1584*0.5)*0.4]           = [0.102816, 0.049728]
    #   P(O) = 0.102816 + 0.049728 = 0.152544
    var pi_f = _row(0.8, 0.2)
    var obs3 = List[Int]()
    obs3.append(0)
    obs3.append(1)
    obs3.append(0)
    var fwd = hmm_forward(obs3, _fwd_a(), _fwd_b(), pi_f)
    check(
        _close(fwd.loglik, LN_0152544, 1e-9),
        "forward loglik matches hand-computed 3-step value",
        passed,
        failed,
    )
    check(
        len(fwd.log_alpha) == 3
        and _close(fwd.log_alpha[0][0], LN_056, 1e-12)
        and _close(fwd.log_alpha[0][1], LN_008, 1e-12)
        and _close(fwd.log_alpha[1][0], LN_01128, 1e-12)
        and _close(fwd.log_alpha[1][1], LN_01584, 1e-12)
        and _close(fwd.log_alpha[2][0], LN_0102816, 1e-12)
        and _close(fwd.log_alpha[2][1], LN_0049728, 1e-12),
        "forward log_alpha exact per cell",
        passed,
        failed,
    )

    # ── hmm_forward: single observation ──────────────────────────────────────
    # obs = [0]: P = 0.8*0.7 + 0.2*0.4 = 0.64
    var obs1 = List[Int]()
    obs1.append(0)
    var fwd1 = hmm_forward(obs1, _fwd_a(), _fwd_b(), pi_f)
    check(
        _close(fwd1.loglik, LN_064, 1e-12),
        "forward n=1 loglik",
        passed,
        failed,
    )

    # ── hmm_forward: empty obs ───────────────────────────────────────────────
    var obs0 = List[Int]()
    var fwd0 = hmm_forward(obs0, _fwd_a(), _fwd_b(), pi_f)
    check(
        len(fwd0.log_alpha) == 0 and fwd0.loglik == 0.0,
        "forward empty obs -> empty alpha, loglik 0",
        passed,
        failed,
    )

    # ── hmm_backward: hand-computed values ───────────────────────────────────
    #   beta2 = [1, 1]
    #   beta1 = [0.6*0.7+0.4*0.4, 0.5*0.7+0.5*0.4]       = [0.58, 0.55]
    #   beta0 = [0.6*0.3*0.58+0.4*0.6*0.55,
    #            0.5*0.3*0.58+0.5*0.6*0.55]              = [0.2364, 0.252]
    var bwd = hmm_backward(obs3, _fwd_a(), _fwd_b(), pi_f)
    check(
        len(bwd) == 3
        and bwd[2][0] == 0.0
        and bwd[2][1] == 0.0
        and _close(bwd[1][0], LN_058, 1e-12)
        and _close(bwd[1][1], LN_055, 1e-12)
        and _close(bwd[0][0], LN_02364, 1e-12)
        and _close(bwd[0][1], LN_0252, 1e-12),
        "backward log_beta exact per cell",
        passed,
        failed,
    )

    # ── forward/backward consistency: alpha[t][i]*beta[t][i] known cell-wise ─
    # t=0: [0.56*0.2364, 0.08*0.252]   = [0.132384, 0.02016]
    # t=1: [0.1128*0.58, 0.1584*0.55]  = [0.065424, 0.08712]
    # t=2: [0.102816, 0.049728]        (beta = 1)
    check(
        _close(fwd.log_alpha[0][0] + bwd[0][0], -2.022048488703136, 1e-12)
        and _close(fwd.log_alpha[0][1] + bwd[0][1], -3.904054835778969, 1e-12)
        and _close(fwd.log_alpha[1][0] + bwd[1][0], -2.726866115359851, 1e-12)
        and _close(fwd.log_alpha[1][1] + bwd[1][1], -2.440468800357432, 1e-12)
        and _close(fwd.log_alpha[2][0] + bwd[2][0], LN_0102816, 1e-12)
        and _close(fwd.log_alpha[2][1] + bwd[2][1], LN_0049728, 1e-12),
        "forward*backward joint probs exact at every t",
        passed,
        failed,
    )

    # ── hmm_viterbi: weather model recovers known optimal path ───────────────
    # obs = [walk, shop, clean] -> [Sunny, Rainy, Rainy] = [1, 0, 0]
    # (best path prob 0.24*0.4*0.4*0.7*0.5 = 0.01344)
    var pi_w = _row(0.6, 0.4)
    var wobs = List[Int]()
    wobs.append(0)
    wobs.append(1)
    wobs.append(2)
    var wpath = hmm_viterbi(wobs, _wx_a(), _wx_b(), pi_w)
    var expected = List[Int]()
    expected.append(1)
    expected.append(0)
    expected.append(0)
    check(
        _paths_equal(wpath, expected),
        "viterbi weather model recovers [Sunny, Rainy, Rainy]",
        passed,
        failed,
    )

    # ── hmm_viterbi: n=1 picks argmax pi_i * b_i(o) ──────────────────────────
    # obs = [walk]: Rainy 0.6*0.1=0.06 vs Sunny 0.4*0.6=0.24 -> Sunny (1)
    var wobs1 = List[Int]()
    wobs1.append(0)
    var wpath1 = hmm_viterbi(wobs1, _wx_a(), _wx_b(), pi_w)
    check(
        len(wpath1) == 1 and wpath1[0] == 1,
        "viterbi n=1 argmax initial*emission",
        passed,
        failed,
    )

    # ── hmm_viterbi: all-equal model ties break to lower state index ─────────
    var pi_u = _row(0.5, 0.5)
    var a_u = List[List[Float64]]()
    a_u.append(_row(0.5, 0.5))
    a_u.append(_row(0.5, 0.5))
    var b_u = List[List[Float64]]()
    b_u.append(_row(0.5, 0.5))
    b_u.append(_row(0.5, 0.5))
    var uobs = List[Int]()
    uobs.append(0)
    uobs.append(0)
    var upath = hmm_viterbi(uobs, a_u, b_u, pi_u)
    check(
        len(upath) == 2 and upath[0] == 0 and upath[1] == 0,
        "viterbi all-equal model tie-breaks to state 0",
        passed,
        failed,
    )

    # ── hmm_viterbi: empty obs -> empty path ─────────────────────────────────
    var epath = hmm_viterbi(obs0, _wx_a(), _wx_b(), pi_w)
    check(len(epath) == 0, "viterbi empty obs -> empty path", passed, failed)

    # ── hmm_baum_welch: structured sequence, monotone loglik ─────────────────
    # 10 repeats of [0,0,0,1,1,1] (T=60): strong 2-regime structure.
    var tobs = List[Int]()
    for _ in range(10):
        tobs.append(0)
        tobs.append(0)
        tobs.append(0)
        tobs.append(1)
        tobs.append(1)
        tobs.append(1)
    var model = hmm_baum_welch(tobs, 2, 2, 30, 7)
    check(
        len(model.loglik_history) == 31,
        "baum_welch history has max_iter+1 entries",
        passed,
        failed,
    )
    var monotone = True
    for k in range(1, len(model.loglik_history)):
        if model.loglik_history[k] < model.loglik_history[k - 1] - 1e-9:
            monotone = False
    check(monotone, "baum_welch loglik monotone non-decreasing", passed, failed)
    check(
        model.loglik_history[30] > model.loglik_history[0] + 0.5,
        "baum_welch loglik strictly improves from random init",
        passed,
        failed,
    )

    # Trained parameters remain valid distributions.
    var stochastic = True
    for i in range(2):
        if not _close(_row_sum(model.a[i]), 1.0, 1e-9):
            stochastic = False
        if not _close(_row_sum(model.b[i]), 1.0, 1e-9):
            stochastic = False
    if not _close(_row_sum(model.pi), 1.0, 1e-9):
        stochastic = False
    check(
        stochastic,
        "baum_welch A/B rows and pi sum to 1",
        passed,
        failed,
    )

    # Scaled loglik agrees with the log-space forward on the trained model.
    var refwd = hmm_forward(tobs, model.a, model.b, model.pi)
    check(
        _close(refwd.loglik, model.loglik_history[30], 1e-9),
        "baum_welch final loglik matches hmm_forward",
        passed,
        failed,
    )

    # Determinism: same seed -> identical history.
    var model2 = hmm_baum_welch(tobs, 2, 2, 30, 7)
    var same = len(model2.loglik_history) == len(model.loglik_history)
    if same:
        for k in range(len(model.loglik_history)):
            if model2.loglik_history[k] != model.loglik_history[k]:
                same = False
    check(same, "baum_welch deterministic for fixed seed", passed, failed)

    # ── hmm_baum_welch: degenerate inputs ────────────────────────────────────
    var m_empty = hmm_baum_welch(obs0, 2, 2, 10, 3)
    check(
        len(m_empty.loglik_history) == 0
        and len(m_empty.a) == 2
        and _close(_row_sum(m_empty.pi), 1.0, 1e-12),
        "baum_welch empty obs -> seeded init, empty history",
        passed,
        failed,
    )
    var m_zero = hmm_baum_welch(tobs, 0, 2, 10, 3)
    check(
        len(m_zero.a) == 0 and len(m_zero.loglik_history) == 0,
        "baum_welch n_states=0 -> empty model",
        passed,
        failed,
    )
    var bad_obs = List[Int]()
    bad_obs.append(0)
    bad_obs.append(5)
    var m_bad = hmm_baum_welch(bad_obs, 2, 2, 10, 3)
    check(
        len(m_bad.loglik_history) == 0,
        "baum_welch out-of-range symbol -> empty history",
        passed,
        failed,
    )

    # ── hmm_baum_welch: all-equal observations still valid ───────────────────
    var same_obs = List[Int]()
    for _ in range(12):
        same_obs.append(1)
    var m_same = hmm_baum_welch(same_obs, 2, 2, 10, 11)
    var m_same_monotone = True
    for k in range(1, len(m_same.loglik_history)):
        if m_same.loglik_history[k] < m_same.loglik_history[k - 1] - 1e-9:
            m_same_monotone = False
    check(
        m_same_monotone
        and _close(m_same.loglik_history[len(m_same.loglik_history) - 1], 0.0, 1e-6),
        "baum_welch all-equal obs -> loglik -> 0 (prob -> 1), monotone",
        passed,
        failed,
    )

    print("  [hmm] Passed:", passed, "Failed:", failed)
