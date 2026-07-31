"""
tensorx.contract — the one status vocabulary, finiteness predicate and shape check for `tensorx`.
Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_contract.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

One of each, per package
------------------------
Rule 3 of `docs/mojo/new-kernel-package-rules.md` applies inside a package as well as across the
tree: `optimization/` grew `_finite` six times, byte-identical and private in every file, so no file
could import it even though five already imported from a shared base module. A duplicated guard is
worse than a missing one — it reads as defence in depth while providing one arbitrary behaviour per
call site.

So this module is the single home for the package's status codes, its finiteness predicate and its
shape check. The one deliberate exception is the tolerance constructor: it lives in `tensorx.dtype`
because it is built from `dtx_eps(dtype_code)`, and putting it here would make `contract` depend on
`dtype` while `dtype` depends on `contract`. There is still exactly one of it.

Status range
------------
`tensorx` owns **300-319** (rule 4e — ranges are allocated per package, not per file, after
`optimization` 0-159, `sparse_numerics` 0-24, `graph_analytics` 0-25 and `retrieval` 200-219
collided at low numbers). Codes are distinct per defect: a caller that gets a rejection needs to know
which of its inputs is wrong, and a single "invalid" code sends it looking at all of them.

The product is checked by division, never by multiplying
---------------------------------------------------------
`rows * cols` is a wrapping 64-bit multiply. `3 * 6148914691236517206 == 2`, which is exactly how a
`rows * cols != len(dense)` guard was walked past in `sparse_numerics` and crashed the process.
`tx_dims_fit` therefore grows the product factor by factor against the ceiling and treats "would
exceed" as the answer, so no oversized product is ever formed. That shape is borrowed from
`sparse_numerics.csr.dims_fit`, which is frozen and reused as-is wherever a CSR is in play; this is
the `tensorx` equivalent for dense row-major shapes, not a replacement for it.

Public API:
  tx_status_name(code)                   — the status vocabulary, one string per code
  tx_finite(x)                           — one scalar finiteness test for the whole package
  tx_all_finite(v, n)                    — bounded scan; rejects n > len(v) rather than reading past
  tx_count_ok(n, length)                 — the count/length relation as a status, not a Bool
  tx_dims_fit(rows, cols, ceiling)       — division-based, never forms a wrapping product
  tx_shape_ok(rows, cols, data_len)      — flat row-major: rows*cols must equal len exactly
"""

from std.math import isnan, isinf

# ── status codes: tensorx owns 300-319 ────────────────────────────────────────

comptime TX_OK: Int = 300
comptime TX_ERR_UNKNOWN_DTYPE: Int = 301
comptime TX_ERR_COUNT_EXCEEDS_LENGTH: Int = 302
comptime TX_ERR_NEGATIVE_COUNT: Int = 303
comptime TX_ERR_DIMENSION_TOO_LARGE: Int = 304
comptime TX_ERR_SHAPE_MISMATCH: Int = 305
comptime TX_ERR_NON_FINITE: Int = 306
comptime TX_ERR_EMPTY: Int = 307
comptime TX_ERR_DTYPE_UNSUPPORTED_FOR_OP: Int = 308
comptime TX_ERR_BLOCK_SIZE: Int = 309
comptime TX_ERR_BITS_UNSUPPORTED: Int = 310
comptime TX_ERR_LENGTH_MISMATCH: Int = 311
comptime TX_ERR_CODE_OUT_OF_RANGE: Int = 312

comptime TX_MAX_ELEMS: Int = 1 << 26
"""67,108,864 elements — 512 MiB of Float64, which is what the resident-dataset budget already
treats as the outer limit for ONE object.

Derived independently of `sparse_numerics.csr.MAX_CSR_DIM` even though the number matches: that one
bounds a row-pointer array, this one bounds an element count, and coupling them would mean a future
change to either silently moves the other. Rule 1c applies on top — a driver allocating k arrays of
this length is bounded at k x 512 MiB, not 512 MiB, so a caller with several buffers scales its own
local ceiling down rather than reusing this one k times."""


fn tx_status_name(code: Int) -> String:
    """Name a status code. Unknown codes are named as unknown rather than guessed at."""
    if code == TX_OK:
        return String("ok")
    if code == TX_ERR_UNKNOWN_DTYPE:
        return String("unknown_dtype")
    if code == TX_ERR_COUNT_EXCEEDS_LENGTH:
        return String("count_exceeds_length")
    if code == TX_ERR_NEGATIVE_COUNT:
        return String("negative_count")
    if code == TX_ERR_DIMENSION_TOO_LARGE:
        return String("dimension_too_large")
    if code == TX_ERR_SHAPE_MISMATCH:
        return String("shape_mismatch")
    if code == TX_ERR_NON_FINITE:
        return String("non_finite")
    if code == TX_ERR_EMPTY:
        return String("empty")
    if code == TX_ERR_DTYPE_UNSUPPORTED_FOR_OP:
        return String("dtype_unsupported_for_op")
    if code == TX_ERR_BLOCK_SIZE:
        return String("invalid_block_size")
    if code == TX_ERR_BITS_UNSUPPORTED:
        return String("bits_unsupported")
    if code == TX_ERR_LENGTH_MISMATCH:
        return String("length_mismatch")
    if code == TX_ERR_CODE_OUT_OF_RANGE:
        return String("code_out_of_range")
    return String("unknown_status")


fn tx_finite(x: Float64) -> Bool:
    """True when `x` is neither NaN nor infinite.

    The package's only finiteness test. Validate finiteness BEFORE computing any tolerance from an
    input: with a NaN in play, `tol = eps * (1 + nan)` is NaN, every `fabs(d) > nan` is False, and an
    audit passes having counted zero violations (rule 4d's trap, found live in `optimization`).
    """
    return not isnan(x) and not isinf(x)


fn tx_count_ok(n: Int, length: Int) -> Int:
    """The count/length relation, as a status rather than a Bool.

    Separates "you asked for a negative count" from "you asked for more than you gave me", because
    the second is the one that reaches production as a plausible-looking config and the first is a
    caller bug. Returns `TX_OK`, `TX_ERR_NEGATIVE_COUNT` or `TX_ERR_COUNT_EXCEEDS_LENGTH`.
    """
    if n < 0:
        return TX_ERR_NEGATIVE_COUNT
    if n > length:
        return TX_ERR_COUNT_EXCEEDS_LENGTH
    return TX_OK


fn tx_all_finite(v: List[Float64], n: Int) -> Bool:
    """Scan the first `n` entries of `v` for non-finite values.

    Returns False — not a crash — when `n` exceeds `len(v)`. The generated A-Z suite calls every
    contract function with a five-element list and `5` for every `Int`, so an unguarded loop here
    would be fine there and fatal in production on the first real call.

    @capability tx_all_finite
    complexity: O(n)
    counts:
    - n <= len(v) [enforced]
    @endcapability
    """
    if tx_count_ok(n, len(v)) != TX_OK:
        return False
    for i in range(n):
        if not tx_finite(v[i]):
            return False
    return True


fn tx_dims_fit(rows: Int, cols: Int, ceiling: Int) -> Bool:
    """True when `rows * cols` fits in `ceiling`, computed WITHOUT forming the product.

    Grows the bound by division instead of multiplying: a wrapping 64-bit multiply is how
    `3 * 6148914691236517206 == 2` walked past a product guard and aborted the worker. Non-positive
    dimensions are not "fitting" — they are invalid, and the caller gets False rather than a
    vacuously-true bound.

    @capability tx_dims_fit
    complexity: O(1)
    counts:
    - dim rows <= TX_MAX_ELEMS [kernel_validated]
    - dim cols <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    if rows <= 0 or cols <= 0 or ceiling <= 0:
        return False
    if rows > ceiling:
        return False
    return cols <= ceiling // rows


fn tx_shape_ok(rows: Int, cols: Int, data_len: Int) -> Int:
    """Validate a flat row-major shape against its buffer length. `rows * cols` must equal exactly.

    Exact equality, not `<=`: a buffer longer than the declared shape means the caller and the kernel
    disagree about what the data is, and silently using a prefix of it produces a plausible answer
    for the wrong matrix.

    @capability tx_shape_ok
    complexity: O(1)
    counts:
    - dim rows <= TX_MAX_ELEMS [kernel_validated]
    - dim cols <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    if rows <= 0 or cols <= 0:
        return TX_ERR_EMPTY
    if not tx_dims_fit(rows, cols, TX_MAX_ELEMS):
        return TX_ERR_DIMENSION_TOO_LARGE
    if rows * cols != data_len:
        return TX_ERR_SHAPE_MISMATCH
    return TX_OK
