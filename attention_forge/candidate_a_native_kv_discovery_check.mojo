"""candidate_a_native_kv_discovery_check.mojo -- STANDALONE go/no-go check (Attention Compiler Plan
v1.0, Phase 2C production wiring): confirms the EXACT pair of blobs the real production wiring needs
-- Candidate A's attention kernel (`attention_forge/generated/candidate_a_blob.c`) and the native-KV-
producer (`attention_forge/generated/native_kv_producer_blob.c`) -- plus the EXISTING production GEMM
blob (`mma_forge/generated/mm8_blob.c`) coexist in ONE binary with unambiguous, non-colliding
pipeline-name discovery, following `candidate_multi_blob_test.mojo`'s own established pattern
exactly, but for THIS session's real production pair rather than Candidate A + Candidate C.

Discovery-only (no dispatch/correctness re-check here -- `candidate_a_blob_test.mojo` and
`native_kv_producer_driver.mojo` already established both kernels' own correctness independently;
this file's only job is the discovery/collision question for the exact three-blob combination
production wiring will link).

Build (PINNED `mojo_env` toolchain):

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/candidate_a_blob.c -o /tmp/candidate_a_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../attention_forge/generated/native_kv_producer_blob.c -o /tmp/native_kv_producer_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -I ../mojo/engine \
        ../attention_forge/candidate_a_native_kv_discovery_check.mojo \
        -o /tmp/candidate_a_native_kv_discovery_check \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/candidate_a_blob.o \
        -Xlinker /tmp/native_kv_producer_blob.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/candidate_a_native_kv_discovery_check
"""
from metaldispatch.ffi import _mb_open_session, _mb_pipeline_count, _mb_pipeline_name


def main() raises:
    print("=== Candidate A + native-KV-producer + mm8: discovery-only go/no-go ===")
    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", opened)
        return
    var count = _mb_pipeline_count()
    print("pipelines discovered:", count)

    var n_grouped_fa = 0
    var n_native_kv = 0
    var n_mm8 = 0
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print("  pipeline", i, ": name=", name)
        if name.find("grouped_fa_q8_k32_h2_sg8") >= 0:
            n_grouped_fa += 1
        if name.find("native_kv_producer") >= 0:
            n_native_kv += 1
        if name.find("mm8__") >= 0:
            n_mm8 += 1

    print("")
    print("grouped_fa matches:", n_grouped_fa, "(want 1)")
    print("native_kv_producer matches:", n_native_kv, "(want 1)")
    print("mm8 matches:", n_mm8, "(want 3)")
    var ok = count == 5 and n_grouped_fa == 1 and n_native_kv == 1 and n_mm8 == 3
    print("")
    print("DISCOVERY CHECK:", "PASS" if ok else "FAIL")
