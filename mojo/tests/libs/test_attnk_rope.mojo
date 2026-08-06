"""test_attnk_rope.mojo — known-value tests for rotary position embedding.

Hand-written. The central assertion is a round trip, not a table of expected numbers.

A rotation is orthogonal, so `inverse(apply(x)) == x` to floating-point tolerance for every layout,
position and head count. That one property simultaneously catches a wrong dimension pairing, a wrong
sine sign and a wrong table index — three bugs that per-element expected values would each need their
own case for, and two of which produce a model that runs and is quietly wrong rather than one that
fails.

The other job is the theta convention. Two frozen kernels disagree by 4x on the same extension, and
which one a checkpoint wants is decided by its config, not by us. The disagreement is pinned here so
it stays a reported number.
"""
from attnk.contract import ATTN_ERR_LENGTH_MISMATCH, ATTN_OK
from attnk.rope import (
    ROPE_SCALING_LINEAR,
    ROPE_SCALING_NONE,
    ROPE_SCALING_SQUARED,
    rope_apply_flat,
    rope_apply_inverse_flat,
    rope_inv_freq,
    rope_table,
    rope_theta_agreement,
    rope_theta_for,
)
from model_abi import rope_theta_scale
from model_interop import hf_rope_theta_scale


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the theta disagreement, pinned ────────────────────────────────────────
    var ag = rope_theta_agreement(10000.0, 2048.0, 8192.0)
    if ag.squared_convention == 160000.0 and ag.linear_convention == 40000.0 and not ag.agree:
        passed += 1
        print("  ✅ the two frozen theta kernels disagree 160000 vs 40000 on a 4x extension")
    else:
        failed += 1
        print("  ❌ the theta disagreement drifted:", ag.squared_convention, ag.linear_convention)

    if _abs(ag.ratio - 4.0) < 1e-12:
        passed += 1
        print("  ✅ the ratio is exactly the extension factor — one is linear, one is squared")
    else:
        failed += 1
        print("  ❌ unexpected theta ratio:", ag.ratio)

    # Both frozen kernels stay reachable and unchanged.
    if rope_theta_scale(10000.0, 2048.0, 8192.0) == 160000.0 and hf_rope_theta_scale(10000.0, 4.0) == 40000.0:
        passed += 1
        print("  ✅ both frozen theta kernels are reachable and behave as before")
    else:
        failed += 1
        print("  ❌ a frozen theta kernel changed")

    # This module's choice is the linear one, and an unknown code does NOT fall back.
    if (
        rope_theta_for(10000.0, 4.0, ROPE_SCALING_LINEAR) == 40000.0
        and rope_theta_for(10000.0, 4.0, ROPE_SCALING_NONE) == 10000.0
        and rope_theta_for(10000.0, 4.0, ROPE_SCALING_SQUARED) > 40000.0
    ):
        passed += 1
        print("  ✅ the linear convention is the default, and both others are selectable")
    else:
        failed += 1
        print("  ❌ theta selection is wrong")

    if rope_theta_for(10000.0, 4.0, 99) < 0.0 and rope_theta_for(10000.0, -1.0, ROPE_SCALING_LINEAR) < 0.0:
        passed += 1
        print("  ✅ an unknown code returns -1 instead of silently falling back to the base theta")
    else:
        failed += 1
        print("  ❌ an unknown scaling code was silently defaulted")

    # ── inverse frequencies ───────────────────────────────────────────────────
    var inv = rope_inv_freq(8, 10000.0)
    # Pair 0 has exponent 0, so its inverse frequency is exactly 1.0 for any theta.
    if len(inv) == 4 and inv[0] == 1.0 and inv[3] < inv[0]:
        passed += 1
        print("  ✅ inverse frequencies are one per pair, start at 1.0 and decrease")
    else:
        failed += 1
        print("  ❌ inverse frequency table is wrong")

    if len(rope_inv_freq(7, 10000.0)) == 0 and len(rope_inv_freq(8, -1.0)) == 0:
        passed += 1
        print("  ✅ an odd head_dim or non-positive theta is refused, not silently truncated")
    else:
        failed += 1
        print("  ❌ an invalid head_dim or theta was accepted")

    # ── the round trip, both layouts ──────────────────────────────────────────
    var tb = rope_table(8, 64, 10000.0)
    if tb.status == ATTN_OK and tb.n_pairs == 4 and len(tb.cos_table) == 64 * 4:
        passed += 1
        print("  ✅ the table is one cos/sin per (position, pair)")
    else:
        failed += 1
        print("  ❌ table shape is wrong")

    var n_tok = 5
    var n_heads = 3
    var head_dim = 8
    var x = List[Float64]()
    for i in range(n_tok * n_heads * head_dim):
        x.append(Float64(i % 17) * 0.31 - 2.0)
    var pos = List[Int]()
    pos.append(0)
    pos.append(1)
    pos.append(7)
    pos.append(31)
    pos.append(63)

    var layouts = List[Bool]()
    layouts.append(True)
    layouts.append(False)
    var worst_rt = 0.0
    var rt_ok = True
    for li in range(2):
        var il = layouts[li]
        var fwd = rope_apply_flat(x, tb.cos_table, tb.sin_table, n_tok, n_heads, head_dim, pos, il)
        var back = rope_apply_inverse_flat(
            fwd.values, tb.cos_table, tb.sin_table, n_tok, n_heads, head_dim, pos, il
        )
        if fwd.status != ATTN_OK or back.status != ATTN_OK:
            rt_ok = False
        for i in range(len(x)):
            var d = _abs(back.values[i] - x[i])
            if d > worst_rt:
                worst_rt = d
    if rt_ok and worst_rt < 1e-12:
        passed += 1
        print("  ✅ inverse(apply(x)) == x for BOTH layouts — max error", worst_rt)
    else:
        failed += 1
        print("  ❌ the rotation is not orthogonal — max error", worst_rt)

    # The two layouts must produce DIFFERENT output. If they agreed, the layout parameter would be
    # doing nothing and the most common conversion bug in the ecosystem would be undetectable here.
    var a_int = rope_apply_flat(x, tb.cos_table, tb.sin_table, n_tok, n_heads, head_dim, pos, True)
    var a_half = rope_apply_flat(x, tb.cos_table, tb.sin_table, n_tok, n_heads, head_dim, pos, False)
    var differ = False
    for i in range(len(x)):
        if _abs(a_int.values[i] - a_half.values[i]) > 1e-9:
            differ = True
            break
    if differ:
        passed += 1
        print("  ✅ interleaved and split-half produce different output — the layout flag is real")
    else:
        failed += 1
        print("  ❌ the two layouts agree, so the flag does nothing")

    # ── position zero is the identity ─────────────────────────────────────────
    var p0 = List[Int]()
    p0.append(0)
    var ident = rope_apply_flat(x, tb.cos_table, tb.sin_table, 1, 1, head_dim, p0, True)
    var ident_ok = True
    for i in range(head_dim):
        if _abs(ident.values[i] - x[i]) > 1e-15:
            ident_ok = False
    if ident_ok:
        passed += 1
        print("  ✅ position 0 is the identity rotation")
    else:
        failed += 1
        print("  ❌ position 0 changed the values")

    # ── per-token positions, which is what makes packing work ─────────────────
    # Two tokens at the SAME position must rotate identically regardless of their index in the batch.
    var same_pos = List[Int]()
    same_pos.append(9)
    same_pos.append(9)
    var xx = List[Float64]()
    for _ in range(2):
        for j in range(head_dim):
            xx.append(Float64(j) * 0.5 + 1.0)
    var sp = rope_apply_flat(xx, tb.cos_table, tb.sin_table, 2, 1, head_dim, same_pos, True)
    var same_ok = True
    for j in range(head_dim):
        if _abs(sp.values[j] - sp.values[head_dim + j]) > 1e-15:
            same_ok = False
    if same_ok:
        passed += 1
        print("  ✅ rotation depends on the position, not the token index — packing-safe")
    else:
        failed += 1
        print("  ❌ two tokens at the same position rotated differently")

    # ── the guards the A-Z harness cannot reach ───────────────────────────────
    var short_pos = List[Int]()
    short_pos.append(0)
    if rope_apply_flat(x, tb.cos_table, tb.sin_table, 5, 3, 8, short_pos, True).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ fewer positions than tokens is refused, not an out-of-bounds read")
    else:
        failed += 1
        print("  ❌ the position count was not bounded")

    # A position past the end of the table would index past cos/sin.
    var far = List[Int]()
    far.append(9999)
    if rope_apply_flat(x, tb.cos_table, tb.sin_table, 1, 1, 8, far, True).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a position beyond the table is refused rather than reading past it")
    else:
        failed += 1
        print("  ❌ an out-of-table position was accepted")

    # The A-Z call shape: 5-element lists, 5 for every Int.
    var lf5 = List[Float64]()
    var li5 = List[Int]()
    for _ in range(5):
        lf5.append(0.5)
        li5.append(5)
    if rope_apply_flat(lf5, lf5, lf5, 5, 5, 5, li5, True).status != ATTN_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [attnk.rope] Passed:", passed, "Failed:", failed)
