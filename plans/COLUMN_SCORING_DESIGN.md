# Column Scoring Design

## Problem

Given a natural-language hint (e.g. "unit cost") and a schema with multiple
numeric columns (UNIT_COST, OH_COST, EXT_COST), the engine must deterministically
pick the correct column without hardcoded industry maps. It must work for any
industry and any dataset.

## Scoring pipeline

Column resolution goes through three ordered steps. Each step can short-circuit
if confidence is high enough.

```
hint + graph
  │
  ├─ Step 0: Query-hints registry (Parquet metadata) ──────────► fast path
  │          if source was pre-registered, structured hints
  │          drive selection directly.  Confidence > 0.80 exits.
  │
  ├─ Step 1: field_map (Mojo) ─────────────────────────────────► semantic type
  │          Maps hint words to (semantic_type, polarity, distribution).
  │          Python fallback when Mojo unavailable.
  │
  ├─ Step 2: column_match (Mojo) ──────────────────────────────► cross-source rank
  │          Score every numeric column against the hint using Mojo
  │          statistical + name similarity.  Augmented with name_sim bonus
  │          (high token overlap → trust name over magnitude).
  │
  └─ Step 3: resolve_metric_column (Python graph) ─────────────► always runs
             Role-targeted scoring with typed intent, source priors, and
             cross-role gap emission.
```

## Score components (Step 3, per candidate)

| Component       | Weight | Description |
|-----------------|--------|-------------|
| `role`          | 0.58–0.70 | Base score for structural role match + node confidence |
| `magnitude`     | 0.0–0.16 | Prefer larger columns for DERIVED_MEASURE; smaller for unit |
| `name_overlap`  | 0.24–0.28 | Token Jaccard between hint and column name tokens |
| `typed_intent`  | 0.0–0.18 | Concept-level match (cost↔cost, unit↔unit, total↔total) |
| `typed_penalty` | –0.08––0.16 | Contradictory concept pairs (unit vs total, missing overhead) |
| `source_prior`  | 0.0–0.10 | Context priors: POS→unit, Backlog→extended, etc. |
| `fill_rate`     | 0.0–0.04 | Penalise sparse columns |
| `id_penalty`    | –0.40 | Penalise identifier-like columns |

## Typed intent concepts

```python
_METRIC_CONCEPTS = {
    "unit":     {"average", "each", "per", "rate", "unit"},
    "total":    {"amount", "extended", "gross", "revenue", "sales", "sum", "total", "value"},
    "overhead": {"burden", "indirect", "oh", "overhead"},
    "cost":     {"cogs", "cost", "expense", "spend"},
    "price":    {"price", "pricing"},
    "count":    {"count", "quantity", "units", "volume"},
}
```

The penalty rules enforce hard separations:
- `unit` hint + `total` column → –0.16
- `total` hint + `unit` column → –0.14
- `overhead` hint, missing overhead token in column → –0.08

## Cross-role gap emission

When only one role-targeted candidate exists (e.g. a single UNIT_MEASURE
column in the source), the scorer runs a secondary pass over all other
numeric columns using the same `_metric_candidate_score` function.  The
gap between the winner and the best cross-role column is emitted as a
step trace:

```
[resolve_metric_column/gap] top=UNIT_COST second=OH_COST gap=0.234
```

This surfaces disambiguation signal to callers even when the primary
candidate is unambiguous within its role class.

## Mojo lexical scorer (`mojo/engine/text/column_scorer.mojo`)

A pure-Mojo module exposing:

| Function              | Algorithm | Range |
|-----------------------|-----------|-------|
| `score_token_overlap` | Jaccard on `_`/space tokens | [0, 1] |
| `score_ngram_overlap` | Dice coefficient on char bigrams | [0, 1] |
| `score_prefix_match`  | Shared prefix / len(hint) | [0, 1] |
| `score_column_hint`   | Weighted composite (50/30/20) | [0, 1] |

The Python bridge calls `score_column_hint` to produce the `name_sim`
component used in Step 2.  No synonym tables are hardcoded in Mojo;
synonym expansion lives in `_METRIC_TOKEN_CANON` (Python) so it can be
extended without recompiling.

## Source priors

```python
_SOURCE_PRIOR_TOKENS = {
    "unit":  { "source": {"pos", "price", "pricing", "quote", "quotes"},
               "column": {"price", "unit", "cost", "rate"} },
    "total": { "source": {"backlog", "booking", "bookings", "order", "orders", "sales"},
               "column": {"extended", "amount", "total", "value", "revenue", "sales"} },
}
```

Bonus capped at 0.10 total.  Source match = +0.04; column name match = +0.03.

## Explainability

Every candidate emits a `score_components` dict and a `notes` list
(surfaced in `CandidateColumn`).  The planner trace contains `[…/gap]`
steps so LLMs can explain ranking decisions to end-users.

Example response snippet:
```json
{
  "candidates": [{
    "column": "UNIT_COST",
    "confidence": 1.14,
    "score_components": {
      "role": 0.58, "magnitude": 0.03, "name_overlap": 0.24,
      "typed_intent": 0.18, "typed_penalty": 0.0,
      "source_prior": 0.07, "fill_rate": 0.04, "id_penalty": 0.0
    },
    "notes": ["typed-intent-match", "source-prior:unit"]
  }],
  "plan": [
    "[resolve_metric_column/gap] top=UNIT_COST second=OH_COST gap=0.234"
  ]
}
```
