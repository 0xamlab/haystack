"""
mlpk.embedding — token embedding lookup and its scatter-add gradient. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_mlpk_embedding.mojo
benchmark: benchmarks/mojo_benchmarks/bench_mlpk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The forward is a gather, and the only interesting thing about it is the bounds check
--------------------------------------------------------------------------------------
`embedding_fwd_flat` reads `weight[id * d_model + j]`. A token id at or past `vocab` indexes past the
end of the buffer, and in Mojo that is an UNCATCHABLE bounds assertion: it aborts the whole worker
process, taking every resident dataset with it, and no `try`/`except` above helps.

This is not hypothetical for this function specifically. The generated A-Z suite calls every contract
function with a five-element list and `5` for every `Int`, which here means
`embedding_fwd_flat([5 floats], [5 ids], n_tok=5, vocab=5, d_model=5)` — a request to read
`weight[24]` from a buffer holding 5. Every id and every derived offset is therefore checked before a
single read, and an out-of-range id gets its own status code rather than being clamped: a clamped id
silently trains the wrong row, which is worse than an error because the run completes.

The backward is a scatter-add, and its ORDER is the design question
---------------------------------------------------------------------
Several tokens in a batch map to the same vocabulary row, so `dW[id[t]] += dy[t]` has genuine write
conflicts. The obvious parallelization — one worker per token — is a race, and even locked it sums
each row in whatever order the threads arrived, so the gradient changes run to run.

The plan's remedy for this is to sort the ids first and accumulate contiguous runs, because on a GPU
the alternative is a non-deterministic atomic scatter-add. On CPU there is a cheaper answer that needs
no sort at all: **split by COLUMN**. Each worker owns a slice of `d_model` and walks every token in
order for its own columns, so two workers never touch the same address and each column is summed in
token order. Deterministic by construction, parallel, and no permutation to build.

`sorting.counting_sort_int` is therefore deliberately NOT called here — it sorts values rather than
returning a permutation, so it could not group gradient rows anyway, and the column split makes the
question moot. A future GPU scatter path is where the sort earns its place; this is recorded so that
path does not have to rediscover why.

Public API:
  embedding_fwd_flat(weight, ids, n_tok, vocab, d_model)         -> EmbedOut
  embedding_bwd_flat(dy, ids, n_tok, vocab, d_model)             -> EmbedGrad
  embedding_ids_in_range(ids, n_tok, vocab)                      -> Bool
"""

from std.algorithm import parallelize
from std.sys.info import num_physical_cores
from mlpk.contract import (
    MLP_ERR_LENGTH_MISMATCH,
    MLP_ERR_TOKEN_OUT_OF_RANGE,
    MLP_OK,
    mlp_vocab_check,
)

comptime PARALLEL_MIN_CELLS: Int = 1 << 15
"""Below ~32k cells the fan-out costs more than the gather. Same threshold as `normk`/`gemm`."""


@fieldwise_init
struct EmbedOut(Copyable, Movable):
    """Gathered embedding rows, `[n_tok][d_model]` row-major."""

    var y: List[Float64]
    var n_tok: Int
    var d_model: Int
    var status: Int


@fieldwise_init
struct EmbedGrad(Copyable, Movable):
    """Gradient with respect to the embedding table, `[vocab][d_model]` row-major.

    Dense rather than sparse. A sparse gradient is the right representation once an optimizer can
    consume one, and nothing in this tree can yet — returning a sparse pair here would push the
    densification onto every caller and make the shape disagree with `embedding_fwd_flat`'s weight.
    `n_touched` reports how many rows are actually non-zero so a caller can see what a sparse form
    would have saved."""

    var d_weight: List[Float64]
    var n_touched: Int
    var vocab: Int
    var d_model: Int
    var status: Int


fn embedding_ids_in_range(ids: List[Int], n_tok: Int, vocab: Int) -> Bool:
    """True when every one of the first `n_tok` ids is a valid row index.

    Separate and public because a caller wants to validate a batch ONCE, before a training step, not
    discover a bad id partway through a backward pass with half a gradient already written.

    @capability embedding_ids_in_range
    complexity: O(n_tok)
    counts:
    - n_tok <= len(ids) [enforced]
    @endcapability
    """
    if n_tok <= 0 or vocab <= 0 or len(ids) < n_tok:
        return False
    for t in range(n_tok):
        var tid = ids[t]
        if tid < 0 or tid >= vocab:
            return False
    return True


fn embedding_fwd_flat(
    weight: List[Float64], ids: List[Int], n_tok: Int, vocab: Int, d_model: Int
) -> EmbedOut:
    """Gather `n_tok` rows of a `[vocab][d_model]` table.

    @capability embedding_fwd_flat
    complexity: O(n_tok * d_model)
    counts:
    - vocab * d_model <= len(weight) [enforced]
    - n_tok <= len(ids) [enforced]
    @endcapability
    """
    var y = List[Float64]()
    var shape = mlp_vocab_check(n_tok, vocab, d_model)
    if shape != MLP_OK:
        return EmbedOut(y^, 0, 0, shape)
    if len(weight) < vocab * d_model or len(ids) < n_tok:
        return EmbedOut(y^, 0, 0, MLP_ERR_LENGTH_MISMATCH)
    # Every id checked BEFORE any read. One pass costs O(n_tok) against a process abort.
    if not embedding_ids_in_range(ids, n_tok, vocab):
        return EmbedOut(y^, 0, 0, MLP_ERR_TOKEN_OUT_OF_RANGE)

    var total = n_tok * d_model
    for _ in range(total):
        y.append(0.0)

    var wp = weight.unsafe_ptr()
    var ip = ids.unsafe_ptr()
    var yp = y.unsafe_ptr()
    var d = d_model
    var n = n_tok
    var workers = num_physical_cores()
    if total < PARALLEL_MIN_CELLS or workers > n_tok:
        workers = 1

    @parameter
    fn _gather_band(tid: Int) capturing:
        var each = n // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else n
        for t in range(lo, hi):
            var src = ip[t] * d
            var dst = t * d
            for j in range(d):
                yp[dst + j] = wp[src + j]

    parallelize[_gather_band](workers)

    return EmbedOut(y^, n_tok, d_model, MLP_OK)


fn embedding_bwd_flat(
    dy: List[Float64], ids: List[Int], n_tok: Int, vocab: Int, d_model: Int
) -> EmbedGrad:
    """Scatter-add `dy` into a dense `[vocab][d_model]` gradient, deterministically.

    Parallelized by COLUMN, not by token — see the module docstring. Each worker owns a slice of
    `d_model` and walks every token in order, so no two workers write the same address and each
    column accumulates in token order regardless of how many workers there are.

    @capability embedding_bwd_flat
    complexity: O(n_tok * d_model + vocab * d_model)
    counts:
    - n_tok * d_model <= len(dy) [enforced]
    - n_tok <= len(ids) [enforced]
    @endcapability
    """
    var d_weight = List[Float64]()
    var shape = mlp_vocab_check(n_tok, vocab, d_model)
    if shape != MLP_OK:
        return EmbedGrad(d_weight^, 0, 0, 0, shape)
    if len(dy) < n_tok * d_model or len(ids) < n_tok:
        return EmbedGrad(d_weight^, 0, 0, 0, MLP_ERR_LENGTH_MISMATCH)
    if not embedding_ids_in_range(ids, n_tok, vocab):
        return EmbedGrad(d_weight^, 0, 0, 0, MLP_ERR_TOKEN_OUT_OF_RANGE)

    for _ in range(vocab * d_model):
        d_weight.append(0.0)

    var dyp = dy.unsafe_ptr()
    var ip = ids.unsafe_ptr()
    var dwp = d_weight.unsafe_ptr()
    var d = d_model
    var n = n_tok
    var workers = num_physical_cores()
    if n_tok * d_model < PARALLEL_MIN_CELLS or workers > d_model:
        workers = 1

    @parameter
    fn _scatter_band(tid: Int) capturing:
        var each = d // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else d
        for t in range(n):
            var row = ip[t] * d
            var src = t * d
            for j in range(lo, hi):
                dwp[row + j] += dyp[src + j]

    parallelize[_scatter_band](workers)

    # How many distinct rows were written. Counted with a seen-flag pass over the vocabulary rather
    # than a set, because the tree has no Dict[Int, Int] and a linear scan of `n_tok` per token would
    # be quadratic on a long batch.
    var seen = List[Bool](capacity=vocab)
    for _ in range(vocab):
        seen.append(False)
    var touched = 0
    for t in range(n_tok):
        var tid = ids[t]
        if not seen[tid]:
            seen[tid] = True
            touched += 1

    return EmbedGrad(d_weight^, touched, vocab, d_model, MLP_OK)
