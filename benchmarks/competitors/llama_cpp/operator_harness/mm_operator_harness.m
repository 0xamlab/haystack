/* mm_operator_harness.m -- GEMM L0 anchor: dispatch the PINNED llama.cpp Metal kernel
 * `kernel_mul_mm_f16_f32` directly, at the real qkv_proj shape from Qwen3-0.6B-Base prefill
 * (M=256, K=1024, N=4096), with our own weight/activation buffers, and compare its output
 * against an independent Float64 CPU reference. This is L0 of the GEMM ablation ledger
 * (Attention Compiler Plan v1.0), mirroring exactly what fa_operator_harness.m did for
 * attention's own L0.
 *
 * ---- which kernel, and why ----
 * At M=256 (batched prefill), llama.cpp's own op dispatch (ggml-metal-ops.cpp,
 * ggml_metal_op_mul_mat) takes the matrix-matrix path, NOT matrix-vector: the mat-vec fast path
 * only fires for ne11 (=M) in [2,8] (F32/F16/BF16/Q8_0 family) or [4,8] (K-quants); M=256 is far
 * outside that range, and `props_dev->has_simdgroup_mm && ne00 >= 64 && ne11 > 8` (ne00=K=1024,
 * ne11=M=256) selects `kernel_mul_mm` unconditionally. src0 (weight) is F16, src1 (activation)
 * is F32, so the pipeline is `kernel_mul_mm_f16_f32`.
 *
 * Tensor-core path (`#ifdef GGML_METAL_HAS_TENSOR` in ggml-metal.metal) is OUT OF SCOPE: that
 * macro is only defined when `ggml_metal_device_get_props(dev)->has_tensor` is true at JIT-compile
 * time (ggml-metal-device.m:220-222), and `has_tensor` is force-disabled for every non-M5/A19+
 * chip by name-string check (ggml-metal-device.m:752-759) -- explicitly including "M4, M4 Max: no
 * significant difference" in the upstream comment. Our own ahead-of-time `xcrun metal` build
 * below never defines this macro either way, so it always compiles the `#else` (legacy
 * simdgroup_multiply_accumulate) branch -- the exact branch that runs on this M4 Max at runtime.
 * Same scoping this plan already applied to MLX's NAX/Metal4 cooperative tensors.
 *
 * ---- kargs struct (real, from ggml-metal-impl.h) ----
 *   typedef struct {
 *       int32_t  ne00;   // K
 *       int32_t  ne02;   // src0 (weight) batch dim, =1 for a plain linear layer
 *       uint64_t nb01;   // weight row stride  = K * sizeof(half)
 *       uint64_t nb02;   // weight batch stride = nb01 * ne01(=N)
 *       uint64_t nb03;   // = nb02 * ne02
 *       int32_t  ne12;   // src1 (activation) batch dim, =1
 *       uint64_t nb10;   // activation element stride = sizeof(float)
 *       uint64_t nb11;   // activation row stride = K * sizeof(float)
 *       uint64_t nb12;   // = nb11 * ne11(=M)
 *       uint64_t nb13;   // = nb12 * ne12
 *       int32_t  ne0;    // dst ne[0] = N (weight rows)
 *       int32_t  ne1;    // dst ne[1] = M (activation rows)
 *       int16_t  r2;     // ne12/ne02 broadcast ratio, =1 here
 *       int16_t  r3;     // ne13/ne03 broadcast ratio, =1 here
 *   } ggml_metal_kargs_mul_mm;
 *
 * ---- function constants (real indices, ggml-metal-device.cpp:704-746 + ggml-metal.metal:10018-10023) ----
 *   FC_MUL_MM = 700 (ggml-metal-impl.h)
 *   +0  bc_inp (bool)  = (src0->ne[0] % 32 != 0)                         -> K=1024, 1024%32=0 -> false
 *   +1  bc_out (bool)  = has_tensor ? ... : (ne0%64!=0 || ne1%32!=0)     -> N=4096%64=0, M=256%32=0 -> false
 *   +2  ne12  (int16)  = src1->ne[2]                                     -> 1
 *   +3  ne13  (int16)  = src1->ne[3]                                     -> 1
 *   +4  r2    (int16)  = ne12/src0->ne[2]                                -> 1
 *   +5  r3    (int16)  = ne13/src0->ne[3]                                -> 1
 * bc_inp=false and bc_out=false means our (M,K,N) is an EXACT tile fit (K%32==0, N%64==0, M%32==0)
 * -- no boundary-check code paths are exercised, the cleanest possible measurement.
 *
 * ---- dispatch geometry (real, from ggml-metal-ops.cpp:2241-2274, non-tensor branch since
 * has_tensor=false) ----
 *   pipeline.nr0 = 64, pipeline.nr1 = 32, pipeline.nsg = N_MM_SIMD_GROUP_X*N_MM_SIMD_GROUP_Y = 4
 *   pipeline.smem = bc_out ? 8192 : (4096+2048) = 6144   (threadgroup memory, index 0)
 *   threadgroups = ( (ne11+nr1-1)/nr1, (ne01+nr0-1)/nr0, ne12*ne13 )
 *                = ( (256+31)/32, (4096+63)/64, 1 ) = (8, 64, 1)
 *   threadsPerThreadgroup = (32, nsg, 1) = (32, 4, 1)
 * Buffer indices are IMPLICIT declaration order (kernel_mul_mm has no [[buffer(N)]] attributes):
 * 0=kargs (setBytes), 1=src0 (weight), 2=src1 (activation), 3=dst.
 *
 * ---- precision: a real finding beyond what "dequantize_f16 = identity" implies ----
 * `kernel_mul_mm_f16_f32`'s own template instantiation is
 *   kernel_mul_mm<half, half4x4, simdgroup_half8x8,   <- S0 (weight tile-load/matmul type)
 *                 half, half2x4, simdgroup_half8x8,   <- S1 (activation tile-load/matmul type)
 *                 half4x4, 1, dequantize_f16,
 *                 half, half4x4, float, float2x4>     <- T0=weight device dtype, T1=activation device dtype
 * T0=half (weight is natively F16 on device, matches the task's "no dequant" framing) but T1=float
 * (activation is natively F32 on device) while S1=half: the non-tensor kernel body narrows the F32
 * activation to `half` when populating shared memory (`*(sb + ...) = (S1)(*((device T1 *) y));`,
 * ggml-metal.metal:10286) BEFORE the simdgroup_multiply_accumulate, which only ever sees
 * simdgroup_half8x8 operands on both sides (`S0_8x8=S1_8x8=simdgroup_half8x8`) accumulating into
 * `simdgroup_float8x8`. So BOTH operands enter the real multiply at F16 precision, not just the
 * weight -- a second, real precision-loss source beyond the "weights are already F16, no dequant"
 * framing this task started from. This is disclosed plainly below and folded into the tolerance.
 *
 * ---- correctness tolerance reasoning ----
 * The CPU oracle uses the UNTRUNCATED F32 activation and the native F16 weight (both widened to
 * Float64) -- i.e. the mathematically ideal answer for the data as generated. The kernel's actual
 * output additionally narrows the activation to F16 internally (see above), so the measured delta
 * is expected to be LARGER than fa_operator_harness.m's (which only narrowed K/V, never Q, and only
 * reduced over dk=128terms). Here BOTH operands round to F16 (~2^-11 relative each) and the
 * reduction is over K=1024 terms (8x longer than attention's per-head dk=128) -- more terms means
 * more rounding events, though also more random-sign cancellation. A relative tolerance (rather
 * than absolute, since GEMM output magnitude scales with K and is not bounded to O(1) the way a
 * softmax-weighted average is) of `tol * max(1.0, |ref|)` is used, checked at 1e-2 (the upper end
 * of the task's stated 1e-3-1e-2 band, chosen because of the two-operand F16 truncation above) --
 * still 1-2 orders of magnitude tighter than any real correctness bug would produce. Both worst
 * absolute and worst relative deltas are printed either way so the real number, not just the
 * pass/fail, is on record.
 *
 * Build:
 *   export DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer
 *   xcrun -sdk macosx metal -c ../upstream_src/ggml-metal.metal -o /tmp/ggml_mm.air
 *   xcrun -sdk macosx metallib /tmp/ggml_mm.air -o /tmp/ggml_mm.metallib
 *   clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *     -I ../upstream_src mm_operator_harness.m -o /tmp/mm_operator_harness
 *   /tmp/mm_operator_harness /tmp/ggml_mm.metallib
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ggml-metal-impl.h"

/* real Qwen3-0.6B-Base qkv_proj shape at m_rows=256 (prefill), see manifest-derived shapes in the
 * task brief: hidden_size=1024, (n_head + 2*n_kv_head)*head_dim = (16+16)*128 = 4096 */
#define M_ROWS 256
#define K_DIM  1024
#define N_DIM  4096

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

        /* ---- data ----
         * weight W: [N][K] row-major F16 (llama.cpp linear-layer weight layout: ne00=K contiguous,
         * ne01=N rows -- exactly how a Linear(in=K,out=N) weight is stored)
         * activation X: [M][K] row-major F32 (ne10=K contiguous, ne11=M rows)
         * dst Y: [M][N] row-major F32 (ne0=N contiguous stride, ne1=M rows) */
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
            fprintf(stderr, "dispatch failed: %s\n", cmdBuf.error.localizedDescription.UTF8String);
            return 1;
        }

        float *y = (float *)yBuf.contents;

        /* ---- independent CPU Float64 reference ----
         * ref[m][n] = sum_k (double)X[m][k] * (double)widen(W[n][k])
         * Precompute the F16->F64 widened weight once (avoids re-converting the same weight value
         * M times) to keep the O(M*N*K) = 256*4096*1024 ~ 1.07e9 FMA reference tractable. */
        double *w_f64 = malloc(n_w * sizeof(double));
        for (size_t i = 0; i < n_w; i++) w_f64[i] = (double)f16_to_f32(w_f16[i]);

        double worst_abs = 0.0, worst_rel = 0.0;
        long worst_m = -1, worst_n = -1;
        for (int m = 0; m < M_ROWS; m++) {
            const float *xrow = x_f32 + (size_t)m * K_DIM;
            for (int n = 0; n < N_DIM; n++) {
                const double *wrow = w_f64 + (size_t)n * K_DIM;
                double acc = 0.0;
                for (int k = 0; k < K_DIM; k++) {
                    acc += (double)xrow[k] * wrow[k];
                }
                float got = y[(size_t)m * N_DIM + n];
                double diff = fabs(acc - (double)got);
                double rel = diff / fmax(1.0, fabs(acc));
                if (diff > worst_abs) worst_abs = diff;
                if (rel > worst_rel) { worst_rel = rel; worst_m = m; worst_n = n; }
            }
        }

        printf("kernel_mul_mm_f16_f32 (legacy simdgroup_multiply_accumulate path, nsg=4) vs CPU Float64 reference\n");
        printf("shape: M=%d K=%d N=%d (qkv_proj @ Qwen3-0.6B-Base, m_rows=256 prefill)\n", M_ROWS, K_DIM, N_DIM);
        printf("worst abs delta: %.9f\n", worst_abs);
        printf("worst rel delta (|diff|/max(1,|ref|)): %.9f  at m=%ld n=%ld\n", worst_rel, worst_m, worst_n);

        if (getenv("MM_DEBUG") && worst_m >= 0) {
            const float *xrow = x_f32 + (size_t)worst_m * K_DIM;
            const double *wrow = w_f64 + (size_t)worst_n * K_DIM;
            double acc = 0.0;
            for (int k = 0; k < K_DIM; k++) acc += (double)xrow[k] * wrow[k];
            float got = y[(size_t)worst_m * N_DIM + worst_n];
            printf("worst element: m=%ld n=%ld cpu=%.6f gpu=%.6f\n", worst_m, worst_n, acc, got);

            long n_nonzero = 0, first_nonzero = -1;
            for (size_t i = 0; i < n_y; i++) {
                if (y[i] != 0.0f) { n_nonzero++; if (first_nonzero < 0) first_nonzero = (long)i; }
            }
            printf("dst buffer: %ld/%zu nonzero elements; first nonzero at flat index %ld (value=%.6f)\n",
                   n_nonzero, n_y, first_nonzero, first_nonzero >= 0 ? y[first_nonzero] : 0.0f);
        }

        /* Relative tolerance (see header comment): both weight AND activation truncate to F16
         * inside the real multiply-accumulate (not just the weight), reduced over K=1024 terms --
         * a strictly harder case than fa_operator_harness.m's single-operand, dk=128 reduction.
         * 1e-2 is the upper end of the task's stated 1e-3-1e-2 band, chosen for that reason; a real
         * correctness bug (wrong stride, transposed tile, wrong FC value) produces errors orders of
         * magnitude larger than F16-rounding noise, so this still catches regressions. */
        double tol = 1.0e-2;
        printf("%s (relative tolerance %.1e; F16-truncated weight AND F16-truncated activation, F32 accumulate, K=%d terms)\n",
               worst_rel < tol ? "PASS" : "FAIL", tol, K_DIM);
        if (worst_rel >= tol) return 1;

        /* ---- L0 timing: 200 warm dispatches, buffers allocated once outside the timed region ---- */
        #define N_TIMING_RUNS 200
        double gpu_ms[N_TIMING_RUNS];
        double wall_ms[N_TIMING_RUNS];
        for (int run = 0; run < N_TIMING_RUNS; run++) {
            CFAbsoluteTime t0 = CFAbsoluteTimeGetCurrent();
            id<MTLCommandBuffer> tcb = [queue commandBuffer];
            id<MTLComputeCommandEncoder> tenc = [tcb computeCommandEncoder];
            [tenc setComputePipelineState:pipeline];
            [tenc setBytes:&kargs length:sizeof(kargs) atIndex:0];
            [tenc setBuffer:wBuf offset:0 atIndex:1];
            [tenc setBuffer:xBuf offset:0 atIndex:2];
            [tenc setBuffer:yBuf offset:0 atIndex:3];
            [tenc setThreadgroupMemoryLength:SMEM atIndex:0];
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
        printf("L0 timing (n=%d dispatches, same shape): GPU median=%.4f ms (p10=%.4f p90=%.4f)  wall median=%.4f ms (p10=%.4f p90=%.4f)\n",
               N_TIMING_RUNS,
               gpu_ms[N_TIMING_RUNS/2], gpu_ms[N_TIMING_RUNS/10], gpu_ms[N_TIMING_RUNS*9/10],
               wall_ms[N_TIMING_RUNS/2], wall_ms[N_TIMING_RUNS/10], wall_ms[N_TIMING_RUNS*9/10]);

        return 0;
    }
}
