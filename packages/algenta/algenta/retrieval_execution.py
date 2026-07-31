"""Retrieval execution — the backend half of the retrieval contract.

Split from `retrieval.py` so the contract (the verbs, the types, the validation and
the error shapes) reads on its own. Everything here runs AFTER a request has been
validated and after its backend has been resolved, which is the one ordering that
matters: nothing below this line can produce an empty result standing in for a
missing engine, because a missing engine has already raised.

Three backends are served here, and the division of labour is deliberate:

* `local` marshals flat, row-major payloads and hands the ranking to a compiled
  kernel. It computes no score, and reorders nothing that comes back.
* `lexical` builds and searches the index engine's own lexical index. It supplies ids
  and text, reads back `(id, score)` in the engine's order, and rescores nothing — a
  second scorer here would be a second definition of relevance.
* `index` calls the governed collection's own entry points and maps its response onto
  the one result vocabulary, so a governed recall and a local fusion explain the same
  way.

Imported lazily by `retrieval.py`, so the contract module stays importable without
touching a runtime or probing for an engine.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from dataclasses import replace
from time import perf_counter
from typing import Any

from algenta.retrieval import (
    _BACKEND_IMPORTS,
    _KERNEL_CEILINGS,
    _KERNEL_FUSE,
    _KERNEL_HYBRID_RANK,
    _KERNEL_MMR_SELECT,
    _KERNEL_RRF_FUSE,
    _KERNEL_RRF_PROVENANCE,
    _KERNEL_SCORE,
    _KERNEL_STATUS_NAME,
    _KERNEL_STATUS_OK,
    _MISSING_KERNEL_CODES,
    MAX_COMPACT_CANDIDATES,
    MAX_TOP_K,
    CompactionReport,
    RememberReceipt,
    RetrievalBackendUnavailableError,
    RetrievalCandidate,
    RetrievalDocument,
    RetrievalError,
    RetrievalFilter,
    RetrievalHit,
    RetrievalLaneContribution,
    RetrievalRequest,
    RetrievalResult,
    _bounded_int,
    _envelope_error_code,
    _envelope_error_message,
    _finite_float,
    _probe_import,
    _require_backend,
    _require_local_runtime,
)

__all__ = ["index_compact", "index_recall", "index_remember", "run_request"]

# The kernels' own ceilings, read from the kernel rather than restated here. The
# retrieval package says why in its own words: a limit copied into Python drifts from
# the limit that is actually applied, and then a request this module accepted is
# rejected downstream with a number nobody can trace back.
#
# Cached per process, not per runtime: the ceilings are compile-time constants of the
# installed binary, so every runtime in this process reports the same ones. The cache
# holds only a SUCCESSFUL read — a failed read means the kernels are not there, which
# is an unavailable backend and must be re-asked rather than remembered.
_CEILINGS: dict[str, int] | None = None
_CEILING_FIELDS = ("cells", "dim", "doc_ordinal", "csr_dim")


def _ceilings(runtime: Any) -> dict[str, int]:
    """`{cells, dim, doc_ordinal, csr_dim}` as the installed kernels enforce them."""
    global _CEILINGS
    if _CEILINGS is not None:
        return _CEILINGS
    envelope = runtime.execute(_KERNEL_SCORE, _KERNEL_CEILINGS, [])
    code = _envelope_error_code(envelope)
    if code in _MISSING_KERNEL_CODES:
        raise RetrievalBackendUnavailableError(
            backend="local",
            missing=(f"{_KERNEL_SCORE}.{_KERNEL_CEILINGS}",),
            detail=_envelope_error_message(envelope),
        )
    if code:
        raise RetrievalError(
            code,
            f"{_KERNEL_SCORE}.{_KERNEL_CEILINGS} failed: "
            f"{_envelope_error_message(envelope)}",
        )
    values = envelope.get("result") if isinstance(envelope, Mapping) else None
    if not isinstance(values, list) or len(values) < len(_CEILING_FIELDS):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{_KERNEL_SCORE}.{_KERNEL_CEILINGS} returned {values!r}; expected "
            f"{len(_CEILING_FIELDS)} ceilings",
        )
    resolved: dict[str, int] = {}
    for name, value in zip(_CEILING_FIELDS, values, strict=False):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise RetrievalError(
                "retrieval_kernel_contract_mismatch",
                f"the kernels reported a {name} ceiling of {value!r}",
            )
        resolved[name] = value
    _CEILINGS = resolved
    return resolved


def _require_within_ceilings(runtime: Any, *, items: int, cells: int) -> None:
    """Reject a payload the kernels would reject, while the caller's numbers are here.

    Both dimensions are checked, because a per-item ceiling is not a bound on a total:
    a lane count under the dimension ceiling and a concatenated length over the cell
    ceiling are two different rejections, and the kernel makes both.
    """
    limits = _ceilings(runtime)
    if items > limits["dim"]:
        raise RetrievalError(
            "invalid_arguments",
            f"{items} items exceeds the retrieval dimension ceiling of {limits['dim']} "
            "that the installed kernels enforce",
        )
    if cells > limits["cells"]:
        raise RetrievalError(
            "invalid_arguments",
            f"{cells} values exceeds the retrieval cell ceiling of {limits['cells']} "
            "that the installed kernels enforce. A per-item ceiling is not a bound on "
            "the total that crosses the boundary.",
        )


# ── kernel dispatch ──────────────────────────────────────────────────────────
def _call_kernel(
    runtime: Any,
    module: str,
    function: str,
    args: list[Any],
    *,
    verb: str,
    lane: str,
) -> Mapping[str, Any]:
    """Run one retrieval kernel and return its decoded struct.

    Three outcomes, kept apart on purpose:

    * the module or function is not in the installed shard, or the runtime is not there
      at all — the backend is unavailable, and that raises;
    * the kernel ran and rejected the request — that raises, carrying the kernel's OWN
      name for the defect, because a rejected ranking is not a short ranking;
    * the kernel ran and answered — the struct is returned as it came back. Nothing is
      recomputed, reordered or filled in here.
    """
    envelope = runtime.execute(module, function, args)
    code = _envelope_error_code(envelope)
    if code in _MISSING_KERNEL_CODES:
        raise RetrievalBackendUnavailableError(
            backend="local",
            missing=(f"{module}.{function}",),
            verb=verb,
            detail=_envelope_error_message(envelope),
        )
    if code:
        raise RetrievalError(
            code,
            f"{module}.{function} failed: {_envelope_error_message(envelope)}",
            lane,
        )
    result = envelope.get("result") if isinstance(envelope, Mapping) else None
    if not isinstance(result, Mapping):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{module}.{function} returned {type(result).__name__}, not a struct",
            lane,
        )
    status = result.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{module}.{function} returned a non-integer status {status!r}",
            lane,
        )
    if status != _KERNEL_STATUS_OK:
        # The kernel's own vocabulary for the defect, asked for on the failure path
        # only. Restating the status names here would be the same constant in two
        # places, and the copy is the one that goes stale.
        raise RetrievalError(
            "retrieval_kernel_rejected",
            f"{module}.{function} rejected the request: "
            f"{_status_name(runtime, status)} (status {status}); no ranking was produced",
            lane,
        )
    return result


def _status_name(runtime: Any, status: int) -> str:
    """The kernel's name for a status code, or the code itself if it cannot be asked."""
    try:
        envelope = runtime.execute(_KERNEL_SCORE, _KERNEL_STATUS_NAME, [status])
    except Exception:  # noqa: BLE001 — naming a failure must not raise a second one
        return "unknown"
    if _envelope_error_code(envelope):
        return "unknown"
    name = envelope.get("result") if isinstance(envelope, Mapping) else None
    return name if isinstance(name, str) and name else "unknown"


def _decode_int_list(result: Mapping[str, Any], key: str, where: str) -> list[int]:
    values = result.get(key)
    if not isinstance(values, list):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned no {key!r} list",
        )
    out: list[int] = []
    for position, value in enumerate(values):
        if not isinstance(value, int) or isinstance(value, bool):
            raise RetrievalError(
                "retrieval_kernel_contract_mismatch",
                f"{where} returned a non-integer {key}[{position}]",
            )
        out.append(value)
    return out


def _decode_float_list(result: Mapping[str, Any], key: str, where: str) -> list[float]:
    values = result.get(key)
    if not isinstance(values, list):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned no {key!r} list",
        )
    out: list[float] = []
    for position, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RetrievalError(
                "retrieval_kernel_contract_mismatch",
                f"{where} returned a non-numeric {key}[{position}]",
            )
        out.append(float(value))
    return out


def _decode_ranking(
    result: Mapping[str, Any], *, score_key: str, where: str
) -> tuple[list[int], list[float]]:
    """`(doc_ids, scores)` from a kernel struct, with the two lengths agreed.

    A ranking with more ids than scores is not a shorter ranking, it is a broken one, so
    the mismatch is reported rather than truncated to whichever list ran out first.
    """
    doc_ids = _decode_int_list(result, "doc_ids", where)
    scores = _decode_float_list(result, score_key, where)
    if len(doc_ids) != len(scores):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned {len(doc_ids)} ids and {len(scores)} scores; a ranking "
            "needs one score per item",
        )
    return doc_ids, scores


def _residual(result: Mapping[str, Any]) -> float | None:
    """The attribution certificate, absent when the kernel reported none.

    The kernels spell absence as -1.0 for this field, which is outside the value domain
    of a relative discrepancy, so it maps to `None` here rather than travelling onward
    as a suspiciously negative number.
    """
    value = result.get("max_attribution_residual")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return None if number < 0.0 else number


# ── dispatch by backend ──────────────────────────────────────────────────────
def run_request(runtime: Any, request: RetrievalRequest) -> RetrievalResult:
    """Dispatch a validated request to the backend that will serve it.

    An absent backend raises before any lane runs, so nothing below this line can
    produce an empty result standing in for a missing engine.

    The `local` backend is the one exception to resolving availability up front, and it
    is not a weakening: its kernel calls ALREADY report a module or function the
    installed shard does not carry as the same typed unavailable error, naming the exact
    function rather than the module. Probing first would dispatch a second frame to
    learn something the real call is about to tell us — and a probe whose answer can go
    stale between the probe and the call is worse than no probe.
    """
    _require_local_runtime(runtime)
    if request.backend != "local":
        _require_backend(request.backend, request.verb, runtime)
    started = perf_counter()
    if request.backend == "local":
        result = _run_local(runtime, request)
    elif request.backend == "lexical":
        result = _run_lexical(request)
    else:
        # `dense` and `index` search a built index. Reaching here means the backend
        # reported itself available, so the call belongs to the index engine's own
        # search surface rather than to this module.
        result = _run_index_search(runtime, request)
    return replace(result, latency_ms=round((perf_counter() - started) * 1000, 3))


def _run_local(runtime: Any, request: RetrievalRequest) -> RetrievalResult:
    """Serve a request from the bundled compiled kernels.

    Each branch marshals a flat payload and hands the ranking to a kernel. No branch
    computes a score, and none reorders what came back.
    """
    if request.verb == "hybrid_search":
        return _local_fuse(runtime, request)
    if request.verb == "rerank":
        return _local_rerank(runtime, request)
    raise RetrievalError(
        "backend_cannot_serve_verb",
        f"the 'local' backend does not serve {request.verb}",
    )


def _local_fuse(runtime: Any, request: RetrievalRequest) -> RetrievalResult:
    """Fuse N lane results with the compiled fusion kernels."""
    lanes: tuple[tuple[str, tuple[tuple[str, float], ...]], ...] = request.params["lanes"]
    if request.params["fusion"] == "rrf":
        return _local_fuse_rrf(runtime, request, lanes)
    return _local_fuse_linear(runtime, request, lanes)


def _ordinals(
    lanes: Sequence[tuple[str, Sequence[tuple[str, float]]]],
) -> tuple[list[str], dict[str, int]]:
    """One integer ordinal per distinct id, in first-seen lane-then-rank order.

    The kernels rank integer document ordinals, so string ids are mapped here and mapped
    back on the way out. First-seen order rather than sorted, so the mapping is a pure
    function of the lanes as written and two runs of the same request produce the same
    ordinals — which matters because the kernels break score ties on ascending ordinal.
    """
    order: list[str] = []
    index: dict[str, int] = {}
    for _, pairs in lanes:
        for item_id, _ in pairs:
            if item_id not in index:
                index[item_id] = len(order)
                order.append(item_id)
    return order, index


def _lane_maps(
    lanes: Sequence[tuple[str, Sequence[tuple[str, float]]]],
) -> list[dict[str, tuple[int, float]]]:
    """Per lane, `id -> (1-based rank, score)`. An id absent from a lane is absent."""
    return [
        {item_id: (rank, score) for rank, (item_id, score) in enumerate(pairs, start=1)}
        for _, pairs in lanes
    ]


def _local_fuse_rrf(
    runtime: Any,
    request: RetrievalRequest,
    lanes: Sequence[tuple[str, Sequence[tuple[str, float]]]],
) -> RetrievalResult:
    order, ordinal_of = _ordinals(lanes)
    # Every lane's ranking CONCATENATED, best first within each lane, plus each lane's
    # length: that is the fusion kernel's payload shape, and ranks are derived from
    # position inside each slice rather than sent alongside, because a rank that
    # disagreed with the list order would be a wrong answer no validation could catch.
    doc_ids: list[int] = []
    lane_lengths: list[int] = []
    for _, pairs in lanes:
        lane_lengths.append(len(pairs))
        doc_ids.extend(ordinal_of[item_id] for item_id, _ in pairs)
    _require_within_ceilings(runtime, items=len(lanes), cells=len(doc_ids))
    rrf_k: float = request.params["rrf_k"]
    args = [doc_ids, lane_lengths, len(lanes), rrf_k, request.top_k]
    result = _call_kernel(
        runtime, _KERNEL_FUSE, _KERNEL_RRF_FUSE, args, verb="hybrid_search", lane="fuse"
    )
    fused_ids, scores = _decode_ranking(
        result, score_key="scores", where=f"{_KERNEL_FUSE}.{_KERNEL_RRF_FUSE}"
    )
    maps = _lane_maps(lanes)
    attribution: dict[str, dict[int, float]] = {}
    residual: float | None = None
    if request.params.get("explain"):
        attribution, residual = _rrf_attribution(runtime, request, args, order)
    hits: list[RetrievalHit] = []
    for position, (ordinal, score) in enumerate(zip(fused_ids, scores, strict=True)):
        item_id = _id_for_ordinal(ordinal, order, f"{_KERNEL_FUSE}.{_KERNEL_RRF_FUSE}")
        contributions = tuple(
            RetrievalLaneContribution(
                lane=name,
                backend="local",
                rank=maps[lane_index].get(item_id, (None, None))[0],
                score=maps[lane_index].get(item_id, (None, None))[1],
                contribution=attribution.get(item_id, {}).get(lane_index),
            )
            for lane_index, (name, _) in enumerate(lanes)
        )
        hits.append(
            RetrievalHit(
                rank=position + 1,
                id=item_id,
                score=score,
                backend="local",
                lanes=contributions,
            )
        )
    return RetrievalResult(
        verb="hybrid_search",
        backend="local",
        lanes=tuple(name for name, _ in lanes),
        hits=tuple(hits),
        top_k=request.top_k,
        score_model=f"{_KERNEL_FUSE}/{_KERNEL_RRF_FUSE}",
        fusion="rrf",
        fusion_params={"rrf_k": rrf_k, "lanes": len(lanes)},
        attribution_residual=residual,
    )


def _rrf_attribution(
    runtime: Any,
    request: RetrievalRequest,
    args: list[Any],
    order: Sequence[str],
) -> tuple[dict[str, dict[int, float]], float | None]:
    """The kernel's own `(document, lane, rank, contribution)` table.

    Same arguments and the same fold as the ranking call, so the table and the order
    cannot drift. Every number in it is the kernel's; none is computed here.
    """
    where = f"{_KERNEL_FUSE}.{_KERNEL_RRF_PROVENANCE}"
    result = _call_kernel(
        runtime,
        _KERNEL_FUSE,
        _KERNEL_RRF_PROVENANCE,
        args,
        verb="hybrid_search",
        lane="fuse",
    )
    row_docs = _decode_int_list(result, "doc_ids", where)
    row_lanes = _decode_int_list(result, "lanes", where)
    contributions = _decode_float_list(result, "contributions", where)
    if not len(row_docs) == len(row_lanes) == len(contributions):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned {len(row_docs)} documents, {len(row_lanes)} lanes and "
            f"{len(contributions)} contributions; a row needs all three",
            "fuse",
        )
    table: dict[str, dict[int, float]] = {}
    for ordinal, lane_index, value in zip(
        row_docs, row_lanes, contributions, strict=True
    ):
        item_id = _id_for_ordinal(ordinal, order, where)
        table.setdefault(item_id, {})[lane_index] = value
    return table, _residual(result)


def _local_fuse_linear(
    runtime: Any,
    request: RetrievalRequest,
    lanes: Sequence[tuple[str, Sequence[tuple[str, float]]]],
) -> RetrievalResult:
    # Validated upstream: exactly the lanes 'dense' and 'sparse', over the same id set.
    # So one aligned score array per lane is a complete payload, with no absence to
    # encode — which is the reason that restriction exists.
    order, _ = _ordinals(lanes)
    dense_of = dict(lanes[0][1])
    sparse_of = dict(lanes[1][1])
    dense = [dense_of[item_id] for item_id in order]
    sparse = [sparse_of[item_id] for item_id in order]
    _require_within_ceilings(runtime, items=len(order), cells=2 * len(order))
    alpha: float = request.params["alpha"]
    where = f"{_KERNEL_SCORE}.{_KERNEL_HYBRID_RANK}"
    result = _call_kernel(
        runtime,
        _KERNEL_SCORE,
        _KERNEL_HYBRID_RANK,
        [dense, sparse, len(order), alpha, request.top_k],
        verb="hybrid_search",
        lane="fuse",
    )
    fused_ids, scores = _decode_ranking(result, score_key="scores", where=where)
    # The kernel reports each lane's weighted share of every returned score, so the
    # decomposition is measured rather than reconstructed.
    dense_part = _decode_float_list(result, "dense_part", where)
    sparse_part = _decode_float_list(result, "sparse_part", where)
    if not len(dense_part) == len(sparse_part) == len(fused_ids):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned {len(fused_ids)} scores but {len(dense_part)} dense and "
            f"{len(sparse_part)} sparse parts",
            "fuse",
        )
    maps = _lane_maps(lanes)
    hits: list[RetrievalHit] = []
    for position, (ordinal, score) in enumerate(zip(fused_ids, scores, strict=True)):
        item_id = _id_for_ordinal(ordinal, order, where)
        parts = (dense_part[position], sparse_part[position])
        contributions = tuple(
            RetrievalLaneContribution(
                lane=name,
                backend="local",
                rank=maps[lane_index].get(item_id, (None, None))[0],
                score=maps[lane_index].get(item_id, (None, None))[1],
                contribution=parts[lane_index],
            )
            for lane_index, (name, _) in enumerate(lanes)
        )
        hits.append(
            RetrievalHit(
                rank=position + 1,
                id=item_id,
                score=score,
                backend="local",
                lanes=contributions,
            )
        )
    return RetrievalResult(
        verb="hybrid_search",
        backend="local",
        lanes=tuple(name for name, _ in lanes),
        hits=tuple(hits),
        top_k=request.top_k,
        score_model=where,
        fusion="linear",
        fusion_params={"alpha": alpha},
        attribution_residual=_residual(result),
    )


def _local_rerank(runtime: Any, request: RetrievalRequest) -> RetrievalResult:
    """Reorder candidates by maximal marginal relevance, in the compiled kernel."""
    candidates: tuple[RetrievalCandidate, ...] = request.params["candidates"]
    similarity: tuple[float, ...] = request.params["similarity"]
    lambda_mmr: float = request.params["lambda_mmr"]
    n = len(candidates)
    _require_within_ceilings(runtime, items=n, cells=len(similarity))
    where = f"{_KERNEL_SCORE}.{_KERNEL_MMR_SELECT}"
    result = _call_kernel(
        runtime,
        _KERNEL_SCORE,
        _KERNEL_MMR_SELECT,
        [
            [candidate.score for candidate in candidates],
            list(similarity),
            n,
            request.top_k,
            lambda_mmr,
        ],
        verb="rerank",
        lane="rerank",
    )
    selected, scores = _decode_ranking(result, score_key="mmr_scores", where=where)
    # The kernel reports the relevance it used and the redundancy it measured, including
    # whether a maximum similarity existed at all — a candidate selected first has
    # nothing to be redundant with, and `max_sim_known` says so instead of implying 0.0.
    relevance = _decode_float_list(result, "relevance", where)
    max_sim = _decode_float_list(result, "max_sim", where)
    known = result.get("max_sim_known")
    if not isinstance(known, list) or not len(relevance) == len(max_sim) == len(known):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned relevance, max_sim and max_sim_known of different lengths",
            "rerank",
        )
    hits: list[RetrievalHit] = []
    for position, (ordinal, score) in enumerate(zip(selected, scores, strict=True)):
        if ordinal < 0 or ordinal >= n:
            raise RetrievalError(
                "retrieval_kernel_contract_mismatch",
                f"{where} selected candidate {ordinal} of {n}",
                "rerank",
            )
        candidate = candidates[ordinal]
        lanes = [
            RetrievalLaneContribution(
                lane="input_relevance",
                backend="local",
                rank=ordinal + 1,
                score=relevance[position] if position < len(relevance) else None,
            )
        ]
        if position < len(known) and known[position]:
            lanes.append(
                RetrievalLaneContribution(
                    lane="redundancy",
                    backend="local",
                    score=max_sim[position],
                )
            )
        else:
            # Absent, not zero: nothing had been selected yet, so there was no
            # similarity to anything and a 0.0 here would read as "measured, and low".
            lanes.append(
                RetrievalLaneContribution(lane="redundancy", backend="local")
            )
        hits.append(
            RetrievalHit(
                rank=position + 1,
                id=candidate.id,
                score=score,
                backend="local",
                lanes=tuple(lanes),
                metadata=dict(candidate.metadata),
                text=candidate.text,
            )
        )
    return RetrievalResult(
        verb="rerank",
        backend="local",
        lanes=("rerank",),
        hits=tuple(hits),
        top_k=request.top_k,
        score_model=f"{where}(mmr)",
        fusion_params={"lambda_mmr": lambda_mmr},
    )


def _id_for_ordinal(ordinal: int, order: Sequence[str], where: str) -> str:
    if ordinal < 0 or ordinal >= len(order):
        raise RetrievalError(
            "retrieval_kernel_contract_mismatch",
            f"{where} returned document ordinal {ordinal} for a set of {len(order)}",
        )
    return order[ordinal]


def _run_lexical(request: RetrievalRequest) -> RetrievalResult:
    """Serve the sparse lane from the index engine's lexical index.

    The index is built and searched by the engine. This function supplies ids and
    text, reads back `(id, score)` in the engine's order, and changes neither — a
    rescore here would be a second definition of relevance that could disagree with
    the index that produced it.

    An empty ranking means the query matched no document. The engine was present and
    answered; that is a result, not a failure — and that is only true because the
    filter is applied BEFORE anything is truncated, never after.

    A FILTERED search asks the index for the whole corpus and admits the ones the
    filter allows, keeping the first `top_k` of those. The filter is over metadata the
    index does not hold, so it can only be applied out here; asking for a window of
    `top_k * 8` and filtering that would silently drop a document that matches both
    the query and the filter but was ranked outside the window, and report the empty
    ranking that comes back as "nothing matched". Those are the two most different
    answers retrieval can give, so the window is not kept.

    The cost of that choice, stated plainly: the index selects over every document it
    scored rather than over `top_k` of them, on filtered searches only. It is bounded
    by the corpus in this very request — `MAX_DOCUMENTS`, all of it already resident
    and already indexed one call above — and the engine scores the whole corpus for a
    top-1 search anyway, so selecting more of what it scored costs no extra pass. In
    exchange, an empty result means nothing matched, with no window to ask about.
    """
    lexical = _import_lexical()
    documents = _lexical_documents(request)
    k1: float = request.params["k1"]
    b: float = request.params["b"]
    index = lexical.LexicalCodeIndex(k1=k1, b=b)
    index.build(
        [document.id for document in documents],
        [document.text for document in documents],
    )
    restriction = request.filter
    # Unfiltered: top_k is the answer's length and the index applies it. Filtered: the
    # whole corpus, because the length is decided out here, after the filter.
    wanted = request.top_k if restriction is None else len(documents)
    ranked = index.search(request.params["query"], wanted)
    by_id = {document.id: document for document in documents}
    hits: list[RetrievalHit] = []
    for engine_rank, entry in enumerate(ranked, start=1):
        item_id = str(entry[0])
        score = _finite_float(entry[1], f"lexical score for {item_id!r}")
        document = by_id.get(item_id)
        if document is None:
            raise RetrievalError(
                "retrieval_kernel_contract_mismatch",
                f"the lexical index returned id {item_id!r}, which is not in the "
                "documents it was built from",
                "sparse",
            )
        if restriction is not None:
            if not restriction.keeps(item_id, document.metadata):
                continue
            if restriction.min_score is not None and score < restriction.min_score:
                continue
            if restriction.max_score is not None and score > restriction.max_score:
                continue
        hits.append(
            RetrievalHit(
                rank=len(hits) + 1,
                id=item_id,
                score=score,
                backend="lexical",
                lanes=(
                    RetrievalLaneContribution(
                        lane="sparse", backend="lexical", rank=engine_rank, score=score
                    ),
                ),
                metadata=dict(document.metadata),
                text=document.text,
            )
        )
        if len(hits) >= request.top_k:
            break
    lanes = ("sparse",) if restriction is None else ("filter", "sparse")
    return RetrievalResult(
        verb=request.verb,
        backend="lexical",
        lanes=lanes,
        hits=tuple(hits),
        top_k=request.top_k,
        score_model=f"lexical-bm25(k1={k1},b={b})",
    )


def _lexical_documents(request: RetrievalRequest) -> tuple[RetrievalDocument, ...]:
    """The documents this lexical request indexes, or a typed raise naming their absence.

    The lexical backend indexes the documents in the request and keeps nothing, so a
    request routed here with no `documents` has nothing to search. `sparse_search`
    refuses that pairing at the builder and `filtered_search` now refuses it too; this
    is the same refusal at the point of use, so a third caller that reaches this
    function without documents gets the sentence naming what was needed rather than a
    `KeyError` on a params key.
    """
    documents: tuple[RetrievalDocument, ...] | None = request.params.get("documents")
    if not documents:
        raise RetrievalError(
            "backend_cannot_serve_verb",
            f"the 'lexical' backend was asked to serve {request.verb} with no "
            "documents=; it indexes the documents in the request and keeps nothing, so "
            "there is no stored collection for it to search",
            "sparse",
        )
    return documents


def _import_lexical() -> Any:
    module_name = _BACKEND_IMPORTS["lexical"][0]
    ok, missing = _probe_import(module_name)
    if not ok:
        raise RetrievalBackendUnavailableError(
            backend="lexical", missing=(missing,), verb="sparse_search"
        )
    return importlib.import_module(module_name)


def _index_module(verb: str) -> Any:
    """The governed collection's own module, or a raise naming what is missing."""
    module_name = _BACKEND_IMPORTS["index"][0]
    ok, missing = _probe_import(module_name)
    if not ok:
        raise RetrievalBackendUnavailableError(
            backend="index", missing=(missing,), verb=verb
        )
    return importlib.import_module(module_name)


def _index_entrypoint(verb: str, name: str) -> Any:
    """One entry point on the governed collection's module.

    A module that imports but does not expose the entry point is unavailable for this
    verb, and saying so by name is the difference between an operator upgrading the
    engine and an operator reading a traceback about an attribute.
    """
    module = _index_module(verb)
    entrypoint = getattr(module, name, None)
    if not callable(entrypoint):
        raise RetrievalBackendUnavailableError(
            backend="index",
            missing=(f"{_BACKEND_IMPORTS['index'][0]}.{name}",),
            verb=verb,
        )
    return entrypoint


def _run_index_search(runtime: Any, request: RetrievalRequest) -> RetrievalResult:
    del runtime
    search = _index_entrypoint(request.verb, "search")
    payload = search(
        verb=request.verb,
        collection=request.collection,
        top_k=request.top_k,
        params=dict(request.params),
        filter=None if request.filter is None else _filter_payload(request.filter),
    )
    return _result_from_recall_payload(
        payload, verb=request.verb, backend=request.backend, top_k=request.top_k
    )


def index_remember(
    runtime: Any, payload: Mapping[str, Any], backend: str
) -> RememberReceipt:
    del runtime
    response = _index_entrypoint("remember", "remember")(**dict(payload))
    return _receipt_from_payload(response, backend)


def index_recall(
    runtime: Any, payload: Mapping[str, Any], backend: str
) -> RetrievalResult:
    del runtime
    response = _index_entrypoint("recall", "recall")(**dict(payload))
    return _result_from_recall_payload(
        response, verb="recall", backend=backend, top_k=int(payload["top_k"])
    )


def index_compact(
    runtime: Any, payload: Mapping[str, Any], backend: str
) -> CompactionReport:
    del runtime
    response = _index_entrypoint("compact", "compact")(**dict(payload))
    return _report_from_payload(response, backend)


def _filter_payload(restriction: RetrievalFilter) -> dict[str, Any]:
    payload: dict[str, Any] = {"where": dict(restriction.where)}
    if restriction.include_ids is not None:
        payload["include_ids"] = list(restriction.include_ids)
    if restriction.exclude_ids is not None:
        payload["exclude_ids"] = list(restriction.exclude_ids)
    if restriction.min_score is not None:
        payload["min_score"] = restriction.min_score
    if restriction.max_score is not None:
        payload["max_score"] = restriction.max_score
    return payload


# The score terms a governed recall reports, in the order they are explained. Each is
# a named contribution to the final score, and a penalty is named too — MEMORY's rule
# that a penalty is never silent is the same rule as provenance being complete.
_RECALL_SCORE_TERMS = (
    "dense_similarity",
    "sparse_score",
    "entity_match",
    "recency_decay",
    "salience",
    "source_authority",
    "confidence",
    "task_affinity",
)


def _result_from_recall_payload(
    payload: Any, *, verb: str, backend: str, top_k: int
) -> RetrievalResult:
    """Map the governed collection's response onto the one result vocabulary.

    A recall's score decomposition becomes lane contributions, so a single provenance
    report covers a governed recall and a local fusion alike. Every term the engine
    reported is carried through, including the named penalties; a term the engine did
    not report is absent rather than zero.

    Zero hits is a real answer and is returned as one — `hits: []`, said by the engine.
    The backend was resolved before this point, so an EMPTY `hits` here can only mean
    nothing matched. A MISSING `hits` means something else entirely and is refused: a
    response whose shape this function does not recognise is not an empty ranking, and
    defaulting it to one would manufacture the "the engine ran and nothing matched"
    answer out of a response that never said so. Same rule as the compaction report's
    `candidates_considered` below.
    """
    if not isinstance(payload, Mapping):
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            f"the retrieval engine returned {type(payload).__name__}, not a recall "
            "response",
        )
    if "hits" not in payload:
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            "the recall response carries no hits key; without it a ranking of zero "
            "items cannot be told from a response this contract does not understand. "
            f"The response carried {', '.join(sorted(map(str, payload))) or 'nothing'}.",
        )
    raw_hits = payload["hits"]
    if not isinstance(raw_hits, (list, tuple)):
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            f"the retrieval engine returned hits as {type(raw_hits).__name__}, not a "
            "list",
        )
    hits: list[RetrievalHit] = []
    for position, raw in enumerate(raw_hits):
        if not isinstance(raw, Mapping):
            raise RetrievalError(
                "retrieval_engine_contract_mismatch",
                f"hit {position} is {type(raw).__name__}, not an object",
            )
        item_id = raw.get("owner_id") or raw.get("fact_id") or raw.get("id")
        if not item_id:
            raise RetrievalError(
                "retrieval_engine_contract_mismatch",
                f"hit {position} carries no owner_id; a hit with no identity cannot be "
                "traced to its source",
            )
        score = _finite_float(raw.get("score", 0.0), f"hit {position} score")
        rank = raw.get("rank", position + 1)
        contributions: list[RetrievalLaneContribution] = []
        decomposition = raw.get("score_decomposition")
        if isinstance(decomposition, Mapping):
            for term in _RECALL_SCORE_TERMS:
                if term not in decomposition:
                    continue
                contributions.append(
                    RetrievalLaneContribution(
                        lane=term,
                        backend=backend,
                        rank=None,
                        score=_finite_float(decomposition[term], f"{term}"),
                    )
                )
            penalties = decomposition.get("penalties")
            if isinstance(penalties, Mapping):
                for name, value in sorted(penalties.items()):
                    contributions.append(
                        RetrievalLaneContribution(
                            lane=f"penalty:{name}",
                            backend=backend,
                            rank=None,
                            score=_finite_float(value, f"penalty {name}"),
                        )
                    )
        metadata: dict[str, Any] = {}
        for key in ("owner_type", "policy_id", "token_count"):
            if key in raw:
                metadata[key] = raw[key]
        source = raw.get("provenance")
        if isinstance(source, Mapping):
            for key in ("source_episode_id", "source_uri", "content_hash"):
                if key in source:
                    metadata[key] = source[key]
        temporal = raw.get("temporal")
        if isinstance(temporal, Mapping):
            for key in ("valid_from", "valid_to", "superseded"):
                if key in temporal:
                    metadata[key] = temporal[key]
        hits.append(
            RetrievalHit(
                rank=_bounded_int(rank, f"hit {position} rank", 1, MAX_TOP_K),
                id=str(item_id),
                score=score,
                backend=backend,
                lanes=tuple(contributions),
                metadata=metadata,
                text=raw.get("content"),
            )
        )
    score_model = payload.get("score_model_version") or payload.get("score_model")
    return RetrievalResult(
        verb=verb,
        backend=backend,
        lanes=("dense", "sparse"),
        hits=tuple(hits),
        top_k=top_k,
        score_model=str(score_model) if score_model else "governed-recall",
        collection=payload.get("collection"),
    )


def _receipt_from_payload(payload: Any, backend: str) -> RememberReceipt:
    if not isinstance(payload, Mapping):
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            f"the retrieval engine returned {type(payload).__name__}, not a remember "
            "response",
        )
    status = payload.get("status")
    if status not in ("created", "existing"):
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            f"a remember status must be 'created' or 'existing'; got {status!r}. "
            "Without it a caller cannot tell a new episode from a repeated one.",
        )
    for key in ("episode_id", "content_hash"):
        if not payload.get(key):
            raise RetrievalError(
                "retrieval_engine_contract_mismatch",
                f"the remember response carries no {key}; provenance to the stored "
                "episode is the point of storing it",
            )
    return RememberReceipt(
        collection=str(payload.get("collection") or "default"),
        episode_id=str(payload["episode_id"]),
        content_hash=str(payload["content_hash"]),
        status=str(status),
        ingested_at=str(payload.get("ingested_at") or ""),
        observed_at=str(payload.get("observed_at") or ""),
        extracted_fact_ids=tuple(
            str(item) for item in payload.get("extracted_fact_ids") or ()
        ),
        extracted_entity_ids=tuple(
            str(item) for item in payload.get("extracted_entity_ids") or ()
        ),
        embedding_model_id=payload.get("embedding_model_id"),
        embedding_model_version=payload.get("embedding_model_version"),
        backend=backend,
    )


def _report_from_payload(payload: Any, backend: str) -> CompactionReport:
    if not isinstance(payload, Mapping):
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            f"the retrieval engine returned {type(payload).__name__}, not a "
            "compaction response",
        )
    if "candidates_considered" not in payload:
        raise RetrievalError(
            "retrieval_engine_contract_mismatch",
            "the compaction response carries no candidates_considered; without it a "
            "report of zero changes cannot be told from a compaction that never ran",
        )
    counts: dict[str, int] = {}
    for key in (
        "candidates_considered",
        "facts_deduped",
        "facts_superseded",
        "contradictions_resolved",
        "summaries_created",
        "entities_merged",
    ):
        counts[key] = _bounded_int(
            payload.get(key, 0), key, 0, MAX_COMPACT_CANDIDATES
        )
    return CompactionReport(
        collection=str(payload.get("collection") or "default"),
        created_at=str(payload.get("created_at") or ""),
        policy=payload.get("policy"),
        summary_ids=tuple(str(item) for item in payload.get("summary_ids") or ()),
        backend=backend,
        **counts,
    )
