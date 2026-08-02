"""test_residentk_session.mojo — the resident GPU decode session, and the two ways it is allowed
to say no.

Hand-written. Runs on EVERY host and adapts, because this module has three legitimate states and
all three need testing:

| build flag | accelerator | expected |
|---|---|---|
| unset | either | `resident_shader_toolchain_absent`, and the binary still built and linked |
| set | absent | `resident_no_accelerator_present` |
| set | present | a whole small transformer's greedy token, matching the frozen CPU kernels |

The first row is the one that protects CI. `-D ALGENTA_GPU` is not set by default, so the
assertions below run in the DEFAULT build too — and there they assert that every kernel is compiled
out and that the package says so, which is precisely the property that lets a Linux runner with no
Metal compiler build `residentk` at all. That row is not a weaker test than the others; it is the
one that would have caught the whole-CI failure mode.

THE GOLDEN VECTOR IS A WHOLE MODEL, NOT A KERNEL
===================================================
`residentk.session` holds its compiled kernel handles as struct fields, which on this toolchain is
only possible through `compile_function_unchecked` — the checked form's return type is
parameterised on a packed argument list with no writable surface syntax. `_unchecked` means the
argument types at a launch site are NOT verified by the compiler: a swapped pointer, a transposed
dimension or an `eps` where a `scale` belongs all compile cleanly and produce wrong numbers.

So the test that matters is not "does a kernel run". It is: build a small but COMPLETE decoder — two
layers, grouped-query attention with a real group size, RoPE, SwiGLU, a tied lm_head — run one token
through the resident GPU session, and run the identical arithmetic through the frozen Float64 CPU
kernels (`normk.rmsnorm`, `attnk.rope`, `attnk.sdpa`, `gemm.blocked`, `mlpk.activation`,
`llmk.generate`), then require the SAME token id.

Every launch-site mistake the compiler cannot catch changes that token. A wrong RoPE pairing, a
q_norm applied after the rotation instead of before, `h_kv` where `h_q` belongs, gate and up
swapped in the SwiGLU, a KV slot written at the wrong position — each produces a plausible network
that answers differently.

WHY THE SHAPE IS NOT SQUARE OR POWER-OF-EVERYTHING
=====================================================
`h_q = 4` against `h_kv = 2` gives a real GQA group size of 2, so a kernel that ignored the mapping
and used `h` where `h / group` belongs is wrong rather than accidentally right. `d_ff = 40` is NOT
a multiple of the 8 output columns a threadgroup owns, so the last threadgroup runs partly out of
range and the `j < n` guards are exercised. `vocab = 23` is prime and far smaller than the 2048
threadgroups the lm_head kernel launches, so almost every threadgroup finds NO candidate — which
tests that "no candidate" loses to a real one in both argmax stages rather than winning with a
sentinel.

PRECISION: the bar is the TOKEN, not the logit
=================================================
The GPU computes in Float32 and every kernel it is checked against computes in Float64. They do not
compute the same function and asserting they agree to Float64 tolerance would always fail while
saying nothing about whether the fusion is right. The token id must match EXACTLY; the logit is
checked against a Float32 bound that scales with the accumulation depth, and the measured delta is
printed so a reader sees the real number rather than the tolerance.
"""

from std.math import sqrt
from std.sys import has_accelerator
from gemm.blocked import gemv_flat
from gemm.contract import GEMM_OK
from normk.rmsnorm import rmsnorm_fwd_flat
from normk.contract import NORM_OK
from mlpk.activation import gated_ffn_fwd_flat
from mlpk.contract import MLP_ACT_SWIGLU, MLP_OK
from attnk.rope import rope_apply_flat, rope_table
from attnk.sdpa import sdpa_forward_flat
from attnk.contract import ATTN_OK
from llmk.generate import greedy_argmax_flat
from llmk.contract import LLMK_OK
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_DIM_TOO_LARGE,
    RESIDENT_ERR_EMPTY_DIM,
    RESIDENT_ERR_HEAD_MISMATCH,
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_MAX_CONTEXT,
    RESIDENT_MAX_D_MODEL,
    RESIDENT_MAX_HEAD_DIM,
    RESIDENT_OK,
    residentk_context_check,
    residentk_dims_check,
    residentk_dispatch_budget,
    residentk_scalars_ok,
    residentk_status_name,
    residentk_weight_elems,
)
from residentk.probe import (
    RESIDENT_GPU_BUILD,
    resident_available,
    resident_gpu_kernels_compiled,
    resident_session_probe,
)
from residentk.session import _ResidentQwen3, _resident_preflight

# ── the small-but-complete model this suite decodes with ──────────────────────
comptime D_MODEL: Int = 32
comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 8
comptime D_FF: Int = 40
comptime N_LAYERS: Int = 2
comptime VOCAB: Int = 23
comptime MAX_CTX: Int = 8
comptime EPS: Float64 = 1.0e-6
comptime THETA: Float64 = 10000.0


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _pseudo(n: Int, seed: Int, amp: Float64) -> List[Float64]:
    """Deterministic small values. Two coprime multipliers so a wrong stride does not alias into a
    pattern that happens to give the same dot product."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var a = Float64((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float64((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


fn _gains(n: Int, seed: Int) -> List[Float64]:
    """Norm gains near 1.0 — a real checkpoint's are, and a gain of 0 would hide a wrong index."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(0.8 + Float64((i * 17 + seed * 5) % 11) / 25.0)
    return o^


fn _row(table: List[Float64], row: Int, width: Int) -> List[Float64]:
    var o = List[Float64](capacity=width)
    for i in range(width):
        o.append(table[row * width + i])
    return o^


fn _add(a: List[Float64], b: List[Float64]) -> List[Float64]:
    var o = List[Float64](capacity=len(a))
    for i in range(len(a)):
        o.append(a[i] + b[i])
    return o^


@fieldwise_init
struct _Ref(Copyable, Movable):
    """The frozen-kernel answer for one token: the greedy id and its Float64 logit."""

    var token_id: Int
    var logit: Float64
    var ok: Bool


fn _cpu_reference(
    embed: List[Float64], final_norm: List[Float64],
    ln1: List[List[Float64]], ln2: List[List[Float64]],
    qn: List[List[Float64]], kn: List[List[Float64]],
    wq: List[List[Float64]], wk: List[List[Float64]], wv: List[List[Float64]],
    wo: List[List[Float64]], wg: List[List[Float64]], wu: List[List[Float64]],
    wd: List[List[Float64]],
    prompt: List[Int], scale: Float64,
) raises -> _Ref:
    """The SAME model, one token at a time, entirely through frozen Float64 CPU kernels.

    Rule 3 throughout: not one line of arithmetic here is new. `rmsnorm_fwd_flat`, `rope_table`,
    `rope_apply_flat`, `sdpa_forward_flat`, `gemv_flat`, `gated_ffn_fwd_flat` and
    `greedy_argmax_flat` are all called unmodified, at the shapes they document. The value of this
    function is the composition — it is the independent implementation the GPU path is judged
    against, and reimplementing a dot product here would mean judging one new kernel with another.

    Weights arrive in the checkpoint's `[in, out]` layout, so every projection is
    `gemv_flat(..., trans=True)` — the same call `qwen3_generate.mojo` makes.
    """
    var rt = rope_table(D_HEAD, MAX_CTX, THETA)
    if rt.status != ATTN_OK:
        return _Ref(-1, 0.0, False)

    var n_kv_elems = H_KV * D_HEAD
    var cache_k = List[List[Float64]]()
    var cache_v = List[List[Float64]]()
    for _ in range(N_LAYERS):
        cache_k.append(List[Float64]())
        cache_v.append(List[Float64]())

    var last_id = -1
    var last_logit = 0.0

    for step in range(len(prompt)):
        var pos = step
        var one_pos = List[Int]()
        one_pos.append(pos)
        var hidden = _row(embed, prompt[step], D_MODEL)

        for layer in range(N_LAYERS):
            var n1 = rmsnorm_fwd_flat(hidden, ln1[layer], 1, D_MODEL, EPS)
            if n1.status != NORM_OK:
                return _Ref(-1, 0.0, False)
            var q = gemv_flat(wq[layer], n1.y, D_MODEL, H_Q * D_HEAD, True)
            var k = gemv_flat(wk[layer], n1.y, D_MODEL, H_KV * D_HEAD, True)
            var v = gemv_flat(wv[layer], n1.y, D_MODEL, H_KV * D_HEAD, True)
            if q.status != GEMM_OK or k.status != GEMM_OK or v.status != GEMM_OK:
                return _Ref(-1, 0.0, False)

            var qh = rmsnorm_fwd_flat(q.c, qn[layer], H_Q, D_HEAD, EPS)
            var kh = rmsnorm_fwd_flat(k.c, kn[layer], H_KV, D_HEAD, EPS)
            if qh.status != NORM_OK or kh.status != NORM_OK:
                return _Ref(-1, 0.0, False)

            var qr = rope_apply_flat(qh.y, rt.cos_table, rt.sin_table, 1, H_Q, D_HEAD, one_pos, False)
            var kr = rope_apply_flat(kh.y, rt.cos_table, rt.sin_table, 1, H_KV, D_HEAD, one_pos, False)
            if qr.status != ATTN_OK or kr.status != ATTN_OK:
                return _Ref(-1, 0.0, False)

            for e in range(n_kv_elems):
                cache_k[layer].append(kr.values[e])
                cache_v[layer].append(v.c[e])

            var empty = List[Float64]()
            var att = sdpa_forward_flat(
                qr.values, cache_k[layer], cache_v[layer], empty,
                1, pos + 1, H_Q, H_KV, D_HEAD, scale, False,
            )
            if att.status != ATTN_OK:
                return _Ref(-1, 0.0, False)

            var op = gemv_flat(wo[layer], att.out, H_Q * D_HEAD, D_MODEL, True)
            if op.status != GEMM_OK:
                return _Ref(-1, 0.0, False)
            hidden = _add(hidden, op.c)

            var n2 = rmsnorm_fwd_flat(hidden, ln2[layer], 1, D_MODEL, EPS)
            if n2.status != NORM_OK:
                return _Ref(-1, 0.0, False)
            var g = gemv_flat(wg[layer], n2.y, D_MODEL, D_FF, True)
            var u = gemv_flat(wu[layer], n2.y, D_MODEL, D_FF, True)
            if g.status != GEMM_OK or u.status != GEMM_OK:
                return _Ref(-1, 0.0, False)
            var act = gated_ffn_fwd_flat(u.c, g.c, 1, D_FF, MLP_ACT_SWIGLU)
            if act.status != MLP_OK:
                return _Ref(-1, 0.0, False)
            var dn = gemv_flat(wd[layer], act.y, D_FF, D_MODEL, True)
            if dn.status != GEMM_OK:
                return _Ref(-1, 0.0, False)
            hidden = _add(hidden, dn.c)

        var fin = rmsnorm_fwd_flat(hidden, final_norm, 1, D_MODEL, EPS)
        if fin.status != NORM_OK:
            return _Ref(-1, 0.0, False)
        var logits = gemv_flat(embed, fin.y, VOCAB, D_MODEL, False)
        if logits.status != GEMM_OK:
            return _Ref(-1, 0.0, False)
        var greedy = greedy_argmax_flat(logits.c, VOCAB)
        if greedy.status != LLMK_OK:
            return _Ref(-1, 0.0, False)
        last_id = greedy.token_id
        last_logit = greedy.logit

    return _Ref(last_id, last_logit, True)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ══ assertions that hold in EVERY build, on EVERY host ═══════════════════
    if residentk_dims_check(D_MODEL, H_Q, H_KV, D_HEAD, D_FF) == RESIDENT_OK:
        passed += 1
        print("  ✅ the suite's own model shape is one the session can hold")
    else:
        failed += 1
        print("  ❌ the suite's model shape is refused:",
              residentk_status_name(residentk_dims_check(D_MODEL, H_Q, H_KV, D_HEAD, D_FF)))

    if residentk_dims_check(D_MODEL, 5, 2, D_HEAD, D_FF) == RESIDENT_ERR_HEAD_MISMATCH:
        passed += 1
        print("  ✅ h_q not a multiple of h_kv is refused — GQA has no integer group size")
    else:
        failed += 1
        print("  ❌ a non-integral GQA group size was accepted")

    if residentk_dims_check(D_MODEL, H_Q, H_KV, 12, D_FF) == RESIDENT_ERR_HEAD_MISMATCH:
        passed += 1
        print("  ✅ a non-power-of-two head dim is refused — the tree reduction would drop lanes")
    else:
        failed += 1
        print("  ❌ a non-power-of-two head dim was accepted")

    if residentk_dims_check(RESIDENT_MAX_D_MODEL + 1, H_Q, H_KV, D_HEAD, D_FF) \
       == RESIDENT_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a d_model past the shared-memory staging ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized d_model was accepted — the shared allocation is fixed at compile time")

    if residentk_dims_check(D_MODEL, H_Q, H_KV, RESIDENT_MAX_HEAD_DIM * 2, D_FF) \
       == RESIDENT_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a head dim past the threadgroup ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized head dim was accepted")

    if residentk_dims_check(0, H_Q, H_KV, D_HEAD, D_FF) == RESIDENT_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an empty dimension is refused")
    else:
        failed += 1
        print("  ❌ an empty dimension was accepted")

    # The A-Z call shape: every Int becomes 5. These take only Ints, so nothing can index past an
    # end — but the answer must still be a refusal rather than a claim about a 5-head model with a
    # 5-wide head, which `d_head = 5` is not (not a power of two).
    if residentk_dims_check(5, 5, 5, 5, 5) == RESIDENT_ERR_HEAD_MISMATCH:
        passed += 1
        print("  ✅ the A-Z call shape (every Int == 5) is refused, not answered")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted:",
              residentk_status_name(residentk_dims_check(5, 5, 5, 5, 5)))

    # The real model this package was built for: 16 * 128 == 2048 != 1024, so a check that assumed
    # `h_q * d_head == d_model` would reject Qwen3-0.6B-Base itself.
    if residentk_dims_check(1024, 16, 8, 128, 3072) == RESIDENT_OK:
        passed += 1
        print("  ✅ Qwen3-0.6B-Base's shape is accepted despite h_q*d_head != d_model")
    else:
        failed += 1
        print("  ❌ the real model's shape is refused")

    if residentk_dispatch_budget(28) == 171:
        passed += 1
        print("  ✅ 28 layers budget 171 dispatches (28*6 + 3)")
    else:
        failed += 1
        print("  ❌ the dispatch budget drifted:", residentk_dispatch_budget(28))

    if residentk_dispatch_budget(0) == 0 and residentk_dispatch_budget(-3) == 0:
        passed += 1
        print("  ✅ a nonsense layer count budgets nothing rather than a negative")
    else:
        failed += 1
        print("  ❌ a bad layer count produced a budget")

    if residentk_context_check(5, 16, MAX_CTX) == RESIDENT_ERR_CONTEXT_FULL:
        passed += 1
        print("  ✅ a run longer than the fixed KV capacity is refused BEFORE the first token")
    else:
        failed += 1
        print("  ❌ an over-long run was accepted against a fixed-capacity cache")

    if residentk_context_check(5, 16, RESIDENT_MAX_CONTEXT) == RESIDENT_OK:
        passed += 1
        print("  ✅ ...and a run that fits is accepted")
    else:
        failed += 1
        print("  ❌ a run that fits was refused")

    # A wrapping `n_prompt + n_new` would compare as small and pass. The check subtracts instead.
    var huge = (1 << 62)
    if residentk_context_check(huge, huge, RESIDENT_MAX_CONTEXT) == RESIDENT_ERR_CONTEXT_FULL:
        passed += 1
        print("  ✅ a context length that would WRAP a 64-bit add is still refused")
    else:
        failed += 1
        print("  ❌ a wrapping context length slipped through")

    if not residentk_scalars_ok(0.0, 1.0) and not residentk_scalars_ok(1.0e-6, -1.0) \
       and residentk_scalars_ok(1.0e-6, 0.125):
        passed += 1
        print("  ✅ non-positive eps/scale are refused, a real pair is accepted")
    else:
        failed += 1
        print("  ❌ the scalar guard is wrong")

    var elems = residentk_weight_elems(1024, 16, 8, 128, 3072, 28, 151936)
    if elems > 600000000 and elems < 700000000:
        passed += 1
        print("  ✅ the real model is", Float64(elems * 4) / 1.0e9, "GB of resident Float32")
    else:
        failed += 1
        print("  ❌ the resident element count is implausible:", elems)

    if residentk_weight_elems(D_MODEL, H_Q, H_KV, 12, D_FF, 2, VOCAB) == 0:
        passed += 1
        print("  ✅ an unsupported shape holds nothing rather than reporting a size")
    else:
        failed += 1
        print("  ❌ an unsupported shape reported a resident size")

    if residentk_status_name(RESIDENT_OK) == String("resident_ok") \
       and residentk_status_name(4242) == String("resident_code_out_of_range"):
        passed += 1
        print("  ✅ the status vocabulary names what it knows and refuses what it does not")
    else:
        failed += 1
        print("  ❌ the status vocabulary is wrong")

    if resident_gpu_kernels_compiled() == RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ the build-flag report agrees with the compile-time constant")
    else:
        failed += 1
        print("  ❌ the build-flag report disagrees with its own constant")

    var bad_probe = resident_session_probe(D_MODEL, 5, 2, D_HEAD, D_FF, 2, VOCAB)
    if bad_probe.status == RESIDENT_ERR_HEAD_MISMATCH and not bad_probe.session_possible:
        passed += 1
        print("  ✅ the probe reports a SHAPE refusal before any host question")
    else:
        failed += 1
        print("  ❌ the probe blamed the host for a shape problem:", bad_probe.status)

    var scale = 1.0 / sqrt(Float64(D_HEAD))
    var pre = _resident_preflight(
        D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, 4, 1, MAX_CTX, EPS, scale
    )

    # ══ the build-flag contract ══════════════════════════════════════════════
    @parameter
    if not RESIDENT_GPU_BUILD:
        # THE DEFAULT BUILD — this is what runs on Linux CI, and it is a real assertion: the whole
        # package compiled, linked, and reports the absence honestly instead of crashing or
        # silently substituting a CPU path.
        if pre == RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: preflight reports", residentk_status_name(pre))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", pre)

        var p = resident_session_probe(D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB)
        if p.status == RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT and not p.kernels_compiled \
           and not p.session_possible:
            passed += 1
            print("  ✅ ...and the probe agrees, while still answering the arithmetic questions:",
                  "budget", p.dispatch_budget, "elems", p.resident_f32_elems)
        else:
            failed += 1
            print("  ❌ the probe disagrees with the preflight in a GPU-less build")

        if not resident_available():
            passed += 1
            print("  ✅ ...and resident_available() is false in a build with no kernels")
        else:
            failed += 1
            print("  ❌ available() claims a session in a build that has no kernels")

        print("  [residentk.session] Passed:", passed, "Failed:", failed)
    else:
        # ══ built WITH GPU kernels, from here ══════════════════════════════
        if not has_accelerator():
            if pre == RESIDENT_ERR_NO_DEVICE:
                passed += 1
                print("  ✅ GPU build, no accelerator:", residentk_status_name(pre))
            else:
                failed += 1
                print("  ❌ wrong status on a device-less host:", pre)
            print("  [residentk.session] Passed:", passed, "Failed:", failed)
            return

        if pre == RESIDENT_OK and resident_available():
            passed += 1
            print("  ✅ GPU build on a GPU host: a resident session is possible")
        else:
            failed += 1
            print("  ❌ preflight refused on a host that should support a session:", pre)

        # ══ the golden vector: a whole small model, GPU vs frozen CPU kernels ════
        var n_q = H_Q * D_HEAD
        var n_kv = H_KV * D_HEAD

        var embed = _pseudo(VOCAB * D_MODEL, 3, 0.35)
        var final_norm = _gains(D_MODEL, 9)
        var ln1 = List[List[Float64]]()
        var ln2 = List[List[Float64]]()
        var qn = List[List[Float64]]()
        var kn = List[List[Float64]]()
        var wq = List[List[Float64]]()
        var wk = List[List[Float64]]()
        var wv = List[List[Float64]]()
        var wo = List[List[Float64]]()
        var wg = List[List[Float64]]()
        var wu = List[List[Float64]]()
        var wd = List[List[Float64]]()
        for l in range(N_LAYERS):
            ln1.append(_gains(D_MODEL, 11 + l))
            ln2.append(_gains(D_MODEL, 23 + l))
            qn.append(_gains(D_HEAD, 31 + l))
            kn.append(_gains(D_HEAD, 41 + l))
            # `[in, out]` — the checkpoint's own layout. The session transposes on upload; the CPU
            # reference calls `gemv_flat(..., trans=True)` on it directly. If the two disagreed about
            # which axis is which, every token below would differ.
            wq.append(_pseudo(D_MODEL * n_q, 51 + l, 0.12))
            wk.append(_pseudo(D_MODEL * n_kv, 61 + l, 0.12))
            wv.append(_pseudo(D_MODEL * n_kv, 71 + l, 0.12))
            wo.append(_pseudo(n_q * D_MODEL, 81 + l, 0.10))
            wg.append(_pseudo(D_MODEL * D_FF, 91 + l, 0.11))
            wu.append(_pseudo(D_MODEL * D_FF, 101 + l, 0.11))
            wd.append(_pseudo(D_FF * D_MODEL, 111 + l, 0.09))

        var prompt = List[Int]()
        prompt.append(4)
        prompt.append(17)
        prompt.append(2)
        prompt.append(11)

        var cpu_ref = _cpu_reference(
            embed, final_norm, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd, prompt, scale
        )
        if cpu_ref.ok:
            passed += 1
            print("  ✅ the frozen CPU kernels produced a reference token:", cpu_ref.token_id,
                  "logit", cpu_ref.logit)
        else:
            failed += 1
            print("  ❌ the frozen-kernel reference failed to run — the GPU cannot be judged")

        var s = _ResidentQwen3(
            D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, EPS, scale
        )
        var rt = rope_table(D_HEAD, MAX_CTX, THETA)
        var up = s.upload_globals(embed, final_norm, rt.cos_table, rt.sin_table, MAX_CTX)
        for l in range(N_LAYERS):
            if up == RESIDENT_OK:
                up = s.upload_layer(
                    l, ln1[l], ln2[l], qn[l], kn[l], wq[l], wk[l], wv[l], wo[l], wg[l], wu[l], wd[l]
                )
        if up == RESIDENT_OK:
            up = s.seal()
        if up == RESIDENT_OK:
            passed += 1
            print("  ✅ every weight converted to Float32 and uploaded once, on", s.device_name())
        else:
            failed += 1
            print("  ❌ the upload failed:", residentk_status_name(up))

        var gpu_id = -1
        var gpu_logit = 0.0
        var gpu_status = RESIDENT_OK
        var issued = 0
        for t in range(len(prompt)):
            var r = s.step(prompt[t], t)
            gpu_status = r.status
            gpu_id = r.token_id
            gpu_logit = r.logit
            issued = r.dispatches
            if r.status != RESIDENT_OK:
                break

        if gpu_status == RESIDENT_OK:
            passed += 1
            print("  ✅ four tokens ran on the resident session, cache written in place each step")
        else:
            failed += 1
            print("  ❌ a step failed:", residentk_status_name(gpu_status))

        if issued == residentk_dispatch_budget(N_LAYERS):
            passed += 1
            print("  ✅ the session issued exactly the budgeted", issued, "dispatches per token")
        else:
            failed += 1
            print("  ❌ dispatch drift:", issued, "issued against a budget of",
                  residentk_dispatch_budget(N_LAYERS))

        # THE GOLDEN ASSERTION. Not "close" — the same token.
        if cpu_ref.ok and gpu_id == cpu_ref.token_id:
            passed += 1
            print("  ✅ the Float32 GPU session and the Float64 frozen kernels choose the SAME token:",
                  gpu_id)
        else:
            failed += 1
            print("  ❌ the greedy token DIVERGES: gpu", gpu_id, "cpu", cpu_ref.token_id,
                  "— a fused kernel is wrong, not merely imprecise")

        # ...and the logit, judged at Float32 precision with a bound that scales with how much
        # accumulation happened. `n_layers * (d_model + d_ff)` is the depth of the longest chain of
        # Float32 additions between the embedding and the logit.
        var f32_eps = 1.1920929e-7
        var depth = Float64(N_LAYERS * (D_MODEL + D_FF) + D_MODEL)
        var bound = f32_eps * depth * (1.0 + _abs(cpu_ref.logit))
        var delta = _abs(gpu_logit - cpu_ref.logit)
        if cpu_ref.ok and delta <= bound:
            passed += 1
            print("  ✅ the logit agrees to", delta, "within a Float32 bound of", bound)
        else:
            failed += 1
            print("  ❌ the logit is outside Float32 precision:", delta, "bound", bound)

        # The bound must be capable of failing, or it proves nothing. A Float64 bound is what a careless
        # reader would reach for; assert it would REJECT, so the loose bound above is a considered
        # choice rather than an unfalsifiable one.
        if delta > 1.0e-12:
            passed += 1
            print("  ✅ ...and it would FAIL a Float64 bound — the two really do compute in different",
                  "precisions, so the token match above is not a tautology")
        else:
            failed += 1
            print("  ❌ the two agree to Float64 precision, so the Float32 bound proves nothing")

        # ── refusals the session itself must make at run time ────────────────────
        var past_end = s.step(0, MAX_CTX)
        if past_end.status == RESIDENT_ERR_CONTEXT_FULL:
            passed += 1
            print("  ✅ a step past the last KV slot is refused, not written out of bounds")
        else:
            failed += 1
            print("  ❌ a step past the cache capacity was accepted — that is silent GPU corruption")

        var bad_tok = s.step(VOCAB + 7, 0)
        if bad_tok.status != RESIDENT_OK:
            passed += 1
            print("  ✅ a token id past the vocabulary is refused before the embedding gather")
        else:
            failed += 1
            print("  ❌ an out-of-range token id was gathered from the embedding table")

        print("  [residentk.session] Passed:", passed, "Failed:", failed)
