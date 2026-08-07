"""test_residentk_kvcache_fp16_kernel.mojo — the fp16-KV-cache kernel PAIR
(`_qk_rope_write_kernel_kvf16`/`_sdpa_kernel_kvf16`), isolated at the KERNEL level from everything
else `residentk` does.

Hand-written. `test_residentk_session.mojo` judges every precision arm at the WHOLE-SESSION level
(a full small transformer, GPU vs frozen CPU kernels) because that is the only level at which a
`compile_function` launch-site mistake — a swapped pointer, a wrong dimension — would
show up. This file exists for a DIFFERENT, narrower question that whole-session judging cannot
answer cleanly: **exactly how much error does narrowing the KV cache to Float16 introduce, on its
own, with no weight quantization, no RoPE, no normalization and no fused projection anywhere in the
picture?** Stage 1 of this package's own correctness protocol, reported here rather than folded
into the whole-model numbers `test_residentk_session.mojo`/`test_metaldispatch_session_i8_kvf16.mojo`
already report for stages 2/3.

Two kernels, tested against their own Float32-cache twins directly
-----------------------------------------------------------------------
1. **The write half** (`_qk_rope_write_kernel` vs `_qk_rope_write_kernel_kvf16`): same `qkv`/norm-
   gain/cos/sin inputs, same `pos`, dispatched at IDENTICAL grid/block shapes into two cache buffers
   that differ only in dtype (Float32 vs Float16). Read back and assert
   `ck_f16_widened[i] == Float16(ck_f32[i])` for every KV element written, EXACTLY — not a tolerance
   check. The kernels' own docstrings claim the q_norm/RoPE arithmetic is byte-identical up to the
   final store; this is that claim, checked, not merely asserted in a comment.
2. **The read half** (`_sdpa_kernel` vs `_sdpa_kernel_kvf16`): a small, fully KNOWN set of K/V
   values (deterministic, printed nowhere near a real checkpoint) is narrowed to BOTH a Float32 and
   a Float16 cache buffer holding the "same" conceptual values, then both kernels compute attention
   over `n_keys` positions with the IDENTICAL query. The output delta is the real error fp16 KV-
   cache storage introduces into attention's own softmax/weighted-sum math, isolated from every
   other moving part in the pipeline — no weight matrix, no GEMV, no rmsnorm is anywhere in this
   file's call graph.

Why the bound is scaled the way it is
-----------------------------------------
Float16 has ~2^-11 (4.8828e-4) relative precision at the mantissa's last bit. Unlike a GEMV's
`k`-deep accumulation (where `f16_eps` is scaled by an accumulation DEPTH in every other suite in
this package), each attention output element here is a convex combination (softmax weights sum to
1) of `n_keys` V values, each rounded ONCE before the weighted sum — errors partially average out
rather than accumulate depth-many times, so the bound below is `f16_eps` scaled by `n_keys` (the
number of independent roundings feeding one output element) rather than by a GEMV-style depth term,
and is checked to be capable of REJECTING a Float64-tight comparison, the same "the bound must be
able to fail" discipline every sibling suite in this package uses.
"""

from std.gpu.host import DeviceContext
from std.math import sqrt
from std.sys import has_accelerator
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _qk_rope_write_kernel,
    _qk_rope_write_kernel_kvf16,
    _sdpa_kernel,
    _sdpa_kernel_kvf16,
)

comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 8
comptime N_KEYS: Int = 5
comptime EPS: Float32 = 1.0e-6
comptime THETA: Float64 = 10000.0


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    """Deterministic, KNOWN small values — the controlled test case this file's task asked for.
    Two coprime multipliers, same discipline `test_residentk_session.mojo`'s own `_pseudo` uses at
    Float64, so a wrong stride does not alias into a pattern that happens to give the same answer."""
    var o = List[Float32](capacity=n)
    for i in range(n):
        var a = Float32((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float32((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        # THE DEFAULT BUILD — protects CI exactly as every sibling suite's own first row does: no
        # kernel is compiled in, so there is nothing to launch and nothing to test at kernel level.
        # This file's only job in this build is to compile and link cleanly.
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no fp16-KV-cache kernel compiled, nothing to run")
        print("  [residentk.kernels kvf16-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels kvf16-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # ══ 1. THE WRITE HALF: narrowing happens only at the final store ═══════════════════════
        var n_pairs = D_HEAD // 2
        var pos = 3
        var max_ctx = 8
        var rt = rope_table(D_HEAD, max_ctx, THETA)
        if rt.status != ATTN_OK:
            failed += 1
            print("  ❌ rope_table failed to build — the write-half test cannot run")
        else:
            var n_qkv_elems = (H_Q + 2 * H_KV) * D_HEAD
            var qkv_vals = _pseudo_f32(n_qkv_elems, 7, 0.4)
            var qn_vals = _pseudo_f32(D_HEAD, 11, 1.0)
            var kn_vals = _pseudo_f32(D_HEAD, 13, 1.0)

            var qkv_buf = ctx.enqueue_create_buffer[DType.float32](n_qkv_elems)
            var qn_buf = ctx.enqueue_create_buffer[DType.float32](D_HEAD)
            var kn_buf = ctx.enqueue_create_buffer[DType.float32](D_HEAD)
            var cos_buf = ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
            var sin_buf = ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
            with qkv_buf.map_to_host() as h:
                for i in range(n_qkv_elems):
                    h[i] = qkv_vals[i]
            with qn_buf.map_to_host() as h:
                for i in range(D_HEAD):
                    h[i] = qn_vals[i]
            with kn_buf.map_to_host() as h:
                for i in range(D_HEAD):
                    h[i] = kn_vals[i]
            with cos_buf.map_to_host() as h:
                for i in range(max_ctx * n_pairs):
                    h[i] = Float32(rt.cos_table[i])
            with sin_buf.map_to_host() as h:
                for i in range(max_ctx * n_pairs):
                    h[i] = Float32(rt.sin_table[i])

            var q_rot32 = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
            var ck32 = ctx.enqueue_create_buffer[DType.float32](max_ctx * H_KV * D_HEAD)
            var cv32 = ctx.enqueue_create_buffer[DType.float32](max_ctx * H_KV * D_HEAD)
            var q_rot16 = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
            var ck16 = ctx.enqueue_create_buffer[DType.float16](max_ctx * H_KV * D_HEAD)
            var cv16 = ctx.enqueue_create_buffer[DType.float16](max_ctx * H_KV * D_HEAD)

            var f_rope32 = ctx.compile_function[_qk_rope_write_kernel]()
            var f_rope16 = ctx.compile_function[_qk_rope_write_kernel_kvf16]()

            ctx.enqueue_function_unchecked(
                f_rope32,
                q_rot32.unsafe_ptr(), ck32.unsafe_ptr(), cv32.unsafe_ptr(), qkv_buf.unsafe_ptr(),
                qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(), cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
                pos, H_Q, H_KV, D_HEAD, EPS,
                grid_dim=H_Q + H_KV, block_dim=D_HEAD,
            )
            ctx.enqueue_function_unchecked(
                f_rope16,
                q_rot16.unsafe_ptr(), ck16.unsafe_ptr(), cv16.unsafe_ptr(), qkv_buf.unsafe_ptr(),
                qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(), cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
                pos, H_Q, H_KV, D_HEAD, EPS,
                grid_dim=H_Q + H_KV, block_dim=D_HEAD,
            )
            ctx.synchronize()

            var write_exact = True
            var qrot_exact = True
            var kv_slot = pos * H_KV * D_HEAD
            var n_kv_elems = H_KV * D_HEAD
            with ck32.map_to_host() as hck32:
                with cv32.map_to_host() as hcv32:
                    with ck16.map_to_host() as hck16:
                        with cv16.map_to_host() as hcv16:
                            for i in range(n_kv_elems):
                                var want_k = Float16(hck32[kv_slot + i])
                                var want_v = Float16(hcv32[kv_slot + i])
                                if hck16[kv_slot + i] != want_k or hcv16[kv_slot + i] != want_v:
                                    write_exact = False
            with q_rot32.map_to_host() as hq32:
                with q_rot16.map_to_host() as hq16:
                    for i in range(H_Q * D_HEAD):
                        if hq32[i] != hq16[i]:
                            qrot_exact = False

            if write_exact:
                passed += 1
                print("  ✅ the fp16-cache write kernel's stored K/V equal EXACTLY Float16(the",
                      "Float32 kernel's own K/V) — narrowing happens only at the final store")
            else:
                failed += 1
                print("  ❌ the fp16-cache write kernel's stored K/V diverge from the Float32",
                      "kernel's by more than the narrowing itself — the upstream RoPE/norm",
                      "arithmetic is NOT byte-identical between the two kernels")

            if qrot_exact:
                passed += 1
                print("  ✅ q_rot (never cached in either kernel) is bit-identical between the two",
                      "write-kernel variants — the query path is untouched by this axis")
            else:
                failed += 1
                print("  ❌ q_rot differs between the two write-kernel variants — the fp16-cache",
                      "twin touched something outside the cache write")

        # ══ 2. THE READ HALF: a controlled, known K/V set, isolated from everything upstream ════
        var q_vals = _pseudo_f32(H_Q * D_HEAD, 21, 1.0)
        var kv_vals = _pseudo_f32(N_KEYS * H_KV * D_HEAD, 31, 0.8)

        var qr_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
        with qr_buf.map_to_host() as h:
            for i in range(H_Q * D_HEAD):
                h[i] = q_vals[i]

        var ck32r = ctx.enqueue_create_buffer[DType.float32](N_KEYS * H_KV * D_HEAD)
        var cv32r = ctx.enqueue_create_buffer[DType.float32](N_KEYS * H_KV * D_HEAD)
        var ck16r = ctx.enqueue_create_buffer[DType.float16](N_KEYS * H_KV * D_HEAD)
        var cv16r = ctx.enqueue_create_buffer[DType.float16](N_KEYS * H_KV * D_HEAD)
        with ck32r.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = kv_vals[i]
        with cv32r.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                # A distinct deterministic set for V, so a K/V swap in either kernel would not
                # accidentally cancel out.
                h[i] = kv_vals[(i + 17) % len(kv_vals)]
        with ck16r.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = Float16(kv_vals[i])
        with cv16r.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = Float16(kv_vals[(i + 17) % len(kv_vals)])

        var attn32 = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
        var attn16 = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
        var scale = Float32(1.0 / sqrt(Float64(D_HEAD)))

        var f_sdpa32 = ctx.compile_function[_sdpa_kernel]()
        var f_sdpa16 = ctx.compile_function[_sdpa_kernel_kvf16]()

        ctx.enqueue_function_unchecked(
            f_sdpa32,
            attn32.unsafe_ptr(), qr_buf.unsafe_ptr(), ck32r.unsafe_ptr(), cv32r.unsafe_ptr(),
            N_KEYS, H_Q, H_KV, D_HEAD, scale,
            grid_dim=H_Q, block_dim=D_HEAD,
        )
        ctx.enqueue_function_unchecked(
            f_sdpa16,
            attn16.unsafe_ptr(), qr_buf.unsafe_ptr(), ck16r.unsafe_ptr(), cv16r.unsafe_ptr(),
            N_KEYS, H_Q, H_KV, D_HEAD, scale,
            grid_dim=H_Q, block_dim=D_HEAD,
        )
        ctx.synchronize()

        var max_abs_delta = Float32(0.0)
        var max_val = Float32(0.0)
        with attn32.map_to_host() as h32:
            with attn16.map_to_host() as h16:
                for i in range(H_Q * D_HEAD):
                    var d = _abs(h16[i] - h32[i])
                    if d > max_abs_delta:
                        max_abs_delta = d
                    var v = _abs(h32[i])
                    if v > max_val:
                        max_val = v

        # `n_keys` independent Float16 roundings feed one softmax-weighted output element — see
        # this file's own module docstring for why that is the right depth term here, unlike a
        # GEMV's accumulation-depth-scaled bound.
        var f16_eps = Float32(9.765625e-4)
        var bound = f16_eps * Float32(N_KEYS) * (1.0 + max_val)
        print("  •  isolated fp16-KV-cache attention delta: max|Δ|=", max_abs_delta,
              "over", H_Q * D_HEAD, "output elements, max|attn32|=", max_val)
        if max_abs_delta <= bound:
            passed += 1
            print("  ✅ the isolated fp16-cache SDPA output agrees with the Float32-cache SDPA",
                  "output to", max_abs_delta, "within a Float16 bound of", bound)
        else:
            failed += 1
            print("  ❌ the isolated fp16-cache SDPA output is outside even the loose Float16",
                  "bound:", max_abs_delta, "bound", bound)

        # The bound must be capable of failing, or it proves nothing — same discipline every
        # sibling precision-arm suite in this package uses for its own logit bound.
        if max_abs_delta > 1.0e-6:
            passed += 1
            print("  ✅ ...and the delta would FAIL a tight (1e-6) Float32-precision bound — the",
                  "two really do read different cache storage, so the bound above is not vacuous")
        else:
            failed += 1
            print("  ❌ the two SDPA variants agree to Float32 precision, so the Float16 bound",
                  "above proves nothing about fp16 cache storage")

        print("  [residentk.kernels kvf16-isolated] Passed:", passed, "Failed:", failed)
