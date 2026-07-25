"""
seq_training.mojo — Sequence model training loop: BPTT over windows. Zero Python imports.

Replaces torch/keras LSTM training loops (nn.LSTM + Adam + clip_grad_norm_)
for small univariate/low-dimensional sequence forecasting. Builds sliding
windows from a series, trains a single-layer LSTM end-to-end with full
backpropagation-through-time, MSE loss, global-norm gradient clipping, and a
locally implemented Adam-style optimizer. Deterministic given the seed.

Public API:
  WindowedDataset    — struct: x (flat windows), y (targets), n_windows, window_len
  TrainResult        — struct: weights (flat), loss_history (one MSE per epoch)
  make_windows       — series -> sliding lookback windows + forward targets
  lstm_weight_count  — number of flat weights for (input_dim, hidden)
  bptt_train_lstm    — full-batch BPTT training of a 1-layer LSTM + linear head
  lstm_predict       — run trained flat weights over one window -> Float64
"""

from std.math import sqrt, exp, tanh, abs as fabs


# ── result structs ───────────────────────────────────────────────────────────


struct WindowedDataset(Copyable, Movable):
    """Sliding-window dataset: x holds n_windows blocks of window_len floats
    (window i occupies x[i*window_len : (i+1)*window_len]); y[i] is the value
    `forward` steps after the end of window i."""
    var x: List[Float64]
    var y: List[Float64]
    var n_windows: Int
    var window_len: Int

    fn __init__(out self):
        self.x = List[Float64]()
        self.y = List[Float64]()
        self.n_windows = 0
        self.window_len = 0


struct TrainResult(Copyable, Movable):
    """Training output: flat LSTM weights + per-epoch mean MSE (loss measured
    with the weights at the start of each epoch, before that epoch's update)."""
    var weights: List[Float64]
    var loss_history: List[Float64]

    fn __init__(out self):
        self.weights = List[Float64]()
        self.loss_history = List[Float64]()


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


fn _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


fn _seed_state(seed: Int) -> UInt64:
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


fn _rand_unit(mut state: UInt64) -> Float64:
    """Uniform Float64 in [0, 1) from the caller's RNG state."""
    state = _xorshift64(state)
    return Float64(state >> 11) / 9007199254740992.0


# ── math helpers ─────────────────────────────────────────────────────────────


fn _sigmoid(x: Float64) -> Float64:
    if x >= 0.0:
        return 1.0 / (1.0 + exp(-x))
    var e = exp(x)
    return e / (1.0 + e)


# ── make_windows ─────────────────────────────────────────────────────────────


fn make_windows(
    series: List[Float64], lookback: Int, forward: Int
) -> WindowedDataset:
    """Slide a lookback window over `series` with a forward-step target.

    Window i is series[i : i + lookback] (flattened contiguously into x);
    its target y[i] is series[i + lookback - 1 + forward]. Yields
    n - lookback - forward + 1 windows. Returns an empty dataset when
    lookback <= 0, forward <= 0, or the series is too short for one window.
    """
    var out = WindowedDataset()
    var n = len(series)
    if lookback <= 0 or forward <= 0:
        return out^
    var count = n - lookback - forward + 1
    if count <= 0:
        return out^
    out.n_windows = count
    out.window_len = lookback
    out.x = List[Float64](capacity=count * lookback)
    out.y = List[Float64](capacity=count)
    for i in range(count):
        for j in range(lookback):
            out.x.append(series[i + j])
        out.y.append(series[i + lookback - 1 + forward])
    return out^


# ── weight layout ────────────────────────────────────────────────────────────
#
# Flat layout for input_dim=D, hidden=H (gates ordered i, f, g, o; each gate
# block is W_x (H*D, row-major), then W_h (H*H, row-major), then b (H)):
#   [gate i block][gate f block][gate g block][gate o block][w_y (H)][b_y (1)]


fn lstm_weight_count(input_dim: Int, hidden: Int) -> Int:
    """Length of the flat weight vector for a 1-layer LSTM + linear head."""
    if input_dim <= 0 or hidden <= 0:
        return 0
    return 4 * (hidden * input_dim + hidden * hidden + hidden) + hidden + 1


fn _gate_block(input_dim: Int, hidden: Int) -> Int:
    return hidden * input_dim + hidden * hidden + hidden


# ── forward + backward over one window ───────────────────────────────────────


fn _lstm_forward(
    w: List[Float64],
    x_flat: List[Float64],
    x_off: Int,
    steps: Int,
    input_dim: Int,
    hidden: Int,
    mut gates: List[Float64],
    mut hs: List[Float64],
    mut cs: List[Float64],
) -> Float64:
    """Run the LSTM over one window; fill per-step caches, return y_hat.

    gates: steps*4*hidden activations (i, f, g, o per step);
    hs/cs: (steps+1)*hidden hidden/cell states (row 0 is the zero initial state).
    """
    var D = input_dim
    var H = hidden
    var block = _gate_block(D, H)
    var head = 4 * block
    for k in range(H):
        hs[k] = 0.0
        cs[k] = 0.0
    for t in range(steps):
        var hprev = t * H
        for g in range(4):
            var base = g * block
            for r in range(H):
                var acc = w[base + H * D + H * H + r]  # bias
                var wx = base + r * D
                for d in range(D):
                    acc += w[wx + d] * x_flat[x_off + t * D + d]
                var wh = base + H * D + r * H
                for k in range(H):
                    acc += w[wh + k] * hs[hprev + k]
                var idx = (t * 4 + g) * H + r
                if g == 2:
                    gates[idx] = tanh(acc)  # candidate g
                else:
                    gates[idx] = _sigmoid(acc)  # i, f, o
        var hcur = (t + 1) * H
        for r in range(H):
            var gi = gates[(t * 4 + 0) * H + r]
            var gf = gates[(t * 4 + 1) * H + r]
            var gg = gates[(t * 4 + 2) * H + r]
            var go = gates[(t * 4 + 3) * H + r]
            var c = gf * cs[hprev + r] + gi * gg
            cs[hcur + r] = c
            hs[hcur + r] = go * tanh(c)
    var y_hat = w[head + H]  # b_y
    for r in range(H):
        y_hat += w[head + r] * hs[steps * H + r]
    return y_hat


fn _lstm_backward(
    w: List[Float64],
    x_flat: List[Float64],
    x_off: Int,
    steps: Int,
    input_dim: Int,
    hidden: Int,
    gates: List[Float64],
    hs: List[Float64],
    cs: List[Float64],
    dy: Float64,
    mut grad: List[Float64],
):
    """Accumulate full-BPTT gradients for one window into `grad`.

    dy is dL/dy_hat for this window; caches come from _lstm_forward.
    """
    var D = input_dim
    var H = hidden
    var block = _gate_block(D, H)
    var head = 4 * block

    var dh = List[Float64](capacity=H)
    var dc = List[Float64](capacity=H)
    var dh_prev = List[Float64](capacity=H)
    var da = List[Float64](capacity=4 * H)
    for _ in range(H):
        dh.append(0.0)
        dc.append(0.0)
        dh_prev.append(0.0)
    for _ in range(4 * H):
        da.append(0.0)

    # Head: y_hat = w_y . h_T + b_y
    grad[head + H] += dy
    for r in range(H):
        grad[head + r] += dy * hs[steps * H + r]
        dh[r] = dy * w[head + r]

    for t in range(steps - 1, -1, -1):
        var hprev = t * H
        var hcur = (t + 1) * H
        for r in range(H):
            var gi = gates[(t * 4 + 0) * H + r]
            var gf = gates[(t * 4 + 1) * H + r]
            var gg = gates[(t * 4 + 2) * H + r]
            var go = gates[(t * 4 + 3) * H + r]
            var tc = tanh(cs[hcur + r])
            var dct = dc[r] + dh[r] * go * (1.0 - tc * tc)
            da[0 * H + r] = dct * gg * gi * (1.0 - gi)  # i pre-act
            da[1 * H + r] = dct * cs[hprev + r] * gf * (1.0 - gf)  # f pre-act
            da[2 * H + r] = dct * gi * (1.0 - gg * gg)  # g pre-act
            da[3 * H + r] = dh[r] * tc * go * (1.0 - go)  # o pre-act
            dc[r] = dct * gf
        for r in range(H):
            dh_prev[r] = 0.0
        for g in range(4):
            var base = g * block
            for r in range(H):
                var d_pre = da[g * H + r]
                if d_pre == 0.0:
                    continue
                var wx = base + r * D
                for d in range(D):
                    grad[wx + d] += d_pre * x_flat[x_off + t * D + d]
                var wh = base + H * D + r * H
                for k in range(H):
                    grad[wh + k] += d_pre * hs[hprev + k]
                    dh_prev[k] += d_pre * w[wh + k]
                grad[base + H * D + H * H + r] += d_pre
        for r in range(H):
            dh[r] = dh_prev[r]


# ── bptt_train_lstm ──────────────────────────────────────────────────────────


fn bptt_train_lstm(
    x_flat: List[Float64],
    y: List[Float64],
    input_dim: Int,
    hidden: Int,
    epochs: Int,
    lr: Float64,
    seed: Int,
    clip_norm: Float64,
) -> TrainResult:
    """Train a 1-layer LSTM + linear head with full-batch BPTT and Adam.

    x_flat holds len(y) windows of equal length (len(x_flat) / len(y) floats
    each; that length must be a multiple of input_dim — timesteps per window
    = window_len / input_dim). Loss is mean squared error over all windows.
    Per epoch: forward + full BPTT on every window, gradients averaged,
    global-L2-norm clipped to clip_norm (clip_norm <= 0 disables clipping),
    then an Adam update (beta1=0.9, beta2=0.999, eps=1e-8, bias-corrected)
    implemented locally. Weights are seeded uniform in ±0.5/sqrt(hidden) with
    the forget-gate bias initialised to 1.0; fully deterministic given seed.
    loss_history[e] is the mean MSE measured at the start of epoch e.
    Returns the seeded initial weights and empty history when epochs <= 0;
    returns an empty result on invalid shapes.
    """
    var out = TrainResult()
    var n_win = len(y)
    if input_dim <= 0 or hidden <= 0 or n_win <= 0:
        return out^
    if len(x_flat) % n_win != 0:
        return out^
    var window_len = len(x_flat) // n_win
    if window_len <= 0 or window_len % input_dim != 0:
        return out^
    var steps = window_len // input_dim

    var D = input_dim
    var H = hidden
    var block = _gate_block(D, H)
    var n_w = lstm_weight_count(D, H)

    # ── seeded init: uniform ±0.5/sqrt(H); forget-gate bias = 1.0 ────────────
    var rng = _seed_state(seed)
    var scale = 0.5 / sqrt(Float64(H))
    var w = List[Float64](capacity=n_w)
    for _ in range(n_w):
        w.append((2.0 * _rand_unit(rng) - 1.0) * scale)
    for r in range(H):
        w[1 * block + H * D + H * H + r] = 1.0  # forget-gate bias

    if epochs <= 0:
        out.weights = w^
        return out^

    # ── Adam state ───────────────────────────────────────────────────────────
    var m = List[Float64](capacity=n_w)
    var v = List[Float64](capacity=n_w)
    var grad = List[Float64](capacity=n_w)
    for _ in range(n_w):
        m.append(0.0)
        v.append(0.0)
        grad.append(0.0)
    var beta1 = 0.9
    var beta2 = 0.999
    var eps = 1e-8
    var b1t = 1.0
    var b2t = 1.0

    # per-window caches, reused across windows/epochs
    var gates = List[Float64](capacity=steps * 4 * H)
    var hs = List[Float64](capacity=(steps + 1) * H)
    var cs = List[Float64](capacity=(steps + 1) * H)
    for _ in range(steps * 4 * H):
        gates.append(0.0)
    for _ in range((steps + 1) * H):
        hs.append(0.0)
        cs.append(0.0)

    out.loss_history = List[Float64](capacity=epochs)
    var inv_n = 1.0 / Float64(n_win)

    for _ in range(epochs):
        for j in range(n_w):
            grad[j] = 0.0
        var loss = 0.0
        for i in range(n_win):
            var x_off = i * window_len
            var y_hat = _lstm_forward(
                w, x_flat, x_off, steps, D, H, gates, hs, cs
            )
            var err = y_hat - y[i]
            loss += err * err
            # d(mean MSE)/dy_hat_i = 2 * err / n_win
            _lstm_backward(
                w, x_flat, x_off, steps, D, H, gates, hs, cs,
                2.0 * err * inv_n, grad,
            )
        out.loss_history.append(loss * inv_n)

        # global-norm clip
        if clip_norm > 0.0:
            var sq = 0.0
            for j in range(n_w):
                sq += grad[j] * grad[j]
            var norm = sqrt(sq)
            if norm > clip_norm:
                var s = clip_norm / norm
                for j in range(n_w):
                    grad[j] *= s

        # Adam step (bias-corrected)
        b1t *= beta1
        b2t *= beta2
        var corr1 = 1.0 - b1t
        var corr2 = 1.0 - b2t
        for j in range(n_w):
            m[j] = beta1 * m[j] + (1.0 - beta1) * grad[j]
            v[j] = beta2 * v[j] + (1.0 - beta2) * grad[j] * grad[j]
            var m_hat = m[j] / corr1
            var v_hat = v[j] / corr2
            w[j] -= lr * m_hat / (sqrt(v_hat) + eps)

    out.weights = w^
    return out^


# ── lstm_predict ─────────────────────────────────────────────────────────────


fn lstm_predict(
    weights: List[Float64], window: List[Float64], input_dim: Int, hidden: Int
) -> Float64:
    """Run flat LSTM weights over one window; return the head's scalar output.

    window length must be a positive multiple of input_dim and weights must
    have exactly lstm_weight_count(input_dim, hidden) entries; returns 0.0
    otherwise. Deterministic: zero initial hidden/cell state, identical
    recurrence to training.
    """
    var D = input_dim
    var H = hidden
    if D <= 0 or H <= 0:
        return 0.0
    if len(weights) != lstm_weight_count(D, H):
        return 0.0
    var wl = len(window)
    if wl <= 0 or wl % D != 0:
        return 0.0
    var steps = wl // D
    var gates = List[Float64](capacity=steps * 4 * H)
    var hs = List[Float64](capacity=(steps + 1) * H)
    var cs = List[Float64](capacity=(steps + 1) * H)
    for _ in range(steps * 4 * H):
        gates.append(0.0)
    for _ in range((steps + 1) * H):
        hs.append(0.0)
        cs.append(0.0)
    return _lstm_forward(weights, window, 0, steps, D, H, gates, hs, cs)
