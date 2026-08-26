"""Retrieval on the local runtime — six typed verbs, one explicit backend per call.

Retrieval is not one operation. A dense lane, a sparse lane, a fusion, a reranker and
a metadata prefilter are five different computations with five different failure modes,
and a surface that hides which one ran cannot tell you why an answer looks the way it
does. So every verb here names its `backend`, every result records which lane produced
each item, and `provenance` turns that record into a sentence:

    from algenta import MojoRuntime, RetrievalCandidate, sparse_search, provenance

    runtime = MojoRuntime(mode="local")

    result = sparse_search(
        runtime,
        query="tokenize query",
        documents=[
            RetrievalDocument(id="a", text="def tokenize_query_parser(x): return x"),
            RetrievalDocument(id="b", text="class Retriever: pass"),
        ],
        top_k=5,
        backend="lexical",
    )
    result.hits[0].id                       # "a"
    provenance(result).items[0].explanation # why "a" ranked first

The rule that makes the rest of it trustworthy
----------------------------------------------
**A requested-but-unavailable backend raises. It never returns an empty result.**

An empty list is a real answer — it means nothing matched. If a missing engine also
produced an empty list, then the two most different outcomes in retrieval would be the
same value, and no caller could tell a broken deployment from an unlucky query. So a
backend that is not present raises `RetrievalBackendUnavailableError`, and the error
names the dependency that is missing so an operator can act on it rather than guess.

Nothing here starts a process. `MojoRuntime(mode="local")` runs the compiled kernels
in this process; there is no daemon, sidecar, service or container to launch, and a
runtime object configured for anything but local execution is refused rather than
quietly used.

What each backend is, and what it needs
---------------------------------------
`local`
    The compiled kernels bundled with this SDK, over a corpus supplied **in the
    request**. No persistent index exists, so nothing is stored between calls. Serves
    the dense lane, fusion, reranking and the metadata prefilter. Needs the retrieval
    kernel module in the installed runtime shard.

`lexical`
    The retrieval engine's lexical (BM25) index, built over the documents supplied in
    the request. It owns tokenization, the postings list and the term statistics — this
    module never reimplements any of them, and never rescores what it returns.

`dense`
    The retrieval engine's approximate-nearest-neighbour index over a built collection.

`index`
    The governed, temporal collection: `remember`, `recall`, `compact`, and searches
    over stored content. This is the backend with provenance to an immutable episode,
    a validity window and a retention policy, and it is the only one where a result
    outlives the call that produced it.

The lanes a verb can be served by are fixed, because a verb whose backend cannot
produce its lane is a request that will be rejected — and the place to reject it is
here, where the caller's own arguments are still available to quote back.

Where the arithmetic happens
----------------------------
Ranking, fusion and reranking are compiled kernels called through
`runtime.execute("retrieval.score", ...)`. This module marshals: it builds flat,
row-major payloads, checks their shapes, and decodes what comes back. It does not
compute a score, a fused value, or a rank — a score computed here would be a second,
divergent definition of the answer, and provenance over it would be a fiction.
The one thing built in Python is the metadata mask for a filtered search, because
string and dictionary matching is not arithmetic and the kernels take numbers.

Nulls, absences and sentinels
-----------------------------
A lane that did not return an item contributes `rank=None`, not rank 0 and not score
0.0 — an item no lane retrieved is absent from that lane, and folding absence into a
number is how a missing contribution starts looking like a weak one. On the wire, a
rank is 1-based and 0 means "this lane did not return this item"; 0 is outside the
value domain of a rank, so the sentinel cannot collide with an answer.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

__all__ = [
    "BACKENDS",
    "FUSIONS",
    "LANES",
    "METRICS",
    "RERANK_METHODS",
    "VERBS",
    "BackendStatus",
    "CompactionReport",
    "RememberReceipt",
    "Retrieval",
    "RetrievalBackendUnavailableError",
    "RetrievalCandidate",
    "RetrievalDocument",
    "RetrievalError",
    "RetrievalFilter",
    "RetrievalHit",
    "RetrievalLaneContribution",
    "RetrievalProvenance",
    "RetrievalProvenanceItem",
    "RetrievalRequest",
    "RetrievalResult",
    "backend_status",
    "compact",
    "filtered_search",
    "hybrid_search",
    "provenance",
    "recall",
    "remember",
    "rerank",
    "sparse_search",
    "vector_search",
]

# ── vocabulary ────────────────────────────────────────────────────────────────
# One spelling per concept, shared with the hosted memory surface so the same
# operation is never named two ways: `remember` / `recall` / `compact` are the verbs
# /v1/memory already exposes, `collection` is its collection, `where` its columnar
# prefilter, `as_of` its temporal view, and `top_k` its result count.
VERBS = (
    "vector_search",
    "sparse_search",
    "hybrid_search",
    "rerank",
    "filtered_search",
    "provenance",
    "remember",
    "recall",
    "compact",
)
BACKENDS = ("local", "lexical", "dense", "index")
LANES = ("dense", "sparse", "rerank", "filter")
FUSIONS = ("rrf", "linear")
RERANK_METHODS = ("mmr", "cross_encoder")
# Matches the embedding metric vocabulary the memory surface accepts, so a vector
# indexed through one path is searched with the same metric name through the other.
METRICS = ("cosine", "l2", "ip")

# A verb may only run on a backend that can produce its lane. Enforced here rather
# than left to the engine: the caller's arguments are still in scope, so the message
# can say which backends WOULD serve this verb instead of only that this one did not.
#
# The table is what the installed kernels and engines can actually do, not an
# aspiration. `local` fuses and reranks — those are the compiled retrieval kernels —
# and it has NEITHER a dense nor a sparse lane of its own, because both need an index
# and this module contains no index by design. A lane needs a built collection.
_VERB_BACKENDS: dict[str, tuple[str, ...]] = {
    # A vector lane needs a nearest-neighbour index over stored vectors. There is no
    # local dense lane: ranking a corpus supplied per request would need an index built
    # per request, which is the index engine's job and is not duplicated here.
    "vector_search": ("dense", "index"),
    # The sparse lane belongs to the index engine, which owns tokenization and the
    # postings list. There is deliberately no local sparse lane either: a second
    # tokenizer would score the same query differently from the one that built the
    # index, and the two sets of scores would not be comparable.
    "sparse_search": ("lexical", "index"),
    # Fusion and reranking take lane results as INPUT, so they need no index — which is
    # exactly why they are the two the local kernels serve.
    "hybrid_search": ("local", "index"),
    "rerank": ("local", "index"),
    "filtered_search": ("lexical", "dense", "index"),
    # Reporting only. It reads a result it was handed and dispatches nothing, so it
    # is available whatever served the search.
    "provenance": BACKENDS,
    # A store that does not outlive the call is not a memory, so the ephemeral
    # backends cannot serve these three at all.
    "remember": ("index",),
    "recall": ("index",),
    "compact": ("index",),
}

# Which backend serves which rerank method, for the same reason: the compiled kernels
# implement the diversity reranker, and a cross-encoder needs a model the local runtime
# does not carry.
_RERANK_METHOD_BACKENDS: dict[str, tuple[str, ...]] = {
    "mmr": ("local", "index"),
    "cross_encoder": ("index",),
}

# ── the kernels this module calls ─────────────────────────────────────────────
# Flat lists in, a struct out — the shape that reaches the runtime contract without a
# new message type. Read from `mojo/engine/retrieval/`, not guessed: the fusion driver
# takes every lane's ranking CONCATENATED plus each lane's length, because ranks are
# derived from position (a caller-supplied rank that disagrees with the list order is a
# wrong answer no validation could catch). A module or function absent from the
# installed shard is reported as an unavailable backend naming exactly what is missing,
# never as an empty result.
_KERNEL_SCORE = "retrieval.score"
_KERNEL_FUSE = "retrieval.fuse"
_KERNEL_RRF_FUSE = "rrf_fuse_flat"
_KERNEL_RRF_PROVENANCE = "rrf_provenance_flat"
_KERNEL_HYBRID_RANK = "hybrid_rank_flat"
_KERNEL_MMR_SELECT = "mmr_select_flat"
_KERNEL_CEILINGS = "retrieval_ceiling_report"
_KERNEL_STATUS_NAME = "retrieval_status_name"

# The kernels' success status. It is 200, not 0 — the retrieval package allocated its
# own status range, and treating 0 as success would read every rejection as an answer.
# `tests/test_algenta_retrieval.py` asserts this against the kernel source, because a
# constant copied across the language boundary is exactly the kind that drifts.
_KERNEL_STATUS_OK = 200

# ── client-side bounds ───────────────────────────────────────────────────────
# Every integer this module puts on the wire is bounded, and each bound is far below
# the 2^63 the engine's JSON reader wraps at — so the "an out-of-range integer arrives
# as a different, plausible number" hazard the query builder has to guard against is
# unreachable here, by construction rather than by a check.
#
# The bounds the KERNELS enforce are not restated here. They are read from the kernel
# itself through `retrieval_ceiling_report`, because a limit copied into Python drifts
# from the limit that is actually applied, and then a request this module accepted is
# rejected downstream with a number nobody can trace. The bounds below are the ones the
# kernels have no opinion about, because the payload never reaches them:
MAX_TOP_K = 1024
MAX_DIMENSION = 4_096
MAX_DOCUMENTS = 65_536
MAX_DOCUMENT_CHARS = 1 << 20
# The governed collection's own result ceiling, matching the hosted memory surface
# exactly. Two different caps for one field would mean a request this builder accepts
# and that surface rejects.
MAX_RECALL_TOP_K = 128
MAX_COMPACT_CANDIDATES = 1_000_000


# ── errors ────────────────────────────────────────────────────────────────────
class RetrievalError(RuntimeError):
    """A retrieval request was rejected, or a lane failed.

    `code` is the failure's stable name and `lane` names which lane it concerns when
    the failure belongs to one — the same division the query builder makes with
    `op_index`, for the same reason: a multi-lane request that failed needs to say
    which part of itself failed.

    A failed request returns NO result. There is no partial answer, because a partial
    ranking is indistinguishable from a complete one once it is in a list.
    """

    def __init__(self, code: str, message: str, lane: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.lane = lane


class RetrievalBackendUnavailableError(RetrievalError):
    """A backend was requested and is not present.

    `backend` is what was asked for and `missing` names the dependencies that are not
    installed — an import name, or the kernel module and function the installed
    runtime shard does not carry. Both are actionable; "unavailable" on its own is not.

    This is raised instead of returning an empty result on purpose. An empty result
    means the backend ran and nothing matched, which is a real answer and a completely
    different thing to plan around.
    """

    def __init__(
        self,
        *,
        backend: str,
        missing: Sequence[str],
        verb: str | None = None,
        detail: str = "",
    ) -> None:
        names = tuple(str(name) for name in missing if str(name))
        listed = ", ".join(names) if names else "an unnamed dependency"
        scope = f" for {verb}" if verb else ""
        message = (
            f"the {backend!r} retrieval backend{scope} is not available: {listed} "
            f"{'are' if len(names) != 1 else 'is'} missing. This is raised rather than "
            "returned as an empty result, because an empty result means the backend ran "
            "and nothing matched."
        )
        if detail:
            message = f"{message} {detail}"
        super().__init__("retrieval_backend_unavailable", message)
        self.backend = backend
        self.missing = names
        self.verb = verb


# ── backend availability ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class BackendStatus:
    """Whether a backend can serve a call, and what is missing if it cannot.

    `available` is `None` — not `False` — when the answer is not knowable from here:
    the `local` backend's kernels live in the installed runtime shard, so without a
    runtime to ask there is no answer, and reporting one would be inventing it.
    """

    backend: str
    available: bool | None
    missing: tuple[str, ...] = ()
    detail: str = ""


# What each backend needs, in the form an operator can act on. The import names are
# the retrieval engine's own module paths; the local backend needs the compiled
# retrieval kernels in whichever shard is installed on this device.
_BACKEND_IMPORTS: dict[str, tuple[str, ...]] = {
    "lexical": ("memengine.lexical",),
    "dense": ("memengine.vectorcore",),
    "index": ("memengine.runtime",),
}

# Entry points a backend's module must expose before it can serve anything. An import
# alone is not enough: `memengine.runtime` can import and still carry none of the
# governed collection's verbs, and `_index_entrypoint` in the execution half already
# refuses that case by name. Probing only the import made `backend_status` answer
# `available=True` for a backend every one of its calls then rejected -- a status that
# disagrees with behaviour is worse than no status, because a caller acts on it.
_BACKEND_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    "index": ("remember", "recall", "compact"),
}


def _probe_import(module_name: str) -> tuple[bool, str]:
    """Import a module and report the name of whatever was missing if it failed.

    An actual import, not a spec lookup: a module file can be present and still fail
    to import because a native dependency of its own is absent, and `ImportError.name`
    is then the name worth reporting — the dependency the operator has to install,
    rather than the module that could not find it.

    Deliberately not cached. A negative result stops being true the moment someone
    installs the dependency, and a cache would keep reporting a fixed deployment as
    broken for the life of the process.
    """
    try:
        importlib.import_module(module_name)
    except ImportError as exc:
        return False, str(getattr(exc, "name", "") or module_name)
    except Exception as exc:  # noqa: BLE001 — an engine that fails to initialise is
        # unavailable in exactly the way that matters, and the reason belongs in the
        # message rather than as a traceback from an import this module chose to try.
        return False, f"{module_name} ({type(exc).__name__}: {exc})"
    return True, ""


def backend_status(backend: str, runtime: Any = None) -> BackendStatus:
    """Report whether `backend` can serve a call right now.

    Pass a local runtime to resolve the `local` backend; without one its kernels
    cannot be looked up and `available` is `None`.
    """
    _require_known_backend(backend)
    if backend == "local":
        if runtime is None:
            return BackendStatus(
                backend="local",
                available=None,
                missing=(),
                detail=(
                    "pass a local runtime to resolve this backend; the retrieval "
                    "kernels live in the installed runtime shard"
                ),
            )
        _require_local_runtime(runtime)
        # Probed with the kernels' own ceiling report: it takes no arguments, so the
        # probe cannot be mistaken for a request, and a success is the same call the
        # bounds are read from rather than a second one.
        envelope = runtime.execute(_KERNEL_SCORE, _KERNEL_CEILINGS, [])
        code = _envelope_error_code(envelope)
        if code in _MISSING_KERNEL_CODES:
            return BackendStatus(
                backend="local",
                available=False,
                missing=(f"{_KERNEL_SCORE}.{_KERNEL_CEILINGS}",),
                detail=_envelope_error_message(envelope),
            )
        if code:
            return BackendStatus(
                backend="local",
                available=False,
                missing=(f"{_KERNEL_SCORE}.{_KERNEL_CEILINGS}",),
                detail=f"the retrieval kernels are registered but failed to answer: {code}",
            )
        return BackendStatus(backend="local", available=True)

    missing: list[str] = []
    details: list[str] = []
    for module_name in _BACKEND_IMPORTS[backend]:
        ok, name = _probe_import(module_name)
        if not ok:
            missing.append(name)
            details.append(f"{module_name} could not be imported")
            continue
        # The import succeeded, so the module object is already in sys.modules and this
        # cannot fail or cost anything; ask it for the entry points its verbs call.
        module = importlib.import_module(module_name)
        for entrypoint in _BACKEND_ENTRYPOINTS.get(backend, ()):
            if not callable(getattr(module, entrypoint, None)):
                missing.append(f"{module_name}.{entrypoint}")
                details.append(
                    f"{module_name} imports but does not expose {entrypoint}()"
                )
    if missing:
        return BackendStatus(
            backend=backend,
            available=False,
            missing=tuple(dict.fromkeys(missing)),
            detail="; ".join(details),
        )
    return BackendStatus(backend=backend, available=True)


def _require_backend(backend: str, verb: str, runtime: Any = None) -> None:
    """Raise if `backend` cannot serve `verb`. Never returns a degraded backend."""
    status = backend_status(backend, runtime)
    if status.available is False:
        raise RetrievalBackendUnavailableError(
            backend=backend,
            missing=status.missing,
            verb=verb,
            detail=status.detail,
        )


_MISSING_KERNEL_CODES = frozenset(
    {"module_not_registered", "function_not_registered", "compute_runtime_unavailable"}
)


# ── runtime seam ─────────────────────────────────────────────────────────────
def _require_local_runtime(runtime: Any) -> None:
    """Accept only an in-process runtime.

    Retrieval is compute, not a call to somebody else's compute. A runtime carrying a
    base URL or an API key is a client for a remote service, and using one here would
    move the ranking off this device without the caller having asked for that — so it
    is refused by name rather than accepted and quietly routed.
    """
    if not callable(getattr(runtime, "execute", None)):
        raise RetrievalError(
            "retrieval_requires_local_runtime",
            "retrieval needs a local runtime with an execute() method; got "
            f"{type(runtime).__name__}. Build one with MojoRuntime(mode='local').",
        )
    config = getattr(runtime, "_runtime_config", None)
    if isinstance(config, Mapping):
        mode = config.get("mode")
        if mode != "local":
            raise RetrievalError(
                "retrieval_requires_local_runtime",
                f"retrieval runs in this process only; the runtime is in {mode!r} mode",
            )
    for attribute in ("base_url", "_base_url", "api_key", "_api_key"):
        if getattr(runtime, attribute, None):
            raise RetrievalError(
                "retrieval_requires_local_runtime",
                f"retrieval runs in this process only; this runtime carries a "
                f"{attribute.lstrip('_')}, which means it is a client for a remote "
                "service. Use MojoRuntime(mode='local').",
            )


def _envelope_error_code(envelope: Any) -> str:
    if not isinstance(envelope, Mapping):
        return "runtime_execution_failed"
    if envelope.get("success") is True:
        return ""
    code = envelope.get("error_code")
    if isinstance(code, str) and code:
        return code
    error = envelope.get("error")
    return "runtime_execution_failed" if error else ""


def _envelope_error_message(envelope: Any) -> str:
    if not isinstance(envelope, Mapping):
        return "the local runtime returned a malformed envelope"
    message = envelope.get("error")
    return str(message) if message else ""




# ── inputs ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RetrievalDocument:
    """A document for the lexical lane: an id, its text, and optional metadata.

    Text rather than tokens, because tokenization belongs to the index engine. A
    tokenizer here would be a second, drifting definition of what a term is, and the
    scores it produced would not be comparable with the index's own.
    """

    id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalCandidate:
    """An item to rerank: an id, its existing relevance score, its text and metadata.

    No vector. A reranker measures redundancy BETWEEN candidates, and the pairwise
    similarity that measures it is supplied as a matrix — computing it from vectors here
    would put a second definition of similarity beside the one that produced the
    relevance scores in the first place.

    `score` is required where the verb reranks by relevance, and each verb says so
    rather than defaulting it. A score defaulted to zero still ranks, and ranks
    plausibly, which is the worst way for a missing input to behave.
    """

    id: str
    score: float | None = None
    text: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalFilter:
    """A restriction on which items a search may return.

    `where` matches metadata by equality, and an item that does not carry the key does
    NOT match — absence is not a value, so it cannot satisfy an equality, exactly as a
    predicate over a missing cell does not pass a columnar filter.

    `include_ids` and `exclude_ids` are checked against each other at construction:
    an id in both is a contradiction, not a precedence question, so it is rejected
    rather than resolved by whichever check happens to run first.
    """

    where: Mapping[str, Any] = field(default_factory=dict)
    include_ids: tuple[str, ...] | None = None
    exclude_ids: tuple[str, ...] | None = None
    min_score: float | None = None
    max_score: float | None = None

    def __post_init__(self) -> None:
        for name in ("include_ids", "exclude_ids"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, str) or not isinstance(value, (list, tuple)):
                raise RetrievalError(
                    "invalid_arguments",
                    f"{name} must be a list or tuple of ids, not "
                    f"{type(value).__name__}",
                )
            ids = tuple(str(item) for item in value)
            if not ids:
                raise RetrievalError(
                    "invalid_arguments",
                    f"{name} is empty; an empty include list admits nothing and an "
                    "empty exclude list restricts nothing — omit it instead, so the "
                    "filter says what it means",
                )
            if len(set(ids)) != len(ids):
                duplicates = sorted({item for item in ids if ids.count(item) > 1})
                raise RetrievalError(
                    "invalid_arguments",
                    f"{name} repeats {', '.join(duplicates)}; a repeated id changes "
                    "nothing and usually means a different id was intended",
                )
            object.__setattr__(self, name, ids)
        if self.include_ids and self.exclude_ids:
            both = sorted(set(self.include_ids) & set(self.exclude_ids))
            if both:
                raise RetrievalError(
                    "invalid_arguments",
                    f"{', '.join(both)} appears in both include_ids and exclude_ids; "
                    "the filter contradicts itself and would admit nothing",
                )
        for name in ("min_score", "max_score"):
            value = getattr(self, name)
            if value is None:
                continue
            object.__setattr__(self, name, _finite_float(value, name))
        if (
            self.min_score is not None
            and self.max_score is not None
            and self.min_score > self.max_score
        ):
            raise RetrievalError(
                "invalid_arguments",
                f"min_score {self.min_score} is above max_score {self.max_score}; "
                "the window is empty, so the filter admits nothing",
            )
        if not isinstance(self.where, Mapping):
            raise RetrievalError(
                "invalid_arguments",
                f"where must be a mapping of metadata key to value, not "
                f"{type(self.where).__name__}",
            )

    def keeps(self, item_id: str, metadata: Mapping[str, Any]) -> bool:
        """Whether this filter admits an item, by id and metadata alone.

        Only the parts a kernel cannot do: string ids and dictionary keys. The score
        window is NOT applied here — it goes to the kernel with the scores, so the
        numeric comparison happens once, in the place that owns the numbers.
        """
        if self.include_ids is not None and item_id not in self.include_ids:
            return False
        if self.exclude_ids is not None and item_id in self.exclude_ids:
            return False
        for key, expected in self.where.items():
            if key not in metadata:
                return False
            if metadata[key] != expected:
                return False
        return True


# ── outputs ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RetrievalLaneContribution:
    """What one lane contributed to one item.

    `rank` is 1-based within that lane and `None` when the lane did not return the
    item at all. `None` rather than 0 or a large sentinel, because a lane that never
    saw an item has no rank for it, and any number put there would be compared
    against the ranks that are real.

    For a governed recall, `lane` may name a score term the engine reported
    (`dense_similarity`, `recency_decay`, ...) rather than a retrieval lane; the term
    then carries its value in `score` and no rank, because a term is not an ordering.
    """

    lane: str
    backend: str
    rank: int | None = None
    score: float | None = None
    # What this lane's placement added to the final score, when the kernel that fused
    # them reported it. Never computed here: a contribution worked out in Python would
    # be a second arithmetic beside the one that produced the ordering, and the two
    # would eventually disagree in a way only the explanation would show.
    contribution: float | None = None

    def describe(self) -> str:
        parts = [f"{self.lane} lane (backend={self.backend})"]
        if self.rank is None:
            parts.append("not returned by this lane")
        else:
            parts.append(f"rank {self.rank}")
        if self.score is not None:
            parts.append(f"score {self.score:.6g}")
        if self.contribution is not None:
            parts.append(f"contributing {self.contribution:.6g}")
        return " ".join(parts[:1]) + " " + ", ".join(parts[1:])


@dataclass(frozen=True)
class RetrievalHit:
    """One ranked item: where it landed, what it scored, and which lanes put it there."""

    rank: int
    id: str
    score: float
    backend: str
    lanes: tuple[RetrievalLaneContribution, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    text: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    """A ranking, plus everything needed to explain it.

    `score_model` identifies what produced the ordering — a kernel and function, or
    the index engine's scorer and its parameters. Two results with different
    `score_model` values are not comparable, and a caller that stores scores needs to
    know that before it compares them next week.

    An empty `hits` is a real answer: the backend ran and nothing matched. A backend
    that was not there raised instead, so this is never ambiguous.
    """

    verb: str
    backend: str
    lanes: tuple[str, ...]
    hits: tuple[RetrievalHit, ...]
    top_k: int
    score_model: str
    fusion: str | None = None
    fusion_params: Mapping[str, Any] = field(default_factory=dict)
    collection: str | None = None
    latency_ms: float = 0.0
    # The fusing kernel's own certificate that the reported per-lane contributions add
    # back up to the scores: the largest per-item relative discrepancy. `None` means the
    # backend reported none — absent, not zero, because "no certificate" and "a perfect
    # certificate" are the two things a caller most needs to tell apart.
    attribution_residual: float | None = None

    def __len__(self) -> int:
        return len(self.hits)

    def ids(self) -> list[str]:
        """The ranked ids, in rank order."""
        return [hit.id for hit in self.hits]

    def provenance(self) -> RetrievalProvenance:
        """The provenance report for this result. Same as `provenance(result)`."""
        return provenance(self)


@dataclass(frozen=True)
class RetrievalProvenanceItem:
    """Why one item is where it is."""

    rank: int
    id: str
    score: float
    backend: str
    contributions: tuple[RetrievalLaneContribution, ...]
    explanation: str


@dataclass(frozen=True)
class RetrievalProvenance:
    """Per-item provenance for a whole result.

    The question this exists to answer is "why did this rank first", and the answer
    needs four things: which lanes contributed, at what rank and score in each, which
    backend served each lane, and what combined them. All four are here, and
    `explanation` states them as a sentence so an answer can be shown to somebody who
    is not going to read any source.
    """

    verb: str
    backend: str
    score_model: str
    fusion: str | None
    fusion_params: Mapping[str, Any]
    items: tuple[RetrievalProvenanceItem, ...]
    collection: str | None = None
    attribution_residual: float | None = None

    def why(self, item_id: str) -> str:
        """The explanation for one id. Raises if the result does not contain it."""
        for item in self.items:
            if item.id == item_id:
                return item.explanation
        known = ", ".join(item.id for item in self.items) or "nothing"
        raise KeyError(f"{item_id!r} is not in this result; it ranked {known}")


@dataclass(frozen=True)
class RememberReceipt:
    """What the governed collection stored, mirroring the memory surface's response.

    `status` is `created` or `existing`: a repeated `remember` of identical content is
    the same episode, not a second one, and the receipt says which happened rather
    than leaving a caller to infer it from a count.
    """

    collection: str
    episode_id: str
    content_hash: str
    status: str
    ingested_at: str
    observed_at: str
    extracted_fact_ids: tuple[str, ...] = ()
    extracted_entity_ids: tuple[str, ...] = ()
    embedding_model_id: str | None = None
    embedding_model_version: str | None = None
    backend: str = "index"


@dataclass(frozen=True)
class CompactionReport:
    """What a compaction changed, mirroring the memory surface's response.

    Every field is a count of something that happened. A compaction that did nothing
    reports zeros, which is a real answer — nothing needed consolidating.
    """

    collection: str
    created_at: str
    policy: str | None = None
    candidates_considered: int = 0
    facts_deduped: int = 0
    facts_superseded: int = 0
    contradictions_resolved: int = 0
    summaries_created: int = 0
    entities_merged: int = 0
    summary_ids: tuple[str, ...] = ()
    backend: str = "index"


# ── validation helpers ───────────────────────────────────────────────────────
def _english(values: Sequence[str]) -> str:
    """Join names as `a, b or c` — the phrasing the query builder uses."""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " or " + values[-1]


def _require_known_backend(backend: Any) -> str:
    if not isinstance(backend, str) or backend not in BACKENDS:
        raise RetrievalError(
            "unknown_backend",
            f"unknown backend {backend!r}; accepted: {_english(BACKENDS)}",
        )
    return backend


def _require_backend_for_verb(verb: str, backend: Any) -> str:
    _require_known_backend(backend)
    allowed = _VERB_BACKENDS[verb]
    if backend not in allowed:
        raise RetrievalError(
            "backend_cannot_serve_verb",
            f"the {backend!r} backend cannot serve {verb}; it is served by "
            f"{_english(allowed)}",
        )
    return str(backend)


def _finite_float(value: Any, label: str, lane: str | None = None) -> float:
    """A real number, or a rejection.

    NaN and infinity are rejected before anything compares against them. A NaN in a
    score makes every threshold comparison false, so a request carrying one passes
    each guard on the way in and produces a ranking nobody can explain.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RetrievalError(
            "invalid_arguments", f"{label} must be a number; got {value!r}", lane
        )
    number = float(value)
    if not math.isfinite(number):
        raise RetrievalError(
            "invalid_arguments",
            f"{label} must be finite; got {number}. A non-finite value defeats every "
            "threshold it is compared against silently.",
            lane,
        )
    return number


def _bounded_float(
    value: Any, label: str, low: float, high: float, lane: str | None = None
) -> float:
    number = _finite_float(value, label, lane)
    if number < low or number > high:
        raise RetrievalError(
            "invalid_arguments",
            f"{label} must be within {low}..{high}; got {number}",
            lane,
        )
    return number


def _bounded_int(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RetrievalError(
            "invalid_arguments", f"{label} must be an integer; got {value!r}"
        )
    if value < low or value > high:
        raise RetrievalError(
            "invalid_arguments", f"{label} must be within {low}..{high}; got {value}"
        )
    return value


def _require_query_text(query: Any) -> str:
    if not isinstance(query, str):
        raise RetrievalError(
            "invalid_arguments", f"query must be a string; got {type(query).__name__}"
        )
    text = query.strip()
    if not text:
        raise RetrievalError(
            "invalid_arguments",
            "query is empty; an empty query has no terms, so a ranking over it would "
            "be an ordering of the corpus rather than an answer",
        )
    return query


def _bm25_params(k1: Any, b: Any) -> dict[str, float]:
    """The lexical index's own BM25 parameters, validated once.

    One definition, shared by `sparse_search` and `filtered_search`. A check written
    twice becomes two checks at two strengths, and the weaker one is then a bug that
    only fires on whichever call site happens to use it.

    `k1` is non-negative and `b` is a fraction of the length normalisation; outside
    those ranges the formula is not BM25 and its scores do not mean what the name says.
    """
    return {
        "k1": _bounded_float(k1, "k1", 0.0, 1000.0, "sparse"),
        "b": _bounded_float(b, "b", 0.0, 1.0, "sparse"),
    }


def _require_metric(metric: Any) -> str:
    if metric not in METRICS:
        raise RetrievalError(
            "invalid_arguments",
            f"unknown metric {metric!r}; accepted: {_english(METRICS)}",
        )
    return str(metric)


def _require_collection(collection: Any) -> str:
    if not isinstance(collection, str) or not collection.strip():
        raise RetrievalError(
            "invalid_arguments", "collection must be a non-empty name"
        )
    return collection


def _require_exactly_one(verb: str, **options: Any) -> str:
    """Exactly one of a set of mutually exclusive inputs. Names both failure modes.

    Two sources means the engine decides which one is authoritative; none means it
    has nothing to read. The query builder rejects `rows` with `dataset` for the
    first reason, and this is the same rule.
    """
    supplied = [name for name, value in options.items() if value is not None]
    names = _english(sorted(options))
    if len(supplied) > 1:
        raise RetrievalError(
            "invalid_arguments",
            f"{verb} takes exactly one of {names}; {' and '.join(sorted(supplied))} "
            "were both given, which leaves which one is authoritative up to the engine",
        )
    if not supplied:
        raise RetrievalError(
            "invalid_arguments",
            f"{verb} needs one of {names}; without one there is nothing to search",
        )
    return supplied[0]


def _normalize_documents(documents: Any) -> tuple[RetrievalDocument, ...]:
    if isinstance(documents, (str, bytes)) or not isinstance(
        documents, (list, tuple)
    ):
        raise RetrievalError(
            "invalid_arguments",
            f"documents must be a list of RetrievalDocument; got "
            f"{type(documents).__name__}",
        )
    if not documents:
        raise RetrievalError(
            "invalid_arguments",
            "documents is empty; there is nothing to index, which is a different "
            "thing from a query that matched nothing",
        )
    if len(documents) > MAX_DOCUMENTS:
        raise RetrievalError(
            "invalid_arguments",
            f"documents holds {len(documents)} items; at most {MAX_DOCUMENTS} may be "
            "indexed in one request",
        )
    out: list[RetrievalDocument] = []
    seen: set[str] = set()
    for index, entry in enumerate(documents):
        if isinstance(entry, Mapping):
            entry = RetrievalDocument(
                id=str(entry.get("id", "")),
                text=str(entry.get("text", "")),
                metadata=entry.get("metadata") or {},
            )
        if not isinstance(entry, RetrievalDocument):
            raise RetrievalError(
                "invalid_arguments",
                f"documents[{index}] is {type(entry).__name__}, not a "
                "RetrievalDocument",
            )
        if not entry.id:
            raise RetrievalError(
                "invalid_arguments",
                f"documents[{index}] has an empty id; ids are what a result is "
                "reported against",
            )
        if entry.id in seen:
            raise RetrievalError(
                "invalid_arguments",
                f"documents[{index}] repeats id {entry.id!r}; one id must denote one "
                "document, or a hit cannot be traced back to its source",
            )
        if not isinstance(entry.text, str) or not entry.text:
            raise RetrievalError(
                "invalid_arguments",
                f"documents[{index}] ({entry.id!r}) has no text; an empty document "
                "cannot match a term",
            )
        if len(entry.text) > MAX_DOCUMENT_CHARS:
            raise RetrievalError(
                "invalid_arguments",
                f"documents[{index}] ({entry.id!r}) is {len(entry.text)} characters; "
                f"at most {MAX_DOCUMENT_CHARS} per document",
            )
        seen.add(entry.id)
        out.append(entry)
    return tuple(out)


def _normalize_candidates(
    candidates: Any,
    *,
    verb: str,
    need_score: bool,
) -> tuple[RetrievalCandidate, ...]:
    """The candidates a rerank will reorder, checked and normalised once.

    No count ceiling is applied here. The kernels publish their own, and it is read from
    them before the payload is sent (`retrieval_ceiling_report`) — a second ceiling in
    Python would be the same limit at two strengths, and the weaker one would be a bug
    even on the days it never fires.
    """
    if isinstance(candidates, (str, bytes)) or not isinstance(
        candidates, (list, tuple)
    ):
        raise RetrievalError(
            "invalid_arguments",
            f"candidates must be a list of RetrievalCandidate; got "
            f"{type(candidates).__name__}",
        )
    if not candidates:
        raise RetrievalError(
            "invalid_arguments",
            f"{verb} was given no candidates; there is nothing to rank, which is a "
            "different thing from a query that matched nothing",
        )
    out: list[RetrievalCandidate] = []
    seen: set[str] = set()
    for index, entry in enumerate(candidates):
        if isinstance(entry, Mapping):
            entry = RetrievalCandidate(
                id=str(entry.get("id", "")),
                score=entry.get("score"),
                text=entry.get("text"),
                metadata=entry.get("metadata") or {},
            )
        if not isinstance(entry, RetrievalCandidate):
            raise RetrievalError(
                "invalid_arguments",
                f"candidates[{index}] is {type(entry).__name__}, not a "
                "RetrievalCandidate",
            )
        if not entry.id:
            raise RetrievalError(
                "invalid_arguments",
                f"candidates[{index}] has an empty id; ids are what a result is "
                "reported against",
            )
        if entry.id in seen:
            raise RetrievalError(
                "invalid_arguments",
                f"candidates[{index}] repeats id {entry.id!r}; one id must denote one "
                "item, or a rank cannot be traced back to it",
            )
        seen.add(entry.id)
        if need_score:
            if entry.score is None:
                raise RetrievalError(
                    "invalid_arguments",
                    f"candidates[{index}] ({entry.id!r}) has no score, and {verb} "
                    "needs one per item. An absent score is not a zero score.",
                )
            entry = replace(
                entry,
                score=_finite_float(entry.score, f"candidates[{index}].score"),
            )
        out.append(entry)
    return tuple(out)


def _normalize_query_vector(query_vector: Any, metric: str) -> tuple[float, ...]:
    if isinstance(query_vector, (str, bytes)) or not isinstance(
        query_vector, (list, tuple)
    ):
        raise RetrievalError(
            "invalid_arguments",
            f"query_vector must be a list of numbers; got "
            f"{type(query_vector).__name__}",
        )
    if not query_vector:
        raise RetrievalError(
            "invalid_arguments",
            "query_vector is empty; there is no direction to search in",
        )
    if len(query_vector) > MAX_DIMENSION:
        raise RetrievalError(
            "invalid_arguments",
            f"query_vector has {len(query_vector)} dimensions; at most "
            f"{MAX_DIMENSION}",
        )
    vector = tuple(
        _finite_float(value, f"query_vector[{index}]")
        for index, value in enumerate(query_vector)
    )
    if metric == "cosine" and not any(value != 0.0 for value in vector):
        raise RetrievalError(
            "invalid_arguments",
            "query_vector is all zeros and the metric is cosine, which divides by its "
            "norm; there is no similarity to a zero vector, so no ranking exists",
        )
    return vector


def _normalize_filter(value: Any) -> RetrievalFilter | None:
    if value is None:
        return None
    if isinstance(value, RetrievalFilter):
        return value
    if isinstance(value, Mapping):
        # Constructed through RetrievalFilter so a dict and a RetrievalFilter go
        # through one definition of a valid filter rather than two.
        return RetrievalFilter(**dict(value))
    raise RetrievalError(
        "invalid_arguments",
        f"filter must be a RetrievalFilter or a mapping; got {type(value).__name__}",
    )


def _lane_pairs(value: Any, label: str) -> tuple[tuple[str, float], ...]:
    """A lane's result as `((id, score), ...)`, from a result or from pairs.

    Accepts a `RetrievalResult` so the output of one verb feeds the next without a
    conversion step, and raw pairs so a lane served elsewhere can be fused here.

    An EMPTY lane is accepted and returned empty. It means the lane ran and matched
    nothing, which is a real retrieval answer: rank fusion contributes no term for a
    lane that did not rank an item, so an empty lane fuses correctly and is reported as
    empty rather than mistaken for a lane that never ran. A lane that never ran is
    `None`, and `hybrid_search` refuses that.
    """
    if isinstance(value, RetrievalResult):
        return tuple((hit.id, hit.score) for hit in value.hits)
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise RetrievalError(
            "invalid_arguments",
            f"{label} must be a RetrievalResult or a list of (id, score) pairs; got "
            f"{type(value).__name__}",
        )
    out: list[tuple[str, float]] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        if isinstance(entry, RetrievalHit):
            item_id, score = entry.id, entry.score
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            item_id, score = entry[0], entry[1]
        else:
            raise RetrievalError(
                "invalid_arguments",
                f"{label}[{index}] is not an (id, score) pair",
            )
        item_id = str(item_id)
        if not item_id:
            raise RetrievalError(
                "invalid_arguments", f"{label}[{index}] has an empty id"
            )
        if item_id in seen:
            raise RetrievalError(
                "invalid_arguments",
                f"{label}[{index}] repeats id {item_id!r}; one lane ranks an item "
                "once, so a repeat means two lanes were concatenated by mistake",
            )
        seen.add(item_id)
        out.append((item_id, _finite_float(score, f"{label}[{index}] score")))
    return tuple(out)


def _normalize_lanes(
    dense: Any, sparse: Any, lanes: Any, fusion: str
) -> tuple[tuple[str, tuple[tuple[str, float], ...]], ...]:
    """The lanes to fuse, as `((name, ((id, score), ...)), ...)` in a fixed order.

    Ordered, not a dict: the fusion kernel folds lane terms in ascending lane order and
    floating-point addition is not associative, so the order of the lanes is part of the
    answer. A mapping's insertion order is preserved here deliberately, and the order the
    caller wrote is the order that is fused.

    `dense=`/`sparse=` and `lanes=` are the same request written two ways, so supplying
    both is refused rather than merged — a merge would have to decide which spelling
    wins, and that decision belongs to nobody.

    Linear fusion additionally requires exactly the two named lanes with the SAME id set.
    Its kernel takes one dense score and one sparse score per candidate, with no notion of
    absence; filling a missing side with 0.0 would read as "this lane scored it, badly"
    rather than "this lane never saw it", and would silently halve the item's score.
    Unaligned lanes are what rank fusion is for, and the message says so.
    """
    if lanes is not None and (dense is not None or sparse is not None):
        raise RetrievalError(
            "invalid_arguments",
            "pass lanes=, or dense= and sparse=, not both; they are the same request "
            "written two ways and merging them would have to pick a winner",
            "fuse",
        )
    ordered: list[tuple[str, Any]] = []
    if lanes is not None:
        if not isinstance(lanes, Mapping):
            raise RetrievalError(
                "invalid_arguments",
                f"lanes must be a mapping of lane name to lane result; got "
                f"{type(lanes).__name__}",
                "fuse",
            )
        if len(lanes) < 2:
            raise RetrievalError(
                "invalid_arguments",
                f"lanes has {len(lanes)} entry; fusing one lane with nothing is that "
                "lane, so it would be a hybrid in name only",
                "fuse",
            )
        for name, value in lanes.items():
            if not isinstance(name, str) or not name.strip():
                raise RetrievalError(
                    "invalid_arguments",
                    "every lane needs a non-empty name; the name is what provenance "
                    "reports a contribution against",
                    "fuse",
                )
            ordered.append((name, value))
    else:
        if dense is None or sparse is None:
            absent = "sparse" if dense is not None else "dense"
            raise RetrievalError(
                "invalid_arguments",
                f"hybrid_search needs both lanes; {absent}= was not given. Fusing one "
                "lane with nothing is that lane, so it would be a hybrid in name only. "
                f"Pass {absent}=[] if that lane ran and matched nothing — an empty lane "
                "and an absent lane are different answers.",
                "fuse",
            )
        ordered.append(("dense", dense))
        ordered.append(("sparse", sparse))

    names = [name for name, _ in ordered]
    if len(set(names)) != len(names):
        raise RetrievalError(
            "invalid_arguments",
            "two lanes share a name; provenance reports a contribution per lane name, "
            "so the names must distinguish them",
            "fuse",
        )
    resolved = tuple((name, _lane_pairs(value, name)) for name, value in ordered)
    if fusion == "linear":
        if names != ["dense", "sparse"]:
            raise RetrievalError(
                "invalid_arguments",
                "linear fusion weights one dense score against one sparse score, so it "
                f"takes exactly the lanes 'dense' and 'sparse'; got {', '.join(names)}. "
                "Use fusion='rrf' to fuse any other set of lanes.",
                "fuse",
            )
        dense_ids = {item_id for item_id, _ in resolved[0][1]}
        sparse_ids = {item_id for item_id, _ in resolved[1][1]}
        if dense_ids != sparse_ids:
            only_dense = sorted(dense_ids - sparse_ids)[:5]
            only_sparse = sorted(sparse_ids - dense_ids)[:5]
            raise RetrievalError(
                "invalid_arguments",
                "linear fusion needs a score from BOTH lanes for every candidate, and "
                f"{len(dense_ids ^ sparse_ids)} are in only one lane"
                + (f" (dense only: {', '.join(only_dense)})" if only_dense else "")
                + (f" (sparse only: {', '.join(only_sparse)})" if only_sparse else "")
                + ". Filling the missing side with 0.0 would read as 'scored, badly' "
                "rather than 'never seen', and would halve the item's score. Use "
                "fusion='rrf', which is defined over lanes that disagree about which "
                "candidates exist.",
                "fuse",
            )
    return resolved


# ── the request ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RetrievalRequest:
    """A validated retrieval request: the verb, the backend, and the verb's inputs.

    Produced only by the verb functions and by `Retrieval`, both of which go through
    the same validation, so there is one definition of a valid request rather than a
    validated path and an unvalidated one. Everything in `params` has already been
    checked against what the named backend will accept, so a request that exists is a
    request the backend can be asked.
    """

    verb: str
    backend: str
    top_k: int
    params: Mapping[str, Any] = field(default_factory=dict)
    filter: RetrievalFilter | None = None
    collection: str | None = None

    def run(self, runtime: Any) -> RetrievalResult:
        """Execute on a local runtime."""
        return _run_request(runtime, self)


def _build_search_request(
    verb: str,
    *,
    backend: str,
    top_k: int,
    params: Mapping[str, Any],
    filter: RetrievalFilter | None = None,  # noqa: A002 — the caller's word for it
    collection: str | None = None,
) -> RetrievalRequest:
    backend = _require_backend_for_verb(verb, backend)
    limit = MAX_RECALL_TOP_K if verb == "recall" else MAX_TOP_K
    return RetrievalRequest(
        verb=verb,
        backend=backend,
        top_k=_bounded_int(top_k, "top_k", 1, limit),
        params=dict(params),
        filter=filter,
        collection=collection,
    )


# ── the six verbs ────────────────────────────────────────────────────────────
def vector_search(
    runtime: Any,
    *,
    query_vector: Sequence[float],
    collection: str,
    top_k: int = 10,
    backend: str = "dense",
    metric: str = "cosine",
) -> RetrievalResult:
    """Rank by vector similarity over a built collection.

    A vector lane needs a nearest-neighbour index, and an index is the retrieval
    engine's to build — this module contains none, by design. So `vector_search` names
    a `collection` and is served by `dense` or `index`; there is no candidates-in-the-
    request form, because ranking one would mean building an index per request.

    To rank vectors you already hold, fuse or rerank them: `hybrid_search` and `rerank`
    take lane results as input and are served by the local compiled kernels.

    Raises `RetrievalBackendUnavailableError` if the requested backend is not present.
    """
    # The backend's NAME is checked first, before any argument-shape rule that mentions
    # it: an unknown backend must be reported as unknown, not as one that cannot serve
    # the shape of the request.
    backend = _require_backend_for_verb("vector_search", backend)
    metric = _require_metric(metric)
    vector = _normalize_query_vector(query_vector, metric)
    request = _build_search_request(
        "vector_search",
        backend=backend,
        top_k=top_k,
        params={"query_vector": vector, "metric": metric},
        collection=_require_collection(collection),
    )
    return _run_request(runtime, request)


def sparse_search(
    runtime: Any,
    *,
    query: str,
    documents: Sequence[RetrievalDocument] | None = None,
    collection: str | None = None,
    top_k: int = 10,
    backend: str = "lexical",
    k1: float = 1.8,
    b: float = 1.0,
) -> RetrievalResult:
    """Rank by term overlap, scored by the index engine's lexical index.

    `k1` and `b` are the index's own BM25 parameters and are reported back in
    `score_model`, because two searches with different parameters produce scores that
    must not be compared.

    Raises `RetrievalBackendUnavailableError` if the lexical index is not installed.
    """
    backend = _require_backend_for_verb("sparse_search", backend)
    text = _require_query_text(query)
    source = _require_exactly_one(
        "sparse_search", documents=documents, collection=collection
    )
    if source == "documents" and backend != "lexical":
        raise RetrievalError(
            "backend_cannot_serve_verb",
            f"the {backend!r} backend searches a stored collection; documents supplied "
            "in the request are indexed by the 'lexical' backend",
        )
    if source == "collection" and backend == "lexical":
        raise RetrievalError(
            "backend_cannot_serve_verb",
            "the 'lexical' backend indexes the documents in this request and keeps "
            "nothing, so it takes documents= rather than collection=",
        )
    params: dict[str, Any] = {"query": text, **_bm25_params(k1, b)}
    if source == "documents":
        params["documents"] = _normalize_documents(documents)
    request = _build_search_request(
        "sparse_search",
        backend=backend,
        top_k=top_k,
        params=params,
        collection=_require_collection(collection) if collection else None,
    )
    return _run_request(runtime, request)


def hybrid_search(
    runtime: Any,
    *,
    dense: Any = None,
    sparse: Any = None,
    lanes: Mapping[str, Any] | None = None,
    query: str | None = None,
    collection: str | None = None,
    top_k: int = 10,
    backend: str = "local",
    fusion: str = "rrf",
    rrf_k: float | None = None,
    alpha: float | None = None,
    explain: bool = False,
) -> RetrievalResult:
    """Fuse ranked lanes into one ranking.

    `local` fuses lane results you already hold — from `sparse_search`,
    `vector_search`, or anywhere else — so the lanes may be served by different
    backends and provenance records which served which. `index` runs its own lanes over
    a stored collection.

    Two lanes are the common case and `dense=` / `sparse=` name them. `lanes=` takes a
    mapping of name to lane result for more than two, because rank fusion is defined
    over any number of ranked lists and a graph walk or a second index is a lane like
    any other. `dense=`/`sparse=` and `lanes=` are the same request written two ways,
    so passing both is refused.

    **An empty lane and an absent lane are different.** `dense=[]` says the dense lane
    ran and matched nothing, which is a real retrieval answer and fuses as one — the
    lane simply contributes no term. `dense=None` says the lane did not run, and a
    hybrid missing a lane is a hybrid in name only, so it is refused. A lane that could
    not run because its backend is missing must have raised before reaching here.

    `rrf` combines RANKS and takes `rrf_k`; `linear` combines SCORES and takes `alpha`,
    the DENSE weight. Passing the other one is rejected rather than ignored: a caller
    who set `alpha` and got rank fusion would have no way to see that their weight did
    nothing.

    `explain=True` asks for the full per-lane attribution table — which lane ranked each
    returned item, where, and what that placement contributed — computed by the same
    kernel path that produced the ranking, so the table and the order cannot disagree.
    """
    backend = _require_backend_for_verb("hybrid_search", backend)
    if fusion not in FUSIONS:
        raise RetrievalError(
            "invalid_arguments",
            f"unknown fusion {fusion!r}; accepted: {_english(FUSIONS)}",
        )
    if fusion == "rrf" and alpha is not None:
        raise RetrievalError(
            "invalid_arguments",
            "alpha is a weight on SCORES and rrf fuses RANKS, so alpha would be "
            "ignored; pass fusion='linear' to weight scores",
            "fuse",
        )
    if fusion == "linear" and rrf_k is not None:
        raise RetrievalError(
            "invalid_arguments",
            "rrf_k is the rank-fusion constant and linear fusion uses no ranks, so "
            "rrf_k would be ignored; pass fusion='rrf' to fuse ranks",
            "fuse",
        )
    params: dict[str, Any] = {"fusion": fusion, "explain": bool(explain)}
    if fusion == "rrf":
        # 60 is the constant the frozen RRF kernel is documented against. The admissible
        # range is exactly the kernel's: finite and non-negative. Ranks are 1-based, so
        # k = 0 is fine (k + rank >= 1), while at k = -1 the rank-1 term divides by zero
        # and no clamp can turn that into a score. One invariant, one strength.
        candidate_k = 60.0 if rrf_k is None else rrf_k
        params["rrf_k"] = _finite_float(candidate_k, "rrf_k", "fuse")
        if params["rrf_k"] < 0.0:
            raise RetrievalError(
                "invalid_arguments",
                f"rrf_k must be non-negative; got {params['rrf_k']}. At a negative k the "
                "rank-1 term divides by zero, so there is no score to return.",
                "fuse",
            )
    else:
        params["alpha"] = _bounded_float(
            0.5 if alpha is None else alpha, "alpha", 0.0, 1.0, "fuse"
        )

    supplied_lanes = dense is not None or sparse is not None or lanes is not None
    supplied_collection = query is not None or collection is not None
    if supplied_lanes and supplied_collection:
        raise RetrievalError(
            "invalid_arguments",
            "hybrid_search fuses either lane results (dense=/sparse=/lanes=) or its own "
            "lanes over a stored collection (query= and collection=), never both — with "
            "both, which pair is authoritative is left to the engine",
            "fuse",
        )
    if supplied_lanes:
        if backend != "local":
            raise RetrievalError(
                "backend_cannot_serve_verb",
                f"lane results are fused by the 'local' backend; {backend!r} runs its "
                "own lanes over a stored collection",
            )
        params["lanes"] = _normalize_lanes(dense, sparse, lanes, fusion)
    elif supplied_collection:
        if backend == "local":
            raise RetrievalError(
                "backend_cannot_serve_verb",
                "the 'local' backend has no stored collection; pass lane results "
                "instead",
            )
        if query is None or collection is None:
            missing = "collection" if query is not None else "query"
            raise RetrievalError(
                "invalid_arguments",
                f"searching a stored collection needs both query= and collection=; "
                f"{missing}= was not given",
                "fuse",
            )
        params["query"] = _require_query_text(query)
    else:
        raise RetrievalError(
            "invalid_arguments",
            "hybrid_search needs either lane results (dense=/sparse=/lanes=) or query= "
            "and collection=",
            "fuse",
        )
    request = _build_search_request(
        "hybrid_search",
        backend=backend,
        top_k=top_k,
        params=params,
        collection=_require_collection(collection) if collection else None,
    )
    return _run_request(runtime, request)


def rerank(
    runtime: Any,
    *,
    candidates: Sequence[RetrievalCandidate],
    similarity: Sequence[float] | None = None,
    top_k: int = 10,
    backend: str = "local",
    method: str = "mmr",
    lambda_mmr: float | None = None,
    bias: float | None = None,
) -> RetrievalResult:
    """Reorder a candidate set by a second criterion.

    `mmr` trades relevance against redundancy: it takes each candidate's existing
    relevance score and the candidate-to-candidate `similarity` matrix, flat and
    row-major, `similarity[i * n + j]` being sim(i, j). The matrix is supplied rather
    than derived, for the reason the rest of this module exists — deriving it would mean
    computing similarities here, in Python, alongside whichever engine computed the ones
    that produced the relevance scores. Only the `[candidate][selected]` direction is
    read, so an asymmetric matrix is used exactly as given.

    `cross_encoder` needs a model the local runtime does not carry, so it is served by
    the governed collection only. Asking for it locally is rejected by name rather than
    approximated with something cheaper.

    Passing the parameter belonging to the other method is rejected rather than ignored,
    for the same reason as in `hybrid_search`: a weight that silently does nothing is
    worse than a weight that is refused.
    """
    backend = _require_backend_for_verb("rerank", backend)
    if method not in RERANK_METHODS:
        raise RetrievalError(
            "invalid_arguments",
            f"unknown rerank method {method!r}; accepted: {_english(RERANK_METHODS)}",
        )
    serving = _RERANK_METHOD_BACKENDS[method]
    if backend not in serving:
        raise RetrievalError(
            "backend_cannot_serve_verb",
            f"the {backend!r} backend does not rerank with {method!r}; that method is "
            f"served by {_english(serving)}",
            "rerank",
        )
    if method == "cross_encoder" and lambda_mmr is not None:
        raise RetrievalError(
            "invalid_arguments",
            "lambda_mmr is the relevance/diversity tradeoff and a cross-encoder makes "
            "no diversity tradeoff, so it would be ignored; pass method='mmr'",
            "rerank",
        )
    if method == "mmr" and bias is not None:
        raise RetrievalError(
            "invalid_arguments",
            "bias is a cross-encoder term and mmr has none, so it would be ignored; "
            "pass method='cross_encoder'",
            "rerank",
        )
    params: dict[str, Any] = {"method": method}
    if method == "cross_encoder":
        params["bias"] = _finite_float(0.0 if bias is None else bias, "bias", "rerank")
        params["candidates"] = _normalize_candidates(
            candidates, verb="rerank", need_score=False
        )
        if similarity is not None:
            raise RetrievalError(
                "invalid_arguments",
                "a cross-encoder scores each candidate against the query and makes no "
                "candidate-to-candidate comparison, so similarity= has no role; omit it",
                "rerank",
            )
    else:
        params["lambda_mmr"] = _bounded_float(
            0.5 if lambda_mmr is None else lambda_mmr, "lambda_mmr", 0.0, 1.0, "rerank"
        )
        items = _normalize_candidates(
            candidates, verb="rerank", need_score=True
        )
        params["candidates"] = items
        params["similarity"] = _normalize_similarity(similarity, len(items))
    request = _build_search_request(
        "rerank", backend=backend, top_k=top_k, params=params
    )
    return _run_request(runtime, request)


def _normalize_similarity(similarity: Any, n: int) -> tuple[float, ...]:
    """The flat row-major `n x n` candidate-to-candidate matrix the reranker reads.

    The length is checked against `n` by DIVISION, not by comparing against `n * n`: the
    product of two large integers is not a bound on anything the kernel can rely on, and
    the whole point of checking here is that the caller's own numbers are still in scope.
    """
    if similarity is None:
        raise RetrievalError(
            "invalid_arguments",
            "mmr measures redundancy between candidates, so similarity= is required: "
            "the flat row-major n x n matrix, with similarity[i * n + j] = sim(i, j). It "
            "is not derived here, because computing it in Python would put a second "
            "definition of similarity beside the one that produced the relevance scores.",
            "rerank",
        )
    if isinstance(similarity, (str, bytes)) or not isinstance(
        similarity, (list, tuple)
    ):
        raise RetrievalError(
            "invalid_arguments",
            f"similarity must be a flat list of numbers; got "
            f"{type(similarity).__name__}",
            "rerank",
        )
    if n == 0 or len(similarity) // n != n or len(similarity) % n != 0:
        raise RetrievalError(
            "invalid_arguments",
            f"similarity holds {len(similarity)} values for {n} candidates; an n x n "
            f"matrix needs exactly {n} rows of {n}. A short matrix would shift every row "
            "after the gap and every redundancy penalty would be read from the wrong "
            "pair.",
            "rerank",
        )
    return tuple(
        _finite_float(value, f"similarity[{index}]", "rerank")
        for index, value in enumerate(similarity)
    )


def filtered_search(
    runtime: Any,
    *,
    lane: str,
    filter: RetrievalFilter | Mapping[str, Any],  # noqa: A002 — the caller's word
    query_vector: Sequence[float] | None = None,
    query: str | None = None,
    documents: Sequence[RetrievalDocument] | None = None,
    collection: str | None = None,
    top_k: int = 10,
    backend: str = "lexical",
    metric: str = "cosine",
    k1: float = 1.8,
    b: float = 1.0,
) -> RetrievalResult:
    """A lane search restricted to the items a filter admits.

    `lane` is `dense` or `sparse` and decides which backends can serve the call, so a
    filtered sparse search cannot be sent to a backend with no sparse lane. `metric`
    belongs to the dense lane and `k1`/`b` to the sparse one; each is validated by the
    same helper the unfiltered verb uses, so a filtered search cannot be scored under
    parameters an unfiltered one would have refused.

    The restriction is split where the capabilities are: ids and metadata keys are
    matched here, because the engines index content and not arbitrary dictionaries; the
    score window is applied to the lane's own scores, which is the only place a score
    exists.
    """
    backend = _require_backend_for_verb("filtered_search", backend)
    if lane not in ("dense", "sparse"):
        raise RetrievalError(
            "invalid_arguments",
            f"lane must be 'dense' or 'sparse'; got {lane!r}",
        )
    restriction = _normalize_filter(filter)
    if restriction is None:
        raise RetrievalError(
            "invalid_arguments",
            "filtered_search needs a filter; without one it is an ordinary search, "
            "and the two should not be the same call",
        )
    if lane == "dense" and backend == "lexical":
        raise RetrievalError(
            "backend_cannot_serve_verb",
            "the 'lexical' backend has no dense lane; it serves lane='sparse'",
        )
    if lane == "sparse" and backend == "dense":
        raise RetrievalError(
            "backend_cannot_serve_verb",
            "the 'dense' backend has no sparse lane; the sparse lane is served by "
            "'lexical' or 'index'",
        )
    params: dict[str, Any] = {"lane": lane}
    if lane == "dense":
        metric = _require_metric(metric)
        params["metric"] = metric
        params["query_vector"] = _normalize_query_vector(query_vector, metric)
        if collection is None:
            raise RetrievalError(
                "invalid_arguments",
                "a filtered dense search needs collection=; a vector lane needs a built "
                "index, and building one per request is the retrieval engine's job",
            )
        if documents is not None:
            raise RetrievalError(
                "invalid_arguments",
                "documents= belongs to the sparse lane; a dense lane searches a built "
                "collection",
            )
    else:
        source = _require_exactly_one(
            "filtered_search", documents=documents, collection=collection
        )
        params["query"] = _require_query_text(query)
        params.update(_bm25_params(k1, b))
        if source == "documents":
            if backend != "lexical":
                raise RetrievalError(
                    "backend_cannot_serve_verb",
                    f"the {backend!r} backend searches a stored collection; documents "
                    "in the request are indexed by 'lexical'",
                )
            params["documents"] = _normalize_documents(documents)
        elif backend == "lexical":
            # The same refusal `sparse_search` makes, for the same reason: the lexical
            # backend indexes the documents in this request and keeps nothing, so it
            # takes documents= rather than collection=. Without this the request
            # reaches the lexical lane with no documents to index at all.
            raise RetrievalError(
                "backend_cannot_serve_verb",
                "the 'lexical' backend indexes the documents in this request and keeps "
                "nothing, so it takes documents= rather than collection=",
            )
    request = _build_search_request(
        "filtered_search",
        backend=backend,
        top_k=top_k,
        params=params,
        filter=restriction,
        collection=_require_collection(collection) if collection else None,
    )
    return _run_request(runtime, request)


def provenance(result: RetrievalResult, *, backend: str | None = None) -> RetrievalProvenance:
    """Explain a result: which lane put each item where, and what combined them.

    Pure reporting over a result already in hand — it dispatches nothing and cannot
    fail for want of a backend. Pass `backend` to assert which backend the result came
    from; a mismatch is rejected rather than relabelled, because provenance that can
    be given the wrong backend is not provenance.
    """
    if not isinstance(result, RetrievalResult):
        raise RetrievalError(
            "invalid_arguments",
            f"provenance takes a RetrievalResult; got {type(result).__name__}",
        )
    if backend is not None:
        _require_backend_for_verb("provenance", backend)
        if backend != result.backend:
            raise RetrievalError(
                "invalid_arguments",
                f"this result was served by {result.backend!r}, not {backend!r}",
            )
    items: list[RetrievalProvenanceItem] = []
    for hit in result.hits:
        items.append(
            RetrievalProvenanceItem(
                rank=hit.rank,
                id=hit.id,
                score=hit.score,
                backend=hit.backend,
                contributions=hit.lanes,
                explanation=_explain_hit(hit, result),
            )
        )
    return RetrievalProvenance(
        verb=result.verb,
        backend=result.backend,
        score_model=result.score_model,
        fusion=result.fusion,
        fusion_params=dict(result.fusion_params),
        items=tuple(items),
        collection=result.collection,
        attribution_residual=result.attribution_residual,
    )


def _explain_hit(hit: RetrievalHit, result: RetrievalResult) -> str:
    """One sentence per hit, stating only what was measured.

    No contribution arithmetic: the per-lane split of a fused score is the kernel's,
    and a number computed here to fill the sentence would be a second answer that
    happened to look authoritative.
    """
    head = (
        f"{hit.id!r} ranked {hit.rank} of {len(result.hits)} with score "
        f"{hit.score:.6g}, served by {hit.backend}"
    )
    if result.fusion:
        params = ", ".join(f"{k}={v}" for k, v in sorted(result.fusion_params.items()))
        head += f", fused by {result.fusion}({params})" if params else f", fused by {result.fusion}"
    head += f" under score model {result.score_model}"
    if not hit.lanes:
        return head + ". No lane decomposition was reported for this item."
    lanes = "; ".join(contribution.describe() for contribution in hit.lanes)
    return f"{head}. Contributions: {lanes}."


# ── the governed collection: remember / recall / compact ─────────────────────
def remember(
    runtime: Any,
    *,
    content: str,
    collection: str = "default",
    source: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    embedding: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    backend: str = "index",
) -> RememberReceipt:
    """Store an observation in the governed collection as an immutable episode.

    Same vocabulary as the hosted memory surface: `content`, `collection`, `source`,
    `policy`, `embedding`, `metadata`. Repeating identical content returns the
    existing episode with `status="existing"` rather than storing a second copy.

    Only the `index` backend can serve this. The ephemeral backends keep nothing
    between calls, so a store on one would not be a memory, and offering it would be
    a promise this module cannot keep.
    """
    backend = _require_backend_for_verb("remember", backend)
    if not isinstance(content, str) or not content.strip():
        raise RetrievalError(
            "invalid_arguments",
            "content is empty; there is no observation to store",
        )
    collection = _require_collection(collection)
    embedding_payload = _normalize_embedding(embedding)
    _require_local_runtime(runtime)
    _require_backend(backend, "remember", runtime)
    payload = {
        "content": content,
        "collection": collection,
        "source": dict(source or {}),
        "policy": dict(policy or {}),
        "metadata": dict(metadata or {}),
    }
    if embedding_payload is not None:
        payload["embedding"] = embedding_payload
    return _index_remember(runtime, payload, backend)


def recall(
    runtime: Any,
    *,
    query: str,
    collection: str = "default",
    where: Mapping[str, Any] | None = None,
    as_of: str | None = None,
    top_k: int = 8,
    explain: bool = False,
    model: str | None = None,
    backend: str = "index",
) -> RetrievalResult:
    """Retrieve from the governed collection, with provenance and score terms.

    Same vocabulary and the same defaults as the hosted memory surface: `top_k`
    defaults to 8 and is capped at 128 here for the same reason it is capped there —
    one bound, so a request this builder accepts is a request that surface accepts.
    `as_of` reconstructs what was valid at a world-time; omitting it means now.
    `model` pins the embedding space, and a recall never mixes spaces.

    Returns a `RetrievalResult` like every other verb, so one provenance report covers
    a governed recall and a local fusion alike. An empty result means nothing matched.
    """
    backend = _require_backend_for_verb("recall", backend)
    text = _require_query_text(query)
    collection = _require_collection(collection)
    top_k = _bounded_int(top_k, "top_k", 1, MAX_RECALL_TOP_K)
    if where is not None and not isinstance(where, Mapping):
        raise RetrievalError(
            "invalid_arguments",
            f"where must be a mapping of column to value; got {type(where).__name__}",
        )
    if as_of is not None and (not isinstance(as_of, str) or not as_of.strip()):
        raise RetrievalError(
            "invalid_arguments",
            "as_of must be an ISO-8601 timestamp string; omit it to recall as of now",
        )
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise RetrievalError(
            "invalid_arguments",
            "model pins the embedding space and must be a non-empty name; omit it to "
            "use the collection's own",
        )
    _require_local_runtime(runtime)
    _require_backend(backend, "recall", runtime)
    payload = {
        "query": text,
        "collection": collection,
        "where": dict(where or {}),
        "as_of": as_of,
        "top_k": top_k,
        "explain": bool(explain),
        "model": model,
    }
    return _index_recall(runtime, payload, backend)


def compact(
    runtime: Any,
    *,
    collection: str = "default",
    scope: Mapping[str, Any] | None = None,
    policy: str | None = None,
    summarize: bool = True,
    dedup_facts: bool = True,
    resolve_contradictions: bool = True,
    max_candidates: int = 10_000,
    backend: str = "index",
) -> CompactionReport:
    """Consolidate a governed collection under its retention policy.

    Same vocabulary as the hosted memory surface: `scope` selects what to consider,
    `policy` names a consolidator (omitted means the deterministic default), and the
    three booleans switch summarisation, fact dedup and contradiction resolution.
    """
    backend = _require_backend_for_verb("compact", backend)
    collection = _require_collection(collection)
    if scope is not None and not isinstance(scope, Mapping):
        raise RetrievalError(
            "invalid_arguments",
            f"scope must be a mapping of column to value; got {type(scope).__name__}",
        )
    if policy is not None and (not isinstance(policy, str) or not policy.strip()):
        raise RetrievalError(
            "invalid_arguments",
            "policy must be a non-empty name; omit it for the deterministic default",
        )
    max_candidates = _bounded_int(
        max_candidates, "max_candidates", 1, MAX_COMPACT_CANDIDATES
    )
    _require_local_runtime(runtime)
    _require_backend(backend, "compact", runtime)
    payload = {
        "collection": collection,
        "scope": dict(scope or {}),
        "policy": policy,
        "summarize": bool(summarize),
        "dedup_facts": bool(dedup_facts),
        "resolve_contradictions": bool(resolve_contradictions),
        "max_candidates": max_candidates,
    }
    return _index_compact(runtime, payload, backend)


def _normalize_embedding(embedding: Any) -> dict[str, Any] | None:
    """A client-supplied embedding, or nothing.

    `model_id` and `model_version` are required when a vector is supplied, because a
    recall must not mix embedding spaces and the only way to keep that promise is to
    know which space a stored vector belongs to. The declared dimension must equal the
    vector's length, checked here rather than trusted.
    """
    if embedding is None:
        return None
    if not isinstance(embedding, Mapping):
        raise RetrievalError(
            "invalid_arguments",
            f"embedding must be a mapping; got {type(embedding).__name__}",
        )
    vector = embedding.get("vector")
    if isinstance(vector, (str, bytes)) or not isinstance(vector, (list, tuple)):
        raise RetrievalError(
            "invalid_arguments", "embedding needs a vector of numbers"
        )
    if not vector:
        raise RetrievalError(
            "invalid_arguments",
            "embedding vector is empty; omit embedding to have the engine embed",
        )
    values = [
        _finite_float(value, f"embedding.vector[{index}]")
        for index, value in enumerate(vector)
    ]
    for key in ("model_id", "model_version"):
        value = embedding.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RetrievalError(
                "invalid_arguments",
                f"embedding needs a non-empty {key}; a recall never mixes embedding "
                "spaces, which it can only honour if every vector says which space "
                "it is in",
            )
    metric = embedding.get("metric", "cosine")
    _require_metric(metric)
    declared = embedding.get("dimension", len(values))
    declared = _bounded_int(declared, "embedding.dimension", 1, MAX_DIMENSION)
    if declared != len(values):
        raise RetrievalError(
            "invalid_arguments",
            f"embedding declares {declared} dimensions and carries {len(values)}",
        )
    return {
        "vector": values,
        "model_id": str(embedding["model_id"]),
        "model_version": str(embedding["model_version"]),
        "dimension": declared,
        "metric": str(metric),
    }


# ── the builder ──────────────────────────────────────────────────────────────
class Retrieval:
    """Build one retrieval request, then run it.

    Fluent construction over the same validation the verb functions use — each method
    delegates, so a request built here and a request built by calling the verb
    directly are the same object and go through one definition of valid:

        result = (
            Retrieval(backend="lexical", top_k=5)
            .sparse(query="tokenize query", documents=docs)
            .run(runtime)
        )

    One verb per request. A second verb raises rather than replacing the first, since
    a builder that silently forgot an earlier call would produce a request nobody
    wrote.
    """

    def __init__(self, *, backend: str = "local", top_k: int = 10) -> None:
        self._backend = _require_known_backend(backend)
        self._top_k = top_k
        self._request: RetrievalRequest | None = None

    # ── verbs ────────────────────────────────────────────────────────────────
    def vector(
        self,
        *,
        query_vector: Sequence[float],
        collection: str,
        metric: str = "cosine",
    ) -> Retrieval:
        return self._set(
            _defer(
                vector_search,
                query_vector=query_vector,
                collection=collection,
                metric=metric,
            )
        )

    def sparse(
        self,
        *,
        query: str,
        documents: Sequence[RetrievalDocument] | None = None,
        collection: str | None = None,
        k1: float = 1.8,
        b: float = 1.0,
    ) -> Retrieval:
        return self._set(
            _defer(
                sparse_search,
                query=query,
                documents=documents,
                collection=collection,
                k1=k1,
                b=b,
            )
        )

    def hybrid(
        self,
        *,
        dense: Any = None,
        sparse: Any = None,
        lanes: Mapping[str, Any] | None = None,
        query: str | None = None,
        collection: str | None = None,
        fusion: str = "rrf",
        rrf_k: float | None = None,
        alpha: float | None = None,
        explain: bool = False,
    ) -> Retrieval:
        return self._set(
            _defer(
                hybrid_search,
                dense=dense,
                sparse=sparse,
                lanes=lanes,
                query=query,
                collection=collection,
                fusion=fusion,
                rrf_k=rrf_k,
                alpha=alpha,
                explain=explain,
            )
        )

    def rerank_with(
        self,
        *,
        candidates: Sequence[RetrievalCandidate],
        similarity: Sequence[float] | None = None,
        method: str = "mmr",
        lambda_mmr: float | None = None,
        bias: float | None = None,
    ) -> Retrieval:
        return self._set(
            _defer(
                rerank,
                candidates=candidates,
                similarity=similarity,
                method=method,
                lambda_mmr=lambda_mmr,
                bias=bias,
            )
        )

    def filtered(
        self,
        *,
        lane: str,
        filter: RetrievalFilter | Mapping[str, Any],  # noqa: A002
        query_vector: Sequence[float] | None = None,
        query: str | None = None,
        documents: Sequence[RetrievalDocument] | None = None,
        collection: str | None = None,
        metric: str = "cosine",
        k1: float = 1.8,
        b: float = 1.0,
    ) -> Retrieval:
        return self._set(
            _defer(
                filtered_search,
                lane=lane,
                filter=filter,
                query_vector=query_vector,
                query=query,
                documents=documents,
                collection=collection,
                metric=metric,
                k1=k1,
                b=b,
            )
        )

    # ── execution ────────────────────────────────────────────────────────────
    def run(self, runtime: Any) -> RetrievalResult:
        """Validate and execute. Raises if no verb was chosen."""
        if self._request is None:
            raise RetrievalError(
                "invalid_arguments",
                "this Retrieval has no verb; call one of vector, sparse, hybrid, "
                "rerank_with or filtered before run",
            )
        return self._request(runtime)

    def _set(self, deferred: Any) -> Retrieval:
        if self._request is not None:
            raise RetrievalError(
                "invalid_arguments",
                "a Retrieval carries one verb; build a second Retrieval rather than "
                "replacing the first, so the request that runs is the one written",
            )
        self._request = deferred(backend=self._backend, top_k=self._top_k)
        return self


def _defer(verb_function: Any, **kwargs: Any) -> Any:
    """Bind a verb's arguments now and its backend/top_k at `_set` time.

    Validation still happens inside the verb function, once, when the builder runs —
    so the builder cannot construct a request the verb would have rejected.
    """

    def bind(*, backend: str, top_k: int) -> Any:
        def execute(runtime: Any) -> RetrievalResult:
            return verb_function(runtime, backend=backend, top_k=top_k, **kwargs)

        return execute

    return bind




# ── execution ────────────────────────────────────────────────────────────────
def _run_request(runtime: Any, request: RetrievalRequest) -> RetrievalResult:
    """Hand a validated request to the backend half.

    Imported here rather than at module scope so importing the contract never probes
    for an engine or touches a runtime — the same discipline the rest of this package
    keeps, where `algenta` can be imported without a compiled runtime existing.
    """
    from algenta.retrieval_execution import run_request

    return run_request(runtime, request)


def _index_remember(
    runtime: Any, payload: Mapping[str, Any], backend: str
) -> RememberReceipt:
    """Store through the governed collection. Lazy for the same reason as above."""
    from algenta.retrieval_execution import index_remember

    return index_remember(runtime, payload, backend)


def _index_recall(
    runtime: Any, payload: Mapping[str, Any], backend: str
) -> RetrievalResult:
    """Recall through the governed collection. Lazy for the same reason as above."""
    from algenta.retrieval_execution import index_recall

    return index_recall(runtime, payload, backend)


def _index_compact(
    runtime: Any, payload: Mapping[str, Any], backend: str
) -> CompactionReport:
    """Compact through the governed collection. Lazy for the same reason as above."""
    from algenta.retrieval_execution import index_compact

    return index_compact(runtime, payload, backend)
