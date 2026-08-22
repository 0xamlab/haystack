"""qwen3_serve_batched_cuda.mojo — the CONCURRENT CUDA serving driver: the same JSON-lines
subprocess protocol of `benchmarks/llm_smoke/nvidia_race/enterprise_bench.py` (its
`JsonlDriverAdapter`) that `qwen3_serve_cuda.mojo` speaks, but backed by the continuous-
batching stack — `residentk.session_cuda_batched` composed with its captured-graph arm
`residentk.session_cuda_batched_graph._CudaResidentQwen3BatchedGraph` — so up to
`_CUDA_BATCH_DECODE_MAX_SEQS` (32) requests decode together and aggregate tok/s scales with
concurrency instead of being pinned at the batch-1 serial rate. The batch-1 driver is
byte-unmodified; this is an additive second binary.

Protocol — byte-compatible with enterprise_bench.py's JsonlDriverAdapter (identical to the
batch-1 driver's; the harness runs UNCHANGED against either binary)
------------------------------------------------------------------------------------
Request (one JSON object per stdin line):

    {"id": int, "prompt": str, "prompt_tokens_approx": int,
     "max_tokens": int, "stream": true}

  * `prompt` is TEXT; the same deterministic byte-window tokenizer contract applies
    (token i = the UTF-8 byte at decoded byte index 4*i; ids in [0, 255]).
  * `prompt_tokens_approx` is authoritative for the prefill length.
  * `stream` is accepted and ignored (no incremental deltas in this protocol).

Response (one JSON object per stdout line, any order — the harness demuxes by `id`):

    {"id": int, "ttft_ms": float, "tpot_ms": float,
     "output_tokens": int, "tokens": [str, ...]}

  * on failure: {"id": int, "error": str}. Non-JSON diagnostic lines are allowed on stdout;
    the harness skips lines that fail json.loads.

Scheduler design — continuous batching on a prefix-addressed slot API, graph-stepped
------------------------------------------------------------------------------------------
The batched session addresses sequences BY SLOT INDEX: decode steps slots [0, B), and
prefill ingests into slots [0, k). Two consequences shape this driver:

  1. ADMISSION PREFILLS are issued by this driver itself, through the SAME prefill kernel
     chain `prefill_batched` runs, but with the slot-offset cache pointers based at the
     admission target (`kv_off = slot * kv_stride_elems`). Admissions go to the contiguous
     FREE TAIL [A, A+k), A = active count, in one grouped call per admit window.

  2. THE PREFIX INVARIANT is maintained by COMPACTION, not by dummy-stepping: when a chunk
     completes sequences mid-batch, the surviving sequences above the holes are moved DOWN
     with a device-to-device copy of their per-layer KV slots (whole-slot copies on the
     context stream — ~1 GB per moved sequence at these shapes, ~1 ms on the A100, and in
     closed-loop uniform-shape cells completions align, so moves are rare). Decode never
     steps junk slots; the graph arm never carries a dummy sequence.

DECODE runs as CAPTURED-GRAPH CHUNKS of up to CHUNK_MAX (64) steps through
`seed_and_run_batched_graph`: one eager STATE seed + K back-to-back replays + one sync per
chunk, instead of K x (1 + n_layers*9 + 3) per-dispatch host submissions — the same replay
physics that took the single-stream arm 71 -> 330 tok/s, applied at B sequences. The chunk
horizon K is the minimum remaining token budget over the active set (capped at CHUNK_MAX),
so at least one sequence completes per chunk and no sequence overshoots max_tokens or the
context; EOS mid-chunk is MASKED on the host side — the log scan truncates the stream at
the EOS token (included), the slot simply keeps consuming its remaining replay steps until
the chunk boundary (the campaign's "fixed-length chunks with EOS mask"). Per-dispatch
`step_batched_tokens` remains the FALLBACK if a graph submission fails, and is the arm the
selftest's single-step checks use.

Main loop (single driver thread — no per-request thread exists or is needed):
    drain stdin (non-blocking) -> compact to a prefix -> admit the pending tail -> step one
    graph chunk -> emit completed responses -> repeat. EOF on stdin drains the remaining
    active sequences, then the driver exits 0.

Timing semantics (driver-reported, per the protocol)
----------------------------------------------------
  * TTFT = wall from the request line's stdin read to the first generated token becoming
    available — the admission prefill, which INCLUDES the lm_head + argmax that produces
    that first token. For a request queued behind a full batch or a running chunk, TTFT
    includes the queue wait — the serving-system semantics the harness intends.
  * TPOT = (last decode step completion - first token availability) / (output_tokens - 1),
    exactly the protocol definition; for a sequence completing inside a graph chunk the
    chunk-boundary sync IS its last step's completion time as seen by the host.
    0.0 when output_tokens == 1.

Stdin semantics — _StdinLines + a poll() drain
----------------------------------------------
The line reader is `_StdinLines` copied VERBATIM from qwen3_serve_cuda.mojo — one
read_bytes(1) per byte, the fix for Mojo 1.0.0 input() dropping buffered bytes past the
first newline (PR #802). What changes is WHEN it is read: a concurrent driver must step the
decode batch whether or not stdin has data, so the loop must never block in a read while
sequences are active. Mojo 1.0.0's std carries no threads, no poll and no non-blocking I/O
(measured: no std.thread / std.concurrency / std.process / usable std.ffi exports), so
readiness is asked of libc directly through C FFI:

    @extern("poll") def _c_poll(fds, nfds, timeout_ms) abi("c") -> Int

  * poll() has a FIXED three-argument signature — deliberate: under local probing the
    variadic ioctl(FIONREAD) form returned EFAULT/garbage through the same FFI path.
  * the pollfd is one 8-byte List[UInt8]: fd @0-3 (0 = stdin), events @4-5 (POLLIN, written
    ONCE at init), revents @6-7 (cleared and re-read around every call; POLLIN=1 on both
    Linux and macOS). poll(fd 0, 1, 0) with timeout 0 is a pure non-blocking check.
  * EOF sets POLLIN|POLLHUP; the drain then reads through _StdinLines, whose "stdin EOF"
    raise flips the loop into drain-and-exit mode.

Correctness gate — --selftest
-----------------------------
  * GATE 1 (the campaign oracle through the serving decode path): the manifest's 256-token
    race prompt is prefilled into slot 0 by this driver's admission prefill and stepped 15
    steps as ONE graph chunk; all 16 generated tokens must match the campaign's known-
    correct 8-id window + 7-id repeat cycle (`_oracle_token`) — "16/16".
  * GATE 2 (concurrent vs batch-1, token-identical): 8 mixed prompts (lengths 3..1000,
    max_tokens 1..64, including the max_tokens=1 edge and staggered completions that
    exercise compaction) are run CONCURRENTLY through this driver's actual scheduler, and
    every response must be token-identical to the SAME request run through the
    single-stream `_CudaResidentQwen3` session — the exact compute path the batch-1 driver
    runs — held resident in-process for the comparison.
  Any mismatch prints FAIL and exits 1.

Build (the CUDA lane recipe, no CUDA toolkit at build time; the batch-1 driver's recipe with
-I attention_forge added — the batched session imports its forge kernels):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine -I attention_forge \\
        benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo \\
        -o qwen3_serve_batched_cuda

--target-accelerator follows the VM's GPU: sm_80 A100 / sm_89 L4. NOTE: a module that
launches kernels through enqueue_function MUST import max.gpu.host directly (the pointer
conformance resolution fails without it) — see the import block below.

CONTEXT CEILING AND VRAM (build-time selection — the batched KV is
32 slots x max_ctx x ~224 KB/position at Qwen3-0.6B's shape):
  * default max_ctx = 4736 — covers chat (approx <= ~1040 with the harness's synth
    overshoot + 256) and rag (approx <= ~4112 + 512); KV ~= 34 GB, total ~= 38 GB — fits
    the A100-40GB. Sized against the harness's ACTUAL prompt lengths: synthesize_prompt
    overshoots the nominal in_tokens by up to one appended sentence (~16 tokens).
  * -D ALGENTA_CTX_1536 — max_ctx = 1536, chat-only ceiling (KV ~= 11 GB), the L4-24GB
    fallback build.
  summar (8192+1024 = 9216 positions) does not fit a 32-slot batched KV on a 40 GB card and
  is out of scope for this driver.

Usage
-----
With the enterprise harness (unchanged):

    python3 benchmarks/llm_smoke/nvidia_race/enterprise_bench.py \\
        --jsonl-driver "$HOME/bserve/qwen3_serve_batched_cuda /tmp/qwen3smoke" \\
        --mix chat --concurrency 1,8,16,32 --requests 64 --timeout 900 --out ~/bserve/out

Standalone selftest (run after every rebuild):

    ./qwen3_serve_batched_cuda /tmp/qwen3smoke --selftest

Standalone smoke (one request over the protocol):

    echo '{"id": 0, "prompt": "The capital of France is", "prompt_tokens_approx": 6, \\
           "max_tokens": 16, "stream": true}' | ./qwen3_serve_batched_cuda /tmp/qwen3smoke

Checkpoint: argv[1] is the directory holding `{manifest.json,weights.blob}` — the same dump
prepare_smoke_checkpoint.py writes — or `--checkpoint <dir>`; default /tmp/qwen3smoke.
"""

from std.math import sqrt
from std.sys import argv, exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from std.gpu import block_idx, thread_idx
from std.origin import MutAnyOrigin
# max.gpu.host MUST be imported here directly, not just transitively through the session
# module: enqueue_function's device-pointer conformance resolution only succeeds in a module
# that imports the context/buffer types itself (measured: identical launch calls fail to
# resolve without this import).
from max.gpu.host import DeviceBuffer, DeviceContext, HostBuffer
from json.parser import (
    find_key,
    json_array_tokens,
    json_get_array,
    json_get_float,
    json_get_int,
    json_get_object,
)
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_OK, residentk_status_name
from residentk.session import _LM_BLOCKS, _ceil_div, _resident_preflight
from residentk.session_cuda import (
    CUDA_PREFILL_TILE,
    CUDA_SESSION_BUILD,
    _CudaResidentQwen3,
)
from residentk.session_cuda_batched import (
    _CUDA_BATCH_DECODE_MAX_SEQS,
    _CudaResidentQwen3Batched,
)
from residentk.session_cuda_batched_graph import _CudaResidentQwen3BatchedGraph
from residentk.kernels import (
    _TG,
    _SUBS,
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
    _pf_attn_tiled_kernel_simd,
    _lmhead_argmax_kernel,
    _argmax_reduce_kernel,
)
from residentk.kernels_prefill_f32 import _pf_embed_rows_kernel
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2,
    _pf_gemm_accum_kernel_v2,
    _pf_gemm_swiglu_kernel_v2,
)

comptime DEFAULT_CHECKPOINT_DIR: String = "/tmp/qwen3smoke"
"""The same shared checkpoint dump every other CUDA arm reads; argv[1] (or --checkpoint)
overrides it."""

comptime EOS_TOKEN_ID: Int = 151643
"""Qwen3's end-of-sequence id — the same comptime every other CUDA arm gates on. A generated
EOS stops the request early and IS included in the response's tokens."""

comptime CTX_1536: Bool = is_defined["ALGENTA_CTX_1536"]()
comptime MAX_CTX: Int = 1536 if CTX_1536 else 4736
"""The session's fixed context ceiling, chosen at build time: default 4736 covers chat and
rag INCLUDING the harness's synth prompt overshoot (see the module docstring); ALGENTA_CTX_1536
is the L4-24GB chat-only fallback. The batched KV scales linearly with it."""

comptime CHUNK_MAX: Int = 64
"""The graph-chunk horizon cap: at most this many back-to-back replays per
seed_and_run_batched_graph submission. The actual chunk K is the minimum remaining token
budget over the active set (capped here), so some sequence completes every chunk and new
requests are admitted between chunks."""

comptime POLLIN: Int = 1
comptime POLLERR: Int = 8
comptime POLLHUP: Int = 16
comptime _POLL_READY_MASK: Int = POLLIN | POLLERR | POLLHUP
"""poll() revents bits treated as "stdin is readable": data, EOF (POLLIN|POLLHUP on a closed
pipe), or an error to be surfaced by the read. Identical values on Linux and macOS."""

# ── ASCII byte constants for the request-line parser (json.parser's own spelling) ──
comptime _QUOTE: UInt8 = 34        # "
comptime _BACKSLASH: UInt8 = 92    # backslash


# ── libc poll() through C FFI — Mojo 1.0.0 std carries no readiness API (measured: no
# std.thread / std.concurrency / std.process / usable std.ffi exports). poll() is
# fixed-arity, unlike variadic ioctl(FIONREAD), which misbehaved through the same FFI path
# under local probing (EFAULT on a valid buffer). ──
@extern("poll")
def _c_poll(fds: Int, nfds: Int, timeout_ms: Int) abi("c") -> Int: ...


def _pollfd_new() raises -> List[UInt8]:
    """struct pollfd { int fd; short events; short revents; } as 8 LE bytes: fd=0 (stdin),
    events=POLLIN, revents=0. Little-endian on every target this driver runs on."""
    var pfd = List[UInt8](capacity=8)
    for _ in range(8):
        pfd.append(UInt8(0))
    pfd[4] = UInt8(POLLIN)
    return pfd^


def _stdin_ready(mut pfd: List[UInt8]) raises -> Bool:
    """Non-blocking stdin readiness: poll(fd 0, timeout 0). pollfd byte layout: fd @0-3,
    events @4-5 (POLLIN, set once at init, never touched again), revents @6-7 — revents is
    cleared before each call and read back out of the SAME list storage poll wrote into."""
    pfd[6] = UInt8(0)
    pfd[7] = UInt8(0)
    var rc = _c_poll(Int(pfd.unsafe_ptr()), 1, 0)
    if rc <= 0:
        return False  # 0 = nothing ready; -1 = EINTR etc., retry on the next iteration
    var revents = Int(pfd[6]) | (Int(pfd[7]) << 8)
    return (revents & _POLL_READY_MASK) != 0


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_serve_batched_cuda: " + ctx + " failed, status=" + String(status)
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
        raise Error("qwen3_serve_batched_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error(
            "qwen3_serve_batched_cuda: short read at byte offset " + String(byte_offset)
        )
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    """Read one tensor out of the flat Float64 blob — the same loader shape every other CUDA
    driver uses (a driver helper with hardcoded paths, deliberately copied, not shared)."""
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    # Mojo 1.0.0: perf_counter_ns() returns Int.
    return Float64(ns) / 1.0e6


def _fmt_ms(v: Float64) -> String:
    """Three decimal places (microseconds), as a JSON-safe number string — the same
    round-then-stringify shape the batch-1 driver uses."""
    var rounded = Float64(Int(v * 1000.0 + 0.5)) / 1000.0
    return String(rounded)


# ── the request-line parser: prompt text -> decoded UTF-8 bytes, one O(n) pass —
#    byte-for-byte the batch-1 driver's (same tokenizer contract) ──


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
    quote) — byte-for-byte the batch-1 driver's decoder."""
    var bytes = raw.as_bytes()
    var n = raw.byte_length()
    var bs = List[UInt8]()
    if pos >= n or bytes[pos] != _QUOTE:
        raise Error("qwen3_serve_batched_cuda: 'prompt' is not a JSON string")
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
    """The tokenizer contract, byte-for-byte the batch-1 driver's: first byte of every
    4-byte window of the decoded prompt, ids in [0, 255]."""
    var pos = find_key(raw, "prompt")
    if pos < 0:
        raise Error("qwen3_serve_batched_cuda: request missing 'prompt'")
    var bs = _decode_prompt_bytes(raw, pos)
    var nb = len(bs)
    if nb == 0:
        raise Error("qwen3_serve_batched_cuda: empty prompt")
    var ids = List[Int](capacity=n_tok)
    var i = 0
    while i < n_tok and 4 * i < nb:
        ids.append(Int(bs[4 * i]))
        i += 1
    return ids^


# ── response-line builders — byte-for-byte the batch-1 driver's ──


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


def _copy_ids(ref src: List[Int]) raises -> List[Int]:
    """An owned duplicate of a token list — List is move-only, and pending/active token
    streams stay in their state lists until completion, so moves between structures copy
    (<= 512 Ints at rag shapes: noise next to the GPU work around it)."""
    var out = List[Int](capacity=len(src))
    for i in range(len(src)):
        out.append(src[i])
    return out^


# ── the campaign oracle — restated per driver, the campaign convention; byte-for-byte the
#    function qwen3_batched_cuda.mojo uses ──
comptime ORACLE_WINDOW: Int = 8


# ── compaction's slot KV mover: enqueue_copy has no sub-range form (measured: every
#    overload copies a whole buffer), so slot j -> slot i inside ONE concatenated per-layer
#    KV buffer is this elementwise device copy over the slot's kv_stride_elems window ──
comptime _COPY_TG: Int = 256


def _slot_copy_kernel(
    dst: UnsafePointer[Float32, origin=MutAnyOrigin],
    src: UnsafePointer[Float32, origin=MutAnyOrigin], n_i64: Int64,
):
    var n = Int(n_i64)
    var i = Int(block_idx.x) * _COPY_TG + Int(thread_idx.x)
    if i < n:
        dst[i] = src[i]


def _oracle_token(i: Int) -> Int:
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


# ── ADMISSION PREFILL: the session's own prefill kernel chain, retargeted at an arbitrary
#    slot base — see the module docstring's "Scheduler design". The ONLY deviation from
#    `_CudaResidentQwen3Batched.prefill_batched` is `kv_off = (base_slot + b) * stride`. ──


def _prefill_slots(
    mut s: _CudaResidentQwen3Batched, base_slot: Int, ref prompts: List[List[Int]],
) raises -> List[Int]:
    """Prefill each prompt into slot `base_slot + b` and return the greedy FIRST generated
    tokens in order. Sequences run one at a time in stream order (the session's prefill
    scratch is reused); the returned list has exactly len(prompts) elements, or is empty on
    any validation/device failure."""

    @parameter
    if not CUDA_SESSION_BUILD:
        var empty = List[Int]()
        return empty^
    else:
        var B = len(prompts)
        if B < 1 or base_slot < 0 or base_slot + B > _CUDA_BATCH_DECODE_MAX_SEQS:
            var empty = List[Int]()
            return empty^
        for b in range(B):
            if len(prompts[b]) < 1 or len(prompts[b]) > s.max_ctx:
                var empty = List[Int]()
                return empty^
            for i in range(len(prompts[b])):
                if prompts[b][i] < 0 or prompts[b][i] >= s.vocab:
                    var empty = List[Int]()
                    return empty^

        var n_iters = _ceil_div(s.vocab, _LM_BLOCKS * _SUBS)
        var first_tokens = List[Int](capacity=B)

        for b in range(B):
            ref prompt = prompts[b]
            var n_prompt = len(prompt)
            var kv_off = (base_slot + b) * s.kv_stride_elems
            var pos = 0
            var last_m = 0
            while pos < n_prompt:
                var m = CUDA_PREFILL_TILE
                if n_prompt - pos < m:
                    m = n_prompt - pos
                last_m = m

                # ── this chunk's token ids, uploaded once ──
                with s.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt[pos + i])
                s.ctx.synchronize()

                # ── the embedding rows, gathered on-device from the resident table ──
                s.ctx.enqueue_function[_pf_embed_rows_kernel](
                    s.pf_hidden.unsafe_ptr(), s.embed.unsafe_ptr(),
                    s.pf_tokens.unsafe_ptr(),
                    Int64(s.d_model), Int64(m),
                    grid_dim=_ceil_div(s.d_model, _TG) * m, block_dim=_TG,
                )

                for layer in range(s.n_layers):
                    ref lw = s.layers[layer]
                    # THIS sequence's KV slot: the unchanged kernels, slot-offset pointers.
                    var ck_b = lw.ck.unsafe_ptr() + kv_off
                    var cv_b = lw.cv.unsafe_ptr() + kv_off

                    # 1 ── rmsnorm(input_layernorm) over every row
                    s.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        s.pf_xn.unsafe_ptr(), s.pf_hidden.unsafe_ptr(),
                        lw.ln1.unsafe_ptr(),
                        Int64(s.d_model), s.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 2 ── fused Q/K/V projection, one tiled GEMM (ASSIGN, v2)
                    s.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                        s.pf_qkv.unsafe_ptr(), s.pf_xn.unsafe_ptr(),
                        lw.w_qkv.unsafe_ptr(),
                        Int64(m), Int64(s.d_model),
                        Int64((s.h_q + 2 * s.h_kv) * s.d_head),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(
                            (s.h_q + 2 * s.h_kv) * s.d_head, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 3 ── q_norm + k_norm + RoPE + the KV-cache write, into the slot
                    s.ctx.enqueue_function[_pf_ropewrt_kernel](
                        s.pf_q_rot.unsafe_ptr(), ck_b, cv_b,
                        s.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        s.cos_t.unsafe_ptr(), s.sin_t.unsafe_ptr(),
                        Int64(pos), Int64(s.h_q), Int64(s.h_kv), Int64(s.d_head),
                        s.eps, Int64(m),
                        Int64(1),  # qk_norm: Qwen3-family only, per-head QK-norm always on
                        grid_dim=(s.h_q + s.h_kv) * m, block_dim=s.d_head,
                    )
                    # 4 ── causal attention over the slot's cache
                    s.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                        s.pf_attn.unsafe_ptr(), s.pf_q_rot.unsafe_ptr(),
                        ck_b, cv_b,
                        Int64(pos), Int64(s.h_q), Int64(s.h_kv), Int64(s.d_head),
                        s.scale, Int64(m),
                        grid_dim=s.h_q * m, block_dim=s.d_head,
                    )
                    # 5 ── o_proj ACCUMULATED into the residual stream (v2)
                    s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                        s.pf_hidden.unsafe_ptr(), s.pf_attn.unsafe_ptr(),
                        lw.w_o.unsafe_ptr(),
                        Int64(m), Int64(s.h_q * s.d_head), Int64(s.d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(s.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 6 ── rmsnorm(post_attention_layernorm) over every row
                    s.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        s.pf_xn.unsafe_ptr(), s.pf_hidden.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(s.d_model), s.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 7 ── gate/up + SwiGLU, one tiled GEMM pair (v2)
                    s.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                        s.pf_act.unsafe_ptr(), s.pf_xn.unsafe_ptr(),
                        lw.w_gu.unsafe_ptr(),
                        Int64(m), Int64(s.d_model), Int64(s.d_ff),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(s.d_ff, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 8 ── down_proj ACCUMULATED into the residual stream (v2)
                    s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                        s.pf_hidden.unsafe_ptr(), s.pf_act.unsafe_ptr(),
                        lw.w_down.unsafe_ptr(),
                        Int64(m), Int64(s.d_ff), Int64(s.d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(s.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                pos += m

            # ── final rmsnorm + lm_head + argmax on this sequence's LAST row ──
            s.ctx.enqueue_function[_lmhead_argmax_kernel](
                s.pf_blk_val.unsafe_ptr(), s.pf_blk_idx.unsafe_ptr(),
                s.pf_hidden.unsafe_ptr() + (last_m - 1) * s.d_model,
                s.final_norm.unsafe_ptr(), s.embed.unsafe_ptr(),
                Int64(s.d_model), Int64(s.vocab), s.eps, Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            s.ctx.enqueue_function[_argmax_reduce_kernel](
                s.pf_out_val.unsafe_ptr(), s.pf_out_idx.unsafe_ptr(),
                s.pf_blk_val.unsafe_ptr(), s.pf_blk_idx.unsafe_ptr(),
                Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG,
            )
            s.ctx.enqueue_copy(s.host_pf_val, s.pf_out_val)
            s.ctx.enqueue_copy(s.host_pf_idx, s.pf_out_idx)
            s.ctx.synchronize()
            var tok = Int(s.host_pf_idx.unsafe_ptr()[0])
            if tok < 0 or tok >= s.vocab:
                var empty = List[Int]()
                return empty^
            first_tokens.append(tok)

        return first_tokens^


# ── the serve state: pending FIFO + per-slot active-sequence records ──


struct _ServeState(Movable):
    """Everything the scheduler tracks, in parallel lists. Move-only (List fields), for the
    same reason the sessions are. Invariant maintained by `compact`: active sequences occupy
    the slot PREFIX [0, n_active) — the graph arm steps slots [0, B), so no holes may exist
    when a chunk is seeded."""

    var n_slots: Int

    # pending queue (FIFO; consumed from pending_head)
    var pending_ids: List[List[Int]]
    var pending_rid: List[Int]
    var pending_t0: List[Int]
    var pending_max_tokens: List[Int]
    var pending_head: Int

    # per-slot active sequence state (the prefix [0, n_active) is active)
    var slot_used: List[Bool]
    var slot_rid: List[Int]
    var slot_t0: List[Int]
    var slot_t_first: List[Int]
    var slot_n_prompt: List[Int]
    var slot_max_tokens: List[Int]
    var slot_last: List[Int]
    var slot_tokens: List[List[Int]]

    var eof: Bool
    var n_active: Int

    # --selftest only: per-rid capture of the completed token streams, for the token-identity
    # diff against the single-stream reference arm (off in serve mode: empty, never written)
    var capture_enabled: Bool
    var capture: List[List[Int]]

    def __init__(out self, n_slots: Int) raises:
        self.n_slots = n_slots
        self.pending_ids = List[List[Int]]()
        self.pending_rid = List[Int]()
        self.pending_t0 = List[Int]()
        self.pending_max_tokens = List[Int]()
        self.pending_head = 0
        self.slot_used = List[Bool]()
        self.slot_rid = List[Int]()
        self.slot_t0 = List[Int]()
        self.slot_t_first = List[Int]()
        self.slot_n_prompt = List[Int]()
        self.slot_max_tokens = List[Int]()
        self.slot_last = List[Int]()
        self.slot_tokens = List[List[Int]]()
        for _ in range(n_slots):
            self.slot_used.append(False)
            self.slot_rid.append(-1)
            self.slot_t0.append(0)
            self.slot_t_first.append(0)
            self.slot_n_prompt.append(0)
            self.slot_max_tokens.append(0)
            self.slot_last.append(0)
            self.slot_tokens.append(List[Int]())
        self.eof = False
        self.n_active = 0
        self.capture_enabled = False
        self.capture = List[List[Int]]()

    def pending_len(self) -> Int:
        return len(self.pending_ids) - self.pending_head

    def enqueue_line(mut self, line: String, t0: Int):
        """Parse one request line into the pending queue; a malformed request gets its error
        response IMMEDIATELY (one response per request, always)."""
        var rid = json_get_int(line, "id", -1)
        var max_tokens = json_get_int(line, "max_tokens", -1)
        var approx = json_get_int(line, "prompt_tokens_approx", -1)
        var ids = List[Int]()
        var err = String()
        if rid < 0:
            err = "request missing integer id"
        elif max_tokens < 1:
            err = "request missing max_tokens"
        elif max_tokens > MAX_CTX:
            err = "max_tokens exceeds the session context"
        elif approx < 1:
            err = "request missing prompt_tokens_approx"
        elif approx + max_tokens > MAX_CTX:
            err = "prompt_tokens_approx + max_tokens exceeds the session context"
        else:
            try:
                ids = _tokenize_request(line, approx)
            except e:
                err = String(e)
            if err.byte_length() == 0 and len(ids) < 1:
                err = "empty prompt"
        if err.byte_length() > 0:
            print(_error_line(rid, err))
            return
        self.pending_ids.append(ids^)
        self.pending_rid.append(rid)
        self.pending_t0.append(t0)
        self.pending_max_tokens.append(max_tokens)

    def _emit_complete(mut self, b: Int, t_last: Int) raises:
        """Emit slot b's response and mark the slot free (compaction closes the hole before
        the next chunk seeds)."""
        var n_gen = len(self.slot_tokens[b])
        var tpot_ms = 0.0
        if n_gen > 1:
            tpot_ms = _ms(t_last - self.slot_t_first[b]) / Float64(n_gen - 1)
        ref generated = self.slot_tokens[b]
        print(_response_line(
            self.slot_rid[b], _ms(self.slot_t_first[b] - self.slot_t0[b]),
            tpot_ms, generated,
        ))
        if self.capture_enabled:
            self.capture[self.slot_rid[b]] = _copy_ids(self.slot_tokens[b])
        self.slot_tokens[b] = List[Int]()
        self.slot_used[b] = False
        self.n_active -= 1

    def compact(mut self, mut gs: _CudaResidentQwen3BatchedGraph) raises:
        """Close every hole below the highest occupied slot by moving the highest sequence
        down into it: a device-side copy of its per-layer KV slot windows (K and V, all
        max_ctx positions of the slot) on the context stream + a host-side metadata swap.
        The copies are stream-ordered before any subsequent prefill/step touches the slots,
        so no extra sync is needed. No-op when the prefix is already clean (the common case
        in uniform-shape closed-loop cells, where completions align and whole batches free
        at once)."""
        var i = 0
        var j = self.n_slots - 1
        while i < self.n_slots and j > i:
            if self.slot_used[i]:
                i += 1
                continue
            while j > i and not self.slot_used[j]:
                j -= 1
            if j <= i:
                break
            # move sequence j down into hole i: both slots' KV windows live in the SAME
            # concatenated per-layer buffer, so this is a sub-range device copy per K/V.
            # The slot window pointers are rebuilt through their addresses (MutAnyOrigin):
            # dst and src alias ONE buffer, and the borrow checker only accepts the pair
            # once the common origin is erased — the graph arm's own pointer-hoisting trick.
            ref inner = gs.inner
            var n_elem = inner.kv_stride_elems
            var grid = (n_elem + _COPY_TG - 1) // _COPY_TG
            for layer in range(inner.n_layers):
                ref lw = inner.layers[layer]
                var ck_i = UnsafePointer[Float32, origin=MutAnyOrigin](
                    unsafe_from_address=Int(lw.ck.unsafe_ptr()) + i * n_elem
                )
                var ck_j = UnsafePointer[Float32, origin=MutAnyOrigin](
                    unsafe_from_address=Int(lw.ck.unsafe_ptr()) + j * n_elem
                )
                var cv_i = UnsafePointer[Float32, origin=MutAnyOrigin](
                    unsafe_from_address=Int(lw.cv.unsafe_ptr()) + i * n_elem
                )
                var cv_j = UnsafePointer[Float32, origin=MutAnyOrigin](
                    unsafe_from_address=Int(lw.cv.unsafe_ptr()) + j * n_elem
                )
                inner.ctx.enqueue_function[_slot_copy_kernel](
                    ck_i, ck_j, Int64(n_elem), grid_dim=grid, block_dim=_COPY_TG,
                )
                inner.ctx.enqueue_function[_slot_copy_kernel](
                    cv_i, cv_j, Int64(n_elem), grid_dim=grid, block_dim=_COPY_TG,
                )
            self.slot_used[i] = True
            self.slot_rid[i] = self.slot_rid[j]
            self.slot_t0[i] = self.slot_t0[j]
            self.slot_t_first[i] = self.slot_t_first[j]
            self.slot_n_prompt[i] = self.slot_n_prompt[j]
            self.slot_max_tokens[i] = self.slot_max_tokens[j]
            self.slot_last[i] = self.slot_last[j]
            self.slot_tokens[i] = _copy_ids(self.slot_tokens[j])
            self.slot_tokens[j] = List[Int]()
            self.slot_used[j] = False
            i += 1
            j -= 1

    def admit(mut self, mut gs: _CudaResidentQwen3BatchedGraph) raises:
        """Admit as many pending requests as fit into the free tail [n_active, ...), in ONE
        grouped admission prefill. Sequences completed by the prefill itself (first token is
        EOS, or max_tokens == 1) emit immediately; the rest join the active set (the caller
        compacts before the next chunk)."""
        if self.pending_head >= len(self.pending_ids):
            return
        var free = self.n_slots - self.n_active
        if free < 1:
            return
        var k = self.pending_len()
        if k > free:
            k = free
        var base = self.n_active
        var prompts = List[List[Int]](capacity=k)
        for g in range(k):
            prompts.append(_copy_ids(self.pending_ids[self.pending_head + g]))
        var firsts = _prefill_slots(gs.inner, base, prompts)
        if len(firsts) != k:
            for g in range(k):
                print(_error_line(self.pending_rid[self.pending_head + g], "prefill failed"))
            self.pending_head += k
            return
        var t_first = perf_counter_ns()
        for g in range(k):
            var h = self.pending_head + g
            var rid = self.pending_rid[h]
            var t0 = self.pending_t0[h]
            var max_tokens = self.pending_max_tokens[h]
            var n_prompt = len(self.pending_ids[h])
            var slot = base + g
            if firsts[g] == EOS_TOKEN_ID or max_tokens == 1:
                var toks = List[Int](capacity=1)
                toks.append(firsts[g])
                print(_response_line(rid, _ms(t_first - t0), 0.0, toks))
                if self.capture_enabled:
                    self.capture[rid] = _copy_ids(toks)
                continue
            self.slot_used[slot] = True
            self.slot_rid[slot] = rid
            self.slot_t0[slot] = t0
            self.slot_t_first[slot] = t_first
            self.slot_n_prompt[slot] = n_prompt
            self.slot_max_tokens[slot] = max_tokens
            self.slot_last[slot] = firsts[g]
            self.slot_tokens[slot] = List[Int](capacity=max_tokens)
            self.slot_tokens[slot].append(firsts[g])
            self.n_active += 1
        self.pending_head += k
        if self.pending_head == len(self.pending_ids):
            # queue fully consumed — release the consumed storage
            self.pending_ids = List[List[Int]]()
            self.pending_rid = List[Int]()
            self.pending_t0 = List[Int]()
            self.pending_max_tokens = List[Int]()
            self.pending_head = 0

    def step_chunk(mut self, mut gs: _CudaResidentQwen3BatchedGraph) raises:
        """ONE graph chunk over all active sequences: K = the minimum remaining token budget
        (capped at CHUNK_MAX), seeded as one STATE upload + K replays + one sync; then a scan
        of the token log applies EOS masking and max_tokens truncation, emits completions,
        and advances the survivors. Falls back to ONE per-dispatch step if the graph
        submission fails."""
        var B = self.n_active
        if B == 0:
            return
        # the chunk horizon: someone completes every chunk; nobody overshoots
        var K = CHUNK_MAX
        var max_ctx = gs.inner.max_ctx
        for b in range(B):
            var rem_tok = self.slot_max_tokens[b] - len(self.slot_tokens[b])
            var rem_ctx = max_ctx - self.slot_n_prompt[b] \
                - len(self.slot_tokens[b]) + 1
            var rem = rem_tok if rem_tok < rem_ctx else rem_ctx
            if rem < K:
                K = rem
        if K < 1:
            K = 1

        var firsts = List[Int](capacity=B)
        var poss = List[Int](capacity=B)
        for b in range(B):
            firsts.append(self.slot_last[b])
            poss.append(self.slot_n_prompt[b] + len(self.slot_tokens[b]) - 1)

        var st = gs.seed_and_run_batched_graph(firsts, poss, K)
        if st != RESIDENT_OK:
            # FALLBACK: one per-dispatch step over the same prefix (K may shrink to 1)
            var toks1 = gs.step_batched_tokens(firsts, poss)
            if len(toks1) != B:
                raise Error(
                    "qwen3_serve_batched_cuda: decode failed (graph status="
                    + String(st) + ", per-dispatch fallback also failed)"
                )
            var t_now = perf_counter_ns()
            for b in range(B):
                self.slot_tokens[b].append(toks1[b])
                self.slot_last[b] = toks1[b]
                if toks1[b] == EOS_TOKEN_ID \
                   or len(self.slot_tokens[b]) == self.slot_max_tokens[b]:
                    self._emit_complete(b, t_now)
            return

        var t_now = perf_counter_ns()
        for b in range(B):
            # EOS masking + max_tokens truncation over the chunk's K logged tokens
            var cap = self.slot_max_tokens[b] - len(self.slot_tokens[b])
            var done = False
            var s = 0
            while s < K and s < cap and not done:
                var t = gs.graph_batched_token(b, s)
                self.slot_tokens[b].append(t)
                self.slot_last[b] = t
                if t == EOS_TOKEN_ID:
                    done = True
                s += 1
            if done or len(self.slot_tokens[b]) == self.slot_max_tokens[b]:
                # completed inside the chunk (EOS or max_tokens); the chunk's remaining
                # replays consumed masked compute on this slot — its KV is freed by
                # compaction and overwritten by the next admission prefill
                self._emit_complete(b, t_now)


def _serve_loop(mut gs: _CudaResidentQwen3BatchedGraph) raises:
    """drain stdin (non-blocking) -> compact -> admit the pending tail -> step one graph
    chunk -> emit completions -> repeat. EOF drains the remaining active sequences, then
    returns."""
    var st = _ServeState(_CUDA_BATCH_DECODE_MAX_SEQS)
    var stdin_lines = _StdinLines()
    var pfd = _pollfd_new()
    while True:
        # 1. non-blocking drain of every request line currently in the pipe
        while not st.eof and _stdin_ready(pfd):
            var line: String
            try:
                line = stdin_lines.next_line()
            except:
                st.eof = True
                break
            if line.byte_length() == 0:
                continue
            var t0 = perf_counter_ns()
            st.enqueue_line(line, t0)
        # 2. close holes left by the previous chunk's completions, then admit
        st.compact(gs)
        st.admit(gs)
        st.compact(gs)  # an admission whose first token was EOS leaves a tail hole
        # 3. step one chunk, or idle-block when there is nothing in flight
        if st.n_active == 0:
            if st.eof:
                return
            if st.pending_len() > 0:
                continue
            var line: String
            try:
                line = stdin_lines.next_line()
            except:
                return  # stdin closed with nothing in flight — the harness is done
            if line.byte_length() > 0:
                var t0 = perf_counter_ns()
                st.enqueue_line(line, t0)
            continue
        st.step_chunk(gs)


# ── VM FIX (copied VERBATIM from qwen3_serve_cuda.mojo, PR #802): Mojo 1.0.0 input() drops
# the buffered bytes past the FIRST newline of each internal refill; at harness concurrency
# >= 8 several lines are always in flight, so requests would be silently lost. The reader is
# ONE byte per read_bytes(1), accumulated to '\n'. ──
struct _StdinLines:
    var f: FileHandle

    def __init__(out self) raises:
        self.f = open("/dev/stdin", "r")

    def next_line(mut self) raises -> String:
        var bs = List[UInt8]()
        while True:
            var chunk = self.f.read_bytes(1)
            if len(chunk) == 0:
                if len(bs) == 0:
                    raise Error("stdin EOF")
                return String(from_utf8=bs^)
            var b = chunk[0]
            if b == UInt8(10):
                return String(from_utf8=bs^)
            bs.append(b)


# ── selftest helpers ──


def _single_stream_tokens(
    mut ss: _CudaResidentQwen3, ref ids: List[Int], max_tokens: Int,
) raises -> List[Int]:
    """The batch-1 driver's exact compute path for one request: prefill + per-dispatch
    greedy steps, EOS-terminated, max_tokens-bounded. The token list --selftest compares
    against (the reference arm)."""
    var prompt = _copy_ids(ids)
    var n_prompt = len(prompt)
    var pf = ss.prefill(prompt^)
    if pf.status != RESIDENT_OK:
        raise Error(
            "qwen3_serve_batched_cuda: selftest single-stream prefill failed, status="
            + String(pf.status)
        )
    var tokens = List[Int](capacity=max_tokens)
    tokens.append(pf.token_id)
    var last = pf.token_id
    if last != EOS_TOKEN_ID:
        while len(tokens) < max_tokens:
            var pos = n_prompt + len(tokens) - 1
            var r = ss.step(last, pos)
            if r.status != RESIDENT_OK:
                raise Error(
                    "qwen3_serve_batched_cuda: selftest single-stream step failed at pos "
                    + String(pos) + ", status=" + String(r.status)
                )
            tokens.append(r.token_id)
            last = r.token_id
            if r.token_id == EOS_TOKEN_ID:
                break
    return tokens^


def _selftest(
    mut gs: _CudaResidentQwen3BatchedGraph, mut ss: _CudaResidentQwen3,
    ref race_prompt: List[Int],
) raises:
    """GATE 1: 16/16 campaign oracle through the serving decode path (admission prefill +
    one graph chunk). GATE 2: 8 mixed prompts run CONCURRENTLY through this driver's actual
    scheduler, token-identical to the single-stream (batch-1) compute path. Any mismatch:
    FAIL + exit 1."""

    # ═══ GATE 1 — the campaign oracle through the serving decode path ═══
    var prompts = List[List[Int]]()
    prompts.append(_copy_ids(race_prompt))
    var firsts = _prefill_slots(gs.inner, 0, prompts)
    if len(firsts) != 1:
        print("RESULT: FAIL — selftest admission prefill failed on the race prompt")
        exit(1)
    var poss = List[Int](capacity=1)
    poss.append(len(race_prompt))
    var st = gs.seed_and_run_batched_graph(firsts, poss, 15)
    if st != RESIDENT_OK:
        print("RESULT: FAIL — selftest graph chunk failed, status=", st)
        exit(1)
    var oracle_bad = 0
    if firsts[0] != _oracle_token(0):
        oracle_bad += 1
    for k in range(15):
        if gs.graph_batched_token(0, k) != _oracle_token(k + 1):
            oracle_bad += 1
    if oracle_bad > 0:
        print("RESULT: FAIL — serving decode path disagrees with the campaign oracle (",
              oracle_bad, "of 16 tokens)")
        exit(1)
    print("  gate 1: PASS — 16/16 campaign oracle tokens through the serving decode path")

    # ═══ GATE 2 — C=8 mixed prompts: concurrent scheduler vs the batch-1 compute path ═══
    var lens = List[Int]()
    var max_toks = List[Int]()
    lens.append(3)
    lens.append(17)
    lens.append(64)
    lens.append(129)
    lens.append(256)
    lens.append(511)
    lens.append(777)
    lens.append(1000)
    max_toks.append(64)
    max_toks.append(33)
    max_toks.append(17)
    max_toks.append(8)
    max_toks.append(5)
    max_toks.append(3)
    max_toks.append(2)
    max_toks.append(1)

    var prompts8 = List[List[Int]]()
    for p in range(8):
        var ids = List[Int](capacity=lens[p])
        for i in range(lens[p]):
            ids.append((lens[p] * 31 + i * 7 + p * 13 + 5) % 256)
        prompts8.append(ids^)

    # the reference arm: each prompt through the single-stream session, in order
    var expected = List[List[Int]]()
    for p in range(8):
        expected.append(_single_stream_tokens(ss, prompts8[p], max_toks[p]))

    # the batched arm: all 8 through THIS driver's actual scheduler, concurrently
    var stt = _ServeState(_CUDA_BATCH_DECODE_MAX_SEQS)
    stt.capture_enabled = True
    for _ in range(8):
        stt.capture.append(List[Int]())
    var t0 = perf_counter_ns()
    for p in range(8):
        var ids = _copy_ids(prompts8[p])
        stt.pending_ids.append(ids^)
        stt.pending_rid.append(p)
        stt.pending_t0.append(t0)
        stt.pending_max_tokens.append(max_toks[p])
    var guard = 0
    while stt.n_active > 0 or stt.pending_len() > 0:
        stt.compact(gs)
        stt.admit(gs)
        stt.compact(gs)
        if stt.n_active > 0:
            stt.step_chunk(gs)
        guard += 1
        if guard > 100000:
            print("RESULT: FAIL — selftest scheduler did not converge")
            exit(1)

    # the token-identity diff: concurrent batched stream == batch-1 compute path, per request
    var mismatched_reqs = 0
    var mismatched_tokens = 0
    for p in range(8):
        ref got = stt.capture[p]
        ref want = expected[p]
        if len(got) != len(want):
            mismatched_reqs += 1
            mismatched_tokens += 1
            continue
        for k in range(len(got)):
            if got[k] != want[k]:
                mismatched_tokens += 1
                mismatched_reqs += 1
                break
    if mismatched_reqs > 0:
        print("RESULT: FAIL — gate 2: concurrent batched streams diverged from the batch-1",
              "compute path (", mismatched_reqs, "requests,", mismatched_tokens,
              "first-divergence tokens)")
        exit(1)
    print("  gate 2: PASS — 8/8 mixed prompts, concurrent scheduler token-identical to the",
          "batch-1 compute path")
    print("RESULT: PASS — selftest (gate 1 oracle 16/16 + gate 2 token identity)")


def main() raises:
    var args = argv()
    var ckpt_dir = DEFAULT_CHECKPOINT_DIR
    var selftest = False
    var i = 1
    while i < len(args):
        var a = String(args[i])
        if a == "--checkpoint" and i + 1 < len(args):
            ckpt_dir = String(args[i + 1])
            i += 2
        elif a == "--selftest":
            selftest = True
            i += 1
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

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1:
        raise Error("qwen3_serve_batched_cuda: manifest config did not parse")
    if vocab_size < 256:
        raise Error(
            "qwen3_serve_batched_cuda: vocab_size < 256 — the byte-window tokenizer needs"
            + " every byte id valid"
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen3_serve_batched_cuda: checkpoint =", ckpt_dir, "| d_model =", d_model,
          "| n_layers =", n_layers, "| h_q =", h_q, "| h_kv =", h_kv,
          "| d_head =", d_head, "| d_ff =", d_ff, "| vocab =", vocab_size,
          "| max_ctx =", MAX_CTX, "| B_max =", _CUDA_BATCH_DECODE_MAX_SEQS,
          "| chunk_max =", CHUNK_MAX, "| prefill_tile =", CUDA_PREFILL_TILE)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, 1, 1, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_serve_batched_cuda: cannot run a resident session here:",
              residentk_status_name(pre))
        print("  (build with -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN, on a",
              "host with an NVIDIA device and driver >= 580)")
        exit(1)

    @parameter
    if not CUDA_SESSION_BUILD:
        # Unreachable — the preflight above already returned — but stated so the compile-time
        # gate is visible at this file's only construction site.
        print("qwen3_serve_batched_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_serve_batched_cuda: no accelerator on this host")
            exit(1)

        var blob_path = ckpt_dir + "/weights.blob"
        var tensors_obj = json_get_object(manifest, "tensors")

        # ═══ ONE-TIME: open the composed graph session, load every weight resident, seal ═══
        var gs = _CudaResidentQwen3BatchedGraph(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  device:", gs.device_name())
        var rt = rope_table(d_head, MAX_CTX, theta)
        if rt.status != ATTN_OK:
            raise Error("qwen3_serve_batched_cuda: rope_table failed")
        var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
        _check_resident(
            gs.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
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
                gs.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
        _check_resident(gs.seal(), "seal")

        if selftest:
            # ═══ SELFTEST: also hold the single-stream session — the batch-1 driver's exact
            # compute path — as the token-identity reference arm ═══
            var ss = _CudaResidentQwen3(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
            )
            _check_resident(
                ss.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
                "single-stream upload_globals",
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
                    ss.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                    "single-stream upload_layer " + String(layer),
                )
            _check_resident(ss.seal(), "single-stream seal")

            var n_race = json_get_int(config, "n_tokens", -1)
            if n_race < 1 or n_race + 16 > MAX_CTX:
                raise Error(
                    "qwen3_serve_batched_cuda: race prompt length does not fit MAX_CTX"
                )
            var ids_arr = json_get_array(manifest, "input_ids")
            var id_tokens = json_array_tokens(ids_arr)
            var race_prompt = List[Int](capacity=n_race)
            for k in range(len(id_tokens)):
                race_prompt.append(parse_int(id_tokens[k]))
            if len(race_prompt) != n_race:
                raise Error(
                    "qwen3_serve_batched_cuda: input_ids length does not match config.n_tokens"
                )
            _selftest(gs, ss, race_prompt)
            exit(0)

        # ═══ ONE-TIME warmup (untimed): every kernel path AND every graph arm captured
        # before READY. Prefill one token into every slot (all 32 KV slots become valid at
        # pos 0), then run ONE 1-step chunk at every B in 1..B_max — the capture of each B's
        # DeviceGraph happens on first use, and it must not happen inside a timed cell. ═══
        var warm_prompts = List[List[Int]]()
        for _ in range(_CUDA_BATCH_DECODE_MAX_SEQS):
            var w = List[Int](capacity=1)
            w.append(1)
            warm_prompts.append(w^)
        var warm_firsts = _prefill_slots(gs.inner, 0, warm_prompts)
        if len(warm_firsts) != _CUDA_BATCH_DECODE_MAX_SEQS:
            print("qwen3_serve_batched_cuda: warmup prefill failed")
            exit(1)
        for B in range(_CUDA_BATCH_DECODE_MAX_SEQS):
            var toks = List[Int](capacity=B + 1)
            var poss = List[Int](capacity=B + 1)
            for b in range(B + 1):
                toks.append(warm_firsts[b])
                poss.append(1)
            var wst = gs.seed_and_run_batched_graph(toks, poss, 1)
            if wst != RESIDENT_OK:
                print("qwen3_serve_batched_cuda: warmup graph chunk failed at B=", B + 1,
                      "status=", wst)
                exit(1)

        print("qwen3_serve_batched_cuda: READY — one JSON request per stdin line, one",
              "response per stdout line; up to", _CUDA_BATCH_DECODE_MAX_SEQS,
              "requests decode together")
        _serve_loop(gs)
        print("qwen3_serve_batched_cuda: stdin EOF — exiting")
        exit(0)
