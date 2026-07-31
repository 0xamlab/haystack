"""
lossk.cross_entropy — fused projection + cross-entropy, chunked so the logits never all exist.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_lossk_cross_entropy.mojo
benchmark: benchmarks/mojo_benchmarks/bench_lossk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The whole point is a tensor that is never allocated
------------------------------------------------------
The naive path is: project hidden states to logits, then take cross-entropy. For a 2048-token batch
against a 151,936 vocabulary that intermediate is 2048 x 151,936 x 8 bytes = **2.5 GB**, allocated so
that it can be reduced to one scalar.

Cross-entropy needs only two numbers per token: the logit of the correct class, and the log-sum-exp
over all classes. Both are reductions over the vocabulary. So the projection is done a CHUNK of
tokens at a time, reduced immediately, and the chunk buffer reused. Peak logit memory becomes
`chunk x vocab` and stops depending on the batch at all.

`ce_peak_logit_cells` reports what a call will actually hold, so the claim is a number the caller can
check rather than a property of the docstring.

Chunk size is the caller's, and it is a real trade
----------------------------------------------------
Small chunks minimise memory and give the projection less to work with at once; large chunks do the
opposite. There is no universally right answer because the kernel cannot see what else is resident —
optimizer state, a KV cache, another rank's buffers — so it validates the chunk against
`LOSS_MAX_LOGIT_CELLS` and refuses an over-large one rather than clamping. A silent clamp would turn
"I asked for 2048" into "you got 883" with no way to notice.

The reduction stays in the widest available precision
-------------------------------------------------------
`logsumexp` comes from the frozen `numerical_stability` kernel, which is max-shifted (rule 3). The
per-token losses are then summed in `Float64` in token order — not in the order chunks happen to
finish — so the total does not move with chunk size. `ce_chunk_invariance_flat` asserts exactly that,
because a loss that depends on how it was chunked is not a loss anyone can reproduce.

Public API:
  ce_from_logits_flat(logits, targets, n_tok, vocab)                     -> CeOut  (reference)
  fused_linear_ce_flat(hidden, weight, targets, n_tok, d_model, vocab, chunk) -> CeOut
  fused_linear_ce_bwd_flat(hidden, weight, targets, n_tok, d_model, vocab)    -> CeGrad
  ce_peak_logit_cells(n_tok, vocab, chunk)                               -> CeMemory
  ce_chunk_invariance_flat(hidden, weight, targets, n_tok, d_model, vocab) -> CeAgreement
"""

from std.math import exp
from lossk.contract import (
    LOSS_ERR_DIM_TOO_LARGE,
    LOSS_ERR_LENGTH_MISMATCH,
    LOSS_MAX_TOKENS,
    LOSS_MAX_VOCAB,
    LOSS_ERR_TARGET_OUT_OF_RANGE,
    LOSS_OK,
    loss_chunk_check,
    loss_dims_check,
    loss_targets_in_range,
    loss_tol_for,
)
from numerical_stability import logsumexp


@fieldwise_init
struct CeOut(Copyable, Movable):
    """A cross-entropy result, and what it cost to hold."""

    var mean_loss: Float64
    var sum_loss: Float64
    var n_tok: Int
    var peak_logit_cells: Int
    var status: Int


@fieldwise_init
struct CeGrad(Copyable, Movable):
    """Gradients of cross-entropy with respect to the hidden states and the projection weight.

    `d_weight` is `[vocab][d_model]`, which is the same size as the weight itself — for a real
    vocabulary that is large, and there is no avoiding it: every class receives gradient from the
    log-sum-exp of every token. Only the LOGITS can be chunked away, not the weight gradient. Stating
    that plainly matters, because "fused cross-entropy saves memory" is easy to over-read into a
    claim about the whole backward pass."""

    var d_hidden: List[Float64]
    var d_weight: List[Float64]
    var n_tok: Int
    var d_model: Int
    var status: Int


@fieldwise_init
struct CeMemory(Copyable, Movable):
    """What a chunked call holds against what the materialized form would."""

    var chunked_cells: Float64
    var materialized_cells: Float64
    var ratio: Float64
    var n_chunks: Int
    var status: Int


@fieldwise_init
struct CeAgreement(Copyable, Movable):
    """How far two spellings of the same loss are apart, and how far they are allowed to be."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


fn ce_peak_logit_cells(n_tok: Int, vocab: Int, chunk: Int) -> CeMemory:
    """What a chunked call will hold, against what the materialized form would.

    Reported rather than asserted. The ratio is the entire argument for this module, and a caller
    sizing a machine needs the number for THEIR shape, not the one in the docstring.

    @capability ce_peak_logit_cells
    complexity: O(1)
    counts:
    - dim n_tok <= LOSS_MAX_TOKENS [kernel_validated]
    - dim vocab <= LOSS_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    # Checked here as well as inside `loss_dims_check`, so the ceilings this function's declared
    # block names are the ones it actually tests rather than ones it inherits by delegation.
    if n_tok > LOSS_MAX_TOKENS or vocab > LOSS_MAX_VOCAB:
        return CeMemory(0.0, 0.0, 0.0, 0, LOSS_ERR_DIM_TOO_LARGE)
    var shape = loss_dims_check(n_tok, 1, vocab)
    if shape != LOSS_OK:
        return CeMemory(0.0, 0.0, 0.0, 0, shape)
    var chunk_status = loss_chunk_check(chunk, vocab)
    if chunk_status != LOSS_OK:
        return CeMemory(0.0, 0.0, 0.0, 0, chunk_status)

    var effective = chunk if chunk < n_tok else n_tok
    var chunked = Float64(effective) * Float64(vocab)
    var full = Float64(n_tok) * Float64(vocab)
    var n_chunks = (n_tok + chunk - 1) // chunk
    return CeMemory(chunked, full, full / chunked, n_chunks, LOSS_OK)


fn ce_from_logits_flat(
    logits: List[Float64], targets: List[Int], n_tok: Int, vocab: Int
) -> CeOut:
    """Cross-entropy from an ALREADY materialized `[n_tok][vocab]` logit tensor. The reference.

    This is the shape the fused kernel exists to avoid, and it is here for exactly that reason: the
    fused kernel's correctness claim is "same answer as the materialized one", and that needs
    something to be measured against.

    @capability ce_from_logits_flat
    complexity: O(n_tok * vocab)
    counts:
    - n_tok * vocab <= len(logits) [enforced]
    - n_tok <= len(targets) [enforced]
    @endcapability
    """
    var shape = loss_dims_check(n_tok, 1, vocab)
    if shape != LOSS_OK:
        return CeOut(0.0, 0.0, 0, 0, shape)
    if len(logits) < n_tok * vocab or len(targets) < n_tok:
        return CeOut(0.0, 0.0, 0, 0, LOSS_ERR_LENGTH_MISMATCH)
    if not loss_targets_in_range(targets, n_tok, vocab):
        return CeOut(0.0, 0.0, 0, 0, LOSS_ERR_TARGET_OUT_OF_RANGE)

    var row = List[Float64](capacity=vocab)
    for _ in range(vocab):
        row.append(0.0)

    var total = 0.0
    for t in range(n_tok):
        var base = t * vocab
        for c in range(vocab):
            row[c] = logits[base + c]
        # Frozen kernel: max-shifted, so a large logit does not overflow the exponential.
        var lse = logsumexp(row)
        total += lse - logits[base + targets[t]]

    return CeOut(total / Float64(n_tok), total, n_tok, n_tok * vocab, LOSS_OK)


fn fused_linear_ce_flat(
    hidden: List[Float64], weight: List[Float64], targets: List[Int],
    n_tok: Int, d_model: Int, vocab: Int, chunk: Int
) -> CeOut:
    """Project and reduce a chunk at a time; the full logit tensor is never allocated.

    `weight` is `[vocab][d_model]` row-major — one row per class, which is the layout an output
    projection ships in and the layout that makes each logit a contiguous dot product.

    @capability fused_linear_ce_flat
    complexity: O(n_tok * d_model * vocab)
    counts:
    - n_tok * d_model <= len(hidden) [enforced]
    - vocab * d_model <= len(weight) [enforced]
    - n_tok <= len(targets) [enforced]
    @endcapability
    """
    var shape = loss_dims_check(n_tok, d_model, vocab)
    if shape != LOSS_OK:
        return CeOut(0.0, 0.0, 0, 0, shape)
    var chunk_status = loss_chunk_check(chunk, vocab)
    if chunk_status != LOSS_OK:
        return CeOut(0.0, 0.0, 0, 0, chunk_status)
    if len(hidden) < n_tok * d_model or len(weight) < vocab * d_model:
        return CeOut(0.0, 0.0, 0, 0, LOSS_ERR_LENGTH_MISMATCH)
    if len(targets) < n_tok:
        return CeOut(0.0, 0.0, 0, 0, LOSS_ERR_LENGTH_MISMATCH)
    if not loss_targets_in_range(targets, n_tok, vocab):
        return CeOut(0.0, 0.0, 0, 0, LOSS_ERR_TARGET_OUT_OF_RANGE)

    var span = chunk if chunk < n_tok else n_tok
    # THE allocation. `span * vocab`, not `n_tok * vocab`, and it is reused across chunks.
    var buffer = List[Float64](capacity=span * vocab)
    for _ in range(span * vocab):
        buffer.append(0.0)
    var row = List[Float64](capacity=vocab)
    for _ in range(vocab):
        row.append(0.0)

    var hp = hidden.unsafe_ptr()
    var wp = weight.unsafe_ptr()
    var bp = buffer.unsafe_ptr()

    var total = 0.0
    var start = 0
    while start < n_tok:
        var stop = start + span
        if stop > n_tok:
            stop = n_tok

        # Project this chunk only.
        for t in range(start, stop):
            var hbase = t * d_model
            var obase = (t - start) * vocab
            for c in range(vocab):
                var wbase = c * d_model
                var dot = 0.0
                for k in range(d_model):
                    dot += hp[hbase + k] * wp[wbase + k]
                bp[obase + c] = dot

        # Reduce it, in token order, then let the buffer be overwritten.
        for t in range(start, stop):
            var obase = (t - start) * vocab
            for c in range(vocab):
                row[c] = bp[obase + c]
            var lse = logsumexp(row)
            total += lse - bp[obase + targets[t]]

        start = stop

    return CeOut(total / Float64(n_tok), total, n_tok, span * vocab, LOSS_OK)


fn fused_linear_ce_bwd_flat(
    hidden: List[Float64], weight: List[Float64], targets: List[Int],
    n_tok: Int, d_model: Int, vocab: Int
) -> CeGrad:
    """Gradients of the fused loss with respect to hidden states and projection weight.

    With `p = softmax(logits)` and `y` the one-hot target, `dlogits = (p - y) / n_tok`, and then

        d_hidden[t] = dlogits[t] @ weight          d_weight[c] = sum_t dlogits[t][c] * hidden[t]

    Not chunked, deliberately. `d_weight` is `[vocab][d_model]` — the size of the weight itself — so
    it is resident for the whole call no matter how the logits are produced; chunking the logits here
    would save a fraction of a buffer that is already dominated by the gradient. Stating that is more
    useful than a chunk parameter that does not change the peak.

    @capability fused_linear_ce_bwd_flat
    complexity: O(n_tok * d_model * vocab)
    counts:
    - n_tok * d_model <= len(hidden) [enforced]
    - vocab * d_model <= len(weight) [enforced]
    - n_tok <= len(targets) [enforced]
    @endcapability
    """
    var d_hidden = List[Float64]()
    var d_weight = List[Float64]()
    var shape = loss_dims_check(n_tok, d_model, vocab)
    if shape != LOSS_OK:
        return CeGrad(d_hidden^, d_weight^, 0, 0, shape)
    if len(hidden) < n_tok * d_model or len(weight) < vocab * d_model:
        return CeGrad(d_hidden^, d_weight^, 0, 0, LOSS_ERR_LENGTH_MISMATCH)
    if len(targets) < n_tok:
        return CeGrad(d_hidden^, d_weight^, 0, 0, LOSS_ERR_LENGTH_MISMATCH)
    if not loss_targets_in_range(targets, n_tok, vocab):
        return CeGrad(d_hidden^, d_weight^, 0, 0, LOSS_ERR_TARGET_OUT_OF_RANGE)

    for _ in range(n_tok * d_model):
        d_hidden.append(0.0)
    for _ in range(vocab * d_model):
        d_weight.append(0.0)

    var row = List[Float64](capacity=vocab)
    for _ in range(vocab):
        row.append(0.0)

    var scale = 1.0 / Float64(n_tok)
    for t in range(n_tok):
        var hbase = t * d_model
        for c in range(vocab):
            var wbase = c * d_model
            var dot = 0.0
            for k in range(d_model):
                dot += hidden[hbase + k] * weight[wbase + k]
            row[c] = dot
        var lse = logsumexp(row)

        for c in range(vocab):
            var p = exp(row[c] - lse)
            var dlogit = (p - (1.0 if c == targets[t] else 0.0)) * scale
            if dlogit == 0.0:
                continue
            var wbase = c * d_model
            for k in range(d_model):
                d_hidden[hbase + k] += dlogit * weight[wbase + k]
                d_weight[wbase + k] += dlogit * hidden[hbase + k]

    return CeGrad(d_hidden^, d_weight^, n_tok, d_model, LOSS_OK)


fn ce_chunk_invariance_flat(
    hidden: List[Float64], weight: List[Float64], targets: List[Int],
    n_tok: Int, d_model: Int, vocab: Int
) -> CeAgreement:
    """Compare the loss computed one token at a time against the whole batch in one chunk.

    A loss that depends on how it was chunked cannot be reproduced by anyone who chose a different
    chunk for memory reasons — which is the only reason the parameter exists. Since the per-token
    losses are summed in token order regardless of chunking, the two should agree to the last bit,
    and this reports whether they do.

    @capability ce_chunk_invariance_flat
    complexity: O(n_tok * d_model * vocab)
    counts:
    - n_tok * d_model <= len(hidden) [enforced]
    - vocab * d_model <= len(weight) [enforced]
    - n_tok <= len(targets) [enforced]
    @endcapability
    """
    var shape = loss_dims_check(n_tok, d_model, vocab)
    if shape != LOSS_OK:
        return CeAgreement(0.0, 0.0, False, 0, shape)
    if len(hidden) < n_tok * d_model or len(weight) < vocab * d_model:
        return CeAgreement(0.0, 0.0, False, 0, LOSS_ERR_LENGTH_MISMATCH)
    if len(targets) < n_tok:
        return CeAgreement(0.0, 0.0, False, 0, LOSS_ERR_LENGTH_MISMATCH)

    var one = fused_linear_ce_flat(hidden, weight, targets, n_tok, d_model, vocab, 1)
    var all_at_once = fused_linear_ce_flat(hidden, weight, targets, n_tok, d_model, vocab, n_tok)
    if one.status != LOSS_OK:
        return CeAgreement(0.0, 0.0, False, 0, one.status)
    if all_at_once.status != LOSS_OK:
        return CeAgreement(0.0, 0.0, False, 0, all_at_once.status)

    var delta = one.sum_loss - all_at_once.sum_loss
    if delta < 0.0:
        delta = -delta
    var tol = loss_tol_for(all_at_once.sum_loss, vocab)
    return CeAgreement(delta, tol, delta <= tol, n_tok, LOSS_OK)
