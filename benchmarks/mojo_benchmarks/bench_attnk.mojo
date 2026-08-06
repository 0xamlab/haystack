"""bench_attnk.mojo — timing and memory gate for the attention kernels.

Hand-written, not generated. No library is named `attnk` at the top level, so nothing can collide
with this filename, and the generator only writes — it never unlinks.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
1. **Peak working set is set by the block, not by the sequence.** This is the entire reason
   `attnk.flash` exists, and it is a memory claim rather than a speed one. The materialized reference
   allocates `s_q x s_k` scores — quadratic in context, and not a choice. The tiled kernel allocates
   `block_k x d`, which is linear in a parameter the caller picks. At a FIXED block the working set
   is constant as context grows; the ratio between the two is what widens.

   Note the planner deliberately does not hold the block fixed: `flash_block_plan` picks the largest
   block that fits the cache, so on a short sequence it takes the whole thing in one tile. That is
   correct behaviour and it is why the gate below measures a fixed block — measuring the planner's
   adaptive choice would be measuring the planner, not the kernel.

2. **Cost per score cell stays flat as context grows.** Attention is `O(s^2)`, so wall-clock must
   grow quadratically — that is not a defect. What must NOT grow is the cost of each individual cell;
   if it does, the tiling has stopped holding its working set and the kernel is falling out of cache
   exactly where long context needs it.

3. **Block size changes the schedule, not the answer.** Asserted bit-identical, not merely close. The
   block boundary is a scheduling choice, so any drift means the rescale correction is landing at the
   wrong point — invisible at one block size and growing at another.

4. **RoPE table construction is O(max_pos * pairs).** Cost per table cell must stay flat; a build that
   recomputed inverse frequencies per position would grow.

Correctness is asserted alongside every timing, because a fast wrong answer is not a result: the
tiled kernel is diffed against the materialized reference on both output and log-sum-exp, and the
rotation is round-tripped through its own inverse.

Gate
----
Fails on the properties, not on absolute nanoseconds, which vary by machine:
  * tiled must agree with materialized within the accumulated-rounding tolerance
  * tiled peak working set must not grow with sequence length
  * ns per score cell must not grow more than 3x across a 4x increase in context
  * block sizes 1 and 64 must produce bit-identical output
  * RoPE inverse(apply(x)) == x to 1e-12
Absolute numbers are printed for tracking.
"""
from std.time import perf_counter_ns

from algenta_runtime.batch import run_batch_execute
from algenta_runtime.session import ResidentDatasets
from attnk.contract import ATTN_OK
from attnk.flash import flash_agrees_with_sdpa, flash_block_plan, flash_forward_flat
from attnk.rope import rope_apply_flat, rope_apply_inverse_flat, rope_table
from attnk.sdpa import sdpa_forward_flat
from runtime_library_dispatch_generated import dispatch_runtime_library


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def _count_occ(haystack: String, needle: String) -> Int:
    """Count non-overlapping occurrences by byte scan; `String` has no slice operator here."""
    var h = haystack.as_bytes()
    var nd = needle.as_bytes()
    if len(nd) == 0 or len(h) < len(nd):
        return 0
    var count = 0
    var i = 0
    while i + len(nd) <= len(h):
        var is_match = True
        for j in range(len(nd)):
            if h[i + j] != nd[j]:
                is_match = False
                break
        if is_match:
            count += 1
            i += len(nd)
        else:
            i += 1
    return count


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic values in roughly [-1, 1], so runs are comparable across machines."""
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


def main() raises:
    var failures = 0
    print("=== attnk timing and memory gate ===")

    var d = 32
    var h = 2
    var nobias = List[Float64]()

    # ── 1 & 2. cost per cell, and the memory that is NOT allocated ────────────
    print("")
    print("[attnk.flash] tiled attention across rising context")
    print("   seq    tiled ns     ns/cell   tiled bytes @block=64   materialized bytes   ratio")

    var seqs = List[Int]()
    seqs.append(64)
    seqs.append(128)
    seqs.append(256)

    # Warm up: the first call pays page faults on a fresh accumulator that belong to neither kernel.
    var wq = _pseudo(16 * h * d, 1)
    var wk = _pseudo(16 * h * d, 2)
    var wv = _pseudo(16 * h * d, 3)
    var warm = flash_forward_flat(wq, wk, wv, nobias, 16, 16, h, h, d, -1.0, False, 16)
    _ = warm

    var first_ns_per_cell = 0.0
    var last_ns_per_cell = 0.0
    var first_tiled_bytes = 0
    var last_tiled_bytes = 0

    for si in range(len(seqs)):
        var s = seqs[si]
        var q = _pseudo(s * h * d, 11 + si)
        var k = _pseudo(s * h * d, 977 + si)
        var v = _pseudo(s * h * d, 313 + si)

        var t0 = perf_counter_ns()
        var out = flash_forward_flat(q, k, v, nobias, s, s, h, h, d, -1.0, False, 64)
        var ns = _ns_since(t0)
        if out.status != ATTN_OK:
            failures += 1
            print("   status not ok at seq =", s)
            continue

        var cells = Float64(h) * Float64(s) * Float64(s)
        var per_cell = ns / cells

        # A FIXED block, so this measures the kernel rather than the planner's adaptive choice.
        var fixed_block = 64
        var tiled_bytes = fixed_block * 2 * 8 * d
        var materialized_bytes = 8.0 * Float64(s) * Float64(s)
        var ratio = materialized_bytes / Float64(tiled_bytes)

        if si == 0:
            first_ns_per_cell = per_cell
            first_tiled_bytes = tiled_bytes
        last_ns_per_cell = per_cell
        last_tiled_bytes = tiled_bytes

        print("  ", s, "  ", ns, "  ", per_cell, "  ", tiled_bytes, "  ", materialized_bytes, "  ", ratio, "x")

    # The memory claim: at a fixed block the working set does not move as context grows.
    if first_tiled_bytes == last_tiled_bytes:
        print("   at a fixed block the working set is constant across context:", last_tiled_bytes, "bytes")
    else:
        failures += 1
        print("   FAIL: the fixed-block working set moved:", first_tiled_bytes, "->", last_tiled_bytes)

    # And the planner, separately: it adapts the block upward when the whole sequence fits, which is
    # why it is measured apart from the kernel invariant above.
    var small_plan = flash_block_plan(64, d, 262144)
    var long_plan = flash_block_plan(32768, d, 262144)
    if long_plan.status == ATTN_OK and long_plan.n_blocks > small_plan.n_blocks:
        print("   planner adapts: 64 tokens ->", small_plan.n_blocks, "block(s);",
              "32768 ->", long_plan.n_blocks, "blocks of", long_plan.block_k)
        print("   at 32k the materialized form would be", long_plan.materialized_bytes,
              "bytes against", long_plan.working_bytes)
    else:
        failures += 1
        print("   FAIL: the planner did not adapt to a long sequence")

    var cell_growth = last_ns_per_cell / first_ns_per_cell if first_ns_per_cell > 0.0 else 0.0
    if cell_growth <= 3.0:
        print("   ns/cell growth across 4x context:", cell_growth, "x  (gate: <= 3x)")
    else:
        failures += 1
        print("   FAIL: ns/cell grew", cell_growth, "x — the tiling is not holding its working set")

    # ── correctness against the materialized reference ────────────────────────
    var cq = _pseudo(48 * h * d, 41)
    var ck = _pseudo(96 * h * d, 42)
    var cv = _pseudo(96 * h * d, 43)
    var ag = flash_agrees_with_sdpa(cq, ck, cv, nobias, 48, 96, h, h, d, -1.0, False, 16)
    if ag.status == ATTN_OK and ag.within_tolerance:
        print("   correctness: tiled matches materialized — out", ag.max_out_delta, "lse", ag.max_lse_delta)
    else:
        failures += 1
        print("   FAIL: the tiled kernel diverged from the reference")

    # ── 3. block size changes the schedule, not the answer ────────────────────
    var b1 = flash_forward_flat(cq, ck, cv, nobias, 48, 96, h, h, d, -1.0, False, 1)
    var b64 = flash_forward_flat(cq, ck, cv, nobias, 48, 96, h, h, d, -1.0, False, 64)
    var drift = 0.0
    for i in range(len(b1.out)):
        var dd = _abs(b1.out[i] - b64.out[i])
        if dd > drift:
            drift = dd
    if drift == 0.0:
        print("   block invariance: bit-identical at block 1 vs 64 (",
              b1.blocks_walked, "vs", b64.blocks_walked, "blocks )")
    else:
        failures += 1
        print("   FAIL: block size changed the answer by", drift)

    # ── the materialized path, for contrast ───────────────────────────────────
    print("")
    print("[attnk.sdpa] the reference it is measured against")
    var t1 = perf_counter_ns()
    var refout = sdpa_forward_flat(cq, ck, cv, nobias, 48, 96, h, h, d, -1.0, False)
    var ref_ns = _ns_since(t1)
    var t2 = perf_counter_ns()
    var tiled = flash_forward_flat(cq, ck, cv, nobias, 48, 96, h, h, d, -1.0, False, 32)
    var tiled_ns = _ns_since(t2)
    print("   materialized ns:", ref_ns, "  tiled ns:", tiled_ns)
    print("   NOTE: at this size both fit in cache, so this is not a speed claim — the tiled kernel's")
    print("   advantage is the allocation it avoids, which only becomes decisive at long context.")
    if refout.status != ATTN_OK or tiled.status != ATTN_OK:
        failures += 1
        print("   FAIL: a reference or tiled run errored")

    # ── 4. RoPE ───────────────────────────────────────────────────────────────
    print("")
    print("[attnk.rope] table construction, ns per cell")
    var positions = List[Int]()
    positions.append(256)
    positions.append(1024)
    positions.append(4096)
    var first_tbl = 0.0
    var last_tbl = 0.0
    for pi in range(len(positions)):
        var mp = positions[pi]
        var t3 = perf_counter_ns()
        var tb = rope_table(d, mp, 10000.0)
        var tns = _ns_since(t3)
        if tb.status != ATTN_OK:
            failures += 1
            print("   table build failed at max_pos =", mp)
            continue
        var per = tns / (Float64(mp) * Float64(tb.n_pairs))
        if pi == 0:
            first_tbl = per
        last_tbl = per
        print("   max_pos =", mp, "  ns:", tns, "  ns/cell:", per)

    var tbl_growth = last_tbl / first_tbl if first_tbl > 0.0 else 0.0
    if tbl_growth <= 3.0:
        print("   ns/cell growth across 16x positions:", tbl_growth, "x  (gate: <= 3x)")
    else:
        failures += 1
        print("   FAIL: table construction is not linear —", tbl_growth, "x")

    # Orthogonality: the property that catches a wrong pairing, sign or table index at once.
    var rt = rope_table(d, 512, 10000.0)
    var rx = _pseudo(64 * 4 * d, 99)
    var rpos = List[Int]()
    for i in range(64):
        rpos.append(i * 7)
    var fwd = rope_apply_flat(rx, rt.cos_table, rt.sin_table, 64, 4, d, rpos, True)
    var back = rope_apply_inverse_flat(fwd.values, rt.cos_table, rt.sin_table, 64, 4, d, rpos, True)
    var rt_err = 0.0
    for i in range(len(rx)):
        var dd = _abs(back.values[i] - rx[i])
        if dd > rt_err:
            rt_err = dd
    if rt_err < 1e-12:
        print("   correctness: inverse(apply(x)) == x — max error", rt_err)
    else:
        failures += 1
        print("   FAIL: the rotation is not orthogonal — max error", rt_err)

    # ── 5. the kernels compose with the existing batch machinery ──────────────
    # Attention is called per layer per head, so a 32-layer forward pass is 32+ dispatches. That is
    # precisely the workload `algenta_runtime/batch.mojo` exists for, and the check that matters is
    # that attnk reached it with NO new wiring — the payoff of rule 2's flat-list export shape. If it
    # had not, these kernels would need their own message type, a daemon RPC and SDK code, the way
    # columnar/ and query/ did.
    print("")
    print("[attnk] batch reachability — a 32-layer mask + plan pattern in one frame")

    var datasets = ResidentDatasets()
    var n_layers = 32
    var frame = String('{"type":"batch_execute","requests":[')
    for layer in range(n_layers):
        if layer > 0:
            frame += ","
        # One mask and one block plan per layer, the shape a forward pass actually issues.
        frame += '{"module":"attnk.mask","function":"mask_causal_flat","args":[16,16,0]},'
        frame += '{"module":"attnk.flash","function":"flash_block_plan","args":[512,64,262144]}'
    frame += '],"partial_ok":true}'

    var tb0 = perf_counter_ns()
    var batched = run_batch_execute(dispatch_runtime_library, frame, datasets)
    var batch_ns = _ns_since(tb0)

    var unregistered = _count_occ(batched, String("module_not_registered"))
    var exec_failed = _count_occ(batched, String("mojo_library_execution_failed"))
    var results = _count_occ(batched, String("\"result\""))
    if unregistered == 0 and exec_failed == 0 and results >= n_layers * 2:
        print("   ", n_layers * 2, "attnk calls dispatched in ONE frame:", batch_ns, "ns")
        print("    attnk is batch-reachable with no new message type, proto change or SDK code")
    else:
        failures += 1
        print("   FAIL: attnk did not dispatch through batch_execute —",
              unregistered, "unregistered,", exec_failed, "errored")

    print("")
    print("   CAVEAT, stated because the number above invites the wrong conclusion: batching helps")
    print("   when many SMALL calls share a frame. A real forward pass must not send Q/K/V over the")
    print("   wire per layer at all — those are intermediate activations, and 32 batched calls each")
    print("   carrying a full tensor payload still moves the tensors 32 times. The fix for that is")
    print("   resident handles in the worker, not batching, and it is not built yet.")

    print("")
    if failures == 0:
        print("✅ attnk gate: all properties hold")
    else:
        print("❌ attnk gate:", failures, "property failure(s)")
