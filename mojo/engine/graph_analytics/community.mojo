"""
graph_analytics.community — Louvain modularity maximisation over `GraphCSR`, seeded.

What the tree already has, and why none of it answers the question
------------------------------------------------------------------
Three community-adjacent kernels exist and all three stay reachable:

* `graph.algorithms.connected_components(g)` labels *reachability* classes. A connected
  component is not a community: two dense clusters joined by one edge form a single
  component and two communities, so the two functions disagree on the most ordinary
  input there is. Components answer "can I get there"; modularity answers "is this
  denser than chance". Neither substitutes for the other.
* `graph_algorithms.modularity_contribution(edge_in_community, degree_u, degree_v,
  total_edges)` computes one Newman-Girvan pair term, `A_ij - k_i*k_j/(2m)`. It is the
  whole objective's inner step and it is *called* here — three times, at three
  granularities, and the derivations are in the docstrings below. Nothing in this file
  re-derives that expression.
* `social_network.community_label_propagation(adj, max_iter)` is label propagation on
  `List[List[Int]]`. It cannot be called from a CSR without materialising an adjacency
  list, it ignores edge weights, it rediscovers in-neighbours with an O(V * E) rescan
  per node, and it returns bare labels — so a caller cannot tell a converged fixed
  point from a labelling that was still moving when `max_iter` ran out, and cannot tell
  how good the labelling is. `community_label_propagation_driver` here is the CSR,
  weighted, seeded, status-carrying driver; the frozen one remains the fast path for a
  caller that already holds an adjacency list.

The objective, stated once
--------------------------
Over a symmetric non-negative weight matrix `W` with `k_i = sum_j W_ij` and
`2m = sum_i k_i`:

    Q = (1 / 2m) * sum_{i,j : c_i = c_j} [ W_ij - k_i * k_j / (2m) ]

Collapsing the inner sum per community with `in_c = sum_{i,j in c} W_ij` and
`tot_c = sum_{i in c} k_i` gives the form the algorithm actually evaluates:

    Q = (1 / 2m) * sum_c [ in_c - tot_c^2 / (2m) ]
      = (1 / 2m) * sum_c modularity_contribution(in_c, tot_c, tot_c, m)

— the same frozen kernel, applied per community instead of per pair, which is exact
algebra and not an approximation. `community_modularity_driver` uses that O(V + E)
form; `community_modularity_pairwise_driver` uses the literal per-pair sum over the
frozen kernel and exists so the collapse can be *checked* rather than believed. The
suite asserts the two agree to the last bit of a hand-computed value.

Direction and parallel edges: a CSR is directed, modularity is not
------------------------------------------------------------------
`W_ij = D_ij + D_ji`, where `D` sums the parallel `i -> j` edges of the input CSR. A
caller that stores both directions therefore gets `W = 2 * A`, and `Q` is invariant
under a uniform rescaling of all weights (numerator and denominator both scale), so the
one-directional and both-directional encodings of the same undirected graph return the
*same* modularity. The suite asserts that on a hand-computed value, because it is the
property a caller will assume without checking.

A stored self-loop of weight `w` lands on the diagonal as `W_ii = 2w`, which is the
convention that makes `k_i` count a loop twice — consistent with the off-diagonal
doubling, and the only choice under which aggregation preserves `Q`.

Parallel edges are summed, not minimised. `adjacency.graph_csr_dedupe_min` takes the
minimum because it answers a distance question; two parallel edges are two units of
attachment for a community question, so this file sums. That is why it does not call
`dedupe_min`, and it is the one place the two modules deliberately differ.

Negative and non-finite weights are refused, not absorbed
---------------------------------------------------------
The null model `k_i*k_j/(2m)` presumes non-negative weight: with a negative edge `2m`
can be zero or negative, `Q` leaves `[-1, 1]`, and the local-moving gain stops being a
lower bound on anything. Signed modularity is a different objective with a different
null model (positive and negative degrees normalised separately), not a special case of
this one — so `GRAPH_ERR_NEGATIVE_WEIGHT` is returned with no numbers attached rather
than a plausible-looking partition. NaN is tested before the sign test because
`nan < 0.0` is False, so a bare negativity check would let NaN through and then poison
every comparison in the greedy loop.

`2m == 0` — no edges, or every weight exactly zero — is the other refusal.
Modularity is `0/0` there, and every partition is equally good, so
`COMMUNITY_ERR_NO_EDGE_WEIGHT` is returned and `modularity` is
`COMMUNITY_NO_MODULARITY = -2.0`. That value is impossible for a real answer: `Q` lies
in `[-1, 1]` for any partition of a non-negatively-weighted graph, so a caller that
ignores the status reads a loud wrong number instead of a quiet plausible one.

Louvain without a random order is not reproducible; this one is addressed
------------------------------------------------------------------------
Louvain's result depends on the order nodes are visited in, and the standard
formulation shuffles. An implementation whose communities change between two runs on
the same graph cannot be used in a decision engine: two reports disagree and neither is
wrong. The visit order here is `determinism.sampling_keyed.permutation_keyed`, a
Fisher-Yates over Philox draws addressed by
`(master_seed, stream, draw_index)` — so the order is a pure function of
`(seed, level, pass)` and reproduces exactly, on any machine, forever.
`community_visit_order` returns that order, so a caller can *audit* the claim instead
of taking a reproducibility assertion on trust.

`draw_index` is `COMMUNITY_DRAW_STRIDE * (level * COMMUNITY_PASS_LIMIT + pass)`, so
distinct `(level, pass)` blocks do not share draws while a level has fewer than
`COMMUNITY_DRAW_STRIDE` nodes. Above that the blocks overlap, which costs draw
independence between passes and costs reproducibility nothing.

Determinism of the *result* needs the tie-breaks fixed too, not just the order. Among
candidate communities the rule is highest gain, then smallest community id, compared
with exact `>` and `==` — no tolerance band, because a band is not a transitive
ordering and would make the winner depend on scan order in a way nothing records. The
node's current community is privileged: a move requires
`gain > stay_gain + tolerance` strictly, which is what makes `Q` non-decreasing.

Why Q cannot go down, and why the loop ends
-------------------------------------------
Moving node `i` out of its community and into `c` changes `Q` by exactly
`(gain_c - gain_stay) / m`, where
`gain_c = modularity_contribution(k_i_to_c, k_i, tot_c, m)` and `tot_c` excludes `i`.
Both terms are measured against the same isolated-`i` baseline, so their difference is
the move's true effect. A move is taken only when that difference exceeds
`tolerance / m >= 0`, so every accepted move strictly increases `Q` by at least
`tolerance / m` and no pass can cycle. `Q` is bounded above by 1, so with
`tolerance > 0` the number of moves is bounded by `m / tolerance`; `max_passes` bounds
it regardless, and `converged` reports whether a pass ended with zero moves or the cap
ran out.

Aggregation preserves `Q` exactly: the level-`t+1` graph on community super-nodes has
`W'_ab = sum_{i in a, j in b} W_ij`, hence `k'_a = tot_a` and `2m' = 2m`, so the
singleton partition of level `t+1` scores exactly what level `t`'s partition scored.
That is what makes the per-level modularity sequence in `CommunityLevels` a monotone
sequence in one objective rather than three numbers from three different objectives.

Community ids are canonical, so two runs are comparable
-------------------------------------------------------
Labels are renumbered by first appearance in node order, so a partition has exactly one
representation and two labellings describe the same partition if and only if their
canonical forms are equal element by element. That is an exact test;
`clustering_metrics.adjusted_rand_index` is reported alongside it for the partial-
agreement case, but equality is decided without a float comparison.

Labels must lie in `[0, n_nodes)`. Any partition of `n` items is expressible that way,
so the restriction normalises rather than limits, and it buys an exact O(n)
canonicalisation with no hash and no Int-to-Float round trip that could silently merge
two large labels into one community.
"""
from std.math import isinf, isnan

from clustering_metrics import adjusted_rand_index, cluster_sizes
from determinism.sampling_keyed import permutation_keyed
from determinism.streams import stream_id
from graph_algorithms import modularity_contribution
from graph_analytics.adjacency import (
    GRAPH_ERR_EMPTY_GRAPH,
    GRAPH_ERR_INVALID_DIMENSIONS,
    GRAPH_ERR_LENGTH_MISMATCH,
    GRAPH_ERR_NEGATIVE_WEIGHT,
    GRAPH_ERR_NON_FINITE_WEIGHT,
    GRAPH_OK,
    graph_csr_from_triplets,
    graph_csr_validate_flat,
    graph_status_name,
)

# ── status codes ──────────────────────────────────────────────────────────────
# Numbered from 20 so the whole `graph_analytics` package shares one code space:
# `adjacency` owns 0-13, and a caller holding a code never has to know which module
# produced it. `community_status_name` delegates below 20.

comptime COMMUNITY_OK: Int = GRAPH_OK
comptime COMMUNITY_ERR_LABEL_LENGTH: Int = 20
comptime COMMUNITY_ERR_LABEL_RANGE: Int = 21
comptime COMMUNITY_ERR_INVALID_LIMITS: Int = 22
comptime COMMUNITY_ERR_NO_EDGE_WEIGHT: Int = 23
comptime COMMUNITY_ERR_PAIRWISE_TOO_LARGE: Int = 24
comptime COMMUNITY_ERR_TOO_MANY_NODES: Int = 25

# ── absence marker ────────────────────────────────────────────────────────────
# Q is in [-1, 1] for every partition of a non-negatively-weighted graph: `in_c >= 0`
# bounds it above by `sum_c in_c / 2m <= 1`, and below by `-sum_c (tot_c/2m)^2 >= -1`.
# So -2.0 cannot be an answer, which is the entire requirement for a marker.

comptime COMMUNITY_NO_MODULARITY: Float64 = -2.0

# A tolerance of exactly 0.0 admits a move whose gain differs from staying only in the
# last mantissa bits; the resulting `Q` increase is real but below measurement, and the
# extra passes buy nothing. 1e-12 is well above double rounding on a normalised
# modularity and well below any structure worth reporting.
comptime COMMUNITY_DEFAULT_TOLERANCE: Float64 = 1e-12

# Caps. `max_levels`/`max_passes` above these are clamped rather than rejected: a
# caller asking for 10^6 passes means "as many as it takes", and the clamp is the
# honest reading of that. Only a non-positive limit is an error, because it asks for no
# work at all while expecting an answer.
comptime COMMUNITY_LEVEL_LIMIT: Int = 64
comptime COMMUNITY_PASS_LIMIT: Int = 1024

# Draw-block stride, so (level, pass) blocks of `permutation_keyed` draws stay disjoint
# for any level with fewer than 2^20 nodes.
comptime COMMUNITY_DRAW_STRIDE: Int = 1048576

# The pairwise scorer walks every ordered node pair. Past this many pairs the caller
# wanted the O(V + E) scorer, and a silent quadratic scan is not a service.
comptime COMMUNITY_MAX_PAIR_CELLS: Int = 4194304

# `community_visit_order` allocates one Int per node before any graph exists, so it
# needs its own ceiling: an `n_nodes` arriving over the wire is untrusted.
comptime COMMUNITY_MAX_ORDER: Int = 1048576


def community_status_name(code: Int) -> String:
    """Name for a status code, including the `adjacency` codes this module can return.

    Delegating below 20 rather than re-listing keeps one name per code: a duplicated
    table drifts, and a caller comparing two spellings of `row_ptr_not_monotonic` has a
    bug that no test would catch.
    """
    if code == COMMUNITY_ERR_LABEL_LENGTH:
        return "label_length_not_n_nodes"
    if code == COMMUNITY_ERR_LABEL_RANGE:
        return "label_outside_zero_to_n_nodes"
    if code == COMMUNITY_ERR_INVALID_LIMITS:
        return "non_positive_iteration_limit"
    if code == COMMUNITY_ERR_NO_EDGE_WEIGHT:
        return "no_edge_weight_modularity_undefined"
    if code == COMMUNITY_ERR_PAIRWISE_TOO_LARGE:
        return "pairwise_scan_too_large"
    if code == COMMUNITY_ERR_TOO_MANY_NODES:
        return "node_count_above_ceiling"
    return graph_status_name(code)


def community_version() -> String:
    """The frozen objective and convention identifier. Deterministic, zero-argument.

    Changing the symmetrisation, the self-loop convention or the draw addressing
    changes which communities a seed produces, so it changes this string too.
    """
    return String("louvain/newman-girvan-Q/sym-sum/loop-doubled/philox4x64-10-order/v1")


def community_default_tolerance() -> Float64:
    """The tolerance `community_louvain_default_driver` applies. Zero-argument probe."""
    return COMMUNITY_DEFAULT_TOLERANCE


# ── return-only result structs ────────────────────────────────────────────────
# Declared in this file because the marshalling spec for a returned struct is parsed
# per file: returning `adjacency.GraphIntsResult` here would drop the function from the
# runtime contract with no error anywhere. `GraphCSR` is likewise absent from every
# public signature below — it is a parameter type owned by another module, and a
# parameter type is resolved from the same per-file table.


@fieldwise_init
struct CommunityCounts(Copyable, Movable):
    """A canonical labelling plus its community sizes.

    `label` is renumbered by first appearance so the representation is unique;
    `size[c]` is how many nodes carry canonical label `c`, from the frozen
    `clustering_metrics.cluster_sizes`. On any non-`ok` status both lists are empty and
    `n_communities` is 0 — a rejected labelling has no partial partition.
    """

    var status: Int
    var n_nodes: Int
    var n_communities: Int
    var label: List[Int]
    var size: List[Int]


@fieldwise_init
struct CommunityOrder(Copyable, Movable):
    """The node visit order a `(seed, level, pass)` triple produces.

    Returned so reproducibility is auditable rather than asserted: a caller can compare
    two seeds' orders and see that the seed is doing work, then compare two runs' labels
    and see that the result does not move.
    """

    var status: Int
    var n_nodes: Int
    var seed: Int
    var level: Int
    var pass_index: Int
    var values: List[Int]


@fieldwise_init
struct CommunityScore(Copyable, Movable):
    """Newman-Girvan modularity of one labelling, with the per-community terms.

    `internal_weight[c]` is `in_c` and `total_degree[c]` is `tot_c` in the symmetrised
    weight matrix, so a caller can re-derive `Q` from the parts and see *where* the
    score comes from. `total_weight` is `m = 2m/2`, the value passed to the frozen
    `modularity_contribution` as `total_edges`.

    `modularity` is `COMMUNITY_NO_MODULARITY` on every non-`ok` status, never 0.0: a
    modularity of 0.0 is the real answer for a graph with no community structure at all,
    so reusing it for "no answer" would erase exactly the distinction this scorer
    exists to report.

    `pairs_scanned` is how many ordered node pairs were actually visited —
    `n_nodes * n_nodes` for `community_modularity_pairwise_driver` and 0 for
    `community_modularity_driver`, which visits none because the null-model sum is
    collapsed algebraically. The two must still return the same number, and the field is
    what makes it visible that they got there by different routes.
    """

    var status: Int
    var n_nodes: Int
    var n_communities: Int
    var pairs_scanned: Int
    var total_weight: Float64
    var modularity: Float64
    var internal_weight: List[Float64]
    var total_degree: List[Float64]
    var size: List[Int]


@fieldwise_init
struct CommunityPartition(Copyable, Movable):
    """A detected partition, its score, and how it was reached.

    `converged` is the honesty field: False means a pass or round limit ran out while
    nodes were still moving, so the labelling is a real partition but not a local
    optimum. The partition is still returned, because it is an answer — unlike a
    rejected input, where `label` is empty and `modularity` is
    `COMMUNITY_NO_MODULARITY`.

    `n_levels` counts the aggregation levels that improved the score. Zero means the
    first local-moving pass could not beat the all-singletons partition, which is the
    correct report for a graph with no community structure — a complete graph, for
    instance, where the answer is one community and `Q = 0`.
    """

    var status: Int
    var n_nodes: Int
    var n_communities: Int
    var n_levels: Int
    var n_passes: Int
    var moves: Int
    var converged: Bool
    var total_weight: Float64
    var modularity: Float64
    var label: List[Int]
    var size: List[Int]


@fieldwise_init
struct CommunityLevels(Copyable, Movable):
    """The whole Louvain ladder, so monotonicity is data rather than a promise.

    `level_modularity[0]` is the all-singletons score of the input graph and each
    later entry is the score after that level's local moving. Aggregation preserves `Q`
    exactly, so every entry measures the same objective on the same graph and the
    sequence is comparable end to end. `monotone` is the in-module check; the numbers
    are exposed so a test can redo it instead of trusting a Bool.

    `n_levels` counts only the levels that improved the score, so it is
    `len(level_modularity) - 1`. `n_passes` and `moves` total the local-moving work
    across every level attempted, including the final level that found nothing — which
    is why they can be non-zero while `n_levels` is 0.
    """

    var status: Int
    var n_nodes: Int
    var n_levels: Int
    var n_communities: Int
    var n_passes: Int
    var moves: Int
    var monotone: Bool
    var converged: Bool
    var total_weight: Float64
    var modularity: Float64
    var level_modularity: List[Float64]
    var level_communities: List[Int]
    var label: List[Int]


@fieldwise_init
struct CommunityAggregate(Copyable, Movable):
    """A symmetrised or community-aggregated graph, as CSR arrays ready to feed back in.

    The diagonal is stored as a real `(a, a, in_a)` edge, so these three arrays plus
    `n_nodes` are a valid `adjacency` CSR and can be handed straight to
    `community_modularity_driver` or `community_louvain_driver` for the next level.
    `total_weight` is `m`, which aggregation leaves unchanged — that invariance is what
    makes the level scores comparable, and the suite checks it.
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var total_weight: Float64
    var row_ptr: List[Int]
    var targets: List[Int]
    var weights: List[Float64]


@fieldwise_init
struct CommunityCompare(Copyable, Movable):
    """Whether two labellings are the same partition, and how far apart if not.

    `same_partition` is exact: both labellings are canonicalised by first appearance,
    which gives a partition exactly one representation, so equality is decided element
    by element with no float comparison. `adjusted_rand_index` comes from the frozen
    `clustering_metrics.adjusted_rand_index` and is the graded measure for the
    disagreeing case.

    `canonical_mismatches` counts nodes whose canonical label differs. It is 0 exactly
    when the partitions match; between 1 and `n_nodes` it is a coarse divergence
    signal, not a count of misplaced nodes, because canonical renumbering is by node
    order and one moved node can shift every label after it.
    """

    var status: Int
    var n_nodes: Int
    var same_partition: Bool
    var n_communities_a: Int
    var n_communities_b: Int
    var canonical_mismatches: Int
    var adjusted_rand_index: Float64


# ── internal working structures ───────────────────────────────────────────────


@fieldwise_init
struct _Level(Copyable, Movable):
    """One Louvain level: the symmetrised weight matrix in CSR form, plus its degrees.

    `weights` holds `W_uv` with the diagonal present as an explicit `(u, u)` entry, and
    `degree[u]` is `k_u = sum_v W_uv`, so `two_m == sum_u degree[u]` by construction
    rather than by a second convention that could disagree.
    """

    var status: Int
    var n: Int
    var row_ptr: List[Int]
    var targets: List[Int]
    var weights: List[Float64]
    var degree: List[Float64]
    var two_m: Float64


@fieldwise_init
struct _Canon(Copyable, Movable):
    var status: Int
    var k: Int
    var label: List[Int]


@fieldwise_init
struct _Terms(Copyable, Movable):
    var modularity: Float64
    var internal: List[Float64]
    var total: List[Float64]


@fieldwise_init
struct _Moving(Copyable, Movable):
    var comm: List[Int]
    var k: Int
    var moves: Int
    var passes: Int
    var converged: Bool


def _empty_level(status: Int) -> _Level:
    return _Level(
        status, 0, List[Int](), List[Int](), List[Float64](), List[Float64](), 0.0
    )


def _seed_key(seed: Int) -> UInt64:
    """Fold an arbitrary `Int` seed onto a non-negative key.

    Masking rather than negating: `-Int.MIN` overflows, and a seed is a name for a
    stream of draws, not a magnitude, so losing the sign bit costs nothing a caller
    could observe.
    """
    return UInt64(seed & 0x7FFFFFFFFFFFFFFF)


def _louvain_stream() -> UInt64:
    """Named draw stream for the local-moving visit order."""
    return stream_id("graph_analytics.community.louvain")


def _propagation_stream() -> UInt64:
    """Named draw stream for label propagation, distinct from Louvain's.

    Two independent streams so a caller running both with one seed does not get the
    same visit order in both, which would make an agreement between them evidence of
    shared randomness rather than of shared structure.
    """
    return stream_id("graph_analytics.community.label_propagation")


def _draw_base(level: Int, pass_index: Int) -> UInt64:
    """First draw coordinate for one `(level, pass)` block."""
    var block = level * COMMUNITY_PASS_LIMIT + pass_index
    return UInt64(block) * UInt64(COMMUNITY_DRAW_STRIDE)


def _weight_defect(weights: List[Float64]) -> Int:
    """`GRAPH_OK`, or the code for the first weight modularity cannot be defined on.

    NaN first: `nan < 0.0` is False, so a sign test alone admits NaN, and a NaN weight
    then makes `two_m` NaN and every gain comparison False — the greedy loop would run
    to its pass cap and report a singleton partition as if that were the answer.
    """
    for k in range(len(weights)):
        var w = weights[k]
        if isnan(w) or isinf(w):
            return GRAPH_ERR_NON_FINITE_WEIGHT
        if w < 0.0:
            return GRAPH_ERR_NEGATIVE_WEIGHT
    return GRAPH_OK


def _level_from_undirected(
    src: List[Int], dst: List[Int], weight: List[Float64], n: Int
) -> _Level:
    """Group already-symmetric triplets into a `_Level`, summing parallel entries.

    `adjacency.graph_csr_from_triplets` does the grouping in O(V + E) by the
    counting-sort transpose, which also leaves every row ascending by target — so the
    duplicate run-merge below is a single linear scan and needs no sort of its own.
    Summing, not minimising: see the module docstring.
    """
    var g = graph_csr_from_triplets(src, dst, weight, n)
    if g.skipped_edges != 0:
        # Every endpoint was range-checked by the caller, so a skip here means the two
        # range checks disagree. Refuse rather than score a graph missing edges.
        return _empty_level(GRAPH_ERR_INVALID_DIMENSIONS)

    var row_ptr = List[Int]()
    var targets = List[Int]()
    var weights = List[Float64]()
    row_ptr.append(0)
    for u in range(n):
        var begin = g.row_ptr[u]
        var end = g.row_ptr[u + 1]
        var p = begin
        while p < end:
            var v = g.targets[p]
            var total = g.weights[p]
            var q = p + 1
            while q < end and g.targets[q] == v:
                total += g.weights[q]
                q += 1
            targets.append(v)
            weights.append(total)
            p = q
        row_ptr.append(len(targets))

    var degree = List[Float64]()
    var two_m: Float64 = 0.0
    for u in range(n):
        var acc: Float64 = 0.0
        for p in range(row_ptr[u], row_ptr[u + 1]):
            acc += weights[p]
        degree.append(acc)
        two_m += acc
    if two_m <= 0.0:
        return _empty_level(COMMUNITY_ERR_NO_EDGE_WEIGHT)
    return _Level(GRAPH_OK, n, row_ptr^, targets^, weights^, degree^, two_m)


def _level_from_flat(
    row_ptr: List[Int], targets: List[Int], weights: List[Float64], n_nodes: Int
) -> _Level:
    """Validate four caller-supplied CSR arrays, then symmetrise them into a `_Level`.

    Validation comes first and unconditionally, because a `row_ptr` entry beyond
    `len(targets)` turns the symmetrisation loop into a read past the end — an
    uncatchable process crash, not an exception.
    """
    var status = graph_csr_validate_flat(row_ptr, targets, weights, n_nodes)
    if status != GRAPH_OK:
        return _empty_level(status)
    if n_nodes == 0:
        return _empty_level(GRAPH_ERR_EMPTY_GRAPH)
    var defect = _weight_defect(weights)
    if defect != GRAPH_OK:
        return _empty_level(defect)

    var src = List[Int]()
    var dst = List[Int]()
    var weight = List[Float64]()
    for u in range(n_nodes):
        for p in range(row_ptr[u], row_ptr[u + 1]):
            var v = targets[p]
            var w = weights[p]
            src.append(u)
            dst.append(v)
            weight.append(w)
            src.append(v)
            dst.append(u)
            weight.append(w)
    return _level_from_undirected(src, dst, weight, n_nodes)


def _canonicalize(label: List[Int], n: Int) -> _Canon:
    """Renumber `label` by first appearance in node order. One partition, one form.

    Requires `len(label) == n` and every entry in `[0, n)`; both are checked before any
    subscript, because `slot[label[i]]` on an out-of-range label is the crash this
    whole file is guarding against.
    """
    if len(label) != n:
        return _Canon(COMMUNITY_ERR_LABEL_LENGTH, 0, List[Int]())
    for i in range(n):
        if label[i] < 0 or label[i] >= n:
            return _Canon(COMMUNITY_ERR_LABEL_RANGE, 0, List[Int]())
    var slot = List[Int]()
    for _ in range(n):
        slot.append(-1)
    var out = List[Int]()
    var k = 0
    for i in range(n):
        var v = label[i]
        if slot[v] < 0:
            slot[v] = k
            k += 1
        out.append(slot[v])
    return _Canon(GRAPH_OK, k, out^)


def _identity(n: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(n):
        out.append(i)
    return out^


def _level_terms(level: _Level, comm: List[Int], k: Int) -> _Terms:
    """`Q`, `in_c` and `tot_c` for a canonical labelling. O(V + E).

    `Q = (1/2m) * sum_c modularity_contribution(in_c, tot_c, tot_c, m)` — the frozen
    per-pair kernel applied per community, which is the exact algebraic collapse of the
    per-pair sum and not an approximation of it. `community_modularity_pairwise_driver`
    evaluates the uncollapsed form so the two can be compared.

    Caller guarantees `len(comm) == level.n` and every entry in `[0, k)`.
    """
    var internal = List[Float64]()
    var total = List[Float64]()
    for _ in range(k):
        internal.append(0.0)
        total.append(0.0)
    for u in range(level.n):
        var cu = comm[u]
        total[cu] += level.degree[u]
        for p in range(level.row_ptr[u], level.row_ptr[u + 1]):
            if comm[level.targets[p]] == cu:
                internal[cu] += level.weights[p]
    var m = level.two_m * 0.5
    var acc: Float64 = 0.0
    for c in range(k):
        acc += modularity_contribution(internal[c], total[c], total[c], m)
    return _Terms(acc / level.two_m, internal^, total^)


def _local_moving(
    level: _Level, seed: Int, level_index: Int, max_passes: Int, tolerance: Float64
) -> _Moving:
    """Louvain's phase one: greedy single-node moves until no move improves `Q`.

    The gain of moving `i` into community `c` is
    `modularity_contribution(k_i_to_c, k_i, tot_c, m)` with `tot_c` measured without
    `i`, and the realised change in `Q` is `(gain_c - gain_stay) / m`. Both sides share
    the isolated-`i` baseline, so the difference is exact and a move is accepted only
    when it exceeds `tolerance`.

    `tot` is recomputed from `comm` at the end of every pass. The incremental
    `tot[from] -= k_i; tot[to] += k_i` is exact in real arithmetic and not in floating
    point, and the drift accumulates over passes into the denominator of every
    subsequent gain — an O(V) refresh per pass costs nothing against the O(E) scan and
    removes the whole question.
    """
    var n = level.n
    var comm = _identity(n)
    var tot = List[Float64]()
    var w_to = List[Float64]()
    var seen = List[Bool]()
    var touched = List[Int]()
    for u in range(n):
        tot.append(level.degree[u])
        w_to.append(0.0)
        seen.append(False)
        touched.append(0)

    var m = level.two_m * 0.5
    var key = _seed_key(seed)
    var stream = _louvain_stream()
    var moves_total = 0
    var passes = 0
    var converged = False

    for pass_index in range(max_passes):
        passes = pass_index + 1
        var order = permutation_keyed(
            n, key, stream, _draw_base(level_index, pass_index)
        )
        var moves = 0
        for slot in range(n):
            var i = order[slot]
            var ci = comm[i]
            var ki = level.degree[i]
            var n_touched = 0
            for p in range(level.row_ptr[i], level.row_ptr[i + 1]):
                var j = level.targets[p]
                # A self-loop attaches `i` to no community but itself, so it belongs to
                # neither side of the gain and is skipped here; it is still in `k_i`,
                # which is where the convention says it belongs.
                if j == i:
                    continue
                var c = comm[j]
                if not seen[c]:
                    seen[c] = True
                    w_to[c] = 0.0
                    touched[n_touched] = c
                    n_touched += 1
                w_to[c] += level.weights[p]

            var w_own: Float64 = 0.0
            if seen[ci]:
                w_own = w_to[ci]
            var stay = modularity_contribution(w_own, ki, tot[ci] - ki, m)

            var best_c = -1
            var best_gain: Float64 = 0.0
            for t in range(n_touched):
                var c = touched[t]
                if c == ci:
                    continue
                var gain = modularity_contribution(w_to[c], ki, tot[c], m)
                # Exact `>` and `==`: highest gain, then smallest community id. A
                # tolerance band here is not a transitive order and would make the
                # winner depend on scan order in a way nothing records.
                if best_c < 0 or gain > best_gain or (
                    gain == best_gain and c < best_c
                ):
                    best_gain = gain
                    best_c = c

            if best_c >= 0 and best_gain > stay + tolerance:
                tot[ci] -= ki
                tot[best_c] += ki
                comm[i] = best_c
                moves += 1

            for t in range(n_touched):
                seen[touched[t]] = False

        moves_total += moves
        for c in range(n):
            tot[c] = 0.0
        for v in range(n):
            tot[comm[v]] += level.degree[v]
        if moves == 0:
            converged = True
            break

    var canon = _canonicalize(comm, n)
    return _Moving(canon.label.copy(), canon.k, moves_total, passes, converged)


def _aggregate_level(level: _Level, comm: List[Int], k: Int) -> _Level:
    """The community graph: one node per community, `W'_ab = sum_{i in a, j in b} W_ij`.

    `k'_a = sum_b W'_ab = sum_{i in a} k_i = tot_a` and `2m' = 2m`, so the singleton
    partition of this graph scores exactly what `comm` scored on `level`. That identity
    is why the per-level modularity sequence is monotone in one objective; if this
    function summed anything else the ladder would be three numbers from three
    different objectives.

    Caller guarantees `len(comm) == level.n` and every entry in `[0, k)`.
    """
    var src = List[Int]()
    var dst = List[Int]()
    var weight = List[Float64]()
    for u in range(level.n):
        var cu = comm[u]
        for p in range(level.row_ptr[u], level.row_ptr[u + 1]):
            src.append(cu)
            dst.append(comm[level.targets[p]])
            weight.append(level.weights[p])
    return _level_from_undirected(src, dst, weight, k)


# ── labelling utilities ───────────────────────────────────────────────────────


def community_canonical_labels(label: List[Int]) -> CommunityCounts:
    """Renumber a labelling by first appearance and count its communities.

    The canonical form is what makes two partitions comparable without a float
    measure. Labels must lie in `[0, len(label))`; see the module docstring for why
    that normalises rather than limits.
    """
    var n = len(label)
    var canon = _canonicalize(label, n)
    if canon.status != GRAPH_OK:
        return CommunityCounts(canon.status, n, 0, List[Int](), List[Int]())
    var sizes = cluster_sizes(canon.label, canon.k)
    return CommunityCounts(GRAPH_OK, n, canon.k, canon.label.copy(), sizes^)


def community_compare_labels(
    label_a: List[Int], label_b: List[Int]
) -> CommunityCompare:
    """Do two labellings describe the same partition, exactly, and how close if not.

    Equality is decided on canonical forms element by element — no tolerance, no float.
    `adjusted_rand_index` is the frozen graded measure, reported alongside rather than
    instead: ARI is 1.0 for identical partitions, but a float compared against 1.0 is a
    weaker test than an integer array compared against another.
    """
    var n = len(label_a)
    if len(label_b) != n:
        return CommunityCompare(
            COMMUNITY_ERR_LABEL_LENGTH, n, False, 0, 0, 0, COMMUNITY_NO_MODULARITY
        )
    var ca = _canonicalize(label_a, n)
    if ca.status != GRAPH_OK:
        return CommunityCompare(
            ca.status, n, False, 0, 0, 0, COMMUNITY_NO_MODULARITY
        )
    var cb = _canonicalize(label_b, n)
    if cb.status != GRAPH_OK:
        return CommunityCompare(
            cb.status, n, False, 0, 0, 0, COMMUNITY_NO_MODULARITY
        )
    var mismatches = 0
    for i in range(n):
        if ca.label[i] != cb.label[i]:
            mismatches += 1
    var ari = adjusted_rand_index(ca.label, cb.label)
    return CommunityCompare(
        GRAPH_OK, n, mismatches == 0, ca.k, cb.k, mismatches, ari
    )


def community_visit_order(
    n_nodes: Int, seed: Int, level: Int, pass_index: Int
) -> CommunityOrder:
    """The exact node order local moving will use for `(seed, level, pass_index)`.

    Exposed so reproducibility is auditable: a caller can check that two seeds really
    do produce different orders before concluding that two identical label arrays mean
    anything.
    """
    if n_nodes < 0 or level < 0 or pass_index < 0:
        return CommunityOrder(
            GRAPH_ERR_INVALID_DIMENSIONS, n_nodes, seed, level, pass_index, List[Int]()
        )
    if n_nodes > COMMUNITY_MAX_ORDER:
        return CommunityOrder(
            COMMUNITY_ERR_TOO_MANY_NODES, n_nodes, seed, level, pass_index, List[Int]()
        )
    if level >= COMMUNITY_LEVEL_LIMIT or pass_index >= COMMUNITY_PASS_LIMIT:
        return CommunityOrder(
            COMMUNITY_ERR_INVALID_LIMITS, n_nodes, seed, level, pass_index, List[Int]()
        )
    var order = permutation_keyed(
        n_nodes, _seed_key(seed), _louvain_stream(), _draw_base(level, pass_index)
    )
    return CommunityOrder(GRAPH_OK, n_nodes, seed, level, pass_index, order^)


def community_modularity_gain(
    weight_to_community: Float64,
    node_degree: Float64,
    community_degree: Float64,
    total_weight: Float64,
) -> Float64:
    """Change in `Q` from moving one isolated node into a community.

    `(1/m) * modularity_contribution(weight_to_community, node_degree,
    community_degree, m)` — the frozen kernel divided by `m`. Exposed because it is the
    single decision the whole local-moving phase makes, and a caller auditing a
    partition should be able to re-price any move without reimplementing the
    derivation.

    `community_degree` must exclude the moving node. `total_weight <= 0` has no gain to
    report and returns `COMMUNITY_NO_MODULARITY`, not 0.0 — 0.0 is the real gain of a
    move that changes nothing.
    """
    if total_weight <= 0.0 or isnan(total_weight):
        return COMMUNITY_NO_MODULARITY
    return (
        modularity_contribution(
            weight_to_community, node_degree, community_degree, total_weight
        )
        / total_weight
    )


# ── modularity scorers ────────────────────────────────────────────────────────


def _no_score(status: Int, n_nodes: Int) -> CommunityScore:
    return CommunityScore(
        status,
        n_nodes,
        0,
        0,
        0.0,
        COMMUNITY_NO_MODULARITY,
        List[Float64](),
        List[Float64](),
        List[Int](),
    )


def community_modularity_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    label: List[Int],
) -> CommunityScore:
    """Newman-Girvan modularity of `label` on the CSR, in O(V + E).

    Works on any labelling, not just one this module produced — that is the point of a
    separate scorer: a caller with communities from a domain model, a k-means run or a
    hand-drawn map can ask how much structure they capture, and compare against
    `community_louvain_driver` on the same graph.
    """
    var level = _level_from_flat(row_ptr, targets, weights, n_nodes)
    if level.status != GRAPH_OK:
        return _no_score(level.status, n_nodes)
    var canon = _canonicalize(label, level.n)
    if canon.status != GRAPH_OK:
        return _no_score(canon.status, level.n)
    var terms = _level_terms(level, canon.label, canon.k)
    var sizes = cluster_sizes(canon.label, canon.k)
    return CommunityScore(
        GRAPH_OK,
        level.n,
        canon.k,
        0,
        level.two_m * 0.5,
        terms.modularity,
        terms.internal.copy(),
        terms.total.copy(),
        sizes^,
    )


def community_modularity_pairwise_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    label: List[Int],
) -> CommunityScore:
    """The same modularity, summed literally over every same-community ordered pair.

    `Q = (1/2m) * sum_{i,j : c_i = c_j} modularity_contribution(W_ij, k_i, k_j, m)`,
    with no algebraic collapse — including the `W_ij = 0` pairs, which is where the
    null-model term lives and where the collapsed form does its work. This exists to
    make `community_modularity_driver` checkable against the frozen kernel at pair
    granularity rather than community granularity; the two must agree to rounding, and
    the suite asserts it against a hand-computed value.

    Refused above `COMMUNITY_MAX_PAIR_CELLS` pairs, reported as a status rather than
    quietly spending O(V^2): a caller that wanted this on a million nodes wanted the
    other driver.
    """
    var level = _level_from_flat(row_ptr, targets, weights, n_nodes)
    if level.status != GRAPH_OK:
        return _no_score(level.status, n_nodes)
    var n = level.n
    if n > COMMUNITY_MAX_PAIR_CELLS // n:
        return _no_score(COMMUNITY_ERR_PAIRWISE_TOO_LARGE, n)
    var canon = _canonicalize(label, n)
    if canon.status != GRAPH_OK:
        return _no_score(canon.status, n)

    var m = level.two_m * 0.5
    var row = List[Float64]()
    for _ in range(n):
        row.append(0.0)
    var acc: Float64 = 0.0
    for i in range(n):
        for p in range(level.row_ptr[i], level.row_ptr[i + 1]):
            row[level.targets[p]] = level.weights[p]
        var ci = canon.label[i]
        for j in range(n):
            if canon.label[j] == ci:
                acc += modularity_contribution(row[j], level.degree[i], level.degree[j], m)
        for p in range(level.row_ptr[i], level.row_ptr[i + 1]):
            row[level.targets[p]] = 0.0

    var internal = List[Float64]()
    var total = List[Float64]()
    for _ in range(canon.k):
        internal.append(0.0)
        total.append(0.0)
    for i in range(n):
        var c = canon.label[i]
        total[c] += level.degree[i]
        for p in range(level.row_ptr[i], level.row_ptr[i + 1]):
            if canon.label[level.targets[p]] == c:
                internal[c] += level.weights[p]
    var sizes = cluster_sizes(canon.label, canon.k)
    return CommunityScore(
        GRAPH_OK,
        n,
        canon.k,
        n * n,
        m,
        acc / level.two_m,
        internal^,
        total^,
        sizes^,
    )


def community_modularity_from_triplets(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    n_nodes: Int,
    label: List[Int],
) -> CommunityScore:
    """Modularity straight from an edge list, no CSR assembled by the caller.

    Out-of-range endpoints are skipped by `adjacency.graph_csr_from_triplets` and never
    indexed, so a stray edge costs that edge rather than the worker process. A caller
    that needs to know how many were dropped should build with
    `adjacency.graph_csr_build` first and read `skipped_edges`.
    """
    if n_nodes < 0:
        return _no_score(GRAPH_ERR_INVALID_DIMENSIONS, 0)
    if len(dst) != len(src) or len(weight) != len(src):
        return _no_score(GRAPH_ERR_LENGTH_MISMATCH, n_nodes)
    var defect = _weight_defect(weight)
    if defect != GRAPH_OK:
        return _no_score(defect, n_nodes)
    var g = graph_csr_from_triplets(src, dst, weight, n_nodes)
    return community_modularity_driver(
        g.row_ptr, g.targets, g.weights, g.n_nodes, label
    )


# ── aggregation ───────────────────────────────────────────────────────────────


def _no_aggregate(status: Int) -> CommunityAggregate:
    return CommunityAggregate(
        status, 0, 0, 0.0, List[Int](), List[Int](), List[Float64]()
    )


def _aggregate_out(level: _Level) -> CommunityAggregate:
    if level.status != GRAPH_OK:
        return _no_aggregate(level.status)
    return CommunityAggregate(
        GRAPH_OK,
        level.n,
        len(level.targets),
        level.two_m * 0.5,
        level.row_ptr.copy(),
        level.targets.copy(),
        level.weights.copy(),
    )


def community_symmetrized_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> CommunityAggregate:
    """The symmetrised weight matrix `W_ij = D_ij + D_ji` this module scores on.

    Exposed because the symmetrisation is the one convention a caller cannot infer from
    a modularity number, and a surprising `Q` is almost always a surprising `W`.
    """
    return _aggregate_out(_level_from_flat(row_ptr, targets, weights, n_nodes))


def community_aggregate_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    label: List[Int],
) -> CommunityAggregate:
    """Louvain's phase two: collapse each community to a node, weights preserved.

    The returned arrays are a valid CSR whose singleton partition has exactly the
    modularity `label` had on the input, so the next level continues the same
    optimisation instead of starting a new one. Feed them back through
    `community_modularity_driver` to check that, which is what the suite does.
    """
    var level = _level_from_flat(row_ptr, targets, weights, n_nodes)
    if level.status != GRAPH_OK:
        return _no_aggregate(level.status)
    var canon = _canonicalize(label, level.n)
    if canon.status != GRAPH_OK:
        return _no_aggregate(canon.status)
    return _aggregate_out(_aggregate_level(level, canon.label, canon.k))


# ── Louvain ───────────────────────────────────────────────────────────────────


def _no_partition(status: Int, n_nodes: Int) -> CommunityPartition:
    return CommunityPartition(
        status,
        n_nodes,
        0,
        0,
        0,
        0,
        False,
        0.0,
        COMMUNITY_NO_MODULARITY,
        List[Int](),
        List[Int](),
    )


def _no_levels(status: Int, n_nodes: Int) -> CommunityLevels:
    return CommunityLevels(
        status,
        n_nodes,
        0,
        0,
        0,
        0,
        False,
        False,
        0.0,
        COMMUNITY_NO_MODULARITY,
        List[Float64](),
        List[Int](),
        List[Int](),
    )


def _clamped_tolerance(tolerance: Float64) -> Float64:
    """`tolerance` clamped to non-negative.

    A negative tolerance would admit moves that *lower* `Q`, which breaks the one
    guarantee the whole ladder rests on. Clamping rather than rejecting because 0.0 is
    the honest reading of "accept any improvement", and NaN is clamped for the same
    reason `_weight_defect` checks NaN first: `nan > x` is False, so a NaN tolerance
    silently accepts every move.
    """
    if isnan(tolerance) or tolerance < 0.0:
        return 0.0
    return tolerance


def _louvain_levels(
    level0: _Level, seed: Int, max_levels: Int, max_passes: Int, tolerance: Float64
) -> CommunityLevels:
    """The full ladder. Returns the original-node labelling and the per-level scores."""
    var n0 = level0.n
    var node_label = _identity(n0)
    var level_q = List[Float64]()
    var level_k = List[Int]()

    # The all-singletons score of the input graph is the baseline every later entry is
    # measured against, so it belongs in the sequence rather than in a separate field.
    var base = _level_terms(level0, node_label, n0)
    level_q.append(base.modularity)
    level_k.append(n0)

    var lvl = level0.copy()
    var n_levels = 0
    var passes = 0
    var moves = 0
    var converged = True

    for level_index in range(max_levels):
        var lm = _local_moving(lvl, seed, level_index, max_passes, tolerance)
        moves += lm.moves
        passes += lm.passes
        if not lm.converged:
            converged = False
        # Every community holds exactly one node, so this level found nothing to merge
        # and aggregating would only relabel. Stop before spending a level on it.
        if lm.k == lvl.n:
            break
        var q = _level_terms(lvl, lm.comm, lm.k).modularity
        if q <= level_q[len(level_q) - 1] + tolerance:
            break
        for v in range(n0):
            node_label[v] = lm.comm[node_label[v]]
        level_q.append(q)
        level_k.append(lm.k)
        n_levels += 1
        var nxt = _aggregate_level(lvl, lm.comm, lm.k)
        if nxt.status != GRAPH_OK:
            break
        lvl = nxt.copy()

    # Composing canonical maps happens to stay canonical, but asserting that in a
    # comment is not the same as guaranteeing it — renumber once at the end.
    var canon = _canonicalize(node_label, n0)
    if canon.status != GRAPH_OK:
        return _no_levels(canon.status, n0)
    var final_q = level_q[len(level_q) - 1]
    var monotone = True
    for i in range(1, len(level_q)):
        if level_q[i] < level_q[i - 1]:
            monotone = False
    return CommunityLevels(
        GRAPH_OK,
        n0,
        n_levels,
        canon.k,
        passes,
        moves,
        monotone,
        converged,
        level0.two_m * 0.5,
        final_q,
        level_q^,
        level_k^,
        canon.label.copy(),
    )


def community_louvain_levels_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    seed: Int,
    max_levels: Int,
    max_passes: Int,
    tolerance: Float64,
) -> CommunityLevels:
    """Louvain with the whole ladder returned, so monotonicity can be checked.

    `level_modularity[0]` is the all-singletons score and each later entry is the score
    after that level. The sequence is non-decreasing by construction — a move needs
    `gain > stay + tolerance` and aggregation preserves `Q` — and it is returned rather
    than asserted so a caller (and the suite) can verify it on real data.
    """
    if max_levels <= 0 or max_passes <= 0:
        return _no_levels(COMMUNITY_ERR_INVALID_LIMITS, n_nodes)
    var levels = max_levels
    if levels > COMMUNITY_LEVEL_LIMIT:
        levels = COMMUNITY_LEVEL_LIMIT
    var passes = max_passes
    if passes > COMMUNITY_PASS_LIMIT:
        passes = COMMUNITY_PASS_LIMIT
    var level0 = _level_from_flat(row_ptr, targets, weights, n_nodes)
    if level0.status != GRAPH_OK:
        return _no_levels(level0.status, n_nodes)
    return _louvain_levels(
        level0, seed, levels, passes, _clamped_tolerance(tolerance)
    )


def _partition_from_levels(result: CommunityLevels) -> CommunityPartition:
    if result.status != GRAPH_OK:
        return _no_partition(result.status, result.n_nodes)
    var sizes = cluster_sizes(result.label, result.n_communities)
    return CommunityPartition(
        GRAPH_OK,
        result.n_nodes,
        result.n_communities,
        result.n_levels,
        result.n_passes,
        result.moves,
        result.converged,
        result.total_weight,
        result.modularity,
        result.label.copy(),
        sizes^,
    )


def community_louvain_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    seed: Int,
    max_levels: Int,
    max_passes: Int,
    tolerance: Float64,
) -> CommunityPartition:
    """Multi-level Louvain over a CSR. Same seed, same communities, every time.

    Returns the partition on the *original* nodes, its modularity, and how many
    aggregation levels improved the score. `n_communities == n_nodes` with
    `n_levels == 0` is the honest report for a graph with no community structure worth
    naming; `n_communities == 1` with `modularity == 0.0` is the honest report for a
    complete graph, where every partition scores at most 0 and inventing groups would
    be a wrong answer rather than a coarse one.
    """
    return _partition_from_levels(
        community_louvain_levels_driver(
            row_ptr, targets, weights, n_nodes, seed, max_levels, max_passes, tolerance
        )
    )


def community_louvain_default_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    seed: Int,
) -> CommunityPartition:
    """Louvain with the caps and tolerance this module recommends.

    A caller should not have to pick `max_levels` and a tolerance to get a partition,
    and a caller that picks them badly (a tolerance of 0.5, say) gets singletons with
    no indication why. The defaults are `COMMUNITY_LEVEL_LIMIT`,
    `COMMUNITY_PASS_LIMIT` and `COMMUNITY_DEFAULT_TOLERANCE`.
    """
    return community_louvain_driver(
        row_ptr,
        targets,
        weights,
        n_nodes,
        seed,
        COMMUNITY_LEVEL_LIMIT,
        COMMUNITY_PASS_LIMIT,
        COMMUNITY_DEFAULT_TOLERANCE,
    )


def community_louvain_from_triplets(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    n_nodes: Int,
    seed: Int,
    max_levels: Int,
    max_passes: Int,
    tolerance: Float64,
) -> CommunityPartition:
    """Louvain straight from an edge list. Out-of-range endpoints are skipped, not indexed."""
    if n_nodes < 0:
        return _no_partition(GRAPH_ERR_INVALID_DIMENSIONS, 0)
    if len(dst) != len(src) or len(weight) != len(src):
        return _no_partition(GRAPH_ERR_LENGTH_MISMATCH, n_nodes)
    var defect = _weight_defect(weight)
    if defect != GRAPH_OK:
        return _no_partition(defect, n_nodes)
    var g = graph_csr_from_triplets(src, dst, weight, n_nodes)
    return community_louvain_driver(
        g.row_ptr,
        g.targets,
        g.weights,
        g.n_nodes,
        seed,
        max_levels,
        max_passes,
        tolerance,
    )


def community_local_moving_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    seed: Int,
    max_passes: Int,
    tolerance: Float64,
) -> CommunityPartition:
    """Louvain's first phase alone — one level, no aggregation.

    Separate from `community_louvain_driver` because the two answer different
    questions: this one finds the finest partition greedy single-node moves can reach,
    which is the resolution a caller wants when the aggregation levels would merge
    groups it considers distinct. `n_levels` is always 0 here, and `converged` says
    whether the pass cap ran out mid-move.
    """
    if max_passes <= 0:
        return _no_partition(COMMUNITY_ERR_INVALID_LIMITS, n_nodes)
    var passes = max_passes
    if passes > COMMUNITY_PASS_LIMIT:
        passes = COMMUNITY_PASS_LIMIT
    var level = _level_from_flat(row_ptr, targets, weights, n_nodes)
    if level.status != GRAPH_OK:
        return _no_partition(level.status, n_nodes)
    var tol = _clamped_tolerance(tolerance)
    var lm = _local_moving(level, seed, 0, passes, tol)
    var terms = _level_terms(level, lm.comm, lm.k)
    var sizes = cluster_sizes(lm.comm, lm.k)
    return CommunityPartition(
        GRAPH_OK,
        level.n,
        lm.k,
        0,
        lm.passes,
        lm.moves,
        lm.converged,
        level.two_m * 0.5,
        terms.modularity,
        lm.comm.copy(),
        sizes^,
    )


# ── label propagation ─────────────────────────────────────────────────────────


def _label_propagation(level: _Level, seed: Int, max_rounds: Int) -> _Moving:
    """Weighted asynchronous label propagation with a seeded visit order.

    Each node takes the label carrying the most incident weight among its neighbours;
    ties go to the smallest label id, compared exactly. Updates are asynchronous — a
    node sees the labels its predecessors in this round already chose — which is what
    keeps a bipartite graph from oscillating between two states forever. Order comes
    from the same `permutation_keyed` machinery as Louvain but on its own named stream.

    Label propagation has no objective it monotonically improves, so it can fail to
    settle; `converged` is False in that case and the labelling is still returned,
    because a labelling is an answer even when it is not a fixed point. That is exactly
    what the frozen `social_network.community_label_propagation` cannot tell a caller.
    """
    var n = level.n
    var labels = _identity(n)
    var w_lab = List[Float64]()
    var seen = List[Bool]()
    var touched = List[Int]()
    for _ in range(n):
        w_lab.append(0.0)
        seen.append(False)
        touched.append(0)

    var key = _seed_key(seed)
    var stream = _propagation_stream()
    var changes_total = 0
    var rounds = 0
    var converged = False

    for round_index in range(max_rounds):
        rounds = round_index + 1
        var order = permutation_keyed(n, key, stream, _draw_base(0, round_index))
        var changes = 0
        for slot in range(n):
            var i = order[slot]
            var n_touched = 0
            for p in range(level.row_ptr[i], level.row_ptr[i + 1]):
                var j = level.targets[p]
                # A self-loop would vote for the node's own current label and pin it in
                # place, which is not a neighbour's opinion.
                if j == i:
                    continue
                var l = labels[j]
                if not seen[l]:
                    seen[l] = True
                    w_lab[l] = 0.0
                    touched[n_touched] = l
                    n_touched += 1
                w_lab[l] += level.weights[p]

            var best_l = -1
            var best_w: Float64 = 0.0
            for t in range(n_touched):
                var l = touched[t]
                var w = w_lab[l]
                if best_l < 0 or w > best_w or (w == best_w and l < best_l):
                    best_w = w
                    best_l = l
            # No neighbours at all: an isolated node is its own community, which is the
            # correct answer and not a missing one.
            if best_l >= 0 and best_l != labels[i]:
                labels[i] = best_l
                changes += 1

            for t in range(n_touched):
                seen[touched[t]] = False

        changes_total += changes
        if changes == 0:
            converged = True
            break

    var canon = _canonicalize(labels, n)
    return _Moving(canon.label.copy(), canon.k, changes_total, rounds, converged)


def community_label_propagation_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    seed: Int,
    max_rounds: Int,
) -> CommunityPartition:
    """Label propagation over a CSR: near-linear per round, no objective guarantee.

    The cheap alternative to Louvain — one weighted scan of every edge per round, no
    aggregation, no modularity evaluated during the search. It is reported *with* a
    modularity so the two are comparable on the same graph, and `converged` says
    whether the labelling is a fixed point. Louvain is the driver to reach for when the
    score matters; this one is for when the graph is large and a reasonable grouping
    beats an optimal one.
    """
    if max_rounds <= 0:
        return _no_partition(COMMUNITY_ERR_INVALID_LIMITS, n_nodes)
    var rounds = max_rounds
    if rounds > COMMUNITY_PASS_LIMIT:
        rounds = COMMUNITY_PASS_LIMIT
    var level = _level_from_flat(row_ptr, targets, weights, n_nodes)
    if level.status != GRAPH_OK:
        return _no_partition(level.status, n_nodes)
    var lp = _label_propagation(level, seed, rounds)
    var terms = _level_terms(level, lp.comm, lp.k)
    var sizes = cluster_sizes(lp.comm, lp.k)
    return CommunityPartition(
        GRAPH_OK,
        level.n,
        lp.k,
        0,
        lp.passes,
        lp.moves,
        lp.converged,
        level.two_m * 0.5,
        terms.modularity,
        lp.comm.copy(),
        sizes^,
    )


def community_label_propagation_from_triplets(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    n_nodes: Int,
    seed: Int,
    max_rounds: Int,
) -> CommunityPartition:
    """Label propagation straight from an edge list."""
    if n_nodes < 0:
        return _no_partition(GRAPH_ERR_INVALID_DIMENSIONS, 0)
    if len(dst) != len(src) or len(weight) != len(src):
        return _no_partition(GRAPH_ERR_LENGTH_MISMATCH, n_nodes)
    var defect = _weight_defect(weight)
    if defect != GRAPH_OK:
        return _no_partition(defect, n_nodes)
    var g = graph_csr_from_triplets(src, dst, weight, n_nodes)
    return community_label_propagation_driver(
        g.row_ptr, g.targets, g.weights, g.n_nodes, seed, max_rounds
    )
