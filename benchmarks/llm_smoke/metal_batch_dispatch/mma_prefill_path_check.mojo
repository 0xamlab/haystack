"""mma_prefill_path_check.mojo — Phase 3 integration check: does `_MBQwen3I8AllSimd7Prefill`'s
`prefill_batch()` ACTUALLY exercise the new hardware-MMA path end to end, and does it agree with the
byte-identical `step()` path, when `m_rows` is MMA-eligible?

The existing golden-vector test (`test_metaldispatch_session_prefill.mojo`) never exercises this:
its toy shape uses `D_FF=40` (not a multiple of 32, so `use_mma` in `_apply_m_rows` is always False
for it) and `M=4` prefilled rows. This probe uses a shape where `d_model`/`n_qkv`/`d_ff` are ALL
multiples of 32 (so the model-shape half of `use_mma`'s eligibility check is satisfied), and prefills
EXACTLY 32 rows (satisfying the `m_rows % 32 == 0` half) — the smallest real MMA-eligible case.

Methodology: two separately-constructed instances, uploaded the SAME weights. Instance A calls
`prefill_batch(prompt[0:32], 0)` (hits the MMA path). Instance B calls `step(prompt[i], i)` 32 times
sequentially (the OLD, per-token decode path, never touched by this whole effort). Both predict the
SAME next-token distribution at position 32 — comparing them needs no new CPU-reference composition
gate, since `step()` is itself an ALREADY-established, independently-verified oracle.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_prefill_path_check.mojo \
        -o /tmp/mma_prefill_path_check \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_prefill_path_check
"""
from std.math import sqrt
from std.sys import has_accelerator
from attnk.rope import rope_table
from metaldispatch.contract import MB_OK, metaldispatch_status_name
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill

comptime D_MODEL: Int = 32
comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 32
comptime D_FF: Int = 32
comptime N_LAYERS: Int = 1
comptime VOCAB: Int = 23
comptime MAX_CTX: Int = 64
comptime EPS: Float64 = 1.0e-6
comptime THETA: Float64 = 10000.0
comptime M: Int = 32


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


def main() raises:
    var passed = 0
    var failed = 0

    if not has_accelerator():
        print("SKIP: no GPU accelerator on this host")
        return

    var scale = 1.0 / sqrt(Float64(D_HEAD))
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

    var rt = rope_table(D_HEAD, MAX_CTX, THETA)

    # ── Instance A: prefill_batch(M=32) -- MMA-eligible, hits _PFROLE_GEMM_*_MMA ──────────────
    var a = _MBQwen3I8AllSimd7Prefill(D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, EPS, scale)
    var up_a = a.upload_globals(embed, final_norm, rt.cos_table, rt.sin_table, MAX_CTX)
    for l in range(N_LAYERS):
        if up_a == MB_OK:
            up_a = a.upload_layer(l, ln1[l], ln2[l], qn[l], kn[l], wq[l], wk[l], wv[l], wo[l], wg[l], wu[l], wd[l])
    if up_a == MB_OK:
        up_a = a.seal()
    if up_a != MB_OK:
        print("FAIL: instance A upload failed:", metaldispatch_status_name(up_a))
        return

    var pf = a.prefill_batch(prompt, 0)
    if pf.status != MB_OK:
        print("FAIL: prefill_batch failed:", metaldispatch_status_name(pf.status))
        return
    passed += 1
    print("  ✅ prefill_batch(M=32) ran", pf.dispatches, "dispatches, status OK")

    # ── Instance B: 32x step(), byte-identical weights, never touches the MMA path ────────────
    var b = _MBQwen3I8AllSimd7Prefill(D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, EPS, scale)
    var up_b = b.upload_globals(embed, final_norm, rt.cos_table, rt.sin_table, MAX_CTX)
    for l in range(N_LAYERS):
        if up_b == MB_OK:
            up_b = b.upload_layer(l, ln1[l], ln2[l], qn[l], kn[l], wq[l], wk[l], wv[l], wo[l], wg[l], wu[l], wd[l])
    if up_b == MB_OK:
        up_b = b.seal()
    if up_b != MB_OK:
        print("FAIL: instance B upload failed:", metaldispatch_status_name(up_b))
        return

    var last = b.step(prompt[0], 0)
    if last.status != MB_OK:
        print("FAIL: step() 0 failed:", metaldispatch_status_name(last.status))
        return
    for i in range(1, M):
        last = b.step(prompt[i], i)
        if last.status != MB_OK:
            print("FAIL: step()", i, "failed:", metaldispatch_status_name(last.status))
            return
    passed += 1
    print("  ✅ 32x step() on the twin instance ran to completion, status OK")

    var i8_eps = 1.0 / 127.0
    var depth = Float64(N_LAYERS * (D_MODEL + D_FF) + D_MODEL)
    var tol = i8_eps * depth

    if pf.token_id == last.token_id:
        passed += 1
        print("  ✅ prefill_batch(M=32) [MMA path] and 32x step() [scalar path] choose the SAME token:", pf.token_id)
    else:
        failed += 1
        print("  ❌ token mismatch: prefill_batch=", pf.token_id, " step-chain=", last.token_id)

    var d = pf.logit - last.logit
    if d < 0:
        d = -d
    if d <= tol:
        passed += 1
        print("  ✅ logits agree to", d, "within tolerance", tol)
    else:
        failed += 1
        print("  ❌ logit mismatch:", d, "exceeds tolerance", tol,
              "(prefill=", pf.logit, "step-chain=", last.logit, ")")

    print("  [mma_prefill_path_check] Passed:", passed, "Failed:", failed)
