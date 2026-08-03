/* cross_encoder_hazard_probe_chain_gpuaddr.m -- combines `cross_encoder_hazard_probe_chain.m`'s long
 * sequential-encoder chain with `cross_encoder_hazard_probe_gpuaddr.m`'s exact production argument-
 * binding ABI (gpuAddress via `setBytes`, kernel casts a `constant uint64_t &` to a device pointer) --
 * the most faithful single-buffer analog available, on this machine, to what lever 2 (persistent
 * multi-token decode loop) would need: many per-step encoders, chained in ONE command buffer, ONE
 * commit/wait, each one depending on the value the previous one wrote, using the SAME pointer-argument
 * convention `batch_shim.m`'s real per-token dispatches use today.
 *
 *     clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *         cross_encoder_hazard_probe_chain_gpuaddr.m -o /tmp/cross_encoder_hazard_probe_chain_gpuaddr
 *     /tmp/cross_encoder_hazard_probe_chain_gpuaddr
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static const char *kShaderSource =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "kernel void increment_kernel(constant uint64_t &addr [[buffer(0)]],\n"
    "                             uint tid [[thread_position_in_grid]]) {\n"
    "    device int *counter = (device int *)addr;\n"
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

        int n_steps = 199 * 8;   // same chain length as the setBuffer-ABI chain probe, for comparison
        int n_iters = 50;
        int n_pass = 0;

        for (int iter = 0; iter < n_iters; iter++) {
            id<MTLBuffer> counter = [device newBufferWithLength:sizeof(int32_t)
                                                          options:MTLResourceStorageModeShared];
            int32_t *contents = (int32_t *)counter.contents;
            contents[0] = 0;
            uint64_t addr = counter.gpuAddress;

            id<MTLCommandBuffer> cb = [queue commandBuffer];
            for (int step = 0; step < n_steps; step++) {
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc useResource:counter usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
                [enc setComputePipelineState:incPSO];
                [enc setBytes:&addr length:sizeof(addr) atIndex:0];
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
                fprintf(stderr, "iter %d: expected %d, got %d (lost %d increments)\n",
                        iter, n_steps, result, n_steps - result);
            }
        }
        printf("chain length: %d encoders/command buffer (gpuAddress ABI), %d iterations, pass: %d, fail: %d\n",
               n_steps, n_iters, n_pass, n_iters - n_pass);
        return n_pass == n_iters ? 0 : 1;
    }
}
