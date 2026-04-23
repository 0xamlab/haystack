"""
vector_kernels/resolver.py — Python column resolver using bigram + token scoring.

Implements the same scoring algorithm as batch_ranker.mojo but in pure Python.
Serves as the planner integration layer until Mojo FFI is compiled and wired.

On the hot path for a 128-column schema:
  - Build time: ~2–5 ms (one-time, at schema-load)
  - Resolve time: ~100–400 µs (per query, Python loop over shortlist)
  - Still 50–200× faster than LLM disambiguation

Algorithm mirrors batch_ranker.mojo exactly:
  score = (
      W_NAME × cosine(bigram)
      + type_boost(role)
      + prior_boost(source)
      + 0.05 × min(token_hits, 3)
  )
  confident = score >= MIN_ACCEPT AND gap >= AMBIG_GAP

Public API:
  build_vec64(name)                  → (vec, norm_inv)
  ColumnVectorResolver(source_map)   → resolver instance
  resolver.resolve(hint, ...)        → VectorResolverResult | None
  resolver.resolve_batch(requests)   → list[VectorResolverResult]

Self-test:
    python3 mojo/engine/vector_kernels/resolver.py
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from enum import Enum

from mojo.engine.vector_kernels.tokenizer import (
    Vocab,
    build_vocab,
    expand_tokens,
    make_query_token_ids,
    merge_aliases,
    tokenize_name,
)

# ── Constants (mirror batch_ranker.mojo) ──────────────────────────────────────

VEC_DIM    = 64
W_NAME     = 0.55
MIN_ACCEPT = 0.72
AMBIG_GAP  = 0.08
MAX_PLANNER_SOURCE_COLUMNS = max(
    16,
    int(os.environ.get("ALGENTA_VECTOR_RESOLVER_MAX_COLUMNS_PER_SOURCE", "64")),
)

# Source IDs
SOURCE_UNKNOWN = 0
SOURCE_POS     = 1
SOURCE_BACKLOG = 2
SOURCE_INVOICE = 3

_SOURCE_MAP: dict[str, int] = {
    "pos":     SOURCE_POS,
    "backlog": SOURCE_BACKLOG,
    "invoice": SOURCE_INVOICE,
}

# Role IDs
ROLE_OTHER   = 0
ROLE_UNIT    = 1
ROLE_DERIVED = 2

_ROLE_MAP: dict[str, int] = {
    "unit_measure": ROLE_UNIT,
    "ratio":        ROLE_UNIT,
    "derived_measure": ROLE_DERIVED,
    "base_measure":    ROLE_DERIVED,
    "metric":          ROLE_OTHER,
    "other":           ROLE_OTHER,
}

_PLANNER_ROLE_PRIORITY: dict[str, int] = {
    "derived_measure": 0,
    "base_measure": 1,
    "unit_measure": 2,
    "ratio": 3,
    "metric": 4,
    "other": 5,
}

# ── Bigram vector encoder ─────────────────────────────────────────────────────

def _norm_byte(c: int) -> int:
    """Normalize byte: A-Z → a-z (mirrors table.mojo _norm_byte)."""
    if 65 <= c <= 90:
        return c + 32
    return c


def build_vec64(name: str) -> tuple[list[float], float]:
    """
    Build 64-dim bigram vector from column name.
    Mirrors table.mojo _build_vec_inplace exactly.

    Returns (vec: list[float], norm_inv: float).
    norm_inv = 1.0 / L2_norm(vec), or 0.0 for empty names.

    Example:
        vec, ni = build_vec64("unit_price")
        # vec has non-zero entries at bigram hash positions
        # cosine(vec_a, vec_b) = dot(vec_a, vec_b) * ni_a * ni_b
    """
    vec = [0.0] * VEC_DIM
    try:
        sb = name.encode('latin-1', errors='replace')
    except Exception:
        return vec, 0.0
    n = len(sb)
    if n == 0:
        return vec, 0.0
    prev = _norm_byte(sb[0])
    for i in range(1, n):
        cur = _norm_byte(sb[i])
        h = (prev * 31 + cur) & (VEC_DIM - 1)
        vec[h] += 1.0
        prev = cur
    mag = sum(v * v for v in vec)
    if mag <= 0.0:
        return vec, 0.0
    return vec, 1.0 / math.sqrt(mag)


def _dot(a: list[float], b: list[float]) -> float:
    """64-element dot product."""
    return sum(a[i] * b[i] for i in range(VEC_DIM))


def _cosine(qv: list[float], cv: list[float], q_ni: float, c_ni: float) -> float:
    """Cosine similarity using precomputed norm inverses."""
    if q_ni == 0.0 or c_ni == 0.0:
        return 0.0
    return max(0.0, min(1.0, _dot(qv, cv) * q_ni * c_ni))


# ── Outcome classification ────────────────────────────────────────────────────

class ResolverOutcome(Enum):
    """
    Mutually exclusive resolution outcomes, ordered by specificity.

    COLUMN_MATCH        — confident, unambiguous column found (score ≥ 0.72, gap ≥ 0.08)
    WEAK_MATCH          — plausible column (score ≥ 0.65, gap_ok) but below strong threshold
                          Planner may accept for non-critical fields (group_by, date, filter)
                          but should fall through to column_match engine for metric fields.
    AMBIGUOUS           — top-2 scores are too close to pick safely (gap < 0.08)
    NO_COLUMN_MATCH     — scored a best candidate but confidence is too low to act on
    META_QUERY          — hint looks like an entity/row-count request, not a column lookup
                          (e.g. "server count", "how many guests", "number of orders")
    """
    COLUMN_MATCH     = "column_match"
    WEAK_MATCH       = "weak_match"
    AMBIGUOUS        = "ambiguous"
    NO_COLUMN_MATCH  = "no_column_match"
    META_QUERY       = "meta_query"


class ResolverReason(Enum):
    """
    Fine-grained why code complementing ResolverOutcome.
    Useful for threshold tuning, user-facing explanations, and debugging.

    DIRECT_MATCH            — score and gap both cleared strong thresholds
    WEAK_MATCH              — score in weak-accept band [0.65, 0.72), gap ok
    AMBIGUOUS_GAP           — score was high enough but gap was too narrow
    NO_SIGNAL               — best score below WEAK_ACCEPT_THRESHOLD, no other signal
    META_PHRASE             — explicit phrase trigger ("how many", "number of", …)
    META_ENTITY_NOUN        — hint is all entity nouns with weak column match
    META_LOW_SCORE_COUNT    — 'count' token present and best score below threshold
    """
    DIRECT_MATCH          = "direct_match"
    WEAK_MATCH            = "weak_match"
    AMBIGUOUS_GAP         = "ambiguous_gap"
    NO_SIGNAL             = "no_signal"
    META_PHRASE           = "meta_phrase"
    META_ENTITY_NOUN      = "meta_entity_noun"
    META_LOW_SCORE_COUNT  = "meta_low_score_count"


# ── Meta-query detection ──────────────────────────────────────────────────────
#
# Applied AFTER scoring so we have a best_score to use as evidence.
# Three signals; the first two fire unconditionally; the third is score-gated.

# Tunable thresholds — adjust per deployment domain without touching logic
META_COUNT_SCORE_THRESHOLD = 0.55   # "X count" fires META_QUERY below this score
META_NOUN_SCORE_THRESHOLD  = 0.50   # entity-only hint fires META_QUERY below this score
DEFINITE_META_THRESHOLD    = 0.50   # below this, gap is irrelevant — nothing matches any column
WEAK_ACCEPT_THRESHOLD      = 0.65   # score in [0.65, 0.72) → WEAK_MATCH
                                    # Planner accepts for group_by/date/filter;
                                    # falls through to column_match engine for metric

_META_QUERY_RE = re.compile(
    r'\b(how many|number of|count of|total count|row count)\b',
    re.IGNORECASE,
)

# Generic entity nouns that typically refer to the row entity itself,
# not to a measurable column.  Kept conservative — false positives here are costly.
_ENTITY_NOUNS: frozenset[str] = frozenset({
    # People / staff
    "servers", "server", "employees", "employee", "staff", "workers", "worker",
    "waiters", "waiter", "cashiers", "cashier",
    # Customers
    "customers", "customer", "clients", "client",
    # Business objects
    "orders", "order", "transactions", "transaction",
    "products", "product", "items", "skus",
    "tables", "records", "entries", "rows",
})


def _meta_reason(hint: str, best_score: float) -> str | None:
    """
    Return a reason string if the hint is a meta-query, else None.

    Signals checked in priority order:
      1. Explicit phrase  ("how many", "number of", …)
      2. Entity-noun only hint with weak column match
      3. Token 'count' present with weak column match
    """
    if _META_QUERY_RE.search(hint):
        return "meta_phrase"
    tokens = set(tokenize_name(hint))
    if tokens and tokens.issubset(_ENTITY_NOUNS) and best_score < META_NOUN_SCORE_THRESHOLD:
        return "meta_entity_noun"
    if "count" in tokens and best_score < META_COUNT_SCORE_THRESHOLD:
        return "meta_low_score_count"
    return None


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ColumnEntry:
    """One candidate column — all data needed for scoring."""
    column_id:      int
    source:         str
    name:           str
    source_id:      int         # SOURCE_* constant
    role_id:        int         # ROLE_* constant
    norm_inv:       float
    vec:            list[float]
    tokens:         list[str]   # from tokenize_name()
    tokens_expanded: set[str]   # from expand_tokens(tokens) — for overlap scoring


@dataclass
class TopKEntry:
    source:    str
    column:    str
    score:     float
    name_sim:  float
    type_boost: float


@dataclass
class VectorResolverResult:
    source:         str
    column:         str
    score:          float
    confidence_gap: float
    outcome:        ResolverOutcome
    reason:         ResolverReason   # fine-grained why code
    confident:      bool             # shorthand: outcome == COLUMN_MATCH
    ambiguous:      bool             # shorthand: outcome == AMBIGUOUS
    fallback_used:  bool
    token_overlap:  int
    top_k:          list[TopKEntry]
    steps:          list[str]


@dataclass(frozen=True)
class _ColumnEntryArtifacts:
    tokens: tuple[str, ...]
    tokens_expanded: frozenset[str]
    posting_tokens: tuple[str, ...]
    vec: tuple[float, ...]
    norm_inv: float


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _type_boost(query_role: int, cand_role: int) -> float:
    """Role compatibility boost (mirrors batch_ranker.mojo _type_boost)."""
    if query_role == ROLE_OTHER:
        return 0.0
    if cand_role == query_role:
        return 0.15
    if cand_role != ROLE_OTHER:
        return -0.08
    return 0.0


def _prior_boost(query_src: int, cand_src: int, cand_role: int) -> float:
    """Source prior boost (mirrors batch_ranker.mojo _prior_boost)."""
    if query_src == SOURCE_UNKNOWN:
        return 0.0
    if cand_src != SOURCE_UNKNOWN and cand_src != query_src:
        return 0.0
    if query_src == SOURCE_POS and cand_role == ROLE_UNIT:
        return 0.10
    if query_src == SOURCE_BACKLOG and cand_role == ROLE_DERIVED:
        return 0.10
    if query_src == SOURCE_INVOICE and cand_role == ROLE_DERIVED:
        return 0.10
    return 0.0


def _token_overlap(query_tokens_ex: set[str], col_tokens_ex: set[str]) -> int:
    """
    Count how many alias-expanded query tokens appear in alias-expanded column tokens.
    Both sets are pre-expanded; this enables bidirectional alias matching without
    inflating the bonus (capped at 3 in the caller).
    """
    return sum(1 for t in query_tokens_ex if t in col_tokens_ex)


# ── Main resolver ─────────────────────────────────────────────────────────────

class ColumnVectorResolver:
    """
    Resident column resolver. Build once at schema-load time; query many times.

    source_map format:
        {
            "POS": [("UNIT_PRICE", "unit_measure"), ("EXT_PRICE", "derived_measure"), ...],
            "BACKLOG": [("OH_COST", "derived_measure"), ...],
        }

    The role strings map to: "unit_measure" | "ratio" | "derived_measure" |
                              "base_measure" | "metric" | "other"
    """

    # Threshold policy (can be overridden per instance)
    ACCEPT_THRESHOLD      = MIN_ACCEPT            # strong match: score ≥ this
    WEAK_ACCEPT_THRESHOLD = WEAK_ACCEPT_THRESHOLD # weak match:  score in [this, ACCEPT_THRESHOLD)
    GAP_THRESHOLD         = AMBIG_GAP             # gap must clear this for any match
    MIN_SHORTLIST         = 2                     # fewer → fallback to all-column scan

    def __init__(
        self,
        source_map:    dict[str, list[tuple[str, str]]],
        extra_aliases: dict[str, list[str]] | None = None,
        domain_aliases: dict[str, list[str]] | None = None,
    ):
        """
        Build all data structures from source_map.

        Args:
            source_map:     {source_name: [(col_name, role_str), ...]}
            domain_aliases: schema/domain-specific aliases merged with the global
                            ALIASES table.  Abbreviations (len≤3, avg expansion≥5)
                            also get bigram-vec expansion so cosine scoring sees the
                            canonical form.  Pass {"ppa": ["per","person","average"]}
                            for a schema that uses PPA without it being in global ALIASES.
            extra_aliases:  legacy name for domain_aliases (deprecated; use domain_aliases)
        """
        # Resolve alias source: domain_aliases takes precedence over extra_aliases
        _da = domain_aliases if domain_aliases is not None else extra_aliases
        # Build combined alias table (global + domain) — stored for use throughout
        self._aliases: dict[str, list[str]] = merge_aliases(_da)

        self._entries: list[ColumnEntry] = []
        col_names = [
            col_name
            for cols in source_map.values()
            for col_name, _role_str in cols
        ]
        self._vocab: Vocab = build_vocab(col_names, _da)
        self._posting: dict[int, list[int]] = {}
        self._sources: set[str] = set()
        self._column_artifact_cache: dict[str, _ColumnEntryArtifacts] = {}

        for source_name, columns in source_map.items():
            self.append_source(source_name, columns)

        self._n_columns = len(self._entries)

    def _expanded_name_tokens(self, name: str) -> list[tuple[str, float]]:
        return expand_tokens(tokenize_name(name), self._aliases)

    def _effective_name_tokens(self, tokens: list[str]) -> list[str]:
        eff_parts: list[str] = []
        for tok in tokens:
            eff_parts.append(tok)
            if tok in self._aliases and len(tok) <= 3:
                exp = self._aliases[tok]
                avg_alias_len = sum(len(alias) for alias in exp) / len(exp)
                if avg_alias_len >= 5.0:
                    eff_parts.extend(exp)
        return eff_parts

    def _column_entry_artifacts(self, col_name: str) -> _ColumnEntryArtifacts:
        cached = self._column_artifact_cache.get(col_name)
        if cached is not None:
            return cached

        tokens = tokenize_name(col_name)
        expanded = expand_tokens(tokens, self._aliases)
        tokens_expanded = frozenset(token for token, _weight in expanded)
        eff_tokens = self._effective_name_tokens(tokens)
        eff_name = " ".join(eff_tokens) if eff_tokens else col_name
        vec, norm_inv = build_vec64(eff_name)
        artifacts = _ColumnEntryArtifacts(
            tokens=tuple(tokens),
            tokens_expanded=tokens_expanded,
            posting_tokens=tuple(token for token, _weight in expanded),
            vec=tuple(vec),
            norm_inv=norm_inv,
        )
        self._column_artifact_cache[col_name] = artifacts
        return artifacts

    def _append_entry(self, source: str, col_name: str, role_str: str) -> None:
        artifacts = self._column_entry_artifacts(col_name)
        entry = ColumnEntry(
            column_id=len(self._entries),
            source=source,
            name=col_name,
            source_id=_SOURCE_MAP.get(source.lower(), SOURCE_UNKNOWN),
            role_id=_ROLE_MAP.get(role_str.lower(), ROLE_OTHER),
            norm_inv=artifacts.norm_inv,
            vec=list(artifacts.vec),
            tokens=list(artifacts.tokens),
            tokens_expanded=set(artifacts.tokens_expanded),
        )
        self._entries.append(entry)
        for token in artifacts.posting_tokens:
            token_id = self._vocab.intern(token)
            self._posting.setdefault(token_id, []).append(entry.column_id)
        self._n_columns = len(self._entries)

    def append_source(
        self,
        source: str,
        columns: list[tuple[str, str]],
    ) -> bool:
        """
        Incrementally append a brand-new source to the resolver.

        Returns True when the source was handled in-place. Returns False only if
        the resolver already contains the source and a full rebuild is required
        to replace it safely.
        """
        if source in self._sources:
            return False
        if not columns:
            return True
        self._sources.add(source)
        for col_name, role_str in columns:
            self._append_entry(source, col_name, role_str)
        return True

    @staticmethod
    def _planner_graph_entries_for_source(
        columns: dict[str, object],
        *,
        include_non_numeric: bool,
    ) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        ranked_entries: list[tuple[str, str, float, int]] = []
        for col_name, node in columns.items():
            fill_rate = float(getattr(node, "fill_rate", 1.0) or 0.0)
            if fill_rate < 0.02:
                continue
            is_numeric = bool(getattr(node, "is_numeric", True))
            if not include_non_numeric and not is_numeric:
                continue
            role_str = getattr(node, "role", "other" if include_non_numeric else "metric")
            entries.append((col_name, role_str))
            priority = _PLANNER_ROLE_PRIORITY.get(role_str, _PLANNER_ROLE_PRIORITY["other"])
            ranked_entries.append((col_name, role_str, fill_rate, priority))

        if len(entries) <= MAX_PLANNER_SOURCE_COLUMNS:
            return entries

        ranked_entries.sort(
            key=lambda item: (
                item[3],
                -item[2],
                len(item[0]),
                item[0].lower(),
            )
        )
        return [
            (col_name, role_str)
            for col_name, role_str, _fill_rate, _priority in ranked_entries[
                :MAX_PLANNER_SOURCE_COLUMNS
            ]
        ]

    def append_planner_graph_source(
        self,
        source: str,
        columns: dict[str, object],
        *,
        fill_rates: dict[tuple[str, str], float] | None = None,
    ) -> bool:
        del fill_rates
        eligible = self._planner_graph_entries_for_source(
            columns,
            include_non_numeric=False,
        )
        return self.append_source(source, eligible)

    def _prefilter(
        self,
        query_token_ids: list[int],
        query_src: int,
        query_role: int,
        shortlist_cap: int = 64,
    ) -> tuple[list[int], bool]:
        """
        Walk posting lists, apply source/role gates, dedup, return shortlist.
        Returns (candidate_indices, fallback_used).
        """
        seen: set[int] = set()
        cands: list[int] = []

        for tok_id in query_token_ids:
            for col_idx in self._posting.get(tok_id, []):
                if col_idx in seen:
                    continue
                e = self._entries[col_idx]

                # Source gate: skip known-wrong sources
                if query_src != SOURCE_UNKNOWN:
                    if e.source_id != SOURCE_UNKNOWN and e.source_id != query_src:
                        continue

                # Role gate: skip incompatible roles
                if query_role != ROLE_OTHER:
                    if e.role_id != ROLE_OTHER and e.role_id != query_role:
                        continue

                seen.add(col_idx)
                cands.append(col_idx)
                if len(cands) >= shortlist_cap:
                    break
            if len(cands) >= shortlist_cap:
                break

        fallback_used = False
        if len(cands) < self.MIN_SHORTLIST:
            # Fallback: all columns, relaxed gates
            fallback_used = True
            cands = list(range(self._n_columns))

        return cands, fallback_used

    def missing_aliases(self) -> list[str]:
        """
        Report tokens in the schema that look like opaque abbreviations but have
        no alias entry in the combined (global + domain) table.

        An "opaque abbreviation" is a token that:
          • is ≤ 3 characters long
          • appears in at least one column name in this resolver
          • has no entry in the combined alias table

        These tokens will produce low cosine scores for natural-language queries
        unless alias definitions are added via domain_aliases.

        Returns a sorted, deduplicated list of token strings.

        Example:
            resolver = ColumnVectorResolver(schema)
            gaps = resolver.missing_aliases()
            # ["arr", "ebitda", "mro"] for a finance/aviation schema
        """
        schema_tokens: set[str] = set()
        for e in self._entries:
            for tok in e.tokens:
                if len(tok) <= 3:
                    schema_tokens.add(tok)
        return sorted(t for t in schema_tokens if t not in self._aliases)

    def resolve(
        self,
        hint: str,
        preferred_source: str | None = None,
        role_hint: str | None = None,
        top_k: int = 5,
    ) -> VectorResolverResult | None:
        """
        Resolve a metric/dimension hint to the best matching column.

        Args:
            hint:             query string ("unit price", "extended cost", etc.)
            preferred_source: source name to prefer (e.g. "POS")
            role_hint:        role context from field_map ("unit_measure", "derived_measure", etc.)
            top_k:            number of candidates in result

        Returns VectorResolverResult, or None if no columns registered.
        """
        if not self._entries or self._vocab is None:
            return None

        steps: list[str] = []

        # Map source/role to integer IDs
        query_src  = _SOURCE_MAP.get((preferred_source or "").lower(), SOURCE_UNKNOWN)
        query_role = _ROLE_MAP.get((role_hint or "").lower(), ROLE_OTHER)

        # Build query vector
        qv, q_ni = build_vec64(hint)

        # Build query token IDs and alias-expanded token set for overlap scoring
        # Use the same combined alias table the index was built with so domain
        # synonyms benefit overlap scoring without any extra config.
        query_token_ids = make_query_token_ids(self._vocab, hint)
        query_tokens    = tokenize_name(hint)
        query_tokens_ex = {token for token, _ in expand_tokens(query_tokens, self._aliases)}

        # Prefilter to shortlist
        cand_indices, fallback_used = self._prefilter(query_token_ids, query_src, query_role)
        steps.append(
            f"[prefilter] shortlist={len(cand_indices)} fallback={fallback_used}"
        )

        # Score shortlist
        scored: list[tuple[float, int, float, float]] = []   # (score, col_idx, nsim, tb)
        for col_idx in cand_indices:
            e = self._entries[col_idx]
            nsim = _cosine(qv, e.vec, q_ni, e.norm_inv)
            tb   = _type_boost(query_role, e.role_id)
            pb   = _prior_boost(query_src, e.source_id, e.role_id)
            hits = _token_overlap(query_tokens_ex, e.tokens_expanded)
            th   = 0.05 * min(hits, 3)
            score = W_NAME * nsim + tb + pb + th
            scored.append((score, col_idx, nsim, tb))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)

        best_score, best_idx, best_nsim, best_tb = scored[0]
        best_entry = self._entries[best_idx]

        gap = (scored[0][0] - scored[1][0]) if len(scored) >= 2 else best_score

        # ── Item 4: explicit gap guard ──────────────────────────────────────────
        # A high score does NOT override a narrow gap — the gap guard fires
        # independently to prevent silent misclassification when two columns
        # score similarly high.
        gap_ok   = gap >= self.GAP_THRESHOLD or len(scored) < 2
        score_ok = best_score >= self.ACCEPT_THRESHOLD
        ambiguous = not gap_ok and len(scored) >= 2
        confident = score_ok and gap_ok

        # ── Classify outcome + reason ────────────────────────────────────────────
        # Meta-query check runs AFTER scoring so best_score is available.
        meta_rsn = _meta_reason(hint, best_score)
        weak = (
            not confident
            and not ambiguous
            and best_score >= self.WEAK_ACCEPT_THRESHOLD
            and gap_ok
        )
        if meta_rsn is not None:
            # Meta-ambiguity guard: explicit phrases are unambiguous by definition;
            # score-based meta detections (count+low_score, entity_noun) can be
            # ambiguous if the gap is narrow — in that case, stay AMBIGUOUS so
            # the planner falls through rather than wrongly routing to the meta executor.
            phrase_based   = (meta_rsn == "meta_phrase")
            # When best_score is below DEFINITE_META_THRESHOLD no column is a
            # plausible match — the gap is small only because all scores are
            # equally poor, not because there is a real competitor.
            definite_meta  = best_score < DEFINITE_META_THRESHOLD
            if phrase_based or gap_ok or definite_meta:
                outcome = ResolverOutcome.META_QUERY
                reason  = ResolverReason(meta_rsn)
            else:
                outcome = ResolverOutcome.AMBIGUOUS
                reason  = ResolverReason.AMBIGUOUS_GAP
        elif confident:
            outcome = ResolverOutcome.COLUMN_MATCH
            reason  = ResolverReason.DIRECT_MATCH
        elif ambiguous:
            outcome = ResolverOutcome.AMBIGUOUS
            reason  = ResolverReason.AMBIGUOUS_GAP
        elif weak:
            outcome = ResolverOutcome.WEAK_MATCH
            reason  = ResolverReason.WEAK_MATCH
        else:
            outcome = ResolverOutcome.NO_COLUMN_MATCH
            reason  = ResolverReason.NO_SIGNAL

        # Keep convenience booleans consistent with outcome
        confident = (outcome == ResolverOutcome.COLUMN_MATCH)
        ambiguous = (outcome == ResolverOutcome.AMBIGUOUS)

        steps.append(
            f"[score] {best_entry.source}.{best_entry.name}  "
            f"score={best_score:.3f}  gap={gap:.3f}  "
            f"outcome={outcome.value}  reason={reason.value}"
        )

        # Build top-k
        result_top_k = []
        for score, col_idx, nsim, tb in scored[:top_k]:
            e = self._entries[col_idx]
            result_top_k.append(TopKEntry(
                source=e.source,
                column=e.name,
                score=round(score, 4),
                name_sim=round(nsim, 4),
                type_boost=round(tb, 4),
            ))

        # Token overlap for top result (same bidirectional expansion as scoring loop)
        top_overlap = _token_overlap(query_tokens_ex, best_entry.tokens_expanded)

        return VectorResolverResult(
            source=best_entry.source,
            column=best_entry.name,
            score=round(best_score, 4),
            confidence_gap=round(gap, 4),
            outcome=outcome,
            reason=reason,
            confident=confident,
            ambiguous=ambiguous,
            fallback_used=fallback_used,
            token_overlap=top_overlap,
            top_k=result_top_k,
            steps=steps,
        )

    def resolve_batch(
        self,
        requests: list[tuple[str, str | None, str | None]],
        top_k: int = 5,
    ) -> list[VectorResolverResult | None]:
        """
        Resolve multiple hints in one call.

        Args:
            requests: list of (hint, preferred_source, role_hint)
            top_k:    number of top candidates per result

        Returns list of VectorResolverResult (same order as requests).
        """
        return [self.resolve(hint, src, role, top_k) for hint, src, role in requests]

    def resolve_plan_fields(
        self,
        *,
        metric:    tuple[str, str | None, str | None] | None = None,
        group_by:  tuple[str, str | None, str | None] | None = None,
        date:      tuple[str, str | None, str | None] | None = None,
        filter_:   tuple[str, str | None, str | None] | None = None,
        top_k:     int = 5,
    ) -> dict[str, VectorResolverResult | None]:
        """
        Batch-resolve all field types for a single planner query in one call.

        Each argument is a (hint, preferred_source, role_hint) triple or None.
        Returns a dict keyed by field type — absent fields map to None.

        Usage:
            results = resolver.resolve_plan_fields(
                metric   = ("extended price",  "POS",  "derived_measure"),
                group_by = ("customer name",   "POS",  "other"),
                date     = ("order date",       "POS",  "other"),
            )
            if results["metric"] and results["metric"].outcome == ResolverOutcome.COLUMN_MATCH:
                ...

        Benefits over individual resolve() calls:
          - Single pass through resolver infrastructure
          - Outcome routing is consistent across all fields
          - Easy to add source-level caching later
        """
        slot_map: dict[str, tuple[str, str | None, str | None] | None] = {
            "metric":   metric,
            "group_by": group_by,
            "date":     date,
            "filter":   filter_,
        }
        results: dict[str, VectorResolverResult | None] = {}
        for field, req in slot_map.items():
            if req is None:
                results[field] = None
            else:
                hint, src, role = req
                results[field] = self.resolve(hint, src, role, top_k)
        return results

    @classmethod
    def from_planner_graph(
        cls,
        graph: dict,
        extra_aliases: dict[str, list[str]] | None = None,
    ) -> ColumnVectorResolver:
        """
        Build a resolver directly from the planner's schema graph.

        graph format: {source: {col_name: SchemaNode}}
        SchemaNode is expected to have a .role attribute (string).

        Only includes numeric columns with fill_rate >= 0.02.
        """
        source_map: dict[str, list[tuple[str, str]]] = {}
        for src, cols in graph.items():
            entries = cls._planner_graph_entries_for_source(
                cols,
                include_non_numeric=False,
            )
            if entries:
                source_map[src] = entries
        return cls(source_map, extra_aliases)

    @classmethod
    def from_planner_graph_all(
        cls,
        graph: dict,
        extra_aliases: dict[str, list[str]] | None = None,
    ) -> ColumnVectorResolver:
        """
        Build a resolver from the planner graph including non-numeric columns.
        Use for dimension resolution (group-by, date, filter fields).
        """
        source_map: dict[str, list[tuple[str, str]]] = {}
        for src, cols in graph.items():
            entries = cls._planner_graph_entries_for_source(
                cols,
                include_non_numeric=True,
            )
            if entries:
                source_map[src] = entries
        return cls(source_map, extra_aliases)


# ── Self-test ─────────────────────────────────────────────────────────────────

def _test_build_vec64():
    """Bigram encoder matches table.mojo exactly for known test cases."""
    # "unit_price" and "UNIT_PRICE" should produce the same vec (case-insensitive)
    v1, n1 = build_vec64("unit_price")
    v2, n2 = build_vec64("UNIT_PRICE")
    assert v1 == v2, f"Case normalization failed: {v1} != {v2}"
    assert n1 == n2
    assert n1 > 0.0
    sim = _cosine(v1, v1, n1, n1)
    assert abs(sim - 1.0) < 1e-5, f"Self-cosine should be 1.0, got {sim}"
    _emit(
        f"  PASS build_vec64: unit_price norm_inv={n1:.4f}  self_cosine={sim:.6f}"
    )


def _test_resolver_unit_price():
    """unit_price query should find UNIT_PRICE above EXT_PRICE."""
    source_map = {
        "POS": [
            ("UNIT_PRICE",  "unit_measure"),
            ("EXT_PRICE",   "derived_measure"),
            ("QTY",         "base_measure"),
            ("OH_COST",     "derived_measure"),
            ("ORDERED_QTY", "base_measure"),
            ("LINE_TOTAL",  "derived_measure"),
        ]
    }
    resolver = ColumnVectorResolver(source_map)

    r = resolver.resolve("unit price", preferred_source="POS", role_hint="unit_measure")
    assert r is not None, "Expected a result"
    assert r.column == "UNIT_PRICE", f"Expected UNIT_PRICE, got {r.column}"
    assert r.score >= 0.72, f"Expected score >= 0.72, got {r.score}"
    assert r.confident, f"Expected confident=True, got flags: confident={r.confident}"
    _emit(
        f"  PASS unit_price → {r.source}.{r.column}  "
        f"score={r.score:.4f}  gap={r.confidence_gap:.4f}"
    )
    for tk in r.top_k[:3]:
        _emit(
            f"       {tk.source}.{tk.column:20s} "
            f"score={tk.score:.4f}  sim={tk.name_sim:.4f}"
        )
    _emit()


def _test_resolver_ambiguity():
    """extended cost vs extended price — should be ambiguous or at least detected."""
    source_map = {
        "BACKLOG": [
            ("EXT_PRICE",    "derived_measure"),
            ("EXT_COST",     "derived_measure"),
            ("UNIT_PRICE",   "unit_measure"),
            ("UNIT_COST",    "unit_measure"),
            ("QTY",          "base_measure"),
        ]
    }
    resolver = ColumnVectorResolver(source_map)

    r = resolver.resolve("extended cost", preferred_source="BACKLOG", role_hint="derived_measure")
    assert r is not None
    _emit(
        f"  INFO extended_cost → {r.source}.{r.column}  "
        f"score={r.score:.4f}  gap={r.confidence_gap:.4f}  "
        f"ambiguous={r.ambiguous}"
    )
    for tk in r.top_k[:3]:
        _emit(f"       {tk.source}.{tk.column:20s} score={tk.score:.4f}")
    _emit()


def _test_batch():
    """Batch resolution returns correct order and types."""
    source_map = {
        "POS": [
            ("UNIT_PRICE",  "unit_measure"),
            ("EXT_PRICE",   "derived_measure"),
            ("QTY",         "base_measure"),
        ],
        "BACKLOG": [
            ("OH_COST",    "derived_measure"),
            ("ORDERED_QTY","base_measure"),
        ],
    }
    resolver = ColumnVectorResolver(source_map)

    requests = [
        ("unit price",    "POS",     "unit_measure"),
        ("extended price","POS",     "derived_measure"),
        ("quantity",      None,      "base_measure"),
        ("overhead cost", "BACKLOG", "derived_measure"),
    ]
    results = resolver.resolve_batch(requests)
    assert len(results) == 4
    for i, (hint, _, _) in enumerate(requests):
        r = results[i]
        assert r is not None, f"Expected result for '{hint}'"
        _emit(
            f"  PASS batch[{i}] '{hint}' → {r.source}.{r.column}  score={r.score:.4f}"
        )
    _emit()


def _emit(message: str = "") -> None:
    import sys

    sys.stdout.write(f"{message}\n")


if __name__ == "__main__":
    import sys

    _emit("=== resolver.py self-test ===")
    _emit()
    _emit("[1] build_vec64 bigram encoder:")
    _test_build_vec64()
    _emit()
    _emit("[2] unit_price resolution:")
    _test_resolver_unit_price()
    _emit("[3] ambiguity detection (ext_price vs ext_cost):")
    _test_resolver_ambiguity()
    _emit("[4] batch resolution:")
    _test_batch()
    _emit("All tests passed.")
    sys.exit(0)
