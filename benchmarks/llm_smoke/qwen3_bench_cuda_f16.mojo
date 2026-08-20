"""qwen3_bench_cuda.mojo — the CUDA-native session benchmarked under the race ledger's FROZEN
tolerance discipline (benchmarks/competitors/llama_cpp/README.md, frozen 2026-08-07): ONE
resident session, one untimed warmup generation, then N_RUNS = 20 timed generations of the SAME
race prompt + generation length (replayed on the same session — every KV slot a replay reads is
rewritten by the replay before it is read, so runs are self-consistent). Per phase the driver
reports the median, the relative IQR = (p75 − p25) / median, and the PASS/FLAG verdict against
the frozen 5% tolerance; runs deviating >10% from the median are flagged as outliers, reported,
and excluded only if >= 16/20 remain (the frozen rule). nvidia-smi clock evidence is captured
alongside by the calling script.

Timed phases, stated precisely:
  * PREFILL tok/s = n_prompt / (time for the chunked batched prefill, which INCLUDES the
    lm_head + argmax that produces the first generated token).
  * DECODE tok/s  = gen / (time for `gen` decode steps AFTER prefill; each step is one
    per-dispatch-enqueue token, exactly the decode path `qwen3_generate_cuda.mojo` runs).

Generation length is a build-time selection — the pinned compiler's defines carry presence, not
values: default is 64; build with -D ALGENTA_GEN_256 for 256. Weights are read from the same
`/tmp/qwen3smoke/{manifest.json,weights.blob}` dump as every other arm.
"""

from std.math import sqrt
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
)
from residentk.session import _resident_preflight, _StepOut
from residentk.session_cuda import CUDA_PREFILL_TILE, CUDA_SESSION_BUILD
from residentk.session_cuda_f16 import _CudaResidentQwen3F16

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime GEN_256: Bool = is_defined["ALGENTA_GEN_256"]()
comptime N_NEW_MAX: Int = 256 if GEN_256 else 64
comptime MAX_CTX: Int = 1024

comptime USE_GRAPH: Bool = is_defined["ALGENTA_CUDA_GRAPH"]()
"""Build with `-D ALGENTA_CUDA_GRAPH` to decode through the session's captured DeviceGraph
(`step_graph`) instead of the per-dispatch path (`step`) — the lever-3a arm the race ledger's
dispatch-bound diagnosis names as the decode ceiling."""
comptime N_RUNS: Int = 20
"""The frozen 20-runs/cell discipline (benchmarks/competitors/llama_cpp/README.md)."""

comptime IQR_TOLERANCE: Float64 = 0.05
"""The frozen relative-IQR tolerance: (p75 − p25) / median <= 5%."""

comptime OUTLIER_DEVIATION: Float64 = 0.10
"""The frozen outlier rule: a run deviating >10% from the median is flagged and reported, and
excluded only if >= 16 of the 20 runs remain after exclusion."""


def _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_bench_cuda_f16: " + ctx + " failed, status=" + String(status))


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_bench_cuda_f16: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_bench_cuda_f16: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_bench_cuda_f16: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _sort_ascending(mut xs: List[Float64]):
    """In-place insertion sort — N_RUNS is 20, so the quadratic cost is noise."""
    for i in range(1, len(xs)):
        var v = xs[i]
        var j = i - 1
        while j >= 0 and xs[j] > v:
            xs[j + 1] = xs[j]
            j -= 1
        xs[j + 1] = v


def _percentile(sorted_xs: List[Float64], q: Float64) -> Float64:
    """Linear-interpolation percentile (numpy's default method) over ASCENDING-sorted samples:
    position = (n − 1) * q, fractional part interpolates between the two neighbours."""
    var n = len(sorted_xs)
    if n == 1:
        return sorted_xs[0]
    var pos = Float64(n - 1) * q
    var lo = Int(pos)
    var frac = pos - Float64(lo)
    if lo >= n - 1:
        return sorted_xs[n - 1]
    return sorted_xs[lo] + frac * (sorted_xs[lo + 1] - sorted_xs[lo])


@fieldwise_init
struct CellStats(Copyable, Movable):
    """The frozen-table verdict for one cell: median, relative IQR, outlier census, and the
    PASS/FLAG judgement — computed exactly the way the 2026-08-08 harness entry describes."""

    var median: Float64
    var p25: Float64
    var p75: Float64
    var rel_iqr: Float64
    var n_outliers: Int
    var passes: Bool


def _cell_stats(samples: List[Float64]) raises -> CellStats:
    # Mojo 1.0.0 has no List.clone(); build the working copy element-wise so the caller's
    # list is not disturbed by the in-place sort.
    var sorted_runs = List[Float64]()
    for i in range(len(samples)):
        sorted_runs.append(samples[i])
    _sort_ascending(sorted_runs)
    var n = len(sorted_runs)
    var median = _percentile(sorted_runs, 0.5)
    var p25 = _percentile(sorted_runs, 0.25)
    var p75 = _percentile(sorted_runs, 0.75)
    var rel_iqr = (p75 - p25) / median

    # The frozen outlier census: runs deviating >10% from the median, flagged and reported.
    var n_outliers = 0
    for i in range(n):
        # Mojo 1.0.0: no Float64.abs() method — fold the sign by hand.
        var delta = sorted_runs[i] - median
        if delta < 0.0:
            delta = -delta
        var dev = delta / median
        if dev > OUTLIER_DEVIATION:
            n_outliers += 1

    var passes = rel_iqr <= IQR_TOLERANCE
    return CellStats(median, p25, p75, rel_iqr, n_outliers, passes)


@fieldwise_init
struct RunTimes(Copyable, Movable):
    var prefill_ms: Float64
    var decode_ms: Float64
    var first_token: Int


def run_generation(
    mut s: _CudaResidentQwen3F16, prompt_ids: List[Int], n_prompt: Int, n_layers: Int, timed: Bool
) raises -> RunTimes:
    """One full generation: batched prefill then N_NEW_MAX decode steps. `timed=False` is the
    warmup — same code path, numbers discarded.

    The graph arm decodes as ONE async chain (N_NEW_MAX back-to-back replays of the captured
    graph, device-side token chain, one synchronize) — zero per-token host traffic; the timed
    decode window is that single call. The per-dispatch arm decodes one enqueue-heavy step at
    a time, exactly as before."""
    var tp0 = perf_counter_ns()
    var pf = s.prefill(prompt_ids)
    var tp1 = perf_counter_ns()
    _check_resident(pf.status, "prefill")

    var first_tok = pf.token_id
    var td0 = perf_counter_ns()
    @parameter
    if USE_GRAPH:
        var st = s.seed_and_run_graph(pf.token_id, n_prompt, N_NEW_MAX)
        _check_resident(st, "seed_and_run_graph")
    else:
        # The f16 arm is GRAPH-ONLY by design — the racing arm IS the captured graph.
        raise Error(
            "qwen3_bench_cuda_f16: build with -D ALGENTA_CUDA_GRAPH (the f16 arm has no "
            "per-dispatch path)"
        )
    var td1 = perf_counter_ns()

    return RunTimes(_ms(tp1 - tp0), _ms(td1 - td0), first_tok)


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
        raise Error("qwen3_bench_cuda_f16: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen3_bench_cuda_f16: gen =", N_NEW_MAX, "| runs =", N_RUNS,
          "| prefill_tile =", CUDA_PREFILL_TILE, "| n_prompt =", n_prompt)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, N_NEW_MAX, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_bench_cuda_f16: cannot run here:", residentk_status_name(pre))
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        print("qwen3_bench_cuda_f16: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_bench_cuda_f16: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_bench_cuda_f16: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")

        # ═══ ONE-TIME weight cost (NOT part of any timed phase) ═══
        var tw0 = perf_counter_ns()
        var s = _CudaResidentQwen3F16(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  device:", s.device_name())
        var rt = rope_table(d_head, MAX_CTX, theta)
        _check(rt.status, ATTN_OK, "rope_table")
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check_resident(
            s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
            "upload_globals",
        )
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
            _check_resident(
                s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
        _check_resident(s.seal(), "seal")
        var tw1 = perf_counter_ns()
        print("  ONE-TIME weight load + upload (untimed):", _ms(tw1 - tw0), "ms")

        # ═══ warmup: same code path, numbers discarded ═══
        var warm = run_generation(s, prompt_ids, n_prompt, n_layers, False)
        print("  warmup: prefill", warm.prefill_ms, "ms, decode", warm.decode_ms,
              "ms, first_token =", warm.first_token)

        # ═══ the frozen 20 timed runs ═══
        var pf_ms = List[Float64]()
        var dc_ms = List[Float64]()
        var first_tok = warm.first_token
        for run in range(N_RUNS):
            var r = run_generation(s, prompt_ids, n_prompt, n_layers, True)
            print("  run", run + 1, ": prefill", r.prefill_ms, "ms decode", r.decode_ms, "ms")
            if r.first_token != first_tok:
                raise Error("qwen3_bench_cuda_f16: runs disagree on the first generated token")
            pf_ms.append(r.prefill_ms)
            dc_ms.append(r.decode_ms)
        print("  all", N_RUNS, "runs agree on first generated token:", first_tok)

        var pf_stats = _cell_stats(pf_ms)
        var dc_stats = _cell_stats(dc_ms)
        var pf_verdict = "PASS" if pf_stats.passes else "FLAGGED"
        var dc_verdict = "PASS" if dc_stats.passes else "FLAGGED"

        print("  prefill: median", pf_stats.median, "ms | p25", pf_stats.p25, "| p75",
              pf_stats.p75, "| rel IQR", pf_stats.rel_iqr * 100.0, "% | outliers (>10% dev):",
              pf_stats.n_outliers, "|", pf_verdict, "(frozen tolerance 5%)")
        print("  decode: median", dc_stats.median, "ms | p25", dc_stats.p25, "| p75",
              dc_stats.p75, "| rel IQR", dc_stats.rel_iqr * 100.0, "% | outliers (>10% dev):",
              dc_stats.n_outliers, "|", dc_verdict, "(frozen tolerance 5%)")

        print("RESULT prefill_tok_per_s:", Float64(n_prompt) / (pf_stats.median / 1000.0),
              "(median prefill", pf_stats.median, "ms over", n_prompt,
              "prompt tokens; rel IQR", pf_stats.rel_iqr * 100.0, "%", pf_verdict + ")")
        print("RESULT decode_tok_per_s:", Float64(N_NEW_MAX) / (dc_stats.median / 1000.0),
              "(median decode", dc_stats.median, "ms over", N_NEW_MAX,
              "generated tokens; rel IQR", dc_stats.rel_iqr * 100.0, "%", dc_verdict + ")")
