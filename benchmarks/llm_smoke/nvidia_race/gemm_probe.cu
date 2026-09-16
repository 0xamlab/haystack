// gemm_probe.cu -- FRONT 6: where the RAG-4096 GEMM time actually goes, and what cuBLAS can do
// better on the two roles that are NOT at roofline.
//
// WHY THIS PROBE EXISTS. The FRONT-6 nsys dissection of one RAG-4096 prefill (4 chunks x 28
// layers, m=1024 per chunk) puts GPU busy at 280.953 ms of a 284.097 ms trace wall -- a 3.144 ms
// (1.11%) host/launch gap, which REFUTES round 5's #1 ranked target ("HOST/LAUNCH GAP ~6-10 ms")
// and re-confirms round 3's refutation of prefill CUDA graphs: there is nothing to recover.
// 80.46% of the busy (226.048 ms, 448 kernels) is cuBLAS. Attributed by launch geometry the four
// projection roles run at VERY different efficiencies:
//
//   gate/up  M=1024 N=37888 K=3584   1053.0 us  263.5 TF/s  (84.5% of the A100's 312 dense f16)
//   qkv      M=1024 N=4608  K=3584    142.6 us  237.2 TF/s
//   down     M=1024 N=3584  K=18944   680.1 us  204.0 TF/s  <-- 59 TF/s below gate/up
//   o_proj   M=1024 N=3584  K=3584    142.6 us  184.5 TF/s  <-- 79 TF/s below gate/up
//
// down and o_proj are the two shapes whose output tile count does not fill the 108 SMs evenly
// (o_proj: 8x28 = 224 tiles of 128x128 = 2.07 waves) and whose K is either huge (down, K=18944,
// the classic split-K case) or small. tc_shim_init() calls cublasCreate + cublasSetStream +
// cublasSetMathMode but NEVER cublasSetWorkspace, so GemmEx runs on cuBLAS's small default
// workspace -- and split-K algorithms need workspace. That is a concrete, testable hypothesis for
// the 59-79 TF/s deficit, and this probe tests it without loading the model (seconds, not the
// ~5 min a driver run costs).
//
// ARMS, per shape:
//   ex_ws0    cublasGemmEx + CUBLAS_GEMM_DEFAULT, no explicit workspace   == THE SHIPPED PATH
//   ex_ws32   cublasGemmEx + CUBLAS_GEMM_DEFAULT, cublasSetWorkspace(32 MB)
//   ex_ws256  cublasGemmEx + CUBLAS_GEMM_DEFAULT, cublasSetWorkspace(256 MB)
//   ex_top    cublasGemmEx + CUBLAS_GEMM_DEFAULT_TENSOR_OP, no explicit workspace
//   lt_ws32   cublasLtMatmul, best of the top-N heuristics, 32 MB workspace
//   lt_ws256  cublasLtMatmul, best of the top-N heuristics, 256 MB workspace
//
// The layouts replicate tc_shim.cu's GemmEx call EXACTLY (row-major C[M,N] = A_rm[M,K] @
// W_rm[N,K]^T via column-major C[N,M] = op(A=W)^T x op(B=A)), so a number here transfers.
//
// Numerics: a different algorithm changes the REDUCTION ORDER, so an lt/ws win is NOT
// bit-identical to the shipped path. This probe reports the max-abs and max-rel difference of
// each winning arm against ex_ws0 over the full C tile so the caller knows whether it is a
// rounding-order change (gate-decidable) or something structural.
//
// build: nvcc -O3 -arch=sm_80 gemm_probe.cu -lcublas -lcublasLt -lcudart -o gemm_probe
// run:   ./gemm_probe [--iters N] [--warmup N] [--top N] [--only substr]
#include <cublasLt.h>
#include <cublas_v2.h>
#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define CK(x)                                                                  \
  do {                                                                         \
    cudaError_t e_ = (x);                                                      \
    if (e_ != cudaSuccess) {                                                   \
      printf("CUDA FAIL %s:%d %s\n", __FILE__, __LINE__,                       \
             cudaGetErrorString(e_));                                          \
      exit(1);                                                                 \
    }                                                                          \
  } while (0)
#define CB(x)                                                                  \
  do {                                                                         \
    cublasStatus_t s_ = (x);                                                   \
    if (s_ != CUBLAS_STATUS_SUCCESS) {                                         \
      printf("CUBLAS FAIL %s:%d status=%d\n", __FILE__, __LINE__, (int)s_);     \
      exit(1);                                                                 \
    }                                                                          \
  } while (0)

static const double A100_F16_TC_PEAK = 312.0;  // TF/s dense, sm_80, at the pinned 1410 MHz

struct Shape {
  const char* role;
  int M, N, K;
  bool c_f16;      // gate/up writes f16 C under ALGENTA_7B_PF_F16MLP; the rest write f32
  bool accumulate; // o_proj / down_proj feed the residual with beta 1
};

// Qwen2.5-7B (manifest.json: hidden 3584, inter 18944, h_q 28, h_kv 4, d_head 128, 28 layers)
// at the prefill tile _B1_PASS_MAX = 1024 rows. n_qkv = (28 + 2*4) * 128 = 4608.
static const Shape SHAPES[] = {
    {"qkv", 1024, 4608, 3584, false, false},
    {"o_proj", 1024, 3584, 3584, false, true},
    {"gate_up", 1024, 37888, 3584, true, false},
    {"down", 1024, 3584, 18944, false, true},
};
static const int NSHAPE = (int)(sizeof(SHAPES) / sizeof(SHAPES[0]));

static int g_iters = 20, g_warm = 5, g_top = 32, g_msweep = 0;

static double med(std::vector<double> v) {
  if (v.empty()) return 0.0;
  std::sort(v.begin(), v.end());
  size_t n = v.size();
  return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

// ── the shipped call, verbatim from tc_shim.cu's gemm entries ──────────────────────────────
static double run_gemmex(cublasHandle_t h, const Shape& s, const void* w16, const void* a16,
                         void* c, cublasGemmAlgo_t algo) {
  float alpha = 1.0f, beta = s.accumulate ? 1.0f : 0.0f;
  __half alpha_h = __float2half(1.0f), beta_h = __float2half(0.0f);
  // the f16-C arm (gate/up) uses beta 0, so the f32 scalars are the right type either way:
  // CUBLAS_COMPUTE_32F takes f32 alpha/beta regardless of the C dtype.
  (void)alpha_h; (void)beta_h;
  std::vector<double> ts;
  cudaEvent_t e0, e1;
  CK(cudaEventCreate(&e0)); CK(cudaEventCreate(&e1));
  for (int i = 0; i < g_warm + g_iters; i++) {
    CK(cudaEventRecord(e0, 0));
    cublasStatus_t st = cublasGemmEx(
        h, CUBLAS_OP_T, CUBLAS_OP_N, s.N, s.M, s.K, &alpha, w16, CUDA_R_16F, s.K, a16,
        CUDA_R_16F, s.K, &beta, c, s.c_f16 ? CUDA_R_16F : CUDA_R_32F, s.N,
        CUBLAS_COMPUTE_32F, algo);
    CK(cudaEventRecord(e1, 0));
    CK(cudaEventSynchronize(e1));
    if (st != CUBLAS_STATUS_SUCCESS) {
      printf("    gemmEx status=%d\n", (int)st);
      cudaEventDestroy(e0); cudaEventDestroy(e1);
      return -1.0;
    }
    if (i >= g_warm) {
      float ms = 0; CK(cudaEventElapsedTime(&ms, e0, e1));
      ts.push_back(ms);
    }
  }
  cudaEventDestroy(e0); cudaEventDestroy(e1);
  return med(ts);
}

// ── cublasLt with an explicit workspace and a heuristic search ─────────────────────────────
struct LtBest {
  double ms = -1.0;
  int idx = -1;
  int nres = 0;
  cublasLtMatmulAlgo_t algo;
  int algo_id = -1, tile = -1, stages = -1, splitk = -1, red = -1, swiz = -1, custom = -1;
};

static LtBest run_lt(cublasLtHandle_t lt, const Shape& s, const void* w16, const void* a16,
                     void* c, void* ws, size_t wsz) {
  LtBest best;
  cublasLtMatmulDesc_t op = nullptr;
  if (cublasLtMatmulDescCreate(&op, CUBLAS_COMPUTE_32F, CUDA_R_32F) != CUBLAS_STATUS_SUCCESS)
    return best;
  cublasOperation_t ta = CUBLAS_OP_T, tb = CUBLAS_OP_N;
  cublasLtMatmulDescSetAttribute(op, CUBLASLT_MATMUL_DESC_TRANSA, &ta, sizeof(ta));
  cublasLtMatmulDescSetAttribute(op, CUBLASLT_MATMUL_DESC_TRANSB, &tb, sizeof(tb));
  cublasLtMatrixLayout_t La = nullptr, Lb = nullptr, Lc = nullptr;
  // stored layouts, pre-op: W is row-major [N,K] == column-major [K,N] ld=K
  cublasLtMatrixLayoutCreate(&La, CUDA_R_16F, s.K, s.N, s.K);
  cublasLtMatrixLayoutCreate(&Lb, CUDA_R_16F, s.K, s.M, s.K);
  cublasLtMatrixLayoutCreate(&Lc, s.c_f16 ? CUDA_R_16F : CUDA_R_32F, s.N, s.M, s.N);
  cublasLtMatmulPreference_t pref = nullptr;
  cublasLtMatmulPreferenceCreate(&pref);
  cublasLtMatmulPreferenceSetAttribute(pref, CUBLASLT_MATMUL_PREF_MAX_WORKSPACE_BYTES, &wsz,
                                       sizeof(wsz));
  std::vector<cublasLtMatmulHeuristicResult_t> res(g_top);
  int nres = 0;
  cublasStatus_t hs = cublasLtMatmulAlgoGetHeuristic(lt, op, La, Lb, Lc, Lc, pref, g_top,
                                                     res.data(), &nres);
  best.nres = (hs == CUBLAS_STATUS_SUCCESS) ? nres : 0;
  if (best.nres <= 0) {
    printf("    lt heuristic status=%d nres=%d\n", (int)hs, nres);
    cublasLtMatmulPreferenceDestroy(pref);
    cublasLtMatrixLayoutDestroy(La); cublasLtMatrixLayoutDestroy(Lb);
    cublasLtMatrixLayoutDestroy(Lc); cublasLtMatmulDescDestroy(op);
    return best;
  }
  float alpha = 1.0f, beta = s.accumulate ? 1.0f : 0.0f;
  cudaEvent_t e0, e1;
  CK(cudaEventCreate(&e0)); CK(cudaEventCreate(&e1));
  for (int i = 0; i < best.nres; i++) {
    // one warm launch: an algo that fails at exec time must not be timed
    cublasStatus_t st = cublasLtMatmul(lt, op, &alpha, w16, La, a16, Lb, &beta, c, Lc, c, Lc,
                                       &res[i].algo, ws, wsz, 0);
    if (st != CUBLAS_STATUS_SUCCESS) continue;
    CK(cudaStreamSynchronize(0));
    std::vector<double> ts;
    bool ok = true;
    for (int it = 0; it < g_warm + g_iters; it++) {
      CK(cudaEventRecord(e0, 0));
      st = cublasLtMatmul(lt, op, &alpha, w16, La, a16, Lb, &beta, c, Lc, c, Lc, &res[i].algo,
                          ws, wsz, 0);
      CK(cudaEventRecord(e1, 0));
      if (cudaEventSynchronize(e1) != cudaSuccess || st != CUBLAS_STATUS_SUCCESS) { ok = false; break; }
      if (it >= g_warm) { float ms = 0; CK(cudaEventElapsedTime(&ms, e0, e1)); ts.push_back(ms); }
    }
    if (!ok || ts.empty()) continue;
    double m = med(ts);
    if (best.ms < 0 || m < best.ms) {
      best.ms = m; best.idx = i; best.algo = res[i].algo;
      size_t sz;
      int v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_ID, &v, sizeof(v), &sz);
      best.algo_id = v; v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_TILE_ID, &v, sizeof(v), &sz);
      best.tile = v; v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_STAGES_ID, &v, sizeof(v), &sz);
      best.stages = v; v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_SPLITK_NUM, &v, sizeof(v), &sz);
      best.splitk = v; v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_REDUCTION_SCHEME, &v, sizeof(v), &sz);
      best.red = v; v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_CTA_SWIZZLING, &v, sizeof(v), &sz);
      best.swiz = v; v = -1;
      cublasLtMatmulAlgoConfigGetAttribute(&res[i].algo, CUBLASLT_ALGO_CONFIG_CUSTOM_OPTION, &v, sizeof(v), &sz);
      best.custom = v;
    }
  }
  cudaEventDestroy(e0); cudaEventDestroy(e1);
  cublasLtMatmulPreferenceDestroy(pref);
  cublasLtMatrixLayoutDestroy(La); cublasLtMatrixLayoutDestroy(Lb);
  cublasLtMatrixLayoutDestroy(Lc); cublasLtMatmulDescDestroy(op);
  return best;
}

int main(int argc, char** argv) {
  std::string only;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--iters") && i + 1 < argc) g_iters = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--warmup") && i + 1 < argc) g_warm = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--top") && i + 1 < argc) g_top = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--only") && i + 1 < argc) only = argv[++i];
    else if (!strcmp(argv[i], "--msweep")) g_msweep = 1;
  }
  CK(cudaFree(0));
  cudaDeviceProp prop{};
  CK(cudaGetDeviceProperties(&prop, 0));
  int smclk = 0;
  cudaDeviceGetAttribute(&smclk, cudaDevAttrClockRate, 0);
  printf("gemm_probe: %s  sm_%d%d  SMs=%d  iters=%d warmup=%d top=%d\n", prop.name, prop.major,
         prop.minor, prop.multiProcessorCount, g_iters, g_warm, g_top);
  printf("f16 tensor-core dense peak assumed %.0f TF/s at the pinned clocks\n\n",
         A100_F16_TC_PEAK);

  cublasLtHandle_t lt = nullptr;
  if (cublasLtCreate(&lt) != CUBLAS_STATUS_SUCCESS) { printf("cublasLtCreate FAIL\n"); return 1; }

  const size_t WS_SMALL = 32ull << 20, WS_BIG = 256ull << 20;
  void* ws_small = nullptr; void* ws_big = nullptr;
  CK(cudaMalloc(&ws_small, WS_SMALL)); CK(cudaMalloc(&ws_big, WS_BIG));
  CK(cudaMemset(ws_small, 0, WS_SMALL)); CK(cudaMemset(ws_big, 0, WS_BIG));

  // ── --msweep: is the driver's 4 x 1024 chunking COSTING money on the projections? ──────────
  // A RAG-4096 prefill does the same four projections per layer either way -- 4 passes of
  // m=1024, 2 of m=2048, or 1 of m=4096 all compute 1905.3 GFLOP per layer -- so this is a pure
  // efficiency question: tail-wave quantization (m=1024, N=3584 = 224 tiles = 2.07 waves on 108
  // SMs) and the weight re-reads (every chunk streams the full 466 MB of that layer's weights
  // again). Round 2 measured the OTHER direction (2x512 at pp1024 lost 1.2 ms because m=512
  // projections run at 151 TF/s against m=1024's 178), so the sign of the effect at larger m is
  // not a given and has to be measured.
  if (g_msweep) {
    const int MS[] = {1024, 2048, 4096};
    printf("%-9s %6s %12s %12s %9s %9s %10s\n", "role", "m", "ex_ws0_us", "lt_best_us",
           "TF/s(ex)", "TF/s(lt)", "lt_algo");
    double tot[3][2] = {{0, 0}, {0, 0}, {0, 0}};
    for (int mi = 0; mi < 3; mi++) {
      for (int si = 0; si < NSHAPE; si++) {
        Shape s = SHAPES[si];
        s.M = MS[mi];
        size_t na = (size_t)s.M * s.K, nw = (size_t)s.N * s.K, nc = (size_t)s.M * s.N;
        size_t csz = s.c_f16 ? sizeof(__half) : sizeof(float);
        __half *a16 = nullptr, *w16 = nullptr; void* c = nullptr; void* c2 = nullptr;
        CK(cudaMalloc(&a16, na * sizeof(__half)));
        CK(cudaMalloc(&w16, nw * sizeof(__half)));
        CK(cudaMalloc(&c, nc * csz)); CK(cudaMalloc(&c2, nc * csz));
        CK(cudaMemset(a16, 0x3c, na * sizeof(__half)));
        CK(cudaMemset(w16, 0x3c, nw * sizeof(__half)));
        CK(cudaMemset(c, 0, nc * csz)); CK(cudaMemset(c2, 0, nc * csz));
        cublasHandle_t h = nullptr;
        if (cublasCreate(&h) != CUBLAS_STATUS_SUCCESS) { printf("cublasCreate FAIL\n"); return 1; }
        cublasSetStream(h, 0);
        cublasSetMathMode(h, CUBLAS_TENSOR_OP_MATH);
        double ms_ex = run_gemmex(h, s, w16, a16, c, CUBLAS_GEMM_DEFAULT);
        cublasSetWorkspace(h, ws_small, WS_SMALL);
        LtBest lb = run_lt(lt, s, w16, a16, c2, ws_small, WS_SMALL);
        double ms_lt = (lb.ms > 0) ? lb.ms : ms_ex;
        double gf = 2.0 * s.M * s.N * s.K / 1e9;
        printf("%-9s %6d %12.2f %12.2f %9.1f %9.1f   id=%d tile=%d stages=%d splitK=%d nres=%d\n",
               s.role, s.M, ms_ex * 1000.0, ms_lt * 1000.0, gf / ms_ex, gf / ms_lt, lb.algo_id,
               lb.tile, lb.stages, lb.splitk, lb.nres);
        tot[mi][0] += ms_ex * 1000.0;
        tot[mi][1] += ms_lt * 1000.0;
        cublasDestroy(h);
        cudaFree(a16); cudaFree(w16); cudaFree(c); cudaFree(c2);
      }
    }
    printf("\n===== PER-LAYER TOTAL over the four projections, and the cost of covering 4096 rows "
           "=====\n");
    printf("  m      passes  per-layer us (ex / lt)     4096-row us (ex / lt)    28-layer ms (ex / lt)"
           "   vs 4x1024 (ex / lt)\n");
    double bex = tot[0][0] * 4, blt = tot[0][1] * 4;
    for (int mi = 0; mi < 3; mi++) {
      int passes = 4096 / MS[mi];
      double ex = tot[mi][0] * passes, ltv = tot[mi][1] * passes;
      printf("  %-6d %6d  %10.2f / %10.2f   %12.2f / %10.2f   %10.3f / %10.3f   %+8.2f / %+8.2f\n",
             MS[mi], passes, tot[mi][0], tot[mi][1], ex, ltv, ex * 28 / 1000.0, ltv * 28 / 1000.0,
             ex - bex, ltv - blt);
    }
    printf("  (nsys measured the shipped 4x1024 RAG-4096 cublas family at 226.048 ms per prefill;"
           " this probe's ex_ws0 4x1024 total is %.3f ms)\n", bex * 28 / 1000.0);
    printf("MSWEEP_DONE\n");
    return 0;
  }

  double base_layer = 0.0;   // shipped per-layer-chunk total
  double best_layer = 0.0;   // best achievable per-layer-chunk total
  printf("%-9s %-9s %10s %9s %8s %8s   %s\n", "role", "arm", "us", "TF/s", "%peak", "vs_ship",
         "note");
  for (int si = 0; si < NSHAPE; si++) {
    const Shape& s = SHAPES[si];
    if (!only.empty() && std::string(s.role).find(only) == std::string::npos) continue;
    size_t na = (size_t)s.M * s.K, nw = (size_t)s.N * s.K;
    size_t nc = (size_t)s.M * s.N;
    size_t csz = s.c_f16 ? sizeof(__half) : sizeof(float);
    __half *a16 = nullptr, *w16 = nullptr;
    void* c = nullptr;
    CK(cudaMalloc(&a16, na * sizeof(__half)));
    CK(cudaMalloc(&w16, nw * sizeof(__half)));
    CK(cudaMalloc(&c, nc * csz));
    // deterministic pseudo-random fill: the same bits every arm sees, so a diff is the
    // algorithm's reduction order and not the data
    {
      std::vector<__half> ha(na), hw(nw);
      unsigned st = 12345u + si;
      auto nx = [&]() { st = st * 1664525u + 1013904223u; return (st >> 8) & 0xFFFF; };
      for (size_t i = 0; i < na; i++) ha[i] = __float2half(((nx() % 2001) - 1000) / 5000.0f);
      for (size_t i = 0; i < nw; i++) hw[i] = __float2half(((nx() % 2001) - 1000) / 5000.0f);
      CK(cudaMemcpy(a16, ha.data(), na * sizeof(__half), cudaMemcpyHostToDevice));
      CK(cudaMemcpy(w16, hw.data(), nw * sizeof(__half), cudaMemcpyHostToDevice));
      CK(cudaMemset(c, 0, nc * csz));
    }
    double gflop = 2.0 * s.M * s.N * s.K / 1e9;
    printf("\n== %s  M=%d N=%d K=%d  C=%s  beta=%d  %.2f GFLOP  out_tiles(128x128)=%d = %.2f "
           "waves on %d SMs\n",
           s.role, s.M, s.N, s.K, s.c_f16 ? "f16" : "f32", s.accumulate ? 1 : 0, gflop,
           ((s.M + 127) / 128) * ((s.N + 127) / 128),
           (double)(((s.M + 127) / 128) * ((s.N + 127) / 128)) / prop.multiProcessorCount,
           prop.multiProcessorCount);

    // A FRESH handle per shape, so the shipped baseline can never inherit a workspace set by a
    // previous shape's arm (cublasSetWorkspace(h, nullptr, 0) is not a documented reset, and a
    // silent failure there would mislabel a 256 MB run as the no-workspace baseline).
    cublasHandle_t h = nullptr;
    if (cublasCreate(&h) != CUBLAS_STATUS_SUCCESS) { printf("cublasCreate FAIL\n"); return 1; }
    cublasSetStream(h, 0);                       // the shipped NOSEAM path uses the legacy stream
    cublasSetMathMode(h, CUBLAS_TENSOR_OP_MATH); // tc_shim_init does exactly this

    // reference: the shipped path, one call on a zeroed C (so a beta=1 role's reference is a
    // single accumulate, comparable to one call of any other arm)
    double ms_base = run_gemmex(h, s, w16, a16, c, CUBLAS_GEMM_DEFAULT);
    CK(cudaMemset(c, 0, nc * csz));
    {
      float alpha = 1.0f, beta = s.accumulate ? 1.0f : 0.0f;
      CB(cublasGemmEx(h, CUBLAS_OP_T, CUBLAS_OP_N, s.N, s.M, s.K, &alpha, w16, CUDA_R_16F, s.K,
                      a16, CUDA_R_16F, s.K, &beta, c, s.c_f16 ? CUDA_R_16F : CUDA_R_32F, s.N,
                      CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT));
      CK(cudaStreamSynchronize(0));
    }
    std::vector<char> ref(nc * csz);
    CK(cudaMemcpy(ref.data(), c, ref.size(), cudaMemcpyDeviceToHost));

    struct Row { const char* arm; double ms; std::string note; };
    std::vector<Row> rows;
    rows.push_back({"ex_ws0", ms_base, "SHIPPED: GemmEx DEFAULT, no explicit workspace"});

    void* c2 = nullptr;
    CK(cudaMalloc(&c2, nc * csz));
    cublasSetWorkspace(h, ws_small, WS_SMALL);
    double m1 = run_gemmex(h, s, w16, a16, c2, CUBLAS_GEMM_DEFAULT);
    rows.push_back({"ex_ws32", m1, "GemmEx DEFAULT + cublasSetWorkspace(32 MB)"});
    cublasSetWorkspace(h, ws_big, WS_BIG);
    double m2 = run_gemmex(h, s, w16, a16, c2, CUBLAS_GEMM_DEFAULT);
    rows.push_back({"ex_ws256", m2, "GemmEx DEFAULT + cublasSetWorkspace(256 MB)"});
    double m3 = run_gemmex(h, s, w16, a16, c2, CUBLAS_GEMM_DEFAULT_TENSOR_OP);
    rows.push_back({"ex_top", m3, "GemmEx DEFAULT_TENSOR_OP @256 MB workspace"});

    LtBest l32 = run_lt(lt, s, w16, a16, c2, ws_small, WS_SMALL);
    char nb[224];
    snprintf(nb, sizeof(nb), "lt best of %d heuristics @32MB: id=%d tile=%d stages=%d splitK=%d red=%d swiz=%d",
             l32.nres, l32.algo_id, l32.tile, l32.stages, l32.splitk, l32.red, l32.swiz);
    rows.push_back({"lt_ws32", l32.ms, nb});
    LtBest l256 = run_lt(lt, s, w16, a16, c2, ws_big, WS_BIG);
    snprintf(nb, sizeof(nb), "lt best of %d heuristics @256MB: id=%d tile=%d stages=%d splitK=%d red=%d swiz=%d",
             l256.nres, l256.algo_id, l256.tile, l256.stages, l256.splitk, l256.red, l256.swiz);
    rows.push_back({"lt_ws256", l256.ms, nb});

    double best_ms = ms_base;
    const char* best_arm = "ex_ws0";
    for (auto& r : rows) {
      if (r.ms < 0) { printf("%-9s %-9s %10s %9s %8s %8s   %s\n", s.role, r.arm, "FAIL", "-", "-", "-", r.note.c_str()); continue; }
      double us = r.ms * 1000.0, tf = gflop / r.ms;   // GFLOP / ms == TFLOP/s
      printf("%-9s %-9s %10.2f %9.1f %7.1f%% %+7.1f%%   %s\n", s.role, r.arm, us, tf,
             100.0 * tf / A100_F16_TC_PEAK, 100.0 * (ms_base - r.ms) / ms_base, r.note.c_str());
      if (r.ms < best_ms) { best_ms = r.ms; best_arm = r.arm; }
    }

    // max-abs element diff of the winning cublasLt algo against the shipped single-call result.
    // ONE call on a zeroed C per side, so a beta=1 role is not compared after 25 accumulates.
    double maxabs = 0.0, maxrel = 0.0;
    if (l256.idx >= 0) {
      CK(cudaMemset(c2, 0, nc * csz));
      float alpha = 1.0f, beta = s.accumulate ? 1.0f : 0.0f;
      cublasLtMatmulDesc_t op = nullptr;
      cublasLtMatmulDescCreate(&op, CUBLAS_COMPUTE_32F, CUDA_R_32F);
      cublasOperation_t ta = CUBLAS_OP_T, tb = CUBLAS_OP_N;
      cublasLtMatmulDescSetAttribute(op, CUBLASLT_MATMUL_DESC_TRANSA, &ta, sizeof(ta));
      cublasLtMatmulDescSetAttribute(op, CUBLASLT_MATMUL_DESC_TRANSB, &tb, sizeof(tb));
      cublasLtMatrixLayout_t La, Lb, Lc;
      cublasLtMatrixLayoutCreate(&La, CUDA_R_16F, s.K, s.N, s.K);
      cublasLtMatrixLayoutCreate(&Lb, CUDA_R_16F, s.K, s.M, s.K);
      cublasLtMatrixLayoutCreate(&Lc, s.c_f16 ? CUDA_R_16F : CUDA_R_32F, s.N, s.M, s.N);
      cublasStatus_t st = cublasLtMatmul(lt, op, &alpha, w16, La, a16, Lb, &beta, c2, Lc, c2, Lc,
                                         &l256.algo, ws_big, WS_BIG, 0);
      CK(cudaStreamSynchronize(0));
      std::vector<char> got(nc * csz);
      CK(cudaMemcpy(got.data(), c2, got.size(), cudaMemcpyDeviceToHost));
      if (st == CUBLAS_STATUS_SUCCESS) {
        for (size_t i = 0; i < nc; i++) {
          double p, q;
          if (s.c_f16) { p = __half2float(((const __half*)ref.data())[i]);
                         q = __half2float(((const __half*)got.data())[i]); }
          else { p = ((const float*)ref.data())[i]; q = ((const float*)got.data())[i]; }
          double d = fabs(p - q);
          if (d > maxabs) maxabs = d;
          double rl = d / (fabs(p) > 1e-30 ? fabs(p) : 1.0);
          if (rl > maxrel) maxrel = rl;
        }
      } else { maxabs = -1.0; }
      cublasLtMatrixLayoutDestroy(La); cublasLtMatrixLayoutDestroy(Lb);
      cublasLtMatrixLayoutDestroy(Lc); cublasLtMatmulDescDestroy(op);
    }
    printf("%-9s %-9s  best=%s  max_abs_diff=%.6g  max_rel_diff=%.6g  (lt@256MB single call vs "
           "shipped single call)\n", s.role, "diff", best_arm, maxabs, maxrel);

    base_layer += ms_base * 1000.0;
    best_layer += best_ms * 1000.0;
    cublasDestroy(h);
    cudaFree(a16); cudaFree(w16); cudaFree(c); cudaFree(c2);
  }

  printf("\n================ PER-LAYER-CHUNK TOTAL (the four projections at m=1024) ================\n");
  printf("  shipped (ex_ws0)      : %9.2f us\n", base_layer);
  printf("  best arm per role     : %9.2f us   (%+.2f us, %+.2f%%)\n", best_layer,
         best_layer - base_layer, 100.0 * (best_layer - base_layer) / base_layer);
  printf("  x 112 layer-chunks (a RAG-4096 prefill = 4 chunks x 28 layers):\n");
  printf("  shipped               : %9.3f ms   (nsys measured 226.048 ms for the cublas family)\n",
         base_layer * 112 / 1000.0);
  printf("  best arm per role     : %9.3f ms   -> RAG-4096 saving %.3f ms\n",
         best_layer * 112 / 1000.0, (base_layer - best_layer) * 112 / 1000.0);
  printf("  the gap to flip is 12.639 ms of wall (284.805 vs TRT-LLM's 272.166)\n");
  printf("GEMM_PROBE_DONE\n");
  return 0;
}
