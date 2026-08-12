/* mm_operator_harness_timestamped.m -- per-DISPATCH GPU timestamps INSIDE llama.cpp's batched
 * qkv_proj GEMM stream, built to settle the one open mechanistic question the GEMM tournament
 * could not (REALRACE_RESULTS.md, "Gate 0, follow-up" + "F1 sector reframing" entries): WHY does
 * llama.cpp's `kernel_mul_mm_f16_f32` get ~2x cheaper per dispatch when densely batched into one
 * command buffer (GPU-only marginal ~0.207ms/dispatch at N>=8 vs its OWN isolated ~0.410ms),
 * while Algenta's `_qkv_proj_gemm_mma8x8` shows ZERO such amortization (batched marginal ~0.596ms
 * == its own isolated ~0.565ms)? Two mutually-exclusive candidate mechanisms remain after the
 * tournament ruled out CPU-encoding overhead (wall-minus-GPU gap flat), tile shape, operand width,
 * datatype, and single-axis traffic cuts (BM64/BN64 ~9% floors):
 *
 *   (A) TEMPORAL OVERLAP -- consecutive dispatches pipeline on the GPU (dispatch d+1's wave
 *       launches while dispatch d's tail drains), so the command buffer's GPU span is LESS than
 *       the sum of per-dispatch durations. If true, sum(per-dispatch) / buffer-total > 1.
 *   (B) CACHE RESIDENCY -- each dispatch still runs alone, but back-to-back dispatching keeps the
 *       8MB f16 weight slice resident in the GPU-side cache, so each in-batch dispatch is
 *       intrinsically ~2x faster than an isolated one (which pays a cold-ish DRAM stream). If true,
 *       sum(per-dispatch) ~= buffer-total AND steady-state per-dispatch duration ~= 0.2ms.
 *
 * The instrument is Metal's own timestamp counter sampling (`MTLCommonCounterSetTimestamp` via a
 * `MTLCounterSampleBuffer`, `sampleCountersInBuffer:atSampleIndex:withBarrier:NO` around every
 * dispatch -- withBarrier:NO so the samples do NOT insert pipeline barriers and the natural
 * scheduling is undisturbed), read back via `resolveCounterRange:` after waitUntilCompleted.
 * Timestamps are cross-checked against the same command buffer's GPUEndTime-GPUStartTime so the
 * unit/scale agreement is visible in the output itself (sum-of-per-dispatch vs buffer total).
 *
 * Everything else is byte-for-byte `mm_operator_harness_batched.m`'s setup: same pinned kernel
 * (kernel_mul_mm_f16_f32, FC_MUL_MM=700), same function constants (bc_inp=bc_out=false, ne12=ne13=
 * r2=r3=1), same real Qwen3-0.6B-Base qkv_proj shape (M=256, K=1024, N=4096), same buffers, same
 * grid ((M+31)/32 x (N+63)/64 = 8x64 threadgroups, 32x4 threads, nsg=4), same SMEM=4096+2048.
 * This file does NOT modify mm_operator_harness.m or mm_operator_harness_batched.m; correctness of
 * this exact dispatch recipe was already validated by mm_operator_harness_batched.m's own N=1
 * sanity check against the CPU Float64 reference, so this file keeps only a dispatch-error check.
 *
 * Protocol (thermal discipline, matching the ledger's warm-vs-warm convention): 5 pipeline warmup
 * dispatches, then for each N in {8, 28, 112}: 10 UNinstrumented reps (median GPU-only total, to
 * reproduce the ~0.207ms/dispatch marginal in THIS session before trusting the instrumented
 * numbers), then 15 instrumented reps (per-dispatch timestamps + buffer total). Separately, 20
 * isolated single-dispatch command buffers for the same-session isolated reference. Per-dispatch
 * durations are reported as: dispatch 0 median (cache-ramp start), dispatch 1 median, and the
 * steady-state median (all durations at index >= N/2 pooled across reps), plus the overlap ratio
 * sum(per-index medians) / instrumented-buffer-total.
 *
 * Build (same recipe as mm_operator_harness_batched.m):
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -c ../upstream_src/ggml-metal.metal -o /tmp/ggml_mm.air        (skip if already built)
 *   xcrun -sdk macosx metallib /tmp/ggml_mm.air -o /tmp/ggml_mm.metallib                   (skip if already built)
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src mm_operator_harness_timestamped.m -o /tmp/mm_operator_harness_timestamped
 *   /tmp/mm_operator_harness_timestamped /tmp/ggml_mm.metallib
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <Metal/MTLCounters.h> /* not always pulled in by the umbrella header on every SDK vintage */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ggml-metal-impl.h"

#define M_ROWS 256
#define K_DIM  1024
#define N_DIM  4096

static const int N_BATCHES[] = {8, 28, 112};
#define N_SWEEP (int)(sizeof(N_BATCHES) / sizeof(N_BATCHES[0]))
#define N_REPS_UNINSTR 10
#define N_REPS_INSTR 15
#define N_REPS_ISOLATED 20
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

        id<MTLCounterSet> ts_counter_set = nil;
        BOOL counters_supported = [device supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary];
        if (counters_supported) {
            for (id<MTLCounterSet> cs in device.counterSets) {
                if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts_counter_set = cs; break; }
            }
        }
        if (!ts_counter_set) {
            /* AGXG16X (M4 Max) advertises the timestamp counter set but REJECTS encoder-level
             * sampling at runtime ("not supported on this device") -- discovered 2026-08-12, now
             * guarded: fall through to the uninstrumented sweep only, which still yields the
             * same-session isolated-vs-batched comparison. */
            fprintf(stderr, "note: encoder-level counter sampling unavailable on this device -- "
                            "running uninstrumented sweep only\n");
        }

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

        /* pipeline warmup, identical to mm_operator_harness_batched.m's own */
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

        /* ---- same-session isolated reference: 20 single-dispatch command buffers ---- */
        {
            double iso_gpu[N_REPS_ISOLATED];
            for (int rep = 0; rep < N_REPS_ISOLATED; rep++) {
                id<MTLCommandBuffer> cb = [queue commandBuffer];
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc setComputePipelineState:pipeline];
                [enc setBytes:&kargs length:sizeof(kargs) atIndex:0];
                [enc setBuffer:wBuf offset:0 atIndex:1];
                [enc setBuffer:xBuf offset:0 atIndex:2];
                [enc setBuffer:yBuf offset:0 atIndex:3];
                [enc setThreadgroupMemoryLength:SMEM atIndex:0];
                [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
                [enc endEncoding];
                [cb commit];
                [cb waitUntilCompleted];
                if (cb.error) { fprintf(stderr, "isolated dispatch failed rep=%d: %s\n", rep, cb.error.localizedDescription.UTF8String); return 1; }
                iso_gpu[rep] = (cb.GPUEndTime - cb.GPUStartTime) * 1000.0;
            }
            insertion_sort(iso_gpu, N_REPS_ISOLATED);
            printf("isolated reference (same session, N=1 x%d): median GPU-only = %.4f ms (p10 %.4f / p90 %.4f)\n",
                   N_REPS_ISOLATED,
                   percentile_sorted(iso_gpu, N_REPS_ISOLATED, 0.5),
                   percentile_sorted(iso_gpu, N_REPS_ISOLATED, 0.1),
                   percentile_sorted(iso_gpu, N_REPS_ISOLATED, 0.9));
        }

        for (int si = 0; si < N_SWEEP; si++) {
            int N = N_BATCHES[si];

            /* uninstrumented reps first: reproduce the batched marginal in THIS session */
            double uninstr_gpu[N_REPS_UNINSTR];
            for (int rep = 0; rep < N_REPS_UNINSTR; rep++) {
                id<MTLCommandBuffer> cb = [queue commandBuffer];
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc setComputePipelineState:pipeline];
                for (int d = 0; d < N; d++) {
                    [enc setBytes:&kargs length:sizeof(kargs) atIndex:0];
                    [enc setBuffer:wBuf offset:0 atIndex:1];
                    [enc setBuffer:xBuf offset:0 atIndex:2];
                    [enc setBuffer:yBuf offset:0 atIndex:3];
                    [enc setThreadgroupMemoryLength:SMEM atIndex:0];
                    [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
                }
                [enc endEncoding];
                [cb commit];
                [cb waitUntilCompleted];
                if (cb.error) { fprintf(stderr, "uninstrumented batch failed N=%d rep=%d: %s\n", N, rep, cb.error.localizedDescription.UTF8String); return 1; }
                uninstr_gpu[rep] = (cb.GPUEndTime - cb.GPUStartTime) * 1000.0;
            }
            insertion_sort(uninstr_gpu, N_REPS_UNINSTR);
            double uninstr_med = percentile_sorted(uninstr_gpu, N_REPS_UNINSTR, 0.5);

            printf("\nN=%d: uninstrumented GPU-total median %.4f ms (marginal %.4f ms/dispatch)\n",
                   N, uninstr_med, uninstr_med / (double)N);
            if (!ts_counter_set) { continue; }

            /* instrumented reps: timestamp samples at boundaries 0..N, withBarrier:NO */
            MTLCounterSampleBufferDescriptor *sbd = [MTLCounterSampleBufferDescriptor new];
            sbd.counterSet = ts_counter_set;
            sbd.sampleCount = (NSUInteger)(N + 1);
            sbd.storageMode = MTLStorageModeShared;
            NSError *sberr = nil;
            id<MTLCounterSampleBuffer> sbuf = [device newCounterSampleBufferWithDescriptor:sbd error:&sberr];
            if (!sbuf) {
                fprintf(stderr, "counter sample buffer creation failed for N=%d: %s\n", N, sberr.localizedDescription.UTF8String);
                return 1;
            }

            double instr_total[N_REPS_INSTR];
            double per_disp[N_REPS_INSTR][N_MAX];
            for (int rep = 0; rep < N_REPS_INSTR; rep++) {
                id<MTLCommandBuffer> cb = [queue commandBuffer];
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc setComputePipelineState:pipeline];
                [enc sampleCountersInBuffer:sbuf atSampleIndex:0 withBarrier:NO];
                for (int d = 0; d < N; d++) {
                    [enc setBytes:&kargs length:sizeof(kargs) atIndex:0];
                    [enc setBuffer:wBuf offset:0 atIndex:1];
                    [enc setBuffer:xBuf offset:0 atIndex:2];
                    [enc setBuffer:yBuf offset:0 atIndex:3];
                    [enc setThreadgroupMemoryLength:SMEM atIndex:0];
                    [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
                    [enc sampleCountersInBuffer:sbuf atSampleIndex:(NSUInteger)(d + 1) withBarrier:NO];
                }
                [enc endEncoding];
                [cb commit];
                [cb waitUntilCompleted];
                if (cb.error) { fprintf(stderr, "instrumented batch failed N=%d rep=%d: %s\n", N, rep, cb.error.localizedDescription.UTF8String); return 1; }

                instr_total[rep] = (cb.GPUEndTime - cb.GPUStartTime) * 1000.0;

                NSData *resolved = [sbuf resolveCounterRange:NSMakeRange(0, (NSUInteger)(N + 1))];
                if (resolved.length < sizeof(MTLCounterResultTimestamp) * (NSUInteger)(N + 1)) {
                    fprintf(stderr, "resolveCounterRange returned %lu bytes, expected >= %lu\n",
                            (unsigned long)resolved.length,
                            (unsigned long)(sizeof(MTLCounterResultTimestamp) * (NSUInteger)(N + 1)));
                    return 1;
                }
                const MTLCounterResultTimestamp *ts = (const MTLCounterResultTimestamp *)resolved.bytes;
                for (int d = 0; d < N; d++) {
                    /* timestamps are nanoseconds on Apple silicon; ms = /1e6 */
                    per_disp[rep][d] = (double)(ts[d + 1].timestamp - ts[d].timestamp) / 1.0e6;
                }
            }
            insertion_sort(instr_total, N_REPS_INSTR);
            double instr_med = percentile_sorted(instr_total, N_REPS_INSTR, 0.5);

            /* per-index medians across reps */
            double idx_med[N_MAX];
            for (int d = 0; d < N; d++) {
                double col[N_REPS_INSTR];
                for (int rep = 0; rep < N_REPS_INSTR; rep++) col[rep] = per_disp[rep][d];
                insertion_sort(col, N_REPS_INSTR);
                idx_med[d] = percentile_sorted(col, N_REPS_INSTR, 0.5);
            }
            double sum_idx_med = 0.0;
            for (int d = 0; d < N; d++) sum_idx_med += idx_med[d];

            /* steady-state: pooled durations at index >= N/2 */
            int ss_start = N / 2;
            int ss_count = 0;
            double ss_pool[N_REPS_INSTR * N_MAX];
            for (int rep = 0; rep < N_REPS_INSTR; rep++)
                for (int d = ss_start; d < N; d++) ss_pool[ss_count++] = per_disp[rep][d];
            insertion_sort(ss_pool, ss_count);
            double ss_med = percentile_sorted(ss_pool, ss_count, 0.5);
            double ss_p10 = percentile_sorted(ss_pool, ss_count, 0.1);
            double ss_p90 = percentile_sorted(ss_pool, ss_count, 0.9);

            printf("N=%d: instrumented  GPU-total median %.4f ms; sum-of-per-index-medians %.4f ms; overlap ratio %.3f\n",
                   N, instr_med, sum_idx_med, sum_idx_med / instr_med);
            printf("N=%d: per-dispatch[0]=%.4f ms  [1]=%.4f ms  steady(idx>=%d) median=%.4f ms (p10 %.4f / p90 %.4f)\n",
                   N, idx_med[0], N > 1 ? idx_med[1] : idx_med[0], ss_start, ss_med, ss_p10, ss_p90);

            printf("N=%d: per-dispatch medians:", N);
            int printed = 0;
            for (int d = 0; d < N && printed < 16; d++, printed++) printf(" %.3f", idx_med[d]);
            if (N > printed) printf(" ...");
            printf("\n");
        }

        return 0;
    }
}
