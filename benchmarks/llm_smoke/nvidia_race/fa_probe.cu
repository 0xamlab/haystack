// fa_probe.cu — standalone correctness + timing harness for FRONT 3's two tc_shim levers:
//
//   * `tc_shim_fa_causal_async`           the fused causal FlashAttention-2 kernel (lever 1)
//   * `tc_shim_swiglu_f16_fastexp_async`  the __expf SwiGLU epilogue (lever 2)
//
// It exists so the kernel can be iterated in SECONDS (nvcc + one small binary) instead of the
// ~5-minute model-load cost of a full driver run, and so the numbers that gate the lever are
// produced against an in-process reference rather than a remembered one.
//
// WHAT IS CHECKED
//   1. the on-device WMMA accumulator-layout probe (tc_shim_fa_layout_probe) — a mismatch
//      disables the lever, it does not silently permute rows.
//   2. FA vs a naive f32 reference over the SAME f16-rounded Q/K/V operands, at every shape
//      the 7B lane dispatches: the one-pass pp256/pp1024 tiles and the four chunks of a
//      4096-token prefill (pos_base 0/1024/2048/3072), plus an odd (m%64, n%64 != 0) tail.
//      Reported: max abs, max rel and RMS error over a row subset, plus a >2%-rel count.
//   3. FA vs the shim's own 5-pass chain (strided-batched QK^T + masked softmax + PV) on the
//      same operands — the drop-in equivalence the session actually relies on.
//   4. SwiGLU fast-exp vs an accurate-`expf` reference on f16 operands: differing f16 bit
//      patterns out of m*n_ff, max abs / max rel.
//   5. timings (cudaEvent, median of N) for FA at BN 32/64/128 and for the 5-pass chain, so
//      the us/layer the A/B predicts is measured here first.
//
// Build (on the GPU VM, CUDA 12.6, next to an already-built tc_shim object):
//   nvcc -O3 -arch=sm_80 -Xcompiler -fPIC -I<tc_rt_ptx dir> -c tc_shim.cu -o /tmp/tc_shim_sm_80.o
//   nvcc -O3 -arch=sm_80 fa_probe.cu /tmp/tc_shim_sm_80.o -lcublas -lcudart -o /tmp/fa_probe
//   /tmp/fa_probe [--iters 30] [--bn 64] [--quick]
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cuda_fp16.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <algorithm>
#include <vector>

extern "C" int64_t tc_shim_init(void);
extern "C" int64_t tc_shim_noseam(int64_t);
extern "C" int64_t tc_shim_last_error(void);
extern "C" int64_t tc_shim_fa_layout_probe(void);
extern "C" int64_t tc_shim_fa_causal_async(const void*, const void*, const void*, void*,
                                           const void*, int64_t, int64_t, int64_t, int64_t,
                                           int64_t, int64_t, int64_t);
extern "C" int64_t tc_shim_bgemm_f16_async(const void*, const void*, void*, int64_t, int64_t,
                                           int64_t, int64_t, int64_t, int64_t, int64_t,
                                           int64_t, int64_t, int64_t, int64_t);
extern "C" int64_t tc_shim_attn_softmax_mask_async(const void*, void*, int64_t, int64_t,
                                                   int64_t, int64_t, int64_t);
extern "C" int64_t tc_shim_swiglu_f16_fastexp_async(const void*, void*, int64_t, int64_t);

#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { \
    printf("CUDA ERROR %s:%d %s\n", __FILE__, __LINE__, cudaGetErrorString(e_)); exit(1);} } while (0)

// ── deterministic fill: reproducible scratch, no /dev/urandom, no host RNG dependency ─────
static void fill_rand(float* p, long n, unsigned seed, float lo, float hi) {
    unsigned s = seed;
    for (long i = 0; i < n; i++) {
        s = s * 1664525u + 1013904223u;
        float u = (float)((double)(s >> 8) / 16777216.0);
        p[i] = lo + u * (hi - lo);
    }
}

// ── HOST reference attention: double precision, no GPU code, no layout guesswork. Computes
//    the exact (non-online) causal softmax over the SAME f16-rounded operands the kernel and
//    the 5-pass chain see — Q pre-scaled and rounded to f16 exactly where the kernel rounds
//    it, P rounded to f16 exactly where both round it — and writes only the sampled
//    (row, head, dim) cells, so `o` is sparse and the comparison must use the same stride.
//    This replaced a GPU reference whose own Q layout was wrong: when a kernel and its
//    reference disagree, the reference is the thing that has to be beyond doubt first. ──────
static void host_ref_attn(const float* q, const __half* k, const __half* v, float* o,
                          const int* rows, int n_check, int m, int n_keys, int h_q, int h_kv,
                          int d, int pos_base, float scale, int dim_stride) {
    std::vector<double> s((size_t)n_keys);
    for (int ci = 0; ci < n_check; ci++) {
        int r = rows[ci];
        if (r >= m) continue;
        int qpos = pos_base + r;
        int hi = qpos < n_keys - 1 ? qpos : n_keys - 1;
        const float* qr_base = q + (size_t)r * h_q * d;
        for (int h = 0; h < h_q; h++) {
            int hk = h / (h_q / h_kv);
            const float* qr = qr_base + (size_t)h * d;
            double mx = -1e300;
            for (int j = 0; j <= hi; j++) {
                const __half* kr = k + ((size_t)j * h_kv + hk) * d;
                double acc = 0;
                for (int t = 0; t < d; t++)
                    acc += (double)__half2float(__float2half(qr[t] * scale)) *
                           (double)__half2float(kr[t]);
                s[j] = acc;
                if (acc > mx) mx = acc;
            }
            double sum = 0;
            for (int j = 0; j <= hi; j++) { s[j] = exp(s[j] - mx); sum += s[j]; }
            double inv = (sum > 0) ? 1.0 / sum : 0.0;
            for (int e = 0; e < d; e += dim_stride) {
                double acc = 0;
                for (int j = 0; j <= hi; j++) {
                    double p = (double)__half2float(__float2half((float)(s[j] * inv)));
                    acc += p * (double)__half2float(v[((size_t)j * h_kv + hk) * d + e]);
                }
                o[(size_t)r * h_q * d + (size_t)h * d + e] = (float)acc;
            }
        }
    }
}

// ── reference SwiGLU: the accurate-expf twin of the shim's __expf kernel ──────────────────
__global__ void ref_swiglu_kernel(const __half* gu, __half* act, long total, int n_ff) {
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= total) return;
    long row = i / n_ff;
    int j = (int)(i - row * n_ff);
    float g = __half2float(gu[row * 2 * n_ff + j]);
    float u = __half2float(gu[row * 2 * n_ff + n_ff + j]);
    act[i] = __float2half((g / (1.0f + expf(-g))) * u);
}

struct Stat { double max_abs, max_rel, rms; long n, nbad; };

static Stat compare_subset(const float* got, const float* want, const int* rows, int n_check,
                           int m, int h_q, int d) {
    Stat s = {0, 0, 0, 0, 0};
    double sq = 0;
    for (int ci = 0; ci < n_check; ci++) {
        long base = (long)rows[ci] * h_q * d;
        for (long i = base; i < base + (long)h_q * d; i++) {
            double a = fabs((double)got[i] - (double)want[i]);
            double w = fabs((double)want[i]);
            double rel = (w > 1e-6) ? a / w : (a > 1e-6 ? 1e9 : 0);
            if (a > s.max_abs) s.max_abs = a;
            if (rel > s.max_rel) s.max_rel = rel;
            sq += a * a;
            s.n++;
            if (rel > 2e-2 && a > 1e-3) s.nbad++;
        }
    }
    (void)m;
    s.rms = s.n ? sqrt(sq / (double)s.n) : 0;
    return s;
}

static Stat compare_all(const float* got, const float* want, long n) {
    Stat s = {0, 0, 0, n, 0};
    double sq = 0;
    for (long i = 0; i < n; i++) {
        double a = fabs((double)got[i] - (double)want[i]);
        double w = fabs((double)want[i]);
        double rel = (w > 1e-6) ? a / w : (a > 1e-6 ? 1e9 : 0);
        if (a > s.max_abs) s.max_abs = a;
        if (rel > s.max_rel) s.max_rel = rel;
        sq += a * a;
        if (rel > 2e-2 && a > 1e-3) s.nbad++;
    }
    s.rms = sqrt(sq / (double)n);
    return s;
}

static double bench(void (*fn)(void*), void* arg, int iters) {
    cudaEvent_t a, b;
    CK(cudaEventCreate(&a)); CK(cudaEventCreate(&b));
    std::vector<double> ts;
    for (int i = 0; i < iters + 3; i++) {
        CK(cudaEventRecord(a));
        fn(arg);
        CK(cudaEventRecord(b));
        CK(cudaEventSynchronize(b));
        float ms = 0; CK(cudaEventElapsedTime(&ms, a, b));
        if (i >= 3) ts.push_back(ms);
    }
    std::sort(ts.begin(), ts.end());
    double med = ts[ts.size() / 2];
    double iqr = ts[(3 * ts.size()) / 4] - ts[ts.size() / 4];
    cudaEventDestroy(a); cudaEventDestroy(b);
    printf("      [median %.4f ms  IQR %.4f ms  rel-IQR %.2f%%  n=%zu]\n", med, iqr,
           med > 0 ? 100.0 * iqr / med : 0.0, ts.size());
    return med;
}

struct FaArgs { const float* q; const __half* k; const __half* v; float* o;
                const float* scale;
                int m, n_keys, h_q, h_kv, d, pos; int bn; };
static void run_fa(void* p) {
    FaArgs* a = (FaArgs*)p;
    tc_shim_fa_causal_async(a->q, a->k, a->v, a->o, a->scale, a->m, a->n_keys, a->h_q,
                            a->h_kv, a->d, a->pos, a->bn);
}

struct ChainArgs { const __half* q16; const __half* k16; const __half* v16; float* s32;
                   __half* p16; float* o32; int m, n_keys, h_q, h_kv, d, pos; };
static void run_chain(void* p) {
    ChainArgs* a = (ChainArgs*)p;
    int g = a->h_q / a->h_kv;
    int gm = g * a->m;
    tc_shim_bgemm_f16_async(a->q16, a->k16, a->s32, gm, a->n_keys, a->d,
                            a->d, a->h_kv * a->d, a->n_keys,
                            (long)gm * a->d, a->d, (long)gm * a->n_keys, a->h_kv, 1);
    tc_shim_attn_softmax_mask_async(a->s32, a->p16, a->n_keys, a->m, a->h_q, a->pos, 0);
    tc_shim_bgemm_f16_async(a->p16, a->v16, a->o32, gm, a->d, a->n_keys,
                            a->n_keys, a->h_kv * a->d, a->d,
                            (long)gm * a->n_keys, a->d, (long)gm * a->d, a->h_kv, 0);
}

struct SwArgs { const __half* gu; __half* act; int m, n_ff; };
static void run_sw(void* p) {
    SwArgs* a = (SwArgs*)p;
    tc_shim_swiglu_f16_fastexp_async(a->gu, a->act, a->m, a->n_ff);
}
static void run_sw_ref(void* p) {
    SwArgs* a = (SwArgs*)p;
    long total = (long)a->m * a->n_ff;
    ref_swiglu_kernel<<<(unsigned)((total + 255) / 256), 256>>>(a->gu, a->act, total, a->n_ff);
}

int main(int argc, char** argv) {
    int iters = 30, h_q = 28, h_kv = 4, d = 128, bn_arg = 0, quick = 0, no_time = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--iters")) iters = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--h-q")) h_q = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--h-kv")) h_kv = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--bn")) bn_arg = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--quick")) quick = 1;
        else if (!strcmp(argv[i], "--no-time")) no_time = 1;
    }
    const float scale = 1.0f / sqrtf((float)d);
    cudaDeviceProp prop;
    CK(cudaGetDeviceProperties(&prop, 0));
    printf("fa_probe: %s sm_%d%d SMs=%d shared/SM=%zu KB shared/block-optin=%zu KB\n",
           prop.name, prop.major, prop.minor, prop.multiProcessorCount,
           prop.sharedMemPerMultiprocessor / 1024, prop.sharedMemPerBlockOptin / 1024);
    printf("shape: h_q=%d h_kv=%d d=%d g=%d scale=%.6f\n", h_q, h_kv, d, h_q / h_kv, scale);

    int64_t r = tc_shim_init();
    if (r != 0) { printf("tc_shim_init FAILED %lld\n", (long long)r); return 1; }
    tc_shim_noseam(1);            // the session's NOSEAM contract: legacy stream, no syncs
    r = tc_shim_fa_layout_probe();
    printf("layout probe: %lld (%s)\n", (long long)r,
           r == 0 ? "OK — the WMMA accumulator mapping the kernel indexes by is verified"
                  : "MISMATCH — lever must stay OFF");
    if (r != 0) return 2;

    const int MAXN = 4096, MAXM = 1024;
    long nq = (long)MAXM * h_q * d, nk = (long)MAXN * h_kv * d;
    long ns = (long)h_q * MAXM * MAXN, no = (long)MAXM * h_q * d;
    float *hq = nullptr, *ho = nullptr, *href = nullptr, *ho32 = nullptr;
    __half *hk16 = nullptr, *hv16 = nullptr, *hqhm = nullptr;
    float *dq = nullptr, *do_ = nullptr, *dref = nullptr, *ds32 = nullptr, *do32 = nullptr;
    __half *dk16 = nullptr, *dv16 = nullptr, *dp16 = nullptr, *dq16 = nullptr;
    int* drows = nullptr;
    CK(cudaMallocHost(&hq, nq * 4)); CK(cudaMallocHost(&ho, no * 4));
    CK(cudaMallocHost(&href, no * 4)); CK(cudaMallocHost(&ho32, no * 4));
    CK(cudaMallocHost(&hk16, nk * 2)); CK(cudaMallocHost(&hv16, nk * 2));
    CK(cudaMallocHost(&hqhm, nq * 2));
    CK(cudaMalloc(&dq, nq * 4)); CK(cudaMalloc(&do_, no * 4)); CK(cudaMalloc(&dref, no * 4));
    CK(cudaMalloc(&ds32, ns * 4)); CK(cudaMalloc(&do32, no * 4));
    CK(cudaMalloc(&dk16, nk * 2)); CK(cudaMalloc(&dv16, nk * 2));
    CK(cudaMalloc(&dp16, ns * 2)); CK(cudaMalloc(&dq16, nq * 2));
    CK(cudaMalloc(&drows, 64 * 4));
    float* dscale = nullptr;
    CK(cudaMalloc(&dscale, 4));
    CK(cudaMemcpy(dscale, &scale, 4, cudaMemcpyHostToDevice));

    // the row subset the reference verifies: the causal-diagonal-sensitive rows (0, 1, 63,
    // 64, 65), the tile boundaries, and the last valid row of the tile.
    int rowset[16] = {0, 1, 2, 63, 64, 65, 127, 128, 255, 256, 511, 512, 700, 1000, 1022,
                      1023};
    struct Case { int m, n_keys, pos; const char* name; };
    std::vector<Case> cases = {
        {256, 256, 0, "pp256"},
        {1024, 1024, 0, "pp1024"},
        {1024, 2048, 1024, "rag4096 chunk1"},
        {1024, 3072, 2048, "rag4096 chunk2"},
        {1024, 4096, 3072, "rag4096 chunk3"},
        {660, 1716, 1056, "odd tail m%64,n%64!=0"},
    };
    if (quick) { cases.resize(3); }

    int fail = 0;
    printf("\n== FA correctness vs the f32 reference (same f16 operands, f16-rounded P) ==\n");
    printf("%-26s %4s %10s %10s %10s %9s\n", "case", "bn", "max_abs", "max_rel", "rms",
           "n>2%rel");
    for (size_t ci = 0; ci < cases.size(); ci++) {
        Case c = cases[ci];
        int n_check = 0;
        int chk[16];
        for (int i = 0; i < 16; i++) if (rowset[i] < c.m) chk[n_check++] = rowset[i];
        fill_rand(hq, (long)c.m * h_q * d, 1234u + (unsigned)ci, -2.0f, 2.0f);
        long kn = (long)c.n_keys * h_kv * d;
        std::vector<float> tmp(kn);
        fill_rand(tmp.data(), kn, 999u + (unsigned)ci, -2.0f, 2.0f);
        for (long i = 0; i < kn; i++) hk16[i] = __float2half(tmp[i]);
        fill_rand(tmp.data(), kn, 5555u + (unsigned)ci, -2.0f, 2.0f);
        for (long i = 0; i < kn; i++) hv16[i] = __float2half(tmp[i]);
        // pre-scaled f16 Q in BOTH layouts: position-major is what the kernel derives from
        // f32 itself; head-major is what the reference and the 5-pass chain consume.
        for (int rr = 0; rr < c.m; rr++)
            for (int hh = 0; hh < h_q; hh++)
                for (int ee = 0; ee < d; ee++) {
                    __half val = __float2half(hq[((size_t)rr * h_q + hh) * d + ee] * scale);
                    hqhm[((size_t)hh * c.m + rr) * d + ee] = val;
                }
        CK(cudaMemcpy(dq, hq, (long)c.m * h_q * d * 4, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(dk16, hk16, (long)c.n_keys * h_kv * d * 2, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(dv16, hv16, (long)c.n_keys * h_kv * d * 2, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(dq16, hqhm, (long)h_q * c.m * d * 2, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(drows, chk, n_check * 4, cudaMemcpyHostToDevice));

        // HOST reference (double precision) over a dim sample of every checked row/head —
        // computed once per case, it does not depend on BN.
        const int DIMS = 8;
        memset(href, 0, no * 4);
        host_ref_attn(hq, hk16, hv16, href, chk, n_check, c.m, c.n_keys, h_q, h_kv, d,
                      c.pos, scale, d / DIMS);
        long ncmp = 0;
        for (int ci2 = 0; ci2 < n_check; ci2++) ncmp += (long)h_q * DIMS;

        int bns[3] = {32, 64, 128};
        for (int bi = 0; bi < 3; bi++) {
            int bn = bns[bi];
            if (bn_arg && bn != bn_arg) continue;
            CK(cudaMemset(do_, 0, no * 4));
            int64_t rc = tc_shim_fa_causal_async(dq, dk16, dv16, do_, dscale, c.m, c.n_keys,
                                                 h_q, h_kv, d, c.pos, bn);
            if (rc != 0) {
                printf("%-26s %4d  LAUNCH rc=%lld (last_error=%lld)\n", c.name, bn,
                       (long long)rc, (long long)tc_shim_last_error());
                fail = 1; continue;
            }
            CK(cudaDeviceSynchronize());
            CK(cudaMemcpy(ho, do_, no * 4, cudaMemcpyDeviceToHost));
            double mabs = 0, mrel = 0, sq = 0; long nbad = 0;
            for (int ci2 = 0; ci2 < n_check; ci2++) {
                int rr = chk[ci2];
                for (int hh = 0; hh < h_q; hh++)
                    for (int ee = 0; ee < d; ee += d / DIMS) {
                        size_t ix = (size_t)rr * h_q * d + (size_t)hh * d + ee;
                        double a = fabs((double)ho[ix] - (double)href[ix]);
                        double w = fabs((double)href[ix]);
                        double rl = (w > 1e-6) ? a / w : (a > 1e-6 ? 1e9 : 0);
                        if (a > mabs) mabs = a;
                        if (rl > mrel) mrel = rl;
                        sq += a * a;
                        if (rl > 2e-2 && a > 1e-3) nbad++;
                    }
            }
            printf("%-26s %4d %10.3e %10.3e %10.3e %9ld %s\n", c.name, bn, mabs, mrel,
                   sqrt(sq / (double)ncmp), nbad, nbad ? "<-- CHECK" : "");
            if (nbad) fail = 1;
        }
    }

    // ── drop-in equivalence against the shim's own 5-pass chain, EVERY row ──
    printf("\n== FA vs the 5-pass chain (QK^T + masked softmax + PV), m=n=1024 pos=0, "
           "ALL %d rows ==\n", 1024);
    {
        int m = 1024, n = 1024, pos = 0;
        fill_rand(hq, (long)m * h_q * d, 4242u, -2.0f, 2.0f);
        std::vector<float> tmp((long)n * h_kv * d);
        fill_rand(tmp.data(), tmp.size(), 77u, -2.0f, 2.0f);
        for (size_t i = 0; i < tmp.size(); i++) hk16[i] = __float2half(tmp[i]);
        fill_rand(tmp.data(), tmp.size(), 78u, -2.0f, 2.0f);
        for (size_t i = 0; i < tmp.size(); i++) hv16[i] = __float2half(tmp[i]);
        for (int rr = 0; rr < m; rr++)
            for (int hh = 0; hh < h_q; hh++)
                for (int ee = 0; ee < d; ee++)
                    hqhm[((size_t)hh * m + rr) * d + ee] =
                        __float2half(hq[((size_t)rr * h_q + hh) * d + ee] * scale);
        CK(cudaMemcpy(dq, hq, (long)m * h_q * d * 4, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(dk16, hk16, (long)n * h_kv * d * 2, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(dv16, hv16, (long)n * h_kv * d * 2, cudaMemcpyHostToDevice));
        CK(cudaMemcpy(dq16, hqhm, (long)h_q * m * d * 2, cudaMemcpyHostToDevice));

        CK(cudaMemset(do32, 0, no * 4));
        ChainArgs ca = {dq16, dk16, dv16, ds32, dp16, do32, m, n, h_q, h_kv, d, pos};
        run_chain(&ca);
        CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(ho32, do32, no * 4, cudaMemcpyDeviceToHost));
        int bns[3] = {32, 64, 128};
        for (int bi = 0; bi < 3; bi++) {
            int bn = bns[bi];
            if (bn_arg && bn != bn_arg) continue;
            CK(cudaMemset(do_, 0, no * 4));
            int64_t rc = tc_shim_fa_causal_async(dq, dk16, dv16, do_, dscale, m, n, h_q,
                                                 h_kv, d, pos, bn);
            if (rc != 0) { printf("  bn=%3d LAUNCH rc=%lld\n", bn, (long long)rc); fail = 1;
                           continue; }
            CK(cudaDeviceSynchronize());
            CK(cudaMemcpy(ho, do_, no * 4, cudaMemcpyDeviceToHost));
            // ho32 is head-major [h_q, m, d]; ho is position-major [m, h_q*d]. EVERY row and
            // every dim — the chain is what ships today, so this is the drop-in proof.
            double mabs = 0, mrel = 0, sq = 0; long nn = 0, nbad = 0;
            for (int rr = 0; rr < m; rr++) {
                for (int hh = 0; hh < h_q; hh++)
                    for (int ee = 0; ee < d; ee++) {
                        double g = ho[((size_t)rr * h_q + hh) * d + ee];
                        double w = ho32[((size_t)hh * m + rr) * d + ee];
                        double a = fabs(g - w);
                        double rl = fabs(w) > 1e-6 ? a / fabs(w) : (a > 1e-6 ? 1e9 : 0);
                        if (a > mabs) mabs = a;
                        if (rl > mrel) mrel = rl;
                        sq += a * a; nn++;
                        if (rl > 2e-2 && a > 1e-3) nbad++;
                    }
            }
            printf("  bn=%3d  max_abs=%.3e max_rel=%.3e rms=%.3e n>2%%rel=%ld (of %ld) %s\n",
                   bn, mabs, mrel, sqrt(sq / (double)nn), nbad, nn, nbad ? "<-- CHECK" : "");
            if (nbad) fail = 1;
        }
    }

    // ── timings ──
    if (!no_time) {
        printf("\n== timings: median of %d calls, ms per call ==\n", iters);
        for (size_t ci = 0; ci < cases.size(); ci++) {
            Case c = cases[ci];
            printf("  -- %s (m=%d n_keys=%d pos=%d)\n", c.name, c.m, c.n_keys, c.pos);
            FaArgs fa = {dq, dk16, dv16, do_, dscale, c.m, c.n_keys, h_q, h_kv, d, c.pos,
                         64};
            ChainArgs ca = {dq16, dk16, dv16, ds32, dp16, do32, c.m, c.n_keys, h_q, h_kv, d,
                            c.pos};
            int bns[3] = {32, 64, 128};
            for (int bi = 0; bi < 3; bi++) {
                int bn = bns[bi];
                if (bn_arg && bn != bn_arg) continue;
                fa.bn = bn;
                printf("    FA bn=%-4d", bn);
                double t = bench(run_fa, &fa, iters);
                printf("        -> %.1f us/layer, %.3f ms over 28 layers\n", t * 1000.0,
                       t * 28.0);
            }
            printf("    5-pass chain");
            double tc5 = bench(run_chain, &ca, iters);
            printf("        -> %.1f us (GEMMs+softmax only; pack/unpack/convert extra)\n",
                   tc5 * 1000.0);
        }
    }

    // ── SwiGLU ──
    {
        const int n_ff = 18944, mrows = 1024;
        long ngu = (long)mrows * 2 * n_ff, nact = (long)mrows * n_ff;
        __half *dgu = nullptr, *dact = nullptr, *dref2 = nullptr;
        CK(cudaMalloc(&dgu, ngu * 2)); CK(cudaMalloc(&dact, nact * 2));
        CK(cudaMalloc(&dref2, nact * 2));
        std::vector<__half> gu16(ngu);
        {   // fill in slices so the host peak stays ~one f32 temp buffer
            const long SL = 1 << 20;
            std::vector<float> t(SL);
            for (long off = 0; off < ngu; off += SL) {
                long cnt = std::min(SL, ngu - off);
                fill_rand(t.data(), cnt, 31337u + (unsigned)off, -8.0f, 8.0f);
                for (long i = 0; i < cnt; i++) gu16[off + i] = __float2half(t[i]);
            }
        }
        CK(cudaMemcpy(dgu, gu16.data(), ngu * 2, cudaMemcpyHostToDevice));
        SwArgs sa = {dgu, dref2, mrows, n_ff};
        run_sw_ref(&sa);
        CK(cudaGetLastError());
        CK(cudaDeviceSynchronize());
        sa.act = dact;
        int64_t rc = tc_shim_swiglu_f16_fastexp_async(dgu, dact, mrows, n_ff);
        CK(cudaGetLastError());
        CK(cudaDeviceSynchronize());
        printf("\n== SwiGLU fast-exp vs accurate expf (m=%d n_ff=%d) rc=%lld ==\n", mrows,
               n_ff, (long long)rc);
        if (rc != 0) { fail = 1; }
        else {
            std::vector<__half> a(nact), b(nact);
            CK(cudaMemcpy(a.data(), dact, nact * 2, cudaMemcpyDeviceToHost));
            CK(cudaMemcpy(b.data(), dref2, nact * 2, cudaMemcpyDeviceToHost));
            long ndiff = 0; double mabs = 0, mrel = 0;
            for (long i = 0; i < nact; i++) {
                float x = __half2float(a[i]), y = __half2float(b[i]);
                if (memcmp(&a[i], &b[i], 2) != 0) ndiff++;
                double ad = fabs((double)x - (double)y);
                double rl = fabs((double)y) > 1e-6 ? ad / fabs((double)y)
                                                   : (ad > 1e-6 ? 1e9 : 0);
                if (ad > mabs) mabs = ad;
                if (rl > mrel) mrel = rl;
            }
            // ex2.approx.ftz vs a correctly-rounded expf is ~2 ulp: expect a small fraction
            // of 1-ulp f16 pattern differences and a max_rel at the 1e-3 class. Anything at
            // or above 1e-2 means the expression, not the intrinsic, diverged.
            printf("  differing f16 patterns: %ld / %ld (%.4f%%)  max_abs=%.3e max_rel=%.3e"
                   " %s\n", ndiff, nact, 100.0 * (double)ndiff / (double)nact, mabs, mrel,
                   (mrel < 1e-2) ? "(1-ulp class — expected for ex2.approx)" : "<-- CHECK");
            if (mrel >= 1e-2) fail = 1;
        }
        if (!no_time) {
            sa.act = dact;
            printf("    fastexp     ");
            double t1 = bench(run_sw, &sa, iters);
            printf("        -> %.1f us/layer, %.3f ms over 28 layers\n", t1 * 1000, t1 * 28);
            printf("    accurate-ref");
            double t2 = bench(run_sw_ref, &sa, iters);
            printf("        -> %.1f us/layer  (speedup %.2fx)\n", t2 * 1000, t2 / t1);
        }
        cudaFree(dgu); cudaFree(dact); cudaFree(dref2);
    }

    printf("\nlast_error=%lld  RESULT: %s\n", (long long)tc_shim_last_error(),
           fail ? "FAIL" : "PASS");
    CK(cudaFree(dq)); CK(cudaFree(do_)); CK(cudaFree(dref)); CK(cudaFree(ds32));
    CK(cudaFree(do32)); CK(cudaFree(dk16)); CK(cudaFree(dv16)); CK(cudaFree(dp16));
    CK(cudaFree(dq16)); CK(cudaFree(drows));
    CK(cudaFreeHost(hq)); CK(cudaFreeHost(ho)); CK(cudaFreeHost(href));
    CK(cudaFreeHost(ho32)); CK(cudaFreeHost(hk16)); CK(cudaFreeHost(hv16));
    CK(cudaFreeHost(hqhm));
    return fail;
}
