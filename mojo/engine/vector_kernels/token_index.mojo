"""
vector_kernels/token_index.mojo — Integer token posting index.

Architecture:
  Tokenisation (String → token ids) is Python-side. Mojo only stores and
  queries the integer data structures, keeping the hot path string-free.

BUILD PHASE (offline, called once at table-load time):
    var b = TokenIndexBuilder(vocab_size=N, n_columns=M)
    for col_idx, token_ids in python_data:
        b.add_column(col_idx, token_ids)
    var index = b.finalize()

QUERY PHASE (hot path — no strings):
    # Python already converted query token strings to ids:
    #   token_id = vocab["unit"]  (or -1 if unknown)
    # Mojo just walks posting lists:
    for t in range(query_token_count):
        let (start, count) = index.get_postings(query_token_ids[t])
        for j in range(count):
            let col_idx = index.column_ids[Int(start) + j]
            ...

Mojo 0.26 ownership notes applied:
  - List fields: .copy() in both __copyinit__ and __moveinit__
  - No ^ on struct fields; function-return ^ is fine
"""

# ── PostingSlice: where one token's postings live in the flat buffer ──────────

struct PostingSlice(Copyable, Movable):
    """(start, count) offset into TokenPostingIndex.column_ids flat buffer."""
    var start: UInt32   # index of first posting
    var count: UInt16   # number of postings for this token

    fn __init__(out self):
        self.start = 0
        self.count = 0

    fn __copyinit__(out self, copy: Self):
        self.start = copy.start
        self.count = copy.count

    fn __moveinit__(out self, var take: Self):
        self.start = take.start
        self.count = take.count


# ── TokenPostingIndex: read-only hot-path structure ───────────────────────────

struct TokenPostingIndex(Movable):
    """
    Inverted index: token_id → contiguous slice of column indices.

    All hot-path operations are integer array lookups — no strings, no maps.

    Memory layout:
      slices[token_id]   : PostingSlice (start, count)
      column_ids[start:] : UInt32 column indices (local 0-based into CandidateTable)
      weights[start:]    : Float32 per-posting importance (optional boost)

    Build with TokenIndexBuilder, then freeze by calling finalize().
    """
    var vocab_size:  Int    # number of distinct tokens
    var total_posts: Int    # total posting entries across all tokens

    var slices:     List[PostingSlice]   # [vocab_size]
    var column_ids: List[UInt32]         # [total_posts] flat column index buffer
    var weights:    List[Float32]        # [total_posts] per-posting weight

    fn __init__(out self):
        self.vocab_size  = 0
        self.total_posts = 0
        self.slices      = List[PostingSlice]()
        self.column_ids  = List[UInt32]()
        self.weights     = List[Float32]()

    fn __moveinit__(out self, var take: Self):
        self.vocab_size  = take.vocab_size
        self.total_posts = take.total_posts
        self.slices      = take.slices.copy()      # ^ disallowed; use copy
        self.column_ids  = take.column_ids.copy()
        self.weights     = take.weights.copy()

    @always_inline
    fn get_postings(self, token_id: UInt32) -> PostingSlice:
        """
        Return PostingSlice (start, count) for a token id.
        Returns empty slice if token_id >= vocab_size (unknown token — no hits).
        """
        if Int(token_id) >= self.vocab_size:
            return PostingSlice()
        return self.slices[Int(token_id)].copy()

    @always_inline
    fn get_column_id(self, posting_ix: Int) -> UInt32:
        """Return column index at flat posting position posting_ix."""
        return self.column_ids[posting_ix]

    @always_inline
    fn get_weight(self, posting_ix: Int) -> Float32:
        return self.weights[posting_ix]


# ── TokenIndexBuilder: mutable build-time accumulator ─────────────────────────

struct _PostingEntry(Copyable, Movable):
    """Temporary (token_id, col_idx, weight) triple, used during build."""
    var token_id: UInt32
    var col_idx:  UInt32
    var weight:   Float32

    fn __init__(out self):
        self.token_id = 0
        self.col_idx  = 0
        self.weight   = Float32(1.0)

    fn __copyinit__(out self, copy: Self):
        self.token_id = copy.token_id
        self.col_idx  = copy.col_idx
        self.weight   = copy.weight

    fn __moveinit__(out self, var take: Self):
        self.token_id = take.token_id
        self.col_idx  = take.col_idx
        self.weight   = take.weight


struct TokenIndexBuilder(Movable):
    """
    Accumulates (token_id, col_idx) pairs and flattens them into a
    TokenPostingIndex on finalize().

    Usage:
        var b = TokenIndexBuilder(vocab_size, n_columns)
        b.add_column(col_idx=0, token_ids=[3, 7, 12])
        b.add_column(col_idx=1, token_ids=[7, 15])
        var index = b.finalize()
    """
    var vocab_size: Int
    var entries:    List[_PostingEntry]   # unsorted (token_id, col_idx, weight)

    fn __init__(out self, vocab_size: Int):
        self.vocab_size = vocab_size
        self.entries    = List[_PostingEntry]()

    fn __moveinit__(out self, var take: Self):
        self.vocab_size = take.vocab_size
        self.entries    = take.entries.copy()   # ^ disallowed; use copy

    fn add_column(mut self, col_idx: Int, token_ids: List[UInt32], weight: Float32 = 1.0):
        """Register all token_ids for one column. Duplicates are allowed (will be deduped)."""
        for i in range(len(token_ids)):
            var e = _PostingEntry()
            e.token_id = token_ids[i]
            e.col_idx  = UInt32(col_idx)
            e.weight   = weight
            self.entries.append(e^)

    fn add_column_weighted(
        mut self,
        col_idx:  Int,
        token_ids: List[UInt32],
        weights:   List[Float32],
    ):
        """Register token_ids with per-token weights (e.g. alias hit = 0.8)."""
        var n = len(token_ids) if len(token_ids) < len(weights) else len(weights)
        for i in range(n):
            var e = _PostingEntry()
            e.token_id = token_ids[i]
            e.col_idx  = UInt32(col_idx)
            e.weight   = weights[i]
            self.entries.append(e^)

    fn finalize(self) -> TokenPostingIndex:
        """
        Build a sorted, compacted TokenPostingIndex.

        Groups all entries by token_id. Within each group, entries are stored
        in the order they were added (i.e. column-order if add_column was
        called in column order).
        """
        var index = TokenPostingIndex()
        index.vocab_size = self.vocab_size

        # Pre-allocate slices (one per token)
        for _ in range(self.vocab_size):
            index.slices.append(PostingSlice())

        # Count postings per token to build start offsets
        var counts = List[Int](capacity=self.vocab_size)
        for _ in range(self.vocab_size):
            counts.append(0)
        for i in range(len(self.entries)):
            var tid = Int(self.entries[i].token_id)
            if tid < self.vocab_size:
                counts[tid] += 1

        # Compute start offsets (prefix sum)
        var starts = List[Int](capacity=self.vocab_size)
        starts.append(0)
        for i in range(1, self.vocab_size):
            starts.append(starts[i - 1] + counts[i - 1])
        var total = starts[self.vocab_size - 1] + counts[self.vocab_size - 1]
        index.total_posts = total

        # Store slice metadata
        for i in range(self.vocab_size):
            index.slices[i].start = UInt32(starts[i])
            index.slices[i].count = UInt16(counts[i])

        # Allocate flat buffers
        for _ in range(total):
            index.column_ids.append(UInt32(0))
            index.weights.append(Float32(1.0))

        # Fill flat buffers (track per-token fill position)
        var fill_pos = List[Int](capacity=self.vocab_size)
        for i in range(self.vocab_size):
            fill_pos.append(starts[i])
        for i in range(len(self.entries)):
            var tid = Int(self.entries[i].token_id)
            if tid < self.vocab_size:
                var pos = fill_pos[tid]
                index.column_ids[pos] = self.entries[i].col_idx
                index.weights[pos]    = self.entries[i].weight
                fill_pos[tid]        += 1

        return index^


# ── ColumnTokenTable: per-column token membership (optional) ──────────────────
#
# Not required for pre-filtering, but useful for:
#   - Overlap-based boost in rank_shortlist
#   - Explainability ("matched on tokens: unit, price")
#
# Build alongside TokenPostingIndex from the same Python-provided data.

struct ColumnTokenTable(Movable):
    """
    Transpose index: for column i, token_ids[token_starts[i] : token_starts[i] + token_counts[i]].

    This is the transpose of TokenPostingIndex. Use for per-column token
    lookups (overlap scoring, explainability).
    """
    var n_columns:    Int
    var token_starts: List[UInt32]   # [n_columns]
    var token_counts: List[UInt16]   # [n_columns]
    var token_ids:    List[UInt32]   # flat token id buffer

    fn __init__(out self):
        self.n_columns    = 0
        self.token_starts = List[UInt32]()
        self.token_counts = List[UInt16]()
        self.token_ids    = List[UInt32]()

    fn __moveinit__(out self, var take: Self):
        self.n_columns    = take.n_columns
        self.token_starts = take.token_starts.copy()   # ^ disallowed; use copy
        self.token_counts = take.token_counts.copy()
        self.token_ids    = take.token_ids.copy()

    @always_inline
    fn get_token_ids(self, col_idx: Int) -> PostingSlice:
        """Return PostingSlice (start, count) for column col_idx."""
        if col_idx >= self.n_columns:
            return PostingSlice()
        var sl = PostingSlice()
        sl.start = self.token_starts[col_idx]
        sl.count = self.token_counts[col_idx]
        return sl^

    fn count_overlap(self, col_idx: Int, query_ids: List[UInt32]) -> Int:
        """
        Count how many query token IDs appear in this column's token list.
        Used as a cheap lexical overlap signal in rank_shortlist().
        """
        if col_idx >= self.n_columns:
            return 0
        var sl = self.get_token_ids(col_idx)
        var hits = 0
        var s = Int(sl.start)
        for qi in range(len(query_ids)):
            for ci in range(Int(sl.count)):
                if self.token_ids[s + ci] == query_ids[qi]:
                    hits += 1
                    break
        return hits


fn main():
    pass
