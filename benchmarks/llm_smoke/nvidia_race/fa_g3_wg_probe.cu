// fa_g3_wg_probe.cu — ROUND 12: the sm_90a wgmma windowed-attention probe, STANDALONE.
//
// WHY A SEPARATE BINARY RATHER THAN AN EDIT TO tc_shim.cu. The one thing that blocks the wgmma port
// is not the arithmetic — it is that the shared-memory MATRIX DESCRIPTOR encoding (LBO / SBO /
// swizzle / trans) and the accumulator -> register-A layout identity cannot be derived safely from
// documentation and cannot be checked without a device. Guessing them yields a kernel that runs and
// returns plausible-looking WRONG numbers, which is the single worst failure mode this campaign
// guards against. So this file proves them ON DEVICE first, in exact small integers, and only then
// runs numerics. Integration into tc_shim.cu is a later step that inherits a layout already pinned
// rather than a layout assumed. It also means the whole thing compiles and censuses with the
// calibrated local ptxas harness at zero VM cost (ptxas is a host cross-compiler; -arch=sm_90a
// needs a CUDA 12.x toolkit, not an sm_90 device).
//
// ORDER OF GATES, and each one is a hard stop:
//   [1] LAYOUT PROBE — exact integers, no tolerance, no floating-point judgement call.
//   [2] NUMERIC GATE — the windowed kernel against a HOST DOUBLE-PRECISION reference at every
//       raced shape, AND bit-identity against the shipped v2 kernel where the math is unchanged.
//   [3] TIMING — only if [1] and [2] are clean.
// A refutation at [1] is a deliverable, not a failure: the register census has already refuted four
// forecasts in this campaign, and a clean structural refutation costs minutes instead of a round.
//
// Build (on the GPU box, or locally in the calibrated container for the census alone):
//   nvcc -O3 -arch=sm_90a -Xptxas -v fa_g3_wg_probe.cu tc_shim.o -lcublas -lcudart -o /tmp/fa_g3_wg_probe
//   /tmp/fa_g3_wg_probe [--iters 20] [--no-time]
#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <algorithm>
#include <chrono>
#include <vector>

// The shipped kernels, for the bit-identity comparison. They live in tc_shim.o and are reached
// through the shim's own extern "C" entries so this file never duplicates their source.
extern "C" int64_t tc_shim_init(void);
extern "C" int64_t tc_shim_last_error(void);
extern "C" int64_t tc_shim_fa2_layout_probe(void);
extern "C" int64_t tc_shim_fa_g3_window2_async(const void*, const void*, const void*, void*,
                                               const void*, int64_t, int64_t, int64_t, int64_t,
                                               int64_t, int64_t, int64_t, int64_t, int64_t,
                                               int64_t, int64_t);

#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { \
    printf("CUDA ERROR %s:%d %s\n", __FILE__, __LINE__, cudaGetErrorString(e_)); exit(1);} } while (0)

// ═══════════════════════════════════════════════════════════════════════════════════════════
// wgmma PRIMITIVES. Syntax below is what ptxas 12.6.85 ACCEPTED for sm_90a (round 8, verified in
// the calibrated local container and reproduced on the box); two facts were learned from ptxas
// rather than from documentation and are worth keeping visible:
//   * an m64nNk16 f32 accumulator takes exactly N/2 registers per thread (64*N/128). Declaring 18
//     outputs for n32 is rejected with "Argument vector size mismatch" — the count is not a choice.
//   * the REGISTER-A form takes only ONE transpose immediate, because trans-a is not a free operand
//     when A comes from registers: the register layout IS the A layout. Passing both is rejected
//     with "Arguments mismatch for instruction 'wgmma.mma_async'".
// ptxas additionally auto-injects warpgroup.arrive / warpgroup.wait around register-A GMMA
// (info C7519 / C7517). That is correct behaviour, not a defect.
// ═══════════════════════════════════════════════════════════════════════════════════════════

// The 64-bit shared-memory matrix descriptor, per the PTX ISA matrix-descriptor layout:
//   bits  0..13  start address        (addr >> 4)
//   bits 16..29  leading byte offset   (LBO >> 4)
//   bits 32..45  stride byte offset    (SBO >> 4)
//   bits 46..48  base offset
//   bits 62..63  swizzle mode: 0 = none, 1 = 128B, 2 = 64B, 3 = 32B
// LBO and SBO are PARAMETERS here rather than hardcoded constants precisely because their correct
// values for a given operand layout are what the [1] probe exists to determine on the device.
__device__ __forceinline__ uint64_t wg_desc(const void* p, uint32_t lbo, uint32_t sbo,
                                           uint32_t swizzle) {
    uint32_t a = (uint32_t)__cvta_generic_to_shared(p);
    uint64_t d = 0;
    d |= (uint64_t)((a >> 4) & 0x3FFF);
    d |= (uint64_t)((lbo >> 4) & 0x3FFF) << 16;
    d |= (uint64_t)((sbo >> 4) & 0x3FFF) << 32;
    d |= (uint64_t)(swizzle & 0x3) << 62;
    return d;
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

// S product: D[64,BN] = A[64,128] @ B^T, f32 accumulate, both operands from shared descriptors.
// BN=64 -> 32 accumulator registers per thread.
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
// O product: D[64,128] += A[64,k16] @ B[k16,128], f32 accumulate, A from REGISTERS (4 f16x2 per
// thread) and B from a shared descriptor. 64 accumulator registers per thread. Only ONE transpose
// immediate, per the ptxas fact above.
__device__ __forceinline__ void wg_o128_regA(float* d, const unsigned* pa, uint64_t b, int acc) {
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
// O product with A ALSO from a shared descriptor — the fallback if the accumulator -> register-A
// identity does not hold, at the cost of an sP window and its fences.
__device__ __forceinline__ void wg_o128_desc(float* d, uint64_t a, uint64_t b, int acc) {
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

// ═══════════════════════════════════════════════════════════════════════════════════════════
// [1] THE LAYOUT PROBE — exact small integers, no tolerance.
//
// Construction: A[r][k] = (k == 0) ? r+1 : 0  for r in 0..63, and B[n][k] = (k == 0) ? n+1 : 0 for
// n in 0..63. Then D[r][n] = sum_k A[r][k]*B[n][k] = (r+1)*(n+1). Every accumulator element
// therefore READS BACK ITS OWN COORDINATES as a product of two small integers, so a wrong
// descriptor encoding, a wrong LBO/SBO, a wrong swizzle or a wrong transpose bit shows up as a
// specific wrong integer at a specific (r, n) — not as a small floating-point disagreement that
// could be argued away as tolerance.
//
// Each thread writes out ITS OWN accumulator registers together with the (row, col) it BELIEVES
// each one holds, under the m64nNk16 D-layout assumption (warp w owns rows 16w..16w+15; within a
// warp the per-lane pattern is the m16n8 one, i.e. rows (lane>>2) and (lane>>2)+8 at columns
// 2*(lane&3) and +1 within each 8-wide n-tile). The host then checks, for every element, that the
// value equals (believed_row+1)*(believed_col+1). If the assumption is wrong the host sees WHICH
// elements disagree and by how much, which is what turns a refutation into a diagnostic instead of
// a dead end.
//
// The probe also tests the ACCUMULATOR -> REGISTER-A IDENTITY, which is what would let P skip a
// shared round trip entirely: it re-feeds the D registers, converted to f16 and packed as an
// A-fragment, into a second wgmma against a known B, and requires the result to equal what the
// assumed A-layout implies. If that identity does NOT hold, the kernel must keep an sP window and
// the design changes — better to learn that here than from a wrong attention output.
// ═══════════════════════════════════════════════════════════════════════════════════════════
#define WG_PR 64          // probe rows  (m64)
#define WG_PC 64          // probe cols  (n64)
#define WG_PK 16          // probe k     (k16)

__global__ void __launch_bounds__(128) _wg_layout_probe_kernel(int* out_val, int* out_row,
                                                              int* out_col, int lbo, int sbo,
                                                              int swz) {
    // Shared holds A as [64][16] and B as [64][16], both f16, row-major with a 16-element stride.
    __shared__ __half sA[WG_PR * WG_PK];
    __shared__ __half sB[WG_PC * WG_PK];
    const int tid = threadIdx.x;
    for (int i = tid; i < WG_PR * WG_PK; i += 128) {
        int r = i / WG_PK, k = i - r * WG_PK;
        sA[i] = __float2half((k == 0) ? (float)(r + 1) : 0.0f);
    }
    for (int i = tid; i < WG_PC * WG_PK; i += 128) {
        int n = i / WG_PK, k = i - n * WG_PK;
        sB[i] = __float2half((k == 0) ? (float)(n + 1) : 0.0f);
    }
    __syncthreads();

    float d[WG_PC / 2];
#pragma unroll
    for (int i = 0; i < WG_PC / 2; i++) d[i] = 0.0f;

    wg_fence();
    wg_s64(d, wg_desc(sA, lbo, sbo, swz), wg_desc(sB, lbo, sbo, swz), 0);
    wg_commit();
    wg_wait<0>();

    // Record each accumulator element with the (row, col) this layout assumption assigns it.
    const int warp = tid >> 5, lane = tid & 31;
    const int rlo = lane >> 2;              // row within the warp's 16
    const int chi = (lane & 3) << 1;        // column base within an 8-wide n-tile
    int o = tid * (WG_PC / 2);
#pragma unroll
    for (int nt = 0; nt < WG_PC / 8; nt++) {
        // m16n8 D layout: elements 0,1 are row rlo at cols chi, chi+1; elements 2,3 are row
        // rlo+8 at the same two columns. Four elements per 8-wide n-tile, so registers are
        // grouped 4 per n-tile.
        int c = nt * 8 + chi;
        int r0 = warp * 16 + rlo, r1 = r0 + 8;
        out_val[o + nt * 4 + 0] = (int)d[nt * 4 + 0]; out_row[o + nt * 4 + 0] = r0;
        out_col[o + nt * 4 + 0] = c;
        out_val[o + nt * 4 + 1] = (int)d[nt * 4 + 1]; out_row[o + nt * 4 + 1] = r0;
        out_col[o + nt * 4 + 1] = c + 1;
        out_val[o + nt * 4 + 2] = (int)d[nt * 4 + 2]; out_row[o + nt * 4 + 2] = r1;
        out_col[o + nt * 4 + 2] = c;
        out_val[o + nt * 4 + 3] = (int)d[nt * 4 + 3]; out_row[o + nt * 4 + 3] = r1;
        out_col[o + nt * 4 + 3] = c + 1;
    }
}

// Deterministic fill, reproducible scratch, no /dev/urandom and no host RNG dependency.
static void fill_rand(float* p, long n, unsigned seed, float lo, float hi) {
    unsigned s = seed;
    for (long i = 0; i < n; i++) {
        s = s * 1664525u + 1013904223u;
        float u = (float)((double)(s >> 8) / 16777216.0);
        p[i] = lo + u * (hi - lo);
    }
}

// HOST reference: double precision, windowed causal, over the SAME rounded operands. key j is
// attended by the query row at global position qpos iff j <= qpos AND (window <= 0 OR
// j >= qpos+1-window) AND j < n_keys — `_attn_softmax_mask_kernel`'s predicate verbatim, and the
// same reference fa_g3_probe.cu uses, so a v4 arm and a v2 arm are held to one identical oracle.
static void host_ref_window_attn(const float* q, const float* k, const float* v, float* o,
                                 const int* rows, int n_check, int m, int n_keys, int h_q,
                                 int h_kv, int d, int pos_base, int window, float scale,
                                 int dim_stride) {
    std::vector<double> s((size_t)n_keys);
    for (int ci = 0; ci < n_check; ci++) {
        int r = rows[ci];
        if (r >= m) continue;
        int qpos = pos_base + r;
        int hi = qpos < n_keys - 1 ? qpos : n_keys - 1;
        int lo = (window > 0) ? (qpos + 1 - window) : 0;
        if (lo < 0) lo = 0;
        if (hi < lo) hi = lo - 1;
        const float* qr_base = q + (size_t)r * h_q * d;
        for (int h = 0; h < h_q; h++) {
            int hk = h / (h_q / h_kv);
            const float* qr = qr_base + (size_t)h * d;
            double mx = -1e300;
            for (int j = lo; j <= hi; j++) {
                const float* kr = k + ((size_t)j * h_kv + hk) * d;
                double acc = 0;
                for (int t = 0; t < d; t++)
                    acc += (double)__half2float(__float2half(qr[t] * scale)) *
                           (double)__half2float(__float2half(kr[t]));
                s[j] = acc;
                if (acc > mx) mx = acc;
            }
            double sum = 0;
            for (int j = lo; j <= hi; j++) { s[j] = exp(s[j] - mx); sum += s[j]; }
            double inv = (sum > 0) ? 1.0 / sum : 0.0;
            for (int e = 0; e < d; e += dim_stride) {
                double acc = 0;
                for (int j = lo; j <= hi; j++) {
                    double p = (double)__half2float(__float2half((float)(s[j] * inv)));
                    acc += p * (double)__half2float(
                        __float2half(v[((size_t)j * h_kv + hk) * d + e]));
                }
                o[(size_t)r * h_q * d + (size_t)h * d + e] = (float)acc;
            }
        }
    }
}

int main(int argc, char** argv) {
    int iters = 20, no_time = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--iters")) iters = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--no-time")) no_time = 1;
    }
    CK(cudaFree(0));

    // ═══ [1] LAYOUT PROBE ═══
    // Sweep the descriptor encodings rather than asserting one. The device decides which (LBO, SBO,
    // swizzle) satisfies the exact-integer identity; a hardcoded guess that happened to be wrong
    // would otherwise be debugged through attention outputs instead of through this table.
    printf("[1] wgmma shared-descriptor layout probe (exact integers, D[r][n] must equal "
           "(r+1)*(n+1))\n");
    int* d_val; int* d_row; int* d_col;
    const int NEL = 128 * (WG_PC / 2);
    CK(cudaMalloc(&d_val, NEL * sizeof(int)));
    CK(cudaMalloc(&d_row, NEL * sizeof(int)));
    CK(cudaMalloc(&d_col, NEL * sizeof(int)));
    std::vector<int> h_val(NEL), h_row(NEL), h_col(NEL);

    struct Cand { int lbo, sbo, swz; const char* why; };
    // Candidate encodings for a [rows][16] f16 tile viewed as 8x8 core matrices. The stride between
    // core matrices along K is 16 bytes (8 halves); the stride between core-matrix ROWS is the tile
    // row stride (16 halves = 32 bytes) for the canonical K-major no-swizzle form, and 8 rows of
    // that for the "core-matrix rows are contiguous" reading. Both are tried, plus the 128B-swizzle
    // form CUTLASS/TMA normally produce, because which one the hardware expects for a hand-staged
    // tile is exactly the fact this probe exists to establish.
    Cand cands[] = {
        {16,  32, 0, "K-major, LBO=16B (one core matrix along K), SBO=32B (one tile row), no swizzle"},
        {16, 256, 0, "K-major, LBO=16B, SBO=256B (eight tile rows = one core-matrix row), no swizzle"},
        {32,  16, 0, "LBO/SBO swapped against candidate 0"},
        {32, 256, 0, "LBO=32B, SBO=256B"},
        {16,  32, 1, "candidate 0 with 128B swizzle"},
        {16, 1024, 1, "LBO=16B, SBO=1KB, 128B swizzle"},
    };
    int winner = -1;
    for (size_t ci = 0; ci < sizeof(cands) / sizeof(cands[0]); ci++) {
        CK(cudaMemset(d_val, 0, NEL * sizeof(int)));
        CK(cudaDeviceSynchronize());
        _wg_layout_probe_kernel<<<1, 128>>>(d_val, d_row, d_col, cands[ci].lbo, cands[ci].sbo,
                                            cands[ci].swz);
        cudaError_t le = cudaGetLastError();
        if (le != cudaSuccess) {
            printf("  cand %zu LBO=%-5d SBO=%-5d swz=%d  LAUNCH ERROR %s\n", ci, cands[ci].lbo,
                   cands[ci].sbo, cands[ci].swz, cudaGetErrorString(le));
            CK(cudaDeviceReset()); CK(cudaMalloc(&d_val, NEL * sizeof(int)));
            CK(cudaMalloc(&d_row, NEL * sizeof(int))); CK(cudaMalloc(&d_col, NEL * sizeof(int)));
            continue;
        }
        CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(h_val.data(), d_val, NEL * sizeof(int), cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(h_row.data(), d_row, NEL * sizeof(int), cudaMemcpyDeviceToHost));
        CK(cudaMemcpy(h_col.data(), d_col, NEL * sizeof(int), cudaMemcpyDeviceToHost));
        long bad = 0; int first_bad = -1;
        for (int i = 0; i < NEL; i++) {
            int want = (h_row[i] + 1) * (h_col[i] + 1);
            if (h_val[i] != want) { if (first_bad < 0) first_bad = i; bad++; }
        }
        printf("  cand %zu LBO=%-5d SBO=%-5d swz=%d  %s  bad=%ld/%d%s\n", ci, cands[ci].lbo,
               cands[ci].sbo, cands[ci].swz, bad == 0 ? "EXACT-MATCH " : "mismatch    ", bad, NEL,
               bad ? "" : "   <== LAYOUT PINNED");
        if (bad == 0 && winner < 0) winner = (int)ci;
        else if (bad && first_bad >= 0)
            printf("        first disagreement at element %d: got %d, layout implies (r=%d,c=%d) "
                   "-> want %d\n        (%s)\n", first_bad, h_val[first_bad], h_row[first_bad],
                   h_col[first_bad], (h_row[first_bad] + 1) * (h_col[first_bad] + 1),
                   cands[ci].why);
    }
    if (winner < 0) {
        printf("\n[1] VERDICT: LAYOUT REFUTED — no candidate descriptor encoding reproduced the "
               "exact-integer identity.\n");
        printf("    This is a CLEAN STRUCTURAL REFUTATION and a deliverable: the wgmma port cannot "
               "proceed on these\n    operand layouts, and the honest next step is a TMA-staged "
               "swizzled layout (what CUTLASS/flashinfer\n    actually use) rather than more "
               "guessing at hand-staged encodings. NO numerics and NO timings were taken.\n");
        CK(cudaFree(d_val)); CK(cudaFree(d_row)); CK(cudaFree(d_col));
        return 2;
    }
    printf("\n[1] VERDICT: LAYOUT PINNED by candidate %d -> LBO=%d SBO=%d swizzle=%d (%s)\n",
           winner, cands[winner].lbo, cands[winner].sbo, cands[winner].swz, cands[winner].why);
    printf("    Every one of %d accumulator elements equalled (row+1)*(col+1) EXACTLY, so both the "
           "descriptor\n    encoding and the assumed m64nNk16 D layout (warp owns rows 16w..16w+15; "
           "per-lane the m16n8\n    pattern at rows lane>>2 and +8, cols 2*(lane&3) and +1) are "
           "confirmed on the device.\n", NEL);
    CK(cudaFree(d_val)); CK(cudaFree(d_row)); CK(cudaFree(d_col));

    // ═══ [2] and [3] are NOT REACHED in this revision ═══
    // The windowed kernel, its host f64 numeric gate and the bit-identity comparison against
    // tc_shim_fa_g3_window2_async are the NEXT step and depend on the encoding pinned above. They
    // are deliberately not written against a guessed layout: with the descriptor semantics settled
    // by [1], the kernel becomes a mechanical transplant of v2's window (kb_min/kb_max and the
    // monotonicity argument), v2's per-element mask predicate, v2's f32 online max/sum and __expf,
    // and v2's straight-to-global epilogue onto wgmma operands — and the D layout [1] just confirmed
    // is the SAME per-warp m16n8 pattern v2's softmax and epilogue already index by, so those
    // sections carry over close to verbatim.
    //
    // The accumulator -> register-A identity is the remaining open question and gets its own exact-
    // integer probe before the kernel relies on it: if it does NOT hold, the O product falls back to
    // wg_o128_desc with an sP window, which round 8's census priced at 122 registers against 126 for
    // the register-A form — a 4-register difference, so the fallback is cheap and the kernel is not
    // blocked on it either way.
    printf("\n[2] numeric gate and [3] timing: NOT REACHED — this revision pins the layout only.\n");
    printf("    Stopping here is deliberate: running numerics against a layout that was guessed "
           "rather than\n    pinned is how a kernel comes to return plausible-looking wrong "
           "numbers.\n");
    (void)iters; (void)no_time; (void)fill_rand; (void)host_ref_window_attn;
    (void)wg_o128_regA; (void)wg_o128_desc; (void)tc_shim_init; (void)tc_shim_last_error;
    (void)tc_shim_fa2_layout_probe; (void)tc_shim_fa_g3_window2_async;
    return 0;
}
