"""
vector_kernels/bench_prefilter.mojo — 4 paths × 4 schema sizes.

Measures:
  A. full_scan   — SIMD cosine over all N columns          O(N × 64)
  B. prefilter   — posting-list shortlist → SIMD on ~16    O(posts + K × 64)
  C. batch_scan  — 10-query batch, full scan each
  D. batch_pre   — 10-query batch, prefilter + score each

Schema sizes: N = {32, 128, 512, 2048}

Expected shape of results:
  N=32:   prefilter overhead visible (tiny shortlist; walk cost dominates)
  N=128:  prefilter roughly neutral
  N=512:  prefilter clearly wins
  N=2048: prefilter dominant; batch amplifies the gap

Token assignment per column (4 tokens, vocab=128):
  tok[0] = col % 128
  tok[1] = (col * 7 + 3)  % 128
  tok[2] = (col * 13 + 5) % 128
  tok[3] = (col * 3 + 11) % 128

Query uses tokens [0, 1, 2, 3], hitting ~N/32 columns per token → ~N/8 unique.
At N=512 and N=2048 the shortlist saturates at SLIST_CAP=64 (realistic production scenario).

Run:
    cd mojo_env
    pixi run mojo run ../mojo/engine/vector_kernels/bench_prefilter.mojo
"""
from std.math import sqrt
from std.time import perf_counter_ns


# ── Constants ─────────────────────────────────────────────────────────────────

comptime VEC_DIM:      Int = 64
comptime SIMD_W:       Int = 8
comptime VOCAB_SIZE:   Int = 128
comptime SLIST_CAP:    Int = 64
comptime BATCH_SIZE:   Int = 10


# ── SIMD dot-product kernel ────────────────────────────────────────────────────

@always_inline
def _dot64(a: List[Float32], b: List[Float32]) -> Float32:
    var pa = a.unsafe_ptr()
    var pb = b.unsafe_ptr()
    var a0 = (pa +  0).load[width=SIMD_W]() * (pb +  0).load[width=SIMD_W]()
    var a1 = (pa +  8).load[width=SIMD_W]() * (pb +  8).load[width=SIMD_W]()
    var a2 = (pa + 16).load[width=SIMD_W]() * (pb + 16).load[width=SIMD_W]()
    var a3 = (pa + 24).load[width=SIMD_W]() * (pb + 24).load[width=SIMD_W]()
    var a4 = (pa + 32).load[width=SIMD_W]() * (pb + 32).load[width=SIMD_W]()
    var a5 = (pa + 40).load[width=SIMD_W]() * (pb + 40).load[width=SIMD_W]()
    var a6 = (pa + 48).load[width=SIMD_W]() * (pb + 48).load[width=SIMD_W]()
    var a7 = (pa + 56).load[width=SIMD_W]() * (pb + 56).load[width=SIMD_W]()
    return ((a0 + a1) + (a2 + a3) + (a4 + a5) + (a6 + a7)).reduce_add()


@always_inline
def _cosine(
    qv: List[Float32], cv: List[Float32],
    q_ni: Float32, c_ni: Float32,
) -> Float32:
    if q_ni == Float32(0.0) or c_ni == Float32(0.0):
        return Float32(0.0)
    var r = _dot64(qv, cv) * q_ni * c_ni
    if r > Float32(1.0): return Float32(1.0)
    if r < Float32(0.0): return Float32(0.0)
    return r


# ── Minimal structs ────────────────────────────────────────────────────────────

struct _Vec64(Copyable, Movable):
    var data: List[Float32]

    def __init__(out self):
        self.data = List[Float32](capacity=VEC_DIM)
        for _ in range(VEC_DIM):
            self.data.append(Float32(0.0))

    def __copyinit__(out self, copy: Self):
        self.data = copy.data.copy()

    def __moveinit__(out self, var take: Self):
        self.data = take.data.copy()


struct _Entry(Copyable, Movable):
    var norm_inv: Float32
    var vec:      _Vec64

    def __init__(out self):
        self.norm_inv = Float32(0.0)
        self.vec      = _Vec64()

    def __copyinit__(out self, copy: Self):
        self.norm_inv = copy.norm_inv
        self.vec      = copy.vec.copy()

    def __moveinit__(out self, var take: Self):
        self.norm_inv = take.norm_inv
        self.vec      = take.vec.copy()


struct _PostingSlice(Copyable, Movable):
    var start: UInt32
    var count: UInt16

    def __init__(out self): self.start = 0; self.count = 0

    def __copyinit__(out self, copy: Self):
        self.start = copy.start
        self.count = copy.count

    def __moveinit__(out self, var take: Self):
        self.start = take.start
        self.count = take.count


struct _PostingIndex(Movable):
    """Inverted index: token_id → column indices."""
    var slices:     List[_PostingSlice]   # [VOCAB_SIZE]
    var column_ids: List[UInt32]          # flat posting buffer

    def __init__(out self):
        self.slices     = List[_PostingSlice](capacity=VOCAB_SIZE)
        self.column_ids = List[UInt32]()

    def __moveinit__(out self, var take: Self):
        self.slices     = take.slices.copy()
        self.column_ids = take.column_ids.copy()


# ── Token assignment ───────────────────────────────────────────────────────────

@always_inline
def _col_tok(col: Int, k: Int) -> Int:
    """Deterministic token assignment: 4 tokens per column, vocab size 128."""
    if k == 0: return col % VOCAB_SIZE
    if k == 1: return (col * 7  +  3) % VOCAB_SIZE
    if k == 2: return (col * 13 +  5) % VOCAB_SIZE
    return     (col * 3  + 11) % VOCAB_SIZE


# ── Data builders ──────────────────────────────────────────────────────────────

def _make_entries(n: Int) -> List[_Entry]:
    """
    Build N entries with deterministic float32 vectors.
    Each column's vec filled with (col + dim + 1) % 64 / 32.0, then L2-normalized.
    """
    var entries = List[_Entry](capacity=n)
    for col in range(n):
        var e = _Entry()
        var norm_sq = Float32(0.0)
        for d in range(VEC_DIM):
            var v = Float32((col + d + 1) % 64) / Float32(32.0)
            e.vec.data[d] = v
            norm_sq = norm_sq + v * v
        if norm_sq > Float32(0.0):
            e.norm_inv = Float32(1.0) / sqrt(norm_sq)
        entries.append(e^)
    return entries^


def _make_posting_index(n: Int) -> _PostingIndex:
    """
    Build token posting index for N columns using counting sort.
    Each column is assigned 4 deterministic token IDs.
    """
    var idx = _PostingIndex()

    # Count postings per token
    var counts = List[Int](capacity=VOCAB_SIZE)
    for _ in range(VOCAB_SIZE):
        counts.append(0)

    for col in range(n):
        for k in range(4):
            var tok = _col_tok(col, k)
            counts[tok] += 1

    # Prefix sum → start offsets
    var starts = List[Int](capacity=VOCAB_SIZE)
    starts.append(0)
    for i in range(1, VOCAB_SIZE):
        starts.append(starts[i - 1] + counts[i - 1])
    var total = starts[VOCAB_SIZE - 1] + counts[VOCAB_SIZE - 1]

    # Build slice metadata
    for i in range(VOCAB_SIZE):
        var sl = _PostingSlice()
        sl.start = UInt32(starts[i])
        sl.count = UInt16(counts[i])
        idx.slices.append(sl^)

    # Allocate flat buffer
    for _ in range(total):
        idx.column_ids.append(UInt32(0))

    # Fill flat buffer (track per-token fill position)
    var fill_pos = List[Int](capacity=VOCAB_SIZE)
    for i in range(VOCAB_SIZE):
        fill_pos.append(starts[i])

    for col in range(n):
        for k in range(4):
            var tok = _col_tok(col, k)
            var pos = fill_pos[tok]
            idx.column_ids[pos] = UInt32(col)
            fill_pos[tok] += 1

    return idx^


def _make_query() -> _Entry:
    """
    Build query: uniform vector (all components = 1.0), properly normalized.
    """
    var q = _Entry()
    for d in range(VEC_DIM):
        q.vec.data[d] = Float32(1.0)
    var norm_sq = Float32(VEC_DIM)    # 64 × 1² = 64
    q.norm_inv = Float32(1.0) / sqrt(norm_sq)
    return q^


def _query_token_ids() -> List[UInt32]:
    """Query tokens [0, 1, 2, 3] — hit ~N/8 columns for VOCAB_SIZE=128, 4 toks/col."""
    var ids = List[UInt32](capacity=4)
    ids.append(UInt32(0))
    ids.append(UInt32(1))
    ids.append(UInt32(2))
    ids.append(UInt32(3))
    return ids^


# ── Benchmark primitives ───────────────────────────────────────────────────────

def _full_scan(
    entries: List[_Entry],
    query:   _Entry,
    n:       Int,
) -> Float32:
    """Score all N entries; return best cosine."""
    var best = Float32(0.0)
    for i in range(n):
        var s = _cosine(query.vec.data, entries[i].vec.data, query.norm_inv, entries[i].norm_inv)
        if s > best:
            best = s
    return best


def _prefilter_score(
    entries:   List[_Entry],
    query:     _Entry,
    tok_ids:   List[UInt32],
    slices:    List[_PostingSlice],
    col_ids:   List[UInt32],
    mut marks: List[UInt32],
    mut cands: List[UInt32],
    mut epoch: UInt32,
) -> Float32:
    """
    Epoch-mark posting walk to build shortlist, then score only shortlist.
    Mirrors prefilter_by_tokens() from prefilter.mojo.
    """
    # O(1) epoch reset
    if epoch == UInt32(0xFFFFFFFF):
        for i in range(len(marks)):
            marks[i] = UInt32(0)
        epoch = UInt32(1)
    else:
        epoch += UInt32(1)

    var n_cands = 0

    # Walk posting lists for each query token
    for t in range(len(tok_ids)):
        var tok = Int(tok_ids[t])
        if tok >= VOCAB_SIZE:
            continue
        var start = Int(slices[tok].start)
        var count = Int(slices[tok].count)

        for j in range(count):
            var col = Int(col_ids[start + j])
            if marks[col] != epoch:
                if n_cands >= SLIST_CAP:
                    continue
                marks[col] = epoch
                cands[n_cands] = UInt32(col)
                n_cands += 1

    # Score only shortlist
    var best = Float32(0.0)
    for i in range(n_cands):
        var col = Int(cands[i])
        var s = _cosine(query.vec.data, entries[col].vec.data, query.norm_inv, entries[col].norm_inv)
        if s > best:
            best = s
    return best


# ── Tier runner ────────────────────────────────────────────────────────────────

def _run_tier(n: Int, iters: Int):
    """Build data for schema size N, run all four paths, report ns/query."""
    var entries = _make_entries(n)
    var idx     = _make_posting_index(n)
    var query   = _make_query()
    var tok_ids = _query_token_ids()

    # Prefilter scratch (pre-allocated)
    var marks = List[UInt32](capacity=n)
    var cands = List[UInt32](capacity=SLIST_CAP)
    for _ in range(n):         marks.append(UInt32(0))
    for _ in range(SLIST_CAP): cands.append(UInt32(0))
    var epoch = UInt32(1)

    # Count actual shortlist size for annotation
    # Use a sentinel epoch distinct from the init value (0) to avoid false-no-match
    var n_cands_check = 0
    var epoch_chk = UInt32(0xFFFF)
    for t in range(len(tok_ids)):
        var tok = Int(tok_ids[t])
        var start = Int(idx.slices[tok].start)
        var count = Int(idx.slices[tok].count)
        for j in range(count):
            var col = Int(idx.column_ids[start + j])
            if marks[col] != epoch_chk:
                if n_cands_check >= SLIST_CAP: continue
                marks[col] = epoch_chk
                n_cands_check += 1
    # Reset marks to 0 before timing (epoch starts at 1, so marks=0 != epoch=1)
    for i in range(n):
        marks[i] = UInt32(0)

    var acc = Float32(0.0)   # prevents dead-code elimination

    # ── Path A: full_scan single ──────────────────────────────────────────────
    var t0 = perf_counter_ns()
    for _ in range(iters):
        acc = acc + _full_scan(entries, query, n)
    var t1 = perf_counter_ns()
    var ns_a = Float64(t1 - t0) / Float64(iters)

    # ── Path B: prefilter single ──────────────────────────────────────────────
    var t2 = perf_counter_ns()
    for _ in range(iters):
        acc = acc + _prefilter_score(
            entries, query, tok_ids,
            idx.slices, idx.column_ids,
            marks, cands, epoch,
        )
    var t3 = perf_counter_ns()
    var ns_b = Float64(t3 - t2) / Float64(iters)

    # ── Path C: batch full_scan (10 queries) ──────────────────────────────────
    var t4 = perf_counter_ns()
    for _ in range(iters):
        for _ in range(BATCH_SIZE):
            acc = acc + _full_scan(entries, query, n)
    var t5 = perf_counter_ns()
    var ns_c = Float64(t5 - t4) / Float64(iters * BATCH_SIZE)

    # ── Path D: batch prefilter (10 queries) ──────────────────────────────────
    var t6 = perf_counter_ns()
    for _ in range(iters):
        for _ in range(BATCH_SIZE):
            acc = acc + _prefilter_score(
                entries, query, tok_ids,
                idx.slices, idx.column_ids,
                marks, cands, epoch,
            )
    var t7 = perf_counter_ns()
    var ns_d = Float64(t7 - t6) / Float64(iters * BATCH_SIZE)

    # Speedups
    var spd_b = ns_a / ns_b   if ns_b > 0.0 else Float64(0.0)
    var spd_d = ns_c / ns_d   if ns_d > 0.0 else Float64(0.0)

    print("[N=", n, " shortlist~", n_cands_check, "]")
    print("  A full_scan   single :", ns_a,  "ns/query")
    print("  B prefilter   single :", ns_b,  "ns/query  speedup vs A:", spd_b)
    print("  C full_scan   batch10:", ns_c,  "ns/query")
    print("  D prefilter   batch10:", ns_d,  "ns/query  speedup vs C:", spd_d)
    print()

    # Print checksum to prevent dead-code elimination of pure _full_scan loops
    print("  checksum:", acc)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== bench_prefilter_vs_fullscan ===")
    print("VEC_DIM=64  VOCAB=128  TOKS_PER_COL=4  QUERY_TOKS=4  SHORTLIST_CAP=64")
    print()

    # Warm up with a small run first
    _run_tier(32, 100)

    # Actual timed runs
    print("── 32 columns (2000 iters) ──────────────────────────────────────────")
    _run_tier(32,   2000)

    print("── 128 columns (2000 iters) ─────────────────────────────────────────")
    _run_tier(128,  2000)

    print("── 512 columns (1000 iters) ─────────────────────────────────────────")
    _run_tier(512,  1000)

    print("── 2048 columns (500 iters) ─────────────────────────────────────────")
    _run_tier(2048,  500)
