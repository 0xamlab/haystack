"""
residentk.kernels_packed3 — the arithmetic-packed-int8 ("packed3") weight-storage arm for the
CUDA decode lane: three unsigned int8 quants per Float32 word, block-32 zero-point
scale+zero, streamed through the ONE load path this toolchain streams at HBM speed (128-bit
`load[width=4]` on a Float32 pointer) and unpacked on-device with `std.memory.bitcast`.
Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, uint8-packed
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` and
`residentk.kernels_prefill_f32_v2` state: shader codegen follows the statically REACHABLE
call graph at COMPILE time, so a public name here would put a GPU launch in the generated
dispatch's call graph. Leading underscores keep these out of the inventory, the contract,
and the dispatch; today only `benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo`
reaches them, and the 16/16 greedy-oracle session integration lands LATER, on the VM.

WHY THIS FILE EXISTS — the measured gap it attacks
----------------------------------------------------
`REALRACE_RESULTS.md` ("THE NVIDIA DECODE LEVER SWEEP" and "THE SECOND-GPU LANE") established
that decode on this stack sits at its f32 bandwidth floor: algenta streams 2.62 GB/token of
Float32 weights, 54-91% of HBM peak per role, and the residual gap to llama.cpp F16 is the
2x weight-bytes of the format, not kernel efficiency. The probe battery in
`benchmarks/llm_smoke/nvidia_race/` measured every sub-f32 SIMD LOAD path scalarized on the
Mojo 1.0.0 / MAX 26.5 CUDA backend (f16 5-7% of peak, int8 1-2%) — so narrower weights must
ride the ONE proven HBM-speed surface, the 128-bit Float32 vector load, and be unpacked from
those bytes in-register. The packed-int8 phase-0 compile battery
(`packed_int8_phase0.sh`, all recipes PASS on sm_80 + sm_89) verified the missing primitive
exists on the pinned toolchain: `std.memory.bitcast[DType.uint8, 16]` reinterprets four
loaded Float32 words as sixteen bytes with no second load. This file is the decode kernel
family that puts the two together.

Layout spec — what "packed3" stores, byte for byte
----------------------------------------------------
Per output row (weights held `[n, k]` row-major, same as every other residentk arm):

1. QUANTS: the row's `k` weights are quantized to unsigned int8, block-32 (see the
   quantization section below), then packed THREE quants per Float32 word, k-ascending:
   the word holds the BIT PATTERN `v = b0 + 256*b1 + 65536*b2` (little-endian bytes
   `[b0, b1, b2, 0]`) with `b0` the LOWEST k-index of the triple. The word is a 32-bit
   CONTAINER, never a Float32 value — it is loaded as Float32 only because that is the one
   SIMD load path this backend streams at HBM speed, and it may legally hold denormal/NaN
   bit patterns because load/store/bitcast preserve bit patterns (no canonicalization on
   this path). Lossless by construction: every byte triple maps to exactly one 32-bit
   pattern and back. Unpack is the byte VIEW of the loaded words: `bitcast[DType.uint8,
   16]` over the `SIMD[DType.float32, 4]` a `load[width=4]` returns yields bytes
   `[b0, b1, b2, 0]` per word on this little-endian target (phase-0 probe p3b2 verified
   the primitive lowers; the host pack round-trip in the probe verifies the convention),
   from which the three quants are pure lane selection — no shifts, no second memory pass.
2. SCALE + ZERO: one Float32 scale and one Float32 zero-point per 32-quant block, two
   companion buffers, both indexed `[row * blocks_per_row + block]`.

TAIL HANDLING (documented per the scheme's +padding requirement): packing needs an integral
word count, so the quant stream is padded to a multiple of 3 — and the row STRIDE is further
rounded to a multiple of 4 WORDS (= 12 elements) so every row's packed stream starts 16-byte
aligned and `load[width=4]` never crosses a row boundary misaligned (a width-4 load on a
misaligned base is the exact fault/slow-path class this format cannot afford). `k = 1024`
therefore stores 344 words = 1032 quant slots (the information content is 1026 quants,
+0.2%; the alignment stride makes it +0.78% — bought for a proven-aligned load path).
`k = 3072` is already a multiple of 12 and pads to itself. Padding quants are set to the
rounded zero-point of their block, and the padding contributes EXACTLY zero to every dot
product because the ACTIVATION side of the tail is nulled too: `_packed3_gemv_kernel`
requires `x` zero-padded to `k_pack`, and `_norm_gemv_kernel_p3` zero-fills its staged tail
itself. Block count covers the padded row: `blocks_per_row = ceil(k_pack / 32)` (k=1024 ->
33 blocks, the last one holding the 8 padding slots; k=3072 -> 96 exactly).

LAYOUT MATH, stated exactly (bytes per stored weight element, k -> infinity):
    packed quants:        4/3  B/w  = 1.3333  (one Float32 word per 3 quants)
    scale + zero (f32):   8/32 B/w  = 0.2500  (two Float32s per 32-block)
    TOTAL AS IMPLEMENTED: 1.5833 B/w  ->  2.38 GB of f32 weights -> ~0.94 GB packed,
                                          ~1.18 GB/token all-in (f32 ledger total 2.62).
The campaign brief's 1.458 B/w (= 4/3 + 4/32) is the same layout with the per-block metadata
at ONE Float32 word combined — reachable later by storing f16 scale + f16 zero (or an f32
scale with the zero-point eliminated algebraically via per-block activation sums); nothing in
these kernels changes under that re-tune, only the host pack and the two metadata buffers'
dtype. The probe driver reports the traffic-model projection under BOTH numbers.

Quantization — block-32 min/max, ZERO-POINT (the chosen of the two schemes)
------------------------------------------------------------------------------
Per 32-element block b of row r over the REAL k elements (padding slots excluded):
    mn = min(w[b*32 .. min(b*32+32, k))),  mx = max(same)
    scale = (mx - mn) / 255     (1.0 on a degenerate constant block)
    zero  = -mn / scale         (stored as Float32, NOT integer-rounded)
    q     = clamp(floor(w / scale + zero + 0.5), 0, 255)
    dequant(q) = (Float32(q) - zero) * scale
so `|w - dequant(q)| <= scale/2 = (mx - mn)/510` per element — the tolerance the probe's
oracle check allows, and the ONLY error these kernels add vs their f32 twins. Zero-point
(asymmetric) rather than symmetric-abs because decode weight rows are not centered at zero
in general and a shifted grid wastes codes; the stored zero costs the second Float32 the
layout math above accounts for.

The kernels
-------------
| kernel | shape |
|---|---|
| `_packed3_gemv_kernel` | `y = W @ x`, ONE output row per block (grid = n), bare GEMV — the probe's correctness + bandwidth kernel |
| `_norm_gemv_kernel_p3` | `y = W @ (rmsnorm(x) * gamma)`, fused norm + 8 rows per block — the structural mirror of `_norm_gemv_kernel_i8` a session integration dispatches |
| `_packed3_gemv_kernel_v2` / `_norm_gemv_kernel_p3_v2` | the same two shapes with ONLY the unpack changed — `bitcast[DType.int32, 4]` word view + shift/AND byte extraction (4 words x 3 ops) instead of the u8x16 byte-view lane selection, and the block-32 crossing classification hoisted out of the chunk loop (loop-invariant: every stride here is a multiple of 32 elements). Same integer quants, same dequant expression, same accumulation order -> bit-identical output; the session's twin v2 kernels in `residentk.session_cuda_p3` follow the same rule |
| `_packed3_gemv_kernel_v3` / `_norm_gemv_kernel_p3_v3` | the v2 bodies PLUS three interleaved accumulators: the chunk's 12 products split by element index mod 3 into three 4-deep chains, combined per lane at loop end as `(acc0 + acc1) + acc2` — the dependent-add chain per chunk is the measured latency wall (the probe battery: v1/v2 unpacks run within noise of each other at ~36% of HBM while the f32 twin's 4-deep chain streams at 75-105%). The reassociation CHANGES accumulation order -> ulp-different output; the session's twin v3 kernels follow the same rule |

Both share one inner step, the phase-0-verified unpack: one `load[width=4]` = 4 packed
words = 16 bytes = 12 quants; three aligned `load[width=4]`s of the activation at the SAME
element offset (12 is a multiple of 4, so the x loads stay float4-aligned); dequant each
quant as `(Float32(q) - zero) * scale` in-register before the multiply that consumes it —
the same widen-immediately / accumulate-in-Float32 discipline `_I8P`'s docstring in
`residentk.kernels` establishes. One wrinkle the 12-wide step introduces: a chunk crosses a
32-quant block boundary when its start offset mod 32 is 24 or 28 (offsets are multiples of
12, so those are the only two crossing residues), handled by loading the neighbouring
block's scale+zero and switching at the crossing element — no per-element division.

Reductions copy `residentk.kernels`' proven patterns VERBATIM: `_packed3_gemv_kernel` uses
`_norm_gemv_kernel_simd_i8`'s two-level form (`std.gpu.primitives.warp.sum` per 32-lane
group — hardware shuffle, no barrier — then a `stack_allocation[...AddressSpace.SHARED]`
combine across the 8 groups' partials); `_norm_gemv_kernel_p3` keeps
`_norm_gemv_kernel_i8`'s shared-memory barrier tree byte-for-byte. Warp width 32 = the
NVIDIA warp, and the shuffle reduction is A100-run-verified (`sdpa_simd_nvidia_probe.mojo`:
0 mismatches in 2000-dispatch stress).

Thread geometry is `residentk.kernels`' verbatim: `_TG = 256` threads, `_LANES = 32` lanes
per cooperating group, `_SUBS = 8` groups per block — imported, not re-decided.

Mojo 1.0.0 kernel-parameter discipline
----------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once
at entry — `accel/launch.mojo`'s pattern, the same one `residentk.kernels` uses.

Build / compile verification (macOS build host, NVPTX ships in the toolchain, no GPU needed)
---------------------------------------------------------------------------------------------
The module compiles THROUGH the probe driver — the campaign's compile-verification form,
which also guarantees the kernels are actually LOWERED (an unreachable kernel would compile
vacuously and prove nothing; `packed_int8_phase0.sh`'s header states the rule):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo \
        -o /tmp/packed3_gemv_probe_sm80
(same with `sm_89` for the L4/4090 lane), or through the campaign driver
(`benchmarks/llm_smoke/nvidia_race/setup_vm.sh` stage 7 `build_one_driver`, which falls back
to the object+link recipe — `--emit object` then clang against the MAX runtime libs,
`-lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals -lAsyncRTMojoBindings
-lMGPRT` — if the plain build does not auto-link the CUDA runtime).
"""

from std.origin import MutAnyOrigin
from std.gpu import block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import floor, sqrt
from std.memory import bitcast, stack_allocation
from residentk.contract import RESIDENT_MAX_D_MODEL
from residentk.kernels import _TG, _LANES, _SUBS

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels`
uses. The packed weight stream is typed Float32 too, on purpose: it is read as Float32 WORDS
(the only SIMD load this backend streams at HBM speed) and reinterpreted AFTER the load."""

comptime _P3_QUANTS_PER_WORD: Int = 3
"""Unsigned int8 quants one Float32 word carries — the word's bit pattern is
`b0 + 256*b1 + 65536*b2` (top byte free), the module docstring's Layout spec."""

comptime _P3_CHUNK: Int = 12
"""ELEMENTS one lane processes per vectorized step: one `load[width=4]` of packed words is 4
words = 16 bytes = 12 quants, and 12 is a multiple of 4 — so the three activation float4
loads at the same element offset stay aligned. The padding stride of `_p3_k_pack` is a
multiple of exactly this number, which is what deletes the scalar tail the f32/i8 twins all
carry."""

comptime _P3_BLOCK: Int = 32
"""Quants sharing one scale+zero pair — the Q8_0-style block size the layout math prices at
8/32 B/w for the pair."""

comptime _P3_STAGE: Int = RESIDENT_MAX_D_MODEL
"""Compile-time size of `_norm_gemv_kernel_p3`'s shared staging array — `residentk.kernels`'
`_STAGE` verbatim (this constant IS `RESIDENT_MAX_D_MODEL`; the ceiling exists because of
this allocation). `k_pack <= k + 11 <= 3072` for every contract-legal `k`, so the staged
vector plus its zero-filled tail always fits."""


def _packed3_gemv_kernel(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP, k_i64: Int64, n_i64: Int64,
):
    """`y = W @ x` with `W` held packed3: ONE output row per block (`grid_dim = n`), 256
    threads streaming the row's packed words in 12-element chunks, unpack + dequant + mac
    in-register, two-level reduction (warp shuffle sum per group + shared combine across the
    8 groups), one scalar write `y[row]`.

    CONTRACT (caller-checked, like every residentk launch): `x` holds `k_pack =
    ceil(k/12)*12` elements with the `k_pack - k` tail zero-filled — that, together with the
    padding quants' zero-point values, is what makes the tail contribute exactly zero (see
    the module docstring's TAIL HANDLING). `wp` holds `n * (k_pack/3)` words, row stride a
    multiple of 4 words by construction; `wscale`/`wzero` hold `n * ceil(k_pack/32)` each.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var row = Int(block_idx.x)
    if row >= n:
        return
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var wbase = row * words_per_row
    var sbase = row * nblocks
    var acc = Float32(0.0)

    # 12-element chunks, lane-strided: `t` is a multiple of 12 at every step, so the packed
    # word offset `t/3` and the three x float4 offsets `t`, `t+4`, `t+8` are ALL aligned.
    var t = tid * _P3_CHUNK
    while t < k_pack:
        # ── the phase-0-verified unpack: 16 bytes as Float32 words, reinterpreted AFTER ──
        var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
        var b = bitcast[DType.uint8, 16](v)
        var xv0 = x.load[width=4](t)
        var xv1 = x.load[width=4](t + 4)
        var xv2 = x.load[width=4](t + 8)

        # ── block-32 scale+zero for this chunk: at most TWO blocks (crossing residues
        #    t mod 32 in {24, 28} only — offsets are multiples of 12) ──
        var blk = t >> 5
        var s0 = wscale[sbase + blk]
        var z0 = wzero[sbase + blk]
        var s1 = s0
        var z1 = z0
        var r = t & 31
        var cross = _P3_CHUNK
        if r == 24:
            cross = 8
        if r == 28:
            cross = 4
        if cross < _P3_CHUNK:
            s1 = wscale[sbase + blk + 1]
            z1 = wzero[sbase + blk + 1]
        # Elements 4-7 take block 1 only when cross == 4; elements 8-11 whenever cross <= 8.
        var s_lo = s0
        var z_lo = z0
        if cross == 4:
            s_lo = s1
            z_lo = z1
        var s_hi = s0
        var z_hi = z0
        if cross <= 8:
            s_hi = s1
            z_hi = z1

        # ── 12 dequant+mac in ascending element order; word w holds elements 3w..3w+2 at
        #    bytes 4w..4w+2 (byte 4w+3 is the always-zero top byte of the packed word) ──
        acc += xv0[0] * ((Float32(Int32(b[0])) - z0) * s0)
        acc += xv0[1] * ((Float32(Int32(b[1])) - z0) * s0)
        acc += xv0[2] * ((Float32(Int32(b[2])) - z0) * s0)
        acc += xv0[3] * ((Float32(Int32(b[4])) - z0) * s0)
        acc += xv1[0] * ((Float32(Int32(b[5])) - z_lo) * s_lo)
        acc += xv1[1] * ((Float32(Int32(b[6])) - z_lo) * s_lo)
        acc += xv1[2] * ((Float32(Int32(b[8])) - z_lo) * s_lo)
        acc += xv1[3] * ((Float32(Int32(b[9])) - z_lo) * s_lo)
        acc += xv2[0] * ((Float32(Int32(b[10])) - z_hi) * s_hi)
        acc += xv2[1] * ((Float32(Int32(b[12])) - z_hi) * s_hi)
        acc += xv2[2] * ((Float32(Int32(b[13])) - z_hi) * s_hi)
        acc += xv2[3] * ((Float32(Int32(b[14])) - z_hi) * s_hi)
        t += _TG * _P3_CHUNK

    # ── two-level reduction, `_norm_gemv_kernel_simd_i8`'s pattern: warp shuffle sum per
    #    group (hardware lockstep, no barrier), one shared combine across the 8 groups ──
    var total = _warp_sum(acc)
    if lane == 0:
        grp[sub] = total
    barrier()
    var out = Float32(0.0)
    for g in range(_SUBS):
        out += grp[g]
    if tid == 0:
        y[row] = out


def _packed3_gemv_kernel_v2(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP, k_i64: Int64, n_i64: Int64,
):
    """`_packed3_gemv_kernel`'s v2 twin — same shape, same contract, same reduction; ONLY
    the unpack changes: the loaded Float32 words are reinterpreted as `SIMD[DType.int32, 4]`
    and each quant comes out of its word with an integer shift/AND (`w & 255`,
    `(w >> 8) & 255`, `(w >> 16) & 255`) instead of a byte-view lane selection. The two
    paths extract the SAME integer quant from the SAME bit pattern — the byte `4j + m` of
    word `j` IS `(word >> 8m) & 255` on this little-endian target — so with the dequant
    expression and the ascending accumulation order kept verbatim, v2 computes bit-identical
    output. The chunk's block-32 crossing classification is hoisted out of the loop: the
    lane's chunk offsets are `tid*12 + i*(256*12)` and `256*12 % 32 == 0`, so `t & 31` is
    loop-invariant. The probe driver benches this against v1 at the real role shapes.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var row = Int(block_idx.x)
    if row >= n:
        return
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var wbase = row * words_per_row
    var sbase = row * nblocks
    var acc = Float32(0.0)

    # ── hoisted crossing classification (loop-invariant — see the docstring) ──
    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        # ── the v2 unpack: 16 bytes as Float32 words, reinterpreted as FOUR Int32 words;
        #    each quant is a shift/AND byte extraction, no second memory pass ──
        var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
        var w = bitcast[DType.int32, 4](v)
        var xv0 = x.load[width=4](t)
        var xv1 = x.load[width=4](t + 4)
        var xv2 = x.load[width=4](t + 8)

        var blk = t >> 5
        var s0 = wscale[sbase + blk]
        var z0 = wzero[sbase + blk]
        var s_lo = s0
        var z_lo = z0
        var s_hi = s0
        var z_hi = z0
        if cross_hi:
            s_hi = wscale[sbase + blk + 1]
            z_hi = wzero[sbase + blk + 1]
            if cross_lo:
                s_lo = s_hi
                z_lo = z_hi

        # ── 12 dequant+mac in ascending element order, `_packed3_gemv_kernel`'s lines
        #    verbatim with the byte-view extraction swapped for word shift/AND ──
        acc += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
        acc += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
        acc += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
        acc += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
        acc += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
        acc += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
        acc += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
        acc += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
        acc += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
        acc += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
        acc += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
        acc += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
        t += _TG * _P3_CHUNK

    # ── two-level reduction, `_packed3_gemv_kernel`'s verbatim ──
    var total = _warp_sum(acc)
    if lane == 0:
        grp[sub] = total
    barrier()
    var out = Float32(0.0)
    for g in range(_SUBS):
        out += grp[g]
    if tid == 0:
        y[row] = out


def _packed3_gemv_kernel_v3(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP, k_i64: Int64, n_i64: Int64,
):
    """`_packed3_gemv_kernel`'s v3 twin — v2's unpack PLUS three interleaved accumulators:
    the chunk's 12 products split by element index mod 3 into `acc0`/`acc1`/`acc2` (4
    sequential adds each instead of one 12-deep chain), combined per lane at loop end as
    `(acc0 + acc1) + acc2`. The dependent-add chain per chunk is the latency wall the probe
    battery measured (v1/v2 unpacks run within noise of each other at ~36% of HBM while the
    f32 twin's 4-deep chain streams at 75-105%); splitting it is the only lever left inside
    the chunk loop. The reassociation CHANGES accumulation order — v3 output is not
    bit-identical to v1/v2 (ulp-level; G0 stays hard, the gate driver's G1 switches to the
    vs-f32 flip-reporting form for this variant). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V3_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var row = Int(block_idx.x)
    if row >= n:
        return
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var wbase = row * words_per_row
    var sbase = row * nblocks
    var acc0 = Float32(0.0)
    var acc1 = Float32(0.0)
    var acc2 = Float32(0.0)

    # ── hoisted crossing classification (loop-invariant — see the v2 docstring) ──
    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
        var w = bitcast[DType.int32, 4](v)
        var xv0 = x.load[width=4](t)
        var xv1 = x.load[width=4](t + 4)
        var xv2 = x.load[width=4](t + 8)

        var blk = t >> 5
        var s0 = wscale[sbase + blk]
        var z0 = wzero[sbase + blk]
        var s_lo = s0
        var z_lo = z0
        var s_hi = s0
        var z_hi = z0
        if cross_hi:
            s_hi = wscale[sbase + blk + 1]
            z_hi = wzero[sbase + blk + 1]
            if cross_lo:
                s_lo = s_hi
                z_lo = z_hi

        # ── the same 12 dequant+mac terms, regrouped into three 4-deep chains by
        #    element index mod 3 (word m holds elements 3m..3m+2) ──
        acc0 += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
        acc1 += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
        acc2 += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
        acc0 += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
        acc1 += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
        acc2 += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
        acc0 += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
        acc1 += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
        acc2 += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
        acc0 += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
        acc1 += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
        acc2 += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
        t += _TG * _P3_CHUNK

    var acc = (acc0 + acc1) + acc2

    # ── two-level reduction, `_packed3_gemv_kernel`'s verbatim ──
    var total = _warp_sum(acc)
    if lane == 0:
        grp[sub] = total
    barrier()
    var out = Float32(0.0)
    for g in range(_SUBS):
        out += grp[g]
    if tid == 0:
        y[row] = out


def _norm_gemv_kernel_p3(
    y: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, eps: Float32,
):
    """The packed3 multi-row twin of `_norm_gemv_kernel` — fused rmsnorm + GEMV, 8 output
    rows per block (`grid_dim = ceil(n / 8)`), the structural mirror of
    `_norm_gemv_kernel_i8` with ONLY the weight load+dequant changed: `w` arrives as the
    packed3 triple (`wp` + per-block `wscale`/`wzero`) instead of one Int8 per byte + one
    per-row scale. The normalization, the shared staging, the accumulator and the barrier-
    tree reduction are copied from `_norm_gemv_kernel_i8` line for line.

    The staging loop stages `k_pack` elements, zero-filling the `k_pack - k` tail, so the
    12-wide chunk loop's aligned reads never touch an uninitialised slot — the activation-
    side half of the module docstring's TAIL HANDLING contract.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    # ── 3. one SIMD group per output row, packed3 chunk loop ──
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
            var b = bitcast[DType.uint8, 16](v)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s1 = s0
            var z1 = z0
            var r = t & 31
            var cross = _P3_CHUNK
            if r == 24:
                cross = 8
            if r == 28:
                cross = 4
            if cross < _P3_CHUNK:
                s1 = wscale[sbase + blk + 1]
                z1 = wzero[sbase + blk + 1]
            var s_lo = s0
            var z_lo = z0
            if cross == 4:
                s_lo = s1
                z_lo = z1
            var s_hi = s0
            var z_hi = z0
            if cross <= 8:
                s_hi = s1
                z_hi = z1

            # MUST stay in sync with `_packed3_gemv_kernel`'s 12 dequant+mac lines above.
            acc += xv0[0] * ((Float32(Int32(b[0])) - z0) * s0)
            acc += xv0[1] * ((Float32(Int32(b[1])) - z0) * s0)
            acc += xv0[2] * ((Float32(Int32(b[2])) - z0) * s0)
            acc += xv0[3] * ((Float32(Int32(b[4])) - z0) * s0)
            acc += xv1[0] * ((Float32(Int32(b[5])) - z_lo) * s_lo)
            acc += xv1[1] * ((Float32(Int32(b[6])) - z_lo) * s_lo)
            acc += xv1[2] * ((Float32(Int32(b[8])) - z_lo) * s_lo)
            acc += xv1[3] * ((Float32(Int32(b[9])) - z_lo) * s_lo)
            acc += xv2[0] * ((Float32(Int32(b[10])) - z_hi) * s_hi)
            acc += xv2[1] * ((Float32(Int32(b[12])) - z_hi) * s_hi)
            acc += xv2[2] * ((Float32(Int32(b[13])) - z_hi) * s_hi)
            acc += xv2[3] * ((Float32(Int32(b[14])) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


def _norm_gemv_kernel_p3_v2(
    y: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, eps: Float32,
):
    """`_norm_gemv_kernel_p3`'s v2 twin — the SAME fused rmsnorm + 8-rows-per-block GEMV with
    ONLY the chunk loop's unpack changed: `bitcast[DType.int32, 4]` word view + shift/AND
    byte extraction instead of the byte-view lane selection, plus the crossing classification
    hoisted out of the loop (the lane's chunk offsets are `lane*12 + i*(32*12)` and
    `384 % 32 == 0`, so `t & 31` is loop-invariant). Both paths extract the same integer
    quant from the same bit pattern, and the dequant expression and ascending accumulation
    order are kept verbatim, so v2 computes bit-identical output — the graph arm's gate
    driver diffs it token-for-token against this kernel's v1. Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V2_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    # ── 3. one SIMD group per output row, v2 chunk loop ──
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        # ── hoisted crossing classification (loop-invariant — see the docstring):
        #    r == 24: elements 8-11 live in the next block; r == 28: elements 4-11 too ──
        var r0 = (lane * _P3_CHUNK) & 31
        var cross_hi = r0 == 24 or r0 == 28
        var cross_lo = r0 == 28
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
            var w = bitcast[DType.int32, 4](v)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s_lo = s0
            var z_lo = z0
            var s_hi = s0
            var z_hi = z0
            if cross_hi:
                s_hi = wscale[sbase + blk + 1]
                z_hi = wzero[sbase + blk + 1]
                if cross_lo:
                    s_lo = s_hi
                    z_lo = z_hi

            # `_norm_gemv_kernel_p3`'s 12 dequant+mac lines verbatim with the byte-view
            # extraction swapped for word shift/AND (word w[m] holds elements 3m..3m+2).
            acc += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
            acc += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
            acc += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
            acc += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
            acc += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
            acc += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
            acc += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
            acc += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
            acc += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
            acc += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
            acc += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
            acc += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


def _norm_gemv_kernel_p3_v3(
    y: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, eps: Float32,
):
    """`_norm_gemv_kernel_p3`'s v3 twin — v2's unpack PLUS three interleaved accumulators
    (the chunk's 12 products split by element index mod 3 into 4-deep chains, combined at
    loop end as `(acc0 + acc1) + acc2`); everything else — fused rmsnorm, staging, 8 rows
    per block, the barrier-tree reduction — is verbatim. The reassociation CHANGES
    accumulation order, so this variant is ulp-different from v1/v2 (the rule
    `_packed3_gemv_kernel_v3`'s docstring states). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V3_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    # ── 3. one SIMD group per output row, v3 chunk loop ──
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc0 = Float32(0.0)
    var acc1 = Float32(0.0)
    var acc2 = Float32(0.0)
    if j < n:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var r0 = (lane * _P3_CHUNK) & 31
        var cross_hi = r0 == 24 or r0 == 28
        var cross_lo = r0 == 28
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
            var w = bitcast[DType.int32, 4](v)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s_lo = s0
            var z_lo = z0
            var s_hi = s0
            var z_hi = z0
            if cross_hi:
                s_hi = wscale[sbase + blk + 1]
                z_hi = wzero[sbase + blk + 1]
                if cross_lo:
                    s_lo = s_hi
                    z_lo = z_hi

            # The same 12 dequant+mac terms as v2, regrouped into three 4-deep chains.
            acc0 += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
            acc1 += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
            acc2 += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
            acc0 += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
            acc1 += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
            acc2 += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
            acc0 += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
            acc1 += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
            acc2 += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
            acc0 += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
            acc1 += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
            acc2 += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = (acc0 + acc1) + acc2
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


# ── host-side pack / unpack: the format's reference implementation ────────────

def _p3_k_pack(k: Int) -> Int:
    """Stored quant slots per row: `k` rounded UP to a multiple of `_P3_CHUNK = 12` — the
    multiple-of-3 packing requirement rounded further to a multiple of 4 WORDS so every
    row's packed stream is 16-byte aligned for `load[width=4]` (module docstring, TAIL
    HANDLING)."""
    return ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK


def _p3_words_per_row(k: Int) -> Int:
    """Packed Float32 words one row occupies: `_p3_k_pack(k) / 3` — a multiple of 4 by
    `_p3_k_pack`'s construction."""
    return _p3_k_pack(k) // _P3_QUANTS_PER_WORD


def _p3_blocks_per_row(k: Int) -> Int:
    """Scale+zero blocks one row owns: `ceil(_p3_k_pack(k) / 32)` — blocks cover the PADDED
    row, so the tail slots always have a block to dequant from."""
    return (_p3_k_pack(k) + _P3_BLOCK - 1) // _P3_BLOCK


def _p3_pack_word(b0: UInt8, b1: UInt8, b2: UInt8) -> Float32:
    """Pack three quants into one Float32 word: the word's BIT PATTERN is
    `v = b0 + 256*b1 + 65536*b2` (bytes `[b0, b1, b2, 0]`), constructed with integer ops
    and bitcast — exact by construction, a 32-bit pattern in, the same pattern out. The
    resulting Float32 is a container, never used as a value (module docstring, Layout
    spec)."""
    var u = UInt32(b0) | (UInt32(b1) << 8) | (UInt32(b2) << 16)
    return bitcast[DType.float32, 1](SIMD[DType.uint32, 1](u))[0]


def _p3_unpack_word(v: Float32) -> Tuple[UInt8, UInt8, UInt8]:
    """The inverse of `_p3_pack_word`: bitcast to the UInt32 bit pattern, mask the three
    bytes. Exact integer arithmetic — the probe's byte-round-trip check runs this against
    synthetic patterns."""
    var u = bitcast[DType.uint32, 1](SIMD[DType.float32, 1](v))[0]
    return (UInt8(u & 255), UInt8((u >> 8) & 255), UInt8((u >> 16) & 255))


struct _P3Packed:
    """The host-side pack result — the packed3 reference layout, one matrix's worth:

    - `packed`: `n * words_per_row` Float32 words, three quants each (module docstring,
      "Layout spec"), row `r` at `packed[r * words_per_row ..]`;
    - `scales` / `zeros`: `n * nblocks` Float32s each, block-32 min/max zero-point
      quantization exactly as the module docstring states — `scale = (mx - mn)/255` (1.0 on
      a constant block), `zero = -mn/scale` stored as Float32,
      `q = clamp(floor(w/scale + zero + 0.5), 0, 255)`;
    - `k_pack` / `words_per_row` / `nblocks`: the layout arithmetic, carried with the data
      so a caller never re-derives them.

    Padding slots (`k .. k_pack`) take the rounded zero-point of their block, which
    dequantizes to `<= scale/2` in magnitude and is multiplied by a zero activation on the
    device side — an exactly-zero contribution. A struct (rather than a tuple of Lists)
    because Mojo 1.0.0 Lists are move-only and a struct field is the this-repo idiom for
    returning several of them at once.
    """

    var packed: List[Float32]
    var scales: List[Float32]
    var zeros: List[Float32]
    var k_pack: Int
    var words_per_row: Int
    var nblocks: Int

    def __init__(out self, weights: List[Float32], k: Int, n: Int):
        """Pack `weights` held `[n, k]` row-major into the packed3 layout."""
        self.k_pack = _p3_k_pack(k)
        self.words_per_row = self.k_pack // _P3_QUANTS_PER_WORD
        self.nblocks = (self.k_pack + _P3_BLOCK - 1) // _P3_BLOCK
        self.packed = List[Float32](capacity=n * self.words_per_row)
        self.scales = List[Float32](capacity=n * self.nblocks)
        self.zeros = List[Float32](capacity=n * self.nblocks)
        for r in range(n):
            var base = r * k
            var blk_base = r * self.nblocks
            # ── per-block scale+zero over the REAL elements; a block that holds only
            #    padding slots gets min/max = 0/0 (scale 1.0, zero 0.0) ──
            for blk in range(self.nblocks):
                var lo = blk * _P3_BLOCK
                var hi = lo + _P3_BLOCK
                if hi > k:
                    hi = k
                var mn = Float32(0.0)
                var mx = Float32(0.0)
                if lo < k:
                    mn = weights[base + lo]
                    mx = weights[base + lo]
                    for e in range(lo + 1, hi):
                        var w = weights[base + e]
                        if w < mn:
                            mn = w
                        if w > mx:
                            mx = w
                var rng = mx - mn
                var scale = Float32(1.0)
                if rng > Float32(0.0):
                    scale = rng / Float32(255.0)
                var zero = -mn * (Float32(1.0) / scale)
                self.scales.append(scale)
                self.zeros.append(zero)
            # ── pack the row's quant stream word by word (global word index -> block) ──
            for wd in range(self.words_per_row):
                var e0 = wd * _P3_QUANTS_PER_WORD
                var q0 = _p3_quant_elem(weights, base, k, blk_base, self.scales, self.zeros, e0)
                var q1 = _p3_quant_elem(weights, base, k, blk_base, self.scales, self.zeros, e0 + 1)
                var q2 = _p3_quant_elem(weights, base, k, blk_base, self.scales, self.zeros, e0 + 2)
                self.packed.append(_p3_pack_word(q0, q1, q2))


def _p3_quant_elem(
    weights: List[Float32], base: Int, k: Int, blk_base: Int,
    scales: List[Float32], zeros: List[Float32], elem: Int,
) -> UInt8:
    """One quant of the pack: `clamp(floor(w/scale + zero + 0.5), 0, 255)` for a real
    element, the rounded zero-point for a padding slot (module docstring, TAIL HANDLING)."""
    var blk = blk_base + (elem >> 5)
    var ze = zeros[blk]
    var f: Float32
    if elem < k:
        var sc = scales[blk]
        f = floor(weights[base + elem] / sc + ze + Float32(0.5))
    else:
        f = floor(ze + Float32(0.5))
    var qi = Int(f)
    if qi < 0:
        qi = 0
    if qi > 255:
        qi = 255
    return UInt8(qi)


def _pack_f32_to_packed3(weights: List[Float32], k: Int, n: Int) -> _P3Packed:
    """Host-side pack, the deliverable's entry point: `weights` held `[n, k]` row-major ->
    a `_P3Packed` (packed words + per-block scales + per-block zeros + the layout
    arithmetic). See `_P3Packed.__init__` for the exact quantization convention."""
    return _P3Packed(weights, k, n)


def _p3_dequant_host(
    packed: List[Float32], scales: List[Float32], zeros: List[Float32], k: Int, n: Int,
) -> List[Float32]:
    """Host-side unpack+dequant, the reference for what the device kernels compute: returns
    `[n, k_pack]` Float32s with `out[r, e] = (Float32(q) - zero_b) * scale_b` — the SAME
    expression, in the SAME Float32 dtype, the kernels evaluate. The probe compares this
    against the original weights to price the quantization error, and against the kernel's
    output to price everything ELSE (unpack bug, lane misalignment, reduction bug)."""
    var k_pack = _p3_k_pack(k)
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK
    var out = List[Float32](capacity=n * k_pack)
    for r in range(n):
        var pbase = r * words_per_row
        var sbase = r * nblocks
        for wd in range(words_per_row):
            var (b0, b1, b2) = _p3_unpack_word(packed[pbase + wd])
            var e0 = wd * _P3_QUANTS_PER_WORD
            var sc = scales[sbase + (e0 >> 5)]
            var ze = zeros[sbase + (e0 >> 5)]
            out.append((Float32(Int32(b0)) - ze) * sc)
            var sc1 = scales[sbase + ((e0 + 1) >> 5)]
            var ze1 = zeros[sbase + ((e0 + 1) >> 5)]
            out.append((Float32(Int32(b1)) - ze1) * sc1)
            var sc2 = scales[sbase + ((e0 + 2) >> 5)]
            var ze2 = zeros[sbase + ((e0 + 2) >> 5)]
            out.append((Float32(Int32(b2)) - ze2) * sc2)
    return out^
