---
icon: magnifying-glass
description: Search, fuse, rerank and explain results with compiled kernels on your own machine — and find out when a backend is missing instead of getting an empty list.
---

# Retrieval

Retrieval is not one operation. A dense lane, a sparse lane, a fusion, a reranker and a
metadata filter are five different computations with five different ways of going wrong, and
a surface that hides which one ran cannot tell you why an answer looks the way it does. So
every verb names the backend serving it, every result records which lane put each item where,
and `provenance` turns that record into a sentence.

Everything runs as compiled kernels inside the runtime that ships with the SDK. There is
nothing to start and nothing to install separately.

```python
from algenta import MojoRuntime, RetrievalDocument, provenance, sparse_search

runtime = MojoRuntime(mode="local")

result = sparse_search(
    runtime,
    query="tokenize query",
    documents=[
        RetrievalDocument(id="a", text="def tokenize_query_parser(x): return x"),
        RetrievalDocument(id="b", text="class Retriever: pass"),
        RetrievalDocument(id="c", text="def parse_query(q): return tokenize(q)"),
    ],
    top_k=3,
    backend="lexical",
)

result.ids()                              # ['a', 'c']
result.score_model                        # 'lexical-bm25(k1=1.8,b=1.0)'
provenance(result).why("a")
# "'a' ranked 1 of 2 with score 0.803993, served by lexical under score model
#  lexical-bm25(k1=1.8,b=1.0). Contributions: sparse lane (backend=lexical) rank 1,
#  score 0.803993."
```

## The modules

| Module | What it does |
| --- | --- |
| `vector_search` | ANN index math (HNSW, IVF, PQ, LSH) and rank-quality metrics (recall@k, MRR, beam search) underlying the `dense` backend's approximate-nearest-neighbour index |

## A backend that is not available raises. It never returns an empty result

This is the most useful thing on this page, so it comes first.

An empty result is a real answer: the backend ran and nothing matched your query. If a
missing backend also produced an empty result, then the two most different outcomes in
retrieval would be the same value, and nothing in your code could tell a broken installation
from an unlucky query. You would ship the broken one.

So a backend that is not present raises, and the error names the component that is missing:

```python
from algenta import RetrievalBackendUnavailableError, recall

try:
    memories = recall(runtime, query="what changed on Tuesday", collection="notes")
except RetrievalBackendUnavailableError as error:
    error.backend      # which backend was asked for
    error.missing      # the components that are not installed, by name
    error.verb         # which verb wanted it
```

`missing` is a name you can act on. "Unavailable" on its own is an adjective; a name is
something to install. Ask before you call, if you would rather branch than catch:

```python
from algenta import backend_status

status = backend_status("dense")
status.available   # False when it is genuinely absent
status.missing     # what to install
```

`available` is `None`, not `False`, for the backend whose kernels live in the runtime
installed on this device: without a runtime to ask, there is no answer, and `False` would be
a claim the check cannot support. Pass a runtime to resolve it.

## The six verbs

| Verb | What it answers |
| --- | --- |
| `vector_search` | rank by vector similarity over a built collection |
| `sparse_search` | rank by term overlap, scored by the retrieval index that owns the terms |
| `hybrid_search` | fuse ranked lanes into one ranking |
| `rerank` | reorder a candidate set by a second criterion |
| `filtered_search` | a lane search restricted to the items a filter admits |
| `provenance` | why each item is where it is |

Three more verbs cover governed memory, and use the same words as the hosted memory surface
so one operation is never named twice: `remember`, `recall` and `compact`.

Every verb takes an explicit `backend`, and takes it as a keyword. There is no default that
quietly picks a different engine on a different machine.

## The backends, and what each one can actually do

| Backend | Corpus | Serves |
| --- | --- | --- |
| `local` | the lane results you pass in | fusion and reranking |
| `lexical` | the documents in this request, indexed by the retrieval index | the sparse lane |
| `dense` | a built approximate-nearest-neighbour index | the dense lane over stored content |
| `index` | the governed, temporal collection | `remember`, `recall`, `compact`, and searches over stored content |

The split is not arbitrary. A search lane needs an **index**, and the local kernels contain
none — no postings list, no nearest-neighbour graph, no segments. Fusion and reranking take
ranked lanes as *input*, so they need no index, which is exactly why they are the two the
local kernels serve. Building an index is the retrieval index's job and is not duplicated.

There is also deliberately no local sparse lane. The retrieval index owns tokenization and
the term statistics; a second tokenizer would score the same query differently from the one
that built the index, and the two sets of scores would not be comparable.

A verb may only run on a backend that can produce its lane, and that is checked before
anything is dispatched — with your own arguments still in scope:

```python
from algenta import RetrievalError

try:
    sparse_search(runtime, query="tokenize", documents=docs, backend="local")
except RetrievalError as error:
    error.code    # 'backend_cannot_serve_verb'
    str(error)    # names 'lexical' and 'index' as the backends that serve it
```

The same rule reaches inside a verb. `rerank` offers a diversity reranker and a
cross-encoder; the diversity reranker is a compiled kernel and the cross-encoder needs a
model the local runtime does not carry, so asking for the cross-encoder locally is refused by
name rather than approximated with something cheaper.

## Fusing lanes

Rank fusion is defined over any number of ranked lists, so `hybrid_search` takes any number.
Two lanes are the common case and `dense=` / `sparse=` name them; `lanes=` takes a mapping
for more, because a graph walk or a second index is a lane like any other.

```python
from algenta import hybrid_search, provenance

fused = hybrid_search(
    runtime,
    lanes={
        "lexical": [("x", 0.91), ("y", 0.40)],
        "dense": [("y", 2.00), ("z", 1.00)],
        "graph": [("x", 0.55)],
    },
    top_k=3,
    fusion="rrf",
    explain=True,
)

report = provenance(fused)
report.fusion          # 'rrf'
report.fusion_params   # {'rrf_k': 60.0, 'lanes': 3}
report.items[0].explanation
```

A lane result from another verb can be passed straight in — the output of `sparse_search` is
a valid lane — so the lanes may be served by different backends and provenance records which
served which.

The lane order is part of the answer, not a detail. Floating-point addition is not
associative, so the fusion folds lane terms in the order you wrote them and the same lanes in
the same order always produce the same bits.

### An empty lane and an absent lane are different

`dense=[]` says the dense lane ran and matched nothing. That is a real retrieval answer: rank
fusion contributes no term for a lane that did not rank an item, so an empty lane fuses
correctly and is reported as empty.

`dense=None` says the lane did not run, and a hybrid missing a lane is a hybrid in name only,
so it is refused. This is the same distinction the unavailable-backend rule makes, one level
down — and it is the reason a lane whose backend is missing raises rather than handing an
empty list to a fusion that would happily accept it.

### Rank fusion or score fusion, and never both parameters

`rrf` fuses **ranks** and takes `rrf_k`. `linear` fuses **scores** and takes `alpha`, the
weight on the dense lane. Passing the parameter belonging to the other one is rejected
rather than ignored:

```python
hybrid_search(runtime, dense=dense_hits, sparse=sparse_hits, fusion="rrf", alpha=0.3)
# RetrievalError: alpha is a weight on SCORES and rrf fuses RANKS, so alpha would be
# ignored; pass fusion='linear' to weight scores
```

A weight that silently does nothing is worse than a weight that is refused: you would tune
it, see no change, and conclude the fusion does not respond to weighting.

Score fusion has one further requirement, and it is worth knowing before you reach for it:
it needs a score from **both** lanes for every candidate. It weighs one dense score against
one sparse score and has no way to represent an absence, so filling a missing side with 0.0
would read as "this lane scored it, badly" rather than "this lane never saw it" — and would
silently halve that item's score. Lanes that disagree about which candidates exist are what
rank fusion is for, and the rejection says so.

## Provenance answers "why did this rank first"

A ranking you cannot explain is a ranking you cannot defend. Each hit carries one
contribution per lane, and a lane that did not return the item has **no** rank for it —
absent, not rank 0 and not score 0.0. An absent contribution must not be comparable with the
ones that are real, because that is how a missing lane starts looking like a weak one.

```python
first = provenance(fused).items[0]
first.contributions[0].lane          # 'lexical'
first.contributions[0].rank          # 1
first.contributions[0].contribution  # what that placement was worth
first.contributions[1].rank          # None — that lane never returned this item
first.explanation                    # the same facts as one sentence
```

With `explain=True`, the per-lane contributions are computed by the same kernel path that
produced the ranking, so the table and the order cannot disagree. Nothing in the explanation
is worked out afterwards in Python — a number reconstructed beside the one that produced the
ordering would eventually differ from it, and the explanation is the last place you would
look. When a backend reports no attribution at all, `attribution_residual` is `None` rather
than `0.0`, because "no certificate" and "a perfect certificate" are the two things worth
telling apart.

`score_model` is part of the answer too. Two results with different score models are not
comparable, and a system that stores scores needs to know that before it compares them next
week.

Provenance cannot be relabelled. Passing a backend the result did not come from is rejected
rather than accepted, because provenance you can hand the wrong backend is not provenance.

## Reranking measures redundancy between candidates

The diversity reranker trades relevance against redundancy. It takes each candidate's
existing relevance score and the candidate-to-candidate similarity matrix, flat and
row-major:

```python
from algenta import RetrievalCandidate, rerank

reranked = rerank(
    runtime,
    candidates=[
        RetrievalCandidate(id="c0", score=0.90),
        RetrievalCandidate(id="c1", score=0.40),
    ],
    similarity=[1.0, 0.2,
                0.2, 1.0],   # similarity[i * n + j] = sim(i, j)
    lambda_mmr=0.7,
    top_k=2,
)
```

The matrix is supplied, not derived. Deriving it would mean computing similarities here,
alongside whichever engine computed the ones that produced the relevance scores — two
definitions of the same quantity, which is the thing this whole surface exists to avoid. Only
the `[candidate][selected]` direction is read, so an asymmetric matrix is used exactly as
given rather than symmetrised behind your back.

The first item selected has nothing to be redundant with, so its redundancy contribution is
**absent** rather than 0.0. A zero there would read as "measured, and found low".

## A filter that admits nothing is a contradiction, not a precedence question

A filter is checked when you build it, not when it produces no results:

```python
from algenta import RetrievalFilter

RetrievalFilter(include_ids=("a", "b"), exclude_ids=("b",))
# RetrievalError: b appears in both include_ids and exclude_ids; the filter
# contradicts itself and would admit nothing

RetrievalFilter(min_score=0.9, max_score=0.1)
# RetrievalError: the window is empty, so the filter admits nothing
```

An empty id list is refused as well, rather than read as "no restriction" — an empty include
list admits nothing and an empty exclude list restricts nothing, so leaving it out is what
either one means.

`where` matches metadata by equality, and an item that does not carry the key does **not**
match. Absence is not a value, so it cannot satisfy an equality — the same rule a predicate
over a missing cell follows in a columnar query.

The restriction is split where the capabilities are: ids and metadata keys are matched before
dispatch, because the engines index content and not arbitrary dictionaries, while the score
window is applied to the lane's own scores, which is the only place a score exists.

## Shapes are checked before anything is read

A similarity matrix of the wrong size is refused, and the message says why it matters — a
short matrix would shift every row after the gap and every redundancy penalty would be read
from the wrong pair:

```python
rerank(runtime, candidates=two_candidates, similarity=[1.0, 0.2, 0.2])
# RetrievalError: similarity holds 3 values for 2 candidates; an n x n matrix needs
# exactly 2 rows of 2
```

Four more checks earn their place the same way:

* **A candidate with no score is refused, not zero-filled.** A score defaulted to zero still
  ranks, and ranks plausibly, which is the worst way for a missing input to behave.
* **Non-finite values are refused.** A `nan` in a score makes every threshold comparison
  false, so a request carrying one passes each check on the way in and produces a ranking
  nobody can explain.
* **An all-zero query vector is refused for cosine.** Cosine divides by the norm, and there
  is no similarity to a zero vector, so no ranking exists. The same vector is a legitimate
  inner-product query and is accepted there.
* **Size limits come from the engine, not from a copy.** The kernels publish the ceilings
  they enforce and those numbers are read before a payload is sent, so a request that is
  accepted here is one the kernels will accept. A limit restated in a second place drifts
  from the one that is actually applied, and then a rejection quotes a number nothing
  explains.

Repeated ids are refused in documents, in candidates and in a lane. One id must denote one
item, or a rank cannot be traced back to anything.

## An empty corpus is not a query that matched nothing

Searching zero documents, or reranking zero candidates, is a mistake in the call rather than
a result, so it is refused. Same distinction again, one level lower: a request that never had
anything to search must not return the same value as a search that found nothing.

## A kernel's failure is not a short ranking

A kernel that rejects a request has not produced a ranking, so what it holds is not returned
under a successful-looking result. The rejection carries the engine's own name for the
defect, asked for at the moment it happens, rather than a bare number:

```python
# RetrievalError: rejected the request: weight_outside_unit_interval (status 207);
# no ranking was produced
```

A result whose shape does not match the contract — mismatched id and score counts, a
non-numeric score, an index outside the candidate set — is reported the same way rather than
salvaged into whatever part of it looked usable.

## Governed memory: remember, recall, compact

`remember`, `recall` and `compact` work against the governed collection, which is the one
backend where a result outlives the call that produced it: provenance to an immutable
episode, a validity window and a retention policy.

```python
from algenta import recall, remember

receipt = remember(
    runtime,
    content="the deploy window moved to Tuesday",
    collection="notes",
)
receipt.status        # 'created', or 'existing' for identical content stored again

result = recall(
    runtime,
    query="when is the deploy window",
    collection="notes",
    as_of="2026-03-01T00:00:00Z",
    top_k=8,
)
```

Storing the same content twice is the same episode, not a second one, and the receipt says
which happened rather than leaving you to infer it from a count.

`recall` returns the same result type as every other verb, so one provenance report covers a
governed recall and a local fusion alike. Its score terms — similarity, recency, salience,
authority, and every penalty — arrive as named contributions, and a penalty is never silent.

`as_of` reconstructs what was valid at a world-time; leaving it out means now. A supplied
embedding must say which model and version it belongs to, because a recall never mixes
embedding spaces and can only honour that if every vector says which space it is in.

The ephemeral backends cannot serve these three verbs at all. A store that does not outlive
the call is not a memory, and offering one would be a promise the SDK cannot keep.

## Everything runs in this process

`MojoRuntime(mode="local")` is the whole setup. A runtime carrying a base URL or an API key is
a client for a remote service, and passing one to a retrieval verb is refused by name rather
than accepted and quietly routed — moving a ranking off your device is not something to do on
your behalf.

## See also

* [Columnar queries](columnar-queries.md) — filter, group, sort and rank tabular data
* [Batched and chained execution](coarse-execution.md) — many kernel calls in one frame
* [Sparse systems & graph analytics](sparse-and-graph.md) — sparse linear algebra and graphs
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
