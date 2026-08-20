"""qwen3_generate_cuda.mojo — the SAME Qwen3-0.6B-Base greedy generation as
`qwen3_generate_metal.mojo`, run through the CUDA-native resident session
(`residentk.session_cuda._CudaResidentQwen3`) on real NVIDIA hardware — the first NVIDIA LLM
inference in this tree. Same `/tmp/qwen3smoke/{manifest.json,weights.blob}` checkpoint dump, same
256-token race prompt (read from the manifest's own `input_ids`, never restated here).

Two differences from the Metal arm, both stated rather than hidden:

* PREFILL IS BATCHED. The Metal arm runs the prompt through the one-token decode path position by
  position; this arm dispatches the m_rows > 1 prefill GEMM path (`residentk.
  kernels_prefill_f32`'s tiled GEMMs plus the batched weightless kernels) in 128-row chunks — the
  shape the Phase-3 prefill tok/s number needs.
* The oracle is enforced IN THE DRIVER: the campaign's known-correct greedy continuation for the
  256-token race prompt (first 8 ids `[374, 12095, 13, 576, 6722, 315, 9625, 374]`, then the
  7-token repeat cycle `[12095, 13, 576, 6722, 315, 9625, 374]` — the model repeats "Paris.\\nThe
  capital of France is" forever on this prompt). A mismatch prints FAIL and exits nonzero.

Build (the CUDA lane recipe, no CUDA toolkit at build time — see the Phase-0 evidence in
`benchmarks/llm_smoke/residentk_cuda_smoke.mojo`'s module docstring for the link line).
"""

from std.math import sqrt
from std.sys import exit, has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_DEFAULT_CONTEXT,
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
    residentk_weight_elems,
)
from residentk.probe import resident_session_probe
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_PREFILL_TILE, CUDA_SESSION_BUILD, _CudaResidentQwen3

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
"""The same shared, read-only checkpoint dump the Metal arm reads — converted from the GGUF (or
the safetensors checkpoint) by the campaign's own converters."""

comptime N_NEW_MAX: Int = 16
comptime EOS_TOKEN_ID: Int = 151643
comptime MAX_CTX: Int = 1024
"""Room for the 256-token race prompt plus a long decode tail (Phase 3's gen=256 benchmark
included) without re-opening the session."""

comptime ORACLE_WINDOW: Int = 8
"""The campaign's known-correct greedy window for the 256-token race prompt on Qwen3-0.6B-Base —
the exact ids every oracle gate in `REALRACE_RESULTS.md` recorded."""


def _oracle_token(i: Int) -> Int:
    """`i`-th expected generated token: the 8-token window, then the 7-token repeat cycle the
    model settles into on this prompt (see `tests/test_inference_gpu_e2e.py`'s own assertion of
    the same invariant)."""
    if i == 0:
        return 374
    if i == 1:
        return 12095
    if i == 2:
        return 13
    if i == 3:
        return 576
    if i == 4:
        return 6722
    if i == 5:
        return 315
    if i == 6:
        return 9625
    if i == 7:
        return 374
    # The cycle the model repeats forever on this prompt: "Paris.\nThe capital of France is".
    var cycle_pos = (i - ORACLE_WINDOW) % 7
    if cycle_pos == 0:
        return 12095
    if cycle_pos == 1:
        return 13
    if cycle_pos == 2:
        return 576
    if cycle_pos == 3:
        return 6722
    if cycle_pos == 4:
        return 315
    if cycle_pos == 5:
        return 9625
    return 374


def _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_generate_cuda: " + ctx + " failed, status=" + String(status))


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_generate_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_generate_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    # Mojo 1.0.0: File.seek takes an Int offset (the pre-1.0 UInt64 spelling no longer converts).
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_generate_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    """Read one tensor out of the flat Float64 blob — the same loader shape the Metal arm's
    driver uses (a driver helper with hardcoded paths, deliberately copied, not shared)."""
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    # Mojo 1.0.0: perf_counter_ns() returns Int.
    return Float64(ns) / 1.0e6


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
        raise Error("qwen3_generate_cuda: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = MAX_CTX

    print("qwen3_generate_cuda: d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q,
          "h_kv=", h_kv, "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size,
          "n_prompt=", n_prompt, "n_new_max=", N_NEW_MAX, "prefill_tile=", CUDA_PREFILL_TILE)

    # ── the capability answer, before anything is allocated ────────────────────
    var probe = resident_session_probe(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size)
    print("  probe: kernels_compiled=", probe.kernels_compiled,
          "device_present=", probe.device_present,
          "session_possible=", probe.session_possible,
          "status=", residentk_status_name(probe.status))
    print("  decode dispatch budget per token:", residentk_dispatch_budget(n_layers))
    print("  resident Float32 elements:", residentk_weight_elems(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx),
        "==", Float64(residentk_weight_elems(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx) * 4) / 1.0e9, "GB")

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, N_NEW_MAX, max_ctx, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_generate_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time gate
        # is visible at this file's only construction site. Everything below is elided from a
        # build without BOTH defines, which is why a Metal or CPU host can compile this file.
        print("qwen3_generate_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_generate_cuda: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_generate_cuda: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var t_wall_start = perf_counter_ns()

        # ═══ ONE-TIME: open the session, convert every weight to Float32, upload ═══
        var t_open0 = perf_counter_ns()
        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        var t_open1 = perf_counter_ns()
        print("  device:", s.device_name())
        print("  session open (context + device allocations):", _ms(t_open1 - t_open0), "ms")

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
        print("     read Float64 blob from disk:               ", read_ms, "ms")
        print("     narrow to Float32 + transpose + upload:    ", upload_ms, "ms")
        print("     total one-time (open + read + convert + upload):",
              _ms(t_load_end - t_wall_start), "ms")

        # ═══ PREFILL: the batched m_rows GEMM path, chunked ═══
        var tp0 = perf_counter_ns()
        var pf = s.prefill(prompt_ids)
        var tp1 = perf_counter_ns()
        _check_resident(pf.status, "prefill")
        var prefill_ms = _ms(tp1 - tp0)
        print("  prefill:", n_prompt, "tokens, batched tile =", CUDA_PREFILL_TILE, "in",
              prefill_ms, "ms ==", Float64(n_prompt) / (prefill_ms / 1000.0), "tokens/sec")
        print("     dispatches issued:", pf.dispatches,
              "(1 embed + n_layers*8 per chunk, +2 lm_head on the final chunk)")
        print("     first generated id =", pf.token_id, "logit =", pf.logit)

        var generated_ids = List[Int]()
        for i in range(n_prompt):
            generated_ids.append(prompt_ids[i])
        generated_ids.append(pf.token_id)
        var stopped_on_eos = pf.token_id == EOS_TOKEN_ID

        # ═══ DECODE: one token at a time, everything already resident ═══
        var per_step_ms = List[Float64]()
        var t_decode_start = perf_counter_ns()
        var n_decoded = 1
        if not stopped_on_eos:
            for step in range(1, N_NEW_MAX):
                var pos = n_prompt + step - 1
                var ts0 = perf_counter_ns()
                var r = s.step(generated_ids[len(generated_ids) - 1], pos)
                var ts1 = perf_counter_ns()
                _check_resident(r.status, "step(decode pos " + String(pos) + ")")
                if r.dispatches != residentk_dispatch_budget(n_layers):
                    raise Error(
                        "qwen3_generate_cuda: the session issued " + String(r.dispatches)
                        + " dispatches but residentk_dispatch_budget says "
                        + String(residentk_dispatch_budget(n_layers))
                        + " -- the design and the code disagree"
                    )
                generated_ids.append(r.token_id)
                per_step_ms.append(_ms(ts1 - ts0))
                n_decoded += 1
                print("  decode step", step, "pos=", pos, "-> id=", r.token_id,
                      "logit=", r.logit, _ms(ts1 - ts0), "ms")
                if r.token_id == EOS_TOKEN_ID:
                    stopped_on_eos = True
                    break
        var t_decode_end = perf_counter_ns()

        var decode_steps = n_decoded - 1
        var decode_ms = _ms(t_decode_end - t_decode_start) if decode_steps > 0 else 0.0
        print("qwen3_generate_cuda: done. stopped_on_eos=", stopped_on_eos)
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
            var step_ms = per_step_ms[i - 1] if i >= 1 and i - 1 < len(per_step_ms) else 0.0
            out_lines += String(i) + String(" ") + String(n_prompt + i) + String(" ") + \
                String(generated_ids[n_prompt + i]) + String(" 0 ") + String(step_ms) + String("\n")
        var f = open("/tmp/qwen3smoke/generated_ids_cuda.txt", "w")
        f.write_bytes(out_lines.as_bytes())
        f.close()
        print("  generated ids written to /tmp/qwen3smoke/generated_ids_cuda.txt")

        # ═══ THE ORACLE: every generated token must sit on the campaign's known-correct sequence ═══
        var mismatches = 0
        for i in range(n_decoded):
            var want = _oracle_token(i)
            var got = generated_ids[n_prompt + i]
            if got != want:
                mismatches += 1
                print("  ORACLE MISMATCH at generated token", i, ": got", got, "want", want)
        if mismatches == 0 and n_decoded >= ORACLE_WINDOW:
            print("RESULT: PASS —", n_decoded, "greedy tokens match the campaign oracle")
            exit(0)
        else:
            print("RESULT: FAIL —", mismatches, "mismatched tokens (decoded", n_decoded, ")")
            exit(1)
