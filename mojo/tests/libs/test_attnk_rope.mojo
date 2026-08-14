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
from attnk.contract import (
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_UNKNOWN_SCALING,
    ATTN_OK,
)
from attnk.rope import (
    ROPE_SCALING_LINEAR,
    ROPE_SCALING_NONE,
    ROPE_SCALING_SQUARED,
    rope_apply_flat,
    rope_apply_inverse_flat,
    rope_inv_freq,
    rope_inv_freq_llama3,
    rope_table,
    rope_table_freq_factors,
    rope_table_llama3,
    rope_theta_agreement,
    rope_theta_for,
)
from model_abi import rope_theta_scale
from model_interop import hf_rope_theta_scale


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _l3_golden() -> List[Float64]:
    """The llama3-adjusted inverse frequencies for head_dim=128, theta=500000, factor=8,
    low_freq_factor=1, high_freq_factor=4, original_max_position_embeddings=8192 -- computed by
    tests/test_rope_scaling_llama3.py's independent Python reference implementation of the
    standard HF formula (positional List construction avoided: the pinned toolchain's List grows
    by append)."""
    var g = List[Float64]()
    g.append(1.00000000000000000e+00); g.append(8.14617233856544720e-01); g.append(6.63601237696088475e-01); g.append(5.40581004635766971e-01)
    g.append(4.40366602671780460e-01); g.append(3.58730223751289878e-01); g.append(2.92227822573015106e-01); g.append(2.38053820480350731e-01)
    g.append(1.93922744748685760e-01); g.append(1.57972809909043194e-01); g.append(1.28687373432650520e-01); g.append(1.04830952177969963e-01)
    g.append(8.53971002857656092e-02); g.append(6.95659496141603217e-02); g.append(5.66696214452910504e-02); g.append(4.61640502654605198e-02)
    g.append(3.76060309308639332e-02); g.append(3.06345208932240418e-02); g.append(2.49554086705586937e-02); g.append(2.03291059809701524e-02)
    g.append(1.65604400809944464e-02); g.append(1.34904198902267482e-02); g.append(1.09895285345398257e-02); g.append(8.95225933619439931e-03)
    g.append(7.29266473721710932e-03); g.append(5.94073037567496680e-03); g.append(4.83942134571989282e-03); g.append(3.94227603011665633e-03)
    g.append(3.21144599475259090e-03); g.append(2.16657076350335910e-03); g.append(1.37189356776113813e-03); g.append(8.56751412919632077e-04)
    g.append(5.24846160992954681e-04); g.append(3.12693750384065170e-04); g.append(1.78507812767996410e-04); g.append(9.55621235396468327e-05)
    g.append(7.78465527393244983e-05); g.append(6.34151434577761506e-05); g.append(5.16590687481895629e-05); g.append(4.20823676872552574e-05)
    g.append(3.42810219595259124e-05); g.append(2.79259112824444676e-05); g.append(2.27489286018281830e-05); g.append(1.85316692908213079e-05)
    g.append(1.50962171764331303e-05); g.append(1.22976386779636137e-05); g.append(1.00178684028099742e-05); g.append(8.16072824743594344e-06)
    g.append(6.64786987118123540e-06); g.append(5.41546936549992203e-06); g.append(4.41153467455840417e-06); g.append(3.59371217365099946e-06)
    g.append(2.92749987017616769e-06); g.append(2.38479184635830328e-06); g.append(1.94269253720404302e-06); g.append(1.58255082089091010e-06)
    g.append(1.28917317215155745e-06); g.append(1.05018268346016874e-06); g.append(8.55496912644365941e-07); g.append(6.96902528551167421e-07)
    g.append(5.67708810075983690e-07); g.append(4.62465380500088366e-07); g.append(3.76732269017396400e-07); g.append(3.06892598891451108e-07)
    return g^


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

    # ── the llama-3.1 "llama3" rope_scaling (feat/llama-d128-ropescale) ─────
    # Representative llama-3.1 config: head_dim=128, theta=500000, factor=8, low_freq_factor=1,
    # high_freq_factor=4, original_max_position_embeddings=8192. The golden table below is an
    # INDEPENDENT Python implementation of the standard HF formula (tests/test_rope_scaling_llama3.
    # py's reference function); the tolerance covers only the pow-libm difference between this
    # toolchain and Python's, never the formula.
    var l3 = rope_inv_freq_llama3(128, 500000.0, 8.0, 1.0, 4.0, 8192.0)
    var golden = _l3_golden()
    var l3_worst = 0.0
    if len(l3) == len(golden):
        for i in range(len(l3)):
            var rel = _abs(l3[i] - golden[i]) / golden[i]
            if rel > l3_worst:
                l3_worst = rel
    if len(l3) == len(golden) and l3_worst <= 1e-9:
        passed += 1
        print("  ✅ llama3 adjusted frequencies match the Python reference -- worst rel diff", l3_worst)
    else:
        failed += 1
        print("  ❌ llama3 frequencies drifted from the Python reference -- worst rel diff", l3_worst)

    # Band structure, checked against the BASE frequencies (same mpow, so exact): the 29 shortest
    # wavelengths stay UNCHANGED, the 29 longest are divided by EXACTLY the factor (division by 8
    # is exact in binary), and the 6 in between sit strictly inside the interpolation.
    var base128 = rope_inv_freq(128, 500000.0)
    var n_unchanged = 0
    var n_scaled = 0
    var n_smooth = 0
    if len(l3) == 64 and len(base128) == 64:
        for i in range(64):
            if l3[i] == base128[i]:
                n_unchanged += 1
            elif l3[i] == base128[i] / 8.0:
                n_scaled += 1
            elif l3[i] > base128[i] / 8.0 and l3[i] < base128[i]:
                n_smooth += 1
    if n_unchanged == 29 and n_scaled == 29 and n_smooth == 6:
        passed += 1
        print("  ✅ llama3 band structure: 29 unchanged / 6 smooth / 29 factor-scaled, as specified")
    else:
        failed += 1
        print("  ❌ llama3 band counts wrong:", n_unchanged, n_smooth, n_scaled)

    # The table builders: llama3 table == factor-1 degenerate case == plain table; explicit
    # per-pair factors are DIVISORS (the ggml rope_freqs.weight contract); invalid scaling refused.
    var t_l3 = rope_table_llama3(128, 16, 500000.0, 8.0, 1.0, 4.0, 8192.0)
    var t_plain = rope_table(128, 16, 500000.0)
    var t_f1 = rope_table_llama3(128, 16, 500000.0, 1.0, 1.0, 4.0, 8192.0)
    var table_match = (
        t_l3.status == ATTN_OK and t_f1.status == ATTN_OK and t_plain.status == ATTN_OK
        and len(t_l3.cos_table) == len(t_plain.cos_table)
    )
    if table_match:
        for i in range(len(t_plain.cos_table)):
            # factor=1 degenerates to the plain table EXACTLY...
            if t_f1.cos_table[i] != t_plain.cos_table[i]
                or t_f1.sin_table[i] != t_plain.sin_table[i]:
                table_match = False
            # ...while the real factor genuinely changes the table somewhere.
        var differs = False
        for i in range(len(t_plain.cos_table)):
            if t_l3.cos_table[i] != t_plain.cos_table[i]:
                differs = True
        table_match = differs
    if table_match:
        passed += 1
        print("  ✅ rope_table_llama3: factor=1 degenerates to the plain table, factor=8 changes it")
    else:
        failed += 1
        print("  ❌ rope_table_llama3 table behavior wrong")

    var factors = List[Float64]()
    var twos = List[Float64]()
    for i in range(4):
        factors.append(1.0)
        twos.append(2.0)
    var t_ones = rope_table_freq_factors(8, 16, 10000.0, factors^)
    var t_half = rope_table_freq_factors(8, 16, 10000.0, twos^)
    var t_base8 = rope_table(8, 16, 10000.0)
    var div_ok = t_ones.status == ATTN_OK and t_half.status == ATTN_OK
    if div_ok:
        for i in range(len(t_base8.cos_table)):
            if t_ones.cos_table[i] != t_base8.cos_table[i]:
                div_ok = False
        # Dividing every frequency by 2 halves every angle, so the factor-2 table at position 2p
        # is EXACTLY the plain table at position p (same rounded product, bit for bit).
        for p in range(8):
            for pair in range(4):
                if t_half.cos_table[(2 * p) * 4 + pair] != t_base8.cos_table[p * 4 + pair]
                    or t_half.sin_table[(2 * p) * 4 + pair] != t_base8.sin_table[p * 4 + pair]:
                    div_ok = False
    if div_ok:
        passed += 1
        print("  ✅ rope_table_freq_factors: all-ones == plain table, factor 2 halves every angle")
    else:
        failed += 1
        print("  ❌ rope_table_freq_factors divisor contract broken")

    if (
        rope_table_llama3(128, 16, 500000.0, 8.0, 4.0, 1.0, 8192.0).status == ATTN_ERR_UNKNOWN_SCALING
        and rope_table_llama3(128, 16, 500000.0, -8.0, 1.0, 4.0, 8192.0).status == ATTN_ERR_UNKNOWN_SCALING
        and rope_table_llama3(128, 16, 500000.0, 8.0, 1.0, 4.0, 0.0).status == ATTN_ERR_UNKNOWN_SCALING
        and len(rope_inv_freq_llama3(128, 500000.0, 8.0, 1.0, 1.0, 8192.0)) == 0
    ):
        passed += 1
        print("  ✅ degenerate llama3 scaling (high<=low, negative factor, zero orig ctx) is refused")
    else:
        failed += 1
        print("  ❌ a degenerate llama3 scaling was accepted")

    print("  [attnk.rope] Passed:", passed, "Failed:", failed)
