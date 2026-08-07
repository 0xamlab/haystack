/* fa_operator_harness.m -- Phase 0A's identical-buffer operator harness: dispatch the PINNED
 * llama.cpp Metal kernel `kernel_flash_attn_ext_f16_dk128_dv128` (matrix path, nsg=4) directly,
 * with our own Q/K/V/mask buffers, and compare its output against an independent Float64 CPU
 * reference. This is L0 of the ablation ledger (Attention Compiler Plan v1.0, Stage 3) -- the
 * fixed point every later candidate is measured against.
 *
 * Uses the REAL vendored kargs struct (`ggml_metal_kargs_flash_attn_ext`, from the pinned
 * `ggml-metal-impl.h`) and the REAL function-constant indices read directly from
 * `ggml-metal-device.cpp` (FC_FLASH_ATTN_EXT=300; +0 has_mask, +1 has_sinks, +2 has_bias,
 * +3 has_scap, +4 has_kvpad, +10 bc_mask, +20 ns10, +21 ns20, +22 nsg) -- not hand-transcribed,
 * so there is no risk of a transcription error in the one thing that must be byte-exact.
 *
 * Test shape: Q_TILE=8 query rows, ONE K-tile (n_kv=64, dividing cleanly by NCPSG=64 so
 * has_kvpad=false), h_q=16, h_kv=8 (real Qwen3-0.6B GQA shape), has_mask=true (causal). The
 * separate `kernel_flash_attn_ext_blk` pre-pass kernel is NOT dispatched -- instead its one
 * output byte for this single-tile shape is written directly: with exactly one Q-tile and one
 * K-tile, the causal boundary falls inside that tile, so its classification is always "1"
 * (mixed, apply the mask), never "0" (fully masked) or "2" (fully valid). This is load-bearing,
 * not a shortcut: the main kernel reads `blk[ic0]` UNCONDITIONALLY whenever has_mask=true
 * (ggml-metal.metal:6599-6629), and `blk_cur==0` means "skip this tile entirely" -- a
 * zero-initialized dummy buffer silently skips every tile, producing all-zero output with NO
 * Metal validation error. That was the actual bug this file's own debugging found (see the
 * comment at the blk buffer setup below), not anything about the mask VALUES.
 *
 * Build:
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -c ../upstream_src/ggml-metal.metal -o /tmp/ggml_fa.air
 *   xcrun -sdk macosx metallib /tmp/ggml_fa.air -o /tmp/ggml_fa.metallib
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src fa_operator_harness.m -o /tmp/fa_operator_harness
 *   /tmp/fa_operator_harness /tmp/ggml_fa.metallib
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
#define Q_ROWS 8
#define N_KV 64
#define NSG 4

/* Deterministic pseudo-data, matching this repo's own established convention
 * (`_pseudo_f32` in benchmarks/llm_smoke/*_probe.mojo) so results are reproducible without a
 * seeded RNG dependency. */
static float pseudo(int i, int seed, float amp) {
    float a = (float)((i * 37 + seed * 101) % 61) / 30.0f - 1.0f;
    float b = (float)((i * 13 + seed * 7) % 29) / 14.0f - 1.0f;
    return amp * (a + 0.5f * b);
}

static uint16_t f32_to_f16(float f) {
    /* Portable, non-vectorized f32->f16 (round-to-nearest-even not required for a test harness;
     * plain truncation of the rounded value is enough for a correctness comparison at the
     * tolerances this plan already uses). */
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
            /* subnormal -- not expected for our test magnitudes, handled for completeness */
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
        BOOL has_mask = YES, has_sinks = NO, has_bias = NO, has_scap = NO, has_kvpad = NO, bc_mask = NO;
        int32_t ns10 = DK, ns20 = DV, nsg = NSG; /* dense F16 rows: ns = nb1/nb0 = (DK*2)/2 = DK */
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

        /* ---- data ---- */
        int n_q_elems = DK * Q_ROWS * H_Q;      /* Q: [DK][Q_ROWS][H_Q][1], F32 */
        int n_kv_elems = DK * N_KV * H_KV;      /* K, V: [DK][N_KV][H_KV][1], F16 */
        int n_mask_elems = N_KV * Q_ROWS;       /* mask: [N_KV][Q_ROWS][1][1], F16 */
        int n_dst_elems = DV * Q_ROWS * H_Q;    /* dst: [DV][Q_ROWS][H_Q][1], F32 */

        float *q_f32 = malloc(n_q_elems * sizeof(float));
        for (int i = 0; i < n_q_elems; i++) q_f32[i] = pseudo(i, 3, 0.6f);
        uint16_t *k_f16 = malloc(n_kv_elems * sizeof(uint16_t));
        uint16_t *v_f16 = malloc(n_kv_elems * sizeof(uint16_t));
        for (int i = 0; i < n_kv_elems; i++) { k_f16[i] = f32_to_f16(pseudo(i, 11, 0.5f)); v_f16[i] = f32_to_f16(pseudo(i, 29, 0.4f)); }

        /* causal mask, additive bias: row q (0-indexed) attends to key k iff k <= q (pos_base=0) */
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
        /* sinks buffer must exist even when unused (has_sinks=false) -- the kernel signature
         * still takes the pointer; bind a 1-element dummy. */
        float sinks_dummy = 0.0f;
        id<MTLBuffer> sinksBuf = [device newBufferWithBytes:&sinks_dummy length:sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> padBuf = [device newBufferWithLength:16 options:MTLResourceStorageModeShared];   /* unused, has_kvpad=false */
        id<MTLBuffer> blkBuf = [device newBufferWithLength:16 options:MTLResourceStorageModeShared];
        /* class 1 = mixed/diagonal: with exactly one Q-tile and one K-tile, the causal boundary
         * falls inside this single tile, so blk[0] must be 1 (apply mask), never the default 0
         * (fully-masked, skip) -- confirmed by direct read of the kernel's own consumption at
         * ggml-metal.metal:6599-6629: blk is read UNCONDITIONALLY when has_mask=true, and a
         * zero-initialized dummy buffer silently skips every tile, giving all-zero output with
         * no error -- this was the real bug, not the mask VALUES. */
        ((int8_t *)blkBuf.contents)[0] = 1;

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
        kargs.ne1 = H_Q; kargs.ne2 = Q_ROWS; kargs.ne3 = 1;  /* dst row = token*ne1+head: heads fastest within a token */
        kargs.scale = 1.0f / sqrtf((float)DK);
        kargs.max_bias = 0.0f; kargs.m0 = 1.0f; kargs.m1 = 1.0f;
        kargs.n_head_log2 = 1 << (int)floorf(log2f((float)H_Q));
        kargs.logit_softcap = 0.0f;

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

        MTLSize grid = MTLSizeMake((Q_ROWS + 7) / 8, H_Q, 1);
        MTLSize tpg = MTLSizeMake(32, NSG, 1);
        [enc dispatchThreadgroups:grid threadsPerThreadgroup:tpg];
        [enc endEncoding];
        [cmdBuf commit];
        [cmdBuf waitUntilCompleted];

        if (cmdBuf.error) {
            fprintf(stderr, "dispatch failed: %s\n", cmdBuf.error.localizedDescription.UTF8String);
            return 1;
        }

        float *dst = (float *)dstBuf.contents;

        /* ---- independent CPU Float64 reference: materialized causal softmax(QK^T/sqrt(d))V ---- */
        double worst = 0.0;
        int group = H_Q / H_KV;
        for (int h = 0; h < H_Q; h++) {
            int hk = h / group;
            for (int qi = 0; qi < Q_ROWS; qi++) {
                double scores[N_KV];
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
                double acc[DV];
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
            }
        }

        printf("kernel_flash_attn_ext_f16_dk128_dv128 (matrix path, nsg=4) vs CPU Float64 reference\n");
        printf("shape: Q_ROWS=%d H_Q=%d H_KV=%d N_KV=%d DK=DV=%d\n", Q_ROWS, H_Q, H_KV, N_KV, DK);
        printf("worst abs delta: %.9f\n", worst);

        if (getenv("FA_DEBUG")) {
            /* recompute CPU reference for h=0, qi=0 and dump both sides for the first 8 dims */
            int h = 0, qi = 0, hk = h / group;
            double scores[N_KV], m = -1e300;
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
            printf("h=0 qi=0: cpu row max=%.6f\n", m);
            double denom = 0.0, acc[8] = {0};
            for (int k = 0; k < N_KV; k++) {
                double w = exp(scores[k] - m);
                denom += w;
                for (int d = 0; d < 8; d++) {
                    double vv = f16_to_f32(v_f16[(size_t)d + (size_t)k * DV + (size_t)hk * DV * N_KV]);
                    acc[d] += w * vv;
                }
            }
            printf("h=0 qi=0: cpu denom=%.6f\n", denom);
            for (int d = 0; d < 8; d++) {
                double ref = acc[d] / denom;
                float got = dst[(size_t)d + (size_t)h * DV + (size_t)qi * DV * H_Q];
                printf("  d=%d: cpu=%.6f  gpu=%.6f  diff=%.6f\n", d, ref, got, fabs(ref - (double)got));
            }
            printf("mask[q=0][k=0..3]=%.1f %.1f %.1f %.1f (expect 0,-60000,-60000,-60000)\n",
                   f16_to_f32(mask_f16[0*N_KV+0]), f16_to_f32(mask_f16[0*N_KV+1]),
                   f16_to_f32(mask_f16[0*N_KV+2]), f16_to_f32(mask_f16[0*N_KV+3]));

            int n_nonzero = 0, first_nonzero = -1;
            for (int i = 0; i < n_dst_elems; i++) {
                if (dst[i] != 0.0f) { n_nonzero++; if (first_nonzero < 0) first_nonzero = i; }
            }
            printf("dst buffer: %d/%d nonzero elements; first nonzero at flat index %d (value=%.6f)\n",
                   n_nonzero, n_dst_elems, first_nonzero, first_nonzero >= 0 ? dst[first_nonzero] : 0.0f);
        }

        /* Pre-registered operator-output tolerance (README.md): observed worst delta on this exact
         * shape is ~1.3e-5 (F16 K/V narrowing dominates; Q stays F32 into the kernel's own internal
         * F16 cast). 1e-3 leaves a comfortable margin for different pseudo-random test data while
         * still catching a real correctness regression, which would be orders of magnitude larger
         * (the pre-fix bug here was 0.586, not a rounding-scale difference). */
        double tol = 1.0e-3;
        printf("%s (tolerance %.1e; F32 Q + F16 K/V narrowing only, no other source of error expected)\n",
               worst < tol ? "PASS" : "FAIL", tol);
        return worst < tol ? 0 : 1;
    }
}
