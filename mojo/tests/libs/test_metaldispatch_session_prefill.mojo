"""test_metaldispatch_session_prefill.mojo — `_MBQwen3I8AllSimd7Prefill`'s golden vector.

Hand-written, mirroring `test_metaldispatch_session.mojo`'s own structure (same three build-flag
states, same "frozen CPU kernels are the independent judge" discipline — see that file's own module
docstring for the full account this one leans on) plus `test_metaldispatch_session_i8.mojo`'s own
int8 tolerance bound (`i8_eps = 1/127`, scaled by accumulation depth). `D_HEAD` here is 32, not
those two files' own 8: `_sdpa_kernel_simd`'s SIMD-group reduction (which `_MBQwen3I8AllSimd7Prefill`
inherits from `_MBQwen3I8AllSimd7`) requires `d_head` to be a positive multiple of `WARP_SIZE` (32
on this Apple GPU target) — the CPU reference composition itself has no such constraint, only the
GPU struct under test does.

Gate 1 (full pipeline, per the implementation plan): `prefill_batch()`'s returned token/logit
diffed against the SAME frozen-CPU-kernel composition `test_metaldispatch_session.mojo` already
uses as its own oracle, run sequentially over the identical prompt prefix — zero new trust required,
since that composition already carries an established, independently-verified track record.

Gate "continue after prefill": after one `prefill_batch()` call, several ordinary `step()` calls on
the SAME struct instance are diffed against the CPU reference run over progressively longer prompt
prefixes — the claim this file's own module docstring makes ("the byte-identical `step()` then
continues from `pos = pos_base + m_rows` on the SAME instance") checked directly, not asserted.

    # GPU build, needs the shim + the mma_forge-extracted hardware-MMA blob linked (see
    # metaldispatch.session's own _PFROLE_GEMM_ASSIGN_MMA docstring for what that blob is)
    clang -c -fobjc-arc -O2 benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=<Xcode>/Contents/Developer clang -c -O2 mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=<Xcode>/Contents/Developer pixi run mojo run -D ALGENTA_GPU \\
      -I <worktree>/mojo/engine mojo/tests/libs/test_metaldispatch_session_prefill.mojo \\
      -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \\
      -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation
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
from metaldispatch.contract import (
    MB_ERR_CONTEXT_FULL,
    MB_ERR_NO_DEVICE,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_ERR_UPLOAD_LENGTH,
    MB_OK,
    metaldispatch_status_name,
)
from metaldispatch.session import MB_GPU_BUILD, _mb_preflight
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill

comptime D_MODEL: Int = 32
comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 32
comptime D_FF: Int = 40
comptime N_LAYERS: Int = 2
comptime VOCAB: Int = 23
comptime MAX_CTX: Int = 16
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
    """Identical composition to `test_metaldispatch_session.mojo`'s own `_cpu_reference` -- the
    independent judge, reused unmodified as a function shape (this file's own copy, since Mojo has
    no cross-test-file import convention here, but byte-for-byte the same calls in the same order)."""
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

    @parameter
    if not MB_GPU_BUILD:
        if pre == MB_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: preflight reports", metaldispatch_status_name(pre))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", pre)
        print("  [metaldispatch.session_prefill] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            if pre == MB_ERR_NO_DEVICE:
                passed += 1
                print("  ✅ GPU build, no accelerator:", metaldispatch_status_name(pre))
            else:
                failed += 1
                print("  ❌ wrong status on a device-less host:", pre)
            print("  [metaldispatch.session_prefill] Passed:", passed, "Failed:", failed)
            return

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

        var full_prompt = List[Int]()
        full_prompt.append(4); full_prompt.append(17); full_prompt.append(2); full_prompt.append(11)
        full_prompt.append(6); full_prompt.append(19)
        comptime M: Int = 4  # prefilled via prefill_batch(); the remaining 2 continue via step()

        var prefill_prompt = List[Int]()
        for i in range(M):
            prefill_prompt.append(full_prompt[i])
        var cpu_prefill = _cpu_reference(
            embed, final_norm, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd, prefill_prompt, scale
        )
        if cpu_prefill.ok:
            passed += 1
            print("  ✅ the frozen CPU kernels produced a prefill reference token:",
                  cpu_prefill.token_id, "logit", cpu_prefill.logit)
        else:
            failed += 1
            print("  ❌ the frozen-kernel prefill reference failed to run — the GPU cannot be judged")

        var s = _MBQwen3I8AllSimd7Prefill(
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
            print("  ✅ every weight per-row-quantized to Int8 and uploaded once, via the shim's own buffers")
        else:
            failed += 1
            print("  ❌ the upload failed:", metaldispatch_status_name(up))

        var i8_eps = 1.0 / 127.0
        var depth = Float64(N_LAYERS * (D_MODEL + D_FF) + D_MODEL)

        # ══ GATE 1: prefill_batch() vs the frozen-CPU-kernel oracle over the SAME prefix ══════
        var pf = s.prefill_batch(prefill_prompt, 0)
        if pf.status == MB_OK:
            passed += 1
            print("  ✅ prefill_batch() ran", pf.dispatches, "dispatches for", M, "rows")
        else:
            failed += 1
            print("  ❌ prefill_batch() failed:", metaldispatch_status_name(pf.status))

        if pf.dispatches == 1 + N_LAYERS * 8 + 2:
            passed += 1
            print("  ✅ prefill dispatch count matches the design budget (1 + n_layers*8 + 2 --",
                  "qkv_proj is rmsnorm+gemm_assign and swiglu is rmsnorm+gemm_swiglu, since the",
                  "weight-stationary tiled-GEMM follow-up)")
        else:
            failed += 1
            print("  ❌ prefill dispatch count drifted:", pf.dispatches, "expected",
                  1 + N_LAYERS * 8 + 2)

        if cpu_prefill.ok and pf.token_id == cpu_prefill.token_id:
            passed += 1
            print("  ✅ prefill_batch() and the Float64 frozen kernels choose the SAME token:",
                  pf.token_id)
        else:
            failed += 1
            print("  ❌ prefill token DIVERGES: gpu", pf.token_id, "cpu", cpu_prefill.token_id,
                  "— a batched-kernel or descriptor bug, not merely imprecision")

        var bound_pf = i8_eps * depth * (1.0 + _abs(cpu_prefill.logit))
        var delta_pf = _abs(pf.logit - cpu_prefill.logit)
        if cpu_prefill.ok and delta_pf <= bound_pf:
            passed += 1
            print("  ✅ prefill logit agrees to", delta_pf, "within the int8 bound of", bound_pf)
        else:
            failed += 1
            print("  ❌ prefill logit is outside the int8 bound:", delta_pf, "bound", bound_pf)

        # ══ GATE "continue after prefill": step() picks up from pos = M, teacher-forced ══════
        var continue_ok = True
        for t in range(M, len(full_prompt)):
            var r = s.step(full_prompt[t], t)
            if r.status != MB_OK:
                failed += 1
                continue_ok = False
                print("  ❌ step() after prefill failed at pos", t, ":", metaldispatch_status_name(r.status))
                break

            var prefix = List[Int]()
            for i in range(t + 1):
                prefix.append(full_prompt[i])
            var cpu_step = _cpu_reference(
                embed, final_norm, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd, prefix, scale
            )
            if not cpu_step.ok or r.token_id != cpu_step.token_id:
                failed += 1
                continue_ok = False
                print("  ❌ step() after prefill DIVERGES at pos", t, ": gpu", r.token_id,
                      "cpu", cpu_step.token_id if cpu_step.ok else -1,
                      "— the KV cache prefill_batch() wrote does not match a fully-stepped session")
                break
            var bound_t = i8_eps * depth * (1.0 + _abs(cpu_step.logit))
            var delta_t = _abs(r.logit - cpu_step.logit)
            if delta_t > bound_t:
                failed += 1
                continue_ok = False
                print("  ❌ step() after prefill logit outside int8 bound at pos", t, ":", delta_t,
                      "bound", bound_t)
                break

        if continue_ok:
            passed += 1
            print("  ✅ step() correctly continues generation from pos = M on the SAME instance",
                  "prefill_batch() populated")

        # ── refusals the new method itself must make at run time ──────────────────
        var empty_prompt = List[Int]()
        var empty_r = s.prefill_batch(empty_prompt, 0)
        if empty_r.status == MB_ERR_UPLOAD_LENGTH:
            passed += 1
            print("  ✅ an empty prompt is refused, not dispatched as zero rows")
        else:
            failed += 1
            print("  ❌ an empty prompt was not refused:", empty_r.status)

        var overflow_r = s.prefill_batch(prefill_prompt, MAX_CTX)
        if overflow_r.status == MB_ERR_CONTEXT_FULL:
            passed += 1
            print("  ✅ a prefill that would overflow max_ctx is refused, not written out of bounds")
        else:
            failed += 1
            print("  ❌ a context-overflowing prefill was accepted:", overflow_r.status)

        print("  [metaldispatch.session_prefill] Passed:", passed, "Failed:", failed)
