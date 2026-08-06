"""test_vector_kernels_dot.mojo — hand-written tests for vector_kernels.dot.

Hand-written because the A-Z generator synthesizes Float64 fixtures only; these kernels
take Float32 vectors of exactly VEC_DIM=64 lanes. Covers known values on valid input and
the degenerate short/empty shapes from the audit battery (defined 0.0, no abort).
"""
from std.math import isnan, isinf
from vector_kernels.dot import dot64_f32, l2_norm_inv_f32, cosine64_f32, build_vec64_f32

def is_finite32(x: Float32) -> Bool:
    return not isnan(Float64(x)) and not isinf(Float64(x))

def approx(a: Float32, b: Float32, tol: Float32) -> Bool:
    var d = a - b
    if d < Float32(0.0):
        d = -d
    return d <= tol

def main() raises:
    # 64-lane vectors: a = 1.0 x 64, b = 2.0 x 64 → dot = 128.
    var a = List[Float32]()
    var b = List[Float32]()
    for _ in range(64):
        a.append(Float32(1.0))
        b.append(Float32(2.0))
    var d = dot64_f32(a, b)
    if not approx(d, Float32(128.0), Float32(1e-3)):
        raise Error("dot64_f32 known value failed")

    var n_inv = l2_norm_inv_f32(a)  # 1/sqrt(64) = 0.125
    if not approx(n_inv, Float32(0.125), Float32(1e-4)):
        raise Error("l2_norm_inv_f32 known value failed")

    var c = cosine64_f32(a, b, n_inv, l2_norm_inv_f32(b))
    if not is_finite32(c):
        raise Error("cosine64_f32 must be finite")
    # Parallel constant vectors → cosine 1.
    if not approx(c, Float32(1.0), Float32(1e-3)):
        raise Error("cosine64_f32 of parallel vectors must be 1")

    # out_vec must arrive pre-sized (kernel zeroes and fills in place).
    var out = List[Float32]()
    for _ in range(64):
        out.append(Float32(9.9))
    var s = build_vec64_f32("unit_price", out)
    if not is_finite32(s):
        raise Error("build_vec64_f32 norm must be finite")
    if len(out) != 64:
        raise Error("build_vec64_f32 must keep 64 lanes")
    # The bigram vector of a non-empty string is non-zero and L2-normalised, so its
    # norm_inv is positive and finite.
    if not (s > Float32(0.0)):
        raise Error("build_vec64_f32 norm_inv must be positive for a non-empty string")

    # ── degenerate shapes from the audit battery must not abort ──
    var empty = List[Float32]()
    var zero_dot = dot64_f32(empty, b)
    if not approx(zero_dot, Float32(0.0), Float32(0.0)):
        raise Error("dot64_f32 empty-a must return 0")
    var zero_norm = l2_norm_inv_f32(empty)
    if not is_finite32(zero_norm):
        raise Error("l2_norm_inv_f32 empty must stay finite")
    # build_vec64_f32 with a short out_vec returns 0.0 without writing (the guard).
    var short_out = List[Float32]()
    short_out.append(Float32(1.0))
    var short_res = build_vec64_f32("unit_price", short_out)
    if not approx(short_res, Float32(0.0), Float32(0.0)):
        raise Error("build_vec64_f32 short out_vec must return 0")
    if len(short_out) != 1:
        raise Error("build_vec64_f32 short out_vec must stay untouched")
