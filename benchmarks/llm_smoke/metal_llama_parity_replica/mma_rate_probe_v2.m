/* mma_rate_probe_v2.m -- host harness for mma_rate_probe_v2.metal: re-tests the "13.3 TF" wall.
 * PROTOCOL (order matters):
 *   1. COOL phase FIRST: baseline arm timed immediately after process start -- run this binary
 *      only after the machine has idled >=10 min if you want the cool/boost-clock number.
 *   2. Heater: 300 baseline dispatches in one cmdbuf (full DVFS ramp).
 *   3. HOT phase: every variant timed at ramped clocks, median of 3 rounds; plus a GRID sweep of
 *      the baseline (160/320/640/1280) to rule out under-saturation.
 * VERDICT MAP: cool-hot delta = DVFS headroom in the original wall; variant > baseline = the wall
 * is layout-dependent and the prefill GEMM tier has scheduling headroom.
 * Build:
 *   xcrun -sdk macosx metal -c mma_rate_probe_v2.metal -o /tmp/mma_rate_probe_v2.air
 *   xcrun -sdk macosx metallib /tmp/mma_rate_probe_v2.air -o /tmp/mma_rate_probe_v2.metallib
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation mma_rate_probe_v2.m -o /tmp/mma_rate_probe_v2
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>

#define ITER 64
#define REPS 50
#define ROUNDS 3

static uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_MONOTONIC); }

static double time_arm(id<MTLCommandQueue> q, id<MTLComputePipelineState> pl,
                       id<MTLBuffer> dst, id<MTLBuffer> src, int grid, int sg_per_tg, int nacc,
                       double *out_tf) {
    double flops_per_dispatch = (double)grid * (double)sg_per_tg * (double)ITER * (double)nacc * 1024.0;
    double tf[ROUNDS];
    for (int r = 0; r < ROUNDS; r++) {
        uint64_t t0 = now_ns();
        id<MTLCommandBuffer> cb = [q commandBuffer];
        for (int i = 0; i < REPS; i++) {
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc useResource:dst usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
            [enc useResource:src usage:MTLResourceUsageRead];
            [enc setComputePipelineState:pl];
            [enc setBuffer:dst offset:0 atIndex:0];
            [enc setBuffer:src offset:0 atIndex:1];
            [enc dispatchThreadgroups:MTLSizeMake(grid, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(sg_per_tg * 32, 1, 1)];
            [enc endEncoding];
        }
        [cb commit];
        [cb waitUntilCompleted];
        uint64_t t1 = now_ns();
        double sec = (double)(t1 - t0) / 1e9 / REPS;
        tf[r] = flops_per_dispatch / sec / 1e12;
    }
    /* median of 3 = sum - max - min */
    double hi = tf[0]; for (int r = 1; r < ROUNDS; r++) if (tf[r] > hi) hi = tf[r];
    double lo = tf[0]; for (int r = 1; r < ROUNDS; r++) if (tf[r] < lo) lo = tf[r];
    *out_tf = tf[0] + tf[1] + tf[2] - hi - lo;
    return *out_tf;
}

int main(void) {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no device\n"); return 1; }
        id<MTLCommandQueue> q = [dev newCommandQueue];
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithURL:[NSURL fileURLWithPath:@"/tmp/mma_rate_probe_v2.metallib"] error:&err];
        if (!lib) { fprintf(stderr, "lib load failed: %s\n", err.localizedDescription.UTF8String); return 1; }
        id<MTLComputePipelineState> p_base  = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"mma_v2_reg"] error:&err];
        id<MTLComputePipelineState> p_n16   = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"mma_v2_reg_nacc16"] error:&err];
        id<MTLComputePipelineState> p_sg8   = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"mma_v2_reg_sg8"] error:&err];
        id<MTLComputePipelineState> p_sg16  = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"mma_v2_reg_sg8_nacc16"] error:&err];
        if (!p_base || !p_n16 || !p_sg8 || !p_sg16) { fprintf(stderr, "pipeline failed: %s\n", err.localizedDescription.UTF8String); return 1; }

        int grid_max = 1280;
        id<MTLBuffer> dst = [dev newBufferWithLength:(NSUInteger)(grid_max * 16 * 64 * 4) options:MTLResourceStorageModeShared];
        id<MTLBuffer> src = [dev newBufferWithLength:128 * 2 options:MTLResourceStorageModeShared];
        _Float16 *sh = (_Float16 *)src.contents;
        for (int i = 0; i < 128; i++) sh[i] = (_Float16)(0.01 * ((i % 5) - 2));

        double tf = 0;
        printf("== COOL phase (run after >=10min idle for the boost-clock number) ==\n");
        time_arm(q, p_base, dst, src, 320, 4, 8, &tf);
        printf("  baseline (GRID=320, 4sg, NACC=8):      %6.2f TF/s\n", tf);
        double cool_base = tf;

        printf("== heater: 300 baseline dispatches ==\n");
        {
            id<MTLCommandBuffer> cb = [q commandBuffer];
            for (int i = 0; i < 300; i++) {
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc useResource:dst usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
                [enc useResource:src usage:MTLResourceUsageRead];
                [enc setComputePipelineState:p_base];
                [enc setBuffer:dst offset:0 atIndex:0];
                [enc setBuffer:src offset:0 atIndex:1];
                [enc dispatchThreadgroups:MTLSizeMake(320, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
                [enc endEncoding];
            }
            [cb commit];
            [cb waitUntilCompleted];
        }

        printf("== HOT phase (ramped clocks -- the original wall's condition) ==\n");
        time_arm(q, p_base, dst, src, 320, 4, 8, &tf);
        printf("  baseline (GRID=320, 4sg, NACC=8):      %6.2f TF/s   (vs cool %+.1f%%)\n",
               tf, (tf / cool_base - 1.0) * 100.0);
        double hot_base = tf;
        time_arm(q, p_n16, dst, src, 320, 4, 16, &tf);
        printf("  NACC=16  (GRID=320, 4sg):              %6.2f TF/s   (vs hot baseline %+.1f%%)\n",
               tf, (tf / hot_base - 1.0) * 100.0);
        time_arm(q, p_sg8, dst, src, 320, 8, 8, &tf);
        printf("  sg8      (GRID=320, 8sg, NACC=8):      %6.2f TF/s   (vs hot baseline %+.1f%%)\n",
               tf, (tf / hot_base - 1.0) * 100.0);
        time_arm(q, p_sg16, dst, src, 320, 8, 16, &tf);
        printf("  sg8+N16  (GRID=320, 8sg, NACC=16):     %6.2f TF/s   (vs hot baseline %+.1f%%)\n",
               tf, (tf / hot_base - 1.0) * 100.0);

        printf("== GRID sweep (baseline, hot) ==\n");
        int grids[4] = {160, 320, 640, 1280};
        for (int g = 0; g < 4; g++) {
            time_arm(q, p_base, dst, src, grids[g], 4, 8, &tf);
            printf("  GRID=%-5d                              %6.2f TF/s\n", grids[g], tf);
        }
        return 0;
    }
}
