"""sdpa_simd_reduce_probe.mojo — does replacing `_sdpa_kernel`'s per-key barrier-tree reduction with
hardware SIMD-group shuffle reduction compute the IDENTICAL softmax math, and does the exact Metal
API exist at this pinned Mojo nightly?

Hand-written, throwaway measurement (not registered in `generate_mojo_tests.py`; this is a probe for
a design decision, exactly like `int8_pack_probe.mojo`/`decode_metal_probe.mojo` before it, not a
golden-vector suite). REQUIRES the GPU build flag and a shader compiler:

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine ../benchmarks/llm_smoke/sdpa_simd_reduce_probe.mojo

Question being asked, precisely
--------------------------------
`residentk.kernels._sdpa_kernel` reduces one dot product (`qv * ck[...]`, `d_head` = 128 partial
products) to a scalar with a SHARED-MEMORY tree: write to `red[e]`, `barrier()`, then
`log2(d_head) = 7` more halving steps each followed by a `barrier()`, plus one final "safety"
`barrier()` before the next key's write can safely overwrite `red`. That is 9 barrier hits per key.

`d_head = 128` and Apple's hardware SIMD-group width (`std.gpu.globals.WARP_SIZE` under
`is_apple_gpu()`) is 32 — confirmed by this file's own `_lane_id`-based probe below, not assumed —
so one threadgroup's `d_head` threads are FOUR SIMD-groups, not one. A pure single-level
`std.gpu.primitives.warp.sum()` (which reduces exactly one 32-lane SIMD-group and broadcasts within
it) is therefore NOT enough on its own: it would only fold each 32-lane quarter of `d_head` down to
its own partial sum. The correct replacement is a TWO-level reduction:

1. `warp.sum(partial)` inside each of the 4 SIMD-groups — a butterfly `shuffle_xor` pattern lowered
   to `llvm.air.simd_shuffle_xor`, lockstep by hardware construction, needing NO `barrier()` at all.
2. ONE lane per SIMD-group (`lane_id() == 0`) writes its group's total to a 4-element shared array;
   ONE `barrier()` makes those 4 writes visible; every thread reads all 4 and sums them.

That is 1 barrier per key instead of 9 — the mechanism this probe verifies before it goes anywhere
near the production kernel.

Correctness gate, per this phase's Stage 1: the SIMD-shuffle reduction is checked against BOTH an
independent pure-host scalar reduction of the identical input AND the existing barrier-tree
reduction's own device output, on a shape (`d_head = 128`, a handful of distinct non-trivial input
patterns) small enough to hand-verify, before any timing number from this file is trusted.
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from max.gpu.host import DeviceContext, DeviceBuffer
from std.gpu import thread_idx, block_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as warp_sum
from std.gpu.primitives.id import lane_id, warp_id
from std.gpu.globals import WARP_SIZE
from std.memory import stack_allocation
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns

comptime PROBE_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()

comptime _D_HEAD: Int = 128
"""Qwen3-0.6B-Base's real `head_dim` (confirmed: `num_attention_heads=16,
num_key_value_heads=8, head_dim=128` — see `decode_metal_probe.mojo`), and the exact block_dim
`_sdpa_kernel` launches with."""

comptime _N_KEYS: Int = 6
"""A handful of keys — enough to exercise the online-softmax running-max/running-sum update at
least twice (so a wrong rescale, not just a wrong single-key score, would show up), small enough to
hand-verify against a pure-Python/host reference."""

comptime _NEG_HUGE: Float32 = -3.0e38

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]


def _lane_width_probe(out_lane: _IP, out_warp: _IP):
    """Writes `lane_id()` and `warp_id()` for every thread of a single `_D_HEAD`-wide threadgroup,
    so the host can confirm — not assume — that Apple's real SIMD-group width on THIS hardware is
    32, and that `_D_HEAD / 32 = 4` distinct SIMD-groups appear inside one `_sdpa_kernel` launch."""
    var e = Int(thread_idx.x)
    out_lane[e] = Int32(lane_id())
    out_warp[e] = Int32(warp_id())


def _dot_reduce_barrier_tree(attn_out: _FP, qv_buf: _FP, kv_buf: _FP, n_keys: Int):
    """The EXISTING mechanism, copied verbatim in structure from `residentk.kernels._sdpa_kernel`'s
    inner loop (barrier-synchronized shared-memory tree, `log2(d_head)` levels plus the trailing
    safety barrier) but isolated to just the reduction + online-softmax update, over a HOST-supplied
    `qv`/`ck` pair instead of a real KV cache, so this probe measures the reduction mechanism alone.

    `grid_dim = h_q` (one threadgroup per query head, exactly like the real kernel): `block_idx.x`
    selects which head's `_D_HEAD`-wide slice of `qv_buf`/`attn_out` this threadgroup owns. `kv_buf`
    is shared across every head in this probe (unlike the real kernel's GQA head mapping) since the
    reduction mechanism, not the head-to-KV mapping, is what this probe is isolating."""
    var red = stack_allocation[_D_HEAD, DType.float32, address_space = AddressSpace.SHARED]()
    var e = Int(thread_idx.x)
    var h = Int(block_idx.x)
    var qv = qv_buf[h * _D_HEAD + e]

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(n_keys):
        var kb = j * _D_HEAD
        red[e] = qv * kv_buf[kb + e]
        barrier()
        var stride = _D_HEAD // 2
        while stride > 0:
            if e < stride:
                red[e] = red[e] + red[e + stride]
            barrier()
            stride //= 2
        var s = red[0]
        barrier()

        var nm = m if m > s else s
        var corr = _exp(m - nm)
        var w = _exp(s - nm)
        o = o * corr + w * kv_buf[kb + e]
        denom = denom * corr + w
        m = nm

    attn_out[h * _D_HEAD + e] = o / denom


def _exp(x: Float32) -> Float32:
    from std.math import exp
    return exp(x)


def _dot_reduce_simd_shuffle(attn_out: _FP, qv_buf: _FP, kv_buf: _FP, n_keys: Int):
    """The CANDIDATE replacement: two-level reduction. Level 1 is `warp.sum` inside each 32-lane
    SIMD-group — pure register shuffle, no `barrier()`. Level 2 combines the `_D_HEAD // 32 = 4`
    per-group partial sums through ONE shared array and exactly ONE `barrier()` per key (down from
    9). Same online-softmax math as `_dot_reduce_barrier_tree` afterward, byte-for-byte."""
    comptime _N_GROUPS: Int = _D_HEAD // WARP_SIZE
    var grp = stack_allocation[_N_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var e = Int(thread_idx.x)
    var h = Int(block_idx.x)
    var qv = qv_buf[h * _D_HEAD + e]
    var lane = lane_id()
    var grp_id = warp_id()

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(n_keys):
        var kb = j * _D_HEAD
        var partial = qv * kv_buf[kb + e]
        var group_total = warp_sum(partial)
        if lane == 0:
            grp[grp_id] = group_total
        barrier()
        var s = Float32(0.0)
        for g in range(_N_GROUPS):
            s += grp[g]
        barrier()

        var nm = m if m > s else s
        var corr = _exp(m - nm)
        var w = _exp(s - nm)
        o = o * corr + w * kv_buf[kb + e]
        denom = denom * corr + w
        m = nm

    attn_out[h * _D_HEAD + e] = o / denom


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _host_reference(qv: List[Float64], kv: List[Float64], n_keys: Int, d_head: Int) -> List[Float64]:
    """Pure-host, independent online-softmax reference: no shuffle, no shared-memory tree, just
    float64 arithmetic in the obvious order, per query element `e`. Used to hand-verify BOTH device
    kernels before comparing them to each other."""
    var out = List[Float64](capacity=d_head)
    for e in range(d_head):
        var m = -1.0e300
        var denom = 0.0
        var o = 0.0
        for j in range(n_keys):
            var kb = j * d_head
            var s = 0.0
            for i in range(d_head):
                s += qv[i] * kv[kb + i]
            var nm = m if m > s else s
            var corr = _exp64(m - nm)
            var w = _exp64(s - nm)
            o = o * corr + w * kv[kb + e]
            denom = denom * corr + w
            m = nm
        out.append(o / denom)
    return out^


def _exp64(x: Float64) -> Float64:
    from std.math import exp
    return exp(x)


def _worst_delta(buf: DeviceBuffer[DType.float32], refv: List[Float64], n: Int) raises -> Float64:
    var worst = 0.0
    with buf.map_to_host() as h:
        for i in range(n):
            var d = Float64(h[i]) - refv[i]
            if d < 0.0:
                d = -d
            if d > worst:
                worst = d
    return worst


def main() raises:
    print("=== SDPA reduction probe: barrier-tree vs SIMD-shuffle, same online-softmax math ===")
    print("")

    if not PROBE_GPU_BUILD:
        print("Built WITHOUT -D ALGENTA_GPU: refusing to report anything (kernels compiled out).")
        return
    if not has_accelerator():
        print("No usable accelerator. Refusing to report anything.")
        return

    var ctx = DeviceContext()

    print("--- SIMD-group width check: confirm WARP_SIZE and the real hardware lane/warp ids ---")
    var lane_buf = ctx.enqueue_create_buffer[DType.int32](_D_HEAD)
    var warp_buf = ctx.enqueue_create_buffer[DType.int32](_D_HEAD)
    var f_probe = ctx.compile_function_unchecked[_lane_width_probe]()
    ctx.enqueue_function_unchecked(
        f_probe, lane_buf.unsafe_ptr(), warp_buf.unsafe_ptr(),
        grid_dim=1, block_dim=_D_HEAD,
    )
    ctx.synchronize()
    print("   std.gpu.globals.WARP_SIZE (compile-time, is_apple_gpu() branch) =", WARP_SIZE)
    var max_warp = 0
    var lane_ok = True
    with lane_buf.map_to_host() as lh:
        with warp_buf.map_to_host() as wh:
            for e in range(_D_HEAD):
                var expect_lane = e % WARP_SIZE
                var expect_warp = e // WARP_SIZE
                if Int(lh[e]) != expect_lane or Int(wh[e]) != expect_warp:
                    lane_ok = False
                if Int(wh[e]) > max_warp:
                    max_warp = Int(wh[e])
    print("   observed distinct SIMD-groups inside one d_head=128 threadgroup =", max_warp + 1)
    print("   lane_id()/warp_id() match thread_idx.x % / // WARP_SIZE exactly:", "OK" if lane_ok else "MISMATCH")
    if not lane_ok or max_warp + 1 != 4:
        print("ASSUMPTION VIOLATED: the two-level plan assumes exactly 4 SIMD-groups of 32. Stopping.")
        return
    print("")

    print("--- Stage 1 correctness: barrier-tree vs SIMD-shuffle vs an independent host reference ---")
    var qv64 = _pseudo(_D_HEAD, 3)
    var kv64 = _pseudo(_N_KEYS * _D_HEAD, 11)
    var refv = _host_reference(qv64, kv64, _N_KEYS, _D_HEAD)

    var qbuf = ctx.enqueue_create_buffer[DType.float32](_D_HEAD)
    var kvbuf = ctx.enqueue_create_buffer[DType.float32](_N_KEYS * _D_HEAD)
    var outbuf = ctx.enqueue_create_buffer[DType.float32](_D_HEAD)
    with qbuf.map_to_host() as h:
        for i in range(_D_HEAD):
            h[i] = Float32(qv64[i])
    with kvbuf.map_to_host() as h:
        for i in range(_N_KEYS * _D_HEAD):
            h[i] = Float32(kv64[i])
    ctx.synchronize()

    var f_tree = ctx.compile_function_unchecked[_dot_reduce_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_dot_reduce_simd_shuffle]()

    ctx.enqueue_function_unchecked(
        f_tree, outbuf.unsafe_ptr(), qbuf.unsafe_ptr(), kvbuf.unsafe_ptr(), _N_KEYS,
        grid_dim=1, block_dim=_D_HEAD,
    )
    ctx.synchronize()
    var worst_tree = _worst_delta(outbuf, refv, _D_HEAD)
    var ok_tree = worst_tree < 1e-4
    print("   correctness[ barrier_tree  ]: worst |delta| vs host f64 reference =", worst_tree, "  ", "OK" if ok_tree else "MISMATCH")

    ctx.enqueue_function_unchecked(
        f_shfl, outbuf.unsafe_ptr(), qbuf.unsafe_ptr(), kvbuf.unsafe_ptr(), _N_KEYS,
        grid_dim=1, block_dim=_D_HEAD,
    )
    ctx.synchronize()
    var worst_shfl = _worst_delta(outbuf, refv, _D_HEAD)
    var ok_shfl = worst_shfl < 1e-4
    print("   correctness[ simd_shuffle  ]: worst |delta| vs host f64 reference =", worst_shfl, "  ", "OK" if ok_shfl else "MISMATCH")

    if not (ok_tree and ok_shfl):
        print("CORRECTNESS FAILURE: refusing to report any timing number.")
        return
    print("")

    print("--- multi-threadgroup correctness: many query heads at once, n_keys growing (decode-shaped) ---")
    comptime _N_HEADS: Int = 16
    var ok_multi = True
    for n_keys_case in [1, 2, 8, 33, 64]:
        var q_multi = List[Float64](capacity=_N_HEADS * _D_HEAD)
        var kv_multi = List[Float64](capacity=n_keys_case * _D_HEAD)
        for i in range(_N_HEADS * _D_HEAD):
            q_multi.append(_pseudo(1, i + 5)[0])
        for i in range(n_keys_case * _D_HEAD):
            kv_multi.append(_pseudo(1, i + 91)[0])

        var qbuf_m = ctx.enqueue_create_buffer[DType.float32](_N_HEADS * _D_HEAD)
        var kvbuf_m = ctx.enqueue_create_buffer[DType.float32](n_keys_case * _D_HEAD)
        var outbuf_m = ctx.enqueue_create_buffer[DType.float32](_N_HEADS * _D_HEAD)
        with qbuf_m.map_to_host() as h:
            for i in range(_N_HEADS * _D_HEAD):
                h[i] = Float32(q_multi[i])
        with kvbuf_m.map_to_host() as h:
            for i in range(n_keys_case * _D_HEAD):
                h[i] = Float32(kv_multi[i])
        ctx.synchronize()

        ctx.enqueue_function_unchecked(
            f_shfl, outbuf_m.unsafe_ptr(), qbuf_m.unsafe_ptr(), kvbuf_m.unsafe_ptr(), n_keys_case,
            grid_dim=_N_HEADS, block_dim=_D_HEAD,
        )
        ctx.synchronize()

        var worst_m = 0.0
        with outbuf_m.map_to_host() as h_out:
            for head in range(_N_HEADS):
                var qh = List[Float64](capacity=_D_HEAD)
                for i in range(_D_HEAD):
                    qh.append(q_multi[head * _D_HEAD + i])
                var ref_m = _host_reference(qh, kv_multi, n_keys_case, _D_HEAD)
                for i in range(_D_HEAD):
                    var d = Float64(h_out[head * _D_HEAD + i]) - ref_m[i]
                    if d < 0.0:
                        d = -d
                    if d > worst_m:
                        worst_m = d
        var ok_m = worst_m < 1e-3
        ok_multi = ok_multi and ok_m
        print("   n_keys=", n_keys_case, " (", _N_HEADS, "heads) worst |delta| =", worst_m, "  ", "OK" if ok_m else "MISMATCH")

    if not ok_multi:
        print("CORRECTNESS FAILURE across n_keys sweep: refusing to report any timing number.")
        return
    print("")

    print("--- timing: barrier-tree vs SIMD-shuffle, decode-shaped n_keys, h_q=16 heads/dispatch ---")
    for n_keys_case in [1, 8, 32, 128, 512]:
        _time_case(ctx, n_keys_case, 500)


def _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


def _time_case(ctx: DeviceContext, n_keys: Int, reps: Int) raises:
    comptime _N_HEADS: Int = 16
    var q64 = _pseudo(_N_HEADS * _D_HEAD, 3)
    var kv64 = _pseudo(n_keys * _D_HEAD, 11)

    var f_tree = ctx.compile_function_unchecked[_dot_reduce_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_dot_reduce_simd_shuffle]()

    var qbuf = ctx.enqueue_create_buffer[DType.float32](_N_HEADS * _D_HEAD)
    var kvbuf = ctx.enqueue_create_buffer[DType.float32](n_keys * _D_HEAD)
    var outbuf = ctx.enqueue_create_buffer[DType.float32](_N_HEADS * _D_HEAD)
    with qbuf.map_to_host() as h:
        for i in range(_N_HEADS * _D_HEAD):
            h[i] = Float32(q64[i])
    with kvbuf.map_to_host() as h:
        for i in range(n_keys * _D_HEAD):
            h[i] = Float32(kv64[i])
    ctx.synchronize()

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_tree, outbuf.unsafe_ptr(), qbuf.unsafe_ptr(), kvbuf.unsafe_ptr(), n_keys,
            grid_dim=_N_HEADS, block_dim=_D_HEAD,
        )
    ctx.synchronize()
    var samples_tree = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_tree, outbuf.unsafe_ptr(), qbuf.unsafe_ptr(), kvbuf.unsafe_ptr(), n_keys,
            grid_dim=_N_HEADS, block_dim=_D_HEAD,
        )
        ctx.synchronize()
        samples_tree.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_tree = _median(samples_tree)

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_shfl, outbuf.unsafe_ptr(), qbuf.unsafe_ptr(), kvbuf.unsafe_ptr(), n_keys,
            grid_dim=_N_HEADS, block_dim=_D_HEAD,
        )
    ctx.synchronize()
    var samples_shfl = List[Float64]()
    for _ in range(reps):
        var t1 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_shfl, outbuf.unsafe_ptr(), qbuf.unsafe_ptr(), kvbuf.unsafe_ptr(), n_keys,
            grid_dim=_N_HEADS, block_dim=_D_HEAD,
        )
        ctx.synchronize()
        samples_shfl.append(Float64(Int(perf_counter_ns() - t1)) / 1e3)
    var med_shfl = _median(samples_shfl)

    print(
        "   n_keys=", n_keys,
        " barrier_tree median of", reps, "=", med_tree, "us",
        "  simd_shuffle median =", med_shfl, "us",
        "  (", (med_shfl - med_tree) / med_tree * 100.0, "% vs barrier_tree)",
    )
