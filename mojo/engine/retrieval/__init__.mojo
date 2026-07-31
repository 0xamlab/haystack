"""
retrieval — the compute half of the retrieval contract. Zero Python.

This package RANKS. It does not index, and it must never grow one.

There is no HNSW graph here, no postings list, no WAL, no LSM tree, no segment format and
no tokenizer. Building and searching an index is the retrieval engine's job, it is already
done, and duplicating it here would be worthless: two indexes over one corpus drift, and
the second one is the one nobody operates. What the tree lacked is the step AFTER search —
given candidate lists and their per-lane scores, produce the final ranking and be able to
explain it — and that is all this package is.

Where the numbers come from
---------------------------
`rag_retrieval.mojo` already holds the scoring primitives, and every one of them is frozen:
`rrf_score`, `hybrid_search_score`, `mmr_diversity_score`, `retrieval_precision`,
`citation_coverage`, `context_relevance_score`. They are scalar functions of scalars. Every
number this package returns comes out of one of them; the package supplies the loop over a
candidate list, the validation, the ordering and the attribution. Nothing here recomputes a
similarity, a BM25 term or a blend.

`vector_kernels/` — the prefilter and the batch ranker, measured at 650 ns per query batch
at N = 2048 — remains the local candidate-generation fast path and is untouched.
`vector_kernels/table.mojo` in particular is a purpose-built ranking index and is frozen.
Its output is one LANE into the drivers here; it is `Float32` and struct-typed and so
deliberately stays on the Mojo side of the wire.

Modules
-------
  score — the per-candidate compositions and the package's shared vocabulary: the status
        codes (200-213, with 214-219 reserved), the single finiteness predicate, the single
        ordering (`retrieval_rank_order`: score descending, document ordinal ascending) and
        the single truncation convention (`top_k == 0` means all, negative is an error).
        Drivers: `hybrid_rank_flat` blends a dense and a sparse lane through the frozen
        `hybrid_search_score` with the weight validated rather than clamped, and returns the
        blend DECOMPOSED into its two terms plus which one dominated, with a per-item
        residual certifying that the parts reproduce the whole; `mmr_select_flat` runs greedy
        MMR through the frozen `mmr_diversity_score`, reporting the redundancy term that
        entered each pick and flagging the first pick's as absent because the maximum over
        an empty selected set does not exist; `retrieval_quality_flat` calls the three frozen
        rank-quality ratios and carries the flag each of them lacks, since all three return
        0.0 for a zero denominator and 0.0 is a real score in all three ranges.
  fuse — reciprocal-rank fusion across N ranked lists. The frozen `rrf_score` takes exactly
        two ranks, so N lanes reach it as a PAIR FOLD in ascending lane order, with an odd
        tail closed by the frozen kernel's own exact `rrf_score(r, r, k) / 2` identity. The
        fold order is part of the contract because floating-point addition is not
        associative. `rrf_fuse_flat` returns the ranking with per-document lane counts and
        best-lane/best-rank attribution and per-lane contribution counts; `rrf_provenance_flat`
        returns the long-form (document, lane, rank, contribution) table with a certificate
        that its rows add up to the scores it explains. Grouping reuses
        `columnar.hash_index.HashIndex` rather than rebuilding a hash table.

Design rules the package keeps
------------------------------
*An answer that does not exist is absent, not zero.* Fusing zero lanes is
`RETR_ERR_NO_LANES`, not a score of 0.0. A lane that did not return a document contributes
no term to it rather than a rank of `n+1`, so a short lane is never punished for being
short, and `lane_hits` / `n_empty_lanes` make "ranked by one lane" and "this lane ranked
nothing" visible instead of inferred. A weight outside [0, 1] is an error, never silently
clamped. Every rank-quality ratio carries whether it exists. Every driver returns a status
and every status is asserted in the suite.

*The lane that could not run is the caller's problem, and it RAISES.* An unavailable
retrieval backend must never reach these kernels as an empty lane or a lane of zeros: an
empty lane here means "this lane ran and matched nothing", which is a real retrieval answer
and is reported as one. That distinction is the whole point of the contract this package
serves, and it is why `hybrid_rank_flat` reports `dense_ranks_nothing` /
`sparse_ranks_nothing` — a lane that scored every candidate identically supplied no
ordering, which is what a zero-filled placeholder looks like from inside the kernel.

*Determinism is stated, not hoped for.* One ordering for the whole package, one fold order,
one tie-break (ascending document ordinal), and no `Dict` anywhere near a ranking.

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a
return-only struct declared in the same file, so the package lands in the runtime library
contract with no new message type, no proto change and no SDK code, and is callable as
`execute(module, function, args)` from both local SDKs. It is therefore *not* in
`_SKIP_RUNTIME_DIRS`.
"""
