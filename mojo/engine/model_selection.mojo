"""
model_selection.mojo — Time-series-aware cross-validation splitters. Zero Python imports.

Replaces sklearn.model_selection (TimeSeriesSplit, KFold, StratifiedKFold,
train_test_split) plus Lopez de Prado purged/embargoed walk-forward CV for
temporal and financial data where label leakage across the train/test
boundary matters.

Public API:
  walk_forward_splits         — expanding- or rolling-window walk-forward splits
  purged_walk_forward_splits  — walk-forward with purge gap + embargo (Lopez de Prado)
  kfold_splits                — k-fold splits, optional seeded shuffle
  stratified_kfold_splits     — k-fold preserving class proportions per fold
  train_test_split_temporal   — single ordered train/test split by fraction
"""


# ── SplitIndices ─────────────────────────────────────────────────────────────


struct SplitIndices(Copyable, Movable):
    """One cross-validation split: train indices + test indices (ascending)."""
    var train: List[Int]
    var test: List[Int]

    def __init__(out self):
        self.train = List[Int]()
        self.test = List[Int]()

    def __init__(out self, var train: List[Int], var test: List[Int]):
        self.train = train^
        self.test = test^


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


def _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


def _seed_state(seed: Int) -> UInt64:
    """Expand an Int seed into a warmed-up nonzero xorshift64 state."""
    var base: UInt64
    if seed < 0:
        base = UInt64(-(seed + 1)) + 1
    else:
        base = UInt64(seed)
    var s = base ^ UInt64(0x9E3779B97F4A7C15)
    if s == 0:
        s = UInt64(0x9E3779B97F4A7C15)
    s = _xorshift64(s)
    s = _xorshift64(s)
    s = _xorshift64(s)
    return s


def _rand_below(mut state: UInt64, bound: Int) -> Int:
    """Uniform-ish integer in [0, bound). bound must be >= 1."""
    state = _xorshift64(state)
    return Int(state % UInt64(bound))


def _shuffle_ints(mut arr: List[Int], mut state: UInt64):
    """In-place Fisher-Yates shuffle driven by the caller's RNG state."""
    var n = len(arr)
    for i in range(n - 1, 0, -1):
        var j = _rand_below(state, i + 1)
        var tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp


# ── walk_forward_splits ──────────────────────────────────────────────────────


def walk_forward_splits(
    n: Int, n_splits: Int, min_train: Int, expanding: Bool
) -> List[SplitIndices]:
    """Walk-forward splits for ordered (time-series) data.

    Test region is [min_train, n), cut into n_splits contiguous,
    non-overlapping, ordered windows that cover the tail (last window
    ends at n). Any remainder goes to the earliest test windows.
    expanding=True: train = [0, test_start). expanding=False: rolling
    fixed-length train window of min_train samples ending at test_start.
    Returns empty list if the config is infeasible (each test window
    must hold at least one sample).
    """
    var result = List[SplitIndices]()
    if n <= 0 or n_splits <= 0 or min_train <= 0:
        return result^
    var region = n - min_train
    if region < n_splits:
        return result^
    var base = region // n_splits
    var rem = region % n_splits
    var start = min_train
    for j in range(n_splits):
        var size = base + (1 if j < rem else 0)
        var t0 = start
        var t1 = start + size
        var lo = 0
        if not expanding:
            lo = t0 - min_train
        var train = List[Int](capacity=t0 - lo)
        for i in range(lo, t0):
            train.append(i)
        var test = List[Int](capacity=t1 - t0)
        for i in range(t0, t1):
            test.append(i)
        result.append(SplitIndices(train^, test^))
        start = t1
    return result^


# ── purged_walk_forward_splits ───────────────────────────────────────────────


def purged_walk_forward_splits(
    n: Int, n_splits: Int, min_train: Int, purge_gap: Int, embargo: Int
) -> List[SplitIndices]:
    """Purged walk-forward splits (Lopez de Prado semantics, expanding window).

    Test region is [min_train + purge_gap, n), cut as in walk_forward_splits.
    For each split with test window [t0, t1):
      - purge: training is [0, t0 - purge_gap) — the purge_gap samples
        immediately before the test window are dropped (label leakage from
        overlapping forward-return windows);
      - embargo: the embargo samples immediately after each earlier test
        window's end are excluded from all subsequent training windows.
    Negative purge_gap/embargo are treated as 0. Returns empty list if the
    config is infeasible.
    """
    var result = List[SplitIndices]()
    var gap = purge_gap
    if gap < 0:
        gap = 0
    var emb = embargo
    if emb < 0:
        emb = 0
    if n <= 0 or n_splits <= 0 or min_train <= 0:
        return result^
    var region = n - min_train - gap
    if region < n_splits:
        return result^
    var base = region // n_splits
    var rem = region % n_splits

    var embargoed = List[Bool](capacity=n)
    for _ in range(n):
        embargoed.append(False)

    var start = min_train + gap
    for j in range(n_splits):
        var size = base + (1 if j < rem else 0)
        var t0 = start
        var t1 = start + size
        var train_end = t0 - gap
        var train = List[Int](capacity=train_end)
        for i in range(train_end):
            if not embargoed[i]:
                train.append(i)
        var test = List[Int](capacity=t1 - t0)
        for i in range(t0, t1):
            test.append(i)
        result.append(SplitIndices(train^, test^))
        # Mark embargo region after this test window for later training sets.
        var stop = t1 + emb
        if stop > n:
            stop = n
        for i in range(t1, stop):
            embargoed[i] = True
        start = t1
    return result^


# ── kfold_splits ─────────────────────────────────────────────────────────────


def kfold_splits(n: Int, k: Int, seed: Int, shuffle: Bool) -> List[SplitIndices]:
    """Standard k-fold splits over indices [0, n).

    shuffle=False: fold f tests the f-th contiguous block (first n % k folds
    get one extra sample). shuffle=True: indices are permuted with a
    deterministic seeded Fisher-Yates before assignment. Train/test index
    lists are always emitted in ascending order. Returns empty list when
    k < 2 or k > n.
    """
    var result = List[SplitIndices]()
    if n <= 0 or k <= 1 or k > n:
        return result^

    var order: List[Int]
    if shuffle:
        order = List[Int](capacity=n)
        for i in range(n):
            order.append(i)
        var rng = _seed_state(seed)
        _shuffle_ints(order, rng)
    else:
        order = List[Int](capacity=n)
        for i in range(n):
            order.append(i)

    var fold_of = List[Int](capacity=n)
    for _ in range(n):
        fold_of.append(0)
    var base = n // k
    var rem = n % k
    var pos = 0
    for f in range(k):
        var size = base + (1 if f < rem else 0)
        for _ in range(size):
            fold_of[order[pos]] = f
            pos += 1

    for f in range(k):
        var train = List[Int](capacity=n)
        var test = List[Int](capacity=n)
        for i in range(n):
            if fold_of[i] == f:
                test.append(i)
            else:
                train.append(i)
        result.append(SplitIndices(train^, test^))
    return result^


# ── stratified_kfold_splits ──────────────────────────────────────────────────


def stratified_kfold_splits(
    labels: List[Int], k: Int, seed: Int
) -> List[SplitIndices]:
    """Stratified k-fold: class proportions preserved per fold (within ±1).

    Each class's indices are shuffled with the seeded RNG, then dealt
    round-robin across folds; the fold cursor continues across classes so
    remainders spread evenly. If a class has fewer than k members, some
    folds simply lack that class. Train/test index lists are ascending.
    Returns empty list when k < 2 or k > len(labels).
    """
    var result = List[SplitIndices]()
    var n = len(labels)
    if n <= 0 or k <= 1 or k > n:
        return result^

    # Distinct class values in order of first appearance.
    var classes = List[Int]()
    for i in range(n):
        var found = False
        for c in range(len(classes)):
            if classes[c] == labels[i]:
                found = True
                break
        if not found:
            classes.append(labels[i])

    var rng = _seed_state(seed)
    var fold_of = List[Int](capacity=n)
    for _ in range(n):
        fold_of.append(0)

    var next_fold = 0
    for c in range(len(classes)):
        var cls = classes[c]
        var idxs = List[Int]()
        for i in range(n):
            if labels[i] == cls:
                idxs.append(i)
        _shuffle_ints(idxs, rng)
        for p in range(len(idxs)):
            fold_of[idxs[p]] = next_fold
            next_fold = (next_fold + 1) % k

    for f in range(k):
        var train = List[Int](capacity=n)
        var test = List[Int](capacity=n)
        for i in range(n):
            if fold_of[i] == f:
                test.append(i)
            else:
                train.append(i)
        result.append(SplitIndices(train^, test^))
    return result^


# ── train_test_split_temporal ────────────────────────────────────────────────


def train_test_split_temporal(n: Int, test_fraction: Float64) -> SplitIndices:
    """Single ordered split: train = [0, n - n_test), test = [n - n_test, n).

    n_test = round(n * test_fraction) (half-up), clamped to [0, n];
    test_fraction <= 0 yields an empty test set, >= 1 an empty train set.
    """
    var out = SplitIndices()
    if n <= 0:
        return out^
    var n_test = Int(Float64(n) * test_fraction + 0.5)
    if test_fraction <= 0.0:
        n_test = 0
    if test_fraction >= 1.0:
        n_test = n
    if n_test < 0:
        n_test = 0
    if n_test > n:
        n_test = n
    for i in range(n - n_test):
        out.train.append(i)
    for i in range(n - n_test, n):
        out.test.append(i)
    return out^
