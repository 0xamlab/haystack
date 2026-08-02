"""qwen3_generate_batch_f16.mojo — the fp16-weight twin of `qwen3_generate_batch.mojo`: the SAME
Qwen3-0.6B-Base greedy decode, through the SAME batched C-shim session mechanism, with the four
GEMV weight matrices per layer and the tied embed/lm_head table resident as Float16 instead of
Float32 (`metaldispatch.session._MBQwen3F16`).

MUST be built and run as its OWN, separate binary — never in the same binary as
`qwen3_generate_batch.mojo`'s `_MBQwen3` (Float32). See `metaldispatch.session`'s module docstring,
"Why `_MBQwen3F16` is a SEPARATE binary's struct, not a second set of roles in the same one", for
why: compiling both a role's Float32 and Float16 kernel into one binary makes their truncated Metal
pipeline names collide and the shim's name-based classifier cannot tell them apart.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m \\
        -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \\
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo \\
        -o /tmp/qwen3_batch_f16 \\
        -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \\
        -Xlinker -framework -Xlinker Foundation
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_batch_f16

Same checkpoint, same prompt, same output format as `qwen3_generate_batch.mojo` and
`qwen3_generate_metal.mojo`, so `benchmarks/llm_smoke/verify_generation.py` cross-checks this arm
with no changes. This file is a near-copy of `qwen3_generate_batch.mojo`'s own driver, deliberately
not shared with it for the same reason that file gives for not sharing with `qwen3_generate.mojo`
and `qwen3_generate_metal.mojo`: these are `mojo run` driver helpers with hardcoded paths, not
kernels, and every file this comparison must leave provably unmodified stays that way.
"""

from std.math import sqrt
from std.sys import has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_DEFAULT_CONTEXT
from metaldispatch.contract import MB_OK, metaldispatch_dispatch_budget, metaldispatch_status_name
from metaldispatch.session import _MBQwen3F16, _mb_preflight, MB_GPU_BUILD

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime OUT_DIR: String = "/tmp/bb/qwen3_ckpt/mojo_generate_batch_f16/"
"""This arm's OWN output directory, distinct from every other arm's, so all `generated_ids.txt`
files stay independently comparable."""

comptime N_NEW_MAX: Int = 16
comptime EOS_TOKEN_ID: Int = 151643


fn _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_generate_batch_f16: " + ctx + " failed, status=" + String(status))


fn _check_mb(status: Int, ctx: String) raises:
    if status != MB_OK:
        raise Error(
            "qwen3_generate_batch_f16: " + ctx + " failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
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
        raise Error("qwen3_generate_batch_f16: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


fn _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_generate_batch_f16: short read at byte offset " + String(byte_offset))
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
        raise Error("qwen3_generate_batch_f16: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = RESIDENT_DEFAULT_CONTEXT

    print("qwen3_generate_batch_f16: d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q,
          "h_kv=", h_kv, "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size,
          "n_prompt=", n_prompt, "n_new_max=", N_NEW_MAX)
    print("  dispatch budget per token:", metaldispatch_dispatch_budget(n_layers))

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, N_NEW_MAX, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_generate_batch_f16: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        print("  (build with -D ALGENTA_GPU and DEVELOPER_DIR set, on a host with an accelerator,")
        print("   and link batch_shim.o)")
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_generate_batch_f16: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_generate_batch_f16: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_generate_batch_f16: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var t_wall_start = perf_counter_ns()

        # ═══ ONE-TIME: open the shim session, resolve pipelines, allocate + upload ═══
        var t_open0 = perf_counter_ns()
        var s = _MBQwen3F16(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        var t_open1 = perf_counter_ns()
        print("  device:", s.device_name())
        print("  session open (shim session + pipelines + ~1.3 GB of fp16-weight device allocations):",
              _ms(t_open1 - t_open0), "ms")

        var rt = rope_table(d_head, max_ctx, theta)
        _check(rt.status, ATTN_OK, "rope_table")

        var t_read0 = perf_counter_ns()
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        var t_read1 = perf_counter_ns()

        var t_up0 = perf_counter_ns()
        _check_mb(
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
            _check_mb(
                s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
            var tr2 = perf_counter_ns()
            read_ms += _ms(tr1 - tr0)
            upload_ms += _ms(tr2 - tr1)

        _ = s.seal()
        var t_load_end = perf_counter_ns()
        print("  ONE-TIME weight cost, split:")
        print("     read Float64 blob from disk:      ", read_ms, "ms")
        print("     narrow to Float16 + transpose + upload to device:", upload_ms, "ms")
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
            _check_mb(r.status, "step(prefill pos " + String(t) + ")")
            dispatches_per_token = r.dispatches
            first_tok = r.token_id
            first_logit = r.logit
        var tp1 = perf_counter_ns()

        generated_ids.append(first_tok)
        per_step_ms.append(_ms(tp1 - tp0))
        per_step_logit.append(first_logit)
        print("  prefill:", n_prompt, "tokens through the decode path,", _ms(tp1 - tp0),
              "ms; first generated id=", first_tok, "logit=", first_logit)
        print("  dispatches issued per token:", dispatches_per_token,
              "(budget", metaldispatch_dispatch_budget(n_layers), ")")
        if dispatches_per_token != metaldispatch_dispatch_budget(n_layers):
            raise Error(
                "qwen3_generate_batch_f16: the session issued " + String(dispatches_per_token)
                + " dispatches but metaldispatch_dispatch_budget says "
                + String(metaldispatch_dispatch_budget(n_layers))
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
                _check_mb(r.status, "step(decode pos " + String(pos) + ")")
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
        print("qwen3_generate_batch_f16: done. stopped_on_eos=", stopped_on_eos)
        print("  total wall:", _ms(t_decode_end - t_wall_start),
              "ms (includes weight load + prefill + decode)")
        if decode_steps > 0:
            print("  decode-only (excludes weight load AND prefill):", decode_ms, "ms for",
                  decode_steps, "steps ==",
                  Float64(decode_steps) / (decode_ms / 1000.0), "tokens/sec")

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
