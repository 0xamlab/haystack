"""qwen3_batched_graph_cuda.mojo — W2 of the campaign gap inventory: the CAPTURED-GRAPH arm of
the continuous-batching (B-sequence) CUDA decode path, benched against the W1 per-dispatch arm
for both CORRECTNESS and aggregate throughput. Drives
`residentk.session_cuda_batched_graph._CudaResidentQwen3BatchedGraph` (which COMPOSES the W1
`_CudaResidentQwen3Batched` — one session holds BOTH arms, same weights, same per-sequence KV
slots) plus `residentk.session_cuda._CudaResidentQwen3` as the single-stream reference oracle.
Same `/tmp/qwen3smoke/{manifest.json,weights.blob}` checkpoint dump every other CUDA arm reads
(argv[1] overrides the directory), same 256-token race prompt (read from the manifest's own
`input_ids`, never restated here).

Correctness gates (FIRST, before any throughput number is printed)
-------------------------------------------------------------------
Gate 0 — single-stream reference vs the campaign oracle: the single-stream session's greedy
stream on the race prompt must match the known-correct 8-id window + 7-id repeat cycle
(`_oracle_token`, byte-for-byte the function `qwen3_batched_cuda.mojo` uses). This ties the
whole driver to the campaign oracle before any batched arm is trusted.

Gate G1 — graph arm == W1 per-dispatch arm, token for token, per sequence:
  * B in {1, 8, 32}, 128 decode steps each; both arms run on the SAME composed session from
    the SAME prefill state;
  * the per-dispatch arm is additionally diffed against the single-stream reference stream
    (the W1 driver's own gate, ported — per-dispatch == single-stream == oracle), so a G1 PASS
    proves graph == per-dispatch == single-stream == oracle in one chain;
  * any mismatch prints FAIL and exits nonzero.

Gate G2 — ENGAGEMENT check (the campaign's stale-binary lesson: a graph build that silently
no-ops or under-performs must FAIL loudly, not just print a sad number):
  * at B in {8, 32}: the graph arm's per-step wall time is measured at n_steps in
    {32, 64, 128, 256} (warmup + G2_RUNS timed runs each, decode-only window, re-prefill per
    run untimed);
  * FLATNESS: max/min of the four per-step medians <= 10% — replay cost must not grow with the
    replayed step count (a capture that leaks per-step host work, or re-captures, fails this);
  * STRICTLY FASTER than the W1 per-dispatch arm's per-step median at EVERY one of the four
    depths (B >= 8 is where the W1 arm's B-amortized dispatch cost still dominates and the
    single-stream arm's 71 -> 330 tok/s graph win says the replay arm must win);
  * any violation prints the full number table, FAIL, and exits nonzero.

Throughput cells (after all gates pass)
----------------------------------------
Per B in {1, 4, 8, 16, 32}: WARMUP untimed runs, then RUNS (default 20) timed runs per arm;
each run re-prefills B prompts (untimed — decode-only discipline, exactly the W1 driver's own)
and times ONLY the decode chain (`seed_and_run_batched_graph` for the graph arm,
`seed_and_run_batched` for the per-dispatch arm). Reported per cell per arm:
  * aggregate tok/s = B * N_NEW / decode-wall, per run
  * median + rel-IQR = (p75-p25)/median over the runs, then the frozen campaign outlier rule:
    runs deviating >10% from the median excluded and median/IQR recomputed
    (REALRACE_RESULTS.md "End-to-end race harness, DVFS-corrected protocol"); both raw and
    outlier-excluded numbers printed;
  * the graph-vs-per-dispatch RATIO of the clean medians — the W2 headline number.

Build (the CUDA lane recipe, no CUDA toolkit at build time — setup_vm.sh stage 7's pattern; the
ONLY deltas from the W1 driver are this file's own source path and the two new modules it pulls
in — `residentk.kernels_batched_cuda_graph` and `residentk.session_cuda_batched_graph`, both
resolved through the SAME -I paths):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \\
        -I mojo/engine -I attention_forge \\
        benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo \\
        -o qwen3_batched_graph_cuda

    # if the pinned toolchain does not auto-link the MAX CUDA runtime (setup_vm.sh's fallback):
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \\
        -I mojo/engine -I attention_forge \\
        benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo \\
        --emit-object -o qwen3_batched_graph_cuda.o
    clang qwen3_batched_graph_cuda.o -o qwen3_batched_graph_cuda -L <max-lib> -Wl,-rpath,<max-lib> \\
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \\
        -lAsyncRTMojoBindings -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm

--target-accelerator follows the VM's GPU: sm_80 A100 / sm_89 L4 / sm_75 T4.

Usage (VM command):

    ./qwen3_batched_graph_cuda /tmp/qwen3smoke                 # 20 runs/cell, N_NEW=128
    ./qwen3_batched_graph_cuda /tmp/qwen3smoke --runs 5 --n-new 64
"""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_OK,
    residentk_status_name,
)
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3
from residentk.session_cuda_batched import (
    CUDA_BATCH_N_SPLITS,
    _CUDA_BATCH_DECODE_MAX_SEQS,
)
from residentk.session_cuda_batched_graph import _CudaResidentQwen3BatchedGraph

comptime DEFAULT_CHECKPOINT_DIR: String = "/tmp/qwen3smoke"
comptime MAX_CTX: Int = 1024
"""Room for the 256-token race prompt + the decode tail at every B/n_steps this driver runs
(256 + 256 = 512 <= 1024). Same conservative default the W1 driver uses; the batched KV is
B_MAX x max_ctx per layer per K/V, and both sessions (composed graph arm + single-stream
reference) hold one each."""

comptime N_NEW_DEFAULT: Int = 128
comptime RUNS_DEFAULT: Int = 20
comptime WARMUP_DEFAULT: Int = 2
comptime EOS_TOKEN_ID: Int = 151643

comptime ORACLE_WINDOW: Int = 8
"""The campaign's known-correct greedy window for the 256-token race prompt on Qwen3-0.6B-Base."""

comptime G1_STEPS: Int = 128
"""G1's fixed decode depth: graph vs per-dispatch token streams compared over exactly 128
steps for B in {1, 8, 32}, per the W2 design brief."""

comptime G2_RUNS: Int = 7
"""Timed runs per (B, n_steps, arm) engagement cell — enough for a stable median at a
measurement whose whole point is wall-time stability, cheap enough to run at four depths."""

comptime G2_WARMUP: Int = 2
comptime G2_FLAT_TOL: Float64 = 0.10
"""G2 flatness bar: the worst per-step median across the four depths may exceed the best by at
most this fraction. Replay is a fixed-cost submission — growth beyond 10% with step count means
the arm is not really replaying."""


def _oracle_token(i: Int) -> Int:
    """`i`-th expected generated token: the 8-token window, then the 7-token repeat cycle the
    model settles into on this prompt — byte-for-byte the function `qwen3_batched_cuda.mojo`
    uses (the oracle is restated per driver, the campaign convention)."""
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


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_batched_graph_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_batched_graph_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_batched_graph_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    """Read one tensor out of the flat Float64 blob — the same loader shape the other CUDA
    drivers use (a driver helper with hardcoded paths, deliberately copied, not shared)."""
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _sort_f64(mut xs: List[Float64]):
    """In-place ascending sort for the tiny run-count lists (Mojo 1.0.0's List carries no sort
    method; insertion sort at <= 32 elements is noise next to the decode runs it orders)."""
    var n = len(xs)
    for i in range(1, n):
        var v = xs[i]
        var j = i - 1
        while j >= 0 and xs[j] > v:
            xs[j + 1] = xs[j]
            j -= 1
        xs[j + 1] = v


@fieldwise_init
struct CellStats(Copyable, Movable):
    """One throughput cell's campaign-discipline summary."""

    var median: Float64
    var rel_iqr: Float64
    var n_outliers: Int
    var median_clean: Float64
    var rel_iqr_clean: Float64


def _median_of_sorted(ref xs: List[Float64]) -> Float64:
    """Median of an ALREADY-SORTED non-empty list (borrowed, never mutated)."""
    var n = len(xs)
    if n % 2 == 1:
        return xs[n // 2]
    return 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def _cell_stats(runs: List[Float64]) raises -> CellStats:
    """Median + rel-IQR = (p75-p25)/median over the runs, then the frozen campaign outlier rule:
    runs deviating >10% from the median are excluded and both are recomputed
    (REALRACE_RESULTS.md "End-to-end race harness, DVFS-corrected protocol")."""
    var n = len(runs)
    var s1 = List[Float64]()
    for i in range(n):
        s1.append(runs[i])
    _sort_f64(s1)
    var med = _median_of_sorted(s1)
    var rel_iqr = (
        (s1[(n * 75) // 100] - s1[(n * 25) // 100]) / med if (med > 0.0 and n >= 4) else 0.0
    )

    var clean = List[Float64]()
    for i in range(n):
        var dev = (runs[i] - med) / med if med > 0.0 else 0.0
        if dev < 0.0:
            dev = -dev
        if dev <= 0.10:
            clean.append(runs[i])
    var n_out = n - len(clean)
    var med_clean = med
    var iqr_clean = rel_iqr
    var m = len(clean)
    if m >= 1:
        _sort_f64(clean)
        med_clean = _median_of_sorted(clean)
        iqr_clean = (
            (clean[(m * 75) // 100] - clean[(m * 25) // 100]) / med_clean if m >= 4 else 0.0
        )
    return CellStats(med, rel_iqr, n_out, med_clean, iqr_clean)


def _median_of_runs(mut runs: List[Float64]) raises -> Float64:
    """Plain median of a run list (mutated in place — the caller discards it afterwards)."""
    if len(runs) == 0:
        return 0.0
    _sort_f64(runs)
    return _median_of_sorted(runs)


def _make_prompts(prompt_ids: List[Int], B: Int) raises -> List[List[Int]]:
    """B independent copies of the race prompt — each sequence owns its own list, the shape
    `prefill_batched` ingests."""
    var prompts = List[List[Int]]()
    for _ in range(B):
        var p = List[Int](capacity=len(prompt_ids))
        for k in range(len(prompt_ids)):
            p.append(prompt_ids[k])
        prompts.append(p^)
    return prompts^


def _uniform_poss(B: Int, pos: Int) raises -> List[Int]:
    var poss = List[Int]()
    for _ in range(B):
        poss.append(pos)
    return poss^


def _single_stream_generate(
    mut s: _CudaResidentQwen3, ref prompt: List[Int], n_new: Int,
) raises -> List[Int]:
    """Reference greedy stream: prefill + n_new decode steps through the SINGLE-STREAM session.
    Returns [first_token, tok_1, ..., tok_n_new]. Borrows the prompt (the caller keeps it for
    the batched side); `prefill` consumes an owned copy."""
    var p = List[Int](capacity=len(prompt))
    for i in range(len(prompt)):
        p.append(prompt[i])
    var pf = s.prefill(p^)
    _check_resident(pf.status, "single-stream prefill")
    var stream = List[Int](capacity=n_new + 1)
    stream.append(pf.token_id)
    var last = pf.token_id
    var pos = len(prompt)
    for _ in range(n_new):
        var r = s.step(last, pos)
        _check_resident(r.status, "single-stream step")
        stream.append(r.token_id)
        last = r.token_id
        pos += 1
    return stream^


def main() raises:
    var args = argv()
    var ckpt_dir = DEFAULT_CHECKPOINT_DIR
    var runs = RUNS_DEFAULT
    var n_new = N_NEW_DEFAULT
    var warmup = WARMUP_DEFAULT
    var i = 1
    while i < len(args):
        var a = String(args[i])
        if a == "--checkpoint" and i + 1 < len(args):
            ckpt_dir = String(args[i + 1])
            i += 2
        elif a == "--runs" and i + 1 < len(args):
            runs = parse_int(args[i + 1])
            i += 2
        elif a == "--n-new" and i + 1 < len(args):
            n_new = parse_int(args[i + 1])
            i += 2
        elif a == "--warmup" and i + 1 < len(args):
            warmup = parse_int(args[i + 1])
            i += 2
        else:
            ckpt_dir = a
            i += 1

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
        raise Error("qwen3_batched_graph_cuda: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = MAX_CTX
    var n_ref = n_new if n_new > G1_STEPS else G1_STEPS
    if n_prompt + 256 > max_ctx:
        raise Error(
            "qwen3_batched_graph_cuda: prompt (" + String(n_prompt)
            + ") + max decode depth (256) exceeds MAX_CTX (" + String(max_ctx) + ")"
        )

    print("qwen3_batched_graph_cuda: checkpoint =", ckpt_dir)
    print("  d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q, "h_kv=", h_kv,
          "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size, "n_prompt=", n_prompt)
    print("  max_ctx=", max_ctx, "B_max=", _CUDA_BATCH_DECODE_MAX_SEQS,
          "n_splits=", CUDA_BATCH_N_SPLITS, "n_new=", n_new, "runs=", runs,
          "warmup=", warmup)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, n_ref, max_ctx, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_batched_graph_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time
        # gate is visible at this file's only construction site.
        print("qwen3_batched_graph_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_batched_graph_cuda: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for k in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[k]))
        if len(prompt_ids) != n_prompt:
            raise Error(
                "qwen3_batched_graph_cuda: input_ids length does not match config.n_tokens"
            )

        var tensors_obj = json_get_object(manifest, "tensors")
        var rt = rope_table(d_head, max_ctx, theta)
        if rt.status != ATTN_OK:
            raise Error("qwen3_batched_graph_cuda: rope_table failed")

        # ═══ ONE-TIME: open BOTH sessions, convert every weight to Float32, upload ═══
        var gs = _CudaResidentQwen3BatchedGraph(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        print("  device:", gs.device_name())
        var ss = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )

        var t_read0 = perf_counter_ns()
        var embed_table = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, "model.norm.weight")
        _check_resident(
            gs.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx),
            "graph-session upload_globals",
        )
        _check_resident(
            ss.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx),
            "single-stream upload_globals",
        )
        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "input_layernorm.weight")
            var ln2 = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "post_attention_layernorm.weight")
            var qn = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "self_attn.q_norm.weight")
            var kn = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "self_attn.k_norm.weight")
            var wq = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "self_attn.q_proj.weight")
            var wk = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "self_attn.k_proj.weight")
            var wv = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "self_attn.v_proj.weight")
            var wo = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "self_attn.o_proj.weight")
            var wg = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "mlp.gate_proj.weight")
            var wu = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "mlp.up_proj.weight")
            var wd = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, prefix + "mlp.down_proj.weight")
            _check_resident(
                gs.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "graph-session upload_layer " + String(layer),
            )
            _check_resident(
                ss.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "single-stream upload_layer " + String(layer),
            )
        _check_resident(gs.seal(), "graph-session seal")
        _check_resident(ss.seal(), "single-stream seal")
        var t_read1 = perf_counter_ns()
        print("  one-time weight load (both sessions):", _ms(t_read1 - t_read0), "ms")
        print("  captured replay node count per B: 1 + n_layers*9 + 4 =",
              gs.batched_graph_node_count(1),
              "(vs", gs.batched_dispatch_count(1), "per-dispatch enqueues per B-token step)")

        # ═══ GATE 0: the single-stream reference is itself oracle-checked ═══
        var ref_full = _single_stream_generate(ss, prompt_ids, n_ref)
        var oracle_bad = 0
        for k in range(len(ref_full)):
            if ref_full[k] != _oracle_token(k):
                oracle_bad += 1
        if oracle_bad > 0:
            print("RESULT: FAIL — single-stream reference disagrees with the campaign oracle (",
                  oracle_bad, "tokens)")
            exit(1)
        print("  gate 0: single-stream reference matches the campaign oracle (",
              len(ref_full), "tokens)")

        var all_pass = True

        # ═══ GATE G1: graph arm == W1 per-dispatch arm, per sequence ═══
        var g1_bs = List[Int]()
        g1_bs.append(1)
        g1_bs.append(8)
        g1_bs.append(32)
        for bi in range(len(g1_bs)):
            var B = g1_bs[bi]
            var prompts = _make_prompts(prompt_ids, B)
            var firsts = gs.prefill_batched(prompts)
            var gate_ok = len(firsts) == B
            var first_mismatch = 0
            var graph_vs_disp_bad = 0
            if gate_ok:
                for b in range(B):
                    if firsts[b] != ref_full[0]:
                        first_mismatch += 1
                        gate_ok = False
            if gate_ok:
                var poss = _uniform_poss(B, n_prompt)

                # ── the W1 per-dispatch arm, diffed against the single-stream reference ──
                var st = gs.seed_and_run_batched(firsts, poss, G1_STEPS)
                _check_resident(st, "seed_and_run_batched B=" + String(B))
                var disp_tokens = List[List[Int]]()
                for b in range(B):
                    var row = List[Int](capacity=G1_STEPS)
                    for step in range(G1_STEPS):
                        var t = gs.batched_token(b, step)
                        row.append(t)
                        if t != ref_full[step + 1]:
                            gate_ok = False
                    disp_tokens.append(row^)

                # ── the graph arm, diffed against the per-dispatch arm token for token ──
                var st2 = gs.seed_and_run_batched_graph(firsts, poss, G1_STEPS)
                _check_resident(st2, "seed_and_run_batched_graph B=" + String(B))
                for b in range(B):
                    for step in range(G1_STEPS):
                        if gs.graph_batched_token(b, step) != disp_tokens[b][step]:
                            graph_vs_disp_bad += 1
                            gate_ok = False

            if gate_ok:
                print("  gate G1 B=", B, ": PASS —", B, " sequences x", G1_STEPS,
                      "steps: graph == per-dispatch == single-stream == oracle")
            else:
                print("  gate G1 B=", B, ": FAIL — first-token mismatches:", first_mismatch,
                      "| graph-vs-per-dispatch token mismatches:", graph_vs_disp_bad)
                all_pass = False

        # ═══ GATE G2: engagement — flat per-step wall + strictly faster than per-dispatch ═══
        var g2_bs = List[Int]()
        g2_bs.append(8)
        g2_bs.append(32)
        var g2_steps = List[Int]()
        g2_steps.append(32)
        g2_steps.append(64)
        g2_steps.append(128)
        g2_steps.append(256)

        for bi in range(len(g2_bs)):
            var B = g2_bs[bi]
            var prompts = _make_prompts(prompt_ids, B)
            var graph_step_ms = List[Float64]()
            var disp_step_ms = List[Float64]()
            for si in range(len(g2_steps)):
                var n_steps = g2_steps[si]
                var g_runs = List[Float64]()
                var d_runs = List[Float64]()
                var total = G2_WARMUP + G2_RUNS
                for r in range(total):
                    var firsts = gs.prefill_batched(prompts)
                    if len(firsts) != B:
                        raise Error(
                            "qwen3_batched_graph_cuda: prefill_batched failed in gate G2"
                        )
                    var poss = _uniform_poss(B, n_prompt)
                    var t0 = perf_counter_ns()
                    var st = gs.seed_and_run_batched_graph(firsts, poss, n_steps)
                    var t1 = perf_counter_ns()
                    _check_resident(st, "gate G2 graph arm")
                    if r >= G2_WARMUP:
                        g_runs.append(_ms(t1 - t0) / Float64(n_steps))

                    var firsts2 = gs.prefill_batched(prompts)
                    if len(firsts2) != B:
                        raise Error(
                            "qwen3_batched_graph_cuda: prefill_batched failed in gate G2"
                        )
                    var poss2 = _uniform_poss(B, n_prompt)
                    var t2 = perf_counter_ns()
                    var st2 = gs.seed_and_run_batched(firsts2, poss2, n_steps)
                    var t3 = perf_counter_ns()
                    _check_resident(st2, "gate G2 per-dispatch arm")
                    if r >= G2_WARMUP:
                        d_runs.append(_ms(t3 - t2) / Float64(n_steps))

                var g_med = _median_of_runs(g_runs)
                var d_med = _median_of_runs(d_runs)
                graph_step_ms.append(g_med)
                disp_step_ms.append(d_med)
                print("  gate G2 B=", B, " n_steps=", n_steps, ": graph ", g_med,
                      " ms/step vs per-dispatch ", d_med, " ms/step (",
                      G2_RUNS, "-run medians)")

            # ── flatness of the graph arm's per-step wall across the four depths ──
            var g_min = graph_step_ms[0]
            var g_max = graph_step_ms[0]
            for k in range(1, len(graph_step_ms)):
                if graph_step_ms[k] < g_min:
                    g_min = graph_step_ms[k]
                if graph_step_ms[k] > g_max:
                    g_max = graph_step_ms[k]
            var flat_ratio = (g_max - g_min) / g_min if g_min > 0.0 else 1.0e9
            var flat_ok = flat_ratio <= G2_FLAT_TOL

            # ── strictly faster than the W1 per-dispatch arm at every depth ──
            var faster_ok = True
            for k in range(len(g2_steps)):
                if not (graph_step_ms[k] < disp_step_ms[k]):
                    faster_ok = False

            if flat_ok and faster_ok:
                print("  gate G2 B=", B, ": PASS — per-step wall flat (spread ",
                      flat_ratio * 100.0, "% <= ", G2_FLAT_TOL * 100.0,
                      "%) and strictly faster than per-dispatch at all four depths")
            else:
                if not flat_ok:
                    print("  gate G2 B=", B, ": FAIL — per-step wall NOT flat (spread ",
                          flat_ratio * 100.0, "% > ", G2_FLAT_TOL * 100.0,
                          "%): the graph arm is not replaying at fixed cost")
                if not faster_ok:
                    print("  gate G2 B=", B,
                          ": FAIL — graph arm NOT strictly faster than per-dispatch at B=", B)
                all_pass = False

        if not all_pass:
            print("RESULT: FAIL — correctness/engagement gate failed; no throughput numbers",
                  "published")
            exit(1)
        print("RESULT: PASS — gates 0 + G1 (every B) + G2 (flat + faster)")

        # ═══ THROUGHPUT CELLS ═══
        print("")
        print("Throughput (decode-only; prefill excluded from the timed window):")
        print("  per-dispatch enqueues per B-token step: 1 + n_layers*9 + 3 =",
              gs.batched_dispatch_count(1),
              "| captured replay nodes per B-step:", gs.batched_graph_node_count(1))
        var cell_bs = List[Int]()
        cell_bs.append(1)
        cell_bs.append(4)
        cell_bs.append(8)
        cell_bs.append(16)
        cell_bs.append(32)
        for bi in range(len(cell_bs)):
            var B = cell_bs[bi]
            var prompts = _make_prompts(prompt_ids, B)

            var graph_tps = List[Float64]()
            var disp_tps = List[Float64]()
            var total_runs = warmup + runs
            for r in range(total_runs):
                var firsts = gs.prefill_batched(prompts)
                if len(firsts) != B:
                    raise Error(
                        "qwen3_batched_graph_cuda: prefill_batched failed in the bench loop"
                    )
                if firsts[B - 1] == EOS_TOKEN_ID:
                    raise Error(
                        "qwen3_batched_graph_cuda: prompt prefill hit EOS — bench invalid"
                    )
                var poss = _uniform_poss(B, n_prompt)
                var t0 = perf_counter_ns()
                var st = gs.seed_and_run_batched_graph(firsts, poss, n_new)
                var t1 = perf_counter_ns()
                _check_resident(st, "bench seed_and_run_batched_graph")
                if r >= warmup:
                    var wall_s = Float64(t1 - t0) / 1.0e9
                    graph_tps.append(Float64(B * n_new) / wall_s)

                var firsts2 = gs.prefill_batched(prompts)
                if len(firsts2) != B:
                    raise Error(
                        "qwen3_batched_graph_cuda: prefill_batched failed in the bench loop"
                    )
                var poss2 = _uniform_poss(B, n_prompt)
                var t2 = perf_counter_ns()
                var st2 = gs.seed_and_run_batched(firsts2, poss2, n_new)
                var t3 = perf_counter_ns()
                _check_resident(st2, "bench seed_and_run_batched")
                if r >= warmup:
                    var wall_s2 = Float64(t3 - t2) / 1.0e9
                    disp_tps.append(Float64(B * n_new) / wall_s2)

            var gstats = _cell_stats(graph_tps)
            var dstats = _cell_stats(disp_tps)
            var ratio = (
                gstats.median_clean / dstats.median_clean if dstats.median_clean > 0.0 else 0.0
            )
            print("  B=", B, ": graph ", gstats.median_clean, " tok/s | per-dispatch ",
                  dstats.median_clean, " tok/s | ratio graph/per-dispatch ", ratio, "x")
            print("        graph:     median ", gstats.median, " rel-IQR ",
                  gstats.rel_iqr * 100.0, "% | clean rel-IQR ", gstats.rel_iqr_clean * 100.0,
                  "% | outliers(>10%) ", gstats.n_outliers, "/", len(graph_tps),
                  " | verdict ",
                  "PASS(<=5%)" if gstats.rel_iqr_clean <= 0.05 else "FLAG(>5%)")
            print("        per-dispatch: median ", dstats.median, " rel-IQR ",
                  dstats.rel_iqr * 100.0, "% | clean rel-IQR ", dstats.rel_iqr_clean * 100.0,
                  "% | outliers(>10%) ", dstats.n_outliers, "/", len(disp_tps),
                  " | verdict ",
                  "PASS(<=5%)" if dstats.rel_iqr_clean <= 0.05 else "FLAG(>5%)")

        print("")
        print("qwen3_batched_graph_cuda: done.")
        exit(0)
