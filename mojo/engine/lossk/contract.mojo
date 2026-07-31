"""
lossk.contract — status vocabulary and work budget for training objectives. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_lossk_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_lossk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Status range
------------
`lossk` owns **580-599**, after tensorx 300-319, gemm 320-339, attnk 360-379, normk 380-389 and
mlpk 390-399 (rule 4e). Finiteness comes from `tensorx.contract.tx_finite`.

The loss is where the memory goes, and it is the one layer that can avoid it
------------------------------------------------------------------------------
Every other layer in a transformer is `O(tokens x hidden)`. The output projection is
`O(tokens x VOCAB)`, and vocabulary is two orders of magnitude larger than hidden: for a 2048-token
batch against a 151,936-token vocabulary the full logit tensor is **2.5 GB in 64-bit**, allocated to
produce a single scalar loss. On a 32 GB machine that one tensor can be the difference between a run
that fits and a run that does not.

It is also unnecessary. Cross-entropy needs, per token, only the logit of the correct class and the
log-sum-exp over all classes — both of which are reductions. So the logits can be produced a CHUNK of
tokens at a time, reduced, and thrown away. `LOSS_MAX_LOGIT_CELLS` bounds the chunk, not the batch,
and that is the whole design: peak memory becomes a property of the chunk size the caller picks
rather than of the batch size the data gave them.

Why the chunk is validated rather than chosen
-----------------------------------------------
A kernel that picked its own chunk size would be picking the caller's peak memory, and it has no way
to know what else is resident — an optimizer state, a KV cache, another rank's buffers. So the chunk
is a parameter, it is checked, and a chunk that would exceed the logit budget is an error naming the
budget rather than a silent clamp to something that fits.

Public API:
  loss_status_name(code)                                     — the status vocabulary
  loss_dims_check(n_tok, d_model, vocab)                     — shape agreement
  loss_chunk_check(chunk, vocab)                             — the peak-memory bound
  loss_logit_cells(chunk, vocab)                             — what a chunk will allocate
  loss_targets_in_range(targets, n_tok, vocab)               — validated before any indexing
  loss_tol_for(magnitude, reduction_width)                   — rule 4b tolerance
"""

from tensorx.contract import tx_finite

# ── status codes: lossk owns 580-599 ──────────────────────────────────────────

comptime LOSS_OK: Int = 580
comptime LOSS_ERR_EMPTY_DIM: Int = 581
comptime LOSS_ERR_LENGTH_MISMATCH: Int = 582
comptime LOSS_ERR_DIM_TOO_LARGE: Int = 583
comptime LOSS_ERR_WORK_TOO_LARGE: Int = 584
comptime LOSS_ERR_NON_FINITE_SCALAR: Int = 585
comptime LOSS_ERR_TARGET_OUT_OF_RANGE: Int = 586
comptime LOSS_ERR_BAD_CHUNK: Int = 587
comptime LOSS_ERR_UNKNOWN_OBJECTIVE: Int = 588

comptime LOSS_MAX_VOCAB: Int = 1 << 22
"""Largest vocabulary. Qwen3 is 151,936; 2^22 is ~4.2M, past every tokenizer in use."""

comptime LOSS_MAX_TOKENS: Int = 1 << 24
comptime LOSS_MAX_DIM: Int = 1 << 20

comptime LOSS_MAX_LOGIT_CELLS: Int = 1 << 27
"""Bound on `chunk * vocab` — the cells one chunk materializes, and therefore peak logit memory.

2^27 cells is 1 GiB at 64-bit. Against a 151,936 vocabulary that permits a chunk of ~883 tokens,
which is a real working size. The bound exists so that a caller who passes their BATCH size where a
chunk size belongs — the obvious mistake, since both are token counts — gets an error naming the
budget instead of a 2.5 GB allocation."""

comptime LOSS_MAX_WORK_CELLS: Int = 1 << 46
"""Bound on total `n_tok * d_model * vocab` work. Far larger than the logit-cell bound on purpose:
the whole point of chunking is that TOTAL work may legitimately exceed what is resident at any one
moment, so one budget cannot express both questions.

Sized against the shapes it must ADMIT rather than a round number. Qwen3-8B, the certification model,
at its three certified context lengths:

| Context | `n_tok * d_model * vocab` |
|---|---|
| 2,048 | 1.28e12 |
| 8,192 | 5.10e12 |
| 32,768 | 2.04e13 |

2^46 is 7.04e13, which clears all three. An earlier 2^40 (1.10e12) did NOT — it rejected the primary
certification shape at the shortest context, and the only reason that surfaced is that the contract
test asserts a REAL model shape instead of a toy one. It still refuses what it is for: the
all-ceilings product is 7.4e19 and a wrapping `2^30` cubed is 1.2e27."""


fn loss_status_name(code: Int) -> String:
    """Name a status code. Unknown codes say so rather than borrowing a neighbour's meaning."""
    if code == LOSS_OK:
        return String("ok")
    if code == LOSS_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == LOSS_ERR_LENGTH_MISMATCH:
        return String("length_mismatch")
    if code == LOSS_ERR_DIM_TOO_LARGE:
        return String("dimension_too_large")
    if code == LOSS_ERR_WORK_TOO_LARGE:
        return String("work_budget_exceeded")
    if code == LOSS_ERR_NON_FINITE_SCALAR:
        return String("non_finite_scalar")
    if code == LOSS_ERR_TARGET_OUT_OF_RANGE:
        return String("target_id_out_of_range")
    if code == LOSS_ERR_BAD_CHUNK:
        return String("chunk_exceeds_logit_budget")
    if code == LOSS_ERR_UNKNOWN_OBJECTIVE:
        return String("unknown_objective")
    return String("unknown_status")


fn loss_logit_cells(chunk: Int, vocab: Int) -> Float64:
    """Cells one chunk materializes: `chunk * vocab`. Negative on a malformed request.

    Returned as `Float64` because the honest answer exceeds `Int` well before it exceeds anything a
    caller would call reasonable, and a wrapped count would compare as small — the exact failure the
    budget exists to prevent.

    @capability loss_logit_cells
    complexity: O(1)
    counts:
    - dim chunk <= LOSS_MAX_TOKENS [kernel_validated]
    - dim vocab <= LOSS_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    if chunk <= 0 or vocab <= 0:
        return -1.0
    if chunk > LOSS_MAX_TOKENS or vocab > LOSS_MAX_VOCAB:
        return -1.0
    return Float64(chunk) * Float64(vocab)


fn loss_chunk_check(chunk: Int, vocab: Int) -> Int:
    """Validate that one chunk's logits fit the peak-memory budget.

    @capability loss_chunk_check
    complexity: O(1)
    counts:
    - dim chunk <= LOSS_MAX_TOKENS [kernel_validated]
    - dim vocab <= LOSS_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    if chunk <= 0 or vocab <= 0:
        return LOSS_ERR_EMPTY_DIM
    if chunk > LOSS_MAX_TOKENS or vocab > LOSS_MAX_VOCAB:
        return LOSS_ERR_DIM_TOO_LARGE
    var cells = loss_logit_cells(chunk, vocab)
    if cells < 0.0 or cells > Float64(LOSS_MAX_LOGIT_CELLS):
        return LOSS_ERR_BAD_CHUNK
    return LOSS_OK


fn loss_work_fits(n_tok: Int, d_model: Int, vocab: Int, ceiling: Int) -> Bool:
    """True when `n_tok * d_model * vocab` fits in `ceiling`, WITHOUT forming the product.

    Grown by division, one factor at a time. This is the projection's true cost and it is the largest
    product anywhere in the plane — three factors each of which can be large — so a wrapping multiply
    here is more likely than anywhere else, not less.

    @capability loss_work_fits
    complexity: O(1)
    counts:
    - dim n_tok <= LOSS_MAX_TOKENS [kernel_validated]
    - dim d_model <= LOSS_MAX_DIM [kernel_validated]
    - dim vocab <= LOSS_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    if n_tok <= 0 or d_model <= 0 or vocab <= 0 or ceiling <= 0:
        return False
    if n_tok > LOSS_MAX_TOKENS or d_model > LOSS_MAX_DIM or vocab > LOSS_MAX_VOCAB:
        return False
    var remaining = ceiling
    if n_tok > remaining:
        return False
    remaining = remaining // n_tok
    if d_model > remaining:
        return False
    remaining = remaining // d_model
    return vocab <= remaining


fn loss_dims_check(n_tok: Int, d_model: Int, vocab: Int) -> Int:
    """Validate a fused-projection loss shape.

    @capability loss_dims_check
    complexity: O(1)
    counts:
    - dim n_tok <= LOSS_MAX_TOKENS [kernel_validated]
    - dim d_model <= LOSS_MAX_DIM [kernel_validated]
    - dim vocab <= LOSS_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    if n_tok <= 0 or d_model <= 0 or vocab <= 0:
        return LOSS_ERR_EMPTY_DIM
    if n_tok > LOSS_MAX_TOKENS or d_model > LOSS_MAX_DIM or vocab > LOSS_MAX_VOCAB:
        return LOSS_ERR_DIM_TOO_LARGE
    if not loss_work_fits(n_tok, d_model, vocab, LOSS_MAX_WORK_CELLS):
        return LOSS_ERR_WORK_TOO_LARGE
    return LOSS_OK


fn loss_targets_in_range(targets: List[Int], n_tok: Int, vocab: Int) -> Bool:
    """True when every one of the first `n_tok` targets is a valid class index.

    A target is used to INDEX the logit row, so an out-of-range one reads past the end of a buffer,
    which in Mojo aborts the whole worker uncatchably. Validated in one pass before any indexing.

    A negative target is refused here rather than treated as "ignore". Masked positions are a real
    need and a real convention (-100 in several frameworks), but silently accepting a magic negative
    would mean a genuine off-by-one that produced -1 is read as "skip this token" and the loss comes
    out plausible. Masking belongs in an explicit mask argument, not in the sign bit of an index.

    @capability loss_targets_in_range
    complexity: O(n_tok)
    counts:
    - n_tok <= len(targets) [enforced]
    @endcapability
    """
    if n_tok <= 0 or vocab <= 0 or len(targets) < n_tok:
        return False
    for t in range(n_tok):
        var target = targets[t]
        if target < 0 or target >= vocab:
            return False
    return True


fn loss_scalars_ok(value: Float64) -> Bool:
    """True when a scalar is finite. Checked before it can turn a whole objective into NaN."""
    return tx_finite(value)


comptime LOSS_TRANSCENDENTAL_FLOOR: Float64 = 1.0e-9
"""The accuracy ceiling imposed by `std.math.log` and `exp` on this toolchain. Measured, not assumed.

Neither is correctly rounded:

| call | this toolchain | correctly rounded | error |
|---|---|---|---|
| `log(1.5)` | 0.4054651080256719 | 0.4054651081081644 | 8.2e-11 |
| `log(100.0)` | 4.605170186247496 | 4.605170185988092 | 2.6e-10 |
| `exp(10.0)` | 22026.465794893786 | 22026.465794806718 | 8.7e-8 absolute |

Every softmax, log-sum-exp and cross-entropy in this plane is built on those two calls, so ~1e-10 is
the floor for anything compared against an EXTERNAL reference. It is NOT the floor for comparing two
Algenta paths against each other: both call the same routines, the same error appears on both sides
and cancels, which is why the chunk-invariance check can demand bit equality while a golden-value
check cannot.

The distinction matters when reading a tolerance in this package. A tight one means "these two
spellings must agree"; a loose one near this floor means "this is as close as the toolchain can get"."""


fn loss_tol_for(magnitude: Float64, reduction_width: Int) -> Float64:
    """Tolerance for comparing two spellings of a loss of size `magnitude` (rule 4b).

    Scales with the quantity judged and with the reduction behind it. A cross-entropy is a
    log-sum-exp over the whole vocabulary, so its rounding error grows with vocabulary size — a
    tolerance calibrated at 32k classes is a false failure at 152k.
    """
    var width = Float64(reduction_width) if reduction_width > 0 else 1.0
    var mag = magnitude if magnitude >= 0.0 else -magnitude
    return 1.0e-14 * (1.0 + mag) * (1.0 + width)
