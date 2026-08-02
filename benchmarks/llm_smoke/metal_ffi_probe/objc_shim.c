/* objc_shim.c -- a THIN, uniquely-named wrapper per Objective-C message signature this probe
 * needs. Not a workaround around the task's FFI requirement: every function here still reaches
 * Metal purely through `objc_msgSend`/`sel_registerName`/`dispatch_data_create` -- exactly the
 * "objc_msgSend and friends" mechanism the task specifies. It exists because Mojo's own
 * `external_call["objc_msgSend", ...]` registers ONE global extern declaration per NAME the
 * first time it is lowered in a compilation unit, so a second call site with a DIFFERENT
 * signature under the SAME name fails to compile ("existing function with conflicting
 * signature"); and the alternative -- `dlsym` + an indirect call through a Mojo function-pointer
 * value -- compiles but crashes inside Mojo's own runtime (`libKGENCompilerRTShared.dylib`) at
 * the point of the indirect call, on this exact toolchain (both are recorded, with repro
 * commands, in the write-up this probe's investigation produced). A one-name-per-signature C
 * shim sidesteps both: each wrapper here has its OWN unique external symbol name, so each
 * `external_call["algenta_..."]` site in Mojo has exactly one signature, and the actual met
 * message send happens in plain C, which has never had any trouble re-typing `objc_msgSend`
 * per call site (that is the standard, decades-old idiom every Objective-C header itself uses).
 *
 * Every function below is a literal one-line forward to `objc_msgSend` (or a Metal/dispatch C
 * function) with a FIXED, explicit signature -- nothing here contains any kernel logic, any
 * Metal argument-layout knowledge, or any behavior beyond "send this exact message". `dispatch:`
 * with MTLSize also lives here so the aggregate-by-value ABI is handled by clang natively, the
 * same lowering `metal_token.m`'s already-measured raw-Metal control relies on, rather than
 * asking Mojo's LLVM lowering to match it independently.
 */
#include <stdint.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <dispatch/dispatch.h>

typedef struct { uint64_t width, height, depth; } AlgentaMTLSize;

void *algenta_sel(const char *name) {
    return (void *)sel_registerName(name);
}

void *algenta_msg0(void *recv, void *s) {
    typedef void *(*F)(void *, void *);
    return ((F)objc_msgSend)(recv, s);
}

void algenta_msg0_void(void *recv, void *s) {
    typedef void (*F)(void *, void *);
    ((F)objc_msgSend)(recv, s);
}

void *algenta_msg1p(void *recv, void *s, void *a0) {
    typedef void *(*F)(void *, void *, void *);
    return ((F)objc_msgSend)(recv, s, a0);
}

void algenta_msg1p_void(void *recv, void *s, void *a0) {
    typedef void (*F)(void *, void *, void *);
    ((F)objc_msgSend)(recv, s, a0);
}

void *algenta_msg1u_ret(void *recv, void *s, uint64_t a0) {
    typedef void *(*F)(void *, void *, uint64_t);
    return ((F)objc_msgSend)(recv, s, a0);
}

uint64_t algenta_msg0_u64(void *recv, void *s) {
    typedef uint64_t (*F)(void *, void *);
    return ((F)objc_msgSend)(recv, s);
}

void *algenta_msg_newbuffer(void *dev, void *s, uint64_t length, uint64_t options) {
    typedef void *(*F)(void *, void *, uint64_t, uint64_t);
    return ((F)objc_msgSend)(dev, s, length, options);
}

void algenta_msg_setbuffer(void *enc, void *s, void *buf, uint64_t offset, uint64_t index) {
    typedef void (*F)(void *, void *, void *, uint64_t, uint64_t);
    ((F)objc_msgSend)(enc, s, buf, offset, index);
}

void algenta_msg_setbytes(void *enc, void *s, const void *data, uint64_t length, uint64_t index) {
    typedef void (*F)(void *, void *, const void *, uint64_t, uint64_t);
    ((F)objc_msgSend)(enc, s, data, length, index);
}

void algenta_msg_dispatch(void *enc, void *s,
                           uint64_t gw, uint64_t gh, uint64_t gd,
                           uint64_t tw, uint64_t th, uint64_t td) {
    typedef void (*F)(void *, void *, AlgentaMTLSize, AlgentaMTLSize);
    AlgentaMTLSize groups = {gw, gh, gd};
    AlgentaMTLSize threads = {tw, th, td};
    ((F)objc_msgSend)(enc, s, groups, threads);
}

void *algenta_msg_2p_err(void *recv, void *s, void *a0, void **err_out) {
    typedef void *(*F)(void *, void *, void *, void **);
    return ((F)objc_msgSend)(recv, s, a0, err_out);
}

void *algenta_msg_1p_1u(void *recv, void *s, void *a0, uint64_t a1) {
    typedef void *(*F)(void *, void *, void *, uint64_t);
    return ((F)objc_msgSend)(recv, s, a0, a1);
}

void *algenta_dispatch_data_create(const void *buf, uint64_t size) {
    return (void *)dispatch_data_create(buf, (size_t)size, dispatch_get_main_queue(),
                                         DISPATCH_DATA_DESTRUCTOR_DEFAULT);
}

void *algenta_objc_getClass(const char *name) {
    return (void *)objc_getClass(name);
}

int64_t algenta_msg0_i64(void *recv, void *s) {
    typedef int64_t (*F)(void *, void *);
    return ((F)objc_msgSend)(recv, s);
}
