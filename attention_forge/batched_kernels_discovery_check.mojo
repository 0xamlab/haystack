"""batched_kernels_discovery_check.mojo -- Project Slipstream Phase 3 (2026-08-09): STANDALONE
discovery go/no-go for the two NEW batched-decode blobs (`native_kv_decode_attn_splitk_batched_blob.c`,
`native_kv_producer_batched_blob.c`). Its ONLY job is to reveal the real, truncated Metal AIR names
the shim assigns these kernels and confirm the substring checks needed for engine wiring are
unambiguous -- specifically the LONGEST-FIRST hazard: the batched attention module's AIR name
contains the single-stream split-K module's substring (`native_kv_decode_attn_splitk` is a prefix of
`native_kv_decode_attn_splitk_batched`), so the engine's discovery loop must check the longer
substring first. Follows `native_kv_decode_attn_discovery_check.mojo`'s pattern exactly.

Build (PINNED `mojo_env` toolchain):

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/native_kv_decode_attn_splitk_batched_blob.c \
        -o /tmp/native_kv_decode_attn_splitk_batched_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/native_kv_producer_batched_blob.c \
        -o /tmp/native_kv_producer_batched_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -I ../mojo/engine \
        ../attention_forge/batched_kernels_discovery_check.mojo \
        -o /tmp/batched_kernels_discovery_check \
        -Xlinker /tmp/batch_shim.o \
        -Xlinker /tmp/native_kv_decode_attn_splitk_batched_blob.o \
        -Xlinker /tmp/native_kv_producer_batched_blob.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/batched_kernels_discovery_check
"""
from metaldispatch.ffi import _mb_open_session, _mb_pipeline_count, _mb_pipeline_name


def main() raises:
    print("=== batched attention (partial+merge) + batched kvprod: discovery-only go/no-go ===")
    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", opened)
        return
    var count = _mb_pipeline_count()
    print("pipelines discovered:", count)

    var n_attn_partial_batched = 0
    var n_kvprod_batched = 0
    var n_naive_producer = 0
    var n_kvprod_batched_leaks_naive = 0
    var n_attn_splitk_ambiguous = 0
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print("  pipeline", i, ": name=", name)
        # Longest-first classification, exactly the discipline the engine wiring must use. The
        # partial-only blob truncates to `native_kv_decode_attn_splitk_bat_<hex>`; `_bat` can never
        # appear in the single-stream split-K name (hex hash has no 't'). The batched kvprod module
        # was RENAMED `kvprod_batched` so it no longer contains `native_kv_producer` (the shared
        # `_classify_attention_forge_pipeline` pattern) -- verified here against the naive producer.
        if name.find("native_kv_decode_attn_splitk_bat") >= 0:
            n_attn_partial_batched += 1
        if name.find("kvprod_batched") >= 0:
            n_kvprod_batched += 1
            if name.find("native_kv_producer") >= 0:
                n_kvprod_batched_leaks_naive += 1
        elif name.find("native_kv_producer") >= 0:
            n_naive_producer += 1
        if name.find("native_kv_decode_attn_splitk") >= 0:
            n_attn_splitk_ambiguous += 1

    print("")
    print("batched attn partial matches (via '_splitk_bat'):", n_attn_partial_batched, "(want 1)")
    print("batched kvprod matches (via 'kvprod_batched'):", n_kvprod_batched, "(want 1)")
    print("batched kvprod names leaking 'native_kv_producer':", n_kvprod_batched_leaks_naive, "(want 0)")
    print("naive producer matches (via 'native_kv_producer'):", n_naive_producer, "(want 1)")
    print("names also matching single-stream 'native_kv_decode_attn_splitk' substring:",
          n_attn_splitk_ambiguous, "(must equal partial count; resolved longest-first)")
    var ok = (
        count == 3 and n_attn_partial_batched == 1 and n_kvprod_batched == 1
        and n_kvprod_batched_leaks_naive == 0 and n_naive_producer == 1
        and n_attn_splitk_ambiguous == 1
    )
    print("")
    print("DISCOVERY CHECK:", "PASS" if ok else "FAIL")
