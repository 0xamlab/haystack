"""candidate_multi_blob_test.mojo -- STANDALONE go/no-go check (Attention Compiler Plan v1.0,
Phase 2C): the ONE explicit unresolved follow-up risk flagged by `candidate_a_blob_test.mojo`'s own
docstring -- that real production wiring needs MULTIPLE cross-toolchain-forged blobs linked into ONE
binary simultaneously, and the runtime pipeline-discovery mechanism (`algenta_open_session`'s whole-
binary `__TEXT,__const` scan) plus this repo's truncated-name substring classifiers must still
resolve EVERY kernel unambiguously once they coexist.

Links THREE separate forged blobs plus `batch_shim.o` into ONE binary (built by the PINNED
production toolchain, `mojo_env`, Mojo 1.0.0b2 -- never `mma_forge`'s nightly env, which only
compiled these blobs' SOURCE, exactly as `candidate_a_blob_test.mojo` already established):
  - `attention_forge/generated/candidate_a_blob.c` -- Candidate A's one kernel (`_attn_grouped_fa_
    kernel`, `grouped_fa_q8_k32_h2_sg8.mojo`), already built and proven in isolation.
  - `attention_forge/generated/candidate_c_blob.c` -- Candidate C's TWO kernels (`_attn_splitk_
    partial_kernel`, `_attn_splitk_merge_kernel`, `splitk_fa.mojo`), built by this same exercise's
    own `candidate_c_blob_driver.mojo` (mirrors `candidate_a_blob_driver.mojo`'s single-kernel
    pattern and `mma_forge/mm8_driver.mojo`'s multi-kernel-in-one-object-file pattern -- forces BOTH
    kernels' codegen in one `mojo build --emit object` call; `extract_blob.py` found exactly 2 back-
    to-back `MTLB` blobs in that object file, confirming `mm8_driver.mojo`'s own 3-kernel precedent
    that the scan handles multiple blobs in one object file either way).
  - `mma_forge/generated/mm8_blob.c` -- the EXISTING production GEMM blob (`_qkv_proj_gemm_mma8x8`,
    `_gemm_accum_mma8x8`, `_swiglu_gemm_mma8x8`, `mm8.mojo`), already built, never touched by this
    exercise.

Does NOT link `residentk.kernels`' own natively-compiled kernels -- this exercise's own task scope
lists exactly these three blobs plus the shim as the standalone deliverable; residentk's kernels are
compiled directly by the pinned toolchain in the REAL production binary (`qwen3_generate_batch*.mojo`
etc.), never through blob injection, and adding them here would require importing `residentk.kernels`
into this file, which is unnecessary for THIS binary's own three-blob question. See this file's own
`main()` docstring comment, below, for a documented (not executed) collision this exercise's own
string-level inspection of the raw AIR bitcode already found BETWEEN Candidate C's real discovered
names and `metaldispatch.session._classify_splitk_pipeline`'s existing two patterns -- a real risk
for the FUTURE binary that also compiles residentk natively, even though it cannot manifest in the
one built here.

Pipeline discovery and identification
--------------------------------------
This binary links in `batch_shim.o` + THREE forged-blob object files -- `algenta_open_session()`
should discover EXACTLY SIX pipelines (1 from Candidate A's blob, 2 from Candidate C's blob, 3 from
mm8's blob). This file does not assume that: it prints every discovered pipeline's real
(possibly-truncated) Metal function name via `_mb_pipeline_name` (the same introspection call
`candidate_a_blob_test.mojo` already established, exported from the shared, provenance-agnostic
`metaldispatch.ffi` production wrapper layer -- nothing new needed here), then identifies each of
the six expected kernels by a substring match, raising on more than one match per substring (an
ambiguous collision) exactly as `candidate_a_blob_test.mojo`'s own identification loop already does.

Every substring below was chosen only AFTER extracting each blob's own raw AIR bitcode and running
`strings` on the decoded bytes to read the REAL, possibly-truncated Metal function name Mojo's own
name-mangling produced -- never guessed from the Mojo source names. The six real names, confirmed
this way:
  1. Candidate A:      `grouped_fa_q8_k32_h2_sg8__attn_6A6A_d7a1249b06314ef7`
  2. Candidate C part:  `splitk_fa__attn_splitk_partial_6A6A_a889ab263ebf4448`
  3. Candidate C merge: `splitk_fa__attn_splitk_merge_ke6A6A_74c61d24acdbdb2b`
  4. mm8 qkv_proj:      `mm8__qkv_proj_gemm_mma8x8_Poi6A6AoA6A6A_ac3c6a83831daf92`
  5. mm8 gemm_accum:    `mm8__gemm_accum_mma8x8_Pointe6A6AoA6A6A_e3b1140be8c45b1f`
  6. mm8 swiglu:        `mm8__swiglu_gemm_mma8x8_Point6A6AoA6A6A_b69c86ec5da971d8`
None of these six real names share ANY of the discriminating substrings chosen below with each
other -- confirmed both by direct inspection of the six strings above and, more strongly, at runtime
by this file's own dup-detection loop, which would FAIL loudly if that were wrong. Candidate A's own
discriminator is its full, unique module name (`grouped_fa_q8_k32_h2_sg8`), exactly the pattern
`candidate_a_blob_test.mojo` already established for a module containing only one candidate kernel.
Candidate C's two kernels share ONE module (`splitk_fa`), so -- unlike Candidate A -- the module name
alone cannot tell them apart; this file discriminates by the module-QUALIFIED kernel-name prefix
(`splitk_fa__attn_splitk_partial` / `splitk_fa__attn_splitk_merge`), deliberately LONGER than the
bare `splitk_part`/`splitk_merg` patterns `metaldispatch.session._classify_splitk_pipeline` already
uses for RESIDENTK's differently-named `_splitk_partial_kernel_simd`/`_splitk_merge_kernel_simd`.

**A REAL collision this exercise found by inspection, NOT exercised by this binary (documented, not
silently avoided):** Candidate C's own real discovered names both begin `splitk_fa__attn_splitk_
partial_`/`splitk_fa__attn_splitk_merge_ke` -- both contain `_classify_splitk_pipeline`'s existing
bare 11-character patterns `splitk_part`/`splitk_merg` (`residentk_kernels__splitk_part6A6A6A6A_
<hash>` for `_splitk_partial_kernel_simd`, per that classifier's own docstring's measured names) as a
literal substring (`attn_SPLITK_PART` / `attn_SPLITK_MERG`-prefixed-`e_ke`). If Candidate C's blob is
EVER linked into the SAME binary as residentk's own natively-compiled kernels -- exactly what real
production wiring will need, per this whole exercise's own premise -- `_classify_splitk_pipeline`'s
UNMODIFIED two-pattern scan (it scans the WHOLE discovered-pipeline list, not scoped by module) would
find TWO pipelines matching `splitk_part` (residentk's real one and Candidate C's) and TWO matching
`splitk_merg`, with zero text-based way to tell them apart -- the exact ambiguity that classifier's
own docstring already documents finding and fixing ONCE (`_attn_splitk_partial_kernel_simd` vs.
`_splitk_partial_kernel_simd`, before residentk's kernels were renamed to diverge inside the 11-
character window). This is NOT a defect in THIS file (Candidate C's kernels are not compiled
alongside residentk's here, so the ambiguity cannot occur in the binary this file actually builds)
-- it is a genuine, concrete, go/no-go-relevant finding about the NEXT integration step, reported
because this exercise's own instructions ask for an honest collision report over a false all-clear.
It is straightforwardly FIXABLE the same way this file's own Candidate C patterns already are: match
`_classify_splitk_pipeline` (or whatever resolves Candidate C in the real production binary) against
the module-qualified prefix (`splitk_fa__attn_splitk_part` / `splitk_fa__attn_splitk_merg`), which
diverges from residentk's own `residentk_kernels__splitk_part`/`residentk_kernels__splitk_merg` at
the very first character, well inside both kernels' own surviving truncation windows.

Correctness re-check: reuses Candidate A's EXACT dispatch/comparison logic from
`candidate_a_blob_test.mojo`'s own `run_case` (same shapes, same tolerances, same CPU oracle),
against the pipeline_idx THIS binary discovers (not necessarily the same index Candidate A got when
it was the ONLY blob linked in -- that is precisely the risk this file exists to re-check: pipeline
indices are assigned in blob-DISCOVERY order, which depends on every linked object's own internal
blob layout, not on which candidate a human calls "first"). If Candidate A still produces correct
output vs. the CPU oracle now that five OTHER pipelines coexist in the same session, that is this
file's own MINIMUM required result. Candidate C's own partial+merge pair is also re-checked, using
the same tiny-aligned shape and the same CPU-oracle comparison convention `splitk_fa_driver.mojo`'s
own `test_correctness` already established, restated independently here (never imported, matching
every other driver in this package's own no-cross-file-dependency convention).

Build (PINNED `mojo_env` toolchain, following `candidate_a_blob_test.mojo`'s own exact command form,
extended to three `-Xlinker` blob objects instead of one):

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m \
      -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/candidate_a_blob.c -o /tmp/candidate_a_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/candidate_c_blob.c -o /tmp/candidate_c_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -I ../mojo/engine \
        ../attention_forge/candidate_multi_blob_test.mojo \
        -o /tmp/candidate_multi_blob_test \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/candidate_a_blob.o \
        -Xlinker /tmp/candidate_c_blob.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/candidate_multi_blob_test
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
    """Same deterministic generator convention every driver in this package restates
    independently -- see `candidate_a_blob_test.mojo`'s own `_pseudo_f16` docstring."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


# ============================================================================================
# Candidate A: native K/V packing + dispatch + CPU-oracle comparison, restated verbatim from
# `candidate_a_blob_test.mojo` (not imported -- this repo's own established no-cross-file-
# dependency convention for these throwaway drivers).
# ============================================================================================


def _pack_k_native_a(
    k64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int
) -> List[Float64]:
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


def _pack_v_native_a(
    v64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int
) -> List[Float64]:
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


def run_case_candidate_a(
    pipeline_idx: Int, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, offset: Int,
) raises -> Bool:
    """Candidate A's exact dispatch + comparison, byte-identical in logic to
    `candidate_a_blob_test.mojo`'s own `run_case` -- the re-check this file exists to run: does the
    SAME kernel, at the SAME shapes, still produce correct output vs. the CPU oracle now that five
    OTHER pipelines (Candidate C's two, mm8's three) coexist in this binary's own session?"""
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

    var k_native = _pack_k_native_a(k64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var v_native = _pack_v_native_a(v64, n_tok_k, h_kv, d, key_block_size, n_blocks)

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
        out_f32[i] = Float32(-999.0)  # canary
    var lse_f32 = lse_ptr.bitcast[Float32]()
    for i in range(n_lse_elems):
        lse_f32[i] = Float32(-999.0)

    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * (h_q // 2)
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


# ============================================================================================
# Candidate C: native K/V packing + two-kernel (partial + merge) dispatch + CPU-oracle
# comparison, restated independently from `splitk_fa_driver.mojo`'s own `_pack_native_kv` /
# `test_correctness` -- same flat-index formulas, same tolerance convention, not imported.
# ============================================================================================


def _pack_native_kv_c(natural64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, n_blocks: Int, is_k: Bool) -> List[Float64]:
    var kbs = 32
    var size = h_kv * n_blocks * d * kbs
    var out = List[Float64](capacity=size)
    for _ in range(size):
        out.append(0.0)
    for j in range(n_tok_k):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for dd in range(d):
                var src = (j * h_kv + hk) * d + dd
                if is_k:
                    var dst = ((hk * n_blocks + block) * d + dd) * kbs + kk
                    out[dst] = natural64[src]
                else:
                    var dst = ((hk * n_blocks + block) * kbs + kk) * d + dd
                    out[dst] = natural64[src]
    return out^


def run_case_candidate_c(
    partial_idx: Int, merge_idx: Int, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, offset: Int, n_splits: Int,
) raises -> Bool:
    """Candidate C's full partial+merge pipeline, dispatched through THIS multi-blob binary's own
    discovered pipeline indices, checked against `attnk.sdpa.sdpa_forward_flat` -- the same oracle
    and tolerance convention `splitk_fa_driver.mojo`'s own `test_correctness` already established.
    Two SEPARATE `_mb_run_token` calls (partial, then merge) -- not one token with two descriptors --
    so the merge's read of the partial's device-memory scratch writes is guaranteed visible by a full
    `waitUntilCompleted` in between, mirroring `splitk_fa_driver.mojo`'s own `ctx.synchronize()`
    between the two dispatches exactly, rather than leaning on same-encoder dispatch-ordering
    semantics (which production's own 171-dispatch-per-token design DOES rely on, but which this
    correctness re-check has no need to also exercise)."""
    var d = 128

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

    var n_blocks = (n_tok_k + 31) // 32
    var k_native = _pack_native_kv_c(k64, n_tok_k, h_kv, d, n_blocks, True)
    var v_native = _pack_native_kv_c(v64, n_tok_k, h_kv, d, n_blocks, False)

    var q_addr = UInt64(0); var q_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var k_addr = UInt64(0); var k_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var v_addr = UInt64(0); var v_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var m_addr = UInt64(0); var m_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var l_addr = UInt64(0); var l_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var o_addr = UInt64(0); var o_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var out_addr = UInt64(0); var out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var lse_addr = UInt64(0); var lse_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    var n_q_elems = n_tok_q * h_q * d
    var n_k_elems = h_kv * n_blocks * d * 32
    var n_v_elems = h_kv * n_blocks * 32 * d
    var n_mln_elems = n_tok_q * h_q * n_splits
    var n_o_elems = n_tok_q * h_q * n_splits * d
    var n_out_elems = n_tok_q * h_q * d
    var n_lse_elems = h_q * n_tok_q

    if _mb_alloc_buffer(n_q_elems * 2, q_addr, q_ptr) < 0:
        print("  [", name, "] FAIL: alloc Q buffer failed"); return False
    if _mb_alloc_buffer(n_k_elems * 2, k_addr, k_ptr) < 0:
        print("  [", name, "] FAIL: alloc K buffer failed"); return False
    if _mb_alloc_buffer(n_v_elems * 2, v_addr, v_ptr) < 0:
        print("  [", name, "] FAIL: alloc V buffer failed"); return False
    if _mb_alloc_buffer(n_mln_elems * 4, m_addr, m_ptr) < 0:
        print("  [", name, "] FAIL: alloc m_scratch buffer failed"); return False
    if _mb_alloc_buffer(n_mln_elems * 4, l_addr, l_ptr) < 0:
        print("  [", name, "] FAIL: alloc l_scratch buffer failed"); return False
    if _mb_alloc_buffer(n_o_elems * 4, o_addr, o_ptr) < 0:
        print("  [", name, "] FAIL: alloc o_scratch buffer failed"); return False
    if _mb_alloc_buffer(n_out_elems * 4, out_addr, out_ptr) < 0:
        print("  [", name, "] FAIL: alloc out buffer failed"); return False
    if _mb_alloc_buffer(n_lse_elems * 4, lse_addr, lse_ptr) < 0:
        print("  [", name, "] FAIL: alloc lse buffer failed"); return False

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
        out_f32[i] = Float32(-999.0)  # canary
    var lse_f32 = lse_ptr.bitcast[Float32]()
    for i in range(n_lse_elems):
        lse_f32[i] = Float32(-999.0)

    var n_q_blocks = (n_tok_q + 7) // 8
    var n_pairs = h_q // 2

    # ---- dispatch 1: partial kernel (14 args) ----
    var grid_partial = n_q_blocks * n_pairs * n_splits
    var desc_partial = _mb_alloc_descriptors(1)
    _mb_set_header(desc_partial, 0, partial_idx, grid_partial, 256, 14)
    _mb_set_arg_ptr(desc_partial, 0, 0, m_addr)
    _mb_set_arg_ptr(desc_partial, 0, 1, l_addr)
    _mb_set_arg_ptr(desc_partial, 0, 2, o_addr)
    _mb_set_arg_ptr(desc_partial, 0, 3, q_addr)
    _mb_set_arg_ptr(desc_partial, 0, 4, k_addr)
    _mb_set_arg_ptr(desc_partial, 0, 5, v_addr)
    _mb_set_arg_int(desc_partial, 0, 6, n_tok_q)
    _mb_set_arg_int(desc_partial, 0, 7, n_tok_k)
    _mb_set_arg_int(desc_partial, 0, 8, h_q)
    _mb_set_arg_int(desc_partial, 0, 9, h_kv)
    _mb_set_arg_f32(desc_partial, 0, 10, Float32(scale64))
    _mb_set_arg_int(desc_partial, 0, 11, offset)
    _mb_set_arg_int(desc_partial, 0, 12, n_splits)
    _mb_set_arg_int(desc_partial, 0, 13, n_blocks)

    var status_partial = _mb_run_token(desc_partial, 1)
    if status_partial != 0:
        print("  [", name, "] FAIL: partial dispatch, algenta_run_token returned", status_partial)
        return False

    # ---- dispatch 2: merge kernel (8 args) -- SEPARATE token, guaranteeing the partial's device-
    # memory writes are visible (full commit + waitUntilCompleted already happened above). ----
    var grid_merge = n_tok_q * h_q
    var desc_merge = _mb_alloc_descriptors(1)
    _mb_set_header(desc_merge, 0, merge_idx, grid_merge, 128, 8)
    _mb_set_arg_ptr(desc_merge, 0, 0, out_addr)
    _mb_set_arg_ptr(desc_merge, 0, 1, lse_addr)
    _mb_set_arg_ptr(desc_merge, 0, 2, m_addr)
    _mb_set_arg_ptr(desc_merge, 0, 3, l_addr)
    _mb_set_arg_ptr(desc_merge, 0, 4, o_addr)
    _mb_set_arg_int(desc_merge, 0, 5, n_tok_q)
    _mb_set_arg_int(desc_merge, 0, 6, h_q)
    _mb_set_arg_int(desc_merge, 0, 7, n_splits)

    var status_merge = _mb_run_token(desc_merge, 1)
    if status_merge != 0:
        print("  [", name, "] FAIL: merge dispatch, algenta_run_token returned", status_merge)
        return False
    print("  [", name, "] dispatch OK (partial + merge)")

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
    print("=== Multi-blob coexistence go/no-go: Candidate A + Candidate C + mm8 in ONE binary ===")

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", opened)
        return
    var count = _mb_pipeline_count()
    print("pipelines discovered:", count, "(expected 6: 1 Candidate A + 2 Candidate C + 3 mm8)")
    print("")

    var candidate_a_idx = -1
    var candidate_c_partial_idx = -1
    var candidate_c_merge_idx = -1
    var mm8_qkv_idx = -1
    var mm8_accum_idx = -1
    var mm8_swiglu_idx = -1
    var ambiguous = False

    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print("  pipeline", i, ": name=", name)

        if name.find("grouped_fa_q8_k32_h2_sg8") >= 0:
            if candidate_a_idx >= 0:
                print("  FAIL: pipeline", i, "ALSO matched 'grouped_fa_q8_k32_h2_sg8' -- already matched by pipeline", candidate_a_idx)
                ambiguous = True
            candidate_a_idx = i
        if name.find("splitk_fa__attn_splitk_partial") >= 0:
            if candidate_c_partial_idx >= 0:
                print("  FAIL: pipeline", i, "ALSO matched 'splitk_fa__attn_splitk_partial' -- already matched by pipeline", candidate_c_partial_idx)
                ambiguous = True
            candidate_c_partial_idx = i
        if name.find("splitk_fa__attn_splitk_merge") >= 0:
            if candidate_c_merge_idx >= 0:
                print("  FAIL: pipeline", i, "ALSO matched 'splitk_fa__attn_splitk_merge' -- already matched by pipeline", candidate_c_merge_idx)
                ambiguous = True
            candidate_c_merge_idx = i
        if name.find("qkv_proj_gemm_mma8x8") >= 0:
            if mm8_qkv_idx >= 0:
                print("  FAIL: pipeline", i, "ALSO matched 'qkv_proj_gemm_mma8x8' -- already matched by pipeline", mm8_qkv_idx)
                ambiguous = True
            mm8_qkv_idx = i
        if name.find("gemm_accum_mma8x8") >= 0:
            if mm8_accum_idx >= 0:
                print("  FAIL: pipeline", i, "ALSO matched 'gemm_accum_mma8x8' -- already matched by pipeline", mm8_accum_idx)
                ambiguous = True
            mm8_accum_idx = i
        if name.find("swiglu_gemm_mma8x8") >= 0:
            if mm8_swiglu_idx >= 0:
                print("  FAIL: pipeline", i, "ALSO matched 'swiglu_gemm_mma8x8' -- already matched by pipeline", mm8_swiglu_idx)
                ambiguous = True
            mm8_swiglu_idx = i

    print("")
    if ambiguous:
        print("FAIL: at least one discriminating substring matched more than one discovered pipeline -- see above")
        return

    print("Candidate A         identified at pipeline_idx =", candidate_a_idx)
    print("Candidate C partial  identified at pipeline_idx =", candidate_c_partial_idx)
    print("Candidate C merge    identified at pipeline_idx =", candidate_c_merge_idx)
    print("mm8 qkv_proj         identified at pipeline_idx =", mm8_qkv_idx)
    print("mm8 gemm_accum       identified at pipeline_idx =", mm8_accum_idx)
    print("mm8 swiglu           identified at pipeline_idx =", mm8_swiglu_idx)
    print("")

    var all_found = True
    if candidate_a_idx < 0:
        print("FAIL: Candidate A not discovered"); all_found = False
    if candidate_c_partial_idx < 0:
        print("FAIL: Candidate C partial not discovered"); all_found = False
    if candidate_c_merge_idx < 0:
        print("FAIL: Candidate C merge not discovered"); all_found = False
    if mm8_qkv_idx < 0:
        print("FAIL: mm8 qkv_proj not discovered"); all_found = False
    if mm8_accum_idx < 0:
        print("FAIL: mm8 gemm_accum not discovered"); all_found = False
    if mm8_swiglu_idx < 0:
        print("FAIL: mm8 swiglu not discovered"); all_found = False
    if not all_found:
        return

    print("=== Candidate A re-dispatch through the multi-blob binary ===")
    var all_ok = True
    all_ok = run_case_candidate_a(candidate_a_idx, "tiny aligned", 8, 64, 2, 1, 0) and all_ok
    all_ok = run_case_candidate_a(
        candidate_a_idx, "real Qwen3-0.6B-Base dims, ragged K, offset=37", 17, 130, 16, 8, 37
    ) and all_ok

    print("")
    print("=== Candidate C re-dispatch (partial + merge) through the multi-blob binary ===")
    all_ok = run_case_candidate_c(
        candidate_c_partial_idx, candidate_c_merge_idx, "tiny aligned s2", 8, 64, 2, 1, 0, 2
    ) and all_ok
    all_ok = run_case_candidate_c(
        candidate_c_partial_idx, candidate_c_merge_idx,
        "real Qwen3-0.6B-Base dims, ragged K, offset=37, s2", 17, 130, 16, 8, 37, 2
    ) and all_ok

    print("")
    print("MULTI-BLOB COEXISTENCE (Candidate A + Candidate C + mm8, ONE binary):", "PASS" if all_ok else "FAIL")
