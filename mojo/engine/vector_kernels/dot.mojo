"""
vector_kernels/dot.mojo — SIMD Float32 dot product and cosine similarity kernels.

64-element Float32 vectors fit exactly in 8 × 8-wide SIMD registers (no tail).
All functions accept List[Float32] of length ≥ 64; the unsafe_ptr() is taken
internally so callers stay in safe Mojo territory.

Public API:
  VEC_DIM           — comptime constant: 64
  dot64_f32         — dot product of two 64-dim Float32 vectors (SIMD 8-wide)
  l2_norm_inv_f32   — 1/||v|| for a 64-dim Float32 vector
  cosine64_f32      — cosine similarity (uses pre-computed norm inverses)
  build_vec64_f32   — encode a String as a 64-bucket bigram freq vector (L2-normed)
"""

from std.math import sqrt


comptime VEC_DIM: Int = 64   # must be a multiple of SIMD_W below
comptime SIMD_W:  Int = 8    # 8 × Float32 = 256-bit (AVX / NEON)


# ── SIMD dot product ──────────────────────────────────────────────────────────

fn dot64_f32(a: List[Float32], b: List[Float32]) -> Float32:
    """
    Dot product of two 64-element Float32 vectors.

    Unrolled 8 × 8-wide SIMD multiply-accumulate — no loop overhead.
    VEC_DIM=64 / SIMD_W=8 = 8 independent accumulators (instruction-level parallelism).
    """
    var pa = a.unsafe_ptr()
    var pb = b.unsafe_ptr()
    var acc0 = (pa +  0).load[width=SIMD_W]() * (pb +  0).load[width=SIMD_W]()
    var acc1 = (pa +  8).load[width=SIMD_W]() * (pb +  8).load[width=SIMD_W]()
    var acc2 = (pa + 16).load[width=SIMD_W]() * (pb + 16).load[width=SIMD_W]()
    var acc3 = (pa + 24).load[width=SIMD_W]() * (pb + 24).load[width=SIMD_W]()
    var acc4 = (pa + 32).load[width=SIMD_W]() * (pb + 32).load[width=SIMD_W]()
    var acc5 = (pa + 40).load[width=SIMD_W]() * (pb + 40).load[width=SIMD_W]()
    var acc6 = (pa + 48).load[width=SIMD_W]() * (pb + 48).load[width=SIMD_W]()
    var acc7 = (pa + 56).load[width=SIMD_W]() * (pb + 56).load[width=SIMD_W]()
    return ((acc0 + acc1) + (acc2 + acc3) + (acc4 + acc5) + (acc6 + acc7)).reduce_add()


# ── L2 norm inverse ───────────────────────────────────────────────────────────

fn l2_norm_inv_f32(v: List[Float32]) -> Float32:
    """
    Compute 1/||v||₂ for a 64-element Float32 vector.
    Returns 0.0 if the vector is the zero vector.
    """
    var p = v.unsafe_ptr()
    var sq0 = (p +  0).load[width=SIMD_W]()
    var sq1 = (p +  8).load[width=SIMD_W]()
    var sq2 = (p + 16).load[width=SIMD_W]()
    var sq3 = (p + 24).load[width=SIMD_W]()
    var sq4 = (p + 32).load[width=SIMD_W]()
    var sq5 = (p + 40).load[width=SIMD_W]()
    var sq6 = (p + 48).load[width=SIMD_W]()
    var sq7 = (p + 56).load[width=SIMD_W]()

    var mag_sq = (
        (sq0*sq0 + sq1*sq1) +
        (sq2*sq2 + sq3*sq3) +
        (sq4*sq4 + sq5*sq5) +
        (sq6*sq6 + sq7*sq7)
    ).reduce_add()

    if mag_sq <= 0.0:
        return Float32(0.0)
    return Float32(1.0) / sqrt(mag_sq)


# ── Cosine similarity ─────────────────────────────────────────────────────────

fn cosine64_f32(
    a:          List[Float32],
    b:          List[Float32],
    a_norm_inv: Float32,
    b_norm_inv: Float32,
) -> Float32:
    """
    Cosine similarity between two 64-dim Float32 vectors.

    Both norm_inv values must be pre-computed with l2_norm_inv_f32().
    Returns 0.0 for zero vectors, clamps result to [0.0, 1.0].
    """
    if a_norm_inv == 0.0 or b_norm_inv == 0.0:
        return Float32(0.0)
    var raw = dot64_f32(a, b) * a_norm_inv * b_norm_inv
    if raw > 1.0:
        return Float32(1.0)
    if raw < 0.0:
        return Float32(0.0)
    return raw


# ── String → 64-bucket bigram vector ─────────────────────────────────────────

@always_inline
fn _norm_byte64(c: UInt8) -> UInt8:
    """Normalise byte: separators → 32, uppercase → lowercase."""
    if c == 95 or c == 45 or c == 46:
        return 32
    if c >= 65 and c <= 90:
        return c + 32
    return c


fn build_vec64_f32(s: String, mut out_vec: List[Float32]) -> Float32:
    """
    Encode a string as a 64-bucket bigram frequency vector.

    Hashes each consecutive normalised-byte pair into [0, 63].
    Output vector is L2-normalised. Returns the norm_inv scalar.

    out_vec must be a List[Float32] of length ≥ VEC_DIM (will be zeroed).
    Avoids intermediate string allocation — normalises bytes in-place.
    """
    for i in range(VEC_DIM):
        out_vec[i] = Float32(0.0)
    var sb = s.as_bytes()
    var n  = len(sb)
    if n == 0:
        return Float32(0.0)
    var prev = _norm_byte64(sb[0])
    for i in range(1, n):
        var cur = _norm_byte64(sb[i])
        var h = (Int(prev) * 31 + Int(cur)) & (VEC_DIM - 1)
        out_vec[h] += Float32(1.0)
        prev = cur
    return l2_norm_inv_f32(out_vec)
