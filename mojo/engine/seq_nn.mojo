"""
seq_nn.mojo — Recurrent cells (LSTM/GRU) with exact forward AND backward math.
Zero Python imports.

Replaces torch.nn.LSTMCell / torch.nn.GRUCell plus their autograd backward for
single-step sequence models; complements nn_layers.mojo (dense/activations,
which has no recurrence). Standard formulations: LSTM gates i,f,g,o with
sigmoid/sigmoid/tanh/sigmoid, c = f*c_prev + i*g, h = o*tanh(c). GRU (Cho
2014) gates r,z with candidate n = tanh(W_n x + U_n (r*h_prev) + b_n),
h = z*h_prev + (1-z)*n.

Weight layout: W stacked [n_gates*hidden x input] flattened row-major
(gate blocks in order i,f,g,o for LSTM; r,z,n for GRU), U stacked
[n_gates*hidden x hidden] row-major, b length n_gates*hidden.

Public API:
  lstm_cell_forward   — one LSTM step -> LSTMState (h, c + gate caches)
  lstm_cell_backward  — exact grads -> LSTMGrads (dx, dh_prev, dc_prev, dW, dU, db)
  gru_cell_forward    — one GRU step -> GRUState (h + gate caches)
  gru_cell_backward   — exact grads -> GRUGrads (dx, dh_prev, dW, dU, db)
  lstm_param_count    — 4*hidden*(input + hidden + 1)
  gru_param_count     — 3*hidden*(input + hidden + 1)
  xavier_flat         — seeded Xavier-uniform flat [rows x cols] matrix
  init_lstm_params    — seeded xavier W,U; b zero except forget-gate block = 1
  init_gru_params     — seeded xavier W,U; b zero
"""
from std.math import exp, sqrt, tanh


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
    """Uniform Float64 in [0, 1) from the caller's RNG state."""
    state = _xorshift64(state)
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)


# ── numerics ─────────────────────────────────────────────────────────────────


def _sigmoid(v: Float64) -> Float64:
    """Numerically stable logistic sigmoid."""
    if v >= 0.0:
        return 1.0 / (1.0 + exp(-v))
    var e = exp(v)
    return e / (1.0 + e)


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for _ in range(n):
        out.append(0.0)
    return out^


# ── result structs ───────────────────────────────────────────────────────────


struct LSTMState(Copyable, Movable):
    """LSTM step output + cache: h, c, gate activations, tanh(c)."""
    var h: List[Float64]
    var c: List[Float64]
    var i_gate: List[Float64]
    var f_gate: List[Float64]
    var g_gate: List[Float64]
    var o_gate: List[Float64]
    var c_tanh: List[Float64]

    def __init__(out self):
        self.h = List[Float64]()
        self.c = List[Float64]()
        self.i_gate = List[Float64]()
        self.f_gate = List[Float64]()
        self.g_gate = List[Float64]()
        self.o_gate = List[Float64]()
        self.c_tanh = List[Float64]()


struct LSTMGrads(Copyable, Movable):
    """LSTM backward result: input/state grads + flat parameter grads."""
    var dx: List[Float64]
    var dh_prev: List[Float64]
    var dc_prev: List[Float64]
    var dW: List[Float64]
    var dU: List[Float64]
    var db: List[Float64]

    def __init__(out self):
        self.dx = List[Float64]()
        self.dh_prev = List[Float64]()
        self.dc_prev = List[Float64]()
        self.dW = List[Float64]()
        self.dU = List[Float64]()
        self.db = List[Float64]()


struct GRUState(Copyable, Movable):
    """GRU step output + cache: h, gate activations, s = r*h_prev."""
    var h: List[Float64]
    var r_gate: List[Float64]
    var z_gate: List[Float64]
    var n_cand: List[Float64]
    var s_reset: List[Float64]

    def __init__(out self):
        self.h = List[Float64]()
        self.r_gate = List[Float64]()
        self.z_gate = List[Float64]()
        self.n_cand = List[Float64]()
        self.s_reset = List[Float64]()


struct GRUGrads(Copyable, Movable):
    """GRU backward result: input/state grads + flat parameter grads."""
    var dx: List[Float64]
    var dh_prev: List[Float64]
    var dW: List[Float64]
    var dU: List[Float64]
    var db: List[Float64]

    def __init__(out self):
        self.dx = List[Float64]()
        self.dh_prev = List[Float64]()
        self.dW = List[Float64]()
        self.dU = List[Float64]()
        self.db = List[Float64]()


struct RNNParams(Copyable, Movable):
    """Flat parameter bundle for one recurrent cell: W, U, b."""
    var W: List[Float64]
    var U: List[Float64]
    var b: List[Float64]

    def __init__(out self):
        self.W = List[Float64]()
        self.U = List[Float64]()
        self.b = List[Float64]()


# ── lstm_cell_forward ────────────────────────────────────────────────────────


def lstm_cell_forward(
    x: List[Float64],
    h_prev: List[Float64],
    c_prev: List[Float64],
    W_flat: List[Float64],
    U_flat: List[Float64],
    b: List[Float64],
    hidden: Int,
) -> LSTMState:
    """One LSTM cell step.

    i = sig(W_i x + U_i h_prev + b_i), f = sig(...), g = tanh(...),
    o = sig(...); c = f*c_prev + i*g; h = o*tanh(c). Gate blocks are
    stacked i,f,g,o: row (gate*hidden + k) of W_flat/U_flat/b drives
    unit k of that gate. Returns empty state if hidden <= 0 or sizes
    are inconsistent.
    """
    var out = LSTMState()
    var input_size = len(x)
    if hidden <= 0 or len(h_prev) != hidden or len(c_prev) != hidden:
        return out^
    var rows = 4 * hidden
    if (
        len(W_flat) != rows * input_size
        or len(U_flat) != rows * hidden
        or len(b) != rows
    ):
        return out^

    # Pre-activations for all 4*hidden gate rows.
    var pre = List[Float64](capacity=rows)
    for r in range(rows):
        var a = b[r]
        var wb = r * input_size
        for j in range(input_size):
            a += W_flat[wb + j] * x[j]
        var ub = r * hidden
        for j in range(hidden):
            a += U_flat[ub + j] * h_prev[j]
        pre.append(a)

    var i_gate = List[Float64](capacity=hidden)
    var f_gate = List[Float64](capacity=hidden)
    var g_gate = List[Float64](capacity=hidden)
    var o_gate = List[Float64](capacity=hidden)
    var c = List[Float64](capacity=hidden)
    var c_tanh = List[Float64](capacity=hidden)
    var h = List[Float64](capacity=hidden)
    for k in range(hidden):
        var iv = _sigmoid(pre[k])
        var fv = _sigmoid(pre[hidden + k])
        var gv = tanh(pre[2 * hidden + k])
        var ov = _sigmoid(pre[3 * hidden + k])
        var cv = fv * c_prev[k] + iv * gv
        var ct = tanh(cv)
        i_gate.append(iv)
        f_gate.append(fv)
        g_gate.append(gv)
        o_gate.append(ov)
        c.append(cv)
        c_tanh.append(ct)
        h.append(ov * ct)

    out.h = h^
    out.c = c^
    out.i_gate = i_gate^
    out.f_gate = f_gate^
    out.g_gate = g_gate^
    out.o_gate = o_gate^
    out.c_tanh = c_tanh^
    return out^


# ── lstm_cell_backward ───────────────────────────────────────────────────────


def lstm_cell_backward(
    dh: List[Float64],
    dc: List[Float64],
    cache: LSTMState,
    x: List[Float64],
    h_prev: List[Float64],
    c_prev: List[Float64],
    W_flat: List[Float64],
    U_flat: List[Float64],
    hidden: Int,
) -> LSTMGrads:
    """Exact LSTM cell backward for upstream grads dh (wrt h) and dc (wrt c).

    Uses the cache from lstm_cell_forward on the same (x, h_prev, c_prev,
    W_flat, U_flat). dW/dU/db use the same flattened layout as the forward
    parameters. Returns empty grads on inconsistent sizes.
    """
    var out = LSTMGrads()
    var input_size = len(x)
    if hidden <= 0 or len(dh) != hidden or len(dc) != hidden:
        return out^
    if len(h_prev) != hidden or len(c_prev) != hidden:
        return out^
    if len(cache.h) != hidden or len(cache.c_tanh) != hidden:
        return out^
    var rows = 4 * hidden
    if len(W_flat) != rows * input_size or len(U_flat) != rows * hidden:
        return out^

    # Pre-activation grads, stacked i,f,g,o (same layout as forward rows).
    var dpre = _zeros(rows)
    var dc_prev = List[Float64](capacity=hidden)
    for k in range(hidden):
        var iv = cache.i_gate[k]
        var fv = cache.f_gate[k]
        var gv = cache.g_gate[k]
        var ov = cache.o_gate[k]
        var ct = cache.c_tanh[k]
        # h = o * tanh(c): route dh into o and into c.
        var do_pre = dh[k] * ct * ov * (1.0 - ov)
        var dc_total = dc[k] + dh[k] * ov * (1.0 - ct * ct)
        # c = f*c_prev + i*g
        var di_pre = dc_total * gv * iv * (1.0 - iv)
        var df_pre = dc_total * c_prev[k] * fv * (1.0 - fv)
        var dg_pre = dc_total * iv * (1.0 - gv * gv)
        dpre[k] = di_pre
        dpre[hidden + k] = df_pre
        dpre[2 * hidden + k] = dg_pre
        dpre[3 * hidden + k] = do_pre
        dc_prev.append(dc_total * fv)

    var dW = List[Float64](capacity=rows * input_size)
    var dU = List[Float64](capacity=rows * hidden)
    var db = List[Float64](capacity=rows)
    for r in range(rows):
        var d = dpre[r]
        for j in range(input_size):
            dW.append(d * x[j])
        for j in range(hidden):
            dU.append(d * h_prev[j])
        db.append(d)

    var dx = _zeros(input_size)
    var dh_prev = _zeros(hidden)
    for r in range(rows):
        var d = dpre[r]
        var wb = r * input_size
        for j in range(input_size):
            dx[j] += W_flat[wb + j] * d
        var ub = r * hidden
        for j in range(hidden):
            dh_prev[j] += U_flat[ub + j] * d

    out.dx = dx^
    out.dh_prev = dh_prev^
    out.dc_prev = dc_prev^
    out.dW = dW^
    out.dU = dU^
    out.db = db^
    return out^


# ── gru_cell_forward ─────────────────────────────────────────────────────────


def gru_cell_forward(
    x: List[Float64],
    h_prev: List[Float64],
    W_flat: List[Float64],
    U_flat: List[Float64],
    b: List[Float64],
    hidden: Int,
) -> GRUState:
    """One GRU cell step (Cho 2014 formulation).

    r = sig(W_r x + U_r h_prev + b_r), z = sig(W_z x + U_z h_prev + b_z),
    n = tanh(W_n x + U_n (r*h_prev) + b_n), h = z*h_prev + (1-z)*n.
    Gate blocks are stacked r,z,n. Returns empty state if hidden <= 0
    or sizes are inconsistent.
    """
    var out = GRUState()
    var input_size = len(x)
    if hidden <= 0 or len(h_prev) != hidden:
        return out^
    var rows = 3 * hidden
    if (
        len(W_flat) != rows * input_size
        or len(U_flat) != rows * hidden
        or len(b) != rows
    ):
        return out^

    # r and z pre-activations (rows [0, 2*hidden)).
    var r_gate = List[Float64](capacity=hidden)
    var z_gate = List[Float64](capacity=hidden)
    for gate in range(2):
        for k in range(hidden):
            var r = gate * hidden + k
            var a = b[r]
            var wb = r * input_size
            for j in range(input_size):
                a += W_flat[wb + j] * x[j]
            var ub = r * hidden
            for j in range(hidden):
                a += U_flat[ub + j] * h_prev[j]
            if gate == 0:
                r_gate.append(_sigmoid(a))
            else:
                z_gate.append(_sigmoid(a))

    var s_reset = List[Float64](capacity=hidden)
    for k in range(hidden):
        s_reset.append(r_gate[k] * h_prev[k])

    # Candidate n (rows [2*hidden, 3*hidden)) uses s = r*h_prev.
    var n_cand = List[Float64](capacity=hidden)
    var h = List[Float64](capacity=hidden)
    for k in range(hidden):
        var r = 2 * hidden + k
        var a = b[r]
        var wb = r * input_size
        for j in range(input_size):
            a += W_flat[wb + j] * x[j]
        var ub = r * hidden
        for j in range(hidden):
            a += U_flat[ub + j] * s_reset[j]
        var nv = tanh(a)
        n_cand.append(nv)
        h.append(z_gate[k] * h_prev[k] + (1.0 - z_gate[k]) * nv)

    out.h = h^
    out.r_gate = r_gate^
    out.z_gate = z_gate^
    out.n_cand = n_cand^
    out.s_reset = s_reset^
    return out^


# ── gru_cell_backward ────────────────────────────────────────────────────────


def gru_cell_backward(
    dh: List[Float64],
    cache: GRUState,
    x: List[Float64],
    h_prev: List[Float64],
    W_flat: List[Float64],
    U_flat: List[Float64],
    hidden: Int,
) -> GRUGrads:
    """Exact GRU cell backward for upstream grad dh (wrt h).

    Uses the cache from gru_cell_forward on the same (x, h_prev, W_flat,
    U_flat). dW/dU/db use the same flattened r,z,n layout as the forward
    parameters. Returns empty grads on inconsistent sizes.
    """
    var out = GRUGrads()
    var input_size = len(x)
    if hidden <= 0 or len(dh) != hidden or len(h_prev) != hidden:
        return out^
    if len(cache.h) != hidden or len(cache.s_reset) != hidden:
        return out^
    var rows = 3 * hidden
    if len(W_flat) != rows * input_size or len(U_flat) != rows * hidden:
        return out^

    # h = z*h_prev + (1-z)*n
    var dz_pre = List[Float64](capacity=hidden)
    var dn_pre = List[Float64](capacity=hidden)
    for k in range(hidden):
        var zv = cache.z_gate[k]
        var nv = cache.n_cand[k]
        dz_pre.append(dh[k] * (h_prev[k] - nv) * zv * (1.0 - zv))
        dn_pre.append(dh[k] * (1.0 - zv) * (1.0 - nv * nv))

    # s = r*h_prev enters n through U_n: ds = U_n^T dn_pre.
    var ds = _zeros(hidden)
    for k in range(hidden):
        var ub = (2 * hidden + k) * hidden
        for j in range(hidden):
            ds[j] += U_flat[ub + j] * dn_pre[k]

    var dr_pre = List[Float64](capacity=hidden)
    for k in range(hidden):
        var rv = cache.r_gate[k]
        dr_pre.append(ds[k] * h_prev[k] * rv * (1.0 - rv))

    # Parameter grads, gate blocks r,z,n. U_n's grad pairs with s, not h_prev.
    var dW = List[Float64](capacity=rows * input_size)
    var dU = List[Float64](capacity=rows * hidden)
    var db = List[Float64](capacity=rows)
    for gate in range(3):
        for k in range(hidden):
            var d: Float64
            if gate == 0:
                d = dr_pre[k]
            elif gate == 1:
                d = dz_pre[k]
            else:
                d = dn_pre[k]
            for j in range(input_size):
                dW.append(d * x[j])
            for j in range(hidden):
                if gate == 2:
                    dU.append(d * cache.s_reset[j])
                else:
                    dU.append(d * h_prev[j])
            db.append(d)

    # dx = W_r^T dr_pre + W_z^T dz_pre + W_n^T dn_pre
    var dx = _zeros(input_size)
    var dh_prev = List[Float64](capacity=hidden)
    for k in range(hidden):
        dh_prev.append(dh[k] * cache.z_gate[k] + ds[k] * cache.r_gate[k])
    for k in range(hidden):
        var wb_r = k * input_size
        var wb_z = (hidden + k) * input_size
        var wb_n = (2 * hidden + k) * input_size
        for j in range(input_size):
            dx[j] += (
                W_flat[wb_r + j] * dr_pre[k]
                + W_flat[wb_z + j] * dz_pre[k]
                + W_flat[wb_n + j] * dn_pre[k]
            )
        var ub_r = k * hidden
        var ub_z = (hidden + k) * hidden
        for j in range(hidden):
            dh_prev[j] += (
                U_flat[ub_r + j] * dr_pre[k] + U_flat[ub_z + j] * dz_pre[k]
            )

    out.dx = dx^
    out.dh_prev = dh_prev^
    out.dW = dW^
    out.dU = dU^
    out.db = db^
    return out^


# ── param counts ─────────────────────────────────────────────────────────────


def lstm_param_count(input_size: Int, hidden: Int) -> Int:
    """Total LSTM cell parameters: 4*hidden*(input_size + hidden + 1)."""
    if input_size < 0 or hidden <= 0:
        return 0
    return 4 * hidden * (input_size + hidden + 1)


def gru_param_count(input_size: Int, hidden: Int) -> Int:
    """Total GRU cell parameters: 3*hidden*(input_size + hidden + 1)."""
    if input_size < 0 or hidden <= 0:
        return 0
    return 3 * hidden * (input_size + hidden + 1)


# ── init helpers ─────────────────────────────────────────────────────────────


def xavier_flat(
    rows: Int, cols: Int, fan_in: Int, fan_out: Int, seed: Int
) -> List[Float64]:
    """Seeded Xavier/Glorot uniform flat [rows x cols] matrix (row-major).

    Values ~ U(-limit, limit), limit = sqrt(6 / (fan_in + fan_out)).
    fan_in/fan_out are explicit because stacked gate matrices have
    rows = n_gates*hidden but per-gate fan_out = hidden. Deterministic
    for a given seed.
    """
    var out = List[Float64]()
    if rows <= 0 or cols <= 0 or fan_in + fan_out <= 0:
        return out^
    var limit = sqrt(6.0 / Float64(fan_in + fan_out))
    var state = _seed_state(seed)
    for _ in range(rows * cols):
        out.append((_rand_unit(state) * 2.0 - 1.0) * limit)
    return out^


def init_lstm_params(input_size: Int, hidden: Int, seed: Int) -> RNNParams:
    """Seeded LSTM parameter init.

    W [4*hidden x input_size] xavier with fans (input_size, hidden);
    U [4*hidden x hidden] xavier with fans (hidden, hidden); b zero
    except the forget-gate block (rows [hidden, 2*hidden)) = 1.0, the
    standard trick so early training does not forget. W and U draw
    from independent derived seeds; deterministic for a given seed.
    """
    var out = RNNParams()
    if input_size <= 0 or hidden <= 0:
        return out^
    out.W = xavier_flat(4 * hidden, input_size, input_size, hidden, seed)
    out.U = xavier_flat(4 * hidden, hidden, hidden, hidden, seed + 0x51F15EED)
    out.b = _zeros(4 * hidden)
    for k in range(hidden, 2 * hidden):
        out.b[k] = 1.0
    return out^


def init_gru_params(input_size: Int, hidden: Int, seed: Int) -> RNNParams:
    """Seeded GRU parameter init.

    W [3*hidden x input_size] xavier with fans (input_size, hidden);
    U [3*hidden x hidden] xavier with fans (hidden, hidden); b zero.
    W and U draw from independent derived seeds; deterministic for a
    given seed.
    """
    var out = RNNParams()
    if input_size <= 0 or hidden <= 0:
        return out^
    out.W = xavier_flat(3 * hidden, input_size, input_size, hidden, seed)
    out.U = xavier_flat(3 * hidden, hidden, hidden, hidden, seed + 0x51F15EED)
    out.b = _zeros(3 * hidden)
    return out^
