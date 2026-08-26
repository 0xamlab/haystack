"""Retrieval contract tests: what a request may say, and what a failure looks like.

Three things are pinned here.

The first is ordinary builder validation — an unknown backend, a `top_k` below one, an
empty query, a weight outside its range, two mutually exclusive inputs. Every one of
those is caught before dispatch, so the caller gets their own argument quoted back
instead of a generic engine failure.

The second is the rule the whole surface rests on: **a requested-but-unavailable backend
raises, and an available backend that matched nothing returns an empty result.** Those
two outcomes must never be the same value, because they are the two most different
things retrieval can tell you. Both are exercised against the real engine rather than
asserted against a mock:

* the lexical lane genuinely runs — the retrieval engine's wheel is put on `sys.path`,
  so `sparse_search` builds a real index and returns real scores, and a query that
  matches nothing comes back with zero hits and no exception;
* the dense and governed lanes are genuinely absent in this environment, so their raises
  are real raises, and the dependency each one names (`faiss`, `telys`) is the one
  actually missing rather than a string a test asserted into existence.

The third is drift between this contract and the kernels it calls. The status constant
and every kernel function name the contract targets are checked against the kernel
source and the packaged runtime contract, so a renamed kernel function fails here rather
than at a customer's first call.

The compiled kernels are exercised through a recording stub runtime: what is pinned is
the payload the contract emits and the way each envelope is translated, which is this
module's half of the boundary. The kernels' own arithmetic belongs to their own suite.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
# A wheel on sys.path is importable through zipimport, so the retrieval engine's
# lexical index is reachable with no install step. That is what lets the lexical
# assertions below be end-to-end instead of mocked.
_ENGINE_WHEEL = _REPO_ROOT / "vendor" / "wheels" / "telys_runtime-0.1.0a1-py3-none-any.whl"
for _entry in (str(_ALGENTA), str(_ENGINE_WHEEL)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from algenta.retrieval import (  # noqa: E402
    _KERNEL_CEILINGS,
    _KERNEL_FUSE,
    _KERNEL_HYBRID_RANK,
    _KERNEL_MMR_SELECT,
    _KERNEL_RRF_FUSE,
    _KERNEL_RRF_PROVENANCE,
    _KERNEL_SCORE,
    _KERNEL_STATUS_NAME,
    _KERNEL_STATUS_OK,
    BACKENDS,
    MAX_TOP_K,
    CompactionReport,
    RememberReceipt,
    Retrieval,
    RetrievalBackendUnavailableError,
    RetrievalCandidate,
    RetrievalDocument,
    RetrievalError,
    RetrievalFilter,
    RetrievalRequest,
    RetrievalResult,
    backend_status,
    compact,
    filtered_search,
    hybrid_search,
    provenance,
    recall,
    remember,
    rerank,
    sparse_search,
    vector_search,
)
from algenta.retrieval_execution import (  # noqa: E402
    _receipt_from_payload,
    _report_from_payload,
    _result_from_recall_payload,
)

_LEXICAL_AVAILABLE = backend_status("lexical").available is True
_needs_lexical = pytest.mark.skipif(
    not _LEXICAL_AVAILABLE,
    reason="the retrieval engine's lexical index is not importable from the wheel",
)

DOCUMENTS = [
    RetrievalDocument(
        id="a", text="def tokenize_query_parser(x): return x", metadata={"lang": "py"}
    ),
    RetrievalDocument(id="b", text="class Retriever: pass", metadata={"lang": "py"}),
    RetrievalDocument(
        id="c", text="def parse_query(q): return tokenize(q)", metadata={"lang": "rs"}
    ),
]

# What the installed kernels report for their own ceilings. Used only as a stub reply;
# the contract reads the real numbers from the kernel, which is the point.
CEILINGS = [1 << 22, 1 << 22, 1 << 52, 1 << 26]


class StubRuntime:
    """A local runtime that records kernel calls and replays scripted envelopes.

    Shaped exactly like `MojoRuntime(mode='local')` at the seam this module uses: one
    `execute(module, function, args)` returning an envelope. Nothing here pretends to
    compute a score — the scripted results stand in for the kernels' answers so the
    payload and the failure translation can be asserted on their own.

    Scripts are keyed by function name, so a test says what one kernel returns without
    having to describe the whole package.
    """

    _runtime_config = {"mode": "local"}

    def __init__(self, **scripts: object) -> None:
        self.scripts: dict[str, object] = {
            _KERNEL_CEILINGS: {"success": True, "result": list(CEILINGS)},
            _KERNEL_STATUS_NAME: {"success": True, "result": "weight_outside_unit_interval"},
        }
        self.scripts.update(scripts)
        self.calls: list[tuple[str, str, object]] = []

    def execute(self, module: str, function: str, args: object = None) -> dict:
        self.calls.append((module, function, args))
        scripted = self.scripts.get(function)
        if scripted is None:
            return {
                "success": False,
                "error_code": "function_not_registered",
                "error": f"{module} does not expose {function!r}",
            }
        return dict(scripted)  # type: ignore[arg-type]

    def kernel_calls(self) -> list[tuple[str, str, object]]:
        """Calls other than the ceiling probe, which every dispatch makes once."""
        return [call for call in self.calls if call[1] != _KERNEL_CEILINGS]


def _ok(**fields: object) -> dict:
    return {"success": True, "result": {"status": _KERNEL_STATUS_OK, **fields}}


def _fusion(doc_ids: list[int], scores: list[float], **extra: object) -> dict:
    return _ok(doc_ids=doc_ids, scores=scores, **extra)


def _candidates() -> list[RetrievalCandidate]:
    return [
        RetrievalCandidate(id="c0", score=0.9, metadata={"lang": "py"}),
        RetrievalCandidate(id="c1", score=0.4, metadata={"lang": "rs"}),
    ]


IDENTITY_SIMILARITY = [1.0, 0.2, 0.2, 1.0]


@pytest.fixture(autouse=True)
def _forget_cached_ceilings():
    """The ceiling cache is per process; a test's stub must not leak into the next."""
    import algenta.retrieval_execution as execution

    execution._CEILINGS = None
    yield
    execution._CEILINGS = None


# ── the contract must not drift from the kernels it calls ────────────────────


def test_the_success_status_matches_the_kernel_source():
    """200, not 0. A constant copied across the language boundary is the kind that
    drifts, so it is checked against the source that defines it."""
    source = (_REPO_ROOT / "mojo" / "engine" / "retrieval" / "score.mojo").read_text()
    match = re.search(r"comptime RETR_OK: Int = (\d+)", source)
    assert match, "the retrieval kernels no longer declare RETR_OK"
    assert int(match.group(1)) == _KERNEL_STATUS_OK


def test_every_kernel_function_the_contract_calls_is_in_the_packaged_contract():
    """A renamed kernel function must fail here, not at a caller's first search."""
    payload = json.loads(
        (_ALGENTA / "algenta" / "runtime_library_contract.json").read_text()
    )
    by_module = {
        module["name"]: {function["name"] for function in module["functions"]}
        for module in payload["modules"]
    }
    expected = {
        _KERNEL_SCORE: {
            _KERNEL_HYBRID_RANK,
            _KERNEL_MMR_SELECT,
            _KERNEL_CEILINGS,
            _KERNEL_STATUS_NAME,
        },
        _KERNEL_FUSE: {_KERNEL_RRF_FUSE, _KERNEL_RRF_PROVENANCE},
    }
    for module, functions in expected.items():
        assert module in by_module, f"{module} is not in the packaged runtime contract"
        missing = functions - by_module[module]
        assert not missing, f"{module} no longer exposes {sorted(missing)}"


def test_the_ceilings_are_read_from_the_kernel_before_a_payload_is_sent():
    """Not restated in Python. A limit copied here would drift from the applied one."""
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [0.03])})
    hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)], top_k=1)
    assert runtime.calls[0][1] == _KERNEL_CEILINGS


def test_a_payload_over_the_kernel_s_own_ceiling_is_refused_here():
    """With the caller's own numbers still in scope, rather than downstream."""
    tight = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [0.03])})
    tight.scripts[_KERNEL_CEILINGS] = {
        "success": True,
        "result": [3, 1, 1 << 52, 1 << 26],
    }
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            tight,
            lanes={"a": [("x", 1.0)], "b": [("y", 1.0)], "c": [("z", 1.0)]},
            top_k=3,
        )
    assert "the installed kernels enforce" in str(caught.value)


def test_a_kernel_rejection_carries_the_kernel_s_own_name_for_the_defect():
    """A bare status number is not a diagnosis, so the kernel is asked what it means."""
    runtime = StubRuntime(
        **{
            _KERNEL_RRF_FUSE: {
                "success": True,
                "result": {"status": 209, "doc_ids": [], "scores": []},
            },
            _KERNEL_STATUS_NAME: {"success": True, "result": "rrf_k_not_positive"},
        }
    )
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "retrieval_kernel_rejected"
    assert "rrf_k_not_positive" in str(caught.value)
    assert "status 209" in str(caught.value)


# ── the central rule ──────────────────────────────────────────────────────────


def test_an_unavailable_backend_raises_and_names_the_missing_dependency():
    """The defect this contract exists to prevent: a missing engine returning [].

    `faiss` is genuinely absent here, so this is the real failure, not a simulated one —
    and the error names `faiss` rather than saying "unavailable", because an operator can
    install a named package and cannot act on an adjective.
    """
    with pytest.raises(RetrievalBackendUnavailableError) as caught:
        vector_search(
            StubRuntime(), query_vector=[1.0, 0.0], collection="docs", backend="dense"
        )
    error = caught.value
    assert error.code == "retrieval_backend_unavailable"
    assert error.backend == "dense"
    assert "faiss" in error.missing
    assert error.verb == "vector_search"


def test_the_governed_collection_names_its_own_missing_dependency():
    """The status and the governed verbs must name the same missing thing.

    Asserted as an invariant, not as one machine's answer: whether the governed
    collection is installed -- and how completely -- decides whether these verbs refuse
    at all, so pinning a literal here made the test a statement about the developer's
    laptop. What must hold everywhere is that `backend_status` and the call agree.
    """
    status = backend_status("index")
    calls = (
        ("remember", lambda: remember(StubRuntime(), content="hello", collection="c")),
        ("recall", lambda: recall(StubRuntime(), query="hello", collection="c")),
        ("compact", lambda: compact(StubRuntime(), collection="c")),
    )
    if status.available is False:
        assert status.missing, "an unavailable backend must name what is missing"
        for verb, call in calls:
            with pytest.raises(RetrievalBackendUnavailableError) as caught:
                call()
            assert caught.value.backend == "index"
            assert caught.value.verb == verb
            assert caught.value.missing == status.missing
        return
    for _verb, call in calls:
        try:
            call()
        except RetrievalBackendUnavailableError as exc:
            pytest.fail(
                "backend_status called the index backend available and the call "
                f"disagreed, naming {exc.missing}"
            )
        except RetrievalError:
            # The stub runtime cannot really serve a store; that is not a claim about
            # the backend's availability, which is all this test is about.
            pass


def test_the_unavailable_message_says_why_it_is_not_an_empty_result():
    """A caller reading the message must learn the distinction, not just the failure."""
    with pytest.raises(RetrievalBackendUnavailableError) as caught:
        recall(StubRuntime(), query="hello")
    message = str(caught.value)
    assert "is not available" in message
    assert "empty result" in message


def test_backend_status_reports_the_truth_per_backend():
    """`available` has to mean "a call will not refuse for a missing dependency".

    Which of faiss and the governed collection is installed is a property of the
    machine, so this asserts the shape of the answer and its agreement with the
    execution half, not a fixed verdict. The old form asserted fixed verdicts and so
    reported a *correctly* configured machine as broken.
    """
    for name in BACKENDS:
        if name == "local":
            continue
        status = backend_status(name)
        assert status.available in (True, False), name
        if status.available is False:
            assert status.missing, f"{name}: unavailable but named nothing to install"
            for entry in status.missing:
                assert entry and not entry.endswith("."), f"{name}: {entry!r}"
            assert status.detail, f"{name}: unavailable with no explanation"
        else:
            assert status.missing == (), name


def test_the_local_backend_is_undetermined_without_a_runtime():
    """Not False. Its kernels live in the installed shard, so with nothing to ask there
    is no answer, and False would be a claim this cannot support."""
    status = backend_status("local")
    assert status.available is None
    assert status.missing == ()
    assert "runtime" in status.detail


def test_the_local_backend_resolves_against_a_runtime():
    assert backend_status("local", StubRuntime()).available is True
    absent = StubRuntime()
    absent.scripts.pop(_KERNEL_CEILINGS)
    resolved = backend_status("local", absent)
    assert resolved.available is False
    assert resolved.missing == (f"{_KERNEL_SCORE}.{_KERNEL_CEILINGS}",)


def test_a_missing_kernel_module_is_an_unavailable_backend_not_an_empty_ranking():
    runtime = StubRuntime(
        **{
            _KERNEL_RRF_FUSE: {
                "success": False,
                "error_code": "module_not_registered",
                "error": "Unknown runtime library 'retrieval.fuse'",
            }
        }
    )
    with pytest.raises(RetrievalBackendUnavailableError) as caught:
        hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.backend == "local"
    assert caught.value.missing == (f"{_KERNEL_FUSE}.{_KERNEL_RRF_FUSE}",)


def test_a_runtime_that_is_not_there_is_an_unavailable_backend():
    runtime = StubRuntime()
    runtime.scripts[_KERNEL_CEILINGS] = {
        "success": False,
        "error_code": "compute_runtime_unavailable",
        "error": "the bundled runtime is not installed",
    }
    with pytest.raises(RetrievalBackendUnavailableError):
        hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)])


# ── the lexical lane, end to end against the real engine ─────────────────────


@_needs_lexical
def test_the_lexical_lane_really_ranks():
    """Deliberately does NOT assert which of `a` and `c` comes first.

    Both tokenize to eight terms and carry each query term exactly once, so BM25 scores
    them identically -- equal to the last float digit, measured. Their order is a
    tie-break, and asserting it made this test fail on a change that altered nothing
    about ranking quality. `test_a_document_that_matches_more_outranks_one_that_matches_once`
    below makes the ordering claim on a corpus where ordering is actually determined.
    """
    result = sparse_search(
        StubRuntime(), query="tokenize query", documents=DOCUMENTS, top_k=3
    )
    assert isinstance(result, RetrievalResult)
    assert result.backend == "lexical"
    # `b` shares no term with the query, so a real ranking drops it rather than
    # returning it with a zero score.
    assert set(result.ids()) == {"a", "c"}
    assert [hit.rank for hit in result.hits] == list(range(1, len(result.hits) + 1))
    assert all(hit.score > 0.0 for hit in result.hits)
    scores = [hit.score for hit in result.hits]
    assert scores == sorted(scores, reverse=True)


@_needs_lexical
def test_a_document_that_matches_more_outranks_one_that_matches_once():
    """The ordering claim the test above cannot make, on a corpus that determines it."""
    documents = [
        *DOCUMENTS,
        RetrievalDocument(
            id="d",
            text="tokenize query tokenize query tokenize query",
            metadata={"lang": "py"},
        ),
    ]
    result = sparse_search(
        StubRuntime(), query="tokenize query", documents=documents, top_k=4
    )
    assert result.ids()[0] == "d"
    assert result.hits[0].score > result.hits[1].score


@_needs_lexical
def test_a_query_that_matches_nothing_returns_an_empty_result_and_does_not_raise():
    """The other half of the central rule. The backend ran; nothing matched."""
    result = sparse_search(
        StubRuntime(), query="zzz_no_such_identifier", documents=DOCUMENTS, top_k=3
    )
    assert len(result) == 0
    assert result.hits == ()
    assert result.backend == "lexical"


@_needs_lexical
def test_the_score_model_records_the_parameters_that_produced_the_scores():
    """Two searches with different BM25 parameters produce scores that must not be
    compared, so the parameters travel with the result."""
    result = sparse_search(
        StubRuntime(), query="tokenize", documents=DOCUMENTS, top_k=2, k1=1.2, b=0.75
    )
    assert result.score_model == "lexical-bm25(k1=1.2,b=0.75)"


@_needs_lexical
def test_a_filtered_lexical_search_admits_only_matching_metadata():
    unfiltered = sparse_search(
        StubRuntime(), query="tokenize query", documents=DOCUMENTS, top_k=3
    )
    assert set(unfiltered.ids()) == {"a", "c"}
    filtered = filtered_search(
        StubRuntime(),
        lane="sparse",
        query="tokenize query",
        documents=DOCUMENTS,
        filter=RetrievalFilter(where={"lang": "rs"}),
        backend="lexical",
        top_k=3,
    )
    assert filtered.ids() == ["c"]
    assert filtered.lanes == ("filter", "sparse")


@_needs_lexical
def test_an_item_without_the_filtered_key_does_not_match():
    """Absence is not a value, so it cannot satisfy an equality."""
    documents = [*DOCUMENTS, RetrievalDocument(id="d", text="def tokenize(): pass")]
    filtered = filtered_search(
        StubRuntime(),
        lane="sparse",
        query="tokenize",
        documents=documents,
        filter=RetrievalFilter(where={"lang": "py"}),
        backend="lexical",
        top_k=5,
    )
    assert "d" not in filtered.ids()


# ── the same rule from the other side: OUR windowing must not empty a result ──
#
# The unavailable-backend half of the central rule is asserted above. This half is the
# same defect class arriving by the opposite route: the engine is present, it ran, a
# document matches both the query and the filter — and a candidate window applied
# BEFORE the filter drops it, leaving `hits=()` under a success status. These four
# assertions run against the real index, and they must RUN rather than skip: a
# `skipif(engine missing)` here would pass wherever the engine happens to be installed
# and stay silent in exactly the environment where the defect would ship.


def _require_lexical_engine() -> None:
    """The lexical engine is a hard requirement of these tests, not a condition."""
    status = backend_status("lexical")
    assert status.available is True, (
        "the lexical index must be importable for this reproduction to mean anything; "
        f"backend_status reported {status}"
    )


# Eleven short documents repeat the query term and are tagged 'py'; the twelfth is long,
# mentions the term once, and is the ONLY document tagged 'rs'. BM25 normalises by
# length, so the one document that satisfies both the query and the filter is the
# WORST-scoring match in the corpus — the index ranks it twelfth. That is what makes
# this a reproduction of a candidate window rather than a smoke test of a filter: with
# top_k=1 any window of `max(top_k * 8, top_k)` candidates stops at eight.
_WINDOW_CORPUS = [
    *(
        RetrievalDocument(
            id=f"py-{position}",
            text="def tokenize(): tokenize()",
            metadata={"lang": "py"},
        )
        for position in range(11)
    ),
    RetrievalDocument(
        id="rs-target",
        text="fn helper() { let padding = 1; } " * 8 + " fn tokenize() {}",
        metadata={"lang": "rs"},
    ),
]
_WINDOW_ESCAPE_RANK = 12


def _target_is_outside_the_window() -> None:
    """Pin the premise: the index really does rank the wanted document last."""
    unfiltered = sparse_search(
        StubRuntime(), query="tokenize", documents=_WINDOW_CORPUS, top_k=len(_WINDOW_CORPUS)
    )
    assert unfiltered.ids()[-1] == "rs-target"
    assert unfiltered.hits[-1].rank == _WINDOW_ESCAPE_RANK
    # Beyond a window of eight, which is what top_k=1 would have asked for.
    assert _WINDOW_ESCAPE_RANK > max(1 * 8, 1)


def test_a_filtered_search_returns_a_match_the_index_ranked_outside_any_window():
    """The critical case: one document matches the query AND the filter, and the index
    ranks it last. An empty answer here would say "nothing matched" about a corpus where
    something did, so the filter is applied before anything is truncated."""
    _require_lexical_engine()
    _target_is_outside_the_window()
    filtered = filtered_search(
        StubRuntime(),
        lane="sparse",
        query="tokenize",
        documents=_WINDOW_CORPUS,
        filter=RetrievalFilter(where={"lang": "rs"}),
        backend="lexical",
        top_k=1,
    )
    assert filtered.hits != (), (
        "a document matching both the query and the filter exists, so an empty ranking "
        "here is a wrong answer, not a short one"
    )
    assert filtered.ids() == ["rs-target"]
    # The index's own rank travels through untouched, and it is outside the window that
    # used to bound the search — which is the proof this hit escaped it.
    (contribution,) = [
        lane for lane in filtered.hits[0].lanes if lane.lane == "sparse"
    ]
    assert contribution.rank == _WINDOW_ESCAPE_RANK


def test_a_filtered_search_finds_every_admitted_match_not_the_first_window_of_them():
    """top_k truncates AFTER the filter, so a larger top_k cannot reveal hits a
    smaller one silently lost."""
    _require_lexical_engine()

    def admitted(top_k: int) -> list[str]:
        return filtered_search(
            StubRuntime(),
            lane="sparse",
            query="tokenize",
            documents=_WINDOW_CORPUS,
            filter=RetrievalFilter(where={"lang": "rs"}),
            backend="lexical",
            top_k=top_k,
        ).ids()

    assert admitted(1) == ["rs-target"]
    # Exactly one document is admitted, so a top_k of five returns one hit and not a
    # padded five.
    assert admitted(5) == ["rs-target"]


def test_an_empty_filtered_result_still_means_nothing_matched():
    """Fixing the window must not weaken the half that already worked: a filter that
    admits nothing returns an empty ranking, and it is a real answer."""
    _require_lexical_engine()
    matched = sparse_search(
        StubRuntime(), query="tokenize", documents=_WINDOW_CORPUS, top_k=5
    )
    assert len(matched) > 0  # the corpus does match the query
    filtered = filtered_search(
        StubRuntime(),
        lane="sparse",
        query="tokenize",
        documents=_WINDOW_CORPUS,
        filter=RetrievalFilter(where={"lang": "go"}),
        backend="lexical",
        top_k=5,
    )
    assert filtered.hits == ()  # nothing carries lang='go'; nothing matched


def test_a_score_window_is_applied_to_every_candidate_not_only_the_first_ones():
    """The score bound is a filter like any other, so it too is applied before
    truncation: the lowest-scoring document is reachable through it."""
    _require_lexical_engine()
    ranked = sparse_search(
        StubRuntime(), query="tokenize", documents=_WINDOW_CORPUS, top_k=len(_WINDOW_CORPUS)
    )
    worst = ranked.hits[-1].score
    best = ranked.hits[0].score
    assert worst < best
    filtered = filtered_search(
        StubRuntime(),
        lane="sparse",
        query="tokenize",
        documents=_WINDOW_CORPUS,
        filter=RetrievalFilter(max_score=(worst + best) / 2),
        backend="lexical",
        top_k=1,
    )
    assert filtered.ids() == ["rs-target"]


# ── a lexical request with no documents names what was needed ────────────────


def test_a_filtered_lexical_search_over_a_stored_collection_is_refused():
    """The lexical backend indexes the request's documents and keeps nothing, so
    collection= is the one thing it cannot serve. `sparse_search` already refused this
    pairing; the filtered path refuses it identically instead of reaching the lane with
    no documents to index."""
    with pytest.raises(RetrievalError) as caught:
        filtered_search(
            StubRuntime(),
            lane="sparse",
            query="tokenize",
            collection="notes",
            filter=RetrievalFilter(where={"lang": "rs"}),
            backend="lexical",
            top_k=3,
        )
    assert caught.value.code == "backend_cannot_serve_verb"
    assert "documents=" in str(caught.value)
    with pytest.raises(RetrievalError) as plain:
        sparse_search(
            StubRuntime(), query="tokenize", collection="notes", backend="lexical"
        )
    # One refusal, worded once: the two verbs must not disagree about this.
    assert str(plain.value) == str(caught.value)


def test_a_lexical_request_reaching_the_lane_with_no_documents_is_a_typed_error():
    """Belt and braces at the point of use. Whatever built the request, the lane raises
    a typed error naming what was missing rather than a KeyError on a params key."""
    _require_lexical_engine()
    request = RetrievalRequest(
        verb="filtered_search",
        backend="lexical",
        top_k=3,
        params={"query": "tokenize", "k1": 1.8, "b": 1.0},
        filter=RetrievalFilter(where={"lang": "rs"}),
    )
    with pytest.raises(RetrievalError) as caught:
        request.run(StubRuntime())
    assert not isinstance(caught.value, KeyError)
    assert caught.value.code == "backend_cannot_serve_verb"
    assert "documents=" in str(caught.value)


@_needs_lexical
def test_provenance_answers_why_this_ranked_first():
    result = sparse_search(
        StubRuntime(), query="tokenize query", documents=DOCUMENTS, top_k=3
    )
    report = provenance(result)
    assert report.backend == "lexical"
    assert report.score_model == result.score_model
    first = report.items[0]
    assert first.rank == 1
    assert first.id == result.ids()[0]
    explanation = first.explanation
    # Everything a caller needs to answer the question without reading any source.
    assert "ranked 1" in explanation
    assert "sparse lane" in explanation
    assert "backend=lexical" in explanation
    assert "lexical-bm25" in explanation
    assert report.why(first.id) == explanation


@_needs_lexical
def test_a_lexical_result_feeds_a_fusion_without_a_conversion_step():
    lexical = sparse_search(
        StubRuntime(), query="tokenize query", documents=DOCUMENTS, top_k=3
    )
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0, 1], [0.033, 0.016])})
    fused = hybrid_search(
        runtime, dense=[("c", 0.8)], sparse=lexical, top_k=2, fusion="rrf"
    )
    assert fused.ids() == ["c", "a"]
    (_, function, args) = runtime.kernel_calls()[0]
    assert function == _KERNEL_RRF_FUSE
    # The dense lane declared 'c' first, so 'c' is ordinal 0 and the lexical lane's
    # ordinals follow in its own rank order.
    assert args[1] == [1, 2]  # one dense entry, two lexical entries


# ── the local lane: what the contract puts on the wire ───────────────────────


def test_rank_fusion_concatenates_the_lanes_and_declares_each_length():
    """Ranks are derived from position inside each slice, so the payload is the lanes
    end to end plus their lengths — no rank array that could disagree with the order."""
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0, 1, 2], [0.03, 0.02, 0.01])})
    result = hybrid_search(
        runtime,
        dense=[("x", 0.9), ("y", 0.4)],
        sparse=[("y", 2.0), ("z", 1.0)],
        top_k=3,
        fusion="rrf",
    )
    (module, function, args) = runtime.kernel_calls()[0]
    assert (module, function) == (_KERNEL_FUSE, _KERNEL_RRF_FUSE)
    # Ordinals: x=0, y=1 (first seen in the dense lane), z=2.
    assert args[0] == [0, 1, 1, 2]
    assert args[1] == [2, 2]
    assert args[2] == 2  # n_lanes
    assert args[3] == 60.0
    assert args[4] == 3
    assert result.ids() == ["x", "y", "z"]
    assert result.fusion == "rrf"
    assert result.fusion_params == {"rrf_k": 60.0, "lanes": 2}


def test_more_than_two_lanes_fuse_in_the_order_they_were_written():
    """Float addition is not associative, so the lane order is part of the answer."""
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [0.05])})
    result = hybrid_search(
        runtime,
        lanes={"lexical": [("x", 1.0)], "dense": [("x", 0.5)], "graph": [("x", 0.2)]},
        top_k=1,
    )
    (_, _, args) = runtime.kernel_calls()[0]
    assert args[1] == [1, 1, 1]
    assert args[2] == 3
    assert result.lanes == ("lexical", "dense", "graph")
    assert [c.lane for c in result.hits[0].lanes] == ["lexical", "dense", "graph"]


def test_a_lane_that_ran_and_matched_nothing_is_not_a_lane_that_did_not_run():
    """The central rule, one level down. An empty lane fuses; an absent lane is a bug."""
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [0.016])})
    fused = hybrid_search(runtime, dense=[], sparse=[("y", 2.0)], top_k=1)
    (_, _, args) = runtime.kernel_calls()[0]
    assert args[1] == [0, 1]  # the dense lane declared a length of zero
    assert fused.ids() == ["y"]
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(StubRuntime(), sparse=[("y", 2.0)])
    assert "hybrid in name only" in str(caught.value)
    assert "dense=[]" in str(caught.value)


def test_a_fused_hit_records_the_rank_it_had_in_each_lane_and_none_where_absent():
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0, 2], [0.03, 0.01])})
    result = hybrid_search(
        runtime,
        dense=[("x", 0.9), ("y", 0.4)],
        sparse=[("y", 2.0), ("z", 1.0)],
        top_k=2,
    )
    lanes = {c.lane: c for c in result.hits[0].lanes}
    assert result.hits[0].id == "x"
    assert lanes["dense"].rank == 1
    assert lanes["dense"].score == 0.9
    # x was never returned by the sparse lane. It has no rank there, and no score.
    assert lanes["sparse"].rank is None
    assert lanes["sparse"].score is None
    assert lanes["sparse"].contribution is None
    assert "not returned by this lane" in lanes["sparse"].describe()


def test_explain_asks_the_kernel_for_the_attribution_table():
    """The contributions are the kernel's numbers. None is computed here."""
    runtime = StubRuntime(
        **{
            _KERNEL_RRF_FUSE: _fusion([0], [0.0328]),
            _KERNEL_RRF_PROVENANCE: _ok(
                doc_ids=[0, 0],
                lanes=[0, 1],
                ranks=[1, 1],
                contributions=[0.016393, 0.016393],
                fused_scores=[0.032786, 0.032786],
                fused_positions=[0, 0],
                max_attribution_residual=0.0,
            ),
        }
    )
    result = hybrid_search(
        runtime, dense=[("x", 0.91)], sparse=[("x", 0.80)], top_k=1, explain=True
    )
    assert [call[1] for call in runtime.kernel_calls()] == [
        _KERNEL_RRF_FUSE,
        _KERNEL_RRF_PROVENANCE,
    ]
    lanes = {c.lane: c for c in result.hits[0].lanes}
    assert lanes["dense"].contribution == pytest.approx(0.016393)
    assert lanes["sparse"].contribution == pytest.approx(0.016393)
    assert result.attribution_residual == 0.0
    assert "contributing 0.016393" in provenance(result).why("x")


def test_an_absent_attribution_certificate_is_none_not_zero():
    """The kernels spell absence as a negative residual; it must not travel on as one."""
    runtime = StubRuntime(
        **{
            _KERNEL_RRF_FUSE: _fusion([0], [0.03]),
            _KERNEL_RRF_PROVENANCE: _ok(
                doc_ids=[0],
                lanes=[0],
                ranks=[1],
                contributions=[0.03],
                fused_scores=[0.03],
                fused_positions=[0],
                max_attribution_residual=-1.0,
            ),
        }
    )
    result = hybrid_search(
        runtime, dense=[("x", 1.0)], sparse=[], top_k=1, explain=True
    )
    assert result.attribution_residual is None


def test_no_attribution_is_asked_for_when_explain_is_not_set():
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [0.03])})
    result = hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)], top_k=1)
    assert [call[1] for call in runtime.kernel_calls()] == [_KERNEL_RRF_FUSE]
    assert result.hits[0].lanes[0].contribution is None
    assert result.attribution_residual is None


def test_linear_fusion_sends_two_aligned_score_arrays_and_reads_back_both_parts():
    runtime = StubRuntime(
        **{
            _KERNEL_HYBRID_RANK: _fusion(
                [0, 1],
                [0.55, 0.30],
                dense_part=[0.225, 0.10],
                sparse_part=[0.325, 0.20],
                dominant_lane=[1, 1],
                max_attribution_residual=0.0,
            )
        }
    )
    result = hybrid_search(
        runtime,
        dense=[("x", 0.9), ("y", 0.4)],
        sparse=[("x", 0.65), ("y", 0.4)],
        top_k=2,
        fusion="linear",
        alpha=0.25,
    )
    (module, function, args) = runtime.kernel_calls()[0]
    assert (module, function) == (_KERNEL_SCORE, _KERNEL_HYBRID_RANK)
    assert args[0] == [0.9, 0.4]
    assert args[1] == [0.65, 0.4]
    assert args[2] == 2
    assert args[3] == 0.25
    lanes = {c.lane: c for c in result.hits[0].lanes}
    assert lanes["dense"].contribution == 0.225
    assert lanes["sparse"].contribution == 0.325
    assert result.fusion_params == {"alpha": 0.25}


def test_linear_fusion_refuses_lanes_that_do_not_cover_the_same_candidates():
    """Its kernel has no notion of absence, and a 0.0 would read as 'scored, badly'."""
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(),
            dense=[("x", 0.9), ("y", 0.4)],
            sparse=[("x", 0.65)],
            fusion="linear",
        )
    message = str(caught.value)
    assert "in only one lane" in message
    assert "dense only: y" in message
    assert "fusion='rrf'" in message


def test_linear_fusion_takes_exactly_the_two_named_lanes():
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(),
            lanes={"lexical": [("x", 1.0)], "graph": [("x", 1.0)]},
            fusion="linear",
        )
    assert "exactly the lanes 'dense' and 'sparse'" in str(caught.value)


def test_an_mmr_rerank_sends_the_relevance_and_the_similarity_matrix():
    runtime = StubRuntime(
        **{
            _KERNEL_MMR_SELECT: _ok(
                doc_ids=[1, 0],
                mmr_scores=[0.28, 0.63],
                relevance=[0.4, 0.9],
                max_sim=[0.0, 0.2],
                max_sim_known=[False, True],
            )
        }
    )
    result = rerank(
        runtime,
        candidates=_candidates(),
        similarity=IDENTITY_SIMILARITY,
        method="mmr",
        lambda_mmr=0.7,
        top_k=2,
    )
    (module, function, args) = runtime.kernel_calls()[0]
    assert (module, function) == (_KERNEL_SCORE, _KERNEL_MMR_SELECT)
    assert args[0] == [0.9, 0.4]
    assert args[1] == IDENTITY_SIMILARITY
    assert args[2] == 2
    assert args[3] == 2  # top_k
    assert args[4] == 0.7
    assert result.ids() == ["c1", "c0"]
    assert result.score_model.endswith("(mmr)")


def test_the_first_selected_item_has_no_redundancy_rather_than_zero_redundancy():
    """Nothing had been selected yet, so there was nothing to be redundant with."""
    runtime = StubRuntime(
        **{
            _KERNEL_MMR_SELECT: _ok(
                doc_ids=[0, 1],
                mmr_scores=[0.63, 0.14],
                relevance=[0.9, 0.4],
                max_sim=[0.0, 0.2],
                max_sim_known=[False, True],
            )
        }
    )
    result = rerank(
        runtime, candidates=_candidates(), similarity=IDENTITY_SIMILARITY, top_k=2
    )
    first = {c.lane: c for c in result.hits[0].lanes}
    second = {c.lane: c for c in result.hits[1].lanes}
    assert first["redundancy"].score is None
    assert second["redundancy"].score == 0.2
    assert first["input_relevance"].score == 0.9


# ── kernel failures are not short rankings ───────────────────────────────────


def test_a_non_zero_kernel_status_raises_rather_than_returning_what_it_holds():
    runtime = StubRuntime(
        **{
            _KERNEL_RRF_FUSE: {
                "success": True,
                "result": {"status": 207, "doc_ids": [0, 1], "scores": [1.0, 0.5]},
            }
        }
    )
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "retrieval_kernel_rejected"
    assert "no ranking was produced" in str(caught.value)


@pytest.mark.parametrize(
    "result",
    [
        {"status": _KERNEL_STATUS_OK, "doc_ids": [0]},
        {"status": _KERNEL_STATUS_OK, "scores": [1.0]},
        {"status": _KERNEL_STATUS_OK, "doc_ids": [0, 1], "scores": [1.0]},
        {"status": _KERNEL_STATUS_OK, "doc_ids": [0], "scores": ["high"]},
        {"status": "ok", "doc_ids": [], "scores": []},
        {"status": _KERNEL_STATUS_OK, "doc_ids": [99], "scores": [1.0]},
    ],
)
def test_a_malformed_kernel_result_is_reported_not_salvaged(result):
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: {"success": True, "result": result}})
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "retrieval_kernel_contract_mismatch"


def test_a_linear_fusion_missing_its_decomposition_is_reported():
    runtime = StubRuntime(
        **{_KERNEL_HYBRID_RANK: _fusion([0], [0.5], dense_part=[0.25])}
    )
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            runtime, dense=[("x", 0.9)], sparse=[("x", 0.1)], fusion="linear"
        )
    assert caught.value.code == "retrieval_kernel_contract_mismatch"


def test_an_unrelated_kernel_failure_keeps_its_own_code():
    runtime = StubRuntime(
        **{
            _KERNEL_RRF_FUSE: {
                "success": False,
                "error_code": "invalid_arguments",
                "error": "bad shape",
            }
        }
    )
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "invalid_arguments"
    assert not isinstance(caught.value, RetrievalBackendUnavailableError)


# ── the runtime must be in this process ──────────────────────────────────────


def test_a_runtime_carrying_a_base_url_is_refused():
    class Remote:
        base_url = "https://example.invalid"

        def execute(self, *args, **kwargs):  # pragma: no cover - never reached
            raise AssertionError("a remote runtime must not be called")

    with pytest.raises(RetrievalError) as caught:
        hybrid_search(Remote(), dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "retrieval_requires_local_runtime"


def test_a_runtime_in_another_mode_is_refused():
    class Hosted(StubRuntime):
        _runtime_config = {"mode": "cloud"}

    with pytest.raises(RetrievalError) as caught:
        hybrid_search(Hosted(), dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "retrieval_requires_local_runtime"


def test_an_object_with_no_execute_is_refused():
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(object(), dense=[("x", 1.0)], sparse=[("x", 1.0)])
    assert caught.value.code == "retrieval_requires_local_runtime"


# ── builder validation: the caller's argument, quoted back ───────────────────


def test_an_unknown_backend_lists_the_ones_that_exist():
    with pytest.raises(RetrievalError) as caught:
        vector_search(
            StubRuntime(),
            query_vector=[1.0],
            collection="docs",
            backend="pinecone",
        )
    assert caught.value.code == "unknown_backend"
    assert "local" in str(caught.value)


def test_a_backend_that_cannot_serve_the_verb_says_which_ones_can():
    with pytest.raises(RetrievalError) as caught:
        sparse_search(StubRuntime(), query="q", documents=DOCUMENTS, backend="local")
    assert caught.value.code == "backend_cannot_serve_verb"
    assert "lexical" in str(caught.value)


def test_there_is_no_local_dense_or_local_sparse_lane():
    """Both need an index, and this module contains none by design."""
    for call in (
        lambda: vector_search(
            StubRuntime(), query_vector=[1.0], collection="c", backend="local"
        ),
        lambda: sparse_search(
            StubRuntime(), query="q", collection="c", backend="local"
        ),
        lambda: filtered_search(
            StubRuntime(),
            lane="dense",
            filter={"where": {"lang": "py"}},
            query_vector=[1.0],
            collection="c",
            backend="local",
        ),
    ):
        with pytest.raises(RetrievalError) as caught:
            call()
        assert caught.value.code == "backend_cannot_serve_verb"


def test_a_cross_encoder_is_not_served_locally_and_says_what_is():
    with pytest.raises(RetrievalError) as caught:
        rerank(
            StubRuntime(),
            candidates=_candidates(),
            method="cross_encoder",
            backend="local",
        )
    assert caught.value.code == "backend_cannot_serve_verb"
    assert "index" in str(caught.value)


def test_the_governed_verbs_refuse_an_ephemeral_backend():
    """A store that does not outlive the call is not a memory."""
    for call in (
        lambda: remember(StubRuntime(), content="x", backend="local"),
        lambda: recall(StubRuntime(), query="x", backend="lexical"),
        lambda: compact(StubRuntime(), backend="dense"),
    ):
        with pytest.raises(RetrievalError) as caught:
            call()
        assert caught.value.code == "backend_cannot_serve_verb"


@pytest.mark.parametrize("top_k", [0, -1, MAX_TOP_K + 1, True, 1.5, "3"])
def test_a_top_k_outside_its_range_is_refused(top_k):
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(), dense=[("x", 1.0)], sparse=[("x", 1.0)], top_k=top_k
        )
    assert caught.value.code == "invalid_arguments"


def test_recall_caps_top_k_where_the_hosted_surface_caps_it():
    """One bound, so a request this builder accepts is one that surface accepts."""
    with pytest.raises(RetrievalError) as caught:
        recall(StubRuntime(), query="q", top_k=129)
    assert "1..128" in str(caught.value)


@pytest.mark.parametrize("query", ["", "   ", 7, None])
def test_an_empty_query_is_refused(query):
    with pytest.raises(RetrievalError) as caught:
        sparse_search(StubRuntime(), query=query, documents=DOCUMENTS)
    assert caught.value.code == "invalid_arguments"


def test_two_sources_are_refused_and_so_is_none():
    with pytest.raises(RetrievalError) as caught:
        sparse_search(
            StubRuntime(), query="q", documents=DOCUMENTS, collection="stored"
        )
    assert "exactly one" in str(caught.value)
    with pytest.raises(RetrievalError) as caught:
        sparse_search(StubRuntime(), query="q")
    assert "needs one of" in str(caught.value)


def test_a_weight_belonging_to_the_other_fusion_is_refused_not_ignored():
    """A weight that silently does nothing is worse than one that is refused."""
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(),
            dense=[("x", 1.0)],
            sparse=[("x", 1.0)],
            fusion="rrf",
            alpha=0.3,
        )
    assert "alpha" in str(caught.value)
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(),
            dense=[("x", 1.0)],
            sparse=[("x", 1.0)],
            fusion="linear",
            rrf_k=10.0,
        )
    assert "rrf_k" in str(caught.value)


def test_a_parameter_belonging_to_the_other_rerank_method_is_refused():
    with pytest.raises(RetrievalError):
        rerank(
            StubRuntime(),
            candidates=_candidates(),
            method="cross_encoder",
            backend="index",
            lambda_mmr=0.5,
        )
    with pytest.raises(RetrievalError):
        rerank(
            StubRuntime(),
            candidates=_candidates(),
            similarity=IDENTITY_SIMILARITY,
            method="mmr",
            bias=0.1,
        )


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"fusion": "linear", "alpha": 1.5}, "alpha"),
        ({"fusion": "linear", "alpha": -0.1}, "alpha"),
        ({"fusion": "rrf", "rrf_k": -1.0}, "non-negative"),
        ({"fusion": "rrf", "rrf_k": float("nan")}, "finite"),
    ],
)
def test_a_weight_outside_its_range_is_refused(kwargs, needle):
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(), dense=[("x", 1.0)], sparse=[("x", 1.0)], **kwargs
        )
    assert needle in str(caught.value)


def test_the_admissible_rrf_k_range_is_exactly_the_kernel_s():
    """The kernel admits k = 0 because ranks are 1-based, so this must too — one
    invariant at one strength."""
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [1.0])})
    result = hybrid_search(
        runtime, dense=[("x", 1.0)], sparse=[("x", 1.0)], rrf_k=0.0, top_k=1
    )
    assert runtime.kernel_calls()[0][2][3] == 0.0
    assert result.fusion_params["rrf_k"] == 0.0


@pytest.mark.parametrize(("k1", "b"), [(-0.1, 1.0), (1.8, 1.5), (1.8, -0.2)])
def test_bm25_parameters_outside_their_ranges_are_refused(k1, b):
    with pytest.raises(RetrievalError):
        sparse_search(StubRuntime(), query="q", documents=DOCUMENTS, k1=k1, b=b)


def test_a_filtered_sparse_search_validates_bm25_the_same_way_the_plain_one_does():
    with pytest.raises(RetrievalError):
        filtered_search(
            StubRuntime(),
            lane="sparse",
            filter={"where": {"lang": "py"}},
            query="q",
            documents=DOCUMENTS,
            backend="lexical",
            b=2.0,
        )


def test_an_unknown_metric_and_an_unknown_fusion_are_refused():
    with pytest.raises(RetrievalError):
        vector_search(
            StubRuntime(),
            query_vector=[1.0],
            collection="docs",
            metric="jaccard",
        )
    with pytest.raises(RetrievalError):
        hybrid_search(
            StubRuntime(), dense=[("x", 1.0)], sparse=[("x", 1.0)], fusion="borda"
        )


# ── filters that admit nothing are contradictions, not precedence questions ──


def test_an_id_in_both_include_and_exclude_is_refused():
    with pytest.raises(RetrievalError) as caught:
        RetrievalFilter(include_ids=("a", "b"), exclude_ids=("b",))
    assert "contradicts itself" in str(caught.value)


def test_an_inverted_score_window_is_refused():
    with pytest.raises(RetrievalError) as caught:
        RetrievalFilter(min_score=0.9, max_score=0.1)
    assert "admits nothing" in str(caught.value)


def test_an_empty_id_list_is_refused_rather_than_read_as_no_restriction():
    with pytest.raises(RetrievalError):
        RetrievalFilter(include_ids=())
    with pytest.raises(RetrievalError):
        RetrievalFilter(exclude_ids=[])


def test_a_repeated_id_in_a_filter_is_refused():
    with pytest.raises(RetrievalError) as caught:
        RetrievalFilter(include_ids=("a", "a"))
    assert "repeats a" in str(caught.value)


def test_a_non_finite_score_bound_is_refused():
    with pytest.raises(RetrievalError):
        RetrievalFilter(min_score=float("inf"))
    with pytest.raises(RetrievalError):
        RetrievalFilter(max_score=float("nan"))


def test_filtered_search_requires_a_filter():
    with pytest.raises(RetrievalError) as caught:
        filtered_search(
            StubRuntime(),
            lane="sparse",
            filter=None,
            query="q",
            documents=DOCUMENTS,
            backend="lexical",
        )
    assert caught.value.code == "invalid_arguments"


def test_a_lane_a_backend_does_not_have_is_refused():
    with pytest.raises(RetrievalError) as caught:
        filtered_search(
            StubRuntime(),
            lane="dense",
            filter={"where": {"lang": "py"}},
            query_vector=[1.0],
            collection="c",
            backend="lexical",
        )
    assert caught.value.code == "backend_cannot_serve_verb"


def test_a_filter_given_as_a_mapping_goes_through_the_same_validation():
    with pytest.raises(RetrievalError):
        filtered_search(
            StubRuntime(),
            lane="sparse",
            filter={"min_score": 1.0, "max_score": 0.0},
            query="q",
            documents=DOCUMENTS,
            backend="lexical",
        )


# ── payload shapes the kernel would misread ──────────────────────────────────


def test_a_similarity_matrix_of_the_wrong_size_is_refused_with_the_reason():
    with pytest.raises(RetrievalError) as caught:
        rerank(StubRuntime(), candidates=_candidates(), similarity=[1.0, 0.2, 0.2])
    assert "shift every row" in str(caught.value)


def test_mmr_requires_the_similarity_matrix_rather_than_deriving_one():
    with pytest.raises(RetrievalError) as caught:
        rerank(StubRuntime(), candidates=_candidates())
    assert "similarity= is required" in str(caught.value)
    assert "second definition of similarity" in str(caught.value)


def test_a_cross_encoder_refuses_a_similarity_matrix():
    with pytest.raises(RetrievalError) as caught:
        rerank(
            StubRuntime(),
            candidates=_candidates(),
            similarity=IDENTITY_SIMILARITY,
            method="cross_encoder",
            backend="index",
        )
    assert "has no role" in str(caught.value)


def test_a_candidate_without_a_score_is_refused_rather_than_zero_filled():
    with pytest.raises(RetrievalError) as caught:
        rerank(
            StubRuntime(),
            candidates=[RetrievalCandidate(id="a")],
            similarity=[1.0],
        )
    assert "not a zero score" in str(caught.value)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_a_non_finite_value_is_refused(bad):
    with pytest.raises(RetrievalError) as caught:
        vector_search(StubRuntime(), query_vector=[1.0, bad], collection="docs")
    assert "finite" in str(caught.value)
    with pytest.raises(RetrievalError):
        hybrid_search(StubRuntime(), dense=[("x", bad)], sparse=[("x", 1.0)])


def test_an_all_zero_query_vector_is_refused_for_cosine():
    """Cosine divides by the norm; there is no similarity to a zero vector."""
    with pytest.raises(RetrievalError) as caught:
        vector_search(StubRuntime(), query_vector=[0.0, 0.0], collection="docs")
    assert "no ranking exists" in str(caught.value)
    # The same vector is a legitimate inner-product query, so it gets past validation
    # and fails on the backend instead — which is genuinely absent here.
    with pytest.raises(RetrievalBackendUnavailableError):
        vector_search(
            StubRuntime(), query_vector=[0.0, 0.0], collection="docs", metric="ip"
        )


def test_a_repeated_id_is_refused_in_documents_candidates_and_lanes():
    with pytest.raises(RetrievalError):
        sparse_search(
            StubRuntime(),
            query="q",
            documents=[
                RetrievalDocument(id="a", text="one"),
                RetrievalDocument(id="a", text="two"),
            ],
        )
    with pytest.raises(RetrievalError):
        rerank(
            StubRuntime(),
            candidates=[
                RetrievalCandidate(id="a", score=1.0),
                RetrievalCandidate(id="a", score=0.5),
            ],
            similarity=IDENTITY_SIMILARITY,
        )
    with pytest.raises(RetrievalError):
        hybrid_search(
            StubRuntime(), dense=[("x", 1.0), ("x", 0.5)], sparse=[("x", 1.0)]
        )


def test_an_empty_corpus_is_refused_because_it_is_not_a_query_that_matched_nothing():
    with pytest.raises(RetrievalError) as caught:
        sparse_search(StubRuntime(), query="q", documents=[])
    assert "nothing to index" in str(caught.value)
    with pytest.raises(RetrievalError) as caught:
        rerank(StubRuntime(), candidates=[], similarity=[])
    assert "nothing to rank" in str(caught.value)


def test_hybrid_search_refuses_mixing_the_two_request_shapes():
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(),
            dense=[("x", 1.0)],
            sparse=[("x", 1.0)],
            query="q",
            collection="stored",
        )
    assert "never both" in str(caught.value)
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(
            StubRuntime(),
            dense=[("x", 1.0)],
            sparse=[("x", 1.0)],
            lanes={"a": [], "b": []},
        )
    assert "same request written two ways" in str(caught.value)


def test_one_lane_is_not_a_hybrid():
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(StubRuntime(), lanes={"only": [("x", 1.0)]})
    assert "hybrid in name only" in str(caught.value)


def test_two_lanes_may_not_share_a_name():
    with pytest.raises(RetrievalError) as caught:
        hybrid_search(StubRuntime(), lanes={"a": [], "b": [], "": []})
    assert "non-empty name" in str(caught.value)


# ── the builder ──────────────────────────────────────────────────────────────


def test_the_builder_and_the_verb_produce_the_same_result():
    script = {_KERNEL_RRF_FUSE: _fusion([0, 1], [0.03, 0.02])}
    direct = hybrid_search(
        StubRuntime(**script), dense=[("x", 0.9)], sparse=[("y", 2.0)], top_k=2
    )
    built = (
        Retrieval(backend="local", top_k=2)
        .hybrid(dense=[("x", 0.9)], sparse=[("y", 2.0)])
        .run(StubRuntime(**script))
    )
    assert built.ids() == direct.ids()
    assert built.score_model == direct.score_model


def test_the_builder_validates_the_same_way_the_verb_does():
    with pytest.raises(RetrievalError) as caught:
        Retrieval(backend="local", top_k=0).hybrid(
            dense=[("x", 1.0)], sparse=[("x", 1.0)]
        ).run(StubRuntime())
    assert caught.value.code == "invalid_arguments"


def test_a_builder_with_two_verbs_raises_rather_than_forgetting_the_first():
    builder = Retrieval(backend="local").hybrid(
        dense=[("x", 1.0)], sparse=[("x", 1.0)]
    )
    with pytest.raises(RetrievalError) as caught:
        builder.rerank_with(candidates=_candidates(), similarity=IDENTITY_SIMILARITY)
    assert "one verb" in str(caught.value)


def test_a_builder_with_no_verb_raises():
    with pytest.raises(RetrievalError) as caught:
        Retrieval().run(StubRuntime())
    assert "no verb" in str(caught.value)


def test_the_builder_rejects_an_unknown_backend_at_construction():
    with pytest.raises(RetrievalError):
        Retrieval(backend="chroma")


# ── provenance is not relabellable ───────────────────────────────────────────


def _fused_result() -> RetrievalResult:
    runtime = StubRuntime(**{_KERNEL_RRF_FUSE: _fusion([0], [0.03])})
    return hybrid_search(
        runtime, dense=[("x", 0.9)], sparse=[("x", 0.8)], top_k=1
    )


def test_provenance_refuses_to_be_told_the_wrong_backend():
    result = _fused_result()
    assert provenance(result, backend="local").backend == "local"
    with pytest.raises(RetrievalError) as caught:
        provenance(result, backend="lexical")
    assert "was served by" in str(caught.value)


def test_provenance_over_an_id_that_did_not_rank_raises():
    with pytest.raises(KeyError):
        provenance(_fused_result()).why("nope")


def test_provenance_needs_a_result():
    with pytest.raises(RetrievalError):
        provenance({"hits": []})


def test_result_provenance_matches_the_free_function():
    result = _fused_result()
    assert result.provenance() == provenance(result)


def test_a_fusion_explains_which_lane_contributed_what():
    explanation = provenance(_fused_result()).why("x")
    assert "fused by rrf(" in explanation
    assert "dense lane (backend=local) rank 1, score 0.9" in explanation
    assert "sparse lane (backend=local) rank 1, score 0.8" in explanation


# ── the governed collection's payload maps onto one vocabulary ───────────────
# The backend itself is absent here, so these exercise the mapping directly with a
# response shaped like the memory surface's. That mapping is what makes one provenance
# report cover a governed recall and a local fusion alike.


RECALL_PAYLOAD = {
    "collection": "notes",
    "score_model_version": "ame-score-1",
    "hits": [
        {
            "rank": 1,
            "owner_id": "fact-1",
            "owner_type": "fact",
            "content": "the deploy window is Tuesday",
            "score": 0.82,
            "score_decomposition": {
                "score_model_version": "ame-score-1",
                "dense_similarity": 0.71,
                "sparse_score": 0.44,
                "recency_decay": 0.90,
                "penalties": {"superseded": -0.25},
            },
            "provenance": {"source_episode_id": "ep-7", "source_uri": "chat://1"},
            "temporal": {"valid_from": "2026-01-01T00:00:00Z", "superseded": False},
            "policy_id": "internal",
            "token_count": 9,
        }
    ],
}


def test_a_recall_decomposition_becomes_lane_contributions():
    result = _result_from_recall_payload(
        RECALL_PAYLOAD, verb="recall", backend="index", top_k=8
    )
    assert result.collection == "notes"
    assert result.score_model == "ame-score-1"
    hit = result.hits[0]
    assert hit.id == "fact-1"
    terms = {c.lane: c for c in hit.lanes}
    assert terms["dense_similarity"].score == 0.71
    assert terms["sparse_score"].score == 0.44
    # A score term is not an ordering, so it carries no rank.
    assert terms["dense_similarity"].rank is None
    # A penalty is named, never silent.
    assert terms["penalty:superseded"].score == -0.25
    assert hit.metadata["source_episode_id"] == "ep-7"
    assert hit.metadata["policy_id"] == "internal"


def test_a_governed_recall_explains_the_same_way_a_local_fusion_does():
    result = _result_from_recall_payload(
        RECALL_PAYLOAD, verb="recall", backend="index", top_k=8
    )
    explanation = provenance(result).why("fact-1")
    assert "ranked 1" in explanation
    assert "dense_similarity" in explanation
    assert "penalty:superseded" in explanation
    assert "backend=index" in explanation


def test_a_recall_that_matched_nothing_maps_to_an_empty_result():
    result = _result_from_recall_payload(
        {"collection": "notes", "hits": []}, verb="recall", backend="index", top_k=8
    )
    assert len(result) == 0
    assert result.score_model == "governed-recall"


def test_a_recall_response_with_no_hits_key_is_refused_not_read_as_empty():
    """`hits: []` is the engine saying nothing matched. NO hits key is the engine saying
    something this contract does not understand, and the two must not collapse into the
    same successful empty ranking — the same rule the compaction report applies to
    `candidates_considered`."""
    for payload in (
        {"collection": "notes"},  # nothing about a ranking at all
        {"collection": "notes", "results": []},  # the key spelled differently
        {"collection": "notes", "matches": [{"owner_id": "fact-1", "score": 1.0}]},
    ):
        with pytest.raises(RetrievalError) as caught:
            _result_from_recall_payload(
                payload, verb="recall", backend="index", top_k=8
            )
        assert caught.value.code == "retrieval_engine_contract_mismatch"
        assert "no hits key" in str(caught.value)
        # The keys it did carry are named, so an operator can see the shape it got.
        for key in payload:
            assert key in str(caught.value)
    # And the honest empty answer still comes through as one.
    empty = _result_from_recall_payload(
        {"collection": "notes", "hits": []}, verb="recall", backend="index", top_k=8
    )
    assert empty.hits == ()


def test_a_hits_key_that_is_not_a_list_says_what_it_was():
    with pytest.raises(RetrievalError) as caught:
        _result_from_recall_payload(
            {"hits": None}, verb="recall", backend="index", top_k=8
        )
    assert caught.value.code == "retrieval_engine_contract_mismatch"
    assert "NoneType" in str(caught.value)


def test_a_hit_with_no_identity_is_rejected():
    with pytest.raises(RetrievalError) as caught:
        _result_from_recall_payload(
            {"hits": [{"score": 1.0, "content": "x"}]},
            verb="recall",
            backend="index",
            top_k=8,
        )
    assert caught.value.code == "retrieval_engine_contract_mismatch"


def test_a_remember_receipt_requires_the_status_that_distinguishes_a_repeat():
    receipt = _receipt_from_payload(
        {
            "collection": "notes",
            "episode_id": "ep-7",
            "content_hash": "abc",
            "status": "existing",
            "ingested_at": "2026-01-01T00:00:00Z",
            "observed_at": "2026-01-01T00:00:00Z",
            "extracted_fact_ids": ["f1"],
        },
        "index",
    )
    assert isinstance(receipt, RememberReceipt)
    assert receipt.status == "existing"
    assert receipt.extracted_fact_ids == ("f1",)
    with pytest.raises(RetrievalError):
        _receipt_from_payload(
            {"episode_id": "ep-7", "content_hash": "abc", "status": "maybe"}, "index"
        )
    with pytest.raises(RetrievalError):
        _receipt_from_payload({"status": "created", "content_hash": "abc"}, "index")


def test_a_compaction_report_requires_the_count_that_proves_it_ran():
    report = _report_from_payload(
        {
            "collection": "notes",
            "created_at": "2026-01-01T00:00:00Z",
            "candidates_considered": 12,
            "facts_deduped": 2,
            "summary_ids": ["s1"],
        },
        "index",
    )
    assert isinstance(report, CompactionReport)
    assert report.candidates_considered == 12
    assert report.facts_deduped == 2
    assert report.summaries_created == 0
    assert report.summary_ids == ("s1",)
    with pytest.raises(RetrievalError) as caught:
        _report_from_payload({"collection": "notes"}, "index")
    assert "never ran" in str(caught.value)


# ── the embedding a caller supplies must say which space it is in ────────────


def test_a_supplied_embedding_needs_its_model_identity():
    with pytest.raises(RetrievalError) as caught:
        remember(
            StubRuntime(),
            content="x",
            embedding={"vector": [0.1, 0.2], "model_version": "1"},
        )
    assert "model_id" in str(caught.value)


def test_a_supplied_embedding_dimension_must_match_its_vector():
    with pytest.raises(RetrievalError) as caught:
        remember(
            StubRuntime(),
            content="x",
            embedding={
                "vector": [0.1, 0.2],
                "model_id": "m",
                "model_version": "1",
                "dimension": 3,
            },
        )
    assert "carries 2" in str(caught.value)


def test_a_valid_embedding_still_raises_for_the_absent_backend():
    """Validation passing is not availability. The engine is still not there."""
    with pytest.raises(RetrievalBackendUnavailableError):
        remember(
            StubRuntime(),
            content="x",
            embedding={
                "vector": [0.1, 0.2],
                "model_id": "m",
                "model_version": "1",
                "dimension": 2,
            },
        )
