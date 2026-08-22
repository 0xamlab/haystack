"""qwen3_p3_session_cuda.mojo — the packed3 CUDA resident session
(`residentk.session_cuda_p3._CudaResidentQwen3P3`) through the campaign's gate battery: the
decode lane streams arithmetic-packed-int8 weights at ~1.5833 B/weight instead of Float32's
4 B/weight (residentk.kernels_packed3's layout math), and this driver ANSWERS the three
questions the adoption decision needs, in order:

G0 — THE ORACLE (hard gate, exits nonzero on failure): 16/16 greedy tokens on the campaign
     fixture — the manifest's 256-token race prompt, the exact protocol
     `qwen3_generate_cuda.mojo` enforces (prefill then per-dispatch decode, every step checked
     against `residentk_dispatch_budget`, every generated token checked against the campaign's
     known-correct continuation: the 8-token window then the 7-token repeat cycle).

G1 — TOKEN-IDENTICALITY vs the f32 `_CudaResidentQwen3` (REPORTING gate): 5 prompts x 64
     generated tokens through BOTH sessions; per-prompt match count, and on mismatch the first
     divergent index plus both ids, then the total flip count. Quantization MAY flip a
     near-tie argmax — the gate REPORTS the flips, it does not hard-fail; adoption requires
     16/16 on the fixture per campaign discipline (G0). The 5 prompts are deterministic
     64-token slices of the race fixture's own ids (offsets 0/16/32/64/128) — this zero-Python
     driver carries no tokenizer, and the fixture's ids are the only prompt the campaign
     standardizes on.

G2 — DECODE tok/s (REPORTING gate): gen64 and gen256, ONE untimed warmup then N_RUNS = 20
     timed generations per session (the frozen qwen3_bench_cuda.mojo discipline: median +
     relative IQR = (p75-p25)/median), the packed3 session's numbers printed ALONGSIDE the f32
     session's from the same run so the ratio reads straight off the table. Both sessions stay
     resident in this one process — ~4.3 GB of weights combined at 0.6B (2.38 GB f32 session +
     2.38 GB twin session's f32 half + its 0.94 GB packed3 decode twins) — which is why the
     comparison is same-process, same-GPU-state, same-run.

The prefill split is stated, not hidden: BOTH sessions prefill through the f32 v2 GEMMs
(the P3 session delegates its prefill to its inner f32 session — decode = packed3,
prefill = f32, the session module's docstring documents why). First-generated-token agreement
between the two sessions is therefore a sanity check this driver asserts: identical f32 prefill
code on identical f32 weights must produce identical first tokens.

Build (the CUDA lane recipe, no CUDA toolkit at build time — setup_vm.sh stage 7's form,
mirrored from qwen3_serve_cuda.mojo's docstring; plain build first, the object+link recipe as
fallback when the pinned toolchain does not auto-link the MAX CUDA runtime):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo \\
        -o qwen3_p3_session_cuda

    # if the pinned toolchain does not auto-link the MAX CUDA runtime:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo \\
        --emit object -o qwen3_p3_session_cuda.o
    clang qwen3_p3_session_cuda.o -o qwen3_p3_session_cuda -L <max-lib> -Wl,-rpath,<max-lib> \\
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \\
        -lAsyncRTMojoBindings -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm

(same with `sm_89` for the L4 lane). `--target-accelerator` follows the VM's GPU.

Run on the VM (checkpoint prepared by setup_vm.sh stage 8 / prepare_smoke_checkpoint.py):

    ./qwen3_p3_session_cuda /tmp/qwen3smoke

Checkpoint: argv[1] is the directory holding `{manifest.json,weights.blob}`, or
`--checkpoint <dir>`; default /tmp/qwen3smoke.
"""

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
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
)
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3
from residentk.session_cuda_p3 import _CudaResidentQwen3P3
from residentk.kernels_packed3 import _p3_words_per_row, _p3_blocks_per_row

comptime DEFAULT_CHECKPOINT_DIR: String = "/tmp/qwen3smoke"

comptime MAX_CTX: Int = 1024
"""Room for the 256-token race prompt plus the gen256 benchmark tail, both sessions."""

comptime G0_TOKENS: Int = 16
"""The oracle gate's generation length: 16/16 greedy tokens must sit on the campaign's
known-correct continuation (same protocol qwen3_generate_cuda.mojo enforces)."""

comptime G1_PROMPTS: Int = 5
comptime G1_PROMPT_LEN: Int = 64
comptime G1_TOKENS: Int = 64
"""G1: five 64-token slices of the race fixture (offsets 0/16/32/64/128), 64 generated tokens
each, token-for-token against the f32 session."""

comptime N_RUNS: Int = 20
"""The frozen 20-runs/cell discipline (benchmarks/competitors/llama_cpp/README.md), the same
one qwen3_bench_cuda.mojo runs."""

comptime IQR_TOLERANCE: Float64 = 0.05
"""The frozen relative-IQR tolerance: (p75 - p25) / median <= 5%."""

comptime OUTLIER_DEVIATION: Float64 = 0.10
"""The frozen outlier rule: a run deviating >10% from the median is flagged and reported."""

comptime ORACLE_WINDOW: Int = 8
"""The campaign's known-correct greedy window for the 256-token race prompt on Qwen3-0.6B-Base —
copied VERBATIM from qwen3_generate_cuda.mojo's own gate (a driver helper with hardcoded
values, deliberately copied, not shared)."""


def _oracle_token(i: Int) -> Int:
    """`i`-th expected generated token: the 8-token window, then the 7-token repeat cycle the
    model settles into on this prompt — qwen3_generate_cuda.mojo's oracle, character for
    character."""
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
        raise Error("qwen3_p3_session_cuda: " + ctx + " failed, status=" + String(status))


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_p3_session_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_p3_session_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_p3_session_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    """Read one tensor out of the flat Float64 blob — the same loader shape every other CUDA
    arm's driver uses (a driver helper with hardcoded paths, deliberately copied, not shared)."""
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    # Mojo 1.0.0: perf_counter_ns() returns Int.
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
    """Linear-interpolation percentile (numpy's default method) over ASCENDING-sorted samples —
    qwen3_bench_cuda.mojo's helper, copied verbatim."""
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
    var median: Float64
    var p25: Float64
    var p75: Float64
    var rel_iqr: Float64
    var n_outliers: Int
    var passes: Bool


def _cell_stats(samples: List[Float64]) raises -> CellStats:
    """qwen3_bench_cuda.mojo's frozen-table verdict, copied: median, relative IQR, outlier
    census (>10% deviation from the median), PASS/FLAG against the frozen 5% tolerance."""
    # Mojo 1.0.0 has no List.clone(); build the working copy element-wise.
    var sorted_runs = List[Float64]()
    for i in range(len(samples)):
        sorted_runs.append(samples[i])
    _sort_ascending(sorted_runs)
    var n = len(sorted_runs)
    var median = _percentile(sorted_runs, 0.5)
    var p25 = _percentile(sorted_runs, 0.25)
    var p75 = _percentile(sorted_runs, 0.75)
    var rel_iqr = (p75 - p25) / median
    var n_outliers = 0
    for i in range(n):
        var delta = sorted_runs[i] - median
        if delta < 0.0:
            delta = -delta
        if delta / median > OUTLIER_DEVIATION:
            n_outliers += 1
    return CellStats(median, p25, p75, rel_iqr, n_outliers, rel_iqr <= IQR_TOLERANCE)


@fieldwise_init
struct RunResult(Movable):
    """One full generation's outcome: the decode-window wall time, the first generated token
    (the prefill's lm_head output), and the generated token ids (G1 compares them; G2 ignores
    them)."""

    var decode_ms: Float64
    var first_token: Int
    var tokens: List[Int]


def _run_f32(
    mut s: _CudaResidentQwen3, prompt_ids: List[Int], n_prompt: Int, n_gen: Int,
    n_layers: Int, collect_tokens: Bool,
) raises -> RunResult:
    """One generation through the f32 session: prefill then `n_gen` per-dispatch decode steps
    (the first generated token comes FROM the prefill; the timed window is the `n_gen` steps
    after it — qwen3_bench_cuda.mojo's phase definition). No EOS early-stop: every campaign
    oracle continuation is a fixed-length window, and G1 needs position-aligned lengths."""
    var pf = s.prefill(prompt_ids)
    _check_resident(pf.status, "f32 prefill")
    var tokens = List[Int](capacity=n_gen + 1)
    if collect_tokens:
        tokens.append(pf.token_id)
    var last = pf.token_id
    var td0 = perf_counter_ns()
    for step in range(n_gen):
        var pos = n_prompt + step
        var r = s.step(last, pos)
        _check_resident(r.status, "f32 step(decode pos " + String(pos) + ")")
        if r.dispatches != residentk_dispatch_budget(n_layers):
            raise Error("qwen3_p3_session_cuda: f32 dispatch budget disagreement")
        last = r.token_id
        if collect_tokens:
            tokens.append(r.token_id)
    var td1 = perf_counter_ns()
    return RunResult(_ms(td1 - td0), pf.token_id, tokens^)


def _run_p3(
    mut s: _CudaResidentQwen3P3, prompt_ids: List[Int], n_prompt: Int, n_gen: Int,
    n_layers: Int, collect_tokens: Bool,
) raises -> RunResult:
    """One generation through the packed3 session — the SAME shape as `_run_f32`, with
    `step_p3` as the decode step. Prefill is delegated to the inner f32 session (the
    decode = packed3 / prefill = f32 split), so `first_token` is directly comparable."""
    var pf = s.prefill(prompt_ids)
    _check_resident(pf.status, "p3 prefill")
    var tokens = List[Int](capacity=n_gen + 1)
    if collect_tokens:
        tokens.append(pf.token_id)
    var last = pf.token_id
    var td0 = perf_counter_ns()
    for step in range(n_gen):
        var pos = n_prompt + step
        var r = s.step_p3(last, pos)
        _check_resident(r.status, "p3 step_p3(decode pos " + String(pos) + ")")
        if r.dispatches != residentk_dispatch_budget(n_layers):
            raise Error("qwen3_p3_session_cuda: p3 dispatch budget disagreement")
        last = r.token_id
        if collect_tokens:
            tokens.append(r.token_id)
    var td1 = perf_counter_ns()
    return RunResult(_ms(td1 - td0), pf.token_id, tokens^)


def _prompt_slice(ids: List[Int], off: Int, n: Int) raises -> List[Int]:
    var out = List[Int](capacity=n)
    for i in range(n):
        out.append(ids[off + i])
    return out^


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
    var n_prompt = json_get_int(config, "n_tokens", -1)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1 or n_prompt < 1:
        raise Error("qwen3_p3_session_cuda: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen3_p3_session_cuda: checkpoint =", ckpt_dir, "| d_model =", d_model,
          "| n_layers =", n_layers, "| h_q =", h_q, "| h_kv =", h_kv,
          "| d_head =", d_head, "| d_ff =", d_ff, "| vocab =", vocab_size,
          "| n_prompt =", n_prompt, "| max_ctx =", MAX_CTX)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 256, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_p3_session_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        exit(1)

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time
        # gate is visible at this file's only construction site.
        print("qwen3_p3_session_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_p3_session_cuda: no accelerator on this host")
            exit(1)

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var race_ids = List[Int]()
        for i in range(len(id_tokens)):
            race_ids.append(parse_int(id_tokens[i]))
        if len(race_ids) != n_prompt:
            raise Error("qwen3_p3_session_cuda: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var blob_path = ckpt_dir + "/weights.blob"

        # ═══ ONE-TIME: open BOTH sessions, load every weight into each, seal ═══
        var rt = rope_table(d_head, MAX_CTX, theta)
        _check(rt.status, ATTN_OK, "rope_table")

        var t0 = perf_counter_ns()
        var sp3 = _CudaResidentQwen3P3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  p3 device:", sp3.device_name())
        var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
        _check_resident(
            sp3.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
            "p3 upload_globals",
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
                sp3.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "p3 upload_layer " + String(layer),
            )
        _check_resident(sp3.seal(), "p3 seal")
        var t1 = perf_counter_ns()
        print("  p3 session one-time load (f32 half + host pack + packed upload):",
              _ms(t1 - t0), "ms")

        var t2 = perf_counter_ns()
        var sf32 = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        _check_resident(
            sf32.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
            "f32 upload_globals",
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
                sf32.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "f32 upload_layer " + String(layer),
            )
        _check_resident(sf32.seal(), "f32 seal")
        var t3 = perf_counter_ns()
        print("  f32 session one-time load:", _ms(t3 - t2), "ms")

        # ── the ledger math, confirmed from this model's own dimensions ──
        var n_q = h_q * d_head
        var n_kv = h_kv * d_head
        var n_qkv = n_q + 2 * n_kv
        var lm_elems = vocab_size * d_model
        var layer_elems = n_qkv * d_model + n_q * d_model + 2 * d_ff * d_model + d_ff * d_model
        var f32_weight_bytes = Float64(n_layers * layer_elems + lm_elems) * 4.0
        var p3_layer_bytes = Float64(
            n_qkv * _p3_words_per_row(d_model)
            + d_model * _p3_words_per_row(n_q)
            + 2 * d_ff * _p3_words_per_row(d_model)
            + d_model * _p3_words_per_row(d_ff)
        ) * 4.0 + Float64(
            n_qkv * _p3_blocks_per_row(d_model)
            + d_model * _p3_blocks_per_row(n_q)
            + 2 * d_ff * _p3_blocks_per_row(d_model)
            + d_model * _p3_blocks_per_row(d_ff)
        ) * 8.0
        var p3_lm_bytes = Float64(vocab_size * _p3_words_per_row(d_model)) * 4.0 \
            + Float64(vocab_size * _p3_blocks_per_row(d_model)) * 8.0
        var p3_weight_bytes = Float64(n_layers) * p3_layer_bytes + p3_lm_bytes
        print("  LEDGER: projection+lm_head weights f32", f32_weight_bytes / 1.0e9,
              "GB -> packed3", p3_weight_bytes / 1.0e9, "GB |",
              p3_weight_bytes / Float64(n_layers * layer_elems + lm_elems),
              "B/weight (layout: 4/3 + 8/32 = 1.5833)")

        # ═══ G0 — 16/16 greedy-token oracle on the campaign fixture ═══
        print("G0 — packed3 session, 16 greedy tokens on the race fixture")
        var g0 = _run_p3(sp3, race_ids, n_prompt, G0_TOKENS - 1, n_layers, True)
        # _run_p3 counts decode STEPS after the prefill's first token: G0_TOKENS - 1 steps
        # give G0_TOKENS generated tokens total.
        var g0_mismatch = 0
        for i in range(G0_TOKENS):
            var want = _oracle_token(i)
            var got = g0.tokens[i]
            if got != want:
                g0_mismatch += 1
                print("  ORACLE MISMATCH at generated token", i, ": got", got, "want", want)
        if g0_mismatch == 0:
            print("G0 RESULT: PASS —", G0_TOKENS,
                  "greedy tokens match the campaign oracle (decode", g0.decode_ms, "ms)")
        else:
            print("G0 RESULT: FAIL —", g0_mismatch, "mismatched tokens")

        # ═══ G1 — token-identical comparison vs the f32 session ═══
        print("G1 — f32 vs packed3,", G1_PROMPTS, "prompts x", G1_TOKENS, "tokens")
        var g1_offsets = List[Int]()
        g1_offsets.append(0)
        g1_offsets.append(16)
        g1_offsets.append(32)
        g1_offsets.append(64)
        g1_offsets.append(128)
        var total_flips = 0
        for p in range(G1_PROMPTS):
            var off = g1_offsets[p]  # the five fixture slices: 0/16/32/64/128
            var prompt = _prompt_slice(race_ids, off, G1_PROMPT_LEN)
            var rf = _run_f32(sf32, prompt, G1_PROMPT_LEN, G1_TOKENS - 1, n_layers, True)
            var rp = _run_p3(sp3, prompt, G1_PROMPT_LEN, G1_TOKENS - 1, n_layers, True)
            if rf.first_token != rp.first_token:
                # Identical f32 prefill code on identical f32 weights — disagreement here is
                # a structural bug, not a quantization flip.
                raise Error(
                    "qwen3_p3_session_cuda: prefill first-token disagreement (f32 half broken)"
                )
            var flips = 0
            var first_div = -1
            for i in range(G1_TOKENS):
                if rf.tokens[i] != rp.tokens[i]:
                    flips += 1
                    if first_div < 0:
                        first_div = i
            total_flips += flips
            if flips == 0:
                print("  prompt", p, "(offset", off, "): ", G1_TOKENS, "/", G1_TOKENS,
                      " tokens identical")
            else:
                print("  prompt", p, "(offset", off, "): ", G1_TOKENS - flips, "/", G1_TOKENS,
                      " identical,", flips, "flip(s), first divergence at index", first_div,
                      ": f32 =", rf.tokens[first_div], "p3 =", rp.tokens[first_div])
        print("G1 RESULT:", total_flips,
              "total flip(s) across all prompts (reporting gate — quantization may flip a",
              "near-tie argmax; adoption requires G0's 16/16)")

        # ═══ G2 — decode tok/s, gen64 + gen256, 20-run median + rel-IQR, both sessions ═══
        print("G2 — decode tok/s,", N_RUNS, "timed runs per cell (1 untimed warmup each)")
        var gen_lengths = List[Int]()
        gen_lengths.append(64)
        gen_lengths.append(256)
        for gi in range(len(gen_lengths)):
            var gen = gen_lengths[gi]

            # f32 cell
            _ = _run_f32(sf32, race_ids, n_prompt, gen, n_layers, False)
            var f32_ms = List[Float64]()
            for run in range(N_RUNS):
                var r = _run_f32(sf32, race_ids, n_prompt, gen, n_layers, False)
                f32_ms.append(r.decode_ms)
            var f32_stats = _cell_stats(f32_ms)
            var f32_toks = Float64(gen) / (f32_stats.median / 1000.0)

            # packed3 cell
            _ = _run_p3(sp3, race_ids, n_prompt, gen, n_layers, False)
            var p3_ms = List[Float64]()
            for run in range(N_RUNS):
                var r = _run_p3(sp3, race_ids, n_prompt, gen, n_layers, False)
                p3_ms.append(r.decode_ms)
            var p3_stats = _cell_stats(p3_ms)
            var p3_toks = Float64(gen) / (p3_stats.median / 1000.0)

            print("  gen", gen, " f32: median", f32_stats.median, "ms | rel IQR",
                  f32_stats.rel_iqr * 100.0, "% | outliers", f32_stats.n_outliers, "|",
                  f32_toks, "tok/s",
                  "(" + ("PASS" if f32_stats.passes else "FLAGGED") + ", frozen 5%)")
            print("  gen", gen, " p3 : median", p3_stats.median, "ms | rel IQR",
                  p3_stats.rel_iqr * 100.0, "% | outliers", p3_stats.n_outliers, "|",
                  p3_toks, "tok/s",
                  "(" + ("PASS" if p3_stats.passes else "FLAGGED") + ", frozen 5%)")
            print("  gen", gen, " ratio p3/f32:", p3_toks / f32_toks)

        if g0_mismatch == 0:
            print("qwen3_p3_session_cuda: done (G0 PASS)")
        else:
            print("qwen3_p3_session_cuda: done (G0 FAIL)")
            exit(1)
