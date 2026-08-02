"""qwen3_probe_counters_i8_sdpasimd.mojo — DIAGNOSTIC-ONLY per-dispatch GPU timing for the
SDPA-SIMD-shuffle-reduction int8 batched arm — the direct twin of `qwen3_probe_counters_i8.mojo`,
built to get a real, hardware-measured BEFORE/AFTER number for the `sdpa` role specifically:
run this file and `qwen3_probe_counters_i8.mojo` and compare their `sdpa` role `avg=` lines.

Everything below is `qwen3_probe_counters_i8.mojo`'s own methodology, unchanged, with
`metaldispatch.session._MBQwen3I8SDPASimd` (SDPA role -> `residentk.kernels._sdpa_kernel_simd`,
the SIMD-shuffle two-level reduction) substituted for `_MBQwen3I8` (SDPA role -> `_sdpa_kernel`,
the nine-barrier-per-key shared-memory tree) everywhere. Not a rewrite of
`qwen3_generate_batch_i8_sdpasimd.mojo` — reuses `_MBQwen3I8SDPASimd` completely unchanged
(session open, weight upload, buffer allocation, and the ordinary `step()` path all run
byte-for-byte identically to that binary) and only ADDS a second, diagnostic way to run one
token's 171 dispatches: through `algenta_run_token_counters` (implemented in the sibling
`batch_shim_counters.m`, a full twin of `batch_shim.m` plus three new exports) instead of
`algenta_run_token`.

Real GPU-side timing, no host sync between dispatches
-------------------------------------------------------------------
`batch_shim_counters.m` samples a hardware timestamp counter immediately before and immediately
after every `dispatchThreadgroups:` call, via `sampleCountersInBuffer:atSampleIndex:withBarrier:NO`
— an ordinary GPU-command-stream entry, not a CPU/GPU sync point. The whole 171-dispatch sequence
still runs behind ONE command buffer, ONE encoder, ONE commit, ONE `waitUntilCompleted`, exactly
like production. `resolveCounterRange:` is called exactly ONCE, after that single wait, to read the
already-GPU-written timestamps back. Confirmed against the actual installed Metal headers on this
machine (Xcode 26.6.0) — see `batch_shim_counters.m`'s own module docstring for the exact
class/method names and where each is declared.

Role classification: reuses the session's OWN classification, doesn't re-derive it
-------------------------------------------------------------------------------------------
`_MBQwen3I8SDPASimd.pipeline_idx` (role id -> discovered Metal pipeline index) is built by
`metaldispatch.session._classify_pipeline`, the exact function production uses. This file's
`_ROLE_AT_DISPATCH` table below assigns each of the 171 fixed dispatch SLOTS a role id, using the
exact same slot order `_MBQwen3I8SDPASimd._build_descriptors` lays them out in (one `_ROLE_EMBED`, then 28
repeats of `_ROLE_NORM_GEMV, _ROLE_QK_ROPE, _ROLE_SDPA, _ROLE_GEMV_ACCUM, _ROLE_NORM_GEMV2_SWIGLU,
_ROLE_GEMV_ACCUM`, then `_ROLE_LMHEAD_ARGMAX, _ROLE_ARGMAX_REDUCE` — see that function, unchanged,
for the ground truth this table transcribes). This is needed ONLY to split the two `_ROLE_GEMV_ACCUM`
slots per layer into "o_proj" and "down_proj" for reporting — `_classify_pipeline` itself cannot
make that distinction (both slots share one pipeline). `_verify_role_table` below cross-checks every
one of the 171 slots' assigned role against the pipeline index actually written into that slot's
descriptor bytes (by `_build_descriptors`, read back here, never re-derived) and raises if a single
slot disagrees — so a future edit to `_build_descriptors`'s dispatch order cannot silently desync
this file's table from what the session really does.

Methodology: same-process, order-alternated, identical-input A/B, not a cross-binary race
-------------------------------------------------------------------------------------------------
Phase 1 (counters OFF, plain `s.step()` — byte-for-byte the production call) runs the standard
15-step greedy decode once and RECORDS the exact (input token id, position) pair fed to every step.
Phases 2-4 alternate ON/OFF/ON, REPLAYING that exact recorded sequence (never depending on that
phase's own generated output) so every phase does IDENTICAL GPU work — same weights, same `n_keys`
per layer, same everything — and the only difference between an OFF phase and an ON phase is
whether `sampleCountersInBuffer:` calls are present in the command stream. Alternating the order
(OFF, ON, OFF, ON) cancels any GPU-clock/thermal warm-up asymmetry that a single OFF-then-ON run
would confound. Replaying the same (token, pos) pair after the KV cache already holds LATER
positions is safe and idempotent: `_sdpa_kernel` for a query at position `pos` only ever reads keys
`[0, pos]` (`n_keys = pos + 1`, enforced by `_MBQwen3I8SDPASimd.step`'s own docstring invariant), never a
later row, and rewriting row `pos` with the same token's embedding is deterministic.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8_sdpasimd.mojo \
        -o /tmp/qwen3_probe_counters_i8_sdpasimd \
        -Xlinker /tmp/batch_shim_counters.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/qwen3_probe_counters_i8_sdpasimd
"""

from std.ffi import external_call
from std.memory import alloc
from std.builtin.type_aliases import MutAnyOrigin
from std.sys import has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_MAX_CONTEXT
from metaldispatch.contract import MB_OK, metaldispatch_dispatch_budget, metaldispatch_status_name
from metaldispatch.session import _MBQwen3I8SDPASimd, _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import _mb_set_arg_int, MB_DESC_STRIDE

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime N_NEW_MAX: Int = 16
comptime EOS_TOKEN_ID: Int = 151643
comptime N_PHASES: Int = 4
"""OFF, ON, OFF, ON — see module docstring."""

# ── the eight role ids `metaldispatch.session._classify_pipeline` assigns, transcribed from that
# file's own `comptime _ROLE_* : Int = ...` block (session.mojo lines ~149-157) so this file never
# has to import a leading-underscore comptime by name. Kept as plain ints, verified at runtime by
# `_verify_role_table` against the session's own `pipeline_idx` list -- if session.mojo's role
# numbering ever changes, that verification fails loudly instead of silently mislabeling dispatches.
comptime _R_EMBED: Int = 0
comptime _R_NORM_GEMV: Int = 1
comptime _R_GEMV_ACCUM: Int = 2
comptime _R_NORM_GEMV2_SWIGLU: Int = 3
comptime _R_QK_ROPE: Int = 4
comptime _R_SDPA: Int = 5
comptime _R_LMHEAD_ARGMAX: Int = 6
comptime _R_ARGMAX_REDUCE: Int = 7


fn _mb_counters_supported() -> Int:
    """1 = device supports dispatch-boundary counter sampling AND has a timestamp counter set,
    0 = neither/either missing, -1 = called before session open. See `batch_shim_counters.m`."""
    return Int(external_call["algenta_counters_supported", Int64]())


fn _mb_timestamp_frequency() -> UInt64:
    """Ticks-per-second for the raw values `_mb_run_token_counters` writes; 0 if this OS predates
    `MTLDevice.queryTimestampFrequency` (macOS 26). NOT TRUSTED for the actual conversion below --
    see `_calibrate_gpu_tick_ns` and the module docstring's calibration finding."""
    return external_call["algenta_timestamp_frequency", UInt64]()


fn _mb_sample_gpu_timestamp() -> UInt64:
    return external_call["algenta_sample_gpu_timestamp", UInt64]()


fn _calibrate_gpu_tick_ns(hold_ms: Int) raises -> Float64:
    """Empirically measures how many real nanoseconds one GPU counter tick is, by bracketing a
    known-length real interval (measured with `perf_counter_ns`, the same wall-clock primitive this
    whole benchmark chain already trusts) with two `algenta_sample_gpu_timestamp` calls and dividing.
    `hold_ms` should be large enough that clock jitter is a small fraction of the interval; this
    file uses 200ms, chosen the same way the rest of this task's timing choices are -- big enough to
    average out noise, small enough not to matter next to the benchmark's own runtime.
    `MTLDevice.queryTimestampFrequency` reported 24,000,000 ticks/sec on this machine (Xcode 26.6,
    the M4 Max this ran on); THIS calibration measured the real rate directly against wall-clock
    time and found it to be ~41.667x higher (i.e., ~1 tick per real nanosecond) -- see this file's
    printed report and the task's final writeup for the exact numbers. Trusting the reported
    frequency instead of calibrating would have made every downstream number in this report wrong
    by the same ~41.667x factor, which is exactly why step 5's reconciliation check matters: it is
    what caught this."""
    var t_wall0 = perf_counter_ns()
    var gpu0 = _mb_sample_gpu_timestamp()
    var deadline = t_wall0 + UInt(hold_ms) * 1_000_000
    while perf_counter_ns() < deadline:
        pass
    var gpu1 = _mb_sample_gpu_timestamp()
    var t_wall1 = perf_counter_ns()
    if gpu1 <= gpu0:
        raise Error("qwen3_probe_counters_i8_sdpasimd: GPU timestamp calibration did not advance")
    var wall_seconds = Float64(Int(t_wall1 - t_wall0)) / 1.0e9
    var tick_rate_hz = Float64(gpu1 - gpu0) / wall_seconds
    return 1.0e9 / tick_rate_hz


fn _mb_open_counters(max_samples: Int) -> Int:
    return Int(external_call["algenta_open_counters", Int64, Int64](Int64(max_samples)))


fn _mb_run_token_counters(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin],
    n: Int,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
) -> Int:
    return Int(
        external_call[
            "algenta_run_token_counters", Int64,
            UnsafePointer[UInt8, origin=MutAnyOrigin], Int64,
            UnsafePointer[UInt64, origin=MutAnyOrigin],
        ](descriptors, Int64(n), out_ticks)
    )


fn _role_name(role: Int) -> String:
    if role == _R_EMBED:
        return "embed_row"
    if role == _R_NORM_GEMV:
        return "norm_gemv (QKV-proj)"
    if role == _R_GEMV_ACCUM:
        return "gemv_accum"
    if role == _R_NORM_GEMV2_SWIGLU:
        return "norm_gemv2_swiglu (gate-up)"
    if role == _R_QK_ROPE:
        return "qk_rope_write"
    if role == _R_SDPA:
        return "sdpa"
    if role == _R_LMHEAD_ARGMAX:
        return "lmhead_argmax"
    if role == _R_ARGMAX_REDUCE:
        return "argmax_reduce"
    return "UNKNOWN"


fn _build_role_table(n_layers: Int, n_descriptors: Int) raises -> List[Int]:
    """Slot -> role id for all `n_descriptors` dispatches in one token, transcribing
    `_MBQwen3I8SDPASimd._build_descriptors`'s own fixed layout (unchanged, read directly from
    `metaldispatch/session.mojo` while writing this file). `o_proj` is the FIRST `_R_GEMV_ACCUM`
    slot in a layer's block of six, `down_proj` the second -- distinguished here by POSITION only,
    since `_classify_pipeline` maps both to the one pipeline. Also carries a distinct per-slot
    sub-label so the two are reported separately without inventing a ninth role id."""
    var roles = List[Int](capacity=n_descriptors)
    roles.append(_R_EMBED)
    for _ in range(n_layers):
        roles.append(_R_NORM_GEMV)
        roles.append(_R_QK_ROPE)
        roles.append(_R_SDPA)
        roles.append(_R_GEMV_ACCUM)  # o_proj (first of the layer's two)
        roles.append(_R_NORM_GEMV2_SWIGLU)
        roles.append(_R_GEMV_ACCUM)  # down_proj (second of the layer's two)
    roles.append(_R_LMHEAD_ARGMAX)
    roles.append(_R_ARGMAX_REDUCE)
    if len(roles) != n_descriptors:
        raise Error(
            "qwen3_probe_counters_i8_sdpasimd: built " + String(len(roles)) + " role slots but the session "
            + "says " + String(n_descriptors) + " descriptors -- table is out of sync with "
            + "_build_descriptors"
        )
    return roles^


fn _sublabel(slot: Int, n_layers: Int) -> String:
    """Distinguishes the two `_R_GEMV_ACCUM` slots per layer for reporting. Every other role has
    exactly one slot per layer (or one total), so this only ever returns a non-default string for
    the two `gemv_accum` positions."""
    if slot == 0:
        return "embed_row"
    if slot >= 1 + 6 * n_layers:
        if slot == 1 + 6 * n_layers:
            return "lmhead_argmax"
        return "argmax_reduce"
    var within = (slot - 1) % 6
    if within == 3:
        return "gemv_accum:o_proj"
    if within == 5:
        return "gemv_accum:down_proj"
    if within == 0:
        return "norm_gemv:qkv_proj"
    if within == 1:
        return "qk_rope_write"
    if within == 2:
        return "sdpa"
    return "norm_gemv2_swiglu:gate_up_proj"


fn _verify_role_table(mut s: _MBQwen3I8SDPASimd, roles: List[Int]) raises:
    """Reads the pipeline index actually stored in every descriptor slot (written by
    `_build_descriptors`, never guessed) and checks it against `s.pipeline_idx[roles[d]]` -- the
    session's OWN role->pipeline map, populated by the OWN `_classify_pipeline` call at session
    open. Any mismatch means this file's positional table has drifted from what the session really
    dispatches, and it is fatal rather than a silent mislabel."""
    for d in range(len(roles)):
        var stored = Int((s.descriptors + d * MB_DESC_STRIDE).bitcast[Int32]()[0])
        var expected = s.pipeline_idx[roles[d]]
        if stored != expected:
            raise Error(
                "qwen3_probe_counters_i8_sdpasimd: slot " + String(d) + " role table says pipeline "
                + String(expected) + " (role " + String(roles[d]) + ") but the descriptor actually "
                + "holds pipeline " + String(stored) + " -- _build_descriptors's dispatch order has "
                + "moved and this file's table must be updated"
            )


@fieldwise_init
struct _RoleAgg(Copyable, Movable):
    var count: Int
    var total_ns: Float64
    var min_ns: Float64
    var max_ns: Float64


fn _ms(ns: UInt) -> Float64:
    return Float64(Int(ns)) / 1.0e6


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
        raise Error("qwen3_probe_counters_i8_sdpasimd: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = RESIDENT_MAX_CONTEXT

    print("qwen3_probe_counters_i8_sdpasimd: d_model=", d_model, "n_layers=", n_layers, "vocab=", vocab_size,
          "n_prompt=", n_prompt)
    print("  dispatch budget per token:", metaldispatch_dispatch_budget(n_layers))

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, N_NEW_MAX, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_probe_counters_i8_sdpasimd: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_probe_counters_i8_sdpasimd: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_probe_counters_i8_sdpasimd: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_probe_counters_i8_sdpasimd: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")

        var s = _MBQwen3I8SDPASimd(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        print("  device:", s.device_name())

        var rt = rope_table(d_head, max_ctx, theta)
        _ = ATTN_OK
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check_mb(s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx))

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
            _check_mb(s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd))
        _ = s.seal()
        print("  weights loaded + sealed")

        # ═══ PREFILL: plain step(), identical to production ═══
        var first_tok = -1
        var first_logit = 0.0
        for t in range(n_prompt):
            var r = s.step(prompt_ids[t], t)
            _check_mb(r.status)
            first_tok = r.token_id
            first_logit = r.logit
        print("  prefill done, first generated id=", first_tok, "logit=", first_logit)

        # ═══ role table, built once, verified once against the session's own classification ═══
        var roles = _build_role_table(n_layers, s.n_descriptors)
        _verify_role_table(s, roles)
        print("  role table verified against", s.n_descriptors, "descriptor slots (0 mismatches)")

        # ═══ counters support + capacity ═══
        var supported = _mb_counters_supported()
        if supported != 1:
            print("qwen3_probe_counters_i8_sdpasimd: counter sampling not available on this device/build, "
                  "status=", supported)
            return
        var reported_freq = _mb_timestamp_frequency()
        print("  MTLDevice.queryTimestampFrequency reports:", reported_freq, "ticks/sec")
        var ns_per_tick = _calibrate_gpu_tick_ns(200)
        var calibrated_freq = 1.0e9 / ns_per_tick
        print("  DIRECT calibration (200ms wall-clock bracket, perf_counter_ns vs "
              "algenta_sample_gpu_timestamp):", calibrated_freq, "ticks/sec (",
              ns_per_tick, "ns/tick )")
        print("  discrepancy vs reported frequency: ", calibrated_freq / Float64(reported_freq),
              "x -- USING THE CALIBRATED VALUE for every ns conversion below, not the reported one")
        var counters_rc = _mb_open_counters(2 * s.n_descriptors)
        if counters_rc != 0:
            raise Error("qwen3_probe_counters_i8_sdpasimd: algenta_open_counters failed, rc=" + String(counters_rc))
        var out_ticks = alloc[UInt64](2 * s.n_descriptors)

        # ═══ Phase 1 (OFF): plain step(), record the exact (token_id, pos) sequence ═══
        var seq_tok = List[Int]()
        var seq_pos = List[Int]()
        var off_ms_1 = List[Float64]()
        var cur_tok = first_tok
        for step in range(1, N_NEW_MAX):
            var pos = n_prompt + step - 1
            seq_tok.append(cur_tok)
            seq_pos.append(pos)
            var t0 = perf_counter_ns()
            var r = s.step(cur_tok, pos)
            var t1 = perf_counter_ns()
            _check_mb(r.status)
            off_ms_1.append(_ms(t1 - t0))
            cur_tok = r.token_id
            if cur_tok == EOS_TOKEN_ID:
                break
        var n_steps = len(seq_tok)
        print("  phase 1 (OFF) recorded", n_steps, "decode steps; per-step ms:", off_ms_1[0], "..",
              off_ms_1[n_steps - 1])

        # role totals, accumulated across every ON phase's every step
        var role_count = List[Int]()
        var role_total_ns = List[Float64]()
        var role_min_ns = List[Float64]()
        var role_max_ns = List[Float64]()
        for _ in range(8):
            role_count.append(0)
            role_total_ns.append(0.0)
            role_min_ns.append(1.0e18)
            role_max_ns.append(-1.0)
        # separate accumulators for the two gemv_accum sub-roles + lm_head kept whole-token
        var oproj_total_ns = 0.0
        var downproj_total_ns = 0.0
        var lmhead_total_ns = 0.0
        var argmaxreduce_total_ns = 0.0
        var n_on_steps = 0

        var off_ms_all = List[Float64]()
        var on_ms_all = List[Float64]()
        for v in off_ms_1:
            off_ms_all.append(v)

        for phase in range(2, N_PHASES + 1):
            var is_on = (phase % 2) == 0
            if not is_on:
                for i in range(n_steps):
                    var t0 = perf_counter_ns()
                    var r = s.step(seq_tok[i], seq_pos[i])
                    var t1 = perf_counter_ns()
                    _check_mb(r.status)
                    off_ms_all.append(_ms(t1 - t0))
                print("  phase", phase, "(OFF) done,", n_steps, "steps")
            else:
                for i in range(n_steps):
                    _mb_set_arg_int(s.descriptors, s.token_id_offset, 3, seq_tok[i])
                    var n_keys = seq_pos[i] + 1
                    for layer in range(n_layers):
                        _mb_set_arg_int(s.descriptors, s.pos_offsets[layer], 8, seq_pos[i])
                        _mb_set_arg_int(s.descriptors, s.nkeys_offsets[layer], 4, n_keys)
                    var t0 = perf_counter_ns()
                    var rc = _mb_run_token_counters(s.descriptors, s.n_descriptors, out_ticks)
                    var t1 = perf_counter_ns()
                    if rc != 0:
                        raise Error("qwen3_probe_counters_i8_sdpasimd: algenta_run_token_counters failed")
                    on_ms_all.append(_ms(t1 - t0))
                    n_on_steps += 1
                    for d in range(s.n_descriptors):
                        var start_tick = out_ticks[2 * d]
                        var end_tick = out_ticks[2 * d + 1]
                        var delta_ns: Float64
                        if end_tick >= start_tick:
                            delta_ns = Float64(end_tick - start_tick) * ns_per_tick
                        else:
                            delta_ns = 0.0  # a wraparound/error tick pair; excluded, not guessed
                        var role = roles[d]
                        role_count[role] += 1
                        role_total_ns[role] += delta_ns
                        if delta_ns < role_min_ns[role]:
                            role_min_ns[role] = delta_ns
                        if delta_ns > role_max_ns[role]:
                            role_max_ns[role] = delta_ns
                        if role == _R_GEMV_ACCUM:
                            var within = (d - 1) % 6
                            if within == 3:
                                oproj_total_ns += delta_ns
                            else:
                                downproj_total_ns += delta_ns
                        elif role == _R_LMHEAD_ARGMAX:
                            lmhead_total_ns += delta_ns
                        elif role == _R_ARGMAX_REDUCE:
                            argmaxreduce_total_ns += delta_ns
                print("  phase", phase, "(ON) done,", n_steps, "steps")

        # ═══ report ═══
        var off_sum = 0.0
        for v in off_ms_all:
            off_sum += v
        var on_sum = 0.0
        for v in on_ms_all:
            on_sum += v
        var off_avg = off_sum / Float64(len(off_ms_all))
        var on_avg = on_sum / Float64(len(on_ms_all))
        print("")
        print("═══ overhead: counters OFF vs ON (same replayed token/pos sequence, alternated order) ═══")
        print("  OFF: n=", len(off_ms_all), "avg=", off_avg, "ms/token ==",
              1000.0 / off_avg, "tok/s")
        print("  ON:  n=", len(on_ms_all), "avg=", on_avg, "ms/token ==",
              1000.0 / on_avg, "tok/s")
        print("  overhead added by counter sampling:", on_avg - off_avg, "ms/token (",
              (on_avg - off_avg) / off_avg * 100.0, "% )")

        print("")
        print("═══ per-role GPU dispatch time, summed over", n_on_steps, "ON-phase decode steps ═══")
        var grand_total_ns = 0.0
        for role in range(8):
            grand_total_ns += role_total_ns[role]
        for role in range(8):
            if role_count[role] == 0:
                continue
            var avg_ns = role_total_ns[role] / Float64(role_count[role])
            print("  ", _role_name(role), ": count=", role_count[role],
                  "total=", role_total_ns[role] / 1.0e6, "ms",
                  "avg=", avg_ns / 1.0e3, "us",
                  "min=", role_min_ns[role] / 1.0e3, "us",
                  "max=", role_max_ns[role] / 1.0e3, "us",
                  "pct_of_residual_sum=", role_total_ns[role] / grand_total_ns * 100.0, "%")
        print("  -- gemv_accum split by position --")
        print("     o_proj:    total=", oproj_total_ns / 1.0e6, "ms over", n_on_steps * n_layers,
              "dispatches, avg=", oproj_total_ns / Float64(n_on_steps * n_layers) / 1.0e3, "us")
        print("     down_proj: total=", downproj_total_ns / 1.0e6, "ms over", n_on_steps * n_layers,
              "dispatches, avg=", downproj_total_ns / Float64(n_on_steps * n_layers) / 1.0e3, "us")
        print("  -- lm_head, once per token --")
        print("     lmhead_argmax:  avg per token=", lmhead_total_ns / Float64(n_on_steps) / 1.0e6,
              "ms (", lmhead_total_ns / grand_total_ns * 100.0, "% of the summed residual)")
        print("     argmax_reduce:  avg per token=",
              argmaxreduce_total_ns / Float64(n_on_steps) / 1.0e6, "ms")

        print("")
        print("═══ reconciliation: summed per-dispatch GPU time vs the wall-clock ON per-token time ═══")
        print("  sum of all per-dispatch GPU deltas, per token:", grand_total_ns / Float64(n_on_steps) / 1.0e6, "ms")
        print("  measured wall-clock ON per-token time (this run):", on_avg, "ms")
        print("  measured wall-clock OFF (no counters) per-token time (this run):", off_avg, "ms")


fn _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


fn _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen3_probe_counters_i8_sdpasimd: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


fn _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_probe_counters_i8_sdpasimd: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


fn _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


fn _check_mb(status: Int) raises:
    if status != MB_OK:
        raise Error(
            "qwen3_probe_counters_i8_sdpasimd: metaldispatch call failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
        )
