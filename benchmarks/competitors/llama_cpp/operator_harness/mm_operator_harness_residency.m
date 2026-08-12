/* mm_operator_harness_residency.m -- CACHE-RESIDENCY DIFFERENTIAL for the batched-GEMM
 * amortization question (REALRACE_RESULTS.md "Gate 0, follow-up"): llama.cpp's
 * `kernel_mul_mm_f16_f32` gets ~2x cheaper per dispatch when densely batched (GPU-only marginal
 * ~0.207ms/dispatch at N>=8 vs its own isolated ~0.410ms on Aug 7), while Algenta's
 * `_qkv_proj_gemm_mma8x8` shows ZERO such amortization. Two mechanisms remained:
 *
 *   (A) TEMPORAL OVERLAP -- consecutive dispatches pipeline on the GPU; the amortization is a
 *       scheduling effect and does NOT depend on which buffers the dispatches read.
 *   (B) CACHE RESIDENCY -- the 8MB f16 weight slice stays resident in the GPU-side cache across
 *       back-to-back dispatches, so each in-batch dispatch streams far less from DRAM than an
 *       isolated one; the amortization DEPENDS on re-reading the SAME weight bytes.
 *
 * Differential (no per-dispatch timestamps needed -- encoder-level counter sampling is rejected
 * at runtime on AGXG16X/M4 Max, discovered 2026-08-12 via mm_operator_harness_timestamped.m):
 * batch N identical dispatches three ways, all GPU-only-timed over the whole command buffer:
 *
 *   V0 "shared": every dispatch reads the SAME wBuf          (the original batched recipe)
 *   V1 "rot8":   dispatch d reads weight copy d % 8          (64MB rotating working set)
 *   V2 "fresh":  dispatch d reads weight copy d (N copies)   (every dispatch cache-cold:
 *                                                             N=28 -> 224MB, N=112 -> 896MB,
 *                                                             far beyond any SLC/L2 capacity)
 *
 * All weight copies hold IDENTICAL data, so kernel behavior is identical across variants; only
 * cache residency differs. xBuf/yBuf are shared everywhere (the question is the 8MB weight
 * stream, which dominates the per-dispatch traffic). Prediction: if (B), V1 moves toward the
 * isolated cost and V2 lands at it; if (A), all three stay at the V0 marginal.
 *
 * Everything else is byte-for-byte mm_operator_harness_batched.m's setup: same pinned kernel
 * (kernel_mul_mm_f16_f32, FC_MUL_MM=700), same function constants, same real Qwen3-0.6B-Base
 * qkv_proj shape (M=256, K=1024, N=4096), same grid (8x64 threadgroups, 32x4 threads), same
 * SMEM. Correctness of this dispatch recipe was validated by mm_operator_harness_batched.m's N=1
 * CPU-reference sanity check; this file keeps a dispatch-error check only. V0 is re-run at the
 * END of the session as a drift control.
 *
 * MACHINE-STATE DISCLOSURE (2026-08-12): this machine has been up 9 days and its GPU steady
 * state is ~1.8x slower per dispatch than the Aug 7 cooled state the ledger's absolute numbers
 * were taken in (isolated 0.747ms today vs 0.410ms Aug 7, tight p10/p90, reproducible across
 * process launches -- thermal/driver steady state, not a code change; same sources, same
 * Xcode-26.6.0 metal compiler). ONLY same-session ratios within this file are load-bearing;
 * cross-day absolute comparisons are not.
 *
 * Build (same recipe as mm_operator_harness_batched.m):
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -c ../upstream_src/ggml-metal.metal -o /tmp/ggml_mm.air        (skip if already built)
 *   xcrun -sdk macosx metallib /tmp/ggml_mm.air -o /tmp/ggml_mm.metallib                   (skip if already built)
 *   xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src mm_operator_harness_residency.m -o /tmp/mm_operator_harness_residency
 *   /tmp/mm_operator_harness_residency /tmp/ggml_mm.metallib
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

#define N_REPS 10
#define N_REPS_ISOLATED 20

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

/* encode+commit+wait ONE command buffer holding N dispatches; dispatch d reads weight buffer
 * w_pool[d % pool_size]. Returns whole-buffer GPU-only ms, or -1 on error. */
static double run_batch(id<MTLCommandQueue> queue, id<MTLComputePipelineState> pipeline,
                        id<MTLBuffer> __unsafe_unretained const *w_pool, int pool_size,
                        id<MTLBuffer> xBuf, id<MTLBuffer> yBuf,
                        const ggml_metal_kargs_mul_mm *kargs, MTLSize grid, MTLSize tpg,
                        NSUInteger smem, int N) {
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pipeline];
    for (int d = 0; d < N; d++) {
        [enc setBytes:kargs length:sizeof(*kargs) atIndex:0];
        [enc setBuffer:w_pool[d % pool_size] offset:0 atIndex:1];
        [enc setBuffer:xBuf offset:0 atIndex:2];
        [enc setBuffer:yBuf offset:0 atIndex:3];
        [enc setThreadgroupMemoryLength:smem atIndex:0];
        [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
    }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if (cb.error) {
        fprintf(stderr, "batch failed (pool=%d, N=%d): %s\n", pool_size, N,
                cb.error.localizedDescription.UTF8String);
        return -1.0;
    }
    return (cb.GPUEndTime - cb.GPUStartTime) * 1000.0;
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
        const int N_FRESH_MAX = 112;

        uint16_t *w_f16 = malloc(n_w * sizeof(uint16_t));
        for (size_t i = 0; i < n_w; i++) w_f16[i] = f32_to_f16(pseudo((int)(i % 5000003), 41, 0.5f));
        float *x_f32 = malloc(n_x * sizeof(float));
        for (size_t i = 0; i < n_x; i++) x_f32[i] = pseudo((int)(i % 5000003), 59, 0.5f);

        id<MTLBuffer> xBuf = [device newBufferWithBytes:x_f32 length:n_x * sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> yBuf = [device newBufferWithLength:n_y * sizeof(float) options:MTLResourceStorageModeShared];

        /* N_FRESH_MAX identical weight copies (896MB total; every copy the same data) */
        id<MTLBuffer> w_pool[N_FRESH_MAX];
        for (int i = 0; i < N_FRESH_MAX; i++) {
            w_pool[i] = [device newBufferWithBytes:w_f16 length:n_w * sizeof(uint16_t) options:MTLResourceStorageModeShared];
            if (!w_pool[i]) { fprintf(stderr, "weight buffer %d alloc failed\n", i); return 1; }
        }

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

        /* pipeline warmup */
        for (int w = 0; w < 5; w++) {
            if (run_batch(queue, pipeline, w_pool, 1, xBuf, yBuf, &kargs, grid, tpg, SMEM, 1) < 0) return 1;
        }

        /* same-session isolated reference */
        {
            double iso[N_REPS_ISOLATED];
            for (int rep = 0; rep < N_REPS_ISOLATED; rep++) {
                iso[rep] = run_batch(queue, pipeline, w_pool, 1, xBuf, yBuf, &kargs, grid, tpg, SMEM, 1);
                if (iso[rep] < 0) return 1;
            }
            insertion_sort(iso, N_REPS_ISOLATED);
            printf("isolated reference (N=1 x%d): median GPU-only = %.4f ms (p10 %.4f / p90 %.4f)\n",
                   N_REPS_ISOLATED,
                   percentile_sorted(iso, N_REPS_ISOLATED, 0.5),
                   percentile_sorted(iso, N_REPS_ISOLATED, 0.1),
                   percentile_sorted(iso, N_REPS_ISOLATED, 0.9));
        }

        struct variant { const char *name; int pool; int N; };
        struct variant plan[] = {
            {"shared",  1,   28},
            {"rot8",    8,   28},
            {"fresh",   28,  28},
            {"shared",  1,   112},
            {"rot8",    8,   112},
            {"fresh",   112, 112},
            {"shared-again", 1, 28},   /* drift control: same recipe as the first cell */
        };
        int n_plan = (int)(sizeof(plan) / sizeof(plan[0]));

        printf("\n%-14s %4s %14s %16s\n", "variant", "N", "gpu_total_med", "marginal_ms_disp");
        double shared28_med = 0.0;
        double shared28_again_med = 0.0;

        for (int pi = 0; pi < n_plan; pi++) {
            struct variant v = plan[pi];
            double reps[N_REPS];
            for (int rep = 0; rep < N_REPS; rep++) {
                reps[rep] = run_batch(queue, pipeline, w_pool, v.pool, xBuf, yBuf, &kargs, grid, tpg, SMEM, v.N);
                if (reps[rep] < 0) return 1;
            }
            insertion_sort(reps, N_REPS);
            double med = percentile_sorted(reps, N_REPS, 0.5);
            double marginal = med / (double)v.N;
            if (pi == 0) shared28_med = med;
            if (pi == n_plan - 1) shared28_again_med = med;
            printf("%-14s %4d %14.4f %16.4f\n", v.name, v.N, med, marginal);
        }

        printf("\ndrift control: shared-again N=28 total %.4f ms vs shared N=28 total %.4f ms (ratio %.3f)\n",
               shared28_again_med, shared28_med, shared28_again_med / shared28_med);
        return 0;
    }
}
