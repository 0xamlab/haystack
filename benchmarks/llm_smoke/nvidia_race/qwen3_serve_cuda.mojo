"""qwen3_serve_cuda.mojo — the CUDA-native resident session as a long-lived SERVING driver:
the JSON-lines subprocess protocol of `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py`
(its `JsonlDriverAdapter`), spoken over ONE resident `_CudaResidentQwen3` session opened once
at startup and held open for the whole run. The harness spawns this process once, writes one
JSON request per stdin line, demuxes one JSON response per stdout line by `id`, and closes
stdin when the run ends; the driver exits cleanly on that EOF.

Protocol — matched field-for-field against enterprise_bench.py's JsonlDriverAdapter
------------------------------------------------------------------------------------
Request (one JSON object per stdin line, exactly the adapter's `send` payload):

    {"id": int, "prompt": str, "prompt_tokens_approx": int,
     "max_tokens": int, "stream": true}

  * `prompt` is TEXT, not token ids — the stdlib harness carries no tokenizer, so this driver
    applies its own deterministic text->ids mapping (the tokenizer contract, below).
  * `prompt_tokens_approx` (the harness's char/4 estimate) is the prompt's TOKEN LENGTH under
    this driver's tokenizer contract — it is always present in the adapter's payload and is
    authoritative for the prefill length.
  * `stream` is accepted and ignored: the protocol has no incremental deltas; the full response
    lands as one line and the harness derives ITL samples from the reported `tpot_ms` itself.

Response (one JSON object per stdout line, any order — the harness demuxes by `id`):

    {"id": int, "ttft_ms": float, "tpot_ms": float,
     "output_tokens": int, "tokens": [str, ...]}

  * `tokens` carries the generated ids as decimal strings; the harness joins `str(t)` of each
    element, so decimal-id strings are the wire unit (neither side has a detokenizer).
  * `output_tokens` = len(tokens). An EOS (151643) stops generation early and IS included.
  * on failure: {"id": int, "error": str}. Non-JSON diagnostic lines may also appear on
    stdout; the harness skips any line that fails json.loads.

Tokenizer contract (why `prompt` text becomes these ids)
--------------------------------------------------------
Neither the harness nor this zero-Python driver has a Qwen3 tokenizer, and the protocol ships
text. The mapping is fixed, documented, and deterministic: n_tok = prompt_tokens_approx, and
token i = the UTF-8 byte at decoded byte index 4*i of the prompt text (one token per 4-byte
window, the window's first byte as the id; ids land in [0, 255], valid for any Qwen3 vocab).
Identical prompt text therefore yields identical id sequences in every process and every run.
The prompt's JSON string literal is decoded in ONE O(n) pass (escapes included; \\uXXXX to its
UTF-8 bytes, surrogate pairs combined) — the prompt is never materialised as a Mojo String, so
parse cost stays noise next to prefill even at the summar mix's ~33 KB lines.

Metrics, stated precisely
-------------------------
  * TTFT  = wall time from the request line's stdin read completion to the first generated
    token becoming available — the batched prefill, which INCLUDES the lm_head + argmax that
    produces that first token (the same phase definition qwen3_bench_cuda.mojo times). Requests
    are processed ONE AT A TIME in arrival order (batch-1 resident session), so for a queued
    request TTFT includes its queue wait — the serving-system semantics the harness intends.
  * TPOT  = (last decode step completion - first token availability) / (output_tokens - 1),
    the mean per-token decode time after the first token; 0.0 when output_tokens == 1.
  * Decode is the per-dispatch `step` path, greedy argmax, checked against
    `residentk_dispatch_budget(n_layers)` every step. The CUDA-graph arm is deliberately NOT
    wired here: `seed_and_run_graph` runs a fixed-length async chain that cannot stop on EOS
    and cannot report the per-token timing the harness consumes as ITL.

Determinism
-----------
Greedy argmax, fixed kernel launch shapes, no RNG and no clock-dependent control flow: an
identical request yields byte-identical tokens across runs of this driver on the same build
and the same GPU — the determinism arm's invariant. (The campaign's warmup requests from the
harness also absorb the one-time first-launch kernel-compile cost, exactly like the bench
driver's own untimed warmup; this driver additionally runs one untimed mini-generation after
seal so every kernel path is compiled before READY.)

Build (the CUDA lane recipe, no CUDA toolkit at build time — setup_vm.sh stage 7 runs this;
the fallback link line is the one in residentk_cuda_smoke.mojo's module docstring):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_serve_cuda.mojo \\
        -o qwen3_serve_cuda

    # if the pinned toolchain does not auto-link the MAX CUDA runtime:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_serve_cuda.mojo \\
        --emit object -o qwen3_serve_cuda.o
    clang qwen3_serve_cuda.o -o qwen3_serve_cuda -L <max-lib> -Wl,-rpath,<max-lib> \\
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \\
        -lAsyncRTMojoBindings -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm

--target-accelerator follows the VM's GPU: sm_80 A100 / sm_89 L4 / sm_75 T4. The session
context ceiling is a build-time selection (the pinned compiler's defines carry presence, not
values): default 10240 positions — every enterprise_bench mix fits (summar = 8192 prompt +
1024 generated); -D ALGENTA_CTX_20K raises it to 20480, -D ALGENTA_CTX_32K to 32768.

Usage
-----
With the enterprise harness (the driver command is shlex-split, so the checkpoint dir rides
as the driver's own argv):

    python3 benchmarks/llm_smoke/nvidia_race/enterprise_bench.py \\
        --jsonl-driver "$HOME/algenta_nv/qwen3_serve_cuda /tmp/qwen3smoke" \\
        --mix chat --concurrency 1,8,16,32 --requests 32 --out ~/bench_out

Standalone smoke (one request over the same protocol):

    echo '{"id": 0, "prompt": "The capital of France is", "prompt_tokens_approx": 6, \\
           "max_tokens": 16, "stream": true}' | ./qwen3_serve_cuda /tmp/qwen3smoke

Checkpoint: argv[1] is the directory holding `{manifest.json,weights.blob}` — the same dump
prepare_smoke_checkpoint.py writes — or `--checkpoint <dir>`; default /tmp/qwen3smoke.
"""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from json.parser import find_key, json_get_float, json_get_int, json_get_object
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
)
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_PREFILL_TILE, CUDA_SESSION_BUILD, _CudaResidentQwen3

comptime DEFAULT_CHECKPOINT_DIR: String = "/tmp/qwen3smoke"
"""The same shared checkpoint dump every other CUDA arm reads; argv[1] (or --checkpoint)
overrides it so the harness can point one binary at any prepared dump."""

comptime EOS_TOKEN_ID: Int = 151643
"""Qwen3's end-of-sequence id — the same comptime qwen3_generate_cuda.mojo gates on. A
generated EOS stops the request early and is included in the response's tokens."""

comptime CTX_20K: Bool = is_defined["ALGENTA_CTX_20K"]()
comptime CTX_32K: Bool = is_defined["ALGENTA_CTX_32K"]()
comptime MAX_CTX_MID: Int = 20480 if CTX_20K else 10240
comptime MAX_CTX: Int = 32768 if CTX_32K else MAX_CTX_MID
"""The session's fixed context ceiling, chosen at build time. 10240 covers every
enterprise_bench mix (largest: summar 8192 prompt + 1024 generated); the KV cache scales
linearly with it (~224 KB/position at Qwen3-0.6B's shape), so a driver meant for longer
--prompts workloads builds the larger ceiling in."""

# ── ASCII byte constants for the request-line parser (json.parser's own spelling) ──
comptime _QUOTE: UInt8 = 34        # "
comptime _BACKSLASH: UInt8 = 92    # backslash


def _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_serve_cuda: " + ctx + " failed, status=" + String(status))


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_serve_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_serve_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_serve_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    """Read one tensor out of the flat Float64 blob — the same loader shape the bench driver
    uses (a driver helper with hardcoded paths, deliberately copied, not shared)."""
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    # Mojo 1.0.0: perf_counter_ns() returns Int.
    return Float64(ns) / 1.0e6


def _fmt_ms(v: Float64) -> String:
    """Three decimal places (microseconds), as a JSON-safe number string — the same
    round-then-stringify shape engines/column_ranker.mojo's _fmt_float uses."""
    var rounded = Float64(Int(v * 1000.0 + 0.5)) / 1000.0
    return String(rounded)


# ── the request-line parser: prompt text -> decoded UTF-8 bytes, one O(n) pass ──


def _hex_digit(c: UInt8) -> Int:
    if c >= UInt8(48) and c <= UInt8(57):      # 0-9
        return Int(c) - 48
    if c >= UInt8(97) and c <= UInt8(102):     # a-f
        return Int(c) - 87
    if c >= UInt8(65) and c <= UInt8(70):      # A-F
        return Int(c) - 55
    return 0


def _hex4(raw: String, p: Int) -> Int:
    var bytes = raw.as_bytes()
    return (_hex_digit(bytes[p]) << 12) | (_hex_digit(bytes[p + 1]) << 8) \
        | (_hex_digit(bytes[p + 2]) << 4) | _hex_digit(bytes[p + 3])


def _append_utf8(mut bs: List[UInt8], cp: Int):
    """One codepoint as its UTF-8 bytes — the \\uXXXX decode target feeds the byte-window
    tokenizer, so the encoding must be the standard one."""
    if cp < 0x80:
        bs.append(UInt8(cp))
    elif cp < 0x800:
        bs.append(UInt8(0xC0 | (cp >> 6)))
        bs.append(UInt8(0x80 | (cp & 0x3F)))
    elif cp < 0x10000:
        bs.append(UInt8(0xE0 | (cp >> 12)))
        bs.append(UInt8(0x80 | ((cp >> 6) & 0x3F)))
        bs.append(UInt8(0x80 | (cp & 0x3F)))
    else:
        bs.append(UInt8(0xF0 | (cp >> 18)))
        bs.append(UInt8(0x80 | ((cp >> 12) & 0x3F)))
        bs.append(UInt8(0x80 | ((cp >> 6) & 0x3F)))
        bs.append(UInt8(0x80 | (cp & 0x3F)))


def _decode_prompt_bytes(raw: String, pos: Int) raises -> List[UInt8]:
    """The decoded UTF-8 bytes of the JSON string literal starting at `pos` (its opening
    quote) — escapes handled: \\" \\\\ \\/ \\n \\r \\t \\b \\f, and \\uXXXX to its UTF-8
    bytes with surrogate pairs combined. Any other escape keeps its second byte literally —
    deterministic for any input. The walk stops at the closing quote; a malformed literal
    yields what decoded so far (the tokenizer then answers for length)."""
    var bytes = raw.as_bytes()
    var n = raw.byte_length()
    var bs = List[UInt8]()
    if pos >= n or bytes[pos] != _QUOTE:
        raise Error("qwen3_serve_cuda: 'prompt' is not a JSON string")
    var p = pos + 1
    while p < n:
        var c = bytes[p]
        if c == _QUOTE:
            return bs^
        if c != _BACKSLASH:
            bs.append(c)
            p += 1
            continue
        if p + 1 >= n:
            return bs^
        var e = bytes[p + 1]
        if e == UInt8(117):  # \uXXXX
            if p + 5 >= n:
                return bs^
            var cp = _hex4(raw, p + 2)
            p += 6
            # A high surrogate followed by \uDCxx.. is one codepoint, not two.
            if cp >= 0xD800 and cp <= 0xDBFF and p + 5 < n \
               and bytes[p] == _BACKSLASH and bytes[p + 1] == UInt8(117):
                var lo = _hex4(raw, p + 2)
                if lo >= 0xDC00 and lo <= 0xDFFF:
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00)
                    p += 6
            _append_utf8(bs, cp)
        else:
            if e == _QUOTE:
                bs.append(_QUOTE)
            elif e == _BACKSLASH:
                bs.append(_BACKSLASH)
            elif e == UInt8(47):
                bs.append(UInt8(47))
            elif e == UInt8(110):
                bs.append(UInt8(10))
            elif e == UInt8(114):
                bs.append(UInt8(13))
            elif e == UInt8(116):
                bs.append(UInt8(9))
            elif e == UInt8(98):
                bs.append(UInt8(8))
            elif e == UInt8(102):
                bs.append(UInt8(12))
            else:
                bs.append(e)
            p += 2
    return bs^


def _tokenize_request(raw: String, n_tok: Int) raises -> List[Int]:
    """The tokenizer contract: locate the request's "prompt" string (json.parser's find_key,
    which skips nested values and escaped quotes correctly), decode it, and take the first
    byte of every 4-byte window — token i = decoded byte 4*i, ids in [0, 255]. The adapter's
    prompt_tokens_approx = ceil(chars/4) guarantees all n_tok windows exist for the harness's
    own payloads; a shorter prompt yields fewer ids and the caller answers for the length."""
    var pos = find_key(raw, "prompt")
    if pos < 0:
        raise Error("qwen3_serve_cuda: request missing 'prompt'")
    var bs = _decode_prompt_bytes(raw, pos)
    var nb = len(bs)
    if nb == 0:
        raise Error("qwen3_serve_cuda: empty prompt")
    var ids = List[Int](capacity=n_tok)
    var i = 0
    while i < n_tok and 4 * i < nb:
        ids.append(Int(bs[4 * i]))
        i += 1
    return ids^


# ── response-line builders ──


def _response_line(rid: Int, ttft_ms: Float64, tpot_ms: Float64, tokens: List[Int]) -> String:
    var out = String('{"id":') + String(rid)
    out += ',"ttft_ms":' + _fmt_ms(ttft_ms)
    out += ',"tpot_ms":' + _fmt_ms(tpot_ms)
    out += ',"output_tokens":' + String(len(tokens))
    out += ',"tokens":['
    for i in range(len(tokens)):
        if i > 0:
            out += ","
        out += '"' + String(tokens[i]) + '"'
    out += "]}"
    return out


def _error_line(rid: Int, msg: String) -> String:
    return String('{"id":') + String(rid) + ',"error":"' + msg + '"}'


# ── one request: prefill -> greedy decode -> the response line ──


def _handle_request(
    mut s: _CudaResidentQwen3, n_layers: Int, line: String,
    rid: Int, max_tokens: Int, approx: Int, t0: Int,
) raises:
    if rid < 0:
        raise Error("qwen3_serve_cuda: request missing integer id")
    if max_tokens < 1:
        raise Error("qwen3_serve_cuda: request missing max_tokens")
    if max_tokens > MAX_CTX:
        raise Error("qwen3_serve_cuda: max_tokens exceeds the session context")
    if approx < 1:
        raise Error("qwen3_serve_cuda: request missing prompt_tokens_approx")
    if approx + max_tokens > MAX_CTX:
        raise Error("qwen3_serve_cuda: prompt_tokens_approx + max_tokens exceeds the session context")

    var ids = _tokenize_request(line, approx)
    var n_prompt = len(ids)
    if n_prompt < 1:
        raise Error("qwen3_serve_cuda: empty prompt")

    # PREFILL — the batched m_rows GEMM path, chunked, exactly the call the bench driver's
    # run_generation issues; it ends in the lm_head + argmax that yields the FIRST token.
    var pf = s.prefill(ids)
    if pf.status != RESIDENT_OK:
        raise Error(
            "qwen3_serve_cuda: prefill failed, status=" + String(pf.status)
            + " (" + residentk_status_name(pf.status) + ")"
        )
    var t_first = perf_counter_ns()

    # DECODE — the per-dispatch step path, greedy, EOS-terminated, budget-checked per step.
    # Pos bookkeeping is the bench driver's: the prefill's token occupies position n_prompt,
    # and the step that consumes the k-th generated token runs at pos = n_prompt + k.
    var tokens = List[Int](capacity=max_tokens)
    tokens.append(pf.token_id)
    var last = pf.token_id
    if last != EOS_TOKEN_ID:
        while len(tokens) < max_tokens:
            var pos = n_prompt + len(tokens) - 1
            var r = s.step(last, pos)
            if r.status != RESIDENT_OK:
                raise Error(
                    "qwen3_serve_cuda: step failed at pos " + String(pos)
                    + ", status=" + String(r.status)
                    + " (" + residentk_status_name(r.status) + ")"
                )
            if r.dispatches != residentk_dispatch_budget(n_layers):
                raise Error("qwen3_serve_cuda: dispatch budget disagreement")
            tokens.append(r.token_id)
            last = r.token_id
            if r.token_id == EOS_TOKEN_ID:
                break
    var t_last = perf_counter_ns()

    var n_gen = len(tokens)
    var tpot_ms = 0.0
    if n_gen > 1:
        tpot_ms = _ms(t_last - t_first) / Float64(n_gen - 1)
    print(_response_line(rid, _ms(t_first - t0), tpot_ms, tokens))


def _serve_loop(mut s: _CudaResidentQwen3, n_layers: Int) raises:
    """One request per stdin line, one response per stdout line, requests processed ONE AT A
    TIME in arrival order — the resident session is batch-1, and every KV slot a later
    request reads is rewritten by that request's own prefill/decode before it is read (the
    self-consistency property qwen3_bench_cuda.mojo's replay discipline relies on), so no
    session reset is needed between requests. EOF on stdin ends the loop."""
    while True:
        var line: String
        try:
            line = input()
        except:
            return  # stdin closed — the harness is done
        if line.byte_length() == 0:
            continue
        var t0 = perf_counter_ns()
        var rid = json_get_int(line, "id", -1)
        var max_tokens = json_get_int(line, "max_tokens", -1)
        var approx = json_get_int(line, "prompt_tokens_approx", -1)
        try:
            _handle_request(s, n_layers, line, rid, max_tokens, approx, t0)
        except e:
            # One response per request, always: the error line first, then the detail for
            # the operator (the harness skips non-JSON lines).
            print(_error_line(rid, "request failed"))
            print("qwen3_serve_cuda:", e)


def main() raises:
    var args = argv()
    var ckpt_dir = DEFAULT_CHECKPOINT_DIR
    if len(args) > 1:
        var a1 = String(args[1])
        if a1 == "--checkpoint" and len(args) > 2:
            ckpt_dir = String(args[2])
        else:
            ckpt_dir = a1

    var manifest = _read_text_file(ckpt_dir + "/manifest.json")
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

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1:
        raise Error("qwen3_serve_cuda: manifest config did not parse")
    if vocab_size < 256:
        raise Error("qwen3_serve_cuda: vocab_size < 256 — the byte-window tokenizer needs every byte id valid")

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen3_serve_cuda: checkpoint =", ckpt_dir, "| d_model =", d_model,
          "| n_layers =", n_layers, "| h_q =", h_q, "| h_kv =", h_kv,
          "| d_head =", d_head, "| d_ff =", d_ff, "| vocab =", vocab_size,
          "| max_ctx =", MAX_CTX, "| prefill_tile =", CUDA_PREFILL_TILE)

    # The capability answer before anything is allocated. The request shape is per-request,
    # so the preflight runs with the minimal valid (1, 1) shape; every real request is
    # validated against MAX_CTX in _handle_request before its prefill.
    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, 1, 1, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_serve_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        exit(1)

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time
        # gate is visible at this file's only construction site, exactly as the bench driver
        # states it. Everything below is elided from a build without BOTH defines.
        print("qwen3_serve_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_serve_cuda: no accelerator on this host")
            exit(1)

        var blob_path = ckpt_dir + "/weights.blob"
        var tensors_obj = json_get_object(manifest, "tensors")

        # ═══ ONE-TIME: open the session, load every weight resident, seal ═══
        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  device:", s.device_name())
        var rt = rope_table(d_head, MAX_CTX, theta)
        _check(rt.status, ATTN_OK, "rope_table")
        var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
        _check_resident(
            s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
            "upload_globals",
        )
        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
            var ln2 = _load_tensor(blob_path, tensors_obj, prefix + "post_attention_layernorm.weight")
            var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
            var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
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
        _check_resident(s.seal(), "seal")

        # ═══ ONE untimed mini-generation: every kernel path compiled before READY — the
        # bench driver's warmup-generation discipline, applied to serving. The KV slots it
        # touches are rewritten by the first real request before they are read. ═══
        var warm_ids = List[Int]()
        warm_ids.append(1)
        warm_ids.append(1)
        var wpf = s.prefill(warm_ids)
        if wpf.status != RESIDENT_OK:
            print("qwen3_serve_cuda: warmup prefill failed, status=", wpf.status)
            exit(1)
        var wlast = wpf.token_id
        for wstep in range(2):
            var wr = s.step(wlast, 2 + wstep)
            if wr.status != RESIDENT_OK:
                print("qwen3_serve_cuda: warmup step failed, status=", wr.status)
                exit(1)
            wlast = wr.token_id

        print("qwen3_serve_cuda: READY — one JSON request per stdin line, one response per stdout line")
        _serve_loop(s, n_layers)
        print("qwen3_serve_cuda: stdin EOF — exiting")
        exit(0)
