"""
mlpk.contract — status vocabulary, work budget and the GELU convention for feed-forward kernels.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_mlpk_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_mlpk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Status range
------------
`mlpk` owns **390-399**, after `tensorx` 300-319, `gemm` 320-339, `attnk` 360-379 and `normk` 380-389
(rule 4e). Finiteness comes from `tensorx.contract.tx_finite`.

The GELU convention, measured 2026-07-31
------------------------------------------
`activations.mojo` holds three GELU spellings and every one of them is the tanh approximation —
including `gelu`, whose docstring opens "Gaussian Error Linear Unit (exact): x x Phi(x)" above a tanh
body. Measured against `x * 0.5 * (1 + erf(x / sqrt(2)))` over `[-4, 4]` at 2001 points:

| Frozen kernel | Max abs error vs the erf form | Note |
|---|---|---|
| `activations.gelu` | **4.73e-4** (at x = 2.7) | docstring says exact; body is tanh |
| `activations.gelu_fast` | **4.73e-4** | agrees with `gelu_new` to 1 ULP |
| `activations.gelu_new` | **4.73e-4** | agrees with `gelu_fast` to 1 ULP |

The three differ from each other only in rounding, and measuring that was worth doing rather than
assuming: `gelu_fast` and `gelu_new` are NOT bit-identical, they sit 2.6e-16 apart, because one
associates the cubic as `C*(x + a*x^3)` and the other as `C*x*(1 + a*x^2)`. `gelu` is a further 9e-13
away because it truncates the constant to `0.7978845608` where the others carry
`0.7978845608028654`. So this is one convention spelled three times — with three slightly different
roundings — and the other convention is absent entirely.

Why 4.73e-4 is not a rounding detail. Hugging Face treats these as DIFFERENT activations: a config
saying `hidden_act: "gelu"` means the erf form, while `"gelu_new"` and `"gelu_pytorch_tanh"` mean the
tanh form. A checkpoint trained under one and served under the other does not fail — it produces
fluent output that is quietly worse, which reads as a disappointing model rather than a wrong
constant. So `mlpk.activation` provides `mlp_gelu_erf` as a SEPARATE contract for new surfaces,
exports `mlp_gelu_agreement` reporting the delta, and every frozen spelling stays reachable and
unchanged. Same treatment `tensorx.dtype` gives the frozen bf16 rounding.

AND THE NEW FUNCTION IS NOT CALLED "EXACT", because it is not
---------------------------------------------------------------
`std.math.erf` resolves on the pinned toolchain, but it is not correctly rounded. Measured against a
correctly-rounded double reference:

| x | `std.math.erf` | correctly rounded | error |
|---|---|---|---|
| 1.0 | 0.8427007923410611 | 0.8427007929497148 | 6.1e-10 |
| 2.0 | 0.9953222865616017 | 0.9953222650189527 | **2.2e-8** |

So an erf-based GELU here is accurate to roughly 2e-8, not to the last bit. Naming it `*_exact` would
repeat precisely the mistake this section documents in the frozen kernel, so it is named for its
CONVENTION (`mlp_gelu_erf`) and the accuracy is stated as a number. 2e-8 is still five orders of
magnitude closer to the erf convention than the tanh form's 4.73e-4, which is what makes the
distinction worth having; it is not a claim of bit-parity with PyTorch's erf.

Public API:
  mlp_status_name(code)                              — the status vocabulary
  mlp_dims_check(n_tok, d_model, d_ff)               — feed-forward shape agreement
  mlp_work_fits(n_tok, d_model, d_ff, ceiling)       — no wrapping product
  mlp_vocab_check(n_tok, vocab, d_model)             — embedding shape agreement
  mlp_tol_for(magnitude, reduction_width)            — rule 4b tolerance
"""

from tensorx.contract import tx_finite

# ── status codes: mlpk owns 390-399 ───────────────────────────────────────────

comptime MLP_OK: Int = 390
comptime MLP_ERR_EMPTY_DIM: Int = 391
comptime MLP_ERR_LENGTH_MISMATCH: Int = 392
comptime MLP_ERR_DIM_TOO_LARGE: Int = 393
comptime MLP_ERR_WORK_TOO_LARGE: Int = 394
comptime MLP_ERR_NON_FINITE_SCALAR: Int = 395
comptime MLP_ERR_TOKEN_OUT_OF_RANGE: Int = 396
comptime MLP_ERR_UNKNOWN_ACTIVATION: Int = 397

# ── activation selectors ──────────────────────────────────────────────────────

comptime MLP_ACT_SWIGLU: Int = 0
comptime MLP_ACT_GEGLU_TANH: Int = 1
comptime MLP_ACT_GEGLU_ERF: Int = 2
"""Which gate nonlinearity a call wants.

`GEGLU_TANH` is the frozen `activations.gelu_new` behaviour and matches Hugging Face's `gelu_new` /
`gelu_pytorch_tanh`. `GEGLU_ERF` is the erf form and matches Hugging Face's plain `gelu`. They are
4.73e-4 apart, so the selector is explicit rather than defaulted: a kernel that silently picked one
would be right for half of all checkpoints and quietly wrong for the other half."""

comptime MLP_MAX_DIM: Int = 1 << 20
"""Largest `d_model` or `d_ff`. Qwen3-8B is 4096 and 12288; 2^20 is far above any of it and low
enough that a byte count passed where a width belongs is refused rather than allocated."""

comptime MLP_MAX_TOKENS: Int = 1 << 24
comptime MLP_MAX_VOCAB: Int = 1 << 22
"""Largest vocabulary. Qwen3 is 151,936; 2^22 is ~4.2M, past every tokenizer in use."""

comptime MLP_MAX_WORK_CELLS: Int = 1 << 38


fn mlp_status_name(code: Int) -> String:
    """Name a status code. Unknown codes say so rather than borrowing a neighbour's meaning."""
    if code == MLP_OK:
        return String("ok")
    if code == MLP_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == MLP_ERR_LENGTH_MISMATCH:
        return String("length_mismatch")
    if code == MLP_ERR_DIM_TOO_LARGE:
        return String("dimension_too_large")
    if code == MLP_ERR_WORK_TOO_LARGE:
        return String("work_budget_exceeded")
    if code == MLP_ERR_NON_FINITE_SCALAR:
        return String("non_finite_scalar")
    if code == MLP_ERR_TOKEN_OUT_OF_RANGE:
        return String("token_id_out_of_range")
    if code == MLP_ERR_UNKNOWN_ACTIVATION:
        return String("unknown_activation")
    return String("unknown_status")


fn mlp_work_fits(n_tok: Int, d_model: Int, d_ff: Int, ceiling: Int) -> Bool:
    """True when `n_tok * d_model * d_ff` fits in `ceiling`, computed WITHOUT forming the product.

    Three factors, grown one at a time by division. A wrapping 64-bit multiply is how a product guard
    was walked past in `sparse_numerics` and aborted the worker.

    @capability mlp_work_fits
    complexity: O(1)
    counts:
    - dim n_tok <= MLP_MAX_TOKENS [kernel_validated]
    - dim d_model <= MLP_MAX_DIM [kernel_validated]
    - dim d_ff <= MLP_MAX_DIM [kernel_validated]
    @endcapability
    """
    if n_tok <= 0 or d_model <= 0 or d_ff <= 0 or ceiling <= 0:
        return False
    if n_tok > MLP_MAX_TOKENS or d_model > MLP_MAX_DIM or d_ff > MLP_MAX_DIM:
        return False
    var remaining = ceiling
    if n_tok > remaining:
        return False
    remaining = remaining // n_tok
    if d_model > remaining:
        return False
    remaining = remaining // d_model
    return d_ff <= remaining


fn mlp_dims_check(n_tok: Int, d_model: Int, d_ff: Int) -> Int:
    """Validate a feed-forward shape.

    @capability mlp_dims_check
    complexity: O(1)
    counts:
    - dim n_tok <= MLP_MAX_TOKENS [kernel_validated]
    - dim d_model <= MLP_MAX_DIM [kernel_validated]
    - dim d_ff <= MLP_MAX_DIM [kernel_validated]
    @endcapability
    """
    if n_tok <= 0 or d_model <= 0 or d_ff <= 0:
        return MLP_ERR_EMPTY_DIM
    if n_tok > MLP_MAX_TOKENS or d_model > MLP_MAX_DIM or d_ff > MLP_MAX_DIM:
        return MLP_ERR_DIM_TOO_LARGE
    if not mlp_work_fits(n_tok, d_model, d_ff, MLP_MAX_WORK_CELLS):
        return MLP_ERR_WORK_TOO_LARGE
    return MLP_OK


fn mlp_vocab_check(n_tok: Int, vocab: Int, d_model: Int) -> Int:
    """Validate an embedding shape.

    The vocabulary is checked separately from `d_ff` because it is the one dimension a caller does
    not choose — it comes from the tokenizer, and a mismatch between tokenizer and weight matrix is a
    configuration error that must be named as one rather than surfacing as an index.

    @capability mlp_vocab_check
    complexity: O(1)
    counts:
    - dim n_tok <= MLP_MAX_TOKENS [kernel_validated]
    - dim vocab <= MLP_MAX_VOCAB [kernel_validated]
    - dim d_model <= MLP_MAX_DIM [kernel_validated]
    @endcapability
    """
    if n_tok <= 0 or vocab <= 0 or d_model <= 0:
        return MLP_ERR_EMPTY_DIM
    if n_tok > MLP_MAX_TOKENS or vocab > MLP_MAX_VOCAB or d_model > MLP_MAX_DIM:
        return MLP_ERR_DIM_TOO_LARGE
    if not mlp_work_fits(n_tok, d_model, 1, MLP_MAX_WORK_CELLS):
        return MLP_ERR_WORK_TOO_LARGE
    if not mlp_work_fits(vocab, d_model, 1, MLP_MAX_WORK_CELLS):
        return MLP_ERR_WORK_TOO_LARGE
    return MLP_OK


fn mlp_activation_known(kind: Int) -> Bool:
    """True for a selector this package implements.

    An unknown activation is refused rather than defaulted. Defaulting to SwiGLU would be right for
    Llama-family models and wrong for every GELU one, and the symptom is a model that runs.
    """
    return kind == MLP_ACT_SWIGLU or kind == MLP_ACT_GEGLU_TANH or kind == MLP_ACT_GEGLU_ERF


fn mlp_scalars_ok(value: Float64) -> Bool:
    """True when a scalar is finite. Checked before it can turn a whole tensor into NaN."""
    return tx_finite(value)


fn mlp_tol_for(magnitude: Float64, reduction_width: Int) -> Float64:
    """Tolerance for comparing two spellings of a value of size `magnitude` (rule 4b).

    Scales with the quantity judged AND with the reduction that produced it: a feed-forward output is
    a sum over `d_model` products, so its rounding error grows with the model width. The `1.0 +`
    floor keeps a value that legitimately lands near zero from being held to an impossible bound.
    """
    var width = Float64(reduction_width) if reduction_width > 0 else 1.0
    var mag = magnitude if magnitude >= 0.0 else -magnitude
    return 1.0e-14 * (1.0 + mag) * (1.0 + width)
