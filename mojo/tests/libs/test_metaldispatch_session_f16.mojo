"""test_metaldispatch_session_f16.mojo — the batched-shim decode session's fp16-weight arm,
`_MBQwen3F16`.

Hand-written, mirroring `test_metaldispatch_session.mojo`'s own structure (same three legitimate
build/accelerator states, same small-model golden vector) AND `test_residentk_session.mojo`'s own
fp16-arm coverage (same Float16-epsilon-scaled bound, same "token match is informational, not a
gate" reasoning — Float16 rounding applied to every weight of even this small model can flip a
close-margin argmax without that being a bug).

A SEPARATE FILE FROM `test_metaldispatch_session.mojo` ON PURPOSE — NOT MERELY FOR TIDINESS
====================================================================================================
`_MBQwen3.__init__` (Float32) and `_MBQwen3F16.__init__` both force `compile_function_unchecked` on
their own GEMV-shaped kernels. If ONE binary called both constructors, it would embed a role's
Float32 AND Float16 pipeline together — and `metaldispatch.session`'s name-based pipeline classifier
cannot tell those two apart: Mojo's Metal AIR function name for both is truncated to an IDENTICAL
visible prefix before a per-specialization hash neither this file nor `_classify_pipeline` can
decode. See `metaldispatch.session`'s module docstring, "Why `_MBQwen3F16` is a SEPARATE binary's
struct...", for the measurement that found this. Keeping the fp16 golden vector in its own file (and
therefore its own compiled binary) is what avoids the collision — exactly the same reason
`qwen3_generate_batch_f16.mojo` is a separate benchmark driver from `qwen3_generate_batch.mojo`.

Build and run all three ways (manual — like `test_metaldispatch_session.mojo`'s own suite, this is
not wired into `make test-gpu-kernels`):

    # default build, no shim needed
    pixi run mojo run -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session_f16.mojo

    # GPU build, needs the shim linked
    clang -c -fobjc-arc -O2 benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=<Xcode>/Contents/Developer pixi run mojo run -D ALGENTA_GPU \\
      -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session_f16.mojo \\
      -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation

    # no-accelerator target, still needs the shim to LINK even though it never opens
    pixi run mojo run -D ALGENTA_GPU --target-accelerator=none -I <worktree>/mojo/engine \\
      mojo/tests/libs/test_metaldispatch_session_f16.mojo \\
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
from metaldispatch.session import MB_GPU_BUILD, _MBQwen3F16, _mb_preflight

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
    """Identical composition to `test_metaldispatch_session.mojo`'s own `_cpu_reference` (itself
    identical to `test_residentk_session.mojo`'s) — same frozen kernels, same call shapes, the same
    independent Float64 judge every one of these suites checks a GPU arm against (rule 3)."""
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

    var scale = 1.0 / sqrt(Float64(D_HEAD))
    var pre = _mb_preflight(
        D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, 4, 1, MAX_CTX, EPS, scale
    )

    # ══ the build-flag contract — same three states as test_metaldispatch_session.mojo ══
    @parameter
    if not MB_GPU_BUILD:
        if pre == MB_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: preflight reports", metaldispatch_status_name(pre))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", pre)
        print("  [metaldispatch.session f16] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            if pre == MB_ERR_NO_DEVICE:
                passed += 1
                print("  ✅ GPU build, no accelerator:", metaldispatch_status_name(pre))
            else:
                failed += 1
                print("  ❌ wrong status on a device-less host:", pre)
            print("  [metaldispatch.session f16] Passed:", passed, "Failed:", failed)
            return

        if pre == MB_OK:
            passed += 1
            print("  ✅ GPU build on a GPU host: a batched-shim fp16 session is possible")
        else:
            failed += 1
            print("  ❌ preflight refused on a host that should support a session:", pre)

        # ══ the golden vector: the SAME small model test_metaldispatch_session.mojo's Float32
        # arm uses (same seeds), through the fp16-weight arm ══
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

        var s16 = _MBQwen3F16(
            D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, EPS, scale
        )
        var rt = rope_table(D_HEAD, MAX_CTX, THETA)
        var up = s16.upload_globals(embed, final_norm, rt.cos_table, rt.sin_table, MAX_CTX)
        for l in range(N_LAYERS):
            if up == MB_OK:
                up = s16.upload_layer(
                    l, ln1[l], ln2[l], qn[l], kn[l], wq[l], wk[l], wv[l], wo[l], wg[l], wu[l], wd[l]
                )
        if up == MB_OK:
            up = s16.seal()
        if up == MB_OK:
            passed += 1
            print("  ✅ every weight narrowed to Float16 and uploaded once, via the shim's own buffers")
        else:
            failed += 1
            print("  ❌ the fp16 upload failed:", metaldispatch_status_name(up))

        var gpu_id = -1
        var gpu_logit = 0.0
        var gpu_status = MB_OK
        var issued = 0
        for t in range(len(prompt)):
            var r = s16.step(prompt[t], t)
            gpu_status = r.status
            gpu_id = r.token_id
            gpu_logit = r.logit
            issued = r.dispatches
            if r.status != MB_OK:
                break

        if gpu_status == MB_OK:
            passed += 1
            print("  ✅ four tokens ran through the batched shim's fp16 arm, one call per token")
        else:
            failed += 1
            print("  ❌ an fp16 step failed:", metaldispatch_status_name(gpu_status))

        if issued == metaldispatch_dispatch_budget(N_LAYERS):
            passed += 1
            print("  ✅ the fp16 session issued exactly the budgeted", issued, "dispatches per token")
        else:
            failed += 1
            print("  ❌ fp16 dispatch drift:", issued, "issued against a budget of",
                  metaldispatch_dispatch_budget(N_LAYERS))

        # THE FP16 LOGIT BOUND — same reasoning as test_residentk_session.mojo's own fp16 arm:
        # Float16 has ~2^-10 (9.77e-4) relative precision, three orders of magnitude looser than
        # Float32's ~2^-23, so the bound here is scaled by Float16 epsilon, not Float32's.
        var f16_eps = 9.765625e-4
        var depth = Float64(N_LAYERS * (D_MODEL + D_FF) + D_MODEL)
        var bound16 = f16_eps * depth * (1.0 + _abs(cpu_ref.logit))
        var delta16 = _abs(gpu_logit - cpu_ref.logit)
        if cpu_ref.ok and delta16 <= bound16:
            passed += 1
            print("  ✅ the fp16 logit agrees to", delta16, "within a Float16 bound of", bound16)
        else:
            failed += 1
            print("  ❌ the fp16 logit is outside even Float16 precision:", delta16, "bound", bound16)

        # NOT asserted as a pass/fail gate — see test_residentk_session.mojo's own fp16 arm for why:
        # Float16 rounding applied to every weight of even this small model can flip a close-margin
        # argmax without that being a bug in these kernels or this dispatch mechanism.
        if gpu_id == cpu_ref.token_id:
            print("  •  fp16 greedy token MATCHES the Float64 reference on this small model:", gpu_id)
        else:
            print("  •  fp16 greedy token DIVERGES on this small model: fp16", gpu_id, "vs cpu",
                  cpu_ref.token_id, "— informational, not a failure; see module docs")

        # ── refusals the session itself must make at run time ────────────────────
        var past_end = s16.step(0, MAX_CTX)
        if past_end.status == MB_ERR_CONTEXT_FULL:
            passed += 1
            print("  ✅ a step past the last KV slot is refused, not written out of bounds")
        else:
            failed += 1
            print("  ❌ a step past the cache capacity was accepted — that is silent GPU corruption")

        var bad_tok = s16.step(VOCAB + 7, 0)
        if bad_tok.status != MB_OK:
            passed += 1
            print("  ✅ a token id past the vocabulary is refused before the embedding gather")
        else:
            failed += 1
            print("  ❌ an out-of-range token id was gathered from the embedding table")

        print("  [metaldispatch.session f16] Passed:", passed, "Failed:", failed)
