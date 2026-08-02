"""test_metaldispatch_session_i8_kvf16.mojo — the batched-shim decode session's fp16-KV-cache
arm on top of int8 weights, `_MBQwen3I8KVF16`.

Hand-written, mirroring `test_metaldispatch_session_i8.mojo`'s own structure (same three legitimate
build/accelerator states, same small-model golden vector, same "token match is informational, bound
the logit instead" gate) — see that file's own docstring for the full reasoning this suite reuses,
and `residentk.kernels`' module docstring for the fp16-KV-cache axis this arm adds.

A SEPARATE FILE FROM `test_metaldispatch_session_i8.mojo` FOR THE SAME REASON THAT FILE IS SEPARATE
FROM `test_metaldispatch_session.mojo`/`test_metaldispatch_session_f16.mojo`
=====================================================================================================
`_MBQwen3I8KVF16` compiles `_qk_rope_write_kernel_kvf16`/`_sdpa_kernel_kvf16` instead of the
Float32-cache `_qk_rope_write_kernel`/`_sdpa_kernel` every other struct in this package uses for
those two roles. Compiling both a role's Float32-cache and fp16-cache pipeline into ONE binary would
collide under the truncated-Metal-AIR-name classifier exactly the way the weight-dtype twins do (see
`_MBQwen3F16`'s own docstring) — so this golden vector lives in its own file/binary, the same
discipline `qwen3_generate_batch_i8_kvf16.mojo` follows as a benchmark driver.

THIS SUITE DELIBERATELY DOES NOT ALSO INSTANTIATE `_MBQwen3I8` FOR AN IN-PROCESS BASELINE
================================================================================================
That would be the natural way to isolate fp16-cache error from int8-weight error, and it was tried
while writing this suite — but it recreates the EXACT collision the paragraph above warns about:
`_MBQwen3I8` compiles the Float32-cache `_qk_rope_write_kernel`/`_sdpa_kernel`, and having BOTH those
AND their `_kvf16` twins embedded in one binary makes `_classify_pipeline` unable to tell a role's
two candidates apart, so BOTH structs silently end up dispatching through whichever pipeline was
discovered last. Confirmed live, not hypothesized: building both in one file made the "Float32-cache"
struct's own logit come out identical to the fp16-cache struct's — a false negative that would hide
a real regression rather than catch one. See the comment at this suite's `_MBQwen3I8KVF16`
construction site below for the full account, including the throwaway single-struct probe that
confirmed `_MBQwen3I8KVF16` itself is correct in isolation. The SAFE isolated int8-weights-held-
fixed, cache-dtype-only comparison lives in `test_residentk_session.mojo` instead, where
`residentk.session`'s compiled-kernel-handles-as-typed-struct-fields design has no equivalent
runtime name-collision hazard.

Build and run all three ways (manual — not wired into `make test-gpu-kernels`):

    # default build, no shim needed
    pixi run mojo run -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session_i8_kvf16.mojo

    # GPU build, needs the shim linked
    clang -c -fobjc-arc -O2 benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=<Xcode>/Contents/Developer pixi run mojo run -D ALGENTA_GPU \\
      -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session_i8_kvf16.mojo \\
      -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation

    # no-accelerator target, still needs the shim to LINK even though it never opens
    pixi run mojo run -D ALGENTA_GPU --target-accelerator=none -I <worktree>/mojo/engine \\
      mojo/tests/libs/test_metaldispatch_session_i8_kvf16.mojo \\
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
from metaldispatch.session import MB_GPU_BUILD, _MBQwen3I8KVF16, _mb_preflight

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
    var o = List[Float64](capacity=n)
    for i in range(n):
        var a = Float64((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float64((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


fn _gains(n: Int, seed: Int) -> List[Float64]:
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
    """Identical composition to `test_metaldispatch_session_i8.mojo`'s own `_cpu_reference` — same
    frozen kernels, same call shapes, the same independent Float64 judge every one of these suites
    checks a GPU arm against (rule 3)."""
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

    # ══ the build-flag contract — same three states as test_metaldispatch_session_i8.mojo ══
    @parameter
    if not MB_GPU_BUILD:
        if pre == MB_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: preflight reports", metaldispatch_status_name(pre))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", pre)
        print("  [metaldispatch.session i8+kvf16] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            if pre == MB_ERR_NO_DEVICE:
                passed += 1
                print("  ✅ GPU build, no accelerator:", metaldispatch_status_name(pre))
            else:
                failed += 1
                print("  ❌ wrong status on a device-less host:", pre)
            print("  [metaldispatch.session i8+kvf16] Passed:", passed, "Failed:", failed)
            return

        if pre == MB_OK:
            passed += 1
            print("  ✅ GPU build on a GPU host: a batched-shim int8+kvf16 session is possible")
        else:
            failed += 1
            print("  ❌ preflight refused on a host that should support a session:", pre)

        # ══ the golden vector: the SAME small model every metaldispatch suite uses (same seeds) ══
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

        # NOT instantiated here, ON PURPOSE: `_MBQwen3I8` (the Float32-cache baseline). Building
        # BOTH `_MBQwen3I8` and `_MBQwen3I8KVF16` in one process was tried while writing this suite
        # and produces a REAL, confirmed bug — not a hypothetical one this comment is guessing at:
        # both structs' independent pipeline-discovery loops see the SAME shared embedded-metallib
        # set (both `_qk_rope_write_kernel`/`_sdpa_kernel` AND their `_kvf16` twins present at once),
        # and the truncated-Metal-AIR-name classifier `_classify_pipeline` cannot tell a role's two
        # candidates apart — exactly the collision `_MBQwen3F16`'s own module docstring documents
        # for the weight axis, confirmed here to apply identically to the cache axis. The observed
        # symptom: BOTH structs' `_ROLE_QK_ROPE`/`_ROLE_SDPA` entries silently resolved to the SAME
        # (arbitrary, last-discovered) pipeline, so the "Float32-cache" struct actually dispatched
        # through the fp16-cache kernels too, and the two arms' logits came out identical — a false
        # negative that would have hidden a real regression instead of catching one. `_MBQwen3I8KVF16`
        # verified correct in isolation (a throwaway single-struct probe reproduced the exact logit
        # `_ResidentQwen3I8KVF16`'s own golden vector in `test_residentk_session.mojo` computes for
        # this identical model/prompt: 6.361604690551758) — the bug was in combining two arms in one
        # binary, not in either arm's own kernels or descriptor plan. So THIS suite judges
        # `_MBQwen3I8KVF16` only against the frozen CPU Float64 reference, exactly like every other
        # single-arm metaldispatch suite in this package; the SAFE isolated int8-weights-held-fixed,
        # cache-dtype-only comparison against `_ResidentQwen3I8` lives in `test_residentk_session.mojo`
        # instead, where `_ResidentQwen3`/`_ResidentQwen3F16`/`_ResidentQwen3I8`/`_ResidentQwen3I8KVF16`
        # already coexist safely in one binary — `residentk.session` binds each session's compiled
        # kernel handles as TYPED struct fields at compile time, never by a runtime name lookup, so
        # this exact collision cannot occur there.
        var s8k = _MBQwen3I8KVF16(
            D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, EPS, scale
        )
        var rt = rope_table(D_HEAD, MAX_CTX, THETA)
        var up = s8k.upload_globals(embed, final_norm, rt.cos_table, rt.sin_table, MAX_CTX)
        for l in range(N_LAYERS):
            if up == MB_OK:
                up = s8k.upload_layer(
                    l, ln1[l], ln2[l], qn[l], kn[l], wq[l], wk[l], wv[l], wo[l], wg[l], wu[l], wd[l]
                )
        if up == MB_OK:
            up = s8k.seal()
        if up == MB_OK:
            passed += 1
            print("  ✅ every weight per-row-quantized to Int8, KV cache allocated Float16, via the",
                  "shim's own buffers")
        else:
            failed += 1
            print("  ❌ the int8+kvf16 upload failed:", metaldispatch_status_name(up))

        var gpu_id = -1
        var gpu_logit = 0.0
        var gpu_status = MB_OK
        var issued = 0
        for t in range(len(prompt)):
            var r = s8k.step(prompt[t], t)
            gpu_status = r.status
            gpu_id = r.token_id
            gpu_logit = r.logit
            issued = r.dispatches
            if r.status != MB_OK:
                break

        if gpu_status == MB_OK:
            passed += 1
            print("  ✅ four tokens ran through the batched shim's int8+kvf16 arm, one call per token")
        else:
            failed += 1
            print("  ❌ an int8+kvf16 step failed:", metaldispatch_status_name(gpu_status))

        if issued == metaldispatch_dispatch_budget(N_LAYERS):
            passed += 1
            print("  ✅ the int8+kvf16 session issued exactly the budgeted", issued, "dispatches per token")
        else:
            failed += 1
            print("  ❌ int8+kvf16 dispatch drift:", issued, "issued against a budget of",
                  metaldispatch_dispatch_budget(N_LAYERS))

        # THE LOGIT BOUND, judged against the Float64 CPU reference (int8 weight-quantization error
        # AND fp16-cache-storage error both included — the SAFE isolated cache-only comparison
        # against the Float32-cache arm lives in `test_residentk_session.mojo`, see the note
        # above). Scaled by BOTH the GEMV-style `depth` term the plain int8 suite's own bound uses
        # (weight-quantization error, accumulated through `depth` Float32 additions) AND an
        # additional `N_LAYERS * D_HEAD`-scaled Float16 term for the cache-narrowing error on top —
        # deliberately looser than either arm's own bound alone, since this arm carries both.
        var delta_i8kvf16 = _abs(gpu_logit - cpu_ref.logit)
        print("  •  int8+kvf16 vs the Float64 CPU reference: logit delta", delta_i8kvf16,
              "( int8+kvf16=", gpu_logit, " cpu_f64=", cpu_ref.logit, ")")

        var i8_eps = 1.0 / 127.0
        var depth = Float64(N_LAYERS * (D_MODEL + D_FF) + D_MODEL)
        var f16_eps = 9.765625e-4
        var combined_bound = (
            i8_eps * depth + f16_eps * Float64(N_LAYERS * D_HEAD)
        ) * (1.0 + _abs(cpu_ref.logit))
        if delta_i8kvf16 <= combined_bound:
            passed += 1
            print("  ✅ the int8+kvf16 logit agrees with the Float64 reference to", delta_i8kvf16,
                  "within a combined int8+Float16 bound of", combined_bound)
        else:
            failed += 1
            print("  ❌ the int8+kvf16 logit is outside even the loose combined bound:",
                  delta_i8kvf16, "bound", combined_bound)

        # NOT asserted as a pass/fail gate — same reasoning every sibling suite's own precision arm
        # uses: fp16 rounding of the cache, applied every step, can flip a close-margin argmax
        # without that being a bug in these kernels.
        if gpu_id == cpu_ref.token_id:
            print("  •  int8+kvf16 greedy token MATCHES the Float64 reference on this small model:", gpu_id)
        else:
            print("  •  int8+kvf16 greedy token DIVERGES on this small model: int8+kvf16", gpu_id,
                  "vs cpu", cpu_ref.token_id, "— informational, not a failure; see module docs")

        # ── refusals the session itself must make at run time ────────────────────
        var past_end = s8k.step(0, MAX_CTX)
        if past_end.status == MB_ERR_CONTEXT_FULL:
            passed += 1
            print("  ✅ a step past the last KV slot is refused, not written out of bounds")
        else:
            failed += 1
            print("  ❌ a step past the cache capacity was accepted — that is silent GPU corruption")

        var bad_tok = s8k.step(VOCAB + 7, 0)
        if bad_tok.status != MB_OK:
            passed += 1
            print("  ✅ a token id past the vocabulary is refused before the embedding gather")
        else:
            failed += 1
            print("  ❌ an out-of-range token id was gathered from the embedding table")

        print("  [metaldispatch.session i8+kvf16] Passed:", passed, "Failed:", failed)
