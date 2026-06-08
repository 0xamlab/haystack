from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")

AlgentaClient = algenta.AlgentaClient


class _FakeDecisionEngineClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(self, call_name: str, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append((call_name, args, kwargs))
        return {"name": call_name, "args": list(args), "kwargs": kwargs}

    def plan_decision(self, request):
        return self._record("plan_decision", request)

    def recommend(self, actions, **kwargs):
        return self._record("recommend", actions, **kwargs)

    def score(self, request, *, scoring_weights=None):
        return self._record("score", request, scoring_weights=scoring_weights)

    def batch(self, items):
        return self._record("batch", items)

    def compare(self, scenarios, **kwargs):
        return self._record("compare", scenarios, **kwargs)

    def get_contract(self):
        return self._record("get_contract")

    def get_runtime_manifest(self):
        return self._record("get_runtime_manifest")

    def get_runtime_modules(self):
        return self._record("get_runtime_modules")

    def get_runtime_benchmarks(self):
        return self._record("get_runtime_benchmarks")

    def get_runtime_release_validation(self):
        return self._record("get_runtime_release_validation")

    def resolve(self, request=None, **kwargs):
        return self._record("resolve", request, **kwargs)

    def query(self, request=None, **kwargs):
        return self._record("query", request, **kwargs)

    def query_with_metadata(self, request=None, **kwargs):
        return self._record("query_with_metadata", request, **kwargs)

    def query_batch(self, request):
        return self._record("query_batch", request)

    def query_sql_report(self, request):
        return self._record("query_sql_report", request)

    def verify(self, request=None, **kwargs):
        return self._record("verify", request, **kwargs)

    def list_connectors(self, *, page, limit):
        return self._record("list_connectors", page=page, limit=limit)

    def create_connector(
        self,
        *,
        name,
        connector_type,
        config=None,
        description=None,
        visibility=None,
    ):
        return self._record(
            "create_connector",
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        )

    def get_connector(self, connector_id):
        return self._record("get_connector", connector_id)

    def update_connector(
        self,
        connector_id,
        *,
        name=None,
        description=None,
        visibility=None,
        config=None,
    ):
        return self._record(
            "update_connector",
            connector_id,
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        )

    def test_connector(self, connector_id):
        return self._record("test_connector", connector_id)

    def preview_test_connector(self, *, connector_type, config=None):
        return self._record(
            "preview_test_connector",
            connector_type=connector_type,
            config=config,
        )

    def browse_connector(self, connector_id):
        return self._record("browse_connector", connector_id)

    def preview_browse_connector(self, *, connector_type, config=None):
        return self._record(
            "preview_browse_connector",
            connector_type=connector_type,
            config=config,
        )

    def delete_connector(self, connector_id):
        return self._record("delete_connector", connector_id)

    def connect_data(self, request=None, **kwargs):
        return self._record("connect_data", request, **kwargs)

    def list_datasets(
        self,
        *,
        page,
        limit,
        search,
        status,
        source_name,
        compact,
    ):
        return self._record(
            "list_datasets",
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def get_dataset(self, dataset_id):
        return self._record("get_dataset", dataset_id)

    def get_dataset_summary(self, dataset_id):
        return self._record("get_dataset_summary", dataset_id)

    def refresh_dataset(self, dataset_id):
        return self._record("refresh_dataset", dataset_id)

    def delete_dataset(self, dataset_id):
        return self._record("delete_dataset", dataset_id)

    def me(self):
        return self._record("me")

    def update_me(self, *, name=None, org_name=None):
        return self._record("update_me", name=name, org_name=org_name)

    def limits(self):
        return self._record("limits")

    def list_api_keys(self):
        return self._record("list_api_keys")

    def create_api_key(self, label=None, *, name=None, expires_at=None, device_limit=None):
        return self._record(
            "create_api_key",
            label=label,
            name=name,
            expires_at=expires_at,
            device_limit=device_limit,
        )

    def revoke_api_key(self, key_id):
        return self._record("revoke_api_key", key_id)

    def list_deployment_regions(self):
        return self._record("list_deployment_regions")

    def get_deployment(self):
        return self._record("get_deployment")

    def create_deployment(self, *, provider, region, config, billing_markup_pct):
        return self._record(
            "create_deployment",
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    def delete_deployment(self, deployment_id):
        return self._record("delete_deployment", deployment_id)

    def get_deployment_cost(self, deployment_id):
        return self._record("get_deployment_cost", deployment_id)

    def list_models(self):
        return self._record("list_models")

    def tokenize(self, text, *, model):
        return self._record("tokenize", text, model=model)

    def count_tokens(self, text, *, model):
        return self._record("count_tokens", text, model=model)

    def chat_completions(self, messages, *, model):
        return self._record("chat_completions", messages, model=model)

    def stream_chat_completions(self, messages, *, model):
        return self._record("stream_chat_completions", messages, model=model)

    def responses(self, input_value, *, model, dimensions):
        return self._record("responses", input_value, model=model, dimensions=dimensions)

    def stream_responses(self, input_value, *, model, dimensions):
        return self._record("stream_responses", input_value, model=model, dimensions=dimensions)

    def embeddings(self, input_value, *, model, dimensions):
        return self._record("embeddings", input_value, model=model, dimensions=dimensions)

    def embedding_similarity(self, left, right, *, model):
        return self._record("embedding_similarity", left, right, model=model)

    def rerank(self, query_embedding, documents, *, model, top_n):
        return self._record(
            "rerank",
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )

    def create_agent_run(
        self,
        *,
        task,
        context,
        tools,
        max_steps,
        output_format,
        approval_mode,
        start_paused,
    ):
        return self._record(
            "create_agent_run",
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    def get_agent_run(self, run_id):
        return self._record("get_agent_run", run_id)

    def list_agent_runs(
        self,
        *,
        page=1,
        limit=25,
        status=None,
        request_hash=None,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
    ):
        return self._record(
            "list_agent_runs",
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        )

    def get_agent_run_events(self, run_id, *, limit):
        return self._record("get_agent_run_events", run_id, limit=limit)

    def stream_agent_run_events(self, run_id, *, limit):
        return self._record("stream_agent_run_events", run_id, limit=limit)

    def list_agent_run_checkpoints(self, run_id):
        return self._record("list_agent_run_checkpoints", run_id)

    def query_agent_run_checkpoints(
        self,
        *,
        page=1,
        limit=25,
        status=None,
        request_hash=None,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
        run_id=None,
        checkpoint_id=None,
    ):
        return self._record(
            "query_agent_run_checkpoints",
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        )

    def query_agent_run_mission_events(
        self,
        *,
        page=1,
        limit=25,
        status=None,
        request_hash=None,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
        run_id=None,
        event_type=None,
    ):
        return self._record(
            "query_agent_run_mission_events",
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        )

    def replay_agent_run(self, run_id, *, checkpoint_id=None):
        return self._record("replay_agent_run", run_id, checkpoint_id=checkpoint_id)

    def fork_agent_run(self, run_id, *, checkpoint_id=None):
        return self._record("fork_agent_run", run_id, checkpoint_id=checkpoint_id)

    def resume_agent_run(self, run_id):
        return self._record("resume_agent_run", run_id)

    def cancel_agent_run(self, run_id):
        return self._record("cancel_agent_run", run_id)

    def approve_agent_run(self, run_id):
        return self._record("approve_agent_run", run_id)

    def query_agent_run_telemetry(
        self,
        *,
        page=1,
        limit=25,
        status=None,
        request_hash=None,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
        run_id=None,
        telemetry_kind=None,
        module_name=None,
    ):
        return self._record(
            "query_agent_run_telemetry",
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            telemetry_kind=telemetry_kind,
            module_name=module_name,
        )

    def submit_job(self, request=None, callback_url=None, **kwargs):
        return self._record("submit_job", request, callback_url=callback_url, **kwargs)

    def get_job(self, job_id):
        return self._record("get_job", job_id)

    def get_job_result(self, job_id):
        return self._record("get_job_result", job_id)

    def cancel_job(self, job_id):
        return self._record("cancel_job", job_id)

    def poll_job(self, job_id, *, timeout=300.0, poll_interval=2.0):
        return self._record(
            "poll_job",
            job_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )


class _FakeBoundModule:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def risk(
        self,
        *,
        runs: int,
        mode: str,
        api_key: str,
        base_url: str,
        revenue: float,
        cost: float,
    ):
        payload = {
            "runs": runs,
            "mode": mode,
            "api_key": api_key,
            "base_url": base_url,
            "revenue": revenue,
            "cost": cost,
        }
        self.calls.append(payload)
        return payload


def test_algenta_client_cloud_methods_delegate_to_decision_engine_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = type("FakeDecisionEngineModule", (), {"DecisionEngineClient": _FakeDecisionEngineClient})
    client_module = importlib.import_module("algenta.client")
    monkeypatch.setattr(client_module, "import_module", lambda name: fake_module)

    client = AlgentaClient(api_key="de_test", base_url="http://localhost:8000")

    assert client.plan_decision({"metric": "profit"})["name"] == "plan_decision"
    assert client.recommend([{"name": "expand", "score": 0.82}])["name"] == "recommend"
    assert (
        client.score({"mode": "expert", "simulation": {"variables": []}}, scoring_weights={"risk": 0.2})[
            "name"
        ]
        == "score"
    )
    assert client.batch([{"mode": "expert", "simulation": {"variables": []}}])["name"] == "batch"
    assert client.compare([{"name": "base"}, {"name": "stretch"}], metric="profit")["name"] == "compare"
    assert client.get_contract()["name"] == "get_contract"
    assert client.get_runtime_manifest()["name"] == "get_runtime_manifest"
    assert client.get_runtime_modules()["name"] == "get_runtime_modules"
    assert client.get_runtime_benchmarks()["name"] == "get_runtime_benchmarks"
    assert (
        client.get_runtime_release_validation()["name"]
        == "get_runtime_release_validation"
    )
    assert client.resolve({"dataset_id": "ds_1"}, aggregation="sum")["name"] == "resolve"
    assert client.query({"dataset_id": "ds_1"}, limit=5)["name"] == "query"
    assert client.query_with_metadata({"dataset_id": "ds_1"}, limit=5)["name"] == "query_with_metadata"
    assert client.query_batch({"queries": []})["name"] == "query_batch"
    assert client.query_sql_report({"sql": "SELECT 1"})["name"] == "query_sql_report"
    assert client.verify({"dataset_id": "ds_1"}, aggregation="sum")["name"] == "verify"
    assert client.list_connectors(page=1, limit=50)["name"] == "list_connectors"
    assert client.create_connector(
        name="Orders REST",
        connector_type="rest",
        config={"url": "https://example.com/orders.json", "data_path": "items"},
        description="Saved connector",
    )["name"] == "create_connector"
    assert client.get_connector("conn_123")["name"] == "get_connector"
    assert client.update_connector("conn_123", description="Updated connector")["name"] == "update_connector"
    assert client.test_connector("conn_123")["name"] == "test_connector"
    assert client.preview_test_connector(
        connector_type="rest",
        config={"url": "https://example.com/orders.json", "data_path": "items"},
    )["name"] == "preview_test_connector"
    assert client.browse_connector("conn_123")["name"] == "browse_connector"
    assert client.preview_browse_connector(
        connector_type="rest",
        config={"url": "https://example.com/orders.json", "data_path": "items"},
    )["name"] == "preview_browse_connector"
    assert client.delete_connector("conn_123")["name"] == "delete_connector"
    assert client.connect_data(connection_type="file_upload", dataset_name="orders", csv="id,amount\n1,10\n")[
        "name"
    ] == "connect_data"
    assert (
        client.list_datasets(search="orders", compact=True)["name"] == "list_datasets"
    )
    assert client.get_dataset("ds_1")["name"] == "get_dataset"
    assert client.get_dataset_summary("ds_1")["name"] == "get_dataset_summary"
    assert client.refresh_dataset("ds_1")["name"] == "refresh_dataset"
    assert client.delete_dataset("ds_1")["name"] == "delete_dataset"
    assert client.me()["name"] == "me"
    assert client.update_me(name="Mission Ops")["name"] == "update_me"
    assert client.limits()["name"] == "limits"
    assert client.list_api_keys()["name"] == "list_api_keys"
    assert client.create_api_key(name="Mission Runtime Key", device_limit=2)["name"] == "create_api_key"
    assert client.revoke_api_key("key_1")["name"] == "revoke_api_key"
    assert client.list_deployment_regions()["name"] == "list_deployment_regions"
    assert client.get_deployment()["name"] == "get_deployment"
    assert client.create_deployment()["name"] == "create_deployment"
    assert client.get_deployment_cost("dep_1")["name"] == "get_deployment_cost"
    assert client.delete_deployment("dep_1")["name"] == "delete_deployment"
    assert client.list_models()["name"] == "list_models"
    assert client.tokenize("hello")["name"] == "tokenize"
    assert client.count_tokens("hello")["name"] == "count_tokens"
    assert client.chat_completions([{"role": "user", "content": "hello"}])["name"] == "chat_completions"
    assert (
        client.stream_chat_completions([{"role": "user", "content": "hello"}])["name"]
        == "stream_chat_completions"
    )
    assert client.responses("hello")["name"] == "responses"
    assert client.stream_responses("hello")["name"] == "stream_responses"
    assert client.embeddings("hello")["name"] == "embeddings"
    assert client.embedding_similarity([0.1], [0.1])["name"] == "embedding_similarity"
    assert client.rerank([0.1], [{"id": "doc-1", "embedding": [0.1]}], top_n=1)["name"] == "rerank"
    assert client.create_agent_run(task="Search", approval_mode="manual")["name"] == "create_agent_run"
    assert client.get_agent_run("run-1")["name"] == "get_agent_run"
    assert client.list_agent_runs(status="requires_approval")["name"] == "list_agent_runs"
    assert client.get_agent_run_events("run-1", limit=25)["name"] == "get_agent_run_events"
    assert client.stream_agent_run_events("run-1", limit=25)["name"] == "stream_agent_run_events"
    assert client.list_agent_run_checkpoints("run-1")["name"] == "list_agent_run_checkpoints"
    assert (
        client.query_agent_run_checkpoints(
            status="completed",
            request_hash="hash_123",
            policy_snapshot_id="policy-v1",
            schema_snapshot_id="schema-v1",
            run_id="run-1",
            checkpoint_id="cp_1",
        )["name"]
        == "query_agent_run_checkpoints"
    )
    assert (
        client.query_agent_run_mission_events(
            status="completed",
            request_hash="hash_123",
            policy_snapshot_id="policy-v1",
            schema_snapshot_id="schema-v1",
            run_id="run-1",
            event_type="run_completed",
        )["name"]
        == "query_agent_run_mission_events"
    )
    assert client.replay_agent_run("run-1", checkpoint_id="cp_1")["name"] == "replay_agent_run"
    assert client.fork_agent_run("run-1", checkpoint_id="cp_1")["name"] == "fork_agent_run"
    assert client.resume_agent_run("run-1")["name"] == "resume_agent_run"
    assert client.cancel_agent_run("run-1")["name"] == "cancel_agent_run"
    assert client.approve_agent_run("run-1")["name"] == "approve_agent_run"
    assert (
        client.query_agent_run_telemetry(
            status="completed",
            request_hash="hash_123",
            policy_snapshot_id="policy-v1",
            schema_snapshot_id="schema-v1",
            run_id="run-1",
            telemetry_kind="agent_run_completion",
            module_name="agent_run_service",
        )["name"]
        == "query_agent_run_telemetry"
    )
    assert client.submit_job({"mode": "auto"}, callback_url="https://example.com/hook")["name"] == "submit_job"
    assert client.get_job("job_123")["name"] == "get_job"
    assert client.get_job_result("job_123")["name"] == "get_job_result"
    assert client.cancel_job("job_123")["name"] == "cancel_job"
    assert client.poll_job("job_123", timeout=30.0, poll_interval=0.5)["name"] == "poll_job"

    bridge = client._sdk_client()
    assert isinstance(bridge, _FakeDecisionEngineClient)
    assert bridge.kwargs == {
        "api_key": "de_test",
        "base_url": "http://localhost:8000",
        "max_retries": 0,
    }


def test_algenta_client_reuses_lazy_decision_engine_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[_FakeDecisionEngineClient] = []

    class _Factory(_FakeDecisionEngineClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            created.append(self)

    fake_module = type("FakeDecisionEngineModule", (), {"DecisionEngineClient": _Factory})
    client_module = importlib.import_module("algenta.client")
    monkeypatch.setattr(client_module, "import_module", lambda name: fake_module)

    client = AlgentaClient(api_key="de_test", base_url="http://localhost:8000")

    first = client._sdk_client()
    second = client._sdk_client()

    assert first is second
    assert created == [first]
    assert first.kwargs["max_retries"] == 0


def test_algenta_client_plan_surface_reports_missing_decision_engine_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_module = importlib.import_module("algenta.client")

    def _raise_import(name: str):
        raise ImportError("missing decision_engine")

    monkeypatch.setattr(client_module, "import_module", _raise_import)

    client = AlgentaClient(api_key="de_test", base_url="http://localhost:8000")

    with pytest.raises(ImportError, match="decision-engine SDK package"):
        client.list_models()


def test_algenta_client_bound_module_injects_only_supported_transport_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = _FakeBoundModule()
    monkeypatch.setitem(sys.modules, "algenta.simulate", fake_module)

    client = AlgentaClient(api_key="de_test", base_url="http://localhost:8000")
    result = client.simulate.risk(revenue=120000.0, cost=-70000.0, runs=250)

    assert result == {
        "runs": 250,
        "mode": "cloud",
        "api_key": "de_test",
        "base_url": "http://localhost:8000",
        "revenue": 120000.0,
        "cost": -70000.0,
    }
    assert fake_module.calls == [result]
