"""
llmk.generate — the two orchestration primitives a real autoregressive decode loop needs that no
frozen kernel, and no other part of `llmk`, already supplies. Zero Python. Additive.

Why these two, and only these two
------------------------------------
`benchmarks/llm_smoke/qwen3_forward.mojo` runs one whole-prompt forward pass and stops there --
prefill, not generation. Wiring an actual decode loop on top of it
(`benchmarks/llm_smoke/qwen3_generate.mojo`) needed exactly two pieces this plane did not already
have; everything else in a decode step is the SAME frozen kernel called at a different shape:

1. KV-cache growth. `attnk.sdpa.sdpa_forward_flat` and `attnk.mask.mask_causal_flat` already support
   the decode shape explicitly, and did before this file existed -- `sdpa_forward_flat` takes
   independent `n_tok_q`/`n_tok_k`, and `mask_causal_flat` takes an `offset` whose docstring names the
   decode case by name ("offset is how many cached keys precede the first query -- the decode case").
   What neither of those supplies is the thing that grows the K/V buffer they read: a decode step
   projects K/V for only the NEW token(s) and must append them to what every earlier step already
   produced, once per layer, twice per step (K, then V). `kv_cache_append_flat` is that append,
   shape-checked the same way `llmk.residual.residual_add_flat` checks its own two operands (rule 1).
2. A full argmax from `llm_sampling.greedy_token_id`. That frozen formula is deliberately a
   per-candidate comparison -- "is THIS logit the max" -- not a full argmax; its own docstring takes
   `max_logit` as an input, meaning the caller already knows it. `greedy_argmax_flat` is the two-pass
   driver that makes it a full argmax: a linear scan for the row's true maximum (no frozen kernel
   computes a bare reduction-max, and there is no sampling decision being made in finding one), then
   the frozen per-candidate formula, called once per vocabulary entry exactly as published, to report
   which id matches it. Ties resolve to the FIRST matching id, `numpy.argmax`'s own convention, so a
   comparison against a reference implementation's argmax agrees even in the rare exact tie.

Neither of these touches `attnk`/`normk`/`mlpk`/`gemm`, neither touches `llm_sampling` or
`generation_loop` (called, not modified), and neither replaces `llmk.residual`. Shape checks
(`llmk_kv_append_dims_check`, `llmk_argmax_dims_check`) live in `llmk.contract` alongside
`llmk_residual_dims_check`, the same split `llmk.residual` already uses. Status codes are additive
within `llmk`'s own owned range 560-579 -- see `llmk.contract` for 566-568.

Public API:
  kv_cache_append_flat(cache, new_vals, cache_len, n_new)   -> KvAppendResult
  greedy_argmax_flat(logits, n)                              -> GreedyResult

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_llmk_generate.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""

from llmk.contract import LLMK_OK, llmk_argmax_dims_check, llmk_kv_append_dims_check
from llm_sampling import greedy_token_id


@fieldwise_init
struct KvAppendResult(Copyable, Movable):
    """The grown cache, its new total length (in elements), and a status code."""

    var out: List[Float64]
    var n: Int
    var status: Int


@fieldwise_init
struct GreedyResult(Copyable, Movable):
    """The argmax token id, its logit, and a status code. `token_id == -1` only on a shape failure."""

    var token_id: Int
    var logit: Float64
    var status: Int


fn kv_cache_append_flat(
    cache: List[Float64], new_vals: List[Float64], cache_len: Int, n_new: Int
) -> KvAppendResult:
    """`out = cache ++ new_vals`, exact-length on both operands (rule 1). One decode step's worth of
    freshly-projected, freshly-RoPE'd K (or V) rows, appended to what every earlier step (prefill
    included) already produced. Called twice per layer per step by `qwen3_generate.mojo` -- once for
    K, once for V -- never for Q, which is never cached (a decode step's query is always exactly the
    new token; there is nothing to look back up).

    @capability kv_cache_append_flat
    complexity: O(cache_len + n_new)
    counts:
    - cache_len == len(cache) [enforced]
    - n_new == len(new_vals) [enforced]
    @endcapability
    """
    var shape = llmk_kv_append_dims_check(cache_len, len(cache), n_new, len(new_vals))
    if shape != LLMK_OK:
        return KvAppendResult(List[Float64](), 0, shape)

    var out = List[Float64](capacity=cache_len + n_new)
    for i in range(cache_len):
        out.append(cache[i])
    for i in range(n_new):
        out.append(new_vals[i])
    return KvAppendResult(out^, cache_len + n_new, LLMK_OK)


fn greedy_argmax_flat(logits: List[Float64], n: Int) -> GreedyResult:
    """The greedy next token: argmax over one row of `n` logits, via the frozen per-candidate formula
    `llm_sampling.greedy_token_id`.

    Two passes over `logits`, not one, and deliberately so: `greedy_token_id` compares a candidate
    against a max that must already be known, so pass one finds that max (a bare linear scan -- there
    is no sampling decision being made, so no frozen formula applies to finding it), and pass two
    calls the frozen formula once per candidate, exactly as published, to report which id it is. The
    FIRST id whose logit equals the max wins, matching `numpy.argmax`'s tie-breaking convention, so a
    generated sequence compared against a reference implementation's argmax agrees even in a tie.

    @capability greedy_argmax_flat
    complexity: O(n)
    counts:
    - n == len(logits) [enforced]
    @endcapability
    """
    var shape = llmk_argmax_dims_check(n, len(logits))
    if shape != LLMK_OK:
        return GreedyResult(-1, 0.0, shape)

    var max_logit = logits[0]
    for i in range(1, n):
        if logits[i] > max_logit:
            max_logit = logits[i]

    for i in range(n):
        var r = greedy_token_id(max_logit, logits[i], Float64(i))
        if r >= 0.0:
            return GreedyResult(Int(r), logits[i], LLMK_OK)

    # Unreachable: max_logit was drawn from this same array, so some i must satisfy the comparison
    # (equality, at minimum, at the index that produced it).
    return GreedyResult(-1, 0.0, LLMK_OK)
