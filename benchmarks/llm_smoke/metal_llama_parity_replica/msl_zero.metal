/* msl_zero.metal -- beat-llama.cpp campaign concurrent front, round 3 increment 2 (2026-08-12):
 * a minimal float-buffer zero kernel for the batched decode table's split-K qkv substitution.
 *
 * WHY: qkv_proj in the batched table is being moved to the split-K MSL GEMM (msl_splitk8, S=8:
 * grid 64x8=512 threadgroups instead of 64 = the round-2 counter probe's next underfill victim,
 * 6.59 ms per B=32 step). The split-K epilogue atomic-ADDS its S partials into dst -- exactly the
 * residual-safe "+=" semantics it was written for -- so for a SCRATCH role like qkv (dst holds no
 * residual) the buffer must be zeroed once per layer before the split-K dispatch. This kernel is
 * that zeroing: one float4 store per thread, n_elem guard tail, same gpuAddress-pointer ABI as
 * every other MSL kernel in this directory (constant ulong address + int64 scalar; the batch shim
 * binds pointers as 8-byte device addresses via setBytes).
 *
 * ABI: buffer(0) = dst gpuAddress (float*), buffer(1) = n_elem (int64, number of floats).
 * Grid: ceil(ceil(n_elem/4)/256) threadgroups x 256 threads (set by the session's descriptor).
 *
 * Ships as its OWN one-kernel metallib blob (batch_shim registers functionNames[0] of each MTLB):
 *   xcrun -sdk macosx metal -c msl_zero.metal -o /tmp/msl_zero.air
 *   xcrun -sdk macosx metallib /tmp/msl_zero.air -o /tmp/msl_zero.metallib
 *   python3 mma_forge/tools/extract_blob.py /tmp/msl_zero.metallib \
 *       mma_forge/generated/msl_zero_blob.c --symbol algenta_msl_zero_blob
 */
#include <metal_stdlib>
using namespace metal;

kernel void msl_zero_f32(
        constant ulong & dst_addr [[buffer(0)]],
        constant long  & n_elem   [[buffer(1)]],
        uint gid [[thread_position_in_grid]]) {
    device float * dst = reinterpret_cast<device float *>(dst_addr);
    long i = (long)gid * 4;
    if (i + 4 <= n_elem) {
        *(device float4 *)(dst + i) = float4(0.0f);
    } else {
        for (long j = i; j < n_elem; j++) {
            dst[j] = 0.0f;
        }
    }
}
