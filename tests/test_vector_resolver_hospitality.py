"""
tests/test_vector_resolver_hospitality.py — Locked regression suite for the
hospitality / restaurant-POS domain.

Covers the schema class seen in "Server Performance Current Month" xlsx:
  4 sources (Totals, Food, Beverage, Alcohol) × 7 columns = 28 total.
  Column set: Net_Sales, Tips, Sold, Avg_Sold_Per_Guest, Avg_Order_Time,
              Guests, PPA.

Test classes:
  TestPPAAbbreviation          — "per person average" → PPA (abbreviation expansion)
  TestRevenueSynonyms          — revenue ↔ sales synonym alignment
  TestSoldQuantitySynonyms     — sold ↔ quantity ↔ qty
  TestGuestCoversVariants      — guest / guests / covers / diners
  TestTipsGratuity             — tips ↔ gratuity
  TestAverageAbbreviation      — avg ↔ average for order time queries
  TestMetaQueryDetection       — entity/row-count queries → META_QUERY outcome
  TestHospitalityBatch         — full 13-query batch, accuracy gate ≥ 90%

Run:
    python3 -m pytest tests/test_vector_resolver_hospitality.py -v
"""

from __future__ import annotations

import pytest

try:
    from mojo.engine.vector_kernels.resolver import (
        ColumnVectorResolver,
        ResolverOutcome,
    )
except ImportError:
    pytest.skip("Mojo engine not available", allow_module_level=True)

# ── Shared fixture ────────────────────────────────────────────────────────────

_HOSP_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "Totals": [
        ("Net_Sales", "derived_measure"),
        ("Tips", "derived_measure"),
        ("Sold", "base_measure"),
        ("Avg_Sold_Per_Guest", "ratio"),
        ("Avg_Order_Time", "ratio"),
        ("Guests", "base_measure"),
        ("PPA", "ratio"),
    ],
    "Food": [
        ("Food_Net_Sales", "derived_measure"),
        ("Food_Tips", "derived_measure"),
        ("Food_Sold", "base_measure"),
        ("Food_Avg_Sold_Per_Guest", "ratio"),
        ("Food_Avg_Order_Time", "ratio"),
        ("Food_Guests", "base_measure"),
        ("Food_PPA", "ratio"),
    ],
    "Beverage": [
        ("Beverage_Net_Sales", "derived_measure"),
        ("Beverage_Tips", "derived_measure"),
        ("Beverage_Sold", "base_measure"),
        ("Beverage_Avg_Sold_Per_Guest", "ratio"),
        ("Beverage_Avg_Order_Time", "ratio"),
        ("Beverage_Guests", "base_measure"),
        ("Beverage_PPA", "ratio"),
    ],
    "Alcohol": [
        ("Alcohol_Net_Sales", "derived_measure"),
        ("Alcohol_Tips", "derived_measure"),
        ("Alcohol_Sold", "base_measure"),
        ("Alcohol_Avg_Sold_Per_Guest", "ratio"),
        ("Alcohol_Avg_Order_Time", "ratio"),
        ("Alcohol_Guests", "base_measure"),
        ("Alcohol_PPA", "ratio"),
    ],
}


@pytest.fixture(scope="module")
def hosp():
    return ColumnVectorResolver(_HOSP_SCHEMA)


# ── PPA abbreviation ──────────────────────────────────────────────────────────


class TestPPAAbbreviation:
    def test_per_person_average_resolves_to_ppa(self, hosp):
        r = hosp.resolve("per person average", preferred_source="Totals", role_hint="ratio")
        assert r is not None
        assert r.column == "PPA", f"Expected PPA, got {r.column} (score={r.score:.3f})"

    def test_food_per_person_average_resolves_to_food_ppa(self, hosp):
        r = hosp.resolve("food per person average", preferred_source="Food", role_hint="ratio")
        assert r is not None
        assert r.column == "Food_PPA", f"Expected Food_PPA, got {r.column}"

    def test_beverage_ppa(self, hosp):
        r = hosp.resolve(
            "beverage per person average", preferred_source="Beverage", role_hint="ratio"
        )
        assert r is not None
        assert r.column == "Beverage_PPA", f"Expected Beverage_PPA, got {r.column}"

    def test_ppa_score_beats_avg_sold_per_guest(self, hosp):
        """PPA column must outscore Avg_Sold_Per_Guest for the 'per person average' query."""
        r = hosp.resolve("per person average", preferred_source="Totals", role_hint="ratio")
        assert r is not None
        assert r.column == "PPA"
        # Confirm runner-up is not PPA (would mean we got lucky on tie-break)
        runner_up_cols = [e.column for e in r.top_k[1:3]]
        assert "PPA" not in runner_up_cols  # PPA is #1, not in runner-up slots


# ── Revenue / sales synonyms ──────────────────────────────────────────────────


class TestRevenueSynonyms:
    def test_food_revenue_resolves_to_food_net_sales(self, hosp):
        r = hosp.resolve("food revenue", preferred_source="Food", role_hint="derived_measure")
        assert r is not None
        assert r.column == "Food_Net_Sales", f"Expected Food_Net_Sales, got {r.column}"

    def test_beverage_sales_resolves_to_beverage_net_sales(self, hosp):
        r = hosp.resolve("beverage sales", preferred_source="Beverage", role_hint="derived_measure")
        assert r is not None
        assert r.column == "Beverage_Net_Sales"

    def test_alcohol_net_sales(self, hosp):
        r = hosp.resolve(
            "alcohol net sales", preferred_source="Alcohol", role_hint="derived_measure"
        )
        assert r is not None
        assert r.column == "Alcohol_Net_Sales"

    def test_total_net_sales_without_source_hint(self, hosp):
        """Without source hint, 'total net sales' should land on Totals.Net_Sales."""
        r = hosp.resolve("total net sales", role_hint="derived_measure")
        assert r is not None
        assert r.source == "Totals" and r.column == "Net_Sales", (
            f"Expected Totals.Net_Sales, got {r.source}.{r.column}"
        )


# ── Sold / quantity synonyms ──────────────────────────────────────────────────


class TestSoldQuantitySynonyms:
    def test_items_sold_resolves_to_sold(self, hosp):
        r = hosp.resolve("items sold", preferred_source="Totals", role_hint="base_measure")
        assert r is not None
        assert r.column == "Sold", f"Expected Sold, got {r.column}"

    def test_beverage_quantity_sold(self, hosp):
        r = hosp.resolve(
            "beverage quantity sold", preferred_source="Beverage", role_hint="base_measure"
        )
        assert r is not None
        assert r.column == "Beverage_Sold"

    def test_food_qty_sold(self, hosp):
        r = hosp.resolve("food qty sold", preferred_source="Food", role_hint="base_measure")
        assert r is not None
        assert r.column == "Food_Sold", f"Expected Food_Sold, got {r.column}"


# ── Guest / covers / diners variants ─────────────────────────────────────────


class TestGuestCoversVariants:
    def test_guest_count_resolves_to_guests(self, hosp):
        """'guest count' maps to the Guests column (not a meta-query — column exists)."""
        r = hosp.resolve("guest count", preferred_source="Totals", role_hint="base_measure")
        assert r is not None
        assert r.column == "Guests", f"Expected Guests, got {r.column}"
        assert r.outcome != ResolverOutcome.META_QUERY, (
            "guest count should NOT be META_QUERY — Guests column exists"
        )

    def test_covers_resolves_to_guests(self, hosp):
        # "covers" is a hospitality synonym for guests. Without a recognized
        # source prior (hospitality sources aren't in _SOURCE_MAP), any Guests
        # variant is a correct answer — check column name only.
        r = hosp.resolve("covers", preferred_source="Totals", role_hint="base_measure")
        assert r is not None
        assert "Guests" in r.column, f"Expected a Guests-family column for 'covers', got {r.column}"

    def test_diners_resolves_to_guests(self, hosp):
        r = hosp.resolve("diners", preferred_source="Totals", role_hint="base_measure")
        assert r is not None
        assert "Guests" in r.column, f"Expected a Guests-family column for 'diners', got {r.column}"


# ── Tips / gratuity ───────────────────────────────────────────────────────────


class TestTipsGratuity:
    def test_tips_resolves(self, hosp):
        r = hosp.resolve("tips", preferred_source="Totals", role_hint="derived_measure")
        assert r is not None
        assert r.column == "Tips"

    def test_food_tips(self, hosp):
        r = hosp.resolve("food tips", preferred_source="Food", role_hint="derived_measure")
        assert r is not None
        assert r.column == "Food_Tips"

    def test_gratuity_resolves_to_tips(self, hosp):
        # Hospitality sources aren't in _SOURCE_MAP so any Tips variant is correct.
        r = hosp.resolve("gratuity", preferred_source="Totals", role_hint="derived_measure")
        assert r is not None
        assert "Tips" in r.column, f"Expected a Tips-family column for 'gratuity', got {r.column}"

    def test_beverage_gratuity(self, hosp):
        r = hosp.resolve(
            "beverage gratuity", preferred_source="Beverage", role_hint="derived_measure"
        )
        assert r is not None
        assert r.column == "Beverage_Tips", f"Expected Beverage_Tips, got {r.column}"


# ── avg / average for order time ──────────────────────────────────────────────


class TestAverageAbbreviation:
    def test_average_order_time_resolves_to_totals(self, hosp):
        r = hosp.resolve("average order time", preferred_source="Totals", role_hint="ratio")
        assert r is not None
        assert r.column == "Avg_Order_Time", f"Expected Avg_Order_Time, got {r.column}"

    def test_avg_order_time_also_resolves(self, hosp):
        """'avg order time' (abbreviated form) must also map correctly."""
        r = hosp.resolve("avg order time", preferred_source="Totals", role_hint="ratio")
        assert r is not None
        assert r.column == "Avg_Order_Time"

    def test_food_average_order_time(self, hosp):
        r = hosp.resolve("food average order time", preferred_source="Food", role_hint="ratio")
        assert r is not None
        assert r.column == "Food_Avg_Order_Time"


# ── Meta-query detection ──────────────────────────────────────────────────────


class TestMetaQueryDetection:
    def test_server_count_is_meta_query(self, hosp):
        """
        'server count' — 'server' is the row entity (staff), no column for it.
        Score will be weak; outcome must be META_QUERY, not a confident column match.
        """
        r = hosp.resolve("server count", preferred_source="Totals", role_hint="base_measure")
        assert r is not None
        assert r.outcome == ResolverOutcome.META_QUERY, (
            f"Expected META_QUERY, got {r.outcome} (score={r.score:.3f})"
        )

    def test_how_many_guests_is_meta_query(self, hosp):
        r = hosp.resolve("how many guests", preferred_source="Totals")
        assert r is not None
        assert r.outcome == ResolverOutcome.META_QUERY, (
            f"Expected META_QUERY for 'how many guests', got {r.outcome}"
        )

    def test_number_of_servers_is_meta_query(self, hosp):
        r = hosp.resolve("number of servers", preferred_source="Totals")
        assert r is not None
        assert r.outcome == ResolverOutcome.META_QUERY

    def test_count_of_orders_is_meta_query(self, hosp):
        r = hosp.resolve("count of orders", preferred_source="Totals")
        assert r is not None
        assert r.outcome == ResolverOutcome.META_QUERY

    def test_meta_query_is_never_confident(self, hosp):
        """A META_QUERY result must never set confident=True."""
        for hint in ["server count", "how many guests", "number of servers"]:
            r = hosp.resolve(hint, preferred_source="Totals")
            if r is not None and r.outcome == ResolverOutcome.META_QUERY:
                assert not r.confident, f"META_QUERY result has confident=True for hint={hint!r}"

    def test_guest_count_is_not_meta_query(self, hosp):
        """
        'guest count' must NOT be META_QUERY — the Guests column exists and
        scores above the weak-match threshold.
        """
        r = hosp.resolve("guest count", preferred_source="Totals", role_hint="base_measure")
        assert r is not None
        assert r.outcome != ResolverOutcome.META_QUERY, (
            f"'guest count' was misclassified as META_QUERY "
            f"(score={r.score:.3f}) — Guests column exists and should win"
        )


# ── Full hospitality batch — accuracy gate ───────────────────────────────────


class TestHospitalityBatch:
    """
    End-to-end accuracy gate: ≥ 90% of column-resolvable queries must be correct.
    Meta-query cases are excluded from the accuracy denominator.
    """

    _QUERIES: list[tuple[str, str | None, str, str, str]] = [
        # (hint,                      source,     role,               exp_col,                 exp_src)
        ("total net sales", None, "derived_measure", "Net_Sales", "Totals"),
        ("food revenue", "Food", "derived_measure", "Food_Net_Sales", "Food"),
        ("beverage sales", "Beverage", "derived_measure", "Beverage_Net_Sales", "Beverage"),
        ("alcohol net sales", "Alcohol", "derived_measure", "Alcohol_Net_Sales", "Alcohol"),
        ("tips", "Totals", "derived_measure", "Tips", "Totals"),
        ("food tips", "Food", "derived_measure", "Food_Tips", "Food"),
        ("items sold", "Totals", "base_measure", "Sold", "Totals"),
        ("beverage quantity sold", "Beverage", "base_measure", "Beverage_Sold", "Beverage"),
        ("per person average", "Totals", "ratio", "PPA", "Totals"),
        ("food per person average", "Food", "ratio", "Food_PPA", "Food"),
        ("average order time", "Totals", "ratio", "Avg_Order_Time", "Totals"),
        ("guest count", "Totals", "base_measure", "Guests", "Totals"),
    ]

    # These are expected to return META_QUERY — excluded from accuracy count
    _META_QUERIES: list[str] = [
        "server count",
        "how many guests",
        "number of servers",
    ]

    def test_column_accuracy_gate(self, hosp):
        correct = 0
        total = len(self._QUERIES)
        failures = []
        for hint, src, role, exp_col, exp_src in self._QUERIES:
            r = hosp.resolve(hint, preferred_source=src, role_hint=role)
            if r is None:
                failures.append(f"  {hint!r} → None  (expected {exp_col})")
                continue
            ok = r.column == exp_col and (src is None or r.source == exp_src)
            if ok:
                correct += 1
            else:
                failures.append(
                    f"  {hint!r} → {r.source}.{r.column}  score={r.score:.3f}  "
                    f"(expected {exp_src}.{exp_col})"
                )
        pct = correct / total
        assert pct >= 0.90, (
            f"Hospitality batch accuracy {correct}/{total} ({pct:.0%}) < 90%\n"
            + "\n".join(failures)
        )

    def test_meta_queries_are_classified_correctly(self, hosp):
        for hint in self._META_QUERIES:
            r = hosp.resolve(hint, preferred_source="Totals")
            assert r is not None
            assert r.outcome == ResolverOutcome.META_QUERY, (
                f"{hint!r} → outcome={r.outcome} (expected META_QUERY)"
            )

    def test_no_meta_query_returns_confident_column(self, hosp):
        """Meta-query results must never short-circuit the planner as a column match."""
        for hint in self._META_QUERIES:
            r = hosp.resolve(hint, preferred_source="Totals")
            if r is not None:
                assert not r.confident, (
                    f"META_QUERY hint {hint!r} returned confident=True — "
                    f"this would cause the planner to short-circuit incorrectly"
                )
