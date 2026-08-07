"""test_metaldispatch_session_prefill_af.mojo — Attention Compiler Plan v1.0, Phase 2C production
wiring: `_MBQwen3I8AllSimd7Prefill.use_native_grouped_fa_attn`'s own golden vector.

Mirrors `test_metaldispatch_session_prefill.mojo`'s own structure and "frozen CPU kernels are the
independent judge" discipline (that file's own `_cpu_reference` composition restated here
independently, byte-for-byte the same calls in the same order, per this repo's no-cross-test-file-
import convention) -- but at a shape Candidate A's own kernel can actually run: `D_HEAD` here is
128, not that file's own 32 -- `attention_forge/grouped_fa_q8_k32_h2_sg8.mojo`'s own `_attn_grouped_
fa_kernel` hardcodes `_D: Int64 = 128` as a comptime constant (no runtime `d_head` argument at all),
so ANY shape exercising this kernel MUST use `d_head=128` exactly; `H_Q=2, H_KV=1` (`group=2`) is the
smallest GQA-valid pairing the kernel's own grouped-head design supports.

ONE `_MBQwen3I8AllSimd7Prefill` instance, called TWICE with the IDENTICAL prompt and `pos_base=0` --
once with `use_native_grouped_fa_attn=False` (byte-identical to today's shipping path), once with it
flipped `True` immediately after (safe: `prefill_batch` fully recomputes `hidden` from the embedding
forward every call; no state from the first call leaks into the second beyond harmless KV-cache
slots the second call's own dispatch plan overwrites at the SAME positions before anything reads
them). Compares BOTH runs against the SAME CPU Float64 oracle (`_cpu_reference`, restated) --
independent, not merely self-consistent -- and, going one step further than a same-token check
alone: reads back `s.hidden_ptr`'s row `m_rows-1` (the transformer's own final, pre-final-norm hidden
state, Float32) directly after each call and diffs the two runs' own hidden VECTORS elementwise,
which a same-argmax-token check alone could miss (two different vectors can occasionally argmax to
the same token by coincidence; a small per-element vector delta cannot).

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/candidate_a_blob.c -o /tmp/candidate_a_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/native_kv_producer_blob.c -o /tmp/native_kv_producer_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -D ALGENTA_GPU -I ../mojo/engine \
      ../mojo/tests/libs/test_metaldispatch_session_prefill_af.mojo \
      -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \
      -Xlinker /tmp/candidate_a_blob.o -Xlinker /tmp/native_kv_producer_blob.o \
      -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
      -Xlinker -framework -Xlinker IOKit
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
    MB_ERR_NO_DEVICE,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_OK,
    metaldispatch_status_name,
)
from metaldispatch.session import MB_GPU_BUILD, _mb_preflight
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill

comptime D_MODEL: Int = 64
comptime H_Q: Int = 2
comptime H_KV: Int = 1
comptime D_HEAD: Int = 128
"""MUST be 128 -- see module docstring; Candidate A's own kernel hardcodes this, no runtime arg."""
comptime D_FF: Int = 48
comptime N_LAYERS: Int = 2
comptime VOCAB: Int = 29
comptime MAX_CTX: Int = 64
comptime EPS: Float64 = 1.0e-6
comptime THETA: Float64 = 10000.0
comptime M: Int = 17
"""Deliberately NOT a multiple of `_AF_KEY_BLOCK_SIZE` (32) -- exercises the native-KV-producer's/
Candidate A's own ragged-final-block handling, not just an aligned shape."""


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
    """Restated independently from `test_metaldispatch_session_prefill.mojo`'s own `_cpu_reference`
    -- byte-for-byte the same calls in the same order, per this repo's no-cross-test-file-import
    convention -- at THIS file's own `D_HEAD=128` shape."""
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
        D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, M, 1, MAX_CTX, EPS, scale
    )

    @parameter
    if not MB_GPU_BUILD:
        if pre == MB_ERR_SHADER_TOOLCHAIN_ABSENT:
            passed += 1
            print("  ✅ built without -D ALGENTA_GPU: preflight reports", metaldispatch_status_name(pre))
        else:
            failed += 1
            print("  ❌ a GPU-less build did not report the toolchain as absent:", pre)
        print("  [metaldispatch.session_prefill_af] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            if pre == MB_ERR_NO_DEVICE:
                passed += 1
                print("  ✅ GPU build, no accelerator:", metaldispatch_status_name(pre))
            else:
                failed += 1
                print("  ❌ wrong status on a device-less host:", pre)
            print("  [metaldispatch.session_prefill_af] Passed:", passed, "Failed:", failed)
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

        var prompt = List[Int]()
        for i in range(M):
            prompt.append((i * 7 + 3) % VOCAB)

        var cpu_ref = _cpu_reference(
            embed, final_norm, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd, prompt, scale
        )
        if cpu_ref.ok:
            passed += 1
            print("  ✅ the frozen CPU kernels produced a reference token:",
                  cpu_ref.token_id, "logit", cpu_ref.logit)
        else:
            failed += 1
            print("  ❌ the frozen-kernel reference failed to run — the GPU cannot be judged")

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
        var bound = i8_eps * depth * (1.0 + _abs(cpu_ref.logit))

        # ══ Gate A: OFF path (default, byte-identical to today's shipping code) vs CPU oracle ══
        print("")
        print("  --- use_native_grouped_fa_attn = False (today's shipping path) ---")
        var af_pipelines_present = (
            s.af_pipeline_idx[0] >= 0 and s.af_pipeline_idx[1] >= 0
        )
        print("  (attention_forge blobs linked into this binary:", af_pipelines_present, ")")

        var pf_off = s.prefill_batch(prompt, 0)
        var hidden_off = List[Float64]()
        if pf_off.status == MB_OK:
            passed += 1
            print("  ✅ prefill_batch() [OFF] ran", pf_off.dispatches, "dispatches for", M, "rows")
            var hp = s.hidden_ptr.bitcast[Float32]()
            var row_off = (M - 1) * D_MODEL
            for e in range(D_MODEL):
                hidden_off.append(Float64(hp[row_off + e]))
        else:
            failed += 1
            print("  ❌ prefill_batch() [OFF] failed:", metaldispatch_status_name(pf_off.status))

        if cpu_ref.ok and pf_off.token_id == cpu_ref.token_id:
            passed += 1
            print("  ✅ [OFF] prefill_batch() and the Float64 frozen kernels choose the SAME token:",
                  pf_off.token_id)
        else:
            failed += 1
            print("  ❌ [OFF] token DIVERGES: gpu", pf_off.token_id, "cpu", cpu_ref.token_id)

        var delta_off = _abs(pf_off.logit - cpu_ref.logit)
        if cpu_ref.ok and delta_off <= bound:
            passed += 1
            print("  ✅ [OFF] logit agrees to", delta_off, "within the int8 bound of", bound)
        else:
            failed += 1
            print("  ❌ [OFF] logit diverges:", delta_off, "bound", bound)

        # ══ Gate B: ON path (Candidate A + native-KV-producer) vs the SAME CPU oracle ══════════
        print("")
        print("  --- use_native_grouped_fa_attn = True (Attention Compiler Plan v1.0, Phase 2C) ---")
        if not af_pipelines_present:
            print("  ⚠️  attention_forge blobs not linked into this binary -- ON-path gates SKIPPED.")
            print("      Rebuild with candidate_a_blob.o + native_kv_producer_blob.o linked (see")
            print("      this file's own module docstring) to actually exercise Gate B.")
        else:
            s.use_native_grouped_fa_attn = True
            var pf_on = s.prefill_batch(prompt, 0)
            var hidden_on = List[Float64]()
            if pf_on.status == MB_OK:
                passed += 1
                print("  ✅ prefill_batch() [ON] ran", pf_on.dispatches, "dispatches for", M, "rows")
                var hp2 = s.hidden_ptr.bitcast[Float32]()
                var row_on = (M - 1) * D_MODEL
                for e in range(D_MODEL):
                    hidden_on.append(Float64(hp2[row_on + e]))
            else:
                failed += 1
                print("  ❌ prefill_batch() [ON] failed:", metaldispatch_status_name(pf_on.status))

            if pf_on.dispatches == 1 + N_LAYERS * 8 + 2:
                passed += 1
                print("  ✅ [ON] dispatch count matches the AF design budget (1 + n_layers*8 + 2)")
            else:
                failed += 1
                print("  ❌ [ON] dispatch count drifted:", pf_on.dispatches, "expected",
                      1 + N_LAYERS * 8 + 2)

            if cpu_ref.ok and pf_on.token_id == cpu_ref.token_id:
                passed += 1
                print("  ✅ [ON] prefill_batch() and the Float64 frozen kernels choose the SAME token:",
                      pf_on.token_id)
            else:
                failed += 1
                print("  ❌ [ON] token DIVERGES: gpu", pf_on.token_id, "cpu", cpu_ref.token_id)

            # F16-narrowed Q/K/V + a genuinely different kernel schedule earns a looser bound than
            # the int8-quantization-only bound above -- not the SAME tolerance, a wider, itemized one
            # (F16 has ~3 decimal digits of precision; this is in ADDITION to the existing int8 error
            # already budgeted above, not a replacement of it).
            var f16_eps = 1.0 / 1024.0
            var bound_on = (i8_eps + f16_eps) * depth * (1.0 + _abs(cpu_ref.logit))
            var delta_on = _abs(pf_on.logit - cpu_ref.logit)
            if cpu_ref.ok and delta_on <= bound_on:
                passed += 1
                print("  ✅ [ON] logit agrees to", delta_on, "within the int8+f16 bound of", bound_on)
            else:
                failed += 1
                print("  ❌ [ON] logit diverges:", delta_on, "bound", bound_on)

            # ── the direct, non-discretized check: elementwise hidden-vector delta between the
            # two GPU paths themselves (not vs. the CPU oracle) -- a same-token/close-logit result
            # could theoretically still hide a larger per-element divergence that happens not to
            # flip the argmax; this does not.
            if len(hidden_off) == D_MODEL and len(hidden_on) == D_MODEL:
                var worst = 0.0
                var worst_idx = -1
                for e in range(D_MODEL):
                    var d = _abs(hidden_off[e] - hidden_on[e])
                    if d > worst:
                        worst = d
                        worst_idx = e
                # Same itemized int8+f16 tolerance convention, applied per-element to hidden
                # (pre-final-norm) rather than to the post-argmax logit.
                var elem_bound = (i8_eps + f16_eps) * depth * (1.0 + _abs(hidden_off[worst_idx if worst_idx >= 0 else 0]))
                if worst <= elem_bound:
                    passed += 1
                    print("  ✅ [ON vs OFF] worst hidden-row element delta", worst, "(idx", worst_idx,
                          ") within", elem_bound)
                else:
                    failed += 1
                    print("  ❌ [ON vs OFF] worst hidden-row element delta", worst, "(idx", worst_idx,
                          ") EXCEEDS", elem_bound)

        # ── forces `step()` (and therefore `_ensure_deep_initialized`'s own `compile_function[
        # _splitk_partial_kernel_simd_native]`/`[_splitk_merge_kernel_simd]` calls) to be reachable
        # from `main()`, so the compiler actually generates and embeds those two metallibs --
        # `_MBQwen3I8AllSimd7Prefill.__init__`'s own pre-existing, unconditional requirement (see
        # that method's own `pipeline_idx_split`/`pipeline_idx_merge` check) needs them discoverable
        # regardless of whether this test ever exercises deep-context decode for real. Unlike
        # `test_metaldispatch_session_prefill.mojo` (which reaches `step()` via its own "continue
        # after prefill" gate), this file's own gates only call `prefill_batch()` -- this call exists
        # PURELY for that reachability, its return value deliberately unchecked/uncounted.
        _ = s.step(0, M)

        print("")
        print("  [metaldispatch.session_prefill_af] Passed:", passed, "Failed:", failed)
