// wgmma_census.cu — the REGISTER CENSUS for round 8's sm_90a wgmma attention port, sized so the
// numbers are directly comparable to the kernels they would replace.
//
// WHY THIS FILE EXISTS SEPARATELY FROM tc_shim.cu. The census is the cheapest refutation gate this
// campaign has: it killed round 7's primary lever (v3 RT=2 row-tiles) in ~30 s of build time
// before an hour of gated cells, because v3 needed 255/255 registers and spilled 424-488 B where
// round 6's shipped v2 needs 172 and spills nothing. But the H200 box is spot capacity that keeps
// going to STOCKOUT, so gating authoring on having the GPU inverts the point. `ptxas` is a HOST
// cross-compiler: `-arch=sm_90a` needs a CUDA 12.x toolkit, not an sm_90 device. This file is
// compiled in an arm64 Linux container with CUDA 12.6.85 — the SAME toolkit release as the race
// box — so the register numbers are comparable to the box's without spending a VM minute.
//
// WHAT IS AND IS NOT PROVEN HERE. Proven: the PTX operand syntax ptxas accepts, and the register
// and spill counts. NOT proven: that the shared-memory descriptor encoding is right, that the
// operand layouts are right, or that the kernel computes anything correct — those need the
// on-device layout probe and the host-f64 numeric gate, which is why the real kernel ships with
// both and with a DECLINED fallback. A register census says the lever FITS; it does not say the
// lever WORKS.
//
// The three arms below bracket the design space the real kernel has to choose from:
//   desc  — both operands from shared descriptors (no A/B registers at all)
//   regA  — the P@V product takes P as a REGISTER A-operand (FA2's in-register-P trick, which
//           works because the m64nNk16 accumulator's per-warp layout IS the m16n8k16 A layout)
//   dbuf  — desc with two K/V tiles in flight, i.e. the pipelined form the real kernel needs
//
// Row counts are IDENTICAL to v2's CTA shape on purpose: one warpgroup = 128 threads = 64 query
// rows, exactly v2's FA_BM=64 with 4 warps. So this is an apples-to-apples register comparison,
// and the difference is purely that wgmma's A and B come from shared descriptors instead of
// occupying registers, and there is no ldmatrix anywhere in the loop.
#include <cuda_fp16.h>
#include <cstdint>

// ── the 64-bit shared-memory matrix descriptor, per the PTX ISA matrix-descriptor layout ──
//   bits  0..13  start address       (addr >> 4)
//   bits 16..29  leading byte offset  (LBO >> 4)
//   bits 32..45  stride byte offset   (SBO >> 4)
//   bits 46..48  base offset
//   bits 62..63  swizzle mode: 0 = none, 1 = 128B, 2 = 64B, 3 = 32B
// Swizzle 0 is used throughout: it is the simplest legal encoding and it does not change the
// register count, which is the only thing this file measures. The production kernel will want a
// swizzled layout for bank-conflict reasons; that is a shared-traffic optimisation, not a
// register one, and it must be pinned by the on-device probe before it is trusted.
__device__ __forceinline__ uint64_t wg_desc(const void* p, uint32_t lbo, uint32_t sbo) {
    uint32_t a = (uint32_t)__cvta_generic_to_shared(p);
    uint64_t d = 0;
    d |= (uint64_t)((a >> 4) & 0x3FFF);
    d |= (uint64_t)((lbo >> 4) & 0x3FFF) << 16;
    d |= (uint64_t)((sbo >> 4) & 0x3FFF) << 32;
    return d;   // swizzle field left 0
}

__device__ __forceinline__ void wg_fence() {
    asm volatile("wgmma.fence.sync.aligned;\n" ::: "memory");
}
__device__ __forceinline__ void wg_commit() {
    asm volatile("wgmma.commit_group.sync.aligned;\n" ::: "memory");
}
template <int W>
__device__ __forceinline__ void wg_wait() {
    asm volatile("wgmma.wait_group.sync.aligned %0;\n" :: "n"(W) : "memory");
}

// ── S accumulator shapes: m64nNk16 f32 costs N/2 registers per thread (64*N/128) ──
__device__ __forceinline__ void wg_s32(float* d, uint64_t a, uint64_t b, int acc) {
    // m64nNk16 f32 accumulator costs N/2 registers per thread (64*N/128), so n32 => SIXTEEN
    // outputs %0..%15, then a=%16, b=%17, acc=%18. (First attempt declared 18 outputs and ptxas
    // rejected it with "Argument vector size mismatch" — the count is not a free choice.)
    asm volatile("{\n.reg .pred p;\nsetp.ne.b32 p, %18, 0;\n"
        "wgmma.mma_async.sync.aligned.m64n32k16.f32.f16.f16 "
        "{%0,%1,%2,%3,%4,%5,%6,%7,%8,%9,%10,%11,%12,%13,%14,%15}, "
        "%16, %17, p, 1, 1, 0, 0;\n}\n"
        : "+f"(d[0]),"+f"(d[1]),"+f"(d[2]),"+f"(d[3]),"+f"(d[4]),"+f"(d[5]),"+f"(d[6]),"+f"(d[7]),
          "+f"(d[8]),"+f"(d[9]),"+f"(d[10]),"+f"(d[11]),"+f"(d[12]),"+f"(d[13]),"+f"(d[14]),
          "+f"(d[15])
        : "l"(a), "l"(b), "r"(acc));
}
__device__ __forceinline__ void wg_s64(float* d, uint64_t a, uint64_t b, int acc) {
    asm volatile("{\n.reg .pred p;\nsetp.ne.b32 p, %34, 0;\n"
        "wgmma.mma_async.sync.aligned.m64n64k16.f32.f16.f16 "
        "{%0,%1,%2,%3,%4,%5,%6,%7,%8,%9,%10,%11,%12,%13,%14,%15,"
        "%16,%17,%18,%19,%20,%21,%22,%23,%24,%25,%26,%27,%28,%29,%30,%31}, "
        "%32, %33, p, 1, 1, 0, 0;\n}\n"
        : "+f"(d[0]),"+f"(d[1]),"+f"(d[2]),"+f"(d[3]),"+f"(d[4]),"+f"(d[5]),"+f"(d[6]),"+f"(d[7]),
          "+f"(d[8]),"+f"(d[9]),"+f"(d[10]),"+f"(d[11]),"+f"(d[12]),"+f"(d[13]),"+f"(d[14]),
          "+f"(d[15]),"+f"(d[16]),"+f"(d[17]),"+f"(d[18]),"+f"(d[19]),"+f"(d[20]),"+f"(d[21]),
          "+f"(d[22]),"+f"(d[23]),"+f"(d[24]),"+f"(d[25]),"+f"(d[26]),"+f"(d[27]),"+f"(d[28]),
          "+f"(d[29]),"+f"(d[30]),"+f"(d[31])
        : "l"(a), "l"(b), "r"(acc));
}
// ── O accumulator: m64n128k16 f32 = 64 registers per thread (head_dim 128) ──
__device__ __forceinline__ void wg_o128(float* d, uint64_t a, uint64_t b, int acc) {
    asm volatile("{\n.reg .pred p;\nsetp.ne.b32 p, %66, 0;\n"
        "wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16 "
        "{%0,%1,%2,%3,%4,%5,%6,%7,%8,%9,%10,%11,%12,%13,%14,%15,"
        "%16,%17,%18,%19,%20,%21,%22,%23,%24,%25,%26,%27,%28,%29,%30,%31,"
        "%32,%33,%34,%35,%36,%37,%38,%39,%40,%41,%42,%43,%44,%45,%46,%47,"
        "%48,%49,%50,%51,%52,%53,%54,%55,%56,%57,%58,%59,%60,%61,%62,%63}, "
        "%64, %65, p, 1, 1, 0, 0;\n}\n"
        : "+f"(d[0]),"+f"(d[1]),"+f"(d[2]),"+f"(d[3]),"+f"(d[4]),"+f"(d[5]),"+f"(d[6]),"+f"(d[7]),
          "+f"(d[8]),"+f"(d[9]),"+f"(d[10]),"+f"(d[11]),"+f"(d[12]),"+f"(d[13]),"+f"(d[14]),
          "+f"(d[15]),"+f"(d[16]),"+f"(d[17]),"+f"(d[18]),"+f"(d[19]),"+f"(d[20]),"+f"(d[21]),
          "+f"(d[22]),"+f"(d[23]),"+f"(d[24]),"+f"(d[25]),"+f"(d[26]),"+f"(d[27]),"+f"(d[28]),
          "+f"(d[29]),"+f"(d[30]),"+f"(d[31]),"+f"(d[32]),"+f"(d[33]),"+f"(d[34]),"+f"(d[35]),
          "+f"(d[36]),"+f"(d[37]),"+f"(d[38]),"+f"(d[39]),"+f"(d[40]),"+f"(d[41]),"+f"(d[42]),
          "+f"(d[43]),"+f"(d[44]),"+f"(d[45]),"+f"(d[46]),"+f"(d[47]),"+f"(d[48]),"+f"(d[49]),
          "+f"(d[50]),"+f"(d[51]),"+f"(d[52]),"+f"(d[53]),"+f"(d[54]),"+f"(d[55]),"+f"(d[56]),
          "+f"(d[57]),"+f"(d[58]),"+f"(d[59]),"+f"(d[60]),"+f"(d[61]),"+f"(d[62]),"+f"(d[63])
        : "l"(a), "l"(b), "r"(acc));
}
// ── O accumulator with a REGISTER A-operand (4 f16x2 registers per thread for m64k16) ──
__device__ __forceinline__ void wg_o128_regA(float* d, const unsigned* pa, uint64_t b, int acc) {
    // 64 accumulator outputs (%0..%63), A registers pa[0..3] = %64..%67, b-desc = %68, acc = %69.
    // The register-A form takes only ONE transpose immediate (trans-b): trans-a is not a free
    // operand when A comes from registers, because the register layout IS the A layout. Passing
    // both is what ptxas rejected with "Arguments mismatch for instruction 'wgmma.mma_async'".
    // Trailing immediates are therefore scale-d(pred p), scale-a=1, scale-b=1, trans-b=0.
    asm volatile("{\n.reg .pred p;\nsetp.ne.b32 p, %69, 0;\n"
        "wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16 "
        "{%0,%1,%2,%3,%4,%5,%6,%7,%8,%9,%10,%11,%12,%13,%14,%15,"
        "%16,%17,%18,%19,%20,%21,%22,%23,%24,%25,%26,%27,%28,%29,%30,%31,"
        "%32,%33,%34,%35,%36,%37,%38,%39,%40,%41,%42,%43,%44,%45,%46,%47,"
        "%48,%49,%50,%51,%52,%53,%54,%55,%56,%57,%58,%59,%60,%61,%62,%63}, "
        "{%64,%65,%66,%67}, %68, p, 1, 1, 0;\n}\n"
        : "+f"(d[0]),"+f"(d[1]),"+f"(d[2]),"+f"(d[3]),"+f"(d[4]),"+f"(d[5]),"+f"(d[6]),"+f"(d[7]),
          "+f"(d[8]),"+f"(d[9]),"+f"(d[10]),"+f"(d[11]),"+f"(d[12]),"+f"(d[13]),"+f"(d[14]),
          "+f"(d[15]),"+f"(d[16]),"+f"(d[17]),"+f"(d[18]),"+f"(d[19]),"+f"(d[20]),"+f"(d[21]),
          "+f"(d[22]),"+f"(d[23]),"+f"(d[24]),"+f"(d[25]),"+f"(d[26]),"+f"(d[27]),"+f"(d[28]),
          "+f"(d[29]),"+f"(d[30]),"+f"(d[31]),"+f"(d[32]),"+f"(d[33]),"+f"(d[34]),"+f"(d[35]),
          "+f"(d[36]),"+f"(d[37]),"+f"(d[38]),"+f"(d[39]),"+f"(d[40]),"+f"(d[41]),"+f"(d[42]),
          "+f"(d[43]),"+f"(d[44]),"+f"(d[45]),"+f"(d[46]),"+f"(d[47]),"+f"(d[48]),"+f"(d[49]),
          "+f"(d[50]),"+f"(d[51]),"+f"(d[52]),"+f"(d[53]),"+f"(d[54]),"+f"(d[55]),"+f"(d[56]),
          "+f"(d[57]),"+f"(d[58]),"+f"(d[59]),"+f"(d[60]),"+f"(d[61]),"+f"(d[62]),"+f"(d[63])
        : "r"(pa[0]), "r"(pa[1]), "r"(pa[2]), "r"(pa[3]), "l"(b), "r"(acc));
}

// ARM 1 — desc/desc, BN=64, single buffered. The register floor of the design.
__global__ void __launch_bounds__(128) _wg_desc_bn64(const __half* q, float* o, int nk) {
    extern __shared__ __half sm[];
    __half* sQ = sm; __half* sK = sQ + 64*128; __half* sV = sK + 64*128; __half* sP = sV + 64*128;
    float sacc[32]; float oacc[64];
#pragma unroll
    for (int i = 0; i < 32; i++) sacc[i] = 0.0f;
#pragma unroll
    for (int i = 0; i < 64; i++) oacc[i] = 0.0f;
    wg_fence();
    uint64_t ad = wg_desc(sQ, 16, 256);
#pragma unroll
    for (int ks = 0; ks < 8; ks++)
        wg_s64(sacc, ad + (ks * 2), wg_desc(sK + ks * 16, 16, 256), ks != 0);
    wg_commit();
    wg_wait<0>();
    wg_fence();
    uint64_t pd = wg_desc(sP, 16, 128);
#pragma unroll
    for (int ks = 0; ks < 4; ks++)
        wg_o128(oacc, pd + (ks * 2), wg_desc(sV + ks * 16, 16, 256), ks != 0);
    wg_commit();
    wg_wait<0>();
    if (nk > 0) o[threadIdx.x] = oacc[0] + sacc[0];
}

// ARM 2 — desc/desc, BN=32. Same O accumulator, half the S accumulator.
__global__ void __launch_bounds__(128) _wg_desc_bn32(const __half* q, float* o, int nk) {
    extern __shared__ __half sm[];
    __half* sQ = sm; __half* sK = sQ + 64*128; __half* sV = sK + 32*128; __half* sP = sV + 32*128;
    float sacc[16]; float oacc[64];
#pragma unroll
    for (int i = 0; i < 16; i++) sacc[i] = 0.0f;
#pragma unroll
    for (int i = 0; i < 64; i++) oacc[i] = 0.0f;
    wg_fence();
    uint64_t ad = wg_desc(sQ, 16, 256);
#pragma unroll
    for (int ks = 0; ks < 8; ks++)
        wg_s32(sacc, ad + (ks * 2), wg_desc(sK + ks * 16, 16, 256), ks != 0);
    wg_commit();
    wg_wait<0>();
    wg_fence();
    uint64_t pd = wg_desc(sP, 16, 64);
#pragma unroll
    for (int ks = 0; ks < 2; ks++)
        wg_o128(oacc, pd + (ks * 2), wg_desc(sV + ks * 16, 16, 256), ks != 0);
    wg_commit();
    wg_wait<0>();
    if (nk > 0) o[threadIdx.x] = oacc[0] + sacc[0];
}

// ARM 3 — register A-operand for the P@V product (FA2's in-register-P trick), BN=64. Prices what
// it costs to avoid the sP shared round trip: P is packed from the S accumulator's registers,
// which the accumulator already occupies, so the marginal cost should be near zero.
__global__ void __launch_bounds__(128) _wg_regA_bn64(const __half* q, float* o, int nk) {
    extern __shared__ __half sm[];
    __half* sQ = sm; __half* sK = sQ + 64*128; __half* sV = sK + 64*128;
    float sacc[32]; float oacc[64];
#pragma unroll
    for (int i = 0; i < 32; i++) sacc[i] = 0.0f;
#pragma unroll
    for (int i = 0; i < 64; i++) oacc[i] = 0.0f;
    wg_fence();
    uint64_t ad = wg_desc(sQ, 16, 256);
#pragma unroll
    for (int ks = 0; ks < 8; ks++)
        wg_s64(sacc, ad + (ks * 2), wg_desc(sK + ks * 16, 16, 256), ks != 0);
    wg_commit();
    wg_wait<0>();
    wg_fence();
#pragma unroll
    for (int ks = 0; ks < 4; ks++) {
        unsigned pa[4];
#pragma unroll
        for (int i = 0; i < 4; i++) {
            __half2 h = __floats2half2_rn(sacc[ks * 8 + i * 2], sacc[ks * 8 + i * 2 + 1]);
            pa[i] = *reinterpret_cast<unsigned*>(&h);
        }
        wg_o128_regA(oacc, pa, wg_desc(sV + ks * 16, 16, 256), ks != 0);
    }
    wg_commit();
    wg_wait<0>();
    if (nk > 0) o[threadIdx.x] = oacc[0] + sacc[0];
}
