"""The five race candidates, their seeded workloads, qualification and the results board.

A race is offered only where the kernel's compute dominates the call (round 7 autopsy,
2026-09-23): one haversine pair or one primality test sits on the C ABI's per-call floor
(12–13 µs of JSON parse, dispatch and serialize on an M4, 70–90 µs on the shared EPYC host)
that inlined Python arithmetic beats, and a 20,000-token bigram count or an 8,000-edge
Dijkstra moves more JSON than it computes. Those functions stay Playground parity references
(`REFERENCES`); the races are Levenshtein, betweenness and closeness centrality, batched
option Greeks and the prime sieve, each against the pure-Python library it replaces.

A candidate pairs one Hub-kernel function with the Python library it replaces, at the
library's ordinary call, over seeded S/M/L workloads built here (seed and size printed on the
card). A candidate is offered only when its incumbent package is installed in this container:
the UI names the missing package instead of substituting anything.

Qualification is read, never decided here: ``qualified.json`` from the results Dataset lists
the (race, size) cells the kernel won in three recorded runs (within five presses) on this hardware
(``apps/spaces/tools/requalify.py`` writes it; the file carries its own ``rule`` and
``generated_utc``, which the tab prints so the copy cannot drift from the file). A cell that
is not in the list is measured all the same but shown as parity plus both latencies and its
measured ratio marked ``not qualified`` — never a ratio hero. With no file, nothing is
qualified.

``run_race`` runs one cell under the rulebook (``bench.run_cell``: correctness gate before
timing, interleaved repeats, median/P95/MAD/CV, noisy is not recorded). The whole cell is one
lane job, so the incumbent — pure Python sharing the CPU — never runs beside a native call.

``Board`` keeps this Space's measured rows in memory (a ring) and appends each as one JSON line
to ``results.jsonl`` when the results directory is writable. Every measured cell is a row, with
its ``kind``: a qualified race the kernel won is a ``race`` row (the ratio is a claim); a cell
that is not qualified is a ``parity`` row (both latencies, the parity label and the measured
ratio marked ``not qualified`` — never a ratio claim);
a qualified race the incumbent won is held and disclosed on the card, never a row. The Dataset
``CommitScheduler`` that publishes those lines arrives in M4; until then the board is this
container's.

Every revision printed here — the lane's version, ``RaceRun.kernel_label``, a row's
``wheel_sha`` — is ``kernel_revision``: the Hub snapshot the kernel module was imported from,
the code that ran, never the capped revision the manifest wanted when the two differ.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import random
import threading
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from algenta_spaces import bench, hubkernel
from algenta_spaces.runtime import utc_stamp

log = logging.getLogger(__name__)

RACE_BUDGET_S = 20.0
BASE_SEED = 20260922
SIZE_KEYS: tuple[str, ...] = ("S", "M", "L")
QUALIFIED_URL_ENV = "ALGENTA_QUALIFIED_URL"
QUALIFIED_URL_DEFAULT = (
    "https://huggingface.co/datasets/thyn-ai/algenta-arena-results/resolve/main/qualified.json"
)
RESULTS_PATH_ENV = "ALGENTA_RESULTS_PATH"
RESULTS_PATH_DEFAULT = "/data/results.jsonl"
BOARD_CAPACITY = 200
UNREACHABLE = 1e17
#: `number_theory.is_prime` agrees with sympy up to 2^31 - 1 on the capped v1 kernel and returns
#: False for larger primes (4294967291, 2^63 - 25 checked on 2026-09-22); the sizes stay in the
#: range where the gate passes and the gate still runs on every cell.
PRIME_CEILING = 2**31 - 1

#: A row's `kind`: a qualified race the kernel won, or a measured cell that is not a race.
ROW_KIND_RACE = "race"
ROW_KIND_PARITY = "parity"
ROW_KINDS: tuple[str, ...] = (ROW_KIND_RACE, ROW_KIND_PARITY)

#: The plan's JSONL columns for one measured row.
ROW_COLUMNS: tuple[str, ...] = (
    "kind",
    "ts_utc",
    "space_id",
    "hardware_id",
    "hardware",
    "duel_id",
    "size",
    "n",
    "algenta_median_ms",
    "incumbent_median_ms",
    "p95",
    "mad",
    "cv",
    "ratio",
    "parity",
    "harness_commit",
    "wheel_sha",
    "incumbent_pin",
)

Gate = Callable[[Any, Any], tuple[bool, str]]


class RaceError(Exception):
    """A refusal before any timing: unknown race, size or an incumbent that is not installed."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def kernel_revision(kernel: hubkernel.LoadedKernel) -> str:
    """The revision the kernel runs at here: the Hub snapshot sha its module was imported from
    (`LoadedKernel.loaded_sha`, the `snapshots/<sha>/` directory `kernels` loaded), or the
    capped v1 sha when the path shows no snapshot. A lane version, a row's `wheel_sha` and a
    revision column name the code that ran — when the cache holds a revision past the capped
    one, that revision, not the manifest's."""
    loaded = str(getattr(kernel, "loaded_sha", "") or "")
    return loaded or kernel.snapshot_sha or kernel.capped_v1_sha


def revision_label(kernel: hubkernel.LoadedKernel) -> str:
    """`algenta-text@92ef06d` — the family at the revision that loaded (`kernel_revision`)."""
    return f"{kernel.family}@{kernel_revision(kernel)[:7]}"


# ---------------------------------------------------------------------------
# Workloads: seeded arguments, the incumbent's call on the same arguments, the gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Size:
    key: str
    label: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.key not in SIZE_KEYS:
            raise ValueError(f"size key must be one of {SIZE_KEYS}, got {self.key!r}")


@dataclass
class Workload:
    """One seeded cell: the kernel's arguments, the incumbent's call, the gate, the disclosure."""

    args: list[Any]
    incumbent: Callable[[], Any]
    gate: Gate
    note: str
    incumbent_config: str


@dataclass(frozen=True)
class Reference:
    """The incumbent on arbitrary arguments (the Playground's parity chip) plus its gate."""

    call: Callable[[Sequence[Any]], Any]
    gate: Gate
    config: str


def _rng(seed: int) -> random.Random:
    return random.Random(seed)  # noqa: S311 - seeded benchmark fixtures, not security


def _within(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def _rel_within(a: float, b: float, tol: float) -> bool:
    scale = max(abs(float(a)), abs(float(b)), 1e-300)
    return abs(float(a) - float(b)) / scale <= tol


def _directed_edges(n: int, m: int, rnd: random.Random) -> list[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    while len(edges) < m:
        a, b = rnd.randrange(n), rnd.randrange(n)
        if a != b:
            edges.add((a, b))
    return sorted(edges)


# -- levenshtein vs nltk ------------------------------------------------------------------


def _ref_levenshtein(args: Sequence[Any]) -> int:
    import nltk

    a, b = args
    return int(nltk.edit_distance(a, b))


def _gate_exact(ours: Any, theirs: Any) -> tuple[bool, str]:
    return ours == theirs, "exact match"


def build_levenshtein(size: Size, seed: int) -> Workload:
    length = int(size.params["chars"])
    rnd = _rng(seed)
    alphabet = "abcdefghijklmnopqrstuvwxyz "
    args = [
        "".join(rnd.choice(alphabet) for _ in range(length)),
        "".join(rnd.choice(alphabet) for _ in range(length)),
    ]
    return Workload(
        args=args,
        incumbent=lambda: _ref_levenshtein(args),
        gate=_gate_exact,
        note=f"two seeded strings of {length:,} characters · seed {seed}",
        incumbent_config=REF_LEVENSHTEIN.config,
    )


REF_LEVENSHTEIN = Reference(_ref_levenshtein, _gate_exact, "nltk.edit_distance(a, b)")


# -- betweenness vs networkx --------------------------------------------------------------


def _ref_betweenness(args: Sequence[Any]) -> list[float]:
    import networkx as nx

    src, dst, weight, n_nodes, weighted, normalized = args
    graph = nx.DiGraph()
    graph.add_nodes_from(range(int(n_nodes)))
    graph.add_weighted_edges_from(zip(src, dst, weight, strict=True))
    values = nx.betweenness_centrality(
        graph, normalized=bool(normalized), weight="weight" if weighted else None
    )
    return [values[i] for i in range(int(n_nodes))]


def _gate_values(ours: Any, theirs: Any) -> tuple[bool, str]:
    values = ours["values"] if isinstance(ours, Mapping) else ours
    ok = len(values) == len(theirs) and all(
        _within(x, y, 1e-9) for x, y in zip(values, theirs, strict=True)
    )
    return ok, "every value within 1e-9"


REF_BETWEENNESS = Reference(
    _ref_betweenness, _gate_values, "networkx.betweenness_centrality(G, normalized=True)"
)


def build_betweenness(size: Size, seed: int) -> Workload:
    n, m = int(size.params["nodes"]), int(size.params["edges"])
    edges = _directed_edges(n, m, _rng(seed))
    args = [[a for a, _ in edges], [b for _, b in edges], [1.0] * len(edges), n, False, True]
    return Workload(
        args=args,
        incumbent=lambda: _ref_betweenness(args),
        gate=_gate_values,
        note=f"seeded directed graph · {n:,} nodes · {m:,} edges · seed {seed}",
        incumbent_config=REF_BETWEENNESS.config,
    )


# -- dijkstra vs networkx -----------------------------------------------------------------


def _ref_dijkstra(args: Sequence[Any]) -> dict[int, float]:
    import networkx as nx

    n, edges, source = args
    graph = nx.DiGraph()
    graph.add_nodes_from(range(int(n)))
    graph.add_weighted_edges_from((e["src"], e["dst"], e["weight"]) for e in edges)
    return nx.single_source_dijkstra_path_length(graph, int(source))


def _gate_distances(ours: Any, theirs: Any) -> tuple[bool, str]:
    for node, distance in enumerate(ours):
        if node in theirs:
            if not _within(distance, theirs[node], 1e-9):
                return False, f"node {node} differs"
        elif float(distance) < UNREACHABLE:
            return False, f"node {node} reachable in one lane only"
    if any(node >= len(ours) for node in theirs):
        return False, "distance vector shorter than the graph"
    return True, "reachable distances within 1e-9, unreachable nodes agree"


REF_DIJKSTRA = Reference(
    _ref_dijkstra, _gate_distances, "networkx.single_source_dijkstra_path_length(G, source)"
)


# -- word n-grams vs nltk -----------------------------------------------------------------

_WORDS = ("the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog", "a", "kernel")


def _ref_ngrams(args: Sequence[Any]) -> list[str]:
    import nltk

    tokens, n = args
    return ["_".join(gram) for gram in nltk.ngrams(list(tokens), int(n))]


def _gate_lists(ours: Any, theirs: Any) -> tuple[bool, str]:
    return list(ours) == list(theirs), "exact match"


REF_NGRAMS = Reference(_ref_ngrams, _gate_lists, '"_".join(g) for g in nltk.ngrams(tokens, n)')


# -- primality vs sympy -------------------------------------------------------------------


def _ref_is_prime(args: Sequence[Any]) -> bool:
    import sympy

    (n,) = args
    return bool(sympy.isprime(int(n)))


def _gate_bool(ours: Any, theirs: Any) -> tuple[bool, str]:
    return bool(ours) == bool(theirs), "exact match"


REF_IS_PRIME = Reference(_ref_is_prime, _gate_bool, "sympy.isprime(n)")


# -- option Greeks vs py_vollib -----------------------------------------------------------

_GREEKS = ("price", "delta", "gamma", "vega", "theta")


def _ref_greeks(args: Sequence[Any]) -> dict[str, list[float]]:
    from py_vollib.black_scholes import black_scholes
    from py_vollib.black_scholes.greeks import analytical

    spots, strikes, times, rates, sigmas, is_calls = args
    out: dict[str, list[float]] = {k: [] for k in _GREEKS}
    for spot, strike, t, r, sigma, call in zip(
        spots, strikes, times, rates, sigmas, is_calls, strict=True
    ):
        flag = "c" if call else "p"
        out["price"].append(black_scholes(flag, spot, strike, t, r, sigma))
        out["delta"].append(analytical.delta(flag, spot, strike, t, r, sigma))
        out["gamma"].append(analytical.gamma(flag, spot, strike, t, r, sigma))
        # py_vollib quotes vega per 1 % of volatility and theta per calendar day.
        out["vega"].append(analytical.vega(flag, spot, strike, t, r, sigma) * 100.0)
        out["theta"].append(analytical.theta(flag, spot, strike, t, r, sigma) * 365.0)
    return out


def _gate_greeks(ours: Any, theirs: Any) -> tuple[bool, str]:
    for key in _GREEKS:
        if len(ours[key]) != len(theirs[key]):
            return False, f"{key} length differs"
        if not all(_within(x, y, 1e-5) for x, y in zip(ours[key], theirs[key], strict=True)):
            return False, f"{key} differs beyond 1e-5"
    # no identifier in board copy (`no_identifiers_in_copy`): the library is named by its lane
    return True, "price and Greeks within 1e-5 (vega per 1 %, theta per day, rescaled)"


REF_GREEKS = Reference(
    _ref_greeks, _gate_greeks, "py_vollib.black_scholes + greeks.analytical per option"
)


def build_greeks(size: Size, seed: int) -> Workload:
    count = int(size.params["options"])
    rnd = _rng(seed)
    args = [
        [round(rnd.uniform(80.0, 120.0), 4) for _ in range(count)],
        [round(rnd.uniform(80.0, 120.0), 4) for _ in range(count)],
        [round(rnd.uniform(0.1, 2.0), 4) for _ in range(count)],
        [0.05] * count,
        [round(rnd.uniform(0.1, 0.5), 4) for _ in range(count)],
        [float(rnd.randrange(2)) for _ in range(count)],
    ]
    return Workload(
        args=args,
        incumbent=lambda: _ref_greeks(args),
        gate=_gate_greeks,
        note=f"{count:,} seeded options · spot 80–120 · 0.1–2 y · vol 10–50 % · seed {seed}",
        incumbent_config=REF_GREEKS.config,
    )


# -- closeness centrality vs networkx -----------------------------------------------------


def _csr(n: int, edges: Sequence[tuple[int, int]]) -> tuple[list[int], list[int]]:
    """Row pointers and sorted targets of a directed edge list — the kernel's CSR input."""
    out: list[list[int]] = [[] for _ in range(n)]
    for a, b in edges:
        out[a].append(b)
    row_ptr = [0]
    targets: list[int] = []
    for a in range(n):
        targets.extend(sorted(out[a]))
        row_ptr.append(len(targets))
    return row_ptr, targets


def _ref_closeness(args: Sequence[Any]) -> list[float]:
    """networkx's closeness on the distances *from* each node (the kernel walks out-edges;
    networkx walks in-edges, so the graph is reversed), Wasserman–Faust scaled (its default)."""
    import networkx as nx

    row_ptr, targets, _weights, n_nodes, _weighted = args
    graph = nx.DiGraph()
    graph.add_nodes_from(range(int(n_nodes)))
    for a in range(int(n_nodes)):
        for k in range(row_ptr[a], row_ptr[a + 1]):
            graph.add_edge(targets[k], a)  # reversed: networkx measures incoming distances
    values = nx.closeness_centrality(graph)
    return [values[i] for i in range(int(n_nodes))]


def _gate_closeness(ours: Any, theirs: Any) -> tuple[bool, str]:
    """`scaled_values` against networkx within 1e-9 where the kernel defines a value; a node
    that reaches nothing is undefined for the kernel and 0.0 for networkx."""
    scaled = ours["scaled_values"] if isinstance(ours, Mapping) else ours
    defined = ours["defined"] if isinstance(ours, Mapping) else [True] * len(scaled)
    if len(scaled) != len(theirs):
        return False, "length differs"
    for node, (x, y, ok) in enumerate(zip(scaled, theirs, defined, strict=True)):
        if ok and not _within(x, y, 1e-9):
            return False, f"node {node} differs"
        if not ok and float(y) != 0.0:
            return False, f"node {node} undefined in one lane only"
    return True, "every defined value within 1e-9, unreachable nodes agree"


REF_CLOSENESS = Reference(
    _ref_closeness, _gate_closeness, "networkx.closeness_centrality(G.reverse())"
)


def build_closeness(size: Size, seed: int) -> Workload:
    n, m = int(size.params["nodes"]), int(size.params["edges"])
    row_ptr, targets = _csr(n, _directed_edges(n, m, _rng(seed)))
    args = [row_ptr, targets, [1.0] * len(targets), n, False]
    return Workload(
        args=args,
        incumbent=lambda: _ref_closeness(args),
        gate=_gate_closeness,
        note=f"seeded directed graph · {n:,} nodes · {m:,} edges · seed {seed}",
        incumbent_config=REF_CLOSENESS.config,
    )


# -- primes below N (sieve) vs sympy --------------------------------------------------------


def _ref_primes(args: Sequence[Any]) -> list[int]:
    import sympy

    (limit,) = args
    return list(sympy.primerange(2, int(limit) + 1))


REF_PRIMES = Reference(_ref_primes, _gate_exact, "list(sympy.primerange(2, limit + 1))")


#: The largest sieve a cell may ask for: 10^7 returns 664,579 primes (~6 MB of JSON) and keeps
#: sympy's lane inside the cell budget; beyond it the response, not the compute, is the cell.
PRIMES_LIMIT_CEILING = 10_000_000


def build_primes(size: Size, seed: int) -> Workload:
    limit = int(size.params["limit"])
    if limit < 2 or limit > PRIMES_LIMIT_CEILING:
        raise RaceError(
            "size_out_of_range", f"primes: limit must be between 2 and {PRIMES_LIMIT_CEILING:,}"
        )
    args = [limit]
    return Workload(
        args=args,
        incumbent=lambda: _ref_primes(args),
        gate=_gate_exact,
        note=f"every prime up to {limit:,} · the same list from both lanes",
        incumbent_config=REF_PRIMES.config,
    )


# -- haversine vs geopy (a Playground parity reference; one pair is no race) ---------------


def _ref_haversine(args: Sequence[Any]) -> float:
    from geopy import distance as geodistance

    lat1, lon1, lat2, lon2 = (float(v) for v in args)
    return float(geodistance.great_circle((lat1, lon1), (lat2, lon2)).km)


def _gate_haversine(ours: Any, theirs: Any) -> tuple[bool, str]:
    ok = _rel_within(ours, theirs, 5e-6)
    return ok, "within 5e-6 relative (geopy's mean radius 6371.009 km, kernel 6371 km)"


REF_HAVERSINE = Reference(_ref_haversine, _gate_haversine, "geopy.distance.great_circle(a, b).km")


#: The Playground's parity references, keyed by ``module.function``; each needs its package.
REFERENCES: dict[str, tuple[str, str, Reference]] = {
    "text.fuzzy.levenshtein_distance": ("nltk", "nltk", REF_LEVENSHTEIN),
    "graph_analytics.centrality.graph_betweenness_from_triplets": (
        "networkx",
        "networkx",
        REF_BETWEENNESS,
    ),
    "graph.weighted.shortest_path_dijkstra": ("networkx", "networkx", REF_DIJKSTRA),
    "text.tokenizer.word_ngrams": ("nltk", "nltk", REF_NGRAMS),
    "number_theory.is_prime": ("sympy", "sympy", REF_IS_PRIME),
    "option_greeks_batch.chain_greeks": ("py_vollib", "py_vollib", REF_GREEKS),
    "geodesy.haversine_distance": ("geopy", "geopy", REF_HAVERSINE),
    "graph_analytics.centrality.graph_closeness_centrality": (
        "networkx",
        "networkx",
        REF_CLOSENESS,
    ),
    "number_theory.sieve_of_eratosthenes": ("sympy", "sympy", REF_PRIMES),
}


def reference_for(module: str, function: str) -> tuple[Reference, str] | None:
    """The installed reference for ``module.function`` with its ``name==version``, or None."""
    entry = REFERENCES.get(f"{module}.{function}")
    if entry is None:
        return None
    import_name, dist_name, reference = entry
    version = incumbent_version(import_name, dist_name)
    if version is None:
        return None
    return reference, f"{dist_name}=={version}"


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    family: str
    module: str
    function: str
    incumbent: str
    import_name: str
    sizes: tuple[Size, ...]
    build: Callable[[Size, int], Workload]
    default_size: str = "M"

    def __post_init__(self) -> None:
        keys = [size.key for size in self.sizes]
        if keys != list(SIZE_KEYS):
            raise ValueError(f"{self.id}: sizes must be S, M, L in order, got {keys}")
        if self.default_size not in keys:
            raise ValueError(f"{self.id}: default size {self.default_size!r} is not offered")

    @property
    def qualname(self) -> str:
        return f"{self.module}.{self.function}"

    def size(self, key: str) -> Size:
        for size in self.sizes:
            if size.key == key:
                return size
        raise RaceError("unknown_size", f"{self.id} has no size {key!r}")


def _sizes(*entries: tuple[str, str, dict[str, Any]]) -> tuple[Size, ...]:
    return tuple(Size(key, label, params) for key, label, params in entries)


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "levenshtein",
        "Levenshtein distance",
        "text",
        "text.fuzzy",
        "levenshtein_distance",
        "nltk",
        "nltk",
        _sizes(
            ("S", "300 × 300 characters", {"chars": 300}),
            ("M", "600 × 600 characters", {"chars": 600}),
            ("L", "1,000 × 1,000 characters", {"chars": 1000}),
        ),
        build_levenshtein,
    ),
    Candidate(
        "betweenness",
        "Betweenness centrality",
        "graph",
        "graph_analytics.centrality",
        "graph_betweenness_from_triplets",
        "networkx",
        "networkx",
        _sizes(
            ("S", "100 nodes · 400 edges", {"nodes": 100, "edges": 400}),
            ("M", "200 nodes · 800 edges", {"nodes": 200, "edges": 800}),
            ("L", "400 nodes · 1,600 edges", {"nodes": 400, "edges": 1600}),
        ),
        build_betweenness,
    ),
    Candidate(
        "closeness",
        "Closeness centrality",
        "graph",
        "graph_analytics.centrality",
        "graph_closeness_centrality",
        "networkx",
        "networkx",
        _sizes(
            ("S", "200 nodes · 800 edges", {"nodes": 200, "edges": 800}),
            ("M", "500 nodes · 2,000 edges", {"nodes": 500, "edges": 2000}),
            ("L", "1,000 nodes · 4,000 edges", {"nodes": 1000, "edges": 4000}),
        ),
        build_closeness,
    ),
    Candidate(
        "greeks",
        "Option chain Greeks",
        "finance",
        "option_greeks_batch",
        "chain_greeks",
        "py_vollib",
        "py_vollib",
        _sizes(
            ("S", "1,000 options", {"options": 1000}),
            ("M", "5,000 options", {"options": 5000}),
            ("L", "20,000 options", {"options": 20000}),
        ),
        build_greeks,
    ),
    Candidate(
        "primes",
        "Primes below N",
        "bits-time",
        "number_theory",
        "sieve_of_eratosthenes",
        "sympy",
        "sympy",
        _sizes(
            ("S", "primes below 500,000", {"limit": 500_000}),
            ("M", "primes below 1,000,000", {"limit": 1_000_000}),
            ("L", "primes below 1,500,000", {"limit": 1_500_000}),
        ),
        build_primes,
    ),
)
CANDIDATES_BY_ID: dict[str, Candidate] = {c.id: c for c in CANDIDATES}


def candidate(race_id: str) -> Candidate:
    try:
        return CANDIDATES_BY_ID[race_id]
    except KeyError:
        raise RaceError("unknown_race", f"no race candidate {race_id!r}") from None


# ---------------------------------------------------------------------------
# Availability: the incumbent must be installed, the family loaded
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Offer:
    """One candidate as this container can offer it."""

    candidate: Candidate
    available: bool
    reason: str
    incumbent_version: str

    @property
    def incumbent_pin(self) -> str:
        return f"{self.candidate.incumbent}=={self.incumbent_version}"


def incumbent_version(import_name: str, dist_name: str) -> str | None:
    """The installed version when the package imports, None when it is absent."""
    if importlib.util.find_spec(import_name) is None:
        return None
    try:
        return metadata.version(dist_name)
    except metadata.PackageNotFoundError:
        return "installed"


def offers(
    loaded_families: Iterable[str],
    candidates: Sequence[Candidate] = CANDIDATES,
    *,
    version_of: Callable[[str, str], str | None] = incumbent_version,
) -> list[Offer]:
    """Every candidate with whether it can run here and, when not, the one reason."""
    families = {hubkernel.short_family(f) for f in loaded_families}
    out: list[Offer] = []
    for cand in candidates:
        version = version_of(cand.import_name, cand.incumbent)
        if version is None:
            out.append(Offer(cand, False, f"{cand.incumbent} is not installed here", ""))
        elif hubkernel.short_family(cand.family) not in families:
            out.append(Offer(cand, False, f"algenta-{cand.family} did not load here", version))
        else:
            out.append(Offer(cand, True, "", version))
    return out


# ---------------------------------------------------------------------------
# Qualification
# ---------------------------------------------------------------------------

ANY_SIZE = "*"


@dataclass(frozen=True)
class Qualified:
    """The (race, size) cells qualified on this hardware, and where the list came from."""

    cells: frozenset[tuple[str, str]]
    source: str
    fetched_utc: str
    error: str = ""
    file_hardware_id: str = ""
    #: The file's own statement of its rule and when it was written (printed on the tab).
    rule: str = ""
    generated_utc: str = ""

    def is_qualified(self, race_id: str, size: str) -> bool:
        return (race_id, size) in self.cells or (race_id, ANY_SIZE) in self.cells

    @property
    def empty(self) -> bool:
        return not self.cells


def parse_qualified(data: Any, *, hardware_id: str = "") -> Qualified:
    """Accept a list of race ids, a list of ``{race_id, size}`` records, or an object with a
    ``qualified`` list; a file stamped with another ``hardware_id`` qualifies nothing here."""
    file_hardware = ""
    rule = ""
    generated = ""
    entries = data
    if isinstance(data, Mapping):
        file_hardware = str(data.get("hardware_id", "") or "")
        rule = str(data.get("rule", "") or "").strip()
        generated = str(data.get("generated_utc", "") or "").strip()
        entries = data.get("qualified", [])
    if not isinstance(entries, list):
        raise ValueError("qualified.json holds neither a list nor an object with `qualified`")
    cells: set[tuple[str, str]] = set()
    for entry in entries:
        if isinstance(entry, str):
            cells.add((entry, ANY_SIZE))
        elif isinstance(entry, Mapping):
            race = str(entry.get("race_id") or entry.get("duel_id") or "")
            if race:
                cells.add((race, str(entry.get("size") or ANY_SIZE)))
    if file_hardware and hardware_id and file_hardware != hardware_id:
        cells = set()
    return Qualified(
        frozenset(cells),
        "",
        utc_stamp(),
        file_hardware_id=file_hardware,
        rule=rule,
        generated_utc=generated,
    )


def load_qualified(
    fetch: Callable[[str], Any],
    *,
    url: str | None = None,
    env: Mapping[str, str] | None = None,
    hardware_id: str = "",
) -> Qualified:
    """Fetch and parse the qualified list; any failure is an empty list with the reason."""
    env = os.environ if env is None else env
    target = url or env.get(QUALIFIED_URL_ENV, "").strip() or QUALIFIED_URL_DEFAULT
    try:
        fetched = fetch(target)
    except Exception as exc:  # the fetcher is injected; nothing here may take the tab down
        return Qualified(frozenset(), target, utc_stamp(), f"{type(exc).__name__}: {exc}")
    error = str(getattr(fetched, "error", "") or "")
    data = getattr(fetched, "data", fetched)
    if error or data is None:
        return Qualified(frozenset(), target, utc_stamp(), error or "empty response")
    try:
        parsed = parse_qualified(data, hardware_id=hardware_id)
    except ValueError as exc:
        return Qualified(frozenset(), target, utc_stamp(), str(exc))
    return Qualified(
        parsed.cells,
        target,
        parsed.fetched_utc,
        "",
        parsed.file_hardware_id,
        rule=parsed.rule,
        generated_utc=parsed.generated_utc,
    )


# ---------------------------------------------------------------------------
# Running one cell
# ---------------------------------------------------------------------------


@dataclass
class RaceRun:
    """One executed cell with everything the card and the board need."""

    candidate: Candidate
    size: Size
    workload: Workload
    cell: bench.CellResult
    qualified: bool
    incumbent_pin: str
    kernel_label: str

    @property
    def title(self) -> str:
        return f"{self.candidate.title} · {self.size.label}"

    @property
    def subtitle(self) -> str:
        """`text.fuzzy.levenshtein_distance vs nltk.edit_distance(a, b)` — the two exact calls."""
        return f"{self.candidate.qualname} vs {self.workload.incumbent_config}"

    @property
    def caption(self) -> str:
        """`two seeded strings of 600 characters · seed 20260922 · vs nltk 3.9.1` — the workload
        and the incumbent in words, for the card; the exact calls stay in `subtitle`."""
        incumbent = self.candidate.incumbent
        version = self.incumbent_pin.partition("==")[2]
        against = f"vs {incumbent} {version}".rstrip() if version else f"vs {incumbent}"
        return f"{self.workload.note} · {against}"

    @property
    def won(self) -> bool:
        return self.cell.measured and self.cell.ratio is not None and self.cell.ratio > 1.0

    @property
    def held(self) -> bool:
        """A qualified race the incumbent won this run: disclosed on the card, never a row."""
        return self.qualified and self.cell.measured and not self.won

    @property
    def row_kind(self) -> str | None:
        """`race` for a qualified win, `parity` for a measured cell that is not a race, None
        for a cell that becomes no row (not measured, or held)."""
        if not self.cell.measured or self.cell.ratio is None or self.held:
            return None
        return ROW_KIND_RACE if self.qualified else ROW_KIND_PARITY


def run_race(
    cand: Candidate,
    size_key: str,
    kernel: hubkernel.LoadedKernel,
    *,
    qualified: bool,
    incumbent_pin: str,
    seed: int = BASE_SEED,
    budget_s: float = RACE_BUDGET_S,
    progress: Callable[[str], None] | None = None,
    execute: Callable[..., Any] = hubkernel.execute,
    **cell_kwargs: Any,
) -> RaceRun:
    """Build the seeded workload and run the two lanes under the rulebook.

    Call this from inside the native lane: the cell times the kernel and the incumbent
    back to back and nothing else native may run meanwhile.
    """
    size = cand.size(size_key)
    workload = cand.build(size, seed)

    def ours() -> Any:
        return execute(kernel, cand.module, cand.function, workload.args).result

    lanes = [
        bench.LaneSpec(
            f"algenta-{cand.family}",
            bench.SIDE_ALGENTA,
            ours,
            version=kernel_revision(kernel)[:7],
            config=cand.qualname,
        ),
        bench.LaneSpec(
            cand.incumbent,
            bench.SIDE_INCUMBENT,
            workload.incumbent,
            version=incumbent_pin.partition("==")[2],
            config=workload.incumbent_config,
        ),
    ]

    def gate(outputs: dict[str, Any]) -> tuple[bool, str]:
        return workload.gate(outputs[lanes[0].name], outputs[lanes[1].name])

    cell = bench.run_cell(
        lanes, correctness_gate=gate, seed=seed, budget_s=budget_s, progress=progress, **cell_kwargs
    )
    return RaceRun(
        candidate=cand,
        size=size,
        workload=workload,
        cell=cell,
        qualified=qualified,
        incumbent_pin=incumbent_pin,
        kernel_label=revision_label(kernel),
    )


# ---------------------------------------------------------------------------
# The results board
# ---------------------------------------------------------------------------


def sig(value: float, figures: int = 6) -> float:
    """`value` rounded to `figures` significant figures — the board's numbers keep every digit
    the card prints (three) with room to spare, whatever the unit."""
    return float(f"{value:.{figures}g}")


def row_from_run(
    run: RaceRun,
    *,
    hardware: str,
    hardware_id: str,
    space_id: str,
    harness_commit: str,
    wheel_sha: str,
) -> dict[str, Any]:
    """The plan's JSONL row for one measured cell, with its `kind` (`RaceRun.row_kind`); refuses
    cells that were not measured and the held cell (a qualified race the incumbent won)."""
    kind = run.row_kind
    if kind is None:
        if run.held:
            raise ValueError("a held cell is disclosed on the card, never a row")
        raise ValueError("only measured cells become rows")
    ours = run.cell.lane(bench.SIDE_ALGENTA)
    theirs = run.cell.lane(bench.SIDE_INCUMBENT)
    if ours is None or theirs is None:
        raise ValueError("a row needs both lanes")
    return {
        "kind": kind,
        "ts_utc": run.cell.ts_utc,
        "space_id": space_id,
        "hardware_id": hardware_id,
        "hardware": hardware,
        "duel_id": run.candidate.id,
        "size": run.size.key,
        "n": run.cell.n,
        # six significant figures, not four decimals: a 4.38 µs incumbent must read 4.38 µs on the
        # board too, never 4.40 µs (launch review round 3)
        "algenta_median_ms": sig(ours.median_ms),
        "incumbent_median_ms": sig(theirs.median_ms),
        "p95": sig(ours.p95_ms),
        "mad": sig(ours.mad_ms),
        "cv": round(ours.cv, 4),
        "ratio": round(run.cell.ratio, 4),
        "parity": run.cell.parity_label,
        "harness_commit": harness_commit,
        "wheel_sha": wheel_sha,
        "incumbent_pin": run.incumbent_pin,
    }


def row_kind(row: Mapping[str, Any]) -> str:
    """A row's kind; a row written before the column existed could only have been a win."""
    kind = str(row.get("kind") or ROW_KIND_RACE)
    return kind if kind in ROW_KINDS else ROW_KIND_RACE


class Board:
    """This Space's measured rows: a ring in memory plus a JSON line per row when writable."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        env: Mapping[str, str] | None = None,
        capacity: int = BOARD_CAPACITY,
    ):
        env = os.environ if env is None else env
        target = env.get(RESULTS_PATH_ENV) or RESULTS_PATH_DEFAULT
        self.path = Path(target if path is None else path)
        self._rows: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self.writable = _writable(self.path)
        if self.writable:
            self._rows.extend(_read_rows(self.path, capacity))

    def append(self, row: Mapping[str, Any]) -> bool:
        """Keep the row; True when it also reached the JSONL file."""
        missing = [c for c in ROW_COLUMNS if c not in row]
        if missing:
            raise ValueError(f"row lacks {', '.join(missing)}")
        record = dict(row)
        with self._lock:
            self._rows.append(record)
            if not self.writable:
                return False
            try:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, sort_keys=True) + "\n")
            except OSError as exc:
                log.warning("results.jsonl append failed: %s", exc)
                self.writable = False
                return False
        return True

    def rows(self) -> list[dict[str, Any]]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._rows))

    def last_win(self, race_id: str, size: str | None = None) -> dict[str, Any] | None:
        """The newest `race` row for the cell — a parity row is a measurement, not a win."""
        for row in self.rows():
            if row_kind(row) != ROW_KIND_RACE:
                continue
            if row["duel_id"] == race_id and (size is None or row["size"] == size):
                return row
        return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._rows)


def _writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
    except OSError:
        return False
    return True


def _read_rows(path: Path, capacity: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines[-capacity:]:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        # A line written before the `kind` column existed could only have been a win.
        record.setdefault("kind", ROW_KIND_RACE)
        if all(c in record for c in ROW_COLUMNS):
            rows.append(record)
    return rows


__all__ = [
    "BASE_SEED",
    "REFERENCES",
    "Reference",
    "reference_for",
    "CANDIDATES",
    "CANDIDATES_BY_ID",
    "PRIME_CEILING",
    "QUALIFIED_URL_DEFAULT",
    "QUALIFIED_URL_ENV",
    "RACE_BUDGET_S",
    "RESULTS_PATH_DEFAULT",
    "RESULTS_PATH_ENV",
    "ROW_COLUMNS",
    "ROW_KINDS",
    "ROW_KIND_PARITY",
    "ROW_KIND_RACE",
    "SIZE_KEYS",
    "Board",
    "Candidate",
    "Offer",
    "Qualified",
    "RaceError",
    "RaceRun",
    "Size",
    "Workload",
    "candidate",
    "incumbent_version",
    "kernel_revision",
    "load_qualified",
    "revision_label",
    "offers",
    "parse_qualified",
    "row_from_run",
    "row_kind",
    "run_race",
]
