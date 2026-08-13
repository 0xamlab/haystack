/* msl_lmhead_batched.metal -- beat-llama.cpp campaign concurrent front, round 3 increment 4
 * (2026-08-12): the GEMM-style rebuild of the batched lm_head.
 *
 * WHY: the shipped `_batched_lmhead_argmax_kernel_simd_i8` sweeps the 155 MB embed/lm_head weight
 * matrix with B rows of accumulator work serialized through its `_LM_BLOCKS`-sized grid -- the
 * counter probe measured 9.70 ms at B=32 (~1 TF/s effective vs a ~0.3 ms bandwidth floor). This
 * file replaces it with the SAME structure llama.cpp uses for the output projection: a proper
 * tiled simdgroup-matrix GEMM `[B, d_model] @ embed^T -> logits [B, vocab]` at grid
 * (B/32)x(vocab/64) = 2374 threadgroups (fully machine-filling at B<=32), Int8-DIRECT weights
 * with in-kernel dequant (the embed twin is Int8+per-row-scale; no F16 twin materialized for a
 * 311 MB matrix), then a small two-stage argmax: block-max over the logits rows feeding the
 * EXISTING engine-side `_batched_argmax_reduce_kernel_simd` (its blk_val/blk_idx contract is
 * reused unchanged).
 *
 * Kernels:
 *   1. `msl_vocab__gemm_i8_f32` -- 32x64 tile, K=d_model loop, direct float store into the
 *      logits scratch [B, vocab] (no atomics: single K pass, each output written once). 7-arg
 *      descriptor ABI identical to the parity/splitk family (logits addr, xn addr, embed-int8
 *      addr, embed-scale addr, m_rows=B, k=d_model, n=vocab).
 *   2. `msl_logits_blockmax_f32` -- one threadgroup per (row, vocab-block): scans the row's block
 *      slice for the (max, argmax) pair and writes blk_val[row*blocks+blk]/blk_idx[...] in the
 *      EXACT [B, blocks] layout `_batched_argmax_reduce_kernel_simd` reads. Args: logits addr,
 *      blk_val addr, blk_idx addr, vocab, blocks. Grid = B*blocks threadgroups x 256 threads.
 *
 * Build (one metallib per kernel via its define gate; concatenate into one blob):
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal-DLMHEAD_GEMM=1 ... (see msl_splitk_swiglu.metal's identical recipe)
 */
#include <metal_stdlib>
using namespace metal;

#ifdef LMHEAD_GEMM

#define LH_NR1 32
#define LH_NR0 64
#define LH_NK  32

[[max_total_threads_per_threadgroup(128)]]
kernel void msl_vocab__gemm_i8_f32(
        constant ulong & y_addr        [[buffer(0)]],   /* logits, float [M, vocab] */
        constant ulong & x_addr        [[buffer(1)]],   /* activations, float [M, k] */
        constant ulong & w_addr        [[buffer(2)]],   /* embed, Int8 [vocab, k] */
        constant ulong & wscale_addr   [[buffer(3)]],   /* per-output-row scales [vocab] */
        constant long  & m_rows_arg    [[buffer(4)]],
        constant long  & k_arg         [[buffer(5)]],
        constant long  & n_arg         [[buffer(6)]],
        uint3  tgpig  [[threadgroup_position_in_grid]],
        ushort tiitg  [[thread_index_in_threadgroup]],
        ushort sgitg  [[simdgroup_index_in_threadgroup]]) {

    const int K = (int)k_arg;
    const int N = (int)n_arg;
    const int M = (int)m_rows_arg;

    const int n_tiles_m = (M + LH_NR1 - 1) / LH_NR1;
    const int im = (int)(tgpig.x % (uint)n_tiles_m);
    const int in = (int)(tgpig.x / (uint)n_tiles_m);
    const int m_base = im * LH_NR1;
    const int n_base = in * LH_NR0;

    threadgroup char shmem[8192];
    threadgroup half * sa = (threadgroup half *)(shmem);
    threadgroup half * sb = sa + LH_NR1 * LH_NK;

    device const float * X = reinterpret_cast<device const float *>(x_addr);
    device const char  * W = reinterpret_cast<device const char  *>(w_addr);
    device const float * wsc = reinterpret_cast<device const float *>(wscale_addr);
    device       float * dst = reinterpret_cast<device float *>(y_addr);

    const int sm = (sgitg & 1) * 16;
    const int sn = (sgitg >> 1) * 32;

    simdgroup_float8x8 mc[8];
    for (int i = 0; i < 8; i++) mc[i] = make_filled_simdgroup_matrix<float, 8>(0.f);

    for (int loop_k = 0; loop_k < K; loop_k += LH_NK) {
        threadgroup_barrier(mem_flags::mem_threadgroup);
        {
            const int row = tiitg / 4;
            const int col = (tiitg % 4) * 8;
            const int m_abs = m_base + row;
            if (m_abs < M) {
                float4 v0 = *(device const float4 *)(X + (uint64_t)m_abs * (uint64_t)K + loop_k + col);
                float4 v1 = *(device const float4 *)(X + (uint64_t)m_abs * (uint64_t)K + loop_k + col + 4);
                *(threadgroup half4 *)(sa + row * LH_NK + col) = half4(v0);
                *(threadgroup half4 *)(sa + row * LH_NK + col + 4) = half4(v1);
            } else {
                *(threadgroup half4 *)(sa + row * LH_NK + col) = half4(0.0h);
                *(threadgroup half4 *)(sa + row * LH_NK + col + 4) = half4(0.0h);
            }
        }
        {
            /* B tile [64][32] from Int8-direct weights: four char4 loads dequantized in-kernel. */
            const int row = tiitg / 2;
            const int col = (tiitg % 2) * 16;
            const int n_abs = n_base + row;
            if (n_abs < N) {
                const float s = wsc[n_abs];
                _Pragma("clang loop unroll(full)")
                for (int j = 0; j < 4; j++) {
                    char4 c4 = *(device const char4 *)(W + (uint64_t)n_abs * (uint64_t)K + loop_k + col + 4 * j);
                    *(threadgroup half4 *)(sb + row * LH_NK + col + 4 * j) =
                        half4(half(float(c4.x) * s), half(float(c4.y) * s),
                              half(float(c4.z) * s), half(float(c4.w) * s));
                }
            } else {
                _Pragma("clang loop unroll(full)")
                for (int j = 0; j < 4; j++) {
                    *(threadgroup half4 *)(sb + row * LH_NK + col + 4 * j) = half4(0.0h);
                }
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        _Pragma("clang loop unroll(full)")
        for (int ik = 0; ik < LH_NK / 8; ik++) {
            simdgroup_half8x8 ma[2];
            simdgroup_half8x8 mb[4];
            simdgroup_barrier(mem_flags::mem_none);
            _Pragma("clang loop unroll(full)")
            for (int f = 0; f < 2; f++) {
                simdgroup_load(ma[f], sa + (sm + 8 * f) * LH_NK + 8 * ik, LH_NK, 0, true);
            }
            simdgroup_barrier(mem_flags::mem_none);
            _Pragma("clang loop unroll(full)")
            for (int g = 0; g < 4; g++) {
                simdgroup_load(mb[g], sb + (sn + 8 * g) * LH_NK + 8 * ik, LH_NK, 0, false);
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

    /* Direct-store epilogue: stage the 32x64 float tile in threadgroup memory, then write the
     * in-bounds elements to logits. */
    threadgroup_barrier(mem_flags::mem_threadgroup);
    threadgroup float * stg = (threadgroup float *)(shmem);
    const int sm_st = (sgitg & 1) * 16;
    const int sn_st = (sgitg >> 1) * 32;
    _Pragma("clang loop unroll(full)")
    for (int f = 0; f < 2; f++) {
        _Pragma("clang loop unroll(full)")
        for (int g = 0; g < 4; g++) {
            simdgroup_store(mc[f * 4 + g], stg + (sm_st + 8 * f) * LH_NR0 + (sn_st + 8 * g), LH_NR0, 0, true);
        }
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (int i = tiitg; i < LH_NR1 * LH_NR0; i += 128) {
        const int row = i / LH_NR0;
        const int col = i % LH_NR0;
        const int m_abs = m_base + row;
        const int n_abs = n_base + col;
        if (m_abs < M && n_abs < N) {
            dst[(uint64_t)m_abs * (uint64_t)N + n_abs] = stg[i];
        }
    }
}

#endif /* LMHEAD_GEMM */

#ifdef LOGITS_BLOCKMAX

/* One threadgroup per (row, vocab-block): find the block's (max, argmax) over the logits row and
 * write blk_val[row*blocks + blk] / blk_idx[...] -- the exact [B, blocks] pair layout the
 * engine's existing `_batched_argmax_reduce_kernel_simd` collapses to the final token. */
kernel void msl_logits_blockmax_f32(
        constant ulong & logits_addr  [[buffer(0)]],
        constant ulong & blk_val_addr [[buffer(1)]],
        constant ulong & blk_idx_addr [[buffer(2)]],
        constant long  & vocab_arg    [[buffer(3)]],
        constant long  & blocks_arg   [[buffer(4)]],
        uint  tg [[threadgroup_position_in_grid]],
        ushort tiitg [[thread_index_in_threadgroup]]) {

    device const float * logits = reinterpret_cast<device const float *>(logits_addr);
    device float * blk_val = reinterpret_cast<device float *>(blk_val_addr);
    device int   * blk_idx = reinterpret_cast<device int   *>(blk_idx_addr);

    const long blocks = blocks_arg;
    const long vocab = vocab_arg;
    const long row = (long)tg / blocks;
    const long blk = (long)tg % blocks;

    const long lo = (vocab * blk) / blocks;
    const long hi = (vocab * (blk + 1)) / blocks;

    float local_max = -INFINITY;
    long local_idx = lo;
    for (long v = lo + (long)tiitg; v < hi; v += 256) {
        float x = logits[row * vocab + v];
        if (x > local_max) {
            local_max = x;
            local_idx = v;
        }
    }

    threadgroup float sh_v[256];
    threadgroup long  sh_i[256];
    sh_v[tiitg] = local_max;
    sh_i[tiitg] = local_idx;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (ushort stride = 128; stride > 0; stride >>= 1) {
        if (tiitg < stride) {
            if (sh_v[tiitg + stride] > sh_v[tiitg]) {
                sh_v[tiitg] = sh_v[tiitg + stride];
                sh_i[tiitg] = sh_i[tiitg + stride];
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (tiitg == 0) {
        blk_val[row * blocks + blk] = sh_v[0];
        blk_idx[row * blocks + blk] = (int)sh_i[0];
    }
}

#endif /* LOGITS_BLOCKMAX */
