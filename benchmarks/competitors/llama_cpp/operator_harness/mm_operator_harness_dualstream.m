/* mm_operator_harness_dualstream.m -- the CONTROL half of the dual-stream concurrency test
 * (REALRACE_RESULTS.md "Gate 0, MECHANISM RESOLVED" entry's pre-registered next experiment): the
 * Algenta side (`mma_forge/probes/gemm_qkv_proj_dualstream.mojo` via `batch_shim_async.m`) showed
 * its `_qkv_proj_gemm_mma8x8` gets ZERO overlap from two concurrent batched streams (span == sum
 * of per-stream durations, each stream ~12% slower co-scheduled). This file runs the IDENTICAL
 * pairing against llama.cpp's own `kernel_mul_mm_f16_f32` -- the kernel whose dense single stream
 * reaches ~10.5 TF/s (~77% of sustained f16 MMA peak) via dispatch overlap -- to bracket the
 * finding: does a kernel already near peak also get nothing from a second stream (machine
 * saturated), or does it overlap (in which case the Algenta kernel's zero-overlap is a
 * kernel-specific full-occupancy signature, as diagnosed)?
 *
 * Pairing (identical to the Mojo probe): S1 single N=112; S2 single N=56; D1 two concurrent
 * streams x N=56 (two command buffers committed back-to-back on the SAME queue before either
 * waits); D2 two concurrent streams x N=112. Metrics per cell: medians of gpu-total (single) or
 * span = max(end)-min(start) plus per-stream durations (dual); aggregate marginal = span / total
 * dispatches. Everything else is byte-for-byte mm_operator_harness_batched.m's setup: same pinned
 * kernel (FC_MUL_MM=700), same constants, same real qkv_proj shape (M=256, K=1024, N=4096), same
 * grid (8x64 threadgroups, 32x4 threads), same SMEM; correctness already validated by that
 * harness's N=1 CPU-reference check, so this file keeps dispatch-error checks only.
 *
 * MACHINE-STATE DISCLOSURE: same 9-day-uptime steady state as the other 2026-08-12 entries --
 * only same-session comparisons are load-bearing.
 *
 * Build:
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src mm_operator_harness_dualstream.m -o /tmp/mm_operator_harness_dualstream
 *   /tmp/mm_operator_harness_dualstream /tmp/ggml_mm.metallib
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ggml-metal-impl.h"

#define M_ROWS 256
#define K_DIM  1024
#define N_DIM  4096

#define N_REPS 15
#define N_WARM 3

static float pseudo(int i, int seed, float amp) {
    float a = (float)((i * 37 + seed * 101) % 61) / 30.0f - 1.0f;
    float b = (float)((i * 13 + seed * 7) % 29) / 14.0f - 1.0f;
    return amp * (a + 0.5f * b);
}

static uint16_t f32_to_f16(float f) {
    uint32_t x = *(uint32_t *)&f;
    uint32_t sign = (x >> 16) & 0x8000;
    int32_t exp = ((x >> 23) & 0xFF) - 127 + 15;
    uint32_t mant = x & 0x7FFFFF;
    if (exp <= 0) return (uint16_t)sign;
    if (exp >= 31) return (uint16_t)(sign | 0x7C00);
    return (uint16_t)(sign | (exp << 10) | (mant >> 13));
}

static double percentile_sorted(const double *sorted, int n, double frac) {
    int idx = (int)(frac * n);
    if (idx >= n) idx = n - 1;
    if (idx < 0) idx = 0;
    return sorted[idx];
}

static void insertion_sort(double *a, int n) {
    for (int i = 1; i < n; i++) {
        double k = a[i]; int j = i - 1;
        while (j >= 0 && a[j] > k) { a[j+1] = a[j]; j--; }
        a[j+1] = k;
    }
}

/* encode one command buffer with N dispatches and COMMIT it (no wait) */
static id<MTLCommandBuffer> commit_batch(id<MTLCommandQueue> queue, id<MTLComputePipelineState> pipeline,
                                         id<MTLBuffer> wBuf, id<MTLBuffer> xBuf, id<MTLBuffer> yBuf,
                                         const ggml_metal_kargs_mul_mm *kargs, MTLSize grid, MTLSize tpg,
                                         NSUInteger smem, int N) {
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pipeline];
    for (int d = 0; d < N; d++) {
        [enc setBytes:kargs length:sizeof(*kargs) atIndex:0];
        [enc setBuffer:wBuf offset:0 atIndex:1];
        [enc setBuffer:xBuf offset:0 atIndex:2];
        [enc setBuffer:yBuf offset:0 atIndex:3];
        [enc setThreadgroupMemoryLength:smem atIndex:0];
        [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
    }
    [enc endEncoding];
    [cb commit];
    return cb;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 2) { fprintf(stderr, "usage: %s <metallib path>\n", argv[0]); return 1; }

        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "no Metal device\n"); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        NSError *err = nil;
        NSURL *libURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
        id<MTLLibrary> library = [device newLibraryWithURL:libURL error:&err];
        if (!library) { fprintf(stderr, "newLibraryWithURL failed: %s\n", err.localizedDescription.UTF8String); return 1; }

        MTLFunctionConstantValues *cv = [MTLFunctionConstantValues new];
        BOOL bc_inp = NO, bc_out = NO;
        int16_t fc_ne12 = 1, fc_ne13 = 1, fc_r2 = 1, fc_r3 = 1;
        [cv setConstantValue:&bc_inp  type:MTLDataTypeBool  atIndex:FC_MUL_MM + 0];
        [cv setConstantValue:&bc_out  type:MTLDataTypeBool  atIndex:FC_MUL_MM + 1];
        [cv setConstantValue:&fc_ne12 type:MTLDataTypeShort atIndex:FC_MUL_MM + 2];
        [cv setConstantValue:&fc_ne13 type:MTLDataTypeShort atIndex:FC_MUL_MM + 3];
        [cv setConstantValue:&fc_r2   type:MTLDataTypeShort atIndex:FC_MUL_MM + 4];
        [cv setConstantValue:&fc_r3   type:MTLDataTypeShort atIndex:FC_MUL_MM + 5];

        id<MTLFunction> fn = [library newFunctionWithName:@"kernel_mul_mm_f16_f32"
                                            constantValues:cv error:&err];
        if (!fn) { fprintf(stderr, "newFunctionWithName failed: %s\n", err.localizedDescription.UTF8String); return 1; }
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:fn error:&err];
        if (!pipeline) { fprintf(stderr, "pipeline creation failed: %s\n", err.localizedDescription.UTF8String); return 1; }

        size_t n_w = (size_t)N_DIM * K_DIM;
        size_t n_x = (size_t)M_ROWS * K_DIM;
        size_t n_y = (size_t)M_ROWS * N_DIM;

        uint16_t *w_f16 = malloc(n_w * sizeof(uint16_t));
        for (size_t i = 0; i < n_w; i++) w_f16[i] = f32_to_f16(pseudo((int)(i % 5000003), 41, 0.5f));
        float *x_f32 = malloc(n_x * sizeof(float));
        for (size_t i = 0; i < n_x; i++) x_f32[i] = pseudo((int)(i % 5000003), 59, 0.5f);

        id<MTLBuffer> wBuf = [device newBufferWithBytes:w_f16 length:n_w * sizeof(uint16_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> xBuf = [device newBufferWithBytes:x_f32 length:n_x * sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> yBuf = [device newBufferWithLength:n_y * sizeof(float) options:MTLResourceStorageModeShared];

        ggml_metal_kargs_mul_mm kargs;
        memset(&kargs, 0, sizeof(kargs));
        kargs.ne00 = K_DIM;
        kargs.ne02 = 1;
        kargs.nb01 = (uint64_t)K_DIM * sizeof(uint16_t);
        kargs.nb02 = kargs.nb01 * (uint64_t)N_DIM;
        kargs.nb03 = kargs.nb02 * (uint64_t)kargs.ne02;
        kargs.ne12 = 1;
        kargs.nb10 = sizeof(float);
        kargs.nb11 = (uint64_t)K_DIM * sizeof(float);
        kargs.nb12 = kargs.nb11 * (uint64_t)M_ROWS;
        kargs.nb13 = kargs.nb12 * (uint64_t)kargs.ne12;
        kargs.ne0 = N_DIM;
        kargs.ne1 = M_ROWS;
        kargs.r2 = 1;
        kargs.r3 = 1;

        const NSUInteger NR0 = 64, NR1 = 32;
        const NSUInteger SMEM = 4096 + 2048;
        MTLSize grid = MTLSizeMake((M_ROWS + NR1 - 1) / NR1, (N_DIM + NR0 - 1) / NR0, 1);
        MTLSize tpg  = MTLSizeMake(32, 4, 1);

        /* warmup */
        for (int w = 0; w < 5; w++) {
            id<MTLCommandBuffer> cb = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, 1);
            [cb waitUntilCompleted];
        }

        printf("%-16s %14s %14s %14s %14s\n", "cell", "med_total_ms", "p10_ms", "p90_ms", "marginal_ms");

        /* S1: single N=112; S2: single N=56 */
        struct { const char *name; int N; } singles[] = { {"S1_single_112", 112}, {"S2_single_56", 56} };
        double s1_med = 0.0;
        for (int si = 0; si < 2; si++) {
            int N = singles[si].N;
            double reps[N_REPS];
            for (int w = 0; w < N_WARM; w++) {
                id<MTLCommandBuffer> cb = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, N);
                [cb waitUntilCompleted];
            }
            for (int rep = 0; rep < N_REPS; rep++) {
                id<MTLCommandBuffer> cb = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, N);
                [cb waitUntilCompleted];
                if (cb.error) { fprintf(stderr, "%s failed: %s\n", singles[si].name, cb.error.localizedDescription.UTF8String); return 1; }
                reps[rep] = (cb.GPUEndTime - cb.GPUStartTime) * 1000.0;
            }
            insertion_sort(reps, N_REPS);
            double med = percentile_sorted(reps, N_REPS, 0.5);
            if (si == 0) s1_med = med;
            printf("%-16s %14.4f %14.4f %14.4f %14.4f\n", singles[si].name, med,
                   percentile_sorted(reps, N_REPS, 0.1), percentile_sorted(reps, N_REPS, 0.9), med / (double)N);
        }

        /* D1: two concurrent streams x 56; D2: two concurrent streams x 112 */
        struct { const char *name; int N; int total; } duals[] = { {"D1_dual_2x56", 56, 112}, {"D2_dual_2x112", 112, 224} };
        double d1_span_med = 0.0;
        for (int di = 0; di < 2; di++) {
            int N = duals[di].N;
            double spans[N_REPS], durA[N_REPS], durB[N_REPS];
            for (int w = 0; w < N_WARM; w++) {
                id<MTLCommandBuffer> a = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, N);
                id<MTLCommandBuffer> b = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, N);
                [a waitUntilCompleted]; [b waitUntilCompleted];
            }
            for (int rep = 0; rep < N_REPS; rep++) {
                id<MTLCommandBuffer> a = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, N);
                id<MTLCommandBuffer> b = commit_batch(queue, pipeline, wBuf, xBuf, yBuf, &kargs, grid, tpg, SMEM, N);
                [a waitUntilCompleted]; [b waitUntilCompleted];
                if (a.error || b.error) { fprintf(stderr, "%s failed\n", duals[di].name); return 1; }
                double a_start = a.GPUStartTime, a_end = a.GPUEndTime;
                double b_start = b.GPUStartTime, b_end = b.GPUEndTime;
                double span_start = a_start < b_start ? a_start : b_start;
                double span_end = a_end > b_end ? a_end : b_end;
                spans[rep] = (span_end - span_start) * 1000.0;
                durA[rep] = (a_end - a_start) * 1000.0;
                durB[rep] = (b_end - b_start) * 1000.0;
            }
            insertion_sort(spans, N_REPS);
            insertion_sort(durA, N_REPS);
            insertion_sort(durB, N_REPS);
            double span_med = percentile_sorted(spans, N_REPS, 0.5);
            if (di == 0) d1_span_med = span_med;
            printf("%-16s %14.4f %14.4f %14.4f %14.4f   (span; durA %.4f / durB %.4f)\n",
                   duals[di].name, span_med,
                   percentile_sorted(spans, N_REPS, 0.1), percentile_sorted(spans, N_REPS, 0.9),
                   span_med / (double)duals[di].total,
                   percentile_sorted(durA, N_REPS, 0.5), percentile_sorted(durB, N_REPS, 0.5));
        }

        double single_marginal = s1_med / 112.0;
        double d1_marginal = d1_span_med / 112.0;
        printf("\nsingle-stream marginal: %.4f ms/dispatch\n", single_marginal);
        printf("D1 aggregate marginal:  %.4f ms/dispatch (speedup vs single: %.3fx)\n", d1_marginal, single_marginal / d1_marginal);
        return 0;
    }
}
