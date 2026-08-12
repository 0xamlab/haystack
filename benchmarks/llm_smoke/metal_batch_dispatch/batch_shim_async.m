/* batch_shim_async.m -- commit/wait-SPLIT sibling of `batch_shim_gputime.m`, built for exactly one
 * experiment (REALRACE_RESULTS.md "Gate 0, MECHANISM RESOLVED" entry's pre-registered next step):
 * the DUAL-STREAM concurrency test -- can TWO batched GEMM streams run CONCURRENTLY on the GPU,
 * and does aggregate throughput rise above a single dense stream? `batch_shim.m`/`batch_shim_gputime.m`
 * cannot answer this: their `algenta_run_token(_gt)` commits AND waits inside one call, so two
 * streams would serialize by construction. This file splits the same encode path into
 *
 *     int64_t algenta_commit_token_as(const AlgentaDispatchDescAS *descriptors, int64_t n);
 *         -- encode n dispatches onto ONE fresh command buffer from the session queue and COMMIT
 *            it (no wait); stores the live command buffer in a pending slot; returns the slot
 *            index (>= 0) or -1 on failure;
 *     int64_t algenta_wait_token_as(int64_t slot, double *out_gpu_ms,
 *                                   double *out_start_s, double *out_end_s);
 *         -- waitUntilCompleted on the slot's command buffer, verify status, write the buffer's
 *            whole-batch GPU-only duration (ms) plus its raw GPUStartTime/GPUEndTime (seconds,
 *            Mach-derived epoch, only comparable WITHIN this process) so the caller can compute
 *            the two-stream overlap span = max(end)-min(start); releases the slot; 0 or -1.
 *
 * Committing stream A and stream B back-to-back (two `algenta_commit_token_as` calls before any
 * wait) puts BOTH command buffers in flight on the same MTLCommandQueue -- Metal explicitly allows
 * multiple outstanding command buffers per queue, and the AGX scheduler runs them concurrently
 * when resources permit. That is exactly the configuration under test. Everything else is
 * byte-for-byte `batch_shim_gputime.m`'s recipe: same ABI (pointer args as gpuAddress values via
 * setBytes, `useResource:` once per encoder for every allocated buffer, Int args 8 bytes, Float32
 * args 4 bytes), same embedded-metallib discovery, same buffer storage mode. Every exported name
 * carries the `_as` suffix so this object file can link alongside `batch_shim.o`/`batch_shim_gputime.o`
 * without symbol collisions (not required by the dual-stream probe, which links this file ALONE,
 * but kept as safety margin). `AlgentaDispatchDescAS`/`AlgentaArgAS` are byte-for-byte the same
 * layout as `batch_shim.m`'s, so `metaldispatch.ffi`'s unmodified descriptor helpers build
 * descriptors this file reads correctly.
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <dispatch/dispatch.h>
#include <mach-o/dyld.h>
#include <mach-o/getsect.h>
#include <stdint.h>
#include <string.h>

#define ALGENTA_AS_MAX_ARGS 16
#define ALGENTA_AS_MAX_PIPELINES 32
#define ALGENTA_AS_MAX_BUFFERS 512
#define ALGENTA_AS_MAX_PENDING 8

typedef struct {
    int32_t tag;       /* 0 = buffer device-address value, 1 = int64 scalar, 2 = float32 scalar */
    int32_t reserved;
    uint64_t value;
} AlgentaArgAS;

typedef struct {
    int32_t pipeline_idx;
    int32_t grid_x;      /* threadgroup count */
    int32_t threads_x;   /* threads per threadgroup */
    int32_t num_args;
    AlgentaArgAS args[ALGENTA_AS_MAX_ARGS];
} AlgentaDispatchDescAS;

static id<MTLDevice> g_device_as = nil;
static id<MTLCommandQueue> g_queue_as = nil;
static id<MTLComputePipelineState> g_pipelines_as[ALGENTA_AS_MAX_PIPELINES];
static NSString *g_pipeline_names_as[ALGENTA_AS_MAX_PIPELINES];
static int32_t g_pipeline_count_as = 0;
static id<MTLBuffer> g_buffers_as[ALGENTA_AS_MAX_BUFFERS];
static int32_t g_buffer_count_as = 0;
static id<MTLCommandBuffer> g_pending_as[ALGENTA_AS_MAX_PENDING];

static int64_t algenta_fail_as(NSString *msg) {
    fprintf(stderr, "algenta_batch_shim_async: %s\n", msg.UTF8String);
    return -1;
}

int64_t algenta_open_session_as(void) {
    @autoreleasepool {
        if (g_device_as != nil) {
            return g_pipeline_count_as; /* idempotent */
        }
        g_device_as = MTLCreateSystemDefaultDevice();
        if (!g_device_as) {
            return algenta_fail_as(@"MTLCreateSystemDefaultDevice returned nil");
        }
        g_queue_as = [g_device_as newCommandQueue];
        if (!g_queue_as) {
            return algenta_fail_as(@"newCommandQueue returned nil");
        }
        for (int32_t i = 0; i < ALGENTA_AS_MAX_PENDING; i++) g_pending_as[i] = nil;

        const struct mach_header *mh = _dyld_get_image_header(0);
        unsigned long sect_size = 0;
        const uint8_t *sect = getsectiondata(
            (const struct mach_header_64 *)mh, "__TEXT", "__const", &sect_size);
        if (!sect) {
            return algenta_fail_as(@"getsectiondata(__TEXT,__const) returned NULL");
        }

        size_t i = 0;
        while (i + 20 < sect_size && g_pipeline_count_as < ALGENTA_AS_MAX_PIPELINES) {
            if (sect[i] == 'M' && sect[i + 1] == 'T' && sect[i + 2] == 'L' && sect[i + 3] == 'B') {
                uint64_t declared_len = 0;
                memcpy(&declared_len, sect + i + 16, sizeof(declared_len));
                if (declared_len > 20 && i + declared_len <= sect_size) {
                    NSData *blob = [NSData dataWithBytesNoCopy:(void *)(sect + i)
                                                         length:(NSUInteger)declared_len
                                                   freeWhenDone:NO];
                    dispatch_data_t dd = dispatch_data_create(
                        blob.bytes, blob.length, NULL, DISPATCH_DATA_DESTRUCTOR_DEFAULT);
                    NSError *err = nil;
                    id<MTLLibrary> lib = [g_device_as newLibraryWithData:dd error:&err];
                    if (lib) {
                        NSArray<NSString *> *names = lib.functionNames;
                        if (names.count >= 1) {
                            id<MTLFunction> fn = [lib newFunctionWithName:names[0]];
                            if (fn) {
                                NSError *perr = nil;
                                id<MTLComputePipelineState> pso =
                                    [g_device_as newComputePipelineStateWithFunction:fn error:&perr];
                                if (pso) {
                                    g_pipelines_as[g_pipeline_count_as] = pso;
                                    g_pipeline_names_as[g_pipeline_count_as] = names[0];
                                    g_pipeline_count_as += 1;
                                }
                            }
                        }
                    }
                    i += (size_t)declared_len;
                    continue;
                }
            }
            i += 1;
        }
        return g_pipeline_count_as;
    }
}

int64_t algenta_pipeline_count_as(void) {
    return g_pipeline_count_as;
}

int64_t algenta_pipeline_name_as(int64_t idx, uint8_t *buf, int64_t buf_len) {
    @autoreleasepool {
        if (idx < 0 || idx >= g_pipeline_count_as || buf_len < 1) {
            return -1;
        }
        const char *cstr = g_pipeline_names_as[idx].UTF8String;
        int64_t n = (int64_t)strlen(cstr);
        int64_t to_copy = n < buf_len - 1 ? n : buf_len - 1;
        memcpy(buf, cstr, (size_t)to_copy);
        buf[to_copy] = 0;
        return to_copy;
    }
}

int64_t algenta_alloc_buffer_as(int64_t length_bytes, uint64_t *out_addr, uint8_t **out_contents) {
    @autoreleasepool {
        if (g_device_as == nil || g_buffer_count_as >= ALGENTA_AS_MAX_BUFFERS || length_bytes <= 0) {
            return -1;
        }
        id<MTLBuffer> buf = [g_device_as newBufferWithLength:(NSUInteger)length_bytes
                                                       options:MTLResourceStorageModeShared];
        if (!buf) {
            return algenta_fail_as(@"newBufferWithLength returned nil");
        }
        int32_t idx = g_buffer_count_as;
        g_buffers_as[idx] = buf;
        g_buffer_count_as += 1;
        *out_addr = buf.gpuAddress;
        *out_contents = (uint8_t *)buf.contents;
        return idx;
    }
}

/* Encode n dispatches onto one fresh command buffer and COMMIT without waiting. Returns the
 * pending slot (>= 0) or -1. The identical encode loop to batch_shim_gputime.m's
 * algenta_run_token_gt, minus the wait and the timing read. */
int64_t algenta_commit_token_as(const AlgentaDispatchDescAS *descriptors, int64_t n) {
    @autoreleasepool {
        if (g_queue_as == nil) {
            return algenta_fail_as(@"algenta_commit_token_as called before algenta_open_session_as");
        }
        int32_t slot = -1;
        for (int32_t i = 0; i < ALGENTA_AS_MAX_PENDING; i++) {
            if (g_pending_as[i] == nil) { slot = i; break; }
        }
        if (slot < 0) {
            return algenta_fail_as(@"no free pending command-buffer slot (all in flight)");
        }
        id<MTLCommandBuffer> cb = [g_queue_as commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];

        for (int32_t b = 0; b < g_buffer_count_as; b++) {
            [enc useResource:g_buffers_as[b] usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
        }

        for (int64_t d = 0; d < n; d++) {
            const AlgentaDispatchDescAS *desc = &descriptors[d];
            if (desc->pipeline_idx < 0 || desc->pipeline_idx >= g_pipeline_count_as) {
                return algenta_fail_as(@"dispatch descriptor named an out-of-range pipeline index");
            }
            [enc setComputePipelineState:g_pipelines_as[desc->pipeline_idx]];
            for (int32_t a = 0; a < desc->num_args; a++) {
                const AlgentaArgAS *arg = &desc->args[a];
                if (arg->tag == 0) {
                    uint64_t addr = arg->value;
                    [enc setBytes:&addr length:sizeof(addr) atIndex:(NSUInteger)a];
                } else if (arg->tag == 1) {
                    int64_t v = (int64_t)arg->value;
                    [enc setBytes:&v length:sizeof(v) atIndex:(NSUInteger)a];
                } else if (arg->tag == 2) {
                    float v;
                    uint32_t bits = (uint32_t)(arg->value & 0xFFFFFFFFu);
                    memcpy(&v, &bits, sizeof(v));
                    [enc setBytes:&v length:sizeof(v) atIndex:(NSUInteger)a];
                } else {
                    return algenta_fail_as(@"dispatch descriptor argument had an unknown tag");
                }
            }
            MTLSize groups = MTLSizeMake((NSUInteger)desc->grid_x, 1, 1);
            MTLSize threads = MTLSizeMake((NSUInteger)desc->threads_x, 1, 1);
            [enc dispatchThreadgroups:groups threadsPerThreadgroup:threads];
        }

        [enc endEncoding];
        [cb commit];
        g_pending_as[slot] = cb;
        return slot;
    }
}

/* Wait on a pending slot's command buffer; write its whole-batch GPU-only duration (ms) and its
 * raw GPUStartTime/GPUEndTime (seconds). Returns 0 on success, -1 on Metal-reported failure. */
int64_t algenta_wait_token_as(int64_t slot, double *out_gpu_ms,
                              double *out_start_s, double *out_end_s) {
    @autoreleasepool {
        if (slot < 0 || slot >= ALGENTA_AS_MAX_PENDING || g_pending_as[slot] == nil) {
            return algenta_fail_as(@"algenta_wait_token_as called with an empty/invalid slot");
        }
        id<MTLCommandBuffer> cb = g_pending_as[slot];
        [cb waitUntilCompleted];
        g_pending_as[slot] = nil;

        if (cb.status != MTLCommandBufferStatusCompleted || cb.error != nil) {
            fprintf(stderr, "algenta_batch_shim_async: command buffer failed, status=%ld err=%s\n",
                    (long)cb.status, cb.error ? cb.error.description.UTF8String : "none");
            return -1;
        }
        if (out_gpu_ms != NULL) {
            *out_gpu_ms = (cb.GPUEndTime - cb.GPUStartTime) * 1000.0;
        }
        if (out_start_s != NULL) {
            *out_start_s = cb.GPUStartTime;
        }
        if (out_end_s != NULL) {
            *out_end_s = cb.GPUEndTime;
        }
        return 0;
    }
}
