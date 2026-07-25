"""
seq2_trainer.mojo — Production trainer for a 2-layer LSTM regressor.
Zero Python imports.

Replaces a keras/CPU-TF training loop (LSTM -> LSTM -> Dense(relu) ->
Dense(1)) for batch training on large sets of dense sequences (lookback
~18..22 steps, ~8..12 features, hidden ~32). Mini-batch Adam with full
backpropagation-through-time through both LSTM layers, inverted dropout,
global-norm gradient clipping, early stopping with best-validation weight
restore, and a flat weight export a Python caller can reshape into keras
kernel/recurrent_kernel/bias conventions.

Architecture (fixed): LSTM(H) -> LSTM(H) -> Dense(Dh, relu) -> Dense(1).
Inputs are dense (no masking layer); no batchnorm. Cell math follows
seq_nn.mojo / seq_training.mojo exactly: gates i, f, g, o with
sigmoid/sigmoid/tanh/sigmoid, c = f*c_prev + i*g, h = o*tanh(c); layer 1
consumes the raw features, layer 2 consumes layer 1's (dropout-masked)
hidden sequence, and the dense head reads layer 2's final hidden state.

PERFORMANCE: the inner gate matmuls and all BPTT gradient accumulations
(the dot/axpy kernels) are SIMD-vectorized (width-8 f64 lanes with scalar
tails); gradient accumulation over a mini-batch is parallelized across
workers with `parallelize`. Measured on the realistic slice (2000 seqs,
T=22, D=11, H=32, batch 64): 8 workers ~8.1x over single-threaded scalar
BPTT (see mojo/tests/bench_seq2_trainer.mojo). Each worker owns a private gradient accumulator and
the per-worker blocks are summed in fixed worker order, so results are
DETERMINISTIC run-to-run for a fixed worker count. A single-threaded run
(n_workers=1, e.g. via seq2_train_workers) is fully deterministic given
the seed. Different worker counts can differ only by floating-point
summation order of per-sample gradients. Dropout masks are derived per
(seed, epoch, sample-index), independent of shuffling and worker layout.

Data layout: x_flat holds n_seq sequences, each seq_len timesteps of
input_dim features, time-major within a sequence:
x_flat[s*seq_len*input_dim + t*input_dim + d].

Flat weight layout (seq2_export / seq2_from_flat / seq2_grad), for
D=input_dim, H=hidden, Dh=dense_h — blocks in order, each row-major:

  block   length   shape       meaning
  l1_wx   4H*D     [4H x D]    layer-1 input weights
  l1_wh   4H*H     [4H x H]    layer-1 recurrent weights
  l1_b    4H       [4H]        layer-1 bias
  l2_wx   4H*H     [4H x H]    layer-2 input weights (input = layer-1 h)
  l2_wh   4H*H     [4H x H]    layer-2 recurrent weights
  l2_b    4H       [4H]        layer-2 bias
  d1_w    Dh*H     [Dh x H]    dense hidden weights
  d1_b    Dh       [Dh]        dense hidden bias
  d2_w    Dh       [1 x Dh]    output weights
  d2_b    1        [1]         output bias

Gate rows within every 4H-row LSTM block are stacked i, f, g, o: row
r = gate*H + k drives unit k of that gate — the same gate order keras
uses (i, f, c, o). Python/keras reshape recipe (numpy, row-major):

  kernel_1           = flat[l1_wx].reshape(4*H, D).T   # (D, 4H)
  recurrent_kernel_1 = flat[l1_wh].reshape(4*H, H).T   # (H, 4H)
  bias_1             = flat[l1_b]                      # (4H,)
  kernel_2           = flat[l2_wx].reshape(4*H, H).T   # (H, 4H)
  recurrent_kernel_2 = flat[l2_wh].reshape(4*H, H).T   # (H, 4H)
  bias_2             = flat[l2_b]                      # (4H,)
  dense1_kernel      = flat[d1_w].reshape(Dh, H).T     # (H, Dh)
  dense1_bias        = flat[d1_b]                      # (Dh,)
  dense2_kernel      = flat[d2_w].reshape(1, Dh).T     # (Dh, 1)
  dense2_bias        = flat[d2_b]                      # (1,)

Public API:
  Seq2Params          — fieldwise flat weight blocks + dims
  Seq2TrainResult     — trained params + train/val loss history + best_epoch
  seq2_weight_count   — total flat weight count for (D, H, Dh)
  seq2_init           — seeded xavier init (forget-gate biases = 1.0)
  seq2_forward        — predictions for n_seq sequences
  seq2_loss           — mean MSE over a dataset (no dropout)
  seq2_grad           — exact mean-MSE gradient, flat export layout
  seq2_train          — mini-batch Adam BPTT trainer (parallel workers)
  seq2_train_workers  — same with explicit worker count (1 = single-thread)
  seq2_train_scalar   — scalar (non-SIMD) single-thread build, perf baseline
  seq2_export         — params -> single flat weight vector (layout above)
  seq2_from_flat      — flat vector -> Seq2Params (inverse of seq2_export)
"""

from std.math import sqrt, exp, tanh
from std.algorithm import parallelize
from std.sys import info
from seq_nn import xavier_flat


# ── seeded RNG helpers (deterministic xorshift64, as in seq_training) ────────


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


def _sample_rng(seed: Int, epoch: Int, idx: Int) -> UInt64:
    """Per-(seed, epoch, sample) dropout RNG state.

    Independent of shuffle order and worker partitioning, so dropout masks
    are identical whatever the worker count.
    """
    var s = _seed_state(seed)
    s ^= (UInt64(epoch) + 1) * UInt64(0xA24BAED4963EE407)
    s ^= (UInt64(idx) + 1) * UInt64(0x9FB21C651E98DF25)
    if s == 0:
        s = UInt64(0x9E3779B97F4A7C15)
    s = _xorshift64(s)
    s = _xorshift64(s)
    return s


# ── math helpers ─────────────────────────────────────────────────────────────


def _sig(x: Float64) -> Float64:
    """Logistic sigmoid, branchless 1/(1+exp(-x)) (IEEE-safe: exp overflow
    to +inf yields exactly 0.0; underflow to 0.0 yields exactly 1.0)."""
    return 1.0 / (1.0 + exp(-x))


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for _ in range(n):
        out.append(0.0)
    return out^


# ── SIMD primitives (width-8 f64 lanes, scalar tails) ────────────────────────

comptime _W = 8


def _dot[
    simd: Bool
](
    a: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    ao: Int,
    b: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    bo: Int,
    n: Int,
) -> Float64:
    """dot(a[ao:ao+n], b[bo:bo+n]); fixed lane-then-tail order (deterministic)."""

    comptime if simd:
        var acc = SIMD[DType.float64, _W](0.0)
        var i = 0
        while i + _W <= n:
            acc = a.load[width=_W](ao + i).fma(b.load[width=_W](bo + i), acc)
            i += _W
        var s = acc.reduce_add()
        while i < n:
            s += a[ao + i] * b[bo + i]
            i += 1
        return s
    else:
        var s = 0.0
        for i in range(n):
            s += a[ao + i] * b[bo + i]
        return s


def _axpy[
    simd: Bool
](
    s: Float64,
    a: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    ao: Int,
    o: UnsafePointer[Float64, origin=MutAnyOrigin],
    oo: Int,
    n: Int,
):
    """o[oo:oo+n] += s * a[ao:ao+n] (ranges must not overlap)."""

    comptime if simd:
        var sv = SIMD[DType.float64, _W](s)
        var i = 0
        while i + _W <= n:
            o.store(
                oo + i, sv.fma(a.load[width=_W](ao + i), o.load[width=_W](oo + i))
            )
            i += _W
        while i < n:
            o[oo + i] += s * a[ao + i]
            i += 1
    else:
        for i in range(n):
            o[oo + i] += s * a[ao + i]


# ── weight / scratch layouts ─────────────────────────────────────────────────


struct _Wt(Copyable, Movable):
    """Flat-weight block offsets for (D, H, Dh) — the documented export layout."""

    var l1wx: Int
    var l1wh: Int
    var l1b: Int
    var l2wx: Int
    var l2wh: Int
    var l2b: Int
    var d1w: Int
    var d1b: Int
    var d2w: Int
    var d2b: Int
    var total: Int

    def __init__(out self, D: Int, H: Int, Dh: Int):
        var h4 = 4 * H
        self.l1wx = 0
        self.l1wh = self.l1wx + h4 * D
        self.l1b = self.l1wh + h4 * H
        self.l2wx = self.l1b + h4
        self.l2wh = self.l2wx + h4 * H
        self.l2b = self.l2wh + h4 * H
        self.d1w = self.l2b + h4
        self.d1b = self.d1w + Dh * H
        self.d2w = self.d1b + Dh
        self.d2b = self.d2w + Dh
        self.total = self.d2b + 1


struct _Scr(Copyable, Movable):
    """Per-worker scratch offsets for one sample of T steps (H, Dh dims)."""

    var pre: Int  # 4H   gate pre-activations (current step)
    var da: Int  # 4H   gate pre-activation grads (current step)
    var dh1: Int  # H    running dL/dh for layer 1
    var dc1: Int  # H    running dL/dc for layer 1
    var dh2: Int  # H    running dL/dh for layer 2
    var dc2: Int  # H    running dL/dc for layer 2
    var tmp1: Int  # H    dh_prev accumulator
    var tmp2: Int  # H    layer-2 -> layer-1 dh contribution
    var dz: Int  # Dh   dense-hidden pre-activation grads
    var a1: Int  # Dh   dense hidden activations (post-relu)
    var a1d: Int  # Dh   dense hidden after dropout
    var md: Int  # Dh   dense dropout mask
    var g1: Int  # T*4H layer-1 gate activations (i,f,g,o per step)
    var g2: Int  # T*4H layer-2 gate activations
    var h1: Int  # (T+1)*H  layer-1 hidden states (row 0 = zero init)
    var c1: Int  # (T+1)*H  layer-1 cell states
    var ct1: Int  # T*H  tanh(c1) cache
    var h1d: Int  # T*H  layer-1 hidden after dropout (layer-2 input)
    var m1: Int  # T*H  inter-layer dropout mask
    var h2: Int  # (T+1)*H  layer-2 hidden states
    var c2: Int  # (T+1)*H  layer-2 cell states
    var ct2: Int  # T*H  tanh(c2) cache
    var total: Int

    def __init__(out self, T: Int, H: Int, Dh: Int):
        var h4 = 4 * H
        self.pre = 0
        self.da = self.pre + h4
        self.dh1 = self.da + h4
        self.dc1 = self.dh1 + H
        self.dh2 = self.dc1 + H
        self.dc2 = self.dh2 + H
        self.tmp1 = self.dc2 + H
        self.tmp2 = self.tmp1 + H
        self.dz = self.tmp2 + H
        self.a1 = self.dz + Dh
        self.a1d = self.a1 + Dh
        self.md = self.a1d + Dh
        self.g1 = self.md + Dh
        self.g2 = self.g1 + T * h4
        self.h1 = self.g2 + T * h4
        self.c1 = self.h1 + (T + 1) * H
        self.ct1 = self.c1 + (T + 1) * H
        self.h1d = self.ct1 + T * H
        self.m1 = self.h1d + T * H
        self.h2 = self.m1 + T * H
        self.c2 = self.h2 + (T + 1) * H
        self.ct2 = self.c2 + (T + 1) * H
        self.total = self.ct2 + T * H


def _fill_masks_one(
    s: UnsafePointer[Float64, origin=MutAnyOrigin], T: Int, H: Int, Dh: Int
):
    """Set a scratch block's dropout masks to 1.0 (used when dropout == 0)."""
    var sc = _Scr(T, H, Dh)
    for i in range(T * H):
        s[sc.m1 + i] = 1.0
    for i in range(Dh):
        s[sc.md + i] = 1.0


# ── public structs ───────────────────────────────────────────────────────────


struct Seq2Params(Copyable, Movable):
    """2-layer LSTM regressor parameters, fieldwise flat blocks (row-major,
    gate rows stacked i,f,g,o — see module docstring for the exact layout)."""

    var input_dim: Int
    var hidden: Int
    var dense_h: Int
    var l1_wx: List[Float64]  # [4H x D]
    var l1_wh: List[Float64]  # [4H x H]
    var l1_b: List[Float64]  # [4H]
    var l2_wx: List[Float64]  # [4H x H]
    var l2_wh: List[Float64]  # [4H x H]
    var l2_b: List[Float64]  # [4H]
    var d1_w: List[Float64]  # [Dh x H]
    var d1_b: List[Float64]  # [Dh]
    var d2_w: List[Float64]  # [Dh]
    var d2_b: List[Float64]  # [1]

    def __init__(out self):
        self.input_dim = 0
        self.hidden = 0
        self.dense_h = 0
        self.l1_wx = List[Float64]()
        self.l1_wh = List[Float64]()
        self.l1_b = List[Float64]()
        self.l2_wx = List[Float64]()
        self.l2_wh = List[Float64]()
        self.l2_b = List[Float64]()
        self.d1_w = List[Float64]()
        self.d1_b = List[Float64]()
        self.d2_w = List[Float64]()
        self.d2_b = List[Float64]()


struct Seq2TrainResult(Copyable, Movable):
    """Training output.

    params: trained weights (best-validation weights when a validation set
    was given, else the final weights). train_loss[e]: mean per-sample
    squared error accumulated during epoch e (dropout active, weights
    updating batch-by-batch). val_loss[e]: clean (no-dropout) validation
    MSE after epoch e (empty when n_val == 0). best_epoch: epoch whose
    validation loss was lowest (last epoch when n_val == 0; -1 on invalid
    input). epochs_run: epochs actually executed (early stopping can make
    this < epochs)."""

    var params: Seq2Params
    var train_loss: List[Float64]
    var val_loss: List[Float64]
    var best_epoch: Int
    var epochs_run: Int

    def __init__(out self):
        self.params = Seq2Params()
        self.train_loss = List[Float64]()
        self.val_loss = List[Float64]()
        self.best_epoch = -1
        self.epochs_run = 0


# ── weight count / init / export / import ────────────────────────────────────


def seq2_weight_count(input_dim: Int, hidden: Int, dense_h: Int) -> Int:
    """Total flat weight count: 4H(D+H+1) + 4H(2H+1) + Dh(H+2) + 1."""
    if input_dim <= 0 or hidden <= 0 or dense_h <= 0:
        return 0
    return _Wt(input_dim, hidden, dense_h).total


def _params_ok(params: Seq2Params) -> Bool:
    var D = params.input_dim
    var H = params.hidden
    var Dh = params.dense_h
    if D <= 0 or H <= 0 or Dh <= 0:
        return False
    var h4 = 4 * H
    return (
        len(params.l1_wx) == h4 * D
        and len(params.l1_wh) == h4 * H
        and len(params.l1_b) == h4
        and len(params.l2_wx) == h4 * H
        and len(params.l2_wh) == h4 * H
        and len(params.l2_b) == h4
        and len(params.d1_w) == Dh * H
        and len(params.d1_b) == Dh
        and len(params.d2_w) == Dh
        and len(params.d2_b) == 1
    )


def seq2_init(input_dim: Int, hidden: Int, dense_h: Int, seed: Int) -> Seq2Params:
    """Seeded init for the 2-layer LSTM regressor.

    LSTM input/recurrent blocks are xavier-uniform (per-gate fans, via
    seq_nn.xavier_flat) with independent derived seeds per block; LSTM
    biases are zero except the forget-gate rows [H, 2H) = 1.0 in BOTH
    layers (standard trick so early training does not forget). Dense
    blocks are xavier-uniform, dense biases zero. Deterministic for a
    given seed. Returns empty params (dims 0) for non-positive dims.
    """
    var out = Seq2Params()
    if input_dim <= 0 or hidden <= 0 or dense_h <= 0:
        return out^
    var D = input_dim
    var H = hidden
    var Dh = dense_h
    out.input_dim = D
    out.hidden = H
    out.dense_h = Dh
    out.l1_wx = xavier_flat(4 * H, D, D, H, seed)
    out.l1_wh = xavier_flat(4 * H, H, H, H, seed + 0x51F15EED)
    out.l1_b = _zeros(4 * H)
    out.l2_wx = xavier_flat(4 * H, H, H, H, seed + 0x2C1B3C6D)
    out.l2_wh = xavier_flat(4 * H, H, H, H, seed + 0x6A09E667)
    out.l2_b = _zeros(4 * H)
    out.d1_w = xavier_flat(Dh, H, H, Dh, seed + 0x3C6EF372)
    out.d1_b = _zeros(Dh)
    out.d2_w = xavier_flat(1, Dh, Dh, 1, seed + 0x1F83D9AB)
    out.d2_b = _zeros(1)
    for k in range(H, 2 * H):
        out.l1_b[k] = 1.0
        out.l2_b[k] = 1.0
    return out^


def seq2_export(params: Seq2Params) -> List[Float64]:
    """Flatten params into one vector, block order as documented in the
    module docstring (l1_wx, l1_wh, l1_b, l2_wx, l2_wh, l2_b, d1_w, d1_b,
    d2_w, d2_b — each row-major, gate rows stacked i,f,g,o). Returns an
    empty list on inconsistent params."""
    var out = List[Float64]()
    if not _params_ok(params):
        return out^
    var lay = _Wt(params.input_dim, params.hidden, params.dense_h)
    out = List[Float64](capacity=lay.total)
    for i in range(len(params.l1_wx)):
        out.append(params.l1_wx[i])
    for i in range(len(params.l1_wh)):
        out.append(params.l1_wh[i])
    for i in range(len(params.l1_b)):
        out.append(params.l1_b[i])
    for i in range(len(params.l2_wx)):
        out.append(params.l2_wx[i])
    for i in range(len(params.l2_wh)):
        out.append(params.l2_wh[i])
    for i in range(len(params.l2_b)):
        out.append(params.l2_b[i])
    for i in range(len(params.d1_w)):
        out.append(params.d1_w[i])
    for i in range(len(params.d1_b)):
        out.append(params.d1_b[i])
    for i in range(len(params.d2_w)):
        out.append(params.d2_w[i])
    out.append(params.d2_b[0])
    return out^


def _slice(flat: List[Float64], start: Int, n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(flat[start + i])
    return out^


def seq2_from_flat(
    flat: List[Float64], input_dim: Int, hidden: Int, dense_h: Int
) -> Seq2Params:
    """Inverse of seq2_export: rebuild Seq2Params from a flat vector.

    Returns empty params (dims 0) when len(flat) does not match
    seq2_weight_count(input_dim, hidden, dense_h) or dims are invalid.
    """
    var out = Seq2Params()
    var n = seq2_weight_count(input_dim, hidden, dense_h)
    if n == 0 or len(flat) != n:
        return out^
    var D = input_dim
    var H = hidden
    var Dh = dense_h
    var lay = _Wt(D, H, Dh)
    out.input_dim = D
    out.hidden = H
    out.dense_h = Dh
    out.l1_wx = _slice(flat, lay.l1wx, 4 * H * D)
    out.l1_wh = _slice(flat, lay.l1wh, 4 * H * H)
    out.l1_b = _slice(flat, lay.l1b, 4 * H)
    out.l2_wx = _slice(flat, lay.l2wx, 4 * H * H)
    out.l2_wh = _slice(flat, lay.l2wh, 4 * H * H)
    out.l2_b = _slice(flat, lay.l2b, 4 * H)
    out.d1_w = _slice(flat, lay.d1w, Dh * H)
    out.d1_b = _slice(flat, lay.d1b, Dh)
    out.d2_w = _slice(flat, lay.d2w, Dh)
    out.d2_b = _slice(flat, lay.d2b, 1)
    return out^


# ── forward-only sample kernel (prediction / validation, no dropout) ─────────


def _predict_sample[
    simd: Bool
](
    w: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    x: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    x_off: Int,
    T: Int,
    D: Int,
    H: Int,
    Dh: Int,
    s: UnsafePointer[Float64, origin=MutAnyOrigin],
) -> Float64:
    """Forward one sequence; scratch s needs 8H + Dh floats.

    Scratch layout: h1[0:H], c1[H:2H], h2[2H:3H], c2[3H:4H], pre[4H:8H],
    a1[8H:8H+Dh]. Zero initial states; identical recurrence to training.
    """
    var lay = _Wt(D, H, Dh)
    var h4 = 4 * H
    var o_h1 = 0
    var o_c1 = H
    var o_h2 = 2 * H
    var o_c2 = 3 * H
    var o_pre = 4 * H
    var o_a1 = 8 * H
    for k in range(4 * H):
        s[k] = 0.0
    for t in range(T):
        var xo = x_off + t * D
        # layer 1 pre-activations (read h1 fully before any state write)
        for r in range(h4):
            s[o_pre + r] = (
                w[lay.l1b + r]
                + _dot[simd](w, lay.l1wx + r * D, x, xo, D)
                + _dot[simd](w, lay.l1wh + r * H, s, o_h1, H)
            )
        for k in range(H):
            var iv = _sig(s[o_pre + k])
            var fv = _sig(s[o_pre + H + k])
            var gv = tanh(s[o_pre + 2 * H + k])
            var ov = _sig(s[o_pre + 3 * H + k])
            var cv = fv * s[o_c1 + k] + iv * gv
            s[o_c1 + k] = cv
            s[o_h1 + k] = ov * tanh(cv)
        # layer 2 (input = layer-1 hidden at this step)
        for r in range(h4):
            s[o_pre + r] = (
                w[lay.l2b + r]
                + _dot[simd](w, lay.l2wx + r * H, s, o_h1, H)
                + _dot[simd](w, lay.l2wh + r * H, s, o_h2, H)
            )
        for k in range(H):
            var iv = _sig(s[o_pre + k])
            var fv = _sig(s[o_pre + H + k])
            var gv = tanh(s[o_pre + 2 * H + k])
            var ov = _sig(s[o_pre + 3 * H + k])
            var cv = fv * s[o_c2 + k] + iv * gv
            s[o_c2 + k] = cv
            s[o_h2 + k] = ov * tanh(cv)
    # dense head
    for j in range(Dh):
        var z = w[lay.d1b + j] + _dot[simd](w, lay.d1w + j * H, s, o_h2, H)
        s[o_a1 + j] = z if z > 0.0 else 0.0
    return w[lay.d2b] + _dot[simd](w, lay.d2w, s, o_a1, Dh)


# ── training sample kernel: forward with caches + full BPTT backward ─────────


def _fwd_bwd_sample[
    simd: Bool
](
    w: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    x: UnsafePointer[Float64, origin=ImmutAnyOrigin],
    x_off: Int,
    target: Float64,
    inv_n: Float64,
    dropout: Float64,
    rng_in: UInt64,
    T: Int,
    D: Int,
    H: Int,
    Dh: Int,
    s: UnsafePointer[Float64, origin=MutAnyOrigin],
    g: UnsafePointer[Float64, origin=MutAnyOrigin],
) -> Float64:
    """One sample: cached forward + exact BPTT; accumulate grads into g.

    dL/dy = 2*(y_hat - target)*inv_n (mean-MSE over the batch). Returns the
    raw squared error. When dropout <= 0 the mask regions of s must already
    hold 1.0 (see _fill_masks_one); when dropout > 0 masks are drawn from
    rng_in (inverted dropout: 0 with prob p, else 1/(1-p)).
    """
    var lay = _Wt(D, H, Dh)
    var sc = _Scr(T, H, Dh)
    var h4 = 4 * H
    var rng = rng_in
    var use_drop = dropout > 0.0
    var keep_scale = 0.0
    if use_drop:
        keep_scale = 1.0 / (1.0 - dropout)

    # ── forward ──────────────────────────────────────────────────────────────
    for k in range(H):
        s[sc.h1 + k] = 0.0
        s[sc.c1 + k] = 0.0
        s[sc.h2 + k] = 0.0
        s[sc.c2 + k] = 0.0
    for t in range(T):
        var xo = x_off + t * D
        var hp1 = sc.h1 + t * H
        var g1t = sc.g1 + t * h4
        for r in range(h4):
            s[sc.pre + r] = (
                w[lay.l1b + r]
                + _dot[simd](w, lay.l1wx + r * D, x, xo, D)
                + _dot[simd](w, lay.l1wh + r * H, s, hp1, H)
            )
        for k in range(H):
            var iv = _sig(s[sc.pre + k])
            var fv = _sig(s[sc.pre + H + k])
            var gv = tanh(s[sc.pre + 2 * H + k])
            var ov = _sig(s[sc.pre + 3 * H + k])
            s[g1t + k] = iv
            s[g1t + H + k] = fv
            s[g1t + 2 * H + k] = gv
            s[g1t + 3 * H + k] = ov
            var cv = fv * s[sc.c1 + t * H + k] + iv * gv
            s[sc.c1 + (t + 1) * H + k] = cv
            var ct = tanh(cv)
            s[sc.ct1 + t * H + k] = ct
            var hv = ov * ct
            s[sc.h1 + (t + 1) * H + k] = hv
            if use_drop:
                var m = keep_scale if _rand_unit(rng) >= dropout else 0.0
                s[sc.m1 + t * H + k] = m
                s[sc.h1d + t * H + k] = hv * m
            else:
                s[sc.h1d + t * H + k] = hv  # mask region pre-filled with 1.0
        var hp2 = sc.h2 + t * H
        var g2t = sc.g2 + t * h4
        for r in range(h4):
            s[sc.pre + r] = (
                w[lay.l2b + r]
                + _dot[simd](w, lay.l2wx + r * H, s, sc.h1d + t * H, H)
                + _dot[simd](w, lay.l2wh + r * H, s, hp2, H)
            )
        for k in range(H):
            var iv = _sig(s[sc.pre + k])
            var fv = _sig(s[sc.pre + H + k])
            var gv = tanh(s[sc.pre + 2 * H + k])
            var ov = _sig(s[sc.pre + 3 * H + k])
            s[g2t + k] = iv
            s[g2t + H + k] = fv
            s[g2t + 2 * H + k] = gv
            s[g2t + 3 * H + k] = ov
            var cv = fv * s[sc.c2 + t * H + k] + iv * gv
            s[sc.c2 + (t + 1) * H + k] = cv
            var ct = tanh(cv)
            s[sc.ct2 + t * H + k] = ct
            s[sc.h2 + (t + 1) * H + k] = ov * ct
    # dense head
    var hT = sc.h2 + T * H
    for j in range(Dh):
        var z = w[lay.d1b + j] + _dot[simd](w, lay.d1w + j * H, s, hT, H)
        var a = z if z > 0.0 else 0.0
        s[sc.a1 + j] = a
        if use_drop:
            var m = keep_scale if _rand_unit(rng) >= dropout else 0.0
            s[sc.md + j] = m
            s[sc.a1d + j] = a * m
        else:
            s[sc.a1d + j] = a
    var y_hat = w[lay.d2b] + _dot[simd](w, lay.d2w, s, sc.a1d, Dh)
    var err = y_hat - target
    var dy = 2.0 * err * inv_n

    # ── backward: dense head ─────────────────────────────────────────────────
    g[lay.d2b] += dy
    _axpy[simd](dy, s, sc.a1d, g, lay.d2w, Dh)
    for j in range(Dh):
        var dz = 0.0
        if s[sc.a1 + j] > 0.0:
            dz = dy * w[lay.d2w + j] * s[sc.md + j]
        s[sc.dz + j] = dz
        g[lay.d1b + j] += dz
        _axpy[simd](dz, s, hT, g, lay.d1w + j * H, H)
    for k in range(H):
        s[sc.dh1 + k] = 0.0
        s[sc.dc1 + k] = 0.0
        s[sc.dh2 + k] = 0.0
        s[sc.dc2 + k] = 0.0
    for j in range(Dh):
        _axpy[simd](s[sc.dz + j], w, lay.d1w + j * H, s, sc.dh2, H)

    # ── backward: interleaved BPTT through both layers ───────────────────────
    for t in range(T - 1, -1, -1):
        # layer 2 step
        var g2t = sc.g2 + t * h4
        for k in range(H):
            var iv = s[g2t + k]
            var fv = s[g2t + H + k]
            var gv = s[g2t + 2 * H + k]
            var ov = s[g2t + 3 * H + k]
            var tc = s[sc.ct2 + t * H + k]
            var dct = s[sc.dc2 + k] + s[sc.dh2 + k] * ov * (1.0 - tc * tc)
            s[sc.da + k] = dct * gv * iv * (1.0 - iv)
            s[sc.da + H + k] = dct * s[sc.c2 + t * H + k] * fv * (1.0 - fv)
            s[sc.da + 2 * H + k] = dct * iv * (1.0 - gv * gv)
            s[sc.da + 3 * H + k] = s[sc.dh2 + k] * tc * ov * (1.0 - ov)
            s[sc.dc2 + k] = dct * fv
        for k in range(H):
            s[sc.tmp1 + k] = 0.0
            s[sc.tmp2 + k] = 0.0
        for r in range(h4):
            var d = s[sc.da + r]
            _axpy[simd](d, s, sc.h1d + t * H, g, lay.l2wx + r * H, H)
            _axpy[simd](d, s, sc.h2 + t * H, g, lay.l2wh + r * H, H)
            g[lay.l2b + r] += d
            _axpy[simd](d, w, lay.l2wh + r * H, s, sc.tmp1, H)  # dh2_prev
            _axpy[simd](d, w, lay.l2wx + r * H, s, sc.tmp2, H)  # dh1d_t
        for k in range(H):
            s[sc.dh2 + k] = s[sc.tmp1 + k]
            s[sc.dh1 + k] += s[sc.tmp2 + k] * s[sc.m1 + t * H + k]
        # layer 1 step
        var g1t = sc.g1 + t * h4
        for k in range(H):
            var iv = s[g1t + k]
            var fv = s[g1t + H + k]
            var gv = s[g1t + 2 * H + k]
            var ov = s[g1t + 3 * H + k]
            var tc = s[sc.ct1 + t * H + k]
            var dct = s[sc.dc1 + k] + s[sc.dh1 + k] * ov * (1.0 - tc * tc)
            s[sc.da + k] = dct * gv * iv * (1.0 - iv)
            s[sc.da + H + k] = dct * s[sc.c1 + t * H + k] * fv * (1.0 - fv)
            s[sc.da + 2 * H + k] = dct * iv * (1.0 - gv * gv)
            s[sc.da + 3 * H + k] = s[sc.dh1 + k] * tc * ov * (1.0 - ov)
            s[sc.dc1 + k] = dct * fv
        for k in range(H):
            s[sc.tmp1 + k] = 0.0
        var xo = x_off + t * D
        for r in range(h4):
            var d = s[sc.da + r]
            _axpy[simd](d, x, xo, g, lay.l1wx + r * D, D)
            _axpy[simd](d, s, sc.h1 + t * H, g, lay.l1wh + r * H, H)
            g[lay.l1b + r] += d
            _axpy[simd](d, w, lay.l1wh + r * H, s, sc.tmp1, H)  # dh1_prev
        for k in range(H):
            s[sc.dh1 + k] = s[sc.tmp1 + k]
    return err * err


# ── seq2_forward / seq2_loss / seq2_grad ─────────────────────────────────────


def seq2_forward(
    params: Seq2Params,
    x_flat: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
) -> List[Float64]:
    """Predictions for n_seq sequences (no dropout; zero initial states).

    x_flat layout: x_flat[s*seq_len*input_dim + t*input_dim + d]. Returns
    an empty list on invalid shapes (len(x_flat) must equal
    n_seq*seq_len*input_dim and input_dim must match params).
    """
    var out = List[Float64]()
    if not _params_ok(params) or params.input_dim != input_dim:
        return out^
    if n_seq <= 0 or seq_len <= 0:
        return out^
    if len(x_flat) != n_seq * seq_len * input_dim:
        return out^
    var H = params.hidden
    var Dh = params.dense_h
    var w = seq2_export(params)
    var scratch = _zeros(8 * H + Dh)
    var wp = w.unsafe_ptr()
    var xp = x_flat.unsafe_ptr()
    var sp = scratch.unsafe_ptr()
    out = List[Float64](capacity=n_seq)
    for i in range(n_seq):
        out.append(
            _predict_sample[True](
                wp, xp, i * seq_len * input_dim, seq_len, input_dim, H, Dh, sp
            )
        )
    return out^


def seq2_loss(
    params: Seq2Params,
    x_flat: List[Float64],
    y: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
) -> Float64:
    """Mean squared error over the dataset (no dropout). Returns 0.0 on
    invalid shapes (same checks as seq2_forward plus len(y) == n_seq)."""
    if len(y) != n_seq or n_seq <= 0:
        return 0.0
    var preds = seq2_forward(params, x_flat, n_seq, seq_len, input_dim)
    if len(preds) != n_seq:
        return 0.0
    var total = 0.0
    for i in range(n_seq):
        var e = preds[i] - y[i]
        total += e * e
    return total / Float64(n_seq)


def seq2_grad(
    params: Seq2Params,
    x_flat: List[Float64],
    y: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
) -> List[Float64]:
    """Exact gradient of the mean-MSE loss wrt all weights (no dropout).

    Returned flat vector uses the documented export layout, so
    grad[i] = d(seq2_loss)/d(seq2_export(params)[i]). Single-threaded and
    deterministic (samples accumulated in order). Empty list on invalid
    shapes. Intended for gradient checking and external optimizers.
    """
    var out = List[Float64]()
    if not _params_ok(params) or params.input_dim != input_dim:
        return out^
    if n_seq <= 0 or seq_len <= 0 or len(y) != n_seq:
        return out^
    if len(x_flat) != n_seq * seq_len * input_dim:
        return out^
    var D = input_dim
    var H = params.hidden
    var Dh = params.dense_h
    var T = seq_len
    var w = seq2_export(params)
    var grad = _zeros(len(w))
    var scratch = _zeros(_Scr(T, H, Dh).total)
    var wp = w.unsafe_ptr()
    var xp = x_flat.unsafe_ptr()
    var sp = scratch.unsafe_ptr()
    var gp = grad.unsafe_ptr()
    _fill_masks_one(sp, T, H, Dh)
    var inv_n = 1.0 / Float64(n_seq)
    for i in range(n_seq):
        _ = _fwd_bwd_sample[True](
            wp, xp, i * T * D, y[i], inv_n, 0.0, UInt64(1), T, D, H, Dh, sp, gp
        )
    return grad^


# ── index shuffle ────────────────────────────────────────────────────────────


def _shuffle(mut idx: List[Int], mut rng: UInt64):
    """Seeded Fisher-Yates shuffle."""
    for i in range(len(idx) - 1, 0, -1):
        var j = Int(_rand_unit(rng) * Float64(i + 1))
        if j > i:
            j = i
        var tswap = idx[i]
        idx[i] = idx[j]
        idx[j] = tswap


# ── trainer core ─────────────────────────────────────────────────────────────


def _train_impl[
    simd: Bool
](
    params: Seq2Params,
    x_flat: List[Float64],
    y: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
    x_val_flat: List[Float64],
    y_val: List[Float64],
    n_val: Int,
    epochs: Int,
    batch_size: Int,
    lr: Float64,
    dropout: Float64,
    patience: Int,
    seed: Int,
    n_workers: Int,
) -> Seq2TrainResult:
    """Shared trainer body; see seq2_train for semantics."""
    var out = Seq2TrainResult()
    var D = input_dim
    if not _params_ok(params) or params.input_dim != D:
        return out^
    var H = params.hidden
    var Dh = params.dense_h
    var T = seq_len
    if n_seq <= 0 or T <= 0 or len(y) != n_seq:
        return out^
    if len(x_flat) != n_seq * T * D:
        return out^
    var nv = n_val
    if nv < 0:
        nv = 0
    if nv > 0 and (len(x_val_flat) != nv * T * D or len(y_val) != nv):
        return out^
    if lr <= 0.0 or dropout >= 1.0:
        return out^
    var p_drop = dropout
    if p_drop < 0.0:
        p_drop = 0.0

    var w = seq2_export(params)
    var n_w = len(w)
    if epochs <= 0:
        out.params = seq2_from_flat(w, D, H, Dh)
        return out^

    var bs = batch_size
    if bs <= 0 or bs > n_seq:
        bs = n_seq
    var nw = n_workers
    if nw < 1:
        nw = 1
    if nw > n_seq:
        nw = n_seq

    var s_size = _Scr(T, H, Dh).total
    var gbuf = _zeros(nw * n_w)  # per-worker gradient accumulators
    var sbuf = _zeros(nw * s_size)  # per-worker BPTT scratch
    var lbuf = _zeros(nw)  # per-worker squared-error sums
    var grad = _zeros(n_w)  # fixed-order reduced gradient
    var pscratch = _zeros(8 * H + Dh)  # validation forward scratch
    if p_drop <= 0.0:
        for wk in range(nw):
            _fill_masks_one(sbuf.unsafe_ptr() + wk * s_size, T, H, Dh)

    var idx = List[Int](capacity=n_seq)
    for i in range(n_seq):
        idx.append(i)
    var srng = _seed_state(seed + 0x5EED)

    # Adam state (beta1=0.9, beta2=0.999, eps=1e-8, bias-corrected),
    # global-norm clip at 5.0 — implemented locally, zero Python.
    var m = _zeros(n_w)
    var v = _zeros(n_w)
    var beta1 = 0.9
    var beta2 = 0.999
    var eps = 1e-8
    var clip_norm = 5.0
    var b1t = 1.0
    var b2t = 1.0

    var wp = w.unsafe_ptr()
    var xp = x_flat.unsafe_ptr()
    var yp = y.unsafe_ptr()
    var idxp = idx.unsafe_ptr()
    var gbp = gbuf.unsafe_ptr()
    var sbp = sbuf.unsafe_ptr()
    var lbp = lbuf.unsafe_ptr()
    var gp = grad.unsafe_ptr()

    var best_w = w.copy()
    var best_val = 1e300
    var best_epoch = -1
    var bad = 0
    var epochs_run = 0
    out.train_loss = List[Float64](capacity=epochs)
    out.val_loss = List[Float64](capacity=epochs)

    for epoch in range(epochs):
        _shuffle(idx, srng)
        var epoch_sq = 0.0
        var b_start = 0
        while b_start < n_seq:
            var b_n = n_seq - b_start
            if b_n > bs:
                b_n = bs
            var nw_eff = nw
            if nw_eff > b_n:
                nw_eff = b_n
            var inv_b = 1.0 / Float64(b_n)
            var chunk = b_n // nw_eff
            var rem = b_n % nw_eff
            var bstart_c = b_start

            @parameter
            def worker(tid: Int):
                var lo: Int
                var hi: Int
                if tid < rem:
                    lo = bstart_c + tid * (chunk + 1)
                    hi = lo + chunk + 1
                else:
                    lo = bstart_c + rem * (chunk + 1) + (tid - rem) * chunk
                    hi = lo + chunk
                var goff = tid * n_w
                for j in range(n_w):
                    gbp[goff + j] = 0.0
                var soff = tid * s_size
                var acc = 0.0
                for pos in range(lo, hi):
                    var orig = idxp[pos]
                    acc += _fwd_bwd_sample[simd](
                        wp,
                        xp,
                        orig * T * D,
                        yp[orig],
                        inv_b,
                        p_drop,
                        _sample_rng(seed, epoch, orig),
                        T,
                        D,
                        H,
                        Dh,
                        sbp + soff,
                        gbp + goff,
                    )
                lbp[tid] = acc

            parallelize[worker](nw_eff)

            # fixed-order reduction: worker 0, then 1, ... => deterministic
            for wk in range(nw_eff):
                epoch_sq += lbp[wk]
            for j in range(n_w):
                gp[j] = gbp[j]
            for wk in range(1, nw_eff):
                _axpy[simd](1.0, gbp, wk * n_w, gp, 0, n_w)

            # global-norm clip
            var sq = _dot[simd](gp, 0, gp, 0, n_w)
            var norm = sqrt(sq)
            if norm > clip_norm:
                var scale = clip_norm / norm
                for j in range(n_w):
                    gp[j] *= scale

            # Adam step (bias-corrected)
            b1t *= beta1
            b2t *= beta2
            var corr1 = 1.0 - b1t
            var corr2 = 1.0 - b2t
            for j in range(n_w):
                m[j] = beta1 * m[j] + (1.0 - beta1) * gp[j]
                v[j] = beta2 * v[j] + (1.0 - beta2) * gp[j] * gp[j]
                w[j] -= lr * (m[j] / corr1) / (sqrt(v[j] / corr2) + eps)

            b_start += b_n

        epochs_run = epoch + 1
        out.train_loss.append(epoch_sq / Float64(n_seq))

        if nv > 0:
            var vsq = 0.0
            var xvp = x_val_flat.unsafe_ptr()
            var psp = pscratch.unsafe_ptr()
            for i in range(nv):
                var e = (
                    _predict_sample[simd](wp, xvp, i * T * D, T, D, H, Dh, psp)
                    - y_val[i]
                )
                vsq += e * e
            var vloss = vsq / Float64(nv)
            out.val_loss.append(vloss)
            if vloss < best_val:
                best_val = vloss
                best_epoch = epoch
                best_w = w.copy()
                bad = 0
            else:
                bad += 1
            if patience > 0 and bad >= patience:
                break

    if nv > 0 and best_epoch >= 0:
        out.params = seq2_from_flat(best_w, D, H, Dh)
        out.best_epoch = best_epoch
    else:
        out.params = seq2_from_flat(w, D, H, Dh)
        out.best_epoch = epochs_run - 1
    out.epochs_run = epochs_run
    return out^


# ── public trainers ──────────────────────────────────────────────────────────


def seq2_train_workers(
    params: Seq2Params,
    x_flat: List[Float64],
    y: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
    x_val_flat: List[Float64],
    y_val: List[Float64],
    n_val: Int,
    epochs: Int,
    batch_size: Int,
    lr: Float64,
    dropout: Float64,
    patience: Int,
    seed: Int,
    n_workers: Int,
) -> Seq2TrainResult:
    """seq2_train with an explicit worker count.

    n_workers == 1 is the fully deterministic single-threaded mode (samples
    accumulated in shuffled batch order). n_workers > 1 splits each batch
    into contiguous per-worker chunks with private gradient accumulators
    that are summed in fixed worker order, so a given worker count is also
    deterministic run-to-run; only the floating-point summation order (and
    therefore the last few ulps) differs BETWEEN worker counts.
    """
    return _train_impl[True](
        params, x_flat, y, n_seq, seq_len, input_dim, x_val_flat, y_val,
        n_val, epochs, batch_size, lr, dropout, patience, seed, n_workers,
    )


def seq2_train(
    params: Seq2Params,
    x_flat: List[Float64],
    y: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
    x_val_flat: List[Float64],
    y_val: List[Float64],
    n_val: Int,
    epochs: Int,
    batch_size: Int,
    lr: Float64,
    dropout: Float64,
    patience: Int,
    seed: Int,
) -> Seq2TrainResult:
    """Train the 2-layer LSTM regressor with mini-batch Adam + full BPTT.

    Starts from `params` (from seq2_init or seq2_from_flat). Per epoch:
    seeded shuffle, then per batch a parallel forward+BPTT over the batch
    samples (SIMD gate matmuls; per-worker gradient accumulators summed in
    fixed order — see seq2_train_workers for the determinism contract),
    mean-MSE gradient, global-L2-norm clip at 5.0, and a locally
    implemented bias-corrected Adam update (beta1=0.9, beta2=0.999,
    eps=1e-8). Inverted dropout (rate `dropout`, 0 disables) is applied to
    layer-1's hidden sequence (the layer-2 input) and to the dense hidden
    activation; masks are seeded per (seed, epoch, sample).

    Validation/early stopping: when n_val > 0 the clean validation MSE is
    recorded after every epoch; the best-validation weights are snapshotted
    and RESTORED into the result. With patience > 0, training stops after
    `patience` consecutive epochs without a new best. n_val == 0 disables
    both (pass empty lists), and the final weights are returned.

    batch_size <= 0 (or > n_seq) means full-batch. Worker count defaults
    to the machine's physical cores. train_loss[e] is the mean per-sample
    squared error accumulated while training epoch e (dropout active,
    weights updating batch to batch); val_loss[e] is measured with dropout
    off. Returns an empty result (dims 0, empty histories, best_epoch -1)
    on invalid shapes, lr <= 0, or dropout >= 1.
    """
    var cores = info.num_physical_cores()
    if cores < 1:
        cores = 1
    return _train_impl[True](
        params, x_flat, y, n_seq, seq_len, input_dim, x_val_flat, y_val,
        n_val, epochs, batch_size, lr, dropout, patience, seed, cores,
    )


def seq2_train_scalar(
    params: Seq2Params,
    x_flat: List[Float64],
    y: List[Float64],
    n_seq: Int,
    seq_len: Int,
    input_dim: Int,
    x_val_flat: List[Float64],
    y_val: List[Float64],
    n_val: Int,
    epochs: Int,
    batch_size: Int,
    lr: Float64,
    dropout: Float64,
    patience: Int,
    seed: Int,
) -> Seq2TrainResult:
    """Single-threaded, scalar (non-SIMD) build of the identical training
    loop. Benchmark baseline for the vectorized/parallel paths; numerics
    can differ from the SIMD build only by floating-point reduction order
    inside dot products."""
    return _train_impl[False](
        params, x_flat, y, n_seq, seq_len, input_dim, x_val_flat, y_val,
        n_val, epochs, batch_size, lr, dropout, patience, seed, 1,
    )
