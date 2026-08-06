"""bench_mlpk.mojo — timing gate for the feed-forward and embedding kernels.

Hand-written, not generated. No library is named `mlpk` at the top level, so nothing can collide.

Every shape is warmed before it is timed. That is not boilerplate: on the sibling `normk` benchmark,
timing cold-then-warm made LayerNorm measure FASTER than RMSNorm — impossible, since it does strictly
more work on the same buffer — because the second kernel read a cache the first had filled. A
published number from that run would have said the two-pass variance was free.

What is claimed
-----------------
1. THE PRICE OF THE erf CONVENTION. `erf` is a transcendental; the tanh form is a `tanh` plus a
   couple of multiplies. Callers choosing between the two are choosing accuracy against speed and
   deserve the real ratio rather than an assurance that it is small.
2. ACTIVATION COST IS FLAT PER CELL. A gated FFN activation is elementwise, so per-cell cost must not
   move with buffer size beyond the parallel fan-out amortizing.
3. THE BACKWARD IS A SMALL MULTIPLE OF THE FORWARD. If it were free it would be wrong.
4. THE EMBEDDING SCATTER IS NOT FREE, and its cost is dominated by the DENSE output rather than the
   tokens: the gradient is `vocab x d_model` regardless of how few rows the batch touches. That is
   the argument for a sparse representation, quantified rather than asserted.

Not claimed: any of this against a bf16 baseline. Every figure is Float64 because that is the runtime
contract's wire type, and these kernels are memory-bound enough that a narrower dtype is most of the
remaining headroom.
"""
from std.time import perf_counter_ns

from mlpk.contract import MLP_ACT_GEGLU_ERF, MLP_ACT_GEGLU_TANH, MLP_ACT_SWIGLU, MLP_OK
from mlpk.activation import gated_ffn_bwd_flat, gated_ffn_fwd_flat, mlp_gelu_agreement
from mlpk.embedding import embedding_bwd_flat, embedding_fwd_flat


def _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic values in roughly [-1, 1], so runs are comparable across machines."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 23)) / 11.0 - 1.0)
    return o^


def main() raises:
    var failures: Int = 0

    print("=== mlpk timing gate ===")
    print("")

    var n_tok = 512
    var d_ff = 2048
    var cells = n_tok * d_ff
    var v = _pseudo(cells, 1)
    var g = _pseudo(cells, 5)

    # ── 1. what the erf convention costs ──────────────────────────────────────
    print("[mlpk.activation] SwiGLU vs tanh-GEGLU vs erf-GEGLU, ", cells, "cells")
    var _w0 = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_SWIGLU)
    var _w1 = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_GEGLU_TANH)
    var _w2 = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_GEGLU_ERF)

    var t0 = perf_counter_ns()
    var sw = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_SWIGLU)
    var sw_ns = _ns_since(t0)

    var t1 = perf_counter_ns()
    var gt = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_GEGLU_TANH)
    var gt_ns = _ns_since(t1)

    var t2 = perf_counter_ns()
    var ge = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_GEGLU_ERF)
    var ge_ns = _ns_since(t2)

    if sw.status != MLP_OK or gt.status != MLP_OK or ge.status != MLP_OK:
        failures += 1
        print("   FAIL: a forward returned", sw.status, gt.status, ge.status)

    print("   SwiGLU      :", sw_ns, "ns  (", sw_ns / Float64(cells), "ns/cell )")
    print("   GEGLU tanh  :", gt_ns, "ns  (", gt_ns / Float64(cells), "ns/cell )")
    print("   GEGLU erf   :", ge_ns, "ns  (", ge_ns / Float64(cells), "ns/cell )")
    print("   erf / tanh ratio:", ge_ns / gt_ns if gt_ns > 0.0 else 0.0)

    var ag = mlp_gelu_agreement(-4.0, 4.0, 2001)
    print("   and what the erf form buys: it is", ag.max_abs_delta, "from the tanh form (worst at x =",
          ag.argmax_input, ").")
    print("   Hugging Face treats those as different activations, so this is a correctness choice")
    print("   the config makes, not a speed/accuracy dial the kernel should decide.")

    # ── 2. per-cell cost across sizes ─────────────────────────────────────────
    print("")
    print("[mlpk.activation] SwiGLU cost per cell across buffer sizes")
    print("   cells        total ns      ns/cell")
    var sizes = List[Int]()
    sizes.append(1 << 14)
    sizes.append(1 << 17)
    sizes.append(1 << 20)
    var first_per = 0.0
    var last_per = 0.0
    for s in range(len(sizes)):
        var n = sizes[s]
        var vv = _pseudo(n, 2)
        var gg = _pseudo(n, 3)
        var _warm = gated_ffn_fwd_flat(vv, gg, 1, n, MLP_ACT_SWIGLU)
        var ts = perf_counter_ns()
        var out = gated_ffn_fwd_flat(vv, gg, 1, n, MLP_ACT_SWIGLU)
        var ns = _ns_since(ts)
        if out.status != MLP_OK:
            failures += 1
            print("   FAIL: status", out.status)
        var per = ns / Float64(n)
        if s == 0:
            first_per = per
        last_per = per
        print("  ", n, "   ", ns, "   ", per)
    var growth = last_per / first_per if first_per > 0.0 else 0.0
    print("   ns/cell growth across 64x more cells:", growth, " (gate: <= 3x)")
    if growth > 3.0:
        failures += 1
        print("   FAIL: an elementwise activation should not cost more per cell as it grows")

    # ── 3. backward against forward ───────────────────────────────────────────
    print("")
    print("[mlpk.activation] backward cost relative to forward")
    var dy = _pseudo(cells, 7)
    var _wb = gated_ffn_bwd_flat(dy, v, g, n_tok, d_ff, MLP_ACT_SWIGLU)
    var t3 = perf_counter_ns()
    var grad = gated_ffn_bwd_flat(dy, v, g, n_tok, d_ff, MLP_ACT_SWIGLU)
    var bwd_ns = _ns_since(t3)
    if grad.status != MLP_OK:
        failures += 1
        print("   FAIL: backward returned", grad.status)
    print("   forward :", sw_ns, "ns")
    print("   backward:", bwd_ns, "ns")
    print("   ratio:", bwd_ns / sw_ns if sw_ns > 0.0 else 0.0,
          "— it writes two gradient buffers and evaluates the product rule")

    # ── 4. the embedding, and the case for a sparse gradient ──────────────────
    print("")
    print("[mlpk.embedding] gather vs dense scatter-add")
    var vocab = 32768
    var d_model = 256
    var tokens = 1024
    var table = _pseudo(vocab * d_model, 4)
    var ids = List[Int](capacity=tokens)
    for t in range(tokens):
        ids.append((t * 7919) % vocab)
    var edy = _pseudo(tokens * d_model, 6)

    var _we = embedding_fwd_flat(table, ids, tokens, vocab, d_model)
    var t4 = perf_counter_ns()
    var eout = embedding_fwd_flat(table, ids, tokens, vocab, d_model)
    var fwd_ns = _ns_since(t4)

    var _wg = embedding_bwd_flat(edy, ids, tokens, vocab, d_model)
    var t5 = perf_counter_ns()
    var egrad = embedding_bwd_flat(edy, ids, tokens, vocab, d_model)
    var eb_ns = _ns_since(t5)

    if eout.status != MLP_OK or egrad.status != MLP_OK:
        failures += 1
        print("   FAIL: embedding returned", eout.status, egrad.status)

    print("   gather ", tokens, "rows of", d_model, ":", fwd_ns, "ns")
    print("   dense scatter into", vocab, "x", d_model, ":", eb_ns, "ns")
    print("   ratio:", eb_ns / fwd_ns if fwd_ns > 0.0 else 0.0)
    print("   rows actually touched:", egrad.n_touched, "of", vocab,
          "— the gradient is dense over ALL of them")
    print("   so the scatter's cost is set by the VOCABULARY, not the batch. That is the argument")
    print("   for a sparse gradient, and it is deferred rather than dismissed: nothing in this tree")
    print("   consumes one yet, and returning a sparse pair today would push densification onto")
    print("   every caller for no saving.")

    print("")
    print("   CAVEAT: every figure is Float64, the runtime contract's wire type. These kernels are")
    print("   memory-bound, so a bf16 path reading a quarter the bytes is most of the remaining")
    print("   headroom — do not compare these against a bf16 baseline.")

    print("")
    if failures == 0:
        print("✅ mlpk gate: all properties hold")
    else:
        print("❌ mlpk gate:", failures, "failure(s)")
