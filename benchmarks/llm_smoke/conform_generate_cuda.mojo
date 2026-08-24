"""conform_generate_cuda.mojo — the model-agnostic conformance battery's CUDA arm: the SAME
fact-driven greedy generation the Metal SDK door runs, on the CUDA-native resident session
(`residentk.session_cuda._CudaResidentQwen3`), for ANY checkpoint whose facts the capability
table claims supported on the CUDA backend.

Usage:
    conform_generate_cuda <ckpt_dir> [--max-new N]

`ckpt_dir` carries the converter's `manifest.json` + `weights.blob` pair. Every fact is read
from the manifest -- dims, qk_norm, tie, q/k/v bias, eos, rope scaling -- never hardcoded to a
model: this is the driver half of the "any model whose facts land in the table runs with zero
per-model code" proof (the other half is `scripts/algenta_synthetic_battery.py`, which compares
the tokens printed below against the independent Float64 reference). The machine-readable line

    CONFORM_TOKENS: <id> <id> ...

carries the generated ids only (prompt excluded), exactly the reference's coordinate system.

Build: the CUDA lane recipe (see `qwen3_generate_cuda.mojo`'s docstring): `-D ALGENTA_GPU
-D ALGENTA_CUDA --target-accelerator sm_NN`; staging tier per model (`-D ALGENTA_STAGE_6144` /
`_8192` / `_18944`) exactly as `residentk/contract.mojo` declares."""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator
from std.time import perf_counter_ns
from json.parser import (
    json_get_array,
    json_get_float,
    json_get_int,
    json_get_object,
    json_array_tokens,
)
from conv import parse_int, parse_float64
from attnk.rope import rope_table, rope_table_freq_factors, rope_table_llama3
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
)
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_PREFILL_TILE, CUDA_SESSION_BUILD, _CudaResidentQwen3

comptime ROPE_SCALING_TYPE_LLAMA3: Int = 3
"""The manifest's `rope_scaling_type` code for the llama-3.1 scheme -- the same value the SDK
converter writes (`algenta.inference._ROPE_SCALING_TYPE_LLAMA3_CODE`)."""


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "conform_generate_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("conform_generate_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("conform_generate_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: conform_generate_cuda <ckpt_dir> [--max-new N]")
        exit(2)
    var ckpt_dir = String(args[1])
    var max_new = 8
    var i = 2
    while i < len(args):
        var a = String(args[i])
        if a == "--max-new" and i + 1 < len(args):
            max_new = parse_int(String(args[i + 1]))
            i += 2
        else:
            i += 1

    var manifest_path = ckpt_dir + "/manifest.json"
    var blob_path = ckpt_dir + "/weights.blob"
    var manifest = _read_text_file(manifest_path)
    var config = json_get_object(manifest, "config")

    # ── the facts, all from the manifest ──────────────────────────────────────
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
    # Family-convention facts (the converter's tensors-are-the-truth probes wrote them):
    # absent keys default to the Qwen3 convention, so a pre-convention manifest runs unchanged.
    var has_qk_norm = json_get_int(config, "has_qk_norm", 1)
    var tied = json_get_int(config, "tie_word_embeddings", 1)
    var has_qkv_bias = json_get_int(config, "attention_bias", 0)
    var eos_token_id = json_get_int(config, "eos_token_id", -1)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0:
        raise Error("conform_generate_cuda: manifest config did not parse")
    if (has_qk_norm != 0 and has_qk_norm != 1) or (tied != 0 and tied != 1) \
       or (has_qkv_bias != 0 and has_qkv_bias != 1):
        raise Error("conform_generate_cuda: a convention flag is neither 0 nor 1")

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new
    var max_ctx = 512
    while max_ctx < needed_ctx:
        max_ctx = max_ctx * 2

    print("conform_generate_cuda: d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q,
          "h_kv=", h_kv, "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size,
          "n_prompt=", n_prompt, "max_new=", max_new,
          "qk_norm=", has_qk_norm, "tied=", tied, "qkv_bias=", has_qkv_bias,
          "eos=", eos_token_id, "prefill_tile=", CUDA_PREFILL_TILE)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new, max_ctx, eps, scale
    )
    if pre != RESIDENT_OK:
        print("conform_generate_cuda: REFUSED by preflight:", residentk_status_name(pre))
        print("CONFORM_REFUSED: " + residentk_status_name(pre))
        exit(3)

    @parameter
    if not CUDA_SESSION_BUILD:
        print("conform_generate_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        exit(4)
    else:
        if not has_accelerator():
            print("conform_generate_cuda: no accelerator on this host")
            exit(4)

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for t in id_tokens:
            prompt_ids.append(parse_int(String(t)))
        if len(prompt_ids) != n_prompt:
            raise Error("conform_generate_cuda: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")

        # ── open the session with the model's own facts ───────────────────────
        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale,
            has_qk_norm, 1 if tied == 0 else 0, 0, has_qkv_bias,
        )

        # ── rope table from the manifest's own scaling facts, then the shared
        # globals upload (embed + final norm + the rope tables) ───────────────
        var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
        var factors_arr = json_get_array(config, "rope_freq_factors")
        if factors_arr.byte_length() > 0:
            var factor_tokens = json_array_tokens(factors_arr)
            var factors = List[Float64]()
            for t in factor_tokens:
                factors.append(parse_float64(String(t)))
            var rt = rope_table_freq_factors(d_head, max_ctx, theta, factors^)
            if rt.status != ATTN_OK:
                raise Error("conform_generate_cuda: rope_freq_factors unusable")
            _check_resident(
                s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx),
                "upload_globals",
            )
        else:
            var scaling_type = json_get_int(config, "rope_scaling_type", 0)
            if scaling_type == 0:
                var rt = rope_table(d_head, max_ctx, theta)
                if rt.status != ATTN_OK:
                    raise Error("conform_generate_cuda: rope table unusable")
                _check_resident(
                    s.upload_globals(
                        embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
                    ),
                    "upload_globals",
                )
            elif scaling_type == ROPE_SCALING_TYPE_LLAMA3:
                var factor = json_get_float(config, "rope_scaling_factor", -1.0)
                var low = json_get_float(config, "rope_scaling_low_freq_factor", -1.0)
                var high = json_get_float(config, "rope_scaling_high_freq_factor", -1.0)
                var orig = json_get_float(
                    config, "rope_scaling_original_max_position_embeddings", -1.0
                )
                var rt = rope_table_llama3(d_head, max_ctx, theta, factor, low, high, orig)
                if rt.status != ATTN_OK:
                    raise Error("conform_generate_cuda: llama3 rope table unusable")
                _check_resident(
                    s.upload_globals(
                        embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
                    ),
                    "upload_globals",
                )
            else:
                raise Error("conform_generate_cuda: unknown rope_scaling_type")

        # ── untied lm_head: the checkpoint's own output projection ───────────
        if tied == 0:
            _check_resident(
                s.upload_lm_head(_load_tensor(blob_path, tensors_obj, "lm_head.weight")),
                "upload_lm_head",
            )

        # ── per-layer weights, branched on the qk_norm / bias facts ──────────
        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
            var ln2 = _load_tensor(
                blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
            )
            # qk_norm=0 checkpoints carry no q_norm/k_norm tensors: the session's ropewrt
            # kernels skip the norm block on the flag and never read these gains, so ones fill
            # the upload slots harmlessly (the Metal SDK entry's exact convention).
            var qn = List[Float64]()
            var kn = List[Float64]()
            if has_qk_norm == 1:
                qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
            else:
                for _j in range(d_head):
                    qn.append(1.0)
                    kn.append(1.0)
            var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
            var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
            var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
            var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
            var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
            var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
            var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
            _check_resident(
                s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
            if has_qkv_bias == 1:
                var qb = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.bias")
                var kb = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.bias")
                var vb = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.bias")
                _check_resident(s.upload_qkv_bias(layer, qb, kb, vb), "upload_qkv_bias")

        _check_resident(s.seal(), "seal")

        # ── prefill + greedy decode ───────────────────────────────────────────
        var pf = s.prefill(prompt_ids)
        _check_resident(pf.status, "prefill")

        var generated = List[Int]()
        generated.append(pf.token_id)
        var stopped = eos_token_id >= 0 and pf.token_id == eos_token_id
        if not stopped:
            for step in range(1, max_new):
                var pos = n_prompt + step - 1
                var r = s.step(generated[len(generated) - 1], pos)
                _check_resident(r.status, "step(decode pos " + String(pos) + ")")
                generated.append(r.token_id)
                if eos_token_id >= 0 and r.token_id == eos_token_id:
                    stopped = True
                    break

        var line = String("CONFORM_TOKENS:")
        for tok in generated:
            line = line + " " + String(tok)
        print(line)
        print("conform_generate_cuda: done. stopped_on_eos=", stopped,
              "expected_decode_budget=", residentk_dispatch_budget(n_layers))
