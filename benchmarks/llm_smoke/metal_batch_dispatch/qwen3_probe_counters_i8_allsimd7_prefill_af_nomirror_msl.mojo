"""qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl.mojo -- beat-llama.cpp campaign
(2026-08-08 night): per-role GPU-counter breakdown of the COMBINATION of the two landed kernel-side
levers -- `attention=PF_ATTN_GROUPED_FA_NO_MIRROR` (tier 2: the mirror-free AF prefill table
`self.descriptors_prefill_af_nomirror`, 8 per-layer dispatches, the with-mirror table's own 9th
dispatch `kvprod_mirror_af_d` and its ~5.95ms/prefill_batch() cost at m_rows=256 -- PROJECT_REDLINE_
TELEMETRY.md section A, REALRACE_RESULTS.md's Phase 3 entry -- absent from this table by
construction) PLUS `gemm=PF_GEMM_MSL_PARITY_ALL_ROLES` (tier 3: all four GEMM roles on the hand-
written MSL replicas of llama.cpp's kernel_mul_mm_f16_f32, mma_forge/generated/msl_parity_blob.c).
The Phase 3 MSL race entry's own ranked work queue names exactly this combination as the next
closable GPU work (its item (1): the kvprod/mirror complex, -5.95ms of it behind the mirror); this
probe measures, per role, whether the combination lands that closure, BEFORE any race entry cites
the number.

Copy-and-extend of `qwen3_probe_counters_i8_allsimd7_prefill_af_msl.mojo` (left completely
unmodified by this file), transformed exactly the way `qwen3_probe_counters_i8_allsimd7_prefill_
af.mojo` became `qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror.mojo`: drop the `_R_KVPROD_
MIRROR` role slot, renumber the six roles after it,
dispatch `s.descriptors_prefill_af_nomirror` through `s._apply_m_rows_af_nomirror`, read the MSL
dispatch-table readback off the `*_af2_d` per-role descriptor-index lists (the no-mirror table's own
bookkeeping). Everything else is byte-for-byte the MSL probe's own protocol: N_PRECONDITION=5 untimed
batches, N_SAMPLES=8 timed reps, M_ROWS=256 only, the three-MSL-pipelines-REQUIRED refusal, and the
plan-resolution hard gate (now asserting attention resolves to 2 = PF_ATTN_GROUPED_FA_NO_MIRROR).

Decode is irrelevant here, stated for the record: this probe measures PREFILL only and never calls
`step()`/`step_native_kv()`, so the no-mirror plan's decode-side contract (the natural F32 `ck`/`cv`
cache stays genuinely unwritten; decode must route through `_step_native_kv_impl`, whose kernel
`attention_forge/generated/native_kv_decode_attn_blob.c` is NOT required to be linked into THIS
binary) never engages. The ~2.87x decode collapse the ledger documents for the naive native decode
kernel is therefore not in scope for this measurement; the split-K occupancy variant that unblocks
promoting the no-mirror plan is separate work.

Needs the SAME forged blobs the with-mirror MSL probe links -- `mm8_blob.c` (the non-GEMM roles +
the original-tier pipelines discovery requires), the three vecload4 blobs (in-tier fallback
availability, matching the raced driver's binary), `msl_parity_blob.c`, and the two `attention_
forge` blobs -- with the counter-sampling shim:

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/probe_msl/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl.mojo \
        -o /tmp/probe_msl/probe_counters_prefill_af_nomirror_msl \
        -Xlinker /tmp/probe_msl/batch_shim_counters.o -Xlinker /tmp/msl_p3_build/mm8_blob.o \
        -Xlinker /tmp/msl_p3_build/mm8_vecload4_blob.o \
        -Xlinker /tmp/msl_p3_build/mm8_accum_vecload4_blob.o \
        -Xlinker /tmp/msl_p3_build/mm8_swiglu_vecload4_blob.o \
        -Xlinker /tmp/msl_p3_build/msl_parity_blob.o \
        -Xlinker /tmp/msl_p3_build/candidate_a_blob.o \
        -Xlinker /tmp/msl_p3_build/native_kv_producer_blob.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      /tmp/probe_msl/probe_counters_prefill_af_nomirror_msl
"""

from std.ffi import external_call
from std.memory import alloc
from std.builtin.type_aliases import MutAnyOrigin
from std.sys import has_accelerator, argv
from std.time import perf_counter_ns
from json.parser import json_get_object, json_get_int, json_get_float
from attnk.rope import rope_table
from conv import parse_int
from metaldispatch.contract import MB_OK, metaldispatch_status_name
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import MB_DESC_STRIDE, _mb_pipeline_name, _mb_run_token
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill, PREFILL_MAX_TILE
from metaldispatch.session_prefill_policy import (
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    UnresolvedPrefillConfig,
)

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke_8k/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke_8k/weights.blob"

comptime N_SAMPLES: Int = 8
"""Identical convention to `qwen3_probe_counters_i8_allsimd7_prefill_af.mojo`'s own -- one AF prefill
dispatch batch already spans `1 + n_layers*8 + 2` = 226 descriptors covering up to 512 rows each, so
a single sample is already far more GPU work than one decode token; 8 keeps one timed block short
enough to stay inside one DVFS regime while still averaging per-rep jitter."""

comptime N_PRECONDITION: Int = 5
"""UNTIMED prefill batches at m_rows=256 before the timed block -- the end-to-end race harness's own
WARMUP_PREFILL=5 preconditioning count (its docstring's rationale: one 256-row batch is 226
dispatches, already far past this GPU's ~8-dispatch DVFS ramp; 5 leaves margin)."""

comptime M_ROWS_DEFAULT: Int = 256
"""The row count this probe measures when no argv override is given. Beat-llama.cpp campaign
(2026-08-12): now overridable as `argv[1]` so ONE build can sweep the per-chunk dispatch gap at any
m_rows up to PREFILL_MAX_TILE (the tile-lever experiments need 512/1024/2048 from a single binary
instead of a rebuild-per-row-count). 256 stays the default = the raced shape itself (the 256-token
manifest prompt the final race entry pinned at 3,180.0 tok/s for this exact arm, and the shape the
Amdahl-vs-llama.cpp arithmetic targets)."""

comptime _R_EMBED: Int = 0
comptime _R_RMSNORM: Int = 1
comptime _R_GEMM_ASSIGN: Int = 2
comptime _R_KVPROD: Int = 3
comptime _R_ATTN: Int = 4
comptime _R_GEMV_O: Int = 5
comptime _R_RMSNORM2: Int = 6
comptime _R_SWIGLU: Int = 7
comptime _R_GEMV_DOWN: Int = 8
comptime _R_LMHEAD_ARGMAX: Int = 9
comptime _R_ARGMAX_REDUCE: Int = 10
comptime _N_ROLES_PREFILL_AF_NOMIRROR: Int = 11
"""Naive-producer pattern (8 per layer). The V2 pattern below (9 per layer) is what the session
builds when `kvprod_v2_blob.c` is linked -- the probe selects between them at runtime off
`s.kvprod_v2_built`."""

comptime _R_KVPROD_Q_V2: Int = 4
comptime _R_ATTN_V2: Int = 5
comptime _R_GEMV_O_V2: Int = 6
comptime _R_RMSNORM2_V2: Int = 7
comptime _R_SWIGLU_V2: Int = 8
comptime _R_GEMV_DOWN_V2: Int = 9
comptime _R_LMHEAD_ARGMAX_V2: Int = 10
comptime _R_ARGMAX_REDUCE_V2: Int = 11
comptime _N_ROLES_PREFILL_AF_NOMIRROR_V2: Int = 12
"""Same 12 roles as `qwen3_probe_counters_i8_allsimd7_prefill_af.mojo` -- the MSL-parity substitution
changes WHICH kernel runs inside four of these roles (gemm_assign, gemv_o, swiglu, gemv_down), not
the role inventory itself."""


def _mb_counters_supported() -> Int:
    return Int(external_call["algenta_counters_supported", Int64]())


def _mb_timestamp_frequency() -> UInt64:
    return external_call["algenta_timestamp_frequency", UInt64]()


def _mb_sample_gpu_timestamp() -> UInt64:
    return external_call["algenta_sample_gpu_timestamp", UInt64]()


def _calibrate_gpu_tick_ns(hold_ms: Int) raises -> Float64:
    var t_wall0 = perf_counter_ns()
    var gpu0 = _mb_sample_gpu_timestamp()
    var deadline = t_wall0 + UInt(hold_ms) * 1_000_000
    while perf_counter_ns() < deadline:
        pass
    var gpu1 = _mb_sample_gpu_timestamp()
    var t_wall1 = perf_counter_ns()
    if gpu1 <= gpu0:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: GPU timestamp calibration did not advance")
    var wall_seconds = Float64(Int(t_wall1 - t_wall0)) / 1.0e9
    var tick_rate_hz = Float64(gpu1 - gpu0) / wall_seconds
    return 1.0e9 / tick_rate_hz


def _mb_open_counters(max_samples: Int) -> Int:
    return Int(external_call["algenta_open_counters", Int64, Int64](Int64(max_samples)))


def _mb_run_token_counters(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin],
    n: Int,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
) -> Int:
    return Int(
        external_call[
            "algenta_run_token_counters", Int64,
            UnsafePointer[UInt8, origin=MutAnyOrigin], Int64,
            UnsafePointer[UInt64, origin=MutAnyOrigin],
        ](descriptors, Int64(n), out_ticks)
    )


def _role_name_af_nomirror(role: Int, v2: Bool) -> String:
    if v2:
        if role == _R_EMBED:
            return "pf_embed_rows"
        if role == _R_RMSNORM:
            return "pf_rmsnorm_rows"
        if role == _R_GEMM_ASSIGN:
            return "gemm_assign (qkv_proj, MSL parity)"
        if role == _R_KVPROD:
            return "kvprod_blk (kvprod_v2 KV pass, replaces naive producer)"
        if role == _R_KVPROD_Q_V2:
            return "kvprod_qvec (kvprod_v2 Q pass)"
        if role == _R_ATTN_V2:
            return "grouped_fa_attn (Candidate A, replaces pf_attn_tiled)"
        if role == _R_GEMV_O_V2:
            return "gemv_o (o_proj, MSL parity accum)"
        if role == _R_RMSNORM2_V2:
            return "pf_rmsnorm_rows (ffn)"
        if role == _R_SWIGLU_V2:
            return "swiglu (fused gate+up, MSL parity)"
        if role == _R_GEMV_DOWN_V2:
            return "gemv_down (down_proj, MSL parity accum)"
        if role == _R_LMHEAD_ARGMAX_V2:
            return "lmhead_argmax (unmodified, row M-1)"
        if role == _R_ARGMAX_REDUCE_V2:
            return "argmax_reduce (unmodified)"
        return "UNKNOWN"
    if role == _R_EMBED:
        return "pf_embed_rows"
    if role == _R_RMSNORM:
        return "pf_rmsnorm_rows"
    if role == _R_GEMM_ASSIGN:
        return "gemm_assign (qkv_proj, MSL parity)"
    if role == _R_KVPROD:
        return "native_kv_producer (AF, replaces ropewrt, NO mirror follows)"
    if role == _R_ATTN:
        return "grouped_fa_attn (Candidate A, replaces pf_attn_tiled)"
    if role == _R_GEMV_O:
        return "gemv_o (o_proj, MSL parity accum)"
    if role == _R_RMSNORM2:
        return "pf_rmsnorm_rows (ffn)"
    if role == _R_SWIGLU:
        return "swiglu (fused gate+up, MSL parity)"
    if role == _R_GEMV_DOWN:
        return "gemv_down (down_proj, MSL parity accum)"
    if role == _R_LMHEAD_ARGMAX:
        return "lmhead_argmax (unmodified, row M-1)"
    if role == _R_ARGMAX_REDUCE:
        return "argmax_reduce (unmodified)"
    return "UNKNOWN"


def _build_role_table_prefill_af_nomirror(n_layers: Int, n_descriptors: Int, v2: Bool) raises -> List[Int]:
    """Same per-layer dispatch ORDER as `qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror.
    mojo`'s own `_build_role_table_prefill_af_nomirror` (which mirrors `_build_descriptors_prefill_
    af_nomirror`'s source): rmsnorm, gemm_assign, native-KV-producer, grouped-FA attn, gemv_o,
    rmsnorm2, swiglu, gemv_down -- 8 per layer, `1 + n_layers*8 + 2` total (one FEWER than the
    with-mirror MSL probe's own 9 -- no kvprod_mirror slot at all)."""
    var roles = List[Int](capacity=n_descriptors)
    roles.append(_R_EMBED)
    for _ in range(n_layers):
        roles.append(_R_RMSNORM)
        roles.append(_R_GEMM_ASSIGN)
        roles.append(_R_KVPROD)
        if v2:
            roles.append(_R_KVPROD_Q_V2)
            roles.append(_R_ATTN_V2)
            roles.append(_R_GEMV_O_V2)
            roles.append(_R_RMSNORM2_V2)
            roles.append(_R_SWIGLU_V2)
            roles.append(_R_GEMV_DOWN_V2)
        else:
            roles.append(_R_ATTN)
            roles.append(_R_GEMV_O)
            roles.append(_R_RMSNORM2)
            roles.append(_R_SWIGLU)
            roles.append(_R_GEMV_DOWN)
    roles.append(_R_LMHEAD_ARGMAX_V2 if v2 else _R_LMHEAD_ARGMAX)
    roles.append(_R_ARGMAX_REDUCE_V2 if v2 else _R_ARGMAX_REDUCE)
    if len(roles) != n_descriptors:
        raise Error(
            "qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: built " + String(len(roles)) + " role slots but "
            + "the session says " + String(n_descriptors) + " descriptors"
        )
    return roles^


def _pipeline_name_or_missing(idx: Int) raises -> String:
    if idx < 0:
        return "<not discovered>"
    var name = String()
    _ = _mb_pipeline_name(idx, name)
    return name


def _descriptor_pipeline_idx(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], desc_idx: Int
) -> Int:
    """Reads back `AlgentaDispatchDesc.pipeline_idx` (the int32 `_mb_set_header` writes at byte 0 of
    each descriptor slot) -- the dispatch table's OWN record of which pipeline slot `desc_idx` will
    run, read directly from the table rather than re-derived from routing logic."""
    return Int((descriptors + desc_idx * MB_DESC_STRIDE).bitcast[Int32]()[0])


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _check_mb(status: Int) raises:
    if status != MB_OK:
        raise Error(
            "qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: metaldispatch call failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
        )


def _verify_msl_dispatch_table(
    s: _MBQwen3I8AllSimd7Prefill, n_layers: Int
) raises -> Bool:
    """READS BACK every GEMM descriptor's pipeline_idx from `s.descriptors_prefill_af_nomirror` after
    `_apply_m_rows_af_nomirror` ran, and checks all four GEMM roles of ALL layers point at the MSL parity
    kernels (qkv_proj -> `msl_parity_qkv_proj_pipeline_idx`, o_proj/down_proj -> `msl_parity_gemm_
    accum_pipeline_idx` OR, when `msl_splitk_blob.c` is linked, the front-2-fourth-strike split-K
    kernels `msl_splitk8_pipeline_idx`/`msl_splitk12_pipeline_idx`, swiglu -> `msl_parity_swiglu_
    pipeline_idx`) -- plus the two AF attention roles of layer 0 as a structural sanity check.
    Returns True iff every slot matches. This is the check that makes "the counters measured the
    MSL parity kernels" a property of THIS run."""
    var ok = True
    var n_checked = 0
    for layer in range(n_layers):
        var expected_assign = s.msl_parity_qkv_proj_pipeline_idx
        var expected_accum = s.msl_parity_gemm_accum_pipeline_idx
        var expected_swiglu = s.msl_parity_swiglu_pipeline_idx
        var got_assign = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.gemm_assign_af2_d[layer])
        var got_o = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.gemv_o_af2_d[layer])
        var got_sw = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.swiglu_af2_d[layer])
        var got_down = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.gemv_down_af2_d[layer])
        n_checked += 4
        if got_assign != expected_assign:
            print("  DISPATCH-TABLE MISMATCH layer", layer, "gemm_assign: got", got_assign,
                  "expected(MSL)", expected_assign)
            ok = False
        if got_o != expected_accum and got_o != s.msl_splitk8_pipeline_idx:
            print("  DISPATCH-TABLE MISMATCH layer", layer, "gemv_o: got", got_o,
                  "expected(MSL accum or splitk8)", expected_accum, "/", s.msl_splitk8_pipeline_idx)
            ok = False
        if got_sw != expected_swiglu:
            print("  DISPATCH-TABLE MISMATCH layer", layer, "swiglu: got", got_sw,
                  "expected(MSL)", expected_swiglu)
            ok = False
        if got_down != expected_accum and got_down != s.msl_splitk12_pipeline_idx:
            print("  DISPATCH-TABLE MISMATCH layer", layer, "gemv_down: got", got_down,
                  "expected(MSL accum or splitk12)", expected_accum, "/", s.msl_splitk12_pipeline_idx)
            ok = False
    # Layer-0 structural sanity: attn slot = grouped-FA pipeline, kvprod slot = EITHER the naive
    # native-KV-producer pipeline (index 0 of `af_pipeline_idx`) OR the campaign's V2 block-
    # cooperative KV pipeline (`kvprod_blk_pipeline_idx`) -- the session builds the latter into
    # this slot when `kvprod_v2_blob.c` is linked (see `session_prefill.mojo`'s Phase C wiring).
    var got_attn = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.attn_af2_d[0])
    var got_kv = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.kvprod_af2_d[0])
    n_checked += 2
    if got_attn != s.af_pipeline_idx[1]:
        print("  DISPATCH-TABLE MISMATCH layer 0 attn: got", got_attn,
              "expected(grouped_fa)", s.af_pipeline_idx[1])
        ok = False
    if got_kv != s.af_pipeline_idx[0] and got_kv != s.kvprod_blk_pipeline_idx:
        print("  DISPATCH-TABLE MISMATCH layer 0 kvprod: got", got_kv,
              "expected(native_kv_producer or kvprod_v2 blk)", s.af_pipeline_idx[0],
              "/", s.kvprod_blk_pipeline_idx)
        ok = False
    print("  kvprod producer wired:",
          "kvprod_v2 (blk-coop)" if got_kv == s.kvprod_blk_pipeline_idx else "naive")
    if s.kvprod_v2_built:
        var got_q = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.kvprod_q_af2_d[0])
        n_checked += 1
        if got_q != s.kvprod_qvec_pipeline_idx:
            print("  DISPATCH-TABLE MISMATCH layer 0 kvprod_qvec: got", got_q,
                  "expected(kvprod_v2 qvec)", s.kvprod_qvec_pipeline_idx)
            ok = False
    var got_o0 = _descriptor_pipeline_idx(s.descriptors_prefill_af_nomirror, s.gemv_o_af2_d[0])
    print("  gemv_o/down kernels:",
          "splitk8/splitk12 (GPU-fill)" if got_o0 == s.msl_splitk8_pipeline_idx else "MSL parity accum")
    print("  dispatch-table readback:", n_checked, "descriptors checked,",
          "all MSL/AF selections confirmed" if ok else "MISMATCHES FOUND")
    return ok


def _sample_at_m_rows_af_nomirror(
    mut s: _MBQwen3I8AllSimd7Prefill,
    m_rows: Int,
    n_layers: Int,
    n_descriptors: Int,
    roles: List[Int],
    ns_per_tick: Float64,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
    mut role_avg_ms_out: List[Float64],
    n_roles: Int,
) raises -> Float64:
    """Same mechanism as `qwen3_probe_counters_i8_allsimd7_prefill_af.mojo`'s own `_sample_at_m_rows_
    af`: `_apply_m_rows_af_nomirror` narrows the production AF table to `m_rows`, then `algenta_run_token_
    counters` dispatches it N_SAMPLES times with per-dispatch GPU timestamp counters."""
    var role_total_ns = List[Float64](capacity=n_roles)
    for _ in range(n_roles):
        role_total_ns.append(0.0)
    s._apply_m_rows_af_nomirror(m_rows, 0)
    var ids_i32 = s.prompt_ids_ptr.bitcast[Int32]()
    for m in range(m_rows):
        ids_i32[m] = Int32(13)  # any valid vocab id -- correctness is not this probe's question
    var wall_total_ms = 0.0
    for _ in range(N_SAMPLES):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors_prefill_af_nomirror, n_descriptors, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: algenta_run_token_counters failed")
        wall_total_ms += Float64(Int(t1 - t0)) / 1.0e6
        for d in range(n_descriptors):
            var start_tick = out_ticks[2 * d]
            var end_tick = out_ticks[2 * d + 1]
            if end_tick >= start_tick:
                role_total_ns[roles[d]] += Float64(end_tick - start_tick) * ns_per_tick
    for role in range(n_roles):
        role_avg_ms_out[role] = role_total_ns[role] / Float64(N_SAMPLES) / 1.0e6
    return wall_total_ms / Float64(N_SAMPLES)


def main() raises:
    # Beat-llama.cpp campaign (2026-08-12): argv[1] overrides the measured row count so ONE build
    # sweeps the per-chunk dispatch gap across the tile lever's shapes (512/1024/2048).
    var m_rows = M_ROWS_DEFAULT
    var args = argv()
    if len(args) > 1:
        m_rows = parse_int(String(args[1]))
    if m_rows < 1 or m_rows > PREFILL_MAX_TILE:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: m_rows out of [1, PREFILL_MAX_TILE]")

    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var theta = json_get_float(config, "rope_theta", -1.0)
    var eps = json_get_float(config, "rms_norm_eps", -1.0)
    var n_prompt = json_get_int(config, "n_tokens", -1)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1 or n_prompt < 1:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = 9216

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 2, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: no accelerator on this host")
            return

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _MBQwen3I8AllSimd7Prefill(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        print("  n_cores detected:", s.n_cores)

        # ── Same AF-blob guard as the AF probe (checked by INDEX, same convention): if the two
        # `attention_forge/` blobs were not linked, `descriptors_prefill_af_nomirror` was never built.
        var af_pipelines_present = (s.af_pipeline_idx[0] >= 0 and s.af_pipeline_idx[1] >= 0)
        print("  (attention_forge blobs linked into this binary:", af_pipelines_present, ")")
        if not af_pipelines_present:
            print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: attention_forge blobs not linked -- "
                  "rebuild with candidate_a_blob.o + native_kv_producer_blob.o (see module docstring).")
            return

        # ── MSL parity pipeline availability, REQUIRED here (see module docstring for why the
        # engine's own legitimate per-role graceful fallback is refused in a counter probe).
        print("  (MSL parity pipelines linked: qkv_proj idx", s.msl_parity_qkv_proj_pipeline_idx,
              ", accum idx", s.msl_parity_gemm_accum_pipeline_idx,
              ", swiglu idx", s.msl_parity_swiglu_pipeline_idx, ")")
        if s.msl_parity_qkv_proj_pipeline_idx < 0 or s.msl_parity_gemm_accum_pipeline_idx < 0 \
           or s.msl_parity_swiglu_pipeline_idx < 0:
            print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: one or more MSL parity metallibs "
                  "not linked -- rebuild with msl_parity_blob.o (mma_forge/tools/"
                  "build_msl_parity_blob.sh; see module docstring). Refusing to sample: a silent "
                  "per-role fallback to the vecload4/original kernels would contaminate this "
                  "breakdown.")
            return

        # ── THE plan under test: no-mirror attention (tier 2) + MSL-parity GEMM (tier 3) -- the
        # two landed levers combined; resolve_plan's own availability gate applies (missing blobs
        # would degrade attention to OFF, caught by the hard gate below).
        s.resolve_plan(UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_MSL_PARITY_ALL_ROLES))
        print("  resolved plan: attention =", s.plan.attention,
              "(2 = PF_ATTN_GROUPED_FA_NO_MIRROR), gemm =", s.plan.gemm,
              "(3 = PF_GEMM_MSL_PARITY_ALL_ROLES)")
        if s.plan.attention != PF_ATTN_GROUPED_FA_NO_MIRROR \
           or s.plan.gemm != PF_GEMM_MSL_PARITY_ALL_ROLES:
            print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: plan did not resolve to the "
                  "requested MSL-parity combination -- refusing to sample (this is the probe's own "
                  "hard gate; the graceful blobs-absent fallback belongs to the production session, "
                  "and is proven separately by the driver-level blobs-absent build).")
            return

        # Which kernels will actually run, by the Metal function names the shim itself resolved:
        print("  kernel qkv_proj MSL       :", _pipeline_name_or_missing(s.msl_parity_qkv_proj_pipeline_idx))
        print("  kernel accum MSL          :", _pipeline_name_or_missing(s.msl_parity_gemm_accum_pipeline_idx))
        print("  kernel swiglu MSL         :", _pipeline_name_or_missing(s.msl_parity_swiglu_pipeline_idx))
        print("  kernel native_kv_producer :", _pipeline_name_or_missing(s.af_pipeline_idx[0]))
        print("  kernel grouped_fa_attn    :", _pipeline_name_or_missing(s.af_pipeline_idx[1]))

        var rt = rope_table(d_head, max_ctx, theta)
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check_mb(s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx))

        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "input_layernorm.weight")
            var ln2 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "post_attention_layernorm.weight")
            var qn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_norm.weight")
            var kn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_norm.weight")
            var wq = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_proj.weight")
            var wk = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_proj.weight")
            var wv = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.v_proj.weight")
            var wo = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.o_proj.weight")
            var wg = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.gate_proj.weight")
            var wu = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.up_proj.weight")
            var wd = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.down_proj.weight")
            _check_mb(s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd))
        _ = s.seal()
        print("  weights loaded + sealed")

        # Same reasoning as the AF probe's own identical call: makes the split-K kernels statically
        # reachable from this binary, required by `__init__`'s own unconditional pipeline_idx_split/
        # merge check.
        s._ensure_deep_initialized()

        var v2 = s.kvprod_v2_built
        var n_roles = _N_ROLES_PREFILL_AF_NOMIRROR_V2 if v2 else _N_ROLES_PREFILL_AF_NOMIRROR
        print("  kvprod V2 producer linked:", v2)
        var roles = _build_role_table_prefill_af_nomirror(n_layers, s.n_descriptors_prefill_af_nomirror, v2)

        var supported = _mb_counters_supported()
        if supported != 1:
            print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: counter sampling not available, status=", supported)
            return
        var ns_per_tick = _calibrate_gpu_tick_ns(200)
        print("  calibrated ns/tick:", ns_per_tick)
        var counters_rc = _mb_open_counters(2 * s.n_descriptors_prefill_af_nomirror)
        if counters_rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: algenta_open_counters failed, rc=" + String(counters_rc))
        var out_ticks = alloc[UInt64](2 * s.n_descriptors_prefill_af_nomirror)

        # ── Narrow the production AF table to the raced shape ONCE, then verify the dispatch table
        # really selects the MSL parity kernels BEFORE any timed sample is trusted.
        s._apply_m_rows_af_nomirror(m_rows, 0)
        var ids_i32 = s.prompt_ids_ptr.bitcast[Int32]()
        for m in range(m_rows):
            ids_i32[m] = Int32(13)
        var table_ok = _verify_msl_dispatch_table(s, n_layers)
        if not table_ok:
            print("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: dispatch-table verification "
                  "FAILED -- refusing to sample.")
            return

        # ── Preconditioning: 5 UNTIMED prefill batches at the raced shape, through the production
        # fast-path dispatch call (`algenta_run_token`, byte-identical twin of `batch_shim.m`'s),
        # BEFORE any timed counter sample -- the race harness's own WARMUP_PREFILL discipline.
        for _ in range(N_PRECONDITION):
            var rc = _mb_run_token(s.descriptors_prefill_af_nomirror, s.n_descriptors_prefill_af_nomirror)
            if rc != 0:
                raise Error("qwen3_probe_counters_i8_allsimd7_prefill_af_nomirror_msl: preconditioning run failed")
        print("  preconditioning done:", N_PRECONDITION, "untimed prefill batches at m_rows=", m_rows)

        print("")
        print("=== [AF-nomirror+MSL parity, Phase 3 opt-in] sampling at m_rows=", m_rows, "(", N_SAMPLES, "reps) ===")
        var role_ms = List[Float64](capacity=n_roles)
        for _ in range(n_roles):
            role_ms.append(0.0)
        var wall_ms = _sample_at_m_rows_af_nomirror(
            s, m_rows, n_layers, s.n_descriptors_prefill_af_nomirror, roles, ns_per_tick, out_ticks, role_ms,
            n_roles
        )
        var total_ms = 0.0
        for role in range(n_roles):
            total_ms += role_ms[role]
        for role in range(n_roles):
            var pct = (role_ms[role] / total_ms * 100.0) if total_ms > 1.0e-9 else -1.0
            print("  ", _role_name_af_nomirror(role, v2), ":", role_ms[role], "ms  (", pct, "% of GPU-time total)")
        print("  TOTAL (sum of per-dispatch GPU time):", total_ms, "ms")
        print("  whole-batch wall time (host-measured):", wall_ms, "ms")
        var gpu_vs_wall_gap_ms = wall_ms - total_ms
        var gpu_vs_wall_gap_pct = (gpu_vs_wall_gap_ms / wall_ms * 100.0) if wall_ms > 1.0e-9 else -1.0
        print("  GPU-sum vs wall-time gap:", gpu_vs_wall_gap_ms, "ms  (",
              gpu_vs_wall_gap_pct, "% of wall time not accounted for by summed per-dispatch GPU time)")
        var tok_per_sec = Float64(m_rows) / (wall_ms / 1000.0)
        print("  implied tok/s at this m_rows in isolation:", tok_per_sec)
