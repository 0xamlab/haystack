"""qwen3_generate_metal_i4.mojo — the SAME Qwen3-0.6B-Base greedy decode as
`qwen3_generate_metal_i8.mojo`, `qwen3_generate_metal_fp16.mojo` and `qwen3_generate_metal.mojo`,
through `residentk`'s PACKED-INT4-weight resident GPU session (`_ResidentQwen3I4`) instead of its
Int8, Float16 or Float32 ones.

A FIFTH, additive arm. `qwen3_generate.mojo` (CPU, Float64), `qwen3_generate_metal.mojo` (GPU,
Float32), `qwen3_generate_metal_fp16.mojo` (GPU, Float16 weights) and `qwen3_generate_metal_i8.mojo`
(GPU, Int8 weights) are none of them touched by this file; all four stay runnable, and the Int8 GPU
arm is this file's own most direct comparison point — same session shape, same dispatch count, same
checkpoint, same prompt, only the resident weight dtype/scale scheme for the THREE per-layer
GEMV-shaped weight matrix roles differs.

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \
        <worktree>/benchmarks/llm_smoke/qwen3_generate_metal_i4.mojo -o /tmp/qwen3_metal_i4
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_metal_i4

Built WITHOUT `-D ALGENTA_GPU` it still compiles and links — and says so, rather than pretending.

What is different from the Int8/Float16/Float32 GPU arms, and what deliberately is not
------------------------------------------------------------------------------------------------
Different: the four GEMV weight matrices per layer (`w_qkv`, `w_o`, `w_gu`, `w_down`) are quantized
to PACKED int4 (per-output-row symmetric, `scale = max(|row|) / 7`, two signed 4-bit values per
byte) instead of Int8/Float16/Float32, and read through the `_i4` kernel twins, which dequantize
each nibble to Float32 (`Float32(nibble) * row_scale`) immediately on load and accumulate in
Float32 — see `residentk.kernels._I4P`'s docstring. The tied embedding/lm_head table DELIBERATELY
STAYS Int8 (this arm's task was scoped to the three per-layer GEMV roles int8 already covers, not
the vocabulary table). Norm gains, the KV cache, the RoPE tables and every activation stay Float32,
identically to every other GPU arm.

Not different: dispatch count (171/token, the SAME budget), dispatch shapes, the prompt, the token
ids, the greedy rule, the reported `decode-only tokens/sec` definition, and the output file format
— so `benchmarks/llm_smoke/verify_generation.py` cross-checks this arm against the SAME
`transformers`-CPU reference with no changes, and a diff against the Int8/Float16/Float32 arms' own
`generated_ids.txt` isolates int4 quantization as the only variable.

This driver is the STAGED CORRECTNESS vehicle for stages (b) and (c) of this arm's task: stage (b)
is the first `step()` call below (a full single-token decode step on the REAL model, comparable
against the int8 arm's own first step, token 12095 being the known-correct greedy token); stage (c)
is the full 16-token greedy sequence this driver writes to `generated_ids.txt`, checked against the
same `transformers`-CPU reference every other arm is checked against. If stage (c) diverges from
the reference, that is reported by `verify_generation.py` precisely (which step, which token) —
this driver does not tune anything to avoid that outcome; it reports the sequence int4
quantization actually produces, including a genuine divergence if there is one.

Prefill here is the decode path run `n_prompt` times — see `qwen3_generate_metal_fp16.mojo`'s own
docstring for why that is exact for a causal model, not a shortcut.
"""

from std.math import sqrt
from std.sys import has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_MAX_CONTEXT,
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
    residentk_weight_elems,
)
from residentk.probe import resident_session_probe
from residentk.session import RESIDENT_GPU_BUILD, _ResidentQwen3I4, _resident_preflight

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
"""The same shared, read-only checkpoint dump `qwen3_generate.mojo` reads."""

comptime OUT_DIR: String = "/tmp/bb/qwen3_ckpt/mojo_generate_metal_i4/"
"""This arm's OWN output directory, distinct from every other arm's."""

comptime N_NEW_MAX: Int = 16
comptime EOS_TOKEN_ID: Int = 151643


fn _ceil_div(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


fn _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_generate_metal_i4: " + ctx + " failed, status=" + String(status))


fn _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_generate_metal_i4: " + ctx + " failed, status=" + String(status)
            + " (" + residentk_status_name(status) + ")"
        )


fn _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


fn _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen3_generate_metal_i4: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


fn _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_generate_metal_i4: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


fn _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


fn _write_text(path: String, text: String) raises:
    var f = open(path, "w")
    f.write_bytes(text.as_bytes())
    f.close()


fn _ms(ns: UInt) -> Float64:
    return Float64(Int(ns)) / 1.0e6


def main() raises:
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
        raise Error("qwen3_generate_metal_i4: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = RESIDENT_MAX_CONTEXT

    print("qwen3_generate_metal_i4: d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q,
          "h_kv=", h_kv, "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size,
          "n_prompt=", n_prompt, "n_new_max=", N_NEW_MAX)

    var probe = resident_session_probe(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size)
    print("  probe: kernels_compiled=", probe.kernels_compiled,
          "device_present=", probe.device_present,
          "session_possible=", probe.session_possible,
          "status=", residentk_status_name(probe.status))
    print("  dispatch budget per token:", residentk_dispatch_budget(n_layers))
    var total_elems = residentk_weight_elems(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size)

    # The THREE GEMV-shaped weight matrix roles per layer (w_qkv, w_o, w_gu, w_down -- four
    # matrices, three kernel roles) are PACKED int4 in this arm (2 elements/byte). The tied
    # embed/lm_head table DELIBERATELY stays Int8 (1 byte/element) -- see this file's own docstring
    # and residentk.session._ResidentQwen3I4's. Byte counts below use ceil(k_in/2) PER ROW, exactly
    # as `_quantize_transposed_into_i4` packs, so this reports the REAL resident footprint rather
    # than an `elems/2` shortcut that would be wrong if any row width were odd (none is, for this
    # checkpoint, but the arithmetic does not assume it).
    var n_q = h_q * d_head
    var n_kv = h_kv * d_head
    var n_qkv = n_q + 2 * n_kv
    var qkv_bytes_per_row = _ceil_div(d_model, 2)
    var o_bytes_per_row = _ceil_div(n_q, 2)
    var gu_bytes_per_row = _ceil_div(d_model, 2)
    var down_bytes_per_row = _ceil_div(d_ff, 2)
    var i4_bytes = n_layers * (
        n_qkv * qkv_bytes_per_row + d_model * o_bytes_per_row
        + 2 * d_ff * gu_bytes_per_row + d_model * down_bytes_per_row
    )
    var i4_source_elems = n_layers * (
        n_qkv * d_model + d_model * n_q + 2 * d_ff * d_model + d_model * d_ff
    )
    var embed_i8_elems = vocab_size * d_model
    var n_scale_rows = n_layers * (n_qkv + d_model + 2 * d_ff + d_model) + vocab_size
    var f32_rest_elems = total_elems - i4_source_elems - embed_i8_elems
    var bytes_f32_arm = Float64(total_elems * 4)
    var bytes_i4_arm = Float64(
        i4_bytes + embed_i8_elems * 1 + n_scale_rows * 4 + f32_rest_elems * 4
    )
    print("  resident elements (same shape, same count as the Float32 arm):", total_elems)
    print("     of which packed-int4 in THIS arm (w_qkv/w_o/w_gu/w_down only):", i4_source_elems,
          "source elements ==", Float64(i4_bytes) / 1.0e9, "GB packed (Float32 would be",
          Float64(i4_source_elems * 4) / 1.0e9, "GB)")
    print("     plus the tied embed/lm_head table, DELIBERATELY Int8 in this arm:",
          embed_i8_elems, "==", Float64(embed_i8_elems) / 1.0e9, "GB")
    print("     plus one Float32 scale per output row:", n_scale_rows, "rows ==",
          Float64(n_scale_rows * 4) / 1.0e9, "GB")
    print("     of which stays Float32 in THIS arm (norm gains + KV-cache allocation):",
          f32_rest_elems, "==", Float64(f32_rest_elems * 4) / 1.0e9, "GB")
    print("  resident bytes, Float32 arm:", bytes_f32_arm / 1.0e9, "GB   int4 arm:",
          bytes_i4_arm / 1.0e9, "GB   ratio:", bytes_f32_arm / bytes_i4_arm)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, N_NEW_MAX, max_ctx, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_generate_metal_i4: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU and DEVELOPER_DIR set, on a host with an accelerator)")
        return

    @parameter
    if not RESIDENT_GPU_BUILD:
        print("qwen3_generate_metal_i4: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_generate_metal_i4: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_generate_metal_i4: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var t_wall_start = perf_counter_ns()

        # ═══ ONE-TIME: open the session, quantize every weight matrix, upload ═══
        var t_open0 = perf_counter_ns()
        var s = _ResidentQwen3I4(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        var t_open1 = perf_counter_ns()
        print("  device:", s.device_name())
        print("  session open (context + ~", bytes_i4_arm / 1.0e9,
              "GB of device allocations + 8 shaders compiled):", _ms(t_open1 - t_open0), "ms")

        var rt = rope_table(d_head, max_ctx, theta)
        _check(rt.status, ATTN_OK, "rope_table")

        var t_read0 = perf_counter_ns()
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        var t_read1 = perf_counter_ns()

        var t_up0 = perf_counter_ns()
        _check_resident(
            s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx),
            "upload_globals",
        )
        var t_up1 = perf_counter_ns()
        var read_ms = _ms(t_read1 - t_read0)
        var upload_ms = _ms(t_up1 - t_up0)

        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var tr0 = perf_counter_ns()
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
            var tr1 = perf_counter_ns()
            _check_resident(
                s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
            var tr2 = perf_counter_ns()
            read_ms += _ms(tr1 - tr0)
            upload_ms += _ms(tr2 - tr1)

        _check_resident(s.seal(), "seal")
        var t_load_end = perf_counter_ns()
        print("  ONE-TIME weight cost, split:")
        print("     read Float64 blob from disk:      ", read_ms, "ms")
        print("     per-row packed-int4-quantize (weight matrices) / Float32 (norm gains) +",
              "transpose + upload to device:", upload_ms, "ms")
        print("     total one-time (open + read + convert + upload):",
              _ms(t_load_end - t_wall_start), "ms")

        # ═══ PREFILL: the prompt through the one-token path, position by position ═══
        var generated_ids = List[Int]()
        for i in range(n_prompt):
            generated_ids.append(prompt_ids[i])
        var per_step_ms = List[Float64]()
        var per_step_logit = List[Float64]()
        var stopped_on_eos = False
        var dispatches_per_token = 0

        var tp0 = perf_counter_ns()
        var first_tok = -1
        var first_logit = 0.0
        for t in range(n_prompt):
            var r = s.step(prompt_ids[t], t)
            _check_resident(r.status, "step(prefill pos " + String(t) + ")")
            dispatches_per_token = r.dispatches
            first_tok = r.token_id
            first_logit = r.logit
        var tp1 = perf_counter_ns()

        # ── stage (b): the FIRST full decode step on the real model — the single-token comparison
        # this arm's task asked for, directly against the int8 arm's own first step and the
        # known-correct token (12095). ──
        print("  STAGE (b) single-token decode: first generated id=", first_tok,
              "logit=", first_logit)

        generated_ids.append(first_tok)
        per_step_ms.append(_ms(tp1 - tp0))
        per_step_logit.append(first_logit)
        print("  prefill:", n_prompt, "tokens through the decode path,", _ms(tp1 - tp0),
              "ms; first generated id=", first_tok, "logit=", first_logit)
        print("  dispatches issued per token:", dispatches_per_token,
              "(budget", residentk_dispatch_budget(n_layers), ")")
        if dispatches_per_token != residentk_dispatch_budget(n_layers):
            raise Error(
                "qwen3_generate_metal_i4: the session issued " + String(dispatches_per_token)
                + " dispatches but residentk_dispatch_budget says "
                + String(residentk_dispatch_budget(n_layers))
                + " -- the design and the code disagree"
            )
        if first_tok == EOS_TOKEN_ID:
            stopped_on_eos = True

        # ═══ DECODE: one token at a time, everything already resident ═══
        var t_decode_start = perf_counter_ns()
        var n_decoded = 1
        if not stopped_on_eos:
            for step in range(1, N_NEW_MAX):
                var pos = n_prompt + step - 1
                var ts0 = perf_counter_ns()
                var r = s.step(generated_ids[len(generated_ids) - 1], pos)
                var ts1 = perf_counter_ns()
                _check_resident(r.status, "step(decode pos " + String(pos) + ")")
                generated_ids.append(r.token_id)
                per_step_ms.append(_ms(ts1 - ts0))
                per_step_logit.append(r.logit)
                n_decoded += 1
                print("  decode step", step, "pos=", pos, "-> id=", r.token_id,
                      "logit=", r.logit, _ms(ts1 - ts0), "ms")
                if r.token_id == EOS_TOKEN_ID:
                    stopped_on_eos = True
                    break
        var t_decode_end = perf_counter_ns()

        var decode_steps = n_decoded - 1
        var decode_ms = _ms(t_decode_end - t_decode_start) if decode_steps > 0 else 0.0
        print("qwen3_generate_metal_i4: done. stopped_on_eos=", stopped_on_eos)
        print("  total wall:", _ms(t_decode_end - t_wall_start),
              "ms (includes weight load + prefill + decode)")
        if decode_steps > 0:
            print("  decode-only (excludes weight load AND prefill):", decode_ms, "ms for",
                  decode_steps, "steps ==",
                  Float64(decode_steps) / (decode_ms / 1000.0), "tokens/sec")

        # ── the id sequence, in the format verify_generation.py already reads ──
        var out_lines = String("n_prompt ") + String(n_prompt) + String("\n")
        out_lines += String("n_generated ") + String(n_decoded) + String("\n")
        out_lines += String("stopped_on_eos ") + (String("1") if stopped_on_eos else String("0")) + String("\n")
        for i in range(n_decoded):
            var step_ms = per_step_ms[i] if i < len(per_step_ms) else 0.0
            var step_logit = per_step_logit[i] if i < len(per_step_logit) else 0.0
            out_lines += String(i) + String(" ") + String(n_prompt + i) + String(" ") + \
                String(generated_ids[n_prompt + i]) + String(" ") + String(step_logit) + \
                String(" ") + String(step_ms) + String("\n")
        _write_text(OUT_DIR + "generated_ids.txt", out_lines)
        print("  generated ids written to", OUT_DIR + "generated_ids.txt")
