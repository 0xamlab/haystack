"""gemma3_correctness_cuda.mojo — the Gemma 3 CUDA correctness driver (Gemma 3 lane, 2026-08-23).

The engine half of the Gemma 3 identity gate. It loads a converted gemma3 checkpoint
(`manifest.json` + `weights.blob`, written by `algenta.inference.prepare_model_checkpoint`),
ingests a prompt through the decode-only gemma3 session (sequential, bit-equivalent to a
parallel prefill), and either:

  * `--dump-logits`  — prints the FULL final logits vector after the prompt (the strong identity
    proof: random-weight synthetic models collapse to token attractors, so the logits —
    not just the argmax token — are what actually verify every kernel), or
  * default          — greedy-generates up to --max-new tokens, stopping on the checkpoint's
    eos ids, and prints the token ids.

The output JSON is diffed against `ref_gemma3_torch.py`'s by
`benchmarks/llm_smoke/gemma3/gate_gemma3.py`.

Build (on the race VM):
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 \
        --target-accelerator sm_90 -I mojo/engine \
        benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo -o gemma3_correctness_cuda

Usage:
    ./gemma3_correctness_cuda /path/to/converted --tokens 3,17,42,8 --max-new 16
    ./gemma3_correctness_cuda /path/to/converted --tokens 3,17,42,8 --dump-logits

`--prefill` ingests the prompt through the tiled prefill (parallel, the TTFT arm) instead of
the serial step-by-step ingestion; the two are the eager-vs-tiled identity gate. `--tokens-file`
reads a comma-separated id list from a file (long race prompts).
"""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator, is_defined
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
from residentk.session import _StepOut
from residentk.session_cuda_gemma3 import CUDA_GEMMA3_BUILD, _CudaResidentGemma3, gemma3_dims_ok
from residentk.session_cuda_gemma3_f16 import _CudaResidentGemma3F16
from std.time import perf_counter_ns

comptime MAX_CTX: Int = 8192
"""The session's fixed context ceiling. 4096 covers the synthetic gate (short prompts) and the
real-weights first-token gate; the race driver builds its own ceiling. KV scales linearly."""


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "gemma3_correctness_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("gemma3_correctness_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_blob_slice(
    path: String, byte_offset: Int, n_elements: Int, elem_bytes: Int
) raises -> List[Float64]:
    """Read `n_elements` of `elem_bytes` width (8 = the historical f64 blob, 4 = the Gemma-3 f32
    blob) and widen to Float64. f32->f64 is exact, so both widths feed identical values."""
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * elem_bytes)
    f.close()
    if len(raw) != n_elements * elem_bytes:
        raise Error("gemma3_correctness_cuda: short read at byte offset " + String(byte_offset))
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


def _upload_and_run_f32(
    mut s: _CudaResidentGemma3,
    blob_path: String, tensors_obj: String, elem_bytes: Int,
    n_layers: Int, vocab: Int,
    cos_g: List[Float64], sin_g: List[Float64], cos_l: List[Float64], sin_l: List[Float64],
    prompt: List[Int], max_new: Int, dump_logits: Bool, eos_ids: List[Int],
    use_prefill: Int,
) raises:
    """Load every weight out of the blob into the session, ingest the prompt, and either dump the
    final logits or greedy-generate. Float32-weight arm — the upload/ingest/generate body; the f16 twin is
    method surface."""
    var embed_table = _load(blob_path, tensors_obj, "model.embed_tokens.weight", elem_bytes)
    var final_norm_w = _load(blob_path, tensors_obj, "model.norm.weight", elem_bytes)
    _check_resident(
        s.upload_globals(embed_table, final_norm_w, cos_g, sin_g, cos_l, sin_l, MAX_CTX),
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

    # ── ingest the prompt: tiled prefill (parallel) or one token at a time (serial) ──
    var n_prompt = len(prompt)
    var t0 = perf_counter_ns()
    var r = _StepOut(0, 0.0, 0, RESIDENT_OK)
    if use_prefill == 1:
        r = s.prefill(prompt)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_correctness_cuda: tiled prefill failed")
    else:
        r = s.step(prompt[0], 0)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_correctness_cuda: prompt step 0 failed")
        for t in range(1, n_prompt):
            r = s.step(prompt[t], t)
            if r.status != RESIDENT_OK:
                raise Error("gemma3_correctness_cuda: prompt step failed at " + String(t))
    var t_pf = perf_counter_ns()

    if dump_logits:
        _check_resident(s.dump_logits(), "dump_logits")
        var logits = s.read_logits()
        var out = String("{\"prompt\": [")
        for t in range(n_prompt):
            out += String(prompt[t])
            if t < n_prompt - 1:
                out += ", "
        out += "], \"argmax\": " + String(r.token_id) + ", \"logits\": ["
        for v in range(vocab):
            out += String(logits[v])
            if v < vocab - 1:
                out += ", "
        out += "]}"
        print(out)
        exit(0)

    # ── greedy generation with EOS ──
    var generated = List[Int]()
    generated.append(r.token_id)
    var last = r.token_id
    var stopped = _is_eos(last, eos_ids)
    var pos = n_prompt
    while len(generated) < max_new and not stopped:
        r = s.step(last, pos)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_correctness_cuda: decode step failed at pos " + String(pos))
        last = r.token_id
        generated.append(last)
        stopped = _is_eos(last, eos_ids)
        pos += 1
    var t_end = perf_counter_ns()
    var ttft_ms = Float64(t_pf - t0) / 1.0e6
    var decode_s = Float64(t_end - t_pf) / 1.0e9
    var n_dec = len(generated) - 1
    var decode_tok_s = Float64(n_dec) / decode_s if decode_s > 0.0 else 0.0

    var out = String("{\"prompt\": [")
    for t in range(n_prompt):
        out += String(prompt[t])
        if t < n_prompt - 1:
            out += ", "
    out += "], \"generated\": ["
    for t in range(len(generated)):
        out += String(generated[t])
        if t < len(generated) - 1:
            out += ", "
    var arm = "prefill" if use_prefill == 1 else "eager"
    out += "], \"ttft_ms\": " + String(ttft_ms) + ", \"decode_tok_s\": " + String(decode_tok_s) + ", \"arm\": \"" + arm + "\", \"n_generated\": " + String(len(generated)) + "}"
    print(out)
    exit(0)




def _upload_and_run_f16(
    mut s: _CudaResidentGemma3F16,
    blob_path: String, tensors_obj: String, elem_bytes: Int,
    n_layers: Int, vocab: Int,
    cos_g: List[Float64], sin_g: List[Float64], cos_l: List[Float64], sin_l: List[Float64],
    prompt: List[Int], max_new: Int, dump_logits: Bool, eos_ids: List[Int], use_graph: Int,
    use_prefill: Int,
) raises:
    """Load every weight out of the blob into the session, ingest the prompt, and either dump the
    final logits or greedy-generate. Float16-weight arm twin of `_upload_and_run_f32`. When
    `use_graph`=1 the decode runs through the captured CUDA graph (zero per-token host traffic)."""
    var embed_table = _load(blob_path, tensors_obj, "model.embed_tokens.weight", elem_bytes)
    var final_norm_w = _load(blob_path, tensors_obj, "model.norm.weight", elem_bytes)
    _check_resident(
        s.upload_globals(embed_table, final_norm_w, cos_g, sin_g, cos_l, sin_l, MAX_CTX),
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

    # ── ingest the prompt: tiled prefill (parallel) or one token at a time (serial) ──
    var n_prompt = len(prompt)
    var t0 = perf_counter_ns()
    var r = _StepOut(0, 0.0, 0, RESIDENT_OK)
    if use_prefill == 1:
        r = s.prefill(prompt)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_correctness_cuda: tiled prefill failed")
    else:
        r = s.step(prompt[0], 0)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_correctness_cuda: prompt step 0 failed")
        for t in range(1, n_prompt):
            r = s.step(prompt[t], t)
            if r.status != RESIDENT_OK:
                raise Error("gemma3_correctness_cuda: prompt step failed at " + String(t))
    var t_pf = perf_counter_ns()

    if dump_logits:
        _check_resident(s.dump_logits(), "dump_logits")
        var logits = s.read_logits()
        var out = String("{\"prompt\": [")
        for t in range(n_prompt):
            out += String(prompt[t])
            if t < n_prompt - 1:
                out += ", "
        out += "], \"argmax\": " + String(r.token_id) + ", \"logits\": ["
        for v in range(vocab):
            out += String(logits[v])
            if v < vocab - 1:
                out += ", "
        out += "]}"
        print(out)
        exit(0)

    # ── greedy generation with EOS ──
    var generated = List[Int]()
    generated.append(r.token_id)
    var last = r.token_id
    var stopped = _is_eos(last, eos_ids)
    var pos = n_prompt
    if use_graph == 1 and not stopped and max_new > 1:
        # CUDA-graph decode: build the graph outside the timed region, then run the remaining
        # tokens as back-to-back replays (zero per-token host traffic). r.token_id (from the
        # ingest above) occupies position n_prompt.
        s.ensure_graph()
        var n_graph = max_new - 1
        var t_g0 = perf_counter_ns()
        _check_resident(s.seed_and_run_graph(last, n_prompt, n_graph), "seed_and_run_graph")
        var t_g1 = perf_counter_ns()
        for k in range(n_graph):
            var tok = s.graph_token(n_prompt + k)
            generated.append(tok)
            if _is_eos(tok, eos_ids):
                break
        var decode_s = Float64(t_g1 - t_g0) / 1.0e9
        var n_dec = len(generated) - 1
        var decode_tok_s = Float64(n_dec) / decode_s if decode_s > 0.0 else 0.0
        var ttft_ms = Float64(t_pf - t0) / 1.0e6
        var out = String("{\"prompt\": [")
        for t in range(n_prompt):
            out += String(prompt[t])
            if t < n_prompt - 1:
                out += ", "
        out += "], \"generated\": ["
        for t in range(len(generated)):
            out += String(generated[t])
            if t < len(generated) - 1:
                out += ", "
        var arm = "prefill+graph" if use_prefill == 1 else "graph"
        out += "], \"ttft_ms\": " + String(ttft_ms) + ", \"decode_tok_s\": " + String(decode_tok_s) + ", \"arm\": \"" + arm + "\", \"n_generated\": " + String(len(generated)) + "}"
        print(out)
        exit(0)
    while len(generated) < max_new and not stopped:
        r = s.step(last, pos)
        if r.status != RESIDENT_OK:
            raise Error("gemma3_correctness_cuda: decode step failed at pos " + String(pos))
        last = r.token_id
        generated.append(last)
        stopped = _is_eos(last, eos_ids)
        pos += 1
    var t_end = perf_counter_ns()
    var ttft_ms = Float64(t_pf - t0) / 1.0e6
    var decode_s = Float64(t_end - t_pf) / 1.0e9
    var n_dec = len(generated) - 1
    var decode_tok_s = Float64(n_dec) / decode_s if decode_s > 0.0 else 0.0

    var out = String("{\"prompt\": [")
    for t in range(n_prompt):
        out += String(prompt[t])
        if t < n_prompt - 1:
            out += ", "
    out += "], \"generated\": ["
    for t in range(len(generated)):
        out += String(generated[t])
        if t < len(generated) - 1:
            out += ", "
    var arm = "prefill" if use_prefill == 1 else "eager"
    out += "], \"ttft_ms\": " + String(ttft_ms) + ", \"decode_tok_s\": " + String(decode_tok_s) + ", \"arm\": \"" + arm + "\", \"n_generated\": " + String(len(generated)) + "}"
    print(out)
    exit(0)


def main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: gemma3_correctness_cuda <ckpt_dir> --tokens a,b,c [--max-new N] [--dump-logits]")
        exit(2)
    var ckpt_dir = String(args[1])
    var prompt = List[Int]()
    var max_new = 8
    var dump_logits = False
    var use_f16 = False
    var use_graph = 0
    var use_prefill = 0
    var i = 2
    while i < len(args):
        var a = String(args[i])
        if a == "--tokens" and i + 1 < len(args):
            var parts = String(args[i + 1]).split(",")
            for p in parts:
                prompt.append(parse_int(String(p)))
            i += 2
        elif a == "--tokens-file" and i + 1 < len(args):
            # comma-separated token ids from a file (long race prompts; writer emits no
            # whitespace, so a bare split is exact)
            var raw = _read_text_file(String(args[i + 1]))
            var parts = raw.split(",")
            for p in parts:
                if String(p).byte_length() > 0:
                    prompt.append(parse_int(String(p)))
            i += 2
        elif a == "--max-new" and i + 1 < len(args):
            max_new = parse_int(String(args[i + 1]))
            i += 2
        elif a == "--dump-logits":
            dump_logits = True
            i += 1
        elif a == "--f16":
            use_f16 = True
            i += 1
        elif a == "--graph":
            use_graph = 1
            i += 1
        elif a == "--prefill":
            use_prefill = 1
            i += 1
        else:
            i += 1
    if len(prompt) == 0:
        raise Error("gemma3_correctness_cuda: --tokens required")

    var manifest = _read_text_file(ckpt_dir + "/manifest.json")
    var config = json_get_object(manifest, "config")

    # ── structural fields ──
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
        raise Error("gemma3_correctness_cuda: manifest config did not parse")

    # ── gemma3 convention fields (all verified by the SDK converter before we see them) ──
    var family = json_get_string(config, "model_family")
    if family != "gemma3":
        raise Error("gemma3_correctness_cuda: model_family is not gemma3")
    var activation = json_get_int(config, "activation_code", -1)
    if activation != 1:
        raise Error("gemma3_correctness_cuda: activation_code != 1 (gelu_pytorch_tanh)")
    var norm_plus_one = json_get_int(config, "norm_weight_plus_one", -1)
    if norm_plus_one != 1:
        raise Error("gemma3_correctness_cuda: norm_weight_plus_one != 1 (blob gains not rebased)")
    var has_qk_norm = json_get_int(config, "has_qk_norm", -1)
    if has_qk_norm != 1:
        raise Error("gemma3_correctness_cuda: has_qk_norm != 1")

    var qpas = json_get_float(config, "query_pre_attn_scalar", -1.0)
    var embed_scale = json_get_float(config, "embed_scale", -1.0)
    var sliding_window = json_get_int(config, "sliding_window", -1)
    var theta_global = json_get_float(config, "rope_theta", -1.0)
    var theta_local = json_get_float(config, "rope_local_theta", -1.0)
    var rope_factor = json_get_float(config, "rope_global_scaling_factor", 1.0)
    if qpas <= 0.0 or embed_scale <= 0.0 or sliding_window < 1 \
       or theta_global <= 0.0 or theta_local <= 0.0 or rope_factor <= 0.0:
        raise Error("gemma3_correctness_cuda: gemma3 convention fields did not parse")
    var scale = 1.0 / sqrt(qpas)

    # ── per-layer class list (1 = full, 0 = sliding) ──
    var lt_arr = json_get_array(config, "layer_types")
    var lt_tokens = json_array_tokens(lt_arr)
    if len(lt_tokens) != n_layers:
        raise Error("gemma3_correctness_cuda: layer_types length != num_hidden_layers")
    var layer_is_global = List[Int]()
    for k in range(n_layers):
        layer_is_global.append(parse_int(lt_tokens[k]))

    # ── eos id list ──
    var eos_arr = json_get_array(config, "eos_token_ids")
    var eos_tokens = json_array_tokens(eos_arr)
    var eos_ids = List[Int]()
    for k in range(len(eos_tokens)):
        eos_ids.append(parse_int(eos_tokens[k]))

    # ── blob element width (f64 historical / f32 Gemma-3) ──
    var weights_dtype = json_get_string(config, "weights_dtype")
    var elem_bytes = 4 if weights_dtype == "f32" else 8

    if not gemma3_dims_ok(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab):
        raise Error("gemma3_correctness_cuda: dims fail the gemma3 gate")
    if len(prompt) > MAX_CTX - max_new:
        raise Error("gemma3_correctness_cuda: prompt + max_new exceeds MAX_CTX")

    print("gemma3_correctness_cuda: d_model =", d_model, "| layers =", n_layers,
          "| h_q =", h_q, "| h_kv =", h_kv, "| d_head =", d_head, "| d_ff =", d_ff,
          "| vocab =", vocab, "| window =", sliding_window,
          "| rope g/l =", theta_global, "/", theta_local, "x", rope_factor,
          "| blob =", weights_dtype if weights_dtype == "f32" else "f64")

    @parameter
    if not CUDA_GEMMA3_BUILD:
        print("gemma3_correctness_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("gemma3_correctness_cuda: no accelerator on this host")
            exit(1)

        var blob_path = ckpt_dir + "/weights.blob"
        var tensors_obj = json_get_object(manifest, "tensors")

        # ── dual rope tables: global = theta_global with the linear factor dividing every pair;
        #    local = theta_local unscaled. Matches ref_gemma3_torch.py's inv_freq exactly. ──
        var n_pairs = d_head // 2
        var factors = List[Float64]()
        for p in range(n_pairs):
            factors.append(rope_factor)
        var rt_g = rope_table_freq_factors(d_head, MAX_CTX, theta_global, factors^)
        if rt_g.status != ATTN_OK:
            raise Error("gemma3_correctness_cuda: global rope table failed")
        var rt_l = rope_table(d_head, MAX_CTX, theta_local)
        if rt_l.status != ATTN_OK:
            raise Error("gemma3_correctness_cuda: local rope table failed")

        if use_f16:
            var s = _CudaResidentGemma3F16(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, MAX_CTX, eps, scale,
                embed_scale, sliding_window, layer_is_global,
            )
            print("  device:", s.device_name(), "| arm: f16 weights",
                  "| ingest: prefill" if use_prefill == 1 else "| ingest: serial",
                  "| decode: graph" if use_graph == 1 else "| decode: eager")
            _upload_and_run_f16(
                s, blob_path, tensors_obj, elem_bytes, n_layers, vocab,
                rt_g.cos_table, rt_g.sin_table, rt_l.cos_table, rt_l.sin_table,
                prompt, max_new, dump_logits, eos_ids, use_graph, use_prefill,
            )
        else:
            var s = _CudaResidentGemma3(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, MAX_CTX, eps, scale,
                embed_scale, sliding_window, layer_is_global,
            )
            print("  device:", s.device_name(), "| arm: f32 weights",
                  "| ingest: prefill" if use_prefill == 1 else "| ingest: serial")
            _upload_and_run_f32(
                s, blob_path, tensors_obj, elem_bytes, n_layers, vocab,
                rt_g.cos_table, rt_g.sin_table, rt_l.cos_table, rt_l.sin_table,
                prompt, max_new, dump_logits, eos_ids, use_prefill,
            )


def _load(blob_path: String, tensors_obj: String, name: String, elem_bytes: Int) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_blob_slice(blob_path, loc.offset * elem_bytes, loc.n_elements, elem_bytes)


def _is_eos(token: Int, eos_ids: List[Int]) -> Bool:
    for k in range(len(eos_ids)):
        if token == eos_ids[k]:
            return True
    return False
