/* useresource_cost_probe.m -- `algenta_run_token` (batch_shim.m) calls `useResource:usage:` ONCE PER
 * ALLOCATED BUFFER, every token, on its one encoder ("every buffer this session has ever allocated,
 * marked resident on the encoder... done ONCE per encoder for every buffer this session ever
 * allocated"). A real `_MBQwen3I8AllSimd7` session allocates roughly 409 buffers (14/layer * 28
 * layers + 5 globals + 9 shared activations + 3 split-K scratch, counted from `session.mojo`'s
 * `__init__`) -- this probe isolates THAT specific cost (separate from per-dispatch encoding cost,
 * which `submission_fixed_vs_marginal_probe.m` already isolates with only 1 buffer) by varying the
 * NUMBER OF BUFFERS declared via `useResource:` on ONE encoder, holding dispatch count fixed at 1.
 *
 * This matters for lever 2's ceiling specifically: this cost is paid ONCE PER ENCODER (Apple's own
 * `useResource(_:usage:)` contract), not once per command buffer and not once per dispatch. Today it
 * is paid once per TOKEN (one encoder per token). A persistent multi-token design built as "N
 * sequentially-encoded encoders, one per decode step" (this task's own background framing) would
 * still pay it N times -- NOT amortized. Only a design that keeps ONE continuous encoder open across
 * all N tokens' dispatches (never calling `endEncoding` until the whole batch is done) would amortize
 * this cost down to once per N tokens instead of once per token -- this probe's result is what tells
 * us whether that distinction is worth caring about at all.
 *
 *     clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *         useresource_cost_probe.m -o /tmp/useresource_cost_probe
 *     /tmp/useresource_cost_probe
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static const char *kShaderSource =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "kernel void noop_kernel(constant uint64_t &addr [[buffer(0)]], uint tid [[thread_position_in_grid]]) {\n"
    "    device int *p = (device int *)addr;\n"
    "    if (tid == 0xFFFFFFFFu) { p[0] = 1; }\n"
    "}\n";

static double median_of(double *v, int n) {
    for (int i = 1; i < n; i++) {
        double key = v[i]; int j = i - 1;
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
        id<MTLFunction> fn = [lib newFunctionWithName:@"noop_kernel"];
        id<MTLComputePipelineState> pso = [device newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) { fprintf(stderr, "pipeline failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        int Bs[] = {1, 10, 50, 100, 200, 409, 800};
        int n_points = sizeof(Bs) / sizeof(Bs[0]);
        int REPS = 30, WARMUP = 5;

        double sum_n = 0, sum_t = 0, sum_nn = 0, sum_nt = 0;
        int count = 0;

        printf("N_buffers,median_us,us_per_buffer\n");
        for (int pi = 0; pi < n_points; pi++) {
            int B = Bs[pi];
            /* allocate B distinct small buffers once, outside the timing loop */
            NSMutableArray<id<MTLBuffer>> *buffers = [NSMutableArray arrayWithCapacity:B];
            for (int i = 0; i < B; i++) {
                [buffers addObject:[device newBufferWithLength:64 options:MTLResourceStorageModeShared]];
            }
            uint64_t addr = ((id<MTLBuffer>)buffers[0]).gpuAddress;

            double samples[64];
            for (int rep = 0; rep < WARMUP + REPS; rep++) {
                struct timespec t0, t1;
                clock_gettime(CLOCK_MONOTONIC, &t0);
                id<MTLCommandBuffer> cb = [queue commandBuffer];
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                for (int i = 0; i < B; i++) {
                    [enc useResource:buffers[i] usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
                }
                [enc setComputePipelineState:pso];
                [enc setBytes:&addr length:sizeof(addr) atIndex:0];
                [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
                [enc endEncoding];
                [cb commit];
                [cb waitUntilCompleted];
                clock_gettime(CLOCK_MONOTONIC, &t1);
                if (cb.status != MTLCommandBufferStatusCompleted) {
                    fprintf(stderr, "B=%d rep=%d: command buffer failed\n", B, rep);
                    return 1;
                }
                if (rep >= WARMUP) {
                    samples[rep - WARMUP] = (t1.tv_sec - t0.tv_sec) * 1e6 + (t1.tv_nsec - t0.tv_nsec) / 1e3;
                }
            }
            double med = median_of(samples, REPS);
            printf("%d,%.1f,%.4f\n", B, med, med / B);
            sum_n += B; sum_t += med; sum_nn += (double)B * B; sum_nt += (double)B * med;
            count++;
        }
        double mean_n = sum_n / count, mean_t = sum_t / count;
        double cov_nt = sum_nt / count - mean_n * mean_t;
        double var_n = sum_nn / count - mean_n * mean_n;
        double marginal = cov_nt / var_n;
        double fixed = mean_t - marginal * mean_n;
        printf("\n=== OLS fit: time_us = fixed_us + marginal_us_per_buffer * N_buffers ===\n");
        printf("fixed_us (encoder/commandbuffer/commit/wait, B->0): %.2f us\n", fixed);
        printf("marginal_us_per_useResource_call: %.4f us\n", marginal);
        printf("(sanity: at B=409 (this session's real buffer count), fit predicts %.1f us)\n",
               fixed + marginal * 409.0);
        return 0;
    }
}
