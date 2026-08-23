// tc_rt_kernels.cu — the RUNTIME-LOADED half of the tensor-core escape hatch (campaign angle 1
// + angle 2). Compiled by scripts/build_tc_probe.sh to PTX (`nvcc -ptx -arch=compute_80`),
// embedded into the shim as a byte array, and loaded at runtime with the DRIVER API
// (cuModuleLoadData -> driver-internal ptxas JIT -> cuLaunchKernel) — NO link-time coupling
// between the kernels and the Mojo binary whatsoever. The Mojo binary links only the tiny C
// shim; the kernels ship as embedded PTX (or could ship as a .cubin sidecar / a file path —
// the loader call is the same).
//
// Why two kernels:
//  * tc_rt_vadd — the minimal interop proof: a runtime-loaded kernel launched on buffers
//    allocated by Mojo's CUDA context. If this is bit-correct, driver-API dispatch on
//    Mojo-owned device pointers works end-to-end.
//  * tc_rt_mma_gemm — the REAL escape hatch: a hand-written mma.sync.m16n8k16 f16->f32 tiled
//    GEMM. No cuBLAS, no CUTLASS — inline tensor-core PTX we emit ourselves. C[M,N](f32) =
//    A[M,K](f16) @ W[N,K](f16)^T, the residentk [n,k] weight convention, matching the cuBLAS
//    arms so the probe compares all three on identical inputs.
//
// mma.sync.m16n8k16 fragment layout (PTX ISA, Ampere+): D[16x8](f32) = A[16x16](f16, row) x
// B[16x8](f16, col) + C. groupID = lane>>2, tig = lane&3.
//   A: a0 = (row=g,     col=2*tig{,+1});  a1 = (row=g+8, col=2*tig{,+1});
//      a2 = (row=g,     col=2*tig+8{,+1}); a3 = (row=g+8, col=2*tig+8{,+1}).
//      (.f16x2 registers; the register ORDER is row-pair-first: {a0,a1} cover cols 0-7 of
//      rows g/g+8, {a2,a3} cover cols 8-15. The first probe iteration swapped a1/a2 — the
//      standalone identity-B debug harness caught it: rows 8-15 rendered transposed from
//      rows 0-7's col+8 data — and this order is the measured-correct one.)
//   B: b0 at k=2*tig{+0,+1}, n=groupID; b1 at k+8.  (col-major k x n == our [n,k] row-major
//      weight memory viewed with ld=K — the SAME trick the cuBLAS arm uses)
//   D: c0/c1 at row=groupID, col=2*tig{,+1}; c2/c3 at row+8.

extern "C" __global__ void tc_rt_vadd(const float* __restrict__ a, const float* __restrict__ b,
                                      float* __restrict__ c, long n) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long stride = (long)gridDim.x * blockDim.x;
    for (; i < n; i += stride) c[i] = a[i] + b[i];
}

// One block = 128 threads = 4 warps; block tile BM=64 x BN=32, K-step BK=16.
// Warp w owns rows [16w, 16w+16) x all 32 cols (4 n8-tiles -> 4 mmas per k-step per warp).
// Smem tiles staged cooperatively with coalesced 32-bit (half-pair) global loads; fragment
// reads are conflict-light (row stride 20 halves = 10 words: the two 8-apart row groups land
// 16 banks apart, same-group reads are broadcasts).
#define TC_BM 64
#define TC_BN 32
#define TC_BK 16
#define TC_SA 20  // smem row stride in halves for both tiles (10 words; see header comment)

extern "C" __global__ void tc_rt_mma_gemm(const unsigned short* __restrict__ A,
                                          const unsigned short* __restrict__ W,
                                          float* __restrict__ C, int M, int K, int N) {
    const int m0 = blockIdx.y * TC_BM;
    const int n0 = blockIdx.x * TC_BN;
    const int tid = threadIdx.x;
    const int warp = tid >> 5;
    const int lane = tid & 31;
    const int g = lane >> 2;
    const int tig = lane & 3;

    __shared__ unsigned short sa[TC_BM * TC_SA];
    __shared__ unsigned short sw[TC_BN * TC_SA];

    float acc[4][4];
#pragma unroll
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) acc[i][j] = 0.0f;

    for (int k0 = 0; k0 < K; k0 += TC_BK) {
        // ── cooperative stage: A tile 64x16 (512 half-pairs), W tile 32x16 (256 half-pairs) ──
#pragma unroll
        for (int i = 0; i < 4; i++) {
            int idx = tid + i * 128;         // uint32 index into the A tile
            int row = idx >> 3;              // 8 half-pairs per row
            int c2 = (idx & 7) << 1;         // half column of the pair
            unsigned v = 0;
            if (m0 + row < M) {
                v = *(const unsigned*)(A + (size_t)(m0 + row) * K + k0 + c2);
            }
            *(unsigned*)(sa + row * TC_SA + c2) = v;
        }
#pragma unroll
        for (int i = 0; i < 2; i++) {
            int idx = tid + i * 128;
            int row = idx >> 3;
            int c2 = (idx & 7) << 1;
            unsigned v = 0;
            if (n0 + row < N) {
                v = *(const unsigned*)(W + (size_t)(n0 + row) * K + k0 + c2);
            }
            *(unsigned*)(sw + row * TC_SA + c2) = v;
        }
        __syncthreads();

        // ── A fragments for this warp's 16 rows (same for all 4 n-tiles). Register order
        //    per the PTX ISA table: a0=(g, c), a1=(g+8, c), a2=(g, c+8), a3=(g+8, c+8). ──
        unsigned a0 = *(const unsigned*)(sa + (warp * 16 + g) * TC_SA + 2 * tig);
        unsigned a1 = *(const unsigned*)(sa + (warp * 16 + g + 8) * TC_SA + 2 * tig);
        unsigned a2 = *(const unsigned*)(sa + (warp * 16 + g) * TC_SA + 2 * tig + 8);
        unsigned a3 = *(const unsigned*)(sa + (warp * 16 + g + 8) * TC_SA + 2 * tig + 8);

#pragma unroll
        for (int nt = 0; nt < 4; nt++) {
            int nrow = nt * 8 + g;
            unsigned b0 = *(const unsigned*)(sw + nrow * TC_SA + 2 * tig);
            unsigned b1 = *(const unsigned*)(sw + nrow * TC_SA + 2 * tig + 8);
            asm volatile(
                "mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32 "
                "{%0,%1,%2,%3}, {%4,%5,%6,%7}, {%8,%9}, {%0,%1,%2,%3};"
                : "+f"(acc[nt][0]), "+f"(acc[nt][1]), "+f"(acc[nt][2]), "+f"(acc[nt][3])
                : "r"(a0), "r"(a1), "r"(a2), "r"(a3), "r"(b0), "r"(b1));
        }
        __syncthreads();
    }

    // ── epilogue: D[m,n] row-major, ld = N ──
#pragma unroll
    for (int nt = 0; nt < 4; nt++) {
        int col = n0 + nt * 8 + 2 * tig;
        int r0 = m0 + warp * 16 + g;
        if (r0 < M && col < N) C[(size_t)r0 * N + col] = acc[nt][0];
        if (r0 < M && col + 1 < N) C[(size_t)r0 * N + col + 1] = acc[nt][1];
        if (r0 + 8 < M && col < N) C[(size_t)(r0 + 8) * N + col] = acc[nt][2];
        if (r0 + 8 < M && col + 1 < N) C[(size_t)(r0 + 8) * N + col + 1] = acc[nt][3];
    }
}
