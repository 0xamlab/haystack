"""
mlpk.gated_ffn — fused gated feed-forward activations over flat Float64 buffers. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: none
benchmark: benchmarks/mojo_benchmarks/bench_vs_torch_feed_forward.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Why this module exists: `activations.swiglu` is not a kernel
--------------------------------------------------------------
`activations.mojo` has `swiglu(x, gate) -> Float64`, `swish`, `gelu`, `gelu_fast` and `gelu_new`, and
every one of them takes and returns a single `Float64`. They are correct scalar algebra and they are
frozen. What they are not is a thing you can put opposite `F.silu(gate) * up`: that torch expression
walks two arrays and writes a third, and the entire cost of a gated feed-forward's activation stage is
that memory traffic, not the sigmoid. Timing a one-element function against it compares different
quantities, and no ratio between them means anything. This module is the missing driver — additive, in
its own namespace, with `activations.mojo` untouched and used as the correctness oracle.

Three GELU spellings, one function
------------------------------------
The frozen tree has `gelu`, `gelu_fast` and `gelu_new`, presented as three variants. They are
algebraically the same function:

    gelu_fast:  0.5*x*(1 + tanh(C*(x + 0.044715*x^3)))
    gelu_new:   x*0.5*(1 + tanh(C*x*(1 + 0.044715*x^2)))     <- C*x*(1+ax^2) == C*(x+ax^3)
    gelu:       x*0.5*(1 + tanh(C'*(x + 0.044715*x^3)))      <- C' = 0.7978845608, C truncated at 10 dp

All three are the *tanh approximation*, and `gelu`'s docstring claiming "exact ... x x 0.5 x (1 +
erf(x/sqrt2))" describes a formula the body does not compute. There is no erf-form GELU anywhere in
the tree, so `F.gelu(approximate='none')` had nothing to be compared against. `geglu_erf_gate` below
is that missing form, built on `std.math.erf`, and `geglu_tanh_gate` matches `approximate='tanh'`.
Choosing the wrong one turns a 4.7e-4 algorithm difference (measured, tanh form vs erf form over
x in [-6,6]) into what looks like a correctness failure.

One pass, not three
---------------------
`F.silu(g) * u` in torch eager is two kernels — `aten::silu` then `aten::mul`, confirmed by profiler op
names, no fusion. That is read g, write s, read s, read u, write o: 40 bytes per element at f64.
Fusing the gate into the multiply makes it read g, read u, write o: 24 bytes per element. On a
bandwidth-bound elementwise stage that ratio *is* the speedup available, and it is why this kernel is
worth writing at all rather than a fresh spelling of the same arithmetic.

Vectorisation and the parallel threshold
------------------------------------------
`W = simd_width_of[DType.float64]()` is 2 on this host (128-bit NEON), so the inner loop runs four
independent `W`-wide streams — 8 elements per iteration — to keep the transcendental and the FMA off a
single dependency chain. Workers get contiguous bands, never interleaved indices: an interleaved split
measures cache-coherence traffic instead of bandwidth. Below `MLP_PARALLEL_MIN_ELEMS` the kernel drops
to one worker and *says so* in `workers_used`, because a row labelled with a thread count it did not
have is the circular error this whole exercise exists to avoid.

Allocation is inside the kernel, on purpose
---------------------------------------------
`out` is allocated with `unsafe_uninit_length` and every element is written exactly once, so it costs
one pass of stores and no zero-fill. It stays inside the kernel because the torch expression it is
compared against also allocates its output inside the call. Charging ourselves an allocation the
baseline does not pay — or dropping one it does — is the same rig in two directions.

Public API:
  swiglu_gate(gate, up, n, requested_workers)           -> GateResult
  geglu_tanh_gate(gate, up, n, requested_workers)       -> GateResult
  geglu_tanh_fast_gate(gate, up, n, requested_workers)  -> GateResult
  geglu_erf_gate(gate, up, n, requested_workers)        -> GateResult
  swiglu_ffn_block(x, wg, wu, wd, tokens, d_model, d_ff) -> BlockResult
  gate_bytes_moved(n)                              -> Float64
"""

from max.algorithm import parallelize
from std.math import erf, exp, tanh
from std.sys import info
from std.sys.info import simd_width_of

from gemm.blocked import sgemm_flat
from gemm.contract import GEMM_OK
from mlpk.contract import (
    MLP_BACKEND_CPU_SIMD,
    MLP_BACKEND_CPU_SIMD_PARALLEL,
    MLP_ERR_PROJECTION_FAILED,
    MLP_OK,
    mlp_block_dims_ok,
    mlp_pair_ok,
    mlp_workers_for,
)
from special_functions import erf as erf_frozen_as

comptime W: Int = simd_width_of[DType.float64]()

# 1/sqrt(2), for the erf-form GELU: Phi(x) = 0.5*(1 + erf(x/sqrt2)).
comptime INV_SQRT2: Float64 = 0.7071067811865476
# sqrt(2/pi), the tanh-approximation constant, full double precision.
comptime TANH_C: Float64 = 0.7978845608028654
comptime TANH_A: Float64 = 0.044715


@fieldwise_init
struct GateResult(Copyable, Movable):
    """A gated activation output, the thread count that produced it, and which kernel ran."""

    var out: List[Float64]
    var n: Int
    var workers_used: Int
    var backend_used: Int
    var bytes_moved: Float64
    var status: Int


@fieldwise_init
struct BlockResult(Copyable, Movable):
    """A full gated feed-forward block output plus the FLOP and byte counts it charged."""

    var out: List[Float64]
    var rows: Int
    var cols: Int
    var gate_workers: Int
    var flop_count: Float64
    var gate_bytes: Float64
    var status: Int


def gate_bytes_moved(n: Int) -> Float64:
    """Bytes a fused f64 gated activation must move: read gate, read up, write out.

    Args:
        n: Element count.

    Returns:
        Byte count, for a bandwidth fraction against the measured 271 GB/s NT-SIMD ceiling.
    """
    return 24.0 * Float64(n)


# ---------------------------------------------------------------------------------------------------
# Vector primitives. Each takes a `W`-wide gate vector and returns the activation applied to it, so the
# three drivers below differ only in this one call and share their loop, band split and tail handling.
# ---------------------------------------------------------------------------------------------------
@always_inline
def _swish_v(g: SIMD[DType.float64, W]) -> SIMD[DType.float64, W]:
    return g / (SIMD[DType.float64, W](1.0) + exp(-g))


@always_inline
def _gelu_tanh_v(g: SIMD[DType.float64, W]) -> SIMD[DType.float64, W]:
    var inner = SIMD[DType.float64, W](TANH_C) * (g + SIMD[DType.float64, W](TANH_A) * g * g * g)
    return SIMD[DType.float64, W](0.5) * g * (SIMD[DType.float64, W](1.0) + tanh(inner))


@always_inline
def _gelu_tanh_exp_v(g: SIMD[DType.float64, W]) -> SIMD[DType.float64, W]:
    """The same tanh-form GELU with `1 + tanh(y)` rewritten as `2 / (1 + exp(-2y))`.

    Not an approximation — an identity. It exists because `std.math.tanh` at f64 SIMD width 2 is the
    single most expensive thing in this file: 4,194,304 elements cost 40.8 ms through `tanh` and
    8.7 ms through this rewrite on the same buffer in the same process, 4.7x, with `exp` alone costing
    5.5 ms of that. The rounding differs (measured 1.18e-13 max abs between the two formulations over
    4.2M standard-normal inputs), so both are exposed rather than one being silently substituted for
    the other: `geglu_tanh_gate` is the accurate one, this is the fast one, and each row on the page
    carries its own measured error.

    No clamp is needed at the tails. For very negative y, `exp(-2y)` overflows to +inf and `2/inf` is
    0, which is the correct limit; for very positive y it underflows to 0 and the expression is 2.
    """
    var y = SIMD[DType.float64, W](TANH_C) * (g + SIMD[DType.float64, W](TANH_A) * g * g * g)
    var one_plus_tanh = SIMD[DType.float64, W](2.0) / (
        SIMD[DType.float64, W](1.0) + exp(SIMD[DType.float64, W](-2.0) * y)
    )
    return SIMD[DType.float64, W](0.5) * g * one_plus_tanh


@always_inline
def _gelu_erf_v(g: SIMD[DType.float64, W]) -> SIMD[DType.float64, W]:
    return (
        SIMD[DType.float64, W](0.5)
        * g
        * (SIMD[DType.float64, W](1.0) + erf(g * SIMD[DType.float64, W](INV_SQRT2)))
    )


@always_inline
def _gelu_erf_frozen_s(g: Float64) -> Float64:
    """The same value via the frozen `special_functions.erf`, kept as the accuracy counter-example.

    Measured max absolute error against `scipy.special.erf` over x in [-6, 6], 20001 points:

        std.math.erf            2.17e-08     <- what geglu_erf_gate uses, and it vectorises
        special_functions.erf   1.39e-07     <- the frozen A&S form, this function
        torch F.gelu('none')    4.44e-16     <- against the same scipy composition

    Neither Mojo path is a float64-accurate erf. `std.math.erf` is 6.4x closer than the frozen one and
    is the reason this is the shipped path, but it still carries a ~2e-8 floor, so the erf-form row is
    a float64 *container* holding a result about six digits short of float64. That is stated on the
    page as a loss rather than hidden behind the dtype label: torch's erf-form GELU is ~5e7 times more
    accurate than ours at the same nominal precision. This function stays so the gap can be
    re-measured rather than believed.
    """
    return 0.5 * g * (1.0 + erf_frozen_as(g * INV_SQRT2))


def swiglu_gate(
    gate: List[Float64], up: List[Float64], n: Int, requested_workers: Int
) -> GateResult:
    """out[i] = swish(gate[i]) * up[i], fused, SIMD, optionally parallel over contiguous bands.

    Matches `F.silu(gate) * up` elementwise. Ours is one pass; torch eager is two kernels.

    @capability swiglu_gate
    complexity: O(n)
    counts:
    - n <= len(gate) [kernel_validated]
    - n <= len(up) [kernel_validated]
    @endcapability
    """
    var shape = mlp_pair_ok(n, gate, up)
    if shape != MLP_OK:
        var empty = List[Float64]()
        return GateResult(empty^, 0, 0, MLP_BACKEND_CPU_SIMD, 0.0, shape)

    var workers = mlp_workers_for(n, requested_workers, info.num_physical_cores())
    var out = List[Float64](unsafe_uninit_length=n)
    var gp = gate.unsafe_ptr()
    var upp = up.unsafe_ptr()
    var op = out.unsafe_ptr()
    var nn = n
    var nw = workers

    @parameter
    def band(tid: Int) capturing:
        var each = nn // nw
        var lo = tid * each
        var hi = lo + each if tid < nw - 1 else nn
        var i = lo
        while i + 4 * W <= hi:
            var g0 = gp.load[width=W, alignment=8](i)
            var g1 = gp.load[width=W, alignment=8](i + W)
            var g2 = gp.load[width=W, alignment=8](i + 2 * W)
            var g3 = gp.load[width=W, alignment=8](i + 3 * W)
            var u0 = upp.load[width=W, alignment=8](i)
            var u1 = upp.load[width=W, alignment=8](i + W)
            var u2 = upp.load[width=W, alignment=8](i + 2 * W)
            var u3 = upp.load[width=W, alignment=8](i + 3 * W)
            op.store[width=W, alignment=8](i, _swish_v(g0) * u0)
            op.store[width=W, alignment=8](i + W, _swish_v(g1) * u1)
            op.store[width=W, alignment=8](i + 2 * W, _swish_v(g2) * u2)
            op.store[width=W, alignment=8](i + 3 * W, _swish_v(g3) * u3)
            i += 4 * W
        while i < hi:
            var g = gp[i]
            op[i] = (g / (1.0 + exp(-g))) * upp[i]
            i += 1

    if nw > 1:
        parallelize[band](nw, nw)
    else:
        band(0)
    var backend = MLP_BACKEND_CPU_SIMD_PARALLEL if nw > 1 else MLP_BACKEND_CPU_SIMD
    return GateResult(out^, n, workers, backend, gate_bytes_moved(n), MLP_OK)


def geglu_tanh_gate(
    gate: List[Float64], up: List[Float64], n: Int, requested_workers: Int
) -> GateResult:
    """out[i] = gelu_tanh(gate[i]) * up[i] — the tanh approximation, matching `F.gelu(approximate='tanh')`.

    @capability geglu_tanh_gate
    complexity: O(n)
    counts:
    - n <= len(gate) [kernel_validated]
    - n <= len(up) [kernel_validated]
    @endcapability
    """
    var shape = mlp_pair_ok(n, gate, up)
    if shape != MLP_OK:
        var empty = List[Float64]()
        return GateResult(empty^, 0, 0, MLP_BACKEND_CPU_SIMD, 0.0, shape)

    var workers = mlp_workers_for(n, requested_workers, info.num_physical_cores())
    var out = List[Float64](unsafe_uninit_length=n)
    var gp = gate.unsafe_ptr()
    var upp = up.unsafe_ptr()
    var op = out.unsafe_ptr()
    var nn = n
    var nw = workers

    @parameter
    def band(tid: Int) capturing:
        var each = nn // nw
        var lo = tid * each
        var hi = lo + each if tid < nw - 1 else nn
        var i = lo
        while i + 4 * W <= hi:
            var g0 = gp.load[width=W, alignment=8](i)
            var g1 = gp.load[width=W, alignment=8](i + W)
            var g2 = gp.load[width=W, alignment=8](i + 2 * W)
            var g3 = gp.load[width=W, alignment=8](i + 3 * W)
            op.store[width=W, alignment=8](i, _gelu_tanh_v(g0) * upp.load[width=W, alignment=8](i))
            op.store[
                width=W, alignment=8
            ](i + W, _gelu_tanh_v(g1) * upp.load[width=W, alignment=8](i + W))
            op.store[
                width=W, alignment=8
            ](i + 2 * W, _gelu_tanh_v(g2) * upp.load[width=W, alignment=8](i + 2 * W))
            op.store[
                width=W, alignment=8
            ](i + 3 * W, _gelu_tanh_v(g3) * upp.load[width=W, alignment=8](i + 3 * W))
            i += 4 * W
        while i < hi:
            var g = gp[i]
            var inner = TANH_C * (g + TANH_A * g * g * g)
            op[i] = 0.5 * g * (1.0 + tanh(inner)) * upp[i]
            i += 1

    if nw > 1:
        parallelize[band](nw, nw)
    else:
        band(0)
    var backend = MLP_BACKEND_CPU_SIMD_PARALLEL if nw > 1 else MLP_BACKEND_CPU_SIMD
    return GateResult(out^, n, workers, backend, gate_bytes_moved(n), MLP_OK)


def geglu_tanh_fast_gate(
    gate: List[Float64], up: List[Float64], n: Int, requested_workers: Int
) -> GateResult:
    """`geglu_tanh_gate` with the `exp` identity in place of `std.math.tanh`: 4.7x, 1.18e-13 apart.

    Same mathematical function, different rounding, its own row on the page. See `_gelu_tanh_exp_v`
    for the measurement and the reason both are kept.

    @capability geglu_tanh_fast_gate
    complexity: O(n)
    counts:
    - n <= len(gate) [kernel_validated]
    - n <= len(up) [kernel_validated]
    @endcapability
    """
    var shape = mlp_pair_ok(n, gate, up)
    if shape != MLP_OK:
        var empty = List[Float64]()
        return GateResult(empty^, 0, 0, MLP_BACKEND_CPU_SIMD, 0.0, shape)

    var workers = mlp_workers_for(n, requested_workers, info.num_physical_cores())
    var out = List[Float64](unsafe_uninit_length=n)
    var gp = gate.unsafe_ptr()
    var upp = up.unsafe_ptr()
    var op = out.unsafe_ptr()
    var nn = n
    var nw = workers

    @parameter
    def band(tid: Int) capturing:
        var each = nn // nw
        var lo = tid * each
        var hi = lo + each if tid < nw - 1 else nn
        var i = lo
        while i + 4 * W <= hi:
            var g0 = gp.load[width=W, alignment=8](i)
            var g1 = gp.load[width=W, alignment=8](i + W)
            var g2 = gp.load[width=W, alignment=8](i + 2 * W)
            var g3 = gp.load[width=W, alignment=8](i + 3 * W)
            op.store[
                width=W, alignment=8
            ](i, _gelu_tanh_exp_v(g0) * upp.load[width=W, alignment=8](i))
            op.store[
                width=W, alignment=8
            ](i + W, _gelu_tanh_exp_v(g1) * upp.load[width=W, alignment=8](i + W))
            op.store[
                width=W, alignment=8
            ](i + 2 * W, _gelu_tanh_exp_v(g2) * upp.load[width=W, alignment=8](i + 2 * W))
            op.store[
                width=W, alignment=8
            ](i + 3 * W, _gelu_tanh_exp_v(g3) * upp.load[width=W, alignment=8](i + 3 * W))
            i += 4 * W
        while i < hi:
            var g = gp[i]
            var y = TANH_C * (g + TANH_A * g * g * g)
            op[i] = 0.5 * g * (2.0 / (1.0 + exp(-2.0 * y))) * upp[i]
            i += 1

    if nw > 1:
        parallelize[band](nw, nw)
    else:
        band(0)
    var backend = MLP_BACKEND_CPU_SIMD_PARALLEL if nw > 1 else MLP_BACKEND_CPU_SIMD
    return GateResult(out^, n, workers, backend, gate_bytes_moved(n), MLP_OK)


def geglu_erf_gate(
    gate: List[Float64], up: List[Float64], n: Int, requested_workers: Int
) -> GateResult:
    """out[i] = 0.5*g*(1+erf(g/sqrt2)) * up[i] — the erf form, matching `F.gelu(approximate='none')`.

    This is the variant the frozen tree did not have. `activations.gelu` advertises the erf form in its
    docstring and computes the tanh approximation in its body, so `F.gelu(approximate='none')` had no
    counterpart to be compared against at all.

    On `std.math.erf`, not `special_functions.erf`: see `_gelu_erf_frozen_s`. Neither is float64
    accurate; the shipped one is 2.17e-8 against scipy where torch is 4.44e-16, and that gap is
    reported as a loss rather than absorbed by the dtype label.

    @capability geglu_erf_gate
    complexity: O(n)
    counts:
    - n <= len(gate) [kernel_validated]
    - n <= len(up) [kernel_validated]
    @endcapability
    """
    var shape = mlp_pair_ok(n, gate, up)
    if shape != MLP_OK:
        var empty = List[Float64]()
        return GateResult(empty^, 0, 0, MLP_BACKEND_CPU_SIMD, 0.0, shape)

    var workers = mlp_workers_for(n, requested_workers, info.num_physical_cores())
    var out = List[Float64](unsafe_uninit_length=n)
    var gp = gate.unsafe_ptr()
    var upp = up.unsafe_ptr()
    var op = out.unsafe_ptr()
    var nn = n
    var nw = workers

    @parameter
    def band(tid: Int) capturing:
        var each = nn // nw
        var lo = tid * each
        var hi = lo + each if tid < nw - 1 else nn
        var i = lo
        while i + 4 * W <= hi:
            var g0 = gp.load[width=W, alignment=8](i)
            var g1 = gp.load[width=W, alignment=8](i + W)
            var g2 = gp.load[width=W, alignment=8](i + 2 * W)
            var g3 = gp.load[width=W, alignment=8](i + 3 * W)
            op.store[width=W, alignment=8](i, _gelu_erf_v(g0) * upp.load[width=W, alignment=8](i))
            op.store[
                width=W, alignment=8
            ](i + W, _gelu_erf_v(g1) * upp.load[width=W, alignment=8](i + W))
            op.store[
                width=W, alignment=8
            ](i + 2 * W, _gelu_erf_v(g2) * upp.load[width=W, alignment=8](i + 2 * W))
            op.store[
                width=W, alignment=8
            ](i + 3 * W, _gelu_erf_v(g3) * upp.load[width=W, alignment=8](i + 3 * W))
            i += 4 * W
        while i < hi:
            var g = gp[i]
            op[i] = 0.5 * g * (1.0 + erf(g * INV_SQRT2)) * upp[i]
            i += 1

    if nw > 1:
        parallelize[band](nw, nw)
    else:
        band(0)
    var backend = MLP_BACKEND_CPU_SIMD_PARALLEL if nw > 1 else MLP_BACKEND_CPU_SIMD
    return GateResult(out^, n, workers, backend, gate_bytes_moved(n), MLP_OK)


def swiglu_ffn_block(
    x: List[Float64],
    wg: List[Float64],
    wu: List[Float64],
    wd: List[Float64],
    tokens: Int,
    d_model: Int,
    d_ff: Int,
) -> BlockResult:
    """A whole SwiGLU feed-forward block: down(swish(X@Wg) * (X@Wu)).

    Exists because the activation is not the layer. Three projections at `2*tokens*d_model*d_ff`,
    `2*tokens*d_model*d_ff` and `2*tokens*d_ff*d_model` FLOPs surround a gate that does `3*tokens*d_ff`
    of arithmetic, so an activation-only comparison can be won by a wide margin and still leave the
    end-to-end layer slower. The projections here are `gemm.blocked.sgemm_flat`, unmodified.

    @capability swiglu_ffn_block
    complexity: O(tokens*d_model*d_ff)
    counts:
    - tokens * d_model <= len(x) [kernel_validated]
    - d_model * d_ff <= len(wg) [kernel_validated]
    - d_model * d_ff <= len(wu) [kernel_validated]
    - d_ff * d_model <= len(wd) [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    var shape = mlp_block_dims_ok(tokens, d_model, d_ff, x, wg, wu, wd)
    if shape != MLP_OK:
        return BlockResult(empty^, 0, 0, 0, 0.0, 0.0, shape)

    var g = sgemm_flat(x, wg, tokens, d_ff, d_model, 1.0, 0.0, False, False)
    if g.status != GEMM_OK:
        var e1 = List[Float64]()
        return BlockResult(e1^, 0, 0, 0, 0.0, 0.0, MLP_ERR_PROJECTION_FAILED)
    var u = sgemm_flat(x, wu, tokens, d_ff, d_model, 1.0, 0.0, False, False)
    if u.status != GEMM_OK:
        var e2 = List[Float64]()
        return BlockResult(e2^, 0, 0, 0, 0.0, 0.0, MLP_ERR_PROJECTION_FAILED)

    var gated = swiglu_gate(g.c, u.c, tokens * d_ff, 0)
    if gated.status != MLP_OK:
        var e3 = List[Float64]()
        return BlockResult(e3^, 0, 0, 0, 0.0, 0.0, gated.status)

    var y = sgemm_flat(gated.out, wd, tokens, d_model, d_ff, 1.0, 0.0, False, False)
    # `.copy()`, not a transfer: a field cannot be moved out of the middle of a live struct, and the
    # alternative — returning `GemmResult` itself — would leak the projection's shape into this
    # package's return type. The copy is `tokens * d_model` elements, it is charged to US inside the
    # timed region, and it is reported rather than subtracted. Erring toward paying a cost the baseline
    # does not is the only safe direction for a published ratio.
    var y_status = y.status
    var y_out = y.c.copy()
    if y_status != GEMM_OK:
        var e4 = List[Float64]()
        return BlockResult(e4^, 0, 0, 0, 0.0, 0.0, MLP_ERR_PROJECTION_FAILED)

    var flops = (
        2.0 * Float64(tokens) * Float64(d_model) * Float64(d_ff) * 2.0
        + 2.0 * Float64(tokens) * Float64(d_ff) * Float64(d_model)
        + 3.0 * Float64(tokens) * Float64(d_ff)
    )
    return BlockResult(
        y_out^, tokens, d_model, gated.workers_used, flops, gated.bytes_moved, MLP_OK
    )
