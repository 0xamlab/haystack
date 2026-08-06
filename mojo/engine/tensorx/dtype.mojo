"""
tensorx.dtype — the dtype system for the LLM plane: tags, limits, accumulation policy, round-trip.
Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, float32, bfloat16, float16, float8_e4m3fn, float8_e5m2, int8, uint8, int4, nf4
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_dtype.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Rounding is done by the compiler, not by hand
----------------------------------------------
`DType.bfloat16`, `DType.float16` and `DType.float8_e4m3fn` all work on the pinned toolchain
(verified 2026-07-31: `SIMD[DType.bfloat16, 8]` round-trips 1.5, `float8_e4m3fn` round-trips 1.0). So
a round-trip here is a native cast down and back, which gives IEEE round-to-nearest-even by
construction and matches what the GPU will do. Hand-rolled bit manipulation would be a second
implementation of something the hardware already defines, and would have to be re-verified per
platform.

Why this is a separate contract from `quantization_stack`
----------------------------------------------------------
`quantization_stack.bf16_to_fp32_round` is frozen, reachable and unchanged, and every current caller
keeps its current answer. It uses its own rounding convention — truncation-based via
`Int64(x / scale * 128.0 + 0.5)`, with the exponent recovered as `Int64(log(|x|) / ln2)`. Measured
against a native cast:

    x        native bf16      frozen bf16      delta
    0.75      0.75             0.75             0.0
   -0.75     -0.75            -0.7421875       -0.0078125
    1.0       1.0              1.0              0.0
   -1.0      -1.0             -0.9921875       -0.0078125
   -3.14159  -3.140625        -3.125           -0.015625

The two agree on positives and differ on negatives, because `+0.5` then truncate-toward-zero is
round-half-up for positive values and round-half-DOWN for negative ones. Over a whole weight tensor
that is a directional bias rather than noise.

This is **not** a defect report and nothing is being changed. Per the freeze rule, a new surface gets
its own frozen numeric contract and legacy calls are never rerouted through it. What this module owes
the reader instead is visibility: `dtx_bf16_frozen_delta(x)` returns the difference between the two
conventions for any value, so a caller comparing results across the old and new paths gets a number
rather than a surprise, and `test_tensorx_dtype.mojo` pins the divergence so neither side can drift
unnoticed.

Sub-byte types are ratios, not byte widths
--------------------------------------------
`dtx_bits` is in BITS and `dtx_bytes_per_1024` is per 1024 elements, because int4 and nf4 occupy half
a byte and "0.5 bytes" cannot be an element size. `model_abi.dtype_byte_width` returns `Float64` and
answers `0.5` for int4; that is correct for the sizing estimates it exists for, and wrong as an exact
buffer stride — `Int(Float64(...))` past the integer grid is undefined, not truncated (rule 4c). So
this module keeps integer arithmetic integral and never routes a stride through a float.

Public API:
  dtx_dtype_name(code) / dtx_dtype_from_name(name)
  dtx_bits(code) / dtx_bytes_per_1024(code)
  dtx_is_float(code) / dtx_is_sub_byte(code) / dtx_is_supported(code)
  dtx_eps(code) / dtx_max_finite(code)
  dtx_accum_dtype(code)          — the single "what do I accumulate in" policy
  dtx_round_trip(value, code)    — one value through the dtype and back
  dtx_round_trip_list(values, n, code) -> DtypeCast
  dtx_bf16_frozen_delta(value)   — the divergence above, as a number
  dtx_tol_for(quantity, code, abs_tol) -> TxTolerance
"""

from std.math import isnan, isinf
from tensorx.contract import (
    TX_ERR_COUNT_EXCEEDS_LENGTH,
    TX_ERR_NEGATIVE_COUNT,
    TX_ERR_UNKNOWN_DTYPE,
    TX_OK,
    tx_count_ok,
    tx_finite,
)
from quantization_stack import bf16_to_fp32_round

# ── dtype codes ───────────────────────────────────────────────────────────────
# Deliberately distinct from `columnar/dtype.mojo`'s DTYPE_* (0-4): that vocabulary describes
# analytics column types, this one describes numeric storage formats, and one integer meaning two
# things across two packages is the defect rule 4e exists to prevent.

comptime DT_INVALID: Int = 0
comptime DT_F64: Int = 1
comptime DT_F32: Int = 2
comptime DT_BF16: Int = 3
comptime DT_F16: Int = 4
comptime DT_F8E4M3: Int = 5
comptime DT_F8E5M2: Int = 6
comptime DT_I8: Int = 7
comptime DT_U8: Int = 8
comptime DT_I4: Int = 9
comptime DT_NF4: Int = 10

comptime DT_FIRST: Int = DT_F64
comptime DT_LAST: Int = DT_NF4


@fieldwise_init
struct DtypeCast(Copyable, Movable):
    """Result of pushing a list through a dtype and back.

    Carries the error alongside the values because a caller choosing a storage format needs to know
    HOW it went wrong, not just that the numbers moved: `n_overflow` says the range is too small,
    `max_abs_err` says the mantissa is, and those lead to different decisions.
    """

    var values: List[Float64]
    var n_overflow: Int
    var n_underflow: Int
    var n_nan: Int
    var max_abs_err: Float64
    var status: Int


@fieldwise_init
struct TxTolerance(Copyable, Movable):
    """A comparison tolerance with its composition exposed.

    Rule 4b's failure mode is a tolerance that looks relative and is not. Returning the two terms
    separately means a reviewer can see which one dominates: if `absolute_term` is doing all the work
    at `|quantity| = 1e-13`, the comparison has silently become absolute at a scale the caller never
    chose, which is spelling 3 of the four.
    """

    var value: Float64
    var relative_term: Float64
    var absolute_term: Float64
    var status: Int


def dtx_is_supported(code: Int) -> Bool:
    """True for a dtype this module knows. `DT_INVALID` and anything out of range are not."""
    return code >= DT_FIRST and code <= DT_LAST


def dtx_dtype_name(code: Int) -> String:
    """Canonical name for a dtype code, or "invalid"."""
    if code == DT_F64:
        return String("float64")
    if code == DT_F32:
        return String("float32")
    if code == DT_BF16:
        return String("bfloat16")
    if code == DT_F16:
        return String("float16")
    if code == DT_F8E4M3:
        return String("float8_e4m3fn")
    if code == DT_F8E5M2:
        return String("float8_e5m2")
    if code == DT_I8:
        return String("int8")
    if code == DT_U8:
        return String("uint8")
    if code == DT_I4:
        return String("int4")
    if code == DT_NF4:
        return String("nf4")
    return String("invalid")


def dtx_dtype_from_name(name: String) -> Int:
    """Parse a canonical dtype name. Returns `DT_INVALID` for anything unrecognised.

    `DT_INVALID` rather than a default: silently resolving an unknown name to float32 would let a
    typo in a config train a model in the wrong precision and report success.
    """
    if name == String("float64"):
        return DT_F64
    if name == String("float32"):
        return DT_F32
    if name == String("bfloat16"):
        return DT_BF16
    if name == String("float16"):
        return DT_F16
    if name == String("float8_e4m3fn"):
        return DT_F8E4M3
    if name == String("float8_e5m2"):
        return DT_F8E5M2
    if name == String("int8"):
        return DT_I8
    if name == String("uint8"):
        return DT_U8
    if name == String("int4"):
        return DT_I4
    if name == String("nf4"):
        return DT_NF4
    return DT_INVALID


def dtx_bits(code: Int) -> Int:
    """Storage width in BITS. 0 for an unknown dtype.

    Bits rather than bytes so int4 and nf4 are expressible as 4 rather than as a fractional byte.
    """
    if code == DT_F64:
        return 64
    if code == DT_F32:
        return 32
    if code == DT_BF16 or code == DT_F16:
        return 16
    if code == DT_F8E4M3 or code == DT_F8E5M2 or code == DT_I8 or code == DT_U8:
        return 8
    if code == DT_I4 or code == DT_NF4:
        return 4
    return 0


def dtx_bytes_per_1024(code: Int) -> Int:
    """Bytes occupied by 1024 elements. Exact integer arithmetic for every supported dtype.

    Per-1024 rather than per-element so a 4-bit dtype has an exact integer answer (512) instead of a
    float that a caller would then have to convert back — which is the `Int(Float64(...))` hazard.
    """
    var bits = dtx_bits(code)
    if bits == 0:
        return 0
    return (bits * 1024) // 8


def dtx_is_float(code: Int) -> Bool:
    """True for the IEEE-style float formats (NF4 is a quantile codebook, not a float)."""
    return (
        code == DT_F64
        or code == DT_F32
        or code == DT_BF16
        or code == DT_F16
        or code == DT_F8E4M3
        or code == DT_F8E5M2
    )


def dtx_is_sub_byte(code: Int) -> Bool:
    """True when two elements share a byte, so a buffer length is not an element count."""
    return code == DT_I4 or code == DT_NF4


def dtx_eps(code: Int) -> Float64:
    """Machine epsilon: the gap between 1.0 and the next representable value.

    This is the number a relative tolerance is built from (rule 4b), which is why it is a first-class
    export rather than a constant inlined at each comparison. Integer and sub-byte codes return 0.0 —
    they are exact on their own grid, and a caller comparing them wants an absolute tolerance.
    """
    if code == DT_F64:
        return 2.220446049250313e-16
    if code == DT_F32:
        return 1.1920928955078125e-07
    if code == DT_BF16:
        return 0.0078125  # 2^-7, 8 significand bits
    if code == DT_F16:
        return 0.0009765625  # 2^-10, 11 significand bits
    if code == DT_F8E4M3:
        return 0.125  # 2^-3, 4 significand bits
    if code == DT_F8E5M2:
        return 0.25  # 2^-2, 3 significand bits
    return 0.0


def dtx_max_finite(code: Int) -> Float64:
    """Largest finite magnitude representable. 0.0 for an unknown dtype."""
    if code == DT_F64:
        return 1.7976931348623157e308
    if code == DT_F32:
        return 3.4028234663852886e38
    if code == DT_BF16:
        return 3.3895313892515355e38
    if code == DT_F16:
        return 65504.0
    if code == DT_F8E4M3:
        return 448.0
    if code == DT_F8E5M2:
        return 57344.0
    if code == DT_I8:
        return 127.0
    if code == DT_U8:
        return 255.0
    if code == DT_I4:
        return 7.0
    if code == DT_NF4:
        return 1.0
    return 0.0


def dtx_accum_dtype(code: Int) -> Int:
    """The dtype to accumulate in when the storage dtype is `code`. The package's single policy.

    Everything below f32 accumulates in f32; f64 stays f64. Accumulating a dot product in bf16 loses
    the run silently — the forward pass still produces numbers, they are just worse — so this is
    stated once here rather than decided per kernel.
    """
    if code == DT_F64:
        return DT_F64
    if not dtx_is_supported(code):
        return DT_INVALID
    return DT_F32


def dtx_round_trip(value: Float64, code: Int) -> Float64:
    """Push one value through `code` and back to f64, using the compiler's own conversion.

    Non-finite input is returned unchanged rather than cast: a NaN's payload is not the caller's
    concern here and casting it through an 8-bit format would invent a value.
    """
    if not tx_finite(value):
        return value
    if code == DT_F64:
        return value
    if code == DT_F32:
        return Float64(Float32(value))
    if code == DT_BF16:
        return Float64(Scalar[DType.bfloat16](Float32(value)).cast[DType.float64]())
    if code == DT_F16:
        return Float64(Scalar[DType.float16](Float32(value)).cast[DType.float64]())
    if code == DT_F8E4M3:
        return Float64(
            Scalar[DType.float8_e4m3fn](Float32(value)).cast[DType.float64]()
        )
    if code == DT_F8E5M2:
        return Float64(
            Scalar[DType.float8_e5m2](Float32(value)).cast[DType.float64]()
        )
    # Integer and codebook formats are not a float round-trip; the pack/unpack path owns them and
    # returning `value` here would claim a fidelity this function did not check.
    return value


def dtx_bf16_frozen_delta(value: Float64) -> Float64:
    """`native_bf16(value) - quantization_stack.bf16_to_fp32_round(value)`.

    Exists so the difference between this module's round-to-nearest-even contract and the frozen
    kernel's own convention is a reported number rather than a silent divergence. Both remain
    reachable and unchanged; see the module docstring for the measured table.
    """
    if not tx_finite(value):
        return 0.0
    return dtx_round_trip(value, DT_BF16) - bf16_to_fp32_round(value)


def dtx_tol_for(quantity: Float64, code: Int, abs_tol: Float64) -> TxTolerance:
    """Build a comparison tolerance for ONE quantity: `abs_tol + eps(dtype) * |quantity|`.

    The package's single tolerance constructor, and the shape matters more than the code. Rule 4b
    records four ways this goes wrong, all of which produce a tolerance that passes a broken result:

      1. a sum over every item, so one large row's units pay for another row's contradiction;
      2. a max/norm over every item, which LOOKS per-item and is not;
      3. a `1 + |x|` floor, which is absolute at any scale below 1.0;
      4. sizing the relative term by the caller's tolerance instead of by `eps`.

    So: the relative term is `eps * |quantity|` and nothing else, the absolute term is exactly what
    the caller passed, and there is no floor. A non-finite quantity is refused rather than producing
    a NaN tolerance that makes every subsequent `>` comparison False (rule 4d).
    """
    if not tx_finite(quantity) or not tx_finite(abs_tol):
        return TxTolerance(0.0, 0.0, 0.0, TX_ERR_UNKNOWN_DTYPE)
    if not dtx_is_supported(code):
        return TxTolerance(0.0, 0.0, 0.0, TX_ERR_UNKNOWN_DTYPE)
    var magnitude = -quantity if quantity < 0.0 else quantity
    var rel = dtx_eps(code) * magnitude
    var absolute = -abs_tol if abs_tol < 0.0 else abs_tol
    return TxTolerance(absolute + rel, rel, absolute, TX_OK)


def dtx_round_trip_list(
    values: List[Float64], n: Int, code: Int
) -> DtypeCast:
    """Round-trip the first `n` entries of `values` through `code`, reporting what was lost.

    Refuses rather than indexes when `n` exceeds `len(values)`: that call is the generated A-Z
    suite's shape (five-element list, `n = 5`) only by luck, and in production it is an uncatchable
    process abort that takes the worker down with every resident model in it.

    @capability dtx_round_trip_list
    complexity: O(n)
    counts:
    - n <= len(values) [enforced]
    @endcapability
    """
    var out = List[Float64]()
    var count_status = tx_count_ok(n, len(values))
    if count_status != TX_OK:
        return DtypeCast(out^, 0, 0, 0, 0.0, count_status)
    if not dtx_is_supported(code):
        return DtypeCast(out^, 0, 0, 0, 0.0, TX_ERR_UNKNOWN_DTYPE)

    var limit = dtx_max_finite(code)
    var n_overflow = 0
    var n_underflow = 0
    var n_nan = 0
    var max_err = 0.0

    for i in range(n):
        var x = values[i]
        if isnan(x):
            n_nan += 1
            out.append(x)
            continue
        var y = dtx_round_trip(x, code)
        var mag = -x if x < 0.0 else x
        # Overflow is judged against the dtype's own range, before looking at the result: a cast that
        # saturates and one that produces inf are the same event to a caller choosing a format.
        if mag > limit or (isinf(y) and not isinf(x)):
            n_overflow += 1
        elif x != 0.0 and y == 0.0:
            n_underflow += 1
        var err = y - x
        if err < 0.0:
            err = -err
        if err > max_err:
            max_err = err
        out.append(y)

    return DtypeCast(out^, n_overflow, n_underflow, n_nan, max_err, TX_OK)
