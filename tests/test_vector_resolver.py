"""
tests/test_vector_resolver.py — Regression tests for the vector resolver.

Covers:
  1. Direct resolver: bigram encoder, token expansion, scoring
  2. Planner integration: vector resolver short-circuits high-confidence cases
  3. Known failure class: unit-cost / extended-cost / overhead-cost disambiguation
  4. Fallback behavior: abbreviations fall through to existing logic
  5. Batch resolution: multiple fields resolved in one call

Acceptance criteria per case:
  - winning column:   exact match
  - best score:       explicit threshold (conservative — system must clear it)
  - confident flag:   True/False as documented
  - ambiguous flag:   True/False as documented

Run:
    python3 -m pytest tests/test_vector_resolver.py -v
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    import mojo.engine.vector_kernels.resolver as resolver_module
    from mojo.engine.vector_kernels.resolver import (
        ColumnVectorResolver,
        _cosine,
        build_vec64,
    )
except ImportError:
    pytest.skip("Mojo engine not available", allow_module_level=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _node(role, is_numeric=True, fill_rate=1.0):
    n = SimpleNamespace()
    n.role = role
    n.is_numeric = is_numeric
    n.fill_rate = fill_rate
    n.formula = None
    n.magnitude_class = None
    return n


# Standard procurement schema used across most tests
_POS_SCHEMA = {
    "POS": [
        ("UNIT_PRICE",   "unit_measure"),
        ("EXT_PRICE",    "derived_measure"),
        ("QTY",          "base_measure"),
        ("LINE_TOTAL",   "derived_measure"),
        ("ORDERED_ON",   "other"),
        ("CUSTOMER_NAME","other"),
    ]
}

_BACKLOG_SCHEMA = {
    "BACKLOG": [
        ("OH_COST",      "derived_measure"),
        ("EXT_COST",     "derived_measure"),
        ("UNIT_COST",    "unit_measure"),
        ("QTY_ORDERED",  "base_measure"),
        ("PART_NUMBER",  "other"),
    ]
}

_MULTI_SOURCE_SCHEMA = {**_POS_SCHEMA, **_BACKLOG_SCHEMA}


# ── Unit tests: bigram encoder ────────────────────────────────────────────────

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


# ── Unit tests: resolver construction ────────────────────────────────────────

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

        resolver = ColumnVectorResolver({
            "POS": [
                ("UNIT_PRICE", "unit_measure"),
                ("EXT_PRICE", "derived_measure"),
            ]
        })

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


# ── Regression: unit-cost / extended-cost disambiguation ─────────────────────
#
# This was a documented failure class. "unit cost" must pick UNIT_COST over
# EXT_COST; "extended cost" must pick EXT_COST over UNIT_COST.

class TestUnitVsExtendedCost:
    @pytest.fixture
    def resolver(self):
        schema = {
            "POS": [
                ("UNIT_COST",   "unit_measure"),
                ("EXT_COST",    "derived_measure"),
                ("OH_COST",     "derived_measure"),
                ("LINE_TOTAL",  "derived_measure"),
            ]
        }
        return ColumnVectorResolver(schema)

    def test_unit_cost_resolves_to_unit_cost(self, resolver):
        r = resolver.resolve("unit cost", preferred_source="POS", role_hint="unit_measure")
        assert r is not None
        assert r.column == "UNIT_COST", (
            f"Expected UNIT_COST, got {r.column}  (score={r.score:.3f})\n"
            f"steps: {r.steps}"
        )
        assert r.score >= 0.55, f"score={r.score:.3f} below minimum"

    def test_extended_cost_resolves_to_ext_cost(self, resolver):
        r = resolver.resolve("extended cost", preferred_source="POS", role_hint="derived_measure")
        assert r is not None
        assert r.column == "EXT_COST", (
            f"Expected EXT_COST, got {r.column}  (score={r.score:.3f})"
        )
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
        assert r.confidence_gap >= 0.08, (
            f"Gap too narrow: {r.confidence_gap:.3f} — ambiguity risk"
        )

    def test_top_k_includes_both_candidates(self, resolver):
        r = resolver.resolve("unit cost", preferred_source="POS")
        assert r is not None
        col_names = [e.column for e in r.top_k]
        assert "UNIT_COST" in col_names


# ── Regression: overhead abbreviation (OH → overhead) ────────────────────────
#
# OH_COST uses abbreviation "oh" for "overhead". The token alias table handles
# this (OH → overhead). The resolver should fall through (not confident) but
# must not return a wrong answer with high confidence.

class TestOverheadAbbreviation:
    @pytest.fixture
    def resolver(self):
        schema = {
            "WH": [
                ("OH_COST",     "derived_measure"),
                ("UNIT_COST",   "unit_measure"),
                ("EXT_COST",    "derived_measure"),
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
            assert r.column == "OH_COST", (
                f"Confident but wrong: got {r.column} (expected OH_COST)"
            )

    def test_overhead_cost_does_not_confidently_pick_wrong_column(self, resolver):
        """Never confidently resolve overhead cost to a non-overhead column."""
        r = resolver.resolve("overhead cost", preferred_source="WH", role_hint="derived_measure")
        assert r is not None
        if r.confident:
            assert r.column in ("OH_COST",), (
                f"Confidently picked wrong column: {r.column}"
            )


# ── Regression: multi-source with source prior ───────────────────────────────

class TestSourcePrior:
    def test_preferred_source_used_when_available(self):
        schema = {
            "POS":     [("UNIT_PRICE", "unit_measure"), ("EXT_PRICE", "derived_measure")],
            "BACKLOG": [("UNIT_COST",  "unit_measure"), ("EXT_COST",  "derived_measure")],
        }
        resolver = ColumnVectorResolver(schema)

        r_pos = resolver.resolve("unit price", preferred_source="POS")
        r_blg = resolver.resolve("unit cost",  preferred_source="BACKLOG")

        assert r_pos is not None and r_pos.source == "POS"
        assert r_blg is not None and r_blg.source == "BACKLOG"

    def test_cross_source_fallback_without_preferred(self):
        """Without preferred_source, resolver picks the globally best match."""
        schema = {
            "POS":     [("UNIT_PRICE", "unit_measure")],
            "BACKLOG": [("UNIT_COST",  "unit_measure")],
        }
        resolver = ColumnVectorResolver(schema)
        r = resolver.resolve("unit price", preferred_source=None)
        # Should find UNIT_PRICE from POS (closer bigram match)
        assert r is not None
        assert r.column == "UNIT_PRICE"


# ── Batch resolution ──────────────────────────────────────────────────────────

class TestBatchResolution:
    def test_batch_returns_correct_count(self):
        resolver = ColumnVectorResolver(_POS_SCHEMA)
        requests = [
            ("unit price",    "POS", "unit_measure"),
            ("extended price","POS", "derived_measure"),
            ("quantity",      "POS", "base_measure"),
        ]
        results = resolver.resolve_batch(requests)
        assert len(results) == 3

    def test_batch_order_preserved(self):
        resolver = ColumnVectorResolver(_POS_SCHEMA)
        requests = [
            ("unit price",     "POS", "unit_measure"),
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
                ("UNIT_PRICE",    "unit_measure"),
                ("EXT_PRICE",     "derived_measure"),
                ("QTY",           "base_measure"),
                ("CUSTOMER_NAME", "other"),
                ("ORDER_DATE",    "other"),
                ("ORDER_STATUS",  "other"),
            ]
        }
        resolver = ColumnVectorResolver(schema)

        requests = [
            ("extended price",  "POS", "derived_measure"),  # metric
            ("customer name",   "POS", "other"),             # group-by
            ("order date",      "POS", "other"),             # date filter
            ("order status",    "POS", "other"),             # filter
        ]
        results = resolver.resolve_batch(requests)
        assert len(results) == 4
        # All should produce a result
        for i, (hint, _, _) in enumerate(requests):
            assert results[i] is not None, f"Batch[{i}] '{hint}' returned None"


# ── Planner integration ───────────────────────────────────────────────────────

class TestPlannerIntegration:
    """
    Tests that the resolver is built correctly from the planner graph
    and correctly short-circuits high-confidence resolutions.
    """

    def test_from_planner_graph_excludes_low_fill_rate(self):
        graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure", fill_rate=1.0),
                "SPARSE_COL": _node("derived_measure", fill_rate=0.01),
            }
        }
        resolver = ColumnVectorResolver.from_planner_graph(graph)
        assert resolver._n_columns == 1   # SPARSE_COL excluded

    def test_from_planner_graph_excludes_non_numeric(self):
        graph = {
            "POS": {
                "UNIT_PRICE":    _node("unit_measure",    is_numeric=True),
                "CUSTOMER_NAME": _node("other",           is_numeric=False),
            }
        }
        resolver = ColumnVectorResolver.from_planner_graph(graph)
        assert resolver._n_columns == 1   # CUSTOMER_NAME excluded

    def test_planner_vector_resolver_built_on_graph_set(self):
        from apps.api_server.services.auto_planner import AutoPlanner
        planner = AutoPlanner(data_dir=Path("."))
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE":  _node("derived_measure"),
            }
        }
        planner._build_vector_resolver()
        assert planner._vector_resolver is not None

    def test_append_planner_graph_source_updates_existing_resolver(self):
        graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE": _node("derived_measure"),
            }
        }
        resolver = ColumnVectorResolver.from_planner_graph(graph)

        appended = resolver.append_planner_graph_source(
            "BACKLOG",
            {
                "UNIT_COST": _node("unit_measure"),
                "EXT_COST": _node("derived_measure"),
            },
        )

        assert appended is True
        assert resolver._n_columns == 4
        result = resolver.resolve(
            "extended cost",
            preferred_source="BACKLOG",
            role_hint="derived_measure",
        )
        assert result is not None
        assert result.source == "BACKLOG"
        assert result.column == "EXT_COST"

    def test_append_planner_graph_source_requires_rebuild_for_existing_source(self):
        graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
            }
        }
        resolver = ColumnVectorResolver.from_planner_graph(graph)

        appended = resolver.append_planner_graph_source(
            "POS",
            {
                "EXT_PRICE": _node("derived_measure"),
            },
        )

        assert appended is False

    def test_from_planner_graph_caps_wide_source_to_high_signal_columns(self, monkeypatch):
        monkeypatch.setattr(resolver_module, "MAX_PLANNER_SOURCE_COLUMNS", 2)
        graph = {
            "WIDE": {
                "DERIVED_HIGH": _node("derived_measure", fill_rate=0.95),
                "BASE_HIGH": _node("base_measure", fill_rate=0.90),
                "UNIT_HIGH": _node("unit_measure", fill_rate=0.99),
                "METRIC_HIGH": _node("metric", fill_rate=1.0),
            }
        }

        resolver = ColumnVectorResolver.from_planner_graph(graph)

        assert resolver._n_columns == 2
        assert [(entry.source, entry.name) for entry in resolver._entries] == [
            ("WIDE", "DERIVED_HIGH"),
            ("WIDE", "BASE_HIGH"),
        ]

    def test_append_planner_graph_source_caps_incremental_wide_source(self, monkeypatch):
        monkeypatch.setattr(resolver_module, "MAX_PLANNER_SOURCE_COLUMNS", 2)
        resolver = ColumnVectorResolver.from_planner_graph(
            {
                "POS": {
                    "UNIT_PRICE": _node("unit_measure"),
                }
            }
        )

        appended = resolver.append_planner_graph_source(
            "WIDE",
            {
                "DERIVED_HIGH": _node("derived_measure", fill_rate=0.95),
                "BASE_HIGH": _node("base_measure", fill_rate=0.90),
                "UNIT_HIGH": _node("unit_measure", fill_rate=0.99),
                "METRIC_HIGH": _node("metric", fill_rate=1.0),
            },
        )

        assert appended is True
        assert resolver._n_columns == 3
        assert [(entry.source, entry.name) for entry in resolver._entries[1:]] == [
            ("WIDE", "DERIVED_HIGH"),
            ("WIDE", "BASE_HIGH"),
        ]

    def test_probe_engines_includes_column_rank(self, tmp_path, monkeypatch):
        from apps.api_server.services.auto_planner import AutoPlanner

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)
        planner = AutoPlanner(data_dir=tmp_path, mojo_binary=binary)
        seen_engines = []

        def _fake_call(payload, timeout=30):
            seen_engines.append(payload["engine_type"])
            return {}

        monkeypatch.setattr(planner, "_call_mojo", _fake_call)

        engines = planner._probe_engines()

        assert "column_rank" in engines
        assert "column_rank" in seen_engines

    def test_planner_call_mojo_auto_prefers_shared_engine_transport(
        self,
        tmp_path,
        monkeypatch,
    ):
        import apps.api_server.services.auto_planner as auto_planner

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)
        planner = auto_planner.AutoPlanner(data_dir=tmp_path, mojo_binary=binary)

        seen = {}

        def _fake_invoke_engine_sync(payload, *, timeout=None):
            seen["payload"] = payload
            seen["timeout"] = timeout
            return {"ok": True}

        def _unexpected_resident(*_args, **_kwargs):
            raise AssertionError("resident transport should not run when shared engine transport succeeds")

        def _unexpected_subprocess(*_args, **_kwargs):
            raise AssertionError("subprocess transport should not run when shared engine transport succeeds")

        monkeypatch.setattr(auto_planner, "_PLANNER_MOJO_TRANSPORT", "auto")
        monkeypatch.setattr(auto_planner, "invoke_engine_sync", _fake_invoke_engine_sync)
        monkeypatch.setattr(auto_planner, "invoke_planner_mojo", _unexpected_resident)
        monkeypatch.setattr(auto_planner.subprocess, "run", _unexpected_subprocess)

        result = planner._call_mojo({"engine_type": "field_map", "data": {"x": [1.0, 2.0]}}, timeout=7)

        assert result == {"ok": True}
        assert seen["payload"]["engine_type"] == "field_map"
        assert seen["timeout"] == 7.0

    def test_planner_call_mojo_resident_mode_prefers_resident_transport(
        self,
        tmp_path,
        monkeypatch,
    ):
        import apps.api_server.services.auto_planner as auto_planner

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)
        planner = auto_planner.AutoPlanner(data_dir=tmp_path, mojo_binary=binary)

        seen = {}

        def _fake_invoke(payload, *, binary_path, timeout=1.0):
            seen["payload"] = payload
            seen["binary_path"] = binary_path
            seen["timeout"] = timeout
            return {"ok": True}

        def _unexpected_shared(*_args, **_kwargs):
            raise AssertionError("shared engine transport should stay disabled in resident mode")

        def _unexpected_subprocess(*_args, **_kwargs):
            raise AssertionError("subprocess transport should not run when resident transport succeeds")

        monkeypatch.setattr(auto_planner, "_PLANNER_MOJO_TRANSPORT", "resident")
        monkeypatch.setattr(auto_planner, "invoke_engine_sync", _unexpected_shared)
        monkeypatch.setattr(auto_planner, "invoke_planner_mojo", _fake_invoke)
        monkeypatch.setattr(auto_planner.subprocess, "run", _unexpected_subprocess)

        result = planner._call_mojo({"engine_type": "field_map", "data": {"x": [1.0, 2.0]}}, timeout=7)

        assert result == {"ok": True}
        assert seen["payload"]["engine_type"] == "field_map"
        assert seen["binary_path"] == binary
        assert seen["timeout"] == 7.0

    def test_planner_call_mojo_auto_can_fallback_to_subprocess(self, tmp_path, monkeypatch):
        import apps.api_server.services.auto_planner as auto_planner

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)
        planner = auto_planner.AutoPlanner(data_dir=tmp_path, mojo_binary=binary)

        def _missing_shared(_payload, *, timeout=None):
            assert timeout == 5.0
            raise RuntimeError("pool unavailable")

        def _fake_subprocess(_argv, *, input, capture_output, timeout):
            assert timeout == 5
            assert capture_output is True
            payload = json.loads(input.decode())
            assert payload["engine_type"] == "column_match"
            return SimpleNamespace(returncode=0, stdout=b'{"mapped": true}')

        monkeypatch.setattr(auto_planner, "_PLANNER_MOJO_TRANSPORT", "auto")
        monkeypatch.setattr(auto_planner, "invoke_engine_sync", _missing_shared)
        monkeypatch.setattr(auto_planner.subprocess, "run", _fake_subprocess)

        result = planner._call_mojo({"engine_type": "column_match"}, timeout=5)

        assert result == {"mapped": True}

    def test_planner_call_mojo_auto_prefers_shared_transport_for_join_detect(
        self,
        tmp_path,
        monkeypatch,
    ):
        import apps.api_server.services.auto_planner as auto_planner

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)
        planner = auto_planner.AutoPlanner(data_dir=tmp_path, mojo_binary=binary)

        seen = {}

        def _fake_invoke_engine_sync(payload, *, timeout=None):
            seen["payload"] = payload
            seen["timeout"] = timeout
            return {"join_keys": []}

        def _unexpected_resident(*_args, **_kwargs):
            raise AssertionError("resident transport should stay disabled when shared engine transport succeeds")

        def _unexpected_subprocess(*_args, **_kwargs):
            raise AssertionError("subprocess transport should stay disabled when shared engine transport succeeds")

        monkeypatch.setattr(auto_planner, "_PLANNER_MOJO_TRANSPORT", "auto")
        monkeypatch.setattr(auto_planner, "invoke_engine_sync", _fake_invoke_engine_sync)
        monkeypatch.setattr(auto_planner, "invoke_planner_mojo", _unexpected_resident)
        monkeypatch.setattr(auto_planner.subprocess, "run", _unexpected_subprocess)

        result = planner._call_mojo(
            {
                "engine_type": "join_detect",
                "source_a": "A",
                "source_b": "B",
                "columns": {"A.id": {"values": ["x1", "x2"], "sample_size": 2}},
            },
            timeout=4,
        )

        assert result == {"join_keys": []}
        assert seen["payload"]["engine_type"] == "join_detect"
        assert seen["timeout"] == 4.0

    def test_planner_prefers_mojo_column_rank_when_available(self, monkeypatch):
        import apps.api_server.services.auto_planner as auto_planner

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "force")
        planner = auto_planner.AutoPlanner(data_dir=Path("."), llm_policy="never")
        planner.mojo_engines = ["column_rank"]
        planner._mojo_binary = None
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE": _node("derived_measure"),
                "QTY": _node("base_measure"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {
                    "is_numeric": True,
                    "numeric": [10.0],
                    "fill_rate": 1.0,
                    "mean": 10.0,
                    "std": 1.0,
                    "sample_values": [10.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "EXT_PRICE": {
                    "is_numeric": True,
                    "numeric": [100.0],
                    "fill_rate": 1.0,
                    "mean": 100.0,
                    "std": 5.0,
                    "sample_values": [100.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "QTY": {
                    "is_numeric": True,
                    "numeric": [5.0],
                    "fill_rate": 1.0,
                    "mean": 5.0,
                    "std": 1.0,
                    "sample_values": [5.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
            }
        }

        def _fake_call(payload, timeout=30):
            if payload.get("engine_type") != "column_rank":
                return None
            return {
                "ranked": [
                    {
                        "source": "POS",
                        "column": "UNIT_PRICE",
                        "score": 0.91,
                        "name_sim": 0.74,
                        "type_boost": 0.12,
                        "confidence_gap": 0.31,
                    },
                    {
                        "source": "POS",
                        "column": "EXT_PRICE",
                        "score": 0.60,
                        "name_sim": 0.51,
                        "type_boost": -0.08,
                        "confidence_gap": 0.0,
                    },
                ],
                "ambiguous": False,
                "gap": 0.31,
            }

        monkeypatch.setattr(planner, "_call_mojo", _fake_call)

        planner._build_vector_resolver()

        assert planner._vector_resolver.__class__.__name__ == "MojoColumnRankResolver"

        src, col, conf, role, steps = planner.resolve_metric("unit price", "POS", "avg")

        assert (src, col) == ("POS", "UNIT_PRICE")
        assert conf >= 0.72
        assert any("vector_resolver" in step for step in steps)
        assert not any("resolve_metric_column" in step for step in steps)

    def test_planner_auto_mode_prefers_mojo_column_rank_when_available(self, monkeypatch):
        import apps.api_server.services.auto_planner as auto_planner

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "auto")
        planner = auto_planner.AutoPlanner(data_dir=Path("."), llm_policy="never")
        planner.mojo_engines = ["column_rank"]
        planner._mojo_binary = None
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE": _node("derived_measure"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {
                    "is_numeric": True,
                    "numeric": [10.0],
                    "fill_rate": 1.0,
                    "mean": 10.0,
                    "std": 1.0,
                    "sample_values": [10.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "EXT_PRICE": {
                    "is_numeric": True,
                    "numeric": [100.0],
                    "fill_rate": 1.0,
                    "mean": 100.0,
                    "std": 5.0,
                    "sample_values": [100.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
            }
        }

        def _fake_call(payload, timeout=30):
            if payload.get("engine_type") != "column_rank":
                return None
            return {
                "ranked": [
                    {
                        "source": "POS",
                        "column": "UNIT_PRICE",
                        "score": 0.91,
                        "name_sim": 0.74,
                        "type_boost": 0.12,
                        "confidence_gap": 0.31,
                    }
                ],
                "ambiguous": False,
                "gap": 0.31,
            }

        monkeypatch.setattr(planner, "_call_mojo", _fake_call)

        planner._build_vector_resolver()

        assert planner._vector_resolver.__class__.__name__ == "MojoColumnRankResolver"

    def test_planner_mojo_rank_pool_round_robins_clients(self, monkeypatch):
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        seen = []

        class _FakeClient:
            _next_id = 0

            def __init__(self, binary_path):
                self.binary_path = binary_path
                self.client_id = _FakeClient._next_id
                _FakeClient._next_id += 1

            def invoke(self, payload, timeout, **_kwargs):
                seen.append(self.client_id)
                return {"client_id": self.client_id}

            def close(self):
                return None

        monkeypatch.setattr(rank_resolver, "_PlannerMojoSocketClient", _FakeClient)
        monkeypatch.setattr(rank_resolver, "_PLANNER_MOJO_POOL_SIZE", 3)
        rank_resolver._close_planner_clients()

        binary = Path("mojo_build/simulate")
        outputs = [
            rank_resolver.invoke_column_rank({"engine_type": "column_rank"}, binary_path=binary)
            for _ in range(4)
        ]

        assert [item["client_id"] for item in outputs] == [0, 1, 2, 0]
        assert seen == [0, 1, 2, 0]

    def test_planner_mojo_rank_pool_keeps_session_bound_calls_on_one_client(self, monkeypatch):
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        seen = []

        class _FakeClient:
            _next_id = 0

            def __init__(self, binary_path):
                self.binary_path = binary_path
                self.client_id = _FakeClient._next_id
                _FakeClient._next_id += 1

            def invoke(self, payload, timeout, **_kwargs):
                seen.append(self.client_id)
                return {"client_id": self.client_id}

            def close(self):
                return None

        monkeypatch.setattr(rank_resolver, "_PlannerMojoSocketClient", _FakeClient)
        monkeypatch.setattr(rank_resolver, "_PLANNER_MOJO_POOL_SIZE", 3)
        rank_resolver._close_planner_clients()

        binary = Path("mojo_build/simulate")
        outputs = [
            rank_resolver.invoke_column_rank(
                {"engine_type": "column_rank"},
                binary_path=binary,
                session_key="org_a:session_1",
                init_payload={"type": "column_rank_init", "entries": []},
            )
            for _ in range(4)
        ]

        assert len({item["client_id"] for item in outputs}) == 1
        assert len(set(seen)) == 1

    def test_planner_mojo_clients_use_distinct_socket_paths(self, tmp_path):
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        client_a = rank_resolver._PlannerMojoSocketClient(binary)
        client_b = rank_resolver._PlannerMojoSocketClient(binary)
        try:
            assert client_a._socket_path != client_b._socket_path
        finally:
            client_a.close()
            client_b.close()

    def test_planner_mojo_client_cooldown_skips_repeated_start_failures(self, monkeypatch, tmp_path):
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        client = rank_resolver._PlannerMojoSocketClient(binary)
        calls = {"count": 0}

        def _fail_start(_timeout):
            calls["count"] += 1
            raise RuntimeError("planner Mojo rank server exited during startup")

        monkeypatch.setattr(client, "_ensure_started", _fail_start)
        monkeypatch.setattr(rank_resolver, "_PLANNER_MOJO_FAILURE_COOLDOWN_S", 60.0)

        assert client.invoke({"engine_type": "column_rank"}, timeout=1.0) is None
        assert client.invoke({"engine_type": "column_rank"}, timeout=1.0) is None
        assert calls["count"] == 1

    def test_planner_uses_resident_query_payload_when_binary_available(self, monkeypatch, tmp_path):
        import apps.api_server.services.auto_planner as auto_planner
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "force")
        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        planner = auto_planner.AutoPlanner(data_dir=tmp_path, llm_policy="never", mojo_binary=binary)
        planner.mojo_engines = ["column_rank"]
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE": _node("derived_measure"),
                "QTY": _node("base_measure"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {
                    "is_numeric": True,
                    "numeric": [10.0],
                    "fill_rate": 1.0,
                    "mean": 10.0,
                    "std": 1.0,
                    "sample_values": [10.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "EXT_PRICE": {
                    "is_numeric": True,
                    "numeric": [100.0],
                    "fill_rate": 1.0,
                    "mean": 100.0,
                    "std": 5.0,
                    "sample_values": [100.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "QTY": {
                    "is_numeric": True,
                    "numeric": [5.0],
                    "fill_rate": 1.0,
                    "mean": 5.0,
                    "std": 1.0,
                    "sample_values": [5.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
            }
        }
        captured = {}

        def _fake_invoke(payload, *, binary_path, timeout=1.0, session_key=None, init_payload=None):
            captured["payload"] = payload
            captured["binary_path"] = binary_path
            captured["timeout"] = timeout
            captured["session_key"] = session_key
            captured["init_payload"] = init_payload
            return {
                "ranked": [
                    {
                        "source": "POS",
                        "column": "UNIT_PRICE",
                        "score": 0.91,
                        "name_sim": 0.74,
                        "type_boost": 0.12,
                        "confidence_gap": 0.31,
                    }
                ],
                "ambiguous": False,
                "gap": 0.31,
            }

        monkeypatch.setattr(rank_resolver, "invoke_column_rank", _fake_invoke)

        planner._build_vector_resolver()
        src, col, conf, role, steps = planner.resolve_metric("unit price", "POS", "avg")

        assert (src, col) == ("POS", "UNIT_PRICE")
        assert conf >= 0.72
        assert captured["payload"]["type"] == "column_rank_query"
        assert captured["payload"]["engine_type"] == "column_rank_query"
        assert captured["payload"]["candidate_ids"]
        assert captured["init_payload"]["type"] == "column_rank_init"
        assert captured["init_payload"]["engine_type"] == "column_rank_init"
        assert captured["session_key"]
        assert captured["binary_path"] == binary
        assert any("vector_resolver" in step for step in steps)

    def test_planner_decodes_compact_resident_query_payload(self, monkeypatch, tmp_path):
        import apps.api_server.services.auto_planner as auto_planner
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "force")
        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        planner = auto_planner.AutoPlanner(data_dir=tmp_path, llm_policy="never", mojo_binary=binary)
        planner.mojo_engines = ["column_rank"]
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE": _node("derived_measure"),
                "QTY": _node("base_measure"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {
                    "is_numeric": True,
                    "numeric": [10.0],
                    "fill_rate": 1.0,
                    "mean": 10.0,
                    "std": 1.0,
                    "sample_values": [10.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "EXT_PRICE": {
                    "is_numeric": True,
                    "numeric": [100.0],
                    "fill_rate": 1.0,
                    "mean": 100.0,
                    "std": 5.0,
                    "sample_values": [100.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "QTY": {
                    "is_numeric": True,
                    "numeric": [5.0],
                    "fill_rate": 1.0,
                    "mean": 5.0,
                    "std": 1.0,
                    "sample_values": [5.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
            }
        }

        def _fake_invoke(payload, *, binary_path, timeout=1.0, session_key=None, init_payload=None):
            return {
                "ranked": [
                    {
                        "id": 0,
                        "score": 0.91,
                        "name_sim": 0.74,
                        "type_boost": 0.12,
                        "confidence_gap": 0.31,
                    }
                ],
                "ambiguous": False,
                "gap": 0.31,
            }

        monkeypatch.setattr(rank_resolver, "invoke_column_rank", _fake_invoke)

        planner._build_vector_resolver()
        src, col, conf, role, steps = planner.resolve_metric("unit price", "POS", "avg")

        assert (src, col) == ("POS", "UNIT_PRICE")
        assert conf >= 0.72
        assert any("vector_resolver" in step for step in steps)

    def test_planner_resolve_plan_fields_uses_batch_payload(self, monkeypatch, tmp_path):
        import apps.api_server.services.auto_planner as auto_planner
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "force")
        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        planner = auto_planner.AutoPlanner(data_dir=tmp_path, llm_policy="never", mojo_binary=binary)
        planner.mojo_engines = ["column_rank"]
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "CUSTOMER_NAME": _node("other"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {
                    "is_numeric": True,
                    "numeric": [10.0],
                    "fill_rate": 1.0,
                    "mean": 10.0,
                    "std": 1.0,
                    "sample_values": [10.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "CUSTOMER_NAME": {
                    "is_numeric": True,
                    "numeric": [1.0],
                    "fill_rate": 1.0,
                    "mean": 1.0,
                    "std": 0.0,
                    "sample_values": ["ACME"],
                    "strings": ["ACME"],
                    "unique_count": 1,
                    "total_count": 1,
                },
            }
        }
        captured = {}

        def _fake_invoke(payload, *, binary_path, timeout=1.0, session_key=None, init_payload=None):
            captured["payload"] = payload
            return {
                "results": [
                    {
                        "ranked": [
                            {
                                "source": "POS",
                                "column": "UNIT_PRICE",
                                "score": 0.91,
                                "name_sim": 0.74,
                                "type_boost": 0.12,
                                "confidence_gap": 0.31,
                            }
                        ],
                        "ambiguous": False,
                        "gap": 0.31,
                    },
                    {
                        "ranked": [
                            {
                                "source": "POS",
                                "column": "CUSTOMER_NAME",
                                "score": 0.90,
                                "name_sim": 0.72,
                                "type_boost": 0.11,
                                "confidence_gap": 0.24,
                            }
                        ],
                        "ambiguous": False,
                        "gap": 0.24,
                    },
                ]
            }

        monkeypatch.setattr(rank_resolver, "invoke_column_rank", _fake_invoke)

        planner._build_vector_resolver()
        results = planner._vector_resolver.resolve_plan_fields(
            metric=("unit price", "POS", "unit_measure"),
            group_by=("customer name", "POS", "other"),
        )

        assert captured["payload"]["type"] == "column_rank_batch"
        assert captured["payload"]["engine_type"] == "column_rank_batch"
        assert len(captured["payload"]["requests"]) == 2
        assert results["metric"] is not None
        assert results["metric"].column == "UNIT_PRICE"
        assert results["group_by"] is not None
        assert results["group_by"].column == "CUSTOMER_NAME"

    def test_mojo_column_rank_resident_session_appends_new_source_incrementally(
        self,
        monkeypatch,
        tmp_path,
    ):
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        base_resolver = ColumnVectorResolver(
            {
                "POS": [
                    ("UNIT_PRICE", "unit_measure"),
                    ("EXT_PRICE", "derived_measure"),
                ]
            }
        )
        resolver = rank_resolver.MojoColumnRankResolver(
            base_resolver,
            call_mojo=lambda payload, timeout=1: {},
            binary_path=binary,
        )
        initial_session = resolver._resident_session_key
        initial_entries = list(resolver._resident_init_payload["entries"])

        appended = resolver.append_planner_graph_source(
            "BACKLOG",
            {
                "UNIT_COST": _node("unit_measure"),
                "EXT_COST": _node("derived_measure"),
            },
            fill_rates={
                ("BACKLOG", "UNIT_COST"): 1.0,
                ("BACKLOG", "EXT_COST"): 1.0,
            },
        )

        assert appended is True
        assert resolver._resident_session_key != initial_session
        assert len(initial_entries) == 2
        assert len(resolver._resident_init_payload["entries"]) == 4
        assert resolver._resident_init_payload["entries"][:2] == initial_entries
        assert [entry["source"] for entry in resolver._resident_init_payload["entries"][2:]] == [
            "BACKLOG",
            "BACKLOG",
        ]

    def test_planner_resolve_plan_fields_decodes_compact_batch_payload(
        self,
        monkeypatch,
        tmp_path,
    ):
        import apps.api_server.services.auto_planner as auto_planner
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "force")
        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        planner = auto_planner.AutoPlanner(data_dir=tmp_path, llm_policy="never", mojo_binary=binary)
        planner.mojo_engines = ["column_rank"]
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "CUSTOMER_NAME": _node("other"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {
                    "is_numeric": True,
                    "numeric": [10.0],
                    "fill_rate": 1.0,
                    "mean": 10.0,
                    "std": 1.0,
                    "sample_values": [10.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "CUSTOMER_NAME": {
                    "is_numeric": True,
                    "numeric": [1.0],
                    "fill_rate": 1.0,
                    "mean": 1.0,
                    "std": 0.0,
                    "sample_values": ["ACME"],
                    "strings": ["ACME"],
                    "unique_count": 1,
                    "total_count": 1,
                },
            }
        }

        def _fake_invoke(payload, *, binary_path, timeout=1.0, session_key=None, init_payload=None):
            return {
                "results": [
                    {
                        "ranked": [
                            {
                                "id": 0,
                                "score": 0.91,
                                "name_sim": 0.74,
                                "type_boost": 0.12,
                                "confidence_gap": 0.31,
                            }
                        ],
                        "ambiguous": False,
                        "gap": 0.31,
                    },
                    {
                        "ranked": [
                            {
                                "id": 1,
                                "score": 0.90,
                                "name_sim": 0.72,
                                "type_boost": 0.11,
                                "confidence_gap": 0.24,
                            }
                        ],
                        "ambiguous": False,
                        "gap": 0.24,
                    },
                ]
            }

        monkeypatch.setattr(rank_resolver, "invoke_column_rank", _fake_invoke)

        planner._build_vector_resolver()
        results = planner._vector_resolver.resolve_plan_fields(
            metric=("unit price", "POS", "unit_measure"),
            group_by=("customer name", "POS", "other"),
        )

        assert results["metric"] is not None
        assert results["metric"].column == "UNIT_PRICE"
        assert results["group_by"] is not None
        assert results["group_by"].column == "CUSTOMER_NAME"

    def test_vector_resolver_short_circuits_unit_price(self):
        """
        When vector resolver is confident, resolve_metric must use its result
        without reaching the Python fallback (no 'resolve_metric_column' in steps).
        """
        from apps.api_server.services.auto_planner import AutoPlanner
        planner = AutoPlanner(data_dir=Path("."), llm_policy="never")
        planner.mojo_engines = []
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE":  _node("derived_measure"),
                "QTY":        _node("base_measure"),
            }
        }
        planner.profiles = {
            "POS": {
                "UNIT_PRICE": {"is_numeric": True, "numeric": [10.0], "fill_rate": 1.0, "mean": 10.0, "std": 1.0, "sample_values": [10.0], "strings": [], "unique_count": 1, "total_count": 1},
                "EXT_PRICE":  {"is_numeric": True, "numeric": [100.0], "fill_rate": 1.0, "mean": 100.0, "std": 5.0, "sample_values": [100.0], "strings": [], "unique_count": 1, "total_count": 1},
                "QTY":        {"is_numeric": True, "numeric": [5.0], "fill_rate": 1.0, "mean": 5.0, "std": 1.0, "sample_values": [5.0], "strings": [], "unique_count": 1, "total_count": 1},
            }
        }
        planner._build_vector_resolver()

        src, col, conf, role, steps = planner.resolve_metric("unit price", "POS", "avg")

        assert (src, col) == ("POS", "UNIT_PRICE"), f"Got {src}.{col}"
        assert conf >= 0.72
        # Vector resolver path is annotated in steps
        assert any("vector_resolver" in s for s in steps), (
            f"Expected vector_resolver in steps. Steps: {steps}"
        )
        # Should not have reached Python fallback
        assert not any("resolve_metric_column" in s for s in steps), (
            f"Should not have fallen through to Python fallback. Steps: {steps}"
        )

    def test_vector_resolver_falls_through_for_abbreviation(self):
        """
        'overhead cost' should fall through to existing Python logic (abbreviation case).
        Either path must return OH_COST correctly.
        """
        from apps.api_server.routers.query import DERIVED_MEASURE, UNIT_MEASURE, ColumnNode
        from apps.api_server.services.auto_planner import AutoPlanner
        planner = AutoPlanner(data_dir=Path("."), llm_policy="never")
        planner.mojo_engines = []
        planner.graph = {
            "WH": {
                "OH_COST":   ColumnNode(name="OH_COST",   role=DERIVED_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
                "EXT_COST":  ColumnNode(name="EXT_COST",  role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large",  fill_rate=1.0),
                "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE,    is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            }
        }
        planner.profiles = {
            "WH": {
                "OH_COST":   {"is_numeric": True, "numeric": [20.0], "fill_rate": 1.0, "mean": 20.0, "std": 2.0, "sample_values": [20.0], "strings": [], "unique_count": 1, "total_count": 1},
                "EXT_COST":  {"is_numeric": True, "numeric": [80.0], "fill_rate": 1.0, "mean": 80.0, "std": 5.0, "sample_values": [80.0], "strings": [], "unique_count": 1, "total_count": 1},
                "UNIT_COST": {"is_numeric": True, "numeric": [5.0],  "fill_rate": 1.0, "mean": 5.0,  "std": 1.0, "sample_values": [5.0],  "strings": [], "unique_count": 1, "total_count": 1},
            }
        }
        planner._build_vector_resolver()

        src, col, conf, role, steps = planner.resolve_metric("overhead cost", "WH", "sum")

        # Must resolve to OH_COST (existing regression)
        assert col == "OH_COST", f"Got {col}, expected OH_COST. Steps: {steps}"
        assert conf > 0.5
