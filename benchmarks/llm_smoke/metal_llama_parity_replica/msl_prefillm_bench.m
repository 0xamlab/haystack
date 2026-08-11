/* msl_prefillm_bench.m -- beat-llama.cpp campaign (2026-08-11, n_splits ceiling-sweep day):
 * the PRODUCTION MSL-parity GEMM tier at PREFILL M. The batched-decode batchsweep bench measured
 * these kernels at M=32..1024 (the batched-decode regime); the three-way load-test prefill runs
 * M=1024/4096/8192, where the roofline decomposition put ~69% of 4K and ~62% of 8K prefill wall
 * in GEMM+other -- and production wires the split-K accum kernels (o_proj S=8, down_proj S=12,
 * designed as the SMALL-M GPU-fill fix, validated only at M<=512) at EVERY M because their gate
 * is on the K dimension divisibility, never on m_rows. This bench settles, by measurement:
 *   1. parity qkv / swiglu TFLOP/s at M=256..8192 (how close to the 13.3 TF MMA wall?), and
 *   2. parity accum vs splitk8 (o_proj shape) and splitk12 (down_proj shape) head-to-head at
 *      each M -- does the small-M GPU-fill fix actively LOSE once the plain grid already fills
 *      the 40 cores?
 * Timing discipline identical to msl_batchsweep_bench.m: batched reps in ONE command buffer,
 * DVFS heater before anything is timed, per-shape re-heat, 3 rounds, median. TIMING ONLY --
 * both kernel families are correctness-gated elsewhere (the splitk bench's accum-semantics gate,
 * the parity suite's oracle gates); the large-M path is the same tiled code, more tiles.
 *
 * Build:
 *   cd benchmarks/llm_smoke/metal_llama_parity_replica
 *   xcrun -sdk macosx metal -c msl_parity_qkv_proj_mul_mm.metal -o /tmp/pfbench_qkv.air
 *   xcrun -sdk macosx metallib /tmp/pfbench_qkv.air -o /tmp/pfbench_qkv.metallib
 *   xcrun -sdk macosx metal -c msl_parity_swiglu_mul_mm.metal -o /tmp/pfbench_swiglu.air
 *   xcrun -sdk macosx metallib /tmp/pfbench_swiglu.air -o /tmp/pfbench_swiglu.metallib
 *   xcrun -sdk macosx metal -c msl_parity_gemm_accum_mul_mm.metal -o /tmp/pfbench_accum.air
 *   xcrun -sdk macosx metallib /tmp/pfbench_accum.air -o /tmp/pfbench_accum.metallib
 *   xcrun -sdk macosx metal -c msl_splitk_accum.metal -o /tmp/pfbench_splitk.air
 *   xcrun -sdk macosx metallib /tmp/pfbench_splitk.air -o /tmp/pfbench_splitk.metallib
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation msl_prefillm_bench.m -o /tmp/msl_prefillm_bench
 *   /tmp/msl_prefillm_bench
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>

#define REPS 20
#define ROUNDS 3

static uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_MONOTONIC); }

static int load_lib(id<MTLDevice> dev, NSString *path, id<MTLLibrary> *out) {
    NSError *err = nil;
    *out = [dev newLibraryWithURL:[NSURL fileURLWithPath:path] error:&err];
    if (!*out) { fprintf(stderr, "library load failed for %s: %s\n", path.UTF8String, err.localizedDescription.UTF8String); return -1; }
    return 0;
}

static int make_pipeline(id<MTLDevice> dev, id<MTLLibrary> lib, NSString *name, id<MTLComputePipelineState> *out) {
    NSError *err = nil;
    id<MTLFunction> fn = [lib newFunctionWithName:name];
    if (!fn) { fprintf(stderr, "function %s not found\n", name.UTF8String); return -1; }
    *out = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!*out) { fprintf(stderr, "pipeline failed for %s: %s\n", name.UTF8String, err.localizedDescription.UTF8String); return -1; }
    return 0;
}

static void dispatch_gemm(id<MTLComputeCommandEncoder> enc, id<MTLComputePipelineState> pl,
                          id<MTLBuffer> dst, id<MTLBuffer> x, id<MTLBuffer> w,
                          int64_t m_rows, int64_t k, int64_t n, int grid_x) {
    [enc useResource:dst usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
    [enc useResource:x usage:MTLResourceUsageRead];
    [enc useResource:w usage:MTLResourceUsageRead];
    [enc setComputePipelineState:pl];
    uint64_t y_addr = [dst gpuAddress];
    uint64_t x_addr = [x gpuAddress];
    uint64_t w_addr = [w gpuAddress];
    uint64_t dummy = 0;
    [enc setBytes:&y_addr length:8 atIndex:0];
    [enc setBytes:&x_addr length:8 atIndex:1];
    [enc setBytes:&w_addr length:8 atIndex:2];
    [enc setBytes:&dummy length:8 atIndex:3];
    [enc setBytes:&m_rows length:8 atIndex:4];
    [enc setBytes:&k length:8 atIndex:5];
    [enc setBytes:&n length:8 atIndex:6];
    [enc dispatchThreadgroups:MTLSizeMake(grid_x, 1, 1)
        threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
}

struct Role {
    const char *label;
    NSString *lib_path;
    NSString *kernel;
    int64_t K, N;
    int S;        /* split factor: 1 = plain parity grid */
    int w_is_gu;  /* swiglu: weight buffer is [2*N, K] halves */
};

int main(void) {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no device\n"); return 1; }
        id<MTLCommandQueue> q = [dev newCommandQueue];

        struct Role roles[6] = {
            {"qkv parity   ", @"/tmp/pfbench_qkv.metallib",     @"msl_parity__qkv_proj_mul_mm_f16_f32", 1024, 4096, 1, 0},
            {"swiglu parity", @"/tmp/pfbench_swiglu.metallib",  @"msl_parity__swiglu_mul_mm_f16_f32",   1024, 3072, 1, 1},
            {"o parity     ", @"/tmp/pfbench_accum.metallib",   @"msl_parity__gemm_accum_mul_mm_f16_f32", 2048, 1024, 1, 0},
            {"o splitk8    ", @"/tmp/pfbench_splitk.metallib",  @"msl_splitk8__gemm_accum_mul_mm_f16_f32", 2048, 1024, 8, 0},
            {"down parity  ", @"/tmp/pfbench_accum.metallib",   @"msl_parity__gemm_accum_mul_mm_f16_f32", 3072, 1024, 1, 0},
            {"down splitk12", @"/tmp/pfbench_splitk.metallib",  @"msl_splitk12__gemm_accum_mul_mm_f16_f32", 3072, 1024, 12, 0},
        };
        id<MTLComputePipelineState> pls[6];
        for (int r = 0; r < 6; r++) {
            id<MTLLibrary> lib;
            if (load_lib(dev, roles[r].lib_path, &lib)) return 1;
            id<MTLComputePipelineState> pl_r;
            if (make_pipeline(dev, lib, roles[r].kernel, &pl_r)) return 1;
            pls[r] = pl_r;
        }

        int64_t Ms[5] = {256, 1024, 2048, 4096, 8192};
        const int nM = 5;

        /* DVFS heater: 300 dispatches of a mid prefill shape before anything is timed. */
        {
            const int64_t Mh = 2048, Kh = 1024, Nh = 4096;
            id<MTLBuffer> x = [dev newBufferWithLength:(NSUInteger)(Mh * Kh * 4) options:MTLResourceStorageModeShared];
            id<MTLBuffer> w = [dev newBufferWithLength:(NSUInteger)(Nh * Kh * 2) options:MTLResourceStorageModeShared];
            id<MTLBuffer> d = [dev newBufferWithLength:(NSUInteger)(Mh * Nh * 4) options:MTLResourceStorageModeShared];
            id<MTLCommandBuffer> cb = [q commandBuffer];
            for (int i = 0; i < 300; i++) {
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                dispatch_gemm(enc, pls[0], d, x, w, Mh, Kh, Nh, (int)((Mh / 32) * (Nh / 64)));
                [enc endEncoding];
            }
            [cb commit]; [cb waitUntilCompleted];
            printf("heater done\n");
        }

        printf("%14s %8s %12s %12s %12s\n", "role", "M(rows)", "ms/dispatch", "TFLOP/s", "grid(tg)");
        for (int r = 0; r < 6; r++) {
            int64_t K = roles[r].K, N = roles[r].N;
            int S = roles[r].S;
            for (int s = 0; s < nM; s++) {
                int64_t M = Ms[s];
                id<MTLBuffer> x = [dev newBufferWithLength:(NSUInteger)(M * K * 4) options:MTLResourceStorageModeShared];
                uint64_t w_elems = (roles[r].w_is_gu ? 2 * N : N) * K;
                id<MTLBuffer> w = [dev newBufferWithLength:(NSUInteger)(w_elems * 2) options:MTLResourceStorageModeShared];
                id<MTLBuffer> d = [dev newBufferWithLength:(NSUInteger)(M * N * 4) options:MTLResourceStorageModeShared];
                int grid = (int)((M / 32) * (N / 64) * S);
                double gf = 2.0 * M * K * N / 1e9;
                double med[ROUNDS];
                /* per-shape re-heat */
                id<MTLCommandBuffer> hcb = [q commandBuffer];
                for (int i = 0; i < 50; i++) {
                    id<MTLComputeCommandEncoder> enc = [hcb computeCommandEncoder];
                    dispatch_gemm(enc, pls[r], d, x, w, M, K, N, grid);
                    [enc endEncoding];
                }
                [hcb commit]; [hcb waitUntilCompleted];
                for (int rr = 0; rr < ROUNDS; rr++) {
                    uint64_t t0 = now_ns();
                    id<MTLCommandBuffer> cb = [q commandBuffer];
                    for (int i = 0; i < REPS; i++) {
                        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                        dispatch_gemm(enc, pls[r], d, x, w, M, K, N, grid);
                        [enc endEncoding];
                    }
                    [cb commit]; [cb waitUntilCompleted];
                    uint64_t t1 = now_ns();
                    med[rr] = (double)(t1 - t0) / 1e9 / REPS * 1e3; /* ms/dispatch */
                }
                /* median of 3 rounds = sum - max - min */
                double mx = med[0] > med[1] ? (med[0] > med[2] ? med[0] : med[2]) : (med[1] > med[2] ? med[1] : med[2]);
                double mn = med[0] < med[1] ? (med[0] < med[2] ? med[0] : med[2]) : (med[1] < med[2] ? med[1] : med[2]);
                double ms = med[0] + med[1] + med[2] - mx - mn;
                double tf = gf / (ms / 1e3) / 1e3;
                printf("%14s %8lld %12.4f %12.2f %12d\n", roles[r].label, M, ms, tf, grid);
            }
        }
        return 0;
    }
}
