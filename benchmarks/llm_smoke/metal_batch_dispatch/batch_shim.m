/* batch_shim.m -- the ONE C-shim call per token this package exists to prove.
 *
 * Compiled to a .o and linked into the Mojo binary via `-Xlinker <path-to-batch_shim.o>`, exactly
 * the linker-object mechanism `.worktrees/metalffi/benchmarks/llm_smoke/metal_ffi_probe/objc_shim.c`
 * proved works (a plain object file is a valid positional argument to `ld`, so passing its path as
 * one `-Xlinker` argument links it straight in). Unlike that probe's shim -- a one-line-per-symbol
 * forward to `objc_msgSend` written because MOJO's own `external_call` can only register one
 * signature per name -- THIS file is ordinary, idiomatic Objective-C (ARC-compiled, bracket syntax
 * throughout). Nothing here is reached through Mojo's FFI signature restriction: clang compiles this
 * file on its own, so there is no reason to hand-rove `objc_msgSend`. The content is different and
 * bigger because the JOB is different: not "prove one dispatch reaches Metal" but "collapse 171
 * dispatches into ONE call, entirely on this side of the Mojo<->C boundary."
 *
 * The proven ABI recipe this file implements for every dispatch (established in
 * `.worktrees/metalair/benchmarks/llm_smoke/metal_air_access_probe/`, both `.m` probes, exact
 * 0.0000000 match against MAX's own `enqueue_function` on the real 5-arg GEMV shape):
 *   - a POINTER kernel argument is bound at its declared slot as the *value* of the buffer's own
 *     64-bit GPU device address (`MTLBuffer.gpuAddress`), via `setBytes:length:atIndex:` -- NOT
 *     `setBuffer:offset:atIndex:`, which is the wrong Metal call for Mojo's Metal ABI and is exactly
 *     the mistake the no-go finding in `#504` made;
 *   - every MTLBuffer actually referenced by ANY dispatch in the token is marked resident on the
 *     encoder with `useResource:usage:` -- done ONCE per encoder for every buffer this session ever
 *     allocated (Apple's residency contract only requires this once per encoder lifetime, not once
 *     per dispatch that touches the buffer, so batching 171 dispatches behind one encoder makes this
 *     cheaper, not more expensive, than the one-dispatch-per-encoder case the probes measured);
 *   - a scalar `Int` argument is bound as its 8-byte value (Mojo's `Int` is 64-bit on this target);
 *   - a scalar `Float32` argument is bound as its 4-byte value.
 *
 * Session-open builds every compute pipeline ONCE, from Mojo's own compiled kernel bytes (the
 * embedded `.metallib`s in this executable's own `__TEXT,__const`, extracted and loaded through the
 * fully public `dispatch_data_create` -> `newLibraryWithData:error:` path -- background steps (1)
 * and (2) from the investigation this task's background section describes). Buffers are allocated
 * ONCE and held for the session's life; only `algenta_run_token` is on the per-token path, and it
 * does the ENTIRE 171-dispatch sequence -- one command buffer, one encoder, one commit, one wait --
 * behind a single call from Mojo.
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <dispatch/dispatch.h>
#import <IOKit/IOKitLib.h>
#include <mach-o/dyld.h>
#include <mach-o/getsect.h>
#include <stdint.h>
#include <string.h>

/* feat/llama-native-deep (2026-08-13): raised 16 -> 17 -- the attention-forge
 * native-KV-producer kernel grew the trailing llama-family qk_norm flag, and its
 * decode/prefill dispatches bind 17 args; must match ffi.mojo's MB_MAX_ARGS. */
#define ALGENTA_MAX_ARGS 17
/* Beat-llama.cpp campaign (2026-08-08 night): bumped 32 -> 64. Real measured need, hit for real,
 * not a theoretical worry: the campaign's no-mirror+MSL race binary links NINE forged blob objects
 * (mm8, three vecload4, msl_parity's three metallibs, candidate_a, native_kv_producer, and the two
 * decode-side native_kv_decode_attn + split-K blobs) on top of the ~23 Mojo-compiled kernels the
 * session's own `__init__` lowers -- ~34 MTLBs total, OVER the old 32 cap. The overflow is silent
 * by construction (the discovery scan stops at the cap): the two decode blobs, linked last, simply
 * never registered, and the first `step()` call failed `metaldispatch_pipeline_not_found` -- the
 * exact failure that surfaced this. 64 leaves the same headroom style the buffer bump below uses. */
#define ALGENTA_MAX_PIPELINES 64
/* Project Redline reopening, adversarial-hardening follow-up (task steps 2/3): bumped 512 -> 2048.
 * Buffers are allocated per-`_MBQwen3I8AllSimd7Prefill`-instance (weights/KV-cache/activation
 * buffers) and never freed for the lifetime of the process (`algenta_alloc_buffer`'s own
 * `g_buffer_count` only ever grows) -- every PRIOR test file in this repo constructed at most a
 * handful of instances per binary, comfortably under 512. This session's own fault-injection/
 * depth-shape-hardening test (`test_metaldispatch_session_prefill_native_decode.mojo`'s Gates H/I)
 * deliberately constructs MANY fresh, isolated instances in one process (one per fault fixture, one
 * per depth/shape scenario) to keep each fixture's own native-cache state genuinely clean -- real
 * measured need, hit 512 for real (`buffer alloc failed (ck)` at the 11th instance), not a
 * theoretical worry. Pipelines (`ALGENTA_MAX_PIPELINES`, a SEPARATE, one-time-discovered, process-
 * wide table `algenta_open_session` reuses across every instance) are unaffected by this and stay
 * unchanged.
 *
 * Parity cheap wins (2026-08-10): bumped 2048 -> 8192. The SDK's one-shot shape runs MANY
 * independent sessions through ONE long-lived runtime worker (every `algenta.inference.decode()`
 * call is a fresh session), and one Qwen3-0.6B anyqwen3 session allocates ~526 buffers (14/layer
 * weights+norms+KV x 28 layers, + 4/layer MSL f16 twins, globals, activations, split-K partials),
 * so the 4th SDK call in one worker process hit 2048 for real (`buffer alloc failed
 * (w_qkv_scale)` in tests/test_inference_gpu_e2e.py). 8192 gives ~15 sessions of headroom; the
 * table itself is 64 KB of static pointers. The HONEST long-term fix is session teardown (freeing
 * a session's buffers when its one-shot call completes) -- that is the parity-gap-4 persistent-
 * sessions work, not a cheap win, so until then the cap is the gate and this comment is the
 * record of why it moves. */
#define ALGENTA_MAX_BUFFERS 8192

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

/* ---- Parity gap 4 (persistent sessions, 2026-08-10): resident-session state. A resident key
 * (FNV hash of checkpoint + dims + max_ctx, computed Mojo-side) labels the model whose weights
 * currently live in g_buffers. When the next call carries the SAME key, the Mojo side constructs
 * its session in ADOPT mode: every algenta_alloc_buffer returns the NEXT EXISTING buffer instead
 * of allocating, so the session re-adopts its own weights/KV/twins with zero Metal traffic and
 * zero re-quantization -- allocations happen in the same order for the same model, so the cursor
 * replays the identical layout. A DIFFERENT key frees every buffer first (teardown) so a model
 * switch starts clean and the table cannot grow unbounded across models. ---- */
static uint64_t g_resident_key = 0;
static int32_t g_adopt = 0;
static int32_t g_adopt_cursor = 0;

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

/* GPU core count, read from the IOKit registry -- the ONE property that answers this question on
 * Apple Silicon at all, since `MTLDevice`'s own public API has none (confirmed by direct inspection
 * of this SDK's `MTLDevice` protocol before writing this function: no `coreCount`, no equivalent, on
 * this toolchain). Every Apple GPU accelerator instance registers an `IOService` named
 * "AGXAccelerator" (the same class `Metal.framework` itself talks to under the hood) carrying an
 * integer property "gpu-core-count" -- verified against this machine's own `system_profiler
 * SPDisplaysDataType` ("Total Number of Cores: 40") returning the identical value, 40, via this exact
 * lookup, so this is reading the same fact `system_profiler` reports, not a different one that
 * happens to agree here.
 *
 * Deliberately independent of `g_device`/`algenta_open_session` -- a caller may want the core count
 * before opening a dispatch session (to size split-K scratch buffers at construction time), so this
 * walks the IOKit registry directly rather than asking the already-open `MTLDevice` for anything.
 *
 * Returns the core count (> 0) on success, or -1 if no matching IOService was found, the property
 * was absent, or the property was present but not the integer type expected -- a typed failure, not
 * a guess, matching this codebase's own `accel.device` convention (report "could not determine",
 * let the CALLER decide the fallback, never silently invent a number here). */
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
        if (g_device == nil || length_bytes <= 0) {
            return -1;
        }
        if (g_adopt) {
            /* Adopt mode: hand back the next existing buffer (persistent resident weights).
             * Overflow (more allocations than buffers exist) is a hard failure -- the caller's
             * session shape does not match the resident one. */
            if (g_adopt_cursor >= g_buffer_count) {
                return -1;
            }
            id<MTLBuffer> buf = g_buffers[g_adopt_cursor];
            int32_t idx = g_adopt_cursor;
            g_adopt_cursor += 1;
            *out_addr = buf.gpuAddress;
            *out_contents = (uint8_t *)buf.contents;
            return idx;
        }
        if (g_buffer_count >= ALGENTA_MAX_BUFFERS) {
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

/* ---- Parity gap 4 (persistent sessions, 2026-08-10): resident-key + adopt API. ---- */

uint64_t algenta_get_resident_key(void) {
    return g_resident_key;
}

int64_t algenta_set_resident_key(uint64_t key) {
    g_resident_key = key;
    return 0;
}

int64_t algenta_begin_adopt(void) {
    g_adopt = 1;
    g_adopt_cursor = 0;
    return 0;
}

int64_t algenta_end_adopt(void) {
    g_adopt = 0;
    g_adopt_cursor = 0;
    return 0;
}

/* Teardown: release EVERY Metal buffer (their contents are weight/KV state for the OLD resident
 * model) and clear the resident key. Pipelines are NOT touched -- they are name-keyed, model-
 * independent, and compiled once per process. Called on a resident-key CHANGE so a model switch
 * starts clean and the buffer table cannot grow unbounded across models. */
int64_t algenta_free_all_buffers(void) {
    @autoreleasepool {
        for (int32_t i = 0; i < g_buffer_count; i++) {
            g_buffers[i] = nil;
        }
        g_buffer_count = 0;
        g_resident_key = 0;
        g_adopt = 0;
        g_adopt_cursor = 0;
    }
    return 0;
}
