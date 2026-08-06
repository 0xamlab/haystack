"""test_attnk_tiled.mojo — known-value tests for the blockwise-online-softmax attention kernel.

Hand-written. `attnk.tiled` is the register-blocked SIMD forward (`attn_forward_tiled`) plus its
materialized-score-matrix sibling (`attn_forward_direct`) and the deliberately-unstable diagnostic
(`attn_forward_unstable`) that shares its code path. The claim under test is "the tiled kernel, which
never materializes an s_q x s_kv score matrix, agrees with the one that does" — `attn_reference_delta`
is the measured evidence for that, not an assertion in a docstring.

This file also pins the two real bugs found while wiring `attnk.tiled` into a compiling state:
`attn_dims_check`'s real, tested signature is 6 args (`test_attnk_contract.mojo`), not the 9-arg call
this module's two forward entry points used before the fix, and the three length checks that call
dropped are re-asserted here directly, so a future edit that removes them again fails a test rather
than an uncatchable bounds assertion in production.
"""
from attnk.contract import (
    ATTN_BACKEND_DIRECT,
    ATTN_BACKEND_TILED,
    ATTN_BACKEND_UNSTABLE,
    ATTN_ERR_CAUSAL_SHAPE,
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_NON_FINITE_SCALE,
    ATTN_ERR_TILE,
    ATTN_OK,
    attn_backend_name,
    attn_score_bytes_fit,
    attn_status_name,
    attn_ws_bytes_direct,
    attn_ws_bytes_tiled,
)
from attnk.tiled import (
    BC_DEFAULT,
    BR_DEFAULT,
    attn_flop_count,
    attn_forward_direct,
    attn_forward_tiled,
    attn_forward_unstable,
    attn_reference_delta,
)


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var b = 1
    var hq = 4
    var hkv = 2
    var s = 40
    var d = 16
    var q = _pseudo(b * hq * s * d, 11)
    var k = _pseudo(b * hkv * s * d, 977)
    var v = _pseudo(b * hkv * s * d, 313)
    var scale = 1.0 / 4.0

    # ── tiled == direct, at the shipped defaults ──────────────────────────────
    var dl = attn_reference_delta(q, k, v, b, hq, hkv, s, s, d, scale, False)
    if dl.status == ATTN_OK and dl.within_tolerance and dl.n_compared == b * hq * s * d:
        passed += 1
        print(
            "  ✅ tiled agrees with the materialized reference — max_abs",
            dl.max_abs_delta, " max_rel", dl.max_rel_delta, " n", dl.n_compared,
        )
    else:
        failed += 1
        print("  ❌ tiled diverged from the materialized reference:", dl.status, dl.max_abs_delta)

    # ── and again causal, where the two kernels mask differently internally ──
    var dlc = attn_reference_delta(q, k, v, b, hq, hkv, s, s, d, scale, True)
    if dlc.status == ATTN_OK and dlc.within_tolerance:
        passed += 1
        print("  ✅ agreement holds causal too — max_abs", dlc.max_abs_delta)
    else:
        failed += 1
        print("  ❌ the causal case diverged:", dlc.status, dlc.max_abs_delta)

    # ── GQA: h_q a multiple of h_kv, not equal to it ──────────────────────────
    var dlg = attn_reference_delta(q, k, v, b, 4, 2, s, s, d, scale, False)
    if dlg.status == ATTN_OK and dlg.within_tolerance:
        passed += 1
        print("  ✅ agreement holds under grouped-query attention (h_q=4, h_kv=2)")
    else:
        failed += 1
        print("  ❌ the GQA case diverged")

    # ── backend tags and names round-trip ─────────────────────────────────────
    var rt = attn_forward_tiled(q, k, v, b, hq, hkv, s, s, d, scale, False, BR_DEFAULT, BC_DEFAULT, 0)
    var rd = attn_forward_direct(q, k, v, b, hq, hkv, s, s, d, scale, False, 0)
    if (
        rt.status == ATTN_OK and rt.backend_used == ATTN_BACKEND_TILED
        and attn_backend_name(rt.backend_used) == "tiled"
        and rd.status == ATTN_OK and rd.backend_used == ATTN_BACKEND_DIRECT
        and attn_backend_name(rd.backend_used) == "direct"
    ):
        passed += 1
        print("  ✅ each kernel reports its own backend tag, and the name lookup agrees")
    else:
        failed += 1
        print("  ❌ backend tagging is wrong:", rt.backend_used, rd.backend_used)

    # ── the tiled kernel's reported working set matches the formula the ─────
    # module docstring's own worked example states: br=32, bc=128, d=64 -> 176 KiB.
    var ws = attn_ws_bytes_tiled(32, 128, 64)
    if _abs(ws - 180224.0) < 1e-9:
        passed += 1
        print("  ✅ attn_ws_bytes_tiled(32, 128, 64) is exactly 180224 bytes (176 KiB), as documented")
    else:
        failed += 1
        print("  ❌ the tiled working-set formula does not match the documented example:", ws)

    # the direct kernel's reported working set is the s_q x s_kv score matrix, per head, per worker.
    var wsd = attn_ws_bytes_direct(s, s, d)
    if _abs(wsd - Float64(s * s * 8)) < 1e-9:
        passed += 1
        print("  ✅ attn_ws_bytes_direct(s, s, d) is s*s*8 bytes, independent of d")
    else:
        failed += 1
        print("  ❌ the direct working-set formula is wrong:", wsd)

    # ── attn_score_bytes_fit refuses a total that would not fit, without wrapping ──
    if attn_score_bytes_fit(1024, 1024, 16, 1 << 30) and not attn_score_bytes_fit(
        1_000_000, 1_000_000, 16, 1 << 30
    ):
        passed += 1
        print("  ✅ attn_score_bytes_fit accepts a real shape and refuses a would-be-16-TB one")
    else:
        failed += 1
        print("  ❌ attn_score_bytes_fit's budget check is wrong")

    # ── flop count matches the closed form, halved when causal ───────────────
    var flops = attn_flop_count(b, hq, s, s, d, False)
    var flops_causal = attn_flop_count(b, hq, s, s, d, True)
    if _abs(flops_causal - flops * 0.5) < 1e-9 and flops > 0.0:
        passed += 1
        print("  ✅ attn_flop_count halves for causal, as its own docstring states")
    else:
        failed += 1
        print("  ❌ attn_flop_count's causal halving is wrong")

    # ── the unstable diagnostic shares the code path and is refused the same way ──
    var ru = attn_forward_unstable(q, k, v, b, hq, hkv, s, s, d, scale, False, 0)
    if ru.status == ATTN_OK and attn_backend_name(ru.backend_used) == "unstable":
        passed += 1
        print("  ✅ the unstable diagnostic runs and tags itself correctly")
    else:
        failed += 1
        print("  ❌ the unstable diagnostic's backend tag is wrong:", ru.backend_used)

    # ── the guards a real caller can trip, and the A-Z harness cannot reach any other way ──
    # A length mismatch: `q` two elements short of what (batch, h_q, s_q, d) declares.
    var q_short = List[Float64](capacity=b * hq * s * d - 2)
    for i in range(b * hq * s * d - 2):
        q_short.append(q[i])
    var bad_len = attn_forward_tiled(
        q_short, k, v, b, hq, hkv, s, s, d, scale, False, BR_DEFAULT, BC_DEFAULT, 0
    )
    var bad_len_direct = attn_forward_direct(q_short, k, v, b, hq, hkv, s, s, d, scale, False, 0)
    if bad_len.status == ATTN_ERR_LENGTH_MISMATCH and bad_len_direct.status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a Q shorter than (batch*h_q*s_q*d) is refused on BOTH kernels, not an OOB read")
    else:
        failed += 1
        print("  ❌ the length guard did not catch a short Q:", bad_len.status, bad_len_direct.status)

    # A causal request with s_q != s_kv has no valid diagonal. k2/v2 are sized for the LARGER
    # s_kv so this trips the causal-shape check specifically, not the length check ahead of it.
    var k2 = _pseudo(b * hkv * (s + 4) * d, 977)
    var v2 = _pseudo(b * hkv * (s + 4) * d, 313)
    if attn_forward_tiled(
        q, k2, v2, b, hq, hkv, s, s + 4, d, scale, True, BR_DEFAULT, BC_DEFAULT, 0
    ).status == ATTN_ERR_CAUSAL_SHAPE:
        passed += 1
        print("  ✅ causal with s_q != s_kv is refused")
    else:
        failed += 1
        print("  ❌ an invalid causal shape was accepted")

    # A non-finite scale must be refused before any score is formed.
    var nan_v = 0.0 / 0.0
    if attn_forward_tiled(
        q, k, v, b, hq, hkv, s, s, d, nan_v, False, BR_DEFAULT, BC_DEFAULT, 0
    ).status == ATTN_ERR_NON_FINITE_SCALE:
        passed += 1
        print("  ✅ a NaN scale is refused before any score is formed")
    else:
        failed += 1
        print("  ❌ a NaN scale was accepted")

    # An invalid tile shape is refused, not silently clamped.
    if attn_forward_tiled(q, k, v, b, hq, hkv, s, s, d, scale, False, 0, 0, 0).status == ATTN_ERR_TILE:
        passed += 1
        print("  ✅ br=0, bc=0 is refused rather than silently clamped")
    else:
        failed += 1
        print("  ❌ an invalid tile shape was accepted")

    # The generic A-Z probe: 5-element lists, 5 for every Int. Every dimension implies
    # batch*h_q*s_q*d = 625 elements, so this must be refused by the length check above,
    # not read 620 elements past the end of a 5-element list.
    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    if attn_forward_tiled(lf5, lf5, lf5, 5, 5, 5, 5, 5, 5, 0.5, False, 5, 5, 5).status != ATTN_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [attnk.tiled] Passed:", passed, "Failed:", failed)
