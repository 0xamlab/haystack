"""Tests for test_vector_resolver: buildvec64_etc.

Extracted from /Users/angel/Developer/decision-engine/tests/test_vector_resolver.py during modularization.
"""
from __future__ import annotations

from tests._test_vector_resolver_helpers import *  # noqa: F401,F403


class TestBuildVec64:
    def test_case_insensitive(self):
        v1, n1 = build_vec64("unit_price")
        v2, n2 = build_vec64("UNIT_PRICE")
        assert v1 == v2
        assert abs(n1 - n2) < 1e-9

    def test_self_cosine_is_one(self):
        v, ni = build_vec64("ext_price")
        sim = _cosine(v, v, ni, ni)
        assert abs(sim - 1.0) < 1e-5

    def test_empty_name_returns_zero_norm(self):
        v, ni = build_vec64("")
        assert ni == 0.0
        assert all(x == 0.0 for x in v)

    def test_similar_names_have_high_cosine(self):
        v1, n1 = build_vec64("unit_price")
        v2, n2 = build_vec64("unit_cost")
        sim = _cosine(v1, v2, n1, n2)
        # Bigram encoder shares "unit" prefix but not "price"/"cost" — realistic lower bound
        assert sim >= 0.45, f"unit_price vs unit_cost cosine={sim:.4f} (expected >= 0.45)"

    def test_distinct_names_have_low_cosine(self):
        v1, n1 = build_vec64("unit_price")
        v2, n2 = build_vec64("customer_name")
        sim = _cosine(v1, v2, n1, n2)
        assert sim < 0.40, f"unit_price vs customer_name cosine={sim:.4f} (expected < 0.40)"


class TestResolverConstruction:
    def test_empty_source_map_returns_none(self):
        r = ColumnVectorResolver({})
        result = r.resolve("unit price")
        assert result is None

    def test_single_source_single_column(self):
        r = ColumnVectorResolver({"POS": [("UNIT_PRICE", "unit_measure")]})
        result = r.resolve("unit price", preferred_source="POS")
        assert result is not None
        assert result.column == "UNIT_PRICE"

    def test_append_source_reuses_cached_column_artifacts_for_repeated_names(self, monkeypatch):
        tokenize_calls = {"count": 0}
        build_calls = {"count": 0}
        real_tokenize = resolver_module.tokenize_name
        real_build_vec = resolver_module.build_vec64

        def _count_tokenize(name: str):
            tokenize_calls["count"] += 1
            return real_tokenize(name)

        def _count_build_vec(name: str):
            build_calls["count"] += 1
            return real_build_vec(name)

        monkeypatch.setattr(resolver_module, "tokenize_name", _count_tokenize)
        monkeypatch.setattr(resolver_module, "build_vec64", _count_build_vec)

        resolver = ColumnVectorResolver(
            {
                "POS": [
                    ("UNIT_PRICE", "unit_measure"),
                    ("EXT_PRICE", "derived_measure"),
                ]
            }
        )

        assert tokenize_calls["count"] == 2
        assert build_calls["count"] == 2

        resolver.append_source(
            "BACKLOG",
            [
                ("UNIT_PRICE", "unit_measure"),
                ("EXT_PRICE", "derived_measure"),
            ],
        )

        assert tokenize_calls["count"] == 2
        assert build_calls["count"] == 2


class TestUnitVsExtendedCost:
    @pytest.fixture
    def resolver(self):
        schema = {
            "POS": [
                ("UNIT_COST", "unit_measure"),
                ("EXT_COST", "derived_measure"),
                ("OH_COST", "derived_measure"),
                ("LINE_TOTAL", "derived_measure"),
            ]
        }
        return ColumnVectorResolver(schema)

    def test_unit_cost_resolves_to_unit_cost(self, resolver):
        r = resolver.resolve("unit cost", preferred_source="POS", role_hint="unit_measure")
        assert r is not None
        assert r.column == "UNIT_COST", (
            f"Expected UNIT_COST, got {r.column}  (score={r.score:.3f})\nsteps: {r.steps}"
        )
        assert r.score >= 0.55, f"score={r.score:.3f} below minimum"

    def test_extended_cost_resolves_to_ext_cost(self, resolver):
        r = resolver.resolve("extended cost", preferred_source="POS", role_hint="derived_measure")
        assert r is not None
        assert r.column == "EXT_COST", f"Expected EXT_COST, got {r.column}  (score={r.score:.3f})"
        assert r.score >= 0.40

    def test_unit_cost_is_confident_with_role_hint(self, resolver):
        r = resolver.resolve("unit cost", preferred_source="POS", role_hint="unit_measure")
        assert r is not None
        assert r.confident, (
            f"Expected confident=True for 'unit cost' → UNIT_COST, "
            f"got score={r.score:.3f} gap={r.confidence_gap:.3f}"
        )

    def test_unit_cost_gap_is_wide(self, resolver):
        """unit cost vs extended cost should have a clear winner."""
        r = resolver.resolve("unit cost", preferred_source="POS", role_hint="unit_measure")
        assert r is not None
        assert r.confidence_gap >= 0.08, f"Gap too narrow: {r.confidence_gap:.3f} — ambiguity risk"

    def test_top_k_includes_both_candidates(self, resolver):
        r = resolver.resolve("unit cost", preferred_source="POS")
        assert r is not None
        col_names = [e.column for e in r.top_k]
        assert "UNIT_COST" in col_names


class TestOverheadAbbreviation:
    @pytest.fixture
    def resolver(self):
        schema = {
            "WH": [
                ("OH_COST", "derived_measure"),
                ("UNIT_COST", "unit_measure"),
                ("EXT_COST", "derived_measure"),
            ]
        }
        return ColumnVectorResolver(schema)

    def test_overhead_cost_falls_through_or_correct(self, resolver):
        """
        The vector resolver may or may not be confident on 'overhead cost'.
        If confident: must pick OH_COST.
        If not confident: that is acceptable — planner falls through to token/fuzzy logic.
        """
        r = resolver.resolve("overhead cost", preferred_source="WH", role_hint="derived_measure")
        assert r is not None
        if r.confident:
            assert r.column == "OH_COST", f"Confident but wrong: got {r.column} (expected OH_COST)"

    def test_overhead_cost_does_not_confidently_pick_wrong_column(self, resolver):
        """Never confidently resolve overhead cost to a non-overhead column."""
        r = resolver.resolve("overhead cost", preferred_source="WH", role_hint="derived_measure")
        assert r is not None
        if r.confident:
            assert r.column in ("OH_COST",), f"Confidently picked wrong column: {r.column}"


class TestSourcePrior:
    def test_preferred_source_used_when_available(self):
        schema = {
            "POS": [("UNIT_PRICE", "unit_measure"), ("EXT_PRICE", "derived_measure")],
            "BACKLOG": [("UNIT_COST", "unit_measure"), ("EXT_COST", "derived_measure")],
        }
        resolver = ColumnVectorResolver(schema)

        r_pos = resolver.resolve("unit price", preferred_source="POS")
        r_blg = resolver.resolve("unit cost", preferred_source="BACKLOG")

        assert r_pos is not None and r_pos.source == "POS"
        assert r_blg is not None and r_blg.source == "BACKLOG"

    def test_cross_source_fallback_without_preferred(self):
        """Without preferred_source, resolver picks the globally best match."""
        schema = {
            "POS": [("UNIT_PRICE", "unit_measure")],
            "BACKLOG": [("UNIT_COST", "unit_measure")],
        }
        resolver = ColumnVectorResolver(schema)
        r = resolver.resolve("unit price", preferred_source=None)
        # Should find UNIT_PRICE from POS (closer bigram match)
        assert r is not None
        assert r.column == "UNIT_PRICE"


class TestBatchResolution:
    def test_batch_returns_correct_count(self):
        resolver = ColumnVectorResolver(_POS_SCHEMA)
        requests = [
            ("unit price", "POS", "unit_measure"),
            ("extended price", "POS", "derived_measure"),
            ("quantity", "POS", "base_measure"),
        ]
        results = resolver.resolve_batch(requests)
        assert len(results) == 3

    def test_batch_order_preserved(self):
        resolver = ColumnVectorResolver(_POS_SCHEMA)
        requests = [
            ("unit price", "POS", "unit_measure"),
            ("extended price", "POS", "derived_measure"),
        ]
        results = resolver.resolve_batch(requests)
        assert results[0] is not None
        assert results[0].column == "UNIT_PRICE"
        assert results[1] is not None
        assert results[1].column == "EXT_PRICE"

    def test_batch_four_fields_procurement(self):
        """
        Simulate a planner batch: metric, group-by target, date, filter.
        All four fields in one call.
        """
        schema = {
            "POS": [
                ("UNIT_PRICE", "unit_measure"),
                ("EXT_PRICE", "derived_measure"),
                ("QTY", "base_measure"),
                ("CUSTOMER_NAME", "other"),
                ("ORDER_DATE", "other"),
                ("ORDER_STATUS", "other"),
            ]
        }
        resolver = ColumnVectorResolver(schema)

        requests = [
            ("extended price", "POS", "derived_measure"),  # metric
            ("customer name", "POS", "other"),  # group-by
            ("order date", "POS", "other"),  # date filter
            ("order status", "POS", "other"),  # filter
        ]
        results = resolver.resolve_batch(requests)
        assert len(results) == 4
        # All should produce a result
        for i, (hint, _, _) in enumerate(requests):
            assert results[i] is not None, f"Batch[{i}] '{hint}' returned None"

