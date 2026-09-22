"""hfkernel.cuda_decode_session — resident, step-by-step Qwen3-family decode on NVIDIA through the
in-process ABI.

The same wire format as `algenta_runtime.qwen3_decode_session` (the Metal registry the worker
serves), so the generated Python `DecodeSession` is backend-agnostic:

    {"type":"qwen3_decode_open","checkpoint_dir":"/path/to/converted","prompt_token_ids":[1,2,3],
     "max_new_tokens":16}
      -> {"session":"qd_1","n_prompt":3,"max_new_tokens":16,"open_count":1}
    {"type":"qwen3_decode_next","session":"qd_1"}
      -> {"token_id":42,"position":4,"done":false,"stopped_on_eos":false,"dispatches":171}
    {"type":"qwen3_decode_close","session":"qd_1"} -> {"closed":true,"count":0}

Semantics mirrored exactly: the prefill computes the first generated token, which the first `next`
delivers without stepping; every later `next` runs one `step`; `done` is true on the response that
carries the last token (budget reached or the checkpoint's own EOS id) and is answered idempotently
afterwards; one open session at a time; `checkpoint_dir` is the CONVERTED directory
(`manifest.json` + `weights.blob`, the output of `algenta.inference.prepare_model_checkpoint`).

The device path is `residentk.session_cuda._CudaResidentQwen3`, the single-stream session the
CUDA conform drivers (`benchmarks/llm_smoke/nvidia_race/*_cuda.mojo`) are built on: Float64 weights
narrowed to Float32 at upload, resident KV cache, one `DeviceContext` for the session's life. The
session struct is heap-held through an untracked pointer (it is Movable, not Copyable) and freed on
close, which releases every device buffer it owns.

Additive module: lives outside mojo/engine/ and is staged next to `abi.mojo` by the family
builder for CUDA builds only. Nothing in the frozen engine changes. The IO helpers below are
private copies of the ones `metaldispatch.qwen3_prefill_decode` uses, so a CUDA build never
imports a Metal module.
"""

from std.math import sqrt
from std.memory import UnsafePointer, alloc
from std.origin import MutUntrackedOrigin
from std.sys import has_accelerator
from json.parser import json_array_tokens, json_get_array, json_get_float, json_get_int, json_get_object, json_get_string
from conv import parse_int
from attnk.contract import ATTN_OK
from attnk.rope import rope_table
from residentk.contract import (
    RESIDENT_DEFAULT_CONTEXT,
    RESIDENT_ERR_CODE_OUT_OF_RANGE,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_MAX_CONTEXT,
    RESIDENT_OK,
    residentk_status_name,
)
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3

comptime SessionPtr = UnsafePointer[_CudaResidentQwen3, origin=MutUntrackedOrigin]


def _json_escape(s: String) -> String:
    """Escape a String for embedding in a JSON string literal: quotes, backslashes and control bytes
    (checkpoint paths and exception text can contain any of them)."""
    var src = s.unsafe_ptr()
    var n = s.byte_length()
    var out = List[UInt8](capacity=n * 6 + 8)  # worst case: every byte a control byte -> \u00XX (6x)
    for i in range(n):
        var b = src[i]
        if b == 34:      # "
            out.append(92); out.append(34)
        elif b == 92:    # backslash
            out.append(92); out.append(92)
        elif b == 10:    # newline
            out.append(92); out.append(110)
        elif b == 13:    # carriage return
            out.append(92); out.append(114)
        elif b == 9:     # tab
            out.append(92); out.append(116)
        elif b < 32:     # other control bytes -> \u00XX (RFC 8259 §7), never dropped
            out.append(92); out.append(117); out.append(48); out.append(48)
            var hi = b >> 4
            var lo = b & 0xF
            out.append(hi + 48 if hi < 10 else hi + 87)
            out.append(lo + 48 if lo < 10 else lo + 87)
        else:
            out.append(b)
    var escaped = String()
    escaped += StringSlice(unsafe_from_utf8=Span(out))
    return escaped


def _session_error(code: String, message: String) -> String:
    var c = _json_escape(code)
    var m = _json_escape(message)
    return (
        '{"error":"' + c + ": " + m + '","error_code":"' + c
        + '","error_message":"' + m + '"}'
    )


def _status_error(status: Int, message: String) -> String:
    var name: String
    if status >= RESIDENT_OK and status <= RESIDENT_ERR_CODE_OUT_OF_RANGE:
        name = residentk_status_name(status)
    else:
        name = "resident_code_out_of_range"
    return _session_error(name, message)


def _ctx_bucket(needed_ctx: Int) -> Int:
    """Round the context up to the next power of two, floor RESIDENT_DEFAULT_CONTEXT (the
    Metal registry's own bucketing, so both backends size the KV cache the same way)."""
    var ctx = RESIDENT_DEFAULT_CONTEXT
    while ctx < needed_ctx:
        ctx = ctx * 2
    return ctx


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    """Bounded chunks (128 MiB) rather than one read: large tables exceed the single-read limit."""
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var out = List[Float64](capacity=n_elements)
    var remaining = n_elements
    comptime CHUNK_ELEMS = 1 << 24
    while remaining > 0:
        var take = CHUNK_ELEMS if remaining > CHUNK_ELEMS else remaining
        var raw = f.read_bytes(take * 8)
        if len(raw) != take * 8:
            f.close()
            raise Error("cuda_decode_session: short read at byte offset " + String(byte_offset))
        var src = raw.unsafe_ptr().bitcast[Float64]()
        for i in range(take):
            out.append(src[i])
        remaining -= take
    f.close()
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("cuda_decode_session: tensor not found in manifest: " + name)
    return _read_f64_slice(blob_path, offset * 8, n)


struct CudaDecodeSessions(Movable):
    """One open resident decode session per handle, keyed by an opaque `qd_N` string."""

    var handle: String
    var session_addr: Int  # 0 = no open session; else the address of a heap-held _CudaResidentQwen3
    var n_prompt: Int
    var max_new_tokens: Int
    var eos_token_id: Int
    var generated_ids: List[Int]  # prompt ids followed by every token generated so far
    var delivered: Int
    var done: Bool
    var next_id: Int

    def __init__(out self):
        self.handle = String("")
        self.session_addr = 0
        self.n_prompt = 0
        self.max_new_tokens = 0
        self.eos_token_id = -1
        self.generated_ids = List[Int]()
        self.delivered = 0
        self.done = False
        self.next_id = 1

    def count(self) -> Int:
        return 1 if self.session_addr != 0 else 0

    def _release(mut self):
        if self.session_addr != 0:
            var p = SessionPtr(unsafe_from_address=self.session_addr)
            p.destroy_pointee()  # frees every device buffer the session owns
            p.free()
            self.session_addr = 0
        self.handle = String("")
        self.generated_ids = List[Int]()
        self.delivered = 0
        self.done = False

    def open_from_json(mut self, raw: String) raises -> String:
        if self.count() > 0:
            return _session_error(
                "qwen3_session_already_open",
                "a qwen3 decode session (" + self.handle + ") is already open; close it before opening another.",
            )
        var checkpoint_dir = json_get_string(raw, "checkpoint_dir")
        if checkpoint_dir.byte_length() == 0:
            return _session_error("invalid_arguments", "qwen3_decode_open requires checkpoint_dir.")
        var prompt_arr = json_get_array(raw, "prompt_token_ids")
        if prompt_arr.byte_length() == 0:
            return _session_error("invalid_arguments", "qwen3_decode_open requires a non-empty prompt_token_ids array.")
        var max_new_tokens = json_get_int(raw, "max_new_tokens", 0)
        if max_new_tokens < 1:
            return _session_error("invalid_arguments", "qwen3_decode_open requires max_new_tokens >= 1.")

        var prompt_ids = List[Int]()
        try:
            var id_tokens = json_array_tokens(prompt_arr)
            for i in range(len(id_tokens)):
                prompt_ids.append(parse_int(id_tokens[i]))
        except e:
            return _session_error("invalid_arguments", "prompt_token_ids did not parse: " + String(e))
        if len(prompt_ids) == 0:
            return _session_error("invalid_arguments", "qwen3_decode_open requires a non-empty prompt_token_ids array.")

        var manifest_path = checkpoint_dir + "/manifest.json"
        var blob_path = checkpoint_dir + "/weights.blob"
        var manifest: String
        try:
            manifest = _read_text_file(manifest_path)
        except e:
            return _session_error("metaldispatch_checkpoint_unreadable", "could not read " + manifest_path + ": " + String(e))

        var d_model: Int
        var n_layers: Int
        var h_q: Int
        var h_kv: Int
        var d_head: Int
        var d_ff: Int
        var vocab_size: Int
        var theta: Float64
        var eps: Float64
        var has_qk_norm: Int
        var tied_embeddings: Int
        var eos_token_id: Int
        var tensors_obj: String
        try:
            var config = json_get_object(manifest, "config")
            d_model = json_get_int(config, "hidden_size", -1)
            n_layers = json_get_int(config, "num_hidden_layers", -1)
            h_q = json_get_int(config, "num_attention_heads", -1)
            h_kv = json_get_int(config, "num_key_value_heads", -1)
            d_head = json_get_int(config, "head_dim", -1)
            d_ff = json_get_int(config, "intermediate_size", -1)
            vocab_size = json_get_int(config, "vocab_size", -1)
            theta = json_get_float(config, "rope_theta", -1.0)
            eps = json_get_float(config, "rms_norm_eps", -1.0)
            has_qk_norm = json_get_int(config, "has_qk_norm", 1)
            tied_embeddings = json_get_int(config, "tie_word_embeddings", 1)
            eos_token_id = json_get_int(config, "eos_token_id", -1)
            tensors_obj = json_get_object(manifest, "tensors")
        except e:
            return _session_error("metaldispatch_checkpoint_unreadable", manifest_path + " did not parse: " + String(e))
        if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 or vocab_size < 1 or theta <= 0.0 or eps <= 0.0:
            return _session_error("metaldispatch_checkpoint_unreadable", manifest_path + " is missing a required config field")
        if (has_qk_norm != 0 and has_qk_norm != 1) or (tied_embeddings != 0 and tied_embeddings != 1):
            return _session_error("metaldispatch_checkpoint_unreadable", manifest_path + " carries a convention flag that is neither 0 nor 1")
        if eos_token_id < -1 or eos_token_id >= vocab_size:
            return _session_error("metaldispatch_checkpoint_unreadable", manifest_path + " declares eos_token_id outside the vocab")
        if (h_q % h_kv) != 0:
            return _session_error("metaldispatch_unsupported_architecture", "grouped-query attention requires num_attention_heads % num_key_value_heads == 0")

        var n_prompt = len(prompt_ids)
        var scale = 1.0 / sqrt(Float64(d_head))
        var max_ctx = _ctx_bucket(n_prompt + max_new_tokens)
        if max_ctx > RESIDENT_MAX_CONTEXT:
            return _session_error(
                "metaldispatch_checkpoint_unreadable",
                "n_prompt + max_new_tokens needs max_ctx=" + String(n_prompt + max_new_tokens) + ", past RESIDENT_MAX_CONTEXT=" + String(RESIDENT_MAX_CONTEXT),
            )
        var pre = _resident_preflight(d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale)
        if pre != RESIDENT_OK:
            return _status_error(pre, "preflight refused this run")

        comptime if not CUDA_SESSION_BUILD:
            return _status_error(RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT, "this build carries no CUDA kernels (built without -D ALGENTA_GPU -D ALGENTA_CUDA)")
        else:
            if not has_accelerator():
                return _status_error(RESIDENT_ERR_NO_DEVICE, "no NVIDIA device was detected on this host")
            var p = alloc[_CudaResidentQwen3](1)
            var opened = False
            try:
                p.init_pointee_move(_CudaResidentQwen3(
                    d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale,
                    has_qk_norm, 1 if tied_embeddings == 0 else 0, 0, 0,
                ))
                opened = True
                var rt = rope_table(d_head, max_ctx, theta)
                if rt.status != ATTN_OK:
                    p.destroy_pointee()
                    p.free()
                    return _session_error("metaldispatch_checkpoint_unreadable", "the rotary table could not be built for this shape")
                var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
                var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
                var st = p[].upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx)
                if st != RESIDENT_OK:
                    p.destroy_pointee()
                    p.free()
                    return _status_error(st, "upload_globals failed")
                if tied_embeddings == 0:
                    var lm = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
                    st = p[].upload_lm_head(lm)
                    if st != RESIDENT_OK:
                        p.destroy_pointee()
                        p.free()
                        return _status_error(st, "upload_lm_head failed")
                for layer in range(n_layers):
                    var prefix = "model.layers." + String(layer) + "."
                    var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                    var ln2 = _load_tensor(blob_path, tensors_obj, prefix + "post_attention_layernorm.weight")
                    var qn = List[Float64]()
                    var kn = List[Float64]()
                    if has_qk_norm == 1:
                        qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                        kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                    else:
                        for _i in range(d_head):
                            qn.append(1.0)
                            kn.append(1.0)
                    var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                    var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                    var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                    var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                    var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                    var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                    var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                    st = p[].upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd)
                    if st != RESIDENT_OK:
                        p.destroy_pointee()
                        p.free()
                        return _status_error(st, "upload_layer " + String(layer) + " failed")
                st = p[].seal()
                if st != RESIDENT_OK:
                    p.destroy_pointee()
                    p.free()
                    return _status_error(st, "seal failed")
                var first = p[].prefill(prompt_ids)
                if first.status != RESIDENT_OK:
                    p.destroy_pointee()
                    p.free()
                    return _status_error(first.status, "prefill failed")

                self.generated_ids = List[Int](capacity=n_prompt + max_new_tokens)
                for i in range(n_prompt):
                    self.generated_ids.append(prompt_ids[i])
                self.generated_ids.append(first.token_id)
                self.handle = "qd_" + String(self.next_id)
                self.next_id += 1
                self.session_addr = Int(p)
                self.n_prompt = n_prompt
                self.max_new_tokens = max_new_tokens
                self.eos_token_id = eos_token_id
                self.delivered = 0
                self.done = False
                return (
                    '{"session":"' + self.handle + '","n_prompt":' + String(n_prompt)
                    + ',"max_new_tokens":' + String(max_new_tokens) + ',"open_count":1}'
                )
            except e:
                if opened:
                    p.destroy_pointee()
                p.free()
                return _status_error(RESIDENT_ERR_LAUNCH_FAILED, "cuda session error: " + String(e))

    def next_from_json(mut self, raw: String) raises -> String:
        var handle = json_get_string(raw, "session")
        if handle.byte_length() == 0:
            return _session_error("invalid_arguments", "qwen3_decode_next requires a session.")
        if self.session_addr == 0 or handle != self.handle:
            return _session_error("qwen3_session_not_found", "no open qwen3 decode session " + handle + ".")
        var eos_id = self.eos_token_id
        if self.done:
            var last = self.generated_ids[len(self.generated_ids) - 1]
            return (
                '{"token_id":' + String(last) + ',"position":' + String(len(self.generated_ids))
                + ',"done":true,"stopped_on_eos":' + ("true" if (eos_id >= 0 and last == eos_id) else "false")
                + ',"dispatches":0}'
            )
        var tok: Int
        var dispatches = 0
        if self.delivered < len(self.generated_ids) - self.n_prompt:
            tok = self.generated_ids[self.n_prompt + self.delivered]  # computed by the prefill
        else:
            comptime if not CUDA_SESSION_BUILD:
                return _status_error(RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT, "this build carries no CUDA kernels")
            else:
                var pos = self.n_prompt + self.delivered - 1
                var last_tok = self.generated_ids[len(self.generated_ids) - 1]
                var p = SessionPtr(unsafe_from_address=self.session_addr)
                var r: _StepOutLike
                try:
                    var out = p[].step(last_tok, pos)
                    r = _StepOutLike(out.token_id, out.dispatches, out.status)
                except e:
                    return _status_error(RESIDENT_ERR_LAUNCH_FAILED, "cuda session error: " + String(e))
                if r.status != RESIDENT_OK:
                    return _status_error(r.status, "step(pos=" + String(pos) + ") failed")
                tok = r.token_id
                dispatches = r.dispatches
                self.generated_ids.append(tok)
        self.delivered += 1
        var is_eos = eos_id >= 0 and tok == eos_id
        var is_done = is_eos or self.delivered >= self.max_new_tokens
        self.done = is_done
        return (
            '{"token_id":' + String(tok) + ',"position":' + String(self.n_prompt + self.delivered)
            + ',"done":' + ("true" if is_done else "false")
            + ',"stopped_on_eos":' + ("true" if is_eos else "false")
            + ',"dispatches":' + String(dispatches) + "}"
        )

    def close_from_json(mut self, raw: String) -> String:
        var handle = json_get_string(raw, "session")
        if handle.byte_length() == 0:
            return _session_error("invalid_arguments", "qwen3_decode_close requires a session.")
        if self.session_addr == 0 or handle != self.handle:
            return _session_error("qwen3_session_not_found", "no open qwen3 decode session " + handle + ".")
        self._release()
        return '{"closed":true,"count":0}'

    def __del__(deinit self):
        if self.session_addr != 0:
            var p = SessionPtr(unsafe_from_address=self.session_addr)
            p.destroy_pointee()
            p.free()


@fieldwise_init
struct _StepOutLike(Copyable, Movable):
    var token_id: Int
    var dispatches: Int
    var status: Int
