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
extern "C" int64_t tc_shim_swiglu_f16_fastexp_async(const void*, void*, int64_t, int64_t) {
    return -302;
}
#endif  // TC_SHIM_NO_WMMA

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
