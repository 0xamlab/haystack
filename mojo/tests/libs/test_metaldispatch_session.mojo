"""test_metaldispatch_session.mojo — the batched-shim decode session, and the two ways it is
allowed to say no.

Hand-written, mirroring `test_residentk_session.mojo`'s own structure and the same three
legitimate states:

| build flag | accelerator | shim linked | expected |
|---|---|---|---|
| unset | either | no | `metaldispatch_shader_toolchain_absent`, binary still built and linked |
| set | absent | yes | `metaldispatch_no_device` |
| set | present | yes | a whole small transformer's greedy token, matching the frozen CPU kernels |

The first row protects CI exactly as `residentk`'s own default-build row does: `_MBQwen3.__init__`
is never ELABORATED unless something calls it, and its only call site in this file is behind
`@parameter if MB_GPU_BUILD` — so a build without `-D ALGENTA_GPU` needs `batch_shim.o` linked in
AT ALL (every `external_call` this package makes lives inside that constructor or the `step()`
method it enables, both dead code on this path). That is what lets this suite build in the
DEFAULT configuration with no linker flags, which is the shape `tests/generate_mojo_tests.py`'s
ordinary run exercises.

THE GOLDEN VECTOR IS THE SAME SMALL MODEL `residentk`'s OWN SUITE USES, THROUGH A DIFFERENT PATH
====================================================================================================
This is deliberate, not laziness: the point of this suite is NOT to re-litigate whether the
kernels' arithmetic is right (that question is `residentk.kernels`' own — unmodified, imported
directly, never rewritten here). It is to catch every mistake THIS package's own new code could
make that `residentk`'s suite cannot see: a pipeline resolved to the wrong role by
`_classify_pipeline`, a descriptor's argument bound at the wrong slot or with the wrong tag, a
grid/threadgroup size that drifted from what the kernel expects, or a `pos`/`n_keys` patch written
to the wrong descriptor. Any of those changes the token, exactly as a launch-site mistake would in
`residentk.session` — the frozen kernels are the same, so a divergence here indicts THIS package.

Build and run all three ways (manual — like `residentk`'s own suite, this is not wired into
`make test-gpu-kernels`, which is scoped to two CI-relevant files; see that target's own comment):

    # default build, no shim needed
    pixi run mojo run -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session.mojo

    # GPU build, needs the shim linked
    clang -c -fobjc-arc -O2 benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=<Xcode>/Contents/Developer pixi run mojo run -D ALGENTA_GPU \\
      -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session.mojo \\
      -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation

    # no-accelerator target, still needs the shim to LINK even though it never opens
    pixi run mojo run -D ALGENTA_GPU --target-accelerator=none -I <worktree>/mojo/engine \\
      mojo/tests/libs/test_metaldispatch_session.mojo \\
      -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation
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
from residentk.contract import RESIDENT_MAX_CONTEXT
from metaldispatch.contract import (
    MB_ERR_CONTEXT_FULL,
    MB_ERR_NO_DEVICE,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_OK,
    metaldispatch_dispatch_budget,
    metaldispatch_status_name,
)
from metaldispatch.session import MB_GPU_BUILD, _MBQwen3, _mb_preflight

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


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo(n: Int, seed: Int, amp: Float64) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var a = Float64((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float64((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _gains(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(0.8 + Float64((i * 17 + seed * 5) % 11) / 25.0)
    return o^


def _row(table: List[Float64], row: Int, width: Int) -> List[Float64]:
    var o = List[Float64](capacity=width)
    for i in range(width):
        o.append(table[row * width + i])
    return o^


def _add(a: List[Float64], b: List[Float64]) -> List[Float64]:
    var o = List[Float64](capacity=len(a))
    for i in range(len(a)):
        o.append(a[i] + b[i])
    return o^


@fieldwise_init
struct _Ref(Copyable, Movable):
    var token_id: Int
    var logit: Float64
    var ok: Bool


def _cpu_reference(
    embed: List[Float64], final_norm: List[Float64],
    ln1: List[List[Float64]], ln2: List[List[Float64]],
    qn: List[List[Float64]], kn: List[List[Float64]],
    wq: List[List[Float64]], wk: List[List[Float64]], wv: List[List[Float64]],
    wo: List[List[Float64]], wg: List[List[Float64]], wu: List[List[Float64]],
    wd: List[List[Float64]],
    prompt: List[Int], scale: Float64,
) raises -> _Ref:
    """Identical composition to `test_residentk_session.mojo`'s own `_cpu_reference` — same frozen
    kernels, same call shapes (rule 3: not duplicated logic, the same independent judge)."""
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
    if metaldispatch_dispatch_budget(28) == 171:
        passed += 1
        print("  ✅ 28 layers budget 171 dispatches, agreeing with residentk's own arithmetic")
    else:
        failed += 1
        print("  ❌ the dispatch budget drifted:", metaldispatch_dispatch_budget(28))

    if metaldispatch_status_name(MB_OK) == String("metaldispatch_ok") \
       and metaldispatch_status_name(99999) == String("metaldispatch_code_out_of_range"):
        passed += 1
        print("  ✅ the status vocabulary names what it knows and refuses what it does not")
    else:
        failed += 1
        print("  ❌ the status vocabulary is wrong")

    var scale = 1.0 / sqrt(Float64(D_HEAD))
    var pre = _mb_preflight(
        D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, 4, 1, MAX_CTX, EPS, scale
    )

    # ══ the build-flag contract ══════════════════════════════════════════════
    @parameter
    if not MB_GPU_BUILD:
        # THE DEFAULT BUILD — no linker object needed at all, because `_MBQwen3.__init__` (the only
        # place this package's `external_call`s live) is never elaborated when nothing calls it.
        if pre == MB_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: preflight reports", metaldispatch_status_name(pre))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", pre)
        print("  [metaldispatch.session] Passed:", passed, "Failed:", failed)
    else:
        # ══ built WITH GPU kernels, from here — needs batch_shim.o linked ═══════
        if not has_accelerator():
            if pre == MB_ERR_NO_DEVICE:
                passed += 1
                print("  ✅ GPU build, no accelerator:", metaldispatch_status_name(pre))
            else:
                failed += 1
                print("  ❌ wrong status on a device-less host:", pre)
            print("  [metaldispatch.session] Passed:", passed, "Failed:", failed)
            return

        if pre == MB_OK:
            passed += 1
            print("  ✅ GPU build on a GPU host: a batched-shim session is possible")
        else:
            failed += 1
            print("  ❌ preflight refused on a host that should support a session:", pre)

        # ══ the golden vector: the same small model, GPU-via-shim vs frozen CPU kernels ══
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

        var s = _MBQwen3(
            D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, EPS, scale
        )
        var rt = rope_table(D_HEAD, MAX_CTX, THETA)
        var up = s.upload_globals(embed, final_norm, rt.cos_table, rt.sin_table, MAX_CTX)
        for l in range(N_LAYERS):
            if up == MB_OK:
                up = s.upload_layer(
                    l, ln1[l], ln2[l], qn[l], kn[l], wq[l], wk[l], wv[l], wo[l], wg[l], wu[l], wd[l]
                )
        if up == MB_OK:
            up = s.seal()
        if up == MB_OK:
            passed += 1
            print("  ✅ every weight converted to Float32 and uploaded once, via the shim's own buffers")
        else:
            failed += 1
            print("  ❌ the upload failed:", metaldispatch_status_name(up))

        var gpu_id = -1
        var gpu_logit = 0.0
        var gpu_status = MB_OK
        var issued = 0
        for t in range(len(prompt)):
            var r = s.step(prompt[t], t)
            gpu_status = r.status
            gpu_id = r.token_id
            gpu_logit = r.logit
            issued = r.dispatches
            if r.status != MB_OK:
                break

        if gpu_status == MB_OK:
            passed += 1
            print("  ✅ four tokens ran through the batched shim, one call per token")
        else:
            failed += 1
            print("  ❌ a step failed:", metaldispatch_status_name(gpu_status))

        if issued == metaldispatch_dispatch_budget(N_LAYERS):
            passed += 1
            print("  ✅ the session issued exactly the budgeted", issued, "dispatches per token")
        else:
            failed += 1
            print("  ❌ dispatch drift:", issued, "issued against a budget of",
                  metaldispatch_dispatch_budget(N_LAYERS))

        # THE GOLDEN ASSERTION. Not "close" — the same token, through a different dispatch path.
        if cpu_ref.ok and gpu_id == cpu_ref.token_id:
            passed += 1
            print("  ✅ the batched-shim GPU session and the Float64 frozen kernels choose the SAME",
                  "token:", gpu_id)
        else:
            failed += 1
            print("  ❌ the greedy token DIVERGES: shim", gpu_id, "cpu", cpu_ref.token_id,
                  "— a descriptor or pipeline-resolution bug, not merely imprecision")

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

        # ── refusals the session itself must make at run time ────────────────────
        var past_end = s.step(0, MAX_CTX)
        if past_end.status == MB_ERR_CONTEXT_FULL:
            passed += 1
            print("  ✅ a step past the last KV slot is refused, not written out of bounds")
        else:
            failed += 1
            print("  ❌ a step past the cache capacity was accepted — that is silent GPU corruption")

        var bad_tok = s.step(VOCAB + 7, 0)
        if bad_tok.status != MB_OK:
            passed += 1
            print("  ✅ a token id past the vocabulary is refused before the embedding gather")
        else:
            failed += 1
            print("  ❌ an out-of-range token id was gathered from the embedding table")

        print("  [metaldispatch.session] Passed:", passed, "Failed:", failed)
