"""Seeded corpus generators for the arena (rule R2).

Each generator is deterministic given its seed; the seed is derived from a
per-duel base plus the size key, and is printed on every result card. The
generators are the same shapes as the published mojo-kernels benchmark
harnesses (benchmarks/bench_*.py @ the harness commit), scaled so a full
duel run fits the HF cpu-basic time budget.
"""

from __future__ import annotations

import random

import numpy as np

BASE_SEED = 20260919  # same base seed family as the published harness


# ---------------------------------------------------------------------------
# BM25 (benchmarks/bench_bm25.py, scaled)
# ---------------------------------------------------------------------------

BM25_VOCAB = 20_000


def bm25_corpus(seed: int, n_docs: int) -> list[list[str]]:
    rng = random.Random(seed)
    vocab = [f"w{i:05d}" for i in range(BM25_VOCAB)]
    weights = [1.0 / (i + 1) for i in range(BM25_VOCAB)]  # Zipf-ish
    return [rng.choices(vocab, weights, k=rng.randint(30, 60)) for _ in range(n_docs)]


def bm25_queries(seed: int, terms: list[str], q_len: int, n_queries: int) -> list[list[str]]:
    rng = random.Random(seed)
    return [
        [rng.choice(terms) for _ in range(q_len)] + (["zzz_unseen"] if i % 4 == 0 else [])
        for i in range(n_queries)
    ]


# ---------------------------------------------------------------------------
# pykalman (benchmarks/bench_pykalman.py)
# ---------------------------------------------------------------------------


def kalman_system(seed: int, n_s: int, n_o: int, T: int):
    rng = np.random.RandomState(seed)
    A = rng.randn(n_s, n_s)
    A *= 0.9 / max(abs(np.linalg.eigvals(A)))
    B = rng.randn(n_s, n_s)
    Q = B @ B.T + 0.2 * np.eye(n_s)
    C = rng.randn(n_o, n_s)
    D = rng.randn(n_o, n_o)
    R = D @ D.T + 0.2 * np.eye(n_o)
    b = rng.randn(n_s)
    d = rng.randn(n_o)
    x0 = rng.randn(n_s)
    E = rng.randn(n_s, n_s)
    P0 = E @ E.T + np.eye(n_s)
    obs = np.zeros((T, n_o))
    x = x0.copy()
    for t in range(T):
        if t > 0:
            x = A @ x + b + rng.multivariate_normal(np.zeros(n_s), Q)
        obs[t] = C @ x + d + rng.multivariate_normal(np.zeros(n_o), R)
    params = dict(
        transition_matrices=A,
        observation_matrices=C,
        transition_covariance=Q,
        observation_covariance=R,
        transition_offsets=b,
        observation_offsets=d,
        initial_state_mean=x0,
        initial_state_covariance=P0,
    )
    return params, obs


# ---------------------------------------------------------------------------
# ruptures (benchmarks/bench_ruptures.py)
# ---------------------------------------------------------------------------


def ruptures_signal(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    s = np.zeros(n)
    val, prev = 0.0, 0
    for p in sorted(rng.choice(np.arange(n // 10, n - n // 10), size=6, replace=False)):
        s[prev:p] = val
        val += rng.standard_normal() * 3.0
        prev = p
    s[prev:] = val
    return s + rng.standard_normal(n)


# ---------------------------------------------------------------------------
# motmetrics (benchmarks/bench_motmetrics.py)
# ---------------------------------------------------------------------------


def mot_stream(seed: int, n_frames: int, n_obj: int, n_hyp: int):
    """Deterministic synthetic MOT stream (frames of (oids, hids, dist))."""
    rng = np.random.default_rng(seed)
    frames = []
    alive_o: list[int] = []
    alive_h: list[int] = []
    next_o = 1
    next_h = 1000
    owner: dict[int, int] = {}
    for _ in range(n_frames):
        for o in list(alive_o):
            if rng.random() < 0.01:
                alive_o.remove(o)
                for h, oo in list(owner.items()):
                    if oo == o:
                        del owner[h]
        for h in list(alive_h):
            if rng.random() < 0.012:
                alive_h.remove(h)
                owner.pop(h, None)
        while len(alive_o) < n_obj:
            alive_o.append(next_o)
            next_o += 1
        while len(alive_h) < n_hyp:
            alive_h.append(next_h)
            next_h += 1
        for h in alive_h:
            if h not in owner and rng.random() < 0.9:
                owner[h] = alive_o[rng.integers(len(alive_o))]
        for h in list(owner):
            if rng.random() < 0.03:
                owner[h] = alive_o[rng.integers(len(alive_o))]
        pos_o = {o: rng.random() * 10 + o for o in alive_o}
        d = np.full((len(alive_o), len(alive_h)), np.nan)
        for i, o in enumerate(alive_o):
            for j, h in enumerate(alive_h):
                if rng.random() < 0.03:
                    continue
                base = abs(pos_o[o] - pos_o.get(owner.get(h, -1), 5.0))
                d[i, j] = base + rng.random() * 0.5
        frames.append((list(alive_o), list(alive_h), d))
    return frames


# ---------------------------------------------------------------------------
# croniter (benchmarks/bench_croniter.py expression set)
# ---------------------------------------------------------------------------

CRON_EXPRS = [
    ("*/5 * * * *", "every-5-min"),
    ("0 9 * * mon-fri", "daily-weekday"),
    ("37/6 14-8/5 */2 7/2 fri-thu", "mixed-wrap"),
    ("0 0 * * 5#3", "nth-weekday"),
    ("0 0 29 2 *", "sparse-feb29"),
]


# ---------------------------------------------------------------------------
# obspy Konno-Ohmachi (benchmarks/bench_obspy_konno.py)
# ---------------------------------------------------------------------------


def konno_freqs(n: int) -> np.ndarray:
    return np.logspace(-1, 2, n)


def konno_spectra(seed: int, shape) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(shape) * 100.0
