"""metaldispatch.qwen3_prefill_decode — makes `_MBQwen3I8AllSimd7Prefill`'s batched-prefill Metal
GPU decode arm reachable from a real `pip install algenta` runtime, not only from a hand-run
benchmark driver.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float, int
backend: mojo
surfaces: library_execute
golden_vectors: mojo/tests/libs/test_metaldispatch_session_prefill.mojo
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7_prefill.mojo
docs: gitbook/engine/qwen3-metal-decode.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Scope, stated precisely so nothing here overclaims -- IDENTICAL to `metaldispatch.qwen3_decode`'s
own scope statement (Qwen3-0.6B-Base, greedy decode, Apple Silicon Metal, refused by named status
rather than silently downgraded), with exactly one change: the prompt is processed by
`_MBQwen3I8AllSimd7Prefill.prefill_batch()` instead of a `for t in range(n_prompt): s.step(...)`
loop -- see `metaldispatch.session_prefill`'s own module docstring for what that struct adds over
`_MBQwen3I8AllSimd7` (which stays completely untouched; this file is new orchestration around a new,
additive kernel path, not a modification of the existing one).

Chunking: `prefill_batch()` itself is bounded to `metaldispatch.session_prefill.PREFILL_MAX_TILE`
rows per call (matching the KV cache's own default capacity). A prompt longer than that is processed
in multiple `prefill_batch()` calls, each writing the next `PREFILL_MAX_TILE`-row slice of the KV
cache at its own `pos_base` -- correctness of this chunking rests on EXACTLY the same cross-call
argument `metaldispatch.session_prefill`'s own module docstring makes for prefill-then-`step()`:
each call only ever depends on the KV cache and per-layer weights, which persist across calls on the
same struct instance, never on the PREVIOUS call's activation-buffer contents.

`max_ctx` is raised above `RESIDENT_DEFAULT_CONTEXT` (512) whenever `n_prompt + max_new_tokens`
would not fit in it, up to `RESIDENT_MAX_CONTEXT`'s own safety ceiling (65536) -- the SAME
auto-raise contract `qwen3_decode.qwen3_i8_allsimd7_decode_flat` applies (since the 2026-08-09
parity cheap-wins pass; before that it always requested the default 512 regardless of prompt
length).
"""

from std.math import sqrt
from std.sys import has_accelerator
from std.time import perf_counter_ns
from std.math import exp
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from crypto.pbkdf2 import sha256_bytes
from llm_sampling import (
    min_p_threshold,
    repetition_penalty_scale,
    temperature_scale,
    token_frequency_penalty,
    top_p_cumulative,
)
from residentk.contract import (
    RESIDENT_DEFAULT_CONTEXT,
    RESIDENT_MAX_CONTEXT,
)
from metaldispatch.contract import (
    MB_ERR_CHECKPOINT_UNREADABLE,
    MB_ERR_CONTEXT_FULL,
    MB_ERR_DISPATCH_COUNT_MISMATCH,
    MB_ERR_NO_DEVICE,
    MB_ERR_SESSION_OPEN_FAILED,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_ERR_UNSUPPORTED_ARCHITECTURE,
    MB_ERR_UPLOAD_LENGTH,
    MB_OK,
    metaldispatch_status_name,
)
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import (
    _mb_begin_adopt,
    _mb_end_adopt,
    _mb_free_all_buffers,
    _mb_get_resident_key,
    _mb_set_resident_key,
)
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill, PREFILL_MAX_TILE, BATCH_DECODE_MAX_SEQS
from metaldispatch.session_prefill_policy import (
    PF_ATTN_OFF,
    PF_ATTN_GROUPED_FA_WITH_MIRROR,
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_ORIGINAL,
    PF_GEMM_BM64,
    PF_GEMM_VECLOAD4_ALL_ROLES,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    UnresolvedPrefillConfig,
)

comptime QWEN3_0_6B_BASE_D_MODEL: Int = 1024
comptime QWEN3_0_6B_BASE_N_LAYERS: Int = 28
comptime QWEN3_0_6B_BASE_H_Q: Int = 16
comptime QWEN3_0_6B_BASE_H_KV: Int = 8
comptime QWEN3_0_6B_BASE_D_HEAD: Int = 128
comptime QWEN3_0_6B_BASE_D_FF: Int = 3072
comptime QWEN3_0_6B_BASE_VOCAB: Int = 151936
comptime QWEN3_0_6B_BASE_EOS_TOKEN_ID: Int = 151643


@fieldwise_init
struct Qwen3PrefillDecodeResult(Copyable, Movable):
    """Same shape as `qwen3_decode.Qwen3DecodeResult` -- see that struct's own docstring."""

    var status: Int
    var error_message: String
    var token_ids: List[Int]
    var n_prompt: Int
    var stopped_on_eos: Bool
    var dispatches_per_token: Int
    var decode_tokens_per_sec: Float64
    var prefill_tokens_per_sec: Float64
    var prefill_chunks: Int
    """How many `prefill_batch()` calls this run needed -- 1 for any prompt `<= PREFILL_MAX_TILE`
    (every prompt this arm has been raced against real opponents with, so far), `> 1` only once a
    prompt exceeds that ceiling."""


def _decode_err(status: Int, message: String) -> Qwen3PrefillDecodeResult:
    return Qwen3PrefillDecodeResult(status, message, List[Int](), 0, False, 0, 0.0, 0.0, 0)


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct _TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> _TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("metaldispatch.qwen3_prefill_decode: tensor not found in manifest: " + name)
    return _TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    # Read in bounded chunks (16 Mi elements = 128 MiB each) rather than one `read_bytes` of the
    # full size: large models (Qwen3-1.7B's tied embedding is ~2.5 GB of float64) exceed the
    # single-read limit a whole-tensor read hits with "Invalid argument", and chunking also halves
    # peak memory (no second full-size copy). Identical bytes either way -- the campaign's
    # Qwen3-0.6B-Base checkpoints read back byte-for-byte the same through this path.
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var remaining = n_elements
    alias CHUNK_ELEMS = 1 << 24  # 16 Mi elements = 128 MiB per read
    while remaining > 0:
        var take = CHUNK_ELEMS if remaining > CHUNK_ELEMS else remaining
        var raw = f.read_bytes(take * 8)
        if len(raw) != take * 8:
            f.close()
            raise Error(
                "metaldispatch.qwen3_prefill_decode: short read at byte offset "
                + String(byte_offset) + " (wanted " + String(take * 8) + " bytes, got "
                + String(len(raw)) + ")"
            )
        var fp = raw.unsafe_ptr().bitcast[Float64]()
        for i in range(take):
            out.append(fp[i])
        remaining -= take
    f.close()
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


# ── Parity cheap wins (beat-llama.cpp campaign, 2026-08-10): quantized-state cache ─────────────
#
# `weights_i8.cache` lives next to a converted checkpoint's manifest.json/weights.blob and holds
# the session's EXACT post-quantization device bytes (Int8 weights + per-row Float32 scales +
# Float32 norms -- ~1 byte/param against the f64 blob's 8). A one-shot call re-uploads weights
# every time (that is the design, parity gap 4), so the second-and-later call on the same
# converted checkpoint otherwise re-reads the whole f64 blob and re-runs the two-pass per-row
# quantization; with a valid cache it does neither. File format, little-endian:
#
#   bytes   0..7   magic "ALGI8C01"
#   bytes   8..39  SHA-256 of manifest.json's bytes -- the validity gate. `prepare_model_
#                  checkpoint` writes manifest+blob atomically per conversion, so the manifest
#                  hash keys the pair. (Honest residual edge, recorded rather than ignored: a
#                  hand-edit of weights.blob that left manifest.json untouched would not be
#                  caught -- the manifest hash is the anchor by design, matching the one writer
#                  that produces the pair.)
#   bytes  40..95  u64 x7: n_layers, d_model, h_q, h_kv, d_head, d_ff, vocab
#   bytes  96..103 u64: quantized-state byte count
#   bytes 104..    `_MBQwen3I8AllSimd7Prefill.dump_quantized_state`'s own region bytes

comptime _I8_CACHE_HEADER_BYTES: Int = 104
comptime _I8_CACHE_CHUNK_BYTES: Int = 1 << 27  # 128 MiB -- same chunking `_read_f64_slice` uses


def _i8_cache_magic_ok(header: List[UInt8]) -> Bool:
    if len(header) < 8:
        return False
    # "ALGI8C01"
    return (
        header[0] == 65 and header[1] == 76 and header[2] == 71 and header[3] == 73
        and header[4] == 56 and header[5] == 67 and header[6] == 48 and header[7] == 49
    )


def _le64(raw: List[UInt8], off: Int) -> Int:
    var v = 0
    for i in range(8):
        v = v | (Int(raw[off + i]) << (8 * i))
    return v


def _sha256_of_string(s: String) -> List[Int]:
    var raw = s.as_bytes()
    var ints = List[Int](capacity=len(raw))
    for i in range(len(raw)):
        ints.append(Int(raw[i]))
    return sha256_bytes(ints^)


def _sha256_matches(header: List[UInt8], digest: List[Int]) -> Bool:
    if len(digest) != 32:
        return False
    for i in range(32):
        if Int(header[8 + i]) != digest[i]:
            return False
    return True


def _slice_ids(ids: List[Int], start: Int, count: Int) -> List[Int]:
    var out = List[Int](capacity=count)
    for i in range(count):
        out.append(ids[start + i])
    return out^


# ── Parity gap 3 (sampling, 2026-08-10): the host-side sampler chain ──────────────────────────
# The logits-emitting lm_head twin lands the whole vocab row in Float32; this chain turns it into
# one drawn token. Order follows the conventional sampler pipeline: penalties -> temperature ->
# top-k -> min-p -> top-p -> weighted draw. The scalar formulas come from `llm_sampling` (the
# module the parity analysis named as "exists unwired" -- wired here, not re-derived). Everything
# is deterministic given the seed: xorshift64 stepped once per draw, strict comparisons with
# lowest-id tie-break, no thread-dependent order anywhere.

struct _SamplerRng(Movable):
    """xorshift64 (Marsaglia) -- shifts and xors only, no wrapping arithmetic anywhere, so the
    pinned toolchain's lack of `&+`/`&*` never matters. Quality is ample for token draws; the
    point is reproducibility: same state + same logits -> same token, on every platform."""

    var state: UInt64

    def __init__(out self, seed_state: UInt64):
        # xorshift64 is stuck at 0 if seeded with 0; the golden-ratio constant keeps a caller
        # seed of 0 honest without changing any other seed.
        self.state = seed_state if seed_state != 0 else 0x9E3779B97F4A7C15

    def next_u64(mut self) -> UInt64:
        var x = self.state
        x = x ^ (x << 13)
        x = x ^ (x >> 7)
        x = x ^ (x << 17)
        self.state = x
        return x

    def uniform(mut self) -> Float64:
        # Top 53 bits -> [0, 1), the standard double construction.
        return Float64(Int(self.next_u64() >> 11)) * (1.0 / 9007199254740992.0)


def _sample_sort_desc_ids(idx: List[Int], w: List[Float64]) -> List[Int]:
    """`idx` sorted by `w` DESCENDING, ties by LOWER id first -- functional (returns a new list,
    mutates nothing), because the pinned toolchain passes List arguments as immutable borrows.
    Deterministic: the pivot is the middle element, the three-way split is a stable ascending-id
    scan, and both recursions apply the same rule."""
    var n = len(idx)
    if n < 2:
        var out0 = List[Int](capacity=n)
        for i in range(n):
            out0.append(idx[i])
        return out0^
    var pivot_id = idx[n // 2]
    var pivot = w[pivot_id]
    var hi = List[Int]()
    var eq = List[Int]()
    var lo = List[Int]()
    for i in range(n):
        var id_i = idx[i]
        var v = w[id_i]
        if v > pivot or (v == pivot and id_i < pivot_id):
            hi.append(id_i)
        elif v == pivot:
            eq.append(id_i)
        else:
            lo.append(id_i)
    var out = _sample_sort_desc_ids(hi, w)
    for i in range(len(eq)):
        out.append(eq[i])
    var lo_sorted = _sample_sort_desc_ids(lo, w)
    for i in range(len(lo_sorted)):
        out.append(lo_sorted[i])
    return out^


@fieldwise_init
struct _SampleDraw(Copyable, Movable):
    """One draw's outcome: the chosen token and the RNG state to seed the next draw."""

    var token: Int
    var next_state: UInt64


def _sample_draw(
    logits: List[Float64], counts: List[Int],
    temperature: Float64, top_k: Int, top_p: Float64, min_p: Float64,
    repeat_penalty: Float64, presence_penalty: Float64, frequency_penalty: Float64,
    rng_state: UInt64,
) -> _SampleDraw:
    """The whole chain; returns the drawn token + next rng state. The greedy-equivalence contract:
    with top_k=1 this returns EXACTLY the argmax the fused kernel would have chosen -- same values
    (penalties/temperature at their neutral values), strict-greater scan, lowest-id tie-break."""
    var vocab = len(logits)
    var w = List[Float64](capacity=vocab)
    for j in range(vocab):
        w.append(logits[j])

    # Penalties first (llm_sampling's own formulas): Keskar repetition (scale) on every token
    # present in prompt + generation, then OpenAI-style presence/frequency (subtractive, count-
    # scaled). `counts[j] == 0` means untouched.
    for j in range(vocab):
        var c = Float64(counts[j])
        if c > 0.0:
            w[j] = repetition_penalty_scale(w[j], repeat_penalty, 1.0)
        w[j] = token_frequency_penalty(w[j], c, frequency_penalty, presence_penalty)

    # Temperature (llm_sampling.temperature_scale; the entry point routes T<=0 to the greedy
    # kernel and never lands here with it).
    for j in range(vocab):
        w[j] = temperature_scale(w[j], temperature)

    # Candidate index list, ascending ids (the tie-break order every stage relies on).
    var idx = List[Int](capacity=vocab)
    for j in range(vocab):
        idx.append(j)
    var n_cand = vocab
    var sorted_desc = False

    # top-k: keep only the k largest. v1 sorts the full list (the top-p stage needs descending
    # order anyway when it runs) and cuts the prefix.
    if 0 < top_k < n_cand:
        idx = _sample_sort_desc_ids(idx, w)
        sorted_desc = True
        var cut = List[Int](capacity=top_k)
        for i in range(top_k):
            cut.append(idx[i])
        idx = cut^
        n_cand = top_k

    # Softmax over candidates (max-shifted for stability), kept unnormalized until the draw.
    var wmax = w[idx[0]]
    for i in range(1, n_cand):
        if w[idx[i]] > wmax:
            wmax = w[idx[i]]
    var probs = List[Float64](capacity=n_cand)
    var z = 0.0
    for i in range(n_cand):
        var pr = exp(w[idx[i]] - wmax)
        probs.append(pr)
        z += pr

    # min-p: drop candidates below max_prob * min_p (llm_sampling's threshold formula).
    # Candidates are still in ascending-id order here, so take the actual max probability first.
    if min_p > 0.0 and n_cand > 1:
        var pmax = probs[0]
        for i in range(1, n_cand):
            if probs[i] > pmax:
                pmax = probs[i]
        var thr = min_p_threshold(pmax / z, min_p) * z
        var kept_idx = List[Int](capacity=n_cand)
        var kept_probs = List[Float64](capacity=n_cand)
        for i in range(n_cand):
            if probs[i] >= thr:
                kept_idx.append(idx[i])
                kept_probs.append(probs[i])
        if len(kept_idx) > 0:
            idx = kept_idx^
            probs = kept_probs^
            n_cand = len(probs)

    # top-p: smallest prefix of the DESCENDING-sorted candidates whose mass reaches p; the most
    # probable token always survives.
    if 0.0 < top_p < 1.0 and n_cand > 1:
        if not sorted_desc:
            idx = _sample_sort_desc_ids(idx, w)
            var probs_sorted = List[Float64](capacity=n_cand)
            for i in range(n_cand):
                probs_sorted.append(exp(w[idx[i]] - wmax))
            probs = probs_sorted^
        var cum = probs[0]
        var kept = 1
        var i = 1
        while i < n_cand and top_p_cumulative(cum, probs[i] / z, top_p) > 0.0:
            cum += probs[i]
            kept += 1
            i += 1
        n_cand = kept

    # Weighted draw over the survivors.
    var mass = 0.0
    for i in range(n_cand):
        mass += probs[i]
    var rng = _SamplerRng(rng_state)
    var u = rng.uniform() * mass
    var chosen = idx[n_cand - 1]
    var acc = 0.0
    for i in range(n_cand):
        acc += probs[i]
        if u < acc:
            chosen = idx[i]
            break
    return _SampleDraw(chosen, rng.state)


def qwen3_i8_allsimd7_prefill_decode_flat(
    checkpoint_dir: String, max_new_tokens: Int
) -> Qwen3PrefillDecodeResult:
    """Greedy-decode a prompt already folded into `checkpoint_dir/manifest.json`'s own `input_ids`,
    through `_MBQwen3I8AllSimd7Prefill` -- batched `prefill_batch()` for the prompt, then the
    byte-identical `step()` for every generated token. Same failure-mode contract as
    `qwen3_decode.qwen3_i8_allsimd7_decode_flat`: every failure is a returned `status`, never a crash
    and never a silently-wrong answer.

    Project Redline reopening (2026-08-08), "make unresolved plan state unrepresentable" audit: this
    is the ONE function in this file actually wired into the real runtime-library-dispatch catalog
    (`runtime_library_dispatch_generated.mojo`'s own `qwen3_i8_allsimd7_prefill_decode_flat` entry),
    and it used to construct `_MBQwen3I8AllSimd7Prefill` and decode via plain `step()` WITHOUT ever
    calling `resolve_plan` -- relying entirely on the constructor's own default. That was safe only
    because the default happens to be the always-safe `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL`, and only by
    coincidence: nothing in this function's own code said so, so a future change to the literal
    default value inside `_MBQwen3I8AllSimd7Prefill.__init__`'s signature would have silently changed
    what this function does (see `metaldispatch.session_prefill_policy`'s own module docstring
    addendum for the full account -- this was one of the two real call sites that motivated it). Now
    resolved explicitly, immediately after construction, to the SAME `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL`
    this function has always run -- this function's own behavior is completely unchanged; only the
    SOURCE of that behavior moved from "whatever the constructor's default happens to be" to "this
    function's own explicit, self-documenting request".

    PROMOTION DECISION, round 5 (2026-08-08), SUPERSEDED by round 7 below: `PF_ATTN_GROUPED_FA_
    NO_MIRROR`/`PF_GEMM_VECLOAD4_ALL_ROLES` was considered and NOT flipped to despite (a)-(g) of the
    promotion gate all genuinely passing, because that plan's own decode path (`native_kv_decode_
    attn`, which has no split-K/deep-decode occupancy variant) collapses decode throughput ~2.87x
    (~255-257 tok/s -> ~89-100 tok/s) relative to the legacy decode path -- a real, structural
    regression for any generation past ~7 tokens, found by measuring DECODE throughput in a
    throughput context for the first time (every prior driver had hardcoded `max_new_tokens=1` to
    isolate prefill). That finding stands, unchanged, for THAT specific plan -- see `qwen3_i8_
    allsimd7_prefill_decode_flat_af_nomirror_vecload4`'s own docstring, which still carries the full
    account. It is superseded here only in the sense that it motivated the round-7 discovery below,
    not because the ~2.87x no-mirror decode regression stopped being real.

    PROMOTION DECISION, round 7 (2026-08-08): `attention=PF_ATTN_GROUPED_FA_WITH_MIRROR` + `gemm=
    PF_GEMM_VECLOAD4_ALL_ROLES` is DIFFERENT from the round-5 candidate above on the ONE axis that
    mattered: with-mirror populates BOTH KV-cache representations every prefill call, so `self.plan.
    decode` derives to `DECODE_PATH_LEGACY_NATURAL_KV` regardless of `gemm` -- decode always runs the
    legacy path's own stable, already-occupancy-optimized throughput, never the no-mirror plan's
    unoptimized native-KV decode path. This makes vecload4's real, independently-confirmed GEMM
    speedup (a property of prefill's own GEMM-role kernel choice, orthogonal to which attention path
    populated the KV cache that same prefill call also writes) reachable WITHOUT the round-5 decode
    regression. `_apply_m_rows_af` (the with-mirror prefill dispatch table) never consulted `self.
    plan.gemm` before this round -- a real, disclosed wiring gap, closed additively in `session_
    prefill.mojo` (see that method's own docstring) -- so this exact combination had never been
    measured, or even reachable, before round 7.

    Independently re-verified end-to-end before this promotion, one round deeper than the promotion
    gate's own stated criteria (this file's own established discipline -- 5 prior rounds on the
    no-mirror path, each finding something real by checking one level deeper than the checklist):
    (1) a fresh, from-scratch rebuild of all 4 real-Metal regression suites (OFF/`test_metaldispatch_
    session_prefill.mojo` 12/12, with-mirror-AF/`test_metaldispatch_session_prefill_af.mojo` 16/16,
    native-decode-attn integration/`test_metaldispatch_session_prefill_native_decode.mojo` 65/65,
    qwen3-production-path/`test_metaldispatch_qwen3_production_path.mojo` 52/52 blobs-present + 3/3
    blobs-absent) found zero regressions. (2) The one case this combination does NOT win: a pure
    prefill-only workload (`max_new_tokens<=1`, zero real decode steps) -- measured directly, 14
    fresh runs per arm, no-mirror+vecload4 beats with-mirror+vecload4 by a real but modest ~4-5% in
    prefill-only throughput (mean 3419.8 vs 3278.0 tok/s, median 3467.7 vs 3302.0 tok/s -- run-to-run
    noise (CV 3-6.7%) is smaller than this gap, so it is real, not noise, but it is a few percent, not
    the ~2.87x decode-regression scale). `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_vecload4`
    remains the better explicit choice for that one workload shape; this default does not change that
    -- see that function's own docstring. (3) `gemm=PF_GEMM_BM64` requested alongside `attention=
    PF_ATTN_GROUPED_FA_WITH_MIRROR` was verified, not assumed, to be a true structural no-op: two
    fresh instances given an identical prompt, one resolved to with-mirror+`PF_GEMM_ORIGINAL` and one
    to with-mirror+`PF_GEMM_BM64`, produced bit-for-bit identical dispatch counts (21) AND token_id/
    logit -- `PF_GEMM_BM64` genuinely stays no-mirror-only, unaffected by this round's own vecload4
    wiring fix (Gate PP-BM64-NOOP, `test_metaldispatch_qwen3_production_path.mojo`). (4) A deep x
    multi-chunk configuration different from every previously-tested depth/chunk-boundary combination
    -- 3 chunks (120/120/80 = 320 rows, every chunk boundary past the ~32-key split-K threshold) at
    the synthetic scale (Gate PP-DEEP-MULTI, CPU-oracle-verified at every position, all 4 named plans,
    zero divergence), AND a real 547-token checkpoint (SAME weights as the established 256-token
    `qwen3smoke` checkpoint, different `input_ids`/`n_tokens` only) that genuinely crosses `PREFILL_
    MAX_TILE`=512 for the first time in this investigation (2 real `prefill_batch()` chunks: 512+35)
    -- both plans produced BYTE-IDENTICAL generated token streams (OFF vs. this default, 24 tokens)
    with decode throughput statistically indistinguishable (232.25 vs. 232.61 tok/s) and prefill
    ~2.2x faster (1622 vs. 3591 tok/s). No 6th regression found. PROMOTED: this is now the default
    for this function, replacing `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL`. Real, independently-verified
    throughput with this default now ACTIVE (no explicit override), re-measured at 3 of the 6
    previously-established generation lengths, lands in the already-measured (c)-arm ranges (see
    `REALRACE_RESULTS.md`'s "With-mirror + vecload4-all-roles" entry for the full 6-length table this
    reproduces). Rollback, fully explicit and never deleted: `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL` (this
    function's own pre-round-7 behavior) stays reachable via `qwen3_i8_allsimd7_prefill_decode_flat_
    af(checkpoint_dir, max_new_tokens, False)` or `..._af_vecload4(checkpoint_dir, max_new_tokens,
    False, False)`; the original with-mirror-without-vecload4 plan via `..._af(checkpoint_dir,
    max_new_tokens, True)`; both no-mirror variants via `..._af_nomirror`/`..._af_nomirror_vecload4`
    -- every plan this investigation has ever measured remains one explicit call away, exactly this
    file's own established "genuine rollback, not a deleted path" discipline."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat runs ONLY"
            + " Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── round 7 (2026-08-08): the default flips here, from `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL`
            # to `PF_ATTN_GROUPED_FA_WITH_MIRROR`/`PF_GEMM_VECLOAD4_ALL_ROLES` -- see this function's
            # own docstring's "PROMOTION DECISION, round 7" addendum for the full evidence trail. This
            # plan's own decode path always derives to `DECODE_PATH_LEGACY_NATURAL_KV` (with-mirror
            # populates BOTH KV-cache representations), so this flip is decode-safe -- unlike the
            # round-5 no-mirror candidate, which stays NOT the default (see that same docstring
            # addendum, and `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_vecload4`'s own, for
            # why). Both blob families gracefully degrade to `PF_ATTN_OFF`/`PF_GEMM_ORIGINAL` if
            # linked without them (`resolve_prefill_execution_plan`'s own availability-gated degrade),
            # so this call is safe even on a binary built without `attention_forge`/vecload4 blobs.
            s.resolve_plan(UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_WITH_MIRROR, PF_GEMM_VECLOAD4_ALL_ROLES))

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                # Round 5 (2026-08-08): reads the GENERATED expected count straight off the session
                # itself (`s.expected_decode_dispatch_count`) instead of re-deriving a split-K-aware
                # formula here -- see that method's own docstring in `metaldispatch.session_prefill`
                # for why a separately-maintained formula is exactly what round 4's own adversarial
                # pass found silently wrong for the native-KV decode path (no split-K variant exists
                # for it at all). Correct for BOTH decode paths uniformly; this wrapper no longer
                # needs to know which one is active.
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_i8_allsimd7_prefill_decode_flat_af(
    checkpoint_dir: String, max_new_tokens: Int, use_native_grouped_fa_attn: Bool
) -> Qwen3PrefillDecodeResult:
    """Attention Compiler Plan v1.0, Phase 2C: byte-for-byte the SAME orchestration as
    `qwen3_i8_allsimd7_prefill_decode_flat` above (copy-and-extend, this file's own established
    precedent for `_MBQwen3I8AllSimd7Prefill`'s own relationship to `_MBQwen3I8AllSimd7`), with
    exactly one addition: `s.resolve_plan(UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_WITH_MIRROR if
    use_native_grouped_fa_attn else PF_ATTN_OFF, PF_GEMM_ORIGINAL))`, called once, immediately after
    construction, before any weight upload or dispatch. The ORIGINAL function
    above is left completely untouched -- every existing caller (every benchmark/production build
    that does not know this function exists) keeps running the exact code it always has; this is a
    new, additive entry point, not a modified one.

    DECODE-AFTER-AF-PREFILL GAP, CLOSED (see `_MBQwen3I8AllSimd7Prefill.prefill_batch`'s own docstring
    addendum, and `use_native_grouped_fa_attn`'s own field docstring, for the full account): this
    function used to carry a known, itemized scope limit -- when `use_native_grouped_fa_attn=True`,
    the natural-layout `ck`/`cv` KV cache `step()` (decode) reads was never populated for the
    prompt's own rows, so a `step()` call issued past the prompt read stale/uninitialized cache and
    produced garbage. `_MBQwen3I8AllSimd7Prefill`'s own AF descriptor table now ALSO double-writes
    `ck`/`cv` (via a second, additive dispatch of the byte-unmodified `_pf_ropewrt_kernel`) every
    `prefill_batch()` call made while the flag is `True` -- `step()` itself is unmodified and now
    finds those buffers correctly populated, so `max_new_tokens > 1` with `use_native_grouped_fa_
    attn=True` is no longer expected to produce wrong decode tokens for a SINGLE-CHUNK prompt (one
    `prefill_batch()` call, i.e. `n_prompt <= PREFILL_MAX_TILE` so the `while pos_base < n_prompt`
    loop below runs its body exactly once).

    PRECISELY WHAT REMAINS UNVERIFIED, stated so this is not overclaimed: this function's own
    MULTI-CHUNK prefill loop (`n_prompt > PREFILL_MAX_TILE`, several `prefill_batch(chunk_ids,
    pos_base)` calls with increasing `pos_base`, ALL with the flag on) followed by decode has not
    been exercised end-to-end -- `test_metaldispatch_session_prefill_af.mojo`'s Gate C (the test that
    proves the gap is closed) covers only a single `prefill_batch()` call at `pos_base=0` followed by
    `step()`. Treat multi-chunk AF prefill + decode as not yet certified until that scenario is
    separately tested through this exact entry point."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af runs ONLY"
            + " Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the ONE addition over `qwen3_i8_allsimd7_prefill_decode_flat` above -- see this
            # function's own docstring for the full, honest scope-limit account. Resolved-execution-
            # plan refactor (2026-08-08): this function's own `use_native_grouped_fa_attn: Bool`
            # parameter is unchanged (still the external, CLI-facing API every existing caller of
            # THIS function passes); internally it now translates to a single `UnresolvedPrefillConfig`
            # request (resolved by `resolve_plan` immediately below) instead of setting a raw struct
            # field directly -- see `metaldispatch.session_
            # prefill_policy`'s own module docstring for why the struct-level API changed.
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_WITH_MIRROR if use_native_grouped_fa_attn else PF_ATTN_OFF,
                PF_GEMM_ORIGINAL,
            ))

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                # Round 5 (2026-08-08): reads the GENERATED expected count straight off the session
                # itself (`s.expected_decode_dispatch_count`) instead of re-deriving a split-K-aware
                # formula here -- see that method's own docstring in `metaldispatch.session_prefill`
                # for why a separately-maintained formula is exactly what round 4's own adversarial
                # pass found silently wrong for the native-KV decode path (no split-K variant exists
                # for it at all). Correct for BOTH decode paths uniformly; this wrapper no longer
                # needs to know which one is active.
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4(
    checkpoint_dir: String, max_new_tokens: Int,
    use_native_grouped_fa_attn: Bool, use_vecload4_all_roles: Bool,
    warmup_prefills: Int = 0,
) -> Qwen3PrefillDecodeResult:
    """Project Redline reopening (2026-08-08), round 7: byte-for-byte the SAME orchestration as
    `qwen3_i8_allsimd7_prefill_decode_flat_af` above (copy-and-extend, this file's own established
    precedent -- `flat` -> `flat_af` -> THIS, exactly the same relationship `flat_af_nomirror` ->
    `flat_af_nomirror_vecload4` already has below), with exactly ONE addition: a single `s.resolve_
    plan(UnresolvedPrefillConfig(...))` call that ALSO threads a `gemm` request through, instead of
    always requesting `PF_GEMM_ORIGINAL`. `qwen3_i8_allsimd7_prefill_decode_flat`, `qwen3_i8_allsimd7_
    prefill_decode_flat_af`, `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror`, and `qwen3_i8_
    allsimd7_prefill_decode_flat_af_nomirror_vecload4` are all FOUR left completely untouched by this
    addition -- every existing caller keeps running the exact code it already runs.

    WHY THIS FUNCTION EXISTS: `attention=PF_ATTN_GROUPED_FA_WITH_MIRROR` + `gemm=PF_GEMM_VECLOAD4_
    ALL_ROLES` had never been measured as its own combination before this round, because `_apply_m_
    rows_af` (the with-mirror prefill dispatch table) never consulted `self.plan.gemm` at all -- a
    real, disclosed wiring gap (NOT a design choice; `PF_GEMM_BM64` staying no-mirror-only IS a design
    choice, restated in `metaldispatch.session_prefill_policy`'s own module docstring), now closed
    additively in `session_prefill.mojo`'s `_apply_m_rows_af` (see that method's own docstring for the
    full account). The motivating hypothesis this function exists to measure: with-mirror populates
    BOTH the packed-F16 AND natural-F32 KV caches, so `self.plan.decode` still resolves to `DECODE_
    PATH_LEGACY_NATURAL_KV` regardless of `gemm` -- decode should therefore run at the legacy path's
    own stable throughput (no regression, unlike the no-mirror arm's own documented ~2.87x decode
    collapse -- see `qwen3_i8_allsimd7_prefill_decode_flat`'s own "PROMOTION DECISION" docstring
    addendum), while prefill should still capture vecload4's real, independently-confirmed GEMM speedup
    (a property of which KERNEL executes the GEMM roles, orthogonal to which attention path populated
    the KV cache that prefill call also writes).

    DECODE SCOPE: like every other arm in this file, this function's own decode loop below calls plain
    `s.step()`, UNRESTRICTED, for `max_new_tokens` tokens -- `step()` is plan-aware (round 5) and
    routes on `self.plan.decode`, which for THIS plan is always `DECODE_PATH_LEGACY_NATURAL_KV`
    (derived from `attention` alone, never from `gemm` -- see `_derive_decode_path_for_attention`'s
    own docstring in `metaldispatch.session_prefill_policy`), so this function carries no scope
    restriction analogous to the no-mirror arms' own historical `max_new_tokens=1` caveat."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4 runs"
            + " ONLY Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the ONE addition over `qwen3_i8_allsimd7_prefill_decode_flat_af` above -- see this
            # function's own docstring for the full account. `gemm` now threads through the caller's
            # own `use_vecload4_all_roles` instead of being hardcoded to `PF_GEMM_ORIGINAL`.
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_WITH_MIRROR if use_native_grouped_fa_attn else PF_ATTN_OFF,
                PF_GEMM_VECLOAD4_ALL_ROLES if use_vecload4_all_roles else PF_GEMM_ORIGINAL,
            ))

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            # ── Beat-llama.cpp front-2 consistency fix (2026-08-09): same warmup discipline as
            # `flat_af_nomirror_msl` above/below -- see that entry point's own warmup note. A
            # fresh process otherwise measures its first prefill_batch COLD (max_ctx-scaled
            # first-use cost); warmup_prefills=0 reproduces the prior cold measurement exactly.
            for _w in range(warmup_prefills):
                var wpos = 0
                while wpos < n_prompt:
                    var wlen = PREFILL_MAX_TILE
                    if n_prompt - wpos < wlen:
                        wlen = n_prompt - wpos
                    var wids = _slice_ids(prompt_ids, wpos, wlen)
                    var wr = s.prefill_batch(wids, wpos)
                    if wr.status != MB_OK:
                        return _decode_err(
                            wr.status,
                            "warmup prefill_batch(pos_base=" + String(wpos) + ") failed: "
                            + metaldispatch_status_name(wr.status),
                        )
                    wpos += wlen

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                # Round 5 (2026-08-08): reads the GENERATED expected count straight off the session
                # itself (`s.expected_decode_dispatch_count`) instead of re-deriving a split-K-aware
                # formula here -- see that method's own docstring in `metaldispatch.session_prefill`
                # for why a separately-maintained formula is exactly what round 4's own adversarial
                # pass found silently wrong for the native-KV decode path (no split-K variant exists
                # for it at all). Correct for BOTH decode paths uniformly; this wrapper no longer
                # needs to know which one is active.
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_i8_allsimd7_prefill_decode_flat_af_msl(
    checkpoint_dir: String, max_new_tokens: Int,
    use_native_grouped_fa_attn: Bool, use_msl_parity_all_roles: Bool,
) -> Qwen3PrefillDecodeResult:
    """Phase 3 (2026-08-08), hybrid per-role Metal GEMM backend: byte-for-byte the SAME
    orchestration as `qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4` above (copy-and-extend,
    this file's own established precedent), with the `gemm` request threading
    `PF_GEMM_MSL_PARITY_ALL_ROLES` (the three hand-written MSL replicas of llama.cpp's
    `kernel_mul_mm_f16_f32`, shipped through the EXISTING blob mechanism as `mma_forge/generated/
    msl_parity_blob.c`) instead of `PF_GEMM_VECLOAD4_ALL_ROLES` when the caller's own
    `use_msl_parity_all_roles` is set. OPT-IN: nothing about the production default changes --
    `qwen3_i8_allsimd7_prefill_decode_flat` (the real runtime-library-dispatch entry point) is
    untouched, and passing `use_msl_parity_all_roles=False` here resolves EXACTLY the current
    production default (`PF_ATTN_GROUPED_FA_WITH_MIRROR` + `PF_GEMM_VECLOAD4_ALL_ROLES`, when
    `use_native_grouped_fa_attn=True`), which is what makes this entry point double as a
    same-binary baseline/fallback arm. GRACEFUL FALLBACK, the round-4/5 lesson: a binary that
    never links `msl_parity_blob.c` resolves the same MSL request down to
    `PF_GEMM_VECLOAD4_ALL_ROLES` (then the existing BM64/ORIGINAL chain) -- never a hard error;
    see `resolve_prefill_execution_plan`'s own Phase 3 branch. Same decode scope as the vecload4
    arm above: `self.plan.decode` derives from `attention` alone and is always
    `DECODE_PATH_LEGACY_NATURAL_KV` for with-mirror, so `step()` is unrestricted."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af_msl runs"
            + " ONLY Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the ONE difference over `qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4`: the
            # `gemm` request is the OPT-IN MSL-parity tier when asked, else byte-for-byte the
            # current production default's vecload4 tier. A blobs-absent binary degrades the MSL
            # request to that same vecload4 tier in `resolve_prefill_execution_plan` (graceful
            # fallback, never a hard error).
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_WITH_MIRROR if use_native_grouped_fa_attn else PF_ATTN_OFF,
                PF_GEMM_MSL_PARITY_ALL_ROLES if use_msl_parity_all_roles else PF_GEMM_VECLOAD4_ALL_ROLES,
            ))
            # Phase 3 diagnostic (benchmark-facing entry point only, printed BEFORE any timed
            # section): makes the resolved plan externally visible -- the graceful-fallback proof
            # reads exactly this line on a blobs-absent binary (requested MSL -> resolved gemm=2
            # PF_GEMM_VECLOAD4_ALL_ROLES), and the routing proof on a blobs-present one (resolved
            # gemm=3 PF_GEMM_MSL_PARITY_ALL_ROLES). Attention: 0=OFF, 1=with-mirror, 2=no-mirror.
            print("  resolved plan: attention =", s.plan.attention,
                  ", gemm =", s.plan.gemm, "(3 = PF_GEMM_MSL_PARITY_ALL_ROLES)")

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl(
    checkpoint_dir: String, max_new_tokens: Int,
    use_native_grouped_fa_attn_no_mirror: Bool, use_msl_parity_all_roles: Bool,
    warmup_prefills: Int = 0,
) -> Qwen3PrefillDecodeResult:
    """Beat-llama.cpp campaign (2026-08-08 night): the COMBINATION arm -- byte-for-byte the SAME
    orchestration as `qwen3_i8_allsimd7_prefill_decode_flat_af_msl` above (copy-and-extend, this
    file's own established precedent), with the `attention` request flipped from the with-mirror
    tier to `PF_ATTN_GROUPED_FA_NO_MIRROR` when the caller's own `use_native_grouped_fa_attn_no_
    mirror` is set -- i.e. the two landed kernel-side levers together: the mirror-free AF prefill
    table (-5.95 ms GPU at m_rows=256, measured by the campaign's nomirror+MSL counter probe) and
    the MSL-parity GEMM tier. The `gemm` request is unchanged from the MSL entry point above
    (MSL-parity when asked, vecload4 fallback otherwise, same graceful-degrade chain).

    DECODE SCOPE, the property that distinguishes this arm from every earlier no-mirror attempt:
    `self.plan.decode` derives to `DECODE_PATH_NATIVE_PACKED_KV`, so `step()` routes to `_step_
    native_kv_impl` -- which, since this same campaign's split-K wiring, dispatches the flash-
    decoding partial+merge pair at and above `_NATIVE_DECODE_SPLITK_THRESHOLD` keys (the round-5
    ~2.87x decode collapse is FIXED by that kernel, not merely worked around: the campaign's
    measurement shows the no-mirror+vecload4 arm decoding at 265-274 tok/s vs the legacy path's
    252-259 at the race's own depths). Multi-token generation is therefore SAFE on this arm -- no
    `max_new_tokens` clamp -- provided the binary links BOTH `attention_forge/generated/native_
    kv_decode_attn_blob.c` AND `native_kv_decode_attn_splitk_blob.c` (the naive table runs below
    threshold or when only the naive blob is present; a binary linking NEITHER decode blob degrades
    the no-mirror request to `PF_ATTN_OFF` at resolution, per `resolve_prefill_execution_plan`'s
    own gate, and generation proceeds on the OFF path)."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl runs"
            + " ONLY Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the ONE difference over `qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4`: the
            # `gemm` request is the OPT-IN MSL-parity tier when asked, else byte-for-byte the
            # current production default's vecload4 tier. A blobs-absent binary degrades the MSL
            # request to that same vecload4 tier in `resolve_prefill_execution_plan` (graceful
            # fallback, never a hard error).
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_NO_MIRROR if use_native_grouped_fa_attn_no_mirror else PF_ATTN_OFF,
                PF_GEMM_MSL_PARITY_ALL_ROLES if use_msl_parity_all_roles else PF_GEMM_VECLOAD4_ALL_ROLES,
            ))
            # Phase 3 diagnostic (benchmark-facing entry point only, printed BEFORE any timed
            # section): makes the resolved plan externally visible -- the graceful-fallback proof
            # reads exactly this line on a blobs-absent binary (requested MSL -> resolved gemm=2
            # PF_GEMM_VECLOAD4_ALL_ROLES), and the routing proof on a blobs-present one (resolved
            # gemm=3 PF_GEMM_MSL_PARITY_ALL_ROLES). Attention: 0=OFF, 1=with-mirror, 2=no-mirror.
            print("  resolved plan: attention =", s.plan.attention,
                  "(2 = PF_ATTN_GROUPED_FA_NO_MIRROR), gemm =", s.plan.gemm, "(3 = PF_GEMM_MSL_PARITY_ALL_ROLES)")

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            # ── Beat-llama.cpp front-2 consistency fix (2026-08-09): a FRESH process measures
            # its first prefill_batch COLD -- the max_ctx-scaled first-use cost the Front-1 entry
            # already diagnosed and quantified (~57 ms at this race's ctx=512): GPU-buffer
            # first-touch + per-pipeline first-dispatch. llama.cpp's number in this harness is
            # WARM-resident (its server is warmed by the preconditioning requests before any timed
            # run). To measure apples-to-apples, run warmup_prefills UNTIMED full prefills first,
            # bringing buffers/PSOs/DVFS to that same warm state. warmup_prefills=0 (the default)
            # reproduces the prior cold measurement byte-for-byte.
            for _w in range(warmup_prefills):
                var wpos = 0
                while wpos < n_prompt:
                    var wlen = PREFILL_MAX_TILE
                    if n_prompt - wpos < wlen:
                        wlen = n_prompt - wpos
                    var wids = _slice_ids(prompt_ids, wpos, wlen)
                    var wr = s.prefill_batch(wids, wpos)
                    if wr.status != MB_OK:
                        return _decode_err(
                            wr.status,
                            "warmup prefill_batch(pos_base=" + String(wpos) + ") failed: "
                            + metaldispatch_status_name(wr.status),
                        )
                    wpos += wlen

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )



def qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_vecload4(
    checkpoint_dir: String, max_new_tokens: Int,
    use_native_grouped_fa_attn_no_mirror: Bool, use_qkv_proj_bm64: Bool, use_vecload4_all_roles: Bool,
) -> Qwen3PrefillDecodeResult:
    """Project Redline reopening (2026-08-08), step 4: byte-for-byte the SAME orchestration as
    `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror` immediately below (copy-and-extend, this
    file's own established precedent -- `flat` -> `flat_af` -> `flat_af_nomirror` -> THIS), with
    exactly ONE addition over that function's two: a single `s.resolve_plan(UnresolvedPrefillConfig(...))`
    call, translating all three `Bool` parameters into one `UnresolvedPrefillConfig` request (`vecload4 > bm64 >
    original` precedence for the `gemm` field -- see `PF_GEMM_VECLOAD4_ALL_ROLES`'s own docstring in
    `metaldispatch.session_prefill_policy` for the full account), called once, immediately after
    construction, before any weight upload or dispatch. `qwen3_i8_allsimd7_prefill_decode_flat`,
    `qwen3_i8_allsimd7_prefill_decode_flat_af`, and `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror`
    are all THREE left completely untouched by this addition -- every existing caller keeps running
    the exact code it always has, and every existing benchmark driver keeps calling the function it
    already calls, unmodified.

    DECODE SCOPE: this function measures PREFILL throughput (`prefill_tokens_per_sec`) primarily,
    matching every other arm's own measurement methodology so the numbers stay directly comparable --
    its own decode loop below calls plain `s.step()`, UNRESTRICTED, for `max_new_tokens` tokens.
    Round 5 (2026-08-08): before this round, `s.step()` only ever read the natural `ck`/`cv` cache, so
    this function's own docstring used to restrict itself to `max_new_tokens=1` whenever `use_native_
    grouped_fa_attn_no_mirror=True` (a real caller error past that, undetected) -- `s.step()` is now
    plan-aware (see `metaldispatch.session_prefill`'s own module docstring addendum, round 5) and
    routes to the correct implementation automatically based on `s.plan.decode`, so that restriction
    no longer applies: this function is correct for any `max_new_tokens` under any combination of its
    three `Bool` parameters. Real decode-after-no-mirror-prefill correctness, INCLUDING the
    all-4-roles-vecload4 combination specifically, is independently, separately verified by
    `test_metaldispatch_session_prefill_native_decode.mojo`'s own Gate K, which exercises the EXACT
    same implementation `s.step()` routes to for this attention path (`_step_native_kv_impl`, via
    the test-only `step_native_kv` wrapper -- byte-identical code either way, see `metaldispatch.
    session_prefill`'s own module docstring addendum, round 5)."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_vecload4"
            + " runs ONLY Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the ONE addition over `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror` above --
            # see this function's own docstring for the full, honest scope-limit account.
            # Resolved-execution-plan refactor (2026-08-08): this function's own three `Bool`
            # parameters are unchanged (still the external, CLI-facing API); internally they now
            # translate to a single `UnresolvedPrefillConfig` request -- `vecload4 > bm64 > original`
            # precedence, matching `PF_GEMM_VECLOAD4_ALL_ROLES`'s own docstring exactly (this is the
            # SAME precedence the pre-refactor two-boolean version's own nested checks implemented,
            # now expressed as which single enum value gets requested instead of two flags plus an
            # `and not` guard).
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_NO_MIRROR if use_native_grouped_fa_attn_no_mirror else PF_ATTN_OFF,
                PF_GEMM_VECLOAD4_ALL_ROLES if use_vecload4_all_roles
                else PF_GEMM_BM64 if use_qkv_proj_bm64
                else PF_GEMM_ORIGINAL,
            ))

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                # Round 5 (2026-08-08): reads the GENERATED expected count straight off the session
                # itself (`s.expected_decode_dispatch_count`) instead of re-deriving a split-K-aware
                # formula here -- see that method's own docstring in `metaldispatch.session_prefill`
                # for why a separately-maintained formula is exactly what round 4's own adversarial
                # pass found silently wrong for the native-KV decode path (no split-K variant exists
                # for it at all). Correct for BOTH decode paths uniformly; this wrapper no longer
                # needs to know which one is active.
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror(
    checkpoint_dir: String, max_new_tokens: Int,
    use_native_grouped_fa_attn_no_mirror: Bool, use_qkv_proj_bm64: Bool,
) -> Qwen3PrefillDecodeResult:
    """Project Redline reopening, adversarial-hardening follow-up (task step 4): byte-for-byte the
    SAME orchestration as `qwen3_i8_allsimd7_prefill_decode_flat_af` immediately above (copy-and-
    extend, this file's own established precedent), with exactly TWO additions over that function's
    ONE: a single `s.resolve_plan(UnresolvedPrefillConfig(...))` call translating both `Bool` parameters
    into one `UnresolvedPrefillConfig` request, called once, immediately after construction, before any weight
    upload or dispatch -- see `metaldispatch.session_prefill_policy`'s own module docstring for the
    full account of what each resolved field does. `qwen3_i8_allsimd7_prefill_decode_flat`
    and `qwen3_i8_allsimd7_prefill_decode_flat_af` are BOTH left completely untouched by this addition
    -- every existing caller keeps running the exact code it always has.

    DECODE SCOPE, stated precisely: this function measures PREFILL throughput
    (`prefill_tokens_per_sec`), the SAME quantity `qwen3_i8_allsimd7_prefill_decode_flat_af` was
    already using `MAX_NEW_TOKENS=1` to isolate for its own `USE_AF` arm (see that benchmark driver's
    own module docstring) -- this function's own decode loop below calls plain `s.step()`,
    UNRESTRICTED, for `max_new_tokens` tokens. Round 5 (2026-08-08): before this round, `s.step()`
    only ever read the natural `ck`/`cv` cache, so this function's own docstring used to restrict
    itself to `max_new_tokens=1` when `use_native_grouped_fa_attn_no_mirror=True` (a real caller error
    past that, undetected -- `PF_ATTN_GROUPED_FA_NO_MIRROR` leaves `ck`/`cv` genuinely unwritten) --
    `s.step()` is now plan-aware (see `metaldispatch.session_prefill`'s own module docstring
    addendum, round 5) and routes to the correct implementation automatically based on `s.plan.
    decode`, so that restriction no longer applies: this function is correct for any `max_new_tokens`
    under either combination of its two `Bool` parameters. Real decode-after-no-mirror-prefill
    correctness is independently, separately verified by `test_metaldispatch_session_prefill_native_
    decode.mojo`'s own Gates D-J, which exercise the EXACT same implementation `s.step()` routes to
    for this attention path (`_step_native_kv_impl`, via the test-only `step_native_kv` wrapper --
    byte-identical code either way)."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror runs"
            + " ONLY Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the TWO additions over `qwen3_i8_allsimd7_prefill_decode_flat_af` above -- see this
            # function's own docstring for the full, honest scope-limit account. Resolved-execution-
            # plan refactor (2026-08-08): same translation as `qwen3_i8_allsimd7_prefill_decode_flat_
            # af_nomirror_vecload4`'s own updated body above, minus the vecload4 tier (this function
            # has no `use_vecload4_all_roles` parameter of its own).
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_NO_MIRROR if use_native_grouped_fa_attn_no_mirror else PF_ATTN_OFF,
                PF_GEMM_BM64 if use_qkv_proj_bm64 else PF_GEMM_ORIGINAL,
            ))

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                # Round 5 (2026-08-08): reads the GENERATED expected count straight off the session
                # itself (`s.expected_decode_dispatch_count`) instead of re-deriving a split-K-aware
                # formula here -- see that method's own docstring in `metaldispatch.session_prefill`
                # for why a separately-maintained formula is exactly what round 4's own adversarial
                # pass found silently wrong for the native-KV decode path (no split-K variant exists
                # for it at all). Correct for BOTH decode paths uniformly; this wrapper no longer
                # needs to know which one is active.
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


# ────────────────────────────────────────────────────────────────────────────────────────────
# MODEL-AGNOSTIC variant of `qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl` (copy-and-
# extend, 2026-08-09): byte-for-byte the same orchestration, with the exact-shape check against
# Qwen3-0.6B-Base replaced by structural-consistency checks, so it runs ANY Qwen3-family model
# (verified on Qwen3-1.7B: hidden 2048 / d_ff 6144). Everything else -- manifest parsing, i8
# quantization, f16-twin materialization, split-K GEMM gating, no-mirror AF attention, timing --
# is identical, which is precisely the model-agnostic property under test.
# ────────────────────────────────────────────────────────────────────────────────────────────
comptime _FNV_OFFSET: UInt64 = 0xcbf29ce484222325
comptime _FNV_PRIME: UInt64 = 0x00000100000001B3


def _resident_key_of(
    checkpoint_dir: String, d_model: Int, n_layers: Int, h_q: Int, h_kv: Int,
    d_head: Int, d_ff: Int, vocab_size: Int, max_ctx: Int,
    use_nomirror: Bool, use_msl: Bool,
) -> UInt64:
    """Parity gap 4 (persistent sessions, 2026-08-10): FNV-1a-64 over everything that shapes the
    resident buffers -- checkpoint identity, model dims, context, and the plan request flags.
    Same key => the weights living in the shim's buffer table belong to THIS call; different key
    => teardown and rebuild. 64-bit FNV collisions across a handful of models are negligible, and
    a collision would only reuse buffers of the SAME total layout (same dims are in the key)."""
    var h = _FNV_OFFSET
    var raw = checkpoint_dir.as_bytes()
    for i in range(len(raw)):
        h = (h ^ UInt64(raw[i])) * _FNV_PRIME
    var scalars = List[Int]()
    scalars.append(d_model)
    scalars.append(n_layers)
    scalars.append(h_q)
    scalars.append(h_kv)
    scalars.append(d_head)
    scalars.append(d_ff)
    scalars.append(vocab_size)
    scalars.append(max_ctx)
    scalars.append(Int(use_nomirror))
    scalars.append(Int(use_msl))
    for j in range(len(scalars)):
        var v = UInt64(scalars[j])
        for b in range(8):
            h = (h ^ ((v >> (8 * b)) & 255)) * _FNV_PRIME
    return h


def qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3(
    checkpoint_dir: String, max_new_tokens: Int,
    use_native_grouped_fa_attn_no_mirror: Bool, use_msl_parity_all_roles: Bool,
    wire_prompt_ids: List[Int],
    warmup_prefills: Int = 0,
) -> Qwen3PrefillDecodeResult:
    """Beat-llama.cpp campaign (2026-08-08 night): the COMBINATION arm -- byte-for-byte the SAME
    orchestration as `qwen3_i8_allsimd7_prefill_decode_flat_af_msl` above (copy-and-extend, this
    file's own established precedent), with the `attention` request flipped from the with-mirror
    tier to `PF_ATTN_GROUPED_FA_NO_MIRROR` when the caller's own `use_native_grouped_fa_attn_no_
    mirror` is set -- i.e. the two landed kernel-side levers together: the mirror-free AF prefill
    table (-5.95 ms GPU at m_rows=256, measured by the campaign's nomirror+MSL counter probe) and
    the MSL-parity GEMM tier. The `gemm` request is unchanged from the MSL entry point above
    (MSL-parity when asked, vecload4 fallback otherwise, same graceful-degrade chain).

    DECODE SCOPE, the property that distinguishes this arm from every earlier no-mirror attempt:
    `self.plan.decode` derives to `DECODE_PATH_NATIVE_PACKED_KV`, so `step()` routes to `_step_
    native_kv_impl` -- which, since this same campaign's split-K wiring, dispatches the flash-
    decoding partial+merge pair at and above `_NATIVE_DECODE_SPLITK_THRESHOLD` keys (the round-5
    ~2.87x decode collapse is FIXED by that kernel, not merely worked around: the campaign's
    measurement shows the no-mirror+vecload4 arm decoding at 265-274 tok/s vs the legacy path's
    252-259 at the race's own depths). Multi-token generation is therefore SAFE on this arm -- no
    `max_new_tokens` clamp -- provided the binary links BOTH `attention_forge/generated/native_
    kv_decode_attn_blob.c` AND `native_kv_decode_attn_splitk_blob.c` (the naive table runs below
    threshold or when only the naive blob is present; a binary linking NEITHER decode blob degrades
    the no-mirror request to `PF_ATTN_OFF` at resolution, per `resolve_prefill_execution_plan`'s
    own gate, and generation proceeds on the OFF path).

    @capability qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3
    complexity: O(n_prompt + max_new_tokens)
    counts:
    - dim max_new_tokens <= RESIDENT_MAX_CONTEXT [kernel_validated]
    @endcapability
    """
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var has_qk_norm: Int
    var tied_embeddings: Int
    var eos_token_id: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        # ── Llama-family convention flags (2026-08-13): both DEFAULT TO THE QWEN3 CONVENTION
        # (1/1), so a manifest written before these keys existed runs byte-for-byte as it always
        # did. The stop token defaults to the Qwen3 constant the same way; the llama-family SDK
        # converter carries the checkpoint's own eos_token_id (TinyLlama's is 2).
        has_qk_norm = json_get_int(config, "has_qk_norm", 1)
        tied_embeddings = json_get_int(config, "tie_word_embeddings", 1)
        eos_token_id = json_get_int(config, "eos_token_id", QWEN3_0_6B_BASE_EOS_TOKEN_ID)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if (has_qk_norm != 0 and has_qk_norm != 1) or (tied_embeddings != 0 and tied_embeddings != 1):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " carries a convention flag (has_qk_norm=" + String(has_qk_norm)
            + ", tie_word_embeddings=" + String(tied_embeddings) + ") that is neither 0 nor 1",
        )
    if eos_token_id < 0 or eos_token_id >= vocab_size:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares eos_token_id=" + String(eos_token_id)
            + " outside the vocab [0, " + String(vocab_size) + ")",
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    # ── Model-agnostic variant (beat-llama.cpp campaign, 2026-08-09): instead of pinning to
    # Qwen3-0.6B-Base's exact shape, validate ONLY the structural invariants the kernels rely on
    # for ANY Qwen3-family model. The split-K GEMM gates (n_q % 256 for o_proj, d_ff % 384 for
    # down_proj) degrade gracefully per-role in `_apply_m_rows_af_nomirror`, so a model whose dims
    # are not divisible simply keeps the parity accum kernel for that role -- never a hard error.
    if (h_q % h_kv) != 0:
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "model-agnostic prefill requires num_attention_heads % num_key_value_heads == 0 (GQA);"
            + " got " + String(h_q) + " % " + String(h_kv),
        )
    if (d_model % 32) != 0 or (d_ff % 32) != 0 or ((h_q * d_head) % 32) != 0:
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "model-agnostic prefill requires d_model, d_ff, and n_q=h_q*d_head all divisible by 32"
            + " (GEMM tile alignment); got d_model=" + String(d_model) + " d_ff=" + String(d_ff)
            + " n_q=" + String(h_q * d_head),
        )

    # ── Serving increment (parity gap 2, 2026-08-10): the prompt can arrive over the wire,
    # SEPARATED from the converted checkpoint. A non-empty wire prompt REPLACES the manifest's
    # baked-in input_ids -- one converted weight set then serves every prompt, and the
    # quantized-state cache (keyed by the manifest's hash) stays warm across different-prompt
    # requests. An empty wire prompt keeps the baked-in behavior byte-for-byte.
    if len(wire_prompt_ids) > 0:
        # Wire arguments arrive as immutable borrows; take an explicit element-wise copy and MOVE
        # it into place (List has no implicit copy).
        var wire_copy = List[Int](capacity=len(wire_prompt_ids))
        for i in range(len(wire_prompt_ids)):
            wire_copy.append(wire_prompt_ids[i])
        prompt_ids = wire_copy^
        n_prompt = len(prompt_ids)

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            # ── Parity gap 4 (persistent sessions, 2026-08-10): resident weights. A matching
            # resident key adopts the shim's existing buffers in allocation order -- zero Metal
            # traffic, zero re-quantization, zero cache read. A different key tears the old
            # model's buffers down first, so a model switch always starts clean.
            var resident_key = _resident_key_of(
                checkpoint_dir, d_model, n_layers, h_q, h_kv, d_head, d_ff, vocab_size, max_ctx,
                use_native_grouped_fa_attn_no_mirror, use_msl_parity_all_roles,
            )
            var resident_match = resident_key != 0 and _mb_get_resident_key() == resident_key
            if not resident_match and _mb_get_resident_key() != 0:
                _mb_free_all_buffers()
            if resident_match:
                _mb_begin_adopt()
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale,
                UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
                has_qk_norm, tied_embeddings,
            )
            if resident_match:
                _mb_end_adopt()
            # ── the ONE difference over `qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4`: the
            # `gemm` request is the OPT-IN MSL-parity tier when asked, else byte-for-byte the
            # current production default's vecload4 tier. A blobs-absent binary degrades the MSL
            # request to that same vecload4 tier in `resolve_prefill_execution_plan` (graceful
            # fallback, never a hard error).
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_NO_MIRROR if use_native_grouped_fa_attn_no_mirror else PF_ATTN_OFF,
                PF_GEMM_MSL_PARITY_ALL_ROLES if use_msl_parity_all_roles else PF_GEMM_VECLOAD4_ALL_ROLES,
            ))
            # Phase 3 diagnostic (benchmark-facing entry point only, printed BEFORE any timed
            # section): makes the resolved plan externally visible -- the graceful-fallback proof
            # reads exactly this line on a blobs-absent binary (requested MSL -> resolved gemm=2
            # PF_GEMM_VECLOAD4_ALL_ROLES), and the routing proof on a blobs-present one (resolved
            # gemm=3 PF_GEMM_MSL_PARITY_ALL_ROLES). Attention: 0=OFF, 1=with-mirror, 2=no-mirror.
            print("  resolved plan: attention =", s.plan.attention,
                  "(2 = PF_ATTN_GROUPED_FA_NO_MIRROR), gemm =", s.plan.gemm, "(3 = PF_GEMM_MSL_PARITY_ALL_ROLES)")

            var rt = rope_table(d_head, max_ctx, theta)

            # ── Parity cheap wins (2026-08-10): quantized-state cache. A VALID
            # `weights_i8.cache` next to the manifest restores the EXACT post-quantization device
            # bytes (~1 byte/param, zero quantization arithmetic); anything else -- missing file,
            # bad magic, stale manifest hash, mismatched dims, wrong length, short read, any
            # error -- falls through to the f64 path below, which then WRITES the cache
            # best-effort for the next call. Never a hard error either way: the cache is a load-
            # time optimization, not part of the correctness contract.
            var cache_path = checkpoint_dir + "/weights_i8.cache"
            var loaded_from_cache = False
            if resident_match:
                # The resident buffers already hold this model's weights + rope tables.
                loaded_from_cache = True
            else:
                try:
                    var cf = open(cache_path, "r")
                    var header = cf.read_bytes(_I8_CACHE_HEADER_BYTES)
                    if (
                        len(header) == _I8_CACHE_HEADER_BYTES
                        and _i8_cache_magic_ok(header)
                        and _le64(header, 40) == n_layers
                        and _le64(header, 48) == d_model
                        and _le64(header, 56) == h_q
                        and _le64(header, 64) == h_kv
                        and _le64(header, 72) == d_head
                        and _le64(header, 80) == d_ff
                        and _le64(header, 88) == vocab_size
                        and _sha256_matches(header, _sha256_of_string(manifest))
                        and _le64(header, 96) == s.quantized_state_bytes()
                    ):
                        var state_bytes = _le64(header, 96)
                        var state = List[UInt8](capacity=state_bytes)
                        var remaining = state_bytes
                        var read_ok = True
                        while read_ok and remaining > 0:
                            var take = _I8_CACHE_CHUNK_BYTES
                            if remaining < take:
                                take = remaining
                            var chunk = cf.read_bytes(take)
                            if len(chunk) != take:
                                read_ok = False
                            else:
                                for i in range(take):
                                    state.append(chunk[i])
                            remaining -= take
                        cf.close()
                        if read_ok and s.load_quantized_state(state^) == MB_OK:
                            var rope_status = s.upload_rope_tables(
                                rt.cos_table, rt.sin_table, max_ctx
                            )
                            loaded_from_cache = rope_status == MB_OK
                    else:
                        cf.close()
                except:
                    loaded_from_cache = False

            if not loaded_from_cache:
                var embed_table = _load_tensor(
                    blob_path, tensors_obj, "model.embed_tokens.weight"
                )
                var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

                var up_status = s.upload_globals(
                    embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
                )
                if up_status != MB_OK:
                    return _decode_err(
                        up_status,
                        "upload_globals failed: " + metaldispatch_status_name(up_status),
                    )

                # Llama-family untied lm_head (2026-08-13): the checkpoint's OWN output
                # projection, quantized into the session's separate lm_head buffer pair. A tied
                # model (has_qk_norm-style flag tie_word_embeddings=1) never reaches this.
                if tied_embeddings == 0:
                    var lm_head_table = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
                    var lm_status = s.upload_lm_head(lm_head_table)
                    if lm_status != MB_OK:
                        return _decode_err(
                            lm_status,
                            "upload_lm_head failed: " + metaldispatch_status_name(lm_status),
                        )

                for layer in range(n_layers):
                    var prefix = "model.layers." + String(layer) + "."
                    var ln1 = _load_tensor(
                        blob_path, tensors_obj, prefix + "input_layernorm.weight"
                    )
                    var ln2 = _load_tensor(
                        blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                    )
                    # Llama-family (2026-08-13): a has_qk_norm=0 checkpoint has NO q_norm/k_norm
                    # tensors -- the session runs its ropewrt kernels with the norm block skipped
                    # and never reads these gains, so ones fill the upload slot harmlessly.
                    var qn = List[Float64]()
                    var kn = List[Float64]()
                    if has_qk_norm == 1:
                        qn = _load_tensor(
                            blob_path, tensors_obj, prefix + "self_attn.q_norm.weight"
                        )
                        kn = _load_tensor(
                            blob_path, tensors_obj, prefix + "self_attn.k_norm.weight"
                        )
                    else:
                        for _i in range(d_head):
                            qn.append(1.0)
                            kn.append(1.0)
                    var wq = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.q_proj.weight"
                    )
                    var wk = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.k_proj.weight"
                    )
                    var wv = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.v_proj.weight"
                    )
                    var wo = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.o_proj.weight"
                    )
                    var wg = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.gate_proj.weight"
                    )
                    var wu = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.up_proj.weight"
                    )
                    var wd = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.down_proj.weight"
                    )
                    var layer_status = s.upload_layer(
                        layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                    )
                    if layer_status != MB_OK:
                        return _decode_err(
                            layer_status,
                            "upload_layer " + String(layer) + " failed: "
                            + metaldispatch_status_name(layer_status),
                        )

                _ = s.seal()

                # Best-effort: persist the exact post-quantization device bytes so the next call
                # on this converted checkpoint skips the f64 read + quantization entirely. A
                # write failure (read-only dir, disk full) must never fail the decode itself.
                try:
                    var state_out = s.dump_quantized_state()
                    var header_out = List[UInt8](capacity=_I8_CACHE_HEADER_BYTES)
                    for _h in range(_I8_CACHE_HEADER_BYTES):
                        header_out.append(0)
                    header_out[0] = 65  # 'A'
                    header_out[1] = 76  # 'L'
                    header_out[2] = 71  # 'G'
                    header_out[3] = 73  # 'I'
                    header_out[4] = 56  # '8'
                    header_out[5] = 67  # 'C'
                    header_out[6] = 48  # '0'
                    header_out[7] = 49  # '1'
                    var digest = _sha256_of_string(manifest)
                    for _d in range(32):
                        header_out[8 + _d] = UInt8(digest[_d])
                    var header_fields = List[Int]()
                    header_fields.append(n_layers)
                    header_fields.append(d_model)
                    header_fields.append(h_q)
                    header_fields.append(h_kv)
                    header_fields.append(d_head)
                    header_fields.append(d_ff)
                    header_fields.append(vocab_size)
                    header_fields.append(len(state_out))
                    for _f in range(len(header_fields)):
                        for _b in range(8):
                            header_out[40 + _f * 8 + _b] = UInt8(
                                (header_fields[_f] >> (8 * _b)) & 255
                            )
                    var wf = open(cache_path, "w")
                    wf.write_bytes(Span[UInt8, origin_of(header_out)](
                        ptr=header_out.unsafe_ptr(), length=_I8_CACHE_HEADER_BYTES
                    ))
                    var written = 0
                    while written < len(state_out):
                        var take = _I8_CACHE_CHUNK_BYTES
                        if len(state_out) - written < take:
                            take = len(state_out) - written
                        wf.write_bytes(Span[UInt8, origin_of(state_out)](
                            ptr=state_out.unsafe_ptr() + written, length=take
                        ))
                        written += take
                    wf.close()
                except:
                    pass
                _mb_set_resident_key(resident_key)
            else:
                _ = s.seal()
                _mb_set_resident_key(resident_key)

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            # ── Beat-llama.cpp front-2 consistency fix (2026-08-09): a FRESH process measures
            # its first prefill_batch COLD -- the max_ctx-scaled first-use cost the Front-1 entry
            # already diagnosed and quantified (~57 ms at this race's ctx=512): GPU-buffer
            # first-touch + per-pipeline first-dispatch. llama.cpp's number in this harness is
            # WARM-resident (its server is warmed by the preconditioning requests before any timed
            # run). To measure apples-to-apples, run warmup_prefills UNTIMED full prefills first,
            # bringing buffers/PSOs/DVFS to that same warm state. warmup_prefills=0 (the default)
            # reproduces the prior cold measurement byte-for-byte.
            for _w in range(warmup_prefills):
                var wpos = 0
                while wpos < n_prompt:
                    var wlen = PREFILL_MAX_TILE
                    if n_prompt - wpos < wlen:
                        wlen = n_prompt - wpos
                    var wids = _slice_ids(prompt_ids, wpos, wlen)
                    var wr = s.prefill_batch(wids, wpos)
                    if wr.status != MB_OK:
                        return _decode_err(
                            wr.status,
                            "warmup prefill_batch(pos_base=" + String(wpos) + ") failed: "
                            + metaldispatch_status_name(wr.status),
                        )
                    wpos += wlen

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == eos_token_id
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == eos_token_id:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            _mb_end_adopt()
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )






def qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3_sampled(
    checkpoint_dir: String, max_new_tokens: Int,
    temperature: Float64, top_k: Int, top_p: Float64, min_p: Float64,
    repeat_penalty: Float64, presence_penalty: Float64, frequency_penalty: Float64,
    seed: Int, wire_prompt_ids: List[Int],
) -> Qwen3PrefillDecodeResult:
    """Parity gap 3 (sampling, 2026-08-10): the SAMPLED twin of `qwen3_prefill_decode_flat_af_
    nomirror_msl_anyqwen3` -- identical model-agnostic gate, checkpoint load, quantized-state
    cache, and prefill+decode orchestration, but every generated token (the first included) is
    DRAWN from the model's own distribution instead of argmaxed: the tail dispatch swaps from the
    fused lm_head+argmax pair to the logits-emitting twin (`step_logits`/`prefill_batch_logits`),
    and the host-side sampler chain (penalties -> temperature -> top-k -> min-p -> top-p ->
    weighted draw, SplitMix64 seeded) picks the token.

    `temperature <= 0` is GREEDY BY DEFINITION and delegates to the greedy entry point above --
    the sampler is never asked to approximate argmax. `top_k = 1` at any temperature is the
    cross-check gate: it must reproduce the greedy sequence exactly (same logits, strict-greater
    scan, lowest-id tie-break). The per-step dispatch budget the greedy path asserts is exactly
    ONE dispatch lower here (the argmax pair collapses to the single logits dispatch), asserted
    the same way.

    Determinism contract: same checkpoint + prompt + parameters + seed -> byte-identical token
    sequence. Different seeds diverge wherever the distribution has more than one survivor.

    @capability qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3_sampled
    complexity: O(n_prompt + max_new_tokens)
    counts:
    - dim max_new_tokens <= RESIDENT_MAX_CONTEXT [kernel_validated]
    @endcapability
    """
    if temperature <= 0.0:
        return qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3(
            checkpoint_dir, max_new_tokens, True, True, wire_prompt_ids, 0
        )
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var has_qk_norm: Int
    var tied_embeddings: Int
    var eos_token_id: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        # ── Llama-family convention flags (2026-08-13): both DEFAULT TO THE QWEN3 CONVENTION
        # (1/1), so a manifest written before these keys existed runs byte-for-byte as it always
        # did. The stop token defaults to the Qwen3 constant the same way; the llama-family SDK
        # converter carries the checkpoint's own eos_token_id (TinyLlama's is 2).
        has_qk_norm = json_get_int(config, "has_qk_norm", 1)
        tied_embeddings = json_get_int(config, "tie_word_embeddings", 1)
        eos_token_id = json_get_int(config, "eos_token_id", QWEN3_0_6B_BASE_EOS_TOKEN_ID)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if (has_qk_norm != 0 and has_qk_norm != 1) or (tied_embeddings != 0 and tied_embeddings != 1):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " carries a convention flag (has_qk_norm=" + String(has_qk_norm)
            + ", tie_word_embeddings=" + String(tied_embeddings) + ") that is neither 0 nor 1",
        )
    if eos_token_id < 0 or eos_token_id >= vocab_size:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares eos_token_id=" + String(eos_token_id)
            + " outside the vocab [0, " + String(vocab_size) + ")",
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    # ── SAME model-agnostic structural gate as the greedy anyqwen3 arm, byte-for-byte.
    if (h_q % h_kv) != 0:
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "model-agnostic prefill requires num_attention_heads % num_key_value_heads == 0 (GQA);"
            + " got " + String(h_q) + " % " + String(h_kv),
        )
    if (d_model % 32) != 0 or (d_ff % 32) != 0 or ((h_q * d_head) % 32) != 0:
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "model-agnostic prefill requires d_model, d_ff, and n_q=h_q*d_head all divisible by 32"
            + " (GEMM tile alignment); got d_model=" + String(d_model) + " d_ff=" + String(d_ff)
            + " n_q=" + String(h_q * d_head),
        )

    # ── Serving increment (parity gap 2, 2026-08-10): the prompt can arrive over the wire,
    # SEPARATED from the converted checkpoint. A non-empty wire prompt REPLACES the manifest's
    # baked-in input_ids -- one converted weight set then serves every prompt, and the
    # quantized-state cache (keyed by the manifest's hash) stays warm across different-prompt
    # requests. An empty wire prompt keeps the baked-in behavior byte-for-byte.
    if len(wire_prompt_ids) > 0:
        # Wire arguments arrive as immutable borrows; take an explicit element-wise copy and MOVE
        # it into place (List has no implicit copy).
        var wire_copy = List[Int](capacity=len(wire_prompt_ids))
        for i in range(len(wire_prompt_ids)):
            wire_copy.append(wire_prompt_ids[i])
        prompt_ids = wire_copy^
        n_prompt = len(prompt_ids)

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            # ── Parity gap 4 (persistent sessions, 2026-08-10): resident weights. A matching
            # resident key adopts the shim's existing buffers in allocation order -- zero Metal
            # traffic, zero re-quantization, zero cache read. A different key tears the old
            # model's buffers down first, so a model switch always starts clean.
            # The sampled arm IS the no-mirror + MSL combination by its name: the resident key
            # uses literal flags (this entry point has none of its own).
            var resident_key = _resident_key_of(
                checkpoint_dir, d_model, n_layers, h_q, h_kv, d_head, d_ff, vocab_size, max_ctx,
                True, True,
            )
            var resident_match = resident_key != 0 and _mb_get_resident_key() == resident_key
            if not resident_match and _mb_get_resident_key() != 0:
                _mb_free_all_buffers()
            if resident_match:
                _mb_begin_adopt()
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale,
                UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
                has_qk_norm, tied_embeddings,
            )
            if resident_match:
                _mb_end_adopt()
            # The sampled arm IS the no-mirror + MSL-parity combination, by its name: no flags.
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_MSL_PARITY_ALL_ROLES,
            ))

            var rt = rope_table(d_head, max_ctx, theta)

            # ── SAME quantized-state cache gate + best-effort write as the greedy anyqwen3 arm.
            var cache_path = checkpoint_dir + "/weights_i8.cache"
            var loaded_from_cache = False
            if resident_match:
                # The resident buffers already hold this model's weights + rope tables.
                loaded_from_cache = True
            else:
                try:
                    var cf = open(cache_path, "r")
                    var header = cf.read_bytes(_I8_CACHE_HEADER_BYTES)
                    if (
                        len(header) == _I8_CACHE_HEADER_BYTES
                        and _i8_cache_magic_ok(header)
                        and _le64(header, 40) == n_layers
                        and _le64(header, 48) == d_model
                        and _le64(header, 56) == h_q
                        and _le64(header, 64) == h_kv
                        and _le64(header, 72) == d_head
                        and _le64(header, 80) == d_ff
                        and _le64(header, 88) == vocab_size
                        and _sha256_matches(header, _sha256_of_string(manifest))
                        and _le64(header, 96) == s.quantized_state_bytes()
                    ):
                        var state_bytes = _le64(header, 96)
                        var state = List[UInt8](capacity=state_bytes)
                        var remaining = state_bytes
                        var read_ok = True
                        while read_ok and remaining > 0:
                            var take = _I8_CACHE_CHUNK_BYTES
                            if remaining < take:
                                take = remaining
                            var chunk = cf.read_bytes(take)
                            if len(chunk) != take:
                                read_ok = False
                            else:
                                for i in range(take):
                                    state.append(chunk[i])
                            remaining -= take
                        cf.close()
                        if read_ok and s.load_quantized_state(state^) == MB_OK:
                            var rope_status = s.upload_rope_tables(
                                rt.cos_table, rt.sin_table, max_ctx
                            )
                            loaded_from_cache = rope_status == MB_OK
                    else:
                        cf.close()
                except:
                    loaded_from_cache = False

            if not loaded_from_cache:
                var embed_table = _load_tensor(
                    blob_path, tensors_obj, "model.embed_tokens.weight"
                )
                var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

                var up_status = s.upload_globals(
                    embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
                )
                if up_status != MB_OK:
                    return _decode_err(
                        up_status,
                        "upload_globals failed: " + metaldispatch_status_name(up_status),
                    )

                # Llama-family untied lm_head (2026-08-13): the checkpoint's OWN output
                # projection, quantized into the session's separate lm_head buffer pair. A tied
                # model (has_qk_norm-style flag tie_word_embeddings=1) never reaches this.
                if tied_embeddings == 0:
                    var lm_head_table = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
                    var lm_status = s.upload_lm_head(lm_head_table)
                    if lm_status != MB_OK:
                        return _decode_err(
                            lm_status,
                            "upload_lm_head failed: " + metaldispatch_status_name(lm_status),
                        )

                for layer in range(n_layers):
                    var prefix = "model.layers." + String(layer) + "."
                    var ln1 = _load_tensor(
                        blob_path, tensors_obj, prefix + "input_layernorm.weight"
                    )
                    var ln2 = _load_tensor(
                        blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                    )
                    # Llama-family (2026-08-13): a has_qk_norm=0 checkpoint has NO q_norm/k_norm
                    # tensors -- the session runs its ropewrt kernels with the norm block skipped
                    # and never reads these gains, so ones fill the upload slot harmlessly.
                    var qn = List[Float64]()
                    var kn = List[Float64]()
                    if has_qk_norm == 1:
                        qn = _load_tensor(
                            blob_path, tensors_obj, prefix + "self_attn.q_norm.weight"
                        )
                        kn = _load_tensor(
                            blob_path, tensors_obj, prefix + "self_attn.k_norm.weight"
                        )
                    else:
                        for _i in range(d_head):
                            qn.append(1.0)
                            kn.append(1.0)
                    var wq = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.q_proj.weight"
                    )
                    var wk = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.k_proj.weight"
                    )
                    var wv = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.v_proj.weight"
                    )
                    var wo = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.o_proj.weight"
                    )
                    var wg = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.gate_proj.weight"
                    )
                    var wu = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.up_proj.weight"
                    )
                    var wd = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.down_proj.weight"
                    )
                    var layer_status = s.upload_layer(
                        layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                    )
                    if layer_status != MB_OK:
                        return _decode_err(
                            layer_status,
                            "upload_layer " + String(layer) + " failed: "
                            + metaldispatch_status_name(layer_status),
                        )

                _ = s.seal()

                try:
                    var state_out = s.dump_quantized_state()
                    var header_out = List[UInt8](capacity=_I8_CACHE_HEADER_BYTES)
                    for _h in range(_I8_CACHE_HEADER_BYTES):
                        header_out.append(0)
                    header_out[0] = 65  # 'A'
                    header_out[1] = 76  # 'L'
                    header_out[2] = 71  # 'G'
                    header_out[3] = 73  # 'I'
                    header_out[4] = 56  # '8'
                    header_out[5] = 67  # 'C'
                    header_out[6] = 48  # '0'
                    header_out[7] = 49  # '1'
                    var digest = _sha256_of_string(manifest)
                    for _d in range(32):
                        header_out[8 + _d] = UInt8(digest[_d])
                    var header_fields = List[Int]()
                    header_fields.append(n_layers)
                    header_fields.append(d_model)
                    header_fields.append(h_q)
                    header_fields.append(h_kv)
                    header_fields.append(d_head)
                    header_fields.append(d_ff)
                    header_fields.append(vocab_size)
                    header_fields.append(len(state_out))
                    for _f in range(len(header_fields)):
                        for _b in range(8):
                            header_out[40 + _f * 8 + _b] = UInt8(
                                (header_fields[_f] >> (8 * _b)) & 255
                            )
                    var wf = open(cache_path, "w")
                    wf.write_bytes(Span[UInt8, origin_of(header_out)](
                        ptr=header_out.unsafe_ptr(), length=_I8_CACHE_HEADER_BYTES
                    ))
                    var written = 0
                    while written < len(state_out):
                        var take = _I8_CACHE_CHUNK_BYTES
                        if len(state_out) - written < take:
                            take = len(state_out) - written
                        wf.write_bytes(Span[UInt8, origin_of(state_out)](
                            ptr=state_out.unsafe_ptr() + written, length=take
                        ))
                        written += take
                    wf.close()
                except:
                    pass
                _mb_set_resident_key(resident_key)
            else:
                _ = s.seal()
                _mb_set_resident_key(resident_key)

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            # ── Sampling state: the context histogram the penalties read, seeded from the whole
            # prompt, plus the SplitMix64 state this run's draws step.
            var counts = List[Int](capacity=vocab_size)
            for _c in range(vocab_size):
                counts.append(0)
            for i in range(n_prompt):
                counts[prompt_ids[i]] += 1
            var rng_state = UInt64(seed)

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                if pos_base + chunk_len < n_prompt:
                    # Not the last chunk: plain greedy prefill (its token is discarded anyway).
                    var r = s.prefill_batch(chunk_ids, pos_base)
                    if r.status != MB_OK:
                        return _decode_err(
                            r.status,
                            "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                            + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                        )
                else:
                    # Last chunk: logits tail, then DRAW the first generated token.
                    var lr = s.prefill_batch_logits(chunk_ids, pos_base)
                    if lr.status != MB_OK:
                        return _decode_err(
                            lr.status,
                            "prefill_batch_logits(pos_base=" + String(pos_base) + ", m_rows="
                            + String(chunk_len) + ") failed: " + metaldispatch_status_name(lr.status),
                        )
                    var draw0 = _sample_draw(
                        lr.logits, counts, temperature, top_k, top_p, min_p,
                        repeat_penalty, presence_penalty, frequency_penalty, rng_state,
                    )
                    first_tok = draw0.token
                    rng_state = draw0.next_state
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            counts[first_tok] += 1
            var stopped_on_eos = first_tok == eos_token_id
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step_logits(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step_logits(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    var draw = _sample_draw(
                        r2.logits, counts, temperature, top_k, top_p, min_p,
                        repeat_penalty, presence_penalty, frequency_penalty, rng_state,
                    )
                    rng_state = draw.next_state
                    generated_ids.append(draw.token)
                    counts[draw.token] += 1
                    n_decoded += 1
                    if draw.token == eos_token_id:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                var n_keys_last = n_prompt + (n_decoded - 1)
                # The sampled tail is exactly ONE dispatch fewer than the greedy tail (the argmax
                # pair collapses to the single logits dispatch) -- asserted the same way.
                var expected_budget = s.expected_decode_dispatch_count(n_keys_last) - 1
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected sampled decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            _mb_end_adopt()
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_batched_prefill_decode_anyqwen3(
    checkpoint_dir: String, max_new_tokens: Int,
    use_msl_parity_all_roles: Bool,
    wire_prompt_ids: List[Int], prompt_lens: List[Int],
) -> Qwen3PrefillDecodeResult:
    """Beat-llama.cpp campaign concurrent front (2026-08-11): BATCHED decode -- B sequences share
ONE weight sweep per token. Copy-and-extend of `qwen3_prefill_decode_flat_af_nomirror_msl_
anyqwen3` (this file's own established precedent for a new arm), identical checkpoint load /
model-agnostic gate / quantized-state cache / resident adoption, with the single-stream
prefill+step loop REPLACED by the Slipstream Phase-3 batched path: each sequence's prompt is
ingested into its own slot of the per-layer batched KV caches via
`prefill_batch_batched_ingest` (the production AF-nomirror prefill table with its KV pointer
args temporarily retargeted per sequence), then ALL B sequences generate together through
`step_batched` -- every projection is the prefill tiled-GEMM shape at m_rows=B, attention is
the per-sequence flash-decoding pair, one descriptor-table submission per token for all B.

Wire contract: `wire_prompt_ids` is the FLAT concatenation of the B prompts and `prompt_lens`
their lengths (len(prompt_lens) == B, sum(prompt_lens) == len(wire_prompt_ids)); a wire prompt
is REQUIRED (there is no baked-in batch). B is bounded by `BATCH_DECODE_MAX_SEQS` (32). The
attention plan is FORCED to `PF_ATTN_GROUPED_FA_NO_MIRROR` -- the only plan paired with the
batched decode caches.

Result contract: `token_ids` carries the FLAT concatenation of the B generated sequences, each
exactly `max_new_tokens` long (v1 generates the full length for every sequence; there is no
per-sequence early stop on EOS -- race prompts are base-model continuations that do not emit
EOS inside the race horizon). `decode_tokens_per_sec` is the SYSTEM throughput: B sequences x
decode steps / decode wall. `prefill_tokens_per_sec` covers all B ingests. `n_prompt` is the
TOTAL prompt tokens across the batch. `prefill_chunks` reports B (one ingest per sequence).

    @capability qwen3_batched_prefill_decode_anyqwen3
    complexity: O(sum(prompt_lens) + B * max_new_tokens)
    counts:
    - dim max_new_tokens <= RESIDENT_MAX_CONTEXT [kernel_validated]
    @endcapability
    """
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var has_qk_norm: Int
    var tied_embeddings: Int
    var eos_token_id: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
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
        n_prompt = json_get_int(config, "n_tokens", -1)
        # ── Llama-family convention flags (2026-08-13): both DEFAULT TO THE QWEN3 CONVENTION
        # (1/1), so a manifest written before these keys existed runs byte-for-byte as it always
        # did. The stop token defaults to the Qwen3 constant the same way; the llama-family SDK
        # converter carries the checkpoint's own eos_token_id (TinyLlama's is 2).
        has_qk_norm = json_get_int(config, "has_qk_norm", 1)
        tied_embeddings = json_get_int(config, "tie_word_embeddings", 1)
        eos_token_id = json_get_int(config, "eos_token_id", QWEN3_0_6B_BASE_EOS_TOKEN_ID)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if (has_qk_norm != 0 and has_qk_norm != 1) or (tied_embeddings != 0 and tied_embeddings != 1):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " carries a convention flag (has_qk_norm=" + String(has_qk_norm)
            + ", tie_word_embeddings=" + String(tied_embeddings) + ") that is neither 0 nor 1",
        )
    if eos_token_id < 0 or eos_token_id >= vocab_size:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares eos_token_id=" + String(eos_token_id)
            + " outside the vocab [0, " + String(vocab_size) + ")",
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    # ── Model-agnostic variant (beat-llama.cpp campaign, 2026-08-09): instead of pinning to
    # Qwen3-0.6B-Base's exact shape, validate ONLY the structural invariants the kernels rely on
    # for ANY Qwen3-family model. The split-K GEMM gates (n_q % 256 for o_proj, d_ff % 384 for
    # down_proj) degrade gracefully per-role in `_apply_m_rows_af_nomirror`, so a model whose dims
    # are not divisible simply keeps the parity accum kernel for that role -- never a hard error.
    if (h_q % h_kv) != 0:
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "model-agnostic prefill requires num_attention_heads % num_key_value_heads == 0 (GQA);"
            + " got " + String(h_q) + " % " + String(h_kv),
        )
    if (d_model % 32) != 0 or (d_ff % 32) != 0 or ((h_q * d_head) % 32) != 0:
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "model-agnostic prefill requires d_model, d_ff, and n_q=h_q*d_head all divisible by 32"
            + " (GEMM tile alignment); got d_model=" + String(d_model) + " d_ff=" + String(d_ff)
            + " n_q=" + String(h_q * d_head),
        )

    # ── Beat-llama.cpp campaign concurrent front (2026-08-11): the batched arm REQUIRES the
    # prompts over the wire -- `wire_prompt_ids` is the FLAT concatenation of the B prompts,
    # `prompt_lens` their per-sequence lengths. The manifest's baked-in input_ids is never used
    # here (there is no baked-in BATCH).
    var B = len(prompt_lens)
    if B < 1 or B > BATCH_DECODE_MAX_SEQS:
        return _decode_err(
            MB_ERR_CONTEXT_FULL,
            "batched decode requires 1 <= B <= " + String(BATCH_DECODE_MAX_SEQS) + ", got " + String(B),
        )
    if len(wire_prompt_ids) < 1:
        return _decode_err(
            MB_ERR_UPLOAD_LENGTH,
            "batched decode requires a non-empty wire prompt (flat concatenation of B prompts)",
        )
    var lens_sum = 0
    var min_len = -1
    for b in range(B):
        if prompt_lens[b] < 1:
            return _decode_err(
                MB_ERR_UPLOAD_LENGTH,
                "batched decode prompt_lens[" + String(b) + "] must be >= 1",
            )
        lens_sum += prompt_lens[b]
        if min_len < 0 or prompt_lens[b] < min_len:
            min_len = prompt_lens[b]
    if lens_sum != len(wire_prompt_ids):
        return _decode_err(
            MB_ERR_UPLOAD_LENGTH,
            "batched decode sum(prompt_lens)=" + String(lens_sum) + " != len(wire_prompt_ids)="
            + String(len(wire_prompt_ids)),
        )
    var wire_copy = List[Int](capacity=len(wire_prompt_ids))
    for i in range(len(wire_prompt_ids)):
        wire_copy.append(wire_prompt_ids[i])
    prompt_ids = wire_copy^
    n_prompt = len(prompt_ids)

    var scale = 1.0 / sqrt(Float64(d_head))
    # The LONGEST sequence governs the context (all B caches stride at max_ctx).
    var needed_ctx = min_len + max_new_tokens
    for b in range(B):
        if prompt_lens[b] + max_new_tokens > needed_ctx:
            needed_ctx = prompt_lens[b] + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, min_len, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            # ── Parity gap 4 (persistent sessions, 2026-08-10): resident weights. A matching
            # resident key adopts the shim's existing buffers in allocation order -- zero Metal
            # traffic, zero re-quantization, zero cache read. A different key tears the old
            # model's buffers down first, so a model switch always starts clean.
            var resident_key = _resident_key_of(
                checkpoint_dir, d_model, n_layers, h_q, h_kv, d_head, d_ff, vocab_size, max_ctx,
                True, use_msl_parity_all_roles,
            )
            var resident_match = resident_key != 0 and _mb_get_resident_key() == resident_key
            if not resident_match and _mb_get_resident_key() != 0:
                _mb_free_all_buffers()
            if resident_match:
                _mb_begin_adopt()
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale,
                UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
                has_qk_norm, tied_embeddings,
            )
            if resident_match:
                _mb_end_adopt()
            # ── the ONE difference over `qwen3_i8_allsimd7_prefill_decode_flat_af_vecload4`: the
            # `gemm` request is the OPT-IN MSL-parity tier when asked, else byte-for-byte the
            # current production default's vecload4 tier. A blobs-absent binary degrades the MSL
            # request to that same vecload4 tier in `resolve_prefill_execution_plan` (graceful
            # fallback, never a hard error).
            s.resolve_plan(UnresolvedPrefillConfig(
                PF_ATTN_GROUPED_FA_NO_MIRROR,
                PF_GEMM_MSL_PARITY_ALL_ROLES if use_msl_parity_all_roles else PF_GEMM_VECLOAD4_ALL_ROLES,
            ))
            # Phase 3 diagnostic (benchmark-facing entry point only, printed BEFORE any timed
            # section): makes the resolved plan externally visible -- the graceful-fallback proof
            # reads exactly this line on a blobs-absent binary (requested MSL -> resolved gemm=2
            # PF_GEMM_VECLOAD4_ALL_ROLES), and the routing proof on a blobs-present one (resolved
            # gemm=3 PF_GEMM_MSL_PARITY_ALL_ROLES). Attention: 0=OFF, 1=with-mirror, 2=no-mirror.
            print("  resolved plan: attention =", s.plan.attention,
                  "(2 = PF_ATTN_GROUPED_FA_NO_MIRROR), gemm =", s.plan.gemm, "(3 = PF_GEMM_MSL_PARITY_ALL_ROLES)")

            var rt = rope_table(d_head, max_ctx, theta)

            # ── Parity cheap wins (2026-08-10): quantized-state cache. A VALID
            # `weights_i8.cache` next to the manifest restores the EXACT post-quantization device
            # bytes (~1 byte/param, zero quantization arithmetic); anything else -- missing file,
            # bad magic, stale manifest hash, mismatched dims, wrong length, short read, any
            # error -- falls through to the f64 path below, which then WRITES the cache
            # best-effort for the next call. Never a hard error either way: the cache is a load-
            # time optimization, not part of the correctness contract.
            var cache_path = checkpoint_dir + "/weights_i8.cache"
            var loaded_from_cache = False
            if resident_match:
                # The resident buffers already hold this model's weights + rope tables.
                loaded_from_cache = True
            else:
                try:
                    var cf = open(cache_path, "r")
                    var header = cf.read_bytes(_I8_CACHE_HEADER_BYTES)
                    if (
                        len(header) == _I8_CACHE_HEADER_BYTES
                        and _i8_cache_magic_ok(header)
                        and _le64(header, 40) == n_layers
                        and _le64(header, 48) == d_model
                        and _le64(header, 56) == h_q
                        and _le64(header, 64) == h_kv
                        and _le64(header, 72) == d_head
                        and _le64(header, 80) == d_ff
                        and _le64(header, 88) == vocab_size
                        and _sha256_matches(header, _sha256_of_string(manifest))
                        and _le64(header, 96) == s.quantized_state_bytes()
                    ):
                        var state_bytes = _le64(header, 96)
                        var state = List[UInt8](capacity=state_bytes)
                        var remaining = state_bytes
                        var read_ok = True
                        while read_ok and remaining > 0:
                            var take = _I8_CACHE_CHUNK_BYTES
                            if remaining < take:
                                take = remaining
                            var chunk = cf.read_bytes(take)
                            if len(chunk) != take:
                                read_ok = False
                            else:
                                for i in range(take):
                                    state.append(chunk[i])
                            remaining -= take
                        cf.close()
                        if read_ok and s.load_quantized_state(state^) == MB_OK:
                            var rope_status = s.upload_rope_tables(
                                rt.cos_table, rt.sin_table, max_ctx
                            )
                            loaded_from_cache = rope_status == MB_OK
                    else:
                        cf.close()
                except:
                    loaded_from_cache = False

            if not loaded_from_cache:
                var embed_table = _load_tensor(
                    blob_path, tensors_obj, "model.embed_tokens.weight"
                )
                var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

                var up_status = s.upload_globals(
                    embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
                )
                if up_status != MB_OK:
                    return _decode_err(
                        up_status,
                        "upload_globals failed: " + metaldispatch_status_name(up_status),
                    )

                # Llama-family untied lm_head (2026-08-13): the checkpoint's OWN output
                # projection, quantized into the session's separate lm_head buffer pair. A tied
                # model (has_qk_norm-style flag tie_word_embeddings=1) never reaches this.
                if tied_embeddings == 0:
                    var lm_head_table = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
                    var lm_status = s.upload_lm_head(lm_head_table)
                    if lm_status != MB_OK:
                        return _decode_err(
                            lm_status,
                            "upload_lm_head failed: " + metaldispatch_status_name(lm_status),
                        )

                for layer in range(n_layers):
                    var prefix = "model.layers." + String(layer) + "."
                    var ln1 = _load_tensor(
                        blob_path, tensors_obj, prefix + "input_layernorm.weight"
                    )
                    var ln2 = _load_tensor(
                        blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                    )
                    # Llama-family (2026-08-13): a has_qk_norm=0 checkpoint has NO q_norm/k_norm
                    # tensors -- the session runs its ropewrt kernels with the norm block skipped
                    # and never reads these gains, so ones fill the upload slot harmlessly.
                    var qn = List[Float64]()
                    var kn = List[Float64]()
                    if has_qk_norm == 1:
                        qn = _load_tensor(
                            blob_path, tensors_obj, prefix + "self_attn.q_norm.weight"
                        )
                        kn = _load_tensor(
                            blob_path, tensors_obj, prefix + "self_attn.k_norm.weight"
                        )
                    else:
                        for _i in range(d_head):
                            qn.append(1.0)
                            kn.append(1.0)
                    var wq = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.q_proj.weight"
                    )
                    var wk = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.k_proj.weight"
                    )
                    var wv = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.v_proj.weight"
                    )
                    var wo = _load_tensor(
                        blob_path, tensors_obj, prefix + "self_attn.o_proj.weight"
                    )
                    var wg = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.gate_proj.weight"
                    )
                    var wu = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.up_proj.weight"
                    )
                    var wd = _load_tensor(
                        blob_path, tensors_obj, prefix + "mlp.down_proj.weight"
                    )
                    var layer_status = s.upload_layer(
                        layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                    )
                    if layer_status != MB_OK:
                        return _decode_err(
                            layer_status,
                            "upload_layer " + String(layer) + " failed: "
                            + metaldispatch_status_name(layer_status),
                        )

                _ = s.seal()

                # Best-effort: persist the exact post-quantization device bytes so the next call
                # on this converted checkpoint skips the f64 read + quantization entirely. A
                # write failure (read-only dir, disk full) must never fail the decode itself.
                try:
                    var state_out = s.dump_quantized_state()
                    var header_out = List[UInt8](capacity=_I8_CACHE_HEADER_BYTES)
                    for _h in range(_I8_CACHE_HEADER_BYTES):
                        header_out.append(0)
                    header_out[0] = 65  # 'A'
                    header_out[1] = 76  # 'L'
                    header_out[2] = 71  # 'G'
                    header_out[3] = 73  # 'I'
                    header_out[4] = 56  # '8'
                    header_out[5] = 67  # 'C'
                    header_out[6] = 48  # '0'
                    header_out[7] = 49  # '1'
                    var digest = _sha256_of_string(manifest)
                    for _d in range(32):
                        header_out[8 + _d] = UInt8(digest[_d])
                    var header_fields = List[Int]()
                    header_fields.append(n_layers)
                    header_fields.append(d_model)
                    header_fields.append(h_q)
                    header_fields.append(h_kv)
                    header_fields.append(d_head)
                    header_fields.append(d_ff)
                    header_fields.append(vocab_size)
                    header_fields.append(len(state_out))
                    for _f in range(len(header_fields)):
                        for _b in range(8):
                            header_out[40 + _f * 8 + _b] = UInt8(
                                (header_fields[_f] >> (8 * _b)) & 255
                            )
                    var wf = open(cache_path, "w")
                    wf.write_bytes(Span[UInt8, origin_of(header_out)](
                        ptr=header_out.unsafe_ptr(), length=_I8_CACHE_HEADER_BYTES
                    ))
                    var written = 0
                    while written < len(state_out):
                        var take = _I8_CACHE_CHUNK_BYTES
                        if len(state_out) - written < take:
                            take = len(state_out) - written
                        wf.write_bytes(Span[UInt8, origin_of(state_out)](
                            ptr=state_out.unsafe_ptr() + written, length=take
                        ))
                        written += take
                    wf.close()
                except:
                    pass
                _mb_set_resident_key(resident_key)
            else:
                _ = s.seal()
                _mb_set_resident_key(resident_key)

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            # ── Beat-llama.cpp campaign concurrent front (2026-08-11): per-sequence ingest into
            # the batched KV caches, timed across the whole batch, then the shared decode loop.
            var dispatches_per_token = s.batched_dispatch_count(B)

            var first_toks = List[Int](capacity=B)
            var t_prefill_start = perf_counter_ns()
            var cur = 0
            for b in range(B):
                var L = prompt_lens[b]
                var ids_b = List[Int](capacity=L)
                for i in range(cur, cur + L):
                    ids_b.append(prompt_ids[i])
                var r_ing = s.prefill_batch_batched_ingest(ids_b^, b)
                if r_ing.status != MB_OK:
                    return _decode_err(
                        r_ing.status,
                        "batched ingest seq " + String(b) + " failed: "
                        + metaldispatch_status_name(r_ing.status),
                    )
                first_toks.append(r_ing.token_id)
                cur += L
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            var step_flat = List[Int](capacity=B * max_new_tokens)
            for b in range(B):
                step_flat.append(first_toks[b])
            var cur_toks = first_toks^
            var n_decoded = 1

            var t_decode_start = perf_counter_ns()
            for step in range(1, max_new_tokens):
                # All sequences advance together. The token fed at batch-step `step` is the
                # `step`-th generated token, whose position is prompt_lens[b] + step - 1 -- the
                # SAME convention the single-stream loop above uses (pos = n_prompt + step - 1):
                # the first generated token lands at position L, not L+1.
                var poss = List[Int](capacity=B)
                for b in range(B):
                    poss.append(prompt_lens[b] + step - 1)
                var toks = s.step_batched(cur_toks, poss^)
                for b in range(B):
                    step_flat.append(toks[b])
                cur_toks = toks^
                n_decoded += 1
            var t_decode_end = perf_counter_ns()

            # Transpose step-major [t*B + b] into the DOCUMENTED seq-major contract: B contiguous
            # runs of exactly max_new_tokens generated tokens each.
            var generated = List[Int](capacity=B * n_decoded)
            for b in range(B):
                for t in range(n_decoded):
                    generated.append(step_flat[t * B + b])

            # SYSTEM decode throughput: B sequences stepped together per token interval.
            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(B * decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated^, n_prompt, False, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, B
            )
        except e:
            _mb_end_adopt()
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )
