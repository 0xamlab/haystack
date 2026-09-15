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
