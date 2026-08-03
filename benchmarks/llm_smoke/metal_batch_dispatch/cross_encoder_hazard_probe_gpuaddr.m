/* cross_encoder_hazard_probe_gpuaddr.m -- the SAME two-encoder write-then-read check as
 * `cross_encoder_hazard_probe.m`, but using this codebase's OWN actual argument-binding ABI
 * (`batch_shim.m`'s documented recipe: a pointer argument is bound as the *value* of the buffer's
 * `gpuAddress`, via `setBytes:length:atIndex:`, NOT `setBuffer:offset:atIndex:`) instead of the
 * standard binding call the first probe used -- because `useResource:usage:` is specifically the
 * mechanism Metal provides for telling an encoder about a resource that is NOT bound through the
 * standard argument-table call, and this codebase's real kernels are bound exactly that way. Runs
 * TWO configurations back to back, as a genuine positive/negative control pair (not a test that can
 * only ever pass):
 *   MODE 1 (--with-useresource, the production pattern): both encoders call `useResource:usage:` on
 *     the shared buffer before dispatching, exactly matching `algenta_run_token`'s own per-encoder
 *     loop over every allocated buffer.
 *   MODE 2 (--without-useresource, the negative control): neither encoder declares the buffer via
 *     `useResource:` at all -- if this mode reliably PASSES too, that would mean this specific
 *     GPU/driver just always happens to order things correctly regardless, weakening confidence that
 *     `useResource:` is the operative mechanism; if it reliably FAILS or is flaky, that confirms the
 *     probe methodology can actually detect a real ordering break, so MODE 1's clean pass is
 *     meaningful evidence, not a tautology.
 *
 *     clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *         cross_encoder_hazard_probe_gpuaddr.m -o /tmp/cross_encoder_hazard_probe_gpuaddr
 *     /tmp/cross_encoder_hazard_probe_gpuaddr --with-useresource
 *     /tmp/cross_encoder_hazard_probe_gpuaddr --without-useresource
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <string.h>

/* Kernel arguments declared as a raw 64-bit scalar (`constant uint64_t &`) and cast to a device
 * pointer INSIDE the kernel body -- this, not a standard `device int * [[buffer(0)]]` parameter, is
 * the shape that actually accepts a `setBytes:`-supplied raw address at that argument index (a
 * standard typed-pointer parameter expects a genuine `setBuffer:` binding and silently does not see
 * a `setBytes`-supplied address the same way -- confirmed by this file's own first version, which
 * used the wrong shape and failed identically in both the with- and without-useResource modes for
 * that unrelated reason, not a hazard-tracking one; see the module docstring's revision note). */
static const char *kShaderSource =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "kernel void write_kernel(constant uint64_t &addr [[buffer(0)]],\n"
    "                         uint tid [[thread_position_in_grid]]) {\n"
    "    device int *shared = (device int *)addr;\n"
    "    shared[0] = 42;\n"
    "}\n"
    "kernel void read_then_copy_kernel(constant uint64_t &addr [[buffer(0)]],\n"
    "                                  uint tid [[thread_position_in_grid]]) {\n"
    "    device int *shared = (device int *)addr;\n"
    "    shared[1] = shared[0] + 1;\n"
    "}\n";

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        int use_resource = 1;
        if (argc > 1 && strcmp(argv[1], "--without-useresource") == 0) {
            use_resource = 0;
        }
        printf("mode: %s\n", use_resource ? "WITH useResource:" : "WITHOUT useResource:");

        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "no Metal device\n"); return 1; }

        NSError *err = nil;
        id<MTLLibrary> lib = [device newLibraryWithSource:[NSString stringWithUTF8String:kShaderSource]
                                                    options:nil error:&err];
        if (!lib) { fprintf(stderr, "newLibraryWithSource failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLFunction> writeFn = [lib newFunctionWithName:@"write_kernel"];
        id<MTLFunction> readFn = [lib newFunctionWithName:@"read_then_copy_kernel"];
        id<MTLComputePipelineState> writePSO = [device newComputePipelineStateWithFunction:writeFn error:&err];
        id<MTLComputePipelineState> readPSO = [device newComputePipelineStateWithFunction:readFn error:&err];
        if (!writePSO || !readPSO) { fprintf(stderr, "pipeline failed: %s\n", err.description.UTF8String); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        int n_iters = 1000;
        int n_pass = 0, n_fail = 0, first_fail_value = -999;

        for (int iter = 0; iter < n_iters; iter++) {
            id<MTLBuffer> shared = [device newBufferWithLength:2 * sizeof(int32_t)
                                                        options:MTLResourceStorageModeShared];
            int32_t *contents = (int32_t *)shared.contents;
            contents[0] = 0;
            contents[1] = 0;
            uint64_t addr = shared.gpuAddress;

            id<MTLCommandBuffer> cb = [queue commandBuffer];

            id<MTLComputeCommandEncoder> encA = [cb computeCommandEncoder];
            if (use_resource) {
                [encA useResource:shared usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
            }
            [encA setComputePipelineState:writePSO];
            [encA setBytes:&addr length:sizeof(addr) atIndex:0];   // gpuAddress-as-scalar, NOT setBuffer
            [encA dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
            [encA endEncoding];

            id<MTLComputeCommandEncoder> encB = [cb computeCommandEncoder];
            if (use_resource) {
                [encB useResource:shared usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
            }
            [encB setComputePipelineState:readPSO];
            [encB setBytes:&addr length:sizeof(addr) atIndex:0];
            [encB dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
            [encB endEncoding];

            [cb commit];
            [cb waitUntilCompleted];

            if (cb.status != MTLCommandBufferStatusCompleted || cb.error != nil) {
                fprintf(stderr, "iter %d: command buffer failed, status=%ld err=%s\n", iter,
                        (long)cb.status, cb.error ? cb.error.description.UTF8String : "none");
                continue;
            }
            int32_t result = contents[1];
            if (result == 43) {
                n_pass++;
            } else {
                n_fail++;
                if (first_fail_value == -999) first_fail_value = result;
            }
        }
        printf("iterations: %d   pass: %d   fail: %d", n_iters, n_pass, n_fail);
        if (n_fail > 0) printf("   first failing value: %d", first_fail_value);
        printf("\n");
        return n_fail == 0 ? 0 : 1;
    }
}
