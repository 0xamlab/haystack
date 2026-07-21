"""On-device code lexical retrieval lane for triage localization.

Wires Telys' ``LexicalCodeIndex`` (kernel-backed BM25 + code-aware tokenization; telys PR #87 — beats
BM25 on 7/8 MTEB(Code)/CoIR tasks, avg 0.488 vs 0.445) into repository-intelligence triage as an
additional Reciprocal-Rank-Fusion lane. On-device, zero-model, numpy-only (native kernel optional,
pure-Python postings fallback). Opt-in via ``ALGENTA_REPOSITORIES_LEXICAL_RANKING``; degrades to a
no-op (``[]``) whenever ``memengine`` is unavailable or the corpus/query is empty, so triage never
breaks — the heuristic + graph lanes still produce a ranking.
"""
from __future__ import annotations

import os
from typing import Any, Sequence

_LEXICAL_RANKING_ENV = "ALGENTA_REPOSITORIES_LEXICAL_RANKING"


def lexical_ranking_enabled() -> bool:
    """Whether the code-lexical (BM25) triage lane is opted in (default off)."""
    return os.environ.get(_LEXICAL_RANKING_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


def lexical_rank(
    snapshot_manifest: dict[str, Any],
    query_terms: Sequence[str],
    top_k: int,
) -> list[str]:
    """Rank snapshot files by BM25 over (path + symbol names) for the query terms.

    Returns an ordered list of file paths (best first) for RRF fusion, or ``[]`` if the index cannot
    run (``memengine`` missing, empty corpus, or empty query). Deterministic given the manifest + terms.
    """
    try:
        from memengine.lexical import LexicalCodeIndex
    except Exception:  # noqa: BLE001 — retrieval must never break triage; degrade to no-op
        return []

    files = snapshot_manifest.get("files") or []
    ids: list[str] = []
    texts: list[str] = []
    for entry in files:
        path = str(entry["file_path"])
        symbols = " ".join(str(symbol["symbol_name"]) for symbol in (entry.get("symbols") or []))
        ids.append(path)
        texts.append(f"{path} {symbols}".strip())

    query = " ".join(str(term) for term in query_terms).strip()
    if not ids or not query:
        return []
    try:
        index = LexicalCodeIndex().build(ids, texts)  # Algenta-tuned defaults k1=1.8, b=1.0
        hits = index.search(query, k=max(1, int(top_k)))
    except Exception:  # noqa: BLE001 — never let a retrieval hiccup fail triage
        return []
    return [str(doc_id) for doc_id, _score in hits]
