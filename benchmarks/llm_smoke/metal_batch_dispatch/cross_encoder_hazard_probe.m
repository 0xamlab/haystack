/* cross_encoder_hazard_probe.m -- a minimal, standalone, real-Metal-device probe answering the ONE
 * question the lever-2 (persistent multi-token decode loop) ceiling recomputation task (2026-08-03)
 * flagged as its single most safety-critical open question: does a buffer WRITTEN by one
 * MTLComputeCommandEncoder get correctly, deterministically read by a LATER MTLComputeCommandEncoder
 * in the SAME MTLCommandBuffer, submitted once (one commit, one waitUntilCompleted) -- the exact
 * shape lever 2 would need for a GPU-resident argmax-token-id -> next-step-embedding-lookup handoff,
 * without a host round trip in between?
 *
 * This is deliberately NOT a Mojo probe and does NOT touch any Mojo-compiled `.metallib` bytes --
 * `submit_floor_batch.mojo`'s own sibling investigation (`REALRACE_RESULTS.md`, "Raw-Metal dispatch
 * addendum") already found that loading MOJO's OWN compiled kernel bytes through the public
 * `newLibraryWithData:` path silently drops buffer WRITES (Metal's optimizer dead-code-eliminates a
 * store against a binding Mojo's codegen marks read-only). Compiling ordinary MSL SOURCE via the
 * fully public, synchronous `newLibraryWithSource:options:error:` is a DIFFERENT code path (no Mojo
 * codegen involved at all) and has no such bug reported anywhere in this codebase's history -- this
 * probe uses exactly that path, so its result speaks to Metal's own documented hazard-tracking
 * contract, not to any Mojo-specific quirk.
 *
 * Grounding for what this probe checks, from Apple's own current documentation (fetched fresh, this
 * task, 2026-08-03): "The Metal framework automatically synchronizes resource access conflicts for
 * the commands you submit to an MTLCommandQueue instance" (developer.apple.com/documentation/metal/
 * resource-synchronization), for resources with `hazardTrackingMode == .tracked` (the DEFAULT for an
 * ordinary `newBufferWithLength:options:` allocation -- never a heap sub-allocation, never explicitly
 * marked `.untracked`, exactly what this probe and `batch_shim.m`'s own `algenta_alloc_buffer` both
 * use) that are declared to each participating encoder -- either bound directly as an argument, or
 * via `useResource:usage:`, which that same site's own `MTLComputeCommandEncoder.useResource(_:usage:)`
 * reference page states IS how "you inform Metal when to apply hazard tracking for a resource you
 * create with `.tracked`." An "access conflict," per that same page, is "when one or more of
 * [the commands accessing a resource] has a memory write... and at least one other command has a
 * memory read" -- exactly the write-then-read shape this probe builds. This probe turns that
 * documentation-grounded expectation into a real, run-on-this-machine, pass/fail measurement rather
 * than trusting the doc text alone -- matching this whole chain's own standing "verify, don't assume"
 * discipline (see this task's own phase-1 correctness requirement).
 *
 * Design: ONE command buffer, TWO SEPARATE MTLComputeCommandEncoder objects (encoder A ends via
 * `endEncoding` BEFORE encoder B is created -- never concurrently open, matching the documented
 * "only one encoder active at a time" rule), sharing ONE small MTLBuffer (`shared`, 2 x int32,
 * storage mode Shared, default -- i.e. TRACKED -- hazard tracking, no heap involved):
 *   - Encoder A dispatches `write_kernel` (1 thread): shared[0] = 42.
 *   - Encoder A ends. Encoder B begins (new object).
 *   - Encoder B dispatches `read_then_copy_kernel` (1 thread): shared[1] = shared[0] + 1.
 *   - Encoder B ends. ONE commit, ONE waitUntilCompleted (host round-trip cost: one submission, same
 *     as today's single-encoder-per-token design -- this probe's OWN cost is not the point; only the
 *     VALUE at shared[1] is).
 * Both encoders call `useResource:usage:(Read|Write)` on `shared` before dispatching, exactly
 * replicating `batch_shim.m`'s own per-encoder residency-declaration discipline. Repeated 1000 times
 * (fresh buffer state each iteration) to rule out a one-off race. PASS iff shared[1] == 43 in every
 * iteration; any other observed value (most likely 1, if encoder B's read raced ahead of encoder A's
 * write and saw the buffer's zero-initialized state) is a clean, unambiguous FAIL.
 *
 *     clang -fobjc-arc -O2 -framework Metal -framework Foundation \
 *         cross_encoder_hazard_probe.m -o /tmp/cross_encoder_hazard_probe
 *     /tmp/cross_encoder_hazard_probe
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static const char *kShaderSource =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "kernel void write_kernel(device int *shared [[buffer(0)]],\n"
    "                         uint tid [[thread_position_in_grid]]) {\n"
    "    shared[0] = 42;\n"
    "}\n"
    "kernel void read_then_copy_kernel(device int *shared [[buffer(0)]],\n"
    "                                  uint tid [[thread_position_in_grid]]) {\n"
    "    shared[1] = shared[0] + 1;\n"
    "}\n";

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) {
            fprintf(stderr, "no Metal device\n");
            return 1;
        }
        printf("device: %s\n", device.name.UTF8String);

        NSError *err = nil;
        id<MTLLibrary> lib = [device newLibraryWithSource:[NSString stringWithUTF8String:kShaderSource]
                                                    options:nil
                                                      error:&err];
        if (!lib) {
            fprintf(stderr, "newLibraryWithSource failed: %s\n", err.description.UTF8String);
            return 1;
        }
        id<MTLFunction> writeFn = [lib newFunctionWithName:@"write_kernel"];
        id<MTLFunction> readFn = [lib newFunctionWithName:@"read_then_copy_kernel"];
        if (!writeFn || !readFn) {
            fprintf(stderr, "newFunctionWithName failed\n");
            return 1;
        }
        id<MTLComputePipelineState> writePSO = [device newComputePipelineStateWithFunction:writeFn error:&err];
        id<MTLComputePipelineState> readPSO = [device newComputePipelineStateWithFunction:readFn error:&err];
        if (!writePSO || !readPSO) {
            fprintf(stderr, "newComputePipelineStateWithFunction failed: %s\n", err.description.UTF8String);
            return 1;
        }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        int n_iters = 1000;
        int n_pass = 0;
        int n_fail = 0;
        int first_fail_value = -999;

        for (int iter = 0; iter < n_iters; iter++) {
            id<MTLBuffer> shared = [device newBufferWithLength:2 * sizeof(int32_t)
                                                        options:MTLResourceStorageModeShared];
            // confirm default hazard tracking mode is TRACKED, not untracked -- the precondition
            // the whole probe's grounding argument depends on. Checked every iteration, not assumed.
            if (shared.hazardTrackingMode != MTLHazardTrackingModeTracked) {
                fprintf(stderr, "iter %d: buffer hazardTrackingMode is NOT .tracked (got %ld) -- "
                        "probe's grounding assumption does not hold for this allocation, aborting\n",
                        iter, (long)shared.hazardTrackingMode);
                return 1;
            }
            int32_t *contents = (int32_t *)shared.contents;
            contents[0] = 0;
            contents[1] = 0;

            id<MTLCommandBuffer> cb = [queue commandBuffer];

            id<MTLComputeCommandEncoder> encA = [cb computeCommandEncoder];
            [encA useResource:shared usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
            [encA setComputePipelineState:writePSO];
            [encA setBuffer:shared offset:0 atIndex:0];
            [encA dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
            [encA endEncoding];   // encoder A fully ended before encoder B is created

            id<MTLComputeCommandEncoder> encB = [cb computeCommandEncoder];   // a NEW encoder object
            [encB useResource:shared usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
            [encB setComputePipelineState:readPSO];
            [encB setBuffer:shared offset:0 atIndex:0];
            [encB dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
            [encB endEncoding];

            [cb commit];
            [cb waitUntilCompleted];

            if (cb.status != MTLCommandBufferStatusCompleted || cb.error != nil) {
                fprintf(stderr, "iter %d: command buffer failed, status=%ld err=%s\n", iter,
                        (long)cb.status, cb.error ? cb.error.description.UTF8String : "none");
                return 1;
            }

            int32_t result = contents[1];
            if (result == 43) {
                n_pass++;
            } else {
                n_fail++;
                if (first_fail_value == -999) {
                    first_fail_value = result;
                }
            }
        }

        printf("iterations: %d   pass (shared[1]==43): %d   fail: %d", n_iters, n_pass, n_fail);
        if (n_fail > 0) {
            printf("   first observed failing value: %d", first_fail_value);
        }
        printf("\n");
        printf("%s\n", n_fail == 0
            ? "RESULT: PASS -- write-then-read across a NEW MTLComputeCommandEncoder in the SAME "
              "command buffer is correctly ordered, every iteration, with zero explicit MTLFence/"
              "MTLEvent -- matches the documented tracked-resource/MTLCommandQueue-scope contract."
            : "RESULT: FAIL -- cross-encoder ordering was NOT reliably correct without an explicit "
              "fence/event on this toolchain; lever 2 would need MTLFence between per-step encoders.");
        return n_fail == 0 ? 0 : 1;
    }
}
