"""Tests for test_vector_resolver: plannerintegration_b.

Extracted from /Users/angel/Developer/decision-engine/tests/test_vector_resolver.py during modularization.
"""
from __future__ import annotations

from tests._test_vector_resolver_helpers import *  # noqa: F401,F403


class TestPlannerIntegration:
    def test_planner_decodes_compact_resident_query_payload(self, monkeypatch, tmp_path):
        import apps.api_server.services.auto_planner as auto_planner
        import apps.api_server.services.mojo_column_rank_resolver as rank_resolver

        monkeypatch.setattr(auto_planner, "_MOJO_COLUMN_RANK_MODE", "force")
        binary = tmp_path / "simulate"
        binary.write_text("")
        binary.chmod(0o755)

        planner = auto_planner.AutoPlanner(
            data_dir=tmp_path, llm_policy="never", mojo_binary=binary
        )
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

        planner = auto_planner.AutoPlanner(
            data_dir=tmp_path, llm_policy="never", mojo_binary=binary
        )
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

        planner = auto_planner.AutoPlanner(
            data_dir=tmp_path, llm_policy="never", mojo_binary=binary
        )
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
                "OH_COST": ColumnNode(
                    name="OH_COST",
                    role=DERIVED_MEASURE,
                    is_numeric=True,
                    magnitude_class="medium",
                    fill_rate=1.0,
                ),
                "EXT_COST": ColumnNode(
                    name="EXT_COST",
                    role=DERIVED_MEASURE,
                    is_numeric=True,
                    magnitude_class="large",
                    fill_rate=1.0,
                ),
                "UNIT_COST": ColumnNode(
                    name="UNIT_COST",
                    role=UNIT_MEASURE,
                    is_numeric=True,
                    magnitude_class="medium",
                    fill_rate=1.0,
                ),
            }
        }
        planner.profiles = {
            "WH": {
                "OH_COST": {
                    "is_numeric": True,
                    "numeric": [20.0],
                    "fill_rate": 1.0,
                    "mean": 20.0,
                    "std": 2.0,
                    "sample_values": [20.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "EXT_COST": {
                    "is_numeric": True,
                    "numeric": [80.0],
                    "fill_rate": 1.0,
                    "mean": 80.0,
                    "std": 5.0,
                    "sample_values": [80.0],
                    "strings": [],
                    "unique_count": 1,
                    "total_count": 1,
                },
                "UNIT_COST": {
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
        planner._build_vector_resolver()

        src, col, conf, role, steps = planner.resolve_metric("overhead cost", "WH", "sum")

        # Must resolve to OH_COST (existing regression)
        assert col == "OH_COST", f"Got {col}, expected OH_COST. Steps: {steps}"
        assert conf > 0.5
