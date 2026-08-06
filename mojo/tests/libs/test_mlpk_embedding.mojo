"""test_mlpk_embedding.mojo — the bounds guard that keeps the worker alive, and a stable scatter-add.

Hand-written. This module is named in the plan as the single highest-probability way the A-Z suite
takes the whole worker down, so the refusals are the headline rather than an afterthought.

THE ABORT. The generated suite calls every contract function with a five-element list and `5` for
every `Int`. Here that is `embedding_fwd_flat([5 floats], [5 ids], n_tok=5, vocab=5, d_model=5)` — a
request to read `weight[24]` from a buffer holding 5. Reading past a `List` in Mojo is an UNCATCHABLE
bounds assertion: it kills the process, and a `try`/`except` at any layer above does not help. So the
test asserts that call is REFUSED, and separately that an id equal to `vocab` (the classic off-by-one)
is refused rather than clamped. A clamped id trains the wrong row and the run completes, which is
worse than an error.

THE SCATTER ORDER. Several tokens map to one vocabulary row, so the backward has real write conflicts.
The kernel splits by column so each row accumulates in token order regardless of worker count. Tested
by shape: a batch large enough to cross the parallel threshold must produce a gradient bit-identical
to a serial reference.
"""
from mlpk.contract import MLP_ERR_LENGTH_MISMATCH, MLP_ERR_TOKEN_OUT_OF_RANGE, MLP_OK
from mlpk.embedding import embedding_bwd_flat, embedding_fwd_flat, embedding_ids_in_range


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var vocab = 6
    var d = 4
    var w = List[Float64](capacity=vocab * d)
    for i in range(vocab * d):
        w.append(Float64(i))
    var ids = List[Int]()
    ids.append(2)
    ids.append(0)
    ids.append(2)
    ids.append(5)
    var n_tok = 4

    # ── the gather ────────────────────────────────────────────────────────────
    var out = embedding_fwd_flat(w, ids, n_tok, vocab, d)
    if out.status == MLP_OK and out.y[0] == 8.0 and out.y[3] == 11.0 and out.y[12] == 20.0:
        passed += 1
        print("  ✅ the gather returns row `id`, not row `t` — token 0 -> row 2 -> [8..11]")
    else:
        failed += 1
        print("  ❌ the gather picked the wrong rows:", out.status, out.y[0])

    # ── the scatter-add ───────────────────────────────────────────────────────
    var dy = List[Float64](capacity=n_tok * d)
    for _ in range(n_tok * d):
        dy.append(1.0)
    var g = embedding_bwd_flat(dy, ids, n_tok, vocab, d)

    # Row 2 appears twice, rows 0 and 5 once, rows 1/3/4 never.
    if g.status == MLP_OK and g.d_weight[2 * d] == 2.0 and g.d_weight[0] == 1.0 and g.d_weight[5 * d] == 1.0:
        passed += 1
        print("  ✅ a repeated token accumulates: row 2 got 2.0 from two hits")
    else:
        failed += 1
        print("  ❌ the scatter-add did not accumulate:", g.d_weight[2 * d])

    if g.d_weight[1 * d] == 0.0 and g.d_weight[3 * d] == 0.0 and g.d_weight[4 * d] == 0.0:
        passed += 1
        print("  ✅ untouched vocabulary rows stay exactly zero")
    else:
        failed += 1
        print("  ❌ an untouched row was written:", g.d_weight[1 * d])

    if g.n_touched == 3:
        passed += 1
        print("  ✅ n_touched counts DISTINCT rows (3), not tokens (4)")
    else:
        failed += 1
        print("  ❌ n_touched miscounted:", g.n_touched)

    # ── the scatter is stable across worker counts ────────────────────────────
    # 4096 tokens x 16 dims crosses the parallel threshold; the small case above does not.
    var big_vocab = 32
    var big_d = 16
    var big_tok = 4096
    var big_ids = List[Int](capacity=big_tok)
    for t in range(big_tok):
        big_ids.append((t * 7) % big_vocab)
    var big_dy = List[Float64](capacity=big_tok * big_d)
    for i in range(big_tok * big_d):
        big_dy.append(Float64((i % 13)) * 0.25 - 1.0)
    var big_grad = embedding_bwd_flat(big_dy, big_ids, big_tok, big_vocab, big_d)

    var worst = 0.0
    for row in range(big_vocab):
        for j in range(big_d):
            var reference = 0.0
            for t in range(big_tok):
                if big_ids[t] == row:
                    reference += big_dy[t * big_d + j]
            var delta = _abs(big_grad.d_weight[row * big_d + j] - reference)
            if delta > worst:
                worst = delta
    if big_grad.status == MLP_OK and worst == 0.0:
        passed += 1
        print("  ✅ the parallel scatter is bit-identical to a serial token-order sum over", big_tok, "tokens")
    else:
        failed += 1
        print("  ❌ the parallel scatter drifted from serial by", worst)

    # ── refusals: this is the module that can kill the worker ─────────────────
    var lf5 = List[Float64]()
    var li5 = List[Int]()
    for _ in range(5):
        lf5.append(0.5)
        li5.append(5)
    # weight[24] from a 5-element buffer. The exact call the generated A-Z suite makes.
    if embedding_fwd_flat(lf5, li5, 5, 5, 5).status == MLP_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted — this WILL abort the worker")

    if embedding_bwd_flat(lf5, li5, 5, 5, 5).status == MLP_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ ...and so is the backward's")
    else:
        failed += 1
        print("  ❌ the backward accepted the A-Z call shape")

    var at_vocab = List[Int]()
    at_vocab.append(vocab)
    if embedding_fwd_flat(w, at_vocab, 1, vocab, d).status == MLP_ERR_TOKEN_OUT_OF_RANGE:
        passed += 1
        print("  ✅ id == vocab is refused, not clamped to the last row")
    else:
        failed += 1
        print("  ❌ an off-by-one id was accepted")

    var negative = List[Int]()
    negative.append(-1)
    if embedding_fwd_flat(w, negative, 1, vocab, d).status == MLP_ERR_TOKEN_OUT_OF_RANGE:
        passed += 1
        print("  ✅ a negative id is refused rather than indexing backwards")
    else:
        failed += 1
        print("  ❌ a negative id was accepted")

    # The validator is public so a caller can check a batch ONCE, before the step.
    if embedding_ids_in_range(ids, n_tok, vocab) and not embedding_ids_in_range(at_vocab, 1, vocab):
        passed += 1
        print("  ✅ embedding_ids_in_range answers both ways without running a step")
    else:
        failed += 1
        print("  ❌ the standalone id validator disagrees with the kernels")

    print("  [mlpk.embedding] Passed:", passed, "Failed:", failed)
