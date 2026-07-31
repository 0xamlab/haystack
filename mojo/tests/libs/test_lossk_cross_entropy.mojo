"""test_lossk_cross_entropy.mojo — the loss that must not allocate, and must not depend on how it was chunked.

Hand-written. Three properties carry this file.

1. CHUNK INVARIANCE, BIT-FOR-BIT. The chunk parameter exists so a caller can trade memory for
   batching efficiency. If the answer moved with the chunk, that trade would silently change the
   model — two engineers on different-sized machines would get different losses from identical
   inputs and neither would know. Per-token losses are summed in token order regardless of chunking,
   so the requirement is equality to the last bit, not to a tolerance.

2. AGREEMENT WITH THE MATERIALIZED FORM. The fused kernel's whole claim is "same answer, without the
   2.5 GB tensor". The materialized reference is here to be that answer.

3. THE MEMORY CLAIM IS A MEASURED NUMBER. `peak_logit_cells` is asserted to scale with the CHUNK and
   not with the batch, which is the only reason this module exists.

Plus the refusals. A target indexes a logit row, so an out-of-range one reads past a buffer and
aborts the worker uncatchably — and a chunk that would exceed the logit budget is refused rather than
clamped, because a clamp turns "I asked for 2048" into "you got 883" with nothing to notice.
"""
from lossk.contract import (
    LOSS_ERR_BAD_CHUNK,
    LOSS_ERR_LENGTH_MISMATCH,
    LOSS_ERR_TARGET_OUT_OF_RANGE,
    LOSS_OK,
)
from lossk.cross_entropy import (
    ce_chunk_invariance_flat,
    ce_from_logits_flat,
    ce_peak_logit_cells,
    fused_linear_ce_bwd_flat,
    fused_linear_ce_flat,
)
from std.math import log


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 23)) / 11.0 - 1.0)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var n_tok = 6
    var d = 4
    var vocab = 9
    var h = _pseudo(n_tok * d, 1)
    var w = _pseudo(vocab * d, 5)
    var targets = List[Int](capacity=n_tok)
    for t in range(n_tok):
        targets.append((t * 3) % vocab)

    # ── the materialized reference ────────────────────────────────────────────
    var logits = List[Float64](capacity=n_tok * vocab)
    for t in range(n_tok):
        for c in range(vocab):
            var dot = 0.0
            for k in range(d):
                dot += h[t * d + k] * w[c * d + k]
            logits.append(dot)
    var baseline = ce_from_logits_flat(logits, targets, n_tok, vocab)

    if baseline.status == LOSS_OK and baseline.mean_loss > 0.0:
        passed += 1
        print("  ✅ the materialized reference computes a positive loss:", baseline.mean_loss)
    else:
        failed += 1
        print("  ❌ the reference failed:", baseline.status)

    # ── 1. chunk invariance, bit for bit ──────────────────────────────────────
    var worst = 0.0
    var smallest_peak = 1 << 30
    var largest_peak = 0
    for chunk in range(1, n_tok + 1):
        var f = fused_linear_ce_flat(h, w, targets, n_tok, d, vocab, chunk)
        if f.status != LOSS_OK:
            failed += 1
            print("  ❌ chunk", chunk, "failed:", f.status)
            continue
        var delta = _abs(f.mean_loss - baseline.mean_loss)
        if delta > worst:
            worst = delta
        if f.peak_logit_cells < smallest_peak:
            smallest_peak = f.peak_logit_cells
        if f.peak_logit_cells > largest_peak:
            largest_peak = f.peak_logit_cells

    if worst == 0.0:
        passed += 1
        print("  ✅ every chunk size from 1 to", n_tok, "gives a BIT-IDENTICAL loss")
    else:
        failed += 1
        print("  ❌ the loss moved with chunk size by", worst)

    var inv = ce_chunk_invariance_flat(h, w, targets, n_tok, d, vocab)
    if inv.status == LOSS_OK and inv.max_abs_delta == 0.0:
        passed += 1
        print("  ✅ one-token-at-a-time equals whole-batch-at-once exactly")
    else:
        failed += 1
        print("  ❌ chunk invariance reported", inv.max_abs_delta)

    # ── 2. the fused kernel agrees with the materialized one ──────────────────
    var fused = fused_linear_ce_flat(h, w, targets, n_tok, d, vocab, 2)
    if fused.status == LOSS_OK and _abs(fused.mean_loss - baseline.mean_loss) == 0.0:
        passed += 1
        print("  ✅ fused equals materialized without ever building the logit tensor")
    else:
        failed += 1
        print("  ❌ fused and materialized disagree by",
              _abs(fused.mean_loss - baseline.mean_loss))

    # ── 3. the memory claim, as a number ──────────────────────────────────────
    if smallest_peak == vocab and largest_peak == n_tok * vocab:
        passed += 1
        print("  ✅ peak logit cells track the CHUNK:", smallest_peak, "at chunk 1 vs",
              largest_peak, "at chunk", n_tok)
    else:
        failed += 1
        print("  ❌ peak cells did not track the chunk:", smallest_peak, largest_peak)

    # A real shape: 2048 tokens against a 151,936 vocabulary.
    var mem = ce_peak_logit_cells(2048, 151936, 256)
    if mem.status == LOSS_OK and mem.ratio > 7.9 and mem.ratio < 8.1:
        passed += 1
        print("  ✅ at a Qwen3 shape a 256-token chunk holds", mem.ratio, "x less than materialized")
    else:
        failed += 1
        print("  ❌ the memory ratio moved:", mem.ratio)

    # ── a known value: uniform logits give log(vocab) ─────────────────────────
    # With every logit equal, softmax is uniform, so the loss is exactly log(vocab) for any target.
    var flat_logits = List[Float64](capacity=n_tok * vocab)
    for _ in range(n_tok * vocab):
        flat_logits.append(0.25)
    var uniform = ce_from_logits_flat(flat_logits, targets, n_tok, vocab)
    if _abs(uniform.mean_loss - log(Float64(vocab))) < 1.0e-14:
        passed += 1
        print("  ✅ uniform logits give exactly log(vocab):", uniform.mean_loss)
    else:
        failed += 1
        print("  ❌ the uniform case gave", uniform.mean_loss, "expected", log(Float64(vocab)))

    # ── the backward ──────────────────────────────────────────────────────────
    var grad = fused_linear_ce_bwd_flat(h, w, targets, n_tok, d, vocab)
    if grad.status == LOSS_OK:
        passed += 1
        print("  ✅ the backward returns both gradients")
    else:
        failed += 1
        print("  ❌ the backward failed:", grad.status)

    # Sum of d_logits over the vocabulary is zero for every token, because softmax sums to one and
    # the one-hot sums to one. That propagates: summing d_weight over ALL classes for a given input
    # dimension must cancel to zero. It is a strong, cheap check on the whole backward.
    var worst_cancel = 0.0
    for k in range(d):
        var total = 0.0
        for c in range(vocab):
            total += grad.d_weight[c * d + k]
        if _abs(total) > worst_cancel:
            worst_cancel = _abs(total)
    # The algebra says exactly zero; the toolchain says ~5e-11, and that is not a bug in the
    # backward. `logsumexp` calls `std.math.log`, which is NOT correctly rounded here — log(1.5) is
    # off by 8.2e-11 and log(100) by 2.6e-10 — so `sum(softmax)` lands near 1 rather than on it and
    # the cancellation inherits that. 1e-9 is the measured floor (LOSS_TRANSCENDENTAL_FLOOR); a real
    # sign or index error in the backward moves this by O(1), so the check still has teeth.
    if worst_cancel < 1.0e-9:
        passed += 1
        print("  ✅ d_weight cancels across the vocabulary to", worst_cancel,
              "— the log/exp floor, not a gradient error")
    else:
        failed += 1
        print("  ❌ d_weight failed to cancel:", worst_cancel)

    # Numeric check of d_hidden against a central difference of the loss.
    var probe = List[Float64](capacity=n_tok * d)
    for i in range(n_tok * d):
        probe.append(h[i])
    var step = 1.0e-5
    var worst_grad = 0.0
    for i in range(n_tok * d):
        var original = probe[i]
        probe[i] = original + step
        var up = fused_linear_ce_flat(probe, w, targets, n_tok, d, vocab, 2).mean_loss
        probe[i] = original - step
        var down = fused_linear_ce_flat(probe, w, targets, n_tok, d, vocab, 2).mean_loss
        probe[i] = original
        var numeric = (up - down) / (2.0 * step)
        var delta = _abs(grad.d_hidden[i] - numeric)
        if delta > worst_grad:
            worst_grad = delta
    if worst_grad < 1.0e-8:
        passed += 1
        print("  ✅ d_hidden matches central differences —", worst_grad)
    else:
        failed += 1
        print("  ❌ d_hidden disagrees with central differences by", worst_grad)

    # ── refusals ──────────────────────────────────────────────────────────────
    var bad_target = List[Int](capacity=n_tok)
    for _ in range(n_tok):
        bad_target.append(vocab)
    if fused_linear_ce_flat(h, w, bad_target, n_tok, d, vocab, 2).status == LOSS_ERR_TARGET_OUT_OF_RANGE:
        passed += 1
        print("  ✅ a target equal to vocab is refused rather than indexing past the row")
    else:
        failed += 1
        print("  ❌ an out-of-range target was accepted")

    # A chunk inside the token ceiling but over the LOGIT budget: 1000 x 151,936 > 2^27.
    var big_h = _pseudo(4, 2)
    if ce_peak_logit_cells(2048, 151936, 1000).status == LOSS_ERR_BAD_CHUNK:
        passed += 1
        print("  ✅ a chunk that would exceed the logit budget is refused, not clamped")
    else:
        failed += 1
        print("  ❌ an over-budget chunk was accepted")

    var lf5 = _pseudo(5, 1)
    var li5 = List[Int]()
    for _ in range(5):
        li5.append(5)
    if fused_linear_ce_flat(lf5, lf5, li5, 5, 5, 5, 5).status == LOSS_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [lossk.cross_entropy] Passed:", passed, "Failed:", failed)
