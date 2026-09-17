// fa_g3_probe.cu — the standalone correctness + timing harness for the GEMMA-3 WINDOWED fused
// tensor-core flash attention (`tc_shim_fa_g3_window_async`, `-D ALGENTA_G3_PF_FA`) and its
// round-6 raw-mma v2 (`tc_shim_fa_g3_window2_async`, `-D ALGENTA_G3_PF_FA2`).
//
// WHY THIS EXISTS. The lever's end-to-end arbiter is the token-identity oracle gate, but that
// gate takes a ~2-minute model load per cell and reports one bit of information (same tokens or
// not). The new logic this round adds over the 7B lane's `_fa_causal_kernel` is the WINDOW: a
// key-block floor `kb_min` derived from the CTA's first query row, plus a per-row lower bound in
// the element mask. An off-by-one there is exactly the kind of defect that can move a handful of
// logits and still argmax to the same 64 tokens — so it is checked here against an independent
// HOST DOUBLE-PRECISION reference at every shape the session dispatches, element by element,
// before any speed claim is made. Round 6 re-earns the same check for the v2 kernel: the window
// logic is ported verbatim, but the score/O fragments move from the opaque WMMA accumulator to
// the raw-mma D layout, and a mis-anchored row there is the exact defect class the 7B PMMA=0
// attribution arm shipped once (max_abs 28.7, 3.2 M of 3.67 M elements wrong).
//
// WHAT IS CHECKED
//   1. the shim's on-device WMMA accumulator-layout probe AND the raw-mma layout probe (the v2
//      kernel indexes m16n8k16 A/B/D fragments and both ldmatrix roles; a mismatch must disable
//      the lever, not permute rows). Plus the v2 host contract: `dbuf=1` together with `kv32=1`
//      must be REJECTED with -305 before any launch (cp.async cannot convert f32).
//   2. BOTH kernels vs `host_ref_window_attn` — double precision, no GPU code, no layout
//      guesswork — over the SAME operands the kernel sees: Q pre-scaled and rounded to f16
//      exactly where the kernel rounds it, K/V rounded to f16 exactly where the kernel rounds
//      them (in-register for kv32=1, by the staging pass for kv32=0 — the same
//      `__float2half`, so the reference is identical for both arms), P rounded to f16 where
//      both round it. Reported per shape: max abs, max rel, RMS, and the count of elements
//      exceeding a 2% relative error.
//   3. v1: BOTH K/V routes (kv32=1 native f32 cache, kv32=0 staged f16) x BOTH output dtypes
//      (of16=0 f32, of16=1 f16) — the four combinations the session can dispatch. v2: the same
//      four at the PRODUCTION mapping dbuf = 1 - kv32, PLUS two synchronous-load f16 arms
//      (dbuf=0) that attribute the delta between cp.async double buffering and the raw-mma
//      rewrites at the same occupancy class.
//   4. cudaEvent timings (median of N) at the raced shapes, so the us/layer the A/B predicts
//      is measured here first and the model-level delta has an independent floor to agree with.
//
// SHAPES are gemma-3-27b's own (h_q=32, h_kv=16, d_head=128, sliding_window=1024,
// G3_PF_TILE=1024): the pp256 tile, the pp1024 tile, the four chunks of a RAG-4096 prefill
// (pos_base 0/1024/2048/3072, so n_keys 1024/2048/3072/4096), each as a LOCAL layer
// (window 1024, where the window binds from tile 2 on) and as a GLOBAL layer (window 0), plus
// an odd (m%64 != 0, n_keys%64 != 0, pos_base%64 != 0) tail so the CTA edge cases are covered.
//
// Build (on the GPU VM, CUDA 12.6, next to an already-built tc_shim object):
//   nvcc -O3 -arch=sm_90 -Xcompiler -fPIC -I/tmp/g3tc -c tc_shim.cu -o /tmp/g3r5tc/tc_shim.o
//   nvcc -O3 -arch=sm_90 fa_g3_probe.cu /tmp/g3r5tc/tc_shim.o -lcublas -lcudart \
//        -o /tmp/fa_g3_probe
//   /tmp/fa_g3_probe [--iters 20] [--rows 4] [--no-time]
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cuda_fp16.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <algorithm>
#include <chrono>
#include <map>
#include <string>
#include <tuple>
#include <vector>

extern "C" int64_t tc_shim_init(void);
extern "C" int64_t tc_shim_last_error(void);
extern "C" int64_t tc_shim_noseam(int64_t);
extern "C" int64_t tc_shim_fa_layout_probe(void);
extern "C" int64_t tc_shim_fa2_layout_probe(void);
extern "C" int64_t tc_shim_fa_g3_window_async(const void*, const void*, const void*, void*,
                                              const void*, int64_t, int64_t, int64_t, int64_t,
                                              int64_t, int64_t, int64_t, int64_t, int64_t,
                                              int64_t);
extern "C" int64_t tc_shim_fa_g3_window2_async(const void*, const void*, const void*, void*,
                                               const void*, int64_t, int64_t, int64_t, int64_t,
                                               int64_t, int64_t, int64_t, int64_t, int64_t,
                                               int64_t, int64_t);
// round 7's v3: v2's contract plus `rt` (16-row tiles per warp) and `gqa` (1 = pack RT query
// heads of one KV head per CTA, 0 = pack RT*16 rows of one head, i.e. FA_BM=128).
extern "C" int64_t tc_shim_fa_g3_window3_async(const void*, const void*, const void*, void*,
                                               const void*, int64_t, int64_t, int64_t, int64_t,
                                               int64_t, int64_t, int64_t, int64_t, int64_t,
                                               int64_t, int64_t, int64_t, int64_t);

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

// ── HOST reference: double precision, windowed causal, over the SAME rounded operands.
//    key j is attended by the query row at global position qpos iff
//        j <= qpos  AND  (window <= 0 OR j >= qpos + 1 - window)  AND  j < n_keys
//    which is `_attn_softmax_mask_kernel`'s predicate verbatim. Only the sampled
//    (row, dim) cells are written, so `o` is sparse and the comparison uses the same stride.
//    K/V arrive f32 and are rounded to f16 here exactly where the kernel rounds them. ──────
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
        if (hi < lo) hi = lo - 1;              // empty row -> the kernel writes zeros
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

struct Stat { double max_abs, max_rel, rms; long n, bad; };

// compare only the sampled (row, dim) cells the reference actually wrote
static Stat compare_subset(const float* got, const float* want, const int* rows, int n_check,
                          int m, int h_q, int d, int dim_stride) {
    Stat st{0, 0, 0, 0, 0};
    double se = 0;
    for (int ci = 0; ci < n_check; ci++) {
        int r = rows[ci];
        if (r >= m) continue;
        for (int h = 0; h < h_q; h++) {
            for (int e = 0; e < d; e += dim_stride) {
                size_t ix = (size_t)r * h_q * d + (size_t)h * d + e;
                double g = got[ix], w = want[ix];
                double ad = fabs(g - w);
                // RELATIVE error with an ABSOLUTE FLOOR on the denominator. The first cut divided
                // by fmax(1e-6, |want|), and an attention output is a softmax-weighted average of
                // V rows that legitimately lands within 1e-5 of zero -- there a 1e-5 absolute
                // disagreement (exactly the f16-P rounding level this kernel is supposed to sit
                // at) reads as a 100%+ relative error and the cell is counted as a defect. The
                // metric was reporting the reference's zero crossings, not the kernel. `bad`
                // therefore requires BOTH an absolute error above 1e-3 AND >2% relative, and the
                // verdict is driven by max_abs/rms (which have no denominator to game) plus that
                // count. max_rel is still printed, floored at 1e-2, as information only.
                double rl = ad / fmax(1e-2, fabs(w));
                st.max_abs = std::max(st.max_abs, ad);
                st.max_rel = std::max(st.max_rel, rl);
                se += ad * ad;
                st.n++;
                if (ad > 1e-3 && rl > 0.02) st.bad++;
            }
        }
    }
    st.rms = st.n ? sqrt(se / (double)st.n) : 0;
    return st;
}

// f16-output variant: the kernel rounds O to f16, so widen it back before comparing
static Stat compare_subset16(const __half* got, const float* want, const int* rows,
                             int n_check, int m, int h_q, int d, int dim_stride) {
    std::vector<float> g((size_t)m * h_q * d);
    for (size_t i = 0; i < g.size(); i++) g[i] = __half2float(got[i]);
    return compare_subset(g.data(), want, rows, n_check, m, h_q, d, dim_stride);
}

struct Shape { const char* name; int m, n_keys, pos_base, window; };

int main(int argc, char** argv) {
    int iters = 20, n_rows = 4, no_time = 0, bn = 64;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--iters")) iters = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--rows")) n_rows = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--bn")) bn = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--no-time")) no_time = 1;
    }
    const int h_q = 32, h_kv = 16, d = 128;         // gemma-3-27b
    const float scale = 1.0f / sqrtf(168.0f);       // query_pre_attn_scalar = 168

    CK(cudaFree(0));
    int64_t r = tc_shim_init();
    if (r != 0) { printf("tc_shim_init FAILED %ld (last_error %ld)\n", (long)r,
                          (long)tc_shim_last_error()); return 1; }
    r = tc_shim_fa_layout_probe();
    printf("[1] WMMA accumulator-layout probe: %s (status %ld)\n",
           r == 0 ? "VERIFIED ON DEVICE" : "MISMATCH -- the lever must decline", (long)r);
    if (r != 0) return 1;
    r = tc_shim_fa2_layout_probe();
    printf("[1b] raw-mma (m16n8k16 A/B/D + both ldmatrix roles) layout probe: %s (status %ld)\n",
           r == 0 ? "VERIFIED ON DEVICE" : "MISMATCH -- the v2 lever must decline", (long)r);
    if (r != 0) return 1;

    // the raced shapes: pp256, pp1024, the four RAG-4096 tiles, local AND global, plus an
    // odd tail that is not a multiple of FA_BM / BN in any of m, n_keys or pos_base.
    std::vector<Shape> shapes = {
        {"pp256    local  w=1024", 256, 256, 0, 1024},
        {"pp256    global w=0",    256, 256, 0, 0},
        {"pp1024   local  w=1024", 1024, 1024, 0, 1024},
        {"pp1024   global w=0",    1024, 1024, 0, 0},
        {"rag t1   local  w=1024", 1024, 1024, 0, 1024},
        {"rag t2   local  w=1024", 1024, 2048, 1024, 1024},
        {"rag t2   global w=0",    1024, 2048, 1024, 0},
        {"rag t3   local  w=1024", 1024, 3072, 2048, 1024},
        {"rag t4   local  w=1024", 1024, 4096, 3072, 1024},
        {"rag t4   global w=0",    1024, 4096, 3072, 0},
        {"odd tail local  w=1024", 660, 1716, 1056, 1024},
        {"odd tail global w=0",    660, 1716, 1056, 0},
    };

    int max_m = 0, max_nk = 0;
    for (auto& s : shapes) { max_m = std::max(max_m, s.m); max_nk = std::max(max_nk, s.n_keys); }

    float *hq, *hk, *hv, *href, *d_scale;
    __half *hk16, *hv16, *ho16;
    float* got;
    CK(cudaMalloc(&hq, (size_t)max_m * h_q * d * sizeof(float)));
    // K/V are allocated at h_q WIDTH, not h_kv, though every measured arm lays them out at
    // h_kv*d and only the first n_keys*h_kv*d elements are ever filled. The extra capacity exists
    // for one reason: the [1d] rejection arms deliberately pass an h_kv the GQA packing cannot
    // divide, and if the host contract were ever violated and such a call launched anyway, it
    // would stride the buffer at the wider h_kv*d. Over-allocating turns that from an
    // out-of-bounds read (a crash that would take the whole probe's output with it) into a read
    // of uninitialized-but-owned memory, so a contract violation is REPORTED instead of fatal.
    CK(cudaMalloc(&hk, (size_t)max_nk * h_q * d * sizeof(float)));
    CK(cudaMalloc(&hv, (size_t)max_nk * h_q * d * sizeof(float)));
    CK(cudaMalloc(&hk16, (size_t)max_nk * h_q * d * sizeof(__half)));
    CK(cudaMalloc(&hv16, (size_t)max_nk * h_q * d * sizeof(__half)));
    CK(cudaMalloc(&href, (size_t)max_m * h_q * d * sizeof(float)));
    CK(cudaMalloc(&got, (size_t)max_m * h_q * d * sizeof(float)));
    CK(cudaMalloc(&ho16, (size_t)max_m * h_q * d * sizeof(__half)));
    CK(cudaMalloc(&d_scale, sizeof(float)));
    CK(cudaMemcpy(d_scale, &scale, sizeof(float), cudaMemcpyHostToDevice));

    {   // [1c] the v2 host contract's REJECTION arm: dbuf=1 together with kv32=1 must return
        // -305 before any launch (cp.async copies raw bytes and cannot convert f32). The
        // pointers are never dereferenced on the decline path; a launch that happened anyway
        // would show up as a status != -305 or a sticky CUDA error at the next CK.
        int64_t st = tc_shim_fa_g3_window2_async(hq, hk, hv, got, d_scale, 256, 256,
                                                 h_q, h_kv, d, 0, 1024, bn, 1, 0, 1);
        printf("[1c] v2 dbuf=1 + kv32=1 rejection: status %ld (%s)\n", (long)st,
               st == -305 ? "REJECTED AS CONTRACTED" : "CONTRACT VIOLATED");
        if (st != -305) return 1;
        CK(cudaGetLastError());
    }

    {   // [1d] the v3 host contract's REJECTION arms. A declined lever must never masquerade as
        //      an accepted one, so every out-of-table or illegal selection has to return its code
        //      BEFORE any launch and leave no sticky CUDA error. bn is pinned explicitly in each
        //      call so a rejection can never be attributed to the wrong check.
        struct Rej { const char* what; int64_t want, got; };
        Rej rj[] = {
            // cp.async copies raw bytes and cannot convert f32 K/V -> dbuf=1 needs kv32=0
            {"v3 dbuf=1 + kv32=1", -305,
             tc_shim_fa_g3_window3_async(hq, hk, hv, got, d_scale, 256, 256, h_q, h_kv, d,
                                         0, 1024, 64, 1, 0, 1, 2, 1)},
            // v3's instantiation table stops at BN=64 by design (round 6's sweep put BN=128 last)
            {"v3 bn=128 off-table", -305,
             tc_shim_fa_g3_window3_async(hq, hk16, hv16, got, d_scale, 256, 256, h_q, h_kv, d,
                                         0, 1024, 128, 0, 0, 1, 2, 1)},
            // rt is 1 or 2; anything else has no instantiation
            {"v3 rt=3 off-table", -305,
             tc_shim_fa_g3_window3_async(hq, hk16, hv16, got, d_scale, 256, 256, h_q, h_kv, d,
                                         0, 1024, 64, 0, 0, 1, 3, 0)},
            // head_dim other than FA_D=128 is not implemented
            {"v3 d=64 unsupported", -301,
             tc_shim_fa_g3_window3_async(hq, hk16, hv16, got, d_scale, 256, 256, h_q, h_kv, 64,
                                         0, 1024, 64, 0, 0, 1, 2, 1)},
            // GQA packing puts rt query heads in ONE CTA and they must share one KV head, so rt
            // has to divide the group size h_q/h_kv exactly. Here h_kv == h_q makes the group 1
            // head wide and rt=2 cannot divide it; without this check the second tile would read
            // the wrong K/V and return plausible-looking WRONG numbers.
            {"v3 gqa=1 rt=2 group=1", -304,
             tc_shim_fa_g3_window3_async(hq, hk16, hv16, got, d_scale, 256, 256, h_q, h_q, d,
                                         0, 1024, 64, 0, 0, 1, 2, 1)},
        };
        for (auto& x : rj) {
            printf("[1d] %-24s rejection: status %ld (%s)\n", x.what, (long)x.got,
                   x.got == x.want ? "REJECTED AS CONTRACTED" : "CONTRACT VIOLATED");
            if (x.got != x.want) return 1;
            CK(cudaGetLastError());
        }
    }

    std::vector<float> sq((size_t)max_m * h_q * d), sk((size_t)max_nk * h_kv * d),
                       sv((size_t)max_nk * h_kv * d), sr((size_t)max_m * h_q * d);
    std::vector<int> rows(n_rows);

    int fails = 0;
    printf("\n[2] fused windowed kernel (v1 WMMA + v2 raw-mma + v3 RT-tiled) vs HOST "
           "DOUBLE-PRECISION reference (%d sampled rows/shape, dim_stride 8 => %d of %d dims)\n",
           n_rows, d / 8, d);
    printf("%-24s %-26s %8s %10s %10s %10s %8s %s\n", "shape", "arm", "n", "max_abs",
           "max_rel", "rms", ">2%rel", "verdict");

    // v2's full output, keyed by (kv32, of16, dbuf), captured as each v2 arm runs so the v3 arms
    // that follow can be held to BIT identity against it (see the gate below). Cleared per shape
    // so a stale buffer from a previous shape can never satisfy the comparison.
    std::map<std::tuple<int, int, int>, std::vector<float>> v2bits;

    for (auto& s : shapes) {
        v2bits.clear();
        // fresh operands per shape so a stale buffer can never mask a window bug
        fill_rand(sq.data(), (long)s.m * h_q * d, 0x1234u + s.m, -1.0f, 1.0f);
        fill_rand(sk.data(), (long)s.n_keys * h_kv * d, 0x9e37u + s.n_keys, -1.0f, 1.0f);
        fill_rand(sv.data(), (long)s.n_keys * h_kv * d, 0x5bf0u + s.pos_base, -1.0f, 1.0f);
        CK(cudaMemcpy(hq, sq.data(), (size_t)s.m * h_q * d * sizeof(float),
                      cudaMemcpyHostToDevice));
        CK(cudaMemcpy(hk, sk.data(), (size_t)s.n_keys * h_kv * d * sizeof(float),
                      cudaMemcpyHostToDevice));
        CK(cudaMemcpy(hv, sv.data(), (size_t)s.n_keys * h_kv * d * sizeof(float),
                      cudaMemcpyHostToDevice));

        // the sampled rows: first, last-valid, one just past a window boundary, one odd
        rows[0] = 0;
        rows[1] = s.m - 1;
        rows[2] = std::min(s.m - 1, s.window > 0 ? s.window - s.pos_base : s.m / 2);
        if (rows[2] < 0) rows[2] = 0;
        rows[3] = std::min(s.m - 1, 37);
        std::sort(rows.begin(), rows.end());
        rows.erase(std::unique(rows.begin(), rows.end()), rows.end());
        int nr = (int)rows.size();

        memset(sr.data(), 0, sr.size() * sizeof(float));
        host_ref_window_attn(sq.data(), sk.data(), sv.data(), sr.data(), rows.data(), nr,
                             s.m, s.n_keys, h_q, h_kv, d, s.pos_base, s.window, scale, 8);

        // the staged-f16 twin of the cache (the kv32=0 control arm reads this)
        {
            std::vector<__half> t((size_t)s.n_keys * h_kv * d);
            for (size_t i = 0; i < t.size(); i++) t[i] = __float2half(sk[i]);
            CK(cudaMemcpy(hk16, t.data(), t.size() * sizeof(__half), cudaMemcpyHostToDevice));
            for (size_t i = 0; i < t.size(); i++) t[i] = __float2half(sv[i]);
            CK(cudaMemcpy(hv16, t.data(), t.size() * sizeof(__half), cudaMemcpyHostToDevice));
        }

        struct Arm { std::string tag; int ver, kv32, of16, dbuf, rt, gqa; };
        std::vector<Arm> arms = {
            // round 5's WMMA kernel (v1) — the four (kv32, of16) combinations it dispatches
            {"v1 kv32=1 of16=0", 1, 1, 0, 0, 1, 0}, {"v1 kv32=0 of16=0", 1, 0, 0, 0, 1, 0},
            {"v1 kv32=1 of16=1", 1, 1, 1, 0, 1, 0}, {"v1 kv32=0 of16=1", 1, 0, 1, 0, 1, 0},
            // round 6's raw-mma kernel (v2) at the PRODUCTION mapping dbuf = 1 - kv32:
            // cp.async double buffering is legal only on the f16 route (cp.async copies raw
            // bytes and cannot convert), so kv32=1 runs single-buffered synchronous loads
            {"v2 kv32=1 of16=0", 2, 1, 0, 0, 1, 0}, {"v2 kv32=0 of16=0", 2, 0, 0, 1, 1, 0},
            {"v2 kv32=1 of16=1", 2, 1, 1, 0, 1, 0}, {"v2 kv32=0 of16=1", 2, 0, 1, 1, 1, 0},
            // v2 attribution arms — synchronous loads on the f16 route: v2s vs v2-kv32=0
            // isolates cp.async double buffering; v2s vs v1 isolates raw-mma + in-register P
            // + the direct epilogue at the SAME occupancy class
            {"v2s kv32=0 of16=0", 2, 0, 0, 0, 1, 0}, {"v2s kv32=0 of16=1", 2, 0, 1, 0, 1, 0},
        };
        // ── round 7's v3: the FULL cross product (rt,gqa) x (kv32,dbuf) x of16, so the numeric
        //    gate covers every combination the host entry can select. RT1/GQA0 is v2 restated
        //    and is the attribution control (it isolates "did the v3 rewrite cost anything" from
        //    "did RT=2 help"); RT2/GQA1 is GQA-packed CTAs; RT2/GQA0 is FA_BM=128. v3's table
        //    stops at BN=64 by design (round 6's sweep put BN=128 last), so at --bn 128 the v3
        //    arms are SKIPPED rather than counted as failures — the skip is printed, not silent.
        //    ──
        const int v3_rt[3] = {1, 2, 2}, v3_gqa[3] = {0, 0, 1};
        const char* v3_nm[3] = {"RT1", "BM128", "GQA2"};
        const int v3_kv[3] = {1, 0, 0}, v3_db[3] = {0, 0, 1};
        if (bn != 128) {
            for (int rg = 0; rg < 3; rg++)
                for (int kd = 0; kd < 3; kd++)
                    for (int oo = 0; oo < 2; oo++) {
                        char tb[96];
                        snprintf(tb, sizeof(tb), "v3 %s kv32=%d of16=%d db=%d", v3_nm[rg],
                                 v3_kv[kd], oo, v3_db[kd]);
                        arms.push_back({tb, 3, v3_kv[kd], oo, v3_db[kd], v3_rt[rg], v3_gqa[rg]});
                    }
        } else {
            printf("%-24s %-18s %8s %10s %10s %10s %8s %s\n", s.name, "v3 (all arms)",
                   "-", "-", "-", "-", "-", "SKIPPED: v3's table stops at BN=64");
        }
        for (auto& a : arms) {
            CK(cudaMemset(got, 0, (size_t)s.m * h_q * d * sizeof(float)));
            CK(cudaMemset(ho16, 0, (size_t)s.m * h_q * d * sizeof(__half)));
            // ORDER THE ZEROING BEFORE THE LAUNCH. The kernel runs on the shim's OWN stream,
            // created cudaStreamNonBlocking, and a non-blocking stream is NOT ordered against the
            // legacy stream these two cudaMemsets are issued on -- so without an explicit device
            // sync the memsets can land AFTER the kernel has already written, zeroing whole
            // output rows. That is exactly what the first run of this probe produced: four of
            // twelve shapes showed max_rel == 1.000 with rms ~0.39 on the kv32=1/of16=0 arm only,
            // i.e. "the kernel returned zeros", while the kv32=0 arm of the SAME shape writing to
            // the SAME buffer agreed with the reference to 1.5e-5. Same math, two instantiations,
            // agreeing at eight shapes and disagreeing at four = a harness race, not a kernel
            // defect. The real session cannot hit this: it launches the kernel and its consumer
            // (the o_proj GemmEx) on the SAME shim stream, which is the G3_STREAM contract the
            // whole build already rests on.
            CK(cudaDeviceSynchronize());
            void* optr = a.of16 ? (void*)ho16 : (void*)got;
            const void* kp = a.kv32 ? (const void*)hk : (const void*)hk16;
            const void* vp = a.kv32 ? (const void*)hv : (const void*)hv16;
            int64_t st = (a.ver == 3)
                ? tc_shim_fa_g3_window3_async(hq, kp, vp, optr, d_scale, s.m, s.n_keys,
                                              h_q, h_kv, d, s.pos_base, s.window, bn,
                                              a.kv32, a.of16, a.dbuf, a.rt, a.gqa)
                : (a.ver == 2)
                ? tc_shim_fa_g3_window2_async(hq, kp, vp, optr, d_scale, s.m, s.n_keys,
                                              h_q, h_kv, d, s.pos_base, s.window, bn,
                                              a.kv32, a.of16, a.dbuf)
                : tc_shim_fa_g3_window_async(hq, kp, vp, optr, d_scale, s.m, s.n_keys,
                                             h_q, h_kv, d, s.pos_base, s.window, bn,
                                             a.kv32, a.of16);
            if (st != 0) {
                printf("%-24s %-18s %8s %10s %10s %10s %8s STATUS %ld\n", s.name,
                       a.tag.c_str(), "-", "-", "-", "-", "-", (long)st);
                fails++;
                continue;
            }
            CK(cudaDeviceSynchronize());
            std::vector<float> g((size_t)s.m * h_q * d);
            if (a.of16) {
                std::vector<__half> gh(g.size());
                CK(cudaMemcpy(gh.data(), ho16, g.size() * sizeof(__half),
                              cudaMemcpyDeviceToHost));
                for (size_t i = 0; i < g.size(); i++) g[i] = __half2float(gh[i]);
            } else {
                CK(cudaMemcpy(g.data(), got, g.size() * sizeof(float), cudaMemcpyDeviceToHost));
            }
            Stat c = compare_subset(g.data(), sr.data(), rows.data(), nr, s.m, h_q, d, 8);
            // The online softmax reorders the sum and rescales O per key block, so the expectation
            // is f16-P-level agreement, not bit identity. The verdict rides the DENOMINATOR-FREE
            // quantities -- max_abs and rms over outputs that are O(1e-2..1) -- plus the floored
            // >2% count; max_rel alone is not a verdict, see compare_subset for why.
            bool ok = (c.bad == 0) && c.max_abs < 5e-3 && c.rms < 5e-4;
            // ── ROUND 7 ADDS A STRICTER GATE FOR v3: BIT IDENTITY AGAINST v2, not tolerance.
            //    v3 does not change a single rounding point. At RT=1/GQA=0 it IS v2 restated. At
            //    RT=2/GQA=1 both tiles share v2's row0, so [kb_min, kb_max], the key-block order,
            //    the NT tiling and the mma k-grouping are v2's exactly per (row, head). At
            //    RT=2/GQA=0 the range widens to the union over 128 rows, but every extra block is
            //    fully masked and the online-softmax rescale annihilates it EXACTLY (trailing:
            //    n0 == m0 so a0 = 1 and p = expf(-1e30 - m0) = 0; leading: the expf(NEG-NEG) = 1
            //    transient is multiplied away by the next real block's a0 = expf(-1e30 - finite)
            //    = 0). So a tolerance pass would be a WEAKER claim than the code can make, and a
            //    single differing bit means the window/mask reasoning above is wrong somewhere.
            //    Any v3 arm whose v2 twin is missing from this shape is reported, never skipped
            //    silently. ──
            const std::tuple<int, int, int> akey(a.kv32, a.of16, a.dbuf);
            char bitbuf[48];
            const char* bitstr = "";
            if (a.ver == 2) {
                v2bits[akey] = g;
            } else if (a.ver == 3) {
                auto it = v2bits.find(akey);
                if (it == v2bits.end()) {
                    snprintf(bitbuf, sizeof(bitbuf), " NOv2REF");
                    bitstr = bitbuf;
                    ok = false;
                } else {
                    long ndiff = 0;
                    const std::vector<float>& rb = it->second;
                    for (size_t i = 0; i < g.size() && i < rb.size(); i++)
                        if (memcmp(&g[i], &rb[i], sizeof(float)) != 0) ndiff++;
                    if (ndiff == 0) {
                        snprintf(bitbuf, sizeof(bitbuf), " BITIDENT-v2");
                    } else {
                        snprintf(bitbuf, sizeof bitbuf, " BITDIFF=%ld", ndiff);
                        ok = false;
                    }
                    bitstr = bitbuf;
                }
            }
            if (!ok) fails++;
            printf("%-24s %-26s %8ld %10.3e %10.3e %10.3e %8ld %s%s\n", s.name,
                   a.tag.c_str(), c.n, c.max_abs, c.max_rel, c.rms, c.bad,
                   ok ? "PASS" : "FAIL", bitstr);
        }
    }

    if (!no_time) {
        printf("\n[3] timing, median of %d (BN=%d) -- the fused kernel alone; "
               "v2 = raw-mma, dbuf = 1-kv32 (the production mapping)\n", iters, bn);
        // WALL CLOCK + cudaDeviceSynchronize, NOT cudaEventRecord on the legacy stream: the
        // shim launches on its OWN non-blocking stream, which the legacy stream's events do
        // not order against, so event brackets around these entries measured the launch gap
        // (~4 us regardless of shape) instead of the kernel. Round 5's probe carried the same
        // defect in this section; its correctness section is unaffected (it synchronizes the
        // device around every launch), and no round-5 claim was made from these numbers.
        printf("%-24s %11s %11s %8s %11s %11s %8s %11s\n", "shape",
               "v1 kv32 us", "v2 kv32 us", "delta", "v1 kv16 us", "v2D kv16 us", "delta",
               "v2s kv16 us");
        for (auto& s : shapes) {
            if (s.m != 1024 && s.m != 256) continue;
            double t[5];
            // order: 0 = v1 kv32=1, 1 = v2 kv32=1 dbuf=0, 2 = v1 kv32=0, 3 = v2 kv32=0 dbuf=1,
            //        4 = v2 kv32=0 dbuf=0 (attributes cp.async against the raw-mma rewrite)
            for (int cfg = 0; cfg < 5; cfg++) {
                int kv = (cfg < 2) ? 1 : 0;
                int v2 = (cfg == 1 || cfg == 3 || cfg == 4) ? 1 : 0;
                int db = (cfg == 3) ? 1 : 0;
                const void* kp = kv ? (const void*)hk : (const void*)hk16;
                const void* vp = kv ? (const void*)hv : (const void*)hv16;
                std::vector<double> ms(iters);
                for (int it = 0; it < iters; it++) {
                    CK(cudaDeviceSynchronize());
                    auto t0 = std::chrono::steady_clock::now();
                    if (v2)
                        tc_shim_fa_g3_window2_async(hq, kp, vp, got, d_scale, s.m, s.n_keys,
                                                    h_q, h_kv, d, s.pos_base, s.window, bn,
                                                    kv, 0, db);
                    else
                        tc_shim_fa_g3_window_async(hq, kp, vp, got, d_scale, s.m, s.n_keys,
                                                   h_q, h_kv, d, s.pos_base, s.window, bn,
                                                   kv, 0);
                    CK(cudaDeviceSynchronize());
                    auto t1 = std::chrono::steady_clock::now();
                    ms[it] = std::chrono::duration<double, std::micro>(t1 - t0).count();
                }
                std::sort(ms.begin(), ms.end());
                t[cfg] = ms[ms.size() / 2];
            }
            printf("%-24s %11.1f %11.1f %+7.2f%% %11.1f %11.1f %+7.2f%% %11.1f\n", s.name,
                   t[0], t[1], 100.0 * (t[1] - t[0]) / t[0],
                   t[2], t[3], 100.0 * (t[3] - t[2]) / t[2], t[4]);
        }
    }

    // ═══ [4] ROUND-7 DECISION TABLE ═══
    // The one measurement this round exists to take: does feeding TWO m16 row-tiles from each
    // B-fragment load beat v2, and if so which way of spending RT=2 wins — GQA-packed CTAs
    // (two query heads of one KV head sharing a tile) or FA_BM=128 (twice the rows of one head)?
    // Run at the PRODUCTION mapping (kv32=0 staged f16 K/V, of16=1 pre-staged-A output, dbuf=1
    // cp.async double buffering) so the numbers are comparable to what the session dispatches,
    // with BN swept INSIDE the process so a single launch yields the whole table.
    //
    // v3 RT1/GQA0 is v2 restated and rides along as the ATTRIBUTION CONTROL: it separates "the
    // v3 rewrite itself cost something" from "RT=2 bought something". If RT1 does not reproduce
    // v2 within noise, the RT2 columns cannot be interpreted and the round stops here.
    //
    // Timing is wall clock + cudaDeviceSynchronize (NOT cudaEventRecord on the legacy stream: the
    // shim launches on its own non-blocking stream, which legacy-stream events do not order
    // against — that defect made round 5's timing section measure launch gaps). 3 warmups then
    // `iters` measured, median reported, matching the campaign's 3+7 cell convention in spirit.
    if (!no_time) {
        printf("\n[4] ROUND-7 DECISION TABLE -- production mapping kv32=0 of16=1 dbuf=1, "
               "median of %d after 3 warmups. RT1 = v3 control (v2 restated),\n"
               "    GQA2 = two query heads of one KV head per CTA, BM128 = FA_BM=128. "
               "Deltas are vs v2 at the same BN.\n", iters);
        printf("%-24s %4s %10s %10s %10s %10s %10s %10s\n", "shape", "BN", "v2 us",
               "v3RT1 us", "ctrl dev", "v3GQA2 us", "GQA2 dev", "v3BM128 us");
        const int bns[2] = {32, 64};
        for (auto& s : shapes) {
            if (s.m != 1024 && s.m != 256) continue;
            for (int bi = 0; bi < 2; bi++) {
                const int cbn = bns[bi];
                double t[4];
                // cfg: 0 = v2, 1 = v3 RT1 GQA0, 2 = v3 RT2 GQA1, 3 = v3 RT2 GQA0
                for (int cfg = 0; cfg < 4; cfg++) {
                    std::vector<double> ms(iters);
                    for (int it = -3; it < iters; it++) {
                        CK(cudaDeviceSynchronize());
                        auto t0 = std::chrono::steady_clock::now();
                        if (cfg == 0)
                            tc_shim_fa_g3_window2_async(hq, hk16, hv16, ho16, d_scale, s.m,
                                                        s.n_keys, h_q, h_kv, d, s.pos_base,
                                                        s.window, cbn, 0, 1, 1);
                        else
                            tc_shim_fa_g3_window3_async(hq, hk16, hv16, ho16, d_scale, s.m,
                                                        s.n_keys, h_q, h_kv, d, s.pos_base,
                                                        s.window, cbn, 0, 1, 1,
                                                        cfg == 1 ? 1 : 2, cfg == 2 ? 1 : 0);
                        CK(cudaDeviceSynchronize());
                        auto t1 = std::chrono::steady_clock::now();
                        if (it >= 0)
                            ms[it] = std::chrono::duration<double, std::micro>(t1 - t0).count();
                    }
                    std::sort(ms.begin(), ms.end());
                    t[cfg] = ms[ms.size() / 2];
                }
                printf("%-24s %4d %10.1f %10.1f %+9.2f%% %10.1f %+9.2f%% %10.1f %+9.2f%%\n",
                       s.name, cbn, t[0], t[1], 100.0 * (t[1] - t[0]) / t[0],
                       t[2], 100.0 * (t[2] - t[0]) / t[0],
                       t[3], 100.0 * (t[3] - t[0]) / t[0]);
            }
        }
    }

    printf("\n=== fa_g3_probe: %d FAIL(s) ===\n", fails);
    CK(cudaFree(hq)); CK(cudaFree(hk)); CK(cudaFree(hv)); CK(cudaFree(hk16));
    CK(cudaFree(hv16)); CK(cudaFree(href)); CK(cudaFree(got)); CK(cudaFree(ho16));
    CK(cudaFree(d_scale));
    return fails ? 1 : 0;
}
