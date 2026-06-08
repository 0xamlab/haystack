from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta.runtime_api_exact import (  # noqa: E402
    _RUNTIME_DATASET_SCOPE_KEY,
    forget_api_registration,
    remember_api_registration,
    try_exact_api_resolve,
)
from algenta.runtime_models import SourceRegistration  # noqa: E402


def _registration() -> SourceRegistration:
    return SourceRegistration(
        source_id="src_1",
        dataset_id="src_1",
        name="orders",
        status="ready",
        source_schema={"source": "orders", "fields": ["amount", "customer"]},
        planner_schema_revision="planner_rev_1",
        row_count=3,
    )


class _FakeClient:
    def __init__(self) -> None:
        self.source_schema_calls = 0

    def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/sources/src_1"
        self.source_schema_calls += 1
        return {"entry": {"source_schema_revision": "source_rev_1"}}


def test_try_exact_api_resolve_reuses_cached_source_schema_revision() -> None:
    registrations_by_name: dict[str, SourceRegistration] = {}
    registrations_by_dataset: dict[str, SourceRegistration] = {}
    source_schema_revision_cache: dict[str, str] = {}
    registration = _registration()
    remember_api_registration(registrations_by_name, registrations_by_dataset, registration)
    client = _FakeClient()
    request = {
        "source_name": "orders",
        "metric": "amount",
        "group_by": "customer",
        "aggregation": "sum",
    }

    first = try_exact_api_resolve(
        request,
        registrations_by_name=registrations_by_name,
        registrations_by_dataset=registrations_by_dataset,
        source_schema_revision_cache=source_schema_revision_cache,
        client_factory=lambda: client,
        resolve_aggregation=lambda payload: str(payload.get("aggregation", "sum")),
        intent_signature=lambda name, _payload, revision: f"{name}:{revision}",
        plan_hash=lambda plan: f"plan:{plan.metric_column}:{plan.group_column}",
        started_at=time.perf_counter(),
    )
    second = try_exact_api_resolve(
        request,
        registrations_by_name=registrations_by_name,
        registrations_by_dataset=registrations_by_dataset,
        source_schema_revision_cache=source_schema_revision_cache,
        client_factory=lambda: client,
        resolve_aggregation=lambda payload: str(payload.get("aggregation", "sum")),
        intent_signature=lambda name, _payload, revision: f"{name}:{revision}",
        plan_hash=lambda plan: f"plan:{plan.metric_column}:{plan.group_column}",
        started_at=time.perf_counter(),
    )

    assert first is not None
    assert second is not None
    assert first.resolved_plan is not None
    assert second.resolved_plan is not None
    assert first.resolved_plan.source_name == "orders"
    assert first.resolved_plan.schema_revision == "source_rev_1"
    assert second.resolved_plan.schema_revision == "source_rev_1"
    assert first.resolved_plan.constraints[_RUNTIME_DATASET_SCOPE_KEY] == "src_1"
    assert client.source_schema_calls == 1
    assert source_schema_revision_cache == {"src_1": "source_rev_1"}


def test_try_exact_api_resolve_skips_schema_fetch_for_non_exact_metric() -> None:
    registrations_by_name: dict[str, SourceRegistration] = {}
    registrations_by_dataset: dict[str, SourceRegistration] = {}
    source_schema_revision_cache: dict[str, str] = {}
    registration = _registration()
    remember_api_registration(registrations_by_name, registrations_by_dataset, registration)
    request = {
        "source_name": "orders",
        "metric": "gross_revenue",
        "group_by": "customer",
        "aggregation": "sum",
    }

    class _FailingClient:
        def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
            raise AssertionError("non-exact requests must not fetch source schema revision")

    resolved = try_exact_api_resolve(
        request,
        registrations_by_name=registrations_by_name,
        registrations_by_dataset=registrations_by_dataset,
        source_schema_revision_cache=source_schema_revision_cache,
        client_factory=_FailingClient,
        resolve_aggregation=lambda payload: str(payload.get("aggregation", "sum")),
        intent_signature=lambda name, _payload, revision: f"{name}:{revision}",
        plan_hash=lambda plan: f"plan:{plan.metric_column}:{plan.group_column}",
        started_at=time.perf_counter(),
    )

    assert resolved is None
    assert source_schema_revision_cache == {}


def test_try_exact_api_resolve_uses_canonical_registered_source_name() -> None:
    registrations_by_name: dict[str, SourceRegistration] = {}
    registrations_by_dataset: dict[str, SourceRegistration] = {}
    source_schema_revision_cache: dict[str, str] = {}
    registration = SourceRegistration(
        source_id="src_1",
        dataset_id="src_1",
        name="orders_alias",
        status="already_registered",
        source_schema={"source": "orders", "fields": ["amount", "customer"]},
        planner_schema_revision="planner_rev_1",
        row_count=3,
    )
    remember_api_registration(registrations_by_name, registrations_by_dataset, registration)

    class _FakeClient:
        def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
            assert method == "GET"
            assert path == "/v1/sources/src_1"
            return {"entry": {"source_schema_revision": "source_rev_1"}}

    resolved = try_exact_api_resolve(
        {
            "source_name": "orders_alias",
            "metric": "amount",
            "aggregation": "sum",
        },
        registrations_by_name=registrations_by_name,
        registrations_by_dataset=registrations_by_dataset,
        source_schema_revision_cache=source_schema_revision_cache,
        client_factory=_FakeClient,
        resolve_aggregation=lambda payload: str(payload.get("aggregation", "sum")),
        intent_signature=lambda name, _payload, revision: f"{name}:{revision}",
        plan_hash=lambda plan: f"plan:{plan.metric_column}:{plan.group_column}",
        started_at=time.perf_counter(),
    )

    assert resolved is not None
    assert resolved.resolved_plan is not None
    assert resolved.resolved_plan.source_name == "orders"
    assert resolved.resolved_plan.constraints[_RUNTIME_DATASET_SCOPE_KEY] == "src_1"


def test_forget_api_registration_clears_schema_revision_cache() -> None:
    registrations_by_name: dict[str, SourceRegistration] = {}
    registrations_by_dataset: dict[str, SourceRegistration] = {}
    source_schema_revision_cache = {"src_1": "source_rev_1"}
    registration = _registration()

    remember_api_registration(registrations_by_name, registrations_by_dataset, registration)
    forget_api_registration(
        registrations_by_name,
        registrations_by_dataset,
        source_schema_revision_cache,
        "src_1",
    )

    assert registrations_by_name == {}
    assert registrations_by_dataset == {}
    assert source_schema_revision_cache == {}
