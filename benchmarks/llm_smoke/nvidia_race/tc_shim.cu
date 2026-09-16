// tc_shim.cu — the NVIDIA tensor-core escape hatch: a hand-written, nvcc-compiled CUDA shim
// (cuBLAS HMMA GEMM + inline WMMA smoke + packed3->f16 dequant) exposing a plain extern "C"
// ABI, designed to be linked into a Mojo CUDA binary the same way the Metal serving path
// links its hand-written .metal batch shim (`-Xlinker tc_shim.o`, the exact CUDA analog of the
// `-Xlinker batch_shim.o -Xlinker -framework -Xlinker Metal` recipe REALRACE_RESULTS.md's
// Metal lanes already ship).
//
// WHY THIS FILE EXISTS
// --------------------
// The pinned Mojo 1.0.0 / MAX 26.5.0 CUDA backend exposes NO tensor-core mma surface
// (mma_surface_probe.sh: every std/max mma/wgmma import compile-FAILS; no inline-asm hatch)
// and scalarizes every sub-f32 SIMD load (f16 5-7% of peak, int8 1-2%). llama.cpp's prefill
// wins on cuBLAS HMMA (A100 autopsy: ampere_h16816gemm, 14.7 ms over the 895-token prefill;
// tensor pipe 26.8-52.3% inside its 128x128 tiles, vs our tensor 0.00-0.01%). This shim is
// the probe that decides, with MEASURED numbers, whether an nvcc-compiled tensor-core object
// can live inside a Mojo CUDA binary and be dispatched from Mojo — the decision gate for an
// integration round, nothing more. No session changes live here.
//
// THE ABI (matches tc_escape_probe.mojo's external_call signatures byte-for-byte)
// --------------------------------------------------------------------------------
// Every entry returns int64_t: 0 = success, negative = shim-defined error class, positive =
// the raw cudaError_t / cublasStatus_t code. All buffer arguments are DEVICE addresses owned
// by the Mojo side (DeviceBuffer.unsafe_ptr() -> Int) — the shim allocates NOTHING itself, so
// every byte of GPU memory stays inside Mojo's allocator/context. The only shim-owned CUDA
// objects are the cuBLAS handle (and its optional stream).
//
// SYNC/INTEROP STRATEGY (the measured seam)
// ------------------------------------------
// MAX's DeviceContext/DeviceStream surface exposes no raw cudaStream_t (round-3 measured API
// map: only create_event / record_event / enqueue_wait_for / synchronize). So the probe seam
// is: Mojo ctx.synchronize() -> external_call -> shim runs on its OWN stream (created
// cudaStreamNonBlocking, or the caller's) and cudaStreamSynchronize's before returning ->
// Mojo enqueues the next wave. Prefill waves are synchronous admissions, so a device-sync seam
// per GEMM wave is structurally acceptable for this probe; an integration round decides
// whether the seam moves to per-layer or per-wave.
//
// GEMM LAYOUT CONTRACT
// --------------------
// C[M,N] = A[M,K] @ W[N,K]^T, ALL row-major, f32 device pointers in/out — the exact residentk
// convention (`_pf_gemm_assign_kernel_v2`: `y[M,n] = xn[M,k] @ W^T[k,n]`, `w` stored `[n,k]`).
// Internally: A and W are converted to f16 staging (once per call for A; W staging is a
// session-open concern, exposed here as tc_shim_f32_to_f16), then cublasGemmEx. cuBLAS is
// column-major; a row-major [M,K] matrix IS a column-major [K,M] matrix on the same pointer,
// so with m=N, n=M, k=K (C_cm is N x M, ldc=N):
//   * W_rm[N,K] == W_cm[K,N]: needs op(A) = N x K  -> transa = OP_T, lda = K (>= k)
//   * A_rm[M,K] == A_cm[K,M]: needs op(B) = K x M  -> transb = OP_N, ldb = K (>= k)
// i.e. cublasGemmEx(handle, OP_T, OP_N, N, M, K, alpha, W16, ld=K, A16, ld=K, beta, C16, ld=N).
// (First run got this wrong — OP_N on W fails the lda >= m check with m=N; the probe's
//  INVALID_VALUE status caught it before any numbers were published.)
//
// Build (on the GPU VMs, CUDA 12.6):
//   nvcc -O3 -arch=sm_90 -Xcompiler -fPIC -c tc_shim.cu -o tc_shim_sm90.o   # H100
//   nvcc -O3 -arch=sm_80 -Xcompiler -fPIC -c tc_shim.cu -o tc_shim_sm80.o   # A100
// Link (mojo build driver):  -Xlinker tc_shim.o -Xlinker -lcublas -Xlinker -lcudart
// (libcuda.so.1 is dlopen'd for the context diagnostics, never linked; the runtime needs -ldl
// which the Mojo link line already carries. scripts/build_tc_probe.sh does the
// object+clang-link fallback where plain `mojo build -Xlinker` is refused.)

#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cuda_fp16.h>
#include <stdint.h>
#include <stdio.h>

// WMMA smoke (inline tensor-core PTX via the CUDA C++ wmma API — the cutlass-free surface the
// attention probe in item 3 of the campaign brief asks about). mma.h ships with the CUDA
// toolkit; guarded so a toolkit-less emergency build of the GEMM-only shim still compiles.
#ifndef TC_SHIM_NO_WMMA
#include <mma.h>
using namespace nvcuda;
#endif

// ── shim-owned state: the cuBLAS handle + its stream. No device memory. ──────────────────
static cublasHandle_t g_handle = nullptr;
static cudaStream_t g_stream = nullptr;   // dedicated non-blocking stream, lazily created
static cudaStream_t g_stream_own = nullptr;  // the init-time own stream (noseam restores it)
static int g_stream_created = 0;
static int g_noseam = 0;
// NOSEAM mode (-D ALGENTA_TC_NOSEAM on the Mojo side, tc_shim_noseam(1) at session open):
// every integration entry enqueues on the LEGACY DEFAULT stream (cudaStreamLegacy = 0) and
// SKIPS its cudaStreamSynchronize, and the session skips its bracketing ctx.synchronize().
// Ordering then rides the CUDA legacy-stream contract: legacy-stream work serializes with
// every blocking stream of the same context (after all prior blocking-stream work, before
// all subsequent blocking-stream work). If the MAX runtime's enqueue stream turns out to be
// cudaStreamNonBlocking the token-identity gates catch the race; if it is blocking (or the
// legacy stream itself) the per-GEMM sync-seam bubble disappears entirely.
static int64_t g_last_error = 0;

static void record_error(int64_t code) {
    if (code != 0) g_last_error = code;
}

extern "C" int64_t tc_shim_last_error(void) { return g_last_error; }

// Create handle + dedicated stream, enable tensor-op math mode (the latter matters for the
// TF32/f32 arms; GemmEx with 16F types picks HMMA regardless). Idempotent.
extern "C" int64_t tc_shim_init(void) {
    if (g_handle != nullptr) return 0;
    cudaError_t e = cudaFree(0);  // force the runtime to bind the CURRENT (Mojo's) context
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    cublasStatus_t s = cublasCreate(&g_handle);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    e = cudaStreamCreateWithFlags(&g_stream, cudaStreamNonBlocking);
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    g_stream_own = g_stream;
    g_stream_created = 1;
    s = cublasSetStream(g_handle, g_stream);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    s = cublasSetMathMode(g_handle, CUBLAS_TENSOR_OP_MATH);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    return 0;
}

// Stream interop probe: accept a caller-owned cudaStream_t (Mojo cannot name one today — the
// MAX 26.5 surface has no handle accessor — but an integration round that captures graphs or a
// future MAX release may). 0 = use the shim's own stream from tc_shim_init.
extern "C" int64_t tc_shim_use_stream(void* stream_ptr) {
    if (g_handle == nullptr) {
        int64_t r = tc_shim_init();
        if (r != 0) return r;
    }
    cudaStream_t s = (cudaStream_t)stream_ptr;
    cublasStatus_t st = cublasSetStream(g_handle, s);
    if (st != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)st); return -(int64_t)st; }
    g_stream = s;
    g_stream_created = 0;
    return 0;
}

// NOSEAM switch (see the g_noseam note above). on=1: move the handle AND every shim kernel
// launch onto the legacy default stream (g_stream itself is repointed so the in-entry
// f32->f16 A conversion stays ordered with its GemmEx) and skip the per-call syncs; on=0:
// restore the init-time non-blocking stream + the syncs. Returns -1 if never initialized.
extern "C" int64_t tc_shim_noseam(int64_t on) {
    if (g_handle == nullptr) { record_error(-1); return -1; }
    g_noseam = (on != 0) ? 1 : 0;
    g_stream = g_noseam ? (cudaStream_t)0 /* cudaStreamLegacy */ : g_stream_own;
    cublasStatus_t st = cublasSetStream(g_handle, g_stream);
    if (st != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)st); return -(int64_t)st; }
    return 0;
}

extern "C" int64_t tc_shim_stream_sync(void) {
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

extern "C" int64_t tc_shim_device_sync(void) {
    cudaError_t e = cudaDeviceSynchronize();
    record_error((int64_t)e);
    return (int64_t)e;
}

// Interop diagnostics: report (via out params) which CUcontext is CURRENT on the calling
// thread and the device ordinal. The probe compares this against Mojo's side to prove both
// share one context — the precondition that makes Mojo-allocated device pointers legal
// arguments to cuBLAS calls issued by this shim. Uses the driver API (libcuda.so.1, resolved
// via dlopen so the shim's link needs NO -lcuda — the toolkit's libcuda.so is a stub on many
// build hosts) so it observes whatever context is CURRENT, primary or not.
#include <dlfcn.h>

extern "C" int64_t tc_shim_diag(int64_t* out_device, int64_t* out_context_ptr,
                                  int64_t* out_driver_api_ok) {
    int dev = 0;
    cudaError_t e = cudaGetDevice(&dev);
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    *out_device = (int64_t)dev;
    *out_context_ptr = 0;
    *out_driver_api_ok = 0;
    void* h = dlopen("libcuda.so.1", RTLD_NOW | RTLD_NOLOAD);
    if (h == nullptr) h = dlopen("libcuda.so.1", RTLD_NOW);
    if (h == nullptr) return 0;  // diag-only: degrade, don't fail the probe
    typedef int (*cuCtxGetCurrent_t)(void**);
    cuCtxGetCurrent_t getcur = (cuCtxGetCurrent_t)dlsym(h, "cuCtxGetCurrent");
    if (getcur != nullptr) {
        void* c = nullptr;
        int r = getcur(&c);
        *out_context_ptr = (int64_t)(uintptr_t)c;
        *out_driver_api_ok = (r == 0) ? 1 : 0;
    }
    return 0;
}

// ── device conversion kernels (grid-stride, coalesced) ────────────────────────────────────

__global__ void _f32_to_f16_kernel(const float* __restrict__ src, __half* __restrict__ dst,
                                   long n) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long stride = (long)gridDim.x * blockDim.x;
    for (; i < n; i += stride) dst[i] = __float2half(src[i]);
}

__global__ void _f16_to_f32_kernel(const __half* __restrict__ src, float* __restrict__ dst,
                                   long n) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long stride = (long)gridDim.x * blockDim.x;
    for (; i < n; i += stride) dst[i] = __half2float(src[i]);
}

// One-shot f32 -> f16 conversion of an arbitrary device buffer (weight staging at session
// open, or A staging). Launches on the shim's stream; does NOT sync (caller decides).
extern "C" int64_t tc_shim_f32_to_f16(const void* src_f32, void* dst_f16, int64_t n) {
    if (n <= 0) return 0;
    int threads = 256;
    long blocks = (long)((n + threads - 1) / threads);
    if (blocks > 65535) blocks = 65535;
    _f32_to_f16_kernel<<<(unsigned)blocks, threads, 0, g_stream>>>(
        (const float*)src_f32, (__half*)dst_f16, (long)n);
    cudaError_t e = cudaGetLastError();
    record_error((int64_t)e);
    return (int64_t)e;
}

// ── FRONT 4 lever 2, part (a): the SAME conversion, 8 elements per thread. ─────────────────
// The scalar grid-stride form above moves one 4-byte load and one 2-byte store per thread per
// iteration. Measured on the RAG-4096 K/V staging it runs at ~170 GB/s = 11% of the A100's
// 1555 GB/s, because a 2-byte store per lane cannot fill a 32-byte sector: consecutive lanes
// write consecutive halves, so a warp's 64 bytes land as two sectors but the LSU issues 32
// separate 2-byte transactions to get there. Two float4 loads and one uint4 store per thread
// give the LSU 16-byte transactions on both sides.
//
// BIT-EXACT, not merely equivalent: `__floats2half2_rn(x, y)` is defined as the
// round-to-nearest-even conversion of each half independently, which is the identical operation
// `__float2half` performs, so every output half is the same bit pattern the scalar kernel
// writes. An unaligned `src`/`dst` (or, defensively, any pointer the 16-byte form cannot
// legally vectorize) falls back to the scalar kernel inside this entry rather than failing, so
// a caller cannot get a different answer by choosing the wrong one.
__global__ void _f32_to_f16_v8_kernel(const float* __restrict__ src, __half* __restrict__ dst,
                                      long n8, long ntail) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long stride = (long)gridDim.x * blockDim.x;
    for (; i < n8; i += stride) {
        const float4 a = *reinterpret_cast<const float4*>(src + i * 8);
        const float4 b = *reinterpret_cast<const float4*>(src + i * 8 + 4);
        uint4 o;
        __half2* h = reinterpret_cast<__half2*>(&o);
        h[0] = __floats2half2_rn(a.x, a.y);
        h[1] = __floats2half2_rn(a.z, a.w);
        h[2] = __floats2half2_rn(b.x, b.y);
        h[3] = __floats2half2_rn(b.z, b.w);
        *reinterpret_cast<uint4*>(dst + i * 8) = o;
    }
    // the sub-8 tail: at most 7 elements, done by block 0's first lanes so `n` need not be a
    // multiple of 8 (the K/V staging always is, the generic A staging need not be)
    if (blockIdx.x == 0 && (long)threadIdx.x < ntail)
        dst[n8 * 8 + threadIdx.x] = __float2half(src[n8 * 8 + threadIdx.x]);
}

extern "C" int64_t tc_shim_f32_to_f16_v8(const void* src_f32, void* dst_f16, int64_t n) {
    if (n <= 0) return 0;
    if ((((uintptr_t)src_f32) | ((uintptr_t)dst_f16)) & 15u)
        return tc_shim_f32_to_f16(src_f32, dst_f16, n);   // alignment fallback, same bits
    long n8 = (long)n >> 3, ntail = (long)n - (n8 << 3);
    int threads = 256;
    long blocks = (n8 + threads - 1) / threads;
    if (blocks < 1) blocks = 1;                 // tail-only call still needs one block
    if (blocks > 65535) blocks = 65535;
    _f32_to_f16_v8_kernel<<<(unsigned)blocks, threads, 0, g_stream>>>(
        (const float*)src_f32, (__half*)dst_f16, n8, ntail);
    cudaError_t e = cudaGetLastError();
    record_error((int64_t)e);
    return (int64_t)e;
}

extern "C" int64_t tc_shim_f16_to_f32(const void* src_f16, void* dst_f32, int64_t n) {
    if (n <= 0) return 0;
    int threads = 256;
    long blocks = (long)((n + threads - 1) / threads);
    if (blocks > 65535) blocks = 65535;
    _f16_to_f32_kernel<<<(unsigned)blocks, threads, 0, g_stream>>>(
        (const __half*)src_f16, (float*)dst_f32, (long)n);
    cudaError_t e = cudaGetLastError();
    record_error((int64_t)e);
    return (int64_t)e;
}

// ── THE core: C[M,N](f32) = A[M,K](f32) @ W[N,K](f32)^T through f16 tensor cores ─────────
// a16/w16/c16 are CALLER-OWNED staging buffers (sizes M*K, N*K, M*N halves). The full arm
// converts A in, converts C out; W arrives ALREADY f16 (dual-residency, session-open cost —
// measured separately). Syncs the shim's stream before returning: the probe seam.
static int64_t gemm_f16_core(const void* a16, const void* w16, void* c16,
                             int64_t M, int64_t K, int64_t N, int f16_accum) {
    __half alpha_h = __float2half(1.0f), beta_h = __float2half(0.0f);
    float alpha_f = 1.0f, beta_f = 0.0f;
    const void* alpha = f16_accum ? (const void*)&alpha_h : (const void*)&alpha_f;
    const void* beta = f16_accum ? (const void*)&beta_h : (const void*)&beta_f;
    cublasComputeType_t ctype = f16_accum ? CUBLAS_COMPUTE_16F : CUBLAS_COMPUTE_32F;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        alpha,
        w16, CUDA_R_16F, (int)K,   // W_rm[N,K] == W_cm[K,N], transposed to N x K
        a16, CUDA_R_16F, (int)K,   // A_rm[M,K] == A_cm[K,M], as-is for K x M
        beta,
        c16, CUDA_R_16F, (int)N,   // C_rm[M,N] == C_cm[N,M], ld = N
        ctype, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// Full seam: f32 A in, f32 C out. W must arrive pre-staged f16 (the integration model).
extern "C" int64_t tc_shim_gemm_f16(const void* a_f32, const void* w_f16,
                                    int64_t M, int64_t K, int64_t N,
                                    void* a16_scratch, void* c16_scratch, void* c_f32,
                                    int64_t f16_accum) {
    int64_t r = tc_shim_f32_to_f16(a_f32, a16_scratch, M * K);
    if (r != 0) return r;
    r = gemm_f16_core(a16_scratch, w_f16, c16_scratch, M, K, N, (int)f16_accum);
    if (r != 0) return r;
    r = tc_shim_f16_to_f32(c16_scratch, c_f32, M * N);
    if (r != 0) return r;
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// GEMM-only arm (both operands pre-staged f16, C out f32): isolates pure TC GEMM speed from
// the conversion costs, the arm comparable to the autopsy's ampere_h16816gemm kernel totals.
extern "C" int64_t tc_shim_gemm_f16_pre(const void* a16, const void* w16,
                                        int64_t M, int64_t K, int64_t N,
                                        void* c16_scratch, void* c_f32, int64_t f16_accum) {
    int64_t r = gemm_f16_core(a16, w16, c16_scratch, M, K, N, (int)f16_accum);
    if (r != 0) return r;
    int64_t r2 = tc_shim_f16_to_f32(c16_scratch, c_f32, M * N);
    if (r2 != 0) return r2;
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// GemmEx-kernel-only variant: no C back-conversion, f16 C stays in c16_scratch. The cleanest
// kernel-speed number (zero non-TC work in the timed region).
extern "C" int64_t tc_shim_gemmex_only(const void* a16, const void* w16,
                                       int64_t M, int64_t K, int64_t N,
                                       void* c16_scratch, int64_t f16_accum) {
    return gemm_f16_core(a16, w16, c16_scratch, M, K, N, (int)f16_accum);
}

// TF32 arm: f32 in/out DIRECTLY — no staging, no dual residency, tensor cores via the 10-bit
// mantissa TF32 format (A100 156 TF/s peak, H100 494 dense). Included because it changes the
// integration story (weights stay f32) if its accuracy passes the 1e-2 gate.
extern "C" int64_t tc_shim_gemm_tf32(const void* a_f32, const void* w_f32,
                                     int64_t M, int64_t K, int64_t N, void* c_f32) {
    float alpha = 1.0f, beta = 0.0f;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha,
        w_f32, CUDA_R_32F, (int)K,
        a_f32, CUDA_R_32F, (int)K,
        &beta,
        c_f32, CUDA_R_32F, (int)N,
        CUBLAS_COMPUTE_32F_FAST_TF32, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// INTEGRATION ENTRIES (feat/tc-int, 2026-08-23) — the seams the session integration
// dispatches. Every probe entry above stays byte-unmodified.
// ═══════════════════════════════════════════════════════════════════════════════════════════

// THE integration workhorse: C[M,N](f32) = A[M,K](f32) @ W[N,K](f16)^T with W PRE-STAGED f16
// at session open, A converted into a16_scratch per call, and C written DIRECTLY as f32 —
// cublasGemmEx supports A/B = CUDA_R_16F with C = CUDA_R_32F under CUBLAS_COMPUTE_32F (still
// HMMA on the tensor cores; accumulator AND output f32). vs the probe's tc_full seam this
// drops the M*N f16->f32 C back-conversion entirely. `accum`: 0 = ASSIGN (beta 0), 1 =
// ACCUMULATE into the existing f32 C (beta 1) — the o_proj/down_proj residual feed done by
// cuBLAS itself at f32 precision (no f16 residual staging, unlike COMPUTE_16F). Syncs the
// shim stream before returning: the integration seam.
extern "C" int64_t tc_shim_gemm_f16_32c(const void* a_f32, const void* w_f16,
                                        int64_t M, int64_t K, int64_t N,
                                        void* a16_scratch, void* c_f32, int64_t accum) {
    int64_t r = tc_shim_f32_to_f16(a_f32, a16_scratch, M * K);
    if (r != 0) return r;
    float alpha = 1.0f, beta = (accum != 0) ? 1.0f : 0.0f;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha,
        w_f16, CUDA_R_16F, (int)K,
        a16_scratch, CUDA_R_16F, (int)K,
        &beta,
        c_f32, CUDA_R_32F, (int)N,
        CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    if (g_noseam) return 0;  // the NOSEAM seam: ordering rides the legacy-stream contract
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// STREAM-ORDERED SEAM (gemma3 lane, 2026-08-24) — the sync-seam removal. MAX 1.0.0's
// DeviceContext grew `create_external_stream(Pointer[NoneType]) -> DeviceStream`, so the
// session can wrap a CALLER-OWNED cudaStream_t and enqueue ALL Mojo kernels onto it. These
// two entries complete the other half: the shim CREATES that stream (returning the raw
// pointer for the Mojo side to wrap) and then every dispatch below runs ASYNCHRONOUSLY on
// it — the GemmEx and its A-convert kernel enqueue and RETURN with no cudaStreamSynchronize.
// Ordering is then the stream's own: Mojo kernel -> convert -> GemmEx -> Mojo kernel, all
// one stream, zero host syncs per seam (the old seam paid 2 device syncs per GEMM: the
// session's ctx.synchronize() BEFORE + the shim's cudaStreamSynchronize INSIDE — 496
// device-syncs per 27B decode step at 4 GEMMs x 62 layers).
// ═══════════════════════════════════════════════════════════════════════════════════════════

// Create a NEW non-blocking cudaStream_t on the current context, bind the cuBLAS handle to
// it, and return the raw pointer (int64) for the Mojo side to wrap with
// `ctx.create_external_stream`. Initializes the handle if needed. Returns 0 on failure
// (check tc_shim_last_error). The stream is shim-owned; tc_shim_shutdown destroys it only
// if the shim created it internally (this one is caller-owned via the returned pointer).
extern "C" int64_t tc_shim_create_stream(void) {
    if (g_handle == nullptr) {
        int64_t r = tc_shim_init();
        if (r != 0) return 0;
    }
    cudaStream_t s = nullptr;
    cudaError_t e = cudaStreamCreateWithFlags(&s, cudaStreamNonBlocking);
    if (e != cudaSuccess) { record_error((int64_t)e); return 0; }
    cublasStatus_t st = cublasSetStream(g_handle, s);
    if (st != CUBLAS_STATUS_SUCCESS) {
        record_error((int64_t)st);
        cudaStreamDestroy(s);
        return 0;
    }
    g_stream = s;
    g_stream_created = 0;  // caller owns it (wrapped as a DeviceStream on the Mojo side)
    return (int64_t)(uintptr_t)s;
}

// The ASYNC workhorse twin of tc_shim_gemm_f16_32c: identical compute (f32->f16 A convert +
// GemmEx COMPUTE_32F, f32 C direct, beta by `accum`), but NOTHING syncs — both the convert
// kernel and the GemmEx enqueue on the shim stream and the entry returns immediately. The
// caller MUST have routed the Mojo-side enqueues onto the SAME stream (the wrapped
// external stream) and owns the eventual sync (one per step, not per GEMM).
extern "C" int64_t tc_shim_gemm_f16_32c_async(const void* a_f32, const void* w_f16,
                                              int64_t M, int64_t K, int64_t N,
                                              void* a16_scratch, void* c_f32, int64_t accum) {
    int64_t r = tc_shim_f32_to_f16(a_f32, a16_scratch, M * K);
    if (r != 0) return r;
    float alpha = 1.0f, beta = (accum != 0) ? 1.0f : 0.0f;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha,
        w_f16, CUDA_R_16F, (int)K,
        a16_scratch, CUDA_R_16F, (int)K,
        &beta,
        c_f32, CUDA_R_32F, (int)N,
        CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    return 0;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// PRE-STAGED-A ENTRIES (7B pp1024/RAG round, 2026-09-15) — the A-convert elimination.
// tc_shim_gemm_f16_32c converts its f32 A into the caller's f16 scratch on EVERY call: at
// m=1024 that is 6 bytes of global traffic per A element per GEMM (4 GEMM roles/layer, the
// widest being down_proj's m*d_ff = 19.4M elements), i.e. ~182 MB/layer = ~5.1 GB over the
// 28-layer pp1024 prefill — pure redundant memory traffic, because the PRODUCER of that A
// (the rmsnorm rows kernel, the SwiGLU epilogue, the attention unpack) wrote the f32 one
// instruction earlier and could have written the f16 directly, at the identical rounded
// value. These two entries take A ALREADY f16 and skip the conversion; the producer-side
// f16 write is the Mojo half of the same lever (-D ALGENTA_7B_PF_F16NORM / _F16MLP).
// Compute mode is UNCHANGED (f16 A/B, CUBLAS_COMPUTE_32F): _16c only moves the C dtype, the
// accumulator stays f32, so the C rounding point is the epilogue's, exactly as a downstream
// f32->f16 convert would have rounded it. g_noseam is honoured identically.
// ═══════════════════════════════════════════════════════════════════════════════════════════

extern "C" int64_t tc_shim_gemm_f16_32c_pre(const void* a16, const void* w_f16,
                                           int64_t M, int64_t K, int64_t N,
                                           void* c_f32, int64_t accum) {
    float alpha = 1.0f, beta = (accum != 0) ? 1.0f : 0.0f;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha,
        w_f16, CUDA_R_16F, (int)K,
        a16, CUDA_R_16F, (int)K,
        &beta,
        c_f32, CUDA_R_32F, (int)N,
        CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    if (g_noseam) return 0;
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// The f16-C twin: same HMMA + f32 accumulator, C written as CUDA_R_16F. This is the gate/up
// GEMM's output under -D ALGENTA_7B_PF_F16MLP — the [m, 2*d_ff] result is 155 MB at m=1024
// in f32 and 77 MB in f16, and the SwiGLU epilogue then reads it back, so the dtype halves
// BOTH legs of the largest single non-GEMM traffic term in the layer. NOT bit-identical to
// the f32-C path (the SwiGLU inputs are rounded to f16 first) — the token-identity gate is
// what decides it, which is why it is its own entry and its own build flag.
extern "C" int64_t tc_shim_gemm_f16_16c_pre(const void* a16, const void* w_f16,
                                           int64_t M, int64_t K, int64_t N,
                                           void* c_f16, int64_t accum) {
    float alpha = 1.0f, beta = (accum != 0) ? 1.0f : 0.0f;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha,
        w_f16, CUDA_R_16F, (int)K,
        a16, CUDA_R_16F, (int)K,
        &beta,
        c_f16, CUDA_R_16F, (int)N,
        CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    if (g_noseam) return 0;
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// Fallback ladder rung 2 (only if the 32F-acc token gates ever fail): TF32 with a beta
// select — f32 weights DIRECTLY (zero dual residency), ASSIGN (beta 0) or ACCUMULATE
// (beta 1) into the f32 residual.
extern "C" int64_t tc_shim_gemm_tf32_beta(const void* a_f32, const void* w_f32,
                                          int64_t M, int64_t K, int64_t N,
                                          void* c_f32, int64_t accum) {
    float alpha = 1.0f, beta = (accum != 0) ? 1.0f : 0.0f;
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha,
        w_f32, CUDA_R_32F, (int)K,
        a_f32, CUDA_R_32F, (int)K,
        &beta,
        c_f32, CUDA_R_32F, (int)N,
        CUBLAS_COMPUTE_32F_FAST_TF32, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    if (g_noseam) return 0;  // the NOSEAM seam: ordering rides the legacy-stream contract
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// Fallback ladder rung 3: f16-ACCUMULATE (COMPUTE_16F requires a 16F C): stage the existing
// f32 residual into c16_scratch, GemmEx with beta 1 in 16F compute, convert back. Rounds the
// residual through f16 at every call — last-resort numerics, documented.
extern "C" int64_t tc_shim_gemm_f16_acc16(const void* a_f32, const void* w_f16,
                                          int64_t M, int64_t K, int64_t N,
                                          void* a16_scratch, void* c16_scratch,
                                          void* c_f32) {
    int64_t r = tc_shim_f32_to_f16(a_f32, a16_scratch, M * K);
    if (r != 0) return r;
    r = tc_shim_f32_to_f16(c_f32, c16_scratch, M * N);
    if (r != 0) return r;
    __half alpha_h = __float2half(1.0f), beta_h = __float2half(1.0f);
    cublasStatus_t s = cublasGemmEx(
        g_handle,
        CUBLAS_OP_T, CUBLAS_OP_N,
        (int)N, (int)M, (int)K,
        &alpha_h,
        w_f16, CUDA_R_16F, (int)K,
        a16_scratch, CUDA_R_16F, (int)K,
        &beta_h,
        c16_scratch, CUDA_R_16F, (int)N,
        CUBLAS_COMPUTE_16F, CUBLAS_GEMM_DEFAULT);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    r = tc_shim_f16_to_f32(c16_scratch, c_f32, M * N);
    if (r != 0) return r;
    if (g_noseam) return 0;  // the NOSEAM seam: ordering rides the legacy-stream contract
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// ── packed3 -> f16 weight dequant at session open ─────────────────────────────────────────
// Layout is residentk/kernels_packed3.mojo's spec, byte for byte: per row (weights [n,k]
// row-major), 3 unsigned int8 quants per 32-bit word little-endian (b0 lowest k), row stride
// words_per_row (k_pack/3 words, k_pad rounded to a multiple of 12 elements); block-32 f32
// scale + f32 zero companions indexed [row * blocks_per_row + block]; dequant = (q - zero) *
// scale. Output: dense f16 [n, k] (padding slots written too — they are exact zero-point
// quants and dequant to ~0, matching the format's zero-contribution contract).
__global__ void _packed3_to_f16_kernel(const uint32_t* __restrict__ words,
                                       const float* __restrict__ scales,
                                       const float* __restrict__ zeros,
                                       __half* __restrict__ out,
                                       long n_rows, long k, long k_pad,
                                       long words_per_row, long blocks_per_row) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long stride = (long)gridDim.x * blockDim.x;
    long total = n_rows * k_pad;
    for (long t = idx; t < total; t += stride) {
        long row = t / k_pad;
        long kk = t - row * k_pad;
        long word = words[row * words_per_row + kk / 3];
        unsigned q = (word >> (8 * (kk % 3))) & 0xFFu;
        long blk = row * blocks_per_row + kk / 32;
        float v = ((float)q - zeros[blk]) * scales[blk];
        out[row * k_pad + kk] = __float2half(v);
        (void)k;
    }
}

extern "C" int64_t tc_shim_dequant_packed3_f16(const void* words, const void* scales,
                                               const void* zeros, void* out_f16,
                                               int64_t n_rows, int64_t k, int64_t k_pad,
                                               int64_t words_per_row, int64_t blocks_per_row) {
    long total = (long)n_rows * (long)k_pad;
    int threads = 256;
    long blocks = (total + threads - 1) / threads;
    if (blocks > 2147483647L) blocks = 2147483647L;
    _packed3_to_f16_kernel<<<(unsigned)blocks, threads, 0, g_stream>>>(
        (const uint32_t*)words, (const float*)scales, (const float*)zeros,
        (__half*)out_f16, (long)n_rows, (long)k, (long)k_pad,
        (long)words_per_row, (long)blocks_per_row);
    cudaError_t e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// INTEGRATION variant (feat/tc-int): DENSE f16 output — writes ONLY the k real elements of
// each row at row stride k (the packed3 `k_pad - k` tail dropped), so the staged table is a
// plain [n_rows, k] row-major f16 matrix the GEMM consumes at its NATURAL K (no padded
// activation tails needed on the session side). The quant/scale/zero indexing is otherwise
// byte-identical to `_packed3_to_f16_kernel` above (words are still read from the packed
// layout's `words_per_row` rows; scales/zeros from `blocks_per_row`).
__global__ void _packed3_to_f16_dense_kernel(const uint32_t* __restrict__ words,
                                             const float* __restrict__ scales,
                                             const float* __restrict__ zeros,
                                             __half* __restrict__ out,
                                             long n_rows, long k,
                                             long words_per_row, long blocks_per_row) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long stride = (long)gridDim.x * blockDim.x;
    long total = n_rows * k;
    for (long t = idx; t < total; t += stride) {
        long row = t / k;
        long kk = t - row * k;
        long word = words[row * words_per_row + kk / 3];
        unsigned q = (word >> (8 * (kk % 3))) & 0xFFu;
        long blk = row * blocks_per_row + kk / 32;
        float v = ((float)q - zeros[blk]) * scales[blk];
        out[t] = __float2half(v);
    }
}

extern "C" int64_t tc_shim_dequant_packed3_f16_dense(const void* words, const void* scales,
                                                     const void* zeros, void* out_f16,
                                                     int64_t n_rows, int64_t k,
                                                     int64_t words_per_row,
                                                     int64_t blocks_per_row) {
    long total = (long)n_rows * (long)k;
    int threads = 256;
    long blocks = (total + threads - 1) / threads;
    if (blocks > 2147483647L) blocks = 2147483647L;
    _packed3_to_f16_dense_kernel<<<(unsigned)blocks, threads, 0, g_stream>>>(
        (const uint32_t*)words, (const float*)scales, (const float*)zeros,
        (__half*)out_f16, (long)n_rows, (long)k,
        (long)words_per_row, (long)blocks_per_row);
    cudaError_t e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// ── WMMA smoke: the minimal cutlass-free inline tensor-core attention tile ────────────────
// One warp computes D[16,16](f32) = A[16,16](f16, row-major, [m,k]) x Bmem[16,16](f16,
// [n,k] row-major — the residentk weight layout — loaded as col_major so element (k,n) sits
// at Bmem[n*16+k]). This is the exact S = Q @ K^T tile shape a TC flash-attention would use;
// the probe checks it against a CPU reference. If this compiles, links AND runs correct
// inside a Mojo binary, inline-PTX/WMMA flash-attn in this same shim is feasible — item 3's
// feasibility question answered at compile+run level (the full kernel is next-round work).
#ifndef TC_SHIM_NO_WMMA
__global__ void _wmma_smoke_kernel(const __half* __restrict__ a16,
                                   const __half* __restrict__ b16_nk,
                                   float* __restrict__ d) {
    wmma::fragment<wmma::matrix_a, 16, 16, 16, __half, wmma::row_major> fa;
    wmma::fragment<wmma::matrix_b, 16, 16, 16, __half, wmma::col_major> fb;
    wmma::fragment<wmma::accumulator, 16, 16, 16, float> fd;
    wmma::load_matrix_sync(fa, a16, 16);
    wmma::load_matrix_sync(fb, b16_nk, 16);
    wmma::fill_fragment(fd, 0.0f);
    wmma::mma_sync(fd, fa, fb, fd);
    wmma::store_matrix_sync(d, fd, 16, wmma::mem_row_major);
}

extern "C" int64_t tc_shim_wmma_smoke(const void* a16, const void* b16_nk, void* d_f32) {
    _wmma_smoke_kernel<<<1, 32, 0, g_stream>>>((const __half*)a16, (const __half*)b16_nk,
                                               (float*)d_f32);
    cudaError_t e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}
#else
extern "C" int64_t tc_shim_wmma_smoke(const void*, const void*, void*) { return -100; }
#endif

// ═══════════════════════════════════════════════════════════════════════════════════════════
// TENSOR-CORE PREFILL ATTENTION (vLLM-flip round, 2026-08-24) — strided-batched cuBLAS
// HMMA QK^T + masked softmax + PV, replacing the SIMT warp-per-row prefill attention that the
// nsys autopsy measured at 55.5 ms (vLLM's tensor-core flash runs the same shape in 3.77 ms).
//
// Layout contract (all row-major, gemma3 GQA: h_q query heads, h_kv KV heads, g = h_q / h_kv):
//   * Q packed by the Mojo side to `q16` [h_q, M, d] f16, contiguous (strideA = M*d per
//     KV-head group spans g query heads => g*M rows per batch).
//   * K/V live in the resident KV cache `ck`/`cv` [ctx, h_kv, d] f16; the per-KV-head view is
//     a strided [n_keys, d] matrix with leading dimension h_kv*d and per-batch offset hk*d.
//   * scores `s32` [h_q, M, n_keys] f32 (QK^T output), P `p16` [h_q, M, n_keys] f16 (softmax),
//     attn `o32` [h_q, M, d] f32 (PV output, same packed layout as Q for the Mojo unpack).
// Batching is over the h_kv KV heads; each batch covers g*M rows (the g query heads that share
// a KV head), so strideB = d (K head offset), strideA = g*M*d, strideC = g*M*(n_keys or d).
// All entries enqueue on the shim stream and return WITHOUT syncing (the G3_STREAM contract).
// ═══════════════════════════════════════════════════════════════════════════════════════════

// Generic strided-batched GemmEx, f16 A/B, f32 C, COMPUTE_32F. Row-major semantics:
//   transB=1: C[M,N] = A[M,K] @ B[N,K]^T  (B is "weights" layout, the QK^T case)
//   transB=0: C[M,N] = A[M,K] @ B[K,N]    (the PV case)
// ldA/ldB/ldC are row strides; strideA/strideB/strideC are per-batch offsets.
static int64_t bgemm_f16_core(const void* a16, const void* b16, void* c32,
                              int64_t M, int64_t N, int64_t K,
                              int64_t ldA, int64_t ldB, int64_t ldC,
                              int64_t strideA, int64_t strideB, int64_t strideC,
                              int64_t batch, int transB) {
    float alpha = 1.0f, beta = 0.0f;
    cublasStatus_t s;
    if (transB) {
        // C_rm[M,N] = A_rm[M,K] @ B_rm[N,K]^T  ->  (OP_T, OP_N, N, M, K; B ld=ldB, A ld=ldA)
        s = cublasGemmStridedBatchedEx(
            g_handle, CUBLAS_OP_T, CUBLAS_OP_N,
            (int)N, (int)M, (int)K, &alpha,
            b16, CUDA_R_16F, (int)ldB, strideB,
            a16, CUDA_R_16F, (int)ldA, strideA,
            &beta,
            c32, CUDA_R_32F, (int)ldC, strideC,
            (int)batch, CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
    } else {
        // C_rm[M,N] = A_rm[M,K] @ B_rm[K,N]  ->  (OP_N, OP_N, N, M, K; B ld=ldB, A ld=ldA)
        s = cublasGemmStridedBatchedEx(
            g_handle, CUBLAS_OP_N, CUBLAS_OP_N,
            (int)N, (int)M, (int)K, &alpha,
            b16, CUDA_R_16F, (int)ldB, strideB,
            a16, CUDA_R_16F, (int)ldA, strideA,
            &beta,
            c32, CUDA_R_32F, (int)ldC, strideC,
            (int)batch, CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
    }
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    return 0;
}

extern "C" int64_t tc_shim_bgemm_f16_async(const void* a16, const void* b16, void* c32,
                                           int64_t M, int64_t N, int64_t K,
                                           int64_t ldA, int64_t ldB, int64_t ldC,
                                           int64_t strideA, int64_t strideB, int64_t strideC,
                                           int64_t batch, int64_t transB) {
    return bgemm_f16_core(a16, b16, c32, M, N, K, ldA, ldB, ldC,
                          strideA, strideB, strideC, batch, (int)transB);
}

// Masked causal+window softmax over one score row -> f16 attention weights. One block per row
// (row r = query head h = r / m_rows, tile position p = r % m_rows; global position
// qpos = pos_base + p). Key j is attended iff j <= qpos AND (window <= 0 OR j >= qpos+1-window).
// grid = h_q * m_rows blocks, block = 256 threads; reads s32, writes p16 (both [row, n_keys]).
__global__ void _attn_softmax_mask_kernel(const float* __restrict__ s32,
                                          __half* __restrict__ p16,
                                          int n_keys, int m_rows, int pos_base, int window) {
    int row = blockIdx.x;
    int p = row % m_rows;
    int qpos = pos_base + p;
    int lo = (window > 0) ? (qpos + 1 - window) : 0;
    if (lo < 0) lo = 0;
    const float* srow = s32 + (long)row * n_keys;
    __half* prow = p16 + (long)row * n_keys;

    __shared__ float red[32];
    int tid = threadIdx.x;

    // pass 1: row max over valid keys
    float mx = -1e30f;
    for (int j = tid; j < n_keys; j += blockDim.x) {
        if (j >= lo && j <= qpos) {
            float v = srow[j];
            if (v > mx) mx = v;
        }
    }
    // block reduce max
    int lane = tid & 31, wid = tid >> 5;
    for (int off = 16; off > 0; off >>= 1)
        mx = fmaxf(mx, __shfl_down_sync(0xffffffff, mx, off));
    if (lane == 0) red[wid] = mx;
    __syncthreads();
    if (wid == 0) {
        mx = (lane < (blockDim.x >> 5)) ? red[lane] : -1e30f;
        for (int off = 16; off > 0; off >>= 1)
            mx = fmaxf(mx, __shfl_down_sync(0xffffffff, mx, off));
        if (lane == 0) red[0] = mx;
    }
    __syncthreads();
    float row_max = red[0];

    // pass 2: sum exp(v - max) over valid keys
    float sum = 0.0f;
    for (int j = tid; j < n_keys; j += blockDim.x) {
        if (j >= lo && j <= qpos) sum += __expf(srow[j] - row_max);
    }
    for (int off = 16; off > 0; off >>= 1)
        sum += __shfl_down_sync(0xffffffff, sum, off);
    if (lane == 0) red[wid] = sum;
    __syncthreads();
    if (wid == 0) {
        sum = (lane < (blockDim.x >> 5)) ? red[lane] : 0.0f;
        for (int off = 16; off > 0; off >>= 1)
            sum += __shfl_down_sync(0xffffffff, sum, off);
        if (lane == 0) red[0] = sum;
    }
    __syncthreads();
    float row_sum = red[0];
    float inv = (row_sum > 0.0f) ? (1.0f / row_sum) : 0.0f;

    // pass 3: normalize + write f16
    for (int j = tid; j < n_keys; j += blockDim.x) {
        float v = 0.0f;
        if (j >= lo && j <= qpos) v = __expf(srow[j] - row_max) * inv;
        prow[j] = __float2half(v);
    }
}

extern "C" int64_t tc_shim_attn_softmax_mask_async(const void* s32, void* p16,
                                                   int64_t n_keys, int64_t m_rows,
                                                   int64_t h_q, int64_t pos_base,
                                                   int64_t window) {
    long rows = (long)h_q * (long)m_rows;
    _attn_softmax_mask_kernel<<<(unsigned)rows, 256, 0, g_stream>>>(
        (const float*)s32, (__half*)p16, (int)n_keys, (int)m_rows, (int)pos_base, (int)window);
    cudaError_t e = cudaGetLastError();
    record_error((int64_t)e);
    return (int64_t)e;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// FUSED CAUSAL FLASH ATTENTION (FRONT 3, 2026-09-15) — `-D ALGENTA_7B_PF_FA`
//
// WHY: the A100 pp1024 layer decomposition (~/trtllm/front1/nsys_decomposition.json, arm
// `adopted_f4` == the shipped _c8) puts the TC prefill attention at 437 us/layer across SIX
// GPU passes — QK^T strided-batched GemmEx 97.6, masked softmax 142.5, PV GemmEx 71.6, the
// head-major Q pack 48.4, the head-major O unpack 47.3, and the f32->f16 A/KV converts 29.4
// — against TensorRT-LLM 1.2.1's ONE `fmha_v2_flash_attention_bf16_64_128_S_qkv_128_causal_
// sm80_kernel_nl_` at 87.0 us/layer (~/trtllm/front1/trtllm_kernel_mix.txt). The gap is not
// arithmetic, it is MATERIALIZATION: the [h_q*m, n_keys] f32 score matrix is 117 MB per layer
// at m=n_keys=1024 — written by the QK^T GEMM, read back three times by the softmax, written
// again as 59 MB of f16 P, read again by the PV GEMM = ~351 MB/layer = 9.8 GB per pp1024
// prefill, and the non-causal GEMM additionally computes 2x the pairs the causal mask keeps.
//
// This kernel removes the matrix entirely: FlashAttention-2 online softmax, one CTA per
// (query block, query head), the [BM,BN] score tile NEVER leaves registers, and Q/K/V/O are
// read/written in the session's OWN layouts (Q f32 position-major straight out of
// `_pf_ropewrt_kernel`, O f32 position-major straight into the o_proj seam) so the pack and
// unpack passes disappear with it. Only the K/V f16 staging stays (it is the additive route
// that keeps the resident f32 KV cache untouched, and at 2 MB/layer it is L2-resident).
//
// TRAFFIC ACCOUNTING (per CTA per key block, BM=64 BN=64 D=128, 4 warps): K 64 KB + V 64 KB
// (each warp needs its own copy of the B operand in registers) + P 8 KB write / 8 KB read =
// 144 KB of shared reads against 4*BM*BN*D = 2.1 MFLOP of HMMA = 0.069 B/FLOP, versus the
// sm_80 ratio of 128 B/clk shared to 2048 FLOP/clk tensor = 0.0625 B/FLOP. Shared bandwidth
// is therefore the binding constraint at ~1.1x the tensor-core time, i.e. an ~89% MFU ceiling
// for this tile shape — which is why BN is a template parameter the A/B sweeps.
//
// LAYOUT CONTRACT (all row-major):
//   q  f32 [m, h_q*d]          post-RoPE query rows (the session's `pf_q_rot`)
//   k  f16 [n_keys, h_kv*d]    staged K cache (the session's `pf_tc_k16`)
//   v  f16 [n_keys, h_kv*d]    staged V cache (the session's `pf_tc_v16`)
//   o  f32 [m, h_q*d]          attention output, position-major (the session's `pf_attn`)
// GQA: query head h reads KV head h/(h_q/h_kv). Query row r is global position pos_base+r and
// attends keys j <= pos_base+r AND j < n_keys — the same predicate `_attn_softmax_mask_kernel`
// applies with window=0, so the two are drop-in equivalents at window 0 (the 7B family is
// full-context causal; a windowed layer keeps the 5-pass chain, gated at the dispatch site).
// The attention scale rides the Q f32->f16 conversion, exactly as `_pf_q_pack_hm_f16` folds
// it, so the scores are pre-scaled at the identical rounding point.
//
// NUMERICS: online softmax with an f32 running max/sum and f32 O accumulation, f16 P into the
// PV HMMA — the same dtypes the 5-pass chain uses (f32 scores, f16 P, f32 O), so the only
// differences are the summation ORDER and the per-block O rescale. `__expf` (ex2.approx.ftz)
// replaces the softmax's `__expf`-equivalent; the token-identity gates decide, which is why the
// lever carries its own build flag.
//
// THE OPAQUE-FRAGMENT GUARD: this kernel indexes `wmma::fragment<accumulator,...>` elements by
// ROW to apply the causal mask, to rescale O by the online-softmax alpha, and to divide by the
// row sum at the end. The WMMA API documents that layout as opaque, so the mapping this file
// assumes (FA_ACC_ROW / FA_ACC_COL below, the sm_80 m16n16k16 f32 accumulator = two m16n8k16
// halves) is VERIFIED ON DEVICE by `_fa_layout_probe_kernel` before the first launch, and a
// mismatch returns -310 so the session falls back to the 5-pass chain instead of silently
// computing attention with permuted rows. Nothing about the numerics rides an assumption.
// ═══════════════════════════════════════════════════════════════════════════════════════════
#ifndef TC_SHIM_NO_WMMA

#define FA_BM 64          // query rows per CTA (4 warps x 16 WMMA rows)
#define FA_NWARP 4
#define FA_D 128          // head_dim — the only value this kernel implements (host-checked)
// Row stride (in halves) of the sQ/sK/sV operand tiles. FA_D itself would be 256 bytes = 64
// 32-bit banks exactly, so EVERY row of a 16-row WMMA tile would start in the same bank group
// and each ldmatrix would serialize 8-way — measured: 367 us/layer at pp1024 with ldm=FA_D,
// i.e. SLOWER than the 5-pass chain it replaces, at ~7% MFU. +8 halves = 272 bytes = 68 words
// shifts each row by 4 banks, which makes an 8-row ldmatrix group conflict-free while keeping
// the stride a multiple of 16 bytes so the uint4 global->shared stores stay aligned.
#define FA_LD (FA_D + 8)
#define FA_PLD 8          // sP row padding (halves) for the same reason on the P round trip
#define FA_OLDF 132       // sO row padding (floats): 528 B = 132 words -> a 4-bank row shift

// accumulator element i of a 16x16 f32 WMMA fragment sits at
//   row = (lane >> 2) + 8 * fa_acc_row(i),  col = 2 * (lane & 3) + fa_acc_col(i)
// i.e. elements {0,1,4,5} belong to row group g and {2,3,6,7} to row g+8, at columns
// {2t, 2t+1, 8+2t, 8+2t+1} — the sm_80 m16n16k16 accumulator's two m16n8k16 halves.
// Functions rather than arrays because a file-scope `static const int[]` is not visible to
// device code; the literal tables below are the readable statement of the same mapping and
// tc_shim_fa_layout_probe() checks the functions against them AND against the device.
__device__ __host__ __forceinline__ int fa_acc_row(int i) { return (i >> 1) & 1; }
__device__ __host__ __forceinline__ int fa_acc_col(int i) {
    return (((i >> 2) & 1) << 3) | (i & 1);
}
static const int FA_ACC_ROW_TBL[8] = {0, 0, 1, 1, 0, 0, 1, 1};
static const int FA_ACC_COL_TBL[8] = {0, 1, 0, 1, 8, 9, 8, 9};

__device__ __forceinline__ float fa_wmax(float v) {   // reduce over the 4 lanes of a row group
    v = fmaxf(v, __shfl_xor_sync(0xffffffffu, v, 1));
    return fmaxf(v, __shfl_xor_sync(0xffffffffu, v, 2));
}
__device__ __forceinline__ float fa_wsum(float v) {
    v += __shfl_xor_sync(0xffffffffu, v, 1);
    return v + __shfl_xor_sync(0xffffffffu, v, 2);
}

// One-time on-device check of the accumulator element -> (row, col) mapping. A = I_16, B is
// staged so that acc[r][c] == B[r][c] == r*16+c, therefore every fragment element READS BACK
// its own coordinates: lane L, element i holds row*16+col. 256 exact small integers, no
// tolerance, no floating-point judgement call.
__global__ void _fa_layout_probe_kernel(float* out) {
    __shared__ __half sA[16 * 16];
    __shared__ __half sB[16 * 16];
    __shared__ __half sOut[16 * 16];
    int t = threadIdx.x;
    for (int i = t; i < 256; i += blockDim.x) {
        int r = i / 16, c = i - r * 16;
        sA[i] = __float2half(r == c ? 1.0f : 0.0f);
        sB[c * 16 + r] = __float2half((float)(r * 16 + c));   // col-major: (k,n) at sB[n*16+k]
    }
    __syncthreads();
    wmma::fragment<wmma::matrix_a, 16, 16, 16, __half, wmma::row_major> fa;
    wmma::fragment<wmma::matrix_b, 16, 16, 16, __half, wmma::col_major> fb;
    wmma::fragment<wmma::accumulator, 16, 16, 16, float> fc;
    wmma::fragment<wmma::accumulator, 16, 16, 16, __half> fh;
    static_assert(sizeof(fc.x) / sizeof(fc.x[0]) == sizeof(fh.x) / sizeof(fh.x[0]),
                  "f32 and f16 accumulator fragments must carry the same element count");
    wmma::load_matrix_sync(fa, sA, 16);
    wmma::load_matrix_sync(fb, sB, 16);
    wmma::fill_fragment(fc, 0.0f);
    wmma::mma_sync(fc, fa, fb, fc);
    // (1) the f32 accumulator element -> (row, col) mapping the kernel indexes by. Packed at
    // out[lane*8 + i] (0..255); part (2) owns out[256..511].
    for (int i = 0; i < fc.num_elements; i++) out[t * 8 + i] = fc.x[i];
    // (2) the f32 -> f16 accumulator element correspondence + store_matrix_sync's row-major
    //     semantics, which is how the kernel hands P to the PV mma. out[256 + r*16 + c] must
    //     read back r*16+c, i.e. the SAME matrix the f32 accumulator held.
    for (int i = 0; i < fh.num_elements; i++) fh.x[i] = __float2half(fc.x[i]);
    wmma::store_matrix_sync(sOut, fh, 16, wmma::mem_row_major);
    __syncwarp();
    for (int i = 0; i < 256; i++) out[256 + i] = __half2float(sOut[i]);
}

static int g_fa_layout_ok = -1;   // -1 unchecked, 0 ok, 1 mismatch

extern "C" int64_t tc_shim_fa_layout_probe(void) {
    if (g_fa_layout_ok == 0) return 0;
    if (g_fa_layout_ok == 1) return -310;
    // self-consistency first: the bit formulas the DEVICE kernel indexes by must reproduce the
    // documented literal table, before either is compared against what the GPU actually did.
    for (int i = 0; i < 8; i++) {
        if (fa_acc_row(i) != FA_ACC_ROW_TBL[i] || fa_acc_col(i) != FA_ACC_COL_TBL[i]) {
            g_fa_layout_ok = 1;
            fprintf(stderr,
                    "[tc_shim] FA mapping formula disagrees with its own table at elem %d "
                    "(row %d/%d col %d/%d) — lever DISABLED.\n",
                    i, fa_acc_row(i), FA_ACC_ROW_TBL[i], fa_acc_col(i), FA_ACC_COL_TBL[i]);
            return -310;
        }
    }
    float* d = nullptr;
    cudaError_t e = cudaMalloc(&d, 512 * sizeof(float));
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    // zeroed first: a fragment that carries FEWER elements than the mapping assumes leaves
    // slots untouched, and an untouched slot must FAIL the check, not read back as a match.
    cudaMemsetAsync(d, 0, 512 * sizeof(float), g_stream);
    _fa_layout_probe_kernel<<<1, 32, 0, g_stream>>>(d);
    e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaStreamSynchronize(g_stream);
    if (e != cudaSuccess) { cudaFree(d); record_error((int64_t)e); return (int64_t)e; }
    float h[512];
    e = cudaMemcpy(h, d, 512 * sizeof(float), cudaMemcpyDeviceToHost);
    cudaFree(d);
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    for (int lane = 0; lane < 32; lane++) {
        int grp = lane >> 2, tig = lane & 3;
        for (int i = 0; i < 8; i++) {
            int want = (grp + 8 * fa_acc_row(i)) * 16 + (2 * tig + fa_acc_col(i));
            if ((int)h[lane * 8 + i] != want) {
                g_fa_layout_ok = 1;
                fprintf(stderr,
                        "[tc_shim] FA accumulator layout MISMATCH: lane %d elem %d = %d, "
                        "expected %d — the fused flash-attention lever is DISABLED for this "
                        "toolkit (the session keeps the 5-pass TC chain).\n",
                        lane, i, (int)h[lane * 8 + i], want);
                return -310;
            }
        }
    }
    for (int i = 0; i < 256; i++) {
        if ((int)h[256 + i] != i) {
            g_fa_layout_ok = 1;
            fprintf(stderr,
                    "[tc_shim] FA f16-accumulator store_matrix_sync MISMATCH: [%d] = %d, "
                    "expected %d — the fused flash-attention lever is DISABLED for this "
                    "toolkit (the session keeps the 5-pass TC chain).\n",
                    i, (int)h[256 + i], i);
            return -310;
        }
    }
    g_fa_layout_ok = 0;
    return 0;
}

template <int BN>
__global__ void __launch_bounds__(FA_NWARP * 32)
_fa_causal_kernel(const float* __restrict__ qg, const __half* __restrict__ kg,
                  const __half* __restrict__ vg, float* __restrict__ og,
                  const float* __restrict__ scalep,
                  int m, int n_keys, int h_q, int h_kv, int d, int pos_base) {
    // The attention scale arrives as a DEVICE POINTER, not a float argument: Mojo's
    // `external_call` FFI has no repo-proven Float32/Float64 argument marshalling, and an
    // ABI mismatch here would be a SILENT numeric bug rather than a crash. One 4-byte
    // L2-resident read per CTA, uniform across the block, is exact and free next to the
    // 32 KB of Q this CTA is about to pull in.
    const float scale = *scalep;
    extern __shared__ __half smem[];
    __half* sQ = smem;                          // [FA_BM][FA_LD]
    __half* sK = sQ + FA_BM * FA_LD;            // [BN][FA_LD]
    __half* sV = sK + BN * FA_LD;               // [BN][FA_LD]
    __half* sP = sV + BN * FA_LD;               // [FA_BM][BN + FA_PLD]
    const int sPld = BN + FA_PLD;

    const int tid = threadIdx.x;
    const int warp = tid >> 5;
    const int lane = tid & 31;
    const int grp = lane >> 2;                  // WMMA row group inside the warp's 16 rows
    const int tig = lane & 3;                   // WMMA column pair
    const int qi = blockIdx.x;
    const int h = blockIdx.y;
    const int hk = h / (h_q / h_kv);
    const int row0 = qi * FA_BM;
    const int kvld = h_kv * d;
    const int qld = h_q * d;

    // ── Q tile: f32 -> f16, attention scale folded in (the `_pf_q_pack_hm_f16` rounding) ──
    {
        const int nvec = FA_BM * (FA_D / 4);
        for (int t = tid; t < nvec; t += FA_NWARP * 32) {
            int r = t / (FA_D / 4);
            int c4 = t - r * (FA_D / 4);
            int gr = row0 + r;
            float4 val = make_float4(0.0f, 0.0f, 0.0f, 0.0f);
            if (gr < m)
                val = *reinterpret_cast<const float4*>(qg + (size_t)gr * qld + h * d + c4 * 4);
            __half2* dst = reinterpret_cast<__half2*>(sQ + r * FA_LD + c4 * 4);
            dst[0] = __floats2half2_rn(val.x * scale, val.y * scale);
            dst[1] = __floats2half2_rn(val.z * scale, val.w * scale);
        }
    }
    __syncthreads();

    // Q A-fragments: loaded ONCE per CTA and reused across every key block — the register-
    // resident A operand is what keeps the per-key-block shared traffic at the K/V terms.
    wmma::fragment<wmma::matrix_a, 16, 16, 16, __half, wmma::row_major> fa[FA_D / 16];
    for (int kk = 0; kk < FA_D / 16; kk++)
        wmma::load_matrix_sync(fa[kk], sQ + (warp * 16) * FA_LD + kk * 16, FA_LD);

    wmma::fragment<wmma::accumulator, 16, 16, 16, float> oacc[FA_D / 16];
    for (int i = 0; i < FA_D / 16; i++) wmma::fill_fragment(oacc[i], 0.0f);

    const float NEG = -1.0e30f;
    float m0 = NEG, m1 = NEG, l0 = 0.0f, l1 = 0.0f;

    // key blocks this CTA needs: causal ceiling from its LAST VALID query row, and the cache
    // ceiling. Rows past `m` are never stored, so a partial tail block cannot over-read.
    int rows_here = m - row0;
    if (rows_here > FA_BM) rows_here = FA_BM;
    int kb_causal = (pos_base + row0 + rows_here - 1) / BN;
    int kb_keys = (n_keys - 1) / BN;
    int kb_max = kb_causal < kb_keys ? kb_causal : kb_keys;
    // this warp's two query rows, as GLOBAL positions (the causal predicate's right side)
    const int qg0 = pos_base + row0 + warp * 16 + grp;
    const int qg1 = qg0 + 8;

    for (int kb = 0; kb <= kb_max; kb++) {
        // ── K,V tiles: [BN][d] f16, 16-byte vector loads straight out of the staged cache ──
        {
            const int nvec = BN * (FA_D / 8);
            const int kbase = kb * BN;
            for (int t = tid; t < nvec; t += FA_NWARP * 32) {
                int r = t / (FA_D / 8);
                int c8 = t - r * (FA_D / 8);
                int gj = kbase + r;
                uint4 kv = make_uint4(0u, 0u, 0u, 0u);
                uint4 vv = make_uint4(0u, 0u, 0u, 0u);
                if (gj < n_keys) {
                    const size_t off = (size_t)gj * kvld + hk * d + c8 * 8;
                    kv = *reinterpret_cast<const uint4*>(kg + off);
                    vv = *reinterpret_cast<const uint4*>(vg + off);
                }
                *reinterpret_cast<uint4*>(sK + r * FA_LD + c8 * 8) = kv;
                *reinterpret_cast<uint4*>(sV + r * FA_LD + c8 * 8) = vv;
            }
        }
        __syncthreads();

        // ── S[16,BN] = Q[16,d] @ K^T[d,BN] on the tensor cores, f32 accumulate. The BN/16
        //    B-fragments of one k-step are loaded BEFORE any of its mmas issue: the loads are
        //    mutually independent, so the scheduler can have them all in flight instead of
        //    serializing load->mma->load->mma down the 32-deep chain. ──
        wmma::fragment<wmma::accumulator, 16, 16, 16, float> sacc[BN / 16];
        for (int n = 0; n < BN / 16; n++) wmma::fill_fragment(sacc[n], 0.0f);
        for (int kk = 0; kk < FA_D / 16; kk++) {
            wmma::fragment<wmma::matrix_b, 16, 16, 16, __half, wmma::col_major> fb[BN / 16];
            for (int n = 0; n < BN / 16; n++)
                wmma::load_matrix_sync(fb[n], sK + (n * 16) * FA_LD + kk * 16, FA_LD);
            for (int n = 0; n < BN / 16; n++)
                wmma::mma_sync(sacc[n], fa[kk], fb[n], sacc[n]);
        }

        // ── causal + cache-tail mask. The whole block is unmasked when its LAST key is at or
        //    below this warp's FIRST query row and inside the cache: the common case for every
        //    off-diagonal block, so the per-element predicate only runs on the diagonal. ──
        const bool need_mask = (kb * BN + BN - 1 > qg0) || (kb * BN + BN - 1 >= n_keys);
        if (need_mask) {
            for (int n = 0; n < BN / 16; n++) {
                for (int i = 0; i < 8; i++) {
                    int j = kb * BN + n * 16 + 2 * tig + fa_acc_col(i);
                    int qpos = fa_acc_row(i) ? qg1 : qg0;
                    if (j > qpos || j >= n_keys) sacc[n].x[i] = NEG;
                }
            }
        }

        // ── online softmax: row max over this block, alpha rescale of O, exp into f16 P ──
        float t0 = NEG, t1 = NEG;
        for (int n = 0; n < BN / 16; n++) {
            for (int i = 0; i < 8; i++) {
                if (fa_acc_row(i)) { if (sacc[n].x[i] > t1) t1 = sacc[n].x[i]; }
                else               { if (sacc[n].x[i] > t0) t0 = sacc[n].x[i]; }
            }
        }
        t0 = fa_wmax(t0);
        t1 = fa_wmax(t1);
        const float n0 = fmaxf(m0, t0), n1 = fmaxf(m1, t1);
        const float a0 = __expf(m0 - n0), a1 = __expf(m1 - n1);
        for (int n = 0; n < FA_D / 16; n++) {
            for (int i = 0; i < 8; i++) oacc[n].x[i] *= fa_acc_row(i) ? a1 : a0;
        }
        float s0 = 0.0f, s1 = 0.0f;
        wmma::fragment<wmma::accumulator, 16, 16, 16, __half> ph;
        for (int n = 0; n < BN / 16; n++) {
            for (int i = 0; i < 8; i++) {
                float p = __expf(sacc[n].x[i] - (fa_acc_row(i) ? n1 : n0));
                sacc[n].x[i] = p;
                if (fa_acc_row(i)) s1 += p; else s0 += p;
                ph.x[i] = __float2half(p);
            }
            wmma::store_matrix_sync(sP + (warp * 16) * sPld + n * 16, ph, sPld,
                                    wmma::mem_row_major);
        }
        s0 = fa_wsum(s0);
        s1 = fa_wsum(s1);
        l0 = l0 * a0 + s0;
        l1 = l1 * a1 + s1;
        m0 = n0;
        m1 = n1;
        __syncthreads();

        // ── O[16,d] += P[16,BN] @ V[BN,d] ──
        for (int kk = 0; kk < BN / 16; kk++) {
            wmma::fragment<wmma::matrix_a, 16, 16, 16, __half, wmma::row_major> fp;
            wmma::load_matrix_sync(fp, sP + (warp * 16) * sPld + kk * 16, sPld);
            for (int n = 0; n < FA_D / 16; n++) {
                wmma::fragment<wmma::matrix_b, 16, 16, 16, __half, wmma::row_major> fv;
                wmma::load_matrix_sync(fv, sV + (kk * 16) * FA_LD + n * 16, FA_LD);
                wmma::mma_sync(oacc[n], fp, fv, oacc[n]);
            }
        }
        __syncthreads();
    }

    // ── epilogue: divide by the row sums, stage through shared, write position-major f32 ──
    const float inv0 = (l0 > 0.0f) ? (1.0f / l0) : 0.0f;
    const float inv1 = (l1 > 0.0f) ? (1.0f / l1) : 0.0f;
    for (int n = 0; n < FA_D / 16; n++) {
        for (int i = 0; i < 8; i++) oacc[n].x[i] *= fa_acc_row(i) ? inv1 : inv0;
    }
    float* sO = reinterpret_cast<float*>(smem);   // reuses sQ/sK/sV: FA_BM*FA_OLDF*4 = 33.8 KB
    for (int n = 0; n < FA_D / 16; n++)
        wmma::store_matrix_sync(sO + (warp * 16) * FA_OLDF + n * 16, oacc[n], FA_OLDF,
                                wmma::mem_row_major);
    __syncthreads();
    {
        const int nvec = FA_BM * (FA_D / 4);
        for (int t = tid; t < nvec; t += FA_NWARP * 32) {
            int r = t / (FA_D / 4);
            int c4 = t - r * (FA_D / 4);
            int gr = row0 + r;
            if (gr >= m) continue;
            const float* src = sO + r * FA_OLDF + c4 * 4;
            *reinterpret_cast<float4*>(og + (size_t)gr * qld + h * d + c4 * 4) =
                make_float4(src[0], src[1], src[2], src[3]);
        }
    }
}

// dynamic shared bytes for a given BN, and the largest the kernel ever needs (the epilogue's
// sO staging reuses the same window: FA_BM * FA_OLDF * 4 = 33792 < both).
template <int BN>
static inline int fa_smem_bytes(void) {
    int tiles = (FA_BM * FA_LD + 2 * BN * FA_LD + FA_BM * (BN + FA_PLD)) * (int)sizeof(__half);
    int epi = FA_BM * FA_OLDF * (int)sizeof(float);   // sO reuses the same window
    return tiles > epi ? tiles : epi;
}

static int g_fa_attr_done = 0;

static int64_t fa_set_attrs(void) {
    if (g_fa_attr_done) return 0;
    cudaError_t e = cudaFuncSetAttribute(_fa_causal_kernel<32>,
                                         cudaFuncAttributeMaxDynamicSharedMemorySize,
                                         fa_smem_bytes<32>());
    if (e == cudaSuccess)
        e = cudaFuncSetAttribute(_fa_causal_kernel<64>,
                                 cudaFuncAttributeMaxDynamicSharedMemorySize,
                                 fa_smem_bytes<64>());
    if (e == cudaSuccess)
        e = cudaFuncSetAttribute(_fa_causal_kernel<128>,
                                 cudaFuncAttributeMaxDynamicSharedMemorySize,
                                 fa_smem_bytes<128>());
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    g_fa_attr_done = 1;
    return 0;
}

// bn: 32 / 64 / 128 key columns per online-softmax block (anything else -> 64). scale_f32 is
// a DEVICE pointer to one float (see the kernel's comment for why it is not an argument).
// Returns -301 for an unsupported head_dim, -310 if the on-device accumulator-layout probe
// disagreed with the mapping this file indexes by (caller MUST fall back), else the
// cudaError_t. Enqueues on the shim stream and returns WITHOUT syncing (the G3_STREAM /
// NOSEAM contract).
extern "C" int64_t tc_shim_fa_causal_async(const void* q_f32, const void* k16, const void* v16,
                                           void* o_f32, const void* scale_f32,
                                           int64_t m, int64_t n_keys,
                                           int64_t h_q, int64_t h_kv, int64_t d,
                                           int64_t pos_base, int64_t bn) {
    if (d != FA_D) return -301;
    if (m <= 0 || n_keys <= 0 || h_kv <= 0 || h_q <= 0) return 0;
    if ((h_q % h_kv) != 0) return -304;
    int64_t r = tc_shim_fa_layout_probe();
    if (r != 0) return r;
    r = fa_set_attrs();
    if (r != 0) return r;
    dim3 grid((unsigned)((m + FA_BM - 1) / FA_BM), (unsigned)h_q);
    dim3 block(FA_NWARP * 32);
    int im = (int)m, ink = (int)n_keys, ihq = (int)h_q, ihkv = (int)h_kv, id = (int)d;
    int ipos = (int)pos_base;
    const float* q = (const float*)q_f32;
    const __half* k = (const __half*)k16;
    const __half* v = (const __half*)v16;
    const float* sp = (const float*)scale_f32;
    float* o = (float*)o_f32;
    cudaError_t e;
    if (bn == 32) {
        _fa_causal_kernel<32><<<grid, block, fa_smem_bytes<32>(), g_stream>>>(
            q, k, v, o, sp, im, ink, ihq, ihkv, id, ipos);
    } else if (bn == 128) {
        _fa_causal_kernel<128><<<grid, block, fa_smem_bytes<128>(), g_stream>>>(
            q, k, v, o, sp, im, ink, ihq, ihkv, id, ipos);
    } else {
        _fa_causal_kernel<64><<<grid, block, fa_smem_bytes<64>(), g_stream>>>(
            q, k, v, o, sp, im, ink, ihq, ihkv, id, ipos);
    }
    e = cudaGetLastError();
    record_error((int64_t)e);
    return (int64_t)e;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// FA2 — cp.async DOUBLE-BUFFERED, RAW-mma FUSED CAUSAL FLASH ATTENTION (FRONT 4 lever 1)
//
// FRONT 3's `_fa_causal_kernel` measures 41.5 ms of FA over a RAG-4096 prefill at ~26% MFU
// against TensorRT-LLM's `fmha_v2_flash_attention_bf16_64_128_S_qkv_128_causal_sm80` at
// 24.4 ms / ~44%. Its own nsys autopsy named two causes, and this kernel is both:
//
//   (a) NO cp.async DOUBLE BUFFERING. The K/V tile is pulled global->register->shared with
//       plain uint4 loads at the TOP of every key block and then fenced, so the whole HBM
//       round trip is exposed latency at 2 CTAs/SM (8 warps), and the block fences three
//       times per key block. Here the tile for kb+1 is in flight while kb computes, on two
//       rotating buffers, with two fences instead of three.
//   (b) THE f16 P TILE ROUND-TRIPS THROUGH SHARED MEMORY. `wmma::fragment<accumulator>` is an
//       f32 fragment and the WMMA API has no way to reinterpret it as a `matrix_a` f16
//       operand, so FRONT 3 stored P to `sP` and `load_matrix_sync`ed it back — 16 extra
//       bytes of shared traffic per score element on a kernel whose shared-load stream is
//       already within 12.5% of the A100's 128 B/clk/SM roof. Raw
//       `mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32` does not have that limit: the
//       m16n8k16 A-fragment and the m16n8 D-fragment put a lane's two f16 of a k-pair at
//       EXACTLY the registers where its two f32 of the same k-pair already sit, so P's
//       A-fragment is `cvt` + `mov.b32` on values already in registers. `sP` disappears.
//
// TWO MORE THINGS FALL OUT OF (b), FOR FREE:
//   * the f32 O accumulator's element -> (row, col) mapping is now specified by the ISA
//     rather than opaque, so the epilogue writes position-major f32 STRAIGHT TO GLOBAL as
//     float2 — `sO`, its 33.8 KB staging window and its fence are gone too.
//   * shared memory per CTA drops from 61.4 KB to 8*BN*FA_LD bytes (34.8 KB at BN=32,
//     69.6 KB at BN=64), because the Q tile is staged into the second rotating buffer and
//     dies the moment its A-fragments are in registers.
//
// LAYOUT CONTRACT (and why it is not an assumption). `_fa2_layout_probe_kernel` runs ON DEVICE
// before the first launch: it fills an A tile with A[r][c] = (c==0 ? r+1 : 0) and a B tile with
// B[k][n] = (k==0 ? n+1 : 0), performs the exact ldmatrix + mma sequences this kernel uses for
// BOTH B roles (the K tile, loaded non-transposed because the session's K is stored [key][dim]
// which is already k-minor; and the V tile, loaded transposed), and requires every lane's four
// D registers to read back (row+1)*(col+1). One probe therefore pins the A mapping, both B
// mappings and the D mapping simultaneously, in exact small integers. A mismatch returns -311
// and the caller keeps FRONT 3's kernel — a declined lever never masquerades.
//
// NUMERICS are FRONT 3's verbatim: f32 running max/sum, f32 O accumulation, `__expf`
// (ex2.approx.ftz), P rounded to f16 with round-to-nearest-even at the same point, the same
// causal/cache predicate, the same scale folded into the same Q f32->f16 conversion. Only the
// summation ORDER changes (m16n8k16 accumulates 16 keys per instruction where WMMA's
// m16n16k16 accumulated 16 as two 8-wide halves), so the lever carries its own build flag and
// goes through the token-identity gates.
// ═══════════════════════════════════════════════════════════════════════════════════════════

__device__ __forceinline__ unsigned fa2_su32(const void* p) {
    return static_cast<unsigned>(__cvta_generic_to_shared(p));
}
// 16-byte async global->shared copy; `bytes` < 16 zero-fills the remainder, so an out-of-cache
// key row is written as zeros by the copy engine rather than by a predicated register store.
__device__ __forceinline__ void fa2_cp16(void* dst, const void* src, int bytes) {
    asm volatile("cp.async.cg.shared.global [%0], [%1], 16, %2;\n" ::
                     "r"(fa2_su32(dst)), "l"(src), "r"(bytes));
}
__device__ __forceinline__ void fa2_cp_commit() { asm volatile("cp.async.commit_group;\n"); }
// "at most one group still in flight" — with exactly two committed groups this retires the
// older one, i.e. the buffer this iteration is about to read.
__device__ __forceinline__ void fa2_cp_wait1() { asm volatile("cp.async.wait_group 1;\n"); }
__device__ __forceinline__ void fa2_ldsm4(unsigned& r0, unsigned& r1, unsigned& r2, unsigned& r3,
                                          const void* p) {
    asm volatile("ldmatrix.sync.aligned.m8n8.x4.shared.b16 {%0,%1,%2,%3}, [%4];\n"
                 : "=r"(r0), "=r"(r1), "=r"(r2), "=r"(r3)
                 : "r"(fa2_su32(p)));
}
__device__ __forceinline__ void fa2_ldsm4t(unsigned& r0, unsigned& r1, unsigned& r2, unsigned& r3,
                                           const void* p) {
    asm volatile("ldmatrix.sync.aligned.m8n8.x4.trans.shared.b16 {%0,%1,%2,%3}, [%4];\n"
                 : "=r"(r0), "=r"(r1), "=r"(r2), "=r"(r3)
                 : "r"(fa2_su32(p)));
}
// D = A @ B + D over one m16n8k16 tile; D and C are the same registers ("+f").
__device__ __forceinline__ void fa2_mma(float* dd, const unsigned* a, unsigned b0, unsigned b1) {
    asm volatile("mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32 "
                 "{%0,%1,%2,%3}, {%4,%5,%6,%7}, {%8,%9}, {%0,%1,%2,%3};\n"
                 : "+f"(dd[0]), "+f"(dd[1]), "+f"(dd[2]), "+f"(dd[3])
                 : "r"(a[0]), "r"(a[1]), "r"(a[2]), "r"(a[3]), "r"(b0), "r"(b1));
}
__device__ __forceinline__ unsigned fa2_pk(float lo, float hi) {
    __half2 h = __floats2half2_rn(lo, hi);
    return *reinterpret_cast<unsigned*>(&h);
}

// K/V tile for key block `kb` -> one rotating buffer. ASYNC=1 issues cp.async (the caller
// commits); ASYNC=0 does FRONT 3's predicated uint4 round trip through registers. Blocks past
// `kb_max` are never read, so they are skipped entirely — but the caller still commits an
// (empty) group, which is what keeps `wait_group 1` counting correctly on the last iterations.
template <int BN, int ASYNC>
__device__ __forceinline__ void fa2_load_kv(__half* dK, __half* dV, const __half* kg,
                                            const __half* vg, int kb, int kb_max, int n_keys,
                                            int hk, int d, int kvld, int tid) {
    if (kb > kb_max) return;
    const int kbase = kb * BN;
#pragma unroll
    for (int i = 0; i < BN * (FA_D / 8) / (FA_NWARP * 32); i++) {
        const int t = tid + i * FA_NWARP * 32;
        const int r = t >> 4;                 // FA_D / 8 == 16 vector columns per row
        const int c8 = t & 15;
        const int gj = kbase + r;
        const int gc = gj < n_keys ? gj : n_keys - 1;   // stay in bounds even when zero-filling
        const size_t off = (size_t)gc * kvld + hk * d + c8 * 8;
        if (ASYNC) {
            const int sz = gj < n_keys ? 16 : 0;
            fa2_cp16(dK + r * FA_LD + c8 * 8, kg + off, sz);
            fa2_cp16(dV + r * FA_LD + c8 * 8, vg + off, sz);
        } else {
            uint4 kv = make_uint4(0u, 0u, 0u, 0u), vv = make_uint4(0u, 0u, 0u, 0u);
            if (gj < n_keys) {
                kv = *reinterpret_cast<const uint4*>(kg + off);
                vv = *reinterpret_cast<const uint4*>(vg + off);
            }
            *reinterpret_cast<uint4*>(dK + r * FA_LD + c8 * 8) = kv;
            *reinterpret_cast<uint4*>(dV + r * FA_LD + c8 * 8) = vv;
        }
    }
}

// PMMA=1 builds P's A-fragment in registers (the point of the lever); PMMA=0 keeps FRONT 3's
// shared-memory round trip so the two sub-levers can be attributed separately at the SAME
// occupancy. DBUF=1 double-buffers the K/V tiles with cp.async; DBUF=0 loads synchronously
// into buffer 0 exactly as FRONT 3 did (buffer 1 is allocated but unused, so shared memory —
// and therefore occupancy — is identical either way).
// NOTE (FRONT 5, refuted arm removed). This declaration briefly carried a fourth template
// parameter `MINB` defaulting to 1 so an occupancy arm could ask ptxas for 4 CTAs/SM. It was
// REVERTED because the default is not neutral: `__launch_bounds__(128)` and
// `__launch_bounds__(128, 1)` are NOT the same hint to ptxas, and adding it moved this exact
// instantiation from 155 to 171 registers — which drops it from 3 CTAs/SM to 2 and cost +9.8%
// on the RAG-4096 FA block (33.89 -> 37.22 ms) in a kernel whose source had not otherwise
// changed. The occupancy question it was meant to answer is answered below in the ledger, and
// the answer is no; the shipped kernel keeps its original launch bounds so that nothing about
// FRONT 4's adopted codegen can drift.
template <int BN, int PMMA, int DBUF>
__global__ void __launch_bounds__(FA_NWARP * 32)
_fa2_causal_kernel(const float* __restrict__ qg, const __half* __restrict__ kg,
                   const __half* __restrict__ vg, float* __restrict__ og,
                   const float* __restrict__ scalep, int m, int n_keys, int h_q, int h_kv, int d,
                   int pos_base) {
    // The scale rides a DEVICE POINTER, not a float argument — see `_fa_causal_kernel`.
    const float scale = *scalep;
    extern __shared__ __half smem[];
    const int KVH = BN * FA_LD;                     // halves in one K (or V) tile
    // The two rotating buffers are addressed by ARITHMETIC on `smem`, never through a
    // `__half* bufK[2]` array: a runtime index (`kb & 1`) into a local array forces the array
    // itself into local memory, which ptxas reports as a 32-byte stack frame and costs a
    // per-thread private load on every use inside the key-block loop.
    __half* sQ = smem + 2 * KVH;                    // == buffer 1's K; dead after the A loads
    __half* sP = smem + 4 * KVH;                    // PMMA=0 only (host sizes the window)
    const int sPld = BN + FA_PLD;

    const int tid = threadIdx.x;
    const int warp = tid >> 5;
    const int lane = tid & 31;
    const int qi = blockIdx.x;
    const int h = blockIdx.y;
    const int hk = h / (h_q / h_kv);
    const int row0 = qi * FA_BM;
    const int kvld = h_kv * d;
    const int qld = h_q * d;
    // ldmatrix address generators: lane>>3 selects which of the four 8x8 sub-matrices this
    // lane names a row of. Bit 0 -> the second group of 8 ROWS, bit 1 -> the second group of
    // 8 COLUMNS. Identical for every tile in the kernel, so they are hoisted out of the loop.
    const int lr8 = ((lane >> 3) & 1) << 3;         // 0 or 8
    const int lc8 = ((lane >> 3) & 2) << 2;         // 0 or 8
    const int l7 = lane & 7;
    const int rlo = lane >> 2;                      // this lane's row inside the warp's 16
    const int chi = (lane & 3) << 1;                // this lane's column base in an 8-wide tile

    int rows_here = m - row0;
    if (rows_here > FA_BM) rows_here = FA_BM;
    int kb_causal = (pos_base + row0 + rows_here - 1) / BN;
    int kb_keys = (n_keys - 1) / BN;
    int kb_max = kb_causal < kb_keys ? kb_causal : kb_keys;

    // ── kb=0 in flight FIRST (it is async and touches buffer 0 only), then stage Q ──
    if (DBUF) {
        fa2_load_kv<BN, 1>(smem, smem + KVH, kg, vg, 0, kb_max, n_keys, hk, d, kvld, tid);
        fa2_cp_commit();
    }
    {   // Q tile: f32 -> f16 with the attention scale folded in, at `_pf_q_pack_hm_f16`'s
        // rounding point — verbatim FRONT 3, into the buffer-1 window instead of its own.
        const int nvec = FA_BM * (FA_D / 4);
        for (int t = tid; t < nvec; t += FA_NWARP * 32) {
            int r = t / (FA_D / 4);
            int c4 = t - r * (FA_D / 4);
            int gr = row0 + r;
            float4 val = make_float4(0.0f, 0.0f, 0.0f, 0.0f);
            if (gr < m)
                val = *reinterpret_cast<const float4*>(qg + (size_t)gr * qld + h * d + c4 * 4);
            __half2* dst = reinterpret_cast<__half2*>(sQ + r * FA_LD + c4 * 4);
            dst[0] = __floats2half2_rn(val.x * scale, val.y * scale);
            dst[1] = __floats2half2_rn(val.z * scale, val.w * scale);
        }
    }
    __syncthreads();
    // ── Q A-fragments: loaded ONCE per CTA, reused across every key block. One ldmatrix.x4
    //    per 16-column k-step yields that step's a0..a3 directly. ──
    unsigned qa[FA_D / 16][4];
#pragma unroll
    for (int ks = 0; ks < FA_D / 16; ks++)
        fa2_ldsm4(qa[ks][0], qa[ks][1], qa[ks][2], qa[ks][3],
                  sQ + (warp * 16 + lr8 + l7) * FA_LD + ks * 16 + lc8);
    __syncthreads();                                // sQ is dead: buffer 1 may be overwritten
    if (DBUF) {
        fa2_load_kv<BN, 1>(smem + 2 * KVH, smem + 3 * KVH, kg, vg, 1, kb_max, n_keys, hk, d,
                           kvld, tid);
        fa2_cp_commit();
    }

    float oacc[FA_D / 8][4];
#pragma unroll
    for (int i = 0; i < FA_D / 8; i++) {
        oacc[i][0] = 0.0f; oacc[i][1] = 0.0f; oacc[i][2] = 0.0f; oacc[i][3] = 0.0f;
    }
    constexpr int NT = BN / 8;                      // m16n8 score tiles per key block
    const float NEG = -1.0e30f;
    float m0 = NEG, m1 = NEG, l0 = 0.0f, l1 = 0.0f;
    const int qg0 = pos_base + row0 + warp * 16 + rlo;      // global position of row `rlo`
    const int qg1 = qg0 + 8;

    for (int kb = 0; kb <= kb_max; kb++) {
        const int cur = DBUF ? (kb & 1) : 0;
        __half* bk = smem + cur * 2 * KVH;          // this iteration's rotating buffer
        __half* bv = bk + KVH;
        if (DBUF) { fa2_cp_wait1(); __syncthreads(); }
        else {
            fa2_load_kv<BN, 0>(smem, smem + KVH, kg, vg, kb, kb_max, n_keys, hk, d, kvld,
                               tid);
            __syncthreads();
        }
        const __half* sK = bk;
        const __half* sV = bv;

        // ── S[16,BN] = Q[16,d] @ K^T[d,BN], f32 accumulate. All of one k-step's B fragments
        //    are loaded before any of its mmas issue, so the loads overlap. ──
        float s[NT][4];
#pragma unroll
        for (int nt = 0; nt < NT; nt++) {
            s[nt][0] = 0.0f; s[nt][1] = 0.0f; s[nt][2] = 0.0f; s[nt][3] = 0.0f;
        }
#pragma unroll
        for (int ks = 0; ks < FA_D / 16; ks++) {
#pragma unroll
            for (int np = 0; np < BN / 16; np++) {
                unsigned b0, b1, b2, b3;
                fa2_ldsm4(b0, b1, b2, b3,
                          sK + (np * 16 + lr8 + l7) * FA_LD + ks * 16 + lc8);
                fa2_mma(s[2 * np], qa[ks], b0, b2);         // n-tile np*16
                fa2_mma(s[2 * np + 1], qa[ks], b1, b3);     // n-tile np*16 + 8
            }
        }

        // ── causal + cache-tail mask. s[nt][0,1] are row `rlo`, s[nt][2,3] row `rlo+8`, at
        //    columns nt*8 + chi + {0,1}. The whole block is unmasked when its LAST key is at
        //    or below this warp's FIRST query row and inside the cache, so the per-element
        //    predicate only runs on the diagonal block. ──
        const bool need_mask = (kb * BN + BN - 1 > qg0) || (kb * BN + BN - 1 >= n_keys);
        if (need_mask) {
#pragma unroll
            for (int nt = 0; nt < NT; nt++) {
                const int j = kb * BN + nt * 8 + chi;
                const int jc = j < n_keys ? j : -1;                 // cache tail
                if (jc < 0 || j > qg0) s[nt][0] = NEG;
                if (jc < 0 || j + 1 > qg0) s[nt][1] = NEG;
                if (jc < 0 || j > qg1) s[nt][2] = NEG;
                if (jc < 0 || j + 1 > qg1) s[nt][3] = NEG;
            }
        }

        // ── online softmax: row max over this block, alpha rescale of O, exp into P ──
        float t0 = NEG, t1 = NEG;
#pragma unroll
        for (int nt = 0; nt < NT; nt++) {
            t0 = fmaxf(t0, fmaxf(s[nt][0], s[nt][1]));
            t1 = fmaxf(t1, fmaxf(s[nt][2], s[nt][3]));
        }
        t0 = fa_wmax(t0);
        t1 = fa_wmax(t1);
        const float n0 = fmaxf(m0, t0), n1 = fmaxf(m1, t1);
        const float a0 = __expf(m0 - n0), a1 = __expf(m1 - n1);
#pragma unroll
        for (int i = 0; i < FA_D / 8; i++) {
            oacc[i][0] *= a0; oacc[i][1] *= a0;
            oacc[i][2] *= a1; oacc[i][3] *= a1;
        }
        float s0 = 0.0f, s1 = 0.0f;
#pragma unroll
        for (int nt = 0; nt < NT; nt++) {
            const float p0 = __expf(s[nt][0] - n0), p1 = __expf(s[nt][1] - n0);
            const float p2 = __expf(s[nt][2] - n1), p3 = __expf(s[nt][3] - n1);
            s0 += p0 + p1; s1 += p2 + p3;
            s[nt][0] = p0; s[nt][1] = p1; s[nt][2] = p2; s[nt][3] = p3;
        }
        s0 = fa_wsum(s0);
        s1 = fa_wsum(s1);
        l0 = l0 * a0 + s0;
        l1 = l1 * a1 + s1;
        m0 = n0; m1 = n1;

        // ── O[16,d] += P[16,BN] @ V[BN,d]. PMMA=1: P's A-fragment for k-step `ks` is the
        //    four f32 of score tiles 2ks / 2ks+1 converted and packed in place — the m16n8k16
        //    A layout and the m16n8 D layout put a lane's k-pair at the same two registers,
        //    so no shared memory and no fence is involved. ──
        if (PMMA) {
#pragma unroll
            for (int ks = 0; ks < BN / 16; ks++) {
                unsigned pa[4];
                pa[0] = fa2_pk(s[2 * ks][0], s[2 * ks][1]);
                pa[1] = fa2_pk(s[2 * ks][2], s[2 * ks][3]);
                pa[2] = fa2_pk(s[2 * ks + 1][0], s[2 * ks + 1][1]);
                pa[3] = fa2_pk(s[2 * ks + 1][2], s[2 * ks + 1][3]);
#pragma unroll
                for (int np = 0; np < FA_D / 16; np++) {
                    unsigned b0, b1, b2, b3;
                    fa2_ldsm4t(b0, b1, b2, b3,
                               sV + (ks * 16 + lr8 + l7) * FA_LD + np * 16 + lc8);
                    fa2_mma(oacc[2 * np], pa, b0, b1);          // dims np*16 .. +7
                    fa2_mma(oacc[2 * np + 1], pa, b2, b3);      // dims np*16+8 .. +15
                }
            }
        } else {
            // P through shared memory (attribution arm). Each warp writes and reads back only
            // its OWN 16 rows, so the round trip needs no cross-warp fence — but the two row
            // groups of an m16n8 accumulator are `rlo` and `rlo + 8`, NOT 0 and 8: anchoring
            // at the tile base instead of at this lane's row scatters every lane's scores into
            // the wrong rows, which is exactly what this arm did on first write (max_abs 28.7
            // against the reference, 3.2 M of 3.67 M elements wrong) while the PMMA=1 arm —
            // which never leaves registers and so has no row to mis-anchor — was correct.
            __half* pw = sP + (warp * 16 + rlo) * sPld;
#pragma unroll
            for (int nt = 0; nt < NT; nt++) {
                *reinterpret_cast<__half2*>(pw + nt * 8 + chi) =
                    __floats2half2_rn(s[nt][0], s[nt][1]);
                *reinterpret_cast<__half2*>(pw + 8 * sPld + nt * 8 + chi) =
                    __floats2half2_rn(s[nt][2], s[nt][3]);
            }
            __syncthreads();
#pragma unroll
            for (int ks = 0; ks < BN / 16; ks++) {
                unsigned pa[4];
                fa2_ldsm4(pa[0], pa[1], pa[2], pa[3],
                          sP + (warp * 16 + lr8 + l7) * sPld + ks * 16 + lc8);
#pragma unroll
                for (int np = 0; np < FA_D / 16; np++) {
                    unsigned b0, b1, b2, b3;
                    fa2_ldsm4t(b0, b1, b2, b3,
                               sV + (ks * 16 + lr8 + l7) * FA_LD + np * 16 + lc8);
                    fa2_mma(oacc[2 * np], pa, b0, b1);
                    fa2_mma(oacc[2 * np + 1], pa, b2, b3);
                }
            }
        }
        __syncthreads();                            // buffer `cur` is dead
        if (DBUF) {
            fa2_load_kv<BN, 1>(bk, bv, kg, vg, kb + 2, kb_max, n_keys, hk, d, kvld, tid);
            fa2_cp_commit();
        }
    }

    // ── epilogue: divide by the row sums and write position-major f32 STRAIGHT TO GLOBAL.
    //    d0/d1 are (row rlo, cols nt*8+chi and +1) = one aligned float2; d2/d3 are row
    //    rlo+8 at the same columns. No shared staging, no fence. ──
    const float inv0 = (l0 > 0.0f) ? (1.0f / l0) : 0.0f;
    const float inv1 = (l1 > 0.0f) ? (1.0f / l1) : 0.0f;
    const int r0g = row0 + warp * 16 + rlo;
    const int r1g = r0g + 8;
    const bool w0 = r0g < m, w1 = r1g < m;
#pragma unroll
    for (int nt = 0; nt < FA_D / 8; nt++) {
        const int c = nt * 8 + chi;
        if (w0) *reinterpret_cast<float2*>(og + (size_t)r0g * qld + h * d + c) =
                    make_float2(oacc[nt][0] * inv0, oacc[nt][1] * inv0);
        if (w1) *reinterpret_cast<float2*>(og + (size_t)r1g * qld + h * d + c) =
                    make_float2(oacc[nt][2] * inv1, oacc[nt][3] * inv1);
    }
}

// Dynamic shared bytes. The window is FOUR K/V tiles = 4 * BN * FA_LD HALVES (two rotating
// buffers, each a K tile and a V tile), i.e. 8 * BN * FA_LD BYTES: 34.8 KB at BN=32, 69.6 KB
// at BN=64, 139.3 KB at BN=128 against the A100's 163 KB per-block opt-in. PMMA=1 needs no
// more than that because the Q tile is staged inside the second rotating buffer (legal iff
// FA_BM <= 2*BN, host-checked) and the epilogue writes straight to global. PMMA=0 adds the sP
// round-trip window.
//
// This formula was wrong on first write as `8 * BN * FA_LD * sizeof(__half)` — it counted the
// element size twice, asked for 278 KB at BN=128, and because one failed
// `cudaFuncSetAttribute` used to abort the whole table, that single overflow DECLINED EVERY
// bn and every variant with a bare cudaErrorInvalidValue. The bytes/halves distinction is
// therefore stated in the formula itself, and the attribute table now records per-instantiation
// success so one shape that cannot fit declines only itself (-305).
template <int BN, int PMMA>
static inline int fa2_smem_bytes(void) {
    int b = 4 * BN * FA_LD * (int)sizeof(__half);
    if (!PMMA) b += FA_BM * (BN + FA_PLD) * (int)sizeof(__half);
    return b;
}

// ON-DEVICE layout probe for the raw-mma path. Both B roles must yield D[r][n] = (r+1)*(n+1),
// but they are filled DIFFERENTLY, because the two roles differ in which stored index the
// operand's k dimension is:
//   A[r][c]      = (c==0 ? r+1 : 0)  ->  A[r][k]      = delta(k,0)*(r+1)
//   K_tile[n][k] = (k==0 ? n+1 : 0)  ->  B[k][n] = K^T = delta(k,0)*(n+1)
//   V_tile[k][n] = (k==0 ? n+1 : 0)  ->  B[k][n] = V   = delta(k,0)*(n+1)
// The K tile is stored [key][dim] and consumed as B = K^T, so its delta lands on the stored
// COLUMN; the V tile is stored [key][dim] and consumed as B = V directly, so its delta lands
// on the stored ROW. Filling both from one pattern tests only one of them: the first version
// of this probe did exactly that and reported a MISMATCH against a CORRECT kernel, because
// with V[k][n] = delta(n,0)*(k+1) the true D[r][n>0] is 0 and not (r+1)*(n+1).
// Max product 16*8 = 128: exact in f16 (integers to 2048) and in f32, so the check is an
// integer equality with no tolerance and no floating-point judgement call. Lane L's four D
// registers must read back (row+1)*(col+1) for row = L/4 + 8*(i>>1), col = 2*(L%4) + (i&1).
extern "C" __global__ void _fa2_layout_probe_kernel(float* out) {
    __shared__ __half sA[16 * FA_LD];
    __shared__ __half sK[16 * FA_LD];
    __shared__ __half sV[16 * FA_LD];
    const int t = threadIdx.x;
    for (int i = t; i < 16 * FA_LD; i += blockDim.x) {
        int r = i / FA_LD, c = i - r * FA_LD;
        sA[i] = __float2half(c == 0 ? (float)(r + 1) : 0.0f);
        sK[i] = __float2half(c == 0 ? (float)(r + 1) : 0.0f);   // delta on the stored COLUMN
        sV[i] = __float2half(r == 0 ? (float)(c + 1) : 0.0f);   // delta on the stored ROW
    }
    __syncwarp();
    unsigned a[4], b0, b1, b2, b3;
    // exactly the kernel's A address generator, for k-step 0
    fa2_ldsm4(a[0], a[1], a[2], a[3],
              sA + ((((t >> 3) & 1) << 3) + (t & 7)) * FA_LD + (((t >> 3) & 2) << 2));
    // role 1: B = K^T, i.e. the [key][dim] tile loaded NON-transposed
    fa2_ldsm4(b0, b1, b2, b3,
              sK + ((((t >> 3) & 1) << 3) + (t & 7)) * FA_LD + (((t >> 3) & 2) << 2));
    float dk[4] = {0.f, 0.f, 0.f, 0.f};
    fa2_mma(dk, a, b0, b2);
    for (int i = 0; i < 4; i++) out[t * 4 + i] = dk[i];
    // role 2: B = V, i.e. the [key][dim] tile loaded TRANSPOSED
    fa2_ldsm4t(b0, b1, b2, b3,
               sV + ((((t >> 3) & 1) << 3) + (t & 7)) * FA_LD + (((t >> 3) & 2) << 2));
    float dv[4] = {0.f, 0.f, 0.f, 0.f};
    fa2_mma(dv, a, b0, b1);
    for (int i = 0; i < 4; i++) out[128 + t * 4 + i] = dv[i];
}

static int g_fa2_layout_ok = -1;   // -1 unchecked, 0 ok, 1 mismatch

extern "C" int64_t tc_shim_fa2_layout_probe(void) {
    if (g_fa2_layout_ok == 0) return 0;
    if (g_fa2_layout_ok == 1) return -311;
    float* d = nullptr;
    cudaError_t e = cudaMalloc(&d, 256 * sizeof(float));
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    cudaMemsetAsync(d, 0, 256 * sizeof(float), g_stream);
    _fa2_layout_probe_kernel<<<1, 32, 0, g_stream>>>(d);
    e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaStreamSynchronize(g_stream);
    if (e != cudaSuccess) { cudaFree(d); record_error((int64_t)e); return (int64_t)e; }
    float h[256];
    e = cudaMemcpy(h, d, 256 * sizeof(float), cudaMemcpyDeviceToHost);
    cudaFree(d);
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    for (int part = 0; part < 2; part++) {
        for (int lane = 0; lane < 32; lane++) {
            for (int i = 0; i < 4; i++) {
                int row = (lane >> 2) + 8 * (i >> 1);
                int col = 2 * (lane & 3) + (i & 1);
                float want = (float)((row + 1) * (col + 1));
                if (h[part * 128 + lane * 4 + i] != want) {
                    g_fa2_layout_ok = 1;
                    fprintf(stderr,
                            "[tc_shim] FA2 %s layout MISMATCH: lane %d reg %d = %g, expected "
                            "%g (row %d col %d) — the FA2 lever is DISABLED for this toolkit "
                            "(the session keeps FRONT 3's fused flash attention).\n",
                            part == 0 ? "K (ldmatrix non-trans)" : "V (ldmatrix trans)", lane, i,
                            (double)h[part * 128 + lane * 4 + i], (double)want, row, col);
                    return -311;
                }
            }
        }
    }
    g_fa2_layout_ok = 0;
    return 0;
}

static int g_fa2_attr_done = 0;
// [bn index: 0=32, 1=64, 2=128][PMMA] = 1 once the opt-in shared-memory attribute was granted
// for that exact instantiation. A shape that cannot fit on this device declines ONLY ITSELF
// (-305) instead of taking the whole table down with it.
static int g_fa2_smem_ok[3][2] = {{0, 0}, {0, 0}, {0, 0}};
static inline int fa2_bn_idx(int64_t bn) { return bn == 32 ? 0 : (bn == 128 ? 2 : 1); }

static int64_t fa2_set_attrs(void) {
    if (g_fa2_attr_done) return 0;
    cudaError_t e = cudaSuccess;
    // A launch failure here must never be silent: the opt-in shared-memory attribute is the one
    // property a >48 KB dynamic request depends on, and cudaErrorInvalidValue at launch time
    // does not say WHICH kernel or how many bytes it wanted.
#define FA2_ATTR(BN_, PM_, IDX_, K)                                                    \
    do {                                                                               \
        int sm_ = fa2_smem_bytes<BN_, PM_>();                                          \
        cudaError_t e_ = cudaFuncSetAttribute(                                         \
            K, cudaFuncAttributeMaxDynamicSharedMemorySize, sm_);                      \
        g_fa2_smem_ok[IDX_][PM_] = (e_ == cudaSuccess) ? 1 : 0;                        \
        if (e_ != cudaSuccess)                                                         \
            fprintf(stderr,                                                            \
                    "[tc_shim] FA2 BN=%d PMMA=%d DECLINED: %d B of dynamic shared "     \
                    "memory is not grantable here (%s) — that shape keeps the "         \
                    "previous kernel.\n",                                              \
                    (BN_), (PM_), sm_, cudaGetErrorString(e_));                        \
    } while (0)
    FA2_ATTR(32, 1, 0, (_fa2_causal_kernel<32, 1, 1>));
    FA2_ATTR(64, 1, 1, (_fa2_causal_kernel<64, 1, 1>));
    FA2_ATTR(128, 1, 2, (_fa2_causal_kernel<128, 1, 1>));
    FA2_ATTR(32, 0, 0, (_fa2_causal_kernel<32, 0, 1>));
    FA2_ATTR(64, 0, 1, (_fa2_causal_kernel<64, 0, 1>));
    FA2_ATTR(128, 0, 2, (_fa2_causal_kernel<128, 0, 1>));
    FA2_ATTR(64, 1, 1, (_fa2_causal_kernel<64, 1, 0>));
#undef FA2_ATTR
    (void)e;
    g_fa2_attr_done = 1;
    return 0;
}

// bn: 32 / 64 / 128 key columns per online-softmax block (anything else -> 64).
// variant: 0 = cp.async double buffer + in-register P (the lever);
//          1 = cp.async double buffer, P still round-trips through shared (attribution);
//          2 = in-register P, synchronous K/V loads (attribution).
// Returns -301 unsupported head_dim, -304 non-integral GQA, -305 the Q-tile-in-buffer-1
// overlay does not fit (FA_BM > 2*BN), -311 the on-device layout probe disagreed (the caller
// MUST fall back), else the cudaError_t. Enqueues on the shim stream, does NOT sync.
extern "C" int64_t tc_shim_fa2_causal_async(const void* q_f32, const void* k16, const void* v16,
                                            void* o_f32, const void* scale_f32, int64_t m,
                                            int64_t n_keys, int64_t h_q, int64_t h_kv, int64_t d,
                                            int64_t pos_base, int64_t bn, int64_t variant) {
    if (d != FA_D) return -301;
    if (m <= 0 || n_keys <= 0 || h_kv <= 0 || h_q <= 0) return 0;
    if ((h_q % h_kv) != 0) return -304;
    // the Q tile is staged inside rotating buffer 1, which holds 2*BN*FA_LD halves: the
    // overlay is legal iff FA_BM*FA_LD <= 2*BN*FA_LD, i.e. FA_BM <= 2*BN.
    {
        int bnv = (bn == 32 || bn == 128) ? (int)bn : 64;
        if (FA_BM > 2 * bnv) return -305;
    }
    int64_t r = tc_shim_fa2_layout_probe();
    if (r != 0) return r;
    r = fa2_set_attrs();
    if (r != 0) return r;
    // the chosen instantiation must have been granted its dynamic shared memory, or the launch
    // would fail with a bare cudaErrorInvalidValue that names nothing.
    {
        int pmm = (variant == 1) ? 0 : 1;
        if (!g_fa2_smem_ok[fa2_bn_idx(bn)][pmm]) return -305;
        if (variant == 2 && bn != 64) return -305;
    }
    dim3 grid((unsigned)((m + FA_BM - 1) / FA_BM), (unsigned)h_q);
    dim3 block(FA_NWARP * 32);
    int im = (int)m, ink = (int)n_keys, ihq = (int)h_q, ihkv = (int)h_kv, id = (int)d;
    int ipos = (int)pos_base;
    const float* q = (const float*)q_f32;
    const __half* k = (const __half*)k16;
    const __half* v = (const __half*)v16;
    const float* sp = (const float*)scale_f32;
    float* o = (float*)o_f32;
    cudaError_t e = cudaSuccess;
#define FA2_LAUNCH(K, SMB)                                                             \
    K<<<grid, block, (size_t)(SMB), g_stream>>>(q, k, v, o, sp, im, ink, ihq, ihkv,    \
                                                id, ipos)
    if (variant == 1) {                       // double buffer, P through shared
        if (bn == 32) { FA2_LAUNCH((_fa2_causal_kernel<32, 0, 1>), (fa2_smem_bytes<32, 0>())); }
        else if (bn == 128) { FA2_LAUNCH((_fa2_causal_kernel<128, 0, 1>), (fa2_smem_bytes<128, 0>())); }
        else { FA2_LAUNCH((_fa2_causal_kernel<64, 0, 1>), (fa2_smem_bytes<64, 0>())); }
    } else if (variant == 2) {                // synchronous loads, P in registers
        if (bn != 64) return -305;
        FA2_LAUNCH((_fa2_causal_kernel<64, 1, 0>), (fa2_smem_bytes<64, 1>()));
    } else {                                  // the lever: both
        if (bn == 32) { FA2_LAUNCH((_fa2_causal_kernel<32, 1, 1>), (fa2_smem_bytes<32, 1>())); }
        else if (bn == 128) { FA2_LAUNCH((_fa2_causal_kernel<128, 1, 1>), (fa2_smem_bytes<128, 1>())); }
        else { FA2_LAUNCH((_fa2_causal_kernel<64, 1, 1>), (fa2_smem_bytes<64, 1>())); }
    }
#undef FA2_LAUNCH
    e = cudaGetLastError();
    if (e != cudaSuccess) {
        int smb = (variant == 1)
            ? ((bn == 32) ? fa2_smem_bytes<32, 0>()
                          : (bn == 128 ? fa2_smem_bytes<128, 0>() : fa2_smem_bytes<64, 0>()))
            : ((bn == 32) ? fa2_smem_bytes<32, 1>()
                          : (bn == 128 ? fa2_smem_bytes<128, 1>() : fa2_smem_bytes<64, 1>()));
        fprintf(stderr,
                "[tc_shim] FA2 LAUNCH FAILED: %s | variant=%lld bn=%lld smem=%d B "
                "grid=%ux%u block=%u m=%lld n_keys=%lld h_q=%lld h_kv=%lld d=%lld pos=%lld\n",
                cudaGetErrorString(e), (long long)variant, (long long)bn, smb, grid.x, grid.y,
                block.x, (long long)m, (long long)n_keys, (long long)h_q, (long long)h_kv,
                (long long)d, (long long)pos_base);
    }
    record_error((int64_t)e);
    return (int64_t)e;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// FA3 — GQA-PACKED CAUSAL FLASH ATTENTION (FRONT 5 lever 1)  `-D ALGENTA_7B_PF_FA3`
//
// WHY FRONT 4's FA2 STOPS AT 35% MFU, AND WHY NO BN CAN FIX IT. FA2 measures 33.7 ms over the
// RAG-4096 FA block against TensorRT-LLM's 24.4 ms, and round 4's own BN sweep is flat to
// INVERTED (32 -> 33.7, 64 -> 36.4, 128 -> 38.0 ms). A sweep that gets worse as the tile gets
// bigger is the signature of a limit BN cannot touch. The per-chunk ladder names it:
//
//      pp1024  106.5 us/layer   7.52 GFLOP   70.6 TFLOPS  22.6% MFU
//      chunk1  246.8 us/layer  22.56 GFLOP   91.4 TFLOPS  29.3% MFU
//      chunk2  376.8 us/layer  37.59 GFLOP   99.8 TFLOPS  32.0% MFU
//      chunk3  475.1 us/layer  52.62 GFLOP  110.8 TFLOPS  35.5% MFU
//
// MFU climbs monotonically with the work each CTA is handed and then stalls near 35%, because
// the kernel is MEMORY bound. An FA2 CTA covers FA_BM=64 query rows of ONE query head and pulls
// the K/V tile of its own kv head out of L2, so per key it moves 128 dims x 2 (K and V) x 2
// bytes = 512 B to do 64 rows x 512 FLOP = 32768 FLOP: an arithmetic intensity of EXACTLY
// 64 FLOP/byte. That number is a property of the CTA's shape, not of BN — BN scales the traffic
// and the FLOPs together, which is precisely why the sweep was flat. The A100's L2<->SM balance
// point is ~312/4 = 78 FLOP/byte, and 64 < 78, so 44% MFU is unreachable from inside one
// (row-block, query-head) CTA no matter how it is tiled. Measured, chunk3 alone streams 822 MB
// of K/V per layer-launch against a UNIQUE working set of 8.39 MB — a 98x amplification, and
// 7/8 of those bytes are the same bytes re-read by the seven query heads that share one kv head
// (Qwen2.5-7B: h_q=28, h_kv=4, g=7).
//
// WHAT THIS DOES. One CTA now covers BMQ query rows for ALL g query heads of ONE kv head, so the
// K/V tile is fetched once per (row-block, kv-head) instead of once per query head. Intensity
// becomes BMQ*g FLOP/byte — 112 at BMQ=16, 224 at BMQ=32 — which is over the balance point, so
// the kernel turns compute bound and its MFU is set by the mma/softmax mix rather than by L2.
//
// BIT-EXACTNESS (the reason this is a scheduling change and not a numeric one). Warp w owns ONE
// 16-row mma tile of ONE query head and runs FRONT 4's per-warp body verbatim: same key-block
// order, same m16n8k16 accumulation order, same f32 online max/sum, same __expf, same
// round-to-nearest-even f16 P at the same point, same causal and cache-tail predicate, same
// scale folded into the same f32->f16 Q conversion. Nothing about a given output element's
// arithmetic changes — only which SM it lands on, and how many neighbours share its K/V fetch.
// Two consequences fall out and both are wins:
//   * kb_max is taken at 16-row granularity instead of FA_BM's 64, so a warp no longer walks up
//     to three extra key blocks that FA2 walked and then masked away. Those blocks were
//     arithmetically inert (an all-masked block gives n=max(m,NEG)=m, a=exp(0)=1, s=0, so
//     oacc*1 and l*1+0), which is exactly why dropping them cannot move a bit.
//   * the Q A-fragment is built DIRECTLY in registers from global f32 using the same
//     __floats2half2_rn(v*scale) rounding FA2's shared staging applied, so FA2's sQ window, its
//     two fences and its FA_BM<=2*BN overlay constraint all disappear; only the K/V double
//     buffer is left in shared memory (34.8 KB at BN=32).
// The A mapping is now hand-built rather than produced by ldmatrix, so `_fa3_layout_probe_kernel`
// pins it ON DEVICE the same way `_fa2_layout_probe_kernel` pins FA2's: A[r][k]=delta(k,0)*(r+1)
// against K_tile[n][k]=delta(k,0)*(n+1) must give D[r][n]=(r+1)*(n+1) for every lane and
// register, in exact small integers, with no tolerance and no floating-point judgement call. A
// mismatch returns -314 and the caller keeps FA2. fa_probe additionally compares every element
// against a host DOUBLE-PRECISION reference at all six raced shapes including the odd tail
// (m=660, n_keys=1716, pos=1056).
//
// DECLINED, NEVER FAKED: head_dim != 128 (-301), non-integral GQA (-304), g not instantiated
// (-312), too few CTAs to fill the device so a short prefill would starve (-313), on-device
// layout probe disagreed (-314), or shared memory not grantable (-305). Every decline leaves the
// caller on the kernel it already had.
// ═══════════════════════════════════════════════════════════════════════════════════════════

#define FA3_D 128
#define FA3_LD (FA3_D + 8)          // the same 4-bank row shift FA_LD documents
#define FA3_G 7                     // the only GQA group size instantiated (Qwen2.5-7B 28/4)

// Cooperative 16-byte async fetch of one K and one V tile for key block `kb`, spread over NTH
// threads. FA2's loader hard-codes FA_NWARP*32==128 and unrolls by that exact quotient; a packed
// CTA has G*BMQ/16 warps, so this one strides instead and needs no divisibility assumption.
template <int BN, int NTH>
__device__ __forceinline__ void fa3_load_kv(__half* dK, __half* dV, const __half* kg,
                                            const __half* vg, int kb, int kb_max, int n_keys,
                                            int hk, int d, int kvld, int tid) {
    if (kb > kb_max) return;
    const int kbase = kb * BN;
    const int nvec = BN * (FA3_D / 8);            // 16-byte vector columns in one tile
    for (int t = tid; t < nvec; t += NTH) {
        const int r = t >> 4;                     // FA3_D / 8 == 16 vector columns per row
        const int c8 = t & 15;
        const int gj = kbase + r;
        const int gc = gj < n_keys ? gj : n_keys - 1;   // stay in bounds even when zero-filling
        const size_t off = (size_t)gc * kvld + hk * d + c8 * 8;
        const int sz = gj < n_keys ? 16 : 0;
        fa2_cp16(dK + r * FA3_LD + c8 * 8, kg + off, sz);
        fa2_cp16(dV + r * FA3_LD + c8 * 8, vg + off, sz);
    }
}

template <int BN, int BMQ, int G, int MINB>
__global__ void __launch_bounds__((G * (BMQ / 16)) * 32, MINB)
_fa3_causal_kernel(const float* __restrict__ qg, const __half* __restrict__ kg,
                   const __half* __restrict__ vg, float* __restrict__ og,
                   const float* __restrict__ scalep, int m, int n_keys, int h_q, int h_kv, int d,
                   int pos_base) {
    constexpr int RPB = BMQ / 16;                 // 16-row mma tiles per query head
    constexpr int NW = G * RPB;                   // warps per CTA, one mma tile each
    constexpr int NTH = NW * 32;
    constexpr int NT = BN / 8;                    // m16n8 score tiles per key block
    const float scale = *scalep;
    extern __shared__ __half smem[];
    const int KVH = BN * FA3_LD;                  // halves in one K (or V) tile

    const int tid = threadIdx.x;
    const int warp = tid >> 5;
    const int lane = tid & 31;
    const int qi = blockIdx.x;
    const int hk = blockIdx.y;                    // ONE kv head per CTA — the whole point
    const int jw = warp / RPB;                    // this warp's head inside the GQA group
    const int rw = warp - jw * RPB;               // this warp's 16-row group inside BMQ
    const int h = hk * G + jw;
    const int row0 = qi * BMQ + rw * 16;
    const int kvld = h_kv * d;
    const int qld = h_q * d;
    // Identical address generators to FA2, hoisted out of the key-block loop.
    const int lr8 = ((lane >> 3) & 1) << 3;       // 0 or 8
    const int lc8 = ((lane >> 3) & 2) << 2;       // 0 or 8
    const int l7 = lane & 7;
    const int rlo = lane >> 2;                    // this lane's row inside the tile's 16
    const int chi = (lane & 3) << 1;              // this lane's column base in an 8-wide tile

    int rows_here = m - row0;
    if (rows_here > 16) rows_here = 16;
    int kb_max = -1;                              // an out-of-range row group does no work
    if (rows_here > 0) {
        const int kb_causal = (pos_base + row0 + rows_here - 1) / BN;
        const int kb_keys = (n_keys - 1) / BN;
        kb_max = kb_causal < kb_keys ? kb_causal : kb_keys;
    }

    // ── kb=0 in flight FIRST (async, buffer 0 only), then build the Q A-fragments while it
    //    travels, then put kb=1 in flight. Buffers 0 and 1 are disjoint, so no fence separates
    //    the two commits; wait_group 1 retires them in order inside the loop. ──
    fa3_load_kv<BN, NTH>(smem, smem + KVH, kg, vg, 0, kb_max, n_keys, hk, d, kvld, tid);
    fa2_cp_commit();

    // ── Q A-fragments: loaded ONCE per CTA, reused across every key block, built straight from
    //    global f32 in the m16n8k16 A layout — lane l holds rows row0+rlo and row0+rlo+8 at
    //    columns ks*16+chi+{0,1} and +{8,9}. Same __floats2half2_rn(v*scale) rounding, at the
    //    same point in the expression, as FA2's shared-memory staging applied. ──
    unsigned qa[FA3_D / 16][4];
    {
        const int rA = row0 + rlo, rB = rA + 8;
        const bool vA = rA < m, vB = rB < m;
        const float* pA = qg + (size_t)rA * qld + h * d;
        const float* pB = qg + (size_t)rB * qld + h * d;
#pragma unroll
        for (int ks = 0; ks < FA3_D / 16; ks++) {
            const int c0 = ks * 16 + chi;
            const float2 x00 = vA ? *reinterpret_cast<const float2*>(pA + c0)
                                  : make_float2(0.0f, 0.0f);
            const float2 x01 = vB ? *reinterpret_cast<const float2*>(pB + c0)
                                  : make_float2(0.0f, 0.0f);
            const float2 x10 = vA ? *reinterpret_cast<const float2*>(pA + c0 + 8)
                                  : make_float2(0.0f, 0.0f);
            const float2 x11 = vB ? *reinterpret_cast<const float2*>(pB + c0 + 8)
                                  : make_float2(0.0f, 0.0f);
            qa[ks][0] = fa2_pk(x00.x * scale, x00.y * scale);
            qa[ks][1] = fa2_pk(x01.x * scale, x01.y * scale);
            qa[ks][2] = fa2_pk(x10.x * scale, x10.y * scale);
            qa[ks][3] = fa2_pk(x11.x * scale, x11.y * scale);
        }
    }
    fa3_load_kv<BN, NTH>(smem + 2 * KVH, smem + 3 * KVH, kg, vg, 1, kb_max, n_keys, hk, d,
                         kvld, tid);
    fa2_cp_commit();

    float oacc[FA3_D / 8][4];
#pragma unroll
    for (int i = 0; i < FA3_D / 8; i++) {
        oacc[i][0] = 0.0f; oacc[i][1] = 0.0f; oacc[i][2] = 0.0f; oacc[i][3] = 0.0f;
    }
    const float NEG = -1.0e30f;
    float m0 = NEG, m1 = NEG, l0 = 0.0f, l1 = 0.0f;
    const int qg0 = pos_base + row0 + rlo;        // global position of row `rlo`
    const int qg1 = qg0 + 8;

    for (int kb = 0; kb <= kb_max; kb++) {
        const int cur = kb & 1;
        __half* bk = smem + cur * 2 * KVH;        // this iteration's rotating buffer
        __half* bv = bk + KVH;
        fa2_cp_wait1();
        __syncthreads();
        const __half* sK = bk;
        const __half* sV = bv;

        // ── S[16,BN] = Q[16,d] @ K^T[d,BN], f32 accumulate. FRONT 4's body verbatim. ──
        float s[NT][4];
#pragma unroll
        for (int nt = 0; nt < NT; nt++) {
            s[nt][0] = 0.0f; s[nt][1] = 0.0f; s[nt][2] = 0.0f; s[nt][3] = 0.0f;
        }
#pragma unroll
        for (int ks = 0; ks < FA3_D / 16; ks++) {
#pragma unroll
            for (int np = 0; np < BN / 16; np++) {
                unsigned b0, b1, b2, b3;
                fa2_ldsm4(b0, b1, b2, b3,
                          sK + (np * 16 + lr8 + l7) * FA3_LD + ks * 16 + lc8);
                fa2_mma(s[2 * np], qa[ks], b0, b2);         // n-tile np*16
                fa2_mma(s[2 * np + 1], qa[ks], b1, b3);     // n-tile np*16 + 8
            }
        }

        // ── causal + cache-tail mask, verbatim. ──
        const bool need_mask = (kb * BN + BN - 1 > qg0) || (kb * BN + BN - 1 >= n_keys);
        if (need_mask) {
#pragma unroll
            for (int nt = 0; nt < NT; nt++) {
                const int j = kb * BN + nt * 8 + chi;
                const int jc = j < n_keys ? j : -1;                 // cache tail
                if (jc < 0 || j > qg0) s[nt][0] = NEG;
                if (jc < 0 || j + 1 > qg0) s[nt][1] = NEG;
                if (jc < 0 || j > qg1) s[nt][2] = NEG;
                if (jc < 0 || j + 1 > qg1) s[nt][3] = NEG;
            }
        }

        // ── online softmax: row max over this block, alpha rescale of O, exp into P. ──
        float t0 = NEG, t1 = NEG;
#pragma unroll
        for (int nt = 0; nt < NT; nt++) {
            t0 = fmaxf(t0, fmaxf(s[nt][0], s[nt][1]));
            t1 = fmaxf(t1, fmaxf(s[nt][2], s[nt][3]));
        }
        t0 = fa_wmax(t0);
        t1 = fa_wmax(t1);
        const float n0 = fmaxf(m0, t0), n1 = fmaxf(m1, t1);
        const float a0 = __expf(m0 - n0), a1 = __expf(m1 - n1);
#pragma unroll
        for (int i = 0; i < FA3_D / 8; i++) {
            oacc[i][0] *= a0; oacc[i][1] *= a0;
            oacc[i][2] *= a1; oacc[i][3] *= a1;
        }
        float s0 = 0.0f, s1 = 0.0f;
#pragma unroll
        for (int nt = 0; nt < NT; nt++) {
            const float p0 = __expf(s[nt][0] - n0), p1 = __expf(s[nt][1] - n0);
            const float p2 = __expf(s[nt][2] - n1), p3 = __expf(s[nt][3] - n1);
            s0 += p0 + p1; s1 += p2 + p3;
            s[nt][0] = p0; s[nt][1] = p1; s[nt][2] = p2; s[nt][3] = p3;
        }
        s0 = fa_wsum(s0);
        s1 = fa_wsum(s1);
        l0 = l0 * a0 + s0;
        l1 = l1 * a1 + s1;
        m0 = n0; m1 = n1;

        // ── O[16,d] += P[16,BN] @ V[BN,d], P's A-fragment packed in registers. ──
#pragma unroll
        for (int ks = 0; ks < BN / 16; ks++) {
            unsigned pa[4];
            pa[0] = fa2_pk(s[2 * ks][0], s[2 * ks][1]);
            pa[1] = fa2_pk(s[2 * ks][2], s[2 * ks][3]);
            pa[2] = fa2_pk(s[2 * ks + 1][0], s[2 * ks + 1][1]);
            pa[3] = fa2_pk(s[2 * ks + 1][2], s[2 * ks + 1][3]);
#pragma unroll
            for (int np = 0; np < FA3_D / 16; np++) {
                unsigned b0, b1, b2, b3;
                fa2_ldsm4t(b0, b1, b2, b3,
                           sV + (ks * 16 + lr8 + l7) * FA3_LD + np * 16 + lc8);
                fa2_mma(oacc[2 * np], pa, b0, b1);          // dims np*16 .. +7
                fa2_mma(oacc[2 * np + 1], pa, b2, b3);      // dims np*16+8 .. +15
            }
        }
        __syncthreads();                            // buffer `cur` is dead
        fa3_load_kv<BN, NTH>(bk, bv, kg, vg, kb + 2, kb_max, n_keys, hk, d, kvld, tid);
        fa2_cp_commit();
    }

    // ── epilogue: divide by the row sums and write position-major f32 STRAIGHT TO GLOBAL, as
    //    one aligned float2 per (row, dim-pair). No shared staging, no fence. ──
    const float inv0 = (l0 > 0.0f) ? (1.0f / l0) : 0.0f;
    const float inv1 = (l1 > 0.0f) ? (1.0f / l1) : 0.0f;
    const int r0g = row0 + rlo;
    const int r1g = r0g + 8;
    const bool w0 = r0g < m, w1 = r1g < m;
#pragma unroll
    for (int nt = 0; nt < FA3_D / 8; nt++) {
        const int c = nt * 8 + chi;
        if (w0) *reinterpret_cast<float2*>(og + (size_t)r0g * qld + h * d + c) =
                    make_float2(oacc[nt][0] * inv0, oacc[nt][1] * inv0);
        if (w1) *reinterpret_cast<float2*>(og + (size_t)r1g * qld + h * d + c) =
                    make_float2(oacc[nt][2] * inv1, oacc[nt][3] * inv1);
    }
}

// ON-DEVICE probe for FA3's HAND-BUILT A fragment. FA2's probe cannot cover this: FA2 gets its
// A tile from ldmatrix, FA3 assembles the four registers itself from strided global f32, so the
// lane -> (row, column) assignment is a new assumption and gets its own integer check. A[r][k] =
// delta(k,0)*(r+1) against K_tile[n][k] = delta(k,0)*(n+1) makes the true product
// D[r][n] = (r+1)*(n+1); max 16*8 = 128 is exact in both f16 and f32, so this is an integer
// equality with no tolerance. Lane L's register i must read back (row+1)*(col+1) for
// row = L/4 + 8*(i>>1), col = 2*(L%4) + (i&1) — the same reading FA2's probe uses.
extern "C" __global__ void _fa3_layout_probe_kernel(float* out) {
    __shared__ float sQ[16 * FA3_D];
    __shared__ __half sK[16 * FA3_LD];
    const int lane = threadIdx.x;
    for (int i = lane; i < 16 * FA3_D; i += 32) {
        const int r = i / FA3_D, c = i - r * FA3_D;
        sQ[i] = (c == 0) ? (float)(r + 1) : 0.0f;
    }
    for (int i = lane; i < 16 * FA3_LD; i += 32) {
        const int r = i / FA3_LD, c = i - r * FA3_LD;
        sK[i] = __float2half((c == 0) ? (float)(r + 1) : 0.0f);   // delta on the stored COLUMN
    }
    __syncwarp();
    const int lr8 = ((lane >> 3) & 1) << 3;
    const int lc8 = ((lane >> 3) & 2) << 2;
    const int l7 = lane & 7;
    const int rlo = lane >> 2;
    const int chi = (lane & 3) << 1;
    // the kernel's A generator verbatim, at scale 1.0 and a 128-float row stride
    unsigned qa[FA3_D / 16][4];
#pragma unroll
    for (int ks = 0; ks < FA3_D / 16; ks++) {
        const int c0 = ks * 16 + chi;
        const float* pA = sQ + rlo * FA3_D;
        const float* pB = sQ + (rlo + 8) * FA3_D;
        const float2 x00 = *reinterpret_cast<const float2*>(pA + c0);
        const float2 x01 = *reinterpret_cast<const float2*>(pB + c0);
        const float2 x10 = *reinterpret_cast<const float2*>(pA + c0 + 8);
        const float2 x11 = *reinterpret_cast<const float2*>(pB + c0 + 8);
        qa[ks][0] = fa2_pk(x00.x, x00.y);
        qa[ks][1] = fa2_pk(x01.x, x01.y);
        qa[ks][2] = fa2_pk(x10.x, x10.y);
        qa[ks][3] = fa2_pk(x11.x, x11.y);
    }
    unsigned b0, b1, b2, b3;
    fa2_ldsm4(b0, b1, b2, b3, sK + (lr8 + l7) * FA3_LD + lc8);
    float dk[4] = {0.f, 0.f, 0.f, 0.f};
    fa2_mma(dk, qa[0], b0, b2);
    for (int i = 0; i < 4; i++) out[lane * 4 + i] = dk[i];
}

static int g_fa3_layout_ok = -1;   // -1 unchecked, 0 ok, 1 mismatch

extern "C" int64_t tc_shim_fa3_layout_probe(void) {
    if (g_fa3_layout_ok == 0) return 0;
    if (g_fa3_layout_ok == 1) return -314;
    float* d = nullptr;
    cudaError_t e = cudaMalloc(&d, 128 * sizeof(float));
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    cudaMemsetAsync(d, 0, 128 * sizeof(float), g_stream);
    _fa3_layout_probe_kernel<<<1, 32, 0, g_stream>>>(d);
    e = cudaGetLastError();
    if (e == cudaSuccess) e = cudaStreamSynchronize(g_stream);
    if (e != cudaSuccess) { cudaFree(d); record_error((int64_t)e); return (int64_t)e; }
    float h[128];
    e = cudaMemcpy(h, d, 128 * sizeof(float), cudaMemcpyDeviceToHost);
    cudaFree(d);
    if (e != cudaSuccess) { record_error((int64_t)e); return (int64_t)e; }
    for (int lane = 0; lane < 32; lane++) {
        for (int i = 0; i < 4; i++) {
            const int row = (lane >> 2) + 8 * (i >> 1);
            const int col = 2 * (lane & 3) + (i & 1);
            const float want = (float)((row + 1) * (col + 1));
            if (h[lane * 4 + i] != want) {
                g_fa3_layout_ok = 1;
                fprintf(stderr,
                        "[tc_shim] FA3 hand-built A-fragment layout MISMATCH: lane %d reg %d = "
                        "%g, expected %g (row %d col %d) — the FA3 lever is DISABLED for this "
                        "toolkit (the session keeps FRONT 4's FA2).\n",
                        lane, i, (double)h[lane * 4 + i], (double)want, row, col);
                return -314;
            }
        }
    }
    g_fa3_layout_ok = 0;
    return 0;
}

// The instantiated (BN, BMQ, MINB) table, spelled out. fa3_cfg_idx's rows and fa3_set_attrs's
// calls and the launch switch below must list the SAME six shapes; anything absent is DECLINED
// with -312 rather than silently rounded onto a neighbour.
#define FA3_NCFG 6

static int fa3_cfg_idx(int64_t bn, int64_t bmq, int64_t minb) {
    static const int T[FA3_NCFG][3] = {{32, 16, 1}, {32, 16, 2}, {64, 16, 1},
                                       {64, 16, 2}, {32, 32, 1}, {64, 32, 1}};
    for (int i = 0; i < FA3_NCFG; i++)
        if (T[i][0] == bn && T[i][1] == bmq && T[i][2] == minb) return i;
    return -1;
}
// 4 rotating K/V tiles, in BYTES. FA2's first version of this formula counted the element size
// twice and thereby declined every shape at once; the bytes/halves distinction is stated here.
static inline int fa3_smem_bytes(int64_t bn) { return (int)(4 * bn * FA3_LD * sizeof(__half)); }

static int g_fa3_attr_done = 0;
static int g_fa3_ok[FA3_NCFG] = {0, 0, 0, 0, 0, 0};

static int64_t fa3_set_attrs(void) {
    if (g_fa3_attr_done) return 0;
    // The kernel symbol is passed as a macro argument WRAPPED IN PARENS, exactly as FA2_ATTR
    // does: the template argument list contains commas, which the preprocessor would otherwise
    // read as argument separators.
#define FA3_ATTR(BN_, BMQ_, MINB_, K)                                                           \
    do {                                                                                        \
        int sm_ = fa3_smem_bytes(BN_);                                                          \
        cudaError_t e_ = cudaFuncSetAttribute(                                                  \
            K, cudaFuncAttributeMaxDynamicSharedMemorySize, sm_);                               \
        g_fa3_ok[fa3_cfg_idx(BN_, BMQ_, MINB_)] = (e_ == cudaSuccess) ? 1 : 0;                  \
        if (e_ != cudaSuccess)                                                                  \
            fprintf(stderr,                                                                     \
                    "[tc_shim] FA3 BN=%d BMQ=%d MINB=%d DECLINED: %d B of dynamic shared "      \
                    "memory is not grantable here (%s) — that shape keeps FA2.\n",              \
                    (BN_), (BMQ_), (MINB_), sm_, cudaGetErrorString(e_));                       \
    } while (0)
    FA3_ATTR(32, 16, 1, (_fa3_causal_kernel<32, 16, FA3_G, 1>));
    FA3_ATTR(32, 16, 2, (_fa3_causal_kernel<32, 16, FA3_G, 2>));
    FA3_ATTR(64, 16, 1, (_fa3_causal_kernel<64, 16, FA3_G, 1>));
    FA3_ATTR(64, 16, 2, (_fa3_causal_kernel<64, 16, FA3_G, 2>));
    FA3_ATTR(32, 32, 1, (_fa3_causal_kernel<32, 32, FA3_G, 1>));
    FA3_ATTR(64, 32, 1, (_fa3_causal_kernel<64, 32, FA3_G, 1>));
#undef FA3_ATTR
    g_fa3_attr_done = 1;
    return 0;
}

// bn: 32/64 key columns per online-softmax block. bmq: query rows per CTA per head (16/32).
// minb: CTAs per SM to ask ptxas to keep register-legal for (1 or 2).
// Returns -301 unsupported head_dim, -304 non-integral GQA, -305 shared memory not grantable,
// -312 this (g, bn, bmq, minb) is not instantiated, -313 too few CTAs to fill the device,
// -314 the on-device A-fragment probe disagreed, else the cudaError_t. Enqueues on the shim
// stream, does NOT sync.
extern "C" int64_t tc_shim_fa3_causal_async(const void* q_f32, const void* k16, const void* v16,
                                            void* o_f32, const void* scale_f32, int64_t m,
                                            int64_t n_keys, int64_t h_q, int64_t h_kv, int64_t d,
                                            int64_t pos_base, int64_t bn, int64_t bmq,
                                            int64_t minb) {
    if (d != FA3_D) return -301;
    if (m <= 0 || n_keys <= 0 || h_kv <= 0 || h_q <= 0) return 0;
    if ((h_q % h_kv) != 0) return -304;
    if ((h_q / h_kv) != FA3_G) return -312;       // only g==7 is instantiated
    if (bmq != 16 && bmq != 32) return -312;
    const int idx = fa3_cfg_idx(bn, bmq, minb);
    if (idx < 0) return -312;
    int64_t r = tc_shim_fa3_layout_probe();
    if (r != 0) return r;
    r = fa3_set_attrs();
    if (r != 0) return r;
    if (!g_fa3_ok[idx]) return -305;
    // A packed CTA is g times bigger than an FA2 CTA, so a short prefill can end up with fewer
    // CTAs than there are SMs and leave the machine idle. Decline and let the caller keep FA2
    // rather than quietly regressing pp256.
    {
        int nsm = 0;
        cudaDeviceGetAttribute(&nsm, cudaDevAttrMultiProcessorCount, 0);
        if (nsm > 0) {
            const int64_t ctas = ((m + bmq - 1) / bmq) * h_kv;
            if (ctas < (int64_t)nsm) return -313;
        }
    }
    dim3 grid((unsigned)((m + bmq - 1) / bmq), (unsigned)h_kv);
    dim3 block((unsigned)((bmq == 32 ? 2 : 1) * FA3_G * 32));
    int im = (int)m, ink = (int)n_keys, ihq = (int)h_q, ihkv = (int)h_kv, id = (int)d;
    int ipos = (int)pos_base;
    const float* q = (const float*)q_f32;
    const __half* k = (const __half*)k16;
    const __half* v = (const __half*)v16;
    const float* sp = (const float*)scale_f32;
    float* o = (float*)o_f32;
    const size_t smb = (size_t)fa3_smem_bytes(bn);
#define FA3_LAUNCH(BN_, BMQ_, MINB_)                                                            \
    _fa3_causal_kernel<BN_, BMQ_, FA3_G, MINB_>                                                 \
        <<<grid, block, smb, g_stream>>>(q, k, v, o, sp, im, ink, ihq, ihkv, id, ipos)
    switch (idx) {
        case 0: FA3_LAUNCH(32, 16, 1); break;
        case 1: FA3_LAUNCH(32, 16, 2); break;
        case 2: FA3_LAUNCH(64, 16, 1); break;
        case 3: FA3_LAUNCH(64, 16, 2); break;
        case 4: FA3_LAUNCH(32, 32, 1); break;
        case 5: FA3_LAUNCH(64, 32, 1); break;
        default: return -312;
    }
#undef FA3_LAUNCH
    cudaError_t e = cudaGetLastError();
    if (e != cudaSuccess)
        fprintf(stderr,
                "[tc_shim] FA3 LAUNCH FAILED: %s | bn=%lld bmq=%lld minb=%lld smem=%zu B "
                "grid=%ux%u block=%u m=%lld n_keys=%lld h_q=%lld h_kv=%lld d=%lld pos=%lld\n",
                cudaGetErrorString(e), (long long)bn, (long long)bmq, (long long)minb, smb,
                grid.x, grid.y, block.x, (long long)m, (long long)n_keys, (long long)h_q,
                (long long)h_kv, (long long)d, (long long)pos_base);
    record_error((int64_t)e);
    return (int64_t)e;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// FAST-EXP SwiGLU EPILOGUE (FRONT 3 lever 2) — `-D ALGENTA_7B_PF_FASTEXP`
//
// The A100 decomposition puts the f16 SwiGLU epilogue at 170.3 us/layer (pp1024) against
// TensorRT-LLM's `silu_and_mul_kernel` at 82.1 us/call. Its floor is pure traffic — 77.6 MB of
// f16 gate/up read + 38.8 MB of f16 A written per layer at m=1024 = 75 us at 1555 GB/s — so
// ~95 us/layer of the 170 is the activation itself: the Mojo epilogue evaluates one scalar
// `exp` per output at ~171 lane-cycles each, and indexes with a runtime `i / n_ff` division.
// This is the same combine with (a) `__expf` = the single-instruction ex2.approx.ftz path and
// (b) a division-free 2-D grid plus 16-byte vector loads/stores. Expression and operand
// dtypes are the epilogue's verbatim (`(g / (1 + exp(-g))) * u` over f16 operands widened to
// f32, one f32->f16 rounding at the store), so the only numeric change is exp's ~2 ulp.
// Requires n_ff % 8 == 0 and 16-byte-aligned operands (the session's f16 scratch satisfies
// both); anything else returns -302 and the caller keeps the Mojo epilogue.
// ═══════════════════════════════════════════════════════════════════════════════════════════

__global__ void _swiglu_f16_fastexp_kernel(const __half* __restrict__ gu,
                                           __half* __restrict__ act, int n_ff, int n_ff8) {
    int j8 = blockIdx.x * blockDim.x + threadIdx.x;
    if (j8 >= n_ff8) return;
    int row = blockIdx.y;
    const size_t gbase = (size_t)row * (2 * n_ff);
    uint4 gv = *reinterpret_cast<const uint4*>(gu + gbase + j8 * 8);
    uint4 uv = *reinterpret_cast<const uint4*>(gu + gbase + n_ff + j8 * 8);
    const __half2* g2 = reinterpret_cast<const __half2*>(&gv);
    const __half2* u2 = reinterpret_cast<const __half2*>(&uv);
    uint4 ov;
    __half2* o2 = reinterpret_cast<__half2*>(&ov);
#pragma unroll
    for (int i = 0; i < 4; i++) {
        float2 gf = __half22float2(g2[i]);
        float2 uf = __half22float2(u2[i]);
        float a0 = (gf.x / (1.0f + __expf(-gf.x))) * uf.x;
        float a1 = (gf.y / (1.0f + __expf(-gf.y))) * uf.y;
        o2[i] = __floats2half2_rn(a0, a1);
    }
    *reinterpret_cast<uint4*>(act + (size_t)row * n_ff + j8 * 8) = ov;
}

extern "C" int64_t tc_shim_swiglu_f16_fastexp_async(const void* gu16, void* act16,
                                                    int64_t m_rows, int64_t n_ff) {
    if (m_rows <= 0 || n_ff <= 0) return 0;
    if ((n_ff & 7) != 0) return -302;
    int n_ff8 = (int)(n_ff / 8);
    int threads = 256;
    dim3 grid((unsigned)((n_ff8 + threads - 1) / threads), (unsigned)m_rows);
    if (grid.y > 65535u) return -303;
    _swiglu_f16_fastexp_kernel<<<grid, threads, 0, g_stream>>>(
        (const __half*)gu16, (__half*)act16, (int)n_ff, n_ff8);
    cudaError_t e = cudaGetLastError();
    record_error((int64_t)e);
    return (int64_t)e;
}

#else   // TC_SHIM_NO_WMMA
extern "C" int64_t tc_shim_fa_layout_probe(void) { return -310; }
extern "C" int64_t tc_shim_fa_causal_async(const void*, const void*, const void*, void*,
                                           const void*, int64_t, int64_t, int64_t, int64_t,
                                           int64_t, int64_t, int64_t) { return -301; }
extern "C" int64_t tc_shim_fa2_layout_probe(void) { return -311; }
extern "C" int64_t tc_shim_fa2_causal_async(const void*, const void*, const void*, void*,
                                            const void*, int64_t, int64_t, int64_t, int64_t,
                                            int64_t, int64_t, int64_t, int64_t) { return -301; }
extern "C" int64_t tc_shim_fa3_layout_probe(void) { return -314; }
extern "C" int64_t tc_shim_fa3_causal_async(const void*, const void*, const void*, void*,
                                            const void*, int64_t, int64_t, int64_t, int64_t,
                                            int64_t, int64_t, int64_t, int64_t,
                                            int64_t) { return -301; }
extern "C" int64_t tc_shim_swiglu_f16_fastexp_async(const void*, void*, int64_t, int64_t) {
    return -302;
}
#endif  // TC_SHIM_NO_WMMA

// ═══════════════════════════════════════════════════════════════════════════════════════
// FRONT 6 LEVER 2 (2026-09-16) — cublasLt with a per-shape algorithm chosen ONCE, at stage
// time, instead of cublasGemmEx's CUBLAS_GEMM_DEFAULT heuristic re-queried on every call.
//
// WHY. `tc_shim_init` calls cublasCreate + cublasSetStream + cublasSetMathMode and NEVER
// cublasSetWorkspace, and every integration entry below dispatches through cublasGemmEx with
// CUBLAS_GEMM_DEFAULT. gemm_probe (this directory) prices what that leaves on the table at the
// Qwen2.5-7B projection shapes, on this exact device with clocks pinned at 1410 MHz, median of
// 15, best of the top-16 cublasLt heuristics against the shipped GemmEx call:
//
//   m=1024 (FRONT 5's four-chunk RAG walk)      shipped us   lt best us    delta
//     qkv      N=4608  K=3584                      147.46       145.41     -1.4%
//     o_proj   N=3584  K=3584                      139.26       131.07     -5.9%
//     gate_up  N=37888 K=3584                      997.38       967.68     -3.0%
//     down     N=3584  K=18944                     653.31       647.17     -0.9%
//   m=4096 (one pass, ALGENTA_PF_PASS4096)        shipped us   lt best us    delta
//     qkv                                          602.11       510.98    -15.1%
//     o_proj                                       526.34       425.98    -19.1%
//     gate_up                                     3920.90      3875.84     -1.2%
//     down                                        2277.38      1963.01    -13.8%
//
// Per layer that is -36.35 us at m=1024 (-4.07 ms over a RAG-4096 prefill's 112 layer-chunks)
// and -550.9 us at m=4096 (-15.43 ms over 28 layers) — the two levers COMPOUND, because the
// wider pass is what exposes the tail-wave headroom that a better algorithm can then take.
// At m=4096 all four roles pick the same descriptor (id=6, tile=20, stages=11; down adds
// splitK=2), which is the split-K reduction the default heuristic does not reach for without
// an explicit workspace.
//
// HONESTY REQUIREMENTS this design discharges:
//  * The whole block is behind ALGENTA_TC_SHIM_LT, so the shim object a baseline arm links is
//    BYTE-IDENTICAL to the one it linked before this lever existed. A shared object with the
//    code merely unreached would not be provable from `strings`, and this campaign has already
//    been burned once by a rebuild that silently dropped a flag (the gemma-3-27b H200 column).
//  * Tuning is a TIMED SEARCH, not heuristic result[0]. The heuristic's ranking is an estimate;
//    the probe's winners were not always index 0.
//  * A shape that was never tuned returns -320 and the caller DECLINES to the shipped GemmEx
//    entry, so an untuned m (any prompt whose first pass is not the tuned one) runs exactly the
//    code it ran before. There is no silent reinterpretation.
//  * NOT bit-identical: a different tile/split-K changes the reduction order, so the f32
//    accumulator rounds differently. Gate-decidable, like ALGENTA_7B_PF_F16MLP.
#ifdef ALGENTA_TC_SHIM_LT
#include <cublasLt.h>

namespace tc_lt {

struct Entry {
    int64_t M, N, K;
    int c16, accum;
    cublasLtMatmulDesc_t op;
    cublasLtMatrixLayout_t La, Lb, Lc;
    cublasLtMatmulAlgo_t algo;
    int tuned;
    int algo_id, tile, stages, splitk, nres;
    double best_ms;
};

static cublasLtHandle_t handle = nullptr;
static void* ws = nullptr;
static size_t ws_bytes = 0;
static Entry cache[12];
static int n_cache = 0;

// The layouts mirror the shipped GemmEx call exactly: row-major C[M,N] = A_rm[M,K] @
// W_rm[N,K]^T is expressed column-major as C[N,M] = op(W)^T x op(A) with W stored K x N
// (ld=K), A stored K x M (ld=K) and C stored N x M (ld=N).
static int make_desc(Entry& e) {
    if (cublasLtMatmulDescCreate(&e.op, CUBLAS_COMPUTE_32F, CUDA_R_32F) != CUBLAS_STATUS_SUCCESS)
        return -321;
    cublasOperation_t ta = CUBLAS_OP_T, tb = CUBLAS_OP_N;
    cublasLtMatmulDescSetAttribute(e.op, CUBLASLT_MATMUL_DESC_TRANSA, &ta, sizeof(ta));
    cublasLtMatmulDescSetAttribute(e.op, CUBLASLT_MATMUL_DESC_TRANSB, &tb, sizeof(tb));
    if (cublasLtMatrixLayoutCreate(&e.La, CUDA_R_16F, e.K, e.N, e.K) != CUBLAS_STATUS_SUCCESS)
        return -321;
    if (cublasLtMatrixLayoutCreate(&e.Lb, CUDA_R_16F, e.K, e.M, e.K) != CUBLAS_STATUS_SUCCESS)
        return -321;
    if (cublasLtMatrixLayoutCreate(&e.Lc, e.c16 ? CUDA_R_16F : CUDA_R_32F, e.N, e.M, e.N)
        != CUBLAS_STATUS_SUCCESS) return -321;
    return 0;
}

static Entry* find(int64_t M, int64_t N, int64_t K, int c16, int accum) {
    for (int i = 0; i < n_cache; i++) {
        Entry& e = cache[i];
        if (e.M == M && e.N == N && e.K == K && e.c16 == c16 && e.accum == accum && e.tuned)
            return &e;
    }
    return nullptr;
}

static int64_t matmul(Entry& e, const void* a16, const void* w16, void* c) {
    float alpha = 1.0f, beta = e.accum ? 1.0f : 0.0f;
    cublasStatus_t s = cublasLtMatmul(handle, e.op, &alpha, w16, e.La, a16, e.Lb, &beta,
                                      c, e.Lc, c, e.Lc, &e.algo, ws, ws_bytes, g_stream);
    if (s != CUBLAS_STATUS_SUCCESS) { record_error((int64_t)s); return -(int64_t)s; }
    if (g_noseam) return 0;   // the same NOSEAM seam the GemmEx entries honour
    cudaError_t ce = cudaStreamSynchronize(g_stream);
    record_error((int64_t)ce);
    return (int64_t)ce;
}

}  // namespace tc_lt

// Create the Lt handle and its workspace. Called once from the session's stage-time headroom
// try, so an allocation failure there demotes the whole TC plan rather than half-enabling this.
extern "C" int64_t tc_shim_lt_init(int64_t workspace_bytes) {
    if (tc_lt::handle != nullptr) return 0;
    if (cublasLtCreate(&tc_lt::handle) != CUBLAS_STATUS_SUCCESS) {
        tc_lt::handle = nullptr; record_error(-322); return -322;
    }
    tc_lt::ws_bytes = (size_t)(workspace_bytes > 0 ? workspace_bytes : (64ll << 20));
    cudaError_t e = cudaMalloc(&tc_lt::ws, tc_lt::ws_bytes);
    if (e != cudaSuccess) {
        record_error((int64_t)e);
        cublasLtDestroy(tc_lt::handle); tc_lt::handle = nullptr; tc_lt::ws = nullptr;
        return (int64_t)e;
    }
    cudaMemset(tc_lt::ws, 0, tc_lt::ws_bytes);
    return 0;
}

// Time the top-`top` heuristics for ONE shape and cache the winner. `c` is SCRATCH: tuning
// writes it (beta is honoured, so an accumulate role's scratch must be a buffer the caller is
// about to overwrite anyway). Returns the winning heuristic index, or negative.
extern "C" int64_t tc_shim_lt_tune(const void* a16, const void* w16, void* c,
                                   int64_t M, int64_t K, int64_t N,
                                   int64_t c16, int64_t accum, int64_t top, int64_t iters) {
    using namespace tc_lt;
    if (handle == nullptr) return -322;
    if (find(M, N, K, (int)c16, (int)accum) != nullptr) return 0;   // already tuned
    if (n_cache >= (int)(sizeof(cache) / sizeof(cache[0]))) return -323;
    Entry& e = cache[n_cache];
    e.M = M; e.N = N; e.K = K; e.c16 = (int)c16; e.accum = (int)accum;
    e.tuned = 0; e.best_ms = -1.0; e.algo_id = -1; e.tile = -1; e.stages = -1;
    e.splitk = -1; e.nres = 0;
    int64_t r = make_desc(e);
    if (r != 0) return r;

    cublasLtMatmulPreference_t pref = nullptr;
    if (cublasLtMatmulPreferenceCreate(&pref) != CUBLAS_STATUS_SUCCESS) return -321;
    cublasLtMatmulPreferenceSetAttribute(pref, CUBLASLT_MATMUL_PREF_MAX_WORKSPACE_BYTES,
                                         &ws_bytes, sizeof(ws_bytes));
    const int MAXRES = 32;
    int want = (int)(top > 0 && top < MAXRES ? top : MAXRES);
    cublasLtMatmulHeuristicResult_t res[MAXRES];
    int nres = 0;
    cublasStatus_t hs = cublasLtMatmulAlgoGetHeuristic(handle, e.op, e.La, e.Lb, e.Lc, e.Lc,
                                                       pref, want, res, &nres);
    cublasLtMatmulPreferenceDestroy(pref);
    e.nres = (hs == CUBLAS_STATUS_SUCCESS) ? nres : 0;
    if (e.nres <= 0) return -324;

    float alpha = 1.0f, beta = e.accum ? 1.0f : 0.0f;
    cudaEvent_t ev0, ev1;
    if (cudaEventCreate(&ev0) != cudaSuccess) return -325;
    cudaEventCreate(&ev1);
    int best = -1;
    const int warm = 3;
    const int meas = (int)(iters > 0 ? iters : 7);
    for (int i = 0; i < e.nres; i++) {
        // one untimed launch first: an algo that cannot execute must not be timed or chosen
        if (cublasLtMatmul(handle, e.op, &alpha, w16, e.La, a16, e.Lb, &beta, c, e.Lc, c, e.Lc,
                           &res[i].algo, ws, ws_bytes, g_stream) != CUBLAS_STATUS_SUCCESS) continue;
        if (cudaStreamSynchronize(g_stream) != cudaSuccess) continue;
        double acc = 0.0; int ok = 1;
        for (int it = 0; it < warm + meas; it++) {
            cudaEventRecord(ev0, g_stream);
            cublasStatus_t s = cublasLtMatmul(handle, e.op, &alpha, w16, e.La, a16, e.Lb, &beta,
                                              c, e.Lc, c, e.Lc, &res[i].algo, ws, ws_bytes,
                                              g_stream);
            cudaEventRecord(ev1, g_stream);
            if (cudaEventSynchronize(ev1) != cudaSuccess || s != CUBLAS_STATUS_SUCCESS) {
                ok = 0; break;
            }
            float ms = 0.0f;
            cudaEventElapsedTime(&ms, ev0, ev1);
            if (it >= warm) acc += ms;
        }
        if (!ok) continue;
        double mean = acc / meas;
        if (best < 0 || mean < e.best_ms) { e.best_ms = mean; best = i; e.algo = res[i].algo; }
    }
    cudaEventDestroy(ev0); cudaEventDestroy(ev1);
    if (best < 0) return -326;
    size_t sz = 0; int v = -1;
    cublasLtMatmulAlgoConfigGetAttribute(&e.algo, CUBLASLT_ALGO_CONFIG_ID, &v, sizeof(v), &sz);
    e.algo_id = v; v = -1;
    cublasLtMatmulAlgoConfigGetAttribute(&e.algo, CUBLASLT_ALGO_CONFIG_TILE_ID, &v, sizeof(v), &sz);
    e.tile = v; v = -1;
    cublasLtMatmulAlgoConfigGetAttribute(&e.algo, CUBLASLT_ALGO_CONFIG_STAGES_ID, &v, sizeof(v), &sz);
    e.stages = v; v = -1;
    cublasLtMatmulAlgoConfigGetAttribute(&e.algo, CUBLASLT_ALGO_CONFIG_SPLITK_NUM, &v, sizeof(v), &sz);
    e.splitk = v;
    e.tuned = 1;
    n_cache++;
    printf("TC LT: tuned M=%lld N=%lld K=%lld C=%s beta=%d -> algo id=%d tile=%d stages=%d "
           "splitK=%d (%.1f us, best of %d heuristics, ws %zu MB)\n",
           (long long)M, (long long)N, (long long)K, e.c16 ? "f16" : "f32", e.accum,
           e.algo_id, e.tile, e.stages, e.splitk, e.best_ms * 1000.0, e.nres, ws_bytes >> 20);
    return best;
}

// The f32-C dispatch on a tuned algorithm. -320 = this shape was never tuned, so the caller
// DECLINES to `tc_shim_gemm_f16_32c_pre` and runs the shipped GemmEx path unchanged.
extern "C" int64_t tc_shim_gemm_f16_32c_pre_lt(const void* a16, const void* w16,
                                               int64_t M, int64_t K, int64_t N,
                                               void* c_f32, int64_t accum) {
    tc_lt::Entry* e = tc_lt::find(M, N, K, 0, (int)accum);
    if (e == nullptr) return -320;
    return tc_lt::matmul(*e, a16, w16, c_f32);
}

// The f16-C twin (the gate/up role under ALGENTA_7B_PF_F16MLP).
extern "C" int64_t tc_shim_gemm_f16_16c_pre_lt(const void* a16, const void* w16,
                                               int64_t M, int64_t K, int64_t N,
                                               void* c_f16, int64_t accum) {
    tc_lt::Entry* e = tc_lt::find(M, N, K, 1, (int)accum);
    if (e == nullptr) return -320;
    return tc_lt::matmul(*e, a16, w16, c_f16);
}

extern "C" int64_t tc_shim_lt_count(void) { return (int64_t)tc_lt::n_cache; }

#endif  // ALGENTA_TC_SHIM_LT
// NOTE: there are deliberately NO stubs in the `#else`. The whole block above is inside
// `#ifdef ALGENTA_TC_SHIM_LT`, so a shim object built WITHOUT the macro is byte-identical to
// the one FRONT 5 shipped — which is what lets a baseline arm claim it carries no part of this
// lever provably, rather than merely unreachable. The Mojo side references these symbols only
// under `@parameter if PF_LTALGO_B1`, so a flag-off binary never asks for them; an arm that
// passes `-D ALGENTA_7B_PF_LTALGO` but links the stock object fails AT LINK TIME with an
// undefined symbol, which is the loud failure this campaign prefers over a silent runtime
// decline that would leave a cell measured on the wrong code path.

extern "C" int64_t tc_shim_shutdown(void) {
    if (g_handle != nullptr) { cublasDestroy(g_handle); g_handle = nullptr; }
    if (g_stream_created && g_stream != nullptr) { cudaStreamDestroy(g_stream); }
    g_stream = nullptr;
    g_stream_created = 0;
    return 0;
}

// ═══════════════════════════════════════════════════════════════════════════════════════════
// ANGLE 1 — RUNTIME PTX/CUBIN LOAD: zero link-time coupling between kernels and the Mojo
// binary. The driver API is dlopen'd (libcuda.so.1 is always present where an NVIDIA driver
// runs — it is Mojo's own dlopen dependency too), the PTX below is loaded with
// cuModuleLoadData (the driver's internal ptxas JITs it for the current GPU), and kernels
// launch via cuLaunchKernel on the CURRENT context — the same context the cuBLAS arm proves
// Mojo shares with us. Kernels live in tc_rt_kernels.cu (compiled with `nvcc -ptx` by
// scripts/build_tc_probe.sh and embedded here as g_tc_rt_ptx).
// ═══════════════════════════════════════════════════════════════════════════════════════════
#include "tc_rt_ptx.h"  // generated: static const unsigned char g_tc_rt_ptx[] (NUL-terminated)

static void* g_rt_mod = nullptr;      // CUmodule
static void* g_rt_vadd = nullptr;     // CUfunction tc_rt_vadd
static void* g_rt_mma = nullptr;      // CUfunction tc_rt_mma_gemm
static void* g_libcuda = nullptr;

typedef int (*cuModuleLoadData_t)(void**, const void*);
typedef int (*cuModuleGetFunction_t)(void**, void*, const char*);
typedef int (*cuLaunchKernel_t)(void*, unsigned, unsigned, unsigned, unsigned, unsigned,
                                unsigned, unsigned, void*, void**, void**);
typedef int (*cuPointerGetAttribute_t)(void*, int, unsigned long long);
static cuModuleLoadData_t p_cuModuleLoadData = nullptr;
static cuModuleGetFunction_t p_cuModuleGetFunction = nullptr;
static cuLaunchKernel_t p_cuLaunchKernel = nullptr;
static cuPointerGetAttribute_t p_cuPointerGetAttribute = nullptr;

static int64_t ensure_libcuda(void) {
    if (g_libcuda != nullptr) return 0;
    g_libcuda = dlopen("libcuda.so.1", RTLD_NOW | RTLD_NOLOAD);
    if (g_libcuda == nullptr) g_libcuda = dlopen("libcuda.so.1", RTLD_NOW);
    if (g_libcuda == nullptr) return -201;
    p_cuModuleLoadData = (cuModuleLoadData_t)dlsym(g_libcuda, "cuModuleLoadData");
    p_cuModuleGetFunction = (cuModuleGetFunction_t)dlsym(g_libcuda, "cuModuleGetFunction");
    p_cuLaunchKernel = (cuLaunchKernel_t)dlsym(g_libcuda, "cuLaunchKernel");
    p_cuPointerGetAttribute =
        (cuPointerGetAttribute_t)dlsym(g_libcuda, "cuPointerGetAttribute");
    if (p_cuModuleLoadData == nullptr || p_cuModuleGetFunction == nullptr ||
        p_cuLaunchKernel == nullptr) return -202;
    return 0;
}

// Load the embedded PTX on the CURRENT context (JIT happens inside cuModuleLoadData; first
// call pays the ptxas cost, ~100 ms class — a session-open cost, not a wave cost).
extern "C" int64_t tc_shim_rt_init(void) {
    if (g_rt_vadd != nullptr && g_rt_mma != nullptr) return 0;
    int64_t r = ensure_libcuda();
    if (r != 0) { record_error(r); return r; }
    int cr = p_cuModuleLoadData(&g_rt_mod, (const void*)g_tc_rt_ptx);
    if (cr != 0) { record_error(-(300 + cr)); return -(300 + cr); }
    cr = p_cuModuleGetFunction(&g_rt_vadd, g_rt_mod, "tc_rt_vadd");
    if (cr != 0) { record_error(-(320 + cr)); return -(320 + cr); }
    cr = p_cuModuleGetFunction(&g_rt_mma, g_rt_mod, "tc_rt_mma_gemm");
    if (cr != 0) { record_error(-(340 + cr)); return -(340 + cr); }
    return 0;
}

// Interop probe: launch the runtime-loaded vector add on Mojo-allocated pointers.
extern "C" int64_t tc_shim_rt_vadd(const void* a, const void* b, void* c, int64_t n) {
    if (g_rt_vadd == nullptr) { record_error(-210); return -210; }
    const void* args[4] = {&a, &b, &c, &n};
    unsigned blocks = (unsigned)((n + 255) / 256);
    int r = p_cuLaunchKernel(g_rt_vadd, blocks, 1, 1, 256, 1, 1, 0, (void*)g_stream,
                             (void**)args, nullptr);
    if (r != 0) { record_error(-(400 + r)); return -(400 + r); }
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// ANGLE 2 — the hand-written mma.sync GEMM, dispatched through the runtime-loaded module.
// C[M,N](f32) = A[M,K](f16) @ W[N,K](f16)^T; grid (ceil(N/32), ceil(M/64)), block 128.
extern "C" int64_t tc_shim_rt_mma_gemm(const void* a16, const void* w16, void* c32,
                                       int64_t M, int64_t K, int64_t N) {
    if (g_rt_mma == nullptr) { record_error(-220); return -220; }
    int m = (int)M, k = (int)K, n = (int)N;
    void* args[6] = {(void*)&a16, (void*)&w16, (void*)&c32, &m, &k, &n};
    unsigned gx = (unsigned)((n + 31) / 32);
    unsigned gy = (unsigned)((m + 63) / 64);
    int r = p_cuLaunchKernel(g_rt_mma, gx, gy, 1, 128, 1, 1, 0, (void*)g_stream, args,
                             nullptr);
    if (r != 0) { record_error(-(500 + r)); return -(500 + r); }
    cudaError_t e = cudaStreamSynchronize(g_stream);
    record_error((int64_t)e);
    return (int64_t)e;
}

// Interop diagnostic: which CUcontext OWNS a device pointer (CU_POINTER_ATTRIBUTE_CONTEXT=1).
// The probe compares this against tc_shim_diag's current-context value for a Mojo-allocated
// buffer — equality is the single-context proof at the pointer level (not just by GEMM
// correctness). Returns 0 on success; out_ctx holds the context address (0 if the attribute
// query is unsupported for that pointer class).
extern "C" int64_t tc_shim_ptr_context(const void* dev_ptr, int64_t* out_ctx) {
    int64_t r = ensure_libcuda();
    if (r != 0) { record_error(r); return r; }
    *out_ctx = 0;
    if (p_cuPointerGetAttribute == nullptr) return -230;
    void* c = nullptr;
    int cr = p_cuPointerGetAttribute(&c, 1, (unsigned long long)(uintptr_t)dev_ptr);
    *out_ctx = (int64_t)(uintptr_t)c;
    if (cr != 0) { record_error(-(600 + cr)); return -(600 + cr); }
    return 0;
}
