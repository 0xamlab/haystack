"""Vendored REAL corpus access for the governed-agent Space.

The corpus is loaded once from data/corpus_wiki_mini.json — real English
Wikipedia lead-extract passages (CC BY-SA 4.0, per-passage title + URL
attribution in the payload; built by scripts/build_corpus.py from the public
MediaWiki API, deterministic sampling). The tokenization is a fixed lowercase
regex applied identically to documents and queries; the BM25 index
(bm25_mojo, native Mojo kernel where loadable) is built lazily, cached, and
its build time measured for the boot badge.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "corpus_wiki_mini.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")

_cache: dict = {}


def tokenize(text: str) -> list[str]:
    """The one tokenizer the BM25 lane shares between documents and queries."""
    return _TOKEN_RE.findall(text.lower())


def load_corpus() -> dict:
    """The vendored corpus payload (docs, provenance, license, queries)."""
    if "corpus" not in _cache:
        _cache["corpus"] = json.loads(DATA_PATH.read_text())
    return _cache["corpus"]


def provenance() -> str:
    return str(load_corpus()["provenance"])


def license_line() -> str:
    payload = load_corpus()
    return f"{payload['license']} ({payload['license_url']}) · {payload['attribution']}"


def sample_queries() -> list[str]:
    return [q["text"] for q in load_corpus()["queries"]]


def docs() -> list[dict]:
    return load_corpus()["docs"]


def mojo_index():
    """The bm25_mojo BM25Okapi index over the tokenized corpus (built once,
    timed — the measurement feeds the boot badge)."""
    if "mojo" not in _cache:
        import bm25_mojo

        started = time.perf_counter()
        _cache["mojo"] = bm25_mojo.BM25Okapi([tokenize(d["text"]) for d in docs()])
        _cache["index_ms"] = (time.perf_counter() - started) * 1e3
        _cache["index_docs"] = len(docs())
    return _cache["mojo"]


def index_stats() -> dict | None:
    """Measured index-build facts after mojo_index() has run; None before."""
    if "index_ms" not in _cache:
        return None
    return {"docs": _cache["index_docs"], "build_ms": round(_cache["index_ms"], 1)}
