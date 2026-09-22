"""Vendored mini-corpus access for the RAG retrieval duel.

The corpus is loaded once from lab/data/corpus_scifact_mini.json (fully
synthetic, BEIR-scifact-style, seed 20260920 — see scripts/gen_corpus.py).
Both BM25 indexes are built lazily and cached; the tokenization is a fixed
lowercase regex applied identically to documents and queries, so both lanes
always see the same tokens (arena rule R2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "corpus_scifact_mini.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")

_cache: dict = {}


def tokenize(text: str) -> list[str]:
    """The one tokenizer both BM25 lanes share."""
    return _TOKEN_RE.findall(text.lower())


def load_corpus() -> dict:
    """The vendored corpus payload (docs, queries, provenance, seed)."""
    if "corpus" not in _cache:
        _cache["corpus"] = json.loads(DATA_PATH.read_text())
    return _cache["corpus"]


def sample_queries() -> list[str]:
    return [q["text"] for q in load_corpus()["queries"]]


def docs() -> list[dict]:
    return load_corpus()["docs"]


def _build_indexes() -> dict:
    import bm25_mojo
    from rank_bm25 import BM25Okapi as RankBM25

    corpus_tokens = [tokenize(d["text"]) for d in docs()]
    return {
        "rank_bm25": RankBM25(corpus_tokens),
        "mojo": bm25_mojo.BM25Okapi(corpus_tokens),
        "mojo_backend": bm25_mojo.backend_info(),
        "n_docs": len(corpus_tokens),
    }


def indexes() -> dict:
    """Both BM25 indexes over the same tokenized corpus (built once)."""
    if "indexes" not in _cache:
        _cache["indexes"] = _build_indexes()
    return _cache["indexes"]
