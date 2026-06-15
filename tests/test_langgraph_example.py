from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ROOT), str(PYTHON_SDK)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "langgraph_tool_example",
        ROOT / "examples" / "langgraph" / "decision_tool.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _invoke_tool(tool_obj, /, *args, **kwargs):
    target = getattr(tool_obj, "func", tool_obj)
    return target(*args, **kwargs)


def test_query_dataset_metric_uses_public_sdk_discovery_and_metadata(monkeypatch) -> None:
    module = _load_module()

    contract = SimpleNamespace(
        api_base_url="https://api.codna.ai",
        primary_data_query_contract=SimpleNamespace(
            api=SimpleNamespace(
                contract_endpoint="/v1/meta/contract",
                discovery_endpoint="/v1/data",
                summary_endpoint="/v1/data/{dataset_id}/summary",
                query_endpoint="/v1/query",
                query_batch_endpoint="/v1/query/batch",
                query_sql_report_endpoint="/v1/query/sql-report",
            ),
            direct_sdk=SimpleNamespace(
                python=SimpleNamespace(contract_method="get_contract"),
                typescript=SimpleNamespace(contract_method="getContract"),
            ),
            cli=SimpleNamespace(contract_command="de contract"),
            mcp=SimpleNamespace(contract_tool="get_contract"),
        ),
    )

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def get_contract(self):
            self.calls.append(("get_contract", None))
            return contract

        def list_datasets(self, **kwargs):
            self.calls.append(("list_datasets", kwargs))
            return SimpleNamespace(
                datasets=[SimpleNamespace(dataset_id="ds_orders")],
                matched_total=3,
            )

        def get_dataset_summary(self, dataset_id: str):
            self.calls.append(("get_dataset_summary", dataset_id))
            return SimpleNamespace(
                dataset_id=dataset_id,
                name="Orders Monthly",
                query_hints=["sum completed orders by order_month"],
            )

        def query_with_metadata(self, request: dict[str, object]):
            self.calls.append(("query_with_metadata", request))
            return SimpleNamespace(
                data=SimpleNamespace(
                    result=[{"order_month": "2026-01-01", "completed_order_count": 91}],
                ),
                metadata=SimpleNamespace(
                    request_id="req_query",
                    latency_ms=18.5,
                    tokens_in=120,
                    tokens_out=45,
                    cost_usd=0.0025,
                    cache_hit=True,
                ),
            )

    fake = FakeClient()
    monkeypatch.setattr(module, "_client", lambda: fake)

    raw = _invoke_tool(
        module.query_dataset_metric,
        dataset_search="orders",
        metric_hint="completed_order_count",
        aggregation="sum",
        group_by=["order_month"],
        limit=12,
        discovery_limit=5,
    )
    body = json.loads(raw)

    assert body["dataset_id"] == "ds_orders"
    assert body["dataset_name"] == "Orders Monthly"
    assert body["matched_total"] == 3
    assert body["contract"]["contract_endpoint"] == "/v1/meta/contract"
    assert body["contract"]["mcp_contract_tool"] == "get_contract"
    assert body["query_hints"] == ["sum completed orders by order_month"]
    assert body["metadata"]["request_id"] == "req_query"
    assert body["metadata"]["tokens_in"] == 120
    assert body["result"][0]["completed_order_count"] == 91

    assert fake.calls == [
        (
            "list_datasets",
            {
                "search": "orders",
                "status": "ready",
                "source_name": None,
                "compact": True,
                "limit": 5,
            },
        ),
        ("get_dataset_summary", "ds_orders"),
        ("get_contract", None),
        (
            "query_with_metadata",
            {
                "dataset_id": "ds_orders",
                "metric": {"role": "derived_measure", "hint": "completed_order_count"},
                "aggregation": "sum",
                "group_by": ["order_month"],
                "limit": 12,
                "order": "desc",
            },
        ),
    ]


def test_inspect_algenta_contract_uses_public_sdk_contract_surface(monkeypatch) -> None:
    module = _load_module()

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def get_contract(self):
            self.calls.append(("get_contract", None))
            return SimpleNamespace(
                api_base_url="https://api.codna.ai",
                primary_data_query_contract=SimpleNamespace(
                    api=SimpleNamespace(
                        contract_endpoint="/v1/meta/contract",
                        discovery_endpoint="/v1/data",
                        summary_endpoint="/v1/data/{dataset_id}/summary",
                        query_endpoint="/v1/query",
                        query_batch_endpoint="/v1/query/batch",
                        query_sql_report_endpoint="/v1/query/sql-report",
                    ),
                    direct_sdk=SimpleNamespace(
                        python=SimpleNamespace(contract_method="get_contract"),
                        typescript=SimpleNamespace(contract_method="getContract"),
                    ),
                    cli=SimpleNamespace(contract_command="de contract"),
                    mcp=SimpleNamespace(contract_tool="get_contract"),
                ),
            )

    fake = FakeClient()
    monkeypatch.setattr(module, "_client", lambda: fake)

    raw = _invoke_tool(module.inspect_algenta_contract)
    body = json.loads(raw)

    assert body["api_base_url"] == "https://api.codna.ai"
    assert body["contract_endpoint"] == "/v1/meta/contract"
    assert body["discovery_endpoint"] == "/v1/data"
    assert body["query_batch_endpoint"] == "/v1/query/batch"
    assert body["python_contract_method"] == "get_contract"
    assert body["typescript_contract_method"] == "getContract"
    assert body["cli_contract_command"] == "de contract"
    assert body["mcp_contract_tool"] == "get_contract"
    assert fake.calls == [("get_contract", None)]


def test_inspect_runtime_lineage_uses_persisted_agent_and_control_plane_surfaces(
    monkeypatch,
) -> None:
    module = _load_module()

    class FakeItem:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload
            self.run_id = str(payload.get("run_id", ""))

        def model_dump(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def list_agent_runs(self, **kwargs):
            self.calls.append(("list_agent_runs", kwargs))
            return SimpleNamespace(
                runs=[FakeItem({"run_id": "run_agent_123", "status": "requires_approval"})],
            )

        def query_agent_run_checkpoints(self, **kwargs):
            self.calls.append(("query_agent_run_checkpoints", kwargs))
            return SimpleNamespace(
                checkpoints=[FakeItem({"checkpoint_id": "cp_2", "run_id": "run_agent_123"})],
            )

        def query_agent_run_mission_events(self, **kwargs):
            self.calls.append(("query_agent_run_mission_events", kwargs))
            return SimpleNamespace(
                events=[FakeItem({"event_type": "checkpoint_committed", "run_id": "run_agent_123"})],
            )

        def query_agent_run_telemetry(self, **kwargs):
            self.calls.append(("query_agent_run_telemetry", kwargs))
            return SimpleNamespace(
                entries=[FakeItem({"telemetry_kind": "checkpoint_commit", "run_id": "run_agent_123"})],
            )

        def get_audit_log_artifacts(self, **kwargs):
            self.calls.append(("get_audit_log_artifacts", kwargs))
            return SimpleNamespace(
                items=[FakeItem({"content_hash": "sha256:abc", "action": "agent_run.replay"})],
            )

        def list_execution_policy_snapshots(self):
            self.calls.append(("list_execution_policy_snapshots", None))
            return SimpleNamespace(
                snapshots=[FakeItem({"snapshot_id": "pol_1", "org_id": "org_demo"})],
            )

    fake = FakeClient()
    monkeypatch.setattr(module, "_client", lambda: fake)

    raw = _invoke_tool(module.inspect_runtime_lineage, status="requires_approval", run_limit=10, query_limit=25)
    body = json.loads(raw)

    assert body["selected_run_id"] == "run_agent_123"
    assert body["runs"][0]["status"] == "requires_approval"
    assert body["checkpoints"][0]["checkpoint_id"] == "cp_2"
    assert body["mission_events"][0]["event_type"] == "checkpoint_committed"
    assert body["telemetry"][0]["telemetry_kind"] == "checkpoint_commit"
    assert body["audit_artifacts"][0]["content_hash"] == "sha256:abc"
    assert body["policy_snapshots"][0]["snapshot_id"] == "pol_1"
    assert fake.calls == [
        ("list_agent_runs", {"status": "requires_approval", "limit": 10}),
        ("query_agent_run_checkpoints", {"run_id": "run_agent_123", "limit": 25}),
        ("query_agent_run_mission_events", {"run_id": "run_agent_123", "limit": 25}),
        ("query_agent_run_telemetry", {"run_id": "run_agent_123", "limit": 25}),
        ("get_audit_log_artifacts", {"limit": 25}),
        ("list_execution_policy_snapshots", None),
    ]


def test_query_dataset_batch_uses_query_batch_surface(monkeypatch) -> None:
    module = _load_module()

    class FakeBatchItem:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def model_dump(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def list_datasets(self, **kwargs):
            self.calls.append(("list_datasets", kwargs))
            return SimpleNamespace(
                datasets=[SimpleNamespace(dataset_id="ds_orders")],
                matched_total=1,
            )

        def get_dataset_summary(self, dataset_id: str):
            self.calls.append(("get_dataset_summary", dataset_id))
            return SimpleNamespace(dataset_id=dataset_id, name="Orders Monthly")

        def query_batch(self, request: dict[str, object]):
            self.calls.append(("query_batch", request))
            return SimpleNamespace(
                request_id="req_batch",
                results=[
                    FakeBatchItem(
                        {
                            "key": "overall_completed_orders",
                            "data": {"result": 924},
                            "metadata": {"request_id": "req_item", "latency_ms": 12.5},
                            "error": None,
                        }
                    )
                ],
            )

    fake = FakeClient()
    monkeypatch.setattr(module, "_client", lambda: fake)

    queries = [
        {
            "key": "overall_completed_orders",
            "request": {
                "metric": {"role": "derived_measure", "hint": "completed_order_count"},
                "aggregation": "sum",
            },
        }
    ]
    raw = _invoke_tool(module.query_dataset_batch, dataset_search="orders", queries=queries)
    body = json.loads(raw)

    assert body["dataset_id"] == "ds_orders"
    assert body["request_id"] == "req_batch"
    assert body["results"][0]["key"] == "overall_completed_orders"
    assert body["results"][0]["metadata"]["latency_ms"] == 12.5
    assert fake.calls[-1] == (
        "query_batch",
        {
            "defaults": {"dataset_id": "ds_orders"},
            "queries": queries,
        },
    )


def test_query_dataset_sql_report_uses_sql_report_surface(monkeypatch) -> None:
    module = _load_module()

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def list_datasets(self, **kwargs):
            self.calls.append(("list_datasets", kwargs))
            return SimpleNamespace(
                datasets=[SimpleNamespace(dataset_id="ds_orders")],
                matched_total=1,
            )

        def get_dataset_summary(self, dataset_id: str):
            self.calls.append(("get_dataset_summary", dataset_id))
            return SimpleNamespace(dataset_id=dataset_id, name="Orders Monthly")

        def query_sql_report(self, request: dict[str, object]):
            self.calls.append(("query_sql_report", request))
            return SimpleNamespace(
                columns=["order_month", "gross_revenue"],
                rows=[{"order_month": "2026-01-01", "gross_revenue": 91000.0}],
                row_count=1,
                truncated=False,
                request_id="req_sql",
                latency_ms=24.1,
            )

    fake = FakeClient()
    monkeypatch.setattr(module, "_client", lambda: fake)

    raw = _invoke_tool(
        module.query_dataset_sql_report,
        dataset_search="orders",
        sql="select order_month, gross_revenue from dataset order by order_month",
        alias="dataset",
        max_rows=100,
    )
    body = json.loads(raw)

    assert body["dataset_id"] == "ds_orders"
    assert body["columns"] == ["order_month", "gross_revenue"]
    assert body["row_count"] == 1
    assert body["request_id"] == "req_sql"
    assert fake.calls[-1] == (
        "query_sql_report",
        {
            "sources": [{"dataset_id": "ds_orders", "alias": "dataset"}],
            "sql": "select order_month, gross_revenue from dataset order by order_month",
            "max_rows": 100,
        },
    )


def test_query_dataset_metric_returns_structured_error_when_no_dataset_matches(monkeypatch) -> None:
    module = _load_module()

    class FakeClient:
        def list_datasets(self, **kwargs):
            return SimpleNamespace(datasets=[], matched_total=0)

    monkeypatch.setattr(module, "_client", lambda: FakeClient())

    raw = _invoke_tool(
        module.query_dataset_metric, dataset_search="missing", metric_hint="completed_order_count"
    )
    body = json.loads(raw)

    assert body["error"]["code"] == "dataset_not_found"
    assert "missing" in body["error"]["message"]
