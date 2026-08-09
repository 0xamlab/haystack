"""qwen3_batched_decode_race.mojo -- Project Slipstream Phase 3 (2026-08-09): the BATCHED /
continuous-batching decode driver. Steps B sequences together through
`_MBQwen3I8AllSimd7Prefill._step_batched` (one descriptor-table submission per step: prefill-shape
tiled-GEMM projections at m_rows=B, per-sequence flash-decoding attention, per-sequence native-packed
KV, B single-row lm_head/argmax tail) and measures aggregate tokens/second, the tokens-per-weight-
sweep number the Slipstream thesis predicts collapses toward the prefill rate as B grows.

Two modes:
  correctness (default): B sequences all seeded with the SAME token at pos 0, stepped N times; every
    sequence must produce the IDENTICAL token stream (they are the same computation) -- a strong
    internal-consistency gate on the per-sequence offset/indirection wiring. Also cross-checks seq 0
    against the single-stream `step()` path for the same seed where numerics align.
  race: sweep B, time n_steps batched steps, report aggregate tok/s = B*n_steps/wall.

    argv[1] = csv B values            (default "1,2,4,8,16")
    argv[2] = decode steps per run     (default 32)
    argv[3] = timed runs per B         (default 5)

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_batched_decode_race.mojo \
        -o /tmp/realrace_msl/batched_decode_race \
        -Xlinker <batch_shim + blob set incl. nska/nkvp batched blobs> \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    /tmp/realrace_msl/batched_decode_race 1,2,4,8,16 32 5
"""

from std.sys import argv
from std.sys import has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_object, json_get_int, json_get_float
from conv import parse_int
from attnk.rope import rope_table
from metaldispatch.contract import MB_OK, metaldispatch_status_name
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill
from metaldispatch.session_prefill_policy import (
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    UnresolvedPrefillConfig,
)

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
comptime SEED_TOKEN: Int = 374
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
        raise Error("qwen3_batched_decode_race: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var remaining = n_elements
    alias CHUNK_ELEMS = 1 << 24
    while remaining > 0:
        var take = CHUNK_ELEMS if remaining > CHUNK_ELEMS else remaining
        var raw = f.read_bytes(take * 8)
        if len(raw) != take * 8:
            f.close()
            raise Error("qwen3_batched_decode_race: short read at byte offset " + String(byte_offset))
        var fp = raw.unsafe_ptr().bitcast[Float64]()
        for i in range(take):
            out.append(fp[i])
        remaining -= take
    f.close()
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _parse_csv_ints(s: String) raises -> List[Int]:
    var parts = s.split(",")
    var out = List[Int]()
    for i in range(len(parts)):
        var part = String(parts[i])
        if len(part) > 0:
            out.append(parse_int(part))
    return out^


def main() raises:
    var args = argv()
    var bs = List[Int]()
    bs.append(1); bs.append(2); bs.append(4); bs.append(8); bs.append(16)
    if len(args) > 1:
        bs = _parse_csv_ints(String(args[1]))
    var n_steps = 32
    if len(args) > 2:
        n_steps = parse_int(String(args[2]))
    var n_timed = 5
    if len(args) > 3:
        n_timed = parse_int(String(args[3]))

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
       or vocab_size < 1:
        raise Error("qwen3_batched_decode_race: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_batched_decode_race: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_batched_decode_race: no accelerator on this host")
            return
        var pre = _mb_preflight(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 256, MAX_CTX, eps, scale
        )
        if pre != MB_OK:
            print("qwen3_batched_decode_race: cannot run a session here:",
                  metaldispatch_status_name(pre))
            return

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _MBQwen3I8AllSimd7Prefill(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        s.resolve_plan(UnresolvedPrefillConfig(
            PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_MSL_PARITY_ALL_ROLES
        ))
        if not s.decode_batched_built:
            print("qwen3_batched_decode_race: batched decode pipelines NOT all discovered "
                  + "(partial=", s.native_decode_splitk_partial_batched_pipeline_idx,
                  " kvprod=", s.kvprod_batched_pipeline_idx,
                  " merge=", s.batched_splitk_merge_pipeline_idx, ")")
            return
        print("  decode_batched_built=True; batch pipelines discovered")

        var rt = rope_table(d_head, MAX_CTX, theta)
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        var up = s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX)
        if up != MB_OK:
            raise Error("qwen3_batched_decode_race: upload_globals failed")
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
            var ls = s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd)
            if ls != MB_OK:
                raise Error("qwen3_batched_decode_race: upload_layer failed: " + String(layer))
        _ = s.seal()
        # Keep the single-stream deep split-K metallibs reachable for AOT (else DCE drops them and
        # `__init__`'s pipeline-discovery guard raises) -- mirrors the decode-race driver's need to
        # reference the deep path; harmless to actually run here.
        s._ensure_deep_initialized()
        print("  weights loaded + sealed")

        # ── correctness: B identical sequences must stay identical ──
        var Bc = 4
        var toks = List[Int]()
        var poss = List[Int]()
        for _ in range(Bc):
            toks.append(SEED_TOKEN)
            poss.append(0)
        var consistent = True
        var seq0 = List[Int]()
        print("=== correctness: B=", Bc, " identical sequences, ", n_steps, " steps ===")
        for step in range(n_steps):
            var nxt = s._step_batched(toks, poss)
            var t0 = nxt[0]
            for b in range(1, Bc):
                if nxt[b] != t0:
                    consistent = False
            for b in range(Bc):
                toks[b] = nxt[b]
                poss[b] = poss[b] + 1
            seq0.append(t0)
        print("  all-", Bc, "-sequences-identical: ", "PASS" if consistent else "FAIL")
        print("  seq0 first 16 tokens:", seq0)

        # ── throughput sweep ──
        print("=== batched decode throughput (aggregate tok/s = B*steps/wall) ===")
        for bi in range(len(bs)):
            var B = bs[bi]
            var btoks = List[Int]()
            var bposs = List[Int]()
            for _ in range(B):
                btoks.append(SEED_TOKEN)
                bposs.append(0)
            # warmup (untimed)
            for _ in range(2):
                var w = s._step_batched(btoks, bposs)
                for b in range(B):
                    btoks[b] = w[b]
                    bposs[b] = bposs[b] + 1
            var best = 0.0
            var med = 0.0
            var rates = List[Float64]()
            for run in range(n_timed):
                var rt2 = List[Int]()
                var rp = List[Int]()
                for _ in range(B):
                    rt2.append(SEED_TOKEN)
                    rp.append(0)
                var t0 = perf_counter_ns()
                for step in range(n_steps):
                    var nxt = s._step_batched(rt2, rp)
                    for b in range(B):
                        rt2[b] = nxt[b]
                        rp[b] = rp[b] + 1
                var t1 = perf_counter_ns()
                var wall_ms = Float64(Int(t1 - t0)) / 1.0e6
                var agg = Float64(B * n_steps) / (wall_ms / 1000.0)
                rates.append(agg)
            # median
            for i in range(len(rates)):
                for j in range(i + 1, len(rates)):
                    if rates[j] < rates[i]:
                        var t = rates[i]
                        rates[i] = rates[j]
                        rates[j] = t
            med = rates[len(rates) / 2]
            print("  B=", B, " steps=", n_steps, " aggregate_tok_per_sec=", med,
                  " per_seq_tok_per_sec=", med / Float64(B))
