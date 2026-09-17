"""qwen25_7b_p3_graph_cuda.mojo — the 7B-LANE single-stream gate+race driver: Qwen2.5-7B-Instruct
through the resident CUDA sessions with the 7B enablement (2026-08-22) switched ON:

  * qk_norm = 0            — Qwen2.5 has NO per-head QK-norm (llama-family ropewrt branch)
  * has_lm_head = 1        — separate lm_head table (tie_word_embeddings=false), bound by both
                             the f32 and packed3 lm_head+argmax dispatches
  * skip_f32_projections   — the packed3 arm residents ONLY packed3 projections + f32
                             embed/lm_head (a 7B's f32+packed3 dual residency exceeds the
                             A100-40GB; prefill runs the JIT-dequant seam, decode the packed3
                             chain — `residentk.session_cuda_p3`'s docstrings state the split)
  * -D ALGENTA_STAGE_18944 — the resident staging tier for d_ff = 18944

TWO ARMS, ONE BINARY, SEPARATE PROCESSES (a 7B does not fit two weight sets at once):
  --arm f32      the full-f32 reference session (~30.5 GB resident): greedy reference stream
                 for the packed3-vs-f32 flip report + its own self-consistency.
  --arm p3       the packed3 graph session (JIT-dequant prefill + captured-graph decode).

GATES (the campaign brief's, mapped):
  G0  16/16 greedy tokens on the fixture vs the --oracle ids (bootstrapped from the llama.cpp
      cross-engine gate; the driver refuses to score G0 without an oracle — no silent pass).
  G1  self-consistency: prefill + decode the fixture TWICE, every token identical (the brief's
      16/16 self-consistency, extended over the whole comparison window).
  G2  packed3-vs-f32 flip report: `--compare <file>` diffs this arm's dumped token stream
      against the other arm's (honest flip counting, near-tie argmax flips reported, not
      hidden). `--dump <file>` writes the stream.

MEASURE (20-run medians, rel-IQR <= 5%, outliers >10% flagged — the frozen discipline):
  prefill256   the 256-token fixture through prefill (JIT-dequant included for the p3 arm)
  gen64        prefill + 64-token captured-graph decode window
  gen256       prefill + 256-token captured-graph decode window

FRONT 7 ARGUMENTS (2026-09-16, both default to the rounds-2-to-6 behaviour):
  --warmup N     warmup prefills before the timed loop (default WARMUP = 1). Raising it cannot
                 move a median; it exists because the in-situ algorithm search below collects one
                 sample per shape per layer per prefill and needs more than one prefill to do it.
  --lt-insitu N  arm the in-situ cublasLt search for N samples per candidate, in a build with
                 -D ALGENTA_7B_PF_LTINSITU. PLACEMENT IS THE WHOLE DESIGN: the search is armed
                 after G0/G1/G2 and the dump, so the token gates cover FRONT 6's stage-time
                 selection rather than a rotating mixture, and it is frozen before the timed loop,
                 so no measured sample can be taken while algorithms are still rotating and the
                 measured runs carry zero event overhead. The shim prints the full per-candidate
                 table (isolated stage-time mean beside in-situ median, selected one marked),
                 which is the deliverable whether or not the two rankings agree. A RACED arm pins
                 the searched set with ALGENTA_LT_PICK at tune time instead, so the selection it
                 runs is one the gates cover normally.

Usage (A100, sm_80, GPU-idle):
  qwen25_7b_p3_graph_cuda --checkpoint /tmp/w7b/ckpt --arm f32 --dump /tmp/w7b/f32_tokens.txt \
      --oracle <ids> --out /tmp/w7b/f32_bench.txt
  qwen25_7b_p3_graph_cuda --checkpoint /tmp/w7b/ckpt --arm p3 --dump /tmp/w7b/p3_tokens.txt \
      --oracle <ids> --compare /tmp/w7b/f32_tokens.txt --out /tmp/w7b/p3_bench.txt
"""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator, is_defined
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
from residentk.session_cuda_p3_graph import _CudaResidentQwen3P3Graph
from residentk.tc_shim_bridge import (
    _tc_lt_explore_begin,
    _tc_lt_freeze,
    _tc_lt_insitu_state,
)

comptime MAX_CTX: Int = 8192 if is_defined["ALGENTA_7B_CTX8192"]() else 1600
"""The 256-token fixture + the gen256 tail (256 + 256 = 512) with headroom, PLUS the pp1024
measurement cell (a 1024-token prefill prompt + its gen tail must fit: 1024 + 256 = 1280).

`-D ALGENTA_7B_CTX8192` (DEFAULT OFF) raises this to 8192 — the long-context arm that makes
the RAG-4096 cell runnable at all: at 1600 the driver's own `--prompt-ids` guard
(`len > MAX_CTX - 256`) refuses any prompt over 1344 tokens, so a 4096-token RAG prompt has
no legal path through this driver. The context length is a DRIVER constant, not a session
one: `max_ctx` reaches `_CudaResidentQwen3P3Graph` (and through it the f32 KV cache, the
RoPE table and the TC attention scratch, all sized off it) as a plain constructor argument,
so the flag changes sizing only — no kernel and no dispatch path is conditional on it. Cost
at the 7B shapes: the f32 KV cache grows 0.18 -> 0.94 GB and the TC attention scratch
(`[h_q, rows, max_ctx]` scores f32 + P f16) 0.28 -> 1.41 GB, inside the same VRAM headroom
try the dual residency already rides — a device that cannot hold it demotes to the native
chain exactly as before, it does not fail."""

comptime G0_TOKENS: Int = 16
comptime G1_STEPS: Int = 64
comptime G2_STEPS: Int = 128
comptime N_RUNS: Int = 20
comptime WARMUP: Int = 1
comptime IQR_TOLERANCE: Float64 = 0.05
comptime OUTLIER_DEVIATION: Float64 = 0.10

comptime _LONG_TARGET: Int = 1024
"""Target prompt length of the long-prefill cell. The cell repeats the fixture
`_LONG_TARGET // n_prompt` times (4x for the 256-token fixture = the historical
"prefill1024" cell) and is skipped when that quotient is 1, i.e. when the prompt already
meets or exceeds the target -- so a `--prompt-ids` RAG run measures its own length once in
the primary cell instead of repeating itself past MAX_CTX."""


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen25_7b: " + ctx + " failed, status=" + String(status)
            + " (" + residentk_status_name(status) + ")"
        )


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


def _write_text_file(path: String, text: String) raises:
    var f = open(path, "w")
    f.write_bytes(text.as_bytes())
    f.close()


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen25_7b: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen25_7b: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _copy_ids(ref ids: List[Int]) raises -> List[Int]:
    var out = List[Int](capacity=len(ids))
    for i in range(len(ids)):
        out.append(ids[i])
    return out^


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _sort_ascending(mut xs: List[Float64]):
    for i in range(1, len(xs)):
        var v = xs[i]
        var j = i - 1
        while j >= 0 and xs[j] > v:
            xs[j + 1] = xs[j]
            j -= 1
        xs[j + 1] = v


def _percentile(sorted_xs: List[Float64], q: Float64) -> Float64:
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


def _parse_ids_csv(text: String) raises -> List[Int]:
    """Parse a token-id list out of a comma- and/or newline-separated string (the --oracle
    spelling and the dump's own one-id-per-line format, both accepted)."""
    var out = List[Int]()
    var lines = text.split("\n")
    for li in range(len(lines)):
        var fields = lines[li].split(",")
        for fi in range(len(fields)):
            var tok = fields[fi].strip()
            if tok.byte_length() > 0:
                out.append(parse_int(String(tok)))
    return out^


def main() raises:
    var args = argv()
    var ckpt_dir = String("/tmp/w7b/ckpt")
    var arm = String("p3")
    var runs = N_RUNS
    var gen_only = 0
    var oracle = List[Int]()
    var prompt_override = List[Int]()
    var dump_path = String()
    var compare_path = String()
    var out_path = String()
    var warmup = WARMUP
    var lt_insitu = 0
    var i = 1
    while i < len(args):
        var a = String(args[i])
        if a == "--checkpoint" and i + 1 < len(args):
            ckpt_dir = String(args[i + 1])
            i += 2
        elif a == "--arm" and i + 1 < len(args):
            arm = String(args[i + 1])
            i += 2
        elif a == "--runs" and i + 1 < len(args):
            runs = parse_int(args[i + 1])
            i += 2
        elif a == "--gen-only" and i + 1 < len(args):
            gen_only = parse_int(args[i + 1])
            i += 2
        elif a == "--oracle" and i + 1 < len(args):
            oracle = _parse_ids_csv(String(args[i + 1]))
            i += 2
        elif a == "--prompt-ids" and i + 1 < len(args):
            prompt_override = _parse_ids_csv(String(args[i + 1]))
            i += 2
        elif a == "--dump" and i + 1 < len(args):
            dump_path = String(args[i + 1])
            i += 2
        elif a == "--compare" and i + 1 < len(args):
            compare_path = String(args[i + 1])
            i += 2
        elif a == "--out" and i + 1 < len(args):
            out_path = String(args[i + 1])
            i += 2
        elif a == "--warmup" and i + 1 < len(args):
            # FRONT 7: warmup prefills before the timed loop. Defaults to WARMUP (1), so every
            # arm that does not pass it runs the rounds-2-to-6 protocol unchanged. The in-situ
            # cublasLt search needs MORE than one, because it collects one sample per shape per
            # layer per prefill: 28 samples per prefill against ~16 executable heuristics, so
            # `--lt-insitu 8` needs ~5 prefills. Raising warmup can only make a measured median
            # steadier; it is not a knob on the result, and the harness records it per cell.
            warmup = parse_int(args[i + 1])
            i += 2
        elif a == "--lt-insitu" and i + 1 < len(args):
            # FRONT 7 lever 3: samples per candidate the in-situ cublasLt search collects before
            # each shape freezes on its best in-situ median. 0 (the default) leaves the search
            # disarmed and the arm runs FRONT 6's stage-time selection. Only meaningful in a
            # build with -D ALGENTA_7B_PF_LTINSITU; without that flag the shim has no search to
            # arm and the driver says so instead of silently doing nothing.
            lt_insitu = parse_int(args[i + 1])
            i += 2
        else:
            raise Error("qwen25_7b: unknown argument: " + a)

    var is_p3 = arm == "p3"

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
    var has_qk_norm = json_get_int(config, "has_qk_norm", 1)
    var tied = json_get_int(config, "tie_word_embeddings", 1)
    var has_qkv_bias = json_get_int(config, "attention_bias", 0)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1 or n_prompt < 1:
        raise Error("qwen25_7b: manifest config did not parse")
    if has_qk_norm != 0:
        raise Error("qwen25_7b: this driver is the no-QK-norm 7B lane; manifest has_qk_norm=1")
    if tied != 0:
        raise Error("qwen25_7b: this driver expects an untied lm_head; manifest tied=1")
    if has_qkv_bias != 1:
        raise Error(
            "qwen25_7b: this driver expects a bias-carrying Qwen2.5 checkpoint "
            "(manifest attention_bias=1) — the pre-2026-08-23 converter silently dropped "
            "the q/k/v biases; re-run prepare_qwen25_7b_checkpoint.py with the fixed one"
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen25_7b: arm =", arm, "| checkpoint =", ckpt_dir, "| d_model =", d_model,
          "| n_layers =", n_layers, "| h_q =", h_q, "| h_kv =", h_kv, "| d_head =", d_head,
          "| d_ff =", d_ff, "| vocab =", vocab_size, "| theta =", theta,
          "| n_prompt =", n_prompt, "| max_ctx =", MAX_CTX)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 256, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen25_7b: cannot run a resident session here:", residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_18944",
              "--target-accelerator sm_80, on a host with an NVIDIA device)")
        exit(1)

    @parameter
    if not CUDA_SESSION_BUILD:
        print("qwen25_7b: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen25_7b: no accelerator on this host")
            exit(1)

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var race_ids = List[Int]()
        for k in range(len(id_tokens)):
            race_ids.append(parse_int(id_tokens[k]))
        if len(race_ids) != n_prompt:
            raise Error("qwen25_7b: input_ids length does not match config.n_tokens")
        # Cross-engine gate hook: --prompt-ids overrides the manifest fixture so the 5 chat
        # prompts (tokenized once, shared with llama.cpp / vLLM) can be run through this arm.
        if len(prompt_override) > 0:
            if len(prompt_override) > MAX_CTX - 256:
                raise Error("qwen25_7b: --prompt-ids too long for MAX_CTX and a 256 tail")
            race_ids = prompt_override^
            n_prompt = len(race_ids)
            print("  --prompt-ids override:", n_prompt, "prompt tokens")

        var tensors_obj = json_get_object(manifest, "tensors")
        var blob_path = ckpt_dir + "/weights.blob"
        var rt = rope_table(d_head, MAX_CTX, theta)
        if rt.status != ATTN_OK:
            raise Error("qwen25_7b: rope_table failed")

        var report = String("qwen25_7b arm=") + arm + "\n"

        if is_p3:
            # ════════════════════ the packed3 graph arm ════════════════════
            var t0 = perf_counter_ns()
            var sg = _CudaResidentQwen3P3Graph(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX,
                eps, scale, 0, 1, 1, has_qkv_bias,
                # qk_norm=0, has_lm_head=1, skip_f32_projections=1, has_qkv_bias
            )
            print("  device:", sg.device_name())
            print("  packed3 kernels:", sg.graph_kernel_variant())

            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
            var lm_head_w = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
            var empty = List[Float64]()
            _check_resident(
                sg.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
                "upload_globals",
            )
            _check_resident(sg.upload_lm_head(lm_head_w), "upload_lm_head")
            for layer in range(n_layers):
                var pfx = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, pfx + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, pfx + "post_attention_layernorm.weight"
                )
                var wq = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, pfx + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, pfx + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, pfx + "mlp.down_proj.weight")
                _check_resident(
                    sg.upload_layer(layer, ln1, ln2, empty, empty, wq, wk, wv, wo, wg, wu, wd),
                    "upload_layer " + String(layer),
                )
                # 7B-lane attention bias: the q/k/v projection biases, packed [Q|K|V].
                var qb = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.q_proj.bias")
                var kb = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.k_proj.bias")
                var vb = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.v_proj.bias")
                _check_resident(
                    sg.upload_qkv_bias(layer, qb, kb, vb),
                    "upload_qkv_bias " + String(layer),
                )
            _check_resident(sg.seal(), "seal")
            var t1 = perf_counter_ns()
            print("  one-time load (packed3 + f32 embed/lm_head):", _ms(t1 - t0), "ms")

            # ── fast cross-engine gate mode: prefill + generate + dump, skip gates/bench ──
            if gen_only > 0:
                var ds = List[Int]()
                var pg = sg.prefill(_copy_ids(race_ids))
                _check_resident(pg.status, "gen_only prefill")
                ds.append(pg.token_id)
                if gen_only > 1:
                    _check_resident(
                        sg.seed_and_run_graph_p3(pg.token_id, n_prompt, gen_only - 1),
                        "gen_only seed_and_run_graph_p3",
                    )
                    for k in range(1, gen_only):
                        ds.append(sg.graph_token(n_prompt + k - 1))
                var txt = String()
                for k in range(len(ds)):
                    txt = txt + String(ds[k]) + "\n"
                if dump_path.byte_length() > 0:
                    _write_text_file(dump_path, txt)
                    print("  gen_only wrote", len(ds), "tokens to", dump_path)
                else:
                    print(txt)
                print("GEN_ONLY DONE:", len(ds), "tokens")
                return

            # ── G0 — 16/16 greedy oracle through the graph arm ──
            var g0_stream = List[Int]()
            var pf0 = sg.prefill(_copy_ids(race_ids))
            _check_resident(pf0.status, "G0 prefill")
            g0_stream.append(pf0.token_id)
            if len(oracle) >= 1:
                # FRONT 6: compare min(len(oracle), G0_TOKENS) tokens, not a fixed 16. The old
                # `len(oracle) >= G0_TOKENS` guard made a SHORT oracle silently skip G0, and
                # every long-prompt oracle is short: the three RAG-4096 prompts answer in four
                # tokens and then emit the EOS token, so a 16-token reference can only be had by
                # forcing the fp32 decoder past its own natural stop -- and post-EOS continuation
                # is undefined behaviour for a chat model, so it is not a gate on anything.
                var ncmp = len(oracle)
                if ncmp > G0_TOKENS:
                    ncmp = G0_TOKENS
                _check_resident(
                    sg.seed_and_run_graph_p3(pf0.token_id, n_prompt, G0_TOKENS - 1),
                    "G0 seed_and_run_graph_p3",
                )
                for k in range(1, G0_TOKENS):
                    g0_stream.append(sg.graph_token(n_prompt + k - 1))
                var g0_mismatch = 0
                for k in range(ncmp):
                    if g0_stream[k] != oracle[k]:
                        g0_mismatch += 1
                        print("  ORACLE MISMATCH at token", k, ": got", g0_stream[k],
                              "want", oracle[k])
                if g0_mismatch > 0:
                    print("G0 RESULT: FAIL —", g0_mismatch, "mismatched of", ncmp, "compared")
                    exit(1)
                print("G0 RESULT: PASS —", ncmp, "/", ncmp,
                      "greedy tokens match the oracle (oracle length", len(oracle), ")")
                report = report + "G0 PASS " + String(ncmp) + "/" + String(ncmp) + "\n"
            else:
                print("G0 SKIPPED: no --oracle ids supplied (bootstrap from the llama.cpp gate)")
                report = report + "G0 SKIPPED (no oracle)\n"

            # ── G1 — self-consistency: the fixture twice, every token identical ──
            var s1 = List[Int]()
            var s2 = List[Int]()
            var pa = sg.prefill(_copy_ids(race_ids))
            _check_resident(pa.status, "G1 prefill run-a")
            s1.append(pa.token_id)
            _check_resident(
                sg.seed_and_run_graph_p3(pa.token_id, n_prompt, G1_STEPS - 1), "G1 run-a"
            )
            for k in range(1, G1_STEPS):
                s1.append(sg.graph_token(n_prompt + k - 1))
            var pb = sg.prefill(_copy_ids(race_ids))
            _check_resident(pb.status, "G1 prefill run-b")
            s2.append(pb.token_id)
            _check_resident(
                sg.seed_and_run_graph_p3(pb.token_id, n_prompt, G1_STEPS - 1), "G1 run-b"
            )
            for k in range(1, G1_STEPS):
                s2.append(sg.graph_token(n_prompt + k - 1))
            var g1_mismatch = 0
            for k in range(G1_STEPS):
                if s1[k] != s2[k]:
                    g1_mismatch += 1
            if g1_mismatch > 0:
                print("G1 RESULT: FAIL —", g1_mismatch, "self-consistency mismatches")
                exit(1)
            print("G1 RESULT: PASS —", G1_STEPS, "/", G1_STEPS,
                  "tokens identical across two runs")
            report = report + "G1 PASS " + String(G1_STEPS) + "/" + String(G1_STEPS) + "\n"

            # ── G2 — flip report vs the f32 arm's dumped stream ──
            if compare_path.byte_length() > 0:
                var other = _parse_ids_csv(_read_text_file(compare_path))
                var n_cmp = len(other)
                if len(s1) < n_cmp:
                    n_cmp = len(s1)
                var flips = 0
                var first_flip = -1
                for k in range(n_cmp):
                    if s1[k] != other[k]:
                        flips += 1
                        if first_flip < 0:
                            first_flip = k
                print("G2 flip report:", flips, "flips in", n_cmp, "tokens vs", compare_path,
                      "(first flip at", first_flip, ")")
                report = report + "G2 flips=" + String(flips) + "/" + String(n_cmp) + "\n"

            # ── dump this arm's stream for the other arm's G2 ──
            if dump_path.byte_length() > 0:
                var ds = List[Int]()
                var pd = sg.prefill(_copy_ids(race_ids))
                _check_resident(pd.status, "dump prefill")
                ds.append(pd.token_id)
                _check_resident(
                    sg.seed_and_run_graph_p3(pd.token_id, n_prompt, G2_STEPS - 1), "dump"
                )
                for k in range(1, G2_STEPS):
                    ds.append(sg.graph_token(n_prompt + k - 1))
                var txt = String()
                for k in range(len(ds)):
                    txt = txt + String(ds[k]) + "\n"
                _write_text_file(dump_path, txt)
                print("  dumped", len(ds), "tokens to", dump_path)

            # ── MEASURE: prefill256 / gen64 / gen256 ──
            # FRONT 7 lever 3 (-D ALGENTA_7B_PF_LTINSITU + --lt-insitu N): the in-situ cublasLt
            # search is armed HERE and frozen BELOW. Both placements are load-bearing:
            #   * armed AFTER G0/G1/G2 and the dump, so what the token gates cover is FRONT 6's
            #     stage-time selection — the search rotates algorithms while it explores, and a
            #     gate that ran during exploration would be gating a mixture;
            #   * frozen BEFORE the timed loop, so no measured sample can be taken while
            #     algorithms are still rotating and every one of the `runs` samples runs one
            #     fixed algorithm per shape with zero event overhead.
            # The shim prints the full per-candidate table at freeze time (isolated mean beside
            # in-situ median, selected one marked), which is the deliverable whether or not the
            # in-situ winner differs from the isolated one.
            # A runtime `if` wraps the comptime one: `@parameter if` cannot carry a dynamic
            # `elif`, and whether the search is armed is a runtime argument.
            if lt_insitu > 0:
                @parameter
                if is_defined["ALGENTA_7B_PF_LTINSITU"]():
                    print("LT INSITU: arming the in-situ search |", lt_insitu,
                          "samples per candidate |", warmup,
                          "warmup prefills to collect them | shapes armed =",
                          _tc_lt_explore_begin(lt_insitu))
                else:
                    print("LT INSITU: --lt-insitu", lt_insitu, "IGNORED — this binary was built"
                          " without -D ALGENTA_7B_PF_LTINSITU, so there is no search to arm")

            for _ in range(warmup):
                var warm = sg.prefill(_copy_ids(race_ids))
                _check_resident(warm.status, "warmup prefill")

            if lt_insitu > 0:
                @parameter
                if is_defined["ALGENTA_7B_PF_LTINSITU"]():
                    var nfrozen = _tc_lt_freeze()
                    print("LT INSITU: FROZEN", nfrozen, "shapes | state =",
                          _tc_lt_insitu_state(), "(2 = frozen; anything else means a measured"
                          " sample below could rotate algorithms and the cell is VOID)")
                    if nfrozen < 4:
                        print("LT INSITU: PARTIAL — only", nfrozen,
                              "of 4 shapes froze on an in-situ winner; the rest keep FRONT 6's"
                              " stage-time selection, so this arm is a mix and says so")

            var pf_samples = List[Float64]()
            for r in range(runs):
                var a0 = perf_counter_ns()
                var pfm = sg.prefill(_copy_ids(race_ids))
                _check_resident(pfm.status, "bench prefill")
                var a1 = perf_counter_ns()
                pf_samples.append(Float64(n_prompt) / (_ms(a1 - a0) / 1000.0))
            var pf_stats = _cell_stats(pf_samples)
            print("prefill" + String(n_prompt) + ": median", pf_stats.median, "tok/s | IQR",
                  pf_stats.rel_iqr * 100.0, "% | outliers", pf_stats.n_outliers,
                  "|", "PASS" if pf_stats.passes else "FLAG")
            report = report + "prefill" + String(n_prompt) + "_tok_s=" \
                + String(pf_stats.median) + "\n"

            # ── MEASURE: prefill1024 (the race prompt repeated x4 — prefill throughput is
            #    content-agnostic). The repetition count is DERIVED from the 1024-token
            #    target and MAX_CTX rather than hardcoded at 4: with `--prompt-ids` longer
            #    than the fixture (the RAG-4096 cell) a fixed x4 would build a 16384-token
            #    prompt and run the KV cache the session was sized for off its own end. When
            #    the fixture is already >= the target the cell is SKIPPED (the primary
            #    `prefill<n_prompt>` cell above IS the long-prefill measurement then), so
            #    the fixture path's cell set is unchanged: 256 -> prefill256 + prefill1024.
            var long_reps = _LONG_TARGET // n_prompt
            if long_reps * n_prompt > MAX_CTX:
                long_reps = MAX_CTX // n_prompt
            if long_reps > 1:
                var long_ids = List[Int](capacity=long_reps * n_prompt)
                for rep in range(long_reps):
                    for i in range(n_prompt):
                        long_ids.append(race_ids[i])
                var n_long = long_reps * n_prompt
                var warmL = sg.prefill(_copy_ids(long_ids))
                _check_resident(warmL.status, "warmup prefill-long")
                var pf1024_samples = List[Float64]()
                for r in range(runs):
                    var b0 = perf_counter_ns()
                    var pfL = sg.prefill(_copy_ids(long_ids))
                    _check_resident(pfL.status, "bench prefill-long")
                    var b1 = perf_counter_ns()
                    pf1024_samples.append(Float64(n_long) / (_ms(b1 - b0) / 1000.0))
                var pf1024_stats = _cell_stats(pf1024_samples)
                print("prefill" + String(n_long) + ": median", pf1024_stats.median,
                      "tok/s | IQR", pf1024_stats.rel_iqr * 100.0, "% | outliers",
                      pf1024_stats.n_outliers, "|",
                      "PASS" if pf1024_stats.passes else "FLAG")
                report = report + "prefill" + String(n_long) + "_tok_s=" \
                    + String(pf1024_stats.median) + "\n"

            var depths = List[Int]()
            depths.append(64)
            depths.append(256)
            for di in range(len(depths)):
                var n_steps = depths[di]
                var samples = List[Float64]()
                for r in range(runs):
                    var pfb = sg.prefill(_copy_ids(race_ids))
                    _check_resident(pfb.status, "bench prefill")
                    var c0 = perf_counter_ns()
                    _check_resident(
                        sg.seed_and_run_graph_p3(pfb.token_id, n_prompt, n_steps),
                        "bench seed_and_run_graph_p3",
                    )
                    var c1 = perf_counter_ns()
                    samples.append(Float64(n_steps) / (_ms(c1 - c0) / 1000.0))
                var stats = _cell_stats(samples)
                print("gen", n_steps, ": median", stats.median, "tok/s | IQR",
                      stats.rel_iqr * 100.0, "% | outliers", stats.n_outliers,
                      "|", "PASS" if stats.passes else "FLAG")
                report = report + "gen" + String(n_steps) + "_tok_s=" \
                    + String(stats.median) + "\n"

            if out_path.byte_length() > 0:
                _write_text_file(out_path, report)
                print("  report written to", out_path)
            print("qwen25_7b: DONE arm = p3")

        else:
            # ════════════════════ the full-f32 reference arm ════════════════════
            var t0 = perf_counter_ns()
            var s32 = _CudaResidentQwen3(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX,
                eps, scale, 0, 1, 0, has_qkv_bias,
                # qk_norm=0, has_lm_head=1, f32 projections resident, has_qkv_bias
            )
            print("  device:", s32.device_name())

            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
            var lm_head_w = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
            var empty = List[Float64]()
            _check_resident(
                s32.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
                "upload_globals",
            )
            _check_resident(s32.upload_lm_head(lm_head_w), "upload_lm_head")
            for layer in range(n_layers):
                var pfx = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, pfx + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, pfx + "post_attention_layernorm.weight"
                )
                var wq = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, pfx + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, pfx + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, pfx + "mlp.down_proj.weight")
                _check_resident(
                    s32.upload_layer(layer, ln1, ln2, empty, empty, wq, wk, wv, wo, wg, wu, wd),
                    "upload_layer " + String(layer),
                )
                # 7B-lane attention bias: the q/k/v projection biases, packed [Q|K|V].
                var qb = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.q_proj.bias")
                var kb = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.k_proj.bias")
                var vb = _load_tensor(blob_path, tensors_obj, pfx + "self_attn.v_proj.bias")
                _check_resident(
                    s32.upload_qkv_bias(layer, qb, kb, vb),
                    "upload_qkv_bias " + String(layer),
                )
            _check_resident(s32.seal(), "seal")
            var t1 = perf_counter_ns()
            print("  one-time load (full f32):", _ms(t1 - t0), "ms")

            # ── fast cross-engine gate mode: prefill + generate + dump, skip gates/bench ──
            if gen_only > 0:
                var ds = List[Int]()
                var pg = s32.prefill(_copy_ids(race_ids))
                _check_resident(pg.status, "gen_only prefill")
                ds.append(pg.token_id)
                if gen_only > 1:
                    _check_resident(
                        s32.seed_and_run_graph(pg.token_id, n_prompt, gen_only - 1),
                        "gen_only seed_and_run_graph",
                    )
                    for k in range(1, gen_only):
                        ds.append(s32.graph_token(n_prompt + k - 1))
                var txt = String()
                for k in range(len(ds)):
                    txt = txt + String(ds[k]) + "\n"
                if dump_path.byte_length() > 0:
                    _write_text_file(dump_path, txt)
                    print("  gen_only wrote", len(ds), "tokens to", dump_path)
                else:
                    print(txt)
                print("GEN_ONLY DONE:", len(ds), "tokens")
                return

            # ── G0 — 16/16 greedy oracle through the f32 graph arm ──
            if len(oracle) >= G0_TOKENS:
                var pf0 = s32.prefill(_copy_ids(race_ids))
                _check_resident(pf0.status, "G0 prefill")
                var g0_mismatch = 0
                var got0 = pf0.token_id
                if got0 != oracle[0]:
                    g0_mismatch += 1
                    print("  ORACLE MISMATCH at token 0: got", got0, "want", oracle[0])
                _check_resident(
                    s32.seed_and_run_graph(got0, n_prompt, G0_TOKENS - 1),
                    "G0 seed_and_run_graph",
                )
                for k in range(1, G0_TOKENS):
                    var got = s32.graph_token(n_prompt + k - 1)
                    if got != oracle[k]:
                        g0_mismatch += 1
                        print("  ORACLE MISMATCH at token", k, ": got", got, "want", oracle[k])
                if g0_mismatch > 0:
                    print("G0 RESULT: FAIL —", g0_mismatch, "mismatched tokens")
                    exit(1)
                print("G0 RESULT: PASS —", G0_TOKENS, "greedy tokens match the oracle")
                report = report + "G0 PASS 16/16\n"
            else:
                print("G0 SKIPPED: no --oracle ids supplied (bootstrap from the llama.cpp gate)")
                report = report + "G0 SKIPPED (no oracle)\n"

            # ── G1 — self-consistency: the fixture twice, every token identical ──
            var s1 = List[Int]()
            var s2 = List[Int]()
            var pa = s32.prefill(_copy_ids(race_ids))
            _check_resident(pa.status, "G1 prefill run-a")
            s1.append(pa.token_id)
            _check_resident(
                s32.seed_and_run_graph(pa.token_id, n_prompt, G1_STEPS - 1), "G1 run-a"
            )
            for k in range(1, G1_STEPS):
                s1.append(s32.graph_token(n_prompt + k - 1))
            var pb = s32.prefill(_copy_ids(race_ids))
            _check_resident(pb.status, "G1 prefill run-b")
            s2.append(pb.token_id)
            _check_resident(
                s32.seed_and_run_graph(pb.token_id, n_prompt, G1_STEPS - 1), "G1 run-b"
            )
            for k in range(1, G1_STEPS):
                s2.append(s32.graph_token(n_prompt + k - 1))
            var g1_mismatch = 0
            for k in range(G1_STEPS):
                if s1[k] != s2[k]:
                    g1_mismatch += 1
            if g1_mismatch > 0:
                print("G1 RESULT: FAIL —", g1_mismatch, "self-consistency mismatches")
                exit(1)
            print("G1 RESULT: PASS —", G1_STEPS, "/", G1_STEPS,
                  "tokens identical across two runs")
            report = report + "G1 PASS " + String(G1_STEPS) + "/" + String(G1_STEPS) + "\n"

            # ── G2 — flip report vs the p3 arm's dumped stream ──
            if compare_path.byte_length() > 0:
                var other = _parse_ids_csv(_read_text_file(compare_path))
                var n_cmp = len(other)
                if len(s1) < n_cmp:
                    n_cmp = len(s1)
                var flips = 0
                var first_flip = -1
                for k in range(n_cmp):
                    if s1[k] != other[k]:
                        flips += 1
                        if first_flip < 0:
                            first_flip = k
                print("G2 flip report:", flips, "flips in", n_cmp, "tokens vs", compare_path,
                      "(first flip at", first_flip, ")")
                report = report + "G2 flips=" + String(flips) + "/" + String(n_cmp) + "\n"

            # ── dump this arm's stream for the other arm's G2 ──
            if dump_path.byte_length() > 0:
                var ds = List[Int]()
                var pd = s32.prefill(_copy_ids(race_ids))
                _check_resident(pd.status, "dump prefill")
                ds.append(pd.token_id)
                _check_resident(
                    s32.seed_and_run_graph(pd.token_id, n_prompt, G2_STEPS - 1), "dump"
                )
                for k in range(1, G2_STEPS):
                    ds.append(s32.graph_token(n_prompt + k - 1))
                var txt = String()
                for k in range(len(ds)):
                    txt = txt + String(ds[k]) + "\n"
                _write_text_file(dump_path, txt)
                print("  dumped", len(ds), "tokens to", dump_path)

            # ── MEASURE: prefill256 / gen64 / gen256 (f32 reference lane) ──
            for _ in range(WARMUP):
                var warm = s32.prefill(_copy_ids(race_ids))
                _check_resident(warm.status, "warmup prefill")

            var pf_samples = List[Float64]()
            for r in range(runs):
                var a0 = perf_counter_ns()
                var pfm = s32.prefill(_copy_ids(race_ids))
                _check_resident(pfm.status, "bench prefill")
                var a1 = perf_counter_ns()
                pf_samples.append(Float64(n_prompt) / (_ms(a1 - a0) / 1000.0))
            var pf_stats = _cell_stats(pf_samples)
            print("prefill" + String(n_prompt) + ": median", pf_stats.median, "tok/s | IQR",
                  pf_stats.rel_iqr * 100.0, "% | outliers", pf_stats.n_outliers,
                  "|", "PASS" if pf_stats.passes else "FLAG")
            report = report + "prefill" + String(n_prompt) + "_tok_s=" \
                + String(pf_stats.median) + "\n"

            var depths = List[Int]()
            depths.append(64)
            depths.append(256)
            for di in range(len(depths)):
                var n_steps = depths[di]
                var samples = List[Float64]()
                for r in range(runs):
                    var pfb = s32.prefill(_copy_ids(race_ids))
                    _check_resident(pfb.status, "bench prefill")
                    var c0 = perf_counter_ns()
                    _check_resident(
                        s32.seed_and_run_graph(pfb.token_id, n_prompt, n_steps),
                        "bench seed_and_run_graph",
                    )
                    var c1 = perf_counter_ns()
                    samples.append(Float64(n_steps) / (_ms(c1 - c0) / 1000.0))
                var stats = _cell_stats(samples)
                print("gen", n_steps, ": median", stats.median, "tok/s | IQR",
                      stats.rel_iqr * 100.0, "% | outliers", stats.n_outliers,
                      "|", "PASS" if stats.passes else "FLAG")
                report = report + "gen" + String(n_steps) + "_tok_s=" \
                    + String(stats.median) + "\n"

            if out_path.byte_length() > 0:
                _write_text_file(out_path, report)
                print("  report written to", out_path)
            print("qwen25_7b: DONE arm = f32")
