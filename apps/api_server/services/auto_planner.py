"""
apps/api_server/services/auto_planner.py — Fully-autonomous query planner.

Given only natural-language hints ("revenue", "product line") the planner:
  1. Discovers local tabular sources in a directory (CSV / Parquet)
  2. Profiles each source with the Mojo column_profile + relation_detect engines
  3. Resolves the best metric column using field_map → column_match Mojo pipeline
  4. Resolves the best dimension column using resolve_group_column_graph
  5. Discovers join keys using the Mojo join_detect engine
  6. Returns a QueryPlan with zero hardcoded column / source names

No human intervention required — the planner is fully data-driven.
"""
from __future__ import annotations

import io
import json
import math
import os
import random
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import structlog

from apps.api_server.compute.mojo_adapter import invoke_engine_sync
from apps.api_server.routers.data_map import _build_mojo_column_profile_columns
from apps.api_server.services.data_coercion import parse_delimited_records
from apps.api_server.services.mojo_column_rank_resolver import (
    MojoColumnRankResolver,
    invoke_planner_mojo,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

logger = structlog.get_logger(__name__)

_CACHE_VERSION = 2
_MOJO_COLUMN_RANK_MODE = os.environ.get("ALGENTA_MOJO_COLUMN_RANK_MODE", "auto").lower()
_PLANNER_MOJO_TRANSPORT = os.environ.get("ALGENTA_PLANNER_MOJO_TRANSPORT", "auto").lower()
_PLANNER_MOJO_RESIDENT_ENGINES = frozenset({"field_map", "relation_detect", "string_similarity"})
_PLANNER_MOJO_SHARED_ENGINES = frozenset(
    {
        "column_profile",
        "relation_detect",
        "field_map",
        "column_match",
        "join_detect",
        "string_similarity",
        "monte_carlo",
    }
)
_PLANNER_MOJO_MAX_RESIDENT_PAYLOAD_BYTES = int(
    os.environ.get("ALGENTA_PLANNER_MOJO_MAX_RESIDENT_PAYLOAD_BYTES", "8192"),
)
_REGISTRY_SOURCE_ARTIFACT_CACHE_MAX = 512


@dataclass
class _CachedRegistrySourceArtifacts:
    nodes: dict[str, Any]
    profile: dict[str, dict[str, Any]]
    query_hints: list[dict[str, Any]]
    last_hit: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_hit = time.monotonic()


_REGISTRY_SOURCE_ARTIFACT_CACHE: dict[
    tuple[str, str, str], _CachedRegistrySourceArtifacts
] = {}


def _should_use_resident_planner_mojo(engine_type: str, payload: dict[str, Any]) -> bool:
    if engine_type not in _PLANNER_MOJO_RESIDENT_ENGINES:
        return False
    payload_size = len(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return payload_size <= _PLANNER_MOJO_MAX_RESIDENT_PAYLOAD_BYTES


def _registry_source_artifact_cache_get(
    key: tuple[str, str, str],
) -> _CachedRegistrySourceArtifacts | None:
    cached = _REGISTRY_SOURCE_ARTIFACT_CACHE.get(key)
    if cached is None:
        return None
    cached.touch()
    return cached


def _registry_source_artifact_cache_put(
    key: tuple[str, str, str],
    value: _CachedRegistrySourceArtifacts,
) -> _CachedRegistrySourceArtifacts:
    if len(_REGISTRY_SOURCE_ARTIFACT_CACHE) >= _REGISTRY_SOURCE_ARTIFACT_CACHE_MAX:
        oldest_key = min(
            _REGISTRY_SOURCE_ARTIFACT_CACHE.items(),
            key=lambda item: item[1].last_hit,
        )[0]
        _REGISTRY_SOURCE_ARTIFACT_CACHE.pop(oldest_key, None)
    _REGISTRY_SOURCE_ARTIFACT_CACHE[key] = value
    return value


# ── Query plan ─────────────────────────────────────────────────────────────────

@dataclass
class JoinHop:
    """One edge in a multi-hop join path."""
    left_source: str
    right_source: str
    left_key: str
    right_key: str
    confidence: float = 0.0
    cardinality: str = ""
    join_type: str = "inner"
    notes: list[str] = field(default_factory=list)


@dataclass
class QueryPlan:
    """Fully-resolved query plan — no human-supplied column names."""
    metric_src:      str
    metric_col:      str
    metric_conf:     float
    metric_role:     str
    agg:             str

    group_col:       str | None = None
    group_src:       str | None = None
    group_conf:      float = 0.0

    join_key_metric: str | None = None   # join column in metric_src
    join_key_group:  str | None = None   # join column in group_src
    join_conf:       float = 0.0
    join_cardinality: str = ""
    join_hops:       list[JoinHop] = field(default_factory=list)
    path_confidence: float = 0.0
    intermediate_sources: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)

    error:    str | None = None
    mojo_ops: list[str]  = field(default_factory=list)   # which Mojo engines were called
    steps:    list[str]  = field(default_factory=list)   # human-readable plan trace


@dataclass(frozen=True)
class AdaptiveSourceContext:
    """Per-source scoring baselines derived from the current customer/org data."""
    join_distinctiveness: tuple[tuple[float, int], ...] = ()
    column_distinctiveness: tuple[tuple[float, int], ...] = ()


_SEMANTIC_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "amt": ("amount",),
    "bu": ("business", "unit"),
    "cat": ("category",),
    "cond": ("condition",),
    "cust": ("customer",),
    "dept": ("department",),
    "ext": ("extended",),
    "manuf": ("manufacturer",),
    "mfgr": ("manufacturer",),
    "mfg": ("manufacturer",),
    "pct": ("percent",),
    "prod": ("product",),
    "qty": ("quantity",),
}

_JOIN_KEY_ENTITY_TOKENS = {
    "booking",
    "catalog",
    "code",
    "customer",
    "id",
    "identifier",
    "invoice",
    "item",
    "key",
    "name",
    "number",
    "order",
    "part",
    "project",
    "quote",
    "request",
    "sku",
    "vendor",
}

_JOIN_KEY_MEASURE_TOKENS = {
    "amount",
    "cost",
    "extended",
    "margin",
    "percent",
    "price",
    "qty",
    "quantity",
    "rate",
    "ratio",
    "revenue",
    "sales",
    "total",
    "unit",
    "value",
}

_MEASURE_LIKE_ROLES = {
    "base_measure",
    "derived_measure",
    "metric",
    "ratio",
    "unit_measure",
}


def _semantic_token_set(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_SEMANTIC_TOKEN_ALIASES.get(token, ()))
    return expanded


def _fuzzy_token_sim(a: str, b: str) -> float:
    """
    Generic string similarity — NO hardcoded domain maps.
    Works for any abbreviation pattern by checking:
      1. Exact match                  → 1.0
      2. Prefix match (short ⊂ long)  → len(short)/len(long)
         e.g. "cust"/"customer" = 4/8 = 0.50
              "qty"/"quantity"  = 3/8 = 0.375
      3. Character bigram overlap     → Dice coefficient

    This handles common column abbreviations (cust, qty, mfg, etc.) without
    knowing the domain — if a column token is a prefix of a hint word, it's
    a partial match proportional to how much of the word it covers.
    """
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Prefix/suffix check (shorter is a prefix of longer)
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if long.startswith(short):
        return len(short) / len(long)
    # Character bigram Dice coefficient
    def _bigrams(s: str) -> set:
        if len(s) < 2:
            return set()
        return {s[i : i + 2] for i in range(len(s) - 1)}
    bg_a, bg_b = _bigrams(a), _bigrams(b)
    if bg_a and bg_b:
        return 2 * len(bg_a & bg_b) / (len(bg_a) + len(bg_b))
    return 0.0


def _fuzzy_name_sim(hint_words: list[str], col_name: str) -> float:
    """
    Score how well a column name matches a multi-word hint.

    Strategy (no hardcoded maps):
      - Split col_name into tokens (split on _, CamelCase, spaces)
      - For each hint word, find the best-matching column token via _fuzzy_token_sim
      - Aggregate: geometric mean of per-hint-word scores (penalizes partial coverage)

    Returns a score in [0.0, 1.0].
    """
    sym_map = {
        "%": " percent ",
        "$": " dollar ",
        "#": " number ",
        "€": " euro ",
        "£": " pound ",
    }
    col_norm = col_name.lower()
    for sym, word in sym_map.items():
        col_norm = col_norm.replace(sym, word)
    # Split on non-alphanumeric, also split CamelCase
    col_norm = re.sub(r"([a-z])([A-Z])", r"\1 \2", col_norm)
    col_toks = re.findall(r"[a-z0-9]+", col_norm)
    if not col_toks:
        return 0.0

    hint_sim_scores = []
    for hw in hint_words:
        best = max((_fuzzy_token_sim(hw, ct) for ct in col_toks), default=0.0)
        hint_sim_scores.append(best)

    if not hint_sim_scores:
        return 0.0
    # Geometric mean — all hint words must match for high score
    import math
    product = math.prod(max(s, 1e-6) for s in hint_sim_scores)
    return round(product ** (1.0 / len(hint_sim_scores)), 4)


def _acronym_score(hint_words: list[str], col_token: str) -> float:
    """
    Data-driven acronym check: does an all-caps column token represent
    the initials of the hint phrase?

    Examples (no hardcoding):
      "BU"   vs ["business", "unit"]   → initials "BU"   → 1.0
      "POS"  vs ["point", "of", "sale"]→ initials "POS"  → 1.0
      "EXT"  vs ["extended"]           → 1/3 chars match  → partial
      "AAR"  vs ["aar", "margin"]      → 1/2 = 0.50
    """
    col_token = col_token.upper()
    if not col_token.isalpha() or len(col_token) < 2 or len(col_token) > 6:
        return 0.0
    # Build initials string from hint words (skip stopwords)
    stop_words = {
        "of",
        "the",
        "a",
        "an",
        "and",
        "or",
        "by",
        "in",
        "at",
        "for",
        "per",
    }
    content_words = [w for w in hint_words if w.lower() not in stop_words and w]
    if not content_words:
        return 0.0
    if len(col_token) > len(content_words):
        return 0.0
    initials = "".join(w[0].upper() for w in content_words)
    if col_token == initials:
        return 1.0
    # Partial: fraction of token chars that match the initials in order
    matches = sum(1 for i, c in enumerate(col_token) if i < len(initials) and initials[i] == c)
    return round(matches / max(len(col_token), len(initials)), 3)


def _value_semantic_score(hint_words: list[str], sample_values: list[str]) -> float:
    """
    Score how well a column's sample VALUES match the hint semantically.

    Approach — purely data-driven, no hardcoded domain lists:
      1. Word-count similarity: tokens from sample values vs hint words
      2. Cardinality signal: moderate unique count (5-50) → likely a dimension category
      3. Length signal: short strings (≤20 chars) in a finite set → category, not free-text

    Returns a bonus in [0.0, 0.30] to be added to the base column score.
    """
    if not sample_values or not hint_words:
        return 0.0
    hint_set = {w.lower() for w in hint_words}
    val_tokens = set()
    for v in sample_values[:30]:
        val_tokens.update(re.findall(r"[a-z]+", str(v).lower()))
    # Direct token overlap between hint and cell values
    token_overlap = len(hint_set & val_tokens) / max(len(hint_set), 1)
    return round(min(token_overlap * 0.30, 0.30), 4)


def _hint_requests_time(hint_words: list[str]) -> bool:
    time_words = {
        "date", "day", "days", "week", "month", "quarter", "year",
        "ytd", "mtd", "qtd", "time", "timeline", "daily", "monthly", "yearly",
    }
    return any(w.lower() in time_words for w in hint_words)


def _dimension_semantic_evidence(
    hint_words: list[str],
    col_name: str,
    sample_values: list[str],
) -> tuple[float, float, float]:
    acro = 0.0
    for part in re.findall(r"[A-Za-z0-9]+", col_name):
        if part.isupper() and 2 <= len(part) <= 6:
            acro = max(acro, _acronym_score(hint_words, part))
    fuzzy = _fuzzy_name_sim(hint_words, col_name)
    val_sem = _value_semantic_score(hint_words, sample_values)
    return fuzzy, acro, val_sem


def _source_token_set(source_name: str) -> set[str]:
    source_norm = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", source_name)
    source_norm = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", source_norm)
    return set(re.findall(r"[a-z0-9]+", source_norm.lower()))


def _normalize_match_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return str(int(value))
        return str(round(value, 6)).rstrip("0").rstrip(".")

    text = str(value).strip().lower()
    if not text or text in {"?", "none", "null", "nan", "n/a"}:
        return None
    text = re.sub(r"[_/\\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _tokenize_identifier(text: str) -> set[str]:
    return _semantic_token_set(text)


# ── Data helpers ───────────────────────────────────────────────────────────────

_LOCAL_SOURCE_PRIORITY = {".parquet": 0, ".csv": 1}

def _load_csv(path: Path, max_rows: int = 3000) -> list[dict[str, Any]]:
    rng = random.Random(0)  # noqa: S311 - deterministic sampling, not security-sensitive
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for i, row in enumerate(parse_delimited_records(f.read(), delimiter=",", sniff=True)):
            if max_rows <= 0 or len(rows) < max_rows:
                rows.append(row)
            else:
                j = rng.randint(0, i)
                if j < max_rows:
                    rows[j] = row
    return rows


def _load_parquet(path: Path, max_rows: int = 3000) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError(
            "Local Parquet planning requires pyarrow to be installed."
        ) from exc

    initialize_pyarrow_parquet_runtime()
    rng = random.Random(0)  # noqa: S311 - deterministic sampling, not security-sensitive
    rows: list[dict[str, Any]] = []
    seen = 0
    parquet_file = pq.ParquetFile(str(path))
    for batch in parquet_file.iter_batches():
        for row in batch.to_pylist():
            if max_rows <= 0 or len(rows) < max_rows:
                rows.append(row)
            else:
                j = rng.randint(0, seen)
                if j < max_rows:
                    rows[j] = row
            seen += 1
    return rows


def _load_records(path: Path, max_rows: int = 3000) -> list[dict[str, Any]]:
    ext = path.suffix.lower()
    if ext == ".csv":
        return _load_csv(path, max_rows=max_rows)
    if ext == ".parquet":
        return _load_parquet(path, max_rows=max_rows)
    raise ValueError(f"Unsupported local source extension: {ext}")


def _discover_local_source_map(data_dir: Path) -> dict[str, str]:
    if not data_dir.exists():
        return {}

    chosen: dict[str, Path] = {}
    for path in sorted(p for p in data_dir.iterdir() if p.is_file()):
        ext = path.suffix.lower()
        if ext not in _LOCAL_SOURCE_PRIORITY:
            continue
        existing = chosen.get(path.stem)
        if existing is None:
            chosen[path.stem] = path
            continue
        if _LOCAL_SOURCE_PRIORITY[ext] < _LOCAL_SOURCE_PRIORITY[existing.suffix.lower()]:
            chosen[path.stem] = path
    return {name: path.name for name, path in sorted(chosen.items())}


def _profile_records(records: list[dict]) -> dict[str, dict]:
    if not records:
        return {}
    profile: dict[str, dict] = {}
    n_total = len(records)
    for f in records[0].keys():
        nums: list[float] = []
        strs: list[str]   = []
        sample_numeric: list[float] = []
        sample_strings: list[str] = []
        unique_values: set[str] = set()
        non_empty = 0
        for rec in records:
            v = rec.get(f)
            if v is None:
                continue
            sv = str(v).strip()
            if sv and sv not in ("", "?", "none", "null", "nan"):
                non_empty += 1
                unique_values.add(sv)
                if isinstance(v, int | float) and not isinstance(v, bool):
                    fv = float(v)
                    nums.append(fv)
                    if len(sample_numeric) < 50:
                        sample_numeric.append(fv)
                else:
                    strs.append(sv)
                    if len(sample_strings) < 50:
                        sample_strings.append(sv)
        mean = sum(nums) / len(nums) if nums else 0.0
        std = (
            math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
            if nums
            else 0.0
        )
        profile[f] = {
            "numeric":       nums,
            "strings":       strs,
            "is_numeric":    len(nums) > len(strs),
            "sample_values": [str(v) for v in sample_numeric[:30]] + sample_strings[:30],
            "unique_count":  len(unique_values),
            "total_count":   len(nums) + len(strs),
            "fill_rate":     round(non_empty / max(n_total, 1), 4),
            "mean":          mean,
            "std":           std,
        }
    return profile


def _profiles_from_registry_meta(meta: dict) -> dict[str, dict]:
    """
    Reconstruct planner profile stats from persisted registry metadata.

    New registrations persist a dedicated planner_profile block so registry
    planners do not need to rescan all rows on startup/prewarm. Older metadata
    falls back to the public column summary fields.
    """
    row_count = int(meta.get("row_count", 0) or 0)
    planner_profile = meta.get("planner_profile") or {}
    if planner_profile:
        out: dict[str, dict] = {}
        for col, raw in planner_profile.items():
            is_numeric = bool(raw.get("is_numeric", False))
            samples = [str(v) for v in (raw.get("sample_values") or [])[:50]]
            strings = [str(v) for v in (raw.get("strings") or [])[:50]]
            if not strings and not is_numeric:
                strings = list(samples)
            total_count = int(raw.get("total_count", 0) or 0)
            fill_rate = float(raw.get("fill_rate", 1.0) or 1.0)
            if total_count <= 0 and row_count > 0:
                total_count = max(int(round(row_count * fill_rate)), 1 if fill_rate > 0 else 0)
            out[col] = {
                "is_numeric": is_numeric,
                "strings": strings,
                "sample_values": samples,
                "unique_count": int(raw.get("unique_count", 0) or 0),
                "total_count": total_count,
                "fill_rate": fill_rate,
                "mean": float(raw.get("mean", 0.0) or 0.0),
                "std": float(raw.get("std", 0.0) or 0.0),
            }
        return out

    out: dict[str, dict] = {}
    for col_meta in meta.get("columns", []):
        col_name = str(col_meta.get("name", "") or "")
        if not col_name:
            continue
        is_numeric = bool(col_meta.get("is_numeric", False))
        samples = [str(v) for v in (col_meta.get("samples") or [])[:50]]
        fill_rate = float(col_meta.get("fill_rate", 1.0) or 1.0)
        total_count = max(
            int(round(row_count * fill_rate)),
            1 if row_count and fill_rate > 0 else 0,
        )
        unique_count = int(col_meta.get("cardinality", 0) or 0)
        if unique_count <= 0 and samples:
            unique_count = len(set(samples))
        out[col_name] = {
            "is_numeric": is_numeric,
            "strings": [] if is_numeric else list(samples),
            "sample_values": samples,
            "unique_count": unique_count,
            "total_count": total_count,
            "fill_rate": fill_rate,
            "mean": float(col_meta.get("mean", 0.0) or 0.0),
            "std": 0.0,
        }
    return out


def _registry_source_artifacts_from_meta(
    *,
    org_id: str,
    source_id: str,
    schema_revision: str,
    meta: dict[str, Any],
) -> _CachedRegistrySourceArtifacts:
    cached = _registry_source_artifact_cache_get((org_id, source_id, schema_revision))
    if cached is not None:
        return cached

    from apps.api_server.routers.query import _graph_nodes_from_cached_meta

    query_hints = meta.get("query_hints", [])
    normalized_query_hints = query_hints if isinstance(query_hints, list) else []
    return _registry_source_artifact_cache_put(
        (org_id, source_id, schema_revision),
        _CachedRegistrySourceArtifacts(
            nodes=_graph_nodes_from_cached_meta(
                org_id=org_id,
                dataset_id=source_id,
                schema_revision=schema_revision,
                schema_meta=meta,
            ),
            profile=_profiles_from_registry_meta(meta),
            query_hints=normalized_query_hints,
        ),
    )


# ── AutoPlanner ────────────────────────────────────────────────────────────────

class AutoPlanner:
    """
    Zero-config autonomous query planner.

    Usage:
        planner = AutoPlanner(data_dir=Path("test_files"))
        planner.build_knowledge()
        plan = planner.plan("revenue", "product line", agg="sum")
        result, row_count, trace = planner.execute_plan(plan)
    """

    def __init__(
        self,
        data_dir: Path,
        max_rows: int = 3000,
        mojo_binary: Path | None = None,
        join_min_confidence: float = 0.40,
        llm_policy: str = "never",
    ) -> None:
        self.data_dir           = Path(data_dir)
        self.max_rows           = max_rows
        self._mojo_binary       = mojo_binary or self._find_mojo()
        self._join_min_conf     = join_min_confidence
        self._llm_policy        = llm_policy

        # Populated by build_knowledge() / from_registry()
        self.tables:   dict[str, list[dict]]     = {}   # source → records (lazy-loaded)
        self.profiles: dict[str, dict]           = {}   # source → col → stats
        self.graph:    Any                       = {}   # SchemaGraph (imported lazily)
        self._mojo_profiles:     dict[str, dict] = {}
        self._relations:         dict[str, list] = {}
        self._join_cache:        dict[tuple, list[dict]] = {}
        self._join_evidence_cache: dict[tuple[str, str, str, str], dict[str, float]] = {}
        self._group_join_evidence_cache: dict[tuple[str, str, str, str, str], dict[str, float]] = {}
        self._adaptive_source_context: dict[str, AdaptiveSourceContext] = {}
        self.mojo_engines:       list[str]       = []
        self._field_map_cache:   dict[str, dict] = {}   # hint → Mojo field_analysis entry
        # Lazy record loading — Parquet paths for sources not yet loaded into memory
        self._parquet_paths: dict[str, Path]     = {}   # source → .parquet cache path
        # query_hints from Arrow Parquet metadata — same data the LLM reads
        self._query_hints_by_src: dict[str, list[dict]] = {}
        # connections from source registry
        self._connections: list[dict] = []
        self._plan_cache: dict[tuple[str, str | None, str, str | None], QueryPlan] = {}
        self._join_candidate_columns: dict[str, dict[str, dict[str, Any]]] = {}
        self._metric_resolution_cache: dict[
            tuple[str, str | None, str],
            tuple[str, str, float, str, list[str]],
        ] = {}
        self._dimension_resolution_cache: dict[
            tuple[str, str | None],
            tuple[str, str, float, list[str]],
        ] = {}
        # Cached planners are shared across requests, so public execution
        # entrypoints must serialize mutation of internal caches and tables.
        self._state_lock = threading.RLock()
        # Vector resolver — built once after graph is populated, used in resolve_metric/dimension
        self._vector_resolver: Any = None

    def _llm_confirm_plan(self, **_kwargs: Any) -> dict[str, Any] | None:
        """Optional LLM review hook. Tests monkeypatch this when they want review behavior."""
        return None

    # ── Binary detection ──────────────────────────────────────────────────────

    @staticmethod
    def _find_mojo() -> Path | None:
        """Search standard paths for the compiled Mojo simulate binary."""
        root = Path(__file__).parent.parent.parent.parent   # repo root
        candidates = [
            root / "mojo_build" / "simulate",
            Path("mojo_build") / "simulate",
            Path.home() / ".algenta" / "mojo_build" / "simulate",
        ]
        for p in candidates:
            resolved = p.resolve() if p.exists() else None
            if resolved and resolved.exists() and os.access(str(resolved), os.X_OK):
                return resolved
        return None

    def _call_mojo(self, payload: dict, timeout: int = 30) -> dict | None:
        if not self._mojo_binary:
            return None
        engine_type = str(payload.get("engine_type", "unknown"))
        should_try_pool = (
            _PLANNER_MOJO_TRANSPORT in {"auto", "pool"}
            and engine_type in _PLANNER_MOJO_SHARED_ENGINES
        )
        if should_try_pool:
            try:
                result = invoke_engine_sync(payload, timeout=float(timeout))
                if result is not None and "error" not in result:
                    return result
                if _PLANNER_MOJO_TRANSPORT == "pool":
                    return None
                logger.debug(
                    "auto_planner_mojo_transport_fallback",
                    engine=engine_type,
                    transport="pool_to_legacy",
                )
            except Exception as exc:
                if _PLANNER_MOJO_TRANSPORT == "pool":
                    logger.debug(
                        "auto_planner_mojo_error",
                        error=str(exc),
                        engine=engine_type,
                        transport="pool",
                    )
                    return None
                logger.debug(
                    "auto_planner_mojo_transport_fallback",
                    error=str(exc),
                    engine=engine_type,
                    transport="pool_to_legacy",
                )
        should_try_resident = _PLANNER_MOJO_TRANSPORT == "resident" or (
            _PLANNER_MOJO_TRANSPORT == "auto"
            and _should_use_resident_planner_mojo(engine_type, payload)
        )
        if should_try_resident:
            try:
                result = invoke_planner_mojo(
                    payload,
                    binary_path=self._mojo_binary,
                    timeout=float(timeout),
                )
                if result is not None and "error" not in result:
                    return result
                if _PLANNER_MOJO_TRANSPORT == "resident":
                    return None
                logger.debug(
                    "auto_planner_mojo_transport_fallback",
                    engine=engine_type,
                    transport="resident_to_subprocess",
                )
            except Exception as exc:
                if _PLANNER_MOJO_TRANSPORT == "resident":
                    logger.debug(
                        "auto_planner_mojo_error",
                        error=str(exc),
                        engine=engine_type,
                        transport="resident",
                    )
                    return None
                logger.debug(
                    "auto_planner_mojo_transport_fallback",
                    error=str(exc),
                    engine=engine_type,
                    transport="resident_to_subprocess",
                )
        try:
            r = subprocess.run(  # noqa: S603 - fixed local binary path discovered by _find_mojo()
                [str(self._mojo_binary)],
                input=json.dumps(payload).encode(),
                capture_output=True,
                timeout=timeout,
            )
            if r.returncode == 0:
                out = json.loads(r.stdout)
                if "error" not in out:
                    return out
        except Exception as exc:
            logger.debug(
                "auto_planner_mojo_error",
                error=str(exc),
                engine=engine_type,
                transport="subprocess",
            )
        return None

    def _probe_engines(self) -> list[str]:
        """Return list of confirmed Mojo engine names.

        Result cached to .algenta_cache/engines.json and only re-probed
        when the Mojo binary mtime changes (saves ~1.4s per warm startup).
        """
        cd = self._cache_dir()
        engines_cache = cd / "engines.json"

        # Cache hit: binary unchanged
        if self._mojo_binary and engines_cache.exists():
            try:
                binary_mtime = self._mojo_binary.stat().st_mtime
                cache_mtime = engines_cache.stat().st_mtime
                if cache_mtime > binary_mtime:
                    cached = json.loads(engines_cache.read_text()).get("engines", [])
                    logger.debug("auto_planner_engines_cache_hit", engines=cached)
                    return cached
            except Exception as exc:
                logger.debug(
                    "auto_planner_engines_cache_read_error",
                    error=str(exc),
                )

        probes = {
            "column_profile": {
                "engine_type": "column_profile",
                "columns": {"x": {"values": ["1", "2", "3"], "strings": [], "sample_size": 3}},
            },
            "relation_detect": {
                "engine_type": "relation_detect",
                "source": "_probe",
                "min_confidence": 0.70,
                "columns": {"a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0], "c": [2.0, 8.0, 18.0]},
            },
            "field_map": {
                "engine_type": "field_map",
                "data": {"revenue": [100.0, 200.0, 150.0], "cost": [60.0, 90.0, 70.0]},
            },
            "column_match": {
                "engine_type": "column_match",
                "source_a": "_q",
                "source_b": "_s",
                "columns_a": [{"name": "revenue", "semantic_type": "currency", "polarity": 1,
                               "distribution": "lognormal", "mean": 150.0, "std": 50.0}],
                "columns_b": [{"name": "EXT_PRICE", "semantic_type": "currency", "polarity": 1,
                               "distribution": "lognormal", "mean": 5000.0, "std": 2000.0}],
                "min_confidence": 0.10,
            },
            "join_detect": {
                "engine_type": "join_detect",
                "source_a": "A",
                "source_b": "B",
                "min_confidence": 0.30,
                "columns": {
                    "A.id": {"values": ["X1", "X2", "X3"], "unique_ratio": 0.99, "sample_size": 3},
                    "B.id": {"values": ["X1", "X2", "X4"], "unique_ratio": 0.99, "sample_size": 3},
                },
            },
            "string_similarity": {
                "engine_type": "string_similarity",
                "hint_words": ["business", "unit"],
                "columns": ["LEACH_BU", "PRODUCT_LINE"],
                "threshold": 0.0,
            },
            "column_rank": {
                "engine_type": "column_rank",
                "hint_words": ["unit", "price"],
                "candidates": [
                    {
                        "source": "POS",
                        "column": "UNIT_PRICE",
                        "role": "unit_measure",
                        "fill_rate": 1.0,
                    },
                    {
                        "source": "POS",
                        "column": "EXT_PRICE",
                        "role": "derived_measure",
                        "fill_rate": 1.0,
                    },
                ],
                "context": {
                    "source_type": "POS",
                    "query_role": "unit_measure",
                },
                "top_k": 2,
            },
            "monte_carlo": {
                "engine_type": "monte_carlo",
                "runs": 10,
                "variables": [{"name": "x", "distribution": "normal", "mean": 0, "std": 1}],
                "objective": "x",
            },
        }
        supported = []
        for name, payload in probes.items():
            result = self._call_mojo(payload, timeout=5)
            if result is not None:
                supported.append(name)

        # Persist so next startup skips probing
        try:
            cd.mkdir(parents=True, exist_ok=True)
            engines_cache.write_text(json.dumps({"engines": supported}))
        except Exception as exc:
            logger.debug(
                "auto_planner_engines_cache_write_error",
                error=str(exc),
            )

        return supported

    # ── Registry-backed knowledge building ───────────────────────────────────

    @classmethod
    def from_registry(
        cls,
        org_id: str,
        data_dir: Path | None = None,
        mojo_binary: Path | None = None,
        join_min_confidence: float = 0.40,
        llm_policy: str = "never",
        allowed_source_ids: set[str] | None = None,
    ) -> AutoPlanner:
        """
        Build an AutoPlanner from pre-registered sources in the source registry.

        Sources registered via POST /v1/ingest (or /v1/map) have pre-built:
          - Arrow Parquet files with embedded algenta_schema metadata
          - .meta.json files with columns, roles, formulas, query_hints
          - connections.json with detected join keys

        This path is much faster than CSV profiling because the schema work
        was already done at registration time.  The LLM uses the same
        query_hints metadata to decide which columns to pick.

        Example:
            planner = AutoPlanner.from_registry("my-org-id")
            plan = planner.plan("revenue", "product line")
        """
        from apps.api_server.services import source_registry as _reg

        instance = cls(
            data_dir=data_dir or Path("."),
            mojo_binary=mojo_binary,
            join_min_confidence=join_min_confidence,
            llm_policy=llm_policy,
        )

        if instance._mojo_binary:
            instance.mojo_engines = instance._probe_engines()

        # Load all sources for this org from the registry
        sources = _reg.list_sources(org_id)
        if allowed_source_ids is not None:
            sources = [entry for entry in sources if entry.get("id") in allowed_source_ids]
        graph: dict = {}
        query_hints_by_src: dict[str, list[dict]] = {}
        connections = _reg.get_connections(org_id)
        if allowed_source_ids is not None:
            connections = [
                conn for conn in connections
                if conn.get("source_a") in allowed_source_ids
                and conn.get("source_b") in allowed_source_ids
            ]

        for src_entry in sources:
            src_id   = src_entry["id"]
            src_name = src_entry["name"]
            meta     = _reg.get_source_meta(org_id, src_id)
            if not meta:
                continue
            source_schema_revision = str(
                src_entry.get("schema_revision") or _reg.source_schema_revision(org_id, src_id)
            )
            artifacts = _registry_source_artifacts_from_meta(
                org_id=org_id,
                source_id=src_id,
                schema_revision=source_schema_revision,
                meta=meta,
            )

            # Reconstruct ColumnNode graph from persisted metadata
            nodes = artifacts.nodes
            if nodes:
                graph[src_name] = nodes

            # Store query_hints for metric resolution
            hints = artifacts.query_hints
            if hints:
                query_hints_by_src[src_name] = hints

            # Reuse persisted planner stats and lazy-load records only on execution.
            instance.profiles[src_name] = artifacts.profile
            parquet_path = _reg.get_source_parquet_path(org_id, src_id)
            if parquet_path is not None:
                instance._parquet_paths[src_name] = parquet_path

        instance.graph = graph
        instance._query_hints_by_src = query_hints_by_src
        instance._connections        = connections
        instance._rebuild_adaptive_context()
        instance._build_vector_resolver()

        # Pre-populate join cache from registry connections
        for conn in connections:
            src_a = conn.get("source_a_name", "")
            src_b = conn.get("source_b_name", "")
            if src_a and src_b:
                ck = (min(src_a, src_b), max(src_a, src_b))
                instance._join_cache.setdefault(ck, []).append({
                    "field_a":     conn["col_a"],
                    "source_a":    src_a,
                    "field_b":     conn["col_b"],
                    "source_b":    src_b,
                    "confidence":  conn.get("confidence", 0.70),
                    "overlap":     conn.get("overlap", 0.5),
                    "cardinality": conn.get("cardinality", "many_to_many"),
                })

        logger.debug(
            "auto_planner_from_registry",
            org_id=org_id,
            sources=list(graph.keys()),
            connections=len(connections),
        )
        return instance

    # ── Knowledge building ────────────────────────────────────────────────────

    def discover_sources(self) -> list[str]:
        """Scan data_dir for supported local tabular files and return source names."""
        return list(_discover_local_source_map(self.data_dir).keys())

    # ── Parquet cache ─────────────────────────────────────────────────────────

    def _cache_dir(self) -> Path:
        return self.data_dir / ".algenta_cache"

    def _cache_fresh(self, name: str, csv_path: Path) -> bool:
        """True if meta.json + Parquet exist and are newer than the CSV."""
        cd        = self._cache_dir()
        meta_path = cd / f"{name}.meta.json"
        pq_path   = cd / f"{name}.parquet"
        if not meta_path.exists() or not pq_path.exists():
            return False
        try:
            meta = json.loads(meta_path.read_text())
            if meta.get("cache_version") != _CACHE_VERSION:
                return False
        except Exception:
            return False
        csv_mtime   = csv_path.stat().st_mtime
        cache_mtime = min(meta_path.stat().st_mtime, pq_path.stat().st_mtime)
        return cache_mtime > csv_mtime

    def _load_from_cache(self, name: str) -> tuple[dict, dict, list]:
        """
        Fast warm-path cache load — returns (profiles, mojo_profiles, relations)
        from the JSON meta file only.  Raw records are NOT loaded here; they are
        lazy-loaded from Parquet only when execute_plan() actually needs them.
        """
        cd       = self._cache_dir()
        meta_raw = json.loads((cd / f"{name}.meta.json").read_text())
        prof      = meta_raw.get("profiles",      {})
        mojo_prof = meta_raw.get("mojo_profiles", {})
        relations = meta_raw.get("relations",     [])
        # Register the Parquet path for lazy record loading
        self._parquet_paths[name] = cd / f"{name}.parquet"
        return prof, mojo_prof, relations

    def _ensure_records(self, name: str) -> None:
        """
        Lazy-load raw records from the Parquet cache if not already in memory.
        Called by execute_plan() for each source it actually needs.
        """
        if name in self.tables:
            return
        pq_path = self._parquet_paths.get(name)
        if pq_path and pq_path.exists():
            try:
                import pyarrow.parquet as pq
                initialize_pyarrow_parquet_runtime()
                table = pq.read_table(str(pq_path))
                self.tables[name] = table.to_pylist()
                logger.debug("auto_planner_records_lazy_loaded", src=name,
                             rows=len(self.tables[name]))
            except Exception as exc:
                logger.debug("auto_planner_parquet_lazy_error", src=name, error=str(exc))

    def _write_cache(self, name: str, recs: list[dict],
                     mojo_profiles: dict, relations: list,
                     profiles: dict | None = None) -> None:
        """Persist records as Parquet + all metadata as JSON.

        Saves Python profiles, Mojo profiles, and relations so warm load
        skips all profiling (not just Mojo profiling).
        Uses per-column type inference with string fallback to handle
        mixed-type CSV columns (e.g. numeric columns with empty strings).
        """
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            cd = self._cache_dir()
            cd.mkdir(parents=True, exist_ok=True)

            if not recs:
                return

            keys = list(recs[0].keys())
            arrays: dict[str, pa.Array] = {}
            for k in keys:
                vals = []
                for record in recs:
                    value = record.get(k)
                    if (
                        isinstance(value, str)
                        and value.strip().lower() in {"", "?", "none", "null", "nan"}
                    ):
                        vals.append(None)
                    else:
                        vals.append(value)
                try:
                    arrays[k] = pa.array(vals)
                except Exception:
                    # Mixed types or invalid values → coerce to string
                    arrays[k] = pa.array(
                        [str(v) if v is not None else None for v in vals],
                        type=pa.string(),
                    )

            table = pa.table(arrays)
            buf = io.BytesIO()
            pq.write_table(table, buf)
            (cd / f"{name}.parquet").write_bytes(buf.getvalue())
            (cd / f"{name}.meta.json").write_text(json.dumps({
                "cache_version": _CACHE_VERSION,
                "profiles":      profiles or {},
                "mojo_profiles": mojo_profiles,
                "relations":     relations,
            }))
            logger.debug("auto_planner_cache_written", src=name, rows=len(recs))
        except Exception as exc:
            logger.debug("auto_planner_cache_write_error", src=name, error=str(exc))

    def build_knowledge(self, source_map: dict[str, str] | None = None) -> None:
        """
        Load all sources, profile, run Mojo analysis, build schema graph.

        Arrow Parquet cache: on first run, results are persisted to
        {data_dir}/.algenta_cache/{name}.parquet + .meta.json.
        Subsequent calls load from cache when the source CSV hasn't changed,
        reducing load time from ~7s → ~300ms.

        source_map: optional {name → filename} override.
                    If None, auto-discovers local CSV and Parquet files in data_dir.
        """
        t0 = time.perf_counter()

        # ── Probe Mojo engines ────────────────────────────────────────────────
        if self._mojo_binary:
            self.mojo_engines = self._probe_engines()
            logger.debug("auto_planner_engines", engines=self.mojo_engines)

        # ── Load sources ──────────────────────────────────────────────────────
        if source_map is None:
            source_map = _discover_local_source_map(self.data_dir)

        self.tables        = {}
        self.profiles      = {}
        self._mojo_profiles = {}
        self._relations     = {}
        self._plan_cache    = {}
        self._join_candidate_columns = {}
        self._join_evidence_cache = {}
        self._group_join_evidence_cache = {}
        self._adaptive_source_context = {}
        self._metric_resolution_cache = {}
        self._dimension_resolution_cache = {}

        need_mojo: list[str] = []   # sources that must be re-profiled via Mojo

        for name, fname in source_map.items():
            p = self.data_dir / fname
            if not p.exists():
                continue

            if self._cache_fresh(name, p):
                # ── Fast path: load from Parquet cache ────────────────────────
                # Records are NOT loaded here — lazy-loaded at execute time.
                try:
                    prof, mojo_prof, relations = self._load_from_cache(name)
                    self.profiles[name]       = prof
                    self._mojo_profiles[name] = mojo_prof
                    self._relations[name]     = relations
                    logger.debug("auto_planner_cache_hit", src=name)
                    continue
                except Exception as exc:
                    logger.debug("auto_planner_cache_load_error", src=name, error=str(exc))

            # ── Slow path: parse local source ────────────────────────────────
            recs = _load_records(p, max_rows=self.max_rows)
            if recs:
                self.tables[name]   = recs
                self.profiles[name] = _profile_records(recs)
                need_mojo.append(name)

        # ── Parallel Mojo: column_profile + relation_detect (only uncached) ───
        if need_mojo:
            need_items = [(n, self.profiles[n]) for n in need_mojo if n in self.profiles]
            if "column_profile" in self.mojo_engines and "relation_detect" in self.mojo_engines:
                with ThreadPoolExecutor(max_workers=max(len(need_items) * 2, 1)) as ex:
                    mp_f  = list(ex.map(self._mojo_profile_source,   need_items))
                    rel_f = list(ex.map(self._mojo_relations_source,  need_items))
                for name, mp  in mp_f:
                    self._mojo_profiles[name] = mp
                for name, rel in rel_f:
                    self._relations[name] = rel
            elif "column_profile" in self.mojo_engines:
                for name, mp in (self._mojo_profile_source(i) for i in need_items):
                    self._mojo_profiles[name] = mp
                for name in need_mojo:
                    self._relations.setdefault(name, [])
            else:
                for name in need_mojo:
                    self._mojo_profiles.setdefault(name, {})
                    self._relations.setdefault(name, [])

            # Persist newly profiled sources to cache (include Python profiles)
            for name in need_mojo:
                if name in self.tables:
                    self._write_cache(
                        name, self.tables[name],
                        self._mojo_profiles.get(name, {}),
                        self._relations.get(name, []),
                        self.profiles.get(name, {}),
                    )

        # ── Build schema graph ────────────────────────────────────────────────
        from apps.api_server.routers.query import build_schema_graph
        self.graph = build_schema_graph(self.profiles, self._mojo_profiles, self._relations)
        self._rebuild_adaptive_context()

        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug(
            "auto_planner_knowledge_built",
            sources=list(self.tables.keys()),
            engines=self.mojo_engines,
            elapsed_ms=round(elapsed, 1),
        )
        self._build_vector_resolver()

    def resolve_fields_batch(
        self,
        *,
        metric:    tuple[str, str | None, str | None] | None = None,
        group_by:  tuple[str, str | None, str | None] | None = None,
        date:      tuple[str, str | None, str | None] | None = None,
        filter_:   tuple[str, str | None, str | None] | None = None,
    ) -> dict[str, Any]:
        """
        Batch-resolve all plan field types through the vector resolver in one call.

        Each argument is a (hint, preferred_source, role_hint) triple or None.
        Returns a dict keyed by field type. Each value is a VectorResolverResult
        or None if the resolver is unavailable or the field was not requested.

        Planner should inspect each result's .outcome to route:
          COLUMN_MATCH  → use source/column directly
          META_QUERY    → forward to meta-query execution layer
          AMBIGUOUS     → fall through to column_match engine
          NO_COLUMN_MATCH → fall through

        Example:
            results = planner.resolve_fields_batch(
                metric   = ("extended price",  "POS",  "derived_measure"),
                group_by = ("customer name",   "POS",  "other"),
            )
        """
        if self._vector_resolver is None:
            return {"metric": None, "group_by": None, "date": None, "filter": None}
        return self._vector_resolver.resolve_plan_fields(
            metric=metric,
            group_by=group_by,
            date=date,
            filter_=filter_,
        )

    def _build_vector_resolver(self) -> None:
        """
        Build the ColumnVectorResolver from the current schema graph.
        Called once after graph is populated (build_knowledge or from_registry).
        Silently skips if graph is empty or import fails.
        """
        if not self.graph:
            return
        try:
            from mojo.engine.vector_kernels.resolver import ColumnVectorResolver
            base_resolver = ColumnVectorResolver.from_planner_graph(self.graph)
            fill_rates: dict[tuple[str, str], float] = {}
            for source_name, columns in self.graph.items():
                for column_name, node in columns.items():
                    fill_rates[(source_name, column_name)] = float(
                        getattr(node, "fill_rate", 1.0) or 1.0
                    )
            use_mojo_column_rank = (
                "column_rank" in self.mojo_engines
                and _MOJO_COLUMN_RANK_MODE in {"auto", "force"}
            )
            if use_mojo_column_rank:
                self._vector_resolver = MojoColumnRankResolver(
                    base_resolver,
                    call_mojo=self._call_mojo,
                    fill_rates=fill_rates,
                    binary_path=self._mojo_binary,
                )
                resolver_mode = "mojo_column_rank"
            else:
                self._vector_resolver = base_resolver
                resolver_mode = "python"
            n_cols = sum(
                len(list(cols.keys())) for cols in self.graph.values()
            )
            logger.debug(
                "auto_planner_vector_resolver_built",
                sources=list(self.graph.keys()),
                n_columns=n_cols,
                mode=resolver_mode,
            )
        except Exception as exc:
            logger.debug("auto_planner_vector_resolver_skip", reason=str(exc))
            self._vector_resolver = None

    def _append_vector_resolver_source(self, source_name: str) -> bool:
        """
        Incrementally append one new source to the current vector resolver.

        Returns True when the current resolver was updated in place or no
        resolver update was needed for that source. Returns False when the
        resolver must be rebuilt from the full graph.
        """
        resolver = self._vector_resolver
        if resolver is None:
            return False
        graph_cols = self.graph.get(source_name)
        if not graph_cols:
            return True
        append_source = getattr(resolver, "append_planner_graph_source", None)
        if not callable(append_source):
            return False
        fill_rates = {
            (source_name, column_name): float(getattr(node, "fill_rate", 1.0) or 1.0)
            for column_name, node in graph_cols.items()
            if getattr(node, "is_numeric", True)
            and float(getattr(node, "fill_rate", 1.0) or 1.0) >= 0.02
        }
        handled = bool(
            append_source(
                source_name,
                graph_cols,
                fill_rates=fill_rates,
            )
        )
        if handled:
            logger.debug(
                "auto_planner_vector_resolver_appended",
                source=source_name,
                n_columns=sum(len(cols) for cols in self.graph.values()),
                mode=resolver.__class__.__name__,
            )
        return handled

    def refresh_registry_source(
        self,
        *,
        org_id: str,
        source_id: str,
        source_name: str,
        schema_meta: dict[str, Any],
        source_schema_revision: str,
        parquet_path: Path | None,
        new_connections: list[dict[str, Any]],
    ) -> None:
        """
        Incrementally apply one newly registered source to an existing registry planner.

        This avoids reconstructing the full planner graph from source-registry
        metadata on every registration when a warm planner for the same
        org/visibility already exists.
        """
        had_graph_source = source_name in self.graph
        artifacts = _registry_source_artifacts_from_meta(
            org_id=org_id,
            source_id=source_id,
            schema_revision=source_schema_revision,
            meta=schema_meta,
        )

        if artifacts.nodes:
            self.graph[source_name] = artifacts.nodes
        self.profiles[source_name] = artifacts.profile
        if artifacts.query_hints:
            self._query_hints_by_src[source_name] = artifacts.query_hints
        else:
            self._query_hints_by_src.pop(source_name, None)

        self.tables.pop(source_name, None)
        self._mojo_profiles.pop(source_name, None)
        self._relations.pop(source_name, None)
        if parquet_path is not None:
            self._parquet_paths[source_name] = parquet_path
        else:
            self._parquet_paths.pop(source_name, None)

        # Query planning caches are schema-dependent and must be cleared after a
        # new source or join graph edge is introduced.
        self._plan_cache.clear()
        self._metric_resolution_cache.clear()
        self._dimension_resolution_cache.clear()
        self._join_candidate_columns.clear()
        self._join_evidence_cache.clear()
        self._group_join_evidence_cache.clear()

        # Replace any stale connection state involving this source, then append
        # the newly detected registry-backed joins.
        self._connections = [
            conn
            for conn in self._connections
            if conn.get("source_a") != source_id
            and conn.get("source_b") != source_id
            and conn.get("source_a_name") != source_name
            and conn.get("source_b_name") != source_name
        ]
        if new_connections:
            self._connections.extend(new_connections)

        # Re-prime the join cache from persisted registry edges. Any
        # query-computed join-key fallbacks will be repopulated lazily.
        self._join_cache = {}
        for conn in self._connections:
            src_a = str(conn.get("source_a_name") or "")
            src_b = str(conn.get("source_b_name") or "")
            if not src_a or not src_b:
                continue
            cache_key = (min(src_a, src_b), max(src_a, src_b))
            self._join_cache.setdefault(cache_key, []).append(
                {
                    "field_a": conn["col_a"],
                    "source_a": src_a,
                    "field_b": conn["col_b"],
                    "source_b": src_b,
                    "confidence": conn.get("confidence", 0.70),
                    "overlap": conn.get("overlap", 0.5),
                    "cardinality": conn.get("cardinality", "many_to_many"),
                }
            )

        self._adaptive_source_context[source_name] = AdaptiveSourceContext(
            join_distinctiveness=tuple(
                self._build_source_distinctiveness(source_name, join_only=True)
            ),
            column_distinctiveness=tuple(
                self._build_source_distinctiveness(source_name, join_only=False)
            ),
        )
        if had_graph_source or not self._append_vector_resolver_source(source_name):
            self._build_vector_resolver()

    def _mojo_profile_source(self, args: tuple) -> tuple[str, dict]:
        name, prof = args
        result = self._call_mojo({
            "engine_type": "column_profile",
            "columns": _build_mojo_column_profile_columns(
                prof,
                value_limit=30,
                string_limit=20,
            ),
        })
        return name, (result or {}).get("profiles", {})

    def _mojo_relations_source(self, args: tuple) -> tuple[str, list]:
        name, prof = args
        numeric = {f: i for f, i in prof.items() if i.get("is_numeric") and i.get("numeric")}
        if len(numeric) < 3:
            return name, []
        n = min(min(len(i["numeric"]) for i in numeric.values()), 500)
        result = self._call_mojo({
            "engine_type": "relation_detect",
            "source": name,
            "min_confidence": 0.70,
            "columns": {c: i["numeric"][:n] for c, i in numeric.items()},
        })
        return name, (result or {}).get("relationships", [])

    # ── Metric resolution ──────────────────────────────────────────────────────

    def _resolve_from_query_hints(
        self,
        hint: str,
        preferred_source: str | None,
        agg: str,
    ) -> tuple[str, str, float, str] | None:
        """
        Use query_hints from Arrow Parquet schema metadata to resolve a metric.

        query_hints structure (same as what the LLM reads from /v1/map output):
          [
            {
              "metric_role": "derived_measure",
              "description": "total / aggregate value ...",
              "columns": [
                {"name": "EXT_PRICE", "fill_rate": 0.99, "samples": [...],
                 "formula": "QTY × UNIT_PRICE", "mean": 5432.1}
              ]
            }, ...
          ]

        Returns (source, col, confidence, role) or None if no match.
        """
        from apps.api_server.routers.query import _metric_concepts, _metric_tokens

        hint_tokens = _metric_tokens(hint)
        hint_concepts = _metric_concepts(hint_tokens)
        best_src, best_col, best_conf, best_role = "", "", 0.0, "metric"
        preferred_best: tuple[str, str, float, str] | None = None

        # Role priority for different aggregations
        if agg in ("sum", "count"):
            role_order = ("derived_measure", "base_measure", "unit_measure", "ratio", "metric")
        elif agg == "avg":
            role_order = ("unit_measure", "ratio", "derived_measure", "base_measure", "metric")
        else:
            role_order = ("derived_measure", "unit_measure", "base_measure", "ratio", "metric")

        role_rank = {r: i for i, r in enumerate(role_order)}

        sources = (
            [preferred_source] + [s for s in self._query_hints_by_src if s != preferred_source]
            if preferred_source
            else list(self._query_hints_by_src.keys())
        )

        for src in sources:
            hints_list = self._query_hints_by_src.get(src, [])
            for hint_entry in hints_list:
                role = hint_entry.get("metric_role", "metric")
                for col_meta in hint_entry.get("columns", []):
                    col      = col_meta.get("name", "")
                    fill     = col_meta.get("fill_rate", 1.0)
                    if fill < 0.02:
                        continue

                    col_tokens = _metric_tokens(col)
                    if not col_tokens:
                        continue
                    col_concepts = _metric_concepts(col_tokens)

                    # Token overlap with hint
                    fwd  = len(hint_tokens & col_tokens) / len(col_tokens)
                    bwd  = len(hint_tokens & col_tokens) / max(len(hint_tokens), 1)
                    name_overlap = (fwd + bwd) / 2
                    concept_overlap = (
                        len(hint_concepts & col_concepts) / max(len(hint_concepts), 1)
                        if hint_concepts else 0.0
                    )

                    # Role rank bonus (lower rank = higher priority role)
                    role_bonus = (
                        max(
                            0,
                            (len(role_order) - role_rank.get(role, len(role_order)))
                            / len(role_order),
                        )
                        * 0.20
                    )

                    # Formula bonus
                    formula_bonus = 0.10 if col_meta.get("formula") else 0.0

                    # Preferred source bonus
                    pref_bonus = 0.18 if preferred_source and src == preferred_source else 0.0

                    typed_penalty = 0.0
                    identifier_tokens = {
                        "id",
                        "identifier",
                        "number",
                        "no",
                        "code",
                        "key",
                        "person",
                        "rep",
                    }
                    measure_tokens = {
                        "price",
                        "cost",
                        "amount",
                        "total",
                        "extended",
                        "value",
                        "revenue",
                        "sales",
                        "qty",
                        "quantity",
                    }
                    identifier_density = len(identifier_tokens & col_tokens) / max(
                        len(col_tokens),
                        1,
                    )
                    combined_tokens = col_tokens | col_concepts
                    measure_density = len(measure_tokens & combined_tokens) / max(
                        len(combined_tokens),
                        1,
                    )
                    hint_requests_identifier = bool(
                        identifier_tokens & (hint_tokens | hint_concepts)
                    )
                    hint_requests_measure = bool(measure_tokens & (hint_tokens | hint_concepts))
                    if "unit" in hint_concepts and "total" in col_concepts:
                        typed_penalty -= 0.16
                    if "total" in hint_concepts and "unit" in col_concepts:
                        typed_penalty -= 0.14
                    if (
                        "overhead" in hint_concepts
                        and "overhead" not in col_concepts
                        and {"cost", "price"} & col_concepts
                    ):
                        typed_penalty -= 0.22
                    if (
                        "total" in hint_concepts
                        and role == "base_measure"
                        and not ({"total", "price", "cost"} & col_concepts)
                    ):
                        typed_penalty -= 0.18
                    if (
                        "sales" in hint_tokens
                        and {"person", "rep", "number", "no", "id"} & col_tokens
                    ):
                        typed_penalty -= 0.24
                    if (
                        {"sales", "revenue"} & hint_tokens
                        and "cost" in col_concepts
                        and "price" not in col_concepts
                        and not {"amount", "revenue", "sales", "value"} & combined_tokens
                    ):
                        typed_penalty -= 0.24
                    if (
                        {"sales", "revenue"} & hint_tokens
                        and {
                            "price",
                            "amount",
                            "extended",
                            "revenue",
                            "sales",
                            "value",
                        }
                        & combined_tokens
                    ):
                        typed_penalty += 0.14
                        if role == "derived_measure":
                            typed_penalty += 0.04
                        if col_meta.get("formula"):
                            typed_penalty += 0.04
                    if agg in ("sum", "avg") and not hint_requests_identifier:
                        typed_penalty -= (
                            max(identifier_density - 0.35 * measure_density, 0.0) * 0.90
                        )
                    if (
                        agg in ("sum", "avg")
                        and hint_requests_measure
                        and role in {"derived_measure", "unit_measure", "base_measure"}
                    ):
                        typed_penalty += measure_density * 0.18

                    score = (
                        0.40 * name_overlap
                        + concept_overlap * 0.18
                        + role_bonus
                        + formula_bonus
                        + pref_bonus
                        + fill * 0.10
                        + typed_penalty
                    )

                    preferred_signal = max(
                        name_overlap,
                        concept_overlap,
                        measure_density if hint_requests_measure else 0.0,
                    )
                    if (
                        preferred_source
                        and src == preferred_source
                        and preferred_signal >= 0.18
                        and score >= 0.25
                        and (
                            preferred_best is None
                            or score > preferred_best[2]
                        )
                    ):
                        preferred_best = (src, col, score, role)

                    if score > best_conf:
                        best_conf = score
                        best_src  = src
                        best_col  = col
                        best_role = role

        if preferred_best is not None:
            p_src, p_col, p_conf, p_role = preferred_best
            same_metric_name = bool(best_col and p_col and p_col == best_col)
            if (
                p_conf + 0.02 >= best_conf
                or (same_metric_name and p_conf >= best_conf - 0.18)
                or (hint_requests_measure and p_conf >= best_conf - 0.12)
            ):
                return p_src, p_col, round(p_conf, 3), p_role

        if best_src and best_conf > 0.15:
            return best_src, best_col, round(best_conf, 3), best_role
        return None

    def _field_map_hint(self, hint: str, preferred_source: str | None = None) -> dict:
        """
        Use Mojo field_map to get semantic properties of a hint word.

        Strategy: find a source column whose name is most similar to the hint,
        take a small sample of its values, and run field_map on it.
        Falls back to lightweight Python inference on failure.
        """
        if hint in self._field_map_cache:
            return self._field_map_cache[hint]

        # Find the best matching column across sources to sample real values
        best_col_vals: list[float] = []
        best_overlap  = 0.0
        hint_tokens   = set(re.findall(r"[a-z0-9]+", hint.lower()))

        sources = (
            [preferred_source] + [s for s in self.profiles if s != preferred_source]
            if preferred_source
            else list(self.profiles.keys())
        )

        for src in sources:
            if src not in self.profiles:
                continue
            for col, info in self.profiles[src].items():
                if not info.get("is_numeric") or not info.get("numeric"):
                    continue
                col_tok = set(re.findall(r"[a-z0-9]+", col.lower()))
                if not col_tok:
                    continue
                fwd     = len(hint_tokens & col_tok) / len(col_tok)
                bwd     = len(hint_tokens & col_tok) / max(len(hint_tokens), 1)
                overlap = (fwd + bwd) / 2
                if overlap > best_overlap:
                    best_overlap  = overlap
                    best_col_vals = info["numeric"][:30]

        if "field_map" in self.mojo_engines and best_col_vals:
            result = self._call_mojo({
                "engine_type": "field_map",
                "data": {hint: best_col_vals},
            })
            if result:
                analysis = result.get("field_analysis", {}).get(hint, {})
                self._field_map_cache[hint] = analysis
                return analysis

        # Pure-Python inference fallback
        analysis = self._python_field_map(hint)
        self._field_map_cache[hint] = analysis
        return analysis

    @staticmethod
    def _python_field_map(hint: str) -> dict:
        """Lightweight field_map without Mojo."""
        h = hint.lower()
        # Unit
        if any(w in h for w in ("rate", "pct", "percent", "ratio", "margin_%", "share")):
            unit = "percentage"
        elif any(w in h for w in ("revenue", "price", "cost", "amount", "sales", "margin",
                                  "spend", "invoice", "value", "ext", "total")):
            unit = "currency"
        elif any(w in h for w in ("qty", "quantity", "count", "units", "volume")):
            unit = "count"
        elif any(w in h for w in ("days", "time", "duration", "lead", "delivery")):
            unit = "time"
        else:
            unit = "unknown"

        # Polarity
        if any(w in h for w in ("cost", "expense", "loss", "return", "refund")):
            polarity = -1
        else:
            polarity = 1

        # Distribution
        dist = "lognormal" if unit in ("currency", "count") else "normal"

        # Semantic type
        if unit == "currency":
            sem = "currency"
        elif unit == "count":
            sem = "count"
        elif unit == "percentage":
            sem = "percentage"
        else:
            sem = "metric"

        return {"polarity": polarity, "distribution": dist, "unit": unit,
                "semantic_type": sem, "confidence": 0.60}

    def resolve_metric(
        self,
        hint: str,
        preferred_source: str | None = None,
        agg: str = "sum",
    ) -> tuple[str, str, float, str, list[str]]:
        """
        Find the best (source, column) for a metric hint.

        Returns (source, col, confidence, role, steps).
        Pipeline:
          1. field_map (Mojo) → semantic properties of hint
          2. column_match (Mojo) → cross-source column scoring
          3. resolve_metric_column (Python) → fallback with schema graph
        """
        from apps.api_server.routers.query import (
            BASE_MEASURE,
            DERIVED_MEASURE,
            METRIC,
            RATIO,
            UNIT_MEASURE,
            _metric_candidate_score,
            resolve_metric_column,
        )

        cache_key = (hint.strip().lower(), preferred_source, agg.strip().lower())
        cached = self._metric_resolution_cache.get(cache_key)
        if cached is not None:
            src, col, conf, role, steps = cached
            return src, col, conf, role, list(steps)

        steps: list[str] = []

        # ── Step 0: query_hints from Arrow Parquet metadata (registry path) ──
        # When sources are registered, their schema metadata includes query_hints
        # — the same structured data the LLM reads when deciding which column
        # to use.  We can use these directly to skip the Mojo field_map step.
        if self._query_hints_by_src:
            registry_result = self._resolve_from_query_hints(hint, preferred_source, agg)
            if registry_result:
                r_src, r_col, r_conf, r_role = registry_result
                steps.append(
                    f"[query_hints/registry] '{hint}' → {r_src}.{r_col}  "
                    f"conf={r_conf:.3f}  role={r_role}"
                )
                result = (r_src, r_col, r_conf, r_role, list(steps))
                self._metric_resolution_cache[cache_key] = result
                return r_src, r_col, r_conf, r_role, list(steps)

        # ── Step 1: Get semantic properties for the hint ──────────────────────
        analysis = self._field_map_hint(hint, preferred_source)
        sem_type  = analysis.get("semantic_type") or analysis.get("unit", "unknown")
        polarity  = analysis.get("polarity", 1)
        dist      = analysis.get("distribution", "lognormal")
        fm_engine = "field_map" if "field_map" in self.mojo_engines else "python_field_map"
        steps.append(
            f"[field_map/{fm_engine}] hint='{hint}' → "
            f"unit={analysis.get('unit', '?')} sem={sem_type} polarity={polarity} dist={dist}"
        )

        # ── Step 1.5: Vector resolver (token prefilter + bigram cosine) ─────────
        # Fast path: token posting → shortlist → SIMD-style score.
        # Routes by outcome:
        #   COLUMN_MATCH  → short-circuit and return immediately
        #   META_QUERY    → log, skip column resolution, fall through to NLP
        #   AMBIGUOUS / NO_COLUMN_MATCH → fall through to column_match engine
        if self._vector_resolver is not None:
            from mojo.engine.vector_kernels.resolver import ResolverOutcome
            _sem_to_role = {
                "currency": "derived_measure", "amount": "derived_measure",
                "count": "base_measure",        "quantity": "base_measure",
                "percentage": "ratio",           "ratio": "ratio",
            }
            _hint_tokens_vr = set(re.findall(r"[a-z0-9]+", hint.lower()))
            _role_hint_vr = _sem_to_role.get(sem_type, "derived_measure")
            if _hint_tokens_vr & {"unit", "rate", "per"}:
                _role_hint_vr = "unit_measure"

            _vr = self._vector_resolver.resolve(hint, preferred_source, _role_hint_vr)
            if _vr is not None:
                if _vr.outcome == ResolverOutcome.META_QUERY:
                    try:
                        from mojo.engine.vector_kernels.meta_executor import (
                            interpret_meta_query,
                            meta_op_to_sql_fragment,
                        )
                        _meta_op = interpret_meta_query(hint, _vr)
                        steps.append(
                            f"[meta_executor] {_meta_op.op_type.value.upper()}  "
                            f"entity={_meta_op.entity!r}  "
                            f"col={_meta_op.column or 'N/A'}  "
                            f"sql_expr={meta_op_to_sql_fragment(_meta_op)}  "
                            f"reason={_vr.reason.value}"
                        )
                    except Exception:
                        steps.append(
                            f"[vector_resolver] META_QUERY hint={hint!r}  "
                            f"reason={_vr.reason.value}  score={_vr.score:.3f}"
                        )
                    # Fall through: meta-query path — no column to short-circuit with
                elif _vr.outcome == ResolverOutcome.WEAK_MATCH:
                    # Non-metric fields accept WEAK_MATCH; metric fields fall through
                    # (caller checks sem_type — planner policy enforced here)
                    _weak_is_metric = sem_type in ("currency", "amount", "ratio", "percentage")
                    if not _weak_is_metric:
                        _vr_node = self.graph.get(_vr.source, {}).get(_vr.column)
                        _vr_role = _vr_node.role if _vr_node else DERIVED_MEASURE
                        steps.append(
                            f"[vector_resolver/weak] {_vr.source}.{_vr.column}  "
                            f"score={_vr.score:.3f}  gap={_vr.confidence_gap:.3f}"
                        )
                        result = (_vr.source, _vr.column, _vr.score, _vr_role, list(steps))
                        self._metric_resolution_cache[cache_key] = result
                        return _vr.source, _vr.column, _vr.score, _vr_role, list(steps)
                    # metric + WEAK_MATCH → fall through to column_match engine
                elif _vr.outcome == ResolverOutcome.COLUMN_MATCH:
                    _vr_node = self.graph.get(_vr.source, {}).get(_vr.column)
                    _vr_role = _vr_node.role if _vr_node else DERIVED_MEASURE
                    steps.append(
                        f"[vector_resolver] {_vr.source}.{_vr.column}  "
                        f"score={_vr.score:.3f}  gap={_vr.confidence_gap:.3f}  "
                        f"tok_overlap={_vr.token_overlap}"
                    )
                    result = (_vr.source, _vr.column, _vr.score, _vr_role, list(steps))
                    self._metric_resolution_cache[cache_key] = result
                    return _vr.source, _vr.column, _vr.score, _vr_role, list(steps)

        # ── Step 2: column_match Mojo engine (if available) ─────────────────
        if "column_match" in self.mojo_engines:
            best_src, best_col, best_conf, best_role = "", "", 0.0, METRIC
            query_col = {
                "name":          hint,
                "semantic_type": sem_type,
                "polarity":      polarity,
                "distribution":  dist,
                "mean":          0.0,
                "std":           0.0,
            }
            sources = (
                [preferred_source] + [s for s in self.graph if s != preferred_source]
                if preferred_source
                else list(self.graph.keys())
            )

            for src in sources:
                if src not in self.profiles:
                    continue
                # Build candidate columns for this source (numeric only)
                cands = []
                for col, info in self.profiles[src].items():
                    if not info.get("is_numeric"):
                        continue
                    if info.get("fill_rate", 1.0) < 0.02:
                        continue
                    mp_col = self._mojo_profiles.get(src, {}).get(col, {})
                    cands.append({
                        "name":          col,
                        "semantic_type": mp_col.get("semantic_type", ""),
                        "polarity":      1,
                        "distribution":  "lognormal",
                        "mean":          info.get("mean", 0.0),
                        "std":           info.get("std", 0.0),
                    })
                if not cands:
                    continue
                result = self._call_mojo({
                    "engine_type":    "column_match",
                    "source_a":       "_query",
                    "source_b":       src,
                    "columns_a":      [query_col],
                    "columns_b":      cands,
                    "min_confidence": 0.10,
                })
                if result and result.get("matches"):
                    sym_map_hint = {"%": "percent", "$": "dollar", "#": "number"}
                    hint_norm = hint.lower()
                    for sym, word in sym_map_hint.items():
                        hint_norm = hint_norm.replace(sym, f" {word} ")
                    hint_tokens_col = set(re.findall(r"[a-z0-9]+", hint_norm))
                    for m in result["matches"]:
                        col_name = m.get("field_b", "")
                        score    = float(m.get("score", 0.0))

                        # Name similarity bonus — when the hint closely names the column,
                        # trust that signal over statistical magnitude.
                        # e.g. "unit price" → UNIT_PRICE (sim=1.0) should beat EXT_PRICE (sim=0.5)
                        # Normalize column name: map symbols to words so
                        # "%" → "percent" matches hint "percent", "$" → "dollar"
                        sym_map = {
                            "%": "percent",
                            "$": "dollar",
                            "#": "number",
                            "€": "euro",
                            "£": "pound",
                        }
                        col_norm = col_name.lower()
                        for sym, word in sym_map.items():
                            col_norm = col_norm.replace(sym, f" {word} ")
                        col_tokens = set(re.findall(r"[a-z0-9]+", col_norm))
                        if col_tokens:
                            fwd_sim = len(hint_tokens_col & col_tokens) / len(col_tokens)
                            bwd_sim = len(hint_tokens_col & col_tokens) / max(
                                len(hint_tokens_col),
                                1,
                            )
                            name_sim = (fwd_sim + bwd_sim) / 2
                        else:
                            name_sim = 0.0

                        # High name similarity → strongly prefer this column
                        if name_sim >= 0.80:
                            score = max(score, 0.50) + name_sim * 0.40
                        elif name_sim >= 0.40:
                            score += name_sim * 0.20

                        # Bonus: formula-proven column (derived_measure/unit_measure)
                        node = self.graph.get(src, {}).get(col_name)
                        role = node.role if node else METRIC

                        # Only apply magnitude/role bonuses when name similarity is low —
                        # for exact name matches the name bonus already dominates.
                        if name_sim < 0.70:
                            if role in (DERIVED_MEASURE,):
                                score += 0.15
                                if node and node.formula:
                                    score += 0.05
                                # Magnitude bonus: prefer the largest column
                                if node and node.magnitude_class == "large":
                                    score += 0.15
                                elif node and node.magnitude_class == "medium":
                                    score += 0.06
                            elif role in (BASE_MEASURE, UNIT_MEASURE):
                                score += 0.08
                                if node and node.magnitude_class == "large":
                                    score += 0.08
                            elif role == RATIO and sem_type in ("percentage", "ratio"):
                                # Prefer RATIO columns when the hint is explicitly about %/ratios
                                score += 0.12

                        # Preferred source — when explicitly specified, strongly bias toward it.
                        # This ensures "revenue pref=POS" finds POS.EXT_PRICE
                        # instead of Inventory.RESERVE_$.
                        if preferred_source and src == preferred_source:
                            score += 0.20
                        if score > best_conf:
                            best_conf = score
                            best_src  = src
                            best_col  = col_name
                            best_role = role
                            steps.append(
                                f"[column_match] {src}.{col_name}  score={score:.3f}  role={role}"
                            )

            if best_src and best_conf > 0.10:
                steps.append(
                    f"[column_match] SELECTED  {best_src}.{best_col}  "
                    f"conf={best_conf:.3f}  role={best_role}"
                )
                result = (best_src, best_col, round(best_conf, 3), best_role, list(steps))
                self._metric_resolution_cache[cache_key] = result
                return best_src, best_col, round(best_conf, 3), best_role, list(steps)

        # ── Step 3: Python resolve_metric_column (fallback / always valid) ────
        hint_tokens = set(re.findall(r"[a-z0-9]+", hint.lower()))
        # Choose role from semantic type
        hint_role_tokens = set(re.findall(r"[a-z0-9]+", hint.lower()))
        if hint_role_tokens & {"unit", "rate", "per"}:
            target_role = UNIT_MEASURE
        elif sem_type in ("count",):
            target_role = BASE_MEASURE
        elif sem_type in ("percentage", "ratio"):
            target_role = RATIO
        elif sem_type in ("currency",):
            target_role = DERIVED_MEASURE
        else:
            target_role = DERIVED_MEASURE   # default: best overall metric

        src, col, conf, candidates = resolve_metric_column(
            target_role, hint_tokens, self.graph, preferred_source
        )
        if src:
            node = self.graph.get(src, {}).get(col)
            role = node.role if node else METRIC
            if len(candidates) >= 2:
                gap = candidates[0]["confidence"] - candidates[1]["confidence"]
                steps.append(
                    "[resolve_metric_column/gap] "
                    f"top={candidates[0]['column']} "
                    f"second={candidates[1]['column']} gap={gap:.3f}"
                )
            else:
                # Cross-role gap: score all other numeric columns regardless of role
                # so we can surface disambiguation signal even when only one role
                # match exists (e.g. single UNIT_MEASURE vs several DERIVED_MEASUREs).
                _cross_best_col, _cross_best_score = "", float("-inf")
                _search_srcs = (
                    [preferred_source] if preferred_source else list(self.graph.keys())
                )
                for _alt_src in _search_srcs:
                    if _alt_src not in self.graph:
                        continue
                    for _alt_col, _alt_node in self.graph[_alt_src].items():
                        if not _alt_node.is_numeric or _alt_col == col:
                            continue
                        if _alt_node.fill_rate < 0.02:
                            continue
                        _alt_s, _, _ = _metric_candidate_score(
                            target_role, hint_tokens, _alt_src, _alt_col, _alt_node
                        )
                        if _alt_s > _cross_best_score:
                            _cross_best_score = _alt_s
                            _cross_best_col = _alt_col
                if _cross_best_col:
                    _gap = conf - _cross_best_score
                    steps.append(
                        "[resolve_metric_column/gap] "
                        f"top={col} second={_cross_best_col} gap={_gap:.3f}"
                    )
            steps.append(
                f"[resolve_metric_column] {src}.{col}  conf={conf:.3f}  role={role}"
            )
            result = (src, col, conf, role, list(steps))
            self._metric_resolution_cache[cache_key] = result
            return src, col, conf, role, list(steps)

        if preferred_source:
            fallback_src, fallback_col, fallback_conf, fallback_role, fallback_steps = (
                self.resolve_metric(hint, None, agg)
            )
            if fallback_src:
                steps.append(
                    "[resolve_metric/preferred_source_miss] "
                    f"broadened search beyond {preferred_source}"
                )
                steps.extend(
                    step
                    for step in fallback_steps
                    if step not in steps
                )
                result = (
                    fallback_src,
                    fallback_col,
                    fallback_conf,
                    fallback_role,
                    list(steps),
                )
                self._metric_resolution_cache[cache_key] = result
                return fallback_src, fallback_col, fallback_conf, fallback_role, list(steps)

        steps = steps + ["[resolve_metric_column] no match found"]
        result = ("", "", 0.0, METRIC, list(steps))
        self._metric_resolution_cache[cache_key] = result
        return "", "", 0.0, METRIC, steps

    # ── Dimension resolution ───────────────────────────────────────────────────

    def resolve_dimension(
        self,
        hint: str,
        preferred_source: str | None = None,
        pref_bonus: float = 0.12,
    ) -> tuple[str, str, float, list[str]]:
        """
        Find the best (source, column) for a dimension/group-by hint.

        Pipeline (no hardcoded column/abbreviation maps):
          1. Token overlap on column names (with known-abbrev expansion for cust/qty/etc.)
          2. Acronym detection: "BU" → initials of "Business Unit" (algorithmic)
          3. Value-semantic scoring: do the cell VALUES mention hint words?
          4. Cardinality filter: drop near-constant columns (useless for group-by)
          5. Preferred-source bonus to break ties
        """
        from apps.api_server.routers.query import (
            CATEGORY,
            IDENTIFIER,
            TEXT,
            TIME,
            resolve_group_column,
            resolve_group_column_graph,
        )

        cache_key = (hint.strip().lower(), preferred_source)
        cached = self._dimension_resolution_cache.get(cache_key)
        if cached is not None:
            src, col, score, steps = cached
            return src, col, score, list(steps)

        steps: list[str] = []
        raw_hint_words = re.findall(r"[a-z0-9]+", hint.lower())
        stop_words = {
            "a",
            "an",
            "and",
            "at",
            "by",
            "for",
            "from",
            "in",
            "of",
            "on",
            "the",
            "to",
            "with",
        }
        hint_words = [w for w in raw_hint_words if w not in stop_words] or raw_hint_words

        # Pass 1 uses the token-overlap algorithm in query.py which does exact
        # token intersection.  We pass the raw hint words (no hardcoded expansion).
        dim_hints = hint_words
        hint_token_set = _semantic_token_set(" ".join(dim_hints))
        hinted_sources = {
            src for src in self.graph
            if hint_token_set & _source_token_set(src)
        }

        if hinted_sources:
            source_hint_best: tuple[str, str, float] | None = None
            for src in hinted_sources:
                src_tokens = _source_token_set(src)
                remaining_tokens = [tok for tok in dim_hints if tok not in src_tokens] or dim_hints
                remaining_set = set(remaining_tokens)
                exact_named_candidate: tuple[str, str, float] | None = None
                for col, node in self.graph.get(src, {}).items():
                    col_tokens = _tokenize_identifier(col)
                    if not col_tokens:
                        continue
                    exact_name_match = bool(
                        remaining_set
                        and remaining_set == col_tokens
                    )
                    if exact_name_match:
                        fill = self.profiles.get(src, {}).get(col, {}).get(
                            "fill_rate",
                            node.fill_rate,
                        )
                        total_count = self.profiles.get(src, {}).get(col, {}).get("total_count", 0)
                        if fill > 0.0 and total_count > 0:
                            score = round(1.65 + min(fill, 1.0) * 0.20, 3)
                            if exact_named_candidate is None or score > exact_named_candidate[2]:
                                exact_named_candidate = (src, col, score)
                        continue

                    prof_info = self.profiles.get(src, {}).get(col, {})
                    unique_count = prof_info.get("unique_count", 0)
                    total_count = prof_info.get("total_count", 0)
                    is_low_card_numeric = bool(
                        node.is_numeric
                        and total_count >= 1
                        and 1 < unique_count <= max(12, int(total_count * 0.05))
                    )
                    base = {CATEGORY: 0.50, TEXT: 0.30, TIME: 0.50, IDENTIFIER: 0.30}.get(
                        node.role,
                        0.20 if not node.is_numeric else (0.16 if is_low_card_numeric else 0.0),
                    )
                    if base == 0.0:
                        continue
                    if node.role == TIME and not _hint_requests_time(hint_words):
                        continue
                    fill = prof_info.get("fill_rate", node.fill_rate)
                    if fill < 0.02:
                        continue
                    if total_count >= 20 and unique_count <= 1:
                        continue
                    query_cov = len(remaining_set & col_tokens) / max(len(remaining_set), 1)
                    col_cov = len(remaining_set & col_tokens) / max(len(col_tokens), 1)
                    exact_cover = min(query_cov, col_cov)
                    if query_cov < 0.60 or col_cov < 0.45:
                        continue

                    fuzzy, acro, val_sem = _dimension_semantic_evidence(
                        remaining_tokens, col, prof_info.get("strings", [])[:30]
                    )
                    score = (
                        base + max(fuzzy * 0.70, exact_cover * 1.10, acro * 0.50) + val_sem
                    ) * max(fill, 0.0)
                    score += 0.35 + min(exact_cover, 1.0) * 0.25
                    if source_hint_best is None or score > source_hint_best[2]:
                        source_hint_best = (src, col, round(score, 3))

                if exact_named_candidate is not None:
                    g_src, g_col, g_score = exact_named_candidate
                    steps.append(
                        "[resolve_group/source_hint_exact] "
                        f"'{hint}' → {g_src}.{g_col}  score={g_score:.3f}"
                    )
                    result = (g_src, g_col, g_score, list(steps))
                    self._dimension_resolution_cache[cache_key] = result
                    return g_src, g_col, g_score, list(steps)

            if source_hint_best is not None:
                g_src, g_col, g_score = source_hint_best
                steps.append(
                    f"[resolve_group/source_hint] '{hint}' → {g_src}.{g_col}  score={g_score:.3f}"
                )
                result = (g_src, g_col, g_score, list(steps))
                self._dimension_resolution_cache[cache_key] = result
                return g_src, g_col, g_score, list(steps)

        if preferred_source and preferred_source in self.graph:
            pref_dim_tokens = _semantic_token_set(" ".join(dim_hints))
            pref_exact: tuple[str, str, float] | None = None
            pref_src_tokens = _source_token_set(preferred_source)
            for col, node in self.graph[preferred_source].items():
                col_tokens = _tokenize_identifier(col)
                if pref_dim_tokens and pref_dim_tokens == col_tokens:
                    fill = self.profiles.get(preferred_source, {}).get(col, {}).get(
                        "fill_rate",
                        node.fill_rate,
                    )
                    total_count = self.profiles.get(preferred_source, {}).get(
                        col,
                        {},
                    ).get("total_count", 0)
                    if fill > 0.0 and total_count > 0:
                        exact_score = round(1.55 + min(fill, 1.0) * 0.18 + pref_bonus, 3)
                        if pref_exact is None or exact_score > pref_exact[2]:
                            pref_exact = (preferred_source, col, exact_score)
                    continue

                prof_info = self.profiles.get(preferred_source, {}).get(col, {})
                unique_count = prof_info.get("unique_count", 0)
                total_count = prof_info.get("total_count", 0)
                is_low_card_numeric = bool(
                    node.is_numeric
                    and total_count >= 1
                    and 1 < unique_count <= max(12, int(total_count * 0.05))
                )
                base = {CATEGORY: 0.50, TEXT: 0.30, TIME: 0.50, IDENTIFIER: 0.30}.get(
                    node.role,
                    0.20 if not node.is_numeric else (0.16 if is_low_card_numeric else 0.0),
                )
                if base == 0.0:
                    continue
                if node.role == TIME and not _hint_requests_time(hint_words):
                    continue
                fill = prof_info.get("fill_rate", node.fill_rate)
                if fill < 0.02:
                    continue
                if prof_info.get("total_count", 0) >= 20 and prof_info.get("unique_count", 99) <= 1:
                    continue
                col_to_query = len(pref_dim_tokens & col_tokens) / len(col_tokens)
                query_to_col = len(pref_dim_tokens & col_tokens) / max(len(pref_dim_tokens), 1)
                exact_cover = min(col_to_query, query_to_col)
                if exact_cover < 0.95:
                    continue
                source_bonus = 0.22 if pref_dim_tokens & pref_src_tokens else 0.0
                exact_score = round(
                    (base + 0.70 + pref_bonus) * max(fill, 0.0)
                    + source_bonus
                    + exact_cover * 0.20,
                    3,
                )
                if pref_exact is None or exact_score > pref_exact[2]:
                    pref_exact = (preferred_source, col, exact_score)
            if pref_exact is not None:
                g_src, g_col, g_score = pref_exact
                steps.append(
                    "[resolve_group/preferred_exact] "
                    f"'{hint}' → {g_src}.{g_col}  score={g_score:.3f}"
                )
                result = (g_src, g_col, g_score, list(steps))
                self._dimension_resolution_cache[cache_key] = result
                return g_src, g_col, g_score, list(steps)

        # ── Pass 1: Token overlap (existing algorithm) ────────────────────────
        g_src, g_col, g_score = resolve_group_column_graph(
            dim_hints, preferred_source or "", self.graph
        )

        # Re-score preferred source with a bonus
        if preferred_source and preferred_source in self.graph:
            p_col, p_score = resolve_group_column(dim_hints, preferred_source, self.graph)
            if p_col and p_score + pref_bonus >= g_score:
                g_src, g_col, g_score = preferred_source, p_col, p_score + pref_bonus

        # ── Pass 1b: Cardinality filter BEFORE acronym pass ───────────────────
        # Remove near-constant columns (e.g. INVEN_BUSINESS_UNIT="COM DIST" × 500 rows)
        # so they don't block the acronym/value pass from winning later.
        g_src, g_col, g_score = self._apply_cardinality_filter(
            g_src, g_col, g_score, dim_hints, preferred_source, pref_bonus
        )

        # Reject weak semantic matches from the initial token-overlap pass.
        # This prevents partial matches like a date field containing "ship"
        # from winning when the user asked for a non-time dimension.
        if g_src and g_col:
            prof_info = self.profiles.get(g_src, {}).get(g_col, {})
            fuzzy0, acro0, val_sem0 = _dimension_semantic_evidence(
                hint_words, g_col, prof_info.get("strings", [])[:30]
            )
            col_tokens0 = _semantic_token_set(g_col)
            query_cov0 = len(hint_token_set & col_tokens0) / max(len(hint_token_set), 1)
            col_cov0 = len(hint_token_set & col_tokens0) / max(len(col_tokens0), 1)
            node0 = self.graph.get(g_src, {}).get(g_col)
            if node0 and node0.role == TIME and not _hint_requests_time(hint_words):
                steps.append(
                    "[resolve_group/filter] "
                    f"rejected {g_src}.{g_col} — time dimension for non-time hint"
                )
                g_src, g_col, g_score = "", "", 0.0
            elif (
                len(hint_words) >= 2
                and max(query_cov0, col_cov0) < 0.50
                and acro0 < 0.50
                and not (hinted_sources and g_src in hinted_sources)
            ):
                steps.append(
                    f"[resolve_group/filter] rejected {g_src}.{g_col} — low token coverage"
                )
                g_src, g_col, g_score = "", "", 0.0
            elif (
                len(hint_words) == 1
                and query_cov0 == 0.0
                and fuzzy0 < 0.55
                and acro0 < 0.50
                and not (hinted_sources and g_src in hinted_sources)
            ):
                steps.append(
                    f"[resolve_group/filter] rejected {g_src}.{g_col} — weak semantic evidence"
                )
                g_src, g_col, g_score = "", "", 0.0

        # ── Pass 2: Fuzzy name + acronym + value-semantic scoring ─────────────
        # Fully data-driven — no hardcoded abbreviation maps.
        #
        # Three signals combined:
        #   1. fuzzy_name_sim: prefix/bigram similarity on column NAME tokens
        #      → "cust"≈"customer", "qty"≈"quantity" without any static lookup.
        #   2. acronym: "BU" = initials of "Business Unit" (algorithmic)
        #   3. val_sem: cell VALUES mention hint words → data-level evidence
        #
        # Scoring is done via Mojo string_similarity engine (batch call) when
        # available, falling back to pure Python implementations.
        role_base = {CATEGORY: 0.50, TEXT: 0.30, TIME: 0.50, IDENTIFIER: 0.30}

        # Collect valid candidates in one pass
        candidates: list[tuple[str, str, object, float, float]] = []
        for src in self.graph:
            if hinted_sources and src not in hinted_sources and preferred_source not in {None, src}:
                continue
            for col, node in self.graph[src].items():
                _prof = self.profiles.get(src, {}).get(col, {})
                unique_count = _prof.get("unique_count", 0)
                total_count = _prof.get("total_count", 0)
                is_low_card_numeric = bool(
                    node.is_numeric
                    and total_count >= 1
                    and 1 < unique_count <= max(12, int(total_count * 0.05))
                )
                base = role_base.get(
                    node.role,
                    0.20 if not node.is_numeric else (0.16 if is_low_card_numeric else 0.0),
                )
                if base == 0.0:
                    continue
                if node.role == TIME and not _hint_requests_time(hint_words):
                    continue
                fill = getattr(node, "fill_rate", 1.0)
                if fill < 0.02:
                    continue
                if _prof.get("total_count", 1) >= 20 and _prof.get("unique_count", 99) <= 1:
                    continue
                candidates.append((src, col, node, base, fill))

        # Batch Mojo string_similarity call — one subprocess for all columns
        mojo_name_scores: dict[str, tuple[float, float]] = {}   # col → (fuzzy, acro)
        if "string_similarity" in self.mojo_engines and candidates:
            unique_cols = list({col for _, col, _, _, _ in candidates})
            mojo_result = self._call_mojo({
                "engine_type": "string_similarity",
                "hint_words": hint_words,
                "columns": unique_cols,
                "threshold": 0.0,
            })
            if mojo_result and "matches" in mojo_result:
                for m in mojo_result["matches"]:
                    mojo_name_scores[m["column"]] = (m["fuzzy"], m["acronym"])

        for src, col, _node, base, fill in candidates:
            # Name similarity: use Mojo result if available, else Python fallback
            if col in mojo_name_scores:
                fuzzy, acro = mojo_name_scores[col]
            else:
                fuzzy, acro, _ = _dimension_semantic_evidence(hint_words, col, [])

            # Value-semantic: cell VALUES mention hint words (always Python — needs raw data)
            prof_info = self.profiles.get(src, {}).get(col, {})
            sample_vals = prof_info.get("strings", [])[:30]
            val_sem = _value_semantic_score(hint_words, sample_vals)
            col_tokens = _semantic_token_set(col)
            source_tokens = _source_token_set(src)
            query_cov = len(hint_token_set & col_tokens) / max(len(hint_token_set), 1)
            col_cov = len(hint_token_set & col_tokens) / max(len(col_tokens), 1)
            exact_cover = min(query_cov, col_cov)
            source_bonus = 0.22 if hint_token_set & source_tokens else 0.0

            # Only proceed if we have a meaningful signal.
            # For multi-token hints we require actual token coverage, an acronym hit,
            # or value-level evidence. This suppresses fuzzy-only false positives like
            # "warehouse" -> "User Created" or "inventory type" -> date fields.
            if (
                len(hint_words) >= 2
                and max(query_cov, col_cov) < 0.50
                and acro < 0.50
                and source_bonus <= 0.0
            ):
                continue
            if (
                len(hint_words) == 1
                and query_cov == 0.0
                and acro < 0.50
                and fuzzy < 0.55
                and source_bonus <= 0.0
            ):
                continue

            # Combined score: base role + strongest name signal + data signal
            name_sig = max(acro * 0.50, fuzzy * 0.70, exact_cover * 1.05)
            exact_bonus = 0.0
            if exact_cover >= 0.95:
                exact_bonus = 0.55
            elif query_cov >= 0.60 and col_cov >= 0.45:
                exact_bonus = 0.18
            if (
                preferred_source
                and src == preferred_source
                and query_cov >= 0.95
                and col_cov >= 0.66
            ):
                exact_bonus += 0.22
            aug_score = (base + name_sig + val_sem) * max(fill, 0.0)
            pref_aug = pref_bonus if (preferred_source and src == preferred_source) else 0.0
            if not hinted_sources and preferred_source and src == preferred_source:
                pref_aug += 0.18
            unique_count = prof_info.get("unique_count", 0)
            total_count = prof_info.get("total_count", 0)
            low_card_penalty = 0.0
            if total_count >= 20 and unique_count <= 3 and exact_cover < 0.95:
                low_card_penalty += 0.18
            elif total_count >= 20 and unique_count <= 5 and exact_cover < 0.60:
                low_card_penalty += 0.08
            if hinted_sources and src not in hinted_sources:
                low_card_penalty += 0.22

            aug_score += pref_aug + exact_bonus + source_bonus - low_card_penalty

            if aug_score > g_score:
                g_src, g_col, g_score = src, col, aug_score
                steps.append(
                    f"[fuzzy/acro/val] {src}.{col}  fuzzy={fuzzy:.2f}  acro={acro:.2f}  "
                    f"val_sem={val_sem:.3f}  score={aug_score:.3f}"
                )

        # ── Pass 3: Final cardinality check on the acronym/value winner ───────
        # (In case Pass 2 selected a constant column via a high acronym score)
        g_src, g_col, g_score = self._apply_cardinality_filter(
            g_src, g_col, g_score, dim_hints, preferred_source, pref_bonus
        )

        if g_src:
            steps.append(f"[resolve_group] '{hint}' → {g_src}.{g_col}  score={g_score:.3f}")
        else:
            steps.append(f"[resolve_group] '{hint}' → no match")

        result = (g_src, g_col, g_score, list(steps))
        self._dimension_resolution_cache[cache_key] = result
        return g_src, g_col, g_score, list(steps)

    def _apply_cardinality_filter(
        self,
        src: str,
        col: str,
        score: float,
        dim_hints: list[str],
        preferred_source: str | None,
        pref_bonus: float,
    ) -> tuple[str, str, float]:
        """
        If the winning column is effectively constant,
        it's useless as a group-by dimension.  Re-rank by excluding it and
        finding the next-best match.

        This prevents columns like TYPE=['COMMERCIAL'] from winning
        over CUST_TYPE=['OEM','Broker','Repair'] in another source.
        """
        from apps.api_server.routers.query import resolve_group_column

        if not src or not col:
            return src, col, score

        info = self.profiles.get(src, {}).get(col, {})
        unique_count = info.get("unique_count", 99)
        total_count  = info.get("total_count", 1)

        # Only penalize if we have enough data to be confident
        if total_count >= 20 and unique_count <= 1:
            # Temporarily remove this node, find next best
            saved = self.graph.get(src, {}).get(col)
            if saved is not None:
                del self.graph[src][col]

            from apps.api_server.routers.query import resolve_group_column_graph
            n_src, n_col, n_score = resolve_group_column_graph(
                dim_hints, preferred_source or "", self.graph
            )
            if preferred_source and preferred_source in self.graph:
                p_col2, p_score2 = resolve_group_column(dim_hints, preferred_source, self.graph)
                if p_col2 and p_score2 + pref_bonus >= n_score:
                    n_src, n_col, n_score = preferred_source, p_col2, p_score2 + pref_bonus

            # Restore
            self.graph[src][col] = saved

            if n_src and n_col:
                return n_src, n_col, n_score

        return src, col, score

    def _same_source_dimension_candidate(
        self,
        source: str,
        hint: str,
    ) -> tuple[str, str, float, list[str]]:
        from apps.api_server.routers.query import CATEGORY, IDENTIFIER, TEXT, TIME

        if source not in self.graph:
            return "", "", 0.0, []

        raw_hint_words = re.findall(r"[a-z0-9]+", hint.lower())
        stop_words = {
            "a",
            "an",
            "and",
            "at",
            "by",
            "for",
            "from",
            "in",
            "of",
            "on",
            "the",
            "to",
            "with",
        }
        hint_words = [w for w in raw_hint_words if w not in stop_words] or raw_hint_words
        hint_token_set = _semantic_token_set(" ".join(hint_words))
        best_src, best_col, best_score = "", "", 0.0
        steps: list[str] = []

        for col, node in self.graph[source].items():
            prof = self.profiles.get(source, {}).get(col, {})
            unique_count = prof.get("unique_count", 0)
            total_count = prof.get("total_count", 0)
            is_low_card_numeric = bool(
                node.is_numeric
                and total_count >= 1
                and 1 < unique_count <= max(12, int(total_count * 0.05))
            )
            base = {CATEGORY: 0.50, TEXT: 0.30, TIME: 0.50, IDENTIFIER: 0.30}.get(
                node.role,
                0.20 if not node.is_numeric else (0.16 if is_low_card_numeric else 0.0),
            )
            if base == 0.0:
                continue
            if node.role == TIME and not _hint_requests_time(hint_words):
                continue
            fill = prof.get("fill_rate", node.fill_rate)
            if fill < 0.02:
                continue

            col_tokens = _semantic_token_set(col)
            if not col_tokens:
                continue
            query_cov = len(hint_token_set & col_tokens) / max(len(hint_token_set), 1)
            col_cov = len(hint_token_set & col_tokens) / max(len(col_tokens), 1)
            exact_cover = min(query_cov, col_cov)
            fuzzy, acro, val_sem = _dimension_semantic_evidence(
                hint_words, col, prof.get("strings", [])[:30]
            )
            if query_cov < 0.60 and acro < 0.80 and fuzzy < 0.55:
                continue
            if col_cov < 0.40 and acro < 0.95:
                continue

            score = (
                base + max(fuzzy * 0.70, exact_cover * 1.05, acro * 0.50) + val_sem
            ) * max(fill, 0.0)
            score += 0.40
            if score > best_score:
                best_src, best_col, best_score = source, col, round(score, 3)
                steps = [
                    "[resolve_group/self_correct_same_source] "
                    f"'{hint}' → {source}.{col}  score={best_score:.3f}"
                ]

        return best_src, best_col, best_score, steps

    # ── Join key detection ─────────────────────────────────────────────────────

    def find_join_keys(
        self,
        src_a: str,
        src_b: str,
    ) -> list[dict]:
        """
        Use Mojo join_detect to find join key pairs between two sources.

        Returns list of join key dicts sorted by confidence:
        [{"field_a", "field_b", "confidence", "cardinality", "overlap"}, ...]
        """
        cache_key = (min(src_a, src_b), max(src_a, src_b))
        if cache_key in self._join_cache:
            return self._join_cache[cache_key]

        if "join_detect" not in self.mojo_engines:
            result = self._python_join_keys(src_a, src_b)
            self._join_cache[cache_key] = result
            return result

        prof_a = self.profiles.get(src_a, {})
        prof_b = self.profiles.get(src_b, {})

        if not prof_a or not prof_b:
            self._join_cache[cache_key] = []
            return []

        columns: dict[str, dict] = {}
        columns.update(self._join_candidates_for_source(src_a))
        columns.update(self._join_candidates_for_source(src_b))

        if not columns:
            self._join_cache[cache_key] = []
            return []

        result = self._call_mojo({
            "engine_type":    "join_detect",
            "source_a":       src_a,
            "source_b":       src_b,
            "min_confidence": self._join_min_conf,
            "columns":        columns,
        })

        if result and result.get("join_keys"):
            keys = sorted(result["join_keys"], key=lambda x: x.get("confidence", 0), reverse=True)
            self._join_cache[cache_key] = keys
            return keys

        # Mojo returned no results → Python fallback
        fallback = self._python_join_keys(src_a, src_b)
        self._join_cache[cache_key] = fallback
        return fallback

    def _join_candidates_for_source(self, src: str) -> dict[str, dict[str, Any]]:
        cached = self._join_candidate_columns.get(src)
        if cached is not None:
            return cached

        prof = self.profiles.get(src, {})
        columns: dict[str, dict[str, Any]] = {}
        for col, info in prof.items():
            ur = info.get("unique_count", 0) / max(info.get("total_count", 1), 1)
            fill = info.get("fill_rate", 1.0)
            if fill < 0.05:
                continue
            if not info.get("is_numeric") or ur > 0.85:
                samples = [
                    str(v)
                    for v in (info.get("strings") or info.get("sample_values", []))[:30]
                ]
                if samples:
                    columns[f"{src}.{col}"] = {
                        "values": samples,
                        "unique_ratio": round(ur, 4),
                        "sample_size": info.get("total_count", 0),
                    }

        self._join_candidate_columns[src] = columns
        return columns

    def _sample_edge_evidence(
        self,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
        sample_limit: int = 400,
    ) -> dict[str, float]:
        cache_key = (left_source, left_key, right_source, right_key)
        cached = self._join_evidence_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

        self._ensure_records(left_source)
        self._ensure_records(right_source)
        left_rows = self.tables.get(left_source, [])
        right_rows = self.tables.get(right_source, [])
        if not left_rows or not right_rows:
            evidence = {"coverage": 1.0, "single_match_ratio": 1.0, "fanout_risk": 0.0}
            self._join_evidence_cache[cache_key] = evidence
            return dict(evidence)

        if len(left_rows) > sample_limit:
            step = max(len(left_rows) // sample_limit, 1)
            sampled_left = left_rows[::step][:sample_limit]
        else:
            sampled_left = left_rows

        right_index: dict[str, int] = {}
        for row in right_rows:
            key = _normalize_match_value(row.get(right_key))
            if not key:
                continue
            right_index[key] = right_index.get(key, 0) + 1

        eligible = 0
        matched = 0
        single = 0
        fanout_hits = 0
        for row in sampled_left:
            key = _normalize_match_value(row.get(left_key))
            if not key:
                continue
            eligible += 1
            count = right_index.get(key, 0)
            if count <= 0:
                continue
            matched += 1
            if count == 1:
                single += 1
            elif count > 1:
                fanout_hits += 1

        coverage = matched / max(eligible, 1)
        single_ratio = single / max(matched, 1)
        fanout_risk = fanout_hits / max(matched, 1)
        evidence = {
            "coverage": round(coverage, 4),
            "single_match_ratio": round(single_ratio, 4),
            "fanout_risk": round(fanout_risk, 4),
        }
        self._join_evidence_cache[cache_key] = evidence
        return dict(evidence)

    def _sample_group_edge_evidence(
        self,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
        group_col: str,
        sample_limit: int = 400,
    ) -> dict[str, float]:
        cache_key = (left_source, left_key, right_source, right_key, group_col)
        cached = self._group_join_evidence_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

        self._ensure_records(left_source)
        self._ensure_records(right_source)
        left_rows = self.tables.get(left_source, [])
        right_rows = self.tables.get(right_source, [])
        if not left_rows or not right_rows or not group_col:
            evidence = {"coverage": 1.0, "stable_ratio": 1.0, "conflict_ratio": 0.0}
            self._group_join_evidence_cache[cache_key] = evidence
            return dict(evidence)

        if len(left_rows) > sample_limit:
            step = max(len(left_rows) // sample_limit, 1)
            sampled_left = left_rows[::step][:sample_limit]
        else:
            sampled_left = left_rows

        group_map: dict[str, str] = {}
        conflict_keys: set[str] = set()
        for row in right_rows:
            key = _normalize_match_value(row.get(right_key))
            group_value = _normalize_match_value(row.get(group_col))
            if not key or not group_value:
                continue
            existing = group_map.get(key)
            if existing is None:
                group_map[key] = group_value
                continue
            if existing != group_value:
                conflict_keys.add(key)

        for key in conflict_keys:
            group_map.pop(key, None)

        eligible = 0
        matched = 0
        stable = 0
        conflicts = 0
        for row in sampled_left:
            key = _normalize_match_value(row.get(left_key))
            if not key:
                continue
            eligible += 1
            if key in conflict_keys:
                conflicts += 1
                continue
            if key in group_map:
                matched += 1
                stable += 1

        observed = matched + conflicts
        evidence = {
            "coverage": round(matched / max(eligible, 1), 4),
            "stable_ratio": round(stable / max(observed, 1), 4),
            "conflict_ratio": round(conflicts / max(observed, 1), 4),
        }
        self._group_join_evidence_cache[cache_key] = evidence
        return dict(evidence)

    def _build_source_distinctiveness(
        self,
        source: str,
        *,
        join_only: bool,
    ) -> list[tuple[float, int]]:
        out: list[tuple[float, int]] = []
        for _col, info in self.profiles.get(source, {}).items():
            total_count = int(info.get("total_count", 0) or 0)
            unique_count = int(info.get("unique_count", 0) or 0)
            fill = float(info.get("fill_rate", 0.0) or 0.0)
            if total_count <= 0 or unique_count <= 0 or fill < 0.05:
                continue
            unique_ratio = unique_count / max(total_count, 1)
            if join_only:
                is_numeric = bool(info.get("is_numeric", False))
                has_values = bool(info.get("strings") or info.get("sample_values") or [])
                if not has_values:
                    continue
                if is_numeric and unique_ratio < 0.70:
                    continue
            out.append((unique_ratio, unique_count))

        out.sort()
        return out

    def _rebuild_adaptive_context(self) -> None:
        context: dict[str, AdaptiveSourceContext] = {}
        for source in self.profiles:
            context[source] = AdaptiveSourceContext(
                join_distinctiveness=tuple(
                    self._build_source_distinctiveness(source, join_only=True)
                ),
                column_distinctiveness=tuple(
                    self._build_source_distinctiveness(source, join_only=False)
                ),
            )
        self._adaptive_source_context = context

    def _source_distinctiveness_distribution(
        self,
        source: str,
        *,
        join_only: bool,
    ) -> list[tuple[float, int]]:
        source_context = self._adaptive_source_context.get(source)
        if source_context is None:
            self._rebuild_adaptive_context()
            source_context = self._adaptive_source_context.get(source)
        if source_context is None:
            return []
        values = (
            source_context.join_distinctiveness
            if join_only
            else source_context.column_distinctiveness
        )
        return list(values)

    @staticmethod
    def _rank_fraction(value: float, population: list[float]) -> float:
        if not population:
            return 0.5
        below = sum(1 for item in population if item < value)
        equal = sum(1 for item in population if item == value)
        return (below + 0.5 * equal) / len(population)

    def _join_key_distinctiveness(
        self,
        source: str,
        key: str,
    ) -> tuple[float, int, float]:
        info = self.profiles.get(source, {}).get(key, {})
        total_count = int(info.get("total_count", 0) or 0)
        unique_count = int(info.get("unique_count", 0) or 0)
        if total_count <= 0 or unique_count <= 0:
            return 1.0, unique_count, 0.0

        unique_ratio = unique_count / max(total_count, 1)
        distribution = self._source_distinctiveness_distribution(source, join_only=True)
        ratio_rank = self._rank_fraction(unique_ratio, [ratio for ratio, _count in distribution])
        count_rank = self._rank_fraction(
            float(unique_count),
            [float(count) for _ratio, count in distribution],
        )
        fallback_ratio = min(unique_ratio / 0.50, 1.0)
        fallback_count = min(
            math.log(unique_count + 1.0, 2) / max(math.log(total_count + 1.0, 2), 1.0),
            1.0,
        )
        ratio_signal = 0.65 * ratio_rank + 0.35 * fallback_ratio
        count_signal = 0.65 * count_rank + 0.35 * fallback_count
        strength = 0.35 + 0.40 * ratio_signal + 0.25 * count_signal
        return round(min(max(strength, 0.30), 1.0), 6), unique_count, round(unique_ratio, 6)

    def _python_join_keys(self, src_a: str, src_b: str) -> list[dict]:
        """
        Pure-Python join key detection via token overlap on string column names.
        Used when Mojo join_detect is unavailable or returns nothing.
        """
        prof_a = self.profiles.get(src_a, {})
        prof_b = self.profiles.get(src_b, {})
        results: list[dict] = []

        def _norm(value: str) -> set[str]:
            return set(re.findall(r"[a-z0-9]+", value.lower()))

        for col_a, info_a in prof_a.items():
            if info_a.get("fill_rate", 1.0) < 0.05:
                continue
            if info_a.get("is_numeric"):
                ur_a = info_a.get("unique_count", 0) / max(info_a.get("total_count", 1), 1)
                if ur_a < 0.80:
                    continue
            toks_a = _norm(col_a)
            if not toks_a:
                continue
            for col_b, info_b in prof_b.items():
                if info_b.get("fill_rate", 1.0) < 0.05:
                    continue
                if info_b.get("is_numeric"):
                    ur_b = info_b.get("unique_count", 0) / max(info_b.get("total_count", 1), 1)
                    if ur_b < 0.80:
                        continue
                toks_b = _norm(col_b)
                if not toks_b:
                    continue
                # Name similarity
                both  = toks_a & toks_b
                union = toks_a | toks_b
                name_sim = len(both) / max(len(union), 1)
                if name_sim < 0.30:
                    continue

                # Value overlap estimate (sample intersection / union)
                vals_a = {
                    str(v)
                    for v in (info_a.get("strings") or info_a.get("sample_values", []))[:50]
                    if v
                }
                vals_b = {
                    str(v)
                    for v in (info_b.get("strings") or info_b.get("sample_values", []))[:50]
                    if v
                }
                if vals_a and vals_b:
                    overlap = len(vals_a & vals_b) / max(len(vals_a | vals_b), 1)
                else:
                    overlap = 0.0

                conf = name_sim * 0.60 + overlap * 0.40
                if conf >= self._join_min_conf:
                    results.append({
                        "field_a":     col_a,
                        "source_a":    src_a,
                        "field_b":     col_b,
                        "source_b":    src_b,
                        "confidence":  round(conf, 3),
                        "overlap":     round(overlap, 3),
                        "cardinality": "many_to_many",
                    })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results

    @staticmethod
    def _plan_cache_key(
        metric_hint: str,
        dim_hint: str | None,
        agg: str,
        preferred_source: str | None,
    ) -> tuple[str, str | None, str, str | None]:
        return (
            metric_hint.strip().lower(),
            (dim_hint or "").strip().lower() or None,
            agg.strip().lower(),
            preferred_source,
        )

    @staticmethod
    def _clone_plan(plan: QueryPlan) -> QueryPlan:
        cloned = replace(plan)
        cloned.join_hops = [replace(hop) for hop in plan.join_hops]
        cloned.intermediate_sources = list(plan.intermediate_sources)
        cloned.validation_notes = list(plan.validation_notes)
        cloned.mojo_ops = list(plan.mojo_ops)
        cloned.steps = list(plan.steps)
        return cloned

    @staticmethod
    def _reverse_join_cardinality(cardinality: str) -> str:
        if cardinality == "one_to_many":
            return "many_to_one"
        if cardinality == "many_to_one":
            return "one_to_many"
        return cardinality

    @staticmethod
    def _cardinality_penalty(cardinality: str) -> float:
        if cardinality in {"", "one_to_one", "many_to_one"}:
            return 1.0
        if cardinality == "one_to_many":
            return 0.82
        if cardinality == "many_to_many":
            return 0.62
        return 0.90

    @staticmethod
    def _group_dimension_join_key_multiplier(
        group_col: str | None,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
    ) -> float:
        if not group_col:
            return 1.0

        group_text = str(group_col or "").lower()
        group_is_inventory_dimension = any(
            token in group_text
            for token in (
                "inventory",
                "product",
                "vendor",
                "vend",
                "warehouse",
                "part",
                "item",
                "line",
                "type",
            )
        )
        if not group_is_inventory_dimension:
            return 1.0

        key_text = f"{left_key} {right_key}".lower()
        source_text = f"{left_source} {right_source}".lower()
        multiplier = 1.0
        if any(token in key_text for token in ("part", "item", "sku", "product", "catalog")):
            multiplier *= 1.10
        if any(token in key_text for token in ("order", "quote", "booking", "invoice", "request")):
            multiplier *= 0.90
        if (
            any(token in source_text for token in ("booking", "bookings", "order", "orders"))
            and "order" in key_text
        ):
            multiplier *= 1.35
        return multiplier

    def _join_key_semantic_multiplier(
        self,
        left_source: str,
        right_source: str,
        left_key: str,
        right_key: str,
    ) -> tuple[float, bool]:
        left_tokens = _semantic_token_set(left_key)
        right_tokens = _semantic_token_set(right_key)
        left_node = self.graph.get(left_source, {}).get(left_key)
        right_node = self.graph.get(right_source, {}).get(right_key)
        left_measure_like = bool(
            _JOIN_KEY_MEASURE_TOKENS & left_tokens
            or (left_node and left_node.role in _MEASURE_LIKE_ROLES)
        )
        right_measure_like = bool(
            _JOIN_KEY_MEASURE_TOKENS & right_tokens
            or (right_node and right_node.role in _MEASURE_LIKE_ROLES)
        )
        multiplier = 1.0
        if left_measure_like and right_measure_like:
            multiplier *= 0.52
        elif left_measure_like or right_measure_like:
            multiplier *= 0.76

        left_entity_like = bool(_JOIN_KEY_ENTITY_TOKENS & left_tokens)
        right_entity_like = bool(_JOIN_KEY_ENTITY_TOKENS & right_tokens)
        if left_entity_like and right_entity_like:
            multiplier *= 1.12
        elif left_entity_like or right_entity_like:
            multiplier *= 1.04

        if (
            left_node
            and right_node
            and left_node.is_numeric
            and right_node.is_numeric
            and not (left_entity_like or right_entity_like)
        ):
            multiplier *= 0.82

        return multiplier, left_measure_like and right_measure_like

    def _join_candidate_effective_conf(
        self,
        candidate: dict[str, Any],
        group_col: str | None = None,
    ) -> float:
        raw_conf = float(candidate.get("confidence", 0.0) or 0.0)
        card = str(candidate.get("cardinality", "") or "")
        penalty = self._cardinality_penalty(card)
        effective = raw_conf * penalty
        left_source = str(candidate.get("source_a", "") or "")
        right_source = str(candidate.get("source_b", "") or "")
        left_key_raw = str(candidate.get("field_a", "") or "").strip()
        right_key_raw = str(candidate.get("field_b", "") or "").strip()
        left_key = left_key_raw.lower()
        right_key = right_key_raw.lower()
        metadata_only = str(candidate.get("evidence_source", "") or "") == "registry"
        if left_source and right_source and left_key_raw and right_key_raw:
            if metadata_only:
                overlap = max(0.0, min(float(candidate.get("overlap", 0.5) or 0.5), 1.0))
                effective *= 0.72 + 0.28 * overlap
                if card in {"", "one_to_one", "many_to_one"}:
                    stability = 1.0
                    fanout_risk = 0.0
                elif card == "one_to_many":
                    stability = 0.82
                    fanout_risk = 0.18
                else:
                    stability = 0.64
                    fanout_risk = 0.36
                if group_col:
                    group_profile = self.profiles.get(right_source, {}).get(group_col, {})
                    group_fill = max(
                        0.0,
                        min(float(group_profile.get("fill_rate", 1.0) or 1.0), 1.0),
                    )
                    effective *= 0.80 + 0.20 * group_fill
            else:
                evidence = self._sample_edge_evidence(
                    left_source,
                    right_source,
                    left_key_raw,
                    right_key_raw,
                )
                if evidence["coverage"] <= 0.0 and not group_col:
                    return 0.0
                effective *= 0.60 + 0.40 * evidence["coverage"]
                stability = evidence["single_match_ratio"]
                fanout_risk = evidence["fanout_risk"]
                if group_col:
                    group_evidence = self._sample_group_edge_evidence(
                        left_source,
                        right_source,
                        left_key_raw,
                        right_key_raw,
                        group_col,
                    )
                    if evidence["coverage"] <= 0.0 and group_evidence["coverage"] <= 0.0:
                        return 0.0
                    stability = max(stability, group_evidence["stable_ratio"])
                    fanout_risk = max(0.0, fanout_risk - 0.80 * group_evidence["stable_ratio"])
                    effective *= 0.70 + 0.30 * group_evidence["coverage"]
                    effective *= 1.00 - 0.20 * group_evidence["conflict_ratio"]
            effective *= 0.70 + 0.30 * stability
            effective *= 1.00 - 0.25 * fanout_risk
            left_strength, left_unique_count, _left_unique_ratio = (
                self._join_key_distinctiveness(left_source, left_key_raw)
            )
            right_strength, right_unique_count, _right_unique_ratio = (
                self._join_key_distinctiveness(right_source, right_key_raw)
            )
            effective *= min(left_strength, right_strength)
            effective *= self._group_dimension_join_key_multiplier(
                group_col,
                left_source,
                right_source,
                left_key_raw,
                right_key_raw,
            )
            join_key_multiplier, both_measure_like = self._join_key_semantic_multiplier(
                left_source,
                right_source,
                left_key_raw,
                right_key_raw,
            )
            effective *= join_key_multiplier
            known_unique_counts = [
                count for count in (left_unique_count, right_unique_count) if count > 0
            ]
            if known_unique_counts and max(known_unique_counts) <= 20:
                effective *= 0.82
            elif known_unique_counts and max(known_unique_counts) <= 100:
                effective *= 0.92
        else:
            both_measure_like = False
        if (
            penalty < 1.0
            and left_key
            and right_key
            and left_key == right_key
            and not both_measure_like
        ):
            effective += 0.06
        return round(min(effective, 1.0), 6)

    def _normalize_join_candidate(
        self,
        left_source: str,
        right_source: str,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        source_a = candidate.get("source_a", "")
        source_b = candidate.get("source_b", "")
        field_a = candidate.get("field_a", "")
        field_b = candidate.get("field_b", "")
        card = str(candidate.get("cardinality", "") or "")

        if source_a == left_source and source_b == right_source:
            return {
                "field_a": field_a,
                "source_a": left_source,
                "field_b": field_b,
                "source_b": right_source,
                "confidence": float(candidate.get("confidence", 0.0) or 0.0),
                "cardinality": card,
                "overlap": float(candidate.get("overlap", 0.0) or 0.0),
            }

        return {
            "field_a": field_b,
            "source_a": left_source,
            "field_b": field_a,
            "source_b": right_source,
            "confidence": float(candidate.get("confidence", 0.0) or 0.0),
            "cardinality": self._reverse_join_cardinality(card),
            "overlap": float(candidate.get("overlap", 0.0) or 0.0),
        }

    def _registry_join_candidates(
        self,
        left_source: str,
        right_source: str,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for conn in self._connections:
            src_a = conn.get("source_a_name", "")
            src_b = conn.get("source_b_name", "")
            if src_a == left_source and src_b == right_source:
                matches.append({
                    "field_a": conn.get("col_a", ""),
                    "source_a": left_source,
                    "field_b": conn.get("col_b", ""),
                    "source_b": right_source,
                    "confidence": float(conn.get("confidence", 0.0) or 0.0),
                    "cardinality": str(conn.get("cardinality", "") or ""),
                    "overlap": float(conn.get("overlap", 0.5) or 0.5),
                    "evidence_source": "registry",
                })
            elif src_a == right_source and src_b == left_source:
                matches.append({
                    "field_a": conn.get("col_b", ""),
                    "source_a": left_source,
                    "field_b": conn.get("col_a", ""),
                    "source_b": right_source,
                    "confidence": float(conn.get("confidence", 0.0) or 0.0),
                    "cardinality": self._reverse_join_cardinality(
                        str(conn.get("cardinality", "") or "")
                    ),
                    "overlap": float(conn.get("overlap", 0.5) or 0.5),
                    "evidence_source": "registry",
                })
        matches.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        return matches

    def _direct_join_candidates(self, left_source: str, right_source: str) -> list[dict[str, Any]]:
        registry_matches = self._registry_join_candidates(left_source, right_source)
        if registry_matches:
            return registry_matches

        matches = [
            self._normalize_join_candidate(left_source, right_source, candidate)
            for candidate in self.find_join_keys(left_source, right_source)
        ]
        matches.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        return matches

    def _search_join_path(
        self,
        metric_src: str,
        group_src: str,
        group_col: str | None = None,
        max_hops: int = 4,
    ) -> tuple[list[JoinHop], float, list[str], str | None]:
        if metric_src == group_src:
            return [], 1.0, [], None

        known_sources = list(self.graph.keys())
        if metric_src not in known_sources or group_src not in known_sources:
            msg = f"Unknown source in join path search: {metric_src} -> {group_src}"
            return [], 0.0, [msg], msg

        candidate_paths: list[tuple[float, float, list[JoinHop], list[str]]] = []

        def _path_min_safe_conf(hops: list[JoinHop]) -> float:
            path_has_many_to_many = any(h.cardinality == "many_to_many" for h in hops)
            path_has_expansion = any(
                h.cardinality in {"one_to_many", "1:N", "many_to_many", "N:N"} for h in hops
            )
            exact_key_path = all(
                h.left_key.strip().lower() == h.right_key.strip().lower()
                for h in hops
                if h.left_key and h.right_key
            )
            if path_has_many_to_many:
                return 0.22 if exact_key_path else 0.48
            if exact_key_path:
                return 0.18
            if path_has_expansion:
                return 0.28
            return 0.24

        def _rank_candidates(
            current: str,
            next_src: str,
        ) -> tuple[list[dict[str, Any]], float, list[str], JoinHop] | None:
            direct_candidates = self._direct_join_candidates(current, next_src)
            if not direct_candidates:
                return None

            def _effective_conf_for_candidate(
                candidate: dict[str, Any],
                current_next_src: str = next_src,
            ) -> float:
                target_group_col = group_col if current_next_src == group_src else None
                return self._join_candidate_effective_conf(
                    candidate,
                    group_col=target_group_col,
                )

            ranked_candidates = sorted(
                direct_candidates,
                key=_effective_conf_for_candidate,
                reverse=True,
            )
            top = ranked_candidates[0]
            top_conf = float(top.get("confidence", 0.0) or 0.0)
            card = str(top.get("cardinality", "") or "")
            edge_effective_conf = _effective_conf_for_candidate(top)
            edge_notes: list[str] = []
            if len(ranked_candidates) > 1:
                second_effective_conf = _effective_conf_for_candidate(ranked_candidates[1])
                if second_effective_conf >= edge_effective_conf - 0.03:
                    edge_notes.append(
                        f"ambiguous join candidates between {current} and {next_src}"
                    )

            hop = JoinHop(
                left_source=current,
                right_source=next_src,
                left_key=str(top.get("field_a", "") or ""),
                right_key=str(top.get("field_b", "") or ""),
                confidence=round(top_conf, 3),
                cardinality=card,
                notes=list(edge_notes),
            )
            return ranked_candidates, edge_effective_conf, edge_notes, hop

        direct_path = _rank_candidates(metric_src, group_src)
        if direct_path is not None:
            _ranked_candidates, direct_effective_conf, direct_notes, direct_hop = direct_path
            direct_hops = [direct_hop]
            if direct_effective_conf >= _path_min_safe_conf(direct_hops):
                return (
                    direct_hops,
                    round(direct_effective_conf, 3),
                    list(dict.fromkeys(direct_notes)),
                    None,
                )

        def _dfs(
            current: str,
            visited: set[str],
            hops: list[JoinHop],
            raw_conf: float,
            effective_conf: float,
            notes: list[str],
        ) -> None:
            if len(hops) >= max_hops:
                return

            candidate_targets = [group_src] + [
                src for src in known_sources
                if src not in visited and src != current and src != group_src
            ]

            for next_src in candidate_targets:
                ranked = _rank_candidates(current, next_src)
                if ranked is None:
                    continue
                ranked_candidates, edge_effective_conf, ranked_notes, hop = ranked
                top_conf = float(ranked_candidates[0].get("confidence", 0.0) or 0.0)
                edge_notes = list(notes) + list(ranked_notes)
                next_raw_conf = raw_conf * max(top_conf, 1e-6)
                next_effective_conf = effective_conf * max(edge_effective_conf, 1e-6)
                next_hops = hops + [hop]

                if next_src == group_src:
                    path_notes = list(edge_notes)
                    if len(next_hops) > 1:
                        path_notes.append(
                            "multi-hop path via "
                            + ", ".join(h.right_source for h in next_hops[:-1])
                        )
                    candidate_paths.append((
                        round(next_effective_conf, 6),
                        round(next_raw_conf, 6),
                        next_hops,
                        list(dict.fromkeys(path_notes)),
                    ))
                else:
                    _dfs(
                        next_src,
                        visited | {next_src},
                        next_hops,
                        next_raw_conf,
                        next_effective_conf,
                        edge_notes,
                    )

        _dfs(metric_src, {metric_src}, [], 1.0, 1.0, [])

        if not candidate_paths:
            msg = f"No join path from '{metric_src}' to '{group_src}'"
            return [], 0.0, [msg], msg

        candidate_paths.sort(key=lambda item: (item[0], item[1], -len(item[2])), reverse=True)
        best_effective_conf, _best_raw_conf, best_hops, best_notes = candidate_paths[0]
        notes = list(best_notes)

        if len(candidate_paths) > 1 and abs(candidate_paths[0][0] - candidate_paths[1][0]) <= 0.02:
            notes.append(f"ambiguous multi-hop path candidates from {metric_src} to {group_src}")

        min_safe_conf = _path_min_safe_conf(best_hops)
        if best_effective_conf < min_safe_conf:
            msg = (
                f"No safe join path from '{metric_src}' to '{group_src}' "
                f"(best confidence={best_effective_conf:.3f})"
            )
            notes.append(msg)
            return best_hops, round(best_effective_conf, 3), list(dict.fromkeys(notes)), msg

        return best_hops, round(best_effective_conf, 3), list(dict.fromkeys(notes)), None

    # ── Full plan ──────────────────────────────────────────────────────────────

    def plan(
        self,
        metric_hint: str,
        dim_hint:    str | None = None,
        agg:         str = "sum",
        preferred_source: str | None = None,
    ) -> QueryPlan:
        """
        Build a complete QueryPlan from natural-language hints only.

        Steps:
          1. Resolve metric → (metric_src, metric_col, metric_conf, metric_role)
          2. Resolve dimension → (group_src, group_col, group_conf)
          3. If group_src ≠ metric_src → find join keys via Mojo join_detect
        """
        cache_key = self._plan_cache_key(metric_hint, dim_hint, agg, preferred_source)
        cached_plan = self._plan_cache.get(cache_key)
        if cached_plan:
            logger.debug(
                "auto_planner_plan_cache_hit",
                metric=metric_hint,
                dim=dim_hint,
                agg=agg,
                preferred_source=preferred_source,
            )
            return self._clone_plan(cached_plan)

        all_steps:  list[str] = []
        mojo_ops:   list[str] = []

        # ── 1. Metric ─────────────────────────────────────────────────────────
        metric_src, metric_col, metric_conf, metric_role, m_steps = self.resolve_metric(
            metric_hint, preferred_source, agg
        )
        all_steps.extend(m_steps)
        if "column_match" in self.mojo_engines:
            mojo_ops.append("column_match")
        if "field_map" in self.mojo_engines:
            mojo_ops.append("field_map")

        if not metric_src:
            return QueryPlan(
                metric_src="", metric_col="", metric_conf=0.0, metric_role="",
                agg=agg, error=f"No metric column found for hint='{metric_hint}'",
                steps=all_steps, mojo_ops=mojo_ops,
            )

        # ── 2. Dimension ──────────────────────────────────────────────────────
        group_src, group_col, group_conf = "", None, 0.0

        if dim_hint:
            d_src, d_col, d_conf, d_steps = self.resolve_dimension(
                dim_hint, preferred_source or metric_src
            )
            all_steps.extend(d_steps)
            if d_src and d_col:
                group_src  = d_src
                group_col  = d_col
                group_conf = d_conf

                hint_tokens = _semantic_token_set(dim_hint)
                hinted_sources = {
                    src for src in self.graph
                    if hint_tokens & _source_token_set(src)
                }
                if not hinted_sources and group_src != metric_src:
                    fb_src, fb_col, fb_score, fb_steps = (
                        self._same_source_dimension_candidate(metric_src, dim_hint)
                    )
                    current_tokens = _semantic_token_set(group_col or "")
                    fallback_tokens = _semantic_token_set(fb_col or "")
                    same_named_dimension = bool(
                        fallback_tokens and fallback_tokens == current_tokens
                    )
                    if fb_src and fb_col and (
                        same_named_dimension
                        or fb_score >= 0.95
                        or fb_score + 0.02 >= group_conf
                    ):
                        group_src = fb_src
                        group_col = fb_col
                        group_conf = fb_score
                        all_steps.extend(fb_steps)

        if "column_profile" in self.mojo_engines:
            mojo_ops.append("column_profile")
        if "relation_detect" in self.mojo_engines:
            mojo_ops.append("relation_detect")

        def _build_join_state(
            current_metric_src: str,
            current_group_src: str,
            current_group_col: str | None,
        ) -> dict[str, Any]:
            join_key_metric: str | None = None
            join_key_group: str | None = None
            join_conf = 0.0
            join_cardinality = ""
            join_hops: list[JoinHop] = []
            path_confidence = 0.0
            intermediate_sources: list[str] = []
            validation_notes: list[str] = []
            join_steps: list[str] = []
            plan_error: str | None = None

            if dim_hint and not current_group_col:
                plan_error = f"No supported dimension found for hint '{dim_hint}'"
                validation_notes.append(plan_error)
                return {
                    "join_key_metric": join_key_metric,
                    "join_key_group": join_key_group,
                    "join_conf": join_conf,
                    "join_cardinality": join_cardinality,
                    "join_hops": join_hops,
                    "path_confidence": path_confidence,
                    "intermediate_sources": intermediate_sources,
                    "validation_notes": validation_notes,
                    "join_steps": join_steps,
                    "plan_error": plan_error,
                }

            if current_group_col and current_group_src and current_group_src != current_metric_src:
                join_steps.append(
                    "[join_detect] "
                    f"dimension in {current_group_src} ≠ metric in {current_metric_src} "
                    f"→ discovering join path"
                )
                if "join_detect" in self.mojo_engines:
                    mojo_ops.append("join_detect")

                join_hops, path_confidence, validation_notes, join_err = self._search_join_path(
                    current_metric_src,
                    current_group_src,
                    current_group_col,
                )
                intermediate_sources = [hop.right_source for hop in join_hops[:-1]]
                if join_hops:
                    join_key_metric = join_hops[0].left_key
                    join_key_group = join_hops[-1].right_key
                    join_conf = path_confidence
                    join_cardinality = join_hops[-1].cardinality or join_hops[0].cardinality
                    for idx, hop in enumerate(join_hops, start=1):
                        join_steps.append(
                            f"[join_path] hop {idx}: {hop.left_source}.{hop.left_key}"
                            f" ↔ {hop.right_source}.{hop.right_key}"
                            f"  conf={hop.confidence:.3f}  card={hop.cardinality or '?'}"
                        )
                    join_steps.append(
                        "[join_path] "
                        f"SELECTED {len(join_hops)} hop path  conf={path_confidence:.3f}"
                    )
                    if join_err:
                        plan_error = join_err
                else:
                    join_steps.append(
                        "[join_path] "
                        f"no path found between {current_metric_src} and {current_group_src}"
                    )
                    plan_error = (
                        f"No join path from '{current_metric_src}' to '{current_group_src}' "
                        f"for dimension '{current_group_col}'"
                    )
                    validation_notes = list(dict.fromkeys(validation_notes + [plan_error]))
            elif current_group_col and current_group_src == current_metric_src:
                path_confidence = 1.0

            return {
                "join_key_metric": join_key_metric,
                "join_key_group": join_key_group,
                "join_conf": join_conf,
                "join_cardinality": join_cardinality,
                "join_hops": join_hops,
                "path_confidence": path_confidence,
                "intermediate_sources": intermediate_sources,
                "validation_notes": list(dict.fromkeys(validation_notes)),
                "join_steps": join_steps,
                "plan_error": plan_error,
            }

        def _llm_review_decision(join_state: dict[str, Any]) -> tuple[bool, str]:
            if self._llm_policy == "never":
                return False, "policy=never"
            if self._llm_policy == "always":
                return True, "policy=always"
            if self._llm_policy != "auto":
                return False, f"policy={self._llm_policy}"
            if not dim_hint or not group_col or not group_src:
                return False, "no_dimension"

            notes = join_state["validation_notes"]
            if group_src == metric_src and metric_conf >= 1.0 and group_conf >= 0.9 and not notes:
                return False, "confident_same_source"
            if any("ambiguous" in note for note in notes):
                return True, "ambiguous_plan"
            if group_conf < 0.75:
                return True, "low_dimension_confidence"
            if group_src != metric_src:
                if not join_state["join_hops"]:
                    return True, "missing_join_path"
                if join_state["join_cardinality"] == "many_to_many":
                    return True, "many_to_many_join"
                if join_state["path_confidence"] < max(self._join_min_conf, 0.65):
                    return True, "low_join_confidence"
            return False, "confident_plan"

        join_state = _build_join_state(metric_src, group_src, group_col)
        all_steps.extend(join_state["join_steps"])

        should_review, review_reason = _llm_review_decision(join_state)
        if should_review:
            review = self._llm_confirm_plan(
                metric_hint=metric_hint,
                dim_hint=dim_hint,
                agg=agg,
                preferred_source=preferred_source,
                metric_src=metric_src,
                metric_col=metric_col,
                metric_conf=metric_conf,
                metric_role=metric_role,
                group_src=group_src,
                group_col=group_col,
                group_conf=group_conf,
                join_state=join_state,
                query_hints=self._query_hints_by_src,
            )
            if review:
                reasoning = str(review.get("reasoning", "") or review_reason)
                all_steps.append(f"[llm] {reasoning}")
                metric_src = str(review.get("metric_src", metric_src) or metric_src)
                metric_col = str(review.get("metric_col", metric_col) or metric_col)
                group_src = str(review.get("group_src", group_src) or group_src)
                group_override = review.get("group_col", group_col)
                group_col = str(group_override) if group_override is not None else None
                if group_col:
                    group_conf = max(group_conf, 1.0)
                metric_node = self.graph.get(metric_src, {}).get(metric_col)
                if metric_node is not None:
                    metric_role = metric_node.role
                join_state = _build_join_state(metric_src, group_src, group_col)
                all_steps.extend(join_state["join_steps"])
            else:
                all_steps.append(f"[llm/skipped] {review_reason}")
        else:
            all_steps.append(f"[llm/skipped] {review_reason}")

        validation_notes = join_state["validation_notes"]
        for note in validation_notes:
            all_steps.append(f"[validation] {note}")

        plan = QueryPlan(
            metric_src=metric_src,
            metric_col=metric_col,
            metric_conf=metric_conf,
            metric_role=metric_role,
            agg=agg,
            group_col=group_col,
            group_src=group_src if group_col else None,
            group_conf=group_conf,
            join_key_metric=join_state["join_key_metric"],
            join_key_group=join_state["join_key_group"],
            join_conf=join_state["join_conf"],
            join_cardinality=join_state["join_cardinality"],
            join_hops=join_state["join_hops"],
            path_confidence=join_state["path_confidence"],
            intermediate_sources=join_state["intermediate_sources"],
            validation_notes=validation_notes,
            error=join_state["plan_error"],
            mojo_ops=list(dict.fromkeys(mojo_ops)),   # deduplicate preserving order
            steps=all_steps,
        )
        self._plan_cache[cache_key] = self._clone_plan(plan)
        return plan

    # ── Execute ────────────────────────────────────────────────────────────────

    def execute_plan(
        self,
        qplan:       QueryPlan,
        limit:       int | None = None,
        order:       str = "desc",
        time_filter: str | None = None,
    ) -> tuple[Any, int, list[str]]:
        """
        Execute a QueryPlan.

        Returns (result, row_count, plan_trace).
        result is either a list[{"group", "value"}] or a scalar float.
        """
        from apps.api_server.routers.query import (
            JoinEdgeSpec,
            execute,
            execute_cross_source,
            execute_join_path,
            find_time_column,
            time_range,
        )

        if qplan.error:
            return None, 0, [f"ERROR: {qplan.error}"]

        # Lazy-load records from Parquet cache if not already in memory
        self._ensure_records(qplan.metric_src)
        if qplan.group_src and qplan.group_src != qplan.metric_src:
            self._ensure_records(qplan.group_src)
        for intermediate_source in qplan.intermediate_sources:
            self._ensure_records(intermediate_source)

        metric_records = self.tables.get(qplan.metric_src, [])

        if qplan.group_col and qplan.group_src and qplan.join_hops:
            ordered_edges = [
                JoinEdgeSpec(
                    left_source=hop.left_source,
                    right_source=hop.right_source,
                    left_key=hop.left_key,
                    right_key=hop.right_key,
                    join_type=hop.join_type,
                    min_confidence=max(hop.confidence, 0.0),
                    expected_cardinality=hop.cardinality or None,
                    allow_many_to_many=hop.cardinality == "many_to_many",
                )
                for hop in qplan.join_hops
            ]
            records_by_source = {qplan.metric_src: metric_records}
            for hop in qplan.join_hops:
                if hop.right_source not in records_by_source:
                    records_by_source[hop.right_source] = self.tables.get(hop.right_source, [])
            result, row_count, trace = execute_join_path(
                records_by_source=records_by_source,
                base_source=qplan.metric_src,
                metric_col=qplan.metric_col,
                group_source=qplan.group_src,
                group_col=qplan.group_col,
                ordered_edges=ordered_edges,
                agg=qplan.agg,
                limit=limit,
                order=order,
                reject_on_ambiguity=True,
            )
        elif qplan.group_col and qplan.group_src and qplan.group_src != qplan.metric_src:
            # Cross-source join
            group_records = self.tables.get(qplan.group_src, [])
            result, row_count, trace = execute_cross_source(
                metric_records=metric_records,
                metric_col=qplan.metric_col,
                group_records=group_records,
                group_col=qplan.group_col,
                join_metric_col=qplan.join_key_metric or qplan.metric_col,
                join_group_col=qplan.join_key_group or qplan.group_col,
                agg=qplan.agg,
                limit=limit,
                order=order,
                join_cardinality=qplan.join_cardinality,
            )
        else:
            # Single-source
            date_col = find_time_column(qplan.metric_src, self.graph) if time_filter else None
            tr       = time_range(time_filter) if time_filter else None
            result, row_count, trace = execute(
                records=metric_records,
                metric_col=qplan.metric_col,
                agg=qplan.agg,
                group_col=qplan.group_col,
                date_col=date_col,
                tr=tr,
                limit=limit,
                order=order,
            )

        return result, row_count, trace
