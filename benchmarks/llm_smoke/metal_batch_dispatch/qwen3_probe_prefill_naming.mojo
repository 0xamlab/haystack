"""qwen3_probe_prefill_naming.mojo — Phase 0 naming probe for the batched-prefill kernel family.

THROWAWAY, NOT WIRED INTO PRODUCTION, NOT PART OF ANY CONTRACT MODULE. Confirms empirically, before
any classifier or production kernel is written, that the six proposed `_pf_*` kernel names survive
Metal's AIR name truncation (measured elsewhere in this codebase at exactly 11 visible characters
after the mangled `residentk_kernels__` prefix — `_classify_splitk_pipeline`'s own docstring,
`metaldispatch/session.mojo`) without colliding with each other OR with any of `_classify_pipeline`'s
/ `_classify_splitk_pipeline`'s existing eight+two patterns. Same throwaway-probe-plus-temporary-print
methodology that function's own docstring says caught two real collisions before landing.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_prefill_naming.mojo \
        -o /tmp/probe_prefill_naming \
        -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/probe_prefill_naming
"""

from metaldispatch.contract import MB_ERR_SESSION_OPEN_FAILED
from metaldispatch.ffi import _mb_open_session, _mb_pipeline_count, _mb_pipeline_name
from metaldispatch.session import _classify_pipeline, _classify_splitk_pipeline
from residentk.kernels import (
    _pf_embed_rows_kernel_i8,
    _pf_qkv_proj_kernel_simd_i8,
    _pf_ropewrt_kernel,
    _pf_gemv_accum_kernel_simd_i8,
    _pf_swiglu_kernel_simd_i8,
    _pf_attn_tiled_kernel_simd,
    _pf_rmsnorm_rows_kernel,
    _pf_gemm_assign_kernel_i8,
    _pf_gemm_accum_kernel_i8,
    _pf_gemm_swiglu_kernel_i8,
    _pf_gnrw_assign_kernel_i8,
    _pf_gnrw_accum_kernel_i8,
    _pf_gnrw_swiglu_kernel_i8,
)


def main() raises:
    from std.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function_unchecked[_pf_embed_rows_kernel_i8]()
    _ = cctx.compile_function_unchecked[_pf_qkv_proj_kernel_simd_i8]()
    _ = cctx.compile_function_unchecked[_pf_ropewrt_kernel]()
    _ = cctx.compile_function_unchecked[_pf_gemv_accum_kernel_simd_i8]()
    _ = cctx.compile_function_unchecked[_pf_swiglu_kernel_simd_i8]()
    _ = cctx.compile_function_unchecked[_pf_attn_tiled_kernel_simd]()
    _ = cctx.compile_function_unchecked[_pf_rmsnorm_rows_kernel]()
    _ = cctx.compile_function_unchecked[_pf_gemm_assign_kernel_i8]()
    _ = cctx.compile_function_unchecked[_pf_gemm_accum_kernel_i8]()
    _ = cctx.compile_function_unchecked[_pf_gemm_swiglu_kernel_i8]()
    _ = cctx.compile_function_unchecked[_pf_gnrw_assign_kernel_i8]()
    _ = cctx.compile_function_unchecked[_pf_gnrw_accum_kernel_i8]()
    _ = cctx.compile_function_unchecked[_pf_gnrw_swiglu_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    print("discovered pipelines:", count)
    var names = List[String]()
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        names.append(name)
        print(" [", i, "]", name)

    # Every discovered name must be findable by EXACTLY ONE of the six expected substrings, and must
    # NOT match any existing `_classify_pipeline`/`_classify_splitk_pipeline` pattern -- the same two
    # failure modes `_classify_splitk_pipeline`'s own docstring recounts hitting for real.
    var expected = List[String]()
    expected.append("pf_embed")
    expected.append("pf_qkv")
    expected.append("pf_ropewrt")
    expected.append("pf_gemv_ac")
    expected.append("pf_swiglu")
    expected.append("pf_attn")
    expected.append("pf_rmsnorm")
    expected.append("pf_gemm_ass")
    expected.append("pf_gemm_acc")
    expected.append("pf_gemm_swi")
    expected.append("pf_gnrw_ass")
    expected.append("pf_gnrw_acc")
    expected.append("pf_gnrw_swi")

    var found = List[Int]()
    for _ in range(len(expected)):
        found.append(0)

    var failed = False
    for name in names:
        var matches = 0
        var which = -1
        for j in range(len(expected)):
            if name.find(expected[j]) >= 0:
                matches += 1
                which = j
        var old_role = _classify_pipeline(name)
        var old_splitk = _classify_splitk_pipeline(name)
        if matches != 1:
            print("FAIL:", name, "matched", matches, "expected patterns (want exactly 1)")
            failed = True
        elif old_role >= 0 or old_splitk >= 0:
            print(
                "FAIL:", name, "collides with an EXISTING classify pattern (role=",
                old_role, "splitk=", old_splitk, ")",
            )
            failed = True
        else:
            found[which] += 1

    for j in range(len(expected)):
        if found[j] != 1:
            print("FAIL: pattern", expected[j], "matched", found[j], "discovered pipelines (want exactly 1)")
            failed = True

    if failed:
        print("NAMING PROBE: FAIL")
    else:
        print("NAMING PROBE: PASS -- all six _pf_* names survive truncation, mutually distinct, no collision with existing roles")
