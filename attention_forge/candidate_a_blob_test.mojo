"""candidate_a_blob_test.mojo -- STANDALONE go/no-go test (Attention Compiler Plan v1.0, Phase 2C):
dispatches CANDIDATE A's real GPU kernel (`_attn_grouped_fa_kernel`, `grouped_fa_q8_k32_h2_sg8.mojo`)
through the production FFI surface (`metaldispatch.ffi`) after being compiled by a DIFFERENT
toolchain (`mma_forge`'s nightly pixi env) and extracted/linked as a raw Metal bitcode blob into a
binary built by the PINNED production toolchain (`mojo_env`, Mojo 1.0.0b2) -- exactly the "proven
mma_forge mechanism" `mma_forge/mm8_driver.mojo`'s own docstring describes, but never yet exercised
for an attention-shaped (12-argument, 5-pointer) kernel; the largest kernel this mechanism has
carried before is `mm8.mojo`'s 7-argument GEMM kernels.

NOT wired into any production path. Does not import, and this whole exercise does not modify,
`mojo/engine/metaldispatch/session*.mojo` or anything under `mojo/engine/residentk/` -- this file
only imports the shared, provenance-agnostic FFI wrapper layer (`metaldispatch.ffi`) that production
code also uses, per this task's own instruction to use "the same FFI import path production code
uses."

Pipeline discovery and identification
--------------------------------------
This binary links in ONLY `batch_shim.o` + the one extracted `candidate_a_blob.o` (no `residentk`
kernels, no other forge blobs) -- so `algenta_open_session()` should discover EXACTLY ONE pipeline.
This file does not assume that and dispatch to index 0 regardless: it prints every discovered
pipeline's real (possibly-truncated) Metal function name via `_mb_pipeline_name`, then identifies
Candidate A's pipeline by a substring match against the FULL, UNTRUNCATED module-qualified prefix
`grouped_fa_q8_k32_h2_sg8`. This is confirmed, not assumed: the blob-extraction step of this same
exercise (`python3 mma_forge/tools/extract_blob.py /tmp/candidate_a_forge.o ... ; grep` on the
generated `.c`) found the real embedded AIR function name to be exactly
`grouped_fa_q8_k32_h2_sg8__attn_6A6A_d7a1249b06314ef7` -- the MODULE name survives fully intact;
only 5 characters of the kernel's OWN name (`_attn_grouped_fa_kernel` -> `attn_`) survive the
truncation window before the `6A6A` filler + opaque hash. That is a DIFFERENT, and stronger,
discriminator than `mojo/engine/metaldispatch/session.mojo`'s own `_classify_pipeline`/
`_classify_splitk_pipeline`/`_classify_prefill_pipeline` get to use: those classify kernels that all
share ONE module (`residentk.kernels`), so only the kernel-name SUFFIX -- truncated to roughly 11
survivable characters, per that file's own measured docstring -- has any discriminating power, and
that file documents real truncation collisions hit as a result (e.g. `_pf_attn8_` needing to be
checked before the prefix-colliding `_pf_attn_`, `splitk_part`/`splitk_merg` needing a rename to
diverge before the 11-character boundary). Here, each forge-extracted attention candidate lives in
its OWN separate module file (`grouped_fa_q8_k32_h2_sg8.mojo` vs. `splitk_fa.mojo`), so the module
name ITSELF -- not the truncated kernel-name suffix -- is what survives and what this file matches
on. That match is safe in THIS binary specifically because only one blob is linked in at all; it
would need re-verifying (count discovered pipelines, confirm exactly one substring match, exactly as
below) the moment a second attention-shaped blob is linked into the same binary -- this file already
guards that by raising on more than one substring match, not just taking the first.

Shapes chosen (two, via a shared `run_case` helper, same open session, same discovered pipeline_idx):
1. "tiny aligned" -- the SAME shape `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `test_correctness`
   already exercises and `candidate_a_blob_driver.mojo` (this exercise's codegen-forcing driver)
   already used -- n_tok_q=8, n_tok_k=64, h_q=2, h_kv=1, d=128, offset=0 (GQA-valid: h_q even;
   native-KV-aligned: 64 keys is exactly 2 full blocks at key_block_size=32, zero ragged tail).
   Deliberately SMALL and ALIGNED, as the FIRST cross-toolchain DISPATCH validation -- single
   threadgroup, simplest possible grid.
2. "real Qwen3-0.6B-Base dims, ragged K, offset=37" -- n_tok_q=17, n_tok_k=130, h_q=16, h_kv=8,
   d=128, offset=37 (the SAME shape `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `test_correctness`
   uses for its own "real Qwen3-0.6B-Base dims" case). Exercises a 16-threadgroup grid (multiple
   q-blocks x all 8 sibling-head pairs), a ragged final native K/V block (130 keys = 4 full blocks
   of 32 + a 2-key tail), and a nonzero causal offset (KV-cache continuation) -- all inside the SAME
   cross-toolchain-dispatched binary as case 1, strengthening confidence that case 1's PASS was not
   an accident of the trivial single-block shape.
Both cases are already proven correct for this kernel INSIDE the forge toolchain by `grouped_fa_
q8_k32_h2_sg8_driver.mojo`; what is UNPROVEN, and what this file exists to test, is the cross-
toolchain blob-extraction-and-link-and-dispatch MECHANISM itself, not a new sweep of shapes.

Q/K/V test vectors and K/V native packing: the SAME `_pseudo_f16` generator convention and the SAME
native-packing flat-index formula `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `_pack_k_native`/
`_pack_v_native` use, restated independently here (not imported) -- this repo's own established
driver convention of not depending on another phase's/file's internals across files, and per this
task's own instruction that this program be genuinely standalone.

CPU oracle: `attnk.sdpa.sdpa_forward_flat`, the SAME trusted materialized Float64 reference
`grouped_fa_q8_k32_h2_sg8_driver.mojo` itself checks against, at the SAME tolerance convention
(`allowed = 5.0e-2 * (1.0 + abs(want))`, `ratio = diff / allowed`, `worst_ratio <= 1.0` => OK).

Build (PINNED `mojo_env` toolchain, NOT mma_forge -- exact command form following
`qwen3_generate_batch_i8_allsimd7_prefill.mojo`'s own docstring pattern):

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m \
      -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/candidate_a_blob.c -o /tmp/candidate_a_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -I ../mojo/engine \
        ../attention_forge/candidate_a_blob_test.mojo \
        -o /tmp/candidate_a_blob_test \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/candidate_a_blob.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/candidate_a_blob_test
"""
from std.builtin.type_aliases import MutAnyOrigin
from metaldispatch.ffi import (
    _mb_open_session,
    _mb_pipeline_count,
    _mb_pipeline_name,
    _mb_alloc_buffer,
    _mb_alloc_descriptors,
    _mb_set_header,
    _mb_set_arg_ptr,
    _mb_set_arg_int,
    _mb_set_arg_f32,
    _mb_run_token,
)
from attnk.contract import ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    """Same deterministic generator convention `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own
    `_pseudo_f16` uses -- restated here independently, per this file's own standalone requirement."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def _pack_k_native(
    k64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int
) -> List[Float64]:
    """Restated independently from `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `_pack_k_native` --
    same flat-index formula (`((hk*n_blocks+block)*d+dd)*key_block_size+kk`), not imported."""
    var total = h_kv * n_blocks * d * key_block_size
    var out = List[Float64](capacity=total)
    for _ in range(total):
        out.append(0.0)
    for gk in range(n_tok_k):
        var block = gk // key_block_size
        var kk = gk % key_block_size
        for hk in range(h_kv):
            for dd in range(d):
                out[((hk * n_blocks + block) * d + dd) * key_block_size + kk] = k64[(gk * h_kv + hk) * d + dd]
    return out^


def _pack_v_native(
    v64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int
) -> List[Float64]:
    """Restated independently from `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `_pack_v_native`."""
    var total = h_kv * n_blocks * key_block_size * d
    var out = List[Float64](capacity=total)
    for _ in range(total):
        out.append(0.0)
    for gk in range(n_tok_k):
        var block = gk // key_block_size
        var kk = gk % key_block_size
        for hk in range(h_kv):
            for dd in range(d):
                out[((hk * n_blocks + block) * key_block_size + kk) * d + dd] = v64[(gk * h_kv + hk) * d + dd]
    return out^


def run_case(
    pipeline_idx: Int, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, offset: Int,
) raises -> Bool:
    """One end-to-end cross-toolchain dispatch + CPU-oracle comparison at the given shape. `d` is
    fixed at 128 (Candidate A's own specialization, per its module docstring)."""
    var d = 128
    var key_block_size = 32
    var n_blocks = (n_tok_k + key_block_size - 1) // key_block_size

    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)

    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] FAIL: mask build failed, status=", cm.status)
        return False
    var scale64 = 1.0 / Float64(d) ** 0.5
    var oracle = sdpa_forward_flat(q64, k64, v64, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale64, True)
    if oracle.status != ATTN_OK:
        print("  [", name, "] FAIL: CPU oracle failed, status=", oracle.status)
        return False

    var k_native = _pack_k_native(k64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var v_native = _pack_v_native(v64, n_tok_k, h_kv, d, key_block_size, n_blocks)

    # ---- allocate real GPU buffers through the shim (same entry point production code uses) ----
    var q_addr = UInt64(0); var q_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var k_addr = UInt64(0); var k_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var v_addr = UInt64(0); var v_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var out_addr = UInt64(0); var out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var lse_addr = UInt64(0); var lse_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    var n_q_elems = n_tok_q * h_q * d
    var n_k_elems = h_kv * n_blocks * d * key_block_size
    var n_v_elems = h_kv * n_blocks * key_block_size * d
    var n_out_elems = n_tok_q * h_q * d
    var n_lse_elems = h_q * n_tok_q

    if _mb_alloc_buffer(n_q_elems * 2, q_addr, q_ptr) < 0:
        print("  [", name, "] FAIL: alloc Q buffer failed")
        return False
    if _mb_alloc_buffer(n_k_elems * 2, k_addr, k_ptr) < 0:
        print("  [", name, "] FAIL: alloc K buffer failed")
        return False
    if _mb_alloc_buffer(n_v_elems * 2, v_addr, v_ptr) < 0:
        print("  [", name, "] FAIL: alloc V buffer failed")
        return False
    if _mb_alloc_buffer(n_out_elems * 4, out_addr, out_ptr) < 0:
        print("  [", name, "] FAIL: alloc out buffer failed")
        return False
    if _mb_alloc_buffer(n_lse_elems * 4, lse_addr, lse_ptr) < 0:
        print("  [", name, "] FAIL: alloc lse buffer failed")
        return False

    var q_f16 = q_ptr.bitcast[Float16]()
    for i in range(n_q_elems):
        q_f16[i] = Float16(Float32(q64[i]))
    var k_f16 = k_ptr.bitcast[Float16]()
    for i in range(n_k_elems):
        k_f16[i] = Float16(Float32(k_native[i]))
    var v_f16 = v_ptr.bitcast[Float16]()
    for i in range(n_v_elems):
        v_f16[i] = Float16(Float32(v_native[i]))
    var out_f32 = out_ptr.bitcast[Float32]()
    for i in range(n_out_elems):
        out_f32[i] = Float32(-999.0)  # canary: must be fully overwritten for every valid row
    var lse_f32 = lse_ptr.bitcast[Float32]()
    for i in range(n_lse_elems):
        lse_f32[i] = Float32(-999.0)

    # ---- descriptor: Candidate A's own 12-argument signature, grid flattened to 1D (already is --
    # `_attn_grouped_fa_kernel` unflattens `block_idx.x` into `(q_block, pair_idx)` internally) ----
    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * (h_q // 2)  # = 1
    var descriptors = _mb_alloc_descriptors(1)
    _mb_set_header(descriptors, 0, pipeline_idx, grid, 256, 12)
    _mb_set_arg_ptr(descriptors, 0, 0, out_addr)
    _mb_set_arg_ptr(descriptors, 0, 1, lse_addr)
    _mb_set_arg_ptr(descriptors, 0, 2, q_addr)
    _mb_set_arg_ptr(descriptors, 0, 3, k_addr)
    _mb_set_arg_ptr(descriptors, 0, 4, v_addr)
    _mb_set_arg_int(descriptors, 0, 5, n_tok_q)
    _mb_set_arg_int(descriptors, 0, 6, n_tok_k)
    _mb_set_arg_int(descriptors, 0, 7, h_q)
    _mb_set_arg_int(descriptors, 0, 8, h_kv)
    _mb_set_arg_f32(descriptors, 0, 9, Float32(scale64))
    _mb_set_arg_int(descriptors, 0, 10, offset)
    _mb_set_arg_int(descriptors, 0, 11, n_blocks)

    var run_status = _mb_run_token(descriptors, 1)
    if run_status != 0:
        print("  [", name, "] FAIL: algenta_run_token returned", run_status)
        return False
    print("  [", name, "] dispatch OK")

    # ---- compare vs CPU oracle, SAME tolerance convention as grouped_fa_q8_k32_h2_sg8_driver.mojo ----
    var worst_out = 0.0
    var worst_out_idx = -1
    for i in range(n_out_elems):
        var got = Float64(out_f32[i])
        var want = oracle.out[i]
        var diff = _abs64(got - want)
        var allowed = 5.0e-2 * (1.0 + _abs64(want))
        var ratio = diff / allowed
        if ratio > worst_out:
            worst_out = ratio
            worst_out_idx = i

    var worst_lse = 0.0
    for i in range(n_lse_elems):
        var got = Float64(lse_f32[i])
        var want = oracle.lse[i]
        var diff = _abs64(got - want)
        var allowed = 5.0e-2 * (1.0 + _abs64(want))
        var ratio = diff / allowed
        if ratio > worst_lse:
            worst_lse = ratio

    var ok = worst_out <= 1.0 and worst_lse <= 1.0
    print("  [", name, "] worst-ratio out=", worst_out, " (at flat idx", worst_out_idx, ") lse=", worst_lse, "  ", "OK" if ok else "MISMATCH")
    return ok


def main() raises:
    print("=== Candidate A cross-toolchain blob dispatch: go/no-go ===")

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", opened)
        return
    var count = _mb_pipeline_count()
    print("pipelines discovered:", count)

    var pipeline_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print("  pipeline", i, ": name=", name)
        if name.find("grouped_fa_q8_k32_h2_sg8") >= 0:
            if pipeline_idx >= 0:
                print("FAIL: multiple pipelines matched the candidate-A module substring -- ambiguous")
                return
            pipeline_idx = i

    if pipeline_idx < 0:
        print("FAIL: no discovered pipeline matched substring 'grouped_fa_q8_k32_h2_sg8'")
        return
    print("Candidate A identified at pipeline_idx =", pipeline_idx)
    print("")

    var all_ok = True
    all_ok = run_case(pipeline_idx, "tiny aligned", 8, 64, 2, 1, 0) and all_ok
    all_ok = run_case(
        pipeline_idx, "real Qwen3-0.6B-Base dims, ragged K, offset=37", 17, 130, 16, 8, 37
    ) and all_ok

    print("")
    print("CANDIDATE A CROSS-TOOLCHAIN BLOB DISPATCH:", "PASS" if all_ok else "FAIL")
