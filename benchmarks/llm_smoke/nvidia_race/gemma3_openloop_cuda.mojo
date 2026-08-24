"""gemma3_openloop_cuda.mojo — the Gemma 3 CUDA OPEN-LOOP SERVING driver (vLLM-flip round, 2026-08-24).

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
    ./gemma3_openloop_cuda /path/to/converted --prompts-dir D --count 500 --concurrency 50 \
        --max-tokens 256 [--ctx 1024] [--warmup-passes 1]

The open-loop protocol mirrors the opponent race client: `concurrency` slots, each request
generates exactly `max_tokens` tokens, and a finished slot immediately admits the next queued
request (single-stream flash ingest, engine-side TTFT = ingest wall). Finished-and-unrefilled
slots PARK (keep decoding, tokens ignored) so the batch stays full to the last completion.
The optional warmup pass re-runs the first wave (ingest + 2 steps) untimed to pay first-launch
costs before the wall clock starts — the engine-side analogue of a warm server."""

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


def _load_prompt(path: String) raises -> List[Int]:
    var raw = _read_text_file(path)
    var parts = raw.split(",")
    var out = List[Int]()
    for p in parts:
        if String(p).byte_length() > 0:
            out.append(parse_int(String(p)))
    return out^


def main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: gemma3_openloop_cuda <ckpt_dir> --prompts-dir D --count N --concurrency C --max-tokens M [--ctx X] [--warmup-passes W]")
        exit(2)
    var ckpt_dir = String(args[1])
    var prompts_dir = String("")
    var count = 500
    var conc = 50
    var max_tokens = 256
    var ctx_cap = 1024
    var warmup_passes = 1
    var i = 2
    while i < len(args):
        var a = String(args[i])
        if a == "--prompts-dir" and i + 1 < len(args):
            prompts_dir = String(args[i + 1])
            i += 2
        elif a == "--count" and i + 1 < len(args):
            count = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--concurrency" and i + 1 < len(args):
            conc = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--max-tokens" and i + 1 < len(args):
            max_tokens = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--ctx" and i + 1 < len(args):
            ctx_cap = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--warmup-passes" and i + 1 < len(args):
            warmup_passes = parse_int(String(args[i + 1]))
            i += 2
        else:
            i += 1
    if prompts_dir.byte_length() == 0:
        raise Error("gemma3_openloop_cuda: --prompts-dir required")
    if count < conc:
        raise Error("gemma3_openloop_cuda: --count must be >= --concurrency")

    # ── load the prompt set (prompt_NNNN.txt token files) ──
    var prompts = List[List[Int]]()
    for k in range(count):
        var idx = String(k)
        var name = idx
        while name.byte_length() < 4:
            name = "0" + name
        var path = prompts_dir + "/prompt_" + name + ".txt"
        var p = _load_prompt(path)
        if len(p) < 1:
            raise Error("gemma3_openloop_cuda: empty prompt " + path)
        prompts.append(p^)
    var n_prompt = len(prompts[0])

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
        raise Error("gemma3_openloop_cuda: manifest config did not parse")

    var family = json_get_string(config, "model_family")
    if family != "gemma3":
        raise Error("gemma3_openloop_cuda: model_family is not gemma3")
    var qpas = json_get_float(config, "query_pre_attn_scalar", -1.0)
    var embed_scale = json_get_float(config, "embed_scale", -1.0)
    var sliding_window = json_get_int(config, "sliding_window", -1)
    var theta_global = json_get_float(config, "rope_theta", -1.0)
    var theta_local = json_get_float(config, "rope_local_theta", -1.0)
    var rope_factor = json_get_float(config, "rope_global_scaling_factor", 1.0)
    if qpas <= 0.0 or embed_scale <= 0.0 or sliding_window < 1 \
       or theta_global <= 0.0 or theta_local <= 0.0 or rope_factor <= 0.0:
        raise Error("gemma3_openloop_cuda: gemma3 convention fields did not parse")
    var scale = 1.0 / sqrt(qpas)

    var lt_arr = json_get_array(config, "layer_types")
    var lt_tokens = json_array_tokens(lt_arr)
    if len(lt_tokens) != n_layers:
        raise Error("gemma3_openloop_cuda: layer_types length != num_hidden_layers")
    var layer_is_global = List[Int]()
    for k in range(n_layers):
        layer_is_global.append(parse_int(lt_tokens[k]))

    var weights_dtype = json_get_string(config, "weights_dtype")
    var elem_bytes = 4 if weights_dtype == "f32" else 8

    if not gemma3_dims_ok(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab):
        raise Error("gemma3_openloop_cuda: dims fail the gemma3 gate")
    if n_prompt + max_tokens + conc + 8 > ctx_cap:
        raise Error("gemma3_openloop_cuda: prompt + max_tokens + park headroom exceeds --ctx")

    print("gemma3_openloop_cuda: d_model =", d_model, "| layers =", n_layers,
          "| h_q =", h_q, "| h_kv =", h_kv, "| d_head =", d_head, "| d_ff =", d_ff,
          "| vocab =", vocab, "| window =", sliding_window,
          "| count =", count, "| concurrency =", conc, "| ctx =", ctx_cap,
          "| prompt =", n_prompt, "| max_tokens =", max_tokens)

    if not has_accelerator():
        print("gemma3_openloop_cuda: no accelerator on this host")
        exit(1)

    var s = _CudaResidentGemma3BatchedF16(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, conc, ctx_cap,
        eps, scale, embed_scale, sliding_window, layer_is_global,
    )
    print("  device:", s.device_name())

    # ── upload (identical to the batched driver) ──
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
        raise Error("gemma3_openloop_cuda: global rope table failed")
    var rt_l = rope_table(d_head, ctx_cap, theta_local)
    if rt_l.status != ATTN_OK:
        raise Error("gemma3_openloop_cuda: local rope table failed")

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

    # ── per-slot state ──
    var slot_tok = List[Int]()      # last token of the slot's active request
    var slot_pos = List[Int]()      # absolute position of the slot's next decode token
    var slot_steps = List[Int]()    # tokens generated by the slot's active request
    var slot_req = List[Int]()      # request id in the slot (>= count means parked)
    var slot_admit_ns = List[Int]()
    var slot_ttft_ms = List[Float64]()
    for slot in range(conc):
        slot_tok.append(0)
        slot_pos.append(0)
        slot_steps.append(0)
        slot_req.append(slot)
        slot_admit_ns.append(0)
        slot_ttft_ms.append(0.0)

    var req_ttft = List[Float64]()  # per completed request, in completion order
    var req_e2e = List[Float64]()
    var req_out = List[Int]()
    var next_req = 0
    var completed = 0

    # ── admission helper inlined: ingest request `rid` into `slot` ──
    # (Mojo has no closures over mut self; the admit code lives in-loop below.)

    # ── optional warmup pass: run the first wave once, discard ──
    var t_warm0 = perf_counter_ns()
    for wp in range(warmup_passes):
        for slot in range(conc):
            var r = s.ingest(slot, prompts[slot])
            if r.status != RESIDENT_OK:
                raise Error("gemma3_openloop_cuda: warmup ingest failed")
            slot_tok[slot] = r.token_id
            slot_pos[slot] = n_prompt
            slot_steps[slot] = 1
        for st in range(2):
            var poss = List[Int]()
            var nkeys = List[Int]()
            var toks = List[Int]()
            for slot in range(conc):
                poss.append(slot_pos[slot])
                nkeys.append(slot_pos[slot] + 1)
                toks.append(slot_tok[slot])
            _check_resident(s.seed_step(conc, toks, poss, nkeys), "warmup seed")
            _check_resident(s.step_batched(conc), "warmup step")
            for slot in range(conc):
                slot_tok[slot] = s.batch_token(slot)
                slot_pos[slot] += 1
                slot_steps[slot] += 1
    var warm_ms = Float64(perf_counter_ns() - t_warm0) / 1.0e6
    print("  warmup pass ms:", warm_ms)

    # ── the measured open-loop pass ──
    # initial admission wave (one request per slot, in order)
    for slot in range(conc):
        slot_req[slot] = next_req
        var t_a0 = perf_counter_ns()
        var r = s.ingest(slot, prompts[next_req])
        var t_a1 = perf_counter_ns()
        if r.status != RESIDENT_OK:
            raise Error("gemma3_openloop_cuda: ingest failed for req " + String(next_req))
        slot_tok[slot] = r.token_id
        slot_pos[slot] = n_prompt
        slot_steps[slot] = 1
        slot_admit_ns[slot] = t_a1
        slot_ttft_ms[slot] = Float64(t_a1 - t_a0) / 1.0e6
        next_req += 1

    var wall_start = perf_counter_ns()
    while completed < count:
        var poss = List[Int]()
        var nkeys = List[Int]()
        var toks = List[Int]()
        for slot in range(conc):
            poss.append(slot_pos[slot])
            nkeys.append(slot_pos[slot] + 1)
            toks.append(slot_tok[slot])
        _check_resident(s.seed_step(conc, toks, poss, nkeys), "seed_step")
        _check_resident(s.step_batched(conc), "step_batched")
        var now_ns = perf_counter_ns()
        for slot in range(conc):
            slot_tok[slot] = s.batch_token(slot)
            slot_pos[slot] += 1
            slot_steps[slot] += 1
            if slot_req[slot] < count and slot_steps[slot] >= max_tokens:
                # request complete — record, then admit the next into this slot
                req_ttft.append(slot_ttft_ms[slot])
                req_e2e.append(Float64(now_ns - slot_admit_ns[slot]) / 1.0e6)
                req_out.append(slot_steps[slot])
                completed += 1
                if next_req < count:
                    slot_req[slot] = next_req
                    var t_b0 = perf_counter_ns()
                    var r2 = s.ingest(slot, prompts[next_req])
                    var t_b1 = perf_counter_ns()
                    if r2.status != RESIDENT_OK:
                        raise Error("gemma3_openloop_cuda: admit ingest failed")
                    slot_tok[slot] = r2.token_id
                    slot_pos[slot] = n_prompt
                    slot_steps[slot] = 1
                    slot_admit_ns[slot] = t_b1
                    slot_ttft_ms[slot] = Float64(t_b1 - t_b0) / 1.0e6
                    next_req += 1
                else:
                    # park the slot: it keeps decoding (bounded by ctx) so the batch stays
                    # full; its tokens are ignored.
                    slot_req[slot] = count + slot
    var wall_end = perf_counter_ns()

    var wall_s = Float64(wall_end - wall_start) / 1.0e9
    var total_out = 0
    for k in range(len(req_out)):
        total_out += req_out[k]
    var agg = Float64(total_out) / wall_s if wall_s > 0.0 else 0.0

    # ttft p50 (insertion-sort the small list)
    var tt = req_ttft^
    for a in range(1, len(tt)):
        var key = tt[a]
        var b = a - 1
        while b >= 0 and tt[b] > key:
            tt[b + 1] = tt[b]
            b -= 1
        tt[b + 1] = key
    var ttft_p50 = tt[len(tt) // 2] if len(tt) > 0 else 0.0

    var out = String("{\"count\": " + String(count) + ", \"concurrency\": " + String(conc)
        + ", \"max_tokens\": " + String(max_tokens)
        + ", \"ok_requests\": " + String(completed)
        + ", \"wall_s\": " + String(wall_s)
        + ", \"agg_out_tok_s\": " + String(agg)
        + ", \"req_s\": " + String(Float64(completed) / wall_s)
        + ", \"total_out_tokens\": " + String(total_out)
        + ", \"ttft_ms_p50\": " + String(ttft_p50)
        + ", \"first_gen_seq0_len\": " + String(len(req_out)) + "}")
    print(out)
    exit(0)
