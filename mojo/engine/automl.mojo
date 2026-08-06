"""
automl.mojo — Hyperparameter search orchestration math. Zero Python imports.

Callback-free by design: every function returns a SCHEDULE (plain data) that
the caller executes however it likes (train loops, remote workers, ...).
Covers the classic budget-allocation algorithms:

Public API:
  successive_halving_schedule — rounds of (n_survivors, budget) for SHA
                                (Jamieson & Talwalkar 2016)
  hyperband_brackets          — full Hyperband bracket list, each bracket
                                carrying its own SHA schedule (Li et al. 2018)
  promote_top_k               — indices of the k best scores; ties broken by
                                lower index; output ordered best-first
  random_search_configs       — Latin-hypercube-style config matrix in [0,1),
                                deterministic for a given seed

Conventions:
  * budgets and config counts are exact integer math (no float log/pow), so
    schedules are bit-reproducible across platforms
  * round i of SHA runs floor(n / eta^i) configs at budget min_budget * eta^i
  * Hyperband bracket s runs SHA with n_s = ceil((s_max+1) * eta^s / (s+1))
    configs starting at budget floor(max_budget / eta^s), for s+1 rounds,
    where s_max = floor(log_eta(max_budget)); brackets are returned in order
    s = s_max, s_max-1, ..., 0 (most exploratory first)
"""


# ── schedule types ───────────────────────────────────────────────────────────


struct HalvingRound(Copyable, Movable):
    """One successive-halving round: how many configs survive into this round
    and the per-config budget they each receive."""
    var n_survivors: Int
    var budget: Int

    def __init__(out self, n_survivors: Int, budget: Int):
        self.n_survivors = n_survivors
        self.budget = budget


struct Bracket(Copyable, Movable):
    """One Hyperband bracket: identifier s, its initial config count and
    per-config starting budget, plus the full SHA schedule (s+1 rounds)."""
    var s: Int
    var n_configs: Int
    var min_budget: Int
    var rounds: List[HalvingRound]

    def __init__(
        out self,
        s: Int,
        n_configs: Int,
        min_budget: Int,
        rounds: List[HalvingRound],
    ):
        self.s = s
        self.n_configs = n_configs
        self.min_budget = min_budget
        self.rounds = rounds.copy()


# ── successive halving ───────────────────────────────────────────────────────


def successive_halving_schedule(
    n_configs: Int, min_budget: Int, eta: Int
) -> List[HalvingRound]:
    """SHA schedule: round i keeps floor(n_configs / eta^i) configs at budget
    min_budget * eta^i. Rounds continue while at least one config survives,
    i.e. floor(log_eta(n_configs)) + 1 rounds total.

    Example (n_configs=27, min_budget=1, eta=3):
      (27, 1), (9, 3), (3, 9), (1, 27)

    Invalid input (n_configs < 1, min_budget < 1, or eta < 2) -> empty list.
    """
    var rounds = List[HalvingRound]()
    if n_configs < 1 or min_budget < 1 or eta < 2:
        return rounds^
    var n = n_configs
    var b = min_budget
    while True:
        rounds.append(HalvingRound(n, b))
        if n < eta:  # floor(n / eta) would be 0: nothing left to halve
            break
        n = n // eta
        b = b * eta
    return rounds^


# ── hyperband ────────────────────────────────────────────────────────────────


def hyperband_brackets(max_budget: Int, eta: Int) -> List[Bracket]:
    """Hyperband bracket list for a maximum per-config budget R = max_budget.

    s_max = floor(log_eta(R)) computed by exact integer repeated
    multiplication (never float log). Returns s_max + 1 brackets, ordered
    s = s_max down to 0. Bracket s:
      n_s = ceil((s_max + 1) * eta^s / (s + 1))   initial configs
      r_s = floor(R / eta^s)                      initial per-config budget
      rounds i = 0..s: (max(floor(n_s / eta^i), 1), r_s * eta^i)

    Invalid input (max_budget < 1 or eta < 2) -> empty list.
    """
    var out = List[Bracket]()
    if max_budget < 1 or eta < 2:
        return out^
    var s_max = 0
    var pow_smax = 1
    while pow_smax * eta <= max_budget:
        pow_smax *= eta
        s_max += 1
    for s in range(s_max, -1, -1):
        var eta_s = 1
        for _ in range(s):
            eta_s *= eta
        # ceil((s_max + 1) * eta^s / (s + 1)) in pure integer math
        var n = ((s_max + 1) * eta_s + s) // (s + 1)
        var r = max_budget // eta_s
        var rounds = List[HalvingRound]()
        var pow_i = 1
        for _ in range(s + 1):
            var ni = n // pow_i
            if ni < 1:
                ni = 1
            rounds.append(HalvingRound(ni, r * pow_i))
            pow_i *= eta
        out.append(Bracket(s, n, r, rounds))
    return out^


# ── promotion ────────────────────────────────────────────────────────────────


def promote_top_k(scores: List[Float64], k: Int) -> List[Int]:
    """Indices of the k highest scores, ordered best-first. Ties broken
    deterministically by lower index (strict > comparison keeps the earlier
    index as champion). k is clamped to len(scores); k < 1 -> empty list.
    """
    var out = List[Int]()
    var n = len(scores)
    if k < 1 or n == 0:
        return out^
    var kk = k
    if kk > n:
        kk = n
    var taken = List[Bool]()
    for _ in range(n):
        taken.append(False)
    for _ in range(kk):
        var best = -1
        for i in range(n):
            if taken[i]:
                continue
            if best == -1 or scores[i] > scores[best]:
                best = i
        taken[best] = True
        out.append(best)
    return out^


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


def _rand_u01(mut state: UInt64) -> Float64:
    """Uniform Float64 in [0, 1) with 53 bits of mantissa."""
    state = _xorshift64(state)
    return Float64(state >> 11) / 9007199254740992.0  # 2^53


# ── random search (Latin hypercube) ──────────────────────────────────────────


def random_search_configs(
    n: Int, dims: Int, seed: Int
) -> List[List[Float64]]:
    """LHS-style config matrix: n rows x dims columns, every value in [0, 1).

    Per dimension, the n samples occupy the n strata [j/n, (j+1)/n) exactly
    once (stratum order is a seeded Fisher-Yates permutation, position inside
    the stratum is a seeded uniform jitter). Fully deterministic for a given
    (n, dims, seed). n < 1 or dims < 1 -> empty list.
    """
    var out = List[List[Float64]]()
    if n < 1 or dims < 1:
        return out^
    for _ in range(n):
        var row = List[Float64]()
        for _ in range(dims):
            row.append(0.0)
        out.append(row^)
    var state = _seed_state(seed)
    for d in range(dims):
        # seeded permutation of strata 0..n-1
        var perm = List[Int]()
        for i in range(n):
            perm.append(i)
        for i in range(n - 1, 0, -1):
            var j = _rand_below(state, i + 1)
            var tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp
        for i in range(n):
            var u = _rand_u01(state)
            out[i][d] = (Float64(perm[i]) + u) / Float64(n)
    return out^
