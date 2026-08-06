"""
semantic_micro/semantic_mlp.mojo — Linear layer, ReLU, and 2-layer head forward.

Each classification head is:
    fc1: EMB_DIM → HIDDEN_DIM  (+ ReLU)
    fc2: HIDDEN_DIM → n_classes
    softmax + argmax → (class_id, confidence)

SIMD is used in the linear layers where the dimension is a multiple of SIMD_W:
    fc1 weight rows: HIDDEN_DIM=24 = 3 SIMD_W chunks    fc2 weight rows: max(INTENT=4, AGG=6, FAMILY=4) → scalar (small enough)
    dot over input:  EMB_DIM=32 = 4 SIMD_W chunks (fc1)
                     HIDDEN_DIM=24 = 3 SIMD_W chunks (fc2)
"""

from std.math import exp
from mojo.engine.vector_kernels.semantic_micro.semantic_types import (
    LinearLayer,
    EMB_DIM, HIDDEN_DIM, EMB_CHUNKS, HIDDEN_CHUNKS, SIMD_W,
    INTENT_CLASSES, AGG_CLASSES, FAMILY_CLASSES,
    INTENT_CONF_THRESHOLD, AGG_CONF_THRESHOLD, FAMILY_CONF_THRESHOLD,
    HINT_NONE,
)


# ── Scalar linear (used for small out_dim layers and fallback) ────────────────

@always_inline
def linear_forward_scalar(
    layer:  LinearLayer,
    x_in:   UnsafePointer[Float32],
    x_out:  UnsafePointer[Float32],
):
    """
    Dense linear pass: x_out[o] = bias[o] + dot(weight[o,:], x_in).
    Pure scalar — used when dimensions are not SIMD-friendly.
    """
    for o in range(Int(layer.out_dim)):
        var acc: Float32 = layer.bias[o]
        var w_row = layer.weight + o * Int(layer.in_dim)
        for i in range(Int(layer.in_dim)):
            acc += w_row[i] * x_in[i]
        x_out[o] = acc


# ── SIMD linear fc1: in=EMB_DIM, out=HIDDEN_DIM ──────────────────────────────

@always_inline
def linear_fc1(
    layer:  LinearLayer,
    x_in:   UnsafePointer[Float32],    # [EMB_DIM]
    x_out:  UnsafePointer[Float32],    # [HIDDEN_DIM]
):
    """
    fc1 forward: EMB_DIM(32) → HIDDEN_DIM(24).
    Input dot uses 4 SIMD chunks (EMB_CHUNKS).
    One output neuron per outer loop iteration.
    """
    for o in range(HIDDEN_DIM):
        var w_row = layer.weight + o * EMB_DIM
        var acc = SIMD[DType.float32, SIMD_W](Float32(0.0))
        @parameter
        for c in range(EMB_CHUNKS):
            acc += (w_row + c * SIMD_W).load[width=SIMD_W]() * \
                   (x_in  + c * SIMD_W).load[width=SIMD_W]()
        x_out[o] = layer.bias[o] + acc.reduce_add()


# ── SIMD linear fc2: in=HIDDEN_DIM, out=n_classes (small) ────────────────────

@always_inline
def linear_fc2(
    layer:  LinearLayer,
    x_in:   UnsafePointer[Float32],    # [HIDDEN_DIM]
    x_out:  UnsafePointer[Float32],    # [out_dim]
):
    """
    fc2 forward: HIDDEN_DIM(24) → n_classes (4–6).
    Input dot uses 3 SIMD chunks (HIDDEN_CHUNKS).
    """
    for o in range(Int(layer.out_dim)):
        var w_row = layer.weight + o * HIDDEN_DIM
        var acc = SIMD[DType.float32, SIMD_W](Float32(0.0))
        @parameter
        for c in range(HIDDEN_CHUNKS):
            acc += (w_row + c * SIMD_W).load[width=SIMD_W]() * \
                   (x_in  + c * SIMD_W).load[width=SIMD_W]()
        x_out[o] = layer.bias[o] + acc.reduce_add()


# ── ReLU ──────────────────────────────────────────────────────────────────────

@always_inline
def relu_hidden(x: UnsafePointer[Float32]):
    """In-place ReLU over HIDDEN_DIM elements (SIMD-unrolled)."""
    var z = SIMD[DType.float32, SIMD_W](Float32(0.0))
    @parameter
    for c in range(HIDDEN_CHUNKS):
        var v = (x + c * SIMD_W).load[width=SIMD_W]()
        # max(0, v) — select v where v > 0 else 0
        (x + c * SIMD_W).store(v.max(z))


# ── Numerically-stable softmax (in-place, max-subtracted) ────────────────────

@always_inline
def softmax_inplace(logits: UnsafePointer[Float32], n: Int):
    """Numerically-stable softmax over the first n elements."""
    var max_val = logits[0]
    for i in range(1, n):
        if logits[i] > max_val:
            max_val = logits[i]
    var sum_exp = Float32(0.0)
    for i in range(n):
        var e = exp(logits[i] - max_val)
        logits[i] = e
        sum_exp += e
    var inv = Float32(1.0) / sum_exp
    for i in range(n):
        logits[i] *= inv


# ── Argmax with confidence ────────────────────────────────────────────────────

@always_inline
def argmax_conf(
    probs: UnsafePointer[Float32],
    n:     Int,
    out_cls:  UnsafePointer[UInt8],
    out_conf: UnsafePointer[Float32],
):
    """
    Find argmax of probability array; write class id and probability.
    Assumes probs are already softmax-normalized (sum to 1.0).
    """
    var best_cls  = UInt8(0)
    var best_prob = probs[0]
    for i in range(1, n):
        if probs[i] > best_prob:
            best_prob = probs[i]
            best_cls  = UInt8(i)
    out_cls[0]  = best_cls
    out_conf[0] = best_prob


# ── Full 2-layer head (embed → fc1 → ReLU → fc2 → softmax → argmax) ─────────

@always_inline
def run_head(
    fc1:         LinearLayer,
    fc2:         LinearLayer,
    query_vec:   UnsafePointer[Float32],   # [EMB_DIM] input (read-only)
    hidden_buf:  UnsafePointer[Float32],   # [HIDDEN_DIM] scratch (overwritten)
    logits_buf:  UnsafePointer[Float32],   # [fc2.out_dim] scratch (overwritten)
    threshold:   Float32,
    out_cls:     UnsafePointer[UInt8],
    out_conf:    UnsafePointer[Float32],
):
    """
    Run one classification head end-to-end.
    If argmax confidence < threshold, writes HINT_NONE to out_cls.
    """
    linear_fc1(fc1, query_vec, hidden_buf)
    relu_hidden(hidden_buf)
    linear_fc2(fc2, hidden_buf, logits_buf)
    softmax_inplace(logits_buf, Int(fc2.out_dim))
    argmax_conf(logits_buf, Int(fc2.out_dim), out_cls, out_conf)
    if out_conf[0] < threshold:
        out_cls[0]  = HINT_NONE
        out_conf[0] = Float32(0.0)
