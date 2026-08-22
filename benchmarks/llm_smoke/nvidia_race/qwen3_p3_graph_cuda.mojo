"""qwen3_p3_graph_cuda.mojo — the CAPTURED-GRAPH arm of the packed3 CUDA decode session
(`residentk.session_cuda_p3_graph._CudaResidentQwen3P3Graph`, which COMPOSES the #800
`_CudaResidentQwen3P3` — one session holds BOTH arms, same weights, same KV cache) through
the campaign's gate battery, then the race throughput table. The packed3 session streams
~1.19 GB/token vs f32's 2.62 GB, but per-dispatch it sits on the same ~19 ms/token
host-dispatch floor as f32 (1.04x) — this driver measures what the packed3 arm becomes once
the f32 graph arm's proven capture deletes that floor: a bandwidth-bound decode that should
clear the llama.cpp Q8_0 ledger rows decisively. Same `/tmp/qwen3smoke/{manifest.json,
weights.blob}` checkpoint dump every other CUDA arm reads (argv[1] overrides the directory),
same 256-token race prompt (read from the manifest's own `input_ids`, never restated here).

Correctness + engagement gates (FIRST, before any throughput number is printed)
--------------------------------------------------------------------------------
Gate G0 — THE ORACLE (hard gate): 16/16 greedy tokens on the campaign fixture THROUGH THE
     GRAPH ARM — the manifest's 256-token race prompt, prefill then ONE async chain of 15
     replays, every generated token checked against the campaign's known-correct continuation
     (the 8-token window then the 7-token repeat cycle, `_oracle_token` byte-for-byte the
     function qwen3_p3_session_cuda.mojo uses). The whole continuation from a single async
     chain is the stronger oracle form qwen3_generate_cuda.mojo's graph lane enforces.

Gate G1 — graph-p3 == per-dispatch-p3, token for token (hard gate): 3 seeds x 128 decode
     steps. The 3 seeds are deterministic 64-token slices of the race fixture (offsets
     0/64/128 — this zero-Python driver carries no tokenizer; the fixture's ids are the only
     prompts the campaign standardizes on). Both arms run on the SAME composed session from
     the SAME prefill state; every one of the 128 tokens must match, else FAIL + exit 1.
     Together with G0 this chains graph == per-dispatch == oracle. NOTE the graph arm's
     packed3 kernel generation is a build-time switch (`residentk.session_cuda_p3_graph.
     P3_GRAPH_V2_KERNELS` / `P3_GRAPH_V3_KERNELS`): the default build dispatches the v2
     twins (bit-identical math), so there this gate is additionally the v2-vs-v1
     token-identity diff; a `-D ALGENTA_P3_V3` build reassociates the chunk sums, so its G1
     switches to the vs-f32 flip-REPORTING form (qwen3_p3_session_cuda.mojo's G1 shape —
     G0 remains the hard gate).

Gate G2 — ENGAGEMENT check (hard gate; the campaign's stale-binary lesson: a graph build
     that silently no-ops or under-performs must FAIL loudly, not just print a sad number):
     the graph arm's per-step wall is measured at n_steps in {32, 64, 128, 256} (warmup +
     G2_RUNS timed runs each, decode-only window, re-prefill per run untimed), and must be
       * FLAT: worst per-step median across the four depths within 10% of the best — replay
         cost must not grow with the replayed step count (a capture that leaks per-step host
         work, or re-captures, fails this);
       * STRICTLY FASTER than the per-dispatch packed3 arm's per-step median at EVERY depth;
     else the full number table is printed, FAIL, exit 1.

Throughput cells (after all gates pass)
----------------------------------------
gen64 and gen256 on the race prompt; ONE untimed warmup then N_RUNS = 20 timed generations
per arm (the frozen qwen3_bench_cuda.mojo discipline: median + rel-IQR = (p75-p25)/median,
outlier census at >10% deviation, PASS/FLAG at the frozen 5% tolerance). Three arms, same
process / same GPU state / same weights:
  * graph-p3        — `seed_and_run_graph_p3` (this driver's subject)
  * f32-graph       — the composed session's inner f32 session `seed_and_run_graph`
  * per-dispatch-p3 — `step_p3` loop (the #800 measurement this arm replaces)
Printed beside each cell: the ratio vs the ledger's A100 llama.cpp rows (REALRACE_RESULTS.md):
Q8_0 404.8 (gen64) / 420.0 (gen256) tok/s and F16 356.9 / 366.6 tok/s — the decisive race
measurement this campaign owes.

Build (the CUDA lane recipe, no CUDA toolkit at build time — setup_vm.sh stage 7's form,
mirrored from qwen3_p3_session_cuda.mojo's docstring; plain build first, the object+link
recipe as fallback when the pinned toolchain does not auto-link the MAX CUDA runtime):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo \\
        -o qwen3_p3_graph_cuda

The default build dispatches the v4 packed3 kernels in the graph arm (v2's int32 word-view
unpack everywhere PLUS the fused gate/up swiglu kernel; both bit-identical math). Add
`-D ALGENTA_P3_V2` for v2-only, `-D ALGENTA_P3_V1` for the #800/#801 byte-view control, or
`-D ALGENTA_P3_V3` for the v3 twins (int32 unpack PLUS three interleaved accumulators —
reassociated sums, G1 in the flip-reporting form) — same source tree, same gates, one run
per binary:

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_P3_V1 --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo \\
        -o qwen3_p3_graph_cuda_v1
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_P3_V2 --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo \\
        -o qwen3_p3_graph_cuda_v2
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_P3_V3 --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo \\
        -o qwen3_p3_graph_cuda_v3

    # if the pinned toolchain does not auto-link the MAX CUDA runtime:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo \\
        --emit object -o qwen3_p3_graph_cuda.o
    clang qwen3_p3_graph_cuda.o -o qwen3_p3_graph_cuda -L <max-lib> -Wl,-rpath,<max-lib> \\
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \\
        -lAsyncRTMojoBindings -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm

(same with `sm_89` for the L4 lane). `--target-accelerator` follows the VM's GPU.

Run on the VM (checkpoint prepared by setup_vm.sh stage 8 / prepare_smoke_checkpoint.py):

    ./qwen3_p3_graph_cuda /tmp/qwen3smoke
    ./qwen3_p3_graph_cuda /tmp/qwen3smoke --runs 5      # quick smoke pass

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
from residentk.session_cuda import CUDA_SESSION_BUILD
from residentk.session_cuda_p3_graph import _CudaResidentQwen3P3Graph, P3_GRAPH_V3_KERNELS

comptime DEFAULT_CHECKPOINT_DIR: String = "/tmp/qwen3smoke"

comptime MAX_CTX: Int = 1024
"""Room for the 256-token race prompt plus the gen256 / G2-256 decode tails
(256 + 256 = 512 <= 1024) — the same conservative default qwen3_p3_session_cuda.mojo uses."""

comptime G0_TOKENS: Int = 16
"""The oracle gate's generation length: 16/16 greedy tokens must sit on the campaign's
known-correct continuation (same protocol qwen3_generate_cuda.mojo enforces)."""

comptime G1_SEEDS: Int = 3
comptime G1_PROMPT_LEN: Int = 64
comptime G1_STEPS: Int = 128
"""G1: three 64-token slices of the race fixture (offsets 0/64/128), 128 decode steps each,
graph-p3 vs per-dispatch-p3 token for token."""

comptime G2_RUNS: Int = 7
"""Timed runs per (n_steps, arm) engagement cell — the batched graph driver's choice: enough
for a stable median at a measurement whose whole point is wall-time stability, cheap enough
to run at four depths."""

comptime G2_WARMUP: Int = 2
comptime G2_FLAT_TOL: Float64 = 0.10
"""G2 flatness bar: the worst per-step median across the four depths may exceed the best by
at most this fraction (the batched graph driver's bar, carried over)."""

comptime N_RUNS: Int = 20
"""The frozen 20-runs/cell discipline (benchmarks/competitors/llama_cpp/README.md), the same
one qwen3_bench_cuda.mojo runs."""

comptime WARMUP: Int = 1
comptime IQR_TOLERANCE: Float64 = 0.05
"""The frozen relative-IQR tolerance: (p75 - p25) / median <= 5%."""

comptime OUTLIER_DEVIATION: Float64 = 0.10
"""The frozen outlier rule: a run deviating >10% from the median is flagged and reported."""

comptime ORACLE_WINDOW: Int = 8
"""The campaign's known-correct greedy window for the 256-token race prompt on Qwen3-0.6B-Base —
copied VERBATIM from qwen3_p3_session_cuda.mojo's own gate (a driver helper with hardcoded
values, deliberately copied, not shared)."""

comptime LEDGER_Q8_0_GEN64: Float64 = 404.8
comptime LEDGER_Q8_0_GEN256: Float64 = 420.0
comptime LEDGER_F16_GEN64: Float64 = 356.9
comptime LEDGER_F16_GEN256: Float64 = 366.6
"""The ledger's A100 llama.cpp decode rows this race is scored against (REALRACE_RESULTS.md:
`llama.cpp Q8_0 ... 404.8 (IQR 0.12%) 420.0 (IQR 0.16%)` and `llama.cpp F16 control ...
356.9 / 366.6`)."""


def _oracle_token(i: Int) -> Int:
    """`i`-th expected generated token: the 8-token window, then the 7-token repeat cycle the
    model settles into on this prompt — qwen3_p3_session_cuda.mojo's oracle, character for
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


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_p3_graph_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_p3_graph_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_p3_graph_cuda: short read at byte offset " + String(byte_offset))
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


def _copy_ids(ref ids: List[Int]) raises -> List[Int]:
    """A fresh owned copy of a prompt id list — `prefill` takes its prompt by value, and the
    driver holds the fixture ids for every arm's re-prefill."""
    var out = List[Int](capacity=len(ids))
    for i in range(len(ids)):
        out.append(ids[i])
    return out^


def _prompt_slice(ref ids: List[Int], off: Int, n: Int) raises -> List[Int]:
    var out = List[Int](capacity=n)
    for i in range(n):
        out.append(ids[off + i])
    return out^


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


def _median_of_runs(mut runs: List[Float64]) raises -> Float64:
    """Plain median of a run list (mutated in place — the caller discards it afterwards)."""
    if len(runs) == 0:
        return 0.0
    _sort_ascending(runs)
    return _percentile(runs, 0.5)


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


def main() raises:
    var args = argv()
    var ckpt_dir = DEFAULT_CHECKPOINT_DIR
    var runs = N_RUNS
    var i = 1
    while i < len(args):
        var a = String(args[i])
        if a == "--checkpoint" and i + 1 < len(args):
            ckpt_dir = String(args[i + 1])
            i += 2
        elif a == "--runs" and i + 1 < len(args):
            runs = parse_int(args[i + 1])
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
        raise Error("qwen3_p3_graph_cuda: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen3_p3_graph_cuda: checkpoint =", ckpt_dir, "| d_model =", d_model,
          "| n_layers =", n_layers, "| h_q =", h_q, "| h_kv =", h_kv,
          "| d_head =", d_head, "| d_ff =", d_ff, "| vocab =", vocab_size,
          "| n_prompt =", n_prompt, "| max_ctx =", MAX_CTX)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 256, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_p3_graph_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        exit(1)

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time
        # gate is visible at this file's only construction site.
        print("qwen3_p3_graph_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_p3_graph_cuda: no accelerator on this host")
            exit(1)

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var race_ids = List[Int]()
        for k in range(len(id_tokens)):
            race_ids.append(parse_int(id_tokens[k]))
        if len(race_ids) != n_prompt:
            raise Error("qwen3_p3_graph_cuda: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var blob_path = ckpt_dir + "/weights.blob"

        # ═══ ONE-TIME: open the ONE composed session (both arms), load every weight, seal ═══
        var rt = rope_table(d_head, MAX_CTX, theta)
        if rt.status != ATTN_OK:
            raise Error("qwen3_p3_graph_cuda: rope_table failed")

        var t0 = perf_counter_ns()
        var sg = _CudaResidentQwen3P3Graph(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  device:", sg.device_name())
        var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
        _check_resident(
            sg.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
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
                sg.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
        _check_resident(sg.seal(), "seal")
        var t1 = perf_counter_ns()
        print("  one-time load (f32 half + packed3 twins + upload):", _ms(t1 - t0), "ms")
        print("  captured replay nodes per token:", sg.decode_graph_node_count(),
              "(vs", sg.dispatch_budget(), "per-dispatch enqueues per token)")
        print("  graph-arm packed3 kernels:", sg.graph_kernel_variant())

        # ═══ G0 — 16/16 greedy-token oracle THROUGH THE GRAPH ARM ═══
        print("G0 — packed3 graph arm, 16 greedy tokens on the race fixture")
        var pf0 = sg.prefill(_copy_ids(race_ids))
        _check_resident(pf0.status, "G0 prefill")
        _check_resident(
            sg.seed_and_run_graph_p3(pf0.token_id, n_prompt, G0_TOKENS - 1),
            "G0 seed_and_run_graph_p3",
        )
        var g0_mismatch = 0
        var want0 = _oracle_token(0)
        if pf0.token_id != want0:
            g0_mismatch += 1
            print("  ORACLE MISMATCH at generated token 0 (prefill): got", pf0.token_id,
                  "want", want0)
        for k in range(1, G0_TOKENS):
            var got = sg.graph_token(n_prompt + k - 1)
            var want = _oracle_token(k)
            if got != want:
                g0_mismatch += 1
                print("  ORACLE MISMATCH at generated token", k, ": got", got, "want", want)
        if g0_mismatch > 0:
            print("G0 RESULT: FAIL —", g0_mismatch, "mismatched tokens")
            exit(1)
        print("G0 RESULT: PASS —", G0_TOKENS,
              "greedy tokens match the campaign oracle through one async chain")

        # ═══ G1 — token identity, 3 seeds x 128 steps ═══
        # v1/v2 builds: graph-p3 == per-dispatch-p3 token for token (HARD gate — the v2
        # kernels are bit-identical-math by construction, and per-dispatch always runs v1).
        # v3 builds: the 3-way accumulator reassociation makes the graph arm ulp-different,
        # so G1 takes the qwen3_p3_session_cuda.mojo form — graph-p3(v3) vs the f32 session,
        # flips REPORTED, not hard-failed (quantization + reassociation may flip a near-tie
        # argmax; G0 remains the hard correctness gate).
        @parameter
        if P3_GRAPH_V3_KERNELS:
            print("G1 — graph-p3(v3) vs f32 per-dispatch,", G1_SEEDS, "seeds x", G1_STEPS,
                  "steps (flip-reporting: v3 reassociates the chunk sums)")
            var g1_offsets = List[Int]()
            g1_offsets.append(0)
            g1_offsets.append(64)
            g1_offsets.append(128)
            var total_flips = 0
            for seed in range(G1_SEEDS):
                var off = g1_offsets[seed]

                # ── the f32 session's per-dispatch arm ──
                var pf_d = sg.prefill(_prompt_slice(race_ids, off, G1_PROMPT_LEN))
                _check_resident(pf_d.status, "G1 f32 prefill")
                var disp_tokens = List[Int](capacity=G1_STEPS)
                var last = pf_d.token_id
                for step in range(G1_STEPS):
                    var pos = G1_PROMPT_LEN + step
                    var r = sg.p3.f32.step(last, pos)
                    _check_resident(r.status, "G1 f32 step(pos " + String(pos) + ")")
                    disp_tokens.append(r.token_id)
                    last = r.token_id

                # ── the graph arm, from the SAME prefill state (fresh prefill) ──
                var pf_g = sg.prefill(_prompt_slice(race_ids, off, G1_PROMPT_LEN))
                _check_resident(pf_g.status, "G1 graph prefill")
                if pf_g.token_id != pf_d.token_id:
                    # Identical f32 prefill code on identical f32 weights — disagreement
                    # here is a structural bug, not a quantization flip.
                    raise Error(
                        "qwen3_p3_graph_cuda: G1 prefill first-token disagreement between arms"
                    )
                _check_resident(
                    sg.seed_and_run_graph_p3(pf_g.token_id, G1_PROMPT_LEN, G1_STEPS),
                    "G1 seed_and_run_graph_p3",
                )
                var flips = 0
                var first_div = -1
                for step in range(G1_STEPS):
                    var gt = sg.graph_token(G1_PROMPT_LEN + step)
                    if gt != disp_tokens[step]:
                        flips += 1
                        if first_div < 0:
                            first_div = step
                total_flips += flips
                if flips == 0:
                    print("  seed", seed, "(offset", off, "):", G1_STEPS, "/", G1_STEPS,
                          "tokens identical to the f32 session")
                else:
                    print("  seed", seed, "(offset", off, "):", flips,
                          "flip(s) vs f32, first at step", first_div, ": f32 =",
                          disp_tokens[first_div], "graph =",
                          sg.graph_token(G1_PROMPT_LEN + first_div))
            print("G1 RESULT:", total_flips,
                  "total flip(s) vs the f32 session across all seeds (reporting gate;",
                  "G0 16/16 remains HARD)")
        else:
            print("G1 — graph-p3 vs per-dispatch-p3,", G1_SEEDS, "seeds x", G1_STEPS, "steps")
            var g1_offsets = List[Int]()
            g1_offsets.append(0)
            g1_offsets.append(64)
            g1_offsets.append(128)
            var g1_ok = True
            for seed in range(G1_SEEDS):
                var off = g1_offsets[seed]

                # ── the per-dispatch packed3 arm ──
                var pf_d = sg.prefill(_prompt_slice(race_ids, off, G1_PROMPT_LEN))
                _check_resident(pf_d.status, "G1 per-dispatch prefill")
                var disp_tokens = List[Int](capacity=G1_STEPS)
                var last = pf_d.token_id
                for step in range(G1_STEPS):
                    var pos = G1_PROMPT_LEN + step
                    var r = sg.step_p3(last, pos)
                    _check_resident(r.status, "G1 step_p3(pos " + String(pos) + ")")
                    if r.dispatches != residentk_dispatch_budget(n_layers):
                        raise Error("qwen3_p3_graph_cuda: p3 dispatch budget disagreement")
                    disp_tokens.append(r.token_id)
                    last = r.token_id

                # ── the graph arm, from the SAME prefill state (fresh prefill) ──
                var pf_g = sg.prefill(_prompt_slice(race_ids, off, G1_PROMPT_LEN))
                _check_resident(pf_g.status, "G1 graph prefill")
                if pf_g.token_id != pf_d.token_id:
                    # Identical f32 prefill code on identical f32 weights — disagreement here is
                    # a structural bug, not a quantization flip.
                    raise Error(
                        "qwen3_p3_graph_cuda: G1 prefill first-token disagreement between arms"
                    )
                _check_resident(
                    sg.seed_and_run_graph_p3(pf_g.token_id, G1_PROMPT_LEN, G1_STEPS),
                    "G1 seed_and_run_graph_p3",
                )
                var flips = 0
                var first_div = -1
                for step in range(G1_STEPS):
                    # The per-dispatch loop's step `s` runs at pos = G1_PROMPT_LEN + s; the graph
                    # logs replay k's output at start_pos + k - 1 — the same slot.
                    var gt = sg.graph_token(G1_PROMPT_LEN + step)
                    if gt != disp_tokens[step]:
                        flips += 1
                        if first_div < 0:
                            first_div = step
                if flips == 0:
                    print("  seed", seed, "(offset", off, "):", G1_STEPS, "/", G1_STEPS,
                          "tokens identical — graph == per-dispatch")
                else:
                    print("  seed", seed, "(offset", off, "):", flips, "flip(s), first at step",
                          first_div, ": per-dispatch =", disp_tokens[first_div],
                          "graph =", sg.graph_token(G1_PROMPT_LEN + first_div))
                    g1_ok = False
            if not g1_ok:
                print("G1 RESULT: FAIL — graph-p3 disagrees with per-dispatch-p3")
                exit(1)
            print("G1 RESULT: PASS —", G1_SEEDS, "seeds x", G1_STEPS,
                  "steps token-for-token identical (graph == per-dispatch == oracle via G0)")

        # ═══ G2 — engagement: flat per-step wall + strictly faster than per-dispatch ═══
        print("G2 — engagement: graph-p3 per-step wall at n_steps 32/64/128/256 vs",
              "per-dispatch-p3 (", G2_RUNS, "-run medians,", G2_WARMUP, "warmup)")
        var g2_steps = List[Int]()
        g2_steps.append(32)
        g2_steps.append(64)
        g2_steps.append(128)
        g2_steps.append(256)
        var graph_step_ms = List[Float64]()
        var disp_step_ms = List[Float64]()
        for si in range(len(g2_steps)):
            var n_steps = g2_steps[si]
            var g_runs = List[Float64]()
            var d_runs = List[Float64]()
            var total = G2_WARMUP + G2_RUNS
            for r in range(total):
                var pf_g2 = sg.prefill(_copy_ids(race_ids))
                _check_resident(pf_g2.status, "G2 graph prefill")
                var tg0 = perf_counter_ns()
                var st = sg.seed_and_run_graph_p3(pf_g2.token_id, n_prompt, n_steps)
                var tg1 = perf_counter_ns()
                _check_resident(st, "G2 seed_and_run_graph_p3")
                if r >= G2_WARMUP:
                    g_runs.append(_ms(tg1 - tg0) / Float64(n_steps))

                var pf_d2 = sg.prefill(_copy_ids(race_ids))
                _check_resident(pf_d2.status, "G2 per-dispatch prefill")
                var last2 = pf_d2.token_id
                var td0 = perf_counter_ns()
                for step in range(n_steps):
                    var r2 = sg.step_p3(last2, n_prompt + step)
                    _check_resident(r2.status, "G2 step_p3")
                    if r2.dispatches != residentk_dispatch_budget(n_layers):
                        raise Error("qwen3_p3_graph_cuda: p3 dispatch budget disagreement")
                    last2 = r2.token_id
                var td1 = perf_counter_ns()
                if r >= G2_WARMUP:
                    d_runs.append(_ms(td1 - td0) / Float64(n_steps))

            var g_med = _median_of_runs(g_runs)
            var d_med = _median_of_runs(d_runs)
            graph_step_ms.append(g_med)
            disp_step_ms.append(d_med)
            print("  n_steps=", n_steps, ": graph-p3", g_med,
                  "ms/step vs per-dispatch-p3", d_med, "ms/step")

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

        # ── strictly faster than the per-dispatch packed3 arm at every depth ──
        var faster_ok = True
        for k in range(len(g2_steps)):
            if not (graph_step_ms[k] < disp_step_ms[k]):
                faster_ok = False

        if not (flat_ok and faster_ok):
            print("G2 RESULT: FAIL — full table:")
            for k in range(len(g2_steps)):
                print("  n_steps=", g2_steps[k], ": graph-p3", graph_step_ms[k],
                      "ms/step | per-dispatch-p3", disp_step_ms[k], "ms/step")
            if not flat_ok:
                print("  per-step wall NOT flat (spread", flat_ratio * 100.0, "% >",
                      G2_FLAT_TOL * 100.0, "%): the graph arm is not replaying at fixed cost")
            if not faster_ok:
                print("  graph arm NOT strictly faster than per-dispatch at every depth")
            exit(1)
        print("G2 RESULT: PASS — per-step wall flat (spread", flat_ratio * 100.0, "% <= ",
              G2_FLAT_TOL * 100.0, "%) and strictly faster than per-dispatch at all four depths")

        # ═══ THROUGHPUT — gen64/gen256, 20-run medians + rel-IQR, three arms ═══
        print("")
        print("Throughput (decode-only; prefill excluded from the timed window),", runs,
              "timed runs per cell (1 untimed warmup each):")
        var gen_lengths = List[Int]()
        gen_lengths.append(64)
        gen_lengths.append(256)
        for gi in range(len(gen_lengths)):
            var gen = gen_lengths[gi]

            # ── graph-p3 cell ──
            var gp_ms = List[Float64]()
            for r in range(WARMUP + runs):
                var pf = sg.prefill(_copy_ids(race_ids))
                _check_resident(pf.status, "bench graph-p3 prefill")
                var bw0 = perf_counter_ns()
                var st = sg.seed_and_run_graph_p3(pf.token_id, n_prompt, gen)
                var bw1 = perf_counter_ns()
                _check_resident(st, "bench seed_and_run_graph_p3")
                if r >= WARMUP:
                    gp_ms.append(_ms(bw1 - bw0))
            var gp_stats = _cell_stats(gp_ms)
            var gp_toks = Float64(gen) / (gp_stats.median / 1000.0)

            # ── f32-graph cell (the composed session's inner f32 session's graph arm) ──
            var fg_ms = List[Float64]()
            for r in range(WARMUP + runs):
                var pf = sg.p3.f32.prefill(_copy_ids(race_ids))
                _check_resident(pf.status, "bench f32-graph prefill")
                var bw0 = perf_counter_ns()
                var st = sg.p3.f32.seed_and_run_graph(pf.token_id, n_prompt, gen)
                var bw1 = perf_counter_ns()
                _check_resident(st, "bench f32 seed_and_run_graph")
                if r >= WARMUP:
                    fg_ms.append(_ms(bw1 - bw0))
            var fg_stats = _cell_stats(fg_ms)
            var fg_toks = Float64(gen) / (fg_stats.median / 1000.0)

            # ── per-dispatch-p3 cell (the #800 arm this one replaces) ──
            var pd_ms = List[Float64]()
            for r in range(WARMUP + runs):
                var pf = sg.prefill(_copy_ids(race_ids))
                _check_resident(pf.status, "bench per-dispatch prefill")
                var last = pf.token_id
                var bw0 = perf_counter_ns()
                for step in range(gen):
                    var rstep = sg.step_p3(last, n_prompt + step)
                    _check_resident(rstep.status, "bench step_p3")
                    last = rstep.token_id
                var bw1 = perf_counter_ns()
                if r >= WARMUP:
                    pd_ms.append(_ms(bw1 - bw0))
            var pd_stats = _cell_stats(pd_ms)
            var pd_toks = Float64(gen) / (pd_stats.median / 1000.0)

            var q8_ref = LEDGER_Q8_0_GEN64 if gen == 64 else LEDGER_Q8_0_GEN256
            var f16_ref = LEDGER_F16_GEN64 if gen == 64 else LEDGER_F16_GEN256

            print("  gen", gen, " graph-p3       : median", gp_stats.median, "ms | rel IQR",
                  gp_stats.rel_iqr * 100.0, "% | outliers", gp_stats.n_outliers, "|",
                  gp_toks, "tok/s",
                  "(" + ("PASS" if gp_stats.passes else "FLAGGED") + ", frozen 5%)")
            print("  gen", gen, " f32-graph      : median", fg_stats.median, "ms | rel IQR",
                  fg_stats.rel_iqr * 100.0, "% | outliers", fg_stats.n_outliers, "|",
                  fg_toks, "tok/s",
                  "(" + ("PASS" if fg_stats.passes else "FLAGGED") + ", frozen 5%)")
            print("  gen", gen, " per-dispatch-p3: median", pd_stats.median, "ms | rel IQR",
                  pd_stats.rel_iqr * 100.0, "% | outliers", pd_stats.n_outliers, "|",
                  pd_toks, "tok/s",
                  "(" + ("PASS" if pd_stats.passes else "FLAGGED") + ", frozen 5%)")
            print("  gen", gen, " graph-p3 vs ledger: ", gp_toks / q8_ref, "x llama.cpp Q8_0 (",
                  q8_ref, "tok/s ) |", gp_toks / f16_ref, "x llama.cpp F16 (", f16_ref, "tok/s )")
            print("  gen", gen, " f32-graph vs ledger:", fg_toks / q8_ref, "x Q8_0 |",
                  fg_toks / f16_ref, "x F16 | graph-p3 / f32-graph:", gp_toks / fg_toks)

        print("")
        print("qwen3_p3_graph_cuda: done (G0 + G1 + G2 all PASS)")
        exit(0)
