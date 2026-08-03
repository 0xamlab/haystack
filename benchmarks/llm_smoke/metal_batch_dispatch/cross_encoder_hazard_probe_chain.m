/* cross_encoder_hazard_probe_chain.m -- `cross_encoder_hazard_probe.m`'s own two-encoder check,
 * extended to a CHAIN of N sequential encoders in ONE command buffer, each one incrementing a
 * counter written by the encoder immediately before it -- a closer shape-match to what lever 2 (the
 * persistent, no-host-round-trip multi-token decode loop) would actually need: many decode STEPS,
 * each its own encoder (or set of encoders), chained back-to-back inside one submission, each
 * reading a value the previous step's own encoder wrote.
 *
 * PASS iff, after N encoders each doing `counter[0] += 1`, the final value is exactly N (any race
 * would either lose increments -- final value < N -- or, less likely, never manifest as a false
 * positive here since each step is a strict read-modify-write dependency on the one before it).
 *
 *     clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *         cross_encoder_hazard_probe_chain.m -o /tmp/cross_encoder_hazard_probe_chain
 *     /tmp/cross_encoder_hazard_probe_chain
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static const char *kShaderSource =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "kernel void increment_kernel(device int *counter [[buffer(0)]],\n"
    "                             uint tid [[thread_position_in_grid]]) {\n"
    "    counter[0] = counter[0] + 1;\n"
    "}\n";

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "no Metal device\n"); return 1; }

        NSError *err = nil;
        id<MTLLibrary> lib = [device newLibraryWithSource:[NSString stringWithUTF8String:kShaderSource]
                                                    options:nil error:&err];
        if (!lib) { fprintf(stderr, "newLibraryWithSource failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLFunction> incFn = [lib newFunctionWithName:@"increment_kernel"];
        id<MTLComputePipelineState> incPSO = [device newComputePipelineStateWithFunction:incFn error:&err];
        if (!incPSO) { fprintf(stderr, "pipeline failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        int n_steps = 199 * 8;   // 8 "tokens" worth of this session's own 199-dispatch deep table, as
                                  // one round-trip-count analogy -- not the real per-layer plan, just
                                  // a chain long enough to make a race statistically obvious if one exists.
        int n_iters = 50;
        int n_pass = 0;

        for (int iter = 0; iter < n_iters; iter++) {
            id<MTLBuffer> counter = [device newBufferWithLength:sizeof(int32_t)
                                                          options:MTLResourceStorageModeShared];
            int32_t *contents = (int32_t *)counter.contents;
            contents[0] = 0;

            id<MTLCommandBuffer> cb = [queue commandBuffer];
            for (int step = 0; step < n_steps; step++) {
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc useResource:counter usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
                [enc setComputePipelineState:incPSO];
                [enc setBuffer:counter offset:0 atIndex:0];
                [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
                [enc endEncoding];
            }
            [cb commit];
            [cb waitUntilCompleted];

            if (cb.status != MTLCommandBufferStatusCompleted || cb.error != nil) {
                fprintf(stderr, "iter %d: command buffer failed, status=%ld\n", iter, (long)cb.status);
                return 1;
            }
            int32_t result = contents[0];
            if (result == n_steps) {
                n_pass++;
            } else {
                fprintf(stderr, "iter %d: expected %d, got %d (lost %d increments -- a real race)\n",
                        iter, n_steps, result, n_steps - result);
            }
        }
        printf("chain length: %d encoders/command buffer, %d iterations, pass: %d, fail: %d\n",
               n_steps, n_iters, n_pass, n_iters - n_pass);
        printf("%s\n", n_pass == n_iters
            ? "RESULT: PASS -- a long chain of sequential per-step encoders in ONE command buffer, "
              "each depending on the one before it, is reliably, fully ordered with zero explicit "
              "fences."
            : "RESULT: FAIL -- lost increments somewhere in the chain; cross-encoder ordering is NOT "
              "reliable without an explicit fence on this toolchain.");
        return n_pass == n_iters ? 0 : 1;
    }
}
