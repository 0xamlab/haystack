"""Tests for test_vector_resolver: plannerintegration_a.

Extracted from /Users/angel/Developer/decision-engine/tests/test_vector_resolver.py during modularization.
"""
from __future__ import annotations

from tests._test_vector_resolver_helpers import *  # noqa: F401,F403


class TestPlannerIntegration:
    def test_from_planner_graph_excludes_low_fill_rate(self):
        graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure", fill_rate=1.0),
                "SPARSE_COL": _node("derived_measure", fill_rate=0.01),
            }
        }
        resolver = ColumnVectorResolver.from_planner_graph(graph)
        assert resolver._n_columns == 1  # SPARSE_COL excluded
    def test_from_planner_graph_excludes_non_numeric(self):
        graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure", is_numeric=True),
                "CUSTOMER_NAME": _node("other", is_numeric=False),
            }
        }
        resolver = ColumnVectorResolver.from_planner_graph(graph)
        assert resolver._n_columns == 1  # CUSTOMER_NAME excluded
    def test_planner_vector_resolver_built_on_graph_set(self):
        from apps.api_server.services.auto_planner import AutoPlanner

        planner = AutoPlanner(data_dir=Path("."))
        planner.graph = {
            "POS": {
                "UNIT_PRICE": _node("unit_measure"),
                "EXT_PRICE": _node("derived_measure"),
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
            raise AssertionError(
                "resident transport should not run when shared engine transport succeeds"
            )

        def _unexpected_subprocess(*_args, **_kwargs):
            raise AssertionError(
                "subprocess transport should not run when shared engine transport succeeds"
            )

        monkeypatch.setattr(auto_planner, "_PLANNER_MOJO_TRANSPORT", "auto")
        monkeypatch.setattr(auto_planner, "invoke_engine_sync", _fake_invoke_engine_sync)
        monkeypatch.setattr(auto_planner, "invoke_planner_mojo", _unexpected_resident)
        monkeypatch.setattr(auto_planner.subprocess, "run", _unexpected_subprocess)

        result = planner._call_mojo(
            {"engine_type": "field_map", "data": {"x": [1.0, 2.0]}}, timeout=7
        )

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
            raise AssertionError(
                "subprocess transport should not run when resident transport succeeds"
            )

        monkeypatch.setattr(auto_planner, "_PLANNER_MOJO_TRANSPORT", "resident")
        monkeypatch.setattr(auto_planner, "invoke_engine_sync", _unexpected_shared)
        monkeypatch.setattr(auto_planner, "invoke_planner_mojo", _fake_invoke)
        monkeypatch.setattr(auto_planner.subprocess, "run", _unexpected_subprocess)

        result = planner._call_mojo(
            {"engine_type": "field_map", "data": {"x": [1.0, 2.0]}}, timeout=7
        )

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
            raise AssertionError(
                "resident transport should stay disabled when shared engine transport succeeds"
            )

        def _unexpected_subprocess(*_args, **_kwargs):
            raise AssertionError(
                "subprocess transport should stay disabled when shared engine transport succeeds"
            )

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
    def test_planner_mojo_client_cooldown_skips_repeated_start_failures(
        self, monkeypatch, tmp_path
    ):
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
