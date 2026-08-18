"""
hmm.mojo — Hidden Markov models with training. Zero Python imports.

Replaces hmmlearn (MultinomialHMM) and pomegranate discrete HMMs. Fills the
HMM gap: markov.mojo covers observed chains only; this kernel adds hidden
states with discrete emissions — log-space forward/backward inference,
Viterbi decoding, and Baum-Welch (EM) parameter estimation.

Conventions: a[i][j] = P(state i -> state j) (n_states x n_states, rows sum
to 1); b[i][k] = P(symbol k | state i) (n_states x n_symbols, rows sum to 1);
pi[i] = P(initial state i). Observations are symbol indices in
[0, n_symbols).

Public API:
  hmm_forward     — log-space forward pass: log-alpha matrix + log-likelihood
  hmm_backward    — log-space backward pass: log-beta matrix
  hmm_viterbi     — most likely hidden state path (log-space DP)
  hmm_baum_welch  — EM training from observations (seeded random init) ->
                    HMMModel(a, b, pi, loglik_history)
"""

from std.math import frexp, ldexp


# Log-space stand-in for log(0): large-magnitude finite negative so sums of
# a few such terms never overflow to -inf / NaN.
comptime _LOG_ZERO: Float64 = -1.0e18

# ln(2) split into high/low parts (fdlibm) for accurate range reduction.
comptime _LN2_HI: Float64 = 6.93147180369123816490e-01
comptime _LN2_LO: Float64 = 1.90821492927058770002e-10
comptime _LN2: Float64 = 0.6931471805599453


# ── result structs ───────────────────────────────────────────────────────────


struct HMMForward(Copyable, Movable):
    """Forward-pass result: log_alpha[t][i] = log P(o_0..o_t, x_t = i)."""
    var log_alpha: List[List[Float64]]
    var loglik: Float64

    def __init__(out self):
        self.log_alpha = List[List[Float64]]()
        self.loglik = 0.0


struct HMMModel(Copyable, Movable):
    """Trained HMM: transition a, emission b, initial pi, per-iteration loglik.

    loglik_history[k] is the data log-likelihood under the parameters after
    k Baum-Welch updates (entry 0 = random init), so it has max_iter + 1
    entries and is monotone non-decreasing (EM guarantee).
    """
    var a: List[List[Float64]]
    var b: List[List[Float64]]
    var pi: List[Float64]
    var loglik_history: List[Float64]

    def __init__(out self):
        self.a = List[List[Float64]]()
        self.b = List[List[Float64]]()
        self.pi = List[Float64]()
        self.loglik_history = List[Float64]()


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


def _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


def _seed_state(seed: Int) -> UInt64:
    """Expand an Int seed into a warmed-up nonzero xorshift64 state."""
    var base: UInt64
    if seed < 0:
        base = UInt64(-(seed + 1)) + 1
    else:
        base = UInt64(seed)
    var s = base ^ UInt64(0x9E3779B97F4A7C15)
    if s == 0:
        s = UInt64(0x9E3779B97F4A7C15)
    s = _xorshift64(s)
    s = _xorshift64(s)
    s = _xorshift64(s)
    return s


def _rand_unit(mut state: UInt64) -> Float64:
    """Uniform Float64 in [0, 1) from the caller's RNG state (53-bit)."""
    state = _xorshift64(state)
    return Float64(state >> 11) / 9007199254740992.0


# ── numeric helpers ──────────────────────────────────────────────────────────
# std.math log/exp in this toolchain are fast approximations (~1e-10 absolute
# error), too coarse for log-likelihoods that gate decisions; _ln/_exp below
# are accurate to ~1e-15 relative via exact frexp/ldexp range reduction.


def _ln(x: Float64) -> Float64:
    """Natural log, ~1 ulp: frexp reduction + atanh series on [sqrt.5, sqrt2).

    ln(m) = 2*atanh(t), t = (m-1)/(m+1), |t| <= 0.1716; degree-10 Horner in
    t^2 leaves relative error ~2e-17. Caller guarantees x > 0 (_log_safe).
    """
    var fr = frexp(x)
    var m = fr[0]  # in [0.5, 1); x = m * 2^e exactly
    var e = fr[1]
    if m < 0.7071067811865476:
        m *= 2.0
        e -= 1.0
    var t = (m - 1.0) / (m + 1.0)
    var p = t * t
    var s = 1.0 / 21.0
    s = s * p + 1.0 / 19.0
    s = s * p + 1.0 / 17.0
    s = s * p + 1.0 / 15.0
    s = s * p + 1.0 / 13.0
    s = s * p + 1.0 / 11.0
    s = s * p + 1.0 / 9.0
    s = s * p + 1.0 / 7.0
    s = s * p + 1.0 / 5.0
    s = s * p + 1.0 / 3.0
    s = s * p + 1.0
    return Float64(e) * _LN2_HI + (2.0 * t * s + Float64(e) * _LN2_LO)


def _exp(x: Float64) -> Float64:
    """exp(x), ~1 ulp: k = round(x/ln2), split-ln2 reduction + Taylor on r.

    |r| <= ln2/2 = 0.3466; degree-14 Horner leaves relative error ~4e-18.
    """
    if x <= -745.0:
        return 0.0
    if x >= 709.0:
        return 1.0e308 * 10.0  # overflow -> inf, matches exp semantics
    var kf = x / _LN2
    var k: Int
    if kf >= 0.0:
        k = Int(kf + 0.5)
    else:
        k = -Int(-kf + 0.5)
    var r = (x - Float64(k) * _LN2_HI) - Float64(k) * _LN2_LO
    var s = 1.0 / 87178291200.0  # 1/14!
    s = s * r + 1.0 / 6227020800.0  # 1/13!
    s = s * r + 1.0 / 479001600.0  # 1/12!
    s = s * r + 1.0 / 39916800.0  # 1/11!
    s = s * r + 1.0 / 3628800.0  # 1/10!
    s = s * r + 1.0 / 362880.0  # 1/9!
    s = s * r + 1.0 / 40320.0  # 1/8!
    s = s * r + 1.0 / 5040.0  # 1/7!
    s = s * r + 1.0 / 720.0  # 1/6!
    s = s * r + 1.0 / 120.0  # 1/5!
    s = s * r + 1.0 / 24.0  # 1/4!
    s = s * r + 1.0 / 6.0  # 1/3!
    s = s * r + 0.5
    s = s * r + 1.0
    s = s * r + 1.0
    return ldexp(s, Int32(k))  # Mojo 1.0.0: ldexp exponent is Int32


def _log_safe(x: Float64) -> Float64:
    """log(x) with log(<=0) and non-finite x mapped to the finite _LOG_ZERO
    sentinel (NaN/inf probabilities must not reach the result wire)."""
    if x <= 0.0 or x - x != 0.0:
        return _LOG_ZERO
    return _ln(x)


def _logsumexp(vals: List[Float64]) -> Float64:
    """Numerically stable log(sum(exp(vals))); _LOG_ZERO if empty/all-zero."""
    var n = len(vals)
    if n == 0:
        return _LOG_ZERO
    var m = vals[0]
    for i in range(1, n):
        if vals[i] > m:
            m = vals[i]
    if m <= _LOG_ZERO * 0.5:
        return _LOG_ZERO
    var s = 0.0
    for i in range(n):
        s += _exp(vals[i] - m)
    return m + _ln(s)


def _log_matrix(m: List[List[Float64]]) -> List[List[Float64]]:
    """Element-wise _log_safe of a probability matrix (precomputed once)."""
    var out = List[List[Float64]](capacity=len(m))
    for i in range(len(m)):
        var row = List[Float64](capacity=len(m[i]))
        for j in range(len(m[i])):
            row.append(_log_safe(m[i][j]))
        out.append(row^)
    return out^


def _log_emit(log_b: List[List[Float64]], state: Int, symbol: Int) -> Float64:
    """log_b[state][symbol]; out-of-range states/symbols emit with probability 0."""
    if state < 0 or state >= len(log_b):
        return _LOG_ZERO
    if symbol < 0 or symbol >= len(log_b[state]):
        return _LOG_ZERO
    return log_b[state][symbol]


def _zeros_matrix(rows: Int, cols: Int) -> List[List[Float64]]:
    var m = List[List[Float64]](capacity=rows)
    for _ in range(rows):
        var row = List[Float64](capacity=cols)
        for _ in range(cols):
            row.append(0.0)
        m.append(row^)
    return m^


def _random_stochastic_row(cols: Int, mut rng: UInt64) -> List[Float64]:
    """Random row of positive probabilities summing to 1 (uniform + noise)."""
    var row = List[Float64](capacity=cols)
    var total = 0.0
    for _ in range(cols):
        var v = 1.0 + _rand_unit(rng)
        row.append(v)
        total += v
    for j in range(cols):
        row[j] /= total
    return row^


# ── hmm_forward ──────────────────────────────────────────────────────────────


def hmm_forward(
    obs: List[Int],
    a: List[List[Float64]],
    b: List[List[Float64]],
    pi: List[Float64],
) -> HMMForward:
    """Log-space forward algorithm.

    Returns log_alpha (T x n_states) with
    log_alpha[t][i] = log P(o_0..o_t, x_t = i), and
    loglik = log P(o_0..o_{T-1}) = logsumexp_i(log_alpha[T-1][i]).
    Empty obs -> empty log_alpha, loglik = 0 (log of the empty product).
    """
    var out = HMMForward()
    var t_len = len(obs)
    var n = len(pi)
    if t_len == 0 or n == 0:
        return out^
    # a must have n rows of at least n entries and b at least n rows: both
    # are indexed by state below, and a short row is an uncatchable abort.
    if len(a) < n or len(b) < n:
        return out^
    for i in range(n):
        if len(a[i]) < n:
            return out^

    var log_a = _log_matrix(a)
    var log_b = _log_matrix(b)

    var first = List[Float64](capacity=n)
    for i in range(n):
        first.append(_log_safe(pi[i]) + _log_emit(log_b, i, obs[0]))
    out.log_alpha.append(first^)

    var scratch = List[Float64](capacity=n)
    for _ in range(n):
        scratch.append(0.0)

    for t in range(1, t_len):
        var row = List[Float64](capacity=n)
        for j in range(n):
            for i in range(n):
                scratch[i] = out.log_alpha[t - 1][i] + log_a[i][j]
            row.append(_logsumexp(scratch) + _log_emit(log_b, j, obs[t]))
        out.log_alpha.append(row^)

    var last = List[Float64](capacity=n)
    for i in range(n):
        last.append(out.log_alpha[t_len - 1][i])
    out.loglik = _logsumexp(last)
    return out^


# ── hmm_backward ─────────────────────────────────────────────────────────────


def hmm_backward(
    obs: List[Int],
    a: List[List[Float64]],
    b: List[List[Float64]],
    pi: List[Float64],
) -> List[List[Float64]]:
    """Log-space backward algorithm.

    Returns log_beta (T x n_states) with
    log_beta[t][i] = log P(o_{t+1}..o_{T-1} | x_t = i); the last row is all
    zeros (log 1). pi is unused by the recursion but kept so the signature
    mirrors hmm_forward. Empty obs -> empty matrix.
    """
    _ = pi
    var out = List[List[Float64]]()
    var t_len = len(obs)
    var n = len(a)
    if t_len == 0 or n == 0:
        return out^
    # Each a row is indexed up to n-1 below and b is indexed by state; short
    # rows are an uncatchable abort.
    if len(b) < n:
        return out^
    for i in range(n):
        if len(a[i]) < n:
            return out^

    var log_a = _log_matrix(a)
    var log_b = _log_matrix(b)

    for _ in range(t_len):
        var row = List[Float64](capacity=n)
        for _ in range(n):
            row.append(0.0)
        out.append(row^)

    var scratch = List[Float64](capacity=n)
    for _ in range(n):
        scratch.append(0.0)

    for t in range(t_len - 2, -1, -1):
        for i in range(n):
            for j in range(n):
                scratch[j] = (
                    log_a[i][j] + _log_emit(log_b, j, obs[t + 1]) + out[t + 1][j]
                )
            out[t][i] = _logsumexp(scratch)
    return out^


# ── hmm_viterbi ──────────────────────────────────────────────────────────────


def hmm_viterbi(
    obs: List[Int],
    a: List[List[Float64]],
    b: List[List[Float64]],
    pi: List[Float64],
) -> List[Int]:
    """Most likely hidden state path (log-space Viterbi DP with backpointers).

    Returns a length-T list of state indices; empty obs -> empty path.
    Ties break toward the lower state index (strict > comparison).
    """
    var path = List[Int]()
    var t_len = len(obs)
    var n = len(pi)
    if t_len == 0 or n == 0:
        return path^
    # a must have n rows of at least n entries and b at least n rows: both
    # are indexed by state below, and a short row is an uncatchable abort.
    if len(a) < n or len(b) < n:
        return path^
    for i in range(n):
        if len(a[i]) < n:
            return path^

    var log_a = _log_matrix(a)
    var log_b = _log_matrix(b)

    var delta = List[Float64](capacity=n)
    for i in range(n):
        delta.append(_log_safe(pi[i]) + _log_emit(log_b, i, obs[0]))

    # back[t][j] = argmax_i predecessor of state j at time t (t >= 1).
    var back = List[List[Int]]()
    for t in range(1, t_len):
        var next_delta = List[Float64](capacity=n)
        var back_row = List[Int](capacity=n)
        for j in range(n):
            var best_i = 0
            var best = delta[0] + log_a[0][j]
            for i in range(1, n):
                var cand = delta[i] + log_a[i][j]
                if cand > best:
                    best = cand
                    best_i = i
            next_delta.append(best + _log_emit(log_b, j, obs[t]))
            back_row.append(best_i)
        back.append(back_row^)
        delta = next_delta^

    var last = 0
    for i in range(1, n):
        if delta[i] > delta[last]:
            last = i

    var rev = List[Int](capacity=t_len)
    rev.append(last)
    for t in range(t_len - 2, -1, -1):
        last = back[t][last]
        rev.append(last)
    for k in range(t_len - 1, -1, -1):
        path.append(rev[k])
    return path^


# ── hmm_baum_welch ───────────────────────────────────────────────────────────


def hmm_baum_welch(
    obs: List[Int],
    n_states: Int,
    n_symbols: Int,
    max_iter: Int,
    seed: Int,
) -> HMMModel:
    """Baum-Welch (EM) training of a discrete-emission HMM.

    Parameters start at seeded random row-stochastic matrices (deterministic
    for a given seed), then run max_iter E-M updates using the scaled
    forward-backward recursions (Rabiner scaling — linear space, no
    underflow for long sequences). loglik_history has max_iter + 1 entries:
    the log-likelihood at init and after each update; the EM guarantee makes
    it monotone non-decreasing. States whose expected occupancy is zero keep
    their previous rows (guards 0/0 without breaking monotonicity).

    Degenerate inputs (empty obs, non-positive dims, or any symbol outside
    [0, n_symbols)) return the seeded initial model with an empty history.
    """
    var model = HMMModel()
    if n_states <= 0 or n_symbols <= 0:
        return model^

    var rng = _seed_state(seed)
    for _ in range(n_states):
        model.a.append(_random_stochastic_row(n_states, rng))
    for _ in range(n_states):
        model.b.append(_random_stochastic_row(n_symbols, rng))
    model.pi = _random_stochastic_row(n_states, rng)

    var t_len = len(obs)
    if t_len == 0:
        return model^
    for t in range(t_len):
        if obs[t] < 0 or obs[t] >= n_symbols:
            return model^

    var n = n_states
    var alpha = _zeros_matrix(t_len, n)
    var beta = _zeros_matrix(t_len, n)
    var scale = List[Float64](capacity=t_len)
    for _ in range(t_len):
        scale.append(0.0)

    for _ in range(max_iter):
        var ll = _scaled_forward(obs, model.a, model.b, model.pi, alpha, scale)
        model.loglik_history.append(ll)
        _scaled_backward(obs, model.a, model.b, scale, beta)
        _reestimate(obs, n, n_symbols, alpha, beta, scale, model)

    var final_ll = _scaled_forward(
        obs, model.a, model.b, model.pi, alpha, scale
    )
    model.loglik_history.append(final_ll)
    return model^


# ── Baum-Welch internals (scaled forward-backward) ───────────────────────────


def _scaled_forward(
    obs: List[Int],
    a: List[List[Float64]],
    b: List[List[Float64]],
    pi: List[Float64],
    mut alpha: List[List[Float64]],
    mut scale: List[Float64],
) -> Float64:
    """Rabiner-scaled forward pass into preallocated alpha/scale.

    alpha[t][i] = P(x_t = i | o_0..o_t) (each row sums to 1);
    scale[t] = P(o_t | o_0..o_{t-1}). Returns sum(log(scale)) = loglik.
    """
    var t_len = len(obs)
    var n = len(pi)
    var ll = 0.0

    var c0 = 0.0
    for i in range(n):
        var v = pi[i] * b[i][obs[0]]
        alpha[0][i] = v
        c0 += v
    scale[0] = c0
    if c0 <= 0.0:
        return _LOG_ZERO
    for i in range(n):
        alpha[0][i] /= c0
    ll += _ln(c0)

    for t in range(1, t_len):
        var ct = 0.0
        for j in range(n):
            var s = 0.0
            for i in range(n):
                s += alpha[t - 1][i] * a[i][j]
            var v = s * b[j][obs[t]]
            alpha[t][j] = v
            ct += v
        scale[t] = ct
        if ct <= 0.0:
            return _LOG_ZERO
        for j in range(n):
            alpha[t][j] /= ct
        ll += _ln(ct)
    return ll


def _scaled_backward(
    obs: List[Int],
    a: List[List[Float64]],
    b: List[List[Float64]],
    scale: List[Float64],
    mut beta: List[List[Float64]],
):
    """Rabiner-scaled backward pass into preallocated beta.

    Uses the forward scale factors so that alpha[t][i] * beta[t][i] equals
    the posterior gamma[t][i] directly.
    """
    var t_len = len(obs)
    var n = len(a)
    for i in range(n):
        beta[t_len - 1][i] = 1.0
    for t in range(t_len - 2, -1, -1):
        var c_next = scale[t + 1]
        for i in range(n):
            var s = 0.0
            for j in range(n):
                s += a[i][j] * b[j][obs[t + 1]] * beta[t + 1][j]
            if c_next > 0.0:
                beta[t][i] = s / c_next
            else:
                beta[t][i] = 0.0


def _reestimate(
    obs: List[Int],
    n: Int,
    n_symbols: Int,
    alpha: List[List[Float64]],
    beta: List[List[Float64]],
    scale: List[Float64],
    mut model: HMMModel,
):
    """M-step: update model.a / model.b / model.pi from the scaled passes.

    gamma[t][i] = alpha[t][i] * beta[t][i];
    xi[t][i][j] = alpha[t][i] * a[i][j] * b[j][o_{t+1}] * beta[t+1][j] / c_{t+1}.
    xi and the emission counts are accumulated in place (no T x N x N
    storage). Zero-occupancy states keep their previous rows.
    """
    var t_len = len(obs)

    var a_num = _zeros_matrix(n, n)
    var a_den = List[Float64](capacity=n)
    var b_num = _zeros_matrix(n, n_symbols)
    var b_den = List[Float64](capacity=n)
    for _ in range(n):
        a_den.append(0.0)
        b_den.append(0.0)

    for t in range(t_len):
        var last_step = t == t_len - 1
        for i in range(n):
            var g = alpha[t][i] * beta[t][i]
            b_num[i][obs[t]] += g
            b_den[i] += g
            if not last_step:
                a_den[i] += g
                var c_next = scale[t + 1]
                if c_next > 0.0:
                    for j in range(n):
                        a_num[i][j] += (
                            alpha[t][i]
                            * model.a[i][j]
                            * model.b[j][obs[t + 1]]
                            * beta[t + 1][j]
                            / c_next
                        )

    for i in range(n):
        model.pi[i] = alpha[0][i] * beta[0][i]
        if a_den[i] > 0.0:
            for j in range(n):
                model.a[i][j] = a_num[i][j] / a_den[i]
        if b_den[i] > 0.0:
            for k in range(n_symbols):
                model.b[i][k] = b_num[i][k] / b_den[i]
