"""
llmk.contract — the one status vocabulary and shape check for `llmk`. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_llmk_residual.mojo
benchmark: benchmarks/llm_smoke/qwen3_forward.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Status range
------------
`llmk` owns **560-579**, after `tensorx` 300-319, `gemm` 320-339, `accel`/`causal_inference` 340-359,
`attnk` 360-379, `normk` 380-389, `mlpk` 390-399 and before `lossk` 580-599 (rule 4e).

Why this package is one kernel, not three
--------------------------------------------
Wiring a real Qwen3 checkpoint through the existing LLM-plane kernels found three candidate gaps and
two of them turned out to already exist:

1. Embedding-table gather: **already exists**, as `mlpk.embedding.embedding_fwd_flat`. Calling it
   directly (rule 3) rather than writing a second gather under a different package's status codes.
2. Half-split RoPE: **already exists**, as `attnk.rope.rope_apply_flat(..., interleaved=False)` —
   the docstring there names the GPT-NeoX split-half convention explicitly and it is exactly Qwen3's.
   Calling it directly rather than writing a second RoPE driver.
3. Elementwise residual-add-of-two-whole-buffers: genuinely absent. `transformer_blocks.residual_connection`
   and `fused_kernels.fused_add_norm` are both scalar, one `Float64` at a time — the "last line of the
   kernel, not the kernel" pattern this plane's other packages already named for attention/norm/FFN.
   This package supplies the one driver that was missing.

Public API:
  llmk_status_name(code)                              — the status vocabulary
  llmk_residual_dims_check(n, len_a, len_b)           — exact-length shape agreement for both operands
  llmk_kv_append_dims_check(cache_len, len_cache, n_new, len_new)  — KV-cache growth, one step
  llmk_argmax_dims_check(n, len_logits)               — a full-vocabulary argmax row
  llmk_gemv_dims_check(m, n, len_a, len_x)            — the parallel transposed-GEMV's shape

Codes 566-568 (below) are additive for `llmk.generate`'s decode-loop primitives (KV-cache append,
greedy argmax), added in the same session that wired the actual generation loop on top of the
prefill-only forward pass this module's docstring above describes -- still inside the 560-579 range
this package owns, nothing renumbered.

Codes 569-570 (below) are additive for `llmk.gemv_fast.gemv_transposed_parallel_flat` -- the parallel
transposed-GEMV that replaces `gemm.blocked.gemv_flat(..., trans=True)`'s single-threaded scalar path
at the 7-of-8 decode-step call sites `benchmarks/llm_smoke/qwen3_generate.mojo` uses it at (see that
module's own docstring for the measured bottleneck). Still inside 560-579, still nothing renumbered.
"""

from tensorx.contract import tx_finite

# ── status codes: llmk owns 560-579 ────────────────────────────────────────────

comptime LLMK_OK: Int = 560
"""The kernel ran and every element of the output is defined."""

comptime LLMK_ERR_EMPTY_DIM: Int = 561
"""`n` was < 1."""

comptime LLMK_ERR_A_LENGTH: Int = 562
"""residual_add_flat: len(a) != n."""

comptime LLMK_ERR_B_LENGTH: Int = 563
"""residual_add_flat: len(b) != n."""

comptime LLMK_ERR_DIM_TOO_LARGE: Int = 564
"""`n` exceeds `LLMK_MAX_DIM`."""

comptime LLMK_ERR_CODE_OUT_OF_RANGE: Int = 565
"""Not one of the codes above. Returned by llmk_status_name for an unrecognized code."""

comptime LLMK_ERR_CACHE_LENGTH: Int = 566
"""kv_cache_append_flat: len(cache) != cache_len -- the existing KV cache is not what the caller
claimed its own running length was."""

comptime LLMK_ERR_NEW_LENGTH: Int = 567
"""kv_cache_append_flat: len(new_vals) != n_new -- this step's freshly-projected K or V rows are not
the length the caller claimed."""

comptime LLMK_ERR_LOGITS_LENGTH: Int = 568
"""greedy_argmax_flat: len(logits) != n -- the logits row is not the vocabulary width the caller
claimed."""

comptime LLMK_ERR_GEMV_A_LENGTH: Int = 569
"""gemv_transposed_parallel_flat: len(a) != m * n -- the weight buffer is not the shape the caller
claimed."""

comptime LLMK_ERR_GEMV_X_LENGTH: Int = 570
"""gemv_transposed_parallel_flat: len(x) != m -- the input vector is not the in-features width the
caller claimed."""

comptime LLMK_MAX_DIM: Int = 1 << 24
"""Ceiling on `n`. Matches `normk.contract.NORM_MAX_ROWS`'s order of magnitude — a residual add over
`tokens * d_model` at any real transformer shape is far below this, and a caller passing a byte count
or an unbounded accumulation length where an element count belongs is refused rather than allocated."""


fn llmk_status_name(code: Int) -> String:
    """Human name for a status code. Every code above appears here exactly once."""
    if code == LLMK_OK:
        return String("llmk_ok")
    if code == LLMK_ERR_EMPTY_DIM:
        return String("llmk_empty_dimension")
    if code == LLMK_ERR_A_LENGTH:
        return String("llmk_a_length_mismatch")
    if code == LLMK_ERR_B_LENGTH:
        return String("llmk_b_length_mismatch")
    if code == LLMK_ERR_DIM_TOO_LARGE:
        return String("llmk_dimension_too_large")
    if code == LLMK_ERR_CACHE_LENGTH:
        return String("llmk_cache_length_mismatch")
    if code == LLMK_ERR_NEW_LENGTH:
        return String("llmk_new_length_mismatch")
    if code == LLMK_ERR_LOGITS_LENGTH:
        return String("llmk_logits_length_mismatch")
    if code == LLMK_ERR_GEMV_A_LENGTH:
        return String("llmk_gemv_a_length_mismatch")
    if code == LLMK_ERR_GEMV_X_LENGTH:
        return String("llmk_gemv_x_length_mismatch")
    return String("llmk_code_out_of_range")


fn llmk_residual_dims_check(n: Int, len_a: Int, len_b: Int) -> Int:
    """Validate a residual add's shape against its real buffer lengths, exactly.

    @capability llmk_residual_dims_check
    complexity: O(1)
    counts:
    - dim n <= LLMK_MAX_DIM [kernel_validated]
    @endcapability
    """
    if n < 1:
        return LLMK_ERR_EMPTY_DIM
    if n > LLMK_MAX_DIM:
        return LLMK_ERR_DIM_TOO_LARGE
    if len_a != n:
        return LLMK_ERR_A_LENGTH
    if len_b != n:
        return LLMK_ERR_B_LENGTH
    return LLMK_OK


fn llmk_kv_append_dims_check(cache_len: Int, len_cache: Int, n_new: Int, len_new: Int) -> Int:
    """Validate one decode step's KV-cache growth against the real buffer lengths, exactly.

    @capability llmk_kv_append_dims_check
    complexity: O(1)
    counts:
    - dim cache_len <= LLMK_MAX_DIM [kernel_validated]
    - dim n_new <= LLMK_MAX_DIM [kernel_validated]
    @endcapability
    """
    if cache_len < 0 or n_new < 1:
        return LLMK_ERR_EMPTY_DIM
    if len_cache != cache_len:
        return LLMK_ERR_CACHE_LENGTH
    if len_new != n_new:
        return LLMK_ERR_NEW_LENGTH
    if cache_len > LLMK_MAX_DIM - n_new:
        return LLMK_ERR_DIM_TOO_LARGE
    return LLMK_OK


fn llmk_argmax_dims_check(n: Int, len_logits: Int) -> Int:
    """Validate a full-vocabulary argmax row against its real length, exactly.

    @capability llmk_argmax_dims_check
    complexity: O(1)
    counts:
    - dim n <= LLMK_MAX_DIM [kernel_validated]
    @endcapability
    """
    if n < 1:
        return LLMK_ERR_EMPTY_DIM
    if n > LLMK_MAX_DIM:
        return LLMK_ERR_DIM_TOO_LARGE
    if len_logits != n:
        return LLMK_ERR_LOGITS_LENGTH
    return LLMK_OK


fn llmk_gemv_dims_check(m: Int, n: Int, len_a: Int, len_x: Int) -> Int:
    """Validate the parallel transposed-GEMV's shape against its real buffer lengths, exactly.

    `a` is `m` rows by `n` columns, row-major (the in-features-by-out-features layout
    `qwen3_generate.mojo`'s pre-transposed weights use); `x` is the length-`m` input vector; the
    result `y` is length `n`. Same two-buffer, two-dimension shape `gemm.blocked.gemv_flat` itself
    validates, just under this package's own status vocabulary (rule 4e).

    @capability llmk_gemv_dims_check
    complexity: O(1)
    counts:
    - dim m <= LLMK_MAX_DIM [kernel_validated]
    - dim n <= LLMK_MAX_DIM [kernel_validated]
    @endcapability
    """
    if m < 1 or n < 1:
        return LLMK_ERR_EMPTY_DIM
    if m > LLMK_MAX_DIM or n > LLMK_MAX_DIM:
        return LLMK_ERR_DIM_TOO_LARGE
    if len_a != m * n:
        return LLMK_ERR_GEMV_A_LENGTH
    if len_x != m:
        return LLMK_ERR_GEMV_X_LENGTH
    return LLMK_OK
