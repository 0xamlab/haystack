/* fa_operator_harness_multitile.m -- L0 at the Phase 2A Round 1 hard-gate shape: a full 256-token
 * single-shot causal prefill (Q_ROWS=256, N_KV=256 -> 32 Q-tiles x 4 K-tiles), not the single-tile
 * shape fa_operator_harness.m tests. Q_ROWS/N_KV are exact multiples of NQPSG=8/NCPSG=64, so
 * has_kvpad=false and no pad kernel is needed -- but with 4 K-tiles, the causal boundary no longer
 * falls inside every dispatched tile, so `blk[]` (the mask-tile classifier's own output, read
 * UNCONDITIONALLY by the main kernel whenever has_mask=true, see fa_operator_harness.m's own
 * header comment on why a wrong blk value silently skips tiles with no error) must be populated
 * PER (query-tile, key-tile) PAIR, not as a single constant byte.
 *
 * `kernel_flash_attn_ext_blk` is not dispatched here either -- instead blk[i1*nblk0+i0] is computed
 * directly from the SAME closed-form causal classification its own source implements
 * (ggml-metal.metal:6331-6359, teardown Sec 5.1: mmax<=-MAXHALF -> 0 fully masked; mmin==0&&mmax==0
 * -> 2 fully visible; else -> 1 mixed), verified against the teardown's own documented census for
 * causal 256^2 (48 class-0 / 48 class-2 / 32 class-1 out of 128 total (i1,i0) tiles) before trusting
 * it here -- this file's own `main()` prints and checks that exact census before dispatching.
 *
 * Build:
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -c ../upstream_src/ggml-metal.metal -o /tmp/ggml_fa.air   (skip if already built)
 *   xcrun -sdk macosx metallib /tmp/ggml_fa.air -o /tmp/ggml_fa.metallib             (skip if already built)
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src fa_operator_harness_multitile.m -o /tmp/fa_operator_harness_multitile
 *   /tmp/fa_operator_harness_multitile /tmp/ggml_fa.metallib
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ggml-metal-impl.h"

#define DK 128
#define DV 128
#define H_Q 16
#define H_KV 8
#define NSG 4
#define C_TILE 64
#define Q_TILE 8

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
        bits = (mant == 0) ? sign : sign;  /* subnormal not expected at our test magnitudes */
    } else if (exp == 31) {
        bits = sign | 0x7F800000 | (mant << 13);
    } else {
        bits = sign | ((exp - 15 + 127) << 23) | (mant << 13);
    }
    float f;
    memcpy(&f, &bits, 4);
    return f;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 2) { fprintf(stderr, "usage: %s <metallib path> [n_rows]\n", argv[0]); return 1; }
        int Q_ROWS = (argc >= 3) ? atoi(argv[2]) : 256;
        int N_KV = Q_ROWS;
        if (Q_ROWS % Q_TILE != 0 || N_KV % C_TILE != 0) {
            fprintf(stderr, "n_rows=%d must be a multiple of both Q_TILE=%d and C_TILE=%d\n", Q_ROWS, Q_TILE, C_TILE);
            return 1;
        }

        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "no Metal device\n"); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        NSError *err = nil;
        NSURL *libURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
        id<MTLLibrary> library = [device newLibraryWithURL:libURL error:&err];
        if (!library) { fprintf(stderr, "newLibraryWithURL failed: %s\n", err.localizedDescription.UTF8String); return 1; }

        MTLFunctionConstantValues *cv = [MTLFunctionConstantValues new];
        BOOL has_mask = YES, has_sinks = NO, has_bias = NO, has_scap = NO, has_kvpad = NO, bc_mask = NO;
        int32_t ns10 = DK, ns20 = DV, nsg = NSG;
        [cv setConstantValue:&has_mask type:MTLDataTypeBool atIndex:FC_FLASH_ATTN_EXT + 0];
        [cv setConstantValue:&has_sinks type:MTLDataTypeBool atIndex:FC_FLASH_ATTN_EXT + 1];
        [cv setConstantValue:&has_bias type:MTLDataTypeBool atIndex:FC_FLASH_ATTN_EXT + 2];
        [cv setConstantValue:&has_scap type:MTLDataTypeBool atIndex:FC_FLASH_ATTN_EXT + 3];
        [cv setConstantValue:&has_kvpad type:MTLDataTypeBool atIndex:FC_FLASH_ATTN_EXT + 4];
        [cv setConstantValue:&bc_mask type:MTLDataTypeBool atIndex:FC_FLASH_ATTN_EXT + 10];
        [cv setConstantValue:&ns10 type:MTLDataTypeInt atIndex:FC_FLASH_ATTN_EXT + 20];
        [cv setConstantValue:&ns20 type:MTLDataTypeInt atIndex:FC_FLASH_ATTN_EXT + 21];
        [cv setConstantValue:&nsg type:MTLDataTypeInt atIndex:FC_FLASH_ATTN_EXT + 22];

        id<MTLFunction> fn = [library newFunctionWithName:@"kernel_flash_attn_ext_f16_dk128_dv128"
                                            constantValues:cv error:&err];
        if (!fn) { fprintf(stderr, "newFunctionWithName failed: %s\n", err.localizedDescription.UTF8String); return 1; }
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:fn error:&err];
        if (!pipeline) { fprintf(stderr, "pipeline creation failed: %s\n", err.localizedDescription.UTF8String); return 1; }

        int n_q_elems = DK * Q_ROWS * H_Q;
        int n_kv_elems = DK * N_KV * H_KV;
        int n_mask_elems = N_KV * Q_ROWS;
        int n_dst_elems = DV * Q_ROWS * H_Q;

        float *q_f32 = malloc(n_q_elems * sizeof(float));
        for (int i = 0; i < n_q_elems; i++) q_f32[i] = pseudo(i, 3, 0.6f);
        uint16_t *k_f16 = malloc(n_kv_elems * sizeof(uint16_t));
        uint16_t *v_f16 = malloc(n_kv_elems * sizeof(uint16_t));
        for (int i = 0; i < n_kv_elems; i++) { k_f16[i] = f32_to_f16(pseudo(i, 11, 0.5f)); v_f16[i] = f32_to_f16(pseudo(i, 29, 0.4f)); }

        uint16_t *mask_f16 = malloc(n_mask_elems * sizeof(uint16_t));
        for (int q = 0; q < Q_ROWS; q++) {
            for (int k = 0; k < N_KV; k++) {
                float bias = (k <= q) ? 0.0f : -60000.0f;
                mask_f16[q * N_KV + k] = f32_to_f16(bias);
            }
        }

        id<MTLBuffer> qBuf = [device newBufferWithBytes:q_f32 length:n_q_elems * sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> kBuf = [device newBufferWithBytes:k_f16 length:n_kv_elems * sizeof(uint16_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> vBuf = [device newBufferWithBytes:v_f16 length:n_kv_elems * sizeof(uint16_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> maskBuf = [device newBufferWithBytes:mask_f16 length:n_mask_elems * sizeof(uint16_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> dstBuf = [device newBufferWithLength:n_dst_elems * sizeof(float) options:MTLResourceStorageModeShared];
        { float *dp = (float *)dstBuf.contents; for (int i = 0; i < n_dst_elems; i++) dp[i] = -999.0f; }
        float sinks_dummy = 0.0f;
        id<MTLBuffer> sinksBuf = [device newBufferWithBytes:&sinks_dummy length:sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> padBuf = [device newBufferWithLength:16 options:MTLResourceStorageModeShared];

        int nblk0 = N_KV / C_TILE;   /* KV blocks, fastest-varying */
        int nblk1 = Q_ROWS / Q_TILE; /* query blocks */
        id<MTLBuffer> blkBuf = [device newBufferWithLength:(size_t)nblk0 * nblk1 options:MTLResourceStorageModeShared];
        int8_t *blk = (int8_t *)blkBuf.contents;
        int n_class0 = 0, n_class1 = 0, n_class2 = 0;
        for (int i1 = 0; i1 < nblk1; i1++) {
            for (int i0 = 0; i0 < nblk0; i0++) {
                int q_lo = i1 * Q_TILE, q_hi = q_lo + Q_TILE - 1;
                int k_lo = i0 * C_TILE, k_hi = k_lo + C_TILE - 1;
                int8_t cls;
                if (k_lo > q_hi) { cls = 0; n_class0++; }               /* fully masked for every row */
                else if (k_hi <= q_lo) { cls = 2; n_class2++; }          /* fully visible for every row */
                else { cls = 1; n_class1++; }                            /* mixed: causal boundary inside */
                blk[i1 * nblk0 + i0] = cls;
            }
        }
        printf("blk census: class0=%d class1=%d class2=%d (total=%d)\n", n_class0, n_class1, n_class2, nblk0 * nblk1);
        if (Q_ROWS == 256 && (n_class0 != 48 || n_class1 != 32 || n_class2 != 48)) {
            /* Self-check against the teardown's own documented causal-256^2 census (Sec 5.1) --
             * only meaningful at exactly this shape; other row counts just print their own census. */
            fprintf(stderr, "blk census does not match the teardown's own documented causal-256^2 numbers (48/32/48) -- aborting\n");
            return 1;
        }
        if (n_class1 != nblk1) {
            /* Every query block has EXACTLY one tile straddled by the causal diagonal at these
             * shapes (Q_TILE divides C_TILE's multiples cleanly here) -- a general sanity check
             * beyond the one shape with a literal documented census to compare against. */
            fprintf(stderr, "unexpected mixed-tile count %d (expected exactly one per query block, %d) -- aborting\n", n_class1, nblk1);
            return 1;
        }

        ggml_metal_kargs_flash_attn_ext kargs;
        memset(&kargs, 0, sizeof(kargs));
        kargs.ne01 = Q_ROWS; kargs.ne02 = H_Q; kargs.ne03 = 1;
        kargs.nb01 = (uint64_t)DK * sizeof(float);
        kargs.nb02 = kargs.nb01 * Q_ROWS;
        kargs.nb03 = kargs.nb02 * H_Q;
        kargs.ne11 = N_KV; kargs.ne_12_2 = H_KV; kargs.ne_12_3 = 1;
        kargs.ns10 = DK;
        kargs.nb11 = (uint64_t)DK * sizeof(uint16_t);
        kargs.nb12 = kargs.nb11 * N_KV;
        kargs.nb13 = kargs.nb12 * H_KV;
        kargs.ns20 = DV;
        kargs.nb21 = (uint64_t)DV * sizeof(uint16_t);
        kargs.nb22 = kargs.nb21 * N_KV;
        kargs.nb23 = kargs.nb22 * H_KV;
        kargs.ne31 = Q_ROWS; kargs.ne32 = 1; kargs.ne33 = 1;
        kargs.nb31 = (uint64_t)N_KV * sizeof(uint16_t);
        kargs.nb32 = kargs.nb31 * Q_ROWS;
        kargs.nb33 = kargs.nb32;
        kargs.ne1 = H_Q; kargs.ne2 = Q_ROWS; kargs.ne3 = 1;
        kargs.scale = 1.0f / sqrtf((float)DK);
        kargs.max_bias = 0.0f; kargs.m0 = 1.0f; kargs.m1 = 1.0f;
        kargs.n_head_log2 = 1 << (int)floorf(log2f((float)H_Q));
        kargs.logit_softcap = 0.0f;

        MTLSize grid = MTLSizeMake((Q_ROWS + 7) / 8, H_Q, 1);
        MTLSize tpg = MTLSizeMake(32, NSG, 1);

        id<MTLCommandBuffer> cmdBuf = [queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmdBuf computeCommandEncoder];
        [enc setComputePipelineState:pipeline];
        [enc setBytes:&kargs length:sizeof(kargs) atIndex:0];
        [enc setBuffer:qBuf offset:0 atIndex:1];
        [enc setBuffer:kBuf offset:0 atIndex:2];
        [enc setBuffer:vBuf offset:0 atIndex:3];
        [enc setBuffer:maskBuf offset:0 atIndex:4];
        [enc setBuffer:sinksBuf offset:0 atIndex:5];
        [enc setBuffer:padBuf offset:0 atIndex:6];
        [enc setBuffer:blkBuf offset:0 atIndex:7];
        [enc setBuffer:dstBuf offset:0 atIndex:8];
        [enc setThreadgroupMemoryLength:10240 atIndex:0];
        [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
        [enc endEncoding];
        [cmdBuf commit];
        [cmdBuf waitUntilCompleted];

        if (cmdBuf.error) {
            fprintf(stderr, "dispatch failed: %s\n", cmdBuf.error.localizedDescription.UTF8String);
            return 1;
        }

        float *dst = (float *)dstBuf.contents;

        /* ---- independent CPU Float64 reference, same shape ---- */
        double worst = 0.0;
        int group = H_Q / H_KV;
        for (int h = 0; h < H_Q; h++) {
            int hk = h / group;
            for (int qi = 0; qi < Q_ROWS; qi++) {
                double *scores = malloc(N_KV * sizeof(double));
                double m = -1e300;
                for (int k = 0; k < N_KV; k++) {
                    double dot = 0.0;
                    for (int d = 0; d < DK; d++) {
                        double qv = q_f32[(size_t)d + (size_t)qi * DK + (size_t)h * DK * Q_ROWS];
                        double kv = f16_to_f32(k_f16[(size_t)d + (size_t)k * DK + (size_t)hk * DK * N_KV]);
                        dot += qv * kv;
                    }
                    double s = dot / sqrt((double)DK);
                    if (k > qi) s += -1.0e9;
                    scores[k] = s;
                    if (s > m) m = s;
                }
                double denom = 0.0;
                double *acc = malloc(DV * sizeof(double));
                for (int d = 0; d < DV; d++) acc[d] = 0.0;
                for (int k = 0; k < N_KV; k++) {
                    double w = exp(scores[k] - m);
                    denom += w;
                    for (int d = 0; d < DV; d++) {
                        double vv = f16_to_f32(v_f16[(size_t)d + (size_t)k * DV + (size_t)hk * DV * N_KV]);
                        acc[d] += w * vv;
                    }
                }
                for (int d = 0; d < DV; d++) {
                    double ref = acc[d] / denom;
                    float got = dst[(size_t)d + (size_t)h * DV + (size_t)qi * DV * H_Q];
                    double diff = fabs(ref - (double)got);
                    if (diff > worst) worst = diff;
                }
                free(scores);
                free(acc);
            }
        }

        printf("kernel_flash_attn_ext_f16_dk128_dv128 (matrix path, nsg=4) vs CPU Float64 reference\n");
        printf("shape: Q_ROWS=%d H_Q=%d H_KV=%d N_KV=%d DK=DV=%d (multi-tile: %d Q-tiles x %d K-tiles)\n",
               Q_ROWS, H_Q, H_KV, N_KV, DK, nblk1, nblk0);
        printf("worst abs delta: %.9f\n", worst);
        double tol = 1.0e-3;
        printf("%s (tolerance %.1e)\n", worst < tol ? "PASS" : "FAIL", tol);
        if (worst >= tol) return 1;

        #define N_TIMING_RUNS 200
        double gpu_ms[N_TIMING_RUNS];
        double wall_ms[N_TIMING_RUNS];
        for (int run = 0; run < N_TIMING_RUNS; run++) {
            CFAbsoluteTime t0 = CFAbsoluteTimeGetCurrent();
            id<MTLCommandBuffer> tcb = [queue commandBuffer];
            id<MTLComputeCommandEncoder> tenc = [tcb computeCommandEncoder];
            [tenc setComputePipelineState:pipeline];
            [tenc setBytes:&kargs length:sizeof(kargs) atIndex:0];
            [tenc setBuffer:qBuf offset:0 atIndex:1];
            [tenc setBuffer:kBuf offset:0 atIndex:2];
            [tenc setBuffer:vBuf offset:0 atIndex:3];
            [tenc setBuffer:maskBuf offset:0 atIndex:4];
            [tenc setBuffer:sinksBuf offset:0 atIndex:5];
            [tenc setBuffer:padBuf offset:0 atIndex:6];
            [tenc setBuffer:blkBuf offset:0 atIndex:7];
            [tenc setBuffer:dstBuf offset:0 atIndex:8];
            [tenc setThreadgroupMemoryLength:10240 atIndex:0];
            [tenc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
            [tenc endEncoding];
            [tcb commit];
            [tcb waitUntilCompleted];
            CFAbsoluteTime t1 = CFAbsoluteTimeGetCurrent();
            gpu_ms[run] = (tcb.GPUEndTime - tcb.GPUStartTime) * 1000.0;
            wall_ms[run] = (t1 - t0) * 1000.0;
        }
        for (int i = 1; i < N_TIMING_RUNS; i++) {
            double kg = gpu_ms[i], kw = wall_ms[i]; int j = i - 1;
            while (j >= 0 && gpu_ms[j] > kg) { gpu_ms[j+1] = gpu_ms[j]; j--; }
            gpu_ms[j+1] = kg;
            j = i - 1;
            while (j >= 0 && wall_ms[j] > kw) { wall_ms[j+1] = wall_ms[j]; j--; }
            wall_ms[j+1] = kw;
        }
        printf("L0 timing (n=%d dispatches, 256-row multi-tile shape): GPU median=%.4f ms (p10=%.4f p90=%.4f)  wall median=%.4f ms\n",
               N_TIMING_RUNS, gpu_ms[N_TIMING_RUNS/2], gpu_ms[N_TIMING_RUNS/10], gpu_ms[N_TIMING_RUNS*9/10],
               wall_ms[N_TIMING_RUNS/2]);

        return 0;
    }
}
