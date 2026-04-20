"""
vector_kernels/prefilter.mojo — Token + role + source candidate pre-filter.

Shrinks "all N columns" to a shortlist of ~8–64 candidates before the SIMD
scorer runs. Keeps latency flat as schema size grows.

Algorithm:
  1. Walk posting lists for each query token
  2. Apply source gate: skip candidates from wrong document type
  3. Apply role gate: skip clearly incompatible roles
  4. Dedupe via epoch marks (O(1) per candidate, O(1) "clear" per query)
  5. Track per-candidate token-hit count for shortlist pre-sorting

All hot-path operations: integer comparisons, pointer/index reads.
No strings, no allocations after CandidateScratch is built.

Usage:
    # Build once
    var scratch = CandidateScratch(n_columns=len(table.entries), shortlist_cap=64)

    # Per request
    scratch.next_epoch()
    prefilter_candidates(table, query_token_ids, query_src, query_role, index, scratch)
    # scratch.candidate_count candidates ready
    rank_shortlist(table, req, scratch)   # from batch_ranker.mojo
"""

from std.math import sqrt


# ── Shared constants (mirror table.mojo — consolidate once pkg imports ready) ─

comptime SOURCE_UNKNOWN: UInt16 = 0
comptime SOURCE_POS:     UInt16 = 1
comptime SOURCE_BACKLOG: UInt16 = 2
comptime SOURCE_INVOICE: UInt16 = 3

comptime ROLE_OTHER:   UInt8 = 0
comptime ROLE_UNIT:    UInt8 = 1
comptime ROLE_DERIVED: UInt8 = 2

comptime MAX_SHORTLIST: Int = 64   # hard cap on pre-filter output


# ── Role compatibility gate ───────────────────────────────────────────────────

@always_inline
fn _role_compatible(query_role: UInt8, cand_role: UInt8) -> Bool:
    """
    True if the candidate role is worth scoring given the query role.

    Compatibility matrix:
      query=OTHER   → pass all (no filter)
      query=UNIT    → pass UNIT, OTHER (suppress DERIVED)
      query=DERIVED → pass DERIVED, OTHER (suppress UNIT)

    Suppressing clear mismatches keeps confidence_gap wide on the winner.
    """
    if query_role == ROLE_OTHER:
        return True
    if cand_role == ROLE_OTHER:
        return True   # unknown cand — allow, let scorer sort it out
    return cand_role == query_role   # exact match only for typed queries


# ── CandidateScratch: pre-allocated, epoch-reset scratch buffer ───────────────

struct CandidateScratch(Movable):
    """
    Pre-allocated scratch buffer for one prefilter pass.

    Create ONE instance per thread/session. Reuse across all requests by
    calling next_epoch() at the start of each new query — O(1) reset,
    no memset, no allocator.

    Capacity:
      n_columns:    max columns in any CandidateTable (safe to over-allocate)
      shortlist_cap: max candidates to emit (typically 32 or 64)

    Memory:
      marks:          [n_columns]    × UInt32   epoch mark per column
      slots:          [n_columns]    × Int32    position in candidate_ids (-1 = not added)
      candidate_ids:  [shortlist_cap] × UInt32  output candidate column indices
      token_hits:     [shortlist_cap] × UInt16  per-candidate query token hit count
    """
    var epoch:           UInt32
    var n_columns:       Int
    var shortlist_cap:   Int
    var candidate_count: Int

    var marks:          List[UInt32]
    var slots:          List[Int32]
    var candidate_ids:  List[UInt32]
    var token_hits:     List[UInt16]

    fn __init__(out self, n_columns: Int, shortlist_cap: Int):
        self.epoch           = 1
        self.n_columns       = n_columns
        self.shortlist_cap   = shortlist_cap
        self.candidate_count = 0

        self.marks         = List[UInt32](capacity=n_columns)
        self.slots         = List[Int32](capacity=n_columns)
        self.candidate_ids = List[UInt32](capacity=shortlist_cap)
        self.token_hits    = List[UInt16](capacity=shortlist_cap)

        for _ in range(n_columns):
            self.marks.append(UInt32(0))
            self.slots.append(Int32(-1))
        for _ in range(shortlist_cap):
            self.candidate_ids.append(UInt32(0))
            self.token_hits.append(UInt16(0))

    fn __moveinit__(out self, var take: Self):
        self.epoch           = take.epoch
        self.n_columns       = take.n_columns
        self.shortlist_cap   = take.shortlist_cap
        self.candidate_count = take.candidate_count
        self.marks           = take.marks.copy()           # ^ disallowed; use copy
        self.slots           = take.slots.copy()
        self.candidate_ids   = take.candidate_ids.copy()
        self.token_hits      = take.token_hits.copy()

    fn next_epoch(mut self):
        """
        O(1) per-query reset. Increment epoch so all prior marks look stale.
        candidate_count reset. On UInt32 wraparound: do a full clear.
        """
        self.candidate_count = 0
        if self.epoch == UInt32(0xFFFFFFFF):
            # Overflow — clear all marks and restart
            for i in range(self.n_columns):
                self.marks[i] = UInt32(0)
                self.slots[i] = Int32(-1)
            self.epoch = 1
        else:
            self.epoch += 1

    fn is_at_capacity(self) -> Bool:
        return self.candidate_count >= self.shortlist_cap


# ── PostingSlice forward-declared for inline import from token_index.mojo ────
#
# In production, import PostingSlice + TokenPostingIndex from token_index.mojo.
# For standalone compilation:

struct _PostingSlice(Copyable, Movable):
    var start: UInt32
    var count: UInt16
    fn __init__(out self): self.start = 0; self.count = 0
    fn __copyinit__(out self, copy: Self): self.start = copy.start; self.count = copy.count
    fn __moveinit__(out self, var take: Self): self.start = take.start; self.count = take.count


# ── Pre-filter entry points ───────────────────────────────────────────────────

fn prefilter_by_tokens(
    n_columns:       Int,             # table.entries length
    source_ids:      List[UInt16],    # table column source_ids (parallel to entries)
    role_ids:        List[UInt8],     # table column role_ids
    query_src:       UInt16,
    query_role:      UInt8,
    query_token_ids: List[UInt32],    # token IDs from Python tokenization
    slices:          List[_PostingSlice],  # posting index slices[token_id]
    column_ids:      List[UInt32],    # posting index flat column buffer
    mut scratch:     CandidateScratch,
):
    """
    Core pre-filter: walks posting lists, applies gates, dedupes via epoch.

    Inputs:
      - Flat parallel arrays from CandidateTable (source_ids, role_ids)
      - Query token IDs and source/role constraints
      - TokenPostingIndex (slices + flat column_ids buffer)
      - Mutable scratch (will be written; call next_epoch() before this)

    After return:
      scratch.candidate_count    — number of candidates found
      scratch.candidate_ids[0:N] — column indices into the table
      scratch.token_hits[0:N]    — per-candidate query token hit count

    Complexity: O(Σ postings[token_i]) — typically much smaller than O(N_total)
    """
    var n_tokens = len(query_token_ids)
    var vocab_size = len(slices)

    for t in range(n_tokens):
        var tok_id = Int(query_token_ids[t])
        if tok_id >= vocab_size:
            continue   # unknown token — no postings

        var start = Int(slices[tok_id].start)
        var count = Int(slices[tok_id].count)

        for j in range(count):
            var col_idx = Int(column_ids[start + j])
            if col_idx >= n_columns:
                continue

            # ── Source gate ────────────────────────────────────────────────
            # If query specifies a source, skip candidates from a different
            # known source. SOURCE_UNKNOWN candidates are always allowed.
            if query_src != SOURCE_UNKNOWN:
                var c_src = source_ids[col_idx]
                if c_src != SOURCE_UNKNOWN and c_src != query_src:
                    continue

            # ── Role gate ──────────────────────────────────────────────────
            if not _role_compatible(query_role, role_ids[col_idx]):
                continue

            # ── Epoch dedup ────────────────────────────────────────────────
            if scratch.marks[col_idx] != scratch.epoch:
                # First hit for this column in this query
                if scratch.is_at_capacity():
                    continue   # shortlist full — skip additional candidates
                var slot = scratch.candidate_count
                scratch.marks[col_idx]      = scratch.epoch
                scratch.slots[col_idx]      = Int32(slot)
                scratch.candidate_ids[slot] = UInt32(col_idx)
                scratch.token_hits[slot]    = UInt16(1)
                scratch.candidate_count    += 1
            else:
                # Already in shortlist — increment hit count (cap at 255)
                var slot = Int(scratch.slots[col_idx])
                if slot >= 0 and scratch.token_hits[slot] < UInt16(255):
                    scratch.token_hits[slot] += UInt16(1)


fn prefilter_fallback_all(
    n_columns:   Int,
    source_ids:  List[UInt16],
    role_ids:    List[UInt8],
    query_src:   UInt16,
    query_role:  UInt8,
    mut scratch: CandidateScratch,
):
    """
    Fallback: add all source/role-compatible columns to the shortlist.

    Use when prefilter_by_tokens returns too few candidates (< 2).
    Equivalent to the original all-column scan in CandidateTable.rank().
    """
    for col_idx in range(n_columns):
        if scratch.is_at_capacity():
            break

        if query_src != SOURCE_UNKNOWN:
            var c_src = source_ids[col_idx]
            if c_src != SOURCE_UNKNOWN and c_src != query_src:
                continue

        if not _role_compatible(query_role, role_ids[col_idx]):
            continue

        if scratch.marks[col_idx] != scratch.epoch:
            var slot = scratch.candidate_count
            scratch.marks[col_idx]      = scratch.epoch
            scratch.slots[col_idx]      = Int32(slot)
            scratch.candidate_ids[slot] = UInt32(col_idx)
            scratch.token_hits[slot]    = UInt16(0)
            scratch.candidate_count    += 1


# ── High-level helper: token filter → fallback if needed ─────────────────────

fn prefilter(
    n_columns:       Int,
    source_ids:      List[UInt16],
    role_ids:        List[UInt8],
    query_src:       UInt16,
    query_role:      UInt8,
    query_token_ids: List[UInt32],
    slices:          List[_PostingSlice],
    column_ids:      List[UInt32],
    mut scratch:     CandidateScratch,
    min_candidates:  Int = 2,
):
    """
    Token-based filter with automatic fallback to all-column scan.

    1. Run token posting filter.
    2. If result has < min_candidates, run fallback_all (relaxed gates).

    This preserves recall for edge cases (new columns, unusual naming).
    """
    scratch.next_epoch()
    prefilter_by_tokens(
        n_columns, source_ids, role_ids,
        query_src, query_role, query_token_ids,
        slices, column_ids,
        scratch,
    )
    if scratch.candidate_count < min_candidates:
        # Reset and run broad fallback
        scratch.next_epoch()
        prefilter_fallback_all(
            n_columns, source_ids, role_ids,
            SOURCE_UNKNOWN,   # relax source gate
            ROLE_OTHER,       # relax role gate
            scratch,
        )


# ── PrefilterStats: diagnostic counter (zero-cost if unused) ─────────────────

struct PrefilterStats(Copyable, Movable):
    """
    Optional counters for measuring pre-filter effectiveness.
    Record: n_queries, total_candidates_after_filter, total_candidates_before.
    """
    var n_queries:    UInt32
    var total_before: UInt32   # sum of n_columns across all calls
    var total_after:  UInt32   # sum of candidate_count across all calls

    fn __init__(out self):
        self.n_queries    = 0
        self.total_before = 0
        self.total_after  = 0

    fn __copyinit__(out self, copy: Self):
        self.n_queries    = copy.n_queries
        self.total_before = copy.total_before
        self.total_after  = copy.total_after

    fn __moveinit__(out self, var take: Self):
        self.n_queries    = take.n_queries
        self.total_before = take.total_before
        self.total_after  = take.total_after

    fn record(mut self, n_before: Int, n_after: Int):
        self.n_queries    += 1
        self.total_before += UInt32(n_before)
        self.total_after  += UInt32(n_after)

    fn reduction_ratio(self) -> Float32:
        """Average fraction of columns that reach the scorer."""
        if self.total_before == 0:
            return Float32(1.0)
        return Float32(Int(self.total_after)) / Float32(Int(self.total_before))


fn main():
    pass
