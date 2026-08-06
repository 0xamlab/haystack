"""test_llmk_residual.mojo — the whole-buffer residual add a transformer decoder layer calls twice.

Hand-written. `residual_add_flat` is the one new kernel `llmk` supplies (embedding gather and RoPE
already existed elsewhere in the plane and are reused, not duplicated — see `llmk/__init__.mojo`).
The correctness claim is trivial arithmetic; the claim worth testing is the guard: `n` bigger than
either real buffer must be refused rather than read past the shorter one, because a `List` read past
its end in Mojo is an UNCATCHABLE process abort, not an exception (rule 1).
"""
from llmk.contract import LLMK_ERR_A_LENGTH, LLMK_ERR_B_LENGTH, LLMK_ERR_EMPTY_DIM, LLMK_OK
from llmk.residual import residual_add_flat


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── basic correctness ──────────────────────────────────────────────────────
    var a = List[Float64]()
    var b = List[Float64]()
    for i in range(6):
        a.append(Float64(i))
        b.append(Float64(10 - i))
    var out = residual_add_flat(a, b, 6)
    var ok = out.status == LLMK_OK
    for i in range(6):
        if _abs(out.out[i] - 10.0) > 1e-12:
            ok = False
    if ok:
        passed += 1
        print("  ✅ a[i] + b[i] == 10.0 for every i, by construction")
    else:
        failed += 1
        print("  ❌ residual add produced the wrong sum")

    # ── residual is exactly what a decoder layer needs: hidden = residual + block_out ──
    var residual_stream = List[Float64]()
    var block_out = List[Float64]()
    for i in range(4096):
        residual_stream.append(Float64(i) * 0.001)
        block_out.append(Float64(i) * -0.0005)
    var big = residual_add_flat(residual_stream, block_out, 4096)
    var worst = 0.0
    for i in range(4096):
        var expected = residual_stream[i] + block_out[i]
        var delta = _abs(big.out[i] - expected)
        if delta > worst:
            worst = delta
    if big.status == LLMK_OK and worst == 0.0 and big.n == 4096:
        passed += 1
        print("  ✅ a 4096-element add (crosses the parallel threshold) is bit-identical to serial")
    else:
        failed += 1
        print("  ❌ the parallel band drifted from serial by", worst)

    # ── refusals: n larger than either real buffer must not be read past the end ──
    var short_a = List[Float64]()
    short_a.append(1.0)
    short_a.append(2.0)
    var full_b = List[Float64]()
    for i in range(6):
        full_b.append(Float64(i))
    if residual_add_flat(short_a, full_b, 6).status == LLMK_ERR_A_LENGTH:
        passed += 1
        print("  ✅ n=6 against a 2-element `a` is refused, not read past the end")
    else:
        failed += 1
        print("  ❌ a short `a` was accepted -- this WOULD abort the worker")

    if residual_add_flat(full_b, short_a, 6).status == LLMK_ERR_B_LENGTH:
        passed += 1
        print("  ✅ ...and the same guard applies to `b`")
    else:
        failed += 1
        print("  ❌ a short `b` was accepted -- this WOULD abort the worker")

    if residual_add_flat(full_b, full_b, 0).status == LLMK_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ n=0 is refused rather than returning an empty success")
    else:
        failed += 1
        print("  ❌ n=0 was not refused")

    # ── the exact shape the generated A-Z suite calls every contract function with ──
    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    var az = residual_add_flat(lf5, lf5, 5)
    if az.status == LLMK_OK and az.n == 5:
        passed += 1
        print("  ✅ the A-Z call shape (5-element lists, Int=5) is exactly in-bounds and succeeds")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was wrongly refused:", az.status)

    print("  [llmk.residual] Passed:", passed, "Failed:", failed)
