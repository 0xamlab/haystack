"""gemma3_batched_cuda.mojo — the Gemma 3 CUDA BATCHED DECODE driver (Gemma 3 lane, 2026-08-24).

Loads a converted gemma3 checkpoint, opens the batched f16 session (B sequences sharing ONE
weight residency), ingests the prompt into every sequence through the tiled prefill (each into
its own KV region), then runs the M=B batched decode loop and reports aggregate throughput.

The greedy tokens ARE the correctness evidence: the gate compares a `--batch 1` run against the
single-stream `gemma3_correctness_cuda --prefill` arm (same prompt, same token contract), and
B>1 runs against B copies of the same single-stream reference.

Build (on the race VM):
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_TC_SHIM \
        --target-accelerator sm_90 -I mojo/engine -I attention_forge \
        benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo -o gemma3_batched_cuda \
        -Xlinker /tmp/g3tc/tc_shim.o -Xlinker -lcublas -Xlinker -lcudart \
        -Xlinker -L/usr/local/cuda/lib64

Usage:
    ./gemma3_batched_cuda /path/to/converted --tokens-file F --batch 8 --max-new 64 [--ctx 1024]
"""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator
from conv import parse_int
from json.parser import (
    json_array_len,
    json_array_tokens,
    json_get_array,
    json_get_float,
    json_get_int,
    json_get_object,
    json_get_string,
)
from attnk.rope import rope_table, rope_table_freq_factors
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_OK, residentk_status_name
from residentk.session_cuda_gemma3 import gemma3_dims_ok
from residentk.session_cuda_gemma3_batched import _CudaResidentGemma3BatchedF16
from std.time import perf_counter_ns


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "gemma3_batched_cuda: " + ctx + " failed, status=" + String(status)
            + " (" + residentk_status_name(status) + ")"
        )


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
        raise Error("gemma3_batched_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_blob_slice(
    path: String, byte_offset: Int, n_elements: Int, elem_bytes: Int
) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * elem_bytes)
    f.close()
    if len(raw) != n_elements * elem_bytes:
        raise Error("gemma3_batched_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    if elem_bytes == 8:
        var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
        for i in range(n_elements):
            out.append(fp[i])
    else:
        var fp = raw.unsafe_ptr().unsafe_bitcast[Float32]()
        for i in range(n_elements):
            out.append(Float64(fp[i]))
    return out^


def _load(blob_path: String, tensors_obj: String, name: String, elem_bytes: Int) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_blob_slice(blob_path, loc.offset * elem_bytes, loc.n_elements, elem_bytes)


def _is_eos(token: Int, eos_ids: List[Int]) -> Bool:
    for k in range(len(eos_ids)):
        if token == eos_ids[k]:
            return True
    return False


def main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: gemma3_batched_cuda <ckpt_dir> --tokens-file F --batch B --max-new N [--ctx C] [--warmup W]")
        exit(2)
    var ckpt_dir = String(args[1])
    var tokens_file = String("")
    var batch = 1
    var max_new = 16
    var ctx_cap = 1024
    var warmup = 2
    var i = 2
    while i < len(args):
        var a = String(args[i])
        if a == "--tokens-file" and i + 1 < len(args):
            tokens_file = String(args[i + 1])
            i += 2
        elif a == "--batch" and i + 1 < len(args):
            batch = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--max-new" and i + 1 < len(args):
            max_new = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--ctx" and i + 1 < len(args):
            ctx_cap = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--warmup" and i + 1 < len(args):
            warmup = parse_int(String(args[i + 1]))
            i += 2
        else:
            i += 1
    if tokens_file.byte_length() == 0:
        raise Error("gemma3_batched_cuda: --tokens-file required")

    var prompt = List[Int]()
    var raw = _read_text_file(tokens_file)
    var parts = raw.split(",")
    for p in parts:
        if String(p).byte_length() > 0:
            prompt.append(parse_int(String(p)))
    var n_prompt = len(prompt)
    if n_prompt < 1:
        raise Error("gemma3_batched_cuda: empty prompt")

    var manifest = _read_text_file(ckpt_dir + "/manifest.json")
    var config = json_get_object(manifest, "config")

    var d_model = json_get_int(config, "hidden_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var vocab = json_get_int(config, "vocab_size", -1)
    var eps = json_get_float(config, "rms_norm_eps", -1.0)
    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab < 1 or eps < 0.0:
        raise Error("gemma3_batched_cuda: manifest config did not parse")

    var family = json_get_string(config, "model_family")
    if family != "gemma3":
        raise Error("gemma3_batched_cuda: model_family is not gemma3")
    var qpas = json_get_float(config, "query_pre_attn_scalar", -1.0)
    var embed_scale = json_get_float(config, "embed_scale", -1.0)
    var sliding_window = json_get_int(config, "sliding_window", -1)
    var theta_global = json_get_float(config, "rope_theta", -1.0)
    var theta_local = json_get_float(config, "rope_local_theta", -1.0)
    var rope_factor = json_get_float(config, "rope_global_scaling_factor", 1.0)
    if qpas <= 0.0 or embed_scale <= 0.0 or sliding_window < 1 \
       or theta_global <= 0.0 or theta_local <= 0.0 or rope_factor <= 0.0:
        raise Error("gemma3_batched_cuda: gemma3 convention fields did not parse")
    var scale = 1.0 / sqrt(qpas)

    var lt_arr = json_get_array(config, "layer_types")
    var lt_tokens = json_array_tokens(lt_arr)
    if len(lt_tokens) != n_layers:
        raise Error("gemma3_batched_cuda: layer_types length != num_hidden_layers")
    var layer_is_global = List[Int]()
    for k in range(n_layers):
        layer_is_global.append(parse_int(lt_tokens[k]))

    var eos_arr = json_get_array(config, "eos_token_ids")
    var eos_tokens = json_array_tokens(eos_arr)
    var eos_ids = List[Int]()
    for k in range(len(eos_tokens)):
        eos_ids.append(parse_int(eos_tokens[k]))

    var weights_dtype = json_get_string(config, "weights_dtype")
    var elem_bytes = 4 if weights_dtype == "f32" else 8

    if not gemma3_dims_ok(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab):
        raise Error("gemma3_batched_cuda: dims fail the gemma3 gate")
    if n_prompt + warmup + max_new > ctx_cap:
        raise Error("gemma3_batched_cuda: prompt + warmup + max_new exceeds --ctx")

    print("gemma3_batched_cuda: d_model =", d_model, "| layers =", n_layers,
          "| h_q =", h_q, "| h_kv =", h_kv, "| d_head =", d_head, "| d_ff =", d_ff,
          "| vocab =", vocab, "| window =", sliding_window,
          "| batch =", batch, "| ctx =", ctx_cap, "| prompt =", n_prompt)

    if not has_accelerator():
        print("gemma3_batched_cuda: no accelerator on this host")
        exit(1)

    var s = _CudaResidentGemma3BatchedF16(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, batch, ctx_cap,
        eps, scale, embed_scale, sliding_window, layer_is_global,
    )
    print("  device:", s.device_name())

    # ── upload ──
    var blob_path = ckpt_dir + "/weights.blob"
    var tensors_obj = json_get_object(manifest, "tensors")

    var embed_table = _load(blob_path, tensors_obj, "model.embed_tokens.weight", elem_bytes)
    var final_norm_w = _load(blob_path, tensors_obj, "model.norm.weight", elem_bytes)

    var n_pairs = d_head // 2
    var factors = List[Float64]()
    for p in range(n_pairs):
        factors.append(rope_factor)
    var rt_g = rope_table_freq_factors(d_head, ctx_cap, theta_global, factors^)
    if rt_g.status != ATTN_OK:
        raise Error("gemma3_batched_cuda: global rope table failed")
    var rt_l = rope_table(d_head, ctx_cap, theta_local)
    if rt_l.status != ATTN_OK:
        raise Error("gemma3_batched_cuda: local rope table failed")

    _check_resident(
        s.upload_globals(embed_table, final_norm_w,
                         rt_g.cos_table, rt_g.sin_table, rt_l.cos_table, rt_l.sin_table,
                         ctx_cap),
        "upload_globals",
    )
    for layer in range(n_layers):
        var prefix = "model.layers." + String(layer) + "."
        var ln1 = _load(blob_path, tensors_obj, prefix + "input_layernorm.weight", elem_bytes)
        var ln2 = _load(blob_path, tensors_obj, prefix + "post_attention_layernorm.weight", elem_bytes)
        var ln3 = _load(blob_path, tensors_obj, prefix + "pre_feedforward_layernorm.weight", elem_bytes)
        var ln4 = _load(blob_path, tensors_obj, prefix + "post_feedforward_layernorm.weight", elem_bytes)
        var qn = _load(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight", elem_bytes)
        var kn = _load(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight", elem_bytes)
        var wq = _load(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight", elem_bytes)
        var wk = _load(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight", elem_bytes)
        var wv = _load(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight", elem_bytes)
        var wo = _load(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight", elem_bytes)
        var wg = _load(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight", elem_bytes)
        var wu = _load(blob_path, tensors_obj, prefix + "mlp.up_proj.weight", elem_bytes)
        var wd = _load(blob_path, tensors_obj, prefix + "mlp.down_proj.weight", elem_bytes)
        _check_resident(
            s.upload_layer(layer, ln1, ln2, ln3, ln4, qn, kn, wq, wk, wv, wo, wg, wu, wd),
            "upload_layer " + String(layer),
        )
    _check_resident(s.seal(), "seal")

    # ── ingest the prompt into every sequence ──
    var first_tokens = List[Int]()
    var t_in0 = perf_counter_ns()
    for seq in range(batch):
        var r = s.ingest(seq, prompt)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_batched_cuda: ingest failed for seq " + String(seq))
        first_tokens.append(r.token_id)
    var t_in1 = perf_counter_ns()
    var ingest_ms = Float64(t_in1 - t_in0) / 1.0e6

    # ── the batched decode loop: poss advance together, all sequences share the schedule ──
    var last_tokens = List[Int]()
    for b in range(batch):
        last_tokens.append(first_tokens[b])
    var pos = n_prompt

    # sequence 0's full generation is kept for the token-identity gate (every sequence runs
    # the identical schedule; B>1 agreement is verified against the single-stream reference)
    var gen_seq0 = List[Int]()
    gen_seq0.append(first_tokens[0])

    # warmup steps (untimed — first batched dispatches pay kernel first-launch costs)
    for w in range(warmup):
        var poss = List[Int]()
        var nkeys = List[Int]()
        for b in range(batch):
            poss.append(pos)
            nkeys.append(pos + 1)
        _check_resident(s.seed_step(batch, last_tokens, poss, nkeys), "seed_step warmup")
        _check_resident(s.step_batched(batch), "step_batched warmup")
        for b in range(batch):
            var tok = s.batch_token(b)
            last_tokens[b] = tok
            if b == 0:
                gen_seq0.append(tok)
        pos += 1

    var t0 = perf_counter_ns()
    for step in range(max_new):
        var poss = List[Int]()
        var nkeys = List[Int]()
        for b in range(batch):
            poss.append(pos)
            nkeys.append(pos + 1)
        _check_resident(s.seed_step(batch, last_tokens, poss, nkeys), "seed_step")
        _check_resident(s.step_batched(batch), "step_batched")
        for b in range(batch):
            var tok = s.batch_token(b)
            last_tokens[b] = tok
            if b == 0:
                gen_seq0.append(tok)
        pos += 1
    var t1 = perf_counter_ns()

    var decode_s = Float64(t1 - t0) / 1.0e9
    var agg_tok_s = Float64(batch * max_new) / decode_s if decode_s > 0.0 else 0.0
    var per_req_tok_s = agg_tok_s / Float64(batch) if batch > 0 else 0.0

    var out = String("{\"batch\": " + String(batch) + ", \"prompt_len\": " + String(n_prompt)
        + ", \"warmup\": " + String(warmup) + ", \"max_new\": " + String(max_new)
        + ", \"ingest_total_ms\": " + String(ingest_ms)
        + ", \"decode_s\": " + String(decode_s)
        + ", \"agg_tok_s\": " + String(agg_tok_s)
        + ", \"per_req_tok_s\": " + String(per_req_tok_s)
        + ", \"first_tokens\": [")
    for b in range(batch):
        out += String(first_tokens[b])
        if b < batch - 1:
            out += ", "
    out += "], \"gen_seq0\": ["
    for t in range(len(gen_seq0)):
        out += String(gen_seq0[t])
        if t < len(gen_seq0) - 1:
            out += ", "
    out += "]}"
    print(out)
    exit(0)
