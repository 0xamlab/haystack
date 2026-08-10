/* batch_shim_counters.m -- DIAGNOSTIC TWIN of `batch_shim.m`, for real per-dispatch GPU timing.
 *
 * Every function `batch_shim.m` exports is reproduced here byte-for-byte (same signatures, same
 * behavior) so `metaldispatch.session`'s existing `_MBQwen3I8` (session open, weight upload, buffer
 * allocation) works completely unchanged when linked against THIS object file instead of
 * `batch_shim.o` -- nothing about the production fast path is touched by this file's existence.
 * `qwen3_generate_batch_i8.mojo` (the production benchmark) never links this file, and this file
 * never touches `batch_shim.m`: the two are independent .o's built from independent .m sources, so
 * there is zero risk of this diagnostic work perturbing the measured 243.06 tok/s number.
 *
 * ADDED, beyond the twin surface: three exports that get REAL per-dispatch GPU-side timestamps
 * without a single CPU-side wait between dispatches, using Apple's public Metal counter-sampling
 * API (confirmed from the actual installed SDK headers on this machine -- Xcode 26.6.0,
 * `MacOSX.sdk/.../Metal.framework/Headers/{MTLCounters,MTLComputePass,MTLComputeCommandEncoder,
 * MTLDevice}.h` -- not from memory):
 *
 *   - `MTLDevice.counterSets` lists the counter sets a device exposes; this file picks the one
 *     named `MTLCommonCounterSetTimestamp` (a set containing only a GPU timestamp).
 *   - `[MTLDevice newCounterSampleBufferWithDescriptor:error:]` allocates an
 *     `id<MTLCounterSampleBuffer>` (Shared storage, so `resolveCounterRange:` can be read back on
 *     the CPU with no extra copy step) sized for every dispatch's start+end sample.
 *   - `id<MTLComputeCommandEncoder>`'s `sampleCountersInBuffer:atSampleIndex:withBarrier:` -- called
 *     TWICE per dispatch (immediately before `dispatchThreadgroups:` and immediately after), with
 *     `withBarrier:NO` -- appends a GPU-side "record the hardware timestamp counter here" command
 *     into the SAME encoder the dispatch itself is in. This is not a CPU/GPU sync point: it is
 *     ordinary encoder-command-stream content, scheduled and executed by the GPU exactly like the
 *     dispatch commands around it. `withBarrier:NO` (matching what Apple's own docs on this method
 *     recommend for "higher performance" sampling, accepting that back-to-back dispatches on
 *     Apple's own hardware may overlap slightly at a sample boundary) means the ONLY thing added to
 *     the command stream is more of the same kind of GPU-side command already in it -- no
 *     `waitUntilCompleted`, no additional command buffer, no additional commit.
 *   - `resolveCounterRange:` turns the opaque sample buffer into raw `MTLCounterResultTimestamp`
 *     values (one `uint64_t` tick count each). This file calls it exactly ONCE, AFTER this token's
 *     single `waitUntilCompleted` returns -- reading a buffer the GPU already finished writing
 *     during the batch, never a mid-batch resolve.
 *   - `MTLDevice.queryTimestampFrequency` (macOS 26+, confirmed present in this SDK's `MTLDevice.h`)
 *     gives ticks-per-second so a tick delta becomes nanoseconds without guessing a conversion
 *     factor.
 *
 * `algenta_run_token` itself (below) is reproduced completely unmodified from `batch_shim.m` --
 * the diagnostic path is `algenta_run_token_counters`, a SEPARATE function, so a caller that never
 * calls it pays literally nothing extra (dead code in this .o, never invoked).
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <dispatch/dispatch.h>
#import <IOKit/IOKitLib.h>
#include <mach-o/dyld.h>
#include <mach-o/getsect.h>
#include <stdint.h>
#include <string.h>

#define ALGENTA_MAX_ARGS 16
/* Beat-llama.cpp campaign (2026-08-08 night): bumped 32 -> 64, mirroring `batch_shim.m`'s own
 * same-night bump and for the same measured reason -- the campaign's counter probes now link the
 * kvprod_v2 blob (two more metallibs) on top of the MSL/vecload4/AF set, ~36 MTLBs total, over
 * the old cap; the overflow is silent (the scan stops at the cap). */
#define ALGENTA_MAX_PIPELINES 64
/* Phase 3 (2026-08-08): bumped 512 -> 2048 to match `batch_shim.m`'s own earlier bump (its comment
 * is the full account). The MSL-parity arm materializes FOUR extra per-layer Float16 weight buffers
 * (28 layers x 4 = 112 extra buffers) on top of the ~469 the vecload4 counter probe already
 * allocated, which crossed the old 512 ceiling for real (`buffer alloc failed (ck)` at layer 25 of
 * the counter probe's own session) -- not a theoretical worry. */
#define ALGENTA_MAX_BUFFERS 2048

typedef struct {
    int32_t tag;       /* 0 = buffer device-address value, 1 = int64 scalar, 2 = float32 scalar */
    int32_t reserved;
    uint64_t value;
} AlgentaArg;

typedef struct {
    int32_t pipeline_idx;
    int32_t grid_x;      /* threadgroup count */
    int32_t threads_x;   /* threads per threadgroup */
    int32_t num_args;
    AlgentaArg args[ALGENTA_MAX_ARGS];
} AlgentaDispatchDesc;

/* ---- session-global state. One session per process, matching residentk's own one-DeviceContext-
 * per-generation-session design; nothing here is freed on purpose (the benchmark process runs one
 * generation and exits, same as `_ResidentQwen3` never tears itself down either). ---- */
static id<MTLDevice> g_device = nil;
static id<MTLCommandQueue> g_queue = nil;
static id<MTLComputePipelineState> g_pipelines[ALGENTA_MAX_PIPELINES];
static NSString *g_pipeline_names[ALGENTA_MAX_PIPELINES];
static int32_t g_pipeline_count = 0;
static id<MTLBuffer> g_buffers[ALGENTA_MAX_BUFFERS];
static int32_t g_buffer_count = 0;

/* ---- counter-sampling state, diagnostic-only, unused by any of the twin functions above ---- */
static id<MTLCounterSampleBuffer> g_counter_buffer = nil;
static int64_t g_counter_capacity = 0;

static int64_t algenta_fail(NSString *msg) {
    fprintf(stderr, "algenta_batch_shim: %s\n", msg.UTF8String);
    return -1;
}

/* Scan the running executable's OWN __TEXT,__const for every embedded Mojo `.metallib` (magic
 * `MTLB`, self-declared container length at byte offset +16 -- proven in the metalair investigation
 * this task's background section cites). Builds one MTLLibrary + one MTLComputePipelineState per
 * blob found, in DISCOVERY order (NOT necessarily the order Mojo's `compile_function_unchecked`
 * calls were written in -- measured to differ; callers identify a pipeline by name, not by index). */
int64_t algenta_open_session(void) {
    @autoreleasepool {
        if (g_device != nil) {
            return g_pipeline_count; /* idempotent */
        }
        g_device = MTLCreateSystemDefaultDevice();
        if (!g_device) {
            return algenta_fail(@"MTLCreateSystemDefaultDevice returned nil");
        }
        g_queue = [g_device newCommandQueue];
        if (!g_queue) {
            return algenta_fail(@"newCommandQueue returned nil");
        }

        const struct mach_header *mh = _dyld_get_image_header(0);
        unsigned long sect_size = 0;
        const uint8_t *sect = getsectiondata(
            (const struct mach_header_64 *)mh, "__TEXT", "__const", &sect_size);
        if (!sect) {
            return algenta_fail(@"getsectiondata(__TEXT,__const) returned NULL");
        }

        size_t i = 0;
        while (i + 20 < sect_size && g_pipeline_count < ALGENTA_MAX_PIPELINES) {
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
                    id<MTLLibrary> lib = [g_device newLibraryWithData:dd error:&err];
                    if (lib) {
                        NSArray<NSString *> *names = lib.functionNames;
                        if (names.count >= 1) {
                            id<MTLFunction> fn = [lib newFunctionWithName:names[0]];
                            if (fn) {
                                NSError *perr = nil;
                                id<MTLComputePipelineState> pso =
                                    [g_device newComputePipelineStateWithFunction:fn error:&perr];
                                if (pso) {
                                    g_pipelines[g_pipeline_count] = pso;
                                    g_pipeline_names[g_pipeline_count] = names[0];
                                    g_pipeline_count += 1;
                                } else {
                                    fprintf(stderr,
                                        "algenta_batch_shim: pipeline build failed for %s: %s\n",
                                        names[0].UTF8String, perr.description.UTF8String);
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
        return g_pipeline_count;
    }
}

int64_t algenta_pipeline_count(void) {
    return g_pipeline_count;
}

/* Same IOKit-registry GPU-core-count probe as `batch_shim.m`'s own `algenta_gpu_core_count` -- see
 * that file's docstring for the full account (verified against `system_profiler
 * SPDisplaysDataType`'s "Total Number of Cores" on this machine). Duplicated rather than shared via
 * a header because this whole package links exactly one `.m` file into a given binary (never both),
 * matching every other symbol both shim files already carry in parallel. */
int64_t algenta_gpu_core_count(void) {
    @autoreleasepool {
        CFMutableDictionaryRef matching = IOServiceMatching("AGXAccelerator");
        if (!matching) {
            return -1;
        }
        io_iterator_t iter = IO_OBJECT_NULL;
        kern_return_t kr = IOServiceGetMatchingServices(kIOMainPortDefault, matching, &iter);
        if (kr != KERN_SUCCESS) {
            return -1;
        }
        int64_t result = -1;
        io_service_t service;
        while ((service = IOIteratorNext(iter))) {
            if (result < 0) {
                CFTypeRef prop = IORegistryEntryCreateCFProperty(
                    service, CFSTR("gpu-core-count"), kCFAllocatorDefault, 0);
                if (prop) {
                    if (CFGetTypeID(prop) == CFNumberGetTypeID()) {
                        int64_t val = 0;
                        if (CFNumberGetValue((CFNumberRef)prop, kCFNumberSInt64Type, &val) && val > 0) {
                            result = val;
                        }
                    }
                    CFRelease(prop);
                }
            }
            IOObjectRelease(service);
        }
        IOObjectRelease(iter);
        return result;
    }
}

/* Copies pipeline `idx`'s Metal function name (as resolved from the loaded MTLLibrary -- the exact
 * string Metal itself uses, not a guess) into `buf`. Returns the byte length written (excluding the
 * NUL), or -1 if `idx` is out of range. */
int64_t algenta_pipeline_name(int64_t idx, uint8_t *buf, int64_t buf_len) {
    @autoreleasepool {
        if (idx < 0 || idx >= g_pipeline_count || buf_len < 1) {
            return -1;
        }
        const char *cstr = g_pipeline_names[idx].UTF8String;
        int64_t n = (int64_t)strlen(cstr);
        int64_t to_copy = n < buf_len - 1 ? n : buf_len - 1;
        memcpy(buf, cstr, (size_t)to_copy);
        buf[to_copy] = 0;
        return to_copy;
    }
}

/* Allocates one MTLBuffer (storage mode Shared -- CPU and GPU coherent on this unified-memory
 * host, no explicit synchronize needed for a CPU write before a GPU read once the buffer is
 * created). Returns the internal buffer index (>=0), or -1 on failure / table exhaustion.
 * `*out_addr` is `buffer.gpuAddress` -- the value a kernel's pointer argument is bound to.
 * `*out_contents` is the CPU-writable pointer Mojo uses for the one-time upload. */
int64_t algenta_alloc_buffer(int64_t length_bytes, uint64_t *out_addr, uint8_t **out_contents) {
    @autoreleasepool {
        if (g_device == nil || g_buffer_count >= ALGENTA_MAX_BUFFERS || length_bytes <= 0) {
            return -1;
        }
        id<MTLBuffer> buf = [g_device newBufferWithLength:(NSUInteger)length_bytes
                                                   options:MTLResourceStorageModeShared];
        if (!buf) {
            return algenta_fail(@"newBufferWithLength returned nil");
        }
        int32_t idx = g_buffer_count;
        g_buffers[idx] = buf;
        g_buffer_count += 1;
        *out_addr = buf.gpuAddress;
        *out_contents = (uint8_t *)buf.contents;
        return idx;
    }
}

/* THE call this whole package exists to make possible: one command buffer, one encoder, every
 * dispatch in `descriptors` bound and issued entirely inside this function (zero Mojo<->C crossings
 * in the loop below), one `endEncoding`, one `commit`, one `waitUntilCompleted`. Returns 0 on
 * success, -1 on any Metal-reported error (checked once, after the wait -- not per dispatch, since
 * Metal has no per-dispatch synchronous error return; a validation failure surfaces on the command
 * buffer). */
int64_t algenta_run_token(const AlgentaDispatchDesc *descriptors, int64_t n) {
    @autoreleasepool {
        if (g_queue == nil) {
            return algenta_fail(@"algenta_run_token called before algenta_open_session");
        }
        id<MTLCommandBuffer> cb = [g_queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];

        /* Residency: every buffer this session has ever allocated, marked resident ONCE for this
         * encoder. Correct per Apple's documented contract (residency lasts the life of the
         * encoder/command buffer once declared) and cheaper than a per-dispatch call would be --
         * `useResource:` is O(1) bookkeeping, not a data transfer, on unified memory. */
        for (int32_t b = 0; b < g_buffer_count; b++) {
            [enc useResource:g_buffers[b] usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
        }

        for (int64_t d = 0; d < n; d++) {
            const AlgentaDispatchDesc *desc = &descriptors[d];
            if (desc->pipeline_idx < 0 || desc->pipeline_idx >= g_pipeline_count) {
                return algenta_fail(@"dispatch descriptor named an out-of-range pipeline index");
            }
            [enc setComputePipelineState:g_pipelines[desc->pipeline_idx]];
            for (int32_t a = 0; a < desc->num_args; a++) {
                const AlgentaArg *arg = &desc->args[a];
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
                    return algenta_fail(@"dispatch descriptor argument had an unknown tag");
                }
            }
            MTLSize groups = MTLSizeMake((NSUInteger)desc->grid_x, 1, 1);
            MTLSize threads = MTLSizeMake((NSUInteger)desc->threads_x, 1, 1);
            [enc dispatchThreadgroups:groups threadsPerThreadgroup:threads];
        }

        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        if (cb.status != MTLCommandBufferStatusCompleted || cb.error != nil) {
            fprintf(stderr, "algenta_batch_shim: command buffer failed, status=%ld err=%s\n",
                    (long)cb.status, cb.error ? cb.error.description.UTF8String : "none");
            return -1;
        }
        return 0;
    }
}

/* ═══════════════════════════ diagnostic counter-sampling additions ═══════════════════════════ */

/* 1 = this device supports GPU counter sampling at a compute encoder ("stage") boundary AND
 * exposes a counter set containing a timestamp counter, 0 = neither/either is missing (caller
 * should not attempt to open a counter buffer), -1 = called before `algenta_open_session`.
 *
 * Checks `MTLCounterSamplingPointAtStageBoundary`, NOT `AtDispatchBoundary` -- measured directly on
 * this M4 Max that `AtDispatchBoundary` (which would let one encoder hold all 171 dispatches with
 * per-dispatch samples via `sampleCountersInBuffer:`) is unsupported here; only the per-ENCODER
 * boundary is, which is what `algenta_run_token_counters`'s one-encoder-per-dispatch design relies
 * on. See that function's own comment for the full explanation. */
int64_t algenta_counters_supported(void) {
    @autoreleasepool {
        if (g_device == nil) {
            return -1;
        }
        if (![g_device supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary]) {
            return 0;
        }
        NSArray<id<MTLCounterSet>> *sets = g_device.counterSets;
        for (id<MTLCounterSet> s in sets) {
            if ([s.name isEqualToString:MTLCommonCounterSetTimestamp]) {
                return 1;
            }
        }
        return 0;
    }
}

/* Ticks-per-second for the raw counter values `algenta_run_token_counters` writes. 0 if this
 * device/OS does not expose `queryTimestampFrequency` (older than macOS 26) -- callers must check
 * for that and fall back to reporting raw ticks instead of nanoseconds. */
uint64_t algenta_timestamp_frequency(void) {
    @autoreleasepool {
        if (g_device == nil) {
            return 0;
        }
        if ([g_device respondsToSelector:@selector(queryTimestampFrequency)]) {
            return [g_device queryTimestampFrequency];
        }
        return 0;
    }
}

/* Reads the GPU-domain half of `[MTLDevice sampleTimestamps:gpuTimestamp:]` -- the same "GPU time"
 * domain Apple's docs say `MTLCommonCounterTimestamp` samples read (both exist specifically so a
 * caller can correlate GPU-side sampled events against real time). NOT used for the per-dispatch
 * samples themselves (those come from `resolveCounterRange:`) -- this is a calibration probe: call
 * it, wait a known real interval (measured on the Mojo side with the same `perf_counter_ns` this
 * whole benchmark chain already trusts), call it again, and divide the GPU tick delta by the
 * elapsed wall seconds to get the REAL tick rate. Added because `algenta_timestamp_frequency`
 * (`queryTimestampFrequency`) measured, directly, to be wrong by a factor of ~41.667 on this
 * machine -- see `qwen3_probe_counters_i8.mojo`'s own calibration step and this task's final report
 * for the measured numbers. */
uint64_t algenta_sample_gpu_timestamp(void) {
    @autoreleasepool {
        if (g_device == nil) {
            return 0;
        }
        MTLTimestamp cpu_ts, gpu_ts;
        [g_device sampleTimestamps:&cpu_ts gpuTimestamp:&gpu_ts];
        return (uint64_t)gpu_ts;
    }
}

/* Allocates the one counter sample buffer this diagnostic session uses for every token it times.
 * `max_samples` must be >= 2 * (the largest `n` any `algenta_run_token_counters` call will use) --
 * two samples (start, end) per dispatch. Returns 0 on success, -1 on failure (no timestamp counter
 * set found, or the device refused to allocate the buffer). Idempotent: a second call with the
 * same or smaller capacity is a no-op success; a larger capacity reallocates. */
int64_t algenta_open_counters(int64_t max_samples) {
    @autoreleasepool {
        if (g_device == nil) {
            return algenta_fail(@"algenta_open_counters called before algenta_open_session");
        }
        if (g_counter_buffer != nil && g_counter_capacity >= max_samples) {
            return 0;
        }
        id<MTLCounterSet> ts_set = nil;
        for (id<MTLCounterSet> s in g_device.counterSets) {
            if ([s.name isEqualToString:MTLCommonCounterSetTimestamp]) {
                ts_set = s;
                break;
            }
        }
        if (ts_set == nil) {
            return algenta_fail(@"no MTLCommonCounterSetTimestamp counter set on this device");
        }
        MTLCounterSampleBufferDescriptor *desc = [MTLCounterSampleBufferDescriptor new];
        desc.counterSet = ts_set;
        desc.storageMode = MTLStorageModeShared;
        desc.sampleCount = (NSUInteger)max_samples;
        desc.label = @"algenta_diagnostic_dispatch_timestamps";
        NSError *err = nil;
        id<MTLCounterSampleBuffer> buf = [g_device newCounterSampleBufferWithDescriptor:desc error:&err];
        if (buf == nil) {
            fprintf(stderr, "algenta_batch_shim: newCounterSampleBufferWithDescriptor failed: %s\n",
                    err ? err.description.UTF8String : "(no error)");
            return -1;
        }
        g_counter_buffer = buf;
        g_counter_capacity = max_samples;
        return 0;
    }
}

/* THE diagnostic per-token call. NOT the same shape as `algenta_run_token` above -- measured
 * directly on this machine (see `algenta_counters_supported`'s own comment) that this M4 Max's
 * driver answers `supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary` with NO, so
 * `sampleCountersInBuffer:atSampleIndex:withBarrier:` on a compute encoder -- the natural "one
 * encoder holds all 171 dispatches" approach -- is not available here (Apple's own header says
 * calling it anyway "will generate an error"). Only `MTLCounterSamplingPointAtStageBoundary` is
 * supported, which means the granularity Metal actually offers per DISPATCH on this hardware is
 * the ENCODER's start/end sample, via `MTLComputePassDescriptor.sampleBufferAttachments` +
 * `startOfEncoderSampleIndex`/`endOfEncoderSampleIndex`. So this function gives every dispatch its
 * OWN compute encoder (171 encoders instead of 1), each configured with exactly one start+end
 * sample pair -- but ALL 171 encoders still belong to the SAME command buffer, committed and
 * waited on exactly ONCE. Ending one encoder and opening the next (`computeCommandEncoderWithDescriptor:`)
 * is pure CPU-side command-buffer construction, not a GPU wait -- creating encoder N+1 does not
 * block on encoder N's execution, so this is still zero host/GPU sync points inside the loop,
 * exactly the constraint this whole diagnostic exists to respect. What it does cost, relative to
 * `algenta_run_token`'s one-encoder design, is more CPU-side encoding work (171 pass-descriptor
 * allocations and 171 `useResource:` sweeps instead of 1) -- measured honestly as this
 * instrumentation's overhead, not assumed away.
 * `out_ticks` must have room for `2 * n` `uint64_t`s; `out_ticks[2*d]`/`out_ticks[2*d+1]` are
 * dispatch `d`'s raw start/end tick counts (divide a delta by `algenta_timestamp_frequency()` and
 * multiply by 1e9 for nanoseconds). Returns 0 on success, -1 on any failure. */
int64_t algenta_run_token_counters(
    const AlgentaDispatchDesc *descriptors, int64_t n, uint64_t *out_ticks
) {
    @autoreleasepool {
        if (g_queue == nil) {
            return algenta_fail(@"algenta_run_token_counters called before algenta_open_session");
        }
        if (g_counter_buffer == nil || g_counter_capacity < 2 * n) {
            return algenta_fail(@"algenta_run_token_counters called before algenta_open_counters "
                                 @"(or with too small a capacity)");
        }
        id<MTLCommandBuffer> cb = [g_queue commandBuffer];

        for (int64_t d = 0; d < n; d++) {
            const AlgentaDispatchDesc *desc = &descriptors[d];
            if (desc->pipeline_idx < 0 || desc->pipeline_idx >= g_pipeline_count) {
                return algenta_fail(@"dispatch descriptor named an out-of-range pipeline index");
            }

            MTLComputePassDescriptor *passDesc = [MTLComputePassDescriptor computePassDescriptor];
            passDesc.sampleBufferAttachments[0].sampleBuffer = g_counter_buffer;
            passDesc.sampleBufferAttachments[0].startOfEncoderSampleIndex = (NSUInteger)(2 * d);
            passDesc.sampleBufferAttachments[0].endOfEncoderSampleIndex = (NSUInteger)(2 * d + 1);
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoderWithDescriptor:passDesc];

            for (int32_t b = 0; b < g_buffer_count; b++) {
                [enc useResource:g_buffers[b] usage:(MTLResourceUsageRead | MTLResourceUsageWrite)];
            }

            [enc setComputePipelineState:g_pipelines[desc->pipeline_idx]];
            for (int32_t a = 0; a < desc->num_args; a++) {
                const AlgentaArg *arg = &desc->args[a];
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
                    return algenta_fail(@"dispatch descriptor argument had an unknown tag");
                }
            }
            MTLSize groups = MTLSizeMake((NSUInteger)desc->grid_x, 1, 1);
            MTLSize threads = MTLSizeMake((NSUInteger)desc->threads_x, 1, 1);
            [enc dispatchThreadgroups:groups threadsPerThreadgroup:threads];
            [enc endEncoding];
        }

        [cb commit];
        [cb waitUntilCompleted];

        if (cb.status != MTLCommandBufferStatusCompleted || cb.error != nil) {
            fprintf(stderr, "algenta_batch_shim: counters command buffer failed, status=%ld err=%s\n",
                    (long)cb.status, cb.error ? cb.error.description.UTF8String : "none");
            return -1;
        }

        /* Resolve ONCE, after the single wait above -- reading a buffer the GPU already finished
         * writing during the batch, never a mid-batch resolve. */
        NSData *resolved = [g_counter_buffer resolveCounterRange:NSMakeRange(0, (NSUInteger)(2 * n))];
        if (resolved == nil || resolved.length < (NSUInteger)(2 * n * sizeof(uint64_t))) {
            return algenta_fail(@"resolveCounterRange returned nil or a short buffer");
        }
        memcpy(out_ticks, resolved.bytes, (size_t)(2 * n) * sizeof(uint64_t));
        return 0;
    }
}
