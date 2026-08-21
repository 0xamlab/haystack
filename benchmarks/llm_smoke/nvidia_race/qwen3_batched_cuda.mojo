"""qwen3_batched_cuda.mojo — W1 of the campaign gap inventory: CONTINUOUS-BATCHING (B-sequence)
DECODE on the CUDA lane, benched against the single-stream CUDA session for both CORRECTNESS and
aggregate throughput. Drives `residentk.session_cuda_batched._CudaResidentQwen3Batched` (the
per-dispatch arm; the graph arm is W2) plus `residentk.session_cuda._CudaResidentQwen3` as the
single-stream reference oracle. Same `/tmp/qwen3smoke/{manifest.json,weights.blob}` checkpoint
dump every other CUDA arm reads (argv[1] overrides the directory), same 256-token race prompt
(read from the manifest's own `input_ids`, never restated here).

Correctness gate (FIRST, before any throughput number is printed)
------------------------------------------------------------------
Every sequence's greedy token stream through the BATCHED session must be IDENTICAL, token for
token, to the single-stream session's decode of the SAME prompt:

  * uniform cells B in {1, 4, 8, 16, 32}: all B sequences run the 256-token race prompt; each
    sequence's first-token (batched prefill tail) + N_NEW decoded tokens are diffed against ONE
    single-stream prefill+decode of the same prompt.
  * ragged cell B=4 (the nkeys ragged contract): prompt prefixes of length 256/192/128/64; each
    sequence is diffed against its OWN single-stream decode of its own prefix — this exercises
    per-sequence `nkeys[b]` divergence mid-batch, the one thing uniform cells cannot.

Any mismatch prints FAIL and exits nonzero. This gate subsumes the campaign oracle: the
single-stream session is itself oracle-checked against the campaign's known-correct continuation
(the 8-id window + 7-id repeat cycle), so batched == single-stream == oracle.

Throughput cells (after the gate passes)
----------------------------------------
Per B in {1, 4, 8, 16, 32}: WARMUP untimed runs, then RUNS (default 20) timed runs; each run
re-prefills B prompts (untimed — decode-only discipline, exactly `qwen3_generate_cuda`'s own)
and times ONLY the `seed_and_run_batched` decode chain. Reported per cell:
  * aggregate tok/s = B * N_NEW / decode-wall, per run
  * per-seq tok/s   = N_NEW / decode-wall (aggregate / B)
  * median + rel-IQR = (p75-p25)/median over the runs, the campaign's 20-run median discipline
    (REALRACE_RESULTS.md "End-to-end race harness, DVFS-corrected protocol": 20 runs/cell,
    median, rel-IQR tolerance <= 5%, runs deviating >10% from the median excluded and the
    median/IQR recomputed — both the raw and the outlier-excluded numbers are printed).

Build (the CUDA lane recipe, no CUDA toolkit at build time — setup_vm.sh stage 7's pattern; the
ONLY deltas from the other CUDA drivers are the second -I path for the new attention_forge
modules and this file's own source path):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \\
        -I mojo/engine -I attention_forge \\
        benchmarks/llm_smoke/nvidia_race/qwen3_batched_cuda.mojo \\
        -o qwen3_batched_cuda

    # if the pinned toolchain does not auto-link the MAX CUDA runtime (setup_vm.sh's fallback):
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \\
        -I mojo/engine -I attention_forge \\
        benchmarks/llm_smoke/nvidia_race/qwen3_batched_cuda.mojo \\
        --emit object -o qwen3_batched_cuda.o
    clang qwen3_batched_cuda.o -o qwen3_batched_cuda -L <max-lib> -Wl,-rpath,<max-lib> \\
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \\
        -lAsyncRTMojoBindings -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm

--target-accelerator follows the VM's GPU: sm_80 A100 / sm_89 L4 / sm_75 T4.

Usage (VM command):

    ./qwen3_batched_cuda /tmp/qwen3smoke                 # 20 runs/cell, N_NEW=128
    ./qwen3_batched_cuda /tmp/qwen3smoke --runs 5 --n-new 64
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
    _CudaResidentQwen3Batched,
)

comptime DEFAULT_CHECKPOINT_DIR: String = "/tmp/qwen3smoke"
comptime MAX_CTX: Int = 1024
"""Room for the 256-token race prompt + the decode tail at every B the cells run. The batched KV
is B_MAX x max_ctx per layer per K/V (7.5 GB at B=32, max_ctx=1024 for Qwen3-0.6B), so the
default stays conservative; A100/L4 both hold it with the reference session alongside."""

comptime N_NEW_DEFAULT: Int = 128
comptime RUNS_DEFAULT: Int = 20
comptime WARMUP_DEFAULT: Int = 2
comptime EOS_TOKEN_ID: Int = 151643

comptime ORACLE_WINDOW: Int = 8
"""The campaign's known-correct greedy window for the 256-token race prompt on Qwen3-0.6B-Base —
the single-stream reference is oracle-checked against it before the batched diff runs."""


def _oracle_token(i: Int) -> Int:
    """`i`-th expected generated token: the 8-token window, then the 7-token repeat cycle the
    model settles into on this prompt — byte-for-byte the function `qwen3_generate_cuda.mojo`
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
            "qwen3_batched_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_batched_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_batched_cuda: short read at byte offset " + String(byte_offset))
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
        raise Error("qwen3_batched_cuda: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = MAX_CTX
    if n_prompt + n_new > max_ctx:
        raise Error(
            "qwen3_batched_cuda: prompt (" + String(n_prompt) + ") + n_new (" + String(n_new)
            + ") exceeds MAX_CTX (" + String(max_ctx) + ")"
        )

    print("qwen3_batched_cuda: checkpoint =", ckpt_dir)
    print("  d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q, "h_kv=", h_kv,
          "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size, "n_prompt=", n_prompt)
    print("  max_ctx=", max_ctx, "B_max=", _CUDA_BATCH_DECODE_MAX_SEQS,
          "n_splits=", CUDA_BATCH_N_SPLITS, "n_new=", n_new, "runs=", runs,
          "warmup=", warmup)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, n_new, max_ctx, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_batched_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time
        # gate is visible at this file's only construction site.
        print("qwen3_batched_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_batched_cuda: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for k in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[k]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_batched_cuda: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var rt = rope_table(d_head, max_ctx, theta)
        if rt.status != ATTN_OK:
            raise Error("qwen3_batched_cuda: rope_table failed")

        # ═══ ONE-TIME: open BOTH sessions, convert every weight to Float32, upload ═══
        var bs = _CudaResidentQwen3Batched(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        print("  device:", bs.device_name())
        var ss = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )

        var t_read0 = perf_counter_ns()
        var embed_table = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(ckpt_dir + "/weights.blob", tensors_obj, "model.norm.weight")
        _check_resident(
            bs.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx),
            "batched upload_globals",
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
                bs.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "batched upload_layer " + String(layer),
            )
            _check_resident(
                ss.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "single-stream upload_layer " + String(layer),
            )
        _check_resident(bs.seal(), "batched seal")
        _check_resident(ss.seal(), "single-stream seal")
        var t_read1 = perf_counter_ns()
        print("  one-time weight load (both sessions):", _ms(t_read1 - t_read0), "ms")

        # ═══ CORRECTNESS GATE 0: the single-stream reference is itself oracle-checked ═══
        var ref_full = _single_stream_generate(ss, prompt_ids, n_new)
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

        # ═══ CORRECTNESS GATE 1: uniform B — every seq == the single-stream stream ═══
        var bs_list = List[Int]()
        bs_list.append(1)
        bs_list.append(4)
        bs_list.append(8)
        bs_list.append(16)
        bs_list.append(32)
        for bi in range(len(bs_list)):
            var B = bs_list[bi]
            var prompts = List[List[Int]]()
            for _ in range(B):
                var p = List[Int](capacity=n_prompt)
                for k in range(n_prompt):
                    p.append(prompt_ids[k])
                prompts.append(p^)

            var firsts = bs.prefill_batched(prompts)
            var gate_ok = len(firsts) == B
            var first_mismatch = 0
            if gate_ok:
                for b in range(B):
                    if firsts[b] != ref_full[0]:
                        first_mismatch += 1
                        gate_ok = False
            if gate_ok:
                var poss = List[Int]()
                for _ in range(B):
                    poss.append(n_prompt)
                var st = bs.seed_and_run_batched(firsts, poss, n_new)
                _check_resident(st, "seed_and_run_batched B=" + String(B))
                for b in range(B):
                    for step in range(n_new):
                        if bs.batched_token(b, step) != ref_full[step + 1]:
                            gate_ok = False
                            break

            if gate_ok:
                print("  gate 1 B=", B, ": PASS —", B, " sequences x", n_new + 1,
                      "tokens identical to the single-stream decode")
            else:
                print("  gate 1 B=", B, ": FAIL — batched stream diverged from the",
                      "single-stream decode (first-token mismatches:", first_mismatch, ")")
                all_pass = False

        # ═══ CORRECTNESS GATE 2: ragged B=4 — divergent per-seq prompt lengths ═══
        var ragged_lens = List[Int]()
        ragged_lens.append(n_prompt)
        ragged_lens.append(n_prompt * 3 // 4)
        ragged_lens.append(n_prompt // 2)
        ragged_lens.append(n_prompt // 4)
        var BR = 4
        var ragged_prompts = List[List[Int]]()
        var ragged_refs = List[List[Int]]()
        for b in range(BR):
            var L = ragged_lens[b]
            var p = List[Int](capacity=L)
            for k in range(L):
                p.append(prompt_ids[k])
            # The reference for THIS prefix is generated from its OWN prompt list (the borrow
            # below keeps `p` alive for the batched side too).
            ragged_refs.append(_single_stream_generate(ss, p, n_new))
            ragged_prompts.append(p^)

        var ragged_firsts = bs.prefill_batched(ragged_prompts)
        var ragged_ok = len(ragged_firsts) == BR
        if ragged_ok:
            for b in range(BR):
                if ragged_firsts[b] != ragged_refs[b][0]:
                    ragged_ok = False
        if ragged_ok:
            var ragged_poss = List[Int]()
            for b in range(BR):
                ragged_poss.append(ragged_lens[b])
            var st = bs.seed_and_run_batched(ragged_firsts, ragged_poss, n_new)
            _check_resident(st, "seed_and_run_batched ragged")
            for b in range(BR):
                for step in range(n_new):
                    if bs.batched_token(b, step) != ragged_refs[b][step + 1]:
                        ragged_ok = False
                        break
        if ragged_ok:
            print("  gate 2 ragged B=", BR, " (lens ", ragged_lens[0], "/", ragged_lens[1],
                  "/", ragged_lens[2], "/", ragged_lens[3], "): PASS —", n_new + 1,
                  "tokens per sequence identical to each own single-stream decode")
        else:
            print("  gate 2 ragged B=", BR, ": FAIL — batched stream diverged")
            all_pass = False

        if not all_pass:
            print("RESULT: FAIL — correctness gate failed; no throughput numbers published")
            exit(1)
        print("RESULT: PASS — correctness gate (every B, uniform + ragged)")

        # ═══ THROUGHPUT CELLS ═══
        print("")
        print("Throughput (decode-only; prefill excluded from the timed window):")
        print("  dispatches per B-token step: 1 + n_layers*9 + 3 =",
              bs.batched_dispatch_count(1))
        for bi in range(len(bs_list)):
            var B = bs_list[bi]
            var prompts = List[List[Int]]()
            for _ in range(B):
                var p = List[Int](capacity=n_prompt)
                for k in range(n_prompt):
                    p.append(prompt_ids[k])
                prompts.append(p^)

            var run_tps = List[Float64]()
            var total_runs = warmup + runs
            for r in range(total_runs):
                var firsts = bs.prefill_batched(prompts)
                if len(firsts) != B:
                    raise Error("qwen3_batched_cuda: prefill_batched failed in the bench loop")
                if firsts[B - 1] == EOS_TOKEN_ID:
                    raise Error("qwen3_batched_cuda: prompt prefill hit EOS — bench invalid")
                var poss = List[Int]()
                for _ in range(B):
                    poss.append(n_prompt)
                var t0 = perf_counter_ns()
                var st = bs.seed_and_run_batched(firsts, poss, n_new)
                var t1 = perf_counter_ns()
                _check_resident(st, "bench seed_and_run_batched")
                if r >= warmup:
                    var wall_s = Float64(t1 - t0) / 1.0e9
                    run_tps.append(Float64(B * n_new) / wall_s)

            var stats = _cell_stats(run_tps)
            var per_seq_med = stats.median_clean / Float64(B)
            print("  B=", B, ": aggregate ", stats.median_clean, " tok/s (per-seq ",
                  per_seq_med, " tok/s) | median ", stats.median, " rel-IQR ",
                  stats.rel_iqr * 100.0, "% | clean rel-IQR ", stats.rel_iqr_clean * 100.0,
                  "% | outliers(>10%) ", stats.n_outliers, "/", len(run_tps),
                  " | verdict ",
                  "PASS(<=5%)" if stats.rel_iqr_clean <= 0.05 else "FLAG(>5%)")

        print("")
        print("qwen3_batched_cuda: done.")
        exit(0)
