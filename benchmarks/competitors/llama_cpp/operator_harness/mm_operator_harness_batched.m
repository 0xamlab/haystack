/* mm_operator_harness_batched.m -- test whether the ~0.152ms wall-vs-GPU gap seen in
 * mm_operator_harness.m's isolated single-dispatch L0 timing (median wall=0.562ms, GPU-only
 * median=0.410ms, N_TIMING_RUNS=200) is mostly ONE-TIME fixed overhead paid once per
 * MTLCommandBuffer (queue/encoder/commit/wait bookkeeping), not once per dispatchThreadgroups
 * call -- matching real ggml-metal graph-execution practice, where one MTLCommandBuffer holds
 * many dispatches on a shared MTLComputeCommandEncoder before a single endEncoding/commit/wait.
 *
 * This file does NOT modify mm_operator_harness.m. It reuses the exact same pinned kernel
 * (`kernel_mul_mm_f16_f32`, FC_MUL_MM=700, same kargs struct, same buffers, same qkv_proj shape
 * M=256/K=1024/N=4096, same function-constant values bc_inp=bc_out=false) and the exact same
 * per-run timing convention (CFAbsoluteTimeGetCurrent() wall-clock wrapped tightly around
 * commit+waitUntilCompleted, GPUStartTime/GPUEndTime for GPU-only) -- the only change is that N
 * identical dispatchThreadgroups calls are encoded onto ONE shared MTLComputeCommandEncoder
 * inside ONE MTLCommandBuffer before the single endEncoding/commit/waitUntilCompleted, instead of
 * one dispatch per command buffer. All N dispatches read the same wBuf/xBuf and write the SAME
 * yBuf/kargs (last-writer-wins on overlapping output) -- output correctness across repeats is
 * explicitly out of scope per the task brief; only timing is measured here. The one-time
 * correctness check (worst abs/rel delta vs the CPU Float64 reference) is still run once at N=1
 * before any timing sweep, to confirm this file dispatches the identical real kernel the base
 * harness already validated.
 *
 * Sweeps N over {1,2,4,8,16,28,56,112} (28 = real transformer depth of Qwen3-0.6B-Base, so N=28
 * is what one GEMM role's worth of dispatches across all layers would look like batched into one
 * command buffer; 112 = 28*4, one command buffer holding all 4 GEMM roles x all 28 layers).
 * For each N: 30 warm repetitions of {build fresh command buffer, encode N dispatches on one
 * encoder, endEncoding, commit, waitUntilCompleted}; report median/p10/p90 TOTAL wall ms and
 * GPU-only ms (GPUEndTime-GPUStartTime for the whole batched command buffer, i.e. all N dispatches
 * combined, not per-dispatch) for that N.
 *
 * Build:
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -c ../upstream_src/ggml-metal.metal -o /tmp/ggml_mm.air        (skip if already built)
 *   xcrun -sdk macosx metallib /tmp/ggml_mm.air -o /tmp/ggml_mm.metallib                   (skip if already built)
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src mm_operator_harness_batched.m -o /tmp/mm_operator_harness_batched
 *   /tmp/mm_operator_harness_batched /tmp/ggml_mm.metallib
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ggml-metal-impl.h"

/* real Qwen3-0.6B-Base qkv_proj shape at m_rows=256 (prefill), identical to mm_operator_harness.m */
#define M_ROWS 256
#define K_DIM  1024
#define N_DIM  4096

#define N_WARM_REPS 50
static const int N_VALUES[] = {1, 2, 4, 8, 16, 28, 56, 112};
#define N_SWEEP (int)(sizeof(N_VALUES) / sizeof(N_VALUES[0]))
#define N_MAX 112

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

static float f16_to_f32(uint16_t h) {
    uint32_t sign = (uint32_t)(h & 0x8000) << 16;
    uint32_t exp = (h >> 10) & 0x1F;
    uint32_t mant = h & 0x3FF;
    uint32_t bits;
    if (exp == 0) {
        if (mant == 0) { bits = sign; }
        else {
            int e = -1;
            do { mant <<= 1; e++; } while (!(mant & 0x400));
            mant &= 0x3FF;
            bits = sign | (uint32_t)((127 - 15 - e) << 23) | (mant << 13);
        }
    } else if (exp == 31) {
        bits = sign | 0x7F800000 | (mant << 13);
    } else {
        bits = sign | ((exp - 15 + 127) << 23) | (mant << 13);
    }
    float f;
    memcpy(&f, &bits, 4);
    return f;
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
        BOOL bc_inp = NO, bc_out = NO;              /* K%32==0, N%64==0 && M%32==0: exact tile fit */
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

        /* ---- data (identical layout to mm_operator_harness.m) ---- */
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
        { float *yp = (float *)yBuf.contents; for (size_t i = 0; i < n_y; i++) yp[i] = -999.0f; }

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
        const NSUInteger SMEM = 4096 + 2048; /* bc_out=false, non-tensor path */
        MTLSize grid = MTLSizeMake((M_ROWS + NR1 - 1) / NR1, (N_DIM + NR0 - 1) / NR0, 1);
        MTLSize tpg  = MTLSizeMake(32, 4, 1); /* nsg = N_MM_SIMD_GROUP_X*N_MM_SIMD_GROUP_Y = 2*2 = 4 */

        /* ---- one-time correctness sanity check at N=1: identical single dispatch to
         * mm_operator_harness.m, confirming this file drives the same real, already-validated
         * kernel before any timing sweep runs. ---- */
        {
            id<MTLCommandBuffer> cmdBuf = [queue commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cmdBuf computeCommandEncoder];
            [enc setComputePipelineState:pipeline];
            [enc setBytes:&kargs length:sizeof(kargs) atIndex:0];
            [enc setBuffer:wBuf offset:0 atIndex:1];
            [enc setBuffer:xBuf offset:0 atIndex:2];
            [enc setBuffer:yBuf offset:0 atIndex:3];
            [enc setThreadgroupMemoryLength:SMEM atIndex:0];
            [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
            [enc endEncoding];
            [cmdBuf commit];
            [cmdBuf waitUntilCompleted];
            if (cmdBuf.error) {
                fprintf(stderr, "sanity dispatch failed: %s\n", cmdBuf.error.localizedDescription.UTF8String);
                return 1;
            }

            double *w_f64 = malloc(n_w * sizeof(double));
            for (size_t i = 0; i < n_w; i++) w_f64[i] = (double)f16_to_f32(w_f16[i]);
            float *y = (float *)yBuf.contents;
            double worst_abs = 0.0, worst_rel = 0.0;
            for (int m = 0; m < M_ROWS; m++) {
                const float *xrow = x_f32 + (size_t)m * K_DIM;
                for (int n = 0; n < N_DIM; n++) {
                    const double *wrow = w_f64 + (size_t)n * K_DIM;
                    double acc = 0.0;
                    for (int k = 0; k < K_DIM; k++) acc += (double)xrow[k] * wrow[k];
                    float got = y[(size_t)m * N_DIM + n];
                    double diff = fabs(acc - (double)got);
                    double rel = diff / fmax(1.0, fabs(acc));
                    if (diff > worst_abs) worst_abs = diff;
                    if (rel > worst_rel) worst_rel = rel;
                }
            }
            free(w_f64);
            double tol = 1.0e-2;
            printf("sanity check (N=1, same kernel/buffers/kargs as mm_operator_harness.m): worst abs=%.9f worst rel=%.9f -> %s\n",
                   worst_abs, worst_rel, worst_rel < tol ? "PASS" : "FAIL");
            if (worst_rel >= tol) return 1;
        }

        /* ---- warmup the pipeline/queue itself before the sweep (avoid first-ever-dispatch
         * JIT/driver warmup noise contaminating the smallest N in the sweep) ---- */
        for (int w = 0; w < 5; w++) {
            id<MTLCommandBuffer> cmdBuf = [queue commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cmdBuf computeCommandEncoder];
            [enc setComputePipelineState:pipeline];
            [enc setBytes:&kargs length:sizeof(kargs) atIndex:0];
            [enc setBuffer:wBuf offset:0 atIndex:1];
            [enc setBuffer:xBuf offset:0 atIndex:2];
            [enc setBuffer:yBuf offset:0 atIndex:3];
            [enc setThreadgroupMemoryLength:SMEM atIndex:0];
            [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
            [enc endEncoding];
            [cmdBuf commit];
            [cmdBuf waitUntilCompleted];
        }

        printf("\nbatched sweep: N identical kernel_mul_mm_f16_f32 dispatches on ONE shared "
               "MTLComputeCommandEncoder / ONE MTLCommandBuffer, %d warm reps per N\n", N_WARM_REPS);
        printf("%-6s %12s %12s %12s %14s %16s\n", "N", "wall_med_ms", "wall_p10_ms", "wall_p90_ms", "gpu_only_ms", "gpu_per_disp_ms");

        double result_wall_med[N_SWEEP], result_wall_p10[N_SWEEP], result_wall_p90[N_SWEEP], result_gpu[N_SWEEP];

        for (int si = 0; si < N_SWEEP; si++) {
            int N = N_VALUES[si];
            double gpu_ms[N_WARM_REPS];
            double wall_ms[N_WARM_REPS];

            for (int rep = 0; rep < N_WARM_REPS; rep++) {
                CFAbsoluteTime t0 = CFAbsoluteTimeGetCurrent();
                id<MTLCommandBuffer> tcb = [queue commandBuffer];
                id<MTLComputeCommandEncoder> tenc = [tcb computeCommandEncoder];
                [tenc setComputePipelineState:pipeline];
                for (int d = 0; d < N; d++) {
                    [tenc setBytes:&kargs length:sizeof(kargs) atIndex:0];
                    [tenc setBuffer:wBuf offset:0 atIndex:1];
                    [tenc setBuffer:xBuf offset:0 atIndex:2];
                    [tenc setBuffer:yBuf offset:0 atIndex:3];
                    [tenc setThreadgroupMemoryLength:SMEM atIndex:0];
                    [tenc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
                }
                [tenc endEncoding];
                [tcb commit];
                [tcb waitUntilCompleted];
                CFAbsoluteTime t1 = CFAbsoluteTimeGetCurrent();

                if (tcb.error) {
                    fprintf(stderr, "batched dispatch failed at N=%d rep=%d: %s\n", N, rep, tcb.error.localizedDescription.UTF8String);
                    return 1;
                }

                gpu_ms[rep] = (tcb.GPUEndTime - tcb.GPUStartTime) * 1000.0;
                wall_ms[rep] = (t1 - t0) * 1000.0;
            }

            insertion_sort(gpu_ms, N_WARM_REPS);
            insertion_sort(wall_ms, N_WARM_REPS);

            double wall_med = percentile_sorted(wall_ms, N_WARM_REPS, 0.5);
            double wall_p10 = percentile_sorted(wall_ms, N_WARM_REPS, 0.1);
            double wall_p90 = percentile_sorted(wall_ms, N_WARM_REPS, 0.9);
            double gpu_med  = percentile_sorted(gpu_ms,  N_WARM_REPS, 0.5);

            result_wall_med[si] = wall_med;
            result_wall_p10[si] = wall_p10;
            result_wall_p90[si] = wall_p90;
            result_gpu[si] = gpu_med;

            printf("%-6d %12.4f %12.4f %12.4f %14.4f %16.4f\n",
                   N, wall_med, wall_p10, wall_p90, gpu_med, gpu_med / (double)N);
        }

        printf("\nRAW_TABLE_M: [");
        for (int si = 0; si < N_SWEEP; si++) {
            printf("%s[%d,%.4f,%.4f,%.4f,%.4f]", si == 0 ? "" : ",",
                   N_VALUES[si], result_wall_med[si], result_wall_p10[si], result_wall_p90[si], result_gpu[si]);
        }
        printf("]\n");

        return 0;
    }
}
