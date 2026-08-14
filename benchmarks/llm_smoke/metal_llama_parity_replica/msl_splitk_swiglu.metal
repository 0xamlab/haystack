/* msl_splitk_swiglu.metal -- beat-llama.cpp campaign concurrent front, round 3 increment 3
 * (2026-08-12): the small-M fix for the fused gate+up swiglu role in the BATCHED decode table.
 *
 * WHY: the shipped `msl_parity__swiglu_mul_mm_f16_f32` at m_rows=B<=32 launches only
 * (n_ff/64)=48... 96 threadgroups (here n_ff=3072 -> 96 tiles at N=2*n_ff viewed as gate+up) and
 * the counter probe measured 9.30 ms per B=32 step -- the round-2 "small-M GEMM underfill" class.
 * Split-K for swiglu CANNOT use the direct atomic-into-dst trick of the plain accum roles: the
 * swiglu nonlinearity `silu(g)*u` needs BOTH full-K products (gate AND up) before combining, and
 * atomic partial sums of g/u separately would be combined wrongly. So this file ships the
 * two-stage form:
 *
 *   1. `msl_splitk4__swiglu_partial_f16_f32` -- the SAME 32x64-tile split-K GEMM machinery as
 *      `msl_splitk_accum.metal`'s F16-weight kernels (S=4: K=1024 -> 256 per split = 8 K-steps),
 *      computing xn @ [Wg;Wu]^T over the FULL [B, 2*n_ff] output into a zeroed scratch buffer,
 *      atomic-adding its partials (gate cols [0,n_ff), up cols [n_ff,2*n_ff)). Grid =
 *      (M/32) x (2*n_ff/64) x 4 = 384 threadgroups at B<=32 -- 4x the shipped kernel's fill.
 *      F16 weights: the session's `msl_w_gu_f16` twin, layout `[2*n_ff, k]` row-major half, gate
 *      rows [0,n_ff), up rows [n_ff,2*n_ff) -- SAME twin the shipped swiglu kernel's nomirror
 *      substitution reads, no repacking.
 *   2. `msl_swiglu_apply_f32` -- elementwise `act[m,j] = silu(scratch[m,j]) * scratch[m,j+n_ff]`,
 *      float4-vectorized, one guard tail.
 *
 * The batched table dispatches [zero(scratch), partial, apply] in place of the single shipped
 * swiglu dispatch (zero via `msl_zero_f32` of `msl_zero.metal`), guarded by discovery of both
 * kernels below (session fields `msl_splitk4_swiglu_pipeline_idx`/`msl_swiglu_apply_pipeline_idx`).
 *
 * ABI: partial = identical 7-arg descriptor layout to the parity/splitk family (constant-ulong
 * addresses + int64 scalars; wscale bound but unused -- the F16 twin is already dequantized).
 * apply = 4 args (scratch addr, act addr, n_ff, n_elem=B*n_ff).
 *
 * Build (one metallib PER kernel via its define gate -- batch_shim registers functionNames[0] of
 * each MTLB blob; concatenate both metallibs into one blob exactly like build_msl_splitk_blob.sh):
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -DSK_SWIGLU_PARTIAL=1 -c msl_splitk_swiglu.metal -o /tmp/sksw_part.air
 *   xcrun -sdk macosx metallib /tmp/sksw_part.air -o /tmp/sksw_part.metallib
 *   xcrun -sdk macosx metal -DSK_SWIGLU_APPLY=1 -c msl_splitk_swiglu.metal -o /tmp/sksw_apply.air
 *   xcrun -sdk macosx metallib /tmp/sksw_apply.air -o /tmp/sksw_apply.metallib
 *   cat /tmp/sksw_part.metallib /tmp/sksw_apply.metallib > /tmp/sksw_all.metallib
 *   python3 mma_forge/tools/extract_blob.py /tmp/sksw_all.metallib \
 *       mma_forge/generated/msl_splitk_swiglu_blob.c --symbol algenta_msl_splitk_swiglu_blob
 */
#include <metal_stdlib>
using namespace metal;

#ifdef SK_SWIGLU_PARTIAL

#define SKS_NR1 32
#define SKS_NR0 64
#define SKS_NK  32
#define SKS_S   4

[[max_total_threads_per_threadgroup(128)]]
kernel void msl_splitk4__swiglu_partial_f16_f32(
        constant ulong & y_addr        [[buffer(0)]],   /* scratch, float [M, 2*n_ff], zeroed */
        constant ulong & x_addr        [[buffer(1)]],   /* activations, float [M, k] */
        constant ulong & w_addr        [[buffer(2)]],   /* F16 twin [2*n_ff, k], gate rows first */
        constant ulong & wscale_addr   [[buffer(3)]],   /* bound, unused (twin already dequantized) */
        constant long  & m_rows_arg    [[buffer(4)]],
        constant long  & k_arg         [[buffer(5)]],
        constant long  & n_arg         [[buffer(6)]],   /* = 2*n_ff */
        uint  tg [[threadgroup_position_in_grid]],
        ushort tiitg [[thread_index_in_threadgroup]],
        ushort sgitg [[simdgroup_index_in_threadgroup]]) {

    const int K = (int)k_arg;
    const int N = (int)n_arg;
    const int M = (int)m_rows_arg;

    const int n_tiles_m = (M + SKS_NR1 - 1) / SKS_NR1;
    const int is = (int)(tg % (uint)SKS_S);             /* split index */
    const int tile = (int)(tg / (uint)SKS_S);
    const int im = tile % n_tiles_m;
    const int in = tile / n_tiles_m;
    const int m_base = im * SKS_NR1;
    const int n_base = in * SKS_NR0;
    const int k_lo = is * (K / SKS_S);
    const int k_hi = k_lo + (K / SKS_S);

    threadgroup char shmem[8192];
    threadgroup half * sa = (threadgroup half *)(shmem);
    threadgroup half * sb = sa + SKS_NR1 * SKS_NK;

    device const float * X = reinterpret_cast<device const float *>(x_addr);
    device const half  * W = reinterpret_cast<device const half  *>(w_addr);
    device       float * dst = reinterpret_cast<device float *>(y_addr);

    const int sm = (sgitg & 1) * 16;
    const int sn = (sgitg >> 1) * 32;

    simdgroup_float8x8 mc[8];
    for (int i = 0; i < 8; i++) mc[i] = make_filled_simdgroup_matrix<float, 8>(0.f);

    for (int loop_k = k_lo; loop_k < k_hi; loop_k += SKS_NK) {
        threadgroup_barrier(mem_flags::mem_threadgroup);
        {
            /* A tile [32][32] halfs: two float4 device loads narrowed to half4 stores. */
            const int row = tiitg / 4;
            const int col = (tiitg % 4) * 8;
            const int m_abs = m_base + row;
            if (m_abs < M) {
                float4 v0 = *(device const float4 *)(X + (uint64_t)m_abs * (uint64_t)K + loop_k + col);
                float4 v1 = *(device const float4 *)(X + (uint64_t)m_abs * (uint64_t)K + loop_k + col + 4);
                *(threadgroup half4 *)(sa + row * SKS_NK + col) = half4(v0);
                *(threadgroup half4 *)(sa + row * SKS_NK + col + 4) = half4(v1);
            } else {
                *(threadgroup half4 *)(sa + row * SKS_NK + col) = half4(0.0h);
                *(threadgroup half4 *)(sa + row * SKS_NK + col + 4) = half4(0.0h);
            }
        }
        {
            /* B tile [64][32] halfs from the F16 twin (already dequantized): 4 half4 loads/thread. */
            const int row = tiitg / 2;
            const int col = (tiitg % 2) * 16;
            const int n_abs = n_base + row;
            if (n_abs < N) {
                _Pragma("clang loop unroll(full)")
                for (int j = 0; j < 4; j++) {
                    *(threadgroup half4 *)(sb + row * SKS_NK + col + 4 * j) =
                        *(device const half4 *)(W + (uint64_t)n_abs * (uint64_t)K + loop_k + col + 4 * j);
                }
            } else {
                _Pragma("clang loop unroll(full)")
                for (int j = 0; j < 4; j++) {
                    *(threadgroup half4 *)(sb + row * SKS_NK + col + 4 * j) = half4(0.0h);
                }
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        _Pragma("clang loop unroll(full)")
        for (int ik = 0; ik < SKS_NK / 8; ik++) {
            simdgroup_half8x8 ma[2];
            simdgroup_half8x8 mb[4];
            simdgroup_barrier(mem_flags::mem_none);
            _Pragma("clang loop unroll(full)")
            for (int f = 0; f < 2; f++) {
                simdgroup_load(ma[f], sa + (sm + 8 * f) * SKS_NK + 8 * ik, SKS_NK, 0, true);
            }
            simdgroup_barrier(mem_flags::mem_none);
            _Pragma("clang loop unroll(full)")
            for (int g = 0; g < 4; g++) {
                simdgroup_load(mb[g], sb + (sn + 8 * g) * SKS_NK + 8 * ik, SKS_NK, 0, false);
            }
            simdgroup_barrier(mem_flags::mem_none);
            _Pragma("clang loop unroll(full)")
            for (int f = 0; f < 2; f++) {
                _Pragma("clang loop unroll(full)")
                for (int g = 0; g < 4; g++) {
                    simdgroup_multiply_accumulate(mc[f * 4 + g], mb[g], ma[f], mc[f * 4 + g]);
                }
            }
        }
    }

    /* Atomic-accumulate epilogue (same form as msl_splitk_accum.metal's): stage the 32x64 float
     * tile in threadgroup memory, then every thread atomic-adds 16 elements into the scratch.
     * feat/batched-llama (2026-08-14): the `m_abs < M` guard is LOAD-BEARING -- the batched
     * scratch is sized EXACTLY B rows (`B * 2 * n_ff` floats), so the padded rows of the 32-row
     * tile must NOT be written: an atomic-add of the staged 0.0 is value-neutral where it lands,
     * but past the buffer end it is an out-of-bounds GPU access (page fault whenever the adjacent
     * pages happen to be unmapped -- d_ff=5632 x 32 padded rows reaches ~1.4 MB past an 88 KB
     * scratch; the old Qwen3 runs survived only because THEIR adjacent allocations -- the much
     * larger logits buffer allocated right after -- happened to map the whole OOB reach). */
    threadgroup_barrier(mem_flags::mem_threadgroup);
    threadgroup float * stg = (threadgroup float *)(shmem);
    const int sm_st = (sgitg & 1) * 16;
    const int sn_st = (sgitg >> 1) * 32;
    _Pragma("clang loop unroll(full)")
    for (int f = 0; f < 2; f++) {
        _Pragma("clang loop unroll(full)")
        for (int g = 0; g < 4; g++) {
            simdgroup_store(mc[f * 4 + g], stg + (sm_st + 8 * f) * SKS_NR0 + (sn_st + 8 * g), SKS_NR0, 0, true);
        }
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (int i = tiitg; i < SKS_NR1 * SKS_NR0; i += 128) {
        const int row = i / SKS_NR0;
        const int col = i % SKS_NR0;
        const int m_abs = m_base + row;
        if (m_abs < M) {
            atomic_fetch_add_explicit(
                (device atomic_float *)(dst + (uint64_t)m_abs * (uint64_t)N + n_base + col),
                stg[i], memory_order_relaxed);
        }
    }
}

#endif /* SK_SWIGLU_PARTIAL */

#ifdef SK_SWIGLU_APPLY

/* act[m, j] = silu(scratch[m, j]) * scratch[m, j + n_ff]; scratch is [M, 2*n_ff] float with gate
 * logits in cols [0, n_ff) and up logits in cols [n_ff, 2*n_ff) -- the exact layout
 * msl_splitk4__swiglu_partial_f16_f32 atomic-accumulates (weight twin is gate-rows-first, so
 * output col j pairs gate weight row j with up weight row n_ff+j). n_ff % 4 == 0 for every Qwen3
 * variant, so the vector path never crosses a row; the scalar tail guards the grid end. */
kernel void msl_swiglu_apply_f32(
        constant ulong & scratch_addr [[buffer(0)]],
        constant ulong & act_addr     [[buffer(1)]],
        constant long  & n_ff_arg     [[buffer(2)]],
        constant long  & n_elem_arg   [[buffer(3)]],    /* = B * n_ff */
        uint gid [[thread_position_in_grid]]) {
    device const float * sc = reinterpret_cast<device const float *>(scratch_addr);
    device       float * act = reinterpret_cast<device float *>(act_addr);
    const long n_ff = n_ff_arg;
    const long n_elem = n_elem_arg;
    long i = (long)gid * 4;
    if (i + 4 <= n_elem) {
        const long m = i / n_ff;
        const long j = i % n_ff;
        float4 g = *(device const float4 *)(sc + m * 2 * n_ff + j);
        float4 u = *(device const float4 *)(sc + m * 2 * n_ff + n_ff + j);
        float4 r = (g / (1.0f + exp(-g))) * u;
        *(device float4 *)(act + i) = r;
    } else {
        for (long t = i; t < n_elem; t++) {
            const long m = t / n_ff;
            const long j = t % n_ff;
            float g = sc[m * 2 * n_ff + j];
            float u = sc[m * 2 * n_ff + n_ff + j];
            act[t] = (g / (1.0f + exp(-g))) * u;
        }
    }
}

#endif /* SK_SWIGLU_APPLY */
