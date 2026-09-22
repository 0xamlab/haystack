"""Tab 1 — RAG retrieval duel: rank_bm25 vs bm25-mojo, live on this Space.

Side-by-side top-10 over the vendored synthetic mini-corpus. The identical
ranking is asserted on every run (ordered doc ids, deterministic tie-break);
per-query latency is the median of 7 interleaved reps per lane. If the native
Mojo kernel is unavailable the duel is *held* — the pure-Python fallback is
never benchmarked as "mojo".
"""

from __future__ import annotations

import statistics
import time

import pandas as pd

from lab import corpus
from lab.hardware import hardware_footer

TOP_N = 10
TIMING_REPS = 7


def _held_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["rank", "doc_id", "score", "topic", "title"])


def _top_table(scores, docs: list[dict]) -> tuple[list[str], pd.DataFrame]:
    """Top-N table with a deterministic (-score, index) tie-break."""
    order = sorted(range(len(docs)), key=lambda i: (-float(scores[i]), i))[:TOP_N]
    rows = [
        {
            "rank": r + 1,
            "doc_id": docs[i]["id"],
            "score": round(float(scores[i]), 6),
            "topic": docs[i]["topic"],
            "title": docs[i]["title"][:88],
        }
        for r, i in enumerate(order)
    ]
    return [docs[i]["id"] for i in order], pd.DataFrame(rows)


def rag_duel(query: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Run one retrieval duel for `query`. Never raises into the UI."""
    try:
        query = (query or "").strip()
        if not query:
            return _held_frame(), _held_frame(), "⚠️ Enter a query (or pick a sample claim) first."
        tokens = corpus.tokenize(query)
        if not tokens:
            return (
                _held_frame(),
                _held_frame(),
                "⚠️ The query has no usable tokens after tokenization.",
            )

        idx = corpus.indexes()
        backend = idx["mojo_backend"]
        if not backend.get("native_available"):
            return (
                _held_frame(),
                _held_frame(),
                (
                    "⏸️ **duel held** — the native bm25-mojo kernel did not load on this host "
                    f"({backend.get('error') or 'fallback active'}). Per the harness rule the "
                    "pure-Python fallback is never benchmarked as 'mojo'."
                ),
            )

        all_docs = corpus.docs()
        ref_scores = idx["rank_bm25"].get_scores(tokens)
        mojo_scores = idx["mojo"].get_scores(tokens)

        ref_order, ref_table = _top_table(ref_scores, all_docs)
        mojo_order, mojo_table = _top_table(mojo_scores, all_docs)

        import numpy as np

        max_delta = float(np.max(np.abs(ref_scores - mojo_scores))) if len(all_docs) else 0.0
        identical = ref_order == mojo_order

        # Per-query latency: median of TIMING_REPS interleaved reps per lane.
        ref_times, mojo_times = [], []
        for _ in range(TIMING_REPS):
            t0 = time.perf_counter()
            idx["rank_bm25"].get_scores(tokens)
            ref_times.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            idx["mojo"].get_scores(tokens)
            mojo_times.append(time.perf_counter() - t0)
        ref_us = statistics.median(ref_times) * 1e6
        mojo_us = statistics.median(mojo_times) * 1e6
        speedup = ref_us / mojo_us if mojo_us > 0 else 0.0

        if identical:
            parity = (
                f"✅ **identical ranking** — top-{TOP_N} doc order matches exactly across lanes "
                f"(deterministic −score/index tie-break); max |Δ| score over {idx['n_docs']} docs: "
                f"{max_delta:.2e} (float64 summation noise)"
            )
        else:
            first_diff = next(
                (
                    r
                    for r, (a, b) in enumerate(zip(ref_order, mojo_order, strict=False), 1)
                    if a != b
                ),
                None,
            )
            parity = (
                f"⚠️ **rankings differ at rank {first_diff}** — max |Δ| score {max_delta:.2e}. "
                "Shown as-is: no assertion is faked on this Space."
            )

        status = (
            f"{parity}\n\n"
            f"⏱️ **per-query latency** (median of {TIMING_REPS}, interleaved): "
            f"rank_bm25 0.2.2 = **{ref_us:,.0f} µs** · bm25-mojo 0.1.2 (native Mojo) = "
            f"**{mojo_us:,.1f} µs** → **{speedup:,.1f}×**\n\n"
            f"⚖️ **retrieval budget** — lexical retrieval at {mojo_us:,.1f} µs leaves your "
            f"entire rerank budget intact; the pure-Python rank_bm25 path would spend "
            f"{ref_us / 1000:,.2f} ms of every query's budget before a reranker even starts. "
            f"RAG isn't dead — your retrieval is slow.\n\n"
            f"<span class='card-hw'>corpus: {idx['n_docs']} synthetic BEIR-scifact-style docs "
            f"(seed 20260920, scripts/gen_corpus.py) · query tokens: {len(tokens)} · "
            f"{hardware_footer()}</span>"
        )
        return ref_table, mojo_table, status
    except Exception as exc:  # surfaced as a clean held card, never a traceback
        return (
            _held_frame(),
            _held_frame(),
            (f"⏸️ **duel held** — {type(exc).__name__}: {exc}. No numbers shown."),
        )
