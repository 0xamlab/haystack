/* submission_fixed_vs_marginal_probe.m -- the fixed-vs-marginal decomposition the lever-recomputation
 * task (2026-08-03) asks for: "reuse the prior investigation's own fixed-vs-marginal decomposition
 * methodology" for lever 2's ceiling (a persistent multi-token loop amortizes only the FIXED
 * per-command-buffer component, not the per-dispatch marginal component). No prior artifact in this
 * repository isolates that split numerically (`submit_floor_batch.mojo` and its deep-table sibling
 * both report ONE (n_dispatches, time) point each and divide -- a single point cannot distinguish a
 * true per-dispatch rate from an intercept-plus-slope shape). This probe varies N directly and fits
 * time_us = fixed_us + marginal_us_per_dispatch * N by ordinary least squares, using the SAME
 * one-command-buffer/one-encoder/one-commit/one-waitUntilCompleted submission shape `batch_shim.m`'s
 * own `algenta_run_token` uses (same `setBytes`-address-style scalar arg per dispatch, same
 * `useResource:` residency declaration, same trivial 1-threadgroup/32-thread grid so GPU EXECUTION
 * time is negligible at every N -- only the HOST-side submission cost is being measured).
 *
 * `fixed_us` (the intercept) is the ONE-TIME cost `commandBuffer`/`commit`/`waitUntilCompleted`
 * plus encoder creation/`endEncoding` impose regardless of how many dispatches sit between them --
 * exactly the component a persistent multi-token loop (lever 2) would amortize across N tokens'
 * worth of dispatches instead of paying once per token. `marginal_us_per_dispatch` (the slope) is the
 * per-dispatch encoding cost (`setComputePipelineState`/`setBytes`-per-arg/`dispatchThreadgroups`) --
 * this does NOT shrink under lever 2, since the total number of dispatches encoded for N tokens is
 * unchanged (still `N * n_descriptors_per_token`) whether they are split across N separate command
 * buffers or concatenated into one.
 *
 *     clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *         submission_fixed_vs_marginal_probe.m -o /tmp/submission_fixed_vs_marginal_probe
 *     /tmp/submission_fixed_vs_marginal_probe
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static const char *kShaderSource =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "kernel void noop_kernel(constant uint64_t &addr [[buffer(0)]],\n"
    "                        constant int64_t &scalar_a [[buffer(1)]],\n"
    "                        constant float &scalar_b [[buffer(2)]],\n"
    "                        uint tid [[thread_position_in_grid]]) {\n"
    "    device int *p = (device int *)addr;\n"
    "    if (tid == 0xFFFFFFFFu) { p[0] = int(scalar_a) + int(scalar_b); }\n"  /* never taken; keeps
                                                                                   the args live so
                                                                                   the compiler can't
                                                                                   strip them */
    "}\n";

static double median_of(double *v, int n) {
    /* simple insertion sort, n is small (REPS=30) */
    for (int i = 1; i < n; i++) {
        double key = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > key) { v[j + 1] = v[j]; j--; }
        v[j + 1] = key;
    }
    return v[n / 2];
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "no Metal device\n"); return 1; }
        NSError *err = nil;
        id<MTLLibrary> lib = [device newLibraryWithSource:[NSString stringWithUTF8String:kShaderSource]
                                                    options:nil error:&err];
        if (!lib) { fprintf(stderr, "newLibraryWithSource failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"noop_kernel"];
        id<MTLComputePipelineState> pso = [device newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) { fprintf(stderr, "pipeline failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLBuffer> buf = [device newBufferWithLength:sizeof(int32_t) options:MTLResourceStorageModeShared];
        uint64_t addr = buf.gpuAddress;
        int64_t scalar_a = 7;
        float scalar_b = 1.5f;

        int Ns[] = {1, 10, 25, 50, 100, 171, 199, 300, 400, 600, 800, 1200, 1600, 2400, 3200};
        int n_points = sizeof(Ns) / sizeof(Ns[0]);
        int REPS = 30;
        int WARMUP = 5;

        double sum_n = 0, sum_t = 0, sum_nn = 0, sum_nt = 0;
        int count = 0;

        printf("N_dispatches,median_us,us_per_dispatch\n");
        for (int pi = 0; pi < n_points; pi++) {
            int N = Ns[pi];
            double samples[64];
            for (int rep = 0; rep < WARMUP + REPS; rep++) {
                struct timespec t0, t1;
                clock_gettime(CLOCK_MONOTONIC, &t0);
                id<MTLCommandBuffer> cb = [queue commandBuffer];
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc useResource:buf usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
                for (int d = 0; d < N; d++) {
                    [enc setComputePipelineState:pso];
                    [enc setBytes:&addr length:sizeof(addr) atIndex:0];
                    [enc setBytes:&scalar_a length:sizeof(scalar_a) atIndex:1];
                    [enc setBytes:&scalar_b length:sizeof(scalar_b) atIndex:2];
                    [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
                }
                [enc endEncoding];
                [cb commit];
                [cb waitUntilCompleted];
                clock_gettime(CLOCK_MONOTONIC, &t1);
                if (cb.status != MTLCommandBufferStatusCompleted) {
                    fprintf(stderr, "N=%d rep=%d: command buffer failed, status=%ld\n", N, rep, (long)cb.status);
                    return 1;
                }
                if (rep >= WARMUP) {
                    double us = (t1.tv_sec - t0.tv_sec) * 1e6 + (t1.tv_nsec - t0.tv_nsec) / 1e3;
                    samples[rep - WARMUP] = us;
                }
            }
            double med = median_of(samples, REPS);
            printf("%d,%.1f,%.4f\n", N, med, med / N);
            sum_n += N; sum_t += med; sum_nn += (double)N * N; sum_nt += (double)N * med;
            count++;
        }

        /* ordinary least squares: time_us = fixed_us + marginal_us_per_dispatch * N */
        double mean_n = sum_n / count;
        double mean_t = sum_t / count;
        double cov_nt = sum_nt / count - mean_n * mean_t;
        double var_n = sum_nn / count - mean_n * mean_n;
        double marginal = cov_nt / var_n;
        double fixed = mean_t - marginal * mean_n;

        printf("\n=== OLS fit: time_us = fixed_us + marginal_us_per_dispatch * N ===\n");
        printf("fixed_us (per-command-buffer, ONE-TIME cost): %.2f us\n", fixed);
        printf("marginal_us_per_dispatch (per-dispatch encode cost): %.4f us\n", marginal);
        printf("(sanity: at N=199, fit predicts %.1f us; N=171 predicts %.1f us)\n",
               fixed + marginal * 199.0, fixed + marginal * 171.0);
        return 0;
    }
}
