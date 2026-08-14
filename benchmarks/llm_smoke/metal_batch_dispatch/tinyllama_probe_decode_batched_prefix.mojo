"""tinyllama_probe_decode_batched_prefix.mojo -- feat/batched-llama (2026-08-14): hang bisection
probe. Opens a REAL TinyLlama session (d_head=64, qk_norm=0, untied lm_head), builds the session's
own `descriptors_decode_batched` table via `_ensure_decode_batched_ready(B)`, then dispatches
PREFIXES of it (`_mb_run_token(table, k)` for increasing k) -- the smallest k that hangs names the
faulting descriptor. Descriptor roles: idx 0 = embed; per layer (9): rms1, qkv, kvprod_batched,
attn PARTIAL, attn MERGE, o_proj, rms2, swiglu-unit (1 or 3 with split-K), down_proj; tail (3+):
final rmsnorm, lm_head (+blockmax with the GEMM tier), argmax reduce.

    argv[1] = B      (default 2)
    argv[2] = depth  (default 85)

    cd /Users/angel/Developer/decision-engine-batched-llama/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -D ALGENTA_STAGE_6144 -I ../mojo/engine \\
        ../benchmarks/llm_smoke/metal_batch_dispatch/tinyllama_probe_decode_batched_prefix.mojo \\
        -o /tmp/probe_tinyllama_db/prefix_probe \\
        -Xlinker /tmp/probe_db/batch_shim.o -Xlinker <blob .o set> \\
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \\
        -Xlinker -framework -Xlinker IOKit
    /tmp/probe_tinyllama_db/prefix_probe 2 85
"""

from std.sys import argv
from std.time import perf_counter_ns
from std.ffi import external_call
from std.math import sqrt
from json.parser import json_get_object, json_get_int, json_get_float
from conv import parse_int
from attnk.rope import rope_table
from metaldispatch.contract import MB_OK
from metaldispatch.ffi import MB_DESC_STRIDE, _mb_alloc_descriptors, _mb_pipeline_name, _mb_set_arg_int
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill
from metaldispatch.qwen3_prefill_decode import qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl
from metaldispatch.session_prefill_policy import (
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_ATTN_OFF,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    PF_GEMM_ORIGINAL,
    UnresolvedPrefillConfig,
)

comptime MANIFEST_PATH: String = "/private/tmp/tinyllama/.algenta-cache/manifest.json"
comptime BLOB_PATH: String = "/private/tmp/tinyllama/.algenta-cache/weights.blob"
comptime MAX_CTX: Int = 512


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
        raise Error("prefix_probe: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    var f = open(blob_path, "r")
    _ = f.seek(UInt64(loc.offset * 8))
    var out = List[Float64](capacity=loc.n_elements)
    var raw = f.read_bytes(loc.n_elements * 8)
    f.close()
    if len(raw) != loc.n_elements * 8:
        raise Error("prefix_probe: short read for " + name)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(loc.n_elements):
        out.append(fp[i])
    return out^


def _mb_run_token(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], n: Int,
) -> Int:
    return Int(
        external_call[
            "algenta_run_token", Int64,
            UnsafePointer[UInt8, origin=MutAnyOrigin], Int64,
        ](descriptors, Int64(n))
    )


def _mb_open_session() -> Int:
    return Int(external_call["algenta_open_session", Int64]())


def _role_name(idx: Int, n_layers: Int, splitk_qkv: Int, splitk_swiglu: Int, lmhead_gemm: Int) -> String:
    if idx == 0:
        return "embed"
    var d = idx - 1
    var per_layer = 9 + splitk_qkv + (2 if splitk_swiglu == 1 else 0)
    var tail = 3 + (1 if lmhead_gemm == 1 else 0)
    if d >= n_layers * per_layer:
        var t = d - n_layers * per_layer
        if t == 0:
            return "tail:final_rmsnorm"
        if lmhead_gemm == 1:
            if t == 1:
                return "tail:msl_lmhead_gemm"
            if t == 2:
                return "tail:msl_logits_blockmax"
            return "tail:argmax_reduce"
        if t == 1:
            return "tail:batched_lmhead"
        return "tail:argmax_reduce"
    var layer = d // per_layer
    var r = d % per_layer
    if splitk_qkv == 1 and splitk_swiglu == 1:
        # per layer: rms1, zero_qkv, splitk8_qkv, kvprod, partial, merge, o, rms2, zero_sw,
        # splitk4_sw, apply_sw, down
        if r == 0:
            return "L" + String(layer) + ":rms1"
        if r == 1:
            return "L" + String(layer) + ":zero_qkv"
        if r == 2:
            return "L" + String(layer) + ":splitk8_qkv"
        if r == 3:
            return "L" + String(layer) + ":kvprod_batched"
        if r == 4:
            return "L" + String(layer) + ":attn_partial"
        if r == 5:
            return "L" + String(layer) + ":attn_merge"
        if r == 6:
            return "L" + String(layer) + ":o_proj"
        if r == 7:
            return "L" + String(layer) + ":rms2"
        if r == 8:
            return "L" + String(layer) + ":zero_swiglu"
        if r == 9:
            return "L" + String(layer) + ":splitk4_swiglu"
        if r == 10:
            return "L" + String(layer) + ":swiglu_apply"
        return "L" + String(layer) + ":down_proj"
    return "L" + String(layer) + ":role" + String(r)


def _desc_info(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], idx: Int,
) raises -> String:
    var base = (descriptors + idx * MB_DESC_STRIDE).bitcast[Int32]()
    var pidx = Int(base[0])
    var grid = Int(base[1])
    var threads = Int(base[2])
    var nargs = Int(base[3])
    var name = ""
    _ = _mb_pipeline_name(pidx, name)
    return (
        "desc[" + String(idx) + "] pipeline=" + String(pidx) + " (" + name
        + ") grid=" + String(grid) + " threads=" + String(threads) + " nargs=" + String(nargs)
    )


def _dump_f32(label: String, ptr: UnsafePointer[UInt8, origin=MutAnyOrigin], n: Int):
    var f = ptr.bitcast[Float32]()
    var s = label + ":"
    for i in range(n):
        s += " " + String(f[i])
    print(s)


def main() raises:
    var args = argv()
    # Keep the fresh-process entry reachable from main: AOT DCE otherwise drops the deep split-K
    # kernels `_ensure_deep_initialized` compiles, and the session constructor's discovery guard
    # raises (same discipline as qwen3_probe_counters_decode_batched.mojo's own ep arm).
    if len(args) > 1 and String(args[1]) == "ep":
        var r = qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl(
            "/tmp/qwen3smoke", 16, True, True, 2
        )
        print("ep status:", r.status)
        return
    var B = 2
    var depth = 85
    var cmp_mode = (
        len(args) > 1
        and (String(args[1]) == "cmpsingle" or String(args[1]) == "cmpbatch"
             or String(args[1]) == "cmpbatchx" or String(args[1]) == "tracesingle"
             or String(args[1]) == "tracebatch")
    )
    if len(args) > 1 and not cmp_mode:
        B = parse_int(String(args[1]))
    if len(args) > 2 and not cmp_mode:
        depth = parse_int(String(args[2]))

    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var eps = json_get_float(config, "rms_norm_eps", 1.0e-6)
    var theta = Float64(json_get_float(config, "rope_theta", 10000.0))
    var scale = 1.0 / sqrt(Float64(d_head))
    print("prefix_probe: d_model=", d_model, " h_q=", h_q, " h_kv=", h_kv, " d_head=", d_head,
          " d_ff=", d_ff, " layers=", n_layers, " vocab=", vocab_size)

    var tensors_obj = json_get_object(manifest, "tensors")
    # llama pairing: qk_norm=0, untied lm_head (the two trailing flags).
    var s = _MBQwen3I8AllSimd7Prefill(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale,
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
        0, 0,
    )
    s.resolve_plan(UnresolvedPrefillConfig(
        PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_MSL_PARITY_ALL_ROLES
    ))
    print("  resolved plan: attention =", s.plan.attention, " gemm =", s.plan.gemm)
    print("  decode_batched_built:", s.decode_batched_built)
    if not s.decode_batched_built:
        raise Error("prefix_probe: batched pipelines not all discovered")

    var rt = rope_table(d_head, MAX_CTX, theta)
    var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
    var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
    var up = s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX)
    if up != MB_OK:
        raise Error("prefix_probe: upload_globals failed")
    var lm_head_table = _load_tensor(BLOB_PATH, tensors_obj, "lm_head.weight")
    if s.upload_lm_head(lm_head_table) != MB_OK:
        raise Error("prefix_probe: upload_lm_head failed")
    for layer in range(n_layers):
        var prefix = "model.layers." + String(layer) + "."
        var ln1 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "input_layernorm.weight")
        var ln2 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "post_attention_layernorm.weight")
        var qn = List[Float64](capacity=d_head)
        var kn = List[Float64](capacity=d_head)
        for _i in range(d_head):
            qn.append(1.0)
            kn.append(1.0)
        var wq = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_proj.weight")
        var wk = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_proj.weight")
        var wv = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.v_proj.weight")
        var wo = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.o_proj.weight")
        var wg = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.gate_proj.weight")
        var wu = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.up_proj.weight")
        var wd = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.down_proj.weight")
        var ls = s.upload_layer(layer, ln1, ln2, qn^, kn^, wq, wk, wv, wo, wg, wu, wd)
        if ls != MB_OK:
            raise Error("prefix_probe: upload_layer failed: " + String(layer))
    _ = s.seal()
    print("  weights loaded + sealed")

    # ── cmpsingle / cmpbatch arms: the SAME 6-token prompt through the production single-stream
    # path (prefill_batch + step) vs the batched path (prefill_batch_batched_ingest + step_batched),
    # one process each; the shell diffs the printed tokens. Isolates the batched STEP math from the
    # SDK/runtime plumbing.
    if cmp_mode:
        var ids = List[Int]()
        ids.append(5115); ids.append(29892); ids.append(607); ids.append(338); ids.append(884); ids.append(278)
        var L = len(ids)
        if String(args[1]) == "cmpsingle":
            var r0 = s.prefill_batch(ids, 0)
            print("cmpsingle tok0:", r0.token_id, " status:", r0.status)
            _dump_f32("cmpsingle hidden_post_ingest", s.hidden_ptr, 8)
            var r1 = s.step(r0.token_id, L)
            print("cmpsingle tok1:", r1.token_id, " status:", r1.status)
            _dump_f32("cmpsingle hidden_post_step1", s.hidden_ptr, 8)
            var r2 = s.step(r1.token_id, L + 1)
            print("cmpsingle tok2:", r2.token_id, " status:", r2.status)
        elif String(args[1]) == "cmpbatchx":
            # Discriminator: NORMAL production prefill (populates the single-stream af K/V caches
            # and hidden), then memcpy those proven-correct caches into batched slot 0, then ONE
            # batched step. If this matches the single-stream token, the batched STEP math is
            # correct and any SDK-level divergence lives in the ingest retargeting; if it
            # diverges, the batched step itself is wrong with a known-good KV state.
            var r0 = s.prefill_batch(ids, 0)
            print("cmpbatchx tok0:", r0.token_id, " status:", r0.status)
            _dump_f32("cmpbatchx hidden_post_ingest", s.hidden_ptr, 8)
            var nbytes = s.batch_kv_stride_elems * 2
            for layer in range(s.n_layers):
                var dst = s.batch_ck_native_ptr[layer]
                var src = s.af_ck_native_ptr[layer]
                for i in range(nbytes):
                    dst[i] = src[i]
                var dst_v = s.batch_cv_native_ptr[layer]
                var src_v = s.af_cv_native_ptr[layer]
                for i in range(nbytes):
                    dst_v[i] = src_v[i]
            var t1 = List[Int](); t1.append(r0.token_id)
            var p1 = List[Int](); p1.append(L)
            var g1 = s.step_batched(t1, p1)
            print("cmpbatchx tok1:", g1[0])
            _dump_f32("cmpbatchx hidden_post_step1", s.hidden_ptr, 8)
        elif String(args[1]) == "tracesingle":
            # Per-layer hidden trace of ONE single-stream naive-native decode step (table layout:
            # 1 embed + 6 per layer + 2 tail). Setup identical to cmpsingle.
            var r0 = s.prefill_batch(ids, 0)
            print("tracesingle tok0:", r0.token_id)
            var table = s.descriptors_decode_native
            _mb_set_arg_int(table, s.token_id_offset_native, 3, r0.token_id)
            for layer in range(s.n_layers):
                _mb_set_arg_int(table, s.pos_offsets_native[layer], 8, L)
                _mb_set_arg_int(table, s.nkeys_offsets_native[layer], 4, L + 1)
            var n_desc_s = s.n_descriptors_decode_native
            _ = _mb_run_token(table, 1)
            _dump_f32("tracesingle hidden_embed", s.hidden_ptr, 4)
            for layer in range(s.n_layers):
                if layer == 0:
                    # sub-stage dumps: [1,5) = norm_gemv+kvprod+attn+o_gemv, [5,7) = swiglu+down
                    _ = _mb_run_token(table + 1 * MB_DESC_STRIDE, 4)
                    _dump_f32("tracesingle attn_out_L0_full", s.attn_out_ptr, s.h_q * s.d_head)
                    _dump_f32("tracesingle hidden_L0_postO_full", s.hidden_ptr, s.d_model)
                    _ = _mb_run_token(table + 5 * MB_DESC_STRIDE, 1)
                    _dump_f32("tracesingle act_L0_full", s.act_ptr, s.d_ff)
                    _dump_f32("tracesingle hidden_L0_preDown_full", s.hidden_ptr, s.d_model)
                    _ = _mb_run_token(table + 6 * MB_DESC_STRIDE, 1)
                    _dump_f32("tracesingle hidden_L0_full", s.hidden_ptr, s.d_model)
                    continue
                _ = _mb_run_token(table + (1 + layer * 6) * MB_DESC_STRIDE, 6)
                if layer == 1:
                    _dump_f32("tracesingle hidden_L" + String(layer) + "_full", s.hidden_ptr, s.d_model)
                elif layer < 4 or layer >= s.n_layers - 2:
                    _dump_f32("tracesingle hidden_L" + String(layer), s.hidden_ptr, 4)
            print("tracesingle dispatched layers; tail skipped (hidden trace only)")
        elif String(args[1]) == "tracebatch":
            # Per-layer hidden trace of ONE batched decode step over copied known-good KV caches
            # (cmpbatchx setup). Table layout: 1 embed + 12 per layer + tail.
            var r0 = s.prefill_batch(ids, 0)
            print("tracebatch tok0:", r0.token_id)
            var nbytes = s.batch_kv_stride_elems * 2
            for layer in range(s.n_layers):
                var dst = s.batch_ck_native_ptr[layer]
                var src = s.af_ck_native_ptr[layer]
                for i in range(nbytes):
                    dst[i] = src[i]
                var dst_v = s.batch_cv_native_ptr[layer]
                var src_v = s.af_cv_native_ptr[layer]
                for i in range(nbytes):
                    dst_v[i] = src_v[i]
            s._ensure_decode_batched_ready(1)
            var ids32t = s.prompt_ids_ptr.bitcast[Int32]()
            var poss64t = s.batch_poss_ptr.bitcast[Int64]()
            var nkeys64t = s.batch_nkeys_ptr.bitcast[Int64]()
            ids32t[0] = Int32(r0.token_id)
            poss64t[0] = Int64(L)
            nkeys64t[0] = Int64(L + 1)
            var table = s.descriptors_decode_batched
            _ = _mb_run_token(table, 1)
            _dump_f32("tracebatch hidden_embed", s.hidden_ptr, 4)
            for layer in range(s.n_layers):
                if layer == 0:
                    # batch L0 = descs [1,13): rms1,zero_qkv,splitk8_qkv,kvprod,partial,merge,
                    # o_proj,rms2,zero_sw,splitk4_sw,apply,down. Sub-stage dumps mirror the
                    # single-stream arm: through o_proj = [1,8), through down = [8,13).
                    _ = _mb_run_token(table + 1 * MB_DESC_STRIDE, 7)
                    _dump_f32("tracebatch attn_out_L0_full", s.attn_out_ptr, s.h_q * s.d_head)
                    _dump_f32("tracebatch hidden_L0_postO_full", s.hidden_ptr, s.d_model)
                    _ = _mb_run_token(table + 8 * MB_DESC_STRIDE, 4)
                    _dump_f32("tracebatch act_L0_full", s.act_ptr, s.d_ff)
                    _dump_f32("tracebatch hidden_L0_preDown_full", s.hidden_ptr, s.d_model)
                    _ = _mb_run_token(table + 12 * MB_DESC_STRIDE, 1)
                    _dump_f32("tracebatch hidden_L0_full", s.hidden_ptr, s.d_model)
                    continue
                _ = _mb_run_token(table + (1 + layer * 12) * MB_DESC_STRIDE, 12)
                if layer == 1:
                    _dump_f32("tracebatch hidden_L" + String(layer) + "_full", s.hidden_ptr, s.d_model)
                elif layer < 4 or layer >= s.n_layers - 2:
                    _dump_f32("tracebatch hidden_L" + String(layer), s.hidden_ptr, 4)
            print("tracebatch dispatched layers; tail skipped (hidden trace only)")
        else:
            var r0 = s.prefill_batch_batched_ingest(ids, 0)
            print("cmpbatch tok0:", r0.token_id, " status:", r0.status)
            _dump_f32("cmpbatch hidden_post_ingest", s.hidden_ptr, 8)
            var t1 = List[Int](); t1.append(r0.token_id)
            var p1 = List[Int](); p1.append(L)
            var g1 = s.step_batched(t1, p1)
            print("cmpbatch tok1:", g1[0])
            _dump_f32("cmpbatch hidden_post_step1", s.hidden_ptr, 8)
            var t2 = List[Int](); t2.append(g1[0])
            var p2 = List[Int](); p2.append(L + 1)
            var g2 = s.step_batched(t2, p2)
            print("cmpbatch tok2:", g2[0])
        return

    s._ensure_decode_batched_ready(B)
    var n_desc = s.n_descriptors_decode_batched
    print("  descriptors_decode_batched:", n_desc)

    var ids32 = s.prompt_ids_ptr.bitcast[Int32]()
    var poss64 = s.batch_poss_ptr.bitcast[Int64]()
    var nkeys64 = s.batch_nkeys_ptr.bitcast[Int64]()
    for b in range(B):
        ids32[b] = Int32(374)
        poss64[b] = Int64(depth)
        nkeys64[b] = Int64(depth + 1)

    # argv[3]/argv[4]: dispatch the descriptor RANGE [start, end) ONCE (default: the ascending
    # prefix sweep below). Names every descriptor in the range first, so a hang names its kernel.
    if len(args) > 4:
        var a = parse_int(String(args[3]))
        var z = parse_int(String(args[4]))
        for i in range(a, z):
            print("  ", _desc_info(s.descriptors_decode_batched, i))
        print("dispatching range [", a, ",", z, ") ...")
        var t0 = perf_counter_ns()
        # Range dispatch: shift the range to the front is impossible in place, so build a copy.
        var span = z - a
        var copy = _mb_alloc_descriptors(span)
        for i in range(span * MB_DESC_STRIDE):
            copy[i] = s.descriptors_decode_batched[a * MB_DESC_STRIDE + i]
        var rc = _mb_run_token(copy, span)
        var ms = Float64(Int(perf_counter_ns() - t0)) / 1.0e6
        print("  range [", a, ",", z, ") rc=", rc, " (", ms, " ms)")
        return

    # Print the descriptor map for the first layer + tail up front.
    for i in range(0, 14):
        print("  ", _desc_info(s.descriptors_decode_batched, i))

    # Prefix bisection: dispatch [0, k) for increasing k. Print BEFORE each dispatch so the last
    # printed line names the descriptor whose inclusion hangs the GPU.
    var k = 1
    while k <= n_desc:
        print("dispatching prefix [0,", k, ") ...")
        var t0 = perf_counter_ns()
        var rc = _mb_run_token(s.descriptors_decode_batched, k)
        var ms = Float64(Int(perf_counter_ns() - t0)) / 1.0e6
        if rc != 0:
            print("  prefix [0,", k, ") FAILED rc=", rc, " after ", ms, " ms")
            return
        print("  prefix [0,", k, ") ok (", ms, " ms)")
        k += 1
    print("ALL", n_desc, "descriptors dispatched without hanging")
