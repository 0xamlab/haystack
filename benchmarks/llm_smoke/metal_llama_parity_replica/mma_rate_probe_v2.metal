/* mma_rate_probe_v2.metal -- beat-llama.cpp campaign (2026-08-11 night): re-test of the
 * "13.3 TF simdgroup-MMA wall" (front-2 third strike, 2026-08-09). That wall was measured HOT
 * (deliberate DVFS heater) with ONE layout only (128 threads = 4 simdgroups/TG, NACC=8, GRID=320,
 * 8x8x8 f16->f32). Two questions this re-test answers:
 *   (1) Is 13.3 TF the SILICON ceiling, or the hot-sustained ceiling? (the host harness runs the
 *       baseline kernel FIRST, on a cool GPU, before any heater -- the delta is DVFS headroom);
 *   (2) Is it layout-dependent? Variants below widen the threadgroup (8 simdgroups), deepen the
 *       independent-accumulator chains (NACC=16), or both -- a higher number on any variant means
 *       the prefill GEMM tier has real headroom via scheduling, not silicon.
 * FLOPs per dispatch = GRID x simdgroups_per_tg x ITER x NACC x 1024 (8x8x8 mma).
 */
#include <metal_stdlib>
using namespace metal;

#define ITER 64

/* baseline: identical to the 2026-08-09 probe's register-only kernel (4 simdgroups, NACC=8). */
kernel void mma_v2_reg(device float *dst [[buffer(0)]],
                       device const half *src [[buffer(1)]],
                       uint tg [[threadgroup_position_in_grid]],
                       ushort tiitg [[thread_index_in_threadgroup]],
                       ushort sgitg [[simdgroup_index_in_threadgroup]]) {
    threadgroup half ta[64];
    threadgroup half tb[64];
    if (tiitg < 64) { ta[tiitg] = src[tiitg]; tb[tiitg] = src[64 + tiitg]; }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    simdgroup_half8x8 a, b;
    simdgroup_load(a, ta, 8, 0, false);
    simdgroup_load(b, tb, 8, 0, false);
    simdgroup_float8x8 c[8];
    for (int j = 0; j < 8; j++) c[j] = make_filled_simdgroup_matrix<float, 8>(0.f);
    for (int i = 0; i < ITER; i++) {
        #pragma clang loop unroll(full)
        for (int j = 0; j < 8; j++) {
            simdgroup_multiply_accumulate(c[j], b, a, c[j]);
        }
    }
    #pragma clang loop unroll(full)
    for (int j = 0; j < 8; j++) {
        simdgroup_store(c[j], dst + ((uint64_t)tg * 8 + j) * 64, 8, 0, false);
    }
}

/* NACC=16: twice the independent accumulator chains per simdgroup (deeper ILP). */
kernel void mma_v2_reg_nacc16(device float *dst [[buffer(0)]],
                              device const half *src [[buffer(1)]],
                              uint tg [[threadgroup_position_in_grid]],
                              ushort tiitg [[thread_index_in_threadgroup]],
                              ushort sgitg [[simdgroup_index_in_threadgroup]]) {
    threadgroup half ta[64];
    threadgroup half tb[64];
    if (tiitg < 64) { ta[tiitg] = src[tiitg]; tb[tiitg] = src[64 + tiitg]; }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    simdgroup_half8x8 a, b;
    simdgroup_load(a, ta, 8, 0, false);
    simdgroup_load(b, tb, 8, 0, false);
    simdgroup_float8x8 c[16];
    for (int j = 0; j < 16; j++) c[j] = make_filled_simdgroup_matrix<float, 8>(0.f);
    for (int i = 0; i < ITER; i++) {
        #pragma clang loop unroll(full)
        for (int j = 0; j < 16; j++) {
            simdgroup_multiply_accumulate(c[j], b, a, c[j]);
        }
    }
    #pragma clang loop unroll(full)
    for (int j = 0; j < 16; j++) {
        simdgroup_store(c[j], dst + ((uint64_t)tg * 16 + j) * 64, 8, 0, false);
    }
}

/* 8 simdgroups per threadgroup (256 threads), NACC=8. */
kernel void mma_v2_reg_sg8(device float *dst [[buffer(0)]],
                           device const half *src [[buffer(1)]],
                           uint tg [[threadgroup_position_in_grid]],
                           ushort tiitg [[thread_index_in_threadgroup]],
                           ushort sgitg [[simdgroup_index_in_threadgroup]]) {
    threadgroup half ta[64];
    threadgroup half tb[64];
    if (tiitg < 64) { ta[tiitg] = src[tiitg]; tb[tiitg] = src[64 + tiitg]; }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    simdgroup_half8x8 a, b;
    simdgroup_load(a, ta, 8, 0, false);
    simdgroup_load(b, tb, 8, 0, false);
    simdgroup_float8x8 c[8];
    for (int j = 0; j < 8; j++) c[j] = make_filled_simdgroup_matrix<float, 8>(0.f);
    for (int i = 0; i < ITER; i++) {
        #pragma clang loop unroll(full)
        for (int j = 0; j < 8; j++) {
            simdgroup_multiply_accumulate(c[j], b, a, c[j]);
        }
    }
    #pragma clang loop unroll(full)
    for (int j = 0; j < 8; j++) {
        simdgroup_store(c[j], dst + ((uint64_t)tg * 8 + j) * 64, 8, 0, false);
    }
}

/* 8 simdgroups per threadgroup AND NACC=16. */
kernel void mma_v2_reg_sg8_nacc16(device float *dst [[buffer(0)]],
                                  device const half *src [[buffer(1)]],
                                  uint tg [[threadgroup_position_in_grid]],
                                  ushort tiitg [[thread_index_in_threadgroup]],
                                  ushort sgitg [[simdgroup_index_in_threadgroup]]) {
    threadgroup half ta[64];
    threadgroup half tb[64];
    if (tiitg < 64) { ta[tiitg] = src[tiitg]; tb[tiitg] = src[64 + tiitg]; }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    simdgroup_half8x8 a, b;
    simdgroup_load(a, ta, 8, 0, false);
    simdgroup_load(b, tb, 8, 0, false);
    simdgroup_float8x8 c[16];
    for (int j = 0; j < 16; j++) c[j] = make_filled_simdgroup_matrix<float, 8>(0.f);
    for (int i = 0; i < ITER; i++) {
        #pragma clang loop unroll(full)
        for (int j = 0; j < 16; j++) {
            simdgroup_multiply_accumulate(c[j], b, a, c[j]);
        }
    }
    #pragma clang loop unroll(full)
    for (int j = 0; j < 16; j++) {
        simdgroup_store(c[j], dst + ((uint64_t)tg * 16 + j) * 64, 8, 0, false);
    }
}
